"""Generador de reporte PDF del prediseño completo.

Toma toda la información que producen los snapshots .json/.txt de las pestañas
P1–P7 más las gráficas que se generan en cada pestaña, y arma un PDF
estructurado con header institucional (GEEDSP / INENCO / CONICET-UNSa) en
cada página.

Las figuras de Plotly se exportan a PNG mediante ``kaleido`` (pinned a 0.2.1
en requirements.txt — la 1.x requiere Chrome instalado en el sistema, lo cual
no es viable en Streamlit Community Cloud).

API pública:
    generar_reporte_pdf(proyecto, session_state, res, T_amb_C, I_g, v_viento,
                       HR_cam_pct) -> bytes
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Registro de fuentes TrueType
# ---------------------------------------------------------------------------
# La fuente Helvetica embebida en ReportLab (PostScript Type 1) no tiene
# glifos para 'Δ', '→', 'η', '−' y otros símbolos que usamos en el reporte.
# DejaVu Sans cubre todo lo necesario y se distribuye con licencia permisiva.
# Buscamos en el repo primero, luego en rutas estándar Linux (Fedora / Debian).


def _registrar_fuentes() -> tuple[str, str, str, str]:
    """Registra DejaVu Sans si está disponible y devuelve los nombres a usar.

    Returns:
        (regular, bold, italic, bold_italic): nombres de fuente para
        usar en TableStyle, canvas.setFont, etc. Fallback a Helvetica si
        ninguna DejaVu está accesible.
    """
    candidatos = [
        Path(__file__).parent.parent / "assets" / "fonts",  # bundled en repo
        Path("/usr/share/fonts/dejavu-sans-fonts"),  # Fedora
        Path("/usr/share/fonts/truetype/dejavu"),  # Debian/Ubuntu
    ]
    for dir_path in candidatos:
        regular = dir_path / "DejaVuSans.ttf"
        bold = dir_path / "DejaVuSans-Bold.ttf"
        oblique = dir_path / "DejaVuSans-Oblique.ttf"
        bold_oblique = dir_path / "DejaVuSans-BoldOblique.ttf"
        if not regular.exists():
            continue
        try:
            # registerFont es idempotente si se llama con el mismo nombre.
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
            if bold.exists():
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
            if oblique.exists():
                pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", str(oblique)))
            if bold_oblique.exists():
                pdfmetrics.registerFont(TTFont("DejaVuSans-BoldOblique", str(bold_oblique)))
            # Mapeos para que Paragraph entienda <b>, <i>, <b><i>
            addMapping("DejaVuSans", 0, 0, "DejaVuSans")
            addMapping(
                "DejaVuSans",
                1,
                0,
                "DejaVuSans-Bold" if bold.exists() else "DejaVuSans",
            )
            addMapping(
                "DejaVuSans",
                0,
                1,
                "DejaVuSans-Oblique" if oblique.exists() else "DejaVuSans",
            )
            addMapping(
                "DejaVuSans",
                1,
                1,
                (
                    "DejaVuSans-BoldOblique"
                    if bold_oblique.exists()
                    else ("DejaVuSans-Bold" if bold.exists() else "DejaVuSans")
                ),
            )
            return (
                "DejaVuSans",
                "DejaVuSans-Bold" if bold.exists() else "DejaVuSans",
                "DejaVuSans-Oblique" if oblique.exists() else "DejaVuSans",
                (
                    "DejaVuSans-BoldOblique"
                    if bold_oblique.exists()
                    else ("DejaVuSans-Bold" if bold.exists() else "DejaVuSans")
                ),
            )
        except Exception:
            continue
    # Último fallback: Helvetica (glyphs limitados, aparecerán cuadrados
    # para Δ, →, η).
    return ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique")


_FONT_REGULAR, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC = _registrar_fuentes()

# ---------------------------------------------------------------------------
# Conversión de figuras Plotly a PNG
# ---------------------------------------------------------------------------

_DEFAULT_FIG_WIDTH_PX = 950
_DEFAULT_FIG_HEIGHT_PX = 420
_FIG_SCALE = 2  # 2× para nitidez en impresión


def _fig_a_png(
    fig, width: int = _DEFAULT_FIG_WIDTH_PX, height: int = _DEFAULT_FIG_HEIGHT_PX
) -> bytes | None:
    """Convierte una figura Plotly a PNG. Devuelve None si fig es None o falla."""
    if fig is None:
        return None
    try:
        return fig.to_image(format="png", width=width, height=height, scale=_FIG_SCALE)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Recolectores de figuras por pestaña
# ---------------------------------------------------------------------------


def _figuras_p2(proyecto) -> list[tuple[str, bytes]]:
    """Devuelve [(título, png_bytes), ...] del recurso climático (P2)."""
    out: list[tuple[str, bytes]] = []
    empl = getattr(proyecto, "emplazamiento", None)
    clima = getattr(proyecto, "clima", None)
    if empl is None or clima is None or clima.datos is None:
        return out

    from ui.componentes.unidades import acimut_duffie_a_pvlib
    from ui.p2_emplazamiento import (
        _calcular_poa_horaria,
        _fig_irradiancia,
        _fig_irradiancia_comparativa,
        _fig_temperatura,
        _fig_viento_hr,
    )

    try:
        datos_local = clima.datos.tz_convert(empl.zona_horaria)
        datos_local = datos_local[datos_local.index.year == clima.anio]
    except Exception:
        return out

    if len(datos_local) == 0:
        return out

    for titulo, fig in [
        ("Temperatura ambiente — promedios diario y mensual", _fig_temperatura(datos_local)),
        ("Irradiación mensual GHI / DNI / DHI", _fig_irradiancia(datos_local)),
        ("Velocidad del viento y humedad relativa mensual", _fig_viento_hr(datos_local)),
    ]:
        png = _fig_a_png(fig)
        if png:
            out.append((titulo, png))

    try:
        acimut_pvlib = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
        poa = _calcular_poa_horaria(
            datos_local,
            empl.latitud_deg,
            empl.longitud_deg,
            empl.altitud_m,
            empl.pendiente_colector_deg,
            acimut_pvlib,
            albedo=empl.albedo_suelo,
        )
        png = _fig_a_png(
            _fig_irradiancia_comparativa(datos_local, poa),
            height=620,
        )
        if png:
            out.append(("Irradiación: plano horizontal vs plano del colector", png))
    except Exception:
        pass
    return out


def _figuras_p3(session_state) -> list[tuple[str, bytes]]:
    """Devuelve [(título, png_bytes), ...] del colector (P3)."""
    out: list[tuple[str, bytes]] = []
    ev = session_state.get("p3_eval") if session_state else None
    if not ev:
        return out
    from ui.p3_colector import (
        _fig_T_fluido_anual,
        _fig_T_fluido_dia,
        _fig_T_salida_anual,
        _fig_T_salida_dia,
    )

    r = ev.get("r")
    modo = ev.get("modo")
    if not r:
        return out
    if modo == "diario":
        label = ev.get("label", "")
        png = _fig_a_png(_fig_T_salida_dia(r, label))
        if png:
            out.append((f"T salida del colector — {label}", png))
        png = _fig_a_png(_fig_T_fluido_dia(r, label))
        if png:
            out.append((f"Perfil T del fluido al mediodía — {label}", png))
    elif modo == "anual":
        png = _fig_a_png(_fig_T_salida_anual(r))
        if png:
            out.append(("T salida del colector por mes (día 15)", png))
        png = _fig_a_png(_fig_T_fluido_anual(r))
        if png:
            out.append(("Perfil T del fluido al mediodía por mes", png))
    return out


def _figuras_p4(proyecto, session_state) -> list[tuple[str, bytes]]:
    """Devuelve [(título, png_bytes), ...] de la cámara (P4)."""
    out: list[tuple[str, bytes]] = []
    if proyecto.camara is None or session_state is None:
        return out
    c = proyecto.camara.carga_producto
    X_obj = c.humedad_objetivo_X
    prod_id = c.producto_id

    res_td = session_state.get("p4_horizonte_resultado")
    if res_td is not None:
        from ui.p4_camara import _grafica_secado_termodinamico

        try:
            fig = _grafica_secado_termodinamico(res_td, X_obj, prod_id)
            png = _fig_a_png(fig, height=900)
            if png:
                out.append(("Trayectorias del motor termodinámico", png))
        except Exception:
            pass
        return out

    res_cf = session_state.get("p4_resultado_dinamico")
    if res_cf is not None:
        from ui.p4_camara import _grafica_curva_secado

        try:
            fig = _grafica_curva_secado(
                res_cf,
                c.humedad_inicial_X,
                X_obj,
                prod_id,
            )
            png = _fig_a_png(fig)
            if png:
                out.append((f"Curva de secado (capa fina) — {prod_id}", png))
        except Exception:
            pass
    return out


def _figuras_p7(res) -> list[tuple[str, bytes]]:
    """Devuelve [(título, png_bytes), ...] del balance global (P7)."""
    out: list[tuple[str, bytes]] = []
    if res is None:
        return out
    from ui.p7_resultados import _fig_sankey_simplificado

    try:
        sankey = _fig_sankey_simplificado(res)
        png = _fig_a_png(sankey)
        if png:
            out.append(("Balance energético del ciclo de secado", png))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Estilos y plantilla del PDF
# ---------------------------------------------------------------------------

_COLOR_TITULO = HexColor("#1f3a5f")
_COLOR_PENDIENTE = HexColor("#a64a00")
_COLOR_LINEA = HexColor("#cccccc")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            name="H1Sec",
            parent=base["Heading1"],
            fontName=_FONT_BOLD,
            fontSize=15,
            spaceBefore=4,
            spaceAfter=10,
            textColor=_COLOR_TITULO,
            leading=18,
        ),
        "h2": ParagraphStyle(
            name="H2Sec",
            parent=base["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=11.5,
            spaceBefore=8,
            spaceAfter=4,
            textColor=_COLOR_TITULO,
            leading=14,
        ),
        "p": ParagraphStyle(
            name="P",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=9.5,
            leading=12,
            spaceAfter=4,
        ),
        "p_celda": ParagraphStyle(
            # Para celdas de tabla con texto largo que necesita line-wrap.
            name="PCelda",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=9,
            leading=11,
            spaceAfter=0,
        ),
        "pendiente": ParagraphStyle(
            name="Pendiente",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=9.5,
            leading=12,
            spaceAfter=4,
            textColor=_COLOR_PENDIENTE,
            backColor=HexColor("#fff4e6"),
            borderPadding=6,
            leftIndent=0,
            rightIndent=0,
        ),
        "caption": ParagraphStyle(
            name="Caption",
            parent=base["Normal"],
            fontName=_FONT_ITALIC,
            fontSize=8.5,
            leading=10,
            alignment=1,
            textColor=HexColor("#555555"),
            spaceAfter=10,
        ),
    }


def _crear_doc(
    buf: io.BytesIO, logos: dict[str, str | None], titulo_proyecto: str
) -> BaseDocTemplate:
    """Crea el documento con header en cada página."""
    ancho, alto = A4

    def on_page(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        # Logos institucionales
        if logos.get("grupo"):
            canvas.drawImage(
                logos["grupo"],
                1.5 * cm,
                alto - 2.4 * cm,
                width=2.4 * cm,
                height=1.5 * cm,
                preserveAspectRatio=True,
                mask="auto",
            )
        if logos.get("inenco"):
            canvas.drawImage(
                logos["inenco"],
                ancho - 3.9 * cm,
                alto - 2.4 * cm,
                width=2.4 * cm,
                height=1.5 * cm,
                preserveAspectRatio=True,
                mask="auto",
            )
        # Título central
        canvas.setFont(_FONT_BOLD, 11)
        canvas.setFillColor(_COLOR_TITULO)
        canvas.drawCentredString(
            ancho / 2, alto - 1.3 * cm, "Secasol26 — Prediseño de Secadores Solares"
        )
        canvas.setFont(_FONT_REGULAR, 8)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawCentredString(ancho / 2, alto - 1.75 * cm, "GEEDSP · INENCO · CONICET-UNSa")
        if titulo_proyecto:
            canvas.setFont(_FONT_ITALIC, 8)
            canvas.drawCentredString(ancho / 2, alto - 2.15 * cm, f"Proyecto: {titulo_proyecto}")
        # Línea separadora
        canvas.setStrokeColor(_COLOR_LINEA)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * cm, alto - 2.55 * cm, ancho - 1.5 * cm, alto - 2.55 * cm)
        # Footer
        canvas.setFont(_FONT_REGULAR, 8)
        canvas.setFillColor(HexColor("#888888"))
        canvas.drawCentredString(ancho / 2, 1.0 * cm, f"Página {doc.page}")
        canvas.restoreState()

    frame = Frame(
        1.7 * cm,
        1.5 * cm,
        ancho - 3.4 * cm,
        alto - 4.3 * cm,
        id="contenido",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=2.8 * cm,
        bottomMargin=1.5 * cm,
        title=f"Prediseño — {titulo_proyecto or 'Secador solar'}",
    )
    doc.addPageTemplates([PageTemplate(id="estandar", frames=[frame], onPage=on_page)])
    return doc


def _imagen(png_bytes: bytes, max_width_cm: float = 16.5) -> Image | None:
    """Crea Image flowable preservando aspect ratio."""
    if not png_bytes:
        return None
    img = Image(io.BytesIO(png_bytes))
    aspect = img.imageHeight / img.imageWidth
    img.drawWidth = max_width_cm * cm
    img.drawHeight = max_width_cm * cm * aspect
    return img


def _tabla_kv(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Tabla clave→valor con estilo consistente."""
    if col_widths is None:
        col_widths = [5.5 * cm, 11.0 * cm]
    style = TableStyle(
        [
            ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 9),
            ("FONT", (0, 0), (0, -1), _FONT_BOLD, 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, _COLOR_LINEA),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    return Table(rows, colWidths=col_widths, style=style, hAlign="LEFT")


def _fmt(val: Any, default: str = "—") -> str:
    if val is None:
        return default
    if isinstance(val, bool):
        return "Sí" if val else "No"
    if isinstance(val, float):
        if abs(val) < 1e-3 or abs(val) >= 1e5:
            return f"{val:.3e}"
        return f"{val:.4g}"
    return str(val)


def _seccion_pendiente(st_dict: dict[str, ParagraphStyle], texto: str) -> list:
    return [Paragraph(f"⚠ {texto}", st_dict["pendiente"]), Spacer(1, 6)]


# ---------------------------------------------------------------------------
# Construcción del contenido del PDF
# ---------------------------------------------------------------------------


def _portada(styles, snap_meta: dict, snap_cfg: dict, snap_empl: dict, snap_clima: dict) -> list:
    """Bloque inicial: metadatos + P1 + P2 + clima."""
    elems: list = []
    elems.append(Paragraph("Resumen del proyecto", styles["h1"]))

    rows_meta = [
        ["Proyecto", snap_meta.get("nombre", "—")],
        ["Autor", snap_meta.get("autor") or "—"],
        ["Fecha de creación", snap_meta.get("fecha_creacion", "—")],
        ["Última modificación", snap_meta.get("fecha_modificacion", "—")],
        ["Versión software", snap_meta.get("version_software", "—")],
    ]
    if snap_meta.get("notas"):
        rows_meta.append(["Notas", snap_meta["notas"]])
    elems.append(_tabla_kv(rows_meta))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Tipología y análisis (P1)", styles["h2"]))
    rows_cfg = [
        ["Tipología", _fmt(snap_cfg.get("tipologia"))],
        ["Modo análisis", _fmt(snap_cfg.get("modo_analisis"))],
        ["Día de análisis", _fmt(snap_cfg.get("dia_analisis"))],
    ]
    if snap_cfg.get("fecha_especifica"):
        rows_cfg.append(["Fecha específica", snap_cfg["fecha_especifica"]])
    elems.append(_tabla_kv(rows_cfg))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Emplazamiento (P2)", styles["h2"]))
    if not snap_empl:
        elems += _seccion_pendiente(
            styles,
            "Emplazamiento no configurado en P2.",
        )
    else:
        rows_empl = [
            ["Latitud", f"{snap_empl.get('latitud_deg', '—')}°"],
            ["Longitud", f"{snap_empl.get('longitud_deg', '—')}°"],
            ["Altitud", f"{_fmt(snap_empl.get('altitud_m'))} m"],
            [
                "Acimut colector (Duffie)",
                f"{snap_empl.get('acimut_colector_deg_duffie', '—')}° (0°=Sur)",
            ],
            ["Pendiente colector", f"{snap_empl.get('pendiente_colector_deg', '—')}°"],
            ["Albedo del suelo", f"{_fmt(snap_empl.get('albedo_suelo'))}"],
            ["Zona horaria", snap_empl.get("zona_horaria", "—")],
        ]
        elems.append(_tabla_kv(rows_empl))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Recurso climático (NASA POWER)", styles["h2"]))
    if not snap_clima:
        elems += _seccion_pendiente(
            styles,
            "Datos climáticos no descargados.",
        )
    else:
        rows_clima = [
            ["Año fuente", _fmt(snap_clima.get("anio"))],
            ["Altitud grilla NASA", f"{_fmt(snap_clima.get('altitud_nasa_m'))} m"],
            ["Horas disponibles", _fmt(snap_clima.get("n_horas"))],
            ["T ambiente media", f"{_fmt(snap_clima.get('T_amb_media_C'))} °C"],
            ["GHI media", f"{_fmt(snap_clima.get('GHI_media_W_m2'))} W/m²"],
        ]
        cal = snap_clima.get("calidad") or {}
        rows_clima += [
            ["Huecos originales", _fmt(cal.get("n_huecos_originales"))],
            ["Horas interpoladas", _fmt(cal.get("n_horas_interpoladas"))],
            ["Horas bloqueadas", _fmt(cal.get("n_horas_bloqueadas"))],
            ["Mayor hueco (h)", _fmt(cal.get("mayor_hueco_h"))],
        ]
        elems.append(_tabla_kv(rows_clima))
    return elems


def _seccion_figuras(
    styles, titulo: str, figuras: list[tuple[str, bytes]], msg_pendiente: str | None
) -> list:
    """Bloque genérico: heading + lista de figuras o nota de pendiente."""
    elems: list = [Paragraph(titulo, styles["h2"])]
    if not figuras:
        if msg_pendiente:
            elems += _seccion_pendiente(styles, msg_pendiente)
        return elems
    for sub_titulo, png in figuras:
        elems.append(Paragraph(sub_titulo, styles["caption"]))
        img = _imagen(png)
        if img is not None:
            elems.append(img)
        elems.append(Spacer(1, 6))
    return elems


def _seccion_colector(styles, snap_col: dict | None, figuras: list[tuple[str, bytes]]) -> list:
    elems: list = [Paragraph("Colector solar (P3)", styles["h1"])]
    if snap_col is None:
        elems += _seccion_pendiente(
            styles,
            "Tipología sin colector externo (CAJA) o colector no configurado.",
        )
        return elems

    u = snap_col.get("unidad", {})
    mats = snap_col.get("materiales", {})
    banco = snap_col.get("banco", {})
    deriv = snap_col.get("derivados", {})

    elems.append(Paragraph("Materiales", styles["h2"]))
    rows = []
    for nombre, key in [
        ("Cubierta", "cubierta"),
        ("Placa", "placa"),
        ("Aislante", "aislante"),
        ("Fondo", "fondo"),
    ]:
        m = mats.get(key, {})
        props = m.get("props_catalogo", {}) or {}
        texto_valor = (
            f"{props.get('descripcion', m.get('id', '—'))}  "
            f"[id={m.get('id', '—')}, e={_fmt(m.get('espesor_m'))} m]"
        )
        # Paragraph para que el texto largo haga line-wrap dentro de la celda
        rows.append([nombre, Paragraph(texto_valor, styles["p_celda"])])
    elems.append(_tabla_kv(rows))
    elems.append(Spacer(1, 8))

    elems.append(Paragraph("Geometría y banco", styles["h2"]))
    rows_geo = [
        [
            "Tipo de colector",
            f"{u.get('tipo_colector')} — {u.get('tipo_colector_descripcion', '—')}",
        ],
        ["Ancho × largo", f"{_fmt(u.get('ancho_m'))} × {_fmt(u.get('largo_m'))} m"],
        ["Espaciado canal", f"{_fmt(u.get('espaciado_m'))} m"],
        ["N° cubiertas", _fmt(u.get("n_cubiertas"))],
        ["Velocidad diseño", f"{_fmt(u.get('velocidad_diseno_ms'))} m/s"],
        ["Banco", f"{banco.get('n_serie', 1)} serie × {banco.get('n_paralelo', 1)} paralelo"],
        ["Área de captación total", f"{_fmt(deriv.get('area_total_m2'))} m²"],
        ["Caudal total", f"{_fmt(deriv.get('caudal_total_m3_s'))} m³/s"],
        ["Camino del aire", f"{_fmt(deriv.get('largo_camino_aire_m'))} m"],
    ]
    elems.append(_tabla_kv(rows_geo))

    # Resultados
    elems.append(Spacer(1, 8))
    elems.append(Paragraph("Resultados de simulación", styles["h2"]))
    res = snap_col.get("resultados") or {}
    if not res.get("ejecutado"):
        elems += _seccion_pendiente(
            styles,
            "Cálculo del colector no ejecutado. "
            "Volver a P3 y presionar 'Calcular desempeño del colector'.",
        )
    else:
        modo = res.get("modo")
        resumen = res.get("resumen") or {}
        if modo == "diario":
            rows_res = [
                ["Día representativo", res.get("dia_representativo", "—")],
                ["T salida máx", f"{_fmt(resumen.get('T_salida_max_C'))} °C"],
                ["T salida mediodía", f"{_fmt(resumen.get('T_salida_mediodia_C'))} °C"],
                ["ΔT máx (sal − amb)", f"{_fmt(resumen.get('delta_T_max_C'))} °C"],
                ["Horas con sol", _fmt(resumen.get("n_horas_con_radiacion"))],
            ]
            elems.append(_tabla_kv(rows_res))
        elif modo == "anual":
            rows_res = [
                [
                    "Mejor mes (T sal máx)",
                    f"{resumen.get('T_salida_max_mes', '—')} — "
                    f"{_fmt(resumen.get('T_salida_max_C'))} °C",
                ],
                [
                    "Peor mes (T sal mín)",
                    f"{resumen.get('T_salida_min_mes', '—')} — "
                    f"{_fmt(resumen.get('T_salida_min_C'))} °C",
                ],
                ["ΔT mín colector", f"{_fmt(resumen.get('delta_T_min_C'))} °C"],
            ]
            elems.append(_tabla_kv(rows_res))

    elems += _bloque_advertencias(styles, snap_col.get("advertencias_diseno"))

    # Figuras
    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        "Gráficas del colector",
        figuras,
        msg_pendiente="Sin gráficas: el cálculo no fue ejecutado.",
    )
    return elems


