"""Tests de i18n del reporte PDF (plan i18n, F6).

Verifican que:
1. El closure `tr` traduce contra el namespace `reporte.*` en los 3 idiomas.
2. Las secciones (`_portada`, `_seccion_*`, `_bloque_advertencias`) construyen
   un PDF válido con snapshots sintéticos, ejercitando ramas con y sin datos.
3. La tabla de advertencias del PDF retraduce el mensaje por código reusando
   el namespace `advertencias.*` (F5), con fallback al ES de core.

No requiere clima real ni kaleido: las figuras se pasan vacías (las secciones
caen a su nota de pendiente traducida).
"""

from __future__ import annotations

import io

import pytest
from reportlab.platypus import PageBreak

import ui.reporte as R
from ui.componentes.traducciones import IDIOMAS

_ADV = [
    {
        "codigo": "GEO_LARGO_PEQUENO",
        "severidad": "INFO",
        "mensaje": "MENSAJE ORIGINAL DE CORE",
        "sugerencia": "s",
        "contexto": {"largo_m": 0.3, "largo_min_m": 0.5},
    }
]

_SNAP_COL = {
    "unidad": {
        "tipo_colector": 1,
        "tipo_colector_descripcion": "canal único",
        "ancho_m": 1.0,
        "largo_m": 2.0,
        "espaciado_m": 0.05,
        "n_cubiertas": 1,
        "velocidad_diseno_ms": 1.5,
    },
    "materiales": {
        "cubierta": {
            "id": "vidrio",
            "espesor_m": 0.004,
            "props_catalogo": {"descripcion": "Vidrio"},
        },
        "placa": {"id": "acero"},
        "aislante": {"id": "lana"},
        "fondo": {"id": "chapa"},
    },
    "banco": {"n_serie": 2, "n_paralelo": 3},
    "derivados": {"area_total_m2": 6.0, "caudal_total_m3_s": 0.1, "largo_camino_aire_m": 4.0},
    "resultados": {
        "ejecutado": True,
        "modo": "diario",
        "dia_representativo": "21-jun",
        "resumen": {
            "T_salida_max_C": 60,
            "T_salida_mediodia_C": 55,
            "delta_T_max_C": 30,
            "n_horas_con_radiacion": 9,
        },
    },
    "advertencias_diseno": _ADV,
}


def test_tr_traduce_por_idioma():
    """El closure tr resuelve claves del namespace reporte.* por idioma."""
    assert R._hacer_tr("es")("colector.titulo") == "Colector solar (P3)"
    assert R._hacer_tr("en")("colector.titulo") == "Solar collector (P3)"
    assert R._hacer_tr("pt")("colector.titulo") == "Coletor solar (P3)"
    # Placeholder con nombre y expone .idioma.
    tr_en = R._hacer_tr("en")
    assert tr_en.idioma == "en"
    assert tr_en("colector.banco_val", serie=2, paralelo=3) == "2 series × 3 parallel"


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_pdf_se_construye_en_cada_idioma(idioma):
    """Las secciones traducidas arman un PDF válido con snapshots sintéticos."""
    tr = R._hacer_tr(idioma)
    styles = R._styles()
    story: list = []
    story += R._portada(
        styles,
        tr,
        snap_meta={"nombre": "Demo", "version_software": "0.16"},
        snap_cfg={"tipologia": "ARMARIO", "modo_analisis": "DIARIO"},
        snap_empl={
            "latitud_deg": -24.7,
            "longitud_deg": -65.4,
            "altitud_m": 1200,
            "acimut_colector_deg_duffie": 0,
            "pendiente_colector_deg": 30,
            "zona_horaria": "America/Argentina/Salta",
        },
        snap_clima={"anio": 2020, "n_horas": 8760, "T_amb_media_C": 18, "GHI_media_W_m2": 220},
    )
    story.append(PageBreak())
    story += R._seccion_colector(styles, tr, _SNAP_COL, [])
    story += R._seccion_camara(styles, tr, None, [])  # rama pendiente
    story += R._seccion_auxiliar(styles, tr, None)
    story += R._seccion_motor(styles, tr, None)
    story += R._seccion_chimenea(styles, tr, None, None)
    story += R._seccion_resultados_globales(
        styles,
        tr,
        {
            "energia_total_MJ": 10,
            "camara": {
                "modo_calculo": "termodinamico",
                "t_secado_h": 8,
                "masa_evaporada_kg": 4,
                "status": "ok",
            },
        },
        {"T_amb_C": 20},
        [],
    )

    buf = io.BytesIO()
    doc = R._crear_doc(buf, {"grupo": None, "inenco": None}, "Demo", tr)
    doc.build(story)
    pdf = buf.getvalue()
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_bloque_advertencias_retraduce_por_codigo():
    """El mensaje de la tabla de advertencias se retraduce por código (F5)."""
    tr_en = R._hacer_tr("en")
    styles = R._styles()
    elems = R._bloque_advertencias(styles, tr_en, _ADV)
    # Aplana el texto de todos los Paragraph/celdas de la tabla.
    textos = []
    for e in elems:
        if hasattr(e, "text"):
            textos.append(e.text)
        if hasattr(e, "_cellvalues"):
            for fila in e._cellvalues:
                for celda in fila:
                    if hasattr(celda, "text"):
                        textos.append(celda.text)
    blob = " ".join(textos)
    assert "length" in blob.lower()  # vino del YAML EN
    assert "MENSAJE ORIGINAL DE CORE" not in blob  # no cayó al default de core


