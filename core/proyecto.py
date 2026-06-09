"""
Dataclasses raíz del proyecto: Meta, Configuracion y Proyecto.

Proyecto es el objeto raíz almacenado en st.session_state.proyecto.
Contiene todas las secciones de entrada y el espejo de Resultados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

VERSION_SOFTWARE = "0.12.0"


class Tipologia(Enum):
    CAJA = "CAJA"
    ARMARIO = "ARMARIO"
    GRAN_ESCALA = "GRAN_ESCALA"


class ModoAnalisis(Enum):
    DIARIO = "DIARIO"
    ANUAL = "ANUAL"


class DiaAnalisis(Enum):
    ESPECIFICO = "ESPECIFICO"
    MAS_FRIO = "MAS_FRIO"
    MAS_CALUROSO = "MAS_CALUROSO"
    SOLSTICIO_VERANO = "SOLSTICIO_VERANO"
    SOLSTICIO_INVIERNO = "SOLSTICIO_INVIERNO"
    EQUINOCCIO_MARZO = "EQUINOCCIO_MARZO"
    EQUINOCCIO_SEPTIEMBRE = "EQUINOCCIO_SEPTIEMBRE"


@dataclass
class Meta:
    """Metadatos administrativos del proyecto.

    Attributes:
        nombre: Nombre descriptivo del proyecto.
        autor: Nombre del autor o responsable.
        fecha_creacion: Fecha de creación del proyecto.
        fecha_modificacion: Fecha de la última modificación.
        version_software: Versión del software al momento de creación.
        notas: Notas libres del usuario.
    """

    nombre: str = "Nuevo proyecto"
    autor: str = ""
    fecha_creacion: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    fecha_modificacion: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    version_software: str = VERSION_SOFTWARE
    notas: str = ""


@dataclass
class Configuracion:
    """Configuración general del análisis.

    Attributes:
        tipologia: Tipo de secador (CAJA, ARMARIO, GRAN_ESCALA).
        modo_analisis: Análisis diario o anual.
        dia_analisis: Criterio de selección del día (solo para modo DIARIO).
        fecha_especifica: Fecha concreta (solo si dia_analisis == ESPECIFICO).
    """

    tipologia: Tipologia = Tipologia.ARMARIO
    modo_analisis: ModoAnalisis = ModoAnalisis.DIARIO
    dia_analisis: DiaAnalisis = DiaAnalisis.SOLSTICIO_VERANO
    fecha_especifica: Optional[date] = None

    def __post_init__(self) -> None:
        if self.modo_analisis == ModoAnalisis.ANUAL and self.tipologia == Tipologia.CAJA:
            raise ValueError(
                "PROY_ANUAL_SIN_VECTORIZACION: el análisis anual no está implementado "
                "para tipología CAJA en v0."
            )
        if self.dia_analisis == DiaAnalisis.ESPECIFICO and self.fecha_especifica is None:
            raise ValueError(
                "CONF_FECHA_ESPECIFICA_REQUERIDA: se seleccionó día específico "
                "pero no se proporcionó fecha_especifica."
            )


@dataclass
class Proyecto:
    """Objeto raíz del proyecto. Se almacena en st.session_state.proyecto.

    Contiene todas las secciones de entrada y el espejo de Resultados.
    Las secciones opcionales son None cuando no aplican a la tipología.
    """

    meta: Meta = field(default_factory=Meta)
    configuracion: Configuracion = field(default_factory=Configuracion)
    emplazamiento: Optional[object] = None  # Emplazamiento — se importa en emplazamiento.py
    clima: Optional[object] = None  # Clima
    colector: Optional[object] = None  # Colector — None si tipología CAJA
    camara: Optional[object] = None  # Camara
    auxiliar: Optional[object] = None  # Auxiliar — None si sin auxiliar
    motor: Optional[object] = None  # Motor — None si convección natural
    chimenea: Optional[object] = None  # Chimenea — None si sin tiro natural
    resultados: Optional[object] = None  # Resultados

    def validar_coherencia_global(self) -> list:
        """Valida las invariantes de coherencia entre secciones.

        Debe llamarse antes de cualquier cálculo.

        Returns:
            Lista de Advertencia con los errores o advertencias encontrados.
            Lista vacía si el proyecto es coherente.

        Raises:
            ValueError: Si se detecta un error duro de coherencia global.
        """
        # TODO: implementar en sesión de código
        raise NotImplementedError
