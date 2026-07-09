"""Gráficas reutilizables de la UI compartidas entre pestañas."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ui.componentes.idiomas import t

if TYPE_CHECKING:
    from calculos.camara_termodinamica import ResultadoMotorTermodinamico


# ---------------------------------------------------------------------------
# Render centralizado de figuras Plotly (mejoras 23 y 24)
# ---------------------------------------------------------------------------
# Config de la modebar de Plotly: siempre visible, sin logo, y descarga PNG en
# alta resolución. El botón de descarga corre en el NAVEGADOR, por lo que captura
# la vista interactiva del usuario (zoom, pan, rangos de ejes) — a diferencia de
# una exportación server-side (kaleido), que renderiza la figura original.
_PLOTLY_MODEBAR_REMOVE = ["lasso2d", "select2d"]

# Contador monótono para keys únicas de los botones de descarga. No usamos
# ``id(fig)``: CPython recicla direcciones de memoria de objetos liberados, así
# que dos figuras distintas creadas en un bucle (p. ej. una por KPI en los
# barridos) pueden compartir id y colisionar la key. El contador garantiza
# unicidad dentro de cada corrida del script; los download_button no guardan
# estado persistente, por lo que que la key cambie entre reruns es inocuo.
_dl_key_counter = itertools.count()


def _fig_a_dataframe(fig: go.Figure) -> pd.DataFrame | None:
    """Extrae los datos numéricos de una figura Plotly a un DataFrame (mejora 24).

    - Si todas las trazas comparten el mismo ``x`` (caso típico de series con
      varias ``y``), devuelve un DataFrame ancho: columna ``x`` + una columna por
      traza (nombrada con ``trace.name``).
    - Si los ``x`` difieren entre trazas, devuelve columnas lado a lado
      ``"<name>_x"`` / ``"<name>_y"`` rellenando con NaN hasta la longitud máxima.
    - Ignora trazas sin ``x``/``y``; devuelve ``None`` si no hay nada exportable.
    """

    def _ajustar(seq: list, n: int) -> list:
        """Trunca o rellena con NaN para dejar la secuencia de longitud n."""
        return list(seq)[:n] + [np.nan] * max(0, n - len(seq))

    try:
        trazas = []
        for i, tr in enumerate(fig.data):
            x = getattr(tr, "x", None)
            y = getattr(tr, "y", None)
            if x is None or y is None:
                continue
            x = list(x)
            y = list(y)
            if len(x) == 0 or len(y) == 0:
                continue
            nombre_tr = getattr(tr, "name", None) or f"serie_{i + 1}"
            trazas.append((nombre_tr, x, y))

        if not trazas:
            return None

        # ¿Todas las trazas comparten el mismo eje x (mismo largo y valores)?
        x0 = trazas[0][1]
        mismo_x = all(len(x) == len(x0) and list(x) == list(x0) for _, x, _ in trazas)

        if mismo_x:
            # Caso típico: x compartido. Cada y se alinea a len(x0) (las trazas
            # pueden tener y de distinto largo que x — p. ej. perfiles del solver
            # con paso adaptativo; Plotly las grafica contra el mismo x).
            n = len(x0)
            x_label = "x"
            try:
                t = fig.layout.xaxis.title.text
                if t:
                    x_label = str(t)
            except AttributeError:
                pass
            cols: dict[str, list] = {x_label: list(x0)}
            usados: dict[str, int] = {}
            for nombre_tr, _, y in trazas:
                col = nombre_tr
                if col in cols or col == x_label:
                    usados[col] = usados.get(col, 1) + 1
                    col = f"{col}_{usados[col]}"
                cols[col] = _ajustar(y, n)
            return pd.DataFrame(cols)

        # x distintos: columnas lado a lado, todo padded a la longitud máxima.
        n_max = max(max(len(x), len(y)) for _, x, y in trazas)
        cols = {}
        for j, (nombre_tr, x, y) in enumerate(trazas):
            base = nombre_tr if nombre_tr else f"serie_{j + 1}"
            cols[f"{base}_x"] = _ajustar(x, n_max)
            cols[f"{base}_y"] = _ajustar(y, n_max)
        return pd.DataFrame(cols)
    except Exception:
        # La exportación de datos es opcional: nunca debe romper el render.
        return None


def mostrar_plotly(fig: go.Figure, *, nombre: str = "grafico", **kwargs) -> None:
    """Renderiza una figura Plotly con modebar siempre visible, descarga PNG y CSV.

    - Imagen (mejora 23): modebar siempre visible + botón de descarga PNG ×2 que
      captura la vista interactiva del usuario (lado navegador).
    - Datos (mejora 24): botón "Datos (CSV)" con la serie numérica detrás del
      gráfico, extraída server-side de ``fig.data``.

    Args:
        fig: Figura Plotly a mostrar.
        nombre: Sufijo de los nombres de archivo (``secasol_<nombre>.png/.csv``).
        **kwargs: Se reenvían a ``st.plotly_chart`` (p. ej. ``key=``).
    """
    config = {
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": _PLOTLY_MODEBAR_REMOVE,
        "toImageButtonOptions": {
            "format": "png",
            "scale": 2,
            "filename": f"secasol_{nombre}",
        },
    }
    st.plotly_chart(fig, width="stretch", config=config, **kwargs)

    # Descarga de los datos numéricos del gráfico (mejora 24).
    df = _fig_a_dataframe(fig)
    if df is not None:
        _, col_dl = st.columns([3, 1])
        col_dl.download_button(
            "⬇ Datos (CSV)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"secasol_{nombre}.csv",
            mime="text/csv",
            key=f"dl_{nombre}_{next(_dl_key_counter)}",
        )


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
        rows=3,
        cols=1,
        shared_xaxes=True,
        specs=[[{}], [{"secondary_y": True}], [{}]],
        vertical_spacing=0.08,
    )

    # Panel 1: X(t)
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.X_prod_kg_kg),
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name=t("graficas.termo.curva_x"),
        ),
        row=1,
        col=1,
    )
    fig.add_hline(
        y=X_obj,
        line=dict(color="red", dash="dot", width=1.5),
        annotation_text=t("graficas.termo.x_obj", v=X_obj),
        row=1,
        col=1,
    )
    if res.t_secado_s is not None:
        t_sec_h = res.t_secado_s / 3600.0
        fig.add_vline(
            x=t_sec_h,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=t("graficas.termo.t_marca", v=t_sec_h),
            row=1,
            col=1,
        )

    # Panel 2: T_prod (eje izq) y T_flujo (eje der)
    T_prod_C = res.T_prod_K - 273.15
    T_flujo_C = res.T_flujo_K - 273.15
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(T_prod_C),
            mode="lines",
            line=dict(color="#d62728", width=2),
            name=t("graficas.termo.t_producto"),
        ),
        row=2,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(T_flujo_C),
            mode="lines",
            line=dict(color="#2ca02c", width=1.5, dash="dash"),
            name=t("graficas.termo.t_aire_camara"),
        ),
        row=2,
        col=1,
        secondary_y=True,
    )

    # Panel 3: flujos de calor
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.q_prod_W),
            mode="lines",
            line=dict(color="#ff7f0e", width=1.5),
            name=t("graficas.termo.q_prod"),
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.q_pared_W),
            mode="lines",
            line=dict(color="#9467bd", width=1.5),
            name=t("graficas.termo.q_pared"),
        ),
        row=3,
        col=1,
    )

    fig.update_yaxes(title_text=t("graficas.termo.eje_x"), rangemode="tozero", row=1, col=1)
    fig.update_yaxes(
        title_text=t("graficas.termo.eje_t_prod"), color="#d62728", row=2, col=1, secondary_y=False
    )
    fig.update_yaxes(
        title_text=t("graficas.termo.eje_t_aire"), color="#2ca02c", row=2, col=1, secondary_y=True
    )
    fig.update_yaxes(title_text=t("graficas.termo.eje_calor"), row=3, col=1)
    fig.update_xaxes(title_text=t("graficas.termo.eje_tiempo"), row=3, col=1)
    fig.update_layout(
        title_text=t("graficas.termo.titulo", prod=prod_id, status=res.status),
        height=700,
        showlegend=True,
    )
    return fig