def _seccion_camara(styles, snap_cam: dict | None, figuras: list[tuple[str, bytes]]) -> list:
    elems: list = [Paragraph("Cámara de secado (P4)", styles["h1"])]
    if snap_cam is None:
        elems += _seccion_pendiente(styles, "Cámara no configurada en P4.")
        return elems

    g = snap_cam.get("geometria", {})
    cn = snap_cam.get("construccion", {})
    b = snap_cam.get("bandejas", {})
    c = snap_cam.get("carga_producto", {})
    f = snap_cam.get("flujo", {})

    elems.append(Paragraph("Geometría y modo de cálculo", styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                [
                    "Largo × ancho × alto",
                    f"{_fmt(g.get('largo_m'))} × {_fmt(g.get('ancho_m'))} × "
                    f"{_fmt(g.get('alto_m'))} m",
                ],
                ["Volumen", f"{_fmt(g.get('volumen_m3'))} m³"],
                ["Motor numérico", snap_cam.get("modo_calculo", "—")],
            ]
        )
    )

    elems.append(Spacer(1, 6))
    elems.append(Paragraph("Construcción (pared opaca + techo)", styles["h2"]))
    pared = cn.get("pared", {})
    rows_pared = [
        ["Techo translúcido", cn.get("cubierta_translucida_id") or "(opaca)"],
        ["A_rad", f"{_fmt(cn.get('A_rad_m2'))} m²"],
        ["Pared compuesta", "Sí" if pared.get("es_compuesta") else "No"],
        ["Capas", str(len(pared.get("capas", [])))],
        ["Espesor pared", f"{_fmt(pared.get('espesor_total_m'))} m"],
        ["R pared total", f"{_fmt(pared.get('R_total_m2K_W'))} m²·K/W"],
        ["U pared", f"{_fmt(pared.get('U_pared_W_m2K'))} W/(m²·K)"],
    ]
    elems.append(_tabla_kv(rows_pared))

    elems.append(Spacer(1, 6))
    elems.append(Paragraph("Bandejas, producto y flujo", styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                [
                    "N° bandejas / área c/u",
                    f"{b.get('n_bandejas', '—')}  /  " f"{_fmt(b.get('area_bandeja_m2'))} m²",
                ],
                ["Espesor capa", f"{_fmt(b.get('espesor_capa_m'))} m"],
                ["Separación bandejas", f"{_fmt(b.get('separacion_entre_bandejas_m'))} m"],
                ["Producto", f"{c.get('producto_id', '—')} " f"({c.get('categoria', '—')})"],
                ["Masa total", f"{_fmt(c.get('masa_total_kg'))} kg"],
                [
                    "X₀ → X_obj",
                    f"{_fmt(c.get('humedad_inicial_X'))} → "
                    f"{_fmt(c.get('humedad_objetivo_X'))} kg/kg ms",
                ],
                [
                    "Modelo capa fina / isoterma",
                    f"{c.get('modelo_capa_fina', '—')} / " f"{c.get('modelo_isoterma', '—')}",
                ],
                ["Caudal másico aire", f"{_fmt(f.get('caudal_masico_kg_s'))} kg/s"],
                ["Dirección flujo", f.get("direccion_flujo", "—")],
                ["HR entrada", _fmt(f.get("HR_entrada_fraccion"), default="(fallback)")],
            ]
        )
    )

    elems.append(Spacer(1, 8))
    elems.append(Paragraph("Resultados de simulación", styles["h2"]))
    r = snap_cam.get("resultados") or {}
    if not r.get("ejecutado"):
        elems += _seccion_pendiente(
            styles,
            "Cálculo de la cámara no ejecutado en esta sesión. "
            "Volver a P4 y presionar 'Calcular cámara'.",
        )
    else:
        res = r.get("resumen") or {}
        if r.get("tipo") == "termodinamico_horizonte":
            elems.append(
                _tabla_kv(
                    [
                        ["Status", res.get("status", "—")],
                        ["Tiempo simulación", f"{_fmt(res.get('t_simulacion_h'))} h"],
                        ["Tiempo de secado", f"{_fmt(res.get('t_secado_h'))} h"],
                        ["Agua evaporada", f"{_fmt(res.get('masa_evaporada_total_kg'))} kg"],
                        [
                            "X inicial → final",
                            f"{_fmt(res.get('X_prod_inicial'))} → "
                            f"{_fmt(res.get('X_prod_final'))} kg/kg ms",
                        ],
                        ["T producto final", f"{_fmt(res.get('T_prod_final_C'))} °C"],
                        ["T producto máx", f"{_fmt(res.get('T_max_alcanzada_C'))} °C"],
                        ["HR máx en cámara", _fmt(res.get("HR_max"))],
                        ["E radiativa total", f"{_fmt(res.get('energia_rad_total_MJ'))} MJ"],
                    ]
                )
            )
        else:
            elems.append(
                _tabla_kv(
                    [
                        ["Modelo aplicado", res.get("modelo_usado", "—")],
                        [
                            "X_eq",
                            f"{_fmt(res.get('X_eq_kg_kg'))} kg/kg ms "
                            f"({res.get('fuente_X_eq', '—')})",
                        ],
                        ["Tiempo de secado", f"{_fmt(res.get('t_secado_h'))} h"],
                        ["Agua extraída", f"{_fmt(res.get('masa_agua_extraida_kg'))} kg"],
                        ["MR objetivo", _fmt(res.get("MR_obj"))],
                        [
                            "Convergencia",
                            (
                                "OK"
                                if res.get("convergencia_ok")
                                else res.get("mensaje_convergencia", "falla")
                            ),
                        ],
                    ]
                )
            )

    elems += _bloque_advertencias(styles, snap_cam.get("advertencias_diseno"))

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        "Gráficas de la cámara",
        figuras,
        msg_pendiente="Sin gráficas: el cálculo no fue ejecutado.",
    )
    return elems


