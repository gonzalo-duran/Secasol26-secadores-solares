"""
Pestaña 6 — Motor / Ventilador.

Dimensiona el sistema de convección forzada calculando la pérdida de carga
total del sistema (colector + cámara + ductos) y la potencia eléctrica del
motor necesaria para vencerla.

Soporta:
    - Motor eléctrico con ventilador axial o centrífugo.

La convección natural no requiere motor (proyecto.motor = None). En ese caso,
se configura la chimenea solar — opcionalmente con extractor eólico en el
tope — desde esta misma pestaña.
"""

from __future__ import annotations

import streamlit as st

from calculos.chimenea_calc import (
    _v_viento_a_altura,
    delta_P_tiro_Pa,
    delta_P_turbina_motriz_Pa,
)
from calculos.motor_calc import (
    caudal_masico_a_volumetrico,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
    estimar_delta_P_singulares,
)
from core import catalogo
from core.advertencias import Severidad
from core.chimenea import Chimenea, advertencias_chimenea
from core.motor import Motor, TipoAccionamiento

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_T_MEDIA_DEFAULT_K: float = 323.15  # 50 °C — temperatura media del sistema


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
    """Snapshot .txt del motor con desglose completo de ΔP y potencias."""
    from datetime import date
    from core.motor import TipoAccionamiento

    sep = "=" * 60
    lines = [
        sep,
        "        CONFIGURACIÓN DEL MOTOR / VENTILADOR",
        sep,
        f"Fecha de exportación: {date.today()}",
        "",
        "TIPO Y CAUDAL",
        f"  Tipo accionamiento : {motor.tipo_accionamiento.value}",
        f"  Caudal volumétrico : {motor.caudal_volumetrico_m3_s * 1000:.3f} L/s "
        f"({motor.caudal_volumetrico_m3_s:.5f} m³/s)",
        "",
        "PÉRDIDA DE CARGA",
        f"  ΔP total           : {motor.perdida_carga_total_Pa:.2f} Pa",
    ]
    if motor.delta_P_colector_Pa is not None:
        lines.append(f"    · ΔP colector   : {motor.delta_P_colector_Pa:.2f} Pa")
    if motor.delta_P_camara_Pa is not None:
        lines.append(f"    · ΔP cámara     : {motor.delta_P_camara_Pa:.2f} Pa")
    if motor.delta_P_ductos_Pa is not None:
        lines.append(f"    · ΔP ductos     : {motor.delta_P_ductos_Pa:.2f} Pa")
    if motor.delta_P_singulares_Pa is not None:
        lines.append(f"    · ΔP singulares : {motor.delta_P_singulares_Pa:.2f} Pa")
    if motor.v_descarga_m_s is not None:
        lines.append(f"  v descarga         : {motor.v_descarga_m_s:.2f} m/s")
    lines += [
        "",
        "EFICIENCIAS Y DIMENSIONAMIENTO",
        f"  η ventilador       : {motor.eficiencia_ventilador:.1%}",
        f"  η motor            : {motor.eficiencia_motor:.1%}",
        f"  Factor servicio    : {motor.factor_servicio:.2f}",
    ]
    if motor.tipo_accionamiento == TipoAccionamiento.MOTOR_ELECTRICO:
        lines += [
            "",
            "MOTOR ELÉCTRICO",
            f"  Tensión            : "
            + (f"{motor.tension_V:.0f} V" if motor.tension_V else "(no especificada)"),
        ]
    lines += [
        "",
        "POTENCIAS CALCULADAS",
    ]
    if motor.potencia_hidraulica_W is not None:
        lines.append(f"  P hidráulica       : {motor.potencia_hidraulica_W:.2f} W")
    if motor.potencia_eje_W is not None:
        lines.append(f"  P eje              : {motor.potencia_eje_W:.2f} W")
    if motor.potencia_electrica_W is not None:
        lines.append(f"  P eléctrica        : {motor.potencia_electrica_W:.2f} W")
    if motor.potencia_a_instalar_W is not None:
        lines.append(
            f"  P a instalar       : {motor.potencia_a_instalar_W:.2f} W "
            f"({motor.potencia_a_instalar_W / 1000:.3f} kW)"
        )
    if motor.corriente_nominal_A is not None:
        lines.append(f"  Corriente nominal  : {motor.corriente_nominal_A:.3f} A " f"(cos φ = 0.85)")
    if all(
        p is None
        for p in (motor.potencia_hidraulica_W, motor.potencia_eje_W, motor.potencia_electrica_W)
    ):
        lines.append("  (sin ΔP > 0, no se calcularon potencias)")

    if motor.notas:
        lines += ["", "NOTAS", f"  {motor.notas}"]

    lines += ["", "ADVERTENCIAS ESTÁTICAS DE DISEÑO"]
    if not motor.advertencias:
        lines.append("  (ninguna)")
    else:
        for a in motor.advertencias:
            lines.append(f"  [{a.severidad.value}] {a.codigo}: {a.mensaje}")
    lines.append("")
    return "\n".join(lines)


