"""Tests del coeficiente convectivo interior de cámara con convección mixta (S61).

Hasta S60 la cámara usaba un único ``h_conv`` **forzado** (placa plana con
μ/Pr/k congelados a ~50 °C) para el producto *y* para el film interior de la
pared. Eso tenía dos consecuencias físicas malas a bajo caudal —el caso de todo
secador de convección natural—:

    1. ``h → 0`` cuando la velocidad del aire → 0, cuando en realidad la
       flotación sostiene la transferencia (Incropera §9.6).
    2. Con el film de pared atado a ese mismo coeficiente, ``U_total → 0``: la
       cámara aparecía perfectamente aislada justo cuando más pierde.

Estos tests fijan el comportamiento nuevo: piso natural en ambos coeficientes,
rama de placa horizontal según el signo de ΔT y film de pared independiente.
"""

from __future__ import annotations

import pytest

from calculos.camara_calc import (
    _h_conv_camara_placa_plana,
    _L_caracteristica_bandeja,
    _rayleigh,
    coef_conveccion_pared_local,
    coef_conveccion_producto_local,
)
from calculos.camara_termodinamica import resolver_estado_camara

P_ATM = 101325.0

# Cámara de referencia: 1.2 m de largo, bandejas de 0.25 m de L característica.
KW_PROD = dict(omega=0.012, P_Pa=P_ATM, L_flujo_m=1.2, L_bandeja_m=0.25)
KW_PARED = dict(
    omega=0.012,
    P_Pa=P_ATM,
    L_flujo_m=1.2,
    alto_m=1.0,
    R_cond_pared_m2K_W=0.5,
    h_w_W_m2K=12.0,
)


# ---------------------------------------------------------------------------
# Longitud característica de bandeja (Incropera Ec. 9.29)
# ---------------------------------------------------------------------------


class TestLCaracteristicaBandeja:

    def test_bandeja_cuadrada_es_lado_sobre_cuatro(self):
        """A = s², P = 4s ⇒ L = s/4. Bandeja de 1 m² en cámara cuadrada."""
        assert _L_caracteristica_bandeja(1.0, 2.0, 2.0) == pytest.approx(0.25)

    def test_hereda_la_relacion_de_aspecto_de_la_camara(self):
        """Una cámara alargada da una bandeja alargada ⇒ menor L que la cuadrada."""
        L_cuadrada = _L_caracteristica_bandeja(1.0, 2.0, 2.0)
        L_alargada = _L_caracteristica_bandeja(1.0, 8.0, 1.0)
        assert L_alargada < L_cuadrada

    def test_area_nula_sin_longitud(self):
        assert _L_caracteristica_bandeja(0.0, 2.0, 2.0) == 0.0


# ---------------------------------------------------------------------------
# Rayleigh con propiedades variables
# ---------------------------------------------------------------------------


class TestRayleigh:

    def test_crece_con_el_cubo_de_L(self):
        """Ra ∝ L³."""
        Ra_1 = _rayleigh(10.0, 0.25, 318.0, 0.012, P_ATM)
        Ra_2 = _rayleigh(10.0, 0.50, 318.0, 0.012, P_ATM)
        assert Ra_2 / Ra_1 == pytest.approx(8.0, rel=1e-6)

    def test_usa_valor_absoluto_de_delta_T(self):
        """El signo de ΔT elige la rama, no la magnitud del empuje."""
        assert _rayleigh(-10.0, 0.25, 318.0, 0.012, P_ATM) == _rayleigh(
            10.0, 0.25, 318.0, 0.012, P_ATM
        )

    def test_nulo_sin_delta_T(self):
        assert _rayleigh(0.0, 0.25, 318.0, 0.012, P_ATM) == 0.0


# ---------------------------------------------------------------------------
# h aire↔producto — mixta transversal sobre placa horizontal
# ---------------------------------------------------------------------------


