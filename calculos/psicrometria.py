"""
Ecuaciones psicrométricas del aire húmedo para el sistema de secado solar.

Todas las funciones trabajan en SI:
    T [K], P [Pa], ω [kg_agua / kg_aire_seco], HR [fracción 0–1]

Ecuación de presión de vapor de saturación: Buck (1981), válida para 0–100 °C
con error < 0.05 % en el rango de interés para secado (30–80 °C).

Constante psicrométrica: razón de masas molares agua/aire = 0.622
    (M_agua = 18.015 g/mol, M_aire_seco = 28.966 g/mol → 18.015/28.966 = 0.6220)

Referencias:
    - Buck AL (1981). New equations for computing vapor pressure and
      enhancement factor. J Appl Meteorol 20:1527-1532.
    - WMO-No.8 (2018). Guide to Instruments and Methods of Observation. Cap. 4.
    - Alduchov OA, Eskridge RE (1996). Improved Magnus form approximation of
      saturation vapor pressure. J Appl Meteorol 35:601-609.
    - Rogers RR, Yau MK (1989). A Short Course in Cloud Physics, 3rd ed.
      Pergamon Press. (Calor latente de vaporización lineal en T)
    - ASHRAE Fundamentals (2021), Cap. 1 — Psychrometrics. (Tabla de aire húmedo)
    - Incropera FP, DeWitt DP (2007). Fundamentals of Heat and Mass Transfer,
      6th ed. Wiley. (Analogía de Chilton-Colburn)
    - van den Berg C, Bruin S (1981). Water activity and its estimation in food
      systems. Water Activity: Influences on Food Quality. Academic Press.
      (Modelo GAB)
"""

from __future__ import annotations

import math

from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Constantes — propiedades termofísicas del aire húmedo
# ---------------------------------------------------------------------------

_EPSILON: float = 0.622          # M_agua / M_aire_seco [adim]
_R_AIRE_SECO: float = 287.058    # constante específica del aire seco [J/(kg·K)]

# Calores específicos a presión constante (rango 0–80 °C)
_CP_AIRE_SECO: float = 1006.0    # J/(kg·K) — aire seco
_CP_VAPOR: float = 1805.0        # J/(kg·K) — vapor de agua
_LV_0: float = 2_501_000.0       # J/kg — calor latente a 0 °C
_T_REF: float = 273.15           # K — referencia para entalpías (0 °C)

# Coeficientes de la correlación lineal de Rogers & Yau (1989)
# L_v(T) = L_v0 − k_Lv · (T − T_ref)
_K_LV: float = 2370.0            # J/(kg·K) — pendiente

# ---------------------------------------------------------------------------
# Constantes — Ecuación de Buck (1981)
# ---------------------------------------------------------------------------

_A_BUCK: float = 18.678          # coeficiente ecuación Buck [adim]
_B_BUCK: float = 234.5           # coeficiente ecuación Buck [°C]
_C_BUCK: float = 257.14          # coeficiente ecuación Buck [°C]
_PS0_PA: float = 611.21          # Ps a T=0°C [Pa]

# Para la aproximación del punto de rocío (Alduchov & Eskridge 1996)
_A_DP: float = 17.625
_B_DP: float = 243.04            # [°C]

# ---------------------------------------------------------------------------
# Tolerancias numéricas
# ---------------------------------------------------------------------------

_TOL_TWB: float = 1e-4           # [K] tolerancia de convergencia de T_wb
_MAX_ITER_TWB: int = 100         # iteraciones máximas para T_wb


# ---------------------------------------------------------------------------
# Presión de vapor de saturación
# ---------------------------------------------------------------------------


def presion_vapor_saturacion(T_K: float) -> float:
    """Presión de vapor de saturación del agua líquida [Pa].

    Ecuación de Buck (1981). Error < 0.05 % para 0–80 °C.

    Args:
        T_K: Temperatura [K].

    Returns:
        Ps [Pa].
    """
    T_C = T_K - 273.15
    return _PS0_PA * math.exp(
        (_A_BUCK - T_C / _B_BUCK) * T_C / (_C_BUCK + T_C)
    )


# ---------------------------------------------------------------------------
# Humedad absoluta ↔ HR
# ---------------------------------------------------------------------------


