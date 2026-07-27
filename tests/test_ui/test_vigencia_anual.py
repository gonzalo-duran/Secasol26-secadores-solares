"""Vigencia del resultado anual (ui/componentes/vigencia.py + hash de entradas).

El resultado anual se calcula en P4 y se **muestra** en P7 y en el reporte, que
no lo recalculan. Sin detección de desactualización, cambiar el auxiliar después
de correr el año dejaba a P7 mostrando números viejos: en un reporte real del
usuario (S58) el bloque global decía ``E_aux = 74.34 MJ`` y el bloque anual del
mismo PDF, ``0.0 MJ``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from calculos.simulacion_anual import hash_entradas_anual
from calculos.simulacion_ventana import PoliticaRecarga
from core.auxiliar import Auxiliar, CargaArranque, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import Camara, CargaProducto, GeometriaCamara
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, Proyecto, Tipologia
from ui.componentes.vigencia import (
    CLAVE_HASH,
    CLAVE_RESULTADO,
    resultado_anual_vigente,
)


def _proyecto_base() -> Proyecto:
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.emplazamiento = Emplazamiento()
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.0, alto_m=1.5),
        carga_producto=CargaProducto(producto_id="manzana"),
    )
    return p


def _auxiliar_del_usuario() -> Auxiliar:
    """El auxiliar de la corrida que destapó el problema (S58)."""
    return Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=2000.0,
        set_point_T_K=328.15,
        temperatura_maxima_salida_K=333.15,
        disponible_nocturno=False,
        cargas_arranque=[
            CargaArranque(hora_inicio_h=5.0, duracion_h=3.0),
            CargaArranque(hora_inicio_h=19.0, duracion_h=3.0),
        ],
    )


class TestHashEntradasAnual:
    def test_es_estable_para_la_misma_configuracion(self):
        assert hash_entradas_anual(_proyecto_base()) == hash_entradas_anual(_proyecto_base())

    def test_agregar_el_auxiliar_cambia_el_hash(self):
        """El caso real: se corrió el año y después se configuró P5."""
        proy = _proyecto_base()
        antes = hash_entradas_anual(proy)
        proy.auxiliar = _auxiliar_del_usuario()
        assert hash_entradas_anual(proy) != antes

    def test_cambiar_el_setpoint_del_auxiliar_cambia_el_hash(self):
        proy = _proyecto_base()
        proy.auxiliar = _auxiliar_del_usuario()
        antes = hash_entradas_anual(proy)
        proy.auxiliar.set_point_T_K = 333.15
        assert hash_entradas_anual(proy) != antes

    def test_cambiar_la_camara_cambia_el_hash(self):
        proy = _proyecto_base()
        antes = hash_entradas_anual(proy)
        proy.camara.geometria = GeometriaCamara(largo_m=3.0, ancho_m=1.0, alto_m=1.5)
        assert hash_entradas_anual(proy) != antes

    def test_cambiar_la_politica_cambia_el_hash(self):
        """La política vive en `Configuracion` (S59): entra al hash por la sección."""
        proy = _proyecto_base()
        h_default = hash_entradas_anual(proy)
        proy.configuracion = replace(
            proy.configuracion, politica_recarga=PoliticaRecarga(hora_carga_h=6.0)
        )
        assert hash_entradas_anual(proy) != h_default

    def test_el_umbral_de_pronostico_entra_al_hash(self):
        proy = _proyecto_base()
        proy.configuracion = replace(
            proy.configuracion,
            politica_recarga=PoliticaRecarga(umbral_pronostico_MJ_m2=8.0),
        )
        h1 = hash_entradas_anual(proy)
        proy.configuracion = replace(
            proy.configuracion,
            politica_recarga=PoliticaRecarga(umbral_pronostico_MJ_m2=15.0),
        )
        assert hash_entradas_anual(proy) != h1

    def test_no_revienta_sin_clima_ni_colector(self):
        assert isinstance(hash_entradas_anual(Proyecto()), str)


class TestResultadoAnualVigente:
    def test_sin_resultado_no_hay_nada_desactualizado(self):
        res, vigente = resultado_anual_vigente(_proyecto_base(), {})
        assert res is None and vigente is True

    def test_vigente_si_no_cambio_nada(self):
        proy = _proyecto_base()
        estado = {
            CLAVE_RESULTADO: "resultado",
            CLAVE_HASH: hash_entradas_anual(proy),
        }
        res, vigente = resultado_anual_vigente(proy, estado)
        assert res == "resultado" and vigente is True

    def test_agregar_auxiliar_lo_invalida(self):
        """El caso del reporte contradictorio, en un test."""
        proy = _proyecto_base()
        estado = {
            CLAVE_RESULTADO: "resultado",
            CLAVE_HASH: hash_entradas_anual(proy),
        }
        proy.auxiliar = _auxiliar_del_usuario()
        res, vigente = resultado_anual_vigente(proy, estado)
        assert res == "resultado", "el resultado se devuelve igual, para poder avisar"
        assert vigente is False

    def test_sin_hash_guardado_no_se_da_por_vigente(self):
        """Resultado de una sesión anterior al mecanismo: no es verificable."""
        estado = {CLAVE_RESULTADO: "resultado"}
        _res, vigente = resultado_anual_vigente(_proyecto_base(), estado)
        assert vigente is False


class TestEnergiaAuxiliarMensual:
    """El auxiliar tiene que verse mes a mes, no solo como total del año."""

    def test_el_punto_mensual_expone_la_energia_auxiliar(self):
        from calculos.simulacion_anual import PuntoMensualAnual

        p = PuntoMensualAnual(mes=1)
        assert p.E_auxiliar_MJ == 0.0

    def test_con_auxiliar_hay_meses_con_energia(self):
        from calculos.simulacion_anual import simular_anual
        from core.proyecto import SubtipoGranEscala
        from tests.test_calculos.test_ventana_glue import _clima_sintetico, _proyecto

        proy = _proyecto(SubtipoGranEscala.BATCH)
        proy.auxiliar = _auxiliar_del_usuario()
        res = simular_anual(proy, _clima_sintetico(12))
        assert res.E_auxiliar_MJ > 0
        assert sum(p.E_auxiliar_MJ for p in res.puntos_mensuales) == pytest.approx(
            res.E_auxiliar_MJ, rel=1e-6
        ), "la desagregación mensual tiene que sumar el total del año"
