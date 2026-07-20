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
from calculos.psicrometria import densidad_aire_humedo, humedad_absoluta
from core.validacion import (
    VARIABLES_TEMPERATURA,
    ConfigReferencia,
    ForzantesMedidas,
    SenalReferencia,
)

# Rango físico plausible de una temperatura de flujo del secador [K]
# (−20 °C a 150 °C): fuera de esto la muestra se anula por QC.
_T_MIN_PLAUSIBLE_K: float = 253.15
_T_MAX_PLAUSIBLE_K: float = 423.15

# Humedad del producto en base seca [kg agua/kg seco]: 20 kg/kg es holgado incluso
# para producto fresco muy jugoso (X_bh = 0.95).
_X_MAX_PLAUSIBLE: float = 20.0

# HR medida: por encima de 1 se admite un margen de instrumento (se clipea a 1);
# más allá de eso la muestra se anula.
_HR_CLIP_MAX: float = 1.02

# Rango físico plausible por variable, en la unidad SI de comparación.
_RANGOS_QC: dict[str, tuple[float, float]] = {
    "T_salida_colector": (_T_MIN_PLAUSIBLE_K, _T_MAX_PLAUSIBLE_K),
    "T_camara": (_T_MIN_PLAUSIBLE_K, _T_MAX_PLAUSIBLE_K),
    "T_producto": (_T_MIN_PLAUSIBLE_K, _T_MAX_PLAUSIBLE_K),
    "HR_camara": (0.0, 1.0),
    "X_producto": (0.0, _X_MAX_PLAUSIBLE),
    "masa_producto": (0.0, _X_MAX_PLAUSIBLE),
}


def _descripcion_rango(variable: str) -> str:
    """Describe el rango de QC en unidades legibles, para el mensaje de advertencia."""
    lo, hi = _RANGOS_QC[variable]
    if variable in VARIABLES_TEMPERATURA:
        return f"[{lo - 273.15:.0f}, {hi - 273.15:.0f}] °C"
    if variable == "HR_camara":
        return f"[{lo:.0f}, {hi:.0f}] (fracción)"
    return f"[{lo:.0f}, {hi:.0f}] kg/kg base seca"


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


def _a_fraccion(valores: pd.Series, unidad: str) -> pd.Series:
    """Convierte humedad relativa a fracción 0–1 (``pct`` o ``frac``)."""
    if unidad == "frac":
        return valores
    if unidad == "pct":
        return valores / 100.0
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de HR '{unidad}' desconocida.")


def _a_base_seca(valores: pd.Series, unidad: str) -> pd.Series:
    """Convierte humedad del producto a base seca [kg agua/kg seco].

    La base húmeda (agua sobre masa total) se convierte con
    ``X_bs = X_bh / (1 − X_bh)``; una muestra con X_bh ≥ 1 es imposible y queda NaN.

    Args:
        valores: Serie numérica de humedad.
        unidad: ``kg_kg`` | ``pct_bs`` | ``kg_kg_bh`` | ``pct_bh``.

    Returns:
        Serie en kg agua/kg seco.
    """
    if unidad == "kg_kg":
        return valores
    if unidad == "pct_bs":
        return valores / 100.0
    if unidad in ("kg_kg_bh", "pct_bh"):
        bh = valores / 100.0 if unidad == "pct_bh" else valores
        bh = bh.mask(bh >= 1.0)  # X_bh ≥ 1 no es físico (más agua que masa total)
        return bh / (1.0 - bh)
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de humedad '{unidad}' desconocida.")


def _masa_a_base_seca(valores: pd.Series, unidad: str, masa_seca_kg: float) -> pd.Series:
    """Convierte una pesada de la muestra a humedad base seca (``X = m/m_seco − 1``).

    Args:
        valores: Serie de masa de la muestra.
        unidad: ``kg`` | ``g``.
        masa_seca_kg: Masa seca de la muestra [kg] (> 0, validada en ``ConfigReferencia``).

    Returns:
        Serie en kg agua/kg seco.
    """
    if unidad == "kg":
        masa_kg = valores
    elif unidad == "g":
        masa_kg = valores / 1000.0
    else:
        raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de masa '{unidad}' desconocida.")
    return masa_kg / float(masa_seca_kg) - 1.0


