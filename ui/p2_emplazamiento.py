"""
Pestaña 2 — Emplazamiento y Recursos Climáticos.

Permite al usuario configurar la ubicación y orientación del colector,
descargar datos horarios de NASA POWER y visualizar el recurso solar/climático.

Convención de ángulos en la UI: Duffie (acimut 0° = Sur).
Las conversiones a pvlib ocurren en ui/componentes/unidades.py, nunca aquí.
"""

from __future__ import annotations

import dataclasses
import io
from typing import Callable

import pandas as pd
import plotly.graph_objects as go
import pvlib
import streamlit as st
from plotly.subplots import make_subplots

from calculos import clima_medido as cm
from calculos.clima_calc import obtener_clima
from core.clima import ANIO_NASA_MAX, ANIO_NASA_MIN, Clima
from core.clima_medido import (
    CONVENCIONES_TIMESTAMP,
    PLANOS_PIRANOMETRO,
    UNIDADES_POR_VARIABLE,
    VARIABLES_MAPEABLES,
    ConfigMapeoClima,
    MapeoColumna,
)
from core.emplazamiento import Emplazamiento
from core.proyecto import DiaAnalisis, ModoAnalisis, Tipologia
from ui.componentes.graficas import mostrar_plotly
from ui.componentes.idiomas import t
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual
from ui.componentes.serializacion import (
    dump_json,
    limpiar_session_state_prefijo,
    nombre_archivo_descarga,
    parsear_json_seccion,
)
from ui.componentes.unidades import (
    acimut_duffie_a_pvlib,
    acimut_duffie_a_ui360,
    acimut_ui360_a_duffie,
)

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ZONAS_HORARIAS = [
    "America/Argentina/Salta",
    "America/Argentina/Buenos_Aires",
    "America/Argentina/Cordoba",
    "America/Argentina/Mendoza",
    "America/Argentina/Tucuman",
    "America/Argentina/Jujuy",
    "America/Argentina/San_Juan",
    "America/Santiago",
    "America/La_Paz",
    "America/Lima",
    "America/Bogota",
    "America/Caracas",
    "America/Asuncion",
    "America/Montevideo",
    "America/Sao_Paulo",
    "America/Mexico_City",
    "America/New_York",
    "Europe/Madrid",
    "UTC",
]

_ANIO_MIN = ANIO_NASA_MIN
_ANIO_MAX = ANIO_NASA_MAX
_ANIO_DEFAULT = 2022


def _resolver_anio_descarga(
    *,
    anio_p1: int | None,
    anio_descarga_actual: int | None,
    ultimo_anio_p1_visto: int | None,
) -> tuple[int, int | None]:
    """Resuelve el año de descarga de P2 y el 'último año P1 visto' (mejora 28).

    Lógica de sincronización P1→P2 robusta a la purga de widget-keys al navegar:

    * Si ``anio_descarga_actual`` es ``None`` (primer ingreso o key purgada),
      siembra desde la ventana/fecha de P1 (``anio_p1``) si existe; si P1 no
      fijó fecha, cae al default. Antes caía SIEMPRE al default (2022), rompiendo
      el vínculo ventana→año.
    * Si P1 cambió de año respecto al último sincronizado, re-sincroniza.
    * En caso contrario respeta el valor actual (override manual del usuario).

    Args:
        anio_p1: Año de la ventana/fecha de P1 (None si P1 no fijó fecha).
        anio_descarga_actual: Valor actual de ``p2_anio_descarga`` (None si la
            key fue purgada o es el primer ingreso).
        ultimo_anio_p1_visto: Último ``anio_p1`` sincronizado (plain key).

    Returns:
        Tupla ``(anio_descarga, ultimo_anio_p1_visto)`` actualizada.
    """
    if anio_descarga_actual is None:
        return (anio_p1 if anio_p1 is not None else _ANIO_DEFAULT), anio_p1
    if anio_p1 is not None and anio_p1 != ultimo_anio_p1_visto:
        return anio_p1, anio_p1
    return anio_descarga_actual, ultimo_anio_p1_visto


# ---------------------------------------------------------------------------
# Helpers internos de visualización
# ---------------------------------------------------------------------------


def _resumen_mensual(datos_local: pd.DataFrame) -> pd.DataFrame:
    """Agrega datos horarios en estadísticas mensuales para visualización.

    Args:
        datos_local: DataFrame SI con índice en zona horaria local.

    Returns:
        DataFrame con estadísticas mensuales en unidades de UI.
    """
    T_C = datos_local["T_amb_K"] - 273.15
    pres_hPa = datos_local["presion_Pa"] / 100.0
    HR_pct = datos_local["HR"] * 100.0

    t_mes = T_C.resample("ME").agg(["mean", "min", "max"])
    ghi_mes_kWh = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_mes_kWh = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_mes_kWh = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    ws_mes = datos_local["WS_ms"].resample("ME").mean()
    hr_mes = HR_pct.resample("ME").mean()
    p_mes = pres_hPa.resample("ME").mean()

    _MES_ABBR = t("graficas.meses_abbr").split(",")
    nombres_mes = [_MES_ABBR[ts.month - 1] for ts in t_mes.index]

    df = pd.DataFrame(
        {
            t("p2.tabla.mes"): nombres_mes,
            t("p2.tabla.t_prom"): t_mes["mean"].round(1).values,
            t("p2.tabla.t_min"): t_mes["min"].round(1).values,
            t("p2.tabla.t_max"): t_mes["max"].round(1).values,
            t("p2.tabla.ghi"): ghi_mes_kWh.round(1).values,
            t("p2.tabla.dni"): dni_mes_kWh.round(1).values,
            t("p2.tabla.dhi"): dhi_mes_kWh.round(1).values,
            t("p2.tabla.viento"): ws_mes.round(1).values,
            t("p2.tabla.hr"): hr_mes.round(1).values,
            t("p2.tabla.presion"): p_mes.round(1).values,
        }
    )
    return df


def _fig_temperatura(datos_local: pd.DataFrame) -> go.Figure:
    """Temperatura media diaria y promedio mensual — figura interactiva Plotly."""
    T_C = datos_local["T_amb_K"] - 273.15
    T_diaria = T_C.resample("D").mean()
    T_mensual = T_C.resample("ME").mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=T_diaria.index,
            y=T_diaria.values,
            mode="lines",
            name=t("graficas.serie.media_diaria"),
            line=dict(color="#aec6e8", width=0.8),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=T_mensual.index,
            y=T_mensual.values,
            mode="lines+markers",
            name=t("graficas.serie.media_mensual"),
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        yaxis_title=t("graficas.eje.temperatura_c"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
    )
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    return fig


