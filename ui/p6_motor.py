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

from calculos.catalogo_rugosidades import id_desde_z0
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
from core.chimenea import Chimenea, advertencias_chimenea
from core.motor import Motor, TipoAccionamiento
from ui.componentes.advertencias_widget import render_advertencias
from ui.componentes.idiomas import t, t_catalogo
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_T_MEDIA_DEFAULT_K: float = 323.15  # 50 °C — temperatura media del sistema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia traducida por código (widget único, F5)."""
    render_advertencias(adv_list, con_sugerencia=False)


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
            "  Tensión            : "
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


def _delta_P_bocas_forzado(
    proyecto, Q_vol_m3_s: float, P_Pa: float
) -> tuple[float, dict[str, float]]:
    """ΔP de las bocas de la cámara en el circuito **forzado** (S61).

    Con ventilador las bocas no cambian el caudal —lo impone el ventilador—
    pero sí la **presión que tiene que entregar**, y con ella la potencia
    eléctrica. Es el mismo dato de dimensionamiento que en convección natural,
    solo que el efecto sale por otro lado.

    Devuelve además los ``K`` que hay que **anular** en
    ``motor_calc.estimar_delta_P_singulares``: sus términos de entrada, salida y
    difusor son las mismas transiciones, estimadas sobre la velocidad del ducto
    —es decir, suponiendo una boca del tamaño del ducto—. Cuando el usuario
    carga las áreas reales, esas áreas mandan y los genéricos se apagan.

    Args:
        proyecto: Proyecto con cámara.
        Q_vol_m3_s: Caudal volumétrico del sistema [m³/s].
        P_Pa: Presión del sitio [Pa].

    Returns:
        ``(ΔP_bocas [Pa], overrides de K para estimar_delta_P_singulares)``.
        Sin bocas definidas: ``(0.0, {})`` — cadena de singulares intacta.
    """
    if proyecto is None or proyecto.camara is None or not proyecto.camara.flujo.bocas_definidas:
        return (0.0, {})
    from calculos.chimenea_calc import coeficientes_bocas, delta_P_bocas_Pa
    from calculos.motor_calc import densidad_aire

    f = proyecto.camara.flujo
    K_in, K_out = coeficientes_bocas(proyecto.colector is not None, proyecto.chimenea is not None)
    rho = densidad_aire(_T_MEDIA_DEFAULT_K, P_Pa)
    dP = delta_P_bocas_Pa(
        Q_vol_m3_s * rho,
        f.area_entrada_aire_m2,
        f.area_salida_aire_m2,
        _T_MEDIA_DEFAULT_K,
        P_Pa,
        K_in=K_in,
        K_out=K_out,
    )
    return (dP, {"K_entrada": 0.0, "K_salida": 0.0, "K_difusor": 0.0})


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
            return T_amb_K, v_viento, t("p6.condiciones.media_anual")
        except Exception:
            pass
    return 293.15, 2.0, t("p6.condiciones.fallback")


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
        st.warning(t("p6.chimenea.calcular.falta_camara"))
        return

    es_caja = getattr(getattr(proyecto, "configuracion", None), "tipologia", None) == Tipologia.CAJA
    delta_T_chim_K = 25.0 if es_caja else 30.0

    if st.button(t("p6.chimenea.calcular.boton"), type="primary", key="p6_btn_calc_chimenea"):
        from calculos.balance_global import (
            _caudal_natural_loop,
            presion_representativa_proyecto,
        )

        T_amb_K, v_viento_ms, origen_clima = _condiciones_representativas_chimenea(proyecto)
        T_chim_K = T_amb_K + delta_T_chim_K
        P_proyecto_Pa, P_origen = presion_representativa_proyecto(proyecto)

        try:
            with st.spinner(t("p6.chimenea.calcular.spinner")):
                res_chim = _caudal_natural_loop(
                    proyecto=proyecto,
                    T_amb_K=T_amb_K,
                    T_chim_K=T_chim_K,
                    m_design_kgs=proyecto.camara.flujo.caudal_masico_kg_s,
                    P_amb_Pa=P_proyecto_Pa,
                    v_viento_ms=v_viento_ms,
                )
        except Exception as exc:
            st.error(t("p6.chimenea.calcular.error_calculo", exc=exc))
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
        st.caption(t("p6.chimenea.calcular.prompt"))
        return

    res = ev["resultado"]
    st.subheader(t("p6.chimenea.calcular.titulo"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        t("p6.chimenea.calcular.caudal_natural.label"),
        f"{res['m_punto_kgs'] * 1000:.2f} g/s",
        help=t("p6.chimenea.calcular.caudal_natural.help"),
    )
    c2.metric(
        t("p6.chimenea.calcular.v_chim.label"),
        f"{res['v_chim_ms']:.2f} m/s",
        help=t("p6.chimenea.calcular.v_chim.help"),
    )
    c3.metric(
        t("p6.chimenea.calcular.re.label"),
        f"{res['Re_chimenea']:.0f}",
        help=t("p6.chimenea.calcular.re.help"),
    )
    c4.metric(
        t("p6.chimenea.calcular.dp_tiro.label"),
        f"{res['delta_P_tiro_Pa']:.2f} Pa",
        help=t("p6.chimenea.calcular.dp_tiro.help"),
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric(
        t("p6.chimenea.calcular.dp_ducto.label"),
        f"{res['delta_P_chimenea_Pa']:.2f} Pa",
        help=t("p6.chimenea.calcular.dp_ducto.help"),
    )
    c6.metric(
        t("p6.chimenea.calcular.dp_resto.label"),
        f"{res['delta_P_resto_Pa']:.2f} Pa",
        help=t("p6.chimenea.calcular.dp_resto.help"),
    )
    dP_turb = float(res.get("delta_P_turbina_motriz_Pa", 0.0))
    if dP_turb > 0.0:
        c7.metric(
            t("p6.chimenea.calcular.dp_turbina.label"),
            f"{dP_turb:.2f} Pa",
            help=t("p6.chimenea.calcular.dp_turbina.help", v=res.get("v_viento_local_ms", 0.0)),
        )
    c8.metric(t("p6.chimenea.calcular.h_eff"), f"{res['H_eff_m']:.2f} m")

    advs = res.get("advertencias", []) or []
    if advs:
        with st.expander(t("p6.chimenea.calcular.advertencias", n=len(advs))):
            for a in advs:
                st.warning(a)  # i18n: exento (mensaje de calculos/, queda ES)

    st.caption(
        t(
            "p6.chimenea.calcular.inputs",
            t_amb=ev["T_amb_K"] - 273.15,
            t_chim=ev["T_chim_K"] - 273.15,
            dt=ev["delta_T_chim_K"],
            tipo=(
                t("p6.chimenea.calcular.tipo_caja")
                if ev["es_caja"]
                else t("p6.chimenea.calcular.tipo_otro")
            ),
            v=ev["v_viento_ms"],
            p=ev["P_amb_Pa"] / 1000,
            clima=ev["origen_clima"],
            presion=ev["P_origen"],
        )
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
    st.subheader(t("p6.chimenea.titulo"))

    # --- Cargar configuración guardada ---
    with st.expander(t("p6.chimenea.cargar.titulo"), expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            t("p6.chimenea.cargar.uploader"),
            type=["json"],
            key="p6_chim_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "chimenea")
            if err:
                st.error(f"❌ {err}")  # i18n: exento (mensaje de serializacion, F4)
            else:
                try:
                    ch_cargada = _from_json_chimenea(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(t("p6.chimenea.cargar.error_reconstruccion", exc=exc))
                else:
                    proyecto.chimenea = ch_cargada
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p6_chim_")
                    st.session_state.pop("p6_chim_cargar_json", None)
                    st.success(t("p6.chimenea.cargar.exito", n=n_borr))
                    st.rerun()

    usar_chimenea = st.toggle(
        t("p6.chimenea.usar.label"),
        value=proyecto.chimenea is not None,
        key="p6_usar_chimenea",
        help=t("p6.chimenea.usar.help"),
    )

    if not usar_chimenea:
        proyecto.chimenea = None
        st.session_state.pop("p6_chimenea_eval", None)
        st.caption(t("p6.chimenea.sin_chimenea"))
        return

    ch_ref = proyecto.chimenea or Chimenea()
    c1, c2, c3 = st.columns(3)
    with c1:
        diam = st.number_input(
            t("p6.chimenea.diametro"),
            min_value=0.05,
            max_value=2.0,
            value=float(ch_ref.diametro_m),
            step=0.01,
            format="%.2f",
            key="p6_chim_diam",
        )
    with c2:
        alt = st.number_input(
            t("p6.chimenea.altura"),
            min_value=0.1,
            max_value=20.0,
            value=float(ch_ref.altura_m),
            step=0.1,
            format="%.1f",
            key="p6_chim_altura",
        )
    with c3:
        opciones = {
            id_mat: t_catalogo(datos, default=id_mat) for id_mat, datos in catalogo.FONDOS.items()
        }
        ids = list(opciones.keys())
        idx = ids.index(ch_ref.id_material) if ch_ref.id_material in ids else 0
        mat = st.selectbox(
            t("p6.chimenea.material"),
            options=ids,
            index=idx,
            format_func=lambda x: opciones[x],
            key="p6_chim_material",
        )

    # --- Extractor eólico (turbina sombrero chino) -------------------------
    ch_ref_ext = proyecto.chimenea
    extractor_prev = bool(ch_ref_ext.extractor_activo) if ch_ref_ext else False

    extractor_activo = st.checkbox(
        t("p6.chimenea.extractor.check"),
        value=extractor_prev,
        key="p6_chim_ext_activo",
        help=t("p6.chimenea.extractor.check_help"),
    )

    diam_ext_val: float | None = None
    Cp_val: float = 0.4
    Kt_val: float = 1.0
    z0_val: float = 0.05

    if extractor_activo:
        with st.expander(t("p6.chimenea.extractor.titulo"), expanded=False):
            ec1, ec2 = st.columns(2)
            with ec1:
                diam_ext_default = (
                    float(ch_ref_ext.diametro_extractor_m)
                    if (ch_ref_ext and ch_ref_ext.diametro_extractor_m is not None)
                    else max(diam, 0.30)
                )
                diam_ext_val = st.number_input(
                    t("p6.chimenea.extractor.diam.label"),
                    min_value=0.10,
                    max_value=2.0,
                    value=diam_ext_default,
                    step=0.05,
                    format="%.2f",
                    key="p6_chim_ext_diam",
                    help=t("p6.chimenea.extractor.diam.help"),
                )
            with ec2:
                Cp_val = st.number_input(
                    t("p6.chimenea.extractor.cp.label"),
                    min_value=0.05,
                    max_value=2.0,
                    value=float(ch_ref_ext.Cp_turbina) if ch_ref_ext else 0.4,
                    step=0.05,
                    format="%.2f",
                    key="p6_chim_ext_Cp",
                    help=t("p6.chimenea.extractor.cp.help"),
                )
            ec3, ec4 = st.columns(2)
            with ec3:
                Kt_val = st.number_input(
                    t("p6.chimenea.extractor.kt.label"),
                    min_value=0.0,
                    max_value=5.0,
                    value=float(ch_ref_ext.Kt_turbina) if ch_ref_ext else 1.0,
                    step=0.1,
                    format="%.2f",
                    key="p6_chim_ext_Kt",
                    help=t("p6.chimenea.extractor.kt.help"),
                )
            with ec4:
                # z0 es propiedad del sitio y vive en `Emplazamiento` desde S57
                # (antes había acá un selector propio, desacoplado del que usaba
                # la ingesta de clima medido). Acá solo se muestra, en solo
                # lectura: se edita en P2 → Ubicación.
                z0_val = float(proyecto.emplazamiento.z0_terreno_m)
                st.metric(
                    t("p6.chimenea.extractor.z0.label"),
                    f"{z0_val:.3f} m",
                    help=t("p6.chimenea.extractor.z0.help"),
                )
                st.caption(
                    t(
                        "p6.chimenea.extractor.z0.origen",
                        terreno=t(f"comun.rugosidad.{id_desde_z0(z0_val)}"),
                    )
                )

            # Preview: viento corregido a la altura del tope. `WS_ms` está a la
            # altura del contrato de Clima (2 m), no a los 10 m meteorológicos.
            v_viento_ref: float | None = None
            try:
                if (
                    proyecto.clima is not None
                    and proyecto.clima.datos is not None
                    and "WS_ms" in proyecto.clima.datos.columns
                ):
                    v_viento_ref = float(proyecto.clima.datos["WS_ms"].mean())
            except (AttributeError, KeyError):
                v_viento_ref = None

            H_cam_default = 1.5
            if proyecto.camara is not None:
                try:
                    H_cam_default = float(proyecto.camara.geometria.alto_m)
                except (AttributeError, TypeError):
                    pass
            z_tope = H_cam_default + alt
            if v_viento_ref is not None:
                v_loc = _v_viento_a_altura(v_viento_ref, z_tope, z0_val)
                dP_turb = delta_P_turbina_motriz_Pa(
                    v_loc, Cp_val, T_amb_K=293.15, P_amb_Pa=P_proyecto_Pa
                )
                st.caption(
                    t(
                        "p6.chimenea.extractor.preview_viento",
                        vref=v_viento_ref,
                        z=z_tope,
                        vloc=v_loc,
                        dp=dP_turb,
                    )
                )
            else:
                st.caption(t("p6.chimenea.extractor.preview_sin_clima"))

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
        st.error(t("p6.chimenea.error_validacion", err=err))
        return
    proyecto.chimenea = nueva

    # --- Advertencias ---
    adv_list = advertencias_chimenea(nueva)
    if adv_list:
        for a in adv_list:
            _mostrar_advertencias([a])

    # --- Preview de tiro térmico ---
    st.markdown(t("p6.chimenea.tiro.titulo"))
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
        col_w.metric(t("p6.chimenea.tiro.metric_dt", dt=dT), f"{dP:.2f} Pa")
    st.caption(
        t(
            "p6.chimenea.tiro.caption",
            alt=nueva.altura_m,
            hcam=H_camara_default,
            heff=H_eff,
        )
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
            t("p6.chimenea.guardar.txt"),
            data=_texto_config_chimenea(nueva),
            file_name=nombre_archivo_descarga(proyecto, "chimenea", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            t("p6.chimenea.guardar.json"),
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
    st.header(t("p6.header"))
    boton_manual(SLUG_POR_SECCION["p6"])

    st.caption(t("p6.intro"))

    proyecto = st.session_state.proyecto

    # Presión atmosférica representativa del emplazamiento (corregida por
    # altitud). Se propaga a estimar_delta_P_* y al preview de chimenea.
    from calculos.balance_global import presion_representativa_proyecto

    P_proyecto_Pa, _P_origen = presion_representativa_proyecto(proyecto)

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander(t("p6.cargar.titulo"), expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            t("p6.cargar.uploader"),
            type=["json"],
            key="p6_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "motor")
            if err:
                st.error(f"❌ {err}")  # i18n: exento (mensaje de serializacion, F4)
            else:
                try:
                    mot_cargado, chim_migrada, aviso_migracion = _from_json_motor(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(t("p6.cargar.error_reconstruccion", exc=exc))
                else:
                    proyecto.motor = mot_cargado
                    if chim_migrada is not None:
                        proyecto.chimenea = chim_migrada
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p6_")
                    st.session_state.pop("p6_cargar_json", None)
                    if aviso_migracion:
                        st.warning(
                            f"⚠️ {aviso_migracion}"
                        )  # i18n: exento (aviso de _from_json_motor, ES)
                    st.success(t("p6.cargar.exito", n=n_borr))
                    st.rerun()

    # -----------------------------------------------------------------------
    # Toggle: ¿usar motor?
    # -----------------------------------------------------------------------
    usar_motor = st.toggle(
        t("p6.usar.label"),
        value=proyecto.motor is not None,
        help=t("p6.usar.help"),
    )

    if not usar_motor:
        proyecto.motor = None
        st.info(t("p6.usar.sin_motor"))
        _render_chimenea_section(proyecto)
        return

    mot_prev = proyecto.motor

    # -----------------------------------------------------------------------
    # Sección A: Tipo de accionamiento
    # -----------------------------------------------------------------------
    st.subheader(t("p6.accionamiento.titulo"))

    # Sólo queda un tipo de motor: eléctrico. El extractor eólico se modela
    # como accesorio de la chimenea, no como tipo de motor (ver P6 sección
    # de chimenea cuando motor=None).
    tipo = TipoAccionamiento.MOTOR_ELECTRICO
    st.caption(t("p6.accionamiento.caption"))

    # -----------------------------------------------------------------------
    # Sección B: Caudal volumétrico
    # -----------------------------------------------------------------------
    with st.expander(t("p6.caudal.titulo"), expanded=False):
        Q_vol_sugerido = mot_prev.caudal_volumetrico_m3_s if mot_prev is not None else 0.020
        hint_caudal = ""

        if proyecto.colector is not None:
            Q_col = proyecto.colector.caudal_total_m3_s()
            Q_vol_sugerido = Q_col
            hint_caudal = t("p6.caudal.hint_colector", q=Q_col * 1000)

        if proyecto.camara is not None:
            Q_vol_cam = caudal_masico_a_volumetrico(
                proyecto.camara.flujo.caudal_masico_kg_s,
                _T_MEDIA_DEFAULT_K,
                P_proyecto_Pa,
            )
            Q_vol_sugerido = Q_vol_cam
            hint_caudal = t(
                "p6.caudal.hint_camara",
                g=proyecto.camara.flujo.caudal_masico_kg_s * 1000,
                l=Q_vol_cam * 1000,
            )

        c1, c2 = st.columns(2)
        with c1:
            Q_vol_ls = st.number_input(
                t("p6.caudal.label"),
                min_value=0.1,
                max_value=10000.0,
                value=round(Q_vol_sugerido * 1000.0, 1),
                step=0.5,
                format="%.1f",
                help=hint_caudal or t("p6.caudal.help_default"),
            )
            Q_vol_m3s = Q_vol_ls / 1000.0
        with c2:
            if hint_caudal:
                st.info(f"💡 {hint_caudal}")  # i18n: exento (hint_caudal ya traducido)
            _q_m3s_help = f"{Q_vol_m3s:.5f} m³/s"  # solo unidad, no se traduce
            st.metric(t("p6.caudal.metric"), f"{Q_vol_ls:.1f} L/s", help=_q_m3s_help)

    # -----------------------------------------------------------------------
    # Sección C: Pérdidas de carga
    # -----------------------------------------------------------------------
    with st.expander(t("p6.perdidas.titulo"), expanded=False):

        modo_dP = st.radio(
            t("p6.perdidas.modo.label"),
            options=["componentes", "total"],
            horizontal=True,
            format_func=lambda k: t(f"p6.perdidas.modo.{k}"),
            help=t("p6.perdidas.modo.help"),
        )

        dP_total_override: float | None = None
        dP_colector_val: float | None = None
        dP_camara_val: float | None = None
        dP_ductos_val: float | None = None
        dP_singulares_val: float | None = None

        if modo_dP == "total":
            dP_total_override = st.number_input(
                t("p6.perdidas.total.label"),
                min_value=1.0,
                max_value=100000.0,
                value=float(
                    mot_prev.perdida_carga_total_Pa
                    if (mot_prev is not None and mot_prev.perdida_carga_total_Pa)
                    else 50.0
                ),
                step=1.0,
                format="%.1f",
                help=t("p6.perdidas.total.help"),
            )

        else:
            c1, c2, c3 = st.columns(3)

            # ΔP colector
            dP_col_auto: float | None = None
            if proyecto.colector is not None:
                try:
                    dP_col_auto = estimar_delta_P_colector(proyecto.colector, P_Pa=P_proyecto_Pa)
                except Exception:
                    pass

            dP_col_default = float(
                mot_prev.delta_P_colector_Pa
                if (mot_prev is not None and mot_prev.delta_P_colector_Pa is not None)
                else (dP_col_auto or 20.0)
            )
            with c1:
                dP_col_input = st.number_input(
                    t("p6.perdidas.colector.label"),
                    min_value=0.0,
                    max_value=50000.0,
                    value=dP_col_default,
                    step=1.0,
                    format="%.1f",
                    help=(
                        t("p6.perdidas.colector.help_auto", v=dP_col_auto)
                        if dP_col_auto is not None
                        else t("p6.perdidas.colector.help_sin")
                    ),
                )
                dP_colector_val = dP_col_input if dP_col_input > 0 else None
                if dP_col_auto is not None:
                    st.caption(t("p6.perdidas.colector.auto_caption", v=dP_col_auto))

            # ΔP cámara
            dP_cam_auto: float | None = None
            if proyecto.camara is not None:
                try:
                    dP_cam_auto = estimar_delta_P_camara(proyecto.camara, P_Pa=P_proyecto_Pa)
                except Exception:
                    pass

            dP_cam_default = float(
                mot_prev.delta_P_camara_Pa
                if (mot_prev is not None and mot_prev.delta_P_camara_Pa is not None)
                else (dP_cam_auto or 10.0)
            )
            with c2:
                dP_cam_input = st.number_input(
                    t("p6.perdidas.camara.label"),
                    min_value=0.0,
                    max_value=50000.0,
                    value=dP_cam_default,
                    step=1.0,
                    format="%.1f",
                    help=(
                        t("p6.perdidas.camara.help_auto", v=dP_cam_auto)
                        if dP_cam_auto is not None
                        else t("p6.perdidas.camara.help_sin")
                    ),
                )
                dP_camara_val = dP_cam_input if dP_cam_input > 0 else None
                if dP_cam_auto is not None:
                    st.caption(t("p6.perdidas.camara.auto_caption", v=dP_cam_auto))

            # ΔP ductos
            with c3:
                usar_ductos_manual = st.checkbox(
                    t("p6.perdidas.ductos.check"),
                    value=(mot_prev is not None and mot_prev.delta_P_ductos_Pa is not None),
                )
                if usar_ductos_manual:
                    dP_duc_input = st.number_input(
                        t("p6.perdidas.ductos.label"),
                        min_value=0.0,
                        max_value=10000.0,
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
                    st.caption(t("p6.perdidas.ductos.auto_caption", v=dP_duc_est))

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
            # Bocas de la cámara: cuando el usuario carga sus áreas, las
            # transiciones de entrada/salida se calculan sobre el área REAL y
            # reemplazan a los términos genéricos de `estimar_delta_P_singulares`
            # (que las estimaba sobre la velocidad del ducto, o sea suponiendo
            # una boca del tamaño del ducto). Sumar ambos sería contar dos veces
            # la misma transición.
            dP_bocas_val, K_bocas_sing = _delta_P_bocas_forzado(proyecto, Q_vol_m3s, P_proyecto_Pa)
            sing = estimar_delta_P_singulares(
                Q_vol_m3_s=Q_vol_m3s,
                v_ducto_m_s=v_ducto,
                n_paralelo=n_paralelo,
                n_codos=2,
                P_Pa=P_proyecto_Pa,
                **K_bocas_sing,
            )
            dP_singulares_val = sing["total"] + dP_bocas_val
            with st.expander(
                t("p6.perdidas.singulares.titulo", v=dP_singulares_val),
                expanded=False,
            ):
                v_ducto_input = st.number_input(
                    t("p6.perdidas.singulares.v_label"),
                    min_value=1.0,
                    max_value=20.0,
                    value=v_ducto,
                    step=0.5,
                    format="%.1f",
                    help=t("p6.perdidas.singulares.v_help"),
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
                        **K_bocas_sing,
                    )
                    dP_singulares_val = sing["total"] + dP_bocas_val
                    v_ducto = v_ducto_input
                st.caption(
                    t(
                        "p6.perdidas.singulares.detalle",
                        n_par=n_paralelo,
                        entrada=sing["entrada"],
                        salida=sing["salida"],
                        codos=sing["codos"],
                        manifold=sing["manifold"],
                        difusor=sing["difusor"],
                    )
                )
                if dP_bocas_val > 0:
                    f_bocas = proyecto.camara.flujo
                    st.caption(
                        t(
                            "p6.perdidas.singulares.bocas",
                            dp=dP_bocas_val,
                            a_in=f_bocas.area_entrada_aire_m2,
                            a_out=f_bocas.area_salida_aire_m2,
                        )
                    )

            dP_ductos_efectivo = (
                dP_ductos_val if dP_ductos_val is not None else 0.20 * (dP_col_input + dP_cam_input)
            )

            # Caño maestro (manifold del banco, gran escala): su ΔP es lo que el
            # ventilador ve aguas arriba de las ramas. Se suma a ductos de forma
            # explícita para que entre al total del Motor (que con ductos=None
            # usaría solo el 20% heurístico).
            dP_cano = 0.0
            if proyecto.colector is not None and proyecto.colector.banco.cano_maestro is not None:
                from calculos.cano_maestro_calc import estimar_delta_P_cano_maestro

                dP_cano = estimar_delta_P_cano_maestro(
                    proyecto.colector.banco.cano_maestro,
                    Q_vol_m3s,
                    T_K=_T_MEDIA_DEFAULT_K,
                    P_Pa=P_proyecto_Pa,
                )["total"]
            if dP_cano > 0:
                dP_ductos_efectivo += dP_cano
                dP_ductos_val = dP_ductos_efectivo  # explícito → entra al total del Motor

            dP_tot_preview = dP_col_input + dP_cam_input + dP_ductos_efectivo + dP_singulares_val
            st.caption(
                t(
                    "p6.perdidas.total_preview",
                    total=dP_tot_preview,
                    col=dP_col_input,
                    cam=dP_cam_input,
                    duc=dP_ductos_efectivo,
                    sing=dP_singulares_val,
                )
            )
            if dP_cano > 0:
                st.caption(t("p6.perdidas.cano_caption", v=dP_cano))

    # -----------------------------------------------------------------------
    # Sección D: Parámetros del ventilador / motor
    # -----------------------------------------------------------------------
    with st.expander(t("p6.ventilador.titulo"), expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            eta_vent = (
                st.slider(
                    t("p6.ventilador.eta_vent.label"),
                    min_value=20,
                    max_value=85,
                    value=int(
                        (mot_prev.eficiencia_ventilador if mot_prev is not None else 0.55) * 100
                    ),
                    step=5,
                    help=t("p6.ventilador.eta_vent.help"),
                )
                / 100.0
            )
        with c2:
            eta_motor_val = (
                st.slider(
                    t("p6.ventilador.eta_motor.label"),
                    min_value=50,
                    max_value=97,
                    value=int((mot_prev.eficiencia_motor if mot_prev is not None else 0.85) * 100),
                    step=5,
                    help=t("p6.ventilador.eta_motor.help"),
                )
                / 100.0
            )
        with c3:
            fs = st.number_input(
                t("p6.ventilador.fs.label"),
                min_value=1.0,
                max_value=2.0,
                value=mot_prev.factor_servicio if mot_prev is not None else 1.15,
                step=0.05,
                format="%.2f",
                help=t("p6.ventilador.fs.help"),
            )

        tension_val: float | None = None
        if tipo == TipoAccionamiento.MOTOR_ELECTRICO:
            usar_tension = st.checkbox(
                t("p6.ventilador.usar_tension"),
                value=mot_prev is not None and mot_prev.tension_V is not None,
                key="motor_usar_tension",
            )
            if usar_tension:
                tension_val = float(
                    st.selectbox(
                        t("p6.ventilador.tension"),
                        options=[220, 380],
                        index=0 if (mot_prev is None or mot_prev.tension_V != 380.0) else 1,
                    )
                )

    # -----------------------------------------------------------------------
    # Botón: calcular
    # -----------------------------------------------------------------------
    st.divider()
    if st.button(t("p6.calcular"), type="primary"):
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
            st.error(t("p6.error_config", exc=exc))
            return

        if motor.advertencias:
            st.subheader(t("p6.advertencias_titulo"))
            _mostrar_advertencias(motor.advertencias)
        else:
            st.success(t("p6.sin_advertencias"))

        # Resultados
        st.subheader(t("p6.resultados.titulo"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("p6.resultados.dp_total"), f"{motor.perdida_carga_total_Pa:.1f} Pa")
        c2.metric(
            t("p6.resultados.p_hidraulica.label"),
            f"{motor.potencia_hidraulica_W:.1f} W" if motor.potencia_hidraulica_W else "—",
            help=t("p6.resultados.p_hidraulica.help"),
        )
        c3.metric(
            t("p6.resultados.p_electrica.label"),
            f"{motor.potencia_electrica_W:.1f} W" if motor.potencia_electrica_W else "—",
            help=t("p6.resultados.p_electrica.help", eta_vent=eta_vent, eta_motor=eta_motor_val),
        )
        c4.metric(
            t("p6.resultados.p_instalar.label"),
            f"{motor.potencia_a_instalar_W:.1f} W" if motor.potencia_a_instalar_W else "—",
            help=t("p6.resultados.p_instalar.help", fs=fs),
        )

        if motor.corriente_nominal_A is not None:
            st.info(
                t(
                    "p6.resultados.corriente",
                    i=motor.corriente_nominal_A,
                    v=int(motor.tension_V),
                )
            )

        with st.expander(t("p6.resumen.titulo")):
            c1, c2 = st.columns(2)
            with c1:
                st.write(t("p6.resumen.tipo"))
                st.write(t("p6.resumen.caudal", v=Q_vol_ls))
                st.write(t("p6.resumen.dp_total", v=motor.perdida_carga_total_Pa))
                st.write(t("p6.resumen.eta_vent", v=eta_vent))
                st.write(t("p6.resumen.eta_motor", v=eta_motor_val))
                st.write(t("p6.resumen.fs", v=fs))
            with c2:
                if motor.potencia_hidraulica_W:
                    st.write(t("p6.resumen.p_hidraulica", v=motor.potencia_hidraulica_W))
                if motor.potencia_eje_W:
                    st.write(t("p6.resumen.p_eje", v=motor.potencia_eje_W))
                if motor.potencia_electrica_W:
                    st.write(t("p6.resumen.p_electrica", v=motor.potencia_electrica_W))
                if motor.potencia_a_instalar_W:
                    st.write(t("p6.resumen.p_instalar", v=motor.potencia_a_instalar_W))
                if motor.corriente_nominal_A:
                    st.write(t("p6.resumen.corriente", v=motor.corriente_nominal_A))

    # --- Guardar configuración ---
    if proyecto.motor is not None:
        st.divider()
        from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

        col_txt, col_json = st.columns(2)
        with col_txt:
            st.download_button(
                t("p6.guardar.txt"),
                data=_texto_config_motor(proyecto.motor),
                file_name=nombre_archivo_descarga(proyecto, "motor", "txt"),
                mime="text/plain",
                width="stretch",
            )
        with col_json:
            st.download_button(
                t("p6.guardar.json"),
                data=dump_json(_json_config_motor(proyecto.motor)),
                file_name=nombre_archivo_descarga(proyecto, "motor", "json"),
                mime="application/json",
                width="stretch",
            )
