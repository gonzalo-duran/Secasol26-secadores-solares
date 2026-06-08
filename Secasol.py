"""
Secador Solar — Software de Prediseño de Secadores Solares
Entry point de Streamlit.
"""

from __future__ import annotations

import importlib

import streamlit as st

from core.proyecto import Proyecto

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
from ui.componentes.header import render_header

st.set_page_config(
    page_title="Secasol26 - Prediseño de Secadores Solares",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)
render_header()  # header full-width, antes de la navegación lateral

# ---------------------------------------------------------------------------
# Inicialización del estado de sesión
# ---------------------------------------------------------------------------

if "proyecto" not in st.session_state:
    st.session_state.proyecto = Proyecto()

# ---------------------------------------------------------------------------
# Navegación lateral (sidebar) — persistente al scrollear (mejora 20)
# ---------------------------------------------------------------------------
# Cada sección es (rótulo, módulo). El sidebar de Streamlit queda fijo al
# scrollear el cuerpo, así que el menú está siempre a mano. Se renderiza solo
# la sección activa (no las 7), lo que acelera y aísla efectos colaterales
# entre secciones; el estado vive en st.session_state.proyecto y persiste al
# cambiar de sección.

_SECCIONES = [
    ("1 · Tipología", "ui.p1_tipologia"),
    ("2 · Emplazamiento y Clima", "ui.p2_emplazamiento"),
    ("3 · Colector", "ui.p3_colector"),
    ("4 · Cámara de Secado", "ui.p4_camara"),
    ("5 · Auxiliar", "ui.p5_auxiliar"),
    ("6 · Motor", "ui.p6_motor"),
    ("7 · Resultados", "ui.p7_resultados"),
]

st.sidebar.title("Secasol26")
st.sidebar.caption("Prediseño de secadores solares")
_rotulo = st.sidebar.radio(
    "Secciones del proyecto",
    options=[r for r, _ in _SECCIONES],
    key="nav_seccion",
)

_modulo = dict(_SECCIONES)[_rotulo]
importlib.import_module(_modulo).render()
