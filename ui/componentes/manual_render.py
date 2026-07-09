"""Parser y render de los capítulos markdown del manual.

Los capítulos (``manual/capitulos/*.md``) son markdown estándar más tres
convenciones propias, invisibles al leerlos en GitHub/Obsidian:

- Bloques "En profundidad" (nivel 2 de lectura), delimitados por comentarios
  HTML::

      <!-- profundidad: Título del bloque -->
      ...contenido markdown, ecuaciones $$...$$, tablas...
      <!-- /profundidad -->

  El visor los convierte en ``st.expander`` colapsados. No se anidan.

- Esquemas SVG (los de ``assets/esquemas/``), como directiva en línea propia::

      <!-- esquema: colectores_seccion_transversal | Caption opcional -->

- Anclas explícitas en headings, con sufijo ``{#ancla}``::

      ## Isotermas de sorción {#isotermas}

  Se renderizan con ``st.header/st.subheader(..., anchor=...)`` para que los
  enlaces ``?manual=slug#ancla`` funcionen sin depender de la generación
  automática de anclas de Streamlit (frágil con acentos). Solo los headings
  con ``{#...}`` son linkeables desde otros capítulos.

Las funciones de parseo y extracción son puras (sin streamlit) para poder
testearlas sin servidor; solo ``render_bloques`` usa streamlit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RE_PROFUNDIDAD_ABRE = re.compile(r"^<!--\s*profundidad:\s*(?P<titulo>.+?)\s*-->\s*$")
_RE_PROFUNDIDAD_CIERRA = re.compile(r"^<!--\s*/profundidad\s*-->\s*$")
_RE_ESQUEMA = re.compile(
    r"^<!--\s*esquema:\s*(?P<nombre>[\w-]+)\s*(?:\|\s*(?P<caption>.+?)\s*)?-->\s*$"
)
_RE_HEADING_ANCLA = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<texto>.+?)\s*\{#(?P<ancla>[\w-]+)\}\s*$")
_RE_ENLACE_MANUAL = re.compile(r"\]\(\?manual=(?P<slug>[\w-]+)(?:#(?P<ancla>[\w-]+))?\)")


@dataclass(frozen=True)
class Bloque:
    """Segmento renderizable de un capítulo.

    Attributes:
        tipo: ``"markdown"`` | ``"profundidad"`` | ``"esquema"`` | ``"heading_ancla"``.
        contenido: Markdown del bloque (markdown/profundidad), nombre del SVG
            (esquema) o texto del heading (heading_ancla).
        titulo: Título del expander (profundidad) o caption (esquema); para
            heading_ancla guarda el ancla.
        nivel: Nivel del heading (1-6) cuando ``tipo == "heading_ancla"``; 0 en el resto.
    """

    tipo: str
    contenido: str
    titulo: str = ""
    nivel: int = 0


def separar_ancla_heading(linea: str) -> tuple[str, str | None, int]:
    """Separa un heading markdown con ancla explícita ``{#ancla}``.

    Args:
        linea: Línea de markdown.

    Returns:
        ``(texto, ancla, nivel)``. Si la línea no es un heading con ancla,
        devuelve ``(linea, None, 0)``.
    """
    m = _RE_HEADING_ANCLA.match(linea)
    if not m:
        return linea, None, 0
    return m.group("texto"), m.group("ancla"), len(m.group("hashes"))


def parsear_capitulo(texto: str) -> list[Bloque]:
    """Segmenta el markdown de un capítulo en bloques renderizables.

    Args:
        texto: Contenido completo del archivo markdown.

    Returns:
        Lista ordenada de :class:`Bloque`.

    Raises:
        ValueError: ``MANUAL_PROFUNDIDAD_SIN_CIERRE`` si un bloque de
            profundidad no cierra, ``MANUAL_PROFUNDIDAD_ANIDADA`` si se abre
            uno dentro de otro, ``MANUAL_PROFUNDIDAD_CIERRE_SUELTO`` si
            aparece un cierre sin apertura, ``MANUAL_PROFUNDIDAD_SIN_TITULO``
            si el título del expander está vacío.
    """
    bloques: list[Bloque] = []
    buffer: list[str] = []
    en_profundidad = False
    titulo_prof = ""

    def _volcar_markdown() -> None:
        chunk = "\n".join(buffer).strip("\n")
        buffer.clear()
        if chunk.strip():
            bloques.append(Bloque(tipo="markdown", contenido=chunk))

    for linea in texto.splitlines():
        m_abre = _RE_PROFUNDIDAD_ABRE.match(linea)
        m_cierra = _RE_PROFUNDIDAD_CIERRA.match(linea)
        m_esquema = _RE_ESQUEMA.match(linea)

        if m_abre:
            if en_profundidad:
                raise ValueError("MANUAL_PROFUNDIDAD_ANIDADA: bloques de profundidad anidados")
            titulo_prof = m_abre.group("titulo").strip()
            if not titulo_prof:
                raise ValueError("MANUAL_PROFUNDIDAD_SIN_TITULO: título de expander vacío")
            _volcar_markdown()
            en_profundidad = True
            continue

        if m_cierra:
            if not en_profundidad:
                raise ValueError(
                    "MANUAL_PROFUNDIDAD_CIERRE_SUELTO: cierre de profundidad sin apertura"
                )
            chunk = "\n".join(buffer).strip("\n")
            buffer.clear()
            bloques.append(Bloque(tipo="profundidad", contenido=chunk, titulo=titulo_prof))
            en_profundidad = False
            titulo_prof = ""
            continue

        if m_esquema and not en_profundidad:
            _volcar_markdown()
            bloques.append(
                Bloque(
                    tipo="esquema",
                    contenido=m_esquema.group("nombre"),
                    titulo=(m_esquema.group("caption") or "").strip(),
                )
            )
            continue

        if not en_profundidad:
            texto_h, ancla, nivel = separar_ancla_heading(linea)
            if ancla is not None:
                _volcar_markdown()
                bloques.append(
                    Bloque(tipo="heading_ancla", contenido=texto_h, titulo=ancla, nivel=nivel)
                )
                continue

        buffer.append(linea)

    if en_profundidad:
        raise ValueError(
            f"MANUAL_PROFUNDIDAD_SIN_CIERRE: bloque '{titulo_prof}' sin <!-- /profundidad -->"
        )
    _volcar_markdown()
    return bloques


def extraer_enlaces_manual(texto: str) -> list[tuple[str, str | None]]:
    """Extrae los enlaces internos ``?manual=slug#ancla`` de un capítulo.

    Args:
        texto: Markdown completo del capítulo.

    Returns:
        Lista de ``(slug, ancla | None)`` en orden de aparición.
    """
    return [(m.group("slug"), m.group("ancla")) for m in _RE_ENLACE_MANUAL.finditer(texto)]


def extraer_anclas(texto: str) -> set[str]:
    """Devuelve las anclas explícitas ``{#ancla}`` declaradas en el capítulo."""
    return {
        m.group("ancla") for m in (_RE_HEADING_ANCLA.match(li) for li in texto.splitlines()) if m
    }


def extraer_esquemas(texto: str) -> list[str]:
    """Devuelve los nombres de esquemas SVG referenciados en el capítulo."""
    return [m.group("nombre") for m in (_RE_ESQUEMA.match(li) for li in texto.splitlines()) if m]


def render_bloques(bloques: list[Bloque], label_profundidad: str = "🔬 En profundidad") -> None:
    """Renderiza la lista de bloques en la UI de Streamlit.

    Un ``st.markdown`` por bloque (no un mega-string): acota el costo de
    KaTeX por render y permite intercalar expanders, esquemas y headings con
    ancla.

    Args:
        bloques: Salida de :func:`parsear_capitulo`.
        label_profundidad: Rótulo del expander "En profundidad" en el idioma
            activo (F8); el visor lo pasa traducido, el default es ES.
    """
    import streamlit as st

    from ui.componentes.esquemas import mostrar_esquema

    for b in bloques:
        if b.tipo == "markdown":
            st.markdown(b.contenido)
        elif b.tipo == "profundidad":
            titulo_exp = (
                f"{label_profundidad} — {b.titulo}"  # i18n: exento (label + título ya resueltos)
            )
            with st.expander(titulo_exp, expanded=False):
                st.markdown(b.contenido)
        elif b.tipo == "esquema":
            mostrar_esquema(b.contenido, caption=b.titulo or None)
        elif b.tipo == "heading_ancla":
            if b.nivel <= 2:
                st.header(b.contenido, anchor=b.titulo)
            else:
                st.subheader(b.contenido, anchor=b.titulo)