def humedad_absoluta(HR: float, T_K: float, P_Pa: float = 101325.0) -> float:
    """Humedad absoluta ω del aire húmedo [kg_agua / kg_aire_seco].

    A partir de HR, T y P usando la ley de gas ideal:
        ω = ε × Pv / (P − Pv)    donde Pv = HR × Ps(T)

    Args:
        HR: Humedad relativa [fracción 0–1].
        T_K: Temperatura del aire [K].
        P_Pa: Presión total [Pa]. Default: 101 325 Pa.

    Returns:
        ω [kg_agua / kg_aire_seco].

    Raises:
        ValueError: Si Pv ≥ P (condición física imposible).
    """
    Ps = presion_vapor_saturacion(T_K)
    Pv = HR * Ps
    if Pv >= P_Pa:
        raise ValueError(
            f"PSICRO_PV_EXCEDE_P: Pv = {Pv:.1f} Pa ≥ P = {P_Pa:.1f} Pa "
            f"(HR={HR:.3f}, T={T_K - 273.15:.1f} °C). Condición física imposible."
        )
    return _EPSILON * Pv / (P_Pa - Pv)


def HR_desde_omega(omega: float, T_K: float, P_Pa: float = 101325.0) -> float:
    """Humedad relativa HR [fracción] desde ω, T y P.

    Inversa de `humedad_absoluta`. Puede devolver valores > 1 si el aire
    está sobresaturado (condensación): el llamador debe decidir cómo manejar
    ese caso.

    Args:
        omega: Humedad absoluta [kg_agua / kg_aire_seco].
        T_K: Temperatura del aire [K].
        P_Pa: Presión total [Pa].

    Returns:
        HR [fracción]. Puede ser > 1 si hay supersaturación.
    """
    Ps = presion_vapor_saturacion(T_K)
    Pv = omega * P_Pa / (_EPSILON + omega)
    return Pv / Ps


def omega_saturacion(T_K: float, P_Pa: float = 101325.0) -> float:
    """Humedad absoluta de saturación ω_sat [kg_agua / kg_aire_seco].

    Equivalente a humedad_absoluta(HR=1.0, T_K, P_Pa).

    Args:
        T_K: Temperatura del aire [K].
        P_Pa: Presión total [Pa].

    Returns:
        ω_sat [kg_agua / kg_aire_seco].
    """
    return humedad_absoluta(1.0, T_K, P_Pa)


# ---------------------------------------------------------------------------
# Punto de rocío
# ---------------------------------------------------------------------------


def temperatura_punto_rocio(HR: float, T_K: float) -> float:
    """Temperatura de punto de rocío [K].

    Aproximación de Alduchov & Eskridge (1996). Error < 0.4 K para 0–60 °C.

    Args:
        HR: Humedad relativa [fracción > 0].
        T_K: Temperatura del aire [K].

    Returns:
        T_rocio [K].
    """
    if HR <= 0.0:
        return 0.0
    T_C = T_K - 273.15
    gamma = math.log(HR) + _A_DP * T_C / (_B_DP + T_C)
    T_dp_C = _B_DP * gamma / (_A_DP - gamma)
    return T_dp_C + 273.15


# ---------------------------------------------------------------------------
# Balance de masa en la cámara
# ---------------------------------------------------------------------------


def balance_masa_camara(
    omega_entrada: float,
    masa_agua_kg: float,
    m_dot_aire_seco_kg_s: float,
    t_secado_s: float,
) -> float:
    """Calcula la humedad absoluta del aire a la salida de la cámara.

    Balance de masa en estado cuasi-estacionario:
        m_dot_seco × (ω_sal − ω_ent) = m_dot_agua_evap
        ω_sal = ω_ent + masa_agua_kg / (m_dot_seco × t_secado_s)

    Args:
        omega_entrada: Humedad absoluta del aire de entrada [kg/kg].
        masa_agua_kg: Masa total de agua evaporada en el ciclo [kg].
        m_dot_aire_seco_kg_s: Caudal másico de aire seco [kg/s].
        t_secado_s: Tiempo total de secado [s].

    Returns:
        ω_salida [kg_agua / kg_aire_seco].

    Raises:
        ValueError: Si m_dot_aire_seco_kg_s ≤ 0 o t_secado_s ≤ 0.
    """
    if m_dot_aire_seco_kg_s <= 0:
        raise ValueError(
            f"PSICRO_CAUDAL_NO_POSITIVO: m_dot={m_dot_aire_seco_kg_s:.4f} kg/s ≤ 0."
        )
    if t_secado_s <= 0:
        raise ValueError(
            f"PSICRO_T_SECADO_NO_POSITIVO: t={t_secado_s:.1f} s ≤ 0."
        )
    return omega_entrada + masa_agua_kg / (m_dot_aire_seco_kg_s * t_secado_s)


