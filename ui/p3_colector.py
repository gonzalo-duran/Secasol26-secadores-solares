"""
Pestaña 3 — Definición y dimensionamiento del colector solar de aire.

Permite al usuario seleccionar materiales del catálogo, configurar la geometría,
la velocidad de diseño y la batería de colectores. Muestra un resumen de diseño
y las advertencias estáticas antes de pasar al cálculo.

Sin cálculo físico aquí: solo configuración de entrada y validación estática.
"""

from __future__ import annotations

from datetime import date as _date_type

import matplotlib.pyplot as plt
import numpy as np
import pvlib
import streamlit as st

from calculos.colector_calc import calcular_colector_tipo1
from calculos.solar_geometria import (
    bin_horario_que_contiene,
    mediodia_solar_transit,
)
from calculos.colector_tipos234_calc import (
    calcular_colector_tipo2,
    calcular_colector_tipo3,
    calcular_colector_tipo4,
)
from core import catalogo
from core.colector import (
    BancoColectores,
    Chimenea,
    Colector,
    ColectorUnidad,
    advertencias_colector,
)
from core.advertencias import Severidad
from core.proyecto import DiaAnalisis, ModoAnalisis, Tipologia
from ui.componentes.unidades import acimut_duffie_a_pvlib, kelvin_a_celsius

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
    return {
        id_mat: datos.get("descripcion", id_mat)
        for id_mat, datos in catalogo_dict.items()
    }


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
    tau = cols[0].number_input("τ solar", min_value=0.0, max_value=1.0, value=0.85,
                                step=0.01, format="%.2f", key=f"{key_prefix}_tau")
    eps = cols[1].number_input("ε IR", min_value=0.0, max_value=1.0, value=0.90,
                                step=0.01, format="%.2f", key=f"{key_prefix}_eps")
    k = cols[2].number_input("k [W/m·K]", min_value=0.01, max_value=5.0, value=0.76,
                              step=0.01, format="%.3f", key=f"{key_prefix}_k")
    Tmax_C = cols[3].number_input("T_max [°C]", min_value=50, max_value=500,
                                   value=150, step=10, key=f"{key_prefix}_Tmax_C")
    return {
        "descripcion": "Definido por el usuario",
        "transmitancia_solar": tau, "emisividad_ir": eps,
        "conductividad_termica": k, "densidad": 2500.0,
        "calor_especifico": 840.0, "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_placa_usuario(key_prefix: str) -> dict:
    st.caption("Propiedades de la placa absorbedora definida por el usuario:")
    cols = st.columns(4)
    alfa = cols[0].number_input("α solar", min_value=0.0, max_value=1.0, value=0.95,
                                 step=0.01, format="%.2f", key=f"{key_prefix}_alfa")
    eps = cols[1].number_input("ε IR", min_value=0.0, max_value=1.0, value=0.15,
                                step=0.01, format="%.2f", key=f"{key_prefix}_eps")
    k = cols[2].number_input("k [W/m·K]", min_value=0.1, max_value=500.0, value=50.0,
                              step=1.0, format="%.1f", key=f"{key_prefix}_k")
    Tmax_C = cols[3].number_input("T_max [°C]", min_value=50, max_value=800,
                                   value=200, step=10, key=f"{key_prefix}_Tmax_C")
    return {
        "descripcion": "Definido por el usuario",
        "absortancia_solar": alfa, "emisividad_ir": eps,
        "conductividad_termica": k, "densidad": 7850.0,
        "calor_especifico": 480.0, "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_aislante_usuario(key_prefix: str) -> dict:
    st.caption("Propiedades del aislante definido por el usuario:")
    cols = st.columns(3)
    k = cols[0].number_input("k [W/m·K]", min_value=0.01, max_value=1.0, value=0.04,
                              step=0.005, format="%.3f", key=f"{key_prefix}_k")
    rho = cols[1].number_input("ρ [kg/m³]", min_value=5.0, max_value=500.0, value=30.0,
                                step=5.0, format="%.0f", key=f"{key_prefix}_rho")
    Tmax_C = cols[2].number_input("T_max [°C]", min_value=50, max_value=500,
                                   value=200, step=10, key=f"{key_prefix}_Tmax_C")
    return {
        "descripcion": "Definido por el usuario",
        "conductividad_termica": k, "densidad": rho,
        "calor_especifico": 1000.0, "T_max_servicio": float(Tmax_C) + 273.15,
    }


def _inputs_fondo_usuario(key_prefix: str) -> dict:
    st.caption("Propiedades del fondo/carcasa definido por el usuario:")
    cols = st.columns(3)
    eps = cols[0].number_input("ε IR", min_value=0.0, max_value=1.0, value=0.90,
                                step=0.01, format="%.2f", key=f"{key_prefix}_eps")
    k = cols[1].number_input("k [W/m·K]", min_value=0.05, max_value=500.0, value=50.0,
                              step=1.0, format="%.1f", key=f"{key_prefix}_k")
    Tmax_C = cols[2].number_input("T_max [°C]", min_value=50, max_value=800,
                                   value=200, step=10, key=f"{key_prefix}_Tmax_C")
    return {
        "descripcion": "Definido por el usuario",
        "emisividad_ir": eps, "conductividad_termica": k,
        "densidad": 7850.0, "calor_especifico": 480.0,
        "T_max_servicio": float(Tmax_C) + 273.15,
    }


# ---------------------------------------------------------------------------
# Generador de texto de configuración (mejora 4)
# ---------------------------------------------------------------------------

def _texto_config_colector(col: "Colector") -> str:
    from datetime import date
    u = col.unidad

    def desc(cat_dict: dict, id_mat: str) -> str:
        return cat_dict.get(id_mat, {}).get("descripcion", id_mat)

    lines = [
        "=== CONFIGURACIÓN DEL COLECTOR SOLAR ===",
        f"Fecha: {date.today()}",
        "",
        "MATERIALES",
        f"  Cubierta : {desc(catalogo.CUBIERTAS, u.id_cubierta)}",
        f"             e = {u.espesor_cubierta_m * 1000:.1f} mm | N° cubiertas = {u.n_cubiertas}",
        f"  Placa    : {desc(catalogo.PLACAS, u.id_placa)}",
        f"             e = {u.espesor_placa_m * 1000:.1f} mm",
        f"  Aislante : {desc(catalogo.AISLANTES, u.id_aislante)}",
        f"             e = {u.espesor_aislante_m * 100:.1f} cm",
        f"  Fondo    : {desc(catalogo.FONDOS, u.id_fondo)}",
        f"             e = {u.espesor_fondo_m * 1000:.1f} mm",
        "",
        "TIPO DE COLECTOR",
        f"  {_TIPOS_COLECTOR.get(u.tipo_colector, f'Tipo {u.tipo_colector}')}",
        "",
        "GEOMETRÍA Y CONDICIÓN DE DISEÑO",
        f"  Ancho           : {u.ancho_m:.2f} m",
        f"  Largo           : {u.largo_m:.2f} m",
        f"  Canal superior  : {u.espaciado_m * 1000:.1f} mm"
        if u.tipo_colector in (2, 3, 4)
        else f"  Espaciado canal : {u.espaciado_m * 1000:.1f} mm",
        *(
            [f"  Canal inferior  : {u.espaciado_inferior_m * 1000:.1f} mm"]
            if u.tipo_colector in (2, 3, 4) else []
        ),
        f"  Vel. diseño     : {u.velocidad_diseno_ms:.2f} m/s",
        f"  Área captación  : {u.area_captacion_m2():.2f} m²",
        f"  Caudal unitario : {u.caudal_volumetrico_m3_s() * 1000:.2f} L/s",
        "",
        "BANCO DE COLECTORES",
        f"  Serie           : {col.banco.n_serie}",
        f"  Paralelo        : {col.banco.n_paralelo}",
        f"  Área total      : {col.banco.n_serie * col.banco.n_paralelo * u.area_captacion_m2():.2f} m²",
        f"  Caudal total    : {col.banco.n_paralelo * u.caudal_volumetrico_m3_s() * 1000:.2f} L/s",
        f"  Camino del aire : {col.banco.n_serie * u.largo_m:.1f} m",
    ]
    if col.chimenea is not None:
        ch = col.chimenea
        lines += [
            "",
            "CHIMENEA SOLAR",
            f"  Diámetro : {ch.diametro_m:.2f} m",
            f"  Altura   : {ch.altura_m:.1f} m",
            f"  Material : {desc(catalogo.FONDOS, ch.id_material)}",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evaluación del colector — cálculo y figuras
# ---------------------------------------------------------------------------

_MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_COLORES_MESES = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45",
    "#fabed4", "#469990", "#dcbeff", "#9a6324",
]


def _poa_serie(datos, lat, lon, alt, pendiente, acimut_pvlib_deg):
    sol_pos = pvlib.solarposition.get_solarposition(datos.index, lat, lon, altitude=alt)
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=pendiente, surface_azimuth=acimut_pvlib_deg,
        solar_zenith=sol_pos["apparent_zenith"], solar_azimuth=sol_pos["azimuth"],
        dni=datos["DNI_Wm2"], ghi=datos["GHI_Wm2"], dhi=datos["DHI_Wm2"],
    )
    return poa["poa_global"].clip(lower=0).fillna(0.0)


def _correr_colector(colector, T_amb_K, I_g_W_m2, v_viento_ms):
    if I_g_W_m2 < 50.0:
        return None
    u = colector.unidad
    tipo = u.tipo_colector
    kw = dict(
        colector=colector, T_amb_K=T_amb_K,
        I_g_W_m2=I_g_W_m2, v_viento_ms=max(v_viento_ms, 0.5),
        P_amb_Pa=101325.0, T_entrada_K=T_amb_K,
    )
    try:
        if tipo == 1:
            return calcular_colector_tipo1(**kw, correlacion_nusselt=None)
        elif tipo == 2:
            return calcular_colector_tipo2(
                **kw, v_diseno_cs_ms=u.velocidad_diseno_ms,
                v_diseno_ci_ms=u.velocidad_diseno_ms,
                alto_cs_m=u.espaciado_m, alto_ci_m=u.espaciado_inferior_m,
            )
        elif tipo == 3:
            return calcular_colector_tipo3(**kw, alto_cs_m=u.espaciado_m, alto_ci_m=u.espaciado_inferior_m)
        elif tipo == 4:
            return calcular_colector_tipo4(**kw, alto_cs_m=u.espaciado_m, alto_ci_m=u.espaciado_inferior_m)
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
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO:
        target = _date_type(anio, 3, 21)
    elif cfg.dia_analisis == DiaAnalisis.MAS_CALUROSO:
        target = ((datos_local["T_amb_K"] - 273.15)
                  .resample("D").mean().idxmax().date())
    else:
        target = ((datos_local["T_amb_K"] - 273.15)
                  .resample("D").mean().idxmin().date())
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
    acimut_pvlib = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
    poa = _poa_serie(datos_dia, empl.latitud_deg, empl.longitud_deg, empl.altitud_m,
                     empl.pendiente_colector_deg, acimut_pvlib)
    tipo = colector.unidad.tipo_colector

    horas, T_sal_C, T_amb_C, poa_list = [], [], [], []
    x_noon = T_perfil_noon_C = None

    if poa.max() > 50:
        # Mediodía solar verdadero (tránsito SPA, resolución continua).
        target = datos_dia.index.date[0]
        hora_transit = mediodia_solar_transit(
            target, empl.latitud_deg, empl.longitud_deg, empl.zona_horaria,
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
        res = _correr_colector(colector, T_amb, I_g, v_w)

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
        "horas": horas, "T_salida_C": T_sal_C, "T_amb_C": T_amb_C, "poa": poa_list,
        "x_noon": x_noon, "T_perfil_noon_C": T_perfil_noon_C,
        "hora_transit": hora_transit, "hora_poa_max": hora_poa_max,
        "tipo": tipo,
    }


def _evaluar_anual(colector, datos_local, empl, anio):
    """Para cada mes: evalúa el colector en el bin horario que contiene el
    mediodía solar verdadero del día 15 (representativo).

    Cambio respecto a la versión anterior: el bin de evaluación se elige
    por el tránsito SPA (independiente de la orientación del colector),
    no por POA máxima. Esto evita que un colector con orientación rara
    desplace artificialmente la evaluación a horas tarde / temprano.
    """
    acimut_pvlib = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
    poa_all = _poa_serie(datos_local, empl.latitud_deg, empl.longitud_deg, empl.altitud_m,
                         empl.pendiente_colector_deg, acimut_pvlib)
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
            target_dia, empl.latitud_deg, empl.longitud_deg, empl.zona_horaria,
        )
        idx_noon = bin_horario_que_contiene(transit, datos_dia.index)
        row = datos_dia.loc[idx_noon]
        I_g = float(poa_dia[idx_noon])
        T_amb = float(row["T_amb_K"])
        v_w = float(row["WS_ms"])

        res = _correr_colector(colector, T_amb, I_g, v_w)
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
        "meses": meses, "T_salida_noon_C": T_sal_C, "T_amb_noon_C": T_amb_C,
        "poa_noon": poa_noon_list, "x_m": x_m, "perfiles_C": perfiles_C, "tipo": tipo,
    }


