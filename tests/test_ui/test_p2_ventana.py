"""Tests de P2 — eje temporal de la ventana (mejora 30) y sync de año (mejora 28)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ui.p2_emplazamiento import (
    _ANIO_DEFAULT,
    _eje_x_temporal,
    _fig_temperatura_diaria,
    _resolver_anio_descarga,
)

_TZ = "America/Argentina/Salta"


# ---------------------------------------------------------------------------
# Mejora 30 — eje temporal completo en la ventana de producción
# ---------------------------------------------------------------------------


def test_eje_temporal_dia_unico_es_categorico():
    """Un solo día → etiquetas 'HH:MM' (eje categórico, como antes)."""
    idx = pd.date_range("2023-01-15 00:00", periods=24, freq="h", tz=_TZ)
    x = _eje_x_temporal(idx)
    assert isinstance(x, list)
    assert x[0] == "00:00" and x[12] == "12:00"


def test_eje_temporal_ventana_es_datetime():
    """Varios días → índice datetime completo (no se colapsa a 24 h)."""
    idx = pd.date_range("2023-01-15 00:00", periods=24 * 5, freq="h", tz=_TZ)
    x = _eje_x_temporal(idx)
    assert isinstance(x, pd.DatetimeIndex)
    assert len(x) == 24 * 5


def test_fig_temperatura_ventana_cubre_dominio_completo():
    """La figura de la ventana abarca todas las horas y >1 fecha (no encimadas)."""
    idx = pd.date_range("2023-01-15 00:00", periods=24 * 5, freq="h", tz=_TZ)
    df = pd.DataFrame({"T_amb_K": np.linspace(283.0, 303.0, len(idx))}, index=idx)

    fig = _fig_temperatura_diaria(df)
    xs = pd.DatetimeIndex(fig.data[0].x)
    assert len(fig.data[0].x) == len(idx)
    assert xs.normalize().nunique() == 5


def test_fig_temperatura_dia_unico_sigue_categorico():
    """El día de diseño (1 día) mantiene etiquetas de hora."""
    idx = pd.date_range("2023-06-21 00:00", periods=24, freq="h", tz=_TZ)
    df = pd.DataFrame({"T_amb_K": np.linspace(275.0, 285.0, len(idx))}, index=idx)

    fig = _fig_temperatura_diaria(df)
    assert list(fig.data[0].x)[6] == "06:00"


# ---------------------------------------------------------------------------
# Mejora 28 — sincronización robusta del año de descarga P1→P2
# ---------------------------------------------------------------------------


def test_anio_ausente_siembra_desde_ventana_p1():
    """Key purgada (None) con ventana en P1 → siembra el año de la ventana, NO 2022."""
    anio, visto = _resolver_anio_descarga(
        anio_p1=2019, anio_descarga_actual=None, ultimo_anio_p1_visto=2019
    )
    assert anio == 2019 and visto == 2019


def test_anio_ausente_sin_fecha_p1_cae_al_default():
    """Sin ventana/fecha en P1 y key ausente → default histórico."""
    anio, visto = _resolver_anio_descarga(
        anio_p1=None, anio_descarga_actual=None, ultimo_anio_p1_visto=None
    )
    assert anio == _ANIO_DEFAULT and visto is None


def test_anio_resincroniza_si_p1_cambia():
    """Si P1 cambia de año respecto al último visto, P2 re-sincroniza."""
    anio, visto = _resolver_anio_descarga(
        anio_p1=2021, anio_descarga_actual=2019, ultimo_anio_p1_visto=2019
    )
    assert anio == 2021 and visto == 2021


def test_anio_respeta_override_manual():
    """Override manual del usuario (P1 sin cambios) se conserva al navegar."""
    anio, visto = _resolver_anio_descarga(
        anio_p1=2019, anio_descarga_actual=2005, ultimo_anio_p1_visto=2019
    )
    assert anio == 2005 and visto == 2019
