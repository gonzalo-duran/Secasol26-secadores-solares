"""Carta psicrométrica del proceso completo del secador — figura Plotly (mejora 27).

Capa UI: ensambla la figura interactiva a partir de la capa de cálculo pura
``calculos/carta_psicrometrica.py``. Dibuja:

- el fondo de la carta a la presión del emplazamiento (curva de saturación +
  familia de HR constante 10–90 %),
- la **poligonal del proceso** (ambiente → salida colector → entrada cámara →
  salida cámara) con marcadores y etiquetas,
- la **isentálpica de referencia** punteada desde la entrada de la cámara, para
  visualizar si el secado fue ≈ adiabático (cámara indirecta, el punto de salida
  cae sobre la línea) o no adiabático (cámara directa con techo translúcido, el
  punto de salida queda por encima).

Eje X = temperatura de bulbo seco [°C]; eje Y = humedad absoluta ω [g/kg].
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import plotly.graph_objects as go

from calculos.balance_global import presion_representativa_proyecto
from calculos.carta_psicrometrica import curvas_fondo, estados_proceso, isentalpica
from ui.componentes.idiomas import t

# Colores del proceso (coherentes con la paleta del proyecto).
_COLOR_SAT = "#1f77b4"
_COLOR_HR = "rgba(120,120,120,0.45)"
_COLOR_PROC = "#e05c2a"
_COLOR_ISENT = "rgba(76,175,80,0.8)"

# Interruptor de la carta (hotfix 1.4.1, 2026-11-09). La carta del proceso estaba dando
# resultados erróneos y se retira de producción antes de la presentación pública de
# Secasol en ASADES 2026. Con False, ``fig_carta_psicrometrica`` devuelve ``None`` y
# todos sus consumidores (P7 en los tres modos, figuras del PDF) la omiten sin aviso,
# porque ya tratan ``None`` como "no aplica". El cálculo (``calculos/carta_psicrometrica``)
# y sus tests no se tocan. Rehabilitar = poner True, una vez corregida la carta.
CARTA_HABILITADA = False


def fig_carta_psicrometrica(
    res: Any,
    proyecto: Any,
    *,
    omega_amb: Optional[float] = None,
) -> Optional[go.Figure]:
    """Construye la carta psicrométrica del proceso, o ``None`` si no aplica.

    Args:
        res: Resultado del balance global (Constantes o Transitorio).
        proyecto: Proyecto raíz (para la presión del emplazamiento).
        omega_amb: ω ambiente/entrada [kg/kg], requerida en modo Constantes.

    Returns:
        ``go.Figure`` o ``None`` (carta deshabilitada / modo Ventana / datos
        insuficientes).
    """
    if not CARTA_HABILITADA:
        return None
    try:
        P_Pa, _origen = presion_representativa_proyecto(proyecto)
    except Exception:
        P_Pa = 101325.0

    datos = estados_proceso(res, P_Pa=P_Pa, omega_amb=omega_amb)
    if datos is None:
        return None
    estados = datos["estados"]
    if not estados or len(estados) < 2:
        return None
    camara_directa = bool(datos["camara_directa"])

    # Rango de temperatura: cubre los estados con margen, acotado a [0, 90] °C.
    T_vals = [e.T_C for e in estados]
    T_min = max(0.0, min(T_vals) - 6.0)
    T_max = min(95.0, max(T_vals) + 8.0)
    if T_max <= T_min:
        T_max = T_min + 20.0

    fondo = curvas_fondo(T_min, T_max, P_Pa)
    T_C = fondo["T_C"]

    fig = go.Figure()

    # --- Curva de saturación (HR = 100 %) ---
    fig.add_trace(
        go.Scatter(
            x=T_C,
            y=fondo["omega_sat"] * 1000.0,
            mode="lines",
            name=t("graficas.carta.saturacion"),
            line=dict(color=_COLOR_SAT, width=2),
            hoverinfo="skip",
        )
    )

    # --- Familia de HR constante ---
    for hr, omega in fondo["hr"].items():
        y = omega * 1000.0
        fig.add_trace(
            go.Scatter(
                x=T_C,
                y=y,
                mode="lines",
                name=t("graficas.carta.hr", hr=int(hr * 100)),
                line=dict(color=_COLOR_HR, width=1),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        # Etiqueta de la curva en su extremo superior (último punto válido).
        idx_validos = np.where(np.isfinite(y))[0]
        if idx_validos.size:
            j = idx_validos[-1]
            fig.add_annotation(
                x=float(T_C[j]),
                y=float(y[j]),
                text=f"{int(hr * 100)}%",
                showarrow=False,
                font=dict(size=9, color="#888"),
                xanchor="left",
                yanchor="middle",
            )

    # --- Isentálpica de referencia desde la entrada de la cámara/túnel ---
    estado_in = estados[datos.get("idx_inlet", len(estados) - 2)]
    T_iso, w_iso = isentalpica(estado_in.h_J_kg, T_min, T_max, P_Pa)
    fig.add_trace(
        go.Scatter(
            x=T_iso,
            y=w_iso * 1000.0,
            mode="lines",
            name=t("graficas.carta.isentalpica"),
            line=dict(color=_COLOR_ISENT, width=1.4, dash="dot"),
            hoverinfo="skip",
        )
    )

    # --- Poligonal del proceso ---
    xs = [e.T_C for e in estados]
    ys = [e.omega_kg_kg * 1000.0 for e in estados]
    textos = [
        f"{e.nombre}<br>T = {e.T_C:.1f} °C<br>ω = {e.omega_kg_kg * 1000:.1f} g/kg<br>HR = {e.HR * 100:.0f} %"
        for e in estados
    ]
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines+markers+text",
            name=t("graficas.carta.proceso"),
            line=dict(color=_COLOR_PROC, width=2.5),
            marker=dict(size=10, color=_COLOR_PROC, line=dict(color="white", width=1)),
            text=[e.nombre for e in estados],
            textposition="top center",
            textfont=dict(size=10),
            customdata=textos,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )

    # --- Anotaciones de contexto ---
    nota_camara = (
        t("graficas.carta.nota_directa") if camara_directa else t("graficas.carta.nota_indirecta")
    )
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.01,
        y=0.99,
        text=t("graficas.carta.nota", p=P_Pa / 1000, camara=nota_camara),
        showarrow=False,
        align="left",
        font=dict(size=10, color="#555"),
        xanchor="left",
        yanchor="top",
    )

    fig.update_layout(
        title_text=t("graficas.carta.titulo"),
        xaxis_title=t("graficas.carta.eje_t"),
        yaxis_title=t("graficas.carta.eje_omega"),
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(rangemode="tozero")
    return fig
