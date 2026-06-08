"""
Pestaña 7 — Resultados del Prediseño.

Orquesta todos los cálculos del sistema y muestra el dashboard integrado:
colector → auxiliar → cámara → balance global.

Las condiciones de operación representativas (T_amb, I_g, v_viento) se
ingresan manualmente o se sugieren desde los datos NASA POWER de P2.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from calculos.balance_global import (
    ResultadosCompletos,
    ResultadosCompletosTransitorio,
    calcular_todo,
    calcular_todo_transitorio,
    resumen_camara,
)
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from core.advertencias import Severidad
from core.proyecto import ModoAnalisis
from ui.componentes.graficas import grafica_termodinamica_camara, mostrar_plotly
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
    for e in errores:
        st.error(f"❌ {e}")


def _mostrar_advertencias(advs: list[str]) -> None:
    for a in advs:
        st.warning(f"⚠️ {a}")


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
    st.subheader("Chimenea Solar (convección natural)")

    m_punto = float(res_chim.get("m_punto_kgs", 0.0))
    # Caudal volumétrico a 1.1 kg/m³ (ρ_amb típica 25 °C, coherente con
    # _advertencia_caudal_inconsistente en balance_global).
    Q_m3h = m_punto / 1.1 * 3600.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Caudal natural",
        f"{m_punto * 1000:.1f} g/s",
        help="ṁ de equilibrio del lazo (cámara + colector + chimenea).",
    )
    c2.metric("Q volumétrico", f"{Q_m3h:.0f} m³/h", help="ṁ / ρ_amb (ρ ≈ 1.1 kg/m³).")
    c3.metric("v chimenea", f"{res_chim.get('v_chim_ms', 0.0):.2f} m/s")
    c4.metric("Re chimenea", f"{res_chim.get('Re_chimenea', 0.0):.0f}")

    dP_tiro = float(res_chim.get("delta_P_tiro_Pa", 0.0))
    dP_chim = float(res_chim.get("delta_P_chimenea_Pa", 0.0))
    dP_resto = float(res_chim.get("delta_P_resto_Pa", 0.0))
    H_eff = float(res_chim.get("H_eff_m", 0.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ΔP tiro", f"{dP_tiro:.2f} Pa", help="Empuje hidrostático disponible (g·H_eff·Δρ).")
    c2.metric(
        "ΔP chimenea", f"{dP_chim:.2f} Pa", help="Fricción + singulares del ducto de chimenea."
    )
    c3.metric(
        "ΔP resto lazo",
        f"{dP_resto:.2f} Pa",
        help="Pérdidas de colector + cámara escaladas ∝ (ṁ/ṁ_diseño)².",
    )
    c4.metric("H efectiva", f"{H_eff:.2f} m", help="altura_chimenea + alto_cámara.")

    # Caption con el balance del lazo (verificación cualitativa de cierre).
    if dP_tiro > 0:
        balance_err = abs(dP_tiro - dP_chim - dP_resto) / dP_tiro
        st.caption(
            f"Balance del lazo: ΔP_tiro = ΔP_chim + ΔP_resto "
            f"({dP_tiro:.2f} ≈ {dP_chim:.2f} + {dP_resto:.2f}, "
            f"error {balance_err:.1%})."
        )

    # Comparación con caudal de diseño de cámara: si difiere >30%, warning.
    desv = _desviacion_caudal_natural(res_chim, proyecto)
    if desv is not None and desv > 0.30:
        m_design = proyecto.camara.flujo.caudal_masico_kg_s
        st.warning(
            f"⚠️ El caudal natural ({m_punto * 1000:.1f} g/s) difiere "
            f"**{desv:.0%}** del caudal de diseño de la cámara "
            f"({m_design * 1000:.1f} g/s). Revisar diámetro/altura de la "
            "chimenea en P6 o el caudal de diseño en P4 para que ambos "
            "queden consistentes."
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
        with st.expander("Advertencias del cálculo", expanded=False):
            _mostrar_advertencias(res_tr.advertencias)

    # ---- Tarjetas resumen ----
    st.subheader("Resumen del prediseño")
    c1, c2, c3, c4 = st.columns(4)
    t_h_obj = (
        res_tr.t_X_obj_alcanzado_s / 3600.0 if res_tr.t_X_obj_alcanzado_s is not None else None
    )
    c1.metric(
        "X_obj alcanzado",
        f"{t_h_obj:.1f} h" if t_h_obj is not None else "No (>horizonte)",
        help="Tiempo desde t=0 en que la humedad del producto baja a X_obj.",
    )
    c2.metric(
        "Masa agua evaporada",
        f"{res_tr.masa_agua_evaporada_kg:.2f} kg",
    )
    c3.metric(
        "Energía secado",
        f"{res_tr.energia_secado_MJ:.2f} MJ",
        help="masa_agua × Lv",
    )
    cop_txt = f"{res_tr.COP_secado:.2f}" if res_tr.COP_secado is not None else "—"
    c4.metric("COP_secado", cop_txt)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("E_solar útil", f"{res_tr.energia_solar_util_MJ:.2f} MJ")
    c6.metric("E_auxiliar", f"{res_tr.energia_auxiliar_MJ:.2f} MJ")
    c7.metric("E_motor", f"{res_tr.energia_motor_MJ:.2f} MJ")
    fs_txt = f"{res_tr.fraccion_solar:.2f}" if res_tr.fraccion_solar is not None else "—"
    c8.metric("Fracción solar", fs_txt)

    # ---- Series temporales ----
    if res_tr.camara is None or res_tr.forzantes_aplicadas is None:
        st.warning("Sin trayectorias para graficar.")
        return

    t_h_fz = res_tr.forzantes_base.t_s / 3600.0
    t_h_cam = res_tr.camara.t_array_s / 3600.0

    st.subheader("Trayectorias del horizonte")

    # --- Panel 1: Aire externo (T_amb, I_g, v_viento) ---
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.T_amb_K - 273.15,
            name="T_amb",
            line=dict(color="#1f77b4", width=2),
        ),
        secondary_y=False,
    )
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.I_g_W_m2,
            name="I_g (POA)",
            line=dict(color="#ff7f0e", width=1.5, dash="dot"),
        ),
        secondary_y=True,
    )
    fig1.add_trace(
        go.Scatter(
            x=t_h_fz,
            y=res_tr.forzantes_base.v_viento_ms,
            name="v_viento",
            line=dict(color="#2ca02c", width=1),
        ),
        secondary_y=False,
    )
    fig1.update_yaxes(title_text="T_amb [°C] / v [m/s]", secondary_y=False)
    fig1.update_yaxes(title_text="I_g [W/m²]", secondary_y=True)
    fig1.update_xaxes(title_text="Tiempo [h]")
    fig1.update_layout(
        title="Forzantes climáticas del horizonte",
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
            name="T_sal_colector",
            line=dict(color="#d62728", width=2),
        )
    )
    if res_tr.auxiliar is not None:
        fig2.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=res_tr.forzantes_aplicadas.T_ent_K - 273.15,
                name="T_ent_cámara (post-aux)",
                line=dict(color="#9467bd", width=2),
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=res_tr.auxiliar.delta_T_K,
                name="ΔT_auxiliar",
                line=dict(color="#8c564b", width=1, dash="dash"),
            )
        )
    fig2.update_xaxes(title_text="Tiempo [h]")
    fig2.update_yaxes(title_text="T [°C] / ΔT [K]")
    fig2.update_layout(
        title="Acoplamiento colector → auxiliar → entrada de cámara",
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
            name="T_prod",
            line=dict(color="#1f77b4", width=2),
        ),
        secondary_y=False,
    )
    fig3.add_trace(
        go.Scatter(
            x=t_h_cam,
            y=res_tr.camara.X_prod_kg_kg,
            name="X_prod",
            line=dict(color="#2ca02c", width=2),
        ),
        secondary_y=True,
    )
    fig3.update_yaxes(title_text="T_prod [°C]", secondary_y=False)
    fig3.update_yaxes(title_text="X [kg/kg ms]", secondary_y=True)
    fig3.update_xaxes(title_text="Tiempo [h]")
    fig3.update_layout(
        title="Producto: temperatura y humedad",
        height=320,
        hovermode="x unified",
    )
    if res_tr.t_X_obj_alcanzado_s is not None:
        fig3.add_vline(
            x=res_tr.t_X_obj_alcanzado_s / 3600.0,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text="X_obj alcanzado",
            annotation_position="top",
        )
    mostrar_plotly(fig3, nombre="transitorio_Tprod_X")

    # --- Panel 4: tasa de evaporación ---
    fig4 = go.Figure()
    fig4.add_trace(
        go.Scatter(
            x=t_h_cam,
            y=res_tr.camara.m_dot_w_kg_s * 3600.0,
            name="ṁ_w",
            line=dict(color="#1f77b4", width=2),
        )
    )
    fig4.update_xaxes(title_text="Tiempo [h]")
    fig4.update_yaxes(title_text="Tasa evaporación [kg/h]")
    fig4.update_layout(
        title="Tasa de evaporación de agua del producto",
        height=280,
        hovermode="x unified",
    )
    mostrar_plotly(fig4, nombre="transitorio_evaporacion")

    # --- Panel 5: Chimenea solar (lazo natural) ---
    res_ch = getattr(res_tr, "chimenea", None)
    if res_ch is not None:
        st.subheader("Chimenea Solar — lazo natural (convección)")
        m_arr = np.asarray(res_ch["m_punto_kgs"])
        Tch_C = np.asarray(res_ch["T_chim_K"]) - 273.15
        dPT = np.asarray(res_ch["delta_P_tiro_Pa"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ṁ promedio", f"{res_ch['m_promedio_kgs'] * 1000:.1f} g/s")
        c2.metric("ṁ máximo", f"{res_ch['m_max_kgs'] * 1000:.1f} g/s")
        c3.metric("T_chim min/max", f"{Tch_C.min():.1f} / {Tch_C.max():.1f} °C")
        c4.metric(
            "Horas sin tiro",
            f"{int(res_ch['horas_sin_tiro'])} h",
            help="T_chim ≤ T_amb → caudal natural nulo en esa hora.",
        )

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Iteraciones Picard",
            f"{res_ch['iteraciones']}",
            help="Convergencia del lazo T_chim ↔ ṁ_nat.",
        )
        c2.metric(
            "Convergencia",
            "✅ sí" if res_ch["convergio"] else "❌ no",
            help=f"|ΔT_chim final| = {res_ch['delta_T_chim_final_K']:.2f} K",
        )
        c3.metric("H efectiva", f"{res_ch['H_eff_m']:.2f} m")

        fig_ch = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ch.add_trace(
            go.Scatter(
                x=t_h_fz, y=m_arr * 1000.0, name="ṁ natural", line=dict(color="#17becf", width=2)
            ),
            secondary_y=False,
        )
        fig_ch.add_trace(
            go.Scatter(x=t_h_fz, y=Tch_C, name="T_chim", line=dict(color="#e377c2", width=2)),
            secondary_y=True,
        )
        fig_ch.add_trace(
            go.Scatter(
                x=t_h_fz,
                y=dPT,
                name="ΔP tiro [Pa]",
                line=dict(color="#7f7f7f", width=1, dash="dot"),
            ),
            secondary_y=False,
        )
        fig_ch.update_yaxes(title_text="ṁ [g/s]  ·  ΔP_tiro [Pa]", secondary_y=False)
        fig_ch.update_yaxes(title_text="T_chim [°C]", secondary_y=True)
        fig_ch.update_xaxes(title_text="Tiempo [h]")
        fig_ch.update_layout(
            title="Lazo natural por chimenea: caudal, T_chim y tiro disponible",
            height=320,
            hovermode="x unified",
        )
        mostrar_plotly(fig_ch, nombre="chimenea")

    # ---- Diagnósticos extra ----
    with st.expander("Diagnósticos del horizonte"):
        d1, d2, d3 = st.columns(3)
        d1.metric(
            "T_prod máx",
            f"{(res_tr.T_prod_max_K - 273.15):.1f} °C" if res_tr.T_prod_max_K is not None else "—",
        )
        d2.metric("Horas anti-rehumect.", f"{res_tr.horas_clipeo_pol_B_s/3600.0:.2f} h")
        d3.metric("Horas HR>95%", f"{res_tr.horas_HR_alta_s/3600.0:.2f} h")
        if res_tr.auxiliar is not None:
            st.write(
                f"**Auxiliar activo**: {res_tr.auxiliar.horas_activo_s/3600.0:.2f} h "
                f"(fracción {res_tr.auxiliar.fraccion_horas_activo*100:.0f} %)"
            )
            st.write(
                f"**ΔT_aux máx**: {res_tr.auxiliar.delta_T_max_K:.1f} K  |  "
                f"**Q_aux máx**: {res_tr.auxiliar.Q_max_W:.0f} W"
            )


def _seccion_config(proyecto) -> None:
    """Muestra el estado de configuración de cada sección."""
    st.subheader("Estado de configuración")

    motor_o_chim_ok = (proyecto.motor is not None) or (
        proyecto.chimenea is not None and st.session_state.get("p6_chimenea_eval") is not None
    )
    if proyecto.motor is not None:
        label_p6 = "P6 · Motor"
    elif proyecto.chimenea is not None:
        label_p6 = "P6 · Chimenea"
    else:
        label_p6 = "P6 · Motor / Chimenea"

    items = [
        ("P2 · Emplazamiento", proyecto.emplazamiento is not None),
        (
            "P2 · Clima (NASA POWER)",
            proyecto.clima is not None and proyecto.clima.datos is not None,
        ),
        ("P3 · Colector", proyecto.colector is not None),
        ("P4 · Cámara de Secado", proyecto.camara is not None),
        ("P5 · Auxiliar", proyecto.auxiliar is not None),
        (label_p6, motor_o_chim_ok),
    ]
    cols = st.columns(len(items))
    for col, (label, ok) in zip(cols, items):
        col.metric(label, _estado(ok))


def _sugerir_condiciones(proyecto) -> tuple[float, float, float]:
    """Devuelve (T_amb_C, I_g, v_viento) sugeridos desde datos de clima.

    Para ``I_g`` (POA representativa) calcula la transposición horaria
    GHI/DNI/DHI → POA con el tilt/azimut del emplazamiento (helper
    ``calcular_POA_horizonte``) y toma el quantile 90 de la serie. Si la
    transposición falla (falta de DNI/DHI o sin emplazamiento), cae a
    ``GHI_Wm2.quantile(0.90)`` como aproximación conservadora.
    """
    T_sug = _T_AMB_DEFAULT_C
    I_sug = _I_G_DEFAULT_W_M2
    v_sug = _V_VIENTO_DEFAULT_MS

    if proyecto.clima is not None and proyecto.clima.datos is not None:
        d = proyecto.clima.datos
        T_sug = round(kelvin_a_celsius(float(d["T_amb_K"].quantile(0.75))), 1)
        v_sug = round(float(d["WS_ms"].mean()), 1)
        # I_g representativa: POA si hay emplazamiento + DNI/DHI; sino GHI.
        if proyecto.emplazamiento is not None:
            try:
                from calculos.clima_calc import calcular_POA_horizonte

                poa = calcular_POA_horizonte(d, proyecto.emplazamiento)
                I_sug = round(float(poa.quantile(0.90)), 0)
            except Exception:
                I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
        else:
            I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
    return T_sug, I_sug, v_sug


def _fig_drying_curve(solver_cam) -> go.Figure:
    t_h = solver_cam.t_array_s / 3600.0
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(solver_cam.X_array_kg_kg),
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name="X(t)",
        )
    )
    fig.add_hline(
        y=solver_cam.X_eq_kg_kg,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=f"X_eq={solver_cam.X_eq_kg_kg:.3f}",
        annotation_position="bottom right",
    )
    t_fin = solver_cam.t_secado_s / 3600.0
    fig.add_vline(
        x=t_fin,
        line=dict(color="orange", dash="dashdot", width=1.5),
        annotation_text=f"t={t_fin:.1f}h",
    )
    fig.update_xaxes(title_text="Tiempo [h]")
    fig.update_yaxes(title_text="Humedad X [kg/kg ms]", rangemode="tozero")
    fig.update_layout(title_text="Curva de secado", height=350, showlegend=True)
    return fig


def _fig_sankey_simplificado(res: ResultadosCompletos) -> go.Figure | None:
    """Gráfico de barras del balance energético."""
    etiquetas = []
    valores = []
    colores = []

    if res.energia_solar_util_MJ is not None and res.energia_solar_util_MJ > 0:
        etiquetas.append("Solar<br>(colector)")
        valores.append(res.energia_solar_util_MJ)
        colores.append("#f5a623")
    if res.energia_auxiliar_MJ is not None and res.energia_auxiliar_MJ > 0:
        etiquetas.append("Auxiliar")
        valores.append(res.energia_auxiliar_MJ)
        colores.append("#e05c2a")
    if res.energia_motor_MJ is not None and res.energia_motor_MJ > 0:
        etiquetas.append("Motor")
        valores.append(res.energia_motor_MJ)
        colores.append("#9c27b0")
    if res.energia_secado_MJ is not None and res.energia_secado_MJ > 0:
        etiquetas.append("Evaporación<br>(útil)")
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
    fig.update_yaxes(title_text="Energía [MJ]")
    fig.update_layout(
        title_text="Balance energético del ciclo de secado",
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
    else:
        lines.append("  (sin configurar)")

    lines += ["", "EMPLAZAMIENTO (P2)"]
    json_empl: dict = {}
    if empl is not None:
        lines += [
            f"  Latitud             : {empl.latitud_deg:.4f}°",
            f"  Longitud            : {empl.longitud_deg:.4f}°",
            f"  Altitud             : {empl.altitud_m:.1f} m",
            f"  Acimut colector     : {empl.acimut_colector_deg:.1f}° "
            "(convención Duffie: 0°=Sur)",
            f"  Pendiente colector  : {empl.pendiente_colector_deg:.1f}°",
            f"  Albedo del suelo    : {empl.albedo_suelo:.2f}",
            f"  Zona horaria        : {empl.zona_horaria}",
        ]
        json_empl = {
            "latitud_deg": empl.latitud_deg,
            "longitud_deg": empl.longitud_deg,
            "altitud_m": empl.altitud_m,
            "acimut_colector_deg_duffie": empl.acimut_colector_deg,
            "pendiente_colector_deg": empl.pendiente_colector_deg,
            "albedo_suelo": empl.albedo_suelo,
            "zona_horaria": empl.zona_horaria,
        }
    else:
        lines.append("  (sin configurar)")

    lines += ["", "CLIMA (NASA POWER)"]
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
            f"  Año fuente          : {clima.anio}",
            f"  Altitud NASA grid   : "
            + (f"{clima.altitud_nasa_m:.1f} m" if clima.altitud_nasa_m is not None else "—"),
            f"  Horas disponibles   : {n_total}",
            f"  T_amb media anual   : " + (f"{T_media_C:.1f} °C" if T_media_C is not None else "—"),
            f"  GHI media anual     : "
            + (f"{GHI_media:.0f} W/m²" if GHI_media is not None else "—"),
            f"  Calidad — huecos originales : {clima.calidad.n_huecos_originales}",
            f"  Calidad — interpoladas (h) : {clima.calidad.n_horas_interpoladas}",
            f"  Calidad — bloqueadas (h)   : {clima.calidad.n_horas_bloqueadas}",
            f"  Mayor hueco (h)            : {clima.calidad.mayor_hueco_h}",
        ]
        json_clima = {
            "anio": clima.anio,
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
    T_amb_C: float,
    I_g: float,
    v_viento: float,
    HR_cam_pct: float,
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
    lines += [
        "",
        "CONDICIONES DE OPERACIÓN REPRESENTATIVAS (P7)",
        f"  T ambiente          : {T_amb_C:.1f} °C",
        f"  Irradiancia (POA)   : {I_g:.0f} W/m²",
        f"  Velocidad viento    : {v_viento:.1f} m/s",
        f"  HR cámara (X_eq)    : {HR_cam_pct:.0f} %",
    ]

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
        bj = proyecto.camara.bandejas
        c = proyecto.camara.carga_producto
        f = proyecto.camara.flujo
        lines += [
            "",
            "CÁMARA DE SECADO",
            f"  Geometría  : {g.largo_m:.2f} m × {g.ancho_m:.2f} m × {g.alto_m:.2f} m",
            f"  Bandejas   : {bj.n_bandejas} | e capa = {bj.espesor_capa_m * 100:.1f} cm",
            f"  Producto   : {c.producto_id} | masa = {c.masa_total_kg:.1f} kg",
            f"  Caudal     : {f.caudal_masico_kg_s:.4f} kg/s | {f.direccion_flujo.value}",
        ]

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
                f"  Modo cálculo  : termodinámico",
                f"  Tiempo secado : "
                + (f"{t_h_cam:.2f} h" if t_h_cam is not None else "no convergió"),
                f"  Agua evap.    : {masa_cam:.3f} kg",
                f"  X final       : {X_final:.4f} kg/kg ms",
                f"  T prod. final : {T_prod_final_C:.1f} °C",
                f"  Status        : {status_cam}",
            ]
        else:
            lines += [
                f"  Modo cálculo  : capa fina estático",
                f"  X_eq          : {_cam_show.X_eq_kg_kg:.4f} kg/kg ms",
                f"  Tiempo secado : {t_h_cam:.2f} h",
                f"  Agua evap.    : {masa_cam:.3f} kg",
                f"  Convergencia  : {status_cam}",
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

    lines.append("")
    return "\n".join(lines)


def _json_resultados_completo(
    proyecto,
    res: "ResultadosCompletos",
    T_amb_C: float,
    I_g: float,
    v_viento: float,
    HR_cam_pct: float,
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
        else:
            t_h, masa, status, ok = _resumen_camara(cam_r)
            res_globales["camara"] = {
                "modo_calculo": "capa_fina",
                "t_secado_h": t_h,
                "masa_agua_extraida_kg": float(masa),
                "status": status,
                "convergencia_ok": ok,
                "X_eq_kg_kg": getattr(cam_r, "X_eq_kg_kg", None),
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
    return snapshot


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


def _render_barridos_parametricos(
    proyecto,
    modo: str,
    *,
    condiciones: dict | None = None,
    forzantes_base=None,
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
    st.subheader("🔀 Corridas paramétricas")
    st.caption(
        f"Variá un parámetro y compará hasta {_MAX_BARRIDOS} corridas (modo **{modo}**). "
        "Los resultados son efímeros: viven solo en esta sesión."
    )

    tipologia = proyecto.configuracion.tipologia
    params = parametros_para_tipologia(tipologia, modo)
    if not params:
        st.info("No hay parámetros barrideables para esta tipología y modo.")
        return

    key_estado = f"p7_barridos_{modo}"
    barridos: list = st.session_state.get(key_estado, [])

    with st.expander("➕ Configurar un nuevo barrido", expanded=not barridos):
        labels = {p.label: p for p in params}
        label_sel = st.selectbox(
            "Parámetro a variar", list(labels.keys()), key=f"barrido_param_{modo}"
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
                f"Mínimo [{parametro.unidad_ui}]",
                min_value=float(lo_ui),
                max_value=float(hi_ui),
                value=float(min_def),
                key=f"barrido_min_{modo}",
            )
        with c2:
            max_ui = st.number_input(
                f"Máximo [{parametro.unidad_ui}]",
                min_value=float(lo_ui),
                max_value=float(hi_ui),
                value=float(max_def),
                key=f"barrido_max_{modo}",
            )
        with c3:
            n_puntos = st.number_input(
                "N° de puntos",
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
            with st.expander("KPIs adicionales (avanzado)", expanded=False):
                for k in avanzados_modo:
                    if st.checkbox(f"{k.label} [{k.unidad}]", key=f"barrido_kpi_{modo}_{k.id}"):
                        kpis_extra.append(k.id)

        nombre_def = f"{parametro.label} ({len(barridos) + 1})"
        nombre = st.text_input(
            "Nombre de la corrida", value=nombre_def, key=f"barrido_nombre_{modo}"
        )

        # Estimación de tiempo.
        t_base = st.session_state.get(f"p7_t_calc_base_s_{modo}")
        if t_base:
            t_est = t_base * int(n_puntos)
            st.caption(
                f"⏱️ Tiempo estimado ≈ {t_est:.0f} s ({int(n_puntos)} × {t_base:.1f} s base)."
            )
            if t_est > 120:
                st.warning(
                    f"El barrido podría tardar ~{t_est:.0f} s. Reducí N° de puntos si es mucho."
                )

        bloqueado = len(barridos) >= _MAX_BARRIDOS
        if bloqueado:
            st.warning(f"Ya hay {_MAX_BARRIDOS} barridos. Eliminá uno para correr otro.")
        correr = st.button(
            "▶ Correr barrido", type="primary", key=f"barrido_run_{modo}", disabled=bloqueado
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
                n_dias=n_dias,
            )
            prog = st.progress(0.0)
            status = st.empty()

            def _cb(i, n, v, _status=status, _prog=prog, _p=parametro):
                _prog.progress(i / n)
                _status.text(f"Punto {i}/{n}: {_p.label} = {v:.4g} {_p.unidad_ui}")

            with st.spinner("Corriendo barrido..."):
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
    st.markdown("#### Barridos activos")
    for idx, b in enumerate(list(barridos)):
        color = _paleta_color_barrido(idx)
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(
                f"<span style='color:{color}'>●</span> **{b.nombre}** — "
                f"{b.parametro_meta.label}, {len(b.puntos)} puntos, "
                f"{b.t_ejecucion_s:.1f} s",
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("🗑️", key=f"barrido_del_{modo}_{idx}", help="Eliminar"):
                barridos.pop(idx)
                st.session_state[key_estado] = barridos
                st.rerun()

    # Tablas por barrido.
    for b in barridos:
        with st.expander(f"📋 Tabla — {b.nombre}", expanded=False):
            st.dataframe(_barrido_a_dataframe(b), width="stretch")

    # Gráficas por KPI. Si todos los barridos comparten parámetro, se superponen.
    params_distintos = {b.config.parametro_id for b in barridos}
    comparten_parametro = len(params_distintos) == 1
    if not comparten_parametro:
        st.info(
            "Los barridos activos varían parámetros distintos: cada gráfica usa "
            "su propio eje X y no se superponen."
        )

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
            else "valor del parámetro"
        )
        fig.update_layout(
            title=f"{kpi.label} [{kpi.unidad}]",
            xaxis_title=eje_x,
            yaxis_title=f"{kpi.label} [{kpi.unidad}]",
            height=360,
        )
        mostrar_plotly(fig, nombre=f"barrido_kpi_{kid}")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 7 — Resultados del Prediseño."""
    st.header("7 · Resultados del Prediseño")

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Estado de configuración
    # -----------------------------------------------------------------------
    _seccion_config(proyecto)
    st.divider()

    # Mínimo necesario para calcular
    if proyecto.camara is None:
        st.warning(
            "⚠️ Para calcular resultados es necesario configurar al menos la "
            "**Cámara de Secado (P4)**."
        )
        return

    # -----------------------------------------------------------------------
    # Panel anual prominente (modo ANUAL): vista principal arriba
    # -----------------------------------------------------------------------
    modo_analisis = getattr(proyecto.configuracion, "modo_analisis", None)
    if modo_analisis == ModoAnalisis.ANUAL:
        res_anual = st.session_state.get("p4_resultado_anual")
        if res_anual is not None:
            _render_operacion_anual_detalle(proyecto)
            _render_barridos_parametricos(proyecto, "anual")
            st.divider()
            st.markdown("### Cálculo de un día representativo (contexto adicional)")
            st.caption(
                "Debajo aparece el cálculo de un único día (constantes o "
                "transitorio). Es útil para validar el motor o explorar "
                "transitorios — los resultados anuales que importan están "
                "arriba. Si no querés verlo, ignorá esta sección."
            )
        else:
            st.info(
                "📅 **Modo ANUAL activado.** Para ver los resultados mensuales "
                "y agregados anuales, andá a **P4** y apretá el botón "
                "'📅 Calcular operación anual'. Mientras tanto se muestra el "
                "cálculo de un día representativo."
            )

    # -----------------------------------------------------------------------
    # Selector modo de cálculo: transitorio (horizonte de P4) vs constantes
    # -----------------------------------------------------------------------
    fz_horizonte = st.session_state.get("p4_forzantes_horizonte")
    horizonte_meta = st.session_state.get("p4_horizonte_meta") or {}
    horizonte_disponible = (
        fz_horizonte is not None and proyecto.camara.modo_calculo == "termodinamico"
    )

    if horizonte_disponible:
        st.subheader("Modo de cálculo")
        modo_p7 = st.radio(
            "¿Cómo evaluamos el prediseño completo?",
            options=[
                "Transitorio (horizonte de P4)",
                "Constantes representativas",
            ],
            index=0,
            horizontal=True,
            help=(
                "Transitorio: usa las forzantes horarias con las que corriste "
                "el motor termodinámico de cámara (P4), suma el auxiliar paso "
                "a paso y reporta resultados integrados sobre el horizonte.\n\n"
                "Constantes: condiciones representativas escalares — un punto "
                "de diseño único."
            ),
        )
    else:
        modo_p7 = "Constantes representativas"
        if proyecto.camara.modo_calculo == "termodinamico":
            st.info(
                "ℹ️ Para activar el **modo transitorio** corré primero la cámara "
                "en P4 con forzantes 'Día sintético' o 'Día real'. El horizonte "
                "se va a propagar automáticamente acá."
            )

    # ===========================================================================
    # RAMA: Transitorio (mejora 19)
    # ===========================================================================
    if modo_p7 == "Transitorio (horizonte de P4)":
        n_dias_hor = int(horizonte_meta.get("n_dias", 1))
        modo_fz_label = str(horizonte_meta.get("modo_forzantes", "sintético"))
        horizonte_tipo = horizonte_meta.get("horizonte_tipo")
        horizonte_h = float(fz_horizonte.t_s[-1]) / 3600.0

        st.subheader("Horizonte propagado de cámara")
        c1, c2, c3 = st.columns(3)
        _hz_txt = f"{n_dias_hor} día(s)"
        if horizonte_tipo and n_dias_hor > 1:
            _hz_txt += f" · {horizonte_tipo}"
        c1.metric("Horizonte", _hz_txt)
        c2.metric("Duración", f"{horizonte_h:.1f} h")
        c3.metric("Forzantes", modo_fz_label)
        st.caption(
            "Las forzantes T_amb(t), T_sal_col(t), v_viento(t), I_g(t), ω(t) "
            "vienen de P4 exactamente como las simulaste. Si configuraste un "
            "**Auxiliar (P5)**, se aplica paso a paso a la T_ent de cámara "
            "antes de re-correr el motor termodinámico."
        )

        st.divider()
        calcular_tr = st.button(
            "▶ Calcular pipeline transitoria",
            type="primary",
            key="p7_btn_calc_tr",
        )
        if calcular_tr:
            import time as _time

            _t0 = _time.perf_counter()
            with st.spinner("Corriendo auxiliar(t) + cámara TD + motor..."):
                res_tr: ResultadosCompletosTransitorio = calcular_todo_transitorio(
                    proyecto,
                    forzantes_base=fz_horizonte,
                    n_dias=n_dias_hor,
                )
            st.session_state["p7_resultados_tr"] = res_tr
            st.session_state["p7_t_calc_base_s_transitorio"] = _time.perf_counter() - _t0

        if "p7_resultados_tr" not in st.session_state:
            st.info("ℹ️ Presioná **Calcular** para evaluar la pipeline transitoria.")
            return

        res_tr = st.session_state["p7_resultados_tr"]
        _render_resultados_transitorios(res_tr, proyecto)

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
            n_dias=n_dias_hor,
        )
        return  # no caer en el flujo de constantes representativas

    # -----------------------------------------------------------------------
    # Condiciones de operación representativas
    # -----------------------------------------------------------------------
    st.subheader("Condiciones de operación representativas")
    st.caption(
        "Ingresá las condiciones del día / momento de análisis. "
        "Los valores sugeridos provienen de los datos NASA POWER de P2 "
        "(percentil 75 de T, percentil 90 de irradiancia)."
    )

    T_sug, I_sug, v_sug = _sugerir_condiciones(proyecto)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        T_amb_C = st.number_input(
            "T ambiente [°C]",
            min_value=-10.0,
            max_value=50.0,
            value=st.session_state.get("p7_T_amb_C", T_sug),
            step=0.5,
            format="%.1f",
        )
        st.session_state["p7_T_amb_C"] = T_amb_C
    with c2:
        I_g = st.number_input(
            "Irradiancia en plano colector [W/m²]",
            min_value=0.0,
            max_value=1200.0,
            value=st.session_state.get("p7_I_g", I_sug),
            step=10.0,
            format="%.0f",
            help="Irradiancia global sobre el plano del colector (POA).",
        )
        st.session_state["p7_I_g"] = I_g
    with c3:
        v_viento = st.number_input(
            "Velocidad del viento [m/s]",
            min_value=0.0,
            max_value=20.0,
            value=st.session_state.get("p7_v_viento", v_sug),
            step=0.5,
            format="%.1f",
        )
        st.session_state["p7_v_viento"] = v_viento
    with c4:
        HR_cam_pct = st.slider(
            "HR en cámara para X_eq [%]",
            min_value=5.0,
            max_value=80.0,
            value=st.session_state.get("p7_HR_cam", _HR_CAMARA_DEFAULT_PCT),
            step=5.0,
            help="HR del aire en la cámara. Determina la humedad de equilibrio del producto.",
        )
        st.session_state["p7_HR_cam"] = HR_cam_pct

    T_amb_K = celsius_a_kelvin(T_amb_C)
    HR_cam = HR_cam_pct / 100.0

    # -----------------------------------------------------------------------
    # Botón de cálculo
    # -----------------------------------------------------------------------
    st.divider()
    calcular = st.button("▶ Calcular prediseño completo", type="primary")

    if calcular:
        import time as _time

        _t0 = _time.perf_counter()
        with st.spinner("Calculando..."):
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
        st.info("ℹ️ Configurá las condiciones y presioná **Calcular** para ver los resultados.")
        return

    res: ResultadosCompletos = st.session_state["p7_resultados"]

    # Errores fatales
    if res.errores:
        st.error("Se detectaron errores que impiden el cálculo:")
        _mostrar_errores(res.errores)
        return

    # Advertencias
    if res.advertencias:
        with st.expander(f"⚠️ {len(res.advertencias)} advertencias del cálculo"):
            _mostrar_advertencias(res.advertencias)

    st.divider()

    # -----------------------------------------------------------------------
    # Dashboard de resultados
    # -----------------------------------------------------------------------

    # --- Colector ---
    if res.colector is not None:
        st.subheader("Colector Solar")
        col = res.colector
        _t_sal = getattr(col, "T_salida_K", getattr(col, "T_salida_mezcla_K", None))
        _regimen = getattr(
            col, "regimen_flujo", getattr(col, "regimen_ci", getattr(col, "regimen_cs", "—"))
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("T entrada", f"{kelvin_a_celsius(col.T_entrada_K):.1f} °C")
        if _t_sal is not None:
            c2.metric(
                "T salida",
                f"{kelvin_a_celsius(_t_sal):.1f} °C",
                delta=f"+{_t_sal - col.T_entrada_K:.1f} °C",
            )
        c3.metric("Q útil", f"{col.Q_util_W:.0f} W")
        c4.metric("η térmica", f"{col.eta_termica:.1%}")
        c5.metric("Régimen", _regimen or "—")
        _re = getattr(col, "Re_medio", getattr(col, "Re_ci", getattr(col, "Re_cs", None)))
        _hint = getattr(
            col, "h_int_medio", getattr(col, "h_int_ci", getattr(col, "h_int_cs", None))
        )
        if _re:
            st.caption(f"Re = {_re:.0f}  |  h_int = {_hint:.1f} W/(m²·K)")

    # --- Auxiliar ---
    if res.auxiliar is not None:
        st.subheader("Auxiliar Térmico")
        aux = res.auxiliar
        c1, c2, c3 = st.columns(3)
        c1.metric("T entrada auxiliar", f"{kelvin_a_celsius(aux.T_entrada_K):.1f} °C")
        c2.metric(
            "T salida auxiliar",
            f"{kelvin_a_celsius(aux.T_salida_K):.1f} °C",
            delta=f"+{aux.delta_T_K:.1f} °C",
        )
        c3.metric("Q efectivo", f"{aux.Q_efectivo_W / 1000:.2f} kW")

    # --- Temperatura de entrada a la cámara ---
    if res.T_entrada_camara_K is not None:
        st.info(
            f"🌡️ **Temperatura de entrada a la cámara: "
            f"{kelvin_a_celsius(res.T_entrada_camara_K):.1f} °C**"
        )

    # --- Cámara ---
    if res.camara is not None:
        st.subheader("Cámara de Secado")
        cam = res.camara
        if isinstance(cam, ResultadoMotorTermodinamico):
            c1, c2, c3, c4 = st.columns(4)
            if cam.t_secado_s is not None:
                c1.metric("Tiempo de secado", f"{cam.t_secado_s / 3600.0:.1f} h")
            else:
                c1.metric("Tiempo de secado", "—", help=f"No convergió: {cam.status}")
            c2.metric("Status", cam.status)
            c3.metric("Agua evaporada", f"{cam.masa_evaporada_total_kg:.2f} kg")
            X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
            c4.metric("X final", f"{X_final:.4f} kg/kg ms")

            if cam.status == "t_max_alcanzado":
                st.warning(
                    "⚠️ El motor termodinámico no alcanzó X_objetivo dentro del "
                    "tiempo máximo de simulación. Energías y COP no son confiables."
                )
            elif cam.status == "error":
                st.error(f"❌ Error en el motor termodinámico: {cam.status}")

            X_obj = proyecto.camara.carga_producto.humedad_objetivo_X
            prod_id = proyecto.camara.carga_producto.producto_id
            fig_td = grafica_termodinamica_camara(cam, X_obj, prod_id)
            mostrar_plotly(fig_td, nombre="camara_trayectorias")
            st.caption(
                "ℹ️ El **T aire en cámara** (eje derecho, verde) varía poco porque el "
                "caudal de aire es el término dominante en el balance energético — "
                "el aire mantiene la temperatura cercana a T_entrada. Cada curva usa "
                "su propia escala (ejes izquierdo y derecho)."
            )
        else:
            c1, c2, c3, c4 = st.columns(4)
            t_h = cam.t_secado_s / 3600.0
            c1.metric(
                "Tiempo de secado", f"{t_h:.1f} h" if cam.convergencia_ok else f">{t_h:.0f} h"
            )
            c2.metric(
                "X equilibrio", f"{cam.X_eq_kg_kg:.4f} kg/kg ms", help=f"Fuente: {cam.fuente_X_eq}"
            )
            c3.metric("Agua evaporada", f"{cam.masa_agua_extraida_kg:.2f} kg")
            c4.metric("MR objetivo", f"{cam.MR_obj:.4f}")

            if res.T_entrada_camara_K is not None:
                st.info(
                    f"ℹ️ **Modelo de capa fina:** supone temperatura del aire "
                    f"**T = {kelvin_a_celsius(res.T_entrada_camara_K):.1f} °C** y "
                    f"HR = **{HR_cam_pct:.0f} %** constantes durante todo el secado. "
                    "El modelo cinético no calcula temperaturas del producto ni flujos de "
                    "calor dinámicos. Para análisis con temperatura y humedad variables, "
                    "usar el modo **Termodinámico** en P4."
                )

            fig_dry = _fig_drying_curve(cam)
            mostrar_plotly(fig_dry, nombre="camara_secado")

    # --- Motor ---
    if proyecto.motor is not None and proyecto.motor.potencia_a_instalar_W:
        st.subheader("Motor / Ventilador")
        mot = proyecto.motor
        c1, c2, c3 = st.columns(3)
        c1.metric("ΔP sistema", f"{mot.perdida_carga_total_Pa:.1f} Pa")
        c2.metric("P eléctrica", f"{mot.potencia_electrica_W:.0f} W")
        c3.metric("P a instalar", f"{mot.potencia_a_instalar_W:.0f} W")

    # --- Chimenea solar (convección natural) ---
    if getattr(res, "chimenea", None) is not None:
        _render_chimenea_resultados(res.chimenea, proyecto)

    # --- Balance global ---
    if res.energia_total_MJ is not None and res.energia_total_MJ > 0:
        st.subheader("Balance Energético Global")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "COP de secado",
            f"{res.COP_secado:.3f}" if res.COP_secado else "—",
            help=(
                "masa_agua × Lv / energía_total. "
                "Valores típicos: 0.10–0.35 para secadores solares."
            ),
        )
        c2.metric(
            "Fracción solar",
            f"{res.fraccion_solar:.1%}" if res.fraccion_solar is not None else "100%",
            help="Energía del colector / (colector + auxiliar).",
        )
        c3.metric(
            "E secado",
            f"{res.energia_secado_MJ:.3f} MJ",
            help="masa_agua × Lv — energía realmente útil para evaporación.",
        )
        c4.metric(
            "E total",
            f"{res.energia_total_MJ:.3f} MJ",
            help="Solar + auxiliar + motor.",
        )

        fig_bal = _fig_sankey_simplificado(res)
        if fig_bal:
            mostrar_plotly(fig_bal, nombre="balance_energetico")

    # --- Resumen del ciclo ---
    st.subheader("Resumen del ciclo de secado")
    if proyecto.camara is not None and res.camara is not None:
        p = proyecto.camara.carga_producto
        ms = res.masa_producto_seco_kg
        t_h, masa_agua, _status, _ok = _resumen_camara(res.camara)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Masa producto fresco", f"{p.masa_total_kg:.1f} kg")
        c2.metric(
            "Masa producto seco", f"{ms:.2f} kg" if ms else "—", help="masa_fresco / (1 + X₀)"
        )
        c3.metric("Agua evaporada", f"{masa_agua:.2f} kg")
        c4.metric(
            "Rendimiento en masa",
            f"{res.rendimiento_masa:.1%}" if res.rendimiento_masa else "—",
            help="kg_seco / kg_fresco",
        )
        c5.metric("Tiempo de secado", f"{t_h:.1f} h" if t_h is not None else "no convergió")

    # --- Tabla de resumen exportable ---
    with st.expander("Tabla de resultados completa"):
        filas = []
        if res.colector:
            col = res.colector
            _t_sal = getattr(col, "T_salida_K", getattr(col, "T_salida_mezcla_K", None))
            filas += [
                ("Colector — T entrada [°C]", f"{kelvin_a_celsius(col.T_entrada_K):.1f}"),
                ("Colector — T salida [°C]", f"{kelvin_a_celsius(_t_sal):.1f}" if _t_sal else "—"),
                ("Colector — Q útil [W]", f"{col.Q_util_W:.0f}"),
                ("Colector — η térmica", f"{col.eta_termica:.1%}"),
            ]
        if res.auxiliar:
            aux = res.auxiliar
            filas += [
                ("Auxiliar — ΔT [°C]", f"{aux.delta_T_K:.1f}"),
                ("Auxiliar — Q efectivo [W]", f"{aux.Q_efectivo_W:.0f}"),
            ]
        if res.camara is not None:
            cam = res.camara
            t_h_cam, masa_cam, status_cam, _ok = _resumen_camara(cam)
            T_op_str = (
                f"{kelvin_a_celsius(res.T_entrada_camara_K):.1f}" if res.T_entrada_camara_K else "—"
            )
            filas += [
                ("Cámara — T operación [°C]", T_op_str),
                (
                    "Cámara — Tiempo secado [h]",
                    f"{t_h_cam:.2f}" if t_h_cam is not None else "no convergió",
                ),
                ("Cámara — Agua evaporada [kg]", f"{masa_cam:.3f}"),
                ("Cámara — Status / convergencia", status_cam),
            ]
            if isinstance(cam, ResultadoMotorTermodinamico):
                X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
                T_prod_final_C = float(cam.T_prod_K[-1]) - 273.15 if len(cam.T_prod_K) else 0.0
                filas += [
                    ("Cámara — X final [kg/kg ms]", f"{X_final:.4f}"),
                    ("Cámara — T producto final [°C]", f"{T_prod_final_C:.1f}"),
                ]
            else:
                filas.append(("Cámara — X_eq [kg/kg ms]", f"{cam.X_eq_kg_kg:.4f}"))
        if proyecto.motor and proyecto.motor.potencia_a_instalar_W:
            mot = proyecto.motor
            filas += [
                ("Motor — ΔP [Pa]", f"{mot.perdida_carga_total_Pa:.1f}"),
                ("Motor — P eléctrica [W]", f"{mot.potencia_electrica_W:.1f}"),
                ("Motor — P a instalar [W]", f"{mot.potencia_a_instalar_W:.1f}"),
            ]
        if getattr(res, "chimenea", None) is not None:
            ch = res.chimenea
            m_punto = float(ch.get("m_punto_kgs", 0.0))
            filas += [
                ("Chimenea — Caudal natural [g/s]", f"{m_punto * 1000:.2f}"),
                ("Chimenea — Caudal vol. [m³/h]", f"{m_punto / 1.1 * 3600.0:.1f}"),
                ("Chimenea — v [m/s]", f"{ch.get('v_chim_ms', 0.0):.3f}"),
                ("Chimenea — Re", f"{ch.get('Re_chimenea', 0.0):.0f}"),
                ("Chimenea — ΔP tiro [Pa]", f"{ch.get('delta_P_tiro_Pa', 0.0):.3f}"),
                ("Chimenea — ΔP ducto [Pa]", f"{ch.get('delta_P_chimenea_Pa', 0.0):.3f}"),
                ("Chimenea — ΔP resto [Pa]", f"{ch.get('delta_P_resto_Pa', 0.0):.3f}"),
                ("Chimenea — H efectiva [m]", f"{ch.get('H_eff_m', 0.0):.2f}"),
            ]
        if res.energia_total_MJ:
            filas += [
                ("Balance — E solar útil [MJ]", f"{res.energia_solar_util_MJ:.4f}"),
                ("Balance — E auxiliar [MJ]", f"{res.energia_auxiliar_MJ:.4f}"),
                ("Balance — E motor [MJ]", f"{res.energia_motor_MJ:.4f}"),
                ("Balance — E secado [MJ]", f"{res.energia_secado_MJ:.4f}"),
                ("Balance — COP", f"{res.COP_secado:.4f}" if res.COP_secado else "—"),
                (
                    "Balance — Fracción solar",
                    f"{res.fraccion_solar:.1%}" if res.fraccion_solar is not None else "100%",
                ),
            ]

        if filas:
            import pandas as pd

            df = pd.DataFrame(filas, columns=["Parámetro", "Valor"])
            st.dataframe(df.set_index("Parámetro"), width="stretch")

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


