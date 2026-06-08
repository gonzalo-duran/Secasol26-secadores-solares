"""Tests unitarios para calculos/colector_calc.py — Colector Tipo 1.

Estrategia de testing
---------------------
Los tests se organizan en tres niveles:

1. Tests de funciones auxiliares (sin dependencia del core):
   - Correlaciones físicas verificadas contra valores de referencia calculados
     a mano o extraídos de bibliografía.
   - Invariantes físicas (e.g., h > 0, T_cie < T_amb, conservación de energía).

2. Tests del sistema algebraico (_sistema_nodo):
   - Verificación de balance en condiciones conocidas.
   - Simetría y límites físicos.

3. Tests de integración (calcular_colector_tipo1):
   - No dependen del core completo: se usan stubs mínimos de Colector.
   - Verifican conservación de energía, monotonía de T_f(x), y advertencias.

Convenciones
------------
- Todas las temperaturas en Kelvin.
- Tolerancias relativas 1e-4 para correlaciones; absolutas 0.1 K para perfiles.
- Los stubs de Colector replican solo los campos accedidos por la función.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.colector_calc import (
    _T_cielo_K,
    _h_viento_W_m2K,
    _diametro_hidraulico_m,
    _T_bot_K,
    _em_efectiva_paralelas,
    _sistema_nodo,
    CP_AIRE,
    K_AIRE,
    MU_AIRE,
    PR_AIRE,
    R_AIRE,
    RHO_AIRE_REF,
    SIGMA_SB,
    V_VIENTO_LIMITE_MCADAMS,
)
from calculos.correlaciones_nusselt import calcular_h_int

# ---------------------------------------------------------------------------
# Wrappers de test — interfaz legada de funciones refactorizadas en Sesión 12
# ---------------------------------------------------------------------------


def _h_int_forzado_W_m2K(m_kgs: float, alto_m: float, W_m: float, L_m: float):
    """Wrapper de test: calcula h_int para flujo forzado a partir de caudal másico."""
    Dh = _diametro_hidraulico_m(alto_m, W_m)
    v = m_kgs / (RHO_AIRE_REF * alto_m * W_m)
    Re = RHO_AIRE_REF * v * Dh / MU_AIRE
    h, _, _, regimen, _ = calcular_h_int(
        Re=Re,
        Pr=PR_AIRE,
        Dh_m=Dh,
        L_m=L_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",
        modo="forzado",
    )
    return h, Re, regimen


def _h_int_natural_W_m2K(
    T_hot_K: float, T_cold_K: float, alto_m: float, theta_deg: float, P_Pa: float
) -> float:
    """Wrapper de test: calcula h_int para convección natural en cavidad inclinada.

    Usa alto_m como longitud característica (correlación de Hollands para cavidades).
    """
    T_mean = (T_hot_K + T_cold_K) / 2.0
    dT = max(T_hot_K - T_cold_K, 0.0)
    rho = P_Pa / (R_AIRE * T_mean)
    g = 9.80665
    Ra = g / T_mean * (rho**2 * CP_AIRE / (MU_AIRE * K_AIRE)) * dT * alto_m**3
    h, _, _, _, _ = calcular_h_int(
        Re=0.0,
        Pr=PR_AIRE,
        Dh_m=alto_m,
        L_m=alto_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",
        modo="natural",
        Ra=Ra,
        theta_deg=theta_deg,
    )
    return h


# =============================================================================
# Helpers
# =============================================================================


def casi_igual(a, b, rtol=1e-4, atol=0.0):
    """Verificación de igualdad aproximada con mensaje informativo."""
    return abs(a - b) <= atol + rtol * abs(b)


# =============================================================================
# 1. _T_cielo_K — correlación de Swinbank
# =============================================================================


class TestTCieloSwinbank:
    """Temperatura de cielo — Swinbank (1963)."""

    def test_formula_exacta_300K(self):
        """T_cie = 0.0552 * 300^1.5 = 287.06 K."""
        esperado = 0.0552 * 300.0**1.5
        assert casi_igual(_T_cielo_K(300.0), esperado)

    def test_T_cie_menor_que_T_amb_rango_habitual(self):
        """T_cie < T_amb para temperaturas ambiente típicas (< 320 K / 47°C).

        Nota: la correlación de Swinbank cruza T_amb ≈ 327 K (54°C), valor
        que no se alcanza en condiciones reales de uso del colector. Para el
        rango de trabajo del software (T_amb < 320 K) la invariante se cumple.
        """
        for T in [270.0, 280.0, 290.0, 300.0, 310.0, 318.0]:
            assert _T_cielo_K(T) < T, f"T_cie={_T_cielo_K(T):.1f} ≥ T_amb={T:.1f} K"

    def test_monotona(self):
        """A mayor T_amb, mayor T_cie."""
        T_vals = [270.0, 280.0, 290.0, 300.0, 310.0]
        T_cie_vals = [_T_cielo_K(T) for T in T_vals]
        assert all(T_cie_vals[i] < T_cie_vals[i + 1] for i in range(len(T_cie_vals) - 1))

    def test_rango_tipico_salta(self):
        """Para T_amb entre 15°C y 35°C (288–308 K), T_cie entre 260–300 K."""
        for T in [288.15, 298.15, 308.15]:
            T_cie = _T_cielo_K(T)
            assert 250.0 < T_cie < 302.0, f"T_cie={T_cie:.1f} fuera de rango para T_amb={T:.1f} K"


# =============================================================================
# 2. _h_viento_W_m2K — correlación de McAdams
# =============================================================================


class TestHVientoMcAdams:
    """Coeficiente convectivo de viento — McAdams (1954)."""

    def test_formula_exacta_3ms(self):
        """h = 5.7 + 3.8 * 3.0 = 17.1 W/m²·K."""
        h, adv = _h_viento_W_m2K(3.0)
        assert casi_igual(h, 17.1)
        assert adv == []

    def test_formula_exacta_0ms(self):
        """h = 5.7 W/m²·K para viento nulo."""
        h, adv = _h_viento_W_m2K(0.0)
        assert casi_igual(h, 5.7)

    def test_sin_advertencia_bajo_limite(self):
        """Sin advertencia para v = 4.9 m/s."""
        _, adv = _h_viento_W_m2K(4.9)
        assert adv == []

    def test_advertencia_exactamente_en_limite(self):
        """Advertencia exactamente en v = 5.0 m/s."""
        _, adv = _h_viento_W_m2K(V_VIENTO_LIMITE_MCADAMS)
        assert len(adv) == 1
        assert "COL_VIENTO_FUERA_RANGO_MCADAMS" in adv[0]

    def test_advertencia_sobre_limite(self):
        """Advertencia para v = 8.0 m/s."""
        _, adv = _h_viento_W_m2K(8.0)
        assert len(adv) == 1

    def test_h_positivo_siempre(self):
        """h > 0 para cualquier velocidad no negativa."""
        for v in [0.0, 0.5, 2.0, 5.0, 10.0]:
            h, _ = _h_viento_W_m2K(v)
            assert h > 0.0

    def test_monotono(self):
        """h crece con v."""
        v_vals = [0.0, 1.0, 2.0, 3.0, 4.0]
        h_vals = [_h_viento_W_m2K(v)[0] for v in v_vals]
        assert all(h_vals[i] < h_vals[i + 1] for i in range(len(h_vals) - 1))


# =============================================================================
# 3. _diametro_hidraulico_m
# =============================================================================


class TestDiametroHidraulico:
    """Diámetro hidráulico de canal rectangular."""

    def test_canal_cuadrado(self):
        """Para canal cuadrado a×a: Dh = a."""
        a = 0.05
        assert casi_igual(_diametro_hidraulico_m(a, a), a)

    def test_canal_muy_ancho(self):
        """Para W >> alto: Dh → 2 * alto."""
        alto = 0.02
        W = 1.0  # W >> alto
        Dh = _diametro_hidraulico_m(alto, W)
        assert casi_igual(Dh, 2 * alto, rtol=0.02)  # 2% tolerancia

    def test_formula_exacta(self):
        """Caso: alto=0.05, W=1.0: Dh = 2*0.05*1.0/(0.05+1.0) = 0.09524."""
        Dh = _diametro_hidraulico_m(0.05, 1.0)
        assert casi_igual(Dh, 2 * 0.05 * 1.0 / (0.05 + 1.0))

    def test_positivo(self):
        """Dh > 0 siempre."""
        assert _diametro_hidraulico_m(0.03, 0.8) > 0.0


# =============================================================================
# 4. _h_int_forzado_W_m2K — regímenes de flujo
# =============================================================================


class TestHIntForzado:
    """Coeficiente convectivo interno para flujo forzado."""

    # Parámetros de referencia: canal típico de colector solar de aire
    ALTO = 0.05  # m
    W = 1.0  # m
    L = 2.0  # m

    def _m_para_Re(self, Re_objetivo: float) -> float:
        """Devuelve m_punto [kg/s] para alcanzar Re_objetivo en el canal."""
        Dh = _diametro_hidraulico_m(self.ALTO, self.W)
        A = self.ALTO * self.W
        v = Re_objetivo * MU_AIRE / (RHO_AIRE_REF * Dh)
        return RHO_AIRE_REF * v * A

    def test_regimen_laminar(self):
        """Re < 2300 → régimen laminar, Nu = 5.385."""
        m = self._m_para_Re(1000.0)
        h, Re, regimen = _h_int_forzado_W_m2K(m, self.ALTO, self.W, self.L)
        assert regimen == "laminar"
        assert Re < 2300.0
        assert h > 0.0

    def test_regimen_transicion(self):
        """2300 < Re < 10000 → régimen transición (Gnielinski)."""
        m = self._m_para_Re(5000.0)
        h, Re, regimen = _h_int_forzado_W_m2K(m, self.ALTO, self.W, self.L)
        assert regimen == "transicion"
        assert 2300.0 < Re < 10000.0
        assert h > 0.0

    def test_regimen_turbulento(self):
        """Re > 10000 → régimen turbulento (Dittus-Boelter)."""
        m = self._m_para_Re(15000.0)
        h, Re, regimen = _h_int_forzado_W_m2K(m, self.ALTO, self.W, self.L)
        assert regimen == "turbulento"
        assert Re > 10000.0
        assert h > 0.0

    def test_h_turbulento_mayor_que_laminar(self):
        """h en turbulento debe ser significativamente mayor que en laminar."""
        m_lam = self._m_para_Re(500.0)
        m_tur = self._m_para_Re(20000.0)
        h_lam, _, _ = _h_int_forzado_W_m2K(m_lam, self.ALTO, self.W, self.L)
        h_tur, _, _ = _h_int_forzado_W_m2K(m_tur, self.ALTO, self.W, self.L)
        assert h_tur > 3 * h_lam

    def test_continuidad_en_frontera_laminar_transicion(self):
        """h no debe saltar abruptamente en Re = 2300 (continuidad aproximada)."""
        m_antes = self._m_para_Re(2290.0)
        m_despues = self._m_para_Re(2310.0)
        h_antes, _, _ = _h_int_forzado_W_m2K(m_antes, self.ALTO, self.W, self.L)
        h_despues, _, _ = _h_int_forzado_W_m2K(m_despues, self.ALTO, self.W, self.L)
        # El salto no debe ser mayor al 50% (Gnielinski vs Nu=5.385 en frontera)
        salto_relativo = abs(h_despues - h_antes) / h_antes
        assert (
            salto_relativo < 0.5
        ), f"Salto de h en frontera laminar/transición: {salto_relativo:.1%}"


# =============================================================================
# 5. _h_int_natural_W_m2K — convección natural
# =============================================================================


class TestHIntNatural:
    """Coeficiente convectivo interno para convección natural — Hollands (1976)."""

    P_REF = 101325.0  # Pa

    def test_sin_diferencia_de_temperatura(self):
        """ΔT = 0 → solo conducción (h = k/alto)."""
        alto = 0.05
        T = 323.15
        h = _h_int_natural_W_m2K(T, T, alto, 45.0, self.P_REF)
        assert casi_igual(h, K_AIRE / alto)

    def test_h_positivo(self):
        """h > 0 para ΔT > 0."""
        h = _h_int_natural_W_m2K(350.0, 300.0, 0.05, 45.0, self.P_REF)
        assert h > 0.0

    def test_h_crece_con_delta_T(self):
        """Mayor ΔT → mayor Ra → mayor h."""
        h1 = _h_int_natural_W_m2K(320.0, 300.0, 0.05, 45.0, self.P_REF)
        h2 = _h_int_natural_W_m2K(340.0, 300.0, 0.05, 45.0, self.P_REF)
        assert h2 >= h1

    def test_pendiente_cero_horizontal(self):
        """Para colector horizontal (θ=0°), la correlación es válida."""
        h = _h_int_natural_W_m2K(350.0, 300.0, 0.05, 0.0, self.P_REF)
        assert h > 0.0

    def test_rango_tipico(self):
        """h en convección natural debe estar en rango físico razonable [1, 20] W/m²K."""
        h = _h_int_natural_W_m2K(340.0, 295.0, 0.05, 45.0, self.P_REF)
        assert 1.0 < h < 20.0, f"h={h:.2f} fuera del rango típico"


# =============================================================================
# 6. _T_bot_K — temperatura de fondo
# =============================================================================


class TestTBot:
    """Temperatura cara externa del fondo del colector."""

    def test_entre_T_abs_y_T_amb(self):
        """T_amb ≤ T_bot ≤ T_abs (el fondo está entre ambiente y absorbedor)."""
        T_abs = 350.0
        T_amb = 300.0
        T_bot = _T_bot_K(T_abs, T_amb, k_ais_W_mK=0.04, esp_ais_m=0.05, h_wind_W_m2K=15.0)
        assert T_amb <= T_bot <= T_abs

    def test_aislante_perfecto(self):
        """Con k_ais → ∞ (conductividad infinita), T_bot → T_abs."""
        T_bot = _T_bot_K(350.0, 300.0, k_ais_W_mK=1e6, esp_ais_m=0.05, h_wind_W_m2K=15.0)
        assert casi_igual(T_bot, 350.0, rtol=1e-3)

    def test_aislante_nulo(self):
        """Con esp_ais → ∞ (resistencia infinita), T_bot → T_amb."""
        T_bot = _T_bot_K(350.0, 300.0, k_ais_W_mK=0.04, esp_ais_m=1e6, h_wind_W_m2K=15.0)
        assert casi_igual(T_bot, 300.0, rtol=1e-3)

    def test_balance_verificado(self):
        """El resultado debe satisfacer el balance: U_ais*(T_abs-T_bot) = h_wind*(T_bot-T_amb)."""
        T_abs, T_amb = 350.0, 300.0
        k_ais, esp_ais, h_wind = 0.04, 0.05, 12.0
        T_bot = _T_bot_K(T_abs, T_amb, k_ais, esp_ais, h_wind)
        U_ais = k_ais / esp_ais
        flujo_ais = U_ais * (T_abs - T_bot)
        flujo_conv = h_wind * (T_bot - T_amb)
        assert casi_igual(flujo_ais, flujo_conv, rtol=1e-6)


# =============================================================================
# 7. _em_efectiva_paralelas
# =============================================================================


class TestEmEfectiva:
    """Emisividad efectiva para superficies paralelas (F=1)."""

    def test_formula_exacta(self):
        """1/em_eff = 1/0.9 + 1/0.95 - 1."""
        em_cub, em_abs = 0.9, 0.95
        esperado = 1.0 / (1 / em_cub + 1 / em_abs - 1)
        assert casi_igual(_em_efectiva_paralelas(em_cub, em_abs), esperado)

    def test_menor_que_minimo(self):
        """em_eff < min(em_cub, em_abs) siempre."""
        em_cub, em_abs = 0.85, 0.92
        em_eff = _em_efectiva_paralelas(em_cub, em_abs)
        assert em_eff < min(em_cub, em_abs)

    def test_simetrico(self):
        """Intercambiar cubierta y absorbedor no cambia el resultado."""
        em_a, em_b = 0.88, 0.95
        assert casi_igual(
            _em_efectiva_paralelas(em_a, em_b),
            _em_efectiva_paralelas(em_b, em_a),
        )

    def test_ambas_negras(self):
        """Para superficies negras (em=1): em_eff = 1."""
        assert casi_igual(_em_efectiva_paralelas(1.0, 1.0), 1.0)


# =============================================================================
# 8. _sistema_nodo — balances algebraicos
# =============================================================================


class TestSistemaNodo:
    """Sistema algebraico de balance por nodo."""

    # Condiciones de referencia para todos los tests de este grupo
    PARAMS_REF = dict(
        T_f_K=330.0,
        T_amb_K=300.0,
        T_cie_K=_T_cielo_K(300.0),
        I_g_W_m2=800.0,
        h_wind=15.0,
        h_int=10.0,
        k_cub=0.9,  # vidrio
        esp_cub=0.004,
        em_cub=0.88,
        k_ais=0.04,  # lana de vidrio
        esp_ais=0.05,
        em_abs=0.95,
        tau_cub=0.85,
        alfa_abs=0.92,
        W_m=1.0,
        W_abs_m=1.0,
    )

    def _residuos(self, T_cub_e, T_cub_i, T_abs, **kwargs):
        """Evalúa _sistema_nodo con los parámetros de referencia."""
        p = {**self.PARAMS_REF, **kwargs}
        return _sistema_nodo(
            np.array([T_cub_e, T_cub_i, T_abs]),
            p["T_f_K"],
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            p["h_int"],
            p["k_cub"],
            p["esp_cub"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais"],
            p["em_abs"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
        )

    def test_solucion_satisface_balances(self):
        """La solución de fsolve debe hacer residuos ≈ 0."""
        from scipy.optimize import fsolve

        p = self.PARAMS_REF
        T_g = p["T_amb_K"] + 20.0
        guess = np.array([T_g, T_g + 5.0, T_g + 30.0])
        sol = fsolve(
            _sistema_nodo,
            guess,
            args=(
                p["T_f_K"],
                p["T_amb_K"],
                p["T_cie_K"],
                p["I_g_W_m2"],
                p["h_wind"],
                p["h_int"],
                p["k_cub"],
                p["esp_cub"],
                p["em_cub"],
                p["k_ais"],
                p["esp_ais"],
                p["em_abs"],
                p["tau_cub"],
                p["alfa_abs"],
                p["W_m"],
                p["W_abs_m"],
            ),
            xtol=1e-10,
        )
        residuos = self._residuos(*sol)
        assert np.allclose(residuos, 0.0, atol=1e-4), f"Residuos: {residuos}"

    def test_T_abs_mayor_que_T_fluido(self):
        """El absorbedor debe estar más caliente que el fluido."""
        from scipy.optimize import fsolve

        p = self.PARAMS_REF
        T_g = p["T_amb_K"] + 20.0
        sol = fsolve(
            _sistema_nodo,
            np.array([T_g, T_g + 5.0, T_g + 30.0]),
            args=(
                p["T_f_K"],
                p["T_amb_K"],
                p["T_cie_K"],
                p["I_g_W_m2"],
                p["h_wind"],
                p["h_int"],
                p["k_cub"],
                p["esp_cub"],
                p["em_cub"],
                p["k_ais"],
                p["esp_ais"],
                p["em_abs"],
                p["tau_cub"],
                p["alfa_abs"],
                p["W_m"],
                p["W_abs_m"],
            ),
        )
        T_cub_e, T_cub_i, T_abs = sol
        assert T_abs > p["T_f_K"], "Absorbedor debe estar más caliente que el fluido"

    def test_sin_radiacion_T_abs_baja(self):
        """Sin irradiancia solar (I_g=0), el gradiente dT_f/dx es casi nulo.

        Con I_g=800 W/m² el absorbedor está significativamente más caliente
        que el fluido (T_abs - T_f > 10 K). Con I_g=0 y T_f = T_amb, el
        absorbedor no puede estar mucho más caliente que T_f (el balance se
        invierte: el absorbedor pierde calor al cielo).

        Verificamos directamente la diferencia T_abs - T_f que impulsa el
        calentamiento del fluido.
        """
        from scipy.optimize import fsolve

        def resolver_con_guess_robusto(I_g: float, T_f: float) -> np.ndarray:
            """Usa múltiples guesses y devuelve la solución con menor residuo."""
            p = {**self.PARAMS_REF, "I_g_W_m2": I_g, "T_f_K": T_f}
            args = (
                p["T_f_K"],
                p["T_amb_K"],
                p["T_cie_K"],
                p["I_g_W_m2"],
                p["h_wind"],
                p["h_int"],
                p["k_cub"],
                p["esp_cub"],
                p["em_cub"],
                p["k_ais"],
                p["esp_ais"],
                p["em_abs"],
                p["tau_cub"],
                p["alfa_abs"],
                p["W_m"],
                p["W_abs_m"],
            )
            mejor_sol = None
            menor_residuo = np.inf
            T_amb = p["T_amb_K"]
            for delta in [5.0, 15.0, 30.0, 50.0]:
                guess = np.array([T_amb + delta * 0.3, T_amb + delta * 0.5, T_amb + delta])
                sol, _, ier, _ = fsolve(
                    _sistema_nodo, guess, args=args, full_output=True, xtol=1e-10
                )
                res = np.linalg.norm(_sistema_nodo(sol, *args))
                if ier == 1 and res < menor_residuo:
                    menor_residuo = res
                    mejor_sol = sol
            return mejor_sol if mejor_sol is not None else sol

        T_amb = self.PARAMS_REF["T_amb_K"]
        sol_sin = resolver_con_guess_robusto(0.0, T_amb)
        sol_con = resolver_con_guess_robusto(800.0, self.PARAMS_REF["T_f_K"])

        T_abs_sin = float(sol_sin[2])
        T_abs_con = float(sol_con[2])
        T_f_con = float(self.PARAMS_REF["T_f_K"])

        # Con sol pleno: absorbedor significativamente más caliente que fluido
        assert T_abs_con > T_f_con + 10.0, (
            f"Con I_g=800: T_abs={T_abs_con:.1f} K, T_f={T_f_con:.1f} K — "
            "diferencia insuficiente para calentar el fluido"
        )
        # Sin sol: absorbedor mucho más frío que con sol
        assert (
            T_abs_sin < T_abs_con - 30.0
        ), f"I_g=0: T_abs={T_abs_sin:.1f} K; I_g=800: T_abs={T_abs_con:.1f} K"

    def test_T_cub_e_menor_que_T_abs(self):
        """La cara externa de la cubierta debe ser más fría que el absorbedor."""
        from scipy.optimize import fsolve

        p = self.PARAMS_REF
        T_g = p["T_amb_K"] + 20.0
        sol = fsolve(
            _sistema_nodo,
            np.array([T_g, T_g + 5.0, T_g + 30.0]),
            args=(
                p["T_f_K"],
                p["T_amb_K"],
                p["T_cie_K"],
                p["I_g_W_m2"],
                p["h_wind"],
                p["h_int"],
                p["k_cub"],
                p["esp_cub"],
                p["em_cub"],
                p["k_ais"],
                p["esp_ais"],
                p["em_abs"],
                p["tau_cub"],
                p["alfa_abs"],
                p["W_m"],
                p["W_abs_m"],
            ),
        )
        T_cub_e, T_cub_i, T_abs = sol
        assert T_cub_e < T_abs, "Cubierta externa debe ser más fría que absorbedor"


# =============================================================================
# 9. Doble cubierta (n_cubiertas = 2)
# =============================================================================


class TestDobleCubierta:
    """Verifica que n_cubiertas=2 mejore el desempeño en línea con la física."""

    @staticmethod
    def _col(
        n_cubiertas: int,
        gap_m: float = 0.025,
        id_cub: str = "vidrio_comun",
        id_pla: str = "aluminio_tinox",
    ):
        from core.colector import Colector, ColectorUnidad, BancoColectores

        return Colector(
            unidad=ColectorUnidad(
                ancho_m=1.0,
                largo_m=2.0,
                n_cubiertas=n_cubiertas,
                espaciado_entre_cubiertas_m=gap_m,
                id_cubierta=id_cub,
                id_placa=id_pla,
            ),
            banco=BancoColectores(),
        )

    @staticmethod
    def _correr(col, dT_in_K: float = 0.0):
        from calculos.colector_calc import calcular_colector_tipo1

        T_amb = 293.15
        return calcular_colector_tipo1(
            colector=col,
            T_amb_K=T_amb,
            I_g_W_m2=800.0,
            v_viento_ms=2.0,
            P_amb_Pa=101325.0,
            T_entrada_K=T_amb + dT_in_K,
            pendiente_deg=30.0,
        )

    def test_eta_n2_mayor_que_n1(self):
        """Doble cubierta reduce pérdidas → η debe aumentar."""
        r1 = self._correr(self._col(1))
        r2 = self._correr(self._col(2))
        assert (
            r2.eta_termica > r1.eta_termica
        ), f"η(n=2)={r2.eta_termica:.3f} no es mayor que η(n=1)={r1.eta_termica:.3f}"

    def test_T_cub_e_n2_menor_que_n1(self):
        """Con doble cubierta la cara externa queda más fría (mejor aislada)."""
        r1 = self._correr(self._col(1))
        r2 = self._correr(self._col(2))
        Te1 = float(np.mean(r1.T_cub_e_K))
        Te2 = float(np.mean(r2.T_cub_e_K))
        assert (
            Te2 < Te1
        ), f"T_cub_e(n=2)={Te2-273.15:.1f}°C debe ser menor que T_cub_e(n=1)={Te1-273.15:.1f}°C"

    def test_T_cub_i_n2_mayor_que_n1(self):
        """Con doble cubierta la cara interna queda más caliente (atrapada)."""
        r1 = self._correr(self._col(1))
        r2 = self._correr(self._col(2))
        Ti1 = float(np.mean(r1.T_cub_i_K))
        Ti2 = float(np.mean(r2.T_cub_i_K))
        assert (
            Ti2 > Ti1
        ), f"T_cub_i(n=2)={Ti2-273.15:.1f}°C debe ser mayor que T_cub_i(n=1)={Ti1-273.15:.1f}°C"

    def test_ganancia_mayor_a_alta_delta_T(self):
        """La ventaja de la doble cubierta crece con (T_in − T_amb)."""
        # Sin sobrecalentamiento de entrada
        r1_baja = self._correr(self._col(1), dT_in_K=0.0)
        r2_baja = self._correr(self._col(2), dT_in_K=0.0)
        # Con T_in elevada (mayor pérdida → más ventaja con 2 cubiertas)
        r1_alta = self._correr(self._col(1), dT_in_K=30.0)
        r2_alta = self._correr(self._col(2), dT_in_K=30.0)
        ganancia_baja = r2_baja.eta_termica - r1_baja.eta_termica
        ganancia_alta = r2_alta.eta_termica - r1_alta.eta_termica
        assert ganancia_alta > ganancia_baja, (
            f"Ganancia con ΔT alto ({ganancia_alta*100:.1f} pp) debe ser mayor que "
            f"con ΔT bajo ({ganancia_baja*100:.1f} pp)"
        )

    def test_temperaturas_fisicas(self):
        """Con doble cubierta el modelo debe converger a temperaturas físicas."""
        r = self._correr(self._col(2))
        T_amb = 293.15
        Te = float(np.mean(r.T_cub_e_K))
        Ti = float(np.mean(r.T_cub_i_K))
        Ta = float(np.mean(r.T_abs_K))
        # Monotonía física: T_amb ≤ T_cub_e ≤ T_cub_i ≤ T_abs
        assert T_amb - 5.0 < Te < Ti < Ta, (
            f"Monotonía violada: T_amb={T_amb-273.15:.1f}, T_cub_e={Te-273.15:.1f}, "
            f"T_cub_i={Ti-273.15:.1f}, T_abs={Ta-273.15:.1f}"
        )
        # T_abs en rango razonable bajo 800 W/m² y aire de paso
        assert 50 + 273.15 < Ta < 200 + 273.15, f"T_abs absurdo: {Ta-273.15:.1f}°C"


class TestCoefConveccionLocal:
    """h_int local (S36): realce de entrada + convección mixta, y continuidad."""

    def _col(self, v, largo):
        from core.colector import Colector, ColectorUnidad, BancoColectores

        u = ColectorUnidad(ancho_m=1.0, largo_m=largo, espaciado_m=0.025, velocidad_diseno_ms=v)
        return Colector(unidad=u, banco=BancoColectores())

    def _correr(self, v, largo):
        from calculos.colector_calc import calcular_colector_tipo1

        return calcular_colector_tipo1(
            self._col(v, largo),
            T_amb_K=300.0,
            I_g_W_m2=800.0,
            v_viento_ms=2.0,
            P_amb_Pa=101325.0,
            T_entrada_K=300.0,
            pendiente_deg=30.0,
        )

    def test_laminar_largo_supera_desarrollado_constante(self):
        """En colector largo laminar, h_int_medio supera el valor desarrollado
        de propiedades constantes (~Nu=5.385·k/Dh ≈ 3.1), por entrada + mixta."""
        r = self._correr(v=0.54, largo=10.0)  # ṁ≈0.016 kg/s, Re~1500 laminar
        Dh = _diametro_hidraulico_m(0.025, 1.0)
        h_desarrollado_const = 5.385 * K_AIRE / Dh
        assert r.regimen_flujo == "laminar"
        assert r.h_int_medio > h_desarrollado_const

    def test_perfil_fluido_monotono_y_continuo(self):
        """El perfil T_fluido(x) crece monótonamente y sin saltos espurios."""
        for v, largo in [(10.0, 10.0), (0.54, 10.0)]:
            r = self._correr(v, largo)
            dTf = np.diff(r.T_fluido_K)
            assert np.all(dTf >= -1e-6), f"perfil no monótono (v={v})"
            # salto entre nodos contiguos acotado (continuidad del h local)
            assert float(np.max(np.abs(dTf))) < 5.0

    def test_convergencia_ambos_regimenes(self):
        """Converge tanto en turbulento (10 m/s) como en laminar (bajo caudal)."""
        assert self._correr(10.0, 2.5).convergencia_ok
        assert self._correr(0.54, 2.5).convergencia_ok


# =============================================================================
# Punto de entrada para ejecución directa
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
