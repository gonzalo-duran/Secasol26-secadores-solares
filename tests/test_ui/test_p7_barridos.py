"""Tests de los helpers puros de la sección de barridos paramétricos de P7.

Solo cubren funciones sin Streamlit: paleta de color, conversión a DataFrame,
cotas UI y lectura del valor actual del parámetro.
"""

from __future__ import annotations

import pytest

from calculos.barrido_parametrico import BarridoConfig, PuntoBarrido, ResultadosBarrido
from calculos.catalogo_parametros_barrido import obtener_parametro
from core.camara import Camara, CargaProducto, ConfiguracionFlujo
from core.colector import Colector
from core.proyecto import Configuracion, Meta, ModoAnalisis, Proyecto, Tipologia
from ui.p7_resultados import (
    _barrido_a_dataframe,
    _bounds_ui_parametro,
    _paleta_color_barrido,
    _valor_actual_si_barrido,
)


def test_paleta_color_ciclica():
    assert _paleta_color_barrido(0) == "#1f77b4"
    assert _paleta_color_barrido(1) == "#d62728"
    assert _paleta_color_barrido(2) == "#2ca02c"
    # Cicla al exceder.
    assert _paleta_color_barrido(3) == _paleta_color_barrido(0)


def test_bounds_ui_identidad():
    """Para un parámetro con conversión identidad, las cotas UI = cotas SI."""
    p = obtener_parametro("caudal_masico")
    lo, hi = _bounds_ui_parametro(p)
    assert lo == pytest.approx(p.valor_min_si)
    assert hi == pytest.approx(p.valor_max_si)


def test_bounds_ui_acimut_no_degenera():
    """El muestreo evita el rango degenerado del acimut (±180 → mismo UI360)."""
    p = obtener_parametro("acimut_colector")
    lo, hi = _bounds_ui_parametro(p)
    assert hi > lo  # no colapsa a un punto


def _resultado_barrido_mock() -> ResultadosBarrido:
    meta = obtener_parametro("caudal_masico")
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.02, 0.04),
        modo="constantes",
        nombre="t",
    )
    puntos = (
        PuntoBarrido(0.02, 0.02, True, {"t_secado_h": 2.0, "cop_secado": 0.4}, None),
        PuntoBarrido(0.04, 0.04, False, {"t_secado_h": None, "cop_secado": None}, "boom"),
    )
    return ResultadosBarrido(cfg, meta, puntos, 1.0, "t", "2026-01-01T00:00:00")


def test_barrido_a_dataframe():
    df = _barrido_a_dataframe(_resultado_barrido_mock())
    assert len(df) == 2
    # Columna de valor con label + unidad.
    assert "Caudal másico de aire [kg/s]" in df.columns
    assert "t_secado_h" in df.columns
    assert "cop_secado" in df.columns
    assert "error" in df.columns
    # Valores.
    assert df.iloc[0]["t_secado_h"] == pytest.approx(2.0)
    assert df.iloc[1]["error"] == "boom"


def test_valor_actual_forzante_desde_condiciones():
    p = obtener_parametro("HR_camara")
    cond = {"HR_camara": 0.35, "T_amb_K": 300.0}
    assert _valor_actual_si_barrido(None, p, cond) == pytest.approx(0.35)
    p_t = obtener_parametro("T_amb")
    assert _valor_actual_si_barrido(None, p_t, cond) == pytest.approx(300.0)


def test_valor_actual_desde_proyecto():
    proyecto = Proyecto(
        meta=Meta(nombre="x", autor="y"),
        configuracion=Configuracion(tipologia=Tipologia.ARMARIO, modo_analisis=ModoAnalisis.DIARIO),
    )
    proyecto.colector = Colector()
    proyecto.camara = Camara(
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.042),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
    )
    p = obtener_parametro("caudal_masico")
    assert _valor_actual_si_barrido(proyecto, p, None) == pytest.approx(0.042)
