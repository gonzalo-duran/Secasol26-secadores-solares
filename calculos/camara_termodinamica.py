"""
Solver algebraico de cámara — motor termodinámico transitorio (S2).

Resuelve el sistema acoplado de 4 ecuaciones para las variables algebraicas
(T_flujo, ω_flujo, T_cam_int, T_cam_ext) dado el estado del producto
(T_prod, X_prod) y las condiciones de boundary (T_ent, ω_ent, T_amb).

Hipótesis:
- CSTR (mezcla perfecta): aire en cámara uniforme a (T_flujo, ω_flujo).
- Cuasi-estacionario en aire (residencia << tiempo de secado).
- Paredes: U_muros global (cascada h_int + k/e + h_w colapsada).
- Cinética de evaporación difusiva: ṁ_w = K_m · A_prod · (ω_sup − ω_flujo),
  con K_m la conductancia másica [kg/(m²·s)] y ω_sup = ω_sat(T_prod)·a_w(X_prod).

Resolución analítica directa (sin iteración interna), aprovechando la
linealidad de las 4 ecuaciones cuando se fijan h_conv, K_m al inicio del paso:
    1. ω_sup = ω_sat(T_prod) · a_w(X_prod)
    2. (a) lineal en ω_flujo  → ω_flujo directo
    3. ṁ_w = ṁ_as · (ω_flujo − ω_ent)
    4. (b) lineal en T_flujo  → T_flujo directo

Referencias:
    - Bitácora Sesión 20 §24.3 (sistema de ecuaciones).
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
    calor_latente_vaporizacion,
    cp_aire_humedo,
    entalpia_aire_humedo,
    omega_saturacion,
)


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
    """

    T_flujo_K: float
    omega_flujo_kg_kg: float
    m_dot_w_kg_s: float
    q_prod_W: float
    q_pared_W: float


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
    U_muros_W_m2K: float,
    T_amb_K: float,
    P_Pa: float,
    aw_func: Callable[[float], float],
) -> EstadoCamara:
    """Resuelve el sistema algebraico de cámara (CSTR, cuasi-estacionario).

    Sistema de 4 ecuaciones:
        (a) Balance de masa del aire:
            ṁ_as·(ω_flujo − ω_ent) = K_m·A_prod·(ω_sup − ω_flujo)
        (b) Balance de energía del aire (entalpía):
            ṁ_as·[h(T_flujo, ω_flujo) − h(T_ent, ω_ent)]
              = − U·A_cuerpo·(T_flujo − T_amb)
                − h_conv·A_prod·(T_flujo − T_prod)
                + ṁ_w · h_v(T_prod)
            El último término es POSITIVO: el vapor sale del producto a
            T_prod y se incorpora al aire llevando su entalpía h_v(T_prod).
        (c)+(d) colapsadas en U_muros (T_cam_int/ext no se reportan en v0).

    Resolución analítica directa, sin iteración. Costo: O(1) por llamada.

    Args:
        T_prod_K: Temperatura del producto [K] (estado).
        X_prod_kg_kg: Humedad del producto [kg_agua/kg_seco] (estado).
        T_ent_K: Temperatura del aire de entrada [K] (boundary).
        omega_ent_kg_kg: Humedad absoluta del aire de entrada [kg/kg_as].
        A_prod_m2: Área de transferencia con el producto [m²].
        A_cuerpo_m2: Área de paredes externas [m²].
        m_dot_as_kg_s: Caudal másico de aire seco [kg/s].
        h_conv_W_m2K: Coeficiente convectivo aire→producto y aire→pared
            [W/(m²·K)].
        K_m_kg_m2s: Conductancia másica = ρ·h_m_chilton [kg/(m²·s)].
            El llamador computa esto multiplicando h_m_chilton (m/s) por
            la densidad del aire húmedo evaluada a una T de referencia.
        U_muros_W_m2K: Coeficiente global de transmisión por paredes
            [W/(m²·K)] (cascada h_int + k/e + h_w colapsada).
        T_amb_K: Temperatura ambiente externa [K].
        P_Pa: Presión total [Pa].
        aw_func: Función X → a_w (típicamente inversión GAB).

    Returns:
        EstadoCamara con T_flujo, ω_flujo, ṁ_w, q_prod, q_pared.

    Raises:
        ValueError: Si ṁ_as ≤ 0, A_prod < 0, A_cuerpo < 0, h_conv < 0,
            K_m < 0, U_muros < 0, o P_Pa ≤ 0.
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
    if U_muros_W_m2K < 0:
        raise ValueError(
            f"CAM_TD_U_MUROS_NEGATIVO: U={U_muros_W_m2K:.3f} W/(m²·K) < 0."
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

    # --- 4) Resolución de (b) — lineal en T_flujo ---
    # h(T, ω) = cp_hum(ω)·(T − T_ref) + ω·L_v0  (forma usada por
    # entalpia_aire_humedo) → lineal en T para ω fijo.
    cp_hum_flujo = cp_aire_humedo(omega_flujo)
    h_ent = entalpia_aire_humedo(T_ent_K, omega_ent_kg_kg)

    # Entalpía del vapor que sale del producto a T_prod, consistente con la
    # convención de entalpía de aire húmedo (referencia T_ref = 273.15 K).
    h_v_prod = _LV_0 + _CP_VAPOR * (T_prod_K - _T_REF)

    UA_c = U_muros_W_m2K * A_cuerpo_m2
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

    return EstadoCamara(
        T_flujo_K=T_flujo,
        omega_flujo_kg_kg=omega_flujo,
        m_dot_w_kg_s=m_dot_w,
        q_prod_W=q_prod,
        q_pared_W=q_pared,
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
            'X_obj_alcanzado' | 't_max_alcanzado' | 'X_inicial_ya_seco' | 'error'.
        t_array_s: Vector de tiempos de la solución [s].
        T_prod_K: Serie temporal de T_prod [K], shape (n,).
        X_prod_kg_kg: Serie temporal de X_prod [kg/kg seco], shape (n,).
        T_flujo_K: Serie reconstruida de T_flujo [K], shape (n,).
        omega_flujo_kg_kg: Serie reconstruida de ω_flujo [kg/kg as], shape (n,).
        m_dot_w_kg_s: Serie reconstruida de tasa de evaporación [kg/s], shape (n,).
        q_prod_W: Serie reconstruida de calor sensible aire→producto [W].
        q_pared_W: Serie reconstruida de pérdida a paredes [W].
        masa_evaporada_total_kg: ∫ ṁ_w dt sobre toda la simulación [kg].
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
    masa_evaporada_total_kg: float
    advertencias: list[str] = field(default_factory=list)


def simular_secado(
    *,
    # Estado inicial y objetivo del producto
    T_prod_inicial_K: float,
    X_prod_inicial_kg_kg: float,
    X_prod_objetivo_kg_kg: float,
    # Propiedades del producto
    m_seco_prod_kg: float,
    cp_prod_J_kgK: float,
    # Boundary del aire (constantes en v0 — extender a callables en v1)
    T_ent_K: float,
    omega_ent_kg_kg: float,
    # Geometría de cámara
    A_prod_m2: float,
    A_cuerpo_m2: float,
    # Aire en cámara
    m_dot_as_kg_s: float,
    h_conv_W_m2K: float,
    K_m_kg_m2s: float,
    # Paredes
    U_muros_W_m2K: float,
    T_amb_K: float,
    P_Pa: float,
    # Isoterma del producto
    aw_func: Callable[[float], float],
    # Solver
    t_max_s: float = 24 * 3600.0,
    rtol: float = 1e-6,
    atol: float = 1e-9,
) -> ResultadoMotorTermodinamico:
    """Integra el secado del producto con `scipy.integrate.solve_ivp`.

    Sistema de EDOs (estado y = [T_prod, X_prod]):
        dT_prod/dt = (q_prod − ṁ_w · L_v(T_prod)) / (m_prod · cp_prod)
        dX_prod/dt = − ṁ_w / m_seco_prod

    donde m_prod(t) = m_seco · (1 + X_prod(t)) y (q_prod, ṁ_w) provienen
    de resolver_estado_camara llamado en cada evaluación del RHS.

    Convención de signos: ṁ_w > 0 indica evaporación (X decrece). ṁ_w < 0
    indica condensación (X aumenta) — caso patológico pero matemáticamente
    válido si el producto está más seco que el aire entrante.

    Hipótesis (opción ii — bitácora §24.10):
        - h_conv y K_m fijos durante toda la simulación. El llamador los
          computa con T_película de referencia. La variación con T es
          débil en el rango operativo (< 5 % entre 30–60 °C).
        - Boundary del aire (T_ent, ω_ent, T_amb) constante. Para acoplar
          con dinámica diaria del colector se debe llamar este motor por
          tramos horarios.

    Event detection: la integración termina cuando X_prod cruza X_objetivo
    desde arriba (direction=-1, terminal=True).

    Returns:
        ResultadoMotorTermodinamico con t_secado_s, status, y series
        temporales de las 5 variables del estado completo + diagnósticos.

    Raises:
        ValueError: Para parámetros físicamente inválidos (m_seco ≤ 0,
            cp_prod ≤ 0, T_inicial ≤ 0, X_obj < 0, t_max ≤ 0).
            La validación de los parámetros geométricos y de propiedades
            del aire delega en `resolver_estado_camara`.
    """
    # --- Validación de inputs propios del motor ---
    if m_seco_prod_kg <= 0:
        raise ValueError(
            f"MOTOR_TD_M_SECO_NO_POSITIVA: m_seco={m_seco_prod_kg:.3f} kg ≤ 0."
        )
    if cp_prod_J_kgK <= 0:
        raise ValueError(
            f"MOTOR_TD_CP_PROD_NO_POSITIVA: cp_prod={cp_prod_J_kgK:.1f} "
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
    if t_max_s <= 0:
        raise ValueError(
            f"MOTOR_TD_T_MAX_NO_POSITIVO: t_max={t_max_s:.1f} s ≤ 0."
        )

    advertencias: list[str] = []

    # --- Caso degenerado: producto ya está seco ---
    if X_prod_inicial_kg_kg <= X_prod_objetivo_kg_kg:
        return ResultadoMotorTermodinamico(
            t_secado_s=0.0,
            status="X_inicial_ya_seco",
            t_array_s=np.array([0.0]),
            T_prod_K=np.array([T_prod_inicial_K]),
            X_prod_kg_kg=np.array([X_prod_inicial_kg_kg]),
            T_flujo_K=np.array([T_ent_K]),
            omega_flujo_kg_kg=np.array([omega_ent_kg_kg]),
            m_dot_w_kg_s=np.array([0.0]),
            q_prod_W=np.array([0.0]),
            q_pared_W=np.array([0.0]),
            masa_evaporada_total_kg=0.0,
            advertencias=[
                "MOTOR_TD_X_INICIAL_YA_SECO: el producto ya está por debajo "
                f"del objetivo (X_ini={X_prod_inicial_kg_kg:.4f} ≤ "
                f"X_obj={X_prod_objetivo_kg_kg:.4f})."
            ],
        )

    # --- Closure: argumentos fijos para resolver_estado_camara ---
    def _resolver(T_prod: float, X_prod: float) -> EstadoCamara:
        # Clip X >= 0 por seguridad numérica (puede ir levemente negativo
        # cerca del fin si el solver overshoot)
        X_safe = max(X_prod, 0.0)
        return resolver_estado_camara(
            T_prod_K=T_prod,
            X_prod_kg_kg=X_safe,
            T_ent_K=T_ent_K,
            omega_ent_kg_kg=omega_ent_kg_kg,
            A_prod_m2=A_prod_m2,
            A_cuerpo_m2=A_cuerpo_m2,
            m_dot_as_kg_s=m_dot_as_kg_s,
            h_conv_W_m2K=h_conv_W_m2K,
            K_m_kg_m2s=K_m_kg_m2s,
            U_muros_W_m2K=U_muros_W_m2K,
            T_amb_K=T_amb_K,
            P_Pa=P_Pa,
            aw_func=aw_func,
        )

    # --- RHS del sistema EDO ---
    def _rhs(t: float, y: np.ndarray) -> list[float]:
        T_prod, X_prod = y[0], y[1]
        est = _resolver(T_prod, X_prod)
        m_prod = m_seco_prod_kg * (1.0 + max(X_prod, 0.0))
        L_v_prod = calor_latente_vaporizacion(T_prod)
        dT_dt = (
            est.q_prod_W - est.m_dot_w_kg_s * L_v_prod
        ) / (m_prod * cp_prod_J_kgK)
        dX_dt = -est.m_dot_w_kg_s / m_seco_prod_kg
        return [dT_dt, dX_dt]

    # --- Event detection: X_prod = X_objetivo (cruzando desde arriba) ---
    def _event_X_obj(t: float, y: np.ndarray) -> float:
        return y[1] - X_prod_objetivo_kg_kg

    _event_X_obj.terminal = True
    _event_X_obj.direction = -1.0

    # --- Integración ---
    sol = solve_ivp(
        _rhs,
        t_span=(0.0, t_max_s),
        y0=[T_prod_inicial_K, X_prod_inicial_kg_kg],
        events=_event_X_obj,
        method="LSODA",   # robusto para sistemas potencialmente stiff
        rtol=rtol,
        atol=atol,
        dense_output=False,
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
            masa_evaporada_total_kg=0.0,
            advertencias=[f"MOTOR_TD_SOLVE_IVP_FALLO: {sol.message}"],
        )

    # --- Determinar status y t_secado ---
    if len(sol.t_events[0]) > 0:
        t_secado = float(sol.t_events[0][0])
        status = "X_obj_alcanzado"
    else:
        t_secado = None
        status = "t_max_alcanzado"
        advertencias.append(
            f"MOTOR_TD_T_MAX_ALCANZADO: el producto no alcanzó X_obj="
            f"{X_prod_objetivo_kg_kg:.4f} dentro de t_max={t_max_s:.0f} s. "
            f"X final = {sol.y[1, -1]:.4f}."
        )

    # --- Reconstrucción de variables algebraicas en cada t guardado ---
    n = len(sol.t)
    T_flujo_arr = np.zeros(n)
    omega_flujo_arr = np.zeros(n)
    m_dot_w_arr = np.zeros(n)
    q_prod_arr = np.zeros(n)
    q_pared_arr = np.zeros(n)
    for i in range(n):
        est = _resolver(sol.y[0, i], sol.y[1, i])
        T_flujo_arr[i] = est.T_flujo_K
        omega_flujo_arr[i] = est.omega_flujo_kg_kg
        m_dot_w_arr[i] = est.m_dot_w_kg_s
        q_prod_arr[i] = est.q_prod_W
        q_pared_arr[i] = est.q_pared_W

    # --- Masa evaporada total: ∫ ṁ_w dt (regla del trapecio) ---
    if n >= 2:
        masa_evap = float(np.trapezoid(m_dot_w_arr, sol.t))
    else:
        masa_evap = 0.0

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
        masa_evaporada_total_kg=masa_evap,
        advertencias=advertencias,
    )
