"""
Pestaña 3 — Definición y dimensionamiento del colector solar de aire.

Permite al usuario seleccionar materiales del catálogo, configurar la geometría,
la velocidad de diseño y la batería de colectores. Muestra un resumen de diseño
y las advertencias estáticas antes de pasar al cálculo.

Sin cálculo físico aquí: solo configuración de entrada y validación estática.
"""

from __future__ import annotations

import dataclasses
from datetime import date as _date_type

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from calculos.colector_calc import calcular_colector_tipo1
from calculos.colector_tipos234_calc import (
    calcular_colector_tipo2,
    calcular_colector_tipo3,
    calcular_colector_tipo4,
)
from calculos.solar_geometria import (
    bin_horario_que_contiene,
    mediodia_solar_transit,
)
from core import catalogo
from core.advertencias import Severidad
from core.chimenea import Chimenea
from core.colector import (
    BancoColectores,
    CanoMaestro,
    Colector,
    ColectorUnidad,
    advertencias_colector,
)
from core.proyecto import DiaAnalisis, ModoAnalisis, Tipologia
from ui.componentes.advertencias_widget import render_advertencias
from ui.componentes.espesores import (
    ESPESORES_MADERA_MM,
    MATERIALES_MADERA,
    selector_espesor_mm,
)
from ui.componentes.esquemas import mostrar_esquema
from ui.componentes.graficas import mostrar_plotly
from ui.componentes.idiomas import t, t_catalogo
from ui.componentes.manual_contenido import SLUG_POR_SECCION
from ui.componentes.manual_link import boton_manual
from ui.componentes.unidades import kelvin_a_celsius

# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------


_ID_USUARIO = "__usuario__"

# Ids de los 4 tipos de colector (rótulos vía t("p3.tipo.opcion.<id>")).
_IDS_TIPOS_COLECTOR = (1, 2, 3, 4)


def _opciones_material(catalogo_dict: dict) -> dict[str, str]:
    """Genera un mapa {id: etiqueta_display} para un selectbox de materiales.

    Args:
        catalogo_dict: Diccionario de materiales cargado por core.catalogo.

    Returns:
        Diccionario ordenado {id_material: descripcion_corta}.
    """
    return {id_mat: t_catalogo(datos, default=id_mat) for id_mat, datos in catalogo_dict.items()}


def _tabla_propiedades_cubierta(id_mat: str) -> None:
    """Muestra las propiedades clave de una cubierta en la UI."""
    mat = catalogo.CUBIERTAS[id_mat]
    cols = st.columns(4)
    cols[0].metric("τ solar", f"{mat.get('transmitancia_solar', '—'):.2f}")
    cols[1].metric("ε IR", f"{mat.get('emisividad_ir', '—'):.2f}")
    cols[2].metric("T_max", f"{kelvin_a_celsius(mat.get('T_max_servicio', 0)):.0f} °C")
    cols[3].metric("k [W/m·K]", f"{mat.get('conductividad_termica', '—'):.3f}")


def _tabla_propiedades_placa(id_mat: str) -> None:
    """Muestra las propiedades clave de una placa absorbedora en la UI."""
    mat = catalogo.PLACAS[id_mat]
    cols = st.columns(4)
    cols[0].metric("α solar", f"{mat.get('absortancia_solar', '—'):.2f}")
    cols[1].metric("ε IR", f"{mat.get('emisividad_ir', '—'):.2f}")
    cols[2].metric("T_max", f"{kelvin_a_celsius(mat.get('T_max_servicio', 0)):.0f} °C")
    cols[3].metric("k [W/m·K]", f"{mat.get('conductividad_termica', '—'):.0f}")


def _tabla_propiedades_aislante(id_mat: str) -> None:
    """Muestra las propiedades clave de un aislante en la UI."""
    mat = catalogo.AISLANTES[id_mat]
    cols = st.columns(3)
    cols[0].metric("k [W/m·K]", f"{mat.get('conductividad_termica', '—'):.3f}")
    cols[1].metric("T_max", f"{kelvin_a_celsius(mat.get('T_max_servicio', 0)):.0f} °C")
    cols[2].metric("ρ [kg/m³]", f"{mat.get('densidad', '—'):.0f}")


def _tabla_propiedades_fondo(id_mat: str) -> None:
    """Muestra las propiedades clave de un material de fondo en la UI."""
    mat = catalogo.FONDOS[id_mat]
    cols = st.columns(3)
    cols[0].metric("k [W/m·K]", f"{mat.get('conductividad_termica', '—'):.2f}")
    cols[1].metric("T_max", f"{kelvin_a_celsius(mat.get('T_max_servicio', 0)):.0f} °C")
    cols[2].metric("ρ [kg/m³]", f"{mat.get('densidad', '—'):.0f}")


# ---------------------------------------------------------------------------
# Inputs para materiales definidos por el usuario
# ---------------------------------------------------------------------------


