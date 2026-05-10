"""
Pestaña 6 — Motor / Ventilador.

Dimensiona el sistema de convección forzada calculando la pérdida de carga
total del sistema (colector + cámara + ductos) y la potencia eléctrica del
motor necesaria para vencerla.

Soporta:
    - Motor eléctrico con ventilador axial o centrífugo.
    - Extractor eólico tipo turbina.

La convección natural no requiere motor (proyecto.motor = None).
"""

from __future__ import annotations

import streamlit as st

from calculos.motor_calc import (
    caudal_masico_a_volumetrico,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
)
from core.advertencias import Severidad
from core.motor import Motor, TipoAccionamiento

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_T_MEDIA_DEFAULT_K: float = 323.15    # 50 °C — temperatura media del sistema
_P_ATM_DEFAULT_PA: float = 101325.0


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


# ---------------------------------------------------------------------------
# Generador de texto de configuración
# ---------------------------------------------------------------------------

def _texto_config_motor(motor: "Motor") -> str:
    from datetime import date
    lines = [
        "=== CONFIGURACIÓN DEL MOTOR / VENTILADOR ===",
        f"Fecha: {date.today()}",
        "",
        f"Tipo accionamiento : {motor.tipo_accionamiento.value}",
        f"ΔP total           : {motor.perdida_carga_total_Pa:.1f} Pa",
        f"η ventilador       : {motor.eficiencia_ventilador:.0%}",
        f"η motor            : {motor.eficiencia_motor:.0%}",
        f"Factor servicio    : {motor.factor_servicio:.2f}",
    ]
    if motor.potencia_hidraulica_W:
        lines.append(f"P hidráulica       : {motor.potencia_hidraulica_W:.1f} W")
    if motor.potencia_eje_W:
        lines.append(f"P eje              : {motor.potencia_eje_W:.1f} W")
    if motor.potencia_electrica_W:
        lines.append(f"P eléctrica        : {motor.potencia_electrica_W:.1f} W")
    if motor.potencia_a_instalar_W:
        lines.append(f"P a instalar       : {motor.potencia_a_instalar_W:.1f} W")
    if motor.corriente_nominal_A:
        lines.append(f"Corriente nominal  : {motor.corriente_nominal_A:.2f} A")
    if motor.diametro_extractor_m:
        lines.append(f"Diámetro extractor : {motor.diametro_extractor_m:.2f} m")
    if motor.notas:
        lines += ["", f"Notas: {motor.notas}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 6 — Motor / Ventilador."""
    st.header("6 · Motor / Ventilador")

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Toggle: ¿usar motor?
    # -----------------------------------------------------------------------
    usar_motor = st.toggle(
        "Incorporar sistema de convección forzada (motor / ventilador)",
        value=proyecto.motor is not None,
        help=(
            "Desactivar para tipologías de convección natural "
            "(secador de tipo caja con chimenea, o armario sin motor)."
        ),
    )

    if not usar_motor:
        proyecto.motor = None
        st.info(
            "Sin motor. El secador opera por convección natural. "
            "Activar el toggle para dimensionar el ventilador."
        )
        return

    mot_prev = proyecto.motor

    # -----------------------------------------------------------------------
    # Sección A: Tipo de accionamiento
    # -----------------------------------------------------------------------
    st.subheader("Tipo de accionamiento")

    tipo_opciones = {
        "Motor eléctrico": TipoAccionamiento.MOTOR_ELECTRICO,
        "Extractor eólico": TipoAccionamiento.EXTRACTOR_EOLICO,
    }
    tipo_prev_label = next(
        (k for k, v in tipo_opciones.items()
         if mot_prev is not None and v == mot_prev.tipo_accionamiento),
        "Motor eléctrico",
    )
    tipo_label = st.selectbox(
        "Tipo de accionamiento",
        options=list(tipo_opciones.keys()),
        index=list(tipo_opciones.keys()).index(tipo_prev_label),
        help=(
            "**Motor eléctrico:** ventilador axial o centrífugo con motor eléctrico.\n\n"
            "**Extractor eólico:** turbina tipo 'sombrero chino' accionada por el viento. "
            "Sin consumo eléctrico pero dependiente de la velocidad del viento del sitio."
        ),
    )
    tipo = tipo_opciones[tipo_label]

    # -----------------------------------------------------------------------
    # Sección B: Caudal volumétrico
    # -----------------------------------------------------------------------
    with st.expander("Caudal de diseño", expanded=True):
        Q_vol_sugerido = mot_prev.caudal_volumetrico_m3_s if mot_prev is not None else 0.020
        hint_caudal = ""

        if proyecto.colector is not None:
            Q_col = proyecto.colector.caudal_total_m3_s()
            Q_vol_sugerido = Q_col
            hint_caudal = f"Colector (P3): {Q_col * 1000:.1f} L/s"

        if proyecto.camara is not None:
            Q_vol_cam = caudal_masico_a_volumetrico(
                proyecto.camara.flujo.caudal_masico_kg_s,
                _T_MEDIA_DEFAULT_K,
                _P_ATM_DEFAULT_PA,
            )
            Q_vol_sugerido = Q_vol_cam
            hint_caudal = (
                f"Cámara (P4): {proyecto.camara.flujo.caudal_masico_kg_s * 1000:.1f} g/s "
                f"→ {Q_vol_cam * 1000:.1f} L/s (a 50 °C)"
            )

        c1, c2 = st.columns(2)
        with c1:
            Q_vol_ls = st.number_input(
                "Caudal volumétrico [L/s]",
                min_value=0.1, max_value=10000.0,
                value=round(Q_vol_sugerido * 1000.0, 1),
                step=0.5, format="%.1f",
                help=hint_caudal or "Caudal que debe mover el ventilador.",
            )
            Q_vol_m3s = Q_vol_ls / 1000.0
        with c2:
            if hint_caudal:
                st.info(f"💡 {hint_caudal}")
            st.metric("Caudal", f"{Q_vol_ls:.1f} L/s",
                      help=f"{Q_vol_m3s:.5f} m³/s")

    # -----------------------------------------------------------------------
    # Sección C: Pérdidas de carga
    # -----------------------------------------------------------------------
    with st.expander("Pérdidas de carga del sistema", expanded=True):

        modo_dP = st.radio(
            "Ingreso de pérdidas de carga",
            options=["Por componentes (auto-estimado)", "ΔP total directo"],
            horizontal=True,
            help=(
                "**Por componentes:** estima ΔP_colector (Darcy-Weisbach) y ΔP_cámara "
                "(resistencia de bandejas) desde P3 y P4, más 20% de margen de ductos.\n\n"
                "**ΔP total directo:** ingresá el valor medido en campo o de catálogo."
            ),
        )

        dP_total_override: float | None = None
        dP_colector_val: float | None = None
        dP_camara_val: float | None = None
        dP_ductos_val: float | None = None

        if modo_dP == "ΔP total directo":
            dP_total_override = st.number_input(
                "ΔP total del sistema [Pa]",
                min_value=1.0, max_value=5000.0,
                value=float(
                    mot_prev.perdida_carga_total_Pa
                    if (mot_prev is not None and mot_prev.perdida_carga_total_Pa)
                    else 50.0
                ),
                step=1.0, format="%.1f",
                help="Incluye colector, cámara y ductos.",
            )

        else:
            c1, c2, c3 = st.columns(3)

            # ΔP colector
            dP_col_auto: float | None = None
            if proyecto.colector is not None:
                try:
                    dP_col_auto = estimar_delta_P_colector(proyecto.colector)
                except Exception:
                    pass

            dP_col_default = float(
                mot_prev.delta_P_colector_Pa
                if (mot_prev is not None and mot_prev.delta_P_colector_Pa is not None)
                else (dP_col_auto or 20.0)
            )
            with c1:
                dP_col_input = st.number_input(
                    "ΔP colector [Pa]",
                    min_value=0.0, max_value=2000.0,
                    value=dP_col_default,
                    step=1.0, format="%.1f",
                    help=(
                        "Pérdida de carga en el banco de colectores (Darcy-Weisbach). "
                        + (f"Auto (P3): {dP_col_auto:.1f} Pa."
                           if dP_col_auto is not None
                           else "Configurar P3 para auto-estimación.")
                    ),
                )
                dP_colector_val = dP_col_input if dP_col_input > 0 else None
                if dP_col_auto is not None:
                    st.caption(f"Auto P3: **{dP_col_auto:.1f} Pa**")

            # ΔP cámara
            dP_cam_auto: float | None = None
            if proyecto.camara is not None:
                try:
                    dP_cam_auto = estimar_delta_P_camara(proyecto.camara)
                except Exception:
                    pass

            dP_cam_default = float(
                mot_prev.delta_P_camara_Pa
                if (mot_prev is not None and mot_prev.delta_P_camara_Pa is not None)
                else (dP_cam_auto or 10.0)
            )
            with c2:
                dP_cam_input = st.number_input(
                    "ΔP cámara [Pa]",
                    min_value=0.0, max_value=2000.0,
                    value=dP_cam_default,
                    step=1.0, format="%.1f",
                    help=(
                        "Pérdida de carga en las bandejas de la cámara. "
                        + (f"Auto (P4): {dP_cam_auto:.1f} Pa (K_malla=2.0)."
                           if dP_cam_auto is not None
                           else "Configurar P4 para auto-estimación.")
                    ),
                )
                dP_camara_val = dP_cam_input if dP_cam_input > 0 else None
                if dP_cam_auto is not None:
                    st.caption(f"Auto P4: **{dP_cam_auto:.1f} Pa**")

            # ΔP ductos
            with c3:
                usar_ductos_manual = st.checkbox(
                    "Especificar ΔP ductos",
                    value=(mot_prev is not None and mot_prev.delta_P_ductos_Pa is not None),
                )
                if usar_ductos_manual:
                    dP_duc_input = st.number_input(
                        "ΔP ductos [Pa]",
                        min_value=0.0, max_value=500.0,
                        value=float(mot_prev.delta_P_ductos_Pa or 10.0)
                        if mot_prev is not None else 10.0,
                        step=1.0, format="%.1f",
                    )
                    dP_ductos_val = dP_duc_input
                else:
                    dP_duc_est = 0.20 * (dP_col_input + dP_cam_input)
                    st.caption(f"Auto 20%: **{dP_duc_est:.1f} Pa**")

            dP_tot_preview = (
                dP_col_input + dP_cam_input
                + (dP_ductos_val if dP_ductos_val is not None
                   else 0.20 * (dP_col_input + dP_cam_input))
            )
            st.caption(
                f"**ΔP total estimada: {dP_tot_preview:.1f} Pa** "
                f"(col={dP_col_input:.1f} + cam={dP_cam_input:.1f} + "
                f"duc={dP_tot_preview - dP_col_input - dP_cam_input:.1f})"
            )

    # -----------------------------------------------------------------------
    # Sección D: Parámetros del ventilador / motor
    # -----------------------------------------------------------------------
    with st.expander("Parámetros del ventilador y motor", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            eta_vent = st.slider(
                "η ventilador [%]",
                min_value=20, max_value=85,
                value=int((mot_prev.eficiencia_ventilador
                           if mot_prev is not None else 0.55) * 100),
                step=5,
                help="Axial simple: 45–60%. Centrífugo media presión: 60–75%.",
            ) / 100.0
        with c2:
            eta_motor_val = st.slider(
                "η motor eléctrico [%]",
                min_value=50, max_value=97,
                value=int((mot_prev.eficiencia_motor
                           if mot_prev is not None else 0.85) * 100),
                step=5,
                help="Motores < 1 kW: 75–85%.",
            ) / 100.0
        with c3:
            fs = st.number_input(
                "Factor de servicio [-]",
                min_value=1.0, max_value=2.0,
                value=mot_prev.factor_servicio if mot_prev is not None else 1.15,
                step=0.05, format="%.2f",
                help="Sobredimensionamiento del motor. Estándar NEMA continuo: 1.15.",
            )

        tension_val: float | None = None
        if tipo == TipoAccionamiento.MOTOR_ELECTRICO:
            usar_tension = st.checkbox(
                "Especificar tensión de alimentación",
                value=mot_prev is not None and mot_prev.tension_V is not None,
            )
            if usar_tension:
                tension_val = float(st.selectbox(
                    "Tensión [V]",
                    options=[220, 380],
                    index=0 if (mot_prev is None or mot_prev.tension_V != 380.0) else 1,
                ))

    # -----------------------------------------------------------------------
    # Sección E: Extractor eólico
    # -----------------------------------------------------------------------
    diametro_ext_val: float | None = None
    v_viento_val: float | None = None

    if tipo == TipoAccionamiento.EXTRACTOR_EOLICO:
        with st.expander("Parámetros del extractor eólico", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                diametro_ext_val = st.selectbox(
                    "Diámetro del extractor [m]",
                    options=[0.30, 0.45, 0.60],
                    index=1,
                    format_func=lambda d: f"{d:.2f} m ({d * 100:.0f} cm)",
                    help="Tallas comerciales típicas de turbinas tipo sombrero chino.",
                )
            with c2:
                usar_v_viento = st.checkbox(
                    "Especificar velocidad de viento de diseño",
                    value=mot_prev is not None
                          and mot_prev.velocidad_viento_diseno_m_s is not None,
                )
                if usar_v_viento:
                    v_default = 3.0
                    if proyecto.clima is not None and proyecto.clima.datos is not None:
                        v_default = round(
                            float(proyecto.clima.datos["WS_ms"].mean()), 1
                        )
                    v_viento_val = st.number_input(
                        "Velocidad de viento de diseño [m/s]",
                        min_value=0.5, max_value=20.0,
                        value=v_default, step=0.5, format="%.1f",
                        help="Usar la mediana del viento del emplazamiento (P50).",
                    )
            st.info(
                "ℹ️ En v0 el caudal del extractor no se calcula automáticamente. "
                "El caudal indicado es el **requerimiento del sistema**. "
                "Verificar capacidad contra el catálogo del fabricante."
            )

    # -----------------------------------------------------------------------
    # Botón: calcular
    # -----------------------------------------------------------------------
    st.divider()
    if st.button("⚙️ Calcular motor", type="primary"):
        try:
            motor = Motor(
                tipo_accionamiento=tipo,
                caudal_volumetrico_m3_s=Q_vol_m3s,
                perdida_carga_total_Pa=dP_total_override,
                delta_P_colector_Pa=dP_colector_val,
                delta_P_camara_Pa=dP_camara_val,
                delta_P_ductos_Pa=dP_ductos_val,
                eficiencia_ventilador=eta_vent,
                eficiencia_motor=eta_motor_val,
                factor_servicio=fs,
                tension_V=tension_val,
                diametro_extractor_m=diametro_ext_val,
                velocidad_viento_diseno_m_s=v_viento_val,
            )
            proyecto.motor = motor
        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Error de configuración: {exc}")
            return

        if motor.advertencias:
            st.subheader("Advertencias de diseño")
            _mostrar_advertencias(motor.advertencias)
        else:
            st.success("✅ Motor dimensionado sin advertencias.")

        # Resultados
        st.subheader("Resultados del dimensionamiento")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ΔP total", f"{motor.perdida_carga_total_Pa:.1f} Pa")
        c2.metric(
            "P hidráulica",
            f"{motor.potencia_hidraulica_W:.1f} W"
            if motor.potencia_hidraulica_W else "—",
            help="Q × ΔP",
        )
        c3.metric(
            "P eléctrica",
            f"{motor.potencia_electrica_W:.1f} W"
            if motor.potencia_electrica_W else "—",
            help=f"P_hid / (η_vent={eta_vent:.0%} × η_motor={eta_motor_val:.0%})",
        )
        c4.metric(
            "P a instalar",
            f"{motor.potencia_a_instalar_W:.1f} W"
            if motor.potencia_a_instalar_W else "—",
            help=f"P_elec × FS={fs:.2f}. Potencia nominal del motor a comprar.",
        )

        if motor.corriente_nominal_A is not None:
            st.info(
                f"⚡ Corriente nominal estimada: **{motor.corriente_nominal_A:.2f} A** "
                f"a {int(motor.tension_V)} V (cos φ = 0.85)"
            )

        with st.expander("Resumen de la configuración"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Tipo:** {tipo_label}")
                st.write(f"**Caudal:** {Q_vol_ls:.1f} L/s")
                st.write(f"**ΔP total:** {motor.perdida_carga_total_Pa:.1f} Pa")
                st.write(f"**η ventilador:** {eta_vent:.0%}")
                st.write(f"**η motor:** {eta_motor_val:.0%}")
                st.write(f"**Factor servicio:** {fs:.2f}")
            with c2:
                if motor.potencia_hidraulica_W:
                    st.write(f"**P hidráulica:** {motor.potencia_hidraulica_W:.1f} W")
                if motor.potencia_eje_W:
                    st.write(f"**P eje:** {motor.potencia_eje_W:.1f} W")
                if motor.potencia_electrica_W:
                    st.write(f"**P eléctrica:** {motor.potencia_electrica_W:.1f} W")
                if motor.potencia_a_instalar_W:
                    st.write(f"**P a instalar:** {motor.potencia_a_instalar_W:.1f} W")
                if motor.corriente_nominal_A:
                    st.write(f"**Corriente:** {motor.corriente_nominal_A:.2f} A")
                if tipo == TipoAccionamiento.EXTRACTOR_EOLICO and diametro_ext_val:
                    st.write(f"**Diámetro extractor:** {diametro_ext_val:.2f} m")

    # --- Guardar configuración ---
    if proyecto.motor is not None:
        st.divider()
        st.download_button(
            "Guardar configuración del motor (.txt)",
            data=_texto_config_motor(proyecto.motor),
            file_name="config_motor.txt",
            mime="text/plain",
            use_container_width=True,
        )
