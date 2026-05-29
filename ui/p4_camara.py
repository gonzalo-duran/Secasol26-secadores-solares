"""
Pestaña 4 — Cámara de Secado.

Permite al usuario configurar la geometría, bandejas, flujo y carga de producto
de la cámara de secado solar. Calcula el tiempo de secado estimado y muestra
la curva de humedad X(t) según el modelo de capa fina seleccionado.

Sin cálculo en el motor de cámara: solo configuración, validación estática y
cálculo de tiempo de secado via calculos/camara_calc.py.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from calculos.balance_global import (
    armar_forzantes_aire,
    construir_serie_sintetica_dia_tipo,
)
from calculos.camara_calc import ResultadosCamara, calcular_camara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.motor_calc import _D_P_DEFAULT_M, _K_rugosidad_default
from calculos.psicrometria import humedad_absoluta
from core import catalogo
from core.advertencias import Severidad
from calculos.operacion_anual_camara import (
    ResultadosAnualCamara,
    calcular_operacion_anual_camara,
)
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    DireccionFlujo,
    ForzantesAire,
    GeometriaCamara,
    OperacionAnualConfig,
    ParedCamara,
    _modelos_disponibles,
    advertencias_camara,
)
from core.proyecto import ModoAnalisis
from ui.componentes.esquemas import mostrar_esquema
from ui.componentes.graficas import grafica_termodinamica_camara
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_T_OP_MIN_C: float = 30.0
_T_OP_MAX_C: float = 90.0
_T_OP_DEFAULT_C: float = 55.0

_HR_DEFAULT_PCT: float = 20.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _productos_disponibles() -> dict[str, str]:
    """Retorna {prod_id: label} solo para productos con al menos un modelo calibrado."""
    result: dict[str, str] = {}
    for prod_id, datos in catalogo.PRODUCTOS.items():
        if _modelos_disponibles(datos):
            desc = datos.get("descripcion", prod_id)
            label = f"{prod_id} — {desc[:60]}..." if len(desc) > 60 else f"{prod_id} — {desc}"
            result[prod_id] = label
    return result


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia en la UI con el icono correspondiente."""
    for adv in adv_list:
        icono = _ICONOS_SEVERIDAD.get(adv.severidad, "•")
        if adv.severidad == Severidad.CRITICAL:
            st.error(f"{icono} **{adv.codigo}** — {adv.mensaje}")
        elif adv.severidad == Severidad.WARNING:
            st.warning(f"{icono} **{adv.codigo}** — {adv.mensaje}")
        else:
            st.info(f"{icono} **{adv.codigo}** — {adv.mensaje}")


def _T_amb_representativa_K(proyecto) -> tuple[float, str]:
    """Devuelve T_amb representativa para el motor termodinámico, con su origen.

    Si hay clima cargado, usa la media anual; si no, fallback 25 °C.
    """
    clima = getattr(proyecto, "clima", None)
    if clima is not None and getattr(clima, "T_amb_K", None) is not None:
        T_arr = np.asarray(clima.T_amb_K)
        if T_arr.size > 0:
            T = float(np.nanmean(T_arr))
            return T, f"media anual NASA POWER = {T - 273.15:.1f} °C"
    return 298.15, "fallback 25 °C (sin clima cargado)"


def _grafica_curva_secado(resultados, X_0: float, X_obj: float, prod_id: str) -> go.Figure:
    """Genera la figura de la curva de secado X(t)."""
    t_h = resultados.t_array_s / 3600.0

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(resultados.X_array_kg_kg),
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name="X(t)",
        )
    )
    fig.add_hline(
        y=resultados.X_eq_kg_kg,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=f"X_eq={resultados.X_eq_kg_kg:.3f}",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=X_obj, line=dict(color="red", dash="dot", width=1.5), annotation_text=f"X_obj={X_obj:.3f}"
    )
    fig.add_hline(
        y=X_0,
        line=dict(color="green", dash="dot", width=1),
        annotation_text=f"X₀={X_0:.3f}",
        annotation_position="top right",
    )

    if resultados.convergencia_ok:
        t_sec_h = resultados.t_secado_s / 3600.0
        fig.add_vline(
            x=t_sec_h,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=f"t={t_sec_h:.1f}h",
        )

    fig.update_xaxes(title_text="Tiempo [h]")
    fig.update_yaxes(title_text="Humedad X [kg agua / kg ms]", rangemode="tozero")
    fig.update_layout(
        title_text=f"Curva de secado — {prod_id} · modelo {resultados.modelo_usado}",
        height=400,
        showlegend=True,
    )
    return fig


# ---------------------------------------------------------------------------
# Helpers del motor termodinámico (forzantes + gráficas)
# ---------------------------------------------------------------------------


def _construir_forzantes_termodinamico(
    *,
    tipo_forzantes: str,
    T_op_K: float,
    HR_op: float,
    caudal_kg_s: float,
    T_amb_K: float,
    n_dias: int,
    proyecto=None,
    p3_eval=None,
    I_g_max_W_m2: float = 0.0,
    P_Pa: float = 101325.0,
) -> ForzantesAire | None:
    """Arma ForzantesAire para el motor termodinámico según el tipo elegido.

    - "constantes" → None: el wire-up construye degeneradas y el motor se
      comporta como en condiciones fijas (compatible con tests antiguos).
    - "sintetico"  → curva senoidal día/noche con pico al mediodía. Amplitudes:
      T_sal_col ±15 K respecto al T_op, T_amb ±5 K respecto a T_amb_K.
      I_g(t) semicampana con pico I_g_max_W_m2 (0 si techo opaco).
    - "real"       → serie horaria del colector calculada en P3 + clima NASA
      de P2. Requiere `p3_eval` (dict producido por P3 en modo 'diario') y
      `proyecto` con `clima.datos` no nulo. GHI viene del clima.
    """
    if tipo_forzantes == "constantes":
        return None
    if tipo_forzantes == "sintetico":
        omega_amb = humedad_absoluta(HR_op, T_op_K, P_Pa)
        return construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=T_op_K,
            T_sal_col_amplitud_K=15.0,
            omega_amb=omega_amb,
            m_dot_aire_seco_kg_s=caudal_kg_s,
            T_amb_promedio_K=T_amb_K,
            T_amb_amplitud_K=5.0,
            v_viento_ms=2.0,
            I_g_max_W_m2=I_g_max_W_m2,
            n_dias=n_dias,
        )
    if tipo_forzantes == "real":
        from core.proyecto import Tipologia

        tipologia = getattr(
            getattr(proyecto, "configuracion", None), "tipologia", None
        )
        if tipologia == Tipologia.CAJA:
            return _construir_forzantes_reales_caja(
                proyecto=proyecto,
                caudal_kg_s=caudal_kg_s,
                n_dias=n_dias,
                P_Pa=P_Pa,
            )
        return _construir_forzantes_reales(
            p3_eval=p3_eval,
            proyecto=proyecto,
            caudal_kg_s=caudal_kg_s,
            n_dias=n_dias,
            P_Pa=P_Pa,
        )
    raise ValueError(f"tipo_forzantes desconocido: {tipo_forzantes!r}")


def _construir_forzantes_reales(
    *,
    p3_eval,
    proyecto,
    caudal_kg_s: float,
    n_dias: int,
    P_Pa: float = 101325.0,
) -> ForzantesAire:
    """Construye ForzantesAire desde el día de análisis real (P2 + P3).

    Args:
        p3_eval: Dict producido por P3 en modo 'diario'
            ({"modo": "diario", "r": {...}, "label": ...}). Su sub-dict `r`
            debe contener `horas` (timestamps) y `T_salida_C` (lista
            del mismo largo, con None en horas sin radiación).
        proyecto: Proyecto con `emplazamiento` y `clima.datos` no nulo.

    Si las series del colector tienen huecos (None por noche), se rellenan
    con T_amb local del clima.

    Raises:
        RuntimeError: Si `p3_eval` no es válido o si el clima no está cargado.
    """
    if not p3_eval or p3_eval.get("modo") != "diario":
        raise RuntimeError(
            "Para usar forzantes reales necesitas calcular el colector en modo "
            "diario en P3 (botón 'Calcular desempeño del colector')."
        )
    if proyecto is None or proyecto.clima is None or proyecto.clima.datos is None:
        raise RuntimeError(
            "Para usar forzantes reales necesitas tener el clima cargado en P2 "
            "(descarga NASA POWER)."
        )

    r = p3_eval["r"]
    # Series del colector (24 puntos, horarios; pueden tener None de noche)
    T_sal_C_list = r["T_salida_C"]
    horas = r["horas"]
    n_horas = len(horas)
    if n_horas == 0:
        raise RuntimeError("p3_eval sin datos horarios; recalcular P3.")

    # Clima local: extraer T_amb, HR, v_viento para los mismos timestamps de P3
    empl = proyecto.emplazamiento
    datos_local = proyecto.clima.datos.tz_convert(empl.zona_horaria)
    datos_local = datos_local[datos_local.index.year == proyecto.clima.anio]
    # Reindexar al rango de p3_eval
    primer_ts = horas[0]
    fin_ts = horas[-1]
    datos_dia = datos_local.loc[primer_ts:fin_ts]

    T_amb_K_arr = np.asarray(datos_dia["T_amb_K"], dtype=float)
    HR_arr = np.asarray(datos_dia["HR"], dtype=float)
    v_viento_arr = np.asarray(datos_dia["WS_ms"], dtype=float)
    # Irradiancia global horizontal sobre el techo (NASA POWER → ALLSKY_SFC_SW_DWN).
    # En cámaras opacas el motor anula el término Q_rad sin coste; pasarla siempre
    # simplifica el wire-up.
    I_g_arr = np.asarray(datos_dia["GHI_Wm2"], dtype=float)
    # POA horaria sobre el plano del colector (transposición de DNI/GHI/DHI
    # con tilt/azimut). El balance global la usa al re-correr el colector
    # con el caudal natural impuesto por el lazo de chimenea (Picard).
    try:
        from calculos.clima_calc import calcular_POA_horizonte

        I_g_POA_arr = np.asarray(
            calcular_POA_horizonte(datos_dia, empl),
            dtype=float,
        )
    except Exception:
        # Si POA falla (p.ej. DNI/DHI faltantes), no la propagamos; el
        # balance global caerá al fallback con aviso.
        I_g_POA_arr = None

    if len(T_amb_K_arr) != n_horas:
        raise RuntimeError(
            f"Desfase entre series P3 ({n_horas} h) y clima ({len(T_amb_K_arr)} h). "
            "Recalcular P3 con el clima actual."
        )

    # T_sal_col: rellenar None (horas sin radiación) con T_amb local
    T_sal_col_K = np.empty(n_horas, dtype=float)
    for i, t_sal_c in enumerate(T_sal_C_list):
        if t_sal_c is None:
            T_sal_col_K[i] = T_amb_K_arr[i]
        else:
            T_sal_col_K[i] = float(t_sal_c) + 273.15

    # ω_amb desde HR y T_amb (gas ideal)
    omega_amb_arr = np.array(
        [humedad_absoluta(float(hr), float(T), P_Pa) for hr, T in zip(HR_arr, T_amb_K_arr)],
        dtype=float,
    )

    modo = "multi_dia" if n_dias > 1 else "diario"
    return armar_forzantes_aire(
        modo=modo,
        n_dias=n_dias,
        T_salida_colector_K=T_sal_col_K,
        omega_ambiente=omega_amb_arr,
        m_dot_aire_seco_kg_s=caudal_kg_s,
        v_viento_ms=v_viento_arr,
        T_amb_K=T_amb_K_arr,
        I_g_W_m2=I_g_arr,
        I_g_POA_W_m2=I_g_POA_arr,
        dt_s=3600.0,
    )


