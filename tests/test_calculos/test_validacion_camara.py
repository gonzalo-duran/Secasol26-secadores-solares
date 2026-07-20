"""Tests de la orquestación de validación de cámara/producto (mejora 38, fase 4, E3).

Cubre: las perillas de calibración ``factor_h_conv``/``factor_K_m`` (neutras por
default), la extracción de series simuladas con timestamps absolutos, los dos
objetos de comparación del túnel (descargas y perfiles) y la recuperación del
parámetro inyectado por ``calibrar_1d``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.calibracion import calibrar_1d
from calculos.camara_calc import calcular_camara
from calculos.ingesta_referencia import ingerir_forzantes_camara
from calculos.validacion_camara import (
    a_display,
    evaluar_camara,
    pares_descarga_tunel,
    perfil_zonas,
    serie_simulada,
    simular_camara_aislada,
    unidad_display,
)
from core.camara import Camara, CargaProducto
from core.validacion import ConfigReferencia, SenalReferencia

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def camara():
    """Cámara de armario con manzana (mismo patrón que test_camara_dispatcher)."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
        modo_calculo="termodinamico",
    )


def _df_ensayo(n: int = 25, paso_min: int = 30) -> pd.DataFrame:
    """Ensayo de cámara: aire de entrada caliente y seco, 12 h."""
    idx = pd.date_range("2010-05-01 08:00", periods=n, freq=f"{paso_min}min")
    return pd.DataFrame(
        {
            "fecha": idx.strftime("%Y-%m-%d %H:%M:%S"),
            "T_in": [45.0] * n,
            "HR_in": [20.0] * n,
            "Tamb": [20.0] * n,
        }
    )


def _forzantes(variable: str = "X_producto", unidad: str = "kg_kg"):
    cfg = ConfigReferencia(
        columna_timestamp="fecha",
        columna_valor="T_in",
        variable=variable,
        unidad=unidad,
        zona_horaria="UTC",
    )
    return ingerir_forzantes_camara(
        _df_ensayo(),
        cfg,
        columna_T_ent="T_in",
        columna_HR_ent="HR_in",
        columna_T_amb="Tamb",
        m_dot_fijo_kg_s=0.05,
    )


# ---------------------------------------------------------------------------
# Perillas de calibración
# ---------------------------------------------------------------------------


class TestFactoresDeCalibracion:

    def test_factores_neutros_dan_resultado_identico(self, camara):
        """Default 1.0 ⇒ bit-idéntico al camino histórico (ningún test previo cambia)."""
        fm = _forzantes()
        base = calcular_camara(
            camara,
            T_operacion_K=318.15,
            HR_operacion=0.2,
            T_amb_K=293.15,
            t_max_s=float(fm.forzantes.t_s[-1]),
            forzantes_aire=fm.forzantes,
        )
        con_factores = calcular_camara(
            camara,
            T_operacion_K=318.15,
            HR_operacion=0.2,
            T_amb_K=293.15,
            t_max_s=float(fm.forzantes.t_s[-1]),
            forzantes_aire=fm.forzantes,
            factor_h_conv=1.0,
            factor_K_m=1.0,
        )
        assert np.array_equal(base.X_prod_kg_kg, con_factores.X_prod_kg_kg)
        assert base.masa_evaporada_total_kg == con_factores.masa_evaporada_total_kg

    def test_factor_K_m_mayor_seca_mas_rapido(self, camara):
        """Monotonía física: más transferencia de masa ⇒ X baja más rápido."""
        fm = _forzantes()
        lento = simular_camara_aislada(camara, fm.forzantes, factor_K_m=0.5)
        base = simular_camara_aislada(camara, fm.forzantes)
        rapido = simular_camara_aislada(camara, fm.forzantes, factor_K_m=2.0)
        X_fin = [float(r.X_prod_kg_kg[-1]) for r in (lento, base, rapido)]
        assert X_fin[0] > X_fin[1] > X_fin[2]
        evap = [float(r.masa_evaporada_total_kg) for r in (lento, base, rapido)]
        assert evap[0] < evap[1] < evap[2]

    def test_factor_h_conv_arrastra_la_transferencia_de_masa(self, camara):
        """K_m sale de h por Chilton-Colburn: escalar h también escala la evaporación."""
        fm = _forzantes()
        base = simular_camara_aislada(camara, fm.forzantes)
        con_h = simular_camara_aislada(camara, fm.forzantes, factor_h_conv=2.0)
        assert float(con_h.X_prod_kg_kg[-1]) < float(base.X_prod_kg_kg[-1])


