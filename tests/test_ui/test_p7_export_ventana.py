"""Tests de la exportación de P7 en modo Ventana (gran escala).

Antes del fix, ``_render_ventana`` retornaba sin llamar a
``_render_botones_guardado``: en modo VENTANA no había TXT, JSON ni PDF.
Los generadores deben tolerar ``ResultadoVentana`` y la ausencia de las
condiciones representativas de Constantes (``T_amb_C=None`` etc.).
"""

from __future__ import annotations

import numpy as np

from calculos.simulacion_ventana import ResultadoVentana
from core.proyecto import Proyecto


def _res_ventana_batch() -> ResultadoVentana:
    return ResultadoVentana(
        subtipo="BATCH",
        horizonte_s=7 * 86400.0,
        masa_seca_producida_kg=120.0,
        masa_evaporada_kg=480.0,
        tasa_regimen_kg_dia=17.0,
        n_batches_completos=3,
        t_secado_medio_s=2.1 * 86400.0,
        batch_en_progreso=True,
        lena_consumida_kg=35.0,
        status="ok",
    )


def _res_ventana_semicontinuo() -> ResultadoVentana:
    return ResultadoVentana(
        subtipo="SEMICONTINUO",
        horizonte_s=30 * 86400.0,
        masa_seca_producida_kg=900.0,
        masa_evaporada_kg=4100.0,
        tasa_regimen_kg_dia=30.0,
        n_avances=60,
        X_salida_regimen=0.18,
        throughput_fresco_kg_dia=170.0,
        perfil_X_zonas=np.array([3.5, 2.4, 1.1, 0.4]),
        perfil_T_aire_zonas_K=np.array([330.0, 327.0, 324.0, 321.0]),
        X_salida_por_avance=np.array([0.5, 0.3, 0.2]),
        intervalo_avance_s=7200.0,
        lena_consumida_kg=210.0,
        status="regimen_alcanzado",
    )


class TestTextoConCondicionesOpcionales:
    """El TXT omite el bloque de condiciones P7 cuando no hay sliders (ventana)."""

    def test_sin_condiciones_no_emite_bloque(self):
        from ui.p7_resultados import _texto_resultados_completo

        texto = _texto_resultados_completo(Proyecto(), _res_ventana_batch())
        assert "CONDICIONES DE OPERACIÓN REPRESENTATIVAS" not in texto
        assert "PREDISEÑO COMPLETO" in texto

    def test_con_condiciones_emite_bloque(self):
        from ui.p7_resultados import _texto_resultados_completo

        texto = _texto_resultados_completo(
            Proyecto(), _res_ventana_batch(), T_amb_C=25.0, I_g=800.0, v_viento=2.0, HR_cam_pct=30.0
        )
        assert "CONDICIONES DE OPERACIÓN REPRESENTATIVAS" in texto
        assert "25.0 °C" in texto

    def test_semicontinuo_no_explota(self):
        from ui.p7_resultados import _texto_resultados_completo

        texto = _texto_resultados_completo(Proyecto(), _res_ventana_semicontinuo())
        assert isinstance(texto, str) and len(texto) > 0


