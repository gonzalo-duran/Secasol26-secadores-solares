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
        albedo_suelo: Reflectancia solar (onda corta) de la superficie que rodea
            al colector [adim], rango [0, 1]. Alimenta la componente reflejada
            del suelo en la transposición POA (``GHI·ρ·(1−cos β)/2``). Relevante
            para colectores inclinados/verticales. Default 0.25 (valor histórico
            de pvlib). Ver ``calculos/catalogo_albedos.py`` para superficies
            usuales.
        z0_terreno_m: Longitud de rugosidad aerodinámica del terreno [m]. Fija
            la forma del perfil logarítmico de viento
            (``calculos/perfil_viento.py``) y por lo tanto la conversión de la
            velocidad entre alturas. La consumen la ingesta de clima medido
            (normaliza el anemómetro a los 2 m del contrato de ``Clima``) y el
            extractor eólico de la chimenea (lleva el viento al tope). Es una
            propiedad **del sitio**, como el albedo: vive acá y no en la
            chimenea (S57). Default 0.05 (rural medio). Ver
            ``calculos/catalogo_rugosidades.py``.
    """

    latitud_deg: float = -24.72
    longitud_deg: float = -65.41
    altitud_m: float = 1187.0
    acimut_colector_deg: float = 180.0
    pendiente_colector_deg: float = 25.0
    zona_horaria: str = "America/Argentina/Salta"
    albedo_suelo: float = 0.25
    z0_terreno_m: float = 0.05

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
        if not (0.0 <= self.albedo_suelo <= 1.0):
            raise ValueError(
                f"EMPL_ALBEDO_INVALIDO: albedo_suelo {self.albedo_suelo:.3f} "
                "fuera del rango válido [0, 1] (reflectancia solar adimensional)."
            )
        # El perfil logarítmico exige z0 > 0 (aparece en ln(z/z0)) y z0 < 2 m para
        # que la altura de referencia del contrato de Clima quede por encima de la
        # capa de rugosidad. El máximo tabulado (urbano denso/bosque) es 0.5 m.
        if not (0.0 < self.z0_terreno_m < 2.0):
            raise ValueError(
                f"EMPL_Z0_TERRENO_INVALIDO: z0_terreno_m {self.z0_terreno_m:.4f} m "
                "fuera del rango válido (0, 2) m. Valores usuales: 0.001 (mar) a "
                "0.5 (urbano denso)."
            )
        try:
            zoneinfo.ZoneInfo(self.zona_horaria)
        except (zoneinfo.ZoneInfoNotFoundError, KeyError, ValueError):
            raise ValueError(
                f"EMPL_ZONA_HORARIA_INVALIDA: '{self.zona_horaria}' no es un "
                "identificador IANA de zona horaria válido."
            )
