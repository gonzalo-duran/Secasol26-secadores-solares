"""
Pestaña 2 — Emplazamiento y Recursos Climáticos.

Permite al usuario configurar la ubicación y orientación del colector,
descargar datos horarios de NASA POWER y visualizar el recurso solar/climático.

Convención de ángulos en la UI: Duffie (acimut 0° = Sur).
Las conversiones a pvlib ocurren en ui/componentes/unidades.py, nunca aquí.
"""

from __future__ import annotations

import io

import matplotlib.pyplot as plt
import pandas as pd
import pvlib
import streamlit as st

from calculos.clima_calc import obtener_clima
from core.clima import Clima
from core.emplazamiento import Emplazamiento
from ui.componentes.unidades import (
    acimut_duffie_a_pvlib,
    acimut_duffie_a_ui360,
    acimut_ui360_a_duffie,
    fraccion_a_porcentaje,
    kelvin_a_celsius,
    pa_a_hpa,
)

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ZONAS_HORARIAS = [
    "America/Argentina/Salta",
    "America/Argentina/Buenos_Aires",
    "America/Argentina/Cordoba",
    "America/Argentina/Mendoza",
    "America/Argentina/Tucuman",
    "America/Argentina/Jujuy",
    "America/Argentina/San_Juan",
    "America/Santiago",
    "America/La_Paz",
    "America/Lima",
    "America/Bogota",
    "America/Caracas",
    "America/Asuncion",
    "America/Montevideo",
    "America/Sao_Paulo",
    "America/Mexico_City",
    "America/New_York",
    "Europe/Madrid",
    "UTC",
]

_ANIO_MIN = 2001
_ANIO_MAX = 2023
_ANIO_DEFAULT = 2022


# ---------------------------------------------------------------------------
# Helpers internos de visualización
# ---------------------------------------------------------------------------


def _resumen_mensual(datos_local: pd.DataFrame) -> pd.DataFrame:
    """Agrega datos horarios en estadísticas mensuales para visualización.

    Args:
        datos_local: DataFrame SI con índice en zona horaria local.

    Returns:
        DataFrame con estadísticas mensuales en unidades de UI.
    """
    T_C = datos_local["T_amb_K"] - 273.15
    pres_hPa = datos_local["presion_Pa"] / 100.0
    HR_pct = datos_local["HR"] * 100.0

    t_mes = T_C.resample("ME").agg(["mean", "min", "max"])
    ghi_mes_kWh = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_mes_kWh = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_mes_kWh = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    ws_mes = datos_local["WS_ms"].resample("ME").mean()
    hr_mes = HR_pct.resample("ME").mean()
    p_mes = pres_hPa.resample("ME").mean()

    _MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    nombres_mes = [_MES_ABBR[ts.month - 1] for ts in t_mes.index]

    df = pd.DataFrame(
        {
            "Mes": nombres_mes,
            "T prom [°C]": t_mes["mean"].round(1).values,
            "T min [°C]": t_mes["min"].round(1).values,
            "T max [°C]": t_mes["max"].round(1).values,
            "GHI [kWh/m²]": ghi_mes_kWh.round(1).values,
            "DNI [kWh/m²]": dni_mes_kWh.round(1).values,
            "DHI [kWh/m²]": dhi_mes_kWh.round(1).values,
            "Viento [m/s]": ws_mes.round(1).values,
            "HR [%]": hr_mes.round(1).values,
            "Presión [hPa]": p_mes.round(1).values,
        }
    )
    return df


