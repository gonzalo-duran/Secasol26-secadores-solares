"""
Dataclasses de configuración y reporte para la ingesta de datos climáticos medidos.

Mejora 38, fase 1a. Este módulo define los tipos puros (sin pandas pesado ni
streamlit) que describen CÓMO interpretar un archivo de datos medidos por el
usuario (mapeo de columnas, unidades, zona horaria, convención de timestamp) y
QUÉ encontró el control de calidad físico al procesarlo.

El pipeline que los consume vive en ``calculos/clima_medido.py``. El objeto
``core.clima.Clima`` referencia estos tipos (campos ``mapeo`` y ``qc``); la
dirección de import es clima → clima_medido (este módulo no importa nada de
``core.clima``).

Contiene:
    - Constantes de procedencia por columna (PROCEDENCIA_*).
    - VARIABLES_MAPEABLES y UNIDADES_POR_VARIABLE: qué se puede mapear y en qué
      unidades de origen.
    - MapeoColumna / ConfigMapeoClima: configuración declarativa de la ingesta.
    - ChequeoQC / ReporteQC: resultado del control de calidad físico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date  # noqa: F401  (usado en anotación Optional[date] de fecha_fija)
from typing import Optional

# ---------------------------------------------------------------------------
# Procedencia de cada columna del clima resultante
# ---------------------------------------------------------------------------
# Claves estables (NO traducir acá; la UI las traduce con t()).
PROCEDENCIA_MEDIDA = "medida"
PROCEDENCIA_DERIVADA = "derivada"  # p. ej. DNI/DHI derivadas de GHI vía Erbs
PROCEDENCIA_NASA = "completada_nasa"
PROCEDENCIA_DEFAULT = "default"  # p. ej. presión ISA si NASA no está disponible

PROCEDENCIAS: tuple[str, ...] = (
    PROCEDENCIA_MEDIDA,
    PROCEDENCIA_DERIVADA,
    PROCEDENCIA_NASA,
    PROCEDENCIA_DEFAULT,
)

# ---------------------------------------------------------------------------
# Variables mapeables y unidades de origen aceptadas
# ---------------------------------------------------------------------------
# Columna opcional del DataFrame de clima: irradiancia global medida EN EL PLANO
# del colector (piranómetro coplanar). No integra COLUMNAS_SI: es un extra que
# `calcular_POA_horizonte` usa para saltear la transposición Liu-Jordan.
COLUMNA_POA_MEDIDA: str = "POA_med_Wm2"

# Variables de serie que el usuario puede mapear desde columnas de su archivo.
# El timestamp NO está acá: se declara aparte en ConfigMapeoClima.columna_timestamp.
VARIABLES_MAPEABLES: tuple[str, ...] = (
    "T_amb_K",
    "GHI_Wm2",
    "DNI_Wm2",
    "DHI_Wm2",
    "WS_ms",
    "presion_Pa",
    "HR",
    COLUMNA_POA_MEDIDA,
)

# Unidades de origen aceptadas por variable (clave estable → la conversión a SI
# vive en calculos/clima_medido.py; la UI traduce el rótulo con t()).
_UNIDADES_IRRADIANCIA: tuple[str, ...] = ("W_m2", "kW_m2")
UNIDADES_POR_VARIABLE: dict[str, tuple[str, ...]] = {
    "T_amb_K": ("C", "K", "F"),
    "GHI_Wm2": _UNIDADES_IRRADIANCIA,
    "DNI_Wm2": _UNIDADES_IRRADIANCIA,
    "DHI_Wm2": _UNIDADES_IRRADIANCIA,
    COLUMNA_POA_MEDIDA: _UNIDADES_IRRADIANCIA,
    "WS_ms": ("m_s", "km_h"),
    "presion_Pa": ("Pa", "kPa", "hPa", "mbar", "atm"),
    "HR": ("porcentaje", "fraccion"),
}

# Convenciones de timestamp del archivo de origen: el valor registrado a la hora
# HH ¿es lectura instantánea, o promedio del intervalo que TERMINA (promedio_fin)
# o EMPIEZA (promedio_inicio) en HH?
CONVENCIONES_TIMESTAMP: tuple[str, ...] = ("instantanea", "promedio_fin", "promedio_inicio")

# Plano del piranómetro de irradiancia global: horizontal (GHI clásica) o
# coplanar con el colector (POA medida directa).
PLANOS_PIRANOMETRO: tuple[str, ...] = ("horizontal", "plano_colector")

# Marcadores de dato inválido típicos de dataloggers/planillas (Campbell usa "NAN").
MARCADORES_INVALIDOS_DEFAULT: tuple[str, ...] = ("NAN", "NaN", "nan", "#N/A", "")


@dataclass
class MapeoColumna:
    """Asocia una columna del archivo del usuario con una variable canónica.

    Attributes:
        variable: Variable canónica destino (una de VARIABLES_MAPEABLES).
        columna_origen: Nombre de la columna tal como aparece en el archivo.
        unidad: Unidad de origen (clave de UNIDADES_POR_VARIABLE[variable]).
    """

    variable: str
    columna_origen: str
    unidad: str

    def __post_init__(self) -> None:
        if self.variable not in VARIABLES_MAPEABLES:
            raise ValueError(
                f"CLIMED_CONFIG_VARIABLE_DESCONOCIDA: '{self.variable}' no es una "
                f"variable mapeable (válidas: {', '.join(VARIABLES_MAPEABLES)})."
            )
        if not str(self.columna_origen).strip():
            raise ValueError(
                "CLIMED_CONFIG_COLUMNA_VACIA: el nombre de la columna de origen "
                f"para '{self.variable}' no puede ser vacío."
            )
        validas = UNIDADES_POR_VARIABLE[self.variable]
        if self.unidad not in validas:
            raise ValueError(
                f"CLIMED_CONFIG_UNIDAD_INVALIDA: unidad '{self.unidad}' no válida "
                f"para '{self.variable}' (válidas: {', '.join(validas)})."
            )


@dataclass
class ConfigMapeoClima:
    """Configuración declarativa completa de la ingesta de un archivo medido.

    Describe todo lo que el pipeline necesita para interpretar el archivo:
    qué columna es el tiempo y en qué convención/zona horaria viene, qué
    columnas son variables climáticas y en qué unidades, y los metadatos de
    los sensores que afectan el acondicionamiento (altura del anemómetro,
    plano del piranómetro).

    Attributes:
        columna_timestamp: Nombre de la columna de fecha/hora en el archivo.
        zona_horaria: Zona IANA de los timestamps del archivo (ej.
            "America/Argentina/Salta").
        convencion_timestamp: "instantanea" | "promedio_fin" | "promedio_inicio".
        columnas: Mapeos de columnas de datos (sin el timestamp).
        hoja: Nombre de hoja (solo Excel; None para CSV).
        fila_encabezado: Índice 0-based de la fila de encabezados.
        altura_anemometro_m: Altura del sensor de viento [m]; la serie se
            normaliza a 2 m (convención del contrato Clima) con perfil log.
        plano_piranometro: "horizontal" (GHI) o "plano_colector" (POA medida).
        marcadores_invalidos: Strings que representan dato inválido.
    """

    columna_timestamp: str
    zona_horaria: str = "America/Argentina/Salta"
    convencion_timestamp: str = "instantanea"
    columnas: list[MapeoColumna] = field(default_factory=list)
    hoja: Optional[str] = None
    fila_encabezado: int = 0
    altura_anemometro_m: float = 2.0
    plano_piranometro: str = "horizontal"
    marcadores_invalidos: tuple[str, ...] = MARCADORES_INVALIDOS_DEFAULT
    fecha_fija: Optional[date] = None

    def __post_init__(self) -> None:
        if not str(self.columna_timestamp).strip():
            raise ValueError(
                "CLIMED_CONFIG_SIN_TIMESTAMP: debe indicarse la columna de fecha/hora."
            )
        if self.convencion_timestamp not in CONVENCIONES_TIMESTAMP:
            raise ValueError(
                f"CLIMED_CONFIG_CONVENCION_INVALIDA: '{self.convencion_timestamp}' "
                f"(válidas: {', '.join(CONVENCIONES_TIMESTAMP)})."
            )
        if self.plano_piranometro not in PLANOS_PIRANOMETRO:
            raise ValueError(
                f"CLIMED_CONFIG_PLANO_INVALIDO: '{self.plano_piranometro}' "
                f"(válidos: {', '.join(PLANOS_PIRANOMETRO)})."
            )
        if self.altura_anemometro_m <= 0:
            raise ValueError(
                "CLIMED_CONFIG_ALTURA_NO_POSITIVA: la altura del anemómetro debe "
                f"ser > 0 m (recibido: {self.altura_anemometro_m})."
            )
        if self.fila_encabezado < 0:
            raise ValueError(
                "CLIMED_CONFIG_FILA_ENCABEZADO_NEGATIVA: la fila de encabezado no "
                f"puede ser negativa (recibido: {self.fila_encabezado})."
            )
        vistas: set[str] = set()
        for m in self.columnas:
            if m.variable in vistas:
                raise ValueError(
                    f"CLIMED_CONFIG_VARIABLE_DUPLICADA: '{m.variable}' está mapeada "
                    "más de una vez."
                )
            vistas.add(m.variable)
            if m.columna_origen == self.columna_timestamp:
                raise ValueError(
                    "CLIMED_CONFIG_TIMESTAMP_MAPEADO: la columna de timestamp "
                    f"'{self.columna_timestamp}' no puede mapearse también a "
                    f"'{m.variable}'."
                )

    def variables_mapeadas(self) -> tuple[str, ...]:
        """Devuelve las variables canónicas presentes en el mapeo, en orden."""
        return tuple(m.variable for m in self.columnas)


@dataclass
class ChequeoQC:
    """Resultado de un chequeo individual del control de calidad físico.

    Attributes:
        codigo: Identificador estable del chequeo ("rango_fisico",
            "ghi_nocturna", "ghi_extraterrestre", "sensor_congelado").
        variable: Variable canónica chequeada.
        n_marcados: Valores anulados (→ NaN) o corregidos (clip) por el chequeo.
        n_avisos: Valores señalados sin acción (solo aviso).
        ejemplos: Hasta 5 timestamps ISO de muestra para orientar al usuario.
    """

    codigo: str
    variable: str
    n_marcados: int = 0
    n_avisos: int = 0
    ejemplos: list[str] = field(default_factory=list)


@dataclass
class ReporteQC:
    """Resumen del control de calidad físico aplicado a un archivo medido.

    Attributes:
        chequeos: Un ChequeoQC por (chequeo, variable) con hallazgos.
        n_filas_nativas: Filas de la serie al paso nativo (post-regularización).
        frecuencia_nativa_s: Paso temporal nativo inferido [s].
        periodo_inicio: Primer timestamp del período, ISO, hora local.
        periodo_fin: Último timestamp del período, ISO, hora local.
        meses_cubiertos: Meses calendario (1-12) con cobertura de datos.
    """

    chequeos: list[ChequeoQC] = field(default_factory=list)
    n_filas_nativas: int = 0
    frecuencia_nativa_s: Optional[float] = None
    periodo_inicio: Optional[str] = None
    periodo_fin: Optional[str] = None
    meses_cubiertos: tuple[int, ...] = ()

    def con_hallazgos(self) -> list[ChequeoQC]:
        """Devuelve solo los chequeos que marcaron o avisaron algo."""
        return [c for c in self.chequeos if c.n_marcados > 0 or c.n_avisos > 0]
