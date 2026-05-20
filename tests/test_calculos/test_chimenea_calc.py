"""Tests del modelo de chimenea solar (`calculos.chimenea_calc`).

Cubre:
- Tiro térmico: signo, magnitud analítica, monotonía con H y ΔT.
- Pérdida de carga del ducto: ceros, monotonía, dependencia con D y altura.
- Caudal de equilibrio: balance, sin tiro, sensibilidades, robustez.
"""
from __future__ import annotations

import math

import pytest

from calculos.chimenea_calc import (
    _G_MS2,
    caudal_natural_kgs,
    delta_P_chimenea_Pa,
    delta_P_tiro_Pa,
)
from calculos.motor_calc import densidad_aire


# ---------------------------------------------------------------------------
# Tiro térmico
# ---------------------------------------------------------------------------


class TestDeltaPTiro:
    """Stack effect: ΔP_tiro = g · H_eff · (ρ_amb − ρ_chim)."""

    def test_tiro_positivo_si_chim_caliente(self):
        """T_chim > T_amb → ΔP > 0 (operación diurna típica)."""
        dP = delta_P_tiro_Pa(T_amb_K=293.15, T_chim_K=323.15, H_eff_m=3.0)
        assert dP > 0.0

    def test_tiro_nulo_si_misma_temperatura(self):
        """T_chim = T_amb → ΔP = 0 (sin gradiente de densidad)."""
        dP = delta_P_tiro_Pa(T_amb_K=293.15, T_chim_K=293.15, H_eff_m=3.0)
        assert dP == pytest.approx(0.0, abs=1e-10)

    def test_tiro_negativo_si_chim_fria(self):
        """T_chim < T_amb → ΔP < 0 (contraflujo posible, ej. noche)."""
        dP = delta_P_tiro_Pa(T_amb_K=303.15, T_chim_K=293.15, H_eff_m=3.0)
        assert dP < 0.0

    def test_tiro_nulo_si_altura_cero(self):
        """H_eff = 0 → ΔP = 0 independientemente del ΔT."""
        dP = delta_P_tiro_Pa(T_amb_K=293.15, T_chim_K=343.15, H_eff_m=0.0)
        assert dP == 0.0

    def test_tiro_valor_analitico(self):
        """Verificación numérica directa contra la fórmula.

        H=3m, T_amb=293.15K, T_chim=343.15K, P=101325 Pa:
        ρ_amb = 101325 / (287.05 · 293.15) ≈ 1.2039 kg/m³
        ρ_chim = 101325 / (287.05 · 343.15) ≈ 1.0286 kg/m³
        ΔP = 9.81 · 3 · (1.2039 − 1.0286) ≈ 5.16 Pa
        """
        T_amb, T_chim, H = 293.15, 343.15, 3.0
        rho_amb = densidad_aire(T_amb)
        rho_chim = densidad_aire(T_chim)
        esperado = _G_MS2 * H * (rho_amb - rho_chim)
        dP = delta_P_tiro_Pa(T_amb, T_chim, H)
        assert dP == pytest.approx(esperado, rel=1e-9)

    def test_tiro_monotonia_altura(self):
        """A mayor H, mayor tiro (lineal)."""
        dP1 = delta_P_tiro_Pa(293.15, 323.15, H_eff_m=1.0)
        dP3 = delta_P_tiro_Pa(293.15, 323.15, H_eff_m=3.0)
        dP6 = delta_P_tiro_Pa(293.15, 323.15, H_eff_m=6.0)
        assert dP1 < dP3 < dP6
        assert dP3 == pytest.approx(3.0 * dP1, rel=1e-9)
        assert dP6 == pytest.approx(6.0 * dP1, rel=1e-9)

    def test_tiro_monotonia_dT(self):
        """A mayor ΔT (T_chim − T_amb), mayor tiro."""
        T_amb = 293.15
        dP_pequeno = delta_P_tiro_Pa(T_amb, T_amb + 10.0, H_eff_m=3.0)
        dP_medio = delta_P_tiro_Pa(T_amb, T_amb + 30.0, H_eff_m=3.0)
        dP_grande = delta_P_tiro_Pa(T_amb, T_amb + 60.0, H_eff_m=3.0)
        assert dP_pequeno < dP_medio < dP_grande


# ---------------------------------------------------------------------------
# Pérdida de carga del ducto
# ---------------------------------------------------------------------------


class TestDeltaPChimenea:
    """Fricción Darcy + singulares en el ducto."""

    def test_perdida_nula_caudal_cero(self):
        dP = delta_P_chimenea_Pa(
            m_punto_kgs=0.0, T_chim_K=323.15,
            diametro_m=0.2, altura_m=3.0,
        )
        assert dP == 0.0

    def test_perdida_positiva_con_flujo(self):
        dP = delta_P_chimenea_Pa(
            m_punto_kgs=0.05, T_chim_K=323.15,
            diametro_m=0.2, altura_m=3.0,
        )
        assert dP > 0.0

    def test_perdida_monotona_con_caudal(self):
        """ΔP crece con ṁ (cuadrático en turbulento + lineal en laminar)."""
        kwargs = dict(T_chim_K=323.15, diametro_m=0.2, altura_m=3.0)
        ms = [0.001, 0.01, 0.05, 0.1, 0.2]
        dPs = [delta_P_chimenea_Pa(m_punto_kgs=m, **kwargs) for m in ms]
        assert all(dPs[i] < dPs[i + 1] for i in range(len(dPs) - 1))

    def test_perdida_crece_con_altura(self):
        """ΔP por fricción crece linealmente con la altura del ducto."""
        kw = dict(m_punto_kgs=0.05, T_chim_K=323.15, diametro_m=0.2)
        dP_corta = delta_P_chimenea_Pa(altura_m=1.0, **kw)
        dP_larga = delta_P_chimenea_Pa(altura_m=5.0, **kw)
        # No es exactamente 5× porque K_singular es independiente de la altura.
        assert dP_larga > dP_corta

    def test_perdida_decrece_con_diametro(self):
        """A mayor D, menor velocidad → menor ΔP (mucho menor por v²)."""
        kw = dict(m_punto_kgs=0.05, T_chim_K=323.15, altura_m=3.0)
        dP_chico = delta_P_chimenea_Pa(diametro_m=0.10, **kw)
        dP_grande = delta_P_chimenea_Pa(diametro_m=0.30, **kw)
        assert dP_grande < dP_chico


