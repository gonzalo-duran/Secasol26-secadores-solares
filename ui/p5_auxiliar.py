"""
Pestaña 5 — Calentamiento Auxiliar.

Permite configurar un sistema de calentamiento auxiliar (resistencia eléctrica
o quemador de biomasa) y calcula el salto térmico que produce sobre el flujo de
aire que viene del colector (o del ambiente en modo respaldo independiente).

El auxiliar es opcional: si el usuario no lo activa, proyecto.auxiliar = None.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from calculos.auxiliar_calc import (
    ResultadosAuxiliarTransitorio,
    calcular_auxiliar_transitorio,
)
from core.auxiliar import (
    Auxiliar,
    CargaArranque,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
    advertencias_auxiliar,
)
from ui.componentes.advertencias_widget import render_advertencias
from ui.componentes.graficas import mostrar_plotly
from ui.componentes.idiomas import t
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius
from ui.componentes.vigencia import horizonte_vigente

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_T_AMB_DEFAULT_C: float = 25.0
_T_MAX_DEFAULT_C: float = 70.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia traducida por código (widget único, F5)."""
    render_advertencias(adv_list, con_sugerencia=False)


# ---------------------------------------------------------------------------
# Generador de texto de configuración
# ---------------------------------------------------------------------------


def _texto_config_auxiliar(aux: "Auxiliar") -> str:
    """Snapshot .txt del auxiliar (config + cálculos derivados del dataclass)."""
    from datetime import date

    from core.auxiliar import TipoAuxiliar, advertencias_auxiliar

    sep = "=" * 60
    lines = [
        sep,
        "        CONFIGURACIÓN DEL AUXILIAR TÉRMICO",
        sep,
        f"Fecha de exportación: {date.today()}",
        "",
        "TIPO Y OPERACIÓN",
        f"  Tipo               : {aux.tipo.value}",
        f"  Modo operación     : {aux.modo_operacion.value}",
        f"  Disponible nocturno: {'Sí' if aux.disponible_nocturno else 'No'}",
        "",
        "POTENCIA Y TEMPERATURA",
        f"  Potencia nominal   : {aux.potencia_nominal_W / 1000:.3f} kW "
        f"({aux.potencia_nominal_W:.0f} W)",
        f"  Fracción operación : {aux.fraccion_potencia_operacion:.1%}",
        f"  Potencia efectiva  : {aux.potencia_efectiva_W() / 1000:.3f} kW "
        f"({aux.potencia_efectiva_W():.0f} W)",
        f"  T_max salida       : {aux.temperatura_maxima_salida_K - 273.15:.1f} °C "
        f"({aux.temperatura_maxima_salida_K:.2f} K)",
        "  Set-point T        : "
        + (
            f"{aux.set_point_T_K - 273.15:.1f} °C ({aux.set_point_T_K:.2f} K)"
            if aux.set_point_T_K is not None
            else "(libre, sin control de T)"
        ),
    ]
    if aux.tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
        consumo = aux.consumo_biomasa_efectivo_kg_h()
        lines += [
            "",
            "QUEMADOR DE BIOMASA",
            f"  Combustible        : {aux.tipo_biomasa or '—'}",
            "  PCI                : " + (f"{aux.PCI_MJ_kg:.2f} MJ/kg" if aux.PCI_MJ_kg else "—"),
            "  η quemador         : "
            + (f"{aux.eficiencia_quemador:.1%}" if aux.eficiencia_quemador else "—"),
            "  Consumo nominal    : "
            + (
                f"{aux.consumo_biomasa_kg_h:.3f} kg/h"
                if aux.consumo_biomasa_kg_h
                else "(calculado por PCI)"
            ),
            "  Consumo efectivo   : " + (f"{consumo:.3f} kg/h" if consumo is not None else "—"),
        ]
    elif aux.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        lines += [
            "",
            "RESISTENCIA ELÉCTRICA",
            "  Tensión            : "
            + (f"{aux.tension_V:.0f} V" if aux.tension_V else "(no especificada)"),
            "  Corriente máx.     : "
            + (
                f"{aux.corriente_maxima_A:.2f} A" if aux.corriente_maxima_A else "(no especificada)"
            ),
        ]
        if aux.tension_V:
            i_aprox = aux.potencia_efectiva_W() / aux.tension_V
            lines.append(f"  Corriente estimada : {i_aprox:.2f} A (P_efec / V, cos φ = 1)")
    if aux.cargas_arranque:
        lines += ["", "CALENDARIO DE ARRANQUE (híbrido mañana/tarde)"]
        for i, c in enumerate(aux.cargas_arranque, start=1):
            lines.append(
                f"  Carga {i}: inicio {c.hora_inicio_h:.1f} h · duración {c.duracion_h:.1f} h"
            )
        cobertura = sum(c.duracion_h for c in aux.cargas_arranque)
        lines.append(f"  Cobertura total    : {cobertura:.1f} h/día")
    if aux.notas:
        lines += ["", "NOTAS", f"  {aux.notas}"]

    advs = advertencias_auxiliar(aux)
    lines += ["", "ADVERTENCIAS ESTÁTICAS DE DISEÑO"]
    if not advs:
        lines.append("  (ninguna)")
    else:
        for a in advs:
            lines.append(f"  [{a.severidad.value}] {a.codigo}: {a.mensaje}")
    lines += ["", sep, "  RESULTADOS DE SIMULACIÓN", sep]
    lines.append("  ⚠ Los resultados del auxiliar se integran en el balance")
    lines.append("    global de P7 (no hay simulación independiente en P5).")
    lines.append("  Ver 'Prediseño completo' para Q_efectivo, ΔT y energía aportada.")
    lines.append("")
    return "\n".join(lines)


