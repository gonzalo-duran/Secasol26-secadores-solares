"""Con carros, el aire atraviesa la cámara en serie, no en una sola pila (S70).

Hasta S70 la transferencia trataba las n_carros × bandejas_por_carro bandejas
como una única pila en paralelo: en ADITAL (24 × 14) la velocidad sobre el
producto salía ~26× baja y el h, en nivel de convección natural. ``motor_calc``
ya trataba los carros en serie para la pérdida de carga.
"""

from __future__ import annotations

import dataclasses

import pytest

from calculos.camara_calc import area_canal_entre_bandejas_m2, longitud_flujo_producto_m
from core import presets
from core.camara import ConfiguracionCarros


def _adital():
    return presets.camara_gran_escala()


def test_canales_de_un_solo_carro():
    cam = _adital()
    b, g = cam.bandejas, cam.geometria
    libre = b.separacion_entre_bandejas_m - b.espesor_capa_m
    assert area_canal_entre_bandejas_m2(cam) == pytest.approx(
        g.ancho_m * libre * (cam.carros.bandejas_por_carro - 1)
    )


def test_la_seccion_no_crece_con_la_cantidad_de_carros():
    """Agregar carros en fila alarga el túnel, no ensancha el paso del aire."""
    cam = _adital()
    mas = dataclasses.replace(
        cam,
        tunel=None,
        geometria=dataclasses.replace(cam.geometria, largo_m=2 * cam.geometria.largo_m),
        carros=dataclasses.replace(cam.carros, n_carros=2 * cam.carros.n_carros),
    )
    assert area_canal_entre_bandejas_m2(mas) == pytest.approx(area_canal_entre_bandejas_m2(cam))


def test_la_capa_limite_se_reinicia_en_cada_carro():
    cam = _adital()
    assert longitud_flujo_producto_m(cam) == pytest.approx(
        cam.geometria.largo_m / cam.carros.n_carros
    )


def test_largo_de_carro_declarado():
    cam = dataclasses.replace(
        _adital(), carros=ConfiguracionCarros(n_carros=24, bandejas_por_carro=14, largo_carro_m=0.7)
    )
    assert longitud_flujo_producto_m(cam) == pytest.approx(0.7)


def test_sin_carros_es_el_largo_de_la_camara():
    base = _adital()
    cam = dataclasses.replace(
        base,
        carros=None,
        tunel=None,
        bandejas=dataclasses.replace(base.bandejas, n_bandejas=14),
        carga_producto=dataclasses.replace(base.carga_producto, masa_total_kg=100.0),
    )
    assert longitud_flujo_producto_m(cam) == pytest.approx(cam.geometria.largo_m)
