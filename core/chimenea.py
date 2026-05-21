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

_CHIM_D_MIN_M: float = 0.10  # diámetro mínimo recomendado [m]
_CHIM_H_MIN_M: float = 1.0  # altura mínima recomendada [m]
_V_VIENTO_EXTRACTOR_BAJA_MS: float = 2.0  # advertencia: extractor poco efectivo


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Chimenea:
    """Chimenea solar para inducir convección natural.

    El material se selecciona del catálogo de fondos (materiales estructurales).
    El diámetro y la altura determinan el tiraje disponible (modelo físico
    en ``calculos.chimenea_calc``).

    Opcionalmente puede equiparse con un extractor eólico (turbina pasiva tipo
    "sombrero chino") montado en el tope, que agrega un término motriz
    proporcional a v_viento² en el balance de presiones del lazo natural y
    un término resistivo pequeño cuando el flujo la atraviesa.

    Attributes:
        diametro_m: Diámetro interno de la chimenea [m].
        altura_m: Altura de la chimenea sobre la cámara de secado [m].
        id_material: Identificador del material en fondos.yaml.
        extractor_activo: Si True, se modela un extractor eólico montado en el
            tope. Requiere ``diametro_extractor_m``. Default: False.
        diametro_extractor_m: Diámetro del extractor [m]. Obligatorio si
            extractor_activo. Típicamente igual o algo mayor al diámetro de la
            chimenea (10–60 cm en turbinas comerciales).
        Cp_turbina: Coeficiente de presión motriz [adim]. La depresión generada
            por la turbina en su base es ΔP = Cp · ρ·v_viento²/2. Default: 0.4
            (turbina sombrero chino típica, rango usual 0.3–0.6).
        Kt_turbina: Coeficiente resistivo de la turbina [adim], aplicado como
            Kt·ρ·v_flujo²/2 sobre la velocidad del flujo en la chimenea.
            Default: 1.0 (expansión + obstrucción de álabes).
        z0_terreno_m: Rugosidad aerodinámica del terreno [m] para corregir el
            viento NASA POWER (medido a 10 m) a la altura del tope de la
            chimenea via perfil logarítmico. Default: 0.05 (terreno rural medio).
    """

    diametro_m: float = 0.20
    altura_m: float = 2.0
    id_material: str = "galvanizada_sin_pintura"
    extractor_activo: bool = False
    diametro_extractor_m: Optional[float] = None
    Cp_turbina: float = 0.4
    Kt_turbina: float = 1.0
    z0_terreno_m: float = 0.05

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
        if self.extractor_activo:
            if self.diametro_extractor_m is None or self.diametro_extractor_m <= 0:
                raise ValueError(
                    "CHIM_EXTRACTOR_SIN_DIAMETRO: extractor activo requiere "
                    "diametro_extractor_m > 0."
                )
            if not (0.0 < self.Cp_turbina <= 2.0):
                raise ValueError(
                    f"CHIM_CP_TURBINA_INVALIDO: Cp_turbina={self.Cp_turbina:.3f} "
                    "fuera del rango (0, 2]. Rango físico típico 0.3–0.6."
                )
            if self.Kt_turbina < 0:
                raise ValueError(
                    f"CHIM_KT_TURBINA_INVALIDO: Kt_turbina={self.Kt_turbina:.3f} " "debe ser ≥ 0."
                )
        if self.z0_terreno_m <= 0:
            raise ValueError(
                f"CHIM_Z0_INVALIDO: z0_terreno_m={self.z0_terreno_m:.4f} m " "debe ser > 0."
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
        adv.append(
            Advertencia(
                codigo="CHIM_DIAMETRO_PEQUENO",
                severidad=Severidad.WARNING,
                mensaje=f"Diámetro de chimenea ({chimenea.diametro_m*100:.0f} cm) < "
                f"{_CHIM_D_MIN_M*100:.0f} cm. Puede ser insuficiente para el tiraje necesario.",
                campo="chimenea.diametro_m",
                sugerencia=f"Usá un diámetro ≥ {_CHIM_D_MIN_M*100:.0f} cm para garantizar tiraje efectivo.",
                contexto={"diametro_m": chimenea.diametro_m, "minimo_m": _CHIM_D_MIN_M},
            )
        )

    if chimenea.altura_m < _CHIM_H_MIN_M:
        adv.append(
            Advertencia(
                codigo="CHIM_ALTURA_PEQUENA",
                severidad=Severidad.WARNING,
                mensaje=f"Altura de chimenea ({chimenea.altura_m:.1f} m) < {_CHIM_H_MIN_M} m. "
                "El tiraje natural puede ser insuficiente para mover el aire.",
                campo="chimenea.altura_m",
                sugerencia=f"Aumentá la altura a ≥ {_CHIM_H_MIN_M} m para asegurar convección natural.",
                contexto={"altura_m": chimenea.altura_m, "minima_m": _CHIM_H_MIN_M},
            )
        )

    if (
        chimenea.extractor_activo
        and chimenea.diametro_extractor_m is not None
        and chimenea.diametro_extractor_m < chimenea.diametro_m
    ):
        adv.append(
            Advertencia(
                codigo="CHIM_EXTRACTOR_DIAMETRO_PEQUENO",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Diámetro del extractor ({chimenea.diametro_extractor_m*100:.0f} cm) "
                    f"< diámetro de chimenea ({chimenea.diametro_m*100:.0f} cm). "
                    "Genera estrangulamiento en el tope, reduce el caudal."
                ),
                campo="chimenea.diametro_extractor_m",
                sugerencia=(
                    "Usar un extractor con diámetro ≥ al de la chimenea para evitar "
                    "estrangular el flujo."
                ),
                contexto={
                    "d_extractor_m": chimenea.diametro_extractor_m,
                    "d_chimenea_m": chimenea.diametro_m,
                },
            )
        )

    return adv
