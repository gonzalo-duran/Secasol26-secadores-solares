"""
Dataclass del motor / ventilador del sistema de convección forzada.

Motor se almacena en Proyecto.motor. Es None para tipologías de convección
natural (proyecto.motor = None en ese caso — no instanciar Motor).

Las potencias se calculan en __post_init__ a partir de la pérdida de carga del
sistema y las eficiencias del ventilador y el motor eléctrico:

    P_hidráulica = Q_vol × ΔP_total
    P_eje        = P_hid / η_ventilador
    P_eléctrica  = P_eje / η_motor
    P_a_instalar = P_elec × factor_servicio

La pérdida de carga total puede ingresarse directamente o calcularse a partir
de las pérdidas en colector, cámara y ductos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.advertencias import Advertencia, Severidad

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_POTENCIA_BAJA_W: float = 30.0      # advertencia: motor posiblemente innecesario
_POTENCIA_ALTA_W: float = 5000.0    # advertencia: revisar pérdidas de carga
_V_VIENTO_BAJA_MS: float = 2.0      # advertencia: extractor eólico poco efectivo
_FRACCION_DUCTOS: float = 0.20      # margen automático de ductos (20% de ΔP_col+cam)
_COS_PHI: float = 0.85              # factor de potencia típico motor pequeño monofásico


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TipoAccionamiento(Enum):
    MOTOR_ELECTRICO = "MOTOR_ELECTRICO"
    EXTRACTOR_EOLICO = "EXTRACTOR_EOLICO"
    CONVECCION_NATURAL = "CONVECCION_NATURAL"


# ---------------------------------------------------------------------------
# Dataclass principal
# ---------------------------------------------------------------------------


@dataclass
class Motor:
    """Ventilador / motor de convección forzada del secador solar.

    Almacenado en Proyecto.motor. Es None si el secador opera por convección
    natural o si la tipología no requiere motor.

    Attributes:
        tipo_accionamiento: Tipo de accionamiento del flujo de aire.
        caudal_volumetrico_m3_s: Caudal volumétrico de diseño [m³/s].
        perdida_carga_total_Pa: ΔP total del sistema [Pa]. Si None, se calcula
            a partir de los sub-componentes.
        delta_P_colector_Pa: ΔP en el banco de colectores [Pa]. None = 0.
        delta_P_camara_Pa: ΔP en la cámara de secado [Pa]. None = 0.
        delta_P_ductos_Pa: ΔP en ductos de conexión [Pa]. None = 20% automático.
        eficiencia_ventilador: η del ventilador [0, 1]. Default: 0.55.
        eficiencia_motor: η del motor eléctrico [0, 1]. Default: 0.85.
        factor_servicio: Factor de sobredimensionamiento nominal [-]. Default: 1.15.
        tension_V: Tensión de alimentación [V]. 220 (monofásico) o 380 (trifásico).
        diametro_extractor_m: Diámetro del extractor eólico [m]. Obligatorio
            si tipo == EXTRACTOR_EOLICO.
        velocidad_viento_diseno_m_s: Velocidad de viento de diseño [m/s].
        notas: Campo libre.

    Campos calculados en __post_init__ (no forman parte de __init__):
        potencia_hidraulica_W, potencia_eje_W, potencia_electrica_W,
        potencia_a_instalar_W, corriente_nominal_A, advertencias.
    """

    tipo_accionamiento: TipoAccionamiento = TipoAccionamiento.MOTOR_ELECTRICO
    caudal_volumetrico_m3_s: float = 0.020
    perdida_carga_total_Pa: Optional[float] = None
    delta_P_colector_Pa: Optional[float] = None
    delta_P_camara_Pa: Optional[float] = None
    delta_P_ductos_Pa: Optional[float] = None
    eficiencia_ventilador: float = 0.55
    eficiencia_motor: float = 0.85
    factor_servicio: float = 1.15
    tension_V: Optional[float] = None
    diametro_extractor_m: Optional[float] = None
    velocidad_viento_diseno_m_s: Optional[float] = None
    notas: str = ""

    # Calculados en __post_init__ — no reciben valor del usuario
    potencia_hidraulica_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_eje_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_electrica_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_a_instalar_W: Optional[float] = field(default=None, init=False, repr=False)
    corriente_nominal_A: Optional[float] = field(default=None, init=False, repr=False)
    advertencias: list[Advertencia] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._validar()
        self._calcular()

    # ------------------------------------------------------------------
    # Validaciones duras
    # ------------------------------------------------------------------

    def _validar(self) -> None:
        if self.tipo_accionamiento == TipoAccionamiento.CONVECCION_NATURAL:
            raise ValueError(
                "MOT_CONVECCION_NATURAL_CON_MOTOR: para convección natural usar "
                "proyecto.motor = None, no instanciar Motor."
            )
        if self.caudal_volumetrico_m3_s <= 0:
            raise ValueError(
                f"MOT_CAUDAL_NO_POSITIVO: caudal_volumetrico_m3_s="
                f"{self.caudal_volumetrico_m3_s:.5f} m³/s ≤ 0."
            )
        if not (0.0 < self.eficiencia_ventilador <= 1.0):
            raise ValueError(
                f"MOT_EFICIENCIA_VENTILADOR_INVALIDA: eficiencia_ventilador="
                f"{self.eficiencia_ventilador:.3f} fuera del rango (0, 1]."
            )
        if not (0.0 < self.eficiencia_motor <= 1.0):
            raise ValueError(
                f"MOT_EFICIENCIA_MOTOR_INVALIDA: eficiencia_motor="
                f"{self.eficiencia_motor:.3f} fuera del rango (0, 1]."
            )
        if self.factor_servicio < 1.0:
            raise ValueError(
                f"MOT_FACTOR_SERVICIO_INVALIDO: factor_servicio={self.factor_servicio:.3f} "
                "< 1.0. El factor de servicio no puede ser menor que 1."
            )
        if (self.tipo_accionamiento == TipoAccionamiento.EXTRACTOR_EOLICO
                and self.diametro_extractor_m is None):
            raise ValueError(
                "MOT_EXTRACTOR_SIN_DIAMETRO: extractor eólico requiere "
                "diametro_extractor_m."
            )

    # ------------------------------------------------------------------
    # Cálculo de potencias
    # ------------------------------------------------------------------

    def _calcular(self) -> None:
        adv: list[Advertencia] = []

        # --- ΔP total ---
        if self.perdida_carga_total_Pa is None:
            dP_col = self.delta_P_colector_Pa or 0.0
            dP_cam = self.delta_P_camara_Pa or 0.0
            dP_duc = self.delta_P_ductos_Pa
            if dP_duc is None:
                dP_duc = _FRACCION_DUCTOS * (dP_col + dP_cam)
                adv.append(Advertencia(
                    codigo="MOT_DUCTOS_ESTIMADOS",
                    severidad=Severidad.INFO,
                    mensaje=(
                        f"ΔP ductos no especificada. Estimada como "
                        f"{_FRACCION_DUCTOS:.0%} de (ΔP_col + ΔP_cam) = {dP_duc:.1f} Pa."
                    ),
                    campo="delta_P_ductos_Pa",
                    sugerencia=(
                        "Especificar delta_P_ductos_Pa para un resultado más preciso, "
                        "o aceptar la estimación del 20%."
                    ),
                    contexto={"dP_ductos_estimado_Pa": round(dP_duc, 2)},
                ))
            self.perdida_carga_total_Pa = dP_col + dP_cam + dP_duc

        dP = self.perdida_carga_total_Pa
        Q = self.caudal_volumetrico_m3_s

        # --- Potencias (solo si ΔP > 0) ---
        if dP > 0.0:
            P_hid = Q * dP
            P_eje = P_hid / self.eficiencia_ventilador
            P_elec = P_eje / self.eficiencia_motor
            P_inst = P_elec * self.factor_servicio

            self.potencia_hidraulica_W = P_hid
            self.potencia_eje_W = P_eje
            self.potencia_electrica_W = P_elec
            self.potencia_a_instalar_W = P_inst

            if self.tension_V is not None:
                self.corriente_nominal_A = P_elec / (self.tension_V * _COS_PHI)

        # --- Advertencias de diseño ---
        P_inst = self.potencia_a_instalar_W
        if P_inst is not None and P_inst < _POTENCIA_BAJA_W:
            adv.append(Advertencia(
                codigo="MOT_POTENCIA_BAJA",
                severidad=Severidad.INFO,
                mensaje=(
                    f"Potencia a instalar {P_inst:.0f} W muy baja. "
                    "Un extractor eólico o convección natural podría ser suficiente, "
                    "evitando el costo de instalación eléctrica."
                ),
                campo="potencia_a_instalar_W",
                sugerencia="Evaluar tipo EXTRACTOR_EOLICO o convección natural.",
                contexto={"potencia_W": round(P_inst, 1)},
            ))
        elif P_inst is not None and P_inst > _POTENCIA_ALTA_W:
            adv.append(Advertencia(
                codigo="MOT_POTENCIA_ALTA",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Potencia a instalar {P_inst:.0f} W elevada para un secador solar. "
                    "Revisar las pérdidas de carga — posiblemente la geometría del "
                    "colector o la cámara sea subóptima."
                ),
                campo="potencia_a_instalar_W",
                sugerencia=(
                    "Reducir la velocidad de diseño, aumentar la sección del canal "
                    "o dividir el banco en más ramas paralelas."
                ),
                contexto={"potencia_W": round(P_inst, 1)},
            ))

        if (self.tipo_accionamiento == TipoAccionamiento.MOTOR_ELECTRICO
                and self.tension_V is None):
            adv.append(Advertencia(
                codigo="MOT_SIN_TENSION",
                severidad=Severidad.INFO,
                mensaje="Tensión de alimentación no especificada. No se calculará corriente nominal.",
                campo="tension_V",
                sugerencia="Especificar tension_V (220 o 380 V) para calcular corriente.",
                contexto={},
            ))

        if (self.tipo_accionamiento == TipoAccionamiento.EXTRACTOR_EOLICO
                and self.velocidad_viento_diseno_m_s is not None
                and self.velocidad_viento_diseno_m_s < _V_VIENTO_BAJA_MS):
            adv.append(Advertencia(
                codigo="MOT_EXTRACTOR_VIENTO_BAJO",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Velocidad de viento de diseño "
                    f"{self.velocidad_viento_diseno_m_s:.1f} m/s baja para extractor eólico. "
                    "El caudal generado puede ser insuficiente para el secado."
                ),
                campo="velocidad_viento_diseno_m_s",
                sugerencia=(
                    "Considerar motor eléctrico si la velocidad media del sitio "
                    f"es < {_V_VIENTO_BAJA_MS} m/s."
                ),
                contexto={"v_viento_ms": self.velocidad_viento_diseno_m_s},
            ))

        self.advertencias = adv
