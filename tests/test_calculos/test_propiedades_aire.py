"""Tests de calculos/propiedades_aire.py — propiedades del aire seco vs T."""

from __future__ import annotations

import pytest

from calculos.propiedades_aire import (
    beta_aire,
    cp_aire,
    k_aire,
    mu_aire,
    pr_aire,
    propiedades_aire,
    rho_aire,
)


def test_coherencia_323K_con_valores_historicos():
    """A 323 K reproducen, dentro de ~1 %, las constantes históricas del modelo."""
    assert cp_aire(323.0) == pytest.approx(1007.0, rel=0.01)
    assert k_aire(323.0) == pytest.approx(0.02814, rel=0.01)
    assert mu_aire(323.0) == pytest.approx(1.963e-5, rel=0.01)
    assert pr_aire(323.0) == pytest.approx(0.703, rel=0.01)
    assert rho_aire(323.0, 101325.0) == pytest.approx(1.093, rel=0.01)


def test_monotonia_fisica():
    """k y μ crecen con T; ρ decrece con T (gas ideal a P constante)."""
    assert k_aire(280.0) < k_aire(350.0) < k_aire(400.0)
    assert mu_aire(280.0) < mu_aire(350.0) < mu_aire(400.0)
    assert rho_aire(280.0) > rho_aire(350.0) > rho_aire(400.0)


def test_valores_en_rango_fisico():
    """En 280–400 K las propiedades quedan en rangos físicos razonables."""
    for T in (280.0, 350.0, 400.0):
        assert 0.024 < k_aire(T) < 0.035
        assert 1.7e-5 < mu_aire(T) < 2.4e-5
        assert 0.68 < pr_aire(T) < 0.72
        assert 1000.0 < cp_aire(T) < 1020.0


def test_rho_gas_ideal_escala_con_presion():
    """ρ ∝ P a T constante (gas ideal)."""
    assert rho_aire(300.0, 200000.0) == pytest.approx(2.0 * rho_aire(300.0, 100000.0))


def test_propiedades_aire_dict_consistente():
    """El dict agrega las funciones individuales sin discrepancia."""
    p = propiedades_aire(330.0, 90000.0)
    assert p["k"] == k_aire(330.0)
    assert p["mu"] == mu_aire(330.0)
    assert p["pr"] == pr_aire(330.0)
    assert p["cp"] == cp_aire(330.0)
    assert p["rho"] == rho_aire(330.0, 90000.0)


def test_beta_gas_ideal():
    """β = 1/T para gas ideal (Incropera Ec. 9.9)."""
    assert beta_aire(300.0) == pytest.approx(1.0 / 300.0)
    assert beta_aire(323.15) == pytest.approx(1.0 / 323.15)


def test_beta_decrece_con_T():
    """A mayor temperatura, menor expansión relativa por grado."""
    assert beta_aire(350.0) < beta_aire(290.0)


def test_PROP_AIRE_T_NO_POSITIVA():
    """T ≤ 0 K no tiene β definido."""
    with pytest.raises(ValueError, match="PROP_AIRE_T_NO_POSITIVA"):
        beta_aire(0.0)


def test_propiedades_aire_incluye_beta():
    """El dict agregado trae β consistente con la función individual."""
    assert propiedades_aire(330.0, 90000.0)["beta"] == beta_aire(330.0)
