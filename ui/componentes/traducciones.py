"""Infraestructura de internacionalización (i18n) — capa pura, sin streamlit.

Carga diccionarios de traducción desde ``ui/idiomas/<lang>/*.yaml`` y resuelve
claves jerárquicas con fallback en cascada: idioma pedido → español → default →
la clave literal. La capa con estado (idioma activo de la sesión, selector 🌐)
vive en ``ui/componentes/idiomas.py``; este módulo es funcional y testeable sin
servidor.

Convención de claves (ver CLAUDE.md §Internacionalización): el nombre del
archivo YAML es el namespace raíz (``p1.yaml`` → claves ``p1.*``) y el
anidamiento interno se aplana con puntos (``tipologia: {label: ...}`` →
``p1.tipologia.label``). Los placeholders son siempre nombrados y se
interpolan con ``str.format`` — si la interpolación falla, se devuelve la
plantilla sin interpolar (este módulo NUNCA lanza por una clave o un formato
roto: un texto imperfecto es mejor que una UI caída).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

IDIOMAS: tuple[str, ...] = ("es", "en", "pt")
IDIOMA_DEFAULT: str = "es"

# ui/componentes/traducciones.py → ui/idiomas/
DIR_IDIOMAS: Path = Path(__file__).resolve().parent.parent / "idiomas"


def _aplanar(prefijo: str, nodo: Any, destino: dict[str, str]) -> None:
    """Aplana un árbol de dicts YAML a claves con puntos.

    Args:
        prefijo: Prefijo acumulado (namespace) de este nodo.
        nodo: Sub-árbol YAML (dict anidado u hoja escalar).
        destino: Diccionario plano donde se acumulan las claves.
    """
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            _aplanar(f"{prefijo}.{k}", v, destino)
    else:
        destino[prefijo] = "" if nodo is None else str(nodo)


@lru_cache(maxsize=len(IDIOMAS))
def cargar_diccionario(lang: str) -> dict[str, str]:
    """Carga (y cachea) el diccionario plano de un idioma.

    Lee todos los ``*.yaml`` de ``ui/idiomas/<lang>/``, aplana el anidamiento
    a claves con puntos y prefija cada clave con el stem del archivo
    (``p1.yaml`` → ``p1.``).

    Args:
        lang: Código de idioma (``es``/``en``/``pt``).

    Returns:
        Diccionario clave → plantilla. Idioma inexistente → dict vacío.
    """
    plano: dict[str, str] = {}
    dir_lang = DIR_IDIOMAS / lang
    if not dir_lang.is_dir():
        return plano
    for archivo in sorted(dir_lang.glob("*.yaml")):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        if isinstance(datos, dict):
            _aplanar(archivo.stem, datos, plano)
    return plano


def traducir(clave: str, lang: str, /, default: str | None = None, **kwargs: Any) -> str:
    """Resuelve una clave de traducción con fallback en cascada.

    Resolución: diccionario del idioma → diccionario ES → ``default`` → la
    clave literal (visible en pantalla, útil para detectar faltantes en e2e).
    Interpola con ``str.format`` (soporta ``{largo_m:.2f}``); si el format
    falla por placeholder faltante o formato inválido, devuelve la plantilla
    sin interpolar. Nunca lanza.

    Args:
        clave: Clave jerárquica (ej. ``p1.tipologia.label``).
        lang: Código de idioma destino.
        default: Texto de respaldo si la clave no existe en ningún idioma.
        **kwargs: Valores para interpolar en la plantilla.

    Returns:
        Texto traducido (o el mejor fallback disponible).
    """
    plantilla = cargar_diccionario(lang).get(clave)
    if plantilla is None and lang != IDIOMA_DEFAULT:
        plantilla = cargar_diccionario(IDIOMA_DEFAULT).get(clave)
    if plantilla is None:
        plantilla = default if default is not None else clave
    if kwargs:
        try:
            return plantilla.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return plantilla
    return plantilla


def campo_i18n(datos: dict[str, Any], campo: str, lang: str) -> str:
    """Resuelve un campo traducible de un item de catálogo YAML.

    Busca ``datos["<campo>_<lang>"]`` (ej. ``descripcion_en``) para idiomas
    distintos de ES; si no existe (o el idioma es ES), cae al campo base.

    Args:
        datos: Dict del item de catálogo.
        campo: Nombre del campo base (ej. ``descripcion``).
        lang: Código de idioma destino.

    Returns:
        Valor del campo en el idioma pedido, o el valor base.
    """
    if lang != IDIOMA_DEFAULT:
        valor = datos.get(f"{campo}_{lang}")
        if valor:
            return str(valor)
    return str(datos.get(campo, ""))


def recargar() -> None:
    """Limpia el caché de diccionarios (desarrollo y tests)."""
    cargar_diccionario.cache_clear()
