"""
Pestaña 1 — Tipología y Configuración del Análisis.

Permite al usuario:
    - Definir los metadatos del proyecto (nombre, autor, notas).
    - Seleccionar la tipología del secador (CAJA, ARMARIO, GRAN_ESCALA).
    - Configurar el tipo de análisis (DIARIO o ANUAL) y el criterio de día.

Los cambios se aplican de inmediato a st.session_state.proyecto.
Si la tipología cambia a CAJA, colector y motor se anulan automáticamente
(la tipología CAJA no admite colector externo ni motor).

i18n (F1): todos los textos visibles pasan por ``t()`` con claves ``p1.*``
(ver ``ui/idiomas/``). Los widgets de opciones usan como options los enums
(valores estables) + ``format_func`` — nunca el rótulo traducido como valor.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from calculos.clima_medido import meses_cubiertos
from core.clima import ANIO_NASA_MAX, ANIO_NASA_MIN
from core.proyecto import (
    Configuracion,
    DiaAnalisis,
    Meta,
    ModoAnalisis,
    SubtipoGranEscala,
    Tipologia,
)
from ui.componentes.esquemas import mostrar_esquema
from ui.componentes.idiomas import t
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual

# Paso de trabajo (mejora 38, fase 1b): valores estables [s] → clave i18n del
# rótulo. Options = segundos (estables); format_func traduce por la clave.
_PASOS_TRABAJO: tuple[tuple[float, str], ...] = (
    (3600.0, "h"),
    (900.0, "15min"),
    (600.0, "10min"),
    (300.0, "5min"),
)


def _clave_paso(paso_s: float) -> str:
    """Devuelve la clave i18n del rótulo de un paso de trabajo [s]."""
    for valor, clave in _PASOS_TRABAJO:
        if valor == paso_s:
            return clave
    return "h"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _render_cargar_proyecto() -> None:
    """Carga de un proyecto completo guardado desde P7.

    Vive en P1 porque es donde se empieza: cargar acá deja las siete pestañas
    servidas. Limpia el estado de todas las pestañas (``p1_``…``p7_``) para que
    los widgets releen del proyecto cargado y no de los valores cacheados de la
    sesión anterior — el mismo patrón de los cargadores por sección.
    """
    import json

    from ui.componentes.carga_proyecto import (
        ErrorCargaProyecto,
        cargar_proyecto_completo,
        resumen_clima_snapshot,
    )
    from ui.componentes.serializacion import limpiar_session_state_prefijo

    with st.expander(t("p1.cargar.titulo"), expanded=False):
        st.caption(t("p1.cargar.caption"))
        archivo = st.file_uploader(
            t("p1.cargar.uploader"),
            type=["json"],
            key="p1_cargar_proyecto",
            help=t("p1.cargar.help"),
        )
        if archivo is None:
            return

        try:
            contenido = archivo.read()
            if isinstance(contenido, bytes):
                contenido = contenido.decode("utf-8")
            datos = json.loads(contenido)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(t("p1.cargar.error_archivo", exc=exc))
            return

        if not st.button(t("p1.cargar.confirmar"), type="primary", key="p1_cargar_confirmar"):
            st.info(t("p1.cargar.pendiente", nombre=archivo.name))
            return

        try:
            proyecto_nuevo, avisos = cargar_proyecto_completo(datos)
        except ErrorCargaProyecto as exc:
            st.error(f"❌ {exc}")  # i18n: exento (mensaje con código, queda ES)
            return

        for prefijo in ("p1_", "p2_", "p3_", "p4_", "p5_", "p6_", "p7_", "cam_"):
            limpiar_session_state_prefijo(st.session_state, prefijo)
        st.session_state.proyecto = proyecto_nuevo

        st.success(t("p1.cargar.exito", nombre=proyecto_nuevo.meta.nombre))
        # El clima no viaja en el snapshot (8760 filas): hay que rebajarlo en P2.
        clima_snap = resumen_clima_snapshot(datos)
        if clima_snap and clima_snap.get("anio"):
            st.warning(t("p1.cargar.clima_pendiente", anio=clima_snap["anio"]))
        for aviso in avisos:
            st.warning(f"⚠️ {aviso}")  # i18n: exento (detalle de la sección que falló)
        st.rerun()


def render() -> None:
    """Renderiza la Pestaña 1 — Tipología y Configuración."""
    st.header(t("p1.header"))
    boton_manual(SLUG_POR_SECCION["p1"])

    _render_cargar_proyecto()

    proyecto = st.session_state.proyecto
    meta: Meta = proyecto.meta
    cfg: Configuracion = proyecto.configuracion

    # -----------------------------------------------------------------------
    # Sección A: Metadatos del proyecto
    # -----------------------------------------------------------------------
    with st.expander(t("p1.metadatos.titulo"), expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input(
                t("p1.metadatos.nombre.label"),
                value=meta.nombre,
                placeholder=t("p1.metadatos.nombre.placeholder"),
            )
        with c2:
            autor = st.text_input(
                t("p1.metadatos.autor.label"),
                value=meta.autor,
                placeholder=t("p1.metadatos.autor.placeholder"),
            )
        notas = st.text_area(
            t("p1.metadatos.notas.label"),
            value=meta.notas,
            height=80,
            placeholder=t("p1.metadatos.notas.placeholder"),
        )

        # Actualizar meta si cambió algo
        if nombre != meta.nombre or autor != meta.autor or notas != meta.notas:
            proyecto.meta = Meta(
                nombre=nombre,
                autor=autor,
                fecha_creacion=meta.fecha_creacion,
                version_software=meta.version_software,
                notas=notas,
            )

    # -----------------------------------------------------------------------
    # Sección B: Tipología del secador
    # -----------------------------------------------------------------------
    st.subheader(t("p1.tipologia.titulo"))

    with st.expander(t("p1.tipologia.guia.titulo"), expanded=False):
        st.markdown(t("p1.tipologia.guia.cuerpo"))

    tipo_lista = list(Tipologia)
    tipo_sel = st.radio(
        t("p1.tipologia.label"),
        options=tipo_lista,
        index=tipo_lista.index(cfg.tipologia),
        format_func=lambda tp: t(f"p1.tipologia.opcion.{tp.value.lower()}"),
        help=t("p1.tipologia.help"),
    )

    # Descripción de la tipología seleccionada
    st.info(t(f"p1.tipologia.desc.{tipo_sel.value.lower()}"))

    # Esquema del circuito de aire según tipología (CAJA / ARMARIO)
    if tipo_sel == Tipologia.CAJA:
        with st.expander(t("p1.esquema.titulo"), expanded=False):
            mostrar_esquema(
                "circuito_caja",
                caption=t("p1.esquema.caption_caja"),
            )
    elif tipo_sel == Tipologia.ARMARIO:
        with st.expander(t("p1.esquema.titulo"), expanded=False):
            mostrar_esquema(
                "circuito_armario",
                caption=t("p1.esquema.caption_armario"),
            )

    # Efecto cascada: si la tipología cambia a CAJA, anular colector y motor;
    # si cambia a GRAN_ESCALA, poblar el sistema con el preset ADITAL (S41).
    if tipo_sel != cfg.tipologia:
        if tipo_sel == Tipologia.CAJA:
            if proyecto.colector is not None:
                proyecto.colector = None
                st.warning(t("p1.cascada.sin_colector"))
            if proyecto.motor is not None:
                proyecto.motor = None
                st.warning(t("p1.cascada.sin_motor"))
        elif tipo_sel == Tipologia.GRAN_ESCALA:
            from core import presets

            proyecto.colector = presets.colector_gran_escala()
            proyecto.camara = presets.camara_gran_escala()
            proyecto.motor = presets.motor_gran_escala()
            st.info(t("p1.cascada.preset_gran_escala"))

    # -----------------------------------------------------------------------
    # Sección B2: Subtipo de secador industrial (solo GRAN_ESCALA)
    # -----------------------------------------------------------------------
    subtipo_sel = cfg.subtipo_gran_escala
    if tipo_sel == Tipologia.GRAN_ESCALA:
        st.subheader(t("p1.subtipo.titulo"))
        sub_lista = list(SubtipoGranEscala)
        idx_sub = sub_lista.index(subtipo_sel) if subtipo_sel in sub_lista else 0
        subtipo_sel = st.radio(
            t("p1.subtipo.label"),
            options=sub_lista,
            index=idx_sub,
            format_func=lambda s: t(f"p1.subtipo.opcion.{s.value.lower()}"),
            help=t("p1.subtipo.help"),
        )

    # -----------------------------------------------------------------------
    # Sección C: Modo de análisis
    # -----------------------------------------------------------------------
    st.subheader(t("p1.modo.titulo"))

    anual_deshabilitado = tipo_sel == Tipologia.CAJA

    if anual_deshabilitado:
        st.caption(t("p1.modo.caja_sin_anual"))
        modo_sel = ModoAnalisis.DIARIO
    else:
        modo_lista = [ModoAnalisis.DIARIO, ModoAnalisis.VENTANA, ModoAnalisis.ANUAL]
        idx_modo = modo_lista.index(cfg.modo_analisis) if cfg.modo_analisis in modo_lista else 0
        modo_sel = st.radio(
            t("p1.modo.label"),
            options=modo_lista,
            index=idx_modo,
            format_func=lambda m: t(f"p1.modo.opcion.{m.value.lower()}"),
            help=t("p1.modo.help"),
        )
        clima_actual = proyecto.clima
        if (
            clima_actual is not None
            and clima_actual.datos is not None
            and getattr(clima_actual, "fuente", "nasa_power") != "nasa_power"
        ):
            meses = meses_cubiertos(
                clima_actual.datos,
                (
                    proyecto.emplazamiento.zona_horaria
                    if proyecto.emplazamiento is not None
                    else "UTC"
                ),
            )
            if len(meses) < 12:
                st.caption(t("p1.modo.clima_parcial", n_meses=len(meses)))

    # -----------------------------------------------------------------------
    # Sección C-bis: Paso de trabajo (mejora 38, fase 1b)
    # -----------------------------------------------------------------------
    # El modo ANUAL trabaja siempre a paso horario (día típico mensual). Para
    # DIARIO/VENTANA se ofrece paso sub-horario (15/5 min).
    paso_sel = cfg.paso_trabajo_s if cfg.paso_trabajo_s in dict(_PASOS_TRABAJO) else 3600.0
    if modo_sel != ModoAnalisis.ANUAL:
        pasos_lista = [v for v, _ in _PASOS_TRABAJO]
        idx_paso = pasos_lista.index(paso_sel) if paso_sel in pasos_lista else 0
        paso_sel = st.radio(
            t("p1.paso.label"),
            options=pasos_lista,
            index=idx_paso,
            format_func=lambda p: t(f"p1.paso.opcion.{_clave_paso(p)}"),
            help=t("p1.paso.help"),
            horizontal=True,
        )
        if paso_sel <= 300.0:
            st.warning(t("p1.paso.aviso_fino"))
        elif paso_sel < 3600.0:
            st.caption(t("p1.paso.aviso_subhorario"))
    else:
        paso_sel = 3600.0

    # -----------------------------------------------------------------------
    # Sección D: Criterio de día (DIARIO) / ventana de producción (VENTANA)
    # -----------------------------------------------------------------------
    dia_sel = cfg.dia_analisis
    fecha_sel = cfg.fecha_especifica
    ventana_inicio_sel = cfg.ventana_inicio
    ventana_fin_sel = cfg.ventana_fin

    if modo_sel == ModoAnalisis.DIARIO:
        dia_lista = [
            DiaAnalisis.SOLSTICIO_VERANO,
            DiaAnalisis.SOLSTICIO_INVIERNO,
            DiaAnalisis.EQUINOCCIO_MARZO,
            DiaAnalisis.EQUINOCCIO_SEPTIEMBRE,
            DiaAnalisis.MAS_CALUROSO,
            DiaAnalisis.MAS_FRIO,
            DiaAnalisis.ESPECIFICO,
        ]

        # Mantener selección previa si es compatible
        idx_dia = dia_lista.index(cfg.dia_analisis) if cfg.dia_analisis in dia_lista else 0

        dia_sel = st.selectbox(
            t("p1.dia.label"),
            options=dia_lista,
            index=idx_dia,
            format_func=lambda d: t(f"p1.dia.opcion.{d.value.lower()}"),
            help=t("p1.dia.help"),
        )

        if dia_sel == DiaAnalisis.ESPECIFICO:
            fecha_min = date(ANIO_NASA_MIN, 1, 1)
            fecha_max = date(ANIO_NASA_MAX, 12, 31)
            if cfg.fecha_especifica:
                fecha_default = cfg.fecha_especifica
            else:
                # Si "hoy" cae dentro del rango NASA POWER se usa hoy. Si no,
                # se preserva mes/día y se reemplaza el año por el más reciente
                # disponible — menos sorprendente que saltar a una fecha fija.
                hoy = date.today()
                if fecha_min <= hoy <= fecha_max:
                    fecha_default = hoy
                else:
                    try:
                        fecha_default = hoy.replace(year=ANIO_NASA_MAX)
                    except ValueError:
                        # 29-feb fuera de año bisiesto.
                        fecha_default = date(ANIO_NASA_MAX, hoy.month, 28)
            fecha_sel = st.date_input(
                t("p1.dia.fecha.label"),
                value=fecha_default,
                min_value=fecha_min,
                max_value=fecha_max,
                help=t("p1.dia.fecha.help", anio_min=ANIO_NASA_MIN, anio_max=ANIO_NASA_MAX),
            )
        else:
            fecha_sel = None

    elif modo_sel == ModoAnalisis.VENTANA:
        dia_sel = DiaAnalisis.SOLSTICIO_VERANO  # irrelevante en modo ventana
        fecha_sel = None
        fecha_min = date(ANIO_NASA_MIN, 1, 1)
        fecha_max = date(ANIO_NASA_MAX, 12, 31)
        if "p1_vent_inicio" not in st.session_state:
            st.session_state["p1_vent_inicio"] = cfg.ventana_inicio or date(ANIO_NASA_MAX, 1, 1)
        if "p1_vent_fin" not in st.session_state:
            st.session_state["p1_vent_fin"] = cfg.ventana_fin or date(ANIO_NASA_MAX, 5, 31)

        # Atajos con duración persistente: el atajo fija la duración y el fin
        # sigue automáticamente a la fecha de inicio. Editar el fin a mano
        # desactiva el atajo (fechas libres).
        def _aplicar_atajo(dias: int) -> None:
            st.session_state["p1_vent_dur_dias"] = dias
            ini = st.session_state["p1_vent_inicio"]
            st.session_state["p1_vent_fin"] = min(fecha_max, ini + timedelta(days=dias))

        def _on_change_inicio() -> None:
            dur = st.session_state.get("p1_vent_dur_dias")
            if dur:
                ini = st.session_state["p1_vent_inicio"]
                st.session_state["p1_vent_fin"] = min(fecha_max, ini + timedelta(days=dur))

        def _on_change_fin() -> None:
            # Edición manual del fin → fechas libres (desactiva el atajo).
            st.session_state["p1_vent_dur_dias"] = None

        st.caption(t("p1.ventana.atajos_caption"))
        pc = st.columns(4)
        if pc[0].button(t("p1.ventana.atajo.semana")):
            _aplicar_atajo(7)
        if pc[1].button(t("p1.ventana.atajo.mes")):
            _aplicar_atajo(30)
        if pc[2].button(t("p1.ventana.atajo.campania")):
            _aplicar_atajo(150)
        if pc[3].button(t("p1.ventana.atajo.anio")):
            _aplicar_atajo(365)

        cc = st.columns(2)
        with cc[0]:
            ventana_inicio_sel = st.date_input(
                t("p1.ventana.inicio"),
                key="p1_vent_inicio",
                min_value=fecha_min,
                max_value=fecha_max,
                on_change=_on_change_inicio,
            )
        with cc[1]:
            ventana_fin_sel = st.date_input(
                t("p1.ventana.fin"),
                key="p1_vent_fin",
                min_value=fecha_min,
                max_value=fecha_max,
                on_change=_on_change_fin,
            )

        dur_activa = st.session_state.get("p1_vent_dur_dias")
        lapso_dias = (ventana_fin_sel - ventana_inicio_sel).days
        if ventana_fin_sel <= ventana_inicio_sel:
            st.warning(t("p1.ventana.fin_anterior"))
        elif lapso_dias > 366:
            st.warning(t("p1.ventana.lapso_excesivo", lapso_dias=lapso_dias))
        else:
            extra = t("p1.ventana.atajo_activo", dur=dur_activa) if dur_activa else ""
            st.caption(t("p1.ventana.lapso_caption", lapso_dias=lapso_dias, extra=extra))
        if ventana_inicio_sel.year != ventana_fin_sel.year:
            st.warning(t("p1.ventana.cruza_anio"))

    else:
        # Modo ANUAL: no aplica criterio de día
        dia_sel = DiaAnalisis.SOLSTICIO_VERANO
        fecha_sel = None

    # -----------------------------------------------------------------------
    # Aplicar configuración
    # -----------------------------------------------------------------------
    # En modo VENTANA, si las fechas son inválidas el warning amigable ya se
    # mostró arriba: se conserva la configuración anterior sin error crudo.
    ventana_invalida = modo_sel == ModoAnalisis.VENTANA and (
        ventana_inicio_sel is None
        or ventana_fin_sel is None
        or ventana_fin_sel <= ventana_inicio_sel
        or (ventana_fin_sel - ventana_inicio_sel).days > 366
    )
    if not ventana_invalida:
        try:
            nueva_cfg = Configuracion(
                tipologia=tipo_sel,
                modo_analisis=modo_sel,
                dia_analisis=dia_sel,
                fecha_especifica=fecha_sel,
                subtipo_gran_escala=subtipo_sel,
                ventana_inicio=ventana_inicio_sel,
                ventana_fin=ventana_fin_sel,
                paso_trabajo_s=paso_sel,
            )
            proyecto.configuracion = nueva_cfg
        except (ValueError, NotImplementedError) as exc:
            st.error(t("p1.config_invalida", exc=exc))

    # -----------------------------------------------------------------------
    # Resumen de la configuración actual
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader(t("p1.resumen.titulo"))

    c1, c2, c3 = st.columns(3)
    c1.metric(t("p1.resumen.tipologia"), t(f"p1.tipologia.corta.{tipo_sel.value.lower()}"))
    c2.metric(t("p1.resumen.modo"), t(f"p1.resumen.modo_corta.{modo_sel.value.lower()}"))
    if modo_sel == ModoAnalisis.DIARIO:
        dia_str = (
            str(fecha_sel)
            if dia_sel == DiaAnalisis.ESPECIFICO and fecha_sel
            else t(f"p1.dia.corta.{dia_sel.value.lower()}")
        )
        c3.metric(t("p1.resumen.dia"), dia_str)
    elif modo_sel == ModoAnalisis.VENTANA:
        if ventana_inicio_sel and ventana_fin_sel:
            c3.metric(
                t("p1.resumen.ventana"),
                t("p1.resumen.ventana_valor", inicio=ventana_inicio_sel, fin=ventana_fin_sel),
            )
        else:
            c3.metric(t("p1.resumen.ventana"), t("p1.resumen.ventana_sin_fechas"))
    else:
        c3.metric(t("p1.resumen.periodo"), t("p1.resumen.anio_completo"))

    if tipo_sel == Tipologia.GRAN_ESCALA:
        st.caption(
            t(
                "p1.resumen.subtipo",
                subtipo=t(f"p1.subtipo.corta.{subtipo_sel.value.lower()}"),
            )
        )

    # Recordatorio de lo que habilita cada tipología
    st.caption(
        t(
            "p1.resumen.secciones",
            secciones=(
                t("p1.resumen.secciones_caja")
                if tipo_sel == Tipologia.CAJA
                else t("p1.resumen.secciones_completa")
            ),
        )
    )
