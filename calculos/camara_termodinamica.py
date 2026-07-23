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
    presion_vapor_saturacion,
)
from core.camara import ForzantesAire

# Constantes físicas
_CP_AGUA_LIQ_J_KGK: float = 4186.0  # cp del agua líquida (para cp_prod variable)
_HR_SAT_UMBRAL: float = 0.95  # umbral para advertencia HR_flujo alta
_MAX_STEP_TOPE_S: float = 3600.0  # tope del paso del integrador (nodos horarios)

# Tope de la presión de vapor de saturación como fracción de la presión total.
# A presión reducida el agua hierve por debajo de 100 °C (a 2650 m, ~73 kPa,
# hierve a 91 °C) y ``P_sat(T) → P`` hace divergir ω_sat: la humedad de
# saturación no está definida por encima de la ebullición. Ver
# :func:`_omega_saturacion_acotada`.
_FRAC_P_SAT_MAX: float = 0.90


def _omega_saturacion_acotada(T_K: float, P_Pa: float) -> float:
    """ω de saturación con la presión de vapor topeada a una fracción de P.

    **Por qué existe.** ``omega_saturacion`` lanza ``PSICRO_PV_EXCEDE_P`` cuando
    ``P_sat(T) ≥ P`` — correctamente, porque ahí el agua hierve y la saturación
    deja de ser el mecanismo que gobierna. Pero eso abortaba la simulación
    entera cuando el producto se acercaba a la ebullición local, cosa que pasa
    en sitios de altura con aire de entrada muy caliente (reportado por el
    usuario en S57: sitio a 73 kPa, aire a 92.8 °C, ebullición a 91.1 °C).

    **Qué hace.** Topea ``P_sat`` a ``_FRAC_P_SAT_MAX·P``, lo que acota ω_sat a
    un valor grande pero finito (~5.6 kg/kg contra los ~0.05 típicos) y deja que
    el balance acoplado responda: una evaporación enorme enfría el producto y lo
    devuelve por debajo de la ebullición.

    **Qué NO hace.** No modela el hervor. El tope es arbitrario y en ese régimen
    los resultados **no son confiables**: si el producto llega ahí, el problema
    es de diseño (colector sobredimensionado para el caudal), no de numérica —
    y además ninguna fruta se seca sana a esa temperatura. ``simular_secado``
    emite ``CAM_TD_SOBRE_EBULLICION`` cuando el tope se activa.

    Args:
        T_K: Temperatura [K].
        P_Pa: Presión total [Pa].

    Returns:
        ω_sat [kg_agua/kg_aire_seco], siempre finito.
    """
    P_sat = min(presion_vapor_saturacion(T_K), _FRAC_P_SAT_MAX * P_Pa)
    return 0.622 * P_sat / (P_Pa - P_sat)