class TestCoefProducto:

    def test_no_colapsa_a_caudal_nulo(self):
        """El hueco que motivó S61: sin flujo forzado queda el piso natural."""
        assert coef_conveccion_producto_local(0.0, 323.15, 313.15, **KW_PROD) > 1.0

    def test_forzado_puro_colapsaba(self):
        """Contraste explícito: el modelo viejo (solo forzado) sí caía a cero."""
        h_forzado = _h_conv_camara_placa_plana(0.0, 1.2, 318.15, 0.012, P_ATM)
        h_mixto = coef_conveccion_producto_local(0.0, 323.15, 313.15, **KW_PROD)
        assert h_forzado == pytest.approx(0.0)
        assert h_mixto > h_forzado

    def test_crece_con_velocidad(self):
        h_lento = coef_conveccion_producto_local(0.2, 323.15, 313.15, **KW_PROD)
        h_rapido = coef_conveccion_producto_local(2.0, 323.15, 313.15, **KW_PROD)
        assert h_rapido > h_lento

    def test_rama_estable_con_aire_mas_caliente(self):
        """Caso normal del secado (producto enfriado por evaporación): rama débil.

        Con el producto más caliente que el aire, mismo |ΔT|, la estratificación
        es inestable y el coeficiente tiene que ser mayor.
        """
        h_aire_caliente = coef_conveccion_producto_local(0.1, 323.15, 313.15, **KW_PROD)
        h_prod_caliente = coef_conveccion_producto_local(0.1, 313.15, 323.15, **KW_PROD)
        assert h_prod_caliente > h_aire_caliente

    def test_domina_el_forzado_a_velocidad_alta(self):
        """A 3 m/s la flotación es marginal: el mixto queda cerca del forzado."""
        h_mixto = coef_conveccion_producto_local(3.0, 323.15, 313.15, **KW_PROD)
        h_forzado = _h_conv_camara_placa_plana(3.0, 1.2, 318.15, 0.012, P_ATM)
        assert h_mixto == pytest.approx(h_forzado, rel=0.15)

    def test_orden_de_magnitud_conveccion_natural_en_aire(self):
        """Sin flujo, h natural en aire cae en 1–10 W/(m²·K)."""
        h = coef_conveccion_producto_local(0.0, 323.15, 313.15, **KW_PROD)
        assert 1.0 < h < 10.0


# ---------------------------------------------------------------------------
# h aire↔pared — mixta sobre placa vertical (film propio desde S61)
# ---------------------------------------------------------------------------


class TestCoefPared:

    def test_no_colapsa_a_caudal_nulo(self):
        """Piso de Churchill-Chu: sin él UA→0 y la cámara parecía adiabática."""
        h = coef_conveccion_pared_local(0.0, 323.15, 293.15, **KW_PARED)
        assert h > 1.0

    def test_crece_con_velocidad(self):
        h_lento = coef_conveccion_pared_local(0.1, 323.15, 293.15, **KW_PARED)
        h_rapido = coef_conveccion_pared_local(2.0, 323.15, 293.15, **KW_PARED)
        assert h_rapido > h_lento

    def test_crece_con_salto_termico(self):
        """Más ΔT con el ambiente ⇒ más empuje ⇒ más h."""
        h_frio = coef_conveccion_pared_local(0.0, 323.15, 273.15, **KW_PARED)
        h_templado = coef_conveccion_pared_local(0.0, 323.15, 318.15, **KW_PARED)
        assert h_frio > h_templado

    def test_pared_aislada_reduce_el_empuje_interior(self):
        """Más R_cond ⇒ la película interior se lleva menos ΔT ⇒ menos h natural."""
        kw = dict(KW_PARED)
        kw["R_cond_pared_m2K_W"] = 5.0
        h_aislada = coef_conveccion_pared_local(0.0, 323.15, 293.15, **kw)
        h_desnuda = coef_conveccion_pared_local(0.0, 323.15, 293.15, **KW_PARED)
        assert h_aislada < h_desnuda

    def test_orden_de_magnitud(self):
        h = coef_conveccion_pared_local(0.0, 323.15, 293.15, **KW_PARED)
        assert 1.0 < h < 10.0