# ---------------------------------------------------------------------------
# Entalpía del aire húmedo
# ---------------------------------------------------------------------------


def entalpia_aire_humedo(T_K: float, omega: float) -> float:
    """Entalpía específica del aire húmedo [J / kg_aire_seco].

    h = cp_as × (T − T_ref) + ω × [Lv + cp_v × (T − T_ref)]

    Propiedades a temperatura media (50 °C):
        cp_aire_seco = 1006 J/(kg·K)
        cp_vapor     = 1805 J/(kg·K)
        Lv           = 2 501 000 J/kg  (a 0 °C)
        T_ref        = 273.15 K  (0 °C)

    Args:
        T_K: Temperatura del aire [K].
        omega: Humedad absoluta [kg_agua / kg_aire_seco].

    Returns:
        h [J / kg_aire_seco].
    """
    delta_T = T_K - _T_REF
    return _CP_AIRE_SECO * delta_T + omega * (_LV_0 + _CP_VAPOR * delta_T)


# ===========================================================================
# AMPLIACIÓN — Sesión 20 — modelo termodinámico transitorio de cámara
# ===========================================================================
#
# Las funciones siguientes habilitan el motor de cámara con balance de
# entalpía acoplado y modelo difusivo de evaporación (h_m).
#
# Orden lógico de dependencias:
#   1. calor_latente_vaporizacion  — usado por T_wb y balance energético
#   2. cp_aire_humedo              — usado por T_wb y h_m de Chilton-Colburn
#   3. volumen_especifico_aire_humedo
#   4. densidad_aire_humedo
#   5. temperatura_bulbo_humedo    — saturación adiabática iterativa
#   6. actividad_agua_desde_X_GAB  — inversión analítica de GAB
#   7. coef_transferencia_masa_chilton_colburn
# ===========================================================================


def calor_latente_vaporizacion(T_K: float) -> float:
    """Calor latente de vaporización del agua L_v [J/kg].

    Correlación lineal de Rogers & Yau (1989), válida para 0–100 °C con
    error < 0.5 % respecto a NIST Webbook en el rango operativo de secado
    solar (5–80 °C).

        L_v(T) = L_v(0°C) − 2370 × (T_K − 273.15)
        L_v(0°C)  ≈ 2 501 000 J/kg
        L_v(100°C) ≈ 2 264 000 J/kg

    Para T < 0 °C la fórmula se extrapola linealmente (sublimación
    aproximada). El error de extrapolación es < 5 % entre -20 °C y 0 °C,
    suficiente para usos transitorios del solver de cámara que ocasionalmente
    visita temperaturas bajas de madrugada o por enfriamiento evaporativo.
    Para T_K extremadamente bajo (< 250 K = -23 °C) se mantiene una guarda
    porque ahí ya es sublimación pura y el modelo lineal no es realista.

    Args:
        T_K: Temperatura [K]. Aceptado en [250, 373] K (-23 a 100 °C).

    Returns:
        L_v [J/kg].

    Raises:
        ValueError: Si T_K < 250 K (extrapolación demasiado agresiva).
    """
    if T_K < 250.0:
        raise ValueError(
            f"PSICRO_LV_T_FUERA_RANGO: T={T_K - 273.15:.1f} °C < -23 °C. "
            "Fuera del rango de extrapolación admisible del modelo lineal."
        )
    return _LV_0 - _K_LV * (T_K - _T_REF)


def cp_aire_humedo(omega: float) -> float:
    """Calor específico del aire húmedo a presión constante [J/(kg_as·K)].

    Por unidad de masa de aire seco:
        cp_hum = cp_aire_seco + ω × cp_vapor

    Relación lineal exacta para mezcla ideal de gases.

    Args:
        omega: Humedad absoluta [kg_agua / kg_aire_seco].

    Returns:
        cp_hum [J / (kg_aire_seco · K)].

    Raises:
        ValueError: Si omega < 0 (no físico).
    """
    if omega < 0.0:
        raise ValueError(
            f"PSICRO_OMEGA_NEGATIVA: ω={omega:.6f} kg/kg < 0."
        )
    return _CP_AIRE_SECO + omega * _CP_VAPOR


