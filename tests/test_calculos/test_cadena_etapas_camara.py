"""El aire de la cámara como cadena de sub-etapas en serie (S63, etapa 4).

El motor trataba a la cámara como un CSTR: un nodo de aire perfectamente
mezclado. Pero un CSTR **no puede saturar por construcción** —su acercamiento al
equilibrio es ``NTU/(1+NTU)``— y el aire de un secador recorre un camino
humedeciéndose, que es flujo pistón: ``1 − exp(−NTU)``.

A NTU = 2 la diferencia es 67 % contra 86 %.
"""

from __future__ import annotations

import math

import pytest

from calculos.camara_termodinamica import (
    _omega_saturacion_acotada,
    resolver_cadena_camara,
    resolver_estado_camara,
)

_P = 89202.0
_A_W = 0.98  # actividad de agua del producto, fija para aislar la topología

_BASE = dict(
    T_prod_K=295.0,
    X_prod_kg_kg=2.0,
    T_ent_K=325.0,
    omega_ent_kg_kg=0.006,
    A_cuerpo_m2=2.7,
    m_dot_as_kg_s=0.0342,
    h_w_W_m2K=13.3,
    k_aisl_W_mK=0.04,
    esp_cam_m=0.05,
    T_amb_K=290.0,
    P_Pa=_P,
    aw_func=lambda X: _A_W,
)


def _acercamiento(n_etapas: int, NTU: float) -> float:
    """Fracción del camino al equilibrio que recorre el aire."""
    K_m = 0.02
    A = NTU * _BASE["m_dot_as_kg_s"] / K_m
    est = resolver_cadena_camara(
        n_etapas=n_etapas,
        A_prod_m2=A,
        h_conv_W_m2K=K_m * 1010.0,
        K_m_kg_m2s=K_m,
        **_BASE,
    )
    w_sup = _omega_saturacion_acotada(_BASE["T_prod_K"], _P) * _A_W
    w_ent = _BASE["omega_ent_kg_kg"]
    return (est.omega_flujo_kg_kg - w_ent) / (w_sup - w_ent)


class TestConvergenciaAFlujoPiston:

    @pytest.mark.parametrize("NTU", [0.2, 1.0, 2.0, 5.0])
    def test_una_etapa_es_exactamente_el_cstr(self, NTU):
        """N = 1 reproduce NTU/(1+NTU): la back-compat es literal, no aproximada."""
        assert _acercamiento(1, NTU) == pytest.approx(NTU / (1.0 + NTU), rel=1e-6)

    @pytest.mark.parametrize("NTU", [0.2, 1.0, 2.0, 5.0])
    def test_muchas_etapas_convergen_al_piston(self, NTU):
        """N grande tiende a 1 − exp(−NTU)."""
        assert _acercamiento(256, NTU) == pytest.approx(1.0 - math.exp(-NTU), rel=0.01)

    @pytest.mark.parametrize("NTU", [0.2, 1.0, 2.0, 5.0])
    def test_es_monotona_en_n(self, NTU):
        """Más etapas, más cerca del equilibrio: nunca al revés."""
        vals = [_acercamiento(n, NTU) for n in (1, 2, 4, 8, 32, 128)]
        assert vals == sorted(vals)

    def test_el_cstr_subestima_donde_importa(self):
        """A NTU ≈ 2 —secador mal cargado— el CSTR se queda 20 puntos corto."""
        cstr = _acercamiento(1, 2.0)
        piston = _acercamiento(256, 2.0)
        assert cstr == pytest.approx(0.667, abs=0.01)
        assert piston == pytest.approx(0.865, abs=0.01)

    def test_en_los_extremos_casi_no_cambia(self):
        """A NTU muy bajo o muy alto, CSTR y pistón dicen casi lo mismo."""
        for NTU, tol in ((0.2, 0.02), (32.0, 0.04)):
            assert _acercamiento(1, NTU) == pytest.approx(_acercamiento(256, NTU), abs=tol)


class TestAgregacionDeLaCadena:
    """El estado devuelto es el aire de SALIDA con los flujos SUMADOS."""

    def _est(self, n):
        return resolver_cadena_camara(
            n_etapas=n, A_prod_m2=45.8, h_conv_W_m2K=24.7, K_m_kg_m2s=0.0244, **_BASE
        )

    def test_una_etapa_es_identica_al_solve_directo(self):
        directo = resolver_estado_camara(
            A_prod_m2=45.8, h_conv_W_m2K=24.7, K_m_kg_m2s=0.0244, **_BASE
        )
        cadena = self._est(1)
        assert cadena == directo

    def test_conserva_el_balance_de_masa(self):
        """ṁ_w total = ṁ_as·(ω_salida − ω_entrada), sumado sobre las etapas."""
        est = self._est(10)
        esperado = _BASE["m_dot_as_kg_s"] * (est.omega_flujo_kg_kg - _BASE["omega_ent_kg_kg"])
        assert est.m_dot_w_kg_s == pytest.approx(esperado, rel=1e-9)

    def test_la_perdida_de_pared_usa_el_perfil_de_aire(self):
        """Cada tramo pierde con SU temperatura, no con una sola.

        Como el aire se enfría a lo largo del camino, la pérdida total con
        perfil es menor que la que daría el CSTR a la temperatura de entrada.
        """
        una = self._est(1)
        diez = self._est(10)
        assert diez.q_pared_W != pytest.approx(una.q_pared_W, rel=1e-6)
        assert 0.0 < diez.q_pared_W < 2.0 * una.q_pared_W

    def test_n_menor_a_uno_se_trata_como_uno(self):
        assert self._est(0) == self._est(1)
        assert self._est(-5) == self._est(1)