# --- Figuras ---

def _fig_T_salida_dia(r, fecha_label):
    horas = r["horas"]
    T_sal = r["T_salida_C"]
    T_amb = r["T_amb_C"]
    poa = r["poa"]

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()

    horas_dt = [h.to_pydatetime() for h in horas]

    # POA como área gris de fondo
    ax2.fill_between(horas_dt, poa, alpha=0.15, color="#f5a623", label="POA [W/m²]")
    ax2.set_ylabel("POA [W/m²]", color="#f5a623", fontsize=9)
    ax2.tick_params(axis="y", labelcolor="#f5a623")
    ax2.set_ylim(bottom=0)

    # T_salida (solo horas con sol)
    h_sol = [h for h, t in zip(horas_dt, T_sal) if t is not None]
    t_sol = [t for t in T_sal if t is not None]
    ax1.plot(h_sol, t_sol, color="#e05c2a", linewidth=2, marker="o", markersize=4,
             label="T salida colector [°C]")
    ax1.plot(horas_dt, T_amb, color="#1f77b4", linewidth=1.5, linestyle="--",
             label="T ambiente [°C]")

    if r["hora_transit"] is not None:
        ax1.axvline(
            r["hora_transit"].to_pydatetime(),
            color="#9c27b0", linestyle=":", linewidth=1.8,
            label=f"Mediodía solar ({r['hora_transit'].strftime('%H:%M')})",
        )
    if r["hora_poa_max"] is not None:
        # Pintamos POA máx solo si está separada del transit por al menos
        # 15 min — si caen en el mismo bin, una sola línea es más limpio.
        if (r["hora_transit"] is None
                or abs((r["hora_poa_max"] - r["hora_transit"]).total_seconds()) > 15 * 60):
            ax1.axvline(
                r["hora_poa_max"].to_pydatetime(),
                color="#ff7f0e", linestyle="--", linewidth=1.3,
                label=f"POA máx ({r['hora_poa_max'].strftime('%H:%M')})",
            )

    ax1.set_ylabel("Temperatura [°C]")
    ax1.set_xlabel("")
    ax1.set_title(f"Temperatura de salida del colector — {fecha_label}")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.4)

    import matplotlib.dates as mdates
    # tz de los datos — sin esto, DateFormatter usa UTC por default y el eje
    # aparece corrido respecto al hemisferio occidental (en Salta, +3 h).
    tz_axis = horas[0].tz if horas else None
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=tz_axis))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    return fig


