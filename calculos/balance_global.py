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
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

if TYPE_CHECKING:
    pass

from calculos.auxiliar_calc import ResultadosAuxiliar as _SolverAuxiliar
from calculos.auxiliar_calc import (
    ResultadosAuxiliarTransitorio,
    calcular_auxiliar,
    calcular_auxiliar_transitorio,
)
from calculos.camara_calc import calcular_camara
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

# Desde S38 la cámara tiene un único motor (termodinámico). El alias se conserva
# por compatibilidad de las firmas internas que lo referencian.
_SolverCamaraUnion = ResultadoMotorTermodinamico

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
    chimenea: Optional[dict] = None  # dict de `caudal_natural_kgs` si aplica

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
    from core.auxiliar import ModoOperacionAuxiliar
    from core.proyecto import ModoAnalisis, Tipologia

    errores: list[str] = []
    cfg = proyecto.configuracion

    if cfg.tipologia == Tipologia.CAJA and proyecto.colector is not None:
        errores.append("PROY_CAJA_CON_COLECTOR: tipología CAJA no admite colector externo.")
    if cfg.tipologia == Tipologia.CAJA and proyecto.motor is not None:
        errores.append(
            "PROY_CAJA_CON_MOTOR: tipología CAJA usa convección natural; " "motor = None requerido."
        )
    if (
        cfg.tipologia == Tipologia.CAJA
        and proyecto.camara is not None
        and not proyecto.camara.construccion.caras_translucidas_activas()
    ):
        errores.append(
            "PROY_CAJA_SIN_CUBIERTA_TRANSLUCIDA: tipología CAJA requiere al menos "
            "una cara translúcida (cubierta_translucida_id no-None y al menos una "
            "cara activa en caras_translucidas). Sin colector externo, la radiación "
            "solar a través de la cubierta es la única fuente de energía del producto."
        )
    if (
        proyecto.auxiliar is not None
        and proyecto.auxiliar.modo_operacion == ModoOperacionAuxiliar.SERIE_POSCOLECTOR
        and proyecto.colector is None
    ):
        errores.append(
            "PROY_AUXILIAR_SERIE_SIN_COLECTOR: auxiliar en SERIE_POSCOLECTOR "
            "requiere colector definido."
        )
    if proyecto.motor is not None and proyecto.camara is None:
        errores.append("PROY_MOTOR_SIN_CAMARA: motor definido pero sin cámara configurada.")
    if cfg.modo_analisis == ModoAnalisis.ANUAL and cfg.tipologia == Tipologia.CAJA:
        errores.append(
            "PROY_ANUAL_SIN_VECTORIZACION: análisis anual para tipología CAJA "
            "no implementado en v0."
        )
    return errores


# ---------------------------------------------------------------------------
# Presión atmosférica representativa del emplazamiento
# ---------------------------------------------------------------------------

_P_REF_NIVEL_MAR_PA: float = 101325.0


def presion_representativa_proyecto(proyecto) -> tuple[float, str]:
    """Presión atmosférica constante a usar en cámara, colector y psicrométricas.

    Política híbrida (ver bitácora S32):
        1. Si ``proyecto.clima`` tiene la columna ``presion_Pa`` con datos
           válidos, se usa su **media anual** como valor único para toda la
           simulación. Captura el sesgo local sin meter variabilidad horaria.
        2. Si no hay clima cargado pero ``proyecto.emplazamiento.altitud_m``
           está definido, se calcula con la atmósfera estándar ISA
           troposférica (``motor_calc.presion_atmosferica``).
        3. Fallback: 101 325 Pa (nivel del mar).

    En altitud > 0 (p.ej. Salta ≈ 1187 m, P_ISA ≈ 88 kPa), la diferencia con
    101 325 Pa impacta significativamente la humedad absoluta de saturación
    (ω_sat ∝ P_sat/(P − P_sat)).

    Args:
        proyecto: Proyecto raíz.

    Returns:
        ``(P_Pa, origen)`` — origen es un string corto descriptivo apto para
        loguear en la UI o las advertencias del balance.
    """
    from calculos.motor_calc import presion_atmosferica

    clima = getattr(proyecto, "clima", None)
    if clima is not None:
        datos = getattr(clima, "datos", None)
        if datos is not None and "presion_Pa" in datos.columns:
            try:
                P_arr = np.asarray(datos["presion_Pa"], dtype=float)
                P_arr = P_arr[np.isfinite(P_arr)]
                if P_arr.size > 0:
                    P = float(np.mean(P_arr))
                    if P > 0:
                        etiquetas = {
                            "nasa_power": "NASA POWER",
                            "medido": "clima medido",
                            "hibrido": "clima híbrido (medido + NASA)",
                        }
                        fuente = getattr(clima, "fuente", "nasa_power")
                        etiqueta = etiquetas.get(fuente, fuente)
                        return P, f"media anual {etiqueta} = {P / 1000.0:.2f} kPa"
            except Exception:
                # Si por algún motivo la columna existe pero no es numérica,
                # caemos al siguiente nivel sin abortar el cálculo.
                pass

    empl = getattr(proyecto, "emplazamiento", None)
    if empl is not None and getattr(empl, "altitud_m", None) is not None:
        try:
            P = float(presion_atmosferica(float(empl.altitud_m)))
            if P > 0:
                return P, f"ISA(altitud={empl.altitud_m:.0f} m) = {P / 1000.0:.2f} kPa"
        except Exception:
            pass

    return _P_REF_NIVEL_MAR_PA, "nivel del mar (fallback)"


# ---------------------------------------------------------------------------
# Verificación de caudal consistente entre motor y cámara
# ---------------------------------------------------------------------------


def resumen_camara(solver_cam: _SolverCamaraUnion) -> dict:
    """Resumen uniforme de un resultado de cámara (motor termodinámico).

    Punto único donde se extraen los campos comunes del resultado del motor de
    cámara para los consumidores (balance global, UI de P7, barridos
    paramétricos). Desde S38 la cámara tiene un único motor, pero se mantiene el
    helper para no dispersar el acceso a los campos.

    Args:
        solver_cam: Resultado del motor termodinámico de cámara.

    Returns:
        dict con claves:
            ``t_secado_s`` (float | None): tiempo de secado [s]. ``None`` cuando
                no se alcanzó X_obj.
            ``masa_agua_kg`` (float): masa de agua evaporada [kg].
            ``status`` (str): estado legible del solver.
            ``convergio`` (bool): True si el secado se completó correctamente.
    """
    convergio = solver_cam.t_secado_s is not None and solver_cam.status == "X_obj_alcanzado"
    return {
        "t_secado_s": solver_cam.t_secado_s,
        "masa_agua_kg": solver_cam.masa_evaporada_total_kg,
        "status": solver_cam.status,
        "convergio": convergio,
    }


def _extraer_t_y_masa(
    solver_cam: _SolverCamaraUnion,
) -> tuple[Optional[float], float]:
    """Extrae (t_secado_s, masa_agua_kg) abstrayendo los nombres divergentes.

    Wrapper fino sobre :func:`resumen_camara` que conserva la firma de tupla
    usada históricamente por el balance global. En modo capa fina ambos campos
    existen siempre como ``float``. En modo termodinámico ``t_secado_s`` puede
    ser ``None`` cuando el solver no llegó a X_obj (status ``t_max_alcanzado`` o
    ``error``); en ese caso el balance global no puede multiplicar potencias ×
    tiempo y los devuelve como ``None``.
    """
    r = resumen_camara(solver_cam)
    return r["t_secado_s"], r["masa_agua_kg"]


def _T_salida_camara(solver_cam, T_op_K_fallback: float) -> float:
    """T del aire saliendo de la cámara [K], abstrayendo el tipo de solver.

    El modelo termodinámico estacionario expone ``T_flujo_K`` (CSTR perfecto).
    El modelo capa-fina no rastrea T del aire (el aire es reservorio): se
    devuelve ``T_op_K_fallback`` (T del aire a la entrada) como aproximación
    razonable — el enfriamiento por evaporación es típicamente < 3 K para
    caudales > 0.03 kg/s.

    Se usa para retroalimentar el lazo natural por chimenea (Picard).
    """
    T_f = getattr(solver_cam, "T_flujo_K", None)
    if isinstance(T_f, (int, float)) and T_f > 0:
        return float(T_f)
    return float(T_op_K_fallback)