# ---------------------------------------------------------------------------
# Enhebrado en el motor: h de pared separado del de producto
# ---------------------------------------------------------------------------


KW_ESTADO = dict(
    T_prod_K=313.15,
    X_prod_kg_kg=2.0,
    T_ent_K=323.15,
    omega_ent_kg_kg=0.012,
    A_prod_m2=2.5,
    A_cuerpo_m2=6.0,
    m_dot_as_kg_s=0.05,
    K_m_kg_m2s=0.005,
    h_w_W_m2K=12.0,
    k_aisl_W_mK=0.04,
    esp_cam_m=0.05,
    T_amb_K=293.15,
    P_Pa=P_ATM,
    aw_func=lambda X: min(1.0, max(0.0, X / 4.0)),
)


class TestMotorConHParedPropio:

    def test_default_none_es_back_compat(self):
        """Sin h de pared explícito, el motor reproduce exactamente el histórico."""
        est_sin = resolver_estado_camara(h_conv_W_m2K=8.0, **KW_ESTADO)
        est_igual = resolver_estado_camara(h_conv_W_m2K=8.0, h_conv_pared_W_m2K=8.0, **KW_ESTADO)
        assert est_sin.T_flujo_K == pytest.approx(est_igual.T_flujo_K)
        assert est_sin.U_pared_W_m2K == pytest.approx(est_igual.U_pared_W_m2K)

    def test_h_pared_gobierna_U_total(self):
        """U_pared responde al film de pared, no al del producto."""
        est_bajo = resolver_estado_camara(h_conv_W_m2K=8.0, h_conv_pared_W_m2K=2.0, **KW_ESTADO)
        est_alto = resolver_estado_camara(h_conv_W_m2K=8.0, h_conv_pared_W_m2K=20.0, **KW_ESTADO)
        assert est_alto.U_pared_W_m2K > est_bajo.U_pared_W_m2K

    def test_producto_y_pared_desacoplados(self):
        """Cambiar el h del producto no mueve U_pared si el de pared se mantiene."""
        est_a = resolver_estado_camara(h_conv_W_m2K=4.0, h_conv_pared_W_m2K=3.0, **KW_ESTADO)
        est_b = resolver_estado_camara(h_conv_W_m2K=25.0, h_conv_pared_W_m2K=3.0, **KW_ESTADO)
        assert est_a.U_pared_W_m2K == pytest.approx(est_b.U_pared_W_m2K)

    def test_camara_no_queda_adiabatica_con_h_producto_nulo(self):
        """El caso que rompía: h_producto→0 pero la pared sigue perdiendo."""
        est = resolver_estado_camara(h_conv_W_m2K=0.0, h_conv_pared_W_m2K=3.0, **KW_ESTADO)
        assert est.U_pared_W_m2K > 0.0
        assert est.q_pared_W > 0.0

    def test_CAM_TD_H_CONV_PARED_NEGATIVO(self):
        with pytest.raises(ValueError, match="CAM_TD_H_CONV_PARED_NEGATIVO"):
            resolver_estado_camara(h_conv_W_m2K=8.0, h_conv_pared_W_m2K=-1.0, **KW_ESTADO)