class TestHelpersVentana:
    """Helpers puros del bloque de ventana (TXT + JSON)."""

    def test_texto_batch(self):
        from ui.p7_resultados import _texto_resultado_ventana

        texto = "\n".join(_texto_resultado_ventana(_res_ventana_batch()))
        assert "PRODUCCIÓN EN VENTANA" in texto
        assert "LOTES (BATCH)" in texto
        assert "120.0 kg" in texto
        assert "35.0 kg" in texto  # leña
        assert "TÚNEL SEMICONTINUO" not in texto

    def test_texto_semicontinuo_con_perfil(self):
        from ui.p7_resultados import _texto_resultado_ventana

        texto = "\n".join(_texto_resultado_ventana(_res_ventana_semicontinuo()))
        assert "TÚNEL SEMICONTINUO" in texto
        assert "Zona 1" in texto and "Zona 4" in texto
        assert "Throughput" in texto

    def test_texto_cano_maestro(self):
        from ui.p7_resultados import _texto_resultado_ventana

        res = _res_ventana_batch()
        res.cano_delta_T_media_K = -1.8
        res.cano_delta_T_minima_K = -4.2
        res.cano_delta_P_Pa = 55.0
        texto = "\n".join(_texto_resultado_ventana(res))
        assert "CAÑO MAESTRO" in texto
        assert "-4.20 K" in texto
        # Sin caño (None) el bloque no aparece.
        texto_sin = "\n".join(_texto_resultado_ventana(_res_ventana_batch()))
        assert "CAÑO MAESTRO" not in texto_sin

    def test_json_ventana_serializa(self):
        import json

        from ui.componentes.serializacion import dump_json
        from ui.p7_resultados import _json_resultado_ventana

        d = _json_resultado_ventana(_res_ventana_semicontinuo())
        assert d["subtipo"] == "SEMICONTINUO"
        assert d["perfil_X_zonas"] == [3.5, 2.4, 1.1, 0.4]
        assert d["X_salida_por_avance"] == [0.5, 0.3, 0.2]
        # Round-trip JSON real (sin ndarray remanente).
        rt = json.loads(dump_json(d))
        assert rt["n_avances"] == 60


def _res_anual_sintetico():
    from calculos.operacion_anual_camara import PuntoMensualCamara, ResultadosAnualCamara

    puntos = [
        PuntoMensualCamara(
            mes=m,
            t_secado_h=20.0 + m,
            convergio=(m != 6),
            m_evap_kg_por_batch=8.0,
            eta_drying=0.02,
            eta_pickup=0.3,
            eta_termica=0.5,
            eta_total=0.01,
            E_solar_batch_MJ=100.0,
            E_auxiliar_batch_MJ=0.0,
            n_batches=4,
            kg_secados_mes=32.0,
        )
        for m in range(1, 13)
    ]
    return ResultadosAnualCamara(
        puntos_mensuales=puntos,
        kg_secados_anual=384.0,
        eta_drying_anual_media=0.02,
        eta_pickup_anual_media=0.3,
        eta_termica_anual_media=0.5,
        eta_total_anual_media=0.01,
        E_solar_anual_MJ=4800.0,
        E_auxiliar_anual_MJ=0.0,
        t_secado_promedio_h=26.0,
    )


class TestHelpersAnual:
    def test_texto_anual(self):
        from ui.p7_resultados import _texto_operacion_anual

        texto = "\n".join(_texto_operacion_anual(_res_anual_sintetico()))
        assert "OPERACIÓN ANUAL DE CÁMARA" in texto
        assert "384.0 kg" in texto
        assert "DETALLE MENSUAL" in texto
        # 12 filas mensuales
        assert texto.count(" | ") >= 12

    def test_json_anual(self):
        import json

        from ui.componentes.serializacion import dump_json
        from ui.p7_resultados import _json_operacion_anual

        d = _json_operacion_anual(_res_anual_sintetico())
        assert len(d["puntos_mensuales"]) == 12
        assert d["puntos_mensuales"][5]["convergio"] is False
        assert json.loads(dump_json(d))["kg_secados_anual"] == 384.0

    def test_txt_completo_incluye_anual(self):
        from ui.p7_resultados import _texto_resultados_completo

        texto = _texto_resultados_completo(
            Proyecto(), _res_ventana_batch(), res_anual=_res_anual_sintetico()
        )
        assert "PRODUCCIÓN EN VENTANA" in texto
        assert "OPERACIÓN ANUAL DE CÁMARA" in texto


class TestJsonConCondicionesOpcionales:
    def test_condiciones_none_serializa(self):
        from ui.componentes.serializacion import dump_json
        from ui.p7_resultados import _json_resultados_completo

        # _json_resultados_completo lee st.session_state.get("p3_eval") — en un
        # test sin servidor el session_state real de streamlit funciona vacío.
        snap = _json_resultados_completo(Proyecto(), _res_ventana_semicontinuo())
        cond = snap["condiciones_operacion_P7"]
        assert cond == {
            "T_amb_C": None,
            "I_g_POA_W_m2": None,
            "v_viento_ms": None,
            "HR_camara_pct": None,
        }
        # Round-trip serializable completo (ndarray, None, etc.).
        assert dump_json(snap)