def volumen_especifico_aire_humedo(
    T_K: float, omega: float, P_Pa: float = 101325.0
) -> float:
    """Volumen específico del aire húmedo [m³ / kg_aire_seco].

    Por unidad de masa de aire seco, suponiendo gas ideal:
        v = R_aire_seco × T × (1 + ω/ε) / P

    Equivalente a la fórmula de ASHRAE:
        v = R_a × T × (1 + 1.6078 × ω) / P     con 1/ε = 1.6078

    Args:
        T_K: Temperatura del aire [K].
        omega: Humedad absoluta [kg_agua / kg_aire_seco].
        P_Pa: Presión total [Pa].

    Returns:
        v [m³ / kg_aire_seco].

    Raises:
        ValueError: Si T_K ≤ 0, omega < 0, o P_Pa ≤ 0.
    """
    if T_K <= 0.0:
        raise ValueError(f"PSICRO_T_NO_POSITIVA: T={T_K:.2f} K ≤ 0.")
    if omega < 0.0:
        raise ValueError(f"PSICRO_OMEGA_NEGATIVA: ω={omega:.6f} kg/kg < 0.")
    if P_Pa <= 0.0:
        raise ValueError(f"PSICRO_P_NO_POSITIVA: P={P_Pa:.1f} Pa ≤ 0.")
    return _R_AIRE_SECO * T_K * (1.0 + omega / _EPSILON) / P_Pa


def densidad_aire_humedo(
    T_K: float, omega: float, P_Pa: float = 101325.0
) -> float:
    """Densidad de la mezcla aire húmedo [kg_mezcla / m³].

    Por unidad de volumen total. Útil para el cálculo de h_m (Chilton-Colburn)
    y para correlaciones de convección con propiedades del aire húmedo.

        ρ_mezcla = (1 + ω) / v          [kg_total / m³]

    donde v es el volumen específico por kg de aire seco.

    Args:
        T_K: Temperatura del aire [K].
        omega: Humedad absoluta [kg_agua / kg_aire_seco].
        P_Pa: Presión total [Pa].

    Returns:
        ρ [kg_mezcla / m³].
    """
    v = volumen_especifico_aire_humedo(T_K, omega, P_Pa)
    return (1.0 + omega) / v


# ---------------------------------------------------------------------------
# Temperatura de bulbo húmedo — saturación adiabática
# ---------------------------------------------------------------------------


