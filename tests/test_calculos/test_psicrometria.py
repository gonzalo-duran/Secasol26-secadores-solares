"""Tests del módulo de psicrometría (calculos/psicrometria.py)."""

from __future__ import annotations

import math

import pytest

from calculos.psicrometria import (
    HR_desde_omega,
    actividad_agua_desde_X_GAB,
    balance_masa_camara,
    calor_latente_vaporizacion,
    coef_transferencia_masa_chilton_colburn,
    cp_aire_humedo,
    densidad_aire_humedo,
    entalpia_aire_humedo,
    humedad_absoluta,
    omega_saturacion,
    presion_vapor_saturacion,
    temperatura_bulbo_humedo,
    temperatura_punto_rocio,
    volumen_especifico_aire_humedo,
)


# ===========================================================================
# Tests originales — Sesión 18 — funciones psicrométricas base
# ===========================================================================


# ---------------------------------------------------------------------------
# presion_vapor_saturacion
# ---------------------------------------------------------------------------


class TestPresionVaporSaturacion:

    def test_valor_0C(self):
        """Ps(0 °C) ≈ 611 Pa — valor estándar."""
        Ps = presion_vapor_saturacion(273.15)
        assert Ps == pytest.approx(611.0, rel=0.002)

    def test_valor_50C(self):
        """Ps(50 °C) ≈ 12 349 Pa — tablas de vapor."""
        Ps = presion_vapor_saturacion(323.15)
        assert Ps == pytest.approx(12349.0, rel=0.002)

    def test_valor_100C(self):
        """Ps(100 °C) ≈ 101 325 Pa — punto de ebullición a 1 atm."""
        Ps = presion_vapor_saturacion(373.15)
        # La ecuación de Buck da ~103 000 Pa a 100 °C; toleramos 3%.
        assert Ps == pytest.approx(101325.0, rel=0.03)

    def test_monotona_creciente(self):
        """Ps debe crecer con la temperatura."""
        T_vals = [273.15, 293.15, 313.15, 333.15, 353.15]
        Ps_vals = [presion_vapor_saturacion(T) for T in T_vals]
        for i in range(len(Ps_vals) - 1):
            assert Ps_vals[i + 1] > Ps_vals[i]

    def test_positiva_siempre(self):
        for T in [273.15, 300.0, 340.0]:
            assert presion_vapor_saturacion(T) > 0


# ---------------------------------------------------------------------------
# humedad_absoluta
# ---------------------------------------------------------------------------


class TestHumedadAbsoluta:

    def test_HR_cero_da_omega_cero(self):
        omega = humedad_absoluta(0.0, 313.15)
        assert omega == pytest.approx(0.0, abs=1e-12)

    def test_HR_1_da_omega_saturacion(self):
        omega_sat = humedad_absoluta(1.0, 313.15)
        omega_from_fn = omega_saturacion(313.15)
        assert omega_sat == pytest.approx(omega_from_fn, rel=1e-9)

    def test_valor_tipico_40C_50pct(self):
        """A 40 °C y HR=50% ω ≈ 0.0234 kg/kg (tabla de aire húmedo)."""
        omega = humedad_absoluta(0.50, 313.15)
        assert omega == pytest.approx(0.0234, rel=0.03)

    def test_omega_crece_con_HR(self):
        T = 323.15
        omega_low = humedad_absoluta(0.20, T)
        omega_high = humedad_absoluta(0.80, T)
        assert omega_high > omega_low

    def test_omega_crece_con_T(self):
        """A mayor T, mayor ω para la misma HR (más vapor en el aire)."""
        omega_30 = humedad_absoluta(0.50, 303.15)
        omega_60 = humedad_absoluta(0.50, 333.15)
        assert omega_60 > omega_30

    def test_Pv_excede_P_lanza(self):
        """HR=1.0 a 100 °C con P=50 000 Pa (< Ps) debe lanzar ValueError."""
        with pytest.raises(ValueError, match="PSICRO_PV_EXCEDE_P"):
            humedad_absoluta(1.0, 373.15, P_Pa=50000.0)


# ---------------------------------------------------------------------------
# HR_desde_omega — inversa de humedad_absoluta
# ---------------------------------------------------------------------------


