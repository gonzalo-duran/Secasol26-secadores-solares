"""
Obtención y caché de datos climáticos NASA POWER.

Descarga datos horarios anuales vía pvlib.iotools.get_nasa_power,
aplica la política de huecos y guarda/lee el caché en parquet.

Política de huecos:
    Huecos ≤ 3 h consecutivos → interpolación lineal en tiempo.
    Huecos > 3 h              → se dejan como NaN; CalidadClima.n_horas_bloqueadas > 0
                                 indica que la UI debe solicitar decisión al usuario.

Conversiones NASA POWER → SI (realizadas aquí, no en core/):
    Temperatura: °C → K  (+273.15)
    Presión:     kPa → Pa (×1000)
    HR:          % → fracción (÷100)
    GHI/DNI/DHI y velocidad del viento: ya en W/m² y m/s (sin conversión).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime
from typing import Optional

import numpy as np  # noqa: F401  (requerido por pvlib internamente)
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pvlib.iotools

from core.clima import CalidadClima, Clima, COLUMNAS_SI
from core.emplazamiento import Emplazamiento

# Parámetros solicitados a NASA POWER (mezcla de nombres pvlib y nativos NASA).
# pvlib traduce los nombres pvlib → NASA internamente al armar la URL.
_PARAMETROS_NASA: list[str] = [
    "ghi",           # ALLSKY_SFC_SW_DWN → ghi [W/m²]
    "dni",           # ALLSKY_SFC_SW_DNI → dni [W/m²]
    "dhi",           # ALLSKY_SFC_SW_DIFF → dhi [W/m²]
    "temp_air",      # T2M → temp_air [°C a 2 m]
    "wind_speed_2m", # WS2M → wind_speed_2m [m/s a 2 m]
    "RH2M",          # Humedad relativa a 2 m [%] (no mapeado por pvlib, nombre NASA)
    "PS",            # Presión superficial [kPa] (no mapeado por pvlib, nombre NASA)
]

# Mapeo columnas pvlib/NASA → nombres SI del proyecto (COLUMNAS_SI)
_RENOMBRES: dict[str, str] = {
    "temp_air": "T_amb_K",
    "ghi": "GHI_Wm2",
    "dni": "DNI_Wm2",
    "dhi": "DHI_Wm2",
    "wind_speed_2m": "WS_ms",
    "PS": "presion_Pa",
    "RH2M": "HR",
}

# Rutas de caché
_RAIZ: pathlib.Path = pathlib.Path(__file__).parent.parent
_DIR_CACHE: pathlib.Path = _RAIZ / "data" / "cache" / "nasa_power"

# Clave de metadatos embebidos en el archivo parquet
_META_ALTITUD_KEY: bytes = b"altitud_nasa_m"


# ---------------------------------------------------------------------------
# Helpers de caché
# ---------------------------------------------------------------------------


def _hash_cache(lat: float, lon: float, anio: int) -> str:
    """Genera un identificador único para la combinación (lat, lon, año).

    Args:
        lat: Latitud redondeada a 4 decimales para la clave.
        lon: Longitud redondeada a 4 decimales para la clave.
        anio: Año calendario de los datos.

    Returns:
        Hash SHA-256 hexadecimal de 64 caracteres.
    """
    clave = {"lat": round(lat, 4), "lon": round(lon, 4), "anio": anio}
    return hashlib.sha256(json.dumps(clave, sort_keys=True).encode()).hexdigest()


def _ruta_cache(lat: float, lon: float, anio: int) -> pathlib.Path:
    """Devuelve la ruta del parquet de caché, creando el directorio si es necesario.

    Args:
        lat: Latitud del sitio.
        lon: Longitud del sitio.
        anio: Año calendario.

    Returns:
        Ruta del archivo parquet de caché.
    """
    _DIR_CACHE.mkdir(parents=True, exist_ok=True)
    return _DIR_CACHE / f"{_hash_cache(lat, lon, anio)}.parquet"


# ---------------------------------------------------------------------------
# Política de huecos
# ---------------------------------------------------------------------------


def _aplicar_politica_huecos(df: pd.DataFrame) -> tuple[pd.DataFrame, CalidadClima]:
    """Detecta huecos e interpola los de duración ≤ 3 h; deja NaN los de > 3 h.

    Se consideran "huecos" las secuencias de filas en que AL MENOS UNA columna
    tiene valor NaN. La estrategia es:
        1. Identificar todos los grupos de huecos y su duración.
        2. Interpolar todo el DataFrame (sin límite).
        3. Restaurar NaN en los grupos de duración > 3 h.

    Nota: no se usa interpolate(limit=3) directamente porque ese parámetro
    rellena desde ambos extremos del hueco, pudiendo llenar gaps de > 3 h
    completamente cuando la suma de ambos lados supera 3.

    Args:
        df: DataFrame con índice DatetimeIndex tz-aware y posibles NaN.

    Returns:
        Tupla (df_corregido, calidad):
            df_corregido: DataFrame con huecos ≤ 3 h interpolados.
            calidad: CalidadClima con estadísticas de huecos.
    """
    hay_nulo = df.isna().any(axis=1)

    # Identificar secuencias contiguas de filas con al menos un NaN
    cambio = hay_nulo != hay_nulo.shift(fill_value=False)
    grupo_id = cambio.cumsum()

    duraciones: list[int] = []
    mascara_grandes: pd.Series = pd.Series(False, index=df.index)

    for gid, bloque in hay_nulo.groupby(grupo_id):
        if bloque.all():
            dur = int(bloque.sum())
            duraciones.append(dur)
            if dur > 3:
                mascara_grandes[bloque.index] = True

    calidad = CalidadClima(
        n_huecos_originales=len(duraciones),
        mayor_hueco_h=max(duraciones, default=0),
    )

    # Interpolar todo el DataFrame (sin límite) y luego restaurar gaps > 3 h
    df_corr = df.copy()
    for col in df_corr.columns:
        df_corr[col] = df_corr[col].interpolate(method="time")
        df_corr.loc[mascara_grandes, col] = float("nan")

    n_interpoladas = int(hay_nulo.sum()) - int(df_corr.isna().any(axis=1).sum())
    calidad.n_horas_interpoladas = n_interpoladas
    calidad.n_horas_bloqueadas = int(df_corr.isna().any(axis=1).sum())

    return df_corr, calidad


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------


def obtener_clima(
    emplazamiento: Emplazamiento,
    anio: int,
    forzar_descarga: bool = False,
) -> Clima:
    """Obtiene datos climáticos horarios de NASA POWER para el emplazamiento y año.

    Flujo:
        1. Busca en caché local (parquet con metadatos embebidos).
        2. Si no existe o forzar_descarga=True, consulta la API de NASA POWER.
        3. Convierte los datos a unidades SI.
        4. Aplica la política de huecos.
        5. Guarda el resultado en caché.

    Args:
        emplazamiento: Dataclass con lat, lon y zona horaria del sitio.
        anio: Año calendario de los datos (ej.: 2022). Rango recomendado: 2000–2023.
        forzar_descarga: Si True, ignora el caché y descarga nuevamente desde NASA POWER.

    Returns:
        Objeto Clima con datos en SI, metadatos de calidad y altitud del punto de grilla.

    Raises:
        RuntimeError: Si la descarga desde NASA POWER falla por error de red o API.
        ValueError: Si el año solicitado está fuera del rango disponible en NASA POWER.
    """
    lat = emplazamiento.latitud_deg
    lon = emplazamiento.longitud_deg
    ruta = _ruta_cache(lat, lon, anio)

    # --- Intentar leer desde caché ---
    if ruta.exists() and not forzar_descarga:
        tabla = pq.read_table(str(ruta))
        df = tabla.to_pandas()
        meta = tabla.schema.metadata or {}
        altitud_nasa = float(meta.get(_META_ALTITUD_KEY, b"0.0"))
        return Clima(
            datos=df,
            anio=anio,
            calidad=CalidadClima(),
            altitud_nasa_m=altitud_nasa,
        )

    # --- Descarga desde NASA POWER ---
    inicio = datetime(anio, 1, 1)
    fin = datetime(anio, 12, 31)
    try:
        df_raw, meta_nasa = pvlib.iotools.get_nasa_power(
            latitude=lat,
            longitude=lon,
            start=inicio,
            end=fin,
            parameters=_PARAMETROS_NASA,
            map_variables=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"CLIMA_DESCARGA_FALLIDA: no se pudo obtener datos de NASA POWER "
            f"para ({lat:.4f}, {lon:.4f}), año {anio}. Causa: {exc}"
        ) from exc

    # --- Renombrar columnas y reordenar ---
    columnas_presentes = [c for c in _RENOMBRES if c in df_raw.columns]
    df = df_raw[columnas_presentes].rename(columns=_RENOMBRES)

    # Verificar que todas las columnas esperadas están presentes
    faltantes = set(COLUMNAS_SI) - set(df.columns)
    if faltantes:
        raise RuntimeError(
            f"CLIMA_COLUMNAS_FALTANTES: NASA POWER no devolvió las columnas: "
            f"{faltantes}. Revisar parámetros solicitados."
        )
    df = df[list(COLUMNAS_SI)]  # ordenar según COLUMNAS_SI

    # --- Convertir a SI ---
    df["T_amb_K"] = df["T_amb_K"] + 273.15      # °C → K
    df["presion_Pa"] = df["presion_Pa"] * 1000.0  # kPa → Pa
    df["HR"] = df["HR"] / 100.0                   # % → fracción [0, 1]

    # --- Política de huecos ---
    df, calidad = _aplicar_politica_huecos(df)

    # --- Guardar en caché con altitud embebida en metadatos parquet ---
    altitud_nasa = float(meta_nasa.get("altitude", 0.0))
    tabla = pa.Table.from_pandas(df)
    meta_parquet: dict[bytes, bytes] = dict(tabla.schema.metadata or {})
    meta_parquet[_META_ALTITUD_KEY] = str(altitud_nasa).encode()
    tabla = tabla.replace_schema_metadata(meta_parquet)
    pq.write_table(tabla, str(ruta))

    return Clima(
        datos=df,
        anio=anio,
        calidad=calidad,
        altitud_nasa_m=altitud_nasa,
    )
