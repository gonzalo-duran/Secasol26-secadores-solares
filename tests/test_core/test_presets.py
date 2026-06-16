"""
Tests del preset de sistema completo de gran escala (S41, core/presets.py).

El preset es el secador híbrido ADITAL (tesis cap. 3) y es la misma fuente de
verdad que usa ``validacion/validacion_adital.py``.
"""

from __future__ import annotations

import pytest

from core.presets import (
    camara_gran_escala,
    cano_maestro_gran_escala,
    colector_gran_escala,
    motor_gran_escala,
)


def test_camara_preset_valida_y_con_carros():
    cam = camara_gran_escala()
    assert cam.carros is not None
    assert cam.carros.n_carros == 24
    assert cam.tunel is not None
    assert cam.tunel.n_zonas == cam.carros.n_carros  # 1 carro por zona
    # Total de bandejas derivado de la jerarquía carro → bandejas.
    assert cam.bandejas.n_bandejas == cam.carros.n_bandejas_total


def test_camara_preset_area_de_secado_adital():
    """Superficie total de secado ≈ 320 m² (5000 kg en lecho de 4 cm)."""
    cam = camara_gran_escala()
    area = cam.bandejas.n_bandejas * cam.bandejas.area_bandeja_m2
    assert 300.0 < area < 340.0
    assert cam.carga_producto.masa_total_kg == pytest.approx(5000.0)


def test_colector_preset_banco_adital():
    col = colector_gran_escala()
    assert col.banco.n_paralelo == 26
    assert col.banco.cano_maestro is not None
    assert col.banco.cano_maestro.largo_m == pytest.approx(18.0)
    # Galvanizado desnudo: α ≈ 0.35, no el 0.90 de chapa pintada.
    assert col.banco.cano_maestro.absortancia_solar == pytest.approx(0.35)


def test_motor_preset_caudal_industrial():
    mot = motor_gran_escala()
    # ≈ 3.8 kg/s de aire → varios m³/s (no los 20 L/s del default de armario).
    assert mot.caudal_volumetrico_m3_s > 3.0


def test_cano_preset_consistente_con_colector():
    assert colector_gran_escala().banco.cano_maestro.largo_m == cano_maestro_gran_escala().largo_m
