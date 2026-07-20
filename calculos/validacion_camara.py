"""Orquestación de la validación de cámara y producto (mejora 38, fase 4).

Corre la **cámara aislada** forzada con el aire de entrada medido en el propio
ensayo y expone sus salidas como series temporales absolutas, listas para
contrastar contra una señal medida con
``calculos.ingesta_referencia.evaluar_ajuste``.

En el colector (fase 2) esta orquestación vivía en la UI porque dependía de
helpers de esa capa; acá es **pura** (sin streamlit), lo que la hace testeable y
reusable tanto por P4 (series) como por P7 (túnel).

Por qué la cámara **aislada**: el ensayo de un lote es, físicamente, un nodo
único (CSTR), aun cuando el proyecto sea de gran escala en modo batch — el
encadenado de lotes de una ventana es un artefacto de producción, no de física.
Forzarla con el aire medido a su entrada aísla el error del modelo de cámara del
error del colector, que es lo único que permite calibrar sin contaminación.

Limitación conocida del túnel semicontinuo: ``ResultadoCascada`` no guarda
historia temporal por zona, solo perfiles espaciales finales y valores por
avance. Por eso :func:`pares_descarga_tunel` y :func:`perfil_zonas` comparan
contra esos dos objetos, que además son los libres del artefacto
euleriano↔lagrangiano (ver ``docs/notas/plan_datos_medidos_4.md``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

from calculos.camara_calc import calcular_camara
from core.validacion import VARIABLES_TEMPERATURA

if TYPE_CHECKING:
    from calculos.camara_termodinamica import ResultadoCascada, ResultadoMotorTermodinamico
    from core.camara import Camara, ForzantesAire

# Variable de referencia → atributo del ResultadoMotorTermodinamico.
# ``masa_producto`` comparte destino con ``X_producto``: la pesada se ingiere ya
# convertida a humedad base seca (ver core/validacion.SenalReferencia).
_ATRIBUTO_POR_VARIABLE: dict[str, str] = {
    "T_camara": "T_flujo_K",
    "HR_camara": "HR_flujo",
    "T_producto": "T_prod_K",
    "X_producto": "X_prod_kg_kg",
    "masa_producto": "X_prod_kg_kg",
}

# Variables que este módulo puede validar (las de cámara/producto).
VARIABLES_CAMARA: tuple[str, ...] = tuple(_ATRIBUTO_POR_VARIABLE)


def simular_camara_aislada(
    camara: "Camara",
    forzantes: "ForzantesAire",
    *,
    P_Pa: float = 101325.0,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
) -> "ResultadoMotorTermodinamico":
    """Corre la cámara sola, forzada con el aire de entrada medido.

    Las condiciones de referencia escalares (``T_operacion_K``/``HR_operacion``)
    se derivan de las propias forzantes: con ``forzantes_aire`` presente el motor
    las ignora para el balance y solo las usa como semilla de los coeficientes.

    Args:
        camara: Cámara configurada del proyecto.
        forzantes: Forzantes del aire de entrada (de
            ``ingesta_referencia.ingerir_forzantes_camara``).
        P_Pa: Presión total [Pa].
        factor_h_conv: Perilla de calibración del convectivo interior.
        factor_K_m: Perilla de calibración de la transferencia de masa.

    Returns:
        ``ResultadoMotorTermodinamico`` con las series del lote.
    """
    from calculos.psicrometria import HR_desde_omega

    T_ref = float(np.mean(forzantes.T_ent_K))
    omega_ref = float(np.mean(forzantes.omega_ent))
    HR_ref = float(np.clip(HR_desde_omega(omega_ref, T_ref, P_Pa), 0.0, 1.0))
    T_amb_ref = float(np.mean(forzantes.T_amb_K))

    return calcular_camara(
        camara,
        T_operacion_K=T_ref,
        HR_operacion=HR_ref,
        T_amb_K=T_amb_ref,
        P_Pa=P_Pa,
        t_max_s=float(forzantes.t_s[-1]),
        forzantes_aire=forzantes,
        factor_h_conv=factor_h_conv,
        factor_K_m=factor_K_m,
    )


def serie_simulada(
    resultado: "ResultadoMotorTermodinamico",
    variable: str,
    t0_utc: pd.Timestamp,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Extrae una serie del resultado, con timestamps **absolutos**.

    El motor integra desde ``t=0``; para comparar contra una señal medida hay que
    reanclar su eje temporal al instante real del origen de las forzantes.

    Args:
        resultado: Salida de :func:`simular_camara_aislada`.
        variable: Variable canónica (una de :data:`VARIABLES_CAMARA`).
        t0_utc: Timestamp UTC correspondiente a ``t=0``
            (``ForzantesMedidas.t0_utc``).

    Returns:
        ``(timestamps, valores)`` en la unidad SI de comparación (K, fracción o
        kg/kg base seca), listos para ``ingesta_referencia.evaluar_ajuste``.

    Raises:
        ValueError: ``VCAM_VARIABLE_NO_SIMULADA`` si la variable no tiene
            contrapartida en el motor de cámara.
    """
    if variable not in _ATRIBUTO_POR_VARIABLE:
        raise ValueError(
            f"VCAM_VARIABLE_NO_SIMULADA: '{variable}' no es una variable de cámara "
            f"(válidas: {', '.join(VARIABLES_CAMARA)})."
        )
    valores = np.asarray(getattr(resultado, _ATRIBUTO_POR_VARIABLE[variable]), dtype=float)
    t_s = np.asarray(resultado.t_array_s, dtype=float)
    t0 = pd.Timestamp(t0_utc)
    if t0.tz is None:
        t0 = t0.tz_localize("UTC")
    else:
        t0 = t0.tz_convert("UTC")
    timestamps = pd.DatetimeIndex(t0 + pd.to_timedelta(t_s, unit="s"))
    return timestamps, valores


