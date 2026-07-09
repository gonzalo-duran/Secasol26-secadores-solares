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
