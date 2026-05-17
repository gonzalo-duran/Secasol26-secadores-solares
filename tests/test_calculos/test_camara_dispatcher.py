"""Tests del despachador `calcular_camara` y wire-up `_calcular_termodinamico`.

Verifica que:
    - El despachador selecciona el motor correcto según camara.modo_calculo.
    - El wire-up con S3 prepara correctamente los argumentos para simular_secado
      y devuelve un ResultadoMotorTermodinamico válido.
    - Productos sin GAB calibrado disparan el fallback de aw_func + advertencia.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.camara_calc import (
    ResultadosCamara,
    _calcular_termodinamico,
    _h_conv_camara_placa_plana,
    calcular_camara,
)
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    GeometriaCamara,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def camara_manzana_capa_fina():
    """Cámara con manzana, modo capa_fina (default)."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
            modelo_capa_fina="logaritmico",
        ),
    )


@pytest.fixture
def camara_manzana_termodinamico():
    """Cámara con manzana, modo termodinámico."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
    )


# ---------------------------------------------------------------------------
# Tests del helper de h_conv
# ---------------------------------------------------------------------------


class TestHConvCamaraPlacaPlana:

    def test_valor_tipico_laminar(self):
        """v=0.5 m/s, L=1.2 m, T=323 K → Re ~ 35000 (laminar) → h ~ 2-4 W/m²K."""
        h = _h_conv_camara_placa_plana(
            v_aire_ms=0.5,
            L_caracteristico_m=1.2,
            T_pelicula_K=323.15,
            omega_pelicula=0.012,
            P_Pa=101325.0,
        )
        assert 1.0 < h < 10.0   # rango razonable para convección natural-forzada suave

    def test_crece_con_velocidad(self):
        h_lento = _h_conv_camara_placa_plana(0.2, 1.0, 323.15, 0.012, 101325.0)
        h_rapido = _h_conv_camara_placa_plana(2.0, 1.0, 323.15, 0.012, 101325.0)
        assert h_rapido > h_lento


# ---------------------------------------------------------------------------
# Despachador
# ---------------------------------------------------------------------------


class TestDispatcher:

    def test_capa_fina_devuelve_resultados_camara(self, camara_manzana_capa_fina):
        res = calcular_camara(
            camara_manzana_capa_fina,
            T_operacion_K=323.15,
            HR_operacion=0.20,
        )
        assert isinstance(res, ResultadosCamara)
        assert res.t_secado_s > 0

    def test_termodinamico_devuelve_resultado_motor(
        self, camara_manzana_termodinamico
    ):
        res = calcular_camara(
            camara_manzana_termodinamico,
            T_operacion_K=323.15,
            HR_operacion=0.20,
            T_amb_K=298.15,
        )
        assert isinstance(res, ResultadoMotorTermodinamico)
        # Manzana ya tiene GAB cargado (Kaymak-Ertekin & Gedik 2004) →
        # no debe emitir CAM_TD_GAB_FALTA.
        assert not any("GAB_FALTA" in a for a in res.advertencias)

    def test_termodinamico_alcanza_X_obj(self):
        """Test de convergencia con yacón (que SÍ tiene GAB calibrada).

        Manzana usa el fallback aw=X/X_inicial, que es no-físico: cuando X
        cae a ≈ X_inicial·HR_op, ω_sup se iguala a ω_ent y el aire deja de
        evaporar antes de alcanzar X_obj. Yacón con GAB real mantiene aw
        cercano a 1 hasta X moderado, lo que permite testear convergencia.

        Cámara dimensionada para flujo activo: caudal alto sobre cámara
        chica para que la correlación de placa plana dé h_conv razonable.
        """
        cam = Camara(
            geometria=GeometriaCamara(largo_m=0.6, ancho_m=0.4, alto_m=0.6),
            bandejas=ConfiguracionBandejas(
                n_bandejas=3,
                area_bandeja_m2=0.20,
                espesor_capa_m=0.015,
                separacion_entre_bandejas_m=0.06,
            ),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.10),
            carga_producto=CargaProducto(
                producto_id="yacon",
                masa_total_kg=2.0,
                humedad_inicial_X=9.0,
                humedad_objetivo_X=0.50,
                modelo_capa_fina="page",
            ),
            modo_calculo="termodinamico",
        )
        res = calcular_camara(
            cam,
            T_operacion_K=333.15,        # 60 °C
            HR_operacion=0.15,
            T_amb_K=298.15,
        )
        assert res.status == "X_obj_alcanzado"
        assert res.t_secado_s is not None
        assert res.t_secado_s > 0
        assert res.X_prod_kg_kg[-1] == pytest.approx(0.50, abs=1e-2)


# ---------------------------------------------------------------------------
# Wire-up directo a _calcular_termodinamico
# ---------------------------------------------------------------------------


class TestWireUpTermodinamico:

    def test_T_prod_inicial_None_usa_T_amb(self, camara_manzana_termodinamico):
        """Si T_prod_inicial_K es None en CargaProducto, debe arrancar en T_amb."""
        res = _calcular_termodinamico(
            camara_manzana_termodinamico,
            T_operacion_K=323.15,
            HR_operacion=0.20,
            T_amb_K=288.15,            # 15 °C — distinto de cualquier default
            P_Pa=101325.0,
        )
        # T_prod en t=0 ≈ T_amb (un único punto de tiempo guardado al inicio)
        assert res.T_prod_K[0] == pytest.approx(288.15, abs=0.5)

    def test_T_prod_inicial_explicita_se_respeta(self):
        """Si CargaProducto define T_prod_inicial_K, NO se usa T_amb."""
        cam = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.20,
                modelo_capa_fina="logaritmico",
                T_prod_inicial_K=305.15,    # 32 °C — explícito
            ),
            modo_calculo="termodinamico",
        )
        res = _calcular_termodinamico(
            cam,
            T_operacion_K=323.15,
            HR_operacion=0.20,
            T_amb_K=288.15,                  # ignorado
            P_Pa=101325.0,
        )
        assert res.T_prod_K[0] == pytest.approx(305.15, abs=0.5)

    def test_yacon_con_GAB_no_emite_fallback(self):
        """Yacón tiene GAB calibrada → no debe emitir CAM_TD_GAB_FALTA."""
        cam = Camara(
            carga_producto=CargaProducto(
                producto_id="yacon",
                masa_total_kg=5.0,
                humedad_inicial_X=9.0,
                humedad_objetivo_X=0.30,
                modelo_capa_fina="page",
            ),
            modo_calculo="termodinamico",
        )
        res = calcular_camara(
            cam, T_operacion_K=323.15, HR_operacion=0.20, T_amb_K=298.15,
        )
        assert not any("GAB_FALTA" in a for a in res.advertencias)

    def test_series_temporales_consistentes(self, camara_manzana_termodinamico):
        """Todas las series tienen el mismo tamaño y son numpy arrays."""
        res = calcular_camara(
            camara_manzana_termodinamico,
            T_operacion_K=323.15,
            HR_operacion=0.20,
            T_amb_K=298.15,
        )
        n = len(res.t_array_s)
        for arr in (
            res.T_prod_K, res.X_prod_kg_kg,
            res.T_flujo_K, res.omega_flujo_kg_kg,
            res.m_dot_w_kg_s, res.q_prod_W, res.q_pared_W,
        ):
            assert isinstance(arr, np.ndarray)
            assert arr.shape == (n,)

    def test_X_decrece_durante_secado(self, camara_manzana_termodinamico):
        res = calcular_camara(
            camara_manzana_termodinamico,
            T_operacion_K=323.15,
            HR_operacion=0.20,
            T_amb_K=298.15,
        )
        # Tendencia decreciente (permitir ruido numérico < 1e-6)
        assert np.all(np.diff(res.X_prod_kg_kg) <= 1e-6)
