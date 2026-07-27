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
from core.operacion import PoliticaRecarga
from core.proyecto import SubtipoGranEscala

if TYPE_CHECKING:
    from core.proyecto import Proyecto

_SEGUNDOS_POR_DIA: float = 86400.0
# Tope defensivo de lotes para evitar bucles si t_secado fuera ~0.
_MAX_BATCHES: int = 10_000
# Horizonte mínimo restante para intentar un lote más [s].
_HORIZONTE_MIN_BATCH_S: float = 1800.0  # 30 min


@dataclass(frozen=True)
class LoteVentana:
    """Un lote del encadenado BATCH, con su ubicación temporal en la ventana.

    Existe para que el llamador pueda **fechar** cada lote y atribuirlo a un
    período (el modo anual lo usa para desagregar la producción por mes). Los
    tiempos son relativos al inicio de la ventana; el instante absoluto se
    reconstruye con ``ResultadoVentana.t0_utc``.

    Attributes:
        indice: Orden del lote en la ventana, empezando en 0.
        t_inicio_s: Instante de carga, relativo al inicio de la ventana [s].
        t_fin_s: Instante de descarga (o de corte de la ventana si quedó
            incompleto), relativo al inicio [s].
        duracion_s: ``t_fin_s − t_inicio_s`` [s].
        masa_evaporada_kg: Agua evaporada durante este lote [kg].
        masa_seca_kg: Producto seco descargado [kg]. Cero si no se completó:
            un lote a medio secar no es producción.
        completo: True si alcanzó ``X_objetivo`` dentro de la ventana.
    """

    indice: int
    t_inicio_s: float
    t_fin_s: float
    duracion_s: float
    masa_evaporada_kg: float
    masa_seca_kg: float
    completo: bool


