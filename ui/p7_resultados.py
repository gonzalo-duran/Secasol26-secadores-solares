"""
Pestaña 7 — Resultados del Prediseño.

Orquesta todos los cálculos del sistema y muestra el dashboard integrado:
colector → auxiliar → cámara → balance global.

Las condiciones de operación representativas (T_amb, I_g, v_viento) se
ingresan manualmente o se sugieren desde los datos NASA POWER de P2.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from calculos.balance_global import ResultadosCompletos, calcular_todo
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from core.advertencias import Severidad
from ui.componentes.graficas import grafica_termodinamica_camara
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_T_AMB_DEFAULT_C = 25.0
_I_G_DEFAULT_W_M2 = 800.0
_V_VIENTO_DEFAULT_MS = 2.0
_HR_CAMARA_DEFAULT_PCT = 20.0
_LV_KJ_KG = 2450.0   # calor latente de vaporización [kJ/kg]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estado(ok: bool) -> str:
    return "✅" if ok else "❌"


def _resumen_camara(cam) -> tuple[float | None, float, str, bool]:
    """Extrae (t_h, masa_agua_kg, status_legible, ok) abstrayendo el tipo.

    `t_h` es ``None`` si el motor termodinámico no convergió. `ok` indica
    si el cálculo es utilizable para el balance energético.
    """
    if isinstance(cam, ResultadoMotorTermodinamico):
        ok = cam.t_secado_s is not None and cam.status == "X_obj_alcanzado"
        t_h = cam.t_secado_s / 3600.0 if cam.t_secado_s is not None else None
        return t_h, cam.masa_evaporada_total_kg, cam.status, ok
    status = "OK" if cam.convergencia_ok else cam.mensaje_convergencia
    return cam.t_secado_s / 3600.0, cam.masa_agua_extraida_kg, status, cam.convergencia_ok


def _mostrar_errores(errores: list[str]) -> None:
    for e in errores:
        st.error(f"❌ {e}")


def _mostrar_advertencias(advs: list[str]) -> None:
    for a in advs:
        st.warning(f"⚠️ {a}")


def _seccion_config(proyecto) -> None:
    """Muestra el estado de configuración de cada sección."""
    st.subheader("Estado de configuración")
    items = [
        ("P2 · Emplazamiento", proyecto.emplazamiento is not None),
        ("P2 · Clima (NASA POWER)", proyecto.clima is not None
         and proyecto.clima.datos is not None),
        ("P3 · Colector", proyecto.colector is not None),
        ("P4 · Cámara de Secado", proyecto.camara is not None),
        ("P5 · Auxiliar", proyecto.auxiliar is not None),
        ("P6 · Motor", proyecto.motor is not None),
    ]
    cols = st.columns(len(items))
    for col, (label, ok) in zip(cols, items):
        col.metric(label, _estado(ok))


def _sugerir_condiciones(proyecto) -> tuple[float, float, float]:
    """Devuelve (T_amb_C, I_g, v_viento) sugeridos desde datos de clima."""
    T_sug = _T_AMB_DEFAULT_C
    I_sug = _I_G_DEFAULT_W_M2
    v_sug = _V_VIENTO_DEFAULT_MS

    if proyecto.clima is not None and proyecto.clima.datos is not None:
        d = proyecto.clima.datos
        T_sug = round(kelvin_a_celsius(float(d["T_amb_K"].quantile(0.75))), 1)
        I_sug = round(float(d["GHI_Wm2"].quantile(0.90)), 0)
        v_sug = round(float(d["WS_ms"].mean()), 1)
    return T_sug, I_sug, v_sug


def _fig_drying_curve(solver_cam) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 3.5))
    t_h = solver_cam.t_array_s / 3600.0
    ax.plot(t_h, solver_cam.X_array_kg_kg, color="#1f77b4", linewidth=2)
    ax.axhline(solver_cam.X_eq_kg_kg, color="gray", linestyle="--", linewidth=1,
               label=f"X_eq = {solver_cam.X_eq_kg_kg:.3f}")
    t_fin = solver_cam.t_secado_s / 3600.0
    ax.axvline(t_fin, color="orange", linestyle="-.", linewidth=1.5,
               label=f"t = {t_fin:.1f} h")
    ax.set_xlabel("Tiempo [h]")
    ax.set_ylabel("Humedad X [kg/kg ms]")
    ax.set_title("Curva de secado")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


def _fig_sankey_simplificado(res: ResultadosCompletos) -> plt.Figure:
    """Gráfico de barras del balance energético."""
    etiquetas = []
    valores = []
    colores = []

    if res.energia_solar_util_MJ is not None and res.energia_solar_util_MJ > 0:
        etiquetas.append("Solar\n(colector)")
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
        etiquetas.append("Evaporación\n(útil)")
        valores.append(res.energia_secado_MJ)
        colores.append("#4caf50")

    if not etiquetas:
        return None

    fig, ax = plt.subplots(figsize=(7, 3))
    bars = ax.bar(etiquetas, valores, color=colores, alpha=0.85)
    for bar, val in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.2f} MJ", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Energía [MJ]")
    ax.set_title("Balance energético del ciclo de secado")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Generador de texto de resultados completos (mejora 5)
# ---------------------------------------------------------------------------

def _texto_resultados_completo(proyecto, res: "ResultadosCompletos",
                                T_amb_C: float, I_g: float,
                                v_viento: float, HR_cam_pct: float) -> str:
    from datetime import date
    from core import catalogo

    def desc(cat_dict: dict, id_mat: str) -> str:
        return cat_dict.get(id_mat, {}).get("descripcion", id_mat)

    sep = "=" * 55
    lines = [
        sep,
        "   PREDISEÑO DE SECADOR SOLAR",
        sep,
        f"  Fecha: {date.today()}",
        "",
        "CONDICIONES DE OPERACIÓN REPRESENTATIVAS",
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
    lines += ["", sep, "  RESULTADOS", sep]

    if res.colector is not None:
        col = res.colector
        _t_sal = getattr(col, 'T_salida_K', getattr(col, 'T_salida_mezcla_K', None))
        _regimen = getattr(col, 'regimen_flujo', getattr(col, 'regimen_ci', getattr(col, 'regimen_cs', '—')))
        lines += [
            "COLECTOR",
            f"  T entrada : {kelvin_a_celsius(col.T_entrada_K):.1f} °C",
            f"  T salida  : {kelvin_a_celsius(_t_sal):.1f} °C" if _t_sal else "  T salida  : —",
            f"  Q útil    : {col.Q_util_W:.0f} W",
            f"  η térmica : {col.eta_termica:.1%}",
            f"  Régimen   : {_regimen or '—'}",
        ]
        _re = getattr(col, 'Re_medio', getattr(col, 'Re_ci', getattr(col, 'Re_cs', None)))
        _hint = getattr(col, 'h_int_medio', getattr(col, 'h_int_ci', getattr(col, 'h_int_cs', None)))
        if _re:
            lines.append(f"  Re medio  : {_re:.0f} | h_int = {_hint:.1f} W/(m²·K)")

    if res.auxiliar is not None:
        aux = res.auxiliar
        lines += [
            "",
            "AUXILIAR",
            f"  ΔT       : {aux.delta_T_K:.1f} °C",
            f"  Q efect. : {aux.Q_efectivo_W:.0f} W",
        ]

    if res.camara is not None:
        cam = res.camara
        t_h_cam, masa_cam, status_cam, _ok = _resumen_camara(cam)
        lines += [
            "",
            "CÁMARA",
            f"  T oper.       : {kelvin_a_celsius(res.T_entrada_camara_K):.1f} °C",
        ]
        if isinstance(cam, ResultadoMotorTermodinamico):
            X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
            T_prod_final_C = (
                float(cam.T_prod_K[-1]) - 273.15 if len(cam.T_prod_K) else 0.0
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
                f"  Modo cálculo  : capa fina",
                f"  X_eq          : {cam.X_eq_kg_kg:.4f} kg/kg ms",
                f"  Tiempo secado : {t_h_cam:.2f} h",
                f"  Agua evap.    : {masa_cam:.3f} kg",
                f"  Convergencia  : {status_cam}",
            ]

    if res.energia_total_MJ:
        lines += [
            "",
            "BALANCE ENERGÉTICO",
            f"  E solar útil : {res.energia_solar_util_MJ:.4f} MJ",
            f"  E auxiliar   : {res.energia_auxiliar_MJ:.4f} MJ",
            f"  E motor      : {res.energia_motor_MJ:.4f} MJ",
            f"  E secado     : {res.energia_secado_MJ:.4f} MJ",
        ]
        if res.COP_secado:
            lines.append(f"  COP secado   : {res.COP_secado:.4f}")
        if res.fraccion_solar is not None:
            lines.append(f"  Fracción solar: {res.fraccion_solar:.1%}")

    lines.append("")
    return "\n".join(lines)


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
            min_value=-10.0, max_value=50.0,
            value=st.session_state.get("p7_T_amb_C", T_sug),
            step=0.5, format="%.1f",
        )
        st.session_state["p7_T_amb_C"] = T_amb_C
    with c2:
        I_g = st.number_input(
            "Irradiancia en plano colector [W/m²]",
            min_value=0.0, max_value=1200.0,
            value=st.session_state.get("p7_I_g", I_sug),
            step=10.0, format="%.0f",
            help="Irradiancia global sobre el plano del colector (POA).",
        )
        st.session_state["p7_I_g"] = I_g
    with c3:
        v_viento = st.number_input(
            "Velocidad del viento [m/s]",
            min_value=0.0, max_value=20.0,
            value=st.session_state.get("p7_v_viento", v_sug),
            step=0.5, format="%.1f",
        )
        st.session_state["p7_v_viento"] = v_viento
    with c4:
        HR_cam_pct = st.slider(
            "HR en cámara para X_eq [%]",
            min_value=5.0, max_value=80.0,
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
        _t_sal = getattr(col, 'T_salida_K', getattr(col, 'T_salida_mezcla_K', None))
        _regimen = getattr(col, 'regimen_flujo', getattr(col, 'regimen_ci', getattr(col, 'regimen_cs', '—')))
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("T entrada", f"{kelvin_a_celsius(col.T_entrada_K):.1f} °C")
        if _t_sal is not None:
            c2.metric("T salida", f"{kelvin_a_celsius(_t_sal):.1f} °C",
                      delta=f"+{_t_sal - col.T_entrada_K:.1f} °C")
        c3.metric("Q útil", f"{col.Q_util_W:.0f} W")
        c4.metric("η térmica", f"{col.eta_termica:.1%}")
        c5.metric("Régimen", _regimen or "—")
        _re = getattr(col, 'Re_medio', getattr(col, 'Re_ci', getattr(col, 'Re_cs', None)))
        _hint = getattr(col, 'h_int_medio', getattr(col, 'h_int_ci', getattr(col, 'h_int_cs', None)))
        if _re:
            st.caption(f"Re = {_re:.0f}  |  h_int = {_hint:.1f} W/(m²·K)")

    # --- Auxiliar ---
    if res.auxiliar is not None:
        st.subheader("Auxiliar Térmico")
        aux = res.auxiliar
        c1, c2, c3 = st.columns(3)
        c1.metric("T entrada auxiliar",
                  f"{kelvin_a_celsius(aux.T_entrada_K):.1f} °C")
        c2.metric("T salida auxiliar",
                  f"{kelvin_a_celsius(aux.T_salida_K):.1f} °C",
                  delta=f"+{aux.delta_T_K:.1f} °C")
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
                c1.metric("Tiempo de secado", "—",
                          help=f"No convergió: {cam.status}")
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
            st.pyplot(fig_td)
            plt.close(fig_td)
            st.caption(
                "ℹ️ El **T aire en cámara** (eje derecho, verde) varía poco porque el "
                "caudal de aire es el término dominante en el balance energético — "
                "el aire mantiene la temperatura cercana a T_entrada. Cada curva usa "
                "su propia escala (ejes izquierdo y derecho)."
            )
        else:
            c1, c2, c3, c4 = st.columns(4)
            t_h = cam.t_secado_s / 3600.0
            c1.metric("Tiempo de secado",
                      f"{t_h:.1f} h" if cam.convergencia_ok else f">{t_h:.0f} h")
            c2.metric("X equilibrio", f"{cam.X_eq_kg_kg:.4f} kg/kg ms",
                      help=f"Fuente: {cam.fuente_X_eq}")
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
            st.pyplot(fig_dry)
            plt.close(fig_dry)

    # --- Motor ---
    if proyecto.motor is not None and proyecto.motor.potencia_a_instalar_W:
        st.subheader("Motor / Ventilador")
        mot = proyecto.motor
        c1, c2, c3 = st.columns(3)
        c1.metric("ΔP sistema", f"{mot.perdida_carga_total_Pa:.1f} Pa")
        c2.metric("P eléctrica", f"{mot.potencia_electrica_W:.0f} W")
        c3.metric("P a instalar", f"{mot.potencia_a_instalar_W:.0f} W")

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
            st.pyplot(fig_bal)
            plt.close(fig_bal)

    # --- Resumen del ciclo ---
    st.subheader("Resumen del ciclo de secado")
    if proyecto.camara is not None and res.camara is not None:
        p = proyecto.camara.carga_producto
        ms = res.masa_producto_seco_kg
        t_h, masa_agua, _status, _ok = _resumen_camara(res.camara)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Masa producto fresco", f"{p.masa_total_kg:.1f} kg")
        c2.metric("Masa producto seco",
                  f"{ms:.2f} kg" if ms else "—",
                  help="masa_fresco / (1 + X₀)")
        c3.metric("Agua evaporada", f"{masa_agua:.2f} kg")
        c4.metric("Rendimiento en masa",
                  f"{res.rendimiento_masa:.1%}" if res.rendimiento_masa else "—",
                  help="kg_seco / kg_fresco")
        c5.metric("Tiempo de secado",
                  f"{t_h:.1f} h" if t_h is not None else "no convergió")

    # --- Tabla de resumen exportable ---
    with st.expander("Tabla de resultados completa"):
        filas = []
        if res.colector:
            col = res.colector
            _t_sal = getattr(col, 'T_salida_K', getattr(col, 'T_salida_mezcla_K', None))
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
        if res.camara:
            cam = res.camara
            t_h_cam, masa_cam, status_cam, _ok = _resumen_camara(cam)
            filas += [
                ("Cámara — T operación [°C]",
                 f"{kelvin_a_celsius(res.T_entrada_camara_K):.1f}"),
                ("Cámara — Tiempo secado [h]",
                 f"{t_h_cam:.2f}" if t_h_cam is not None else "no convergió"),
                ("Cámara — Agua evaporada [kg]", f"{masa_cam:.3f}"),
                ("Cámara — Status / convergencia", status_cam),
            ]
            if isinstance(cam, ResultadoMotorTermodinamico):
                X_final = float(cam.X_prod_kg_kg[-1]) if len(cam.X_prod_kg_kg) else 0.0
                T_prod_final_C = (
                    float(cam.T_prod_K[-1]) - 273.15 if len(cam.T_prod_K) else 0.0
                )
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
        if res.energia_total_MJ:
            filas += [
                ("Balance — E solar útil [MJ]",
                 f"{res.energia_solar_util_MJ:.4f}"),
                ("Balance — E auxiliar [MJ]",
                 f"{res.energia_auxiliar_MJ:.4f}"),
                ("Balance — E motor [MJ]",
                 f"{res.energia_motor_MJ:.4f}"),
                ("Balance — E secado [MJ]",
                 f"{res.energia_secado_MJ:.4f}"),
                ("Balance — COP",
                 f"{res.COP_secado:.4f}" if res.COP_secado else "—"),
                ("Balance — Fracción solar",
                 f"{res.fraccion_solar:.1%}" if res.fraccion_solar is not None else "100%"),
            ]

        if filas:
            import pandas as pd
            df = pd.DataFrame(filas, columns=["Parámetro", "Valor"])
            st.dataframe(df.set_index("Parámetro"), use_container_width=True)

    # --- Guardar resultados completos ---
    st.divider()
    texto_res = _texto_resultados_completo(
        proyecto, res,
        T_amb_C=T_amb_C, I_g=I_g, v_viento=v_viento, HR_cam_pct=HR_cam_pct,
    )
    st.download_button(
        "Guardar prediseño completo (.txt)",
        data=texto_res,
        file_name="prediseno_secador_solar.txt",
        mime="text/plain",
        use_container_width=True,
    )
