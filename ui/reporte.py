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
from typing import Any, Callable

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

from ui.componentes.traducciones import IDIOMA_DEFAULT, campo_i18n, traducir

# Traductor enhebrado a las secciones: tr("colector.titulo", **kwargs) →
# traducir("reporte.colector.titulo", idioma, **kwargs). Ver F6 del plan i18n.
Tr = Callable[..., str]


def _hacer_tr(idioma: str) -> Tr:
    """Construye el closure de traducción del reporte para un idioma.

    El closure expone ``.idioma`` para que ``_bloque_advertencias`` pueda
    retraducir los mensajes por código contra el namespace ``advertencias.*``
    (F5) sin enhebrar el idioma por separado.
    """

    def tr(clave: str, **kwargs: Any) -> str:
        return traducir(f"reporte.{clave}", idioma, **kwargs)

    tr.idioma = idioma  # type: ignore[attr-defined]
    return tr


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


def _figuras_p2(proyecto, tr: Tr) -> list[tuple[str, bytes]]:
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
        (tr("p2.fig.temperatura"), _fig_temperatura(datos_local)),
        (tr("p2.fig.irradiacion"), _fig_irradiancia(datos_local)),
        (tr("p2.fig.viento_hr"), _fig_viento_hr(datos_local)),
    ]:
        png = _fig_a_png(fig)
        if png:
            out.append((titulo, png))

    try:
        from core.proyecto import Tipologia

        es_caja = getattr(getattr(proyecto, "configuracion", None), "tipologia", None) == (
            Tipologia.CAJA
        )
        camara = getattr(proyecto, "camara", None)
        if es_caja and camara is not None:
            pendiente_poa = camara.geometria.pendiente_techo_deg
            acimut_pvlib = acimut_duffie_a_pvlib(camara.geometria.acimut_camara_deg)
            titulo_poa = tr("p2.fig.poa_techo")
        else:
            pendiente_poa = empl.pendiente_colector_deg
            acimut_pvlib = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
            titulo_poa = tr("p2.fig.poa_colector")
        poa = _calcular_poa_horaria(
            datos_local,
            empl.latitud_deg,
            empl.longitud_deg,
            empl.altitud_m,
            pendiente_poa,
            acimut_pvlib,
            albedo=empl.albedo_suelo,
        )
        png = _fig_a_png(
            _fig_irradiancia_comparativa(datos_local, poa),
            height=620,
        )
        if png:
            out.append((titulo_poa, png))
    except Exception:
        pass
    return out


def _figuras_p3(session_state, tr: Tr) -> list[tuple[str, bytes]]:
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
            out.append((tr("colector.fig.t_salida_dia", label=label), png))
        png = _fig_a_png(_fig_T_fluido_dia(r, label))
        if png:
            out.append((tr("colector.fig.perfil_dia", label=label), png))
    elif modo == "anual":
        png = _fig_a_png(_fig_T_salida_anual(r))
        if png:
            out.append((tr("colector.fig.t_salida_anual"), png))
        png = _fig_a_png(_fig_T_fluido_anual(r))
        if png:
            out.append((tr("colector.fig.perfil_anual"), png))
    return out


def _figuras_p4(proyecto, session_state, tr: Tr) -> list[tuple[str, bytes]]:
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
                out.append((tr("camara.fig.td"), png))
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
                out.append((tr("camara.fig.capa_fina", prod=prod_id), png))
        except Exception:
            pass
    return out


def _figuras_p7(
    res, tr: Tr, proyecto=None, *, HR_cam_pct: float | None = 20.0
) -> list[tuple[str, bytes]]:
    """Devuelve [(título, png_bytes), ...] del balance global (P7)."""
    out: list[tuple[str, bytes]] = []
    if res is None:
        return out
    from ui.p7_resultados import _fig_sankey_simplificado

    try:
        sankey = _fig_sankey_simplificado(res)
        png = _fig_a_png(sankey)
        if png:
            out.append((tr("global.fig.sankey"), png))
    except Exception:
        pass

    # Carta psicrométrica del proceso (mejora 27).
    if proyecto is not None:
        try:
            from calculos.balance_global import presion_representativa_proyecto
            from calculos.psicrometria import humedad_absoluta
            from ui.componentes.carta_psicrometrica import fig_carta_psicrometrica

            omega_amb = None
            # Modo Constantes (sin forzantes): ω desde HR_cam + T_ent + P.
            T_in = getattr(res, "T_entrada_camara_K", None)
            if (
                T_in is not None
                and HR_cam_pct is not None
                and getattr(res, "forzantes_aplicadas", None) is None
            ):
                try:
                    P_Pa, _ = presion_representativa_proyecto(proyecto)
                except Exception:
                    P_Pa = 101325.0
                try:
                    omega_amb = humedad_absoluta(HR_cam_pct / 100.0, float(T_in), P_Pa)
                except ValueError:
                    omega_amb = None
            carta = fig_carta_psicrometrica(res, proyecto, omega_amb=omega_amb)
            png = _fig_a_png(carta)
            if png:
                out.append((tr("global.fig.carta"), png))
        except Exception:
            pass
    return out


def _figuras_ventana(res, tr: Tr, proyecto=None) -> list[tuple[str, bytes]]:
    """Figuras del modo Ventana (gran escala): perfil del túnel + carta."""
    out: list[tuple[str, bytes]] = []
    if res is None:
        return out
    # Perfil espacial del túnel (solo semicontinuo con perfil disponible).
    if getattr(res, "perfil_X_zonas", None) is not None and len(res.perfil_X_zonas):
        try:
            from ui.p7_resultados import _fig_perfil_tunel

            png = _fig_a_png(_fig_perfil_tunel(res))
            if png:
                out.append((tr("ventana.fig.perfil"), png))
        except Exception:
            pass
    # Carta psicrométrica del proceso (fig_carta_psicrometrica ya soporta
    # ResultadoVentana vía los campos aire_*).
    if proyecto is not None:
        try:
            from ui.componentes.carta_psicrometrica import fig_carta_psicrometrica

            png = _fig_a_png(fig_carta_psicrometrica(res, proyecto))
            if png:
                out.append((tr("global.fig.carta"), png))
        except Exception:
            pass
    return out


def _figuras_anual(res_anual, tr: Tr) -> list[tuple[str, bytes]]:
    """Figura de barras kg/mes + η_total de la operación anual (si convierte)."""
    out: list[tuple[str, bytes]] = []
    if res_anual is None:
        return out
    try:
        from ui.p7_resultados import _fig_operacion_anual

        png = _fig_a_png(_fig_operacion_anual(res_anual))
        if png:
            out.append((tr("anual.fig.kg_mes"), png))
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
    buf: io.BytesIO, logos: dict[str, str | None], titulo_proyecto: str, tr: Tr
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
        canvas.drawCentredString(ancho / 2, alto - 1.3 * cm, tr("cab.titulo_marca"))
        canvas.setFont(_FONT_REGULAR, 8)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawCentredString(ancho / 2, alto - 1.75 * cm, tr("cab.institucion"))
        if titulo_proyecto:
            canvas.setFont(_FONT_ITALIC, 8)
            canvas.drawCentredString(
                ancho / 2, alto - 2.15 * cm, tr("cab.proyecto", titulo=titulo_proyecto)
            )
        # Línea separadora
        canvas.setStrokeColor(_COLOR_LINEA)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * cm, alto - 2.55 * cm, ancho - 1.5 * cm, alto - 2.55 * cm)
        # Footer
        canvas.setFont(_FONT_REGULAR, 8)
        canvas.setFillColor(HexColor("#888888"))
        canvas.drawCentredString(ancho / 2, 1.0 * cm, tr("cab.pagina", n=doc.page))
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
        title=tr("cab.doc_titulo", titulo=titulo_proyecto or tr("cab.doc_titulo_default")),
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


def _fmt(val: Any, default: str = "—", *, tr: Tr | None = None) -> str:
    if val is None:
        return default
    if isinstance(val, bool):
        if tr is not None:
            return tr("comun.si") if val else tr("comun.no")
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


