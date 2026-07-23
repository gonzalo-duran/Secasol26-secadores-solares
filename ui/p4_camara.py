"""
Pestaña 4 — Cámara de Secado.

Permite al usuario configurar la geometría, bandejas, flujo y carga de producto
de la cámara de secado solar. Calcula el tiempo de secado estimado y muestra
la curva de humedad X(t) según el modelo de capa fina seleccionado.

Sin cálculo en el motor de cámara: solo configuración, validación estática y
cálculo de tiempo de secado via calculos/camara_calc.py.
"""

from __future__ import annotations

from datetime import time as _time
from typing import Optional

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from calculos.balance_global import (
    armar_forzantes_aire,
    caudal_masico_banco_kg_s,
    construir_serie_sintetica_dia_tipo,
    presion_representativa_proyecto,
)
from calculos.camara_calc import calcular_camara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.clima_medido import meses_cubiertos
from calculos.conversiones_angulo import (
    acimut_duffie_a_pvlib,
    acimut_duffie_a_ui360,
    acimut_ui360_a_duffie,
)
from calculos.motor_calc import _D_P_DEFAULT_M, _C_obstruccion_bloqueo
from calculos.psicrometria import humedad_absoluta
from calculos.simulacion_anual import ResultadosAnual, simular_anual
from calculos.simulacion_ventana import PoliticaRecarga
from core import catalogo
from core.camara import (
    Camara,
    CapaPared,
    CarasTranslucidas,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionCarros,
    ConfiguracionFlujo,
    ConfiguracionTunel,
    ConstruccionCamara,
    DireccionFlujo,
    ForzantesAire,
    GeometriaCamara,
    ParedCamara,
    _modelos_disponibles,
    advertencias_camara,
)
from core.proyecto import ModoAnalisis
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
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius
from ui.componentes.vigencia import extras_horizonte, invalidar, registrar, registrar_anual

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_T_OP_MIN_C: float = 30.0
_T_OP_MAX_C: float = 90.0
_T_OP_DEFAULT_C: float = 55.0

