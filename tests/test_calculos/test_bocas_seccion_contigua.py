"""Bocas con sección distinta a la del elemento contiguo (S62).

Hasta S62 el modelo suponía que la boca de entrada de la cámara tenía la misma
sección que la salida del colector, y la de salida la misma que la base de la
chimenea. Cuando no la tienen hay una contracción o una expansión que disipa
energía, y en convección natural esa pérdida **define el caudal**: estrangular un
empalme frena el tiro.

Cada boca puede ahora **heredar** la sección del elemento contiguo —que es el
caso sin pérdida— o declararse aparte, con la posibilidad de desarrollar la
transición para recuperar presión.
"""

from __future__ import annotations

import pytest

from calculos.balance_global import (
    _areas_bocas,
    area_base_chimenea_m2,
    area_salida_colector_m2,
    calcular_todo,
)

from .test_conveccion_natural_cajon import _proyecto


def _corre(proyecto):
    return calcular_todo(
        proyecto,
        T_amb_K=293.15,
        I_g_W_m2=800.0,
        v_viento_ms=2.0,
        T_entrada_K=293.15,
        HR_camara=0.5,
    )


class TestSeccionesContiguas:
    def test_area_de_la_chimenea_es_la_del_circulo(self):
        import math

        p = _proyecto(A_boca=0.05, con_chimenea=True)
        esperado = math.pi * p.chimenea.diametro_m**2 / 4.0
        assert area_base_chimenea_m2(p) == pytest.approx(esperado)

    def test_sin_chimenea_no_hay_seccion_contigua(self):
        assert area_base_chimenea_m2(_proyecto(A_boca=0.05)) is None

    def test_sin_colector_no_hay_seccion_contigua(self):
        assert area_salida_colector_m2(_proyecto(A_boca=0.05)) is None

    def test_el_colector_suma_las_ramas_en_paralelo(self):
        """Todas descargan al mismo plenum: el aire llega por la suma."""
        from core.colector import BancoColectores, Colector, ColectorUnidad

        p = _proyecto(A_boca=0.05)
        p.colector = Colector(
            unidad=ColectorUnidad(ancho_m=1.0, espaciado_m=0.025),
            banco=BancoColectores(n_serie=1, n_paralelo=4),
        )
        assert area_salida_colector_m2(p) == pytest.approx(0.025 * 1.0 * 4)


class TestHerenciaDeSeccion:
    def test_heredar_resuelve_el_area_desde_la_chimenea(self):
        p = _proyecto(A_boca=0.05, con_chimenea=True)
        p.camara.flujo.area_salida_aire_m2 = None
        p.camara.flujo.boca_salida_hereda_seccion = True
        _, A_out = _areas_bocas(p)
        assert A_out == pytest.approx(area_base_chimenea_m2(p))

    def test_pedir_herencia_sin_elemento_contiguo_deja_la_boca_sin_resolver(self):
        """Sin chimenea la descarga es a la atmósfera: no hay de dónde heredar."""
        p = _proyecto(A_boca=0.05)  # sin chimenea
        p.camara.flujo.boca_salida_hereda_seccion = True
        p.camara.flujo.area_salida_aire_m2 = None
        assert _areas_bocas(p) == (None, None)

    def test_el_default_conserva_el_comportamiento_previo(self):
        """Los flags arrancan en False: un proyecto viejo se resuelve igual."""
        p = _proyecto(A_boca=0.05)
        f = p.camara.flujo
        assert f.boca_entrada_hereda_seccion is False
        assert f.boca_salida_hereda_seccion is False
        assert _areas_bocas(p) == (pytest.approx(0.05), pytest.approx(0.05))


class TestEfectoSobreElTiro:
    """En convección natural la pérdida del empalme define el caudal."""

    def _caudal(self, A_out: float, L_transicion: float = 0.0) -> float:
        p = _proyecto(A_boca=0.05, con_chimenea=True)
        p.camara.flujo.area_salida_aire_m2 = A_out
        p.camara.flujo.longitud_transicion_salida_m = L_transicion
        res = _corre(p)
        assert res.chimenea is not None
        return float(res.chimenea["m_punto_kgs"])

    def test_estrangular_la_boca_baja_el_caudal(self):
        A_chim = area_base_chimenea_m2(_proyecto(A_boca=0.05, con_chimenea=True))
        assert self._caudal(A_chim * 0.1) < self._caudal(A_chim)

    def test_boca_igual_a_la_chimenea_no_penaliza(self):
        """Con secciones iguales el término de transición es exactamente cero."""
        A_chim = area_base_chimenea_m2(_proyecto(A_boca=0.05, con_chimenea=True))
        from calculos.transiciones_seccion import coeficiente_transicion

        assert coeficiente_transicion(A_chim, A_chim) == 0.0

    def test_desarrollar_la_transicion_recupera_caudal(self):
        A_chim = area_base_chimenea_m2(_proyecto(A_boca=0.05, con_chimenea=True))
        A_out = A_chim * 0.1
        assert self._caudal(A_out, L_transicion=0.6) > self._caudal(A_out, L_transicion=0.0)


class TestBackCompat:
    def test_un_proyecto_sin_los_campos_nuevos_no_cambia(self):
        """Sin herencia ni transiciones declaradas, el resultado es el de S61."""
        p = _proyecto(A_boca=0.05, con_chimenea=True)
        f = p.camara.flujo
        assert f.longitud_transicion_entrada_m == 0.0
        assert f.longitud_transicion_salida_m == 0.0
        res = _corre(p)
        assert res.chimenea is not None
        assert res.chimenea["m_punto_kgs"] > 0.0
