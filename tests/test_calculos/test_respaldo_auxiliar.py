"""Tests del auxiliar en modo RESPALDO_INDEPENDIENTE (S62).

Hasta S61 el modo respaldo no tenía física propia: aplicaba su ΔT sobre el aire
de entrada igual que SERIE_POSCOLECTOR, así que elegirlo no cambiaba nada. Ahora
la potencia se inyecta en el **nodo de aire** de la cámara —la fuente está
adentro— y, si hay set-point, se modula algebraicamente contra ``T_flujo``.

Ver ``docs/notas/spec_conveccion_natural_y_respaldo.md`` §2.2.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.balance_global import calcular_todo
from calculos.camara_termodinamica import resolver_estado_camara
from core.auxiliar import (
    Auxiliar,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
    advertencias_auxiliar,
)

from .test_conveccion_natural_cajon import _proyecto

# Estado algebraico de referencia: cajón a 20 °C, producto húmedo.
_BASE_ESTADO = dict(
    T_prod_K=293.15,
    X_prod_kg_kg=4.0,
    T_ent_K=293.15,
    omega_ent_kg_kg=0.008,
    A_prod_m2=2.0,
    A_cuerpo_m2=6.0,
    m_dot_as_kg_s=0.02,
    h_conv_W_m2K=5.0,
    K_m_kg_m2s=0.005,
    h_w_W_m2K=10.0,
    k_aisl_W_mK=0.04,
    esp_cam_m=0.05,
    T_amb_K=293.15,
    P_Pa=89150.0,
    aw_func=lambda X: 0.95,
)


def _corre(aux, *, I_g_W_m2: float = 500.0, A_boca: float | None = 0.05):
    proyecto = _proyecto(A_boca=A_boca)
    proyecto.auxiliar = aux
    return calcular_todo(
        proyecto,
        T_amb_K=293.15,
        I_g_W_m2=I_g_W_m2,
        v_viento_ms=2.0,
        T_entrada_K=293.15,
        HR_camara=0.5,
    )


def _respaldo(**kwargs) -> Auxiliar:
    base = dict(
        potencia_nominal_W=800.0,
        modo_operacion=ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
        disponible_nocturno=True,
    )
    base.update(kwargs)
    return Auxiliar(**base)


# ---------------------------------------------------------------------------
# Solve algebraico: Q_aux al nodo de aire
# ---------------------------------------------------------------------------


class TestQAuxEnElBalanceDeAire:
    def test_sin_auxiliar_reproduce_el_balance_historico(self):
        """Q_aux = 0 debe dar exactamente lo de antes (back-compat bit a bit)."""
        sin = resolver_estado_camara(**_BASE_ESTADO)
        con_cero = resolver_estado_camara(**_BASE_ESTADO, Q_aux_max_W=0.0)
        assert con_cero.T_flujo_K == sin.T_flujo_K
        assert con_cero.Q_aux_W == 0.0

    def test_Q_aux_sube_la_temperatura_del_aire(self):
        sin = resolver_estado_camara(**_BASE_ESTADO)
        con = resolver_estado_camara(**_BASE_ESTADO, Q_aux_max_W=500.0)
        assert con.T_flujo_K > sin.T_flujo_K
        assert con.Q_aux_W == pytest.approx(500.0)

    def test_el_aporte_es_lineal_en_la_potencia(self):
        """T_flujo = (num + Q_aux)/den ⇒ doble potencia, doble incremento."""
        sin = resolver_estado_camara(**_BASE_ESTADO)
        uno = resolver_estado_camara(**_BASE_ESTADO, Q_aux_max_W=400.0)
        dos = resolver_estado_camara(**_BASE_ESTADO, Q_aux_max_W=800.0)
        assert (dos.T_flujo_K - sin.T_flujo_K) == pytest.approx(
            2.0 * (uno.T_flujo_K - sin.T_flujo_K)
        )


class TestSetPoint:
    def test_alcanza_el_objetivo_exactamente(self):
        """Es una inversión algebraica, no una iteración: el error es cero."""
        sin = resolver_estado_camara(**_BASE_ESTADO)
        T_set = sin.T_flujo_K + 5.0
        est = resolver_estado_camara(**_BASE_ESTADO, Q_aux_max_W=5000.0, T_set_aux_K=T_set)
        assert est.T_flujo_K == pytest.approx(T_set, abs=1e-9)
        assert 0.0 < est.Q_aux_W < 5000.0

    def test_no_gasta_si_el_objetivo_ya_esta_superado(self):
        sin = resolver_estado_camara(**_BASE_ESTADO)
        est = resolver_estado_camara(
            **_BASE_ESTADO, Q_aux_max_W=5000.0, T_set_aux_K=sin.T_flujo_K - 5.0
        )
        assert est.Q_aux_W == 0.0
        assert est.T_flujo_K == pytest.approx(sin.T_flujo_K)

    def test_satura_en_el_techo_si_esta_subdimensionado(self):
        sin = resolver_estado_camara(**_BASE_ESTADO)
        est = resolver_estado_camara(
            **_BASE_ESTADO, Q_aux_max_W=50.0, T_set_aux_K=sin.T_flujo_K + 50.0
        )
        assert est.Q_aux_W == pytest.approx(50.0)
        assert est.T_flujo_K < sin.T_flujo_K + 50.0


# ---------------------------------------------------------------------------
# Coacción del tipo de fuente
# ---------------------------------------------------------------------------


class TestCoaccionAResistencia:
    def test_quemador_en_respaldo_se_coacciona(self):
        aux = _respaldo(tipo=TipoAuxiliar.QUEMADOR_BIOMASA, PCI_MJ_kg=16.0, eficiencia_quemador=0.7)
        assert aux.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA
        assert aux.tipo_coaccionado_a_resistencia is True

    def test_la_coaccion_se_avisa(self):
        aux = _respaldo(tipo=TipoAuxiliar.QUEMADOR_BIOMASA, PCI_MJ_kg=16.0, eficiencia_quemador=0.7)
        codigos = [a.codigo for a in advertencias_auxiliar(aux)]
        assert "AUX_RESPALDO_COACCIONADO_A_RESISTENCIA" in codigos

    def test_quemador_en_serie_queda_intacto(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=2000.0,
            PCI_MJ_kg=16.0,
            eficiencia_quemador=0.7,
        )
        assert aux.tipo == TipoAuxiliar.QUEMADOR_BIOMASA
        assert aux.tipo_coaccionado_a_resistencia is False

    def test_resistencia_en_respaldo_no_genera_ruido(self):
        """Sin cambio real no debe aparecer el aviso."""
        aux = _respaldo()
        assert aux.tipo_coaccionado_a_resistencia is False
        codigos = [a.codigo for a in advertencias_auxiliar(aux)]
        assert "AUX_RESPALDO_COACCIONADO_A_RESISTENCIA" not in codigos


# ---------------------------------------------------------------------------
# Integración con el balance global
# ---------------------------------------------------------------------------


class TestRespaldoEnElBalance:
    def test_no_precalienta_la_entrada(self):
        """La marca del respaldo: T_ent no se toca, sube T_flujo."""
        res = _corre(_respaldo())
        # Sin solver de auxiliar: no hay ΔT aguas arriba que reportar.
        assert res.auxiliar is None
        assert res.camara is not None
        assert float(np.mean(res.camara.Q_aux_W)) > 0.0

    def test_calienta_mas_que_sin_respaldo(self):
        sin = _corre(None)
        con = _corre(_respaldo())
        assert float(np.mean(con.camara.T_flujo_K)) > float(np.mean(sin.camara.T_flujo_K))
        assert con.camara.masa_evaporada_total_kg > sin.camara.masa_evaporada_total_kg

    def test_la_energia_entregada_se_contabiliza(self):
        res = _corre(_respaldo())
        assert res.camara.energia_aux_total_J > 0.0
        # El reporte toma la ENTREGADA del motor, no potencia × tiempo.
        assert res.energia_auxiliar_MJ == pytest.approx(res.camara.energia_aux_total_J / 1e6)

    def test_el_set_point_recorta_la_potencia(self):
        """Se compara potencia MEDIA, no energía total.

        La integral no es comparable entre las dos corridas: a potencia plena el
        lote termina y la integración se corta, mientras que con el set-point más
        bajo el secado no llega a X_objetivo y sigue hasta t_max. La corrida
        modulada consume **menos por hora** y sin embargo más en total, que es el
        resultado correcto y no una regresión.
        """
        pleno = _corre(_respaldo())
        T_set = float(np.mean(pleno.camara.T_flujo_K)) - 10.0
        modulado = _corre(_respaldo(set_point_T_K=T_set))
        assert float(np.mean(modulado.camara.Q_aux_W)) < float(np.mean(pleno.camara.Q_aux_W))
        assert float(np.mean(modulado.camara.T_flujo_K)) < float(np.mean(pleno.camara.T_flujo_K))

    def test_el_respaldo_refuerza_el_tiro(self):
        """Con bocas, más Q_aux ⇒ más T_flujo ⇒ más empuje ⇒ más caudal.

        Es la consecuencia nueva de que el motor de caudal exista (S61): en
        convección natural el auxiliar no solo calienta, además mueve más aire.
        """
        sin = _corre(None, A_boca=0.05)
        con = _corre(_respaldo(potencia_nominal_W=1500.0), A_boca=0.05)
        # El caudal que resuelve el equilibrio tiro↔resistencia queda en el dict
        # del lazo natural (`res.chimenea`, que también cubre el cajón desnudo).
        assert sin.chimenea is not None and con.chimenea is not None
        assert con.chimenea["m_punto_kgs"] > sin.chimenea["m_punto_kgs"]


class TestDiagnosticosDelRespaldo:
    """Los tres arreglos de S62 salidos de una corrida real del usuario."""

    def test_la_irradiancia_POA_sirve_de_referencia_dia_noche(self):
        """Con `I_g_W_m2` en cero pero POA poblada, el respaldo debe operar igual.

        Con la máscara atada solo a `I_g_W_m2`, una serie idénticamente nula la
        daba toda falsa y el auxiliar quedaba apagado **en silencio**: el reporte
        decía `E_aux = 0` mientras P5 dibujaba la potencia disponible desde otras
        forzantes. Una serie nula significa "nadie llenó este campo", no "hubo
        tres días de noche".
        """
        import numpy as np

        from calculos.balance_global import _irradiancia_para_mascara

        class _Fz:
            I_g_W_m2 = np.zeros(24)
            I_g_POA_W_m2 = np.concatenate([np.zeros(8), np.full(8, 800.0), np.zeros(8)])

        serie = _irradiancia_para_mascara(_Fz())
        assert serie is not None
        assert float(np.max(serie)) == 800.0

    def test_sin_ninguna_irradiancia_no_inventa_referencia(self):
        import numpy as np

        from calculos.balance_global import _irradiancia_para_mascara

        class _Fz:
            I_g_W_m2 = np.zeros(24)
            I_g_POA_W_m2 = np.zeros(24)

        assert _irradiancia_para_mascara(_Fz()) is None

    def test_avisa_si_el_aire_supera_la_T_maxima_del_auxiliar(self):
        """En serie lo controla `calcular_auxiliar`; en respaldo no había NADA.

        La corrida del usuario llevó el producto a 63.4 °C contra un límite
        declarado de 65 °C sin emitir una sola advertencia.
        """
        aux = _respaldo(potencia_nominal_W=4000.0, temperatura_maxima_salida_K=303.15)
        res = _corre(aux)
        assert any("AUX_RESPALDO_EXCEDE_T_MAX" in a for a in res.advertencias), res.advertencias

    def test_no_avisa_si_se_mantiene_bajo_el_limite(self):
        aux = _respaldo(potencia_nominal_W=100.0, temperatura_maxima_salida_K=363.15)
        res = _corre(aux)
        assert not any("AUX_RESPALDO_EXCEDE_T_MAX" in a for a in res.advertencias)


class TestSetPointEnElPipelineTransitorio:
    """El set-point tiene que llegar al motor TAMBIÉN por el camino transitorio.

    El techo de potencia viaja como serie en las forzantes, pero la consigna es
    un escalar y se pasa aparte. `_correr_motor_TD` no la pasaba, así que en todo
    el pipeline transitorio la resistencia corría a plena potencia ignorando el
    set-point: en la corrida real del usuario entregaba 500 W con el aire ya a
    91 °C y la consigna en 60 °C (S62). El modo Constantes sí la respetaba, de
    modo que las dos rutas daban física distinta con la misma configuración.
    """

    def _correr_transitorio(self, aux, horas: int = 24):
        import numpy as np

        from calculos.balance_global import calcular_todo_transitorio
        from calculos.psicrometria import humedad_absoluta
        from core.camara import ForzantesAire

        from .test_conveccion_natural_cajon import _proyecto

        proyecto = _proyecto(A_boca=0.05)
        proyecto.auxiliar = aux
        t = np.arange(horas, dtype=float) * 3600.0
        hora = np.arange(horas) % 24
        T_amb = np.full(horas, 293.15)
        I_g = np.where((hora >= 8) & (hora <= 18), 900.0, 0.0)
        fz = ForzantesAire(
            t_s=t,
            T_ent_K=T_amb.copy(),
            omega_ent=np.full(horas, humedad_absoluta(0.5, 293.15)),
            m_dot_aire_seco_kg_s=np.full(horas, 0.02),
            T_amb_K=T_amb,
            v_viento_ms=np.full(horas, 2.0),
            I_g_W_m2=I_g,
            I_g_POA_W_m2=I_g,
        )
        return calcular_todo_transitorio(proyecto, forzantes_base=fz)

    def test_el_set_point_recorta_la_potencia_en_transitorio(self):
        import numpy as np

        pleno = self._correr_transitorio(_respaldo(potencia_nominal_W=1500.0))
        T_pico_pleno = float(np.max(pleno.camara.T_flujo_K))
        # Consigna claramente por debajo de lo que da la potencia plena.
        T_set = T_pico_pleno - 15.0
        modulado = self._correr_transitorio(
            _respaldo(potencia_nominal_W=1500.0, set_point_T_K=T_set)
        )
        assert float(np.max(modulado.camara.Q_aux_W)) < 1500.0
        assert float(np.max(modulado.camara.T_flujo_K)) < T_pico_pleno

    def test_la_resistencia_se_apaga_cuando_el_sol_ya_supera_la_consigna(self):
        """La marca de que la consigna llegó: horas con el techo disponible y 0 W."""
        import numpy as np

        res = self._correr_transitorio(_respaldo(potencia_nominal_W=1500.0, set_point_T_K=295.15))
        Q = res.camara.Q_aux_W
        disponible = res.forzantes_aplicadas.Q_aux_max_W
        # En algún instante el auxiliar tuvo permiso de operar y aun así no entregó.
        assert float(np.max(disponible)) > 0.0
        assert float(np.min(Q)) == 0.0


class TestRespaldoEnElEncadenadoDeLotes:
    """El respaldo también tiene que contar en ventana y anual (S62).

    `armar_forzantes_ventana` solo aplicaba el auxiliar en SERIE, y las forzantes
    de ese pipeline no llevaban `Q_aux_max_W`: configurar un respaldo de 25 kW
    daba exactamente el mismo resultado que no configurar nada, en silencio.
    Afecta al ARMARIO en modo anual —el modo con el que se evalúa producción— y
    a GRAN_ESCALA-BATCH en ventana.
    """

    def _forzantes(self, horas: int, Q_aux_max_W: float):
        import numpy as np

        from calculos.psicrometria import humedad_absoluta
        from core.camara import ForzantesAire

        t = np.arange(horas, dtype=float) * 3600.0
        hora = np.arange(horas) % 24
        T_amb = np.full(horas, 293.15)
        I_g = np.where((hora >= 8) & (hora <= 18), 900.0, 0.0)
        return ForzantesAire(
            t_s=t,
            T_ent_K=T_amb.copy(),
            omega_ent=np.full(horas, humedad_absoluta(0.5, 293.15)),
            m_dot_aire_seco_kg_s=np.full(horas, 0.02),
            T_amb_K=T_amb,
            v_viento_ms=np.full(horas, 2.0),
            I_g_W_m2=I_g,
            I_g_POA_W_m2=I_g,
            Q_aux_max_W=np.full(horas, Q_aux_max_W),
        )

    def _encadenar(self, Q_aux_max_W: float, aux=None, horas: int = 120):
        from calculos.simulacion_ventana import simular_encadenado_lotes

        from .test_conveccion_natural_cajon import _proyecto

        proyecto = _proyecto(A_boca=0.05)
        proyecto.auxiliar = aux
        return simular_encadenado_lotes(
            proyecto, forzantes_base=self._forzantes(horas, Q_aux_max_W)
        )

    def test_el_respaldo_produce_mas_lotes(self):
        sin = self._encadenar(0.0)
        con = self._encadenar(1500.0, aux=_respaldo(potencia_nominal_W=1500.0))
        assert con.n_batches_completos > sin.n_batches_completos

    def test_la_energia_entregada_queda_en_el_resultado(self):
        res = self._encadenar(1500.0, aux=_respaldo(potencia_nominal_W=1500.0))
        assert res.E_auxiliar_respaldo_MJ > 0.0

    def test_el_total_es_la_suma_de_los_lotes(self):
        """Si no cuadra, la tabla mensual del anual contradice al resumen."""
        res = self._encadenar(1500.0, aux=_respaldo(potencia_nominal_W=1500.0))
        suma = sum(lote.E_auxiliar_MJ for lote in res.lotes)
        assert suma == pytest.approx(res.E_auxiliar_respaldo_MJ, rel=1e-9)

    def test_sin_auxiliar_no_aporta_nada(self):
        res = self._encadenar(0.0)
        assert res.E_auxiliar_respaldo_MJ == 0.0
        assert all(lote.E_auxiliar_MJ == 0.0 for lote in res.lotes)

    def test_el_set_point_llega_al_motor_de_cada_lote(self):
        """Con consigna baja debe entregar menos que a potencia libre."""
        libre = self._encadenar(1500.0, aux=_respaldo(potencia_nominal_W=1500.0))
        T_set = 296.15  # apenas por encima del ambiente: recorta fuerte
        modulado = self._encadenar(
            1500.0, aux=_respaldo(potencia_nominal_W=1500.0, set_point_T_K=T_set)
        )
        assert modulado.E_auxiliar_respaldo_MJ < libre.E_auxiliar_respaldo_MJ


class TestCorteDeForzantesPreservaTodo:
    """`_slice_forzantes` reconstruía el objeto campo por campo (S62).

    Dejaba afuera `Q_rad_aire_W` —la radiación que calienta el aire de una cámara
    translúcida— y `t0_utc`, así que **cada lote** del anual y de la ventana
    perdía en silencio un aporte que el modo diario sí contaba. Tercera aparición
    del mismo patrón, después de `camara_calc` y `_correr_aux_y_armar_forzantes`.
    """

    def _fz(self):
        import numpy as np
        import pandas as pd

        from core.camara import ForzantesAire

        n = 10
        return ForzantesAire(
            t_s=np.arange(n, dtype=float) * 3600.0,
            T_ent_K=np.full(n, 300.0),
            omega_ent=np.full(n, 0.01),
            m_dot_aire_seco_kg_s=np.full(n, 0.02),
            T_amb_K=np.full(n, 290.0),
            v_viento_ms=np.full(n, 2.0),
            I_g_W_m2=np.arange(n, dtype=float) * 100.0,
            Q_rad_aire_W=np.arange(n, dtype=float) * 10.0,
            Q_aux_max_W=np.full(n, 500.0),
            t0_utc=pd.Timestamp("2015-09-21 00:00", tz="UTC"),
        )

    def test_preserva_la_radiacion_al_aire(self):
        from calculos.simulacion_ventana import _slice_forzantes

        sl = _slice_forzantes(self._fz(), 3 * 3600.0)
        assert sl.Q_rad_aire_W is not None
        assert float(sl.Q_rad_aire_W[0]) == pytest.approx(30.0)

    def test_preserva_el_techo_de_potencia_del_respaldo(self):
        from calculos.simulacion_ventana import _slice_forzantes

        sl = _slice_forzantes(self._fz(), 3 * 3600.0)
        assert float(sl.Q_aux_max_W[0]) == pytest.approx(500.0)

    def test_corre_el_ancla_temporal_con_el_corte(self):
        """El lote arranca t0_s después: su t=0 no es el inicio de la ventana."""
        import pandas as pd

        from calculos.simulacion_ventana import _slice_forzantes

        sl = _slice_forzantes(self._fz(), 3 * 3600.0)
        assert sl.t0_utc == pd.Timestamp("2015-09-21 03:00", tz="UTC")

    def test_todos_los_arrays_quedan_de_la_misma_longitud(self):
        import numpy as np

        from calculos.simulacion_ventana import _slice_forzantes

        sl = _slice_forzantes(self._fz(), 3 * 3600.0)
        n = len(sl.t_s)
        for nombre in ("T_ent_K", "omega_ent", "I_g_W_m2", "Q_rad_aire_W", "Q_aux_max_W"):
            assert len(np.asarray(getattr(sl, nombre))) == n, nombre


class TestBackCompat:
    def test_sin_auxiliar_no_cambia_nada(self):
        """Un proyecto sin auxiliar debe dar idéntico a antes del respaldo."""
        res = _corre(None)
        assert res.camara is not None
        assert float(np.max(res.camara.Q_aux_W)) == 0.0
        assert res.camara.energia_aux_total_J == 0.0
