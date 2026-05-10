"""
Pestaña 5 — Calentamiento Auxiliar.

Permite configurar un sistema de calentamiento auxiliar (resistencia eléctrica
o quemador de biomasa) y calcula el salto térmico que produce sobre el flujo de
aire que viene del colector (o del ambiente en modo respaldo independiente).

El auxiliar es opcional: si el usuario no lo activa, proyecto.auxiliar = None.
"""

from __future__ import annotations

import streamlit as st

from calculos.auxiliar_calc import calcular_auxiliar
from core.advertencias import Severidad
from core.auxiliar import (
    Auxiliar,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
    advertencias_auxiliar,
)
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_T_SALIDA_DEFAULT_C: float = 60.0
_T_AMB_DEFAULT_C: float = 25.0
_T_MAX_DEFAULT_C: float = 70.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mostrar_advertencias(adv_list: list) -> None:
    for adv in adv_list:
        icono = _ICONOS_SEVERIDAD.get(adv.severidad, "•")
        msg = f"{icono} **{adv.codigo}** — {adv.mensaje}"
        if adv.severidad == Severidad.CRITICAL:
            st.error(msg)
        elif adv.severidad == Severidad.WARNING:
            st.warning(msg)
        else:
            st.info(msg)


def _T_entrada_sugerida() -> float:
    """Devuelve la mejor estimación de T_entrada para el auxiliar [K].

    En modo SERIE_POSCOLECTOR: idealmente T_salida del colector.
    Como los resultados del colector no están en session_state todavía,
    el usuario la ingresa manualmente. Esta función provee el default.
    """
    return celsius_a_kelvin(_T_SALIDA_DEFAULT_C)


# ---------------------------------------------------------------------------
# Generador de texto de configuración
# ---------------------------------------------------------------------------