def _from_json_motor(data: dict) -> tuple["Motor | None", "Chimenea | None", str | None]:
    """Reconstruye un ``Motor`` desde un dict producido por ``_json_config_motor``.

    Para preservar el dimensionamiento original, si la pérdida total fue
    explícitamente especificada por el usuario (es decir, no es la suma de
    los componentes), se pasa al constructor; de lo contrario se deja en
    None y se deja que ``__post_init__`` la recompute.

    Migración de snapshots pre-S31: si el JSON trae
    ``tipo_accionamiento == "EXTRACTOR_EOLICO"``, se devuelve
    ``(None, Chimenea_migrada, aviso)``. El extractor se reemplaza por una
    Chimenea con ``extractor_activo=True``, preservando el diámetro original
    como ``diametro_extractor_m`` y usando defaults físicos para Cp/Kt/z0.

    Returns:
        Tupla ``(motor, chimenea_migrada, aviso)``. Solo uno de ``motor`` y
        ``chimenea_migrada`` está activo; el otro es None. ``aviso`` es un
        mensaje legible si hubo migración, o None.

    Raises:
        KeyError/ValueError: si faltan campos o el Enum no es válido.
    """
    tipo_str = data.get("tipo_accionamiento", "")
    if tipo_str == "EXTRACTOR_EOLICO":
        eolico = data.get("eolico") or {}
        diam_ext = eolico.get("diametro_extractor_m")
        chim_migrada = Chimenea(
            diametro_m=0.20,
            altura_m=2.0,
            id_material="galvanizada_sin_pintura",
            extractor_activo=True,
            diametro_extractor_m=(float(diam_ext) if diam_ext is not None else 0.45),
        )
        aviso = (
            "Snapshot pre-S31 detectado: el extractor eólico ya no se modela "
            "como motor sino como accesorio de la chimenea solar. Se reconstruyó "
            "automáticamente una chimenea con extractor activo "
            f"(diámetro {chim_migrada.diametro_extractor_m*100:.0f} cm, "
            f"Cp={chim_migrada.Cp_turbina}, Kt={chim_migrada.Kt_turbina}). "
            "Revisá la sección 'Chimenea solar' abajo para ajustar geometría, "
            "altura y material — los valores son defaults."
        )
        return None, chim_migrada, aviso

    dp = data.get("perdida_de_carga") or {}
    eff = data.get("eficiencias") or {}
    elec = data.get("electrico") or {}

    dp_componentes = [
        dp.get("delta_P_colector_Pa") or 0.0,
        dp.get("delta_P_camara_Pa") or 0.0,
        dp.get("delta_P_ductos_Pa") or 0.0,
        dp.get("delta_P_singulares_Pa") or 0.0,
    ]
    dp_total = dp.get("delta_P_total_Pa")
    suma_comp = sum(dp_componentes)
    # Si total ≈ suma de componentes, dejamos None para que __post_init__
    # lo recompute (consistente con cómo lo calcula Motor); si difiere,
    # respetamos el valor explícito guardado.
    pasar_total = None
    if dp_total is not None and abs(dp_total - suma_comp) > 0.5:
        pasar_total = float(dp_total)

    motor = Motor(
        tipo_accionamiento=TipoAccionamiento(data["tipo_accionamiento"]),
        caudal_volumetrico_m3_s=float(data["caudal_volumetrico_m3_s"]),
        perdida_carga_total_Pa=pasar_total,
        delta_P_colector_Pa=(
            float(dp["delta_P_colector_Pa"]) if dp.get("delta_P_colector_Pa") is not None else None
        ),
        delta_P_camara_Pa=(
            float(dp["delta_P_camara_Pa"]) if dp.get("delta_P_camara_Pa") is not None else None
        ),
        delta_P_ductos_Pa=(
            float(dp["delta_P_ductos_Pa"]) if dp.get("delta_P_ductos_Pa") is not None else None
        ),
        delta_P_singulares_Pa=(
            float(dp["delta_P_singulares_Pa"])
            if dp.get("delta_P_singulares_Pa") is not None
            else None
        ),
        v_descarga_m_s=(
            float(dp["v_descarga_m_s"]) if dp.get("v_descarga_m_s") is not None else None
        ),
        eficiencia_ventilador=float(eff.get("eficiencia_ventilador", 0.55)),
        eficiencia_motor=float(eff.get("eficiencia_motor", 0.85)),
        factor_servicio=float(eff.get("factor_servicio", 1.15)),
        tension_V=(float(elec["tension_V"]) if elec.get("tension_V") is not None else None),
        notas=data.get("notas") or "",
    )
    return motor, None, None


def _json_config_motor(motor: "Motor") -> dict:
    """Snapshot reconstruible (dict) del motor."""
    from datetime import date

    return {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "motor",
        "tipo_accionamiento": motor.tipo_accionamiento.value,
        "caudal_volumetrico_m3_s": motor.caudal_volumetrico_m3_s,
        "perdida_de_carga": {
            "delta_P_total_Pa": motor.perdida_carga_total_Pa,
            "delta_P_colector_Pa": motor.delta_P_colector_Pa,
            "delta_P_camara_Pa": motor.delta_P_camara_Pa,
            "delta_P_ductos_Pa": motor.delta_P_ductos_Pa,
            "delta_P_singulares_Pa": motor.delta_P_singulares_Pa,
            "v_descarga_m_s": motor.v_descarga_m_s,
        },
        "eficiencias": {
            "eficiencia_ventilador": motor.eficiencia_ventilador,
            "eficiencia_motor": motor.eficiencia_motor,
            "factor_servicio": motor.factor_servicio,
        },
        "electrico": {
            "tension_V": motor.tension_V,
        },
        "notas": motor.notas,
        "resultados": {
            "ejecutado": (motor.potencia_hidraulica_W is not None),
            "potencia_hidraulica_W": motor.potencia_hidraulica_W,
            "potencia_eje_W": motor.potencia_eje_W,
            "potencia_electrica_W": motor.potencia_electrica_W,
            "potencia_a_instalar_W": motor.potencia_a_instalar_W,
            "corriente_nominal_A": motor.corriente_nominal_A,
        },
        "advertencias_diseno": [
            {
                "codigo": a.codigo,
                "severidad": a.severidad.value,
                "mensaje": a.mensaje,
                "campo": a.campo,
                "sugerencia": a.sugerencia,
                "contexto": a.contexto,
            }
            for a in motor.advertencias
        ],
    }


# ---------------------------------------------------------------------------
# Chimenea solar — serialización
# ---------------------------------------------------------------------------


