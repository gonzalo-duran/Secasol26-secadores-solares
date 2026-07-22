"""
Tests de la versión de Secasol (core/version.py).

`__version__` es la fuente de verdad en runtime (el `CHANGELOG.md` no se deploya al
Space), así que el riesgo real es que quede desfasada del changelog al liberar. Estos
tests atan las dos fuentes: si se agrega una versión al `CHANGELOG.md` sin tocar
`core/version.py` (o al revés), fallan.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.version import __version__

_RAIZ = Path(__file__).resolve().parents[2]
_CHANGELOG = _RAIZ / "CHANGELOG.md"

# Encabezados de versión liberada: "## [1.1.0] — 2026-07-21" (ignora "## [Unreleased]").
_RE_VERSION = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def _ultima_version_changelog() -> str:
    """Devuelve la versión liberada más reciente del CHANGELOG (la primera del archivo)."""
    versiones = _RE_VERSION.findall(_CHANGELOG.read_text(encoding="utf-8"))
    if not versiones:
        pytest.fail("El CHANGELOG.md no tiene ningún encabezado de versión liberada")
    return versiones[0]


def test_version_es_semver():
    assert re.fullmatch(
        r"\d+\.\d+\.\d+", __version__
    ), f"__version__ debe ser MAJOR.MINOR.PATCH, no {__version__!r}"


def test_version_coincide_con_changelog():
    esperada = _ultima_version_changelog()
    assert __version__ == esperada, (
        f"core/version.py dice {__version__!r} y el CHANGELOG.md libera {esperada!r}. "
        "Al liberar hay que actualizar ambos."
    )