def _fig_irradiancia(datos_local: pd.DataFrame) -> go.Figure:
    """Irradiación mensual GHI/DNI/DHI — figura interactiva Plotly."""
    _MES_ABBR = t("graficas.meses_abbr").split(",")

    ghi_s = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_s = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_s = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ghi_s.index]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(name="GHI", x=etiquetas, y=ghi_s.values, marker_color="#f5a623", opacity=0.85)
    )
    fig.add_trace(
        go.Bar(name="DHI", x=etiquetas, y=dhi_s.values, marker_color="#7ec8e3", opacity=0.85)
    )
    fig.add_trace(
        go.Bar(name="DNI", x=etiquetas, y=dni_s.values, marker_color="#e05c2a", opacity=0.85)
    )
    fig.update_layout(
        barmode="stack",
        yaxis_title=t("graficas.eje.irradiacion_mensual"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
    )
    fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    return fig


def _fig_viento_hr(datos_local: pd.DataFrame) -> go.Figure:
    """Velocidad del viento y HR mensuales — eje Y secundario nativo Plotly."""
    _MES_ABBR = t("graficas.meses_abbr").split(",")

    ws_s = datos_local["WS_ms"].resample("ME").mean()
    hr_s = (datos_local["HR"] * 100.0).resample("ME").mean()
    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ws_s.index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            name=t("graficas.serie.viento_ms"),
            x=etiquetas,
            y=ws_s.values,
            marker_color="#4caf50",
            opacity=0.7,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            name=t("graficas.serie.hr_pct"),
            x=etiquetas,
            y=hr_s.values,
            mode="lines+markers",
            line=dict(color="#9c27b0", width=2.5),
            marker=dict(size=6),
        ),
        secondary_y=True,
    )
    fig.update_yaxes(
        title_text=t("graficas.eje.viento_ms"),
        title_font_color="#4caf50",
        secondary_y=False,
        showgrid=True,
        gridwidth=0.5,
        gridcolor="lightgray",
    )
    fig.update_yaxes(
        title_text=t("graficas.eje.hr_pct"), title_font_color="#9c27b0", secondary_y=True
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=320,
        margin=dict(l=60, r=60, t=30, b=40),
    )
    return fig


def _calcular_poa_horaria(
    datos_local: pd.DataFrame,
    lat: float,
    lon: float,
    altitud_m: float,
    pendiente_deg: float,
    acimut_pvlib_deg: float,
    albedo: float = 0.25,
) -> pd.Series:
    """Calcula la irradiancia global sobre el plano del colector (POA) hora a hora.

    Usa pvlib para la posición solar y la transposición. La componente reflejada
    del suelo usa ``albedo`` (debe pasarse ``emplazamiento.albedo_suelo`` para que
    la figura sea coherente con el solver del colector, que usa ese mismo albedo).

    Args:
        datos_local: DataFrame SI con índice tz-aware (hora local).
        lat: Latitud [°].
        lon: Longitud [°].
        altitud_m: Altitud [m].
        pendiente_deg: Inclinación del colector [°].
        acimut_pvlib_deg: Acimut del colector en convención pvlib [°].
        albedo: Reflectancia solar del suelo [adim]. Default 0.25.

    Returns:
        Serie de POA global [W/m²], misma frecuencia que datos_local.
    """
    solar_pos = pvlib.solarposition.get_solarposition(
        datos_local.index, lat, lon, altitude=altitud_m
    )
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=pendiente_deg,
        surface_azimuth=acimut_pvlib_deg,
        solar_zenith=solar_pos["apparent_zenith"],
        solar_azimuth=solar_pos["azimuth"],
        dni=datos_local["DNI_Wm2"],
        ghi=datos_local["GHI_Wm2"],
        dhi=datos_local["DHI_Wm2"],
        albedo=albedo,
    )
    return poa["poa_global"].clip(lower=0).fillna(0.0)


def _fig_irradiancia_comparativa(
    datos_local: pd.DataFrame,
    poa_horaria: pd.Series,
) -> go.Figure:
    """Dos subgráficos: plano horizontal (GHI/DNI/DHI) y plano del colector (POA)."""
    _MES_ABBR = t("graficas.meses_abbr").split(",")

    ghi_s = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_s = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_s = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    poa_s = poa_horaria.resample("ME").sum() / 1000.0
    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ghi_s.index]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=[
            t("graficas.subplot.plano_horizontal"),
            t("graficas.subplot.plano_colector"),
        ],
    )
    fig.add_trace(
        go.Bar(name="GHI", x=etiquetas, y=ghi_s.values, marker_color="#f5a623", opacity=0.85),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(name="DHI", x=etiquetas, y=dhi_s.values, marker_color="#7ec8e3", opacity=0.85),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(name="DNI", x=etiquetas, y=dni_s.values, marker_color="#e05c2a", opacity=0.85),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            name=t("graficas.serie.poa_global"),
            x=etiquetas,
            y=poa_s.values,
            marker_color="#4caf50",
            opacity=0.85,
            showlegend=True,
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=560,
        margin=dict(l=60, r=20, t=60, b=40),
    )
    fig.update_yaxes(title_text="kWh/m²", showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    return fig


def _fecha_dia_analisis(datos_local: pd.DataFrame, cfg, anio: int):
    """Resuelve la fecha concreta del día de diseño según cfg.dia_analisis."""
    from datetime import date

    if cfg.dia_analisis == DiaAnalisis.ESPECIFICO and cfg.fecha_especifica:
        return cfg.fecha_especifica
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_VERANO:
        return date(anio, 12, 21)
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_INVIERNO:
        return date(anio, 6, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_MARZO:
        return date(anio, 3, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_SEPTIEMBRE:
        return date(anio, 9, 21)
    elif cfg.dia_analisis == DiaAnalisis.MAS_CALUROSO:
        return (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmax().date()
    else:  # MAS_FRIO
        return (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmin().date()


def _eje_x_temporal(indice: pd.DatetimeIndex):
    """Eje X para los perfiles horarios (mejora 30).

    Si el rango abarca un solo día devuelve etiquetas categóricas ``HH:MM``
    (día de diseño). Si abarca varios días (ventana de producción) devuelve el
    índice datetime completo, para que Plotly grafique sobre el dominio temporal
    real en vez de encimar todos los días sobre 24 h.
    """
    if indice.normalize().nunique() > 1:
        return indice
    return [t.strftime("%H:%M") for t in indice]


def _fig_temperatura_diaria(datos_dia: pd.DataFrame) -> go.Figure:
    """Perfil horario de temperatura ambiente para el día/ventana de diseño."""
    T_C = datos_dia["T_amb_K"] - 273.15
    horas_str = _eje_x_temporal(datos_dia.index)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=T_C.values,
            mode="lines+markers",
            name=t("graficas.serie.t_amb"),
            line=dict(color="#1f77b4", width=2.0),
            marker=dict(size=5),
            hovertemplate="%{x} — %{y:.1f} °C<extra></extra>",
        )
    )
    fig.update_layout(
        yaxis_title=t("graficas.eje.temperatura_c"),
        hovermode="x unified",
        height=300,
        margin=dict(l=50, r=20, t=20, b=40),
    )
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    fig.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    return fig


def _fig_irradiancia_diaria(datos_dia: pd.DataFrame, poa_dia: pd.Series) -> go.Figure:
    """Dos subgráficos horarios: plano horizontal y plano del colector."""
    horas_str = _eje_x_temporal(datos_dia.index)
    horas_poa = _eje_x_temporal(poa_dia.index)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=[
            t("graficas.subplot.plano_horizontal"),
            t("graficas.subplot.plano_colector"),
        ],
    )

    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=datos_dia["GHI_Wm2"].values,
            fill="tozeroy",
            fillcolor="rgba(245,166,35,0.35)",
            line=dict(color="#f5a623"),
            name="GHI",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=datos_dia["DNI_Wm2"].values,
            mode="lines",
            line=dict(color="#e05c2a", width=1.6),
            name="DNI",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=datos_dia["DHI_Wm2"].values,
            mode="lines",
            line=dict(color="#7ec8e3", width=1.6),
            name="DHI",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=horas_poa,
            y=poa_dia.values,
            fill="tozeroy",
            fillcolor="rgba(76,175,80,0.35)",
            line=dict(color="#4caf50"),
            name=t("graficas.serie.poa"),
        ),
        row=2,
        col=1,
    )

    fig.update_yaxes(title_text="W/m²", showgrid=True, gridwidth=0.5, gridcolor="lightgray")
    fig.update_layout(
        hovermode="x unified",
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=60, b=40),
    )
    return fig


