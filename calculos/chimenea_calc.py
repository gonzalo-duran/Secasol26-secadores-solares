"""Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.

Modelo cuasi-estacionario unidimensional. La chimenea induce flujo natural
por diferencia de densidad entre la columna de aire caliente (cámara + chimenea)
y la atmósfera circundante. El caudal de equilibrio se obtiene cuando el tiro
disponible iguala las pérdidas totales del lazo.

Fenómenos modelados:
- Tiro térmico (stack effect): ΔP_tiro = g·H_eff·(ρ_amb − ρ_chim).
- Fricción en el ducto de chimenea: Darcy-Weisbach con Haaland.
- Pérdidas singulares de entrada y salida (K bundleado por defecto = 1.5).

Convención termodinámica:
- T_chim es la temperatura promedio de la columna ascendente (cámara + chimenea).
- Para prediseño se recomienda T_chim ≈ T_salida_camara (el aire ya pasó por
  el enfriamiento evaporativo en la cámara), no T_salida_colector.
- H_eff = altura_chimenea + altura útil de la cámara (entrada de aire frío
  en la base, salida por la chimenea superior).

API pública:
- `delta_P_tiro_Pa`: tiro térmico disponible.
- `delta_P_chimenea_Pa`: pérdida en el ducto (fricción + singulares).
- `caudal_natural_kgs`: caudal másico de equilibrio del lazo completo.

El módulo es puro: no depende de `core/` ni de `streamlit`. Toma primitivas
para mantenerse testeable y reusable desde cualquier capa.
"""
from __future__ import annotations

from math import pi

import numpy as np
from scipy.optimize import brentq