@dataclass
class ResultadoVentana:
    """Producción acumulada del secador de gran escala sobre la ventana.

    Attributes:
        subtipo: "BATCH" | "SEMICONTINUO".
        lotes: Historia lote a lote del encadenado (solo BATCH), en orden
            cronológico. Incluye el lote incompleto final si lo hubo.
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
        n_dias_salteados_pronostico: Días en que hubo oportunidad de cargar y no
            se cargó porque el día no llegaba al umbral de irradiación (solo
            BATCH, con ``PoliticaRecarga.exigir_pronostico``). Cero no significa
            que el criterio no se aplicó: significa que ningún día lo activó.
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
        cano_delta_T_media_K: ΔT térmica media del caño maestro sobre el lapso
            [K] (None sin caño maestro). Diagnóstico para el reporte.
        cano_delta_T_minima_K: ΔT mínima (peor pérdida) del caño maestro [K].
        cano_delta_P_Pa: Pérdida de carga del caño maestro al caudal del
            sistema [Pa] (flujo acumulado, ver ``cano_maestro_calc``).
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
    n_dias_salteados_pronostico: int = 0
    lotes: list["LoteVentana"] = field(default_factory=list)
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
    # Diagnósticos del caño maestro (para los exports; None sin caño).
    cano_delta_T_media_K: Optional[float] = None
    cano_delta_T_minima_K: Optional[float] = None
    cano_delta_P_Pa: Optional[float] = None
    status: str = ""
    advertencias: list[str] = field(default_factory=list)
    # Estados del aire para la carta psicrométrica del proceso (mejora 27).
    aire_T_amb_K: Optional[float] = None
    aire_T_ent_K: Optional[float] = None
    aire_omega_ent: Optional[float] = None
    aire_T_salida_K: Optional[float] = None
    aire_omega_salida: Optional[float] = None
    camara_directa: bool = False


# `PoliticaRecarga` nació acá en S57, pero es modelo de datos: cuelga de
# `Configuracion.politica_recarga`, viaja en el snapshot del proyecto y entra en la
# huella de vigencia (S59). Vive en `core/operacion.py`; se reexporta desde este
# módulo porque es su consumidor natural y hay código (y snapshots de tests) que la
# importa de acá.


def _proximo_instante_carga(
    t_fin_s: float, politica: PoliticaRecarga, hora_local_t0_h: float
) -> float:
    """Instante en que arranca el lote siguiente [s desde el inicio del lapso].

    Es el primer momento que cumple las dos condiciones: haber terminado la
    maniobra (``t_fin + maniobra_h``) y caer en la hora de carga del día.

    Args:
        t_fin_s: Instante de descarga del lote anterior [s].
        politica: Política de recarga.
        hora_local_t0_h: Hora local del día que corresponde a ``t = 0`` [h].

    Returns:
        Instante de carga [s]. Con la política inactiva, ``t_fin_s`` sin cambio.
    """
    if not politica.activa:
        return t_fin_s
    t_disponible = t_fin_s + politica.maniobra_h * 3600.0
    hora_actual = (hora_local_t0_h + t_disponible / 3600.0) % 24.0
    espera_h = (politica.hora_carga_h - hora_actual) % 24.0
    return t_disponible + espera_h * 3600.0


def _dia_local(t_s: float, hora_local_t0_h: float) -> int:
    """Índice de día local (0 = día en que arranca el lapso) del instante ``t_s``."""
    return int(np.floor((hora_local_t0_h + t_s / 3600.0) / 24.0))


def _energia_diaria_POA(fz: ForzantesAire, hora_local_t0_h: float) -> dict[int, float]:
    """Irradiación diaria en el plano del colector, por día local [MJ/m²·día].

    Es la magnitud con la que se decide si vale la pena cargar un lote: el
    recurso que va a tener el día, no la potencia instantánea del momento de
    cargar (a las 8 de la mañana el sol siempre es flojo).

    Se agrupa por **día local** y no por día UTC porque la jornada de trabajo
    del operador es local; el mismo criterio que usa la desagregación mensual
    del modo anual.

    Args:
        fz: Forzantes del lapso completo (usa ``I_g_POA_W_m2``).
        hora_local_t0_h: Hora local del día que corresponde a ``t = 0`` [h].

    Returns:
        ``{índice_de_día: MJ/m²}``. Dict vacío si no hay POA disponible —el
        llamador debe interpretarlo como "no se puede decidir", no como "día
        malo".
    """
    poa = getattr(fz, "I_g_POA_W_m2", None)
    if poa is None:
        return {}
    poa_arr = np.asarray(poa, dtype=float)
    t = np.asarray(fz.t_s, dtype=float)
    if t.size < 2 or poa_arr.size != t.size:
        return {}
    dt = float(t[1] - t[0])
    dias = np.floor((hora_local_t0_h + t / 3600.0) / 24.0).astype(int)
    poa_arr = np.nan_to_num(poa_arr, nan=0.0, posinf=0.0, neginf=0.0)
    return {int(d): float(poa_arr[dias == d].sum() * dt / 1e6) for d in np.unique(dias)}  # W→MJ


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
    hora_local_t0_h: float = 0.0,
) -> ResultadoVentana:
    """Acumula la producción del secador de gran escala sobre la ventana.

    Despacha según ``proyecto.configuracion.subtipo_gran_escala``.

    La rama BATCH encadena lotes, así que obedece la
    ``Configuracion.politica_recarga`` del proyecto — la misma que usa el modo
    anual. Hasta S58 este pipeline no la leía y quedaba clavado en los defaults
    del motor, sin ningún widget que la gobernara: misma física que el anual con
    la operación fija.

    Args:
        proyecto: Proyecto GRAN_ESCALA con cámara configurada.
        forzantes_base: Forzantes del aire sobre la ventana (T_ent = salida del
            colector/auxiliar; horizonte = duración de la ventana).
        P_Pa: Presión representativa [Pa].
        hora_local_t0_h: Hora local del día que corresponde a ``t = 0`` [h]. La
            política razona en hora local del sitio ("cargar a las 8" es 8 de la
            mañana en Salta, no en UTC), así que sin esta ancla la hora de carga
            se interpreta contra el inicio de la ventana.

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
        # El túnel no encadena lotes: avanza columnas por cadencia. La política
        # de recarga no aplica.
        return _simular_ventana_semicontinuo(proyecto, forzantes_base, P_Pa, res)
    return _simular_ventana_batch(
        proyecto,
        forzantes_base,
        P_Pa,
        res,
        getattr(cfg, "politica_recarga", None),
        hora_local_t0_h,
    )