def _inputs_cubierta_usuario(key_prefix: str) -> dict:
    st.caption(t("p3.materiales.props_cubierta"))
    cols = st.columns(4)
    tau = cols[0].number_input(
        "τ solar",
        min_value=0.0,
        max_value=1.0,
        value=0.85,
        step=0.01,
        format="%.2f",
        key=f"{key_prefix}_tau",
    )
    eps = cols[1].number_input(
        "ε IR",
        min_value=0.0,
        max_value=1.0,
        value=0.90,
        step=0.01,
        format="%.2f",
        key=f"{key_prefix}_eps",
    )
    k = cols[2].number_input(
        "k [W/m·K]",
        min_value=0.01,
        max_value=5.0,
        value=0.76,
        step=0.01,
        format="%.3f",
        key=f"{key_prefix}_k",
    )
    Tmax_C = cols[3].number_input(
        "T_max [°C]", min_value=50, max_value=500, value=150, step=10, key=f"{key_prefix}_Tmax_C"
    )
    return {
        "descripcion": "Definido por el usuario",
        "transmitancia_solar": tau,
        "emisividad_ir": eps,
        "conductividad_termica": k,
        "densidad": 2500.0,
        "calor_especifico": 840.0,
        "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_placa_usuario(key_prefix: str) -> dict:
    st.caption(t("p3.materiales.props_placa"))
    cols = st.columns(4)
    alfa = cols[0].number_input(
        "α solar",
        min_value=0.0,
        max_value=1.0,
        value=0.95,
        step=0.01,
        format="%.2f",
        key=f"{key_prefix}_alfa",
    )
    eps = cols[1].number_input(
        "ε IR",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.01,
        format="%.2f",
        key=f"{key_prefix}_eps",
    )
    k = cols[2].number_input(
        "k [W/m·K]",
        min_value=0.1,
        max_value=500.0,
        value=50.0,
        step=1.0,
        format="%.1f",
        key=f"{key_prefix}_k",
    )
    Tmax_C = cols[3].number_input(
        "T_max [°C]", min_value=50, max_value=800, value=200, step=10, key=f"{key_prefix}_Tmax_C"
    )
    return {
        "descripcion": "Definido por el usuario",
        "absortancia_solar": alfa,
        "emisividad_ir": eps,
        "conductividad_termica": k,
        "densidad": 7850.0,
        "calor_especifico": 480.0,
        "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_aislante_usuario(key_prefix: str) -> dict:
    st.caption(t("p3.materiales.props_aislante"))
    cols = st.columns(3)
    k = cols[0].number_input(
        "k [W/m·K]",
        min_value=0.01,
        max_value=1.0,
        value=0.04,
        step=0.005,
        format="%.3f",
        key=f"{key_prefix}_k",
    )
    rho = cols[1].number_input(
        "ρ [kg/m³]",
        min_value=5.0,
        max_value=500.0,
        value=30.0,
        step=5.0,
        format="%.0f",
        key=f"{key_prefix}_rho",
    )
    Tmax_C = cols[2].number_input(
        "T_max [°C]", min_value=50, max_value=500, value=200, step=10, key=f"{key_prefix}_Tmax_C"
    )
    return {
        "descripcion": "Definido por el usuario",
        "conductividad_termica": k,
        "densidad": rho,
        "calor_especifico": 1000.0,
        "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_fondo_usuario(key_prefix: str) -> dict:
    st.caption(t("p3.materiales.props_fondo"))
    cols = st.columns(3)
    eps = cols[0].number_input(
        "ε IR",
        min_value=0.0,
        max_value=1.0,
        value=0.90,
        step=0.01,
        format="%.2f",
        key=f"{key_prefix}_eps",
    )
    k = cols[1].number_input(
        "k [W/m·K]",
        min_value=0.05,
        max_value=500.0,
        value=50.0,
        step=1.0,
        format="%.1f",
        key=f"{key_prefix}_k",
    )
    Tmax_C = cols[2].number_input(
        "T_max [°C]", min_value=50, max_value=800, value=200, step=10, key=f"{key_prefix}_Tmax_C"
    )
    return {
        "descripcion": "Definido por el usuario",
        "emisividad_ir": eps,
        "conductividad_termica": k,
        "densidad": 7850.0,
        "calor_especifico": 480.0,
        "T_max_servicio": float(Tmax_C) + 273.15,
    }


# ---------------------------------------------------------------------------
# Generador de texto de configuración (mejora 4)
# ---------------------------------------------------------------------------


def _mat_props(cat_dict: dict, id_mat: str) -> dict:
    """Devuelve todas las propiedades del material para snapshot reconstruible."""
    return dict(cat_dict.get(id_mat, {}))


def _resumen_eval_diario(r: dict) -> dict | None:
    """Extrae métricas representativas de la evaluación diaria del colector."""
    if not r:
        return None
    T_sal = [t for t in r.get("T_salida_C", []) if t is not None]
    T_amb = r.get("T_amb_C", [])
    if not T_sal:
        return None
    # ΔT máx en horas con T_salida válida
    pares = [
        (ts, T_amb[i])
        for i, ts in enumerate(r.get("T_salida_C", []))
        if ts is not None and i < len(T_amb)
    ]
    dT_max = max(ts - ta for ts, ta in pares) if pares else None
    return {
        "T_salida_max_C": float(max(T_sal)),
        "T_salida_min_C": float(min(T_sal)),
        "T_salida_mediodia_C": float(T_sal[len(T_sal) // 2]),
        "delta_T_max_C": float(dT_max) if dT_max is not None else None,
        "hora_transit": r.get("hora_transit"),
        "n_horas_con_radiacion": len(T_sal),
    }


def _resumen_eval_ventana(r: dict) -> dict | None:
    """Extrae métricas representativas de la evaluación sobre la ventana (S41)."""
    if not r:
        return None
    T_sal = [t for t in r.get("T_salida_C", []) if t is not None]
    if not T_sal:
        return None
    pares_diurnos = [
        (ts, ta)
        for ts, ta, p in zip(r.get("T_salida_C", []), r.get("T_amb_C", []), r.get("poa", []))
        if ts is not None and p > 50.0
    ]
    dT_medio = (
        sum(ts - ta for ts, ta in pares_diurnos) / len(pares_diurnos) if pares_diurnos else None
    )
    return {
        "T_salida_max_C": float(max(T_sal)),
        "T_salida_min_C": float(min(T_sal)),
        "delta_T_medio_diurno_C": float(dT_medio) if dT_medio is not None else None,
        "n_horas_T_sal_40C": sum(1 for t in T_sal if t > 40.0),
        "n_horas_evaluadas": len(r.get("T_salida_C", [])),
    }


def _resumen_eval_anual(r: dict) -> dict | None:
    """Extrae métricas representativas de la evaluación anual del colector."""
    if not r or not r.get("meses"):
        return None
    meses = r["meses"]
    T_sal_noon = r.get("T_salida_noon_C", [])
    T_amb_noon = r.get("T_amb_noon_C", [])
    if not T_sal_noon:
        return None
    idx_max = T_sal_noon.index(max(T_sal_noon))
    idx_min = T_sal_noon.index(min(T_sal_noon))
    dT_min = min(ts - ta for ts, ta in zip(T_sal_noon, T_amb_noon))
    return {
        "T_salida_max_C": float(max(T_sal_noon)),
        "T_salida_max_mes": meses[idx_max],
        "T_salida_min_C": float(min(T_sal_noon)),
        "T_salida_min_mes": meses[idx_min],
        "delta_T_min_C": float(dT_min),
        "T_salida_por_mes": {m: float(v) for m, v in zip(meses, T_sal_noon)},
    }


def _texto_config_colector(
    col: "Colector",
    eval_dict: dict | None = None,
) -> str:
    """Genera el snapshot .txt del colector incluyendo resultados si están.

    Args:
        col: Instancia configurada del colector.
        eval_dict: ``st.session_state["p3_eval"]`` (o ``None`` si no se corrió).
    """
    from datetime import date

    u = col.unidad

    def desc(cat_dict: dict, id_mat: str) -> str:
        return cat_dict.get(id_mat, {}).get("descripcion", id_mat)

    def material_block(
        label: str, cat: dict, mat_id: str, espesor_m: float, espesor_unit: str = "mm"
    ) -> list[str]:
        props = _mat_props(cat, mat_id)
        if espesor_unit == "mm":
            e_str = f"{espesor_m * 1000:.1f} mm"
        else:
            e_str = f"{espesor_m * 100:.1f} cm"
        out = [
            f"  {label:8}: {desc(cat, mat_id)}  [id={mat_id}]",
            f"             e = {e_str}",
        ]
        for k, etiq in [
            ("conductividad_termica", "k [W/(m·K)]"),
            ("densidad", "ρ [kg/m³]"),
            ("calor_especifico", "cp [J/(kg·K)]"),
            ("emisividad_ir", "ε_ir"),
            ("absortancia_solar", "α_sol"),
            ("transmitancia_solar", "τ_sol"),
            ("T_max_servicio", "T_max [K]"),
        ]:
            if k in props and props[k] is not None:
                v = props[k]
                if isinstance(v, float):
                    out.append(f"               {etiq} = {v:.3f}")
                else:
                    out.append(f"               {etiq} = {v}")
        return out

    sep = "=" * 60
    lines = [
        sep,
        "       CONFIGURACIÓN DEL COLECTOR SOLAR",
        sep,
        f"Fecha de exportación: {date.today()}",
        "",
        "MATERIALES",
        *material_block("Cubierta", catalogo.CUBIERTAS, u.id_cubierta, u.espesor_cubierta_m, "mm"),
        f"             N° cubiertas = {u.n_cubiertas}",
        *material_block("Placa", catalogo.PLACAS, u.id_placa, u.espesor_placa_m, "mm"),
        *material_block("Aislante", catalogo.AISLANTES, u.id_aislante, u.espesor_aislante_m, "cm"),
        *material_block("Fondo", catalogo.FONDOS, u.id_fondo, u.espesor_fondo_m, "mm"),
        "",
        "TIPO DE COLECTOR",
        f"  {t(f'p3.tipo.opcion.{u.tipo_colector}', default=f'Tipo {u.tipo_colector}')}",
        "",
        "GEOMETRÍA Y CONDICIÓN DE DISEÑO",
        f"  Ancho           : {u.ancho_m:.3f} m",
        f"  Largo           : {u.largo_m:.3f} m",
        (
            f"  Canal superior  : {u.espaciado_m * 1000:.1f} mm"
            if u.tipo_colector in (2, 3, 4)
            else f"  Espaciado canal : {u.espaciado_m * 1000:.1f} mm"
        ),
        *(
            [f"  Canal inferior  : {u.espaciado_inferior_m * 1000:.1f} mm"]
            if u.tipo_colector in (2, 3, 4)
            else []
        ),
        f"  Vel. diseño     : {u.velocidad_diseno_ms:.3f} m/s",
        f"  Sección canal   : {u.seccion_canal_m2() * 1e4:.2f} cm²",
        f"  Área captación  : {u.area_captacion_m2():.3f} m²",
        f"  Caudal unitario : {u.caudal_volumetrico_m3_s() * 1000:.3f} L/s",
        "",
        "BANCO DE COLECTORES",
        f"  N° serie        : {col.banco.n_serie}",
        f"  N° paralelo     : {col.banco.n_paralelo}",
        f"  Área total      : {col.area_total_m2():.3f} m²",
        f"  Caudal total    : {col.caudal_total_m3_s() * 1000:.3f} L/s",
        f"  Camino del aire : {col.largo_camino_aire_m():.2f} m",
    ]
    if col.banco.cano_maestro is not None:
        cm = col.banco.cano_maestro
        lines += [
            "",
            "CAÑO MAESTRO (manifold del banco)",
            f"  Largo           : {cm.largo_m:.1f} m",
            f"  Sección (vent.) : {cm.ancho_m:.2f} × {cm.alto_m:.2f} m "
            f"({cm.area_seccion_m2:.2f} m²)",
            *(
                [
                    f"  Sección (inicio): {cm.ancho_inicio_m:.2f} × {cm.alto_inicio_m:.2f} m "
                    f"({cm.area_seccion_inicio_m2:.2f} m²) — sección creciente"
                ]
                if cm.seccion_variable
                else []
            ),
            f"  Aislado         : {'Sí' if cm.aislado else 'No'}"
            + (f" ({cm.material_aislante})" if cm.material_aislante else ""),
            f"  Aporte solar    : {'Sí' if cm.aporte_solar else 'No'}"
            + (f" (α = {cm.absortancia_solar:.2f})" if cm.aporte_solar else ""),
            *(
                [f"  Cubierta transl.: {cm.cubierta} (τ = {cm.transmitancia_cubierta:.2f})"]
                if cm.cubierta
                else []
            ),
        ]
    # Advertencias estáticas activas
    advs = advertencias_colector(col)
    lines += ["", "ADVERTENCIAS ESTÁTICAS DE DISEÑO"]
    if not advs:
        lines.append("  (ninguna)")
    else:
        for a in advs:
            lines.append(f"  [{a.severidad.value}] {a.codigo}: {a.mensaje}")

    # Resultados de simulación si están disponibles
    lines += ["", sep, "  RESULTADOS DE SIMULACIÓN", sep]
    if eval_dict is None or not eval_dict.get("r"):
        lines.append("  ⚠ Cálculo no ejecutado. Volver a P3 y presionar")
        lines.append("    'Calcular desempeño del colector' para incluirlos.")
    else:
        modo = eval_dict.get("modo")
        r = eval_dict["r"]
        if modo == "diario":
            label = eval_dict.get("label", "—")
            res = _resumen_eval_diario(r)
            lines += [
                "  Modo evaluación   : DIARIO",
                f"  Día representativo: {label}",
            ]
            if res is None:
                lines.append("  (sin horas con radiación suficiente)")
            else:
                lines += [
                    f"  T salida máx     : {res['T_salida_max_C']:.1f} °C",
                    f"  T salida mediodía: {res['T_salida_mediodia_C']:.1f} °C",
                    f"  T salida mín     : {res['T_salida_min_C']:.1f} °C",
                    (
                        f"  ΔT máx           : " f"{res['delta_T_max_C']:.1f} °C"
                        if res["delta_T_max_C"] is not None
                        else "  ΔT máx           : —"
                    ),
                    f"  Hora tránsito    : {res['hora_transit'] or '—'}",
                    f"  Horas con sol    : {res['n_horas_con_radiacion']}",
                ]
        elif modo == "ventana":
            label = eval_dict.get("label", "—")
            res = _resumen_eval_ventana(r)
            lines += [
                "  Modo evaluación   : VENTANA DE PRODUCCIÓN",
                f"  Lapso             : {label}",
            ]
            if res is None:
                lines.append("  (sin horas con radiación suficiente)")
            else:
                lines += [
                    f"  T salida máx     : {res['T_salida_max_C']:.1f} °C",
                    f"  T salida mín     : {res['T_salida_min_C']:.1f} °C",
                    (
                        f"  ΔT medio diurno  : {res['delta_T_medio_diurno_C']:.1f} °C"
                        if res["delta_T_medio_diurno_C"] is not None
                        else "  ΔT medio diurno  : —"
                    ),
                    f"  Horas T>40 °C    : {res['n_horas_T_sal_40C']}",
                    f"  Horas evaluadas  : {res['n_horas_evaluadas']}",
                ]
        elif modo == "anual":
            res = _resumen_eval_anual(r)
            lines.append("  Modo evaluación  : ANUAL (12 meses representativos)")
            if res is None:
                lines.append("  (sin resultados válidos)")
            else:
                lines += [
                    f"  T salida máx     : {res['T_salida_max_C']:.1f} °C "
                    f"(en {res['T_salida_max_mes']})",
                    f"  T salida mín     : {res['T_salida_min_C']:.1f} °C "
                    f"(en {res['T_salida_min_mes']})",
                    f"  ΔT mín           : {res['delta_T_min_C']:.1f} °C",
                    "  T salida por mes : ",
                ]
                for mes, val in res["T_salida_por_mes"].items():
                    lines.append(f"    {mes:3s} : {val:5.1f} °C")
    lines.append("")
    return "\n".join(lines)


def _from_json_colector(data: dict) -> "Colector":
    """Reconstruye un ``Colector`` desde un dict producido por
    ``_json_config_colector``.

    Solo usa los campos del dict que el constructor del dataclass requiere.
    Los campos derivados (área total, advertencias, resultados) se ignoran
    porque se recomputan al instanciar.

    Nota: la chimenea ya no forma parte del Colector. Si el .json es viejo
    y trae la key ``chimenea``, el caller debe restaurarla por separado en
    ``proyecto.chimenea`` (ver caller en ``render()``).

    Raises:
        KeyError: si faltan campos obligatorios.
        ValueError: si un id de material no existe en el catálogo.
    """
    u = data.get("unidad") or {}
    mats = data.get("materiales") or {}
    banco = data.get("banco") or {}

    def _mat_id(key: str) -> str:
        m = mats.get(key) or {}
        if "id" not in m:
            raise KeyError(f"materiales.{key}.id ausente en el JSON cargado")
        return m["id"]

    def _mat_espesor(key: str) -> float:
        m = mats.get(key) or {}
        if "espesor_m" not in m:
            raise KeyError(f"materiales.{key}.espesor_m ausente en el JSON cargado")
        return float(m["espesor_m"])

    unidad = ColectorUnidad(
        ancho_m=float(u["ancho_m"]),
        largo_m=float(u["largo_m"]),
        espaciado_m=float(u["espaciado_m"]),
        n_cubiertas=int(u["n_cubiertas"]),
        espaciado_entre_cubiertas_m=float(u.get("espaciado_entre_cubiertas_m", 0.025)),
        velocidad_diseno_ms=float(u["velocidad_diseno_ms"]),
        tipo_colector=int(u.get("tipo_colector", 1)),
        espaciado_inferior_m=float(u.get("espaciado_inferior_m", u["espaciado_m"])),
        id_cubierta=_mat_id("cubierta"),
        espesor_cubierta_m=_mat_espesor("cubierta"),
        id_placa=_mat_id("placa"),
        espesor_placa_m=_mat_espesor("placa"),
        id_aislante=_mat_id("aislante"),
        espesor_aislante_m=_mat_espesor("aislante"),
        id_fondo=_mat_id("fondo"),
        espesor_fondo_m=_mat_espesor("fondo"),
        k_cubierta_efectivo_W_mK=u.get("k_cubierta_efectivo_W_mK"),
    )
    cano_d = banco.get("cano_maestro")
    _ancho_ini = cano_d.get("ancho_inicio_m") if cano_d else None
    _alto_ini = cano_d.get("alto_inicio_m") if cano_d else None
    cano = (
        CanoMaestro(
            largo_m=float(cano_d["largo_m"]),
            ancho_m=float(cano_d["ancho_m"]),
            alto_m=float(cano_d["alto_m"]),
            rugosidad_m=float(cano_d.get("rugosidad_m", 1.5e-4)),
            aislado=bool(cano_d.get("aislado", False)),
            espesor_aislante_m=float(cano_d.get("espesor_aislante_m", 0.0)),
            material_aislante=cano_d.get("material_aislante"),
            aporte_solar=bool(cano_d.get("aporte_solar", True)),
            absortancia_solar=float(cano_d.get("absortancia_solar", 0.90)),
            cubierta=cano_d.get("cubierta"),
            ancho_inicio_m=float(_ancho_ini) if _ancho_ini is not None else None,
            alto_inicio_m=float(_alto_ini) if _alto_ini is not None else None,
        )
        if cano_d
        else None
    )
    bco = BancoColectores(
        n_serie=int(banco.get("n_serie", 1)),
        n_paralelo=int(banco.get("n_paralelo", 1)),
        cano_maestro=cano,
    )
    return Colector(unidad=unidad, banco=bco)


def _json_config_colector(
    col: "Colector",
    eval_dict: dict | None = None,
) -> dict:
    """Genera el snapshot reconstruible (dict serializable) del colector."""
    from datetime import date

    u = col.unidad

    snapshot: dict = {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "colector",
        "unidad": {
            "ancho_m": u.ancho_m,
            "largo_m": u.largo_m,
            "espaciado_m": u.espaciado_m,
            "espaciado_inferior_m": u.espaciado_inferior_m,
            "n_cubiertas": u.n_cubiertas,
            "espaciado_entre_cubiertas_m": u.espaciado_entre_cubiertas_m,
            "velocidad_diseno_ms": u.velocidad_diseno_ms,
            "tipo_colector": u.tipo_colector,
            "tipo_colector_descripcion": t(f"p3.tipo.opcion.{u.tipo_colector}", default=None),
            "k_cubierta_efectivo_W_mK": u.k_cubierta_efectivo_W_mK,
        },
        "materiales": {
            "cubierta": {
                "id": u.id_cubierta,
                "espesor_m": u.espesor_cubierta_m,
                "props_catalogo": _mat_props(catalogo.CUBIERTAS, u.id_cubierta),
            },
            "placa": {
                "id": u.id_placa,
                "espesor_m": u.espesor_placa_m,
                "props_catalogo": _mat_props(catalogo.PLACAS, u.id_placa),
            },
            "aislante": {
                "id": u.id_aislante,
                "espesor_m": u.espesor_aislante_m,
                "props_catalogo": _mat_props(catalogo.AISLANTES, u.id_aislante),
            },
            "fondo": {
                "id": u.id_fondo,
                "espesor_m": u.espesor_fondo_m,
                "props_catalogo": _mat_props(catalogo.FONDOS, u.id_fondo),
            },
        },
        "banco": {
            "n_serie": col.banco.n_serie,
            "n_paralelo": col.banco.n_paralelo,
            "cano_maestro": (
                {
                    "largo_m": col.banco.cano_maestro.largo_m,
                    "ancho_m": col.banco.cano_maestro.ancho_m,
                    "alto_m": col.banco.cano_maestro.alto_m,
                    "rugosidad_m": col.banco.cano_maestro.rugosidad_m,
                    "aislado": col.banco.cano_maestro.aislado,
                    "espesor_aislante_m": col.banco.cano_maestro.espesor_aislante_m,
                    "material_aislante": col.banco.cano_maestro.material_aislante,
                    "aporte_solar": col.banco.cano_maestro.aporte_solar,
                    "absortancia_solar": col.banco.cano_maestro.absortancia_solar,
                    "cubierta": col.banco.cano_maestro.cubierta,
                    "ancho_inicio_m": col.banco.cano_maestro.ancho_inicio_m,
                    "alto_inicio_m": col.banco.cano_maestro.alto_inicio_m,
                    "area_seccion_m2": col.banco.cano_maestro.area_seccion_m2,
                }
                if col.banco.cano_maestro is not None
                else None
            ),
        },
        "derivados": {
            "seccion_canal_m2": u.seccion_canal_m2(),
            "area_captacion_unidad_m2": u.area_captacion_m2(),
            "caudal_unidad_m3_s": u.caudal_volumetrico_m3_s(),
            "area_total_m2": col.area_total_m2(),
            "caudal_total_m3_s": col.caudal_total_m3_s(),
            "largo_camino_aire_m": col.largo_camino_aire_m(),
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
            for a in advertencias_colector(col)
        ],
    }

    # Resultados
    if eval_dict is None or not eval_dict.get("r"):
        snapshot["resultados"] = {
            "ejecutado": False,
            "nota": "Cálculo no ejecutado en esta sesión.",
        }
    else:
        modo = eval_dict.get("modo")
        r = eval_dict["r"]
        bloque = {"ejecutado": True, "modo": modo}
        if modo == "diario":
            bloque["dia_representativo"] = eval_dict.get("label")
            bloque["resumen"] = _resumen_eval_diario(r)
        elif modo == "ventana":
            bloque["lapso"] = eval_dict.get("label")
            bloque["resumen"] = _resumen_eval_ventana(r)
        elif modo == "anual":
            bloque["resumen"] = _resumen_eval_anual(r)
        snapshot["resultados"] = bloque

    return snapshot


# ---------------------------------------------------------------------------
# Evaluación del colector — cálculo y figuras
# ---------------------------------------------------------------------------

_COLORES_MESES = [
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#42d4f4",
    "#f032e6",
    "#bfef45",
    "#fabed4",
    "#469990",
    "#dcbeff",
    "#9a6324",
]


def _poa_serie(datos, empl):
    """Wrapper sobre ``calculos.clima_calc.calcular_POA_horizonte`` para
    mantener firma estable en este módulo. POA horaria sobre el plano del
    colector, derivada de DNI/GHI/DHI + tilt/azimut del emplazamiento."""
    from calculos.clima_calc import calcular_POA_horizonte

    return calcular_POA_horizonte(datos, empl)


def _render_albedo_suelo(proyecto, empl) -> None:
    """Desplegable de albedo del suelo (superficie circundante) en P3.

    El albedo es una propiedad del sitio (se guarda en ``emplazamiento``), pero
    el widget vive en P3 porque —como el tilt— gobierna la componente reflejada
    del suelo en la POA. Escribe ``proyecto.emplazamiento`` reconstruyendo el
    dataclass con ``dataclasses.replace`` para re-disparar la validación.
    """
    from calculos.catalogo_albedos import (
        ALBEDOS_SUPERFICIE,
        ETIQUETA_PERSONALIZADO,
        etiqueta_desde_albedo,
    )

    opciones = list(ALBEDOS_SUPERFICIE.keys()) + [ETIQUETA_PERSONALIZADO]
    etiqueta_actual = etiqueta_desde_albedo(empl.albedo_suelo)

    col_sel, col_val = st.columns([2, 1])
    with col_sel:
        seleccion = st.selectbox(
            t("p3.eval.albedo.label"),
            options=opciones,
            index=opciones.index(etiqueta_actual),
            key="p3_albedo_superficie",
            help=t("p3.eval.albedo.help"),
        )

    if seleccion == ETIQUETA_PERSONALIZADO:
        with col_val:
            nuevo_albedo = st.number_input(
                t("p3.eval.albedo.personalizado"),
                min_value=0.0,
                max_value=1.0,
                value=float(empl.albedo_suelo),
                step=0.01,
                format="%.2f",
                key="p3_albedo_personalizado",
            )
    else:
        nuevo_albedo = ALBEDOS_SUPERFICIE[seleccion]
        with col_val:
            st.metric("ρ", f"{nuevo_albedo:.2f}")

    if abs(nuevo_albedo - empl.albedo_suelo) > 1e-9:
        proyecto.emplazamiento = dataclasses.replace(empl, albedo_suelo=nuevo_albedo)


def _correr_colector(colector, T_amb_K, I_g_W_m2, v_viento_ms, pendiente_deg=30.0):
    if I_g_W_m2 < 50.0:
        return None
    u = colector.unidad
    tipo = u.tipo_colector
    kw = dict(
        colector=colector,
        T_amb_K=T_amb_K,
        I_g_W_m2=I_g_W_m2,
        v_viento_ms=max(v_viento_ms, 0.5),
        P_amb_Pa=101325.0,
        T_entrada_K=T_amb_K,
        pendiente_deg=pendiente_deg,
    )
    try:
        if tipo == 1:
            return calcular_colector_tipo1(**kw, correlacion_nusselt=None)
        elif tipo == 2:
            return calcular_colector_tipo2(
                **kw,
                v_diseno_cs_ms=u.velocidad_diseno_ms,
                v_diseno_ci_ms=u.velocidad_diseno_ms,
                alto_cs_m=u.espaciado_m,
                alto_ci_m=u.espaciado_inferior_m,
            )
        elif tipo == 3:
            # Tipo 3 usa theta_deg para Hollands del canal estanco; lo unificamos
            # con la pendiente del colector (ya se reutiliza para la cavidad de cubiertas).
            kw_t3 = {k: v for k, v in kw.items() if k != "pendiente_deg"}
            return calcular_colector_tipo3(
                **kw_t3,
                alto_cs_m=u.espaciado_m,
                alto_ci_m=u.espaciado_inferior_m,
                theta_deg=pendiente_deg,
            )
        elif tipo == 4:
            return calcular_colector_tipo4(
                **kw, alto_cs_m=u.espaciado_m, alto_ci_m=u.espaciado_inferior_m
            )
    except Exception:
        return None


def _T_salida_res(res, tipo):
    return res.T_salida_mezcla_K if tipo == 2 else res.T_salida_K


# Canales de salida ofrecidos para validar contra el medido. Solo el Tipo 2
# (doble canal activo) distingue superior/inferior; en el resto los tres colapsan
# a la única salida.
CANALES_SALIDA: tuple[str, ...] = ("mezcla", "superior", "inferior")


def _T_salida_canal_K(res, tipo, canal: str) -> float:
    """T de salida del colector para el canal pedido [K].

    Args:
        res: Resultado del solver del colector.
        tipo: Tipo de colector (1–4).
        canal: "mezcla" | "superior" | "inferior". Para Tipos 1/3/4 los tres
            devuelven la única salida disponible.
    """
    if tipo == 2:
        if canal == "superior":
            return res.T_salida_cs_K
        if canal == "inferior":
            return res.T_salida_ci_K
        return res.T_salida_mezcla_K
    return _T_salida_res(res, tipo)


def _perfil_fluido(res, tipo):
    x = res.x_m
    if tipo == 1:
        T = res.T_fluido_K
    elif tipo == 2:
        T = (res.T_f_cs_K + res.T_f_ci_K) / 2.0
    elif tipo == 3:
        T = res.T_f_ci_K
    else:
        T = res.T_f_cs_K
    return x, T


def _seleccionar_dia(datos_local, cfg, anio):
    """Devuelve (datos_dia, fecha_date) según el criterio de cfg."""
    if cfg.dia_analisis == DiaAnalisis.ESPECIFICO and cfg.fecha_especifica:
        target = cfg.fecha_especifica
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_VERANO:
        target = _date_type(anio, 12, 21)
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_INVIERNO:
        target = _date_type(anio, 6, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_MARZO:
        target = _date_type(anio, 3, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_SEPTIEMBRE:
        target = _date_type(anio, 9, 21)
    elif cfg.dia_analisis == DiaAnalisis.MAS_CALUROSO:
        target = (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmax().date()
    else:
        target = (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmin().date()
    mask = datos_local.index.date == target
    return datos_local[mask], target


def _evaluar_diario(colector, datos_dia, empl):
    """Evalúa el colector hora a hora en el día de análisis.

    Devuelve dos timestamps de referencia:
        - ``hora_transit``: tránsito solar verdadero (mediodía físico, SPA).
            Resolución continua (típicamente 13:15-13:25 en Salta).
        - ``hora_poa_max``: bin horario con máxima POA (la hora de mejor
            rendimiento del colector según su orientación).

    El perfil de temperatura T(x) se evalúa en el bin horario que contiene
    el tránsito solar (no en POA máx), siguiendo la convención de "estado
    al mediodía" usada en textos de secado solar.
    """
    poa = _poa_serie(datos_dia, empl)
    tipo = colector.unidad.tipo_colector

    horas, T_sal_C, T_amb_C, poa_list = [], [], [], []
    x_noon = T_perfil_noon_C = None

    if poa.max() > 50:
        # Mediodía solar verdadero (tránsito SPA, resolución continua).
        target = datos_dia.index.date[0]
        hora_transit = mediodia_solar_transit(
            target,
            empl.latitud_deg,
            empl.longitud_deg,
            empl.zona_horaria,
        )
        hora_poa_max = poa.idxmax()
        # Evaluamos el perfil en el bin que contiene el tránsito SPA.
        idx_perfil = bin_horario_que_contiene(hora_transit, datos_dia.index)
    else:
        hora_transit = hora_poa_max = idx_perfil = None

    for ts, row in datos_dia.iterrows():
        I_g = float(poa.get(ts, 0.0))
        T_amb = float(row["T_amb_K"])
        v_w = float(row["WS_ms"])
        res = _correr_colector(colector, T_amb, I_g, v_w, pendiente_deg=empl.pendiente_colector_deg)

        horas.append(ts)
        T_amb_C.append(T_amb - 273.15)
        poa_list.append(I_g)

        if res is not None:
            T_sal_C.append(_T_salida_res(res, tipo) - 273.15)
            if idx_perfil is not None and ts == idx_perfil:
                x_noon, T_perfil = _perfil_fluido(res, tipo)
                T_perfil_noon_C = T_perfil - 273.15
        else:
            T_sal_C.append(None)

    return {
        "horas": horas,
        "T_salida_C": T_sal_C,
        "T_amb_C": T_amb_C,
        "poa": poa_list,
        "x_noon": x_noon,
        "T_perfil_noon_C": T_perfil_noon_C,
        "hora_transit": hora_transit,
        "hora_poa_max": hora_poa_max,
        "tipo": tipo,
    }


def _evaluar_ventana(colector, datos_vent, empl):
    """Evalúa el colector hora a hora sobre la ventana de producción (S41, mejora 34).

    Vista previa de P3: corre el solver a la **velocidad de diseño** del
    módulo. El cálculo de producción de P7 (fuente de verdad) re-corre el
    colector al caudal real del sistema impuesto por el ventilador.

    Devuelve, además de las series horarias de T_salida / T_ambiente / POA,
    la serie de T del **absorbedor**, el **perfil T(x)** a mediodía solar del
    **primer día** de la ventana, y las marcas (POA máx + mediodía solar SPA)
    de **cada día**. De noche (POA < 50 W/m²) el aire no se calienta:
    ``T_salida = T_absorbedor = T_amb`` (no ``None``), para reflejar día y noche.
    """
    poa = _poa_serie(datos_vent, empl)
    tipo = colector.unidad.tipo_colector

    horas, T_sal_C, T_amb_C, T_abs_C, poa_list = [], [], [], [], []
    # Salidas por canal (solo difieren de la mezcla en Tipo 2, doble canal activo).
    T_sal_cs_C, T_sal_ci_C = [], []
    for ts, row in datos_vent.iterrows():
        I_g = float(poa.get(ts, 0.0))
        T_amb = float(row["T_amb_K"])
        v_w = float(row["WS_ms"])
        res = _correr_colector(colector, T_amb, I_g, v_w, pendiente_deg=empl.pendiente_colector_deg)

        horas.append(ts)
        T_amb_C.append(T_amb - 273.15)
        poa_list.append(I_g)
        if res is not None:
            T_sal_C.append(_T_salida_res(res, tipo) - 273.15)
            T_sal_cs_C.append(_T_salida_canal_K(res, tipo, "superior") - 273.15)
            T_sal_ci_C.append(_T_salida_canal_K(res, tipo, "inferior") - 273.15)
            T_abs_C.append(float(res.T_abs_K.mean()) - 273.15)
        else:
            # Noche / sin sol: el aire pasa sin calentarse (T → T_amb).
            T_sal_C.append(T_amb - 273.15)
            T_sal_cs_C.append(T_amb - 273.15)
            T_sal_ci_C.append(T_amb - 273.15)
            T_abs_C.append(T_amb - 273.15)

    # --- Marcas por día (POA máx en bin + mediodía solar SPA) y perfil T(x) ---
    marcas_poa_max: list = []
    marcas_mediodia: list = []
    x_noon = T_perfil_noon_C = None
    dias = sorted({ts.date() for ts in horas})
    for dia in dias:
        poa_dia = poa[poa.index.date == dia]
        if len(poa_dia) == 0 or float(poa_dia.max()) <= 50.0:
            continue
        marcas_poa_max.append((poa_dia.idxmax(), float(poa_dia.max())))
        transit = mediodia_solar_transit(
            dia, empl.latitud_deg, empl.longitud_deg, empl.zona_horaria
        )
        marcas_mediodia.append(transit)
        # Perfil T(x) sólo del primer día con sol de la ventana.
        if x_noon is None:
            idx_perfil = bin_horario_que_contiene(transit, datos_vent.index)
            if idx_perfil is not None and idx_perfil in datos_vent.index:
                fila = datos_vent.loc[idx_perfil]
                res_p = _correr_colector(
                    colector,
                    float(fila["T_amb_K"]),
                    float(poa.get(idx_perfil, 0.0)),
                    float(fila["WS_ms"]),
                    pendiente_deg=empl.pendiente_colector_deg,
                )
                if res_p is not None:
                    xs, T = _perfil_fluido(res_p, tipo)
                    x_noon, T_perfil_noon_C = xs, T - 273.15

    return {
        "horas": horas,
        "T_salida_C": T_sal_C,
        "T_salida_cs_C": T_sal_cs_C,
        "T_salida_ci_C": T_sal_ci_C,
        "T_amb_C": T_amb_C,
        "T_abs_C": T_abs_C,
        "poa": poa_list,
        "x_noon": x_noon,
        "T_perfil_noon_C": T_perfil_noon_C,
        "marcas_poa_max": marcas_poa_max,
        "marcas_mediodia": marcas_mediodia,
        "tipo": tipo,
    }


def _fig_T_salida_ventana(r, lapso_label):
    """Series horarias (día y noche) de T salida / T absorbedor / T ambiente / POA.

    Sobre la ventana completa, con marcas por día de POA máxima y de mediodía
    solar (tránsito SPA). De noche el aire no se calienta → T_salida ≈ T_amb.
    """
    horas = list(r["horas"])
    T_sal = r["T_salida_C"]
    T_abs = r.get("T_abs_C")
    T_amb = r["T_amb_C"]
    poa = r["poa"]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=horas,
            y=poa,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(245,166,35,0.15)",
            line=dict(color="rgba(245,166,35,0.5)", width=1),
            name=t("p3.figuras.poa_wm2"),
        ),
        secondary_y=True,
    )
    if T_abs is not None:
        fig.add_trace(
            go.Scatter(
                x=horas,
                y=T_abs,
                mode="lines",
                line=dict(color="#8e44ad", width=1.2),
                name=t("p3.figuras.t_absorbedor"),
            ),
            secondary_y=False,
        )
    fig.add_trace(
        go.Scatter(
            x=horas,
            y=T_sal,
            mode="lines",
            line=dict(color="#e05c2a", width=1.8),
            name=t("p3.figuras.t_salida"),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=horas,
            y=T_amb,
            mode="lines",
            line=dict(color="#1f77b4", width=1.2, dash="dash"),
            name=t("p3.figuras.t_ambiente"),
        ),
        secondary_y=False,
    )
    # Marcas por día: POA máxima (diamante) y mediodía solar SPA (triángulo).
    marcas_poa = r.get("marcas_poa_max") or []
    if marcas_poa:
        fig.add_trace(
            go.Scatter(
                x=[ts for ts, _ in marcas_poa],
                y=[val for _, val in marcas_poa],
                mode="markers",
                marker=dict(color="#f5a623", symbol="diamond", size=7),
                name=t("p3.figuras.poa_max_dia"),
            ),
            secondary_y=True,
        )
    marcas_md = r.get("marcas_mediodia") or []
    if marcas_md:
        fig.add_trace(
            go.Scatter(
                x=list(marcas_md),
                y=[0.0] * len(marcas_md),
                mode="markers",
                marker=dict(color="#c0392b", symbol="triangle-up", size=8),
                name=t("p3.figuras.mediodia_solar"),
            ),
            secondary_y=True,
        )
    fig.update_yaxes(title_text=t("graficas.eje.temperatura_c"), secondary_y=False)
    fig.update_yaxes(
        title_text=t("p3.figuras.poa_wm2"), color="#f5a623", secondary_y=True, rangemode="tozero"
    )
    fig.update_xaxes(tickformat="%d-%b")
    fig.update_layout(
        title_text=t("p3.figuras.titulo_ventana", lapso=lapso_label),
        height=420,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _fig_campo_colectores(rc) -> go.Figure:
    """Reparto de caudal/T por rama + perfil de velocidad del troncal (S41/S42).

    Panel superior: caudal por rama (barras) y T de salida por rama (línea).
    Panel inferior (si hay caño maestro): velocidad del aire a lo largo del
    troncal (extremo lejano → ventilador). Hace visible la compensación de
    sección — una sección creciente mantiene la velocidad acotada al acumular
    caudal; una sección chica constante la dispara cerca del ventilador.
    """
    n = len(rc.q_ramas_m3_s)
    bocas = list(range(1, n + 1))
    _vp = getattr(rc, "v_troncal_perfil_ms", None)
    tiene_perfil = _vp is not None and len(_vp) > 0

    if tiene_perfil:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
            row_heights=[0.62, 0.38],
            vertical_spacing=0.12,
            subplot_titles=(
                t("p3.figuras.subtitulo_reparto"),
                t("p3.figuras.subtitulo_v_troncal"),
            ),
        )
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=bocas,
            y=[float(q) * 1000.0 for q in rc.q_ramas_m3_s],
            name=t("p3.figuras.caudal_rama"),
            marker_color="#4caf50",
            opacity=0.75,
        ),
        secondary_y=False,
        **({"row": 1, "col": 1} if tiene_perfil else {}),
    )
    if rc.T_salida_ramas_K is not None:
        fig.add_trace(
            go.Scatter(
                x=bocas,
                y=[float(t) - 273.15 for t in rc.T_salida_ramas_K],
                mode="lines+markers",
                name=t("p3.figuras.t_salida_rama"),
                line=dict(color="#e05c2a", width=2),
                marker=dict(size=6),
            ),
            secondary_y=True,
            **({"row": 1, "col": 1} if tiene_perfil else {}),
        )

    if tiene_perfil:
        fig.add_trace(
            go.Scatter(
                x=bocas,
                y=[float(v) for v in _vp],
                mode="lines+markers",
                name=t("p3.figuras.v_troncal"),
                line=dict(color="#1f77b4", width=2),
                marker=dict(size=6),
                fill="tozeroy",
                fillcolor="rgba(31,119,180,0.12)",
            ),
            row=2,
            col=1,
        )
        fig.update_yaxes(
            title_text=t("p3.figuras.v_troncal"), row=2, col=1, rangemode="tozero", color="#1f77b4"
        )
        fig.update_xaxes(
            title_text=t("p3.figuras.eje_boca_tramo"),
            tickmode="linear",
            dtick=1,
            row=2,
            col=1,
        )
        fig.update_yaxes(title_text=t("p3.figuras.caudal_rama"), secondary_y=False, row=1, col=1)
        fig.update_yaxes(
            title_text=t("p3.figuras.eje_t_salida"),
            color="#e05c2a",
            secondary_y=True,
            row=1,
            col=1,
        )
    else:
        fig.update_xaxes(title_text=t("p3.figuras.eje_boca"), tickmode="linear", dtick=1)
        fig.update_yaxes(
            title_text=t("p3.figuras.caudal_rama"), secondary_y=False, rangemode="tozero"
        )
        fig.update_yaxes(title_text=t("p3.figuras.eje_t_salida"), color="#e05c2a", secondary_y=True)

    fig.update_layout(
        title_text=t("p3.figuras.titulo_campo"),
        height=560 if tiene_perfil else 400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _evaluar_anual(colector, datos_local, empl, anio):
    """Para cada mes: evalúa el colector en el bin horario que contiene el
    mediodía solar verdadero del día 15 (representativo).

    Cambio respecto a la versión anterior: el bin de evaluación se elige
    por el tránsito SPA (independiente de la orientación del colector),
    no por POA máxima. Esto evita que un colector con orientación rara
    desplace artificialmente la evaluación a horas tarde / temprano.
    """
    poa_all = _poa_serie(datos_local, empl)
    tipo = colector.unidad.tipo_colector
    meses_abbr = t("graficas.meses_abbr").split(",")

    meses, T_sal_C, T_amb_C, poa_noon_list, perfiles_C = [], [], [], [], []
    x_m = None

    for mes_num in range(1, 13):
        datos_dia = None
        target_dia = None
        for delta in [0, 1, -1, 2, -2, 3, -3]:
            try:
                target_try = _date_type(anio, mes_num, 15 + delta)
                mask = datos_local.index.date == target_try
                if mask.any():
                    datos_dia = datos_local[mask]
                    target_dia = target_try
                    break
            except ValueError:
                continue
        if datos_dia is None or len(datos_dia) == 0:
            continue

        poa_dia = poa_all[datos_dia.index]
        if poa_dia.max() < 50:
            continue

        # Bin que contiene el mediodía solar verdadero (no idxmax(POA)).
        transit = mediodia_solar_transit(
            target_dia,
            empl.latitud_deg,
            empl.longitud_deg,
            empl.zona_horaria,
        )
        idx_noon = bin_horario_que_contiene(transit, datos_dia.index)
        row = datos_dia.loc[idx_noon]
        I_g = float(poa_dia[idx_noon])
        T_amb = float(row["T_amb_K"])
        v_w = float(row["WS_ms"])

        res = _correr_colector(colector, T_amb, I_g, v_w, pendiente_deg=empl.pendiente_colector_deg)
        if res is None:
            continue

        meses.append(meses_abbr[mes_num - 1])
        T_sal_C.append(_T_salida_res(res, tipo) - 273.15)
        T_amb_C.append(T_amb - 273.15)
        poa_noon_list.append(I_g)

        x_arr, T_arr = _perfil_fluido(res, tipo)
        if x_m is None:
            x_m = x_arr
        perfiles_C.append(T_arr - 273.15)

    return {
        "meses": meses,
        "T_salida_noon_C": T_sal_C,
        "T_amb_noon_C": T_amb_C,
        "poa_noon": poa_noon_list,
        "x_m": x_m,
        "perfiles_C": perfiles_C,
        "tipo": tipo,
    }


# --- Figuras ---


def _add_vline_datetime(fig, *, x, text, color, dash, width, xanchor):
    """Línea vertical + anotación en eje X de tipo datetime.

    Workaround de un bug de Plotly: add_vline con annotation_text falla con
    TypeError cuando x es un Timestamp/string porque internamente intenta
    sum([x, x]) para posicionar la anotación. Separamos shape y annotation.
    """
    fig.add_shape(
        type="line",
        xref="x",
        yref="paper",
        x0=x,
        x1=x,
        y0=0,
        y1=1,
        line=dict(color=color, dash=dash, width=width),
    )
    fig.add_annotation(
        x=x,
        y=1.0,
        xref="x",
        yref="paper",
        text=text,
        showarrow=False,
        xanchor=xanchor,
        yanchor="bottom",
        font=dict(color=color, size=11),
    )


def _fig_T_salida_dia(r, fecha_label):
    horas = r["horas"]
    T_sal = r["T_salida_C"]
    T_amb = r["T_amb_C"]
    poa = r["poa"]

    h_sol = [h for h, t in zip(horas, T_sal) if t is not None]
    t_sol = [t for t in T_sal if t is not None]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=list(horas),
            y=poa,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(245,166,35,0.15)",
            line=dict(color="rgba(245,166,35,0.5)", width=1),
            name=t("p3.figuras.poa_wm2"),
        ),
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(
            x=h_sol,
            y=t_sol,
            mode="lines+markers",
            line=dict(color="#e05c2a", width=2),
            marker=dict(size=4),
            name=t("p3.figuras.t_salida"),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=list(horas),
            y=T_amb,
            mode="lines",
            line=dict(color="#1f77b4", width=1.5, dash="dash"),
            name=t("p3.figuras.t_ambiente"),
        ),
        secondary_y=False,
    )

    if r["hora_transit"] is not None:
        _add_vline_datetime(
            fig,
            x=r["hora_transit"],
            text=t("p3.figuras.marca_mediodia", hora=r["hora_transit"].strftime("%H:%M")),
            color="#9c27b0",
            dash="dot",
            width=1.8,
            xanchor="left",
        )
    if r["hora_poa_max"] is not None:
        if (
            r["hora_transit"] is None
            or abs((r["hora_poa_max"] - r["hora_transit"]).total_seconds()) > 15 * 60
        ):
            _add_vline_datetime(
                fig,
                x=r["hora_poa_max"],
                text=t("p3.figuras.marca_poa_max", hora=r["hora_poa_max"].strftime("%H:%M")),
                color="#ff7f0e",
                dash="dash",
                width=1.3,
                xanchor="right",
            )

    fig.update_yaxes(title_text=t("graficas.eje.temperatura_c"), secondary_y=False)
    fig.update_yaxes(
        title_text=t("p3.figuras.poa_wm2"), color="#f5a623", secondary_y=True, rangemode="tozero"
    )
    fig.update_xaxes(tickformat="%H:%M")
    fig.update_layout(
        title_text=t("p3.figuras.titulo_salida_dia", fecha=fecha_label),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _fig_T_fluido_dia(r, fecha_label):
    x = r["x_noon"]
    T = r["T_perfil_noon_C"]
    if x is None or T is None:
        return None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(x),
            y=list(T),
            mode="lines",
            line=dict(color="#e05c2a", width=2),
            name=t("p3.figuras.t_fluido"),
        )
    )
    fig.add_hline(
        y=float(T[0]),
        line=dict(color="#1f77b4", dash="dash", width=1),
        annotation_text=t("p3.figuras.t_entrada_annot", v=T[0]),
    )
    fig.update_xaxes(title_text=t("p3.figuras.eje_x_colector"))
    fig.update_yaxes(title_text=t("p3.figuras.eje_t_fluido"))
    fig.update_layout(
        title_text=t("p3.figuras.titulo_perfil_dia", fecha=fecha_label),
        height=350,
        showlegend=True,
    )
    return fig


def _fig_T_salida_anual(r):
    meses = r["meses"]
    T_sal = r["T_salida_noon_C"]
    T_amb = r["T_amb_noon_C"]
    poa = r["poa_noon"]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=meses,
            y=poa,
            name=t("p3.figuras.poa_mediodia"),
            marker=dict(
                color="rgba(245,166,35,0.2)", line=dict(color="rgba(245,166,35,0.5)", width=1)
            ),
        ),
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(
            x=meses,
            y=T_sal,
            mode="lines+markers",
            line=dict(color="#e05c2a", width=2),
            marker=dict(symbol="circle", size=6),
            name=t("p3.figuras.t_salida_mediodia"),
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=meses,
            y=T_amb,
            mode="lines+markers",
            line=dict(color="#1f77b4", width=1.5, dash="dash"),
            marker=dict(symbol="square", size=4),
            name=t("p3.figuras.t_amb_mediodia"),
        ),
        secondary_y=False,
    )

    fig.update_yaxes(title_text=t("graficas.eje.temperatura_c"), secondary_y=False)
    fig.update_yaxes(
        title_text=t("p3.figuras.poa_wm2"), color="#f5a623", secondary_y=True, rangemode="tozero"
    )
    fig.update_layout(
        title_text=t("p3.figuras.titulo_salida_anual"),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _fig_T_fluido_anual(r):
    x_m = r["x_m"]
    perfiles = r["perfiles_C"]
    meses = r["meses"]
    if x_m is None or not perfiles:
        return None

    fig = go.Figure()
    for i, (mes, T) in enumerate(zip(meses, perfiles)):
        color = _COLORES_MESES[i % len(_COLORES_MESES)]
        fig.add_trace(
            go.Scatter(
                x=list(x_m),
                y=list(T),
                mode="lines",
                line=dict(color=color, width=1.8),
                name=mes,
            )
        )

    fig.update_xaxes(title_text=t("p3.figuras.eje_x_colector"))
    fig.update_yaxes(title_text=t("p3.figuras.eje_t_fluido"))
    fig.update_layout(
        title_text=t("p3.figuras.titulo_perfil_anual"),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ---------------------------------------------------------------------------
# Validación con datos medidos (mejora 38, fase 2)
# ---------------------------------------------------------------------------


def _config_referencia_desde_widgets(
    *, col_ts, col_val, unidad, zona, conv, hoja, fila_enc, fecha_fija=None
):
    """Arma la ConfigReferencia desde las selecciones de los widgets (puro).

    Returns:
        ``core.validacion.ConfigReferencia`` (valida en __post_init__).
    """
    from core.validacion import ConfigReferencia

    return ConfigReferencia(
        columna_timestamp=col_ts,
        columna_valor=col_val,
        variable="T_salida_colector",
        unidad=unidad,
        zona_horaria=zona,
        convencion_timestamp=conv,
        hoja=hoja,
        fila_encabezado=fila_enc,
        fecha_fija=fecha_fija,
    )


def _filas_metricas(metricas) -> list[tuple[str, float, str]]:
    """Convierte MetricasAjuste en filas ``(id, valor, unidad)`` para la tabla (puro).

    La unidad ``"C"`` marca métricas en grados (RMSE/MBE/MAE — invariantes al
    offset K↔°C); ``""`` marca adimensionales (R²/NSE/d).
    """
    return [
        ("rmse", metricas.rmse, "C"),
        ("mbe", metricas.mbe, "C"),
        ("mae", metricas.mae, "C"),
        ("r2", metricas.r2, ""),
        ("nse", metricas.nse, ""),
        ("d", metricas.d_willmott, ""),
    ]


def _series_simuladas_colector(proyecto, senal, clima_forzante=None, salida="mezcla"):
    """Corre el colector sobre el período de la señal medida (fase 2 / 2b).

    Fuente del clima de forzado:
    - ``clima_forzante`` provisto (fase 2b): se usa **ese** df (clima medido del
      propio ensayo — Ta + POA a paso fino) → validación de colector aislado.
    - None: se recorta el clima de P2 al rango de la referencia (fase 2).

    En ambos casos evalúa el colector paso a paso (``_evaluar_ventana``).

    Args:
        proyecto: Proyecto con colector, clima y emplazamiento.
        senal: ``core.validacion.SenalReferencia`` (índice UTC).
        clima_forzante: DataFrame de forzado (COLUMNAS del colector + ``POA_med_Wm2``)
            o None para usar el clima de P2.
        salida: Canal de salida a comparar — "mezcla" | "superior" | "inferior"
            (solo distingue en Tipo 2; en el resto colapsan a la única salida).

    Returns:
        ``(t_sim, y_sim_K)`` — DatetimeIndex UTC y array de T de salida [K]; o
        ``(None, None)`` si no hay clima que cubra el período.
    """
    empl = proyecto.emplazamiento
    if proyecto.colector is None:
        return None, None

    idx_ref = senal.serie.dropna().index
    if len(idx_ref) == 0:
        return None, None
    t0, t1 = idx_ref[0], idx_ref[-1]

    if clima_forzante is not None:
        idx = clima_forzante.index
        slice_ref = clima_forzante.loc[(idx >= t0) & (idx <= t1)]
    else:
        clima = getattr(proyecto, "clima", None)
        if clima is None or getattr(clima, "datos", None) is None:
            return None, None
        datos = clima.datos
        idx = datos.index
        if idx.tz is None:
            datos = datos.tz_localize("UTC")
            idx = datos.index
        slice_ref = datos.loc[(idx >= t0) & (idx <= t1)]
    if len(slice_ref) < 2:
        return None, None

    ev = _evaluar_ventana(proyecto.colector, slice_ref, empl)
    clave = {"superior": "T_salida_cs_C", "inferior": "T_salida_ci_C"}.get(salida, "T_salida_C")
    t_sim = pd.DatetimeIndex(ev["horas"])
    y_sim_K = np.asarray(ev[clave], dtype=float) + 273.15
    return t_sim, y_sim_K


def _fig_overlay_validacion(ts, y_med_C, y_sim_C, *, medido_lbl, simulado_lbl, titulo, y_lbl):
    """Overlay medido vs simulado de la T de salida del colector."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=y_med_C,
            mode="markers",
            name=medido_lbl,
            marker=dict(size=5, color="#d62728"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=y_sim_C,
            mode="lines",
            name=simulado_lbl,
            line=dict(color="#1f77b4", width=2),
        )
    )
    fig.update_layout(
        title=titulo,
        xaxis_title="",
        yaxis_title=y_lbl,
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def _render_validacion_colector(proyecto) -> None:
    """Sección de P3: valida la T de salida del colector contra datos medidos."""
    from calculos import clima_medido as cm
    from calculos.ingesta_referencia import evaluar_ajuste, ingerir_referencia
    from core.proyecto import Tipologia
    from core.validacion import CONVENCIONES_TIMESTAMP
    from ui.componentes.serializacion import limpiar_session_state_prefijo

    empl = proyecto.emplazamiento

    with st.expander(t("p3.validacion.titulo"), expanded=False):
        st.caption(t("p3.validacion.intro"))

        if proyecto.colector is None or getattr(proyecto.configuracion, "tipologia", None) == (
            Tipologia.CAJA
        ):
            st.info(t("p3.validacion.sin_colector"))
            return
        # Sin clima en P2 no se bloquea: se puede forzar con el clima del propio
        # archivo (fase 2b). Solo se avisa que hará falta una de las dos fuentes.
        if getattr(proyecto, "clima", None) is None or proyecto.clima.datos is None:
            st.caption(t("p3.validacion.sin_clima"))

        arch = st.session_state.get("p3_val_archivo")
        if arch is None:
            subido = st.file_uploader(
                t("p3.validacion.uploader.label"),
                type=["csv", "txt", "xls", "xlsx"],
                key="p3_val_uploader",
                help=t("p3.validacion.uploader.help"),
            )
            if subido is not None:
                contenido = subido.read()
                st.session_state["p3_val_archivo"] = {
                    "nombre": subido.name,
                    "bytes": contenido,
                    "hash": cm.hash_archivo(contenido),
                }
                st.session_state.pop("p3_val_uploader", None)
                st.rerun()
            return

        c_a, c_b = st.columns([4, 1])
        with c_a:
            st.markdown(
                t(
                    "p3.validacion.archivo_cargado",
                    nombre=arch["nombre"],
                    kb=max(len(arch["bytes"]) // 1024, 1),
                )
            )
        with c_b:
            if st.button(t("p3.validacion.quitar"), key="p3_val_quitar"):
                limpiar_session_state_prefijo(st.session_state, "p3_val_")
                limpiar_session_state_prefijo(st.session_state, "_p3_val_")
                st.rerun()

        try:
            hojas = cm.listar_hojas(arch["bytes"], arch["nombre"])
        except (ValueError, RuntimeError) as exc:
            st.error(t("p3.validacion.error", err=exc))
            return
        hoja = None
        c1, c2 = st.columns([3, 1])
        if hojas:
            with c1:
                hoja = st.selectbox(t("p2.medido.hoja.label"), options=hojas, key="p3_val_hoja")
        with c2:
            fila_enc = int(
                st.number_input(
                    t("p2.medido.fila_enc.label"),
                    min_value=0,
                    max_value=50,
                    value=0,
                    key="p3_val_fila_enc",
                    help=t("p2.medido.fila_enc.help"),
                )
            )

        clave_tabla = (arch["hash"], hoja, fila_enc)
        cache = st.session_state.get("_p3_val_tabla_cache")
        if cache is None or cache[0] != clave_tabla:
            try:
                tabla = cm.leer_tabla(
                    arch["bytes"], arch["nombre"], hoja=hoja, fila_encabezado=fila_enc
                )
            except (ValueError, RuntimeError) as exc:
                st.error(t("p3.validacion.error", err=exc))
                return
            st.session_state["_p3_val_tabla_cache"] = (clave_tabla, tabla)
            st.session_state.pop("p3_val_resultado", None)
        tabla = st.session_state["_p3_val_tabla_cache"][1]

        with st.expander(t("p3.validacion.preview_titulo"), expanded=False):
            st.dataframe(tabla.head(12))

        columnas = [str(c) for c in tabla.columns]
        st.markdown(t("p3.validacion.mapeo.titulo"))
        col_ts = st.selectbox(
            t("p3.validacion.mapeo.timestamp"), options=columnas, key="p3_val_col_ts"
        )
        col_val = st.selectbox(
            t("p3.validacion.mapeo.valor"), options=columnas, key="p3_val_col_val"
        )
        # Canal de salida simulado a comparar (solo Tipo 2 distingue superior/inferior).
        salida = "mezcla"
        if getattr(proyecto.colector.unidad, "tipo_colector", 1) == 2:
            salida = st.selectbox(
                t("p3.validacion.salida.label"),
                options=list(CANALES_SALIDA),
                format_func=lambda s: t(f"p3.validacion.salida.{s}"),
                key="p3_val_salida",
                help=t("p3.validacion.salida.help"),
            )
        c_u, c_c = st.columns(2)
        with c_u:
            unidad = st.selectbox(
                t("p2.medido.mapeo.unidad"),
                options=["C", "K", "F"],
                format_func=lambda u: t(f"p2.medido.unidad.{u}"),
                key="p3_val_unidad",
            )
        with c_c:
            conv = st.radio(
                t("p2.medido.convencion.label"),
                options=list(CONVENCIONES_TIMESTAMP),
                format_func=lambda k: t(f"p2.medido.convencion.{k}"),
                key="p3_val_conv",
                horizontal=True,
            )
        from ui.p2_emplazamiento import _ZONAS_HORARIAS

        zona = st.selectbox(
            t("p2.medido.tz.label"),
            options=_ZONAS_HORARIAS,
            index=(
                _ZONAS_HORARIAS.index(empl.zona_horaria)
                if empl.zona_horaria in _ZONAS_HORARIAS
                else 0
            ),
            key="p3_val_tz",
        )

        # --- Fecha fija (archivos con timestamp de solo hora, fase 2b) ---
        fecha_fija = None
        if st.checkbox(t("p3.validacion.fecha_fija.check"), key="p3_val_usar_fecha"):
            from datetime import date as _d

            fecha_fija = st.date_input(
                t("p3.validacion.fecha_fija.label"),
                value=_d(2007, 6, 9),
                min_value=_d(1990, 1, 1),
                max_value=_d.today(),
                key="p3_val_fecha",
                help=t("p3.validacion.fecha_fija.help"),
            )

        # --- Forzar con el clima medido del propio archivo (fase 2b) ---
        forzar_medido = st.checkbox(
            t("p3.validacion.forzar.check"),
            key="p3_val_forzar",
            help=t("p3.validacion.forzar.help"),
        )
        col_ta = col_poa = None
        uni_ta, uni_poa = "C", "W_m2"
        if forzar_medido:
            f_ta, f_poa = st.columns(2)
            with f_ta:
                col_ta = st.selectbox(
                    t("p3.validacion.forzar.col_ta"), options=columnas, key="p3_val_col_ta"
                )
                uni_ta = st.selectbox(
                    t("p2.medido.mapeo.unidad"),
                    options=["C", "K", "F"],
                    format_func=lambda u: t(f"p2.medido.unidad.{u}"),
                    key="p3_val_uni_ta",
                )
            with f_poa:
                col_poa = st.selectbox(
                    t("p3.validacion.forzar.col_poa"), options=columnas, key="p3_val_col_poa"
                )
                uni_poa = st.selectbox(
                    t("p2.medido.mapeo.unidad"),
                    options=["W_m2", "kW_m2"],
                    format_func=lambda u: t(f"p2.medido.unidad.{u}"),
                    key="p3_val_uni_poa",
                )

        if st.button(t("p3.validacion.procesar"), type="primary", key="p3_val_procesar"):
            try:
                cfg = _config_referencia_desde_widgets(
                    col_ts=col_ts,
                    col_val=col_val,
                    unidad=unidad,
                    zona=zona,
                    conv=conv,
                    hoja=hoja,
                    fila_enc=fila_enc,
                    fecha_fija=fecha_fija,
                )
                with st.spinner(t("p3.validacion.spinner")):
                    senal = ingerir_referencia(tabla, cfg)
                    clima_forz = None
                    if forzar_medido:
                        from calculos.ingesta_referencia import ingerir_clima_forzante

                        clima_forz = ingerir_clima_forzante(
                            tabla,
                            cfg,
                            columna_T_amb=col_ta,
                            unidad_T_amb=uni_ta,
                            columna_POA=col_poa,
                            unidad_POA=uni_poa,
                        )
                    t_sim, y_sim_K = _series_simuladas_colector(
                        proyecto, senal, clima_forzante=clima_forz, salida=salida
                    )
                st.session_state["p3_val_resultado"] = {
                    "senal": senal,
                    "t_sim": t_sim,
                    "y_sim_K": y_sim_K,
                    "forzado_medido": forzar_medido,
                    "clima_forzante": clima_forz,
                    "salida": salida,
                }
            except (ValueError, RuntimeError) as exc:
                st.error(t("p3.validacion.error", err=exc))
                st.session_state.pop("p3_val_resultado", None)
                return

        res = st.session_state.get("p3_val_resultado")
        if res is None:
            return

        senal = res["senal"]
        for adv in senal.advertencias:
            st.warning(adv)
        st.caption(
            t(
                "p3.validacion.senal_ok",
                n=int(senal.serie.notna().sum()),
                freq=int(round(senal.frecuencia_nativa_s / 60.0)),
            )
        )
        st.caption(
            t("p3.validacion.forzado.medido")
            if res.get("forzado_medido")
            else t("p3.validacion.forzado.p2")
        )

        if res["t_sim"] is None:
            st.warning(t("p3.validacion.sin_cobertura"))
            return

        metricas, y_med_K, y_sim_al_K, ts = evaluar_ajuste(senal, res["t_sim"], res["y_sim_K"])
        if metricas is None:
            st.warning(t("p3.validacion.sin_solape"))
            return

        st.plotly_chart(
            _fig_overlay_validacion(
                ts,
                y_med_K - 273.15,
                y_sim_al_K - 273.15,
                medido_lbl=t("p3.validacion.grafica.medido"),
                simulado_lbl=t("p3.validacion.grafica.simulado"),
                titulo=t("p3.validacion.grafica.titulo"),
                y_lbl=t("p3.validacion.grafica.y_label"),
            ),
            width="stretch",
        )

        st.markdown(t("p3.validacion.metricas_titulo"))
        cols = st.columns(3)
        for i, (mid, val, uni) in enumerate(_filas_metricas(metricas)):
            valor_fmt = f"{val:+.2f} °C" if uni == "C" else f"{val:.3f}"
            cols[i % 3].metric(t(f"p3.validacion.metrica.{mid}"), valor_fmt)
        st.caption(t("p3.validacion.n_pares", n=metricas.n_pares))
        st.caption(t("p3.validacion.interpretacion"))

        # --- Calibración (fase 3) ---
        _render_calibracion_colector(
            proyecto, senal, res.get("clima_forzante"), res.get("salida", "mezcla")
        )


# Parámetros del colector ofrecidos para calibración (id del catálogo de barridos
# → clave i18n del rótulo). Se calibra un escalar 1-D contra el medido.
_PARAMS_CALIBRABLES: tuple[tuple[str, str], ...] = (
    ("velocidad_diseno", "velocidad_diseno"),
    ("largo_colector", "largo_colector"),
)

# Id del parámetro calibrado → key del number_input de geometría en P3, para
# refrescar el campo tras "aplicar óptimo" (Streamlit prioriza el session_state
# sobre ``value=``, así que se borra la key para que re-lea del proyecto).
_WIDGET_KEY_POR_PARAM: dict[str, str] = {
    "velocidad_diseno": "p3_velocidad",
    "largo_colector": "p3_largo",
}


def _fig_curva_calibracion(res_cal, *, x_lbl, y_lbl, titulo, optimo_lbl):
    """Curva de la función objetivo vs el parámetro, con marca en el óptimo."""
    xs = [p.valor for p in res_cal.puntos if p.objetivo is not None]
    ys = [p.objetivo for p in res_cal.puntos if p.objetivo is not None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color="#1f77b4")))
    if res_cal.valor_optimo is not None:
        y_opt = min(ys)
        fig.add_trace(
            go.Scatter(
                x=[res_cal.valor_optimo],
                y=[y_opt],
                mode="markers",
                name=optimo_lbl,
                marker=dict(size=13, color="#2ca02c", symbol="star"),
            )
        )
    fig.update_layout(title=titulo, xaxis_title=x_lbl, yaxis_title=y_lbl, height=360)
    return fig


def _render_calibracion_colector(proyecto, senal, clima_forz, salida="mezcla") -> None:
    """Calibra un parámetro del colector minimizando el ajuste contra el medido."""
    import copy

    from calculos.barrido_parametrico import aplicar_parametro
    from calculos.calibracion import calibrar_1d
    from calculos.ingesta_referencia import evaluar_ajuste

    st.divider()
    st.markdown(t("p3.calibracion.titulo"))
    st.caption(t("p3.calibracion.intro"))

    param_ids = [pid for pid, _ in _PARAMS_CALIBRABLES]
    parametro_id = st.selectbox(
        t("p3.calibracion.parametro"),
        options=param_ids,
        format_func=lambda pid: t(f"p3.calibracion.param.{dict(_PARAMS_CALIBRABLES)[pid]}"),
        key="p3_cal_param",
    )
    c1, c2, c3, c4 = st.columns(4)
    vmin = float(c1.number_input(t("p3.calibracion.min"), value=1.0, key="p3_cal_min"))
    vmax = float(c2.number_input(t("p3.calibracion.max"), value=10.0, key="p3_cal_max"))
    n_pts = int(
        c3.number_input(t("p3.calibracion.n"), min_value=3, max_value=40, value=10, key="p3_cal_n")
    )
    objetivo = c4.selectbox(
        t("p3.calibracion.objetivo"),
        options=["rmse", "mbe_abs", "mae"],
        format_func=lambda o: t(f"p3.calibracion.obj.{o}"),
        key="p3_cal_obj",
    )

    if vmax <= vmin:
        st.warning(t("p3.calibracion.rango_invalido"))
        return

    if st.button(t("p3.calibracion.correr"), key="p3_cal_correr"):
        valores = np.linspace(vmin, vmax, n_pts)

        def _evaluar(valor):
            proy2 = copy.copy(proyecto)
            proy2.colector = copy.deepcopy(proyecto.colector)
            try:
                aplicar_parametro(proy2, parametro_id, float(valor))
            except (ValueError, KeyError):
                return None
            t_sim, y_sim_K = _series_simuladas_colector(
                proy2, senal, clima_forzante=clima_forz, salida=salida
            )
            if t_sim is None:
                return None
            met, *_ = evaluar_ajuste(senal, t_sim, y_sim_K)
            return met

        with st.spinner(t("p3.calibracion.spinner")):
            res_cal = calibrar_1d(valores, _evaluar, parametro=parametro_id, objetivo=objetivo)
        st.session_state["p3_cal_resultado"] = res_cal

    res_cal = st.session_state.get("p3_cal_resultado")
    if res_cal is None:
        return
    if res_cal.valor_optimo is None:
        st.warning(t("p3.calibracion.sin_optimo"))
        return

    st.plotly_chart(
        _fig_curva_calibracion(
            res_cal,
            x_lbl=t(f"p3.calibracion.param.{dict(_PARAMS_CALIBRABLES)[res_cal.parametro]}"),
            y_lbl=t(f"p3.calibracion.obj.{res_cal.objetivo_nombre}"),
            titulo=t("p3.calibracion.grafica_titulo"),
            optimo_lbl=t("p3.calibracion.optimo"),
        ),
        width="stretch",
    )
    mo = res_cal.metricas_optimo
    st.success(
        t(
            "p3.calibracion.resultado",
            valor=f"{res_cal.valor_optimo:.3g}",
            rmse=f"{mo.rmse:.2f}",
            mbe=f"{mo.mbe:+.2f}",
            r2=f"{mo.r2:.3f}",
        )
    )
    if st.button(t("p3.calibracion.aplicar"), key="p3_cal_aplicar"):
        try:
            aplicar_parametro(proyecto, res_cal.parametro, float(res_cal.valor_optimo))
            # Refrescar el number_input de geometría correspondiente: se deja el
            # valor pendiente para fijarlo al TOPE del próximo render (antes de que
            # el widget se instancie). Es robusto: no depende de re-leer ``value=``
            # ni del orden en que se reconstruye el colector desde los widgets.
            _wkey = _WIDGET_KEY_POR_PARAM.get(res_cal.parametro)
            if _wkey is not None:
                st.session_state["_p3_pending_widget"] = {_wkey: float(res_cal.valor_optimo)}
            st.session_state.pop("p3_val_resultado", None)
            st.session_state.pop("p3_cal_resultado", None)
            st.success(t("p3.calibracion.aplicado"))
            st.rerun()
        except (ValueError, KeyError) as exc:
            st.error(t("p3.validacion.error", err=exc))


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la pestaña 3: Colector Solar."""

    st.header(t("p3.header"))
    boton_manual(SLUG_POR_SECCION["p3"])

    proyecto = st.session_state.proyecto
    tipologia = proyecto.configuracion.tipologia

    # Aplicar cambios pendientes a widgets de geometría (calibración → "aplicar
    # óptimo"). Se fija el session_state ANTES de instanciar los number_input, que
    # es la forma robusta de actualizar un widget desde un botón de otra sección
    # (no depende de re-leer ``value=`` ni del orden de reconstrucción del colector).
    _pend = st.session_state.pop("_p3_pending_widget", None)
    if _pend:
        for _k, _v in _pend.items():
            st.session_state[_k] = _v

    # La tipología CAJA no tiene colector externo
    if tipologia == Tipologia.CAJA:
        st.info(t("p3.caja_no_aplica"))
        return

    # Inicializar colector si es la primera vez
    if proyecto.colector is None:
        proyecto.colector = Colector()

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander(t("p3.cargar.titulo"), expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            t("p3.cargar.uploader"),
            type=["json"],
            key="p3_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "colector")
            if err:
                st.error(f"❌ {err}")  # i18n: exento (mensaje de serializacion, F4)
            else:
                try:
                    col_cargado = _from_json_colector(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(t("p3.cargar.error_reconstruccion", exc=exc))
                else:
                    proyecto.colector = col_cargado
                    # Backward compat: .json viejos guardaban chimenea como
                    # parte del snapshot de colector. La restauramos a
                    # proyecto.chimenea para no perder esa configuración al
                    # cargar archivos previos a la migración.
                    chim_data = data.get("chimenea")
                    if chim_data is not None:
                        try:
                            proyecto.chimenea = Chimenea(
                                diametro_m=float(chim_data["diametro_m"]),
                                altura_m=float(chim_data["altura_m"]),
                                id_material=chim_data["id_material"],
                            )
                        except (KeyError, ValueError, TypeError):
                            pass  # chimenea malformada en el .json viejo: ignorar
                    # Limpiar widgets cacheados y resultados viejos de P3.
                    # Preservamos la clave del file_uploader para no entrar
                    # en bucle de "archivo todavía está cargado".
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p3_")
                    # Volvemos a poner el archivo (sin él, file_uploader
                    # quedaría en estado "no hay archivo" y al hacer
                    # rerun la siguiente render trataría de cargar de nuevo).
                    st.session_state.pop("p3_cargar_json", None)
                    st.success(t("p3.cargar.exito", n=n_borr))
                    st.rerun()

    colector: Colector = proyecto.colector

    # -----------------------------------------------------------------------
    # Sección 0: Tipo de colector
    # -----------------------------------------------------------------------

    with st.expander(t("p3.tipo.titulo"), expanded=False):
        ids_tipo = list(_IDS_TIPOS_COLECTOR)
        idx_tipo = (
            ids_tipo.index(colector.unidad.tipo_colector)
            if colector.unidad.tipo_colector in ids_tipo
            else 0
        )
        tipo_colector = st.selectbox(
            t("p3.tipo.label"),
            options=ids_tipo,
            index=idx_tipo,
            format_func=lambda x: t(f"p3.tipo.opcion.{x}"),
            key="p3_tipo_colector",
        )
        st.info(t(f"p3.tipo.ayuda.{tipo_colector}"))

        with st.expander(t("p3.tipo.esquema_titulo"), expanded=False):
            mostrar_esquema(
                "colectores_seccion_transversal",
                max_ancho_px=600,
                caption=t("p3.tipo.esquema_caption"),
            )

    # -----------------------------------------------------------------------
    # Sección 1: Colector unitario — materiales
    # -----------------------------------------------------------------------

    with st.expander(t("p3.materiales.titulo"), expanded=False):

        st.subheader(t("p3.materiales.cubierta_titulo"))
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_cub = {
                k: v for k, v in _opciones_material(catalogo.CUBIERTAS).items() if k != _ID_USUARIO
            }
            opciones_cub[_ID_USUARIO] = t("p3.materiales.usuario")
            ids_cub = list(opciones_cub.keys())
            idx_cub = (
                ids_cub.index(colector.unidad.id_cubierta)
                if colector.unidad.id_cubierta in ids_cub
                else 0
            )
            id_cubierta = st.selectbox(
                t("p3.materiales.cubierta_label"),
                options=ids_cub,
                index=idx_cub,
                format_func=lambda x: opciones_cub[x],
                key="p3_id_cubierta",
            )
        with c2:
            # Espesor de cubierta. Para el policarbonato alveolar se ofrecen las
            # medidas de mercado (4/6/8/10/16 mm) del mapa k(espesor) del
            # catálogo, que además fijan el k efectivo según el espesor elegido.
            mapa_k_pc = catalogo.CUBIERTAS.get(id_cubierta, {}).get("k_efectivo_por_espesor_mm")
            opciones_cub_mm = (
                [(float(mm), f"{float(mm):.0f} mm") for mm in sorted(mapa_k_pc)]
                if mapa_k_pc
                else None
            )
            espesor_cubierta_mm = selector_espesor_mm(
                t("p3.materiales.espesor_mm"),
                colector.unidad.espesor_cubierta_m,
                key="p3_esp_cubierta",
                opciones_mm=opciones_cub_mm,
                min_mm=1.0,
                max_mm=40.0,
                step=0.5,
            )
            # k efectivo override: solo si el espesor coincide con una medida de
            # mercado del mapa; para "Otro" o cubiertas sin mapa → None (catálogo).
            k_cubierta_override = (
                mapa_k_pc.get(int(round(espesor_cubierta_mm))) if mapa_k_pc else None
            )
            n_cubiertas = st.selectbox(
                t("p3.materiales.n_cubiertas.label"),
                options=[1, 2],
                index=colector.unidad.n_cubiertas - 1,
                key="p3_n_cubiertas",
                help=t("p3.materiales.n_cubiertas.help"),
            )
            if n_cubiertas == 2:
                esp_cub_cub_mm = st.number_input(
                    t("p3.materiales.esp_cub_cub.label"),
                    min_value=10.0,
                    max_value=50.0,
                    value=colector.unidad.espaciado_entre_cubiertas_m * 1000,
                    step=1.0,
                    key="p3_esp_cub_cub",
                    help=t("p3.materiales.esp_cub_cub.help"),
                )
            else:
                esp_cub_cub_mm = colector.unidad.espaciado_entre_cubiertas_m * 1000
        if id_cubierta == _ID_USUARIO:
            catalogo.CUBIERTAS[_ID_USUARIO] = _inputs_cubierta_usuario("p3_ucub")
        _tabla_propiedades_cubierta(id_cubierta)

        st.divider()
        st.subheader(t("p3.materiales.placa_titulo"))
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_pla = {
                k: v for k, v in _opciones_material(catalogo.PLACAS).items() if k != _ID_USUARIO
            }
            opciones_pla[_ID_USUARIO] = t("p3.materiales.usuario")
            ids_pla = list(opciones_pla.keys())
            idx_pla = (
                ids_pla.index(colector.unidad.id_placa)
                if colector.unidad.id_placa in ids_pla
                else 0
            )
            id_placa = st.selectbox(
                t("p3.materiales.placa_label"),
                options=ids_pla,
                index=idx_pla,
                format_func=lambda x: opciones_pla[x],
                key="p3_id_placa",
            )
        with c2:
            espesor_placa_mm = st.number_input(
                t("p3.materiales.espesor_mm"),
                min_value=0.3,
                max_value=5.0,
                value=colector.unidad.espesor_placa_m * 1000,
                step=0.1,
                key="p3_esp_placa",
                help=t("p3.materiales.placa_espesor_help"),
            )
        if id_placa == _ID_USUARIO:
            catalogo.PLACAS[_ID_USUARIO] = _inputs_placa_usuario("p3_upla")
        _tabla_propiedades_placa(id_placa)

        st.divider()
        st.subheader(t("p3.materiales.aislante_titulo"))
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_ais = {
                k: v for k, v in _opciones_material(catalogo.AISLANTES).items() if k != _ID_USUARIO
            }
            opciones_ais[_ID_USUARIO] = t("p3.materiales.usuario")
            ids_ais = list(opciones_ais.keys())
            idx_ais = (
                ids_ais.index(colector.unidad.id_aislante)
                if colector.unidad.id_aislante in ids_ais
                else 0
            )
            id_aislante = st.selectbox(
                t("p3.materiales.aislante_label"),
                options=ids_ais,
                index=idx_ais,
                format_func=lambda x: opciones_ais[x],
                key="p3_id_aislante",
            )
        with c2:
            espesor_aislante_cm = st.number_input(
                t("p3.materiales.espesor_cm"),
                min_value=1.0,
                max_value=20.0,
                value=colector.unidad.espesor_aislante_m * 100,
                step=0.5,
                key="p3_esp_aislante",
            )
        if id_aislante == _ID_USUARIO:
            catalogo.AISLANTES[_ID_USUARIO] = _inputs_aislante_usuario("p3_uais")
        _tabla_propiedades_aislante(id_aislante)

        st.divider()
        st.subheader(t("p3.materiales.fondo_titulo"))
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_fon = {
                k: v for k, v in _opciones_material(catalogo.FONDOS).items() if k != _ID_USUARIO
            }
            opciones_fon[_ID_USUARIO] = t("p3.materiales.usuario")
            ids_fon = list(opciones_fon.keys())
            idx_fon = (
                ids_fon.index(colector.unidad.id_fondo)
                if colector.unidad.id_fondo in ids_fon
                else 0
            )
            id_fondo = st.selectbox(
                t("p3.materiales.fondo_label"),
                options=ids_fon,
                index=idx_fon,
                format_func=lambda x: opciones_fon[x],
                key="p3_id_fondo",
            )
        with c2:
            # Fondo de madera → medidas de mercado en pulgadas; chapa/otros →
            # input libre. Para madera se sube el tope a 100 mm (3/4" = 19 mm no
            # entraba en el viejo límite de 5 mm).
            es_madera_fondo = id_fondo in MATERIALES_MADERA
            espesor_fondo_mm = selector_espesor_mm(
                t("p3.materiales.espesor_mm"),
                colector.unidad.espesor_fondo_m,
                key="p3_esp_fondo",
                opciones_mm=ESPESORES_MADERA_MM if es_madera_fondo else None,
                min_mm=0.3,
                max_mm=100.0 if es_madera_fondo else 60.0,
                step=0.1,
            )
        if id_fondo == _ID_USUARIO:
            catalogo.FONDOS[_ID_USUARIO] = _inputs_fondo_usuario("p3_ufon")
        _tabla_propiedades_fondo(id_fondo)

    # -----------------------------------------------------------------------
    # Sección 2: Colector unitario — geometría y velocidad
    # -----------------------------------------------------------------------

    with st.expander(t("p3.geometria.titulo"), expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            ancho_m = st.number_input(
                t("p3.geometria.ancho.label"),
                min_value=0.1,
                max_value=5.0,
                value=float(colector.unidad.ancho_m),
                step=0.05,
                format="%.2f",
                key="p3_ancho",
                help=t("p3.geometria.ancho.help"),
            )
            largo_m = st.number_input(
                t("p3.geometria.largo.label"),
                min_value=0.1,
                # Máximo adaptado al valor actual (calibración/snapshot) para no crashear.
                max_value=max(20.0, float(colector.unidad.largo_m)),
                step=0.1,
                format="%.2f",
                key="p3_largo",
                help=t("p3.geometria.largo.help"),
                **(
                    {}
                    if "p3_largo" in st.session_state
                    else {"value": float(colector.unidad.largo_m)}
                ),
            )
        with c2:
            _clave_esp = (
                "p3.geometria.espaciado_t1"
                if tipo_colector == 1
                else ("p3.geometria.espaciado_t234")
            )
            espaciado_mm = st.number_input(
                t(f"{_clave_esp}.label"),
                min_value=5.0,
                max_value=200.0,
                value=colector.unidad.espaciado_m * 1000,
                step=1.0,
                format="%.1f",
                key="p3_espaciado",
                help=t(f"{_clave_esp}.help"),
            )
            if tipo_colector in (2, 3, 4):
                espaciado_inferior_mm = st.number_input(
                    t("p3.geometria.espaciado_inferior.label"),
                    min_value=5.0,
                    max_value=200.0,
                    value=colector.unidad.espaciado_inferior_m * 1000,
                    step=1.0,
                    format="%.1f",
                    key="p3_espaciado_inferior",
                    help=t("p3.geometria.espaciado_inferior.help"),
                )
            else:
                espaciado_inferior_mm = colector.unidad.espaciado_inferior_m * 1000
        with c3:
            velocidad_ms = st.number_input(
                t("p3.geometria.velocidad.label"),
                min_value=0.01,
                # Sin tope artificial bajo: en gran escala/alto caudal la velocidad de
                # canal puede ser alta. El máximo se adapta al valor actual (calibración,
                # snapshot) para no crashear nunca (StreamlitValueAboveMaxError).
                max_value=max(50.0, float(colector.unidad.velocidad_diseno_ms)),
                # value= solo para inicializar; si la key ya está en session_state
                # (incl. "aplicar óptimo" que la fija), el widget la respeta sin warning.
                step=0.05,
                format="%.2f",
                key="p3_velocidad",
                help=t("p3.geometria.velocidad.help"),
                **(
                    {}
                    if "p3_velocidad" in st.session_state
                    else {"value": float(colector.unidad.velocidad_diseno_ms)}
                ),
            )

        # Preview rápido
        seccion_m2 = ancho_m * (espaciado_mm / 1000)
        caudal_unit_m3s = velocidad_ms * seccion_m2
        _caption = t(
            "p3.geometria.preview",
            seccion=seccion_m2 * 10000,
            caudal=caudal_unit_m3s * 1000,
            area=ancho_m * largo_m,
        )
        if tipo_colector in (2, 3, 4):
            seccion_inf_m2 = ancho_m * (espaciado_inferior_mm / 1000)
            _caption += t("p3.geometria.preview_inferior", seccion=seccion_inf_m2 * 10000)
        st.caption(_caption)

    # -----------------------------------------------------------------------
    # Sección 3: Banco de colectores
    # -----------------------------------------------------------------------

    with st.expander(t("p3.banco.titulo"), expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            n_serie = st.number_input(
                t("p3.banco.n_serie.label"),
                min_value=1,
                max_value=20,
                value=colector.banco.n_serie,
                step=1,
                key="p3_n_serie",
                help=t("p3.banco.n_serie.help"),
            )
        with c2:
            n_paralelo = st.number_input(
                t("p3.banco.n_paralelo.label"),
                min_value=1,
                max_value=200,
                value=colector.banco.n_paralelo,
                step=1,
                key="p3_n_paralelo",
                help=t("p3.banco.n_paralelo.help"),
            )

        caudal_total = n_paralelo * caudal_unit_m3s
        area_total = n_serie * n_paralelo * ancho_m * largo_m
        largo_camino = n_serie * largo_m

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(
            t("p3.banco.caudal_total.label"),
            f"{caudal_total*1000:.1f} L/s",
            help=t("p3.banco.caudal_total.help"),
        )
        col_m2.metric(t("p3.banco.area_total"), f"{area_total:.2f} m²")
        col_m3.metric(
            t("p3.banco.camino.label"),
            f"{largo_camino:.1f} m",
            help=t("p3.banco.camino.help"),
        )

        # -------------------------------------------------------------------
        # Caño maestro (manifold del banco) — solo gran escala
        # -------------------------------------------------------------------
        cano_maestro_cfg = None
        if tipologia == Tipologia.GRAN_ESCALA:
            st.markdown(t("p3.cano.titulo"))
            st.caption(t("p3.cano.intro"))
            cm_prev = colector.banco.cano_maestro
            usar_cano = st.checkbox(
                t("p3.cano.usar.label"),
                value=cm_prev is not None,
                key="p3_usar_cano",
                help=t("p3.cano.usar.help"),
            )
            if usar_cano:
                cm = cm_prev or CanoMaestro()
                cc1, cc2, cc3 = st.columns(3)
                cm_largo = cc1.number_input(
                    t("p3.cano.largo.label"),
                    min_value=0.5,
                    max_value=100.0,
                    value=cm.largo_m,
                    step=0.5,
                    format="%.1f",
                    key="p3_cm_largo",
                    help=t("p3.cano.largo.help"),
                )
                cm_ancho = cc2.number_input(
                    t("p3.cano.ancho.label"),
                    min_value=0.1,
                    max_value=5.0,
                    value=cm.ancho_m,
                    step=0.05,
                    format="%.2f",
                    key="p3_cm_ancho",
                    help=t("p3.cano.ancho.help"),
                )
                cm_alto = cc3.number_input(
                    t("p3.cano.alto.label"),
                    min_value=0.1,
                    max_value=5.0,
                    value=cm.alto_m,
                    step=0.05,
                    format="%.2f",
                    key="p3_cm_alto",
                    help=t("p3.cano.alto.help"),
                )
                cd1, cd2 = st.columns(2)
                cm_aislado = cd1.checkbox(
                    t("p3.cano.aislado.label"),
                    value=cm.aislado,
                    key="p3_cm_aislado",
                    help=t("p3.cano.aislado.help"),
                )
                cm_aporte = cd2.checkbox(
                    t("p3.cano.aporte.label"),
                    value=cm.aporte_solar,
                    key="p3_cm_aporte",
                    help=t("p3.cano.aporte.help"),
                )
                cm_esp_m = 0.0
                cm_mat_aisl = None
                if cm_aislado:
                    _ops_aisl = _opciones_material(catalogo.AISLANTES)
                    _ids_aisl = list(_ops_aisl.keys())
                    _idx_aisl = (
                        _ids_aisl.index(cm.material_aislante)
                        if cm.material_aislante in _ids_aisl
                        else 0
                    )
                    cm_mat_aisl = cd1.selectbox(
                        t("p3.cano.mat_aisl.label"),
                        options=_ids_aisl,
                        index=_idx_aisl,
                        format_func=lambda i: _ops_aisl[i],
                        key="p3_cm_mat_aisl",
                        help=t("p3.cano.mat_aisl.help"),
                    )
                    cm_esp_m = (
                        cd1.number_input(
                            t("p3.cano.esp_aisl"),
                            min_value=0.5,
                            max_value=20.0,
                            value=max(0.5, cm.espesor_aislante_m * 100.0),
                            step=0.5,
                            format="%.1f",
                            key="p3_cm_esp",
                        )
                        / 100.0
                    )
                cm_absort = cm.absortancia_solar
                cm_cubierta = None
                if cm_aporte:
                    cm_absort = cd2.number_input(
                        t("p3.cano.absort.label"),
                        min_value=0.05,
                        max_value=1.0,
                        value=float(cm.absortancia_solar),
                        step=0.05,
                        format="%.2f",
                        key="p3_cm_absort",
                        help=t("p3.cano.absort.help"),
                    )
                    _ops_cub = {"(sin cubierta)": t("p3.cano.sin_cubierta")}
                    _ops_cub.update(_opciones_material(catalogo.CUBIERTAS))
                    _ids_cub = list(_ops_cub.keys())
                    _idx_cub = _ids_cub.index(cm.cubierta) if cm.cubierta in _ids_cub else 0
                    _sel_cub = cd2.selectbox(
                        t("p3.cano.cubierta.label"),
                        options=_ids_cub,
                        index=_idx_cub,
                        format_func=lambda i: _ops_cub[i],
                        key="p3_cm_cubierta",
                        help=t("p3.cano.cubierta.help"),
                    )
                    cm_cubierta = None if _sel_cub == "(sin cubierta)" else _sel_cub

                cm_sec_var = st.checkbox(
                    t("p3.cano.sec_var.label"),
                    value=cm.seccion_variable,
                    key="p3_cm_sec_var",
                    help=t("p3.cano.sec_var.help"),
                )
                cm_ancho_ini = cm_alto_ini = None
                if cm_sec_var:
                    cv1, cv2 = st.columns(2)
                    cm_ancho_ini = cv1.number_input(
                        t("p3.cano.ancho_ini.label"),
                        min_value=0.05,
                        max_value=5.0,
                        value=float(cm.ancho_inicio_m or cm.ancho_m / 2.0),
                        step=0.05,
                        format="%.2f",
                        key="p3_cm_ancho_ini",
                        help=t("p3.cano.ancho_ini.help"),
                    )
                    cm_alto_ini = cv2.number_input(
                        t("p3.cano.alto_ini"),
                        min_value=0.05,
                        max_value=5.0,
                        value=float(cm.alto_inicio_m or cm.alto_m / 2.0),
                        step=0.05,
                        format="%.2f",
                        key="p3_cm_alto_ini",
                    )
                try:
                    cano_maestro_cfg = CanoMaestro(
                        largo_m=cm_largo,
                        ancho_m=cm_ancho,
                        alto_m=cm_alto,
                        aislado=cm_aislado,
                        espesor_aislante_m=cm_esp_m,
                        material_aislante=cm_mat_aisl,
                        aporte_solar=cm_aporte,
                        absortancia_solar=float(cm_absort),
                        cubierta=cm_cubierta,
                        ancho_inicio_m=cm_ancho_ini,
                        alto_inicio_m=cm_alto_ini,
                    )
                    from calculos.cano_maestro_calc import estimar_delta_P_cano_maestro

                    _dP = estimar_delta_P_cano_maestro(cano_maestro_cfg, caudal_total)
                    if cano_maestro_cfg.seccion_variable:
                        _sec_txt = t(
                            "p3.cano.preview_crece",
                            a_ini=cano_maestro_cfg.area_seccion_inicio_m2,
                            a_fin=cano_maestro_cfg.area_seccion_m2,
                            v_max=_dP["v_max_ms"],
                            v_fin=_dP["v_fin_ms"],
                        )
                    else:
                        _sec_txt = t(
                            "p3.cano.preview_constante",
                            a_fin=cano_maestro_cfg.area_seccion_m2,
                            v_max=_dP["v_max_ms"],
                            v_fin=_dP["v_fin_ms"],
                        )
                    st.caption(
                        t(
                            "p3.cano.preview_dp",
                            sec=_sec_txt,
                            total=_dP["total"],
                            friccion=_dP["friccion"],
                            accesorios=_dP["accesorios"],
                        )
                    )
                except ValueError as _e:
                    st.error(t("p3.cano.invalido", e=_e))
                    cano_maestro_cfg = None

    # -----------------------------------------------------------------------
    # Nota: la chimenea solar se configura en P6 (pestaña Motor / Convección
    # natural), no acá, porque es independiente del colector y aplica también
    # a tipología CAJA donde esta pestaña no se muestra.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Aplicar cambios al session_state
    # -----------------------------------------------------------------------

    try:
        nueva_unidad = ColectorUnidad(
            ancho_m=ancho_m,
            largo_m=largo_m,
            espaciado_m=espaciado_mm / 1000,
            n_cubiertas=n_cubiertas,
            espaciado_entre_cubiertas_m=esp_cub_cub_mm / 1000,
            velocidad_diseno_ms=velocidad_ms,
            tipo_colector=tipo_colector,
            espaciado_inferior_m=espaciado_inferior_mm / 1000,
            id_cubierta=id_cubierta,
            espesor_cubierta_m=espesor_cubierta_mm / 1000,
            id_placa=id_placa,
            espesor_placa_m=espesor_placa_mm / 1000,
            id_aislante=id_aislante,
            espesor_aislante_m=espesor_aislante_cm / 100,
            id_fondo=id_fondo,
            espesor_fondo_m=espesor_fondo_mm / 1000,
            k_cubierta_efectivo_W_mK=k_cubierta_override,
        )
        nuevo_banco = BancoColectores(
            n_serie=n_serie, n_paralelo=n_paralelo, cano_maestro=cano_maestro_cfg
        )

        nuevo_colector = Colector(
            unidad=nueva_unidad,
            banco=nuevo_banco,
        )
        proyecto.colector = nuevo_colector

    except ValueError as err:
        codigo = str(err).split(":")[0]
        st.error(t("p3.error_validacion", codigo=codigo, err=err))
        return  # No mostrar advertencias ni resumen si hay error duro

    # -----------------------------------------------------------------------
    # Sección 5: Advertencias y resumen
    # -----------------------------------------------------------------------

    adv_list = advertencias_colector(proyecto.colector)

    if adv_list:
        criticas = [a for a in adv_list if a.severidad == Severidad.CRITICAL]
        warnings = [a for a in adv_list if a.severidad == Severidad.WARNING]
        infos = [a for a in adv_list if a.severidad == Severidad.INFO]

        # Resumen visible de un vistazo antes del expander, para que las
        # advertencias importantes no pasen desapercibidas si queda colapsado.
        if criticas:
            st.error(t("p3.advertencias.resumen_criticas", n=len(criticas)))
        elif warnings:
            st.warning(t("p3.advertencias.resumen_warnings", n=len(warnings)))

        with st.expander(
            t(
                "p3.advertencias.titulo_expander",
                nc=len(criticas),
                nw=len(warnings),
                ni=len(infos),
            ),
            expanded=bool(criticas),
        ):
            render_advertencias(adv_list, con_sugerencia=True)
    else:
        st.success(t("p3.advertencias.sin_advertencias"))

    # -----------------------------------------------------------------------
    # Sección 5b: Evaluación del desempeño del colector unitario
    # (primero un colector; el campo/banco se evalúa a continuación)
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader(t("p3.eval.titulo"))

    _empl = proyecto.emplazamiento
    _clima = proyecto.clima
    _cfg = proyecto.configuracion
    _prereq_ok = True

    if _empl is None:
        st.warning(t("p3.eval.falta_emplazamiento"))
        _prereq_ok = False
    if _clima is None or _clima.datos is None:
        st.warning(t("p3.eval.falta_clima"))
        _prereq_ok = False

    if _prereq_ok:
        _modo_label = {
            ModoAnalisis.DIARIO: t("p3.eval.modo.diario"),
            ModoAnalisis.VENTANA: t("p3.eval.modo.ventana"),
        }.get(_cfg.modo_analisis, t("p3.eval.modo.anual"))
        st.caption(
            t(
                "p3.eval.modo_caption",
                modo=_modo_label,
                pend=_empl.pendiente_colector_deg,
                anio=_clima.anio,
            )
        )

        _render_albedo_suelo(proyecto, _empl)

        if st.button(t("p3.eval.boton"), type="primary", key="p3_calcular_eval"):
            _datos_local = _clima.datos.tz_convert(_empl.zona_horaria)
            _datos_local = _datos_local[_datos_local.index.year == _clima.anio]

            if _cfg.modo_analisis == ModoAnalisis.DIARIO:
                _datos_dia, _fecha = _seleccionar_dia(_datos_local, _cfg, _clima.anio)
                _fecha_label = str(_fecha)
                if len(_datos_dia) == 0:
                    st.error(t("p3.eval.sin_datos_dia", fecha=_fecha_label))
                else:
                    with st.spinner(t("p3.eval.spinner_dia", fecha=_fecha_label)):
                        _r = _evaluar_diario(proyecto.colector, _datos_dia, _empl)
                    st.session_state["p3_eval"] = {"modo": "diario", "r": _r, "label": _fecha_label}
            elif _cfg.modo_analisis == ModoAnalisis.VENTANA:
                from calculos.clima_calc import slice_clima_ventana

                _df_v, _msg_v = slice_clima_ventana(_clima, _cfg.ventana_inicio, _cfg.ventana_fin)
                if _df_v is None:
                    st.error(t("p3.eval.ventana_error", msg=_msg_v))
                else:
                    _datos_v = _df_v.tz_convert(_empl.zona_horaria)
                    _lapso_label = f"{_cfg.ventana_inicio} → {_cfg.ventana_fin}"
                    with st.spinner(t("p3.eval.spinner_ventana", horas=len(_datos_v))):
                        _r = _evaluar_ventana(proyecto.colector, _datos_v, _empl)
                    st.session_state["p3_eval"] = {
                        "modo": "ventana",
                        "r": _r,
                        "label": _lapso_label,
                    }
            else:
                with st.spinner(t("p3.eval.spinner_anual")):
                    _r = _evaluar_anual(proyecto.colector, _datos_local, _empl, _clima.anio)
                st.session_state["p3_eval"] = {"modo": "anual", "r": _r}

    # Mostrar resultados si existen
    if "p3_eval" in st.session_state and st.session_state["p3_eval"]:
        _ev = st.session_state["p3_eval"]
        _r = _ev["r"]
        _modo = _ev["modo"]

        st.markdown(t("p3.eval.resultados_titulo"))

        if _modo == "diario":
            _lbl = _ev["label"]

            # Métricas rápidas
            _T_sal_vals = [t for t in _r["T_salida_C"] if t is not None]
            if _T_sal_vals:
                c1, c2, c3 = st.columns(3)
                c1.metric(t("p3.eval.diario.t_max"), f"{max(_T_sal_vals):.1f} °C")
                c2.metric(
                    t("p3.eval.diario.t_mediodia"),
                    (
                        f"{_T_sal_vals[len(_T_sal_vals)//2]:.1f} °C"
                        if _r["hora_transit"] is not None
                        else "—"
                    ),
                )
                c3.metric(
                    t("p3.eval.diario.dt_max"),
                    f"{max(ts - ta for ts, ta in zip(_T_sal_vals, [_r['T_amb_C'][i] for i, t in enumerate(_r['T_salida_C']) if t is not None])):.1f} °C",
                )

            tab_a, tab_b = st.tabs([t("p3.eval.diario.tab_a"), t("p3.eval.diario.tab_b")])

            with tab_a:
                _fig_a = _fig_T_salida_dia(_r, _lbl)
                mostrar_plotly(_fig_a, nombre="colector_Tsalida_dia")

            with tab_b:
                _fig_b = _fig_T_fluido_dia(_r, _lbl)
                if _fig_b is not None:
                    mostrar_plotly(_fig_b, nombre="colector_Tfluido_dia")
                else:
                    st.info(t("p3.eval.diario.sin_radiacion"))

        elif _modo == "ventana":
            _lbl = _ev["label"]
            _T_vals = [t for t in _r["T_salida_C"] if t is not None]
            if _T_vals:
                _pares = [
                    (ts, ta)
                    for ts, ta, p in zip(_r["T_salida_C"], _r["T_amb_C"], _r["poa"])
                    if ts is not None and p > 50.0
                ]
                c1, c2, c3 = st.columns(3)
                c1.metric(t("p3.eval.ventana.t_max"), f"{max(_T_vals):.1f} °C")
                c2.metric(
                    t("p3.eval.ventana.dt_medio"),
                    f"{sum(ts - ta for ts, ta in _pares) / len(_pares):.1f} °C" if _pares else "—",
                )
                c3.metric(
                    t("p3.eval.ventana.horas_40"),
                    f"{sum(1 for t in _T_vals if t > 40.0)} h",
                )
            _tab_v1, _tab_v2 = st.tabs(
                [t("p3.eval.ventana.tab_series"), t("p3.eval.ventana.tab_perfil")]
            )
            with _tab_v1:
                mostrar_plotly(_fig_T_salida_ventana(_r, _lbl), nombre="colector_Tsalida_ventana")
                st.caption(t("p3.eval.ventana.caption_series"))
            with _tab_v2:
                _fig_perfil_v = _fig_T_fluido_dia(_r, t("p3.eval.ventana.perfil_label", lapso=_lbl))
                if _fig_perfil_v is not None:
                    mostrar_plotly(_fig_perfil_v, nombre="colector_Tfluido_ventana")
                    st.caption(t("p3.eval.ventana.caption_perfil"))
                else:
                    st.info(t("p3.eval.ventana.sin_radiacion"))
            st.caption(t("p3.eval.ventana.caption_vista_previa"))

        else:  # anual
            if _r["meses"]:
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    t("p3.eval.anual.t_max_mes"),
                    f"{max(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(max(_r['T_salida_noon_C']))]}",
                )
                c2.metric(
                    t("p3.eval.anual.t_min_mes"),
                    f"{min(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(min(_r['T_salida_noon_C']))]}",
                )
                c3.metric(
                    t("p3.eval.anual.dt_min"),
                    f"{min(ts - ta for ts, ta in zip(_r['T_salida_noon_C'], _r['T_amb_noon_C'])):.1f} °C",
                )

                tab_a, tab_b = st.tabs([t("p3.eval.anual.tab_a"), t("p3.eval.anual.tab_b")])

                with tab_a:
                    _fig_a = _fig_T_salida_anual(_r)
                    mostrar_plotly(_fig_a, nombre="colector_Tsalida_anual")
                    st.caption(t("p3.eval.anual.caption_mediodia"))

                with tab_b:
                    _fig_b = _fig_T_fluido_anual(_r)
                    if _fig_b is not None:
                        mostrar_plotly(_fig_b, nombre="colector_Tfluido_anual")
            else:
                st.warning(t("p3.eval.anual.sin_resultados"))

    # -----------------------------------------------------------------------
    # Sección 5c: Evaluación del campo de colectores (banco, gran escala, S41)
    # (se evalúa después del colector unitario: usa ese colector en cada rama)
    # -----------------------------------------------------------------------

    if tipologia == Tipologia.GRAN_ESCALA:
        st.divider()
        st.subheader(t("p3.campo.titulo"))
        st.caption(t("p3.campo.intro"))

        _cam_p4 = getattr(proyecto, "camara", None)
        _rho_ref_campo = 1.05  # kg/m³ ~45 °C — solo para el default del widget
        if _cam_p4 is not None and _cam_p4.flujo.caudal_masico_kg_s > 0:
            _q_def_Ls = _cam_p4.flujo.caudal_masico_kg_s / _rho_ref_campo * 1000.0
            _origen_q = t("p3.campo.origen_p4")
        else:
            _q_def_Ls = caudal_total * 1000.0
            _origen_q = t("p3.campo.origen_banco")

        ci1, ci2, ci3, ci4 = st.columns(4)
        _q_Ls = ci1.number_input(
            t("p3.campo.q.label"),
            min_value=1.0,
            max_value=50000.0,
            value=float(max(1.0, _q_def_Ls)),
            step=10.0,
            key="p3_campo_q",
            help=t("p3.campo.q.help", origen=_origen_q),
        )
        _T_amb_campo = ci2.number_input(
            t("p3.campo.t_amb"),
            min_value=-10.0,
            max_value=50.0,
            value=25.0,
            step=1.0,
            key="p3_campo_tamb",
        )
        _poa_campo = ci3.number_input(
            t("p3.campo.poa.label"),
            min_value=0.0,
            max_value=1400.0,
            value=900.0,
            step=50.0,
            key="p3_campo_poa",
            help=t("p3.campo.poa.help"),
        )
        _vw_campo = ci4.number_input(
            t("p3.campo.viento"),
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.5,
            key="p3_campo_vw",
        )

        if st.button(t("p3.campo.boton"), type="primary", key="p3_btn_campo"):
            from calculos.balance_global import presion_representativa_proyecto
            from calculos.campo_colectores_calc import evaluar_campo_colectores

            _P_campo, _ = presion_representativa_proyecto(proyecto)
            _pend_campo = (
                proyecto.emplazamiento.pendiente_colector_deg
                if proyecto.emplazamiento is not None
                else 25.0
            )
            _n_ramas = proyecto.colector.banco.n_paralelo
            with st.spinner(t("p3.campo.spinner", n=_n_ramas)):
                _rc = evaluar_campo_colectores(
                    proyecto.colector,
                    Q_total_m3_s=_q_Ls / 1000.0,
                    T_amb_K=_T_amb_campo + 273.15,
                    I_g_POA_W_m2=_poa_campo,
                    v_viento_ms=_vw_campo,
                    P_Pa=_P_campo,
                    pendiente_deg=_pend_campo,
                )
            st.session_state["p3_campo"] = _rc

        _rc = st.session_state.get("p3_campo")
        if _rc is not None:
            for _a in _rc.advertencias:
                st.warning(f"⚠️ {_a}")  # i18n: exento (mensaje de calculos/, queda ES)
            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric(
                t("p3.campo.t_salida_cano"),
                (
                    f"{_rc.T_salida_cano_K - 273.15:.1f} °C"
                    if _rc.T_salida_cano_K is not None
                    else "—"
                ),
                delta=(
                    t("p3.campo.delta_cano", v=_rc.dT_cano_K) if _rc.dT_cano_K is not None else None
                ),
            )
            cm2.metric(
                t("p3.campo.t_mezcla"),
                f"{_rc.T_mezcla_K - 273.15:.1f} °C" if _rc.T_mezcla_K is not None else "—",
            )
            cm3.metric(
                t("p3.campo.desuniformidad.label"),
                f"{_rc.uniformidad['desviacion_max_pct']:.1f} %",
                help=t("p3.campo.desuniformidad.help"),
            )
            cm4.metric(
                t("p3.campo.dp_sistema.label"),
                f"{_rc.dP_sistema_Pa:.0f} Pa",
                help=t("p3.campo.dp_sistema.help"),
            )
            # Compensación de sección del caño (mejora 32): el ΔP del troncal
            # aislado de la rama + el rango de velocidad hacen visible si la
            # sección creciente acota la velocidad al acumular caudal.
            _vp = getattr(_rc, "v_troncal_perfil_ms", None)
            if _vp is not None and len(_vp) > 0:
                cn1, cn2 = st.columns(2)
                cn1.metric(
                    t("p3.campo.dp_troncal.label"),
                    f"{_rc.dP_troncal_Pa:.1f} Pa",
                    help=t("p3.campo.dp_troncal.help"),
                )
                cn2.metric(
                    t("p3.campo.v_troncal.label"),
                    f"{float(_vp.min()):.2f} → {float(_vp.max()):.2f} m/s",
                    help=t("p3.campo.v_troncal.help"),
                )
            mostrar_plotly(_fig_campo_colectores(_rc), nombre="campo_colectores")
            st.caption(
                t(
                    "p3.campo.caption_reparto",
                    n=_rc.n_iter,
                    estado=(
                        t("p3.campo.convergio") if _rc.convergio else t("p3.campo.no_convergio")
                    ),
                    qmin=_rc.uniformidad["q_min_m3_s"] * 1000,
                    qmax=_rc.uniformidad["q_max_m3_s"] * 1000,
                )
            )

    # --- Validación con datos medidos (mejora 38, fase 2) ---
    st.divider()
    _render_validacion_colector(proyecto)

    # --- Guardar configuración (mejora 4) ---
    st.divider()
    from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

    _eval_p3 = st.session_state.get("p3_eval")
    col_txt, col_json = st.columns(2)
    with col_txt:
        st.download_button(
            t("p3.guardar.txt"),
            data=_texto_config_colector(proyecto.colector, _eval_p3),
            file_name=nombre_archivo_descarga(proyecto, "colector", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            t("p3.guardar.json"),
            data=dump_json(_json_config_colector(proyecto.colector, _eval_p3)),
            file_name=nombre_archivo_descarga(proyecto, "colector", "json"),
            mime="application/json",
            width="stretch",
        )