def _seccion_auxiliar(styles, snap_aux: dict | None) -> list:
    elems: list = [Paragraph("Calentamiento auxiliar (P5)", styles["h1"])]
    if snap_aux is None:
        elems += _seccion_pendiente(
            styles,
            "Secador sin sistema auxiliar configurado.",
        )
        return elems
    rows = [
        ["Tipo", snap_aux.get("tipo", "—")],
        ["Modo operación", snap_aux.get("modo_operacion", "—")],
        [
            "Potencia nominal",
            f"{_fmt(snap_aux.get('potencia_nominal_W'))} W "
            f"({_fmt((snap_aux.get('potencia_nominal_W') or 0) / 1000)} kW)",
        ],
        ["Fracción operación", _fmt(snap_aux.get("fraccion_potencia_operacion"))],
        ["Potencia efectiva", f"{_fmt(snap_aux.get('potencia_efectiva_W'))} W"],
        ["T máx salida", f"{(_fmt(snap_aux.get('temperatura_maxima_salida_K')))} K"],
        ["Disponible nocturno", _fmt(snap_aux.get("disponible_nocturno"))],
    ]
    if snap_aux.get("biomasa"):
        bm = snap_aux["biomasa"]
        rows += [
            ["Combustible", bm.get("tipo_biomasa", "—")],
            ["PCI", f"{_fmt(bm.get('PCI_MJ_kg'))} MJ/kg"],
            ["η quemador", _fmt(bm.get("eficiencia_quemador"))],
            ["Consumo efectivo", f"{_fmt(bm.get('consumo_biomasa_efectivo_kg_h'))} kg/h"],
        ]
    if snap_aux.get("resistencia_electrica"):
        re = snap_aux["resistencia_electrica"]
        rows += [
            ["Tensión", f"{_fmt(re.get('tension_V'))} V"],
            ["Corriente estimada", f"{_fmt(re.get('corriente_estimada_A'))} A"],
        ]
    elems.append(_tabla_kv(rows))
    if snap_aux.get("notas"):
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(f"<i>Notas:</i> {snap_aux['notas']}", styles["p"]))
    elems += _bloque_advertencias(styles, snap_aux.get("advertencias_diseno"))
    elems += _seccion_pendiente(
        styles,
        "Los resultados de operación del auxiliar (Q_efectivo, ΔT, energía aportada) "
        "se integran en el balance global de P7. Ver sección Resultados globales.",
    )
    return elems


