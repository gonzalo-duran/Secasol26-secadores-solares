"""
Pipeline de ingesta de datos climáticos medidos por el usuario (mejora 38, F1a).

Transforma un archivo tabular (CSV / Excel) con mediciones de campaña en un
objeto :class:`core.clima.Clima` con el MISMO contrato que el clima NASA POWER
(7 columnas ``COLUMNAS_SI``, índice horario UTC tz-aware, unidades SI), de modo
que todos los motores aguas abajo funcionen sin cambios.

Etapas del pipeline (orden de :func:`ingerir_clima_medido`):
    1. ``aplicar_mapeo``       — columnas del archivo → variables canónicas SI.
    2. ``inferir_frecuencia_s``— paso temporal nativo (ej. 600 s).
    3. ``regularizar_grilla``  — huecos de filas → filas NaN explícitas.
    4. ``qc_fisico``           — control de calidad físico con reporte.
    5. ``remuestrear_horario`` — media horaria (etiqueta = inicio de hora, UTC).
    6. ``derivar_dni_dhi_erbs``— descomposición GHI → DNI/DHI si faltan.
    7. ``completar_con_nasa``  — columnas ausentes desde NASA POWER.
    8. Política de huecos existente (``clima_calc.aplicar_politica_huecos``).

Cada columna del resultado queda etiquetada con su PROCEDENCIA_* (medida /
derivada / completada_nasa / default) para mostrarse al usuario antes de
confirmar. La serie al paso nativo se conserva en ``Clima.datos_nativos``
(reservada para la fase 1b, motor sub-horario).

Errores con prefijo ``CLIMED_``: ValueError para datos/configuración inválidos,
RuntimeError para fallas de entorno (p. ej. descarga NASA).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import pathlib
import re
import unicodedata
from dataclasses import asdict
from typing import Callable, Optional, Sequence

import numpy as np
import pandas as pd
import pvlib
import pyarrow as pa
import pyarrow.parquet as pq

from calculos.clima_calc import aplicar_politica_huecos, obtener_clima
from core.clima import ANIO_NASA_MAX, ANIO_NASA_MIN, COLUMNAS_SI, CalidadClima, Clima
from core.clima_medido import (
    COLUMNA_POA_MEDIDA,
    PROCEDENCIA_DERIVADA,
    PROCEDENCIA_MEDIDA,
    PROCEDENCIA_NASA,
    ChequeoQC,
    ConfigMapeoClima,
    MapeoColumna,
    ReporteQC,
)
from core.emplazamiento import Emplazamiento

# ---------------------------------------------------------------------------
# Constantes del pipeline
# ---------------------------------------------------------------------------

_EXTENSIONES_CSV = (".csv", ".txt")
_EXTENSIONES_EXCEL = {".xls": "xlrd", ".xlsx": "openpyxl"}

# Rango plausible de un serial de fecha Excel (1954-11-25 a 2118-12-31): si la
# columna de timestamp es numérica y cae acá, se interpreta como serial Excel.
_SERIAL_EXCEL_MIN = 20_000.0
_SERIAL_EXCEL_MAX = 80_000.0
_ORIGEN_SERIAL_EXCEL = "1899-12-30"

# Conversión de unidades de origen → SI (clave = unidad de core.clima_medido).
_A_SI: dict[str, Callable[[pd.Series], pd.Series]] = {
    "K": lambda s: s,
    "C": lambda s: s + 273.15,
    "F": lambda s: (s - 32.0) * 5.0 / 9.0 + 273.15,
    "W_m2": lambda s: s,
    "kW_m2": lambda s: s * 1000.0,
    "m_s": lambda s: s,
    "km_h": lambda s: s / 3.6,
    "Pa": lambda s: s,
    "kPa": lambda s: s * 1000.0,
    "hPa": lambda s: s * 100.0,
    "mbar": lambda s: s * 100.0,
    "atm": lambda s: s * 101_325.0,
    "fraccion": lambda s: s,
    "porcentaje": lambda s: s / 100.0,
}

# Perfil logarítmico neutro para normalizar el viento a 2 m (contrato Clima).
_Z_VIENTO_CONTRATO_M = 2.0
_Z0_RUGOSIDAD_M = 0.05

# Rangos físicos del QC: variable → (min, max). Fuera de rango → NaN.
_RANGOS_QC: dict[str, tuple[float, float]] = {
    "T_amb_K": (200.0, 335.0),
    "HR": (0.0, 1.02),  # tolerancia de sensor: (1, 1.02] se clipea a 1
    "GHI_Wm2": (-5.0, 1500.0),  # [-5, 0) se clipea a 0
    "DNI_Wm2": (-5.0, 1500.0),
    "DHI_Wm2": (-5.0, 1500.0),
    COLUMNA_POA_MEDIDA: (-5.0, 1500.0),
    "WS_ms": (0.0, 40.0),
    "presion_Pa": (50_000.0, 110_000.0),
}
_VARIABLES_IRRADIANCIA = ("GHI_Wm2", "DNI_Wm2", "DHI_Wm2", COLUMNA_POA_MEDIDA)

# Umbrales del QC solar
_ZENIT_NOCHE_DEG = 95.0
_GHI_NOCTURNA_UMBRAL_W_m2 = 20.0
_FACTOR_EXTRATERRESTRE = 1.2
_HORAS_SENSOR_CONGELADO = 3.0

# Fracción mínima de muestras válidas para que una hora remuestreada cuente.
_FRACCION_MINIMA_HORA = 0.5

# Fracción mínima de pasos que debe explicar la moda de los diffs para
# considerar la frecuencia "regular".
_FRACCION_MINIMA_MODA = 0.8

# ---------------------------------------------------------------------------
# Lectura de archivos
# ---------------------------------------------------------------------------


def _extension(nombre_archivo: str) -> str:
    nombre = nombre_archivo.lower().strip()
    for ext in list(_EXTENSIONES_EXCEL) + list(_EXTENSIONES_CSV):
        if nombre.endswith(ext):
            return ext
    raise ValueError(
        f"CLIMED_FORMATO_NO_SOPORTADO: '{nombre_archivo}' — formatos aceptados: "
        "CSV (.csv/.txt), Excel (.xls/.xlsx)."
    )


def listar_hojas(contenido: bytes, nombre_archivo: str) -> Optional[list[str]]:
    """Lista las hojas de un archivo Excel; None para CSV.

    Args:
        contenido: Bytes del archivo subido.
        nombre_archivo: Nombre original (decide el motor por extensión).

    Returns:
        Lista de nombres de hoja (Excel) o None (CSV).

    Raises:
        ValueError: ``CLIMED_FORMATO_NO_SOPORTADO`` si la extensión no se conoce.
        RuntimeError: ``CLIMED_LECTURA_FALLIDA`` si el archivo no puede abrirse.
    """
    ext = _extension(nombre_archivo)
    if ext in _EXTENSIONES_CSV:
        return None
    try:
        xf = pd.ExcelFile(io.BytesIO(contenido), engine=_EXTENSIONES_EXCEL[ext])
        return [str(h) for h in xf.sheet_names]
    except Exception as exc:  # xlrd/openpyxl lanzan tipos variados
        raise RuntimeError(
            f"CLIMED_LECTURA_FALLIDA: no se pudo abrir '{nombre_archivo}' ({exc})."
        ) from exc


def _leer_csv(contenido: bytes, fila_encabezado: int) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 nunca falla, defensivo
        raise RuntimeError("CLIMED_LECTURA_FALLIDA: codificación de texto no reconocida.")

    muestra = "\n".join(texto.splitlines()[fila_encabezado : fila_encabezado + 10])
    try:
        sep = csv.Sniffer().sniff(muestra, delimiters=",;\t").delimiter
    except csv.Error:
        sep = ","
    # Heurística regional: separador ';' suele venir con decimal ','.
    decimal = "," if sep == ";" else "."
    return pd.read_csv(
        io.StringIO(texto),
        sep=sep,
        decimal=decimal,
        header=fila_encabezado,
        skip_blank_lines=False,
    )


def leer_tabla(
    contenido: bytes,
    nombre_archivo: str,
    *,
    hoja: Optional[str] = None,
    fila_encabezado: int = 0,
) -> pd.DataFrame:
    """Lee el archivo del usuario a un DataFrame crudo (sin tipado ni limpieza).

    Args:
        contenido: Bytes del archivo subido.
        nombre_archivo: Nombre original (decide CSV vs Excel por extensión).
        hoja: Nombre de hoja (solo Excel; None = primera hoja).
        fila_encabezado: Índice 0-based de la fila de encabezados.

    Returns:
        DataFrame crudo con los nombres de columna del archivo.

    Raises:
        ValueError: ``CLIMED_FORMATO_NO_SOPORTADO`` / ``CLIMED_HOJA_INEXISTENTE``.
        RuntimeError: ``CLIMED_LECTURA_FALLIDA``.
    """
    ext = _extension(nombre_archivo)
    if ext in _EXTENSIONES_CSV:
        try:
            return _leer_csv(contenido, fila_encabezado)
        except (RuntimeError, ValueError):
            raise
        except Exception as exc:
            raise RuntimeError(
                f"CLIMED_LECTURA_FALLIDA: no se pudo leer '{nombre_archivo}' ({exc})."
            ) from exc
    try:
        return pd.read_excel(
            io.BytesIO(contenido),
            sheet_name=hoja if hoja is not None else 0,
            header=fila_encabezado,
            engine=_EXTENSIONES_EXCEL[ext],
        )
    except ValueError as exc:
        if "Worksheet" in str(exc):
            raise ValueError(
                f"CLIMED_HOJA_INEXISTENTE: la hoja '{hoja}' no existe en " f"'{nombre_archivo}'."
            ) from exc
        raise RuntimeError(
            f"CLIMED_LECTURA_FALLIDA: no se pudo leer '{nombre_archivo}' ({exc})."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"CLIMED_LECTURA_FALLIDA: no se pudo leer '{nombre_archivo}' ({exc})."
        ) from exc


# ---------------------------------------------------------------------------
# Sugerencia de mapeo
# ---------------------------------------------------------------------------


def _normalizar(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", str(texto))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return plano.lower().strip()


# Canales de proceso del secador (temperaturas/HR internas, señales crudas):
# NUNCA se sugieren como variables climáticas.
_RE_EXCLUSION = re.compile(
    r"quemador|chimenea|cano|caño|interc|prod|volt|flujo|salida|entrada|"
    r"camara|colector|record|step|placa|absorbedor|horno"
)

# Patrones de sugerencia por variable canónica (se aplican tras la exclusión).
_PATRONES_SUGERENCIA: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("T_amb_K", re.compile(r"(temp.*amb|t_?amb|amb.*temp)"), "C"),
    ("HR", re.compile(r"(hr|hum|rh)"), "porcentaje"),
    ("DNI_Wm2", re.compile(r"(dni|directa|beam)"), "W_m2"),
    ("DHI_Wm2", re.compile(r"(dhi|difusa|diffuse)"), "W_m2"),
    ("GHI_Wm2", re.compile(r"(radiac|ghi|global|pirano|solar)"), "W_m2"),
    ("WS_ms", re.compile(r"(viento|wind|veloc|\bws\b)"), "m_s"),
    ("presion_Pa", re.compile(r"(presion|press|barom)"), "hPa"),
)

_RE_TIMESTAMP = re.compile(r"(timestamp|tiempo|fecha|hora|date|time|\bdia\b|dia y hora)")


def sugerir_mapeo(columnas: Sequence[str]) -> ConfigMapeoClima:
    """Propone un mapeo inicial a partir de los nombres de columna del archivo.

    Heurística por regex, insensible a mayúsculas y acentos, con lista de
    exclusión de canales de proceso del secador (quemador, chimenea, caño,
    entrada/salida de cámara, etc.). La sugerencia es solo un punto de partida:
    el usuario la confirma o corrige en la UI.

    Args:
        columnas: Nombres de columna tal como vienen en el archivo.

    Returns:
        ConfigMapeoClima con el timestamp y las variables detectadas (las no
        detectadas simplemente no aparecen en ``columnas``).
    """
    nombres = [str(c) for c in columnas]
    normalizados = {c: _normalizar(c) for c in nombres}

    ts = next((c for c in nombres if _RE_TIMESTAMP.search(normalizados[c])), None)
    if ts is None:
        ts = nombres[0] if nombres else "timestamp"

    asignadas: set[str] = set()
    mapeos: list[MapeoColumna] = []
    for variable, patron, unidad in _PATRONES_SUGERENCIA:
        for c in nombres:
            if c == ts or variable in asignadas:
                continue
            norm = normalizados[c]
            if _RE_EXCLUSION.search(norm):
                continue
            if any(m.columna_origen == c for m in mapeos):
                continue
            if patron.search(norm):
                mapeos.append(MapeoColumna(variable, c, unidad))
                asignadas.add(variable)
                break

    return ConfigMapeoClima(columna_timestamp=ts, columnas=mapeos)


# ---------------------------------------------------------------------------
# Mapeo → serie SI al paso nativo
# ---------------------------------------------------------------------------


def _parsear_timestamps(serie: pd.Series, zona_horaria: str, fecha_fija=None) -> pd.DatetimeIndex:
    """Parsea una columna de timestamps a un DatetimeIndex UTC.

    Soporta serial de Excel, texto ("2010-05-01 09:00"), objetos ``datetime.time``
    y objetos datetime. Con ``fecha_fija`` (archivos que traen **solo la hora**,
    ej. "09:00:00" o ``datetime.time(9, 0)``) se toma la hora del día de cada
    registro y se combina con esa fecha.

    Raises:
        ValueError: ``CLIMED_TIMESTAMP_SOLO_HORA`` si la columna trae solo la hora y
            no se dio ``fecha_fija``; ``CLIMED_TIMESTAMP_INVALIDO`` si no se pudo
            interpretar ninguna fecha/hora; ``CLIMED_TZ_INVALIDA`` si la zona falla.
    """
    from datetime import datetime, time

    es_solo_hora = bool(serie.map(lambda v: isinstance(v, time)).any())

    if fecha_fija is not None:
        # Combinar la hora del día de cada registro con la fecha del ensayo.
        def _combinar(v):
            if isinstance(v, time):
                return datetime.combine(fecha_fija, v)
            ts = pd.to_datetime(v, dayfirst=True, errors="coerce")
            return pd.NaT if pd.isna(ts) else datetime.combine(fecha_fija, ts.time())

        tiempos = pd.to_datetime([_combinar(v) for v in serie], errors="coerce")
    elif es_solo_hora:
        raise ValueError(
            "CLIMED_TIMESTAMP_SOLO_HORA: la columna de timestamp trae solo la hora (sin "
            "fecha). Activá 'el archivo trae solo la hora' e indicá la fecha del ensayo."
        )
    else:
        numerica = pd.to_numeric(serie, errors="coerce")
        frac_num = float(numerica.notna().mean()) if len(numerica) else 0.0
        if frac_num > 0.9 and numerica.dropna().between(_SERIAL_EXCEL_MIN, _SERIAL_EXCEL_MAX).all():
            tiempos = pd.to_datetime(
                numerica, unit="D", origin=_ORIGEN_SERIAL_EXCEL, errors="coerce"
            ).dt.round("s")
        else:
            tiempos = pd.to_datetime(serie, dayfirst=True, errors="coerce", format="mixed")

    if pd.Series(tiempos).isna().all():
        raise ValueError(
            "CLIMED_TIMESTAMP_INVALIDO: no se pudo interpretar ninguna fecha/hora "
            "de la columna de timestamp."
        )
    try:
        idx = pd.DatetimeIndex(tiempos)
        if idx.tz is None:
            idx = idx.tz_localize(zona_horaria, ambiguous="NaT", nonexistent="NaT")
        return idx.tz_convert("UTC")
    except (ValueError, TypeError) as exc:
        if "zone" in str(exc).lower() or "tz" in str(exc).lower():
            raise ValueError(f"CLIMED_TZ_INVALIDA: '{zona_horaria}' ({exc}).") from exc
        raise ValueError(f"CLIMED_TIMESTAMP_INVALIDO: {exc}") from exc
    except Exception as exc:  # zoneinfo.ZoneInfoNotFoundError, pytz.UnknownTimeZoneError
        raise ValueError(f"CLIMED_TZ_INVALIDA: '{zona_horaria}' ({exc}).") from exc


def _a_numerico(serie: pd.Series, marcadores: tuple[str, ...]) -> pd.Series:
    limpios = {m.strip().lower() for m in marcadores}

    def _limpiar(v):
        if isinstance(v, str) and v.strip().lower() in limpios:
            return np.nan
        return v

    return pd.to_numeric(serie.map(_limpiar), errors="coerce")


def _viento_a_2m(v: pd.Series, altura_m: float) -> pd.Series:
    if abs(altura_m - _Z_VIENTO_CONTRATO_M) < 1e-9:
        return v
    factor = np.log(_Z_VIENTO_CONTRATO_M / _Z0_RUGOSIDAD_M) / np.log(altura_m / _Z0_RUGOSIDAD_M)
    return v * factor


def aplicar_mapeo(df_crudo: pd.DataFrame, config: ConfigMapeoClima) -> pd.DataFrame:
    """Aplica el mapeo declarativo: archivo crudo → DataFrame SI al paso nativo.

    Pasos: parseo de timestamps (serial Excel o texto) → tz del archivo → UTC;
    marcadores inválidos ('NAN', etc.) → NaN; conversión de unidades a SI;
    normalización del viento a 2 m; renombre a ``POA_med_Wm2`` si el
    piranómetro está en el plano del colector.

    Args:
        df_crudo: Salida de :func:`leer_tabla`.
        config: Configuración de mapeo validada.

    Returns:
        DataFrame con columnas canónicas SI, índice DatetimeIndex UTC ordenado y
        sin duplicados, al paso temporal del archivo.

    Raises:
        ValueError: ``CLIMED_COLUMNA_INEXISTENTE`` / ``CLIMED_SIN_VARIABLES`` /
            ``CLIMED_TIMESTAMP_INVALIDO`` / ``CLIMED_TZ_INVALIDA``.
    """
    if not config.columnas:
        raise ValueError("CLIMED_SIN_VARIABLES: el mapeo no incluye ninguna variable climática.")
    columnas_archivo = [str(c) for c in df_crudo.columns]
    requeridas = [config.columna_timestamp] + [m.columna_origen for m in config.columnas]
    for col in requeridas:
        if col not in columnas_archivo:
            raise ValueError(
                f"CLIMED_COLUMNA_INEXISTENTE: la columna '{col}' no está en el "
                f"archivo (disponibles: {', '.join(columnas_archivo[:20])})."
            )

    df = df_crudo.copy()
    df.columns = columnas_archivo
    idx = _parsear_timestamps(df[config.columna_timestamp], config.zona_horaria, config.fecha_fija)

    datos: dict[str, pd.Series] = {}
    for m in config.columnas:
        serie = _a_numerico(df[m.columna_origen], config.marcadores_invalidos)
        serie = _A_SI[m.unidad](serie)
        if m.variable == "WS_ms":
            serie = _viento_a_2m(serie, config.altura_anemometro_m)
        datos[m.variable] = serie

    resultado = pd.DataFrame(datos)
    resultado.index = idx
    resultado = resultado[~resultado.index.isna()]
    resultado = resultado.sort_index()
    resultado = resultado[~resultado.index.duplicated(keep="first")]

    # Red de seguridad: piranómetro coplanar declarado pero columna mapeada a GHI.
    if (
        config.plano_piranometro == "plano_colector"
        and "GHI_Wm2" in resultado.columns
        and COLUMNA_POA_MEDIDA not in resultado.columns
    ):
        resultado = resultado.rename(columns={"GHI_Wm2": COLUMNA_POA_MEDIDA})

    if len(resultado) == 0:
        raise ValueError("CLIMED_TIMESTAMP_INVALIDO: no quedó ninguna fila con timestamp válido.")
    return resultado


# ---------------------------------------------------------------------------
# Frecuencia y grilla
# ---------------------------------------------------------------------------


def inferir_frecuencia_s(idx: pd.DatetimeIndex) -> float:
    """Infiere el paso temporal nativo como la moda de los saltos del índice.

    Args:
        idx: Índice temporal ordenado (≥ 2 puntos).

    Returns:
        Paso temporal [s].

    Raises:
        ValueError: ``CLIMED_TIMESTAMP_INVALIDO`` con < 2 puntos;
            ``CLIMED_FRECUENCIA_IRREGULAR`` si la moda explica < 80 % de los
            saltos (archivo con cadencia mezclada).
    """
    if len(idx) < 2:
        raise ValueError(
            "CLIMED_TIMESTAMP_INVALIDO: se necesitan al menos 2 filas con "
            "timestamp válido para inferir la frecuencia."
        )
    # Aritmética de timedeltas: independiente de la resolución del índice
    # (pandas ≥ 3.0 puede dar datetime64[us] o [ns] según cómo se construyó).
    difs = np.diff(idx.to_numpy()) / np.timedelta64(1, "s")
    valores, cuentas = np.unique(difs, return_counts=True)
    moda = float(valores[np.argmax(cuentas)])
    fraccion = float(cuentas.max()) / float(len(difs))
    if fraccion < _FRACCION_MINIMA_MODA:
        raise ValueError(
            f"CLIMED_FRECUENCIA_IRREGULAR: el paso más común ({moda:.0f} s) solo "
            f"explica el {fraccion:.0%} de los saltos; el archivo mezcla cadencias."
        )
    if moda <= 0:
        raise ValueError("CLIMED_FRECUENCIA_IRREGULAR: paso temporal no positivo.")
    return moda


def regularizar_grilla(df: pd.DataFrame, paso_s: float) -> pd.DataFrame:
    """Reindexa a una grilla regular; los huecos de filas quedan como NaN.

    Args:
        df: Serie SI al paso nativo (índice UTC ordenado).
        paso_s: Paso temporal [s] (de :func:`inferir_frecuencia_s`).

    Returns:
        DataFrame reindexado sobre la grilla completa [primer, último] timestamp.
    """
    grilla = pd.date_range(df.index[0], df.index[-1], freq=f"{int(round(paso_s))}s")
    return df.reindex(grilla)


# ---------------------------------------------------------------------------
# QC físico
# ---------------------------------------------------------------------------


def _ejemplos(idx: pd.DatetimeIndex, mascara: np.ndarray, n: int = 5) -> list[str]:
    return [ts.isoformat() for ts in idx[mascara][:n]]


def qc_fisico(
    df_nativo: pd.DataFrame, *, lat: float, lon: float, alt_m: float
) -> tuple[pd.DataFrame, ReporteQC]:
    """Control de calidad físico sobre la serie al paso nativo.

    Chequeos y acciones:
        - ``rango_fisico``: valores fuera de rango físico → NaN (con clips
          benignos: irradiancia en [-5, 0) → 0; HR en (1, 1.02] → 1).
        - ``ghi_nocturna``: irradiancia global > 20 W/m² con cenit > 95° → 0.
        - ``ghi_extraterrestre``: GHI > 1.2·I0·cos(cenit) de día → NaN.
        - ``sensor_congelado``: ≥ 3 h de valor idéntico no nulo → solo aviso.

    Args:
        df_nativo: Serie SI regularizada al paso nativo.
        lat: Latitud del emplazamiento [°].
        lon: Longitud del emplazamiento [°].
        alt_m: Altitud del emplazamiento [m].

    Returns:
        ``(df_corregido, ReporteQC)``.

    Raises:
        ValueError: ``CLIMED_TODO_INVALIDO`` si una variable queda 100 % NaN
            tras el QC (columna muerta: sensor roto o unidad mal declarada).
    """
    df = df_nativo.copy()
    chequeos: list[ChequeoQC] = []
    idx = df.index

    # --- rangos físicos (con clips benignos) ---
    for col in df.columns:
        if col not in _RANGOS_QC:
            continue
        vmin, vmax = _RANGOS_QC[col]
        serie = df[col]
        marcados = 0
        if col in _VARIABLES_IRRADIANCIA:
            negativo_leve = (serie >= vmin) & (serie < 0.0)
            marcados += int(negativo_leve.sum())
            serie = serie.where(~negativo_leve, 0.0)
        if col == "HR":
            sobre_leve = (serie > 1.0) & (serie <= vmax)
            marcados += int(sobre_leve.sum())
            serie = serie.where(~sobre_leve, 1.0)
        fuera = (serie < vmin) | (serie > vmax)
        marcados += int(fuera.sum())
        mascara_fuera = fuera.fillna(False).to_numpy()
        serie = serie.where(~fuera)
        df[col] = serie
        if marcados:
            chequeos.append(
                ChequeoQC(
                    "rango_fisico", col, n_marcados=marcados, ejemplos=_ejemplos(idx, mascara_fuera)
                )
            )

    # --- chequeos solares (necesitan posición del sol al paso nativo) ---
    presentes_irr = [c for c in _VARIABLES_IRRADIANCIA if c in df.columns]
    if presentes_irr:
        solpos = pvlib.solarposition.get_solarposition(idx, lat, lon, altitude=alt_m)
        cenit = solpos["apparent_zenith"].to_numpy()

        for col in presentes_irr:
            nocturna = (cenit > _ZENIT_NOCHE_DEG) & (df[col].to_numpy() > _GHI_NOCTURNA_UMBRAL_W_m2)
            n_noct = int(np.nansum(nocturna))
            if n_noct:
                df.loc[nocturna, col] = 0.0
                chequeos.append(
                    ChequeoQC(
                        "ghi_nocturna", col, n_marcados=n_noct, ejemplos=_ejemplos(idx, nocturna)
                    )
                )

        if "GHI_Wm2" in df.columns:
            I0 = pvlib.irradiance.get_extra_radiation(idx).to_numpy()
            cos_cenit = np.cos(np.radians(cenit)).clip(min=0.0)
            limite = _FACTOR_EXTRATERRESTRE * I0 * cos_cenit
            excede = (cenit < 90.0) & (df["GHI_Wm2"].to_numpy() > limite)
            n_exc = int(np.nansum(excede))
            if n_exc:
                df.loc[excede, "GHI_Wm2"] = np.nan
                chequeos.append(
                    ChequeoQC(
                        "ghi_extraterrestre",
                        "GHI_Wm2",
                        n_marcados=n_exc,
                        ejemplos=_ejemplos(idx, excede),
                    )
                )

    # --- sensor congelado (solo aviso) ---
    paso_s = float((idx[1] - idx[0]) / pd.Timedelta(seconds=1)) if len(idx) > 1 else 3600.0
    n_congelado = max(int(round(_HORAS_SENSOR_CONGELADO * 3600.0 / paso_s)), 2)
    for col in df.columns:
        serie = df[col]
        mismo = serie.eq(serie.shift()) & serie.notna() & (serie != 0.0)
        rachas = mismo.groupby((~mismo).cumsum()).cumsum()
        n_avisos = int((rachas >= n_congelado).sum())
        if n_avisos:
            mascara = (rachas >= n_congelado).to_numpy()
            chequeos.append(
                ChequeoQC(
                    "sensor_congelado", col, n_avisos=n_avisos, ejemplos=_ejemplos(idx, mascara)
                )
            )

    # --- columna muerta ---
    for col in df.columns:
        if df[col].isna().all():
            raise ValueError(
                f"CLIMED_TODO_INVALIDO: la variable '{col}' quedó sin ningún valor "
                "válido tras el control de calidad (¿sensor roto o unidad mal "
                "declarada?). Corregí el mapeo o no mapees esa columna."
            )

    reporte = ReporteQC(chequeos=chequeos, n_filas_nativas=len(df))
    return df, reporte


# ---------------------------------------------------------------------------
# Remuestreo a horaria
# ---------------------------------------------------------------------------


def remuestrear_a_paso(
    df_nativo: pd.DataFrame,
    *,
    paso_nativo_s: float,
    paso_destino_s: float,
    convencion: str = "instantanea",
) -> pd.DataFrame:
    """Lleva la serie nativa al paso de trabajo (mejora 38, fase 1b).

    Dos regímenes según la relación entre pasos:

    - **Agregación** (``paso_destino_s >= paso_nativo_s``, caso normal): media
      por bin, etiqueta = inicio del bin, réplica de la convención NASA POWER
      (el valor etiquetado T representa la media de [T, T+paso) en UTC). Un bin
      con < 50 % de muestras válidas queda NaN (lo resuelve la política de
      huecos). El horario (``paso_destino_s == 3600``) es el caso de la fase 1a.
    - **Interpolación** (``paso_destino_s < paso_nativo_s``): la resolución
      pedida es más fina que la nativa → se interpola linealmente. No agrega
      información física (el llamador debe avisar *resolución sintética*); se
      ofrece para homogeneizar el paso de trabajo.

    Para archivos cuyo valor es promedio del intervalo (no lectura instantánea)
    el timestamp se corre medio paso nativo para centrar cada muestra.

    Args:
        df_nativo: Serie SI al paso nativo (post-QC).
        paso_nativo_s: Paso nativo [s].
        paso_destino_s: Paso de trabajo deseado [s].
        convencion: "instantanea" | "promedio_fin" | "promedio_inicio".

    Returns:
        DataFrame remuestreado al paso de trabajo.
    """
    df = df_nativo
    if convencion == "promedio_fin":
        df = df.copy()
        df.index = df.index - pd.Timedelta(seconds=paso_nativo_s / 2.0)
    elif convencion == "promedio_inicio":
        df = df.copy()
        df.index = df.index + pd.Timedelta(seconds=paso_nativo_s / 2.0)

    freq = f"{int(round(paso_destino_s))}s"

    if paso_destino_s < paso_nativo_s:
        # Upsampling: rejilla fina + interpolación temporal lineal.
        grilla = pd.date_range(df.index[0], df.index[-1], freq=freq)
        return df.reindex(df.index.union(grilla)).interpolate(method="time").reindex(grilla)

    agrupado = df.resample(freq, closed="left", label="left")
    medias = agrupado.mean()
    cuentas = agrupado.count()
    esperado = max(paso_destino_s / paso_nativo_s, 1.0)
    insuficiente = cuentas < (_FRACCION_MINIMA_HORA * esperado)
    return medias.where(~insuficiente)


def remuestrear_horario(
    df_nativo: pd.DataFrame,
    *,
    paso_nativo_s: float,
    convencion: str = "instantanea",
) -> pd.DataFrame:
    """Agrega la serie nativa a paso horario (wrapper de :func:`remuestrear_a_paso`).

    Camino de la fase 1a: contrato ``Clima.datos`` horario. Ver
    :func:`remuestrear_a_paso` para el detalle de la agregación.

    Args:
        df_nativo: Serie SI al paso nativo (post-QC).
        paso_nativo_s: Paso nativo [s].
        convencion: "instantanea" | "promedio_fin" | "promedio_inicio".

    Returns:
        DataFrame horario; una hora con < 50 % de muestras válidas queda NaN.
    """
    return remuestrear_a_paso(
        df_nativo,
        paso_nativo_s=paso_nativo_s,
        paso_destino_s=3600.0,
        convencion=convencion,
    )


# ---------------------------------------------------------------------------
# Derivación y completado
# ---------------------------------------------------------------------------


def derivar_dni_dhi_erbs(
    df_horario: pd.DataFrame, *, lat: float, lon: float, alt_m: float
) -> tuple[pd.DataFrame, list[str]]:
    """Deriva DNI/DHI desde GHI (correlación de Erbs) si faltan componentes.

    Args:
        df_horario: Serie horaria SI (debe incluir ``GHI_Wm2`` para derivar).
        lat: Latitud [°]. lon: Longitud [°]. alt_m: Altitud [m].

    Returns:
        ``(df, columnas_derivadas)`` — solo se agregan las que faltaban.
    """
    faltan = [c for c in ("DNI_Wm2", "DHI_Wm2") if c not in df_horario.columns]
    if not faltan or "GHI_Wm2" not in df_horario.columns:
        return df_horario, []

    df = df_horario.copy()
    solpos = pvlib.solarposition.get_solarposition(df.index, lat, lon, altitude=alt_m)
    descomp = pvlib.irradiance.erbs(df["GHI_Wm2"], solpos["apparent_zenith"], df.index)
    for col, clave in (("DNI_Wm2", "dni"), ("DHI_Wm2", "dhi")):
        if col in faltan:
            df[col] = pd.Series(descomp[clave], index=df.index).clip(lower=0.0)
    return df, faltan


def completar_con_nasa(
    df_horario: pd.DataFrame,
    emplazamiento: Emplazamiento,
    anio: int,
    *,
    obtener_clima_fn: Optional[Callable[..., Clima]] = None,
) -> tuple[pd.DataFrame, dict[str, str], Optional[float]]:
    """Completa las columnas de COLUMNAS_SI ausentes con NASA POWER.

    Args:
        df_horario: Serie horaria SI del archivo medido (columnas parciales).
        emplazamiento: Da lat/lon para la descarga (reusa la cache parquet).
        anio: Año calendario de la campaña.
        obtener_clima_fn: Inyectable para tests; default
            :func:`calculos.clima_calc.obtener_clima`.

    Returns:
        ``(df_completo, procedencia_parcial, altitud_nasa_m)`` — el df queda en
        orden COLUMNAS_SI (+ ``POA_med_Wm2`` al final si existe);
        ``procedencia_parcial`` solo trae las columnas completadas;
        ``altitud_nasa_m`` es None si no hizo falta completar nada.

    Raises:
        ValueError: ``CLIMED_ANIO_FUERA_NASA`` si el año de la campaña está
            fuera del rango descargable.
        RuntimeError: ``CLIMED_COMPLETADO_FALLIDO`` si la descarga NASA falla.
    """
    faltantes = [c for c in COLUMNAS_SI if c not in df_horario.columns]
    extras = [c for c in df_horario.columns if c not in COLUMNAS_SI]
    if not faltantes:
        orden = [c for c in COLUMNAS_SI] + extras
        return df_horario[orden], {}, None

    if not (ANIO_NASA_MIN <= anio <= ANIO_NASA_MAX):
        raise ValueError(
            f"CLIMED_ANIO_FUERA_NASA: la campaña es del año {anio}, fuera del "
            f"rango NASA POWER [{ANIO_NASA_MIN}, {ANIO_NASA_MAX}] necesario para "
            f"completar las variables no medidas ({', '.join(faltantes)})."
        )

    fn = obtener_clima_fn if obtener_clima_fn is not None else obtener_clima
    try:
        clima_nasa = fn(emplazamiento, anio)
    except RuntimeError as exc:
        raise RuntimeError(
            f"CLIMED_COMPLETADO_FALLIDO: no se pudo obtener NASA POWER {anio} "
            f"para completar {', '.join(faltantes)} ({exc})."
        ) from exc

    df = df_horario.copy()
    procedencia: dict[str, str] = {}
    for col in faltantes:
        df[col] = clima_nasa.datos[col].reindex(df.index)
        procedencia[col] = PROCEDENCIA_NASA

    orden = [c for c in COLUMNAS_SI] + extras
    return df[orden], procedencia, clima_nasa.altitud_nasa_m


# ---------------------------------------------------------------------------
# Cobertura mensual (base del gating de ANUAL)
# ---------------------------------------------------------------------------


def meses_cubiertos(
    datos: pd.DataFrame, tz_local: str = "UTC", *, min_horas_mes: int = 24
) -> tuple[int, ...]:
    """Meses calendario (1-12) con cobertura mínima de datos válidos.

    Un mes cuenta si tiene al menos ``min_horas_mes`` filas con ``T_amb_K`` y
    ``GHI_Wm2`` simultáneamente no-NaN (las dos variables imprescindibles de
    cualquier análisis).

    Args:
        datos: DataFrame horario con columnas COLUMNAS_SI.
        tz_local: Zona horaria para asignar cada hora a su mes local.
        min_horas_mes: Umbral de horas válidas por mes.

    Returns:
        Tupla ordenada de meses cubiertos.
    """
    if datos is None or len(datos) == 0:
        return ()
    idx_local = datos.index.tz_convert(tz_local)
    validas = datos["T_amb_K"].notna() & datos["GHI_Wm2"].notna()
    conteo = validas.groupby(idx_local.month).sum()
    return tuple(int(m) for m in sorted(conteo[conteo >= min_horas_mes].index))


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def ingerir_clima_medido(
    df_crudo: pd.DataFrame,
    config: ConfigMapeoClima,
    emplazamiento: Emplazamiento,
    *,
    obtener_clima_fn: Optional[Callable[..., Clima]] = None,
) -> Clima:
    """Pipeline completo: archivo crudo mapeado → objeto Clima con contrato NASA.

    Ver el docstring del módulo para el orden de etapas. La serie al paso
    nativo (post-QC, pre-remuestreo) queda en ``Clima.datos_nativos`` para la
    fase 1b.

    Args:
        df_crudo: Salida de :func:`leer_tabla`.
        config: Mapeo declarativo confirmado por el usuario.
        emplazamiento: Emplazamiento del proyecto (lat/lon/altitud para QC
            solar, Erbs y completado NASA).
        obtener_clima_fn: Inyectable para tests (default: descarga real con
            cache parquet).

    Returns:
        Clima con ``fuente`` "medido" (todo medido/derivado) o "hibrido"
        (hubo columnas completadas con NASA), procedencia por columna, QC y
        política de huecos aplicada.

    Raises:
        ValueError / RuntimeError: códigos ``CLIMED_*`` de las etapas.
    """
    lat = emplazamiento.latitud_deg
    lon = emplazamiento.longitud_deg
    alt = emplazamiento.altitud_m

    df_nativo = aplicar_mapeo(df_crudo, config)
    paso_s = inferir_frecuencia_s(df_nativo.index)
    df_nativo = regularizar_grilla(df_nativo, paso_s)
    df_nativo, reporte = qc_fisico(df_nativo, lat=lat, lon=lon, alt_m=alt)

    anios = df_nativo.index.tz_convert(config.zona_horaria).year.unique()
    if len(anios) > 1:
        raise ValueError(
            f"CLIMED_PERIODO_MULTIANIO: la campaña cruza el 31 de diciembre "
            f"(años {', '.join(str(a) for a in sorted(anios))}); en esta versión "
            "cada archivo debe caer dentro de un único año calendario."
        )
    anio = int(anios[0])

    df_h = remuestrear_horario(
        df_nativo, paso_nativo_s=paso_s, convencion=config.convencion_timestamp
    )
    df_h, derivadas = derivar_dni_dhi_erbs(df_h, lat=lat, lon=lon, alt_m=alt)

    procedencia: dict[str, str] = {}
    for variable in df_nativo.columns:
        procedencia[variable] = PROCEDENCIA_MEDIDA
    for variable in derivadas:
        procedencia[variable] = PROCEDENCIA_DERIVADA

    df_h, proc_nasa, altitud_nasa = completar_con_nasa(
        df_h, emplazamiento, anio, obtener_clima_fn=obtener_clima_fn
    )
    procedencia.update(proc_nasa)

    df_h, calidad = aplicar_politica_huecos(df_h)

    fuente = "hibrido" if any(p == PROCEDENCIA_NASA for p in procedencia.values()) else "medido"

    idx_local = df_nativo.index.tz_convert(config.zona_horaria)
    reporte.frecuencia_nativa_s = paso_s
    reporte.periodo_inicio = idx_local[0].isoformat()
    reporte.periodo_fin = idx_local[-1].isoformat()
    reporte.meses_cubiertos = meses_cubiertos(df_h, config.zona_horaria)

    return Clima(
        datos=df_h,
        anio=anio,
        calidad=calidad,
        altitud_nasa_m=altitud_nasa,
        fuente=fuente,
        procedencia=procedencia,
        frecuencia_nativa_s=paso_s,
        datos_nativos=df_nativo,
        mapeo=config,
        qc=reporte,
    )


# ---------------------------------------------------------------------------
# Cache parquet y serialización del mapeo (E6)
# ---------------------------------------------------------------------------

_RAIZ = pathlib.Path(__file__).parent.parent
_DIR_CACHE_MEDIDO = _RAIZ / "data" / "cache" / "clima_medido"
_META_CLIMA_MEDIDO_KEY: bytes = b"clima_medido_meta"


def hash_archivo(contenido: bytes) -> str:
    """SHA-256 hexadecimal del contenido crudo del archivo subido."""
    return hashlib.sha256(contenido).hexdigest()


def config_a_dict(config: ConfigMapeoClima) -> dict:
    """Serializa la configuración de mapeo a un dict JSON-compatible."""
    d = asdict(config)
    # fecha_fija (date) → isoformat para que sea JSON-serializable (hash/snapshot).
    if d.get("fecha_fija") is not None and not isinstance(d["fecha_fija"], str):
        d["fecha_fija"] = d["fecha_fija"].isoformat()
    return d


def config_desde_dict(d: dict) -> ConfigMapeoClima:
    """Reconstruye una ConfigMapeoClima desde el dict de :func:`config_a_dict`.

    Tolera listas donde el dataclass usa tuplas (round-trip JSON).

    Raises:
        ValueError: códigos ``CLIMED_CONFIG_*`` si el dict trae valores
            inválidos (mismas validaciones que el constructor).
    """
    from datetime import date as _date

    datos = dict(d)
    columnas = [
        m if isinstance(m, MapeoColumna) else MapeoColumna(**m) for m in datos.get("columnas", [])
    ]
    datos["columnas"] = columnas
    if "marcadores_invalidos" in datos and datos["marcadores_invalidos"] is not None:
        datos["marcadores_invalidos"] = tuple(datos["marcadores_invalidos"])
    if isinstance(datos.get("fecha_fija"), str):
        datos["fecha_fija"] = _date.fromisoformat(datos["fecha_fija"])
    return ConfigMapeoClima(**datos)


def hash_ingesta(hash_arch: str, config: ConfigMapeoClima) -> str:
    """Identificador único de (archivo, mapeo): mismo archivo con otro mapeo
    produce otro Clima y por lo tanto otra entrada de cache."""
    clave = {"archivo": hash_arch, "config": config_a_dict(config)}
    return hashlib.sha256(json.dumps(clave, sort_keys=True).encode()).hexdigest()


def _rutas_cache_medido(
    hash_ing: str, dir_cache: Optional[pathlib.Path] = None
) -> tuple[pathlib.Path, pathlib.Path]:
    base = dir_cache if dir_cache is not None else _DIR_CACHE_MEDIDO
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{hash_ing}.parquet", base / f"{hash_ing}_nativo.parquet"


def guardar_cache_medido(
    clima: Clima, hash_ing: str, *, dir_cache: Optional[pathlib.Path] = None
) -> pathlib.Path:
    """Persiste el Clima medido en cache parquet (horario + nativo + metadatos).

    Los metadatos (fuente, año, procedencia, mapeo, QC, calidad, frecuencia,
    altitud NASA) van embebidos como JSON en el schema del parquet horario —
    mismo patrón que la cache NASA de ``clima_calc``.

    Args:
        clima: Clima producido por :func:`ingerir_clima_medido`.
        hash_ing: Clave de :func:`hash_ingesta`.
        dir_cache: Directorio alternativo (tests).

    Returns:
        Ruta del parquet horario escrito.
    """
    ruta_horario, ruta_nativo = _rutas_cache_medido(hash_ing, dir_cache)
    meta = {
        "fuente": clima.fuente,
        "anio": clima.anio,
        "procedencia": clima.procedencia,
        "frecuencia_nativa_s": clima.frecuencia_nativa_s,
        "altitud_nasa_m": clima.altitud_nasa_m,
        "mapeo": config_a_dict(clima.mapeo) if clima.mapeo is not None else None,
        "qc": asdict(clima.qc) if clima.qc is not None else None,
        "calidad": asdict(clima.calidad),
    }
    tabla = pa.Table.from_pandas(clima.datos)
    meta_parquet: dict[bytes, bytes] = dict(tabla.schema.metadata or {})
    meta_parquet[_META_CLIMA_MEDIDO_KEY] = json.dumps(meta).encode()
    tabla = tabla.replace_schema_metadata(meta_parquet)
    pq.write_table(tabla, str(ruta_horario))

    if clima.datos_nativos is not None:
        pq.write_table(pa.Table.from_pandas(clima.datos_nativos), str(ruta_nativo))
    return ruta_horario


def cargar_cache_medido(
    hash_ing: str, *, dir_cache: Optional[pathlib.Path] = None
) -> Optional[Clima]:
    """Restaura un Clima medido desde la cache; None si no existe la entrada."""
    ruta_horario, ruta_nativo = _rutas_cache_medido(hash_ing, dir_cache)
    if not ruta_horario.exists():
        return None
    tabla = pq.read_table(str(ruta_horario))
    df = tabla.to_pandas()
    meta_raw = (tabla.schema.metadata or {}).get(_META_CLIMA_MEDIDO_KEY)
    meta = json.loads(meta_raw) if meta_raw else {}

    qc = None
    if meta.get("qc") is not None:
        d_qc = dict(meta["qc"])
        d_qc["chequeos"] = [ChequeoQC(**c) for c in d_qc.get("chequeos", [])]
        d_qc["meses_cubiertos"] = tuple(d_qc.get("meses_cubiertos", ()))
        qc = ReporteQC(**d_qc)

    datos_nativos = None
    if ruta_nativo.exists():
        datos_nativos = pq.read_table(str(ruta_nativo)).to_pandas()

    return Clima(
        datos=df,
        anio=meta.get("anio"),
        calidad=CalidadClima(**meta.get("calidad", {})),
        altitud_nasa_m=meta.get("altitud_nasa_m"),
        fuente=meta.get("fuente", "medido"),
        procedencia=meta.get("procedencia"),
        frecuencia_nativa_s=meta.get("frecuencia_nativa_s"),
        datos_nativos=datos_nativos,
        mapeo=config_desde_dict(meta["mapeo"]) if meta.get("mapeo") else None,
        qc=qc,
    )
