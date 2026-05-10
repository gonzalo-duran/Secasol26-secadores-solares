"""Geometría solar — utilidades de tiempo y posición.

Funciones puras (sin streamlit) para cálculos geométricos del Sol que
necesitan varias capas de la aplicación.

Convención: lat en grados (positivo norte), lon en grados (positivo este),
tz como identificador IANA (ej. 'America/Argentina/Salta').
"""

from __future__ import annotations

from datetime import date as _date_type
from typing import Union

import pandas as pd
import pvlib


def mediodia_solar_transit(
    fecha: Union[_date_type, pd.Timestamp, str],
    lat: float,
    lon: float,
    tz: str,
) -> pd.Timestamp:
    """Calcula el tránsito solar (mediodía solar verdadero) para una fecha.

    El tránsito es el momento físico en que el Sol cruza el meridiano local
    (cenital mínimo). Calculado con el algoritmo SPA de pvlib —
    `pvlib.solarposition.sun_rise_set_transit_spa`.

    A diferencia de `idxmax(POA)` o `idxmax(GHI)`, el tránsito SPA:
        - Tiene resolución continua (no bin horario).
        - Es independiente de la orientación del colector.
        - Refleja la ecuación del tiempo y la longitud del lugar.

    Args:
        fecha: Fecha en hora local (date, Timestamp o "YYYY-MM-DD").
        lat: Latitud [°], positivo norte.
        lon: Longitud [°], positivo este.
        tz: Identificador IANA de zona horaria local
            (ej. 'America/Argentina/Salta').

    Returns:
        Timestamp tz-aware (en `tz`) del tránsito solar de la fecha pedida.

    Raises:
        ValueError: Si `fecha` no se puede interpretar.
    """
    if isinstance(fecha, str):
        fecha = pd.Timestamp(fecha).date()
    elif isinstance(fecha, pd.Timestamp):
        fecha = fecha.date()

    # SPA requiere DatetimeIndex tz-aware. Le damos un único punto al mediodía
    # local del día para que el algoritmo sepa el día solar.
    times = pd.DatetimeIndex(
        [pd.Timestamp(fecha) + pd.Timedelta(hours=12)]
    ).tz_localize(tz)

    res = pvlib.solarposition.sun_rise_set_transit_spa(times, lat, lon)
    transit = res["transit"].iloc[0]

    if pd.isna(transit):
        raise ValueError(
            f"SOLAR_TRANSIT_NO_CALCULABLE: SPA no devolvió tránsito para "
            f"({lat}, {lon}) en {fecha}. ¿Latitud polar fuera de rango?"
        )

    return transit


def bin_horario_que_contiene(
    timestamp: pd.Timestamp,
    indice: pd.DatetimeIndex,
) -> pd.Timestamp:
    """Devuelve el timestamp del índice horario que CONTIENE a `timestamp`.

    Útil cuando se quiere localizar un instante continuo (ej. mediodía solar
    a las 13:20:05) dentro de una grilla horaria discreta (NASA POWER da
    bins 12:00, 13:00, 14:00, ...).

    Convención: los bins se interpretan como `[t, t+1h)`. Es decir, las
    13:20 están en el bin 13:00.

    Args:
        timestamp: Instante a localizar (tz-aware compatible con `indice`).
        indice: Grilla horaria (típicamente `datos_dia.index`).

    Returns:
        Timestamp del bin que contiene `timestamp`. Si `timestamp` queda
        fuera del rango del índice, devuelve el bin más cercano.

    Raises:
        ValueError: Si `indice` está vacío.
    """
    if len(indice) == 0:
        raise ValueError("BIN_INDICE_VACIO: el índice no tiene elementos.")

    # Alinear la unidad de tiempo. NASA POWER deja el índice en microsegundos
    # (`us`); pvlib SPA devuelve nanosegundos (`ns`). searchsorted falla si
    # las unidades difieren cuando el ns no es lossless. Truncamos a la unit
    # del índice — es lo que define el bin de todas formas.
    if hasattr(timestamp, "floor") and hasattr(indice, "unit"):
        timestamp = timestamp.floor(indice.unit)

    # Convención [t, t+1h) — ubicación 'right' deja `t` y descarta `t+1h`.
    pos = indice.searchsorted(timestamp, side="right") - 1
    if pos < 0:
        return indice[0]
    if pos >= len(indice):
        return indice[-1]
    return indice[pos]