# ---------------------------------------------------------------------------
# Series simuladas
# ---------------------------------------------------------------------------


class TestSerieSimulada:

    def test_timestamps_absolutos_anclados_en_t0(self, camara):
        fm = _forzantes()
        res = simular_camara_aislada(camara, fm.forzantes)
        ts, y = serie_simulada(res, "T_camara", fm.t0_utc)
        assert len(ts) == len(y) == len(res.t_array_s)
        assert ts[0] == fm.t0_utc
        assert str(ts.tz) == "UTC"
        # El desplazamiento respeta t_array_s.
        assert (ts[-1] - ts[0]).total_seconds() == pytest.approx(float(res.t_array_s[-1]))

    @pytest.mark.parametrize(
        "variable,atributo",
        [
            ("T_camara", "T_flujo_K"),
            ("HR_camara", "HR_flujo"),
            ("T_producto", "T_prod_K"),
            ("X_producto", "X_prod_kg_kg"),
            ("masa_producto", "X_prod_kg_kg"),
        ],
    )
    def test_cada_variable_mapea_a_su_serie(self, camara, variable, atributo):
        fm = _forzantes()
        res = simular_camara_aislada(camara, fm.forzantes)
        _, y = serie_simulada(res, variable, fm.t0_utc)
        assert np.array_equal(y, np.asarray(getattr(res, atributo), dtype=float))

    def test_VCAM_VARIABLE_NO_SIMULADA(self, camara):
        fm = _forzantes()
        res = simular_camara_aislada(camara, fm.forzantes)
        with pytest.raises(ValueError, match="VCAM_VARIABLE_NO_SIMULADA"):
            serie_simulada(res, "T_salida_colector", fm.t0_utc)

    def test_unidades_de_display(self):
        assert unidad_display("T_camara") == "°C"
        assert unidad_display("HR_camara") == "%"
        assert unidad_display("X_producto") == "kg/kg"
        assert a_display(np.array([313.15]), "T_producto")[0] == pytest.approx(40.0)
        assert a_display(np.array([0.35]), "HR_camara")[0] == pytest.approx(35.0)
        assert a_display(np.array([4.0]), "X_producto")[0] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# Evaluación y calibración
# ---------------------------------------------------------------------------


