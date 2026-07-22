"""
Tests del perfil logarítmico de viento (calculos/perfil_viento.py).

Fuente única de la conversión de viento entre alturas, compartida por la ingesta de
clima medido (normaliza el anemómetro del usuario al contrato) y el extractor eólico
de la chimenea (evalúa el viento en el tope). Ver S57.
"""

from __future__ import annotations

import math

import pytest

from calculos.perfil_viento import (
    Z0_DEFAULT_M,
    Z_CONTRATO_M,
    factor_altura,
    velocidad_a_altura,
)


class TestContrato:
    def test_altura_de_contrato_es_2m(self):
        """El contrato de `Clima.WS_ms` es 2 m (NASA POWER WS2M)."""
        assert Z_CONTRATO_M == 2.0

    def test_rugosidad_default_rural(self):
        assert Z0_DEFAULT_M == 0.05


class TestFactorAltura:
    def test_misma_altura_da_uno(self):
        assert factor_altura(2.0, z_origen_m=2.0, z0_m=0.05) == pytest.approx(1.0, rel=1e-12)

    def test_formula_analitica(self):
        esperado = math.log(6.0 / 0.05) / math.log(2.0 / 0.05)
        assert factor_altura(6.0, z_origen_m=2.0, z0_m=0.05) == pytest.approx(esperado, rel=1e-12)

    def test_crece_con_la_altura(self):
        f2 = factor_altura(2.0, z_origen_m=2.0, z0_m=0.05)
        f6 = factor_altura(6.0, z_origen_m=2.0, z0_m=0.05)
        f10 = factor_altura(10.0, z_origen_m=2.0, z0_m=0.05)
        assert f2 < f6 < f10

    def test_destino_dentro_de_capa_de_rugosidad_da_cero(self):
        assert factor_altura(0.01, z_origen_m=2.0, z0_m=0.05) == 0.0

    def test_es_reciproco(self):
        """Ir de 2 m a 10 m y volver debe devolver el valor original."""
        ida = factor_altura(10.0, z_origen_m=2.0, z0_m=0.05)
        vuelta = factor_altura(2.0, z_origen_m=10.0, z0_m=0.05)
        assert ida * vuelta == pytest.approx(1.0, rel=1e-12)

    def test_VIENTO_Z0_INVALIDO(self):
        with pytest.raises(ValueError, match="VIENTO_Z0_INVALIDO"):
            factor_altura(6.0, z_origen_m=2.0, z0_m=0.0)

    def test_VIENTO_Z_ORIGEN_INVALIDO(self):
        with pytest.raises(ValueError, match="VIENTO_Z_ORIGEN_INVALIDO"):
            factor_altura(6.0, z_origen_m=0.02, z0_m=0.05)


class TestVelocidadAAltura:
    def test_es_lineal_en_v(self):
        v1 = velocidad_a_altura(3.0, 6.0)
        v2 = velocidad_a_altura(6.0, 6.0)
        assert v2 == pytest.approx(2.0 * v1, rel=1e-12)

    def test_default_usa_altura_de_contrato(self):
        explicito = velocidad_a_altura(5.0, 6.0, z_origen_m=Z_CONTRATO_M, z0_m=Z0_DEFAULT_M)
        assert velocidad_a_altura(5.0, 6.0) == pytest.approx(explicito, rel=1e-12)

    def test_v_no_positiva_da_cero(self):
        assert velocidad_a_altura(0.0, 6.0) == 0.0
        assert velocidad_a_altura(-2.0, 6.0) == 0.0

    def test_magnitud_del_sesgo_corregido_en_s57(self):
        """Tratar el viento de 2 m como si fuera de 10 m lo subestima ~30 %.

        El factor ln(2/z0)/ln(10/z0) es independiente de la altura de destino y de
        la velocidad; con z0 = 0.05 vale ≈ 0.696, y como el término motriz de la
        turbina va con v², el ΔP quedaba en ≈ 0.485 del correcto.
        """
        z0 = 0.05
        for z_destino in (3.0, 6.0, 12.0):
            correcto = velocidad_a_altura(4.0, z_destino, z_origen_m=2.0, z0_m=z0)
            como_si_fuera_10m = velocidad_a_altura(4.0, z_destino, z_origen_m=10.0, z0_m=z0)
            ratio = como_si_fuera_10m / correcto
            assert ratio == pytest.approx(math.log(2.0 / z0) / math.log(10.0 / z0), rel=1e-12)
            assert ratio == pytest.approx(0.696, abs=1e-3)
            assert ratio**2 == pytest.approx(0.485, abs=1e-3)
