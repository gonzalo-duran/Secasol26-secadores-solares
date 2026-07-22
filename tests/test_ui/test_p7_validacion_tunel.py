"""Tests de la validación del túnel semicontinuo en P7 (mejora 38, fase 4, E5).

El túnel no se valida por serie temporal —``simular_cascada`` no guarda historia
por zona— sino contra sus dos objetos directos: las **descargas** por avance
(comparación lagrangiana: la columna que sale) y el **perfil espacial** al cierre
(comparación euleriana: la foto del túnel). Ver `docs/notas/plan_datos_medidos_4.md`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ui.p7_resultados import _perfil_medido_desde_editor


class TestPerfilMedidoDesdeEditor:
    """Helper puro que lee la tabla editable del perfil por zona."""

    def test_extrae_pares_validos(self):
        filas = [{"medido": 4.0}, {"medido": 2.5}, {"medido": 1.0}]
        zonas, valores = _perfil_medido_desde_editor(filas, n_zonas=3)
        assert zonas == [0, 1, 2]
        assert valores == pytest.approx([4.0, 2.5, 1.0])

    def test_descarta_zonas_sin_sensor(self):
        """Las zonas sin valor (None) simplemente no participan de la comparación."""
        filas = [{"medido": 4.0}, {"medido": None}, {"medido": 1.0}]
        zonas, valores = _perfil_medido_desde_editor(filas, n_zonas=3)
        assert zonas == [0, 2]
        assert valores == pytest.approx([4.0, 1.0])

    def test_descarta_nan_y_no_numericos(self):
        filas = [{"medido": float("nan")}, {"medido": "abc"}, {"medido": 2.0}]
        zonas, valores = _perfil_medido_desde_editor(filas, n_zonas=3)
        assert zonas == [2]
        assert valores == pytest.approx([2.0])

    def test_ignora_filas_fuera_de_rango(self):
        """Más filas que zonas (tabla desincronizada) no rompe ni inventa zonas."""
        filas = [{"medido": 4.0}, {"medido": 2.0}, {"medido": 1.0}]
        zonas, valores = _perfil_medido_desde_editor(filas, n_zonas=2)
        assert zonas == [0, 1]
        assert len(valores) == 2

    def test_tabla_vacia(self):
        zonas, valores = _perfil_medido_desde_editor([], n_zonas=3)
        assert zonas == [] and valores == []


class TestDescargasDelTunel:
    """``pares_descarga_tunel`` sobre el resultado de ventana (duck-typing)."""

    class _ResFalso:
        """Mínimo que la función necesita: descargas, cadencia y ancla."""

        X_salida_por_avance = np.array([3.0, 2.0, 1.5, 1.2])
        T_prod_salida_por_avance_K = np.array([310.0, 312.0, 313.0, 313.5])
        intervalo_avance_s = 7200.0

    def test_fecha_cada_descarga_al_fin_de_su_intervalo(self):
        from calculos.validacion_camara import pares_descarga_tunel

        t0 = pd.Timestamp("2008-01-14 09:00", tz="UTC")
        ts, y = pares_descarga_tunel(self._ResFalso(), t0)
        assert len(ts) == len(y) == 4
        # La primera columna sale al cumplirse el primer avance, no en t0.
        assert (ts[0] - t0).total_seconds() == pytest.approx(7200.0)
        assert (ts[-1] - t0).total_seconds() == pytest.approx(4 * 7200.0)
        assert y[0] == pytest.approx(3.0)

    def test_resultado_de_ventana_es_compatible(self):
        """``ResultadoVentana`` expone los mismos campos que ``ResultadoCascada``."""
        from calculos.simulacion_ventana import ResultadoVentana
        from calculos.validacion_camara import pares_descarga_tunel

        res = ResultadoVentana(subtipo="SEMICONTINUO", horizonte_s=7 * 86400.0)
        res.X_salida_por_avance = np.array([2.0, 1.5])
        res.intervalo_avance_s = 3600.0
        ts, y = pares_descarga_tunel(res, pd.Timestamp("2008-01-14", tz="UTC"))
        assert len(ts) == 2
        assert y[1] == pytest.approx(1.5)


class TestSnapshotsValidacionTunel:
    """Helpers puros que persisten la validación del túnel para el reporte PDF."""

    def _metricas(self):
        from calculos.metricas_validacion import MetricasAjuste

        return MetricasAjuste(
            n_pares=4, rmse=0.1, mbe=-0.05, mae=0.08, r2=0.98, nse=0.97, d_willmott=0.99
        )

    def test_snapshot_descargas(self):
        from ui.p7_resultados import _snapshot_descargas_tunel

        ts = list(pd.date_range("2020-05-15 12:00", periods=3, freq="2h", tz="UTC"))
        snap = _snapshot_descargas_tunel(
            ts, np.array([3.0, 2.0, 1.5]), np.array([2.9, 2.1, 1.4]), self._metricas(), "X_producto"
        )
        assert snap["variable"] == "X_producto"
        assert snap["y_med_disp"] == [3.0, 2.0, 1.5]
        assert snap["metricas"].n_pares == 4
        assert len(snap["ts"]) == 3

    def test_snapshot_perfil_preserva_nones(self):
        from ui.p7_resultados import _snapshot_perfil_tunel

        snap = _snapshot_perfil_tunel(
            "X_producto", [4.0, None, 1.0], [3.8, 2.2, 1.1], self._metricas()
        )
        assert snap["magnitud"] == "X_producto"
        assert snap["y_med_disp"] == [4.0, None, 1.0]
        assert snap["y_sim_disp"] == pytest.approx([3.8, 2.2, 1.1])