def _fig_viento_hr_diaria(datos_dia: pd.DataFrame) -> go.Figure:
    """Perfil horario de velocidad del viento y HR — eje Y secundario nativo Plotly."""
    horas_str = _eje_x_temporal(datos_dia.index)
    ws = datos_dia["WS_ms"].values
    hr_pct = datos_dia["HR"].values * 100.0

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=ws,
            mode="lines+markers",
            name=t("graficas.serie.viento_ms"),
            line=dict(color="#4caf50", width=2.0),
            marker=dict(size=5),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=horas_str,
            y=hr_pct,
            mode="lines+markers",
            name=t("graficas.serie.hr_pct"),
            line=dict(color="#9c27b0", width=2.0),
            marker=dict(size=5, symbol="square"),
        ),
        secondary_y=True,
    )
    fig.update_yaxes(
        title_text=t("graficas.eje.viento_ms"),
        title_font_color="#4caf50",
        showgrid=True,
        gridwidth=0.5,
        gridcolor="lightgray",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text=t("graficas.eje.hr_pct"), title_font_color="#9c27b0", secondary_y=True
    )
    fig.update_layout(
        hovermode="x unified",
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=30, b=40),
    )
    return fig


def _generar_csv(datos: pd.DataFrame, zona_horaria: str) -> bytes:
    """Genera un CSV con los datos en unidades de UI (no SI).

    Args:
        datos: DataFrame SI con índice UTC tz-aware.
        zona_horaria: Identificador IANA para convertir el índice.

    Returns:
        Bytes del archivo CSV codificado en UTF-8.
    """
    export = datos.tz_convert(zona_horaria).copy()
    export.index.name = t("p2.csv.indice")
    export["T_amb_C"] = export["T_amb_K"] - 273.15
    export["HR_pct"] = export["HR"] * 100.0
    export["presion_hPa"] = export["presion_Pa"] / 100.0

    columnas_csv = {
        "T_amb_C": t("p2.csv.t_amb"),
        "GHI_Wm2": t("p2.csv.ghi"),
        "DNI_Wm2": t("p2.csv.dni"),
        "DHI_Wm2": t("p2.csv.dhi"),
        "WS_ms": t("p2.csv.viento"),
        "HR_pct": t("p2.csv.hr"),
        "presion_hPa": t("p2.csv.presion"),
    }
    df_out = export[list(columnas_csv.keys())].rename(columns=columnas_csv)
    buf = io.StringIO()
    df_out.to_csv(buf, encoding="utf-8")
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Clima medido por el usuario (mejora 38, F1a)
# ---------------------------------------------------------------------------


def _construir_config_medido(
    columna_timestamp: str,
    seleccion: dict,
    zona_horaria: str,
    convencion: str,
    altura_anemometro_m: float,
    plano_piranometro: str,
    hoja: str | None,
    fila_encabezado: int,
    fecha_fija=None,
) -> ConfigMapeoClima:
    """Arma la ConfigMapeoClima desde los valores de los widgets (pura, testeable).

    Args:
        seleccion: variable canónica → (columna_origen | None, unidad).
        fecha_fija: fecha del ensayo si la columna de timestamp trae solo la hora.
    """
    columnas = [
        MapeoColumna(variable, col, unidad)
        for variable, (col, unidad) in seleccion.items()
        if col is not None
    ]
    return ConfigMapeoClima(
        columna_timestamp=columna_timestamp,
        zona_horaria=zona_horaria,
        convencion_timestamp=convencion,
        columnas=columnas,
        hoja=hoja,
        fila_encabezado=fila_encabezado,
        altura_anemometro_m=altura_anemometro_m,
        plano_piranometro=plano_piranometro,
        fecha_fija=fecha_fija,
    )


def _tabla_procedencia(clima: Clima, traducir_fn: Callable[..., str]) -> pd.DataFrame:
    """Tabla variable → procedencia traducida, para mostrar antes de confirmar."""
    filas = []
    for col, proc in (clima.procedencia or {}).items():
        filas.append(
            {
                traducir_fn("p2.medido.procedencia.variable"): traducir_fn(
                    f"p2.medido.variable.{col}"
                ),
                traducir_fn("p2.medido.procedencia.origen"): traducir_fn(
                    f"p2.medido.procedencia.{proc}"
                ),
            }
        )
    return pd.DataFrame(filas)


def _resumen_medido_dict(clima: Clima) -> dict:
    """Resumen compacto del clima medido confirmado (puro, testeable)."""
    qc = clima.qc
    return {
        "fuente": clima.fuente,
        "anio": clima.anio,
        "paso_s": clima.frecuencia_nativa_s,
        "periodo_inicio": qc.periodo_inicio if qc is not None else None,
        "periodo_fin": qc.periodo_fin if qc is not None else None,
        "meses": tuple(qc.meses_cubiertos) if qc is not None else (),
    }


def _limpiar_estado_medido() -> None:
    limpiar_session_state_prefijo(st.session_state, "p2_med_")
    limpiar_session_state_prefijo(st.session_state, "_p2_med_")


def _render_snapshot_medido(proyecto) -> None:
    """Expander guardar/cargar la configuración de ingesta (sección clima_medido)."""
    clima = proyecto.clima
    with st.expander(t("p2.medido.snapshot.titulo"), expanded=False):
        snap = st.session_state.get("p2med_snapshot")
        if snap is None and clima is not None and getattr(clima, "mapeo", None) is not None:
            snap = {
                "seccion": "clima_medido",
                "nombre_archivo": None,
                "hash_archivo": None,
                "hash_ingesta": None,
                "mapeo": cm.config_a_dict(clima.mapeo),
            }
        if snap is not None:
            st.download_button(
                t("p2.medido.snapshot.guardar"),
                data=dump_json(snap),
                file_name=nombre_archivo_descarga(proyecto, "clima_medido", "json"),
                mime="application/json",
                key="p2_med_snap_dl",
            )
        archivo = st.file_uploader(
            t("p2.medido.snapshot.cargar"), type=["json"], key="p2_med_snap_uploader"
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "clima_medido")
            if err:
                st.error(t("p2.medido.snapshot.error", err=err))
            else:
                hash_ing = data.get("hash_ingesta")
                rec = cm.cargar_cache_medido(hash_ing) if hash_ing else None
                if rec is not None:
                    proyecto.clima = rec
                    _limpiar_estado_medido()
                    st.session_state.pop("p2_med_snap_uploader", None)
                    st.success(t("p2.medido.snapshot.restaurado"))
                    st.rerun()
                else:
                    st.info(t("p2.medido.snapshot.falta_archivo"))


