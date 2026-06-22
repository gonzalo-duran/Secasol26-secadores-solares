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
from ui.componentes.espesores import (
    ESPESORES_MADERA_MM,
    MATERIALES_MADERA,
    selector_espesor_mm,
)
from ui.componentes.esquemas import mostrar_esquema
from ui.componentes.graficas import mostrar_plotly
from ui.componentes.unidades import kelvin_a_celsius

# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_ID_USUARIO = "__usuario__"

_TIPOS_COLECTOR = {
    1: "Tipo 1 — Canal único, absorbedor en el fondo",
    2: "Tipo 2 — Absorbedor a media altura, ambos canales activos",
    3: "Tipo 3 — Absorbedor a media altura, canal inferior activo (superior estanco)",
    4: "Tipo 4 — Absorbedor a media altura, canal superior activo (inferior estanco)",
}

_TIPOS_HELP = {
    1: (
        "El absorbedor está en el fondo del cuerpo del colector. "
        "El aire circula por el canal único entre la cubierta y el absorbedor. "
        "Es la configuración más simple y común."
    ),
    2: (
        "El absorbedor divide el cuerpo en dos canales. "
        "El aire circula por ambos canales simultáneamente, lo que duplica el caudal "
        "y mejora la extracción de calor."
    ),
    3: (
        "El absorbedor divide el cuerpo en dos canales. "
        "El aire circula solo por el canal inferior (absorbedor–fondo). "
        "El canal superior queda estanco y actúa como aislación adicional."
    ),
    4: (
        "El absorbedor divide el cuerpo en dos canales. "
        "El aire circula solo por el canal superior (cubierta–absorbedor). "
        "El canal inferior queda estanco."
    ),
}


def _opciones_material(catalogo_dict: dict) -> dict[str, str]:
    """Genera un mapa {id: etiqueta_display} para un selectbox de materiales.

    Args:
        catalogo_dict: Diccionario de materiales cargado por core.catalogo.

    Returns:
        Diccionario ordenado {id_material: descripcion_corta}.
    """
    return {id_mat: datos.get("descripcion", id_mat) for id_mat, datos in catalogo_dict.items()}


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
    st.caption("Propiedades de la cubierta definida por el usuario:")
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
    st.caption("Propiedades de la placa absorbedora definida por el usuario:")
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
    st.caption("Propiedades del aislante definido por el usuario:")
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
    st.caption("Propiedades del fondo/carcasa definido por el usuario:")
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
        f"  {_TIPOS_COLECTOR.get(u.tipo_colector, f'Tipo {u.tipo_colector}')}",
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
            "tipo_colector_descripcion": _TIPOS_COLECTOR.get(u.tipo_colector),
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

_MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
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
            "Albedo del suelo (superficie circundante)",
            options=opciones,
            index=opciones.index(etiqueta_actual),
            key="p3_albedo_superficie",
            help="Reflectancia solar del suelo que rodea al colector. Alimenta la "
            "componente reflejada de la POA (GHI·ρ·(1−cos β)/2). Su efecto crece "
            "con la inclinación: en un colector vertical, la mitad de GHI·ρ "
            "llega al plano del colector.",
        )

    if seleccion == ETIQUETA_PERSONALIZADO:
        with col_val:
            nuevo_albedo = st.number_input(
                "ρ personalizado",
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
            T_abs_C.append(float(res.T_abs_K.mean()) - 273.15)
        else:
            # Noche / sin sol: el aire pasa sin calentarse (T → T_amb).
            T_sal_C.append(T_amb - 273.15)
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
            name="POA [W/m²]",
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
                name="T absorbedor [°C]",
            ),
            secondary_y=False,
        )
    fig.add_trace(
        go.Scatter(
            x=horas,
            y=T_sal,
            mode="lines",
            line=dict(color="#e05c2a", width=1.8),
            name="T salida colector [°C]",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=horas,
            y=T_amb,
            mode="lines",
            line=dict(color="#1f77b4", width=1.2, dash="dash"),
            name="T ambiente [°C]",
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
                name="POA máx (día)",
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
                name="Mediodía solar",
            ),
            secondary_y=True,
        )
    fig.update_yaxes(title_text="Temperatura [°C]", secondary_y=False)
    fig.update_yaxes(title_text="POA [W/m²]", color="#f5a623", secondary_y=True, rangemode="tozero")
    fig.update_xaxes(tickformat="%d-%b")
    fig.update_layout(
        title_text=f"Desempeño del colector sobre la ventana {lapso_label}",
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
            subplot_titles=("Reparto de caudal y temperatura por rama", "Velocidad en el troncal"),
        )
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=bocas,
            y=[float(q) * 1000.0 for q in rc.q_ramas_m3_s],
            name="Caudal por rama [L/s]",
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
                name="T salida rama [°C]",
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
                name="v troncal [m/s]",
                line=dict(color="#1f77b4", width=2),
                marker=dict(size=6),
                fill="tozeroy",
                fillcolor="rgba(31,119,180,0.12)",
            ),
            row=2,
            col=1,
        )
        fig.update_yaxes(
            title_text="v troncal [m/s]", row=2, col=1, rangemode="tozero", color="#1f77b4"
        )
        fig.update_xaxes(
            title_text="Boca / tramo (1 = extremo lejano al ventilador)",
            tickmode="linear",
            dtick=1,
            row=2,
            col=1,
        )
        fig.update_yaxes(title_text="Caudal por rama [L/s]", secondary_y=False, row=1, col=1)
        fig.update_yaxes(
            title_text="T salida [°C]", color="#e05c2a", secondary_y=True, row=1, col=1
        )
    else:
        fig.update_xaxes(
            title_text="Boca (1 = extremo lejano al ventilador)", tickmode="linear", dtick=1
        )
        fig.update_yaxes(title_text="Caudal por rama [L/s]", secondary_y=False, rangemode="tozero")
        fig.update_yaxes(title_text="T salida [°C]", color="#e05c2a", secondary_y=True)

    fig.update_layout(
        title_text="Campo de colectores — reparto, temperatura y velocidad del troncal",
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

        meses.append(_MES_ABBR[mes_num - 1])
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
            name="POA [W/m²]",
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
            name="T salida colector [°C]",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=list(horas),
            y=T_amb,
            mode="lines",
            line=dict(color="#1f77b4", width=1.5, dash="dash"),
            name="T ambiente [°C]",
        ),
        secondary_y=False,
    )

    if r["hora_transit"] is not None:
        _add_vline_datetime(
            fig,
            x=r["hora_transit"],
            text=f"Mediodía ({r['hora_transit'].strftime('%H:%M')})",
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
                text=f"POA máx ({r['hora_poa_max'].strftime('%H:%M')})",
                color="#ff7f0e",
                dash="dash",
                width=1.3,
                xanchor="right",
            )

    fig.update_yaxes(title_text="Temperatura [°C]", secondary_y=False)
    fig.update_yaxes(title_text="POA [W/m²]", color="#f5a623", secondary_y=True, rangemode="tozero")
    fig.update_xaxes(tickformat="%H:%M")
    fig.update_layout(
        title_text=f"Temperatura de salida del colector — {fecha_label}",
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
            name="T fluido [°C]",
        )
    )
    fig.add_hline(
        y=float(T[0]),
        line=dict(color="#1f77b4", dash="dash", width=1),
        annotation_text=f"T entrada = {T[0]:.1f} °C",
    )
    fig.update_xaxes(title_text="Posición x a lo largo del colector [m]")
    fig.update_yaxes(title_text="Temperatura del fluido [°C]")
    fig.update_layout(
        title_text=f"Perfil de temperatura del fluido — mediodía solar — {fecha_label}",
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
            name="POA mediodía [W/m²]",
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
            name="T salida colector — mediodía [°C]",
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
            name="T ambiente — mediodía [°C]",
        ),
        secondary_y=False,
    )

    fig.update_yaxes(title_text="Temperatura [°C]", secondary_y=False)
    fig.update_yaxes(title_text="POA [W/m²]", color="#f5a623", secondary_y=True, rangemode="tozero")
    fig.update_layout(
        title_text="Temperatura de salida del colector — mediodía solar por mes (día 15)",
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

    fig.update_xaxes(title_text="Posición x a lo largo del colector [m]")
    fig.update_yaxes(title_text="Temperatura del fluido [°C]")
    fig.update_layout(
        title_text="Perfil de temperatura del fluido — mediodía solar por mes",
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la pestaña 3: Colector Solar."""

    st.header("Colector Solar de Aire")

    proyecto = st.session_state.proyecto
    tipologia = proyecto.configuracion.tipologia

    # La tipología CAJA no tiene colector externo
    if tipologia == Tipologia.CAJA:
        st.info(
            "La tipología **Caja** no tiene colector solar externo: "
            "la cámara actúa como colector. Esta pestaña no aplica."
        )
        return

    # Inicializar colector si es la primera vez
    if proyecto.colector is None:
        proyecto.colector = Colector()

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander("📥 Cargar configuración guardada (.json)", expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            "Subí un archivo .json del colector previamente guardado",
            type=["json"],
            key="p3_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "colector")
            if err:
                st.error(f"❌ {err}")
            else:
                try:
                    col_cargado = _from_json_colector(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(f"❌ Error reconstruyendo el colector: {exc}")
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
                    st.success(
                        f"✅ Colector cargado desde JSON "
                        f"(se reiniciaron {n_borr} valores de la sesión)."
                    )
                    st.rerun()

    colector: Colector = proyecto.colector

    # -----------------------------------------------------------------------
    # Sección 0: Tipo de colector
    # -----------------------------------------------------------------------

    with st.expander("Tipo de colector", expanded=False):
        ids_tipo = list(_TIPOS_COLECTOR.keys())
        idx_tipo = (
            ids_tipo.index(colector.unidad.tipo_colector)
            if colector.unidad.tipo_colector in ids_tipo
            else 0
        )
        tipo_colector = st.selectbox(
            "Configuración del canal de flujo",
            options=ids_tipo,
            index=idx_tipo,
            format_func=lambda x: _TIPOS_COLECTOR[x],
            key="p3_tipo_colector",
        )
        st.info(_TIPOS_HELP[tipo_colector])

        with st.expander("📐 Sección transversal de los 4 tipos", expanded=False):
            mostrar_esquema(
                "colectores_seccion_transversal",
                max_ancho_px=600,
                caption="Sección transversal comparativa de los 4 tipos de colector.",
            )

    # -----------------------------------------------------------------------
    # Sección 1: Colector unitario — materiales
    # -----------------------------------------------------------------------

    with st.expander("Materiales del colector unitario", expanded=False):

        st.subheader("Cubierta transparente")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_cub = {
                k: v for k, v in _opciones_material(catalogo.CUBIERTAS).items() if k != _ID_USUARIO
            }
            opciones_cub[_ID_USUARIO] = "Definido por el usuario"
            ids_cub = list(opciones_cub.keys())
            idx_cub = (
                ids_cub.index(colector.unidad.id_cubierta)
                if colector.unidad.id_cubierta in ids_cub
                else 0
            )
            id_cubierta = st.selectbox(
                "Material de cubierta",
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
                "Espesor [mm]",
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
                "N° cubiertas",
                options=[1, 2],
                index=colector.unidad.n_cubiertas - 1,
                key="p3_n_cubiertas",
                help="1 cubierta es lo estándar. 2 cubiertas reduce pérdidas "
                "superiores (mejor en climas fríos o ventosos) pero baja la "
                "transmitancia solar.",
            )
            if n_cubiertas == 2:
                esp_cub_cub_mm = st.number_input(
                    "Espaciado entre cubiertas [mm]",
                    min_value=10.0,
                    max_value=50.0,
                    value=colector.unidad.espaciado_entre_cubiertas_m * 1000,
                    step=1.0,
                    key="p3_esp_cub_cub",
                    help="Cavidad de aire entre las dos cubiertas. Rango "
                    "óptimo 20–40 mm (Duffie & Beckman): minimiza convección "
                    "natural manteniendo la resistencia conductiva.",
                )
            else:
                esp_cub_cub_mm = colector.unidad.espaciado_entre_cubiertas_m * 1000
        if id_cubierta == _ID_USUARIO:
            catalogo.CUBIERTAS[_ID_USUARIO] = _inputs_cubierta_usuario("p3_ucub")
        _tabla_propiedades_cubierta(id_cubierta)

        st.divider()
        st.subheader("Placa absorbedora")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_pla = {
                k: v for k, v in _opciones_material(catalogo.PLACAS).items() if k != _ID_USUARIO
            }
            opciones_pla[_ID_USUARIO] = "Definido por el usuario"
            ids_pla = list(opciones_pla.keys())
            idx_pla = (
                ids_pla.index(colector.unidad.id_placa)
                if colector.unidad.id_placa in ids_pla
                else 0
            )
            id_placa = st.selectbox(
                "Material de placa",
                options=ids_pla,
                index=idx_pla,
                format_func=lambda x: opciones_pla[x],
                key="p3_id_placa",
            )
        with c2:
            espesor_placa_mm = st.number_input(
                "Espesor [mm]",
                min_value=0.3,
                max_value=5.0,
                value=colector.unidad.espesor_placa_m * 1000,
                step=0.1,
                key="p3_esp_placa",
                help=(
                    "Dato geométrico/diagnóstico: el modelo es cuasi-estacionario y "
                    "asume capacitancia térmica de la placa despreciable, así que este "
                    "espesor **no entra al balance térmico** ni cambia el rendimiento "
                    "calculado."
                ),
            )
        if id_placa == _ID_USUARIO:
            catalogo.PLACAS[_ID_USUARIO] = _inputs_placa_usuario("p3_upla")
        _tabla_propiedades_placa(id_placa)

        st.divider()
        st.subheader("Aislante térmico")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_ais = {
                k: v for k, v in _opciones_material(catalogo.AISLANTES).items() if k != _ID_USUARIO
            }
            opciones_ais[_ID_USUARIO] = "Definido por el usuario"
            ids_ais = list(opciones_ais.keys())
            idx_ais = (
                ids_ais.index(colector.unidad.id_aislante)
                if colector.unidad.id_aislante in ids_ais
                else 0
            )
            id_aislante = st.selectbox(
                "Material aislante",
                options=ids_ais,
                index=idx_ais,
                format_func=lambda x: opciones_ais[x],
                key="p3_id_aislante",
            )
        with c2:
            espesor_aislante_cm = st.number_input(
                "Espesor [cm]",
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
        st.subheader("Fondo / Carcasa")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_fon = {
                k: v for k, v in _opciones_material(catalogo.FONDOS).items() if k != _ID_USUARIO
            }
            opciones_fon[_ID_USUARIO] = "Definido por el usuario"
            ids_fon = list(opciones_fon.keys())
            idx_fon = (
                ids_fon.index(colector.unidad.id_fondo)
                if colector.unidad.id_fondo in ids_fon
                else 0
            )
            id_fondo = st.selectbox(
                "Material de fondo",
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
                "Espesor [mm]",
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

    with st.expander("Geometría y condición de diseño", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            ancho_m = st.number_input(
                "Ancho del canal [m]",
                min_value=0.1,
                max_value=5.0,
                value=float(colector.unidad.ancho_m),
                step=0.05,
                format="%.2f",
                key="p3_ancho",
                help=(
                    "Ancho interior del canal de flujo de un módulo unitario "
                    "(perpendicular al flujo). En un banco, el ancho total resulta "
                    "de los módulos en paralelo."
                ),
            )
            largo_m = st.number_input(
                "Largo del colector [m]",
                min_value=0.1,
                max_value=20.0,
                value=float(colector.unidad.largo_m),
                step=0.1,
                format="%.2f",
                key="p3_largo",
                help=(
                    "Largo del módulo en la dirección del flujo. Es la principal "
                    "variable de diseño: a mayor largo, mayor salto térmico del aire "
                    "pero también más pérdida de carga. La evaluación gráfica de abajo "
                    "ayuda a encontrar el largo óptimo."
                ),
            )
        with c2:
            _label_esp = (
                "Espaciado cubierta–placa [mm]"
                if tipo_colector == 1
                else "Canal superior cubierta–absorbedor [mm]"
            )
            _help_esp = (
                "Altura del canal único de flujo. Típico: 15–50 mm."
                if tipo_colector == 1
                else "Altura del canal superior (cubierta–absorbedor). Típico: 15–50 mm."
            )
            espaciado_mm = st.number_input(
                _label_esp,
                min_value=5.0,
                max_value=200.0,
                value=colector.unidad.espaciado_m * 1000,
                step=1.0,
                format="%.1f",
                key="p3_espaciado",
                help=_help_esp,
            )
            if tipo_colector in (2, 3, 4):
                espaciado_inferior_mm = st.number_input(
                    "Canal inferior absorbedor–fondo [mm]",
                    min_value=5.0,
                    max_value=200.0,
                    value=colector.unidad.espaciado_inferior_m * 1000,
                    step=1.0,
                    format="%.1f",
                    key="p3_espaciado_inferior",
                    help="Altura del canal inferior (absorbedor–fondo). Típico: 15–50 mm.",
                )
            else:
                espaciado_inferior_mm = colector.unidad.espaciado_inferior_m * 1000
        with c3:
            velocidad_ms = st.number_input(
                "Velocidad de diseño [m/s]",
                min_value=0.01,
                max_value=10.0,
                value=float(colector.unidad.velocidad_diseno_ms),
                step=0.05,
                format="%.2f",
                key="p3_velocidad",
                help=(
                    "Velocidad superficial del aire en el canal activo. "
                    "Determina el caudal por unidad y la pérdida de carga. "
                    "Rango recomendado: 0.3–3.0 m/s."
                ),
            )

        # Preview rápido
        seccion_m2 = ancho_m * (espaciado_mm / 1000)
        caudal_unit_m3s = velocidad_ms * seccion_m2
        _caption = (
            f"Sección del canal: {seccion_m2*10000:.1f} cm²  |  "
            f"Caudal por unidad: {caudal_unit_m3s*1000:.2f} L/s  |  "
            f"Área de captación: {ancho_m * largo_m:.2f} m²"
        )
        if tipo_colector in (2, 3, 4):
            seccion_inf_m2 = ancho_m * (espaciado_inferior_mm / 1000)
            _caption += f"  |  Sección inferior: {seccion_inf_m2*10000:.1f} cm²"
        st.caption(_caption)

    # -----------------------------------------------------------------------
    # Sección 3: Banco de colectores
    # -----------------------------------------------------------------------

    with st.expander("Banco de colectores", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            n_serie = st.number_input(
                "Colectores en serie por rama",
                min_value=1,
                max_value=20,
                value=colector.banco.n_serie,
                step=1,
                key="p3_n_serie",
                help="El aire pasa por N colectores consecutivos. Aumenta ΔT de salida.",
            )
        with c2:
            n_paralelo = st.number_input(
                "Ramas en paralelo",
                min_value=1,
                max_value=200,
                value=colector.banco.n_paralelo,
                step=1,
                key="p3_n_paralelo",
                help=(
                    "Ramas paralelas. El motor mueve la suma de los caudales de "
                    "todas las ramas. En gran escala puede haber decenas de ramas "
                    "(ej. ADITAL: 26 colectores descargando al caño maestro)."
                ),
            )

        caudal_total = n_paralelo * caudal_unit_m3s
        area_total = n_serie * n_paralelo * ancho_m * largo_m
        largo_camino = n_serie * largo_m

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(
            "Caudal total al motor",
            f"{caudal_total*1000:.1f} L/s",
            help="n_paralelo × caudal por unidad. Caudal volumétrico a condiciones de diseño.",
        )
        col_m2.metric("Área de captación total", f"{area_total:.2f} m²")
        col_m3.metric(
            "Camino del aire",
            f"{largo_camino:.1f} m",
            help="n_serie × largo de unidad. Longitud total que recorre el aire.",
        )

        # -------------------------------------------------------------------
        # Caño maestro (manifold del banco) — solo gran escala
        # -------------------------------------------------------------------
        cano_maestro_cfg = None
        if tipologia == Tipologia.GRAN_ESCALA:
            st.markdown("**Caño maestro (manifold del banco)**")
            st.caption(
                "En gran escala las ramas no descargan directo al ventilador: cada "
                "rama entrega su aire por una **boca** (con campana de reducción y "
                "llave mariposa de regulación) a un **caño maestro** que corre a lo "
                "largo del banco y conduce el caudal acumulado hasta el ventilador "
                "(estilo túnel ADITAL). Trabaja **en depresión** (aguas arriba del "
                "ventilador) y su sección crece hacia el ventilador para mantener "
                "la velocidad acotada a medida que suma caudal. Su ΔP se suma a lo "
                "que ve el ventilador (se muestra en **P6**) y su pérdida/aporte "
                "térmico entra al pipeline de ventana de producción."
            )
            cm_prev = colector.banco.cano_maestro
            usar_cano = st.checkbox(
                "Incluir caño maestro",
                value=cm_prev is not None,
                key="p3_usar_cano",
                help=(
                    "Tildado: el manifold se modela explícitamente (fricción + "
                    "accesorios de boca + balance térmico con el ambiente). "
                    "Sin tildar: conexión directa simple (el ΔP de distribución "
                    "cae en la heurística de ductos del motor en P6)."
                ),
            )
            if usar_cano:
                cm = cm_prev or CanoMaestro()
                cc1, cc2, cc3 = st.columns(3)
                cm_largo = cc1.number_input(
                    "Largo [m]",
                    min_value=0.5,
                    max_value=100.0,
                    value=cm.largo_m,
                    step=0.5,
                    format="%.1f",
                    key="p3_cm_largo",
                    help=(
                        "Longitud total del caño, que recorre el banco juntando "
                        "las bocas de las ramas (≈ el ancho del campo de "
                        "colectores). ADITAL: 18 m. La fricción se evalúa sobre "
                        "este largo."
                    ),
                )
                cm_ancho = cc2.number_input(
                    "Ancho sección [m]",
                    min_value=0.1,
                    max_value=5.0,
                    value=cm.ancho_m,
                    step=0.05,
                    format="%.2f",
                    key="p3_cm_ancho",
                    help=(
                        "Ancho de la sección transversal rectangular en el "
                        "**extremo del ventilador**, donde ya circula el caudal "
                        "total del banco (sección representativa del modelo de "
                        "prediseño). ADITAL: 1.0 m."
                    ),
                )
                cm_alto = cc3.number_input(
                    "Alto sección [m]",
                    min_value=0.1,
                    max_value=5.0,
                    value=cm.alto_m,
                    step=0.05,
                    format="%.2f",
                    key="p3_cm_alto",
                    help=(
                        "Alto de la sección transversal en el extremo del "
                        "ventilador. Junto con el ancho define la velocidad "
                        "troncal v = Q_total / (ancho × alto). ADITAL: 0.90 m."
                    ),
                )
                cd1, cd2 = st.columns(2)
                cm_aislado = cd1.checkbox(
                    "Aislado térmicamente",
                    value=cm.aislado,
                    key="p3_cm_aislado",
                    help=(
                        "El caño pierde calor al ambiente por convección externa "
                        "(viento), pero si su cara superior está al sol también "
                        "gana radiación: la pérdida neta suele ser chica. "
                        "ADITAL: no aislado, ΔT neta ≈ −3 °C."
                    ),
                )
                cm_aporte = cd2.checkbox(
                    "Aporte solar (cara superior expuesta)",
                    value=cm.aporte_solar,
                    key="p3_cm_aporte",
                    help=(
                        "La cara superior del caño expuesta al cielo colecta "
                        "radiación solar y compensa parte de la pérdida "
                        "convectiva. ADITAL: expuesta (chapa galvanizada)."
                    ),
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
                        "Material aislante",
                        options=_ids_aisl,
                        index=_idx_aisl,
                        format_func=lambda i: _ops_aisl[i],
                        key="p3_cm_mat_aisl",
                        help=(
                            "Material del catálogo de aislantes (mismo catálogo "
                            "que colector y cámara). Define la conductividad k "
                            "de la capa."
                        ),
                    )
                    cm_esp_m = (
                        cd1.number_input(
                            "Espesor aislante [cm]",
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
                        "Absortancia solar de la cara superior [-]",
                        min_value=0.05,
                        max_value=1.0,
                        value=float(cm.absortancia_solar),
                        step=0.05,
                        format="%.2f",
                        key="p3_cm_absort",
                        help=(
                            "Absortancia solar de la superficie que recibe el "
                            "sol. Chapa pintada oscura ≈ 0.90 (default); "
                            "galvanizado desnudo brillante ≈ 0.35 (caso ADITAL)."
                        ),
                    )
                    _ops_cub = {"(sin cubierta)": "(sin cubierta — chapa desnuda)"}
                    _ops_cub.update(_opciones_material(catalogo.CUBIERTAS))
                    _ids_cub = list(_ops_cub.keys())
                    _idx_cub = _ids_cub.index(cm.cubierta) if cm.cubierta in _ids_cub else 0
                    _sel_cub = cd2.selectbox(
                        "Cubierta translúcida (opcional)",
                        options=_ids_cub,
                        index=_idx_cub,
                        format_func=lambda i: _ops_cub[i],
                        key="p3_cm_cubierta",
                        help=(
                            "Cubierta transparente sobre la cara superior "
                            "(catálogo de cubiertas del colector): la ganancia "
                            "se afecta por τ y la cavidad de aire reduce la "
                            "pérdida convectiva (mini-colector)."
                        ),
                    )
                    cm_cubierta = None if _sel_cub == "(sin cubierta)" else _sel_cub

                cm_sec_var = st.checkbox(
                    "Sección creciente (variable a lo largo del caño)",
                    value=cm.seccion_variable,
                    key="p3_cm_sec_var",
                    help=(
                        "El caño arranca con sección chica en el extremo lejano "
                        "y crece hacia el ventilador para mantener la velocidad "
                        "acotada a medida que acumula caudal (interpolación "
                        "lineal). Mejora la uniformidad de reparto frente a un "
                        "caño constante chico, con menos material que uno "
                        "constante grande."
                    ),
                )
                cm_ancho_ini = cm_alto_ini = None
                if cm_sec_var:
                    cv1, cv2 = st.columns(2)
                    cm_ancho_ini = cv1.number_input(
                        "Ancho sección inicial [m]",
                        min_value=0.05,
                        max_value=5.0,
                        value=float(cm.ancho_inicio_m or cm.ancho_m / 2.0),
                        step=0.05,
                        format="%.2f",
                        key="p3_cm_ancho_ini",
                        help="Sección en el extremo lejano al ventilador (primera boca).",
                    )
                    cm_alto_ini = cv2.number_input(
                        "Alto sección inicial [m]",
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
                        _sec_txt = (
                            f"Sección crece "
                            f"{cano_maestro_cfg.area_seccion_inicio_m2:.2f} → "
                            f"{cano_maestro_cfg.area_seccion_m2:.2f} m² · "
                            f"v acotada a **{_dP['v_max_ms']:.1f} m/s** "
                            f"(extremo ventilador {_dP['v_fin_ms']:.1f} m/s)"
                        )
                    else:
                        _sec_txt = (
                            f"Sección constante {cano_maestro_cfg.area_seccion_m2:.2f} m² · "
                            f"v máx **{_dP['v_max_ms']:.1f} m/s** "
                            f"(extremo ventilador {_dP['v_fin_ms']:.1f} m/s)"
                        )
                    st.caption(
                        f"{_sec_txt} · "
                        f"ΔP caño maestro ≈ **{_dP['total']:.0f} Pa** "
                        f"(fricción {_dP['friccion']:.1f} + accesorios "
                        f"{_dP['accesorios']:.1f}). Flujo acumulado a lo largo del "
                        f"caño: la sección creciente mantiene la velocidad acotada "
                        f"con menos material que un caño grande constante."
                    )
                except ValueError as _e:
                    st.error(f"Caño maestro inválido: {_e}")
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
        st.error(f"**Error de validación** ({codigo})\n\n{err}")
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
            st.error(
                f"🚨 El diseño del colector tiene **{len(criticas)} advertencia(s) "
                "crítica(s)**. Revisá el detalle abajo antes de calcular."
            )
        elif warnings:
            st.warning(
                f"⚠️ El diseño del colector tiene **{len(warnings)} advertencia(s)**. "
                "Conviene revisar el detalle abajo."
            )

        with st.expander(
            f"Advertencias de diseño ({len(criticas)} críticas, {len(warnings)} warnings, {len(infos)} info)",
            expanded=bool(criticas),
        ):
            for adv in adv_list:
                icono = _ICONOS_SEVERIDAD[adv.severidad]
                if adv.severidad == Severidad.CRITICAL:
                    st.error(f"{icono} **{adv.codigo}** — {adv.mensaje}\n\n💡 {adv.sugerencia}")
                elif adv.severidad == Severidad.WARNING:
                    st.warning(f"{icono} **{adv.codigo}** — {adv.mensaje}\n\n💡 {adv.sugerencia}")
                else:
                    st.info(f"{icono} **{adv.codigo}** — {adv.mensaje}\n\n💡 {adv.sugerencia}")
    else:
        st.success("Diseño del colector sin advertencias.")

    # -----------------------------------------------------------------------
    # Sección 5b: Evaluación del desempeño del colector unitario
    # (primero un colector; el campo/banco se evalúa a continuación)
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader("Evaluación del desempeño del colector")

    _empl = proyecto.emplazamiento
    _clima = proyecto.clima
    _cfg = proyecto.configuracion
    _prereq_ok = True

    if _empl is None:
        st.warning("Configurá el emplazamiento (P2) para habilitar la evaluación.")
        _prereq_ok = False
    if _clima is None or _clima.datos is None:
        st.warning("Descargá los datos climáticos (P2) para habilitar la evaluación.")
        _prereq_ok = False

    if _prereq_ok:
        _modo_label = {
            ModoAnalisis.DIARIO: "Diario",
            ModoAnalisis.VENTANA: "Ventana de producción",
        }.get(_cfg.modo_analisis, "Anual")
        st.caption(
            f"Modo de análisis: **{_modo_label}** (configurado en P1)  |  "
            f"Pendiente: {_empl.pendiente_colector_deg:.0f}°  |  "
            f"Año climático: {_clima.anio}"
        )

        _render_albedo_suelo(proyecto, _empl)

        if st.button("Calcular desempeño del colector", type="primary", key="p3_calcular_eval"):
            _datos_local = _clima.datos.tz_convert(_empl.zona_horaria)
            _datos_local = _datos_local[_datos_local.index.year == _clima.anio]

            if _cfg.modo_analisis == ModoAnalisis.DIARIO:
                _datos_dia, _fecha = _seleccionar_dia(_datos_local, _cfg, _clima.anio)
                _fecha_label = str(_fecha)
                if len(_datos_dia) == 0:
                    st.error(f"No hay datos para el día {_fecha_label} en el archivo climático.")
                else:
                    with st.spinner(f"Evaluando colector para el {_fecha_label}..."):
                        _r = _evaluar_diario(proyecto.colector, _datos_dia, _empl)
                    st.session_state["p3_eval"] = {"modo": "diario", "r": _r, "label": _fecha_label}
            elif _cfg.modo_analisis == ModoAnalisis.VENTANA:
                from calculos.clima_calc import slice_clima_ventana

                _df_v, _msg_v = slice_clima_ventana(_clima, _cfg.ventana_inicio, _cfg.ventana_fin)
                if _df_v is None:
                    st.error(f"No se pudo recortar la ventana: {_msg_v}")
                else:
                    _datos_v = _df_v.tz_convert(_empl.zona_horaria)
                    _lapso_label = f"{_cfg.ventana_inicio} → {_cfg.ventana_fin}"
                    with st.spinner(
                        f"Evaluando colector sobre la ventana ({len(_datos_v)} horas)..."
                    ):
                        _r = _evaluar_ventana(proyecto.colector, _datos_v, _empl)
                    st.session_state["p3_eval"] = {
                        "modo": "ventana",
                        "r": _r,
                        "label": _lapso_label,
                    }
            else:
                with st.spinner("Evaluando colector para los 12 meses representativos..."):
                    _r = _evaluar_anual(proyecto.colector, _datos_local, _empl, _clima.anio)
                st.session_state["p3_eval"] = {"modo": "anual", "r": _r}

    # Mostrar resultados si existen
    if "p3_eval" in st.session_state and st.session_state["p3_eval"]:
        _ev = st.session_state["p3_eval"]
        _r = _ev["r"]
        _modo = _ev["modo"]

        st.markdown("#### Resultados de la evaluación")

        if _modo == "diario":
            _lbl = _ev["label"]

            # Métricas rápidas
            _T_sal_vals = [t for t in _r["T_salida_C"] if t is not None]
            if _T_sal_vals:
                c1, c2, c3 = st.columns(3)
                c1.metric("T salida máx (día)", f"{max(_T_sal_vals):.1f} °C")
                c2.metric(
                    "T salida en mediodía",
                    (
                        f"{_T_sal_vals[len(_T_sal_vals)//2]:.1f} °C"
                        if _r["hora_transit"] is not None
                        else "—"
                    ),
                )
                c3.metric(
                    "ΔT máx (salida − ambiente)",
                    f"{max(ts - ta for ts, ta in zip(_T_sal_vals, [_r['T_amb_C'][i] for i, t in enumerate(_r['T_salida_C']) if t is not None])):.1f} °C",
                )

            tab_a, tab_b = st.tabs(["9a · T salida vs hora", "9b · Perfil T fluido en mediodía"])

            with tab_a:
                _fig_a = _fig_T_salida_dia(_r, _lbl)
                mostrar_plotly(_fig_a, nombre="colector_Tsalida_dia")

            with tab_b:
                _fig_b = _fig_T_fluido_dia(_r, _lbl)
                if _fig_b is not None:
                    mostrar_plotly(_fig_b, nombre="colector_Tfluido_dia")
                else:
                    st.info("No hay radiación solar suficiente a mediodía para calcular el perfil.")

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
                c1.metric("T salida máx (ventana)", f"{max(_T_vals):.1f} °C")
                c2.metric(
                    "ΔT medio diurno (POA > 50)",
                    f"{sum(ts - ta for ts, ta in _pares) / len(_pares):.1f} °C" if _pares else "—",
                )
                c3.metric(
                    "Horas con T salida > 40 °C",
                    f"{sum(1 for t in _T_vals if t > 40.0)} h",
                )
            _tab_v1, _tab_v2 = st.tabs(
                ["Series sobre la ventana", "Perfil T fluido (mediodía 1er día)"]
            )
            with _tab_v1:
                mostrar_plotly(_fig_T_salida_ventana(_r, _lbl), nombre="colector_Tsalida_ventana")
                st.caption(
                    "Series horarias de **día y noche** (de noche el aire no se "
                    "calienta → T_salida ≈ T_amb). Marcas: POA máx (◆) y mediodía "
                    "solar (▲) de cada día."
                )
            with _tab_v2:
                _fig_perfil_v = _fig_T_fluido_dia(_r, f"primer día de {_lbl}")
                if _fig_perfil_v is not None:
                    mostrar_plotly(_fig_perfil_v, nombre="colector_Tfluido_ventana")
                    st.caption(
                        "⚠️ Esta gráfica representa **sólo el mediodía solar del "
                        "primer día** de la ventana de producción."
                    )
                else:
                    st.info(
                        "No hay radiación suficiente a mediodía del primer día para "
                        "calcular el perfil T(x)."
                    )
            st.caption(
                "Vista previa a **velocidad de diseño** del módulo. El cálculo de "
                "producción (P7) re-corre el colector al caudal real que impone el "
                "ventilador del sistema."
            )

        else:  # anual
            if _r["meses"]:
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "T salida máx (mejor mes)",
                    f"{max(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(max(_r['T_salida_noon_C']))]}",
                )
                c2.metric(
                    "T salida mín (peor mes)",
                    f"{min(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(min(_r['T_salida_noon_C']))]}",
                )
                c3.metric(
                    "ΔT mín colector",
                    f"{min(ts - ta for ts, ta in zip(_r['T_salida_noon_C'], _r['T_amb_noon_C'])):.1f} °C",
                )

                tab_a, tab_b = st.tabs(["9a · T salida vs mes", "9b · Perfil T fluido por mes"])

                with tab_a:
                    _fig_a = _fig_T_salida_anual(_r)
                    mostrar_plotly(_fig_a, nombre="colector_Tsalida_anual")
                    st.caption("Evaluación en el mediodía solar del día 15 de cada mes.")

                with tab_b:
                    _fig_b = _fig_T_fluido_anual(_r)
                    if _fig_b is not None:
                        mostrar_plotly(_fig_b, nombre="colector_Tfluido_anual")
            else:
                st.warning(
                    "No se obtuvieron resultados válidos. Verificá que el clima tenga radiación suficiente."
                )

    # -----------------------------------------------------------------------
    # Sección 5c: Evaluación del campo de colectores (banco, gran escala, S41)
    # (se evalúa después del colector unitario: usa ese colector en cada rama)
    # -----------------------------------------------------------------------

    if tipologia == Tipologia.GRAN_ESCALA:
        st.divider()
        st.subheader("Evaluación del campo de colectores")
        st.caption(
            "Red hidráulica del **banco + caño maestro** (metodología ASHRAE "
            "cap. 21: fricción Darcy-Weisbach por tramo + pérdidas singulares "
            "de boca): reparto real de caudal entre ramas, temperatura de "
            "salida de cada rama a su caudal propio, mezcla en el manifold y "
            "T del flujo a la salida del caño maestro."
        )

        _cam_p4 = getattr(proyecto, "camara", None)
        _rho_ref_campo = 1.05  # kg/m³ ~45 °C — solo para el default del widget
        if _cam_p4 is not None and _cam_p4.flujo.caudal_masico_kg_s > 0:
            _q_def_Ls = _cam_p4.flujo.caudal_masico_kg_s / _rho_ref_campo * 1000.0
            _origen_q = "el caudal del sistema configurado en P4 (caudal único S41)"
        else:
            _q_def_Ls = caudal_total * 1000.0
            _origen_q = "el caudal de diseño del banco (no hay cámara configurada)"

        ci1, ci2, ci3, ci4 = st.columns(4)
        _q_Ls = ci1.number_input(
            "Caudal total [L/s]",
            min_value=1.0,
            max_value=50000.0,
            value=float(max(1.0, _q_def_Ls)),
            step=10.0,
            key="p3_campo_q",
            help=f"Caudal que mueve el ventilador. Default: {_origen_q}.",
        )
        _T_amb_campo = ci2.number_input(
            "T ambiente [°C]",
            min_value=-10.0,
            max_value=50.0,
            value=25.0,
            step=1.0,
            key="p3_campo_tamb",
        )
        _poa_campo = ci3.number_input(
            "POA [W/m²]",
            min_value=0.0,
            max_value=1400.0,
            value=900.0,
            step=50.0,
            key="p3_campo_poa",
            help="Irradiancia sobre el plano del colector (punto de operación representativo).",
        )
        _vw_campo = ci4.number_input(
            "Viento [m/s]",
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.5,
            key="p3_campo_vw",
        )

        if st.button("Evaluar campo de colectores", type="primary", key="p3_btn_campo"):
            from calculos.balance_global import presion_representativa_proyecto
            from calculos.campo_colectores_calc import evaluar_campo_colectores

            _P_campo, _ = presion_representativa_proyecto(proyecto)
            _pend_campo = (
                proyecto.emplazamiento.pendiente_colector_deg
                if proyecto.emplazamiento is not None
                else 25.0
            )
            _n_ramas = proyecto.colector.banco.n_paralelo
            with st.spinner(f"Resolviendo red hidráulica + térmica de {_n_ramas} ramas..."):
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
                st.warning(f"⚠️ {_a}")
            cm1, cm2, cm3, cm4 = st.columns(4)
            cm1.metric(
                "T salida caño maestro",
                (
                    f"{_rc.T_salida_cano_K - 273.15:.1f} °C"
                    if _rc.T_salida_cano_K is not None
                    else "—"
                ),
                delta=(f"{_rc.dT_cano_K:+.1f} K en el caño" if _rc.dT_cano_K is not None else None),
            )
            cm2.metric(
                "T mezcla del banco",
                f"{_rc.T_mezcla_K - 273.15:.1f} °C" if _rc.T_mezcla_K is not None else "—",
            )
            cm3.metric(
                "Desuniformidad de reparto",
                f"{_rc.uniformidad['desviacion_max_pct']:.1f} %",
                help="(q_máx − q_mín) / q_medio. Bajo 10 % se considera buen reparto.",
            )
            cm4.metric(
                "ΔP del sistema (campo)",
                f"{_rc.dP_sistema_Pa:.0f} Pa",
                help="ΔP de trayectoria igualada: rama + troncal del caño maestro.",
            )
            # Compensación de sección del caño (mejora 32): el ΔP del troncal
            # aislado de la rama + el rango de velocidad hacen visible si la
            # sección creciente acota la velocidad al acumular caudal.
            _vp = getattr(_rc, "v_troncal_perfil_ms", None)
            if _vp is not None and len(_vp) > 0:
                cn1, cn2 = st.columns(2)
                cn1.metric(
                    "ΔP troncal del caño",
                    f"{_rc.dP_troncal_Pa:.1f} Pa",
                    help=(
                        "Pérdida del manifold solo (boca 1 lejana → ventilador), "
                        "aislada de la rama. Es lo que responde a la compensación "
                        "de sección del caño."
                    ),
                )
                cn2.metric(
                    "v troncal (mín → máx)",
                    f"{float(_vp.min()):.2f} → {float(_vp.max()):.2f} m/s",
                    help=(
                        "Velocidad del aire a lo largo del caño (extremo lejano → "
                        "ventilador). Una sección creciente la mantiene acotada al "
                        "acumular caudal; una sección chica constante la dispara "
                        "cerca del ventilador."
                    ),
                )
            mostrar_plotly(_fig_campo_colectores(_rc), nombre="campo_colectores")
            st.caption(
                f"Reparto resuelto en {_rc.n_iter} iteraciones "
                f"({'convergió' if _rc.convergio else '**no convergió**'}). "
                f"q por rama: {_rc.uniformidad['q_min_m3_s']*1000:.1f} – "
                f"{_rc.uniformidad['q_max_m3_s']*1000:.1f} L/s."
            )

    # --- Guardar configuración (mejora 4) ---
    st.divider()
    from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

    _eval_p3 = st.session_state.get("p3_eval")
    col_txt, col_json = st.columns(2)
    with col_txt:
        st.download_button(
            "Guardar configuración del colector (.txt)",
            data=_texto_config_colector(proyecto.colector, _eval_p3),
            file_name=nombre_archivo_descarga(proyecto, "colector", "txt"),
            mime="text/plain",
            width="stretch",
        )
    with col_json:
        st.download_button(
            "Guardar configuración del colector (.json)",
            data=dump_json(_json_config_colector(proyecto.colector, _eval_p3)),
            file_name=nombre_archivo_descarga(proyecto, "colector", "json"),
            mime="application/json",
            width="stretch",
        )
