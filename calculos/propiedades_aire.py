"""Propiedades termofísicas del aire seco en función de la temperatura.

Provee correlaciones ``k(T)``, ``mu(T)``, ``cp(T)``, ``Pr(T)`` y ``rho(T, P)``
para usar en el cálculo **local** del coeficiente convectivo interno de los
colectores (``colector_calc.py`` y ``colector_tipos234_calc.py``), donde la
temperatura del fluido varía a lo largo del canal y las propiedades constantes
a 323 K dejan de ser adecuadas (colectores largos de alto ΔT).

Es aire **seco** (no húmedo: para aire húmedo ver ``psicrometria.py``). El
módulo es puro (sin Streamlit, sin estado). Rango de validez: ~270–420 K.

Coherencia con el modelo histórico: a 323 K (50 °C) las correlaciones
reproducen, dentro de ~1 %, los valores constantes que usaban los motores de
colector (cp=1007, k=0.02814, μ=1.963e-5, Pr=0.703).

Correlaciones
-------------
- Viscosidad dinámica μ(T): ley de Sutherland (White, Viscous Fluid Flow).
- Conductividad térmica k(T): ley de Sutherland para conductividad.
- Calor específico cp(T): ajuste lineal a tablas de aire seco (Incropera).
- Número de Prandtl: Pr(T) = cp(T)·μ(T)/k(T) (consistente, no ajuste aparte).
- Densidad ρ(T, P): gas ideal, ρ = P/(R·T), R = 287.058 J/kg·K.

Referencias
-----------
- White, F.M. Viscous Fluid Flow, 3ª ed. (Sutherland μ y k).
- Incropera & DeWitt, Fundamentals of Heat and Mass Transfer (tablas aire seco).
"""

from __future__ import annotations

R_AIRE: float = 287.058  # J/kg·K — constante específica del aire seco

# --- Sutherland para viscosidad dinámica ---
_MU_REF: float = 1.716e-5  # Pa·s a T_REF
_T_REF_MU: float = 273.15  # K
_S_MU: float = 110.4  # K — constante de Sutherland (viscosidad)

# --- Sutherland para conductividad térmica ---
_K_REF: float = 0.0241  # W/m·K a T_REF
_T_REF_K: float = 273.15  # K
_S_K: float = 194.0  # K — constante de Sutherland (conductividad)

# --- cp lineal (aire seco, ~270–420 K) ---
_CP_300: float = 1005.0  # J/kg·K a 300 K
_CP_PENDIENTE: float = 0.08  # J/kg·K por K


def mu_aire(T_K: float) -> float:
    """Viscosidad dinámica del aire seco [Pa·s] — ley de Sutherland.

    Args:
        T_K: Temperatura [K].

    Returns:
        μ [Pa·s].
    """
    return _MU_REF * (T_K / _T_REF_MU) ** 1.5 * (_T_REF_MU + _S_MU) / (T_K + _S_MU)


def k_aire(T_K: float) -> float:
    """Conductividad térmica del aire seco [W/m·K] — ley de Sutherland.

    Args:
        T_K: Temperatura [K].

    Returns:
        k [W/m·K].
    """
    return _K_REF * (T_K / _T_REF_K) ** 1.5 * (_T_REF_K + _S_K) / (T_K + _S_K)


def cp_aire(T_K: float) -> float:
    """Calor específico del aire seco a presión constante [J/kg·K].

    Ajuste lineal a tablas de aire seco; varía <1 % en el rango de operación.

    Args:
        T_K: Temperatura [K].

    Returns:
        cp [J/kg·K].
    """
    return _CP_300 + _CP_PENDIENTE * (T_K - 300.0)


def pr_aire(T_K: float) -> float:
    """Número de Prandtl del aire seco [adim], Pr = cp·μ/k.

    Args:
        T_K: Temperatura [K].

    Returns:
        Pr [adim].
    """
    return cp_aire(T_K) * mu_aire(T_K) / k_aire(T_K)


def beta_aire(T_K: float) -> float:
    """Coeficiente de expansión térmica volumétrica del aire [1/K].

    Para un gas ideal ``β = −(1/ρ)·(∂ρ/∂T)_P = 1/T`` (Incropera & DeWitt,
    Ec. 9.9). Es el coeficiente de flotación que entra en Grashof
    ``Gr = g·β·ΔT·L³/ν²`` en todo cálculo de convección natural o mixta.

    Args:
        T_K: Temperatura [K] (típicamente la de película).

    Returns:
        β [1/K].

    Raises:
        ValueError: Si T_K <= 0.
    """
    if T_K <= 0.0:
        raise ValueError(f"PROP_AIRE_T_NO_POSITIVA: T={T_K} K <= 0.")
    return 1.0 / T_K


def rho_aire(T_K: float, P_Pa: float = 101325.0) -> float:
    """Densidad del aire seco [kg/m³] — gas ideal ρ = P/(R·T).

    Args:
        T_K: Temperatura [K].
        P_Pa: Presión absoluta [Pa]. Default 101 325 Pa.

    Returns:
        ρ [kg/m³].
    """
    return P_Pa / (R_AIRE * T_K)


def propiedades_aire(T_K: float, P_Pa: float = 101325.0) -> dict[str, float]:
    """Devuelve todas las propiedades del aire seco a (T, P) en un dict.

    Conveniencia para los solvers de colector, que necesitan k, μ, Pr, cp y ρ
    en el mismo nodo.

    Args:
        T_K: Temperatura [K].
        P_Pa: Presión absoluta [Pa].

    Returns:
        dict con claves ``k``, ``mu``, ``pr``, ``cp``, ``rho``, ``beta``
        (todas SI).
    """
    return {
        "k": k_aire(T_K),
        "mu": mu_aire(T_K),
        "pr": pr_aire(T_K),
        "cp": cp_aire(T_K),
        "rho": rho_aire(T_K, P_Pa),
        "beta": beta_aire(T_K),
    }