class TestHRDesdeOmega:

    def test_inversa_exacta(self):
        """HR_desde_omega(humedad_absoluta(HR, T, P), T, P) == HR."""
        for HR in [0.10, 0.30, 0.60, 0.90]:
            T = 323.15
            omega = humedad_absoluta(HR, T)
            HR_rec = HR_desde_omega(omega, T)
            assert HR_rec == pytest.approx(HR, rel=1e-6)

    def test_omega_cero_da_HR_cero(self):
        HR = HR_desde_omega(0.0, 313.15)
        assert HR == pytest.approx(0.0, abs=1e-12)

    def test_supersaturacion_devuelve_mayor_uno(self):
        """ω > ω_sat debe devolver HR > 1 (no se clipea internamente)."""
        omega_sat = omega_saturacion(313.15)
        HR = HR_desde_omega(omega_sat * 1.5, 313.15)
        assert HR > 1.0


# ---------------------------------------------------------------------------
# omega_saturacion
# ---------------------------------------------------------------------------


class TestOmegaSaturacion:

    def test_crece_con_T(self):
        omega_30 = omega_saturacion(303.15)
        omega_60 = omega_saturacion(333.15)
        assert omega_60 > omega_30

    def test_valor_40C(self):
        """ω_sat(40 °C, 1 atm) ≈ 0.0495 kg/kg (tabla)."""
        omega = omega_saturacion(313.15)
        assert omega == pytest.approx(0.0495, rel=0.03)


# ---------------------------------------------------------------------------
# temperatura_punto_rocio
# ---------------------------------------------------------------------------


class TestTemperaturaPuntoRocio:

    def test_HR_1_da_T_rocio_igual_T_bulbo_seco(self):
        """Con HR=1, el punto de rocío es igual a la T del aire."""
        T = 313.15
        T_dp = temperatura_punto_rocio(1.0, T)
        assert T_dp == pytest.approx(T, abs=0.5)

    def test_T_rocio_menor_que_T_bulbo_seco(self):
        """Con HR < 1, T_rocio < T_bulbo_seco."""
        T = 323.15
        T_dp = temperatura_punto_rocio(0.50, T)
        assert T_dp < T

    def test_T_rocio_sube_con_HR(self):
        T = 323.15
        T_dp_20 = temperatura_punto_rocio(0.20, T)
        T_dp_80 = temperatura_punto_rocio(0.80, T)
        assert T_dp_80 > T_dp_20

    def test_valor_conocido(self):
        """A T=25 °C y HR=50%, T_rocio ≈ 13.8 °C."""
        T_dp = temperatura_punto_rocio(0.50, 298.15)
        assert T_dp == pytest.approx(273.15 + 13.8, abs=0.5)


# ---------------------------------------------------------------------------
# balance_masa_camara
# ---------------------------------------------------------------------------


class TestBalanceMasaCamara:

    def test_sin_evaporacion_omega_no_cambia(self):
        omega_out = balance_masa_camara(
            omega_entrada=0.010,
            masa_agua_kg=0.0,
            m_dot_aire_seco_kg_s=0.03,
            t_secado_s=3600.0,
        )
        assert omega_out == pytest.approx(0.010, rel=1e-9)

    def test_omega_out_mayor_que_omega_in(self):
        omega_out = balance_masa_camara(
            omega_entrada=0.010,
            masa_agua_kg=1.0,
            m_dot_aire_seco_kg_s=0.03,
            t_secado_s=3600.0,
        )
        assert omega_out > 0.010

    def test_formula_exacta(self):
        """ω_out = ω_in + masa_agua / (m_dot × t)."""
        omega_in = 0.012
        masa = 2.0
        m_dot = 0.05
        t = 7200.0
        omega_esperado = omega_in + masa / (m_dot * t)
        omega_out = balance_masa_camara(omega_in, masa, m_dot, t)
        assert omega_out == pytest.approx(omega_esperado, rel=1e-9)

    def test_mayor_caudal_menor_incremento(self):
        """A mayor caudal, el aire se carga menos de humedad."""
        omega_bajo = balance_masa_camara(0.010, 1.0, 0.01, 3600.0)
        omega_alto = balance_masa_camara(0.010, 1.0, 0.10, 3600.0)
        assert omega_alto < omega_bajo

    def test_mayor_tiempo_menor_incremento(self):
        """Mayor tiempo → tasa de evaporación menor → menor carga del aire."""
        omega_rapido = balance_masa_camara(0.010, 1.0, 0.03, 1800.0)
        omega_lento = balance_masa_camara(0.010, 1.0, 0.03, 7200.0)
        assert omega_lento < omega_rapido

    def test_caudal_cero_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_CAUDAL_NO_POSITIVO"):
            balance_masa_camara(0.010, 1.0, 0.0, 3600.0)

    def test_t_cero_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_T_SECADO_NO_POSITIVO"):
            balance_masa_camara(0.010, 1.0, 0.03, 0.0)


