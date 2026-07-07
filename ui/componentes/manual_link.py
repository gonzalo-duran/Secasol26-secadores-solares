"""Botones y enlaces hacia el manual de usuario.

El manual se abre SIEMPRE en otra pestaña del navegador (``target="_blank"``),
al estilo del manual de SAM: el usuario lo consulta en paralelo sin perder la
sesión de diseño. Un clic sin ``_blank`` recargaría la app y perdería el
``Proyecto`` en ``st.session_state``, así que todos los enlaces que se
renderizan DENTRO de la vista de diseño deben pasar por este módulo.

La URL es relativa (``?manual=<slug>``): el navegador la resuelve contra el
documento actual, así que funciona igual en ``localhost:8501`` y detrás del
proxy/iframe de Hugging Face Spaces.
"""

from __future__ import annotations

import streamlit as st

_ESTILO_PILL = (
    "display:inline-block;padding:0.15em 0.75em;border:1px solid rgba(128,128,128,0.45);"
    "border-radius:999px;text-decoration:none;font-size:0.9em;"
)


def boton_manual(slug: str, texto: str = "📖 Manual") -> None:
    """Renderiza un botón-píldora que abre el capítulo del manual en otra pestaña.

    Args:
        slug: Slug del capítulo (ver ``manual_contenido.CAPITULOS``).
        texto: Rótulo visible del botón.
    """
    st.markdown(
        f'<div style="text-align:right;margin-top:-0.5em;">'
        f'<a href="?manual={slug}" target="_blank" rel="noopener" '
        f'style="{_ESTILO_PILL}">{texto}</a></div>',
        unsafe_allow_html=True,
    )


def enlace_manual_inline(slug: str, texto: str) -> str:
    """Devuelve un anchor HTML inline hacia el manual (para st.markdown con HTML).

    Pensado para deep-links contextuales dentro de textos de la vista de
    diseño (ej. junto a la carta psicrométrica → ``?manual=psicrometria``).

    Args:
        slug: Slug del capítulo destino.
        texto: Texto del enlace.

    Returns:
        HTML del anchor con ``target="_blank"``.
    """
    return f'<a href="?manual={slug}" target="_blank" rel="noopener">{texto}</a>'
