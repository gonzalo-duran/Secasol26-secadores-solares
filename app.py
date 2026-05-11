"""
Secador Solar — Software de Prediseño de Secadores Solares
Entry point de Streamlit.
"""

from __future__ import annotations

import streamlit as st

from core.proyecto import Proyecto

# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------

from ui.componentes.header import render_header

st.set_page_config(page_title="Secasol26", page_icon="☀️", layout="wide")
render_header()   # ← antes del st.tabs()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Tipología y Configuración",
    "Emplazamiento y Clima",
    "Colector Solar",
    "Cámara de Secado",
    "Calentamiento Auxiliar",
    "Motor / Ventilador",
    "Resultados",
])

st.set_page_config(
    page_title="Secasol26 - Herramienta de Prediseño de Secadores Solares",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Inicialización del estado de sesión
# ---------------------------------------------------------------------------

if "proyecto" not in st.session_state:
    st.session_state.proyecto = Proyecto()

# ---------------------------------------------------------------------------
# Navegación por pestañas
# ---------------------------------------------------------------------------

tabs = st.tabs([
    "1 · Tipología",
    "2 · Emplazamiento y Clima",
    "3 · Colector",
    "4 · Cámara de Secado",
    "5 · Auxiliar",
    "6 · Motor",
    "7 · Resultados",
])

with tabs[0]:
    from ui.p1_tipologia import render
    render()

with tabs[1]:
    from ui.p2_emplazamiento import render
    render()

with tabs[2]:
    from ui.p3_colector import render
    render()

with tabs[3]:
    from ui.p4_camara import render
    render()

with tabs[4]:
    from ui.p5_auxiliar import render
    render()

with tabs[5]:
    from ui.p6_motor import render
    render()

with tabs[6]:
    from ui.p7_resultados import render
    render()