def _portada(
    styles, tr: Tr, snap_meta: dict, snap_cfg: dict, snap_empl: dict, snap_clima: dict
) -> list:
    """Bloque inicial: metadatos + P1 + P2 + clima."""
    elems: list = []
    elems.append(Paragraph(tr("portada.resumen"), styles["h1"]))

    rows_meta = [
        [tr("portada.meta.proyecto"), snap_meta.get("nombre", "—")],
        [tr("portada.meta.autor"), snap_meta.get("autor") or "—"],
        [tr("portada.meta.fecha_creacion"), snap_meta.get("fecha_creacion", "—")],
        [tr("portada.meta.fecha_modif"), snap_meta.get("fecha_modificacion", "—")],
        [tr("portada.meta.version"), snap_meta.get("version_software", "—")],
    ]
    if snap_meta.get("notas"):
        rows_meta.append([tr("portada.meta.notas"), snap_meta["notas"]])
    elems.append(_tabla_kv(rows_meta))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(tr("portada.p1.titulo"), styles["h2"]))
    rows_cfg = [
        [tr("portada.p1.tipologia"), _fmt(snap_cfg.get("tipologia"))],
        [tr("portada.p1.modo"), _fmt(snap_cfg.get("modo_analisis"))],
        [tr("portada.p1.dia"), _fmt(snap_cfg.get("dia_analisis"))],
    ]
    if snap_cfg.get("fecha_especifica"):
        rows_cfg.append([tr("portada.p1.fecha_esp"), snap_cfg["fecha_especifica"]])
    if snap_cfg.get("subtipo_gran_escala"):
        rows_cfg.append([tr("portada.p1.subtipo"), _fmt(snap_cfg.get("subtipo_gran_escala"))])
    if snap_cfg.get("ventana_inicio") and snap_cfg.get("ventana_fin"):
        rows_cfg.append(
            [
                tr("portada.p1.ventana_lapso"),
                f"{snap_cfg['ventana_inicio']} → {snap_cfg['ventana_fin']}",
            ]
        )
    elems.append(_tabla_kv(rows_cfg))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(tr("portada.empl.titulo"), styles["h2"]))
    if not snap_empl:
        elems += _seccion_pendiente(styles, tr("portada.empl.pendiente"))
    else:
        rows_empl = [
            [tr("portada.empl.latitud"), f"{snap_empl.get('latitud_deg', '—')}°"],
            [tr("portada.empl.longitud"), f"{snap_empl.get('longitud_deg', '—')}°"],
            [tr("portada.empl.altitud"), f"{_fmt(snap_empl.get('altitud_m'))} m"],
        ]
        # Sin colector externo (CAJA), el snapshot no trae estos campos — la
        # orientación de la cámara se reporta en la sección de Cámara (P4).
        if "acimut_colector_deg_duffie" in snap_empl:
            rows_empl.append(
                [
                    tr("portada.empl.acimut_col"),
                    f"{snap_empl.get('acimut_colector_deg_duffie', '—')}° "
                    f"({tr('portada.empl.sur_nota')})",
                ]
            )
            rows_empl.append(
                [
                    tr("portada.empl.pendiente_col"),
                    f"{snap_empl.get('pendiente_colector_deg', '—')}°",
                ]
            )
        rows_empl += [
            [tr("portada.empl.albedo"), f"{_fmt(snap_empl.get('albedo_suelo'))}"],
            [tr("portada.empl.tz"), snap_empl.get("zona_horaria", "—")],
        ]
        elems.append(_tabla_kv(rows_empl))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(tr("portada.clima.titulo"), styles["h2"]))
    if not snap_clima:
        elems += _seccion_pendiente(styles, tr("portada.clima.pendiente"))
    else:
        fuente_clima = snap_clima.get("fuente") or "nasa_power"
        rows_clima = [
            [tr("portada.clima.fuente"), tr(f"portada.clima.fuente_{fuente_clima}")],
            [tr("portada.clima.anio"), _fmt(snap_clima.get("anio"))],
            [tr("portada.clima.altitud_nasa"), f"{_fmt(snap_clima.get('altitud_nasa_m'))} m"],
            [tr("portada.clima.horas"), _fmt(snap_clima.get("n_horas"))],
            [tr("portada.clima.t_media"), f"{_fmt(snap_clima.get('T_amb_media_C'))} °C"],
            [tr("portada.clima.ghi_media"), f"{_fmt(snap_clima.get('GHI_media_W_m2'))} W/m²"],
        ]
        cal = snap_clima.get("calidad") or {}
        rows_clima += [
            [tr("portada.clima.huecos"), _fmt(cal.get("n_huecos_originales"))],
            [tr("portada.clima.horas_interp"), _fmt(cal.get("n_horas_interpoladas"))],
            [tr("portada.clima.horas_bloq"), _fmt(cal.get("n_horas_bloqueadas"))],
            [tr("portada.clima.mayor_hueco"), _fmt(cal.get("mayor_hueco_h"))],
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


def _seccion_colector(
    styles, tr: Tr, snap_col: dict | None, figuras: list[tuple[str, bytes]]
) -> list:
    elems: list = [Paragraph(tr("colector.titulo"), styles["h1"])]
    if snap_col is None:
        elems += _seccion_pendiente(styles, tr("colector.pendiente_sin"))
        return elems

    u = snap_col.get("unidad", {})
    mats = snap_col.get("materiales", {})
    banco = snap_col.get("banco", {})
    deriv = snap_col.get("derivados", {})

    elems.append(Paragraph(tr("colector.materiales"), styles["h2"]))
    rows = []
    for clave_tr, key in [
        ("colector.mat.cubierta", "cubierta"),
        ("colector.mat.placa", "placa"),
        ("colector.mat.aislante", "aislante"),
        ("colector.mat.fondo", "fondo"),
    ]:
        m = mats.get(key, {})
        props = m.get("props_catalogo", {}) or {}
        descripcion = campo_i18n(props, "descripcion", getattr(tr, "idioma", IDIOMA_DEFAULT))
        texto_valor = (
            f"{descripcion or m.get('id', '—')}  "
            f"[id={m.get('id', '—')}, e={_fmt(m.get('espesor_m'))} m]"
        )
        # Paragraph para que el texto largo haga line-wrap dentro de la celda
        rows.append([tr(clave_tr), Paragraph(texto_valor, styles["p_celda"])])
    elems.append(_tabla_kv(rows))
    elems.append(Spacer(1, 8))

    elems.append(Paragraph(tr("colector.geo_banco"), styles["h2"]))
    rows_geo = [
        [
            tr("colector.tipo_col"),
            f"{u.get('tipo_colector')} — {u.get('tipo_colector_descripcion', '—')}",
        ],
        [tr("colector.ancho_largo"), f"{_fmt(u.get('ancho_m'))} × {_fmt(u.get('largo_m'))} m"],
        [tr("colector.espaciado"), f"{_fmt(u.get('espaciado_m'))} m"],
        [tr("colector.n_cubiertas"), _fmt(u.get("n_cubiertas"))],
        [tr("colector.vel"), f"{_fmt(u.get('velocidad_diseno_ms'))} m/s"],
        [
            tr("colector.banco"),
            tr(
                "colector.banco_val",
                serie=banco.get("n_serie", 1),
                paralelo=banco.get("n_paralelo", 1),
            ),
        ],
        [tr("colector.area"), f"{_fmt(deriv.get('area_total_m2'))} m²"],
        [tr("colector.caudal"), f"{_fmt(deriv.get('caudal_total_m3_s'))} m³/s"],
        [tr("colector.camino"), f"{_fmt(deriv.get('largo_camino_aire_m'))} m"],
    ]
    elems.append(_tabla_kv(rows_geo))

    # Resultados
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(tr("colector.res_titulo"), styles["h2"]))
    res = snap_col.get("resultados") or {}
    if not res.get("ejecutado"):
        elems += _seccion_pendiente(styles, tr("colector.res_pendiente"))
    else:
        modo = res.get("modo")
        resumen = res.get("resumen") or {}
        if modo == "diario":
            rows_res = [
                [tr("colector.dia_rep"), res.get("dia_representativo", "—")],
                [tr("colector.t_sal_max"), f"{_fmt(resumen.get('T_salida_max_C'))} °C"],
                [tr("colector.t_sal_med"), f"{_fmt(resumen.get('T_salida_mediodia_C'))} °C"],
                [tr("colector.dt_max"), f"{_fmt(resumen.get('delta_T_max_C'))} °C"],
                [tr("colector.horas_sol"), _fmt(resumen.get("n_horas_con_radiacion"))],
            ]
            elems.append(_tabla_kv(rows_res))
        elif modo == "anual":
            rows_res = [
                [
                    tr("colector.mejor_mes"),
                    f"{resumen.get('T_salida_max_mes', '—')} — "
                    f"{_fmt(resumen.get('T_salida_max_C'))} °C",
                ],
                [
                    tr("colector.peor_mes"),
                    f"{resumen.get('T_salida_min_mes', '—')} — "
                    f"{_fmt(resumen.get('T_salida_min_C'))} °C",
                ],
                [tr("colector.dt_min"), f"{_fmt(resumen.get('delta_T_min_C'))} °C"],
            ]
            elems.append(_tabla_kv(rows_res))

    elems += _bloque_advertencias(styles, tr, snap_col.get("advertencias_diseno"))

    # Figuras
    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        tr("colector.graficas"),
        figuras,
        msg_pendiente=tr("comun.graficas_no_calc"),
    )
    return elems


