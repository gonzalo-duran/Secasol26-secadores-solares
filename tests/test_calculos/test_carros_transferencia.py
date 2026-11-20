"""Sección de paso y largo de placa del aire sobre el producto (S70).

- Con carros el aire los atraviesa en serie, no como una sola pila: hasta S70 la
  transferencia trataba las n_carros × bandejas_por_carro bandejas como paralelas y en
  ADITAL (24 × 14) la velocidad sobre el producto salía ~26× baja. ``motor_calc`` ya
  trataba los carros en serie para la pérdida de carga.
- La capa límite se reinicia en el borde de cada bandeja (Fase 1 del plan de
  evaporación): la placa es la bandeja, no la cámara.
"""

from __future__ import annotations

import dataclasses

import pytest

from calculos.camara_calc import area_canal_entre_bandejas_m2, longitud_flujo_producto_m
from core import presets
from core.camara import Camara, ConfiguracionCarros


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


def test_la_capa_limite_se_reinicia_en_cada_bandeja():
    """La placa es la bandeja (área/ancho), más corta que el carro en ADITAL."""
    cam = _adital()
    L_bandeja = cam.bandejas.area_bandeja_m2 / cam.geometria.ancho_m
    assert L_bandeja < cam.geometria.largo_m / cam.carros.n_carros
    assert longitud_flujo_producto_m(cam) == pytest.approx(L_bandeja)


def test_el_carro_acota_si_es_mas_corto_que_la_bandeja():
    cam = dataclasses.replace(
        _adital(),
        carros=ConfiguracionCarros(n_carros=24, bandejas_por_carro=14, largo_carro_m=0.2),
    )
    assert longitud_flujo_producto_m(cam) == pytest.approx(0.2)


def test_sin_carros_es_el_largo_de_la_bandeja():
    cam = Camara()
    assert longitud_flujo_producto_m(cam) == pytest.approx(
        cam.bandejas.area_bandeja_m2 / cam.geometria.ancho_m
    )


def test_bandeja_que_ocupa_toda_la_planta():
    """Caso borde: la validación de la cámara impide bandejas más grandes que la planta."""
    cam = Camara()
    planta = cam.geometria.largo_m * cam.geometria.ancho_m
    cam = dataclasses.replace(
        cam, bandejas=dataclasses.replace(cam.bandejas, area_bandeja_m2=planta)
    )
    assert longitud_flujo_producto_m(cam) == pytest.approx(cam.geometria.largo_m)
