"""Isotermas del catálogo de productos: resolución propia / analogía (S70).

Cubre `core.catalogo.isoterma_gab` y la integridad del catálogo: desde S70
todo producto tiene isoterma propia o por analogía, salvo el charqui (la sal
cambia la isoterma, no se presta la de un vegetal).
"""

from __future__ import annotations

import pytest

from calculos.psicrometria import actividad_agua_desde_X_GAB
from core import catalogo

# Productos que deliberadamente corren sin isoterma (decisión S70).
SIN_ISOTERMA = {"charqui_vacuno"}


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
            aws.append(actividad_agua_desde_X_GAB(X, iso.X_m, iso.C, iso.K))
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