def _resolver_aux_cam_const(
    proyecto,
    T_sal_colector_K: float,
    caudal_kg_s: float,
    HR_camara: float,
    T_amb_K: float,
    P_Pa: float = _P_REF_NIVEL_MAR_PA,
) -> tuple:
    """Corre auxiliar + cámara en modo constantes con un caudal dado.

    No mutea ``proyecto.camara.flujo.caudal_masico_kg_s``: el llamador
    decide si quiere persistir el caudal (lo hace antes de llamar) o
    restaurarlo después. Sí depende de que el dataclass ya tenga el
    caudal correcto cuando se invoca, porque ``calcular_camara`` lee
    ese campo.

    Returns:
        Tuple ``(solver_aux, solver_cam, T_sal_aux_K, T_sal_cam_K,
        advertencias, errores)``. ``solver_aux`` y ``solver_cam`` pueden
        ser ``None`` si el proyecto no los configura.
    """
    advertencias: list[str] = []
    errores: list[str] = []

    T_sal_aux_K = T_sal_colector_K
    solver_aux = None
    if proyecto.auxiliar is not None:
        try:
            solver_aux = calcular_auxiliar(
                auxiliar=proyecto.auxiliar,
                T_entrada_K=T_sal_colector_K,
                caudal_masico_kg_s=caudal_kg_s,
            )
            T_sal_aux_K = solver_aux.T_salida_K
            advertencias.extend(solver_aux.advertencias)
        except Exception as exc:
            advertencias.append(f"ADVERTENCIA_AUXILIAR: {exc}")

    solver_cam = None
    T_sal_cam_K = T_sal_aux_K
    if proyecto.camara is not None:
        try:
            solver_cam = calcular_camara(
                camara=proyecto.camara,
                T_operacion_K=T_sal_aux_K,
                HR_operacion=HR_camara,
                T_amb_K=T_amb_K,
                P_Pa=P_Pa,
            )
            T_sal_cam_K = _T_salida_camara(solver_cam, T_sal_aux_K)
            advertencias.extend(solver_cam.advertencias)
        except Exception as exc:
            errores.append(f"ERROR_CAMARA: {exc}")

    return solver_aux, solver_cam, T_sal_aux_K, T_sal_cam_K, advertencias, errores


def _correr_colector(
    proyecto,
    *,
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    T_entrada_K: float,
    P_amb_Pa: float = _P_REF_NIVEL_MAR_PA,
) -> tuple[Any, float]:
    """Corre el solver de colector que corresponda al tipo del proyecto.

    Lee ``unidad.velocidad_diseno_ms`` del dataclass (el orquestador puede
    mutarlo antes de llamar para acoplar con el lazo natural de chimenea).

    Returns:
        (solver_col, T_salida_colector_K). Si ``proyecto.colector`` es None,
        retorna (None, T_entrada_K).

    Raises:
        Cualquier excepción del solver de colector. El llamador decide cómo
        reportarla en ``ResultadosCompletos``.
    """
    if proyecto.colector is None:
        return None, T_entrada_K

    u = proyecto.colector.unidad
    tipo = u.tipo_colector
    pendiente_deg = (
        proyecto.emplazamiento.pendiente_colector_deg
        if proyecto.emplazamiento is not None
        else 30.0
    )
    _kwargs_comunes = dict(
        colector=proyecto.colector,
        T_amb_K=T_amb_K,
        I_g_W_m2=I_g_W_m2,
        v_viento_ms=v_viento_ms,
        P_amb_Pa=P_amb_Pa,
        T_entrada_K=T_entrada_K,
    )
    if tipo == 1:
        solver_col = calcular_colector_tipo1(
            **_kwargs_comunes,
            correlacion_nusselt=None,
            pendiente_deg=pendiente_deg,
        )
        T_salida_K = solver_col.T_salida_K
    elif tipo == 2:
        solver_col = calcular_colector_tipo2(
            **_kwargs_comunes,
            v_diseno_cs_ms=u.velocidad_diseno_ms,
            v_diseno_ci_ms=u.velocidad_diseno_ms,
            alto_cs_m=u.espaciado_m,
            alto_ci_m=u.espaciado_inferior_m,
            pendiente_deg=pendiente_deg,
        )
        T_salida_K = solver_col.T_salida_mezcla_K
    elif tipo == 3:
        solver_col = calcular_colector_tipo3(
            **_kwargs_comunes,
            alto_cs_m=u.espaciado_m,
            alto_ci_m=u.espaciado_inferior_m,
            theta_deg=pendiente_deg,
        )
        T_salida_K = solver_col.T_salida_K
    elif tipo == 4:
        solver_col = calcular_colector_tipo4(
            **_kwargs_comunes,
            alto_cs_m=u.espaciado_m,
            alto_ci_m=u.espaciado_inferior_m,
            pendiente_deg=pendiente_deg,
        )
        T_salida_K = solver_col.T_salida_K
    else:
        raise ValueError(f"BG_TIPO_COLECTOR_INVALIDO: tipo={tipo!r}")
    return solver_col, T_salida_K


def _velocidad_modulo_desde_caudal(
    colector,
    m_punto_kgs: float,
    T_op_K: float,
    P_amb_Pa: float = 101325.0,
) -> float:
    """Convierte ṁ del lazo a velocidad de aire en el canal de un módulo [m/s].

    Asume reparto uniforme entre los ``n_paralelo`` módulos del banco y usa
    el ancho × espaciado del canal principal como sección de paso. Para Tipos
    2/3/4 (dos canales) toma el canal superior — es una aproximación de
    primer orden para acoplar el colector al lazo natural; el solver luego
    aplica la mecánica detallada del bicanal en `colector_tipos234_calc`.
    """
    from calculos.motor_calc import densidad_aire

    u = colector.unidad
    b = colector.banco
    rho = densidad_aire(T_op_K, P_amb_Pa)
    A_canal = float(u.ancho_m) * float(u.espaciado_m)
    n_par = max(1, int(b.n_paralelo))
    if A_canal <= 0 or rho <= 0:
        return float(u.velocidad_diseno_ms)
    return float(m_punto_kgs) / (rho * A_canal * n_par)


def _caudal_natural_loop(
    proyecto,
    T_amb_K: float,
    T_chim_K: float,
    m_design_kgs: float,
    P_amb_Pa: float = 101325.0,
    v_viento_ms: float = 0.0,
) -> dict:
    """Caudal másico de equilibrio cuando el flujo lo induce la chimenea.

    Construye ``delta_P_resto_fn(m)`` con **escalado cuadrático** alrededor
    del punto de diseño del usuario (caudal de cámara). Es decir:

        ΔP_resto(m) ≈ ΔP_resto(m_design) · (m / m_design)²

    Esa aproximación es exacta para régimen turbulento (ΔP ∝ v²) y
    conservadora para laminar (subestima caudal, sobrestima pérdidas).
    Para prediseño es suficiente; iteración fina queda para mejora futura.

    Args:
        proyecto: Proyecto con chimenea, camara (y opcionalmente colector).
        T_amb_K: Temperatura ambiente [K].
        T_chim_K: Temperatura de la columna ascendente [K]. Recomendado:
            T_salida_camara (aire ya enfriado por evaporación). Si no se
            conoce, ~T_salida_colector − 5 K es buena aproximación para
            armario; T_amb + 25 K para CAJA.
        m_design_kgs: Caudal de diseño del usuario (de la cámara) [kg/s],
            usado como ancla del escalado cuadrático.
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        Dict de ``calculos.chimenea_calc.caudal_natural_kgs``.
    """
    from calculos.chimenea_calc import caudal_natural_kgs
    from calculos.motor_calc import (
        estimar_delta_P_camara,
        estimar_delta_P_colector,
    )

    chim = proyecto.chimenea
    camara = proyecto.camara
    H_camara_m = float(camara.geometria.alto_m)

    # ΔP de referencia a m_design (usa los estimadores existentes que leen
    # caudal/velocidad de los dataclass — no mutamos nada aquí porque ya
    # están al valor de diseño cuando se llama esta función).
    T_op_K = (T_amb_K + T_chim_K) / 2.0
    dP_col_design = (
        estimar_delta_P_colector(proyecto.colector, T_op_K, P_amb_Pa)
        if proyecto.colector is not None
        else 0.0
    )
    dP_cam_design = estimar_delta_P_camara(camara, T_op_K, P_amb_Pa)
    dP_design = dP_col_design + dP_cam_design

    if m_design_kgs <= 0 or dP_design <= 0:
        # Lazo abierto / sin pérdidas estimadas; modela como muy poco resistivo.
        def delta_P_resto_fn(_m: float) -> float:
            return 0.0

    else:

        def delta_P_resto_fn(m: float) -> float:
            return dP_design * (m / m_design_kgs) ** 2

    return caudal_natural_kgs(
        T_amb_K=T_amb_K,
        T_chim_K=T_chim_K,
        diametro_chim_m=chim.diametro_m,
        altura_chim_m=chim.altura_m,
        H_camara_m=H_camara_m,
        delta_P_resto_fn=delta_P_resto_fn,
        P_amb_Pa=P_amb_Pa,
        extractor_activo=chim.extractor_activo,
        Cp_turbina=chim.Cp_turbina,
        Kt_turbina=chim.Kt_turbina,
        diametro_extractor_m=chim.diametro_extractor_m,
        z0_terreno_m=chim.z0_terreno_m,
        v_viento_10m_ms=v_viento_ms,
    )


