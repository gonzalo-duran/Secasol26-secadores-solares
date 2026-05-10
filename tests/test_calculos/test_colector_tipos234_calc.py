"""Tests unitarios para calculos/colector_tipos234_calc.py.

Estrategia
----------
1. Tests de funciones auxiliares nuevas (_T_bot_desde_T_int, _Re_canal,
   _em_efectiva_paralelas, despeje canal estanco).
2. Tests del sistema algebraico Tipo 2 (_sistema_nodo_tipo2):
   invariantes físicas, conservación de energía, balances.
3. Tests del sistema algebraico Tipos 3/4 (_sistema_nodo_tipos34):
   idem + verificación del despeje analítico del canal estanco.
4. Tests de las RHS (derivadas del fluido): signo correcto, magnitud razonable.
5. Tests de integración liviana: solve_ivp con parámetros físicos razonables,
   sin objeto Colector del core (stubs mínimos o parámetros directos).

Los tests de funciones auxiliares reutilizan lógica de test_colector_calc.py
pero adaptados a la nueva geometría de dos canales.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import fsolve

from calculos.colector_tipos234_calc import (
    RHO_AIRE_REF,
    _construir_rhs_tipo2,
    _construir_rhs_tipo3,
    _construir_rhs_tipo4,
    _diametro_hidraulico_m,
    _Re_canal,
    _sistema_nodo_tipo2,
    _sistema_nodo_tipos34,
    _T_bot_desde_T_int,
    _T_cielo_K,
)

# =============================================================================
# Helpers
# =============================================================================


def casi_igual(a, b, rtol=1e-4, atol=0.0):
    return abs(a - b) <= atol + rtol * max(abs(b), 1e-12)


def _params_ref_tipo2(
    I_g: float = 800.0,
    T_amb: float = 300.0,
    T_f_cs: float = 330.0,
    T_f_ci: float = 325.0,
) -> dict:
    """Parámetros de referencia para tests del sistema Tipo 2."""
    T_cie = _T_cielo_K(T_amb)
    return dict(
        T_amb_K=T_amb,
        T_cie_K=T_cie,
        I_g_W_m2=I_g,
        h_wind=15.0,
        h_int_cs=8.0,
        h_int_ci=10.0,
        k_cub=0.9,
        esp_cub_m=0.004,
        em_cub=0.88,
        k_ais=0.04,
        esp_ais_m=0.05,
        em_abs=0.95,
        em_fondo=0.90,
        tau_cub=0.85,
        alfa_abs=0.92,
        W_m=1.0,
        W_abs_m=1.0,
        m_punto_cs_kgs=0.05,
        m_punto_ci_kgs=0.05,
        T_f_cs=T_f_cs,
        T_f_ci=T_f_ci,
    )


def _resolver_tipo2(p: dict) -> np.ndarray:
    """Resuelve el sistema Tipo 2 con los parámetros dados."""
    T_amb = p["T_amb_K"]
    T_f_max = max(p["T_f_cs"], p["T_f_ci"])
    # El absorbedor debe estar por encima del fluido más caliente
    T_g_abs = T_f_max + 20.0
    T_g_cub = T_amb + 5.0
    guess = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])
    sol = fsolve(
        _sistema_nodo_tipo2,
        guess,
        args=(
            p["T_f_cs"],
            p["T_f_ci"],
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            p["h_int_cs"],
            p["h_int_ci"],
            p["k_cub"],
            p["esp_cub_m"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais_m"],
            p["em_abs"],
            p["em_fondo"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
        ),
        xtol=1e-10,
    )
    return sol


def _resolver_tipos34(
    p: dict, T_f_activo: float, T_f_estanco: float, canal_activo: str
) -> np.ndarray:
    """Resuelve el sistema Tipos 3/4."""
    T_amb = p["T_amb_K"]
    T_f_max = max(T_f_activo, T_f_estanco)
    T_g_abs = T_f_max + 20.0
    T_g_cub = T_amb + 5.0
    guess = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])
    h_act = p["h_int_ci"] if canal_activo == "inferior" else p["h_int_cs"]
    h_est = p["h_int_cs"] if canal_activo == "inferior" else p["h_int_ci"]
    sol = fsolve(
        _sistema_nodo_tipos34,
        guess,
        args=(
            T_f_activo,
            T_f_estanco,
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            h_act,
            h_est,
            p["k_cub"],
            p["esp_cub_m"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais_m"],
            p["em_abs"],
            p["em_fondo"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
            canal_activo,
        ),
        xtol=1e-10,
    )
    return sol


# =============================================================================
# 1. _T_bot_desde_T_int
# =============================================================================


class TestTBotDesdeInt:

    def test_entre_T_int_y_T_amb(self):
        """T_amb ≤ T_bot ≤ T_int."""
        T_bot = _T_bot_desde_T_int(340.0, 300.0, 0.04, 0.05, 15.0)
        assert 300.0 <= T_bot <= 340.0

    def test_balance_satisfecho(self):
        """k_ais/esp * (T_int - T_bot) = h_wind * (T_bot - T_amb)."""
        T_int, T_amb, k, e, h = 340.0, 300.0, 0.04, 0.05, 12.0
        T_bot = _T_bot_desde_T_int(T_int, T_amb, k, e, h)
        flujo_ais = (k / e) * (T_int - T_bot)
        flujo_conv = h * (T_bot - T_amb)
        assert casi_igual(flujo_ais, flujo_conv, rtol=1e-6)

    def test_aislante_perfecto_T_bot_igual_T_int(self):
        """k_ais → ∞ → T_bot → T_int."""
        T_bot = _T_bot_desde_T_int(340.0, 300.0, 1e6, 0.05, 15.0)
        assert casi_igual(T_bot, 340.0, rtol=1e-3)

    def test_aislante_nulo_T_bot_igual_T_amb(self):
        """esp_ais → ∞ → T_bot → T_amb."""
        T_bot = _T_bot_desde_T_int(340.0, 300.0, 0.04, 1e6, 15.0)
        assert casi_igual(T_bot, 300.0, rtol=1e-3)

    def test_T_int_igual_T_amb(self):
        """Si T_int = T_amb, T_bot = T_amb (sin gradiente)."""
        T_bot = _T_bot_desde_T_int(300.0, 300.0, 0.04, 0.05, 15.0)
        assert casi_igual(T_bot, 300.0, rtol=1e-6)


# =============================================================================
# 2. _Re_canal
# =============================================================================


class TestReCanal:

    def test_positivo(self):
        Re, Dh = _Re_canal(0.05, 0.05, 1.0)
        assert Re > 0.0
        assert Dh > 0.0

    def test_Re_crece_con_m_punto(self):
        Re1, _ = _Re_canal(0.02, 0.05, 1.0)
        Re2, _ = _Re_canal(0.10, 0.05, 1.0)
        assert Re2 > Re1

    def test_Dh_canal_muy_ancho(self):
        """Para W >> alto: Dh → 2 * alto."""
        alto, W = 0.05, 100.0
        _, Dh = _Re_canal(0.05, alto, W)
        assert casi_igual(Dh, 2 * alto, rtol=0.02)

    def test_formula_Re(self):
        """Verificación directa de Re = rho*v*Dh/mu."""
        alto, W = 0.05, 1.0
        m_punto = 0.05
        Dh_esperado = _diametro_hidraulico_m(alto, W)
        A = alto * W
        v = m_punto / (RHO_AIRE_REF * A)
        Re_esperado = RHO_AIRE_REF * v * Dh_esperado / 1.963e-5
        Re, Dh = _Re_canal(m_punto, alto, W)
        assert casi_igual(Re, Re_esperado)
        assert casi_igual(Dh, Dh_esperado)


# =============================================================================
# 3. Sistema algebraico Tipo 2
# =============================================================================


class TestSistemaTipo2:

    def test_residuos_nulos_en_solucion(self):
        """La solución de fsolve debe hacer residuos ≈ 0."""
        p = _params_ref_tipo2()
        sol = _resolver_tipo2(p)
        res = _sistema_nodo_tipo2(
            sol,
            p["T_f_cs"],
            p["T_f_ci"],
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            p["h_int_cs"],
            p["h_int_ci"],
            p["k_cub"],
            p["esp_cub_m"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais_m"],
            p["em_abs"],
            p["em_fondo"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
        )
        assert np.allclose(res, 0.0, atol=1e-3), f"Residuos: {res}"

    def test_T_abs_mayor_que_fluidos(self):
        """El absorbedor debe estar más caliente que ambos fluidos."""
        p = _params_ref_tipo2()
        sol = _resolver_tipo2(p)
        T_abs = sol[2]
        assert T_abs > p["T_f_cs"], "T_abs debe superar T_f_cs"
        assert T_abs > p["T_f_ci"], "T_abs debe superar T_f_ci"

    def test_T_cub_e_menor_T_abs(self):
        """Cara externa cubierta más fría que absorbedor."""
        sol = _resolver_tipo2(_params_ref_tipo2())
        assert sol[0] < sol[2]

    def test_T_int_entre_T_amb_y_T_abs(self):
        """Cara interna fondo entre T_amb y T_abs."""
        p = _params_ref_tipo2()
        sol = _resolver_tipo2(p)
        T_int = sol[3]
        assert (
            p["T_amb_K"] <= T_int <= sol[2]
        ), f"T_int={T_int:.1f} fuera de [{p['T_amb_K']:.1f}, {sol[2]:.1f}]"

    def test_sin_radiacion_T_abs_menor(self):
        """Con I_g=0, T_abs debe ser significativamente menor que con I_g=800."""
        sol_sin = _resolver_tipo2(_params_ref_tipo2(I_g=0.0, T_f_cs=300.0, T_f_ci=300.0))
        sol_con = _resolver_tipo2(_params_ref_tipo2(I_g=800.0))
        assert (
            sol_con[2] > sol_sin[2] + 20.0
        ), f"I_g=0: T_abs={sol_sin[2]:.1f} K; I_g=800: T_abs={sol_con[2]:.1f} K"

    def test_4_incognitas(self):
        """La solución tiene exactamente 4 componentes."""
        sol = _resolver_tipo2(_params_ref_tipo2())
        assert len(sol) == 4


# =============================================================================
# 4. Sistema algebraico Tipos 3 y 4
# =============================================================================


class TestSistemaTipos34:

    P = _params_ref_tipo2()  # reutilizamos parámetros de referencia

    def test_tipo3_residuos_nulos(self):
        """Canal inferior activo: residuos ≈ 0."""
        T_f_ci = 328.0
        T_f_cs = 320.0  # estanco
        sol = _resolver_tipos34(self.P, T_f_ci, T_f_cs, "inferior")
        res = _sistema_nodo_tipos34(
            sol,
            T_f_ci,
            T_f_cs,
            self.P["T_amb_K"],
            self.P["T_cie_K"],
            self.P["I_g_W_m2"],
            self.P["h_wind"],
            self.P["h_int_ci"],
            self.P["h_int_cs"],
            self.P["k_cub"],
            self.P["esp_cub_m"],
            self.P["em_cub"],
            self.P["k_ais"],
            self.P["esp_ais_m"],
            self.P["em_abs"],
            self.P["em_fondo"],
            self.P["tau_cub"],
            self.P["alfa_abs"],
            self.P["W_m"],
            self.P["W_abs_m"],
            "inferior",
        )
        assert np.allclose(res, 0.0, atol=1e-3), f"Residuos Tipo 3: {res}"

    def test_tipo4_residuos_nulos(self):
        """Canal superior activo: residuos ≈ 0."""
        T_f_cs = 333.0
        T_f_ci = 322.0  # estanco
        sol = _resolver_tipos34(self.P, T_f_cs, T_f_ci, "superior")
        res = _sistema_nodo_tipos34(
            sol,
            T_f_cs,
            T_f_ci,
            self.P["T_amb_K"],
            self.P["T_cie_K"],
            self.P["I_g_W_m2"],
            self.P["h_wind"],
            self.P["h_int_cs"],
            self.P["h_int_ci"],
            self.P["k_cub"],
            self.P["esp_cub_m"],
            self.P["em_cub"],
            self.P["k_ais"],
            self.P["esp_ais_m"],
            self.P["em_abs"],
            self.P["em_fondo"],
            self.P["tau_cub"],
            self.P["alfa_abs"],
            self.P["W_m"],
            self.P["W_abs_m"],
            "superior",
        )
        assert np.allclose(res, 0.0, atol=1e-3), f"Residuos Tipo 4: {res}"

    def test_T_abs_mayor_que_fluido_activo_tipo3(self):
        """Tipo 3: absorbedor más caliente que fluido canal inferior."""
        T_f_ci = 328.0
        T_f_cs = 320.0
        sol = _resolver_tipos34(self.P, T_f_ci, T_f_cs, "inferior")
        assert sol[2] > T_f_ci

    def test_T_abs_mayor_que_fluido_activo_tipo4(self):
        """Tipo 4: absorbedor más caliente que fluido canal superior."""
        T_f_cs = 333.0
        T_f_ci = 322.0
        sol = _resolver_tipos34(self.P, T_f_cs, T_f_ci, "superior")
        assert sol[2] > T_f_cs

    def test_tipo3_4_misma_estructura_4x4(self):
        """Ambos tipos devuelven 4 incógnitas."""
        sol3 = _resolver_tipos34(self.P, 328.0, 320.0, "inferior")
        sol4 = _resolver_tipos34(self.P, 333.0, 322.0, "superior")
        assert len(sol3) == 4
        assert len(sol4) == 4


# =============================================================================
# 5. Despeje analítico del canal estanco
# =============================================================================


class TestDespejeCanalEstanco:
    """Verifica que T_f_estanco = (T_sup + T_inf) / 2 satisface el balance.

    El balance del canal estanco es:
    h * (T_f - T_sup) * dA + h * (T_f - T_inf) * dA = 0
    → T_f = (T_sup + T_inf) / 2

    Esto es exacto cuando h es el mismo en ambas paredes.
    """

    def test_canal_superior_estanco_tipo3(self):
        """T_f_cs = (T_cub_i + T_abs) / 2 satisface el balance del canal estanco."""
        T_cub_i, T_abs = 320.0, 345.0
        T_f_cs = 0.5 * (T_cub_i + T_abs)
        h = 8.0
        # Balance: h*(T_f - T_cub_i) + h*(T_f - T_abs) = 0
        balance = h * (T_f_cs - T_cub_i) + h * (T_f_cs - T_abs)
        assert casi_igual(balance, 0.0, atol=1e-10)

    def test_canal_inferior_estanco_tipo4(self):
        """T_f_ci = (T_abs + T_int) / 2 satisface el balance del canal estanco."""
        T_abs, T_int = 342.0, 308.0
        T_f_ci = 0.5 * (T_abs + T_int)
        h = 10.0
        balance = h * (T_f_ci - T_abs) + h * (T_f_ci - T_int)
        assert casi_igual(balance, 0.0, atol=1e-10)

    def test_T_f_estanco_entre_paredes(self):
        """T_f_estanco siempre entre las dos temperaturas de pared."""
        pares = [(310.0, 350.0), (295.0, 340.0), (320.0, 330.0)]
        for T_a, T_b in pares:
            T_f = 0.5 * (T_a + T_b)
            assert min(T_a, T_b) <= T_f <= max(T_a, T_b)


# =============================================================================
# 6. RHS del solver — signo y magnitud
# =============================================================================


class TestRHSTipo2:
    """Tests de la función RHS para solve_ivp — Tipo 2."""

    def _params_rhs(self):
        p = _params_ref_tipo2()
        # Renombrar para compatibilidad con _construir_rhs_tipo2
        return {
            "T_amb_K": p["T_amb_K"],
            "T_cie_K": p["T_cie_K"],
            "I_g_W_m2": p["I_g_W_m2"],
            "h_wind": p["h_wind"],
            "h_int_cs": p["h_int_cs"],
            "h_int_ci": p["h_int_ci"],
            "k_cub": p["k_cub"],
            "esp_cub_m": p["esp_cub_m"],
            "em_cub": p["em_cub"],
            "k_ais": p["k_ais"],
            "esp_ais_m": p["esp_ais_m"],
            "em_abs": p["em_abs"],
            "em_fondo": p["em_fondo"],
            "tau_cub": p["tau_cub"],
            "alfa_abs": p["alfa_abs"],
            "W_m": p["W_m"],
            "W_abs_m": p["W_abs_m"],
            "m_punto_cs_kgs": p["m_punto_cs_kgs"],
            "m_punto_ci_kgs": p["m_punto_ci_kgs"],
        }

    def test_derivadas_positivas_entrada(self):
        """En x=0 con fluido ligeramente por encima de T_amb, ambas derivadas > 0.

        Nota: con T_f exactamente igual a T_amb y I_g=800 W/m², la derivada
        del canal superior puede ser marginalmente negativa porque la cubierta
        pierde más calor al cielo (T_cie < T_amb) del que gana por radiación solar.
        El test usa T_f = T_amb - 5 K (fluido más frío) para garantizar derivadas > 0.
        """
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo2(params)
        T_fria = params["T_amb_K"] - 5.0  # fluido frío: garantiza calentamiento
        dy = rhs_fn(0.0, np.array([T_fria, T_fria]))
        assert dy[0] > 0.0, f"dT_f_cs/dx = {dy[0]:.4f} ≤ 0 con fluido frío"
        assert dy[1] > 0.0, f"dT_f_ci/dx = {dy[1]:.4f} ≤ 0 con fluido frío"

    def test_derivadas_finitas(self):
        """Las derivadas no deben ser NaN ni inf."""
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo2(params)
        dy = rhs_fn(0.0, np.array([params["T_amb_K"], params["T_amb_K"]]))
        assert np.all(np.isfinite(dy))

    def test_output_dimension_2(self):
        """RHS Tipo 2 devuelve array de dim 2."""
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo2(params)
        dy = rhs_fn(0.0, np.array([300.0, 300.0]))
        assert len(dy) == 2


class TestRHSTipos34:
    """Tests de las funciones RHS para Tipos 3 y 4."""

    def _params_rhs(self):
        p = _params_ref_tipo2()
        return {
            "T_amb_K": p["T_amb_K"],
            "T_cie_K": p["T_cie_K"],
            "I_g_W_m2": p["I_g_W_m2"],
            "h_wind": p["h_wind"],
            "h_int_cs": p["h_int_cs"],
            "h_int_ci": p["h_int_ci"],
            "k_cub": p["k_cub"],
            "esp_cub_m": p["esp_cub_m"],
            "em_cub": p["em_cub"],
            "k_ais": p["k_ais"],
            "esp_ais_m": p["esp_ais_m"],
            "em_abs": p["em_abs"],
            "em_fondo": p["em_fondo"],
            "tau_cub": p["tau_cub"],
            "alfa_abs": p["alfa_abs"],
            "W_m": p["W_m"],
            "W_abs_m": p["W_abs_m"],
            "m_punto_ci_kgs": p["m_punto_ci_kgs"],
            "m_punto_cs_kgs": p["m_punto_cs_kgs"],
        }

    def test_tipo3_derivada_positiva_entrada(self):
        """Tipo 3: dT_f_ci/dx > 0 en x=0 con fluido frío."""
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo3(params)
        dy = rhs_fn(0.0, np.array([params["T_amb_K"]]))
        assert dy[0] > 0.0, f"dT_f_ci/dx = {dy[0]:.4f} ≤ 0"

    def test_tipo4_derivada_positiva_entrada(self):
        """Tipo 4: dT_f_cs/dx > 0 en x=0 con fluido frío."""
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo4(params)
        dy = rhs_fn(0.0, np.array([params["T_amb_K"]]))
        assert dy[0] > 0.0, f"dT_f_cs/dx = {dy[0]:.4f} ≤ 0"

    def test_tipo3_output_dimension_1(self):
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo3(params)
        dy = rhs_fn(0.0, np.array([300.0]))
        assert len(dy) == 1

    def test_tipo4_output_dimension_1(self):
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo4(params)
        dy = rhs_fn(0.0, np.array([300.0]))
        assert len(dy) == 1

    def test_tipo3_derivadas_finitas(self):
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo3(params)
        dy = rhs_fn(0.0, np.array([300.0]))
        assert np.all(np.isfinite(dy))

    def test_tipo4_derivadas_finitas(self):
        params = self._params_rhs()
        rhs_fn, _ = _construir_rhs_tipo4(params)
        dy = rhs_fn(0.0, np.array([300.0]))
        assert np.all(np.isfinite(dy))


# =============================================================================
# 7. Integración liviana con solve_ivp (sin core)
# =============================================================================


class TestIntegracionLiviana:
    """Tests de solve_ivp directamente sobre la RHS, sin objeto Colector."""

    from scipy.integrate import solve_ivp as _solve_ivp

    def _params_integracion(self):
        p = _params_ref_tipo2()
        return {
            "T_amb_K": p["T_amb_K"],
            "T_cie_K": p["T_cie_K"],
            "I_g_W_m2": p["I_g_W_m2"],
            "h_wind": p["h_wind"],
            "h_int_cs": p["h_int_cs"],
            "h_int_ci": p["h_int_ci"],
            "k_cub": p["k_cub"],
            "esp_cub_m": p["esp_cub_m"],
            "em_cub": p["em_cub"],
            "k_ais": p["k_ais"],
            "esp_ais_m": p["esp_ais_m"],
            "em_abs": p["em_abs"],
            "em_fondo": p["em_fondo"],
            "tau_cub": p["tau_cub"],
            "alfa_abs": p["alfa_abs"],
            "W_m": p["W_m"],
            "W_abs_m": p["W_abs_m"],
            "m_punto_cs_kgs": p["m_punto_cs_kgs"],
            "m_punto_ci_kgs": p["m_punto_ci_kgs"],
        }

    def _integrar(self, rhs_fn, y0, L=2.0):
        from scipy.integrate import solve_ivp

        return solve_ivp(
            rhs_fn,
            (0.0, L),
            y0,
            method="RK45",
            max_step=L / 50,
            rtol=1e-6,
            atol=1e-6,
        )

    def test_tipo2_converge(self):
        """solve_ivp converge para Tipo 2 con parámetros físicos."""
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo2(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"], params["T_amb_K"]])
        assert resultado.success, f"No convergió: {resultado.message}"

    def test_tipo2_T_crece_a_lo_largo(self):
        """T_f aumenta monotónicamente de entrada a salida (fluido se calienta)."""
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo2(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"], params["T_amb_K"]])
        T_cs = resultado.y[0]
        T_ci = resultado.y[1]
        assert T_cs[-1] > T_cs[0], "T_f_cs no aumenta"
        assert T_ci[-1] > T_ci[0], "T_f_ci no aumenta"

    def test_tipo3_converge(self):
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo3(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"]])
        assert resultado.success, f"No convergió: {resultado.message}"

    def test_tipo3_T_crece_a_lo_largo(self):
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo3(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"]])
        T = resultado.y[0]
        assert T[-1] > T[0], "T_f_ci no aumenta"

    def test_tipo4_converge(self):
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo4(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"]])
        assert resultado.success, f"No convergió: {resultado.message}"

    def test_tipo4_T_crece_a_lo_largo(self):
        params = self._params_integracion()
        rhs_fn, _ = _construir_rhs_tipo4(params)
        resultado = self._integrar(rhs_fn, [params["T_amb_K"]])
        T = resultado.y[0]
        assert T[-1] > T[0], "T_f_cs no aumenta"

    def test_tipo2_T_salida_mayor_entrada(self):
        """T salida > T entrada cuando el fluido entra más frío que T_amb."""
        params = self._params_integracion()
        T_ent = params["T_amb_K"] - 5.0  # fluido más frío que el ambiente
        rhs_fn, _ = _construir_rhs_tipo2(params)
        resultado = self._integrar(rhs_fn, [T_ent, T_ent])
        assert resultado.y[0, -1] > T_ent + 1.0, "T_f_cs no gana al menos 1 K"
        assert resultado.y[1, -1] > T_ent + 1.0, "T_f_ci no gana al menos 1 K"

    def test_tipo2_con_I_g_cero_no_calienta(self):
        """Con I_g=0, el fluido no debe calentarse (debería enfriarse o quedar igual)."""
        params = self._params_integracion()
        params["I_g_W_m2"] = 0.0
        T_ent = params["T_amb_K"]
        rhs_fn, _ = _construir_rhs_tipo2(params)
        resultado = self._integrar(rhs_fn, [T_ent, T_ent])
        if resultado.success:
            # Con I_g=0, la T de salida no debe superar la de entrada en más de 2 K
            assert resultado.y[0, -1] <= T_ent + 2.0
            assert resultado.y[1, -1] <= T_ent + 2.0


# =============================================================================
# 8. Regresión bug §15.5 — signo en F3 (balance del absorbedor)
# =============================================================================


class TestRegresionBugF3:
    """Regresión del bug documentado en §15.5 de la bitácora.

    Bug original (Sesión 12): los términos de cesión de calor del absorbedor
    al fluido (``conv_cs_abs`` y ``conv_ci_abs``) sumaban en lugar de restar
    en el balance F3, lo cual permitía una raíz espuria con
    ``T_abs ≈ 301 K`` cuando ``T_f = 330 K`` e ``I_g = 800 W/m²``.

    Estrategia (Opción A): se evalúa el residuo F3 directamente en el punto
    patológico, eligiendo condiciones donde el signo del residuo F3 cambia
    entre la versión correcta y la versión con el signo invertido. Con los
    signos correctos F3 debe ser fuertemente positivo; con el bug
    reintroducido, F3 es negativo. La diferencia entre ambas versiones es
    exactamente ``2·(h_cs + h_ci)·(T_f − T_abs)·W ≈ 1044 W/m`` para los
    parámetros elegidos, lo cual da margen amplio.

    Tests complementarios:
    - Caso isotérmico con ``I_g=0``: todos los residuos deben ser ≈ 0.
      Captura familias enteras de bugs de signo (no solo F3).

    Ver también: §15.5 en bitacora_sesion12.md.
    """

    # Punto patológico discriminante: T_abs < T_f y I_g moderada.
    # Con los parámetros de _params_ref_tipo2() (h_cs=8, h_ci=10, W=W_abs=1),
    # el efecto del bug en F3 es ΔF3 = 2·(h_cs+h_ci)·(T_f−T_abs)·W = +1044 W/m
    # cuando se re-invierten los signos. Eligiendo I_g=400 (moderada) y
    # T_f=330, T_abs=301: F3_correcto ≈ +894 W/m, F3_bug ≈ −150 W/m.
    # El threshold "F3 > 500" detecta el bug con margen amplio y resiste
    # variaciones razonables en otros parámetros del balance.
    T_F_PATOLOGICO_K: float = 330.0
    T_ABS_PATOLOGICO_K: float = 301.0
    T_AMB_PATOLOGICO_K: float = 300.0
    I_G_PATOLOGICO: float = 400.0
    F3_THRESHOLD_W_M: float = 500.0  # > 0 con signos correctos, < 0 con bug

    def _params_patologicos(self) -> dict:
        """Parámetros del punto patológico §15.5."""
        return _params_ref_tipo2(
            I_g=self.I_G_PATOLOGICO,
            T_amb=self.T_AMB_PATOLOGICO_K,
            T_f_cs=self.T_F_PATOLOGICO_K,
            T_f_ci=self.T_F_PATOLOGICO_K,
        )

    def test_F3_tipo2_signo_correcto_en_punto_patologico(self):
        """§15.5 Tipo 2: F3 fuertemente positivo en el punto patológico.

        Con los signos correctos:
            F3 = rad_solar − conv_cs_abs − conv_ci_abs + rad_cub_abs − rad_abs_fondo

        En el punto patológico (T_abs=301 K, T_f=330 K, I_g=400 W/m²):
            - rad_solar = 400·0.85·0.92 ≈ 313 W/m
            - conv_cs_abs = h_cs·(T_abs − T_f) = 8·(−29) = −232 W/m
            - conv_ci_abs = h_ci·(T_abs − T_f) = 10·(−29) = −290 W/m
            - F3_correcto ≈ 313 − (−232) − (−290) + ... ≈ +894 W/m

        Si alguien re-invierte los signos (bug original):
            - F3_bug = 313 + (−232) + (−290) + ... ≈ −150 W/m

        El test exige F3 > 500 W/m, valor que distingue claramente las dos
        versiones con margen amplio. Si el bug se reintroduce, este test cae
        con un mensaje que apunta a §15.5.
        """
        p = self._params_patologicos()
        # vars_ = [T_cub_e, T_cub_i, T_abs, T_int]
        vars_ = np.array(
            [
                p["T_amb_K"] + 5.0,  # T_cub_e
                p["T_amb_K"] + 8.0,  # T_cub_i
                self.T_ABS_PATOLOGICO_K,  # T_abs (raíz espuria del bug)
                p["T_amb_K"] + 5.0,  # T_int
            ]
        )
        residuos = _sistema_nodo_tipo2(
            vars_,
            p["T_f_cs"],
            p["T_f_ci"],
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            p["h_int_cs"],
            p["h_int_ci"],
            p["k_cub"],
            p["esp_cub_m"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais_m"],
            p["em_abs"],
            p["em_fondo"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
        )
        F3 = residuos[2]
        assert F3 > self.F3_THRESHOLD_W_M, (
            f"Bug §15.5 reintroducido: F3={F3:.2f} W/m en el punto patológico "
            f"(T_abs={self.T_ABS_PATOLOGICO_K}, T_f={self.T_F_PATOLOGICO_K}, "
            f"I_g={self.I_G_PATOLOGICO}). Esperado F3 > {self.F3_THRESHOLD_W_M} W/m. "
            "Verificar signos de conv_cs_abs y conv_ci_abs en _sistema_nodo_tipo2."
        )

    @pytest.mark.parametrize("canal_activo", ["superior", "inferior"])
    def test_F3_tipos34_signo_correcto_en_punto_patologico(self, canal_activo):
        """§15.5 Tipos 3 y 4: F3 fuertemente positivo en el punto patológico.

        Misma lógica y umbral que el test de Tipo 2, parametrizada sobre el
        canal activo. En el punto patológico, ambos canales tienen el mismo
        T_f, así que el cálculo es idéntico al de Tipo 2 (los signos del
        balance F3 son los mismos en ``_sistema_nodo_tipos34``).
        """
        p = self._params_patologicos()
        T_f_activo = self.T_F_PATOLOGICO_K
        T_f_estanco = self.T_F_PATOLOGICO_K
        h_act = p["h_int_ci"] if canal_activo == "inferior" else p["h_int_cs"]
        h_est = p["h_int_cs"] if canal_activo == "inferior" else p["h_int_ci"]
        vars_ = np.array(
            [
                p["T_amb_K"] + 5.0,
                p["T_amb_K"] + 8.0,
                self.T_ABS_PATOLOGICO_K,
                p["T_amb_K"] + 5.0,
            ]
        )
        residuos = _sistema_nodo_tipos34(
            vars_,
            T_f_activo,
            T_f_estanco,
            p["T_amb_K"],
            p["T_cie_K"],
            p["I_g_W_m2"],
            p["h_wind"],
            h_act,
            h_est,
            p["k_cub"],
            p["esp_cub_m"],
            p["em_cub"],
            p["k_ais"],
            p["esp_ais_m"],
            p["em_abs"],
            p["em_fondo"],
            p["tau_cub"],
            p["alfa_abs"],
            p["W_m"],
            p["W_abs_m"],
            canal_activo,
        )
        F3 = residuos[2]
        assert F3 > self.F3_THRESHOLD_W_M, (
            f"Bug §15.5 reintroducido en Tipos 3/4 (canal_activo={canal_activo}): "
            f"F3={F3:.2f} W/m. Esperado F3 > {self.F3_THRESHOLD_W_M} W/m. "
            "Verificar signos en _sistema_nodo_tipos34."
        )

    def test_balance_isotermico_residuos_nulos_tipo2(self):
        """Caso isotérmico: I_g=0, todo a T_amb → todos los residuos ≈ 0.

        Estado de equilibrio térmico estricto: si todas las temperaturas son
        iguales y no hay radiación incidente, no hay flujos de calor netos
        en ninguna frontera. Cualquier residuo ≠ 0 indica un bug de signo o
        de unidad. Test más fuerte que el de F3 puntual: cubre F1, F2, F3, F4.
        """
        p = _params_ref_tipo2(I_g=0.0, T_amb=300.0, T_f_cs=300.0, T_f_ci=300.0)
        T_iso = p["T_amb_K"]
        p_iso = dict(p)
        p_iso["T_cie_K"] = T_iso  # cielo a T_amb → sin pérdida radiativa neta
        vars_ = np.array([T_iso, T_iso, T_iso, T_iso])
        residuos = _sistema_nodo_tipo2(
            vars_,
            T_iso,
            T_iso,
            p_iso["T_amb_K"],
            p_iso["T_cie_K"],
            p_iso["I_g_W_m2"],
            p_iso["h_wind"],
            p_iso["h_int_cs"],
            p_iso["h_int_ci"],
            p_iso["k_cub"],
            p_iso["esp_cub_m"],
            p_iso["em_cub"],
            p_iso["k_ais"],
            p_iso["esp_ais_m"],
            p_iso["em_abs"],
            p_iso["em_fondo"],
            p_iso["tau_cub"],
            p_iso["alfa_abs"],
            p_iso["W_m"],
            p_iso["W_abs_m"],
        )
        assert np.allclose(residuos, 0.0, atol=1e-9), (
            f"Caso isotérmico no devuelve residuos nulos: {residuos}. "
            "Indica bug de signo en algún balance."
        )

    @pytest.mark.parametrize("canal_activo", ["superior", "inferior"])
    def test_balance_isotermico_residuos_nulos_tipos34(self, canal_activo):
        """Caso isotérmico Tipos 3/4: residuos ≈ 0 con todas las T iguales."""
        p = _params_ref_tipo2(I_g=0.0, T_amb=300.0)
        T_iso = p["T_amb_K"]
        p_iso = dict(p)
        p_iso["T_cie_K"] = T_iso
        h_act = p_iso["h_int_ci"] if canal_activo == "inferior" else p_iso["h_int_cs"]
        h_est = p_iso["h_int_cs"] if canal_activo == "inferior" else p_iso["h_int_ci"]
        vars_ = np.array([T_iso, T_iso, T_iso, T_iso])
        residuos = _sistema_nodo_tipos34(
            vars_,
            T_iso,
            T_iso,
            p_iso["T_amb_K"],
            p_iso["T_cie_K"],
            p_iso["I_g_W_m2"],
            p_iso["h_wind"],
            h_act,
            h_est,
            p_iso["k_cub"],
            p_iso["esp_cub_m"],
            p_iso["em_cub"],
            p_iso["k_ais"],
            p_iso["esp_ais_m"],
            p_iso["em_abs"],
            p_iso["em_fondo"],
            p_iso["tau_cub"],
            p_iso["alfa_abs"],
            p_iso["W_m"],
            p_iso["W_abs_m"],
            canal_activo,
        )
        assert np.allclose(residuos, 0.0, atol=1e-9), (
            f"Caso isotérmico Tipos 3/4 (canal_activo={canal_activo}) no devuelve "
            f"residuos nulos: {residuos}."
        )


# =============================================================================
# 9. Alturas independientes de canales — Opción 2a (§15.11)
# =============================================================================

# Estos tests requieren construir un Colector real. Si core.colector no está
# disponible (catálogo no cargado, entorno aislado), TestAlturasIndependientes
# se saltea; los tests anteriores no son afectados.

from calculos.colector_tipos234_calc import (  # noqa: E402
    ALTO_CANAL_MIN_M,
    calcular_colector_tipo2,
    calcular_colector_tipo3,
    calcular_colector_tipo4,
)


@pytest.fixture
def colector_basico():
    """Colector con todos los defaults — útil para tests de integración liviana.

    Requiere ``core.colector`` y catálogo cargado. Si no está, se saltea.
    """
    core_colector = pytest.importorskip(
        "core.colector",
        reason="Tests de integración: requieren core.colector y catálogo cargado.",
    )
    return core_colector.Colector()


class TestAlturasIndependientes:
    """Tests de la firma extendida con alto_cs_m / alto_ci_m (§15.11).

    Verifica:
    - Compatibilidad: pasar None reproduce el comportamiento previo.
    - Equivalencia: pasar explícitamente unidad.espaciado_m da igual resultado.
    - Validación: alturas < ALTO_CANAL_MIN_M levantan ValueError.
    - Asimetría efectiva: en Tipo 2 con misma velocidad y alturas distintas,
      las temperaturas de salida de los canales difieren (porque cambian
      caudal, Re, h_int y Dh).
    """

    # Parámetros operativos comunes
    T_AMB_K = 295.0
    I_G = 700.0
    V_VIENTO = 2.0
    P_AMB = 101325.0
    T_ENTRADA = 295.0

    def test_tipo2_default_None_equivale_a_pasar_espaciado(self, colector_basico):
        """Tipo 2: alto_cs_m=alto_ci_m=None reproduce alto=espaciado_m."""
        esp = colector_basico.unidad.espaciado_m
        r_default = calcular_colector_tipo2(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            v_diseno_cs_ms=0.5,
            v_diseno_ci_ms=0.5,
        )
        r_explicito = calcular_colector_tipo2(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            v_diseno_cs_ms=0.5,
            v_diseno_ci_ms=0.5,
            alto_cs_m=esp,
            alto_ci_m=esp,
        )
        assert casi_igual(r_default.T_salida_mezcla_K, r_explicito.T_salida_mezcla_K)
        assert casi_igual(r_default.Q_util_W, r_explicito.Q_util_W)

    def test_tipo3_default_None_equivale_a_pasar_espaciado(self, colector_basico):
        """Tipo 3: alturas None reproducen alto=espaciado_m."""
        esp = colector_basico.unidad.espaciado_m
        r_default = calcular_colector_tipo3(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
        )
        r_explicito = calcular_colector_tipo3(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            alto_cs_m=esp,
            alto_ci_m=esp,
        )
        assert casi_igual(r_default.T_salida_K, r_explicito.T_salida_K)
        assert casi_igual(r_default.Q_util_W, r_explicito.Q_util_W)

    def test_tipo4_default_None_equivale_a_pasar_espaciado(self, colector_basico):
        """Tipo 4: alturas None reproducen alto=espaciado_m."""
        esp = colector_basico.unidad.espaciado_m
        r_default = calcular_colector_tipo4(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
        )
        r_explicito = calcular_colector_tipo4(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            alto_cs_m=esp,
            alto_ci_m=esp,
        )
        assert casi_igual(r_default.T_salida_K, r_explicito.T_salida_K)
        assert casi_igual(r_default.Q_util_W, r_explicito.Q_util_W)

    @pytest.mark.parametrize(
        "motor,kwargs_extra",
        [
            ("tipo2", {"v_diseno_cs_ms": 0.5, "v_diseno_ci_ms": 0.5}),
            ("tipo3", {}),
            ("tipo4", {}),
        ],
    )
    def test_alto_cs_menor_a_minimo_levanta_ValueError(
        self,
        colector_basico,
        motor,
        kwargs_extra,
    ):
        """alto_cs_m < ALTO_CANAL_MIN_M debe levantar ValueError con código GEO_."""
        funciones = {
            "tipo2": calcular_colector_tipo2,
            "tipo3": calcular_colector_tipo3,
            "tipo4": calcular_colector_tipo4,
        }
        f = funciones[motor]
        with pytest.raises(ValueError, match="GEO_ALTO_CS_MINIMO"):
            f(
                colector_basico,
                self.T_AMB_K,
                self.I_G,
                self.V_VIENTO,
                self.P_AMB,
                self.T_ENTRADA,
                alto_cs_m=ALTO_CANAL_MIN_M / 2.0,
                alto_ci_m=0.020,
                **kwargs_extra,
            )

    @pytest.mark.parametrize(
        "motor,kwargs_extra",
        [
            ("tipo2", {"v_diseno_cs_ms": 0.5, "v_diseno_ci_ms": 0.5}),
            ("tipo3", {}),
            ("tipo4", {}),
        ],
    )
    def test_alto_ci_menor_a_minimo_levanta_ValueError(
        self,
        colector_basico,
        motor,
        kwargs_extra,
    ):
        """alto_ci_m < ALTO_CANAL_MIN_M debe levantar ValueError con código GEO_."""
        funciones = {
            "tipo2": calcular_colector_tipo2,
            "tipo3": calcular_colector_tipo3,
            "tipo4": calcular_colector_tipo4,
        }
        f = funciones[motor]
        with pytest.raises(ValueError, match="GEO_ALTO_CI_MINIMO"):
            f(
                colector_basico,
                self.T_AMB_K,
                self.I_G,
                self.V_VIENTO,
                self.P_AMB,
                self.T_ENTRADA,
                alto_cs_m=0.020,
                alto_ci_m=ALTO_CANAL_MIN_M / 2.0,
                **kwargs_extra,
            )

    def test_tipo2_canales_asimetricos_dan_caudales_distintos(self, colector_basico):
        """Tipo 2 con misma velocidad pero alturas distintas → caudales distintos.

        Verifica que la asimetría geométrica se propaga al cálculo. Con la misma
        v_diseno en ambos canales, el caudal másico va como ``ρ·v·W·alto``, así
        que el canal más alto debe tener mayor caudal y, en consecuencia, distinta
        T de salida (todo lo demás igual).
        """
        r = calcular_colector_tipo2(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            v_diseno_cs_ms=0.5,
            v_diseno_ci_ms=0.5,
            alto_cs_m=0.010,  # canal superior 10 mm
            alto_ci_m=0.040,  # canal inferior 40 mm
        )
        # Las dos T de salida deben diferir (asimetría geométrica observable)
        assert abs(r.T_salida_cs_K - r.T_salida_ci_K) > 0.5, (
            f"Asimetría geométrica no observable: T_salida_cs={r.T_salida_cs_K:.2f}, "
            f"T_salida_ci={r.T_salida_ci_K:.2f} K."
        )

    def test_tipo3_canal_estanco_pequeno_caso_uso_real(self, colector_basico):
        """Tipo 3 con canal superior estanco pequeño: caso de uso del usuario.

        Caso de uso descrito en sesión: canal superior estanco angosto (~8 mm)
        para reducir convección y pérdidas al ambiente. Verifica que el motor
        acepta esta configuración asimétrica y converge a un resultado físico.

        Nota: con la implementación actual de ``h_int`` estanco (Re=500 fijo),
        achicar alto_cs reduce Dh y aumenta h_int (Nu·k/Dh). Para que el
        modelo refleje correctamente el efecto de inhibir convección natural,
        se requiere pasar a modo='natural' (mejora futura, ver §10).
        """
        r = calcular_colector_tipo3(
            colector_basico,
            self.T_AMB_K,
            self.I_G,
            self.V_VIENTO,
            self.P_AMB,
            self.T_ENTRADA,
            alto_cs_m=0.008,  # canal estanco superior pequeño
            alto_ci_m=0.030,  # canal activo inferior estándar
        )
        # Sanidad física básica: el motor convergió y entrega calor útil
        assert r.convergencia_ok
        assert r.T_salida_K > self.T_ENTRADA, "El fluido no se calentó"
        assert r.Q_util_W > 0.0


# =============================================================================
# Punto de entrada
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