def _construir_forzantes_reales_caja(
    *,
    proyecto,
    caudal_kg_s: float,
    n_dias: int,
    P_Pa: float = 101325.0,
) -> ForzantesAire:
    """Construye ForzantesAire para tipología CAJA desde un día real del clima.

    En CAJA la cámara actúa como colector: no hay colector externo y el aire
    entrante es directamente ambiente, por lo que T_salida_colector(t) = T_amb(t).
    El resto de la serie horaria (T_amb, HR→ω, viento, GHI, POA) sale del
    clima NASA POWER de P2 seleccionando 24 h según ``cfg.dia_analisis``.

    Raises:
        RuntimeError: Si el clima no está cargado o no hay datos para el día
            resuelto.
    """
    from datetime import date as _date

    from core.proyecto import DiaAnalisis

    if proyecto is None or proyecto.clima is None or proyecto.clima.datos is None:
        raise RuntimeError(
            "Para usar forzantes reales en CAJA necesitas tener el clima cargado "
            "en P2 (descarga NASA POWER)."
        )

    empl = proyecto.emplazamiento
    cfg = proyecto.configuracion
    anio = proyecto.clima.anio
    datos_local = proyecto.clima.datos.tz_convert(empl.zona_horaria)
    datos_local = datos_local[datos_local.index.year == anio]

    if cfg.dia_analisis == DiaAnalisis.ESPECIFICO and cfg.fecha_especifica:
        fecha_dia = cfg.fecha_especifica
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_VERANO:
        fecha_dia = _date(anio, 12, 21)
    elif cfg.dia_analisis == DiaAnalisis.SOLSTICIO_INVIERNO:
        fecha_dia = _date(anio, 6, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_MARZO:
        fecha_dia = _date(anio, 3, 21)
    elif cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_SEPTIEMBRE:
        fecha_dia = _date(anio, 9, 21)
    elif cfg.dia_analisis == DiaAnalisis.MAS_CALUROSO:
        fecha_dia = (
            (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmax().date()
        )
    else:  # MAS_FRIO
        fecha_dia = (
            (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmin().date()
        )

    mask_dia = datos_local.index.date == fecha_dia
    datos_dia = datos_local[mask_dia]
    if len(datos_dia) == 0:
        raise RuntimeError(
            f"Sin datos climáticos para {fecha_dia} en el año {anio}. "
            "Revisá la cobertura del clima en P2."
        )

    T_amb_K_arr = np.asarray(datos_dia["T_amb_K"], dtype=float)
    HR_arr = np.asarray(datos_dia["HR"], dtype=float)
    v_viento_arr = np.asarray(datos_dia["WS_ms"], dtype=float)
    I_g_arr = np.asarray(datos_dia["GHI_Wm2"], dtype=float)
    try:
        from calculos.clima_calc import calcular_POA_horizonte

        I_g_POA_arr = np.asarray(
            calcular_POA_horizonte(datos_dia, empl),
            dtype=float,
        )
    except Exception:
        I_g_POA_arr = None

    # CAJA: sin colector externo → T_sal_col(t) = T_amb(t).
    T_sal_col_K = T_amb_K_arr.copy()

    omega_amb_arr = np.array(
        [humedad_absoluta(float(hr), float(T), P_Pa) for hr, T in zip(HR_arr, T_amb_K_arr)],
        dtype=float,
    )

    modo = "multi_dia" if n_dias > 1 else "diario"
    return armar_forzantes_aire(
        modo=modo,
        n_dias=n_dias,
        T_salida_colector_K=T_sal_col_K,
        omega_ambiente=omega_amb_arr,
        m_dot_aire_seco_kg_s=caudal_kg_s,
        v_viento_ms=v_viento_arr,
        T_amb_K=T_amb_K_arr,
        I_g_W_m2=I_g_arr,
        I_g_POA_W_m2=I_g_POA_arr,
        dt_s=3600.0,
    )


def _disponibilidad_forzantes_reales(p3_eval, proyecto) -> tuple[bool, str]:
    """Verifica si hay datos suficientes para construir forzantes reales.

    Reglas según tipología:
        - CAJA: el aire entrante es ambiente (sin colector externo), así que
          solo se exige clima NASA POWER cargado en P2.
        - ARMARIO / GRAN_ESCALA: se exige además que P3 esté calculado en
          modo diario, porque T_sal_col(t) proviene del solver del colector.
    """
    from core.proyecto import Tipologia

    tipologia = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
    es_caja = tipologia == Tipologia.CAJA

    if proyecto is None or proyecto.clima is None or proyecto.clima.datos is None:
        return False, "P2 sin clima descargado (datos NASA POWER no disponibles)."

    if es_caja:
        # En CAJA no hay colector; basta con clima.
        return True, "OK"

    if not p3_eval or p3_eval.get("modo") != "diario":
        return False, "P3 sin calcular (ejecutá 'Calcular desempeño del colector' en modo diario)."
    return True, "OK"


def _grafica_secado_termodinamico(
    res: ResultadoMotorTermodinamico,
    X_obj: float,
    prod_id: str,
) -> go.Figure:
    """Figura multi-panel de las trayectorias del motor termodinámico.

    Paneles:
        1. X(t) con línea X_obj y marcador de t_secado.
        2. T_prod, T_flujo, T_cam_int, T_cam_ext en °C.
        3. HR_flujo y banda al 95 %.
        4. Tasa de evaporación ṁ_w [g/h] (segundo eje opcional).
    """
    t_h = res.t_array_s / 3600.0

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "Humedad del producto X(t)",
            "Temperaturas: producto, aire y paredes",
            "HR del aire en cámara",
            "Tasa de evaporación",
        ),
    )

    # Panel 1: X(t)
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.X_prod_kg_kg),
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name="X(t)",
        ),
        row=1,
        col=1,
    )
    fig.add_hline(
        y=X_obj,
        line=dict(color="red", dash="dot", width=1.5),
        annotation_text=f"X_obj={X_obj:.3f}",
        row=1,
        col=1,
    )
    if res.status == "X_obj_alcanzado" and res.t_secado_s is not None:
        t_sec_h = res.t_secado_s / 3600.0
        fig.add_vline(
            x=t_sec_h,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=f"t={t_sec_h:.1f}h",
            row=1,
            col=1,
        )

    # Panel 2: Temperaturas
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.T_prod_K - 273.15),
            mode="lines",
            line=dict(color="#d62728", width=2),
            name="T_producto",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.T_flujo_K - 273.15),
            mode="lines",
            line=dict(color="#ff7f0e", width=1.5, dash="dash"),
            name="T_aire (flujo)",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.T_cam_int_K - 273.15),
            mode="lines",
            line=dict(color="#2ca02c", width=1, dash="dot"),
            name="T_pared interna",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.T_cam_ext_K - 273.15),
            mode="lines",
            line=dict(color="#8c564b", width=1, dash="dot"),
            name="T_pared externa",
        ),
        row=2,
        col=1,
    )

    # Panel 3: HR_flujo
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.HR_flujo * 100.0),
            mode="lines",
            line=dict(color="#9467bd", width=1.5),
            name="HR_flujo [%]",
        ),
        row=3,
        col=1,
    )
    fig.add_hline(
        y=95.0, line=dict(color="red", dash="dot", width=1.0), annotation_text="95%", row=3, col=1
    )

    # Panel 4: ṁ_w (g/h)
    m_dot_g_h = res.m_dot_w_kg_s * 1000.0 * 3600.0
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(m_dot_g_h),
            mode="lines",
            line=dict(color="#17becf", width=1.5),
            name="ṁ_w [g/h]",
        ),
        row=4,
        col=1,
    )
    fig.add_hline(y=0.0, line=dict(color="gray", dash="solid", width=0.8), row=4, col=1)

    fig.update_yaxes(title_text="X [kg/kg ms]", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="T [°C]", row=2, col=1)
    fig.update_yaxes(title_text="HR [%]", range=[0, 105], row=3, col=1)
    fig.update_yaxes(title_text="ṁ_w [g/h]", row=4, col=1)
    fig.update_xaxes(title_text="Tiempo [h]", row=4, col=1)
    fig.update_layout(
        title_text=f"Motor termodinámico — {prod_id}",
        height=900,
        showlegend=True,
    )
    return fig


# ---------------------------------------------------------------------------
# Generador de texto de configuración
# ---------------------------------------------------------------------------


def _resumen_resultado_termodinamico(res) -> dict:
    """Extrae métricas escalares del resultado del motor termodinámico."""
    import numpy as np

    n = len(res.t_array_s) if hasattr(res, "t_array_s") else 0
    out = {
        "status": res.status,
        "t_secado_s": res.t_secado_s,
        "t_secado_h": res.t_secado_s / 3600.0 if res.t_secado_s else None,
        "masa_evaporada_total_kg": float(res.masa_evaporada_total_kg),
        "T_max_alcanzada_K": float(res.T_max_alcanzada_K),
        "T_max_alcanzada_C": float(res.T_max_alcanzada_K) - 273.15,
        "energia_rad_total_MJ": float(res.energia_rad_total_J) / 1e6,
        "horas_clipeo_nocturno_h": float(res.horas_clipeo_nocturno_s) / 3600.0,
        "horas_HR_alta_h": float(res.horas_HR_alta_s) / 3600.0,
        "advertencias": list(res.advertencias),
        "n_puntos_simulacion": n,
    }
    if n > 0:
        out["X_prod_final"] = float(res.X_prod_kg_kg[-1])
        out["X_prod_inicial"] = float(res.X_prod_kg_kg[0])
        out["T_prod_final_K"] = float(res.T_prod_K[-1])
        out["T_prod_final_C"] = out["T_prod_final_K"] - 273.15
        out["T_flujo_max_C"] = float(np.max(res.T_flujo_K)) - 273.15
        out["HR_max"] = float(np.max(res.HR_flujo))
        out["t_simulacion_h"] = float(res.t_array_s[-1]) / 3600.0
    return out


def _resumen_resultado_capa_fina(res) -> dict:
    """Extrae métricas del resultado de capa fina estático."""
    return {
        "X_eq_kg_kg": float(res.X_eq_kg_kg),
        "fuente_X_eq": res.fuente_X_eq,
        "modelo_usado": res.modelo_usado,
        "t_secado_s": float(res.t_secado_s),
        "t_secado_h": float(res.t_secado_s) / 3600.0,
        "MR_obj": float(res.MR_obj),
        "masa_agua_extraida_kg": float(res.masa_agua_extraida_kg),
        "convergencia_ok": bool(res.convergencia_ok),
        "mensaje_convergencia": res.mensaje_convergencia,
        "advertencias": list(res.advertencias),
        "omega_entrada_kg_kg": res.omega_entrada_kg_kg,
        "omega_salida_kg_kg": res.omega_salida_kg_kg,
        "HR_salida": res.HR_salida,
        "HR_media": res.HR_media,
        "X_eq_corregido_kg_kg": res.X_eq_corregido_kg_kg,
        "t_secado_corregido_s": res.t_secado_corregido_s,
        "t_secado_corregido_h": (
            res.t_secado_corregido_s / 3600.0 if res.t_secado_corregido_s is not None else None
        ),
    }


def _obtener_resultado_camara(session_state) -> tuple[str | None, object | None, dict | None]:
    """Devuelve (tipo, resultado, meta) extraído de session_state.

    tipo ∈ {"termodinamico_horizonte", "capa_fina", None}.
    """
    horizonte = session_state.get("p4_horizonte_resultado")
    if horizonte is not None:
        return "termodinamico_horizonte", horizonte, session_state.get("p4_horizonte_meta")
    estatico = session_state.get("p4_resultado_dinamico")
    if estatico is not None:
        return "capa_fina", estatico, None
    return None, None, None


