"""
Tests de las funciones de conversión en ui/componentes/unidades.py.

Verifica que las conversiones sean exactas y que Duffie↔pvlib sean inversas.
"""

from __future__ import annotations

import pytest

from ui.componentes.unidades import (
    acimut_duffie_a_pvlib,
    acimut_duffie_a_ui360,
    acimut_pvlib_a_duffie,
    acimut_ui360_a_duffie,
    celsius_a_kelvin,
    fraccion_a_porcentaje,
    kelvin_a_celsius,
    kpa_a_pa,
    pa_a_hpa,
    pa_a_kpa,
    porcentaje_a_fraccion,
)


# ---------------------------------------------------------------------------
# Temperatura
# ---------------------------------------------------------------------------


def test_celsius_a_kelvin_cero():
    assert celsius_a_kelvin(0.0) == pytest.approx(273.15)


def test_celsius_a_kelvin_negativo():
    assert celsius_a_kelvin(-273.15) == pytest.approx(0.0)


def test_kelvin_a_celsius_punto_congelacion():
    assert kelvin_a_celsius(273.15) == pytest.approx(0.0)


def test_temperatura_ida_vuelta():
    """celsius_a_kelvin y kelvin_a_celsius deben ser inversas exactas."""
    for T in [-40.0, 0.0, 20.0, 100.0]:
        assert kelvin_a_celsius(celsius_a_kelvin(T)) == pytest.approx(T)


# ---------------------------------------------------------------------------
# Presión
# ---------------------------------------------------------------------------


def test_kpa_a_pa():
    assert kpa_a_pa(101.325) == pytest.approx(101325.0)


def test_pa_a_kpa():
    assert pa_a_kpa(101325.0) == pytest.approx(101.325)


def test_pa_a_hpa():
    assert pa_a_hpa(101325.0) == pytest.approx(1013.25)


def test_presion_ida_vuelta():
    assert pa_a_kpa(kpa_a_pa(90.0)) == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Humedad relativa
# ---------------------------------------------------------------------------


def test_porcentaje_a_fraccion():
    assert porcentaje_a_fraccion(100.0) == pytest.approx(1.0)
    assert porcentaje_a_fraccion(50.0) == pytest.approx(0.5)
    assert porcentaje_a_fraccion(0.0) == pytest.approx(0.0)


def test_fraccion_a_porcentaje():
    assert fraccion_a_porcentaje(1.0) == pytest.approx(100.0)
    assert fraccion_a_porcentaje(0.0) == pytest.approx(0.0)


def test_hr_ida_vuelta():
    assert fraccion_a_porcentaje(porcentaje_a_fraccion(75.0)) == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# Ángulos Duffie ↔ pvlib
# ---------------------------------------------------------------------------
#
# Tabla de referencia:
#   Duffie   pvlib    Punto cardinal
#     0°      180°     Sur
#    90°      270°     Oeste
#   -90°       90°     Este
#   180°        0°     Norte
#  -180°        0°     Norte


@pytest.mark.parametrize(
    "duffie, pvlib_esperado",
    [
        (0.0, 180.0),      # Sur
        (90.0, 270.0),     # Oeste
        (-90.0, 90.0),     # Este
        (180.0, 0.0),      # Norte
        (-180.0, 0.0),     # Norte (equivalente)
        (45.0, 225.0),     # SO
        (-45.0, 135.0),    # SE
    ],
)
def test_acimut_duffie_a_pvlib(duffie, pvlib_esperado):
    """Verifica la tabla de conversión Duffie → pvlib."""
    assert acimut_duffie_a_pvlib(duffie) == pytest.approx(pvlib_esperado)


@pytest.mark.parametrize(
    "pvlib_ang, duffie_esperado",
    [
        (180.0, 0.0),      # Sur
        (270.0, 90.0),     # Oeste
        (90.0, -90.0),     # Este
        (0.0, 180.0),      # Norte
        (225.0, 45.0),     # SO
        (135.0, -45.0),    # SE
    ],
)
def test_acimut_pvlib_a_duffie(pvlib_ang, duffie_esperado):
    """Verifica la tabla de conversión pvlib → Duffie."""
    assert acimut_pvlib_a_duffie(pvlib_ang) == pytest.approx(duffie_esperado)


def test_acimut_conversiones_son_inversas():
    """acimut_duffie_a_pvlib y acimut_pvlib_a_duffie deben ser inversas.

    Se excluye -180° porque es el caso degenerado: -180° y +180° representan
    el mismo punto cardinal (Norte) y la función canónica devuelve +180°.
    """
    for angulo_duffie in [-90.0, -45.0, 0.0, 45.0, 90.0, 179.9]:
        pvlib_val = acimut_duffie_a_pvlib(angulo_duffie)
        duffie_recuperado = acimut_pvlib_a_duffie(pvlib_val)
        assert duffie_recuperado == pytest.approx(angulo_duffie, abs=1e-9)


# ---------------------------------------------------------------------------
# Ángulos Duffie ↔ UI360
# ---------------------------------------------------------------------------
#
# Tabla de referencia:
#   Duffie   UI360    Punto cardinal
#     0°       0°     Sur
#    90°      270°    Oeste
#   -90°       90°    Este
#   180°      180°    Norte
#  -180°      180°    Norte (equivalente)


@pytest.mark.parametrize(
    "duffie, ui360_esperado",
    [
        (0.0, 0.0),      # Sur
        (-90.0, 90.0),   # Este
        (180.0, 180.0),  # Norte
        (-180.0, 180.0), # Norte (equivalente)
        (90.0, 270.0),   # Oeste
        (45.0, 315.0),   # SO (Duffie) → NO (UI360)... wait
        (-45.0, 45.0),   # SE
    ],
)
def test_acimut_duffie_a_ui360(duffie, ui360_esperado):
    """Verifica la tabla de conversión Duffie → UI360."""
    assert acimut_duffie_a_ui360(duffie) == pytest.approx(ui360_esperado)


@pytest.mark.parametrize(
    "ui360, duffie_esperado",
    [
        (0.0, 0.0),      # Sur
        (90.0, -90.0),   # Este
        (180.0, 180.0),  # Norte  (la función retorna +180°, equivalente a -180° en Duffie)
        (270.0, 90.0),   # Oeste
        (45.0, -45.0),   # SE
        (315.0, 45.0),   # SO
    ],
)
def test_acimut_ui360_a_duffie(ui360, duffie_esperado):
    """Verifica la tabla de conversión UI360 → Duffie."""
    assert acimut_ui360_a_duffie(ui360) == pytest.approx(duffie_esperado)


def test_acimut_ui360_duffie_son_inversas():
    """Duffie→UI360→Duffie debe recuperar el ángulo original (salvo ±180° Norte)."""
    for angulo_duffie in [-90.0, -45.0, 0.0, 45.0, 90.0, 170.0]:
        ui360_val = acimut_duffie_a_ui360(angulo_duffie)
        duffie_recuperado = acimut_ui360_a_duffie(ui360_val)
        assert duffie_recuperado == pytest.approx(angulo_duffie, abs=1e-9)