def simular_encadenado_lotes(
    proyecto: "Proyecto",
    *,
    forzantes_base: ForzantesAire,
    P_Pa: float = 101325.0,
    politica: Optional[PoliticaRecarga] = None,
    hora_local_t0_h: float = 0.0,
) -> ResultadoVentana:
    """Encadena lotes sobre las forzantes, **sin** depender de la tipología.

    Misma física que la rama BATCH de :func:`simular_ventana`, pero sin leer
    ``configuracion.subtipo_gran_escala`` — que solo existe en GRAN_ESCALA. El
    modo anual la usa para CAJA / ARMARIO / GRAN_ESCALA-BATCH por igual: el
    encadenado de lotes no es una particularidad del secador industrial, es
    cómo opera cualquier secador batch.

    Args:
        proyecto: Proyecto con cámara configurada.
        forzantes_base: Forzantes del aire sobre el horizonte completo.
        P_Pa: Presión representativa [Pa].

    Returns:
        ``ResultadoVentana`` con ``lotes`` poblado.
    """
    camara = proyecto.camara
    horizonte_s = float(forzantes_base.t_s[-1] - forzantes_base.t_s[0])
    res = ResultadoVentana(subtipo="BATCH", horizonte_s=horizonte_s)

    if camara is None:
        res.status = "error"
        res.advertencias.append("VENTANA_SIN_CAMARA: la simulación requiere cámara.")
        return res

    res.aire_T_amb_K, res.aire_T_ent_K, res.aire_omega_ent = _estado_aire_repr(forzantes_base)
    res.camara_directa = (
        getattr(getattr(camara, "construccion", None), "cubierta_translucida_id", None) is not None
    )
    return _simular_ventana_batch(proyecto, forzantes_base, P_Pa, res, politica, hora_local_t0_h)