def _correr_colector_horizonte(
    proyecto,
    *,
    T_amb_K_serie: np.ndarray,
    v_viento_ms_serie: np.ndarray,
    I_g_POA_W_m2_serie: np.ndarray,
    m_nat_kgs_serie: np.ndarray,
    T_chim_K_serie: np.ndarray,
    P_amb_Pa: float = 101325.0,
) -> np.ndarray:
    """Corre el solver de colector hora a hora con la velocidad efectiva del
    aire impuesta por el lazo natural.

    Para cada t:
      1. v_modulo(t) = ṁ_nat(t) / (ρ·A_canal·n_paralelo) con ρ a T_op(t).
      2. Muta ``unidad.velocidad_diseno_ms`` y corre el solver estacionario
         con (T_amb, I_POA, v_viento, T_entrada=T_amb).
      3. Recoge T_salida_K. Si el solver falla, deja T_salida = T_amb (sin
         aporte del colector en esa hora).
    Restaura ``velocidad_diseno_ms`` al valor original en ``finally``.

    Args:
        proyecto: Proyecto con colector y emplazamiento.
        T_amb_K_serie: T ambiente por hora [K], shape (N,).
        v_viento_ms_serie: Velocidad de viento por hora [m/s], shape (N,).
        I_g_POA_W_m2_serie: Irradiancia POA (sobre el plano del colector)
            por hora [W/m²], shape (N,). El llamador es responsable de
            asegurar que es POA, no GHI: el solver del colector la usa
            directamente sin proyectar. Calcular con
            ``calculos.clima_calc.calcular_POA_horizonte`` cuando se
            disponga de DNI/GHI/DHI.
        m_nat_kgs_serie: Caudal másico del lazo natural por hora [kg/s].
        T_chim_K_serie: T de la chimenea por hora [K], para promediar T_op.
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        Array de shape (N,) con ``T_salida_colector_K(t)``. Si el proyecto
        no tiene colector, devuelve ``T_amb_K_serie`` (sin aporte).
    """
    N = len(T_amb_K_serie)
    if proyecto.colector is None:
        return np.asarray(T_amb_K_serie, dtype=float).copy()

    u = proyecto.colector.unidad
    v_diseno_original = float(u.velocidad_diseno_ms)
    T_sal_col_arr = np.empty(N, dtype=float)

    try:
        for i in range(N):
            T_amb_i = float(T_amb_K_serie[i])
            T_chim_i = float(T_chim_K_serie[i])
            m_i = float(m_nat_kgs_serie[i])

            # Velocidad efectiva del módulo a partir del caudal natural.
            T_op_K = 0.5 * (T_amb_i + T_chim_i)
            v_modulo = _velocidad_modulo_desde_caudal(
                proyecto.colector,
                m_i,
                T_op_K,
                P_amb_Pa,
            )
            v_modulo = float(np.clip(v_modulo, 0.05, 15.0))
            u.velocidad_diseno_ms = v_modulo
            try:
                _solver_col, T_sal_K = _correr_colector(
                    proyecto,
                    T_amb_K=T_amb_i,
                    I_g_W_m2=float(I_g_POA_W_m2_serie[i]),
                    v_viento_ms=float(v_viento_ms_serie[i]),
                    T_entrada_K=T_amb_i,
                    P_amb_Pa=P_amb_Pa,
                )
                T_sal_col_arr[i] = T_sal_K
            except Exception:
                # Régimen patológico (Re fuera de calibración, fsolve falla,
                # etc.): asumimos sin aporte del colector en esa hora.
                T_sal_col_arr[i] = T_amb_i
    finally:
        u.velocidad_diseno_ms = v_diseno_original

    # T_sal_col no puede caer por debajo de T_amb (gas ideal + radiación
    # positiva).
    T_sal_col_arr = np.maximum(T_sal_col_arr, np.asarray(T_amb_K_serie, dtype=float))
    return T_sal_col_arr