def test_bloque_advertencias_fallback_codigo_desconocido():
    """Código sin plantilla YAML → usa el mensaje ES de core (nunca clave cruda)."""
    tr_en = R._hacer_tr("en")
    styles = R._styles()
    advs = [
        {
            "codigo": "CODIGO_QUE_NO_EXISTE",
            "severidad": "WARNING",
            "mensaje": "mensaje core de respaldo",
            "sugerencia": "",
            "contexto": {},
        }
    ]
    elems = R._bloque_advertencias(styles, tr_en, advs)
    tabla = elems[-1]
    celda_msg = tabla._cellvalues[1][2]
    assert celda_msg.text == "mensaje core de respaldo"


# ---------------------------------------------------------------------------
# Secciones nuevas: ventana (gran escala) y operación anual
# ---------------------------------------------------------------------------

_SNAP_VENTANA_SEMI = {
    "subtipo": "SEMICONTINUO",
    "horizonte_s": 30 * 86400.0,
    "masa_seca_producida_kg": 900.0,
    "masa_evaporada_kg": 4100.0,
    "tasa_regimen_kg_dia": 30.0,
    "lena_consumida_kg": 210.0,
    "status": "regimen_alcanzado",
    "n_avances": 60,
    "X_salida_regimen": 0.18,
    "throughput_fresco_kg_dia": 170.0,
    "intervalo_avance_s": 7200.0,
    "perfil_X_zonas": [3.5, 2.4, 1.1, 0.4],
    "perfil_T_aire_zonas_K": [330.0, 327.0, 324.0, 321.0],
    "cano_delta_T_media_K": -1.8,
    "cano_delta_T_minima_K": -4.2,
    "cano_delta_P_Pa": 55.0,
    "advertencias": ["ADV_DEMO: aviso de runtime"],
}

_SNAP_VENTANA_BATCH = {
    "subtipo": "BATCH",
    "horizonte_s": 7 * 86400.0,
    "masa_seca_producida_kg": 120.0,
    "masa_evaporada_kg": 480.0,
    "status": "ok",
    "n_batches_completos": 3,
    "t_secado_medio_s": 2.1 * 86400.0,
    "batch_en_progreso": True,
}

_SNAP_ANUAL = {
    "kg_secados_anual": 384.0,
    "t_secado_promedio_h": 26.0,
    "E_solar_anual_MJ": 4800.0,
    "E_auxiliar_anual_MJ": 0.0,
    "eta_drying_anual_media": 0.02,
    "eta_pickup_anual_media": 0.3,
    "eta_termica_anual_media": 0.5,
    "eta_total_anual_media": 0.01,
    "puntos_mensuales": [
        {
            "mes": m,
            "t_secado_h": 20.0 + m,
            "convergio": m != 6,
            "m_evap_kg_por_batch": 8.0,
            "n_batches": 4,
            "kg_secados_mes": 32.0,
            "eta_total": 0.01,
        }
        for m in range(1, 13)
    ],
}


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_pdf_ventana_y_anual_en_cada_idioma(idioma):
    """Las secciones de ventana (batch/semicontinuo) y anual arman PDF válido."""
    tr = R._hacer_tr(idioma)
    styles = R._styles()
    story: list = []
    story += R._portada(
        styles,
        tr,
        snap_meta={"nombre": "Demo", "version_software": "1.0"},
        snap_cfg={
            "tipologia": "GRAN_ESCALA",
            "modo_analisis": "VENTANA",
            "subtipo_gran_escala": "SEMICONTINUO",
            "ventana_inicio": "2020-05-15",
            "ventana_fin": "2020-06-18",
        },
        snap_empl={},
        snap_clima={},
    )
    story.append(PageBreak())
    story += R._seccion_ventana(styles, tr, _SNAP_VENTANA_SEMI, [])
    story.append(PageBreak())
    story += R._seccion_ventana(styles, tr, _SNAP_VENTANA_BATCH, [])
    story.append(PageBreak())
    story += R._seccion_operacion_anual(styles, tr, _SNAP_ANUAL, [])

    buf = io.BytesIO()
    doc = R._crear_doc(buf, {"grupo": None, "inenco": None}, "Demo", tr)
    doc.build(story)
    assert buf.getvalue().startswith(b"%PDF")


