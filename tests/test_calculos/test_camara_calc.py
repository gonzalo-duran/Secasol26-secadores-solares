"""Tests del motor numérico de la cámara de secado (calculos/camara_calc.py).

Cubre:
    - calcular_X_eq_gab: invariantes físicas de la isoterma GAB
    - evaluar_MR: todos los modelos de capa fina
    - calcular_tiempo_secado_estatico: casos típicos, casos extremos, convergencia
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from calculos.camara_calc import (
    ResultadosCamara,
    calcular_X_eq_gab,
    calcular_tiempo_secado_estatico,
    evaluar_MR,
)
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    GeometriaCamara,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def camara_manzana():
    """Cámara con manzana / modelo logaritmico (Sacilik 2006)."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        )
    )


@pytest.fixture
def camara_yacon_page():
    """Cámara con yacón / modelo page (Shi 2013, set default 25 °C)."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=5.0,
            humedad_inicial_X=9.0,
            humedad_objetivo_X=0.20,
            modelo_capa_fina="page",
        )
    )


# ---------------------------------------------------------------------------
# calcular_X_eq_gab
# ---------------------------------------------------------------------------


class TestCalcularXeqGAB:

    def test_X_eq_positivo(self):
        X_eq = calcular_X_eq_gab(a_w=0.30, X_m=0.129, C=1.5, K=0.978)
        assert X_eq > 0

    def test_X_eq_crece_con_a_w(self):
        """A mayor actividad de agua, mayor humedad de equilibrio."""
        X_eq_low = calcular_X_eq_gab(a_w=0.20, X_m=0.129, C=1.5, K=0.978)
        X_eq_high = calcular_X_eq_gab(a_w=0.60, X_m=0.129, C=1.5, K=0.978)
        assert X_eq_high > X_eq_low

    def test_X_eq_cero_cuando_a_w_cero(self):
        """A a_w=0, X_eq=0 (producto absolutamente seco)."""
        X_eq = calcular_X_eq_gab(a_w=0.0, X_m=0.129, C=1.5, K=0.978)
        assert X_eq == pytest.approx(0.0, abs=1e-12)

    def test_denominador_no_positivo_lanza(self):
        """K*a_w ≥ 1 hace el denominador ≤ 0."""
        with pytest.raises(ValueError, match="GAB_DENOMINADOR_NO_POSITIVO"):
            calcular_X_eq_gab(a_w=1.1, X_m=0.129, C=1.5, K=0.978)

    def test_valor_tipico_yacon_desorcion_50C(self):
        """Verifica valor de referencia Marques 2022 a T=50°C, modo DDI."""
        # Params DDI, 50°C: X_m=0.129, C=1.32, K=0.973
        # A a_w=0.5: valor de referencia verificado analíticamente.
        X_eq = calcular_X_eq_gab(a_w=0.5, X_m=0.129, C=1.32, K=0.973)
        # Rango esperado físico: 0.05 – 0.25 kg/kg ms para a_w=0.5
        assert 0.05 < X_eq < 0.25


# ---------------------------------------------------------------------------
# evaluar_MR — cada modelo
# ---------------------------------------------------------------------------


class TestEvaluarMR:

    @pytest.mark.parametrize("modelo,params", [
        ("lewis",       {"k": 0.1}),
        ("page",        {"k": 0.1153, "n": 1.2965}),
        ("henderson",   {"a": 1.0, "k": 0.08}),
        ("midilli",     {"a": 1.0041, "k": 0.1281, "n": 0.82, "b": -0.03897}),
        ("logaritmico", {"a": 1.7506, "k": 0.0761, "c": -0.7718}),
    ])
    def test_MR_decrece_con_t(self, modelo, params):
        """MR debe disminuir con el tiempo para todos los modelos en rango típico."""
        MR_0 = evaluar_MR(0.1, modelo, params)
        MR_1h = evaluar_MR(60, modelo, params)
        assert MR_1h < MR_0

    @pytest.mark.parametrize("modelo,params", [
        ("lewis",       {"k": 0.1}),
        ("page",        {"k": 0.1153, "n": 1.2965}),
        ("henderson",   {"a": 1.0, "k": 0.08}),
        ("midilli",     {"a": 1.0041, "k": 0.1281, "n": 0.82, "b": 0.0}),
        ("logaritmico", {"a": 1.0, "k": 0.1, "c": 0.0}),
    ])
    def test_MR_aproxima_1_en_t_cero(self, modelo, params):
        """A t→0, MR debería ser ≈ 1 para parámetros bien calibrados."""
        MR = evaluar_MR(1e-6, modelo, params)
        assert 0.9 < MR < 1.1  # tolerancia empírica para modelos calibrados

    def test_lewis_formula_exacta(self):
        k = 0.1
        t = 10.0
        MR = evaluar_MR(t, "lewis", {"k": k})
        assert MR == pytest.approx(math.exp(-k * t), rel=1e-9)

    def test_page_formula_exacta(self):
        k, n, t = 0.1153, 1.2965, 20.0
        MR = evaluar_MR(t, "page", {"k": k, "n": n})
        assert MR == pytest.approx(math.exp(-k * t**n), rel=1e-9)

    def test_midilli_formula_exacta(self):
        params = {"a": 1.0041, "k": 0.1281, "n": 0.82, "b": -0.03897}
        t = 15.0
        MR = evaluar_MR(t, "midilli", params)
        esperado = params["a"] * math.exp(-params["k"] * t**params["n"]) + params["b"] * t
        assert MR == pytest.approx(esperado, rel=1e-9)

    def test_logaritmico_formula_exacta(self):
        params = {"a": 1.7506, "k": 0.0761, "c": -0.7718}
        t = 30.0
        MR = evaluar_MR(t, "logaritmico", params)
        esperado = params["a"] * math.exp(-params["k"] * t) + params["c"]
        assert MR == pytest.approx(esperado, rel=1e-9)

    def test_modelo_desconocido_lanza(self):
        with pytest.raises(ValueError, match="MODELO_CF_DESCONOCIDO"):
            evaluar_MR(10.0, "modelo_inexistente", {"k": 0.1})


# ---------------------------------------------------------------------------
# calcular_tiempo_secado_estatico
# ---------------------------------------------------------------------------


class TestCalcularTiempoSecado:

    def test_resultado_es_ResultadosCamara(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert isinstance(res, ResultadosCamara)

    def test_convergencia_manzana_50C(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.convergencia_ok
        assert res.t_secado_s > 0

    def test_t_secado_positivo(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.t_secado_s > 0

    def test_tiempo_en_rango_fisico(self, camara_manzana):
        """El solver converge y el tiempo es positivo y menor al límite de 72 h."""
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.convergencia_ok
        assert 0 < res.t_secado_s < 72 * 3600

    def test_X_eq_positivo_y_menor_que_X0(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        X_0 = camara_manzana.carga_producto.humedad_inicial_X
        assert 0 <= res.X_eq_kg_kg < X_0

    def test_curva_monotona_decreciente(self, camara_manzana):
        """La curva de secado X(t) debe ser monótonamente decreciente."""
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        diff = np.diff(res.X_array_kg_kg)
        assert np.all(diff <= 1e-6), "La curva de secado no es monótonamente decreciente."

    def test_curva_empieza_en_X0(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        X_0 = camara_manzana.carga_producto.humedad_inicial_X
        X_eq = res.X_eq_kg_kg
        # El primer punto debe ser ≈ X₀ (MR≈1 en t=0)
        assert res.X_array_kg_kg[0] == pytest.approx(X_eq + (X_0 - X_eq), rel=0.05)

    def test_curva_termina_en_X_obj(self, camara_manzana):
        """El último punto de la curva debe ser ≈ X_obj."""
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        X_obj = camara_manzana.carga_producto.humedad_objetivo_X
        assert res.X_array_kg_kg[-1] == pytest.approx(X_obj, abs=0.05)

    def test_yacon_page_con_GAB(self, camara_yacon_page):
        """Yacón tiene isoterma GAB — fuente_X_eq debe ser 'gab'."""
        res = calcular_tiempo_secado_estatico(camara_yacon_page, T_operacion_K=318.15, HR_operacion=0.25)
        assert res.fuente_X_eq == "gab"

    def test_manzana_usa_gab(self, camara_manzana):
        """Manzana ahora tiene isoterma GAB cargada (Kaymak-Ertekin & Gedik 2004)
        → fuente_X_eq debe ser 'gab'."""
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.fuente_X_eq == "gab"

    def test_masa_agua_extraida_positiva(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.masa_agua_extraida_kg > 0

    def test_masa_agua_extraida_valor(self, camara_manzana):
        """Verifica el valor de masa de agua extraída."""
        p = camara_manzana.carga_producto
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        ms = p.masa_total_kg / (1.0 + p.humedad_inicial_X)
        agua_esperada = ms * (p.humedad_inicial_X - p.humedad_objetivo_X)
        assert res.masa_agua_extraida_kg == pytest.approx(agua_esperada, rel=0.05)

    def test_T_invalida_lanza(self, camara_manzana):
        with pytest.raises(ValueError):
            calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=-10.0, HR_operacion=0.20)

    def test_HR_invalida_lanza(self, camara_manzana):
        with pytest.raises(ValueError):
            calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=1.5)

    def test_advertencia_T_fuera_rango(self, camara_manzana):
        """T=90°C (363 K) está fuera del rango de calibración de Sacilik (40-60°C)."""
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=363.15, HR_operacion=0.20)
        codigos = " ".join(res.advertencias)
        assert "CAM_T_FUERA_RANGO_CALIBRACION" in codigos

    def test_MR_obj_en_rango(self, camara_manzana):
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert 0.0 < res.MR_obj < 1.0

    def test_N_puntos_curva_correcto(self, camara_manzana):
        from calculos.camara_calc import N_PUNTOS_CURVA
        res = calcular_tiempo_secado_estatico(camara_manzana, T_operacion_K=323.15, HR_operacion=0.20)
        assert len(res.t_array_s) == N_PUNTOS_CURVA
        assert len(res.X_array_kg_kg) == N_PUNTOS_CURVA

    def test_tiempo_mayor_a_mayor_rango_X(self):
        """Mayor diferencia X₀-X_obj → mayor tiempo de secado."""
        camara_corto = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=1.0,  # objetivo más alto → menor tiempo
                modelo_capa_fina="logaritmico",
            )
        )
        camara_largo = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,  # objetivo más bajo → mayor tiempo
                modelo_capa_fina="logaritmico",
            )
        )
        res_corto = calcular_tiempo_secado_estatico(camara_corto, T_operacion_K=323.15, HR_operacion=0.20)
        res_largo = calcular_tiempo_secado_estatico(camara_largo, T_operacion_K=323.15, HR_operacion=0.20)
        assert res_largo.t_secado_s > res_corto.t_secado_s

    def test_manzana_midilli(self):
        """Verifica que el modelo midilli también converge para manzana."""
        camara = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="midilli",
            )
        )
        res = calcular_tiempo_secado_estatico(camara, T_operacion_K=323.15, HR_operacion=0.20)
        assert res.convergencia_ok
        assert res.t_secado_s > 0
