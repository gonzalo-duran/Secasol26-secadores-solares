"""Tests de integridad del manual de usuario (mejora 36).

Validan el contenido de ``manual/capitulos/*.md`` contra el TOC declarativo
(``ui/componentes/manual_contenido.py``) usando solo las funciones puras del
parser (``ui/componentes/manual_render.py``) — sin servidor Streamlit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ui.componentes.manual_contenido import (
    CAPITULOS,
    CAPITULOS_DIR,
    POR_SLUG,
    SLUG_INDICE,
    SLUG_POR_SECCION,
)
from ui.componentes.manual_contenido import (
    ruta_capitulo as _ruta,
)
from ui.componentes.manual_render import (
    extraer_anclas,
    extraer_enlaces_manual,
    extraer_esquemas,
    parsear_capitulo,
    separar_ancla_heading,
)

_ESQUEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "esquemas"

_SLUG_RE = re.compile(r"[a-z][a-z0-9-]*")


def _texto(cap) -> str:
    return cap.ruta.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Integridad TOC ↔ disco
# ---------------------------------------------------------------------------


def test_manual_archivos_declarados_existen():
    faltantes = [c.archivo for c in CAPITULOS if not c.ruta.is_file()]
    assert not faltantes, f"Capítulos declarados sin archivo: {faltantes}"


def test_manual_sin_archivos_huerfanos():
    declarados = {c.archivo for c in CAPITULOS}
    en_disco = {p.name for p in (CAPITULOS_DIR / "es").glob("*.md")}
    huerfanos = en_disco - declarados
    assert not huerfanos, f"Archivos .md sin declarar en el TOC: {sorted(huerfanos)}"


def test_manual_slugs_unicos_y_kebab_case():
    slugs = [c.slug for c in CAPITULOS]
    assert len(slugs) == len(set(slugs)), "Slugs duplicados en el TOC"
    for slug in slugs:
        assert _SLUG_RE.fullmatch(slug), f"Slug no kebab-case: {slug!r}"
    assert SLUG_INDICE not in slugs, "El slug reservado 'indice' no puede ser un capítulo"


def test_manual_titulos_y_descripciones_no_vacios():
    for c in CAPITULOS:
        assert c.titulo.strip(), f"Título vacío: {c.slug}"
        assert c.descripcion.strip(), f"Descripción vacía: {c.slug}"
        assert c.parte.strip(), f"Parte vacía: {c.slug}"


# ---------------------------------------------------------------------------
# 2. Sintaxis de bloques "En profundidad"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_parsea_sin_errores(cap):
    bloques = parsear_capitulo(_texto(cap))
    assert bloques, f"Capítulo vacío: {cap.slug}"
    for b in bloques:
        if b.tipo == "profundidad":
            assert b.titulo.strip(), f"Expander sin título en {cap.slug}"
            assert b.contenido.strip(), f"Expander vacío en {cap.slug}"


def test_manual_profundidad_sin_cierre_lanza():
    with pytest.raises(ValueError, match="MANUAL_PROFUNDIDAD_SIN_CIERRE"):
        parsear_capitulo("<!-- profundidad: Abierto -->\ntexto")


def test_manual_profundidad_anidada_lanza():
    texto = (
        "<!-- profundidad: Uno -->\n"
        "<!-- profundidad: Dos -->\n"
        "<!-- /profundidad -->\n"
        "<!-- /profundidad -->"
    )
    with pytest.raises(ValueError, match="MANUAL_PROFUNDIDAD_ANIDADA"):
        parsear_capitulo(texto)


def test_manual_profundidad_cierre_suelto_lanza():
    with pytest.raises(ValueError, match="MANUAL_PROFUNDIDAD_CIERRE_SUELTO"):
        parsear_capitulo("texto\n<!-- /profundidad -->")


def test_manual_separar_ancla_heading():
    texto, ancla, nivel = separar_ancla_heading("## Isotermas de sorción {#isotermas}")
    assert (texto, ancla, nivel) == ("Isotermas de sorción", "isotermas", 2)
    texto, ancla, nivel = separar_ancla_heading("## Sin ancla")
    assert ancla is None and nivel == 0


# ---------------------------------------------------------------------------
# 3. Enlaces internos: slugs y anclas resuelven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_enlaces_internos_resuelven(cap):
    for slug, ancla in extraer_enlaces_manual(_texto(cap)):
        assert (
            slug == SLUG_INDICE or slug in POR_SLUG
        ), f"{cap.slug}: enlace a slug inexistente '?manual={slug}'"
        if ancla is not None:
            destino = POR_SLUG[slug]
            anclas_destino = extraer_anclas(_texto(destino))
            assert ancla in anclas_destino, (
                f"{cap.slug}: ancla '#{ancla}' no existe en '{slug}' "
                f"(disponibles: {sorted(anclas_destino)})"
            )


def test_manual_todos_los_capitulos_enlazados_desde_alguno():
    """Ningún capítulo debe quedar aislado (inalcanzable por enlaces)."""
    enlazados: set[str] = set()
    for cap in CAPITULOS:
        enlazados.update(slug for slug, _ in extraer_enlaces_manual(_texto(cap)))
    aislados = {c.slug for c in CAPITULOS} - enlazados
    assert not aislados, f"Capítulos que ningún otro enlaza: {sorted(aislados)}"


# ---------------------------------------------------------------------------
# 4. Esquemas SVG referenciados existen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_esquemas_existen(cap):
    for nombre in extraer_esquemas(_texto(cap)):
        assert (
            _ESQUEMAS_DIR / f"{nombre}.svg"
        ).is_file(), f"{cap.slug}: esquema '{nombre}' sin SVG en assets/esquemas/"


# ---------------------------------------------------------------------------
# 5. Ecuaciones KaTeX bien formadas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_ecuaciones_display_balanceadas(cap):
    for b in parsear_capitulo(_texto(cap)):
        if b.tipo in ("markdown", "profundidad"):
            assert b.contenido.count("$$") % 2 == 0, f"{cap.slug}: bloque con '$$' desbalanceado"


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_sin_entorno_align(cap):
    # KaTeX no soporta \begin{align}; usar aligned.
    assert r"\begin{align}" not in _texto(cap), f"{cap.slug}: usar 'aligned', no 'align'"


# ---------------------------------------------------------------------------
# 6. Mapa sección → capítulo completo
# ---------------------------------------------------------------------------


def test_manual_slug_por_seccion_cubre_p1_a_p7():
    assert set(SLUG_POR_SECCION) == {f"p{i}" for i in range(1, 8)}
    for seccion, slug in SLUG_POR_SECCION.items():
        assert slug in POR_SLUG, f"{seccion} apunta a slug inexistente '{slug}'"


# ---------------------------------------------------------------------------
# 7. Higiene: sin URLs absolutas hardcodeadas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cap", CAPITULOS, ids=lambda c: c.slug)
def test_manual_sin_urls_absolutas_de_la_app(cap):
    texto = _texto(cap)
    for prohibido in ("http://localhost", "https://localhost", "hf.space", "huggingface.co"):
        assert prohibido not in texto, f"{cap.slug}: URL absoluta hardcodeada '{prohibido}'"


# ---------------------------------------------------------------------------
# 8. Multiidioma (F8): carpetas por idioma, fallback a ES, propagación de lang
# ---------------------------------------------------------------------------


def test_manual_capitulos_es_completos():
    """Todos los capítulos existen bajo manual/capitulos/es/ (ES obligatorio)."""
    from ui.componentes.manual_contenido import IDIOMA_MANUAL_DEFAULT

    for cap in CAPITULOS:
        ruta, es_fallback = _ruta(cap.archivo, IDIOMA_MANUAL_DEFAULT)
        assert ruta.is_file(), f"falta el ES de {cap.slug}: {ruta}"
        assert es_fallback is False


def test_ruta_capitulo_fallback_a_es():
    """Un capítulo sin la traducción a un idioma cae al ES con la señal es_fallback.

    F9 traduce los capítulos de a poco; el test busca dinámicamente un capítulo
    que todavía no tenga su .md en 'en' para ejercitar el fallback. Si ya están
    todos traducidos, no hay nada que verificar (el fallback deja de aplicar).
    """
    sin_traducir = [cap for cap in CAPITULOS if not (CAPITULOS_DIR / "en" / cap.archivo).is_file()]
    if not sin_traducir:
        pytest.skip("todos los capítulos ya están traducidos a 'en' (F9 completa)")
    cap = sin_traducir[0]
    ruta, es_fallback = _ruta(cap.archivo, "en")
    assert es_fallback is True
    assert ruta == CAPITULOS_DIR / "es" / cap.archivo
    assert ruta.is_file()


def test_render_manual_helpers_propagan_lang():
    """Los helpers del visor arman URLs con &lang= y reescriben enlaces internos."""
    from ui.manual import _propagar_lang, _url

    assert _url("colector", "en") == "?manual=colector&lang=en"
    assert _url("colector", "pt", ancla="tipos") == "?manual=colector&lang=pt#tipos"
    # Reescribe enlaces internos del markdown preservando el ancla.
    md = "ver [colector](?manual=colector) y [psi](?manual=psicrometria#carta)"
    out = _propagar_lang(md, "en")
    assert "(?manual=colector&lang=en)" in out
    assert "(?manual=psicrometria&lang=en#carta)" in out


def test_manual_ui_chrome_traducido():
    """El chrome del visor (manual.ui.*) resuelve distinto por idioma."""
    from ui.componentes.traducciones import traducir

    assert traducir("manual.ui.volver", "es") == "⬅ Volver al diseñador"
    assert "Back" in traducir("manual.ui.volver", "en")
    assert "Voltar" in traducir("manual.ui.volver", "pt")
    # Título del TOC (F9): EN/PT resuelven por manual.toc.<slug>.titulo; ES cae al
    # default de la tupla CAPITULOS (no hay claves manual.toc.* en es/manual.yaml).
    from ui.manual import _titulo

    cap = POR_SLUG["colector"]
    assert _titulo(cap, "es") == cap.titulo  # ES: default de la tupla
    assert _titulo(cap, "en") == "3 · Solar collector"
    assert _titulo(cap, "pt") == "3 · Coletor solar"
