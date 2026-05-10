"""
Dataclass de emplazamiento geográfico del secador solar.

Los ángulos del colector se almacenan en convención Duffie (acimut 0° = Sur).
La conversión a convención pvlib (0° = Norte) ocurre exclusivamente en
ui/componentes/unidades.py, nunca aquí.
"""

from __future__ import annotations

import zoneinfo
from dataclasses import dataclass


@dataclass
class Emplazamiento:
    """Ubicación geográfica y orientación del colector solar.

    Todos los ángulos se almacenan en convención Duffie & Beckman:
    acimut γ = 0° → Sur; γ > 0 → Oeste; γ < 0 → Este; |γ| = 180° → Norte.

    Attributes:
        latitud_deg: Latitud geográfica [°]. Norte positivo, rango [-90, 90].
        longitud_deg: Longitud geográfica [°]. Este positivo, rango [-180, 180].
        altitud_m: Altitud sobre el nivel del mar [m]. Mínimo aceptado: -500 m.
        acimut_colector_deg: Acimut del colector [°], convención Duffie.
            0° = Sur, +90° = Oeste, -90° = Este, ±180° = Norte.
            Rango: [-180, 180].
        pendiente_colector_deg: Ángulo de inclinación del colector respecto a la
            horizontal [°]. 0° = horizontal, 90° = vertical. Rango: [0, 90].
        zona_horaria: Identificador IANA de zona horaria
            (ej.: 'America/Argentina/Salta').
    """

    latitud_deg: float = -24.72
    longitud_deg: float = -65.41
    altitud_m: float = 1187.0
    acimut_colector_deg: float = 180.0
    pendiente_colector_deg: float = 25.0
    zona_horaria: str = "America/Argentina/Salta"

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitud_deg <= 90.0):
            raise ValueError(
                f"EMPL_LATITUD_INVALIDA: latitud {self.latitud_deg:.4f}° "
                "fuera del rango válido [-90, 90]."
            )
        if not (-180.0 <= self.longitud_deg <= 180.0):
            raise ValueError(
                f"EMPL_LONGITUD_INVALIDA: longitud {self.longitud_deg:.4f}° "
                "fuera del rango válido [-180, 180]."
            )
        if self.altitud_m < -500.0:
            raise ValueError(
                f"EMPL_ALTITUD_INVALIDA: altitud {self.altitud_m:.1f} m "
                "inusualmente baja. Mínimo aceptado: -500 m."
            )
        if not (-180.0 <= self.acimut_colector_deg <= 180.0):
            raise ValueError(
                f"EMPL_ACIMUT_INVALIDO: acimut {self.acimut_colector_deg:.1f}° "
                "fuera del rango válido [-180, 180] (convención Duffie, 0° = Sur)."
            )
        if not (0.0 <= self.pendiente_colector_deg <= 90.0):
            raise ValueError(
                f"EMPL_PENDIENTE_INVALIDA: pendiente {self.pendiente_colector_deg:.1f}° "
                "fuera del rango válido [0, 90]."
            )
        try:
            zoneinfo.ZoneInfo(self.zona_horaria)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError, ValueError):
            raise ValueError(
                f"EMPL_ZONA_HORARIA_INVALIDA: '{self.zona_horaria}' no es un "
                "identificador IANA de zona horaria válido."
            )
