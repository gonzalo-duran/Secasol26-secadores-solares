"""
Pestaña 7 — Resultados del Prediseño.

Orquesta todos los cálculos del sistema y muestra el dashboard integrado:
colector → auxiliar → cámara → balance global.

Las condiciones de operación representativas (T_amb, I_g, v_viento) se
ingresan manualmente o se sugieren desde los datos NASA POWER de P2.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from calculos.balance_global import (
    ResultadosCompletos,
    ResultadosCompletosTransitorio,
    calcular_todo,
    calcular_todo_transitorio,
    calcular_todo_ventana,
    resumen_camara,
)
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from core.proyecto import ModoAnalisis, Tipologia
from ui.componentes.graficas import grafica_termodinamica_camara, mostrar_plotly
from ui.componentes.idiomas import idioma_actual, t
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_T_AMB_DEFAULT_C = 25.0
_I_G_DEFAULT_W_M2 = 800.0
_V_VIENTO_DEFAULT_MS = 2.0
_HR_CAMARA_DEFAULT_PCT = 20.0
_LV_KJ_KG = 2450.0  # calor latente de vaporización [kJ/kg]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estado(ok: bool) -> str:
    return "✅" if ok else "❌"


def _resumen_camara(cam) -> tuple[float | None, float, str, bool]:
    """Extrae (t_h, masa_agua_kg, status_legible, ok) abstrayendo el tipo.

    Wrapper de UI sobre :func:`calculos.balance_global.resumen_camara` que
    convierte el tiempo a horas (la conversión de unidades vive en la frontera
    de UI) y conserva la firma de tupla usada por los consumidores de P7.
    """
    r = resumen_camara(cam)
    t_s = r["t_secado_s"]
    t_h = t_s / 3600.0 if t_s is not None else None
    return t_h, r["masa_agua_kg"], r["status"], r["convergio"]


def _mostrar_errores(errores: list[str]) -> None:
    # Los mensajes de error vienen de calculos/ y quedan en ES en v1 (fase F5).
    for e in errores:
        st.error(f"❌ {e}")  # i18n: exento (mensaje de calculos/, F5)


def _mostrar_advertencias(advs: list[str]) -> None:
    for a in advs:
        st.warning(f"⚠️ {a}")  # i18n: exento (mensaje de calculos/, F5)


def _desviacion_caudal_natural(res_chim: dict, proyecto) -> float | None:
    """Desviación relativa caudal natural vs caudal de diseño de cámara.

    Returns:
        |m_natural − m_design| / m_design (adim), o None si no aplica.
    """
    if proyecto is None or proyecto.camara is None:
        return None
    m_design = float(proyecto.camara.flujo.caudal_masico_kg_s or 0.0)
    m_nat = float(res_chim.get("m_punto_kgs", 0.0))
    if m_design <= 0:
        return None
    return abs(m_nat - m_design) / m_design


def _render_chimenea_resultados(res_chim: dict, proyecto) -> None:
    """Renderiza el bloque de resultados del lazo natural por chimenea.

    Solo se llama cuando ``res.chimenea is not None`` (motor=None + chimenea
    + cámara presentes, ver `calcular_todo`).
    """
    st.subheader(t("p7.chimenea.titulo"))

    m_punto = float(res_chim.get("m_punto_kgs", 0.0))
    # Caudal volumétrico a 1.1 kg/m³ (ρ_amb típica 25 °C, coherente con
    # _advertencia_caudal_inconsistente en balance_global).
    Q_m3h = m_punto / 1.1 * 3600.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        t("p7.chimenea.caudal_natural.label"),
        f"{m_punto * 1000:.1f} g/s",
        help=t("p7.chimenea.caudal_natural.help"),
    )
    c2.metric(t("p7.chimenea.q_vol.label"), f"{Q_m3h:.0f} m³/h", help=t("p7.chimenea.q_vol.help"))
    c3.metric(t("p7.chimenea.v_chim"), f"{res_chim.get('v_chim_ms', 0.0):.2f} m/s")
    c4.metric(t("p7.chimenea.re"), f"{res_chim.get('Re_chimenea', 0.0):.0f}")

    dP_tiro = float(res_chim.get("delta_P_tiro_Pa", 0.0))
    dP_chim = float(res_chim.get("delta_P_chimenea_Pa", 0.0))
    dP_resto = float(res_chim.get("delta_P_resto_Pa", 0.0))
    H_eff = float(res_chim.get("H_eff_m", 0.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        t("p7.chimenea.dp_tiro.label"), f"{dP_tiro:.2f} Pa", help=t("p7.chimenea.dp_tiro.help")
    )
    c2.metric(
        t("p7.chimenea.dp_chim.label"), f"{dP_chim:.2f} Pa", help=t("p7.chimenea.dp_chim.help")
    )
    c3.metric(
        t("p7.chimenea.dp_resto.label"),
        f"{dP_resto:.2f} Pa",
        help=t("p7.chimenea.dp_resto.help"),
    )
    c4.metric(t("p7.chimenea.h_eff.label"), f"{H_eff:.2f} m", help=t("p7.chimenea.h_eff.help"))

    # Caption con el balance del lazo (verificación cualitativa de cierre).
    if dP_tiro > 0:
        balance_err = abs(dP_tiro - dP_chim - dP_resto) / dP_tiro
        st.caption(
            t("p7.chimenea.balance", tiro=dP_tiro, chim=dP_chim, resto=dP_resto, err=balance_err)
        )

    # Comparación con caudal de diseño de cámara: si difiere >30%, warning.
    desv = _desviacion_caudal_natural(res_chim, proyecto)
    if desv is not None and desv > 0.30:
        m_design = proyecto.camara.flujo.caudal_masico_kg_s
        st.warning(
            t(
                "p7.chimenea.desviacion_caudal",
                nat=m_punto * 1000,
                desv=desv,
                design=m_design * 1000,
            )
        )

    # Advertencias propias de la solución del lazo (laminar, v alta, sin tiro).
    advs_chim = res_chim.get("advertencias", []) or []
    if advs_chim:
        _mostrar_advertencias(advs_chim)


# ---------------------------------------------------------------------------
# Render: pipeline transitoria (mejora 19)
# ---------------------------------------------------------------------------


def _render_resultados_transitorios(res_tr, proyecto) -> None:
    """Muestra series transitorias + acumulados de la pipeline P7-transitoria."""
    if res_tr.errores:
        _mostrar_errores(res_tr.errores)
        return
    if res_tr.advertencias:
        with st.expander(t("p7.transitorio.advertencias"), expanded=False):
            _mostrar_advertencias(res_tr.advertencias)

    # ---- Tarjetas resumen ----
    st.subheader(t("p7.transitorio.resumen"))
    c1, c2, c3, c4 = st.columns(4)
    t_h_obj = (
        res_tr.t_X_obj_alcanzado_s / 3600.0 if res_tr.t_X_obj_alcanzado_s is not None else None
    )
    c1.metric(
        t("p7.transitorio.x_obj.label"),
        f"{t_h_obj:.1f} h" if t_h_obj is not None else t("p7.transitorio.x_obj.no"),
        help=t("p7.transitorio.x_obj.help"),
    )
    c2.metric(
        t("p7.transitorio.masa_agua"),
        f"{res_tr.masa_agua_evaporada_kg:.2f} kg",
    )
    c3.metric(
        t("p7.transitorio.energia_secado.label"),
        f"{res_tr.energia_secado_MJ:.2f} MJ",
        help=t("p7.transitorio.energia_secado.help"),
    )
    cop_txt = f"{res_tr.COP_secado:.2f}" if res_tr.COP_secado is not None else "—"
    c4.metric(t("p7.transitorio.cop"), cop_txt)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric(t("p7.transitorio.e_solar"), f"{res_tr.energia_solar_util_MJ:.2f} MJ")
    c6.metric(t("p7.transitorio.e_aux"), f"{res_tr.energia_auxiliar_MJ:.2f} MJ")
    c7.metric(t("p7.transitorio.e_motor"), f"{res_tr.energia_motor_MJ:.2f} MJ")
    fs_txt = f"{res_tr.fraccion_solar:.2f}" if res_tr.fraccion_solar is not None else "—"
    c8.metric(t("p7.transitorio.fraccion_solar"), fs_txt)

    # ---- Series temporales ----
    if res_tr.camara is None or res_tr.forzantes_aplicadas is None:
        st.warning(t("p7.transitorio.sin_trayectorias"))
        return

    t_h_fz = res_tr.forzantes_base.t_s / 3600.0
    t_h_cam = res_tr.camara.t_array_s / 3600.0

    st.subheader(t("p7.transitorio.trayectorias"))

    # --- Panel 1: Aire externo (T_amb, I_g, v_viento) ---
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.T_amb_K - 273.15,
            name=t("p7.transitorio.fig1.t_amb"),
            line=dict(color="#1f77b4", width=2),
        ),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.I_g_W_m2,
            name=t("p7.transitorio.fig1.i_g"),
            line=dict(color="#ff7f0e", width=1.5, dash="dot"),
        ),
        secondary_y=True,
    )
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.v_viento_ms,
            name=t("p7.transitorio.fig1.v_viento"),
            line=dict(color="#2ca02c", width=1),
        ),
        secondary_y=False,
    )
    fig1.update_yaxes(title_text=t("p7.transitorio.fig1.eje_t"), secondary_y=False)
    fig1.update_yaxes(title_text=t("p7.transitorio.fig1.eje_ig"), secondary_y=True)
    fig1.update_xaxes(title_text=t("p7.transitorio.eje_tiempo"))
    fig1.update_layout(
        title=t("p7.transitorio.fig1.titulo"),
        height=320,
        hovermode="x unified",
    )
    mostrar_plotly(fig1, nombre="transitorio_forzantes")

    # --- Panel 2: T_sal_col, ΔT_aux, T_ent_cam ---
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.T_ent_K - 273.15,
            name=t("p7.transitorio.fig2.t_sal_col"),
            line=dict(color="#d62728", width=2),
        )
    )
    if res_tr.auxiliar is not None:
        fig2.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=res_tr.forzantes_aplicadas.T_ent_K - 273.15,
                name=t("p7.transitorio.fig2.t_ent_cam"),
                line=dict(color="#9467bd", width=2),
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=res_tr.auxiliar.delta_T_K,
                name=t("p7.transitorio.fig2.dt_aux"),
                line=dict(color="#8c564b", width=1, dash="dash"),
            )
        )
    fig2.update_xaxes(title_text=t("p7.transitorio.eje_tiempo"))
    fig2.update_yaxes(title_text=t("p7.transitorio.fig2.eje"))
    fig2.update_layout(
        title=t("p7.transitorio.fig2.titulo"),
        height=320,
        hovermode="x unified",
    )
    mostrar_plotly(fig2, nombre="transitorio_acoplamiento")

    # --- Panel 3: producto T_prod, X_prod ---
    fig3 = make_subplots(specs=[[{"secondary_y": True}]])
    fig3.add_trace(
        go.Scatter(
            x=t_h_cam,
            y=res_tr.camara.T_prod_K - 273.15,
            name=t("p7.transitorio.fig3.t_prod"),
            line=dict(color="#1f77b4", width=2),
        ),
        secondary_y=False,
    )
    fig3.add_trace(
        go.Scatter(
            x=t_h_cam,
            y=res_tr.camara.X_prod_kg_kg,
            name=t("p7.transitorio.fig3.x_prod"),
            line=dict(color="#2ca02c", width=2),
        ),
        secondary_y=True,
    )
    fig3.update_yaxes(title_text=t("p7.transitorio.fig3.eje_t"), secondary_y=False)
    fig3.update_yaxes(title_text=t("p7.transitorio.fig3.eje_x"), secondary_y=True)
    fig3.update_xaxes(title_text=t("p7.transitorio.eje_tiempo"))
    fig3.update_layout(
        title=t("p7.transitorio.fig3.titulo"),
        height=320,
        hovermode="x unified",
    )
    if res_tr.t_X_obj_alcanzado_s is not None:
        fig3.add_vline(
            x=res_tr.t_X_obj_alcanzado_s / 3600.0,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=t("p7.transitorio.fig3.x_obj_marca"),
            annotation_position="top",
        )
    mostrar_plotly(fig3, nombre="transitorio_Tprod_X")

    # --- Panel 4: tasa de evaporación ---
    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(
            x=t_h_cam,
            y=res_tr.camara.m_dot_w_kg_s * 3600.0,
            name=t("p7.transitorio.fig4.m_dot"),
            line=dict(color="#1f77b4", width=2),
        )
    )
    fig4.update_xaxes(title_text=t("p7.transitorio.eje_tiempo"))
    fig4.update_yaxes(title_text=t("p7.transitorio.fig4.eje"))
    fig4.update_layout(
        title=t("p7.transitorio.fig4.titulo"),
        height=280,
        hovermode="x unified",
    )
    mostrar_plotly(fig4, nombre="transitorio_evaporacion")

    # --- Panel 5: Chimenea solar (lazo natural) ---
    res_ch = getattr(res_tr, "chimenea", None)
    if res_ch is not None:
        st.subheader(t("p7.transitorio.chim_titulo"))
        m_arr = np.asarray(res_ch["m_punto_kgs"])
        Tch_C = np.asarray(res_ch["T_chim_K"]) - 273.15
        dPT = np.asarray(res_ch["delta_P_tiro_Pa"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("p7.transitorio.chim_prom"), f"{res_ch['m_promedio_kgs'] * 1000:.1f} g/s")
        c2.metric(t("p7.transitorio.chim_max"), f"{res_ch['m_max_kgs'] * 1000:.1f} g/s")
        c3.metric(t("p7.transitorio.chim_tminmax"), f"{Tch_C.min():.1f} / {Tch_C.max():.1f} °C")
        c4.metric(
            t("p7.transitorio.chim_sin_tiro.label"),
            f"{int(res_ch['horas_sin_tiro'])} h",
            help=t("p7.transitorio.chim_sin_tiro.help"),
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(
            t("p7.transitorio.chim_iter.label"),
            f"{res_ch['iteraciones']}",
            help=t("p7.transitorio.chim_iter.help"),
        )
        c2.metric(
            t("p7.transitorio.chim_conv.label"),
            (
                t("p7.transitorio.chim_conv.si")
                if res_ch["convergio"]
                else t("p7.transitorio.chim_conv.no")
            ),
            help=t("p7.transitorio.chim_conv.help", v=res_ch["delta_T_chim_final_K"]),
        )
        c3.metric(t("p7.transitorio.chim_heff"), f"{res_ch['H_eff_m']:.2f} m")

        fig_ch = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ch.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=m_arr * 1000.0,
                name=t("p7.transitorio.chim_fig.m_nat"),
                line=dict(color="#17becf", width=2),
            ),
            secondary_y=False,
        )
        fig_ch.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=Tch_C,
                name=t("p7.transitorio.chim_fig.t_chim"),
                line=dict(color="#e377c2", width=2),
            ),
            secondary_y=True,
        )
        fig_ch.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=dPT,
                name=t("p7.transitorio.chim_fig.dp_tiro"),
                line=dict(color="#7f7f7f", width=1, dash="dot"),
            ),
            secondary_y=False,
        )
        fig_ch.update_yaxes(title_text=t("p7.transitorio.chim_fig.eje_izq"), secondary_y=False)
        fig_ch.update_yaxes(title_text=t("p7.transitorio.chim_fig.eje_der"), secondary_y=True)
        fig_ch.update_xaxes(title_text=t("p7.transitorio.eje_tiempo"))
        fig_ch.update_layout(
            title=t("p7.transitorio.chim_fig.titulo"),
            height=320,
            hovermode="x unified",
        )
        mostrar_plotly(fig_ch, nombre="chimenea")

    # ---- Diagnósticos extra ----
    with st.expander(t("p7.transitorio.diagnosticos")):
        d1, d2, d3 = st.columns(3)
        d1.metric(
            t("p7.transitorio.t_prod_max"),
            f"{(res_tr.T_prod_max_K - 273.15):.1f} °C" if res_tr.T_prod_max_K is not None else "—",
        )
        d2.metric(
            t("p7.transitorio.horas_anti_rehum"), f"{res_tr.horas_clipeo_pol_B_s/3600.0:.2f} h"
        )
        d3.metric(t("p7.transitorio.horas_hr"), f"{res_tr.horas_HR_alta_s/3600.0:.2f} h")
        if res_tr.auxiliar is not None:
            st.write(
                t(
                    "p7.transitorio.aux_activo",
                    horas=res_tr.auxiliar.horas_activo_s / 3600.0,
                    frac=res_tr.auxiliar.fraccion_horas_activo * 100,
                )
            )
            st.write(
                t(
                    "p7.transitorio.aux_dt",
                    dt=res_tr.auxiliar.delta_T_max_K,
                    q=res_tr.auxiliar.Q_max_W,
                )
            )


def _seccion_config(proyecto) -> None:
    """Muestra el estado de configuración de cada sección."""
    st.subheader(t("p7.config.titulo"))

    motor_o_chim_ok = (proyecto.motor is not None) or (
        proyecto.chimenea is not None and st.session_state.get("p6_chimenea_eval") is not None
    )
    if proyecto.motor is not None:
        label_p6 = t("p7.config.p6_motor")
    elif proyecto.chimenea is not None:
        label_p6 = t("p7.config.p6_chim")
    else:
        label_p6 = t("p7.config.p6_ambos")

    items = [
        (t("p7.config.p2_empl"), proyecto.emplazamiento is not None),
        (
            t("p7.config.p2_clima"),
            proyecto.clima is not None and proyecto.clima.datos is not None,
        ),
        (t("p7.config.p3_col"), proyecto.colector is not None),
        (t("p7.config.p4_cam"), proyecto.camara is not None),
        (t("p7.config.p5_aux"), proyecto.auxiliar is not None),
        (label_p6, motor_o_chim_ok),
    ]
    cols = st.columns(len(items))
    for col, (label, ok) in zip(cols, items):
        col.metric(label, _estado(ok))

    st.caption(t("p7.config.caption"))


def _sugerir_condiciones(proyecto) -> tuple[float, float, float]:
    """Devuelve (T_amb_C, I_g, v_viento) sugeridos desde datos de clima.

    Para ``I_g`` calcula una serie representativa y toma el quantile 90:
    en tipología CAJA, la irradiancia equivalente al producto sobre las
    caras translúcidas de la cámara (``series_radiacion_camara`` — la
    cámara opera como colector, con su propia orientación); en el resto,
    la POA sobre el plano del colector (``calcular_POA_horizonte``). Si el
    cálculo falla (falta de DNI/DHI, sin emplazamiento/cámara), cae a
    ``GHI_Wm2.quantile(0.90)`` como aproximación conservadora.
    """
    T_sug = _T_AMB_DEFAULT_C
    I_sug = _I_G_DEFAULT_W_M2
    v_sug = _V_VIENTO_DEFAULT_MS

    if proyecto.clima is not None and proyecto.clima.datos is not None:
        d = proyecto.clima.datos
        T_sug = round(kelvin_a_celsius(float(d["T_amb_K"].quantile(0.75))), 1)
        v_sug = round(float(d["WS_ms"].mean()), 1)
        es_caja = getattr(getattr(proyecto, "configuracion", None), "tipologia", None) == (
            Tipologia.CAJA
        )
        if es_caja and proyecto.emplazamiento is not None and proyecto.camara is not None:
            try:
                from calculos.radiacion_camara import series_radiacion_camara

                i_eq, _ = series_radiacion_camara(d, proyecto.emplazamiento, proyecto.camara)
                I_sug = round(float(i_eq.quantile(0.90)), 0)
            except Exception:
                I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
        elif proyecto.emplazamiento is not None:
            try:
                from calculos.clima_calc import calcular_POA_horizonte

                poa = calcular_POA_horizonte(d, proyecto.emplazamiento)
                I_sug = round(float(poa.quantile(0.90)), 0)
            except Exception:
                I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
        else:
            I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
    return T_sug, I_sug, v_sug


def _fig_sankey_simplificado(res: ResultadosCompletos) -> go.Figure | None:
    """Gráfico de barras del balance energético."""
    etiquetas = []
    valores = []
    colores = []

    if res.energia_solar_util_MJ is not None and res.energia_solar_util_MJ > 0:
        etiquetas.append(t("p7.balance_fig.solar"))
        valores.append(res.energia_solar_util_MJ)
        colores.append("#f5a623")
    if res.energia_auxiliar_MJ is not None and res.energia_auxiliar_MJ > 0:
        etiquetas.append(t("p7.balance_fig.auxiliar"))
        valores.append(res.energia_auxiliar_MJ)
        colores.append("#e05c2a")
    if res.energia_motor_MJ is not None and res.energia_motor_MJ > 0:
        etiquetas.append(t("p7.balance_fig.motor"))
        valores.append(res.energia_motor_MJ)
        colores.append("#9c27b0")
    if res.energia_secado_MJ is not None and res.energia_secado_MJ > 0:
        etiquetas.append(t("p7.balance_fig.evaporacion"))
        valores.append(res.energia_secado_MJ)
        colores.append("#4caf50")

    if not etiquetas:
        return None

    fig = go.Figure(
        go.Bar(
            x=etiquetas,
            y=valores,
            marker_color=colores,
            opacity=0.85,
            text=[f"{v:.2f} MJ" for v in valores],
            textposition="outside",
        )
    )
    fig.update_yaxes(title_text=t("p7.balance_fig.eje"))
    fig.update_layout(
        title_text=t("p7.balance_fig.titulo"),
        height=350,
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Generador de texto de resultados completos (mejora 5)
# ---------------------------------------------------------------------------


def _bloque_meta_emplazamiento_clima(proyecto) -> tuple[list[str], dict]:
    """Devuelve (líneas de texto, dict para JSON) de meta + P1 + P2 + clima."""
    cfg = getattr(proyecto, "configuracion", None)
    empl = getattr(proyecto, "emplazamiento", None)
    clima = getattr(proyecto, "clima", None)
    meta = getattr(proyecto, "meta", None)

    lines: list[str] = ["METADATOS DEL PROYECTO"]
    json_meta: dict = {}
    if meta is not None:
        lines += [
            f"  Nombre              : {meta.nombre}",
            f"  Autor               : {meta.autor or '(no especificado)'}",
            f"  Fecha creación      : {meta.fecha_creacion.isoformat()}",
            f"  Fecha modificación  : {meta.fecha_modificacion.isoformat()}",
            f"  Versión software    : {meta.version_software}",
        ]
        if meta.notas:
            lines.append(f"  Notas               : {meta.notas}")
        json_meta = {
            "nombre": meta.nombre,
            "autor": meta.autor,
            "fecha_creacion": meta.fecha_creacion.isoformat(),
            "fecha_modificacion": meta.fecha_modificacion.isoformat(),
            "version_software": meta.version_software,
            "notas": meta.notas,
        }

    lines += ["", "TIPOLOGÍA Y MODO DE ANÁLISIS (P1)"]
    json_cfg: dict = {}
    if cfg is not None:
        lines += [
            f"  Tipología           : {cfg.tipologia.value}",
            f"  Modo análisis       : {cfg.modo_analisis.value}",
            f"  Día de análisis     : {cfg.dia_analisis.value}",
        ]
        if cfg.fecha_especifica is not None:
            lines.append(f"  Fecha específica    : {cfg.fecha_especifica.isoformat()}")
        json_cfg = {
            "tipologia": cfg.tipologia.value,
            "modo_analisis": cfg.modo_analisis.value,
            "dia_analisis": cfg.dia_analisis.value,
            "fecha_especifica": (
                cfg.fecha_especifica.isoformat() if cfg.fecha_especifica else None
            ),
        }
        # Gran escala: el subtipo (batch/semicontinuo) distingue el secador.
        _subtipo = getattr(cfg, "subtipo_gran_escala", None)
        if cfg.tipologia == Tipologia.GRAN_ESCALA and _subtipo is not None:
            lines.append(f"  Subtipo gran escala : {_subtipo.value}")
            json_cfg["subtipo_gran_escala"] = _subtipo.value
        # Modo ventana: el lapso y el paso de trabajo definen la corrida.
        _v_ini = getattr(cfg, "ventana_inicio", None)
        _v_fin = getattr(cfg, "ventana_fin", None)
        if cfg.modo_analisis == ModoAnalisis.VENTANA and _v_ini is not None and _v_fin is not None:
            lines.append(f"  Ventana producción  : {_v_ini.isoformat()} → {_v_fin.isoformat()}")
            json_cfg["ventana_inicio"] = _v_ini.isoformat()
            json_cfg["ventana_fin"] = _v_fin.isoformat()
        _paso_s = getattr(cfg, "paso_trabajo_s", None)
        if _paso_s is not None and float(_paso_s) != 3600.0:
            lines.append(f"  Paso de trabajo     : {float(_paso_s) / 60.0:.0f} min")
        if _paso_s is not None:
            json_cfg["paso_trabajo_s"] = float(_paso_s)
    else:
        lines.append("  (sin configurar)")

    lines += ["", "EMPLAZAMIENTO (P2)"]
    json_empl: dict = {}
    _es_caja_p7 = cfg is not None and cfg.tipologia == Tipologia.CAJA
    if empl is not None:
        lines += [
            f"  Latitud             : {empl.latitud_deg:.4f}°",
            f"  Longitud            : {empl.longitud_deg:.4f}°",
            f"  Altitud             : {empl.altitud_m:.1f} m",
        ]
        if not _es_caja_p7:
            lines += [
                f"  Acimut colector     : {empl.acimut_colector_deg:.1f}° "
                "(convención Duffie: 0°=Sur)",
                f"  Pendiente colector  : {empl.pendiente_colector_deg:.1f}°",
            ]
        lines += [
            f"  Albedo del suelo    : {empl.albedo_suelo:.2f}",
            f"  Zona horaria        : {empl.zona_horaria}",
        ]
        json_empl = {
            "latitud_deg": empl.latitud_deg,
            "longitud_deg": empl.longitud_deg,
            "altitud_m": empl.altitud_m,
            "albedo_suelo": empl.albedo_suelo,
            "zona_horaria": empl.zona_horaria,
        }
        if not _es_caja_p7:
            json_empl["acimut_colector_deg_duffie"] = empl.acimut_colector_deg
            json_empl["pendiente_colector_deg"] = empl.pendiente_colector_deg
    else:
        lines.append("  (sin configurar)")

    fuente_clima = getattr(clima, "fuente", "nasa_power") if clima is not None else "nasa_power"
    _ETIQUETAS_FUENTE = {
        "nasa_power": "NASA POWER",
        "medido": "datos medidos del usuario",
        "hibrido": "híbrido (medido + NASA POWER)",
    }
    lines += ["", f"CLIMA ({_ETIQUETAS_FUENTE.get(fuente_clima, fuente_clima)})"]
    json_clima: dict = {}
    if clima is not None and clima.datos is not None:
        n_total = len(clima.datos)
        T_media_C = (
            float(clima.datos["T_amb_K"].mean()) - 273.15
            if "T_amb_K" in clima.datos.columns
            else None
        )
        GHI_media = (
            float(clima.datos["GHI_Wm2"].mean()) if "GHI_Wm2" in clima.datos.columns else None
        )
        lines += [
            f"  Fuente              : {fuente_clima}",
            f"  Año fuente          : {clima.anio}",
            "  Altitud NASA grid   : "
            + (f"{clima.altitud_nasa_m:.1f} m" if clima.altitud_nasa_m is not None else "—"),
            f"  Horas disponibles   : {n_total}",
            "  T_amb media anual   : " + (f"{T_media_C:.1f} °C" if T_media_C is not None else "—"),
            "  GHI media anual     : "
            + (f"{GHI_media:.0f} W/m²" if GHI_media is not None else "—"),
            f"  Calidad — huecos originales : {clima.calidad.n_huecos_originales}",
            f"  Calidad — interpoladas (h) : {clima.calidad.n_horas_interpoladas}",
            f"  Calidad — bloqueadas (h)   : {clima.calidad.n_horas_bloqueadas}",
            f"  Mayor hueco (h)            : {clima.calidad.mayor_hueco_h}",
        ]
        procedencia = getattr(clima, "procedencia", None)
        if procedencia:
            lines.append(
                "  Procedencia         : "
                + ", ".join(f"{col}:{proc}" for col, proc in sorted(procedencia.items()))
            )
        if getattr(clima, "frecuencia_nativa_s", None):
            lines.append(f"  Paso nativo medido  : {clima.frecuencia_nativa_s:.0f} s")
        json_clima = {
            "anio": clima.anio,
            "fuente": fuente_clima,
            "procedencia": procedencia,
            "frecuencia_nativa_s": getattr(clima, "frecuencia_nativa_s", None),
            "altitud_nasa_m": clima.altitud_nasa_m,
            "n_horas": n_total,
            "T_amb_media_C": T_media_C,
            "GHI_media_W_m2": GHI_media,
            "calidad": {
                "n_huecos_originales": clima.calidad.n_huecos_originales,
                "n_horas_interpoladas": clima.calidad.n_horas_interpoladas,
                "n_horas_bloqueadas": clima.calidad.n_horas_bloqueadas,
                "mayor_hueco_h": clima.calidad.mayor_hueco_h,
                "decision_usuario": clima.calidad.decision_usuario,
            },
        }
    else:
        lines.append("  (sin datos descargados)")

    return lines, {
        "meta": json_meta,
        "configuracion": json_cfg,
        "emplazamiento": json_empl,
        "clima": json_clima,
    }


def _texto_resultados_completo(
    proyecto,
    res: "ResultadosCompletos",
    T_amb_C: Optional[float] = None,
    I_g: Optional[float] = None,
    v_viento: Optional[float] = None,
    HR_cam_pct: Optional[float] = None,
    res_anual=None,
) -> str:
    from datetime import date

    from core import catalogo

    def desc(cat_dict: dict, id_mat: str) -> str:
        return cat_dict.get(id_mat, {}).get("descripcion", id_mat)

    sep = "=" * 60
    lines = [
        sep,
        "         PREDISEÑO COMPLETO DE SECADOR SOLAR",
        sep,
        f"Fecha de exportación: {date.today()}",
        "",
    ]
    # Bloque P1/P2/clima
    meta_lines, _meta_dict = _bloque_meta_emplazamiento_clima(proyecto)
    lines += meta_lines
    # En modo Ventana no hay sliders de condiciones representativas: el bloque
    # solo se emite cuando las condiciones existen (Constantes/Transitorio).
    if T_amb_C is not None:
        lines += [
            "",
            "CONDICIONES DE OPERACIÓN REPRESENTATIVAS (P7)",
            f"  T ambiente          : {T_amb_C:.1f} °C",
        ]
        if I_g is not None:
            lines.append(f"  Irradiancia (POA)   : {I_g:.0f} W/m²")
        if v_viento is not None:
            lines.append(f"  Velocidad viento    : {v_viento:.1f} m/s")
        if HR_cam_pct is not None:
            lines.append(f"  HR aire entrada     : {HR_cam_pct:.0f} %")

    # --- Colector ---
    if proyecto.colector is not None:
        u = proyecto.colector.unidad
        b = proyecto.colector.banco
        lines += [
            "",
            "COLECTOR SOLAR",
            f"  Cubierta  : {desc(catalogo.CUBIERTAS, u.id_cubierta)}",
            f"              e = {u.espesor_cubierta_m * 1000:.1f} mm | N° = {u.n_cubiertas}",
            f"  Placa     : {desc(catalogo.PLACAS, u.id_placa)}",
            f"  Aislante  : {desc(catalogo.AISLANTES, u.id_aislante)}",
            f"  Fondo     : {desc(catalogo.FONDOS, u.id_fondo)}",
            f"  Geometría : {u.ancho_m:.2f} m × {u.largo_m:.2f} m × {u.espaciado_m * 1000:.0f} mm",
            f"  Vel. dis. : {u.velocidad_diseno_ms:.2f} m/s",
            f"  Banco     : {b.n_serie} serie × {b.n_paralelo} paralelo",
            f"  Área total: {b.n_serie * b.n_paralelo * u.area_captacion_m2():.2f} m²",
        ]

    # --- Cámara ---
    if proyecto.camara is not None:
        g = proyecto.camara.geometria
        cn = proyecto.camara.construccion
        bj = proyecto.camara.bandejas
        c = proyecto.camara.carga_producto
        f = proyecto.camara.flujo
        lines += [
            "",
            "CÁMARA DE SECADO",
            f"  Geometría  : {g.largo_m:.2f} m × {g.ancho_m:.2f} m × {g.alto_m:.2f} m",
            f"  Orientación: acimut {g.acimut_camara_deg:.1f}° Duffie | "
            f"techo {g.pendiente_techo_deg:.1f}° (cae hacia {g.cara_caida_techo})",
            f"  Bandejas   : {bj.n_bandejas} | e capa = {bj.espesor_capa_m * 100:.1f} cm",
            f"  Producto   : {c.producto_id} | masa = {c.masa_total_kg:.1f} kg",
            f"  Caudal     : {f.caudal_masico_kg_s:.4f} kg/s | {f.direccion_flujo.value}",
        ]
        if cn.cubierta_translucida_id is not None:
            lines.append(f"  Caras translúcidas: {', '.join(cn.caras_translucidas_activas())}")

    # --- Auxiliar ---
    if proyecto.auxiliar is not None:
        aux_cfg = proyecto.auxiliar
        lines += [
            "",
            "AUXILIAR TÉRMICO",
            f"  Tipo  : {aux_cfg.tipo.value}",
            f"  Potencia: {aux_cfg.potencia_nominal_W / 1000:.2f} kW | Modo: {aux_cfg.modo_operacion.value}",
        ]

    # --- Motor ---
    if proyecto.motor is not None:
        mot_cfg = proyecto.motor
        lines += [
            "",
            "MOTOR / VENTILADOR",
            f"  Tipo  : {mot_cfg.tipo_accionamiento.value}",
            f"  ΔP    : {mot_cfg.perdida_carga_total_Pa:.1f} Pa",
        ]
        if mot_cfg.potencia_a_instalar_W:
            lines.append(f"  P inst.: {mot_cfg.potencia_a_instalar_W:.1f} W")

    # ---- RESULTADOS ----
    # Se usa getattr para tolerar tanto ResultadosCompletos (modo "constantes")
    # como ResultadosCompletosTransitorio (modo "horizonte"), que tienen
    # firmas distintas (p.ej. el transitorio no expone .colector como solver).
    lines += ["", sep, "  RESULTADOS", sep]

    col = getattr(res, "colector", None)
    if col is not None:
        _t_sal = getattr(col, "T_salida_K", getattr(col, "T_salida_mezcla_K", None))
        _regimen = getattr(
            col, "regimen_flujo", getattr(col, "regimen_ci", getattr(col, "regimen_cs", "—"))
        )
        lines += [
            "COLECTOR",
            f"  T entrada : {kelvin_a_celsius(col.T_entrada_K):.1f} °C",
            f"  T salida  : {kelvin_a_celsius(_t_sal):.1f} °C" if _t_sal else "  T salida  : —",
            f"  Q útil    : {col.Q_util_W:.0f} W",
            f"  η térmica : {col.eta_termica:.1%}",
            f"  Régimen   : {_regimen or '—'}",
        ]
        _re = getattr(col, "Re_medio", getattr(col, "Re_ci", getattr(col, "Re_cs", None)))
        _hint = getattr(
            col, "h_int_medio", getattr(col, "h_int_ci", getattr(col, "h_int_cs", None))
        )
        if _re:
            lines.append(f"  Re medio  : {_re:.0f} | h_int = {_hint:.1f} W/(m²·K)")

    aux = getattr(res, "auxiliar", None)
    if aux is not None:
        # En transitorio aux.delta_T_K y aux.Q_efectivo_W son arrays;
        # mostramos sólo si son escalares (constantes).
        dt_aux = getattr(aux, "delta_T_K", None)
        q_aux = getattr(aux, "Q_efectivo_W", None)
        es_escalar = dt_aux is not None and isinstance(dt_aux, (int, float))
        if es_escalar:
            lines += [
                "",
                "AUXILIAR",
                f"  ΔT       : {dt_aux:.1f} °C",
                f"  Q efect. : {q_aux:.0f} W" if isinstance(q_aux, (int, float)) else "",
            ]
        else:
            # Transitorio: mostramos series resumidas si están
            dt_max = getattr(aux, "delta_T_max_K", None)
            q_max = getattr(aux, "Q_max_W", None)
            horas_act = getattr(aux, "horas_activo_s", None)
            lines += ["", "AUXILIAR (transitorio)"]
            if dt_max is not None:
                lines.append(f"  ΔT máx        : {dt_max:.1f} K")
            if q_max is not None:
                lines.append(f"  Q máx         : {q_max:.0f} W")
            if horas_act is not None:
                lines.append(f"  Horas activo  : {horas_act / 3600.0:.2f} h")

    # Cámara: resultado estático o termodinámico
    _cam_show = getattr(res, "camara", None)
    if _cam_show is not None:
        t_h_cam, masa_cam, status_cam, _ok = _resumen_camara(_cam_show)
        T_ent_cam_K = getattr(res, "T_entrada_camara_K", None)
        lines += [
            "",
            "CÁMARA",
            (
                f"  T oper.       : {kelvin_a_celsius(T_ent_cam_K):.1f} °C"
                if T_ent_cam_K
                else "  T oper.       : —"
            ),
        ]
        if isinstance(_cam_show, ResultadoMotorTermodinamico):
            X_final = float(_cam_show.X_prod_kg_kg[-1]) if len(_cam_show.X_prod_kg_kg) else 0.0
            T_prod_final_C = (
                float(_cam_show.T_prod_K[-1]) - 273.15 if len(_cam_show.T_prod_K) else 0.0
            )
            lines += [
                "  Modo cálculo  : termodinámico",
                "  Tiempo secado : "
                + (f"{t_h_cam:.2f} h" if t_h_cam is not None else "no convergió"),
                f"  Agua evap.    : {masa_cam:.3f} kg",
                f"  X final       : {X_final:.4f} kg/kg ms",
                f"  T prod. final : {T_prod_final_C:.1f} °C",
                f"  Status        : {status_cam}",
            ]

    res_chim = getattr(res, "chimenea", None)
    if res_chim is not None:
        m_raw = res_chim.get("m_punto_kgs", 0.0)
        es_serie = hasattr(m_raw, "__len__") and not isinstance(m_raw, str)
        if es_serie:
            # Modo transitorio: series horarias. Mostramos resumen escalar.
            import numpy as _np

            m_arr = _np.asarray(m_raw, dtype=float)
            T_chim_arr = _np.asarray(res_chim.get("T_chim_K", []), dtype=float)
            dPT_arr = _np.asarray(res_chim.get("delta_P_tiro_Pa", []), dtype=float)
            v_arr = _np.asarray(res_chim.get("v_chim_ms", []), dtype=float)
            Re_arr = _np.asarray(res_chim.get("Re_chimenea", []), dtype=float)
            lines += [
                "",
                "CHIMENEA SOLAR (lazo natural — transitorio)",
                f"  ṁ promedio     : {res_chim.get('m_promedio_kgs', float(_np.mean(m_arr))) * 1000:.2f} g/s",
                f"  ṁ máximo       : {res_chim.get('m_max_kgs', float(_np.max(m_arr))) * 1000:.2f} g/s",
                f"  v chim media   : {float(_np.mean(v_arr)):.2f} m/s",
                f"  Re medio       : {float(_np.mean(Re_arr)):.0f}",
                f"  ΔP tiro medio  : {float(_np.mean(dPT_arr)):.2f} Pa",
                (
                    (
                        f"  T_chim min/max : {T_chim_arr.min()-273.15:.1f} / "
                        f"{T_chim_arr.max()-273.15:.1f} °C"
                    )
                    if T_chim_arr.size
                    else "  T_chim         : —"
                ),
                f"  Horas sin tiro : {int(res_chim.get('horas_sin_tiro', 0))} h",
                f"  H efectiva     : {res_chim.get('H_eff_m', 0.0):.2f} m",
                f"  Picard         : {res_chim.get('iteraciones', '?')} iter, "
                f"{'convergió' if res_chim.get('convergio') else 'NO convergió'} "
                f"(ΔT_max final {res_chim.get('delta_T_chim_final_K', 0.0):.2f} K)",
            ]
        else:
            m_punto = float(m_raw)
            lines += [
                "",
                "CHIMENEA SOLAR (convección natural)",
                f"  Caudal natural : {m_punto * 1000:.2f} g/s "
                f"({m_punto / 1.1 * 3600.0:.1f} m³/h)",
                f"  v chimenea     : {res_chim.get('v_chim_ms', 0.0):.2f} m/s",
                f"  Re chimenea    : {res_chim.get('Re_chimenea', 0.0):.0f}",
                f"  ΔP tiro        : {res_chim.get('delta_P_tiro_Pa', 0.0):.2f} Pa",
                f"  ΔP ducto       : {res_chim.get('delta_P_chimenea_Pa', 0.0):.2f} Pa",
                f"  ΔP resto lazo  : {res_chim.get('delta_P_resto_Pa', 0.0):.2f} Pa",
                f"  H efectiva     : {res_chim.get('H_eff_m', 0.0):.2f} m",
            ]
            if "iteraciones" in res_chim:
                lines.append(
                    f"  Picard         : {res_chim['iteraciones']} iter, "
                    f"{'convergió' if res_chim.get('convergio') else 'NO convergió'} "
                    f"(ΔT final {res_chim.get('delta_T_chim_final_K', 0.0):.2f} K)"
                )
            desv = _desviacion_caudal_natural(res_chim, proyecto)
            if desv is not None and desv > 0.30:
                m_design = proyecto.camara.flujo.caudal_masico_kg_s
                lines.append(
                    f"  ⚠ Desviación vs caudal de diseño "
                    f"({m_design * 1000:.1f} g/s): {desv:.0%}"
                )
        for adv in res_chim.get("advertencias", []) or []:
            if adv:
                lines.append(f"  ⚠ {adv}")

    energia_total = getattr(res, "energia_total_MJ", None)
    if energia_total:
        lines += [
            "",
            "BALANCE ENERGÉTICO",
            f"  E solar útil : {getattr(res, 'energia_solar_util_MJ', 0) or 0:.4f} MJ",
            f"  E auxiliar   : {getattr(res, 'energia_auxiliar_MJ', 0) or 0:.4f} MJ",
            f"  E motor      : {getattr(res, 'energia_motor_MJ', 0) or 0:.4f} MJ",
            f"  E secado     : {getattr(res, 'energia_secado_MJ', 0) or 0:.4f} MJ",
        ]
        cop = getattr(res, "COP_secado", None)
        if cop:
            lines.append(f"  COP secado   : {cop:.4f}")
        f_sol = getattr(res, "fraccion_solar", None)
        if f_sol is not None:
            lines.append(f"  Fracción solar: {f_sol:.1%}")

    # Producción en ventana (gran escala) y operación anual, si aplican.
    from calculos.simulacion_ventana import ResultadoVentana

    if isinstance(res, ResultadoVentana):
        lines += _texto_resultado_ventana(res)
    if res_anual is not None:
        lines += _texto_operacion_anual(res_anual)

    lines.append("")
    return "\n".join(lines)


def _json_resultados_completo(
    proyecto,
    res: "ResultadosCompletos",
    T_amb_C: Optional[float] = None,
    I_g: Optional[float] = None,
    v_viento: Optional[float] = None,
    HR_cam_pct: Optional[float] = None,
    res_anual=None,
) -> dict:
    """Snapshot completo reconstruible (dict) del prediseño."""
    from datetime import date

    from ui.p3_colector import _json_config_colector
    from ui.p4_camara import _json_config_camara
    from ui.p5_auxiliar import _json_config_auxiliar
    from ui.p6_motor import _json_config_chimenea, _json_config_motor

    _, meta_dict = _bloque_meta_emplazamiento_clima(proyecto)

    snapshot: dict = {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "prediseno_completo",
        **meta_dict,
        "condiciones_operacion_P7": {
            "T_amb_C": T_amb_C,
            "I_g_POA_W_m2": I_g,
            "v_viento_ms": v_viento,
            "HR_camara_pct": HR_cam_pct,
        },
        "colector": (
            _json_config_colector(proyecto.colector, st.session_state.get("p3_eval"))
            if proyecto.colector is not None
            else None
        ),
        "camara": (
            _json_config_camara(proyecto.camara, st.session_state)
            if proyecto.camara is not None
            else None
        ),
        "auxiliar": (
            _json_config_auxiliar(proyecto.auxiliar) if proyecto.auxiliar is not None else None
        ),
        "motor": (_json_config_motor(proyecto.motor) if proyecto.motor is not None else None),
        "chimenea": (
            _json_config_chimenea(proyecto.chimenea)
            if getattr(proyecto, "chimenea", None) is not None
            else None
        ),
    }

    # Resultados globales del prediseño (P7)
    res_globales: dict = {
        "T_entrada_camara_K": getattr(res, "T_entrada_camara_K", None),
        "T_entrada_camara_C": (
            kelvin_a_celsius(res.T_entrada_camara_K)
            if getattr(res, "T_entrada_camara_K", None) is not None
            else None
        ),
        "energia_total_MJ": getattr(res, "energia_total_MJ", None),
        "energia_solar_util_MJ": getattr(res, "energia_solar_util_MJ", None),
        "energia_auxiliar_MJ": getattr(res, "energia_auxiliar_MJ", None),
        "energia_motor_MJ": getattr(res, "energia_motor_MJ", None),
        "energia_secado_MJ": getattr(res, "energia_secado_MJ", None),
        "COP_secado": getattr(res, "COP_secado", None),
        "fraccion_solar": getattr(res, "fraccion_solar", None),
    }
    # Sub-bloques de resultados si existen
    if getattr(res, "colector", None) is not None:
        col_r = res.colector
        res_globales["colector"] = {
            "T_entrada_K": getattr(col_r, "T_entrada_K", None),
            "T_salida_K": (
                getattr(col_r, "T_salida_K", None) or getattr(col_r, "T_salida_mezcla_K", None)
            ),
            "Q_util_W": getattr(col_r, "Q_util_W", None),
            "eta_termica": getattr(col_r, "eta_termica", None),
            "regimen_flujo": (
                getattr(col_r, "regimen_flujo", None)
                or getattr(col_r, "regimen_ci", None)
                or getattr(col_r, "regimen_cs", None)
            ),
            "Re_medio": (
                getattr(col_r, "Re_medio", None)
                or getattr(col_r, "Re_ci", None)
                or getattr(col_r, "Re_cs", None)
            ),
            "h_int_medio": (
                getattr(col_r, "h_int_medio", None)
                or getattr(col_r, "h_int_ci", None)
                or getattr(col_r, "h_int_cs", None)
            ),
        }
    if getattr(res, "auxiliar", None) is not None:
        aux_r = res.auxiliar
        dt = getattr(aux_r, "delta_T_K", None)
        q = getattr(aux_r, "Q_efectivo_W", None)
        if isinstance(dt, (int, float)) or dt is None:
            # ResultadoAuxiliar (constantes): escalares
            res_globales["auxiliar"] = {
                "delta_T_K": dt,
                "Q_efectivo_W": q if isinstance(q, (int, float)) else None,
            }
        else:
            # ResultadosAuxiliarTransitorio: arrays — guardo solo el resumen
            res_globales["auxiliar"] = {
                "tipo": "transitorio",
                "delta_T_max_K": getattr(aux_r, "delta_T_max_K", None),
                "Q_max_W": getattr(aux_r, "Q_max_W", None),
                "horas_activo_s": getattr(aux_r, "horas_activo_s", None),
                "fraccion_horas_activo": getattr(aux_r, "fraccion_horas_activo", None),
            }
    if getattr(res, "camara", None) is not None:
        cam_r = res.camara
        if isinstance(cam_r, ResultadoMotorTermodinamico):
            t_h, masa, status, ok = _resumen_camara(cam_r)
            res_globales["camara"] = {
                "modo_calculo": "termodinamico",
                "t_secado_h": t_h,
                "masa_evaporada_kg": float(masa),
                "status": status,
                "objetivo_alcanzado": ok,
                "X_final": float(cam_r.X_prod_kg_kg[-1]) if len(cam_r.X_prod_kg_kg) else None,
                "T_prod_final_C": (
                    float(cam_r.T_prod_K[-1]) - 273.15 if len(cam_r.T_prod_K) else None
                ),
            }
    res_chim = getattr(res, "chimenea", None)
    if res_chim is not None:
        m_raw = res_chim.get("m_punto_kgs", 0.0)
        es_serie = hasattr(m_raw, "__len__") and not isinstance(m_raw, str)
        if es_serie:
            import numpy as _np

            def _arr(k):
                return _np.asarray(res_chim.get(k, []), dtype=float).tolist()

            res_globales["chimenea"] = {
                "modo": "transitorio",
                "m_promedio_kgs": float(
                    res_chim.get(
                        "m_promedio_kgs",
                        float(_np.mean(m_raw)),
                    )
                ),
                "m_max_kgs": float(
                    res_chim.get(
                        "m_max_kgs",
                        float(_np.max(m_raw)),
                    )
                ),
                "horas_sin_tiro": int(res_chim.get("horas_sin_tiro", 0)),
                "H_eff_m": float(res_chim.get("H_eff_m", 0.0)),
                "iteraciones": int(res_chim.get("iteraciones", 0)),
                "convergio": bool(res_chim.get("convergio", False)),
                "delta_T_chim_final_K": float(res_chim.get("delta_T_chim_final_K", 0.0)),
                "advertencias": list(res_chim.get("advertencias", []) or []),
                "series": {
                    "t_s": _arr("t_s"),
                    "m_punto_kgs": _arr("m_punto_kgs"),
                    "v_chim_ms": _arr("v_chim_ms"),
                    "Re_chimenea": _arr("Re_chimenea"),
                    "T_chim_K": _arr("T_chim_K"),
                    "delta_P_tiro_Pa": _arr("delta_P_tiro_Pa"),
                    "delta_P_chimenea_Pa": _arr("delta_P_chimenea_Pa"),
                    "delta_P_resto_Pa": _arr("delta_P_resto_Pa"),
                },
            }
        else:
            m_punto = float(m_raw)
            res_globales["chimenea"] = {
                "modo": "constantes",
                "m_punto_kgs": m_punto,
                "Q_volumetrico_m3_h": m_punto / 1.1 * 3600.0,
                "v_chim_ms": float(res_chim.get("v_chim_ms", 0.0)),
                "Re_chimenea": float(res_chim.get("Re_chimenea", 0.0)),
                "delta_P_tiro_Pa": float(res_chim.get("delta_P_tiro_Pa", 0.0)),
                "delta_P_chimenea_Pa": float(res_chim.get("delta_P_chimenea_Pa", 0.0)),
                "delta_P_resto_Pa": float(res_chim.get("delta_P_resto_Pa", 0.0)),
                "H_eff_m": float(res_chim.get("H_eff_m", 0.0)),
                "iteraciones": int(res_chim.get("iteraciones", 0)) or None,
                "convergio": bool(res_chim.get("convergio", False)),
                "delta_T_chim_final_K": float(res_chim.get("delta_T_chim_final_K", 0.0)),
                "T_chim_K": float(res_chim.get("T_chim_K", 0.0)),
                "advertencias": list(res_chim.get("advertencias", []) or []),
                "desviacion_vs_diseno": _desviacion_caudal_natural(res_chim, proyecto),
            }
    snapshot["resultados_globales"] = res_globales

    # Producción en ventana (gran escala): bloque propio del ResultadoVentana.
    from calculos.simulacion_ventana import ResultadoVentana

    if isinstance(res, ResultadoVentana):
        snapshot["resultado_ventana"] = _json_resultado_ventana(res)

    # Operación anual de cámara (si P4 la corrió): convive con el resto.
    if res_anual is not None:
        snapshot["operacion_anual"] = _json_operacion_anual(res_anual)
    return snapshot


# ---------------------------------------------------------------------------
# Exports del modo Ventana (gran escala) y de la operación anual — helpers
# puros (sin session_state): los consumen TXT, JSON y el reporte PDF.
# ---------------------------------------------------------------------------


def _texto_resultado_ventana(res) -> list[str]:
    """Bloque de texto (ES, artefacto de exportación) de un ResultadoVentana."""
    lines = [
        "",
        "PRODUCCIÓN EN VENTANA (GRAN ESCALA)",
        f"  Subtipo             : {res.subtipo}",
        f"  Horizonte           : {res.horizonte_s / 86400.0:.1f} días "
        f"({res.horizonte_s / 3600.0:.0f} h)",
        f"  Producto seco       : {res.masa_seca_producida_kg:.1f} kg",
        f"  Agua evaporada      : {res.masa_evaporada_kg:.1f} kg",
    ]
    if res.tasa_regimen_kg_dia is not None:
        lines.append(f"  Tasa de régimen     : {res.tasa_regimen_kg_dia:.1f} kg/día")
    if res.lena_consumida_kg > 0:
        lines.append(f"  Leña consumida      : {res.lena_consumida_kg:.1f} kg")
    lines.append(f"  Estado              : {res.status}")

    if res.subtipo == "BATCH":
        lines += [
            "",
            "  LOTES (BATCH)",
            f"    Lotes completos   : {res.n_batches_completos}",
        ]
        if res.t_secado_medio_s is not None:
            lines.append(f"    t secado medio    : {res.t_secado_medio_s / 3600.0:.1f} h")
        if res.batch_en_progreso:
            lines.append("    (quedó un lote sin completar al cierre de la ventana)")
    elif res.subtipo == "SEMICONTINUO":
        lines += [
            "",
            "  TÚNEL SEMICONTINUO",
            f"    Avances (columnas descargadas): {res.n_avances}",
        ]
        if res.X_salida_regimen is not None:
            lines.append(f"    X salida en régimen: {res.X_salida_regimen:.3f} kg/kg seco")
        if res.throughput_fresco_kg_dia is not None:
            lines.append(f"    Throughput fresco  : {res.throughput_fresco_kg_dia:.1f} kg/día")
        if res.intervalo_avance_s is not None:
            lines.append(f"    Cadencia de avance : {res.intervalo_avance_s / 3600.0:.1f} h")
        if res.perfil_X_zonas is not None and len(res.perfil_X_zonas):
            lines.append("    Perfil X por zona (entrada → salida):")
            for i, x_z in enumerate(res.perfil_X_zonas):
                t_z = (
                    f" | T aire = {float(res.perfil_T_aire_zonas_K[i]) - 273.15:.1f} °C"
                    if res.perfil_T_aire_zonas_K is not None and len(res.perfil_T_aire_zonas_K) > i
                    else ""
                )
                lines.append(f"      Zona {i + 1}: X = {float(x_z):.3f} kg/kg seco{t_z}")

    if res.cano_delta_P_Pa is not None:
        lines += [
            "",
            "  CAÑO MAESTRO (diagnóstico sobre el lapso)",
            f"    ΔT media          : {res.cano_delta_T_media_K:+.2f} K",
            f"    ΔT mínima (peor)  : {res.cano_delta_T_minima_K:+.2f} K",
            f"    ΔP al caudal sist.: {res.cano_delta_P_Pa:.1f} Pa",
        ]

    for adv in res.advertencias or []:
        lines.append(f"  ⚠ {adv}")
    return lines


def _json_resultado_ventana(res) -> dict:
    """Dict JSON-serializable (vía to_jsonable) de un ResultadoVentana."""

    def _lista(arr):
        return [float(v) for v in arr] if arr is not None else None

    return {
        "subtipo": res.subtipo,
        "horizonte_s": res.horizonte_s,
        "masa_seca_producida_kg": res.masa_seca_producida_kg,
        "masa_evaporada_kg": res.masa_evaporada_kg,
        "tasa_regimen_kg_dia": res.tasa_regimen_kg_dia,
        "lena_consumida_kg": res.lena_consumida_kg,
        "status": res.status,
        # BATCH
        "n_batches_completos": res.n_batches_completos,
        "t_secado_medio_s": res.t_secado_medio_s,
        "batch_en_progreso": res.batch_en_progreso,
        # SEMICONTINUO
        "n_avances": res.n_avances,
        "X_salida_regimen": res.X_salida_regimen,
        "throughput_fresco_kg_dia": res.throughput_fresco_kg_dia,
        "perfil_X_zonas": _lista(res.perfil_X_zonas),
        "perfil_T_aire_zonas_K": _lista(res.perfil_T_aire_zonas_K),
        "perfil_omega_aire_zonas": _lista(res.perfil_omega_aire_zonas),
        "X_salida_por_avance": _lista(res.X_salida_por_avance),
        "T_prod_salida_por_avance_K": _lista(res.T_prod_salida_por_avance_K),
        "intervalo_avance_s": res.intervalo_avance_s,
        "t0_utc": (res.t0_utc.isoformat() if res.t0_utc is not None else None),
        # Caño maestro (diagnóstico)
        "cano_delta_T_media_K": res.cano_delta_T_media_K,
        "cano_delta_T_minima_K": res.cano_delta_T_minima_K,
        "cano_delta_P_Pa": res.cano_delta_P_Pa,
        # Estados del aire (carta psicrométrica)
        "aire_T_amb_K": res.aire_T_amb_K,
        "aire_T_ent_K": res.aire_T_ent_K,
        "aire_omega_ent": res.aire_omega_ent,
        "aire_T_salida_K": res.aire_T_salida_K,
        "aire_omega_salida": res.aire_omega_salida,
        "advertencias": list(res.advertencias or []),
    }


def _texto_operacion_anual(res_anual) -> list[str]:
    """Bloque de texto (ES) del análisis anual sobre 8760 h."""

    def _f(v, fmt=".1f", suf=""):
        return f"{v:{fmt}}{suf}" if v is not None else "n/d"

    lines = [
        "",
        "ANÁLISIS ANUAL (8760 h de clima real)",
        f"  Producto seco       : {res_anual.masa_seca_anual_kg:.1f} kg",
        f"  Agua evaporada      : {res_anual.masa_evaporada_anual_kg:.1f} kg",
        f"  Lotes completados   : {res_anual.n_lotes_completos}"
        f" (sin completar: {res_anual.n_lotes_frustrados})",
        f"  Duración de lote    : media {_f(res_anual.duracion_media_h)} h, "
        f"p50 {_f(res_anual.duracion_p50_h)} h, p90 {_f(res_anual.duracion_p90_h)} h",
        f"  E solar incidente   : {res_anual.E_solar_anual_MJ:.0f} MJ",
        f"  Q útil del colector : {res_anual.Q_util_colector_MJ:.0f} MJ",
        f"  E auxiliar          : {res_anual.E_auxiliar_MJ:.0f} MJ",
        f"  Leña consumida      : {res_anual.lena_consumida_kg:.1f} kg",
        f"  Fracción solar      : {_f(res_anual.fraccion_solar, '.3f')}",
        f"  η secado (drying)   : {_f(res_anual.eta_drying_anual, '.4f')}",
        f"  η total             : {_f(res_anual.eta_total_anual, '.4f')}",
        f"  Aprovech. del aire  : {_f(res_anual.aprovechamiento_aire, '.4f')}"
        "  (no comparable con η_pickup de Augustus Leon)",
        f"  Energía específica  : {_f(res_anual.energia_especifica_MJ_kg)} MJ/kg agua",
        f"  Días operables      : {res_anual.dias_operables}"
        f" (umbral {res_anual.umbral_dia_operable_MJ_m2:.1f} MJ/m²·día)",
        "  NOTA: recarga inmediata sin turnos ni tiempo de carga → cota superior.",
        "",
        "  DETALLE MENSUAL",
        "  mes | seco[kg] | agua[kg] | lotes | sin_compl | dur[h] | oper/días | E_sol[MJ]",
    ]
    for p in res_anual.puntos_mensuales:
        lines.append(
            f"  {p.mes:3d} | {p.masa_seca_kg:8.1f} | {p.masa_evaporada_kg:8.1f} | "
            f"{p.lotes_completos:5d} | {p.lotes_frustrados:9d} | "
            f"{_f(p.duracion_media_h):>6} | {p.dias_operables:4d}/{p.dias:<4d} | "
            f"{p.E_solar_MJ:9.0f}"
        )
    for adv in res_anual.advertencias or []:
        lines.append(f"  ⚠ {adv}")
    return lines


def _json_operacion_anual(res_anual) -> dict:
    """Dict JSON-serializable de ResultadosAnual (modo anual 8760 h)."""
    return {
        "masa_seca_anual_kg": res_anual.masa_seca_anual_kg,
        "masa_evaporada_anual_kg": res_anual.masa_evaporada_anual_kg,
        "n_lotes_completos": res_anual.n_lotes_completos,
        "n_lotes_frustrados": res_anual.n_lotes_frustrados,
        "duracion_media_h": res_anual.duracion_media_h,
        "duracion_p50_h": res_anual.duracion_p50_h,
        "duracion_p90_h": res_anual.duracion_p90_h,
        "E_solar_anual_MJ": res_anual.E_solar_anual_MJ,
        "Q_util_colector_MJ": res_anual.Q_util_colector_MJ,
        "E_auxiliar_MJ": res_anual.E_auxiliar_MJ,
        "lena_consumida_kg": res_anual.lena_consumida_kg,
        "fraccion_solar": res_anual.fraccion_solar,
        "eta_drying_anual": res_anual.eta_drying_anual,
        "eta_total_anual": res_anual.eta_total_anual,
        "aprovechamiento_aire": res_anual.aprovechamiento_aire,
        "energia_especifica_MJ_kg": res_anual.energia_especifica_MJ_kg,
        "dias_operables": res_anual.dias_operables,
        "umbral_dia_operable_MJ_m2": res_anual.umbral_dia_operable_MJ_m2,
        "horas_simuladas": res_anual.horas_simuladas,
        "area_colector_m2": res_anual.area_colector_m2,
        "status": res_anual.status,
        "advertencias": list(res_anual.advertencias or []),
        "puntos_mensuales": [
            {
                "mes": p.mes,
                "masa_seca_kg": p.masa_seca_kg,
                "masa_evaporada_kg": p.masa_evaporada_kg,
                "lotes_completos": p.lotes_completos,
                "lotes_frustrados": p.lotes_frustrados,
                "duracion_media_h": p.duracion_media_h,
                "dias_operables": p.dias_operables,
                "dias": p.dias,
                "E_solar_MJ": p.E_solar_MJ,
                "eta_drying": p.eta_drying,
                "energia_especifica_MJ_kg": p.energia_especifica_MJ_kg,
            }
            for p in res_anual.puntos_mensuales
        ],
    }


# ---------------------------------------------------------------------------
# Corridas paramétricas (barridos)
# ---------------------------------------------------------------------------

_PALETA_BARRIDO = ("#1f77b4", "#d62728", "#2ca02c")  # azul, rojo, verde
_MAX_BARRIDOS = 3
_N_DEFAULT_POR_MODO = {"constantes": 7, "transitorio": 5, "anual": 3}


def _paleta_color_barrido(indice: int) -> str:
    """Color fijo de la paleta de barridos según índice (cicla si excede)."""
    return _PALETA_BARRIDO[indice % len(_PALETA_BARRIDO)]


def _barrido_a_dataframe(resultado):
    """Convierte un ResultadosBarrido en DataFrame (valor + KPIs + error)."""
    import pandas as pd

    meta = resultado.parametro_meta
    col_valor = f"{meta.label} [{meta.unidad_ui}]"
    filas = []
    for pt in resultado.puntos:
        fila = {col_valor: pt.valor_ui}
        fila.update(pt.kpis)
        fila["error"] = pt.error
        filas.append(fila)
    return pd.DataFrame(filas)


def _bounds_ui_parametro(parametro) -> tuple[float, float]:
    """Cotas en unidad de UI por muestreo de ``si_a_ui`` (robusto si no es monótona)."""
    lo, hi = parametro.valor_min_si, parametro.valor_max_si
    muestras = [parametro.si_a_ui(lo + f * (hi - lo)) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    return min(muestras), max(muestras)


def _valor_actual_si_barrido(proyecto, parametro, condiciones):
    """Valor SI actual del parámetro (desde el proyecto, o desde condiciones si es forzante)."""
    if parametro.es_forzante:
        cond = condiciones or {}
        if parametro.nombre_forzante == "HR_camara":
            return cond.get("HR_camara")
        if parametro.nombre_forzante == "T_amb":
            return cond.get("T_amb_K")
        return None
    from operator import attrgetter

    try:
        return attrgetter(parametro.path)(proyecto)
    except AttributeError:
        return None


def _construir_forzantes_builder_desde_meta(horizonte_meta: dict, p3_eval):
    """Cierra un ``forzantes_builder`` que reconstruye las forzantes desde un
    proyecto (posiblemente clonado y mutado por un barrido paramétrico), con
    los mismos kwargs que armaron la forzante congelada de P4.

    Sin esto, un barrido en modo Transitorio sobre un parámetro que solo
    afecta a las forzantes (ej. orientación de la cámara, que entra vía
    ``calculos.radiacion_camara`` al armar ``I_g_W_m2``/``Q_rad_aire_W``, no
    al motor) no tendría ningún efecto: se seguiría reutilizando la forzante
    ya calculada con la orientación original.

    Returns:
        Callable ``proyecto -> ForzantesAire``, o ``None`` si el meta no trae
        los kwargs necesarios (horizontes viejos persistidos antes de S47).
    """
    requeridos = (
        "usar_ventana",
        "tipo_forzantes",
        "T_op_K",
        "HR_op",
        "T_amb_calc_K",
        "n_dias_solicitado",
        "I_g_max_W_m2",
        "P_proyecto_Pa",
        "dias_consecutivos",
    )
    if not all(k in horizonte_meta for k in requeridos):
        return None

    from ui.p4_camara import _construir_forzantes_termodinamico, _construir_forzantes_ventana

    def _builder(proy):
        if horizonte_meta["usar_ventana"]:
            return _construir_forzantes_ventana(
                proyecto=proy,
                caudal_kg_s=proy.camara.flujo.caudal_masico_kg_s,
                P_Pa=horizonte_meta["P_proyecto_Pa"],
            )
        return _construir_forzantes_termodinamico(
            tipo_forzantes=horizonte_meta["tipo_forzantes"],
            T_op_K=horizonte_meta["T_op_K"],
            HR_op=horizonte_meta["HR_op"],
            caudal_kg_s=proy.camara.flujo.caudal_masico_kg_s,
            T_amb_K=horizonte_meta["T_amb_calc_K"],
            n_dias=horizonte_meta["n_dias_solicitado"],
            proyecto=proy,
            p3_eval=p3_eval,
            I_g_max_W_m2=horizonte_meta["I_g_max_W_m2"],
            P_Pa=horizonte_meta["P_proyecto_Pa"],
            dias_consecutivos=horizonte_meta["dias_consecutivos"],
        )

    return _builder


def _render_barridos_parametricos(
    proyecto,
    modo: str,
    *,
    condiciones: dict | None = None,
    forzantes_base=None,
    forzantes_builder=None,
    n_dias: int | None = None,
) -> None:
    """Sección de corridas paramétricas para un modo de cálculo dado.

    Permite variar un parámetro curado (filtrado por tipología y modo), correr
    N simulaciones y comparar hasta ``_MAX_BARRIDOS`` corridas con gráficas
    superpuestas. Estado efímero en ``session_state`` (no se persiste al JSON).
    """
    from calculos.barrido_parametrico import BarridoConfig, correr_barrido
    from calculos.catalogo_kpis_barrido import KPIS_AVANZADOS
    from calculos.catalogo_parametros_barrido import parametros_para_tipologia

    st.divider()
    st.subheader(t("p7.barridos.titulo"))
    st.caption(t("p7.barridos.caption", max=_MAX_BARRIDOS, modo=modo))

    tipologia = proyecto.configuracion.tipologia
    params = parametros_para_tipologia(tipologia, modo)
    if not params:
        st.info(t("p7.barridos.sin_params"))
        return

    key_estado = f"p7_barridos_{modo}"
    barridos: list = st.session_state.get(key_estado, [])

    with st.expander(t("p7.barridos.configurar"), expanded=not barridos):
        labels = {p.label: p for p in params}
        label_sel = st.selectbox(
            t("p7.barridos.parametro"), list(labels.keys()), key=f"barrido_param_{modo}"
        )
        parametro = labels[label_sel]
        st.caption(parametro.descripcion_corta)

        lo_ui, hi_ui = _bounds_ui_parametro(parametro)
        actual_si = _valor_actual_si_barrido(proyecto, parametro, condiciones)
        actual_ui = parametro.si_a_ui(actual_si) if actual_si is not None else None
        if actual_ui is not None and actual_ui > 0:
            min_def = max(lo_ui, 0.5 * actual_ui)
            max_def = min(hi_ui, 1.5 * actual_ui)
        else:
            min_def, max_def = lo_ui, hi_ui

        c1, c2, c3 = st.columns(3)
        with c1:
            min_ui = st.number_input(
                t("p7.barridos.minimo", unidad=parametro.unidad_ui),
                min_value=float(lo_ui),
                max_value=float(hi_ui),
                value=float(min_def),
                key=f"barrido_min_{modo}",
            )
        with c2:
            max_ui = st.number_input(
                t("p7.barridos.maximo", unidad=parametro.unidad_ui),
                min_value=float(lo_ui),
                max_value=float(hi_ui),
                value=float(max_def),
                key=f"barrido_max_{modo}",
            )
        with c3:
            n_puntos = st.number_input(
                t("p7.barridos.n_puntos"),
                min_value=2,
                max_value=30,
                value=_N_DEFAULT_POR_MODO.get(modo, 5),
                step=1,
                key=f"barrido_n_{modo}",
            )

        # KPIs avanzados opt-in válidos para el modo.
        avanzados_modo = [k for k in KPIS_AVANZADOS if modo in k.modos_validos]
        kpis_extra: list[str] = []
        if avanzados_modo:
            with st.expander(t("p7.barridos.kpis_avanzados"), expanded=False):
                for k in avanzados_modo:
                    if st.checkbox(
                        t("p7.barridos.kpi_check", label=k.label, unidad=k.unidad),
                        key=f"barrido_kpi_{modo}_{k.id}",
                    ):
                        kpis_extra.append(k.id)

        nombre_def = f"{parametro.label} ({len(barridos) + 1})"
        nombre = st.text_input(
            t("p7.barridos.nombre"), value=nombre_def, key=f"barrido_nombre_{modo}"
        )

        # Estimación de tiempo.
        t_base = st.session_state.get(f"p7_t_calc_base_s_{modo}")
        if t_base:
            t_est = t_base * int(n_puntos)
            st.caption(t("p7.barridos.t_estimado", est=t_est, n=int(n_puntos), base=t_base))
            if t_est > 120:
                st.warning(t("p7.barridos.t_largo", est=t_est))

        bloqueado = len(barridos) >= _MAX_BARRIDOS
        if bloqueado:
            st.warning(t("p7.barridos.bloqueado", max=_MAX_BARRIDOS))
        correr = st.button(
            t("p7.barridos.correr"), type="primary", key=f"barrido_run_{modo}", disabled=bloqueado
        )

        if correr:
            valores_ui = np.linspace(float(min_ui), float(max_ui), int(n_puntos))
            valores_si = tuple(float(parametro.ui_a_si(v)) for v in valores_ui)
            cfg = BarridoConfig(
                parametro_id=parametro.id,
                valores_si=valores_si,
                modo=modo,
                nombre=nombre or nombre_def,
                kpis_extra=tuple(kpis_extra),
                condiciones_constantes=condiciones,
                forzantes_base=forzantes_base,
                forzantes_builder=forzantes_builder,
                n_dias=n_dias,
            )
            prog = st.progress(0.0)
            status = st.empty()

            def _cb(i, n, v, _status=status, _prog=prog, _p=parametro):
                _prog.progress(i / n)
                _status.text(
                    t(
                        "p7.barridos.progreso_punto",
                        i=i,
                        n=n,
                        label=_p.label,
                        v=v,
                        unidad=_p.unidad_ui,
                    )
                )

            with st.spinner(t("p7.barridos.spinner")):
                resultado = correr_barrido(proyecto, cfg, callback_progreso=_cb)
            prog.empty()
            status.empty()
            barridos.append(resultado)
            st.session_state[key_estado] = barridos
            st.rerun()

    if not barridos:
        return

    _render_resultados_barridos(barridos, modo, key_estado)


def _render_resultados_barridos(barridos: list, modo: str, key_estado: str) -> None:
    """Tarjetas de gestión + tablas + gráficas superpuestas por KPI."""
    from calculos.catalogo_kpis_barrido import kpis_fijos_para_modo, obtener_kpi

    # Tarjetas de gestión (nombre, parámetro, N, eliminar).
    st.markdown(t("p7.barridos.activos"))
    for idx, b in enumerate(list(barridos)):
        color = _paleta_color_barrido(idx)
        c1, c2 = st.columns([5, 1])
        with c1:
            _tarjeta = t(
                "p7.barridos.tarjeta",
                nombre=b.nombre,
                param=b.parametro_meta.label,
                n=len(b.puntos),
                t=b.t_ejecucion_s,
            )
            st.markdown(
                f"<span style='color:{color}'>●</span> {_tarjeta}",
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("🗑️", key=f"barrido_del_{modo}_{idx}", help=t("p7.barridos.eliminar")):
                barridos.pop(idx)
                st.session_state[key_estado] = barridos
                st.rerun()

    # Tablas por barrido.
    for b in barridos:
        with st.expander(t("p7.barridos.tabla", nombre=b.nombre), expanded=False):
            st.dataframe(_barrido_a_dataframe(b), width="stretch")

    # Gráficas por KPI. Si todos los barridos comparten parámetro, se superponen.
    params_distintos = {b.config.parametro_id for b in barridos}
    comparten_parametro = len(params_distintos) == 1
    if not comparten_parametro:
        st.info(t("p7.barridos.params_distintos"))

    # Conjunto de KPIs a graficar: fijos del modo + extras presentes en algún barrido.
    kpis_ids: list[str] = [k.id for k in kpis_fijos_para_modo(modo)]
    for b in barridos:
        for kid in b.config.kpis_extra:
            if kid not in kpis_ids:
                kpis_ids.append(kid)

    for kid in kpis_ids:
        kpi = obtener_kpi(kid)
        fig = go.Figure()
        hay_datos = False
        for idx, b in enumerate(barridos):
            if kid not in {kk for pt in b.puntos for kk in pt.kpis}:
                continue
            xs = [pt.valor_ui for pt in b.puntos]
            ys = [pt.kpis.get(kid) for pt in b.puntos]
            if all(y is None for y in ys):
                continue
            hay_datos = True
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines+markers",
                    name=b.nombre,
                    line=dict(color=_paleta_color_barrido(idx)),
                    connectgaps=False,
                )
            )
        if not hay_datos:
            continue
        eje_x = (
            f"{barridos[0].parametro_meta.label} [{barridos[0].parametro_meta.unidad_ui}]"
            if comparten_parametro
            else t("p7.barridos.eje_x_valor")
        )
        fig.update_layout(
            title=f"{kpi.label} [{kpi.unidad}]",
            xaxis_title=eje_x,
            yaxis_title=f"{kpi.label} [{kpi.unidad}]",
            height=360,
        )
        mostrar_plotly(fig, nombre=f"barrido_kpi_{kid}")


# ---------------------------------------------------------------------------
# Ventana de producción (gran escala)
# ---------------------------------------------------------------------------


def _slice_clima_ventana(clima, inicio, fin, paso_s: float = 3600.0):
    """Recorta el clima al lapso de la ventana, al **paso de trabajo** (fase 1b).

    Resuelve ``clima.datos`` a la resolución ``paso_s`` (sub-horario real desde
    ``datos_nativos`` o interpolado del horario con ``ADV_PASO_SINTETICO``) antes
    de recortar. Devuelve ``(df, msg, advertencias)``.
    """
    import dataclasses

    from calculos.clima_calc import resolver_datos_trabajo, slice_clima_ventana

    df_trab, advertencias = resolver_datos_trabajo(clima, paso_s)
    if df_trab is not None and df_trab is not getattr(clima, "datos", None):
        clima = dataclasses.replace(clima, datos=df_trab)
    df, msg = slice_clima_ventana(clima, inicio, fin)
    return df, msg, advertencias


def _fig_perfil_tunel(res) -> go.Figure:
    """Perfil espacial del túnel: X del producto y T del aire por zona."""
    n = len(res.perfil_X_zonas)
    zonas = list(range(1, n + 1))
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=zonas,
            y=[float(x) for x in res.perfil_X_zonas],
            name=t("p7.tunel_fig.x_prod"),
            mode="lines+markers",
            line=dict(color="#1f77b4"),
        ),
        secondary_y=False,
    )
    if res.perfil_T_aire_zonas_K is not None:
        fig.add_trace(
            go.Scatter(
                x=zonas,
                y=[float(tk) - 273.15 for tk in res.perfil_T_aire_zonas_K],
                name=t("p7.tunel_fig.t_aire"),
                mode="lines+markers",
                line=dict(color="#d62728", dash="dot"),
            ),
            secondary_y=True,
        )
    fig.update_xaxes(title_text=t("p7.tunel_fig.eje_zona"))
    fig.update_yaxes(title_text=t("p7.tunel_fig.eje_x"), secondary_y=False)
    fig.update_yaxes(title_text=t("p7.tunel_fig.eje_t"), secondary_y=True)
    fig.update_layout(
        title=t("p7.tunel_fig.titulo"),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def _render_resultados_ventana(res, proyecto) -> None:
    """Dashboard de producción del secador de gran escala sobre la ventana."""
    if res.status == "error":
        _mostrar_errores(res.advertencias)
        return

    dias = res.horizonte_s / 86400.0
    st.subheader(t("p7.ventana.produccion", subtipo=res.subtipo.capitalize()))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("p7.ventana.producto_seco"), f"{res.masa_seca_producida_kg:,.0f} kg")
    c2.metric(
        t("p7.ventana.tasa_regimen"),
        f"{res.tasa_regimen_kg_dia:,.1f} kg/día" if res.tasa_regimen_kg_dia else "—",
    )
    c3.metric(t("p7.ventana.agua_evaporada"), f"{res.masa_evaporada_kg:,.0f} kg")
    c4.metric(t("p7.ventana.lena"), f"{res.lena_consumida_kg:,.0f} kg")
    st.caption(t("p7.ventana.simulada", dias=dias, horas=res.horizonte_s / 3600))

    if res.subtipo == "BATCH":
        b1, b2, b3 = st.columns(3)
        b1.metric(t("p7.ventana.lotes"), f"{res.n_batches_completos}")
        b2.metric(
            t("p7.ventana.tiempo_lote"),
            f"{res.t_secado_medio_s / 3600:.1f} h" if res.t_secado_medio_s else "—",
        )
        b3.metric(
            t("p7.ventana.lote_progreso"),
            t("p7.ventana.si") if res.batch_en_progreso else t("p7.ventana.no"),
        )
    else:  # SEMICONTINUO
        s1, s2, s3 = st.columns(3)
        s1.metric(t("p7.ventana.columnas_desc"), f"{res.n_avances}")
        s2.metric(
            t("p7.ventana.x_salida"),
            f"{res.X_salida_regimen:.3f}" if res.X_salida_regimen is not None else "—",
        )
        s3.metric(
            t("p7.ventana.throughput"),
            f"{res.throughput_fresco_kg_dia:,.0f} kg/día" if res.throughput_fresco_kg_dia else "—",
        )
        if res.perfil_X_zonas is not None and len(res.perfil_X_zonas) > 0:
            mostrar_plotly(_fig_perfil_tunel(res), nombre="perfil_tunel")
        # Validación del túnel contra muestreo de campo (mejora 38, fase 4).
        _render_validacion_tunel(proyecto, res)

    _render_carta_psicrometrica(res, proyecto)

    if res.advertencias:
        _mostrar_advertencias(res.advertencias)


def _render_ventana(proyecto) -> None:
    """Rama de P7 para tipología gran escala en modo VENTANA de producción."""
    cfg = proyecto.configuracion
    st.subheader(t("p7.ventana.titulo"))

    inicio = getattr(cfg, "ventana_inicio", None)
    fin = getattr(cfg, "ventana_fin", None)
    subtipo = getattr(cfg, "subtipo_gran_escala", None)
    if inicio is None or fin is None:
        st.warning(t("p7.ventana.sin_fechas"))
        return

    c1, c2, c3 = st.columns(3)
    c1.metric(t("p7.ventana.lapso"), f"{(fin - inicio).days} días")
    c2.metric(t("p7.ventana.desde_hasta"), f"{inicio} → {fin}")
    c3.metric(t("p7.ventana.subtipo"), subtipo.value.capitalize() if subtipo else "—")

    clima = getattr(proyecto, "clima", None)
    paso_s = getattr(cfg, "paso_trabajo_s", 3600.0)
    df_ventana, msg, adv_paso = _slice_clima_ventana(clima, inicio, fin, paso_s)
    if df_ventana is None:
        st.info(t("p7.ventana.sin_clima", msg=msg))
        return

    for a in adv_paso:
        st.warning(a)
    st.caption(t("p7.ventana.clima_lapso", n=len(df_ventana), anio=clima.anio))
    if clima.anio is not None and inicio.year != clima.anio:
        st.warning(t("p7.ventana.anio_distinto", anio_ventana=inicio.year, anio_clima=clima.anio))

    st.divider()
    if st.button(t("p7.ventana.boton"), type="primary", key="p7_btn_ventana"):
        import time as _time

        _t0 = _time.perf_counter()
        with st.spinner(t("p7.ventana.spinner")):
            res = calcular_todo_ventana(proyecto, df_ventana)
        st.session_state["p7_resultado_ventana"] = res
        st.session_state["p7_t_calc_ventana_s"] = _time.perf_counter() - _t0
        # Resultado nuevo → la validación del túnel persistida queda obsoleta.
        st.session_state.pop("p7_valtun_resultado", None)

    res = st.session_state.get("p7_resultado_ventana")
    if res is None:
        st.info(t("p7.ventana.prompt"))
        return

    t_calc = st.session_state.get("p7_t_calc_ventana_s")
    if t_calc is not None:
        st.caption(t("p7.ventana.t_calc", t=t_calc))
    _render_resultados_ventana(res, proyecto)

    # Exportación (txt / JSON / PDF) también en modo ventana. Las condiciones
    # representativas de Constantes no existen acá → quedan en None.
    if getattr(res, "status", "") != "error":
        _render_botones_guardado(proyecto, res)


def _omega_amb_constantes(res, proyecto) -> Optional[float]:
    """ω de entrada [kg/kg] en modo Constantes, desde HR_cam (P7) + T_ent + P.

    En Constantes no hay forzantes con ω; la HR del aire de entrada la fija el
    slider de P7 a la temperatura de entrada a la cámara.
    """
    from calculos.balance_global import presion_representativa_proyecto
    from calculos.psicrometria import humedad_absoluta

    T_in = getattr(res, "T_entrada_camara_K", None)
    if T_in is None:
        return None
    try:
        P_Pa, _ = presion_representativa_proyecto(proyecto)
    except Exception:
        P_Pa = 101325.0
    HR = st.session_state.get("p7_HR_cam", _HR_CAMARA_DEFAULT_PCT) / 100.0
    try:
        return humedad_absoluta(HR, float(T_in), P_Pa)
    except ValueError:
        return None


def _render_carta_psicrometrica(res, proyecto, *, omega_amb: Optional[float] = None) -> None:
    """Carta psicrométrica del proceso (mejora 27). Silenciosa si no aplica."""
    from ui.componentes.carta_psicrometrica import fig_carta_psicrometrica

    fig = fig_carta_psicrometrica(res, proyecto, omega_amb=omega_amb)
    if fig is None:
        return
    st.divider()
    st.subheader(t("p7.carta.titulo"))
    st.caption(t("p7.carta.caption"))
    mostrar_plotly(fig, nombre="carta_psicrometrica")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 7 — Resultados del Prediseño."""
    st.header(t("p7.header"))
    boton_manual(SLUG_POR_SECCION["p7"])

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Estado de configuración
    # -----------------------------------------------------------------------
    _seccion_config(proyecto)
    st.divider()

    # Mínimo necesario para calcular
    if proyecto.camara is None:
        st.warning(t("p7.sin_camara"))
        return

    # -----------------------------------------------------------------------
    # Rama gran escala: ventana de producción (autocontenida)
    # -----------------------------------------------------------------------
    # Solo GRAN_ESCALA usa el pipeline de producción (banco + caño maestro +
    # túnel). Para CAJA/ARMARIO en modo VENTANA, el horizonte es un multidía
    # real (mejora 35): cae al flujo transitorio normal de abajo, que levanta
    # el horizonte persistido por P4 (p4_horizonte_resultado).
    modo_analisis = getattr(proyecto.configuracion, "modo_analisis", None)
    tipologia = getattr(proyecto.configuracion, "tipologia", None)
    if modo_analisis == ModoAnalisis.VENTANA and tipologia == Tipologia.GRAN_ESCALA:
        _render_ventana(proyecto)
        return

    # -----------------------------------------------------------------------
    # Panel anual prominente (modo ANUAL): vista principal arriba
    # -----------------------------------------------------------------------
    if modo_analisis == ModoAnalisis.ANUAL:
        res_anual = st.session_state.get("p4_resultado_anual")
        if res_anual is not None:
            _render_operacion_anual_detalle(proyecto)
            _render_barridos_parametricos(proyecto, "anual")
            st.divider()
            _md_titulo = "### " + t("p7.anual_prompt_detalle")
            st.markdown(_md_titulo)
            st.caption(t("p7.anual_prompt_detalle_cap"))
        else:
            st.info(t("p7.anual_sin_calcular"))

    # -----------------------------------------------------------------------
    # Selector modo de cálculo: transitorio (horizonte de P4) vs constantes
    # -----------------------------------------------------------------------
    fz_horizonte = st.session_state.get("p4_forzantes_horizonte")
    horizonte_meta = st.session_state.get("p4_horizonte_meta") or {}
    horizonte_disponible = (
        fz_horizonte is not None and proyecto.camara.modo_calculo == "termodinamico"
    )

    if horizonte_disponible:
        st.subheader(t("p7.modo.titulo"))
        # Options con claves estables: la selección no depende del idioma.
        _modo_keys = ["transitorio", "constantes"]
        modo_p7 = st.radio(
            t("p7.modo.label"),
            options=_modo_keys,
            index=0,
            horizontal=True,
            format_func=lambda k: t(f"p7.modo.{k}"),
            help=t("p7.modo.help"),
        )
    else:
        modo_p7 = "constantes"
        if proyecto.camara.modo_calculo == "termodinamico":
            st.info(t("p7.modo.sin_horizonte"))

    # ===========================================================================
    # RAMA: Transitorio (mejora 19)
    # ===========================================================================
    if modo_p7 == "transitorio":
        n_dias_hor = int(horizonte_meta.get("n_dias", 1))
        modo_fz_label = str(horizonte_meta.get("modo_forzantes", "sintético"))
        horizonte_tipo = horizonte_meta.get("horizonte_tipo")
        horizonte_h = float(fz_horizonte.t_s[-1]) / 3600.0

        st.subheader(t("p7.horizonte.titulo"))
        c1, c2, c3 = st.columns(3)
        _hz_txt = t("p7.horizonte.dias", n=n_dias_hor)
        if horizonte_tipo and n_dias_hor > 1:
            _hz_txt += f" · {horizonte_tipo}"
        c1.metric(t("p7.horizonte.horizonte"), _hz_txt)
        c2.metric(t("p7.horizonte.duracion"), f"{horizonte_h:.1f} h")
        c3.metric(t("p7.horizonte.forzantes"), modo_fz_label)
        st.caption(t("p7.horizonte.caption"))

        st.divider()
        calcular_tr = st.button(
            t("p7.horizonte.boton"),
            type="primary",
            key="p7_btn_calc_tr",
        )
        if calcular_tr:
            import time as _time

            _t0 = _time.perf_counter()
            with st.spinner(t("p7.horizonte.spinner")):
                res_tr: ResultadosCompletosTransitorio = calcular_todo_transitorio(
                    proyecto,
                    forzantes_base=fz_horizonte,
                    n_dias=n_dias_hor,
                )
            st.session_state["p7_resultados_tr"] = res_tr
            st.session_state["p7_t_calc_base_s_transitorio"] = _time.perf_counter() - _t0

        if "p7_resultados_tr" not in st.session_state:
            st.info(t("p7.horizonte.prompt"))
            return

        res_tr = st.session_state["p7_resultados_tr"]
        _render_resultados_transitorios(res_tr, proyecto)
        _render_carta_psicrometrica(res_tr, proyecto)

        # Botones de guardado para modo transitorio
        # (mismo bloque que en constantes, con condiciones representativas
        # sugeridas a partir de los datos climáticos)
        T_sug, I_sug, v_sug = _sugerir_condiciones(proyecto)
        _render_botones_guardado(
            proyecto,
            res_tr,
            T_amb_C=T_sug,
            I_g=I_sug,
            v_viento=v_sug,
            HR_cam_pct=_HR_CAMARA_DEFAULT_PCT,
        )

        _render_barridos_parametricos(
            proyecto,
            "transitorio",
            forzantes_base=fz_horizonte,
            forzantes_builder=_construir_forzantes_builder_desde_meta(
                horizonte_meta, st.session_state.get("p3_eval")
            ),
            n_dias=n_dias_hor,
        )
        return  # no caer en el flujo de constantes representativas

    # -----------------------------------------------------------------------
    # Condiciones de operación representativas
    # -----------------------------------------------------------------------
    st.subheader(t("p7.condiciones.titulo"))
    st.caption(t("p7.condiciones.caption"))

    T_sug, I_sug, v_sug = _sugerir_condiciones(proyecto)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        T_amb_C = st.number_input(
            t("p7.condiciones.t_amb"),
            min_value=-10.0,
            max_value=50.0,
            value=st.session_state.get("p7_T_amb_C", T_sug),
            step=0.5,
            format="%.1f",
        )
        st.session_state["p7_T_amb_C"] = T_amb_C
    with c2:
        I_g = st.number_input(
            t("p7.condiciones.irradiancia.label"),
            min_value=0.0,
            max_value=1200.0,
            value=st.session_state.get("p7_I_g", I_sug),
            step=10.0,
            format="%.0f",
            help=t("p7.condiciones.irradiancia.help"),
        )
        st.session_state["p7_I_g"] = I_g
    with c3:
        v_viento = st.number_input(
            t("p7.condiciones.viento"),
            min_value=0.0,
            max_value=20.0,
            value=st.session_state.get("p7_v_viento", v_sug),
            step=0.5,
            format="%.1f",
        )
        st.session_state["p7_v_viento"] = v_viento
    with c4:
        HR_cam_pct = st.slider(
            t("p7.condiciones.hr.label"),
            min_value=5.0,
            max_value=80.0,
            value=st.session_state.get("p7_HR_cam", _HR_CAMARA_DEFAULT_PCT),
            step=5.0,
            help=t("p7.condiciones.hr.help"),
        )
        st.session_state["p7_HR_cam"] = HR_cam_pct

    T_amb_K = celsius_a_kelvin(T_amb_C)
    HR_cam = HR_cam_pct / 100.0

    # -----------------------------------------------------------------------
    # Botón de cálculo
    # -----------------------------------------------------------------------
    st.divider()
    calcular = st.button(t("p7.condiciones.boton"), type="primary")

    if calcular:
        import time as _time

        _t0 = _time.perf_counter()
        with st.spinner(t("p7.condiciones.spinner")):
            res: ResultadosCompletos = calcular_todo(
                proyecto=proyecto,
                T_amb_K=T_amb_K,
                I_g_W_m2=I_g,
                v_viento_ms=v_viento,
                T_entrada_K=T_amb_K,
                HR_camara=HR_cam,
            )
        st.session_state["p7_resultados"] = res
        st.session_state["p7_t_calc_base_s_constantes"] = _time.perf_counter() - _t0

    # Usar resultados almacenados si existen
    if "p7_resultados" not in st.session_state:
        st.info(t("p7.condiciones.prompt"))
        return

    res: ResultadosCompletos = st.session_state["p7_resultados"]

    # Errores fatales
    if res.errores:
        st.error(t("p7.errores_fatales"))
        _mostrar_errores(res.errores)
        return

    # Advertencias
    if res.advertencias:
        with st.expander(t("p7.advertencias_expander", n=len(res.advertencias))):
            _mostrar_advertencias(res.advertencias)

    st.divider()

    # -----------------------------------------------------------------------
    # Dashboard de resultados
    # -----------------------------------------------------------------------

    # --- Colector ---
    if res.colector is not None:
        st.subheader(t("p7.colector.titulo"))
        col = res.colector
        _t_sal = getattr(col, "T_salida_K", getattr(col, "T_salida_mezcla_K", None))
        _regimen = getattr(
            col, "regimen_flujo", getattr(col, "regimen_ci", getattr(col, "regimen_cs", "—"))
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("p7.colector.t_entrada"), f"{kelvin_a_celsius(col.T_entrada_K):.1f} °C")
        if _t_sal is not None:
            c2.metric(
                t("p7.colector.t_salida"),
                f"{kelvin_a_celsius(_t_sal):.1f} °C",
                delta=f"+{_t_sal - col.T_entrada_K:.1f} °C",
            )
        c3.metric(t("p7.colector.q_util"), f"{col.Q_util_W:.0f} W")
        c4.metric(t("p7.colector.eta"), f"{col.eta_termica:.1%}")
        c5.metric(t("p7.colector.regimen"), _regimen or "—")
        _re = getattr(col, "Re_medio", getattr(col, "Re_ci", getattr(col, "Re_cs", None)))
        _hint = getattr(
            col, "h_int_medio", getattr(col, "h_int_ci", getattr(col, "h_int_cs", None))
        )
        if _re:
            st.caption(t("p7.colector.re_hint", re=_re, hint=_hint))

    # --- Auxiliar ---
    if res.auxiliar is not None:
        st.subheader(t("p7.auxiliar.titulo"))
        aux = res.auxiliar
        c1, c2, c3 = st.columns(3)
        c1.metric(t("p7.auxiliar.t_entrada"), f"{kelvin_a_celsius(aux.T_entrada_K):.1f} °C")
        c2.metric(
            t("p7.auxiliar.t_salida"),
            f"{kelvin_a_celsius(aux.T_salida_K):.1f} °C",
            delta=f"+{aux.delta_T_K:.1f} °C",
        )
        c3.metric(t("p7.auxiliar.q_efectivo"), f"{aux.Q_efectivo_W / 1000:.2f} kW")

    # --- Temperatura de entrada a la cámara ---
    if res.T_entrada_camara_K is not None:
        st.info(t("p7.t_entrada_camara", t=kelvin_a_celsius(res.T_entrada_camara_K)))

    # --- Cámara ---
    if res.camara is not None:
        st.subheader(t("p7.camara.titulo"))
        cam = res.camara
        if isinstance(cam, ResultadoMotorTermodinamico):
            c1, c2, c3, c4 = st.columns(4)
            if cam.t_secado_s is not None:
                c1.metric(t("p7.camara.t_secado"), f"{cam.t_secado_s / 3600.0:.1f} h")
            else:
                c1.metric(
                    t("p7.camara.t_secado"),
                    "—",
                    help=t("p7.camara.no_convergio_help", status=cam.status),
                )
            c2.metric(t("p7.camara.status"), cam.status)
            c3.metric(t("p7.camara.agua_evaporada"), f"{cam.masa_evaporada_total_kg:.2f} kg")
            X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
            c4.metric(t("p7.camara.x_final"), f"{X_final:.4f} kg/kg ms")

            if cam.status == "t_max_alcanzado":
                st.warning(t("p7.camara.t_max_warning"))
            elif cam.status == "error":
                st.error(t("p7.camara.error", status=cam.status))

            X_obj = proyecto.camara.carga_producto.humedad_objetivo_X
            prod_id = proyecto.camara.carga_producto.producto_id
            fig_td = grafica_termodinamica_camara(cam, X_obj, prod_id)
            mostrar_plotly(fig_td, nombre="camara_trayectorias")
            st.caption(t("p7.camara.caption_taire"))

    # --- Motor ---
    if proyecto.motor is not None and proyecto.motor.potencia_a_instalar_W:
        st.subheader(t("p7.motor.titulo"))
        mot = proyecto.motor
        c1, c2, c3 = st.columns(3)
        c1.metric(t("p7.motor.dp"), f"{mot.perdida_carga_total_Pa:.1f} Pa")
        c2.metric(t("p7.motor.p_electrica"), f"{mot.potencia_electrica_W:.0f} W")
        c3.metric(t("p7.motor.p_instalar"), f"{mot.potencia_a_instalar_W:.0f} W")

    # --- Chimenea solar (convección natural) ---
    if getattr(res, "chimenea", None) is not None:
        _render_chimenea_resultados(res.chimenea, proyecto)

    # --- Balance global ---
    if res.energia_total_MJ is not None and res.energia_total_MJ > 0:
        st.subheader(t("p7.balance.titulo"))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            t("p7.balance.cop.label"),
            f"{res.COP_secado:.3f}" if res.COP_secado else "—",
            help=t("p7.balance.cop.help"),
        )
        c2.metric(
            t("p7.balance.fraccion_solar.label"),
            f"{res.fraccion_solar:.1%}" if res.fraccion_solar is not None else "100%",
            help=t("p7.balance.fraccion_solar.help"),
        )
        c3.metric(
            t("p7.balance.e_secado.label"),
            f"{res.energia_secado_MJ:.3f} MJ",
            help=t("p7.balance.e_secado.help"),
        )
        c4.metric(
            t("p7.balance.e_total.label"),
            f"{res.energia_total_MJ:.3f} MJ",
            help=t("p7.balance.e_total.help"),
        )

        fig_bal = _fig_sankey_simplificado(res)
        if fig_bal:
            mostrar_plotly(fig_bal, nombre="balance_energetico")

    # --- Carta psicrométrica del proceso (mejora 27) ---
    _render_carta_psicrometrica(res, proyecto, omega_amb=_omega_amb_constantes(res, proyecto))

    # --- Resumen del ciclo ---
    st.subheader(t("p7.ciclo.titulo"))
    if proyecto.camara is not None and res.camara is not None:
        p = proyecto.camara.carga_producto
        ms = res.masa_producto_seco_kg
        t_h, masa_agua, _status, _ok = _resumen_camara(res.camara)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("p7.ciclo.masa_fresco"), f"{p.masa_total_kg:.1f} kg")
        c2.metric(
            t("p7.ciclo.masa_seco.label"),
            f"{ms:.2f} kg" if ms else "—",
            help=t("p7.ciclo.masa_seco.help"),
        )
        c3.metric(t("p7.ciclo.agua_evaporada"), f"{masa_agua:.2f} kg")
        c4.metric(
            t("p7.ciclo.rendimiento.label"),
            f"{res.rendimiento_masa:.1%}" if res.rendimiento_masa else "—",
            help=t("p7.ciclo.rendimiento.help"),
        )
        c5.metric(
            t("p7.ciclo.t_secado"),
            f"{t_h:.1f} h" if t_h is not None else t("p7.ciclo.no_convergio"),
        )

    # --- Tabla de resumen exportable ---
    with st.expander(t("p7.tabla.titulo")):
        filas = []
        if res.colector:
            col = res.colector
            _t_sal = getattr(col, "T_salida_K", getattr(col, "T_salida_mezcla_K", None))
            filas += [
                (t("p7.tabla.col_t_ent"), f"{kelvin_a_celsius(col.T_entrada_K):.1f}"),
                (t("p7.tabla.col_t_sal"), f"{kelvin_a_celsius(_t_sal):.1f}" if _t_sal else "—"),
                (t("p7.tabla.col_q"), f"{col.Q_util_W:.0f}"),
                (t("p7.tabla.col_eta"), f"{col.eta_termica:.1%}"),
            ]
        if res.auxiliar:
            aux = res.auxiliar
            filas += [
                (t("p7.tabla.aux_dt"), f"{aux.delta_T_K:.1f}"),
                (t("p7.tabla.aux_q"), f"{aux.Q_efectivo_W:.0f}"),
            ]
        if res.camara is not None:
            cam = res.camara
            t_h_cam, masa_cam, status_cam, _ok = _resumen_camara(cam)
            T_op_str = (
                f"{kelvin_a_celsius(res.T_entrada_camara_K):.1f}" if res.T_entrada_camara_K else "—"
            )
            filas += [
                (t("p7.tabla.cam_top"), T_op_str),
                (
                    t("p7.tabla.cam_t"),
                    f"{t_h_cam:.2f}" if t_h_cam is not None else t("p7.tabla.no_convergio"),
                ),
                (t("p7.tabla.cam_agua"), f"{masa_cam:.3f}"),
                (t("p7.tabla.cam_status"), status_cam),
            ]
            if isinstance(cam, ResultadoMotorTermodinamico):
                X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
                T_prod_final_C = float(cam.T_prod_K[-1]) - 273.15 if len(cam.T_prod_K) else 0.0
                filas += [
                    (t("p7.tabla.cam_xfin"), f"{X_final:.4f}"),
                    (t("p7.tabla.cam_tprod"), f"{T_prod_final_C:.1f}"),
                ]
        if proyecto.motor and proyecto.motor.potencia_a_instalar_W:
            mot = proyecto.motor
            filas += [
                (t("p7.tabla.mot_dp"), f"{mot.perdida_carga_total_Pa:.1f}"),
                (t("p7.tabla.mot_pe"), f"{mot.potencia_electrica_W:.1f}"),
                (t("p7.tabla.mot_pi"), f"{mot.potencia_a_instalar_W:.1f}"),
            ]
        if getattr(res, "chimenea", None) is not None:
            ch = res.chimenea
            m_punto = float(ch.get("m_punto_kgs", 0.0))
            filas += [
                (t("p7.tabla.chim_caudal"), f"{m_punto * 1000:.2f}"),
                (t("p7.tabla.chim_qvol"), f"{m_punto / 1.1 * 3600.0:.1f}"),
                (t("p7.tabla.chim_v"), f"{ch.get('v_chim_ms', 0.0):.3f}"),
                (t("p7.tabla.chim_re"), f"{ch.get('Re_chimenea', 0.0):.0f}"),
                (t("p7.tabla.chim_tiro"), f"{ch.get('delta_P_tiro_Pa', 0.0):.3f}"),
                (t("p7.tabla.chim_ducto"), f"{ch.get('delta_P_chimenea_Pa', 0.0):.3f}"),
                (t("p7.tabla.chim_resto"), f"{ch.get('delta_P_resto_Pa', 0.0):.3f}"),
                (t("p7.tabla.chim_heff"), f"{ch.get('H_eff_m', 0.0):.2f}"),
            ]
        if res.energia_total_MJ:
            filas += [
                (t("p7.tabla.bal_solar"), f"{res.energia_solar_util_MJ:.4f}"),
                (t("p7.tabla.bal_aux"), f"{res.energia_auxiliar_MJ:.4f}"),
                (t("p7.tabla.bal_motor"), f"{res.energia_motor_MJ:.4f}"),
                (t("p7.tabla.bal_secado"), f"{res.energia_secado_MJ:.4f}"),
                (t("p7.tabla.bal_cop"), f"{res.COP_secado:.4f}" if res.COP_secado else "—"),
                (
                    t("p7.tabla.bal_fs"),
                    f"{res.fraccion_solar:.1%}" if res.fraccion_solar is not None else "100%",
                ),
            ]

        if filas:
            import pandas as pd

            _col_p = t("p7.tabla.col_param")
            df = pd.DataFrame(filas, columns=[_col_p, t("p7.tabla.col_valor")])
            st.dataframe(df.set_index(_col_p), width="stretch")

    # --- Guardar resultados completos ---
    _render_botones_guardado(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
    )

    # --- Corridas paramétricas (modo Constantes) ---
    _render_barridos_parametricos(
        proyecto,
        "constantes",
        condiciones=dict(
            T_amb_K=T_amb_K,
            I_g_W_m2=I_g,
            v_viento_ms=v_viento,
            T_entrada_K=T_amb_K,
            HR_camara=HR_cam,
        ),
    )


