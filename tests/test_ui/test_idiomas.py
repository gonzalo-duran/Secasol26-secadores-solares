"""Tests de la infraestructura i18n (plan `docs/notas/plan_i18n.md`, F1).

Cubre: carga/aplanado de los YAML, paridad de claves y de placeholders entre
idiomas, la cascada de fallbacks de `traducir` (nunca lanza), `campo_i18n`,
`idioma_actual` fuera de runtime, cobertura de las claves usadas por los
archivos migrados, y una heurística anti-regresión que prohíbe literales
visibles en llamadas `st.*` de los archivos ya migrados (escape:
comentario `# i18n: exento` en la línea de la llamada).
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Formatter

import pytest

from core.proyecto import DiaAnalisis, ModoAnalisis, SubtipoGranEscala, Tipologia
from ui.componentes import traducciones
from ui.componentes.traducciones import (
    IDIOMA_DEFAULT,
    IDIOMAS,
    campo_i18n,
    cargar_diccionario,
    traducir,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]

# Archivos ya migrados a t() — crece fase a fase del plan i18n.
_ARCHIVOS_MIGRADOS = (
    "Secasol.py",
    "ui/p1_tipologia.py",
    "ui/p2_emplazamiento.py",
    "ui/p3_colector.py",
    "ui/p5_auxiliar.py",
    "ui/p6_motor.py",
    "ui/p4_camara.py",
    "ui/p7_resultados.py",
)

# Fuentes de core/ que emiten Advertencia (para el censo de códigos, F5).
_FUENTES_ADVERTENCIAS = (
    "core/colector.py",
    "core/camara.py",
    "core/auxiliar.py",
    "core/motor.py",
    "core/chimenea.py",
)


# ---------------------------------------------------------------------------
# Carga y estructura de los YAML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", IDIOMAS)
def test_yaml_parsea_y_sin_valores_vacios(lang):
    """Cada YAML de idioma parsea y ninguna clave aplanada queda vacía."""
    plano = cargar_diccionario(lang)
    assert plano, f"idioma '{lang}' sin claves"
    vacias = [k for k, v in plano.items() if not v.strip()]
    assert not vacias, f"claves vacías en '{lang}': {vacias}"


def test_yaml_sin_coercion_de_tipos():
    """Ninguna clave ni valor de los YAML se coerce a bool/None (gotcha `no:`).

    YAML sin comillas parsea `no`/`No`/`NO`/`yes`/`Yes`/`on`/`off`/`null` como
    booleano o None. Como el loader aplana a str, un valor `False` se muestra
    como el texto "False" y una clave `no` se aplana a `...False`, rompiendo la
    resolución (`comun.no` no existiría). La paridad no lo detecta (los 3
    idiomas comparten el error), así que se valida sobre el YAML crudo.
    """
    import yaml

    problemas: list[str] = []

    def _revisar(nodo, archivo, pfx=""):
        if not isinstance(nodo, dict):
            return
        for k, v in nodo.items():
            kp = f"{pfx}.{k}" if pfx else str(k)
            if not isinstance(k, str):
                problemas.append(f"{archivo}: clave coercida {kp!r} ({type(k).__name__})")
            if isinstance(v, dict):
                _revisar(v, archivo, kp)
            elif not isinstance(v, str):
                problemas.append(f"{archivo}: valor coercido {kp} -> {v!r} ({type(v).__name__})")

    for archivo in (traducciones.DIR_IDIOMAS).rglob("*.yaml"):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        _revisar(datos, f"{archivo.parent.name}/{archivo.name}")
    assert not problemas, "coerción de tipos en YAML (quotear la clave/valor):\n" + "\n".join(
        problemas
    )


# Familias que viven SOLO en EN/PT: el ES canónico del TOC y de las partes del
# manual está en la tupla CAPITULOS (ui/componentes/manual_contenido.py), así que
# el visor lo resuelve por default de la tupla y no hay claves manual.toc.*/
# manual.parte.* en es/manual.yaml (F9). Se exceptúan de la paridad contra ES,
# pero se exige paridad EN↔PT (ninguna traducción del TOC puede quedar a medias).
_FAMILIAS_SOLO_EN_PT = ("manual.toc.", "manual.parte.")


def _es_solo_en_pt(clave: str) -> bool:
    return clave.startswith(_FAMILIAS_SOLO_EN_PT)


@pytest.mark.i18n_paridad
def test_paridad_de_claves_entre_idiomas():
    """EN y PT tienen el mismo set de claves que ES (salvo familias EN/PT-only)."""
    claves_es = set(cargar_diccionario("es"))
    por_lang = {lang: set(cargar_diccionario(lang)) for lang in ("en", "pt")}
    for lang, claves in por_lang.items():
        faltan = claves_es - claves
        huerfanas = {c for c in claves - claves_es if not _es_solo_en_pt(c)}
        assert not faltan, f"claves de ES sin traducir en '{lang}': {sorted(faltan)}"
        assert (
            not huerfanas
        ), f"claves huérfanas en '{lang}' (no existen en ES): {sorted(huerfanas)}"
    # Las familias EN/PT-only deben coincidir entre EN y PT (ninguna a medias).
    solo_en = {c for c in por_lang["en"] if _es_solo_en_pt(c)}
    solo_pt = {c for c in por_lang["pt"] if _es_solo_en_pt(c)}
    assert solo_en == solo_pt, (
        "familias manual.toc.*/manual.parte.* desalineadas entre EN y PT: "
        f"solo en EN {sorted(solo_en - solo_pt)}, solo en PT {sorted(solo_pt - solo_en)}"
    )


def _placeholders(plantilla: str) -> set[str]:
    return {campo for _, campo, _, _ in Formatter().parse(plantilla) if campo}


@pytest.mark.i18n_paridad
def test_paridad_de_placeholders():
    """Cada clave usa el mismo set de placeholders nombrados en los 3 idiomas."""
    dicc = {lang: cargar_diccionario(lang) for lang in IDIOMAS}
    for clave, plantilla_es in dicc["es"].items():
        esperado = _placeholders(plantilla_es)
        for lang in ("en", "pt"):
            reales = _placeholders(dicc[lang].get(clave, ""))
            assert reales == esperado, (
                f"placeholders de '{clave}' difieren en '{lang}': "
                f"{sorted(reales)} vs ES {sorted(esperado)}"
            )


def test_placeholders_solo_nombrados():
    """No hay placeholders posicionales ({} o {0}) en ninguna plantilla."""
    for lang in IDIOMAS:
        for clave, plantilla in cargar_diccionario(lang).items():
            for _, campo, _, _ in Formatter().parse(plantilla):
                assert (
                    campo is None or not campo.isdigit()
                ), f"placeholder posicional en '{clave}' ({lang})"
                assert campo != "", f"placeholder anónimo {{}} en '{clave}' ({lang})"


# ---------------------------------------------------------------------------
# Unidad de traducir / campo_i18n / idioma_actual
# ---------------------------------------------------------------------------


def test_traducir_clave_existente_e_interpolacion():
    texto = traducir("p1.dia.fecha.help", "en", anio_min=2001, anio_max=2024)
    assert "2001" in texto and "2024" in texto
    assert "NASA POWER" in texto


def test_traducir_fallback_a_espanol(tmp_path, monkeypatch):
    """Idioma sin la clave → cae al diccionario ES."""
    (tmp_path / "es").mkdir()
    (tmp_path / "en").mkdir()
    (tmp_path / "es" / "x.yaml").write_text("solo_es: hola\ncomun: hola es\n", encoding="utf-8")
    (tmp_path / "en" / "x.yaml").write_text("comun: hello\n", encoding="utf-8")
    monkeypatch.setattr(traducciones, "DIR_IDIOMAS", tmp_path)
    traducciones.recargar()
    try:
        assert traducir("x.comun", "en") == "hello"
        assert traducir("x.solo_es", "en") == "hola"  # fallback ES
        assert traducir("x.nada", "en", default="def") == "def"
        assert traducir("x.nada", "en") == "x.nada"  # clave literal visible
        assert traducir("x.comun", "xx") == "hola es"  # idioma inexistente → ES
    finally:
        traducciones.recargar()


def test_traducir_format_roto_no_lanza(tmp_path, monkeypatch):
    """Placeholder faltante o formato inválido → plantilla sin interpolar."""
    (tmp_path / "es").mkdir()
    (tmp_path / "es" / "x.yaml").write_text(
        'rota: "hola {nombre} y {otro}"\nmal_formato: "valor {v:.2f}"\n', encoding="utf-8"
    )
    monkeypatch.setattr(traducciones, "DIR_IDIOMAS", tmp_path)
    traducciones.recargar()
    try:
        assert traducir("x.rota", "es", nombre="Ana") == "hola {nombre} y {otro}"
        assert traducir("x.mal_formato", "es", v="no-numero") == "valor {v:.2f}"
    finally:
        traducciones.recargar()


def test_cargar_diccionario_idioma_inexistente():
    assert cargar_diccionario("zz") == {}


def test_aplanado_prefija_con_stem_del_archivo():
    plano = cargar_diccionario("es")
    assert "p1.header" in plano
    assert "sidebar.nav.p1" in plano


def test_campo_i18n():
    datos = {"descripcion": "Vidrio común", "descripcion_en": "Common glass"}
    assert campo_i18n(datos, "descripcion", "es") == "Vidrio común"
    assert campo_i18n(datos, "descripcion", "en") == "Common glass"
    assert campo_i18n(datos, "descripcion", "pt") == "Vidrio común"  # sin _pt → base
    assert campo_i18n({}, "descripcion", "en") == ""


def test_idioma_actual_fuera_de_runtime():
    """Sin servidor de Streamlit, idioma_actual devuelve el default sin lanzar."""
    from ui.componentes.idiomas import idioma_actual

    assert idioma_actual() == IDIOMA_DEFAULT


def test_t_fuera_de_runtime():
    from ui.componentes.idiomas import t

    assert t("p1.resumen.titulo") == "Configuración activa"


# ---------------------------------------------------------------------------
# Cobertura: las claves que usa el código migrado existen en ES
# ---------------------------------------------------------------------------

_RE_T_LITERAL = re.compile(r"""\bt\(\s*["']([a-z0-9_.]+)["']""")


def test_claves_estaticas_usadas_existen_en_es():
    """Toda clave literal pasada a t() en los archivos migrados existe en ES."""
    claves_es = set(cargar_diccionario("es"))
    for rel in _ARCHIVOS_MIGRADOS:
        fuente = (RAIZ_REPO / rel).read_text(encoding="utf-8")
        for clave in _RE_T_LITERAL.findall(fuente):
            assert clave in claves_es, f"clave '{clave}' usada en {rel} no existe en es/"


def test_claves_derivadas_de_enums_existen_en_es():
    """Las familias de claves construidas desde enums están completas en ES."""
    claves_es = set(cargar_diccionario("es"))
    esperadas: list[str] = []
    for tp in Tipologia:
        v = tp.value.lower()
        esperadas += [
            f"p1.tipologia.opcion.{v}",
            f"p1.tipologia.corta.{v}",
            f"p1.tipologia.desc.{v}",
        ]
    for s in SubtipoGranEscala:
        v = s.value.lower()
        esperadas += [f"p1.subtipo.opcion.{v}", f"p1.subtipo.corta.{v}"]
    for m in ModoAnalisis:
        v = m.value.lower()
        esperadas += [f"p1.modo.opcion.{v}", f"p1.resumen.modo_corta.{v}"]
    for d in DiaAnalisis:
        v = d.value.lower()
        esperadas += [f"p1.dia.opcion.{v}", f"p1.dia.corta.{v}"]
    esperadas += [f"sidebar.nav.p{i}" for i in range(1, 8)]
    faltan = [c for c in esperadas if c not in claves_es]
    assert not faltan, f"claves derivadas de enums faltantes en es/: {faltan}"


# ---------------------------------------------------------------------------
# Catálogos (F7): descripcion_en/descripcion_pt por item
# ---------------------------------------------------------------------------


@pytest.mark.i18n_paridad
def test_catalogo_descripciones_traducidas():
    """Todo item de catálogo con `descripcion` trae `descripcion_en`/`_pt` no vacías."""
    import yaml

    faltan: list[str] = []
    for archivo in sorted((RAIZ_REPO / "catalogo").rglob("*.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            continue
        for item_id, item in datos.items():
            if not isinstance(item, dict) or "descripcion" not in item:
                continue
            for campo in ("descripcion_en", "descripcion_pt"):
                if not str(item.get(campo, "")).strip():
                    faltan.append(f"{archivo.name}:{item_id}.{campo}")
    assert not faltan, f"traducciones de catálogo faltantes (F7): {faltan}"


def test_campo_i18n_catalogo_real():
    """campo_i18n resuelve la descripción por idioma sobre un catálogo real."""
    from core import catalogo

    vidrio = catalogo.CUBIERTAS["vidrio_comun"]
    assert campo_i18n(vidrio, "descripcion", "es").startswith("Vidrio")
    assert "glass" in campo_i18n(vidrio, "descripcion", "en").lower()
    assert campo_i18n(vidrio, "descripcion", "pt").lower().startswith("vidro")
    # notas/fuente NO se traducen (quedan ES en v1): sin *_en → cae al base.
    assert campo_i18n(vidrio, "notas", "en") == vidrio.get("notas", "")


# ---------------------------------------------------------------------------
# Advertencias por código (F5): cobertura, placeholders y widget
# ---------------------------------------------------------------------------

_RE_CODIGO = re.compile(r'codigo\s*=\s*"([A-Z_]+)"')
# codigo="X" ... contexto={...} dentro del mismo bloque Advertencia(...).
_RE_CODIGO_CONTEXTO = re.compile(r'codigo\s*=\s*"(\w+)".*?contexto\s*=\s*\{(.*?)\}', re.DOTALL)
_RE_CLAVE_CONTEXTO = re.compile(r'"(\w+)"\s*:')


def _codigos_de_core() -> set[str]:
    """Censo de todos los códigos de Advertencia emitidos por core/."""
    codigos: set[str] = set()
    for rel in _FUENTES_ADVERTENCIAS:
        fuente = (RAIZ_REPO / rel).read_text(encoding="utf-8")
        codigos.update(_RE_CODIGO.findall(fuente))
    return codigos


def _contexto_por_codigo() -> dict[str, set[str]]:
    """Extrae, por código, las claves disponibles en su dict `contexto`."""
    ctx: dict[str, set[str]] = {}
    for rel in _FUENTES_ADVERTENCIAS:
        fuente = (RAIZ_REPO / rel).read_text(encoding="utf-8")
        for cod, cuerpo in _RE_CODIGO_CONTEXTO.findall(fuente):
            ctx[cod] = set(_RE_CLAVE_CONTEXTO.findall(cuerpo))
    return ctx


@pytest.mark.i18n_paridad
def test_todos_los_codigos_tienen_plantilla_en_los_tres_idiomas():
    """Cada código de advertencia de core/ tiene mensaje+sugerencia en es/en/pt."""
    codigos = _codigos_de_core()
    assert codigos, "no se detectó ningún código de advertencia en core/"
    for lang in IDIOMAS:
        plano = cargar_diccionario(lang)
        faltan = [
            f"advertencias.{c}.{campo}"
            for c in sorted(codigos)
            for campo in ("mensaje", "sugerencia")
            if f"advertencias.{c}.{campo}" not in plano
        ]
        assert not faltan, f"plantillas de advertencia faltantes en '{lang}': {faltan}"


def test_placeholders_de_advertencias_estan_en_contexto():
    """Los placeholders de cada plantilla ⊆ claves del `contexto` del código."""
    ctx = _contexto_por_codigo()
    plano_es = cargar_diccionario("es")
    problemas = []
    for c, claves in ctx.items():
        for campo in ("mensaje", "sugerencia"):
            plantilla = plano_es.get(f"advertencias.{c}.{campo}", "")
            extra = _placeholders(plantilla) - claves
            if extra:
                problemas.append(f"{c}.{campo}: {sorted(extra)} no en contexto {sorted(claves)}")
    assert not problemas, "placeholders fuera del contexto disponible:\n" + "\n".join(problemas)


def test_texto_advertencia_traduce_e_interpola():
    """texto_advertencia resuelve mensaje+sugerencia interpolando el contexto."""
    from core.advertencias import Advertencia, Severidad
    from ui.componentes.advertencias_widget import texto_advertencia

    adv = Advertencia(
        codigo="GEO_LARGO_PEQUENO",
        severidad=Severidad.INFO,
        mensaje="msg core ES",
        campo="largo_m",
        sugerencia="sug core ES",
        contexto={"largo_m": 0.3, "largo_min_m": 0.5},
    )
    msg_en, sug_en = texto_advertencia(adv, "en")
    assert "0.30" in msg_en and "length" in msg_en.lower()
    assert sug_en and "core ES" not in sug_en  # vino del YAML, no del default


def test_texto_advertencia_cae_al_default_de_core_si_no_hay_clave():
    """Código sin plantilla YAML → usa el mensaje ES de core (nunca la clave cruda)."""
    from core.advertencias import Advertencia, Severidad
    from ui.componentes.advertencias_widget import texto_advertencia

    adv = Advertencia(
        codigo="CODIGO_INEXISTENTE_XYZ",
        severidad=Severidad.WARNING,
        mensaje="mensaje original de core",
        campo="x",
        sugerencia="sugerencia original de core",
        contexto={},
    )
    msg, sug = texto_advertencia(adv, "en")
    assert msg == "mensaje original de core"
    assert sug == "sugerencia original de core"


# ---------------------------------------------------------------------------
# Heurística anti-regresión: sin literales visibles en archivos migrados
# ---------------------------------------------------------------------------

# Llamadas st.* (y st.sidebar.*) cuyo primer argumento posicional es texto
# visible. Solo se inspeccionan strings con comillas dobles: los wrappers HTML
# legítimos (que envuelven un t() en un anchor) usan comillas simples.
_WIDGETS_VISIBLES = (
    "title|header|subheader|caption|markdown|info|warning|error|success|"
    "radio|selectbox|multiselect|text_input|text_area|number_input|date_input|"
    "checkbox|toggle|button|download_button|metric|expander|slider|tabs"
)
_RE_LITERAL_VISIBLE = re.compile(
    rf"""st(?:\.sidebar)?\.(?:{_WIDGETS_VISIBLES})\(\s*f?"[^"\n]*[A-Za-zÁÉÍÓÚáéíóúÑñ]"""
)
_RE_HELP_LITERAL = re.compile(r"""help=\s*f?"[^"\n]*[A-Za-zÁÉÍÓÚáéíóúÑñ]""")


@pytest.mark.parametrize("rel", _ARCHIVOS_MIGRADOS)
def test_sin_literales_visibles_en_archivos_migrados(rel):
    """Los archivos migrados no renderizan strings literales (deben usar t())."""
    lineas = (RAIZ_REPO / rel).read_text(encoding="utf-8").splitlines()
    infractoras = []
    for n, linea in enumerate(lineas, start=1):
        if "# i18n: exento" in linea:
            continue
        if _RE_LITERAL_VISIBLE.search(linea) or _RE_HELP_LITERAL.search(linea):
            infractoras.append(f"{rel}:{n}: {linea.strip()}")
    assert not infractoras, "literales visibles sin t():\n" + "\n".join(infractoras)