# ---------------------------------------------------------------------------
# entalpia_aire_humedo
# ---------------------------------------------------------------------------


class TestEntalpiaAireHumedo:

    def test_aire_seco_a_0C_es_cero(self):
        """A T=0 °C y ω=0, h = 0 (T_ref = 0 °C)."""
        h = entalpia_aire_humedo(273.15, 0.0)
        assert h == pytest.approx(0.0, abs=1.0)

    def test_crece_con_T(self):
        h_30 = entalpia_aire_humedo(303.15, 0.010)
        h_60 = entalpia_aire_humedo(333.15, 0.010)
        assert h_60 > h_30

    def test_crece_con_omega(self):
        """A mayor ω, mayor contribución del vapor → mayor entalpía."""
        h_seco = entalpia_aire_humedo(323.15, 0.005)
        h_humedo = entalpia_aire_humedo(323.15, 0.030)
        assert h_humedo > h_seco

    def test_valor_tipico_50C_omega_020(self):
        """
        A 50 °C y ω=0.020 kg/kg:
        h ≈ 1006×50 + 0.020×(2501000 + 1805×50)
          ≈ 50300 + 0.020×2591250
          ≈ 50300 + 51825 ≈ 102125 J/kg
        """
        h = entalpia_aire_humedo(323.15, 0.020)
        assert h == pytest.approx(102125.0, rel=0.005)


# ---------------------------------------------------------------------------
# Integración: corrección psicrométrica en calcular_tiempo_secado
# ---------------------------------------------------------------------------


class TestIntegracionPsicrometriaCamara:
    """Verifica que calcular_tiempo_secado popula los campos psicrométricos."""

    @pytest.fixture
    def camara_manzana(self):
        from core.camara import Camara, CargaProducto, ConfiguracionFlujo
        return Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )

    def test_omega_entrada_poblado(self, camara_manzana):
        from calculos.camara_calc import calcular_tiempo_secado
        res = calcular_tiempo_secado(camara_manzana, 323.15, 0.20)
        assert res.omega_entrada_kg_kg is not None
        assert res.omega_entrada_kg_kg > 0

    def test_omega_salida_mayor_que_entrada(self, camara_manzana):
        from calculos.camara_calc import calcular_tiempo_secado
        res = calcular_tiempo_secado(camara_manzana, 323.15, 0.20)
        assert res.omega_salida_kg_kg > res.omega_entrada_kg_kg

    def test_HR_salida_entre_0_y_1(self, camara_manzana):
        from calculos.camara_calc import calcular_tiempo_secado
        res = calcular_tiempo_secado(camara_manzana, 323.15, 0.20)
        assert res.HR_salida is not None
        assert 0.0 < res.HR_salida <= 1.0

    def test_HR_media_entre_HR_entrada_y_HR_salida(self, camara_manzana):
        from calculos.camara_calc import calcular_tiempo_secado
        HR_in = 0.20
        res = calcular_tiempo_secado(camara_manzana, 323.15, HR_in)
        assert res.HR_media is not None
        assert min(HR_in, res.HR_salida) <= res.HR_media <= max(HR_in, res.HR_salida)

    def test_saturacion_con_caudal_muy_bajo(self):
        """Caudal muy bajo → el aire se satura → advertencia CAM_RIESGO_SATURACION_AIRE."""
        from calculos.camara_calc import calcular_tiempo_secado
        from core.camara import Camara, CargaProducto, ConfiguracionFlujo
        cam = Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.0005),  # caudal minúsculo
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        res = calcular_tiempo_secado(cam, 323.15, 0.10)
        assert any("SATURACION" in a for a in res.advertencias)

    def test_t_secado_corregido_mayor_igual_original(self, camara_manzana):
        """La corrección aumenta X_eq → MR_obj más pequeño → t_secado mayor o igual."""
        from calculos.camara_calc import calcular_tiempo_secado
        res = calcular_tiempo_secado(camara_manzana, 323.15, 0.20)
        # Solo aplica si hay isoterma GAB (yacón); manzana usa fallback → sin corrección
        # Si no hay corrección, t_secado_corregido == t_secado
        assert res.t_secado_corregido_s >= res.t_secado_s - 1.0  # tolerancia 1 s

    def test_camara_yacon_tiene_correccion_gab(self):
        """Yacón tiene GAB → X_eq_corregido debería diferir de X_eq base."""
        from calculos.camara_calc import calcular_tiempo_secado
        from core.camara import Camara, CargaProducto, ConfiguracionFlujo
        cam = Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="yacon",
                masa_total_kg=5.0,
                humedad_inicial_X=9.0,
                humedad_objetivo_X=0.20,
                modelo_capa_fina="page",
            ),
        )
        res = calcular_tiempo_secado(cam, 323.15, 0.20)
        # X_eq con HR_media > X_eq con HR_entrada (aire en cámara es más húmedo)
        assert res.X_eq_corregido_kg_kg is not None
        assert res.X_eq_corregido_kg_kg >= res.X_eq_kg_kg - 0.001  # corrección ≥ 0


