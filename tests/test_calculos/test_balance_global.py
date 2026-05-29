"""Tests del orquestador de cálculo global (calculos/balance_global.py)."""

from __future__ import annotations

import numpy as np
import pytest

from calculos.balance_global import (
    ResultadosCompletos,
    armar_forzantes_aire,
    calcular_todo,
    construir_serie_sintetica_dia_tipo,
    verificar_coherencia_proyecto,
)
from calculos.camara_calc import calcular_camara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.psicrometria import humedad_absoluta
from core.camara import ForzantesAire
from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import (
    Camara, CargaProducto, ConfiguracionBandejas, ConfiguracionFlujo,
    GeometriaCamara,
)
from core.chimenea import Chimenea
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
        modo_calculo="capa_fina",
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
# Integración de chimenea solar (caudal natural en ausencia de motor)
# ---------------------------------------------------------------------------


class TestChimeneaIntegrada:
    """Verifica que ``calcular_todo`` activa el cálculo de caudal natural
    cuando hay chimenea + sin motor, y deja el resto del flujo intacto en
    otros casos. La integración mutea temporalmente
    ``proyecto.camara.flujo.caudal_masico_kg_s`` para que la cámara
    consuma el caudal natural, restaurándolo después."""

    def _proyecto_chimenea(self) -> Proyecto:
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.ARMARIO, modo_analisis=ModoAnalisis.DIARIO,
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
        # motor = None (default), chimenea presente
        p.chimenea = Chimenea(diametro_m=0.25, altura_m=3.0)
        return p

    def test_sin_chimenea_res_chimenea_es_None(self, proyecto_armario_completo):
        """Proyecto con motor y sin chimenea: res.chimenea no se computa."""
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.chimenea is None

    def test_chimenea_con_motor_no_se_invoca(self, proyecto_armario_completo):
        """Si hay motor además de chimenea, el motor manda — no se computa."""
        proyecto_armario_completo.chimenea = Chimenea(diametro_m=0.25, altura_m=3.0)
        res = calcular_todo(
            proyecto_armario_completo,
            T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.chimenea is None

    def test_sin_motor_con_chimenea_calcula_caudal(self):
        """motor=None + chimenea → res.chimenea poblado con dict del solver."""
        p = self._proyecto_chimenea()
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert res.chimenea is not None
        assert "m_punto_kgs" in res.chimenea
        assert "delta_P_tiro_Pa" in res.chimenea
        assert res.chimenea["m_punto_kgs"] > 0.0
        assert res.chimenea["delta_P_tiro_Pa"] > 0.0

    def test_caudal_camara_se_restaura_despues_de_calcular(self):
        """Aunque la integración mutea camara.flujo.caudal_masico_kg_s para
        que la cámara consuma el caudal natural, debe restaurarse antes de
        que calcular_todo retorne — no contaminamos el proyecto del usuario."""
        p = self._proyecto_chimenea()
        caudal_orig = p.camara.flujo.caudal_masico_kg_s
        calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert p.camara.flujo.caudal_masico_kg_s == caudal_orig

    def test_caudal_natural_difiere_del_diseno(self):
        """El caudal de equilibrio típicamente no coincide con el caudal de
        diseño que el usuario puso en P4 — la chimenea impone su propio
        punto de operación."""
        p = self._proyecto_chimenea()
        caudal_design = p.camara.flujo.caudal_masico_kg_s
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        # No es razonable exigir un valor exacto, pero deberían diferir > 1%
        # en casi cualquier configuración no-trivial.
        rel_diff = abs(res.chimenea["m_punto_kgs"] - caudal_design) / caudal_design
        assert rel_diff > 0.01

    def test_balance_chimenea_se_cierra(self):
        """En el equilibrio: ΔP_tiro = ΔP_chimenea + ΔP_resto."""
        p = self._proyecto_chimenea()
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        ch = res.chimenea
        assert ch["delta_P_tiro_Pa"] == pytest.approx(
            ch["delta_P_chimenea_Pa"] + ch["delta_P_resto_Pa"], rel=1e-5,
        )

    def test_caja_con_chimenea_funciona(self):
        """Tipología CAJA (sin colector) + chimenea: no debe fallar y
        debe producir un caudal natural con T_chim fallback."""
        from core.camara import GeometriaCamara
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.CAJA, modo_analisis=ModoAnalisis.DIARIO,
            ),
        )
        # CAJA requiere cubierta translúcida en la cámara
        from core.camara import ConstruccionCamara
        p.camara = Camara(
            geometria=GeometriaCamara(largo_m=1.0, ancho_m=0.8, alto_m=1.2),
            construccion=ConstruccionCamara(cubierta_translucida_id="vidrio_comun"),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.020),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=5.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        p.chimenea = Chimenea(diametro_m=0.20, altura_m=2.5)
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        # No errores fatales; chimenea calculada
        assert res.errores == [] or all("CAMARA" not in e for e in res.errores)
        assert res.chimenea is not None
        assert res.chimenea["m_punto_kgs"] > 0.0

    def test_picard_metadata_presente(self):
        """El dict res.chimenea debe traer la metadata del Picard."""
        p = self._proyecto_chimenea()
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        ch = res.chimenea
        for k in ("iteraciones", "convergio", "delta_T_chim_final_K", "T_chim_K"):
            assert k in ch, f"Falta {k!r} en res.chimenea"
        assert isinstance(ch["iteraciones"], int) and ch["iteraciones"] >= 1
        assert isinstance(ch["convergio"], bool)

    def test_picard_converge_armario(self):
        """ARMARIO típico: el lazo natural converge dentro del máximo de
        iteraciones permitido y ΔT_chim final < tolerancia."""
        p = self._proyecto_chimenea()
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        ch = res.chimenea
        assert ch["convergio"] is True
        assert ch["delta_T_chim_final_K"] < 0.5
        assert ch["iteraciones"] <= 10

    def test_picard_re_corre_colector(self):
        """El colector debe re-correrse con la velocidad efectiva del lazo
        natural: el Q_util / η resultantes responden al ṁ convergido, no
        a la velocidad de diseño que puso el usuario en P3."""
        p = self._proyecto_chimenea()
        # Corrida 1: D, H = (0.25, 3.0) → ṁ_nat distinto a corrida 2.
        res1 = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        # Corrida 2: chimenea más grande (D=0.40, H=5.0) → más tiro, ṁ mayor.
        p.chimenea = Chimenea(diametro_m=0.40, altura_m=5.0)
        res2 = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        # ṁ mayor con chimenea más grande
        assert res2.chimenea["m_punto_kgs"] > res1.chimenea["m_punto_kgs"]
        # Cambia el colector también (Q_util responde a v efectiva).
        assert res1.colector.Q_util_W != pytest.approx(res2.colector.Q_util_W, rel=1e-3)

    def test_picard_caja_converge_trivialmente(self):
        """CAJA sin colector: T_chim no depende del lazo (heurística estática
        T_amb + 25 K), Picard converge en 1 iter."""
        from core.camara import GeometriaCamara, ConstruccionCamara
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.CAJA, modo_analisis=ModoAnalisis.DIARIO,
            ),
        )
        p.camara = Camara(
            geometria=GeometriaCamara(largo_m=1.0, ancho_m=0.8, alto_m=1.2),
            construccion=ConstruccionCamara(cubierta_translucida_id="vidrio_comun"),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.020),
            carga_producto=CargaProducto(
                producto_id="manzana", masa_total_kg=5.0,
                humedad_inicial_X=4.6, humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        p.chimenea = Chimenea(diametro_m=0.20, altura_m=2.5)
        res = calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        ch = res.chimenea
        assert ch["convergio"] is True
        assert ch["iteraciones"] == 1

    def test_picard_restaura_v_diseno_colector(self):
        """La mutación temporal de velocidad_diseno_ms del colector debe
        restaurarse al valor original tras calcular_todo (igual que el
        caudal de la cámara)."""
        p = self._proyecto_chimenea()
        v_diseno_orig = p.colector.unidad.velocidad_diseno_ms
        calcular_todo(
            p, T_amb_K=298.15, I_g_W_m2=800.0, v_viento_ms=2.0,
            T_entrada_K=298.15, HR_camara=0.20,
        )
        assert p.colector.unidad.velocidad_diseno_ms == v_diseno_orig


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


# ===========================================================================
# Fase 3: construir_serie_sintetica_dia_tipo + wire-up forzantes_aire
# ===========================================================================


class TestSerieSinteticaDiaTipo:
    """Generador de forzantes senoidales día/noche."""

    def test_estructura_basica_24h_un_dia(self):
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=0.008,
            m_dot_aire_seco_kg_s=0.05,
        )
        assert isinstance(fz, ForzantesAire)
        assert len(fz.t_s) == 24
        assert fz.t_s[0] == 0.0
        assert fz.t_s[-1] == 23 * 3600.0

    def test_T_pico_al_mediodia(self):
        """Por default el pico está a las 12 h."""
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=320.0,
            T_sal_col_amplitud_K=20.0,
            omega_amb=0.008,
            m_dot_aire_seco_kg_s=0.05,
            hora_pico=12.0,
        )
        idx_max = int(np.argmax(fz.T_ent_K))
        assert idx_max == 12

    def test_T_col_no_inferior_a_T_amb(self):
        """El colector no enfría el aire por debajo del ambiente (clamp)."""
        # Caso extremo: amplitud T_col muy alta llevaría T_col < T_amb por la noche
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=305.0,        # cerca del ambiente
            T_sal_col_amplitud_K=30.0,         # amplitud muy grande
            T_amb_promedio_K=295.0,
            T_amb_amplitud_K=5.0,
            omega_amb=0.008,
            m_dot_aire_seco_kg_s=0.05,
        )
        # Tras el clamp, T_ent ≥ T_amb hora a hora
        assert np.all(fz.T_ent_K >= fz.T_amb_K - 1e-9)

    def test_multi_dia_replica(self):
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=0.008,
            m_dot_aire_seco_kg_s=0.05,
            n_dias=3,
        )
        assert len(fz.t_s) == 72
        # Las primeras 24 h coinciden con las últimas 24 h en T_ent (réplica exacta)
        assert np.allclose(fz.T_ent_K[:24], fz.T_ent_K[24:48])
        assert np.allclose(fz.T_ent_K[:24], fz.T_ent_K[48:72])