def _caudal_natural_horizonte(
    proyecto,
    T_amb_K_serie: np.ndarray,
    T_chim_K_serie: np.ndarray,
    m_ref_kgs: float,
    P_amb_Pa: float = 101325.0,
    v_viento_ms_serie: Optional[np.ndarray] = None,
) -> dict:
    """Resuelve el caudal natural por hora sobre un horizonte temporal.

    Para cada t llama a ``caudal_natural_kgs`` con T_amb(t), T_chim(t) y la
    misma ``delta_P_resto_fn`` cuadrática que ``_caudal_natural_loop`` (el
    escalado se ancla en ``m_ref_kgs``, típicamente el caudal de diseño).
    Los t donde el tiro es nulo (T_chim ≤ T_amb) reciben ``m_punto = 0``;
    el llamador decide cómo manejarlos (en pipeline transitoria, conviene
    un piso pequeño para no romper interpolaciones del motor TD).

    Returns:
        Dict con arrays shape (N,) y advertencias agregadas:
            - m_punto_kgs : caudal natural por hora [kg/s].
            - v_chim_ms   : velocidad media por hora [m/s].
            - delta_P_tiro_Pa, delta_P_chimenea_Pa, delta_P_resto_Pa.
            - Re_chimenea : Reynolds por hora.
            - T_chim_K    : copia de T_chim_K_serie (entrada).
            - H_eff_m     : escalar (no varía).
            - advertencias: códigos únicos vistos en cualquier hora.
            - horas_sin_tiro : contador de horas con tiro nulo.
    """
    from calculos.chimenea_calc import caudal_natural_kgs
    from calculos.motor_calc import (
        estimar_delta_P_camara,
        estimar_delta_P_colector,
    )

    chim = proyecto.chimenea
    camara = proyecto.camara
    H_camara_m = float(camara.geometria.alto_m)
    N = len(T_amb_K_serie)

    # ΔP_resto de referencia evaluado a un T_op medio del horizonte.
    T_op_K_ref = 0.5 * (float(np.mean(T_amb_K_serie)) + float(np.mean(T_chim_K_serie)))
    dP_col_ref = (
        estimar_delta_P_colector(proyecto.colector, T_op_K_ref, P_amb_Pa)
        if proyecto.colector is not None
        else 0.0
    )
    dP_cam_ref = estimar_delta_P_camara(camara, T_op_K_ref, P_amb_Pa)
    dP_ref = dP_col_ref + dP_cam_ref

    if m_ref_kgs <= 0 or dP_ref <= 0:

        def _dP_resto(_m: float) -> float:
            return 0.0

    else:

        def _dP_resto(m: float) -> float:
            return dP_ref * (m / m_ref_kgs) ** 2

    m_arr = np.zeros(N)
    v_arr = np.zeros(N)
    dPT_arr = np.zeros(N)
    dPC_arr = np.zeros(N)
    dPR_arr = np.zeros(N)
    Re_arr = np.zeros(N)
    advs_set: set[str] = set()
    horas_sin_tiro = 0
    H_eff_m = chim.altura_m + H_camara_m

    v_viento_arr = (
        np.asarray(v_viento_ms_serie, dtype=float) if v_viento_ms_serie is not None else np.zeros(N)
    )

    for i in range(N):
        try:
            r = caudal_natural_kgs(
                T_amb_K=float(T_amb_K_serie[i]),
                T_chim_K=float(T_chim_K_serie[i]),
                diametro_chim_m=chim.diametro_m,
                altura_chim_m=chim.altura_m,
                H_camara_m=H_camara_m,
                delta_P_resto_fn=_dP_resto,
                P_amb_Pa=P_amb_Pa,
                extractor_activo=chim.extractor_activo,
                Cp_turbina=chim.Cp_turbina,
                Kt_turbina=chim.Kt_turbina,
                diametro_extractor_m=chim.diametro_extractor_m,
                z0_terreno_m=chim.z0_terreno_m,
                v_viento_10m_ms=float(v_viento_arr[i]),
            )
        except Exception:
            # Brentq fuera del bracket: marcamos hora como sin tiro.
            horas_sin_tiro += 1
            continue
        m_arr[i] = r["m_punto_kgs"]
        v_arr[i] = r["v_chim_ms"]
        dPT_arr[i] = r["delta_P_tiro_Pa"]
        dPC_arr[i] = r["delta_P_chimenea_Pa"]
        dPR_arr[i] = r["delta_P_resto_Pa"]
        Re_arr[i] = r["Re_chimenea"]
        if r["m_punto_kgs"] <= 0:
            horas_sin_tiro += 1
        for a in r.get("advertencias", []) or []:
            # quitamos el sufijo numérico de los mensajes para deduplicar
            advs_set.add(a.split(":")[0])

    return {
        "m_punto_kgs": m_arr,
        "v_chim_ms": v_arr,
        "delta_P_tiro_Pa": dPT_arr,
        "delta_P_chimenea_Pa": dPC_arr,
        "delta_P_resto_Pa": dPR_arr,
        "Re_chimenea": Re_arr,
        "T_chim_K": np.asarray(T_chim_K_serie, dtype=float).copy(),
        "H_eff_m": H_eff_m,
        "advertencias": sorted(advs_set),
        "horas_sin_tiro": horas_sin_tiro,
    }


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
    I_g_POA_W_m2: Optional[np.ndarray] = None,
    Q_rad_aire_W: Optional[np.ndarray] = None,
    dt_s: float = 3600.0,
    t0_utc=None,
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
        I_g_POA_W_m2: Serie horaria de irradiancia sobre el plano del colector
            (POA) [W/m²]. None → no se propaga (el balance global decide el
            fallback al re-correr el colector con caudal natural). Para forzantes
            reales armadas desde clima, computar con
            ``calculos.clima_calc.calcular_POA_horizonte``.
        Q_rad_aire_W: Serie horaria de potencia radiativa que calienta el aire
            de la cámara vía superficies internas [W]. None → array de ceros
            (comportamiento histórico). Computar con
            ``calculos.radiacion_camara.series_radiacion_camara``.
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
            f"FORZANTES_MODO_INVALIDO: modo='{modo}' no reconocido. " f"Opciones: {modos_validos}."
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

    # --- I_g_POA (irradiancia sobre plano del colector) ---
    if I_g_POA_W_m2 is not None:
        I_g_POA_base = np.asarray(I_g_POA_W_m2, dtype=float)
        if len(I_g_POA_base) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: I_g_POA_W_m2 tiene "
                f"{len(I_g_POA_base)} elementos, esperado {n_base}."
            )
    else:
        I_g_POA_base = None

    # --- Q_rad_aire (potencia radiativa al aire vía superficies internas) ---
    if Q_rad_aire_W is not None:
        Q_rad_aire_base = np.asarray(Q_rad_aire_W, dtype=float)
        if len(Q_rad_aire_base) != n_base:
            raise ValueError(
                f"FORZANTES_LONGITUD_INCONSISTENTE: Q_rad_aire_W tiene "
                f"{len(Q_rad_aire_base)} elementos, esperado {n_base}."
            )
    else:
        Q_rad_aire_base = np.zeros(n_base)

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
        I_g_POA_arr = np.tile(I_g_POA_base, n_reps) if I_g_POA_base is not None else None
        Q_rad_aire_arr = np.tile(Q_rad_aire_base, n_reps)
    else:
        T_ent_arr = T_ent_base.copy()
        omega_arr = omega.copy()
        v_arr = v_base.copy()
        T_amb_arr = T_amb_base.copy()
        m_arr = m_base.copy()
        I_g_arr = I_g_base.copy()
        I_g_POA_arr = I_g_POA_base.copy() if I_g_POA_base is not None else None
        Q_rad_aire_arr = Q_rad_aire_base.copy()

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
        I_g_POA_W_m2=I_g_POA_arr,
        Q_rad_aire_W=Q_rad_aire_arr,
        t0_utc=t0_utc,
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
    Q_rad_aire_max_W: float = 0.0,
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
        I_g_max_W_m2: Irradiancia equivalente al producto, pico al mediodía
            [W/m²]. Default 0 (sin radiación — cámara opaca o sin caras
            translúcidas). Típico cielo claro: 800–1000 W/m². La curva diaria
            es una semicampana sinusoidal positiva (sol entre h=6 y h=18 si
            hora_pico=12); de noche I_g=0.
        Q_rad_aire_max_W: Potencia radiativa al aire, pico al mediodía [W].
            Default 0. Misma forma de semicampana que ``I_g_max_W_m2`` (no
            hay posición solar horaria en modo sintético para diferenciar
            caras) — ver ``calculos.radiacion_camara.factores_sinteticos``.
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
    Q_rad_aire_arr = np.maximum(0.0, float(Q_rad_aire_max_W) * np.sin(fase_dia))

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
        # En modo sintético no hay separación física GHI/POA: usamos la
        # misma curva como POA del colector. Si el usuario quiere distinguir
        # explícitamente, debe armar las forzantes con armar_forzantes_aire.
        I_g_POA_W_m2=I_g_arr.copy(),
        Q_rad_aire_W=Q_rad_aire_arr,
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

    # --- Presión atmosférica representativa del emplazamiento ---
    # Se computa UNA vez y se propaga a colector, cámara y auxiliar.
    P_proyecto_Pa, _P_origen = presion_representativa_proyecto(proyecto)
    res.advertencias.append(f"ADV_PRESION_PROYECTO: {_P_origen}.")

    # --- Solver colector (pase inicial; puede re-correrse abajo si
    # el lazo natural por chimenea cambia el caudal y, por tanto, la
    # velocidad efectiva del aire en el colector).
    T_salida_colector_K = T_entrada_K  # fallback si no hay colector
    if proyecto.colector is not None:
        try:
            solver_col, T_salida_colector_K = _correr_colector(
                proyecto,
                T_amb_K=T_amb_K,
                I_g_W_m2=I_g_W_m2,
                v_viento_ms=v_viento_ms,
                T_entrada_K=T_entrada_K,
                P_amb_Pa=P_proyecto_Pa,
            )
            res.colector = solver_col
            res.advertencias.extend(solver_col.advertencias)
        except Exception as exc:
            res.errores.append(f"ERROR_COLECTOR: {exc}")
            return res

    # --- Caudal del lazo: motor forzado o chimenea natural ---
    # Por defecto se usa el caudal user-set en la cámara. Si no hay motor
    # pero hay chimenea, se itera (Picard) el lazo natural: T_chim ↔ ṁ_nat
    # ↔ T_salida_colector → T_chim ... hasta convergencia. En cada iteración
    # se re-corre el colector con la nueva velocidad efectiva del aire (ṁ
    # natural mapeado a v_diseno de un módulo).
    caudal_design_kg_s = (
        proyecto.camara.flujo.caudal_masico_kg_s if proyecto.camara is not None else 0.030
    )
    v_diseno_user_ms = (
        proyecto.colector.unidad.velocidad_diseno_ms if proyecto.colector is not None else None
    )
    _picard_mutado = False
    chimenea_activa = (
        proyecto.motor is None and proyecto.chimenea is not None and proyecto.camara is not None
    )

    try:
        if not chimenea_activa:
            # --- Single-pass (motor forzado o sin chimenea) ---
            solver_aux, solver_cam, T_salida_aux_K, _T_sal_cam_K, advs, errs = (
                _resolver_aux_cam_const(
                    proyecto,
                    T_sal_colector_K=T_salida_colector_K,
                    caudal_kg_s=caudal_design_kg_s,
                    HR_camara=HR_camara,
                    T_amb_K=T_amb_K,
                    P_Pa=P_proyecto_Pa,
                )
            )
            res.auxiliar = solver_aux
            res.camara = solver_cam
            res.T_entrada_camara_K = T_salida_aux_K
            res.advertencias.extend(advs)
            if errs:
                res.errores.extend(errs)
                return res
        else:
            # --- Picard sobre el lazo natural (cerrado por el colector) ---
            # En cada iteración: T_chim → caudal_natural → ṁ_nat
            # → mutar v_diseno del módulo → re-correr colector
            # → T_salida_colector_NUEVA → T_chim_NUEVO = T_sal_col − 5 K.
            # La cámara queda fuera del loop: se corre 1 sola vez al final
            # con el caudal convergido (su feedback térmico sobre T_chim es
            # de segundo orden — enfriamiento por evaporación < 3 K — y el
            # solver de capa fina no expone T_aire explícita).
            #
            # Para CAJA (sin colector) el loop converge trivialmente en
            # 1 iter: T_chim queda en T_amb + 25 K (heurística del techo
            # translúcido, no hay variable interna que dependa de ṁ).
            res.advertencias.clear()

            MAX_ITER_PICARD: int = 10
            TOL_T_CHIM_K: float = 0.5

            def _T_chim_desde_colector(T_sal_col_K: float) -> float:
                if proyecto.colector is not None:
                    return max(T_sal_col_K - 5.0, T_amb_K + 1.0)
                return T_amb_K + 25.0

            T_chim_K_iter = _T_chim_desde_colector(T_salida_colector_K)
            res_chim_iter: Optional[dict] = None
            iter_count: int = 0
            converged: bool = False
            delta_final: float = float("inf")
            m_nat_final: float = caudal_design_kg_s
            _picard_mutado = True

            for iter_count in range(1, MAX_ITER_PICARD + 1):
                # 1) Caudal natural con T_chim del paso previo.
                try:
                    res_chim_iter = _caudal_natural_loop(
                        proyecto,
                        T_amb_K,
                        T_chim_K_iter,
                        proyecto.camara.flujo.caudal_masico_kg_s,
                        P_amb_Pa=P_proyecto_Pa,
                        v_viento_ms=v_viento_ms,
                    )
                except Exception as exc:
                    res.advertencias.append(f"ADV_PICARD_CHIM_BRENTQ: {exc} (iter {iter_count})")
                    break

                m_nat = float(res_chim_iter.get("m_punto_kgs", 0.0))
                if m_nat <= 0.0:
                    # Sin tiro térmico (T_chim ≤ T_amb). Reportamos el dict
                    # vacío y salimos: el lazo natural queda inerte y la
                    # cámara correrá con el caudal de diseño del usuario.
                    converged = True
                    break

                m_nat_final = m_nat
                proyecto.camara.flujo.caudal_masico_kg_s = m_nat

                # 2) Re-correr colector con la velocidad efectiva que
                # corresponde al caudal natural.
                if proyecto.colector is not None:
                    T_op_K = 0.5 * (T_amb_K + T_chim_K_iter)
                    v_nueva = _velocidad_modulo_desde_caudal(
                        proyecto.colector,
                        m_nat,
                        T_op_K,
                    )
                    # Limites razonables (Re fuera de calibración).
                    v_nueva = float(np.clip(v_nueva, 0.05, 15.0))
                    proyecto.colector.unidad.velocidad_diseno_ms = v_nueva
                    try:
                        solver_col_iter, T_salida_colector_K = _correr_colector(
                            proyecto,
                            T_amb_K=T_amb_K,
                            I_g_W_m2=I_g_W_m2,
                            v_viento_ms=v_viento_ms,
                            T_entrada_K=T_entrada_K,
                            P_amb_Pa=P_proyecto_Pa,
                        )
                        res.colector = solver_col_iter
                    except Exception as exc:
                        res.advertencias.append(
                            f"ADV_PICARD_COL_RECORRIDA: {exc} "
                            f"(iter {iter_count}, v={v_nueva:.2f} m/s)"
                        )
                        break

                # 3) T_chim nuevo del colector convergido.
                T_chim_K_new = _T_chim_desde_colector(T_salida_colector_K)
                delta_final = abs(T_chim_K_new - T_chim_K_iter)
                T_chim_K_iter = T_chim_K_new
                if delta_final < TOL_T_CHIM_K:
                    converged = True
                    break

            # --- Última corrida de aux + cámara con caudal convergido ---
            solver_aux, solver_cam, T_sal_aux_K, _T_sal_cam_K, _advs, errs = (
                _resolver_aux_cam_const(
                    proyecto,
                    T_sal_colector_K=T_salida_colector_K,
                    caudal_kg_s=m_nat_final,
                    HR_camara=HR_camara,
                    T_amb_K=T_amb_K,
                    P_Pa=P_proyecto_Pa,
                )
            )
            if errs:
                res.errores.extend(errs)
                return res
            res.auxiliar = solver_aux
            res.camara = solver_cam
            res.T_entrada_camara_K = T_sal_aux_K

            # Advertencias del último pase (no duplicamos las de iter intermedias).
            if res.colector is not None:
                res.advertencias.extend(getattr(res.colector, "advertencias", []) or [])
            if res.auxiliar is not None:
                res.advertencias.extend(getattr(res.auxiliar, "advertencias", []) or [])
            if res.camara is not None:
                res.advertencias.extend(getattr(res.camara, "advertencias", []) or [])

            # Metadata de la iteración en res.chimenea.
            if res_chim_iter is not None:
                res_chim_iter["iteraciones"] = iter_count
                res_chim_iter["convergio"] = converged
                res_chim_iter["delta_T_chim_final_K"] = delta_final
                res_chim_iter["T_chim_K"] = T_chim_K_iter
                res.chimenea = res_chim_iter
                res.advertencias.extend(res_chim_iter.get("advertencias", []))
            if (not converged) and iter_count >= MAX_ITER_PICARD:
                res.advertencias.append(
                    f"ADV_PICARD_CHIM_NO_CONVERGIO: lazo natural alcanzó "
                    f"{MAX_ITER_PICARD} iteraciones sin |ΔT_chim| < "
                    f"{TOL_T_CHIM_K} K (último ΔT = {delta_final:.2f} K). "
                    "Resultados son del último pase."
                )
    finally:
        # Restaurar estado original del proyecto: caudal de cámara y
        # velocidad de diseño del colector.
        if _picard_mutado and proyecto.camara is not None:
            proyecto.camara.flujo.caudal_masico_kg_s = caudal_design_kg_s
        if _picard_mutado and v_diseno_user_ms is not None:
            proyecto.colector.unidad.velocidad_diseno_ms = v_diseno_user_ms

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
            E_aux = res.auxiliar.Q_efectivo_W * t_s / 1e6 if res.auxiliar else 0.0
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
        t0_utc: Instante absoluto (UTC) de ``t_s[0]``, heredado de las forzantes.
            Permite reanclar las trayectorias del motor a timestamps reales para
            contrastarlas contra datos medidos (mejora 38, fase 4). ``None`` con
            forzantes sintéticas.
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
    t0_utc: Optional[object] = None
    camara: Optional[ResultadoMotorTermodinamico] = None
    auxiliar: Optional[ResultadosAuxiliarTransitorio] = None
    chimenea: Optional[dict] = None  # series horarias del lazo natural si aplica
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
        forzantes_base=forzantes_base,
        n_dias=n_dias,
        horizonte_s=float(forzantes_base.t_s[-1] - forzantes_base.t_s[0]),
        t0_utc=getattr(forzantes_base, "t0_utc", None),
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

    # --- Presión atmosférica representativa del emplazamiento ---
    P_proyecto_Pa, _P_origen = presion_representativa_proyecto(proyecto)
    res.advertencias.append(f"ADV_PRESION_PROYECTO: {_P_origen}.")

    caudal_kg_s = proyecto.camara.flujo.caudal_masico_kg_s
    chimenea_activa = proyecto.motor is None and proyecto.chimenea is not None

    def _correr_aux_y_armar_forzantes(
        m_dot_serie: np.ndarray,
        caudal_para_aux_kg_s: float,
        T_sal_col_serie: Optional[np.ndarray] = None,
    ) -> ForzantesAire:
        """Corre auxiliar transitorio (si existe) y arma las forzantes
        finales para el motor TD con el ``m_dot_serie`` dado.

        Si se provee ``T_sal_col_serie`` (acople con re-cálculo del colector
        por hora), se usa esa serie como T de entrada al auxiliar / cámara
        en vez de ``forzantes_base.T_ent_K``.
        """
        nonlocal res
        T_sal_col_base = (
            np.asarray(T_sal_col_serie, dtype=float)
            if T_sal_col_serie is not None
            else forzantes_base.T_ent_K.copy()
        )
        T_ent_arr = T_sal_col_base.copy()
        omega_arr = forzantes_base.omega_ent.copy()
        if proyecto.auxiliar is not None:
            try:
                aux_tr = calcular_auxiliar_transitorio(
                    proyecto.auxiliar,
                    T_entrada_K_serie=T_sal_col_base,
                    t_s=forzantes_base.t_s,
                    caudal_masico_kg_s=caudal_para_aux_kg_s,
                    I_g_W_m2_serie=forzantes_base.I_g_W_m2,
                )
                res.auxiliar = aux_tr
                res.energia_auxiliar_MJ = aux_tr.E_aux_MJ
                T_ent_arr = T_sal_col_base + aux_tr.delta_T_K
            except Exception as exc:
                res.advertencias.append(f"ADVERTENCIA_AUXILIAR_TR: {exc}")
        return ForzantesAire(
            t_s=forzantes_base.t_s.copy(),
            T_ent_K=T_ent_arr,
            omega_ent=omega_arr,
            m_dot_aire_seco_kg_s=np.asarray(m_dot_serie, dtype=float).copy(),
            T_amb_K=forzantes_base.T_amb_K.copy(),
            v_viento_ms=forzantes_base.v_viento_ms.copy(),
            I_g_W_m2=(None if forzantes_base.I_g_W_m2 is None else forzantes_base.I_g_W_m2.copy()),
        )

    def _correr_motor_TD(forzantes: ForzantesAire) -> Optional[ResultadoMotorTermodinamico]:
        T_ent_media_K = float(np.mean(forzantes.T_ent_K))
        omega_ent_media = float(np.mean(forzantes.omega_ent))
        try:
            from calculos.psicrometria import HR_desde_omega

            HR_op = max(0.05, min(0.95, HR_desde_omega(omega_ent_media, T_ent_media_K)))
        except Exception:
            HR_op = HR_camara_fallback
        T_amb_media_K = float(np.mean(forzantes.T_amb_K))
        t_max_s_local = float(forzantes.t_s[-1])
        return calcular_camara(
            camara=proyecto.camara,
            T_operacion_K=T_ent_media_K,
            HR_operacion=HR_op,
            T_amb_K=T_amb_media_K,
            P_Pa=P_proyecto_Pa,
            t_max_s=t_max_s_local,
            forzantes_aire=forzantes,
        )

    # ---------------- Pipeline normal (sin chimenea o con motor) ----------------
    if not chimenea_activa:
        forzantes_aplicadas = _correr_aux_y_armar_forzantes(
            forzantes_base.m_dot_aire_seco_kg_s,
            caudal_kg_s,
        )
        if proyecto.auxiliar is not None and res.auxiliar is not None:
            res.advertencias.extend(res.auxiliar.advertencias_unicas)
        res.forzantes_aplicadas = forzantes_aplicadas
        try:
            solver_cam = _correr_motor_TD(forzantes_aplicadas)
            res.camara = solver_cam
            res.advertencias.extend(solver_cam.advertencias)
        except Exception as exc:
            res.errores.append(f"ERROR_CAMARA_TR: {exc}")
            return res
    else:
        # ---------------- Picard transitorio con chimenea ----------------
        # T_chim inicial por hora: post-colector (margen evaporativo) o
        # default CAJA (sin colector). Clamp ≥ T_amb + 1 K.
        if proyecto.colector is not None:
            T_chim_serie = forzantes_base.T_ent_K - 5.0
        else:
            T_chim_serie = forzantes_base.T_amb_K + 25.0
        T_chim_serie = np.maximum(T_chim_serie, forzantes_base.T_amb_K + 1.0)

        MAX_ITER_TR: int = 5  # cada iter corre el motor TD: 5 alcanza
        TOL_T_CHIM_K: float = 0.5
        m_ref_kgs = caudal_kg_s  # ancla para escalar ΔP_resto cuadrático
        # Piso para evitar ṁ=0 en horas sin tiro (motor TD interpolaría 0).
        M_DOT_PISO_KGS: float = 1.0e-4

        chim_dict_final: Optional[dict] = None
        solver_cam: Optional[ResultadoMotorTermodinamico] = None
        forzantes_aplicadas: Optional[ForzantesAire] = None
        iter_count: int = 0
        converged: bool = False
        delta_final: float = float("inf")
        # Series del colector re-corrido (sólo si hay colector); inicialmente
        # tomamos las que vinieron en ``forzantes_base.T_ent_K``.
        T_sal_col_serie = forzantes_base.T_ent_K.copy()

        for iter_count in range(1, MAX_ITER_TR + 1):
            # 1) ṁ_nat(t) sobre el horizonte.
            chim_dict = _caudal_natural_horizonte(
                proyecto,
                forzantes_base.T_amb_K,
                T_chim_serie,
                m_ref_kgs,
                P_amb_Pa=P_proyecto_Pa,
                v_viento_ms_serie=forzantes_base.v_viento_ms,
            )
            m_nat_serie = np.maximum(chim_dict["m_punto_kgs"], M_DOT_PISO_KGS)

            # 2) Re-correr el colector por hora con v efectiva impuesta por
            #    el lazo natural. Para CAJA (sin colector) la serie queda
            #    igual a T_amb (sin aporte del colector).
            #
            #    Para el solver de colector necesitamos POA (irradiancia
            #    sobre el plano inclinado), no GHI. Usamos la POA precomputada
            #    en las forzantes si está disponible; sino caemos a GHI con
            #    aviso explícito (en latitudes altas / tilt agresivo esto
            #    subestima T_sal_col).
            if proyecto.colector is not None:
                if forzantes_base.I_g_POA_W_m2 is not None:
                    I_para_colector = forzantes_base.I_g_POA_W_m2
                else:
                    I_para_colector = forzantes_base.I_g_W_m2
                    if iter_count == 1:
                        res.advertencias.append(
                            "ADV_PICARD_POA_NO_DISPONIBLE: forzantes_base no "
                            "trae I_g_POA_W_m2 — el colector se re-corre con "
                            "I_g_W_m2 (irradiancia equivalente de la cámara, "
                            "no del colector) como aproximación. Solo ocurre en "
                            "modo sintético, donde ambas curvas coinciden por "
                            "construcción. Para fidelidad física completa, "
                            "armar las forzantes desde clima real con "
                            "calcular_POA_horizonte."
                        )
                T_sal_col_serie = _correr_colector_horizonte(
                    proyecto,
                    T_amb_K_serie=forzantes_base.T_amb_K,
                    v_viento_ms_serie=forzantes_base.v_viento_ms,
                    I_g_POA_W_m2_serie=I_para_colector,
                    m_nat_kgs_serie=m_nat_serie,
                    T_chim_K_serie=T_chim_serie,
                    P_amb_Pa=P_proyecto_Pa,
                )

            # 3) Auxiliar (con ṁ medio del horizonte) + forzantes con ṁ(t).
            #    El auxiliar transitorio no acepta caudal array; promediar es
            #    una aproximación de primer orden razonable.
            m_dot_medio = float(np.mean(m_nat_serie))
            res.auxiliar = None  # se vuelve a setear si auxiliar presente
            forzantes_aplicadas = _correr_aux_y_armar_forzantes(
                m_nat_serie,
                m_dot_medio,
                T_sal_col_serie=T_sal_col_serie,
            )

            # 4) Motor TD con las nuevas forzantes.
            try:
                solver_cam = _correr_motor_TD(forzantes_aplicadas)
            except Exception as exc:
                res.errores.append(f"ERROR_CAMARA_TR: {exc}")
                return res

            # 5) T_chim_nueva interpolada al grid horario; clamp ≥ T_amb + 1.
            T_chim_nueva = np.interp(
                forzantes_base.t_s,
                solver_cam.t_array_s,
                solver_cam.T_flujo_K,
            )
            T_chim_nueva = np.maximum(T_chim_nueva, forzantes_base.T_amb_K + 1.0)

            delta_final = float(np.max(np.abs(T_chim_nueva - T_chim_serie)))
            T_chim_serie = T_chim_nueva
            chim_dict_final = chim_dict
            if delta_final < TOL_T_CHIM_K:
                converged = True
                break

        # Persistir resultados.
        res.camara = solver_cam
        res.forzantes_aplicadas = forzantes_aplicadas
        res.advertencias.extend(solver_cam.advertencias)
        if proyecto.auxiliar is not None and res.auxiliar is not None:
            res.advertencias.extend(res.auxiliar.advertencias_unicas)

        if chim_dict_final is not None:
            chim_dict_final["t_s"] = forzantes_base.t_s.copy()
            chim_dict_final["T_chim_K"] = T_chim_serie
            chim_dict_final["iteraciones"] = iter_count
            chim_dict_final["convergio"] = converged
            chim_dict_final["delta_T_chim_final_K"] = delta_final
            chim_dict_final["m_promedio_kgs"] = float(np.mean(chim_dict_final["m_punto_kgs"]))
            chim_dict_final["m_max_kgs"] = float(np.max(chim_dict_final["m_punto_kgs"]))
            res.chimenea = chim_dict_final
            for a in chim_dict_final.get("advertencias", []) or []:
                if a:
                    res.advertencias.append(a)
        if (not converged) and iter_count >= MAX_ITER_TR:
            res.advertencias.append(
                f"ADV_PICARD_CHIM_TR_NO_CONVERGIO: lazo natural transitorio "
                f"alcanzó {MAX_ITER_TR} iter sin |ΔT_chim| < {TOL_T_CHIM_K} K "
                f"(último ΔT máx = {delta_final:.2f} K). "
                "Resultados son del último pase."
            )

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
    # E_sol = ∫ ṁ_as(t) · cp · (T_sal_col(t) − T_amb(t)) dt
    # En pipeline sin chimenea: T_sal_col(t) = forzantes_base.T_ent_K,
    # ṁ_as(t) = forzantes_base.m_dot_aire_seco_kg_s (caudal de diseño).
    # En pipeline con chimenea acoplada: usar las series re-calculadas en
    # ``forzantes_aplicadas`` (T_ent_K antes del aporte del auxiliar y
    # ṁ_nat impuesto por el lazo natural).
    from calculos.auxiliar_calc import CP_AIRE

    if chimenea_activa and forzantes_aplicadas is not None:
        # T_sal_col coherente con el caudal natural — sustraemos ΔT_aux si
        # hay auxiliar, porque forzantes_aplicadas.T_ent_K ya lo incluye.
        if proyecto.auxiliar is not None and res.auxiliar is not None:
            T_sal_col_eval = forzantes_aplicadas.T_ent_K - res.auxiliar.delta_T_K
        else:
            T_sal_col_eval = forzantes_aplicadas.T_ent_K
        m_dot_eval = forzantes_aplicadas.m_dot_aire_seco_kg_s
    else:
        T_sal_col_eval = forzantes_base.T_ent_K
        m_dot_eval = forzantes_base.m_dot_aire_seco_kg_s
    dT_col = T_sal_col_eval - forzantes_base.T_amb_K
    Q_col_t = m_dot_eval * CP_AIRE * dT_col
    Q_col_t = np.clip(Q_col_t, 0.0, None)  # noche / colector sin aporte → 0
    res.energia_solar_util_MJ = float(np.trapezoid(Q_col_t, forzantes_base.t_s) / 1e6)

    # --- Energía de secado ---
    res.energia_secado_MJ = res.masa_agua_evaporada_kg * LV_AGUA_MJ_KG

    # --- Acumulados ---
    res.energia_total_MJ = (
        res.energia_solar_util_MJ + res.energia_auxiliar_MJ + res.energia_motor_MJ
    )
    if res.energia_total_MJ > 0:
        res.COP_secado = res.energia_secado_MJ / res.energia_total_MJ
    if res.energia_solar_util_MJ + res.energia_auxiliar_MJ > 0:
        res.fraccion_solar = res.energia_solar_util_MJ / (
            res.energia_solar_util_MJ + res.energia_auxiliar_MJ
        )

    return res