def _seccion_motor(styles, snap_mot: dict | None) -> list:
    elems: list = [Paragraph("Motor / ventilador (P6)", styles["h1"])]
    if snap_mot is None:
        elems += _seccion_pendiente(
            styles,
            "Secador sin motor configurado (convección natural).",
        )
        return elems
    dp = snap_mot.get("perdida_de_carga", {})
    ef = snap_mot.get("eficiencias", {})
    rows = [
        ["Tipo accionamiento", snap_mot.get("tipo_accionamiento", "—")],
        ["Caudal volumétrico", f"{_fmt(snap_mot.get('caudal_volumetrico_m3_s'))} m³/s"],
        ["ΔP total", f"{_fmt(dp.get('delta_P_total_Pa'))} Pa"],
        ["ΔP colector", f"{_fmt(dp.get('delta_P_colector_Pa'))} Pa"],
        ["ΔP cámara", f"{_fmt(dp.get('delta_P_camara_Pa'))} Pa"],
        ["ΔP ductos", f"{_fmt(dp.get('delta_P_ductos_Pa'))} Pa"],
        ["ΔP singulares", f"{_fmt(dp.get('delta_P_singulares_Pa'))} Pa"],
        ["η ventilador", _fmt(ef.get("eficiencia_ventilador"))],
        ["η motor", _fmt(ef.get("eficiencia_motor"))],
        ["Factor servicio", _fmt(ef.get("factor_servicio"))],
    ]
    res = snap_mot.get("resultados") or {}
    if res.get("ejecutado"):
        rows += [
            ["P hidráulica", f"{_fmt(res.get('potencia_hidraulica_W'))} W"],
            ["P eje", f"{_fmt(res.get('potencia_eje_W'))} W"],
            ["P eléctrica", f"{_fmt(res.get('potencia_electrica_W'))} W"],
            ["P a instalar", f"{_fmt(res.get('potencia_a_instalar_W'))} W"],
            ["Corriente nominal", f"{_fmt(res.get('corriente_nominal_A'))} A"],
        ]
    elems.append(_tabla_kv(rows))
    if snap_mot.get("notas"):
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(f"<i>Notas:</i> {snap_mot['notas']}", styles["p"]))
    elems += _bloque_advertencias(styles, snap_mot.get("advertencias_diseno"))
    return elems