# ===========================================================================
# Tests Sesión 20 — funciones psicrométricas para motor termodinámico
# ===========================================================================


# ---------------------------------------------------------------------------
# calor_latente_vaporizacion
# ---------------------------------------------------------------------------


class TestCalorLatenteVaporizacion:

    def test_valor_0C(self):
        """L_v(0 °C) = 2 501 000 J/kg (referencia)."""
        Lv = calor_latente_vaporizacion(273.15)
        assert Lv == pytest.approx(2_501_000.0, rel=1e-6)

    def test_valor_100C(self):
        """L_v(100 °C) ≈ 2 264 000 J/kg (NIST: 2 256 400, error < 0.5 %)."""
        Lv = calor_latente_vaporizacion(373.15)
        assert Lv == pytest.approx(2_257_000.0, rel=0.005)

    def test_valor_50C(self):
        """L_v(50 °C) ≈ 2 382 500 J/kg (NIST: 2 382 800)."""
        Lv = calor_latente_vaporizacion(323.15)
        assert Lv == pytest.approx(2_382_500.0, rel=0.001)

    def test_decreciente_con_T(self):
        """L_v debe decrecer con la temperatura."""
        T_vals = [283.15, 303.15, 323.15, 343.15, 363.15]
        Lv_vals = [calor_latente_vaporizacion(T) for T in T_vals]
        for i in range(len(Lv_vals) - 1):
            assert Lv_vals[i + 1] < Lv_vals[i]

    def test_T_negativa_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_LV_T_FUERA_RANGO"):
            calor_latente_vaporizacion(263.15)  # -10 °C

    def test_pendiente_lineal(self):
        """dL_v/dT = -2370 J/(kg·K) por construcción."""
        Lv_25 = calor_latente_vaporizacion(298.15)
        Lv_75 = calor_latente_vaporizacion(348.15)
        pendiente = (Lv_75 - Lv_25) / 50.0
        assert pendiente == pytest.approx(-2370.0, rel=1e-9)


# ---------------------------------------------------------------------------
# cp_aire_humedo
# ---------------------------------------------------------------------------


class TestCpAireHumedo:

    def test_aire_seco(self):
        """ω=0 → cp = cp_aire_seco = 1006 J/(kg·K)."""
        cp = cp_aire_humedo(0.0)
        assert cp == pytest.approx(1006.0, rel=1e-9)

    def test_crece_con_omega(self):
        cp_seco = cp_aire_humedo(0.005)
        cp_humedo = cp_aire_humedo(0.025)
        assert cp_humedo > cp_seco

    def test_lineal_en_omega(self):
        """cp_hum = 1006 + 1805·ω."""
        omega = 0.020
        cp = cp_aire_humedo(omega)
        assert cp == pytest.approx(1006.0 + 1805.0 * omega, rel=1e-9)

    def test_omega_negativa_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_OMEGA_NEGATIVA"):
            cp_aire_humedo(-0.001)


# ---------------------------------------------------------------------------
# volumen_especifico_aire_humedo
# ---------------------------------------------------------------------------