def _seccion_camara(
    styles, tr: Tr, snap_cam: dict | None, figuras: list[tuple[str, bytes]]
) -> list:
    elems: list = [Paragraph(tr("camara.titulo"), styles["h1"])]
    if snap_cam is None:
        elems += _seccion_pendiente(styles, tr("camara.pendiente_sin"))
        return elems

    g = snap_cam.get("geometria", {})
    cn = snap_cam.get("construccion", {})
    b = snap_cam.get("bandejas", {})
    c = snap_cam.get("carga_producto", {})
    f = snap_cam.get("flujo", {})

    elems.append(Paragraph(tr("camara.geo_modo"), styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                [
                    tr("camara.lwh"),
                    f"{_fmt(g.get('largo_m'))} × {_fmt(g.get('ancho_m'))} × "
                    f"{_fmt(g.get('alto_m'))} m",
                ],
                [tr("camara.volumen"), f"{_fmt(g.get('volumen_m3'))} m³"],
                [
                    tr("camara.orient"),
                    f"{_fmt(g.get('acimut_camara_deg'))}° ({tr('camara.sur_nota')})",
                ],
                [
                    tr("camara.pend_techo"),
                    f"{_fmt(g.get('pendiente_techo_deg'))}° ({g.get('cara_caida_techo', '—')})",
                ],
                [tr("camara.motor_num"), snap_cam.get("modo_calculo", "—")],
            ]
        )
    )

    elems.append(Spacer(1, 6))
    elems.append(Paragraph(tr("camara.constr"), styles["h2"]))
    pared = cn.get("pared", {})
    caras_t = cn.get("caras_translucidas") or {}
    caras_activas_str = ", ".join(nombre for nombre, activa in caras_t.items() if activa) or "—"
    rows_pared = [
        [tr("camara.mat_vidr"), cn.get("cubierta_translucida_id") or tr("comun.opaca")],
        [tr("camara.caras_t"), caras_activas_str],
        [tr("camara.a_rad"), f"{_fmt(cn.get('A_rad_m2'))} m²"],
        [tr("camara.pared_comp"), _fmt(bool(pared.get("es_compuesta")), tr=tr)],
        [tr("camara.capas"), str(len(pared.get("capas", [])))],
        [tr("camara.esp_pared"), f"{_fmt(pared.get('espesor_total_m'))} m"],
        [tr("camara.r_pared"), f"{_fmt(pared.get('R_total_m2K_W'))} m²·K/W"],
        [tr("camara.u_pared"), f"{_fmt(pared.get('U_pared_W_m2K'))} W/(m²·K)"],
    ]
    elems.append(_tabla_kv(rows_pared))

    elems.append(Spacer(1, 6))
    elems.append(Paragraph(tr("camara.bandejas_titulo"), styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                [
                    tr("camara.n_band"),
                    f"{b.get('n_bandejas', '—')}  /  " f"{_fmt(b.get('area_bandeja_m2'))} m²",
                ],
                [tr("camara.esp_capa"), f"{_fmt(b.get('espesor_capa_m'))} m"],
                [tr("camara.sep_band"), f"{_fmt(b.get('separacion_entre_bandejas_m'))} m"],
                [
                    tr("camara.producto"),
                    f"{c.get('producto_id', '—')} " f"({c.get('categoria', '—')})",
                ],
                [tr("camara.masa"), f"{_fmt(c.get('masa_total_kg'))} kg"],
                [
                    tr("camara.x_obj"),
                    f"{_fmt(c.get('humedad_inicial_X'))} → "
                    f"{_fmt(c.get('humedad_objetivo_X'))} kg/kg ms",
                ],
                [
                    tr("camara.modelo"),
                    f"{c.get('modelo_capa_fina', '—')} / " f"{c.get('modelo_isoterma', '—')}",
                ],
                [tr("camara.caudal_masico"), f"{_fmt(f.get('caudal_masico_kg_s'))} kg/s"],
                [tr("camara.direccion"), f.get("direccion_flujo", "—")],
                [
                    tr("camara.hr_ent"),
                    _fmt(f.get("HR_entrada_fraccion"), default=tr("comun.fallback")),
                ],
            ]
        )
    )

    elems.append(Spacer(1, 8))
    elems.append(Paragraph(tr("camara.res_titulo"), styles["h2"]))
    r = snap_cam.get("resultados") or {}
    if not r.get("ejecutado"):
        elems += _seccion_pendiente(styles, tr("camara.res_pendiente"))
    else:
        res = r.get("resumen") or {}
        if r.get("tipo") == "termodinamico_horizonte":
            elems.append(
                _tabla_kv(
                    [
                        [tr("camara.status"), res.get("status", "—")],
                        [tr("camara.t_sim"), f"{_fmt(res.get('t_simulacion_h'))} h"],
                        [tr("camara.t_secado"), f"{_fmt(res.get('t_secado_h'))} h"],
                        [tr("camara.agua_evap"), f"{_fmt(res.get('masa_evaporada_total_kg'))} kg"],
                        [
                            tr("camara.x_ini_fin"),
                            f"{_fmt(res.get('X_prod_inicial'))} → "
                            f"{_fmt(res.get('X_prod_final'))} kg/kg ms",
                        ],
                        [tr("camara.t_prod_fin"), f"{_fmt(res.get('T_prod_final_C'))} °C"],
                        [tr("camara.t_prod_max"), f"{_fmt(res.get('T_max_alcanzada_C'))} °C"],
                        [tr("camara.hr_max"), _fmt(res.get("HR_max"))],
                        [tr("camara.e_rad"), f"{_fmt(res.get('energia_rad_total_MJ'))} MJ"],
                    ]
                )
            )
        else:
            elems.append(
                _tabla_kv(
                    [
                        [tr("camara.modelo_aplic"), res.get("modelo_usado", "—")],
                        [
                            tr("camara.x_eq"),
                            f"{_fmt(res.get('X_eq_kg_kg'))} kg/kg ms "
                            f"({res.get('fuente_X_eq', '—')})",
                        ],
                        [tr("camara.t_secado"), f"{_fmt(res.get('t_secado_h'))} h"],
                        [tr("camara.agua_extr"), f"{_fmt(res.get('masa_agua_extraida_kg'))} kg"],
                        [tr("camara.mr_obj"), _fmt(res.get("MR_obj"))],
                        [
                            tr("camara.convergencia"),
                            (
                                tr("comun.ok")
                                if res.get("convergencia_ok")
                                else res.get("mensaje_convergencia", "falla")
                            ),
                        ],
                    ]
                )
            )

    elems += _bloque_advertencias(styles, tr, snap_cam.get("advertencias_diseno"))

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        tr("camara.graficas"),
        figuras,
        msg_pendiente=tr("comun.graficas_no_calc"),
    )
    return elems