# ===========================================================================
# S40 — Ventana de producción (gran escala): clima real horario sobre [inicio, fin]
# ===========================================================================


def _correr_colector_horizonte_forzado(
    proyecto,
    *,
    T_amb_K_serie: np.ndarray,
    v_viento_ms_serie: np.ndarray,
    I_g_POA_W_m2_serie: np.ndarray,
    P_amb_Pa: float,
    m_dot_sistema_kg_s: Optional[float] = None,
) -> tuple[np.ndarray, int]:
    """Corre el colector hora a hora con el caudal que impone el ventilador.

    El ventilador fija el caudal del sistema (S41): la velocidad de aire en el
    canal de cada módulo se deriva de ese caudal —
    ``v = ṁ / (ρ(T_amb(t)) · A_canal · n_paralelo)`` — igual que hace
    ``_correr_colector_horizonte`` en el lazo natural. Esto mantiene coherente
    la cadena banco → caño maestro → cámara: el colector se evalúa al caudal
    que realmente circula, no a su ``velocidad_diseno_ms`` nominal.

    Si ``m_dot_sistema_kg_s`` es None (o no positivo), se conserva el
    comportamiento previo: el colector corre a ``velocidad_diseno_ms``.

    Si el solver falla en una hora, se asume sin aporte (T_salida = T_amb) y
    se cuenta la falla — el llamador decide si emitir advertencia. Si no hay
    colector, devuelve (T_amb, 0).

    Returns:
        (T_salida_colector_K(t), n_horas_con_falla_del_solver).
    """
    T_amb_arr = np.asarray(T_amb_K_serie, dtype=float)
    if proyecto.colector is None:
        return T_amb_arr.copy(), 0
    N = len(T_amb_arr)
    T_sal = np.empty(N, dtype=float)
    n_fallas = 0

    u = proyecto.colector.unidad
    v_diseno_original = float(u.velocidad_diseno_ms)
    derivar_v = m_dot_sistema_kg_s is not None and m_dot_sistema_kg_s > 0.0
    try:
        for i in range(N):
            T_amb_i = float(T_amb_arr[i])
            if derivar_v:
                # ρ a T_entrada = T_amb (convención S36: ṁ fijado con ρ(T_entrada)).
                v_modulo = _velocidad_modulo_desde_caudal(
                    proyecto.colector,
                    float(m_dot_sistema_kg_s),
                    T_amb_i,
                    P_amb_Pa,
                )
                u.velocidad_diseno_ms = float(np.clip(v_modulo, 0.05, 15.0))
            try:
                _solver, T_sal_K = _correr_colector(
                    proyecto,
                    T_amb_K=T_amb_i,
                    I_g_W_m2=float(I_g_POA_W_m2_serie[i]),
                    v_viento_ms=float(v_viento_ms_serie[i]),
                    T_entrada_K=T_amb_i,
                    P_amb_Pa=P_amb_Pa,
                )
                T_sal[i] = T_sal_K
            except Exception:
                # Régimen patológico (fsolve no converge, Re fuera de rango...):
                # sin aporte del colector en esa hora. Se reporta vía n_fallas.
                T_sal[i] = T_amb_i
                n_fallas += 1
    finally:
        u.velocidad_diseno_ms = v_diseno_original
    return np.maximum(T_sal, T_amb_arr), n_fallas