# _factor_friccion_haaland es interno a motor_calc pero esta es la misma
# implementación que necesitamos; reusarla evita duplicar código y mantiene
# coherencia con las pérdidas del colector y de la cámara.
from calculos.motor_calc import (
    _factor_friccion_haaland as _haaland,
    densidad_aire,
    viscosidad_aire,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_G_MS2: float = 9.81

# Rugosidad típica para chapa galvanizada (~0.15 mm). Cubre la mayoría de las
# chimeneas de secadores solares (galvanizada, acero pintado). Usuarios con
# materiales distintos pueden pasar el valor explícito.
_RUGOSIDAD_DEFAULT_M: float = 1.5e-4

# Coeficiente de pérdidas singulares por defecto: K_entrada (~0.5, contracción
# suave desde cámara) + K_salida (1.0, descarga a la atmósfera) = 1.5.
_K_SINGULAR_DEFAULT: float = 1.5

# Bracket para brentq al buscar el caudal de equilibrio. Cubre desde flujo
# imperceptible (1e-8 kg/s ≈ 0.01 g/s) hasta caudales de chimeneas grandes
# (10 kg/s ≈ 36 000 m³/h). Si el problema cae fuera, brentq lanza ValueError.
_M_MIN_KGS: float = 1.0e-8
_M_MAX_KGS: float = 10.0


# ---------------------------------------------------------------------------
# Tiro térmico (driving force)
# ---------------------------------------------------------------------------


def delta_P_tiro_Pa(
    T_amb_K: float,
    T_chim_K: float,
    H_eff_m: float,
    P_amb_Pa: float = 101325.0,
) -> float:
    """Tiro térmico disponible en la base de la chimenea [Pa].

    Formula de empuje hidrostático para columnas de aire a P común:

        ΔP_tiro = g · H_eff · (ρ_amb − ρ_chim)

    Con gas ideal a P común: ρ ∝ 1/T, así que ΔP_tiro > 0 cuando T_chim > T_amb
    (flujo ascendente en la chimenea) y ΔP_tiro < 0 cuando T_chim < T_amb
    (contraflujo, ej. de noche o con sombras).

    Args:
        T_amb_K: Temperatura del aire ambiente [K].
        T_chim_K: Temperatura promedio de la columna ascendente [K]. Para
            prediseño, usar T_salida_camara.
        H_eff_m: Altura efectiva de la columna [m]: altura de chimenea +
            altura útil de la cámara (desde la entrada de aire frío hasta la
            salida de la chimenea).
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        ΔP_tiro [Pa]. Positivo si la columna caliente es menos densa que el
        ambiente (caso normal de operación diurna).
    """
    if H_eff_m <= 0:
        return 0.0
    rho_amb = densidad_aire(T_amb_K, P_amb_Pa)
    rho_chim = densidad_aire(T_chim_K, P_amb_Pa)
    return _G_MS2 * H_eff_m * (rho_amb - rho_chim)


# ---------------------------------------------------------------------------
# Pérdida de carga del ducto de chimenea
# ---------------------------------------------------------------------------


def delta_P_chimenea_Pa(
    m_punto_kgs: float,
    T_chim_K: float,
    diametro_m: float,
    altura_m: float,
    P_amb_Pa: float = 101325.0,
    rugosidad_m: float = _RUGOSIDAD_DEFAULT_M,
    K_singular: float = _K_SINGULAR_DEFAULT,
) -> float:
    """Pérdida de carga en el ducto de chimenea [Pa].

    Incluye fricción (Darcy-Weisbach con Haaland) y singulares de entrada+salida.

        ΔP_chim = (f · L/D + K_singular) · ρ_chim · v² / 2

    Las propiedades del aire (ρ, μ) se evalúan a T_chim (temperatura local
    dentro de la columna, no la del ambiente).

    Args:
        m_punto_kgs: Caudal másico [kg/s].
        T_chim_K: Temperatura del aire en la chimenea [K].
        diametro_m: Diámetro interno de la chimenea [m].
        altura_m: Largo del ducto de chimenea [m].
        P_amb_Pa: Presión ambiente [Pa].
        rugosidad_m: Rugosidad absoluta de la pared interna [m]. Default
            1.5e-4 m (chapa galvanizada).
        K_singular: Coeficiente bundleado de pérdidas singulares
            (entrada + salida). Default 1.5 = 0.5 (contracción suave) +
            1.0 (descarga a atmósfera).

    Returns:
        ΔP [Pa]. Siempre ≥ 0.
    """
    if m_punto_kgs <= 0 or diametro_m <= 0 or altura_m <= 0:
        return 0.0
    rho = densidad_aire(T_chim_K, P_amb_Pa)
    mu = viscosidad_aire(T_chim_K)
    A = pi * (diametro_m / 2.0) ** 2
    v = m_punto_kgs / (rho * A)
    Re = rho * v * diametro_m / mu
    eps_rel = rugosidad_m / diametro_m
    f = _haaland(Re, eps_rel)
    K_total = f * (altura_m / diametro_m) + K_singular
    return K_total * (rho * v ** 2) / 2.0


# ---------------------------------------------------------------------------
# Caudal de equilibrio del lazo
# ---------------------------------------------------------------------------


def caudal_natural_kgs(
    T_amb_K: float,
    T_chim_K: float,
    diametro_chim_m: float,
    altura_chim_m: float,
    H_camara_m: float,
    delta_P_resto_fn,
    P_amb_Pa: float = 101325.0,
    rugosidad_m: float = _RUGOSIDAD_DEFAULT_M,
    K_singular_chim: float = _K_SINGULAR_DEFAULT,
) -> dict:
    """Caudal másico de equilibrio del lazo con chimenea solar [kg/s].

    Resuelve la ecuación de equilibrio:

        ΔP_tiro(T_amb, T_chim, H_eff) = ΔP_chimenea(ṁ, T_chim, ...) + ΔP_resto(ṁ)

    donde ΔP_resto agrupa colector + cámara + ductos + singulares del resto
    del lazo. La temperatura T_chim se toma como dato; el acoplamiento térmico
    completo (T_chim depende de ṁ) requiere iteración externa sobre esta
    función.

    Args:
        T_amb_K: Temperatura del aire ambiente [K].
        T_chim_K: Temperatura promedio de la columna ascendente [K].
            Recomendación: usar T_salida_camara.
        diametro_chim_m: Diámetro interno de la chimenea [m].
        altura_chim_m: Altura de la chimenea sobre la cámara [m].
        H_camara_m: Altura útil de la cámara (entrada-de-aire a base-de-chimenea) [m].
        delta_P_resto_fn: Callable ``f(m_punto_kgs) → ΔP [Pa]`` que devuelve
            la pérdida de carga del resto del lazo (todo excepto la propia
            chimenea). Debe ser monótona creciente y satisfacer f(0) = 0.
            En la práctica se construye con
            ``estimar_delta_P_colector + estimar_delta_P_camara + estimar_delta_P_singulares``.
        P_amb_Pa: Presión ambiente [Pa].
        rugosidad_m: Rugosidad de la chimenea [m].
        K_singular_chim: Pérdidas singulares de la chimenea (entrada+salida).

    Returns:
        Dict con:
            - ``m_punto_kgs``: caudal másico de equilibrio.
            - ``v_chim_ms``: velocidad media en la chimenea.
            - ``delta_P_tiro_Pa``: tiro disponible.
            - ``delta_P_chimenea_Pa``: pérdida en el ducto de chimenea.
            - ``delta_P_resto_Pa``: pérdida en el resto del lazo.
            - ``Re_chimenea``: Reynolds en la chimenea.
            - ``H_eff_m``: altura efectiva usada.
            - ``advertencias``: lista de códigos.

    Raises:
        ValueError: Si el bracket de brentq no encierra la raíz (lazo muy
            restrictivo o caudal de equilibrio fuera de ``[_M_MIN_KGS, _M_MAX_KGS]``).
    """
    H_eff = altura_chim_m + H_camara_m
    dPT = delta_P_tiro_Pa(T_amb_K, T_chim_K, H_eff, P_amb_Pa)
    advertencias: list[str] = []

    # Caso sin tiro: T_chim ≤ T_amb (noche, día nublado sin gradiente, etc.)
    if dPT <= 0.0:
        return {
            "m_punto_kgs": 0.0,
            "v_chim_ms": 0.0,
            "delta_P_tiro_Pa": dPT,
            "delta_P_chimenea_Pa": 0.0,
            "delta_P_resto_Pa": 0.0,
            "Re_chimenea": 0.0,
            "H_eff_m": H_eff,
            "advertencias": ["CHIM_SIN_TIRO: T_chim ≤ T_amb, no hay flujo natural."],
        }

    def residuo(m: float) -> float:
        dPC = delta_P_chimenea_Pa(
            m, T_chim_K, diametro_chim_m, altura_chim_m,
            P_amb_Pa, rugosidad_m, K_singular_chim,
        )
        dPR = float(delta_P_resto_fn(m))
        return dPT - dPC - dPR

    m_eq = brentq(residuo, _M_MIN_KGS, _M_MAX_KGS, xtol=1e-8, rtol=1e-6)

    rho_chim = densidad_aire(T_chim_K, P_amb_Pa)
    A_chim = pi * (diametro_chim_m / 2.0) ** 2
    v_chim = m_eq / (rho_chim * A_chim)
    mu_chim = viscosidad_aire(T_chim_K)
    Re = rho_chim * v_chim * diametro_chim_m / mu_chim
    dPC_eq = delta_P_chimenea_Pa(
        m_eq, T_chim_K, diametro_chim_m, altura_chim_m,
        P_amb_Pa, rugosidad_m, K_singular_chim,
    )
    dPR_eq = float(delta_P_resto_fn(m_eq))

    if Re < 2300.0:
        advertencias.append("CHIM_FLUJO_LAMINAR: Re < 2300, fricción dominada por viscosidad.")
    if v_chim > 5.0:
        advertencias.append(
            f"CHIM_VEL_ALTA: v_chim = {v_chim:.2f} m/s > 5 m/s. "
            "Revisar diámetro o pérdidas singulares."
        )

    return {
        "m_punto_kgs": float(m_eq),
        "v_chim_ms": float(v_chim),
        "delta_P_tiro_Pa": float(dPT),
        "delta_P_chimenea_Pa": float(dPC_eq),
        "delta_P_resto_Pa": float(dPR_eq),
        "Re_chimenea": float(Re),
        "H_eff_m": float(H_eff),
        "advertencias": advertencias,
    }
