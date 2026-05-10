"""Tests del solver algebraico de cámara (calculos/camara_termodinamica.py)."""

from __future__ import annotations

import math

import pytest

from calculos.camara_termodinamica import (
    EstadoCamara,
    resolver_estado_camara,
)
from calculos.psicrometria import (
    _CP_VAPOR,
    _LV_0,
    _T_REF,
    entalpia_aire_humedo,
    humedad_absoluta,
    omega_saturacion,
)


# ---------------------------------------------------------------------------
# Helper: kwargs base para un secador armario tipo (10 kg de fruta)
# ---------------------------------------------------------------------------


def _kwargs_base(**overrides):
    """Retorna kwargs nominales reproducibles, con overrides."""
    base = dict(
        T_prod_K=313.15,                                    # 40 °C
        X_prod_kg_kg=2.0,
        T_ent_K=323.15,                                     # 50 °C aire del colector
        omega_ent_kg_kg=humedad_absoluta(0.20, 323.15),     # HR=20 %
        A_prod_m2=2.5,                                      # 5 bandejas × 0.5 m²
        A_cuerpo_m2=8.0,                                    # paredes
        m_dot_as_kg_s=0.030,
        h_conv_W_m2K=15.0,                                  # convección forzada
        K_m_kg_m2s=0.015,
        U_muros_W_m2K=0.5,                                  # ConstruccionCamara default
        T_amb_K=298.15,                                     # 25 °C
        P_Pa=101325.0,
        aw_func=lambda X: 0.85,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests básicos: estructura del resultado y signos esperados
# ---------------------------------------------------------------------------


class TestEstadoCamaraBasico:

    def test_retorna_estado_con_campos_finitos(self):
        est = resolver_estado_camara(**_kwargs_base())
        assert isinstance(est, EstadoCamara)
        assert math.isfinite(est.T_flujo_K)
        assert math.isfinite(est.omega_flujo_kg_kg)
        assert math.isfinite(est.m_dot_w_kg_s)
        assert math.isfinite(est.q_prod_W)
        assert math.isfinite(est.q_pared_W)

    def test_T_flujo_entre_T_amb_y_T_ent(self):
        """Sin fuente interna, T_flujo cae en el bracket (T_amb, T_ent)."""
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        assert kw["T_amb_K"] < est.T_flujo_K < kw["T_ent_K"]

    def test_omega_flujo_mayor_que_omega_ent_en_evaporacion(self):
        """Producto húmedo (a_w alto) → evaporación → ω_flujo > ω_ent."""
        kw = _kwargs_base(aw_func=lambda X: 0.95)
        est = resolver_estado_camara(**kw)
        assert est.omega_flujo_kg_kg > kw["omega_ent_kg_kg"]
        assert est.m_dot_w_kg_s > 0

    def test_signos_q_prod_q_pared(self):
        """T_flujo > T_prod y > T_amb → q_prod > 0 y q_pared > 0."""
        est = resolver_estado_camara(**_kwargs_base())
        assert est.q_prod_W > 0
        assert est.q_pared_W > 0


# ---------------------------------------------------------------------------
# Casos límite físicos
# ---------------------------------------------------------------------------


class TestCasosLimite:

    def test_K_m_cero_no_hay_evaporacion(self):
        """K_m = 0 → ω_flujo = ω_ent y ṁ_w = 0."""
        kw = _kwargs_base(K_m_kg_m2s=0.0)
        est = resolver_estado_camara(**kw)
        assert est.omega_flujo_kg_kg == pytest.approx(
            kw["omega_ent_kg_kg"], rel=1e-12
        )
        assert est.m_dot_w_kg_s == pytest.approx(0.0, abs=1e-12)

    def test_aw_cero_aire_pierde_humedad_al_producto(self):
        """a_w = 0 (producto extremadamente seco) → puede haber condensación."""
        kw = _kwargs_base(aw_func=lambda X: 0.0)
        est = resolver_estado_camara(**kw)
        assert est.omega_flujo_kg_kg < kw["omega_ent_kg_kg"]
        assert est.m_dot_w_kg_s < 0  # condensación neta sobre el producto

    def test_equilibrio_masico_aire_saturado_a_producto(self):
        """Si ω_ent = ω_sup, no hay potencial → ω_flujo = ω_ent."""
        T_prod = 313.15
        omega_sup = omega_saturacion(T_prod) * 0.85
        est = resolver_estado_camara(
            **_kwargs_base(
                T_prod_K=T_prod,
                omega_ent_kg_kg=omega_sup,
                aw_func=lambda X: 0.85,
            )
        )
        assert est.omega_flujo_kg_kg == pytest.approx(omega_sup, rel=1e-9)
        assert abs(est.m_dot_w_kg_s) < 1e-12

    def test_caudal_alto_aire_pasa_sin_perturbarse(self):
        """ṁ_as → ∞ → T_flujo → T_ent y ω_flujo → ω_ent."""
        kw = _kwargs_base(m_dot_as_kg_s=1000.0)
        est = resolver_estado_camara(**kw)
        assert est.T_flujo_K == pytest.approx(kw["T_ent_K"], abs=0.5)
        assert est.omega_flujo_kg_kg == pytest.approx(
            kw["omega_ent_kg_kg"], rel=1e-3
        )

    def test_U_muros_cero_pared_aislante_perfecta(self):
        """U_muros = 0 → q_pared = 0 sin importar T."""
        est = resolver_estado_camara(**_kwargs_base(U_muros_W_m2K=0.0))
        assert est.q_pared_W == pytest.approx(0.0, abs=1e-12)

    def test_T_ent_igual_T_prod_sin_evap_sin_perdidas(self):
        """T_ent = T_prod = T_amb, K_m=0, U=0 → T_flujo = T_ent (no hay drivers)."""
        T = 318.15
        est = resolver_estado_camara(
            **_kwargs_base(
                T_prod_K=T,
                T_ent_K=T,
                T_amb_K=T,
                K_m_kg_m2s=0.0,
                U_muros_W_m2K=0.0,
            )
        )
        assert est.T_flujo_K == pytest.approx(T, abs=1e-9)

    def test_T_prod_mayor_que_T_ent_aire_se_calienta(self):
        """Si el producto está más caliente que el aire entrante, T_flujo > T_ent."""
        kw = _kwargs_base(T_prod_K=343.15, T_ent_K=303.15, U_muros_W_m2K=0.0)
        est = resolver_estado_camara(**kw)
        assert est.T_flujo_K > kw["T_ent_K"]
        assert est.q_prod_W < 0  # el aire recibe calor del producto


# ---------------------------------------------------------------------------
# Verificación numérica del balance (ecuaciones (a) y (b))
# ---------------------------------------------------------------------------


class TestBalancesCierran:
    """La solución analítica debe cerrar exactamente las ecuaciones (a) y (b)."""

    def test_balance_masa_residuo_cero(self):
        """ṁ_as·(ω_flujo − ω_ent) = K_m·A_prod·(ω_sup − ω_flujo)."""
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        omega_sup = omega_saturacion(kw["T_prod_K"], kw["P_Pa"]) * kw["aw_func"](
            kw["X_prod_kg_kg"]
        )
        LHS = kw["m_dot_as_kg_s"] * (est.omega_flujo_kg_kg - kw["omega_ent_kg_kg"])
        RHS = kw["K_m_kg_m2s"] * kw["A_prod_m2"] * (
            omega_sup - est.omega_flujo_kg_kg
        )
        assert LHS == pytest.approx(RHS, rel=1e-9, abs=1e-15)

    def test_balance_energia_residuo_cero(self):
        """LHS − RHS de la ecuación (b) debe ser ≈ 0 (analítico exacto)."""
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        h_ent = entalpia_aire_humedo(kw["T_ent_K"], kw["omega_ent_kg_kg"])
        h_sal = entalpia_aire_humedo(est.T_flujo_K, est.omega_flujo_kg_kg)
        h_v_prod = _LV_0 + _CP_VAPOR * (kw["T_prod_K"] - _T_REF)
        LHS = kw["m_dot_as_kg_s"] * (h_sal - h_ent)
        RHS = (
            -kw["U_muros_W_m2K"] * kw["A_cuerpo_m2"]
            * (est.T_flujo_K - kw["T_amb_K"])
            - kw["h_conv_W_m2K"] * kw["A_prod_m2"]
            * (est.T_flujo_K - kw["T_prod_K"])
            + est.m_dot_w_kg_s * h_v_prod
        )
        # Tolerancia: < 1e-6 W de residuo (precisión doble flotante).
        assert abs(LHS - RHS) < 1e-6


# ---------------------------------------------------------------------------
# Validación de entradas (errores duros)
# ---------------------------------------------------------------------------


class TestValidacionEntradas:

    def test_m_dot_as_no_positivo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_M_DOT_NO_POSITIVO"):
            resolver_estado_camara(**_kwargs_base(m_dot_as_kg_s=0.0))

    def test_A_prod_negativa_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_A_PROD_NEGATIVA"):
            resolver_estado_camara(**_kwargs_base(A_prod_m2=-1.0))

    def test_A_cuerpo_negativa_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_A_CUERPO_NEGATIVA"):
            resolver_estado_camara(**_kwargs_base(A_cuerpo_m2=-1.0))

    def test_h_conv_negativo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_H_CONV_NEGATIVO"):
            resolver_estado_camara(**_kwargs_base(h_conv_W_m2K=-1.0))

    def test_K_m_negativo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_KM_NEGATIVO"):
            resolver_estado_camara(**_kwargs_base(K_m_kg_m2s=-0.001))

    def test_U_muros_negativo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_U_MUROS_NEGATIVO"):
            resolver_estado_camara(**_kwargs_base(U_muros_W_m2K=-0.1))

    def test_P_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_P_NO_POSITIVA"):
            resolver_estado_camara(**_kwargs_base(P_Pa=0.0))

    def test_aw_excede_uno_se_clipea_sin_lanzar(self):
        """aw_func ruidoso devolviendo > 1 no debe romper (clipeo interno)."""
        est = resolver_estado_camara(**_kwargs_base(aw_func=lambda X: 1.5))
        assert math.isfinite(est.T_flujo_K)
        # Equivale a a_w = 1 → ω_sup = ω_sat(T_prod) → debería evaporar
        assert est.m_dot_w_kg_s > 0


# ===========================================================================
# Tests del motor termodinámico transitorio (S3) — simular_secado
# ===========================================================================


import numpy as np

from calculos.camara_termodinamica import (
    ResultadoMotorTermodinamico,
    simular_secado,
)
from calculos.psicrometria import temperatura_bulbo_humedo


def _kwargs_motor(**overrides):
    """Kwargs nominales para el motor: secador armario con 10 kg de fruta."""
    base = dict(
        T_prod_inicial_K=298.15,                            # 25 °C
        X_prod_inicial_kg_kg=2.0,                           # producto bastante húmedo
        X_prod_objetivo_kg_kg=0.30,
        m_seco_prod_kg=3.0,                                 # 10 kg fruta ≈ 3 kg seco
        cp_prod_J_kgK=3700.0,                               # frutas
        T_ent_K=323.15,                                     # 50 °C aire del colector
        omega_ent_kg_kg=humedad_absoluta(0.20, 323.15),
        A_prod_m2=2.5,
        A_cuerpo_m2=8.0,
        m_dot_as_kg_s=0.030,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        U_muros_W_m2K=0.5,
        T_amb_K=298.15,
        P_Pa=101325.0,
        aw_func=lambda X: min(1.0, max(0.0, X / 0.5)),      # rampa: aw=1 si X≥0.5
        t_max_s=24 * 3600.0,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests básicos: estructura y comportamiento esperado
# ---------------------------------------------------------------------------


class TestMotorBasico:

    def test_smoke_secado_completa(self):
        res = simular_secado(**_kwargs_motor())
        assert isinstance(res, ResultadoMotorTermodinamico)
        assert res.status == "X_obj_alcanzado"
        assert res.t_secado_s is not None
        assert res.t_secado_s > 0
        n = len(res.t_array_s)
        assert n > 1
        # Todas las series tienen el mismo tamaño
        for arr in (
            res.T_prod_K, res.X_prod_kg_kg, res.T_flujo_K,
            res.omega_flujo_kg_kg, res.m_dot_w_kg_s,
            res.q_prod_W, res.q_pared_W,
        ):
            assert arr.shape == (n,)

    def test_X_decrece_monotonamente(self):
        res = simular_secado(**_kwargs_motor())
        diffs = np.diff(res.X_prod_kg_kg)
        # Permite ruido numérico mínimo (< 1e-6 increase) pero la tendencia es decrecer.
        assert np.all(diffs <= 1e-6)
        # Y al final X ≈ X_obj
        assert res.X_prod_kg_kg[-1] == pytest.approx(
            _kwargs_motor()["X_prod_objetivo_kg_kg"], abs=1e-3
        )

    def test_T_prod_acotada_entre_T_inicial_y_T_ent(self):
        """T_prod debe permanecer en (T_inicial, T_ent) — el aire calienta al producto."""
        kw = _kwargs_motor()
        res = simular_secado(**kw)
        assert np.all(res.T_prod_K >= kw["T_prod_inicial_K"] - 1.0)
        assert np.all(res.T_prod_K <= kw["T_ent_K"] + 1.0)

    def test_orden_magnitud_t_secado_horas(self):
        """Para 10 kg de fruta a 50 °C con h≈15 W/m²K, t_secado debe ser de horas."""
        res = simular_secado(**_kwargs_motor())
        assert 1800 < res.t_secado_s < 24 * 3600  # entre 30 min y 24 h


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------


class TestEventDetection:

    def test_X_en_t_secado_coincide_con_X_obj(self):
        kw = _kwargs_motor()
        res = simular_secado(**kw)
        assert res.X_prod_kg_kg[-1] == pytest.approx(
            kw["X_prod_objetivo_kg_kg"], abs=1e-3
        )

    def test_X_inicial_menor_X_obj_t_cero(self):
        """Producto ya seco → status especial, t_secado=0, sin integrar."""
        res = simular_secado(**_kwargs_motor(
            X_prod_inicial_kg_kg=0.10,
            X_prod_objetivo_kg_kg=0.30,
        ))
        assert res.status == "X_inicial_ya_seco"
        assert res.t_secado_s == 0.0
        assert any("YA_SECO" in a for a in res.advertencias)

    def test_t_max_insuficiente_devuelve_status(self):
        """t_max muy chico → status 't_max_alcanzado' con advertencia."""
        res = simular_secado(**_kwargs_motor(t_max_s=60.0))  # 1 minuto
        assert res.status == "t_max_alcanzado"
        assert res.t_secado_s is None
        assert any("T_MAX" in a for a in res.advertencias)
        # X final aún por encima del objetivo
        assert res.X_prod_kg_kg[-1] > _kwargs_motor()["X_prod_objetivo_kg_kg"]


# ---------------------------------------------------------------------------
# Conservación física
# ---------------------------------------------------------------------------


class TestConservacionFisica:

    def test_balance_masa_global(self):
        """∫ṁ_w dt ≈ m_seco·(X_inicial − X_final). Tolerancia: 1 % por integración."""
        kw = _kwargs_motor()
        res = simular_secado(**kw)
        masa_esperada = kw["m_seco_prod_kg"] * (
            kw["X_prod_inicial_kg_kg"] - res.X_prod_kg_kg[-1]
        )
        assert res.masa_evaporada_total_kg == pytest.approx(
            masa_esperada, rel=0.01
        )

    def test_T_prod_tiende_a_T_wb_en_regimen_constante(self):
        """Con a_w=1 y caudal alto, T_prod → T_wb del aire entrante.

        En régimen de tasa constante, el producto se enfría evaporativamente
        hasta que T_prod alcanza la T de bulbo húmedo (saturación adiabática).
        """
        kw = _kwargs_motor(
            aw_func=lambda X: 1.0,                          # producto saturado
            X_prod_inicial_kg_kg=5.0,                       # mucha agua
            X_prod_objetivo_kg_kg=0.001,                    # nunca se alcanza en t_max
            m_dot_as_kg_s=1.0,                              # caudal alto: ω_flujo ≈ ω_ent
            t_max_s=4 * 3600.0,
        )
        res = simular_secado(**kw)
        # T_wb del aire entrante
        T_wb = temperatura_bulbo_humedo(kw["T_ent_K"], kw["omega_ent_kg_kg"])
        # En t suficientemente largo (>> τ térmica del producto), T_prod ≈ T_wb
        assert abs(res.T_prod_K[-1] - T_wb) < 2.0

    def test_sin_evaporacion_ni_perdidas_T_prod_tiende_a_T_ent(self):
        """K_m=0 + U=0 → producto se calienta hasta T_ent (régimen sensible puro).

        Si hubiese pérdidas a paredes (U > 0), T_prod tendería a un T_flujo
        de equilibrio entre T_ent y T_amb, no a T_ent.
        """
        kw = _kwargs_motor(
            K_m_kg_m2s=0.0,
            U_muros_W_m2K=0.0,                              # sin pérdidas a paredes
            X_prod_objetivo_kg_kg=0.5,                      # nunca se alcanza
            t_max_s=4 * 3600.0,
        )
        res = simular_secado(**kw)
        assert res.status == "t_max_alcanzado"
        assert res.T_prod_K[-1] == pytest.approx(kw["T_ent_K"], abs=1.0)
        assert res.X_prod_kg_kg[-1] == pytest.approx(
            kw["X_prod_inicial_kg_kg"], rel=1e-6
        )


# ---------------------------------------------------------------------------
# Sensibilidad a parámetros operativos
# ---------------------------------------------------------------------------


class TestSensibilidad:

    def test_mayor_caudal_menor_t_secado(self):
        res_bajo = simular_secado(**_kwargs_motor(m_dot_as_kg_s=0.020))
        res_alto = simular_secado(**_kwargs_motor(m_dot_as_kg_s=0.080))
        assert res_alto.t_secado_s < res_bajo.t_secado_s

    def test_mayor_h_conv_menor_t_secado(self):
        res_bajo = simular_secado(**_kwargs_motor(h_conv_W_m2K=8.0))
        res_alto = simular_secado(**_kwargs_motor(h_conv_W_m2K=30.0))
        assert res_alto.t_secado_s < res_bajo.t_secado_s

    def test_mayor_T_ent_menor_t_secado(self):
        res_frio = simular_secado(**_kwargs_motor(T_ent_K=313.15))   # 40 °C
        res_caliente = simular_secado(**_kwargs_motor(T_ent_K=333.15))  # 60 °C
        assert res_caliente.t_secado_s < res_frio.t_secado_s


# ---------------------------------------------------------------------------
# Validación de entradas del motor
# ---------------------------------------------------------------------------


class TestValidacionMotor:

    def test_m_seco_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_M_SECO_NO_POSITIVA"):
            simular_secado(**_kwargs_motor(m_seco_prod_kg=0.0))

    def test_cp_prod_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_CP_PROD_NO_POSITIVA"):
            simular_secado(**_kwargs_motor(cp_prod_J_kgK=-1.0))

    def test_T_inicial_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_T_INICIAL_NO_POSITIVA"):
            simular_secado(**_kwargs_motor(T_prod_inicial_K=0.0))

    def test_X_inicial_negativa_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_X_INICIAL_NEGATIVA"):
            simular_secado(**_kwargs_motor(X_prod_inicial_kg_kg=-0.1))

    def test_X_obj_negativa_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_X_OBJ_NEGATIVA"):
            simular_secado(**_kwargs_motor(X_prod_objetivo_kg_kg=-0.5))

    def test_t_max_no_positivo_lanza(self):
        with pytest.raises(ValueError, match="MOTOR_TD_T_MAX_NO_POSITIVO"):
            simular_secado(**_kwargs_motor(t_max_s=0.0))
