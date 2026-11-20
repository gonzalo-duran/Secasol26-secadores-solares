"""Isotermas del catálogo de productos: resolución propia / analogía (S70).

Cubre `core.catalogo.isoterma_gab` y la integridad del catálogo: todo producto
tiene isoterma propia o por analogía. El charqui fue la excepción hasta S71, cuando
llegó la suya (Comaposada 2000, dos ramas con la meseta de la salmuera saturada).
"""

from __future__ import annotations

import pytest

from calculos.psicrometria import actividad_agua_isoterma
from core import catalogo

# Productos que deliberadamente corren sin isoterma (vacío desde S71).
SIN_ISOTERMA: set[str] = set()


@pytest.mark.parametrize("producto_id", sorted(catalogo.PRODUCTOS))
def test_todo_producto_tiene_isoterma(producto_id):
    iso = catalogo.isoterma_gab(producto_id)
    if producto_id in SIN_ISOTERMA:
        assert iso is None
    else:
        assert iso is not None, f"'{producto_id}' sin isoterma propia ni analogía"


@pytest.mark.parametrize(
    "producto_id", sorted(p for p in catalogo.PRODUCTOS if p not in SIN_ISOTERMA)
)
def test_aw_fisica_en_todo_el_rango(producto_id):
    """a_w(X) monótona, en [0, 1] y cerca de 1 con el producto fresco.

    Ningún producto puede caer en el escalón (S69) ni en la rampa X/X0.
    """
    iso = catalogo.isoterma_gab(producto_id)
    Xs = [0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    aws = []
    for X in Xs:
        try:
            aws.append(actividad_agua_isoterma(X, iso))
        except ValueError:
            aws.append(1.0)  # K < 1 y X sobre el máximo de la isoterma: agua libre
    assert all(0.0 <= a <= 1.0 for a in aws)
    assert all(b >= a for a, b in zip(aws, aws[1:]))
    assert aws[-1] > 0.9


@pytest.mark.parametrize(
    "producto_id, fuente",
    [
        ("aji_rojo", "pimiento_rojo"),
        ("mandioca", "papa"),
        ("durazno", "damasco"),
        ("ciruela", "damasco"),
        ("granada", "damasco"),
        ("perejil", "te_yerba"),
        ("apio", "te_yerba"),
        ("oregano", "te_yerba"),
        ("coca", "te_yerba"),
    ],
)
def test_analogias_aprobadas(producto_id, fuente):
    """Tabla de analogías aprobada por el usuario en S70."""
    iso = catalogo.isoterma_gab(producto_id)
    assert iso.origen == "analogia"
    assert iso.material_fuente == fuente


@pytest.mark.parametrize(
    "producto_id",
    [
        "manzana",
        "yacon",
        "papa",
        "pimiento_rojo",
        "tomate",
        "cebolla",
        "zanahoria_rallada",
        "te_yerba",
        "algarroba",
        "charqui_vacuno",
    ],
)
def test_isotermas_propias(producto_id):
    iso = catalogo.isoterma_gab(producto_id)
    assert iso.origen == "propia"
    assert iso.material_fuente == producto_id


def test_tomate_kiranoudis_a_45C():
    """Tomate: Kiranoudis 1993 Tabla 3 evaluada a 45 °C (C0 ×10⁵, k0 ×10²)."""
    iso = catalogo.isoterma_gab("tomate")
    assert (iso.X_m, iso.C, iso.K) == pytest.approx((0.182, 9.191, 0.695), rel=1e-3)


def test_analogia_no_encadena():
    """Una analogía apunta a una isoterma propia; nunca a otra analogía."""
    for pid, datos in catalogo.PRODUCTOS.items():
        destino = ((datos.get("isoterma") or {}).get("gab") or {}).get("analogia")
        if not destino:
            continue
        if destino in catalogo.PRODUCTOS:
            assert catalogo.isoterma_gab(destino).origen == "propia", (pid, destino)
        else:
            assert destino in catalogo.ISOTERMAS_REFERENCIA, (pid, destino)


def test_producto_inexistente_devuelve_none():
    assert catalogo.isoterma_gab("no_existe") is None


class TestMesetaCharqui:
    """Isoterma con escalón de la salmuera saturada (Comaposada 2000, S71)."""

    iso = catalogo.isoterma_gab("charqui_vacuno")

    def test_extremos_de_la_meseta(self):
        assert self.iso.meseta_a_w == 0.753
        assert self.iso.X_inicio_meseta == pytest.approx(0.169, abs=0.002)
        assert self.iso.X_fin_meseta == pytest.approx(0.662, abs=0.002)

    @pytest.mark.parametrize("X", [0.17, 0.3, 0.5, 0.66])
    def test_dentro_de_la_meseta_aw_es_la_de_la_salmuera(self, X):
        assert actividad_agua_isoterma(X, self.iso) == 0.753

    def test_continua_en_los_bordes(self):
        for X in (self.iso.X_inicio_meseta, self.iso.X_fin_meseta):
            for dX in (-1e-6, 1e-6):
                assert actividad_agua_isoterma(X + dX, self.iso) == pytest.approx(0.753, abs=1e-4)

    @pytest.mark.parametrize(
        "a_w, X_digitalizado",
        [(0.438, 0.091 / 1.2), (0.708, 0.178 / 1.2), (0.843, 1.04), (0.903, 1.32), (0.946, 1.63)],
    )
    def test_reproduce_los_puntos_de_comaposada(self, a_w, X_digitalizado):
        """Rama baja: sin sal ÷ 1.2; rama alta: 20 % NaCl b.s., 26 °C (Figs. 2 y 3)."""
        assert self.iso.X_de_aw(a_w) == pytest.approx(X_digitalizado, rel=0.08)

    def test_objetivo_en_la_rama_baja(self):
        """a_w = 0.60 cae debajo de la meseta: X ≈ 0.11, no los ~0.35 de una GAB única."""
        o = catalogo.objetivo_secado("charqui_vacuno")
        assert o.a_w == pytest.approx(0.60)
        assert o.X == pytest.approx(0.109, abs=0.003)

    def test_X_dentro_de_la_meseta_resuelve_a_la_aw_de_la_meseta(self, monkeypatch):
        """objetivo_secado invierte por bisección: con X declarado en la meseta da 0.753."""
        datos = dict(catalogo.PRODUCTOS["charqui_vacuno"], objetivo_secado={"X": 0.4})
        monkeypatch.setitem(catalogo.PRODUCTOS, "charqui_vacuno", datos)
        assert catalogo.objetivo_secado("charqui_vacuno").a_w == pytest.approx(0.753, abs=1e-6)


def _con_meseta(monkeypatch, meseta):
    datos = dict(catalogo.PRODUCTOS["charqui_vacuno"])
    gab = dict(datos["isoterma"]["gab"], meseta=meseta)
    datos["isoterma"] = dict(datos["isoterma"], gab=gab)
    monkeypatch.setitem(catalogo.PRODUCTOS, "charqui_vacuno", datos)


def test_CAT_MESETA_INVALIDA_sin_rama_alta(monkeypatch):
    _con_meseta(monkeypatch, {"a_w": 0.753})
    with pytest.raises(ValueError, match="CAT_MESETA_INVALIDA"):
        catalogo.isoterma_gab("charqui_vacuno")


def test_CAT_MESETA_INVALIDA_escalon_hacia_abajo(monkeypatch):
    _con_meseta(monkeypatch, {"a_w": 0.753, "rama_alta": {"X_m": 0.01, "C": 1.0, "K": 0.5}})
    with pytest.raises(ValueError, match="CAT_MESETA_INVALIDA"):
        catalogo.isoterma_gab("charqui_vacuno")