def _a_si_referencia(valores: pd.Series, config: ConfigReferencia) -> pd.Series:
    """Lleva la señal medida a la unidad SI **de comparación** según la variable.

    Temperaturas → K; HR → fracción 0–1; humedad del producto y pesadas → kg agua/kg
    seco (que es lo que devuelve el modelo, ``X_prod_kg_kg``).

    Args:
        valores: Serie numérica cruda (ya limpia de marcadores inválidos).
        config: Configuración de la referencia (aporta variable, unidad y masa seca).

    Returns:
        Serie en la unidad SI de comparación.

    Raises:
        ValueError: ``VREF_UNIDAD_NO_SOPORTADA`` si la unidad no aplica a la variable.
    """
    variable = config.variable
    if variable in VARIABLES_TEMPERATURA:
        return _a_kelvin(valores, config.unidad)
    if variable == "HR_camara":
        return _a_fraccion(valores, config.unidad)
    if variable == "X_producto":
        return _a_base_seca(valores, config.unidad)
    if variable == "masa_producto":
        return _masa_a_base_seca(valores, config.unidad, float(config.masa_seca_kg))
    raise ValueError(f"VREF_VARIABLE_NO_SOPORTADA: '{variable}' no tiene conversión a SI.")


def ingerir_referencia(df_crudo: pd.DataFrame, config: ConfigReferencia) -> SenalReferencia:
    """Ingiere el archivo de referencia → `SenalReferencia` en SI al paso nativo.

    Pasos: timestamp (serial Excel o texto) → tz del archivo → UTC; limpieza de
    marcadores → numérico; conversión a la unidad SI de comparación según la variable
    (K, fracción o kg/kg base seca); QC de rango físico (fuera de rango → NaN);
    inferencia de frecuencia + regularización de grilla.

    Args:
        df_crudo: Tabla cruda leída del archivo (con encabezado ya resuelto).
        config: Configuración de mapeo de la referencia.

    Returns:
        `SenalReferencia` en SI, índice UTC ordenado y regular.

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

    # Conversión a la unidad SI de comparación (K, fracción o kg/kg base seca).
    serie_si = _a_si_referencia(valores.astype(float), config)

    advertencias: list[str] = []

    # Clip benigno de HR: 1 < HR ≤ 1.02 es ruido de instrumento saturado, no un
    # dato inválido (mismo criterio que el QC del clima medido).
    if config.variable == "HR_camara":
        n_clip = int(((serie_si > 1.0) & (serie_si <= _HR_CLIP_MAX)).sum())
        if n_clip > 0:
            serie_si = serie_si.mask(serie_si.between(1.0, _HR_CLIP_MAX, inclusive="right"), 1.0)
            advertencias.append(
                f"VREF_QC_HR_CLIPEADA: {n_clip} muestras con HR entre 1 y "
                f"{_HR_CLIP_MAX:.2f} llevadas a 1 (saturación del sensor)."
            )

    # QC de rango físico: fuera de plausible → NaN.
    n_validos_pre = int(serie_si.notna().sum())
    lo, hi = _RANGOS_QC[config.variable]
    fuera = (serie_si < lo) | (serie_si > hi)
    serie_si = serie_si.mask(fuera)
    n_invalidos = int(serie_si.isna().sum())

    n_fuera = int(fuera.sum())
    if n_fuera > 0:
        advertencias.append(
            f"VREF_QC_FUERA_DE_RANGO: {n_fuera} muestras fuera de "
            f"{_descripcion_rango(config.variable)} anuladas."
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


def _serie_columna(
    df_crudo: pd.DataFrame, columna: str, config: ConfigReferencia, codigo: str
) -> pd.Series:
    """Extrae una columna del archivo como serie numérica limpia.

    Args:
        df_crudo: Tabla cruda del archivo.
        columna: Nombre de la columna a extraer.
        config: Config de la referencia (aporta los marcadores inválidos).
        codigo: Sufijo del código de error si la columna no existe.

    Returns:
        Serie numérica (marcadores → NaN).

    Raises:
        ValueError: ``VREF_COLUMNA_<codigo>_AUSENTE``.
    """
    if columna not in df_crudo.columns:
        raise ValueError(f"VREF_COLUMNA_{codigo}_AUSENTE: '{columna}' no está en el archivo.")
    return _a_numerico(df_crudo[columna], config.marcadores_invalidos)


def _a_caudal_masico_seco(
    valores: pd.Series,
    unidad: str,
    T_ent_K: pd.Series,
    omega_ent: pd.Series,
    P_Pa: float,
) -> pd.Series:
    """Convierte el caudal medido a **aire seco** [kg/s], que es lo que pide el motor.

    Para caudales volumétricos se usa la densidad de la mezcla a las condiciones
    locales y se descuenta el vapor: ``ṁ_as = ρ_mezcla·V̇ / (1 + ω)``.

    Args:
        valores: Serie de caudal medido.
        unidad: ``kg_s`` | ``m3_s`` | ``m3_h``.
        T_ent_K: Temperatura del aire en cada instante [K].
        omega_ent: Humedad absoluta en cada instante [kg/kg as].
        P_Pa: Presión total [Pa].

    Returns:
        Serie de caudal másico de aire seco [kg/s].

    Raises:
        ValueError: ``VREF_UNIDAD_NO_SOPORTADA`` si la unidad no se reconoce.
    """
    if unidad == "kg_s":
        return valores
    if unidad in ("m3_s", "m3_h"):
        vol_m3_s = valores / 3600.0 if unidad == "m3_h" else valores
        rho = pd.Series(
            [
                densidad_aire_humedo(float(T), float(w), P_Pa)
                for T, w in zip(T_ent_K.to_numpy(), omega_ent.to_numpy())
            ],
            index=valores.index,
        )
        return rho * vol_m3_s / (1.0 + omega_ent)
    raise ValueError(f"VREF_UNIDAD_NO_SOPORTADA: unidad de caudal '{unidad}' desconocida.")


def ingerir_forzantes_camara(
    df_crudo: pd.DataFrame,
    config: ConfigReferencia,
    *,
    columna_T_ent: str,
    unidad_T_ent: str = "C",
    columna_HR_ent: str | None = None,
    unidad_HR_ent: str = "pct",
    HR_ent_fija: float | None = None,
    columna_caudal: str | None = None,
    unidad_caudal: str = "kg_s",
    m_dot_fijo_kg_s: float | None = None,
    columna_T_amb: str | None = None,
    unidad_T_amb: str = "C",
    T_amb_fija_K: float = 293.15,
    columna_viento: str | None = None,
    unidad_viento: str = "m_s",
    v_viento_fija_ms: float = 2.0,
    columna_I_g: str | None = None,
    unidad_I_g: str = "W_m2",
    P_Pa: float = 101325.0,
) -> ForzantesMedidas:
    """Construye las forzantes de la **cámara aislada** desde el archivo del ensayo.

    Es el análogo de :func:`ingerir_clima_forzante` (fase 2b) para el segundo eslabón:
    en vez de forzar el colector con el clima medido, fuerza la cámara con el **aire de
    entrada medido** (salida del colector), aislando el modelo de cámara del error del
    colector. Lo que no se midió se asume, y cada supuesto deja una advertencia.

    **Cuidado físico:** ``ω_ent`` es la fuerza motriz de la evaporación
    (``ṁ_w = h_m·A·(ω_sat·a_w − ω_flujo)``). Si la HR de entrada no se midió y se asume,
    el sesgo entra directo al balance de masa y una calibración posterior lo **absorbe
    dentro de K_m**, devolviendo un coeficiente que en realidad compensa una humedad mal
    supuesta. Por eso el caso se marca con ``VREF_HR_ENT_ASUMIDA``.

    Args:
        df_crudo: Tabla cruda del archivo del ensayo.
        config: Config de la referencia (aporta timestamp, tz, ``fecha_fija`` y marcadores).
        columna_T_ent / unidad_T_ent: T del aire a la entrada de cámara (C/K/F).
        columna_HR_ent / unidad_HR_ent: HR a la entrada (pct/frac). None → ``HR_ent_fija``.
        HR_ent_fija: HR de entrada asumida [fracción] si no se midió. None → 0.30.
        columna_caudal / unidad_caudal: Caudal de aire (kg_s/m3_s/m3_h).
            None → ``m_dot_fijo_kg_s``.
        m_dot_fijo_kg_s: Caudal másico de aire seco asumido [kg/s] si no se midió.
        columna_T_amb / unidad_T_amb / T_amb_fija_K: Ambiente exterior (pérdidas de pared).
        columna_viento / unidad_viento / v_viento_fija_ms: Viento exterior (h_w McAdams).
        columna_I_g / unidad_I_g: Irradiancia sobre la cámara (solo cámaras translúcidas).
        P_Pa: Presión total [Pa].

    Returns:
        ``ForzantesMedidas`` con el ``ForzantesAire``, el ``t0_utc`` del origen y las
        advertencias de lo asumido.

    Raises:
        ValueError: ``VREF_COLUMNA_*_AUSENTE`` si falta una columna declarada;
            ``VREF_FORZANTES_VACIAS`` si no queda ningún registro válido;
            ``VREF_CAUDAL_NO_DEFINIDO`` si no hay ni columna ni valor fijo de caudal.
    """
    from core.camara import ForzantesAire

    advertencias: list[str] = []

    idx = _parsear_timestamps_ref(
        df_crudo[config.columna_timestamp], config.zona_horaria, config.fecha_fija
    )
    T_ent_K = _a_kelvin(_serie_columna(df_crudo, columna_T_ent, config, "TENT"), unidad_T_ent)

    if columna_HR_ent is not None:
        HR_ent = _a_fraccion(
            _serie_columna(df_crudo, columna_HR_ent, config, "HRENT"), unidad_HR_ent
        ).clip(lower=0.0, upper=1.0)
    else:
        HR_asumida = 0.30 if HR_ent_fija is None else float(HR_ent_fija)
        HR_ent = pd.Series(HR_asumida, index=df_crudo.index)
        advertencias.append(
            f"VREF_HR_ENT_ASUMIDA: no se mapeó la HR del aire de entrada; se asume "
            f"{HR_asumida:.0%} constante. La humedad de entrada es la fuerza motriz de la "
            "evaporación: un valor mal supuesto sesga el secado y la calibración lo "
            "absorbe dentro de K_m."
        )

    if columna_T_amb is not None:
        T_amb_K = _a_kelvin(_serie_columna(df_crudo, columna_T_amb, config, "TAMB"), unidad_T_amb)
    else:
        T_amb_K = pd.Series(float(T_amb_fija_K), index=df_crudo.index)
        advertencias.append(
            f"VREF_T_AMB_ASUMIDA: sin temperatura ambiente medida se asume "
            f"{T_amb_fija_K - 273.15:.0f} °C constante (afecta la pérdida por paredes)."
        )

    if columna_viento is not None:
        viento = _a_viento_ms(
            _serie_columna(df_crudo, columna_viento, config, "VIENTO"), unidad_viento
        ).clip(lower=0.0)
    else:
        viento = pd.Series(float(v_viento_fija_ms), index=df_crudo.index)
        advertencias.append(
            f"VREF_VIENTO_ASUMIDO: sin anemómetro se asume {v_viento_fija_ms:.1f} m/s "
            "constante (afecta h_w exterior)."
        )

    if columna_I_g is not None:
        I_g = _a_poa_Wm2(_serie_columna(df_crudo, columna_I_g, config, "IG"), unidad_I_g).clip(
            lower=0.0
        )
    else:
        I_g = pd.Series(0.0, index=df_crudo.index)

    datos = pd.DataFrame(
        {
            "T_ent_K": T_ent_K.to_numpy(dtype=float),
            "HR_ent": HR_ent.to_numpy(dtype=float),
            "T_amb_K": T_amb_K.to_numpy(dtype=float),
            "v_viento_ms": viento.to_numpy(dtype=float),
            "I_g_W_m2": I_g.to_numpy(dtype=float),
        },
        index=idx,
    )
    if columna_caudal is not None:
        datos["caudal"] = _serie_columna(df_crudo, columna_caudal, config, "CAUDAL").to_numpy(
            dtype=float
        )
    elif m_dot_fijo_kg_s is None:
        raise ValueError(
            "VREF_CAUDAL_NO_DEFINIDO: hay que mapear una columna de caudal o declarar un "
            "caudal másico fijo para forzar la cámara."
        )

    datos = datos[~datos.index.isna()]
    datos = datos[~datos.index.duplicated(keep="first")].sort_index()
    datos = datos.dropna(subset=["T_ent_K"])
    if len(datos) < 2:
        raise ValueError(
            "VREF_FORZANTES_VACIAS: no quedaron al menos dos registros válidos de aire de "
            "entrada tras el parseo."
        )
    datos = datos.interpolate(method="time").ffill().bfill()

    omega_ent = pd.Series(
        [
            humedad_absoluta(float(hr), float(T), P_Pa)
            for hr, T in zip(datos["HR_ent"].to_numpy(), datos["T_ent_K"].to_numpy())
        ],
        index=datos.index,
    )

    if columna_caudal is not None:
        m_dot = _a_caudal_masico_seco(
            datos["caudal"], unidad_caudal, datos["T_ent_K"], omega_ent, P_Pa
        ).clip(lower=0.0)
    else:
        m_dot = pd.Series(float(m_dot_fijo_kg_s), index=datos.index)
        advertencias.append(
            f"VREF_CAUDAL_ASUMIDO: se usa un caudal fijo de {float(m_dot_fijo_kg_s):.4f} kg/s "
            "de aire seco (no medido en el ensayo)."
        )

    t0 = datos.index[0]
    t_s = (datos.index - t0).total_seconds().to_numpy(dtype=float)
    forzantes = ForzantesAire(
        t_s=t_s,
        T_ent_K=datos["T_ent_K"].to_numpy(dtype=float),
        omega_ent=omega_ent.to_numpy(dtype=float),
        m_dot_aire_seco_kg_s=m_dot.to_numpy(dtype=float),
        T_amb_K=datos["T_amb_K"].to_numpy(dtype=float),
        v_viento_ms=datos["v_viento_ms"].to_numpy(dtype=float),
        I_g_W_m2=datos["I_g_W_m2"].to_numpy(dtype=float),
    )
    return ForzantesMedidas(forzantes=forzantes, t0_utc=t0, advertencias=advertencias)


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