def _from_json_chimenea(data: dict) -> Chimenea:
    """Reconstruye una Chimenea desde un dict producido por _json_config_chimenea.

    Compatible con snapshots viejos (sin campos del extractor): los defaults
    de la dataclass se aplican automáticamente (extractor_activo=False).
    """
    ch = data.get("chimenea") or {}
    kwargs = {
        "diametro_m": float(ch["diametro_m"]),
        "altura_m": float(ch["altura_m"]),
        "id_material": ch["id_material"],
    }
    extractor = ch.get("extractor")
    if extractor is not None:
        kwargs["extractor_activo"] = bool(extractor.get("activo", False))
        if extractor.get("diametro_extractor_m") is not None:
            kwargs["diametro_extractor_m"] = float(extractor["diametro_extractor_m"])
        if extractor.get("Cp_turbina") is not None:
            kwargs["Cp_turbina"] = float(extractor["Cp_turbina"])
        if extractor.get("Kt_turbina") is not None:
            kwargs["Kt_turbina"] = float(extractor["Kt_turbina"])
        if extractor.get("z0_terreno_m") is not None:
            kwargs["z0_terreno_m"] = float(extractor["z0_terreno_m"])
    return Chimenea(**kwargs)


def _json_config_chimenea(chimenea: Chimenea) -> dict:
    """Snapshot reconstruible (dict) de la chimenea solar."""
    from datetime import date

    props = dict(catalogo.FONDOS.get(chimenea.id_material, {}))
    advs = advertencias_chimenea(chimenea)
    return {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "chimenea",
        "chimenea": {
            "diametro_m": chimenea.diametro_m,
            "altura_m": chimenea.altura_m,
            "id_material": chimenea.id_material,
            "props_catalogo": props,
            "extractor": {
                "activo": chimenea.extractor_activo,
                "diametro_extractor_m": chimenea.diametro_extractor_m,
                "Cp_turbina": chimenea.Cp_turbina,
                "Kt_turbina": chimenea.Kt_turbina,
                "z0_terreno_m": chimenea.z0_terreno_m,
            },
        },
        "advertencias_diseno": [
            {
                "codigo": a.codigo,
                "severidad": a.severidad.value,
                "mensaje": a.mensaje,
                "campo": a.campo,
                "sugerencia": a.sugerencia,
                "contexto": a.contexto,
            }
            for a in advs
        ],
    }


