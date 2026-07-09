"""Vista del manual de usuario (mejora 36) — estilo SAM, multiidioma (F8).

Se activa con el query param ``?manual=<slug>`` interceptado en ``Secasol.py``
ANTES de inicializar el estado de sesión: la vista es *stateless* y nunca toca
``st.session_state.proyecto``. Los enlaces internos del manual recargan la
página (mismo tab) preservando ``&lang=``; los botones que apuntan al manual
desde la vista de diseño usan ``target=_blank`` (ver
``ui/componentes/manual_link.py``).

Idioma (F8): el visor lee ``idioma_actual()`` (del query param ``?lang=`` en
la pestaña del manual). El *chrome* del visor se traduce vía el namespace
``manual.ui.*``; los títulos del TOC vía ``manual.toc.<slug>.*`` con fallback
al ES de la tupla ``CAPITULOS``. El contenido de cada capítulo vive en
``manual/capitulos/<lang>/*.md``; si falta la traducción se muestra el ES con
un aviso (``manual.ui.solo_es``). La traducción de los 22 capítulos es F9.
"""

from __future__ import annotations

import re
from functools import lru_cache

import streamlit as st

from ui.componentes.idiomas import idioma_actual
from ui.componentes.manual_contenido import (
    CAPITULOS,
    PARTES,
    POR_SLUG,
    SLUG_INDICE,
    CapituloManual,
    ruta_capitulo,
)
from ui.componentes.manual_render import parsear_capitulo, render_bloques
from ui.componentes.traducciones import traducir

# Reescribe los enlaces internos ``](?manual=slug#ancla)`` para propagar &lang=.
_RE_ENLACE_INTERNO = re.compile(r"\]\(\?manual=([\w-]+)(#[\w-]+)?\)")


def _tr(clave: str, lang: str, **kwargs) -> str:
    """Traduce una clave del namespace ``manual.*`` para el visor."""
    return traducir(f"manual.{clave}", lang, **kwargs)


def _titulo(cap: CapituloManual, lang: str) -> str:
    """Título del capítulo en el idioma pedido (fallback al ES de la tupla)."""
    return traducir(f"manual.toc.{cap.slug}.titulo", lang, default=cap.titulo)


def _descripcion(cap: CapituloManual, lang: str) -> str:
    """Descripción del capítulo en el idioma pedido (fallback al ES de la tupla)."""
    return traducir(f"manual.toc.{cap.slug}.descripcion", lang, default=cap.descripcion)


def _parte(parte: str, idx: int, lang: str) -> str:
    """Rótulo de la parte en el idioma pedido (fallback al ES de la tupla)."""
    return traducir(f"manual.parte.{idx}", lang, default=parte)


def _url(slug: str, lang: str, ancla: str | None = None) -> str:
    """URL relativa de un capítulo preservando el idioma (``?manual=..&lang=..``)."""
    sufijo = f"#{ancla}" if ancla else ""
    return f"?manual={slug}&lang={lang}{sufijo}"


@lru_cache(maxsize=128)
def _leer_capitulo(archivo: str, lang: str) -> tuple[str, bool]:
    """Lee (y cachea) el markdown de un capítulo con fallback a ES.

    Args:
        archivo: Nombre del archivo (ej. ``12_colector.md``).
        lang: Idioma pedido.

    Returns:
        Tupla ``(texto, es_fallback)``: el contenido y si se cayó al ES por
        falta de traducción. ``("", False)`` si ni el ES existe.
    """
    ruta, es_fallback = ruta_capitulo(archivo, lang)
    if not ruta.is_file():
        return "", False
    return ruta.read_text(encoding="utf-8"), es_fallback


def _propagar_lang(texto: str, lang: str) -> str:
    """Añade ``&lang=`` a los enlaces internos ``?manual=slug`` del markdown."""
    return _RE_ENLACE_INTERNO.sub(
        lambda m: f"](?manual={m.group(1)}&lang={lang}{m.group(2) or ''})", texto
    )