def _render_operacion_anual_detalle(proyecto) -> None:
    """Panel detalle de operación anual de cámara — visible si P4 lo calculó.

    Muestra tabla 12 meses con t_secado, m_evap/batch, n_batches, kg/mes y
    las 4 eficiencias Augustus Leon. Más gráfica de barras kg/mes con línea
    de η_total sobre eje secundario.
    """
    from calculos.operacion_anual_camara import ResultadosAnualCamara

    res_anual: ResultadosAnualCamara | None = st.session_state.get("p4_resultado_anual")
    if res_anual is None:
        return

    st.divider()
    st.subheader("Operación anual de cámara")
    st.caption(
        "Resultados del motor termodinámico corrido mes a mes sobre el día "
        "típico, escalado por la cantidad de batches/mes configurada en P4. "
        "Eficiencias según método Augustus Leon (RSER 2002)."
    )

    if res_anual.advertencias:
        for msg in res_anual.advertencias:
            st.warning(f"⚠️ {msg}")

    # Resumen anual (mismo que P4 pero acá lo tenemos integrado en P7)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("kg secados/año", f"{res_anual.kg_secados_anual:.0f}")
    col2.metric("η_total media", f"{res_anual.eta_total_anual_media * 100:.1f}%")
    col3.metric("t_secado promedio", f"{res_anual.t_secado_promedio_h:.1f} h")
    col4.metric("Energía solar anual", f"{res_anual.E_solar_anual_MJ:.0f} MJ")

    # Tabla 12 meses
    import pandas as pd

    meses_nombres = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]
    filas = []
    for p in res_anual.puntos_mensuales:
        filas.append(
            {
                "Mes": meses_nombres[p.mes - 1],
                "t_secado [h]": round(p.t_secado_h, 1),
                "Convergió": "✓" if p.convergio else "—",
                "m_evap/batch [kg]": round(p.m_evap_kg_por_batch, 2),
                "batches/mes": p.n_batches,
                "kg/mes": round(p.kg_secados_mes, 1),
                "η_drying [%]": round(p.eta_drying * 100, 2),
                "η_pickup [%]": round(p.eta_pickup * 100, 1),
                "η_térmica [%]": round(p.eta_termica * 100, 1),
                "η_total [%]": round(p.eta_total * 100, 2),
            }
        )
    df_meses = pd.DataFrame(filas).set_index("Mes")
    st.dataframe(df_meses, width="stretch")

    # Gráfica de barras kg/mes con línea η_total
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(
        x=meses_nombres,
        y=[p.kg_secados_mes for p in res_anual.puntos_mensuales],
        name="kg/mes",
        marker_color="#1f77b4",
    )
    fig.add_scatter(
        x=meses_nombres,
        y=[p.eta_total * 100 for p in res_anual.puntos_mensuales],
        name="η_total [%]",
        mode="lines+markers",
        line=dict(color="#d62728", width=2),
        marker=dict(size=8),
        yaxis="y2",
    )
    fig.update_layout(
        title="Producción mensual y eficiencia del sistema",
        xaxis_title="Mes",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
    )
    fig.update_yaxes(title_text="Producto secado [kg/mes]", secondary_y=False)
    fig.update_yaxes(title_text="η_total [%]", secondary_y=True)
    mostrar_plotly(fig, nombre="operacion_anual")