def _from_json_auxiliar(data: dict) -> "Auxiliar":
    """Reconstruye un ``Auxiliar`` desde un dict producido por
    ``_json_config_auxiliar``.

    Raises:
        KeyError/ValueError: si faltan campos obligatorios o un Enum no es válido.
    """
    biomasa = data.get("biomasa") or {}
    re_dict = data.get("resistencia_electrica") or {}
    set_point = data.get("set_point_T_K")
    return Auxiliar(
        tipo=TipoAuxiliar(data["tipo"]),
        modo_operacion=ModoOperacionAuxiliar(data["modo_operacion"]),
        potencia_nominal_W=float(data["potencia_nominal_W"]),
        temperatura_maxima_salida_K=float(data["temperatura_maxima_salida_K"]),
        set_point_T_K=float(set_point) if set_point is not None else None,
        fraccion_potencia_operacion=float(data.get("fraccion_potencia_operacion", 1.0)),
        disponible_nocturno=bool(data.get("disponible_nocturno", False)),
        tipo_biomasa=biomasa.get("tipo_biomasa"),
        PCI_MJ_kg=(float(biomasa["PCI_MJ_kg"]) if biomasa.get("PCI_MJ_kg") is not None else None),
        eficiencia_quemador=(
            float(biomasa["eficiencia_quemador"])
            if biomasa.get("eficiencia_quemador") is not None
            else None
        ),
        consumo_biomasa_kg_h=(
            float(biomasa["consumo_biomasa_kg_h_nominal"])
            if biomasa.get("consumo_biomasa_kg_h_nominal") is not None
            else None
        ),
        tension_V=(float(re_dict["tension_V"]) if re_dict.get("tension_V") is not None else None),
        corriente_maxima_A=(
            float(re_dict["corriente_maxima_A"])
            if re_dict.get("corriente_maxima_A") is not None
            else None
        ),
        cargas_arranque=[
            CargaArranque(
                hora_inicio_h=float(c["hora_inicio_h"]),
                duracion_h=float(c["duracion_h"]),
            )
            for c in (data.get("cargas_arranque") or [])
        ],
        notas=data.get("notas") or "",
    )