def _texto_config_auxiliar(aux: "Auxiliar") -> str:
    from datetime import date
    lines = [
        "=== CONFIGURACIÓN DEL AUXILIAR TÉRMICO ===",
        f"Fecha: {date.today()}",
        "",
        f"Tipo            : {aux.tipo.value}",
        f"Modo operación  : {aux.modo_operacion.value}",
        f"Potencia nominal: {aux.potencia_nominal_W / 1000:.2f} kW",
        f"Fracción oper.  : {aux.fraccion_potencia_operacion:.0%}",
        f"T_max salida    : {aux.temperatura_maxima_salida_K - 273.15:.0f} °C",
        f"Disponible noc. : {'Sí' if aux.disponible_nocturno else 'No'}",
    ]
    if aux.tipo.value == "QUEMADOR_BIOMASA":
        lines += [
            f"Combustible     : {aux.tipo_biomasa or '—'}",
            f"PCI             : {f'{aux.PCI_MJ_kg:.1f} MJ/kg' if aux.PCI_MJ_kg else '—'}",
            f"η quemador      : {f'{aux.eficiencia_quemador:.0%}' if aux.eficiencia_quemador else '—'}",
        ]
    if aux.notas:
        lines += ["", f"Notas: {aux.notas}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 5 — Calentamiento Auxiliar."""
    st.header("5 · Calentamiento Auxiliar")

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Toggle principal: ¿usar auxiliar?
    # -----------------------------------------------------------------------
    usar_auxiliar = st.toggle(
        "Incorporar sistema de calentamiento auxiliar",
        value=proyecto.auxiliar is not None,
        help=(
            "Activa un sistema de calentamiento auxiliar (resistencia eléctrica o quemador "
            "de biomasa) para extender el horario de secado o reforzar en días nublados."
        ),
    )

    if not usar_auxiliar:
        proyecto.auxiliar = None
        st.info(
            "Sin calentamiento auxiliar. El secador opera únicamente con energía solar. "
            "Activar el toggle para configurar un auxiliar."
        )
        return

    aux_prev = proyecto.auxiliar

    # -----------------------------------------------------------------------
    # Sección A: Tipo y modo de operación
    # -----------------------------------------------------------------------
    st.subheader("Tipo y modo de operación")
    col1, col2 = st.columns(2)

    with col1:
        tipo_opciones = {
            "Resistencia eléctrica": TipoAuxiliar.RESISTENCIA_ELECTRICA,
            "Quemador de biomasa": TipoAuxiliar.QUEMADOR_BIOMASA,
        }
        tipo_prev_label = next(
            (k for k, v in tipo_opciones.items()
             if aux_prev is not None and v == aux_prev.tipo),
            "Resistencia eléctrica",
        )
        tipo_label = st.selectbox(
            "Tipo de fuente de calor auxiliar",
            options=list(tipo_opciones.keys()),
            index=list(tipo_opciones.keys()).index(tipo_prev_label),
            help=(
                "Resistencia eléctrica: η ≈ 1, control preciso, requiere red eléctrica.\n"
                "Quemador de biomasa: η ≈ 0.60–0.75, combustible local, control más simple."
            ),
        )
        tipo = tipo_opciones[tipo_label]

    with col2:
        modo_opciones = {
            "Serie post-colector": ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            "Respaldo independiente": ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
        }
        modo_prev_label = next(
            (k for k, v in modo_opciones.items()
             if aux_prev is not None and v == aux_prev.modo_operacion),
            "Serie post-colector",
        )
        modo_label = st.selectbox(
            "Modo de operación",
            options=list(modo_opciones.keys()),
            index=list(modo_opciones.keys()).index(modo_prev_label),
            help=(
                "**Serie post-colector:** el auxiliar calienta el aire luego del colector. "
                "Úselo como refuerzo en días nublados o para alcanzar temperaturas más altas.\n\n"
                "**Respaldo independiente:** el auxiliar tiene su propio circuito de aire. "
                "Úselo para secado nocturno o días sin sol."
            ),
        )
        modo = modo_opciones[modo_label]

    # -----------------------------------------------------------------------
    # Sección B: Parámetros comunes
    # -----------------------------------------------------------------------
    with st.expander("Parámetros de operación", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            potencia_kW = st.number_input(
                "Potencia nominal [kW]",
                min_value=0.05, max_value=100.0,
                value=(aux_prev.potencia_nominal_W / 1000.0
                       if aux_prev is not None else 1.0),
                step=0.05, format="%.2f",
                help=(
                    "Potencia térmica nominal entregada al aire. "
                    "Para resistencia eléctrica: potencia eléctrica = potencia térmica."
                ),
            )
            potencia_W = potencia_kW * 1000.0

            fraccion = st.slider(
                "Fracción de potencia en operación [%]",
                min_value=10, max_value=100,
                value=int((aux_prev.fraccion_potencia_operacion
                           if aux_prev is not None else 1.0) * 100),
                step=5,
                help="Permite modelar operación parcial del auxiliar.",
            )
            fraccion_f = fraccion / 100.0

        with c2:
            T_max_C = st.number_input(
                "T máxima de salida [°C]",
                min_value=30.0, max_value=200.0,
                value=kelvin_a_celsius(
                    aux_prev.temperatura_maxima_salida_K
                    if aux_prev is not None else celsius_a_kelvin(_T_MAX_DEFAULT_C)
                ),
                step=1.0, format="%.0f",
                help=(
                    "Límite de seguridad para proteger el producto. "
                    "Para frutas y hortalizas: ≤ 60–70 °C."
                ),
            )
            T_max_K = celsius_a_kelvin(T_max_C)

            usar_set_point = st.checkbox(
                "Control por set point de temperatura",
                value=aux_prev is not None and aux_prev.set_point_T_K is not None,
                help=(
                    "Si está activo, el auxiliar regula su potencia para mantener "
                    "la temperatura de salida en el valor objetivo."
                ),
            )
            set_point_K: float | None = None
            if usar_set_point:
                sp_C = st.number_input(
                    "Set point [°C]",
                    min_value=30.0, max_value=T_max_C,
                    value=min(
                        kelvin_a_celsius(aux_prev.set_point_T_K)
                        if (aux_prev is not None and aux_prev.set_point_T_K is not None)
                        else _T_MAX_DEFAULT_C - 5.0,
                        T_max_C,
                    ),
                    step=1.0, format="%.0f",
                )
                set_point_K = celsius_a_kelvin(sp_C)

        disponible_nocturno = st.checkbox(
            "Disponible para operación nocturna",
            value=aux_prev.disponible_nocturno if aux_prev is not None else False,
            help=(
                "Resistencia eléctrica: disponible si hay red eléctrica. "
                "Quemador de biomasa: generalmente disponible."
            ),
        )

    # -----------------------------------------------------------------------
    # Sección C: Parámetros específicos por tipo
    # -----------------------------------------------------------------------
    tipo_biomasa_val: str | None = None
    PCI_val: float | None = None
    eta_quemador_val: float | None = None
    consumo_override_val: float | None = None
    tension_val: float | None = None
    corriente_val: float | None = None

    if tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
        with st.expander("Parámetros del quemador de biomasa", expanded=True):
            _COMBUSTIBLES = {
                "Leña seca (~20% HR)": (14.5, 0.65),
                "Pellets de madera": (17.5, 0.70),
                "Cáscara de girasol": (16.0, 0.65),
                "Bagazo de caña (seco)": (17.0, 0.65),
                "Otro (ingresar manualmente)": (None, None),
            }
            combustible_prev = (aux_prev.tipo_biomasa
                                if aux_prev is not None and aux_prev.tipo_biomasa else
                                "Leña seca (~20% HR)")
            combustible_sel = st.selectbox(
                "Combustible",
                options=list(_COMBUSTIBLES.keys()),
                index=0 if combustible_prev not in _COMBUSTIBLES else
                      list(_COMBUSTIBLES.keys()).index(combustible_prev),
            )
            PCI_default, eta_default = _COMBUSTIBLES[combustible_sel]

            c1, c2 = st.columns(2)
            with c1:
                PCI_val = st.number_input(
                    "PCI [MJ/kg]",
                    min_value=5.0, max_value=40.0,
                    value=float(
                        aux_prev.PCI_MJ_kg
                        if (aux_prev is not None and aux_prev.PCI_MJ_kg is not None)
                        else (PCI_default or 14.5)
                    ),
                    step=0.5, format="%.1f",
                    help="Poder calorífico inferior del combustible.",
                )
                tipo_biomasa_val = (combustible_sel
                                    if combustible_sel != "Otro (ingresar manualmente)"
                                    else st.text_input("Nombre del combustible", value=""))
            with c2:
                eta_quemador_val = st.slider(
                    "Eficiencia del quemador [%]",
                    min_value=30, max_value=95,
                    value=int((
                        aux_prev.eficiencia_quemador
                        if (aux_prev is not None and aux_prev.eficiencia_quemador is not None)
                        else (eta_default or 0.65)
                    ) * 100),
                    step=5,
                ) / 100.0

            # Consumo estimado (solo informativo)
            if PCI_val and eta_quemador_val:
                consumo_est = (potencia_W * fraccion_f * 3600.0
                               / (PCI_val * 1e6 * eta_quemador_val))
                st.caption(
                    f"💡 Consumo estimado a potencia efectiva "
                    f"({potencia_W * fraccion_f / 1000:.2f} kW): "
                    f"**{consumo_est:.2f} kg/h** de {combustible_sel.lower()}"
                )

    elif tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        with st.expander("Parámetros de la resistencia eléctrica", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                tension_opciones = [None, 220.0, 380.0]
                tension_prev = (aux_prev.tension_V
                                if aux_prev is not None else 220.0)
                usar_tension = st.checkbox(
                    "Especificar tensión de alimentación",
                    value=tension_prev is not None,
                )
                if usar_tension:
                    tension_val = st.selectbox(
                        "Tensión [V]",
                        options=[220, 380],
                        index=0 if (tension_prev is None or tension_prev == 220) else 1,
                        help="220 V monofásico o 380 V trifásico.",
                    )
                    tension_val = float(tension_val)
            with c2:
                if tension_val is not None:
                    corriente_est = potencia_W * fraccion_f / (tension_val * 0.85)
                    st.metric(
                        "Corriente estimada",
                        f"{corriente_est:.1f} A",
                        help="I = P / (V × cos_phi), cos_phi = 0.85.",
                    )

    # -----------------------------------------------------------------------
    # Botón: aplicar configuración del auxiliar
    # -----------------------------------------------------------------------
    st.divider()
    calcular = st.button("⚙️ Aplicar auxiliar", type="primary")

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
            )
            proyecto.auxiliar = auxiliar
        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Error de configuración: {exc}")
            return

        # Advertencias estáticas
        adv_list = advertencias_auxiliar(auxiliar)
        if adv_list:
            st.subheader("Advertencias de diseño")
            _mostrar_advertencias(adv_list)
        else:
            st.success("✅ Auxiliar configurado sin advertencias.")

        # -----------------------------------------------------------------------
        # Sección D: Condiciones de operación y resultados
        # -----------------------------------------------------------------------
        st.subheader("Estimación del efecto térmico")

        col_op1, col_op2 = st.columns(2)
        with col_op1:
            T_entrada_hint = (
                "T_salida del colector (modo serie)."
                if modo == ModoOperacionAuxiliar.SERIE_POSCOLECTOR
                else "T_ambiente (modo respaldo independiente)."
            )
            T_entrada_C = st.number_input(
                "Temperatura de entrada al auxiliar [°C]",
                min_value=-10.0, max_value=120.0,
                value=st.session_state.get("aux_T_entrada_C", _T_SALIDA_DEFAULT_C),
                step=1.0, format="%.1f",
                help=T_entrada_hint,
            )
            st.session_state["aux_T_entrada_C"] = T_entrada_C

        with col_op2:
            # Caudal: tomar del colector si existe, sino pedir al usuario
            caudal_default = 0.030
            caudal_hint = ""
            if proyecto.colector is not None:
                Q_m3s = proyecto.colector.caudal_total_m3_s()
                caudal_default = Q_m3s * 1.1  # ρ ≈ 1.1 kg/m³
                caudal_hint = (
                    f"Tomado del colector: {Q_m3s * 1000:.1f} L/s → "
                    f"~{caudal_default:.3f} kg/s"
                )
            if proyecto.camara is not None:
                caudal_default = proyecto.camara.flujo.caudal_masico_kg_s
                caudal_hint = "Tomado de la cámara de secado."

            caudal_kg_s = st.number_input(
                "Caudal másico [kg/s]",
                min_value=0.001, max_value=10.0,
                value=caudal_default,
                step=0.001, format="%.4f",
                help=caudal_hint or "Caudal de aire seco que pasa por el auxiliar.",
            )
            if caudal_hint:
                st.caption(f"💡 {caudal_hint}")

        T_entrada_K = celsius_a_kelvin(T_entrada_C)
        try:
            res = calcular_auxiliar(auxiliar, T_entrada_K, caudal_kg_s)
        except Exception as exc:
            st.error(f"❌ Error en el cálculo: {exc}")
            return

        if res.advertencias:
            for msg in res.advertencias:
                st.warning(f"⚠️ {msg}")

        # Métricas de resultado
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric(
            "T entrada",
            f"{kelvin_a_celsius(res.T_entrada_K):.1f} °C",
        )
        col_r2.metric(
            "T salida",
            f"{kelvin_a_celsius(res.T_salida_K):.1f} °C",
            delta=f"+{res.delta_T_K:.1f} °C",
        )
        col_r3.metric(
            "Potencia efectiva",
            f"{res.Q_efectivo_W / 1000:.2f} kW",
            help=f"Fracción activa: {res.fraccion_activa:.0%}",
        )
        if res.consumo_biomasa_kg_h is not None:
            col_r4.metric(
                "Consumo biomasa",
                f"{res.consumo_biomasa_kg_h:.3f} kg/h",
                help="A la potencia efectiva de operación.",
            )
        elif res.consumo_electrico_W is not None:
            col_r4.metric(
                "Consumo eléctrico",
                f"{res.consumo_electrico_W / 1000:.2f} kW",
            )

        if res.set_point_activo:
            st.info(
                f"ℹ️ Control de set point activo: el auxiliar opera al "
                f"{res.fraccion_activa:.0%} de su potencia nominal para mantener "
                f"{kelvin_a_celsius(res.T_salida_K):.1f} °C a la salida."
            )

        # Resumen compacto
        with st.expander("Resumen de la configuración"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Tipo:** {tipo_label}")
                st.write(f"**Modo:** {modo_label}")
                st.write(f"**Potencia nominal:** {potencia_kW:.2f} kW")
                st.write(f"**Fracción operación:** {fraccion} %")
                st.write(f"**T_max salida:** {T_max_C:.0f} °C")
                st.write(f"**Set point:** "
                         + (f"{kelvin_a_celsius(set_point_K):.0f} °C"
                            if set_point_K else "No definido"))
            with c2:
                st.write(f"**Disponible nocturno:** {'Sí' if disponible_nocturno else 'No'}")
                if tipo == TipoAuxiliar.QUEMADOR_BIOMASA:
                    st.write(f"**Combustible:** {tipo_biomasa_val or '—'}")
                    st.write(f"**PCI:** {PCI_val:.1f} MJ/kg" if PCI_val else "**PCI:** —")
                    st.write(f"**η quemador:** {eta_quemador_val:.0%}"
                             if eta_quemador_val else "**η quemador:** —")
                elif tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
                    st.write(f"**Tensión:** {tension_val:.0f} V"
                             if tension_val else "**Tensión:** No especificada")

    # --- Guardar configuración ---
    if proyecto.auxiliar is not None:
        st.divider()
        st.download_button(
            "Guardar configuración del auxiliar (.txt)",
            data=_texto_config_auxiliar(proyecto.auxiliar),
            file_name="config_auxiliar.txt",
            mime="text/plain",
            use_container_width=True,
        )
