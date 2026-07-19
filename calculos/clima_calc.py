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
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np  # noqa: F401  (requerido por pvlib internamente)
import pandas as pd
import pvlib.iotools
import pvlib.irradiance
import pvlib.solarposition
import pyarrow as pa
import pyarrow.parquet as pq

from calculos.conversiones_angulo import acimut_duffie_a_pvlib
from core.clima import COLUMNA_POA_MEDIDA, COLUMNAS_SI, CalidadClima, Clima
from core.emplazamiento import Emplazamiento

# Parámetros solicitados a NASA POWER (mezcla de nombres pvlib y nativos NASA).
# pvlib traduce los nombres pvlib → NASA internamente al armar la URL.
_PARAMETROS_NASA: list[str] = [
    "ghi",  # ALLSKY_SFC_SW_DWN → ghi [W/m²]
    "dni",  # ALLSKY_SFC_SW_DNI → dni [W/m²]
    "dhi",  # ALLSKY_SFC_SW_DIFF → dhi [W/m²]
    "temp_air",  # T2M → temp_air [°C a 2 m]
    "wind_speed_2m",  # WS2M → wind_speed_2m [m/s a 2 m]
    "RH2M",  # Humedad relativa a 2 m [%] (no mapeado por pvlib, nombre NASA)
    "PS",  # Presión superficial [kPa] (no mapeado por pvlib, nombre NASA)
]