class TestWireUpForzantes:
    """calcular_camara acepta ForzantesAire externo en modo termodinámico."""

    def _camara_minima(self):
        """Construye una Camara mínima en modo termodinámico para los tests."""
        return Camara(
            geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.5),
            bandejas=ConfiguracionBandejas(n_bandejas=5, area_bandeja_m2=0.5),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.0,
                humedad_objetivo_X=0.20,
                modelo_isoterma="gab",
                modelo_capa_fina="page",
            ),
            modo_calculo="termodinamico",
        )

    def test_modo_termodinamico_sin_forzantes_funciona(self):
        """Si forzantes_aire=None, el wire-up arma degeneradas (comportamiento previo)."""
        cam = self._camara_minima()
        res = calcular_camara(
            cam, T_operacion_K=323.15, HR_operacion=0.30,
            T_amb_K=293.15, t_max_s=12 * 3600.0,
        )
        assert isinstance(res, ResultadoMotorTermodinamico)
        # Con forzantes degeneradas constantes, T_flujo debería ser casi constante
        assert np.std(res.T_flujo_K) < 5.0

    def test_modo_termodinamico_con_forzantes_sinteticas_modula_T_flujo(self):
        """Con forzantes senoidales, T_flujo debe oscilar significativamente."""
        cam = self._camara_minima()
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=15.0,                 # ±15 K día/noche
            omega_amb=humedad_absoluta(0.40, 295.0),
            m_dot_aire_seco_kg_s=0.030,
            T_amb_promedio_K=293.15,
            T_amb_amplitud_K=5.0,
            n_dias=2,
        )
        res = calcular_camara(
            cam, T_operacion_K=323.15, HR_operacion=0.30,
            T_amb_K=293.15, t_max_s=48 * 3600.0,
            forzantes_aire=fz,
        )
        assert isinstance(res, ResultadoMotorTermodinamico)
        # T_flujo debería oscilar siguiendo la forzante
        assert np.std(res.T_flujo_K) > 3.0

    def test_modo_capa_fina_ignora_forzantes(self):
        """capa_fina no usa forzantes_aire; pasar no debe fallar."""
        cam = self._camara_minima()
        cam.modo_calculo = "capa_fina"   # cambio para este test
        # Forzantes válidas pero el motor estático las ignora
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=323.15,
            T_sal_col_amplitud_K=10.0,
            omega_amb=0.008,
            m_dot_aire_seco_kg_s=0.030,
        )
        # No debe lanzar
        res = calcular_camara(
            cam, T_operacion_K=323.15, HR_operacion=0.30,
            forzantes_aire=fz,
        )
        # ResultadosCamara (estático), no ResultadoMotorTermodinamico
        assert not isinstance(res, ResultadoMotorTermodinamico)


