"""Operación anual de la cámara de secado (cascada A + B).

Implementa el método de evaluación anual del prediseñador en dos pasadas:

- **Opción A** (analítica): modelo lineal del colector ``T_sal = T_amb +
  η·POA·A_col / (ṁ·c_p)`` que alimenta forzantes mensuales sintéticas.
- **Opción B** (termodinámica): el motor ``camara_termodinamica.simular_secado``
  corre con el día típico del mes sobre un horizonte de varios días,
  obteniendo m_evap y t_secado del batch representativo.

Para cada mes se construye el "día típico" promediando horariamente los
registros NASA POWER del mes, se replica sobre el horizonte del batch, y
se obtienen las 4 eficiencias de Augustus Leon (RSER 2002). Los resultados
mensuales se escalan a operación anual con ``batches_por_mes``.

Referencias del método:
    Augustus Leon, M., Kumar, S., Bhattacharya, S.C. (2002).
    "A comprehensive procedure for performance evaluation of solar food dryers".
    Renewable and Sustainable Energy Reviews 6(4), pp. 367-393.

    Forson, F.K., Nazha, M.A.A., Akuffo, F.O., Rajakaruna, H. (2007).
    "Design of mixed-mode natural convection solar crop dryers".
    Renewable Energy 32(14), pp. 2306-2319.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from calculos.clima_calc import calcular_POA_horizonte, dia_tipo_mensual
from calculos.eficiencias_camara import (
    eta_drying,
    eta_pickup,
    eta_termica_camara,
    eta_total_sistema,
)
from calculos.psicrometria import humedad_absoluta, omega_saturacion

if TYPE_CHECKING:
    from core.proyecto import Proyecto


# Calor específico del aire seco a ~50 °C [J/(kg·K)]
_CP_AIRE_J_KGK: float = 1007.0

# Eficiencia térmica de colector por defecto cuando el proyecto no tiene un
# cálculo de P3 disponible. Valor típico para placa plana cubierta operando
# a ΔT ~ 20–30 K sobre T_amb.
_ETA_COLECTOR_DEFAULT: float = 0.5


# ---------------------------------------------------------------------------
# Dataclasses de resultados
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PuntoMensualCamara:
    """Resultado del batch representativo de un mes."""

    mes: int  # 1..12
    t_secado_h: float  # horas hasta humedad objetivo (o tope del horizonte)
    convergio: bool  # True si alcanzó X_objetivo dentro del horizonte
    m_evap_kg_por_batch: float
    eta_drying: float
    eta_pickup: float
    eta_termica: float
    eta_total: float
    E_solar_batch_MJ: float  # ∫ POA dt · A_col, sobre el horizonte del batch
    E_auxiliar_batch_MJ: float  # estimación (0 si no hay auxiliar configurado)
    n_batches: int  # = config.batches_por_mes
    kg_secados_mes: float  # = m_evap_kg_por_batch * n_batches
    advertencias: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadosAnualCamara:
    """Operación anual: 12 puntos mensuales + agregados anuales."""

    puntos_mensuales: list[PuntoMensualCamara]
    # Agregados anuales (promedios ponderados por kg_secados_mes donde corresponda)
    kg_secados_anual: float
    eta_drying_anual_media: float
    eta_pickup_anual_media: float
    eta_termica_anual_media: float
    eta_total_anual_media: float
    E_solar_anual_MJ: float
    E_auxiliar_anual_MJ: float
    t_secado_promedio_h: float
    advertencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Modelo lineal del colector (Opción A — alimenta forzantes para B)
# ---------------------------------------------------------------------------


def _T_salida_colector_lineal(
    POA_W_m2_serie: np.ndarray,
    T_amb_K_serie: np.ndarray,
    A_col_m2: float,
    eta_colector: float,
    m_dot_kg_s: float,
) -> np.ndarray:
    """Estima T_salida_colector(t) con modelo lineal de prediseño.

        T_sal(t) = T_amb(t) + η_col · POA(t) · A_col / (ṁ · c_p)

    Es una aproximación de la Opción A — pierde la inercia térmica del
    colector y la dependencia de η con ΔT, pero alcanza para alimentar el
    motor TD mes a mes sin re-correr el solver del colector.

    Args:
        POA_W_m2_serie: Irradiancia POA por hora [W/m²].
        T_amb_K_serie: T ambiente por hora [K].
        A_col_m2: Área del colector [m²].
        eta_colector: Eficiencia térmica media del colector [adim].
        m_dot_kg_s: Caudal másico de aire [kg/s].

    Returns:
        T_salida_colector_K por hora [K].
    """
    if m_dot_kg_s <= 0 or A_col_m2 <= 0:
        return np.asarray(T_amb_K_serie, dtype=float).copy()
    Q_util = np.clip(np.asarray(eta_colector) * POA_W_m2_serie * A_col_m2, 0.0, None)
    dT = Q_util / (m_dot_kg_s * _CP_AIRE_J_KGK)
    return np.asarray(T_amb_K_serie, dtype=float) + dT


def _area_colector_m2(proyecto: "Proyecto") -> float:
    """Área total del banco de colectores [m²]. 0 si no hay colector."""
    if proyecto.colector is None:
        return 0.0
    u = proyecto.colector.unidad
    b = proyecto.colector.banco
    return float(u.largo_m * u.ancho_m * b.n_serie * b.n_paralelo)


# ---------------------------------------------------------------------------
# Punto mensual — corre el motor TD para el día típico del mes
# ---------------------------------------------------------------------------


def _calcular_punto_mensual(
    proyecto: "Proyecto",
    mes: int,
    A_col_m2: float,
    eta_colector: float,
) -> PuntoMensualCamara:
    """Para un mes: arma forzantes mensuales y corre el motor TD vía dispatcher."""
    from calculos.balance_global import armar_forzantes_aire, presion_representativa_proyecto
    from calculos.camara_calc import calcular_camara
    from calculos.radiacion_camara import series_radiacion_camara

    cfg = proyecto.camara.operacion_anual
    cam = proyecto.camara
    flujo = cam.flujo
    m_dot = float(flujo.caudal_masico_kg_s)
    tz_local = proyecto.emplazamiento.zona_horaria if proyecto.emplazamiento is not None else "UTC"

    # 1. Día típico mensual del clima NASA POWER
    df_dia = dia_tipo_mensual(proyecto.clima.datos, mes, tz_local=tz_local)

    # 2. POA del día tipo (sobre plano del colector)
    POA_dia = (
        calcular_POA_horizonte(df_dia, proyecto.emplazamiento).to_numpy()
        if proyecto.colector is not None and proyecto.emplazamiento is not None
        else df_dia["GHI_Wm2"].to_numpy()
    )

    T_amb_dia = df_dia["T_amb_K"].to_numpy()
    WS_dia = df_dia["WS_ms"].to_numpy()
    HR_dia = df_dia["HR"].to_numpy() / 100.0  # NASA da en %

    # Irradiancia equivalente al producto sobre las caras translúcidas de la
    # cámara (fase 2: orientación propia, independiente del banco de
    # colectores). Fallback a GHI horizontal (sin aporte al aire) si falla.
    try:
        I_eq_serie, Q_rad_aire_dia = series_radiacion_camara(df_dia, proyecto.emplazamiento, cam)
        I_eq_dia = np.asarray(I_eq_serie, dtype=float)
        Q_rad_aire_dia = np.asarray(Q_rad_aire_dia, dtype=float)
    except Exception:
        I_eq_dia = df_dia["GHI_Wm2"].to_numpy()
        Q_rad_aire_dia = np.zeros(len(df_dia))

    # 3. T_salida del colector con modelo lineal
    T_sal_col_dia = _T_salida_colector_lineal(
        POA_dia,
        T_amb_dia,
        A_col_m2,
        eta_colector,
        m_dot,
    )

    # 4. ω ambiente desde HR y T_amb. La presión corregida por altitud se
    #    obtiene del helper híbrido (media NASA anual o ISA del emplazamiento).
    P_amb, _ = presion_representativa_proyecto(proyecto)
    omega_amb_dia = np.array([humedad_absoluta(HR_dia[h], T_amb_dia[h], P_amb) for h in range(24)])

    # 5. Replicar el día N veces para llenar el horizonte del batch
    n_dias = max(1, int(np.ceil(cfg.horizonte_horas_batch / 24)))
    forzantes = armar_forzantes_aire(
        modo="multi_dia",
        n_dias=n_dias,
        T_salida_colector_K=T_sal_col_dia,
        omega_ambiente=omega_amb_dia,
        m_dot_aire_seco_kg_s=m_dot,
        v_viento_ms=WS_dia,
        T_amb_K=T_amb_dia,
        I_g_W_m2=I_eq_dia,
        I_g_POA_W_m2=POA_dia,
        Q_rad_aire_W=Q_rad_aire_dia,
    )

    # 6. Correr motor TD vía dispatcher. calcular_camara arma todos los
    # parámetros del motor desde la dataclass Camara (A_prod, A_cuerpo,
    # h_conv, K_m, k_aisl, esp_cam, P_Pa, aw_func, etc.). T_op_K / HR_op
    # son referencia de inicialización; el motor usa las forzantes hora a
    # hora.
    T_op_K = float(T_sal_col_dia.mean())
    HR_op = float(HR_dia.mean())
    T_amb_ref_K = float(T_amb_dia.mean())
    t_max_s = float(cfg.horizonte_horas_batch) * 3600.0

    res = calcular_camara(
        cam,
        T_op_K,
        HR_op,
        T_amb_K=T_amb_ref_K,
        P_Pa=P_amb,
        t_max_s=t_max_s,
        forzantes_aire=forzantes,
    )

    # 7. Métricas del batch
    t_secado_s = res.t_secado_s if res.t_secado_s is not None else (n_dias * 86400.0)
    t_secado_h = t_secado_s / 3600.0
    m_evap = float(res.masa_evaporada_total_kg)

    # Energía solar en el horizonte = ∫ POA · A_col dt (sumamos sobre las horas)
    horas_op = min(int(t_secado_h), n_dias * 24)
    # Replicar POA n_dias veces y truncar a horas_op
    POA_horizonte = np.tile(POA_dia, n_dias)[:horas_op] if horas_op > 0 else np.array([0.0])
    E_solar_J = float(POA_horizonte.sum() * A_col_m2 * 3600.0)
    E_solar_MJ = E_solar_J / 1e6

    # Q_aire entregado (sensible aire) = ∫ ṁ·cp·(T_sal_col − T_amb) dt
    T_sal_col_horizonte = (
        np.tile(T_sal_col_dia, n_dias)[:horas_op] if horas_op > 0 else np.array([0.0])
    )
    T_amb_horizonte = np.tile(T_amb_dia, n_dias)[:horas_op] if horas_op > 0 else np.array([0.0])
    Q_aire_J = float(
        m_dot * _CP_AIRE_J_KGK * np.sum(T_sal_col_horizonte - T_amb_horizonte) * 3600.0
    )

    # Auxiliar — en v0 no se modela en el batch anual; se podría estimar después
    E_aux_J = 0.0

    # ω salida y ω saturación a T_salida (último valor estable del solver)
    omega_sal = (
        float(res.omega_flujo_kg_kg[-1])
        if len(res.omega_flujo_kg_kg) > 0
        else float(omega_amb_dia.mean())
    )
    T_sal_cam = float(res.T_flujo_K[-1]) if len(res.T_flujo_K) > 0 else float(T_sal_col_dia.mean())
    omega_sat_sal = omega_saturacion(T_sal_cam, P_amb)

    # 8. Eficiencias Augustus Leon
    T_evap = float(T_sal_col_dia.mean())  # T representativa para h_fg
    eta_d = eta_drying(m_evap, E_solar_J / A_col_m2 if A_col_m2 > 0 else 0.0, A_col_m2, T_evap)
    eta_p = eta_pickup(float(omega_amb_dia.mean()), omega_sal, omega_sat_sal)
    eta_t = eta_termica_camara(Q_aire_J, E_solar_J / A_col_m2 if A_col_m2 > 0 else 0.0, A_col_m2)
    eta_tot = eta_total_sistema(m_evap, E_solar_J, E_aux_J, T_evap)

    advs = list(res.advertencias)
    convergio = res.t_secado_s is not None

    return PuntoMensualCamara(
        mes=mes,
        t_secado_h=t_secado_h,
        convergio=convergio,
        m_evap_kg_por_batch=m_evap,
        eta_drying=eta_d,
        eta_pickup=eta_p,
        eta_termica=eta_t,
        eta_total=eta_tot,
        E_solar_batch_MJ=E_solar_MJ,
        E_auxiliar_batch_MJ=E_aux_J / 1e6,
        n_batches=cfg.batches_por_mes,
        kg_secados_mes=m_evap * cfg.batches_por_mes,
        advertencias=advs,
    )


# ---------------------------------------------------------------------------
# Orquestador anual
# ---------------------------------------------------------------------------


def calcular_operacion_anual_camara(
    proyecto: "Proyecto",
    *,
    eta_colector: float | None = None,
) -> ResultadosAnualCamara:
    """Ejecuta el motor termodinámico mes a mes y agrega resultados anuales.

    Para cada mes (1..12):
        1. Construye día tipo mensual desde NASA POWER.
        2. Estima T_salida_colector con modelo lineal (Opción A).
        3. Replica el día tipo y corre simular_secado del motor TD.
        4. Calcula las 4 eficiencias Augustus Leon.
        5. Escala a operación mensual con batches_por_mes.

    Args:
        proyecto: Proyecto con clima, colector, cámara y configuración
            anual completa.
        eta_colector: Eficiencia media del colector [adim] para el modelo
            lineal. Si ``None``, usa el default 0.5 (placa plana cubierta).

    Returns:
        ResultadosAnualCamara con 12 puntos mensuales + agregados anuales.

    Raises:
        ValueError: Si el proyecto no tiene clima, cámara, colector o
            configuración anual.
    """
    if proyecto.clima is None or proyecto.clima.datos is None:
        raise ValueError(
            "ANUAL_SIN_CLIMA: la operación anual requiere clima NASA POWER "
            "cargado en P2 (proyecto.clima.datos)."
        )
    if proyecto.camara is None:
        raise ValueError("ANUAL_SIN_CAMARA: requiere proyecto.camara configurada.")
    if proyecto.camara.operacion_anual is None:
        raise ValueError("ANUAL_SIN_CONFIG: requiere proyecto.camara.operacion_anual configurado.")
    if proyecto.camara.modo_calculo != "termodinamico":
        raise ValueError(
            "ANUAL_REQUIERE_TD: la cascada A+B usa el motor termodinámico. "
            "Configurar camara.modo_calculo='termodinamico'."
        )

    A_col = _area_colector_m2(proyecto)
    eta_col = float(eta_colector) if eta_colector is not None else _ETA_COLECTOR_DEFAULT

    puntos: list[PuntoMensualCamara] = []
    advertencias_globales: list[str] = []

    for mes in range(1, 13):
        try:
            punto = _calcular_punto_mensual(proyecto, mes, A_col, eta_col)
            puntos.append(punto)
        except Exception as exc:
            advertencias_globales.append(f"ANUAL_MES_{mes:02d}_FALLO: {exc}")
            puntos.append(
                PuntoMensualCamara(
                    mes=mes,
                    t_secado_h=0.0,
                    convergio=False,
                    m_evap_kg_por_batch=0.0,
                    eta_drying=0.0,
                    eta_pickup=0.0,
                    eta_termica=0.0,
                    eta_total=0.0,
                    E_solar_batch_MJ=0.0,
                    E_auxiliar_batch_MJ=0.0,
                    n_batches=0,
                    kg_secados_mes=0.0,
                    advertencias=[f"MES_FALLO: {exc}"],
                )
            )

    # Agregados anuales — promedios ponderados por kg_secados_mes
    kg_anual = sum(p.kg_secados_mes for p in puntos)
    E_solar_anual = sum(p.E_solar_batch_MJ * p.n_batches for p in puntos)
    E_aux_anual = sum(p.E_auxiliar_batch_MJ * p.n_batches for p in puntos)
    t_promedio = (
        float(np.mean([p.t_secado_h for p in puntos if p.convergio]))
        if any(p.convergio for p in puntos)
        else 0.0
    )

    def _ponderada(getter):
        if kg_anual <= 0:
            return 0.0
        return sum(getter(p) * p.kg_secados_mes for p in puntos) / kg_anual

    return ResultadosAnualCamara(
        puntos_mensuales=puntos,
        kg_secados_anual=kg_anual,
        eta_drying_anual_media=_ponderada(lambda p: p.eta_drying),
        eta_pickup_anual_media=_ponderada(lambda p: p.eta_pickup),
        eta_termica_anual_media=_ponderada(lambda p: p.eta_termica),
        eta_total_anual_media=_ponderada(lambda p: p.eta_total),
        E_solar_anual_MJ=E_solar_anual,
        E_auxiliar_anual_MJ=E_aux_anual,
        t_secado_promedio_h=t_promedio,
        advertencias=advertencias_globales,
    )
