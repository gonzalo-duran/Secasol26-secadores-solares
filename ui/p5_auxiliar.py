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
from core.auxiliar import (
    Auxiliar,
    CargaArranque,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
    advertencias_auxiliar,
)
from ui.componentes.advertencias_widget import render_advertencias
from ui.componentes.idiomas import t
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_T_SALIDA_DEFAULT_C: float = 60.0
_T_AMB_DEFAULT_C: float = 25.0
_T_MAX_DEFAULT_C: float = 70.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia traducida por código (widget único, F5)."""
    render_advertencias(adv_list, con_sugerencia=False)


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
            f"  PCI                : " + (f"{aux.PCI_MJ_kg:.2f} MJ/kg" if aux.PCI_MJ_kg else "—"),
            f"  η quemador         : "
            + (f"{aux.eficiencia_quemador:.1%}" if aux.eficiencia_quemador else "—"),
            f"  Consumo nominal    : "
            + (
                f"{aux.consumo_biomasa_kg_h:.3f} kg/h"
                if aux.consumo_biomasa_kg_h
                else "(calculado por PCI)"
            ),
            f"  Consumo efectivo   : " + (f"{consumo:.3f} kg/h" if consumo is not None else "—"),
        ]
    elif aux.tipo == TipoAuxiliar.RESISTENCIA_ELECTRICA:
        lines += [
            "",
            "RESISTENCIA ELÉCTRICA",
            f"  Tensión            : "
            + (f"{aux.tension_V:.0f} V" if aux.tension_V else "(no especificada)"),
            f"  Corriente máx.     : "
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
    consumo_override_val: float | None = None
    tension_val: float | None = None
    corriente_val: float | None = None

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
        # Sección D: Condiciones de operación y resultados
        # -----------------------------------------------------------------------
        st.subheader(t("p5.efecto.titulo"))

        col_op1, col_op2 = st.columns(2)
        with col_op1:
            T_entrada_hint = (
                t("p5.efecto.t_entrada.hint_serie")
                if modo == ModoOperacionAuxiliar.SERIE_POSCOLECTOR
                else t("p5.efecto.t_entrada.hint_respaldo")
            )
            T_entrada_C = st.number_input(
                t("p5.efecto.t_entrada.label"),
                min_value=-10.0,
                max_value=120.0,
                value=st.session_state.get("aux_T_entrada_C", _T_SALIDA_DEFAULT_C),
                step=1.0,
                format="%.1f",
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
                caudal_hint = t("p5.efecto.caudal.hint_colector", q=Q_m3s * 1000, kg=caudal_default)
            if proyecto.camara is not None:
                caudal_default = proyecto.camara.flujo.caudal_masico_kg_s
                caudal_hint = t("p5.efecto.caudal.hint_camara")

            caudal_kg_s = st.number_input(
                t("p5.efecto.caudal.label"),
                min_value=0.001,
                max_value=10.0,
                value=caudal_default,
                step=0.001,
                format="%.4f",
                help=caudal_hint or t("p5.efecto.caudal.hint_default"),
            )
            if caudal_hint:
                st.caption(f"💡 {caudal_hint}")  # i18n: exento (caudal_hint ya traducido)

        T_entrada_K = celsius_a_kelvin(T_entrada_C)
        try:
            res = calcular_auxiliar(auxiliar, T_entrada_K, caudal_kg_s)
        except Exception as exc:
            st.error(t("p5.efecto.error_calculo", exc=exc))
            return

        if res.advertencias:
            for msg in res.advertencias:
                st.warning(f"⚠️ {msg}")  # i18n: exento (mensaje de calculos/, queda ES)

        # Métricas de resultado
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric(
            t("p5.efecto.t_entrada_metric"),
            f"{kelvin_a_celsius(res.T_entrada_K):.1f} °C",
        )
        col_r2.metric(
            t("p5.efecto.t_salida"),
            f"{kelvin_a_celsius(res.T_salida_K):.1f} °C",
            delta=f"+{res.delta_T_K:.1f} °C",
        )
        col_r3.metric(
            t("p5.efecto.potencia_efectiva.label"),
            f"{res.Q_efectivo_W / 1000:.2f} kW",
            help=t("p5.efecto.potencia_efectiva.help", frac=res.fraccion_activa),
        )
        if res.consumo_biomasa_kg_h is not None:
            col_r4.metric(
                t("p5.efecto.consumo_biomasa.label"),
                f"{res.consumo_biomasa_kg_h:.3f} kg/h",
                help=t("p5.efecto.consumo_biomasa.help"),
            )
        elif res.consumo_electrico_W is not None:
            col_r4.metric(
                t("p5.efecto.consumo_electrico"),
                f"{res.consumo_electrico_W / 1000:.2f} kW",
            )

        if res.set_point_activo:
            st.info(
                t(
                    "p5.efecto.set_point_activo",
                    frac=res.fraccion_activa,
                    t_salida=kelvin_a_celsius(res.T_salida_K),
                )
            )

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