class TestArmarForzantesAireYaExistente:
    """Smoke tests para armar_forzantes_aire (ya existía, verificamos integración)."""

    def test_diario_24h(self):
        T_col = np.full(24, 323.15)
        omega = np.full(24, 0.008)
        fz = armar_forzantes_aire(
            modo="diario",
            T_salida_colector_K=T_col,
            omega_ambiente=omega,
            m_dot_aire_seco_kg_s=0.03,
        )
        assert len(fz.t_s) == 24

    def test_multi_dia_replica_correctamente(self):
        T_col = np.linspace(310.0, 330.0, 24)
        omega = np.full(24, 0.008)
        fz = armar_forzantes_aire(
            modo="multi_dia", n_dias=2,
            T_salida_colector_K=T_col,
            omega_ambiente=omega,
            m_dot_aire_seco_kg_s=0.03,
        )
        assert len(fz.t_s) == 48
        assert np.allclose(fz.T_ent_K[:24], fz.T_ent_K[24:])


# ===========================================================================
# Test integral end-to-end: P3 colector + P4 cámara termodinámico multi-día
# ===========================================================================


class TestIntegralEndToEnd:
    """Integración: forzantes sintéticas → motor termodinámico → trayectorias coherentes."""

    def test_multi_dia_sintetico_con_secado_progresivo(self):
        """Con día sintético senoidal de 3 días, X(t) decrece monotónicamente
        durante las horas de operación y la trayectoria es coherente."""
        cam = Camara(
            geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.5),
            bandejas=ConfiguracionBandejas(n_bandejas=5, area_bandeja_m2=0.5),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=5.0,                # carga menor para que converja
                humedad_inicial_X=2.0,
                humedad_objetivo_X=0.30,
                modelo_isoterma="gab",
                modelo_capa_fina="page",
            ),
            modo_calculo="termodinamico",
        )
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=325.15,
            T_sal_col_amplitud_K=15.0,
            omega_amb=humedad_absoluta(0.40, 295.0),
            m_dot_aire_seco_kg_s=0.030,
            T_amb_promedio_K=295.0,
            T_amb_amplitud_K=5.0,
            n_dias=3,
        )
        res = calcular_camara(
            cam, T_operacion_K=325.15, HR_operacion=0.30,
            T_amb_K=295.0, t_max_s=72 * 3600.0,
            forzantes_aire=fz,
        )
        # X final < X inicial (hubo secado, aunque no necesariamente alcanzó X_obj)
        assert res.X_prod_kg_kg[-1] < cam.carga_producto.humedad_inicial_X
        # T_flujo oscila (forzante senoidal)
        assert np.std(res.T_flujo_K) > 2.0
        # Series multi-día completas (al menos múltiples puntos)
        assert len(res.t_array_s) > 10
        # Trayectorias coherentes: sin NaN
        assert np.all(np.isfinite(res.T_prod_K))
        assert np.all(np.isfinite(res.X_prod_kg_kg))
        # T_cam_int siempre <= T_flujo (pared cede calor del aire)
        assert np.all(res.T_cam_int_K <= res.T_flujo_K + 1e-6)
