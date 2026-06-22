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

with st.sidebar.expander("👋 Cómo empezar", expanded=False):
    st.markdown(
        "**Secasol** predimensiona secadores solares paso a paso. Recorré las "
        "secciones en orden:\n\n"
        "1. **Tipología** — tipo de secador y modo de análisis.\n"
        "2. **Emplazamiento** — coordenadas del sitio y descarga del clima (NASA POWER).\n"
        "3. **Colector** — materiales, geometría y velocidad de aire.\n"
        "4. **Cámara** — geometría, producto a secar y carga.\n"
        "5. **Auxiliar** — calentamiento de respaldo (opcional).\n"
        "6. **Motor** — ventilador o chimenea solar para mover el aire.\n"
        "7. **Resultados** — corre el prediseño completo y exporta el reporte.\n\n"
        "**Tené a mano:** latitud/longitud del sitio y el producto a secar.\n\n"
        "ℹ️ Es una herramienta de **prediseño** (orden de magnitud), no de certificación."
    )

# Persistencia de widget-keys entre secciones (mejora 28). En esta arquitectura
# de render condicional, Streamlit purga al fin del run las widget-keys de la
# sección no montada (las plain-keys sí sobreviven). Eso hacía que, al navegar
# P1↔P2 varias veces, el año de descarga (`p2_anio_descarga`) y las fechas de la
# ventana de producción volvieran a su default. Re-asignar la key al inicio del
# run —mientras todavía existe, antes de desmontar la sección— la convierte en
# valor de usuario persistente, inmune al cleanup. Lista curada (no global) para
# no tocar widgets que combinan `key=` + `index=/value=` (ya nav-safe vía el
# objeto `proyecto`) ni los flags/cachés que se limpian a propósito con `.pop()`.
_KEYS_PERSISTENTES = (
    "p1_vent_inicio",
    "p1_vent_fin",
    "p1_vent_dur_dias",
    "p2_anio_descarga",
)
for _k in _KEYS_PERSISTENTES:
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

_modulo = dict(_SECCIONES)[_rotulo]
importlib.import_module(_modulo).render()