def _seccion_auxiliar(styles, tr: Tr, snap_aux: dict | None) -> list:
    elems: list = [Paragraph(tr("auxiliar.titulo"), styles["h1"])]
    if snap_aux is None:
        elems += _seccion_pendiente(styles, tr("auxiliar.pendiente_sin"))
        return elems
    rows = [
        [tr("auxiliar.tipo"), snap_aux.get("tipo", "—")],
        [tr("auxiliar.modo_op"), snap_aux.get("modo_operacion", "—")],
        [
            tr("auxiliar.pot_nom"),
            f"{_fmt(snap_aux.get('potencia_nominal_W'))} W "
            f"({_fmt((snap_aux.get('potencia_nominal_W') or 0) / 1000)} kW)",
        ],
        [tr("auxiliar.frac_op"), _fmt(snap_aux.get("fraccion_potencia_operacion"))],
        [tr("auxiliar.pot_efe"), f"{_fmt(snap_aux.get('potencia_efectiva_W'))} W"],
        [tr("auxiliar.t_max"), f"{(_fmt(snap_aux.get('temperatura_maxima_salida_K')))} K"],
        [tr("auxiliar.disp_noct"), _fmt(snap_aux.get("disponible_nocturno"), tr=tr)],
    ]
    if snap_aux.get("biomasa"):
        bm = snap_aux["biomasa"]
        rows += [
            [tr("auxiliar.combustible"), bm.get("tipo_biomasa", "—")],
            [tr("auxiliar.pci"), f"{_fmt(bm.get('PCI_MJ_kg'))} MJ/kg"],
            [tr("auxiliar.eta_quem"), _fmt(bm.get("eficiencia_quemador"))],
            [tr("auxiliar.consumo"), f"{_fmt(bm.get('consumo_biomasa_efectivo_kg_h'))} kg/h"],
        ]
    if snap_aux.get("resistencia_electrica"):
        re = snap_aux["resistencia_electrica"]
        rows += [
            [tr("auxiliar.tension"), f"{_fmt(re.get('tension_V'))} V"],
            [tr("auxiliar.corriente"), f"{_fmt(re.get('corriente_estimada_A'))} A"],
        ]
    elems.append(_tabla_kv(rows))
    if snap_aux.get("notas"):
        elems.append(Spacer(1, 4))
        elems.append(
            Paragraph(f"<i>{tr('comun.notas_prefijo')}</i> {snap_aux['notas']}", styles["p"])
        )
    elems += _bloque_advertencias(styles, tr, snap_aux.get("advertencias_diseno"))
    elems += _seccion_pendiente(styles, tr("auxiliar.nota_p7"))
    return elems


def _seccion_motor(styles, tr: Tr, snap_mot: dict | None) -> list:
    elems: list = [Paragraph(tr("motor.titulo"), styles["h1"])]
    if snap_mot is None:
        elems += _seccion_pendiente(styles, tr("motor.pendiente_sin"))
        return elems
    dp = snap_mot.get("perdida_de_carga", {})
    ef = snap_mot.get("eficiencias", {})
    rows = [
        [tr("motor.tipo_acc"), snap_mot.get("tipo_accionamiento", "—")],
        [tr("motor.caudal_vol"), f"{_fmt(snap_mot.get('caudal_volumetrico_m3_s'))} m³/s"],
        [tr("motor.dp_total"), f"{_fmt(dp.get('delta_P_total_Pa'))} Pa"],
        [tr("motor.dp_colector"), f"{_fmt(dp.get('delta_P_colector_Pa'))} Pa"],
        [tr("motor.dp_camara"), f"{_fmt(dp.get('delta_P_camara_Pa'))} Pa"],
        [tr("motor.dp_ductos"), f"{_fmt(dp.get('delta_P_ductos_Pa'))} Pa"],
        [tr("motor.dp_singulares"), f"{_fmt(dp.get('delta_P_singulares_Pa'))} Pa"],
        [tr("motor.eta_vent"), _fmt(ef.get("eficiencia_ventilador"))],
        [tr("motor.eta_motor"), _fmt(ef.get("eficiencia_motor"))],
        [tr("motor.factor_serv"), _fmt(ef.get("factor_servicio"))],
    ]
    res = snap_mot.get("resultados") or {}
    if res.get("ejecutado"):
        rows += [
            [tr("motor.p_hid"), f"{_fmt(res.get('potencia_hidraulica_W'))} W"],
            [tr("motor.p_eje"), f"{_fmt(res.get('potencia_eje_W'))} W"],
            [tr("motor.p_elec"), f"{_fmt(res.get('potencia_electrica_W'))} W"],
            [tr("motor.p_inst"), f"{_fmt(res.get('potencia_a_instalar_W'))} W"],
            [tr("motor.corriente_nom"), f"{_fmt(res.get('corriente_nominal_A'))} A"],
        ]
    elems.append(_tabla_kv(rows))
    if snap_mot.get("notas"):
        elems.append(Spacer(1, 4))
        elems.append(
            Paragraph(f"<i>{tr('comun.notas_prefijo')}</i> {snap_mot['notas']}", styles["p"])
        )
    elems += _bloque_advertencias(styles, tr, snap_mot.get("advertencias_diseno"))
    return elems


def _seccion_chimenea(
    styles,
    tr: Tr,
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
    elems: list = [Paragraph(tr("chimenea.titulo"), styles["h1"])]
    if snap_chim is None:
        elems += _seccion_pendiente(styles, tr("chimenea.pendiente_sin"))
        return elems

    ch = snap_chim.get("chimenea", {})
    ext = ch.get("extractor", {}) or {}

    # --- Geometría y material ---
    elems.append(Paragraph(tr("chimenea.geo_mat"), styles["h2"]))
    rows_geo = [
        [tr("chimenea.diam_int"), f"{_fmt(ch.get('diametro_m'))} m"],
        [tr("chimenea.altura"), f"{_fmt(ch.get('altura_m'))} m"],
        [tr("chimenea.material"), ch.get("id_material", "—")],
    ]
    props = ch.get("props_catalogo") or {}
    descripcion = campo_i18n(props, "descripcion", getattr(tr, "idioma", IDIOMA_DEFAULT))
    if descripcion:
        rows_geo.append([tr("chimenea.descripcion"), descripcion])
    elems.append(_tabla_kv(rows_geo))

    # --- Extractor eólico (si está activo) ---
    if ext.get("activo"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("chimenea.extractor_titulo"), styles["h2"]))
        rows_ext = [
            [tr("chimenea.diam_ext"), f"{_fmt(ext.get('diametro_extractor_m'))} m"],
            [tr("chimenea.cp"), _fmt(ext.get("Cp_turbina"))],
            [tr("chimenea.kt"), _fmt(ext.get("Kt_turbina"))],
            [tr("chimenea.z0"), f"{_fmt(ext.get('z0_terreno_m'))} m"],
        ]
        elems.append(_tabla_kv(rows_ext))
    else:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(f"<i>{tr('chimenea.sin_extractor')}</i>", styles["p"]))

    # --- Resultados del lazo natural resuelto en P7 (Picard completo) ---
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(tr("chimenea.lazo_titulo"), styles["h2"]))
    if res_chim is None:
        elems += _seccion_pendiente(styles, tr("chimenea.lazo_pendiente"))
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
                [tr("chimenea.modo_calc"), tr("chimenea.modo_transitorio")],
                [tr("chimenea.caudal_prom"), f"{m_prom * 1000:.2f} g/s ({_fmt(m_prom)} kg/s)"],
                [tr("chimenea.caudal_max"), f"{m_max * 1000:.2f} g/s ({_fmt(m_max)} kg/s)"],
                [tr("chimenea.h_eff"), f"{_fmt(H_eff)} m"],
                [tr("chimenea.iter_picard"), _fmt(iter_picard)],
                [tr("chimenea.convergio"), _fmt(bool(convergio), tr=tr)],
            ]
            if delta_T_final is not None:
                rows_res.append([tr("chimenea.dt_final"), f"{_fmt(delta_T_final)} K"])
            if horas_sin_tiro is not None:
                rows_res.append([tr("chimenea.horas_sin_tiro"), _fmt(horas_sin_tiro)])
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
                [tr("chimenea.modo_calc"), tr("chimenea.modo_constantes")],
                [tr("chimenea.caudal_nat"), f"{m_punto * 1000:.2f} g/s ({_fmt(m_punto)} kg/s)"],
                [tr("chimenea.vel_chim"), f"{_fmt(v_chim)} m/s"],
                [tr("chimenea.re_chim"), f"{Re_chim:.0f}"],
                [tr("chimenea.dp_tiro"), f"{_fmt(dP_tiro)} Pa"],
                [tr("chimenea.dp_ducto"), f"{_fmt(dP_ducto)} Pa"],
                [tr("chimenea.dp_resto"), f"{_fmt(dP_resto)} Pa"],
                [tr("chimenea.h_eff"), f"{_fmt(H_eff)} m"],
                [tr("chimenea.iter_picard"), _fmt(iter_picard)],
                [tr("chimenea.convergio"), _fmt(bool(convergio), tr=tr)],
            ]
            if dP_turb > 0.0 or ext.get("activo"):
                rows_res.append([tr("chimenea.dp_motriz"), f"{_fmt(dP_turb)} Pa"])
                rows_res.append([tr("chimenea.viento_tope"), f"{_fmt(v_loc)} m/s"])
            if T_chim_K is not None:
                try:
                    rows_res.append([tr("chimenea.t_chim"), f"{float(T_chim_K) - 273.15:.1f} °C"])
                except (TypeError, ValueError):
                    pass
            if delta_T_final is not None:
                rows_res.append([tr("chimenea.dt_final"), f"{_fmt(delta_T_final)} K"])
        elems.append(_tabla_kv(rows_res))

        # Advertencias del solver (deduplicadas por código)
        advs_solver = res_chim.get("advertencias") or []
        if advs_solver:
            elems.append(Spacer(1, 4))
            elems.append(Paragraph(f"<i>{tr('chimenea.avisos_solver')}</i>", styles["p"]))
            for a in advs_solver:
                if a:
                    elems.append(Paragraph(f"• {a}", styles["p"]))

    # --- Advertencias estáticas del diseño de chimenea ---
    elems += _bloque_advertencias(styles, tr, snap_chim.get("advertencias_diseno"))
    return elems