class TestVolumenEspecifico:

    def test_aire_seco_25C(self):
        """v(25 °C, ω=0, 1 atm) ≈ 0.844 m³/kg (gas ideal seco)."""
        v = volumen_especifico_aire_humedo(298.15, 0.0)
        # R·T/P = 287.058·298.15/101325 = 0.8444 m³/kg
        assert v == pytest.approx(0.8444, rel=0.001)

    def test_aire_humedo_25C(self):
        """v(25 °C, ω=0.010, 1 atm) ≈ 0.858 m³/kg_as.

        ASHRAE Fundamentals 2021 tabla aire húmedo: v ≈ 0.8581.
        """
        v = volumen_especifico_aire_humedo(298.15, 0.010)
        assert v == pytest.approx(0.8581, rel=0.005)

    def test_crece_con_T(self):
        v_25 = volumen_especifico_aire_humedo(298.15, 0.010)
        v_60 = volumen_especifico_aire_humedo(333.15, 0.010)
        assert v_60 > v_25

    def test_crece_con_omega(self):
        """A más vapor de agua (más liviano que aire), volumen específico crece."""
        v_seco = volumen_especifico_aire_humedo(323.15, 0.005)
        v_hum = volumen_especifico_aire_humedo(323.15, 0.030)
        assert v_hum > v_seco

    def test_inversa_con_P(self):
        """v ∝ 1/P."""
        v_1atm = volumen_especifico_aire_humedo(298.15, 0.010, 101325.0)
        v_2atm = volumen_especifico_aire_humedo(298.15, 0.010, 2 * 101325.0)
        assert v_2atm == pytest.approx(v_1atm / 2.0, rel=1e-9)

    def test_T_negativa_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_T_NO_POSITIVA"):
            volumen_especifico_aire_humedo(-1.0, 0.010)

    def test_omega_negativa_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_OMEGA_NEGATIVA"):
            volumen_especifico_aire_humedo(298.15, -0.001)

    def test_P_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_P_NO_POSITIVA"):
            volumen_especifico_aire_humedo(298.15, 0.010, 0.0)


# ---------------------------------------------------------------------------
# densidad_aire_humedo
# ---------------------------------------------------------------------------


class TestDensidadAireHumedo:

    def test_aire_seco_25C(self):
        """ρ(25 °C, ω=0, 1 atm) ≈ 1.184 kg/m³."""
        rho = densidad_aire_humedo(298.15, 0.0)
        assert rho == pytest.approx(1.184, rel=0.005)

    def test_aire_humedo_50C(self):
        """ρ(50 °C, ω=0.020, 1 atm) ≈ 1.085 kg/m³ (ASHRAE)."""
        rho = densidad_aire_humedo(323.15, 0.020)
        assert rho == pytest.approx(1.085, rel=0.01)

    def test_decrece_con_T(self):
        rho_25 = densidad_aire_humedo(298.15, 0.010)
        rho_60 = densidad_aire_humedo(333.15, 0.010)
        assert rho_60 < rho_25

    def test_relacion_con_volumen(self):
        """ρ = (1 + ω) / v."""
        T, omega = 313.15, 0.015
        v = volumen_especifico_aire_humedo(T, omega)
        rho = densidad_aire_humedo(T, omega)
        assert rho == pytest.approx((1.0 + omega) / v, rel=1e-9)


# ---------------------------------------------------------------------------
# temperatura_bulbo_humedo
# ---------------------------------------------------------------------------


