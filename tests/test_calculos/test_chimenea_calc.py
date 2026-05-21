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
    _v_viento_a_altura,
    caudal_natural_kgs,
    delta_P_chimenea_Pa,
    delta_P_tiro_Pa,
    delta_P_turbina_motriz_Pa,
)
from calculos.motor_calc import densidad_aire
from core.chimenea import Chimenea

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
            m_punto_kgs=0.0,
            T_chim_K=323.15,
            diametro_m=0.2,
            altura_m=3.0,
        )
        assert dP == 0.0

    def test_perdida_positiva_con_flujo(self):
        dP = delta_P_chimenea_Pa(
            m_punto_kgs=0.05,
            T_chim_K=323.15,
            diametro_m=0.2,
            altura_m=3.0,
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
            T_amb_K=293.15,
            T_chim_K=293.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(1000.0),
        )
        assert res["m_punto_kgs"] == 0.0
        assert any("CHIM_SIN_TIRO" in a for a in res["advertencias"])

    def test_sin_tiro_si_chim_mas_fria(self):
        """T_chim < T_amb → ṁ = 0."""
        res = caudal_natural_kgs(
            T_amb_K=303.15,
            T_chim_K=293.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(1000.0),
        )
        assert res["m_punto_kgs"] == 0.0

    def test_caudal_positivo_caso_tipico(self):
        """Caso operativo típico: T_amb=20°C, T_chim=50°C, chimenea 3m."""
        res = caudal_natural_kgs(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        assert res["m_punto_kgs"] > 0.0
        assert res["v_chim_ms"] > 0.0
        assert res["delta_P_tiro_Pa"] > 0.0

    def test_balance_energia_se_cierra(self):
        """En el equilibrio: ΔP_tiro = ΔP_chim + ΔP_resto."""
        res = caudal_natural_kgs(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        dPT = res["delta_P_tiro_Pa"]
        dPC = res["delta_P_chimenea_Pa"]
        dPR = res["delta_P_resto_Pa"]
        assert dPT == pytest.approx(dPC + dPR, rel=1e-5)

    def test_caudal_crece_con_altura_chimenea(self):
        """Chimenea más alta → más tiro → más caudal."""
        base = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            H_camara_m=1.5,
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
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        m_dT10 = caudal_natural_kgs(T_chim_K=303.15, **base)["m_punto_kgs"]
        m_dT30 = caudal_natural_kgs(T_chim_K=323.15, **base)["m_punto_kgs"]
        m_dT60 = caudal_natural_kgs(T_chim_K=353.15, **base)["m_punto_kgs"]
        assert m_dT10 < m_dT30 < m_dT60

    def test_caudal_decrece_con_resistencia_externa(self):
        """A mayor ΔP_resto, menor caudal de equilibrio."""
        base = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
        )
        m_libre = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(0.0),
            **base,
        )["m_punto_kgs"]
        m_poco = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(100.0),
            **base,
        )["m_punto_kgs"]
        m_mucho = caudal_natural_kgs(
            delta_P_resto_fn=_resto_lineal(10_000.0),
            **base,
        )["m_punto_kgs"]
        assert m_libre > m_poco > m_mucho

    def test_velocidad_consistente_con_caudal(self):
        """v_chim debe ser coherente con ṁ / (ρ · A)."""
        res = caudal_natural_kgs(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
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
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),  # lazo de resistencia media
        )
        assert (
            0.001 < res["m_punto_kgs"] < 0.2
        ), f"Caudal fuera de rango razonable: {res['m_punto_kgs']:.4f} kg/s"

    def test_dict_completo(self):
        """El dict de salida tiene todas las claves documentadas."""
        res = caudal_natural_kgs(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        claves = {
            "m_punto_kgs",
            "v_chim_ms",
            "delta_P_tiro_Pa",
            "delta_P_chimenea_Pa",
            "delta_P_resto_Pa",
            "Re_chimenea",
            "H_eff_m",
            "advertencias",
        }
        assert claves <= res.keys()

    def test_H_eff_es_suma(self):
        """H_eff devuelto debe ser altura_chim + H_camara."""
        res = caudal_natural_kgs(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.2,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        assert res["H_eff_m"] == pytest.approx(4.5, rel=1e-9)


# ---------------------------------------------------------------------------
# Perfil logarítmico de viento
# ---------------------------------------------------------------------------


class TestPerfilVientoLog:
    """v(z) = v(10) · ln(z/z0) / ln(10/z0)."""

    def test_a_10m_devuelve_v_referencia(self):
        # v(10 m) debe coincidir con la velocidad de referencia.
        assert _v_viento_a_altura(5.0, z_m=10.0, z0_m=0.05) == pytest.approx(5.0, rel=1e-9)

    def test_altura_menor_da_menos_viento(self):
        # Para z < 10 m con terreno rugoso, v(z) < v(10).
        v_2m = _v_viento_a_altura(5.0, z_m=2.0, z0_m=0.05)
        assert 0.0 < v_2m < 5.0

    def test_z_menor_a_z0_devuelve_cero(self):
        # Dentro de la capa de rugosidad no hay viento útil.
        assert _v_viento_a_altura(5.0, z_m=0.01, z0_m=0.05) == 0.0

    def test_v_negativo_o_cero_devuelve_cero(self):
        assert _v_viento_a_altura(0.0, z_m=2.0, z0_m=0.05) == 0.0
        assert _v_viento_a_altura(-1.0, z_m=2.0, z0_m=0.05) == 0.0

    def test_terreno_liso_da_mas_viento_a_altura_baja(self):
        # Terreno liso (z0 chico) → la capa límite es más fina → más viento a baja altura.
        v_rural = _v_viento_a_altura(5.0, z_m=2.0, z0_m=0.05)
        v_mar = _v_viento_a_altura(5.0, z_m=2.0, z0_m=0.001)
        assert v_mar > v_rural

    def test_formula_analitica(self):
        # Para z=2, z0=0.05: factor esperado = ln(40)/ln(200) ≈ 0.6961
        v_calc = _v_viento_a_altura(10.0, z_m=2.0, z0_m=0.05)
        factor_esperado = math.log(2.0 / 0.05) / math.log(10.0 / 0.05)
        assert v_calc == pytest.approx(10.0 * factor_esperado, rel=1e-9)


# ---------------------------------------------------------------------------
# Término motriz de la turbina
# ---------------------------------------------------------------------------


class TestDeltaPTurbinaMotriz:

    def test_v_viento_cero_da_cero(self):
        assert delta_P_turbina_motriz_Pa(0.0, Cp_turbina=0.4, T_amb_K=293.15) == 0.0

    def test_Cp_cero_da_cero(self):
        assert delta_P_turbina_motriz_Pa(5.0, Cp_turbina=0.0, T_amb_K=293.15) == 0.0

    def test_escala_cuadraticamente_con_v(self):
        dP1 = delta_P_turbina_motriz_Pa(2.0, Cp_turbina=0.4, T_amb_K=293.15)
        dP2 = delta_P_turbina_motriz_Pa(4.0, Cp_turbina=0.4, T_amb_K=293.15)
        # v_2 = 2·v_1 → ΔP_2 = 4·ΔP_1
        assert dP2 == pytest.approx(4.0 * dP1, rel=1e-9)

    def test_formula_analitica(self):
        # Cp=0.5, v=4 m/s, T=20°C → ρ ≈ 1.204 kg/m³ → ΔP = 0.5·1.204·16/2 ≈ 4.82 Pa
        dP = delta_P_turbina_motriz_Pa(4.0, Cp_turbina=0.5, T_amb_K=293.15)
        rho = densidad_aire(293.15)
        assert dP == pytest.approx(0.5 * rho * 16.0 / 2.0, rel=1e-9)


# ---------------------------------------------------------------------------
# Caudal natural con extractor eólico
# ---------------------------------------------------------------------------


class TestCaudalNaturalConExtractor:
    """Combinaciones de tiro térmico y motriz turbina en el balance."""

    def _llamar(self, **overrides):
        defaults = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.20,
            altura_chim_m=3.0,
            H_camara_m=1.5,
            delta_P_resto_fn=_resto_lineal(500.0),
        )
        defaults.update(overrides)
        return caudal_natural_kgs(**defaults)

    def test_sin_extractor_resultados_iguales_a_baseline(self):
        # Sin extractor: el campo motriz turbina debe ser 0.
        res = self._llamar()
        assert res["delta_P_turbina_motriz_Pa"] == 0.0
        assert res["v_viento_local_ms"] == 0.0

    def test_viento_alto_sin_sol_genera_caudal(self):
        # T_chim = T_amb (sin tiro térmico) pero hay viento → la turbina sola
        # debe inducir caudal positivo.
        res = self._llamar(
            T_chim_K=293.15,
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=1.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=8.0,
        )
        assert res["m_punto_kgs"] > 0.0
        assert res["delta_P_turbina_motriz_Pa"] > 0.0
        assert res["delta_P_tiro_Pa"] <= 0.0

    def test_viento_y_sol_suma_caudal(self):
        # Mismo sol, con viento debe dar más caudal que sin viento.
        sin_viento = self._llamar(
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=1.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=0.0,
        )
        con_viento = self._llamar(
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=1.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=6.0,
        )
        assert con_viento["m_punto_kgs"] > sin_viento["m_punto_kgs"]

    def test_turbina_parada_resta_caudal(self):
        # Sin viento (v=0) pero con Kt > 0: la turbina parada agrega resistencia
        # → caudal menor que chimenea desnuda.
        chim_sola = self._llamar()
        con_turbina_parada = self._llamar(
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=2.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=0.0,
        )
        assert con_turbina_parada["m_punto_kgs"] < chim_sola["m_punto_kgs"]

    def test_sin_tiro_ni_viento_devuelve_cero(self):
        res = self._llamar(
            T_chim_K=293.15,  # = T_amb
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=1.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=0.0,
        )
        assert res["m_punto_kgs"] == 0.0

    def test_aviso_sin_tiro_si_ambos_nulos(self):
        res = self._llamar(
            T_chim_K=293.15,
            extractor_activo=True,
            Cp_turbina=0.5,
            Kt_turbina=1.0,
            diametro_extractor_m=0.30,
            v_viento_10m_ms=0.0,
        )
        assert any("CHIM_SIN_TIRO" in a for a in res["advertencias"])


# ---------------------------------------------------------------------------
# Validaciones de la dataclass Chimenea con extractor
# ---------------------------------------------------------------------------


class TestValidacionesChimeneaExtractor:

    def test_extractor_sin_diametro_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_EXTRACTOR_SIN_DIAMETRO"):
            Chimenea(extractor_activo=True)  # falta diametro_extractor_m

    def test_extractor_diametro_cero_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_EXTRACTOR_SIN_DIAMETRO"):
            Chimenea(extractor_activo=True, diametro_extractor_m=0.0)

    def test_Cp_negativo_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_CP_TURBINA_INVALIDO"):
            Chimenea(
                extractor_activo=True,
                diametro_extractor_m=0.30,
                Cp_turbina=-0.1,
            )

    def test_Cp_excesivo_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_CP_TURBINA_INVALIDO"):
            Chimenea(
                extractor_activo=True,
                diametro_extractor_m=0.30,
                Cp_turbina=2.5,
            )

    def test_Kt_negativo_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_KT_TURBINA_INVALIDO"):
            Chimenea(
                extractor_activo=True,
                diametro_extractor_m=0.30,
                Kt_turbina=-0.5,
            )

    def test_z0_no_positivo_lanza_error(self):
        with pytest.raises(ValueError, match="CHIM_Z0_INVALIDO"):
            Chimenea(z0_terreno_m=0.0)

    def test_chimenea_sin_extractor_no_requiere_diametro_ext(self):
        # extractor_activo=False (default) NO debe pedir diámetro de extractor.
        ch = Chimenea()
        assert ch.extractor_activo is False
        assert ch.diametro_extractor_m is None
