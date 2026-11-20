"""X objetivo por debajo de la humedad de equilibrio con el aire (S70).

Con aire a 25 °C y 20 % HR la manzana se equilibra en X ≈ 0.17: un X_obj de 0.15
es inalcanzable con cualquier horizonte, y la app sugería "ampliar el horizonte".
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from calculos.camara_calc import (
    _construir_params_termodinamico,
    calcular_camara,
    humedad_equilibrio_alcanzable,
)
from calculos.psicrometria import actividad_agua_desde_X_GAB, actividad_agua_isoterma
from core import catalogo
from core.camara import Camara


def _camara(X_obj: float, masa_kg: float = 1.5) -> Camara:
    cam = Camara()
    return dataclasses.replace(
        cam,
        carga_producto=dataclasses.replace(
            cam.carga_producto, humedad_objetivo_X=X_obj, masa_total_kg=masa_kg
        ),
    )


class TestHumedadEquilibrio:
    def test_invierte_la_isoterma_en_la_HR_minima(self):
        pr = _construir_params_termodinamico(Camara(), 298.15, 0.2, 298.15, 101325.0)
        X_eq = humedad_equilibrio_alcanzable(pr.aw_func, np.array([0.6, 0.2, 0.35]))
        assert pr.aw_func(X_eq) == pytest.approx(0.2, abs=1e-5)

    def test_sin_serie_valida(self):
        assert humedad_equilibrio_alcanzable(lambda X: 0.5, np.array([np.nan])) is None


class TestAvisoObjetivoBajoEquilibrio:
    def test_CAM_TD_X_OBJ_BAJO_EQUILIBRIO(self):
        res = calcular_camara(_camara(0.15), 298.15, 0.20, 298.15, 101325.0, t_max_s=4 * 86400)
        assert res.status == "t_max_alcanzado"
        assert res.X_equilibrio_kg_kg == pytest.approx(0.172, abs=0.005)
        assert res.X_prod_kg_kg[-1] == pytest.approx(res.X_equilibrio_kg_kg, abs=0.005)
        assert any(a.startswith("CAM_TD_X_OBJ_BAJO_EQUILIBRIO") for a in res.advertencias)

    def test_objetivo_alcanzable_no_avisa(self):
        res = calcular_camara(_camara(0.25), 298.15, 0.20, 298.15, 101325.0, t_max_s=4 * 86400)
        assert res.status == "X_obj_alcanzado"
        assert res.X_equilibrio_kg_kg < 0.25
        assert not any(a.startswith("CAM_TD_X_OBJ_BAJO_EQUILIBRIO") for a in res.advertencias)


class TestInversionGABEstable:
    @pytest.mark.parametrize("X", [1e-12, 1e-9, 1e-6])
    def test_X_diminuto_no_cae_al_agua_libre(self, X):
        """Hasta S70 la fórmula directa cancelaba y el motor devolvía a_w = 1."""
        iso = catalogo.isoterma_gab("manzana")
        a_w = actividad_agua_desde_X_GAB(X, iso.X_m, iso.C, iso.K)
        # Límite lineal de la GAB: X ≈ X_m·C·K·a_w.
        assert a_w == pytest.approx(X / (iso.X_m * iso.C * iso.K), rel=1e-3)


class TestObjetivoSecadoPorProducto:
    """X objetivo por defecto desde a_w = 0.60 sobre la isoterma (S70)."""

    @pytest.mark.parametrize("producto", sorted(catalogo.PRODUCTOS))
    def test_cae_en_la_aw_objetivo(self, producto):
        o = catalogo.objetivo_secado(producto)
        iso = catalogo.isoterma_gab(producto)
        assert o.origen == "aw_default"
        assert actividad_agua_isoterma(o.X, iso) == pytest.approx(
            catalogo.AW_OBJETIVO_DEFAULT, abs=1e-6
        )

    def test_depende_del_producto(self):
        """Manzana (isoterma alta) pide más X que la yerba a igual a_w."""
        assert catalogo.objetivo_secado("manzana").X > 3 * catalogo.objetivo_secado("te_yerba").X

    def test_sin_isoterma_usa_la_reserva(self, monkeypatch):
        datos = {k: v for k, v in catalogo.PRODUCTOS["charqui_vacuno"].items() if k != "isoterma"}
        monkeypatch.setitem(catalogo.PRODUCTOS, "charqui_vacuno", datos)  # sin isoterma (S71)
        o = catalogo.objetivo_secado("charqui_vacuno")
        assert o.origen == "reserva"
        assert o.X == catalogo.X_OBJETIVO_RESERVA
        assert o.a_w is None

    def test_X_declarado_en_catalogo(self, monkeypatch):
        datos = dict(catalogo.PRODUCTOS["pimiento_rojo"], objetivo_secado={"X": 0.12})
        monkeypatch.setitem(catalogo.PRODUCTOS, "pimiento_rojo", datos)
        o = catalogo.objetivo_secado("pimiento_rojo")
        assert o.origen == "X_catalogo" and o.X == 0.12
        iso = catalogo.isoterma_gab("pimiento_rojo")
        assert o.a_w == pytest.approx(
            actividad_agua_desde_X_GAB(0.12, iso.X_m, iso.C, iso.K), abs=1e-6
        )

    def test_aw_declarada_en_catalogo(self, monkeypatch):
        datos = dict(catalogo.PRODUCTOS["manzana"], objetivo_secado={"a_w": 0.5})
        monkeypatch.setitem(catalogo.PRODUCTOS, "manzana", datos)
        o = catalogo.objetivo_secado("manzana")
        assert o.origen == "aw_catalogo" and o.a_w == 0.5
        iso = catalogo.isoterma_gab("manzana")
        assert actividad_agua_desde_X_GAB(o.X, iso.X_m, iso.C, iso.K) == pytest.approx(
            0.5, abs=1e-6
        )