def _fig_T_fluido_dia(r, fecha_label):
    x = r["x_noon"]
    T = r["T_perfil_noon_C"]
    if x is None or T is None:
        return None

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(x, T, color="#e05c2a", linewidth=2)
    ax.axhline(T[0], color="#1f77b4", linestyle="--", linewidth=1, label=f"T entrada = {T[0]:.1f} °C")
    ax.set_xlabel("Posición x a lo largo del colector [m]")
    ax.set_ylabel("Temperatura del fluido [°C]")
    ax.set_title(f"Perfil de temperatura del fluido — mediodía solar — {fecha_label}")
    ax.legend(fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_T_salida_anual(r):
    meses = r["meses"]
    T_sal = r["T_salida_noon_C"]
    T_amb = r["T_amb_noon_C"]
    poa = r["poa_noon"]
    n = len(meses)

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()

    x = list(range(n))
    ax2.bar(x, poa, color="#f5a623", alpha=0.2, label="POA mediodía [W/m²]")
    ax2.set_ylabel("POA [W/m²]", color="#f5a623", fontsize=9)
    ax2.tick_params(axis="y", labelcolor="#f5a623")
    ax2.set_ylim(bottom=0)

    ax1.plot(x, T_sal, color="#e05c2a", linewidth=2, marker="o", markersize=6,
             label="T salida colector — mediodía [°C]")
    ax1.plot(x, T_amb, color="#1f77b4", linewidth=1.5, linestyle="--", marker="s", markersize=4,
             label="T ambiente — mediodía [°C]")

    ax1.set_xticks(x, labels=meses)
    ax1.set_ylabel("Temperatura [°C]")
    ax1.set_title("Temperatura de salida del colector — mediodía solar por mes (día 15)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_T_fluido_anual(r):
    x_m = r["x_m"]
    perfiles = r["perfiles_C"]
    meses = r["meses"]
    if x_m is None or not perfiles:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    for i, (mes, T) in enumerate(zip(meses, perfiles)):
        color = _COLORES_MESES[i % len(_COLORES_MESES)]
        ax.plot(x_m, T, color=color, linewidth=1.8, label=mes)

    ax.set_xlabel("Posición x a lo largo del colector [m]")
    ax.set_ylabel("Temperatura del fluido [°C]")
    ax.set_title("Perfil de temperatura del fluido — mediodía solar por mes")
    ax.legend(fontsize=8, ncol=4, loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
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

    colector: Colector = proyecto.colector

    # -----------------------------------------------------------------------
    # Sección 0: Tipo de colector
    # -----------------------------------------------------------------------

    with st.expander("Tipo de colector", expanded=True):
        ids_tipo = list(_TIPOS_COLECTOR.keys())
        idx_tipo = ids_tipo.index(colector.unidad.tipo_colector) if colector.unidad.tipo_colector in ids_tipo else 0
        tipo_colector = st.selectbox(
            "Configuración del canal de flujo",
            options=ids_tipo,
            index=idx_tipo,
            format_func=lambda x: _TIPOS_COLECTOR[x],
            key="p3_tipo_colector",
        )
        st.info(_TIPOS_HELP[tipo_colector])

    # -----------------------------------------------------------------------
    # Sección 1: Colector unitario — materiales
    # -----------------------------------------------------------------------

    with st.expander("Materiales del colector unitario", expanded=True):

        st.subheader("Cubierta transparente")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_cub = {k: v for k, v in _opciones_material(catalogo.CUBIERTAS).items()
                            if k != _ID_USUARIO}
            opciones_cub[_ID_USUARIO] = "Definido por el usuario"
            ids_cub = list(opciones_cub.keys())
            idx_cub = ids_cub.index(colector.unidad.id_cubierta) if colector.unidad.id_cubierta in ids_cub else 0
            id_cubierta = st.selectbox(
                "Material de cubierta",
                options=ids_cub,
                index=idx_cub,
                format_func=lambda x: opciones_cub[x],
                key="p3_id_cubierta",
            )
        with c2:
            espesor_cubierta_mm = st.number_input(
                "Espesor [mm]",
                min_value=1.0, max_value=20.0,
                value=colector.unidad.espesor_cubierta_m * 1000,
                step=0.5,
                key="p3_esp_cubierta",
            )
            n_cubiertas = st.selectbox(
                "N° cubiertas",
                options=[1, 2],
                index=colector.unidad.n_cubiertas - 1,
                key="p3_n_cubiertas",
                help="1 cubierta es lo estándar. 2 cubiertas reduce pérdidas pero baja la transmitancia.",
            )
        if id_cubierta == _ID_USUARIO:
            catalogo.CUBIERTAS[_ID_USUARIO] = _inputs_cubierta_usuario("p3_ucub")
        _tabla_propiedades_cubierta(id_cubierta)

        st.divider()
        st.subheader("Placa absorbedora")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_pla = {k: v for k, v in _opciones_material(catalogo.PLACAS).items()
                            if k != _ID_USUARIO}
            opciones_pla[_ID_USUARIO] = "Definido por el usuario"
            ids_pla = list(opciones_pla.keys())
            idx_pla = ids_pla.index(colector.unidad.id_placa) if colector.unidad.id_placa in ids_pla else 0
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
                min_value=0.3, max_value=5.0,
                value=colector.unidad.espesor_placa_m * 1000,
                step=0.1,
                key="p3_esp_placa",
            )
        if id_placa == _ID_USUARIO:
            catalogo.PLACAS[_ID_USUARIO] = _inputs_placa_usuario("p3_upla")
        _tabla_propiedades_placa(id_placa)

        st.divider()
        st.subheader("Aislante térmico")
        c1, c2 = st.columns([3, 1])
        with c1:
            opciones_ais = {k: v for k, v in _opciones_material(catalogo.AISLANTES).items()
                            if k != _ID_USUARIO}
            opciones_ais[_ID_USUARIO] = "Definido por el usuario"
            ids_ais = list(opciones_ais.keys())
            idx_ais = ids_ais.index(colector.unidad.id_aislante) if colector.unidad.id_aislante in ids_ais else 0
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
                min_value=1.0, max_value=20.0,
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
            opciones_fon = {k: v for k, v in _opciones_material(catalogo.FONDOS).items()
                            if k != _ID_USUARIO}
            opciones_fon[_ID_USUARIO] = "Definido por el usuario"
            ids_fon = list(opciones_fon.keys())
            idx_fon = ids_fon.index(colector.unidad.id_fondo) if colector.unidad.id_fondo in ids_fon else 0
            id_fondo = st.selectbox(
                "Material de fondo",
                options=ids_fon,
                index=idx_fon,
                format_func=lambda x: opciones_fon[x],
                key="p3_id_fondo",
            )
        with c2:
            espesor_fondo_mm = st.number_input(
                "Espesor [mm]",
                min_value=0.3, max_value=5.0,
                value=colector.unidad.espesor_fondo_m * 1000,
                step=0.1,
                key="p3_esp_fondo",
            )
        if id_fondo == _ID_USUARIO:
            catalogo.FONDOS[_ID_USUARIO] = _inputs_fondo_usuario("p3_ufon")
        _tabla_propiedades_fondo(id_fondo)

    # -----------------------------------------------------------------------
    # Sección 2: Colector unitario — geometría y velocidad
    # -----------------------------------------------------------------------

    with st.expander("Geometría y condición de diseño", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ancho_m = st.number_input(
                "Ancho del canal [m]",
                min_value=0.1, max_value=5.0,
                value=float(colector.unidad.ancho_m),
                step=0.05,
                format="%.2f",
                key="p3_ancho",
                help="Ancho interior del canal de flujo (dimensión perpendicular al flujo).",
            )
            largo_m = st.number_input(
                "Largo del colector [m]",
                min_value=0.1, max_value=20.0,
                value=float(colector.unidad.largo_m),
                step=0.1,
                format="%.2f",
                key="p3_largo",
                help="Variable de diseño para la optimización del largo óptimo.",
            )
        with c2:
            _label_esp = (
                "Espaciado cubierta–placa [mm]" if tipo_colector == 1
                else "Canal superior cubierta–absorbedor [mm]"
            )
            _help_esp = (
                "Altura del canal único de flujo. Típico: 15–50 mm."
                if tipo_colector == 1
                else "Altura del canal superior (cubierta–absorbedor). Típico: 15–50 mm."
            )
            espaciado_mm = st.number_input(
                _label_esp,
                min_value=5.0, max_value=200.0,
                value=colector.unidad.espaciado_m * 1000,
                step=1.0,
                format="%.1f",
                key="p3_espaciado",
                help=_help_esp,
            )
            if tipo_colector in (2, 3, 4):
                espaciado_inferior_mm = st.number_input(
                    "Canal inferior absorbedor–fondo [mm]",
                    min_value=5.0, max_value=200.0,
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
                min_value=0.01, max_value=10.0,
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

    with st.expander("Banco de colectores", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            n_serie = st.number_input(
                "Colectores en serie por rama",
                min_value=1, max_value=10,
                value=colector.banco.n_serie,
                step=1,
                key="p3_n_serie",
                help="El aire pasa por N colectores consecutivos. Aumenta ΔT de salida.",
            )
        with c2:
            n_paralelo = st.number_input(
                "Ramas en paralelo",
                min_value=1, max_value=20,
                value=colector.banco.n_paralelo,
                step=1,
                key="p3_n_paralelo",
                help="Ramas paralelas. El motor mueve la suma de los caudales de todas las ramas.",
            )

        caudal_total = n_paralelo * caudal_unit_m3s
        area_total = n_serie * n_paralelo * ancho_m * largo_m
        largo_camino = n_serie * largo_m

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Caudal total al motor", f"{caudal_total*1000:.1f} L/s",
                      help="n_paralelo × caudal por unidad. Caudal volumétrico a condiciones de diseño.")
        col_m2.metric("Área de captación total", f"{area_total:.2f} m²")
        col_m3.metric("Camino del aire", f"{largo_camino:.1f} m",
                      help="n_serie × largo de unidad. Longitud total que recorre el aire.")

    # -----------------------------------------------------------------------
    # Sección 4: Chimenea (solo si convección natural)
    # -----------------------------------------------------------------------

    usar_chimenea = st.checkbox(
        "Incorporar chimenea solar (convección natural o asistida)",
        value=colector.chimenea is not None,
        key="p3_usar_chimenea",
        help="Activa la configuración de chimenea solar para inducir tiraje natural.",
    )

    chim_data: dict = {}
    if usar_chimenea:
        with st.expander("Chimenea solar", expanded=True):
            ch_ref = colector.chimenea or Chimenea()
            c1, c2, c3 = st.columns(3)
            with c1:
                chim_diametro = st.number_input(
                    "Diámetro interno [m]",
                    min_value=0.05, max_value=2.0,
                    value=float(ch_ref.diametro_m),
                    step=0.01,
                    format="%.2f",
                    key="p3_chim_diam",
                )
            with c2:
                chim_altura = st.number_input(
                    "Altura [m]",
                    min_value=0.1, max_value=20.0,
                    value=float(ch_ref.altura_m),
                    step=0.1,
                    format="%.1f",
                    key="p3_chim_altura",
                )
            with c3:
                opciones_fon_chim = _opciones_material(catalogo.FONDOS)
                ids_fon_chim = list(opciones_fon_chim.keys())
                idx_fon_chim = ids_fon_chim.index(ch_ref.id_material) if ch_ref.id_material in ids_fon_chim else 0
                chim_material = st.selectbox(
                    "Material",
                    options=ids_fon_chim,
                    index=idx_fon_chim,
                    format_func=lambda x: opciones_fon_chim[x],
                    key="p3_chim_material",
                )
            chim_data = {
                "diametro_m": chim_diametro,
                "altura_m": chim_altura,
                "id_material": chim_material,
            }

    # -----------------------------------------------------------------------
    # Aplicar cambios al session_state
    # -----------------------------------------------------------------------

    try:
        nueva_unidad = ColectorUnidad(
            ancho_m=ancho_m,
            largo_m=largo_m,
            espaciado_m=espaciado_mm / 1000,
            n_cubiertas=n_cubiertas,
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
        )
        nuevo_banco = BancoColectores(n_serie=n_serie, n_paralelo=n_paralelo)
        nueva_chimenea = Chimenea(**chim_data) if usar_chimenea else None

        nuevo_colector = Colector(
            unidad=nueva_unidad,
            banco=nuevo_banco,
            chimenea=nueva_chimenea,
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
    # Sección 6: Evaluación del desempeño del colector
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
        _modo_label = "Diario" if _cfg.modo_analisis == ModoAnalisis.DIARIO else "Anual"
        st.caption(
            f"Modo de análisis: **{_modo_label}** (configurado en P1)  |  "
            f"Pendiente: {_empl.pendiente_colector_deg:.0f}°  |  "
            f"Año climático: {_clima.anio}"
        )

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
                c2.metric("T salida en mediodía", f"{_T_sal_vals[len(_T_sal_vals)//2]:.1f} °C"
                           if _r['hora_transit'] is not None else "—")
                c3.metric("ΔT máx (salida − ambiente)",
                           f"{max(ts - ta for ts, ta in zip(_T_sal_vals, [_r['T_amb_C'][i] for i, t in enumerate(_r['T_salida_C']) if t is not None])):.1f} °C")

            tab_a, tab_b = st.tabs(["9a · T salida vs hora", "9b · Perfil T fluido en mediodía"])

            with tab_a:
                _fig_a = _fig_T_salida_dia(_r, _lbl)
                st.pyplot(_fig_a, clear_figure=True)
                plt.close(_fig_a)

            with tab_b:
                _fig_b = _fig_T_fluido_dia(_r, _lbl)
                if _fig_b is not None:
                    st.pyplot(_fig_b, clear_figure=True)
                    plt.close(_fig_b)
                else:
                    st.info("No hay radiación solar suficiente a mediodía para calcular el perfil.")

        else:  # anual
            if _r["meses"]:
                c1, c2, c3 = st.columns(3)
                c1.metric("T salida máx (mejor mes)",
                           f"{max(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(max(_r['T_salida_noon_C']))]}")
                c2.metric("T salida mín (peor mes)",
                           f"{min(_r['T_salida_noon_C']):.1f} °C — {_r['meses'][_r['T_salida_noon_C'].index(min(_r['T_salida_noon_C']))]}")
                c3.metric("ΔT mín colector",
                           f"{min(ts - ta for ts, ta in zip(_r['T_salida_noon_C'], _r['T_amb_noon_C'])):.1f} °C")

                tab_a, tab_b = st.tabs(["9a · T salida vs mes", "9b · Perfil T fluido por mes"])

                with tab_a:
                    _fig_a = _fig_T_salida_anual(_r)
                    st.pyplot(_fig_a, clear_figure=True)
                    plt.close(_fig_a)
                    st.caption("Evaluación en el mediodía solar del día 15 de cada mes.")

                with tab_b:
                    _fig_b = _fig_T_fluido_anual(_r)
                    if _fig_b is not None:
                        st.pyplot(_fig_b, clear_figure=True)
                        plt.close(_fig_b)
            else:
                st.warning("No se obtuvieron resultados válidos. Verificá que el clima tenga radiación suficiente.")

    # --- Guardar configuración (mejora 4) ---
    st.divider()
    st.download_button(
        "Guardar configuración del colector (.txt)",
        data=_texto_config_colector(proyecto.colector),
        file_name="config_colector.txt",
        mime="text/plain",
        use_container_width=True,
    )
