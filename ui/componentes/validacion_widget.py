"""Widgets compartidos de validación contra datos medidos (mejora 38).

Helpers de presentación reusados por la validación del **colector** (P3, fase 2/3)
y la de **cámara/producto** (P4/P7, fase 4): tabla de métricas, overlay
medido-vs-simulado y curva de calibración. Son funciones puras que arman objetos
Plotly o listas de filas — no tocan ``st.session_state`` ni el proyecto, así que
se testean sin servidor.

Las etiquetas llegan ya traducidas desde la pestaña llamadora (estos helpers no
llaman a ``t()``), para que el mismo widget sirva a cualquier variable validada.
"""

from __future__ import annotations

import plotly.graph_objects as go

# Paleta consistente entre pestañas: medido = puntos rojos, simulado = línea azul.
_COLOR_MEDIDO = "#d62728"
_COLOR_SIMULADO = "#1f77b4"
_COLOR_OPTIMO = "#2ca02c"


def filas_metricas(metricas, unidad: str = "C") -> list[tuple[str, float, str]]:
    """Convierte ``MetricasAjuste`` en filas ``(id, valor, unidad)`` para la tabla.

    Args:
        metricas: ``calculos.metricas_validacion.MetricasAjuste``.
        unidad: Unidad de las métricas de diferencia (RMSE/MBE/MAE), que están en
            la unidad de la señal validada. Las adimensionales (R²/NSE/d) llevan
            ``""`` siempre.

    Returns:
        Lista de filas ``(id_metrica, valor, unidad)``.
    """
    return [
        ("rmse", metricas.rmse, unidad),
        ("mbe", metricas.mbe, unidad),
        ("mae", metricas.mae, unidad),
        ("r2", metricas.r2, ""),
        ("nse", metricas.nse, ""),
        ("d", metricas.d_willmott, ""),
    ]


def fig_overlay(ts, y_med, y_sim, *, medido_lbl, simulado_lbl, titulo, y_lbl):
    """Overlay medido (puntos) vs simulado (línea) sobre el mismo eje temporal.

    Args:
        ts: Timestamps de los pares alineados.
        y_med: Valores medidos, en unidad de display.
        y_sim: Valores simulados alineados, en unidad de display.
        medido_lbl, simulado_lbl: Rótulos de leyenda (ya traducidos).
        titulo, y_lbl: Título y rótulo del eje Y (ya traducidos).

    Returns:
        ``plotly.graph_objects.Figure``.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=y_med,
            mode="markers",
            name=medido_lbl,
            marker=dict(size=5, color=_COLOR_MEDIDO),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=y_sim,
            mode="lines",
            name=simulado_lbl,
            line=dict(color=_COLOR_SIMULADO, width=2),
        )
    )
    fig.update_layout(
        title=titulo,
        xaxis_title="",
        yaxis_title=y_lbl,
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def fig_curva_calibracion(res_cal, *, x_lbl, y_lbl, titulo, optimo_lbl):
    """Curva de la función objetivo vs el parámetro barrido, con marca en el óptimo.

    Args:
        res_cal: ``calculos.calibracion.ResultadoCalibracion``.
        x_lbl, y_lbl, titulo, optimo_lbl: Rótulos (ya traducidos).

    Returns:
        ``plotly.graph_objects.Figure``.
    """
    xs = [p.valor for p in res_cal.puntos if p.objetivo is not None]
    ys = [p.objetivo for p in res_cal.puntos if p.objetivo is not None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color=_COLOR_SIMULADO)))
    if res_cal.valor_optimo is not None and ys:
        fig.add_trace(
            go.Scatter(
                x=[res_cal.valor_optimo],
                y=[min(ys)],
                mode="markers",
                name=optimo_lbl,
                marker=dict(size=13, color=_COLOR_OPTIMO, symbol="star"),
            )
        )
    fig.update_layout(title=titulo, xaxis_title=x_lbl, yaxis_title=y_lbl, height=360)
    return fig


def fig_perfil_zonas(zonas, y_med, y_sim, *, medido_lbl, simulado_lbl, titulo, x_lbl, y_lbl):
    """Perfil espacial por zona del túnel: medido (puntos) vs simulado (línea).

    A diferencia de :func:`fig_overlay`, el eje X es **posición** (índice de zona,
    0 = producto fresco), no tiempo: es la foto instantánea del túnel contra los
    sensores de posición fija.

    Args:
        zonas: Índices de zona.
        y_med: Valores medidos por zona (``None`` donde no haya sensor).
        y_sim: Valores simulados por zona.
        medido_lbl, simulado_lbl, titulo, x_lbl, y_lbl: Rótulos (ya traducidos).

    Returns:
        ``plotly.graph_objects.Figure``.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(zonas),
            y=list(y_sim),
            mode="lines+markers",
            name=simulado_lbl,
            line=dict(color=_COLOR_SIMULADO, width=2),
        )
    )
    if y_med is not None:
        fig.add_trace(
            go.Scatter(
                x=list(zonas),
                y=list(y_med),
                mode="markers",
                name=medido_lbl,
                marker=dict(size=11, color=_COLOR_MEDIDO, symbol="diamond"),
            )
        )
    fig.update_layout(
        title=titulo,
        xaxis_title=x_lbl,
        yaxis_title=y_lbl,
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
