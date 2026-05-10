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

if TYPE_CHECKING:
    from core.auxiliar import Auxiliar
    from core.camara import Camara
    from core.colector import Colector

from calculos.auxiliar_calc import calcular_auxiliar
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
from core.resultados import LV_AGUA_MJ_KG

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