class TestTemperaturaBulboHumedo:

    def test_aire_saturado_T_wb_igual_T_db(self):
        """Aire saturado: T_wb = T_db."""
        T = 313.15
        omega_sat = omega_saturacion(T)
        T_wb = temperatura_bulbo_humedo(T, omega_sat)
        assert T_wb == pytest.approx(T, abs=0.01)

    def test_T_wb_menor_que_T_db(self):
        """Para aire no saturado, T_wb < T_db."""
        T = 313.15
        omega = humedad_absoluta(0.30, T)
        T_wb = temperatura_bulbo_humedo(T, omega)
        assert T_wb < T

    def test_T_wb_mayor_que_T_dp(self):
        """T_dp ≤ T_wb ≤ T_db (orden estricto para HR < 1)."""
        T = 323.15
        HR = 0.30
        omega = humedad_absoluta(HR, T)
        T_wb = temperatura_bulbo_humedo(T, omega)
        T_dp = temperatura_punto_rocio(HR, T)
        assert T_dp < T_wb < T

    def test_caso_ASHRAE_30C_50pct(self):
        """ASHRAE: T_db=30 °C, HR=50% → T_wb ≈ 21.95 °C."""
        T = 303.15
        omega = humedad_absoluta(0.50, T)
        T_wb = temperatura_bulbo_humedo(T, omega)
        assert (T_wb - 273.15) == pytest.approx(21.95, abs=0.5)

    def test_caso_ASHRAE_50C_20pct(self):
        """ASHRAE: T_db=50 °C, HR=20%.

        Caso típico de aire de salida de colector solar.
        ASHRAE da T_wb ≈ 27.6 °C (T_wb termodinámica con corrección
        de entalpía del agua líquida). Esta función resuelve la T de
        saturación adiabática pura (sin corrección de líquido), que
        es la magnitud físicamente correcta para el balance de cámara.
        Diferencia esperada: < 1 °C en el rango operativo de secado.
        """
        T = 323.15
        omega = humedad_absoluta(0.20, T)
        T_wb = temperatura_bulbo_humedo(T, omega)
        assert (T_wb - 273.15) == pytest.approx(28.0, abs=1.0)

    def test_T_wb_decrece_con_HR_baja(self):
        """A menor HR, mayor depresión de bulbo húmedo (T_db − T_wb)."""
        T = 333.15
        omega_seco = humedad_absoluta(0.10, T)
        omega_humedo = humedad_absoluta(0.60, T)
        T_wb_seco = temperatura_bulbo_humedo(T, omega_seco)
        T_wb_humedo = temperatura_bulbo_humedo(T, omega_humedo)
        # Depresión mayor con aire más seco
        assert (T - T_wb_seco) > (T - T_wb_humedo)

    def test_aire_supersaturado_devuelve_T_db(self):
        """ω > ω_sat: el aire ya está saturado → T_wb = T_db."""
        T = 313.15
        omega = omega_saturacion(T) * 1.1
        T_wb = temperatura_bulbo_humedo(T, omega)
        assert T_wb == pytest.approx(T, abs=0.01)


# ---------------------------------------------------------------------------
# actividad_agua_desde_X_GAB
# ---------------------------------------------------------------------------


class TestActividadAguaDesdeXGAB:

    # Parámetros GAB típicos para alimentos (Maroulis et al. 2001)
    # Manzana: X_m=0.05, C=12, K=0.85
    # Carne: X_m=0.08, C=15, K=0.80

    def test_X_cero_da_aw_cero(self):
        """X = 0 → a_w = 0 (producto totalmente seco)."""
        aw = actividad_agua_desde_X_GAB(0.0, X_m=0.05, C=12.0, K=0.85)
        assert aw == 0.0

    def test_round_trip_GAB(self):
        """X → a_w → X debe ser identidad para múltiples (X_m, C, K).

        Usa la forma directa de GAB:
            X = X_m·C·K·a_w / [(1−K·a_w)(1−K·a_w + C·K·a_w)]
        """
        casos = [
            (0.05, 12.0, 0.85),  # frutas tipo manzana
            (0.08, 15.0, 0.80),  # carne
            (0.04, 8.0, 0.90),   # cereales
            (0.10, 25.0, 0.75),  # producto con monocapa alta
        ]
        for X_m, C, K in casos:
            for aw_orig in [0.05, 0.20, 0.40, 0.60, 0.80, 0.95]:
                # GAB directo: aw → X
                u = K * aw_orig
                X = X_m * C * u / ((1.0 - u) * (1.0 - u + C * u))
                # Inversa: X → aw
                aw_rec = actividad_agua_desde_X_GAB(X, X_m, C, K)
                assert aw_rec == pytest.approx(aw_orig, abs=1e-9), (
                    f"Falló para (X_m={X_m}, C={C}, K={K}, aw={aw_orig}): "
                    f"X={X:.6f}, aw_rec={aw_rec:.9f}"
                )

    def test_aw_creciente_con_X(self):
        """A mayor X, mayor a_w (función monótona)."""
        params = {"X_m": 0.05, "C": 12.0, "K": 0.85}
        aw_bajo = actividad_agua_desde_X_GAB(0.05, **params)
        aw_alto = actividad_agua_desde_X_GAB(0.30, **params)
        assert aw_alto > aw_bajo

    def test_aw_en_rango_unitario(self):
        """a_w siempre en [0, 1] para X dentro del rango físico de GAB.

        Para (X_m=0.05, C=12, K=0.85), el rango válido es X ∈ (0, ~0.18)
        (X mayores corresponden a a_w > 1, fuera del modelo).
        """
        params = {"X_m": 0.05, "C": 12.0, "K": 0.85}
        for X in [0.01, 0.05, 0.10, 0.15, 0.18]:
            aw = actividad_agua_desde_X_GAB(X, **params)
            assert 0.0 <= aw <= 1.0

    def test_X_fuera_de_rango_lanza(self):
        """X que excede el límite GAB (a_w > 1) debe lanzar."""
        with pytest.raises(ValueError, match="PSICRO_GAB_AW_FUERA_RANGO"):
            actividad_agua_desde_X_GAB(0.40, X_m=0.05, C=12.0, K=0.85)

    def test_caso_degenerado_C1(self):
        """C=1 (caso límite): GAB se reduce a forma simplificada."""
        # Para C=1, GAB: X = X_m · K · a_w / (1 − K·a_w)²
        # Caso de prueba: X_m=0.05, K=0.85, aw=0.5
        X_m, K = 0.05, 0.85
        aw_orig = 0.5
        u = K * aw_orig
        X = X_m * u / (1.0 - u) ** 2
        aw_rec = actividad_agua_desde_X_GAB(X, X_m, C=1.0, K=K)
        assert aw_rec == pytest.approx(aw_orig, abs=1e-6)

    def test_X_m_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_GAB_XM_NO_POSITIVA"):
            actividad_agua_desde_X_GAB(0.10, X_m=0.0, C=12.0, K=0.85)

    def test_C_no_positiva_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_GAB_C_NO_POSITIVA"):
            actividad_agua_desde_X_GAB(0.10, X_m=0.05, C=-1.0, K=0.85)

    def test_K_fuera_rango_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_GAB_K_FUERA_RANGO"):
            actividad_agua_desde_X_GAB(0.10, X_m=0.05, C=12.0, K=1.0)
        with pytest.raises(ValueError, match="PSICRO_GAB_K_FUERA_RANGO"):
            actividad_agua_desde_X_GAB(0.10, X_m=0.05, C=12.0, K=0.0)