def _json_config_auxiliar(aux: "Auxiliar") -> dict:
    """Snapshot reconstruible (dict) del auxiliar."""
    from datetime import date

    from core.auxiliar import TipoAuxiliar, advertencias_auxiliar

    base = {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "auxiliar",
        "tipo": aux.tipo.value,
        "modo_operacion": aux.modo_operacion.value,
        "potencia_nominal_W": aux.potencia_nominal_W,
        "fraccion_potencia_operacion": aux.fraccion_potencia_operacion,
        "potencia_efectiva_W": aux.potencia_efectiva_W(),
        "temperatura_maxima_salida_K": aux.temperatura_maxima_salida_K,
        "set_point_T_K": aux.set_point_T_K,
        "disponible_nocturno": aux.disponible_nocturno,
        "cargas_arranque": [
            {"hora_inicio_h": c.hora_inicio_h, "duracion_h": c.duracion_h}
            for c in aux.cargas_arranque
        ],
        "notas": aux.notas,
    }
    if aux.tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
        base["biomasa"] = {
            "tipo_biomasa": aux.tipo_biomasa,
            "PCI_MJ_kg": aux.PCI_MJ_kg,
            "eficiencia_quemador": aux.eficiencia_quemador,
            "consumo_biomasa_kg_h_nominal": aux.consumo_biomasa_kg_h,
            "consumo_biomasa_efectivo_kg_h": aux.consumo_biomasa_efectivo_kg_h(),
        }
    elif aux.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        base["resistencia_electrica"] = {
            "tension_V": aux.tension_V,
            "corriente_maxima_A": aux.corriente_maxima_A,
            "corriente_estimada_A": (
                aux.potencia_efectiva_W() / aux.tension_V if aux.tension_V else None
            ),
        }
    base["advertencias_diseno"] = [
        {
            "codigo": a.codigo,
            "severidad": a.severidad.value,
            "mensaje": a.mensaje,
            "campo": a.campo,
            "sugerencia": a.sugerencia,
            "contexto": a.contexto,
        }
        for a in advertencias_auxiliar(aux)
    ]
    base["resultados"] = {
        "ejecutado": False,
        "nota": (
            "El auxiliar no se simula de forma independiente en P5. "
            "Sus resultados de operación (Q_efectivo, ΔT, energía aportada) "
            "se computan en el balance global de P7."
        ),
    }
    return base


# ---------------------------------------------------------------------------
# Entregable transitorio: T_sal_aux(t)
# ---------------------------------------------------------------------------


def _grafica_tsal_aux(
    aux_tr: "ResultadosAuxiliarTransitorio", set_point_K: float | None
) -> go.Figure:
    """Gráfica del entregable de P5: T_entrada_aux(t) → T_sal_aux(t).

    T_entrada_aux(t) es la salida del colector (o el ambiente en CAJA), modulada
    por el clima. La banda entre ambas curvas es el ΔT sensible que aporta el
    auxiliar (ΔT = Q_eff/(ṁ·cp)). Si hay set-point, se dibuja como línea de corte.
    """
    t_h = aux_tr.t_s / 3600.0
    T_ent_C = aux_tr.T_entrada_K - 273.15
    T_sal_C = aux_tr.T_salida_K - 273.15
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(T_ent_C),
            name=t("p5.tsal_aux.leyenda.t_entrada"),
            line=dict(color="#d62728", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(T_sal_C),
            name=t("p5.tsal_aux.leyenda.t_salida"),
            line=dict(color="#ff7f0e", width=2),
            fill="tonexty",
            fillcolor="rgba(255,127,14,0.15)",
        )
    )
    if set_point_K is not None:
        fig.add_hline(
            y=set_point_K - 273.15,
            line=dict(color="#2ca02c", dash="dot", width=1.5),
            annotation_text=t("p5.tsal_aux.leyenda.set_point", v=set_point_K - 273.15),
        )
    fig.update_xaxes(title_text=t("p5.tsal_aux.eje_tiempo"))
    fig.update_yaxes(title_text=t("p5.tsal_aux.eje_t"))
    fig.update_layout(
        title=t("p5.tsal_aux.grafica_titulo"),
        height=380,
        hovermode="x unified",
    )
    return fig