def armar_forzantes_ventana(
    proyecto,
    clima_datos_df,
    *,
    P_Pa: float = 101325.0,
) -> tuple[ForzantesAire, float, list[str], dict[str, float]]:
    """Arma las forzantes de cámara sobre la ventana desde clima real horario.

    Encadena, hora a hora sobre el lapso ``clima_datos_df`` (slice horario con
    columnas COLUMNAS_SI e índice DatetimeIndex):
        1. POA sobre el plano del colector (transposición Liu-Jordan, pvlib).
        2. Colector forzado → T_salida_colector(t).
        3. Caño maestro (si presente): ΔT térmica (pérdida/aporte solar) → T(t).
        4. Auxiliar en serie (si presente): ΔT(t) según su calendario de
           arranque (mañana/tarde) → T_entrada de cámara. Acumula leña.

    Args:
        proyecto: Proyecto GRAN_ESCALA con colector y emplazamiento.
        clima_datos_df: DataFrame horario (COLUMNAS_SI) del lapso [inicio, fin].
        P_Pa: Presión representativa [Pa].

    Returns:
        (forzantes, lena_consumida_kg, advertencias, diagnosticos). El último
        es un dict con los diagnósticos del caño maestro para los exports
        (``cano_delta_T_media_K``, ``cano_delta_T_minima_K``,
        ``cano_delta_P_Pa``) — vacío si no hay caño maestro.
    """
    from calculos.clima_calc import calcular_POA_horizonte
    from calculos.psicrometria import humedad_absoluta
    from calculos.radiacion_camara import series_radiacion_camara
    from core.auxiliar import ModoOperacionAuxiliar

    advertencias: list[str] = []
    df = clima_datos_df
    n = len(df)

    T_amb = np.asarray(df["T_amb_K"].to_numpy(), dtype=float)
    v_viento = np.asarray(df["WS_ms"].to_numpy(), dtype=float)
    GHI = np.asarray(df["GHI_Wm2"].to_numpy(), dtype=float)
    HR = np.asarray(df["HR"].to_numpy(), dtype=float)

    # Irradiancia equivalente al producto sobre las caras translúcidas de la
    # cámara (fase 2: orientación propia, independiente del banco de
    # colectores). Fallback a GHI horizontal (sin aporte al aire) si falla.
    try:
        I_eq_serie, Q_rad_aire_serie = series_radiacion_camara(
            df, proyecto.emplazamiento, proyecto.camara
        )
        I_eq_prod = np.asarray(I_eq_serie, dtype=float)
        Q_rad_aire = np.asarray(Q_rad_aire_serie, dtype=float)
    except Exception as exc:
        advertencias.append(
            f"ADV_VENTANA_IEQ_NO_DISPONIBLE: {exc}. Se usa GHI como irradiancia "
            "equivalente de la cámara, sin aporte radiativo al aire."
        )
        I_eq_prod = GHI.copy()
        Q_rad_aire = np.zeros(n)

    # POA sobre el plano del colector.
    try:
        POA = np.asarray(calcular_POA_horizonte(df, proyecto.emplazamiento).to_numpy(), dtype=float)
    except Exception as exc:
        advertencias.append(f"ADV_VENTANA_POA_NO_DISPONIBLE: {exc}. Se usa GHI como POA.")
        POA = GHI.copy()

    # Caudal del sistema: lo fija el ventilador y circula por banco, caño
    # maestro y cámara por igual (S41 — caudal único).
    m_dot_sistema = (
        float(proyecto.camara.flujo.caudal_masico_kg_s) if proyecto.camara is not None else None
    )

    # Colector forzado hora a hora, a la velocidad que impone el caudal del
    # sistema (no a la velocidad de diseño nominal del módulo).
    T_sal_col, n_fallas_col = _correr_colector_horizonte_forzado(
        proyecto,
        T_amb_K_serie=T_amb,
        v_viento_ms_serie=v_viento,
        I_g_POA_W_m2_serie=POA,
        P_amb_Pa=P_Pa,
        m_dot_sistema_kg_s=m_dot_sistema,
    )
    if n_fallas_col > 0:
        advertencias.append(
            f"ADV_VENTANA_COLECTOR_FALLO_HORAS: el solver del colector falló en "
            f"{n_fallas_col} de {n} horas (se asumió T_salida = T_amb, sin aporte "
            "solar en esas horas). Revisá la configuración del colector."
        )

    # Coherencia de caudales banco ↔ sistema (S41): si el caudal de diseño del
    # banco difiere mucho del que mueve el ventilador, el punto de operación
    # real del colector se aleja del nominal — avisar para que el usuario
    # redimensione banco o ventilador.
    if proyecto.colector is not None and m_dot_sistema is not None and m_dot_sistema > 0:
        from calculos.motor_calc import densidad_aire as _densidad_aire

        _u = proyecto.colector.unidad
        _b = proyecto.colector.banco
        _rho_ref = _densidad_aire(float(np.mean(T_amb)), P_Pa)
        m_banco_diseno = (
            _b.n_paralelo * _u.velocidad_diseno_ms * _u.ancho_m * _u.espaciado_m * _rho_ref
        )
        if m_banco_diseno > 0:
            _ratio = m_banco_diseno / m_dot_sistema
            if _ratio > 1.5 or _ratio < (1.0 / 1.5):
                _v_real = _velocidad_modulo_desde_caudal(
                    proyecto.colector, m_dot_sistema, float(np.mean(T_amb)), P_Pa
                )
                advertencias.append(
                    f"ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE: el caudal de diseño del "
                    f"banco ({m_banco_diseno:.3f} kg/s = {_b.n_paralelo} ramas × "
                    f"{_u.velocidad_diseno_ms:.2f} m/s) difiere {_ratio:.1f}× del "
                    f"caudal del sistema ({m_dot_sistema:.3f} kg/s). El colector se "
                    f"evaluó al caudal del sistema (v ≈ {_v_real:.2f} m/s por rama). "
                    "Ajustá el caudal del ventilador o el tamaño del banco."
                )

        # Velocidad media del aire en la cámara: bajo ~0.1 m/s el secado queda
        # limitado por transporte (h_conv y K_m minúsculos).
        _geo = proyecto.camara.geometria
        _A_frontal = float(_geo.ancho_m) * float(_geo.alto_m)
        if _A_frontal > 0:
            _v_camara = m_dot_sistema / (_rho_ref * _A_frontal)
            if _v_camara < 0.10:
                advertencias.append(
                    f"ADV_VENTANA_VELOCIDAD_CAMARA_BAJA: velocidad media del aire en "
                    f"la cámara ≈ {_v_camara * 100:.1f} cm/s (sección frontal "
                    f"{_A_frontal:.2f} m²). Bajo ~10 cm/s los coeficientes de "
                    "transporte se desploman y el secado se hace muy lento. "
                    "Aumentá el caudal o reducí la sección de la cámara."
                )

    # Caño maestro: ΔT térmica entre la salida del banco y la cámara.
    diagnosticos: dict[str, float] = {}
    cano = getattr(getattr(proyecto.colector, "banco", None), "cano_maestro", None)
    if cano is not None:
        from calculos.cano_maestro_calc import delta_T_cano_maestro

        m_dot = proyecto.camara.flujo.caudal_masico_kg_s
        dT_cano = np.array(
            [
                delta_T_cano_maestro(
                    cano,
                    T_aire_K=float(T_sal_col[i]),
                    T_amb_K=float(T_amb[i]),
                    I_g_W_m2=float(GHI[i]),
                    m_dot_as_kg_s=m_dot,
                    v_viento_ms=float(v_viento[i]),
                    P_Pa=P_Pa,
                )
                for i in range(n)
            ]
        )
        T_post_cano = T_sal_col + dT_cano
        # Diagnósticos para los exports: ΔT media/peor y ΔP al caudal del
        # sistema (la serie dT_cano no se persiste; estos agregados sí).
        diagnosticos["cano_delta_T_media_K"] = float(np.mean(dT_cano))
        diagnosticos["cano_delta_T_minima_K"] = float(np.min(dT_cano))
        try:
            from calculos.cano_maestro_calc import estimar_delta_P_cano_maestro
            from calculos.motor_calc import densidad_aire

            T_media_K = float(np.mean(T_sal_col))
            Q_vol_m3_s = m_dot / densidad_aire(T_media_K, P_Pa)
            diagnosticos["cano_delta_P_Pa"] = float(
                estimar_delta_P_cano_maestro(cano, Q_vol_m3_s, T_K=T_media_K, P_Pa=P_Pa)["total"]
            )
        except Exception as exc:
            advertencias.append(f"ADV_VENTANA_CANO_DP: no se pudo estimar ΔP del caño ({exc}).")
    else:
        T_post_cano = T_sal_col

    omega_amb = np.array([humedad_absoluta(float(HR[i]), float(T_amb[i]), P_Pa) for i in range(n)])
    # Paso temporal real del clima (fase 1b: puede ser sub-horario). Se deriva
    # del índice en vez de asumir 3600 s; fallback a horario si n == 1.
    if n > 1:
        dt_s = float((df.index[1] - df.index[0]).total_seconds())
    else:
        dt_s = 3600.0
    t_s = np.arange(n, dtype=float) * dt_s

    # Auxiliar en serie (con calendario de arranque) → ΔT y leña.
    T_ent = T_post_cano.copy()
    lena_kg = 0.0
    aux = proyecto.auxiliar
    if aux is not None and aux.modo_operacion == ModoOperacionAuxiliar.SERIE_POSCOLECTOR:
        try:
            hora_offset = _hora_offset_local(df, proyecto.emplazamiento)
            aux_tr = calcular_auxiliar_transitorio(
                aux,
                T_entrada_K_serie=T_post_cano,
                t_s=t_s,
                caudal_masico_kg_s=proyecto.camara.flujo.caudal_masico_kg_s,
                I_g_W_m2_serie=POA,
                hora_offset_h=hora_offset,
            )
            T_ent = T_post_cano + aux_tr.delta_T_K
            lena_kg = aux_tr.lena_consumida_kg
            advertencias.extend(aux_tr.advertencias_unicas)
        except Exception as exc:
            advertencias.append(f"ADV_VENTANA_AUXILIAR: {exc}")

    forzantes = ForzantesAire(
        t_s=t_s,
        T_ent_K=T_ent,
        omega_ent=omega_amb,
        m_dot_aire_seco_kg_s=np.full(n, proyecto.camara.flujo.caudal_masico_kg_s),
        T_amb_K=T_amb,
        v_viento_ms=v_viento,
        I_g_W_m2=I_eq_prod,
        I_g_POA_W_m2=POA,
        # Ancla absoluta del lapso: sin ella las descargas del túnel no se pueden
        # fechar para contrastarlas contra muestreos de campo (mejora 38, fase 4).
        t0_utc=df.index[0] if len(df.index) else None,
        Q_rad_aire_W=Q_rad_aire,
    )
    return forzantes, lena_kg, advertencias, diagnosticos