def _max_step_desde_forzantes(t_fz: np.ndarray) -> float:
    """Paso máximo del integrador desde el espaciado de las forzantes (fase 1b).

    El RHS interpola las forzantes linealmente entre nodos; el integrador no debe
    dar zancadas que salteen nodos (perdería la curvatura sub-horaria). Se usa la
    mediana de los saltos positivos, acotada a ``_MAX_STEP_TOPE_S`` para preservar
    el comportamiento histórico con forzantes horarias.

    Args:
        t_fz: Vector de tiempos de las forzantes [s].

    Returns:
        Paso máximo [s]: ``min(3600, mediana(diff(t_fz)))`` (o el tope si <2 nodos).
    """
    if t_fz.size < 2:
        return _MAX_STEP_TOPE_S
    diffs = np.diff(t_fz)
    diffs = diffs[diffs > 0.0]
    if diffs.size == 0:
        return _MAX_STEP_TOPE_S
    return float(min(_MAX_STEP_TOPE_S, np.median(diffs)))


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
    R_cond_techo_m2K_W: float = 0.0,
    A_techo_m2: float = 0.0,
    Q_rad_aire_W: float = 0.0,
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
        R_cond_techo_m2K_W: Resistencia conductiva del techo translúcido
            (vidriado) = espesor / k_efectivo [m²·K/W]. Default 0 → sin techo
            translúcido (la cara del techo ya está en A_cuerpo como opaca).
        A_techo_m2: Área del techo translúcido [m²]. Default 0 → techo opaco.
            Cuando > 0, suma al balance una pérdida UA_techo = A_techo /
            (1/h_conv + R_cond_techo + 1/h_w), sin afectar la reconstrucción
            de los nodos de la pared opaca.
        Q_rad_aire_W: Potencia radiativa que calienta el aire directamente
            (radiación transmitida por las caras translúcidas que no
            intercepta el producto y calienta paredes/piso internos — efecto
            invernadero de la caja). Default 0.0 → sin efecto, back-compat
            exacta con el balance histórico. Ver ``calculos/radiacion_camara.py``.

    Returns:
        EstadoCamara con T_flujo, ω_flujo, ṁ_w, q_prod, q_pared, T_cam_int,
        T_cam_ext y U_pared.

    Raises:
        ValueError: Si ṁ_as ≤ 0, A_prod < 0, A_cuerpo < 0, h_conv < 0,
            K_m < 0, h_w < 0, k_aisl < 0, esp_cam ≤ 0, o P_Pa ≤ 0.
    """
    # --- Validación dura ---
    if m_dot_as_kg_s <= 0:
        raise ValueError(f"CAM_TD_M_DOT_NO_POSITIVO: ṁ_as={m_dot_as_kg_s:.4f} kg/s ≤ 0.")
    if A_prod_m2 < 0:
        raise ValueError(f"CAM_TD_A_PROD_NEGATIVA: A_prod={A_prod_m2:.3f} m² < 0.")
    if A_cuerpo_m2 < 0:
        raise ValueError(f"CAM_TD_A_CUERPO_NEGATIVA: A_cuerpo={A_cuerpo_m2:.3f} m² < 0.")
    if h_conv_W_m2K < 0:
        raise ValueError(f"CAM_TD_H_CONV_NEGATIVO: h_conv={h_conv_W_m2K:.2f} W/(m²·K) < 0.")
    if K_m_kg_m2s < 0:
        raise ValueError(f"CAM_TD_KM_NEGATIVO: K_m={K_m_kg_m2s:.4f} kg/(m²·s) < 0.")
    if h_w_W_m2K < 0:
        raise ValueError(f"CAM_TD_H_W_NEGATIVO: h_w={h_w_W_m2K:.2f} W/(m²·K) < 0.")
    if k_aisl_W_mK < 0:
        raise ValueError(f"CAM_TD_K_AISL_NEGATIVA: k_aisl={k_aisl_W_mK:.4f} W/(m·K) < 0.")
    if esp_cam_m <= 0:
        raise ValueError(f"CAM_TD_ESP_CAM_NO_POSITIVO: esp_cam={esp_cam_m:.4f} m ≤ 0.")
    if P_Pa <= 0:
        raise ValueError(f"CAM_TD_P_NO_POSITIVA: P={P_Pa:.1f} Pa ≤ 0.")

    # --- 1) Humedad absoluta de superficie del producto ---
    omega_sat_prod = _omega_saturacion_acotada(T_prod_K, P_Pa)
    a_w = aw_func(X_prod_kg_kg)
    # Clip por tolerancia numérica de la inversión GAB (puede dar a_w ≈ 1+ε).
    a_w_clipped = max(0.0, min(1.0, a_w))
    omega_sup = omega_sat_prod * a_w_clipped

    # --- 2) Resolución de (a) — lineal en ω_flujo ---
    # ṁ_as·(ω_flujo − ω_ent) = K_A·(ω_sup − ω_flujo)
    # ⇒ ω_flujo·(ṁ_as + K_A) = ṁ_as·ω_ent + K_A·ω_sup
    K_A = K_m_kg_m2s * A_prod_m2  # [kg/s]
    omega_flujo = (m_dot_as_kg_s * omega_ent_kg_kg + K_A * omega_sup) / (m_dot_as_kg_s + K_A)

    # --- 3) Caudal de evaporación (signo: + evap, − condensación) ---
    m_dot_w = m_dot_as_kg_s * (omega_flujo - omega_ent_kg_kg)

    # --- 4) Cascada resistiva de pared en 3 nodos ---
    # R_total = 1/h_conv_int + esp_cam/k_aisl + 1/h_w  →  U_total = 1/R_total
    # k_aisl = 0  →  R_cond = ∞  →  U_total = 0  (pared aislante perfecta).
    # h_conv_int = 0 o h_w = 0  →  el film correspondiente domina (R_total = ∞).
    if k_aisl_W_mK == 0.0 or h_conv_W_m2K == 0.0 or h_w_W_m2K == 0.0:
        U_total = 0.0
    else:
        R_total = 1.0 / h_conv_W_m2K + esp_cam_m / k_aisl_W_mK + 1.0 / h_w_W_m2K
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

    # Pérdida conductiva del techo translúcido (vidriado): U_techo en serie con
    # los mismos films interior (h_conv) y exterior (h_w McAdams) que la pared.
    # A_techo=0 (techo opaco, ya contado en A_cuerpo) → UA_techo=0, sin efecto.
    if A_techo_m2 > 0.0 and R_cond_techo_m2K_W > 0.0 and h_conv_W_m2K > 0.0 and h_w_W_m2K > 0.0:
        U_techo = 1.0 / (1.0 / h_conv_W_m2K + R_cond_techo_m2K_W + 1.0 / h_w_W_m2K)
        UA_techo = U_techo * A_techo_m2
    else:
        UA_techo = 0.0
    # Pérdida total al ambiente (pared opaca + techo vidriado) en el balance.
    UA_loss = UA_c + UA_techo

    numerador = (
        m_dot_as_kg_s * cp_hum_flujo * _T_REF
        + m_dot_as_kg_s * (h_ent - omega_flujo * _LV_0)
        + UA_loss * T_amb_K
        + hA_p * T_prod_K
        + m_dot_w * h_v_prod
        + Q_rad_aire_W
    )
    denominador = m_dot_as_kg_s * cp_hum_flujo + UA_loss + hA_p
    T_flujo = numerador / denominador

    # --- Diagnósticos ---
    # q_pared = flujo por la pared OPACA (reconstruye los nodos T_cam_int/ext con
    # la geometría opaca). La pérdida del techo entra al balance vía UA_loss pero
    # no a esta reconstrucción.
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
        Q_rad_aire_W: Serie temporal de potencia radiativa que calienta el
            aire vía superficies internas (radiación transmitida por caras
            translúcidas que no intercepta el producto). Cero por defecto
            (``forzantes.Q_rad_aire_W is None`` o cámara sin caras
            translúcidas adicionales al techo — ver
            ``calculos/radiacion_camara.py``).
        energia_rad_aire_total_J: ∫ Q_rad_aire dt sobre toda la simulación [J].
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
    Q_rad_aire_W: np.ndarray = field(default_factory=lambda: np.array([]))
    energia_rad_aire_total_J: float = 0.0
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
    # Pérdida conductiva del techo translúcido (vidriado). Defaults 0 → techo
    # opaco (su cara ya está contada en A_cuerpo_m2 como pared opaca).
    R_cond_techo_m2K_W: float = 0.0,
    A_techo_m2: float = 0.0,
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
        raise ValueError(f"MOTOR_TD_M_SECO_NO_POSITIVA: m_seco={m_seco_prod_kg:.3f} kg ≤ 0.")
    if c_ps_J_kgK <= 0:
        raise ValueError(f"MOTOR_TD_CP_PROD_NO_POSITIVA: c_ps={c_ps_J_kgK:.1f} " "J/(kg·K) ≤ 0.")
    if T_prod_inicial_K <= 0:
        raise ValueError(f"MOTOR_TD_T_INICIAL_NO_POSITIVA: T_inicial={T_prod_inicial_K:.2f} K ≤ 0.")
    if X_prod_inicial_kg_kg < 0:
        raise ValueError(f"MOTOR_TD_X_INICIAL_NEGATIVA: X_inicial={X_prod_inicial_kg_kg:.4f} < 0.")
    if X_prod_objetivo_kg_kg < 0:
        raise ValueError(f"MOTOR_TD_X_OBJ_NEGATIVA: X_obj={X_prod_objetivo_kg_kg:.4f} < 0.")
    # Determinar horizonte
    t_max_forz = float(forzantes.t_s[-1])
    if t_max_s is None:
        t_max_s_eff = t_max_forz
    else:
        if t_max_s <= 0:
            raise ValueError(f"MOTOR_TD_T_MAX_NO_POSITIVO: t_max={t_max_s:.1f} s ≤ 0.")
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
    Q_rad_aire_fz = np.asarray(forzantes.Q_rad_aire_W, dtype=float)

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
        h_w = 5.7 + 3.8 * v_w  # McAdams
        return T_ent, omega_ent, m_dot, T_amb, h_w

    def _Q_rad_t(t: float) -> float:
        """Potencia radiativa absorbida por el producto a tiempo t [W]."""
        if _Q_rad_factor == 0.0:
            return 0.0
        I_g = max(0.0, _interp(I_g_fz, t))
        return _Q_rad_factor * I_g

    def _Q_rad_aire_t(t: float) -> float:
        """Potencia radiativa que calienta el aire vía superficies internas [W]."""
        return _interp(Q_rad_aire_fz, t)

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
            R_cond_techo_m2K_W=R_cond_techo_m2K_W,
            A_techo_m2=A_techo_m2,
            Q_rad_aire_W=_Q_rad_aire_t(t),
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
        # Paso máximo derivado del espaciado de forzantes (fase 1b): evita saltar
        # nodos con forzantes sub-horarias; == 3600 con forzantes horarias.
        max_step=_max_step_desde_forzantes(t_fz),
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
        sol.t_events[1]
        if (T_max_admisible_K is not None and len(sol.t_events) > 1)
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

    # --- Aviso de operación por encima de la ebullición local ---
    # El tope de `_omega_saturacion_acotada` evita que la corrida aborte, pero en
    # ese régimen el modelo está fuera de su dominio: hay que decirlo fuerte.
    _T_prod_max_K = float(np.max(sol.y[0])) if sol.y.size else 0.0
    if presion_vapor_saturacion(_T_prod_max_K) >= _FRAC_P_SAT_MAX * P_Pa:
        advertencias.append(
            f"CAM_TD_SOBRE_EBULLICION: el producto alcanzó "
            f"{_T_prod_max_K - 273.15:.1f} °C, cerca o por encima de la ebullición del "
            f"agua a la presión del sitio ({P_Pa / 1000:.1f} kPa). Se topeó la humedad "
            "de saturación para no abortar, pero **los resultados de esas horas no son "
            "confiables**: el modelo describe evaporación difusiva, no hervor. Suele "
            "indicar un colector sobredimensionado para el caudal — y ninguna fruta se "
            "seca sana a esa temperatura."
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
    Q_rad_aire_arr = np.zeros(n)
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
        Q_rad_aire_arr[i] = _Q_rad_aire_t(t_i)
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
        energia_rad_aire = float(np.trapezoid(Q_rad_aire_arr, sol.t))
    else:
        masa_evap = 0.0
        energia_rad = 0.0
        energia_rad_aire = 0.0

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
        Q_rad_aire_W=Q_rad_aire_arr,
        energia_rad_aire_total_J=energia_rad_aire,
        horas_clipeo_nocturno_s=horas_clipeo,
        horas_HR_alta_s=horas_hr_alta,
        T_max_alcanzada_K=float(np.max(sol.y[0])) if n > 0 else float(T_prod_inicial_K),
        advertencias=advertencias,
    )


# ===========================================================================
# S40 — Motor de cámara semicontinuo: cascada de N zonas a contracorriente
# ===========================================================================
#
# Túnel de secado tipo ADITAL: N columnas de carros en serie. El aire marcha
# de la zona N−1 (extremo seco/caliente, recibe el aire del colector+auxiliar)
# hacia la zona 0 (extremo fresco/húmedo, descarga el aire al ambiente). El
# producto avanza en sentido OPUESTO: entra fresco por la zona 0 y se descarga
# seco por la zona N−1. Cada `intervalo_avance_s` las columnas avanzan una
# posición (cadencia fija → sequedad de salida emergente).
#
# Reutiliza `resolver_estado_camara` (CSTR de una zona) intacto: para la zona i
# el aire de entrada es la salida de la zona i+1 (la vecina más caliente). Solo
# la zona N−1 recibe el aire de las forzantes (colector/auxiliar).
#
# Estado integrado: y = [T_0, X_0, T_1, X_1, ..., T_{N-1}, X_{N-1}] (2N vars).
# Por evaluación del RHS se marcha el aire N−1 → 0 (N solves algebraicos
# secuenciales, SIN Picard: el producto está dado en cada instante), y cada
# zona integra su EDO de producto. Los avances de columna son saltos discretos
# del estado: se integra un tramo de `intervalo_avance_s` con solve_ivp y luego
# se reinicializa (zona i ← producto de zona i−1; zona 0 ← carga fresca; zona
# N−1 → descarga). Decisiones de diseño S40: ver bitácora y plan industrial.
# ===========================================================================


@dataclass(frozen=True)
class ResultadoCascada:
    """Salida del motor semicontinuo (túnel a contracorriente).

    Atributos:
        n_zonas: Número de zonas (columnas) de la cascada.
        intervalo_avance_s: Cadencia de avance de columnas [s] = residencia por
            zona. La residencia total de un carro es n_zonas × intervalo.
        n_avances: Número de avances (columnas descargadas) simulados.
        X_salida_por_avance: X del producto descargado en cada avance
            [kg/kg seco], shape (n_avances,). Sequedad emergente.
        T_prod_salida_por_avance_K: T del producto descargado en cada avance [K].
        masa_evaporada_por_avance_kg: Agua evaporada de cada columna descargada
            [kg] = m_seco·(X_inicial − X_salida).
        X_salida_regimen: X de salida en régimen estacionario (promedio del
            último ciclo completo) [kg/kg seco]. ``None`` si no se alcanzó el
            régimen (n_avances < n_zonas, túnel aún llenándose).
        throughput_fresco_kg_s: Caudal de producto fresco procesado [kg/s] =
            masa_fresca_columna / intervalo_avance.
        masa_seca_producida_total_kg: Σ masa de producto descargado (a su X de
            salida) sobre todos los avances [kg].
        masa_evaporada_total_kg: Agua total evaporada (columnas descargadas +
            residual en el túnel al final) [kg].
        X_perfil_zonas: Perfil espacial de X por zona al final [kg/kg seco],
            shape (n_zonas,). Zona 0 = fresco, zona N−1 = seco.
        T_prod_perfil_zonas_K: Perfil de T de producto por zona al final [K].
        T_aire_perfil_zonas_K: Perfil de T del aire por zona al final [K]
            (reconstruido del último estado). Zona N−1 = más caliente.
        omega_aire_perfil_zonas: Perfil de ω del aire por zona al final [kg/kg as].
        status: 'regimen_alcanzado' | 'llenando' | 'error'.
        T_max_alcanzada_K: Máxima T_prod registrada en cualquier zona/instante [K].
        advertencias: Lista de códigos/mensajes.
    """

    n_zonas: int
    intervalo_avance_s: float
    n_avances: int
    X_salida_por_avance: np.ndarray
    T_prod_salida_por_avance_K: np.ndarray
    masa_evaporada_por_avance_kg: np.ndarray
    X_salida_regimen: float | None
    throughput_fresco_kg_s: float
    masa_seca_producida_total_kg: float
    masa_evaporada_total_kg: float
    X_perfil_zonas: np.ndarray
    T_prod_perfil_zonas_K: np.ndarray
    T_aire_perfil_zonas_K: np.ndarray
    omega_aire_perfil_zonas: np.ndarray
    status: str
    T_max_alcanzada_K: float = 0.0
    advertencias: list[str] = field(default_factory=list)


def simular_cascada(
    *,
    n_zonas: int,
    intervalo_avance_s: float,
    n_avances: int | None = None,
    # Estado inicial del producto fresco (idéntico para cada carga nueva)
    T_prod_inicial_K: float,
    X_prod_inicial_kg_kg: float,
    X_prod_objetivo_kg_kg: float,
    # Propiedades del producto (por columna)
    m_seco_por_zona_kg: float,
    c_ps_J_kgK: float,
    # Boundary del aire (colector/auxiliar) — entra a la zona N−1
    forzantes: ForzantesAire,
    # Geometría por zona
    A_prod_por_zona_m2: float,
    A_cuerpo_por_zona_m2: float,
    # Coeficientes de transporte interior (escalares congelados por defecto)
    h_conv_W_m2K: float,
    K_m_kg_m2s: float,
    k_aisl_W_mK: float,
    esp_cam_m: float,
    P_Pa: float,
    aw_func: Callable[[float], float],
    coef_transporte_func: Callable[[float, float, float, float], tuple[float, float]] | None = None,
    # Radiación solar directa (túnel translúcido — normalmente opaco → 0)
    tau_cubierta_solar: float = 0.0,
    alfa_producto_solar: float = 0.6,
    A_rad_por_zona_m2: float = 0.0,
    # Pérdida conductiva del techo translúcido por zona (normalmente opaco → 0)
    R_cond_techo_m2K_W: float = 0.0,
    A_techo_por_zona_m2: float = 0.0,
    T_max_admisible_K: float | None = None,
    rtol: float = 1e-6,
    atol: float = 1e-9,
) -> ResultadoCascada:
    """Simula el túnel semicontinuo a contracorriente (cascada de N zonas).

    Cadencia fija: cada ``intervalo_avance_s`` las columnas avanzan una
    posición; la sequedad de salida es emergente (no se ajusta la cadencia
    para alcanzar X_objetivo — X_objetivo solo sirve para avisar sub/sobre-secado).

    El túnel arranca **lleno de producto fresco** (condición realista al inicio
    de campaña). Tras ~n_zonas avances se alcanza el régimen estacionario.

    Para ``n_zonas == 1`` se reduce a un único CSTR de un solo paso de aire
    (equivalente a un batch que se descarga/recarga cada intervalo), lo que
    permite verificar consistencia con ``simular_secado``.

    Args:
        n_zonas: Número de columnas en serie (≥ 1).
        intervalo_avance_s: Cadencia de avance = residencia por zona [s] (> 0).
        n_avances: Número de avances a simular. Si None, se deriva del horizonte
            de las forzantes: floor(t_max_forz / intervalo_avance_s), mínimo 1.
        T_prod_inicial_K, X_prod_inicial_kg_kg: Estado del producto fresco.
        X_prod_objetivo_kg_kg: Humedad objetivo (solo para avisos sub/sobre-seco).
        m_seco_por_zona_kg: Masa seca de producto por columna [kg].
        c_ps_J_kgK: Calor específico del sólido seco [J/(kg·K)].
        forzantes: Serie horaria del aire que entra a la zona N−1 (salida del
            colector/auxiliar): T_ent, ω_ent, ṁ_as, T_amb, v_viento, I_g.
        A_prod_por_zona_m2, A_cuerpo_por_zona_m2: Áreas por zona.
        h_conv_W_m2K, K_m_kg_m2s: Coeficientes interiores (escalares congelados;
            se recalculan por paso si se pasa coef_transporte_func).
        k_aisl_W_mK, esp_cam_m, P_Pa, aw_func: Idénticos a simular_secado.
        coef_transporte_func: Coeficientes variables en t (opcional).
        T_max_admisible_K: Si se da, se avisa (no se detiene) si alguna zona
            supera ese umbral.

    Returns:
        ResultadoCascada con la sequedad emergente por avance, el throughput de
        régimen, totales de producción/evaporación y el perfil espacial final.

    Raises:
        ValueError: Para parámetros físicamente inválidos.
    """
    # --- Validación ---
    if n_zonas < 1:
        raise ValueError(f"CASCADA_N_ZONAS_INVALIDO: n_zonas={n_zonas} < 1.")
    if intervalo_avance_s <= 0:
        raise ValueError(
            f"CASCADA_INTERVALO_NO_POSITIVO: intervalo_avance_s={intervalo_avance_s:.1f} s ≤ 0."
        )
    if m_seco_por_zona_kg <= 0:
        raise ValueError(
            f"CASCADA_M_SECO_NO_POSITIVA: m_seco_por_zona={m_seco_por_zona_kg:.3f} kg ≤ 0."
        )
    if c_ps_J_kgK <= 0:
        raise ValueError(f"CASCADA_CP_NO_POSITIVA: c_ps={c_ps_J_kgK:.1f} ≤ 0.")
    if X_prod_inicial_kg_kg < 0 or X_prod_objetivo_kg_kg < 0:
        raise ValueError("CASCADA_X_NEGATIVA: X_inicial/X_objetivo deben ser ≥ 0.")

    t_max_forz = float(forzantes.t_s[-1])
    if n_avances is None:
        n_avances = max(1, int(np.floor(t_max_forz / intervalo_avance_s)))
    elif n_avances < 1:
        raise ValueError(f"CASCADA_N_AVANCES_INVALIDO: n_avances={n_avances} < 1.")

    advertencias: list[str] = []

    # --- Interpoladores de forzantes (idéntico a simular_secado) ---
    t_fz = np.asarray(forzantes.t_s, dtype=float)
    T_ent_fz = np.asarray(forzantes.T_ent_K, dtype=float)
    omega_ent_fz = np.asarray(forzantes.omega_ent, dtype=float)
    m_dot_fz = np.asarray(forzantes.m_dot_aire_seco_kg_s, dtype=float)
    T_amb_fz = np.asarray(forzantes.T_amb_K, dtype=float)
    v_viento_fz = np.asarray(forzantes.v_viento_ms, dtype=float)
    I_g_fz = np.asarray(forzantes.I_g_W_m2, dtype=float)
    Q_rad_aire_fz = np.asarray(forzantes.Q_rad_aire_W, dtype=float)

    _Q_rad_factor = tau_cubierta_solar * alfa_producto_solar * A_rad_por_zona_m2

    def _interp(arr: np.ndarray, t: float) -> float:
        t_clip = max(t_fz[0], min(t_fz[-1], t))
        return float(np.interp(t_clip, t_fz, arr))

    def _boundary_t(t: float) -> tuple[float, float, float, float, float]:
        T_ent = _interp(T_ent_fz, t)
        omega_ent = _interp(omega_ent_fz, t)
        m_dot = _interp(m_dot_fz, t)
        T_amb = _interp(T_amb_fz, t)
        v_w = _interp(v_viento_fz, t)
        h_w = 5.7 + 3.8 * v_w
        return T_ent, omega_ent, m_dot, T_amb, h_w

    def _Q_rad_t(t: float) -> float:
        if _Q_rad_factor == 0.0:
            return 0.0
        return _Q_rad_factor * max(0.0, _interp(I_g_fz, t))

    def _Q_rad_aire_por_zona_t(t: float) -> float:
        """Potencia radiativa al aire, repartida en partes iguales entre zonas.

        ``forzantes.Q_rad_aire_W`` es el total de la cámara (como
        ``A_rad_por_zona_m2`` = ``A_rad_total/N``, se reparte por zona).
        """
        return _interp(Q_rad_aire_fz, t) / n_zonas

    def _resolver_zona(
        T_prod: float,
        X_prod: float,
        T_ent_zona: float,
        omega_ent_zona: float,
        m_dot: float,
        T_amb: float,
        h_w: float,
        Q_rad_aire_zona_W: float = 0.0,
        K_m_override: float | None = None,
    ) -> EstadoCamara:
        """Resuelve el CSTR de una zona dado el aire que le entra (de la vecina
        más caliente o, para la zona N−1, de las forzantes)."""
        X_safe = max(X_prod, 0.0)
        if coef_transporte_func is not None:
            h_conv_local, K_m_base = coef_transporte_func(T_ent_zona, T_prod, omega_ent_zona, m_dot)
        else:
            h_conv_local, K_m_base = h_conv_W_m2K, K_m_kg_m2s
        K_m_usado = K_m_override if K_m_override is not None else K_m_base
        return resolver_estado_camara(
            T_prod_K=T_prod,
            X_prod_kg_kg=X_safe,
            T_ent_K=T_ent_zona,
            omega_ent_kg_kg=omega_ent_zona,
            A_prod_m2=A_prod_por_zona_m2,
            A_cuerpo_m2=A_cuerpo_por_zona_m2,
            m_dot_as_kg_s=m_dot,
            h_conv_W_m2K=h_conv_local,
            K_m_kg_m2s=K_m_usado,
            h_w_W_m2K=h_w,
            k_aisl_W_mK=k_aisl_W_mK,
            esp_cam_m=esp_cam_m,
            T_amb_K=T_amb,
            P_Pa=P_Pa,
            aw_func=aw_func,
            R_cond_techo_m2K_W=R_cond_techo_m2K_W,
            A_techo_m2=A_techo_por_zona_m2,
            Q_rad_aire_W=Q_rad_aire_zona_W,
        )

    def _march_aire(y: np.ndarray, t: float, aplicar_politica_B: bool) -> list[EstadoCamara]:
        """Marcha el aire de la zona N−1 → 0 y devuelve el EstadoCamara de cada
        zona (índice de lista = índice de zona)."""
        T_ent0, omega_ent0, m_dot, T_amb, h_w = _boundary_t(t)
        Q_rad_aire_zona = _Q_rad_aire_por_zona_t(t)
        estados: list[EstadoCamara | None] = [None] * n_zonas
        T_ent_i, omega_ent_i = T_ent0, omega_ent0  # aire que entra a la zona N−1
        for i in range(n_zonas - 1, -1, -1):
            T_prod_i, X_prod_i = y[2 * i], y[2 * i + 1]
            est = _resolver_zona(
                T_prod_i, X_prod_i, T_ent_i, omega_ent_i, m_dot, T_amb, h_w, Q_rad_aire_zona
            )
            if aplicar_politica_B and est.m_dot_w_kg_s < 0.0:
                est = _resolver_zona(
                    T_prod_i,
                    X_prod_i,
                    T_ent_i,
                    omega_ent_i,
                    m_dot,
                    T_amb,
                    h_w,
                    Q_rad_aire_zona,
                    K_m_override=0.0,
                )
            estados[i] = est
            # el aire que sale de la zona i entra a la zona i−1
            T_ent_i, omega_ent_i = est.T_flujo_K, est.omega_flujo_kg_kg
        return estados  # type: ignore[return-value]

    diag = {"T_max": float(T_prod_inicial_K)}

    def _rhs(t: float, y: np.ndarray) -> np.ndarray:
        estados = _march_aire(y, t, aplicar_politica_B=True)
        Q_rad = _Q_rad_t(t)
        dydt = np.zeros(2 * n_zonas)
        for i in range(n_zonas):
            T_prod_i, X_prod_i = y[2 * i], y[2 * i + 1]
            est = estados[i]
            X_safe = max(X_prod_i, 0.0)
            C_thermal = m_seco_por_zona_kg * (c_ps_J_kgK + _CP_AGUA_LIQ_J_KGK * X_safe)
            T_prod_safe = min(373.0, max(250.0, T_prod_i))
            L_v = calor_latente_vaporizacion(T_prod_safe)
            dydt[2 * i] = (est.q_prod_W + Q_rad - est.m_dot_w_kg_s * L_v) / C_thermal
            dydt[2 * i + 1] = -est.m_dot_w_kg_s / m_seco_por_zona_kg
            if T_prod_i > diag["T_max"]:
                diag["T_max"] = float(T_prod_i)
        return dydt

    # --- Estado inicial: túnel lleno de producto fresco ---
    y = np.tile([float(T_prod_inicial_K), float(X_prod_inicial_kg_kg)], n_zonas)

    X_salida: list[float] = []
    T_salida: list[float] = []
    m_evap_avance: list[float] = []
    status = "error"

    for k in range(n_avances):
        t0 = k * intervalo_avance_s
        t1 = (k + 1) * intervalo_avance_s
        if t0 >= t_max_forz:
            # Sin más clima disponible; detener el llenado.
            break
        t1_eff = min(t1, t_max_forz)
        sol = solve_ivp(
            _rhs,
            t_span=(t0, t1_eff),
            y0=y,
            method="LSODA",
            rtol=rtol,
            atol=atol,
            # Paso máximo derivado del espaciado de forzantes (fase 1b).
            max_step=_max_step_desde_forzantes(t_fz),
        )
        if not sol.success:
            advertencias.append(f"CASCADA_SOLVE_IVP_FALLO (avance {k}): {sol.message}")
            return ResultadoCascada(
                n_zonas=n_zonas,
                intervalo_avance_s=intervalo_avance_s,
                n_avances=len(X_salida),
                X_salida_por_avance=np.asarray(X_salida),
                T_prod_salida_por_avance_K=np.asarray(T_salida),
                masa_evaporada_por_avance_kg=np.asarray(m_evap_avance),
                X_salida_regimen=None,
                throughput_fresco_kg_s=0.0,
                masa_seca_producida_total_kg=0.0,
                masa_evaporada_total_kg=0.0,
                X_perfil_zonas=y[1::2].copy(),
                T_prod_perfil_zonas_K=y[0::2].copy(),
                T_aire_perfil_zonas_K=np.array([]),
                omega_aire_perfil_zonas=np.array([]),
                status="error",
                T_max_alcanzada_K=diag["T_max"],
                advertencias=advertencias,
            )
        y = sol.y[:, -1].copy()

        # --- Descarga de la zona N−1 (extremo seco) ---
        X_desc = max(0.0, float(y[2 * (n_zonas - 1) + 1]))
        T_desc = float(y[2 * (n_zonas - 1)])
        X_salida.append(X_desc)
        T_salida.append(T_desc)
        m_evap_avance.append(m_seco_por_zona_kg * max(0.0, X_prod_inicial_kg_kg - X_desc))

        # --- Avance de columnas: zona i ← zona i−1; zona 0 ← carga fresca ---
        if n_zonas >= 2:
            for i in range(n_zonas - 1, 0, -1):
                y[2 * i] = y[2 * (i - 1)]
                y[2 * i + 1] = y[2 * (i - 1) + 1]
        y[0] = float(T_prod_inicial_K)
        y[1] = float(X_prod_inicial_kg_kg)

    n_av_real = len(X_salida)
    if n_av_real == 0:
        raise ValueError(
            "CASCADA_HORIZONTE_INSUFICIENTE: el horizonte de forzantes "
            f"({t_max_forz:.0f} s) no cubre un intervalo de avance "
            f"({intervalo_avance_s:.0f} s)."
        )

    # --- Régimen: estado estacionario tras n_zonas avances ---
    X_salida_arr = np.asarray(X_salida)
    if n_av_real >= n_zonas:
        X_salida_regimen = float(np.mean(X_salida_arr[n_zonas - 1 :]))
        status = "regimen_alcanzado"
    else:
        X_salida_regimen = None
        status = "llenando"
        advertencias.append(
            f"CASCADA_REGIMEN_NO_ALCANZADO: se simularon {n_av_real} avances pero el "
            f"túnel necesita ≥ {n_zonas} para llenarse. La sequedad de salida aún "
            "está en transitorio."
        )

    # --- Avisos de sub/sobre-secado (sobre el régimen, si existe) ---
    X_ref = X_salida_regimen if X_salida_regimen is not None else float(X_salida_arr[-1])
    if X_ref > X_prod_objetivo_kg_kg * 1.10:
        advertencias.append(
            f"CASCADA_SUBSECADO: el producto de salida (X={X_ref:.3f}) supera el "
            f"objetivo (X_obj={X_prod_objetivo_kg_kg:.3f}). Reducí la cadencia "
            "(intervalo de avance mayor) o agregá zonas."
        )
    elif X_ref < X_prod_objetivo_kg_kg * 0.90:
        advertencias.append(
            f"CASCADA_SOBRESECADO: el producto de salida (X={X_ref:.3f}) está por "
            f"debajo del objetivo (X_obj={X_prod_objetivo_kg_kg:.3f}). Podés acelerar "
            "la cadencia (intervalo menor) para mayor throughput."
        )
    if T_max_admisible_K is not None and diag["T_max"] > T_max_admisible_K:
        advertencias.append(
            f"CASCADA_DANO_TERMICO: T_prod alcanzó {diag['T_max'] - 273.15:.1f} °C "
            f"(> T_max={T_max_admisible_K - 273.15:.1f} °C) en alguna zona."
        )

    # --- Producción y throughput ---
    m_fresca_columna = m_seco_por_zona_kg * (1.0 + X_prod_inicial_kg_kg)
    throughput_fresco = m_fresca_columna / intervalo_avance_s
    masa_seca_producida = float(np.sum(m_seco_por_zona_kg * (1.0 + X_salida_arr)))
    # Evaporado: columnas descargadas + residual aún en el túnel al final.
    m_evap_descargado = float(np.sum(m_evap_avance))
    X_residual = np.clip(y[1::2], 0.0, None)
    m_evap_residual = float(
        np.sum(m_seco_por_zona_kg * np.maximum(0.0, X_prod_inicial_kg_kg - X_residual))
    )
    masa_evap_total = m_evap_descargado + m_evap_residual

    # --- Perfil espacial final + reconstrucción del aire ---
    estados_final = _march_aire(y, min((n_av_real) * intervalo_avance_s, t_max_forz), True)
    T_aire_perfil = np.array([e.T_flujo_K for e in estados_final])
    omega_perfil = np.array([e.omega_flujo_kg_kg for e in estados_final])

    return ResultadoCascada(
        n_zonas=n_zonas,
        intervalo_avance_s=intervalo_avance_s,
        n_avances=n_av_real,
        X_salida_por_avance=X_salida_arr,
        T_prod_salida_por_avance_K=np.asarray(T_salida),
        masa_evaporada_por_avance_kg=np.asarray(m_evap_avance),
        X_salida_regimen=X_salida_regimen,
        throughput_fresco_kg_s=throughput_fresco,
        masa_seca_producida_total_kg=masa_seca_producida,
        masa_evaporada_total_kg=masa_evap_total,
        X_perfil_zonas=y[1::2].copy(),
        T_prod_perfil_zonas_K=y[0::2].copy(),
        T_aire_perfil_zonas_K=T_aire_perfil,
        omega_aire_perfil_zonas=omega_perfil,
        status=status,
        T_max_alcanzada_K=diag["T_max"],
        advertencias=advertencias,
    )