def _df_operacion_anual(res_anual):
    """Tabla mensual del anual, lista para mostrar y para exportar a CSV.

    Función aparte (y pura salvo por ``t()``) para que la vista y la descarga
    compartan exactamente los mismos números: si divergieran, el CSV dejaría de
    ser el respaldo de lo que el usuario vio en pantalla.
    """
    import pandas as pd

    meses_nombres = t("graficas.meses_abbr").split(",")
    _col_mes = t("p7.anual_det.col_mes")
    filas = []
    for p in res_anual.puntos_mensuales:
        filas.append(
            {
                _col_mes: meses_nombres[p.mes - 1],
                t("p7.anual_det.col_seca"): round(p.masa_seca_kg, 1),
                t("p7.anual_det.col_evap"): round(p.masa_evaporada_kg, 1),
                t("p7.anual_det.col_lotes"): p.lotes_completos,
                t("p7.anual_det.col_frustrados"): p.lotes_frustrados,
                t("p7.anual_det.col_dur"): (
                    round(p.duracion_media_h, 1) if p.duracion_media_h is not None else None
                ),
                t("p7.anual_det.col_operables"): f"{p.dias_operables}/{p.dias}",
                t("p7.anual_det.col_esolar"): round(p.E_solar_MJ, 0),
                t("p7.anual_det.col_drying"): (
                    round(p.eta_drying * 100, 2) if p.eta_drying is not None else None
                ),
                t("p7.anual_det.col_especifica"): (
                    round(p.energia_especifica_MJ_kg, 1)
                    if p.energia_especifica_MJ_kg is not None
                    else None
                ),
            }
        )
    return pd.DataFrame(filas).set_index(_col_mes)


