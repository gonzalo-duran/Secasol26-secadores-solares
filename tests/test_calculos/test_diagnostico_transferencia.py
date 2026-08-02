"""Diagnóstico de acoplamiento aire↔producto (NTU) — S63, etapa 3.

El NTU es el número que dice si el secador está bien cargado, y hasta S63 no
aparecía en ninguna vista: se podía diseñar una cámara que transfería 200 veces
menos de lo que debía sin que nada lo insinuara.
"""

from __future__ import annotations

import pytest

from calculos.camara_calc import diagnostico_transferencia
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    DireccionFlujo,
    GeometriaCamara,
)

_P = 89202.0


def _camara(direccion=DireccionFlujo.VERTICAL_ASCENDENTE, caudal=0.0342) -> Camara:
    return Camara(
        geometria=GeometriaCamara(largo_m=0.5, ancho_m=0.5, alto_m=1.1),
        bandejas=ConfiguracionBandejas(
            n_bandejas=10,
            area_bandeja_m2=0.25,
            espesor_capa_m=0.02,
            separacion_entre_bandejas_m=0.07,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=caudal, direccion_flujo=direccion),
        construccion=ConstruccionCamara(),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=9.5,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
        ),
    )


def _diag(cam):
    return diagnostico_transferencia(
        cam, T_operacion_K=324.6, HR_operacion=0.06, T_amb_K=290.0, P_Pa=_P
    )


class TestDiagnosticoTransferencia:

    def test_ntu_es_km_por_area_sobre_caudal(self):
        cam = _camara()
        d = _diag(cam)
        assert d.NTU == pytest.approx(
            d.K_m_kg_m2s * d.A_prod_m2 / cam.flujo.caudal_masico_kg_s, rel=1e-9
        )

    def test_acercamiento_es_el_de_la_cadena_de_etapas(self):
        """El diagnóstico describe el modelo que después integra el motor.

        Hasta S64 calculaba el CSTR (``NTU/(1+NTU)``) aunque el motor resuelve
        una cadena de N etapas desde S63.
        """
        from calculos.camara_calc import _N_ETAPAS_OVERFLOW

        d = _diag(_camara())
        N = _N_ETAPAS_OVERFLOW
        assert d.acercamiento_equilibrio == pytest.approx(1.0 - (1.0 + d.NTU / N) ** (-N))
        assert 0.0 <= d.acercamiento_equilibrio <= 1.0

    def test_cross_flow_sobre_bandeja_queda_lejos_del_equilibrio(self):
        """Única topología (S64): el aire barre la bandeja y apenas se moja."""
        d = _diag(_camara(DireccionFlujo.HORIZONTAL))
        assert d.NTU < 1.0
        assert d.acercamiento_equilibrio < 0.5

    def test_mas_caudal_baja_el_ntu(self):
        """Con más aire por la misma superficie, cada kg se moja menos."""
        poco = _diag(_camara(caudal=0.01))
        mucho = _diag(_camara(caudal=0.20))
        assert mucho.NTU < poco.NTU

    def test_caudal_nulo_no_divide_por_cero(self):
        cam = _camara()
        cam.flujo.caudal_masico_kg_s = 0.0
        d = _diag(cam)
        assert d.NTU == 0.0
        assert d.acercamiento_equilibrio == 0.0