def _texto_config_camara(cam: "Camara", session_state=None) -> str:
    """Genera el snapshot .txt de la cámara con resultados si están en session."""
    from datetime import date

    g = cam.geometria
    cn = cam.construccion
    b = cam.bandejas
    f = cam.flujo
    c = cam.carga_producto
    from core import catalogo as _cat

    datos_prod = _cat.PRODUCTOS.get(c.producto_id) or {}
    props_prod = datos_prod.get("propiedades_basicas") or {}

    sep = "=" * 60
    lines = [
        sep,
        "        CONFIGURACIÓN DE LA CÁMARA DE SECADO",
        sep,
        f"Fecha de exportación: {date.today()}",
        f"Motor numérico       : {cam.modo_calculo}",
        "",
        "GEOMETRÍA",
        f"  Largo : {g.largo_m:.3f} m",
        f"  Ancho : {g.ancho_m:.3f} m",
        f"  Alto  : {g.alto_m:.3f} m",
        f"  Volumen interno   : {g.largo_m * g.ancho_m * g.alto_m:.3f} m³",
        "",
        "CONSTRUCCIÓN",
        f"  Techo translúcido : " + (cn.cubierta_translucida_id or "(opaca)"),
    ]
    if cn.cubierta_translucida_id is not None and cn.A_rad_m2 is not None:
        lines.append(f"  A_rad             : {cn.A_rad_m2:.4f} m²")
    lines.append(
        f"  Pared             : {'compuesta' if cn.pared.es_compuesta else 'simple'} "
        f"({len(cn.pared.capas)} capa(s))"
    )
    for i, capa in enumerate(cn.pared.capas, start=1):
        lines.append(
            f"    Capa {i}: id={capa.material_id} ({capa.catalogo})  "
            f"e={capa.espesor_m * 1000:.2f} mm  "
            f"k={capa.conductividad_termica_W_mK:.3f} W/(m·K)  "
            f"R={capa.R_conduccion_m2K_W:.4f} m²·K/W"
        )
    lines += [
        f"  Espesor pared     : {cn.pared.espesor_total_m * 1000:.1f} mm",
        f"  R_total pared     : {cn.pared.R_conduccion_m2K_W:.4f} m²·K/W",
        f"  U_pared (cond.)   : {cn.U_muros_W_m2K:.3f} W/(m²·K)",
        "",
        "BANDEJAS",
        f"  N° bandejas         : {b.n_bandejas}",
        f"  Área c/u            : {b.area_bandeja_m2:.4f} m²",
        f"  Área total bandejas : {b.n_bandejas * b.area_bandeja_m2:.3f} m²",
        f"  Espesor capa        : {b.espesor_capa_m * 100:.2f} cm",
        f"  Separación          : {b.separacion_entre_bandejas_m * 100:.2f} cm",
        f"  Tipo malla          : {b.tipo_malla or '(no especificada)'}",
        f"  Porosidad lecho     : {b.porosidad_lecho:.3f}",
        f"  Esfericidad         : {b.esfericidad:.3f}",
    ]
    if b.diametro_eq_particula_m is not None:
        lines.append(f"  d_eq partícula      : {b.diametro_eq_particula_m * 1000:.2f} mm")
    if b.K_rugosidad_producto is not None:
        lines.append(f"  K rugosidad (forzado): {b.K_rugosidad_producto:.2f}")
    lines += [
        "",
        "PRODUCTO Y CARGA",
        f"  Producto           : {c.producto_id}",
        f"  Categoría          : {datos_prod.get('categoria', '—')}",
        f"  Masa total         : {c.masa_total_kg:.2f} kg",
        f"  X inicial          : {c.humedad_inicial_X:.4f} kg/kg ms",
        f"  X objetivo         : {c.humedad_objetivo_X:.4f} kg/kg ms",
        f"  Modelo capa fina   : {c.modelo_capa_fina}",
        f"  Modelo isoterma    : {c.modelo_isoterma}",
        "  T_prod inicial     : "
        + (
            f"{c.T_prod_inicial_K - 273.15:.1f} °C (explícita)"
            if c.T_prod_inicial_K is not None
            else "T_amb (fallback)"
        ),
    ]
    if props_prod:
        lines += ["", "  Propiedades básicas del producto (catálogo):"]
        for k, v in props_prod.items():
            lines.append(f"    {k}: {v}")
    lines += [
        "",
        "FLUJO",
        f"  Caudal másico      : {f.caudal_masico_kg_s:.5f} kg/s",
        f"  Dirección          : {f.direccion_flujo.value}",
        f"  Recirculación      : {f.fraccion_recirculacion:.0%}",
        "  HR entrada         : "
        + (
            f"{f.HR_entrada_fraccion:.3f}"
            if f.HR_entrada_fraccion is not None
            else "(no especificada, fallback)"
        ),
    ]

    # Advertencias
    from core.camara import advertencias_camara as _advs_cam

    advs = _advs_cam(cam)
    lines += ["", "ADVERTENCIAS ESTÁTICAS DE DISEÑO"]
    if not advs:
        lines.append("  (ninguna)")
    else:
        for a in advs:
            lines.append(f"  [{a.severidad.value}] {a.codigo}: {a.mensaje}")

    # Resultados
    lines += ["", sep, "  RESULTADOS DE SIMULACIÓN", sep]
    tipo_res, res, meta = _obtener_resultado_camara(
        session_state if session_state is not None else {}
    )
    if res is None:
        lines.append("  ⚠ Cálculo no ejecutado. Volver a P4 y presionar")
        lines.append("    'Calcular cámara' para incluirlos.")
    elif tipo_res == "termodinamico_horizonte":
        resumen = _resumen_resultado_termodinamico(res)
        lines.append("  Modo               : termodinámico (horizonte)")
        if meta:
            lines.append(
                f"  Horizonte          : {meta.get('n_dias')} día(s), "
                f"forzantes={meta.get('modo_forzantes')}"
            )
        lines += [
            f"  Status             : {resumen['status']}",
            f"  Tiempo simulación  : {resumen.get('t_simulacion_h', 0):.2f} h",
            f"  Tiempo de secado   : "
            + (f"{resumen['t_secado_h']:.2f} h" if resumen["t_secado_h"] else "no alcanzado"),
            f"  Agua evaporada     : {resumen['masa_evaporada_total_kg']:.3f} kg",
            f"  X inicial          : {resumen.get('X_prod_inicial', 0):.4f} kg/kg",
            f"  X final            : {resumen.get('X_prod_final', 0):.4f} kg/kg",
            f"  T producto final   : {resumen.get('T_prod_final_C', 0):.1f} °C",
            f"  T producto máx     : {resumen['T_max_alcanzada_C']:.1f} °C",
            f"  T flujo máx        : {resumen.get('T_flujo_max_C', 0):.1f} °C",
            f"  HR máx en cámara   : {resumen.get('HR_max', 0):.3f}",
            f"  E radiativa total  : {resumen['energia_rad_total_MJ']:.4f} MJ",
            f"  Horas clipeo noct. : {resumen['horas_clipeo_nocturno_h']:.2f} h",
            f"  Horas HR > 0.95    : {resumen['horas_HR_alta_h']:.2f} h",
        ]
        if resumen["advertencias"]:
            lines.append("  Advertencias cálculo:")
            for adv in resumen["advertencias"]:
                lines.append(f"    - {adv}")
    elif tipo_res == "capa_fina":
        resumen = _resumen_resultado_capa_fina(res)
        lines += [
            "  Modo               : capa fina (estático)",
            f"  Modelo aplicado    : {resumen['modelo_usado']}",
            f"  X_eq               : {resumen['X_eq_kg_kg']:.4f} kg/kg ms",
            f"  Fuente X_eq        : {resumen['fuente_X_eq']}",
            f"  Tiempo de secado   : {resumen['t_secado_h']:.2f} h",
            f"  Agua extraída      : {resumen['masa_agua_extraida_kg']:.3f} kg",
            f"  MR objetivo        : {resumen['MR_obj']:.4f}",
            f"  Convergencia       : "
            + (
                "OK" if resumen["convergencia_ok"] else f"FALLA — {resumen['mensaje_convergencia']}"
            ),
        ]
        if resumen["HR_media"] is not None:
            lines += [
                f"  HR media (psicro)  : {resumen['HR_media']:.3f}",
                f"  X_eq corregido     : "
                + (
                    f"{resumen['X_eq_corregido_kg_kg']:.4f} kg/kg"
                    if resumen["X_eq_corregido_kg_kg"] is not None
                    else "—"
                ),
                f"  t_secado corregido : "
                + (
                    f"{resumen['t_secado_corregido_h']:.2f} h"
                    if resumen["t_secado_corregido_h"] is not None
                    else "—"
                ),
            ]
        if resumen["advertencias"]:
            lines.append("  Advertencias cálculo:")
            for adv in resumen["advertencias"]:
                lines.append(f"    - {adv}")
    lines.append("")
    return "\n".join(lines)


def _from_json_camara(data: dict) -> "Camara":
    """Reconstruye una ``Camara`` desde un dict producido por
    ``_json_config_camara``.

    Raises:
        KeyError/ValueError/TypeError: si el JSON está corrupto o un id de
            material/producto no existe en el catálogo actual.
    """
    g_d = data.get("geometria") or {}
    cn_d = data.get("construccion") or {}
    b_d = data.get("bandejas") or {}
    c_d = data.get("carga_producto") or {}
    f_d = data.get("flujo") or {}

    geometria = GeometriaCamara(
        largo_m=float(g_d["largo_m"]),
        ancho_m=float(g_d["ancho_m"]),
        alto_m=float(g_d["alto_m"]),
    )

    pared_d = cn_d.get("pared") or {}
    capas_d = pared_d.get("capas") or []
    capas = [
        CapaPared(
            material_id=c["material_id"],
            espesor_m=float(c["espesor_m"]),
            catalogo=c["catalogo"],
        )
        for c in capas_d
    ]
    pared = ParedCamara(capas=capas)
    construccion = ConstruccionCamara(
        cubierta_translucida_id=cn_d.get("cubierta_translucida_id"),
        A_rad_m2=(float(cn_d["A_rad_m2"]) if cn_d.get("A_rad_m2") is not None else None),
        pared=pared,
    )

    bandejas = ConfiguracionBandejas(
        n_bandejas=int(b_d["n_bandejas"]),
        area_bandeja_m2=float(b_d["area_bandeja_m2"]),
        espesor_capa_m=float(b_d["espesor_capa_m"]),
        separacion_entre_bandejas_m=float(b_d["separacion_entre_bandejas_m"]),
        tipo_malla=b_d.get("tipo_malla"),
        porosidad_lecho=float(b_d.get("porosidad_lecho", 0.45)),
        diametro_eq_particula_m=(
            float(b_d["diametro_eq_particula_m"])
            if b_d.get("diametro_eq_particula_m") is not None
            else None
        ),
        esfericidad=float(b_d.get("esfericidad", 0.60)),
        K_rugosidad_producto=(
            float(b_d["K_rugosidad_producto"])
            if b_d.get("K_rugosidad_producto") is not None
            else None
        ),
    )

    carga = CargaProducto(
        producto_id=c_d["producto_id"],
        masa_total_kg=float(c_d["masa_total_kg"]),
        humedad_inicial_X=float(c_d["humedad_inicial_X"]),
        humedad_objetivo_X=float(c_d["humedad_objetivo_X"]),
        modelo_capa_fina=c_d["modelo_capa_fina"],
        modelo_isoterma=c_d["modelo_isoterma"],
        T_prod_inicial_K=(
            float(c_d["T_prod_inicial_K"]) if c_d.get("T_prod_inicial_K") is not None else None
        ),
    )

    flujo = ConfiguracionFlujo(
        caudal_masico_kg_s=float(f_d["caudal_masico_kg_s"]),
        fraccion_recirculacion=float(f_d.get("fraccion_recirculacion", 0.0)),
        direccion_flujo=DireccionFlujo(f_d.get("direccion_flujo", "HORIZONTAL")),
        HR_entrada_fraccion=(
            float(f_d["HR_entrada_fraccion"])
            if f_d.get("HR_entrada_fraccion") is not None
            else None
        ),
    )

    return Camara(
        geometria=geometria,
        construccion=construccion,
        bandejas=bandejas,
        flujo=flujo,
        carga_producto=carga,
        modo_calculo=data.get("modo_calculo", "termodinamico"),
    )


