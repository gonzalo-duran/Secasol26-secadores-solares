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
from ui.componentes.idiomas import idioma_actual, selector_idioma, t


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
            ver = t("sidebar.entorno.no_instalado")
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
# Manual de usuario (mejora 36) — vista paralela estilo SAM
# ---------------------------------------------------------------------------
# Con ?manual=<slug> en la URL la app renderiza el manual en vez del diseñador.
# El intercept va ANTES de inicializar `proyecto`: la vista manual es stateless
# (nunca toca st.session_state.proyecto) y st.stop() evita montar la navegación
# y las secciones. La pestaña de diseño nunca lleva ?manual= en su URL, así que
# no hay interferencia entre ambas vistas.

_slug_manual = st.query_params.get("manual")
if _slug_manual is not None:
    from ui.manual import render_manual

    render_manual(_slug_manual)
    st.stop()

# ---------------------------------------------------------------------------
# Inicialización del estado de sesión
# ---------------------------------------------------------------------------

if "proyecto" not in st.session_state:
    st.session_state.proyecto = Proyecto()

# ---------------------------------------------------------------------------
# Navegación lateral (sidebar) — persistente al scrollear (mejora 20)
# ---------------------------------------------------------------------------
# Cada sección es (clave estable, módulo). El sidebar de Streamlit queda fijo
# al scrollear el cuerpo, así que el menú está siempre a mano. Se renderiza
# solo la sección activa (no las 7), lo que acelera y aísla efectos
# colaterales entre secciones; el estado vive en st.session_state.proyecto y
# persiste al cambiar de sección. Las options del radio son claves estables
# (p1..p7) con format_func: el valor guardado en `nav_seccion` no depende del
# idioma, así la selección sobrevive a un cambio de idioma (plan i18n, F1).

_SECCIONES = {
    "p1": "ui.p1_tipologia",
    "p2": "ui.p2_emplazamiento",
    "p3": "ui.p3_colector",
    "p4": "ui.p4_camara",
    "p5": "ui.p5_auxiliar",
    "p6": "ui.p6_motor",
    "p7": "ui.p7_resultados",
}

st.sidebar.title("Secasol26")  # i18n: exento (marca)
st.sidebar.caption(t("sidebar.caption"))
selector_idioma()
# Punto de entrada global al manual: siempre en pestaña nueva (target=_blank)
# para no recargar la app y perder el proyecto en curso.
st.sidebar.markdown(
    f'<a href="?manual=indice&lang={idioma_actual()}" target="_blank" rel="noopener">'
    f'{t("sidebar.manual")}</a>',
    unsafe_allow_html=True,
)
# Migración: sesiones abiertas antes del cambio a claves estables pueden
# guardar el rótulo viejo en nav_seccion; un valor fuera de options lanza
# StreamlitAPIException, así que se descarta y el radio vuelve a p1.
if st.session_state.get("nav_seccion") not in _SECCIONES:
    st.session_state.pop("nav_seccion", None)
_seccion = st.sidebar.radio(
    t("sidebar.nav.label"),
    options=list(_SECCIONES),
    key="nav_seccion",
    format_func=lambda k: t(f"sidebar.nav.{k}"),
)

with st.sidebar.expander(t("sidebar.como_empezar.titulo"), expanded=False):
    st.markdown(t("sidebar.como_empezar.cuerpo"))

with st.sidebar.expander(t("sidebar.entorno.titulo"), expanded=False):
    st.caption(t("sidebar.entorno.caption"))
    st.markdown(_diagnostico_entorno())

# Contacto institucional (S46) — visible en todas las secciones porque el sidebar
# es persistente. Pensado para los usuarios que llegan por el despliegue público
# de Hugging Face Spaces, que de otro modo no tienen ningún punto de contacto con
# el autor ni con el grupo.
_CONTACTO_MAIL = "gonzalo.jose.duran@gmail.com"

with st.sidebar.expander(t("sidebar.contacto.titulo"), expanded=False):
    st.markdown(t("sidebar.contacto.cuerpo", mail=_CONTACTO_MAIL))

# Pie discreto del sidebar: mail siempre a la vista sin desplegar el expander.
st.sidebar.caption(f"✉️ [{_CONTACTO_MAIL}](mailto:{_CONTACTO_MAIL})")  # i18n: exento (mail)

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

importlib.import_module(_SECCIONES[_seccion]).render()
