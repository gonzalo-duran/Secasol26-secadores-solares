"""
Conversiones entre unidades de la interfaz de usuario y el SI interno.

Regla de oro del proyecto: todo lo que entra a core/ y calculos/ está en SI.
Esta es la ÚNICA capa de conversión entre la UI y el modelo.

Convenciones de ángulos (tres en total):
    Almacenamiento interno (Duffie & Beckman):
        acimut γ: 0°=Sur, +90°=Oeste, -90°=Este, ±180°=Norte. Rango [−180°, +180°].
        Usado en core/emplazamiento.py.
    UI de usuario (convención geográfica local, rango completo):
        acimut α: 0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0°, 360°).
        Usado en el widget de acimut de p2_emplazamiento.py.
    pvlib (cálculo interno de irradiancia):
        surface_azimuth ψ: 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste. Rango [0°, 360°).
        Usado en calculos/clima_calc.py y pvlib.irradiance.

    Conversiones:
        Duffie → UI360:  α = (−γ) mod 360
        UI360  → Duffie: γ = (−α) mod 360; si γ > 180: γ −= 360
        Duffie → pvlib:  ψ = (180 + γ) mod 360
        pvlib  → Duffie: γ = (ψ − 180) mod 360; si γ > 180: γ −= 360
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Temperatura
# ---------------------------------------------------------------------------


def celsius_a_kelvin(T_C: float) -> float:
    """Convierte temperatura de Celsius a Kelvin.

    Args:
        T_C: Temperatura en grados Celsius.

    Returns:
        Temperatura en Kelvin.
    """
    return T_C + 273.15


def kelvin_a_celsius(T_K: float) -> float:
    """Convierte temperatura de Kelvin a Celsius.

    Args:
        T_K: Temperatura en Kelvin.

    Returns:
        Temperatura en grados Celsius.
    """
    return T_K - 273.15


# ---------------------------------------------------------------------------
# Presión
# ---------------------------------------------------------------------------


def kpa_a_pa(presion_kPa: float) -> float:
    """Convierte presión de kilopascal a pascal.

    Args:
        presion_kPa: Presión en kPa.

    Returns:
        Presión en Pa.
    """
    return presion_kPa * 1000.0


def pa_a_kpa(presion_Pa: float) -> float:
    """Convierte presión de pascal a kilopascal.

    Args:
        presion_Pa: Presión en Pa.

    Returns:
        Presión en kPa.
    """
    return presion_Pa / 1000.0


def pa_a_hpa(presion_Pa: float) -> float:
    """Convierte presión de pascal a hectopascal (equivalente a mbar).

    Args:
        presion_Pa: Presión en Pa.

    Returns:
        Presión en hPa.
    """
    return presion_Pa / 100.0


# ---------------------------------------------------------------------------
# Humedad relativa
# ---------------------------------------------------------------------------


def porcentaje_a_fraccion(porcentaje: float) -> float:
    """Convierte humedad relativa de porcentaje a fracción adimensional.

    Args:
        porcentaje: Humedad relativa en % (rango 0–100).

    Returns:
        Humedad relativa como fracción (rango 0–1).
    """
    return porcentaje / 100.0


def fraccion_a_porcentaje(fraccion: float) -> float:
    """Convierte humedad relativa de fracción adimensional a porcentaje.

    Args:
        fraccion: Humedad relativa como fracción (rango 0–1).

    Returns:
        Humedad relativa en % (rango 0–100).
    """
    return fraccion * 100.0


# ---------------------------------------------------------------------------
# Ángulos: convención Duffie ↔ pvlib
# ---------------------------------------------------------------------------


def acimut_duffie_a_pvlib(acimut_duffie_deg: float) -> float:
    """Convierte acimut superficial de convención Duffie a convención pvlib.

    Duffie (almacenamiento y UI):
        0° = Sur, +90° = Oeste, −90° = Este, ±180° = Norte. Rango [−180, +180].
    pvlib (cálculo interno):
        0° = Norte, 90° = Este, 180° = Sur, 270° = Oeste. Rango [0, 360).

    Fórmula: ψ = (180 + γ) mod 360.

    Ejemplos de verificación:
        γ =   0° (Sur)   → ψ = 180° (Sur)   ✓
        γ =  90° (Oeste) → ψ = 270° (Oeste) ✓
        γ = −90° (Este)  → ψ =  90° (Este)  ✓
        γ = 180° (Norte) → ψ =   0° (Norte) ✓

    Args:
        acimut_duffie_deg: Acimut superficial en convención Duffie [°].

    Returns:
        Acimut superficial en convención pvlib [°], rango [0, 360).
    """
    return (180.0 + acimut_duffie_deg) % 360.0


def acimut_duffie_a_ui360(acimut_duffie_deg: float) -> float:
    """Convierte acimut de convención Duffie a convención UI360.

    Duffie (almacenamiento):
        0°=Sur, +90°=Oeste, −90°=Este, ±180°=Norte. Rango [−180, +180].
    UI360 (widget de usuario):
        0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0, 360).

    Fórmula: α = (−γ) mod 360.

    Ejemplos:
        γ =   0° (Sur)   → α =   0° ✓
        γ = −90° (Este)  → α =  90° ✓
        γ = 180° (Norte) → α = 180° ✓
        γ =  90° (Oeste) → α = 270° ✓

    Args:
        acimut_duffie_deg: Acimut en convención Duffie [°].

    Returns:
        Acimut en convención UI360 [°], rango [0, 360).
    """
    return (-acimut_duffie_deg) % 360.0


def acimut_ui360_a_duffie(acimut_ui360_deg: float) -> float:
    """Convierte acimut de convención UI360 a convención Duffie.

    UI360 (widget de usuario):
        0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0, 360).
    Duffie (almacenamiento):
        0°=Sur, +90°=Oeste, −90°=Este, ±180°=Norte. Rango [−180, +180].

    Fórmula: γ = (−α) mod 360; si γ > 180: γ −= 360.

    Args:
        acimut_ui360_deg: Acimut en convención UI360 [°].

    Returns:
        Acimut en convención Duffie [°], rango (−180, +180].
    """
    resultado = (-acimut_ui360_deg) % 360.0
    if resultado > 180.0:
        resultado -= 360.0
    return resultado


def acimut_pvlib_a_duffie(acimut_pvlib_deg: float) -> float:
    """Convierte acimut superficial de convención pvlib a convención Duffie.

    pvlib (cálculo interno):
        0° = Norte, 90° = Este, 180° = Sur, 270° = Oeste. Rango [0, 360).
    Duffie (almacenamiento y UI):
        0° = Sur, +90° = Oeste, −90° = Este, ±180° = Norte. Rango (−180, +180].

    Fórmula: γ = ((ψ − 180) mod 360), luego γ -= 360 si γ > 180.

    Args:
        acimut_pvlib_deg: Acimut superficial en convención pvlib [°].

    Returns:
        Acimut superficial en convención Duffie [°], rango (−180, +180].
    """
    resultado = (acimut_pvlib_deg - 180.0) % 360.0
    if resultado > 180.0:
        resultado -= 360.0
    return resultado
