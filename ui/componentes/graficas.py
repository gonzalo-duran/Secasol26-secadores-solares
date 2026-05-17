"""Gráficas reutilizables de la UI compartidas entre pestañas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go
from plotly.subplots import make_subplots

if TYPE_CHECKING:
    from calculos.camara_termodinamica import ResultadoMotorTermodinamico


def grafica_termodinamica_camara(
    res: "ResultadoMotorTermodinamico",
    X_obj: float,
    prod_id: str,
) -> go.Figure:
    """Tres paneles temporales del motor termodinámico de la cámara.

    Panel 1: humedad del producto X(t) con X_obj y t_secado.
    Panel 2: temperaturas del producto y del aire en cámara (eje dual).
    Panel 3: flujos de calor q_aire→producto y q_pérdida_pared.
    """
    t_h = res.t_array_s / 3600.0

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        specs=[[{}], [{"secondary_y": True}], [{}]],
        vertical_spacing=0.08,
    )

    # Panel 1: X(t)
    fig.add_trace(go.Scatter(
        x=list(t_h), y=list(res.X_prod_kg_kg), mode="lines",
        line=dict(color="#1f77b4", width=2), name="X(t)",
    ), row=1, col=1)
    fig.add_hline(y=X_obj, line=dict(color="red", dash="dot", width=1.5),
                  annotation_text=f"X_obj={X_obj:.3f}", row=1, col=1)
    if res.t_secado_s is not None:
        t_sec_h = res.t_secado_s / 3600.0
        fig.add_vline(x=t_sec_h, line=dict(color="orange", dash="dashdot", width=1.5),
                      annotation_text=f"t={t_sec_h:.1f}h", row=1, col=1)

    # Panel 2: T_prod (eje izq) y T_flujo (eje der)
    T_prod_C = res.T_prod_K - 273.15
    T_flujo_C = res.T_flujo_K - 273.15
    fig.add_trace(go.Scatter(
        x=list(t_h), y=list(T_prod_C), mode="lines",
        line=dict(color="#d62728", width=2), name="T producto [°C]",
    ), row=2, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(
        x=list(t_h), y=list(T_flujo_C), mode="lines",
        line=dict(color="#2ca02c", width=1.5, dash="dash"), name="T aire cámara [°C]",
    ), row=2, col=1, secondary_y=True)

    # Panel 3: flujos de calor
    fig.add_trace(go.Scatter(
        x=list(t_h), y=list(res.q_prod_W), mode="lines",
        line=dict(color="#ff7f0e", width=1.5), name="q aire→producto [W]",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=list(t_h), y=list(res.q_pared_W), mode="lines",
        line=dict(color="#9467bd", width=1.5), name="q pérdida pared [W]",
    ), row=3, col=1)

    fig.update_yaxes(title_text="X [kg agua / kg ms]", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="T producto [°C]", color="#d62728",
                     row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="T aire [°C]", color="#2ca02c",
                     row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Calor [W]", row=3, col=1)
    fig.update_xaxes(title_text="Tiempo [h]", row=3, col=1)
    fig.update_layout(
        title_text=f"Motor termodinámico — {prod_id} (status: {res.status})",
        height=700, showlegend=True,
    )
    return fig
