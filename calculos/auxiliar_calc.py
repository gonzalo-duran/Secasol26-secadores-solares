"""
Motor numérico del sistema de calentamiento auxiliar.

Calcula el salto de temperatura que produce el auxiliar sobre el flujo de aire
y los consumos de energía asociados.

Modelo:
    Balance de energía en régimen estacionario (sin inercia térmica):
        Q_eff = m_dot × cp_aire × (T_salida - T_entrada)
    Despejando T_salida:
        T_salida = T_entrada + Q_eff / (m_dot × cp_aire)

    Q_eff = potencia_nominal_W × fraccion_potencia_operacion

    Si set_point_T_K está definido y T_salida_sin_control > set_point,
    el modelo asume control proporcional ideal: el auxiliar entrega solo la
    potencia necesaria para alcanzar el set point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from core.auxiliar import Auxiliar

# Propiedades del aire a ~50 °C (valor medio típico de operación)
CP_AIRE: float = 1007.0   # J/(kg·K)

# Umbral de irradiancia para considerar "día" en disponible_nocturno=False [W/m²]
_I_G_UMBRAL_DIA_W_M2: float = 10.0


# ---------------------------------------------------------------------------
# Dataclass de resultados
# ---------------------------------------------------------------------------


@dataclass
class ResultadosAuxiliar:
    """Resultados del cálculo del sistema auxiliar.

    Attributes:
        T_entrada_K: Temperatura del aire a la entrada del auxiliar [K].
        T_salida_K: Temperatura del aire a la salida del auxiliar [K].
        delta_T_K: Incremento de temperatura logrado [K].
        Q_efectivo_W: Potencia térmica efectivamente entregada al aire [W].
        Q_nominal_W: Potencia nominal del auxiliar [W].
        fraccion_activa: Fracción de potencia nominal que el auxiliar usó [0,1].
            Puede ser < fraccion_potencia_operacion si el set_point limita la salida.
        consumo_biomasa_kg_h: Consumo de biomasa en operación [kg/h]. None si no es quemador.
        consumo_electrico_W: Potencia eléctrica consumida [W]. None si no es resistencia.
        energia_por_kg_agua_kJ_kg: Energía del auxiliar por kg de agua evaporada [kJ/kg].
            None si no se conoce la tasa de evaporación.
        set_point_activo: True si el control de set_point limitó la potencia.
        advertencias: Lista de mensajes de advertencia del cálculo.
    """

    T_entrada_K: float
    T_salida_K: float
    delta_T_K: float
    Q_efectivo_W: float
    Q_nominal_W: float
    fraccion_activa: float
    consumo_biomasa_kg_h: Optional[float]
    consumo_electrico_W: Optional[float]
    energia_por_kg_agua_kJ_kg: Optional[float]
    set_point_activo: bool
    advertencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def calcular_auxiliar(
    auxiliar: "Auxiliar",
    T_entrada_K: float,
    caudal_masico_kg_s: float,
    masa_agua_a_evaporar_kg: Optional[float] = None,
) -> ResultadosAuxiliar:
    """Calcula el salto térmico y los consumos del sistema auxiliar.

    Args:
        auxiliar: Configuración del sistema auxiliar.
        T_entrada_K: Temperatura del aire a la entrada [K].
            En modo SERIE_POSCOLECTOR: T_salida del colector.
            En modo RESPALDO_INDEPENDIENTE: T_ambiente.
        caudal_masico_kg_s: Caudal másico de aire [kg/s].
        masa_agua_a_evaporar_kg: Masa total de agua a evaporar en la sesión de secado [kg].
            Si se provee, se calcula la energía específica del auxiliar [kJ/kg_agua].

    Returns:
        ResultadosAuxiliar con T_salida, consumos y advertencias.

    Raises:
        ValueError: Si T_entrada_K ≤ 0 o caudal_masico_kg_s ≤ 0.
    """
    if T_entrada_K <= 0:
        raise ValueError(f"T_entrada_K debe ser > 0 K. Recibido: {T_entrada_K}")
    if caudal_masico_kg_s <= 0:
        raise ValueError(
            f"caudal_masico_kg_s debe ser > 0 kg/s. Recibido: {caudal_masico_kg_s}"
        )

    advertencias: list[str] = []
    from core.auxiliar import TipoAuxiliar

    Q_nominal = auxiliar.potencia_nominal_W
    Q_max_posible = Q_nominal * auxiliar.fraccion_potencia_operacion

    # Potencia necesaria para alcanzar el set_point (si está definido)
    set_point_activo = False
    if auxiliar.set_point_T_K is not None:
        Q_para_set_point = caudal_masico_kg_s * CP_AIRE * (
            auxiliar.set_point_T_K - T_entrada_K
        )
        if Q_para_set_point < 0:
            # T_entrada ya supera el set_point — el auxiliar no aporta calor
            Q_efectivo = 0.0
            set_point_activo = True
            advertencias.append(
                f"AUX_T_ENTRADA_SUPERA_SET_POINT: T_entrada={T_entrada_K - 273.15:.1f} °C "
                f"> set_point={auxiliar.set_point_T_K - 273.15:.1f} °C. "
                "El auxiliar no aporta calor."
            )
        elif Q_para_set_point <= Q_max_posible:
            # El auxiliar puede alcanzar el set_point con menos potencia que la nominal
            Q_efectivo = Q_para_set_point
            set_point_activo = True
        else:
            # El auxiliar opera a máxima potencia y no alcanza el set_point
            Q_efectivo = Q_max_posible
            advertencias.append(
                f"AUX_SET_POINT_NO_ALCANZABLE: la potencia máxima ({Q_max_posible:.0f} W) "
                f"es insuficiente para alcanzar el set_point "
                f"({auxiliar.set_point_T_K - 273.15:.1f} °C). "
                f"T_salida real: {T_entrada_K + Q_max_posible / (caudal_masico_kg_s * CP_AIRE) - 273.15:.1f} °C."
            )
    else:
        Q_efectivo = Q_max_posible

    # T_salida resultante
    T_salida = T_entrada_K + Q_efectivo / (caudal_masico_kg_s * CP_AIRE)

    # Verificar que T_salida no supera T_max del auxiliar
    if T_salida > auxiliar.temperatura_maxima_salida_K:
        advertencias.append(
            f"AUX_T_SALIDA_EXCEDE_T_MAX: T_salida={T_salida - 273.15:.1f} °C > "
            f"T_max={auxiliar.temperatura_maxima_salida_K - 273.15:.1f} °C. "
            "Revisar la configuración de potencia o el caudal de aire."
        )

    fraccion_activa = Q_efectivo / Q_nominal if Q_nominal > 0 else 0.0
    delta_T = T_salida - T_entrada_K

    # Consumo de biomasa
    consumo_biomasa: Optional[float] = None
    if auxiliar.tipo == TipoAuxiliar.QUEMADOR_BIOMASA and Q_efectivo > 0:
        consumo_biomasa = auxiliar.consumo_biomasa_efectivo_kg_h()
        if consumo_biomasa is not None:
            # Ajustar consumo a la fracción activa real
            consumo_nominal = auxiliar.consumo_biomasa_efectivo_kg_h()
            if consumo_nominal and auxiliar.fraccion_potencia_operacion > 0:
                consumo_biomasa = (consumo_nominal
                                   * fraccion_activa / auxiliar.fraccion_potencia_operacion)

    # Consumo eléctrico
    consumo_electrico: Optional[float] = None
    if auxiliar.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        # η_resistencia ≈ 1 → P_eléctrica = P_térmica
        consumo_electrico = Q_efectivo

    # Energía por kg de agua evaporada
    energia_por_kg_agua: Optional[float] = None
    if masa_agua_a_evaporar_kg is not None and masa_agua_a_evaporar_kg > 0:
        # Estimación: el auxiliar opera durante un tiempo t_secado
        # (este cálculo es orientativo; la integración real va en Resultados)
        # Aquí solo calculamos la potencia específica instantánea:
        # kJ/kg_agua = Q_eff [W] / tasa_evap [kg_agua/s] → necesita t_secado
        # Sin t_secado, no podemos calcular este valor aquí.
        # Se deja para el módulo de Resultados.
        pass

    return ResultadosAuxiliar(
        T_entrada_K=T_entrada_K,
        T_salida_K=T_salida,
        delta_T_K=delta_T,
        Q_efectivo_W=Q_efectivo,
        Q_nominal_W=Q_nominal,
        fraccion_activa=fraccion_activa,
        consumo_biomasa_kg_h=consumo_biomasa,
        consumo_electrico_W=consumo_electrico,
        energia_por_kg_agua_kJ_kg=energia_por_kg_agua,
        set_point_activo=set_point_activo,
        advertencias=advertencias,
    )


# ---------------------------------------------------------------------------
# Solver transitorio (vectorizado sobre el horizonte de cámara)
# ---------------------------------------------------------------------------


@dataclass
class ResultadosAuxiliarTransitorio:
    """Resultados del auxiliar evaluado sobre un horizonte temporal.

    Cada serie tiene la misma longitud que ``t_s``. La política de operación
    (set_point, fracción de potencia, disponibilidad nocturna) se aplica a
    cada paso de tiempo de forma desacoplada — es decir, se asume que el
    auxiliar reacciona instantáneamente al estado del aire entrante.

    Attributes:
        t_s: Tiempos [s].
        T_entrada_K: Serie de T del aire a la entrada del auxiliar [K].
        T_salida_K: Serie de T del aire a la salida del auxiliar [K].
        delta_T_K: Serie de aumento ΔT producido [K].
        Q_efectivo_W: Serie de potencia térmica entregada al aire [W].
        E_aux_MJ: Energía total entregada en el horizonte [MJ],
            calculada como ∫ Q_efectivo dt.
        horas_activo_s: Tiempo con Q_efectivo > 0 [s].
        Q_max_W: Potencia máxima alcanzada en el horizonte [W].
        delta_T_max_K: ΔT máximo alcanzado en el horizonte [K].
        fraccion_horas_activo: horas_activo_s / (t_s[-1] - t_s[0]).
        advertencias_unicas: Mensajes deduplicados de la corrida escalar.
        activado_alguna_vez: True si Q_efectivo > 0 en algún punto del horizonte.
    """

    t_s: np.ndarray
    T_entrada_K: np.ndarray
    T_salida_K: np.ndarray
    delta_T_K: np.ndarray
    Q_efectivo_W: np.ndarray
    E_aux_MJ: float
    horas_activo_s: float
    Q_max_W: float
    delta_T_max_K: float
    fraccion_horas_activo: float
    advertencias_unicas: list[str] = field(default_factory=list)
    activado_alguna_vez: bool = False


def calcular_auxiliar_transitorio(
    auxiliar: "Auxiliar",
    *,
    T_entrada_K_serie: np.ndarray,
    t_s: np.ndarray,
    caudal_masico_kg_s: float,
    I_g_W_m2_serie: Optional[np.ndarray] = None,
) -> ResultadosAuxiliarTransitorio:
    """Evalúa el auxiliar a cada paso del horizonte temporal.

    Reusa la lógica escalar de ``calcular_auxiliar`` paso a paso. Si el
    auxiliar tiene ``disponible_nocturno = False`` y se provee
    ``I_g_W_m2_serie``, los pasos con ``I_g ≤ _I_G_UMBRAL_DIA_W_M2`` quedan
    forzados a ``Q_efectivo = 0`` (auxiliar apagado de noche).

    Args:
        auxiliar: Configuración del sistema auxiliar.
        T_entrada_K_serie: Serie de T del aire entrante al auxiliar [K].
            En modo SERIE_POSCOLECTOR, es T_salida del colector.
        t_s: Tiempos [s] (mismo length que T_entrada_K_serie).
        caudal_masico_kg_s: Caudal másico [kg/s] (escalar, constante).
        I_g_W_m2_serie: Irradiancia [W/m²] para evaluar día/noche cuando
            ``disponible_nocturno = False``. None → asume día siempre.

    Returns:
        ResultadosAuxiliarTransitorio con series y acumulados.
    """
    n = len(t_s)
    if len(T_entrada_K_serie) != n:
        raise ValueError(
            f"AUX_TR_LONGITUD_INCONSISTENTE: T_entrada_K_serie tiene "
            f"{len(T_entrada_K_serie)} elementos, esperado {n}."
        )
    if caudal_masico_kg_s <= 0:
        raise ValueError(
            f"AUX_TR_CAUDAL_NO_POSITIVO: caudal_masico_kg_s="
            f"{caudal_masico_kg_s} ≤ 0."
        )

    es_dia = (
        np.full(n, True, dtype=bool)
        if I_g_W_m2_serie is None or auxiliar.disponible_nocturno
        else (np.asarray(I_g_W_m2_serie) > _I_G_UMBRAL_DIA_W_M2)
    )

    T_salida = np.empty(n, dtype=float)
    delta_T = np.empty(n, dtype=float)
    Q_eff = np.empty(n, dtype=float)
    advertencias_set: dict[str, None] = {}    # dict preserva orden de inserción

    for i in range(n):
        T_ent_i = float(T_entrada_K_serie[i])
        if not es_dia[i]:
            T_salida[i] = T_ent_i
            delta_T[i] = 0.0
            Q_eff[i] = 0.0
            continue
        res_i = calcular_auxiliar(
            auxiliar=auxiliar,
            T_entrada_K=T_ent_i,
            caudal_masico_kg_s=caudal_masico_kg_s,
        )
        T_salida[i] = res_i.T_salida_K
        delta_T[i] = res_i.delta_T_K
        Q_eff[i] = res_i.Q_efectivo_W
        for msg in res_i.advertencias:
            advertencias_set[msg] = None

    # Energía total: trapezoidal sobre Q_efectivo
    E_aux_MJ = float(np.trapezoid(Q_eff, t_s) / 1e6) if n > 1 else 0.0
    # Horas activas: integrar el indicador 1_{Q>0} sobre t
    activo = (Q_eff > 0.0).astype(float)
    horas_activo_s = float(np.trapezoid(activo, t_s)) if n > 1 else 0.0
    span_s = float(t_s[-1] - t_s[0]) if n > 1 else 0.0
    fraccion = horas_activo_s / span_s if span_s > 0 else 0.0

    return ResultadosAuxiliarTransitorio(
        t_s=np.asarray(t_s, dtype=float),
        T_entrada_K=np.asarray(T_entrada_K_serie, dtype=float),
        T_salida_K=T_salida,
        delta_T_K=delta_T,
        Q_efectivo_W=Q_eff,
        E_aux_MJ=E_aux_MJ,
        horas_activo_s=horas_activo_s,
        Q_max_W=float(np.max(Q_eff)) if n > 0 else 0.0,
        delta_T_max_K=float(np.max(delta_T)) if n > 0 else 0.0,
        fraccion_horas_activo=fraccion,
        advertencias_unicas=list(advertencias_set.keys()),
        activado_alguna_vez=bool(np.any(Q_eff > 0.0)),
    )
