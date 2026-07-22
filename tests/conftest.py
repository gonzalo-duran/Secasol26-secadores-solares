"""
Fixtures compartidas para todos los tests.

Provee instancias de proyecto mínimas válidas para usar como punto de
partida en los tests de validación y cálculo.
"""

from __future__ import annotations

import pytest

from core.proyecto import Configuracion, Meta, ModoAnalisis, Proyecto, Tipologia


@pytest.fixture
def proyecto_armario_minimo() -> Proyecto:
    """Proyecto con configuración mínima válida, tipología ARMARIO."""
    return Proyecto(
        meta=Meta(nombre="Test armario", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )


@pytest.fixture
def proyecto_caja_minimo() -> Proyecto:
    """Proyecto con configuración mínima válida, tipología CAJA."""
    return Proyecto(
        meta=Meta(nombre="Test caja", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.CAJA,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
