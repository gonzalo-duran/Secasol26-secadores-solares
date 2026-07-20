"""Dataclasses de validación medido vs simulado (mejora 38, fase 2).

Estructuras puras (sin streamlit ni calculos) que describen una **señal de
referencia** medida por el usuario y cómo interpretarla, para contrastarla contra
la salida simulada. El primer corte de la fase 2 valida la **temperatura de salida
del colector** (caso ideal: prototipo colector 10 m del INENCO).

La ingesta (`calculos/ingesta_referencia.py`) reusa la maquinaria de lectura y
parseo de `clima_medido` (fase 1a). Convención: la señal se guarda en SI (K para
temperatura); las métricas de diferencia (RMSE/MBE/MAE) son invariantes al offset
K↔°C, y la UI muestra °C.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date  # noqa: F401  (usado en anotación Optional[date] de fecha_fija)
from typing import Optional

import pandas as pd

# Variables de referencia que se pueden validar (extensible a cámara/producto en
# fases siguientes). El primer corte cubre la temperatura de salida del colector.
VARIABLES_REFERENCIA: tuple[str, ...] = ("T_salida_colector",)

# Unidades de origen aceptadas por variable de referencia.
UNIDADES_REFERENCIA: dict[str, tuple[str, ...]] = {
    "T_salida_colector": ("C", "K", "F"),
}

# Convenciones de timestamp (idénticas a clima_medido, fase 1a).
CONVENCIONES_TIMESTAMP: tuple[str, ...] = ("instantanea", "promedio_fin", "promedio_inicio")

# Marcadores de dato inválido típicos de dataloggers/planillas.
MARCADORES_INVALIDOS_DEFAULT: tuple[str, ...] = ("NAN", "NaN", "nan", "#N/A", "")


@dataclass
class ConfigReferencia:
    """Cómo interpretar el archivo de la señal de referencia medida.

    Attributes:
        columna_timestamp: Nombre de la columna de fecha/hora.
        columna_valor: Nombre de la columna con la señal a validar.
        variable: Variable canónica (una de VARIABLES_REFERENCIA).
        unidad: Unidad de origen (clave de UNIDADES_REFERENCIA[variable]).
        zona_horaria: Zona horaria del archivo (ej. "America/Argentina/Salta").
        convencion_timestamp: instantanea | promedio_fin | promedio_inicio.
        hoja: Hoja del libro Excel (None para CSV o primera hoja).
        fila_encabezado: Fila (0-based) del encabezado.
        marcadores_invalidos: Cadenas a tratar como dato faltante.
        fecha_fija: Fecha del ensayo, para archivos cuya columna de timestamp trae
            **solo la hora** (sin fecha, ej. "09:00:00"). Si se define, se combina
            con la hora de cada registro; None → se usa la fecha del propio dato.
    """

    columna_timestamp: str
    columna_valor: str
    variable: str = "T_salida_colector"
    unidad: str = "C"
    zona_horaria: str = "UTC"
    convencion_timestamp: str = "instantanea"
    hoja: Optional[str] = None
    fila_encabezado: int = 0
    marcadores_invalidos: tuple[str, ...] = MARCADORES_INVALIDOS_DEFAULT
    fecha_fija: Optional[date] = None

    def __post_init__(self) -> None:
        if not str(self.columna_timestamp).strip():
            raise ValueError("VREF_CONFIG_TIMESTAMP_VACIO: la columna de timestamp es obligatoria.")
        if not str(self.columna_valor).strip():
            raise ValueError("VREF_CONFIG_VALOR_VACIO: la columna de la señal es obligatoria.")
        if self.variable not in VARIABLES_REFERENCIA:
            raise ValueError(
                f"VREF_CONFIG_VARIABLE_DESCONOCIDA: '{self.variable}' no es una variable "
                f"de referencia válida (válidas: {', '.join(VARIABLES_REFERENCIA)})."
            )
        validas = UNIDADES_REFERENCIA[self.variable]
        if self.unidad not in validas:
            raise ValueError(
                f"VREF_CONFIG_UNIDAD_INVALIDA: unidad '{self.unidad}' no válida para "
                f"'{self.variable}' (válidas: {', '.join(validas)})."
            )
        if self.convencion_timestamp not in CONVENCIONES_TIMESTAMP:
            raise ValueError(
                f"VREF_CONFIG_CONVENCION_INVALIDA: '{self.convencion_timestamp}' no es una "
                f"convención válida (válidas: {', '.join(CONVENCIONES_TIMESTAMP)})."
            )
        if int(self.fila_encabezado) < 0:
            raise ValueError("VREF_CONFIG_FILA_NEGATIVA: fila_encabezado no puede ser negativa.")


@dataclass
class SenalReferencia:
    """Señal de referencia medida, ya en SI y a su paso nativo.

    Attributes:
        variable: Variable canónica validada (una de VARIABLES_REFERENCIA).
        serie: Serie temporal en SI (K para temperatura), índice UTC ordenado.
        unidad_origen: Unidad del archivo original (para trazabilidad).
        frecuencia_nativa_s: Paso temporal nativo detectado [s].
        n_invalidos: Cantidad de muestras marcadas inválidas (NaN) en la ingesta.
    """

    variable: str
    serie: pd.Series
    unidad_origen: str
    frecuencia_nativa_s: float
    n_invalidos: int = 0
    advertencias: list[str] = field(default_factory=list)
