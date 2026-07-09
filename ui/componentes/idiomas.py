"""Idioma activo de la sesión + selector 🌐 (capa con estado, importa streamlit).

La resolución del idioma es: ``st.session_state["idioma"]`` → query param
``?lang=`` (si es válido se copia a la sesión) → español. El query param
permite compartir URLs pre-configuradas del Space y que el manual (pestaña
aparte, stateless) herede el idioma (fase F8 del plan i18n).

La función :func:`t` es el punto de entrada de traducción para TODA la UI:
``t("p1.tipologia.label")``. NUNCA llamarla a nivel de módulo (el idioma
cambia entre reruns): los dicts de etiquetas module-level deben ser funciones.
Ver ``docs/notas/plan_i18n.md`` y CLAUDE.md §Internacionalización.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.componentes.traducciones import IDIOMA_DEFAULT, IDIOMAS, campo_i18n, traducir

_NOMBRES_IDIOMA = {"es": "Español", "en": "English", "pt": "Português"}


def idioma_actual() -> str:
    """Devuelve el código del idioma activo de la sesión.

    Fuera de un runtime de Streamlit (pytest sin servidor) devuelve el
    default sin lanzar.

    Returns:
        Código de idioma (``es``/``en``/``pt``).
    """
    try:
        lang = st.session_state.get("idioma")
        if lang in IDIOMAS:
            return lang
        lang = st.query_params.get("lang")
        if lang in IDIOMAS:
            st.session_state["idioma"] = lang
            return lang
    except Exception:
        pass
    return IDIOMA_DEFAULT


def t(clave: str, /, default: str | None = None, **kwargs: Any) -> str:
    """Traduce una clave al idioma activo de la sesión.

    Args:
        clave: Clave jerárquica (ej. ``p1.tipologia.label``).
        default: Texto de respaldo si la clave no existe.
        **kwargs: Valores para interpolar en la plantilla.

    Returns:
        Texto traducido.
    """
    return traducir(clave, idioma_actual(), default=default, **kwargs)


def t_catalogo(datos: dict, campo: str = "descripcion", default: str = "") -> str:
    """Resuelve un campo traducible de un item de catálogo en el idioma activo.

    Envuelve :func:`ui.componentes.traducciones.campo_i18n` leyendo el idioma
    de la sesión (F7). Busca ``<campo>_<lang>`` (ej. ``descripcion_en``) y cae
    al campo base ES; si no existe, devuelve ``default``.

    Args:
        datos: Dict del item de catálogo.
        campo: Nombre del campo base (default ``descripcion``).
        default: Texto de respaldo si el item no trae el campo (ej. el id).

    Returns:
        Descripción en el idioma activo, o ``default``.
    """
    return campo_i18n(datos, campo, idioma_actual()) or default


def _sincronizar_query_param() -> None:
    """on_change del selector: refleja el idioma elegido en ``?lang=``."""
    st.query_params["lang"] = st.session_state["idioma"]


def selector_idioma() -> None:
    """Renderiza el selector 🌐 de idioma en el sidebar.

    Las options son los códigos estables (``es``/``en``/``pt``) con
    ``format_func`` para el nombre visible — el valor guardado en
    ``session_state`` no depende del idioma (misma regla que la navegación).
    """
    if "idioma" not in st.session_state:
        st.session_state["idioma"] = idioma_actual()
    st.sidebar.selectbox(
        "🌐 Idioma / Language / Língua",
        options=list(IDIOMAS),
        key="idioma",
        format_func=lambda c: _NOMBRES_IDIOMA.get(c, c),
        on_change=_sincronizar_query_param,
    )
