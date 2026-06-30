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

VERSION_SOFTWARE = "0.14.1"


class Tipologia(Enum):
    CAJA = "CAJA"
    ARMARIO = "ARMARIO"
    GRAN_ESCALA = "GRAN_ESCALA"


class ModoAnalisis(Enum):
    DIARIO = "DIARIO"
    ANUAL = "ANUAL"
    VENTANA = "VENTANA"  # Lapso calendario [inicio, fin] con clima real horario (S40)


class SubtipoGranEscala(Enum):
    """Subtipo de secador de gran escala (solo aplica a ``Tipologia.GRAN_ESCALA``).

    - ``BATCH``: opera por lotes (carga → secado → descarga → recarga).
    - ``SEMICONTINUO``: carga completa con producto a contracorriente del aire,
      estilo túnel ADITAL (las columnas de carros avanzan según una cadencia).

    Ambos subtipos son de igual jerarquía. Para tipologías CAJA/ARMARIO el campo
    existe con valor por defecto pero no tiene efecto.
    """

    BATCH = "BATCH"
    SEMICONTINUO = "SEMICONTINUO"


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
        modo_analisis: Análisis diario, anual o por ventana calendario.
        dia_analisis: Criterio de selección del día (solo para modo DIARIO).
        fecha_especifica: Fecha concreta (solo si dia_analisis == ESPECIFICO).
        subtipo_gran_escala: Subtipo del secador de gran escala (BATCH o
            SEMICONTINUO). Solo significativo si ``tipologia == GRAN_ESCALA``.
        ventana_inicio: Fecha de inicio del lapso de análisis (solo modo VENTANA).
        ventana_fin: Fecha de fin del lapso de análisis (solo modo VENTANA).
            El lapso ``[ventana_inicio, ventana_fin]`` se simula con clima real
            horario; su largo máximo es 1 año (366 días).
    """

    tipologia: Tipologia = Tipologia.ARMARIO
    modo_analisis: ModoAnalisis = ModoAnalisis.DIARIO
    dia_analisis: DiaAnalisis = DiaAnalisis.SOLSTICIO_VERANO
    fecha_especifica: Optional[date] = None
    subtipo_gran_escala: SubtipoGranEscala = SubtipoGranEscala.BATCH
    ventana_inicio: Optional[date] = None
    ventana_fin: Optional[date] = None

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
        if self.modo_analisis == ModoAnalisis.VENTANA:
            if self.ventana_inicio is None or self.ventana_fin is None:
                raise ValueError(
                    "CONF_VENTANA_FECHAS_REQUERIDAS: modo VENTANA requiere "
                    "ventana_inicio y ventana_fin."
                )
            if self.ventana_fin <= self.ventana_inicio:
                raise ValueError(
                    "CONF_VENTANA_ORDEN_INVALIDO: ventana_fin "
                    f"({self.ventana_fin}) debe ser posterior a ventana_inicio "
                    f"({self.ventana_inicio})."
                )
            if (self.ventana_fin - self.ventana_inicio).days > 366:
                raise ValueError(
                    "CONF_VENTANA_DEMASIADO_LARGA: el lapso de análisis no puede "
                    f"superar 366 días (recibido: "
                    f"{(self.ventana_fin - self.ventana_inicio).days} días)."
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
