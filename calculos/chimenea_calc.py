"""Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.

Modelo cuasi-estacionario unidimensional. La chimenea induce flujo natural
por diferencia de densidad entre la columna de aire caliente (cámara + chimenea)
y la atmósfera circundante. El caudal de equilibrio se obtiene cuando el tiro
disponible iguala las pérdidas totales del lazo.

Fenómenos modelados:
- Tiro térmico (stack effect): ΔP_tiro = g·H_eff·(ρ_amb − ρ_chim).
- Fricción en el ducto de chimenea: Darcy-Weisbach con Haaland.
- Pérdidas singulares de entrada y salida (K bundleado por defecto = 1.5).
- Extractor eólico opcional en el tope (turbina sombrero chino): agrega un
  término motriz ΔP = Cp·ρ_amb·v_viento²/2 al balance, donde v_viento se
  corrige del valor NASA POWER (10 m) a la altura del tope via perfil
  logarítmico. La turbina también introduce una resistencia adicional al
  flujo Kt·ρ_chim·v_extractor²/2.

Convención termodinámica:
- T_chim es la temperatura promedio de la columna ascendente (cámara + chimenea).
- Para prediseño se recomienda T_chim ≈ T_salida_camara (el aire ya pasó por
  el enfriamiento evaporativo en la cámara), no T_salida_colector.
- H_eff = altura_chimenea + altura útil de la cámara (entrada de aire frío
  en la base, salida por la chimenea superior).

API pública:
- `delta_P_tiro_Pa`: tiro térmico disponible.
- `delta_P_turbina_motriz_Pa`: depresión motriz del extractor eólico.
- `delta_P_chimenea_Pa`: pérdida en el ducto (fricción + singulares + turbina).
- `caudal_natural_kgs`: caudal másico de equilibrio del lazo completo.

El módulo es puro: no depende de `core/` ni de `streamlit`. Toma primitivas
para mantenerse testeable y reusable desde cualquier capa.
"""

from __future__ import annotations

import math
from math import pi
from typing import Optional

from scipy.optimize import brentq

