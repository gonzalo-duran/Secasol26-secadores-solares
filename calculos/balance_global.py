"""
Orquestador del cálculo global del secador solar.

Encadena los solvers de colector → auxiliar → cámara y calcula el balance
energético completo del sistema.

Flujo de cálculo:
    1. Colector (Tipo 1): T_entrada → T_salida, Q_util, η.
    2. Auxiliar (si configurado): T_salida_col → T_salida_aux, Q_aux.
    3. Cámara: T_entrada_camara → t_secado, X_final, masa_agua.
    4. Balance global: COP, fracción solar, etc.

Hipótesis de v0:
    - Condiciones cuasi-estacionarias durante todo el ciclo de secado.
    - Se usan condiciones representativas ingresadas por el usuario (no
      integración horaria sobre el día).
    - El colector se calcula siempre como Tipo 1 (canal único sobre absorbedor).
      Los Tipos 2, 3, 4 requieren selección explícita en versiones futuras.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np

if TYPE_CHECKING:
    from core.auxiliar import Auxiliar
    from core.camara import Camara
    from core.colector import Colector

from calculos.auxiliar_calc import (
    ResultadosAuxiliarTransitorio,
    calcular_auxiliar,
    calcular_auxiliar_transitorio,
)
from calculos.auxiliar_calc import ResultadosAuxiliar as _SolverAuxiliar
from calculos.camara_calc import calcular_camara
from calculos.camara_calc import ResultadosCamara as _SolverCamara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.colector_calc import calcular_colector_tipo1
from calculos.colector_tipos234_calc import (
    calcular_colector_tipo2,
    calcular_colector_tipo3,
    calcular_colector_tipo4,
)
from core.camara import ForzantesAire
from core.resultados import LV_AGUA_MJ_KG

_HORIZONTE_MAX_DIAS: int = 21

_SolverCamaraUnion = Union[_SolverCamara, ResultadoMotorTermodinamico]

# ---------------------------------------------------------------------------
# Dataclass de resultados integrados
# ---------------------------------------------------------------------------


@dataclass
class ResultadosCompletos:
    """Resultados integrados del cálculo global del secador.

    Attributes:
        colector: Salida del solver de colector (None si no hay colector).
        auxiliar: Salida del solver de auxiliar (None si no hay auxiliar).
        camara: Salida del solver de cámara (None si no hay cámara).
        T_entrada_camara_K: Temperatura del aire que llega a la cámara [K].
            T_salida_auxiliar si hay auxiliar, T_salida_colector si no.
        energia_solar_util_MJ: Energía útil del colector × t_secado [MJ].
        energia_auxiliar_MJ: Energía del auxiliar × t_secado [MJ].
        energia_motor_MJ: Energía eléctrica del motor × t_secado [MJ].
        energia_secado_MJ: masa_agua × Lv [MJ].
        energia_total_MJ: solar + auxiliar + motor.
        COP_secado: masa_agua × Lv / energia_total [adim].
        fraccion_solar: energia_solar / (solar + auxiliar).
        masa_producto_seco_kg: masa_total / (1 + X_0).
        rendimiento_masa: masa_seco / masa_fresco.
        advertencias: Mensajes de advertencia del cálculo integrado.
        errores: Errores que impidieron parte del cálculo.
    """

    colector: Optional[Any] = None
    auxiliar: Optional[_SolverAuxiliar] = None
    camara: Optional[_SolverCamaraUnion] = None

    T_entrada_camara_K: Optional[float] = None

    energia_solar_util_MJ: Optional[float] = None
    energia_auxiliar_MJ: Optional[float] = None
    energia_motor_MJ: Optional[float] = None
    energia_secado_MJ: Optional[float] = None
    energia_total_MJ: Optional[float] = None
    COP_secado: Optional[float] = None
    fraccion_solar: Optional[float] = None

    masa_producto_seco_kg: Optional[float] = None
    rendimiento_masa: Optional[float] = None

    advertencias: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validaciones cruzadas del Proyecto
# ---------------------------------------------------------------------------


def verificar_coherencia_proyecto(proyecto) -> list[str]:
    """Comprueba las invariantes de coherencia cruzada entre secciones.

    Args:
        proyecto: Objeto Proyecto del core.

    Returns:
        Lista de mensajes de error. Vacía si el proyecto es coherente.
    """
    from core.proyecto import ModoAnalisis, Tipologia
    from core.auxiliar import ModoOperacionAuxiliar

    errores: list[str] = []
    cfg = proyecto.configuracion

    if cfg.tipologia == Tipologia.CAJA and proyecto.colector is not None:
        errores.append(
            "PROY_CAJA_CON_COLECTOR: tipología CAJA no admite colector externo."
        )
    if cfg.tipologia == Tipologia.CAJA and proyecto.motor is not None:
        errores.append(
            "PROY_CAJA_CON_MOTOR: tipología CAJA usa convección natural; "
            "motor = None requerido."
        )
    if (cfg.tipologia == Tipologia.CAJA
            and proyecto.camara is not None
            and proyecto.camara.construccion.cubierta_translucida_id is None):
        errores.append(
            "PROY_CAJA_SIN_CUBIERTA_TRANSLUCIDA: tipología CAJA requiere techo "
            "translúcido (cubierta_translucida_id no-None). Sin colector externo, "
            "la radiación solar a través de la cubierta es la única fuente de "
            "energía del producto."
        )
    if (proyecto.auxiliar is not None
            and proyecto.auxiliar.modo_operacion == ModoOperacionAuxiliar.SERIE_POSCOLECTOR
            and proyecto.colector is None):
        errores.append(
            "PROY_AUXILIAR_SERIE_SIN_COLECTOR: auxiliar en SERIE_POSCOLECTOR "
            "requiere colector definido."
        )
    if proyecto.motor is not None and proyecto.camara is None:
        errores.append(
            "PROY_MOTOR_SIN_CAMARA: motor definido pero sin cámara configurada."
        )
    if (cfg.modo_analisis == ModoAnalisis.ANUAL
            and cfg.tipologia == Tipologia.CAJA):
        errores.append(
            "PROY_ANUAL_SIN_VECTORIZACION: análisis anual para tipología CAJA "
            "no implementado en v0."
        )
    return errores


# ---------------------------------------------------------------------------
# Verificación de caudal consistente entre motor y cámara
# ---------------------------------------------------------------------------


def _extraer_t_y_masa(
    solver_cam: _SolverCamaraUnion,
) -> tuple[Optional[float], float]:
    """Extrae (t_secado_s, masa_agua_kg) abstrayendo los nombres divergentes.

    En modo capa fina ambos campos existen siempre como ``float``. En modo
    termodinámico ``t_secado_s`` puede ser ``None`` cuando el solver no llegó
    a X_obj (status ``t_max_alcanzado`` o ``error``); en ese caso el balance
    global no puede multiplicar potencias × tiempo y los devuelve como ``None``.
    """
    if isinstance(solver_cam, ResultadoMotorTermodinamico):
        return solver_cam.t_secado_s, solver_cam.masa_evaporada_total_kg
    return solver_cam.t_secado_s, solver_cam.masa_agua_extraida_kg


def _advertencia_caudal_inconsistente(proyecto) -> Optional[str]:
    if proyecto.motor is None or proyecto.camara is None:
        return None
    rho = 1.1
    Q_cam = proyecto.camara.flujo.caudal_masico_kg_s / rho
    Q_mot = proyecto.motor.caudal_volumetrico_m3_s
    if Q_cam > 0 and abs(Q_mot - Q_cam) / Q_cam > 0.15:
        return (
            f"PROY_CAUDAL_INCONSISTENTE: caudal del motor ({Q_mot*1000:.1f} L/s) "
            f"difiere >15% del caudal de la cámara ({Q_cam*1000:.1f} L/s). "
            "Verificar consistencia entre P4 y P6."
        )
    return None


# ---------------------------------------------------------------------------
# Constructor de forzantes para el motor dinámico
# ---------------------------------------------------------------------------


def armar_forzantes_aire(
    *,
    modo: str,
    n_dias: int = 1,
    T_salida_colector_K: np.ndarray,
    omega_ambiente: np.ndarray,
    T_salida_auxiliar_K: Optional[np.ndarray] = None,
    m_dot_aire_seco_kg_s: float,
    v_viento_ms: Optional[np.ndarray] = None,
    T_amb_K: Optional[np.ndarray] = None,
    I_g_W_m2: Optional[np.ndarray] = None,
    dt_s: float = 3600.0,
) -> ForzantesAire:
    """Construye la serie de forzantes de entrada a la cámara para el motor dinámico.

    Lógica de cada variable:
    - **T_ent:** T_salida_auxiliar_K si hay auxiliar activo; T_salida_colector_K si no.
    - **omega_ent:** omega_ambiente (el colector/auxiliar no aporta vapor de agua).
    - **m_dot:** m_dot_aire_seco_kg_s constante (motor eléctrico de diseño).
    - **Multi-día:** replica la serie base de 24 h exactamente N veces.
    - **Anual:** usa la serie tal como llega (responsabilidad del llamador proveer 8760 h).

    Args:
        modo: "diario" | "multi_dia" | "anual".
        n_dias: Número de días para modo multi_dia [1–21]. Ignorado en otros modos.
        T_salida_colector_K: Serie horaria de T_salida del colector [K].
            Modo diario/multi_dia: 24 elementos (día tipo).
            Modo anual: N_horas elementos (serie completa).
        omega_ambiente: Humedad absoluta del aire ambiente [kg/kg ms].
            Misma longitud que T_salida_colector_K.
        T_salida_auxiliar_K: T_salida del auxiliar si está activo [K].
            None → T_ent = T_salida_colector_K.
        m_dot_aire_seco_kg_s: Caudal másico de aire seco [kg/s]. Constante.
        v_viento_ms: Serie horaria de velocidad de viento [m/s].
            None → 2.0 m/s constante.
        T_amb_K: Serie horaria de temperatura ambiente [K].
            None → T_ent − 10 K (aproximación conservadora: colector aporta ~10 K).
        I_g_W_m2: Serie horaria de irradiancia global horizontal sobre el techo
            de la cámara [W/m²]. None → array de ceros (cámara opaca o sin
            radiación). Para techo translúcido en modo real, pasar GHI_Wm2
            del clima NASA POWER.
        dt_s: Intervalo entre puntos de la serie [s]. Default 3600 (datos horarios).

    Returns:
        ForzantesAire listo para pasar al motor termodinámico (simular_secado).

    Raises:
        ValueError: Si modo no es válido, n_dias fuera de rango, o los arrays
            tienen longitudes inconsistentes.
    """
    modos_validos = ("diario", "multi_dia", "anual")
    if modo not in modos_validos:
        raise ValueError(
            f"FORZANTES_MODO_INVALIDO: modo='{modo}' no reconocido. "
            f"Opciones: {modos_validos}."
        )

    T_col = np.asarray(T_salida_colector_K, dtype=float)
    omega = np.asarray(omega_ambiente, dtype=float)
    n_base = len(T_col)

    if len(omega) != n_base:
        raise ValueError(
            f"FORZANTES_LONGITUD_INCONSISTENTE: omega_ambiente tiene {len(omega)} "
            f"elementos, esperado {n_base} (igual que T_salida_colector_K)."
        )

    # --- T_ent: auxiliar si activo ---
    if T_salida_auxiliar_K is not None:
        T_aux = np.asarray(T_salida_auxiliar_K, dtype=float)
        if len(T_aux) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: T_salida_auxiliar_K tiene {len(T_aux)} "
                f"elementos, esperado {n_base}."
            )
        T_ent_base = T_aux
    else:
        T_ent_base = T_col

    # --- v_viento ---
    if v_viento_ms is not None:
        v_base = np.asarray(v_viento_ms, dtype=float)
        if len(v_base) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: v_viento_ms tiene {len(v_base)} "
                f"elementos, esperado {n_base}."
            )
    else:
        v_base = np.full(n_base, 2.0)

    # --- T_amb ---
    if T_amb_K is not None:
        T_amb_base = np.asarray(T_amb_K, dtype=float)
        if len(T_amb_base) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: T_amb_K tiene {len(T_amb_base)} "
                f"elementos, esperado {n_base}."
            )
    else:
        # Fallback: T_ent - 10 K (el colector eleva ~10 K sobre el ambiente)
        T_amb_base = T_ent_base - 10.0

    # --- I_g (irradiancia global sobre el techo de la cámara) ---
    if I_g_W_m2 is not None:
        I_g_base = np.asarray(I_g_W_m2, dtype=float)
        if len(I_g_base) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: I_g_W_m2 tiene {len(I_g_base)} "
                f"elementos, esperado {n_base}."
            )
    else:
        I_g_base = np.zeros(n_base)

    # --- m_dot: constante ---
    m_base = np.full(n_base, float(m_dot_aire_seco_kg_s))

    # --- Replicación según modo ---
    if modo == "multi_dia":
        if not (1 <= n_dias <= _HORIZONTE_MAX_DIAS):
            raise ValueError(
                f"FORZANTES_N_DIAS_INVALIDO: n_dias={n_dias} fuera del rango "
                f"[1, {_HORIZONTE_MAX_DIAS}]."
            )
        n_reps = n_dias
    else:
        n_reps = 1

    if n_reps > 1:
        T_ent_arr = np.tile(T_ent_base, n_reps)
        omega_arr = np.tile(omega, n_reps)
        v_arr = np.tile(v_base, n_reps)
        T_amb_arr = np.tile(T_amb_base, n_reps)
        m_arr = np.tile(m_base, n_reps)
        I_g_arr = np.tile(I_g_base, n_reps)
    else:
        T_ent_arr = T_ent_base.copy()
        omega_arr = omega.copy()
        v_arr = v_base.copy()
        T_amb_arr = T_amb_base.copy()
        m_arr = m_base.copy()
        I_g_arr = I_g_base.copy()

    # --- Vector de tiempos: empieza en 0, paso dt_s ---
    N = len(T_ent_arr)
    t_s = np.arange(N, dtype=float) * dt_s

    return ForzantesAire(
        t_s=t_s,
        T_ent_K=T_ent_arr,
        omega_ent=omega_arr,
        m_dot_aire_seco_kg_s=m_arr,
        T_amb_K=T_amb_arr,
        v_viento_ms=v_arr,
        I_g_W_m2=I_g_arr,
    )


def construir_serie_sintetica_dia_tipo(
    *,
    T_sal_col_promedio_K: float,
    T_sal_col_amplitud_K: float,
    omega_amb: float,
    m_dot_aire_seco_kg_s: float,
    T_amb_promedio_K: float | None = None,
    T_amb_amplitud_K: float = 0.0,
    v_viento_ms: float = 2.0,
    I_g_max_W_m2: float = 0.0,
    hora_pico: float = 12.0,
    n_horas: int = 24,
    n_dias: int = 1,
) -> ForzantesAire:
    """Genera una ForzantesAire con curvas senoidales día/noche (modo sintético).

    T_sal_col(h) = T_promedio + T_amplitud · sin(2π·(h − hora_pico + 6) / 24)
    T_amb(h)     = T_amb_promedio + T_amb_amplitud · sin(2π·(h − hora_pico + 6) / 24)
    I_g(h)       = max(0, I_g_max · sin(π·(h − hora_pico + 6) / 12))   (campana solo
                   durante el día; cero de noche)

    Se garantiza T_sal_col(h) ≥ T_amb(h) en cada hora (sin radiación, el colector
    no puede enfriar el aire por debajo del ambiente). ω_amb, ṁ_as y v_viento
    se mantienen constantes en el día tipo.

    Args:
        T_sal_col_promedio_K: Temperatura media del aire a la salida del colector [K].
        T_sal_col_amplitud_K: Amplitud de oscilación día/noche de T_sal_col [K].
            Típico: ~15 K (medianoche frío, mediodía caliente).
        omega_amb: Humedad absoluta del aire ambiente [kg/kg ms]. Constante.
        m_dot_aire_seco_kg_s: Caudal másico de aire seco [kg/s]. Constante.
        T_amb_promedio_K: Temperatura ambiente media [K]. None → T_sal_col_prom − 10 K.
        T_amb_amplitud_K: Amplitud de T_amb [K]. Default 0 (T_amb constante).
        v_viento_ms: Velocidad del viento [m/s]. Constante. Default 2.0.
        I_g_max_W_m2: Irradiancia global pico al mediodía [W/m²]. Default 0
            (sin radiación — cámara opaca o sin techo translúcido). Típico
            cielo claro: 800–1000 W/m². La curva diaria es una semicampana
            sinusoidal positiva (sol entre h=6 y h=18 si hora_pico=12);
            de noche I_g=0.
        hora_pico: Hora del día (0–24) en que ocurre el pico térmico. Default 12.
        n_horas: Puntos por día. Default 24 (datos horarios).
        n_dias: Número de días a replicar. Default 1.

    Returns:
        ForzantesAire con n_horas·n_dias puntos a paso 1 h.
    """
    if T_amb_promedio_K is None:
        T_amb_promedio_K = T_sal_col_promedio_K - 10.0

    horas = np.arange(n_horas, dtype=float)
    fase = 2.0 * np.pi * (horas - hora_pico + 6.0) / 24.0
    T_col = T_sal_col_promedio_K + T_sal_col_amplitud_K * np.sin(fase)
    T_amb = T_amb_promedio_K + T_amb_amplitud_K * np.sin(fase)

    # Sin radiación, el colector cae al ambiente: T_sal_col ≥ T_amb siempre.
    T_col = np.maximum(T_col, T_amb)

    # Curva de radiación: semicampana sinusoidal positiva centrada en hora_pico,
    # cero fuera del intervalo (hora_pico − 6, hora_pico + 6). La media diaria
    # resulta I_g_max·2/π ≈ 0.637·I_g_max (típico de día claro).
    fase_dia = np.pi * (horas - hora_pico + 6.0) / 12.0
    I_g_arr = np.maximum(0.0, float(I_g_max_W_m2) * np.sin(fase_dia))

    omega = np.full(n_horas, float(omega_amb))
    v_viento_arr = np.full(n_horas, float(v_viento_ms))

    modo = "multi_dia" if n_dias > 1 else "diario"
    return armar_forzantes_aire(
        modo=modo,
        n_dias=n_dias,
        T_salida_colector_K=T_col,
        omega_ambiente=omega,
        m_dot_aire_seco_kg_s=m_dot_aire_seco_kg_s,
        v_viento_ms=v_viento_arr,
        T_amb_K=T_amb,
        I_g_W_m2=I_g_arr,
        dt_s=3600.0,
    )


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def calcular_todo(
    proyecto,
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    T_entrada_K: float,
    HR_camara: float,
) -> ResultadosCompletos:
    """Ejecuta todos los solvers encadenados y calcula el balance global.

    Args:
        proyecto: Objeto Proyecto con todas las secciones configuradas.
        T_amb_K: Temperatura ambiente representativa [K].
        I_g_W_m2: Irradiancia global en el plano del colector [W/m²].
        v_viento_ms: Velocidad del viento representativa [m/s].
        T_entrada_K: Temperatura del aire a la entrada del colector [K].
            En la práctica ≈ T_amb para un sistema abierto.
        HR_camara: Humedad relativa en la cámara para cálculo de X_eq [0,1].

    Returns:
        ResultadosCompletos con todos los resultados y advertencias.
    """
    res = ResultadosCompletos()

    # --- Verificaciones cruzadas ---
    errores = verificar_coherencia_proyecto(proyecto)
    if errores:
        res.errores = errores
        return res

    adv_caudal = _advertencia_caudal_inconsistente(proyecto)
    if adv_caudal:
        res.advertencias.append(adv_caudal)

    # --- Solver colector ---
    T_salida_colector_K = T_entrada_K   # fallback si no hay colector
    if proyecto.colector is not None:
        try:
            u = proyecto.colector.unidad
            tipo = u.tipo_colector
            _kwargs_comunes = dict(
                colector=proyecto.colector,
                T_amb_K=T_amb_K,
                I_g_W_m2=I_g_W_m2,
                v_viento_ms=v_viento_ms,
                P_amb_Pa=101325.0,
                T_entrada_K=T_entrada_K,
            )
            if tipo == 1:
                solver_col = calcular_colector_tipo1(
                    **_kwargs_comunes, correlacion_nusselt=None
                )
                T_salida_colector_K = solver_col.T_salida_K
            elif tipo == 2:
                solver_col = calcular_colector_tipo2(
                    **_kwargs_comunes,
                    v_diseno_cs_ms=u.velocidad_diseno_ms,
                    v_diseno_ci_ms=u.velocidad_diseno_ms,
                    alto_cs_m=u.espaciado_m,
                    alto_ci_m=u.espaciado_inferior_m,
                )
                T_salida_colector_K = solver_col.T_salida_mezcla_K
            elif tipo == 3:
                solver_col = calcular_colector_tipo3(
                    **_kwargs_comunes,
                    alto_cs_m=u.espaciado_m,
                    alto_ci_m=u.espaciado_inferior_m,
                )
                T_salida_colector_K = solver_col.T_salida_K
            elif tipo == 4:
                solver_col = calcular_colector_tipo4(
                    **_kwargs_comunes,
                    alto_cs_m=u.espaciado_m,
                    alto_ci_m=u.espaciado_inferior_m,
                )
                T_salida_colector_K = solver_col.T_salida_K
            res.colector = solver_col
            res.advertencias.extend(solver_col.advertencias)
        except Exception as exc:
            res.errores.append(f"ERROR_COLECTOR: {exc}")
            return res

    # --- Solver auxiliar ---
    T_salida_aux_K = T_salida_colector_K
    caudal_kg_s = (
        proyecto.camara.flujo.caudal_masico_kg_s
        if proyecto.camara is not None else 0.030
    )
    if proyecto.auxiliar is not None:
        try:
            solver_aux = calcular_auxiliar(
                auxiliar=proyecto.auxiliar,
                T_entrada_K=T_salida_colector_K,
                caudal_masico_kg_s=caudal_kg_s,
            )
            res.auxiliar = solver_aux
            T_salida_aux_K = solver_aux.T_salida_K
            res.advertencias.extend(solver_aux.advertencias)
        except Exception as exc:
            res.advertencias.append(f"ADVERTENCIA_AUXILIAR: {exc}")

    res.T_entrada_camara_K = T_salida_aux_K

    # --- Solver cámara ---
    if proyecto.camara is not None:
        try:
            solver_cam = calcular_camara(
                camara=proyecto.camara,
                T_operacion_K=T_salida_aux_K,
                HR_operacion=HR_camara,
                T_amb_K=T_amb_K,
            )
            res.camara = solver_cam
            res.advertencias.extend(solver_cam.advertencias)
        except Exception as exc:
            res.errores.append(f"ERROR_CAMARA: {exc}")
            return res

    # --- Balance global ---
    if res.camara is not None:
        t_s, masa_agua = _extraer_t_y_masa(res.camara)

        # Masa producto seco — siempre calculable, no depende de t_secado.
        p = proyecto.camara.carga_producto
        X_0 = p.humedad_inicial_X
        ms = p.masa_total_kg / (1 + X_0)
        res.masa_producto_seco_kg = ms
        res.rendimiento_masa = ms / p.masa_total_kg

        if t_s is None:
            # Motor TD no convergió (t_max_alcanzado o error). No podemos
            # calcular energías × tiempo. Reportamos lo que tenemos.
            status = getattr(res.camara, "status", "desconocido")
            res.advertencias.append(
                f"BG_TD_NO_CONVERGE: motor termodinámico devolvió status='{status}'. "
                "Energías y COP no calculables; aumentar t_max o revisar parámetros."
            )
        else:
            # Energías [MJ]
            E_sol = (res.colector.Q_util_W * t_s / 1e6) if res.colector else 0.0
            E_aux = (
                res.auxiliar.Q_efectivo_W * t_s / 1e6 if res.auxiliar else 0.0
            )
            E_mot = (
                (proyecto.motor.potencia_electrica_W * t_s / 1e6)
                if proyecto.motor is not None and proyecto.motor.potencia_electrica_W
                else 0.0
            )
            E_total = E_sol + E_aux + E_mot
            E_sec = masa_agua * LV_AGUA_MJ_KG

            res.energia_solar_util_MJ = E_sol
            res.energia_auxiliar_MJ = E_aux if proyecto.auxiliar else 0.0
            res.energia_motor_MJ = E_mot
            res.energia_secado_MJ = E_sec
            res.energia_total_MJ = E_total

            if E_total > 0:
                res.COP_secado = E_sec / E_total
            if E_sol + E_aux > 0:
                res.fraccion_solar = E_sol / (E_sol + E_aux)

    return res


# ===========================================================================
# Pipeline transitoria (mejora 19)
# ===========================================================================


@dataclass
class ResultadosCompletosTransitorio:
    """Resultados del cálculo global propagando el horizonte transitorio.

    A diferencia de ``ResultadosCompletos``, las series temporales del aire
    y del producto provienen del motor TD de cámara corrido sobre las
    forzantes del horizonte (clima real o día sintético), no de un punto de
    diseño escalar. Si hay auxiliar, sus aportes se computan paso a paso y
    se suman a la T_ent de cámara antes de re-correr el motor TD.

    Attributes:
        forzantes_base: ForzantesAire del horizonte tal como salieron de P4
            (T_ent_K = T_salida del colector, sin auxiliar).
        forzantes_aplicadas: ForzantesAire que efectivamente vio la cámara
            (T_ent_K = T_sal_col + ΔT_aux si hay auxiliar; igual a base si no).
        camara: ResultadoMotorTermodinamico re-corrido con forzantes_aplicadas.
            Contiene trayectorias T_prod, X_prod, T_flujo, m_dot_w, etc.
        auxiliar: ResultadosAuxiliarTransitorio si el proyecto tiene auxiliar,
            None en caso contrario.
        motor_P_elec_W: Potencia eléctrica nominal del motor [W] (escalar).
        horizonte_s: Duración total del horizonte simulado [s].
        n_dias: Días simulados (informativo, replicado de P4).

        energia_solar_util_MJ: ∫ ṁ·cp·(T_sal_col − T_amb) dt sobre el horizonte.
        energia_auxiliar_MJ: E_aux del solver transitorio del auxiliar.
        energia_motor_MJ: P_elec · horizonte_s / 1e6 (escalar × tiempo).
        energia_secado_MJ: masa_agua_evaporada × LV_AGUA [MJ].
        energia_total_MJ: solar + auxiliar + motor.
        COP_secado: E_secado / E_total.
        fraccion_solar: E_solar / (E_solar + E_aux).

        masa_producto_seco_kg: Masa de sólido seco del producto.
        masa_agua_evaporada_kg: Integrada del motor TD desde X_inicial y t_secado.

        t_X_obj_alcanzado_s: Tiempo en que X bajó a X_obj. None si no se alcanzó.
        horas_clipeo_pol_B_s: Heredado del motor TD.
        horas_HR_alta_s: Heredado del motor TD.
        T_prod_max_K: Heredado del motor TD.

        advertencias: Mensajes integrados (incluye auxiliar y cámara).
        errores: Errores que impidieron parte del cálculo.
    """

    forzantes_base: Optional[ForzantesAire] = None
    forzantes_aplicadas: Optional[ForzantesAire] = None
    camara: Optional[ResultadoMotorTermodinamico] = None
    auxiliar: Optional[ResultadosAuxiliarTransitorio] = None
    motor_P_elec_W: float = 0.0
    horizonte_s: float = 0.0
    n_dias: int = 1

    energia_solar_util_MJ: float = 0.0
    energia_auxiliar_MJ: float = 0.0
    energia_motor_MJ: float = 0.0
    energia_secado_MJ: float = 0.0
    energia_total_MJ: float = 0.0
    COP_secado: Optional[float] = None
    fraccion_solar: Optional[float] = None

    masa_producto_seco_kg: float = 0.0
    masa_agua_evaporada_kg: float = 0.0

    t_X_obj_alcanzado_s: Optional[float] = None
    horas_clipeo_pol_B_s: float = 0.0
    horas_HR_alta_s: float = 0.0
    T_prod_max_K: Optional[float] = None

    advertencias: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def calcular_todo_transitorio(
    proyecto,
    *,
    forzantes_base: ForzantesAire,
    n_dias: int = 1,
    HR_camara_fallback: float = 0.20,
) -> ResultadosCompletosTransitorio:
    """Corre la pipeline transitoria: auxiliar(t) + cámara TD + motor escalar.

    Args:
        proyecto: ``Proyecto`` con cámara configurada en modo ``termodinamico``.
        forzantes_base: ForzantesAire del horizonte simulado en P4 — debe
            tener ``T_ent_K`` = T_salida del colector (sin auxiliar).
        n_dias: Días simulados (informativo).
        HR_camara_fallback: HR de operación de cámara para el wire-up. Solo
            se usa si el caudal o las forzantes no traen omega coherente.

    Returns:
        ResultadosCompletosTransitorio con trayectorias y acumulados.
    """
    res = ResultadosCompletosTransitorio(
        forzantes_base=forzantes_base, n_dias=n_dias,
        horizonte_s=float(forzantes_base.t_s[-1] - forzantes_base.t_s[0]),
    )

    # --- Verificaciones cruzadas ---
    errores = verificar_coherencia_proyecto(proyecto)
    if errores:
        res.errores = errores
        return res
    if proyecto.camara is None:
        res.errores.append("BG_TR_SIN_CAMARA: pipeline transitoria requiere cámara configurada.")
        return res
    if proyecto.camara.modo_calculo != "termodinamico":
        res.errores.append(
            "BG_TR_MODO_CAMARA_INCOMPATIBLE: pipeline transitoria requiere "
            "modo_calculo='termodinamico' en cámara. Cambiar el motor en P4."
        )
        return res

    caudal_kg_s = proyecto.camara.flujo.caudal_masico_kg_s

    # --- Auxiliar transitorio (si hay) ---
    if proyecto.auxiliar is not None:
        try:
            aux_tr = calcular_auxiliar_transitorio(
                proyecto.auxiliar,
                T_entrada_K_serie=forzantes_base.T_ent_K,
                t_s=forzantes_base.t_s,
                caudal_masico_kg_s=caudal_kg_s,
                I_g_W_m2_serie=forzantes_base.I_g_W_m2,
            )
            res.auxiliar = aux_tr
            res.energia_auxiliar_MJ = aux_tr.E_aux_MJ
            res.advertencias.extend(aux_tr.advertencias_unicas)
            # Construir forzantes con T_ent = T_sal_col + ΔT_aux
            forzantes_aplicadas = ForzantesAire(
                t_s=forzantes_base.t_s.copy(),
                T_ent_K=forzantes_base.T_ent_K + aux_tr.delta_T_K,
                omega_ent=forzantes_base.omega_ent.copy(),
                m_dot_aire_seco_kg_s=forzantes_base.m_dot_aire_seco_kg_s.copy(),
                T_amb_K=forzantes_base.T_amb_K.copy(),
                v_viento_ms=forzantes_base.v_viento_ms.copy(),
                I_g_W_m2=(
                    None if forzantes_base.I_g_W_m2 is None
                    else forzantes_base.I_g_W_m2.copy()
                ),
            )
        except Exception as exc:
            res.advertencias.append(f"ADVERTENCIA_AUXILIAR_TR: {exc}")
            forzantes_aplicadas = forzantes_base
    else:
        forzantes_aplicadas = forzantes_base

    res.forzantes_aplicadas = forzantes_aplicadas

    # --- Cámara TD con forzantes aplicadas ---
    # Wire-up: usamos T_ent media y omega media como "T_operacion / HR" para
    # consistencia con _calcular_termodinamico (que también arma forzantes
    # degeneradas si no recibe forzantes_aire). Con forzantes_aire presentes,
    # esos escalares solo influyen en h_conv y K_m (constantes a lo largo).
    T_ent_media_K = float(np.mean(forzantes_aplicadas.T_ent_K))
    omega_ent_media = float(np.mean(forzantes_aplicadas.omega_ent))
    # HR a partir de omega y T_ent media (aproximación; el motor sólo la usa
    # para h_conv/K_m congelados).
    try:
        from calculos.psicrometria import HR_desde_omega
        HR_op = max(0.05, min(0.95, HR_desde_omega(omega_ent_media, T_ent_media_K)))
    except Exception:
        HR_op = HR_camara_fallback
    T_amb_media_K = float(np.mean(forzantes_aplicadas.T_amb_K))
    t_max_s = float(forzantes_aplicadas.t_s[-1])
    try:
        solver_cam = calcular_camara(
            camara=proyecto.camara,
            T_operacion_K=T_ent_media_K,
            HR_operacion=HR_op,
            T_amb_K=T_amb_media_K,
            t_max_s=t_max_s,
            forzantes_aire=forzantes_aplicadas,
        )
        res.camara = solver_cam
        res.advertencias.extend(solver_cam.advertencias)
    except Exception as exc:
        res.errores.append(f"ERROR_CAMARA_TR: {exc}")
        return res

    # Trayectorias y eventos del motor TD
    res.t_X_obj_alcanzado_s = solver_cam.t_secado_s
    res.horas_clipeo_pol_B_s = getattr(solver_cam, "horas_clipeo_nocturno_s", 0.0) or 0.0
    res.horas_HR_alta_s = getattr(solver_cam, "horas_HR_alta_s", 0.0) or 0.0
    res.T_prod_max_K = getattr(solver_cam, "T_max_alcanzada_K", None)

    # Masa de producto seco y agua evaporada
    p = proyecto.camara.carga_producto
    X_0 = p.humedad_inicial_X
    ms = p.masa_total_kg / (1.0 + X_0)
    res.masa_producto_seco_kg = ms
    X_arr = solver_cam.X_prod_kg_kg
    res.masa_agua_evaporada_kg = float(ms * (X_arr[0] - X_arr[-1])) if len(X_arr) > 0 else 0.0

    # --- Motor eléctrico (escalar) ---
    if proyecto.motor is not None and proyecto.motor.potencia_electrica_W:
        res.motor_P_elec_W = float(proyecto.motor.potencia_electrica_W)
        res.energia_motor_MJ = res.motor_P_elec_W * res.horizonte_s / 1e6

    # --- Energía solar útil integrada ---
    # E_sol = ∫ ṁ_as · cp · (T_sal_col − T_amb) dt
    # T_sal_col(t) = forzantes_base.T_ent_K (antes del auxiliar)
    from calculos.auxiliar_calc import CP_AIRE
    dT_col = forzantes_base.T_ent_K - forzantes_base.T_amb_K
    Q_col_t = forzantes_base.m_dot_aire_seco_kg_s * CP_AIRE * dT_col
    Q_col_t = np.clip(Q_col_t, 0.0, None)   # noche / colector sin aporte → 0
    res.energia_solar_util_MJ = float(np.trapezoid(Q_col_t, forzantes_base.t_s) / 1e6)

    # --- Energía de secado ---
    res.energia_secado_MJ = res.masa_agua_evaporada_kg * LV_AGUA_MJ_KG

    # --- Acumulados ---
    res.energia_total_MJ = (
        res.energia_solar_util_MJ
        + res.energia_auxiliar_MJ
        + res.energia_motor_MJ
    )
    if res.energia_total_MJ > 0:
        res.COP_secado = res.energia_secado_MJ / res.energia_total_MJ
    if res.energia_solar_util_MJ + res.energia_auxiliar_MJ > 0:
        res.fraccion_solar = res.energia_solar_util_MJ / (
            res.energia_solar_util_MJ + res.energia_auxiliar_MJ
        )

    return res
