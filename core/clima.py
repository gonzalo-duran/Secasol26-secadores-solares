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

    Datos provistos por NASA POWER y convertidos a unidades SI.

    Attributes:
        datos: DataFrame con columnas en COLUMNAS_SI e índice DatetimeIndex UTC
            tz-aware. None si los datos aún no han sido descargados.
        anio: Año calendario de los datos (ej.: 2022).
        calidad: Resumen de la calidad y política de huecos aplicada.
        altitud_nasa_m: Altitud del punto de grilla reportada por NASA POWER [m].
    """

    datos: Optional[pd.DataFrame] = None
    anio: Optional[int] = None
    calidad: CalidadClima = field(default_factory=CalidadClima)
    altitud_nasa_m: Optional[float] = None