def test_seccion_ventana_sin_cano_ni_lena():
    """Sin caño maestro ni leña, esos bloques no aparecen (sin crashear)."""
    tr = R._hacer_tr("es")
    styles = R._styles()
    elems = R._seccion_ventana(styles, tr, _SNAP_VENTANA_BATCH, [])
    textos = [e.text for e in elems if hasattr(e, "text")]
    assert not any("Caño maestro" in t for t in textos)


def test_seccion_ventana_vacia_es_pendiente():
    tr = R._hacer_tr("es")
    styles = R._styles()
    elems = R._seccion_ventana(styles, tr, {}, [])
    assert any("P7" in getattr(e, "text", "") for e in elems)


# ---------------------------------------------------------------------------
# Sección de validación con datos medidos (E5)
# ---------------------------------------------------------------------------


def _metricas_demo():
    from calculos.metricas_validacion import MetricasAjuste

    return MetricasAjuste(
        n_pares=50, rmse=0.9, mbe=-0.2, mae=0.7, r2=0.99, nse=0.98, d_willmott=0.99
    )


def _cal_demo(parametro="velocidad_diseno"):
    from calculos.calibracion import PuntoCalibracion, ResultadoCalibracion

    m = _metricas_demo()
    puntos = [PuntoCalibracion(valor=v, objetivo=1.0 / v, metricas=m) for v in (2.0, 4.0, 8.0)]
    return ResultadoCalibracion(
        parametro=parametro,
        objetivo_nombre="rmse",
        puntos=puntos,
        valor_optimo=8.0,
        metricas_optimo=m,
    )


def _session_validacion():
    """session_state sintético: dict plano alcanza (el código usa .get)."""
    import numpy as np

    return {
        "p4_val_resultado": {
            "variable": "T_camara",
            "metricas": _metricas_demo(),
            "ts": list(range(5)),
            "y_med": np.array([320.0, 321.0, 322.0, 321.5, 320.5]),
            "y_sim": np.array([320.2, 321.1, 321.8, 321.6, 320.4]),
        },
        "p4_cal_resultado": _cal_demo("factor_K_m"),
        "p7_valtun_resultado": {
            "descargas": {
                "ts": list(range(3)),
                "y_med_disp": [3.0, 2.0, 1.5],
                "y_sim_disp": [2.9, 2.1, 1.4],
                "metricas": _metricas_demo(),
                "variable": "X_producto",
            },
            "perfil": {
                "magnitud": "X_producto",
                "y_med_disp": [4.0, None, 1.0],
                "y_sim_disp": [3.8, 2.2, 1.1],
                "metricas": _metricas_demo(),
            },
        },
    }


def test_datos_validacion_vacio_sin_claves():
    assert R._datos_validacion({}) == {}


def test_datos_validacion_normaliza_camara_y_tunel():
    datos = R._datos_validacion(_session_validacion())
    assert set(datos) == {"camara", "tunel"}
    cam = datos["camara"]
    assert cam["variable"] == "T_camara"
    assert cam["unidad"] == "°C"
    # a_display convirtió K → °C.
    assert cam["y_med"][0] == pytest.approx(320.0 - 273.15)
    assert cam["cal"].parametro == "factor_K_m"
    assert "descargas" in datos["tunel"] and "perfil" in datos["tunel"]


@pytest.mark.parametrize("idioma", IDIOMAS)
def test_pdf_seccion_validacion_en_cada_idioma(idioma):
    """La sección de validación arma un PDF válido en los 3 idiomas."""
    tr = R._hacer_tr(idioma)
    styles = R._styles()
    datos = R._datos_validacion(_session_validacion())
    story = R._seccion_validacion(styles, tr, datos, {})
    buf = io.BytesIO()
    doc = R._crear_doc(buf, {"grupo": None, "inenco": None}, "Demo", tr)
    doc.build(story)
    assert buf.getvalue().startswith(b"%PDF")


def test_seccion_validacion_factor_lleva_nota_diagnostico():
    """Un factor_* calibrado muestra la lectura física + nota de diagnóstico."""
    tr = R._hacer_tr("es")
    styles = R._styles()
    datos = R._datos_validacion(_session_validacion())
    elems = R._seccion_validacion(styles, tr, datos, {})
    textos = " ".join(getattr(e, "text", "") for e in elems)
    assert "diagnóstico" in textos