def _render_clima_medido(proyecto, empl: Emplazamiento) -> None:
    """Sección de carga de datos climáticos medidos (CSV/XLS) en P2."""
    st.caption(t("p2.medido.intro"))

    clima_conf = proyecto.clima
    hay_confirmado = (
        clima_conf is not None
        and clima_conf.datos is not None
        and getattr(clima_conf, "fuente", "nasa_power") != "nasa_power"
    )
    if hay_confirmado and st.session_state.get("p2_med_archivo") is None:
        resumen = _resumen_medido_dict(clima_conf)
        st.success(
            t(
                "p2.medido.resumen.confirmado",
                fuente=(
                    t(f"p2.fuente.{resumen['fuente']}")
                    if resumen["fuente"] in ("medido",)
                    else t("p2.medido.resumen.hibrido")
                ),
                inicio=str(resumen["periodo_inicio"] or "—")[:16],
                fin=str(resumen["periodo_fin"] or "—")[:16],
                paso=int(resumen["paso_s"] or 0),
                n_meses=len(resumen["meses"]),
            )
        )
        tabla_proc = _tabla_procedencia(clima_conf, t)
        if len(tabla_proc) > 0:
            st.dataframe(tabla_proc, hide_index=True)
        _render_snapshot_medido(proyecto)

    arch = st.session_state.get("p2_med_archivo")
    if arch is None:
        subido = st.file_uploader(
            t("p2.medido.uploader.label"),
            type=["csv", "txt", "xls", "xlsx"],
            key="p2_med_uploader",
            help=t("p2.medido.uploader.help"),
        )
        if subido is not None:
            contenido = subido.read()
            st.session_state["p2_med_archivo"] = {
                "nombre": subido.name,
                "bytes": contenido,
                "hash": cm.hash_archivo(contenido),
            }
            st.session_state.pop("p2_med_uploader", None)
            st.rerun()
        if not hay_confirmado:
            _render_snapshot_medido(proyecto)
        return

    c_a, c_b = st.columns([4, 1])
    with c_a:
        st.markdown(
            t(
                "p2.medido.archivo_cargado",
                nombre=arch["nombre"],
                kb=max(len(arch["bytes"]) // 1024, 1),
            )
        )
    with c_b:
        if st.button(t("p2.medido.quitar"), key="p2_med_quitar"):
            _limpiar_estado_medido()
            st.rerun()

    # ---- hoja / fila de encabezado (solo Excel) ----
    try:
        hojas = cm.listar_hojas(arch["bytes"], arch["nombre"])
    except (ValueError, RuntimeError) as exc:
        st.error(t("p2.medido.error", err=exc))
        return
    except Exception as exc:  # archivo arbitrario del usuario: nunca traceback crudo
        st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
        return
    hoja = None
    c1, c2 = st.columns([3, 1])
    if hojas:
        with c1:
            hoja = st.selectbox(t("p2.medido.hoja.label"), options=hojas, key="p2_med_hoja")
    with c2:
        fila_enc = int(
            st.number_input(
                t("p2.medido.fila_enc.label"),
                min_value=0,
                max_value=50,
                value=0,
                key="p2_med_fila_enc",
                help=t("p2.medido.fila_enc.help"),
            )
        )

    # ---- tabla cruda cacheada por (hash, hoja, fila) ----
    clave_tabla = (arch["hash"], hoja, fila_enc)
    cache = st.session_state.get("_p2_med_tabla_cache")
    if cache is None or cache[0] != clave_tabla:
        try:
            tabla = cm.leer_tabla(
                arch["bytes"], arch["nombre"], hoja=hoja, fila_encabezado=fila_enc
            )
        except (ValueError, RuntimeError) as exc:
            st.error(t("p2.medido.error", err=exc))
            return
        except Exception as exc:  # archivo arbitrario del usuario
            st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
            return
        st.session_state["_p2_med_tabla_cache"] = (clave_tabla, tabla)
        st.session_state["_p2_med_sugerencia"] = cm.sugerir_mapeo(tabla.columns)
        limpiar_session_state_prefijo(st.session_state, "p2_med_col_")
        limpiar_session_state_prefijo(st.session_state, "p2_med_uni_")
        st.session_state.pop("p2_med_resultado", None)
    tabla = st.session_state["_p2_med_tabla_cache"][1]
    sugerencia = st.session_state["_p2_med_sugerencia"]

    with st.expander(t("p2.medido.preview_titulo"), expanded=False):
        st.dataframe(tabla.head(12))

    # ---- mapeo de columnas ----
    st.markdown(t("p2.medido.mapeo.titulo"))
    st.caption(t("p2.medido.mapeo.caption"))
    columnas_archivo = [str(c) for c in tabla.columns]

    idx_ts = (
        columnas_archivo.index(sugerencia.columna_timestamp)
        if sugerencia.columna_timestamp in columnas_archivo
        else 0
    )
    col_ts = st.selectbox(
        t("p2.medido.mapeo.timestamp"),
        options=columnas_archivo,
        index=idx_ts,
        key="p2_med_col_timestamp",
    )

    sug_por_var = {m.variable: m for m in sugerencia.columnas}
    opciones_col = [None] + columnas_archivo
    seleccion: dict = {}
    for variable in VARIABLES_MAPEABLES:
        unidades = list(UNIDADES_POR_VARIABLE[variable])
        sug = sug_por_var.get(variable)
        c_col, c_uni = st.columns([3, 1])
        with c_col:
            col_sel = st.selectbox(
                t(f"p2.medido.variable.{variable}"),
                options=opciones_col,
                index=(
                    opciones_col.index(sug.columna_origen)
                    if sug is not None and sug.columna_origen in columnas_archivo
                    else 0
                ),
                format_func=lambda c: t("p2.medido.mapeo.no_mapear") if c is None else c,
                key=f"p2_med_col_{variable}",
            )
        with c_uni:
            uni_sel = st.selectbox(
                t("p2.medido.mapeo.unidad"),
                options=unidades,
                index=(
                    unidades.index(sug.unidad) if sug is not None and sug.unidad in unidades else 0
                ),
                format_func=lambda u: t(f"p2.medido.unidad.{u}"),
                key=f"p2_med_uni_{variable}",
            )
        seleccion[variable] = (col_sel, uni_sel)

    # ---- metadatos de adquisición ----
    conv = st.radio(
        t("p2.medido.convencion.label"),
        options=list(CONVENCIONES_TIMESTAMP),
        format_func=lambda k: t(f"p2.medido.convencion.{k}"),
        key="p2_med_conv",
        horizontal=True,
        help=t("p2.medido.convencion.help"),
    )
    zona = st.selectbox(
        t("p2.medido.tz.label"),
        options=_ZONAS_HORARIAS,
        index=(
            _ZONAS_HORARIAS.index(empl.zona_horaria) if empl.zona_horaria in _ZONAS_HORARIAS else 0
        ),
        key="p2_med_tz",
    )
    # Fecha fija: archivos cuya columna de timestamp trae solo la hora (sin fecha).
    fecha_fija = None
    if st.checkbox(t("p2.medido.fecha_fija.check"), key="p2_med_usar_fecha"):
        from datetime import date as _date

        fecha_fija = st.date_input(
            t("p2.medido.fecha_fija.label"),
            min_value=_date(1990, 1, 1),
            max_value=_date.today(),
            key="p2_med_fecha",
            help=t("p2.medido.fecha_fija.help"),
        )
    altura = 2.0
    if seleccion.get("WS_ms", (None, None))[0] is not None:
        altura = float(
            st.number_input(
                t("p2.medido.alt_viento.label"),
                min_value=0.5,
                max_value=50.0,
                value=2.0,
                step=0.5,
                key="p2_med_alt_viento",
                help=t("p2.medido.alt_viento.help"),
            )
        )
    plano = "horizontal"
    if seleccion.get("GHI_Wm2", (None, None))[0] is not None:
        plano = st.radio(
            t("p2.medido.plano.label"),
            options=list(PLANOS_PIRANOMETRO),
            format_func=lambda k: t(f"p2.medido.plano.{k}"),
            key="p2_med_plano",
            horizontal=True,
            help=t("p2.medido.plano.help"),
        )

    n_mapeadas = sum(1 for c, _ in seleccion.values() if c is not None)
    if n_mapeadas == 0:
        st.warning(t("p2.medido.falta_variables"))
        st.session_state.pop("p2_med_resultado", None)
        return

    try:
        cfg = _construir_config_medido(
            col_ts, seleccion, zona, conv, altura, plano, hoja, fila_enc, fecha_fija
        )
    except ValueError as exc:
        st.error(t("p2.medido.error", err=exc))
        return
    hash_cfg = cm.hash_ingesta(arch["hash"], cfg)

    # resultado previo invalidado si cambió el mapeo
    if st.session_state.get("_p2_med_hash_res") not in (None, hash_cfg):
        st.session_state.pop("p2_med_resultado", None)

    if st.button(t("p2.medido.procesar"), type="primary", key="p2_med_procesar"):
        with st.spinner(t("p2.medido.spinner")):
            try:
                resultado = cm.ingerir_clima_medido(tabla, cfg, empl)
            except (ValueError, RuntimeError) as exc:
                st.error(t("p2.medido.error", err=exc))
            except Exception as exc:  # mapeo arbitrario sobre archivo arbitrario
                st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
            else:
                st.session_state["p2_med_resultado"] = resultado
                st.session_state["_p2_med_hash_res"] = hash_cfg

    res = st.session_state.get("p2_med_resultado")
    if res is None:
        return

    # ---- revisión: procedencia + QC + confirmación ----
    st.markdown(t("p2.medido.procedencia.titulo"))
    st.dataframe(_tabla_procedencia(res, t), hide_index=True)
    resumen = _resumen_medido_dict(res)
    st.caption(
        t(
            "p2.medido.resumen.previo",
            inicio=str(resumen["periodo_inicio"] or "—")[:16],
            fin=str(resumen["periodo_fin"] or "—")[:16],
            paso=int(resumen["paso_s"] or 0),
            n_horas=len(res.datos),
        )
    )
    hallazgos = res.qc.con_hallazgos() if res.qc is not None else []
    with st.expander(t("p2.medido.qc.titulo", n=len(hallazgos)), expanded=False):
        if not hallazgos:
            st.caption(t("p2.medido.qc.sin_hallazgos"))
        for chq in hallazgos:
            st.warning(
                t(
                    "p2.medido.qc.detalle",
                    chequeo=t(f"p2.medido.qc.chequeo.{chq.codigo}"),
                    variable=t(f"p2.medido.variable.{chq.variable}"),
                    n=chq.n_marcados + chq.n_avisos,
                    ejemplos=", ".join(chq.ejemplos[:3]),
                )
            )

    if st.button(t("p2.medido.confirmar"), type="primary", key="p2_med_confirmar"):
        proyecto.clima = res
        try:
            cm.guardar_cache_medido(res, hash_cfg)
        except Exception:
            pass  # la cache es una comodidad; no bloquea la confirmación
        # Clave deliberadamente FUERA del prefijo "p2_med_": debe sobrevivir a
        # _limpiar_estado_medido() para poder descargar el snapshot tras confirmar.
        st.session_state["p2med_snapshot"] = {
            "seccion": "clima_medido",
            "nombre_archivo": arch["nombre"],
            "hash_archivo": arch["hash"],
            "hash_ingesta": hash_cfg,
            "mapeo": cm.config_a_dict(cfg),
        }
        _limpiar_estado_medido()
        st.success(t("p2.medido.exito"))
        st.rerun()


def render() -> None:
    """Renderiza la pestaña 2: Emplazamiento y Recursos Climáticos."""

    st.header(t("p2.header"))
    boton_manual(SLUG_POR_SECCION["p2"])

    proyecto = st.session_state.proyecto

    # Inicializar emplazamiento con defaults si es la primera vez
    if proyecto.emplazamiento is None:
        proyecto.emplazamiento = Emplazamiento()

    empl: Emplazamiento = proyecto.emplazamiento

    # -----------------------------------------------------------------------
    # Sección 1: Ubicación geográfica
    # -----------------------------------------------------------------------

    with st.expander(t("p2.ubicacion.titulo"), expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            lat = st.number_input(
                t("p2.ubicacion.lat.label"),
                min_value=-90.0,
                max_value=90.0,
                value=float(empl.latitud_deg),
                step=0.01,
                format="%.4f",
                help=t("p2.ubicacion.lat.help"),
            )
            lon = st.number_input(
                t("p2.ubicacion.lon.label"),
                min_value=-180.0,
                max_value=180.0,
                value=float(empl.longitud_deg),
                step=0.01,
                format="%.4f",
                help=t("p2.ubicacion.lon.help"),
            )
        with c2:
            alt = st.number_input(
                t("p2.ubicacion.alt.label"),
                min_value=-500.0,
                max_value=8850.0,
                value=float(empl.altitud_m),
                step=10.0,
                format="%.0f",
                help=t("p2.ubicacion.alt.help"),
            )
            tz_idx = (
                _ZONAS_HORARIAS.index(empl.zona_horaria)
                if empl.zona_horaria in _ZONAS_HORARIAS
                else 0
            )
            zona = st.selectbox(
                t("p2.ubicacion.zona.label"),
                options=_ZONAS_HORARIAS,
                index=tz_idx,
                help=t("p2.ubicacion.zona.help"),
            )
        with c3:
            st.caption(t("p2.ubicacion.referencia"))
            hemisferio = t(
                "p2.ubicacion.hemisferio_sur" if lat < 0 else "p2.ubicacion.hemisferio_norte"
            )
            meridiano = t(
                "p2.ubicacion.meridiano_oeste" if lon < 0 else "p2.ubicacion.meridiano_este"
            )
            st.info(
                t(
                    "p2.ubicacion.resumen",
                    lat=abs(lat),
                    hemisferio=hemisferio,
                    lon=abs(lon),
                    meridiano=meridiano,
                    alt=alt,
                )
            )

        # Aplicar cambios al emplazamiento
        try:
            # replace() preserva los campos no mencionados (orientación, albedo,
            # y cualquier campo futuro de Emplazamiento) — evita resetearlos.
            nuevo_empl = dataclasses.replace(
                empl,
                latitud_deg=lat,
                longitud_deg=lon,
                altitud_m=alt,
                zona_horaria=zona,
            )
            if nuevo_empl != empl:
                # Si cambió la posición geográfica, invalidar datos climáticos
                if (
                    abs(nuevo_empl.latitud_deg - empl.latitud_deg) > 1e-4
                    or abs(nuevo_empl.longitud_deg - empl.longitud_deg) > 1e-4
                ):
                    proyecto.clima = None
                proyecto.emplazamiento = nuevo_empl
                empl = nuevo_empl
        except ValueError as err:
            codigo = str(err).split(":")[0]
            st.error(t("p2.error_validacion", codigo=codigo, err=err))

    # -----------------------------------------------------------------------
    # Sección 2: Orientación del colector
    # -----------------------------------------------------------------------

    _tipologia_p2 = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
    if _tipologia_p2 == Tipologia.CAJA:
        with st.expander(t("p2.orientacion.titulo"), expanded=False):
            st.info(t("p2.orientacion.nota_caja"))
    else:
        with st.expander(t("p2.orientacion.titulo"), expanded=False):
            c1, c2 = st.columns([2, 1])
            with c1:
                # Mostrar en convención UI360 (0=S, 90=E, 180=N, 270=O)
                acimut_ui360 = st.number_input(
                    t("p2.orientacion.acimut.label"),
                    min_value=0.0,
                    max_value=360.0,
                    value=float(acimut_duffie_a_ui360(empl.acimut_colector_deg)),
                    step=1.0,
                    format="%.1f",
                    help=t("p2.orientacion.acimut.help"),
                )
                pendiente = st.number_input(
                    t("p2.orientacion.pendiente.label"),
                    min_value=0.0,
                    max_value=90.0,
                    value=float(empl.pendiente_colector_deg),
                    step=1.0,
                    format="%.1f",
                    help=t("p2.orientacion.pendiente.help"),
                )
            with c2:
                st.caption(t("p2.orientacion.caption"))
                _puntos_ui360 = {
                    0.0: "sur",
                    45.0: "se",
                    90.0: "este",
                    135.0: "ne",
                    180.0: "norte",
                    225.0: "no",
                    270.0: "oeste",
                    315.0: "so",
                    360.0: "sur",
                }
                referencia = min(_puntos_ui360.keys(), key=lambda k: abs(k - acimut_ui360))
                acimut_duffie = acimut_ui360_a_duffie(acimut_ui360)
                acimut_pvlib = acimut_duffie_a_pvlib(acimut_duffie)
                st.metric(
                    t("p2.orientacion.aprox"),
                    t(f"p2.orientacion.puntos.{_puntos_ui360[referencia]}"),
                )
                st.caption(t("p2.orientacion.acimut_pvlib", v=acimut_pvlib))
                st.caption(t("p2.orientacion.inclinacion", v=pendiente))

            # Actualizar emplazamiento con orientación (almacenamiento en Duffie)
            try:
                # replace() preserva lat/lon/alt/zona/albedo y cualquier campo futuro.
                nuevo_empl = dataclasses.replace(
                    empl,
                    acimut_colector_deg=acimut_duffie,
                    pendiente_colector_deg=pendiente,
                )
                if nuevo_empl != empl:
                    proyecto.emplazamiento = nuevo_empl
                    empl = nuevo_empl
            except ValueError as err:
                codigo = str(err).split(":")[0]
                st.error(t("p2.error_validacion", codigo=codigo, err=err))

    # -----------------------------------------------------------------------
    # Sección 3: Datos climáticos NASA POWER
    # -----------------------------------------------------------------------

    st.subheader(t("p2.clima.titulo"))

    # Sincronización con P1: si el usuario eligió un día específico (modo
    # DIARIO) o una ventana de producción (modo VENTANA) en P1, el año de
    # descarga arranca con el año de esa fecha. Si después cambia la fecha en
    # P1, el widget se actualiza automáticamente. El usuario puede sobrescribir
    # el año manualmente — su elección persiste hasta que vuelva a cambiar la
    # fecha en P1.
    cfg_p1 = proyecto.configuracion
    fecha_p1 = cfg_p1.fecha_especifica if cfg_p1 is not None else None
    ventana_inicio_p1 = getattr(cfg_p1, "ventana_inicio", None) if cfg_p1 is not None else None
    modo_ventana = (
        cfg_p1 is not None and getattr(cfg_p1, "modo_analisis", None) == ModoAnalisis.VENTANA
    )
    if modo_ventana and ventana_inicio_p1 is not None:
        anio_p1 = ventana_inicio_p1.year
        fecha_sync_label = t("p2.clima.sync_ventana", fecha=ventana_inicio_p1.isoformat())
    elif fecha_p1:
        anio_p1 = fecha_p1.year
        fecha_sync_label = t("p2.clima.sync_dia", fecha=fecha_p1.isoformat())
    else:
        anio_p1 = None
        fecha_sync_label = None
    fuente_sel = st.radio(
        t("p2.fuente.titulo"),
        options=["nasa_power", "medido"],
        index=(
            1
            if (
                "p2_fuente_clima" not in st.session_state
                and proyecto.clima is not None
                and getattr(proyecto.clima, "fuente", "nasa_power") != "nasa_power"
            )
            else 0
        ),
        format_func=lambda k: t(f"p2.fuente.{k}"),
        key="p2_fuente_clima",
        horizontal=True,
    )
    clima: Clima | None = proyecto.clima
    boton_descarga = False

    if fuente_sel == "medido":
        _render_clima_medido(proyecto, empl)
        clima = proyecto.clima
    else:
        # Sincronización P1→P2 robusta a la purga de widget-keys al navegar (mejora
        # 28). La lógica vive en _resolver_anio_descarga (pura, testeable).
        anio_descarga, ultimo_visto = _resolver_anio_descarga(
            anio_p1=anio_p1,
            anio_descarga_actual=st.session_state.get("p2_anio_descarga"),
            ultimo_anio_p1_visto=st.session_state.get("_p2_anio_p1_visto"),
        )
        st.session_state["p2_anio_descarga"] = anio_descarga
        st.session_state["_p2_anio_p1_visto"] = ultimo_visto

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            anio = st.number_input(
                t("p2.clima.anio.label"),
                min_value=_ANIO_MIN,
                max_value=_ANIO_MAX,
                step=1,
                key="p2_anio_descarga",
                help=(
                    t("p2.clima.anio.help_base", anio_min=_ANIO_MIN, anio_max=_ANIO_MAX)
                    + (
                        t("p2.clima.anio.help_sync", sync=fecha_sync_label)
                        if fecha_sync_label
                        else t("p2.clima.anio.help_sin_sync")
                    )
                ),
            )
        with c2:
            forzar = st.checkbox(
                t("p2.clima.forzar.label"),
                value=False,
                help=t("p2.clima.forzar.help"),
            )
        with c3:
            st.write("")
            st.write("")
            boton_descarga = st.button(t("p2.clima.descargar"), type="primary", width="stretch")

        if boton_descarga:
            with st.spinner(
                t("p2.clima.spinner", lat=empl.latitud_deg, lon=empl.longitud_deg, anio=anio)
            ):
                try:
                    clima = obtener_clima(empl, int(anio), forzar_descarga=forzar)
                    proyecto.clima = clima
                    st.success(t("p2.clima.exito", n=len(clima.datos), alt=clima.altitud_nasa_m))
                except RuntimeError as err:
                    st.error(t("p2.clima.error_descarga", err=err))
                    clima = None

    # -----------------------------------------------------------------------
    # Mostrar estado de la descarga previa (si existe en session_state)
    # -----------------------------------------------------------------------

    if clima is not None and clima.datos is not None:
        datos = clima.datos
        cal = clima.calidad

        # Resumen de calidad
        col_cal = st.columns(4)
        col_cal[0].metric(t("p2.calidad.registros"), f"{len(datos):,}")
        col_cal[1].metric(t("p2.calidad.anio_datos"), str(clima.anio))
        col_cal[2].metric(
            t("p2.calidad.interpoladas.label"),
            f"{cal.n_horas_interpoladas}",
            help=t("p2.calidad.interpoladas.help"),
        )
        col_cal[3].metric(
            t("p2.calidad.bloqueadas.label"),
            f"{cal.n_horas_bloqueadas}",
            delta=None if cal.n_horas_bloqueadas == 0 else "⚠",
            help=t("p2.calidad.bloqueadas.help"),
        )

        # Coherencia con la ventana de producción de P1 (modo VENTANA).
        if modo_ventana and ventana_inicio_p1 is not None and clima.anio != ventana_inicio_p1.year:
            st.warning(
                t(
                    "p2.calidad.anio_distinto_ventana",
                    anio_clima=clima.anio,
                    anio_ventana=ventana_inicio_p1.year,
                )
            )

        # ---- Decisión de usuario para huecos bloqueados ----
        if cal.n_horas_bloqueadas > 0 and cal.decision_usuario is None:
            st.warning(
                t(
                    "p2.calidad.huecos_warning",
                    n=cal.n_horas_bloqueadas,
                    mayor=cal.mayor_hueco_h,
                )
            )
            decision = st.radio(
                t("p2.calidad.como_continuar"),
                options=["aceptar_con_nulos", "descargar_nuevo_anio"],
                format_func=lambda x: (
                    t("p2.medido.opcion_descartar")
                    if x == "descargar_nuevo_anio"
                    and getattr(clima, "fuente", "nasa_power") != "nasa_power"
                    else t(f"p2.calidad.opcion_{x}")
                ),
                key="p2_decision_huecos",
            )
            if st.button(t("p2.calidad.confirmar")):
                clima.calidad.decision_usuario = decision
                proyecto.clima = clima
                if decision == "descargar_nuevo_anio":
                    proyecto.clima = None
                    st.rerun()
                else:
                    st.success(t("p2.calidad.decision_guardada"))

        elif cal.n_horas_bloqueadas > 0 and cal.decision_usuario == "aceptar_con_nulos":
            st.info(t("p2.calidad.nulos_aceptados", n=cal.n_horas_bloqueadas))

        # -----------------------------------------------------------------------
        # Sección 4: Visualizaciones
        # -----------------------------------------------------------------------

        st.subheader(t("p2.anual.titulo"))
        st.caption(
            t("p2.anual.caption", anio=clima.anio, lat=empl.latitud_deg, lon=empl.longitud_deg)
        )

        # Convertir índice a zona horaria local y recortar al año de análisis.
        # Sin el recorte, la conversión UTC→local desplaza algunas horas al
        # año anterior (ej. 00:00 UTC del 1-ene = 21:00 del 31-dic en UTC-3),
        # generando un bucket extra en el resample mensual (13 meses en vez de 12).
        datos_local = datos.tz_convert(empl.zona_horaria)
        datos_local = datos_local[datos_local.index.year == clima.anio]

        # Calcular POA anual aquí (fuera de tabs) para reutilizarlo
        # tanto en la sección anual como en la sección diaria.
        # En CAJA no hay colector: se usa la orientación propia de la cámara
        # (techo a un agua) si está configurada; si no, GHI horizontal.
        _poa_label = t("p2.anual.poa_plano_colector")
        if _tipologia_p2 == Tipologia.CAJA and getattr(proyecto, "camara", None) is not None:
            _geo_cam = proyecto.camara.geometria
            pendiente_poa = _geo_cam.pendiente_techo_deg
            acimut_pvlib_actual = acimut_duffie_a_pvlib(_geo_cam.acimut_camara_deg)
            _poa_label = t("p2.anual.poa_techo_camara")
        else:
            pendiente_poa = empl.pendiente_colector_deg
            acimut_pvlib_actual = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
        with st.spinner(t("p2.anual.spinner_poa", plano=_poa_label)):
            poa_horaria = _calcular_poa_horaria(
                datos_local,
                lat=empl.latitud_deg,
                lon=empl.longitud_deg,
                altitud_m=empl.altitud_m,
                pendiente_deg=pendiente_poa,
                acimut_pvlib_deg=acimut_pvlib_actual,
                albedo=empl.albedo_suelo,
            )

        tab_t, tab_rad, tab_vhr, tab_tabla = st.tabs(
            [
                t("p2.tabs.temperatura"),
                t("p2.tabs.irradiancia"),
                t("p2.tabs.viento_hr"),
                t("p2.tabs.tabla"),
            ]
        )

        with tab_t:
            fig_t = _fig_temperatura(datos_local)
            mostrar_plotly(fig_t, nombre="temperatura")

        with tab_rad:
            fig_rad = _fig_irradiancia_comparativa(datos_local, poa_horaria)
            mostrar_plotly(fig_rad, nombre="irradiancia")

            poa_anual = poa_horaria.sum() / 1000.0
            ghi_anual = datos_local["GHI_Wm2"].sum() / 1000.0
            col_a, col_b, col_c = st.columns(3)
            col_a.metric(t("p2.anual.ghi_anual"), f"{ghi_anual:.0f} kWh/m²")
            col_b.metric(
                t("p2.anual.poa_anual"),
                f"{poa_anual:.0f} kWh/m²",
                delta=t("p2.anual.delta_vs_ghi", delta=poa_anual - ghi_anual),
            )
            col_c.metric(
                t("p2.anual.pend_acimut"),
                f"{empl.pendiente_colector_deg:.0f}° / {acimut_duffie_a_ui360(empl.acimut_colector_deg):.0f}°",
            )
            st.caption(t("p2.anual.nota_transposicion"))

        with tab_vhr:
            fig_vhr = _fig_viento_hr(datos_local)
            mostrar_plotly(fig_vhr, nombre="viento_hr")

        with tab_tabla:
            df_mens = _resumen_mensual(datos_local)
            st.dataframe(df_mens.set_index(t("p2.tabla.mes")), width="stretch")

        # -----------------------------------------------------------------------
        # Sección 5: Recurso climático del día de diseño (solo modo DIARIO)
        # -----------------------------------------------------------------------

        cfg = proyecto.configuracion
        if cfg is not None and cfg.modo_analisis == ModoAnalisis.DIARIO:
            fecha_dia = _fecha_dia_analisis(datos_local, cfg, clima.anio)
            mask_dia = datos_local.index.date == fecha_dia
            datos_dia = datos_local[mask_dia]
            poa_dia = poa_horaria[mask_dia]

            label_dia = t(
                f"p2.dia.criterio.{cfg.dia_analisis.value.lower()}",
                default=t("p2.dia.criterio.default"),
            )

            st.subheader(t("p2.dia.titulo"))
            st.caption(
                t(
                    "p2.dia.caption",
                    fecha=fecha_dia.strftime("%d/%m/%Y"),
                    criterio=label_dia,
                    lat=empl.latitud_deg,
                    lon=empl.longitud_deg,
                )
            )

            if len(datos_dia) == 0:
                st.warning(
                    t(
                        "p2.dia.sin_datos",
                        fecha=fecha_dia.strftime("%d/%m/%Y"),
                        anio=clima.anio,
                    )
                )
            else:
                # Métricas del día
                T_dia_C = datos_dia["T_amb_K"] - 273.15
                col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns(5)
                col_d1.metric(t("p2.dia.t_media"), f"{T_dia_C.mean():.1f} °C")
                col_d2.metric(
                    t("p2.dia.t_min_max"), f"{T_dia_C.min():.1f} / {T_dia_C.max():.1f} °C"
                )
                col_d3.metric(t("p2.dia.ghi_dia"), f"{datos_dia['GHI_Wm2'].sum()/1000:.2f} kWh/m²")
                col_d4.metric(t("p2.dia.poa_dia"), f"{poa_dia.sum()/1000:.2f} kWh/m²")
                col_d5.metric(t("p2.dia.viento_medio"), f"{datos_dia['WS_ms'].mean():.1f} m/s")

                tab_dt, tab_drad, tab_dvhr = st.tabs(
                    [t("p2.tabs.temperatura"), t("p2.tabs.irradiancia"), t("p2.tabs.viento_hr")]
                )

                with tab_dt:
                    fig_dt = _fig_temperatura_diaria(datos_dia)
                    mostrar_plotly(fig_dt, nombre="temperatura_dia")

                with tab_drad:
                    fig_drad = _fig_irradiancia_diaria(datos_dia, poa_dia)
                    mostrar_plotly(fig_drad, nombre="irradiancia_dia")
                    st.caption(t("p2.dia.nota_transposicion"))

                with tab_dvhr:
                    fig_dvhr = _fig_viento_hr_diaria(datos_dia)
                    mostrar_plotly(fig_dvhr, nombre="viento_hr_dia")

                # Botón CSV del día
                csv_dia = _generar_csv(datos_dia, empl.zona_horaria)
                st.download_button(
                    label=t("p2.dia.csv", fecha=fecha_dia.strftime("%d/%m/%Y")),
                    data=csv_dia,
                    file_name=(
                        f"nasa_power_{empl.latitud_deg:.4f}_{empl.longitud_deg:.4f}"
                        f"_{fecha_dia.isoformat()}.csv"
                    ),
                    mime="text/csv",
                )

        # -----------------------------------------------------------------------
        # Sección 5b: Recurso climático de la ventana de producción (modo
        # VENTANA, gran escala — S41)
        # -----------------------------------------------------------------------

        if (
            cfg is not None
            and cfg.modo_analisis == ModoAnalisis.VENTANA
            and getattr(cfg, "ventana_inicio", None) is not None
            and getattr(cfg, "ventana_fin", None) is not None
        ):
            from calculos.clima_calc import slice_clima_ventana

            st.subheader(t("p2.ventana.titulo"))
            df_vent, msg_vent = slice_clima_ventana(clima, cfg.ventana_inicio, cfg.ventana_fin)
            if df_vent is None:
                st.warning(f"⚠️ {msg_vent}")  # i18n: exento (mensaje de calculos/, queda ES)
            else:
                datos_vent = df_vent.tz_convert(empl.zona_horaria)
                poa_vent = poa_horaria.reindex(datos_vent.index).fillna(0.0)
                n_dias_vent = (cfg.ventana_fin - cfg.ventana_inicio).days
                st.caption(
                    t(
                        "p2.ventana.caption",
                        inicio=cfg.ventana_inicio,
                        fin=cfg.ventana_fin,
                        dias=n_dias_vent,
                        horas=len(datos_vent),
                        anio=clima.anio,
                        lat=empl.latitud_deg,
                        lon=empl.longitud_deg,
                    )
                )

                T_vent_C = datos_vent["T_amb_K"] - 273.15
                col_v1, col_v2, col_v3, col_v4, col_v5 = st.columns(5)
                col_v1.metric(t("p2.dia.t_media"), f"{T_vent_C.mean():.1f} °C")
                col_v2.metric(
                    t("p2.dia.t_min_max"), f"{T_vent_C.min():.1f} / {T_vent_C.max():.1f} °C"
                )
                col_v3.metric(t("p2.ventana.ghi"), f"{datos_vent['GHI_Wm2'].sum()/1000:.1f} kWh/m²")
                col_v4.metric(t("p2.ventana.poa"), f"{poa_vent.sum()/1000:.1f} kWh/m²")
                col_v5.metric(t("p2.dia.viento_medio"), f"{datos_vent['WS_ms'].mean():.1f} m/s")

                tab_vt, tab_vrad, tab_vvhr = st.tabs(
                    [t("p2.tabs.temperatura"), t("p2.tabs.irradiancia"), t("p2.tabs.viento_hr")]
                )
                with tab_vt:
                    mostrar_plotly(
                        _fig_temperatura_diaria(datos_vent), nombre="temperatura_ventana"
                    )
                with tab_vrad:
                    mostrar_plotly(
                        _fig_irradiancia_diaria(datos_vent, poa_vent),
                        nombre="irradiancia_ventana",
                    )
                    st.caption(t("p2.dia.nota_transposicion"))
                with tab_vvhr:
                    mostrar_plotly(_fig_viento_hr_diaria(datos_vent), nombre="viento_hr_ventana")

                csv_vent = _generar_csv(datos_vent, empl.zona_horaria)
                st.download_button(
                    label=t("p2.ventana.csv", inicio=cfg.ventana_inicio, fin=cfg.ventana_fin),
                    data=csv_vent,
                    file_name=(
                        f"nasa_power_{empl.latitud_deg:.4f}_{empl.longitud_deg:.4f}"
                        f"_ventana_{cfg.ventana_inicio.isoformat()}"
                        f"_{cfg.ventana_fin.isoformat()}.csv"
                    ),
                    mime="text/csv",
                )

        # -----------------------------------------------------------------------
        # Sección 6: Descarga CSV
        # -----------------------------------------------------------------------

        st.subheader(t("p2.exportar.titulo"))
        csv_bytes = _generar_csv(datos, empl.zona_horaria)
        st.download_button(
            label=t("p2.exportar.csv"),
            data=csv_bytes,
            file_name=f"nasa_power_{empl.latitud_deg:.4f}_{empl.longitud_deg:.4f}_{clima.anio}.csv",
            mime="text/csv",
            help=t("p2.exportar.csv_help"),
        )

    elif proyecto.clima is None and not boton_descarga:
        st.info(t("p2.sin_clima"))