def unidad_display(variable: str) -> str:
    """Devuelve la unidad en que conviene **mostrar** la variable en la UI.

    Las métricas de diferencia (RMSE/MBE/MAE) son invariantes al offset K↔°C, así
    que se calculan en SI y se muestran en la unidad familiar.
    """
    if variable in VARIABLES_TEMPERATURA:
        return "°C"
    if variable == "HR_camara":
        return "%"
    return "kg/kg"


def a_display(valores: np.ndarray, variable: str) -> np.ndarray:
    """Convierte valores SI a la unidad de display de :func:`unidad_display`."""
    arr = np.asarray(valores, dtype=float)
    if variable in VARIABLES_TEMPERATURA:
        return arr - 273.15
    if variable == "HR_camara":
        return arr * 100.0
    return arr


def pares_descarga_tunel(
    resultado: "ResultadoCascada",
    t0_utc: pd.Timestamp,
    variable: str = "X_producto",
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Serie de las **descargas** del túnel: un punto por avance de columna.

    Es la comparación lagrangiana natural del semicontinuo: cada punto es la
    columna que sale del túnel, que es exactamente lo que se muestrea en campo.
    El instante asignado a cada descarga es el fin de su intervalo de avance.

    Args:
        resultado: Salida de ``camara_calc.calcular_camara_cascada``.
        t0_utc: Timestamp UTC del inicio de la simulación.
        variable: ``X_producto``/``masa_producto`` (humedad de salida) o
            ``T_producto`` (temperatura del producto descargado).

    Returns:
        ``(timestamps, valores)`` con un punto por avance.

    Raises:
        ValueError: ``VCAM_VARIABLE_NO_DESCARGA`` si la variable no se descarga.
    """
    if variable in ("X_producto", "masa_producto"):
        valores = np.asarray(resultado.X_salida_por_avance, dtype=float)
    elif variable == "T_producto":
        valores = np.asarray(resultado.T_prod_salida_por_avance_K, dtype=float)
    else:
        raise ValueError(
            f"VCAM_VARIABLE_NO_DESCARGA: '{variable}' no es una propiedad del producto "
            "descargado (válidas: X_producto, masa_producto, T_producto)."
        )
    t0 = pd.Timestamp(t0_utc)
    t0 = t0.tz_localize("UTC") if t0.tz is None else t0.tz_convert("UTC")
    segundos = (np.arange(len(valores), dtype=float) + 1.0) * float(resultado.intervalo_avance_s)
    return pd.DatetimeIndex(t0 + pd.to_timedelta(segundos, unit="s")), valores


def perfil_zonas(resultado: "ResultadoCascada", variable: str) -> np.ndarray:
    """Perfil espacial por zona al cierre de la simulación (zona 0 = fresco).

    Es la comparación euleriana natural: la foto instantánea del túnel contra los
    sensores de posición fija.

    Args:
        resultado: Salida de ``camara_calc.calcular_camara_cascada``.
        variable: ``T_camara`` (aire), ``T_producto``, ``X_producto`` /
            ``masa_producto``.

    Returns:
        Array de longitud ``n_zonas`` en la unidad SI de comparación.

    Raises:
        ValueError: ``VCAM_VARIABLE_SIN_PERFIL`` si la variable no tiene perfil.
    """
    mapa = {
        "T_camara": "T_aire_perfil_zonas_K",
        "T_producto": "T_prod_perfil_zonas_K",
        "X_producto": "X_perfil_zonas",
        "masa_producto": "X_perfil_zonas",
    }
    if variable not in mapa:
        raise ValueError(
            f"VCAM_VARIABLE_SIN_PERFIL: '{variable}' no tiene perfil espacial por zona "
            f"(válidas: {', '.join(mapa)})."
        )
    return np.asarray(getattr(resultado, mapa[variable]), dtype=float)


def evaluar_camara(
    camara: "Camara",
    senal,
    forzantes: "ForzantesAire",
    t0_utc: pd.Timestamp,
    *,
    P_Pa: float = 101325.0,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
) -> tuple[Optional[object], "ResultadoMotorTermodinamico"]:
    """Corre la cámara aislada y evalúa el ajuste contra la señal medida.

    Es el nexo que consume la calibración: devuelve las métricas listas para usar
    como función objetivo de ``calculos.calibracion.calibrar_1d``.

    Args:
        camara: Cámara del proyecto.
        senal: ``SenalReferencia`` medida (su ``variable`` decide qué se compara).
        forzantes: Forzantes del aire de entrada.
        t0_utc: Instante absoluto de ``t=0``.
        P_Pa: Presión total [Pa].
        factor_h_conv, factor_K_m: Perillas de calibración.

    Returns:
        ``(metricas, resultado)``; ``metricas`` es None si no hubo solape temporal
        entre la simulación y lo medido.
    """
    from calculos.ingesta_referencia import evaluar_ajuste

    resultado = simular_camara_aislada(
        camara,
        forzantes,
        P_Pa=P_Pa,
        factor_h_conv=factor_h_conv,
        factor_K_m=factor_K_m,
    )
    t_sim, y_sim = serie_simulada(resultado, senal.variable, t0_utc)
    metricas, _, _, _ = evaluar_ajuste(senal, t_sim, y_sim)
    return metricas, resultado
