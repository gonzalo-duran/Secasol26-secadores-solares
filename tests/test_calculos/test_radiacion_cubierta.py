"""Tests del término radiativo Q_rad = I_g·τ·α·A_rad en el motor termodinámico.

Cubre las cuatro capas del refactor de techo translúcido:
- core.camara.ConstruccionCamara: validación de cubierta_translucida_id.
- core.camara.ForzantesAire: campo opcional I_g_W_m2.
- calculos.camara_termodinamica.simular_secado: aporte radiativo al producto.
- calculos.balance_global.construir_serie_sintetica_dia_tipo: curva I_g(t)
  sinusoidal positiva con pico al mediodía.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.balance_global import (
    armar_forzantes_aire,
    construir_serie_sintetica_dia_tipo,
)
from calculos.camara_termodinamica import simular_secado
from calculos.psicrometria import humedad_absoluta
from core.camara import ConstruccionCamara, ForzantesAire

# ---------------------------------------------------------------------------
# Fixture: kwargs nominales para simular_secado
# ---------------------------------------------------------------------------


def _forzantes_planas(*, n=2, t_max_s=12 * 3600.0, I_g_W_m2=None):
    t_s = np.linspace(0.0, t_max_s, n)
    return ForzantesAire(
        t_s=t_s,
        T_ent_K=np.full(n, 323.15),
        omega_ent=np.full(n, humedad_absoluta(0.20, 323.15)),
        m_dot_aire_seco_kg_s=np.full(n, 0.030),
        T_amb_K=np.full(n, 298.15),
        v_viento_ms=np.full(n, 2.0),
        I_g_W_m2=None if I_g_W_m2 is None else np.full(n, float(I_g_W_m2)),
    )


def _kwargs_motor(**overrides):
    base = dict(
        T_prod_inicial_K=298.15,
        X_prod_inicial_kg_kg=2.0,
        X_prod_objetivo_kg_kg=0.30,
        m_seco_prod_kg=3.0,
        c_ps_J_kgK=1500.0,
        forzantes=_forzantes_planas(),
        A_prod_m2=2.5,
        A_cuerpo_m2=8.0,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        k_aisl_W_mK=0.02679,
        esp_cam_m=0.05,
        P_Pa=101325.0,
        aw_func=lambda X: min(1.0, max(0.0, X / 0.5)),
        t_max_s=12 * 3600.0,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ConstruccionCamara — validación
# ---------------------------------------------------------------------------


class TestConstruccionCubierta:

    def test_opaca_default(self):
        cons = ConstruccionCamara()
        assert cons.cubierta_translucida_id is None
        assert cons.A_rad_m2 is None

    def test_id_valido(self):
        cons = ConstruccionCamara(cubierta_translucida_id="vidrio_comun")
        assert cons.cubierta_translucida_id == "vidrio_comun"

    def test_id_invalido_falla(self):
        with pytest.raises(ValueError, match="MAT_CUBIERTA_CAM_NO_ENCONTRADA"):
            ConstruccionCamara(cubierta_translucida_id="material_inexistente")

    def test_A_rad_no_positiva_falla(self):
        with pytest.raises(ValueError, match="CONS_A_RAD_NO_POSITIVA"):
            ConstruccionCamara(cubierta_translucida_id="vidrio_comun", A_rad_m2=-1.0)


# ---------------------------------------------------------------------------
# ForzantesAire — I_g_W_m2 opcional
# ---------------------------------------------------------------------------


class TestForzantesAireConIg:

    def test_sin_I_g_rellena_ceros(self):
        fz = _forzantes_planas(n=5, I_g_W_m2=None)
        assert fz.I_g_W_m2.shape == (5,)
        assert np.all(fz.I_g_W_m2 == 0.0)

    def test_con_I_g_se_respeta(self):
        fz = _forzantes_planas(n=5, I_g_W_m2=600.0)
        assert np.all(fz.I_g_W_m2 == 600.0)

    def test_longitud_I_g_inconsistente_falla(self):
        with pytest.raises(ValueError, match="FORZANTES_LONGITUD_INCONSISTENTE"):
            ForzantesAire(
                t_s=np.array([0.0, 3600.0]),
                T_ent_K=np.array([323.15, 323.15]),
                omega_ent=np.array([0.01, 0.01]),
                m_dot_aire_seco_kg_s=np.array([0.03, 0.03]),
                T_amb_K=np.array([298.15, 298.15]),
                v_viento_ms=np.array([2.0, 2.0]),
                I_g_W_m2=np.array([800.0]),  # longitud 1, esperado 2
            )


# ---------------------------------------------------------------------------
# Motor: efecto del término Q_rad
# ---------------------------------------------------------------------------


class TestMotorConRadiacion:

    def test_Q_rad_cero_es_idempotente(self):
        """Con tau=0 o A_rad=0, el resultado debe ser idéntico al motor sin radiación."""
        kw_sin = _kwargs_motor()
        res_sin = simular_secado(**kw_sin)

        # Mismas forzantes, pero esta vez con I_g grande — sin embargo τ=0
        # (default) anula Q_rad, así que el resultado debe ser idéntico.
        kw_con_Ig = _kwargs_motor(
            forzantes=_forzantes_planas(I_g_W_m2=900.0),
        )
        res_con_Ig = simular_secado(**kw_con_Ig)

        assert res_sin.t_secado_s == pytest.approx(res_con_Ig.t_secado_s, rel=1e-9)
        assert res_sin.energia_rad_total_J == 0.0
        assert res_con_Ig.energia_rad_total_J == 0.0
        # Q_rad_W debe ser cero en ambos casos
        assert np.all(res_sin.Q_rad_W == 0.0)
        assert np.all(res_con_Ig.Q_rad_W == 0.0)

    def test_Q_rad_acelera_secado(self):
        """Con τ·α·A_rad > 0 e I_g > 0, t_secado se reduce y energia_rad > 0."""
        I_g = 800.0
        kw_base = _kwargs_motor(forzantes=_forzantes_planas(I_g_W_m2=I_g))
        res_opaco = simular_secado(**kw_base)
        kw_trans = _kwargs_motor(
            forzantes=_forzantes_planas(I_g_W_m2=I_g),
            tau_cubierta_solar=0.85,
            alfa_producto_solar=0.6,
            A_rad_m2=1.0,  # 1 m² de bandeja superior expuesta
        )
        res_trans = simular_secado(**kw_trans)

        assert res_trans.energia_rad_total_J > 0.0
        # Aporte teórico mínimo (sin perdidas):
        # Q_rad = 0.85·0.6·1.0·800 = 408 W constantes durante 12 h ≈ 17.6 MJ
        Q_rad_teorico_W = 0.85 * 0.6 * 1.0 * I_g
        assert res_trans.Q_rad_W[0] == pytest.approx(Q_rad_teorico_W, rel=1e-6)
        # El secado debe acelerarse (puede saltar el evento X_obj antes).
        if res_opaco.t_secado_s is not None and res_trans.t_secado_s is not None:
            assert res_trans.t_secado_s < res_opaco.t_secado_s
        # T_max del producto debe ser mayor con radiación.
        assert res_trans.T_max_alcanzada_K > res_opaco.T_max_alcanzada_K

    def test_T_prod_acercase_a_T_flujo_con_radiacion(self):
        """Con radiación moderada, T_prod debe ser sistemáticamente mayor que
        sin radiación (el aporte solar directo eleva la temperatura del
        producto). No exigimos T_prod > T_flujo porque la evaporación
        endotérmica consume el aporte; pero T_prod debe acercarse a T_flujo.

        Q_rad nominal: 0.85·0.6·1.0·800 = 408 W (≈40 % de q_prod inicial).
        """
        I_g = 800.0
        kw_sin = _kwargs_motor(forzantes=_forzantes_planas(I_g_W_m2=I_g))
        res_sin = simular_secado(**kw_sin)

        kw_con = _kwargs_motor(
            forzantes=_forzantes_planas(I_g_W_m2=I_g),
            tau_cubierta_solar=0.85,
            alfa_producto_solar=0.6,
            A_rad_m2=1.0,
        )
        res_con = simular_secado(**kw_con)

        # En cada paso temporal donde ambos solver han avanzado, la trayectoria
        # con radiación debería tener T_prod >= sin radiación.
        n_min = min(len(res_sin.T_prod_K), len(res_con.T_prod_K))
        # Media de T_prod en los primeros n_min puntos
        media_sin = float(np.mean(res_sin.T_prod_K[:n_min]))
        media_con = float(np.mean(res_con.T_prod_K[:n_min]))
        assert media_con > media_sin, (
            f"T_prod no se elevó con radiación (sin={media_sin:.2f} K, " f"con={media_con:.2f} K)."
        )


# ---------------------------------------------------------------------------
# Constructor sintético: curva I_g(t)
# ---------------------------------------------------------------------------


class TestSinteticoIg:

    def test_I_g_max_cero_da_ceros(self):
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=0.01,
            m_dot_aire_seco_kg_s=0.03,
            I_g_max_W_m2=0.0,
        )
        assert np.all(fz.I_g_W_m2 == 0.0)

    def test_I_g_pico_al_mediodia(self):
        I_g_max = 800.0
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=0.01,
            m_dot_aire_seco_kg_s=0.03,
            I_g_max_W_m2=I_g_max,
            hora_pico=12.0,
            n_horas=24,
        )
        # Hora 12 = índice 12 → pico exacto
        assert fz.I_g_W_m2[12] == pytest.approx(I_g_max, rel=1e-9)
        # Medianoche y madrugada → cero (fuera del intervalo solar)
        assert fz.I_g_W_m2[0] == pytest.approx(0.0, abs=1e-9)
        assert fz.I_g_W_m2[3] == pytest.approx(0.0, abs=1e-9)
        # Todas las horas tienen valores no negativos
        assert np.all(fz.I_g_W_m2 >= 0.0)

    def test_I_g_replica_multi_dia(self):
        I_g_max = 700.0
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=0.01,
            m_dot_aire_seco_kg_s=0.03,
            I_g_max_W_m2=I_g_max,
            n_horas=24,
            n_dias=3,
        )
        assert len(fz.I_g_W_m2) == 72
        # Pico de cada día (índices 12, 36, 60) ≈ I_g_max
        for idx_pico in (12, 36, 60):
            assert fz.I_g_W_m2[idx_pico] == pytest.approx(I_g_max, rel=1e-9)


# ---------------------------------------------------------------------------
# armar_forzantes_aire — pase de I_g explícito
# ---------------------------------------------------------------------------


class TestArmarForzantesConIg:

    def test_sin_I_g_default_ceros(self):
        fz = armar_forzantes_aire(
            modo="diario",
            T_salida_colector_K=np.full(24, 323.15),
            omega_ambiente=np.full(24, 0.01),
            m_dot_aire_seco_kg_s=0.03,
        )
        assert np.all(fz.I_g_W_m2 == 0.0)

    def test_con_I_g_explicito(self):
        I_g_in = np.linspace(0.0, 900.0, 24)
        fz = armar_forzantes_aire(
            modo="diario",
            T_salida_colector_K=np.full(24, 323.15),
            omega_ambiente=np.full(24, 0.01),
            m_dot_aire_seco_kg_s=0.03,
            I_g_W_m2=I_g_in,
        )
        np.testing.assert_allclose(fz.I_g_W_m2, I_g_in)

    def test_I_g_longitud_inconsistente_falla(self):
        with pytest.raises(ValueError, match="FORZANTES_LONGITUD_INCONSISTENTE"):
            armar_forzantes_aire(
                modo="diario",
                T_salida_colector_K=np.full(24, 323.15),
                omega_ambiente=np.full(24, 0.01),
                m_dot_aire_seco_kg_s=0.03,
                I_g_W_m2=np.full(12, 500.0),  # mitad de la longitud
            )