def _fig_temperatura(datos_local: pd.DataFrame) -> plt.Figure:
    """Genera figura de temperatura media diaria y promedio mensual.

    Args:
        datos_local: DataFrame SI con índice en zona horaria local.

    Returns:
        Figura matplotlib.
    """
    T_C = datos_local["T_amb_K"] - 273.15
    T_diaria = T_C.resample("D").mean()
    T_mensual = T_C.resample("ME").mean()

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(T_diaria.index, T_diaria.values, color="#aec6e8", linewidth=0.7, label="Media diaria")
    ax.plot(T_mensual.index, T_mensual.values, color="#1f77b4", linewidth=2.0, marker="o",
            markersize=4, label="Media mensual")
    ax.set_ylabel("Temperatura [°C]")
    ax.set_xlabel("")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_irradiancia(datos_local: pd.DataFrame) -> plt.Figure:
    """Genera figura de irradiación mensual (GHI, DNI, DHI).

    Args:
        datos_local: DataFrame SI con índice en zona horaria local.

    Returns:
        Figura matplotlib.
    """
    _MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    ghi_s = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_s = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_s = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ghi_s.index]
    ghi = ghi_s.values
    dni = dni_s.values
    dhi = dhi_s.values
    n = len(ghi)
    x = range(n)

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.bar(x, ghi, label="GHI", color="#f5a623", alpha=0.85)
    ax.bar(x, dhi, label="DHI", color="#7ec8e3", alpha=0.85)
    ax.bar(x, dni, label="DNI", color="#e05c2a", alpha=0.85, bottom=dhi)
    ax.set_xticks(list(x), labels=etiquetas)
    ax.set_ylabel("Irradiación mensual [kWh/m²]")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_viento_hr(datos_local: pd.DataFrame) -> plt.Figure:
    """Genera figura de velocidad del viento y humedad relativa mensuales.

    Args:
        datos_local: DataFrame SI con índice en zona horaria local.

    Returns:
        Figura matplotlib.
    """
    _MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    ws_s = datos_local["WS_ms"].resample("ME").mean()
    hr_s = (datos_local["HR"] * 100.0).resample("ME").mean()
    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ws_s.index]
    ws = ws_s.values
    hr = hr_s.values
    n = len(ws)
    x = list(range(n))

    fig, ax1 = plt.subplots(figsize=(10, 3.5))
    ax2 = ax1.twinx()

    ax1.bar(x, ws, color="#4caf50", alpha=0.7, label="Viento [m/s]")
    ax2.plot(x, hr, color="#9c27b0", linewidth=2.0, marker="o", markersize=4,
             label="HR [%]")

    ax1.set_xticks(x, labels=etiquetas)
    ax1.set_ylabel("Velocidad del viento [m/s]", color="#4caf50")
    ax2.set_ylabel("Humedad relativa [%]", color="#9c27b0")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.3)

    lineas1, etq1 = ax1.get_legend_handles_labels()
    lineas2, etq2 = ax2.get_legend_handles_labels()
    ax1.legend(lineas1 + lineas2, etq1 + etq2, loc="upper right", fontsize=9)

    fig.tight_layout()
    return fig


def _calcular_poa_horaria(
    datos_local: pd.DataFrame,
    lat: float,
    lon: float,
    altitud_m: float,
    pendiente_deg: float,
    acimut_pvlib_deg: float,
) -> pd.Series:
    """Calcula la irradiancia global sobre el plano del colector (POA) hora a hora.

    Usa pvlib para la posición solar y el modelo de transposición Hay-Davies.

    Args:
        datos_local: DataFrame SI con índice tz-aware (hora local).
        lat: Latitud [°].
        lon: Longitud [°].
        altitud_m: Altitud [m].
        pendiente_deg: Inclinación del colector [°].
        acimut_pvlib_deg: Acimut del colector en convención pvlib [°].

    Returns:
        Serie de POA global [W/m²], misma frecuencia que datos_local.
    """
    solar_pos = pvlib.solarposition.get_solarposition(
        datos_local.index, lat, lon, altitude=altitud_m
    )
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=pendiente_deg,
        surface_azimuth=acimut_pvlib_deg,
        solar_zenith=solar_pos["apparent_zenith"],
        solar_azimuth=solar_pos["azimuth"],
        dni=datos_local["DNI_Wm2"],
        ghi=datos_local["GHI_Wm2"],
        dhi=datos_local["DHI_Wm2"],
    )
    return poa["poa_global"].clip(lower=0).fillna(0.0)


