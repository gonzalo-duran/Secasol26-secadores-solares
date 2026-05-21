"""Eficiencias de cámara de secado — método Augustus Leon (RSER 2002).

Define las cuatro eficiencias del método estándar de evaluación de desempeño
de secadores solares. Las funciones toman primitivas (m_agua, energías,
áreas) para ser usables tanto desde simulaciones (motor termodinámico) como
desde balances analíticos a escala mensual.

Referencia:
    Augustus Leon, M., Kumar, S., Bhattacharya, S.C. (2002).
    "A comprehensive procedure for performance evaluation of solar food dryers".
    Renewable and Sustainable Energy Reviews 6(4), pp. 367-393.

Convención de unidades: SI estricto (J, kg, m, s, K).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Calor latente de vaporización del agua
# ---------------------------------------------------------------------------


def calor_latente_agua_J_kg(T_K: float) -> float:
    """Calor latente de vaporización del agua [J/kg] vs T.

    Correlación lineal aproximada en el rango 273–373 K (error < 1 %):

        h_fg = 2.501e6 − 2.386e3 · (T − 273.15)

    Valores de referencia: ~2.45e6 a 20 °C, ~2.38e6 a 50 °C, ~2.27e6 a 90 °C.

    Args:
        T_K: Temperatura [K]. Recomendado en el rango 273–373 K.

    Returns:
        h_fg [J/kg].
    """
    return 2.501e6 - 2.386e3 * (T_K - 273.15)


# ---------------------------------------------------------------------------
# Las cuatro eficiencias de Augustus Leon
# ---------------------------------------------------------------------------


def eta_drying(
    m_agua_evaporada_kg: float,
    I_total_J_m2: float,
    A_col_m2: float,
    T_evap_K: float = 323.15,
) -> float:
    """η_drying = m_agua · h_fg / (I_total · A_col).

    Eficiencia específica de secado: fracción de la radiación solar incidente
    sobre el colector que termina convertida en evaporación de agua. Es la
    eficiencia más sintética del método Augustus Leon y la más usada en
    comparaciones entre prototipos.

    Args:
        m_agua_evaporada_kg: Masa total de agua evaporada en el batch [kg].
        I_total_J_m2: Irradiación total sobre el colector durante el batch
            [J/m²]. Equivale a ∫ POA(t) dt en el horizonte del batch.
        A_col_m2: Área del colector [m²].
        T_evap_K: Temperatura de referencia para h_fg [K]. Default 50 °C.

    Returns:
        η_drying adimensional. Cero si no hay evaporación o si la entrada
        de energía es nula.
    """
    if I_total_J_m2 <= 0 or A_col_m2 <= 0 or m_agua_evaporada_kg <= 0:
        return 0.0
    h_fg = calor_latente_agua_J_kg(T_evap_K)
    return m_agua_evaporada_kg * h_fg / (I_total_J_m2 * A_col_m2)


def eta_pickup(
    omega_entrada_kg_kg: float,
    omega_salida_kg_kg: float,
    omega_sat_salida_kg_kg: float,
) -> float:
    """η_pickup = (ω_sal − ω_ent) / (ω_sat_sal − ω_ent).

    Eficiencia de captura de humedad del aire en la cámara: qué fracción
    del potencial de pickup (entre ω_entrada y la saturación a T_salida)
    realmente se aprovecha. 1.0 indica aire sale saturado — caso ideal
    de extracción de humedad.

    Args:
        omega_entrada_kg_kg: ω del aire a la entrada de la cámara
            [kg agua / kg aire seco].
        omega_salida_kg_kg: ω del aire a la salida de la cámara.
        omega_sat_salida_kg_kg: ω de saturación a T_salida_cámara.

    Returns:
        η_pickup adimensional, clipeado a [0, 1]. Cero si ω_sat_sal ≤ ω_ent
        (no hay capacidad de captación).
    """
    denom = omega_sat_salida_kg_kg - omega_entrada_kg_kg
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, (omega_salida_kg_kg - omega_entrada_kg_kg) / denom))


def eta_termica_camara(
    Q_aire_entregado_J: float,
    I_total_J_m2: float,
    A_col_m2: float,
) -> float:
    """η_térmica = Q_aire_entregado / Q_solar_disponible.

    Eficiencia térmica del subsistema colector: cuánta energía solar se
    convierte en energía sensible del aire que entra a la cámara. Equivale
    a la eficiencia "instantánea promedio" del colector en el período
    del batch.

    Args:
        Q_aire_entregado_J: Energía sensible total entregada al aire por
            el colector durante el batch [J] = ∫ ṁ·c_p·(T_salida−T_amb) dt.
        I_total_J_m2: Irradiación total sobre el colector [J/m²].
        A_col_m2: Área del colector [m²].

    Returns:
        η_térmica adimensional. Cero si no hay radiación recibida.
    """
    if I_total_J_m2 <= 0 or A_col_m2 <= 0:
        return 0.0
    return Q_aire_entregado_J / (I_total_J_m2 * A_col_m2)


def eta_total_sistema(
    m_agua_evaporada_kg: float,
    E_solar_J: float,
    E_auxiliar_J: float = 0.0,
    T_evap_K: float = 323.15,
) -> float:
    """η_total = m_agua · h_fg / (E_solar + E_auxiliar).

    Eficiencia global del sistema: agua evaporada por unidad de energía
    primaria total invertida. La métrica más útil para evaluación económica
    y comparación entre configuraciones con/sin auxiliar.

    Args:
        m_agua_evaporada_kg: Masa total de agua evaporada en el batch [kg].
        E_solar_J: Energía solar total recibida sobre el colector
            durante el batch [J] = I_total_J_m2 · A_col_m2.
        E_auxiliar_J: Energía total aportada por el auxiliar [J].
            Default 0 (sin auxiliar).
        T_evap_K: Temperatura de referencia para h_fg [K]. Default 50 °C.

    Returns:
        η_total adimensional. Cero si la energía total invertida es nula
        o si no hubo evaporación.
    """
    denom = E_solar_J + E_auxiliar_J
    if denom <= 0 or m_agua_evaporada_kg <= 0:
        return 0.0
    h_fg = calor_latente_agua_J_kg(T_evap_K)
    return m_agua_evaporada_kg * h_fg / denom