def _seccion_resultados_globales(
    styles, tr: Tr, snap_global: dict, condiciones: dict, figuras: list[tuple[str, bytes]]
) -> list:
    elems: list = [Paragraph(tr("global.titulo"), styles["h1"])]
    elems.append(Paragraph(tr("global.cond_titulo"), styles["h2"]))
    elems.append(
        _tabla_kv(
            [
                [tr("global.t_amb"), f"{_fmt(condiciones.get('T_amb_C'))} °C"],
                [tr("global.irr_poa"), f"{_fmt(condiciones.get('I_g_POA_W_m2'))} W/m²"],
                [tr("global.vel_viento"), f"{_fmt(condiciones.get('v_viento_ms'))} m/s"],
                [tr("global.hr_cam"), f"{_fmt(condiciones.get('HR_camara_pct'))} %"],
            ]
        )
    )

    elems.append(Spacer(1, 8))
    elems.append(Paragraph(tr("global.balance_titulo"), styles["h2"]))
    rows = [
        [tr("global.e_total"), f"{_fmt(snap_global.get('energia_total_MJ'))} MJ"],
        [tr("global.solar_util"), f"{_fmt(snap_global.get('energia_solar_util_MJ'))} MJ"],
        [tr("global.auxiliar"), f"{_fmt(snap_global.get('energia_auxiliar_MJ'))} MJ"],
        [tr("global.motor"), f"{_fmt(snap_global.get('energia_motor_MJ'))} MJ"],
        [tr("global.secado"), f"{_fmt(snap_global.get('energia_secado_MJ'))} MJ"],
        [tr("global.cop"), _fmt(snap_global.get("COP_secado"))],
        [tr("global.frac_solar"), _fmt(snap_global.get("fraccion_solar"))],
        [tr("global.t_ent_cam"), f"{_fmt(snap_global.get('T_entrada_camara_C'))} °C"],
    ]
    elems.append(_tabla_kv(rows))

    # Sub-bloques colector/aux/camara dentro del global
    if snap_global.get("colector"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("global.col_titulo"), styles["h2"]))
        col = snap_global["colector"]
        elems.append(
            _tabla_kv(
                [
                    [
                        tr("global.col_t_es"),
                        f"{_fmt(col.get('T_entrada_K'))} → " f"{_fmt(col.get('T_salida_K'))} K",
                    ],
                    [tr("global.col_q"), f"{_fmt(col.get('Q_util_W'))} W"],
                    [tr("global.col_eta"), _fmt(col.get("eta_termica"))],
                    [tr("global.col_regimen"), _fmt(col.get("regimen_flujo"))],
                    [tr("global.col_re"), _fmt(col.get("Re_medio"))],
                    [tr("global.col_hint"), f"{_fmt(col.get('h_int_medio'))} W/(m²·K)"],
                ]
            )
        )

    if snap_global.get("camara"):
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("global.cam_titulo"), styles["h2"]))
        c = snap_global["camara"]
        if c.get("modo_calculo") == "termodinamico":
            elems.append(
                _tabla_kv(
                    [
                        [tr("global.cam_modo"), tr("global.cam_modo_td")],
                        [tr("global.cam_t_secado"), f"{_fmt(c.get('t_secado_h'))} h"],
                        [tr("global.cam_agua_evap"), f"{_fmt(c.get('masa_evaporada_kg'))} kg"],
                        [tr("global.cam_x_final"), _fmt(c.get("X_final"))],
                        [tr("global.cam_t_prod"), f"{_fmt(c.get('T_prod_final_C'))} °C"],
                        [tr("global.cam_status"), c.get("status", "—")],
                    ]
                )
            )
        else:
            elems.append(
                _tabla_kv(
                    [
                        [tr("global.cam_modo"), tr("global.cam_modo_cf")],
                        [tr("global.cam_t_secado"), f"{_fmt(c.get('t_secado_h'))} h"],
                        [tr("global.cam_agua_extr"), f"{_fmt(c.get('masa_agua_extraida_kg'))} kg"],
                        [tr("global.cam_x_eq"), _fmt(c.get("X_eq_kg_kg"))],
                        [tr("global.cam_conv"), _fmt(c.get("convergencia_ok"), tr=tr)],
                    ]
                )
            )

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        tr("global.graficas"),
        figuras,
        msg_pendiente=tr("global.graficas_pendiente"),
    )
    return elems


