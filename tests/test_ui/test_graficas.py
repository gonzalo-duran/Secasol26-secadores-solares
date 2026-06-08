"""Tests del extractor de datos de figuras Plotly (ui/componentes/graficas.py, mejora 24)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from ui.componentes.graficas import _fig_a_dataframe


def test_trazas_mismo_x_formato_ancho():
    """Varias trazas con el mismo x → DataFrame ancho: columna x + una por traza."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1, 2], y=[10, 11, 12], name="T_amb"))
    fig.add_trace(go.Scatter(x=[0, 1, 2], y=[20, 21, 22], name="T_sal"))
    fig.update_xaxes(title_text="Tiempo [h]")

    df = _fig_a_dataframe(fig)
    assert list(df.columns) == ["Tiempo [h]", "T_amb", "T_sal"]
    assert df["Tiempo [h]"].tolist() == [0, 1, 2]
    assert df["T_amb"].tolist() == [10, 11, 12]
    assert df["T_sal"].tolist() == [20, 21, 22]


def test_trazas_x_distintos_formato_lado_a_lado():
    """Trazas con x distintos → columnas <name>_x/<name>_y con padding NaN."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1, 2], y=[1, 2, 3], name="perfil"))
    fig.add_trace(go.Scatter(x=[0, 5], y=[9, 8], name="salida"))

    df = _fig_a_dataframe(fig)
    assert set(df.columns) == {"perfil_x", "perfil_y", "salida_x", "salida_y"}
    assert len(df) == 3  # longitud máxima
    assert df["salida_x"].tolist()[:2] == [0, 5]
    assert np.isnan(df["salida_x"].tolist()[2])  # padding NaN


def test_mismo_x_con_y_de_distinto_largo_no_rompe():
    """Regresión: trazas con el mismo x pero y de distinto largo (perfiles del
    solver con paso adaptativo) — no debe lanzar; alinea cada y a len(x)."""
    x = [0.0, 0.5, 1.0, 1.5, 2.0]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[10, 11, 12, 13, 14], name="ene"))  # largo 5
    fig.add_trace(go.Scatter(x=x, y=[20, 21, 22], name="feb"))  # largo 3 (más corto)

    df = _fig_a_dataframe(fig)
    assert df is not None
    assert len(df) == len(x)  # alineado a la longitud de x
    assert df["ene"].tolist() == [10, 11, 12, 13, 14]
    # 'feb' se rellena con NaN hasta len(x)
    assert df["feb"].tolist()[:3] == [20, 21, 22]
    assert np.isnan(df["feb"].tolist()[3]) and np.isnan(df["feb"].tolist()[4])


def test_sin_datos_devuelve_none():
    """Figura sin trazas con x/y exportables → None."""
    fig = go.Figure()
    assert _fig_a_dataframe(fig) is None


def test_traza_sin_nombre_recibe_etiqueta_generica():
    """Una traza sin name obtiene una etiqueta 'serie_N'."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[3, 4]))  # sin name
    df = _fig_a_dataframe(fig)
    # mismo x (única traza) → formato ancho con columna 'serie_1'
    assert "serie_1" in df.columns
    assert df["serie_1"].tolist() == [3, 4]
