"""
Dataclasses para los datos climáticos del emplazamiento.

El objeto Clima almacena la serie temporal horaria descargada de NASA POWER,
ya convertida a unidades SI. El índice del DataFrame es DatetimeIndex UTC tz-aware.

Columnas del DataFrame (definidas en COLUMNAS_SI):
    T_amb_K:    temperatura ambiente a 2 m [K]
    GHI_Wm2:    irradiancia global horizontal [W/m²]
    DNI_Wm2:    irradiancia directa normal [W/m²]
    DHI_Wm2:    irradiancia difusa horizontal [W/m²]
    WS_ms:      velocidad del viento a 2 m [m/s]
    presion_Pa: presión superficial [Pa]
    HR:         humedad relativa [fracción, 0–1]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from core.clima_medido import COLUMNA_POA_MEDIDA, ConfigMapeoClima, ReporteQC

__all__ = [
    "COLUMNAS_SI",
    "COLUMNA_POA_MEDIDA",
    "ANIO_NASA_MIN",
    "ANIO_NASA_MAX",
    "FUENTES_CLIMA",
    "CalidadClima",
    "Clima",
]

# Nombre canónico de las columnas del DataFrame Clima.datos, en orden.
COLUMNAS_SI: tuple[str, ...] = (
    "T_amb_K",
    "GHI_Wm2",
    "DNI_Wm2",
    "DHI_Wm2",
    "WS_ms",
    "presion_Pa",
    "HR",
)

# Rango disponible de NASA POWER para descarga horaria (revisar periódicamente —
# NASA POWER suele extender el rango ~1 año tras finalizar el calendario).
ANIO_NASA_MIN: int = 2001
ANIO_NASA_MAX: int = 2023

# Fuentes posibles de la serie climática del proyecto.
FUENTES_CLIMA: tuple[str, ...] = ("nasa_power", "medido", "hibrido")


@dataclass
class CalidadClima:
    """Resumen de la calidad de los datos climáticos y política de huecos aplicada.

    Attributes:
        n_huecos_originales: Número de secuencias contiguas de datos faltantes
            detectadas en los datos crudos de NASA POWER.
        n_horas_interpoladas: Total de horas corregidas por interpolación lineal
            (huecos de duración ≤ 3 h).
        n_horas_bloqueadas: Horas que siguen siendo NaN tras la interpolación
            (huecos de duración > 3 h), pendientes de decisión del usuario.
        mayor_hueco_h: Duración en horas del hueco más largo detectado.
        decision_usuario: Decisión tomada frente a huecos bloqueados.
            Valores posibles: 'aceptar_con_nulos', 'descargar_nuevo_anio', None.
    """

    n_huecos_originales: int = 0
    n_horas_interpoladas: int = 0
    n_horas_bloqueadas: int = 0
    mayor_hueco_h: int = 0
    decision_usuario: Optional[str] = None


@dataclass
class Clima:
    """Serie temporal horaria de recursos climáticos del emplazamiento.

    Datos provistos por NASA POWER o ingeridos de mediciones del usuario
    (mejora 38, F1a), siempre convertidos a unidades SI. El viento ``WS_ms``
    está referido a 2 m sobre el suelo (convención NASA WS2M); las series
    medidas a otra altura se normalizan a 2 m en la ingesta. ``datos`` puede
    incluir además la columna opcional ``POA_med_Wm2`` (irradiancia global
    medida en el plano del colector), que ``calcular_POA_horizonte`` usa para
    saltear la transposición.

    Attributes:
        datos: DataFrame con columnas en COLUMNAS_SI e índice DatetimeIndex UTC
            tz-aware, paso horario. None si aún no hay datos.
        anio: Año calendario de los datos (ej.: 2022).
        calidad: Resumen de la calidad y política de huecos aplicada.
        altitud_nasa_m: Altitud del punto de grilla reportada por NASA POWER [m]
            (también cuando NASA solo se usó para completar columnas faltantes).
        fuente: Origen de la serie: "nasa_power" (descarga completa),
            "medido" (todas las columnas medidas/derivadas del archivo del
            usuario) o "hibrido" (columnas medidas + completadas con NASA).
        procedencia: Mapa columna canónica → constante PROCEDENCIA_* de
            core.clima_medido. None equivale a "todo NASA POWER".
        frecuencia_nativa_s: Paso temporal del archivo medido original [s]
            (ej. 600 para 10-minutal). None para clima NASA.
        datos_nativos: Serie medida en SI al paso nativo, post-QC y
            pre-remuestreo (reservada para la fase 1b). None para clima NASA.
        mapeo: Configuración de mapeo usada en la ingesta (para snapshot y
            restauración). None para clima NASA.
        qc: Reporte del control de calidad físico de la ingesta. None para
            clima NASA.
    """

    datos: Optional[pd.DataFrame] = None
    anio: Optional[int] = None
    calidad: CalidadClima = field(default_factory=CalidadClima)
    altitud_nasa_m: Optional[float] = None
    fuente: str = "nasa_power"
    procedencia: Optional[dict[str, str]] = None
    frecuencia_nativa_s: Optional[float] = None
    datos_nativos: Optional[pd.DataFrame] = None
    mapeo: Optional[ConfigMapeoClima] = None
    qc: Optional[ReporteQC] = None

    def __post_init__(self) -> None:
        if self.fuente not in FUENTES_CLIMA:
            raise ValueError(
                f"CLIMA_FUENTE_INVALIDA: '{self.fuente}' " f"(válidas: {', '.join(FUENTES_CLIMA)})."
            )
