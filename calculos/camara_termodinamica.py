"""
Solver algebraico de cámara — motor termodinámico transitorio.

Resuelve el sistema acoplado para las variables algebraicas
(T_flujo, ω_flujo, T_cam_int, T_cam_ext) dado el estado del producto
(T_prod, X_prod) y las condiciones de boundary (T_ent, ω_ent, T_amb).

Hipótesis:
- CSTR (mezcla perfecta): aire en cámara uniforme a (T_flujo, ω_flujo).
- Cuasi-estacionario en aire (residencia << tiempo de secado).
- Pared en 3 nodos: T_flujo → T_cam_int (convección interior h_conv_int) →
  T_cam_ext (conducción por aislante k_aisl/esp_cam) → T_amb (convección
  exterior h_w por viento). La cascada se resuelve analíticamente en
  U_total = 1/(1/h_conv_int + esp_cam/k_aisl + 1/h_w); T_cam_int y T_cam_ext
  se reconstruyen como post-cómputos de la solución de T_flujo.
- Cinética de evaporación difusiva: ṁ_w = K_m · A_prod · (ω_sup − ω_flujo),
  con K_m la conductancia másica [kg/(m²·s)] y ω_sup = ω_sat(T_prod)·a_w(X_prod).

Resolución analítica directa (sin iteración interna), aprovechando la
linealidad del sistema cuando se fijan h_conv_int, K_m al inicio del paso:
    1. ω_sup = ω_sat(T_prod) · a_w(X_prod)
    2. (a) lineal en ω_flujo  → ω_flujo directo
    3. ṁ_w = ṁ_as · (ω_flujo − ω_ent)
    4. (b) lineal en T_flujo  → T_flujo directo
    5. T_cam_int, T_cam_ext por reparto resistivo de Q_pared

Referencias:
    - Bitácora Sesión 20 §24.3 (sistema de ecuaciones).
    - docs/notas/balance de calor y masa en camara ampliado.md (3-nodos pared).
    - Hallaire M (1963), reformulado en Mujumdar AS (ed.) Handbook of
      Industrial Drying, 4th ed., Cap. 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp

from calculos.psicrometria import (
    _CP_VAPOR,
    _LV_0,
    _T_REF,
    HR_desde_omega,
    calor_latente_vaporizacion,
    cp_aire_humedo,
    entalpia_aire_humedo,
    omega_saturacion,
)
from core.camara import ForzantesAire

# Constantes físicas
_CP_AGUA_LIQ_J_KGK: float = 4186.0   # cp del agua líquida (para cp_prod variable)
_HR_SAT_UMBRAL: float = 0.95          # umbral para advertencia HR_flujo alta


@dataclass(frozen=True)
class EstadoCamara:
    """Estado algebraico instantáneo de la cámara para (T_prod, X_prod) dado.

    Atributos:
        T_flujo_K: Temperatura del aire en cámara (CSTR) [K].
        omega_flujo_kg_kg: Humedad absoluta del aire en cámara [kg/kg_as].
        m_dot_w_kg_s: Caudal de agua evaporada [kg/s]. Positivo = evaporación,
            negativo = condensación sobre el producto (físicamente posible si
            el producto está más seco que el aire de entrada).
        q_prod_W: Calor sensible aire → producto [W]. Positivo si el aire
            calienta al producto.
        q_pared_W: Calor sensible aire → ambiente vía paredes [W]. Positivo
            si la cámara pierde calor al ambiente.
        T_cam_int_K: Temperatura de la cara interna de la pared [K].
            Reconstruida del reparto resistivo: T_cam_int = T_flujo −
            Q_pared/(h_conv_int·A_cuerpo). Si Q_pared=0, T_cam_int = T_flujo.
        T_cam_ext_K: Temperatura de la cara externa de la pared [K].
            Reconstruida del reparto resistivo: T_cam_ext = T_amb +
            Q_pared/(h_w·A_cuerpo). Si Q_pared=0, T_cam_ext = T_amb.
        U_pared_W_m2K: Coeficiente global de transmisión de pared resultante
            de la cascada h_conv_int + k_aisl/esp_cam + h_w [W/(m²·K)].
            Diagnóstico para verificación contra el U_muros del data model.
    """

    T_flujo_K: float
    omega_flujo_kg_kg: float
    m_dot_w_kg_s: float
    q_prod_W: float
    q_pared_W: float
    T_cam_int_K: float
    T_cam_ext_K: float
    U_pared_W_m2K: float


def resolver_estado_camara(
    *,
    T_prod_K: float,
    X_prod_kg_kg: float,
    T_ent_K: float,
    omega_ent_kg_kg: float,
    A_prod_m2: float,
    A_cuerpo_m2: float,
    m_dot_as_kg_s: float,
    h_conv_W_m2K: float,
    K_m_kg_m2s: float,
    h_w_W_m2K: float,
    k_aisl_W_mK: float,
    esp_cam_m: float,
    T_amb_K: float,
    P_Pa: float,
    aw_func: Callable[[float], float],
) -> EstadoCamara:
    """Resuelve el sistema algebraico de cámara (CSTR, cuasi-estacionario).

    Sistema de ecuaciones:
        (a) Balance de masa del aire:
            ṁ_as·(ω_flujo − ω_ent) = K_m·A_prod·(ω_sup − ω_flujo)
        (b) Balance de energía del aire (entalpía):
            ṁ_as·[h(T_flujo, ω_flujo) − h(T_ent, ω_ent)]
              = − U_total·A_cuerpo·(T_flujo − T_amb)
                − h_conv·A_prod·(T_flujo − T_prod)
                + ṁ_w · h_v(T_prod)
            El último término es POSITIVO: el vapor sale del producto a
            T_prod y se incorpora al aire llevando su entalpía h_v(T_prod).
        (c) Pared interna (cuasi-estacionaria):
            h_conv·A_cuerpo·(T_flujo − T_cam_int)
                = (k_aisl/esp_cam)·A_cuerpo·(T_cam_int − T_cam_ext)
        (d) Pared externa (cuasi-estacionaria):
            (k_aisl/esp_cam)·A_cuerpo·(T_cam_int − T_cam_ext)
                = h_w·A_cuerpo·(T_cam_ext − T_amb)

    (c) y (d) se combinan en U_total = 1/(1/h_conv + esp_cam/k_aisl + 1/h_w);
    T_cam_int y T_cam_ext se reconstruyen como post-cómputos a partir de
    Q_pared = U_total·A_cuerpo·(T_flujo − T_amb).

    Resolución analítica directa, sin iteración. Costo: O(1) por llamada.

    Args:
        T_prod_K: Temperatura del producto [K] (estado).
        X_prod_kg_kg: Humedad del producto [kg_agua/kg_seco] (estado).
        T_ent_K: Temperatura del aire de entrada [K] (boundary).
        omega_ent_kg_kg: Humedad absoluta del aire de entrada [kg/kg_as].
        A_prod_m2: Área de transferencia con el producto [m²].
        A_cuerpo_m2: Área de paredes externas [m²].
        m_dot_as_kg_s: Caudal másico de aire seco [kg/s].
        h_conv_W_m2K: Coeficiente convectivo interior aire→producto y
            aire→pared [W/(m²·K)].
        K_m_kg_m2s: Conductancia másica = ρ·h_m_chilton [kg/(m²·s)].
            El llamador computa esto multiplicando h_m_chilton (m/s) por
            la densidad del aire húmedo evaluada a una T de referencia.
        h_w_W_m2K: Coeficiente convectivo exterior por viento [W/(m²·K)].
            Calculado por correlación McAdams h_w = 5.7 + 3.8·v_viento.
            Si h_w = 0, la cara externa queda térmicamente desacoplada del
            ambiente; T_cam_ext se aproxima a T_cam_int.
        k_aisl_W_mK: Conductividad térmica del aislante de pared [W/(m·K)].
            Si k_aisl = 0, la pared es aislante perfecta: U_total = 0,
            T_cam_int = T_flujo y T_cam_ext = T_amb (no acoplados).
        esp_cam_m: Espesor de la pared [m]. Debe ser > 0.
        T_amb_K: Temperatura ambiente externa [K].
        P_Pa: Presión total [Pa].
        aw_func: Función X → a_w (típicamente inversión GAB).

    Returns:
        EstadoCamara con T_flujo, ω_flujo, ṁ_w, q_prod, q_pared, T_cam_int,
        T_cam_ext y U_pared.

    Raises:
        ValueError: Si ṁ_as ≤ 0, A_prod < 0, A_cuerpo < 0, h_conv < 0,
            K_m < 0, h_w < 0, k_aisl < 0, esp_cam ≤ 0, o P_Pa ≤ 0.
    """
    # --- Validación dura ---
    if m_dot_as_kg_s <= 0:
        raise ValueError(
            f"CAM_TD_M_DOT_NO_POSITIVO: ṁ_as={m_dot_as_kg_s:.4f} kg/s ≤ 0."
        )
    if A_prod_m2 < 0:
        raise ValueError(
            f"CAM_TD_A_PROD_NEGATIVA: A_prod={A_prod_m2:.3f} m² < 0."
        )
    if A_cuerpo_m2 < 0:
        raise ValueError(
            f"CAM_TD_A_CUERPO_NEGATIVA: A_cuerpo={A_cuerpo_m2:.3f} m² < 0."
        )
    if h_conv_W_m2K < 0:
        raise ValueError(
            f"CAM_TD_H_CONV_NEGATIVO: h_conv={h_conv_W_m2K:.2f} W/(m²·K) < 0."
        )
    if K_m_kg_m2s < 0:
        raise ValueError(
            f"CAM_TD_KM_NEGATIVO: K_m={K_m_kg_m2s:.4f} kg/(m²·s) < 0."
        )
    if h_w_W_m2K < 0:
        raise ValueError(
            f"CAM_TD_H_W_NEGATIVO: h_w={h_w_W_m2K:.2f} W/(m²·K) < 0."
        )
    if k_aisl_W_mK < 0:
        raise ValueError(
            f"CAM_TD_K_AISL_NEGATIVA: k_aisl={k_aisl_W_mK:.4f} W/(m·K) < 0."
        )
    if esp_cam_m <= 0:
        raise ValueError(
            f"CAM_TD_ESP_CAM_NO_POSITIVO: esp_cam={esp_cam_m:.4f} m ≤ 0."
        )
    if P_Pa <= 0:
        raise ValueError(f"CAM_TD_P_NO_POSITIVA: P={P_Pa:.1f} Pa ≤ 0.")

    # --- 1) Humedad absoluta de superficie del producto ---
    omega_sat_prod = omega_saturacion(T_prod_K, P_Pa)
    a_w = aw_func(X_prod_kg_kg)
    # Clip por tolerancia numérica de la inversión GAB (puede dar a_w ≈ 1+ε).
    a_w_clipped = max(0.0, min(1.0, a_w))
    omega_sup = omega_sat_prod * a_w_clipped

    # --- 2) Resolución de (a) — lineal en ω_flujo ---
    # ṁ_as·(ω_flujo − ω_ent) = K_A·(ω_sup − ω_flujo)
    # ⇒ ω_flujo·(ṁ_as + K_A) = ṁ_as·ω_ent + K_A·ω_sup
    K_A = K_m_kg_m2s * A_prod_m2  # [kg/s]
    omega_flujo = (
        m_dot_as_kg_s * omega_ent_kg_kg + K_A * omega_sup
    ) / (m_dot_as_kg_s + K_A)

    # --- 3) Caudal de evaporación (signo: + evap, − condensación) ---
    m_dot_w = m_dot_as_kg_s * (omega_flujo - omega_ent_kg_kg)

    # --- 4) Cascada resistiva de pared en 3 nodos ---
    # R_total = 1/h_conv_int + esp_cam/k_aisl + 1/h_w  →  U_total = 1/R_total
    # k_aisl = 0  →  R_cond = ∞  →  U_total = 0  (pared aislante perfecta).
    # h_conv_int = 0 o h_w = 0  →  el film correspondiente domina (R_total = ∞).
    if k_aisl_W_mK == 0.0 or h_conv_W_m2K == 0.0 or h_w_W_m2K == 0.0:
        U_total = 0.0
    else:
        R_total = (
            1.0 / h_conv_W_m2K
            + esp_cam_m / k_aisl_W_mK
            + 1.0 / h_w_W_m2K
        )
        U_total = 1.0 / R_total

    # --- 5) Resolución de (b) — lineal en T_flujo ---
    # h(T, ω) = cp_hum(ω)·(T − T_ref) + ω·L_v0  (forma usada por
    # entalpia_aire_humedo) → lineal en T para ω fijo.
    cp_hum_flujo = cp_aire_humedo(omega_flujo)
    h_ent = entalpia_aire_humedo(T_ent_K, omega_ent_kg_kg)

    # Entalpía del vapor que sale del producto a T_prod, consistente con la
    # convención de entalpía de aire húmedo (referencia T_ref = 273.15 K).
    h_v_prod = _LV_0 + _CP_VAPOR * (T_prod_K - _T_REF)

    UA_c = U_total * A_cuerpo_m2
    hA_p = h_conv_W_m2K * A_prod_m2

    numerador = (
        m_dot_as_kg_s * cp_hum_flujo * _T_REF
        + m_dot_as_kg_s * (h_ent - omega_flujo * _LV_0)
        + UA_c * T_amb_K
        + hA_p * T_prod_K
        + m_dot_w * h_v_prod
    )
    denominador = m_dot_as_kg_s * cp_hum_flujo + UA_c + hA_p
    T_flujo = numerador / denominador

    # --- Diagnósticos ---
    q_prod = hA_p * (T_flujo - T_prod_K)
    q_pared = UA_c * (T_flujo - T_amb_K)

    # --- 6) Reconstrucción de T_cam_int y T_cam_ext ---
    # Q_pared (W) atraviesa cada resistencia en serie con el mismo valor.
    # Caída por convección interior: ΔT_int = Q_pared / (h_conv·A_cuerpo)
    # Caída por convección exterior: ΔT_ext = Q_pared / (h_w·A_cuerpo)
    # Si U_total = 0, Q_pared = 0 → T_cam_int = T_flujo, T_cam_ext = T_amb
    # (pared desacoplada: cada cara está al equilibrio con su lado).
    if U_total == 0.0 or A_cuerpo_m2 == 0.0:
        T_cam_int = T_flujo
        T_cam_ext = T_amb_K
    else:
        T_cam_int = T_flujo - q_pared / (h_conv_W_m2K * A_cuerpo_m2)
        T_cam_ext = T_amb_K + q_pared / (h_w_W_m2K * A_cuerpo_m2)

    return EstadoCamara(
        T_flujo_K=T_flujo,
        omega_flujo_kg_kg=omega_flujo,
        m_dot_w_kg_s=m_dot_w,
        q_prod_W=q_prod,
        q_pared_W=q_pared,
        T_cam_int_K=T_cam_int,
        T_cam_ext_K=T_cam_ext,
        U_pared_W_m2K=U_total,
    )


# ===========================================================================
# S3 — Motor termodinámico transitorio (solve_ivp + event detection)
# ===========================================================================
#
# Integra las dos EDOs del producto (T_prod, X_prod) acopladas con el solver
# algebraico de S2 evaluado en cada paso. h_conv y K_m se reciben como inputs
# fijos (opción ii: congelar por paso, ver bitácora §24.10) — es el llamador
# quien los computa con T_película = (T_ent + T_prod_inicial)/2.
#
# Sistema integrado:
#     dX_prod/dt = − ṁ_w / m_seco_prod
#     m_prod·cp_prod · dT_prod/dt = q_prod − ṁ_w · L_v(T_prod)
#
# donde (ṁ_w, q_prod) salen de resolver_estado_camara(T_prod, X_prod, ...).
#
# Event detection: integración termina cuando X_prod = X_objetivo.
# ===========================================================================


@dataclass(frozen=True)
class ResultadoMotorTermodinamico:
    """Salida del motor termodinámico transitorio.

    Atributos:
        t_secado_s: Tiempo hasta alcanzar X_objetivo [s]. ``None`` si no se
            alcanzó dentro de t_max_s.
        status: Estado del solver. Uno de:
            'X_obj_alcanzado' | 't_max_alcanzado' | 'X_inicial_ya_seco'
            | 'dano_termico' | 'error'.
        t_array_s: Vector de tiempos de la solución [s].
        T_prod_K: Serie temporal de T_prod [K], shape (n,).
        X_prod_kg_kg: Serie temporal de X_prod [kg/kg seco], shape (n,).
        T_flujo_K: Serie reconstruida de T_flujo [K], shape (n,).
        omega_flujo_kg_kg: Serie reconstruida de ω_flujo [kg/kg as], shape (n,).
        m_dot_w_kg_s: Serie reconstruida de tasa de evaporación [kg/s], shape (n,).
        q_prod_W: Serie reconstruida de calor sensible aire→producto [W].
        q_pared_W: Serie reconstruida de pérdida a paredes [W].
        T_cam_int_K: Serie reconstruida de T de cara interna de pared [K].
        T_cam_ext_K: Serie reconstruida de T de cara externa de pared [K].
        U_pared_W_m2K: Serie reconstruida del U efectivo de pared, varía con
            v_viento(t) vía h_w McAdams.
        HR_flujo: Serie reconstruida de HR del aire en cámara [adim].
        masa_evaporada_total_kg: ∫ ṁ_w dt sobre toda la simulación [kg].
        Q_rad_W: Serie temporal de potencia radiativa solar absorbida por el
            producto a través del techo translúcido [W]. Q_rad =
            I_g(t)·τ·α·A_rad. Cero en cámaras opacas o sin I_g.
        energia_rad_total_J: ∫ Q_rad dt sobre toda la simulación [J].
            Útil como diagnóstico de aporte solar directo vs convección.
        horas_clipeo_nocturno_s: Tiempo acumulado [s] en que la política B
            anti-rehumectación clipeó dX/dt a 0 porque la fuerza motriz se
            invirtió (ω_sup < ω_ent → tendencia a condensación).
        horas_HR_alta_s: Tiempo acumulado [s] en que HR_flujo > 0.95
            (riesgo de saturación del aire en cámara).
        T_max_alcanzada_K: Máxima T_prod registrada en toda la trayectoria [K].
        advertencias: Lista de códigos/mensajes (ver core/advertencias.py).
    """

    t_secado_s: float | None
    status: str
    t_array_s: np.ndarray
    T_prod_K: np.ndarray
    X_prod_kg_kg: np.ndarray
    T_flujo_K: np.ndarray
    omega_flujo_kg_kg: np.ndarray
    m_dot_w_kg_s: np.ndarray
    q_prod_W: np.ndarray
    q_pared_W: np.ndarray
    T_cam_int_K: np.ndarray
    T_cam_ext_K: np.ndarray
    U_pared_W_m2K: np.ndarray
    HR_flujo: np.ndarray
    masa_evaporada_total_kg: float
    Q_rad_W: np.ndarray = field(default_factory=lambda: np.array([]))
    energia_rad_total_J: float = 0.0
    horas_clipeo_nocturno_s: float = 0.0
    horas_HR_alta_s: float = 0.0
    T_max_alcanzada_K: float = 0.0
    advertencias: list[str] = field(default_factory=list)


def simular_secado(
    *,
    # Estado inicial y objetivo del producto
    T_prod_inicial_K: float,
    X_prod_inicial_kg_kg: float,
    X_prod_objetivo_kg_kg: float,
    # Propiedades del producto
    m_seco_prod_kg: float,
    c_ps_J_kgK: float,
    # Boundary del aire — serie horaria de forzantes (T_ent, ω_ent, ṁ, T_amb, v_viento)
    forzantes: ForzantesAire,
    # Geometría de cámara
    A_prod_m2: float,
    A_cuerpo_m2: float,
    # Aire en cámara — coeficientes de transporte interior.
    # Por defecto se usan estos escalares (congelados, opción ii §24.10). Si se
    # provee coef_transporte_func, se recalculan por paso (ver más abajo).
    h_conv_W_m2K: float,
    K_m_kg_m2s: float,
    # Paredes — geometría (h_w se calcula del v_viento del forzante)
    k_aisl_W_mK: float,
    esp_cam_m: float,
    P_Pa: float,
    # Isoterma del producto
    aw_func: Callable[[float], float],
    # Coeficientes de transporte interior variables en el tiempo (opcional).
    # Firma: (T_ent_K, T_prod_K, omega_ent, m_dot_as) -> (h_conv, K_m_base).
    # Si None, se usan los escalares h_conv_W_m2K / K_m_kg_m2s (congelados).
    coef_transporte_func: Callable[[float, float, float, float], tuple[float, float]] | None = None,
    # Radiación solar directa al producto (techo translúcido).
    # Q_rad(t) = I_g(t)·τ·α·A_rad. Defaults 0 → cámara opaca, sin término radiativo.
    tau_cubierta_solar: float = 0.0,
    alfa_producto_solar: float = 0.6,
    A_rad_m2: float = 0.0,
    # Límite térmico del producto (None → sin evento de daño)
    T_max_admisible_K: float | None = None,
    # Solver
    t_max_s: float | None = None,
    rtol: float = 1e-6,
    atol: float = 1e-9,
) -> ResultadoMotorTermodinamico:
    """Integra el secado del producto con `scipy.integrate.solve_ivp`.

    Sistema de EDOs (estado y = [T_prod, X_prod]):
        m_seco·(c_ps + c_pa·X)·dT_prod/dt = q_prod − ṁ_w · L_v(T_prod)
        dX_prod/dt = − ṁ_w / m_seco_prod

    El cp del producto se calcula dinámicamente en cada paso como
    suma de sólido seco + agua ligada: c_pa·X·M_s + c_ps·M_s. Esto es
    matemáticamente equivalente a usar cp_efectivo = (c_ps+c_pa·X)/(1+X)
    multiplicado por m_prod = m_seco·(1+X), pero se evita el doble
    cómputo factorizando m_seco·(c_ps + c_pa·X) directamente.

    Forzantes horarias: T_ent, ω_ent, ṁ_as, T_amb, v_viento se interpolan
    linealmente en cada evaluación del RHS desde `forzantes`. El coeficiente
    convectivo exterior h_w se recalcula cada paso por McAdams desde el
    v_viento(t). Los coeficientes interiores h_conv y K_m se recalculan por
    paso vía `coef_transporte_func(T_ent(t), T_prod(t), ω_ent(t), ṁ(t))` cuando
    se provee (la película usa T_ent + T_prod, ambas conocidas al evaluar el
    RHS, por lo que no se rompe la linealidad del sistema algebraico dentro del
    paso); si es None, quedan congelados en h_conv_W_m2K / K_m_kg_m2s
    (comportamiento histórico, opción ii §24.10).

    Política B anti-rehumectación: si la solución algebraica daría ṁ_w < 0
    (condensación neta sobre el producto, fuerza motriz invertida), se
    fuerza dX/dt = 0 y se reresuelve T_flujo con K_m=0 (sin evaporación).
    El tiempo acumulado bajo este régimen se reporta en horas_clipeo_nocturno_s.

    Event detection: la integración termina cuando X_prod cruza X_objetivo
    desde arriba (direction=-1, terminal=True). Si T_max_admisible_K está
    definido, también termina si T_prod cruza ese umbral (status='dano_termico').

    Returns:
        ResultadoMotorTermodinamico con t_secado_s, status, series temporales
        completas (incluyendo T_cam_int, T_cam_ext, U_pared, HR_flujo) y
        diagnósticos (horas_clipeo, horas_HR_alta, T_max_alcanzada).

    Raises:
        ValueError: Para parámetros físicamente inválidos (m_seco ≤ 0,
            c_ps ≤ 0, T_inicial ≤ 0, X_obj < 0, t_max ≤ 0).
    """
    # --- Validación de inputs propios del motor ---
    if m_seco_prod_kg <= 0:
        raise ValueError(
            f"MOTOR_TD_M_SECO_NO_POSITIVA: m_seco={m_seco_prod_kg:.3f} kg ≤ 0."
        )
    if c_ps_J_kgK <= 0:
        raise ValueError(
            f"MOTOR_TD_CP_PROD_NO_POSITIVA: c_ps={c_ps_J_kgK:.1f} "
            "J/(kg·K) ≤ 0."
        )
    if T_prod_inicial_K <= 0:
        raise ValueError(
            f"MOTOR_TD_T_INICIAL_NO_POSITIVA: T_inicial={T_prod_inicial_K:.2f} K ≤ 0."
        )
    if X_prod_inicial_kg_kg < 0:
        raise ValueError(
            f"MOTOR_TD_X_INICIAL_NEGATIVA: X_inicial={X_prod_inicial_kg_kg:.4f} < 0."
        )
    if X_prod_objetivo_kg_kg < 0:
        raise ValueError(
            f"MOTOR_TD_X_OBJ_NEGATIVA: X_obj={X_prod_objetivo_kg_kg:.4f} < 0."
        )
    # Determinar horizonte
    t_max_forz = float(forzantes.t_s[-1])
    if t_max_s is None:
        t_max_s_eff = t_max_forz
    else:
        if t_max_s <= 0:
            raise ValueError(
                f"MOTOR_TD_T_MAX_NO_POSITIVO: t_max={t_max_s:.1f} s ≤ 0."
            )
        t_max_s_eff = min(float(t_max_s), t_max_forz)

    advertencias: list[str] = []

    # --- Interpoladores de forzantes ---
    t_fz = np.asarray(forzantes.t_s, dtype=float)
    T_ent_fz = np.asarray(forzantes.T_ent_K, dtype=float)
    omega_ent_fz = np.asarray(forzantes.omega_ent, dtype=float)
    m_dot_fz = np.asarray(forzantes.m_dot_aire_seco_kg_s, dtype=float)
    T_amb_fz = np.asarray(forzantes.T_amb_K, dtype=float)
    v_viento_fz = np.asarray(forzantes.v_viento_ms, dtype=float)
    I_g_fz = np.asarray(forzantes.I_g_W_m2, dtype=float)

    # Factor radiativo precalculado: Q_rad(t) = factor · I_g(t).
    # Si τ=0 o A_rad=0, el factor es 0 y el término desaparece sin coste.
    _Q_rad_factor = tau_cubierta_solar * alfa_producto_solar * A_rad_m2

    def _interp(arr: np.ndarray, t: float) -> float:
        t_clip = max(t_fz[0], min(t_fz[-1], t))
        return float(np.interp(t_clip, t_fz, arr))

    def _boundary_t(t: float) -> tuple[float, float, float, float, float]:
        """Devuelve (T_ent, ω_ent, ṁ_as, T_amb, h_w) interpolados a t."""
        T_ent = _interp(T_ent_fz, t)
        omega_ent = _interp(omega_ent_fz, t)
        m_dot = _interp(m_dot_fz, t)
        T_amb = _interp(T_amb_fz, t)
        v_w = _interp(v_viento_fz, t)
        h_w = 5.7 + 3.8 * v_w   # McAdams
        return T_ent, omega_ent, m_dot, T_amb, h_w

    def _Q_rad_t(t: float) -> float:
        """Potencia radiativa absorbida por el producto a tiempo t [W]."""
        if _Q_rad_factor == 0.0:
            return 0.0
        I_g = max(0.0, _interp(I_g_fz, t))
        return _Q_rad_factor * I_g

    # --- Caso degenerado: producto ya está seco ---
    if X_prod_inicial_kg_kg <= X_prod_objetivo_kg_kg:
        T_ent_0, omega_ent_0, _, _, _ = _boundary_t(0.0)
        return ResultadoMotorTermodinamico(
            t_secado_s=0.0,
            status="X_inicial_ya_seco",
            t_array_s=np.array([0.0]),
            T_prod_K=np.array([T_prod_inicial_K]),
            X_prod_kg_kg=np.array([X_prod_inicial_kg_kg]),
            T_flujo_K=np.array([T_ent_0]),
            omega_flujo_kg_kg=np.array([omega_ent_0]),
            m_dot_w_kg_s=np.array([0.0]),
            q_prod_W=np.array([0.0]),
            q_pared_W=np.array([0.0]),
            T_cam_int_K=np.array([T_ent_0]),
            T_cam_ext_K=np.array([_boundary_t(0.0)[3]]),
            U_pared_W_m2K=np.array([0.0]),
            HR_flujo=np.array([0.0]),
            masa_evaporada_total_kg=0.0,
            T_max_alcanzada_K=float(T_prod_inicial_K),
            advertencias=[
                "MOTOR_TD_X_INICIAL_YA_SECO: el producto ya está por debajo "
                f"del objetivo (X_ini={X_prod_inicial_kg_kg:.4f} ≤ "
                f"X_obj={X_prod_objetivo_kg_kg:.4f})."
            ],
        )

    # --- Closure: resolver con boundary interpolado ---
    # Los coeficientes interiores (h_conv, K_m) se evalúan por paso desde el
    # estado del aire si hay coef_transporte_func; si no, se usan los escalares
    # congelados. K_m_override=0.0 lo usa la política B (sin evaporación).
    def _resolver(
        T_prod: float, X_prod: float, t: float, K_m_override: float | None = None
    ) -> EstadoCamara:
        X_safe = max(X_prod, 0.0)
        T_ent, omega_ent, m_dot, T_amb, h_w = _boundary_t(t)
        if coef_transporte_func is not None:
            h_conv_local, K_m_base = coef_transporte_func(T_ent, T_prod, omega_ent, m_dot)
        else:
            h_conv_local, K_m_base = h_conv_W_m2K, K_m_kg_m2s
        K_m_usado = K_m_override if K_m_override is not None else K_m_base
        return resolver_estado_camara(
            T_prod_K=T_prod,
            X_prod_kg_kg=X_safe,
            T_ent_K=T_ent,
            omega_ent_kg_kg=omega_ent,
            A_prod_m2=A_prod_m2,
            A_cuerpo_m2=A_cuerpo_m2,
            m_dot_as_kg_s=m_dot,
            h_conv_W_m2K=h_conv_local,
            K_m_kg_m2s=K_m_usado,
            h_w_W_m2K=h_w,
            k_aisl_W_mK=k_aisl_W_mK,
            esp_cam_m=esp_cam_m,
            T_amb_K=T_amb,
            P_Pa=P_Pa,
            aw_func=aw_func,
        )

    # --- Estado mutable para diagnóstico de política B y HR alta ---
    diag = {
        "t_anterior": 0.0,
        "horas_clipeo_s": 0.0,
        "horas_hr_alta_s": 0.0,
    }

    def _resolver_con_politica_B(
        T_prod: float, X_prod: float, t: float
    ) -> tuple[EstadoCamara, bool]:
        """Aplica política B: si daría condensación, re-resuelve con K_m=0.

        Returns:
            (EstadoCamara final, clipeado_flag).
        """
        est = _resolver(T_prod, X_prod, t)
        if est.m_dot_w_kg_s < 0.0:
            est_clip = _resolver(T_prod, X_prod, t, K_m_override=0.0)
            return est_clip, True
        return est, False

    # --- RHS del sistema EDO ---
    def _rhs(t: float, y: np.ndarray) -> list[float]:
        T_prod, X_prod = y[0], y[1]
        est, clipeado = _resolver_con_politica_B(T_prod, X_prod, t)

        # Capacidad térmica dinámica: m_seco·(c_ps + c_pa·X)
        X_safe = max(X_prod, 0.0)
        C_thermal = m_seco_prod_kg * (c_ps_J_kgK + _CP_AGUA_LIQ_J_KGK * X_safe)
        # Clamp defensivo: solve_ivp puede tantear T fuera del rango físico
        # durante steps tentativos. Limitamos a [250, 373] K para que las
        # funciones psicrométricas no rompan; el solver luego rechaza el step
        # si la solución no converge.
        T_prod_safe = min(373.0, max(250.0, T_prod))
        L_v_prod = calor_latente_vaporizacion(T_prod_safe)
        Q_rad = _Q_rad_t(t)
        dT_dt = (est.q_prod_W + Q_rad - est.m_dot_w_kg_s * L_v_prod) / C_thermal
        dX_dt = -est.m_dot_w_kg_s / m_seco_prod_kg

        # Tracking aproximado del tiempo bajo cada régimen
        dt_paso = max(0.0, t - diag["t_anterior"])
        if clipeado:
            diag["horas_clipeo_s"] += dt_paso
        # HR alta del flujo
        try:
            T_ent_t, _, _, _, _ = _boundary_t(t)
            HR_f = HR_desde_omega(est.omega_flujo_kg_kg, est.T_flujo_K, P_Pa)
            if HR_f > _HR_SAT_UMBRAL:
                diag["horas_hr_alta_s"] += dt_paso
        except (ZeroDivisionError, ValueError):
            pass
        diag["t_anterior"] = t

        return [dT_dt, dX_dt]

    # --- Eventos ---
    def _event_X_obj(t: float, y: np.ndarray) -> float:
        return y[1] - X_prod_objetivo_kg_kg

    _event_X_obj.terminal = True
    _event_X_obj.direction = -1.0

    eventos: list = [_event_X_obj]

    if T_max_admisible_K is not None:
        def _event_T_max(t: float, y: np.ndarray) -> float:
            return y[0] - float(T_max_admisible_K)

        _event_T_max.terminal = True
        _event_T_max.direction = 1.0
        eventos.append(_event_T_max)

    # --- Integración ---
    sol = solve_ivp(
        _rhs,
        t_span=(0.0, t_max_s_eff),
        y0=[T_prod_inicial_K, X_prod_inicial_kg_kg],
        events=eventos,
        method="LSODA",
        rtol=rtol,
        atol=atol,
        dense_output=False,
        max_step=3600.0,  # evita saltar tramos enteros entre forzantes horarias
    )

    if not sol.success:
        return ResultadoMotorTermodinamico(
            t_secado_s=None,
            status="error",
            t_array_s=sol.t,
            T_prod_K=sol.y[0],
            X_prod_kg_kg=sol.y[1],
            T_flujo_K=np.array([]),
            omega_flujo_kg_kg=np.array([]),
            m_dot_w_kg_s=np.array([]),
            q_prod_W=np.array([]),
            q_pared_W=np.array([]),
            T_cam_int_K=np.array([]),
            T_cam_ext_K=np.array([]),
            U_pared_W_m2K=np.array([]),
            HR_flujo=np.array([]),
            masa_evaporada_total_kg=0.0,
            advertencias=[f"MOTOR_TD_SOLVE_IVP_FALLO: {sol.message}"],
        )

    # --- Determinar status y t_secado ---
    eventos_X_obj_t = sol.t_events[0] if len(sol.t_events) > 0 else np.array([])
    eventos_T_max_t = (
        sol.t_events[1] if (T_max_admisible_K is not None and len(sol.t_events) > 1)
        else np.array([])
    )

    if len(eventos_T_max_t) > 0:
        t_secado = None
        status = "dano_termico"
        advertencias.append(
            f"MOTOR_TD_DANO_TERMICO: T_prod alcanzó T_max="
            f"{T_max_admisible_K - 273.15:.1f} °C a t={float(eventos_T_max_t[0]):.0f} s. "
            "El secado se detuvo para evitar daño al producto."
        )
    elif len(eventos_X_obj_t) > 0:
        t_secado = float(eventos_X_obj_t[0])
        status = "X_obj_alcanzado"
    else:
        t_secado = None
        status = "t_max_alcanzado"
        advertencias.append(
            f"MOTOR_TD_T_MAX_ALCANZADO: el producto no alcanzó X_obj="
            f"{X_prod_objetivo_kg_kg:.4f} dentro de t_max={t_max_s_eff:.0f} s. "
            f"X final = {sol.y[1, -1]:.4f}."
        )

    # --- Reconstrucción de variables algebraicas en cada t guardado ---
    n = len(sol.t)
    T_flujo_arr = np.zeros(n)
    omega_flujo_arr = np.zeros(n)
    m_dot_w_arr = np.zeros(n)
    q_prod_arr = np.zeros(n)
    q_pared_arr = np.zeros(n)
    T_cam_int_arr = np.zeros(n)
    T_cam_ext_arr = np.zeros(n)
    U_pared_arr = np.zeros(n)
    HR_flujo_arr = np.zeros(n)
    Q_rad_arr = np.zeros(n)
    for i in range(n):
        t_i = float(sol.t[i])
        est, _ = _resolver_con_politica_B(sol.y[0, i], sol.y[1, i], t_i)
        T_flujo_arr[i] = est.T_flujo_K
        omega_flujo_arr[i] = est.omega_flujo_kg_kg
        m_dot_w_arr[i] = est.m_dot_w_kg_s
        q_prod_arr[i] = est.q_prod_W
        q_pared_arr[i] = est.q_pared_W
        T_cam_int_arr[i] = est.T_cam_int_K
        T_cam_ext_arr[i] = est.T_cam_ext_K
        U_pared_arr[i] = est.U_pared_W_m2K
        Q_rad_arr[i] = _Q_rad_t(t_i)
        try:
            HR_flujo_arr[i] = HR_desde_omega(est.omega_flujo_kg_kg, est.T_flujo_K, P_Pa)
        except (ZeroDivisionError, ValueError):
            HR_flujo_arr[i] = float("nan")

    # --- Masa evaporada total: ∫ ṁ_w dt (regla del trapecio) ---
    if n >= 2:
        # Sólo cuenta los aportes positivos (evaporación) — los negativos
        # corresponden al estado pre-clipeo de política B y no representan
        # masa que efectivamente cambió en el producto.
        m_dot_pos = np.clip(m_dot_w_arr, 0.0, None)
        masa_evap = float(np.trapezoid(m_dot_pos, sol.t))
        energia_rad = float(np.trapezoid(Q_rad_arr, sol.t))
    else:
        masa_evap = 0.0
        energia_rad = 0.0

    # Diagnósticos
    horas_clipeo = float(diag["horas_clipeo_s"])
    horas_hr_alta = float(diag["horas_hr_alta_s"])
    if horas_clipeo > 3.0 * 3600.0:
        advertencias.append(
            f"CAM_NOCHE_RIESGO_REHUMECTACION: {horas_clipeo / 3600.0:.1f} h con "
            "dX/dt clipeado por política B (≥ 3 h). El emplazamiento puede "
            "requerir cierre nocturno."
        )
    if horas_hr_alta > 0:
        advertencias.append(
            f"CAM_HR_FLUJO_ALTA: HR del aire en cámara > 95 % durante "
            f"{horas_hr_alta / 3600.0:.1f} h. Riesgo de saturación, considerar "
            "aumentar caudal o reducir la carga."
        )

    return ResultadoMotorTermodinamico(
        t_secado_s=t_secado,
        status=status,
        t_array_s=sol.t,
        T_prod_K=sol.y[0],
        X_prod_kg_kg=sol.y[1],
        T_flujo_K=T_flujo_arr,
        omega_flujo_kg_kg=omega_flujo_arr,
        m_dot_w_kg_s=m_dot_w_arr,
        q_prod_W=q_prod_arr,
        q_pared_W=q_pared_arr,
        T_cam_int_K=T_cam_int_arr,
        T_cam_ext_K=T_cam_ext_arr,
        U_pared_W_m2K=U_pared_arr,
        HR_flujo=HR_flujo_arr,
        masa_evaporada_total_kg=masa_evap,
        Q_rad_W=Q_rad_arr,
        energia_rad_total_J=energia_rad,
        horas_clipeo_nocturno_s=horas_clipeo,
        horas_HR_alta_s=horas_hr_alta,
        T_max_alcanzada_K=float(np.max(sol.y[0])) if n > 0 else float(T_prod_inicial_K),
        advertencias=advertencias,
    )