def _render_operacion_anual_detalle(proyecto) -> None:
    """Panel detalle del modo anual sobre 8760 h — visible si P4 lo calculó.

    Resumen del año, tabla de 12 meses (con descarga CSV) y gráfica de producto
    seco por mes.
    """
    from calculos.simulacion_anual import ResultadosAnual

    res_anual: ResultadosAnual | None = st.session_state.get("p4_resultado_anual")
    if res_anual is None:
        return

    st.divider()
    st.subheader(t("p7.anual_det.titulo"))
    st.caption(t("p7.anual_det.caption"))

    if res_anual.advertencias:
        for msg in res_anual.advertencias:
            st.warning(f"⚠️ {msg}")  # i18n: exento (mensaje de calculos/, F5)

    # Producción y agua evaporada son cantidades distintas y se muestran como
    # tales: confundirlas era el defecto del anual anterior.
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("p7.anual_det.kg_seco"), f"{res_anual.masa_seca_anual_kg:.0f} kg")
    col2.metric(t("p7.anual_det.kg_agua"), f"{res_anual.masa_evaporada_anual_kg:.0f} kg")
    col3.metric(
        t("p7.anual_det.lotes"),
        f"{res_anual.n_lotes_completos}",
        delta=(
            t("p7.anual_det.lotes_frustrados", n=res_anual.n_lotes_frustrados)
            if res_anual.n_lotes_frustrados
            else None
        ),
        delta_color="inverse",
    )
    col4.metric(
        t("p7.anual_det.especifica"),
        (
            f"{res_anual.energia_especifica_MJ_kg:.1f}"
            if res_anual.energia_especifica_MJ_kg is not None
            else "—"  # i18n: exento (marcador de dato ausente)
        ),
    )

    col5, col6, col7, col8 = st.columns(4)
    col5.metric(t("p7.anual_det.e_solar"), f"{res_anual.E_solar_anual_MJ:.0f} MJ")
    col6.metric(
        t("p7.anual_det.frac_solar"),
        (
            f"{res_anual.fraccion_solar * 100:.0f}%"
            if res_anual.fraccion_solar is not None
            else "—"  # i18n: exento (marcador de dato ausente)
        ),
        help=t("p7.anual_det.frac_solar_help"),
    )
    col7.metric(
        t("p7.anual_det.eta_drying"),
        (
            f"{res_anual.eta_drying_anual * 100:.2f}%"
            if res_anual.eta_drying_anual is not None
            else "—"  # i18n: exento (marcador de dato ausente)
        ),
        help=t("p7.anual_det.eta_drying_help"),
    )
    col8.metric(
        t("p7.anual_det.dias_operables"),
        f"{res_anual.dias_operables}",
        help=t("p7.anual_det.dias_operables_help", umbral=res_anual.umbral_dia_operable_MJ_m2),
    )

    if res_anual.duracion_p50_h is not None:
        st.caption(
            t(
                "p7.anual_det.dispersion",
                p50=res_anual.duracion_p50_h,
                p90=res_anual.duracion_p90_h,
            )
        )
    st.caption(t("p7.anual_det.cota_superior"))

    df_meses = _df_operacion_anual(res_anual)
    st.dataframe(df_meses, width="stretch")
    st.download_button(
        t("p7.anual_det.csv"),
        data=df_meses.to_csv(encoding="utf-8"),
        file_name="secasol_anual_mensual.csv",  # i18n: exento (nombre de archivo)
        mime="text/csv",
        key="p7_anual_csv",
        help=t("p7.anual_det.csv_help"),
    )

    mostrar_plotly(_fig_operacion_anual(res_anual), nombre="operacion_anual")