def _simular_ventana_batch(
    proyecto: "Proyecto",
    forzantes_base: ForzantesAire,
    P_Pa: float,
    res: ResultadoVentana,
    politica: Optional[PoliticaRecarga] = None,
    hora_local_t0_h: float = 0.0,
) -> ResultadoVentana:
    """Encadena lotes sobre la ventana.

    Cada lote arranca cuando la :class:`PoliticaRecarga` lo permite: por defecto
    a la hora de carga del día siguiente a la descarga, no en el instante exacto
    en que el anterior terminó. Con ``politica.activa = False`` se recupera el
    encadenado inmediato, que es una cota superior de producción.
    """
    camara = proyecto.camara
    p = camara.carga_producto
    m_seco_total = p.masa_total_kg / (1.0 + p.humedad_inicial_X)
    masa_seca_por_lote = m_seco_total * (1.0 + p.humedad_objetivo_X)
    politica = politica if politica is not None else PoliticaRecarga()

    horizonte_s = res.horizonte_s
    # Primer lote: también respeta la hora de carga (arrancar a medianoche del
    # 1-1 sería el mismo artificio que recargar a las 3 AM).
    t_now = _proximo_instante_carga(0.0, politica, hora_local_t0_h) if politica.activa else 0.0
    t_ciclos: list[float] = []
    t_secados: list[float] = []
    masa_seca = 0.0
    masa_evap = 0.0
    n_batches = 0
    lotes: list[LoteVentana] = []
    # Advertencias agregadas por código (ver el bucle): cuántos lotes las
    # dispararon y el primer mensaje de cada una como muestra.
    conteo_codigo: dict[str, int] = {}
    ejemplo_codigo: dict[str, str] = {}
    n_lotes_intentados = 0

    # Irradiación diaria del lapso, para la decisión de cargar (pronóstico).
    # Se calcula una vez: es una reducción del array de POA, no depende del lote.
    energia_dia = (
        _energia_diaria_POA(forzantes_base, hora_local_t0_h) if politica.exigir_pronostico else {}
    )
    pronostico_evaluable = bool(energia_dia)
    if politica.exigir_pronostico and not pronostico_evaluable:
        res.advertencias.append(
            "VENTANA_PRONOSTICO_SIN_POA: se pidió no cargar lotes en días de mal "
            "pronóstico, pero las forzantes no traen irradiación en el plano del "
            "colector. Se cargan todos los días (el criterio no se aplicó)."
        )
    n_dias_salteados = 0

    while t_now < horizonte_s and n_batches < _MAX_BATCHES:
        if (horizonte_s - t_now) < _HORIZONTE_MIN_BATCH_S:
            break
        # ¿Conviene cargar hoy? Un operador no llena el secador un día que viene
        # nublado: el lote se arrastra sin terminar y ocupa la cámara. Saltear
        # esos días es lo que separa "el modelo carga siempre" de la operación
        # real (S58). Nótese que la decisión usa el clima que efectivamente va a
        # ocurrir — pronóstico perfecto, ver PoliticaRecarga.
        if pronostico_evaluable:
            dia = _dia_local(t_now, hora_local_t0_h)
            if energia_dia.get(dia, 0.0) < politica.umbral_pronostico_MJ_m2:
                t_now += _SEGUNDOS_POR_DIA
                n_dias_salteados += 1
                continue
        fz = _slice_forzantes(forzantes_base, t_now)
        if fz is None:
            break
        T_ref, HR_ref = _T_HR_referencia(fz, P_Pa)
        T_amb_ref = float(np.mean(fz.T_amb_K))
        n_lotes_intentados += 1
        sub = calcular_camara(
            camara=camara,
            T_operacion_K=T_ref,
            HR_operacion=HR_ref,
            T_amb_K=T_amb_ref,
            P_Pa=P_Pa,
            t_max_s=float(fz.t_s[-1]),
            forzantes_aire=fz,
        )
        # Agregación por CÓDIGO, no por string exacto: los mensajes llevan el
        # número de horas del lote ("... durante 5.6 h"), así que deduplicar por
        # igualdad no filtra nada — sobre un año de 52 lotes eso inundaba la
        # pantalla con ~100 avisos casi idénticos (S57).
        for a in sub.advertencias:
            codigo = a.split(":", 1)[0].strip()
            conteo_codigo[codigo] = conteo_codigo.get(codigo, 0) + 1
            if codigo not in ejemplo_codigo:
                ejemplo_codigo[codigo] = a

        if sub.status == "X_obj_alcanzado" and sub.t_secado_s is not None:
            masa_seca += masa_seca_por_lote
            masa_evap += float(sub.masa_evaporada_total_kg)
            t_secados.append(float(sub.t_secado_s))
            t_fin = t_now + float(sub.t_secado_s)
            lotes.append(
                LoteVentana(
                    indice=n_batches,
                    t_inicio_s=t_now,
                    t_fin_s=t_fin,
                    duracion_s=float(sub.t_secado_s),
                    masa_evaporada_kg=float(sub.masa_evaporada_total_kg),
                    masa_seca_kg=masa_seca_por_lote,
                    completo=True,
                )
            )
            # El ciclo es secado + espera hasta la próxima hora de carga: es lo
            # que gobierna la tasa de régimen, no el secado solo.
            t_siguiente = _proximo_instante_carga(t_fin, politica, hora_local_t0_h)
            t_ciclos.append(t_siguiente - t_now)
            t_now = t_siguiente
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
            # Se registra igual: su agua evaporada cuenta y su existencia es
            # información (el anual reporta lotes frustrados), pero no aporta
            # producto seco.
            masa_evap += float(sub.masa_evaporada_total_kg)
            lotes.append(
                LoteVentana(
                    indice=n_batches,
                    t_inicio_s=t_now,
                    t_fin_s=horizonte_s,
                    duracion_s=max(0.0, horizonte_s - t_now),
                    masa_evaporada_kg=float(sub.masa_evaporada_total_kg),
                    masa_seca_kg=0.0,
                    completo=False,
                )
            )
            res.batch_en_progreso = True
            break

    # Un aviso por código, con cuántos lotes lo dispararon. Sobre un año son
    # decenas de lotes: repetir el mismo diagnóstico por cada uno esconde los
    # avisos que sí son distintos.
    for codigo, n_veces in conteo_codigo.items():
        mensaje = ejemplo_codigo[codigo]
        if n_veces > 1:
            mensaje += (
                f" · Se repitió en {n_veces} de {n_lotes_intentados} lotes "
                "(se muestra el primero)."
            )
        res.advertencias.append(mensaje)

    res.lotes = lotes
    res.n_dias_salteados_pronostico = n_dias_salteados
    res.n_batches_completos = n_batches
    res.masa_seca_producida_kg = masa_seca
    res.masa_evaporada_kg = masa_evap
    if t_secados:
        t_medio = float(np.mean(t_secados))
        res.t_secado_medio_s = t_medio
        # Tasa de régimen: un lote por **ciclo**, y el ciclo incluye la espera
        # hasta la próxima hora de carga. Usar solo el tiempo de secado
        # sobrestimaría la producción sostenible en la fracción ociosa.
        t_ciclo_medio = float(np.mean(t_ciclos)) if t_ciclos else t_medio
        res.tasa_regimen_kg_dia = masa_seca_por_lote / (t_ciclo_medio / _SEGUNDOS_POR_DIA)
        res.status = "ok"
    else:
        res.status = "sin_lotes_completos"
        if n_lotes_intentados == 0 and n_dias_salteados > 0:
            # Distinguir "el secador no seca" de "nunca se dio la orden de
            # cargar": el diagnóstico y la corrección son distintos.
            res.advertencias.append(
                f"VENTANA_PRONOSTICO_BLOQUEA_TODO: no se cargó ningún lote porque "
                f"ninguno de los {n_dias_salteados} días del lapso llegó a "
                f"{politica.umbral_pronostico_MJ_m2:.1f} MJ/m² sobre el plano del "
                "colector. Bajá el umbral de pronóstico o revisá el recurso solar "
                "del sitio y la orientación del colector."
            )
        else:
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