def _seccion_chimenea(
    styles,
    snap_chim: dict | None,
    res_chim: dict | None,
) -> list:
    """Sección de chimenea solar + extractor eólico en el reporte PDF.

    Args:
        snap_chim: Snapshot reconstruible producido por
            ``ui.p6_motor._json_config_chimenea`` (geometría + extractor +
            advertencias estáticas), o None si el proyecto no tiene chimenea.
        res_chim: Dict de resultados del lazo natural producido por
            ``balance_global.calcular_todo`` (escalares en modo Constantes)
            o ``calcular_todo_transitorio`` (mix de escalares + arrays),
            o None si el balance no se ejecutó o motor está activo.
    """
    elems: list = [Paragraph("Chimenea solar (P6)", styles["h1"])]
    if snap_chim is None:
        elems += _seccion_pendiente(
            styles,
            "Sin chimenea configurada. Si el secador opera por convección "
            "forzada, ver sección Motor; si es difusión libre, no aplica.",
        )
        return elems

    ch = snap_chim.get("chimenea", {})
    ext = ch.get("extractor", {}) or {}

    # --- Geometría y material ---
    elems.append(Paragraph("Geometría y material", styles["h2"]))
    rows_geo = [
        ["Diámetro interno", f"{_fmt(ch.get('diametro_m'))} m"],
        ["Altura", f"{_fmt(ch.get('altura_m'))} m"],
        ["Material", ch.get("id_material", "—")],
    ]
    props = ch.get("props_catalogo") or {}
    if props.get("descripcion"):
        rows_geo.append(["Descripción", props["descripcion"]])
    elems.append(_tabla_kv(rows_geo))

    # --- Extractor eólico (si está activo) ---
    if ext.get("activo"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph("Extractor eólico (turbina sombrero chino)", styles["h2"]))
        rows_ext = [
            ["Diámetro del extractor", f"{_fmt(ext.get('diametro_extractor_m'))} m"],
            ["Cp motriz (turbina)", _fmt(ext.get("Cp_turbina"))],
            ["Kt resistivo (turbina)", _fmt(ext.get("Kt_turbina"))],
            ["z₀ rugosidad terreno", f"{_fmt(ext.get('z0_terreno_m'))} m"],
        ]
        elems.append(_tabla_kv(rows_ext))
    else:
        elems.append(Spacer(1, 6))
        elems.append(
            Paragraph(
                "<i>Sin extractor eólico — convección natural sólo por tiro térmico.</i>",
                styles["p"],
            )
        )

    # --- Resultados del lazo natural resuelto en P7 (Picard completo) ---
    elems.append(Spacer(1, 8))
    elems.append(Paragraph("Resultados del lazo natural (balance Picard)", styles["h2"]))
    if res_chim is None:
        elems += _seccion_pendiente(
            styles,
            "Cálculo del lazo natural no ejecutado (motor activo, o balance "
            "global no corrido en P7).",
        )
    else:
        # Detectar si es transitorio (arrays) o constantes (escalares):
        # en transitorio existen las claves m_promedio_kgs / m_max_kgs y
        # los valores de m_punto_kgs / v_chim_ms son arrays.
        es_transitorio = "m_promedio_kgs" in res_chim
        if es_transitorio:
            m_prom = float(res_chim.get("m_promedio_kgs", 0.0))
            m_max = float(res_chim.get("m_max_kgs", 0.0))
            H_eff = float(res_chim.get("H_eff_m", 0.0))
            iter_picard = res_chim.get("iteraciones", "—")
            convergio = res_chim.get("convergio", False)
            delta_T_final = res_chim.get("delta_T_chim_final_K", None)
            horas_sin_tiro = res_chim.get("horas_sin_tiro", None)
            rows_res = [
                ["Modo de cálculo", "Transitorio (horizonte horario)"],
                ["Caudal natural promedio", f"{m_prom * 1000:.2f} g/s ({_fmt(m_prom)} kg/s)"],
                ["Caudal natural máximo", f"{m_max * 1000:.2f} g/s ({_fmt(m_max)} kg/s)"],
                ["H efectiva", f"{_fmt(H_eff)} m"],
                ["Iteraciones Picard", _fmt(iter_picard)],
                ["¿Convergió?", "Sí" if convergio else "No"],
            ]
            if delta_T_final is not None:
                rows_res.append(
                    [
                        "ΔT_chim final entre iteraciones",
                        f"{_fmt(delta_T_final)} K",
                    ]
                )
            if horas_sin_tiro is not None:
                rows_res.append(
                    [
                        "Horas sin tiro (ṁ = 0)",
                        _fmt(horas_sin_tiro),
                    ]
                )
        else:
            m_punto = float(res_chim.get("m_punto_kgs", 0.0))
            v_chim = float(res_chim.get("v_chim_ms", 0.0))
            Re_chim = float(res_chim.get("Re_chimenea", 0.0))
            dP_tiro = float(res_chim.get("delta_P_tiro_Pa", 0.0))
            dP_ducto = float(res_chim.get("delta_P_chimenea_Pa", 0.0))
            dP_resto = float(res_chim.get("delta_P_resto_Pa", 0.0))
            dP_turb = float(res_chim.get("delta_P_turbina_motriz_Pa", 0.0))
            H_eff = float(res_chim.get("H_eff_m", 0.0))
            v_loc = float(res_chim.get("v_viento_local_ms", 0.0))
            iter_picard = res_chim.get("iteraciones", "—")
            convergio = res_chim.get("convergio", False)
            delta_T_final = res_chim.get("delta_T_chim_final_K", None)
            T_chim_K = res_chim.get("T_chim_K", None)
            rows_res = [
                ["Modo de cálculo", "Constantes (régimen estacionario)"],
                ["Caudal natural", f"{m_punto * 1000:.2f} g/s ({_fmt(m_punto)} kg/s)"],
                ["Velocidad en chimenea", f"{_fmt(v_chim)} m/s"],
                ["Re en chimenea", f"{Re_chim:.0f}"],
                ["ΔP tiro térmico", f"{_fmt(dP_tiro)} Pa"],
                ["ΔP ducto chimenea", f"{_fmt(dP_ducto)} Pa"],
                ["ΔP resto (col + cám)", f"{_fmt(dP_resto)} Pa"],
                ["H efectiva", f"{_fmt(H_eff)} m"],
                ["Iteraciones Picard", _fmt(iter_picard)],
                ["¿Convergió?", "Sí" if convergio else "No"],
            ]
            if dP_turb > 0.0 or ext.get("activo"):
                rows_res.append(
                    [
                        "ΔP motriz del extractor",
                        f"{_fmt(dP_turb)} Pa",
                    ]
                )
                rows_res.append(
                    [
                        "Viento a la altura del tope",
                        f"{_fmt(v_loc)} m/s",
                    ]
                )
            if T_chim_K is not None:
                try:
                    rows_res.append(
                        [
                            "T en chimenea (Picard final)",
                            f"{float(T_chim_K) - 273.15:.1f} °C",
                        ]
                    )
                except (TypeError, ValueError):
                    pass
            if delta_T_final is not None:
                rows_res.append(
                    [
                        "ΔT_chim final entre iteraciones",
                        f"{_fmt(delta_T_final)} K",
                    ]
                )
        elems.append(_tabla_kv(rows_res))

        # Advertencias del solver (deduplicadas por código)
        advs_solver = res_chim.get("advertencias") or []
        if advs_solver:
            elems.append(Spacer(1, 4))
            elems.append(
                Paragraph(
                    "<i>Avisos del solver del lazo natural:</i>",
                    styles["p"],
                )
            )
            for a in advs_solver:
                if a:
                    elems.append(Paragraph(f"• {a}", styles["p"]))

    # --- Advertencias estáticas del diseño de chimenea ---
    elems += _bloque_advertencias(styles, snap_chim.get("advertencias_diseno"))
    return elems


