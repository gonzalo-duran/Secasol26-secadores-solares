"""Ingesta de la señal de referencia medida (mejora 38, fase 2).

Parsea el archivo de validación del usuario (CSV/.xls/.xlsx) y produce una
`SenalReferencia` en SI, reusando la maquinaria de lectura y parseo de
`clima_medido` (fase 1a): lectura de tablas, timestamps serial-Excel/texto,
limpieza de marcadores, inferencia de frecuencia y regularización de grilla.

Errores con prefijo ``VREF_``. Convención de unidades: la señal se guarda en SI
(K para temperatura). La lectura de hojas/tablas la hace la UI directamente con
`clima_medido.listar_hojas`/`leer_tabla`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from calculos.clima_medido import (
    _a_numerico,
    _parsear_timestamps,
    inferir_frecuencia_s,
    regularizar_grilla,
)
from core.validacion import ConfigReferencia, SenalReferencia

# Rango físico plausible de una temperatura de flujo del secador [K]
# (−20 °C a 150 °C): fuera de esto la muestra se anula por QC.
_T_MIN_PLAUSIBLE_K: float = 253.15
_T_MAX_PLAUSIBLE_K: float = 423.15


def _parsear_timestamps_ref(serie: pd.Series, zona_horaria: str, fecha_fija) -> pd.DatetimeIndex:
    """Parsea timestamps de la referencia, soportando **fecha fija** (fase 2b).

    Con ``fecha_fija`` (para archivos cuya columna trae solo la hora, ej.
    "09:00:00"): se toma la **hora del día** de cada registro y se combina con
    ``fecha_fija``, luego se localiza en ``zona_horaria`` y se pasa a UTC. Sin
    ``fecha_fija`` delega en el parser de clima_medido (serial Excel o texto).

    Maneja tanto valores de texto ("09:00:00") como objetos ``datetime.time``
    (cómo ``pd.read_excel`` suele leer una columna de solo-hora de un ``.xls``).

    Args:
        serie: Columna cruda de timestamps.
        zona_horaria: Zona horaria del archivo.
        fecha_fija: ``datetime.date`` o None.

    Returns:
        DatetimeIndex UTC (con NaT donde no se pudo parsear).
    """
    return _parsear_timestamps(serie, zona_horaria, fecha_fija)


def _a_kelvin(valores: pd.Series, unidad: str) -> pd.Series:
    """Convierte una serie de temperatura a K según la unidad de origen.

    Args:
        valores: Serie numérica de temperatura.
        unidad: "C" | "K" | "F".

    Returns:
        Serie en K.

    Raises:
        ValueError: ``VREF_UNIDAD_NO_SOPORTADA`` si la unidad no se reconoce.
    """
    if unidad == "K":
        return valores
    if unidad == "C":
        return valores + 273.15
    if unidad == "F":
        return (valores - 32.0) * 5.0 / 9.0 + 273.15
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de temperatura '{unidad}' desconocida.")


def ingerir_referencia(df_crudo: pd.DataFrame, config: ConfigReferencia) -> SenalReferencia:
    """Ingiere el archivo de referencia → `SenalReferencia` en SI al paso nativo.

    Pasos: timestamp (serial Excel o texto) → tz del archivo → UTC; limpieza de
    marcadores → numérico; conversión a SI (K); QC de rango físico (fuera de rango
    → NaN); inferencia de frecuencia + regularización de grilla.

    Args:
        df_crudo: Tabla cruda leída del archivo (con encabezado ya resuelto).
        config: Configuración de mapeo de la referencia.

    Returns:
        `SenalReferencia` en SI (K), índice UTC ordenado y regular.

    Raises:
        ValueError: ``VREF_COLUMNA_TIMESTAMP_AUSENTE`` / ``VREF_COLUMNA_VALOR_AUSENTE``
            si faltan columnas; ``VREF_TODO_INVALIDO`` si no queda ningún dato válido;
            (propaga ``CLIMED_*`` del parseo de timestamps y frecuencia).
    """
    if config.columna_timestamp not in df_crudo.columns:
        raise ValueError(
            f"VREF_COLUMNA_TIMESTAMP_AUSENTE: '{config.columna_timestamp}' no está en el archivo."
        )
    if config.columna_valor not in df_crudo.columns:
        raise ValueError(
            f"VREF_COLUMNA_VALOR_AUSENTE: '{config.columna_valor}' no está en el archivo."
        )

    idx = _parsear_timestamps_ref(
        df_crudo[config.columna_timestamp], config.zona_horaria, config.fecha_fija
    )
    valores = _a_numerico(df_crudo[config.columna_valor], config.marcadores_invalidos)
    valores.index = idx

    # Descartar timestamps no parseables (NaT), ordenar, deduplicar.
    valores = valores[~valores.index.isna()]
    valores = valores[~valores.index.duplicated(keep="first")].sort_index()
    if len(valores) == 0:
        raise ValueError("VREF_TODO_INVALIDO: no quedó ninguna muestra con timestamp válido.")

    # Conversión a SI (K).
    serie_si = _a_kelvin(valores.astype(float), config.unidad)

    # QC de rango físico: fuera de plausible → NaN.
    n_validos_pre = int(serie_si.notna().sum())
    fuera = (serie_si < _T_MIN_PLAUSIBLE_K) | (serie_si > _T_MAX_PLAUSIBLE_K)
    serie_si = serie_si.mask(fuera)
    n_invalidos = int(serie_si.isna().sum())

    advertencias: list[str] = []
    n_fuera = int(fuera.sum())
    if n_fuera > 0:
        advertencias.append(
            f"VREF_QC_FUERA_DE_RANGO: {n_fuera} muestras fuera de "
            f"[{_T_MIN_PLAUSIBLE_K - 273.15:.0f}, {_T_MAX_PLAUSIBLE_K - 273.15:.0f}] °C anuladas."
        )
    if serie_si.notna().sum() == 0:
        raise ValueError(
            "VREF_TODO_INVALIDO: ninguna muestra de la señal es un valor físico válido."
        )

    # Frecuencia nativa + regularización de grilla.
    paso_s = inferir_frecuencia_s(serie_si.index)
    df_reg = regularizar_grilla(serie_si.to_frame(name=config.variable), paso_s)
    serie_reg = df_reg[config.variable]

    _ = n_validos_pre  # (trazabilidad; el conteo relevante es n_invalidos)
    return SenalReferencia(
        variable=config.variable,
        serie=serie_reg,
        unidad_origen=config.unidad,
        frecuencia_nativa_s=float(paso_s),
        n_invalidos=n_invalidos,
        advertencias=advertencias,
    )


def _a_poa_Wm2(valores: pd.Series, unidad: str) -> pd.Series:
    """Convierte irradiancia a W/m² (``W_m2`` o ``kW_m2``)."""
    if unidad == "W_m2":
        return valores
    if unidad == "kW_m2":
        return valores * 1000.0
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de irradiancia '{unidad}' desconocida.")


def _a_viento_ms(valores: pd.Series, unidad: str) -> pd.Series:
    """Convierte velocidad de viento a m/s (``m_s`` o ``km_h``)."""
    if unidad == "m_s":
        return valores
    if unidad == "km_h":
        return valores / 3.6
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de viento '{unidad}' desconocida.")


def ingerir_clima_forzante(
    df_crudo: pd.DataFrame,
    config: ConfigReferencia,
    *,
    columna_T_amb: str,
    unidad_T_amb: str = "C",
    columna_POA: str,
    unidad_POA: str = "W_m2",
    columna_viento: str | None = None,
    unidad_viento: str = "m_s",
) -> pd.DataFrame:
    """Construye un df de **forzado del colector** desde el clima medido del archivo (fase 2b).

    Permite validar el colector **aislado** forzándolo con la temperatura ambiente
    y la irradiancia **del propio ensayo** (no con el clima horario de P2, que no
    ve las nubes del día). Reusa el timestamp de ``config`` (incl. ``fecha_fija``).

    Args:
        df_crudo: Tabla cruda del archivo de referencia.
        config: Config de la referencia (aporta timestamp, tz, convención, fecha_fija).
        columna_T_amb / unidad_T_amb: Columna y unidad de temperatura ambiente (C/K/F).
        columna_POA / unidad_POA: Columna y unidad de irradiancia en plano (W_m2/kW_m2).
        columna_viento / unidad_viento: Columna y unidad de viento (opcional; None → 2 m/s).

    Returns:
        DataFrame UTC regular con columnas ``T_amb_K``, ``WS_ms``, ``POA_med_Wm2``,
        ``GHI_Wm2``, ``DNI_Wm2``, ``DHI_Wm2`` (POA medida directa; ``calcular_POA_horizonte``
        la usa sin transponer).

    Raises:
        ValueError: ``VREF_COLUMNA_*_AUSENTE`` si faltan columnas; ``VREF_CLIMA_VACIO``
            si no queda ningún registro válido.
    """
    for col, code in ((columna_T_amb, "TAMB"), (columna_POA, "POA")):
        if col not in df_crudo.columns:
            raise ValueError(f"VREF_COLUMNA_{code}_AUSENTE: '{col}' no está en el archivo.")

    idx = _parsear_timestamps_ref(
        df_crudo[config.columna_timestamp], config.zona_horaria, config.fecha_fija
    )
    T_amb_K = _a_kelvin(
        _a_numerico(df_crudo[columna_T_amb], config.marcadores_invalidos), unidad_T_amb
    )
    poa = _a_poa_Wm2(
        _a_numerico(df_crudo[columna_POA], config.marcadores_invalidos), unidad_POA
    ).clip(lower=0.0)

    if columna_viento is not None and columna_viento in df_crudo.columns:
        viento = _a_viento_ms(
            _a_numerico(df_crudo[columna_viento], config.marcadores_invalidos), unidad_viento
        ).clip(lower=0.0)
    else:
        viento = pd.Series(2.0, index=df_crudo.index)

    df = pd.DataFrame(
        {
            "T_amb_K": T_amb_K.to_numpy(dtype=float),
            "WS_ms": viento.to_numpy(dtype=float),
            "POA_med_Wm2": poa.to_numpy(dtype=float),
        },
        index=idx,
    )
    df = df[~df.index.isna()]
    df = df[~df.index.duplicated(keep="first")].sort_index()
    if len(df) == 0:
        raise ValueError("VREF_CLIMA_VACIO: no quedó ningún registro de clima válido.")

    paso_s = inferir_frecuencia_s(df.index)
    df = regularizar_grilla(df, paso_s)
    # POA/T_amb completas (interpolación de huecos cortos de la grilla regular).
    df = df.interpolate(method="time").ffill().bfill()
    # calcular_POA_horizonte usa POA_med si está; GHI de respaldo, DNI/DHI ausentes.
    df["GHI_Wm2"] = df["POA_med_Wm2"]
    df["DNI_Wm2"] = np.nan
    df["DHI_Wm2"] = np.nan
    return df


def alinear_con_simulada(
    senal: SenalReferencia,
    t_sim: pd.DatetimeIndex,
    y_sim: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Alinea la señal medida con una serie simulada (interpola la simulada).

    La serie simulada se interpola linealmente en el tiempo a los timestamps de la
    señal medida que caen dentro del rango simulado; se descartan los instantes sin
    dato válido en ambas.

    Args:
        senal: Señal de referencia medida (SI, índice UTC).
        t_sim: Timestamps de la serie simulada (DatetimeIndex tz-aware UTC).
        y_sim: Valores simulados (misma longitud que ``t_sim``, SI).

    Returns:
        ``(y_med, y_sim_alineada, timestamps)`` — arrays alineados (mismos
        instantes) y los timestamps correspondientes. Puede quedar vacío si no hay
        solape temporal.

    Raises:
        ValueError: ``VREF_SIM_VACIA`` si la serie simulada no tiene puntos válidos.
    """
    t_sim = pd.DatetimeIndex(t_sim)
    y_sim = np.asarray(y_sim, dtype=float)
    if t_sim.tz is None:
        t_sim = t_sim.tz_localize("UTC")
    else:
        t_sim = t_sim.tz_convert("UTC")

    sim = pd.Series(y_sim, index=t_sim).dropna().sort_index()
    if len(sim) == 0:
        raise ValueError("VREF_SIM_VACIA: la serie simulada no tiene puntos válidos.")

    med = senal.serie.dropna()
    # Restringir a los instantes medidos dentro del rango simulado.
    en_rango = (med.index >= sim.index[0]) & (med.index <= sim.index[-1])
    med = med[en_rango]
    if len(med) == 0:
        return np.array([]), np.array([]), pd.DatetimeIndex([], tz="UTC")

    # Interpolar la simulada a los timestamps medidos (unión + interpolación temporal).
    union = sim.index.union(med.index)
    sim_interp = sim.reindex(union).interpolate(method="time").reindex(med.index)

    y_med = med.to_numpy(dtype=float)
    y_sim_al = sim_interp.to_numpy(dtype=float)
    return y_med, y_sim_al, med.index


def evaluar_ajuste(
    senal: SenalReferencia,
    t_sim: pd.DatetimeIndex,
    y_sim: np.ndarray,
):
    """Alinea medido↔simulado y calcula las métricas de ajuste (fase 2, E3).

    Compone :func:`alinear_con_simulada` + ``metricas_validacion.calcular_metricas``.
    Es el nexo entre la simulación del colector (capa UI) y las métricas puras.

    Args:
        senal: Señal de referencia medida (SI).
        t_sim: Timestamps de la serie simulada.
        y_sim: Valores simulados (SI, misma longitud que ``t_sim``).

    Returns:
        ``(metricas, y_med, y_sim_alineada, timestamps)``; ``metricas`` es None si
        no hubo solape temporal (los arrays quedan vacíos).
    """
    from calculos.metricas_validacion import calcular_metricas

    y_med, y_sim_al, ts = alinear_con_simulada(senal, t_sim, y_sim)
    if len(y_med) == 0:
        return None, y_med, y_sim_al, ts
    metricas = calcular_metricas(y_med, y_sim_al)
    return metricas, y_med, y_sim_al, ts