class TestSetPointConCadena:
    """La consigna gobierna UNA potencia sobre el aire, no una por etapa.

    Regresión S63: al partir la cámara en etapas, dejar que cada una modulara su
    propia potencia daba un controlador por tramo. El primero, que ve el aire
    frío de **entrada**, encendía siempre —aunque el sol ya hubiera superado la
    consigna aguas abajo— y la resistencia no se apagaba nunca.
    """

    def _est(self, *, Q_max, T_set, Q_rad_aire=0.0, n=8):
        return resolver_cadena_camara(
            n_etapas=n,
            A_prod_m2=10.0,
            h_conv_W_m2K=20.0,
            K_m_kg_m2s=0.02,
            Q_rad_aire_W=Q_rad_aire,
            Q_aux_max_W=Q_max,
            T_set_aux_K=T_set,
            **_BASE,
        )

    def test_no_enciende_si_el_aire_ya_supera_la_consigna(self):
        """Consigna por debajo de lo que da el sol solo ⇒ 0 W, con N > 1."""
        sin_aux = self._est(Q_max=0.0, T_set=None, Q_rad_aire=1500.0)
        est = self._est(Q_max=1500.0, T_set=sin_aux.T_flujo_K - 5.0, Q_rad_aire=1500.0)
        assert est.Q_aux_W == 0.0
        assert est.T_flujo_K == pytest.approx(sin_aux.T_flujo_K, rel=1e-9)

    def test_alcanza_la_consigna_exactamente(self):
        """La inversión afín es exacta: la salida cae sobre la consigna."""
        sin_aux = self._est(Q_max=0.0, T_set=None)
        T_set = sin_aux.T_flujo_K + 4.0
        est = self._est(Q_max=5000.0, T_set=T_set)
        assert 0.0 < est.Q_aux_W < 5000.0
        assert est.T_flujo_K == pytest.approx(T_set, abs=1e-6)

    def test_satura_en_el_techo_si_no_alcanza(self):
        """Equipo subdimensionado: entrega todo y no llega."""
        est = self._est(Q_max=50.0, T_set=400.0)
        assert est.Q_aux_W == pytest.approx(50.0)
        assert est.T_flujo_K < 400.0

    def test_una_etapa_da_lo_mismo_que_el_despeje_de_siempre(self):
        """Back-compat: con N = 1 la cadena y el solve único coinciden."""
        comun = dict(
            A_prod_m2=10.0,
            h_conv_W_m2K=20.0,
            K_m_kg_m2s=0.02,
            Q_aux_max_W=800.0,
            T_set_aux_K=310.0,
            **_BASE,
        )
        directo = resolver_estado_camara(**comun)
        cadena = resolver_cadena_camara(n_etapas=1, **comun)
        assert cadena.Q_aux_W == pytest.approx(directo.Q_aux_W, rel=1e-9)
        assert cadena.T_flujo_K == pytest.approx(directo.T_flujo_K, rel=1e-12)


class TestTopologiaDefineLasEtapas:
    """Vertical: bandejas en serie. Horizontal: canales en paralelo."""

    def _camara(self, direccion, n_bandejas=10):
        from core.camara import (
            Camara,
            CargaProducto,
            ConfiguracionBandejas,
            ConfiguracionFlujo,
            ConstruccionCamara,
            GeometriaCamara,
        )

        return Camara(
            geometria=GeometriaCamara(largo_m=0.5, ancho_m=0.5, alto_m=1.1),
            bandejas=ConfiguracionBandejas(
                n_bandejas=n_bandejas,
                area_bandeja_m2=0.25,
                espesor_capa_m=0.02,
                separacion_entre_bandejas_m=0.07,
            ),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.0342, direccion_flujo=direccion),
            construccion=ConstruccionCamara(),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=9.5,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
            ),
        )

    def _n_etapas(self, cam):
        from calculos.camara_calc import _construir_params_termodinamico

        return _construir_params_termodinamico(
            cam, T_operacion_K=325.0, HR_operacion=0.06, T_amb_K=290.0, P_Pa=_P
        ).n_etapas_aire

    def test_una_camara_migrada_usa_las_etapas_de_cross_flow(self):
        """Un snapshot con flujo vertical se coacciona y comparte el N (S64)."""
        from core.camara import DireccionFlujo

        migrada = self._n_etapas(self._camara(DireccionFlujo.VERTICAL_ASCENDENTE, 10))
        nativa = self._n_etapas(self._camara(DireccionFlujo.HORIZONTAL, 10))
        assert migrada == nativa

    def test_horizontal_no_escala_con_las_bandejas(self):
        """Los canales van en PARALELO: cada uno recibe aire de entrada.

        Sumar una bandeja agrega un canal más, no una etapa más en serie. Lo que
        se discretiza es el largo del canal, que es continuo.
        """
        from core.camara import DireccionFlujo

        n4 = self._n_etapas(self._camara(DireccionFlujo.HORIZONTAL, 4))
        n10 = self._n_etapas(self._camara(DireccionFlujo.HORIZONTAL, 10))
        assert n4 == n10 > 1
