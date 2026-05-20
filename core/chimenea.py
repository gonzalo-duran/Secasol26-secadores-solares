"""Chimenea solar — componente independiente del lazo aerodinámico.

Almacenada en ``Proyecto.chimenea`` (top-level), independiente del colector
porque puede usarse tanto en tipologías con colector externo (ARMARIO,
GRAN_ESCALA) como en CAJA (donde ``Proyecto.colector`` es ``None``).

El modelo numérico del tiro térmico vive en ``calculos.chimenea_calc``.
Este módulo solo define la dataclass de configuración y sus advertencias
estáticas de diseño.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core import catalogo
from core.advertencias import Advertencia, Severidad

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_CHIM_D_MIN_M: float = 0.10     # diámetro mínimo recomendado [m]
_CHIM_H_MIN_M: float = 1.0      # altura mínima recomendada [m]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Chimenea:
    """Chimenea solar para inducir convección natural.

    El material se selecciona del catálogo de fondos (materiales estructurales).
    El diámetro y la altura determinan el tiraje disponible (modelo físico
    en ``calculos.chimenea_calc``).

    Attributes:
        diametro_m: Diámetro interno de la chimenea [m].
        altura_m: Altura de la chimenea sobre la cámara de secado [m].
        id_material: Identificador del material en fondos.yaml.
    """

    diametro_m: float = 0.20
    altura_m: float = 2.0
    id_material: str = "galvanizada_sin_pintura"

    def __post_init__(self) -> None:
        if self.diametro_m <= 0:
            raise ValueError(
                f"CHIM_DIAMETRO_NO_POSITIVO: diámetro {self.diametro_m:.4f} m ≤ 0. "
                "El diámetro interno de la chimenea debe ser positivo."
            )
        if self.altura_m <= 0:
            raise ValueError(
                f"CHIM_ALTURA_NO_POSITIVA: altura {self.altura_m:.2f} m ≤ 0. "
                "La altura de la chimenea debe ser positiva."
            )
        if self.id_material not in catalogo.FONDOS:
            ids = list(catalogo.FONDOS.keys())
            raise ValueError(
                f"CHIM_MATERIAL_NO_ENCONTRADO: '{self.id_material}' no existe en el "
                f"catálogo de materiales estructurales. Disponibles: {ids}."
            )


# ---------------------------------------------------------------------------
# Advertencias estáticas
# ---------------------------------------------------------------------------


def advertencias_chimenea(chimenea: Optional[Chimenea]) -> list[Advertencia]:
    """Genera advertencias estáticas de diseño para la chimenea.

    Args:
        chimenea: Instancia de Chimenea, o None si no hay chimenea configurada.

    Returns:
        Lista de Advertencia (vacía si chimenea es None o si la geometría es
        razonable).
    """
    if chimenea is None:
        return []

    adv: list[Advertencia] = []

    if chimenea.diametro_m < _CHIM_D_MIN_M:
        adv.append(Advertencia(
            codigo="CHIM_DIAMETRO_PEQUENO",
            severidad=Severidad.WARNING,
            mensaje=f"Diámetro de chimenea ({chimenea.diametro_m*100:.0f} cm) < "
                    f"{_CHIM_D_MIN_M*100:.0f} cm. Puede ser insuficiente para el tiraje necesario.",
            campo="chimenea.diametro_m",
            sugerencia=f"Usá un diámetro ≥ {_CHIM_D_MIN_M*100:.0f} cm para garantizar tiraje efectivo.",
            contexto={"diametro_m": chimenea.diametro_m, "minimo_m": _CHIM_D_MIN_M},
        ))

    if chimenea.altura_m < _CHIM_H_MIN_M:
        adv.append(Advertencia(
            codigo="CHIM_ALTURA_PEQUENA",
            severidad=Severidad.WARNING,
            mensaje=f"Altura de chimenea ({chimenea.altura_m:.1f} m) < {_CHIM_H_MIN_M} m. "
                    "El tiraje natural puede ser insuficiente para mover el aire.",
            campo="chimenea.altura_m",
            sugerencia=f"Aumentá la altura a ≥ {_CHIM_H_MIN_M} m para asegurar convección natural.",
            contexto={"altura_m": chimenea.altura_m, "minima_m": _CHIM_H_MIN_M},
        ))

    return adv
