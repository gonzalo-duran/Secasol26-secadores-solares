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

Nota: las cuatro conversiones de acimut viven ahora en
``calculos/conversiones_angulo.py`` (matemática pura, también la consume la
capa de cálculo) y se re-exportan acá por compatibilidad con los consumidores
históricos de la UI.
"""

from __future__ import annotations

# Re-export por compatibilidad: la fuente de verdad es calculos/conversiones_angulo.py.
from calculos.conversiones_angulo import (  # noqa: F401
    acimut_duffie_a_pvlib,
    acimut_duffie_a_ui360,
    acimut_pvlib_a_duffie,
    acimut_ui360_a_duffie,
)

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
# Ángulos: ver calculos/conversiones_angulo.py (re-exportadas arriba).
# ---------------------------------------------------------------------------