# Mapeo columnas pvlib/NASA → nombres SI del proyecto (COLUMNAS_SI)
#
# Para HR y presión incluimos AMBOS nombres posibles: el crudo de NASA
# (`RH2M`, `PS`) y el mapeado por pvlib (`relative_humidity`, `pressure`).
# Hasta pvlib 0.15.1 esos dos parámetros NO estaban en VARIABLE_MAP, así que
# con map_variables=True quedaban con su nombre crudo; desde 0.15.2 pvlib los
# mapea. Como una versión dada solo produce uno de cada par, tener ambas claves
# es inocuo (_columnas_presentes filtra a lo que exista) y evita el error
# CLIMA_COLUMNAS_FALTANTES al desplegar contra una versión distinta de pvlib.
_RENOMBRES: dict[str, str] = {
    "temp_air": "T_amb_K",
    "ghi": "GHI_Wm2",
    "dni": "DNI_Wm2",
    "dhi": "DHI_Wm2",
    "wind_speed_2m": "WS_ms",
    "PS": "presion_Pa",
    "pressure": "presion_Pa",
    "RH2M": "HR",
    "relative_humidity": "HR",
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


def aplicar_politica_huecos(df: pd.DataFrame) -> tuple[pd.DataFrame, CalidadClima]:
    """Alias público de la política de huecos (la reusa la ingesta de datos
    medidos, ``calculos/clima_medido.py``, sobre la serie ya horaria)."""
    return _aplicar_politica_huecos(df)


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
    df["T_amb_K"] = df["T_amb_K"] + 273.15  # °C → K
    df["presion_Pa"] = df["presion_Pa"] * 1000.0  # kPa → Pa
    df["HR"] = df["HR"] / 100.0  # % → fracción [0, 1]

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


# ---------------------------------------------------------------------------
# POA (Plane of Array) horaria — transposición de GHI/DNI/DHI al plano del colector
# ---------------------------------------------------------------------------


def calcular_POA_horizonte(
    datos_clima: pd.DataFrame,
    emplazamiento: Emplazamiento,
    *,
    modelo_difuso: str = "isotropic",
    tilt_deg: Optional[float] = None,
    acimut_duffie_deg: Optional[float] = None,
) -> pd.Series:
    """Calcula POA horaria sobre un plano orientado [W/m²].

    Aplica transposición de Liu-Jordan (componente directa: DNI·cos(θ_i);
    componente difusa: ``modelo_difuso``; componente reflejada del suelo:
    GHI·ρ_g·(1−cos β)/2) usando pvlib. El albedo ρ_g sale de
    ``emplazamiento.albedo_suelo`` (configurable en P3; default 0.25).

    Args:
        datos_clima: DataFrame horario con columnas ``GHI_Wm2``, ``DNI_Wm2``,
            ``DHI_Wm2`` y un índice DatetimeIndex tz-aware (típicamente el
            que produce ``obtener_clima``).
        emplazamiento: Emplazamiento del secador (lat, lon, alt; y tilt/acimut
            del colector si no se pasan explícitamente).
        modelo_difuso: Modelo de transposición difusa que acepta pvlib
            (``isotropic``, ``klucher``, ``haydavies``, ``reindl``, ``king``,
            ``perez``). Default ``isotropic`` por simplicidad y coherencia
            con P3.
        tilt_deg: Inclinación del plano [°]. ``None`` → usa
            ``emplazamiento.pendiente_colector_deg`` (comportamiento
            histórico: POA del colector).
        acimut_duffie_deg: Acimut del plano, convención Duffie. ``None`` →
            usa ``emplazamiento.acimut_colector_deg``.

    Returns:
        ``pd.Series`` POA horaria [W/m²], índice idéntico a ``datos_clima``.
        Valores negativos (artefacto numérico cerca del horizonte) se
        clipean a 0. Horas con DNI o DHI NaN reciben fallback a GHI (no se
        puede saber cuánto era directa vs difusa, así que se asume
        conservadoramente POA = GHI esa hora).

    Nota (mejora 38, F1a — POA medida): si ``datos_clima`` trae la columna
    ``POA_med_Wm2`` (irradiancia global medida con piranómetro EN el plano
    del colector) y la función se llama SIN overrides de ``tilt_deg`` /
    ``acimut_duffie_deg`` (= plano del colector), la medición manda: se
    devuelve ``POA_med_Wm2`` (clip ≥ 0) y la transposición solo rellena las
    horas donde la medida es NaN. Con overrides explícitos (p. ej. caras de
    la cámara radiativa) SIEMPRE se transpone — la medida vale solo para el
    plano en que se midió.

    Raises:
        ValueError: Si ``datos_clima`` no tiene las columnas esperadas o
            el índice no es DatetimeIndex tz-aware.
    """
    columnas_necesarias = {"GHI_Wm2", "DNI_Wm2", "DHI_Wm2"}
    faltantes = columnas_necesarias - set(datos_clima.columns)
    if faltantes:
        raise ValueError(f"CLIMA_COLUMNAS_POA_FALTANTES: faltan {faltantes} en datos_clima.")
    if not isinstance(datos_clima.index, pd.DatetimeIndex):
        raise ValueError("CLIMA_INDICE_NO_DATETIME: datos_clima.index debe ser DatetimeIndex.")
    if datos_clima.index.tz is None:
        raise ValueError(
            "CLIMA_INDICE_NAIVE: datos_clima.index debe ser tz-aware "
            "(timestamps localizados). pvlib.solarposition lo requiere."
        )

    usa_poa_medida = (
        tilt_deg is None and acimut_duffie_deg is None and COLUMNA_POA_MEDIDA in datos_clima.columns
    )

    sol_pos = pvlib.solarposition.get_solarposition(
        datos_clima.index,
        latitude=emplazamiento.latitud_deg,
        longitude=emplazamiento.longitud_deg,
        altitude=emplazamiento.altitud_m,
    )

    tilt = emplazamiento.pendiente_colector_deg if tilt_deg is None else tilt_deg
    acimut_duffie = (
        emplazamiento.acimut_colector_deg if acimut_duffie_deg is None else acimut_duffie_deg
    )
    acimut_pvlib = acimut_duffie_a_pvlib(acimut_duffie)

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=acimut_pvlib,
        solar_zenith=sol_pos["apparent_zenith"],
        solar_azimuth=sol_pos["azimuth"],
        dni=datos_clima["DNI_Wm2"],
        ghi=datos_clima["GHI_Wm2"],
        dhi=datos_clima["DHI_Wm2"],
        albedo=emplazamiento.albedo_suelo,
        model=modelo_difuso,
    )

    poa_global = poa["poa_global"].clip(lower=0.0)
    # Fallback hora-a-hora si DNI o DHI son NaN: usamos GHI como POA. Es
    # conservador (subestima POA en colectores con tilt > 0) pero evita
    # propagar NaN al solver del colector.
    mask_nan = poa_global.isna() | datos_clima["DNI_Wm2"].isna() | datos_clima["DHI_Wm2"].isna()
    if mask_nan.any():
        poa_global = poa_global.where(~mask_nan, datos_clima["GHI_Wm2"].clip(lower=0.0))

    if usa_poa_medida:
        # La medición manda donde existe; la transposición rellena sus NaN.
        poa_medida = datos_clima[COLUMNA_POA_MEDIDA].clip(lower=0.0)
        poa_global = poa_medida.where(poa_medida.notna(), poa_global)

    return poa_global.fillna(0.0)


# ---------------------------------------------------------------------------
# Día típico mensual (promedio horario sobre el mes)
# ---------------------------------------------------------------------------