def temperatura_bulbo_humedo(
    T_K: float, omega: float, P_Pa: float = 101325.0
) -> float:
    """Temperatura de bulbo húmedo (saturación adiabática) [K].

    Resuelve el balance energético de saturación adiabática:
        cp_hum(ω) × (T − T_wb) = (ω_sat(T_wb, P) − ω) × L_v(T_wb)

    El aire entrante (T, ω) se enfría adiabáticamente hasta saturarse en T_wb.
    Resuelto con `scipy.optimize.brentq` en el bracket [T_dp − 0.5, T_db].

    Si ω ≥ ω_sat(T, P) el aire ya está saturado: T_wb = T.

    Args:
        T_K: Temperatura de bulbo seco [K].
        omega: Humedad absoluta [kg_agua / kg_aire_seco].
        P_Pa: Presión total [Pa].

    Returns:
        T_wb [K]. Cumple T_dp ≤ T_wb ≤ T.

    Raises:
        ValueError: Si la iteración no converge (poco probable, indica entrada
            patológica o bug).
    """
    omega_sat_T = omega_saturacion(T_K, P_Pa)
    if omega >= omega_sat_T:
        # Aire saturado: T_wb = T_db (no hay potencial de evaporación)
        return T_K

    cp_hum = cp_aire_humedo(omega)

    # Brackets seguros: T_dp ≤ T_wb ≤ T_db
    HR = HR_desde_omega(omega, T_K, P_Pa)
    if HR > 0.0:
        T_dp = temperatura_punto_rocio(HR, T_K)
    else:
        # Aire absolutamente seco: bracket inferior conservador
        T_dp = max(_T_REF + 0.1, T_K - 60.0)

    # Residuo del balance de saturación adiabática (f = LHS − RHS):
    #   f(T_wb) = cp_hum·(T_db − T_wb) − (ω_sat(T_wb) − ω) · L_v(T_wb)
    # En T_wb=T_db: LHS=0, RHS>0  → f < 0
    # En T_wb=T_dp: LHS>0, RHS=0  → f > 0
    # ⇒ raíz garantizada en (T_dp, T_db).

    def _residuo(T_wb_test: float) -> float:
        omega_sat_wb = omega_saturacion(T_wb_test, P_Pa)
        L_v_wb = calor_latente_vaporizacion(T_wb_test)
        return cp_hum * (T_K - T_wb_test) - (omega_sat_wb - omega) * L_v_wb

    # Garantizar bracket válido (por si Alduchov subestima T_dp)
    T_lo = max(_T_REF + 0.01, T_dp - 0.5)
    T_hi = T_K
    f_lo = _residuo(T_lo)
    f_hi = _residuo(T_hi)
    if f_lo * f_hi > 0.0:
        # Bracket inválido: expandir hacia abajo hasta encontrar cambio de signo
        T_lo = _T_REF + 0.01
        f_lo = _residuo(T_lo)
        if f_lo * f_hi > 0.0:
            raise ValueError(
                f"PSICRO_TWB_BRACKET_INVALIDO: no se encontró cambio de signo "
                f"en T ∈ [{T_lo - 273.15:.1f}, {T_hi - 273.15:.1f}] °C para "
                f"T_db={T_K - 273.15:.1f} °C, ω={omega:.5f} kg/kg."
            )

    try:
        T_wb = brentq(_residuo, T_lo, T_hi, xtol=_TOL_TWB, maxiter=_MAX_ITER_TWB)
    except (RuntimeError, ValueError) as exc:
        raise ValueError(
            f"PSICRO_TWB_NO_CONVERGE: brentq falló para T={T_K - 273.15:.1f} °C, "
            f"ω={omega:.5f} kg/kg, P={P_Pa:.0f} Pa. Detalle: {exc}"
        ) from exc
    return T_wb


# ---------------------------------------------------------------------------
# Inversión analítica del modelo GAB
# ---------------------------------------------------------------------------


