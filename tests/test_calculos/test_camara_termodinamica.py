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
    """Retorna kwargs nominales reproducibles, con overrides.

    Pared 3-nodos calibrada para U_total = 0.5 W/(m²·K) (default histórico de
    ConstruccionCamara): h_conv_int=15, h_w=15 (≈ v_viento 2.5 m/s), esp_cam=0.05 m,
    k_aisl=0.02679 W/(m·K) (espuma rígida). R_total = 1/15 + 0.05/0.02679 + 1/15
    = 2.0 m²K/W ⇒ U_total = 0.5.
    """
    base = dict(
        T_prod_K=313.15,                                    # 40 °C
        X_prod_kg_kg=2.0,
        T_ent_K=323.15,                                     # 50 °C aire del colector
        omega_ent_kg_kg=humedad_absoluta(0.20, 323.15),     # HR=20 %
        A_prod_m2=2.5,                                      # 5 bandejas × 0.5 m²
        A_cuerpo_m2=8.0,                                    # paredes
        m_dot_as_kg_s=0.030,
        h_conv_W_m2K=15.0,                                  # convección interior
        K_m_kg_m2s=0.015,
        h_w_W_m2K=15.0,                                     # convección exterior (viento)
        k_aisl_W_mK=0.02679,                                # espuma rígida
        esp_cam_m=0.05,
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

    def test_k_aisl_cero_pared_aislante_perfecta(self):
        """k_aisl = 0 → R_cond = ∞ → U_total = 0 → q_pared = 0."""
        est = resolver_estado_camara(**_kwargs_base(k_aisl_W_mK=0.0))
        assert est.q_pared_W == pytest.approx(0.0, abs=1e-12)
        assert est.U_pared_W_m2K == 0.0
        # Pared desacoplada: T_cam_int queda al lado del flujo, T_cam_ext al lado del amb.
        assert est.T_cam_int_K == pytest.approx(est.T_flujo_K, abs=1e-9)
        assert est.T_cam_ext_K == pytest.approx(_kwargs_base()["T_amb_K"], abs=1e-9)

    def test_T_ent_igual_T_prod_sin_evap_sin_perdidas(self):
        """T_ent = T_prod = T_amb, K_m=0, pared aislante → T_flujo = T_ent."""
        T = 318.15
        est = resolver_estado_camara(
            **_kwargs_base(
                T_prod_K=T,
                T_ent_K=T,
                T_amb_K=T,
                K_m_kg_m2s=0.0,
                k_aisl_W_mK=0.0,
            )
        )
        assert est.T_flujo_K == pytest.approx(T, abs=1e-9)

    def test_T_prod_mayor_que_T_ent_aire_se_calienta(self):
        """Si el producto está más caliente que el aire entrante, T_flujo > T_ent."""
        kw = _kwargs_base(T_prod_K=343.15, T_ent_K=303.15, k_aisl_W_mK=0.0)
        est = resolver_estado_camara(**kw)
        assert est.T_flujo_K > kw["T_ent_K"]
        assert est.q_prod_W < 0  # el aire recibe calor del producto

    def test_T_cam_int_entre_T_flujo_y_T_cam_ext(self):
        """En régimen normal, T_flujo > T_cam_int > T_cam_ext > T_amb."""
        est = resolver_estado_camara(**_kwargs_base())
        kw = _kwargs_base()
        # El aire cede calor por la pared → T_cam_int < T_flujo
        assert est.T_cam_int_K < est.T_flujo_K
        # La conducción a través del aislante cae T → T_cam_ext < T_cam_int
        assert est.T_cam_ext_K < est.T_cam_int_K
        # La pared exterior está sobre T_amb (perdida hacia el exterior)
        assert est.T_cam_ext_K > kw["T_amb_K"]

    def test_balance_pared_3_nodos_consistente(self):
        """h_conv·(T_f − T_ci) = (k/e)·(T_ci − T_ce) = h_w·(T_ce − T_amb)."""
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        flujo_int = kw["h_conv_W_m2K"] * (est.T_flujo_K - est.T_cam_int_K)
        flujo_cond = (kw["k_aisl_W_mK"] / kw["esp_cam_m"]) * (
            est.T_cam_int_K - est.T_cam_ext_K
        )
        flujo_ext = kw["h_w_W_m2K"] * (est.T_cam_ext_K - kw["T_amb_K"])
        # Los tres flujos por unidad de área deben coincidir (régimen estacionario)
        assert flujo_int == pytest.approx(flujo_cond, rel=1e-9)
        assert flujo_cond == pytest.approx(flujo_ext, rel=1e-9)
        # Y deben coincidir con q_pared/A_cuerpo
        assert flujo_int == pytest.approx(est.q_pared_W / kw["A_cuerpo_m2"], rel=1e-9)

    def test_U_pared_cascada_consistente(self):
        """U_total reportado = 1/(1/h_conv + esp/k + 1/h_w)."""
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        R_esperado = (
            1.0 / kw["h_conv_W_m2K"]
            + kw["esp_cam_m"] / kw["k_aisl_W_mK"]
            + 1.0 / kw["h_w_W_m2K"]
        )
        U_esperado = 1.0 / R_esperado
        assert est.U_pared_W_m2K == pytest.approx(U_esperado, rel=1e-12)


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
        """LHS − RHS de la ecuación (b) debe ser ≈ 0 (analítico exacto).

        Q_pared se toma directamente de est.q_pared_W (ya incluye la cascada
        3-nodos: U_total·A_cuerpo·(T_flujo − T_amb)).
        """
        kw = _kwargs_base()
        est = resolver_estado_camara(**kw)
        h_ent = entalpia_aire_humedo(kw["T_ent_K"], kw["omega_ent_kg_kg"])
        h_sal = entalpia_aire_humedo(est.T_flujo_K, est.omega_flujo_kg_kg)
        h_v_prod = _LV_0 + _CP_VAPOR * (kw["T_prod_K"] - _T_REF)
        LHS = kw["m_dot_as_kg_s"] * (h_sal - h_ent)
        RHS = (
            -est.q_pared_W
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

    def test_h_w_negativo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_H_W_NEGATIVO"):
            resolver_estado_camara(**_kwargs_base(h_w_W_m2K=-1.0))

    def test_k_aisl_negativa_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_K_AISL_NEGATIVA"):
            resolver_estado_camara(**_kwargs_base(k_aisl_W_mK=-0.001))

    def test_esp_cam_no_positivo_lanza(self):
        with pytest.raises(ValueError, match="CAM_TD_ESP_CAM_NO_POSITIVO"):
            resolver_estado_camara(**_kwargs_base(esp_cam_m=0.0))

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
from core.camara import ForzantesAire


# v_viento default de los tests: 2.5 m/s → h_w = 5.7 + 3.8·2.5 = 15.2 W/(m²·K)
# (reproduce el U_total = 0.5 del fixture pared 3-nodos en _kwargs_base).
_V_VIENTO_TEST_MS = 2.5


def _kwargs_motor(**overrides):
    """Kwargs nominales para el motor: secador armario con 10 kg de fruta.

    Por conveniencia acepta T_ent_K, omega_ent_kg_kg, m_dot_as_kg_s, T_amb_K,
    v_viento_ms como overrides (no son kwargs reales de simular_secado pero
    se inyectan al construir ForzantesAire degeneradas en 2 puntos).
    """
    # Override-aware extracción de parámetros que van a la forzante
    T_ent = overrides.pop("T_ent_K", 323.15)                 # 50 °C
    omega_ent = overrides.pop("omega_ent_kg_kg", humedad_absoluta(0.20, 323.15))
    m_dot = overrides.pop("m_dot_as_kg_s", 0.030)
    T_amb = overrides.pop("T_amb_K", 298.15)
    v_viento = overrides.pop("v_viento_ms", _V_VIENTO_TEST_MS)
    t_max = float(overrides.get("t_max_s", 24 * 3600.0))

    forzantes = ForzantesAire(
        t_s=np.array([0.0, t_max], dtype=float),
        T_ent_K=np.full(2, T_ent),
        omega_ent=np.full(2, omega_ent),
        m_dot_aire_seco_kg_s=np.full(2, m_dot),
        T_amb_K=np.full(2, T_amb),
        v_viento_ms=np.full(2, v_viento),
    )

    base = dict(
        T_prod_inicial_K=298.15,                            # 25 °C
        X_prod_inicial_kg_kg=2.0,                           # producto bastante húmedo
        X_prod_objetivo_kg_kg=0.30,
        m_seco_prod_kg=3.0,                                 # 10 kg fruta ≈ 3 kg seco
        c_ps_J_kgK=1500.0,                                  # sólido seco (default catálogo)
        forzantes=forzantes,
        A_prod_m2=2.5,
        A_cuerpo_m2=8.0,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        k_aisl_W_mK=0.02679,
        esp_cam_m=0.05,
        P_Pa=101325.0,
        aw_func=lambda X: min(1.0, max(0.0, X / 0.5)),      # rampa: aw=1 si X≥0.5
        t_max_s=t_max,
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
        T_ent = 323.15
        kw = _kwargs_motor(T_ent_K=T_ent)
        res = simular_secado(**kw)
        assert np.all(res.T_prod_K >= kw["T_prod_inicial_K"] - 1.0)
        assert np.all(res.T_prod_K <= T_ent + 1.0)

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
        T_ent = 323.15
        omega_ent = humedad_absoluta(0.20, 323.15)
        kw = _kwargs_motor(
            aw_func=lambda X: 1.0,                          # producto saturado
            X_prod_inicial_kg_kg=5.0,                       # mucha agua
            X_prod_objetivo_kg_kg=0.001,                    # nunca se alcanza en t_max
            T_ent_K=T_ent,
            omega_ent_kg_kg=omega_ent,
            m_dot_as_kg_s=1.0,                              # caudal alto: ω_flujo ≈ ω_ent
            t_max_s=4 * 3600.0,
        )
        res = simular_secado(**kw)
        # T_wb del aire entrante
        T_wb = temperatura_bulbo_humedo(T_ent, omega_ent)
        # En t suficientemente largo (>> τ térmica del producto), T_prod ≈ T_wb
        assert abs(res.T_prod_K[-1] - T_wb) < 2.0

    def test_sin_evaporacion_ni_perdidas_T_prod_tiende_a_T_ent(self):
        """K_m=0 + pared aislante → producto se calienta hasta T_ent (sensible puro).

        Si hubiese pérdidas a paredes, T_prod tendería a un T_flujo de
        equilibrio entre T_ent y T_amb, no a T_ent.
        """
        T_ent = 323.15
        kw = _kwargs_motor(
            T_ent_K=T_ent,
            K_m_kg_m2s=0.0,
            k_aisl_W_mK=0.0,                                # pared aislante perfecta
            X_prod_objetivo_kg_kg=0.5,                      # nunca se alcanza
            t_max_s=4 * 3600.0,
        )
        res = simular_secado(**kw)
        assert res.status == "t_max_alcanzado"
        assert res.T_prod_K[-1] == pytest.approx(T_ent, abs=1.0)
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
            simular_secado(**_kwargs_motor(c_ps_J_kgK=-1.0))

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


# ===========================================================================
# Fase 2: forzantes horarias variables, política B, cp(X), eventos T_max
# ===========================================================================


def _kwargs_motor_con_forzantes(forzantes, **overrides):
    """Igual que _kwargs_motor pero inyecta una ForzantesAire arbitraria."""
    base = dict(
        T_prod_inicial_K=298.15,
        X_prod_inicial_kg_kg=2.0,
        X_prod_objetivo_kg_kg=0.30,
        m_seco_prod_kg=3.0,
        c_ps_J_kgK=1500.0,
        forzantes=forzantes,
        A_prod_m2=2.5,
        A_cuerpo_m2=8.0,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        k_aisl_W_mK=0.02679,
        esp_cam_m=0.05,
        P_Pa=101325.0,
        aw_func=lambda X: min(1.0, max(0.0, X / 0.5)),
        t_max_s=24 * 3600.0,
    )
    base.update(overrides)
    return base


class TestForzantesVariables:
    """Verifica que las forzantes horarias se interpolan y mueven el sistema."""

    def test_T_ent_oscilante_modula_T_prod(self):
        """T_ent senoidal día/noche → T_prod sigue con retraso, sin diverger."""
        t = np.linspace(0.0, 24 * 3600.0, 25)
        # Senoidal con pico a las 12 h: T_ent oscila entre 30 °C y 60 °C
        T_ent = 318.15 + 15.0 * np.sin(2 * np.pi * (t - 6 * 3600.0) / (24 * 3600.0))
        omega_ent = np.full_like(t, humedad_absoluta(0.30, 313.15))
        m_dot = np.full_like(t, 0.030)
        T_amb = np.full_like(t, 293.15)
        v_w = np.full_like(t, 2.5)
        fz = ForzantesAire(
            t_s=t, T_ent_K=T_ent, omega_ent=omega_ent,
            m_dot_aire_seco_kg_s=m_dot, T_amb_K=T_amb, v_viento_ms=v_w,
        )
        res = simular_secado(**_kwargs_motor_con_forzantes(
            fz, X_prod_objetivo_kg_kg=0.05, t_max_s=24 * 3600.0,
        ))
        # T_prod debe oscilar sin diverger ni dispararse
        assert np.all(res.T_prod_K < 333.15)        # no excede T_ent_max + ~10 K
        assert np.all(res.T_prod_K > 290.0)         # no se enfría por debajo de T_amb − algo
        # Y debe tener variabilidad (no es plana)
        assert np.std(res.T_prod_K) > 1.0

    def test_v_viento_alta_aumenta_perdidas(self):
        """Con más viento (h_w mayor), U_pared aumenta y q_pared crece."""
        # Caso bajo viento
        kw_bajo = _kwargs_motor(v_viento_ms=0.5, X_prod_objetivo_kg_kg=0.05,
                                  t_max_s=4 * 3600.0)
        kw_alto = _kwargs_motor(v_viento_ms=10.0, X_prod_objetivo_kg_kg=0.05,
                                   t_max_s=4 * 3600.0)
        res_bajo = simular_secado(**kw_bajo)
        res_alto = simular_secado(**kw_alto)
        # U_pared debe ser mayor con más viento
        assert np.mean(res_alto.U_pared_W_m2K) > np.mean(res_bajo.U_pared_W_m2K)
        # Y las pérdidas |q_pared| también mayores (en magnitud)
        assert np.mean(np.abs(res_alto.q_pared_W)) > np.mean(np.abs(res_bajo.q_pared_W))


class TestPoliticaBAntirehumectacion:
    """Política B: dX/dt se clipea a 0 si la fuerza motriz se invierte."""

    def test_aire_saturado_no_rehumecta_producto_seco(self):
        """Producto casi seco + aire entrante muy húmedo → política B activa."""
        # Producto en X=0.05 (casi seco), aire entrante a HR=0.95 (casi saturado)
        kw = _kwargs_motor(
            X_prod_inicial_kg_kg=0.05,
            X_prod_objetivo_kg_kg=0.001,
            omega_ent_kg_kg=humedad_absoluta(0.95, 313.15),
            T_ent_K=313.15,                          # T baja: ω_sat baja
            aw_func=lambda X: 0.05,                  # producto seco → ω_sup muy baja
            t_max_s=3600.0,
        )
        res = simular_secado(**kw)
        # X no debería AUMENTAR significativamente respecto al inicial
        assert res.X_prod_kg_kg[-1] <= kw["X_prod_inicial_kg_kg"] + 1e-6
        # Debe haber acumulado horas de clipeo
        assert res.horas_clipeo_nocturno_s > 0.0


class TestCpVariable:
    """cp_prod efectivo depende de X — capacidad térmica decrece al secarse."""

    def test_cp_variable_secado_completo_consistente(self):
        """Producto con mucha agua (X alto inicial): la capacidad térmica
        empieza alta, decrece al secarse. La simulación debe avanzar de forma
        consistente (sin NaN, T_prod acotada, X decreciente).

        Con cp(X) variable, secar 15 kg de fruta puede no completarse en 24 h
        con los caudales nominales; aquí sólo verificamos consistencia física.
        """
        kw = _kwargs_motor(
            X_prod_inicial_kg_kg=4.0,           # mucha agua: C_thermal alta al inicio
            X_prod_objetivo_kg_kg=0.10,
            t_max_s=48 * 3600.0,
        )
        res = simular_secado(**kw)
        # Sin NaN
        assert np.all(np.isfinite(res.T_prod_K))
        assert np.all(np.isfinite(res.X_prod_kg_kg))
        # X debe decrecer (o quedarse) en promedio
        assert res.X_prod_kg_kg[-1] < kw["X_prod_inicial_kg_kg"]
        # T_prod razonable
        assert 280.0 < res.T_prod_K[-1] < 340.0


class TestEventoTMaxAdmisible:
    """Si T_prod supera T_max, status='dano_termico' y termina."""

    def test_T_max_alcanzada_dispara_evento(self):
        """T_max_admisible bajo + producto seco que se calienta → dano_termico."""
        kw = _kwargs_motor(
            T_prod_inicial_K=298.15,
            X_prod_inicial_kg_kg=0.05,           # poca agua
            X_prod_objetivo_kg_kg=0.001,
            aw_func=lambda X: 0.0,               # nada de evaporación → solo se calienta
            K_m_kg_m2s=0.0,
            T_ent_K=343.15,                      # 70 °C: producto se calienta
            T_max_admisible_K=313.15,            # 40 °C: cota baja
            t_max_s=4 * 3600.0,
        )
        res = simular_secado(**kw)
        assert res.status == "dano_termico"
        assert res.t_secado_s is None
        assert any("DANO_TERMICO" in a for a in res.advertencias)
        # T_prod final debe estar cerca de T_max (cruzó por arriba)
        assert res.T_prod_K[-1] >= 312.0

    def test_T_max_no_alcanzado_no_dispara(self):
        """Si T_max es alto, status no es 'dano_termico'."""
        res = simular_secado(**_kwargs_motor(
            T_max_admisible_K=400.0,         # cota alta: nunca se alcanza
        ))
        assert res.status != "dano_termico"
        # T_max_alcanzada reportada debe ser razonable
        assert res.T_max_alcanzada_K < 400.0


class TestReconstruccionCompleta:
    """ResultadoMotorTermodinamico reporta T_cam_int, T_cam_ext, U_pared, HR_flujo."""

    def test_series_de_pared_y_HR_no_vacias(self):
        res = simular_secado(**_kwargs_motor())
        n = len(res.t_array_s)
        assert res.T_cam_int_K.shape == (n,)
        assert res.T_cam_ext_K.shape == (n,)
        assert res.U_pared_W_m2K.shape == (n,)
        assert res.HR_flujo.shape == (n,)
        # T_cam_int debería estar siempre entre T_flujo y T_cam_ext (mayoría del tiempo)
        assert np.mean(res.T_cam_int_K <= res.T_flujo_K + 1e-6) > 0.95
        assert np.mean(res.T_cam_int_K >= res.T_cam_ext_K - 1e-6) > 0.95

    def test_HR_flujo_finito_y_acotado(self):
        res = simular_secado(**_kwargs_motor())
        assert np.all(np.isfinite(res.HR_flujo))
        # HR debe estar en [0, 1.1] (ligero overshoot numérico aceptable)
        assert np.all(res.HR_flujo >= 0.0)
        assert np.all(res.HR_flujo <= 1.1)