def _seccion_ventana(styles, tr: Tr, snap_ventana: dict, figuras: list[tuple[str, bytes]]) -> list:
    """Sección de producción en ventana (gran escala, batch/semicontinuo).

    Consume el snapshot ``resultado_ventana`` de ``_json_resultado_ventana``
    (dict puro), no el dataclass — mismo criterio que el resto de secciones.
    """
    elems: list = [Paragraph(tr("ventana.titulo"), styles["h1"])]
    if not snap_ventana:
        return elems + _seccion_pendiente(styles, tr("ventana.pendiente"))

    horizonte_s = snap_ventana.get("horizonte_s") or 0.0
    rows = [
        [tr("ventana.subtipo"), _fmt(snap_ventana.get("subtipo"))],
        [tr("ventana.horizonte"), f"{horizonte_s / 86400.0:.1f} d ({horizonte_s / 3600.0:.0f} h)"],
        [tr("ventana.masa_seca"), f"{_fmt(snap_ventana.get('masa_seca_producida_kg'))} kg"],
        [tr("ventana.agua_evap"), f"{_fmt(snap_ventana.get('masa_evaporada_kg'))} kg"],
        [tr("ventana.tasa_regimen"), f"{_fmt(snap_ventana.get('tasa_regimen_kg_dia'))} kg/d"],
        [tr("ventana.status"), _fmt(snap_ventana.get("status"))],
    ]
    if (snap_ventana.get("lena_consumida_kg") or 0.0) > 0:
        rows.append([tr("ventana.lena"), f"{_fmt(snap_ventana.get('lena_consumida_kg'))} kg"])
    elems.append(_tabla_kv(rows))

    subtipo = snap_ventana.get("subtipo")
    if subtipo == "BATCH":
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("ventana.batch_titulo"), styles["h2"]))
        t_med = snap_ventana.get("t_secado_medio_s")
        rows_b = [
            [tr("ventana.batch_lotes"), _fmt(snap_ventana.get("n_batches_completos"))],
            [
                tr("ventana.batch_t_medio"),
                f"{t_med / 3600.0:.1f} h" if t_med is not None else "—",
            ],
            [
                tr("ventana.batch_en_progreso"),
                _fmt(snap_ventana.get("batch_en_progreso"), tr=tr),
            ],
        ]
        elems.append(_tabla_kv(rows_b))
    elif subtipo == "SEMICONTINUO":
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("ventana.tunel_titulo"), styles["h2"]))
        cadencia_s = snap_ventana.get("intervalo_avance_s")
        rows_s = [
            [tr("ventana.tunel_avances"), _fmt(snap_ventana.get("n_avances"))],
            [tr("ventana.tunel_x_salida"), _fmt(snap_ventana.get("X_salida_regimen"))],
            [
                tr("ventana.tunel_throughput"),
                f"{_fmt(snap_ventana.get('throughput_fresco_kg_dia'))} kg/d",
            ],
            [
                tr("ventana.tunel_cadencia"),
                f"{cadencia_s / 3600.0:.1f} h" if cadencia_s is not None else "—",
            ],
        ]
        elems.append(_tabla_kv(rows_s))
        # Perfil por zona (tabla compacta entrada → salida).
        perfil_X = snap_ventana.get("perfil_X_zonas")
        if perfil_X:
            perfil_T = snap_ventana.get("perfil_T_aire_zonas_K") or []
            filas_zona = [[tr("ventana.zona"), tr("ventana.zona_x"), tr("ventana.zona_t_aire")]]
            for i, x_z in enumerate(perfil_X):
                t_c = f"{perfil_T[i] - 273.15:.1f}" if len(perfil_T) > i else "—"
                filas_zona.append([str(i + 1), f"{x_z:.3f}", t_c])
            elems.append(Spacer(1, 4))
            elems.append(
                Table(
                    filas_zona,
                    colWidths=[2.5 * cm, 5.0 * cm, 5.0 * cm],
                    style=TableStyle(
                        [
                            ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 8.5),
                            ("FONT", (0, 0), (-1, 0), _FONT_BOLD, 8.5),
                            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f0f0f0")),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.25, _COLOR_LINEA),
                        ]
                    ),
                    hAlign="LEFT",
                )
            )

    # Caño maestro: diagnóstico térmico/hidráulico sobre el lapso.
    if snap_ventana.get("cano_delta_P_Pa") is not None:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("ventana.cano_titulo"), styles["h2"]))
        elems.append(
            _tabla_kv(
                [
                    [
                        tr("ventana.cano_dt_media"),
                        f"{snap_ventana.get('cano_delta_T_media_K'):+.2f} K",
                    ],
                    [
                        tr("ventana.cano_dt_minima"),
                        f"{snap_ventana.get('cano_delta_T_minima_K'):+.2f} K",
                    ],
                    [tr("ventana.cano_dp"), f"{_fmt(snap_ventana.get('cano_delta_P_Pa'))} Pa"],
                ]
            )
        )

    # Avisos de runtime (ES, artefactos de calculos/ — mismo criterio que
    # chimenea.avisos_solver).
    advs = snap_ventana.get("advertencias") or []
    if advs:
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(tr("ventana.avisos"), styles["h2"]))
        for a in advs:
            elems.append(Paragraph(f"⚠ {a}", styles["pendiente"]))  # i18n: exento

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        tr("ventana.graficas"),
        figuras,
        msg_pendiente=tr("global.graficas_pendiente"),
    )
    return elems


def _seccion_operacion_anual(
    styles, tr: Tr, snap_anual: dict, figuras: list[tuple[str, bytes]]
) -> list:
    """Sección de operación anual de cámara (eficiencias Augustus Leon).

    Consume el snapshot ``operacion_anual`` de ``_json_operacion_anual``.
    """
    elems: list = [Paragraph(tr("anual.titulo"), styles["h1"])]
    if not snap_anual:
        return elems + _seccion_pendiente(styles, tr("anual.pendiente"))

    rows = [
        [tr("anual.kg_anual"), f"{_fmt(snap_anual.get('kg_secados_anual'))} kg"],
        [tr("anual.t_promedio"), f"{_fmt(snap_anual.get('t_secado_promedio_h'))} h"],
        [tr("anual.e_solar"), f"{_fmt(snap_anual.get('E_solar_anual_MJ'))} MJ"],
        [tr("anual.e_aux"), f"{_fmt(snap_anual.get('E_auxiliar_anual_MJ'))} MJ"],
        [tr("anual.eta_drying"), _fmt(snap_anual.get("eta_drying_anual_media"))],
        [tr("anual.eta_pickup"), _fmt(snap_anual.get("eta_pickup_anual_media"))],
        [tr("anual.eta_termica"), _fmt(snap_anual.get("eta_termica_anual_media"))],
        [tr("anual.eta_total"), _fmt(snap_anual.get("eta_total_anual_media"))],
    ]
    elems.append(_tabla_kv(rows))

    puntos = snap_anual.get("puntos_mensuales") or []
    if puntos:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(tr("anual.tabla_titulo"), styles["h2"]))
        filas = [
            [
                tr("anual.col_mes"),
                tr("anual.col_t"),
                tr("anual.col_conv"),
                tr("anual.col_kg_batch"),
                tr("anual.col_batches"),
                tr("anual.col_kg_mes"),
                tr("anual.col_eta_total"),
            ]
        ]
        for p in puntos:
            filas.append(
                [
                    str(p.get("mes", "—")),
                    f"{p.get('t_secado_h', 0.0):.1f}",
                    "✓" if p.get("convergio") else "—",
                    f"{p.get('m_evap_kg_por_batch', 0.0):.2f}",
                    str(p.get("n_batches", "—")),
                    f"{p.get('kg_secados_mes', 0.0):.1f}",
                    f"{p.get('eta_total', 0.0) * 100:.2f} %",
                ]
            )
        elems.append(
            Table(
                filas,
                colWidths=[1.5 * cm, 2.2 * cm, 1.8 * cm, 2.6 * cm, 2.2 * cm, 2.4 * cm, 2.4 * cm],
                style=TableStyle(
                    [
                        ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 8.5),
                        ("FONT", (0, 0), (-1, 0), _FONT_BOLD, 8.5),
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f0f0f0")),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.25, _COLOR_LINEA),
                    ]
                ),
                hAlign="LEFT",
            )
        )

    advs = snap_anual.get("advertencias") or []
    for a in advs:
        elems.append(Paragraph(f"⚠ {a}", styles["pendiente"]))  # i18n: exento

    elems.append(Spacer(1, 6))
    elems += _seccion_figuras(
        styles,
        tr("anual.graficas"),
        figuras,
        msg_pendiente=tr("global.graficas_pendiente"),
    )
    return elems


def _datos_validacion(session_state) -> dict:
    """Normaliza los resultados de validación/calibración persistidos en la sesión.

    Devuelve un dict con hasta tres bloques (``colector``/``camara``/``tunel``),
    listo para que ``_seccion_validacion`` y ``_figuras_validacion`` lo consuman.
    Vacío si el usuario no validó nada — la sección entera se omite del PDF.
    Todo va en unidad de display (°C, kg/kg seco, etc.).
    """
    out: dict = {}

    # --- Colector (P3): las métricas se recomputan desde la señal persistida
    # (mismo camino puro que el render de P3). La señal puede referir a un
    # proyecto ya mutado → try/except amplio.
    val3 = session_state.get("p3_val_resultado")
    cal3 = session_state.get("p3_cal_resultado")
    if val3 or cal3:
        bloque: dict = {"cal": cal3}
        try:
            if val3 is not None and val3.get("t_sim") is not None:
                from calculos.ingesta_referencia import evaluar_ajuste

                bloque["forzado_medido"] = bool(val3.get("forzado_medido"))
                metricas, y_med_K, y_sim_K, ts = evaluar_ajuste(
                    val3["senal"], val3["t_sim"], val3["y_sim_K"]
                )
                if metricas is not None:
                    bloque.update(
                        {
                            "metricas": metricas,
                            "unidad": "°C",
                            "ts": list(ts),
                            "y_med": [float(v) - 273.15 for v in y_med_K],
                            "y_sim": [float(v) - 273.15 for v in y_sim_K],
                        }
                    )
        except Exception:
            pass
        out["colector"] = bloque

    # --- Cámara (P4): el resultado ya trae métricas y series en SI.
    val4 = session_state.get("p4_val_resultado")
    cal4 = session_state.get("p4_cal_resultado")
    if val4 or cal4:
        bloque = {"cal": cal4}
        try:
            if val4 is not None and val4.get("metricas") is not None:
                import numpy as _np

                from calculos.validacion_camara import a_display, unidad_display

                var = val4["variable"]
                bloque.update(
                    {
                        "variable": var,
                        "unidad": unidad_display(var),
                        "metricas": val4["metricas"],
                        "ts": list(val4["ts"]),
                        "y_med": [float(v) for v in a_display(_np.asarray(val4["y_med"]), var)],
                        "y_sim": [float(v) for v in a_display(_np.asarray(val4["y_sim"]), var)],
                    }
                )
        except Exception:
            pass
        out["camara"] = bloque

    # --- Túnel (P7): snapshots ya en display (descargas + perfil por zona).
    valtun = session_state.get("p7_valtun_resultado")
    if valtun:
        out["tunel"] = valtun
    return out


