"""Vista del manual de usuario (mejora 36) — estilo SAM.

Se activa con el query param ``?manual=<slug>`` interceptado en ``Secasol.py``
ANTES de inicializar el estado de sesión: la vista es *stateless* y nunca toca
``st.session_state.proyecto``. Los enlaces internos del manual recargan la
página (mismo tab), lo cual es inocuo porque no hay estado que perder; los
botones que apuntan al manual desde la vista de diseño usan ``target=_blank``
(ver ``ui/componentes/manual_link.py``).

Contenido: ``manual/capitulos/*.md`` + TOC declarativo en
``ui/componentes/manual_contenido.py`` + parser/render en
``ui/componentes/manual_render.py``.
"""

from __future__ import annotations

from functools import lru_cache

import streamlit as st

from ui.componentes.manual_contenido import (
    CAPITULOS,
    CAPITULOS_DIR,
    PARTES,
    POR_SLUG,
    SLUG_INDICE,
    CapituloManual,
)
from ui.componentes.manual_render import parsear_capitulo, render_bloques


@lru_cache(maxsize=64)
def _leer_capitulo(archivo: str) -> str:
    """Lee (y cachea en memoria) el markdown de un capítulo.

    Args:
        archivo: Nombre del archivo dentro de ``manual/capitulos/``.

    Returns:
        Contenido del markdown, o cadena vacía si el archivo no existe.
    """
    ruta = CAPITULOS_DIR / archivo
    if not ruta.is_file():
        return ""
    return ruta.read_text(encoding="utf-8")


def _sidebar_manual(slug_activo: str) -> None:
    """Sidebar propio del manual: TOC completo agrupado por parte.

    Los capítulos son enlaces ``?manual=slug`` (no widgets): la recarga es
    inocua porque la vista es stateless, y así no hay estado de widgets que
    gestionar.
    """
    st.sidebar.title("📖 Manual de Secasol")
    st.sidebar.markdown(f"[⬅ Volver al diseñador](./) · [🏠 Índice](?manual={SLUG_INDICE})")
    for parte in PARTES:
        lineas = [f"**{parte}**"]
        for cap in CAPITULOS:
            if cap.parte != parte:
                continue
            if cap.slug == slug_activo:
                lineas.append(f"- ▸ **{cap.titulo}**")
            else:
                lineas.append(f"- [{cap.titulo}](?manual={cap.slug})")
        st.sidebar.markdown("\n".join(lineas))
    st.sidebar.divider()
    st.sidebar.caption(
        "Los enlaces del manual navegan en esta misma pestaña. "
        "Tu diseño sigue abierto en la pestaña original de Secasol; "
        "«Volver al diseñador» abre la vista de diseño acá (sesión nueva, "
        "no toca tu proyecto)."
    )


def _render_indice(aviso: str | None = None) -> None:
    """Página índice generada desde el TOC (no es un .md)."""
    if aviso:
        st.info(aviso)
    st.title("📖 Manual de Secasol")
    st.markdown(
        "Referencia de uso y de los modelos físicos de **Secasol**, el prediseñador "
        "de secadores solares. Cada capítulo abre con la idea general y despliega "
        "los detalles (ecuaciones, correlaciones, decisiones de modelo) en bloques "
        "**🔬 En profundidad**. Los capítulos de la Parte IV son la referencia "
        "técnica completa de cada subsistema."
    )
    for parte in PARTES:
        st.header(parte)
        for cap in CAPITULOS:
            if cap.parte != parte:
                continue
            st.markdown(f"**[{cap.titulo}](?manual={cap.slug})** — {cap.descripcion}")


def _render_capitulo(cap: CapituloManual) -> None:
    """Renderiza un capítulo: breadcrumb, contenido y navegación anterior/siguiente."""
    st.markdown(f"[📖 Manual](?manual={SLUG_INDICE}) › {cap.parte} › **{cap.titulo}**")
    texto = _leer_capitulo(cap.archivo)
    if not texto:
        st.error(f"El capítulo '{cap.slug}' todavía no tiene contenido ({cap.archivo}).")
        return
    render_bloques(parsear_capitulo(texto))

    st.divider()
    idx = CAPITULOS.index(cap)
    col_prev, col_next = st.columns(2)
    if idx > 0:
        anterior = CAPITULOS[idx - 1]
        col_prev.markdown(f"⬅ [{anterior.titulo}](?manual={anterior.slug})")
    if idx < len(CAPITULOS) - 1:
        siguiente = CAPITULOS[idx + 1]
        col_next.markdown(
            f'<div style="text-align:right;">'
            f'<a href="?manual={siguiente.slug}">{siguiente.titulo} ➡</a></div>',
            unsafe_allow_html=True,
        )


def render_manual(slug: str) -> None:
    """Punto de entrada de la vista manual.

    Args:
        slug: Valor del query param ``manual``. Vacío, ``indice`` o
            desconocido → página índice (con aviso si era desconocido).
    """
    slug = slug.strip().lower()
    _sidebar_manual(slug)

    if slug in ("", SLUG_INDICE):
        _render_indice()
        return
    cap = POR_SLUG.get(slug)
    if cap is None:
        _render_indice(aviso=f"No existe el capítulo '{slug}'. Este es el índice del manual.")
        return
    _render_capitulo(cap)