class TestEvaluarYCalibrar:

    def _senal_desde_simulacion(self, camara, fm, variable, factor_K_m):
        """Genera una señal 'medida' sintética corriendo el propio motor."""
        res = simular_camara_aislada(camara, fm.forzantes, factor_K_m=factor_K_m)
        ts, y = serie_simulada(res, variable, fm.t0_utc)
        # Submuestreo de los propios puntos del solver (como una planilla de campo
        # con pocas pesadas). Ojo: `resample().first()` etiquetaría el valor en el
        # borde del bin aunque el dato sea de otro instante → sesgo espurio.
        serie = pd.Series(y, index=ts).iloc[::7].dropna()
        return SenalReferencia(
            variable=variable,
            serie=serie,
            unidad_origen="kg_kg",
            frecuencia_nativa_s=3600.0,
        )

    def test_ajuste_perfecto_cuando_el_factor_coincide(self, camara):
        fm = _forzantes()
        senal = self._senal_desde_simulacion(camara, fm, "X_producto", factor_K_m=1.0)
        metricas, _ = evaluar_camara(camara, senal, fm.forzantes, fm.t0_utc)
        assert metricas is not None
        assert metricas.rmse == pytest.approx(0.0, abs=1e-6)
        assert metricas.n_pares > 3

    def test_calibrar_recupera_el_factor_inyectado(self, camara):
        """Test de recuperación de parámetro (verificación E3 del plan)."""
        fm = _forzantes()
        senal = self._senal_desde_simulacion(camara, fm, "X_producto", factor_K_m=1.5)

        def _evaluar(valor):
            metricas, _ = evaluar_camara(camara, senal, fm.forzantes, fm.t0_utc, factor_K_m=valor)
            return metricas

        res = calibrar_1d(
            np.linspace(0.5, 2.5, 9), _evaluar, parametro="factor_K_m", objetivo="rmse"
        )
        assert res.valor_optimo == pytest.approx(1.5, abs=0.13)  # paso de la grilla = 0.25
        assert res.metricas_optimo.rmse < 1e-6

    def test_sin_solape_temporal_metricas_none(self, camara):
        fm = _forzantes()
        idx = pd.date_range("2011-01-01", periods=5, freq="h", tz="UTC")
        senal = SenalReferencia(
            variable="X_producto",
            serie=pd.Series(np.linspace(4.0, 1.0, 5), index=idx),
            unidad_origen="kg_kg",
            frecuencia_nativa_s=3600.0,
        )
        metricas, _ = evaluar_camara(camara, senal, fm.forzantes, fm.t0_utc)
        assert metricas is None


# ---------------------------------------------------------------------------
# Túnel semicontinuo: descargas y perfiles
# ---------------------------------------------------------------------------


class TestTunel:

    @pytest.fixture
    def resultado_cascada(self, camara):
        from calculos.camara_calc import calcular_camara_cascada
        from core.camara import ConfiguracionTunel

        cam = Camara(
            carga_producto=camara.carga_producto,
            modo_calculo="termodinamico",
            tunel=ConfiguracionTunel(n_zonas=3, intervalo_avance_h=2.0),
        )
        fm = _forzantes()
        return (
            calcular_camara_cascada(
                cam,
                T_operacion_K=318.15,
                HR_operacion=0.2,
                forzantes_aire=fm.forzantes,
            ),
            fm,
        )

    def test_descargas_un_punto_por_avance(self, resultado_cascada):
        res, fm = resultado_cascada
        ts, y = pares_descarga_tunel(res, fm.t0_utc)
        assert len(ts) == len(y) == res.n_avances
        # La primera descarga ocurre al cumplirse el primer intervalo de avance.
        assert (ts[0] - fm.t0_utc).total_seconds() == pytest.approx(res.intervalo_avance_s)

    def test_descarga_de_temperatura(self, resultado_cascada):
        res, fm = resultado_cascada
        _, y = pares_descarga_tunel(res, fm.t0_utc, variable="T_producto")
        assert np.array_equal(y, np.asarray(res.T_prod_salida_por_avance_K, dtype=float))

    def test_VCAM_VARIABLE_NO_DESCARGA(self, resultado_cascada):
        res, fm = resultado_cascada
        with pytest.raises(ValueError, match="VCAM_VARIABLE_NO_DESCARGA"):
            pares_descarga_tunel(res, fm.t0_utc, variable="HR_camara")

    def test_perfil_por_zona(self, resultado_cascada):
        res, _ = resultado_cascada
        perfil = perfil_zonas(res, "X_producto")
        assert len(perfil) == res.n_zonas
        assert np.array_equal(perfil, np.asarray(res.X_perfil_zonas, dtype=float))

    def test_VCAM_VARIABLE_SIN_PERFIL(self, resultado_cascada):
        res, _ = resultado_cascada
        with pytest.raises(ValueError, match="VCAM_VARIABLE_SIN_PERFIL"):
            perfil_zonas(res, "HR_camara")
