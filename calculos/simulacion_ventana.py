"""Orquestador de ventana — simulación de producción sobre un lapso [inicio, fin].

Para tipología GRAN_ESCALA (S40). Sobre una ventana de producción (clima real
horario, modo VENTANA) acumula la producción del secador según el subtipo:

- **BATCH**: encadena lotes. Corre el motor termodinámico batch; cada vez que el
  producto alcanza X_objetivo cuenta un lote completo, recarga producto fresco
  y continúa con el clima restante de la ventana (recarga *event-driven*).
- **SEMICONTINUO**: corre el túnel a contracorriente (``simular_cascada`` vía
  ``calcular_camara_cascada``) una vez sobre toda la ventana; el producto avanza
  a cadencia fija y la sequedad de salida es emergente.

Métrica de salida: masa de producto seco acumulada en la ventana + tasa de
régimen sostenible (kg/día) + masa evaporada. El consumo de leña del híbrido se
integra en la Fase 4 (hoy queda en 0).

Este módulo recibe las forzantes del aire ya armadas sobre la ventana (T_ent =
salida del colector/auxiliar). El armado de forzantes desde clima real NASA
POWER vive en el wire-up de UI/balance (consume ``clima_calc`` +
``_correr_colector_horizonte``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

from calculos.camara_calc import calcular_camara, calcular_camara_cascada
from calculos.psicrometria import HR_desde_omega
from core.camara import ForzantesAire
from core.proyecto import SubtipoGranEscala

if TYPE_CHECKING:
    from core.proyecto import Proyecto

_SEGUNDOS_POR_DIA: float = 86400.0
# Tope defensivo de lotes para evitar bucles si t_secado fuera ~0.
_MAX_BATCHES: int = 10_000
# Horizonte mínimo restante para intentar un lote más [s].
_HORIZONTE_MIN_BATCH_S: float = 1800.0  # 30 min


@dataclass
class ResultadoVentana:
    """Producción acumulada del secador de gran escala sobre la ventana.

    Attributes:
        subtipo: "BATCH" | "SEMICONTINUO".
        horizonte_s: Duración de la ventana simulada [s].
        masa_seca_producida_kg: Masa de producto seco (a su X de salida)
            producida en la ventana [kg].
        masa_evaporada_kg: Agua total evaporada en la ventana [kg].
        tasa_regimen_kg_dia: Tasa sostenible de producto seco [kg/día] en
            régimen. None si no se alcanzó régimen.
        n_batches_completos: Lotes completos (solo BATCH).
        t_secado_medio_s: Tiempo medio de secado de un lote [s] (solo BATCH).
        batch_en_progreso: True si al final de la ventana quedó un lote sin
            completar (solo BATCH).
        n_avances: Columnas descargadas (solo SEMICONTINUO).
        X_salida_regimen: Humedad de salida en régimen (solo SEMICONTINUO).
        throughput_fresco_kg_dia: Caudal de producto fresco procesado [kg/día]
            (solo SEMICONTINUO).
        perfil_X_zonas: Perfil espacial de X por zona (solo SEMICONTINUO).
        perfil_T_aire_zonas_K: Perfil de T del aire por zona (solo SEMICONTINUO).
        perfil_omega_aire_zonas: Perfil de ω del aire por zona (solo SEMICONTINUO).
        X_salida_por_avance: X del producto descargado en cada avance [kg/kg seco].
        T_prod_salida_por_avance_K: T del producto descargado en cada avance [K].
        intervalo_avance_s: Cadencia de avance [s] (para fechar cada descarga).
        t0_utc: Instante absoluto del inicio del lapso (ancla de las descargas).
        lena_consumida_kg: Leña consumida por el híbrido [kg] (Fase 4; hoy 0).
        status: Estado global.
        advertencias: Mensajes integrados.
        aire_T_amb_K, aire_T_ent_K, aire_omega_ent: Estado del aire ambiente y de
            entrada (a la cámara/túnel) en el instante representativo de POA
            máxima — para la carta psicrométrica del proceso (mejora 27).
        aire_T_salida_K, aire_omega_salida: Estado del aire a la salida de la
            cámara (solo BATCH; en SEMICONTINUO el path sale del perfil de zonas).
        camara_directa: True si la cámara recibe radiación (techo translúcido).
    """

    subtipo: str
    horizonte_s: float
    masa_seca_producida_kg: float = 0.0
    masa_evaporada_kg: float = 0.0
    tasa_regimen_kg_dia: Optional[float] = None
    # BATCH
    n_batches_completos: int = 0
    t_secado_medio_s: Optional[float] = None
    batch_en_progreso: bool = False
    # SEMICONTINUO
    n_avances: int = 0
    X_salida_regimen: Optional[float] = None
    throughput_fresco_kg_dia: Optional[float] = None
    perfil_X_zonas: Optional[np.ndarray] = None
    perfil_T_aire_zonas_K: Optional[np.ndarray] = None
    perfil_omega_aire_zonas: Optional[np.ndarray] = None
    # Descargas del túnel: una columna por avance. Es la comparación lagrangiana
    # natural contra un muestreo de campo (lo que sale del túnel), y lo único
    # fechable sin historia por zona (mejora 38, fase 4).
    X_salida_por_avance: Optional[np.ndarray] = None
    T_prod_salida_por_avance_K: Optional[np.ndarray] = None
    intervalo_avance_s: Optional[float] = None
    t0_utc: Optional[object] = None
    # Común
    lena_consumida_kg: float = 0.0
    status: str = ""
    advertencias: list[str] = field(default_factory=list)
    # Estados del aire para la carta psicrométrica del proceso (mejora 27).
    aire_T_amb_K: Optional[float] = None
    aire_T_ent_K: Optional[float] = None
    aire_omega_ent: Optional[float] = None
    aire_T_salida_K: Optional[float] = None
    aire_omega_salida: Optional[float] = None
    camara_directa: bool = False


def _slice_forzantes(fz: ForzantesAire, t0_s: float) -> Optional[ForzantesAire]:
    """Recorta las forzantes desde ``t0_s`` en adelante, re-zerando el tiempo.

    Interpola el estado en ``t0_s`` como primer punto. Devuelve None si no queda
    horizonte útil (``t0_s`` ≥ último tiempo).
    """
    t = np.asarray(fz.t_s, dtype=float)
    if t0_s >= t[-1]:
        return None
    mask = t > t0_s

    def _cut(arr: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if arr is None:
            return None
        arr = np.asarray(arr, dtype=float)
        head = float(np.interp(t0_s, t, arr))
        return np.concatenate([[head], arr[mask]])

    t_abs = np.concatenate([[t0_s], t[mask]])
    return ForzantesAire(
        t_s=t_abs - t0_s,
        T_ent_K=_cut(fz.T_ent_K),
        omega_ent=_cut(fz.omega_ent),
        m_dot_aire_seco_kg_s=_cut(fz.m_dot_aire_seco_kg_s),
        T_amb_K=_cut(fz.T_amb_K),
        v_viento_ms=_cut(fz.v_viento_ms),
        I_g_W_m2=_cut(fz.I_g_W_m2),
        I_g_POA_W_m2=_cut(fz.I_g_POA_W_m2),
    )


def _T_HR_referencia(fz: ForzantesAire, P_Pa: float) -> tuple[float, float]:
    """T y HR de referencia (medias de la forzante) para el wire-up de cámara."""
    T_ref = float(np.mean(fz.T_ent_K))
    omega_ref = float(np.mean(fz.omega_ent))
    try:
        HR_ref = max(0.05, min(0.95, HR_desde_omega(omega_ref, T_ref, P_Pa)))
    except Exception:
        HR_ref = 0.20
    return T_ref, HR_ref


def _estado_aire_repr(fz: ForzantesAire) -> tuple[float, float, float]:
    """Estado del aire de entrada en el instante representativo (POA máxima).

    Devuelve ``(T_amb_K, T_ent_K, omega_ent)`` para la carta psicrométrica del
    proceso. Usa el bin de máxima irradiancia POA (≈ mediodía solar / pico de
    operación); fallback al punto medio si no hay POA.
    """
    poa = getattr(fz, "I_g_POA_W_m2", None)
    if poa is not None and len(poa) > 0 and np.any(np.isfinite(poa)):
        idx = int(np.nanargmax(poa))
    else:
        idx = len(fz.t_s) // 2
    return (
        float(fz.T_amb_K[idx]),
        float(fz.T_ent_K[idx]),
        float(fz.omega_ent[idx]),
    )


def simular_ventana(
    proyecto: "Proyecto",
    *,
    forzantes_base: ForzantesAire,
    P_Pa: float = 101325.0,
) -> ResultadoVentana:
    """Acumula la producción del secador de gran escala sobre la ventana.

    Despacha según ``proyecto.configuracion.subtipo_gran_escala``.

    Args:
        proyecto: Proyecto GRAN_ESCALA con cámara configurada.
        forzantes_base: Forzantes del aire sobre la ventana (T_ent = salida del
            colector/auxiliar; horizonte = duración de la ventana).
        P_Pa: Presión representativa [Pa].

    Returns:
        ResultadoVentana con producción acumulada, tasa de régimen y diagnósticos.
    """
    cfg = proyecto.configuracion
    camara = proyecto.camara
    horizonte_s = float(forzantes_base.t_s[-1] - forzantes_base.t_s[0])
    subtipo = cfg.subtipo_gran_escala

    res = ResultadoVentana(subtipo=subtipo.value, horizonte_s=horizonte_s)

    if camara is None:
        res.status = "error"
        res.advertencias.append("VENTANA_SIN_CAMARA: la simulación requiere cámara.")
        return res

    # Estado del aire de entrada (representativo, para la carta psicrométrica).
    res.aire_T_amb_K, res.aire_T_ent_K, res.aire_omega_ent = _estado_aire_repr(forzantes_base)
    res.camara_directa = (
        getattr(getattr(camara, "construccion", None), "cubierta_translucida_id", None) is not None
    )

    if subtipo == SubtipoGranEscala.SEMICONTINUO:
        return _simular_ventana_semicontinuo(proyecto, forzantes_base, P_Pa, res)
    return _simular_ventana_batch(proyecto, forzantes_base, P_Pa, res)


def _simular_ventana_batch(
    proyecto: "Proyecto",
    forzantes_base: ForzantesAire,
    P_Pa: float,
    res: ResultadoVentana,
) -> ResultadoVentana:
    """Encadena lotes sobre la ventana (recarga event-driven al alcanzar X_obj)."""
    camara = proyecto.camara
    p = camara.carga_producto
    m_seco_total = p.masa_total_kg / (1.0 + p.humedad_inicial_X)
    masa_seca_por_lote = m_seco_total * (1.0 + p.humedad_objetivo_X)

    horizonte_s = res.horizonte_s
    t_now = 0.0
    t_secados: list[float] = []
    masa_seca = 0.0
    masa_evap = 0.0
    n_batches = 0
    vistos: set[str] = set()

    while t_now < horizonte_s and n_batches < _MAX_BATCHES:
        if (horizonte_s - t_now) < _HORIZONTE_MIN_BATCH_S:
            break
        fz = _slice_forzantes(forzantes_base, t_now)
        if fz is None:
            break
        T_ref, HR_ref = _T_HR_referencia(fz, P_Pa)
        T_amb_ref = float(np.mean(fz.T_amb_K))
        sub = calcular_camara(
            camara=camara,
            T_operacion_K=T_ref,
            HR_operacion=HR_ref,
            T_amb_K=T_amb_ref,
            P_Pa=P_Pa,
            t_max_s=float(fz.t_s[-1]),
            forzantes_aire=fz,
        )
        for a in sub.advertencias:
            if a not in vistos:
                vistos.add(a)
                res.advertencias.append(a)

        if sub.status == "X_obj_alcanzado" and sub.t_secado_s is not None:
            masa_seca += masa_seca_por_lote
            masa_evap += float(sub.masa_evaporada_total_kg)
            t_secados.append(float(sub.t_secado_s))
            t_now += float(sub.t_secado_s)
            n_batches += 1
            # Salida de cámara representativa (primer lote, instante de máxima
            # evaporación) — para la carta psicrométrica del proceso.
            if res.aire_T_salida_K is None:
                m_dot_w = np.asarray(getattr(sub, "m_dot_w_kg_s", []), dtype=float)
                if m_dot_w.size > 0 and np.any(np.isfinite(m_dot_w)):
                    j = int(np.nanargmax(m_dot_w))
                    res.aire_T_salida_K = float(np.asarray(sub.T_flujo_K)[j])
                    res.aire_omega_salida = float(np.asarray(sub.omega_flujo_kg_kg)[j])
        else:
            # No completó en el clima restante → lote en progreso al cierre.
            masa_evap += float(sub.masa_evaporada_total_kg)
            res.batch_en_progreso = True
            break

    res.n_batches_completos = n_batches
    res.masa_seca_producida_kg = masa_seca
    res.masa_evaporada_kg = masa_evap
    if t_secados:
        t_medio = float(np.mean(t_secados))
        res.t_secado_medio_s = t_medio
        # Tasa de régimen: un lote cada t_secado_medio.
        res.tasa_regimen_kg_dia = masa_seca_por_lote / (t_medio / _SEGUNDOS_POR_DIA)
        res.status = "ok"
    else:
        res.status = "sin_lotes_completos"
        res.advertencias.append(
            "VENTANA_BATCH_SIN_LOTES: ningún lote alcanzó X_objetivo dentro de la "
            "ventana. Ampliá la ventana o revisá las condiciones de secado."
        )
    return res


def _simular_ventana_semicontinuo(
    proyecto: "Proyecto",
    forzantes_base: ForzantesAire,
    P_Pa: float,
    res: ResultadoVentana,
) -> ResultadoVentana:
    """Corre el túnel a contracorriente una vez sobre la ventana."""
    camara = proyecto.camara
    if camara.tunel is None:
        res.status = "error"
        res.advertencias.append(
            "VENTANA_SEMICONTINUO_SIN_TUNEL: el subtipo SEMICONTINUO requiere "
            "camara.tunel (ConfiguracionTunel) configurado."
        )
        return res

    T_ref, HR_ref = _T_HR_referencia(forzantes_base, P_Pa)
    T_amb_ref = float(np.mean(forzantes_base.T_amb_K))
    cas = calcular_camara_cascada(
        camara,
        T_operacion_K=T_ref,
        HR_operacion=HR_ref,
        T_amb_K=T_amb_ref,
        P_Pa=P_Pa,
        forzantes_aire=forzantes_base,
    )
    res.advertencias.extend(cas.advertencias)
    res.n_avances = cas.n_avances
    res.X_salida_regimen = cas.X_salida_regimen
    res.masa_seca_producida_kg = float(cas.masa_seca_producida_total_kg)
    res.masa_evaporada_kg = float(cas.masa_evaporada_total_kg)
    res.perfil_X_zonas = cas.X_perfil_zonas
    res.perfil_T_aire_zonas_K = cas.T_aire_perfil_zonas_K
    res.perfil_omega_aire_zonas = cas.omega_aire_perfil_zonas
    res.X_salida_por_avance = cas.X_salida_por_avance
    res.T_prod_salida_por_avance_K = cas.T_prod_salida_por_avance_K
    res.intervalo_avance_s = float(cas.intervalo_avance_s)
    res.t0_utc = getattr(forzantes_base, "t0_utc", None)
    res.throughput_fresco_kg_dia = cas.throughput_fresco_kg_s * _SEGUNDOS_POR_DIA

    if cas.X_salida_regimen is not None:
        tun = camara.tunel
        m_seco_col = (
            camara.carga_producto.masa_total_kg
            / (1.0 + camara.carga_producto.humedad_inicial_X)
            / tun.n_zonas
        )
        masa_seca_por_columna = m_seco_col * (1.0 + cas.X_salida_regimen)
        res.tasa_regimen_kg_dia = masa_seca_por_columna / (
            tun.intervalo_avance_s / _SEGUNDOS_POR_DIA
        )
        res.status = "regimen_alcanzado"
    else:
        res.status = "llenando"
    return res
