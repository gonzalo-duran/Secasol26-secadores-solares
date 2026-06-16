"""
Pestaña 1 — Tipología y Configuración del Análisis.

Permite al usuario:
    - Definir los metadatos del proyecto (nombre, autor, notas).
    - Seleccionar la tipología del secador (CAJA, ARMARIO, GRAN_ESCALA).
    - Configurar el tipo de análisis (DIARIO o ANUAL) y el criterio de día.

Los cambios se aplican de inmediato a st.session_state.proyecto.
Si la tipología cambia a CAJA, colector y motor se anulan automáticamente
(la tipología CAJA no admite colector externo ni motor).
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

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

# ---------------------------------------------------------------------------
# Descripciones de tipología
# ---------------------------------------------------------------------------

_DESC_TIPOLOGIA = {
    Tipologia.CAJA: (
        "**Secador de tipo Caja** — Pequeña escala (~1–10 kg de producto fresco). "
        "La cámara actúa como colector: efecto invernadero directo sobre el producto. "
        "Sin colector externo. Circulación de aire por **convección natural** "
        "(puede incorporar chimenea solar). "
        "Típico para uso doméstico o pequeños productores."
    ),
    Tipologia.ARMARIO: (
        "**Secador tipo Armario** — Escala media (~10–100 kg de producto fresco). "
        "Cámara de secado separada con uno o dos **colectores solares de aire** externos. "
        "Circulación natural (chimenea) o forzada (ventilador / extractor eólico). "
        "Puede incorporar calentamiento auxiliar (resistencia o biomasa). "
        "Apto para productores pequeños y medianos."
    ),
    Tipologia.GRAN_ESCALA: (
        "**Secador de Gran Escala** — Alta capacidad (~100 kg a varias toneladas). "
        "**Banco de colectores** solares de aire en serie/paralelo con caño maestro. "
        "Circulación **forzada** con motor eléctrico. "
        "Puede incluir calentamiento auxiliar. "
        "Orientado a producción agroindustrial."
    ),
}

_ETIQUETAS_TIPOLOGIA = {
    Tipologia.CAJA: "Caja (convección natural, sin colector externo)",
    Tipologia.ARMARIO: "Armario (colector externo, 10–100 kg)",
    Tipologia.GRAN_ESCALA: "Gran escala (banco de colectores, 100 kg+)",
}

_ETIQUETAS_DIA = {
    DiaAnalisis.SOLSTICIO_VERANO: "Solsticio de verano (21 dic) — día más largo",
    DiaAnalisis.SOLSTICIO_INVIERNO: "Solsticio de invierno (21 jun) — día más corto",
    DiaAnalisis.EQUINOCCIO_MARZO: "Equinoccio de otoño — 21 mar (hem. sur)",
    DiaAnalisis.EQUINOCCIO_SEPTIEMBRE: "Equinoccio de primavera — 21 sep (hem. sur)",
    DiaAnalisis.MAS_CALUROSO: "Día más caluroso del año (T_amb máxima)",
    DiaAnalisis.MAS_FRIO: "Día más frío del año (T_amb mínima)",
    DiaAnalisis.ESPECIFICO: "Día específico definido por el usuario",
}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 1 — Tipología y Configuración."""
    st.header("1 · Tipología y Configuración del Análisis")

    proyecto = st.session_state.proyecto
    meta: Meta = proyecto.meta
    cfg: Configuracion = proyecto.configuracion

    # -----------------------------------------------------------------------
    # Sección A: Metadatos del proyecto
    # -----------------------------------------------------------------------
    with st.expander("Metadatos del proyecto", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input(
                "Nombre del proyecto",
                value=meta.nombre,
                placeholder="Ej.: Secador armario manzana — Finca La Esperanza",
            )
        with c2:
            autor = st.text_input(
                "Autor / responsable",
                value=meta.autor,
                placeholder="Ej.: Juan García",
            )
        notas = st.text_area(
            "Notas libres",
            value=meta.notas,
            height=80,
            placeholder="Observaciones, condiciones de diseño, referencias, etc.",
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
    st.subheader("Tipología del secador")

    tipo_lista = list(_ETIQUETAS_TIPOLOGIA.keys())
    tipo_labels = [_ETIQUETAS_TIPOLOGIA[t] for t in tipo_lista]
    idx_tipo = tipo_lista.index(cfg.tipologia)

    tipo_sel_label = st.radio(
        "Seleccioná la tipología",
        options=tipo_labels,
        index=idx_tipo,
        help="La tipología define qué subsistemas están disponibles en el prediseño.",
    )
    tipo_sel = tipo_lista[tipo_labels.index(tipo_sel_label)]

    # Descripción de la tipología seleccionada
    st.info(_DESC_TIPOLOGIA[tipo_sel])

    # Esquema del circuito de aire según tipología (CAJA / ARMARIO)
    if tipo_sel == Tipologia.CAJA:
        with st.expander("📐 Circuito de aire", expanded=False):
            mostrar_esquema(
                "circuito_caja",
                caption="Circuito de aire del secador tipo Caja.",
            )
    elif tipo_sel == Tipologia.ARMARIO:
        with st.expander("📐 Circuito de aire", expanded=False):
            mostrar_esquema(
                "circuito_armario",
                caption="Circuito de aire del secador tipo Armario.",
            )

    # Efecto cascada: si la tipología cambia a CAJA, anular colector y motor;
    # si cambia a GRAN_ESCALA, poblar el sistema con el preset ADITAL (S41).
    if tipo_sel != cfg.tipologia:
        if tipo_sel == Tipologia.CAJA:
            if proyecto.colector is not None:
                proyecto.colector = None
                st.warning(
                    "⚠️ La tipología **Caja** no admite colector externo. "
                    "La configuración de P3 fue eliminada."
                )
            if proyecto.motor is not None:
                proyecto.motor = None
                st.warning(
                    "⚠️ La tipología **Caja** usa convección natural. "
                    "La configuración del motor (P6) fue eliminada."
                )
        elif tipo_sel == Tipologia.GRAN_ESCALA:
            from core import presets

            proyecto.colector = presets.colector_gran_escala()
            proyecto.camara = presets.camara_gran_escala()
            proyecto.motor = presets.motor_gran_escala()
            st.info(
                "🏭 Se cargó el **preset de gran escala** (secador híbrido "
                "ADITAL, San Carlos): banco de 26 colectores 7.5×0.94 m + caño "
                "maestro de 18 m, túnel de 18×3×1.85 m con 24 carros × 14 "
                "bandejas, 5000 kg de pimiento y ventilador de 3.8 kg/s. "
                "Ajustá lo que necesites en P3–P6."
            )

    # -----------------------------------------------------------------------
    # Sección B2: Subtipo de secador industrial (solo GRAN_ESCALA)
    # -----------------------------------------------------------------------
    subtipo_sel = cfg.subtipo_gran_escala
    if tipo_sel == Tipologia.GRAN_ESCALA:
        st.subheader("Subtipo de secador industrial")
        sub_opciones = {
            SubtipoGranEscala.BATCH: "Batch — secado por lotes (carga → seca → descarga)",
            SubtipoGranEscala.SEMICONTINUO: (
                "Semicontinuo — túnel a contracorriente, carga completa con avance "
                "de carros (estilo ADITAL)"
            ),
        }
        sub_lista = list(sub_opciones.keys())
        idx_sub = sub_lista.index(subtipo_sel) if subtipo_sel in sub_lista else 0
        sub_label = st.radio(
            "Modo de operación del secador",
            options=list(sub_opciones.values()),
            index=idx_sub,
            help=(
                "**Batch:** una carga completa se seca por lotes; la producción es "
                "la suma de los lotes completados en la ventana.\n\n"
                "**Semicontinuo:** el producto avanza a contracorriente del aire en "
                "un túnel de N columnas; produce un caudal sostenido (kg/día)."
            ),
        )
        subtipo_sel = sub_lista[list(sub_opciones.values()).index(sub_label)]

    # -----------------------------------------------------------------------
    # Sección C: Modo de análisis
    # -----------------------------------------------------------------------
    st.subheader("Modo de análisis")

    anual_deshabilitado = tipo_sel == Tipologia.CAJA

    if anual_deshabilitado:
        st.caption("ℹ️ El análisis **Anual** no está disponible para la tipología Caja en v0.")
        modo_sel = ModoAnalisis.DIARIO
    else:
        modo_opciones = {
            ModoAnalisis.DIARIO: "Diario — un día representativo (datos horarios)",
            ModoAnalisis.VENTANA: "Ventana de producción — lapso [inicio, fin] (clima real horario)",
            ModoAnalisis.ANUAL: "Anual — año completo (8 760 horas)",
        }
        modo_lista = list(modo_opciones.keys())
        idx_modo = modo_lista.index(cfg.modo_analisis) if cfg.modo_analisis in modo_lista else 0
        modo_label = st.radio(
            "Tipo de análisis",
            options=list(modo_opciones.values()),
            index=idx_modo,
            help=(
                "**Diario:** un día seleccionado. Rápido, para prediseño inicial.\n\n"
                "**Ventana de producción:** acumula la producción sobre un lapso "
                "(semana, mes, campaña) con clima real horario. Pensado para gran escala.\n\n"
                "**Anual:** integra sobre las 8 760 horas del año."
            ),
        )
        modo_sel = modo_lista[list(modo_opciones.values()).index(modo_label)]

    # -----------------------------------------------------------------------
    # Sección D: Criterio de día (DIARIO) / ventana de producción (VENTANA)
    # -----------------------------------------------------------------------
    dia_sel = cfg.dia_analisis
    fecha_sel = cfg.fecha_especifica
    ventana_inicio_sel = cfg.ventana_inicio
    ventana_fin_sel = cfg.ventana_fin

    if modo_sel == ModoAnalisis.DIARIO:
        dia_lista = list(_ETIQUETAS_DIA.keys())
        dia_labels = [_ETIQUETAS_DIA[d] for d in dia_lista]

        # Mantener selección previa si es compatible
        idx_dia = dia_lista.index(cfg.dia_analisis) if cfg.dia_analisis in dia_lista else 0

        dia_label_sel = st.selectbox(
            "Criterio de selección del día de análisis",
            options=dia_labels,
            index=idx_dia,
            help=(
                "Determina qué día del año se usa para el cálculo. "
                "Los criterios por temperatura o insolación usan los datos NASA POWER "
                "del emplazamiento (requiere que P2 esté configurada)."
            ),
        )
        dia_sel = dia_lista[dia_labels.index(dia_label_sel)]

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
                "Fecha del análisis",
                value=fecha_default,
                min_value=fecha_min,
                max_value=fecha_max,
                help=(
                    f"Fecha concreta del día a analizar. Rango disponible en "
                    f"NASA POWER: {ANIO_NASA_MIN}–{ANIO_NASA_MAX}."
                ),
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

        st.caption("Atajos de duración (el fin sigue a la fecha de inicio):")
        pc = st.columns(4)
        if pc[0].button("1 semana"):
            _aplicar_atajo(7)
        if pc[1].button("1 mes"):
            _aplicar_atajo(30)
        if pc[2].button("Campaña (5 meses)"):
            _aplicar_atajo(150)
        if pc[3].button("1 año"):
            _aplicar_atajo(365)

        cc = st.columns(2)
        with cc[0]:
            ventana_inicio_sel = st.date_input(
                "Inicio",
                key="p1_vent_inicio",
                min_value=fecha_min,
                max_value=fecha_max,
                on_change=_on_change_inicio,
            )
        with cc[1]:
            ventana_fin_sel = st.date_input(
                "Fin",
                key="p1_vent_fin",
                min_value=fecha_min,
                max_value=fecha_max,
                on_change=_on_change_fin,
            )

        dur_activa = st.session_state.get("p1_vent_dur_dias")
        lapso_dias = (ventana_fin_sel - ventana_inicio_sel).days
        if ventana_fin_sel <= ventana_inicio_sel:
            st.warning("⚠️ La fecha de fin debe ser posterior a la de inicio.")
        elif lapso_dias > 366:
            st.warning(
                f"⚠️ El lapso de análisis no puede superar **366 días** "
                f"(elegiste {lapso_dias}). Acortá la ventana o usá un atajo."
            )
        else:
            extra = (
                f" · Atajo activo: fin = inicio + {dur_activa} días "
                "(editar el fin lo desactiva)."
                if dur_activa
                else ""
            )
            st.caption(f"📆 Lapso: **{lapso_dias} días** de clima real horario.{extra}")
        if ventana_inicio_sel.year != ventana_fin_sel.year:
            st.warning(
                "⚠️ La ventana cruza el año calendario. Los datos climáticos "
                "NASA POWER se descargan por año calendario: elegí una ventana "
                "dentro de un mismo año para que P7 encuentre clima en todo el lapso."
            )

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
            )
            proyecto.configuracion = nueva_cfg
        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Configuración inválida: {exc}")

    # -----------------------------------------------------------------------
    # Resumen de la configuración actual
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Configuración activa")

    c1, c2, c3 = st.columns(3)
    c1.metric("Tipología", tipo_sel.value)
    c2.metric("Modo", modo_sel.value)
    if modo_sel == ModoAnalisis.DIARIO:
        dia_str = (
            str(fecha_sel) if dia_sel == DiaAnalisis.ESPECIFICO and fecha_sel else dia_sel.value
        )
        c3.metric("Día de análisis", dia_str)
    elif modo_sel == ModoAnalisis.VENTANA:
        if ventana_inicio_sel and ventana_fin_sel:
            c3.metric("Ventana", f"{ventana_inicio_sel} → {ventana_fin_sel}")
        else:
            c3.metric("Ventana", "(definir fechas)")
    else:
        c3.metric("Período", "Año completo")

    if tipo_sel == Tipologia.GRAN_ESCALA:
        st.caption(f"**Subtipo industrial:** {subtipo_sel.value}")

    # Recordatorio de lo que habilita cada tipología
    st.caption(
        "**Secciones disponibles según tipología:** "
        + (
            "P2 Clima · P4 Cámara"
            if tipo_sel == Tipologia.CAJA
            else "P2 Clima · P3 Colector · P4 Cámara · P5 Auxiliar · P6 Motor"
        )
    )