def _json_config_camara(cam: "Camara", session_state=None) -> dict:
    """Snapshot reconstruible (dict) de la cámara con resultados."""
    from datetime import date
    from core import catalogo as _cat
    from core.camara import advertencias_camara as _advs_cam

    g = cam.geometria
    cn = cam.construccion
    b = cam.bandejas
    f = cam.flujo
    c = cam.carga_producto
    datos_prod = _cat.PRODUCTOS.get(c.producto_id) or {}

    snapshot: dict = {
        "fecha_exportacion": date.today().isoformat(),
        "seccion": "camara",
        "modo_calculo": cam.modo_calculo,
        "geometria": {
            "largo_m": g.largo_m,
            "ancho_m": g.ancho_m,
            "alto_m": g.alto_m,
            "volumen_m3": g.largo_m * g.ancho_m * g.alto_m,
        },
        "construccion": {
            "cubierta_translucida_id": cn.cubierta_translucida_id,
            "cubierta_translucida_props": (
                dict(_cat.CUBIERTAS.get(cn.cubierta_translucida_id, {}))
                if cn.cubierta_translucida_id
                else None
            ),
            "A_rad_m2": cn.A_rad_m2,
            "pared": {
                "es_compuesta": cn.pared.es_compuesta,
                "espesor_total_m": cn.pared.espesor_total_m,
                "R_total_m2K_W": cn.pared.R_conduccion_m2K_W,
                "U_pared_W_m2K": cn.U_muros_W_m2K,
                "capas": [
                    {
                        "material_id": capa.material_id,
                        "catalogo": capa.catalogo,
                        "espesor_m": capa.espesor_m,
                        "conductividad_W_mK": capa.conductividad_termica_W_mK,
                        "R_m2K_W": capa.R_conduccion_m2K_W,
                    }
                    for capa in cn.pared.capas
                ],
            },
        },
        "bandejas": {
            "n_bandejas": b.n_bandejas,
            "area_bandeja_m2": b.area_bandeja_m2,
            "area_total_bandejas_m2": b.n_bandejas * b.area_bandeja_m2,
            "espesor_capa_m": b.espesor_capa_m,
            "separacion_entre_bandejas_m": b.separacion_entre_bandejas_m,
            "tipo_malla": b.tipo_malla,
            "porosidad_lecho": b.porosidad_lecho,
            "diametro_eq_particula_m": b.diametro_eq_particula_m,
            "esfericidad": b.esfericidad,
            "K_rugosidad_producto": b.K_rugosidad_producto,
        },
        "carga_producto": {
            "producto_id": c.producto_id,
            "categoria": datos_prod.get("categoria"),
            "masa_total_kg": c.masa_total_kg,
            "humedad_inicial_X": c.humedad_inicial_X,
            "humedad_objetivo_X": c.humedad_objetivo_X,
            "modelo_capa_fina": c.modelo_capa_fina,
            "modelo_isoterma": c.modelo_isoterma,
            "T_prod_inicial_K": c.T_prod_inicial_K,
            "propiedades_basicas_catalogo": datos_prod.get("propiedades_basicas") or {},
        },
        "flujo": {
            "caudal_masico_kg_s": f.caudal_masico_kg_s,
            "direccion_flujo": f.direccion_flujo.value,
            "fraccion_recirculacion": f.fraccion_recirculacion,
            "HR_entrada_fraccion": f.HR_entrada_fraccion,
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
            for a in _advs_cam(cam)
        ],
    }

    tipo_res, res, meta = _obtener_resultado_camara(
        session_state if session_state is not None else {}
    )
    if res is None:
        snapshot["resultados"] = {
            "ejecutado": False,
            "nota": "Cálculo no ejecutado en esta sesión.",
        }
    elif tipo_res == "termodinamico_horizonte":
        snapshot["resultados"] = {
            "ejecutado": True,
            "tipo": "termodinamico_horizonte",
            "meta_horizonte": meta,
            "resumen": _resumen_resultado_termodinamico(res),
        }
    elif tipo_res == "capa_fina":
        snapshot["resultados"] = {
            "ejecutado": True,
            "tipo": "capa_fina",
            "resumen": _resumen_resultado_capa_fina(res),
        }
    return snapshot


# ---------------------------------------------------------------------------
# Operación anual de cámara (cascada A + B)
# ---------------------------------------------------------------------------


