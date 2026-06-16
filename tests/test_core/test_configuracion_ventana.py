"""
Tests de la reformulación del período (modo VENTANA) y del subtipo de gran
escala (S40, Fase 0 del modo industrial).

Cubre:
  - ModoAnalisis.VENTANA con sus validaciones de fechas
    (CONF_VENTANA_FECHAS_REQUERIDAS, CONF_VENTANA_ORDEN_INVALIDO,
    CONF_VENTANA_DEMASIADO_LARGA).
  - SubtipoGranEscala (BATCH por defecto, ambos válidos).
  - Back-compat: una Configuracion sin los campos nuevos usa defaults.
"""

from __future__ import annotations

from datetime import date

import pytest

from core.proyecto import (
    Configuracion,
    ModoAnalisis,
    SubtipoGranEscala,
    Tipologia,
)

# ---------------------------------------------------------------------------
# Modo VENTANA — validaciones de fechas
# ---------------------------------------------------------------------------


def test_ventana_valida_no_lanza():
    """Una ventana bien formada (fin > inicio, ≤ 366 días) es válida."""
    cfg = Configuracion(
        tipologia=Tipologia.GRAN_ESCALA,
        modo_analisis=ModoAnalisis.VENTANA,
        ventana_inicio=date(2020, 1, 1),
        ventana_fin=date(2020, 5, 31),
    )
    assert cfg.modo_analisis == ModoAnalisis.VENTANA
    assert (cfg.ventana_fin - cfg.ventana_inicio).days == 151


def test_conf_ventana_fechas_requeridas_sin_inicio():
    """Modo VENTANA sin ventana_inicio debe fallar."""
    with pytest.raises(ValueError, match="CONF_VENTANA_FECHAS_REQUERIDAS"):
        Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_fin=date(2020, 5, 31),
        )


def test_conf_ventana_fechas_requeridas_sin_fin():
    """Modo VENTANA sin ventana_fin debe fallar."""
    with pytest.raises(ValueError, match="CONF_VENTANA_FECHAS_REQUERIDAS"):
        Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_inicio=date(2020, 1, 1),
        )


def test_conf_ventana_orden_invalido():
    """ventana_fin anterior o igual a ventana_inicio debe fallar."""
    with pytest.raises(ValueError, match="CONF_VENTANA_ORDEN_INVALIDO"):
        Configuracion(
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_inicio=date(2020, 5, 31),
            ventana_fin=date(2020, 1, 1),
        )


def test_conf_ventana_orden_invalido_iguales():
    """ventana_fin == ventana_inicio debe fallar (lapso nulo)."""
    with pytest.raises(ValueError, match="CONF_VENTANA_ORDEN_INVALIDO"):
        Configuracion(
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_inicio=date(2020, 3, 15),
            ventana_fin=date(2020, 3, 15),
        )


def test_conf_ventana_demasiado_larga():
    """Un lapso de más de 366 días debe fallar."""
    with pytest.raises(ValueError, match="CONF_VENTANA_DEMASIADO_LARGA"):
        Configuracion(
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_inicio=date(2020, 1, 1),
            ventana_fin=date(2021, 6, 1),
        )


def test_ventana_un_anio_justo_es_valida():
    """Exactamente 366 días (año bisiesto) debe ser válido."""
    cfg = Configuracion(
        modo_analisis=ModoAnalisis.VENTANA,
        ventana_inicio=date(2020, 1, 1),
        ventana_fin=date(2020, 12, 31),
    )
    assert (cfg.ventana_fin - cfg.ventana_inicio).days == 365


# ---------------------------------------------------------------------------
# Subtipo de gran escala
# ---------------------------------------------------------------------------


def test_subtipo_default_es_batch():
    """El subtipo por defecto es BATCH."""
    cfg = Configuracion(tipologia=Tipologia.GRAN_ESCALA)
    assert cfg.subtipo_gran_escala == SubtipoGranEscala.BATCH


def test_subtipo_semicontinuo_valido():
    """SEMICONTINUO es un subtipo válido."""
    cfg = Configuracion(
        tipologia=Tipologia.GRAN_ESCALA,
        subtipo_gran_escala=SubtipoGranEscala.SEMICONTINUO,
    )
    assert cfg.subtipo_gran_escala == SubtipoGranEscala.SEMICONTINUO


# ---------------------------------------------------------------------------
# Back-compat: defaults sin los campos nuevos
# ---------------------------------------------------------------------------


def test_back_compat_defaults():
    """Una Configuracion sin los campos nuevos conserva los defaults previos
    y no lanza (snapshots viejos siguen deserializando)."""
    cfg = Configuracion()
    assert cfg.modo_analisis == ModoAnalisis.DIARIO
    assert cfg.subtipo_gran_escala == SubtipoGranEscala.BATCH
    assert cfg.ventana_inicio is None
    assert cfg.ventana_fin is None


def test_modos_diario_anual_no_requieren_ventana():
    """Los modos DIARIO/ANUAL no exigen fechas de ventana."""
    cfg_d = Configuracion(modo_analisis=ModoAnalisis.DIARIO)
    cfg_a = Configuracion(tipologia=Tipologia.GRAN_ESCALA, modo_analisis=ModoAnalisis.ANUAL)
    assert cfg_d.ventana_inicio is None
    assert cfg_a.ventana_fin is None