def _figuras_validacion(datos: dict, tr: Tr) -> dict[str, list[tuple[str, bytes]]]:
    """Figuras (PNG) de la sección de validación, por bloque."""
    out: dict[str, list[tuple[str, bytes]]] = {"colector": [], "camara": [], "tunel": []}
    if not datos:
        return out
    from ui.componentes.validacion_widget import (
        fig_curva_calibracion,
        fig_overlay,
        fig_perfil_zonas,
    )

    med_lbl = tr("validacion.medido")
    sim_lbl = tr("validacion.simulado")

    def _overlay_png(bloque: dict, y_lbl: str, titulo: str) -> bytes | None:
        try:
            return _fig_a_png(
                fig_overlay(
                    bloque["ts"],
                    bloque["y_med"],
                    bloque["y_sim"],
                    medido_lbl=med_lbl,
                    simulado_lbl=sim_lbl,
                    titulo=titulo,
                    y_lbl=y_lbl,
                )
            )
        except Exception:
            return None

    def _curva_png(cal) -> bytes | None:
        try:
            return _fig_a_png(
                fig_curva_calibracion(
                    cal,
                    x_lbl=str(cal.parametro),
                    y_lbl=str(cal.objetivo_nombre),
                    titulo=tr("validacion.fig.curva"),
                    optimo_lbl=tr("validacion.cal_optimo"),
                )
            )
        except Exception:
            return None

    for clave, titulo_key in (("colector", "validacion.fig.overlay_colector"),):
        bloque = datos.get(clave) or {}
        if bloque.get("metricas") is not None:
            png = _overlay_png(bloque, f"T [{bloque.get('unidad', '°C')}]", tr(titulo_key))
            if png:
                out[clave].append((tr(titulo_key), png))
        if bloque.get("cal") is not None:
            png = _curva_png(bloque["cal"])
            if png:
                out[clave].append((tr("validacion.fig.curva"), png))

    bloque = datos.get("camara") or {}
    if bloque.get("metricas") is not None:
        y_lbl = f"{bloque.get('variable', '')} [{bloque.get('unidad', '')}]"
        png = _overlay_png(bloque, y_lbl, tr("validacion.fig.overlay_camara"))
        if png:
            out["camara"].append((tr("validacion.fig.overlay_camara"), png))
    if bloque.get("cal") is not None:
        png = _curva_png(bloque["cal"])
        if png:
            out["camara"].append((tr("validacion.fig.curva"), png))

    tunel = datos.get("tunel") or {}
    desc = tunel.get("descargas")
    if desc is not None:
        try:
            png = _fig_a_png(
                fig_overlay(
                    desc["ts"],
                    desc["y_med_disp"],
                    desc["y_sim_disp"],
                    medido_lbl=med_lbl,
                    simulado_lbl=sim_lbl,
                    titulo=tr("validacion.fig.descargas"),
                    y_lbl="X [kg/kg]",
                )
            )
            if png:
                out["tunel"].append((tr("validacion.fig.descargas"), png))
        except Exception:
            pass
    perfil = tunel.get("perfil")
    if perfil is not None:
        try:
            n = len(perfil["y_sim_disp"])
            png = _fig_a_png(
                fig_perfil_zonas(
                    list(range(1, n + 1)),
                    perfil.get("y_med_disp"),
                    perfil["y_sim_disp"],
                    medido_lbl=med_lbl,
                    simulado_lbl=sim_lbl,
                    titulo=tr("validacion.fig.perfil"),
                    x_lbl=tr("validacion.zona"),
                    y_lbl=str(perfil.get("magnitud", "")),
                )
            )
            if png:
                out["tunel"].append((tr("validacion.fig.perfil"), png))
        except Exception:
            pass
    return out


def _seccion_validacion(
    styles, tr: Tr, datos: dict, figuras: dict[str, list[tuple[str, bytes]]]
) -> list:
    """Sección "Validación con datos medidos": métricas + calibración por bloque.

    Solo se llama si ``datos`` no está vacío (la sección se omite sin nota de
    pendiente cuando el usuario no validó nada).
    """
    idioma = getattr(tr, "idioma", IDIOMA_DEFAULT)
    elems: list = [Paragraph(tr("validacion.titulo"), styles["h1"])]
    elems.append(Paragraph(tr("validacion.intro"), styles["pendiente"]))
    elems.append(Spacer(1, 6))

    def _tabla_metricas(metricas, unidad: str):
        from ui.componentes.validacion_widget import filas_metricas

        rows = []
        for mid, val, uni in filas_metricas(metricas, unidad):
            label = traducir(f"p4.validacion.metrica.{mid}", idioma, default=mid.upper())
            rows.append([label, f"{val:.3g}" + (f" {uni}" if uni else "")])
        rows.append([tr("validacion.n_pares"), str(int(metricas.n_pares))])
        return _tabla_kv(rows)

    def _bloque_calibracion(cal) -> list:
        m = cal.metricas_optimo
        sub: list = [Spacer(1, 4), Paragraph(tr("validacion.cal_titulo"), styles["h2"])]
        rows = [
            [tr("validacion.cal_parametro"), str(cal.parametro)],
            [tr("validacion.cal_objetivo"), str(cal.objetivo_nombre)],
            [tr("validacion.cal_optimo"), _fmt(cal.valor_optimo)],
        ]
        if m is not None:
            rows.append(
                [
                    tr("validacion.cal_metricas"),
                    f"RMSE {m.rmse:.3g} | MBE {m.mbe:+.3g} | R² {m.r2:.3f}",
                ]
            )
        sub.append(_tabla_kv(rows))
        # Factores de cámara: diagnóstico, no parámetro de diseño. Misma
        # lectura física que la UI de P4 (namespace p4.calibracion.*).
        if str(cal.parametro).startswith("factor_") and cal.valor_optimo is not None:
            if cal.valor_optimo > 1.05:
                lectura = traducir("p4.calibracion.lectura_alto", idioma)
            elif cal.valor_optimo < 0.95:
                lectura = traducir("p4.calibracion.lectura_bajo", idioma)
            else:
                lectura = traducir("p4.calibracion.lectura_neutro", idioma)
            sub.append(Paragraph(lectura, styles["pendiente"]))
            sub.append(Paragraph(tr("validacion.cal_nota_diagnostico"), styles["pendiente"]))
        return sub

    def _figs(clave: str) -> list:
        sub: list = []
        for titulo_fig, png in figuras.get(clave, []) or []:
            sub.append(Spacer(1, 4))
            sub.append(Paragraph(titulo_fig, styles["p_celda"]))
            sub.append(Image(io.BytesIO(png), width=15.5 * cm, height=15.5 * cm * 0.55))
        return sub

    # --- Colector ---
    bloque = datos.get("colector")
    if bloque:
        elems.append(Paragraph(tr("validacion.colector_titulo"), styles["h2"]))
        if "forzado_medido" in bloque:
            forzado = (
                tr("validacion.forzado_medido")
                if bloque["forzado_medido"]
                else tr("validacion.forzado_p2")
            )
            elems.append(Paragraph(forzado, styles["pendiente"]))
        if bloque.get("metricas") is not None:
            elems.append(_tabla_metricas(bloque["metricas"], bloque.get("unidad", "°C")))
        elems += _figs("colector")
        if bloque.get("cal") is not None:
            elems += _bloque_calibracion(bloque["cal"])
        elems.append(Spacer(1, 8))

    # --- Cámara ---
    bloque = datos.get("camara")
    if bloque:
        elems.append(Paragraph(tr("validacion.camara_titulo"), styles["h2"]))
        var = bloque.get("variable")
        if var:
            var_lbl = traducir(f"p4.validacion.variable.{var}", idioma, default=var)
            elems.append(
                _tabla_kv([[tr("validacion.variable"), f"{var_lbl} [{bloque.get('unidad', '')}]"]])
            )
        if bloque.get("metricas") is not None:
            elems.append(_tabla_metricas(bloque["metricas"], bloque.get("unidad", "")))
        elems += _figs("camara")
        if bloque.get("cal") is not None:
            elems += _bloque_calibracion(bloque["cal"])
        elems.append(Spacer(1, 8))

    # --- Túnel (semicontinuo) ---
    tunel = datos.get("tunel")
    if tunel:
        elems.append(Paragraph(tr("validacion.tunel_titulo"), styles["h2"]))
        desc = tunel.get("descargas")
        if desc is not None and desc.get("metricas") is not None:
            elems.append(Paragraph(tr("validacion.descargas_titulo"), styles["p_celda"]))
            from calculos.validacion_camara import unidad_display as _ud

            elems.append(_tabla_metricas(desc["metricas"], _ud(desc.get("variable", "X_producto"))))
        perfil = tunel.get("perfil")
        if perfil is not None and perfil.get("metricas") is not None:
            elems.append(Spacer(1, 4))
            elems.append(Paragraph(tr("validacion.perfil_titulo"), styles["p_celda"]))
            from calculos.validacion_camara import unidad_display as _ud

            elems.append(_tabla_metricas(perfil["metricas"], _ud(perfil.get("magnitud", ""))))
        elems += _figs("tunel")
    return elems


