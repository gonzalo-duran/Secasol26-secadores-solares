"""
Modo anual sobre las 8760 h reales del clima.

Reemplaza al esquema de "12 días típicos mensuales" (módulo
``calculos/operacion_anual_camara.py``, eliminado en S57) por una simulación
continua sobre la serie horaria del año: el secador encadena lotes uno tras
otro, cada uno con el clima que efectivamente le tocó, y la producción se
atribuye al mes en que cada lote se descarga.

**Qué gana el usuario respecto del día típico.** El día típico
(``groupby(hour).mean()``) construye un día que nunca está nublado, y el secado
es no lineal: un lote que en el día promedio de julio cierra en 30 h puede no
cerrar nunca durante una racha de mal tiempo. Acá eso aparece: los lotes se
alargan, y los que no llegan quedan contados como frustrados. Además la cantidad
de lotes deja de ser un dato que el usuario asegura (``batches_por_mes``) y pasa
a ser un **resultado**.

**Convención de atribución mensual.** Un lote se cuenta en el mes en que
**termina**, porque es cuando se descarga el producto. Un lote que arranca el 29
de junio y sale el 2 de julio es producción de julio. La energía solar, en
cambio, se integra por mes calendario sobre las horas de ese mes, porque es un
flujo y no un evento.

**Alcance.** El anual simula **encadenado de lotes**, que es cómo opera un
secador batch (tipologías CAJA, ARMARIO y GRAN_ESCALA/BATCH). El túnel
semicontinuo tiene una operación conceptualmente distinta —flujo continuo con
avance de columnas, sin lotes— y no está cubierto todavía; se rechaza con un
error explícito en vez de devolver un número sin sentido.

Ver ``docs/notas/plan_anual_8760.md`` §4 para los límites físicos del modelo
(CSTR de nodo único, colector cuasi-estacionario, y sobre todo: el operador
decide con **pronóstico perfecto**, así que el resultado es la cota superior de
la buena decisión).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from core.proyecto import Proyecto

_SEGUNDOS_POR_HORA: float = 3600.0
_MESES: tuple[int, ...] = tuple(range(1, 13))

# Irradiación diaria mínima para considerar un día "operable" [MJ/m²·día].
# ≈ 2.2 kWh/m²·día, mínimo práctico para que un secador solar haga algo útil.
# Hereda el valor del campo `I_g_diaria_minima_MJ_m2` que el modo anual anterior
# declaraba y validaba pero nunca llegaba a usar (S57).
UMBRAL_DIA_OPERABLE_MJ_M2: float = 8.0

# Temperatura de referencia para el calor latente en las eficiencias [K].
# Mismo criterio que usaba el modo anual anterior (50 °C, evaporación típica en
# cámara); h_fg varía < 3 % en el rango 40-60 °C, así que la elección no cambia
# las conclusiones.
_T_EVAP_REF_K: float = 323.15


@dataclass(frozen=True)
class PuntoMensualAnual:
    """Producción y energía atribuidas a un mes calendario.

    Attributes:
        mes: 1..12.
        lotes_completos: Lotes descargados en el mes.
        lotes_frustrados: Lotes que terminaron el mes sin alcanzar X_objetivo.
        masa_seca_kg: Producto seco descargado en el mes [kg].
        masa_evaporada_kg: Agua evaporada por los lotes atribuidos al mes [kg].
        duracion_media_h: Duración media de los lotes completos del mes [h].
            None si no se completó ninguno.
        E_solar_MJ: Energía solar sobre el plano del colector durante las horas
            del mes [MJ]. Se integra por mes calendario, no por lote.
        E_auxiliar_MJ: Energía que el auxiliar entregó al aire durante las horas
            del mes [MJ]. Mismo criterio de integración que la solar: es un
            flujo. Cero sin auxiliar.
        horas: Horas de clima que el mes aportó a la simulación.
        dias_operables: Días del mes cuya irradiación diaria sobre el plano del
            colector superó el umbral de operabilidad.
        dias: Días de clima que el mes aportó.
        eta_drying: Fracción de la radiación incidente del mes convertida en
            evaporación (Augustus Leon). None si no hubo sol.
        energia_especifica_MJ_kg: Energía solar incidente por kg de agua
            evaporada en el mes [MJ/kg]. None si no se evaporó nada.
    """

    mes: int
    lotes_completos: int = 0
    lotes_frustrados: int = 0
    masa_seca_kg: float = 0.0
    masa_evaporada_kg: float = 0.0
    duracion_media_h: Optional[float] = None
    E_solar_MJ: float = 0.0
    E_auxiliar_MJ: float = 0.0
    horas: int = 0
    dias_operables: int = 0
    dias: int = 0
    eta_drying: Optional[float] = None
    energia_especifica_MJ_kg: Optional[float] = None


@dataclass(frozen=True)
class ResultadosAnual:
    """Resultado del año completo simulado hora a hora.

    Attributes:
        puntos_mensuales: Los 12 meses, en orden.
        masa_seca_anual_kg: Producto seco total del año [kg]. **Es producto
            seco**, no agua evaporada: la confusión entre ambos era el problema
            principal del modo anual anterior.
        masa_evaporada_anual_kg: Agua total evaporada en el año [kg].
        n_lotes_completos: Lotes descargados en el año.
        n_lotes_frustrados: Lotes iniciados que no alcanzaron X_objetivo.
        duracion_media_h / duracion_p50_h / duracion_p90_h: Duración de los
            lotes completos [h]. La dispersión (p50 vs p90) es lo que el día
            típico borraba: con un día promedio todos los lotes duran igual.
        E_solar_anual_MJ: Energía solar **incidente** sobre el plano del
            colector en el año [MJ].
        Q_util_colector_MJ: Energía que el colector efectivamente entregó al
            aire [MJ]. Es la magnitud comparable con la del auxiliar.
        E_auxiliar_MJ: Energía que el auxiliar entregó al aire [MJ].
        fraccion_solar: ``Q_util_colector / (Q_util_colector + E_aux)``. Compara
            energías **útiles**, no la irradiancia incidente contra el auxiliar
            —que serían magnitudes distintas—. None sin energía entregada.
        eta_drying_anual: Fracción de la radiación incidente del año convertida
            en evaporación (Augustus Leon). None si no hubo sol.
        eta_total_anual: Igual pero contra la energía primaria total
            (solar incidente + auxiliar). Con auxiliar apagado coincide con
            ``eta_drying_anual``; con auxiliar activo se separan.
        aprovechamiento_aire: Fracción de la capacidad de carga de humedad del
            aire que efectivamente se usó:
            ``m_evap / (ṁ·∫(ω_sat(T_ent) − ω_ent) dt)`` sobre las horas de
            operación.

            **No es el η_pickup de Augustus Leon y no debe compararse con los
            valores de esa literatura** (típicamente 5-30 %). Aquel está
            definido por lote y en condiciones de secado activo; este integra el
            déficit de saturación sobre *todas* las horas de operación,
            incluidas las noches y el tramo final del lote, cuando el aire sigue
            circulando y el producto ya casi no entrega agua. Por eso da valores
            mucho más bajos. Lo que mide es útil —cuánto se desaprovecha el aire
            que se hace circular— pero es otra cosa, y se nombra distinto a
            propósito (S57).
        energia_especifica_MJ_kg: Energía solar incidente por kg de agua
            evaporada [MJ/kg]. Métrica de comparación estándar entre secadores.
        dias_operables: Días del año con irradiación diaria sobre el umbral.
        umbral_dia_operable_MJ_m2: Umbral usado [MJ/m²·día].
        dias_salteados_pronostico: Días en que el secador estaba libre y no se
            cargó lote porque el día no llegaba al umbral de pronóstico. Es
            **decisión de operación**, no disponibilidad del recurso: se lee
            junto a ``dias_operables`` (cuántos días el sol alcanzaba) para
            separar "no había sol" de "había sol pero el secador estaba ocupado".
        lena_consumida_kg: Leña del auxiliar en el año [kg].
        horas_simuladas: Horas de clima efectivamente simuladas.
        area_colector_m2: Área del banco usada para integrar la energía solar.
        superficie_n_solves: Solves del colector que costó la superficie de
            respuesta (diagnóstico de performance).
        status: "ok" | "sin_lotes_completos" | "error".
        advertencias: Mensajes integrados de toda la cadena.
    """

    puntos_mensuales: list[PuntoMensualAnual]
    masa_seca_anual_kg: float = 0.0
    masa_evaporada_anual_kg: float = 0.0
    n_lotes_completos: int = 0
    n_lotes_frustrados: int = 0
    duracion_media_h: Optional[float] = None
    duracion_p50_h: Optional[float] = None
    duracion_p90_h: Optional[float] = None
    E_solar_anual_MJ: float = 0.0
    Q_util_colector_MJ: float = 0.0
    E_auxiliar_MJ: float = 0.0
    fraccion_solar: Optional[float] = None
    eta_drying_anual: Optional[float] = None
    eta_total_anual: Optional[float] = None
    aprovechamiento_aire: Optional[float] = None
    energia_especifica_MJ_kg: Optional[float] = None
    dias_operables: int = 0
    umbral_dia_operable_MJ_m2: float = 0.0
    dias_salteados_pronostico: int = 0
    lena_consumida_kg: float = 0.0
    horas_simuladas: int = 0
    area_colector_m2: float = 0.0
    superficie_n_solves: int = 0
    status: str = ""
    advertencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Vigencia del resultado
# ---------------------------------------------------------------------------


#: Secciones del proyecto que determinan el resultado anual. Las tres primeras
#: entran al balance; el emplazamiento fija la posición solar y la presión, y la
#: configuración, la tipología y el modo con el que se corrió el año.
SECCIONES_ANUAL = ("configuracion", "emplazamiento", "colector", "camara", "auxiliar")


def _politica_del_proyecto(proyecto: "Proyecto", explicita=None):
    """Política de recarga a usar: la explícita, o la del proyecto.

    Args:
        proyecto: Proyecto del que sale la política por defecto.
        explicita: ``PoliticaRecarga`` pasada por el llamador, o None.

    Returns:
        La ``PoliticaRecarga`` efectiva.
    """
    if explicita is not None:
        return explicita
    from core.operacion import PoliticaRecarga

    cfg = getattr(proyecto, "configuracion", None)
    return getattr(cfg, "politica_recarga", None) or PoliticaRecarga()


def hash_entradas_anual(proyecto: "Proyecto") -> str:
    """Huella de todo lo que determina el resultado del modo anual.

    El resultado anual se calcula en P4 y se **muestra** en P7 y en el reporte,
    que no lo recalculan. Sin una huella, cambiar el auxiliar (o el colector, o
    la cámara) después de correr el año dejaba a P7 mostrando números viejos sin
    ninguna señal: en un reporte real del usuario (S58) el bloque global decía
    ``E_aux = 74 MJ`` y el bloque anual, ``0 MJ`` — el año se había corrido antes
    de configurar P5.

    Envuelve el mecanismo general de ``core.huellas`` fijando las secciones del
    modo anual. La política de recarga entra sola: desde S59 cuelga de
    ``Configuracion``, y ``huella_entradas`` expande las dataclasses anidadas —
    antes viajaba como ``extras`` porque vivía suelta en los widgets de P4.

    Args:
        proyecto: Proyecto a huellear.

    Returns:
        Hash SHA-256 hexadecimal.
    """
    from core.huellas import huella_entradas

    return huella_entradas(proyecto, SECCIONES_ANUAL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _area_colector_m2(proyecto: "Proyecto") -> float:
    """Área total del banco de colectores [m²]. 0 si no hay colector."""
    if proyecto.colector is None:
        return 0.0
    u = proyecto.colector.unidad
    b = proyecto.colector.banco
    return float(u.largo_m * u.ancho_m * b.n_serie * b.n_paralelo)


def _meses_del_indice(indice, tz_local: str) -> np.ndarray:
    """Mes calendario (1..12) de cada hora del índice, en hora local del sitio.

    Se pasa a hora local porque el usuario piensa el año en su calendario, no en
    UTC: una hora de las 23:00 del 31 de julio en Salta es UTC del 1 de agosto.
    """
    idx = pd.DatetimeIndex(indice)
    try:
        if idx.tz is not None:
            idx = idx.tz_convert(tz_local)
    except Exception:
        pass
    return np.asarray(idx.month, dtype=int)


def _dias_operables_por_mes(
    POA_W_m2, indice, tz_local: str, umbral_MJ_m2: float
) -> tuple[dict[int, int], dict[int, int]]:
    """Cuenta días operables y días totales por mes.

    Un día es **operable** si la irradiación diaria sobre el plano del colector
    supera ``umbral_MJ_m2``. Es un criterio de disponibilidad del recurso, no de
    la decisión del operador: dice cuántos días el sol alcanzaba, no cuántos se
    trabajó. Resuelve el campo ``I_g_diaria_minima_MJ_m2`` que el modo anual
    anterior declaraba y validaba pero nunca usaba (S57).

    Returns:
        ``(dias_operables_por_mes, dias_por_mes)``.
    """
    idx = pd.DatetimeIndex(indice)
    try:
        if idx.tz is not None:
            idx = idx.tz_convert(tz_local)
    except Exception:
        pass
    serie = pd.Series(np.asarray(POA_W_m2, dtype=float), index=idx)
    # W/m² horario → MJ/m² diarios.
    diaria = serie.groupby(idx.normalize()).sum() * _SEGUNDOS_POR_HORA / 1e6
    meses_dia = pd.DatetimeIndex(diaria.index).month
    operables = {m: 0 for m in _MESES}
    totales = {m: 0 for m in _MESES}
    for m in _MESES:
        sel = meses_dia == m
        totales[m] = int(sel.sum())
        operables[m] = int((diaria[sel] >= umbral_MJ_m2).sum())
    return operables, totales


def _agua_maxima_captable_kg(forzantes, t_fin_operacion_s: float, P_Pa: float) -> tuple[float, int]:
    """Agua que el aire podría haber cargado hasta saturarse [kg].

    ``ṁ · ∫ (ω_sat(T_ent) − ω_ent) dt`` sobre las horas en que el secador operó.
    Es el denominador de ``aprovechamiento_aire``: cuánta agua *podía* llevarse
    el aire que efectivamente pasó por la cámara.

    **Horas por encima de la ebullición local.** A presión reducida el agua
    hierve por debajo de 100 °C (a 2650 m, ~73 kPa, hierve a 91 °C), y ahí la
    humedad de saturación deja de estar definida: ``P_sat(T) ≥ P`` y el aire
    puede cargar agua sin límite termodinámico. Un colector bien dimensionado en
    altura alcanza esas temperaturas al mediodía. Esas horas se **excluyen** del
    denominador —incluirlas con capacidad infinita no significa nada— y se
    cuentan para que el llamador pueda avisar.

    Returns:
        ``(agua_captable_kg, n_horas_sobre_ebullicion)``.
    """
    from calculos.psicrometria import presion_vapor_saturacion

    t_s = np.asarray(forzantes.t_s, dtype=float)
    if t_s.size < 2:
        return 0.0, 0
    sel = t_s <= float(t_fin_operacion_s)
    if not sel.any():
        return 0.0, 0
    dt = float(t_s[1] - t_s[0])
    T_ent = np.asarray(forzantes.T_ent_K, dtype=float)[sel]
    omega_ent = np.asarray(forzantes.omega_ent, dtype=float)[sel]
    m_dot = np.asarray(forzantes.m_dot_aire_seco_kg_s, dtype=float)[sel]

    total = 0.0
    n_sobre_ebullicion = 0
    for T, w, m in zip(T_ent, omega_ent, m_dot):
        P_sat = presion_vapor_saturacion(float(T))
        if P_sat >= P_Pa:
            n_sobre_ebullicion += 1
            continue
        # ω_sat = 0.622·P_sat/(P − P_sat), sin pasar por humedad_absoluta para
        # no repetir la validación que ya se hizo arriba.
        omega_sat = 0.622 * P_sat / (P_Pa - P_sat)
        total += float(m) * max(0.0, omega_sat - float(w))
    return total * dt, n_sobre_ebullicion


def _hora_local_de_t0(t0_utc, tz_local: str) -> float:
    """Hora local del día (con fracción) que corresponde a ``t = 0`` [h].

    La política de recarga razona en hora local del sitio: "cargar a las 8" es 8
    de la mañana en Salta, no en UTC. Devuelve 0.0 si no hay ancla temporal.
    """
    if t0_utc is None:
        return 0.0
    try:
        ts = pd.Timestamp(t0_utc)
        if ts.tz is not None:
            ts = ts.tz_convert(tz_local)
        return float(ts.hour) + float(ts.minute) / 60.0
    except Exception:
        return 0.0


def _mes_de_instante(t0_utc, t_s: float, tz_local: str) -> Optional[int]:
    """Mes local en que cae ``t0_utc + t_s`` segundos. None si no hay ancla."""
    if t0_utc is None:
        return None
    try:
        ts = pd.Timestamp(t0_utc) + pd.Timedelta(seconds=float(t_s))
        if ts.tz is not None:
            ts = ts.tz_convert(tz_local)
        return int(ts.month)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------


def simular_anual(
    proyecto: "Proyecto",
    clima_datos_df,
    *,
    P_Pa: Optional[float] = None,
    usar_superficie: bool = True,
    umbral_dia_operable_MJ_m2: float = UMBRAL_DIA_OPERABLE_MJ_M2,
    politica_recarga=None,
) -> ResultadosAnual:
    """Simula el año completo encadenando lotes sobre el clima horario real.

    Args:
        proyecto: Proyecto con clima, emplazamiento, colector y cámara.
        clima_datos_df: DataFrame horario (COLUMNAS_SI) del año, con
            DatetimeIndex. La función simula el lapso que reciba: **exigir que
            cubra los 12 meses es responsabilidad del llamador** (la UI ya lo
            hace con ``ANUAL_CLIMA_INCOMPLETO`` cuando el clima medido es de
            campaña parcial). Mantenerlo así deja el motor testeable sobre
            lapsos cortos.
        P_Pa: Presión representativa [Pa]. Si es None se deriva del proyecto.
        usar_superficie: Si True (default) el colector se evalúa por superficie
            de respuesta interpolada en vez de resolverse hora a hora — mismo
            modelo, ~48× más rápido sobre 8760 h. Ver
            ``calculos/superficie_colector.py``.
        umbral_dia_operable_MJ_m2: Irradiación diaria mínima para contar el día
            como operable [MJ/m²·día].
        politica_recarga: ``PoliticaRecarga`` a usar. Si es None se toma la del
            proyecto (``proyecto.configuracion.politica_recarga``), que es el
            camino normal desde S59; el parámetro queda para que los tests
            puedan barrer políticas sin construir un proyecto por cada una.

    Returns:
        ``ResultadosAnual`` con desagregación mensual y agregados del año.

    Raises:
        ValueError: ``ANUAL_SIN_CAMARA``, ``ANUAL_SEMICONTINUO_NO_SOPORTADO``.
    """
    from calculos.balance_global import armar_forzantes_ventana, presion_representativa_proyecto
    from calculos.clima_calc import calcular_POA_horizonte
    from calculos.eficiencias_camara import calor_latente_agua_J_kg
    from calculos.simulacion_ventana import simular_encadenado_lotes
    from calculos.superficie_colector import construir_superficie
    from core.proyecto import SubtipoGranEscala, Tipologia

    if proyecto.camara is None:
        raise ValueError("ANUAL_SIN_CAMARA: la simulación anual requiere cámara configurada.")

    cfg = getattr(proyecto, "configuracion", None)
    if (
        getattr(cfg, "tipologia", None) == Tipologia.GRAN_ESCALA
        and getattr(cfg, "subtipo_gran_escala", None) == SubtipoGranEscala.SEMICONTINUO
    ):
        raise ValueError(
            "ANUAL_SEMICONTINUO_NO_SOPORTADO: el modo anual simula encadenado de "
            "lotes. El túnel semicontinuo opera en flujo continuo (avance de "
            "columnas), que es una operación distinta y todavía no está cubierta. "
            "Usá el modo Ventana para el túnel."
        )

    advertencias: list[str] = []
    if P_Pa is None:
        P_Pa, _origen = presion_representativa_proyecto(proyecto)

    tz_local = getattr(proyecto.emplazamiento, "zona_horaria", "UTC") or "UTC"
    n_horas = int(len(clima_datos_df))
    A_col = _area_colector_m2(proyecto)

    # --- Superficie de respuesta del colector (saca al colector del camino
    # crítico y, de paso, hace que el colector REAL entre al anual: el esquema
    # de día típico usaba un η fijo de 0.5 y era ciego al diseño de P3).
    superficie = None
    if usar_superficie and proyecto.colector is not None:
        try:
            POA_serie = calcular_POA_horizonte(clima_datos_df, proyecto.emplazamiento).to_numpy()
        except Exception:
            POA_serie = np.asarray(clima_datos_df.get("GHI_Wm2", []), dtype=float)
        m_dot = float(proyecto.camara.flujo.caudal_masico_kg_s)
        try:
            superficie = construir_superficie(
                proyecto,
                POA_W_m2_serie=POA_serie,
                T_amb_K_serie=np.asarray(clima_datos_df["T_amb_K"], dtype=float),
                v_viento_ms_serie=np.asarray(clima_datos_df["WS_ms"], dtype=float),
                m_dot_sistema_kg_s=m_dot if m_dot > 0 else None,
                P_amb_Pa=P_Pa,
            )
        except Exception as exc:
            advertencias.append(
                f"ANUAL_SUPERFICIE_FALLO: no se pudo construir la superficie de "
                f"respuesta del colector ({exc}); se resuelve hora a hora (más lento)."
            )
            superficie = None

    # --- Forzantes del año completo ---
    forzantes, lena_kg, advs_fz, diag = armar_forzantes_ventana(
        proyecto,
        clima_datos_df,
        P_Pa=P_Pa,
        superficie_colector=superficie,
    )
    advertencias.extend(advs_fz)
    E_aux_MJ = float(diag.get("E_aux_MJ", 0.0))
    Q_util_col_MJ = float(diag.get("Q_util_colector_MJ", 0.0))

    # --- Encadenado de lotes sobre las 8760 h ---
    # La política de recarga necesita saber qué hora local es t=0 para poder
    # esperar a la hora de carga de cada día.
    hora_t0 = _hora_local_de_t0(getattr(forzantes, "t0_utc", None), tz_local)
    res_v = simular_encadenado_lotes(
        proyecto,
        forzantes_base=forzantes,
        P_Pa=P_Pa,
        politica=_politica_del_proyecto(proyecto, politica_recarga),
        hora_local_t0_h=hora_t0,
    )
    for a in res_v.advertencias:
        if a not in advertencias:
            advertencias.append(a)

    # --- Energía solar por mes (flujo: se integra por mes calendario) ---
    meses_hora = _meses_del_indice(clima_datos_df.index, tz_local)
    POA_arr = np.asarray(getattr(forzantes, "I_g_POA_W_m2", None), dtype=float)
    if POA_arr.size != n_horas:
        POA_arr = np.zeros(n_horas, dtype=float)
    # Potencia del auxiliar hora a hora (0 si no hay): se integra por mes con el
    # mismo criterio que el sol, porque también es un flujo. Sin esto el aporte
    # del auxiliar solo existía como total del año y no se veía en qué meses
    # trabaja — justo lo que un híbrido necesita mostrar (S58).
    Q_aux_arr = np.asarray(diag.get("Q_aux_W_serie", []), dtype=float)
    if Q_aux_arr.size != n_horas:
        Q_aux_arr = np.zeros(n_horas, dtype=float)

    E_solar_mes = {m: 0.0 for m in _MESES}
    E_aux_mes = {m: 0.0 for m in _MESES}
    horas_mes = {m: 0 for m in _MESES}
    for m in _MESES:
        sel = meses_hora == m
        horas_mes[m] = int(sel.sum())
        E_solar_mes[m] = float(POA_arr[sel].sum() * A_col * _SEGUNDOS_POR_HORA / 1e6)
        E_aux_mes[m] = float(Q_aux_arr[sel].sum() * _SEGUNDOS_POR_HORA / 1e6)

    # El total anual del auxiliar se recompone de los meses en vez de tomar el
    # escalar del solver: aquel integra con regla trapezoidal sobre el horizonte
    # completo y acá se integra por rectángulos hora a hora, igual que la solar.
    # La diferencia es ~1 % (medios pasos en los extremos), pero si el total no
    # fuera la suma de sus meses la tabla mensual contradiría al resumen.
    # (el total se recompone MÁS ABAJO, después de sumar el respaldo lote a lote)

    operables_mes, dias_mes = _dias_operables_por_mes(
        POA_arr, clima_datos_df.index, tz_local, umbral_dia_operable_MJ_m2
    )

    # --- Atribución de lotes al mes de descarga ---
    t0_utc = getattr(forzantes, "t0_utc", None)
    completos_mes = {m: 0 for m in _MESES}
    frustrados_mes = {m: 0 for m in _MESES}
    seca_mes = {m: 0.0 for m in _MESES}
    evap_mes = {m: 0.0 for m in _MESES}
    duraciones_mes: dict[int, list[float]] = {m: [] for m in _MESES}

    lotes = list(getattr(res_v, "lotes", []))
    if lotes and t0_utc is None:
        advertencias.append(
            "ANUAL_SIN_ANCLA_TEMPORAL: las forzantes no traen t0_utc, así que no se "
            "pudo atribuir cada lote a su mes. Los agregados anuales son válidos; "
            "la tabla mensual queda vacía."
        )

    for lote in lotes:
        mes = _mes_de_instante(t0_utc, lote.t_fin_s, tz_local)
        if mes is None:
            continue
        evap_mes[mes] += float(lote.masa_evaporada_kg)
        # El respaldo se atribuye al mes de DESCARGA, igual que la producción:
        # su energía no viaja en una serie horaria (la modula el motor de cada
        # lote contra T_flujo), así que se reparte lote a lote.
        E_aux_mes[mes] += float(getattr(lote, "E_auxiliar_MJ", 0.0))
        if lote.completo:
            completos_mes[mes] += 1
            seca_mes[mes] += float(lote.masa_seca_kg)
            duraciones_mes[mes].append(float(lote.duracion_s) / _SEGUNDOS_POR_HORA)
        else:
            frustrados_mes[mes] += 1

    # Recién acá el reparto mensual está completo: trae el auxiliar en SERIE
    # (serie horaria, arriba) y el de RESPALDO (lote a lote, recién sumado).
    E_aux_respaldo_MJ = float(getattr(res_v, "E_auxiliar_respaldo_MJ", 0.0))
    if Q_aux_arr.any() or E_aux_respaldo_MJ > 0.0:
        E_aux_MJ = float(sum(E_aux_mes.values()))

    h_fg_MJ_kg = calor_latente_agua_J_kg(_T_EVAP_REF_K) / 1e6
    puntos = [
        PuntoMensualAnual(
            mes=m,
            lotes_completos=completos_mes[m],
            lotes_frustrados=frustrados_mes[m],
            masa_seca_kg=seca_mes[m],
            masa_evaporada_kg=evap_mes[m],
            duracion_media_h=(float(np.mean(duraciones_mes[m])) if duraciones_mes[m] else None),
            E_solar_MJ=E_solar_mes[m],
            E_auxiliar_MJ=E_aux_mes[m],
            horas=horas_mes[m],
            dias_operables=operables_mes[m],
            dias=dias_mes[m],
            eta_drying=(evap_mes[m] * h_fg_MJ_kg / E_solar_mes[m] if E_solar_mes[m] > 0 else None),
            energia_especifica_MJ_kg=(E_solar_mes[m] / evap_mes[m] if evap_mes[m] > 0 else None),
        )
        for m in _MESES
    ]

    # --- Agregados del año ---
    dur_completos = [float(lote.duracion_s) / _SEGUNDOS_POR_HORA for lote in lotes if lote.completo]
    n_completos = sum(1 for lote in lotes if lote.completo)
    n_frustrados = sum(1 for lote in lotes if not lote.completo)

    status = res_v.status or ("ok" if n_completos else "sin_lotes_completos")

    E_solar_anual = float(sum(E_solar_mes.values()))
    m_evap = float(res_v.masa_evaporada_kg)
    E_primaria = E_solar_anual + E_aux_MJ
    E_util = Q_util_col_MJ + E_aux_MJ

    # Aprovechamiento del aire: agua evaporada sobre la que el aire podía cargar
    # en las horas que el secador operó (hasta la descarga del último lote).
    # Envuelto: una métrica derivada no puede tirar abajo una simulación de un
    # año entero — si falla, se reporta como no disponible y el resto queda.
    t_fin_operacion = max((lote.t_fin_s for lote in lotes), default=0.0)
    try:
        agua_captable, n_sobre_ebullicion = _agua_maxima_captable_kg(
            forzantes, t_fin_operacion, P_Pa
        )
    except Exception as exc:
        advertencias.append(f"ANUAL_APROVECHAMIENTO_NO_CALCULADO: {exc}")
        agua_captable, n_sobre_ebullicion = 0.0, 0
    if n_sobre_ebullicion:
        advertencias.append(
            f"ANUAL_AIRE_SOBRE_EBULLICION: en {n_sobre_ebullicion} h el aire de entrada "
            f"superó la temperatura de ebullición del agua a la presión del sitio "
            f"({P_Pa / 1000:.1f} kPa). Esas horas quedan fuera del aprovechamiento del "
            "aire (la saturación no está definida por encima de la ebullición). "
            "Revisá si el colector está sobredimensionado para el caudal: temperaturas "
            "de entrada tan altas también dañan el producto."
        )

    return ResultadosAnual(
        puntos_mensuales=puntos,
        masa_seca_anual_kg=float(res_v.masa_seca_producida_kg),
        masa_evaporada_anual_kg=m_evap,
        n_lotes_completos=n_completos,
        n_lotes_frustrados=n_frustrados,
        duracion_media_h=(float(np.mean(dur_completos)) if dur_completos else None),
        duracion_p50_h=(float(np.percentile(dur_completos, 50)) if dur_completos else None),
        duracion_p90_h=(float(np.percentile(dur_completos, 90)) if dur_completos else None),
        E_solar_anual_MJ=E_solar_anual,
        Q_util_colector_MJ=Q_util_col_MJ,
        E_auxiliar_MJ=E_aux_MJ,
        fraccion_solar=(Q_util_col_MJ / E_util if E_util > 0 else None),
        eta_drying_anual=(m_evap * h_fg_MJ_kg / E_solar_anual if E_solar_anual > 0 else None),
        eta_total_anual=(m_evap * h_fg_MJ_kg / E_primaria if E_primaria > 0 else None),
        aprovechamiento_aire=(m_evap / agua_captable if agua_captable > 0 else None),
        energia_especifica_MJ_kg=(E_solar_anual / m_evap if m_evap > 0 else None),
        dias_operables=int(sum(operables_mes.values())),
        umbral_dia_operable_MJ_m2=float(umbral_dia_operable_MJ_m2),
        dias_salteados_pronostico=int(getattr(res_v, "n_dias_salteados_pronostico", 0)),
        lena_consumida_kg=float(lena_kg),
        horas_simuladas=n_horas,
        area_colector_m2=A_col,
        superficie_n_solves=int(getattr(superficie, "n_solves", 0)),
        status=status,
        advertencias=advertencias,
    )
