"""Infografía panorámica (16:9) de Secasol para difusión institucional.

Genera un PDF vectorial de una sola lámina, pensado para portal web / prensa
(UNSa - INENCO). Todo el contenido (incluido el gráfico de escala) es vectorial,
salvo los logos institucionales.

Uso:
    .venv/bin/python docs/difusion/infografia_secasol.py
Salida:
    docs/difusion/infografia_secasol.pdf
"""

from __future__ import annotations

import math
import os

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------- geometría ---
W, H = 1280, 720  # lámina panorámica 16:9 (puntos PDF)

# ---------------------------------------------------------------- paleta -------
AZUL = HexColor("#0B3D66")       # azul profundo institucional
AZUL2 = HexColor("#155B8A")
NARANJA = HexColor("#E8821E")    # sol / energía
AMBAR = HexColor("#F4B23E")
VERDE = HexColor("#2E9E5B")      # agro
CREMA = HexColor("#FFF8EF")
CREMA2 = HexColor("#FDEFD9")
GRIS = HexColor("#5A6470")
GRIS_CLARO = HexColor("#9AA4AE")
BLANCO = HexColor("#FFFFFF")
TINTA = HexColor("#1E2A36")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "infografia_secasol.pdf")


def _hx(color: Color, alpha: float) -> Color:
    """Devuelve el color con transparencia (para fondos suaves)."""
    return Color(color.red, color.green, color.blue, alpha=alpha)