def _render_botones_guardado(
    proyecto, res, *, T_amb_C: float, I_g: float, v_viento: float, HR_cam_pct: float
) -> None:
    """Renderiza el bloque de botones .txt / .json / PDF al pie de P7.

    Compartido entre la rama de modo transitorio y la de constantes
    representativas. ``res`` puede ser ``ResultadosCompletos`` o
    ``ResultadosCompletosTransitorio`` — ambos funcionan vía ``getattr``.
    """
    from ui.componentes.serializacion import (
        dump_json,
        nombre_archivo_descarga,
        nombre_archivo_reporte,
    )

    st.divider()
    texto_res = _texto_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
    )
    json_res = _json_resultados_completo(
        proyecto,
        res,
        T_amb_C=T_amb_C,
        I_g=I_g,
        v_viento=v_viento,
        HR_cam_pct=HR_cam_pct,
    )
    col_txt, col_json = st.columns(2)
    with col_txt:
        st.download_button(
            "Guardar prediseño completo (.txt)",
            data=texto_res,
            file_name=nombre_archivo_descarga(proyecto, "prediseno_completo", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            "Guardar prediseño completo (.json)",
            data=dump_json(json_res),
            file_name=nombre_archivo_descarga(proyecto, "prediseno_completo", "json"),
            mime="application/json",
            width="stretch",
        )

    # --- Generar reporte PDF ---
    st.markdown("##### Reporte PDF")
    st.caption(
        "Genera un PDF completo con todas las secciones, tablas de configuración "
        "y gráficas. Puede tardar 10–30 s al generar las imágenes."
    )
    if st.button("Generar reporte PDF", type="primary", width="stretch", key="p7_generar_pdf"):
        from ui.reporte import generar_reporte_pdf

        with st.spinner("Generando reporte PDF (incluye exportación de gráficas)..."):
            try:
                pdf_bytes = generar_reporte_pdf(
                    proyecto,
                    st.session_state,
                    res,
                    T_amb_C=T_amb_C,
                    I_g=I_g,
                    v_viento=v_viento,
                    HR_cam_pct=HR_cam_pct,
                )
                st.session_state["p7_reporte_pdf"] = pdf_bytes
                st.success(
                    f"✅ Reporte generado ({len(pdf_bytes) / 1024:.0f} KB). "
                    "Descargá con el botón debajo."
                )
            except Exception as exc:
                st.error(f"❌ Error generando el reporte: {exc}")
                st.session_state.pop("p7_reporte_pdf", None)

    pdf_cached = st.session_state.get("p7_reporte_pdf")
    if pdf_cached is not None:
        st.download_button(
            "Descargar reporte PDF",
            data=pdf_cached,
            file_name=nombre_archivo_reporte(proyecto, "pdf"),
            mime="application/pdf",
            width="stretch",
        )
