"""
Dataclasses de resultados del proyecto de prediseño.

`Resultados` es el espejo de salida del objeto `Proyecto`. Almacena
exclusivamente outputs calculados por los solvers; las entradas viven
en las secciones de configuración (Emplazamiento, Colector, Camara, etc.).

Todos los sub-bloques heredan de `BloqueResultados` (core/advertencias.py),
que implementa el mecanismo de invalidación por hash de entradas.

Naming: las clases se llaman ResultadosXxx para consistencia con tanda5.
En los módulos de cálculo (calculos/) se usan nombres distintos para los
outputs del solver puntual (ej. ResultadosColectorTipo1, ResultadosCamara
en camara_calc.py), sin colisión porque los prefijos de módulo los distinguen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.advertencias import BloqueResultados


# ---------------------------------------------------------------------------
# Constantes físicas para el balance global
# ---------------------------------------------------------------------------

LV_AGUA_MJ_KG: float = 2.450    # calor latente de vaporización a ~20°C [MJ/kg]


# ---------------------------------------------------------------------------
# ResultadosClima
# ---------------------------------------------------------------------------


@dataclass
class ResultadosClima(BloqueResultados):
    """Post-proceso de los datos NASA POWER del emplazamiento.

    No tiene solver propio — recalcula estadísticos del período sobre los
    datos ya descargados en core.clima.Clima.
    """

    T_ambiente_media_K: Optional[float] = None
    T_ambiente_max_K: Optional[float] = None
    T_ambiente_min_K: Optional[float] = None
    irradiancia_GHI_media_W_m2: Optional[float] = None
    energia_GHI_total_MJ_m2: Optional[float] = None
    horas_sol_efectivas: Optional[float] = None   # horas con GHI > 50 W/m²
    velocidad_viento_media_ms: Optional[float] = None
    HR_media_fraccion: Optional[float] = None
    fraccion_datos_validos: Optional[float] = None
    n_horas_faltantes: Optional[int] = None


# ---------------------------------------------------------------------------
# ResultadosColector
# ---------------------------------------------------------------------------


@dataclass
class ResultadosColector(BloqueResultados):
    """Resultados del solver del colector bajo condiciones de diseño."""

    # Condiciones de cálculo usadas
    T_amb_calc_K: Optional[float] = None
    I_g_calc_W_m2: Optional[float] = None
    v_viento_calc_ms: Optional[float] = None
    T_entrada_calc_K: Optional[float] = None

    # Outputs del solver
    T_salida_K: Optional[float] = None
    delta_T_K: Optional[float] = None
    Q_util_W: Optional[float] = None
    Q_incidente_W: Optional[float] = None
    eta_termica: Optional[float] = None
    h_int_W_m2K: Optional[float] = None
    Re_medio: Optional[float] = None
    regimen_flujo: Optional[str] = None

    # Globales estimados para la sesión completa
    Q_util_total_MJ: Optional[float] = None    # Q_util × t_secado
    area_total_m2: Optional[float] = None


# ---------------------------------------------------------------------------
# ResultadosAuxiliar  (bloque de resultados — distinto de calculos.auxiliar_calc.ResultadosAuxiliar)
# ---------------------------------------------------------------------------


@dataclass
class ResultadosAuxiliar(BloqueResultados):
    """Resultados del sistema de calentamiento auxiliar."""

    T_entrada_K: Optional[float] = None
    T_salida_K: Optional[float] = None
    delta_T_K: Optional[float] = None
    Q_efectivo_W: Optional[float] = None
    fraccion_activa: Optional[float] = None
    consumo_biomasa_kg_h: Optional[float] = None
    consumo_electrico_W: Optional[float] = None

    # Totales para la sesión completa
    energia_aportada_MJ: Optional[float] = None
    consumo_biomasa_total_kg: Optional[float] = None
    energia_electrica_total_kWh: Optional[float] = None


# ---------------------------------------------------------------------------
# ResultadosCamara  (bloque de resultados — distinto de calculos.camara_calc.ResultadosCamara)
# ---------------------------------------------------------------------------


@dataclass
class ResultadosCamara(BloqueResultados):
    """Resultados del modelo de capa fina para la cámara de secado."""

    T_operacion_K: Optional[float] = None
    HR_operacion: Optional[float] = None

    X_eq_kg_kg: Optional[float] = None
    t_secado_s: Optional[float] = None
    t_secado_h: Optional[float] = None
    X_final_kg_kg: Optional[float] = None
    MR_final: Optional[float] = None
    masa_agua_evaporada_kg: Optional[float] = None
    objetivo_alcanzado: Optional[bool] = None
    fuente_X_eq: Optional[str] = None

    # Inocuidad (solo carnes)
    a_w_final: Optional[float] = None
    inocuidad_ok: Optional[bool] = None


# ---------------------------------------------------------------------------
# ResultadosMotor
# ---------------------------------------------------------------------------


@dataclass
class ResultadosMotor(BloqueResultados):
    """Resultados del dimensionamiento del motor."""

    caudal_volumetrico_m3_s: Optional[float] = None
    perdida_carga_total_Pa: Optional[float] = None
    potencia_hidraulica_W: Optional[float] = None
    potencia_eje_W: Optional[float] = None
    potencia_electrica_W: Optional[float] = None
    potencia_a_instalar_W: Optional[float] = None
    corriente_nominal_A: Optional[float] = None
    eficiencia_sistema: Optional[float] = None    # η_vent × η_motor

    # Energía del motor para la sesión completa
    energia_electrica_motor_kWh: Optional[float] = None


# ---------------------------------------------------------------------------
# ResultadosGlobal
# ---------------------------------------------------------------------------


@dataclass
class ResultadosGlobal(BloqueResultados):
    """Balance energético global y resumen del ciclo de secado.

    Se calcula cuando todos los bloques upstream están vigentes.
    """

    # Balance energético
    energia_solar_util_MJ: Optional[float] = None     # Q_util_col × t_secado
    energia_auxiliar_MJ: Optional[float] = None       # Q_aux × t_secado (0 si None)
    energia_motor_MJ: Optional[float] = None          # P_elec_motor × t_secado
    energia_total_MJ: Optional[float] = None          # solar + auxiliar + motor
    energia_secado_MJ: Optional[float] = None         # masa_agua × Lv (calor latente)
    fraccion_solar: Optional[float] = None            # solar / (solar + auxiliar)

    # Indicadores de desempeño
    COP_secado: Optional[float] = None
    # COP = masa_agua_kg × Lv_MJ_kg / energia_total_MJ
    # Valores típicos: 0.10–0.35 para secadores solares

    eficiencia_global: Optional[float] = None
    # η = energia_secado / energia_solar_disponible (POA × área × t_secado)

    # Resumen del ciclo
    tiempo_secado_h: Optional[float] = None
    masa_producto_fresco_kg: Optional[float] = None
    masa_producto_seco_kg: Optional[float] = None
    masa_agua_evaporada_kg: Optional[float] = None
    rendimiento_masa: Optional[float] = None          # kg_seco / kg_fresco

    # Resumen del sistema
    area_colectores_m2: Optional[float] = None
    n_bandejas: Optional[int] = None
    potencia_motor_W: Optional[float] = None
    consumo_electrico_total_kWh: Optional[float] = None

    # Errores de coherencia cruzada detectados al integrar
    errores_cruzados: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resultados (contenedor raíz)
# ---------------------------------------------------------------------------


@dataclass
class Resultados:
    """Contenedor de todos los bloques de resultados del proyecto.

    Almacenado en Proyecto.resultados. Inicialmente todos los bloques
    están en estado _stale=True hasta que se ejecuta el cálculo.
    """

    clima: ResultadosClima = field(default_factory=ResultadosClima)
    colector: ResultadosColector = field(default_factory=ResultadosColector)
    auxiliar: ResultadosAuxiliar = field(default_factory=ResultadosAuxiliar)
    camara: ResultadosCamara = field(default_factory=ResultadosCamara)
    motor: ResultadosMotor = field(default_factory=ResultadosMotor)
    global_: ResultadosGlobal = field(default_factory=ResultadosGlobal)