def _fig_irradiancia_comparativa(
    datos_local: pd.DataFrame,
    poa_horaria: pd.Series,
) -> plt.Figure:
    """Figura con dos subgráficos: irradiación en plano horizontal y en plano del colector.

    Args:
        datos_local: DataFrame SI con índice tz-aware (hora local).
        poa_horaria: Serie de POA global [W/m²], misma frecuencia que datos_local.

    Returns:
        Figura matplotlib con dos subplots verticales.
    """
    _MES_ABBR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                 "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    ghi_s = datos_local["GHI_Wm2"].resample("ME").sum() / 1000.0
    dni_s = datos_local["DNI_Wm2"].resample("ME").sum() / 1000.0
    dhi_s = datos_local["DHI_Wm2"].resample("ME").sum() / 1000.0
    poa_s = poa_horaria.resample("ME").sum() / 1000.0

    etiquetas = [_MES_ABBR[ts.month - 1] for ts in ghi_s.index]
    n = len(etiquetas)
    x = list(range(n))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    # Panel superior: plano horizontal
    ax1.bar(x, ghi_s.values, label="GHI", color="#f5a623", alpha=0.85)
    ax1.bar(x, dhi_s.values, label="DHI", color="#7ec8e3", alpha=0.85)
    ax1.bar(x, dni_s.values, label="DNI", color="#e05c2a", alpha=0.85, bottom=dhi_s.values)
    ax1.set_ylabel("Irradiación mensual [kWh/m²]")
    ax1.set_title("Plano horizontal (GHI / DNI / DHI)")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.4)

    # Panel inferior: plano del colector (POA)
    ax2.bar(x, poa_s.values, label="POA global", color="#4caf50", alpha=0.85)
    ax2.set_xticks(x, labels=etiquetas)
    ax2.set_ylabel("Irradiación mensual [kWh/m²]")
    ax2.set_title("Plano del colector (POA global)")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, axis="y", linestyle="--", alpha=0.4)

    fig.tight_layout()
    return fig