_HR_DEFAULT_PCT: float = 20.0
# Default de fábrica de ConfiguracionFlujo.caudal_masico_kg_s: si el valor
# guardado es exactamente este, nadie lo tocó y el caudal puede seguir al
# colector sin pisar una decisión del usuario.
_CAUDAL_FLUJO_DEFAULT_KG_S: float = ConfiguracionFlujo().caudal_masico_kg_s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _productos_disponibles() -> dict[str, str]:
    """Retorna {prod_id: label} solo para productos con al menos un modelo calibrado."""
    result: dict[str, str] = {}
    for prod_id, datos in catalogo.PRODUCTOS.items():
        if _modelos_disponibles(datos):
            desc = t_catalogo(datos, default=prod_id)
            label = f"{prod_id} — {desc[:60]}..." if len(desc) > 60 else f"{prod_id} — {desc}"
            result[prod_id] = label
    return result


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia traducida por código (widget único, F5)."""
    render_advertencias(adv_list, con_sugerencia=False)


def _T_amb_representativa_K(proyecto) -> tuple[float, str]:
    """Devuelve T_amb representativa para el motor termodinámico, con su origen.

    Si hay clima cargado, usa la media anual; si no, fallback 25 °C.
    """
    clima = getattr(proyecto, "clima", None)
    if clima is not None and getattr(clima, "T_amb_K", None) is not None:
        T_arr = np.asarray(clima.T_amb_K)
        if T_arr.size > 0:
            T = float(np.nanmean(T_arr))
            return T, t("p4.t_amb_origen.media_anual", t=T - 273.15)
    return 298.15, t("p4.t_amb_origen.fallback")


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
            name=t("p4.graficas.curva_x"),
        )
    )
    fig.add_hline(
        y=resultados.X_eq_kg_kg,
        line=dict(color="gray", dash="dash", width=1),
        annotation_text=t("p4.graficas.x_eq", v=resultados.X_eq_kg_kg),
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=X_obj,
        line=dict(color="red", dash="dot", width=1.5),
        annotation_text=t("p4.graficas.x_obj", v=X_obj),
    )
    fig.add_hline(
        y=X_0,
        line=dict(color="green", dash="dot", width=1),
        annotation_text=t("p4.graficas.x_0", v=X_0),
        annotation_position="top right",
    )

    if resultados.convergencia_ok:
        t_sec_h = resultados.t_secado_s / 3600.0
        fig.add_vline(
            x=t_sec_h,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=t("p4.graficas.t_marca", v=t_sec_h),
        )

    fig.update_xaxes(title_text=t("p4.graficas.eje_tiempo"))
    fig.update_yaxes(title_text=t("p4.graficas.eje_x"), rangemode="tozero")
    fig.update_layout(
        title_text=t("p4.graficas.titulo_curva", prod=prod_id, modelo=resultados.modelo_usado),
        height=400,
        showlegend=True,
    )
    return fig


# ---------------------------------------------------------------------------
# Helpers del motor termodinámico (forzantes + gráficas)
# ---------------------------------------------------------------------------

# Clave de session_state donde se depositan las advertencias del paso de trabajo
# (ADV_PASO_SINTETICO) para que P4/P7 las muestren tras resolver el clima.
_PASO_ADV_KEY = "p4_paso_trabajo_advertencias"


def _datos_local_paso(proyecto):
    """Devuelve el clima al **paso de trabajo** de P1, en hora local (fase 1b).

    Resuelve ``clima.datos`` a la resolución ``configuracion.paso_trabajo_s``
    (sub-horario real desde ``datos_nativos`` o interpolado del horario con
    ``ADV_PASO_SINTETICO``), lo convierte a la zona local y lo filtra al año
    climático. Las advertencias quedan en ``st.session_state[_PASO_ADV_KEY]``
    para que la UI las muestre.

    Returns:
        DataFrame en hora local al paso de trabajo (o None si no hay clima).
    """
    from calculos.clima_calc import resolver_datos_trabajo

    paso_s = getattr(proyecto.configuracion, "paso_trabajo_s", 3600.0)
    df, adv = resolver_datos_trabajo(proyecto.clima, paso_s)
    st.session_state[_PASO_ADV_KEY] = list(adv)
    if df is None:
        return None
    df_local = df.tz_convert(proyecto.emplazamiento.zona_horaria)
    return df_local[df_local.index.year == proyecto.clima.anio]


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
    dias_consecutivos: bool = False,
) -> ForzantesAire | None:
    """Arma ForzantesAire para el motor termodinámico según el tipo elegido.

    - "constantes" → None: el wire-up construye degeneradas y el motor se
      comporta como en condiciones fijas (compatible con tests antiguos).
    - "sintetico"  → curva senoidal día/noche con pico al mediodía. Amplitudes:
      T_sal_col ±15 K respecto al T_op, T_amb ±5 K respecto a T_amb_K.
      I_g(t) semicampana con pico I_g_max_W_m2 (0 si no hay caras translúcidas
      activas). Sin posición solar horaria disponible, I_g_max_W_m2 se
      interpreta como pico sobre CADA cara activa; ``factores_sinteticos``
      lo escala a la irradiancia equivalente al producto y deriva el pico de
      ``Q_rad_aire`` (radiación no interceptada que calienta el aire).
    - "real"       → serie horaria del colector calculada en P3 + clima NASA
      de P2. Requiere `p3_eval` (dict producido por P3 en modo 'diario') y
      `proyecto` con `clima.datos` no nulo. GHI viene del clima.
    """
    if tipo_forzantes == "constantes":
        return None
    if tipo_forzantes == "sintetico":
        from calculos.radiacion_camara import factores_sinteticos

        omega_amb = humedad_absoluta(HR_op, T_op_K, P_Pa)
        camara_proy = getattr(proyecto, "camara", None)
        factor_prod, factor_aire = (
            factores_sinteticos(camara_proy) if camara_proy is not None else (1.0, 0.0)
        )
        return construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=T_op_K,
            T_sal_col_amplitud_K=15.0,
            omega_amb=omega_amb,
            m_dot_aire_seco_kg_s=caudal_kg_s,
            T_amb_promedio_K=T_amb_K,
            T_amb_amplitud_K=5.0,
            v_viento_ms=2.0,
            I_g_max_W_m2=I_g_max_W_m2 * factor_prod,
            Q_rad_aire_max_W=I_g_max_W_m2 * factor_aire,
            n_dias=n_dias,
        )
    if tipo_forzantes == "real":
        from core.proyecto import Tipologia

        tipologia = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
        if tipologia == Tipologia.CAJA:
            return _construir_forzantes_reales_caja(
                proyecto=proyecto,
                caudal_kg_s=caudal_kg_s,
                n_dias=n_dias,
                P_Pa=P_Pa,
                dias_consecutivos=dias_consecutivos,
            )
        return _construir_forzantes_reales(
            p3_eval=p3_eval,
            proyecto=proyecto,
            caudal_kg_s=caudal_kg_s,
            n_dias=n_dias,
            P_Pa=P_Pa,
            dias_consecutivos=dias_consecutivos,
        )
    raise ValueError(f"tipo_forzantes desconocido: {tipo_forzantes!r}")


def _resolver_fecha_dia(cfg, datos_local, anio):
    """Resuelve la fecha (date) del día de diseño según ``cfg.dia_analisis``.

    Mapeo único reutilizado por los builders de forzantes reales (CAJA y
    ARMARIO) para el modo "días reales consecutivos".
    """
    from datetime import date as _date

    from core.proyecto import DiaAnalisis

    if cfg.dia_analisis == DiaAnalisis.ESPECIFICO and cfg.fecha_especifica:
        return cfg.fecha_especifica
    if cfg.dia_analisis == DiaAnalisis.SOLSTICIO_VERANO:
        return _date(anio, 12, 21)
    if cfg.dia_analisis == DiaAnalisis.SOLSTICIO_INVIERNO:
        return _date(anio, 6, 21)
    if cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_MARZO:
        return _date(anio, 3, 21)
    if cfg.dia_analisis == DiaAnalisis.EQUINOCCIO_SEPTIEMBRE:
        return _date(anio, 9, 21)
    if cfg.dia_analisis == DiaAnalisis.MAS_CALUROSO:
        return (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmax().date()
    return (datos_local["T_amb_K"] - 273.15).resample("D").mean().idxmin().date()


def _forzantes_desde_slice(
    *,
    datos_slice,
    empl,
    camara,
    caudal_kg_s: float,
    T_sal_col_K,
    P_Pa: float,
) -> ForzantesAire:
    """Arma ForzantesAire desde un slice climático de 24·N h sin replicar.

    Construye T_amb/ω/v/I_eq/POA desde ``datos_slice`` y usa la ``T_sal_col_K``
    provista (T_amb en CAJA; salida del colector hora a hora en ARMARIO). Pasa
    la serie completa a ``armar_forzantes_aire`` por el camino sin replicación
    (modo "diario": n_reps=1, usa la serie tal cual aunque tenga 24·N puntos).

    ``I_g_W_m2`` e ``Q_rad_aire_W`` se computan con
    ``calculos.radiacion_camara.series_radiacion_camara`` (irradiancia
    equivalente por orientación de las caras translúcidas de ``camara``); si
    falla (p.ej. sin cubierta o datos insuficientes), cae a GHI horizontal
    sin aporte al aire (comportamiento histórico).
    """
    from calculos.radiacion_camara import series_radiacion_camara

    T_amb_K_arr = np.asarray(datos_slice["T_amb_K"], dtype=float)
    HR_arr = np.asarray(datos_slice["HR"], dtype=float)
    v_viento_arr = np.asarray(datos_slice["WS_ms"], dtype=float)
    try:
        I_g_serie, Q_rad_aire_serie = series_radiacion_camara(datos_slice, empl, camara)
        I_g_arr = np.asarray(I_g_serie, dtype=float)
        Q_rad_aire_arr = np.asarray(Q_rad_aire_serie, dtype=float)
    except Exception:
        I_g_arr = np.asarray(datos_slice["GHI_Wm2"], dtype=float)
        Q_rad_aire_arr = np.zeros_like(I_g_arr)
    try:
        from calculos.clima_calc import calcular_POA_horizonte

        I_g_POA_arr = np.asarray(calcular_POA_horizonte(datos_slice, empl), dtype=float)
    except Exception:
        I_g_POA_arr = None

    omega_amb_arr = np.array(
        [humedad_absoluta(float(hr), float(T), P_Pa) for hr, T in zip(HR_arr, T_amb_K_arr)],
        dtype=float,
    )

    # Paso temporal real del slice (fase 1b): sub-horario si el clima de trabajo
    # se resolvió a 15/5 min; 3600 s con clima horario.
    if len(datos_slice.index) > 1:
        dt_s = float((datos_slice.index[1] - datos_slice.index[0]).total_seconds())
    else:
        dt_s = 3600.0

    return armar_forzantes_aire(
        modo="diario",  # n_reps=1 → serie completa de 24·N sin replicar
        n_dias=1,
        T_salida_colector_K=np.asarray(T_sal_col_K, dtype=float),
        omega_ambiente=omega_amb_arr,
        m_dot_aire_seco_kg_s=caudal_kg_s,
        v_viento_ms=v_viento_arr,
        T_amb_K=T_amb_K_arr,
        I_g_W_m2=I_g_arr,
        I_g_POA_W_m2=I_g_POA_arr,
        Q_rad_aire_W=Q_rad_aire_arr,
        dt_s=dt_s,
        t0_utc=datos_slice.index[0] if len(datos_slice.index) else None,
    )


def _construir_forzantes_reales(
    *,
    p3_eval,
    proyecto,
    caudal_kg_s: float,
    n_dias: int,
    P_Pa: float = 101325.0,
    dias_consecutivos: bool = False,
) -> ForzantesAire:
    """Construye ForzantesAire desde el día de análisis real (P2 + P3).

    Args:
        p3_eval: Dict producido por P3 en modo 'diario'
            ({"modo": "diario", "r": {...}, "label": ...}). Su sub-dict `r`
            debe contener `horas` (timestamps) y `T_salida_C` (lista
            del mismo largo, con None en horas sin radiación).
        proyecto: Proyecto con `emplazamiento` y `clima.datos` no nulo.
        dias_consecutivos: Si True (modo multi-día), toma N días calendario
            consecutivos del clima desde el día de diseño y corre el colector
            sobre todo el horizonte (no usa ``p3_eval``).

    Si las series del colector tienen huecos (None por noche), se rellenan
    con T_amb local del clima.

    Raises:
        RuntimeError: Si `p3_eval` no es válido o si el clima no está cargado.
    """
    # --- Días reales consecutivos: corre el colector sobre N días del clima ---
    if dias_consecutivos and n_dias > 1:
        if proyecto is None or proyecto.clima is None or proyecto.clima.datos is None:
            raise RuntimeError("Para días reales consecutivos necesitas el clima cargado en P2.")
        if proyecto.colector is None:
            raise RuntimeError("Tipología ARMARIO sin colector configurado (P3).")
        from calculos.clima_calc import slice_n_dias_consecutivos
        from ui.p3_colector import _evaluar_diario

        empl = proyecto.emplazamiento
        cfg = proyecto.configuracion
        anio = proyecto.clima.anio
        datos_local = _datos_local_paso(proyecto)
        fecha_dia = _resolver_fecha_dia(cfg, datos_local, anio)
        datos_slice, _, _ = slice_n_dias_consecutivos(datos_local, fecha_dia, n_dias)
        if len(datos_slice) == 0:
            raise RuntimeError(f"Sin datos climáticos desde {fecha_dia} en el año {anio}.")
        # T_salida del colector hora a hora sobre el slice (reusa el evaluador de P3,
        # que itera cualquier rango). None de noche → se rellena con T_amb.
        ev = _evaluar_diario(proyecto.colector, datos_slice, empl)
        T_amb_slice = np.asarray(datos_slice["T_amb_K"], dtype=float)
        T_sal_col_K = np.array(
            [
                (float(t) + 273.15) if t is not None else T_amb_slice[i]
                for i, t in enumerate(ev["T_salida_C"])
            ],
            dtype=float,
        )
        return _forzantes_desde_slice(
            datos_slice=datos_slice,
            empl=empl,
            camara=proyecto.camara,
            caudal_kg_s=caudal_kg_s,
            T_sal_col_K=T_sal_col_K,
            P_Pa=P_Pa,
        )

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
    # Irradiancia equivalente al producto sobre las caras translúcidas de la
    # cámara (orientación propia, ver calculos/radiacion_camara.py). En
    # cámaras opacas el motor anula el término Q_rad sin coste; se computa
    # siempre para simplificar el wire-up. Fallback a GHI horizontal (sin
    # aporte al aire) si falla (p.ej. sin cubierta o datos insuficientes).
    from calculos.radiacion_camara import series_radiacion_camara

    try:
        I_g_serie, Q_rad_aire_serie = series_radiacion_camara(datos_dia, empl, proyecto.camara)
        I_g_arr = np.asarray(I_g_serie, dtype=float)
        Q_rad_aire_arr = np.asarray(Q_rad_aire_serie, dtype=float)
    except Exception:
        I_g_arr = np.asarray(datos_dia["GHI_Wm2"], dtype=float)
        Q_rad_aire_arr = np.zeros_like(I_g_arr)
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
        Q_rad_aire_W=Q_rad_aire_arr,
        dt_s=3600.0,
        t0_utc=datos_dia.index[0] if len(datos_dia.index) else None,
    )


def _construir_forzantes_reales_caja(
    *,
    proyecto,
    caudal_kg_s: float,
    n_dias: int,
    P_Pa: float = 101325.0,
    dias_consecutivos: bool = False,
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
    if proyecto is None or proyecto.clima is None or proyecto.clima.datos is None:
        raise RuntimeError(
            "Para usar forzantes reales en CAJA necesitas tener el clima cargado "
            "en P2 (descarga NASA POWER)."
        )

    empl = proyecto.emplazamiento
    cfg = proyecto.configuracion
    anio = proyecto.clima.anio
    datos_local = _datos_local_paso(proyecto)

    fecha_dia = _resolver_fecha_dia(cfg, datos_local, anio)

    # --- Días reales consecutivos: N días calendario desde el día de diseño ---
    if dias_consecutivos and n_dias > 1:
        from calculos.clima_calc import slice_n_dias_consecutivos

        datos_slice, _, _ = slice_n_dias_consecutivos(datos_local, fecha_dia, n_dias)
        if len(datos_slice) == 0:
            raise RuntimeError(f"Sin datos climáticos desde {fecha_dia} en el año {anio}.")
        # CAJA: T_salida_colector(t) = T_amb(t) sobre todo el slice.
        return _forzantes_desde_slice(
            datos_slice=datos_slice,
            empl=empl,
            camara=proyecto.camara,
            caudal_kg_s=caudal_kg_s,
            T_sal_col_K=np.asarray(datos_slice["T_amb_K"], dtype=float),
            P_Pa=P_Pa,
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
    from calculos.radiacion_camara import series_radiacion_camara

    try:
        I_g_serie, Q_rad_aire_serie = series_radiacion_camara(datos_dia, empl, proyecto.camara)
        I_g_arr = np.asarray(I_g_serie, dtype=float)
        Q_rad_aire_arr = np.asarray(Q_rad_aire_serie, dtype=float)
    except Exception:
        I_g_arr = np.asarray(datos_dia["GHI_Wm2"], dtype=float)
        Q_rad_aire_arr = np.zeros_like(I_g_arr)
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

    if len(datos_dia.index) > 1:
        dt_s = float((datos_dia.index[1] - datos_dia.index[0]).total_seconds())
    else:
        dt_s = 3600.0
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
        Q_rad_aire_W=Q_rad_aire_arr,
        dt_s=dt_s,
        t0_utc=datos_dia.index[0] if len(datos_dia.index) else None,
    )


def _construir_forzantes_ventana(
    *,
    proyecto,
    caudal_kg_s: float,
    P_Pa: float = 101325.0,
) -> ForzantesAire:
    """Construye ForzantesAire sobre la ventana de producción de P1 (mejora 35).

    En tipología CAJA/ARMARIO, el modo VENTANA es un **multidía real**: el
    horizonte es el lapso ``[ventana_inicio, ventana_fin]`` con clima horario
    real de NASA POWER. Reusa ``_forzantes_desde_slice`` (mismo camino que
    "días reales consecutivos"): corre el colector hora a hora sobre el slice
    para ARMARIO (día y noche; las horas sin sol caen a T_amb) o toma
    ``T_sal_col(t) = T_amb(t)`` para CAJA.

    Raises:
        RuntimeError: Si la ventana no está definida, el clima no está cargado,
            o no hay datos para el lapso en el año climático descargado.
    """
    from datetime import date as _date

    from core.proyecto import Tipologia

    cfg = proyecto.configuracion
    inicio = getattr(cfg, "ventana_inicio", None)
    fin = getattr(cfg, "ventana_fin", None)
    if inicio is None or fin is None:
        raise RuntimeError("Definí la ventana de producción [inicio, fin] en P1.")
    if proyecto.clima is None or proyecto.clima.datos is None:
        raise RuntimeError(
            "La ventana de producción necesita clima real cargado en P2 (NASA POWER)."
        )

    empl = proyecto.emplazamiento
    anio = proyecto.clima.anio
    datos_local = _datos_local_paso(proyecto)
    n_dias = max(1, (fin - inicio).days)
    # La ventana se mapea al año climático descargado (mismo criterio que P7).
    inicio_anio = _date(anio, inicio.month, inicio.day)

    from calculos.clima_calc import slice_n_dias_consecutivos

    datos_slice, _, _ = slice_n_dias_consecutivos(datos_local, inicio_anio, n_dias)
    if len(datos_slice) == 0:
        raise RuntimeError(
            f"Sin datos climáticos para la ventana desde {inicio_anio} en el año {anio}."
        )

    T_amb_slice = np.asarray(datos_slice["T_amb_K"], dtype=float)
    es_caja = getattr(cfg, "tipologia", None) == Tipologia.CAJA
    if es_caja or proyecto.colector is None:
        T_sal_col_K = T_amb_slice
    else:
        from ui.p3_colector import _evaluar_diario

        ev = _evaluar_diario(proyecto.colector, datos_slice, empl)
        T_sal_col_K = np.array(
            [
                (float(t) + 273.15) if t is not None else T_amb_slice[i]
                for i, t in enumerate(ev["T_salida_C"])
            ],
            dtype=float,
        )

    return _forzantes_desde_slice(
        datos_slice=datos_slice,
        empl=empl,
        camara=proyecto.camara,
        caudal_kg_s=caudal_kg_s,
        T_sal_col_K=T_sal_col_K,
        P_Pa=P_Pa,
    )


def _T_amb_ref_K(proyecto) -> float:
    """Temperatura ambiente de referencia para fijar el caudal másico [K].

    El caudal másico del banco se fija con la densidad del aire que **entra** al
    colector, que es el ambiente. Usa la media anual del clima si está cargado;
    si no, 20 °C, que para este uso (proponer un caudal) mueve el resultado
    menos que el redondeo del widget.
    """
    datos = getattr(getattr(proyecto, "clima", None), "datos", None)
    if datos is not None and "T_amb_K" in getattr(datos, "columns", []):
        try:
            T_media = float(np.nanmean(np.asarray(datos["T_amb_K"], dtype=float)))
            if np.isfinite(T_media) and T_media > 0:
                return T_media
        except (TypeError, ValueError):
            pass
    return 293.15


def _P_ref_Pa(proyecto) -> float:
    """Presión del sitio [Pa], con caída a la estándar si no se puede derivar."""
    try:
        P_Pa, _origen = presion_representativa_proyecto(proyecto)
        return float(P_Pa)
    except Exception:
        return 101325.0


def _seguir_colector_default(flujo_prev, m_col: float) -> bool:
    """¿El checkbox "seguir al colector" arranca activado?

    Lee la **decisión persistida** (``ConfiguracionFlujo.seguir_caudal_colector``)
    y no la deduce de los números. Deducirla era frágil: el caudal del banco es
    ``v·A·n·ρ(T_amb, P)``, así que cambiar el año de clima mueve ρ unas décimas
    de por mil y el caudal guardado dejaba de coincidir → la app concluía que el
    usuario había desacoplado los caudales a propósito y destildaba el checkbox
    sola, justo al cargar un proyecto (S58).

    El fallback por coincidencia numérica se conserva **solo** para snapshots
    anteriores al campo, donde no hay decisión que leer, y con una tolerancia
    del 2 % en vez de 0.01 %.
    """
    decision = getattr(flujo_prev, "seguir_caudal_colector", None)
    if decision is not None:
        return bool(decision)
    caudal_prev = float(getattr(flujo_prev, "caudal_masico_kg_s", 0.0))
    if abs(caudal_prev - _CAUDAL_FLUJO_DEFAULT_KG_S) < 1e-9:
        return True
    return abs(caudal_prev - m_col) <= 0.02 * max(m_col, 1e-9)


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
            t("p4.graficas.panel_x"),
            t("p4.graficas.panel_temps"),
            t("p4.graficas.panel_hr"),
            t("p4.graficas.panel_evap"),
        ),
    )

    # Panel 1: X(t)
    fig.add_trace(
        go.Scatter(
            x=list(t_h),
            y=list(res.X_prod_kg_kg),
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            name=t("p4.graficas.curva_x"),
        ),
        row=1,
        col=1,
    )
    fig.add_hline(
        y=X_obj,
        line=dict(color="red", dash="dot", width=1.5),
        annotation_text=t("p4.graficas.x_obj", v=X_obj),
        row=1,
        col=1,
    )
    if res.status == "X_obj_alcanzado" and res.t_secado_s is not None:
        t_sec_h = res.t_secado_s / 3600.0
        fig.add_vline(
            x=t_sec_h,
            line=dict(color="orange", dash="dashdot", width=1.5),
            annotation_text=t("p4.graficas.t_marca", v=t_sec_h),
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
            name=t("p4.graficas.t_producto"),
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
            name=t("p4.graficas.t_aire"),
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
            name=t("p4.graficas.t_pared_int"),
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
            name=t("p4.graficas.t_pared_ext"),
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
            name=t("p4.graficas.hr_flujo"),
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
            name=t("p4.graficas.m_dot"),
        ),
        row=4,
        col=1,
    )
    fig.add_hline(y=0.0, line=dict(color="gray", dash="solid", width=0.8), row=4, col=1)

    fig.update_yaxes(title_text=t("p4.graficas.eje_x_ms"), rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text=t("p4.graficas.eje_t"), row=2, col=1)
    fig.update_yaxes(title_text=t("p4.graficas.eje_hr"), range=[0, 105], row=3, col=1)
    fig.update_yaxes(title_text=t("p4.graficas.eje_m_dot"), row=4, col=1)
    fig.update_xaxes(title_text=t("p4.graficas.eje_tiempo"), row=4, col=1)
    fig.update_layout(
        title_text=t("p4.graficas.titulo_td", prod=prod_id),
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


def _obtener_resultado_camara(session_state) -> tuple[str | None, object | None, dict | None]:
    """Devuelve (tipo, resultado, meta) extraído de session_state.

    tipo ∈ {"termodinamico_horizonte", None}.
    """
    horizonte = session_state.get("p4_horizonte_resultado")
    if horizonte is not None:
        return "termodinamico_horizonte", horizonte, session_state.get("p4_horizonte_meta")
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
        f"  Pendiente techo   : {g.pendiente_techo_deg:.1f}°  (cae hacia: {g.cara_caida_techo})",
        f"  Acimut cámara     : {g.acimut_camara_deg:.1f}° Duffie",
        "",
        "CONSTRUCCIÓN",
        "  Material vidriado : " + (cn.cubierta_translucida_id or "(opaca)"),
    ]
    if cn.cubierta_translucida_id is not None:
        lines.append("  Caras translúcidas: " + ", ".join(cn.caras_translucidas_activas()))
    if cn.cubierta_translucida_id is not None and cn.A_rad_m2 is not None:
        lines.append(f"  A_rad             : {cn.A_rad_m2:.4f} m²")
    if cn.cubierta_translucida_id is not None and cn.cubierta_translucida_espesor_m is not None:
        lines.append(f"  Espesor techo     : {cn.cubierta_translucida_espesor_m * 1000:.1f} mm")
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
    if cam.carros is not None:
        lines += [
            "",
            "CARROS (disposición industrial)",
            f"  N° carros           : {cam.carros.n_carros}",
            f"  Bandejas por carro  : {cam.carros.bandejas_por_carro}",
            f"  Bandejas totales    : {cam.carros.n_bandejas_total} (derivado)",
        ]
    if cam.tunel is not None:
        lines += [
            "",
            "TÚNEL SEMICONTINUO (contracorriente)",
            f"  N° columnas (zonas) : {cam.tunel.n_zonas}",
            f"  Cadencia de avance  : {cam.tunel.intervalo_avance_h:.1f} h",
            f"  Residencia total    : {cam.tunel.residencia_total_h:.1f} h "
            f"(≈ {cam.tunel.residencia_total_h / 24.0:.1f} días)",
        ]
    lines += [
        "",
        "PRODUCTO Y CARGA",
        f"  Producto           : {c.producto_id}",
        f"  Categoría          : {datos_prod.get('categoria', '—')}",
        f"  Masa total         : {c.masa_total_kg:.2f} kg",
        f"  X inicial          : {c.humedad_inicial_X:.4f} kg/kg ms",
        f"  X objetivo         : {c.humedad_objetivo_X:.4f} kg/kg ms",
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
            _tipo_hz = meta.get("horizonte_tipo")
            _hz_extra = f", {_tipo_hz}" if _tipo_hz and int(meta.get("n_dias", 1)) > 1 else ""
            lines.append(
                f"  Horizonte          : {meta.get('n_dias')} día(s){_hz_extra}, "
                f"forzantes={meta.get('modo_forzantes')}"
            )
        lines += [
            f"  Status             : {resumen['status']}",
            f"  Tiempo simulación  : {resumen.get('t_simulacion_h', 0):.2f} h",
            "  Tiempo de secado   : "
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
        pendiente_techo_deg=float(g_d.get("pendiente_techo_deg", 0.0)),
        acimut_camara_deg=float(g_d.get("acimut_camara_deg", 180.0)),
        cara_caida_techo=g_d.get("cara_caida_techo", "frente"),
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
    caras_d = cn_d.get("caras_translucidas") or {}
    construccion = ConstruccionCamara(
        cubierta_translucida_id=cn_d.get("cubierta_translucida_id"),
        A_rad_m2=(float(cn_d["A_rad_m2"]) if cn_d.get("A_rad_m2") is not None else None),
        cubierta_translucida_espesor_m=(
            float(cn_d["cubierta_translucida_espesor_m"])
            if cn_d.get("cubierta_translucida_espesor_m") is not None
            else None
        ),
        caras_translucidas=CarasTranslucidas(
            techo=bool(caras_d.get("techo", True)),
            frente=bool(caras_d.get("frente", False)),
            atras=bool(caras_d.get("atras", False)),
            lateral_izq=bool(caras_d.get("lateral_izq", False)),
            lateral_der=bool(caras_d.get("lateral_der", False)),
        ),
        absortancia_interior=float(cn_d.get("absortancia_interior", 0.85)),
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
        # Back-compat: los snapshots anteriores a S58 no traen la decisión. Se
        # asume que sí seguía al colector, que es el default de la app.
        seguir_caudal_colector=bool(f_d.get("seguir_caudal_colector", True)),
    )

    # Túnel semicontinuo (opcional; back-compat: ausente → None).
    tun_d = data.get("tunel")
    tunel = (
        ConfiguracionTunel(
            n_zonas=int(tun_d["n_zonas"]),
            intervalo_avance_h=float(tun_d["intervalo_avance_h"]),
        )
        if tun_d
        else None
    )

    # Carros con bandejas (S41; back-compat: ausente → None).
    car_d = data.get("carros")
    carros = (
        ConfiguracionCarros(
            n_carros=int(car_d["n_carros"]),
            bandejas_por_carro=int(car_d["bandejas_por_carro"]),
            largo_carro_m=(
                float(car_d["largo_carro_m"]) if car_d.get("largo_carro_m") is not None else None
            ),
            ancho_carro_m=(
                float(car_d["ancho_carro_m"]) if car_d.get("ancho_carro_m") is not None else None
            ),
        )
        if car_d
        else None
    )

    return Camara(
        geometria=geometria,
        construccion=construccion,
        bandejas=bandejas,
        flujo=flujo,
        carga_producto=carga,
        modo_calculo=data.get("modo_calculo", "termodinamico"),
        tunel=tunel,
        carros=carros,
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
            "pendiente_techo_deg": g.pendiente_techo_deg,
            "acimut_camara_deg": g.acimut_camara_deg,
            "cara_caida_techo": g.cara_caida_techo,
            "alto_menor_m": g.alto_menor_m,
            "alto_mayor_m": g.alto_mayor_m,
            "A_techo_geom_m2": g.A_techo_geom_m2,
        },
        "construccion": {
            "cubierta_translucida_id": cn.cubierta_translucida_id,
            "cubierta_translucida_props": (
                dict(_cat.CUBIERTAS.get(cn.cubierta_translucida_id, {}))
                if cn.cubierta_translucida_id
                else None
            ),
            "A_rad_m2": cn.A_rad_m2,
            "cubierta_translucida_espesor_m": cn.cubierta_translucida_espesor_m,
            "caras_translucidas": {
                "techo": cn.caras_translucidas.techo,
                "frente": cn.caras_translucidas.frente,
                "atras": cn.caras_translucidas.atras,
                "lateral_izq": cn.caras_translucidas.lateral_izq,
                "lateral_der": cn.caras_translucidas.lateral_der,
            },
            "absortancia_interior": cn.absortancia_interior,
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
            "seguir_caudal_colector": f.seguir_caudal_colector,
        },
        "tunel": (
            {
                "n_zonas": cam.tunel.n_zonas,
                "intervalo_avance_h": cam.tunel.intervalo_avance_h,
                "tiempo_residencia_total_h": cam.tunel.residencia_total_h,
            }
            if cam.tunel is not None
            else None
        ),
        "carros": (
            {
                "n_carros": cam.carros.n_carros,
                "bandejas_por_carro": cam.carros.bandejas_por_carro,
                "largo_carro_m": cam.carros.largo_carro_m,
                "ancho_carro_m": cam.carros.ancho_carro_m,
                "n_bandejas_total": cam.carros.n_bandejas_total,
            }
            if cam.carros is not None
            else None
        ),
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
        st.info(t("p4.anual.sin_clima"))
        return
    tz_local = proyecto.emplazamiento.zona_horaria if proyecto.emplazamiento is not None else "UTC"
    meses = meses_cubiertos(proyecto.clima.datos, tz_local)
    if len(meses) < 12:
        st.warning(t("p4.anual.clima_incompleto", n_meses=len(meses)))
        return
    if proyecto.colector is None:
        st.warning(t("p4.anual.sin_colector"))
        return

    st.markdown(t("p4.anual.titulo"))
    st.caption(t("p4.anual.caption"))

    # Política de recarga: cuándo se carga el lote siguiente. Sin esto el modelo
    # recarga en el instante exacto en que el anterior terminó —a las 3 AM si
    # tocó— y sobreestima la producción.
    with st.expander(t("p4.anual.recarga.titulo"), expanded=False):
        st.caption(t("p4.anual.recarga.caption"))
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            recarga_activa = st.checkbox(
                t("p4.anual.recarga.activa.label"),
                value=True,
                key="p4_anual_recarga_activa",
                help=t("p4.anual.recarga.activa.help"),
            )
        with rc2:
            # time_input y no number_input: la hora del día se lee "08:00", no
            # "8.00". Se convierte a horas decimales para el motor, que razona
            # en horas desde el inicio del lapso.
            _hora_widget = st.time_input(
                t("p4.anual.recarga.hora.label"),
                value=_time(8, 0),
                step=1800,  # 30 min
                disabled=not recarga_activa,
                key="p4_anual_recarga_hora",
                help=t("p4.anual.recarga.hora.help"),
            )
            hora_carga = float(_hora_widget.hour) + float(_hora_widget.minute) / 60.0
        with rc3:
            maniobra = st.number_input(
                t("p4.anual.recarga.maniobra.label"),
                min_value=0.0,
                max_value=12.0,
                value=1.0,
                step=0.5,
                disabled=not recarga_activa,
                key="p4_anual_recarga_maniobra",
                help=t("p4.anual.recarga.maniobra.help"),
            )
        if not recarga_activa:
            st.warning(t("p4.anual.recarga.aviso_cota"))

        # Decisión de cargar: un operador no llena el secador un día que viene
        # nublado. Sin esto el modelo carga siempre e infla los lotes que se
        # arrastran sin terminar (S58).
        st.divider()
        pc1, pc2 = st.columns(2)
        with pc1:
            exigir_pronostico = st.checkbox(
                t("p4.anual.pronostico.activo.label"),
                value=True,
                key="p4_anual_pronostico_activo",
                help=t("p4.anual.pronostico.activo.help"),
            )
        with pc2:
            umbral_pronostico = st.number_input(
                t("p4.anual.pronostico.umbral.label"),
                min_value=0.0,
                max_value=40.0,
                value=8.0,
                step=1.0,
                disabled=not exigir_pronostico,
                key="p4_anual_pronostico_umbral",
                help=t("p4.anual.pronostico.umbral.help"),
            )
        if exigir_pronostico:
            st.caption(t("p4.anual.pronostico.nota_perfecto"))

    calcular_anual = st.button(
        t("p4.anual.calcular.label"),
        type="primary",
        key="p4_anual_calcular",
        help=t("p4.anual.calcular.help"),
    )

    if calcular_anual:
        # Construir la cámara desde los widgets y forzar modo termodinámico.
        try:
            camara = camara_builder(modo_calculo_override="termodinamico")
        except (ValueError, NotImplementedError) as exc:
            st.error(t("p4.anual.error_config", exc=exc))
            return
        proyecto.camara = camara

        try:
            politica = PoliticaRecarga(
                activa=bool(recarga_activa),
                hora_carga_h=float(hora_carga),
                maniobra_h=float(maniobra),
                exigir_pronostico=bool(exigir_pronostico),
                umbral_pronostico_MJ_m2=float(umbral_pronostico),
            )
        except ValueError as exc:
            st.error(t("p4.anual.error", exc=exc))
            return

        with st.spinner(t("p4.anual.spinner")):
            try:
                res_anual = simular_anual(proyecto, proyecto.clima.datos, politica_recarga=politica)
            except ValueError as exc:
                st.error(t("p4.anual.error", exc=exc))
                return
            except Exception as exc:
                st.error(t("p4.anual.error_calculo", exc=exc))
                return
        # Huella de las entradas + política usada: P7 y el reporte muestran este
        # resultado sin recalcularlo, así que necesitan poder detectar que quedó
        # viejo (S58). Sin esto, cambiar P5 después de correr el año dejaba a P7
        # mostrando un año sin auxiliar como si fuera el actual.
        registrar_anual(st.session_state, res_anual, proyecto, politica)
        st.success(t("p4.anual.exito"))

    res_anual: ResultadosAnual | None = st.session_state.get("p4_resultado_anual")
    if res_anual is None:
        return

    if res_anual.advertencias:
        for msg in res_anual.advertencias:
            st.warning(f"⚠️ {msg}")  # i18n: exento (mensaje de calculos/, queda ES)

    st.markdown(t("p4.anual.resumen"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        t("p4.anual.producto_seco.label"),
        f"{res_anual.masa_seca_anual_kg:.0f} kg",
        help=t("p4.anual.producto_seco.help"),
    )
    col2.metric(
        t("p4.anual.agua_evaporada.label"),
        f"{res_anual.masa_evaporada_anual_kg:.0f} kg",
        help=t("p4.anual.agua_evaporada.help"),
    )
    col3.metric(
        t("p4.anual.lotes.label"),
        f"{res_anual.n_lotes_completos}",
        delta=(
            t("p4.anual.lotes.frustrados", n=res_anual.n_lotes_frustrados)
            if res_anual.n_lotes_frustrados
            else None
        ),
        delta_color="inverse",
        help=t("p4.anual.lotes.help"),
    )
    col4.metric(
        t("p4.anual.duracion.label"),
        (
            f"{res_anual.duracion_media_h:.0f} h"
            if res_anual.duracion_media_h is not None
            else "—"  # i18n: exento (marcador de dato ausente)
        ),
        help=t("p4.anual.duracion.help"),
    )
    # El operador del modelo decide con pronóstico perfecto: el resultado es la
    # cota superior de la buena decisión. Decirlo acá, junto a los números, evita
    # que se lean como una promesa.
    if res_anual.dias_salteados_pronostico > 0:
        st.caption(t("p4.anual.dias_salteados", n=res_anual.dias_salteados_pronostico))
    st.caption(t("p4.anual.cota_superior"))


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 4 — Cámara de Secado."""
    st.header(t("p4.header"))
    boton_manual(SLUG_POR_SECCION["p4"])

    proyecto = st.session_state.proyecto

    # Aplicar cambios pendientes a widgets (calibración → "aplicar óptimo"). Se fija
    # el session_state ANTES de instanciar los number_input, que es la forma robusta
    # de actualizar un widget desde un botón de otra sección.
    _pend = st.session_state.pop("_p4_pending_widget", None)
    if _pend:
        for _k, _v in _pend.items():
            st.session_state[_k] = _v

    # Detectar tipología temprano: condiciona defaults de cubierta y T_op.
    from core.proyecto import SubtipoGranEscala, Tipologia

    _cfg_actual = getattr(proyecto, "configuracion", None)
    _tipologia_actual = getattr(_cfg_actual, "tipologia", None)
    es_caja_pre = _tipologia_actual == Tipologia.CAJA
    if es_caja_pre:
        st.info(t("p4.info_caja"))

    # Subtipo de gran escala: SEMICONTINUO habilita la topología de túnel a
    # contracorriente (N columnas con avance por cadencia). BATCH (y las demás
    # tipologías) usan la topología de bandejas clásica.
    _subtipo_actual = getattr(_cfg_actual, "subtipo_gran_escala", SubtipoGranEscala.BATCH)
    es_gran_escala = _tipologia_actual == Tipologia.GRAN_ESCALA
    # Modo Ventana de producción: el horizonte de la vista previa de cámara es el
    # lapso [inicio, fin] de P1 con clima real horario. Vale para TODAS las
    # tipologías (incl. gran escala): P7 sigue siendo la fuente de verdad —con su
    # pipeline de cascada para el túnel—, pero la previa de P4 no tiene por qué
    # degradarse a un día sintético cuando hay clima real de la ventana.
    usar_ventana = getattr(_cfg_actual, "modo_analisis", None) == ModoAnalisis.VENTANA
    es_semicontinuo = (
        _tipologia_actual == Tipologia.GRAN_ESCALA
        and _subtipo_actual == SubtipoGranEscala.SEMICONTINUO
    )
    if es_semicontinuo:
        st.info(t("p4.info_semicontinuo"))

    # -----------------------------------------------------------------------
    # Cargar configuración guardada (.json)
    # -----------------------------------------------------------------------
    with st.expander(t("p4.cargar.titulo"), expanded=False):
        from ui.componentes.serializacion import (
            limpiar_session_state_prefijo,
            parsear_json_seccion,
        )

        archivo = st.file_uploader(
            t("p4.cargar.uploader"),
            type=["json"],
            key="p4_cargar_json",
        )
        if archivo is not None:
            data, err = parsear_json_seccion(archivo, "camara")
            if err:
                st.error(f"❌ {err}")  # i18n: exento (mensaje de serializacion, F4)
            else:
                try:
                    cam_cargada = _from_json_camara(data)
                except (KeyError, ValueError, TypeError) as exc:
                    st.error(t("p4.cargar.error_reconstruccion", exc=exc))
                else:
                    proyecto.camara = cam_cargada
                    # Limpiar widgets + resultados viejos de la cámara
                    # y del horizonte que dependa de ella.
                    n_borr = limpiar_session_state_prefijo(st.session_state, "p4_")
                    limpiar_session_state_prefijo(st.session_state, "cam_")
                    st.session_state.pop("p4_cargar_json", None)
                    st.success(t("p4.cargar.exito", n=n_borr))
                    st.rerun()

    # -----------------------------------------------------------------------
    # Sección A: Producto
    # -----------------------------------------------------------------------
    st.subheader(t("p4.producto.titulo"))

    productos_disp = _productos_disponibles()
    if not productos_disp:
        st.error(t("p4.producto.sin_productos"))
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
        t("p4.producto.label"),
        options=labels_disponibles,
        index=idx_default,
        help=t("p4.producto.help"),
    )
    prod_id = ids_disponibles[labels_disponibles.index(prod_sel_label)]
    datos_prod = catalogo.PRODUCTOS[prod_id]
    props = datos_prod.get("propiedades_basicas") or {}

    col1, col2 = st.columns(2)
    with col1:
        # Humedad inicial: default desde catálogo
        X_ini_default = float(props.get("humedad_inicial_tipica", 4.0))
        if proyecto.camara is not None and proyecto.camara.carga_producto.producto_id == prod_id:
            X_ini_default = proyecto.camara.carga_producto.humedad_inicial_X

        X_ini = st.number_input(
            t("p4.producto.x_ini.label"),
            min_value=0.01,
            max_value=50.0,
            value=X_ini_default,
            step=0.1,
            format="%.2f",
            help=t("p4.producto.x_ini.help"),
        )

        X_obj = st.number_input(
            t("p4.producto.x_obj.label"),
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
            help=t("p4.producto.x_obj.help"),
        )

        masa_kg = st.number_input(
            t("p4.producto.masa"),
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
        # El selector de "modelo cinético de capa fina" se eliminó en S38
        # (motor único: termodinámico). El campo modelo_capa_fina quedó
        # vestigial; se preserva el valor previo para round-trip de snapshots.
        modelo_cf = (
            proyecto.camara.carga_producto.modelo_capa_fina
            if proyecto.camara is not None
            else "logaritmico"
        )

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
            st.success(t("p4.producto.gab_ok"))
        elif X_eq_fallback is not None:
            st.warning(t("p4.producto.gab_fallback", x=X_eq_fallback))

    # -----------------------------------------------------------------------
    # Sección B: Geometría y construcción
    # -----------------------------------------------------------------------
    with st.expander(t("p4.geometria.titulo"), expanded=False):
        with st.expander(t("p4.geometria.esquema_titulo"), expanded=False):
            mostrar_esquema(
                "camara_dimensiones",
                caption=t("p4.geometria.esquema_caption"),
            )
        c1, c2, c3 = st.columns(3)
        geo_prev = proyecto.camara.geometria if proyecto.camara is not None else GeometriaCamara()
        largo = c1.number_input(
            t("p4.geometria.largo"),
            min_value=0.1,
            max_value=20.0,
            value=geo_prev.largo_m,
            step=0.05,
            format="%.2f",
        )
        ancho = c2.number_input(
            t("p4.geometria.ancho"),
            min_value=0.1,
            max_value=10.0,
            value=geo_prev.ancho_m,
            step=0.05,
            format="%.2f",
        )
        alto = c3.number_input(
            t("p4.geometria.alto"),
            min_value=0.1,
            max_value=5.0,
            value=geo_prev.alto_m,
            step=0.05,
            format="%.2f",
        )
        vol = largo * ancho * alto
        st.caption(t("p4.geometria.volumen", vol=vol, area=largo * ancho))

        st.markdown(t("p4.geometria.orientacion_titulo"))
        st.caption(t("p4.geometria.orientacion_caption"))
        oc1, oc2, oc3 = st.columns(3)
        pendiente_techo = oc1.number_input(
            t("p4.geometria.pendiente_techo.label"),
            min_value=0.0,
            max_value=60.0,
            value=float(geo_prev.pendiente_techo_deg),
            step=1.0,
            format="%.1f",
            help=t("p4.geometria.pendiente_techo.help"),
        )
        acimut_camara_ui360 = oc2.number_input(
            t("p4.geometria.acimut.label"),
            min_value=0.0,
            max_value=360.0,
            value=float(acimut_duffie_a_ui360(geo_prev.acimut_camara_deg)),
            step=1.0,
            format="%.1f",
            help=t("p4.geometria.acimut.help"),
        )
        _caida_keys = ["frente", "atras", "lateral_izq", "lateral_der"]
        cara_caida_sel = oc3.selectbox(
            t("p4.geometria.cara_caida.label"),
            options=_caida_keys,
            format_func=lambda k: t(f"p4.geometria.cara_caida.{k}"),
            index=(
                _caida_keys.index(geo_prev.cara_caida_techo)
                if geo_prev.cara_caida_techo in _caida_keys
                else 0
            ),
            help=t("p4.geometria.cara_caida.help"),
        )
        acimut_camara_duffie = acimut_ui360_a_duffie(acimut_camara_ui360)
        _geo_preview: Optional[GeometriaCamara] = None
        try:
            _geo_preview = GeometriaCamara(
                largo_m=largo,
                ancho_m=ancho,
                alto_m=alto,
                pendiente_techo_deg=pendiente_techo,
                acimut_camara_deg=acimut_camara_duffie,
                cara_caida_techo=cara_caida_sel,
            )
            st.caption(
                t(
                    "p4.geometria.preview_techo",
                    menor=_geo_preview.alto_menor_m,
                    mayor=_geo_preview.alto_mayor_m,
                    area=_geo_preview.A_techo_geom_m2,
                    pvlib=acimut_duffie_a_pvlib(acimut_camara_duffie),
                )
            )
        except ValueError as err:
            st.error(f"⚠️ {err}")  # i18n: exento (mensaje de core/, queda ES)

        cons_prev = (
            proyecto.camara.construccion if proyecto.camara is not None else ConstruccionCamara()
        )
        _label_opaca = t("p4.vidriado.opaca")
        opciones_cubierta = [_label_opaca] + list(catalogo.CUBIERTAS.keys())
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
            t("p4.vidriado.material.label"),
            options=opciones_cubierta,
            index=idx_cub_default,
            format_func=lambda k: t_catalogo(catalogo.CUBIERTAS.get(k, {}), default=k),
            help=t("p4.vidriado.material.help"),
        )
        cubierta_id_sel: Optional[str] = (
            None if cubierta_sel == opciones_cubierta[0] else cubierta_sel
        )
        espesor_techo_m_sel: Optional[float] = None
        caras_translucidas_sel = CarasTranslucidas(techo=False)
        if cubierta_id_sel is not None:
            tau_info = catalogo.CUBIERTAS[cubierta_id_sel].get("transmitancia_solar", 0.85)
            st.caption(t("p4.vidriado.tau", v=float(tau_info)))
            # Espesor del vidriado (mejora 33), único para todas las caras. Para
            # el alveolar se ofrecen las medidas de mercado del mapa k(espesor)
            # del catálogo; el espesor entra al balance como pérdida conductiva
            # (U = k_efectivo/espesor en serie con films), ver camara_calc.
            mapa_k_techo = catalogo.CUBIERTAS.get(cubierta_id_sel, {}).get(
                "k_efectivo_por_espesor_mm"
            )
            opciones_techo_mm = (
                [(float(mm), f"{float(mm):.0f} mm") for mm in sorted(mapa_k_techo)]
                if mapa_k_techo
                else None
            )
            esp_techo_prev_m = cons_prev.cubierta_translucida_espesor_m or 0.006
            espesor_techo_mm = selector_espesor_mm(
                t("p4.vidriado.espesor"),
                esp_techo_prev_m,
                key="p4_esp_techo",
                opciones_mm=opciones_techo_mm,
                min_mm=1.0,
                max_mm=40.0,
                step=0.5,
            )
            espesor_techo_m_sel = espesor_techo_mm / 1000.0
            if mapa_k_techo:
                k_techo_eff = mapa_k_techo.get(int(round(espesor_techo_mm)))
                if k_techo_eff:
                    st.caption(t("p4.vidriado.k_efectivo", v=float(k_techo_eff)))

            st.markdown(t("p4.vidriado.caras_titulo"))
            st.caption(t("p4.vidriado.caras_caption"))
            caras_prev = (
                cons_prev.caras_translucidas
                if cons_prev.cubierta_translucida_id is not None
                else CarasTranslucidas()
            )
            tc1, tc2, tc3, tc4, tc5 = st.columns(5)
            techo_activo = tc1.checkbox(t("p4.vidriado.cara_techo"), value=caras_prev.techo)
            frente_activo = tc2.checkbox(t("p4.vidriado.cara_frente"), value=caras_prev.frente)
            atras_activo = tc3.checkbox(t("p4.vidriado.cara_atras"), value=caras_prev.atras)
            lateral_izq_activo = tc4.checkbox(
                t("p4.vidriado.cara_lat_izq"), value=caras_prev.lateral_izq
            )
            lateral_der_activo = tc5.checkbox(
                t("p4.vidriado.cara_lat_der"), value=caras_prev.lateral_der
            )
            caras_translucidas_sel = CarasTranslucidas(
                techo=techo_activo,
                frente=frente_activo,
                atras=atras_activo,
                lateral_izq=lateral_izq_activo,
                lateral_der=lateral_der_activo,
            )
            if not any(
                [techo_activo, frente_activo, atras_activo, lateral_izq_activo, lateral_der_activo]
            ):
                st.warning(t("p4.vidriado.sin_caras"))
                if es_caja_pre:
                    st.error(t("p4.vidriado.caja_sin_caras"))
            elif _geo_preview is not None:
                _caras_geom_prev = _geo_preview.caras()
                _col_cara = t("p4.vidriado.preview.cara")
                _col_area = t("p4.vidriado.preview.area")
                _col_incl = t("p4.vidriado.preview.inclinacion")
                _col_acim = t("p4.vidriado.preview.acimut")
                _col_transl = t("p4.vidriado.preview.translucida")
                _preview_rows = [
                    {
                        _col_cara: (
                            t(f"p4.geometria.cara_caida.{nombre}", default=nombre)
                            if nombre != "techo"
                            else t("p4.vidriado.cara_techo")
                        ),
                        _col_area: round(cara.area_m2, 3),
                        _col_incl: round(cara.tilt_deg, 1),
                        _col_acim: round(acimut_duffie_a_ui360(cara.acimut_duffie_deg), 1),
                        _col_transl: getattr(caras_translucidas_sel, nombre),
                    }
                    for nombre, cara in _caras_geom_prev.items()
                ]
                st.dataframe(_preview_rows, hide_index=True, width="stretch")
        elif es_caja_pre:
            st.error(t("p4.vidriado.caja_sin_techo"))
        # --- Materiales de la cámara: pared simple o compuesta ---
        st.markdown(t("p4.materiales.titulo"))
        st.caption(t("p4.materiales.caption"))

        fondos_keys = list(catalogo.FONDOS.keys())
        aislantes_keys = list(catalogo.AISLANTES.keys())

        # Estado previo: detectar si era simple o compuesta
        es_compuesta_prev = cons_prev.pared.es_compuesta
        tipo_pared = st.radio(
            t("p4.materiales.tipo_pared.label"),
            options=["simple", "compuesta"],
            index=0 if not es_compuesta_prev else 1,
            horizontal=True,
            format_func=lambda k: t(f"p4.materiales.tipo_pared.{k}"),
            help=t("p4.materiales.tipo_pared.help"),
        )

        if tipo_pared == "simple":
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
                t("p4.materiales.catalogo.label"),
                options=["fondos", "aislantes"],
                index=0 if cat_prev == "fondos" else 1,
                key="p4_pared_simple_cat",
                help=t("p4.materiales.catalogo.help"),
            )
            opciones_mat = fondos_keys if cat_sel == "fondos" else aislantes_keys
            _cat_dict = catalogo.FONDOS if cat_sel == "fondos" else catalogo.AISLANTES
            try:
                idx_mat = opciones_mat.index(mat_prev_id)
            except ValueError:
                idx_mat = 0
            mat_sel = c_mat.selectbox(
                t("p4.materiales.material"),
                options=opciones_mat,
                index=idx_mat,
                format_func=lambda k: t_catalogo(_cat_dict.get(k, {}), default=k),
                key="p4_pared_simple_mat",
            )
            with c_esp:
                _es_madera_simple = cat_sel == "fondos" and mat_sel in MATERIALES_MADERA
                esp_sel = (
                    selector_espesor_mm(
                        t("p4.materiales.espesor_mm"),
                        float(esp_prev),
                        key="p4_pared_simple_esp",
                        opciones_mm=ESPESORES_MADERA_MM if _es_madera_simple else None,
                        min_mm=1.0,
                        max_mm=500.0,
                        step=5.0,
                    )
                    / 1000.0
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

            st.caption(t("p4.materiales.cara_externa"))
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
                t("p4.materiales.material_estructural"),
                options=fondos_keys,
                index=idx_ext,
                format_func=lambda k: t_catalogo(catalogo.FONDOS.get(k, {}), default=k),
                key="p4_pared_comp_mat_ext",
            )
            with c2:
                esp_ext = (
                    selector_espesor_mm(
                        t("p4.materiales.espesor_externa"),
                        float(cap_ext_prev.espesor_m),
                        key="p4_pared_comp_esp_ext",
                        opciones_mm=(ESPESORES_MADERA_MM if mat_ext in MATERIALES_MADERA else None),
                        min_mm=0.1,
                        max_mm=200.0,
                        step=0.5,
                    )
                    / 1000.0
                )

            st.caption(t("p4.materiales.aislante"))
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
                t("p4.materiales.material_aislante"),
                options=aislantes_keys,
                index=idx_ais,
                format_func=lambda k: t_catalogo(catalogo.AISLANTES.get(k, {}), default=k),
                key="p4_pared_comp_mat_ais",
            )
            esp_ais = (
                c4.number_input(
                    t("p4.materiales.espesor_aislante"),
                    min_value=1.0,
                    max_value=500.0,
                    value=float(cap_ais_prev.espesor_m) * 1000.0,
                    step=5.0,
                    format="%.1f",
                    key="p4_pared_comp_esp_ais",
                )
                / 1000.0
            )

            st.caption(t("p4.materiales.cara_interna"))
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
                t("p4.materiales.material_estructural"),
                options=fondos_keys,
                index=idx_int,
                format_func=lambda k: t_catalogo(catalogo.FONDOS.get(k, {}), default=k),
                key="p4_pared_comp_mat_int",
            )
            with c6:
                esp_int = (
                    selector_espesor_mm(
                        t("p4.materiales.espesor_interna"),
                        float(cap_int_prev.espesor_m),
                        key="p4_pared_comp_esp_int",
                        opciones_mm=(ESPESORES_MADERA_MM if mat_int in MATERIALES_MADERA else None),
                        min_mm=0.1,
                        max_mm=200.0,
                        step=0.5,
                    )
                    / 1000.0
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
        st.success(t("p4.materiales.resumen_u", u=_U_cond, r=_R_cond, esp=_esp_tot * 1000))
        st.caption(t("p4.materiales.resumen_u_nota"))

    # -----------------------------------------------------------------------
    # Sección C: Bandejas
    # -----------------------------------------------------------------------
    with st.expander(
        t("p4.bandejas.titulo_carros") if es_gran_escala else t("p4.bandejas.titulo"),
        expanded=False,
    ):
        band_prev = (
            proyecto.camara.bandejas if proyecto.camara is not None else ConfiguracionBandejas()
        )
        carros_cfg: Optional[ConfiguracionCarros] = None
        c1, c2 = st.columns(2)
        if es_gran_escala:
            # Disposición industrial (S41): carros móviles con pila de bandejas.
            # En semicontinuo el carro es la unidad que avanza por el túnel
            # (cada zona aloja un carro); en batch los carros son estáticos.
            carros_prev = (
                proyecto.camara.carros
                if proyecto.camara is not None and proyecto.camara.carros is not None
                else ConfiguracionCarros()
            )
            n_carros = c1.number_input(
                t("p4.bandejas.n_carros.label"),
                min_value=1,
                max_value=200,
                value=int(carros_prev.n_carros),
                step=1,
                key="p4_n_carros",
                help=t("p4.bandejas.n_carros.help"),
            )
            bandejas_por_carro = c1.number_input(
                t("p4.bandejas.band_por_carro.label"),
                min_value=1,
                max_value=50,
                value=int(carros_prev.bandejas_por_carro),
                step=1,
                key="p4_band_por_carro",
                help=t("p4.bandejas.band_por_carro.help"),
            )
            n_bandejas = int(n_carros) * int(bandejas_por_carro)
            c1.caption(t("p4.bandejas.bandejas_totales", n=n_bandejas))
            carros_cfg = ConfiguracionCarros(
                n_carros=int(n_carros),
                bandejas_por_carro=int(bandejas_por_carro),
            )
        else:
            n_bandejas = c1.number_input(
                t("p4.bandejas.n_bandejas"),
                min_value=1,
                max_value=100,
                value=band_prev.n_bandejas,
                step=1,
            )
        area_bandeja = c2.number_input(
            t("p4.bandejas.area_bandeja"),
            min_value=0.01,
            # El máximo se adapta al valor actual (calibración del área efectiva,
            # snapshot) para no crashear nunca con StreamlitValueAboveMaxError.
            max_value=max(10.0, float(band_prev.area_bandeja_m2)),
            step=0.05,
            format="%.3f",
            key="p4_area_bandeja",
            # value= solo inicializa; si la key ya está en session_state (incl.
            # "aplicar óptimo" de la calibración), el widget la respeta sin warning.
            **(
                {}
                if "p4_area_bandeja" in st.session_state
                else {"value": float(band_prev.area_bandeja_m2)}
            ),
        )
        c3, c4 = st.columns(2)
        espesor_capa = c3.number_input(
            t("p4.bandejas.espesor_capa.label"),
            min_value=0.002,
            max_value=0.2,
            value=band_prev.espesor_capa_m,
            step=0.005,
            format="%.3f",
            help=t("p4.bandejas.espesor_capa.help"),
        )
        sep_bandejas = c4.number_input(
            t("p4.bandejas.separacion.label"),
            min_value=0.02,
            max_value=1.0,
            value=band_prev.separacion_entre_bandejas_m,
            step=0.01,
            format="%.3f",
            help=t("p4.bandejas.separacion.help"),
        )
        _n_pila = carros_cfg.bandejas_por_carro if carros_cfg is not None else n_bandejas
        st.caption(
            t(
                "p4.bandejas.resumen",
                sufijo=t("p4.bandejas.sufijo_carro") if carros_cfg is not None else "",
                altura=_n_pila * sep_bandejas,
                area=n_bandejas * area_bandeja,
                carga=masa_kg / n_bandejas / area_bandeja,
            )
        )

        # -------------------------------------------------------------------
        # Pérdida de carga por rugosidad del producto sobre la bandeja
        # -------------------------------------------------------------------
        st.markdown(t("p4.bandejas.perdida_titulo"))
        _forma = (catalogo.PRODUCTOS.get(prod_id) or {}).get("forma_geometrica") or {}
        _d_p_auto = float(_forma.get("diametro_eq_m") or _D_P_DEFAULT_M)
        _beta_auto = espesor_capa / sep_bandejas if sep_bandejas > 0 else 0.0
        _K_auto = _C_obstruccion_bloqueo(_beta_auto)

        forzar_K_rug = st.checkbox(
            t("p4.bandejas.forzar_k"),
            value=band_prev.K_rugosidad_producto is not None,
            help=t("p4.bandejas.k_rug_help"),
        )
        K_rugosidad_val: Optional[float] = None
        if forzar_K_rug:
            K_rugosidad_val = st.number_input(
                t("p4.bandejas.c_obstruccion.label"),
                min_value=0.0,
                max_value=10.0,
                value=float(band_prev.K_rugosidad_producto or _K_auto),
                step=0.1,
                format="%.2f",
                help=t("p4.bandejas.c_obstruccion.help"),
            )
        else:
            st.caption(t("p4.bandejas.k_auto", k=_K_auto, beta=_beta_auto, dp=_d_p_auto * 1000))

    # -----------------------------------------------------------------------
    # Sección C2: Topología del túnel (solo gran escala semicontinuo)
    # -----------------------------------------------------------------------
    tunel_cfg: Optional[ConfiguracionTunel] = None
    if es_semicontinuo:
        with st.expander(t("p4.tunel.titulo"), expanded=True):
            tun_prev = (
                proyecto.camara.tunel
                if proyecto.camara is not None and proyecto.camara.tunel is not None
                else ConfiguracionTunel()
            )
            t1, t2 = st.columns(2)
            if carros_cfg is not None:
                # Con carros (S41) las zonas quedan derivadas: 1 carro por zona.
                n_zonas = carros_cfg.n_carros
                t1.metric(
                    t("p4.tunel.zonas_carros.label"),
                    f"{n_zonas}",
                    help=t("p4.tunel.zonas_carros.help"),
                )
            else:
                n_zonas = t1.number_input(
                    t("p4.tunel.n_zonas.label"),
                    min_value=1,
                    max_value=50,
                    value=int(tun_prev.n_zonas),
                    step=1,
                    help=t("p4.tunel.n_zonas.help"),
                )
            intervalo_avance_h = t2.number_input(
                t("p4.tunel.cadencia.label"),
                min_value=0.5,
                max_value=240.0,
                value=float(tun_prev.intervalo_avance_h),
                step=1.0,
                format="%.1f",
                help=t("p4.tunel.cadencia.help"),
            )
            tunel_cfg = ConfiguracionTunel(
                n_zonas=int(n_zonas),
                intervalo_avance_h=float(intervalo_avance_h),
            )
            _ciclo_dias = tunel_cfg.residencia_total_h / 24.0
            st.caption(
                t(
                    "p4.tunel.resumen",
                    res=tunel_cfg.residencia_total_h,
                    dias=_ciclo_dias,
                    carga=masa_kg / int(n_zonas),
                    cadencia=intervalo_avance_h,
                )
            )

    # -----------------------------------------------------------------------
    # Sección D: Flujo de aire
    # -----------------------------------------------------------------------
    with st.expander(t("p4.flujo.titulo"), expanded=False):
        flujo_prev = proyecto.camara.flujo if proyecto.camara is not None else ConfiguracionFlujo()

        # Caudal del banco: en un sistema hermético lo que sale del colector es
        # lo que entra a la cámara, así que el caudal de cámara **sigue** al del
        # colector por defecto (S58). Antes arrancaba en el default de
        # ConfiguracionFlujo y el usuario que no lo tocaba corría la cámara con
        # un caudal que no era el del banco, con la única señal de una
        # advertencia al final del cálculo.
        m_col: float | None = None
        hint_caudal = ""
        if proyecto.colector is not None:
            Q_m3s = proyecto.colector.caudal_total_m3_s()
            # Misma densidad que usa la advertencia de coherencia
            # (ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE) para que el valor propuesto
            # no la dispare: ρ(T_amb, P_sitio).
            m_col = caudal_masico_banco_kg_s(
                proyecto.colector, _T_amb_ref_K(proyecto), _P_ref_Pa(proyecto)
            )
            rho_ef = m_col / Q_m3s if Q_m3s > 0 else 1.1
            hint_caudal = t("p4.flujo.hint_colector", q=Q_m3s * 1000, kg=m_col, rho=rho_ef)

        seguir_colector = False
        if m_col is not None and m_col > 0:
            seguir_colector = st.checkbox(
                t("p4.flujo.seguir_colector.label"),
                value=_seguir_colector_default(flujo_prev, m_col),
                key="p4_flujo_seguir_colector",
                help=t("p4.flujo.seguir_colector.help"),
            )

        caudal_sugerido = float(m_col) if seguir_colector else flujo_prev.caudal_masico_kg_s

        c1, c2 = st.columns(2)
        caudal = c1.number_input(
            t("p4.flujo.caudal.label"),
            min_value=0.001,
            # El tope no puede recortar el caudal del propio banco: un banco
            # grande mueve más de 10 kg/s y un tope fijo rompería gran escala.
            max_value=max(10.0, caudal_sugerido * 2.0),
            value=caudal_sugerido,
            step=0.001,
            format="%.4f",
            disabled=seguir_colector,
            help=hint_caudal or t("p4.flujo.caudal.help_default"),
        )
        if hint_caudal:
            c1.caption(f"💡 {hint_caudal}")  # i18n: exento (hint_caudal ya traducido)
        if m_col is not None and not seguir_colector:
            # Desacoplar es legítimo (mezclar aire ambiente para bajar la T de
            # entrada), pero deja de ser el caudal del banco: decirlo acá evita
            # que la incoherencia se descubra recién en la advertencia final.
            c1.caption(t("p4.flujo.seguir_colector.desacoplado"))

        _dir_keys = ["horizontal", "vertical_ascendente"]
        _dir_enum = {
            "horizontal": DireccionFlujo.HORIZONTAL,
            "vertical_ascendente": DireccionFlujo.VERTICAL_ASCENDENTE,
        }
        _dir_prev = flujo_prev.direccion_flujo.value.lower()
        dir_key = c2.selectbox(
            t("p4.flujo.direccion.label"),
            options=_dir_keys,
            index=_dir_keys.index(_dir_prev) if _dir_prev in _dir_keys else 0,
            format_func=lambda k: t(f"p4.flujo.direccion.{k}"),
        )
        direccion = _dir_enum[dir_key]

        usar_HR = st.checkbox(
            t("p4.flujo.usar_hr.label"),
            value=flujo_prev.HR_entrada_fraccion is not None,
            help=t("p4.flujo.usar_hr.help"),
        )
        HR_entrada_frac: float | None = None
        if usar_HR:
            HR_pct = st.slider(
                t("p4.flujo.hr_entrada"),
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
        st.caption(t("p4.flujo.velocidad", v=v_sup, q=Q_vol * 1000))

    # -----------------------------------------------------------------------
    # Sección E: Condiciones de operación
    # -----------------------------------------------------------------------
    with st.expander(t("p4.borde.titulo"), expanded=False):
        # En modo "Día real" (con datos reales disponibles) el borde y los
        # coeficientes salen del clima/colector → estos sliders no intervienen
        # y se ocultan para no confundir. Si "Día real" se eligió pero no hay
        # datos reales, el cálculo cae a "Sintético", que SÍ usa estos valores
        # → en ese caso se muestran igual.
        # La selección de forzantes se guarda como índice estable ("cam_forz_idx")
        # además del label; el modo "Día real" es el índice 2 del radio.
        _forz_idx_sel = int(st.session_state.get("cam_forz_idx", 0))
        _real_disp, _ = _disponibilidad_forzantes_reales(st.session_state.get("p3_eval"), proyecto)
        _borde_no_aplica = usar_ventana or (_forz_idx_sel == 2 and _real_disp)

        if _borde_no_aplica:
            st.info(t("p4.borde.no_aplica"))
            # Valores vestigiales para el build (no afectan el cálculo en Día real).
            T_op_C = st.session_state.get("cam_T_op_C", _T_OP_DEFAULT_C)
            HR_op_pct = st.session_state.get("cam_HR_op_pct", _HR_DEFAULT_PCT)
        else:
            st.caption(t("p4.borde.caption"))
            if es_caja_pre:
                hint_T = t("p4.borde.hint_t_caja")
            else:
                hint_T = t("p4.borde.hint_t_otro")

            T_op_C = st.slider(
                t("p4.borde.t_op"),
                min_value=int(_T_OP_MIN_C),
                max_value=int(_T_OP_MAX_C),
                value=int(st.session_state.get("cam_T_op_C", _T_OP_DEFAULT_C)),
                step=1,
                help=hint_T,
            )
            st.session_state["cam_T_op_C"] = T_op_C

            HR_op_pct = st.slider(
                t("p4.borde.hr_op.label"),
                min_value=5,
                max_value=95,
                value=int(st.session_state.get("cam_HR_op_pct", _HR_DEFAULT_PCT)),
                step=1,
                help=t("p4.borde.hr_op.help"),
            )
            st.session_state["cam_HR_op_pct"] = HR_op_pct

    # -----------------------------------------------------------------------
    # Sección F: Modo de cálculo
    # -----------------------------------------------------------------------

    # Detectar restricciones
    from core.proyecto import Tipologia

    tipologia = getattr(getattr(proyecto, "configuracion", None), "tipologia", None)
    es_caja = tipologia == Tipologia.CAJA
    es_gran_escala = tipologia == Tipologia.GRAN_ESCALA

    with st.expander(t("p4.forzantes.titulo"), expanded=False):

        # Motor único desde S38 (termodinámico). El antiguo selector de motor
        # (capa fina vs termodinámico) se eliminó.
        modo_calculo = "termodinamico"
        st.session_state.pop("cam_modo_dinamico", None)

        # Sub-controles del modo termodinámico: tipo de forzantes + horizonte
        tipo_forzantes = "constantes"
        n_dias = 1
        dias_consecutivos = False
        I_g_max_W_m2 = 0.0
        if usar_ventana:
            # Ventana de producción: horizonte = lapso de P1, forzantes reales.
            tipo_forzantes = "real"
            _vi = getattr(proyecto.configuracion, "ventana_inicio", None)
            _vf = getattr(proyecto.configuracion, "ventana_fin", None)
            _ndias_vent = (_vf - _vi).days if (_vi and _vf) else 0
            _borde_vent = (
                t("p4.forzantes.ventana_borde_caja")
                if es_caja
                else t("p4.forzantes.ventana_borde_otro")
            )
            st.info(
                t("p4.forzantes.ventana_info", vi=_vi, vf=_vf, ndias=_ndias_vent, borde=_borde_vent)
            )
            if proyecto.clima is None or proyecto.clima.datos is None:
                st.warning(t("p4.forzantes.ventana_sin_clima"))
        elif modo_calculo == "termodinamico":
            real_ok, real_motivo = _disponibilidad_forzantes_reales(
                st.session_state.get("p3_eval"),
                proyecto,
            )

            # Options con claves estables (constantes/sintetico/real) + format_func:
            # el valor guardado en session_state no depende del idioma.
            _label_real = t("p4.forzantes.real_caja") if es_caja else t("p4.forzantes.real_otro")
            _forz_labels = {
                "constantes": t("p4.forzantes.op_constantes"),
                "sintetico": t("p4.forzantes.op_sintetico"),
                "real": _label_real,
            }
            _forz_keys = list(_forz_labels)
            _help_real = (
                t("p4.forzantes.help_real_caja") if es_caja else t("p4.forzantes.help_real_otro")
            )
            forz_key = st.radio(
                t("p4.forzantes.radio.label"),
                options=_forz_keys,
                key="cam_forz_key",
                horizontal=False,
                format_func=lambda k: _forz_labels[k],
                help=t("p4.forzantes.radio.help", real=_help_real),
            )
            st.session_state["cam_forz_idx"] = _forz_keys.index(forz_key)
            tipo_forzantes = forz_key

            if tipo_forzantes == "real" and not real_ok:
                st.warning(t("p4.forzantes.real_no_disp", motivo=real_motivo))
                tipo_forzantes = "sintetico"

            _hz_keys = ["un_dia", "multidia"]
            _hz_idx = st.session_state.get("cam_hz_idx", 0)
            hz_key = st.selectbox(
                t("p4.forzantes.hz.label"),
                options=_hz_keys,
                index=_hz_idx,
                format_func=lambda k: t(f"p4.forzantes.hz.{k}"),
                help=t("p4.forzantes.hz.help"),
            )
            st.session_state["cam_hz_idx"] = _hz_keys.index(hz_key)
            if hz_key == "multidia":
                n_dias = int(
                    st.number_input(
                        t("p4.forzantes.n_dias"),
                        min_value=1,
                        max_value=21,
                        value=int(st.session_state.get("cam_n_dias", 3)),
                        step=1,
                    )
                )
                st.session_state["cam_n_dias"] = n_dias

                # Solo con forzantes "real": elegir repetir el día de diseño o
                # tomar N días reales consecutivos del clima.
                if tipo_forzantes == "real":
                    _md_keys = ["repetir", "consecutivos"]
                    _md_idx = 1 if st.session_state.get("cam_multidia_consecutivo", False) else 0
                    md_key = st.radio(
                        t("p4.forzantes.composicion.label"),
                        options=_md_keys,
                        index=_md_idx,
                        horizontal=True,
                        format_func=lambda k: t(f"p4.forzantes.composicion.{k}"),
                        help=t("p4.forzantes.composicion.help"),
                    )
                    dias_consecutivos = md_key == "consecutivos"
                    st.session_state["cam_multidia_consecutivo"] = dias_consecutivos

            if tipo_forzantes == "real":
                if es_caja:
                    st.info(t("p4.forzantes.reales_caja"))
                else:
                    st.info(t("p4.forzantes.reales_otro"))

            # I_g_max del día sintético: sólo relevante si hay techo translúcido
            if tipo_forzantes == "sintetico" and cubierta_id_sel is not None:
                I_g_max_W_m2 = float(
                    st.number_input(
                        t("p4.forzantes.i_g_max.label"),
                        min_value=0.0,
                        max_value=1400.0,
                        value=float(st.session_state.get("cam_I_g_max", 800.0)),
                        step=50.0,
                        help=t("p4.forzantes.i_g_max.help"),
                    )
                )
                st.session_state["cam_I_g_max"] = I_g_max_W_m2
            else:
                I_g_max_W_m2 = 0.0

        T_prod_inicial_K_val: float | None = None
        if modo_calculo == "termodinamico":
            T_amb_repr_K, T_amb_origen = _T_amb_representativa_K(proyecto)
            st.caption(t("p4.forzantes.t_amb_repr", t=T_amb_repr_K - 273.15, origen=T_amb_origen))
            usar_T_prod_explicita = st.checkbox(
                t("p4.forzantes.t_prod_check"),
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
                    t("p4.forzantes.t_prod.label"),
                    min_value=-10.0,
                    max_value=70.0,
                    value=float(T_prod_default_C),
                    step=1.0,
                    help=t("p4.forzantes.t_prod.help"),
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
                st.warning(t("p4.forzantes.sin_gab"))

    # -----------------------------------------------------------------------
    # Builder de Camara desde los widgets actuales (closure)
    # -----------------------------------------------------------------------
    def _build_camara(*, modo_calculo_override: str | None = None) -> Camara:
        """Construye Camara con los valores actuales de los widgets."""
        geo = GeometriaCamara(
            largo_m=largo,
            ancho_m=ancho,
            alto_m=alto,
            pendiente_techo_deg=pendiente_techo,
            acimut_camara_deg=acimut_camara_duffie,
            cara_caida_techo=cara_caida_sel,
        )
        cons = ConstruccionCamara(
            cubierta_translucida_id=cubierta_id_sel,
            cubierta_translucida_espesor_m=espesor_techo_m_sel,
            caras_translucidas=caras_translucidas_sel,
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
            seguir_caudal_colector=seguir_colector,
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
            tunel=tunel_cfg,
            carros=carros_cfg,
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
        st.markdown(t("p4.test_puntual.titulo"))
        st.caption(t("p4.test_puntual.caption"))
    _bloqueo_caja_opaca = es_caja_pre and (
        cubierta_id_sel is None or not caras_translucidas_sel.activas()
    )
    # En túnel semicontinuo la previa NO es el modelo real: P4 resuelve siempre con
    # `calcular_camara` (un nodo), mientras que el túnel de N zonas a contracorriente
    # vive en `calcular_camara_cascada` y se corre en P7. Hay que decirlo, porque los
    # números de acá no son los de producción.
    if es_semicontinuo:
        st.warning(t("p4.calcular.aviso_previa_nodo_unico"))
    calcular = st.button(
        t("p4.calcular.label"),
        type="primary" if modo_analisis != ModoAnalisis.ANUAL else "secondary",
        disabled=_bloqueo_caja_opaca,
        help=(t("p4.calcular.help_bloqueo") if _bloqueo_caja_opaca else None),
    )

    if calcular:
        try:
            geo = GeometriaCamara(
                largo_m=largo,
                ancho_m=ancho,
                alto_m=alto,
                pendiente_techo_deg=pendiente_techo,
                acimut_camara_deg=acimut_camara_duffie,
                cara_caida_techo=cara_caida_sel,
            )
            cons = ConstruccionCamara(
                cubierta_translucida_id=cubierta_id_sel,
                cubierta_translucida_espesor_m=espesor_techo_m_sel,
                caras_translucidas=caras_translucidas_sel,
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
                seguir_caudal_colector=seguir_colector,
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
                tunel=tunel_cfg,
                carros=carros_cfg,
            )
            proyecto.camara = camara

        except (ValueError, NotImplementedError) as exc:
            st.error(t("p4.error_config", exc=exc))
            return

        # Advertencias estáticas
        adv_list = advertencias_camara(camara)
        if adv_list:
            st.subheader(t("p4.advertencias_titulo"))
            _mostrar_advertencias(adv_list)
        else:
            st.success(t("p4.sin_advertencias"))

        # Cálculo numérico
        T_op_K = celsius_a_kelvin(float(T_op_C))
        HR_op = HR_op_pct / 100.0
        T_amb_calc_K, _ = _T_amb_representativa_K(proyecto)

        # Presión atmosférica representativa del emplazamiento (corregida por
        # altitud o NASA POWER). Sin esta corrección, las psicrométricas usan
        # 101 325 Pa y sobrestiman ω_sat en sitios elevados.
        from calculos.balance_global import presion_representativa_proyecto

        P_proyecto_Pa, P_origen = presion_representativa_proyecto(proyecto)
        st.caption(t("p4.presion_usada", origen=P_origen))

        try:
            if modo_calculo == "termodinamico":
                # El armado de forzantes es pesado (re-corre el colector hora a
                # hora sobre el lapso): sin spinner parece que la app se colgó.
                with st.spinner(t("p4.spinner_forzantes")):
                    if usar_ventana:
                        fz_aire = _construir_forzantes_ventana(
                            proyecto=proyecto,
                            caudal_kg_s=camara.flujo.caudal_masico_kg_s,
                            P_Pa=P_proyecto_Pa,
                        )
                    else:
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
                            dias_consecutivos=dias_consecutivos,
                        )
                # Advertencias del paso de trabajo (ADV_PASO_SINTETICO, fase 1b),
                # depositadas por _datos_local_paso al resolver el clima real.
                for _a in st.session_state.get(_PASO_ADV_KEY, []):
                    st.warning(_a)
                t_max_efectivo = (
                    float(fz_aire.t_s[-1]) if fz_aire is not None else float(n_dias) * 24.0 * 3600.0
                )
                # Días efectivamente simulados (en consecutivos puede truncarse en el
                # borde del año). Se infiere de la longitud de la serie: puntos por día
                # = 86400/dt (fase 1b: el paso puede ser sub-horario).
                if fz_aire is not None and len(fz_aire.t_s) > 1:
                    _dt_fz = float(fz_aire.t_s[1] - fz_aire.t_s[0])
                    _ppd = max(1, round(86400.0 / _dt_fz))
                    n_dias_efectivo = max(1, round(len(fz_aire.t_s) / _ppd))
                else:
                    n_dias_efectivo = int(n_dias)
                if dias_consecutivos and n_dias_efectivo < n_dias:
                    st.warning(
                        t(
                            "p4.horizonte_recortado",
                            n=n_dias_efectivo,
                            solicitado=n_dias,
                            anio=proyecto.clima.anio,
                        )
                    )
                with st.spinner(t("p4.spinner_integrando")):
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
                    st.session_state["p4_horizonte_resultado"] = res
                    st.session_state["p4_horizonte_meta"] = {
                        "n_dias": int(n_dias_efectivo),
                        "modo_forzantes": tipo_forzantes,
                        "horizonte_tipo": (
                            "ventana de producción"
                            if usar_ventana
                            else (
                                "días reales consecutivos"
                                if dias_consecutivos and n_dias > 1
                                else ("día típico repetido" if n_dias > 1 else "1 día")
                            )
                        ),
                        # Kwargs del builder (S47): permiten a P7 reconstruir las
                        # forzantes desde un proyecto clonado y mutado en un
                        # barrido paramétrico (ver BarridoConfig.forzantes_builder),
                        # en vez de reutilizar esta forzante congelada.
                        "usar_ventana": usar_ventana,
                        "tipo_forzantes": tipo_forzantes,
                        "T_op_K": T_op_K,
                        "HR_op": HR_op,
                        "T_amb_calc_K": T_amb_calc_K,
                        "n_dias_solicitado": int(n_dias),
                        "I_g_max_W_m2": I_g_max_W_m2,
                        "P_proyecto_Pa": P_proyecto_Pa,
                        "dias_consecutivos": dias_consecutivos,
                    }
                    # Con la huella de las entradas: P7 consume estas forzantes
                    # sin rehacerlas, así que tiene que poder detectar que el
                    # colector (o el clima, o el día de análisis) cambió después
                    # de armarlas. Mismo mecanismo que el resultado anual (S58).
                    registrar(
                        st.session_state,
                        "horizonte",
                        fz_aire,
                        proyecto,
                        extras=extras_horizonte(st.session_state["p4_horizonte_meta"]),
                    )
                else:
                    # Modo "Constantes": no hay horizonte transitorio para P7.
                    invalidar(st.session_state, "horizonte")
                    st.session_state.pop("p4_horizonte_resultado", None)
                    st.session_state.pop("p4_horizonte_meta", None)
        except Exception as exc:
            st.error(t("p4.error_calculo", exc=exc))
            return

        # Limpiar resultado del motor dinámico viejo (si quedó en session_state)
        st.session_state.pop("p4_resultado_dinamico", None)
        st.session_state.pop("p4_din_X_obj", None)
        st.session_state.pop("p4_din_prod_id", None)
        st.session_state.pop("p4_din_modelo", None)

        # Advertencias del cálculo
        if res.advertencias:
            st.subheader(t("p4.advertencias_calculo"))
            for msg in res.advertencias:
                st.warning(f"⚠️ {msg}")  # i18n: exento (mensaje de calculos/, queda ES)

        # Display branched por tipo de resultado
        if isinstance(res, ResultadoMotorTermodinamico):
            # ---- Display motor termodinámico ----
            st.subheader(t("p4.resultados_td.titulo"))
            # Repetido sobre los resultados: es donde el usuario lee los números y
            # donde más fácil sería tomarlos por los del túnel.
            if es_semicontinuo:
                st.warning(t("p4.calcular.aviso_previa_nodo_unico"))
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            if res.t_secado_s is not None:
                col_r1.metric(
                    t("p4.resultados_td.t_secado"),
                    f"{res.t_secado_s / 3600.0:.1f} h",
                )
            else:
                col_r1.metric(
                    t("p4.resultados_td.t_secado"),
                    t("p4.resultados_td.no_alcanzado"),
                    help=res.status,
                )
            col_r2.metric(t("p4.resultados_td.status"), res.status)
            col_r3.metric(
                t("p4.resultados_td.agua_evaporada.label"),
                f"{res.masa_evaporada_total_kg:.2f} kg",
                help=t("p4.resultados_td.agua_evaporada.help"),
            )
            col_r4.metric(
                t("p4.resultados_td.x_final.label"),
                f"{res.X_prod_kg_kg[-1]:.4f}",
                help=t("p4.resultados_td.x_final.help"),
            )

            # Diagnósticos extras del nuevo motor
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            col_d1.metric(
                t("p4.resultados_td.t_max.label"),
                f"{res.T_max_alcanzada_K - 273.15:.1f} °C",
                help=t("p4.resultados_td.t_max.help"),
            )
            col_d2.metric(
                t("p4.resultados_td.horas_anti_rehum.label"),
                f"{res.horas_clipeo_nocturno_s / 3600.0:.1f} h",
                help=t("p4.resultados_td.horas_anti_rehum.help"),
            )
            col_d3.metric(
                t("p4.resultados_td.horas_hr.label"),
                f"{res.horas_HR_alta_s / 3600.0:.1f} h",
                help=t("p4.resultados_td.horas_hr.help"),
            )
            col_d4.metric(
                t("p4.resultados_td.energia_rad.label"),
                f"{res.energia_rad_total_J / 3.6e6:.2f} kWh",
                help=t("p4.resultados_td.energia_rad.help"),
            )

            if res.status == "t_max_alcanzado":
                horas_total = float(res.t_array_s[-1]) / 3600.0
                st.warning(
                    t(
                        "p4.resultados_td.no_convergio",
                        dias=horas_total / 24.0,
                        x_obj=X_obj,
                        x_fin=res.X_prod_kg_kg[-1],
                    )
                )

            fig = _grafica_secado_termodinamico(res, X_obj, prod_id)
            mostrar_plotly(fig, nombre="camara_secado_td")

            with st.expander(t("p4.resultados_td.curva_expander"), expanded=False):
                st.markdown(t("p4.resultados_td.curva_md"))
        else:
            # ---- Display motor capa fina (existente) ----
            st.subheader(t("p4.resultados_cf.titulo"))

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            t_h = res.t_secado_s / 3600.0

            col_r1.metric(
                t("p4.resultados_cf.t_secado.label"),
                f"{t_h:.1f} h" if res.convergencia_ok else f">{t_h:.0f} h",
                help=t("p4.resultados_cf.t_secado.help"),
            )
            col_r2.metric(
                t("p4.resultados_cf.x_eq.label"),
                f"{res.X_eq_kg_kg:.4f} kg/kg ms",
                help=t("p4.resultados_cf.x_eq.help", fuente=res.fuente_X_eq),
            )
            col_r3.metric(
                t("p4.resultados_cf.agua_extraida.label"),
                f"{res.masa_agua_extraida_kg:.2f} kg",
                help=t("p4.resultados_cf.agua_extraida.help"),
            )
            col_r4.metric(
                t("p4.resultados_cf.mr_obj.label"),
                f"{res.MR_obj:.4f}",
                help=t("p4.resultados_cf.mr_obj.help"),
            )

            if not res.convergencia_ok:
                st.warning(f"⚠️ {res.mensaje_convergencia}")  # i18n: exento (mensaje de calculos/)

            fig = _grafica_curva_secado(res, X_ini, X_obj, prod_id)
            mostrar_plotly(fig, nombre="camara_curva_secado")

        # Resumen compacto
        with st.expander(t("p4.resumen.titulo")):
            c1, c2 = st.columns(2)
            with c1:
                st.write(t("p4.resumen.producto", v=prod_id))
                st.write(t("p4.resumen.masa", v=masa_kg))
                st.write(t("p4.resumen.x_ini", v=X_ini))
                st.write(t("p4.resumen.x_obj", v=X_obj))
                st.write(t("p4.resumen.modelo_cf", v=modelo_cf))
                st.write(t("p4.resumen.motor", v=modo_calculo))
                st.write(t("p4.resumen.t_op", v=T_op_C))
                st.write(t("p4.resumen.hr_op", v=HR_op_pct))
            with c2:
                st.write(t("p4.resumen.camara", largo=largo, ancho=ancho, alto=alto))
                st.write(t("p4.resumen.bandejas", n=n_bandejas, area=area_bandeja))
                st.write(t("p4.resumen.espesor_capa", v=espesor_capa * 100))
                st.write(t("p4.resumen.caudal", v=caudal))
                st.write(t("p4.resumen.direccion", v=t(f"p4.flujo.direccion.{dir_key}")))
                st.write(t("p4.resumen.t_amb", v=T_amb_calc_K - 273.15))

    # --- Guardar configuración ---
    if proyecto.camara is not None:
        st.divider()
        from ui.componentes.serializacion import dump_json, nombre_archivo_descarga

        col_txt, col_json = st.columns(2)
        with col_txt:
            st.download_button(
                t("p4.guardar.txt"),
                data=_texto_config_camara(proyecto.camara, st.session_state),
                file_name=nombre_archivo_descarga(proyecto, "camara", "txt"),
                mime="text/plain",
                width="stretch",
            )
        with col_json:
            st.download_button(
                t("p4.guardar.json"),
                data=dump_json(_json_config_camara(proyecto.camara, st.session_state)),
                file_name=nombre_archivo_descarga(proyecto, "camara", "json"),
                mime="application/json",
                width="stretch",
            )

    # --- Validación con datos medidos (mejora 38, fase 4) ---
    st.divider()
    _render_validacion_camara(proyecto)


# ---------------------------------------------------------------------------
# Validación con datos medidos (mejora 38, fase 4)
# ---------------------------------------------------------------------------


def _config_referencia_camara(
    *, col_ts, col_val, variable, unidad, zona, conv, hoja, fila_enc, fecha_fija, masa_seca
):
    """Arma la ``ConfigReferencia`` de cámara desde los widgets (puro, testeable)."""
    from core.validacion import ConfigReferencia

    return ConfigReferencia(
        columna_timestamp=col_ts,
        columna_valor=col_val,
        variable=variable,
        unidad=unidad,
        zona_horaria=zona,
        convencion_timestamp=conv,
        hoja=hoja,
        fila_encabezado=int(fila_enc),
        fecha_fija=fecha_fija,
        masa_seca_kg=masa_seca,
    )


def _opciones_columna(columnas, etiqueta_vacia):
    """Lista de columnas con una opción 'no mapeada' al frente."""
    return [etiqueta_vacia] + [str(c) for c in columnas]


# Parámetros calibrables de la cámara. Los dos primeros grupos son distintos:
#   - ``area_bandeja`` es un CAMPO REAL del proyecto (área efectiva de intercambio).
#     Multiplica tanto h·A como K_m·A, así que es el knob físicamente interpretable
#     — y por eso se puede APLICAR al proyecto, como en P3.
#   - ``factor_K_m``/``factor_h_conv`` son correcciones al CIERRE del modelo (analogía
#     de Chilton-Colburn, isoterma GAB del cultivar, ω de entrada supuesta). No son
#     propiedades de la cámara ni transfieren a otro producto/caudal, así que quedan
#     como DIAGNÓSTICO: se informan, no se guardan.
_PARAMS_CALIBRABLES_CAMARA: tuple[str, ...] = ("area_bandeja", "factor_K_m", "factor_h_conv")
_PARAMS_APLICABLES_CAMARA: tuple[str, ...] = ("area_bandeja",)

# Id del parámetro calibrado → key del widget de P4, para refrescar el campo tras
# "aplicar óptimo" (mismo patrón pendiente que P3).
_WIDGET_KEY_POR_PARAM_P4: dict[str, str] = {"area_bandeja": "p4_area_bandeja"}


def _rango_sugerido_calibracion(param: str, proyecto) -> tuple[float, float, float]:
    """Rango por defecto del barrido: ``(min, max, paso)`` según el parámetro.

    Para el área efectiva se centra en el valor actual del proyecto (0.5×–3×,
    porque una capa de rodajas apiladas puede tener varias veces el área de la
    bandeja); para los factores de cierre, un rango neutro alrededor de 1.
    """
    if param == "area_bandeja" and proyecto.camara is not None:
        actual = float(proyecto.camara.bandejas.area_bandeja_m2)
        return max(0.01, 0.5 * actual), 3.0 * actual, max(0.01, actual / 20.0)
    return 0.5, 2.5, 0.1


def _evaluador_calibracion_camara(proyecto, senal, forzantes, t0_utc, param):
    """Closure ``valor -> MetricasAjuste|None`` para :func:`calibrar_1d`.

    Los factores de cierre se pasan como kwargs al motor; el área efectiva se
    aplica sobre un **clon** de la cámara (nunca sobre el proyecto del usuario)
    vía ``barrido_parametrico.aplicar_parametro``.
    """
    import copy
    from types import SimpleNamespace

    from calculos.barrido_parametrico import aplicar_parametro
    from calculos.validacion_camara import evaluar_camara

    def _evaluar(valor):
        if param in ("factor_K_m", "factor_h_conv"):
            metricas, _ = evaluar_camara(
                proyecto.camara, senal, forzantes, t0_utc, **{param: float(valor)}
            )
            return metricas
        shim = SimpleNamespace(camara=copy.deepcopy(proyecto.camara))
        aplicar_parametro(shim, param, float(valor))
        metricas, _ = evaluar_camara(shim.camara, senal, forzantes, t0_utc)
        return metricas

    return _evaluar


def _render_calibracion_camara(proyecto, senal, forzantes, t0_utc) -> None:
    """Calibra un parámetro de la cámara contra el medido.

    El área efectiva se puede aplicar al proyecto (es un campo real); los factores
    de cierre solo se informan (ver :data:`_PARAMS_CALIBRABLES_CAMARA`).
    """
    import numpy as _np

    from calculos.barrido_parametrico import aplicar_parametro
    from calculos.calibracion import calibrar_1d
    from calculos.validacion_camara import unidad_display
    from ui.componentes.validacion_widget import fig_curva_calibracion

    st.divider()
    st.markdown(t("p4.calibracion.titulo"))
    st.caption(t("p4.calibracion.intro"))

    param = st.selectbox(
        t("p4.calibracion.parametro"),
        options=list(_PARAMS_CALIBRABLES_CAMARA),
        format_func=lambda k: t(f"p4.calibracion.param.{k}"),
        key="p4_cal_param",
        help=t("p4.calibracion.ayuda_param"),
    )
    st.caption(
        t("p4.calibracion.es_aplicable")
        if param in _PARAMS_APLICABLES_CAMARA
        else t("p4.calibracion.es_diagnostico")
    )

    v_min_def, v_max_def, paso_def = _rango_sugerido_calibracion(param, proyecto)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        v_min = st.number_input(
            t("p4.calibracion.min"),
            value=float(v_min_def),
            min_value=0.001,
            step=float(paso_def),
            format="%.3f",
            key=f"p4_cal_min_{param}",
        )
    with c2:
        v_max = st.number_input(
            t("p4.calibracion.max"),
            value=float(v_max_def),
            min_value=0.002,
            step=float(paso_def),
            format="%.3f",
            key=f"p4_cal_max_{param}",
        )
    with c3:
        n_pts = st.number_input(
            t("p4.calibracion.n"), value=9, min_value=3, max_value=41, step=1, key="p4_cal_n"
        )
    with c4:
        objetivo = st.selectbox(
            t("p4.calibracion.objetivo"),
            options=["rmse", "mbe_abs", "mae"],
            format_func=lambda k: t(f"p4.calibracion.obj.{k}"),
            key="p4_cal_obj",
        )

    if v_max <= v_min:
        st.warning(t("p4.calibracion.rango_invalido"))
        return

    if st.button(t("p4.calibracion.correr"), key="p4_cal_correr"):
        with st.spinner(t("p4.calibracion.spinner")):
            st.session_state["p4_cal_resultado"] = calibrar_1d(
                _np.linspace(float(v_min), float(v_max), int(n_pts)),
                _evaluador_calibracion_camara(proyecto, senal, forzantes, t0_utc, param),
                parametro=param,
                objetivo=objetivo,
            )

    res_cal = st.session_state.get("p4_cal_resultado")
    if res_cal is None:
        return
    if res_cal.valor_optimo is None:
        st.warning(t("p4.calibracion.sin_optimo"))
        return

    es_factor = res_cal.parametro in ("factor_K_m", "factor_h_conv")
    st.plotly_chart(
        fig_curva_calibracion(
            res_cal,
            x_lbl=(
                t("p4.calibracion.eje_x")
                if es_factor
                else t(f"p4.calibracion.param.{res_cal.parametro}")
            ),
            y_lbl=t(f"p4.calibracion.obj.{res_cal.objetivo_nombre}"),
            titulo=t("p4.calibracion.grafica_titulo"),
            optimo_lbl=t("p4.calibracion.optimo"),
        ),
        width="stretch",
    )
    m = res_cal.metricas_optimo
    unidad = unidad_display(senal.variable)
    st.success(
        t(
            "p4.calibracion.resultado",
            valor=f"{res_cal.valor_optimo:.4g}",
            rmse=f"{m.rmse:.3g} {unidad}",
            mbe=f"{m.mbe:+.3g} {unidad}",
            r2=f"{m.r2:.3f}",
        )
    )

    if es_factor:
        # Lectura física del factor: qué dice sobre el modelo.
        if res_cal.valor_optimo > 1.05:
            st.caption(t("p4.calibracion.lectura_alto"))
        elif res_cal.valor_optimo < 0.95:
            st.caption(t("p4.calibracion.lectura_bajo"))
        else:
            st.caption(t("p4.calibracion.lectura_neutro"))
    elif res_cal.parametro == "area_bandeja" and proyecto.camara is not None:
        # El área efectiva es interpretable: cuántas veces la de bandeja declarada.
        actual = float(proyecto.camara.bandejas.area_bandeja_m2)
        if actual > 0:
            st.caption(
                t("p4.calibracion.lectura_area", veces=f"{res_cal.valor_optimo / actual:.2f}")
            )

    if st.session_state.get("_p4_val_hr_asumida"):
        st.warning(t("p4.calibracion.aviso_hr"))

    if res_cal.parametro in _PARAMS_APLICABLES_CAMARA:
        if st.button(t("p4.calibracion.aplicar"), key="p4_cal_aplicar"):
            try:
                aplicar_parametro(proyecto, res_cal.parametro, float(res_cal.valor_optimo))
                # Igual que en P3: se deja el valor pendiente para fijarlo al TOPE del
                # próximo render, antes de que el widget se instancie.
                _wkey = _WIDGET_KEY_POR_PARAM_P4.get(res_cal.parametro)
                if _wkey is not None:
                    st.session_state["_p4_pending_widget"] = {_wkey: float(res_cal.valor_optimo)}
                st.session_state.pop("p4_val_resultado", None)
                st.session_state.pop("p4_cal_resultado", None)
                st.success(t("p4.calibracion.aplicado"))
                st.rerun()
            except (ValueError, KeyError) as exc:
                st.error(t("p4.validacion.error", err=exc))


def _render_cadena_completa(senal, variable) -> None:
    """Overlay medido vs **cadena completa** de P7 (diagnóstico, sin calibrar).

    Reusa el resultado transitorio que P7 dejó en sesión. Solo es posible si ese
    resultado trae ``t0_utc`` (forzantes con clima real): el motor integra en
    tiempo relativo, así que sin ancla absoluta no hay forma de alinearlo contra
    una señal medida — y un overlay corrido sería peor que no tenerlo.
    """
    from calculos.ingesta_referencia import evaluar_ajuste
    from calculos.validacion_camara import a_display, serie_simulada, unidad_display
    from ui.componentes.validacion_widget import fig_overlay

    st.divider()
    st.markdown(t("p4.cadena.titulo"))
    st.caption(t("p4.cadena.intro"))

    res_tr = st.session_state.get("p7_resultados_tr")
    if res_tr is None or getattr(res_tr, "camara", None) is None:
        st.info(t("p4.cadena.sin_resultado"))
        return
    t0 = getattr(res_tr, "t0_utc", None)
    if t0 is None:
        st.info(t("p4.cadena.sin_ancla"))
        return

    try:
        t_sim, y_sim = serie_simulada(res_tr.camara, variable, t0)
        metricas, y_med, y_sim_al, ts = evaluar_ajuste(senal, t_sim, y_sim)
    except (ValueError, RuntimeError) as exc:
        st.error(t("p4.validacion.error", err=exc))
        return
    if metricas is None:
        st.info(t("p4.cadena.sin_solape"))
        return

    unidad_disp = unidad_display(variable)
    st.plotly_chart(
        fig_overlay(
            ts,
            a_display(y_med, variable),
            a_display(y_sim_al, variable),
            medido_lbl=t("p4.validacion.grafica.medido"),
            simulado_lbl=t("p4.cadena.simulado"),
            titulo=t("p4.cadena.grafica_titulo", magnitud=t(f"p4.validacion.variable.{variable}")),
            y_lbl=f"{t(f'p4.validacion.variable.{variable}')} [{unidad_disp}]",
        ),
        width="stretch",
    )
    st.caption(
        t(
            "p4.cadena.metricas",
            rmse=f"{metricas.rmse:.3g} {unidad_disp}",
            mbe=f"{metricas.mbe:+.3g} {unidad_disp}",
            r2=f"{metricas.r2:.3f}",
            n=int(metricas.n_pares),
        )
    )
    st.caption(t("p4.cadena.comparacion"))


def _render_validacion_camara(proyecto) -> None:
    """Sección de P4: valida la cámara AISLADA contra un ensayo medido."""
    from calculos import clima_medido as cm
    from calculos.ingesta_referencia import (
        evaluar_ajuste,
        ingerir_forzantes_camara,
        ingerir_referencia,
    )
    from calculos.validacion_camara import (
        VARIABLES_CAMARA,
        a_display,
        serie_simulada,
        simular_camara_aislada,
        unidad_display,
    )
    from core.validacion import CONVENCIONES_TIMESTAMP, UNIDADES_REFERENCIA
    from ui.componentes.serializacion import limpiar_session_state_prefijo
    from ui.componentes.validacion_widget import fig_overlay, filas_metricas

    with st.expander(t("p4.validacion.titulo"), expanded=False):
        st.caption(t("p4.validacion.intro"))
        st.info(t("p4.validacion.aviso_orden"))

        if proyecto.camara is None:
            st.info(t("p4.validacion.sin_camara"))
            return

        arch = st.session_state.get("p4_val_archivo")
        if arch is None:
            subido = st.file_uploader(
                t("p4.validacion.uploader.label"),
                type=["csv", "txt", "xls", "xlsx"],
                key="p4_val_uploader",
                help=t("p4.validacion.uploader.help"),
            )
            if subido is not None:
                contenido = subido.read()
                st.session_state["p4_val_archivo"] = {
                    "nombre": subido.name,
                    "bytes": contenido,
                    "hash": cm.hash_archivo(contenido),
                }
                st.session_state.pop("p4_val_uploader", None)
                st.rerun()
            return

        c_a, c_b = st.columns([4, 1])
        with c_a:
            st.markdown(
                t(
                    "p4.validacion.archivo_cargado",
                    nombre=arch["nombre"],
                    kb=f"{len(arch['bytes']) / 1024:.0f}",
                )
            )
        with c_b:
            if st.button(t("p4.validacion.quitar"), key="p4_val_quitar"):
                limpiar_session_state_prefijo(st.session_state, "p4_val_")
                limpiar_session_state_prefijo(st.session_state, "_p4_val_")
                limpiar_session_state_prefijo(st.session_state, "p4_cal_")
                st.rerun()

        try:
            hojas = cm.listar_hojas(arch["bytes"], arch["nombre"])
        except (ValueError, RuntimeError) as exc:
            st.error(t("p4.validacion.error", err=exc))
            return
        except Exception as exc:  # archivo arbitrario del usuario
            st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
            return

        hoja = None
        c1, c2 = st.columns([3, 1])
        if hojas:
            with c1:
                hoja = st.selectbox(t("p2.medido.hoja.label"), options=hojas, key="p4_val_hoja")
        with c2:
            fila_enc = st.number_input(
                t("p2.medido.fila_enc.label"),
                min_value=0,
                value=0,
                step=1,
                key="p4_val_fila",
            )

        clave_tabla = (arch["hash"], hoja, int(fila_enc))
        cache = st.session_state.get("_p4_val_tabla_cache")
        if cache is None or cache[0] != clave_tabla:
            try:
                tabla = cm.leer_tabla(
                    arch["bytes"], arch["nombre"], hoja=hoja, fila_encabezado=fila_enc
                )
            except (ValueError, RuntimeError) as exc:
                st.error(t("p4.validacion.error", err=exc))
                return
            except Exception as exc:  # archivo arbitrario del usuario
                st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
                return
            st.session_state["_p4_val_tabla_cache"] = (clave_tabla, tabla)
            st.session_state.pop("p4_val_resultado", None)
        tabla = st.session_state["_p4_val_tabla_cache"][1]
        columnas = [str(c) for c in tabla.columns]

        with st.expander(t("p4.validacion.preview_titulo"), expanded=False):
            st.dataframe(tabla.head(12))

        # ---- señal a validar ----
        st.markdown(t("p4.validacion.mapeo.titulo"))
        col_ts = st.selectbox(
            t("p4.validacion.mapeo.timestamp"), options=columnas, key="p4_val_col_ts"
        )
        variable = st.selectbox(
            t("p4.validacion.mapeo.variable"),
            options=list(VARIABLES_CAMARA),
            format_func=lambda k: t(f"p4.validacion.variable.{k}"),
            key="p4_val_variable",
        )
        c_v, c_u = st.columns(2)
        with c_v:
            col_val = st.selectbox(
                t("p4.validacion.mapeo.valor"), options=columnas, key="p4_val_col_val"
            )
        with c_u:
            unidad = st.selectbox(
                t("p4.validacion.mapeo.unidad"),
                options=list(UNIDADES_REFERENCIA[variable]),
                format_func=lambda k: t(f"p4.validacion.unidad.{k}"),
                key=f"p4_val_unidad_{variable}",
            )
        masa_seca = None
        if variable == "masa_producto":
            masa_seca = st.number_input(
                t("p4.validacion.masa_seca.label"),
                min_value=0.001,
                value=1.0,
                step=0.1,
                format="%.3f",
                key="p4_val_masa_seca",
                help=t("p4.validacion.masa_seca.help"),
            )

        from ui.p2_emplazamiento import _ZONAS_HORARIAS

        empl_tz = getattr(proyecto.emplazamiento, "zona_horaria", None)
        c_z, c_c = st.columns(2)
        with c_z:
            zona = st.selectbox(
                t("p2.medido.tz.label"),
                options=_ZONAS_HORARIAS,
                index=(_ZONAS_HORARIAS.index(empl_tz) if empl_tz in _ZONAS_HORARIAS else 0),
                key="p4_val_zona",
            )
        with c_c:
            conv = st.radio(
                t("p2.medido.convencion.label"),
                options=list(CONVENCIONES_TIMESTAMP),
                format_func=lambda k: t(f"p2.medido.convencion.{k}"),
                horizontal=True,
                key="p4_val_conv",
            )

        fecha_fija = None
        if st.checkbox(t("p4.validacion.fecha_fija.check"), key="p4_val_usar_fecha"):
            from datetime import date as _date

            fecha_fija = st.date_input(
                t("p4.validacion.fecha_fija.label"),
                value=_date(2010, 5, 1),
                min_value=_date(1990, 1, 1),
                key="p4_val_fecha",
                help=t("p4.validacion.fecha_fija.help"),
            )

        # ---- aire de entrada (forzado de la cámara aislada) ----
        st.markdown(t("p4.validacion.aire.titulo"))
        c_t, c_h = st.columns(2)
        with c_t:
            col_t_ent = st.selectbox(
                t("p4.validacion.aire.t_ent"), options=columnas, key="p4_val_t_ent"
            )
        with c_h:
            col_hr_ent = st.selectbox(
                t("p4.validacion.aire.hr_ent"),
                options=_opciones_columna(columnas, t("p4.validacion.aire.hr_ent_sin")),
                key="p4_val_hr_ent",
            )
        hr_fija = None
        if col_hr_ent == t("p4.validacion.aire.hr_ent_sin"):
            hr_fija = (
                st.slider(
                    t("p4.validacion.aire.hr_fija"),
                    min_value=5,
                    max_value=95,
                    value=30,
                    key="p4_val_hr_fija",
                )
                / 100.0
            )

        c_q, c_qu = st.columns(2)
        with c_q:
            col_caudal = st.selectbox(
                t("p4.validacion.aire.caudal"),
                options=_opciones_columna(columnas, t("p4.validacion.aire.caudal_sin")),
                key="p4_val_caudal",
            )
        m_dot_fijo = None
        if col_caudal == t("p4.validacion.aire.caudal_sin"):
            with c_qu:
                m_dot_fijo = st.number_input(
                    t("p4.validacion.aire.caudal_fijo"),
                    min_value=0.001,
                    value=float(proyecto.camara.flujo.caudal_masico_kg_s),
                    step=0.01,
                    format="%.4f",
                    key="p4_val_mdot",
                )
            unidad_caudal = "kg_s"
        else:
            with c_qu:
                unidad_caudal = st.selectbox(
                    t("p4.validacion.aire.caudal_unidad"),
                    options=["kg_s", "m3_s", "m3_h"],
                    key="p4_val_uni_caudal",
                )

        c_ta, c_vv = st.columns(2)
        with c_ta:
            col_t_amb = st.selectbox(
                t("p4.validacion.aire.t_amb"),
                options=_opciones_columna(columnas, t("p4.validacion.aire.t_amb_sin")),
                key="p4_val_t_amb",
            )
        with c_vv:
            col_viento = st.selectbox(
                t("p4.validacion.aire.viento"),
                options=_opciones_columna(columnas, t("p4.validacion.aire.viento_sin")),
                key="p4_val_viento",
            )

        def _col_o_none(valor, etiqueta_vacia):
            return None if valor == etiqueta_vacia else valor

        if st.button(t("p4.validacion.procesar"), type="primary", key="p4_val_procesar"):
            try:
                with st.spinner(t("p4.validacion.spinner")):
                    cfg = _config_referencia_camara(
                        col_ts=col_ts,
                        col_val=col_val,
                        variable=variable,
                        unidad=unidad,
                        zona=zona,
                        conv=conv,
                        hoja=hoja,
                        fila_enc=fila_enc,
                        fecha_fija=fecha_fija,
                        masa_seca=masa_seca,
                    )
                    senal = ingerir_referencia(tabla, cfg)
                    fm = ingerir_forzantes_camara(
                        tabla,
                        cfg,
                        columna_T_ent=col_t_ent,
                        columna_HR_ent=_col_o_none(col_hr_ent, t("p4.validacion.aire.hr_ent_sin")),
                        HR_ent_fija=hr_fija,
                        columna_caudal=_col_o_none(col_caudal, t("p4.validacion.aire.caudal_sin")),
                        unidad_caudal=unidad_caudal,
                        m_dot_fijo_kg_s=m_dot_fijo,
                        columna_T_amb=_col_o_none(col_t_amb, t("p4.validacion.aire.t_amb_sin")),
                        columna_viento=_col_o_none(col_viento, t("p4.validacion.aire.viento_sin")),
                    )
                    resultado = simular_camara_aislada(proyecto.camara, fm.forzantes)
                    t_sim, y_sim = serie_simulada(resultado, variable, fm.t0_utc)
                    metricas, y_med, y_sim_al, ts = evaluar_ajuste(senal, t_sim, y_sim)
                st.session_state["p4_val_resultado"] = {
                    "senal": senal,
                    "forzantes": fm.forzantes,
                    "t0_utc": fm.t0_utc,
                    "advertencias": fm.advertencias,
                    "metricas": metricas,
                    "y_med": y_med,
                    "y_sim": y_sim_al,
                    "ts": ts,
                    "variable": variable,
                }
                st.session_state["_p4_val_hr_asumida"] = any(
                    "VREF_HR_ENT_ASUMIDA" in a for a in fm.advertencias
                )
                st.session_state.pop("p4_cal_resultado", None)
            except (ValueError, RuntimeError) as exc:
                st.error(t("p4.validacion.error", err=exc))
                st.session_state.pop("p4_val_resultado", None)
                return
            except Exception as exc:  # ingesta + simulación sobre datos arbitrarios
                st.error(t("comun.error_inesperado", tipo=type(exc).__name__, err=exc))
                st.session_state.pop("p4_val_resultado", None)
                return

        res = st.session_state.get("p4_val_resultado")
        if res is None:
            return

        senal = res["senal"]
        st.caption(
            t(
                "p4.validacion.senal_ok",
                n=int(senal.serie.notna().sum()),
                freq=f"{senal.frecuencia_nativa_s / 60:.0f}",
            )
        )
        for adv in senal.advertencias:
            st.warning(adv)
        if res["advertencias"]:
            st.markdown(t("p4.validacion.supuestos_titulo"))
            for adv in res["advertencias"]:
                st.caption(f"⚙️ {adv}")  # i18n: exento (código VREF_* de calculos/)

        if res["metricas"] is None:
            st.warning(t("p4.validacion.sin_solape"))
            return

        var = res["variable"]
        unidad_disp = unidad_display(var)
        st.plotly_chart(
            fig_overlay(
                res["ts"],
                a_display(res["y_med"], var),
                a_display(res["y_sim"], var),
                medido_lbl=t("p4.validacion.grafica.medido"),
                simulado_lbl=t("p4.validacion.grafica.simulado"),
                titulo=t(
                    "p4.validacion.grafica.titulo",
                    magnitud=t(f"p4.validacion.variable.{var}"),
                ),
                y_lbl=f"{t(f'p4.validacion.variable.{var}')} [{unidad_disp}]",
            ),
            width="stretch",
        )

        st.markdown(t("p4.validacion.metricas_titulo"))
        filas = filas_metricas(res["metricas"], unidad=unidad_disp)
        cols = st.columns(3)
        for i, (clave, valor, uni) in enumerate(filas):
            with cols[i % 3]:
                st.metric(
                    t(f"p4.validacion.metrica.{clave}"),
                    f"{valor:.3g}" + (f" {uni}" if uni else ""),
                )
        st.caption(t("p4.validacion.n_pares", n=int(res["metricas"].n_pares)))
        st.caption(t("p4.validacion.interpretacion"))
        st.caption(t("p4.validacion.aviso_cstr"))

        _render_calibracion_camara(proyecto, senal, res["forzantes"], res["t0_utc"])
        _render_cadena_completa(senal, var)
