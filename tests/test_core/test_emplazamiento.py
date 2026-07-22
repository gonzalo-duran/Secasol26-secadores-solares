"""
Tests de validación de Emplazamiento.

Un test por cada error duro definido en core/emplazamiento.py,
siguiendo la convención del proyecto (nombre test = código en minúsculas).
"""

from __future__ import annotations

import pytest

from core.emplazamiento import Emplazamiento


def test_emplazamiento_valido_defaults():
    """Emplazamiento con valores por defecto (Salta) no debe lanzar errores."""
    empl = Emplazamiento()
    assert empl.latitud_deg == -24.72
    assert empl.longitud_deg == -65.41


def test_emplazamiento_valido_personalizado():
    """Emplazamiento con valores extremos pero válidos debe instanciarse."""
    empl = Emplazamiento(
        latitud_deg=90.0,
        longitud_deg=-180.0,
        altitud_m=0.0,
        acimut_colector_deg=0.0,
        pendiente_colector_deg=90.0,
        zona_horaria="UTC",
    )
    assert empl.pendiente_colector_deg == 90.0


def test_empl_latitud_invalida_positiva():
    """Latitud > 90° debe lanzar EMPL_LATITUD_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_LATITUD_INVALIDA"):
        Emplazamiento(latitud_deg=90.001)


def test_empl_latitud_invalida_negativa():
    """Latitud < −90° debe lanzar EMPL_LATITUD_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_LATITUD_INVALIDA"):
        Emplazamiento(latitud_deg=-91.0)


def test_empl_longitud_invalida_positiva():
    """Longitud > 180° debe lanzar EMPL_LONGITUD_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_LONGITUD_INVALIDA"):
        Emplazamiento(longitud_deg=180.001)


def test_empl_longitud_invalida_negativa():
    """Longitud < −180° debe lanzar EMPL_LONGITUD_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_LONGITUD_INVALIDA"):
        Emplazamiento(longitud_deg=-181.0)


def test_empl_altitud_invalida():
    """Altitud < −500 m debe lanzar EMPL_ALTITUD_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_ALTITUD_INVALIDA"):
        Emplazamiento(altitud_m=-501.0)


def test_empl_acimut_invalido_positivo():
    """Acimut > 180° debe lanzar EMPL_ACIMUT_INVALIDO."""
    with pytest.raises(ValueError, match="EMPL_ACIMUT_INVALIDO"):
        Emplazamiento(acimut_colector_deg=180.001)


def test_empl_acimut_invalido_negativo():
    """Acimut < −180° debe lanzar EMPL_ACIMUT_INVALIDO."""
    with pytest.raises(ValueError, match="EMPL_ACIMUT_INVALIDO"):
        Emplazamiento(acimut_colector_deg=-181.0)


def test_empl_pendiente_invalida_negativa():
    """Pendiente < 0° debe lanzar EMPL_PENDIENTE_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_PENDIENTE_INVALIDA"):
        Emplazamiento(pendiente_colector_deg=-1.0)


def test_empl_pendiente_invalida_excede_90():
    """Pendiente > 90° debe lanzar EMPL_PENDIENTE_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_PENDIENTE_INVALIDA"):
        Emplazamiento(pendiente_colector_deg=90.001)


def test_empl_zona_horaria_invalida():
    """Zona horaria no IANA debe lanzar EMPL_ZONA_HORARIA_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_ZONA_HORARIA_INVALIDA"):
        Emplazamiento(zona_horaria="GMT+3")


def test_empl_zona_horaria_invalida_vacia():
    """Zona horaria vacía debe lanzar EMPL_ZONA_HORARIA_INVALIDA."""
    with pytest.raises(ValueError, match="EMPL_ZONA_HORARIA_INVALIDA"):
        Emplazamiento(zona_horaria="")


def test_empl_albedo_default():
    """El albedo del suelo por defecto es 0.25 (valor histórico de pvlib)."""
    assert Emplazamiento().albedo_suelo == 0.25


def test_empl_albedo_invalido_negativo():
    """Albedo < 0 debe lanzar EMPL_ALBEDO_INVALIDO."""
    with pytest.raises(ValueError, match="EMPL_ALBEDO_INVALIDO"):
        Emplazamiento(albedo_suelo=-0.01)


def test_empl_albedo_invalido_excede_1():
    """Albedo > 1 debe lanzar EMPL_ALBEDO_INVALIDO."""
    with pytest.raises(ValueError, match="EMPL_ALBEDO_INVALIDO"):
        Emplazamiento(albedo_suelo=1.01)


def test_empl_z0_terreno_default():
    """La rugosidad del terreno por defecto es 0.05 m (rural medio)."""
    assert Emplazamiento().z0_terreno_m == 0.05


def test_EMPL_Z0_TERRENO_INVALIDO():
    """z₀ debe estar en (0, 2) m: aparece en ln(z/z₀) y debe quedar por debajo
    de los 2 m de referencia del contrato de Clima."""
    with pytest.raises(ValueError, match="EMPL_Z0_TERRENO_INVALIDO"):
        Emplazamiento(z0_terreno_m=0.0)
    with pytest.raises(ValueError, match="EMPL_Z0_TERRENO_INVALIDO"):
        Emplazamiento(z0_terreno_m=-0.1)
    with pytest.raises(ValueError, match="EMPL_Z0_TERRENO_INVALIDO"):
        Emplazamiento(z0_terreno_m=2.0)
