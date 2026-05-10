"""
Estimación de pérdidas de carga para el dimensionamiento del motor.

Provee funciones para calcular ΔP en el banco de colectores y en la cámara
de secado. Estos valores se usan como entrada al objeto Motor.

Modelos:
    Colector (canal rectangular) — Darcy-Weisbach:
        ΔP = f × (L/Dh) × (ρ × v²/2)
        Dh = 2·W·e / (W + e)    [diámetro hidráulico canal plano]
        f  = 64/Re               (laminar, Re < 2 300)
        f  = 0.316·Re^(-0.25)   (Blasius turbulento, 2 300 ≤ Re < 100 000)
        En banco serie: ΔP_rama = ΔP_unidad × n_serie
        En paralelo:   ΔP banco = ΔP rama

    Cámara — flujo HORIZONTAL:
        ΔP_cam = K_malla × (ρ · v_sup²/2) × n_bandejas
        v_sup = Q_vol / (ancho × alto)
        K_malla = 2.0 (malla de alambre, conservador)

    Cámara — flujo VERTICAL_ASCENDENTE:
        Por bandeja: ΔP = ΔP_malla + ΔP_lecho
        ΔP_malla = K_malla × (ρ · v₀²/2)
        ΔP_lecho = Ergun(v₀, ε, Φ_s, d_p, L)   [si d_p está definido]
        v₀ = Q_vol / area_bandeja

    Ergun (lecho empacado):
        ΔP/L = 150·μ·v₀·(1-ε)² / [(Φ_s·d_p)²·ε³]
             + 1.75·ρ·v₀²·(1-ε) / [(Φ_s·d_p)·ε³]

Propiedades del aire:
    ρ(T,P) = P / (R_aire · T)          [gas ideal, R_aire = 287.058 J/(kg·K)]
    μ(T)   = Sutherland (1893)         [válido 200–2 000 K, error < 2 %]
    P_atm(h) = ISA (atmósfera estándar, troposfera, h < 11 000 m)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.camara import Camara, ConfiguracionBandejas
    from core.colector import Colector

# ---------------------------------------------------------------------------
# Constantes físicas
# ---------------------------------------------------------------------------

_R_AIRE: float = 287.058     # J/(kg·K) — constante gas ideal aire seco
_MU_REF: float = 1.716e-5   # Pa·s     — viscosidad referencia Sutherland
_T_REF_MU: float = 273.11   # K        — temperatura referencia Sutherland
_S_SUTH: float = 110.4      # K        — constante Sutherland del aire

# Coeficiente de resistencia de malla (adimensional, v0)
K_MALLA: float = 2.0


# ---------------------------------------------------------------------------
# Propiedades del aire en función de T y P
# ---------------------------------------------------------------------------


def presion_atmosferica(altitud_m: float) -> float:
    """Presión atmosférica estándar ISA en función de la altitud [Pa].

    P = 101 325 × (1 − 2.25577×10⁻⁵ · h)^5.25588

    Válida para h < 11 000 m (troposfera).

    Args:
        altitud_m: Altitud sobre el nivel del mar [m].

    Returns:
        P_atm [Pa].
    """
    return 101325.0 * (1.0 - 2.25577e-5 * altitud_m) ** 5.25588


def densidad_aire(T_K: float, P_Pa: float = 101325.0) -> float:
    """Densidad del aire seco via gas ideal [kg/m³].

    ρ = P / (R_aire · T)

    Args:
        T_K: Temperatura [K].
        P_Pa: Presión [Pa].

    Returns:
        ρ [kg/m³].
    """
    return P_Pa / (_R_AIRE * T_K)


def viscosidad_aire(T_K: float) -> float:
    """Viscosidad dinámica del aire via ley de Sutherland [Pa·s].

    μ = μ_ref × (T/T_ref)^1.5 × (T_ref + S) / (T + S)

    Válida para 200–2 000 K con error < 2 %.

    Args:
        T_K: Temperatura [K].

    Returns:
        μ [Pa·s].
    """
    return _MU_REF * (T_K / _T_REF_MU) ** 1.5 * (_T_REF_MU + _S_SUTH) / (T_K + _S_SUTH)


# ---------------------------------------------------------------------------
# Estimación ΔP colector
# ---------------------------------------------------------------------------


def estimar_delta_P_colector(
    colector: "Colector",
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> float:
    """Estima la pérdida de carga en el banco de colectores via Darcy-Weisbach.

    La densidad y viscosidad del aire se calculan internamente a partir de T y P.
    Para banco en serie, ΔP escala con la longitud total del camino. Para ramas
    en paralelo, ΔP banco = ΔP de una rama.

    Args:
        colector: Objeto Colector con geometría y banco definidos.
        T_K: Temperatura de operación del aire en el colector [K]. Default: 323.15 K (50 °C).
        P_Pa: Presión atmosférica en el emplazamiento [Pa]. Default: 101 325 Pa (nivel del mar).

    Returns:
        ΔP estimada en el banco de colectores [Pa].
    """
    u = colector.unidad
    b = colector.banco

    rho = densidad_aire(T_K, P_Pa)
    mu = viscosidad_aire(T_K)

    ancho = u.ancho_m
    espaciado = u.espaciado_m
    v = u.velocidad_diseno_ms
    L_total = u.largo_m * b.n_serie

    Dh = 2.0 * ancho * espaciado / (ancho + espaciado)
    Re = rho * v * Dh / mu

    if Re <= 0:
        return 0.0
    elif Re < 2300.0:
        f = 64.0 / Re
    else:
        f = 0.316 * Re ** (-0.25)

    return f * (L_total / Dh) * (rho * v ** 2 / 2.0)


# ---------------------------------------------------------------------------
# Ergun — lecho empacado (uso interno)
# ---------------------------------------------------------------------------


def _delta_P_lecho_por_bandeja(
    bandejas: "ConfiguracionBandejas",
    v0: float,
    rho: float,
    mu: float,
) -> float:
    """ΔP a través de la capa de producto en una bandeja via ecuación de Ergun [Pa].

    Retorna 0 si diametro_eq_particula_m no está definido.

    Args:
        bandejas: Configuración de bandejas (contiene ε, Φ_s, d_p, L).
        v0: Velocidad superficial del aire sobre la bandeja [m/s].
        rho: Densidad del aire [kg/m³].
        mu: Viscosidad dinámica del aire [Pa·s].

    Returns:
        ΔP_lecho por bandeja [Pa].
    """
    if bandejas.diametro_eq_particula_m is None:
        return 0.0

    d_p = bandejas.diametro_eq_particula_m
    eps = bandejas.porosidad_lecho
    phi_s = bandejas.esfericidad
    L = bandejas.espesor_capa_m

    phi_dp = phi_s * d_p
    eps3 = eps ** 3
    one_minus_eps = 1.0 - eps

    grad_viscoso = 150.0 * mu * v0 * one_minus_eps ** 2 / (phi_dp ** 2 * eps3)
    grad_inercial = 1.75 * rho * v0 ** 2 * one_minus_eps / (phi_dp * eps3)

    return (grad_viscoso + grad_inercial) * L


# ---------------------------------------------------------------------------
# Estimación ΔP cámara
# ---------------------------------------------------------------------------


def estimar_delta_P_camara(
    camara: "Camara",
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> float:
    """Estima la pérdida de carga en la cámara de secado.

    Flujo HORIZONTAL:
        ΔP = K_malla × (ρ·v_sup²/2) × n_bandejas
        v_sup = Q_vol / (ancho × alto)

    Flujo VERTICAL_ASCENDENTE:
        ΔP = (ΔP_malla + ΔP_lecho) × n_bandejas
        ΔP_malla = K_malla × (ρ·v₀²/2),   v₀ = Q_vol / area_bandeja
        ΔP_lecho = Ergun(v₀, ε, Φ_s, d_p, L)  [si d_p definido, si no = 0]

    Args:
        camara: Objeto Camara con geometría, bandejas y flujo definidos.
        T_K: Temperatura de operación del aire en la cámara [K]. Default: 323.15 K (50 °C).
        P_Pa: Presión atmosférica en el emplazamiento [Pa]. Default: 101 325 Pa.

    Returns:
        ΔP estimada en la cámara de secado [Pa].
    """
    from core.camara import DireccionFlujo

    g = camara.geometria
    f = camara.flujo
    b = camara.bandejas

    rho = densidad_aire(T_K, P_Pa)
    mu = viscosidad_aire(T_K)
    Q_vol = f.caudal_masico_kg_s / rho

    if f.direccion_flujo == DireccionFlujo.VERTICAL_ASCENDENTE:
        v0 = Q_vol / b.area_bandeja_m2 if b.area_bandeja_m2 > 0 else 0.0
        dP_malla = K_MALLA * (rho * v0 ** 2 / 2.0)
        dP_lecho = _delta_P_lecho_por_bandeja(b, v0, rho, mu)
        return (dP_malla + dP_lecho) * b.n_bandejas
    else:
        seccion = g.ancho_m * g.alto_m
        v_sup = Q_vol / seccion if seccion > 0 else 0.0
        dP_malla = K_MALLA * (rho * v_sup ** 2 / 2.0)
        return dP_malla * b.n_bandejas


# ---------------------------------------------------------------------------
# Caudal volumétrico desde caudal másico
# ---------------------------------------------------------------------------


def caudal_masico_a_volumetrico(
    caudal_masico_kg_s: float,
    T_K: float,
    P_Pa: float = 101325.0,
) -> float:
    """Convierte caudal másico a volumétrico usando gas ideal.

    Args:
        caudal_masico_kg_s: Caudal másico de aire seco [kg/s].
        T_K: Temperatura del aire [K].
        P_Pa: Presión absoluta [Pa]. Default: 101 325 Pa.

    Returns:
        Caudal volumétrico [m³/s].
    """
    rho = densidad_aire(T_K, P_Pa)
    return caudal_masico_kg_s / rho