def _bloque_advertencias(styles, tr: Tr, advs: list[dict] | None) -> list:
    if not advs:
        return []
    idioma = getattr(tr, "idioma", IDIOMA_DEFAULT)
    elems: list = [Spacer(1, 4), Paragraph(tr("adv.titulo"), styles["h2"])]
    # Header crudo + filas con Paragraph para que el texto haga line-wrap
    # cuando el código o el mensaje exceden el ancho de columna.
    rows = [[tr("adv.sev"), tr("adv.codigo"), tr("adv.mensaje")]]
    for a in advs:
        # Mensaje retraducido por código (F5): mismo fallback al ES de core.
        mensaje = traducir(
            f"advertencias.{a.get('codigo', '')}.mensaje",
            idioma,
            default=a.get("mensaje", ""),
            **(a.get("contexto") or {}),
        )
        rows.append(
            [
                Paragraph(a.get("severidad", ""), styles["p_celda"]),
                Paragraph(a.get("codigo", ""), styles["p_celda"]),
                Paragraph(mensaje, styles["p_celda"]),
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
    T_amb_C: float | None = None,
    I_g: float | None = None,
    v_viento: float | None = None,
    HR_cam_pct: float | None = None,
    idioma: str = IDIOMA_DEFAULT,
) -> bytes:
    """Genera el reporte PDF completo del prediseño.

    Args:
        proyecto: Objeto Proyecto raíz.
        session_state: ``st.session_state`` con los resultados cacheados.
        res: ResultadosCompletos del balance global (P7).
        T_amb_C, I_g, v_viento, HR_cam_pct: condiciones de operación P7.
        idioma: Código de idioma del reporte (``es``/``en``/``pt``). Los
            títulos, rótulos y mensajes se traducen vía el namespace
            ``reporte.*``; los valores numéricos y unidades quedan en v1.

    Returns:
        Bytes del PDF generado.
    """
    tr = _hacer_tr(idioma)
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

    # Dispatch por tipo de resultado: en modo Ventana (gran escala) la sección
    # global se reemplaza por la de producción; la operación anual (si P4 la
    # corrió) se agrega en cualquier modo.
    from calculos.simulacion_ventana import ResultadoVentana

    es_ventana = isinstance(res, ResultadoVentana)
    res_anual = session_state.get("p4_resultado_anual")

    # Snapshot completo (para sección global)
    snap_full = _json_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
        res_anual=res_anual,
    )

    # Recolección de figuras (esto puede tardar varios segundos)
    figs_p2 = _figuras_p2(proyecto, tr)
    figs_p3 = _figuras_p3(session_state, tr)
    figs_p4 = _figuras_p4(proyecto, session_state, tr)
    figs_p7 = [] if es_ventana else _figuras_p7(res, tr, proyecto, HR_cam_pct=HR_cam_pct)
    figs_ventana = _figuras_ventana(res, tr, proyecto) if es_ventana else []
    figs_anual = _figuras_anual(res_anual, tr) if res_anual is not None else []

    # Validación/calibración con datos medidos (colector/cámara/túnel): la
    # sección entra automáticamente si el usuario validó algo en la sesión.
    datos_val = _datos_validacion(session_state)
    figs_val = _figuras_validacion(datos_val, tr) if datos_val else {}

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
    doc = _crear_doc(buf, logos, nombre_proyecto, tr)
    styles = _styles()
    story: list = []

    # 1. Portada con P1/P2/clima
    story += _portada(
        styles,
        tr,
        snap_meta=meta_dict.get("meta") or {},
        snap_cfg=meta_dict.get("configuracion") or {},
        snap_empl=meta_dict.get("emplazamiento") or {},
        snap_clima=meta_dict.get("clima") or {},
    )

    # 2. Gráficas climáticas
    story.append(PageBreak())
    story.append(Paragraph(tr("p2.titulo"), styles["h1"]))
    story += _seccion_figuras(
        styles,
        "",
        figs_p2,
        msg_pendiente=tr("p2.pendiente"),
    )

    # 3. Colector
    story.append(PageBreak())
    story += _seccion_colector(styles, tr, snap_col, figs_p3)

    # 4. Cámara
    story.append(PageBreak())
    story += _seccion_camara(styles, tr, snap_cam, figs_p4)

    # 5. Auxiliar
    story.append(PageBreak())
    story += _seccion_auxiliar(styles, tr, snap_aux)

    # 6. Motor
    story += [Spacer(1, 12)]
    story += _seccion_motor(styles, tr, snap_mot)

    # 6.b Chimenea solar (sólo si está configurada — convección natural o
    # accesorio paralelo al motor en armarios con ambos definidos).
    if snap_chim is not None:
        story.append(PageBreak())
        story += _seccion_chimenea(styles, tr, snap_chim, res_chim)

    # 7. Resultados globales (incluye gráfica balance) — o producción en
    # ventana cuando el resultado es un ResultadoVentana (gran escala).
    story.append(PageBreak())
    if es_ventana:
        story += _seccion_ventana(
            styles,
            tr,
            snap_ventana=snap_full.get("resultado_ventana") or {},
            figuras=figs_ventana,
        )
    else:
        story += _seccion_resultados_globales(
            styles,
            tr,
            snap_global=snap_full.get("resultados_globales") or {},
            condiciones=snap_full.get("condiciones_operacion_P7") or {},
            figuras=figs_p7,
        )

    # 8. Operación anual de cámara (si P4 la corrió — convive con cualquier modo)
    if res_anual is not None:
        story.append(PageBreak())
        story += _seccion_operacion_anual(
            styles,
            tr,
            snap_anual=snap_full.get("operacion_anual") or {},
            figuras=figs_anual,
        )

    # 9. Validación con datos medidos (solo si el usuario validó/calibró algo)
    if datos_val:
        story.append(PageBreak())
        story += _seccion_validacion(styles, tr, datos_val, figs_val)

    doc.build(story)
    return buf.getvalue()
