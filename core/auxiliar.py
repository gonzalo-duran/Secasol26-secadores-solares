"""
Dataclasses del sistema de calentamiento auxiliar.

El auxiliar es opcional (Proyecto.auxiliar puede ser None).
Puede operar en serie después del colector (SERIE_POSCOLECTOR) o como
fuente independiente (RESPALDO_INDEPENDIENTE).

Tipos soportados en v0: resistencia eléctrica y quemador de biomasa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.advertencias import Advertencia, Severidad

# ---------------------------------------------------------------------------
# Límites físicos
# ---------------------------------------------------------------------------

_T_MAX_SALIDA_MIN_K: float = 273.15  # 0 °C
_T_MAX_SALIDA_MAX_K: float = 473.15  # 200 °C
_T_ALTA_PRODUCTO_K: float = 343.15  # 70 °C — umbral de advertencia
_ETA_QUEMADOR_BAJA: float = 0.50  # umbral de eficiencia baja


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TipoAuxiliar(Enum):
    RESISTENCIA_ELECTRICA = "RESISTENCIA_ELECTRICA"
    QUEMADOR_BIOMASA = "QUEMADOR_BIOMASA"


class ModoOperacionAuxiliar(Enum):
    SERIE_POSCOLECTOR = "SERIE_POSCOLECTOR"
    RESPALDO_INDEPENDIENTE = "RESPALDO_INDEPENDIENTE"


# ---------------------------------------------------------------------------
# Calendario de arranque (híbrido solar-biomasa estilo ADITAL)
# ---------------------------------------------------------------------------


@dataclass
class CargaArranque:
    """Una carga de combustible programada en una hora del día.

    Modela el uso del quemador como "arranque" en los bordes del día: el
    operario carga leña a la mañana (antes/al amanecer) y al atardecer, cuando
    el aporte solar es bajo o nulo. Durante esas ventanas el auxiliar opera; el
    resto de la jornada queda apagado (el colector cubre el mediodía).

    Attributes:
        hora_inicio_h: Hora del día de inicio de la carga [h], 0–24.
        duracion_h: Duración de la ventana de operación [h] (> 0).
    """

    hora_inicio_h: float
    duracion_h: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.hora_inicio_h < 24.0):
            raise ValueError(
                f"ARRANQUE_HORA_FUERA_RANGO: hora_inicio_h={self.hora_inicio_h:.2f} " "∉ [0, 24)."
            )
        if self.duracion_h <= 0:
            raise ValueError(
                f"ARRANQUE_DURACION_NO_POSITIVA: duracion_h={self.duracion_h:.2f} h ≤ 0."
            )


# ---------------------------------------------------------------------------
# Dataclass principal
# ---------------------------------------------------------------------------


@dataclass
class Auxiliar:
    """Sistema de calentamiento auxiliar del secador solar.

    Almacenado en Proyecto.auxiliar. Es None si el secador no tiene auxiliar.

    Attributes:
        tipo: Tipo de fuente de calor auxiliar.
        modo_operacion: Si opera en serie con el colector o como respaldo independiente.
        potencia_nominal_W: Potencia térmica nominal entregada al aire [W].
            Para resistencia eléctrica: potencia eléctrica ≈ potencia térmica (η ≈ 1).
            Para quemador: potencia_térmica = PCI × flujo × η_quemador.
        temperatura_maxima_salida_K: T máxima del aire a la salida [K].
            Límite de seguridad para proteger el producto.
        set_point_T_K: Temperatura objetivo de salida [K]. None = operación a
            potencia constante (sin control de temperatura).
        fraccion_potencia_operacion: Fracción de la potencia nominal en operación [0,1].
        disponible_nocturno: True si el auxiliar puede operar fuera del horario solar.
        tipo_biomasa: Nombre del combustible (string libre). Solo para quemador.
        PCI_MJ_kg: Poder calorífico inferior [MJ/kg]. Solo para quemador.
        eficiencia_quemador: Rendimiento térmico del quemador [fracción]. Solo para quemador.
        consumo_biomasa_kg_h: Override de consumo [kg/h]. Calcula automáticamente si None.
        tension_V: Tensión de alimentación [V]. Solo para resistencia eléctrica.
        corriente_maxima_A: Corriente máxima [A]. Solo para resistencia eléctrica.
        notas: Campo libre de observaciones.
    """

    tipo: TipoAuxiliar = TipoAuxiliar.RESISTENCIA_ELECTRICA
    modo_operacion: ModoOperacionAuxiliar = ModoOperacionAuxiliar.SERIE_POSCOLECTOR
    potencia_nominal_W: float = 1000.0
    temperatura_maxima_salida_K: float = 343.15  # 70 °C
    set_point_T_K: Optional[float] = None
    fraccion_potencia_operacion: float = 1.0
    disponible_nocturno: bool = False

    # Quemador de biomasa
    tipo_biomasa: Optional[str] = None
    PCI_MJ_kg: Optional[float] = None
    eficiencia_quemador: Optional[float] = None
    consumo_biomasa_kg_h: Optional[float] = None

    # Resistencia eléctrica
    tension_V: Optional[float] = None
    corriente_maxima_A: Optional[float] = None

    # Calendario de arranque (híbrido mañana/tarde). Vacío → opera por día
    # (I_g) como hasta ahora; con cargas → opera solo en esas ventanas horarias.
    cargas_arranque: list[CargaArranque] = field(default_factory=list)

    notas: str = ""

    def __post_init__(self) -> None:
        # --- Errores duros ---
        if self.potencia_nominal_W <= 0:
            raise ValueError(
                f"AUX_POTENCIA_NO_POSITIVA: potencia_nominal_W={self.potencia_nominal_W:.1f} W ≤ 0."
            )
        if not (_T_MAX_SALIDA_MIN_K <= self.temperatura_maxima_salida_K <= _T_MAX_SALIDA_MAX_K):
            Tc = self.temperatura_maxima_salida_K - 273.15
            raise ValueError(
                f"AUX_T_MAX_SALIDA_INVALIDA: temperatura_maxima_salida_K="
                f"{self.temperatura_maxima_salida_K:.2f} K ({Tc:.1f} °C) fuera del rango "
                f"operativo para secado de alimentos (0–200 °C)."
            )
        if self.set_point_T_K is not None and self.set_point_T_K > self.temperatura_maxima_salida_K:
            raise ValueError(
                f"AUX_SET_POINT_EXCEDE_T_MAX: set_point={self.set_point_T_K:.2f} K "
                f"> T_max={self.temperatura_maxima_salida_K:.2f} K."
            )
        if not (0.0 <= self.fraccion_potencia_operacion <= 1.0):
            raise ValueError(
                f"AUX_FRACCION_INVALIDA: fraccion_potencia_operacion="
                f"{self.fraccion_potencia_operacion:.3f} fuera del rango [0, 1]."
            )
        if self.tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
            if self.PCI_MJ_kg is None and self.consumo_biomasa_kg_h is None:
                raise ValueError(
                    "AUX_BIOMASA_SIN_PCI: quemador de biomasa requiere "
                    "PCI_MJ_kg o consumo_biomasa_kg_h."
                )
            if self.PCI_MJ_kg is not None and self.eficiencia_quemador is None:
                raise ValueError(
                    "AUX_BIOMASA_SIN_EFICIENCIA: si se especifica PCI_MJ_kg "
                    "también se requiere eficiencia_quemador."
                )

    def potencia_efectiva_W(self) -> float:
        """Potencia térmica efectiva entregada al aire [W].

        Returns:
            potencia_nominal_W × fraccion_potencia_operacion.
        """
        return self.potencia_nominal_W * self.fraccion_potencia_operacion

    def consumo_biomasa_efectivo_kg_h(self) -> Optional[float]:
        """Consumo de biomasa en operación [kg/h].

        Si consumo_biomasa_kg_h está definido lo devuelve directamente.
        Si están definidos PCI y eficiencia, lo calcula como:
            consumo = potencia_efectiva_W × 3600 / (PCI_MJ_kg × 1e6 × η)

        Returns:
            Consumo en kg/h, o None si faltan datos.
        """
        if self.tipo != TipoAuxiliar.QUEMADOR_BIOMASA:
            return None
        if self.consumo_biomasa_kg_h is not None:
            return self.consumo_biomasa_kg_h * self.fraccion_potencia_operacion
        if self.PCI_MJ_kg is not None and self.eficiencia_quemador is not None:
            return (
                self.potencia_efectiva_W()
                * 3600.0
                / (self.PCI_MJ_kg * 1e6 * self.eficiencia_quemador)
            )
        return None

    def tiene_calendario_arranque(self) -> bool:
        """True si el auxiliar opera por calendario de arranque (mañana/tarde)."""
        return bool(self.cargas_arranque)


# ---------------------------------------------------------------------------
# Advertencias estáticas
# ---------------------------------------------------------------------------


def advertencias_auxiliar(auxiliar: Auxiliar) -> list[Advertencia]:
    """Genera advertencias de diseño no bloqueantes para el sistema auxiliar.

    Args:
        auxiliar: Instancia de Auxiliar completamente inicializada.

    Returns:
        Lista de Advertencia, vacía si el diseño es correcto.
    """
    adv: list[Advertencia] = []

    # T_max alta para producto sensible
    if auxiliar.temperatura_maxima_salida_K > _T_ALTA_PRODUCTO_K:
        Tc = auxiliar.temperatura_maxima_salida_K - 273.15
        adv.append(
            Advertencia(
                codigo="AUX_T_MAX_ALTA_PARA_PRODUCTO",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Temperatura máxima de salida del auxiliar {Tc:.1f} °C puede dañar "
                    "productos sensibles al calor (carotenoides, aceites esenciales, FOS). "
                    "Verificar con la T_max recomendada del producto."
                ),
                campo="temperatura_maxima_salida_K",
                sugerencia="Reducir T_max o verificar compatibilidad con el producto a secar.",
                contexto={"T_max_C": round(Tc, 1), "umbral_C": _T_ALTA_PRODUCTO_K - 273.15},
            )
        )

    # Biomasa con eficiencia baja
    if (
        auxiliar.tipo == TipoAuxiliar.QUEMADOR_BIOMASA
        and auxiliar.eficiencia_quemador is not None
        and auxiliar.eficiencia_quemador < _ETA_QUEMADOR_BAJA
    ):
        adv.append(
            Advertencia(
                codigo="AUX_BIOMASA_EFICIENCIA_BAJA",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Eficiencia del quemador {auxiliar.eficiencia_quemador:.0%} muy baja. "
                    "Quemadores simples tipo rocket alcanzan 60–75%."
                ),
                campo="eficiencia_quemador",
                sugerencia=(
                    "Mejorar diseño del quemador: precalentamiento de aire de combustión, "
                    "aislación del cuerpo del quemador."
                ),
                contexto={"eficiencia": auxiliar.eficiencia_quemador, "umbral": _ETA_QUEMADOR_BAJA},
            )
        )

    # Resistencia sin tensión
    if auxiliar.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA and auxiliar.tension_V is None:
        adv.append(
            Advertencia(
                codigo="AUX_RESISTENCIA_SIN_TENSION",
                severidad=Severidad.INFO,
                mensaje=(
                    "Tensión de alimentación no especificada. No se calculará "
                    "corriente máxima para el dimensionamiento eléctrico."
                ),
                campo="tension_V",
                sugerencia="Especificar tension_V (220 o 380 V) para calcular la corriente nominal.",
                contexto={},
            )
        )

    # Respaldo independiente no disponible nocturno
    if (
        auxiliar.modo_operacion == ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE
        and not auxiliar.disponible_nocturno
    ):
        adv.append(
            Advertencia(
                codigo="AUX_RESPALDO_SIN_DISPONIBILIDAD_NOCTURNA",
                severidad=Severidad.INFO,
                mensaje=(
                    "Auxiliar en modo RESPALDO_INDEPENDIENTE marcado como no disponible nocturno. "
                    "El modo respaldo se usa habitualmente para extender el secado fuera "
                    "del horario solar."
                ),
                campo="disponible_nocturno",
                sugerencia=(
                    "Verificar si es intencional. Si el auxiliar puede operar de noche, "
                    "activar disponible_nocturno=True."
                ),
                contexto={},
            )
        )

    return adv