def _seccion_resultados_globales(
    styles, snap_global: dict, condiciones: dict, figuras: list[tuple[str, bytes]]
) -> list:
    elems: list = [Paragraph("Resultados globales (P7)", styles["h1"])]
    elems.append(Paragraph("Condiciones de operación representativas", styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                ["T ambiente", f"{_fmt(condiciones.get('T_amb_C'))} °C"],
                ["Irradiancia POA", f"{_fmt(condiciones.get('I_g_POA_W_m2'))} W/m²"],
                ["Velocidad viento", f"{_fmt(condiciones.get('v_viento_ms'))} m/s"],
                ["HR cámara", f"{_fmt(condiciones.get('HR_camara_pct'))} %"],
            ]
        )
    )

    elems.append(Spacer(1, 8))
    elems.append(Paragraph("Balance energético", styles["h2"]))
    rows = [
        ["Energía total", f"{_fmt(snap_global.get('energia_total_MJ'))} MJ"],
        ["Solar útil", f"{_fmt(snap_global.get('energia_solar_util_MJ'))} MJ"],
        ["Auxiliar", f"{_fmt(snap_global.get('energia_auxiliar_MJ'))} MJ"],
        ["Motor", f"{_fmt(snap_global.get('energia_motor_MJ'))} MJ"],
        ["Secado (útil)", f"{_fmt(snap_global.get('energia_secado_MJ'))} MJ"],
        ["COP secado", _fmt(snap_global.get("COP_secado"))],
        ["Fracción solar", _fmt(snap_global.get("fraccion_solar"))],
        ["T entrada cámara", f"{_fmt(snap_global.get('T_entrada_camara_C'))} °C"],
    ]
    elems.append(_tabla_kv(rows))

    # Sub-bloques colector/aux/camara dentro del global
    if snap_global.get("colector"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph("Colector — salida calculada", styles["h2"]))
        col = snap_global["colector"]
        elems.append(
            _tabla_kv(
                [
                    [
                        "T entrada/salida",
                        f"{_fmt(col.get('T_entrada_K'))} → " f"{_fmt(col.get('T_salida_K'))} K",
                    ],
                    ["Q útil", f"{_fmt(col.get('Q_util_W'))} W"],
                    ["η térmica", _fmt(col.get("eta_termica"))],
                    ["Régimen", _fmt(col.get("regimen_flujo"))],
                    ["Re medio", _fmt(col.get("Re_medio"))],
                    ["h_int", f"{_fmt(col.get('h_int_medio'))} W/(m²·K)"],
                ]
            )
        )

    if snap_global.get("camara"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph("Cámara — ciclo simulado", styles["h2"]))
        c = snap_global["camara"]
        if c.get("modo_calculo") == "termodinamico":
            elems.append(
                _tabla_kv(
                    [
                        ["Modo", "termodinámico"],
                        ["Tiempo de secado", f"{_fmt(c.get('t_secado_h'))} h"],
                        ["Agua evaporada", f"{_fmt(c.get('masa_evaporada_kg'))} kg"],
                        ["X final", _fmt(c.get("X_final"))],
                        ["T producto final", f"{_fmt(c.get('T_prod_final_C'))} °C"],
                        ["Status", c.get("status", "—")],
                    ]
                )
            )
        else:
            elems.append(
                _tabla_kv(
                    [
                        ["Modo", "capa fina"],
                        ["Tiempo de secado", f"{_fmt(c.get('t_secado_h'))} h"],
                        ["Agua extraída", f"{_fmt(c.get('masa_agua_extraida_kg'))} kg"],
                        ["X_eq", _fmt(c.get("X_eq_kg_kg"))],
                        ["Convergencia", _fmt(c.get("convergencia_ok"))],
                    ]
                )
            )

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        "Gráficas globales",
        figuras,
        msg_pendiente="Sin gráfica global disponible.",
    )
    return elems


