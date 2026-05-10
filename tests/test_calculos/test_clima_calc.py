"""
Tests del módulo calculos/clima_calc.py.

Los tests de la función obtener_clima() que requieren red están marcados con
pytest.mark.network y se omiten por defecto en el CI sin red.

Los tests de _aplicar_politica_huecos() son unitarios puros (sin red).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.clima_calc import _aplicar_politica_huecos, _hash_cache
from core.clima import COLUMNAS_SI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_sin_huecos(n: int = 24) -> pd.DataFrame:
    """DataFrame SI completo sin NaN, índice UTC horario."""
    idx = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    data = {
        "T_amb_K": np.full(n, 293.15),
        "GHI_Wm2": np.linspace(0, 800, n),
        "DNI_Wm2": np.linspace(0, 700, n),
        "DHI_Wm2": np.linspace(0, 200, n),
        "WS_ms": np.full(n, 2.5),
        "presion_Pa": np.full(n, 90000.0),
        "HR": np.full(n, 0.6),
    }
    return pd.DataFrame(data, index=idx)


def _df_con_hueco(inicio_hueco: int, duracion: int) -> pd.DataFrame:
    """DataFrame de 48 h con un hueco de NaN de longitud dada."""
    df = _df_sin_huecos(n=48)
    df.iloc[inicio_hueco : inicio_hueco + duracion] = np.nan
    return df


# ---------------------------------------------------------------------------
# Tests de _hash_cache
# ---------------------------------------------------------------------------


def test_hash_cache_determinista():
    """El mismo (lat, lon, año) produce siempre el mismo hash."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-24.72, -65.41, 2022)
    assert h1 == h2


def test_hash_cache_diferente_anio():
    """Años distintos producen hashes distintos."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-24.72, -65.41, 2023)
    assert h1 != h2


def test_hash_cache_diferente_ubicacion():
    """Ubicaciones distintas producen hashes distintos."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-25.00, -65.41, 2022)
    assert h1 != h2


# ---------------------------------------------------------------------------
# Tests de _aplicar_politica_huecos
# ---------------------------------------------------------------------------


def test_politica_sin_huecos():
    """DataFrame sin NaN no debe generar huecos ni horas interpoladas."""
    df = _df_sin_huecos()
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 0
    assert calidad.n_horas_interpoladas == 0
    assert calidad.n_horas_bloqueadas == 0
    assert calidad.mayor_hueco_h == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_1h_interpolado():
    """Hueco de 1 h debe interpolarse completamente."""
    df = _df_con_hueco(inicio_hueco=10, duracion=1)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 1
    assert calidad.n_horas_interpoladas == 1
    assert calidad.n_horas_bloqueadas == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_3h_interpolado():
    """Hueco de exactamente 3 h debe interpolarse completamente."""
    df = _df_con_hueco(inicio_hueco=5, duracion=3)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_horas_interpoladas == 3
    assert calidad.n_horas_bloqueadas == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_4h_bloqueado():
    """Hueco de 4 h (> 3 h) debe quedar bloqueado como NaN."""
    df = _df_con_hueco(inicio_hueco=5, duracion=4)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.mayor_hueco_h == 4
    assert calidad.n_horas_bloqueadas == 4
    # Las 4 filas centrales del hueco deben seguir siendo NaN
    assert df_corr.iloc[5:9].isna().any().any()


def test_politica_dos_huecos_mixtos():
    """Un hueco de 2 h (interpolado) y otro de 5 h (bloqueado) coexisten."""
    df = _df_sin_huecos(n=72)
    df.iloc[5:7] = np.nan    # hueco de 2 h → se interpola
    df.iloc[20:25] = np.nan  # hueco de 5 h → se bloquea
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 2
    assert calidad.n_horas_interpoladas == 2
    assert calidad.n_horas_bloqueadas == 5
    assert calidad.mayor_hueco_h == 5


def test_politica_columnas_preservadas():
    """El DataFrame resultante debe conservar exactamente las columnas de COLUMNAS_SI."""
    df = _df_con_hueco(inicio_hueco=2, duracion=2)
    df_corr, _ = _aplicar_politica_huecos(df)
    assert list(df_corr.columns) == list(df.columns)