def draw(c: canvas.Canvas) -> None:
    # ---- fondo general --------------------------------------------------
    c.setFillColor(CREMA)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # banda lateral de acento (columna derecha sutil)
    c.setFillColor(_hx(AMBAR, 0.10))
    c.rect(600, 0, W - 600, H - 132, stroke=0, fill=1)

    # ================================================================= HEADER
    hy = H - 132
    c.setFillColor(BLANCO)
    c.rect(0, hy, W, 132, stroke=0, fill=1)
    # franja de acento inferior del header
    c.setFillColor(NARANJA)
    c.rect(0, hy - 5, W, 5, stroke=0, fill=1)

    # Título
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 60)
    c.drawString(55, hy + 56, "SECASOL")
    c.setFillColor(NARANJA)
    c.setFont("Helvetica-Bold", 60)
    tw = c.stringWidth("SECASOL", "Helvetica-Bold", 60)
    c.drawString(55 + tw + 14, hy + 56, "·")
    # subtítulo
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 21)
    c.drawString(58, hy + 26, "Prediseñador libre de secadores solares")
    c.setFillColor(GRIS_CLARO)
    c.setFont("Helvetica-Oblique", 14.5)
    c.drawString(58, hy + 7, "INENCO · CONICET · Universidad Nacional de Salta")

    # Logos a la derecha del header
    logos = [
        ("logo_inenco_transparente.png", 1.60),
        ("logo_grupo_transparente.png", 1.78),
    ]
    lh = 74
    x_right = W - 55
    for fname, ar in reversed(logos):
        path = os.path.join(ASSETS, fname)
        if os.path.exists(path):
            lw = lh * ar
            x_right -= lw
            c.drawImage(
                ImageReader(path), x_right, hy + (132 - lh) / 2,
                width=lw, height=lh, mask="auto", preserveAspectRatio=True,
            )
            x_right -= 26

    # =========================================================== COLUMNA IZQ
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(55, hy - 46, "¿Qué hace distinto a Secasol?")

    bullets = [
        (NARANJA, "Escala flexible",
         "Diseña desde pocos kilos (caja doméstica/educativa)",
         "hasta toneladas (secadores industriales semicontinuos)."),
        (VERDE, "Código libre y abierto",
         "Licencia GNU GPLv3: auditable, reproducible y sin costo.",
         "Pensado para enseñanza, investigación y transferencia."),
        (AZUL2, "Disponible 24 horas en la web",
         "Corre en el navegador (Hugging Face Spaces).",
         "Sin instalar nada, desde cualquier dispositivo."),
        (AMBAR, "Modular y guiado",
         "Flujo de 7 etapas: del emplazamiento al reporte final,",
         "con clima real (NASA POWER) y física en cada paso."),
        (VERDE, "Para docentes, profesionales y productores",
         "Orientado a usuarios con capacitación en secado solar:",
         "academia, técnicos y productores agrícolas."),
    ]

    top = hy - 78
    bottom = 70
    n = len(bullets)
    gap = 12
    ch = (top - bottom - gap * (n - 1)) / n  # alto de cada tarjeta
    y = top
    for color, titulo, l1, l2 in bullets:
        y0 = y - ch
        # tarjeta
        c.setFillColor(BLANCO)
        c.roundRect(50, y0, 525, ch, 9, stroke=0, fill=1)
        # barra de color a la izquierda
        c.setFillColor(color)
        c.roundRect(50, y0, 9, ch, 4, stroke=0, fill=1)
        c.rect(54, y0, 5, ch, stroke=0, fill=1)
        # badge circular
        cx, cy = 92, y0 + ch / 2
        c.setFillColor(_hx(color, 0.16))
        c.circle(cx, cy, 19, stroke=0, fill=1)
        c.setFillColor(color)
        c.circle(cx, cy, 7.5, stroke=0, fill=1)
        # texto
        c.setFillColor(TINTA)
        c.setFont("Helvetica-Bold", 16.5)
        c.drawString(126, y0 + ch - 25, titulo)
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 12.5)
        c.drawString(126, y0 + ch - 44, l1)
        c.drawString(126, y0 + ch - 60, l2)
        y = y0 - gap

    # =========================================================== COLUMNA DER
    rx = 628  # margen izquierdo de la columna derecha

    # ---- Gráfico de escala (eje log, vectorial) ------------------------
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(rx, hy - 44, "Una sola herramienta, todas las escalas")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 13)
    c.drawString(rx, hy - 64, "Capacidad de carga de producto fresco (escala logarítmica)")

    gx0, gx1 = rx + 12, W - 60          # extensión del eje x
    vmin, vmax = 1.0, 10000.0
    lo, hi = math.log10(vmin), math.log10(vmax)

    def xs(v: float) -> float:
        return gx0 + (math.log10(v) - lo) / (hi - lo) * (gx1 - gx0)

    base_y = hy - 220                    # línea base del eje
    # grilla + etiquetas de ticks
    ticks = [(1, "1"), (10, "10"), (100, "100"), (1000, "1.000"), (10000, "10.000")]
    c.setFont("Helvetica", 11)
    for v, lab in ticks:
        x = xs(v)
        c.setStrokeColor(_hx(GRIS_CLARO, 0.55))
        c.setLineWidth(1)
        c.line(x, base_y, x, base_y + 132)
        c.setFillColor(GRIS)
        c.drawCentredString(x, base_y - 16, lab)
    c.setFillColor(GRIS_CLARO)
    c.setFont("Helvetica-Oblique", 11)
    c.drawRightString(gx1, base_y - 32, "kg de producto")

    # barras de rango por tipología (de arriba hacia abajo)
    barras = [
        ("CAJA", "Doméstico / educativo", 1, 25, NARANJA),
        ("ARMARIO", "Profesional / pyme", 20, 300, AMBAR),
        ("GRAN ESCALA", "Industrial · batch y semicontinuo", 200, 6000, VERDE),
    ]
    bh = 26
    by = base_y + 120
    for nombre, sub, a, b, color in barras:
        x_a, x_b = xs(a), xs(b)
        c.setFillColor(color)
        c.roundRect(x_a, by - bh, x_b - x_a, bh, 7, stroke=0, fill=1)
        # etiqueta de tipología sobre la barra
        c.setFillColor(TINTA)
        c.setFont("Helvetica-Bold", 12.5)
        c.drawString(x_a + 4, by + 4, nombre)
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 10.5)
        c.drawString(x_a + 4 + c.stringWidth(nombre, "Helvetica-Bold", 12.5) + 8, by + 4, sub)
        by -= bh + 22

    # ---- Pipeline modular de 7 pasos -----------------------------------
    py = base_y - 78
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 19)
    c.drawString(rx, py + 34, "Flujo modular en 7 pasos")

    pasos = [
        ("1", "Tipología"), ("2", "Emplaza-\nmiento"), ("3", "Colector"),
        ("4", "Cámara"), ("5", "Auxiliar"), ("6", "Motor/\nChimenea"),
        ("7", "Resultados"),
    ]
    pw, ph = 78, 50
    pgap = (W - 60 - rx - pw * len(pasos)) / (len(pasos) - 1)
    px = rx
    for i, (num, lab) in enumerate(pasos):
        cfill = AZUL if i < 6 else VERDE
        c.setFillColor(cfill)
        c.roundRect(px, py - ph, pw, ph, 8, stroke=0, fill=1)
        c.setFillColor(AMBAR if i < 6 else BLANCO)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(px + 8, py - 20, num)
        c.setFillColor(BLANCO)
        c.setFont("Helvetica-Bold", 9.3)
        lines = lab.split("\n")
        ly = py - 20 - (0 if len(lines) == 1 else 0)
        for j, ln in enumerate(lines):
            c.drawCentredString(px + pw / 2 + 6, py - 20 - j * 11, ln)
        # flecha conectora
        if i < len(pasos) - 1:
            ax = px + pw + pgap / 2
            c.setStrokeColor(GRIS_CLARO)
            c.setLineWidth(2)
            c.line(px + pw + 3, py - ph / 2, px + pw + pgap - 3, py - ph / 2)
            c.setFillColor(GRIS_CLARO)
            p = c.beginPath()
            p.moveTo(px + pw + pgap - 3, py - ph / 2)
            p.lineTo(px + pw + pgap - 10, py - ph / 2 + 4)
            p.lineTo(px + pw + pgap - 10, py - ph / 2 - 4)
            p.close()
            c.drawPath(p, stroke=0, fill=1)
        px += pw + pgap

    # ---- Panel destacado (acceso + tecnología) -------------------------
    panel_y = 70
    panel_h = py - ph - 24 - panel_y
    c.setFillColor(AZUL)
    c.roundRect(rx, panel_y, W - 60 - rx, panel_h, 12, stroke=0, fill=1)
    c.setFillColor(AMBAR)
    c.roundRect(rx, panel_y, 9, panel_h, 5, stroke=0, fill=1)
    c.rect(rx + 4, panel_y, 5, panel_h, stroke=0, fill=1)

    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(rx + 30, panel_y + panel_h - 32, "Probalo online, sin instalar nada")
    c.setFillColor(AMBAR)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(rx + 30, panel_y + panel_h - 58,
                 "huggingface.co/spaces/gonzalojduran/Secasol26")

    c.setFillColor(_hx(BLANCO, 0.92))
    c.setFont("Helvetica", 12.5)
    chips = [
        "Clima real NASA POWER",
        "Física: balance calor-masa",
        "Reporte PDF del diseño",
        "Convección natural o forzada",
    ]
    cyp = panel_y + panel_h - 88
    cxp = rx + 30
    for i, ch_ in enumerate(chips):
        if i == 2:
            cyp -= 24
            cxp = rx + 30
        tw_ = c.stringWidth(ch_, "Helvetica", 12.5)
        c.setFillColor(_hx(BLANCO, 0.14))
        c.roundRect(cxp - 8, cyp - 6, tw_ + 30, 22, 11, stroke=0, fill=1)
        c.setFillColor(AMBAR)
        c.circle(cxp + 4, cyp + 5, 3.5, stroke=0, fill=1)
        c.setFillColor(BLANCO)
        c.drawString(cxp + 16, cyp, ch_)
        cxp += tw_ + 44

    # ================================================================= FOOTER
    c.setFillColor(AZUL)
    c.rect(0, 0, W, 44, stroke=0, fill=1)
    c.setFillColor(BLANCO)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(55, 16, "Secasol")
    c.setFillColor(_hx(BLANCO, 0.85))
    c.setFont("Helvetica", 12.5)
    c.drawString(118, 16, "·  Software libre (GNU GPLv3) para el prediseño de secadores solares")
    c.setFillColor(AMBAR)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawRightString(W - 55, 16, "INENCO · CONICET · UNSa")


def main() -> None:
    c = canvas.Canvas(OUT, pagesize=(W, H))
    c.setTitle("Secasol — Prediseñador libre de secadores solares")
    c.setAuthor("INENCO · CONICET · UNSa")
    draw(c)
    c.showPage()
    c.save()
    print("OK ->", OUT)


if __name__ == "__main__":
    main()
