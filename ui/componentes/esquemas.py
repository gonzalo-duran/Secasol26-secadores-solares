"""Helper para renderizar esquemas SVG en Streamlit.

Los archivos SVG viven en ``assets/esquemas/`` (raíz del repo). Se leen una
sola vez vía ``functools.lru_cache`` y se inyectan dentro de un iframe vía
``streamlit.components.v1.html``. El iframe aísla el SVG del CSS de
Streamlit, evitando que el tema oscuro repinte los textos del diagrama
(``fill="#333"``) con los colores del tema.

Ubicación en el repo: ui/componentes/esquemas.py

Uso en las pestañas::

    from ui.componentes.esquemas import mostrar_esquema

    mostrar_esquema("camara_dimensiones")
    mostrar_esquema("colector_tipo1", max_ancho_px=500)

Esquemas disponibles (cada uno corresponde a un archivo
``assets/esquemas/<nombre>.svg``):

- ``camara_dimensiones``: vista isométrica de la cámara con cotas.
- ``colector_tipo1``: vista isométrica del colector tipo 1.
- ``colectores_seccion_transversal``: sección transversal comparativa de
  los 4 tipos de colector.
- ``circuito_caja``: circuito de aire del secador tipo CAJA.
- ``circuito_armario``: circuito de aire del secador tipo ARMARIO.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_ESQUEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "esquemas"

_VIEWBOX_RE = re.compile(r'viewBox="\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*"')


@lru_cache(maxsize=32)
def _leer_svg(nombre: str) -> str:
    """Lee el contenido SVG del archivo y lo cachea en memoria.

    Args:
        nombre: Nombre del archivo sin extensión.

    Returns:
        Contenido del SVG como string, o cadena vacía si el archivo no existe.
    """
    ruta = _ESQUEMAS_DIR / f"{nombre}.svg"
    if not ruta.is_file():
        return ""
    return ruta.read_text(encoding="utf-8")


def _aspecto_svg(svg: str) -> float:
    """Devuelve el ratio alto/ancho del viewBox del SVG.

    Si no encuentra viewBox, asume 1:1 (cuadrado).
    """
    m = _VIEWBOX_RE.search(svg)
    if not m:
        return 1.0
    _, _, w, h = map(float, m.groups())
    if w <= 0:
        return 1.0
    return h / w


def mostrar_esquema(
    nombre: str,
    max_ancho_px: int = 680,
    caption: str | None = None,
) -> None:
    """Renderiza un esquema SVG en la UI de Streamlit dentro de un iframe.

    El iframe garantiza que el SVG se vea idéntico independientemente del
    tema (claro/oscuro) configurado en Streamlit. El alto del iframe se
    calcula a partir del aspecto del viewBox del SVG y el ancho deseado.

    Args:
        nombre: Nombre del archivo sin extensión (ej. ``"camara_dimensiones"``).
        max_ancho_px: Ancho máximo del esquema en píxeles.
        caption: Texto opcional debajo del esquema.
    """
    svg = _leer_svg(nombre)
    if not svg:
        st.caption(f"[esquema '{nombre}' no encontrado]")
        return

    aspecto = _aspecto_svg(svg)
    # Padding y borde del contenedor + un pequeño margen extra para que el SVG
    # no quede pegado a los bordes del iframe.
    alto_px = int(round(max_ancho_px * aspecto)) + 32

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; padding: 0; background: #ffffff; }}
  .wrap {{
    max-width: {max_ancho_px}px;
    margin: 0 auto;
    padding: 0.75em;
    box-sizing: border-box;
    text-align: center;
  }}
  .wrap svg {{ display: block; width: 100%; height: auto; }}
</style></head><body><div class="wrap">{svg}</div></body></html>"""

    components.html(html, height=alto_px, scrolling=False)
    if caption:
        st.caption(caption)
