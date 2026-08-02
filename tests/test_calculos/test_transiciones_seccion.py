"""Pérdida de carga en los cambios de sección del circuito de aire (S62).

Los empalmes colector→boca de entrada y boca de salida→chimenea disipan energía
cuando las áreas no coinciden, y hasta S62 el modelo no lo representaba: las
bocas usaban coeficientes fijos de manual, evaluados sobre su propia velocidad,
sin mirar qué había del otro lado.

Los tests anclan el módulo contra los resultados **analíticos y tabulados** de la
literatura, que es lo único que puede hacer de árbitro mientras no haya
mediciones propias.
"""

from __future__ import annotations

import math

import pytest

from calculos.transiciones_seccion import (
    angulo_transicion_deg,
    coeficiente_transicion,
    delta_P_transicion_Pa,
    radio_equivalente_m,
)


class TestExpansionBrusca:
    """Borda-Carnot es **exacta**: sale del balance de cantidad de movimiento."""

    @pytest.mark.parametrize("razon", [0.1, 0.25, 0.5, 0.75, 0.9])
    def test_reproduce_borda_carnot(self, razon):
        K = coeficiente_transicion(area_origen_m2=razon, area_destino_m2=1.0)
        assert K == pytest.approx((1.0 - razon) ** 2, rel=1e-12)

    def test_descarga_a_un_recinto_infinito_disipa_toda_la_altura(self):
        """A₂ → ∞ el coeficiente tiende a 1: se pierde toda la energía cinética."""
        K = coeficiente_transicion(area_origen_m2=0.01, area_destino_m2=1e6)
        assert K == pytest.approx(1.0, abs=1e-4)


class TestContraccionBrusca:
    @pytest.mark.parametrize("razon", [0.25, 0.5, 0.75])
    def test_reproduce_idelchik(self, razon):
        K = coeficiente_transicion(area_origen_m2=1.0, area_destino_m2=razon)
        assert K == pytest.approx(0.5 * (1.0 - razon) ** 0.75, rel=1e-12)

    def test_pierde_menos_que_la_expansion_equivalente(self):
        """Contraer es barato; ensanchar es caro. Es el hecho físico central."""
        K_contrae = coeficiente_transicion(1.0, 0.25)
        K_expande = coeficiente_transicion(0.25, 1.0)
        assert K_contrae < K_expande


class TestTransicionGradual:
    def _longitud_para_angulo(self, A1: float, A2: float, theta_deg: float) -> float:
        r1, r2 = radio_equivalente_m(A1), radio_equivalente_m(A2)
        return abs(r2 - r1) / math.tan(math.radians(theta_deg / 2.0))

    @pytest.mark.parametrize("theta,k_tabla", [(10.0, 0.17), (20.0, 0.43), (40.0, 0.87)])
    def test_el_difusor_sigue_la_tabla_de_gibson(self, theta, k_tabla):
        """El coeficiente del difusor cónico contra los valores publicados.

        Se admite holgura: la correlación ``2.61·sin(θ/2)`` es un ajuste de la
        tabla, y del lado conservador en ángulos chicos.
        """
        A1, A2 = 0.5, 1.0
        L = self._longitud_para_angulo(A1, A2, theta)
        K = coeficiente_transicion(A1, A2, L)
        k_efectivo = K / (1.0 - A1 / A2) ** 2
        assert k_efectivo == pytest.approx(k_tabla, abs=0.07), (theta, k_efectivo)

    def test_alargar_la_transicion_nunca_aumenta_la_perdida(self):
        anterior = None
        for L in (0.0, 0.1, 0.3, 0.6, 1.0, 2.0):
            dp = delta_P_transicion_Pa(0.05, 0.02, 0.10, 1.1, L)
            if anterior is not None:
                assert dp <= anterior + 1e-12, L
            anterior = dp

    def test_por_encima_de_45_grados_se_comporta_como_escalon(self):
        """Un difusor muy abierto desprende y deja de recuperar presión.

        Lo captura la cota ``k ≤ 1``, no una rama aparte del código.
        """
        A1, A2 = 0.02, 0.10
        L_corta = self._longitud_para_angulo(A1, A2, 60.0)
        assert coeficiente_transicion(A1, A2, L_corta) == pytest.approx(
            coeficiente_transicion(A1, A2, 0.0)
        )

    def test_una_transicion_larga_recupera_presion(self):
        A1, A2 = 0.02, 0.10
        L_larga = self._longitud_para_angulo(A1, A2, 10.0)
        assert coeficiente_transicion(A1, A2, L_larga) < 0.4 * coeficiente_transicion(A1, A2, 0.0)


class TestAngulo:
    def test_sin_longitud_es_brusca(self):
        assert angulo_transicion_deg(0.02, 0.10, 0.0) == 180.0

    def test_crece_al_acortar_la_transicion(self):
        a_corta = angulo_transicion_deg(0.02, 0.10, 0.1)
        a_larga = angulo_transicion_deg(0.02, 0.10, 1.0)
        assert a_corta > a_larga

    def test_simetrico_en_el_sentido(self):
        """El ángulo del tronco de cono no depende de por dónde se lo recorra."""
        assert angulo_transicion_deg(0.02, 0.10, 0.5) == pytest.approx(
            angulo_transicion_deg(0.10, 0.02, 0.5)
        )


class TestCasosDegenerados:
    def test_secciones_iguales_no_pierden(self):
        assert coeficiente_transicion(0.05, 0.05) == 0.0
        assert delta_P_transicion_Pa(0.05, 0.05, 0.05, 1.1) == 0.0

    @pytest.mark.parametrize("A1,A2", [(0.0, 0.05), (0.05, 0.0), (-1.0, 0.05)])
    def test_areas_no_positivas_devuelven_cero(self, A1, A2):
        assert coeficiente_transicion(A1, A2) == 0.0
        assert delta_P_transicion_Pa(0.05, A1, A2, 1.1) == 0.0

    def test_sin_caudal_no_hay_perdida(self):
        assert delta_P_transicion_Pa(0.0, 0.02, 0.10, 1.1) == 0.0

    def test_la_perdida_es_siempre_no_negativa(self):
        for A1, A2 in ((0.02, 0.10), (0.10, 0.02), (0.05, 0.05)):
            assert delta_P_transicion_Pa(0.03, A1, A2, 1.1) >= 0.0


class TestReferenciaALaVelocidadMenor:
    """La convención importa: referir a la sección mayor daría otra pérdida."""

    def test_usa_el_area_menor_en_los_dos_sentidos(self):
        A_chica, A_grande, m_dot, rho = 0.02, 0.10, 0.05, 1.1
        v_menor = m_dot / (rho * A_chica)
        for origen, destino in ((A_chica, A_grande), (A_grande, A_chica)):
            K = coeficiente_transicion(origen, destino)
            esperado = K * 0.5 * rho * v_menor**2
            assert delta_P_transicion_Pa(m_dot, origen, destino, rho) == pytest.approx(esperado)
