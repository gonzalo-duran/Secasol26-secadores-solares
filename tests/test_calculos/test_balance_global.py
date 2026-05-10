"""Tests del orquestador de cálculo global (calculos/balance_global.py)."""

from __future__ import annotations

import pytest

from calculos.balance_global import (
    ResultadosCompletos,
    calcular_todo,
    verificar_coherencia_proyecto,
)
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import (
    Camara, CargaProducto, ConfiguracionBandejas, ConfiguracionFlujo,
    GeometriaCamara,
)
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


# ---------------------------------------------------------------------------
# Despacho del motor termodinámico de cámara
# ---------------------------------------------------------------------------


class TestModoTermodinamico:
    """Cuando ``camara.modo_calculo='termodinamico'`` el balance global debe
    consumir las salidas del motor termodinámico (no de capa fina) y manejar
    correctamente el caso de no-convergencia."""

    @pytest.fixture
    def proyecto_yacon_TD(self):
        """ARMARIO + colector + cámara TD con yacón (GAB calibrada → converge)."""
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.ARMARIO, modo_analisis=ModoAnalisis.DIARIO,
            ),
        )
        p.colector = Colector()
        p.camara = Camara(
            geometria=GeometriaCamara(largo_m=0.6, ancho_m=0.4, alto_m=0.6),
            bandejas=ConfiguracionBandejas(
                n_bandejas=3, area_bandeja_m2=0.20,
                espesor_capa_m=0.015, separacion_entre_bandejas_m=0.06,
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
        return p

    def test_devuelve_ResultadoMotorTermodinamico(self, proyecto_yacon_TD):
        res = calcular_todo(
            proyecto_yacon_TD,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.15,
        )
        assert isinstance(res.camara, ResultadoMotorTermodinamico)
        assert res.camara.status == "X_obj_alcanzado"

    def test_balance_energetico_calculado_cuando_converge(self, proyecto_yacon_TD):
        res = calcular_todo(
            proyecto_yacon_TD,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.15,
        )
        # Con TD convergente, el balance global debe poblarse igual que con capa fina.
        assert res.energia_total_MJ is not None
        assert res.energia_solar_util_MJ is not None
        assert res.energia_secado_MJ is not None
        assert res.COP_secado is not None
        assert res.COP_secado > 0

    def test_masa_agua_usa_masa_evaporada_total(self, proyecto_yacon_TD):
        """E_secado = masa_evaporada_total × Lv (no masa_agua_extraida)."""
        res = calcular_todo(
            proyecto_yacon_TD,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.15,
        )
        from core.resultados import LV_AGUA_MJ_KG
        assert res.energia_secado_MJ == pytest.approx(
            res.camara.masa_evaporada_total_kg * LV_AGUA_MJ_KG, rel=1e-9,
        )

    def test_no_convergencia_emite_advertencia_y_energias_None(self):
        """Manzana sin GAB con HR alta → fallback aw lineal se atasca → no llega
        a X_obj. El balance global no calcula energías y emite BG_TD_NO_CONVERGE."""
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.ARMARIO, modo_analisis=ModoAnalisis.DIARIO,
            ),
        )
        p.colector = Colector()
        p.camara = Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="manzana",         # sin GAB → fallback aw lineal
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.10,
                modelo_capa_fina="logaritmico",
            ),
            modo_calculo="termodinamico",
        )
        res = calcular_todo(
            p,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15,
            HR_camara=0.50,                    # alta → atasca el fallback
        )
        assert isinstance(res.camara, ResultadoMotorTermodinamico)
        assert res.camara.t_secado_s is None
        assert res.camara.status == "t_max_alcanzado"
        assert any("BG_TD_NO_CONVERGE" in a for a in res.advertencias)
        assert res.energia_total_MJ is None
        assert res.energia_solar_util_MJ is None
        assert res.COP_secado is None
        # Pero la masa de producto seco SÍ se calcula (no depende de t_secado).
        assert res.masa_producto_seco_kg is not None
        assert res.masa_producto_seco_kg > 0
