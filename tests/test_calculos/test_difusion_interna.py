"""Resistencia interna a la difusión en serie con la película (S70, Fase 2).

Plan: ``docs/notas/plan_modelo_evaporacion.md``. El agua recorre dos tramos en
serie —interior → superficie por difusión, superficie → aire por la película— y
el motor resuelve la humedad de superficie ``X_s`` que iguala los dos flujos.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from calculos.camara_termodinamica import (
    _omega_saturacion_acotada,
    humedad_superficie_producto,
    simular_secado,
)
from calculos.psicrometria import actividad_agua_desde_X_GAB, humedad_absoluta
from core import catalogo
from core.camara import ForzantesAire


def _aw_gab_manzana():
    iso = catalogo.isoterma_gab("manzana")

    def aw(X: float) -> float:
        if X <= 0.0:
            return 0.0
        try:
            return actividad_agua_desde_X_GAB(X, iso.X_m, iso.C, iso.K)
        except ValueError:
            return 1.0

    return aw


# ---------------------------------------------------------------------------
# Función pura: humedad de superficie
# ---------------------------------------------------------------------------


class TestHumedadSuperficie:
    P = 87000.0
    T_PROD = 313.15

    def _kw(self, **over):
        aw = _aw_gab_manzana()
        X = 1.5
        w_sat = _omega_saturacion_acotada(self.T_PROD, self.P)
        w_ent = humedad_absoluta(0.25, self.T_PROD, self.P)
        w_sup = w_sat * aw(X)
        G = 0.02  # kg/s por unidad de Δω
        kw = dict(
            X_prod_kg_kg=X,
            m_seco_kg=1.0,
            tasa_difusion_s=1e-4,
            m_dot_w_kg_s=G * (w_sup - w_ent),
            omega_sup_kg_kg=w_sup,
            omega_ent_kg_kg=w_ent,
            omega_sat_prod_kg_kg=w_sat,
            aw_func=aw,
        )
        kw.update(over)
        return kw, G

    def test_iguala_flujo_interno_y_externo(self):
        kw, G = self._kw()
        X_s = humedad_superficie_producto(**kw)
        interno = kw["tasa_difusion_s"] * kw["m_seco_kg"] * (kw["X_prod_kg_kg"] - X_s)
        externo = G * (kw["omega_sat_prod_kg_kg"] * kw["aw_func"](X_s) - kw["omega_ent_kg_kg"])
        assert interno == pytest.approx(externo, rel=1e-8)
        assert 0.0 < X_s < kw["X_prod_kg_kg"]

    def test_difusion_rapida_vuelve_a_la_pelicula(self):
        """λ → ∞: la superficie es la humedad media (modelo previo a S70)."""
        kw, _ = self._kw(tasa_difusion_s=1e3)
        assert humedad_superficie_producto(**kw) == pytest.approx(kw["X_prod_kg_kg"], rel=1e-4)

    def test_difusion_lenta_seca_la_superficie(self):
        """λ chica: la superficie se acerca al equilibrio con el aire."""
        kw, _ = self._kw(tasa_difusion_s=1e-9)
        X_s = humedad_superficie_producto(**kw)
        a_w_eq = kw["omega_ent_kg_kg"] / kw["omega_sat_prod_kg_kg"]
        assert kw["aw_func"](X_s) == pytest.approx(a_w_eq, abs=1e-3)

    def test_sin_evaporacion_devuelve_la_media(self):
        kw, _ = self._kw(m_dot_w_kg_s=0.0)
        assert humedad_superficie_producto(**kw) == kw["X_prod_kg_kg"]

    def test_CAM_TD_DIFUSION_TASA_NO_POSITIVA(self):
        kw, _ = self._kw(tasa_difusion_s=0.0)
        with pytest.raises(ValueError, match="CAM_TD_DIFUSION_TASA_NO_POSITIVA"):
            humedad_superficie_producto(**kw)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


class TestCatalogoDifusion:
    def test_tasa_de_lamina_es_el_primer_modo_de_fick(self):
        """λ = π²·D/(4·L²) con L = semiespesor."""
        d = catalogo.DifusionInterna(1e-10, 323.15, 0.0, "lamina")
        assert d.tasa_primer_modo_s(323.15, 0.006) == pytest.approx(
            math.pi**2 * 1e-10 / (4 * 0.003**2), rel=1e-12
        )

    def test_arrhenius_crece_con_la_temperatura(self):
        d = catalogo.difusion_interna("pimiento_rojo")
        assert d.D_eff_m2_s(343.15) > d.D_eff_m2_s(323.15)
        # Vega 2007 Tabla 4 contra su propia regresión de Arrhenius (r² = 0.90: ±21 %).
        for T_C, D_tabla in [(50, 3.2e-9), (60, 6.9e-9), (70, 10.2e-9), (80, 11.2e-9)]:
            assert d.D_eff_m2_s(T_C + 273.15) == pytest.approx(D_tabla, rel=0.22), T_C

    @pytest.mark.parametrize(
        "producto",
        [
            "manzana",
            "pimiento_rojo",
            "pimiento_pimenton",
            "aji_rojo",
            "ciruela",
            "durazno",
            "papa",
            "charqui_vacuno",
            "te_yerba",
            "zanahoria_rallada",
        ],
    )
    def test_productos_con_difusividad(self, producto):
        d = catalogo.difusion_interna(producto)
        assert d is not None
        assert 1e-12 < d.D_ref_m2_s < 1e-8  # alimentos; hojas en el extremo bajo

    def test_producto_sin_bloque(self):
        assert catalogo.difusion_interna("tomate") is None

    def test_bloque_incompleto_no_se_usa(self, monkeypatch):
        monkeypatch.setitem(
            catalogo.PRODUCTOS, "_prueba", {"difusion_interna": {"D_ref_m2_s": 1e-10}}
        )
        assert catalogo.difusion_interna("_prueba") is None


# ---------------------------------------------------------------------------
# Motor: simular_secado con resistencia interna
# ---------------------------------------------------------------------------

_P_SARAVIA = 87000.0
_T_SARAVIA = 313.15


def _saravia(tasa_difusion_func, t_max_h: float = 12.0):
    """Minisecador de Saravia, Alía & Sánchez (2007): banana, aire a 40 °C y 25 % HR.

    Datos del paper: rodajas de 5 mm, A_t = 0.282 m², M_s = 0.0974 kg,
    X(τ) = exp(1.035 − 0.1989·τ[h]), p = 87 kPa. Los coeficientes de película
    (h = 24 W/m²K, K_m = 0.024 kg/m²s) son una estimación de placa plana a
    1.6 m/s; la isoterma es la de manzana (banana no está en el catálogo).
    """
    t_max = t_max_h * 3600.0
    fz = ForzantesAire(
        t_s=np.array([0.0, t_max]),
        T_ent_K=np.full(2, _T_SARAVIA),
        omega_ent=np.full(2, humedad_absoluta(0.25, _T_SARAVIA, _P_SARAVIA)),
        m_dot_aire_seco_kg_s=np.full(2, 0.05),
        T_amb_K=np.full(2, _T_SARAVIA),
        v_viento_ms=np.full(2, 1.0),
    )
    return simular_secado(
        T_prod_inicial_K=301.15,
        X_prod_inicial_kg_kg=math.exp(1.035),
        X_prod_objetivo_kg_kg=0.05,
        m_seco_prod_kg=0.0974,
        c_ps_J_kgK=1500.0,
        forzantes=fz,
        A_prod_m2=0.282,
        A_cuerpo_m2=0.5,
        h_conv_W_m2K=24.0,
        K_m_kg_m2s=0.024,
        k_aisl_W_mK=0.03,
        esp_cam_m=0.05,
        P_Pa=_P_SARAVIA,
        aw_func=_aw_gab_manzana(),
        tasa_difusion_func=tasa_difusion_func,
        t_max_s=t_max,
    )


def _tasa_banana(T_K: float) -> float:
    # D_eff = 1.40e-10 m²/s: λ = 0.1989 1/h del ajuste de Saravia con L = 2.5 mm.
    return catalogo.DifusionInterna(1.40e-10, _T_SARAVIA, 0.0, "lamina").tasa_primer_modo_s(
        T_K, 0.005
    )


class TestMotorConDifusion:
    def test_reproduce_la_curva_de_saravia_2007(self):
        res = _saravia(_tasa_banana)
        th = res.t_array_s / 3600.0
        sel = th <= 10.0
        X_med = np.exp(1.035 - 0.1989 * th[sel])
        rmse = float(np.sqrt(np.mean((res.X_prod_kg_kg[sel] - X_med) ** 2)))
        assert rmse < 0.12, rmse
        # T de producto del paper a 5 h: (40·5 + 55.6)/(5 + 1.94) = 36.8 °C.
        assert float(np.interp(5.0, th, res.T_prod_K)) - 273.15 == pytest.approx(36.8, abs=2.0)

    def test_sin_difusion_seca_mucho_mas_rapido(self):
        """La película sola lleva la banana al equilibrio en < 2 h: el hueco de S69."""
        res = _saravia(None)
        assert float(np.interp(2.0, res.t_array_s / 3600.0, res.X_prod_kg_kg)) < 0.3

    def test_difusion_rapida_reproduce_la_pelicula(self):
        base = _saravia(None, t_max_h=3.0)
        rapida = _saravia(lambda T: 10.0, t_max_h=3.0)
        X_b = np.interp(2.0, base.t_array_s, base.X_prod_kg_kg)
        X_r = np.interp(2.0, rapida.t_array_s, rapida.X_prod_kg_kg)
        assert X_r == pytest.approx(X_b, abs=5e-3)

    def test_superficie_mas_seca_que_la_media(self):
        res = _saravia(_tasa_banana, t_max_h=4.0)
        assert np.all(res.X_sup_kg_kg <= res.X_prod_kg_kg + 1e-9)
        assert res.X_sup_kg_kg[-1] < 0.8 * res.X_prod_kg_kg[-1]

    def test_sin_difusion_la_superficie_es_la_media(self):
        res = _saravia(None, t_max_h=2.0)
        np.testing.assert_allclose(res.X_sup_kg_kg, res.X_prod_kg_kg)


# ---------------------------------------------------------------------------
# Wire-up desde la cámara
# ---------------------------------------------------------------------------


class TestWireUpCamara:
    def _params(self, producto: str):
        from calculos.camara_calc import _construir_params_termodinamico
        from tests.test_calculos.test_conveccion_natural_cajon import _camara

        cam = _camara()
        cam.carga_producto.producto_id = producto
        return _construir_params_termodinamico(cam, 323.15, 0.2, 298.15, 101325.0)

    def test_CAM_TD_DIFUSION_FALTA(self):
        pr = self._params("tomate")
        assert pr.tasa_difusion_func is None
        assert any(a.startswith("CAM_TD_DIFUSION_FALTA") for a in pr.advertencias)

    def test_producto_con_difusividad_arma_la_tasa(self):
        pr = self._params("manzana")
        assert pr.tasa_difusion_func is not None
        assert not any(a.startswith("CAM_TD_DIFUSION_FALTA") for a in pr.advertencias)
        # Manzana, rodaja de 6 mm a 50 °C: λ = π²·3.5e-10/(4·0.003²) ≈ 9.6e-5 1/s.
        assert pr.tasa_difusion_func(323.15) == pytest.approx(
            math.pi**2 * 3.5e-10 / (4 * 0.003**2), rel=1e-9
        )


class TestDimensionPieza:
    """La difusión puede declarar su propia dimensión de pieza (yerba mate, S70)."""

    def _tasa(self, d_p_usuario=None):
        from calculos.camara_calc import _construir_params_termodinamico
        from tests.test_calculos.test_conveccion_natural_cajon import _camara

        cam = _camara()
        cam.carga_producto.producto_id = "te_yerba"
        cam.carga_producto.humedad_inicial_X = 2.3
        cam.carga_producto.humedad_objetivo_X = 0.10
        if d_p_usuario is not None:
            cam.bandejas.diametro_eq_particula_m = d_p_usuario
        pr = _construir_params_termodinamico(cam, 323.15, 0.2, 298.15, 101325.0)
        return pr.tasa_difusion_func(323.15)

    def test_usa_el_espesor_de_la_hoja(self):
        d = catalogo.difusion_interna("te_yerba")
        assert self._tasa() == pytest.approx(d.tasa_primer_modo_s(323.15, 0.00036), rel=1e-9)

    def test_el_d_p_explicito_del_usuario_manda(self):
        d = catalogo.difusion_interna("te_yerba")
        assert self._tasa(0.001) == pytest.approx(d.tasa_primer_modo_s(323.15, 0.001), rel=1e-9)
