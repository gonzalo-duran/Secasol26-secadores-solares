"""Tests del orquestador de cálculo global (calculos/balance_global.py)."""

from __future__ import annotations

import pytest

from calculos.balance_global import (
    ResultadosCompletos,
    calcular_todo,
    verificar_coherencia_proyecto,
)
from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import Camara, CargaProducto, ConfiguracionFlujo
from core.colector import Colector
from core.motor import Motor, TipoAccionamiento
from core.proyecto import (
    Configuracion, Meta, ModoAnalisis, Proyecto, Tipologia,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def proyecto_armario_completo():
    """Proyecto ARMARIO con colector + cámara + motor configurados."""
    p = Proyecto(
        meta=Meta(nombre="Test P7", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.colector = Colector()
    p.camara = Camara(
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
    )
    p.motor = Motor(
        tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
        caudal_volumetrico_m3_s=0.025,
        perdida_carga_total_Pa=50.0,
    )
    return p


@pytest.fixture
def proyecto_camara_solo():
    """Proyecto con solo cámara (sin colector) — válido si auxiliar es respaldo."""
    p = Proyecto(
        meta=Meta(nombre="Solo camara", autor="pytest"),
        configuracion=Configuracion(tipologia=Tipologia.ARMARIO,
                                    modo_analisis=ModoAnalisis.DIARIO),
    )
    p.camara = Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=5.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        )
    )
    return p


# ---------------------------------------------------------------------------
# verificar_coherencia_proyecto
# ---------------------------------------------------------------------------


class TestVerificarCoherencia:

    def test_proyecto_valido_sin_errores(self, proyecto_armario_completo):
        errores = verificar_coherencia_proyecto(proyecto_armario_completo)
        assert errores == []

    def test_caja_con_colector(self):
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.CAJA,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.colector = Colector()
        errores = verificar_coherencia_proyecto(p)
        assert any("PROY_CAJA_CON_COLECTOR" in e for e in errores)

    def test_caja_con_motor(self):
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.CAJA,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.02,
            perdida_carga_total_Pa=30.0,
        )
        errores = verificar_coherencia_proyecto(p)
        assert any("PROY_CAJA_CON_MOTOR" in e for e in errores)

    def test_auxiliar_serie_sin_colector(self):
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.ARMARIO,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.camara = Camara()
        p.auxiliar = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=1000.0,
            temperatura_maxima_salida_K=343.15,
        )
        errores = verificar_coherencia_proyecto(p)
        assert any("PROY_AUXILIAR_SERIE_SIN_COLECTOR" in e for e in errores)

    def test_motor_sin_camara(self):
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.ARMARIO,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.02,
            perdida_carga_total_Pa=30.0,
        )
        errores = verificar_coherencia_proyecto(p)
        assert any("PROY_MOTOR_SIN_CAMARA" in e for e in errores)


# ---------------------------------------------------------------------------
# calcular_todo
# ---------------------------------------------------------------------------


class TestCalcularTodo:

    def test_retorna_ResultadosCompletos(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15,
            I_g_W_m2=800.0,
            v_viento_ms=2.0,
            T_entrada_K=298.15,
            HR_camara=0.20,
        )
        assert isinstance(res, ResultadosCompletos)

    def test_sin_errores_proyecto_valido(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.errores == []

    def test_colector_calculado(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.colector is not None
        assert res.colector.T_salida_K > 298.15

    def test_camara_calculada(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.camara is not None
        assert res.camara.t_secado_s > 0

    def test_T_entrada_camara_igual_T_salida_col_sin_auxiliar(
        self, proyecto_armario_completo
    ):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.T_entrada_camara_K == pytest.approx(
            res.colector.T_salida_K, rel=1e-6
        )

    def test_balance_energetico_calculado(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.energia_total_MJ is not None
        assert res.energia_total_MJ > 0

    def test_COP_positivo(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.COP_secado is not None
        assert res.COP_secado > 0

    def test_sin_colector_camara_usa_T_amb(self, proyecto_camara_solo):
        T_amb = 313.15
        res = calcular_todo(
            proyecto_camara_solo,
            T_amb_K=T_amb, I_g_W_m2=0.0, v_viento_ms=2.0,
            T_entrada_K=T_amb, HR_camara=0.20,
        )
        assert res.colector is None
        assert res.T_entrada_camara_K == pytest.approx(T_amb, rel=1e-6)
        assert res.camara is not None

    def test_errores_con_proyecto_incoherente(self):
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.CAJA,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.colector = Colector()  # CAJA + colector = error cruzado
        p.camara = Camara()
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert len(res.errores) > 0

    def test_auxiliar_encadenado(self):
        """Con auxiliar, T_entrada_camara > T_salida_colector."""
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.ARMARIO,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.colector = Colector()
        p.camara = Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        p.auxiliar = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=1000.0,
            temperatura_maxima_salida_K=353.15,
        )
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.auxiliar is not None
        # T_entrada_camara debe ser >= T_salida_colector
        assert res.T_entrada_camara_K >= res.colector.T_salida_K - 0.01

    def test_fraccion_solar_uno_sin_auxiliar(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        # Sin auxiliar, fraccion_solar = 1.0
        assert res.fraccion_solar == pytest.approx(1.0, abs=1e-6)

    def test_rendimiento_masa_positivo(self, proyecto_armario_completo):
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.rendimiento_masa is not None
        assert 0 < res.rendimiento_masa < 1

    def test_I_g_cero_reduce_T_salida(self):
        """Sin irradiancia, el colector no aporta calor útil."""
        p = Proyecto(
            configuracion=Configuracion(tipologia=Tipologia.ARMARIO,
                                        modo_analisis=ModoAnalisis.DIARIO),
        )
        p.colector = Colector()
        p.camara = Camara()
        res_con = calcular_todo(p, T_amb_K=298.15, I_g_W_m2=800.0,
                                v_viento_ms=2.0, T_entrada_K=298.15,
                                HR_camara=0.20)
        res_sin = calcular_todo(p, T_amb_K=298.15, I_g_W_m2=0.0,
                                v_viento_ms=2.0, T_entrada_K=298.15,
                                HR_camara=0.20)
        assert res_con.colector.T_salida_K > res_sin.colector.T_salida_K
