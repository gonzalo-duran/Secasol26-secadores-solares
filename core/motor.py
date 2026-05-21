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

_POTENCIA_BAJA_W: float = 30.0  # advertencia: motor posiblemente innecesario
_POTENCIA_ALTA_W: float = 5000.0  # advertencia: revisar pérdidas de carga
_FRACCION_DUCTOS: float = 0.20  # margen automático de ductos (20% de ΔP_col+cam)
_COS_PHI: float = 0.85  # factor de potencia típico motor pequeño monofásico


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TipoAccionamiento(Enum):
    MOTOR_ELECTRICO = "MOTOR_ELECTRICO"
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
        delta_P_ductos_Pa: ΔP friccional en ductos de conexión [Pa]. None = 20% automático.
        delta_P_singulares_Pa: ΔP de pérdidas singulares (entrada, salida,
            codos, manifold de banco paralelo) [Pa]. None = 0. Se obtiene
            típicamente de ``calculos.motor_calc.estimar_delta_P_singulares``.
        v_descarga_m_s: Velocidad del aire en la descarga del ventilador [m/s].
            Si está definida, se suma la presión dinámica ρ·v²/2 al ΔP total
            (presión TOTAL del ventilador = estática + dinámica). None = 0
            (sólo presión estática, conservador a la baja).
        eficiencia_ventilador: η del ventilador [0, 1]. Default: 0.55.
        eficiencia_motor: η del motor eléctrico [0, 1]. Default: 0.85.
        factor_servicio: Factor de sobredimensionamiento nominal [-]. Default: 1.15.
        tension_V: Tensión de alimentación [V]. 220 (monofásico) o 380 (trifásico).
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
    delta_P_singulares_Pa: Optional[float] = None
    v_descarga_m_s: Optional[float] = None
    eficiencia_ventilador: float = 0.55
    eficiencia_motor: float = 0.85
    factor_servicio: float = 1.15
    tension_V: Optional[float] = None
    notas: str = ""

    # Calculados en __post_init__ — no reciben valor del usuario
    potencia_hidraulica_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_eje_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_electrica_W: Optional[float] = field(default=None, init=False, repr=False)
    potencia_a_instalar_W: Optional[float] = field(default=None, init=False, repr=False)
    corriente_nominal_A: Optional[float] = field(default=None, init=False, repr=False)
    advertencias: list[Advertencia] = field(default_factory=list, init=False, repr=False)

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
                adv.append(
                    Advertencia(
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
                    )
                )
            dP_sing = self.delta_P_singulares_Pa or 0.0
            # Presión dinámica de salida: ρ·v_descarga²/2.
            # Si v_descarga no se proveyó, asumimos cero (modelo histórico
            # conservador a la baja). Densidad del aire a ~50 °C / 1 atm.
            if self.v_descarga_m_s is not None and self.v_descarga_m_s > 0:
                rho_descarga = 101325.0 / (287.058 * 323.15)  # ~1.092 kg/m³
                dP_dinamica = rho_descarga * self.v_descarga_m_s**2 / 2.0
            else:
                dP_dinamica = 0.0
            self.perdida_carga_total_Pa = dP_col + dP_cam + dP_duc + dP_sing + dP_dinamica

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
            adv.append(
                Advertencia(
                    codigo="MOT_POTENCIA_BAJA",
                    severidad=Severidad.INFO,
                    mensaje=(
                        f"Potencia a instalar {P_inst:.0f} W muy baja. "
                        "Convección natural (chimenea solar, eventualmente con extractor "
                        "eólico) podría ser suficiente, evitando el costo de instalación "
                        "eléctrica."
                    ),
                    campo="potencia_a_instalar_W",
                    sugerencia=(
                        "Evaluar convección natural con chimenea solar (proyecto.motor = None)."
                    ),
                    contexto={"potencia_W": round(P_inst, 1)},
                )
            )
        elif P_inst is not None and P_inst > _POTENCIA_ALTA_W:
            adv.append(
                Advertencia(
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
                )
            )

        if self.tipo_accionamiento == TipoAccionamiento.MOTOR_ELECTRICO and self.tension_V is None:
            adv.append(
                Advertencia(
                    codigo="MOT_SIN_TENSION",
                    severidad=Severidad.INFO,
                    mensaje="Tensión de alimentación no especificada. No se calculará corriente nominal.",
                    campo="tension_V",
                    sugerencia="Especificar tension_V (220 o 380 V) para calcular corriente.",
                    contexto={},
                )
            )

        self.advertencias = adv
