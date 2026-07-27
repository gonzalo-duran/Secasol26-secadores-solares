"""Política de recarga (core/operacion.py).

Nació en ``calculos/simulacion_ventana.py`` en S57, pero es modelo de datos: en
S59 pasó a colgar de ``Configuracion`` para que sobreviva a un guardar/cargar del
proyecto y entre sola en la huella de vigencia.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core.operacion import PoliticaRecarga
from core.proyecto import Configuracion


class TestValidacion:
    def test_RECARGA_HORA_INVALIDA(self):
        with pytest.raises(ValueError, match="RECARGA_HORA_INVALIDA"):
            PoliticaRecarga(hora_carga_h=24.0)

    def test_RECARGA_HORA_INVALIDA_negativa(self):
        with pytest.raises(ValueError, match="RECARGA_HORA_INVALIDA"):
            PoliticaRecarga(hora_carga_h=-1.0)

    def test_RECARGA_MANIOBRA_NEGATIVA(self):
        with pytest.raises(ValueError, match="RECARGA_MANIOBRA_NEGATIVA"):
            PoliticaRecarga(maniobra_h=-0.5)

    def test_RECARGA_UMBRAL_NEGATIVO(self):
        with pytest.raises(ValueError, match="RECARGA_UMBRAL_NEGATIVO"):
            PoliticaRecarga(umbral_pronostico_MJ_m2=-1.0)

    def test_medianoche_es_valida(self):
        assert PoliticaRecarga(hora_carga_h=0.0).hora_carga_h == 0.0


class TestSerializacion:
    def test_ida_y_vuelta(self):
        pol = PoliticaRecarga(
            activa=False,
            hora_carga_h=6.5,
            maniobra_h=2.0,
            exigir_pronostico=False,
            umbral_pronostico_MJ_m2=12.0,
        )
        assert PoliticaRecarga.desde_dict(pol.a_dict()) == pol

    def test_sin_datos_da_los_defaults(self):
        """Snapshots anteriores a S59: los defaults son los que usaron."""
        assert PoliticaRecarga.desde_dict(None) == PoliticaRecarga()
        assert PoliticaRecarga.desde_dict({}) == PoliticaRecarga()

    def test_dict_parcial_completa_con_defaults(self):
        pol = PoliticaRecarga.desde_dict({"hora_carga_h": 7.0})
        assert pol.hora_carga_h == 7.0
        assert pol.maniobra_h == PoliticaRecarga().maniobra_h

    def test_claves_desconocidas_se_ignoran(self):
        assert PoliticaRecarga.desde_dict({"campo_del_futuro": 1}) == PoliticaRecarga()

    def test_valor_invalido_del_snapshot_propaga_el_codigo(self):
        with pytest.raises(ValueError, match="RECARGA_HORA_INVALIDA"):
            PoliticaRecarga.desde_dict({"hora_carga_h": 99.0})


class TestEnConfiguracion:
    def test_la_configuracion_trae_una_politica_por_defecto(self):
        assert Configuracion().politica_recarga == PoliticaRecarga()

    def test_cada_configuracion_tiene_la_suya(self):
        """`default_factory`, no una instancia compartida a nivel de clase."""
        a, b = Configuracion(), Configuracion()
        assert a.politica_recarga == b.politica_recarga

    def test_replace_no_pisa_el_resto(self):
        cfg = Configuracion(paso_trabajo_s=900.0)
        nueva = replace(cfg, politica_recarga=PoliticaRecarga(hora_carga_h=6.0))
        assert nueva.paso_trabajo_s == 900.0
        assert nueva.politica_recarga.hora_carga_h == 6.0
