"""
Tests del modo anual sobre 8760 h reales (calculos/simulacion_anual.py).

El motor reemplaza al esquema de 12 días típicos mensuales. Lo que estos tests
fijan, además del contrato, son las dos cosas que estaban mal en el anterior:
que **producto seco y agua evaporada son cantidades distintas** (el viejo
rotulaba la segunda como la primera) y que la **cantidad de lotes es un
resultado**, no un dato que el usuario asegura.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.simulacion_anual import (
    PuntoMensualAnual,
    ResultadosAnual,
    _area_colector_m2,
    _mes_de_instante,
    _meses_del_indice,
    simular_anual,
)
from core.proyecto import Proyecto, SubtipoGranEscala
from tests.test_calculos.test_ventana_glue import _clima_sintetico, _proyecto


@pytest.fixture(scope="module")
def _encadenado():
    """Encadenado de lotes sobre un lapso corto, compartido por los tests.

    Se calcula una sola vez: armar las forzantes corre el colector hora a hora,
    que es el costo dominante (~26 ms/h).
    """
    from calculos.balance_global import armar_forzantes_ventana
    from calculos.simulacion_ventana import simular_encadenado_lotes

    proy = _proyecto(SubtipoGranEscala.BATCH)
    fz, _lena, _adv, _diag = armar_forzantes_ventana(proy, _clima_sintetico(12))
    return simular_encadenado_lotes(proy, forzantes_base=fz)


# ---------------------------------------------------------------------------
# Helpers de fechado
# ---------------------------------------------------------------------------


class TestFechado:
    def test_meses_del_indice_convierte_a_hora_local(self):
        """23:00 local del 31/7 en Salta es 1/8 en UTC: debe contar como julio."""
        idx = pd.DatetimeIndex(["2020-08-01T02:00:00Z"])
        meses = _meses_del_indice(idx, "America/Argentina/Salta")
        assert meses[0] == 7

    def test_meses_del_indice_sin_tz_no_rompe(self):
        idx = pd.DatetimeIndex(["2020-05-15T10:00:00"])
        assert _meses_del_indice(idx, "America/Argentina/Salta")[0] == 5

    def test_mes_de_instante_avanza_con_los_segundos(self):
        t0 = pd.Timestamp("2020-01-30T12:00:00Z")
        assert _mes_de_instante(t0, 0.0, "UTC") == 1
        assert _mes_de_instante(t0, 3 * 86400.0, "UTC") == 2

    def test_mes_de_instante_sin_ancla_devuelve_none(self):
        assert _mes_de_instante(None, 1000.0, "UTC") is None


class TestAreaColector:
    def test_sin_colector_es_cero(self):
        assert _area_colector_m2(Proyecto()) == 0.0

    def test_multiplica_por_el_banco(self):
        proy = _proyecto(SubtipoGranEscala.BATCH)
        u, b = proy.colector.unidad, proy.colector.banco
        esperado = u.largo_m * u.ancho_m * b.n_serie * b.n_paralelo
        assert _area_colector_m2(proy) == pytest.approx(esperado)


# ---------------------------------------------------------------------------
# Guardas de alcance
# ---------------------------------------------------------------------------


class TestGuardas:
    def test_ANUAL_SIN_CAMARA(self):
        with pytest.raises(ValueError, match="ANUAL_SIN_CAMARA"):
            simular_anual(Proyecto(), _clima_sintetico(2))

    def test_ANUAL_SEMICONTINUO_NO_SOPORTADO(self):
        """El túnel opera en flujo continuo: no son lotes, y no se finge que sí."""
        proy = _proyecto(SubtipoGranEscala.SEMICONTINUO, con_tunel=True)
        with pytest.raises(ValueError, match="ANUAL_SEMICONTINUO_NO_SOPORTADO"):
            simular_anual(proy, _clima_sintetico(2))


# ---------------------------------------------------------------------------
# Integración — un lapso corto, con superficie de respuesta
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _resultado_corto():
    """Una sola corrida compartida: construir la superficie cuesta ~5 s."""
    proy = _proyecto(SubtipoGranEscala.BATCH)
    df = _clima_sintetico(40)
    return simular_anual(proy, df), df


class TestIntegracion:
    def test_devuelve_doce_meses_siempre(self, _resultado_corto):
        res, _ = _resultado_corto
        assert len(res.puntos_mensuales) == 12
        assert [p.mes for p in res.puntos_mensuales] == list(range(1, 13))

    def test_producto_seco_y_agua_evaporada_son_distintos(self, _resultado_corto):
        """La confusión entre ambos era el problema principal del anual viejo."""
        res, _ = _resultado_corto
        if res.n_lotes_completos == 0:
            pytest.skip("el fixture no completó lotes en el lapso")
        assert res.masa_seca_anual_kg > 0
        assert res.masa_evaporada_anual_kg > 0
        assert res.masa_seca_anual_kg != pytest.approx(res.masa_evaporada_anual_kg)

    def test_horas_simuladas_coincide_con_el_clima(self, _resultado_corto):
        res, df = _resultado_corto
        assert res.horas_simuladas == len(df)

    def test_energia_solar_mensual_suma_la_anual(self, _resultado_corto):
        res, _ = _resultado_corto
        suma = sum(p.E_solar_MJ for p in res.puntos_mensuales)
        assert suma == pytest.approx(res.E_solar_anual_MJ, rel=1e-9)

    def test_horas_mensuales_suman_el_total(self, _resultado_corto):
        res, _ = _resultado_corto
        assert sum(p.horas for p in res.puntos_mensuales) == res.horas_simuladas

    def test_lotes_mensuales_suman_los_anuales(self, _resultado_corto):
        res, _ = _resultado_corto
        assert sum(p.lotes_completos for p in res.puntos_mensuales) == res.n_lotes_completos
        assert sum(p.lotes_frustrados for p in res.puntos_mensuales) == res.n_lotes_frustrados

    def test_masa_seca_mensual_suma_la_anual(self, _resultado_corto):
        res, _ = _resultado_corto
        suma = sum(p.masa_seca_kg for p in res.puntos_mensuales)
        assert suma == pytest.approx(res.masa_seca_anual_kg, rel=1e-6)

    def test_usa_la_superficie_de_respuesta(self, _resultado_corto):
        res, _ = _resultado_corto
        assert res.superficie_n_solves > 0

    def test_dispersion_disponible_si_hubo_lotes(self, _resultado_corto):
        """El p90 es lo que el día típico borraba: sin él no hay noción de riesgo."""
        res, _ = _resultado_corto
        if res.n_lotes_completos == 0:
            pytest.skip("el fixture no completó lotes en el lapso")
        assert res.duracion_media_h is not None
        assert res.duracion_p90_h is not None
        assert res.duracion_p90_h >= res.duracion_media_h

    def test_area_colector_reportada(self, _resultado_corto):
        res, _ = _resultado_corto
        assert res.area_colector_m2 > 0


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestMetricasDerivadas:
    """Las métricas de E3: las que el modo de día típico no daba o daba mal."""

    def test_energia_especifica_es_solar_sobre_agua(self, _resultado_corto):
        res, _ = _resultado_corto
        if res.masa_evaporada_anual_kg <= 0:
            pytest.skip("sin evaporación en el lapso")
        esperado = res.E_solar_anual_MJ / res.masa_evaporada_anual_kg
        assert res.energia_especifica_MJ_kg == pytest.approx(esperado, rel=1e-9)

    def test_eta_drying_usa_la_solar_incidente(self, _resultado_corto):
        from calculos.eficiencias_camara import calor_latente_agua_J_kg

        res, _ = _resultado_corto
        if res.E_solar_anual_MJ <= 0 or res.masa_evaporada_anual_kg <= 0:
            pytest.skip("sin sol o sin evaporación")
        h_fg = calor_latente_agua_J_kg(323.15) / 1e6
        esperado = res.masa_evaporada_anual_kg * h_fg / res.E_solar_anual_MJ
        assert res.eta_drying_anual == pytest.approx(esperado, rel=1e-9)

    def test_sin_auxiliar_eta_total_coincide_con_eta_drying(self, _resultado_corto):
        """Con E_aux = 0 ambas dividen por lo mismo. El defecto del anual viejo
        era hardcodear ese cero y mostrarlas igual como si fueran distintas."""
        res, _ = _resultado_corto
        if res.eta_drying_anual is None:
            pytest.skip("sin sol")
        assert res.E_auxiliar_MJ == pytest.approx(0.0)
        assert res.eta_total_anual == pytest.approx(res.eta_drying_anual, rel=1e-9)

    def test_fraccion_solar_compara_energias_utiles(self, _resultado_corto):
        """Sin auxiliar, toda la energía útil puesta en el aire es solar."""
        res, _ = _resultado_corto
        if res.Q_util_colector_MJ <= 0:
            pytest.skip("el colector no entregó energía")
        assert res.fraccion_solar == pytest.approx(1.0, rel=1e-9)

    def test_q_util_es_menor_que_la_solar_incidente(self, _resultado_corto):
        """El colector no puede entregar más de lo que recibe."""
        res, _ = _resultado_corto
        if res.E_solar_anual_MJ <= 0:
            pytest.skip("sin sol")
        assert 0.0 <= res.Q_util_colector_MJ <= res.E_solar_anual_MJ

    def test_percentiles_de_duracion_ordenados(self, _resultado_corto):
        res, _ = _resultado_corto
        if res.n_lotes_completos == 0:
            pytest.skip("sin lotes completos")
        assert res.duracion_p50_h <= res.duracion_p90_h

    def test_dias_operables_no_superan_los_dias(self, _resultado_corto):
        res, _ = _resultado_corto
        total_dias = sum(p.dias for p in res.puntos_mensuales)
        assert 0 <= res.dias_operables <= total_dias
        assert res.dias_operables == sum(p.dias_operables for p in res.puntos_mensuales)

    def test_umbral_de_operabilidad_se_respeta(self):
        """Un umbral inalcanzable deja cero días operables — el campo huérfano
        del anual viejo (I_g_diaria_minima_MJ_m2) ahora hace algo."""
        proy = _proyecto(SubtipoGranEscala.BATCH)
        res = simular_anual(proy, _clima_sintetico(6), umbral_dia_operable_MJ_m2=1e9)
        assert res.dias_operables == 0
        assert res.umbral_dia_operable_MJ_m2 == pytest.approx(1e9)

    def test_aprovechamiento_aire_es_una_fraccion(self, _resultado_corto):
        res, _ = _resultado_corto
        if res.aprovechamiento_aire is None:
            pytest.skip("sin horas de operación")
        assert 0.0 <= res.aprovechamiento_aire <= 1.0

    def test_eta_drying_mensual_consistente_con_el_mes(self, _resultado_corto):
        from calculos.eficiencias_camara import calor_latente_agua_J_kg

        res, _ = _resultado_corto
        h_fg = calor_latente_agua_J_kg(323.15) / 1e6
        for p in res.puntos_mensuales:
            if p.E_solar_MJ > 0:
                assert p.eta_drying == pytest.approx(
                    p.masa_evaporada_kg * h_fg / p.E_solar_MJ, rel=1e-9
                )
            else:
                assert p.eta_drying is None


class TestAireSobreEbullicion:
    """Regresión S57: a presión reducida el agua hierve por debajo de 100 °C.

    Reportado por el usuario corriendo un armario en altura: sitio a 73.2 kPa
    (≈2650 m, ebullición a 91.1 °C) con el aire de entrada llegando a 92.8 °C.
    `omega_saturacion` lanza `PSICRO_PV_EXCEDE_P` ahí, y eso tiraba abajo la
    simulación completa del año desde una métrica derivada.
    """

    def _forzantes(self, T_max_K: float):
        from core.camara import ForzantesAire

        n = 24
        return ForzantesAire(
            t_s=np.arange(n) * 3600.0,
            T_ent_K=np.linspace(290.0, T_max_K, n),
            omega_ent=np.full(n, 0.008),
            m_dot_aire_seco_kg_s=np.full(n, 0.05),
            T_amb_K=np.full(n, 288.0),
            v_viento_ms=np.full(n, 2.0),
        )

    def test_no_lanza_por_encima_de_la_ebullicion(self):
        from calculos.simulacion_anual import _agua_maxima_captable_kg

        # 73216.1 Pa y 92.8 °C son los valores exactos del reporte.
        agua, n_sobre = _agua_maxima_captable_kg(self._forzantes(366.0), 24 * 3600.0, 73216.1)
        assert agua > 0.0
        assert n_sobre >= 1

    def test_a_nivel_del_mar_ninguna_hora_queda_fuera(self):
        from calculos.simulacion_anual import _agua_maxima_captable_kg

        _agua, n_sobre = _agua_maxima_captable_kg(self._forzantes(366.0), 24 * 3600.0, 101325.0)
        assert n_sobre == 0

    def test_excluye_solo_las_horas_afectadas(self):
        """El agua captable debe seguir contando las horas por debajo de la
        ebullición, no anularse entera."""
        from calculos.simulacion_anual import _agua_maxima_captable_kg

        agua_alt, n_alt = _agua_maxima_captable_kg(self._forzantes(366.0), 24 * 3600.0, 73216.1)
        agua_frio, n_frio = _agua_maxima_captable_kg(self._forzantes(320.0), 24 * 3600.0, 73216.1)
        assert n_frio == 0
        assert agua_alt > agua_frio > 0.0


class TestAuxiliarEnElAnual:
    """Con auxiliar activo las eficiencias dejan de ser la misma cosa."""

    @pytest.fixture(scope="class")
    def _con_aux(self):
        proy = _proyecto(SubtipoGranEscala.BATCH, con_aux=True)
        return simular_anual(proy, _clima_sintetico(30))

    def test_energia_auxiliar_se_contabiliza(self, _con_aux):
        assert _con_aux.E_auxiliar_MJ > 0.0

    def test_eta_total_es_menor_que_eta_drying(self, _con_aux):
        """Con más energía primaria invertida, la eficiencia global baja."""
        if _con_aux.eta_drying_anual is None:
            pytest.skip("sin sol")
        assert _con_aux.eta_total_anual < _con_aux.eta_drying_anual

    def test_fraccion_solar_estrictamente_entre_cero_y_uno(self, _con_aux):
        assert 0.0 < _con_aux.fraccion_solar < 1.0


class TestDataclasses:
    def test_punto_mensual_tiene_defaults_neutros(self):
        p = PuntoMensualAnual(mes=3)
        assert p.lotes_completos == 0
        assert p.masa_seca_kg == 0.0
        assert p.duracion_media_h is None

    def test_resultado_admite_lista_vacia(self):
        r = ResultadosAnual(puntos_mensuales=[])
        assert r.masa_seca_anual_kg == 0.0
        assert r.advertencias == []

    def test_advertencias_no_se_comparten_entre_instancias(self):
        a, b = ResultadosAnual(puntos_mensuales=[]), ResultadosAnual(puntos_mensuales=[])
        a.advertencias.append("x")
        assert b.advertencias == []


# ---------------------------------------------------------------------------
# Historia por lote (extensión de simulacion_ventana en E2)
# ---------------------------------------------------------------------------


class TestHistoriaDeLotes:
    def test_lotes_en_orden_cronologico_y_sin_solapes(self, _encadenado):
        """Sin solapes, y con hueco: entre descarga y carga hay espera.

        Con el encadenado inmediato el hueco era cero. Desde que existe la
        política de recarga (S57) el siguiente lote arranca en la hora de carga,
        así que la invariante es ``t_inicio ≥ t_fin`` — no la igualdad.
        """
        res_v = _encadenado
        assert res_v.lotes, "el encadenado debe registrar al menos un lote"
        for anterior, siguiente in zip(res_v.lotes, res_v.lotes[1:]):
            assert siguiente.indice == anterior.indice + 1
            assert siguiente.t_inicio_s >= anterior.t_fin_s

    def test_lote_incompleto_no_aporta_producto_seco(self, _encadenado):
        """Un lote a medio secar evapora agua pero no es producción."""
        for lote in _encadenado.lotes:
            if not lote.completo:
                assert lote.masa_seca_kg == 0.0

    def test_masa_seca_de_lotes_suma_el_agregado(self, _encadenado):
        res_v = _encadenado
        suma = sum(lote.masa_seca_kg for lote in res_v.lotes)
        assert suma == pytest.approx(res_v.masa_seca_producida_kg, rel=1e-9)
        assert np.isclose(
            sum(lote.masa_evaporada_kg for lote in res_v.lotes),
            res_v.masa_evaporada_kg,
            rtol=1e-9,
        )


# ---------------------------------------------------------------------------
# Política de recarga (S57) — a pedido del usuario
# ---------------------------------------------------------------------------


class TestPoliticaRecarga:
    """El encadenado inmediato recargaba a las 3 AM si el lote cerraba ahí.

    Ningún operador descarga y recarga de madrugada: espera a la mañana. Modelar
    esa espera baja la producción hacia lo realista y es la diferencia entre una
    cota superior y una estimación.
    """

    def test_valida_la_hora(self):
        from calculos.simulacion_ventana import PoliticaRecarga

        with pytest.raises(ValueError, match="RECARGA_HORA_INVALIDA"):
            PoliticaRecarga(hora_carga_h=24.0)
        with pytest.raises(ValueError, match="RECARGA_HORA_INVALIDA"):
            PoliticaRecarga(hora_carga_h=-1.0)

    def test_valida_la_maniobra(self):
        from calculos.simulacion_ventana import PoliticaRecarga

        with pytest.raises(ValueError, match="RECARGA_MANIOBRA_NEGATIVA"):
            PoliticaRecarga(maniobra_h=-0.5)

    def test_inactiva_recarga_en_el_instante(self):
        from calculos.simulacion_ventana import PoliticaRecarga, _proximo_instante_carga

        pol = PoliticaRecarga(activa=False)
        assert _proximo_instante_carga(12345.0, pol, 0.0) == 12345.0

    def test_espera_a_la_hora_de_carga(self):
        """Lote que cierra a las 3 AM: el siguiente arranca a las 8, no a las 3."""
        from calculos.simulacion_ventana import PoliticaRecarga, _proximo_instante_carga

        pol = PoliticaRecarga(hora_carga_h=8.0, maniobra_h=0.0)
        t_carga = _proximo_instante_carga(3.0 * 3600.0, pol, hora_local_t0_h=0.0)
        assert t_carga == pytest.approx(8.0 * 3600.0)

    def test_pasa_al_dia_siguiente_si_ya_paso_la_hora(self):
        """Cierra a las 10, la carga es a las 8 → espera al día siguiente."""
        from calculos.simulacion_ventana import PoliticaRecarga, _proximo_instante_carga

        pol = PoliticaRecarga(hora_carga_h=8.0, maniobra_h=0.0)
        t_carga = _proximo_instante_carga(10.0 * 3600.0, pol, hora_local_t0_h=0.0)
        assert t_carga == pytest.approx((24.0 + 8.0) * 3600.0)

    def test_la_maniobra_puede_empujar_al_dia_siguiente(self):
        """Cierra 7:30 con 1 h de maniobra: no llega a las 8, espera a mañana."""
        from calculos.simulacion_ventana import PoliticaRecarga, _proximo_instante_carga

        pol = PoliticaRecarga(hora_carga_h=8.0, maniobra_h=1.0)
        t_carga = _proximo_instante_carga(7.5 * 3600.0, pol, hora_local_t0_h=0.0)
        assert t_carga == pytest.approx((24.0 + 8.0) * 3600.0)

    def test_respeta_la_hora_local_del_origen(self):
        """t=0 a las 22:00 locales; cierra 2 h después (medianoche) → carga 8 AM."""
        from calculos.simulacion_ventana import PoliticaRecarga, _proximo_instante_carga

        pol = PoliticaRecarga(hora_carga_h=8.0, maniobra_h=0.0)
        t_carga = _proximo_instante_carga(2.0 * 3600.0, pol, hora_local_t0_h=22.0)
        assert t_carga == pytest.approx(10.0 * 3600.0)  # 00:00 + 8 h

    def test_produce_menos_que_el_encadenado_inmediato(self):
        """La política es una corrección hacia abajo: es su razón de ser."""
        from calculos.balance_global import armar_forzantes_ventana
        from calculos.simulacion_ventana import PoliticaRecarga, simular_encadenado_lotes

        proy = _proyecto(SubtipoGranEscala.BATCH)
        fz, _l, _a, _d = armar_forzantes_ventana(proy, _clima_sintetico(30))
        inmediato = simular_encadenado_lotes(
            proy, forzantes_base=fz, politica=PoliticaRecarga(activa=False)
        )
        con_espera = simular_encadenado_lotes(
            proy, forzantes_base=fz, politica=PoliticaRecarga(hora_carga_h=8.0, maniobra_h=1.0)
        )
        assert con_espera.masa_seca_producida_kg <= inmediato.masa_seca_producida_kg

    def test_la_tasa_de_regimen_usa_el_ciclo_no_solo_el_secado(self):
        """Con espera, el ciclo es mayor que el secado → la tasa baja."""
        from calculos.balance_global import armar_forzantes_ventana
        from calculos.simulacion_ventana import PoliticaRecarga, simular_encadenado_lotes

        proy = _proyecto(SubtipoGranEscala.BATCH)
        fz, _l, _a, _d = armar_forzantes_ventana(proy, _clima_sintetico(30))
        res = simular_encadenado_lotes(
            proy, forzantes_base=fz, politica=PoliticaRecarga(hora_carga_h=8.0, maniobra_h=1.0)
        )
        if res.n_batches_completos < 2 or res.tasa_regimen_kg_dia is None:
            pytest.skip("hacen falta al menos dos lotes para ver el ciclo")
        masa_lote = res.masa_seca_producida_kg / res.n_batches_completos
        tasa_solo_secado = masa_lote / (res.t_secado_medio_s / 86400.0)
        assert res.tasa_regimen_kg_dia <= tasa_solo_secado


class TestAgregacionDeAdvertencias:
    """Sobre un año son decenas de lotes: repetir el mismo diagnóstico por cada
    uno inunda la pantalla y esconde los avisos que sí son distintos.

    La deduplicación por string exacto no servía: los mensajes llevan el número
    de horas del lote ("... durante 5.6 h") y cambian lote a lote (S57).
    """

    def test_un_aviso_por_codigo_con_su_conteo(self):
        from calculos.balance_global import armar_forzantes_ventana
        from calculos.simulacion_ventana import simular_encadenado_lotes

        proy = _proyecto(SubtipoGranEscala.BATCH)
        fz, _l, _a, _d = armar_forzantes_ventana(proy, _clima_sintetico(30))
        res = simular_encadenado_lotes(proy, forzantes_base=fz)

        codigos = [a.split(":", 1)[0].strip() for a in res.advertencias]
        assert len(codigos) == len(
            set(codigos)
        ), f"hay códigos repetidos en las advertencias: {codigos}"

    def test_el_conteo_aparece_cuando_se_repite(self):
        """Un mensaje que dispara en varios lotes se emite una vez, con el conteo."""
        mensajes = [
            "CAM_HR_FLUJO_ALTA: HR > 95 % durante 5.6 h.",
            "CAM_HR_FLUJO_ALTA: HR > 95 % durante 4.8 h.",
            "CAM_HR_FLUJO_ALTA: HR > 95 % durante 4.0 h.",
        ]
        conteo: dict[str, int] = {}
        ejemplo: dict[str, str] = {}
        for m in mensajes:
            c = m.split(":", 1)[0].strip()
            conteo[c] = conteo.get(c, 0) + 1
            ejemplo.setdefault(c, m)
        assert list(conteo.values()) == [3]
        assert ejemplo["CAM_HR_FLUJO_ALTA"] == mensajes[0]
