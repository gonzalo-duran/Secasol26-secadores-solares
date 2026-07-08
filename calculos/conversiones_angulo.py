"""Conversiones puras entre las tres convenciones de acimut del proyecto.

Estas funciones son **matemática pura de ángulos** (sin estado, sin Streamlit,
sin pandas/numpy): convierten un acimut entre las convenciones Duffie & Beckman,
UI360 y pvlib. Viven en ``calculos/`` —y no en ``ui/componentes/unidades.py``—
porque las consume tanto la UI (widgets de P2/P3, reporte) como la capa de
cálculo (``clima_calc`` para la transposición POA, y el catálogo de barridos
paramétricos). ``ui/componentes/unidades.py`` las re-exporta por compatibilidad.

Las tres convenciones (ver también CLAUDE.md):
    Duffie & Beckman (almacenamiento interno, ``core/emplazamiento.py``):
        acimut γ: 0°=Sur, +90°=Oeste, −90°=Este, ±180°=Norte. Rango [−180, +180].
    UI360 (widget de usuario en P2):
        acimut α: 0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0, 360).
    pvlib (cálculo interno de irradiancia):
        surface_azimuth ψ: 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste. Rango [0, 360).

    Conversiones:
        Duffie → UI360:  α = (−γ) mod 360
        UI360  → Duffie: γ = (−α) mod 360; si γ > 180: γ −= 360
        Duffie → pvlib:  ψ = (180 + γ) mod 360
        pvlib  → Duffie: γ = (ψ − 180) mod 360; si γ > 180: γ −= 360
"""

from __future__ import annotations


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
    return (180.0 + float(acimut_duffie_deg)) % 360.0


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
    return (-float(acimut_duffie_deg)) % 360.0


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
    resultado = (-float(acimut_ui360_deg)) % 360.0
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
    resultado = (float(acimut_pvlib_deg) - 180.0) % 360.0
    if resultado > 180.0:
        resultado -= 360.0
    return resultado


def normalizar_acimut_duffie(acimut_duffie_deg: float) -> float:
    """Envuelve un acimut Duffie arbitrario al rango canónico (−180, +180].

    Útil para derivar el acimut de caras rotadas (p. ej. ``γ + 90``,
    ``γ + 180``) que pueden caer fuera del rango de almacenamiento.

    Args:
        acimut_duffie_deg: Acimut en convención Duffie [°], cualquier rango.

    Returns:
        Acimut en convención Duffie [°], rango (−180, +180].
    """
    resultado = float(acimut_duffie_deg) % 360.0
    if resultado > 180.0:
        resultado -= 360.0
    return resultado
