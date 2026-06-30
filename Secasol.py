"""
Secador Solar — Software de Prediseño de Secadores Solares
Entry point de Streamlit.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import platform

import streamlit as st

from core.proyecto import Proyecto
from ui.componentes.header import render_header


def _diagnostico_entorno() -> str:
    """Devuelve un resumen del entorno de ejecución (Python + librerías clave).

    Se usa para diagnosticar discrepancias entre el repo local y el despliegue
    remoto (Hugging Face Spaces): si dos entornos corren versiones distintas de
    Python o de las librerías de cálculo, los resultados numéricos pueden diferir
    aunque el código y los datos sean idénticos. Mostrarlo en la UI hace visible
    "qué está corriendo realmente" en cada lado.

    Returns:
        Texto markdown con la versión de Python y de cada librería relevante.
    """
    libs = ["numpy", "scipy", "pandas", "pvlib", "streamlit", "plotly", "pyarrow"]
    lineas = [f"**Python** `{platform.python_version()}`"]
    for nombre in libs:
        try:
            ver = importlib.metadata.version(nombre)
        except importlib.metadata.PackageNotFoundError:
            ver = "no instalado"
        lineas.append(f"**{nombre}** `{ver}`")
    return "  \n".join(lineas)


# ---------------------------------------------------------------------------
# Configuración de página
# ---------------------------------------------------------------------------
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

with st.sidebar.expander("🔧 Entorno", expanded=False):
    st.caption(
        "Versión de Python y de las librerías de cálculo que está corriendo "
        "esta instancia. Útil para comparar el repo local con el despliegue "
        "remoto: mismos números requieren el mismo entorno."
    )
    st.markdown(_diagnostico_entorno())

# Contacto institucional (S46) — visible en todas las secciones porque el sidebar
# es persistente. Pensado para los usuarios que llegan por el despliegue público
# de Hugging Face Spaces, que de otro modo no tienen ningún punto de contacto con
# el autor ni con el grupo.
_CONTACTO_MAIL = "gonzalo.jose.duran@gmail.com"

with st.sidebar.expander("📬 Contacto", expanded=False):
    st.markdown(
        "**Gonzalo J. Durán**  \n"
        "GEEDSP · INENCO · CONICET-UNSa  \n"
        f"✉️ [{_CONTACTO_MAIL}](mailto:{_CONTACTO_MAIL})\n\n"
        "Escribime para **citar** el programa en un trabajo, **reportar un "
        "problema** o acercar **sugerencias**. ¡Todo feedback es bienvenido!"
    )

# Pie discreto del sidebar: mail siempre a la vista sin desplegar el expander.
st.sidebar.caption(f"✉️ [{_CONTACTO_MAIL}](mailto:{_CONTACTO_MAIL})")

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
