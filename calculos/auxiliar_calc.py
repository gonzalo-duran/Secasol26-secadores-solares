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

if TYPE_CHECKING:
    from core.auxiliar import Auxiliar

# Propiedades del aire a ~50 °C (valor medio típico de operación)
CP_AIRE: float = 1007.0   # J/(kg·K)


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