def _render_operacion_anual(proyecto, camara_builder) -> None:
    """Sección prominente de operación anual de cámara (modo ANUAL).

    Muestra slider de batches_por_mes, botón de cálculo y card resumen anual.
    No requiere que ``proyecto.camara`` esté construido previamente — recibe
    ``camara_builder``, un callable sin argumentos que construye ``Camara``
    desde los valores actuales de los widgets de P4 cuando se aprieta el
    botón anual. Eso permite que el flujo anual sea la vista principal en
    modo ANUAL y no requiera correr antes el batch puntual del día sintético.
    """
    if proyecto.clima is None or proyecto.clima.datos is None:
        st.info("ℹ️ **Operación anual** disponible solo con clima NASA POWER " "cargado en P2.")
        return
    if proyecto.colector is None:
        st.warning(
            "⚠️ La operación anual de cámara requiere un colector configurado "
            "en P3 (modelo lineal de prediseño)."
        )
        return

    st.markdown("### 📅 Operación anual de cámara (cascada A + B)")
    st.caption(
        "Corre el motor termodinámico sobre el día típico de cada mes, calcula "
        "las 4 eficiencias de Augustus Leon (RSER 2002) y escala a operación "
        "mensual con la cantidad de batches configurada. El detalle por mes "
        "se muestra en P7."
    )

    # Estado previo (puede ser None si aún no se calculó la cámara)
    cfg_prev = OperacionAnualConfig()
    if proyecto.camara is not None and proyecto.camara.operacion_anual is not None:
        cfg_prev = proyecto.camara.operacion_anual

    c1, c2 = st.columns([2, 1])
    with c1:
        batches = st.slider(
            "Batches del producto por mes",
            min_value=1,
            max_value=30,
            value=int(cfg_prev.batches_por_mes),
            step=1,
            help=(
                "Cantidad de batches completos del producto que se asume "
                "operar por mes. 10 batches/mes ≈ 1 batch cada 3 días."
            ),
            key="p4_anual_batches",
        )
    with c2:
        st.metric(
            "Días/batch (aprox.)",
            f"{30 / batches:.1f}",
            help="30 días/mes ÷ batches/mes",
        )

    calcular_anual = st.button(
        "📅 Calcular operación anual",
        type="primary",
        key="p4_anual_calcular",
        help=(
            "Construye la cámara con los valores actuales de los widgets, "
            "fija modo_calculo=termodinamico y corre 12 simulaciones (~30 s)."
        ),
    )

    if calcular_anual:
        # Construir la cámara desde los widgets y forzar modo termodinámico
        # (la cascada A+B no usa capa fina).
        try:
            camara = camara_builder(modo_calculo_override="termodinamico")
        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Error de configuración: {exc}")
            return

        try:
            cfg_nuevo = OperacionAnualConfig(batches_por_mes=batches)
        except ValueError as exc:
            st.error(f"❌ {exc}")
            return

        camara.operacion_anual = cfg_nuevo
        proyecto.camara = camara

        with st.spinner("Corriendo motor termodinámico mes a mes..."):
            try:
                res_anual = calcular_operacion_anual_camara(proyecto)
            except ValueError as exc:
                st.error(f"❌ {exc}")
                return
            except Exception as exc:
                st.error(f"❌ Error en cálculo anual: {exc}")
                return
        st.session_state["p4_resultado_anual"] = res_anual
        st.success("✅ Operación anual calculada. Ver detalle mensual en P7.")

    res_anual: ResultadosAnualCamara | None = st.session_state.get("p4_resultado_anual")
    if res_anual is None:
        return

    if res_anual.advertencias:
        for msg in res_anual.advertencias:
            st.warning(f"⚠️ {msg}")

    st.markdown("**Resumen anual**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "kg secados/año",
        f"{res_anual.kg_secados_anual:.0f}",
        help="Suma de kg de producto fresco secados en los 12 meses.",
    )
    col2.metric(
        "η_total media",
        f"{res_anual.eta_total_anual_media * 100:.1f}%",
        help="Eficiencia global del sistema ponderada por kg/mes.",
    )
    col3.metric(
        "t_secado promedio",
        f"{res_anual.t_secado_promedio_h:.1f} h",
        help="Promedio sobre meses que convergieron al X_objetivo.",
    )
    col4.metric(
        "Energía solar anual",
        f"{res_anual.E_solar_anual_MJ:.0f} MJ",
        help="Sobre el plano del colector durante batches operativos.",
    )


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 4 — Cámara de Secado."""
    st.header("4 · Cámara de Secado")

    proyecto = st.session_state.proyecto

    # Detectar tipología temprano: condiciona defaults de cubierta y T_op.
    from core.proyecto import Tipologia

    _tipologia_actual = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
    es_caja_pre = _tipologia_actual == Tipologia.CAJA
    if es_caja_pre:
        st.info(
            "📦 **Tipología CAJA**: la cámara actúa como secador directo. "
            "El techo translúcido es obligatorio (única fuente de energía) "
            "y la temperatura de operación es la del aire ambiente."
        )

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander("📥 Cargar configuración guardada (.json)", expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            "Subí un archivo .json de la cámara previamente guardado",
            type=["json"],
            key="p4_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "camara")
            if err:
                st.error(f"❌ {err}")
            else:
                try:
                    cam_cargada = _from_json_camara(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(f"❌ Error reconstruyendo la cámara: {exc}")
                else:
                    proyecto.camara = cam_cargada
                    # Limpiar widgets + resultados viejos de la cámara
                    # y del horizonte que dependa de ella.
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p4_")
                    limpiar_session_state_prefijo(st.session_state, "cam_")
                    st.session_state.pop("p4_cargar_json", None)
                    st.success(
                        f"✅ Cámara cargada desde JSON "
                        f"(se reiniciaron {n_borr} valores de la sesión)."
                    )
                    st.rerun()

    # -----------------------------------------------------------------------
    # Sección A: Producto
    # -----------------------------------------------------------------------
    st.subheader("Producto a secar")

    productos_disp = _productos_disponibles()
    if not productos_disp:
        st.error(
            "No se encontraron productos con modelos de capa fina calibrados en el catálogo. "
            "Verificar los archivos en catalogo/productos/."
        )
        return

    ids_disponibles = list(productos_disp.keys())
    labels_disponibles = list(productos_disp.values())

    # Valor previo guardado
    prod_previo = "manzana"
    if (
        proyecto.camara is not None
        and proyecto.camara.carga_producto.producto_id in ids_disponibles
    ):
        prod_previo = proyecto.camara.carga_producto.producto_id

    idx_default = ids_disponibles.index(prod_previo) if prod_previo in ids_disponibles else 0
    prod_sel_label = st.selectbox(
        "Producto",
        options=labels_disponibles,
        index=idx_default,
        help="Solo se muestran productos con al menos un modelo de capa fina calibrado.",
    )
    prod_id = ids_disponibles[labels_disponibles.index(prod_sel_label)]
    datos_prod = catalogo.PRODUCTOS[prod_id]
    props = datos_prod.get("propiedades_basicas") or {}

    modelos_disp = _modelos_disponibles(datos_prod)

    col1, col2 = st.columns(2)
    with col1:
        # Humedad inicial: default desde catálogo
        X_ini_default = float(props.get("humedad_inicial_tipica", 4.0))
        if proyecto.camara is not None and proyecto.camara.carga_producto.producto_id == prod_id:
            X_ini_default = proyecto.camara.carga_producto.humedad_inicial_X

        X_ini = st.number_input(
            "Humedad inicial X₀ [kg agua / kg ms]",
            min_value=0.01,
            max_value=50.0,
            value=X_ini_default,
            step=0.1,
            format="%.2f",
            help="Base seca. Típicamente 4–16 kg/kg ms para frutas y hortalizas frescas.",
        )

        X_obj = st.number_input(
            "Humedad objetivo X_obj [kg agua / kg ms]",
            min_value=0.01,
            max_value=X_ini - 0.01,
            value=(
                min(
                    0.15,
                    X_ini - 0.01,
                )
                if proyecto.camara is None
                else min(proyecto.camara.carga_producto.humedad_objetivo_X, X_ini - 0.01)
            ),
            step=0.01,
            format="%.3f",
            help=(
                "Humedad final deseada en base seca. "
                "Valores típicos de almacenamiento: 0.10–0.20 kg/kg ms."
            ),
        )

        masa_kg = st.number_input(
            "Masa total a secar [kg]",
            min_value=0.1,
            max_value=10000.0,
            value=float(
                proyecto.camara.carga_producto.masa_total_kg
                if proyecto.camara is not None
                else 10.0
            ),
            step=0.5,
            format="%.1f",
        )

    with col2:
        modelo_cf_idx = 0
        if (
            proyecto.camara is not None
            and proyecto.camara.carga_producto.modelo_capa_fina in modelos_disp
        ):
            modelo_cf_idx = modelos_disp.index(proyecto.camara.carga_producto.modelo_capa_fina)

        modelo_cf = st.selectbox(
            "Modelo cinético de capa fina",
            options=modelos_disp,
            index=modelo_cf_idx,
            help=(
                "Solo se muestran los modelos con parámetros calibrados para el producto. "
                "El modelo logarítmico de Sacilik 2006 es el recomendado para manzana."
            ),
        )

        # Información del modelo seleccionado
        cf = datos_prod.get("capa_fina") or {}
        m_entry = cf.get(modelo_cf) or {}
        calidad_cf = (m_entry.get("calidad_datos") or "").upper() if m_entry else ""
        fuente_cf = m_entry.get("fuente", "—") if m_entry else "—"
        cond = m_entry.get("condiciones_calibracion") or {} if m_entry else {}
        T_K_cal = cond.get("T_K")
        v_cal = cond.get("v_aire_m_s")

        if calidad_cf:
            icono_cal = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(calidad_cf, "⚪")
            st.caption(f"{icono_cal} Calidad: {calidad_cf}")
        if T_K_cal:
            T_rango = T_K_cal if isinstance(T_K_cal, list) else [T_K_cal]
            T_str = f"{min(T_rango)-273.15:.0f}–{max(T_rango)-273.15:.0f} °C"
            st.caption(
                f"🌡️ Rango calibración: {T_str}" + (f"  |  💨 v = {v_cal} m/s" if v_cal else "")
            )
        if fuente_cf and fuente_cf != "—":
            with st.expander("Fuente bibliográfica"):
                st.caption(fuente_cf[:300] + "..." if len(fuente_cf) > 300 else fuente_cf)

        # Isoterma disponible?
        iso = datos_prod.get("isoterma") or {}
        iso_entry = iso.get("gab") or {}
        params_iso = iso_entry.get("params") or {} if iso_entry else {}
        tiene_gab = (
            params_iso.get("X_m") is not None
            and params_iso.get("C") is not None
            and params_iso.get("K") is not None
        )
        X_eq_fallback = props.get("humedad_equilibrio_aire_seco")
        if tiene_gab:
            st.success("✅ Isoterma GAB calibrada disponible.")
        elif X_eq_fallback is not None:
            st.warning(
                f"⚠️ Sin isoterma GAB. Se usará X_eq = {X_eq_fallback:.3f} kg/kg ms (fallback)."
            )

    # -----------------------------------------------------------------------
    # Sección B: Geometría y construcción
    # -----------------------------------------------------------------------
    with st.expander("Geometría de la cámara", expanded=True):
        with st.expander("📐 Esquema de la cámara", expanded=False):
            mostrar_esquema(
                "camara_dimensiones",
                caption="Esquema de la cámara de secado con sus dimensiones principales.",
            )
        c1, c2, c3 = st.columns(3)
        geo_prev = proyecto.camara.geometria if proyecto.camara is not None else GeometriaCamara()
        largo = c1.number_input(
            "Largo [m]",
            min_value=0.1,
            max_value=20.0,
            value=geo_prev.largo_m,
            step=0.05,
            format="%.2f",
        )
        ancho = c2.number_input(
            "Ancho [m]",
            min_value=0.1,
            max_value=10.0,
            value=geo_prev.ancho_m,
            step=0.05,
            format="%.2f",
        )
        alto = c3.number_input(
            "Alto [m]",
            min_value=0.1,
            max_value=5.0,
            value=geo_prev.alto_m,
            step=0.05,
            format="%.2f",
        )
        vol = largo * ancho * alto
        st.caption(f"Volumen interno: {vol:.3f} m³  |  Área de planta: {largo*ancho:.3f} m²")

        cons_prev = (
            proyecto.camara.construccion if proyecto.camara is not None else ConstruccionCamara()
        )
        opciones_cubierta = ["(opaca — sin radiación al producto)"] + list(
            catalogo.CUBIERTAS.keys()
        )
        # Default: para CAJA, "vidrio_comun" (no opaca); para el resto, lo previo o opaca.
        if cons_prev.cubierta_translucida_id is None:
            idx_cub_default = (
                opciones_cubierta.index("vidrio_comun")
                if es_caja_pre and "vidrio_comun" in opciones_cubierta
                else 0
            )
        else:
            try:
                idx_cub_default = opciones_cubierta.index(cons_prev.cubierta_translucida_id)
            except ValueError:
                idx_cub_default = 0
        cubierta_sel = st.selectbox(
            "Techo translúcido",
            options=opciones_cubierta,
            index=idx_cub_default,
            help=(
                "Opaca: cámara cerrada al sol (secador indirecto puro). "
                "Material translúcido: ingresa radiación al producto "
                "Q_rad = I_g · τ · α · A_rad. τ leído del catálogo de cubiertas.\n\n"
                "**CAJA**: obligatoriamente translúcido (la radiación es la única "
                "fuente de energía sin colector externo)."
            ),
        )
        cubierta_id_sel: Optional[str] = (
            None if cubierta_sel == opciones_cubierta[0] else cubierta_sel
        )
        if cubierta_id_sel is not None:
            tau_info = catalogo.CUBIERTAS[cubierta_id_sel].get("transmitancia_solar", 0.85)
            st.caption(f"τ_solar = {float(tau_info):.2f} (del catálogo)")
        elif es_caja_pre:
            st.error(
                "❌ Tipología CAJA requiere techo translúcido. Sin colector externo "
                "y con cubierta opaca, el secador no recibe ninguna energía."
            )
        # --- Materiales de la cámara: pared simple o compuesta ---
        st.markdown("**Materiales de la cámara**")
        st.caption(
            "La composición elegida aplica a paredes laterales, piso y techo "
            "(salvo cuando el techo es translúcido, en cuyo caso ese se trata "
            "aparte arriba)."
        )

        fondos_keys = list(catalogo.FONDOS.keys())
        aislantes_keys = list(catalogo.AISLANTES.keys())

        # Estado previo: detectar si era simple o compuesta
        es_compuesta_prev = cons_prev.pared.es_compuesta
        tipo_pared_default = (
            "Compuesta (cara externa + aislante + cara interna)"
            if es_compuesta_prev
            else "Simple (1 material + espesor)"
        )
        tipo_pared = st.radio(
            "Tipo de pared",
            options=[
                "Simple (1 material + espesor)",
                "Compuesta (cara externa + aislante + cara interna)",
            ],
            index=0 if not es_compuesta_prev else 1,
            horizontal=True,
            help=(
                "Simple: una sola capa estructural. "
                "Compuesta: cara externa + aislante + cara interna, "
                "resistencias térmicas en serie."
            ),
        )

        if tipo_pared.startswith("Simple"):
            # --- Pared simple: 1 capa ---
            # Recuperar default si pared previa era simple
            if not es_compuesta_prev and len(cons_prev.pared.capas) == 1:
                cap_prev = cons_prev.pared.capas[0]
                mat_prev_id = cap_prev.material_id
                esp_prev = cap_prev.espesor_m
                cat_prev = cap_prev.catalogo
            else:
                mat_prev_id = "pino"
                esp_prev = 0.018
                cat_prev = "fondos"

            c_cat, c_mat, c_esp = st.columns([1, 2, 1])
            cat_sel = c_cat.selectbox(
                "Catálogo",
                options=["fondos", "aislantes"],
                index=0 if cat_prev == "fondos" else 1,
                key="p4_pared_simple_cat",
                help="fondos = chapa/madera estructural; aislantes = lana, EPS, PUR.",
            )
            opciones_mat = fondos_keys if cat_sel == "fondos" else aislantes_keys
            try:
                idx_mat = opciones_mat.index(mat_prev_id)
            except ValueError:
                idx_mat = 0
            mat_sel = c_mat.selectbox(
                "Material",
                options=opciones_mat,
                index=idx_mat,
                key="p4_pared_simple_mat",
            )
            esp_sel = c_esp.number_input(
                "Espesor [m]",
                min_value=0.001,
                max_value=0.50,
                value=float(esp_prev),
                step=0.005,
                format="%.4f",
                key="p4_pared_simple_esp",
            )
            pared_widget = ParedCamara(
                capas=[
                    CapaPared(material_id=mat_sel, espesor_m=esp_sel, catalogo=cat_sel),
                ]
            )
        else:
            # --- Pared compuesta: 3 capas (externa + aislante + interna) ---
            if es_compuesta_prev and len(cons_prev.pared.capas) >= 3:
                cap_ext_prev = cons_prev.pared.capas[0]
                cap_ais_prev = cons_prev.pared.capas[1]
                cap_int_prev = cons_prev.pared.capas[-1]
            else:
                cap_ext_prev = CapaPared(
                    material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"
                )
                cap_ais_prev = CapaPared(
                    material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes"
                )
                cap_int_prev = CapaPared(
                    material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"
                )

            st.caption("**Cara externa**")
            c1, c2 = st.columns([2, 1])
            try:
                idx_ext = (
                    fondos_keys.index(cap_ext_prev.material_id)
                    if cap_ext_prev.catalogo == "fondos"
                    else 0
                )
            except ValueError:
                idx_ext = 0
            mat_ext = c1.selectbox(
                "Material (fondos.yaml)",
                options=fondos_keys,
                index=idx_ext,
                key="p4_pared_comp_mat_ext",
            )
            esp_ext = c2.number_input(
                "Espesor externa [m]",
                min_value=0.0001,
                max_value=0.20,
                value=float(cap_ext_prev.espesor_m),
                step=0.0005,
                format="%.4f",
                key="p4_pared_comp_esp_ext",
            )

            st.caption("**Aislante**")
            c3, c4 = st.columns([2, 1])
            try:
                idx_ais = (
                    aislantes_keys.index(cap_ais_prev.material_id)
                    if cap_ais_prev.catalogo == "aislantes"
                    else 0
                )
            except ValueError:
                idx_ais = 0
            mat_ais = c3.selectbox(
                "Material (aislantes.yaml)",
                options=aislantes_keys,
                index=idx_ais,
                key="p4_pared_comp_mat_ais",
            )
            esp_ais = c4.number_input(
                "Espesor aislante [m]",
                min_value=0.001,
                max_value=0.50,
                value=float(cap_ais_prev.espesor_m),
                step=0.005,
                format="%.4f",
                key="p4_pared_comp_esp_ais",
            )

            st.caption("**Cara interna**")
            c5, c6 = st.columns([2, 1])
            try:
                idx_int = (
                    fondos_keys.index(cap_int_prev.material_id)
                    if cap_int_prev.catalogo == "fondos"
                    else 0
                )
            except ValueError:
                idx_int = 0
            mat_int = c5.selectbox(
                "Material (fondos.yaml)",
                options=fondos_keys,
                index=idx_int,
                key="p4_pared_comp_mat_int",
            )
            esp_int = c6.number_input(
                "Espesor interna [m]",
                min_value=0.0001,
                max_value=0.20,
                value=float(cap_int_prev.espesor_m),
                step=0.0005,
                format="%.4f",
                key="p4_pared_comp_esp_int",
            )

            pared_widget = ParedCamara(
                capas=[
                    CapaPared(material_id=mat_ext, espesor_m=esp_ext, catalogo="fondos"),
                    CapaPared(material_id=mat_ais, espesor_m=esp_ais, catalogo="aislantes"),
                    CapaPared(material_id=mat_int, espesor_m=esp_int, catalogo="fondos"),
                ]
            )

        # Resumen del U computado
        _U_cond = pared_widget.U_conduccion_W_m2K
        _R_cond = pared_widget.R_conduccion_m2K_W
        _esp_tot = pared_widget.espesor_total_m
        st.success(
            f"📐 **U_pared (sólo conducción)** = {_U_cond:.2f} W/(m²·K)  |  "
            f"R = {_R_cond:.3f} m²·K/W  |  "
            f"Espesor total = {_esp_tot*1000:.1f} mm"
        )
        st.caption(
            "Nota: este U corresponde sólo a la conducción de la pared. "
            "El motor termodinámico le suma los films convectivos interior y "
            "exterior (h_int + R_pared + h_w) en cada paso de integración."
        )

    # -----------------------------------------------------------------------
    # Sección C: Bandejas
    # -----------------------------------------------------------------------
    with st.expander("Configuración de bandejas", expanded=True):
        band_prev = (
            proyecto.camara.bandejas if proyecto.camara is not None else ConfiguracionBandejas()
        )
        c1, c2 = st.columns(2)
        n_bandejas = c1.number_input(
            "Número de bandejas", min_value=1, max_value=100, value=band_prev.n_bandejas, step=1
        )
        area_bandeja = c2.number_input(
            "Área por bandeja [m²]",
            min_value=0.01,
            max_value=10.0,
            value=band_prev.area_bandeja_m2,
            step=0.05,
            format="%.3f",
        )
        c3, c4 = st.columns(2)
        espesor_capa = c3.number_input(
            "Espesor de capa de producto [m]",
            min_value=0.002,
            max_value=0.2,
            value=band_prev.espesor_capa_m,
            step=0.005,
            format="%.3f",
            help="Modelos de capa fina válidos para espesor ≤ 5 cm.",
        )
        sep_bandejas = c4.number_input(
            "Separación entre bandejas [m]",
            min_value=0.02,
            max_value=1.0,
            value=band_prev.separacion_entre_bandejas_m,
            step=0.01,
            format="%.3f",
            help="Distancia libre entre superficies de bandejas consecutivas.",
        )
        st.caption(
            f"Altura total ocupada por bandejas: {n_bandejas * sep_bandejas:.2f} m  |  "
            f"Área total de bandeja: {n_bandejas * area_bandeja:.2f} m²  |  "
            f"Carga estimada: {masa_kg / n_bandejas / area_bandeja:.1f} kg/m²/bandeja"
        )

        # -------------------------------------------------------------------
        # Pérdida de carga por rugosidad del producto sobre la bandeja
        # -------------------------------------------------------------------
        st.markdown("**Pérdida de carga por rugosidad del producto**")
        _forma = (catalogo.PRODUCTOS.get(prod_id) or {}).get("forma_geometrica") or {}
        _d_p_auto = float(_forma.get("diametro_eq_m") or _D_P_DEFAULT_M)
        _espacio_libre_auto = max(0.0, sep_bandejas - espesor_capa)
        _K_auto = _K_rugosidad_default(_d_p_auto, _espacio_libre_auto)
        _ratio = _d_p_auto / _espacio_libre_auto if _espacio_libre_auto > 0 else 0.0

        K_rug_help = (
            "Coeficiente K de pérdida de forma aplicado como K·ρv²/2 una vez "
            "por bandeja para capturar la rugosidad del lecho de producto en "
            "cross-flow (HORIZONTAL). Darcy-Weisbach de pared lisa subestima "
            "esta pérdida porque el aire no encuentra una superficie pulida "
            "sino partículas que sobresalen y generan estelas locales.\n\n"
            "**Fundamento del default automático** (sin correlación específica "
            "en literatura): tabla de anclajes inspirada en Idelchik / Crane "
            "TP-410, interpolada linealmente sobre el ratio d_p/espacio_libre:\n"
            "• ratio < 0.05  →  K = 0.2  (casi liso)\n"
            "• 0.05–0.15     →  K = 0.2–0.5  (rugosidad significativa)\n"
            "• 0.15–0.30     →  K = 0.5–1.0  (obstrucción parcial)\n"
            "• 0.30–0.50     →  K = 1.0–2.0  (cuasi-bloqueo)\n\n"
            "En VERTICAL_ASCENDENTE este término no se aplica porque la "
            "ecuación de Ergun ya captura la rugosidad del producto vía la "
            "esfericidad Φ_s y el diámetro de partícula d_p."
        )

        forzar_K_rug = st.checkbox(
            "Forzar K_rugosidad (override del default automático)",
            value=band_prev.K_rugosidad_producto is not None,
            help=K_rug_help,
        )
        K_rugosidad_val: Optional[float] = None
        if forzar_K_rug:
            K_rugosidad_val = st.number_input(
                "K_rugosidad [adim]",
                min_value=0.0,
                max_value=10.0,
                value=float(band_prev.K_rugosidad_producto or _K_auto),
                step=0.1,
                format="%.2f",
                help="Se aplica como K·ρv²/2 una vez por bandeja.",
            )
        else:
            st.caption(
                f"K_rugosidad estimado automáticamente: **{_K_auto:.2f}**  "
                f"(d_p = {_d_p_auto * 1000:.1f} mm, espacio libre = "
                f"{_espacio_libre_auto * 100:.1f} cm, ratio = {_ratio:.3f})"
            )

    # -----------------------------------------------------------------------
    # Sección D: Flujo de aire
    # -----------------------------------------------------------------------
    with st.expander("Flujo de aire", expanded=True):
        flujo_prev = proyecto.camara.flujo if proyecto.camara is not None else ConfiguracionFlujo()

        # Sugerir caudal del colector si está disponible
        caudal_sugerido = flujo_prev.caudal_masico_kg_s
        hint_caudal = ""
        if proyecto.colector is not None:
            Q_m3s = proyecto.colector.caudal_total_m3_s()
            rho_est = 1.1
            m_col = Q_m3s * rho_est
            hint_caudal = (
                f"El colector entrega {Q_m3s*1000:.1f} L/s → "
                f"~{m_col:.3f} kg/s (a ρ≈{rho_est} kg/m³)."
            )

        c1, c2 = st.columns(2)
        caudal = c1.number_input(
            "Caudal másico [kg/s]",
            min_value=0.001,
            max_value=10.0,
            value=caudal_sugerido,
            step=0.001,
            format="%.4f",
            help=hint_caudal or "Caudal de aire seco que circula por la cámara.",
        )
        if hint_caudal:
            c1.caption(f"💡 {hint_caudal}")

        dir_opciones = {
            "HORIZONTAL": DireccionFlujo.HORIZONTAL,
            "VERTICAL_ASCENDENTE": DireccionFlujo.VERTICAL_ASCENDENTE,
        }
        dir_prev_str = flujo_prev.direccion_flujo.value
        dir_sel = c2.selectbox(
            "Dirección del flujo",
            options=list(dir_opciones.keys()),
            index=list(dir_opciones.keys()).index(dir_prev_str),
        )
        direccion = dir_opciones[dir_sel]

        usar_HR = st.checkbox(
            "Especificar HR de entrada",
            value=flujo_prev.HR_entrada_fraccion is not None,
            help="Si no se especifica, el cálculo usa el fallback escalar del catálogo.",
        )
        HR_entrada_frac: float | None = None
        if usar_HR:
            HR_pct = st.slider(
                "HR del aire en entrada a la cámara [%]",
                min_value=5,
                max_value=95,
                value=int((flujo_prev.HR_entrada_fraccion or _HR_DEFAULT_PCT / 100) * 100),
                step=1,
            )
            HR_entrada_frac = HR_pct / 100.0

        # Velocidad superficial estimada
        rho_est = 1.1
        Q_vol = caudal / rho_est
        v_sup = Q_vol / (ancho * alto) if (ancho * alto) > 0 else 0.0
        st.caption(
            f"Velocidad superficial estimada: {v_sup:.2f} m/s  |  "
            f"Q_vol ≈ {Q_vol * 1000:.1f} L/s"
        )

    # -----------------------------------------------------------------------
    # Sección E: Condiciones de operación
    # -----------------------------------------------------------------------
    with st.expander("Condiciones de operación", expanded=True):
        if es_caja_pre:
            hint_T = (
                "Tipología CAJA: el aire entrante es el ambiente (sin colector). "
                "Configurar T ≈ T_amb representativa del emplazamiento."
            )
        else:
            hint_T = (
                "Temperatura del aire en la cámara. " "Típicamente ≈ T_salida del colector solar."
            )
        T_op_prev_C = _T_OP_DEFAULT_C
        if proyecto.camara is not None and "T_operacion_K" in st.session_state:
            T_op_prev_C = kelvin_a_celsius(
                st.session_state.get("cam_T_operacion_K", celsius_a_kelvin(_T_OP_DEFAULT_C))
            )

        T_op_C = st.slider(
            "Temperatura de operación en cámara [°C]",
            min_value=int(_T_OP_MIN_C),
            max_value=int(_T_OP_MAX_C),
            value=int(st.session_state.get("cam_T_op_C", _T_OP_DEFAULT_C)),
            step=1,
            help=hint_T,
        )
        st.session_state["cam_T_op_C"] = T_op_C

        HR_op_pct = st.slider(
            "HR en cámara para cálculo de X_eq [%]",
            min_value=5,
            max_value=95,
            value=int(st.session_state.get("cam_HR_op_pct", _HR_DEFAULT_PCT)),
            step=1,
            help=(
                "Humedad relativa del aire dentro de la cámara. "
                "Determina X_eq via isoterma GAB. En la práctica sube durante el secado; "
                "para prediseño se usa un valor representativo."
            ),
        )
        st.session_state["cam_HR_op_pct"] = HR_op_pct

    # -----------------------------------------------------------------------
    # Sección F: Modo de cálculo
    # -----------------------------------------------------------------------

    # Detectar restricciones
    from core.proyecto import Tipologia

    tipologia = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
    es_caja = tipologia == Tipologia.CAJA
    solo_midilli = modelos_disp == ["midilli"]

    with st.expander("Modo de cálculo (motor numérico)", expanded=False):

        _OPCIONES_MODO = [
            "Capa fina — Estático (rápido)",
            "Termodinámico (balance acoplado)",
        ]

        # Reconstruir índice previo
        _modo_prev_raw = (
            proyecto.camara.modo_calculo if proyecto.camara is not None else "termodinamico"
        )
        _idx_prev = 1 if _modo_prev_raw == "termodinamico" else 0

        modo_label = st.radio(
            "Motor para el cálculo del secado",
            options=_OPCIONES_MODO,
            index=_idx_prev,
            help=(
                "**Estático:** brentq algebraico — no depende de la masa, rápido.\n\n"
                "**Termodinámico:** balance acoplado calor-masa con pared 3-nodos, "
                "cp(X) variable y política anti-rehumectación. Soporta forzantes "
                "constantes o día sintético senoidal, en horizonte 1–21 días."
            ),
        )

        # Limpiar flag obsoleto del antiguo motor dinámico
        st.session_state.pop("cam_modo_dinamico", None)

        # Derive modo_calculo para el objeto Camara
        if "Termodinámico" in modo_label:
            modo_calculo = "termodinamico"
        else:
            modo_calculo = "capa_fina"

        # Sub-controles del modo termodinámico: tipo de forzantes + horizonte
        tipo_forzantes = "constantes"
        n_dias = 1
        I_g_max_W_m2 = 0.0
        if modo_calculo == "termodinamico":
            real_ok, real_motivo = _disponibilidad_forzantes_reales(
                st.session_state.get("p3_eval"),
                proyecto,
            )

            _label_real = (
                "Día real (clima ambiente)"
                if es_caja
                else "Día real (clima + colector)"
            )
            _opciones_forz = [
                "Constantes (rápido)",
                "Día sintético (senoidal)",
                _label_real,
            ]
            _forz_idx_prev = st.session_state.get("cam_forz_idx", 0)
            _help_real = (
                "**Día real:** serie horaria de T_amb, ω, viento e I_g del "
                "clima NASA POWER de P2 para el día seleccionado en P1. "
                "T_entrada al lecho = T_amb (la cámara actúa como colector)."
                if es_caja
                else "**Día real:** serie horaria del colector calculada en P3 + "
                "clima NASA POWER de P2."
            )
            forz_sel = st.radio(
                "Forzantes del aire de entrada",
                options=_opciones_forz,
                index=_forz_idx_prev,
                horizontal=False,
                help=(
                    "**Constantes:** T_ent, ω y T_amb fijos al valor de diseño. "
                    "Equivale a una corrida puntual.\n\n"
                    "**Día sintético:** curva senoidal día/noche (pico al mediodía, "
                    "±15 K en T_sal_col, ±5 K en T_amb). Captura ciclo diurno.\n\n"
                    + _help_real
                ),
            )
            st.session_state["cam_forz_idx"] = _opciones_forz.index(forz_sel)
            if "Constantes" in forz_sel:
                tipo_forzantes = "constantes"
            elif "sintético" in forz_sel:
                tipo_forzantes = "sintetico"
            else:
                tipo_forzantes = "real"

            if tipo_forzantes == "real" and not real_ok:
                st.warning(f"⚠️ Día real no disponible: {real_motivo} Cae a 'Día sintético'.")
                tipo_forzantes = "sintetico"

            _opciones_hz = ["1 día", "Multi-día"]
            _hz_idx = st.session_state.get("cam_hz_idx", 0)
            _help_hz = (
                "1 día: 24 h de simulación. Multi-día: 24 h × N (1–21).\n\n"
                "Constantes: define el `t_max_s` de la corrida.\n\n"
                "Sintético/Real: define cuántos días tipo se replican."
            )
            hz_sel = st.selectbox(
                "Horizonte de secado",
                options=_opciones_hz,
                index=_hz_idx,
                help=_help_hz,
            )
            st.session_state["cam_hz_idx"] = _opciones_hz.index(hz_sel)
            if hz_sel == "Multi-día":
                n_dias = int(
                    st.number_input(
                        "Número de días",
                        min_value=1,
                        max_value=21,
                        value=int(st.session_state.get("cam_n_dias", 3)),
                        step=1,
                    )
                )
                st.session_state["cam_n_dias"] = n_dias

            if tipo_forzantes == "real":
                if es_caja:
                    st.info(
                        "📅 Forzantes reales (CAJA): T_entrada(t) = T_amb(t) y "
                        "ω(t), v_viento(t) e I_g(t) del clima NASA POWER de P2 "
                        "para el día de análisis seleccionado en P1."
                    )
                else:
                    st.info(
                        "📅 Forzantes reales: T_sal_col(t) del cálculo P3, "
                        "ω_amb(t), T_amb(t), v_viento(t) e I_g(t) del clima NASA POWER de P2."
                    )

            # I_g_max del día sintético: sólo relevante si hay techo translúcido
            if tipo_forzantes == "sintetico" and cubierta_id_sel is not None:
                I_g_max_W_m2 = float(
                    st.number_input(
                        "I_g pico al mediodía [W/m²]",
                        min_value=0.0,
                        max_value=1400.0,
                        value=float(st.session_state.get("cam_I_g_max", 800.0)),
                        step=50.0,
                        help=(
                            "Pico de irradiancia global horizontal sobre el techo. "
                            "Típico día claro: 800–1000 W/m². Curva diaria: semicampana "
                            "sinusoidal positiva (sol entre 6 h y 18 h)."
                        ),
                    )
                )
                st.session_state["cam_I_g_max"] = I_g_max_W_m2
            else:
                I_g_max_W_m2 = 0.0

        T_prod_inicial_K_val: float | None = None
        if modo_calculo == "termodinamico":
            T_amb_repr_K, T_amb_origen = _T_amb_representativa_K(proyecto)
            st.caption(
                f"📍 T ambiente representativa: **{T_amb_repr_K - 273.15:.1f} °C** "
                f"({T_amb_origen}). Se usa para pérdidas a paredes y como T inicial "
                "del producto si no se define explícitamente."
            )
            usar_T_prod_explicita = st.checkbox(
                "Definir T inicial del producto explícitamente "
                "(refrigerado, precalentado, etc.)",
                value=(
                    proyecto.camara is not None
                    and proyecto.camara.carga_producto.T_prod_inicial_K is not None
                ),
            )
            if usar_T_prod_explicita:
                T_prod_default_C = (
                    kelvin_a_celsius(proyecto.camara.carga_producto.T_prod_inicial_K)
                    if (
                        proyecto.camara is not None
                        and proyecto.camara.carga_producto.T_prod_inicial_K is not None
                    )
                    else 25.0
                )
                T_prod_inicial_C = st.number_input(
                    "T inicial del producto [°C]",
                    min_value=-10.0,
                    max_value=70.0,
                    value=float(T_prod_default_C),
                    step=1.0,
                    help="Rango razonable: −10 °C (refrigerado) a +70 °C (precalentado).",
                )
                T_prod_inicial_K_val = celsius_a_kelvin(T_prod_inicial_C)

            iso = (catalogo.PRODUCTOS.get(prod_id, {}).get("isoterma") or {}).get("gab") or {}
            iso_params = iso.get("params") or {}
            tiene_gab = (
                iso_params.get("X_m") is not None
                and iso_params.get("C") is not None
                and iso_params.get("K") is not None
            )
            if not tiene_gab:
                st.warning(
                    "⚠️ El producto seleccionado **no tiene parámetros GAB calibrados**. "
                    "El motor termodinámico usará un fallback no-físico (rampa lineal "
                    "`a_w = X / X_inicial`) que sobrestima el secado en X bajo. Para "
                    "resultados confiables, cargar parámetros GAB en el catálogo o "
                    "elegir otro producto."
                )

    # -----------------------------------------------------------------------
    # Builder de Camara desde los widgets actuales (closure)
    # -----------------------------------------------------------------------
    def _build_camara(*, modo_calculo_override: str | None = None) -> Camara:
        """Construye Camara con los valores actuales de los widgets."""
        geo = GeometriaCamara(largo_m=largo, ancho_m=ancho, alto_m=alto)
        cons = ConstruccionCamara(
            cubierta_translucida_id=cubierta_id_sel,
            pared=pared_widget,
        )
        band = ConfiguracionBandejas(
            n_bandejas=n_bandejas,
            area_bandeja_m2=area_bandeja,
            espesor_capa_m=espesor_capa,
            separacion_entre_bandejas_m=sep_bandejas,
            K_rugosidad_producto=K_rugosidad_val,
        )
        flujo = ConfiguracionFlujo(
            caudal_masico_kg_s=caudal,
            fraccion_recirculacion=0.0,
            direccion_flujo=direccion,
            HR_entrada_fraccion=HR_entrada_frac,
        )
        carga = CargaProducto(
            producto_id=prod_id,
            masa_total_kg=masa_kg,
            humedad_inicial_X=X_ini,
            humedad_objetivo_X=X_obj,
            modelo_capa_fina=modelo_cf,
            modelo_isoterma="gab",
            T_prod_inicial_K=T_prod_inicial_K_val,
        )
        return Camara(
            geometria=geo,
            construccion=cons,
            bandejas=band,
            flujo=flujo,
            carga_producto=carga,
            modo_calculo=modo_calculo_override or modo_calculo,
        )

    # -----------------------------------------------------------------------
    # Sección anual prominente (cuando modo_analisis == ANUAL)
    # -----------------------------------------------------------------------
    modo_analisis = getattr(proyecto.configuracion, "modo_analisis", None)
    if modo_analisis == ModoAnalisis.ANUAL:
        st.divider()
        _render_operacion_anual(proyecto, _build_camara)

    # -----------------------------------------------------------------------
    # Botón de cálculo (batch puntual del día sintético/real)
    # -----------------------------------------------------------------------
    st.divider()
    if modo_analisis == ModoAnalisis.ANUAL:
        st.markdown("### Test puntual de un día (opcional)")
        st.caption(
            "Permite correr un batch único con día sintético o real para "
            "validar el motor o explorar transitorios de un día. **No** "
            "alimenta los resultados anuales — esos salen del botón "
            "'Calcular operación anual' de arriba."
        )
    _bloqueo_caja_opaca = es_caja_pre and cubierta_id_sel is None
    calcular = st.button(
        "⚙️ Calcular cámara",
        type="primary" if modo_analisis != ModoAnalisis.ANUAL else "secondary",
        disabled=_bloqueo_caja_opaca,
        help=(
            "Tipología CAJA requiere techo translúcido para poder calcular."
            if _bloqueo_caja_opaca
            else None
        ),
    )

    if calcular:
        try:
            geo = GeometriaCamara(largo_m=largo, ancho_m=ancho, alto_m=alto)
            cons = ConstruccionCamara(
                cubierta_translucida_id=cubierta_id_sel,
                pared=pared_widget,
            )
            band = ConfiguracionBandejas(
                n_bandejas=n_bandejas,
                area_bandeja_m2=area_bandeja,
                espesor_capa_m=espesor_capa,
                separacion_entre_bandejas_m=sep_bandejas,
                K_rugosidad_producto=K_rugosidad_val,
            )
            flujo = ConfiguracionFlujo(
                caudal_masico_kg_s=caudal,
                fraccion_recirculacion=0.0,
                direccion_flujo=direccion,
                HR_entrada_fraccion=HR_entrada_frac,
            )
            carga = CargaProducto(
                producto_id=prod_id,
                masa_total_kg=masa_kg,
                humedad_inicial_X=X_ini,
                humedad_objetivo_X=X_obj,
                modelo_capa_fina=modelo_cf,
                modelo_isoterma="gab",
                T_prod_inicial_K=T_prod_inicial_K_val,
            )
            camara = Camara(
                geometria=geo,
                construccion=cons,
                bandejas=band,
                flujo=flujo,
                carga_producto=carga,
                modo_calculo=modo_calculo,
            )
            proyecto.camara = camara

        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Error de configuración: {exc}")
            return

        # Advertencias estáticas
        adv_list = advertencias_camara(camara)
        if adv_list:
            st.subheader("Advertencias de diseño")
            _mostrar_advertencias(adv_list)
        else:
            st.success("✅ Diseño sin advertencias.")

        # Cálculo numérico
        T_op_K = celsius_a_kelvin(float(T_op_C))
        HR_op = HR_op_pct / 100.0
        T_amb_calc_K, _ = _T_amb_representativa_K(proyecto)

        # Presión atmosférica representativa del emplazamiento (corregida por
        # altitud o NASA POWER). Sin esta corrección, las psicrométricas usan
        # 101 325 Pa y sobrestiman ω_sat en sitios elevados.
        from calculos.balance_global import presion_representativa_proyecto

        P_proyecto_Pa, P_origen = presion_representativa_proyecto(proyecto)
        st.caption(f"Presión atmosférica usada: {P_origen}.")

        try:
            if modo_calculo == "termodinamico":
                fz_aire = _construir_forzantes_termodinamico(
                    tipo_forzantes=tipo_forzantes,
                    T_op_K=T_op_K,
                    HR_op=HR_op,
                    caudal_kg_s=camara.flujo.caudal_masico_kg_s,
                    T_amb_K=T_amb_calc_K,
                    n_dias=n_dias,
                    proyecto=proyecto,
                    p3_eval=st.session_state.get("p3_eval"),
                    I_g_max_W_m2=I_g_max_W_m2,
                    P_Pa=P_proyecto_Pa,
                )
                t_max_efectivo = (
                    float(fz_aire.t_s[-1]) if fz_aire is not None else float(n_dias) * 24.0 * 3600.0
                )
                with st.spinner("Integrando motor termodinámico..."):
                    res = calcular_camara(
                        camara,
                        T_op_K,
                        HR_op,
                        T_amb_K=T_amb_calc_K,
                        P_Pa=P_proyecto_Pa,
                        t_max_s=t_max_efectivo,
                        forzantes_aire=fz_aire,
                    )
                # Persistir horizonte para que P7 pueda re-correr la pipeline
                # transitoria con auxiliar + motor (mejora 19).
                if fz_aire is not None:
                    st.session_state["p4_forzantes_horizonte"] = fz_aire
                    st.session_state["p4_horizonte_resultado"] = res
                    st.session_state["p4_horizonte_meta"] = {
                        "n_dias": int(n_dias),
                        "modo_forzantes": tipo_forzantes,
                    }
                else:
                    # Modo "Constantes": no hay horizonte transitorio para P7.
                    st.session_state.pop("p4_forzantes_horizonte", None)
                    st.session_state.pop("p4_horizonte_resultado", None)
                    st.session_state.pop("p4_horizonte_meta", None)
            else:
                res = calcular_camara(
                    camara,
                    T_op_K,
                    HR_op,
                    T_amb_K=T_amb_calc_K,
                    P_Pa=P_proyecto_Pa,
                )
                # Modo capa fina: no se propaga horizonte a P7.
                st.session_state.pop("p4_forzantes_horizonte", None)
                st.session_state.pop("p4_horizonte_resultado", None)
                st.session_state.pop("p4_horizonte_meta", None)
        except Exception as exc:
            st.error(f"❌ Error en el cálculo: {exc}")
            return

        # Limpiar resultado del motor dinámico viejo (si quedó en session_state)
        st.session_state.pop("p4_resultado_dinamico", None)
        st.session_state.pop("p4_din_X_obj", None)
        st.session_state.pop("p4_din_prod_id", None)
        st.session_state.pop("p4_din_modelo", None)

        # Advertencias del cálculo
        if res.advertencias:
            st.subheader("Advertencias del cálculo")
            for msg in res.advertencias:
                st.warning(f"⚠️ {msg}")

        # Display branched por tipo de resultado
        if isinstance(res, ResultadoMotorTermodinamico):
            # ---- Display motor termodinámico ----
            st.subheader("Resultados del motor termodinámico")
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            if res.t_secado_s is not None:
                col_r1.metric(
                    "Tiempo de secado",
                    f"{res.t_secado_s / 3600.0:.1f} h",
                )
            else:
                col_r1.metric("Tiempo de secado", "no alcanzado", help=res.status)
            col_r2.metric("Status", res.status)
            col_r3.metric(
                "Agua evaporada",
                f"{res.masa_evaporada_total_kg:.2f} kg",
                help="Integral de ṁ_w(t) sobre la simulación.",
            )
            col_r4.metric(
                "X final",
                f"{res.X_prod_kg_kg[-1]:.4f}",
                help="Humedad del producto al final de la integración.",
            )

            # Diagnósticos extras del nuevo motor
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            col_d1.metric(
                "T_max producto",
                f"{res.T_max_alcanzada_K - 273.15:.1f} °C",
                help="Máxima T_prod registrada en la trayectoria.",
            )
            col_d2.metric(
                "Horas anti-rehumectación",
                f"{res.horas_clipeo_nocturno_s / 3600.0:.1f} h",
                help="Tiempo con política B activa (dX/dt clipeado a 0).",
            )
            col_d3.metric(
                "Horas HR > 95 %",
                f"{res.horas_HR_alta_s / 3600.0:.1f} h",
                help="Tiempo con HR del aire en cámara > 95 % (riesgo saturación).",
            )
            col_d4.metric(
                "Energía radiativa directa",
                f"{res.energia_rad_total_J / 3.6e6:.2f} kWh",
                help=(
                    "∫ Q_rad(t) dt — aporte solar directo al producto a través "
                    "del techo translúcido. 0 en cámaras opacas."
                ),
            )

            if res.status == "t_max_alcanzado":
                horas_total = float(res.t_array_s[-1]) / 3600.0
                st.warning(
                    f"⚠️ En {horas_total / 24.0:.1f} día(s) no se alcanzó "
                    f"X_obj = {X_obj:.3f} kg/kg ms. "
                    f"Humedad final: {res.X_prod_kg_kg[-1]:.3f} kg/kg ms. "
                    "Aumentar el horizonte o mejorar las condiciones."
                )

            fig = _grafica_secado_termodinamico(res, X_obj, prod_id)
            st.plotly_chart(fig, width="stretch")

            with st.expander(
                "ℹ️ Sobre la forma de la curva de ṁ_w (modelo difusivo)",
                expanded=False,
            ):
                st.markdown(
                    "El motor termodinámico modela la evaporación como\n\n"
                    "$$\\dot m_w = K_m \\cdot A_{prod} \\cdot "
                    "(\\omega_{sup} - \\omega_{flujo})$$\n\n"
                    "con $\\omega_{sup} = \\omega_{sat}(T_{prod}) \\cdot a_w(X_{prod})$.\n\n"
                    "**Período de calentamiento (warming-up):** al inicio el "
                    "producto está más frío que el aire. ω_sat(T_prod) es chica "
                    "(crece exponencialmente con T por Clausius-Clapeyron), así "
                    "que ω_sup ≈ ω_ent y ṁ_w arranca cerca de cero. A medida "
                    "que T_prod sube, ω_sup crece rápido y ṁ_w escala con él. "
                    "Esto se ve como una **rampa inicial creciente**, no como "
                    'el clásico "velocidad constante desde t=0" de los '
                    "modelos empíricos (Lewis, Page).\n\n"
                    "**Período de velocidad decreciente:** aparece sólo cuando "
                    "X cruza X_m (humedad de monocapa GAB). Recién ahí a_w "
                    "empieza a caer y arrastra a ω_sup hacia abajo. Si tu "
                    "X_objetivo > X_m, terminás el secado antes de entrar a "
                    "esta zona y nunca ves la caída.\n\n"
                    "**Pico al final de la corrida:** si el evento X_obj se "
                    "dispara cerca del mediodía solar, T_prod (y por ende ṁ_w) "
                    "está en su máximo justo cuando la integración se corta. "
                    "El último punto guardado coincide con el pico — no es "
                    "un artefacto de graficación.\n\n"
                    "Los modelos empíricos de capa fina (Lewis/Page/etc.) "
                    "**absorben el warming-up dentro del parámetro k**, por "
                    "eso muestran MR cayendo desde 1 desde t=0. El motor "
                    "difusivo modela el balance de energía explícitamente — "
                    "es más realista pero la forma de la curva difiere."
                )
        else:
            # ---- Display motor capa fina (existente) ----
            st.subheader("Resultados del prediseño")

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            t_h = res.t_secado_s / 3600.0

            col_r1.metric(
                "Tiempo de secado",
                f"{t_h:.1f} h" if res.convergencia_ok else f">{t_h:.0f} h",
                help="Tiempo estimado para reducir X₀ a X_obj.",
            )
            col_r2.metric(
                "X_eq",
                f"{res.X_eq_kg_kg:.4f} kg/kg ms",
                help=f"Humedad de equilibrio ({res.fuente_X_eq}).",
            )
            col_r3.metric(
                "Agua extraída",
                f"{res.masa_agua_extraida_kg:.2f} kg",
                help="Masa de agua que debe evaporarse.",
            )
            col_r4.metric(
                "MR objetivo",
                f"{res.MR_obj:.4f}",
                help="Razón de humedad al final del secado.",
            )

            if not res.convergencia_ok:
                st.warning(f"⚠️ {res.mensaje_convergencia}")

            fig = _grafica_curva_secado(res, X_ini, X_obj, prod_id)
            st.plotly_chart(fig, width="stretch")

        # Resumen compacto
        with st.expander("Resumen de la configuración"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Producto:** {prod_id}")
                st.write(f"**Masa:** {masa_kg:.1f} kg")
                st.write(f"**X₀:** {X_ini:.2f} kg/kg ms")
                st.write(f"**X_obj:** {X_obj:.3f} kg/kg ms")
                st.write(f"**Modelo capa fina (catálogo):** {modelo_cf}")
                st.write(f"**Motor numérico:** {modo_calculo}")
                st.write(f"**T_operación:** {T_op_C} °C")
                st.write(f"**HR_operación:** {HR_op_pct} %")
            with c2:
                st.write(f"**Cámara:** {largo}×{ancho}×{alto} m")
                st.write(f"**Bandejas:** {n_bandejas} × {area_bandeja:.2f} m²")
                st.write(f"**Espesor capa:** {espesor_capa*100:.1f} cm")
                st.write(f"**Caudal:** {caudal:.4f} kg/s")
                st.write(f"**Dirección:** {dir_sel}")
                if isinstance(res, ResultadosCamara):
                    st.write(f"**Fuente X_eq:** {res.fuente_X_eq}")
                else:
                    st.write(f"**T_amb (cálculo):** {T_amb_calc_K - 273.15:.1f} °C")

    # --- Guardar configuración ---
    if proyecto.camara is not None:
        st.divider()
        from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

        col_txt, col_json = st.columns(2)
        with col_txt:
            st.download_button(
                "Guardar configuración de la cámara (.txt)",
                data=_texto_config_camara(proyecto.camara, st.session_state),
                file_name=nombre_archivo_descarga(proyecto, "camara", "txt"),
                mime="text/plain",
                width="stretch",
            )
        with col_json:
            st.download_button(
                "Guardar configuración de la cámara (.json)",
                data=dump_json(_json_config_camara(proyecto.camara, st.session_state)),
                file_name=nombre_archivo_descarga(proyecto, "camara", "json"),
                mime="application/json",
                width="stretch",
            )