def dia_tipo_mensual(
    datos_clima: pd.DataFrame,
    mes: int,
    tz_local: str = "UTC",
) -> pd.DataFrame:
    """Genera el día típico horario de un mes promediando NASA POWER.

    Para cada hora del día (h=0..23), promedia todos los registros del mes
    indicado. El resultado es un DataFrame de 24 filas que representa el
    "día medio" del mes, útil como forzante para simular un batch
    representativo en el motor termodinámico.

    Si ``tz_local`` se provee, los datos se convierten a esa zona antes de
    agrupar — así el pico solar cae cerca de la hora 12 local, no UTC.

    Args:
        datos_clima: DataFrame horario con índice DatetimeIndex tz-aware y
            las columnas SI estándar (``T_amb_K``, ``GHI_Wm2``, ``DNI_Wm2``,
            ``DHI_Wm2``, ``WS_ms``, ``HR``).
        mes: Mes calendario [1, 12].
        tz_local: Zona horaria local (string IANA). Default ``"UTC"`` no
            convierte. Para Argentina usar p.ej. ``"America/Argentina/Salta"``.

    Returns:
        DataFrame de 24 filas con las mismas columnas promediadas por hora
        del día, indexado por DatetimeIndex sintético del día 15 del mes
        del año del clima. Apto para alimentar ``calcular_POA_horizonte``.

    Raises:
        ValueError: Si ``mes`` no está en [1, 12] o no hay datos del mes
            en ``datos_clima``.
    """
    if not (1 <= mes <= 12):
        raise ValueError(f"DIA_TIPO_MES_INVALIDO: mes={mes} fuera de [1, 12].")

    df = datos_clima.copy()
    if tz_local != "UTC" and df.index.tz is not None:
        df.index = df.index.tz_convert(tz_local)

    df_mes = df[df.index.month == mes]
    if df_mes.empty:
        raise ValueError(
            f"DIA_TIPO_SIN_DATOS: no hay registros del mes {mes} en el clima provisto."
        )

    df_dia = df_mes.groupby(df_mes.index.hour).mean(numeric_only=True)
    df_dia = df_dia.reindex(range(24))
    if df_dia.isna().any().any():
        df_dia = df_dia.interpolate(limit_direction="both")

    anio = int(df_mes.index[0].year)
    timestamps = pd.date_range(
        start=f"{anio}-{mes:02d}-15 00:00",
        periods=24,
        freq="1h",
        tz=tz_local,
    )
    df_dia.index = timestamps
    return df_dia


def slice_n_dias_consecutivos(
    datos_local: pd.DataFrame,
    fecha_inicio: date,
    n_dias: int,
) -> tuple[pd.DataFrame, int, bool]:
    """Recorta N días calendario consecutivos del clima desde ``fecha_inicio``.

    Usado por el modo multi-día "días reales consecutivos": en vez de replicar
    el día de diseño, toma los N días siguientes del clima NASA. Si el rango
    excede el año disponible (cruza el 31-dic), trunca al último día disponible
    y lo marca con ``truncado=True`` — no se inventa empalme (decisión de diseño).

    Args:
        datos_local: DataFrame horario tz-aware ya en hora local y filtrado al
            año del clima (índice DatetimeIndex).
        fecha_inicio: Fecha del primer día del horizonte.
        n_dias: Número de días pedidos.

    Returns:
        Tupla ``(datos_slice, n_dias_efectivo, truncado)``:
        - ``datos_slice``: subconjunto de ``datos_local`` del rango recortado.
        - ``n_dias_efectivo``: días calendario distintos efectivamente incluidos.
        - ``truncado``: True si ``n_dias_efectivo < n_dias`` (se cruzó el borde
          del año).
    """
    fin_excl = fecha_inicio + timedelta(days=n_dias)
    fechas = datos_local.index.date
    mask = (fechas >= fecha_inicio) & (fechas < fin_excl)
    datos_slice = datos_local[mask]
    n_dias_efectivo = len(set(datos_slice.index.date))
    truncado = n_dias_efectivo < n_dias
    return datos_slice, n_dias_efectivo, truncado


