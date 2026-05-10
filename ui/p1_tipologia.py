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

from datetime import date

import streamlit as st

from core.proyecto import (
    Configuracion,
    DiaAnalisis,
    Meta,
    ModoAnalisis,
    Tipologia,
)

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
    DiaAnalisis.EQUINOCCIO: "Equinoccio (21 mar / 21 sep)",
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
    with st.expander("Metadatos del proyecto", expanded=True):
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

    # Efecto cascada: si la tipología cambia a CAJA, anular colector y motor
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

    # -----------------------------------------------------------------------
    # Sección C: Modo de análisis
    # -----------------------------------------------------------------------
    st.subheader("Modo de análisis")

    anual_deshabilitado = (tipo_sel == Tipologia.CAJA)

    if anual_deshabilitado:
        st.caption(
            "ℹ️ El análisis **Anual** no está disponible para la tipología Caja en v0."
        )
        modo_sel = ModoAnalisis.DIARIO
    else:
        modo_opciones = {
            ModoAnalisis.DIARIO: "Diario — un día representativo (datos horarios)",
            ModoAnalisis.ANUAL: "Anual — año completo (8 760 horas)",
        }
        modo_label = st.radio(
            "Tipo de análisis",
            options=list(modo_opciones.values()),
            index=0 if cfg.modo_analisis == ModoAnalisis.DIARIO else 1,
            help=(
                "**Diario:** calcula el comportamiento en un día seleccionado. "
                "Rápido y adecuado para prediseño inicial.\n\n"
                "**Anual:** integra sobre las 8 760 horas del año. "
                "Requiere más tiempo de cómputo."
            ),
        )
        modo_sel = (
            ModoAnalisis.DIARIO
            if modo_label == modo_opciones[ModoAnalisis.DIARIO]
            else ModoAnalisis.ANUAL
        )

    # -----------------------------------------------------------------------
    # Sección D: Criterio de día (solo modo DIARIO)
    # -----------------------------------------------------------------------
    dia_sel = cfg.dia_analisis
    fecha_sel = cfg.fecha_especifica

    if modo_sel == ModoAnalisis.DIARIO:
        dia_lista = list(_ETIQUETAS_DIA.keys())
        dia_labels = [_ETIQUETAS_DIA[d] for d in dia_lista]

        # Mantener selección previa si es compatible
        idx_dia = (
            dia_lista.index(cfg.dia_analisis)
            if cfg.dia_analisis in dia_lista else 0
        )

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
            fecha_default = cfg.fecha_especifica or date.today()
            fecha_sel = st.date_input(
                "Fecha del análisis",
                value=fecha_default,
                help="Fecha concreta del día a analizar.",
            )
        else:
            fecha_sel = None

    else:
        # Modo ANUAL: no aplica criterio de día
        dia_sel = DiaAnalisis.SOLSTICIO_VERANO
        fecha_sel = None

    # -----------------------------------------------------------------------
    # Aplicar configuración
    # -----------------------------------------------------------------------
    try:
        nueva_cfg = Configuracion(
            tipologia=tipo_sel,
            modo_analisis=modo_sel,
            dia_analisis=dia_sel,
            fecha_especifica=fecha_sel,
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
            str(fecha_sel) if dia_sel == DiaAnalisis.ESPECIFICO and fecha_sel
            else dia_sel.value
        )
        c3.metric("Día de análisis", dia_str)
    else:
        c3.metric("Período", "Año completo")

    # Recordatorio de lo que habilita cada tipología
    st.caption(
        "**Secciones disponibles según tipología:** "
        + (
            "P2 Clima · P4 Cámara"
            if tipo_sel == Tipologia.CAJA
            else "P2 Clima · P3 Colector · P4 Cámara · P5 Auxiliar · P6 Motor"
        )
    )