def _bloque_advertencias(styles, advs: list[dict] | None) -> list:
    if not advs:
        return []
    elems: list = [Spacer(1, 4), Paragraph("Advertencias estáticas de diseño", styles["h2"])]
    # Header crudo + filas con Paragraph para que el texto haga line-wrap
    # cuando el código o el mensaje exceden el ancho de columna.
    rows = [["Sev.", "Código", "Mensaje"]]
    for a in advs:
        rows.append(
            [
                Paragraph(a.get("severidad", ""), styles["p_celda"]),
                Paragraph(a.get("codigo", ""), styles["p_celda"]),
                Paragraph(a.get("mensaje", ""), styles["p_celda"]),
            ]
        )
    # Anchos rebalanceados: severidad 2 cm para "WARNING"/"CRITICAL",
    # código 5 cm para nombres largos, mensaje 9.5 cm.
    t = Table(
        rows,
        colWidths=[2.0 * cm, 5.0 * cm, 9.5 * cm],
        style=TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 8.5),
                ("FONT", (0, 0), (-1, 0), _FONT_BOLD, 8.5),
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, _COLOR_LINEA),
            ]
        ),
    )
    elems.append(t)
    return elems


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def generar_reporte_pdf(
    proyecto,
    session_state,
    res,
    T_amb_C: float,
    I_g: float,
    v_viento: float,
    HR_cam_pct: float,
) -> bytes:
    """Genera el reporte PDF completo del prediseño.

    Args:
        proyecto: Objeto Proyecto raíz.
        session_state: ``st.session_state`` con los resultados cacheados.
        res: ResultadosCompletos del balance global (P7).
        T_amb_C, I_g, v_viento, HR_cam_pct: condiciones de operación P7.

    Returns:
        Bytes del PDF generado.
    """
    from ui.p3_colector import _json_config_colector
    from ui.p4_camara import _json_config_camara
    from ui.p5_auxiliar import _json_config_auxiliar
    from ui.p6_motor import _json_config_chimenea, _json_config_motor
    from ui.p7_resultados import (
        _bloque_meta_emplazamiento_clima,
        _json_resultados_completo,
    )

    # Snapshots de cada sección
    _, meta_dict = _bloque_meta_emplazamiento_clima(proyecto)
    snap_col = (
        _json_config_colector(proyecto.colector, session_state.get("p3_eval"))
        if proyecto.colector is not None
        else None
    )
    snap_cam = (
        _json_config_camara(proyecto.camara, session_state) if proyecto.camara is not None else None
    )
    snap_aux = _json_config_auxiliar(proyecto.auxiliar) if proyecto.auxiliar is not None else None
    snap_mot = _json_config_motor(proyecto.motor) if proyecto.motor is not None else None
    snap_chim = (
        _json_config_chimenea(proyecto.chimenea)
        if getattr(proyecto, "chimenea", None) is not None
        else None
    )
    # Resultados del lazo natural ya resueltos por el balance global (P7).
    # Mismo dict que res.chimenea, tanto para modo Constantes (escalares)
    # como Transitorio (arrays + agregados).
    res_chim = getattr(res, "chimenea", None) if res is not None else None

    # Snapshot completo (para sección global)
    snap_full = _json_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
    )

    # Recolección de figuras (esto puede tardar varios segundos)
    figs_p2 = _figuras_p2(proyecto)
    figs_p3 = _figuras_p3(session_state)
    figs_p4 = _figuras_p4(proyecto, session_state)
    figs_p7 = _figuras_p7(res)

    # Logos
    assets_dir = Path(__file__).parent.parent / "assets"
    logo_grupo = assets_dir / "logo_grupo_transparente.png"
    if not logo_grupo.exists():
        logo_grupo = assets_dir / "logo_grupo.png"
    logo_inenco = assets_dir / "logo_inenco_transparente.png"
    if not logo_inenco.exists():
        logo_inenco = assets_dir / "logo_inenco.png"
    logos = {
        "grupo": str(logo_grupo) if logo_grupo.exists() else None,
        "inenco": str(logo_inenco) if logo_inenco.exists() else None,
    }

    nombre_proyecto = (meta_dict.get("meta") or {}).get("nombre", "Prediseño")

    buf = io.BytesIO()
    doc = _crear_doc(buf, logos, nombre_proyecto)
    styles = _styles()
    story: list = []

    # 1. Portada con P1/P2/clima
    story += _portada(
        styles,
        snap_meta=meta_dict.get("meta") or {},
        snap_cfg=meta_dict.get("configuracion") or {},
        snap_empl=meta_dict.get("emplazamiento") or {},
        snap_clima=meta_dict.get("clima") or {},
    )

    # 2. Gráficas climáticas
    story.append(PageBreak())
    story.append(Paragraph("Recurso solar y clima — gráficas (P2)", styles["h1"]))
    story += _seccion_figuras(
        styles,
        "",
        figs_p2,
        msg_pendiente="Sin gráficas: clima no descargado en P2.",
    )

    # 3. Colector
    story.append(PageBreak())
    story += _seccion_colector(styles, snap_col, figs_p3)

    # 4. Cámara
    story.append(PageBreak())
    story += _seccion_camara(styles, snap_cam, figs_p4)

    # 5. Auxiliar
    story.append(PageBreak())
    story += _seccion_auxiliar(styles, snap_aux)

    # 6. Motor
    story += [Spacer(1, 12)]
    story += _seccion_motor(styles, snap_mot)

    # 6.b Chimenea solar (sólo si está configurada — convección natural o
    # accesorio paralelo al motor en armarios con ambos definidos).
    if snap_chim is not None:
        story.append(PageBreak())
        story += _seccion_chimenea(styles, snap_chim, res_chim)

    # 7. Resultados globales (incluye gráfica balance)
    story.append(PageBreak())
    story += _seccion_resultados_globales(
        styles,
        snap_global=snap_full.get("resultados_globales") or {},
        condiciones=snap_full.get("condiciones_operacion_P7") or {},
        figuras=figs_p7,
    )

    doc.build(story)
    return buf.getvalue()