# _factor_friccion_haaland es interno a motor_calc pero esta es la misma
# implementación que necesitamos; reusarla evita duplicar código y mantiene
# coherencia con las pérdidas del colector y de la cámara.
from calculos.motor_calc import (
    _factor_friccion_haaland as _haaland,
)
from calculos.motor_calc import (
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

# Altura de referencia del viento NASA POWER (estándar meteorológico) [m].
_Z_REF_VIENTO_M: float = 10.0


# ---------------------------------------------------------------------------
# Perfil logarítmico de viento (capa límite atmosférica)
# ---------------------------------------------------------------------------


def _v_viento_a_altura(v_10m_ms: float, z_m: float, z0_m: float = 0.05) -> float:
    """Corrige el viento medido a 10 m a una altura ``z`` via perfil logarítmico.

    Perfil de capa límite neutra (Monin-Obukhov simplificado):

        v(z) = v(10) · ln(z/z₀) / ln(10/z₀)

    Args:
        v_10m_ms: Velocidad del viento a 10 m sobre el suelo [m/s] (estándar
            NASA POWER y la mayoría de las estaciones meteorológicas).
        z_m: Altura de interés [m] (tope de la chimenea).
        z0_m: Longitud de rugosidad aerodinámica del terreno [m]. Valores
            típicos: 0.001 (mar/lago), 0.03 (campo abierto/cultivo bajo),
            0.05 (rural medio, default), 0.10-0.25 (suburbano), 0.5-1.0
            (urbano denso, árboles altos).

    Returns:
        v(z) [m/s]. Devuelve 0 si v_10m_ms ≤ 0 o z ≤ z0 (dentro de la capa
        de rugosidad, sin viento útil).
    """
    if v_10m_ms <= 0 or z_m <= z0_m or z0_m <= 0:
        return 0.0
    return v_10m_ms * math.log(z_m / z0_m) / math.log(_Z_REF_VIENTO_M / z0_m)


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
# Extractor eólico — término motriz
# ---------------------------------------------------------------------------


def delta_P_turbina_motriz_Pa(
    v_viento_local_ms: float,
    Cp_turbina: float,
    T_amb_K: float,
    P_amb_Pa: float = 101325.0,
) -> float:
    """Depresión motriz generada por un extractor eólico en su base [Pa].

    Modelo empírico de turbina pasiva tipo "sombrero chino": la rotación de
    los álabes inclinados por la presión dinámica del viento crea depresión
    en la base, succionando aire desde la chimenea hacia afuera.

        ΔP_turbina = Cp · ρ_amb · v_viento² / 2

    La densidad se evalúa a T_amb porque es el aire externo el que mueve la
    turbina (no la columna ascendente caliente).

    Args:
        v_viento_local_ms: Velocidad del viento a la altura del extractor
            (corregida por perfil log si v_NASA es a 10 m) [m/s].
        Cp_turbina: Coeficiente de presión motriz [adim]. Típico 0.3-0.6
            para turbinas comerciales tipo sombrero chino.
        T_amb_K: Temperatura ambiente [K].
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        ΔP_turbina [Pa]. Cero si v_viento o Cp son ≤ 0.
    """
    if v_viento_local_ms <= 0 or Cp_turbina <= 0:
        return 0.0
    rho_amb = densidad_aire(T_amb_K, P_amb_Pa)
    return Cp_turbina * rho_amb * v_viento_local_ms**2 / 2.0


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
    Kt_turbina: float = 0.0,
    diametro_extractor_m: Optional[float] = None,
) -> float:
    """Pérdida de carga en el ducto de chimenea [Pa].

    Incluye fricción (Darcy-Weisbach con Haaland), singulares de entrada+salida
    y, opcionalmente, la resistencia adicional de un extractor eólico montado
    en el tope:

        ΔP_chim   = (f · L/D + K_singular) · ρ_chim · v² / 2
        ΔP_turb_K = Kt · ρ_chim · v_extractor² / 2
        v_extractor = ṁ / (ρ_chim · A_extractor)

    Total = ΔP_chim + ΔP_turb_K. Las propiedades del aire (ρ, μ) se evalúan a
    T_chim (temperatura local dentro de la columna).

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
        Kt_turbina: Coeficiente resistivo del extractor eólico [adim]. 0
            (default) si no hay extractor.
        diametro_extractor_m: Diámetro del extractor [m]. None (default) si
            no hay extractor. Si está, se calcula v_extractor con su área.

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
    dP_ducto = K_total * (rho * v**2) / 2.0

    # Resistencia del extractor (si aplica). Se aplica sobre la velocidad
    # del flujo a través del diámetro propio del extractor (que puede ser
    # mayor o menor que el de la chimenea).
    dP_turbina_K = 0.0
    if Kt_turbina > 0 and diametro_extractor_m is not None and diametro_extractor_m > 0:
        A_ext = pi * (diametro_extractor_m / 2.0) ** 2
        v_ext = m_punto_kgs / (rho * A_ext)
        dP_turbina_K = Kt_turbina * (rho * v_ext**2) / 2.0

    return dP_ducto + dP_turbina_K


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
    extractor_activo: bool = False,
    Cp_turbina: float = 0.0,
    Kt_turbina: float = 0.0,
    diametro_extractor_m: Optional[float] = None,
    z0_terreno_m: float = 0.05,
    v_viento_10m_ms: float = 0.0,
) -> dict:
    """Caudal másico de equilibrio del lazo con chimenea solar [kg/s].

    Resuelve la ecuación de equilibrio motriz vs resistiva:

        ΔP_tiro_térmico + ΔP_turbina_motriz = ΔP_chimenea(ṁ) + ΔP_resto(ṁ)

    donde:
        ΔP_chimenea = fricción + singulares + Kt·turbina (función de ṁ)
        ΔP_resto    = colector + cámara + ductos + singulares (función de ṁ)

    El término ΔP_turbina_motriz aparece sólo si ``extractor_activo``. La
    temperatura T_chim se toma como dato; el acoplamiento térmico completo
    (T_chim depende de ṁ) requiere iteración externa sobre esta función.

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
        extractor_activo: Si True, se modela un extractor eólico en el tope.
        Cp_turbina: Coeficiente de presión motriz del extractor [adim].
        Kt_turbina: Coeficiente resistivo del extractor [adim].
        diametro_extractor_m: Diámetro del extractor [m]. Obligatorio si
            ``extractor_activo``.
        z0_terreno_m: Rugosidad aerodinámica del terreno [m] para corregir
            v_viento por perfil logarítmico.
        v_viento_10m_ms: Velocidad del viento a 10 m (NASA POWER) [m/s].

    Returns:
        Dict con:
            - ``m_punto_kgs``: caudal másico de equilibrio.
            - ``v_chim_ms``: velocidad media en la chimenea.
            - ``delta_P_tiro_Pa``: tiro térmico disponible.
            - ``delta_P_turbina_motriz_Pa``: depresión motriz del extractor
              (0 si no hay extractor).
            - ``delta_P_chimenea_Pa``: pérdida en el ducto de chimenea
              (incluye Kt del extractor si aplica).
            - ``delta_P_resto_Pa``: pérdida en el resto del lazo.
            - ``Re_chimenea``: Reynolds en la chimenea.
            - ``H_eff_m``: altura efectiva usada.
            - ``v_viento_local_ms``: velocidad de viento corregida a la
              altura del tope (0 si no hay extractor).
            - ``advertencias``: lista de códigos.

    Raises:
        ValueError: Si el bracket de brentq no encierra la raíz (lazo muy
            restrictivo o caudal de equilibrio fuera de ``[_M_MIN_KGS, _M_MAX_KGS]``).
    """
    H_eff = altura_chim_m + H_camara_m
    dPT_termico = delta_P_tiro_Pa(T_amb_K, T_chim_K, H_eff, P_amb_Pa)
    advertencias: list[str] = []

    # Componente motriz del extractor (si aplica). El viento se evalúa a la
    # altura del tope de la chimenea = H_camara + altura_chim.
    if extractor_activo:
        z_top = H_camara_m + altura_chim_m
        v_loc = _v_viento_a_altura(v_viento_10m_ms, z_top, z0_terreno_m)
        dPT_turbina = delta_P_turbina_motriz_Pa(v_loc, Cp_turbina, T_amb_K, P_amb_Pa)
        Kt_eff = Kt_turbina
        d_ext_eff = diametro_extractor_m
    else:
        v_loc = 0.0
        dPT_turbina = 0.0
        Kt_eff = 0.0
        d_ext_eff = None

    dPT_total = dPT_termico + dPT_turbina

    # Caso sin tiro motriz: ni térmico ni eólico.
    if dPT_total <= 0.0:
        return {
            "m_punto_kgs": 0.0,
            "v_chim_ms": 0.0,
            "delta_P_tiro_Pa": dPT_termico,
            "delta_P_turbina_motriz_Pa": dPT_turbina,
            "delta_P_chimenea_Pa": 0.0,
            "delta_P_resto_Pa": 0.0,
            "Re_chimenea": 0.0,
            "H_eff_m": H_eff,
            "v_viento_local_ms": v_loc,
            "advertencias": [
                "CHIM_SIN_TIRO: T_chim ≤ T_amb y sin viento útil — no hay flujo natural."
            ],
        }

    def residuo(m: float) -> float:
        dPC = delta_P_chimenea_Pa(
            m,
            T_chim_K,
            diametro_chim_m,
            altura_chim_m,
            P_amb_Pa,
            rugosidad_m,
            K_singular_chim,
            Kt_turbina=Kt_eff,
            diametro_extractor_m=d_ext_eff,
        )
        dPR = float(delta_P_resto_fn(m))
        return dPT_total - dPC - dPR

    m_eq = brentq(residuo, _M_MIN_KGS, _M_MAX_KGS, xtol=1e-8, rtol=1e-6)

    rho_chim = densidad_aire(T_chim_K, P_amb_Pa)
    A_chim = pi * (diametro_chim_m / 2.0) ** 2
    v_chim = m_eq / (rho_chim * A_chim)
    mu_chim = viscosidad_aire(T_chim_K)
    Re = rho_chim * v_chim * diametro_chim_m / mu_chim
    dPC_eq = delta_P_chimenea_Pa(
        m_eq,
        T_chim_K,
        diametro_chim_m,
        altura_chim_m,
        P_amb_Pa,
        rugosidad_m,
        K_singular_chim,
        Kt_turbina=Kt_eff,
        diametro_extractor_m=d_ext_eff,
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
        "delta_P_tiro_Pa": float(dPT_termico),
        "delta_P_turbina_motriz_Pa": float(dPT_turbina),
        "delta_P_chimenea_Pa": float(dPC_eq),
        "delta_P_resto_Pa": float(dPR_eq),
        "Re_chimenea": float(Re),
        "H_eff_m": float(H_eff),
        "v_viento_local_ms": float(v_loc),
        "advertencias": advertencias,
    }