def _lecturas_tsal_aux(aux_tr: "ResultadosAuxiliarTransitorio", set_point_K: float | None) -> None:
    """Lecturas automáticas de la gráfica T_sal_aux(t).

    Sin set-point: el ΔT es constante mientras el auxiliar opera (calentamiento
    sensible). Con set-point: cuántas horas colector+aux alcanza el corte, cuántas
    queda corto por potencia, y si el colector solo ya lo supera.
    """
    horas_activo = aux_tr.horas_activo_s / 3600.0
    if horas_activo <= 0.0:
        st.info(t("p5.tsal_aux.lectura_inactivo"))
        return
    if set_point_K is None:
        st.info(t("p5.tsal_aux.lectura_sin_sp", dt=aux_tr.delta_T_max_K, horas=horas_activo))
        return

    tol = 0.1
    activo = aux_tr.Q_efectivo_W > 0.0

    def _horas(mask: np.ndarray) -> float:
        return float(np.trapezoid(mask.astype(float), aux_tr.t_s)) / 3600.0

    h_alcanza = _horas(activo & (aux_tr.T_salida_K >= set_point_K - tol))
    h_corto = _horas(activo & (aux_tr.T_salida_K < set_point_K - tol))
    h_col = _horas(aux_tr.T_entrada_K >= set_point_K - tol)
    sp_C = set_point_K - 273.15

    if h_alcanza > 0.0:
        st.success(t("p5.tsal_aux.lectura_alcanza", sp=sp_C, horas=h_alcanza))
    if h_corto > 0.0:
        st.warning(t("p5.tsal_aux.lectura_corto", horas=h_corto))
    if h_alcanza <= 0.0:
        st.warning(t("p5.tsal_aux.lectura_nunca", sp=sp_C))
    if h_col > 0.0:
        st.caption(t("p5.tsal_aux.lectura_colector_solo", horas=h_col))


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 5 — Calentamiento Auxiliar."""
    st.header(t("p5.header"))
    boton_manual(SLUG_POR_SECCION["p5"])

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander(t("p5.cargar.titulo"), expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            t("p5.cargar.uploader"),
            type=["json"],
            key="p5_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "auxiliar")
            if err:
                st.error(f"❌ {err}")  # i18n: exento (mensaje de serializacion, F4)
            else:
                try:
                    aux_cargado = _from_json_auxiliar(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(t("p5.cargar.error_reconstruccion", exc=exc))
                else:
                    proyecto.auxiliar = aux_cargado
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p5_")
                    # También aux_*: claves auxiliares usadas por widgets
                    limpiar_session_state_prefijo(st.session_state, "aux_")
                    st.session_state.pop("p5_cargar_json", None)
                    st.success(t("p5.cargar.exito", n=n_borr))
                    st.rerun()

    # -----------------------------------------------------------------------
    # Toggle principal: ¿usar auxiliar?
    # -----------------------------------------------------------------------
    usar_auxiliar = st.toggle(
        t("p5.usar.label"),
        value=proyecto.auxiliar is not None,
        help=t("p5.usar.help"),
    )

    if not usar_auxiliar:
        proyecto.auxiliar = None
        st.info(t("p5.usar.sin_auxiliar"))
        return

    aux_prev = proyecto.auxiliar

    # -----------------------------------------------------------------------
    # Sección A: Tipo y modo de operación
    # -----------------------------------------------------------------------
    st.subheader(t("p5.tipo_modo.titulo"))
    col1, col2 = st.columns(2)

    with col1:
        tipo_opts = [TipoAuxiliar.RESISTENCIA_ELECTRICA, TipoAuxiliar.QUEMADOR_BIOMASA]
        tipo_idx = tipo_opts.index(aux_prev.tipo) if aux_prev is not None else 0
        tipo = st.selectbox(
            t("p5.tipo_modo.tipo.label"),
            options=tipo_opts,
            index=tipo_idx,
            format_func=lambda e: t(f"p5.tipo_modo.tipo.{e.value.lower()}"),
            help=t("p5.tipo_modo.tipo.help"),
        )

    with col2:
        modo_opts = [
            ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
        ]
        modo_idx = modo_opts.index(aux_prev.modo_operacion) if aux_prev is not None else 0
        modo = st.selectbox(
            t("p5.tipo_modo.modo.label"),
            options=modo_opts,
            index=modo_idx,
            format_func=lambda e: t(f"p5.tipo_modo.modo.{e.value.lower()}"),
            help=t("p5.tipo_modo.modo.help"),
        )

    # -----------------------------------------------------------------------
    # Sección B: Parámetros comunes
    # -----------------------------------------------------------------------
    with st.expander(t("p5.operacion.titulo"), expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            potencia_kW = st.number_input(
                t("p5.operacion.potencia.label"),
                min_value=0.05,
                max_value=100.0,
                value=(aux_prev.potencia_nominal_W / 1000.0 if aux_prev is not None else 1.0),
                step=0.05,
                format="%.2f",
                help=t("p5.operacion.potencia.help"),
            )
            potencia_W = potencia_kW * 1000.0

            fraccion = st.slider(
                t("p5.operacion.fraccion.label"),
                min_value=10,
                max_value=100,
                value=int(
                    (aux_prev.fraccion_potencia_operacion if aux_prev is not None else 1.0) * 100
                ),
                step=5,
                help=t("p5.operacion.fraccion.help"),
            )
            fraccion_f = fraccion / 100.0

        with c2:
            T_max_C = st.number_input(
                t("p5.operacion.t_max.label"),
                min_value=30.0,
                max_value=200.0,
                value=kelvin_a_celsius(
                    aux_prev.temperatura_maxima_salida_K
                    if aux_prev is not None
                    else celsius_a_kelvin(_T_MAX_DEFAULT_C)
                ),
                step=1.0,
                format="%.0f",
                help=t("p5.operacion.t_max.help"),
            )
            T_max_K = celsius_a_kelvin(T_max_C)

            usar_set_point = st.checkbox(
                t("p5.operacion.set_point.check"),
                value=aux_prev is not None and aux_prev.set_point_T_K is not None,
                help=t("p5.operacion.set_point.check_help"),
            )
            set_point_K: float | None = None
            if usar_set_point:
                sp_C = st.number_input(
                    t("p5.operacion.set_point.label"),
                    min_value=30.0,
                    max_value=T_max_C,
                    value=min(
                        (
                            kelvin_a_celsius(aux_prev.set_point_T_K)
                            if (aux_prev is not None and aux_prev.set_point_T_K is not None)
                            else _T_MAX_DEFAULT_C - 5.0
                        ),
                        T_max_C,
                    ),
                    step=1.0,
                    format="%.0f",
                )
                set_point_K = celsius_a_kelvin(sp_C)

        disponible_nocturno = st.checkbox(
            t("p5.operacion.nocturno.label"),
            value=aux_prev.disponible_nocturno if aux_prev is not None else False,
            help=t("p5.operacion.nocturno.help"),
        )

    # -----------------------------------------------------------------------
    # Sección C: Parámetros específicos por tipo
    # -----------------------------------------------------------------------
    tipo_biomasa_val: str | None = None
    PCI_val: float | None = None
    eta_quemador_val: float | None = None
    tension_val: float | None = None

    if tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
        with st.expander(t("p5.biomasa.titulo"), expanded=False):
            # (id_estable, PCI_MJ_kg, η). El id "otro" es sentinel de entrada manual.
            _COMBUSTIBLES = [
                ("lena", 14.5, 0.65),
                ("pellets", 17.5, 0.70),
                ("girasol", 16.0, 0.65),
                ("bagazo", 17.0, 0.65),
                ("otro", None, None),
            ]
            _ids_comb = [c[0] for c in _COMBUSTIBLES]

            def _label_comb(cid: str) -> str:
                return t("p5.biomasa.otro") if cid == "otro" else t(f"p5.biomasa.opcion.{cid}")

            # El nombre previo puede ser un label traducido guardado; se busca por
            # coincidencia con cualquier idioma o cae a "lena".
            _prev_nombre = aux_prev.tipo_biomasa if aux_prev is not None else None
            _idx_comb = 0
            if _prev_nombre:
                for i, cid in enumerate(_ids_comb):
                    if cid != "otro" and _label_comb(cid) == _prev_nombre:
                        _idx_comb = i
                        break
            combustible_sel = st.selectbox(
                t("p5.biomasa.combustible"),
                options=_ids_comb,
                index=_idx_comb,
                format_func=_label_comb,
            )
            _map_comb = {c[0]: (c[1], c[2]) for c in _COMBUSTIBLES}
            PCI_default, eta_default = _map_comb[combustible_sel]

            c1, c2 = st.columns(2)
            with c1:
                PCI_val = st.number_input(
                    t("p5.biomasa.pci.label"),
                    min_value=5.0,
                    max_value=40.0,
                    value=float(
                        aux_prev.PCI_MJ_kg
                        if (aux_prev is not None and aux_prev.PCI_MJ_kg is not None)
                        else (PCI_default or 14.5)
                    ),
                    step=0.5,
                    format="%.1f",
                    help=t("p5.biomasa.pci.help"),
                )
                tipo_biomasa_val = (
                    _label_comb(combustible_sel)
                    if combustible_sel != "otro"
                    else st.text_input(t("p5.biomasa.nombre_combustible"), value="")
                )
            with c2:
                eta_quemador_val = (
                    st.slider(
                        t("p5.biomasa.eficiencia"),
                        min_value=30,
                        max_value=95,
                        value=int(
                            (
                                aux_prev.eficiencia_quemador
                                if (
                                    aux_prev is not None
                                    and aux_prev.eficiencia_quemador is not None
                                )
                                else (eta_default or 0.65)
                            )
                            * 100
                        ),
                        step=5,
                    )
                    / 100.0
                )

            # Consumo estimado (solo informativo)
            if PCI_val and eta_quemador_val:
                consumo_est = potencia_W * fraccion_f * 3600.0 / (PCI_val * 1e6 * eta_quemador_val)
                st.caption(
                    t(
                        "p5.biomasa.consumo_estimado",
                        potencia=potencia_W * fraccion_f / 1000,
                        consumo=consumo_est,
                        combustible=_label_comb(combustible_sel).lower(),
                    )
                )

    elif tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        with st.expander(t("p5.resistencia.titulo"), expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                tension_prev = aux_prev.tension_V if aux_prev is not None else 220.0
                usar_tension = st.checkbox(
                    t("p5.resistencia.especificar_tension"),
                    value=tension_prev is not None,
                )
                if usar_tension:
                    tension_val = st.selectbox(
                        t("p5.resistencia.tension.label"),
                        options=[220, 380],
                        index=0 if (tension_prev is None or tension_prev == 220) else 1,
                        help=t("p5.resistencia.tension.help"),
                    )
                    tension_val = float(tension_val)
            with c2:
                if tension_val is not None:
                    corriente_est = potencia_W * fraccion_f / (tension_val * 0.85)
                    st.metric(
                        t("p5.resistencia.corriente.label"),
                        f"{corriente_est:.1f} A",
                        help=t("p5.resistencia.corriente.help"),
                    )

    # -----------------------------------------------------------------------
    # Calendario de arranque (híbrido mañana/tarde) — opcional
    # -----------------------------------------------------------------------
    cargas_list: list[CargaArranque] = []
    with st.expander(t("p5.calendario.titulo"), expanded=False):
        st.caption(t("p5.calendario.intro"))
        cargas_prev = aux_prev.cargas_arranque if aux_prev is not None else []
        usar_cal = st.checkbox(
            t("p5.calendario.usar.label"),
            value=bool(cargas_prev),
            help=t("p5.calendario.usar.help"),
        )
        if usar_cal:
            n_def = len(cargas_prev) if cargas_prev else 2
            n_cargas = st.number_input(
                t("p5.calendario.n_cargas"),
                min_value=1,
                max_value=6,
                value=int(n_def),
                step=1,
            )
            _def = [(6.0, 3.0), (18.0, 3.0)]  # mañana / atardecer
            for i in range(int(n_cargas)):
                h_prev = cargas_prev[i].hora_inicio_h if i < len(cargas_prev) else _def[i % 2][0]
                d_prev = cargas_prev[i].duracion_h if i < len(cargas_prev) else _def[i % 2][1]
                cc1, cc2 = st.columns(2)
                hi = cc1.number_input(
                    t("p5.calendario.carga_inicio", i=i + 1),
                    min_value=0.0,
                    max_value=23.5,
                    value=float(h_prev),
                    step=0.5,
                    format="%.1f",
                    key=f"p5_carga_hi_{i}",
                )
                du = cc2.number_input(
                    t("p5.calendario.carga_duracion", i=i + 1),
                    min_value=0.5,
                    max_value=24.0,
                    value=float(d_prev),
                    step=0.5,
                    format="%.1f",
                    key=f"p5_carga_du_{i}",
                )
                cargas_list.append(CargaArranque(hora_inicio_h=float(hi), duracion_h=float(du)))
            horas_cubiertas = sum(c.duracion_h for c in cargas_list)
            st.caption(t("p5.calendario.cobertura", horas=horas_cubiertas, n=len(cargas_list)))

    # -----------------------------------------------------------------------
    # Botón: aplicar configuración del auxiliar
    # -----------------------------------------------------------------------
    st.divider()
    calcular = st.button(t("p5.aplicar"), type="primary")

    if calcular:
        try:
            auxiliar = Auxiliar(
                tipo=tipo,
                modo_operacion=modo,
                potencia_nominal_W=potencia_W,
                temperatura_maxima_salida_K=T_max_K,
                set_point_T_K=set_point_K,
                fraccion_potencia_operacion=fraccion_f,
                disponible_nocturno=disponible_nocturno,
                tipo_biomasa=tipo_biomasa_val,
                PCI_MJ_kg=PCI_val,
                eficiencia_quemador=eta_quemador_val,
                tension_V=tension_val,
                cargas_arranque=cargas_list,
            )
            proyecto.auxiliar = auxiliar
        except (ValueError, NotImplementedError) as exc:
            st.error(t("p5.error_config", exc=exc))
            return

        # Advertencias estáticas
        adv_list = advertencias_auxiliar(auxiliar)
        if adv_list:
            st.subheader(t("p5.advertencias_titulo"))
            _mostrar_advertencias(adv_list)
        else:
            st.success(t("p5.sin_advertencias"))

        # -----------------------------------------------------------------------
        # Sección D: Entregable transitorio — T_sal_aux(t)
        # -----------------------------------------------------------------------
        st.subheader(t("p5.tsal_aux.titulo"))
        st.caption(t("p5.tsal_aux.caption"))

        # T_entrada_aux(t) = T_salida_colector(t) (o T_amb en CAJA) sale del
        # forzante del horizonte que arma P4/P7. El auxiliar se evalúa hora a
        # hora con el MISMO solver transitorio que usa P7 (calcular_auxiliar_
        # transitorio): esta gráfica NO recomputa física, la reproduce.
        fz_h, _meta_h, vigente_h = horizonte_vigente(proyecto, st.session_state)
        if fz_h is None:
            st.info(t("p5.tsal_aux.sin_horizonte"))
        else:
            _m_dot = getattr(fz_h, "m_dot_aire_seco_kg_s", None)
            if _m_dot is not None and len(np.asarray(_m_dot)) > 0:
                caudal_aux = float(np.mean(_m_dot))
            elif proyecto.camara is not None:
                caudal_aux = proyecto.camara.flujo.caudal_masico_kg_s
            else:
                caudal_aux = 0.030
            try:
                aux_tr = calcular_auxiliar_transitorio(
                    auxiliar,
                    T_entrada_K_serie=fz_h.T_ent_K,
                    t_s=fz_h.t_s,
                    caudal_masico_kg_s=caudal_aux,
                    I_g_W_m2_serie=getattr(fz_h, "I_g_W_m2", None),
                )
            except Exception as exc:  # noqa: BLE001
                st.error(t("p5.tsal_aux.error", exc=exc))
                aux_tr = None

            if aux_tr is not None:
                if not vigente_h:
                    st.caption(t("p5.tsal_aux.horizonte_stale"))
                if proyecto.chimenea is not None and proyecto.motor is None:
                    st.caption(t("p5.tsal_aux.caudal_chimenea"))
                mostrar_plotly(
                    _grafica_tsal_aux(aux_tr, set_point_K), nombre="aux_tsal_transitorio"
                )
                _lecturas_tsal_aux(aux_tr, set_point_K)
                for msg in aux_tr.advertencias_unicas:
                    st.warning(f"⚠️ {msg}")  # i18n: exento (mensaje de calculos/, queda ES)

        # Resumen compacto
        with st.expander(t("p5.resumen.titulo")):
            _si = t("p5.si")
            _no = t("p5.no")
            c1, c2 = st.columns(2)
            with c1:
                st.write(t("p5.resumen.tipo", v=t(f"p5.tipo_modo.tipo.{tipo.value.lower()}")))
                st.write(t("p5.resumen.modo", v=t(f"p5.tipo_modo.modo.{modo.value.lower()}")))
                st.write(t("p5.resumen.potencia", v=potencia_kW))
                st.write(t("p5.resumen.fraccion", v=fraccion))
                st.write(t("p5.resumen.t_max", v=T_max_C))
                st.write(
                    t(
                        "p5.resumen.set_point",
                        v=t("p5.resumen.set_point_valor", v=kelvin_a_celsius(set_point_K)),
                    )
                    if set_point_K
                    else t("p5.resumen.set_point", v=t("p5.resumen.set_point_no"))
                )
            with c2:
                st.write(t("p5.resumen.nocturno", v=_si if disponible_nocturno else _no))
                if tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
                    st.write(t("p5.resumen.combustible", v=tipo_biomasa_val or "—"))
                    st.write(t("p5.resumen.pci", v=PCI_val) if PCI_val else t("p5.resumen.pci_no"))
                    st.write(
                        t("p5.resumen.eta", v=eta_quemador_val)
                        if eta_quemador_val
                        else t("p5.resumen.eta_no")
                    )
                elif tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
                    st.write(
                        t("p5.resumen.tension", v=tension_val)
                        if tension_val
                        else t("p5.resumen.tension_no")
                    )

    # --- Guardar configuración ---
    if proyecto.auxiliar is not None:
        st.divider()
        from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

        col_txt, col_json = st.columns(2)
        with col_txt:
            st.download_button(
                t("p5.guardar.txt"),
                data=_texto_config_auxiliar(proyecto.auxiliar),
                file_name=nombre_archivo_descarga(proyecto, "auxiliar", "txt"),
                mime="text/plain",
                width="stretch",
            )
        with col_json:
            st.download_button(
                t("p5.guardar.json"),
                data=dump_json(_json_config_auxiliar(proyecto.auxiliar)),
                file_name=nombre_archivo_descarga(proyecto, "auxiliar", "json"),
                mime="application/json",
                width="stretch",
            )