def _generar_csv(datos: pd.DataFrame, zona_horaria: str) -> bytes:
    """Genera un CSV con los datos en unidades de UI (no SI).

    Args:
        datos: DataFrame SI con índice UTC tz-aware.
        zona_horaria: Identificador IANA para convertir el índice.

    Returns:
        Bytes del archivo CSV codificado en UTF-8.
    """
    export = datos.tz_convert(zona_horaria).copy()
    export.index.name = "fecha_hora_local"
    export["T_amb_C"] = export["T_amb_K"] - 273.15
    export["HR_pct"] = export["HR"] * 100.0
    export["presion_hPa"] = export["presion_Pa"] / 100.0

    columnas_csv = {
        "T_amb_C": "T_amb [°C]",
        "GHI_Wm2": "GHI [W/m²]",
        "DNI_Wm2": "DNI [W/m²]",
        "DHI_Wm2": "DHI [W/m²]",
        "WS_ms": "Viento [m/s]",
        "HR_pct": "HR [%]",
        "presion_hPa": "Presión [hPa]",
    }
    df_out = export[list(columnas_csv.keys())].rename(columns=columnas_csv)
    buf = io.StringIO()
    df_out.to_csv(buf, encoding="utf-8")
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la pestaña 2: Emplazamiento y Recursos Climáticos."""

    st.header("Emplazamiento y Recursos Climáticos")

    proyecto = st.session_state.proyecto

    # Inicializar emplazamiento con defaults si es la primera vez
    if proyecto.emplazamiento is None:
        proyecto.emplazamiento = Emplazamiento()

    empl: Emplazamiento = proyecto.emplazamiento

    # -----------------------------------------------------------------------
    # Sección 1: Ubicación geográfica
    # -----------------------------------------------------------------------

    with st.expander("Ubicación geográfica", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            lat = st.number_input(
                "Latitud [°]",
                min_value=-90.0,
                max_value=90.0,
                value=float(empl.latitud_deg),
                step=0.01,
                format="%.4f",
                help="Norte positivo. Rango: −90° a +90°.",
            )
            lon = st.number_input(
                "Longitud [°]",
                min_value=-180.0,
                max_value=180.0,
                value=float(empl.longitud_deg),
                step=0.01,
                format="%.4f",
                help="Este positivo. Rango: −180° a +180°.",
            )
        with c2:
            alt = st.number_input(
                "Altitud [m s.n.m.]",
                min_value=-500.0,
                max_value=8850.0,
                value=float(empl.altitud_m),
                step=10.0,
                format="%.0f",
                help="Altitud del sitio. NASA POWER reporta la altitud de su punto de grilla.",
            )
            tz_idx = _ZONAS_HORARIAS.index(empl.zona_horaria) if empl.zona_horaria in _ZONAS_HORARIAS else 0
            zona = st.selectbox(
                "Zona horaria",
                options=_ZONAS_HORARIAS,
                index=tz_idx,
                help="Identificador IANA de zona horaria local.",
            )
        with c3:
            st.caption("Referencia geográfica")
            hemisferio = "Sur" if lat < 0 else "Norte"
            meridiano = "Oeste" if lon < 0 else "Este"
            st.info(
                f"**Lat:** {abs(lat):.4f}° {hemisferio}\n\n"
                f"**Lon:** {abs(lon):.4f}° {meridiano}\n\n"
                f"**Alt:** {alt:.0f} m"
            )

        # Aplicar cambios al emplazamiento
        try:
            nuevo_empl = Emplazamiento(
                latitud_deg=lat,
                longitud_deg=lon,
                altitud_m=alt,
                acimut_colector_deg=empl.acimut_colector_deg,
                pendiente_colector_deg=empl.pendiente_colector_deg,
                zona_horaria=zona,
            )
            if nuevo_empl != empl:
                # Si cambió la posición geográfica, invalidar datos climáticos
                if (
                    abs(nuevo_empl.latitud_deg - empl.latitud_deg) > 1e-4
                    or abs(nuevo_empl.longitud_deg - empl.longitud_deg) > 1e-4
                ):
                    proyecto.clima = None
                proyecto.emplazamiento = nuevo_empl
                empl = nuevo_empl
        except ValueError as err:
            codigo = str(err).split(":")[0]
            st.error(f"Error de validación ({codigo}): {err}")

    # -----------------------------------------------------------------------
    # Sección 2: Orientación del colector
    # -----------------------------------------------------------------------

    with st.expander("Orientación del colector", expanded=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            # Mostrar en convención UI360 (0=S, 90=E, 180=N, 270=O)
            acimut_ui360 = st.number_input(
                "Acimut del colector [°]  —  0° = Sur, 90° = Este, 180° = Norte, 270° = Oeste",
                min_value=0.0,
                max_value=360.0,
                value=float(acimut_duffie_a_ui360(empl.acimut_colector_deg)),
                step=1.0,
                format="%.1f",
                help=(
                    "Convención: 0° = Sur, 90° = Este, 180° = Norte, 270° = Oeste.\n"
                    "En el hemisferio sur, un colector óptimo apunta al Norte (180°)."
                ),
            )
            pendiente = st.number_input(
                "Pendiente / inclinación [°]  —  0° = horizontal, 90° = vertical",
                min_value=0.0,
                max_value=90.0,
                value=float(empl.pendiente_colector_deg),
                step=1.0,
                format="%.1f",
                help="Ángulo entre el plano del colector y la horizontal.",
            )
        with c2:
            st.caption("Orientación del colector")
            _puntos_ui360 = {
                0.0: "Sur", 45.0: "SE", 90.0: "Este",
                135.0: "NE", 180.0: "Norte", 225.0: "NO",
                270.0: "Oeste", 315.0: "SO", 360.0: "Sur",
            }
            referencia = min(_puntos_ui360.keys(), key=lambda k: abs(k - acimut_ui360))
            acimut_duffie = acimut_ui360_a_duffie(acimut_ui360)
            acimut_pvlib = acimut_duffie_a_pvlib(acimut_duffie)
            st.metric("Orientación aproximada", _puntos_ui360[referencia])
            st.caption(f"Acimut pvlib (interno): {acimut_pvlib:.1f}°")
            st.caption(f"Inclinación: {pendiente:.1f}°")

        # Actualizar emplazamiento con orientación (almacenamiento en Duffie)
        try:
            nuevo_empl = Emplazamiento(
                latitud_deg=empl.latitud_deg,
                longitud_deg=empl.longitud_deg,
                altitud_m=empl.altitud_m,
                acimut_colector_deg=acimut_duffie,
                pendiente_colector_deg=pendiente,
                zona_horaria=empl.zona_horaria,
            )
            if nuevo_empl != empl:
                proyecto.emplazamiento = nuevo_empl
                empl = nuevo_empl
        except ValueError as err:
            codigo = str(err).split(":")[0]
            st.error(f"Error de validación ({codigo}): {err}")

    # -----------------------------------------------------------------------
    # Sección 3: Datos climáticos NASA POWER
    # -----------------------------------------------------------------------

    st.subheader("Datos climáticos NASA POWER")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        anio = st.number_input(
            "Año de referencia",
            min_value=_ANIO_MIN,
            max_value=_ANIO_MAX,
            value=_ANIO_DEFAULT,
            step=1,
            help=(
                f"Año calendar de los datos horarios. "
                f"Rango disponible en NASA POWER: {_ANIO_MIN}–{_ANIO_MAX}."
            ),
        )
    with c2:
        forzar = st.checkbox(
            "Forzar re-descarga",
            value=False,
            help="Ignora el caché local y descarga nuevamente desde NASA POWER.",
        )
    with c3:
        st.write("")
        st.write("")
        boton_descarga = st.button("Descargar datos", type="primary", use_container_width=True)

    clima: Clima | None = proyecto.clima

    if boton_descarga:
        with st.spinner(f"Descargando datos NASA POWER para ({empl.latitud_deg:.4f}, {empl.longitud_deg:.4f}), año {anio}..."):
            try:
                clima = obtener_clima(empl, int(anio), forzar_descarga=forzar)
                proyecto.clima = clima
                st.success(
                    f"Datos cargados: {len(clima.datos):,} registros horarios. "
                    f"Altitud NASA POWER: {clima.altitud_nasa_m:.0f} m s.n.m."
                )
            except RuntimeError as err:
                st.error(f"Error de descarga: {err}")
                clima = None

    # -----------------------------------------------------------------------
    # Mostrar estado de la descarga previa (si existe en session_state)
    # -----------------------------------------------------------------------

    if clima is not None and clima.datos is not None:
        datos = clima.datos
        cal = clima.calidad

        # Resumen de calidad
        col_cal = st.columns(4)
        col_cal[0].metric("Registros totales", f"{len(datos):,}")
        col_cal[1].metric("Año de datos", str(clima.anio))
        col_cal[2].metric(
            "Horas interpoladas",
            f"{cal.n_horas_interpoladas}",
            help="Huecos ≤ 3 h corregidos por interpolación.",
        )
        col_cal[3].metric(
            "Horas bloqueadas",
            f"{cal.n_horas_bloqueadas}",
            delta=None if cal.n_horas_bloqueadas == 0 else "⚠",
            help="Huecos > 3 h que requieren decisión del usuario.",
        )

        # ---- Decisión de usuario para huecos bloqueados ----
        if cal.n_horas_bloqueadas > 0 and cal.decision_usuario is None:
            st.warning(
                f"Se detectaron {cal.n_horas_bloqueadas} horas con datos faltantes "
                f"(hueco máximo: {cal.mayor_hueco_h} h > límite de 3 h para interpolación). "
                "Los cálculos posteriores pueden fallar si se procesan esas horas."
            )
            decision = st.radio(
                "¿Cómo continuar?",
                options=["aceptar_con_nulos", "descargar_nuevo_anio"],
                format_func=lambda x: {
                    "aceptar_con_nulos": "Continuar con horas faltantes (NaN). Los cálculos ignorarán esos instantes.",
                    "descargar_nuevo_anio": "Seleccionar otro año y volver a descargar.",
                }[x],
                key="p2_decision_huecos",
            )
            if st.button("Confirmar decisión"):
                clima.calidad.decision_usuario = decision
                proyecto.clima = clima
                if decision == "descargar_nuevo_anio":
                    proyecto.clima = None
                    st.rerun()
                else:
                    st.success("Decisión guardada. Podés continuar con el prediseño.")

        elif cal.n_horas_bloqueadas > 0 and cal.decision_usuario == "aceptar_con_nulos":
            st.info(
                f"{cal.n_horas_bloqueadas} horas con NaN aceptadas. "
                "Los cálculos ignorarán esos instantes."
            )

        # -----------------------------------------------------------------------
        # Sección 4: Visualizaciones
        # -----------------------------------------------------------------------

        st.subheader("Recurso climático anual")
        st.caption(
            f"Datos horarios NASA POWER — Año {clima.anio} — "
            f"({empl.latitud_deg:.4f}°, {empl.longitud_deg:.4f}°)"
        )

        # Convertir índice a zona horaria local y recortar al año de análisis.
        # Sin el recorte, la conversión UTC→local desplaza algunas horas al
        # año anterior (ej. 00:00 UTC del 1-ene = 21:00 del 31-dic en UTC-3),
        # generando un bucket extra en el resample mensual (13 meses en vez de 12).
        datos_local = datos.tz_convert(empl.zona_horaria)
        datos_local = datos_local[datos_local.index.year == clima.anio]

        tab_t, tab_rad, tab_vhr, tab_tabla = st.tabs(
            ["Temperatura", "Irradiancia solar", "Viento y Humedad", "Tabla mensual"]
        )

        with tab_t:
            fig_t = _fig_temperatura(datos_local)
            st.pyplot(fig_t, clear_figure=True)
            plt.close(fig_t)

        with tab_rad:
            acimut_pvlib_actual = acimut_duffie_a_pvlib(empl.acimut_colector_deg)
            with st.spinner("Calculando irradiancia sobre el plano del colector..."):
                poa_horaria = _calcular_poa_horaria(
                    datos_local,
                    lat=empl.latitud_deg,
                    lon=empl.longitud_deg,
                    altitud_m=empl.altitud_m,
                    pendiente_deg=empl.pendiente_colector_deg,
                    acimut_pvlib_deg=acimut_pvlib_actual,
                )
            fig_rad = _fig_irradiancia_comparativa(datos_local, poa_horaria)
            st.pyplot(fig_rad, clear_figure=True)
            plt.close(fig_rad)

            poa_anual = poa_horaria.sum() / 1000.0
            ghi_anual = datos_local["GHI_Wm2"].sum() / 1000.0
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("GHI anual", f"{ghi_anual:.0f} kWh/m²")
            col_b.metric("POA anual (plano colector)", f"{poa_anual:.0f} kWh/m²",
                         delta=f"{poa_anual - ghi_anual:+.0f} vs GHI")
            col_c.metric("Pendiente / Acimut",
                         f"{empl.pendiente_colector_deg:.0f}° / {acimut_duffie_a_ui360(empl.acimut_colector_deg):.0f}°")
            st.caption(
                "Plano horizontal: datos directos de NASA POWER (GHI, DNI, DHI). "
                "Plano del colector: irradiancia transpuesta con modelo Hay-Davies (pvlib), "
                "usando la pendiente e inclinación configuradas arriba."
            )

        with tab_vhr:
            fig_vhr = _fig_viento_hr(datos_local)
            st.pyplot(fig_vhr, clear_figure=True)
            plt.close(fig_vhr)

        with tab_tabla:
            df_mens = _resumen_mensual(datos_local)
            st.dataframe(df_mens.set_index("Mes"), use_container_width=True)

        # -----------------------------------------------------------------------
        # Sección 5: Descarga CSV
        # -----------------------------------------------------------------------

        st.subheader("Exportar datos")
        csv_bytes = _generar_csv(datos, empl.zona_horaria)
        st.download_button(
            label="Descargar CSV (unidades de usuario)",
            data=csv_bytes,
            file_name=f"nasa_power_{empl.latitud_deg:.4f}_{empl.longitud_deg:.4f}_{clima.anio}.csv",
            mime="text/csv",
            help=(
                "Exporta los datos en unidades de usuario: T [°C], GHI/DNI/DHI [W/m²], "
                "Viento [m/s], HR [%], Presión [hPa]. Índice en hora local."
            ),
        )

    elif proyecto.clima is None and not boton_descarga:
        st.info(
            "Ingresá las coordenadas del emplazamiento y presioná **Descargar datos** "
            "para obtener la serie climática anual de NASA POWER."
        )
