"""Tests del catálogo de albedos de superficies (calculos/catalogo_albedos.py)."""

from __future__ import annotations

from calculos.catalogo_albedos import (
    ALBEDOS_SUPERFICIE,
    ETIQUETA_PERSONALIZADO,
    etiqueta_desde_albedo,
)


def test_catalogo_tiene_superficies_esperadas():
    """El catálogo incluye las superficies usuales pedidas."""
    for etiqueta in ("Cemento / hormigón", "Suelo desnudo", "Suelo con pasto"):
        assert etiqueta in ALBEDOS_SUPERFICIE


def test_catalogo_valores_en_rango():
    """Todos los albedos del catálogo están en [0, 1]."""
    for valor in ALBEDOS_SUPERFICIE.values():
        assert 0.0 <= valor <= 1.0


def test_etiqueta_desde_albedo_reconoce_conocido():
    """Un valor que coincide con el catálogo devuelve su etiqueta."""
    assert etiqueta_desde_albedo(0.30) == "Cemento / hormigón"
    assert etiqueta_desde_albedo(0.17) == "Suelo desnudo"


def test_etiqueta_desde_albedo_personalizado():
    """Un valor que no coincide con ninguna superficie cae en 'Personalizado'."""
    assert etiqueta_desde_albedo(0.123) == ETIQUETA_PERSONALIZADO