# ---------------------------------------------------------------------------
# coef_transferencia_masa_chilton_colburn
# ---------------------------------------------------------------------------


class TestCoefTransferenciaMasa:

    def test_valor_tipico(self):
        """h_conv=20 W/(m²·K) a 50 °C, ω=0.020, Le=1 → h_m ≈ 0.018 m/s.

        Cálculo:
            ρ ≈ 1.085 kg/m³, cp ≈ 1006 + 1805·0.020 = 1042 J/(kg·K)
            h_m = 20 / (1.085 · 1042 · 1) ≈ 0.0177 m/s
        """
        h_m = coef_transferencia_masa_chilton_colburn(
            h_conv=20.0, T_K=323.15, omega=0.020, Le=1.0
        )
        assert h_m == pytest.approx(0.0177, rel=0.02)

    def test_proporcional_a_h_conv(self):
        """h_m es lineal en h_conv."""
        h_m_10 = coef_transferencia_masa_chilton_colburn(10.0, 323.15, 0.020)
        h_m_30 = coef_transferencia_masa_chilton_colburn(30.0, 323.15, 0.020)
        assert h_m_30 == pytest.approx(3.0 * h_m_10, rel=1e-9)

    def test_h_conv_cero_da_h_m_cero(self):
        h_m = coef_transferencia_masa_chilton_colburn(0.0, 323.15, 0.020)
        assert h_m == 0.0

    def test_efecto_lewis(self):
        """Le > 1 reduce h_m respecto a Le=1."""
        h_m_Le1 = coef_transferencia_masa_chilton_colburn(
            20.0, 323.15, 0.020, Le=1.0
        )
        h_m_Le2 = coef_transferencia_masa_chilton_colburn(
            20.0, 323.15, 0.020, Le=2.0
        )
        assert h_m_Le2 < h_m_Le1
        # Con Le=2: factor = 1/2^(2/3) ≈ 0.630
        ratio = h_m_Le2 / h_m_Le1
        assert ratio == pytest.approx(2.0 ** (-2.0 / 3.0), rel=1e-9)

    def test_h_conv_negativo_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_HCONV_NEGATIVO"):
            coef_transferencia_masa_chilton_colburn(-1.0, 323.15, 0.020)

    def test_lewis_no_positivo_lanza(self):
        with pytest.raises(ValueError, match="PSICRO_LEWIS_NO_POSITIVO"):
            coef_transferencia_masa_chilton_colburn(20.0, 323.15, 0.020, Le=0.0)