class TestFilmDeParedGobernadoPorElAireInterior:
    """El film de pared lo mueve el aire DE ADENTRO, no el que entra (S62).

    El wire-up le pasaba ``T_ent`` a la correlación. En tipología CAJA el aire
    entra a la temperatura ambiente, así que ``ΔT = T_ent − T_amb = 0``
    idénticamente: el Rayleigh se anulaba, la convección natural desaparecía y
    sobrevivía solo el término forzado a ~0.01 m/s. Resultado, ``h ≈ 0.5``
    en vez de ~2.4 (pared) / 3.7 (vidriado), y una envolvente **8× más aislante
    de lo real** — con lo cual una resistencia chica sostenía cualquier consigna.
    Lo detectó el usuario corriendo una caja con resistencia.
    """

    #: Condiciones de una caja al mediodía: el aire ENTRA a la ambiente (25 °C)
    #: pero adentro está a 65 °C por el efecto invernadero.
    T_AIRE_INTERIOR_K = 338.15
    T_AMB_K = 298.15
    V_AIRE_MS = 0.01  # convección natural: velocidad superficial ínfima

    def _h(self, T_aire_K: float, R_cond: float = 1.25) -> float:
        return coef_conveccion_pared_local(
            self.V_AIRE_MS, T_aire_K, self.T_AMB_K, 0.01, 89250.0, 0.5, 1.0, R_cond, 17.0
        )

    def test_con_delta_T_nulo_el_film_colapsa(self):
        """Documenta el modo de falla: si se evalúa con T_ent = T_amb, se hunde."""
        h_colapsado = self._h(self.T_AMB_K)
        assert h_colapsado < 1.0

    def test_con_el_aire_interior_el_film_es_fisico(self):
        """Con el ΔT real, una placa vertical de 1 m debe dar del orden de 2-4."""
        h = self._h(self.T_AIRE_INTERIOR_K)
        assert 1.5 < h < 6.0, h
        assert h > 3.0 * self._h(self.T_AMB_K)

    def test_el_vidriado_queda_en_el_orden_de_la_ficha_tecnica(self):
        """Policarbonato 6 mm: U ≈ 3.8 con films ISO; con convección pura, ~2.3.

        Con el film colapsado daba 0.47 — un orden de magnitud de más de
        aislación, que es lo que volvía inocuo el tamaño de la resistencia.
        """
        R_cond_vidriado = 0.006 / 0.06
        h = self._h(self.T_AIRE_INTERIOR_K, R_cond=R_cond_vidriado)
        U = 1.0 / (1.0 / h + R_cond_vidriado + 1.0 / 17.0)
        assert U > 1.5, U

    def test_el_motor_no_deja_el_film_clavado_en_el_valor_forzado(self):
        """End-to-end: con T_ent = T_amb el motor debe recalcularlo, no congelarlo.

        Se mira ``U_pared``, que depende del film de pared: si el motor evaluara
        el film con la T de entrada, sería el mismo con la cámara fría que con la
        cámara caliente.
        """
        import numpy as np

        from calculos.camara_calc import calcular_camara
        from core.camara import ForzantesAire

        from .test_conveccion_natural_cajon import _camara

        camara = _camara(A_boca=0.05)
        n = 12
        t = np.arange(n, dtype=float) * 3600.0
        T_amb = np.full(n, self.T_AMB_K)
        fz = ForzantesAire(
            t_s=t,
            T_ent_K=T_amb.copy(),  # CAJA: entra el ambiente
            omega_ent=np.full(n, 0.008),
            m_dot_aire_seco_kg_s=np.full(n, 0.005),
            T_amb_K=T_amb,
            v_viento_ms=np.full(n, 2.0),
            Q_aux_max_W=np.full(n, 2000.0),  # calienta la cámara muy por encima
        )
        res = calcular_camara(
            camara=camara,
            T_operacion_K=self.T_AMB_K,
            HR_operacion=0.3,
            T_amb_K=self.T_AMB_K,
            P_Pa=89250.0,
            forzantes_aire=fz,
            t_max_s=float(t[-1]),
        )
        # La cámara se calentó bastante por encima del ambiente...
        assert float(np.max(res.T_flujo_K)) > self.T_AMB_K + 15.0
        # ...y la envolvente NO quedó con el U degenerado del film colapsado.
        assert float(np.max(res.U_pared_W_m2K)) > 0.40, float(np.max(res.U_pared_W_m2K))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