# ---------------------------------------------------------------------------
# Caudal de equilibrio
# ---------------------------------------------------------------------------


def _resto_lineal(coef_Pa_por_kgs2: float):
    """Devuelve un delta_P_resto_fn ficticio: ΔP = c·ṁ² (cuadrático puro)."""
    return lambda m: coef_Pa_por_kgs2 * m * m


def _resto_constante_mas_lineal(coef: float):
    """ΔP_resto = c·ṁ (lineal con caudal). Útil para verificar monotonía."""
    return lambda m: coef * m


class TestCaudalNatural:

    def test_sin_tiro_si_T_chim_igual_a_T_amb(self):
        """T_chim = T_amb → ṁ = 0 y advertencia CHIM_SIN_TIRO."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=293.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(1000.0),
        )
        assert res["m_punto_kgs"] == 0.0
        assert any("CHIM_SIN_TIRO" in a for a in res["advertencias"])

    def test_sin_tiro_si_chim_mas_fria(self):
        """T_chim < T_amb → ṁ = 0."""
        res = caudal_natural_kgs(
            T_amb_K=303.15, T_chim_K=293.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(1000.0),
        )
        assert res["m_punto_kgs"] == 0.0

    def test_caudal_positivo_caso_tipico(self):
        """Caso operativo típico: T_amb=20°C, T_chim=50°C, chimenea 3m."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        assert res["m_punto_kgs"] > 0.0
        assert res["v_chim_ms"] > 0.0
        assert res["delta_P_tiro_Pa"] > 0.0

    def test_balance_energia_se_cierra(self):
        """En el equilibrio: ΔP_tiro = ΔP_chim + ΔP_resto."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        dPT = res["delta_P_tiro_Pa"]
        dPC = res["delta_P_chimenea_Pa"]
        dPR = res["delta_P_resto_Pa"]
        assert dPT == pytest.approx(dPC + dPR, rel=1e-5)

    def test_caudal_crece_con_altura_chimenea(self):
        """Chimenea más alta → más tiro → más caudal."""
        base = dict(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        m_baja = caudal_natural_kgs(altura_chim_m=1.0, **base)["m_punto_kgs"]
        m_media = caudal_natural_kgs(altura_chim_m=3.0, **base)["m_punto_kgs"]
        m_alta = caudal_natural_kgs(altura_chim_m=6.0, **base)["m_punto_kgs"]
        assert m_baja < m_media < m_alta

    def test_caudal_crece_con_dT(self):
        """T_chim más caliente → más tiro → más caudal."""
        base = dict(
            T_amb_K=293.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        m_dT10 = caudal_natural_kgs(T_chim_K=303.15, **base)["m_punto_kgs"]
        m_dT30 = caudal_natural_kgs(T_chim_K=323.15, **base)["m_punto_kgs"]
        m_dT60 = caudal_natural_kgs(T_chim_K=353.15, **base)["m_punto_kgs"]
        assert m_dT10 < m_dT30 < m_dT60

    def test_caudal_decrece_con_resistencia_externa(self):
        """A mayor ΔP_resto, menor caudal de equilibrio."""
        base = dict(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
        )
        m_libre = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(0.0), **base,
        )["m_punto_kgs"]
        m_poco = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(100.0), **base,
        )["m_punto_kgs"]
        m_mucho = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(10_000.0), **base,
        )["m_punto_kgs"]
        assert m_libre > m_poco > m_mucho

    def test_velocidad_consistente_con_caudal(self):
        """v_chim debe ser coherente con ṁ / (ρ · A)."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        rho = densidad_aire(323.15)
        A = math.pi * (0.2 / 2.0) ** 2
        v_esperada = res["m_punto_kgs"] / (rho * A)
        assert res["v_chim_ms"] == pytest.approx(v_esperada, rel=1e-9)

    def test_magnitud_caudal_realista(self):
        """Sanity: para chimenea de 20 cm, 3 m, ΔT=30K, lazo razonable,
        el caudal debe caer en el orden 0.005-0.1 kg/s (típico secadores
        chicos a medianos de prediseño)."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),  # lazo de resistencia media
        )
        assert 0.001 < res["m_punto_kgs"] < 0.2, (
            f"Caudal fuera de rango razonable: {res['m_punto_kgs']:.4f} kg/s"
        )

    def test_dict_completo(self):
        """El dict de salida tiene todas las claves documentadas."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        claves = {
            "m_punto_kgs", "v_chim_ms", "delta_P_tiro_Pa",
            "delta_P_chimenea_Pa", "delta_P_resto_Pa", "Re_chimenea",
            "H_eff_m", "advertencias",
        }
        assert claves <= res.keys()

    def test_H_eff_es_suma(self):
        """H_eff devuelto debe ser altura_chim + H_camara."""
        res = caudal_natural_kgs(
            T_amb_K=293.15, T_chim_K=323.15,
            diametro_chim_m=0.2, altura_chim_m=3.0, H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        assert res["H_eff_m"] == pytest.approx(4.5, rel=1e-9)