def slice_clima_ventana(
    clima,
    inicio: date,
    fin: date,
) -> tuple[Optional[pd.DataFrame], str]:
    """Recorta ``clima.datos`` al lapso [inicio, fin] (mapeado al año del clima).

    Compartido por P2 (series del lapso), P3 (evaluación de colector sobre la
    ventana) y P7 (producción en modo VENTANA). El lapso se mapea por mes/día
    al año de la serie climática descargada; si los años no coinciden, el
    llamador es responsable de avisar al usuario (ver sincronización P1→P2).

    Args:
        clima: Objeto ``core.clima.Clima`` (o None).
        inicio, fin: Fechas de la ventana de producción.

    Returns:
        ``(df, msg)``: ``df`` es el slice horario (DatetimeIndex, COLUMNAS_SI)
        o ``None`` si no hay datos o el lapso no intersecta. ``msg`` describe
        el motivo cuando ``df is None``.
    """
    if clima is None or clima.datos is None or len(clima.datos) == 0:
        return None, "Sin datos de clima descargados (P2)."
    datos = clima.datos
    idx = datos.index
    anio = clima.anio or idx[0].year
    tz = idx.tz
    try:
        ini_ts = pd.Timestamp(year=anio, month=inicio.month, day=inicio.day, hour=0, tz=tz)
        fin_ts = pd.Timestamp(year=anio, month=fin.month, day=fin.day, hour=23, minute=59, tz=tz)
    except (ValueError, TypeError) as exc:
        return None, f"No se pudo construir el lapso: {exc}"
    df = datos.loc[(idx >= ini_ts) & (idx <= fin_ts)]
    if len(df) < 2:
        return None, (
            f"El lapso [{inicio} → {fin}] no intersecta los datos de clima "
            f"(año {anio}). Descargá el año correspondiente en P2."
        )
    return df, ""


def resolver_datos_trabajo(clima, paso_s: float) -> tuple[Optional[pd.DataFrame], list[str]]:
    """Entrega el DataFrame de clima al **paso de trabajo** (mejora 38, fase 1b).

    Único punto que traduce el contrato horario ``Clima.datos`` al paso temporal
    de la simulación transitoria (``Configuracion.paso_trabajo_s``). Estrategia
    por capas para preservar la procedencia:

    - ``paso_s == 3600`` → ``clima.datos`` tal cual (camino histórico, sin aviso).
    - ``paso_s < 3600`` → se interpola ``clima.datos`` horario al paso pedido como
      **baseline sintético** (cubre todas las columnas) y, para las columnas que
      existan en ``clima.datos_nativos`` a resolución suficiente
      (``frecuencia_nativa_s <= paso_s``), se **sobrescribe** con el remuestreo
      **real** de la serie nativa. Si alguna columna de trabajo quedó
      interpolada del horario, se agrega ``ADV_PASO_SINTETICO`` nombrando esas
      columnas (interpolar radiación horaria no repone los transitorios
      sub-horarios; ver ``docs/notas/plan_datos_medidos_1b.md``).

    Args:
        clima: Objeto ``core.clima.Clima`` (o None).
        paso_s: Paso de trabajo [s] (3600 / 900 / 300).

    Returns:
        ``(df, advertencias)``: ``df`` al paso de trabajo (o None si no hay
        datos); ``advertencias`` es una lista (posiblemente vacía) de códigos.
    """
    if clima is None or getattr(clima, "datos", None) is None or len(clima.datos) == 0:
        return None, []

    datos = clima.datos
    if paso_s >= 3600.0:
        return datos, []

    freq = f"{int(round(paso_s))}s"
    grilla = pd.date_range(datos.index[0], datos.index[-1], freq=freq)

    # Baseline sintético: interpolación temporal lineal de todas las columnas.
    base = datos.reindex(datos.index.union(grilla)).interpolate(method="time").reindex(grilla)

    columnas_reales: set[str] = set()
    nativos = getattr(clima, "datos_nativos", None)
    freq_nat = getattr(clima, "frecuencia_nativa_s", None)
    if nativos is not None and freq_nat is not None and float(freq_nat) <= paso_s:
        from calculos.clima_medido import remuestrear_a_paso

        convencion = "instantanea"
        mapeo = getattr(clima, "mapeo", None)
        if mapeo is not None:
            convencion = getattr(mapeo, "convencion_timestamp", "instantanea")
        remuestreado = remuestrear_a_paso(
            nativos,
            paso_nativo_s=float(freq_nat),
            paso_destino_s=paso_s,
            convencion=convencion,
        ).reindex(grilla)
        for col in remuestreado.columns:
            if col in base.columns:
                # Solo sobrescribir donde el nativo aporta dato real (no NaN).
                mask_real = remuestreado[col].notna()
                base.loc[mask_real, col] = remuestreado.loc[mask_real, col]
                if mask_real.any():
                    columnas_reales.add(col)

    advertencias: list[str] = []
    sinteticas = [c for c in datos.columns if c not in columnas_reales]
    if sinteticas:
        advertencias.append(
            "ADV_PASO_SINTETICO: paso de trabajo "
            f"{int(round(paso_s / 60.0))} min con columnas interpoladas del horario "
            f"({', '.join(sinteticas)}) — resolución sintética, sin transitorios "
            "sub-horarios reales."
        )
    return base, advertencias
