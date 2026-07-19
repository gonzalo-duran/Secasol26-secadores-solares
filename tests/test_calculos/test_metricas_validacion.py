"""Tests de las métricas de bondad de ajuste (mejora 38, fase 2, E1)."""

from __future__ import annotations

import numpy as np
import pytest

from calculos.metricas_validacion import (
    MetricasAjuste,
    calcular_metricas,
    indice_willmott,
    mae,
    mbe,
    nse,
    r2,
    rmse,
)


class TestSerieIdentica:
    """Simulado == medido → ajuste perfecto."""

    def test_metricas_de_ajuste_perfecto(self):
        m = np.array([10.0, 20.0, 30.0, 40.0])
        res = calcular_metricas(m, m.copy())
        assert res.n_pares == 4
        assert res.rmse == pytest.approx(0.0)
        assert res.mbe == pytest.approx(0.0)
        assert res.mae == pytest.approx(0.0)
        assert res.r2 == pytest.approx(1.0)
        assert res.nse == pytest.approx(1.0)
        assert res.d_willmott == pytest.approx(1.0)


class TestSesgoConstante:
    """Simulado = medido + c → MBE = c, RMSE = |c|, R² = 1, NSE < 1."""

    def test_sesgo_positivo(self):
        m = np.array([10.0, 20.0, 30.0, 40.0])
        s = m + 2.0
        assert mbe(m, s) == pytest.approx(2.0)
        assert rmse(m, s) == pytest.approx(2.0)
        assert mae(m, s) == pytest.approx(2.0)
        # R² es ciego al sesgo (correlación perfecta).
        assert r2(m, s) == pytest.approx(1.0)
        # NSE castiga el sesgo (no es 1).
        assert nse(m, s) < 1.0

    def test_sesgo_negativo_signo(self):
        m = np.array([10.0, 20.0, 30.0])
        s = m - 3.0
        assert mbe(m, s) == pytest.approx(-3.0)


class TestValoresAnaliticos:
    """Casos con RMSE/MBE calculables a mano."""

    def test_rmse_conocido(self):
        m = np.array([1.0, 2.0, 3.0])
        s = np.array([2.0, 2.0, 3.0])  # errores: +1, 0, 0
        assert rmse(m, s) == pytest.approx(np.sqrt(1.0 / 3.0))
        assert mbe(m, s) == pytest.approx(1.0 / 3.0)
        assert mae(m, s) == pytest.approx(1.0 / 3.0)

    def test_nse_igual_media_da_cero(self):
        """Un modelo que devuelve la media del medido → NSE = 0."""
        m = np.array([10.0, 20.0, 30.0, 40.0])
        s = np.full_like(m, np.mean(m))
        assert nse(m, s) == pytest.approx(0.0, abs=1e-12)

    def test_anticorrelacion_nse_negativo(self):
        """Serie invertida → peor que la media → NSE < 0."""
        m = np.array([10.0, 20.0, 30.0, 40.0])
        s = np.array([40.0, 30.0, 20.0, 10.0])
        assert nse(m, s) < 0.0
        # R² sigue alto (correlación lineal, aunque negativa).
        assert r2(m, s) == pytest.approx(1.0)


class TestManejoNaN:
    """Filtrado de pares no finitos y validaciones de forma."""

    def test_filtra_nan_en_cualquiera(self):
        m = np.array([1.0, np.nan, 3.0, 4.0])
        s = np.array([1.0, 2.0, np.nan, 4.0])
        res = calcular_metricas(m, s)
        # Solo los índices 0 y 3 son válidos en ambas.
        assert res.n_pares == 2
        assert res.rmse == pytest.approx(0.0)

    def test_MVAL_LONGITUD_DISTINTA(self):
        with pytest.raises(ValueError, match="MVAL_LONGITUD_DISTINTA"):
            calcular_metricas(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))

    def test_MVAL_SERIES_VACIAS(self):
        with pytest.raises(ValueError, match="MVAL_SERIES_VACIAS"):
            calcular_metricas(np.array([np.nan, np.nan]), np.array([1.0, 2.0]))


class TestConstantes:
    """Series constantes → correlación indefinida → convenciones seguras."""

    def test_r2_serie_constante_da_cero(self):
        m = np.array([5.0, 5.0, 5.0])
        s = np.array([5.0, 6.0, 7.0])
        assert r2(m, s) == 0.0

    def test_willmott_en_rango(self):
        m = np.array([10.0, 20.0, 30.0, 40.0])
        s = np.array([12.0, 18.0, 33.0, 38.0])
        d = indice_willmott(m, s)
        assert 0.0 <= d <= 1.0

    def test_dataclass_es_frozen(self):
        res = calcular_metricas(np.array([1.0, 2.0]), np.array([1.0, 2.0]))
        assert isinstance(res, MetricasAjuste)
        with pytest.raises(Exception):
            res.rmse = 1.0  # type: ignore[misc]