def _sidebar_manual(slug_activo: str, lang: str) -> None:
    """Sidebar propio del manual: TOC completo agrupado por parte."""
    st.sidebar.title(_tr("ui.sidebar_titulo", lang))
    st.sidebar.markdown(
        f"[{_tr('ui.volver', lang)}](./) · "
        f"[{_tr('ui.indice', lang)}]({_url(SLUG_INDICE, lang)})"
    )
    for idx, parte in enumerate(PARTES):
        lineas = [f"**{_parte(parte, idx, lang)}**"]
        for cap in CAPITULOS:
            if cap.parte != parte:
                continue
            titulo = _titulo(cap, lang)
            if cap.slug == slug_activo:
                lineas.append(f"- ▸ **{titulo}**")
            else:
                lineas.append(f"- [{titulo}]({_url(cap.slug, lang)})")
        st.sidebar.markdown("\n".join(lineas))  # i18n: exento (separador, líneas ya traducidas)
    st.sidebar.divider()
    st.sidebar.caption(_tr("ui.sidebar_caption", lang))


def _render_indice(lang: str, aviso: str | None = None) -> None:
    """Página índice generada desde el TOC (no es un .md)."""
    if aviso:
        st.info(aviso)
    st.title(_tr("ui.indice_titulo", lang))
    st.markdown(_tr("ui.indice_intro", lang))
    for idx, parte in enumerate(PARTES):
        st.header(_parte(parte, idx, lang))
        for cap in CAPITULOS:
            if cap.parte != parte:
                continue
            st.markdown(
                f"**[{_titulo(cap, lang)}]({_url(cap.slug, lang)})** — {_descripcion(cap, lang)}"
            )


def _render_capitulo(cap: CapituloManual, lang: str) -> None:
    """Renderiza un capítulo: breadcrumb, contenido y navegación anterior/siguiente."""
    idx_parte = PARTES.index(cap.parte)
    st.markdown(
        f"[{_tr('ui.breadcrumb_manual', lang)}]({_url(SLUG_INDICE, lang)}) › "
        f"{_parte(cap.parte, idx_parte, lang)} › **{_titulo(cap, lang)}**"
    )
    texto, es_fallback = _leer_capitulo(cap.archivo, lang)
    if not texto:
        st.error(_tr("ui.sin_contenido", lang, slug=cap.slug, archivo=cap.archivo))
        return
    if es_fallback:
        st.info(_tr("ui.solo_es", lang))
    render_bloques(
        parsear_capitulo(_propagar_lang(texto, lang)),
        label_profundidad=_tr("ui.en_profundidad", lang),
    )

    st.divider()
    idx = CAPITULOS.index(cap)
    col_prev, col_next = st.columns(2)
    if idx > 0:
        anterior = CAPITULOS[idx - 1]
        col_prev.markdown(f"⬅ [{_titulo(anterior, lang)}]({_url(anterior.slug, lang)})")
    if idx < len(CAPITULOS) - 1:
        siguiente = CAPITULOS[idx + 1]
        col_next.markdown(
            f'<div style="text-align:right;">'
            f'<a href="{_url(siguiente.slug, lang)}">{_titulo(siguiente, lang)} ➡</a></div>',
            unsafe_allow_html=True,
        )


def render_manual(slug: str) -> None:
    """Punto de entrada de la vista manual.

    Args:
        slug: Valor del query param ``manual``. Vacío, ``indice`` o
            desconocido → página índice (con aviso si era desconocido).
    """
    lang = idioma_actual()
    slug = slug.strip().lower()
    _sidebar_manual(slug, lang)

    if slug in ("", SLUG_INDICE):
        _render_indice(lang)
        return
    cap = POR_SLUG.get(slug)
    if cap is None:
        _render_indice(lang, aviso=_tr("ui.no_existe", lang, slug=slug))
        return
    _render_capitulo(cap, lang)