def actividad_agua_desde_X_GAB(
    X: float, X_m: float, C: float, K: float
) -> float:
    """Inversión analítica del modelo GAB: dado X, devuelve a_w.

    Modelo GAB directo:
        X = X_m · C · K · a_w / [(1 − K·a_w)(1 − K·a_w + C·K·a_w)]

    Definiendo u = K·a_w y reorganizando, se obtiene la cuadrática:
        X·(C−1)·u² + [X_m·C − X·(C−2)]·u − X = 0

    De las dos raíces reales, la positiva es la físicamente válida. Caso
    degenerado: si C ≈ 1, la cuadrática colapsa a lineal y se trata aparte.

    Args:
        X: Contenido de humedad de equilibrio del producto [kg_agua/kg_seco].
        X_m: Humedad de monocapa GAB [kg_agua/kg_seco].
        C: Constante de Guggenheim (energía de adsorción de monocapa) [adim].
            Típicamente 5–30 para alimentos.
        K: Constante GAB (corrección multicapa) [adim]. Típicamente 0.7–0.95.

    Returns:
        a_w [adim, fracción 0–1]. Devuelve 0 si X ≤ 0.

    Raises:
        ValueError: Si los parámetros GAB son no físicos, o si la raíz
            calculada cae fuera de [0, 1] (indica X fuera del rango GAB).
    """
    if X_m <= 0.0:
        raise ValueError(f"PSICRO_GAB_XM_NO_POSITIVA: X_m={X_m:.4f} ≤ 0.")
    if C <= 0.0:
        raise ValueError(f"PSICRO_GAB_C_NO_POSITIVA: C={C:.3f} ≤ 0.")
    if not (0.0 < K < 1.0):
        raise ValueError(
            f"PSICRO_GAB_K_FUERA_RANGO: K={K:.4f} ∉ (0, 1). "
            "K debe estar en el intervalo abierto (0, 1)."
        )
    if X <= 0.0:
        return 0.0

    # Caso degenerado C → 1: GAB colapsa a Henderson lineal en a_w
    if abs(C - 1.0) < 1e-9:
        # X·(1−u)² = X_m·u → ecuación cuadrática diferente
        # X − 2X·u + X·u² = X_m·u → X·u² − (2X + X_m)·u + X = 0
        a_q = X
        b_q = -(2.0 * X + X_m)
        c_q = X
        disc = b_q * b_q - 4.0 * a_q * c_q
        if disc < 0:
            raise ValueError(
                f"PSICRO_GAB_INVERSION_FALLO: discriminante negativo "
                f"(C=1, X={X:.4f}, X_m={X_m:.4f})."
            )
        u = (-b_q - math.sqrt(disc)) / (2.0 * a_q)  # raíz menor (en (0,1))
    else:
        # Caso general: a·u² + b·u + c = 0
        a_q = X * (C - 1.0)
        b_q = X_m * C - X * (C - 2.0)
        c_q = -X

        disc = b_q * b_q - 4.0 * a_q * c_q
        if disc < 0:
            raise ValueError(
                f"PSICRO_GAB_INVERSION_FALLO: discriminante negativo "
                f"(X={X:.4f}, X_m={X_m:.4f}, C={C:.3f}, K={K:.4f})."
            )

        # De las dos raíces, la positiva es la física (producto de raíces = c/a < 0)
        sqrt_disc = math.sqrt(disc)
        u_pos = (-b_q + sqrt_disc) / (2.0 * a_q)
        u_neg = (-b_q - sqrt_disc) / (2.0 * a_q)
        u = u_pos if u_pos > 0 else u_neg

    a_w = u / K

    if not (0.0 <= a_w <= 1.0 + 1e-9):
        raise ValueError(
            f"PSICRO_GAB_AW_FUERA_RANGO: a_w={a_w:.4f} ∉ [0, 1] para "
            f"X={X:.4f} kg/kg con (X_m={X_m:.4f}, C={C:.2f}, K={K:.4f}). "
            "Indica que X está fuera del rango de validez del modelo GAB."
        )
    return min(a_w, 1.0)


# ---------------------------------------------------------------------------
# Coeficiente de transferencia de masa — analogía Chilton-Colburn
# ---------------------------------------------------------------------------


def coef_transferencia_masa_chilton_colburn(
    h_conv: float,
    T_K: float,
    omega: float,
    P_Pa: float = 101325.0,
    Le: float = 1.0,
) -> float:
    """Coeficiente de transferencia de masa h_m por analogía Chilton-Colburn.

    h_m = h_conv / (ρ × cp_hum × Le^(2/3))

    Donde Le es el número de Lewis. Para el sistema aire-vapor de agua,
    Le ≈ 1.0 con error < 5 % en el rango operativo de secado solar.

    Unidades: h_m sale en m/s. La fuerza impulsora del flujo de masa es:
        ṁ_w = h_m × ρ × A × (ω_sup − ω_∞)     [kg/s]
    o equivalentemente:
        ṁ_w = (h_m / v) × A × (ω_sup − ω_∞)   con v = volumen específico

    Args:
        h_conv: Coeficiente convectivo de calor [W/(m²·K)].
        T_K: Temperatura del aire [K].
        omega: Humedad absoluta [kg_agua / kg_aire_seco].
        P_Pa: Presión total [Pa].
        Le: Número de Lewis [adim]. Default 1.0 para aire-agua.

    Returns:
        h_m [m/s].

    Raises:
        ValueError: Si h_conv < 0 o Le ≤ 0.

    References:
        Incropera & DeWitt, "Fundamentals of Heat and Mass Transfer", 6th ed.,
        §6.7 (Chapter 6, Boundary Layer Similarity).
    """
    if h_conv < 0.0:
        raise ValueError(
            f"PSICRO_HCONV_NEGATIVO: h_conv={h_conv:.2f} W/(m²·K) < 0."
        )
    if Le <= 0.0:
        raise ValueError(f"PSICRO_LEWIS_NO_POSITIVO: Le={Le:.3f} ≤ 0.")
    rho = densidad_aire_humedo(T_K, omega, P_Pa)
    cp = cp_aire_humedo(omega)
    return h_conv / (rho * cp * Le ** (2.0 / 3.0))
