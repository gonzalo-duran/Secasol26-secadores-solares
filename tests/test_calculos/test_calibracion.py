"""Tests del motor de calibración 1-D (mejora 38, fase 3, E1)."""

from __future__ import annotations

import numpy as np
import pytest

from calculos.calibracion import OBJETIVOS, ResultadoCalibracion, calibrar_1d
from calculos.metricas_validacion import MetricasAjuste


def _metricas(rmse, mbe=0.0):
    """MetricasAjuste sintética con el RMSE/MBE deseado (resto neutro)."""
    return MetricasAjuste(
        n_pares=100, rmse=rmse, mbe=mbe, mae=abs(mbe), r2=0.9, nse=0.8, d_willmott=0.9
    )


class TestCalibrar1D:

    def test_encuentra_minimo_de_parabola(self):
        """objetivo(v) = (v−8)² → el óptimo debe caer en v=8."""
        valores = np.arange(2, 13, 1.0)

        def evaluar_fn(v):
            return _metricas(rmse=(v - 8.0) ** 2)

        res = calibrar_1d(valores, evaluar_fn, parametro="velocidad", objetivo="rmse")
        assert isinstance(res, ResultadoCalibracion)
        assert res.valor_optimo == pytest.approx(8.0)
        assert res.metricas_optimo.rmse == pytest.approx(0.0)
        assert len(res.puntos) == len(valores)

    def test_objetivo_mbe_abs_minimiza_sesgo(self):
        """Con objetivo |MBE|, elige el valor de sesgo más chico en magnitud."""
        valores = [0.0, 1.0, 2.0]

        def evaluar_fn(v):
            # MBE = v − 1 → |MBE| mínimo en v=1.
            return _metricas(rmse=5.0, mbe=v - 1.0)

        res = calibrar_1d(valores, evaluar_fn, objetivo="mbe_abs")
        assert res.valor_optimo == pytest.approx(1.0)

    def test_puntos_no_evaluables_se_saltan(self):
        """Los valores donde evaluar_fn devuelve None no compiten por el óptimo."""
        valores = [1.0, 2.0, 3.0]

        def evaluar_fn(v):
            if v == 2.0:
                return None  # no convergió / sin solape
            return _metricas(rmse=v)

        res = calibrar_1d(valores, evaluar_fn)
        # v=1 tiene el RMSE más bajo entre los evaluables (1 y 3).
        assert res.valor_optimo == pytest.approx(1.0)
        # El punto no evaluable queda registrado con objetivo None.
        p2 = next(p for p in res.puntos if p.valor == 2.0)
        assert p2.objetivo is None

    def test_todos_none_devuelve_optimo_none(self):
        res = calibrar_1d([1.0, 2.0], lambda v: None)
        assert res.valor_optimo is None
        assert res.metricas_optimo is None
        assert len(res.puntos) == 2

    def test_CAL_OBJETIVO_INVALIDO(self):
        with pytest.raises(ValueError, match="CAL_OBJETIVO_INVALIDO"):
            calibrar_1d([1.0], lambda v: _metricas(1.0), objetivo="banana")

    def test_objetivos_disponibles(self):
        assert set(OBJETIVOS) == {"rmse", "mbe_abs", "mae"}
