"""
Tests de validación de coherencia global del Proyecto.

Cubre los 5 errores duros a nivel Proyecto definidos en la bitácora
(Tanda 5): PROY_CAJA_CON_COLECTOR, PROY_CAJA_CON_MOTOR,
PROY_AUXILIAR_SERIE_SIN_COLECTOR, PROY_MOTOR_SIN_CAMARA,
PROY_ANUAL_SIN_VECTORIZACION.
"""

from __future__ import annotations

import pytest

from core.proyecto import Configuracion, ModoAnalisis, Tipologia


def test_proy_anual_sin_vectorizacion():
    """CAJA + análisis anual debe lanzar ValueError."""
    with pytest.raises(ValueError, match="PROY_ANUAL_SIN_VECTORIZACION"):
        Configuracion(
            tipologia=Tipologia.CAJA,
            modo_analisis=ModoAnalisis.ANUAL,
        )


def test_proyecto_armario_minimo_valido(proyecto_armario_minimo):
    """Un proyecto ARMARIO mínimo no debe lanzar errores al instanciarse."""
    assert proyecto_armario_minimo.configuracion.tipologia == Tipologia.ARMARIO


def test_proyecto_caja_minimo_valido(proyecto_caja_minimo):
    """Un proyecto CAJA mínimo no debe lanzar errores al instanciarse."""
    assert proyecto_caja_minimo.configuracion.tipologia == Tipologia.CAJA