def _texto_config_chimenea(chimenea: Chimenea) -> str:
    """Snapshot .txt de la chimenea solar."""
    from datetime import date

    desc = catalogo.FONDOS.get(chimenea.id_material, {}).get("descripcion", chimenea.id_material)
    sep = "=" * 60
    lines = [
        sep,
        "        CONFIGURACIÓN DE LA CHIMENEA SOLAR",
        sep,
        f"Fecha de exportación: {date.today()}",
        "",
        "GEOMETRÍA Y MATERIAL",
        f"  Diámetro interno : {chimenea.diametro_m:.3f} m  ({chimenea.diametro_m*100:.1f} cm)",
        f"  Altura           : {chimenea.altura_m:.2f} m",
        f"  Material         : {desc}  [id={chimenea.id_material}]",
    ]
    if chimenea.extractor_activo:
        d_ext = chimenea.diametro_extractor_m
        lines += [
            "",
            "EXTRACTOR EÓLICO",
            f"  Diámetro extractor : {d_ext*100:.1f} cm" if d_ext else "  Diámetro extractor : —",
            f"  Cp turbina         : {chimenea.Cp_turbina:.2f}",
            f"  Kt turbina         : {chimenea.Kt_turbina:.2f}",
            f"  z0 terreno         : {chimenea.z0_terreno_m:.3f} m",
        ]
    advs = advertencias_chimenea(chimenea)
    lines += ["", "ADVERTENCIAS ESTÁTICAS DE DISEÑO"]
    if not advs:
        lines.append("  (ninguna)")
    else:
        for a in advs:
            lines.append(f"  [{a.severidad.value}] {a.codigo}: {a.mensaje}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chimenea solar — render section
# ---------------------------------------------------------------------------


def _condiciones_representativas_chimenea(
    proyecto,
) -> tuple[float, float, str]:
    """Devuelve (T_amb_K, v_viento_ms, origen) para la evaluación de chimenea.

    Si hay clima cargado, usa la media anual; en caso contrario cae a un
    20 °C / 2 m/s estándar. El string de origen va al caption de resultados.
    """
    clima = getattr(proyecto, "clima", None)
    if clima is not None and getattr(clima, "datos", None) is not None:
        try:
            datos = clima.datos
            T_arr = datos["T_amb_K"].to_numpy()
            v_arr = datos["WS_ms"].to_numpy()
            T_amb_K = float(T_arr.mean())
            v_viento = float(v_arr.mean())
            return T_amb_K, v_viento, "media anual NASA POWER (P2)"
        except Exception:
            pass
    return 293.15, 2.0, "fallback (T=20 °C, v=2 m/s)"


def _render_calcular_chimenea(proyecto, chimenea) -> None:
    """Botón 'Calcular chimenea' + display de resultados del lazo natural.

    Resuelve ``_caudal_natural_loop`` con condiciones representativas
    (T_amb / v_viento del clima, T_chim heurística según tipología) y los
    ΔP del colector y cámara reales del proyecto. Persiste el resultado en
    ``st.session_state['p6_chimenea_eval']`` para que P7 cuente la chimenea
    como evaluada en el checklist.
    """
    from core.proyecto import Tipologia

    requisitos_ok = proyecto.camara is not None
    if not requisitos_ok:
        st.warning(
            "⚠️ Configurá la cámara (P4) antes de evaluar la chimenea — su "
            "caudal de diseño y ΔP son inputs del lazo natural."
        )
        return

    es_caja = (
        getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
        == Tipologia.CAJA
    )
    delta_T_chim_K = 25.0 if es_caja else 30.0

    if st.button("🌪️ Calcular chimenea", type="primary", key="p6_btn_calc_chimenea"):
        from calculos.balance_global import (
            _caudal_natural_loop,
            presion_representativa_proyecto,
        )

        T_amb_K, v_viento_ms, origen_clima = _condiciones_representativas_chimenea(proyecto)
        T_chim_K = T_amb_K + delta_T_chim_K
        P_proyecto_Pa, P_origen = presion_representativa_proyecto(proyecto)

        try:
            with st.spinner("Resolviendo lazo natural por chimenea..."):
                res_chim = _caudal_natural_loop(
                    proyecto=proyecto,
                    T_amb_K=T_amb_K,
                    T_chim_K=T_chim_K,
                    m_design_kgs=proyecto.camara.flujo.caudal_masico_kg_s,
                    P_amb_Pa=P_proyecto_Pa,
                    v_viento_ms=v_viento_ms,
                )
        except Exception as exc:
            st.error(f"❌ Error en el cálculo: {exc}")
            return

        st.session_state["p6_chimenea_eval"] = {
            "T_amb_K": T_amb_K,
            "T_chim_K": T_chim_K,
            "delta_T_chim_K": delta_T_chim_K,
            "v_viento_ms": v_viento_ms,
            "P_amb_Pa": P_proyecto_Pa,
            "P_origen": P_origen,
            "origen_clima": origen_clima,
            "es_caja": es_caja,
            "resultado": res_chim,
        }

    ev = st.session_state.get("p6_chimenea_eval")
    if ev is None:
        st.caption(
            "Presioná **Calcular chimenea** para resolver el lazo natural con "
            "condiciones representativas. El resultado queda persistido y se "
            "muestra en P7 como sección evaluada."
        )
        return

    res = ev["resultado"]
    st.subheader("Resultados del lazo natural")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Caudal natural",
        f"{res['m_punto_kgs'] * 1000:.2f} g/s",
        help="ṁ de equilibrio del lazo (cámara + colector + chimenea).",
    )
    c2.metric(
        "v en chimenea",
        f"{res['v_chim_ms']:.2f} m/s",
        help="Velocidad media en la sección de la chimenea.",
    )
    c3.metric(
        "Re chimenea",
        f"{res['Re_chimenea']:.0f}",
        help="Re > 4000: turbulento. Re < 2300: laminar.",
    )
    c4.metric(
        "ΔP tiro térmico",
        f"{res['delta_P_tiro_Pa']:.2f} Pa",
        help="Empuje hidrostático = g·H_eff·(ρ_amb − ρ_chim).",
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric(
        "ΔP ducto chimenea",
        f"{res['delta_P_chimenea_Pa']:.2f} Pa",
        help="Fricción + singulares del ducto de chimenea.",
    )
    c6.metric(
        "ΔP resto (col+cam)",
        f"{res['delta_P_resto_Pa']:.2f} Pa",
        help="ΔP de colector + cámara escalado cuadrático al caudal de equilibrio.",
    )
    dP_turb = float(res.get("delta_P_turbina_motriz_Pa", 0.0))
    if dP_turb > 0.0:
        c7.metric(
            "ΔP motriz turbina",
            f"{dP_turb:.2f} Pa",
            help=f"Extractor eólico a v_local={res.get('v_viento_local_ms', 0.0):.2f} m/s.",
        )
    c8.metric("H efectiva", f"{res['H_eff_m']:.2f} m")

    advs = res.get("advertencias", []) or []
    if advs:
        with st.expander(f"⚠️ {len(advs)} advertencia(s) del lazo natural"):
            for a in advs:
                st.warning(a)

    st.caption(
        f"Inputs: T_amb={ev['T_amb_K'] - 273.15:.1f} °C, "
        f"T_chim={ev['T_chim_K'] - 273.15:.1f} °C "
        f"(heurística ΔT={ev['delta_T_chim_K']:.0f} K para "
        f"{'CAJA' if ev['es_caja'] else 'ARMARIO/GRAN_ESCALA'}), "
        f"v_viento={ev['v_viento_ms']:.1f} m/s, "
        f"P={ev['P_amb_Pa'] / 1000:.2f} kPa. "
        f"Clima: {ev['origen_clima']}. Presión: {ev['P_origen']}. "
        "En P7 se vuelve a resolver con el lazo Picard completo (T_chim de la "
        "cámara realimenta el cálculo)."
    )


def _render_chimenea_section(proyecto) -> None:
    """Renderiza la configuración de chimenea solar.

    Se invoca cuando no hay motor (convección natural). La chimenea vive
    como componente top-level en ``proyecto.chimenea``, independiente del
    colector (utilizable también en tipología CAJA).
    """
    from calculos.balance_global import presion_representativa_proyecto

    # Presión atmosférica representativa para los previews de tiro térmico
    # y del extractor eólico. Se recomputa aquí porque la sección puede ser
    # llamada en contextos donde la variable de ``render()`` no está en scope.
    P_proyecto_Pa, _ = presion_representativa_proyecto(proyecto)

    st.divider()
    st.subheader("Chimenea solar")

    # --- Cargar configuración guardada ---
    with st.expander("📥 Cargar configuración de chimenea (.json)", expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            "Subí un archivo .json de chimenea previamente guardado",
            type=["json"],
            key="p6_chim_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "chimenea")
            if err:
                st.error(f"❌ {err}")
            else:
                try:
                    ch_cargada = _from_json_chimenea(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(f"❌ Error reconstruyendo la chimenea: {exc}")
                else:
                    proyecto.chimenea = ch_cargada
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p6_chim_")
                    st.session_state.pop("p6_chim_cargar_json", None)
                    st.success(
                        f"✅ Chimenea cargada desde JSON " f"(se reiniciaron {n_borr} valores)."
                    )
                    st.rerun()

    usar_chimenea = st.toggle(
        "Incorporar chimenea solar",
        value=proyecto.chimenea is not None,
        key="p6_usar_chimenea",
        help=(
            "Una chimenea genera tiraje térmico por diferencia de densidad entre "
            "el aire caliente (cámara + chimenea) y el ambiente. Modelo en "
            "`calculos.chimenea_calc`."
        ),
    )

    if not usar_chimenea:
        proyecto.chimenea = None
        st.session_state.pop("p6_chimenea_eval", None)
        st.caption("Sin chimenea. El aire se moverá solo por difusión libre.")
        return

    ch_ref = proyecto.chimenea or Chimenea()
    c1, c2, c3 = st.columns(3)
    with c1:
        diam = st.number_input(
            "Diámetro interno [m]",
            min_value=0.05,
            max_value=2.0,
            value=float(ch_ref.diametro_m),
            step=0.01,
            format="%.2f",
            key="p6_chim_diam",
        )
    with c2:
        alt = st.number_input(
            "Altura [m]",
            min_value=0.1,
            max_value=20.0,
            value=float(ch_ref.altura_m),
            step=0.1,
            format="%.1f",
            key="p6_chim_altura",
        )
    with c3:
        opciones = {
            id_mat: datos.get("descripcion", id_mat) for id_mat, datos in catalogo.FONDOS.items()
        }
        ids = list(opciones.keys())
        idx = ids.index(ch_ref.id_material) if ch_ref.id_material in ids else 0
        mat = st.selectbox(
            "Material",
            options=ids,
            index=idx,
            format_func=lambda x: opciones[x],
            key="p6_chim_material",
        )

    # --- Extractor eólico (turbina sombrero chino) -------------------------
    ch_ref_ext = proyecto.chimenea
    extractor_prev = bool(ch_ref_ext.extractor_activo) if ch_ref_ext else False

    ext_help = (
        "Turbina pasiva tipo 'sombrero chino' montada en el tope de la "
        "chimenea. Agrega un término motriz ΔP = Cp·ρ·v_viento²/2 al lazo "
        "natural, donde v_viento se corrige del valor NASA POWER (10 m) a "
        "la altura del tope via perfil logarítmico de capa límite. Tambien "
        "introduce una resistencia adicional Kt·ρ·v_flujo²/2 al flujo "
        "ascendente.\n\n"
        "**Casos límite:**\n"
        "• v_viento = 0 (calma): la turbina sólo agrega resistencia → peor "
        "que chimenea desnuda.\n"
        "• Sin sol (noche/nublado): si hay viento, la turbina sigue moviendo "
        "aire — robustez del sistema.\n"
        "• v_viento alto + sol: efectos se suman, caudal mayor.\n\n"
        "Sin correlación específica de literatura; los rangos de Cp y Kt son "
        "anclajes de orden de magnitud (Idelchik / hojas técnicas de turbinas "
        "comerciales)."
    )

    extractor_activo = st.checkbox(
        "Agregar extractor eólico en el tope",
        value=extractor_prev,
        key="p6_chim_ext_activo",
        help=ext_help,
    )

    diam_ext_val: float | None = None
    Cp_val: float = 0.4
    Kt_val: float = 1.0
    z0_val: float = 0.05

    if extractor_activo:
        with st.expander("Parámetros del extractor eólico", expanded=True):
            ec1, ec2 = st.columns(2)
            with ec1:
                diam_ext_default = (
                    float(ch_ref_ext.diametro_extractor_m)
                    if (ch_ref_ext and ch_ref_ext.diametro_extractor_m is not None)
                    else max(diam, 0.30)
                )
                diam_ext_val = st.number_input(
                    "Diámetro del extractor [m]",
                    min_value=0.10,
                    max_value=2.0,
                    value=diam_ext_default,
                    step=0.05,
                    format="%.2f",
                    key="p6_chim_ext_diam",
                    help=(
                        "Diámetro del orificio del extractor. Tallas comerciales "
                        "típicas: 0.30 / 0.45 / 0.60 m. Recomendado ≥ al "
                        "diámetro de la chimenea para evitar estrangulamiento."
                    ),
                )
            with ec2:
                Cp_val = st.number_input(
                    "Cp turbina [adim]",
                    min_value=0.05,
                    max_value=2.0,
                    value=float(ch_ref_ext.Cp_turbina) if ch_ref_ext else 0.4,
                    step=0.05,
                    format="%.2f",
                    key="p6_chim_ext_Cp",
                    help=(
                        "Coeficiente de presión motriz: ΔP_motriz = Cp·ρ·v² / 2. "
                        "Rango típico 0.3–0.6 para turbinas sombrero chino. "
                        "Valores más altos sólo con datos de fabricante."
                    ),
                )
            ec3, ec4 = st.columns(2)
            with ec3:
                Kt_val = st.number_input(
                    "Kt turbina (resistencia) [adim]",
                    min_value=0.0,
                    max_value=5.0,
                    value=float(ch_ref_ext.Kt_turbina) if ch_ref_ext else 1.0,
                    step=0.1,
                    format="%.2f",
                    key="p6_chim_ext_Kt",
                    help=(
                        "Coeficiente resistivo: ΔP_resistencia = Kt·ρ·v_flujo²/2 "
                        "sobre la velocidad del aire en el extractor. "
                        "1.0 (default) cubre expansión + obstrucción de álabes."
                    ),
                )
            with ec4:
                z0_opciones = {
                    "Mar/lago (0.001 m)": 0.001,
                    "Campo abierto (0.03 m)": 0.03,
                    "Rural medio (0.05 m)": 0.05,
                    "Suburbano (0.20 m)": 0.20,
                    "Urbano denso (0.50 m)": 0.50,
                }
                z0_prev_val = float(ch_ref_ext.z0_terreno_m) if ch_ref_ext else 0.05
                z0_prev_label = next(
                    (k for k, v in z0_opciones.items() if abs(v - z0_prev_val) < 1e-6),
                    "Rural medio (0.05 m)",
                )
                z0_label = st.selectbox(
                    "Tipo de terreno (z₀)",
                    options=list(z0_opciones.keys()),
                    index=list(z0_opciones.keys()).index(z0_prev_label),
                    key="p6_chim_ext_z0",
                    help=(
                        "Longitud de rugosidad aerodinámica del terreno. Se "
                        "usa para corregir el viento de NASA POWER (a 10 m) "
                        "a la altura del tope de chimenea via perfil "
                        "logarítmico v(z) = v(10)·ln(z/z₀)/ln(10/z₀)."
                    ),
                )
                z0_val = z0_opciones[z0_label]

            # Preview: viento corregido a la altura del tope.
            v_viento_10m: float | None = None
            try:
                if (
                    proyecto.clima is not None
                    and proyecto.clima.datos is not None
                    and "WS_ms" in proyecto.clima.datos.columns
                ):
                    v_viento_10m = float(proyecto.clima.datos["WS_ms"].mean())
            except (AttributeError, KeyError):
                v_viento_10m = None

            H_cam_default = 1.5
            if proyecto.camara is not None:
                try:
                    H_cam_default = float(proyecto.camara.geometria.alto_m)
                except (AttributeError, TypeError):
                    pass
            z_tope = H_cam_default + alt
            if v_viento_10m is not None:
                v_loc = _v_viento_a_altura(v_viento_10m, z_tope, z0_val)
                dP_turb = delta_P_turbina_motriz_Pa(
                    v_loc, Cp_val, T_amb_K=293.15, P_amb_Pa=P_proyecto_Pa
                )
                st.caption(
                    f"Viento medio del sitio (P2, a 10 m): "
                    f"**{v_viento_10m:.1f} m/s** → corregido a {z_tope:.1f} m del "
                    f"tope: **{v_loc:.2f} m/s** → ΔP motriz turbina (a T_amb 20 °C): "
                    f"**{dP_turb:.2f} Pa**."
                )
            else:
                st.caption(
                    "Cargar datos de clima en P2 para previsualizar el efecto "
                    "del viento a la altura del tope de la chimenea."
                )

    try:
        nueva = Chimenea(
            diametro_m=diam,
            altura_m=alt,
            id_material=mat,
            extractor_activo=extractor_activo,
            diametro_extractor_m=diam_ext_val if extractor_activo else None,
            Cp_turbina=Cp_val,
            Kt_turbina=Kt_val,
            z0_terreno_m=z0_val,
        )
    except ValueError as err:
        st.error(f"**Error de validación** — {err}")
        return
    proyecto.chimenea = nueva

    # --- Advertencias ---
    adv_list = advertencias_chimenea(nueva)
    if adv_list:
        for a in adv_list:
            _mostrar_advertencias([a])

    # --- Preview de tiro térmico ---
    st.markdown("**Tiro térmico estimado** (cámara + chimenea como columna ascendente)")
    H_camara_default = 1.5  # m, placeholder hasta integrar con P4
    if proyecto.camara is not None and getattr(proyecto.camara, "geometria", None) is not None:
        try:
            H_camara_default = float(proyecto.camara.geometria.alto_m)
        except (AttributeError, TypeError):
            pass
    H_eff = nueva.altura_m + H_camara_default
    T_amb_C = 20.0
    delta_T_ejemplos = (10.0, 20.0, 30.0, 40.0)
    cols = st.columns(len(delta_T_ejemplos))
    for col_w, dT in zip(cols, delta_T_ejemplos):
        dP = delta_P_tiro_Pa(
            T_amb_K=273.15 + T_amb_C,
            T_chim_K=273.15 + T_amb_C + dT,
            H_eff_m=H_eff,
            P_amb_Pa=P_proyecto_Pa,
        )
        col_w.metric(f"ΔT = +{dT:.0f} K", f"{dP:.2f} Pa")
    st.caption(
        f"Cálculo informativo con T_amb=20 °C, H_efectiva = altura_chimenea ({nueva.altura_m:.1f} m) "
        f"+ alto_cámara ({H_camara_default:.2f} m) = {H_eff:.2f} m. El caudal de equilibrio "
        f"se resuelve en `balance_global` con T_chim del lazo y pérdidas reales."
    )

    # --- Botón: calcular chimenea (lazo natural con condiciones representativas) ---
    st.divider()
    _render_calcular_chimenea(proyecto, nueva)

    # --- Guardar configuración ---
    st.divider()
    from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

    col_txt, col_json = st.columns(2)
    with col_txt:
        st.download_button(
            "Guardar configuración de chimenea (.txt)",
            data=_texto_config_chimenea(nueva),
            file_name=nombre_archivo_descarga(proyecto, "chimenea", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            "Guardar configuración de chimenea (.json)",
            data=dump_json(_json_config_chimenea(nueva)),
            file_name=nombre_archivo_descarga(proyecto, "chimenea", "json"),
            mime="application/json",
            width="stretch",
        )


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 6 — Motor / Ventilador."""
    st.header("6 · Motor / Ventilador")

    proyecto = st.session_state.proyecto

    # Presión atmosférica representativa del emplazamiento (corregida por
    # altitud). Se propaga a estimar_delta_P_* y al preview de chimenea.
    from calculos.balance_global import presion_representativa_proyecto

    P_proyecto_Pa, _P_origen = presion_representativa_proyecto(proyecto)

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander("📥 Cargar configuración guardada (.json)", expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            "Subí un archivo .json del motor previamente guardado",
            type=["json"],
            key="p6_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "motor")
            if err:
                st.error(f"❌ {err}")
            else:
                try:
                    mot_cargado, chim_migrada, aviso_migracion = _from_json_motor(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(f"❌ Error reconstruyendo el motor: {exc}")
                else:
                    proyecto.motor = mot_cargado
                    if chim_migrada is not None:
                        proyecto.chimenea = chim_migrada
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p6_")
                    st.session_state.pop("p6_cargar_json", None)
                    if aviso_migracion:
                        st.warning(f"⚠️ {aviso_migracion}")
                    st.success(
                        f"✅ Motor cargado desde JSON "
                        f"(se reiniciaron {n_borr} valores de la sesión)."
                    )
                    st.rerun()

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
            "Configurá la chimenea solar abajo para inducir tiraje térmico, "
            "o activá el toggle para dimensionar un ventilador."
        )
        _render_chimenea_section(proyecto)
        return

    mot_prev = proyecto.motor

    # -----------------------------------------------------------------------
    # Sección A: Tipo de accionamiento
    # -----------------------------------------------------------------------
    st.subheader("Tipo de accionamiento")

    # Sólo queda un tipo de motor: eléctrico. El extractor eólico se modela
    # como accesorio de la chimenea, no como tipo de motor (ver P6 sección
    # de chimenea cuando motor=None).
    tipo = TipoAccionamiento.MOTOR_ELECTRICO
    st.caption(
        "Motor eléctrico (ventilador axial o centrífugo). Para convección "
        "natural — eventualmente con extractor eólico en el tope de chimenea "
        "— desactivar el motor en el toggle de arriba."
    )

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
                P_proyecto_Pa,
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
                min_value=0.1,
                max_value=10000.0,
                value=round(Q_vol_sugerido * 1000.0, 1),
                step=0.5,
                format="%.1f",
                help=hint_caudal or "Caudal que debe mover el ventilador.",
            )
            Q_vol_m3s = Q_vol_ls / 1000.0
        with c2:
            if hint_caudal:
                st.info(f"💡 {hint_caudal}")
            st.metric("Caudal", f"{Q_vol_ls:.1f} L/s", help=f"{Q_vol_m3s:.5f} m³/s")

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
        dP_singulares_val: float | None = None

        if modo_dP == "ΔP total directo":
            dP_total_override = st.number_input(
                "ΔP total del sistema [Pa]",
                min_value=1.0,
                max_value=5000.0,
                value=float(
                    mot_prev.perdida_carga_total_Pa
                    if (mot_prev is not None and mot_prev.perdida_carga_total_Pa)
                    else 50.0
                ),
                step=1.0,
                format="%.1f",
                help="Incluye colector, cámara y ductos.",
            )

        else:
            c1, c2, c3 = st.columns(3)

            # ΔP colector
            dP_col_auto: float | None = None
            if proyecto.colector is not None:
                try:
                    dP_col_auto = estimar_delta_P_colector(
                        proyecto.colector, P_Pa=P_proyecto_Pa
                    )
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
                    min_value=0.0,
                    max_value=2000.0,
                    value=dP_col_default,
                    step=1.0,
                    format="%.1f",
                    help=(
                        "Pérdida de carga en el banco de colectores (Darcy-Weisbach). "
                        + (
                            f"Auto (P3): {dP_col_auto:.1f} Pa."
                            if dP_col_auto is not None
                            else "Configurar P3 para auto-estimación."
                        )
                    ),
                )
                dP_colector_val = dP_col_input if dP_col_input > 0 else None
                if dP_col_auto is not None:
                    st.caption(f"Auto P3: **{dP_col_auto:.1f} Pa**")

            # ΔP cámara
            dP_cam_auto: float | None = None
            if proyecto.camara is not None:
                try:
                    dP_cam_auto = estimar_delta_P_camara(
                        proyecto.camara, P_Pa=P_proyecto_Pa
                    )
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
                    min_value=0.0,
                    max_value=2000.0,
                    value=dP_cam_default,
                    step=1.0,
                    format="%.1f",
                    help=(
                        "Pérdida de carga en las bandejas de la cámara. "
                        + (
                            f"Auto (P4): {dP_cam_auto:.1f} Pa (K_malla=2.0)."
                            if dP_cam_auto is not None
                            else "Configurar P4 para auto-estimación."
                        )
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
                        min_value=0.0,
                        max_value=500.0,
                        value=(
                            float(mot_prev.delta_P_ductos_Pa or 10.0)
                            if mot_prev is not None
                            else 10.0
                        ),
                        step=1.0,
                        format="%.1f",
                    )
                    dP_ductos_val = dP_duc_input
                else:
                    dP_duc_est = 0.20 * (dP_col_input + dP_cam_input)
                    st.caption(f"Auto 20%: **{dP_duc_est:.1f} Pa**")

            # --- ΔP singulares (entrada, salida, codos, manifold) ---
            # v_ducto = velocidad típica en ductos de aire de secadores solares
            # (5–10 m/s). NO es la velocidad del canal del colector (mucho más
            # baja) ni la velocidad superficial de la cámara. Default 6 m/s.
            v_ducto = float(st.session_state.get("p6_v_ducto", 6.0))
            n_paralelo = 1
            if proyecto.colector is not None:
                try:
                    n_paralelo = int(proyecto.colector.banco.n_paralelo)
                except Exception:
                    pass
            sing = estimar_delta_P_singulares(
                Q_vol_m3_s=Q_vol_m3s,
                v_ducto_m_s=v_ducto,
                n_paralelo=n_paralelo,
                n_codos=2,
                P_Pa=P_proyecto_Pa,
            )
            dP_singulares_val = sing["total"]
            with st.expander(
                f"ΔP singulares (entrada, salida, codos, manifold): "
                f"**{dP_singulares_val:.1f} Pa**",
                expanded=False,
            ):
                v_ducto_input = st.number_input(
                    "Velocidad del aire en ducto principal [m/s]",
                    min_value=1.0,
                    max_value=20.0,
                    value=v_ducto,
                    step=0.5,
                    format="%.1f",
                    help=(
                        "Velocidad típica en ductos de secadores solares: 5–10 m/s. "
                        "Más alta → más pérdida singular. Para ductos de ø≈15 cm con "
                        "Q≈900 m³/h, v ≈ 14 m/s."
                    ),
                )
                if abs(v_ducto_input - v_ducto) > 1e-6:
                    st.session_state["p6_v_ducto"] = v_ducto_input
                    # Recalcular display si el usuario tocó la velocidad
                    sing = estimar_delta_P_singulares(
                        Q_vol_m3_s=Q_vol_m3s,
                        v_ducto_m_s=v_ducto_input,
                        n_paralelo=n_paralelo,
                        n_codos=2,
                        P_Pa=P_proyecto_Pa,
                    )
                    dP_singulares_val = sing["total"]
                    v_ducto = v_ducto_input
                st.caption(
                    f"n_paralelo = {n_paralelo} · n_codos asumidos = 2\n\n"
                    f"- Entrada (K=0.5): {sing['entrada']:.1f} Pa\n"
                    f"- Salida descarga libre (K=1.0): {sing['salida']:.1f} Pa\n"
                    f"- 2 codos 90° (K=0.9 c/u): {sing['codos']:.1f} Pa\n"
                    f"- Manifold banco paralelo (K=1.5): {sing['manifold']:.1f} Pa"
                )

            dP_ductos_efectivo = (
                dP_ductos_val if dP_ductos_val is not None else 0.20 * (dP_col_input + dP_cam_input)
            )
            dP_tot_preview = dP_col_input + dP_cam_input + dP_ductos_efectivo + dP_singulares_val
            st.caption(
                f"**ΔP total estimada: {dP_tot_preview:.1f} Pa** "
                f"(col={dP_col_input:.1f} + cam={dP_cam_input:.1f} + "
                f"duc={dP_ductos_efectivo:.1f} + sing={dP_singulares_val:.1f})"
            )

    # -----------------------------------------------------------------------
    # Sección D: Parámetros del ventilador / motor
    # -----------------------------------------------------------------------
    with st.expander("Parámetros del ventilador y motor", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            eta_vent = (
                st.slider(
                    "η ventilador [%]",
                    min_value=20,
                    max_value=85,
                    value=int(
                        (mot_prev.eficiencia_ventilador if mot_prev is not None else 0.55) * 100
                    ),
                    step=5,
                    help="Axial simple: 45–60%. Centrífugo media presión: 60–75%.",
                )
                / 100.0
            )
        with c2:
            eta_motor_val = (
                st.slider(
                    "η motor eléctrico [%]",
                    min_value=50,
                    max_value=97,
                    value=int((mot_prev.eficiencia_motor if mot_prev is not None else 0.85) * 100),
                    step=5,
                    help="Motores < 1 kW: 75–85%.",
                )
                / 100.0
            )
        with c3:
            fs = st.number_input(
                "Factor de servicio [-]",
                min_value=1.0,
                max_value=2.0,
                value=mot_prev.factor_servicio if mot_prev is not None else 1.15,
                step=0.05,
                format="%.2f",
                help="Sobredimensionamiento del motor. Estándar NEMA continuo: 1.15.",
            )

        tension_val: float | None = None
        if tipo == TipoAccionamiento.MOTOR_ELECTRICO:
            usar_tension = st.checkbox(
                "Especificar tensión de alimentación",
                value=mot_prev is not None and mot_prev.tension_V is not None,
                key="motor_usar_tension",
            )
            if usar_tension:
                tension_val = float(
                    st.selectbox(
                        "Tensión [V]",
                        options=[220, 380],
                        index=0 if (mot_prev is None or mot_prev.tension_V != 380.0) else 1,
                    )
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
                delta_P_singulares_Pa=dP_singulares_val,
                v_descarga_m_s=(
                    st.session_state.get("p6_v_ducto", 6.0) if dP_total_override is None else None
                ),
                eficiencia_ventilador=eta_vent,
                eficiencia_motor=eta_motor_val,
                factor_servicio=fs,
                tension_V=tension_val,
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
            f"{motor.potencia_hidraulica_W:.1f} W" if motor.potencia_hidraulica_W else "—",
            help="Q × ΔP",
        )
        c3.metric(
            "P eléctrica",
            f"{motor.potencia_electrica_W:.1f} W" if motor.potencia_electrica_W else "—",
            help=f"P_hid / (η_vent={eta_vent:.0%} × η_motor={eta_motor_val:.0%})",
        )
        c4.metric(
            "P a instalar",
            f"{motor.potencia_a_instalar_W:.1f} W" if motor.potencia_a_instalar_W else "—",
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
                st.write("**Tipo:** Motor eléctrico")
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

    # --- Guardar configuración ---
    if proyecto.motor is not None:
        st.divider()
        from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

        col_txt, col_json = st.columns(2)
        with col_txt:
            st.download_button(
                "Guardar configuración del motor (.txt)",
                data=_texto_config_motor(proyecto.motor),
                file_name=nombre_archivo_descarga(proyecto, "motor", "txt"),
                mime="text/plain",
                width="stretch",
            )
        with col_json:
            st.download_button(
                "Guardar configuración del motor (.json)",
                data=dump_json(_json_config_motor(proyecto.motor)),
                file_name=nombre_archivo_descarga(proyecto, "motor", "json"),
                mime="application/json",
                width="stretch",
            )
