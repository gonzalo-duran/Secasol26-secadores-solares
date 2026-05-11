"""Header institucional de Secasol26.

Renderiza la barra superior con nombre del programa y logos institucionales.
Oculta el toolbar nativo de Streamlit (espacio vacío con enlace de deploy).

Ubicación en el repo: ui/componentes/header.py

Uso en app.py::

    from ui.componentes.header import render_header

    st.set_page_config(
        page_title="Secasol26",
        page_icon="☀️",
        layout="wide",
    )
    render_header()
    tab1, tab2, ... = st.tabs([...])

Logos esperados en assets/ (raíz del repo):
    assets/logo_grupo.png   — logo del grupo de investigación (fondo transparente)
    assets/logo_inenco.png  — logo INENCO / CONICET      (fondo transparente)

Nota sobre selectores CSS:
    Los data-testid de Streamlit son semiprivados. Verificados con Streamlit 1.33+.
    Si una actualización los cambia, inspeccionar con DevTools del navegador y
    ajustar los selectores en _CSS_OCULTAR_TOOLBAR.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
_LOGO_GRUPO = _ASSETS_DIR / "logo_grupo.png"
_LOGO_INENCO = _ASSETS_DIR / "logo_inenco.png"

_ANCHO_LOGO_PX = 90  # ancho de cada logo en píxeles

# CSS que elimina el toolbar nativo de Streamlit y ajusta el padding superior.
# Selector principal: [data-testid="stToolbar"]
# Selector de la línea de decoración de color: [data-testid="stDecoration"]
# Selector del header contenedor: header[data-testid="stHeader"]
_CSS_OCULTAR_TOOLBAR = """
<style>
    [data-testid="stToolbar"]    { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 0.8rem !important; }
</style>
"""

_HTML_TITULO = """
<div style="
    text-align: center;
    padding: 4px 0 2px 0;
    line-height: 1.35;
">
    <span style="
        font-size: 1.65rem;
        font-weight: 700;
        letter-spacing: 0.06em;
    ">Secasol26</span>
    <br>
    <span style="
        font-size: 0.78rem;
        color: #888888;
        letter-spacing: 0.02em;
    ">Herramienta de Prediseño de Secadores Solares &nbsp;·&nbsp; INENCO · CONICET-UNSa</span>
</div>
"""


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def render_header() -> None:
    """Renderiza el header institucional de Secasol26.

    Debe llamarse en app.py inmediatamente después de st.set_page_config()
    y antes de cualquier st.tabs() u otro contenido.

    Efectos:
        - Inyecta CSS que oculta el toolbar nativo de Streamlit.
        - Muestra una fila de tres columnas: logo grupo | nombre | logo INENCO.
        - Agrega un st.divider() al final para separar del contenido.

    Los archivos de logo son opcionales: si no existen en assets/, la columna
    correspondiente queda vacía sin lanzar excepción ni mostrar error al usuario.
    """
    # Ocultar chrome nativo de Streamlit
    st.markdown(_CSS_OCULTAR_TOOLBAR, unsafe_allow_html=True)

    # Fila del header: [logo_grupo | título | logo_inenco]
    col_izq, col_centro, col_der = st.columns([1, 5, 1])

    with col_izq:
        _mostrar_logo(_LOGO_GRUPO, alt="Logo grupo de investigación")

    with col_centro:
        st.markdown(_HTML_TITULO, unsafe_allow_html=True)

    with col_der:
        _mostrar_logo(_LOGO_INENCO, alt="Logo INENCO CONICET")

    st.divider()


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _mostrar_logo(ruta: Path, alt: str) -> None:
    """Muestra un logo si el archivo existe; no hace nada si falta.

    Args:
        ruta: Ruta absoluta al archivo PNG del logo.
        alt:  Texto alternativo (para accesibilidad / depuración).
    """
    if ruta.is_file():
        st.image(str(ruta), width=_ANCHO_LOGO_PX)
    # Si el archivo no existe, la columna queda vacía sin error visible.
    # Para depurar, descomentar:
    # else:
    #     st.caption(f"[logo no encontrado: {ruta.name}]")