def _hora_offset_local(clima_datos_df, emplazamiento) -> float:
    """Hora del día (local) del primer registro de la ventana [h], para alinear
    el calendario de arranque del auxiliar. Convierte el índice UTC a la zona
    horaria del emplazamiento si es posible."""
    try:
        idx0 = clima_datos_df.index[0]
        if getattr(idx0, "tzinfo", None) is not None and emplazamiento is not None:
            idx0 = idx0.tz_convert(emplazamiento.zona_horaria)
        return float(idx0.hour) + float(idx0.minute) / 60.0
    except Exception:
        return 0.0


def calcular_todo_ventana(
    proyecto,
    clima_datos_df,
    *,
    P_Pa: Optional[float] = None,
):
    """Pipeline de ventana de producción (gran escala).

    Arma las forzantes desde clima real horario sobre el lapso y delega en
    ``simulacion_ventana.simular_ventana`` para acumular la producción según el
    subtipo (BATCH / SEMICONTINUO). Es el punto de entrada que consume P7.

    Args:
        proyecto: Proyecto GRAN_ESCALA en modo VENTANA.
        clima_datos_df: DataFrame horario (COLUMNAS_SI) del lapso [inicio, fin].
        P_Pa: Presión representativa [Pa]. None → se deriva del emplazamiento.

    Returns:
        ResultadoVentana con producción, tasa de régimen, leña y diagnósticos.
    """
    from calculos.simulacion_ventana import ResultadoVentana, simular_ventana

    if P_Pa is None:
        P_Pa, _origen = presion_representativa_proyecto(proyecto)

    errores = verificar_coherencia_proyecto(proyecto)
    if errores:
        return ResultadoVentana(
            subtipo=proyecto.configuracion.subtipo_gran_escala.value,
            horizonte_s=0.0,
            status="error",
            advertencias=errores,
        )

    forzantes, lena_kg, adv, diag = armar_forzantes_ventana(proyecto, clima_datos_df, P_Pa=P_Pa)
    res = simular_ventana(proyecto, forzantes_base=forzantes, P_Pa=P_Pa)
    # La leña del auxiliar se computa al armar las forzantes (calendario de arranque).
    res.lena_consumida_kg = lena_kg
    res.advertencias = list(adv) + list(res.advertencias)
    # Diagnósticos del caño maestro (para los exports).
    res.cano_delta_T_media_K = diag.get("cano_delta_T_media_K")
    res.cano_delta_T_minima_K = diag.get("cano_delta_T_minima_K")
    res.cano_delta_P_Pa = diag.get("cano_delta_P_Pa")
    return res