def _fig_operacion_anual(res_anual):
    """Barras de producto seco por mes + línea de lotes. Reusada por el PDF."""
    meses_nombres = t("graficas.meses_abbr").split(",")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(
        x=meses_nombres,
        y=[p.masa_seca_kg for p in res_anual.puntos_mensuales],
        name=t("p7.anual_det.fig_kg"),
        marker_color="#1f77b4",
    )
    fig.add_scatter(
        x=meses_nombres,
        y=[p.lotes_completos for p in res_anual.puntos_mensuales],
        name=t("p7.anual_det.fig_lotes"),
        mode="lines+markers",
        line=dict(color="#d62728", width=2),
        marker=dict(size=8),
        yaxis="y2",
    )
    fig.update_layout(
        title=t("p7.anual_det.fig_titulo"),
        xaxis_title=t("p7.anual_det.fig_eje_mes"),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title_text=t("p7.anual_det.fig_eje_kg"), secondary_y=False)
    fig.update_yaxes(title_text=t("p7.anual_det.fig_eje_lotes"), secondary_y=True)
    return fig


def _render_botones_guardado(
    proyecto,
    res,
    *,
    T_amb_C: Optional[float] = None,
    I_g: Optional[float] = None,
    v_viento: Optional[float] = None,
    HR_cam_pct: Optional[float] = None,
) -> None:
    """Renderiza el bloque de botones .txt / .json / PDF al pie de P7.

    Compartido entre las ramas de modo transitorio, constantes representativas
    y ventana de producción. ``res`` puede ser ``ResultadosCompletos``,
    ``ResultadosCompletosTransitorio`` o ``ResultadoVentana`` — todos funcionan
    vía ``getattr``. Las condiciones representativas (sliders de Constantes)
    son opcionales: en modo Ventana no existen y quedan en ``None``.
    """
    from ui.componentes.serializacion import (
        dump_json,
        nombre_archivo_descarga,
        nombre_archivo_reporte,
    )

    st.divider()
    # Operación anual de cámara (si P4 la corrió): entra a los tres exports.
    res_anual = st.session_state.get("p4_resultado_anual")
    texto_res = _texto_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
        res_anual=res_anual,
    )
    json_res = _json_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
        res_anual=res_anual,
    )
    col_txt, col_json = st.columns(2)
    with col_txt:
        st.download_button(
            t("p7.guardar.txt"),
            data=texto_res,
            file_name=nombre_archivo_descarga(proyecto, "prediseno_completo", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            t("p7.guardar.json"),
            data=dump_json(json_res),
            file_name=nombre_archivo_descarga(proyecto, "prediseno_completo", "json"),
            mime="application/json",
            width="stretch",
        )

    # --- Generar reporte PDF ---
    st.markdown(t("p7.guardar.pdf_titulo"))
    st.caption(t("p7.guardar.pdf_caption"))
    if st.button(t("p7.guardar.pdf_boton"), type="primary", width="stretch", key="p7_generar_pdf"):
        from ui.reporte import generar_reporte_pdf

        with st.spinner(t("p7.guardar.pdf_spinner")):
            try:
                pdf_bytes = generar_reporte_pdf(
                    proyecto,
                    st.session_state,
                    res,
                    T_amb_C=T_amb_C,
                    I_g=I_g,
                    v_viento=v_viento,
                    HR_cam_pct=HR_cam_pct,
                    idioma=idioma_actual(),
                )
                st.session_state["p7_reporte_pdf"] = pdf_bytes
                st.success(t("p7.guardar.pdf_exito", kb=len(pdf_bytes) / 1024))
            except Exception as exc:
                st.error(t("p7.guardar.pdf_error", exc=exc))
                st.session_state.pop("p7_reporte_pdf", None)

    pdf_cached = st.session_state.get("p7_reporte_pdf")
    if pdf_cached is not None:
        st.download_button(
            t("p7.guardar.pdf_descargar"),
            data=pdf_cached,
            file_name=nombre_archivo_reporte(proyecto, "pdf"),
            mime="application/pdf",
            width="stretch",
        )


# ---------------------------------------------------------------------------
# Validación del túnel con datos medidos (mejora 38, fase 4, E5)
# ---------------------------------------------------------------------------


def _perfil_medido_desde_editor(filas, n_zonas: int):
    """Extrae ``(indices_zona, valores)`` de la tabla editable del perfil (puro).

    Se descartan las filas sin valor (zonas sin sensor) y las fuera de rango.

    Args:
        filas: Iterable de dicts con claves de zona (1-based) y valor medido.
        n_zonas: Cantidad de zonas del túnel.

    Returns:
        ``(zonas_0based, valores)`` como listas paralelas, ya ordenadas por zona.
    """
    import math

    pares = []
    for i, fila in enumerate(filas):
        valor = fila.get("medido") if isinstance(fila, dict) else None
        if valor is None:
            continue
        try:
            v = float(valor)
        except (TypeError, ValueError):
            continue
        if math.isnan(v) or not (0 <= i < n_zonas):
            continue
        pares.append((i, v))
    pares.sort()
    return [z for z, _ in pares], [v for _, v in pares]


def _snapshot_descargas_tunel(ts, y_med_disp, y_sim_disp, metricas, variable: str) -> dict:
    """Snapshot persistible de la comparación de descargas del túnel.

    Helper puro (testeable sin servidor): lo consume el reporte PDF vía
    ``st.session_state["p7_valtun_resultado"]["descargas"]``. Los valores ya
    están en unidad de display.
    """
    return {
        "ts": list(ts),
        "y_med_disp": [float(v) for v in y_med_disp],
        "y_sim_disp": [float(v) for v in y_sim_disp],
        "metricas": metricas,
        "variable": variable,
    }


def _snapshot_perfil_tunel(magnitud: str, y_med_disp, y_sim_disp, metricas) -> dict:
    """Snapshot persistible de la comparación de perfil por zona del túnel.

    ``y_med_disp`` puede traer None en las zonas sin sensor (se preserva).
    """
    return {
        "magnitud": magnitud,
        "y_med_disp": [None if v is None else float(v) for v in y_med_disp],
        "y_sim_disp": [float(v) for v in y_sim_disp],
        "metricas": metricas,
    }


def _render_validacion_tunel(proyecto, res) -> None:
    """Valida el túnel semicontinuo contra descargas y perfil medidos.

    No hay overlay temporal por zona: ``simular_cascada`` no guarda historia
    ``(n_zonas, n_pasos)`` (deuda registrada en ``docs/notas/plan_datos_medidos_4.md``).
    Se comparan los dos objetos que sí son directos y libres del artefacto
    euleriano↔lagrangiano: las **descargas** (columna que sale, comparación
    lagrangiana) y el **perfil espacial** al cierre (foto instantánea, euleriana).
    """
    import numpy as np
    import pandas as pd

    from calculos import clima_medido as cm
    from calculos.ingesta_referencia import evaluar_ajuste, ingerir_referencia
    from calculos.metricas_validacion import calcular_metricas
    from calculos.validacion_camara import a_display, unidad_display
    from core.proyecto import SubtipoGranEscala
    from ui.componentes.validacion_widget import fig_overlay, fig_perfil_zonas

    subtipo = getattr(proyecto.configuracion, "subtipo_gran_escala", None)
    if subtipo != SubtipoGranEscala.SEMICONTINUO:
        return

    with st.expander(t("p7.validacion_tunel.titulo"), expanded=False):
        st.caption(t("p7.validacion_tunel.intro"))
        if res is None:
            st.info(t("p7.validacion_tunel.sin_resultado"))
            return

        # ---- 1) Descargas del túnel (comparación lagrangiana) ----
        st.markdown(t("p7.validacion_tunel.descargas.titulo"))
        st.caption(t("p7.validacion_tunel.descargas.ayuda"))

        descargas = getattr(res, "X_salida_por_avance", None)
        if descargas is None or len(descargas) == 0:
            st.info(t("p7.validacion_tunel.descargas.sin_datos"))
        elif getattr(res, "t0_utc", None) is None:
            st.info(t("p7.validacion_tunel.descargas.sin_ancla"))
        else:
            _render_descargas_tunel(res, cm, ingerir_referencia, evaluar_ajuste, fig_overlay)

        # ---- 2) Perfil espacial por zona (comparación euleriana) ----
        st.divider()
        st.markdown(t("p7.validacion_tunel.perfil.titulo"))
        st.caption(t("p7.validacion_tunel.perfil.ayuda"))

        magnitudes = {
            "X_producto": res.perfil_X_zonas,
            "T_camara": res.perfil_T_aire_zonas_K,
        }
        magnitud = st.selectbox(
            t("p7.validacion_tunel.perfil.magnitud"),
            options=list(magnitudes),
            format_func=lambda k: t(f"p4.validacion.variable.{k}"),
            key="p7_valtun_magnitud",
        )
        perfil_sim = magnitudes.get(magnitud)
        if perfil_sim is None or len(perfil_sim) == 0:
            st.info(t("p7.validacion_tunel.descargas.sin_datos"))
            return

        perfil_sim = np.asarray(perfil_sim, dtype=float)
        n_zonas = len(perfil_sim)
        unidad_disp = unidad_display(magnitud)
        tabla = pd.DataFrame(
            {
                t("p7.validacion_tunel.perfil.columna_zona"): list(range(1, n_zonas + 1)),
                "medido": [None] * n_zonas,
            }
        )
        editada = st.data_editor(
            tabla,
            key="p7_valtun_perfil",
            hide_index=True,
            width="stretch",
            column_config={
                "medido": st.column_config.NumberColumn(
                    t("p7.validacion_tunel.perfil.columna_medido") + f" [{unidad_disp}]"
                )
            },
            disabled=[t("p7.validacion_tunel.perfil.columna_zona")],
        )
        zonas_med, valores_med = _perfil_medido_desde_editor(editada.to_dict("records"), n_zonas)
        # Lo cargado está en unidad de display; el perfil simulado, en SI.
        perfil_sim_disp = a_display(perfil_sim, magnitud)
        y_med_alineado = [None] * n_zonas
        for z, v in zip(zonas_med, valores_med):
            y_med_alineado[z] = v

        st.plotly_chart(
            fig_perfil_zonas(
                list(range(1, n_zonas + 1)),
                y_med_alineado if zonas_med else None,
                perfil_sim_disp,
                medido_lbl=t("p7.validacion_tunel.medido"),
                simulado_lbl=t("p7.validacion_tunel.simulado"),
                titulo=t("p7.validacion_tunel.perfil.grafica_titulo"),
                x_lbl=t("p7.validacion_tunel.perfil.eje_x"),
                y_lbl=f"{t(f'p4.validacion.variable.{magnitud}')} [{unidad_disp}]",
            ),
            width="stretch",
        )
        if len(zonas_med) < 2:
            st.caption(t("p7.validacion_tunel.perfil.sin_medidos"))
            return
        metricas = calcular_metricas(
            np.array(valores_med, dtype=float),
            np.array([perfil_sim_disp[z] for z in zonas_med], dtype=float),
        )
        st.caption(
            t(
                "p7.validacion_tunel.metricas",
                rmse=f"{metricas.rmse:.3g} {unidad_disp}",
                mbe=f"{metricas.mbe:+.3g} {unidad_disp}",
                r2=f"{metricas.r2:.3f}",
                n=int(metricas.n_pares),
            )
        )
        # Persistir para el reporte PDF (sección de validación).
        st.session_state.setdefault("p7_valtun_resultado", {})["perfil"] = _snapshot_perfil_tunel(
            magnitud, y_med_alineado, list(perfil_sim_disp), metricas
        )


def _render_descargas_tunel(res, cm, ingerir_referencia, evaluar_ajuste, fig_overlay) -> None:
    """Sub-bloque de descargas: carga el muestreo de campo y lo contrasta."""
    import numpy as np

    from calculos.validacion_camara import a_display, pares_descarga_tunel, unidad_display
    from core.validacion import UNIDADES_REFERENCIA, ConfigReferencia, SenalReferencia

    arch = st.session_state.get("p7_valtun_archivo")
    if arch is None:
        subido = st.file_uploader(
            t("p4.validacion.uploader.label"),
            type=["csv", "txt", "xls", "xlsx"],
            key="p7_valtun_uploader",
        )
        if subido is not None:
            contenido = subido.read()
            st.session_state["p7_valtun_archivo"] = {
                "nombre": subido.name,
                "bytes": contenido,
                "hash": cm.hash_archivo(contenido),
            }
            st.session_state.pop("p7_valtun_uploader", None)
            st.rerun()
        return

    c_a, c_b = st.columns([4, 1])
    with c_a:
        st.markdown(
            t(
                "p4.validacion.archivo_cargado",
                nombre=arch["nombre"],
                kb=f"{len(arch['bytes']) / 1024:.0f}",
            )
        )
    with c_b:
        if st.button(t("p4.validacion.quitar"), key="p7_valtun_quitar"):
            st.session_state.pop("p7_valtun_archivo", None)
            st.session_state.pop("p7_valtun_resultado", None)
            st.rerun()

    try:
        tabla = cm.leer_tabla(arch["bytes"], arch["nombre"])
    except (ValueError, RuntimeError) as exc:
        st.error(t("p4.validacion.error", err=exc))
        return
    except Exception as exc:  # archivo arbitrario del usuario
        st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
        return

    columnas = [str(c) for c in tabla.columns]
    c1, c2, c3 = st.columns(3)
    with c1:
        col_ts = st.selectbox(
            t("p4.validacion.mapeo.timestamp"), options=columnas, key="p7_valtun_ts"
        )
    with c2:
        col_val = st.selectbox(
            t("p4.validacion.mapeo.valor"), options=columnas, key="p7_valtun_val"
        )
    with c3:
        unidad = st.selectbox(
            t("p4.validacion.mapeo.unidad"),
            options=list(UNIDADES_REFERENCIA["X_producto"]),
            format_func=lambda k: t(f"p4.validacion.unidad.{k}"),
            key="p7_valtun_unidad",
        )

    if not st.button(t("p4.validacion.procesar"), key="p7_valtun_procesar"):
        return
    try:
        cfg = ConfigReferencia(
            columna_timestamp=col_ts,
            columna_valor=col_val,
            variable="X_producto",
            unidad=unidad,
            zona_horaria="UTC",
        )
        senal: SenalReferencia = ingerir_referencia(tabla, cfg)
        ts_sim, y_sim = pares_descarga_tunel(res, res.t0_utc, "X_producto")
        metricas, y_med, y_sim_al, ts = evaluar_ajuste(senal, ts_sim, y_sim)
    except (ValueError, RuntimeError) as exc:
        st.error(t("p4.validacion.error", err=exc))
        return
    except Exception as exc:  # ingesta sobre datos arbitrarios
        st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
        return

    if metricas is None:
        st.warning(t("p4.validacion.sin_solape"))
        return

    unidad_disp = unidad_display("X_producto")
    st.plotly_chart(
        fig_overlay(
            ts,
            a_display(np.asarray(y_med), "X_producto"),
            a_display(np.asarray(y_sim_al), "X_producto"),
            medido_lbl=t("p7.validacion_tunel.medido"),
            simulado_lbl=t("p7.validacion_tunel.simulado"),
            titulo=t("p7.validacion_tunel.descargas.grafica_titulo"),
            y_lbl=t("p7.validacion_tunel.descargas.y_label"),
        ),
        width="stretch",
    )
    st.caption(
        t(
            "p7.validacion_tunel.metricas",
            rmse=f"{metricas.rmse:.3g} {unidad_disp}",
            mbe=f"{metricas.mbe:+.3g} {unidad_disp}",
            r2=f"{metricas.r2:.3f}",
            n=int(metricas.n_pares),
        )
    )
    # Persistir para el reporte PDF (sección de validación).
    st.session_state.setdefault("p7_valtun_resultado", {})["descargas"] = _snapshot_descargas_tunel(
        ts,
        a_display(np.asarray(y_med), "X_producto"),
        a_display(np.asarray(y_sim_al), "X_producto"),
        metricas,
        "X_producto",
    )
