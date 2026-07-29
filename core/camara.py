"""
Dataclasses de la cámara de secado solar.

Jerarquía:
    Camara
    ├── GeometriaCamara       — dimensiones internas [m]
    ├── ConstruccionCamara    — materiales/cubierta/aislación
    ├── ConfiguracionBandejas — número, área, espesor de capa, separación
    ├── ConfiguracionFlujo    — caudal, dirección, HR de entrada
    └── CargaProducto         — producto, humedades y modelos de secado

Almacenado en Proyecto.camara. Para tipologías ARMARIO y GRAN_ESCALA la cámara
recibe aire precalentado por el colector externo. Para tipología CAJA se admite
también una Camara, pero con `construccion.cubierta_translucida_id` obligatoria
(la única fuente de energía es la radiación solar a través del techo).

Convención de unidades (SI estricto):
    Temperaturas: K
    Longitudes:   m
    Masas:        kg
    Humedades del producto: kg agua / kg masa seca (base seca, X)
    Humedad relativa del aire: fracción [0, 1]
    Caudal másico: kg/s
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

import numpy as np

from core import catalogo
from core.advertencias import Advertencia, Severidad

# Modos válidos de cálculo de cámara
_MODOS_CALCULO_VALIDOS: tuple[str, ...] = ("capa_fina", "termodinamico")
# Rango razonable para T inicial del producto (caso refrigerado a precalentado)
_T_PROD_INICIAL_MIN_K: float = 263.15  # −10 °C
_T_PROD_INICIAL_MAX_K: float = 343.15  # +70 °C

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_VOL_MIN_M3: float = 0.01  # 10 litros — mínimo para secador funcional
_ALTO_MIN_TIPICO_M: float = 0.3  # límite inferior de rango típico [m]
_ALTO_MAX_TIPICO_M: float = 3.0  # límite superior de rango típico [m]
_RATIO_LARGO_ANCHO_MAX: float = 10.0
_RATIO_LARGO_ANCHO_MIN: float = 0.1
_ESPESOR_MAX_BANDEJA_M: float = 0.05  # 5 cm — espesor de lecho recomendado
_N_BANDEJAS_ALTO: int = 20
_V_SUP_MIN_MS: float = 0.3  # velocidad superficial mínima [m/s]
_V_SUP_MAX_MS: float = 3.0  # velocidad superficial máxima [m/s]
_RHO_AIRE_EST: float = 1.1  # densidad de aire estimada a ~50°C [kg/m³]
_CARGA_MAX_KG_M2: float = 20.0  # carga máxima de producto por m² de bandeja
_U_MUROS_ALTO_W_M2K: float = 2.0  # umbral de conductancia lateral alta


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class DireccionFlujo(Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL_ASCENDENTE = "VERTICAL_ASCENDENTE"


_CARAS_CAIDA_VALIDAS: tuple[str, ...] = ("frente", "atras", "lateral_izq", "lateral_der")
_PENDIENTE_TECHO_MAX_DEG: float = 60.0
_ALTO_MENOR_MIN_M: float = 0.05


def _normalizar_acimut_duffie(acimut_deg: float) -> float:
    """Envuelve un acimut Duffie arbitrario al rango canónico (−180, +180].

    Duplica la fórmula de ``calculos/conversiones_angulo.py`` (misma
    matemática pura) para no introducir una dependencia de ``core/`` hacia
    ``calculos/`` — la separación de capas del proyecto es estricta.
    """
    resultado = float(acimut_deg) % 360.0
    if resultado > 180.0:
        resultado -= 360.0
    return resultado


# ---------------------------------------------------------------------------
# Sub-dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CaraCamara:
    """Una cara captadora de la cámara (techo o pared vertical).

    Attributes:
        area_m2: Área geométrica de la cara [m²].
        tilt_deg: Inclinación respecto a la horizontal [°]. 90° = vertical.
        acimut_duffie_deg: Acimut de la normal exterior, convención Duffie
            (0°=Sur, +90°=Oeste, −90°=Este, ±180°=Norte).
    """

    area_m2: float
    tilt_deg: float
    acimut_duffie_deg: float


@dataclass
class GeometriaCamara:
    """Dimensiones internas de la cámara de secado.

    El techo es a un agua: cae desde ``alto_mayor_m`` hasta ``alto_menor_m``
    en la dirección de ``cara_caida_techo`` (esa cara es la de menor altura).
    ``alto_m`` es la altura MEDIA de la cámara — el volumen
    ``largo_m·ancho_m·alto_m`` y el área transversal de flujo
    ``ancho_m·alto_m`` son exactos con techo inclinado, sin cambios respecto
    al caso histórico de techo plano (``pendiente_techo_deg=0``).

    Attributes:
        largo_m: Dimensión horizontal en la dirección del flujo [m].
        ancho_m: Dimensión horizontal transversal al flujo [m].
        alto_m: Altura libre interna MEDIA [m].
        pendiente_techo_deg: Inclinación del techo a un agua respecto a la
            horizontal [°]. 0° = techo plano (comportamiento histórico).
        acimut_camara_deg: Acimut de la normal exterior de la cara "frente"
            de la cámara, convención Duffie (0°=Sur, +90°=Oeste, −90°=Este,
            ±180°=Norte). Define la orientación de todas las caras.
        cara_caida_techo: Cara hacia la que cae el techo (la de menor
            altura). El acimut del techo coincide con el de esa cara.
    """

    largo_m: float = 1.2
    ancho_m: float = 0.8
    alto_m: float = 1.5
    pendiente_techo_deg: float = 0.0
    acimut_camara_deg: float = 180.0
    cara_caida_techo: Literal["frente", "atras", "lateral_izq", "lateral_der"] = "frente"

    def __post_init__(self) -> None:
        if self.largo_m <= 0 or self.ancho_m <= 0 or self.alto_m <= 0:
            raise ValueError(
                f"GEO_DIMENSIONES_NO_POSITIVAS: dimensiones deben ser positivas. "
                f"Recibido: largo={self.largo_m}, ancho={self.ancho_m}, alto={self.alto_m}."
            )
        vol = self.largo_m * self.ancho_m * self.alto_m
        if vol < _VOL_MIN_M3:
            raise ValueError(
                f"GEO_VOLUMEN_MINIMO: volumen {vol:.4f} m³ < {_VOL_MIN_M3} m³ mínimo operativo."
            )
        if not (0.0 <= self.pendiente_techo_deg <= _PENDIENTE_TECHO_MAX_DEG):
            raise ValueError(
                f"GEO_PENDIENTE_TECHO_INVALIDA: pendiente_techo_deg={self.pendiente_techo_deg:.2f}° "
                f"fuera del rango válido [0, {_PENDIENTE_TECHO_MAX_DEG:.0f}]°."
            )
        if not (-180.0 <= self.acimut_camara_deg <= 180.0):
            raise ValueError(
                f"GEO_ACIMUT_CAMARA_INVALIDO: acimut_camara_deg={self.acimut_camara_deg:.2f}° "
                "fuera del rango válido [-180, 180]°."
            )
        if self.cara_caida_techo not in _CARAS_CAIDA_VALIDAS:
            raise ValueError(
                f"GEO_CARA_CAIDA_INVALIDA: cara_caida_techo='{self.cara_caida_techo}' "
                f"no es válida. Opciones: {_CARAS_CAIDA_VALIDAS}."
            )
        if self.alto_menor_m <= _ALTO_MENOR_MIN_M:
            raise ValueError(
                f"GEO_ALTO_MENOR_INSUFICIENTE: con pendiente {self.pendiente_techo_deg:.1f}° "
                f"el alto menor del techo ({self.alto_menor_m:.3f} m) queda por debajo del "
                f"mínimo operativo ({_ALTO_MENOR_MIN_M} m). Reducir la pendiente o aumentar alto_m."
            )

    @property
    def area_planta_m2(self) -> float:
        """Área de planta (huella horizontal) de la cámara [m²]."""
        return self.largo_m * self.ancho_m

    @property
    def _profundidad_caida_m(self) -> float:
        """Dimensión en la dirección en que corre la pendiente del techo [m]."""
        if self.cara_caida_techo in ("frente", "atras"):
            return self.largo_m
        return self.ancho_m

    @property
    def alto_menor_m(self) -> float:
        """Altura de la cara hacia la que cae el techo [m]."""
        return self.alto_m - (self._profundidad_caida_m / 2.0) * math.tan(
            math.radians(self.pendiente_techo_deg)
        )

    @property
    def alto_mayor_m(self) -> float:
        """Altura de la cara opuesta a la caída del techo [m]."""
        return self.alto_m + (self._profundidad_caida_m / 2.0) * math.tan(
            math.radians(self.pendiente_techo_deg)
        )

    @property
    def A_techo_geom_m2(self) -> float:
        """Área real del techo inclinado (planta / cos β) [m²]."""
        return self.area_planta_m2 / math.cos(math.radians(self.pendiente_techo_deg))

    def caras(self) -> dict[str, CaraCamara]:
        """Geometría (área, tilt, acimut) de las 5 caras captadoras.

        El piso no se incluye (siempre opaco). Las caras rectangulares
        (frente/atrás o laterales, según el eje de caída) tienen alturas
        ``alto_menor_m``/``alto_mayor_m``; las trapezoidales (el otro par)
        usan la altura media ``alto_m``, exacta para su área real.

        Returns:
            Diccionario con claves "techo", "frente", "atras",
            "lateral_izq", "lateral_der".
        """
        g_acimut = self.acimut_camara_deg
        ac_frente = g_acimut
        ac_atras = _normalizar_acimut_duffie(g_acimut + 180.0)
        ac_der = _normalizar_acimut_duffie(g_acimut + 90.0)
        ac_izq = _normalizar_acimut_duffie(g_acimut - 90.0)

        if self.cara_caida_techo in ("frente", "atras"):
            rect_dim = self.ancho_m
            trap_dim = self.largo_m
            rect_acimut = {"frente": ac_frente, "atras": ac_atras}
            trap_acimut = {"lateral_izq": ac_izq, "lateral_der": ac_der}
        else:
            rect_dim = self.largo_m
            trap_dim = self.ancho_m
            rect_acimut = {"lateral_izq": ac_izq, "lateral_der": ac_der}
            trap_acimut = {"frente": ac_frente, "atras": ac_atras}

        cara_baja = self.cara_caida_techo
        cara_alta = next(nombre for nombre in rect_acimut if nombre != cara_baja)

        caras: dict[str, CaraCamara] = {
            cara_baja: CaraCamara(
                area_m2=rect_dim * self.alto_menor_m,
                tilt_deg=90.0,
                acimut_duffie_deg=rect_acimut[cara_baja],
            ),
            cara_alta: CaraCamara(
                area_m2=rect_dim * self.alto_mayor_m,
                tilt_deg=90.0,
                acimut_duffie_deg=rect_acimut[cara_alta],
            ),
        }
        for nombre, acimut in trap_acimut.items():
            caras[nombre] = CaraCamara(
                area_m2=trap_dim * self.alto_m, tilt_deg=90.0, acimut_duffie_deg=acimut
            )
        caras["techo"] = CaraCamara(
            area_m2=self.A_techo_geom_m2,
            tilt_deg=self.pendiente_techo_deg,
            acimut_duffie_deg=caras[cara_baja].acimut_duffie_deg,
        )
        return caras

    @property
    def A_cuerpo_total_m2(self) -> float:
        """Área total de la envolvente: 6 caras (piso + 5 captadoras) [m²].

        Con ``pendiente_techo_deg=0`` es idéntica a la fórmula histórica de
        caja con techo plano: ``2·(largo·alto + ancho·alto + largo·ancho)``.
        """
        return self.area_planta_m2 + sum(c.area_m2 for c in self.caras().values())


_CATALOGOS_PARED: tuple[str, ...] = ("fondos", "aislantes")


def _catalogo_pared(nombre: str) -> dict:
    if nombre == "fondos":
        return catalogo.FONDOS
    if nombre == "aislantes":
        return catalogo.AISLANTES
    raise ValueError(
        f"CAPA_CATALOGO_INVALIDO: '{nombre}' no es un catálogo válido. "
        f"Opciones: {_CATALOGOS_PARED}."
    )


@dataclass
class CapaPared:
    """Una capa material de la pared de la cámara.

    Cada capa apunta a un material del catálogo (fondos.yaml o aislantes.yaml)
    y declara su espesor. La resistencia térmica de conducción se computa como
    R = espesor / k_material.

    Attributes:
        material_id: Clave del material en su catálogo.
        espesor_m: Espesor de la capa [m].
        catalogo: Catálogo de origen — "fondos" (materiales estructurales) o
            "aislantes" (lana de vidrio, EPS, PUR, etc.).
    """

    material_id: str
    espesor_m: float
    catalogo: Literal["fondos", "aislantes"]

    def __post_init__(self) -> None:
        if self.espesor_m <= 0:
            raise ValueError(f"CAPA_ESPESOR_NO_POSITIVO: espesor_m={self.espesor_m:.4f} m ≤ 0.")
        if self.catalogo not in _CATALOGOS_PARED:
            raise ValueError(
                f"CAPA_CATALOGO_INVALIDO: '{self.catalogo}'. " f"Opciones: {_CATALOGOS_PARED}."
            )
        cat = _catalogo_pared(self.catalogo)
        if self.material_id not in cat:
            raise ValueError(
                f"CAPA_MATERIAL_NO_ENCONTRADO: '{self.material_id}' no existe en "
                f"{self.catalogo}.yaml. Disponibles: {list(cat.keys())}."
            )

    @property
    def conductividad_termica_W_mK(self) -> float:
        return float(_catalogo_pared(self.catalogo)[self.material_id]["conductividad_termica"])

    @property
    def R_conduccion_m2K_W(self) -> float:
        return self.espesor_m / self.conductividad_termica_W_mK


@dataclass
class ParedCamara:
    """Composición de la envolvente opaca de la cámara.

    Aplica a las paredes laterales, piso y techo (salvo que el techo sea
    translúcido, en cuyo caso ese se trata aparte vía ``cubierta_translucida_id``).

    Pared simple = lista de 1 capa. Pared compuesta = lista de 2+ capas
    (típicamente 3: cara externa + aislante + cara interna).

    La resistencia total de conducción es la suma de las resistencias de cada
    capa (capas en serie). Los films convectivos interior/exterior se aplican
    en el motor termodinámico, no acá.

    Attributes:
        capas: Lista de capas en orden externo → interno (no afecta a R_total,
            pero conviene seguir esa convención para legibilidad).
    """

    capas: list[CapaPared]

    def __post_init__(self) -> None:
        if not self.capas:
            raise ValueError("PARED_SIN_CAPAS: la pared debe tener al menos una capa.")

    @property
    def R_conduccion_m2K_W(self) -> float:
        return sum(c.R_conduccion_m2K_W for c in self.capas)

    @property
    def U_conduccion_W_m2K(self) -> float:
        return 1.0 / self.R_conduccion_m2K_W

    @property
    def espesor_total_m(self) -> float:
        return sum(c.espesor_m for c in self.capas)

    @property
    def es_compuesta(self) -> bool:
        return len(self.capas) >= 2


def _default_pared_camara() -> ParedCamara:
    """Default razonable: pared compuesta chapa + lana de vidrio 50 mm + chapa.

    U_conduccion ≈ 0.8 W/(m²·K), próximo al U_muros=0.5 histórico. Realista
    para un secador armario con aislación estándar.
    """
    return ParedCamara(
        capas=[
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
            CapaPared(material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes"),
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
        ]
    )


@dataclass(frozen=True)
class CarasTranslucidas:
    """Qué caras de la cámara llevan la cubierta translúcida (vs. opacas).

    El material y espesor de la cubierta son únicos para toda la cámara
    (``ConstruccionCamara.cubierta_translucida_id``); esto solo decide en
    qué caras se monta. El piso no se incluye: siempre es opaco. Default
    (solo techo) reproduce el comportamiento histórico.

    Attributes:
        techo: Techo translúcido.
        frente: Pared frontal translúcida.
        atras: Pared trasera translúcida.
        lateral_izq: Pared lateral izquierda translúcida.
        lateral_der: Pared lateral derecha translúcida.
    """

    techo: bool = True
    frente: bool = False
    atras: bool = False
    lateral_izq: bool = False
    lateral_der: bool = False

    def activas(self) -> tuple[str, ...]:
        """Nombres de las caras marcadas como translúcidas."""
        return tuple(
            nombre for nombre in _CARAS_CAIDA_VALIDAS + ("techo",) if getattr(self, nombre)
        )


@dataclass
class ConstruccionCamara:
    """Propiedades constructivas de la cámara.

    Attributes:
        cubierta_translucida_id: Identificador del material de la cubierta
            translúcida en el catálogo ``catalogo/materiales/cubiertas.yaml``.
            ``None`` → todas las caras opacas (envolvente completa con la
            composición de ``pared``), y ``caras_translucidas`` se ignora.
            Cualquier string válido activa el término radiativo en las caras
            marcadas por ``caras_translucidas`` (mismo material y espesor
            para todas — ver ``calculos/radiacion_camara.py``).
        A_rad_m2: Área expuesta a la radiación solar directa que intercepta
            el producto [m²]. ``None`` → toma ``area_bandeja_m2`` de la
            bandeja superior (sólo la primera "ve" el sol directamente).
            Ignorado si ``cubierta_translucida_id is None``.
        cubierta_translucida_espesor_m: Espesor de la cubierta translúcida
            [m], único para todas las caras vidriadas. ``None`` → el motor
            usa un default razonable (6 mm). El espesor entra al balance
            térmico como conducción del vidriado ``R_cond = espesor /
            k_efectivo`` (esas caras dejan de modelarse como pared opaca;
            ver ``camara_calc``). Ignorado si ``cubierta_translucida_id is
            None``.
        caras_translucidas: Qué caras llevan la cubierta (default: solo
            techo, comportamiento histórico). Ignorado si
            ``cubierta_translucida_id is None``.
        absortancia_interior: Absortancia solar de las superficies internas
            opacas (paredes, piso) para la fracción de radiación que no
            intercepta el producto directamente [0–1]. Alimenta el término
            ``Q_rad_aire`` (radiación que calienta el aire vía las paredes
            internas — efecto invernadero de la caja).
        pared: Composición de la envolvente opaca (paredes + piso + caras
            no vidriadas). 1 capa = pared simple; 3 capas = pared compuesta
            cara externa + aislante + cara interna.

    Properties:
        U_muros_W_m2K: Conductancia de conducción de la pared, computada como
            ``1 / R_conduccion_pared`` (los films convectivos los suma el motor).
    """

    cubierta_translucida_id: Optional[str] = None
    A_rad_m2: Optional[float] = None
    cubierta_translucida_espesor_m: Optional[float] = None
    caras_translucidas: CarasTranslucidas = field(default_factory=CarasTranslucidas)
    absortancia_interior: float = 0.85
    pared: ParedCamara = field(default_factory=_default_pared_camara)

    def __post_init__(self) -> None:
        if self.cubierta_translucida_id is not None:
            if self.cubierta_translucida_id not in catalogo.CUBIERTAS:
                raise ValueError(
                    f"MAT_CUBIERTA_CAM_NO_ENCONTRADA: '{self.cubierta_translucida_id}' "
                    "no existe en cubiertas.yaml. Disponibles: "
                    f"{list(catalogo.CUBIERTAS.keys())}."
                )
        if self.A_rad_m2 is not None and self.A_rad_m2 <= 0:
            raise ValueError(f"CONS_A_RAD_NO_POSITIVA: A_rad_m2={self.A_rad_m2:.4f} m² ≤ 0.")
        if (
            self.cubierta_translucida_espesor_m is not None
            and self.cubierta_translucida_espesor_m <= 0
        ):
            raise ValueError(
                "CONS_ESPESOR_CUBIERTA_NO_POSITIVO: cubierta_translucida_espesor_m="
                f"{self.cubierta_translucida_espesor_m} m ≤ 0. Si se especifica debe ser > 0."
            )
        if not (0.0 < self.absortancia_interior <= 1.0):
            raise ValueError(
                f"CONS_ABSORTANCIA_INTERIOR_INVALIDA: absortancia_interior="
                f"{self.absortancia_interior:.3f} fuera del rango válido (0, 1]."
            )

    def caras_translucidas_activas(self) -> tuple[str, ...]:
        """Caras efectivamente translúcidas (vacía si no hay cubierta)."""
        if self.cubierta_translucida_id is None:
            return ()
        return self.caras_translucidas.activas()

    @property
    def U_muros_W_m2K(self) -> float:
        """Conductancia por conducción de la pared opaca [W/(m²·K)].

        Computada de la composición de capas. Los films convectivos
        (interior aire-pared, exterior pared-viento) los aplica el motor TD
        en la cascada de resistencias h_int + R_pared + h_w.
        """
        return self.pared.U_conduccion_W_m2K


@dataclass
class ConfiguracionBandejas:
    """Configuración del sistema de bandejas de secado.

    Attributes:
        n_bandejas: Número total de bandejas en la cámara.
        area_bandeja_m2: Área de carga de producto por bandeja [m²].
        espesor_capa_m: Espesor de la capa de producto sobre la bandeja [m].
            Los modelos de capa fina son válidos para espesor ≤ 0.05 m.
        separacion_entre_bandejas_m: Distancia entre superficies de bandejas
            consecutivas [m]. Debe ser > espesor_capa_m + 0.01 m.
        tipo_malla: Identificador del tipo de malla (para cálculo de caída de presión).
            None si no se especifica.
        K_rugosidad_producto: Coeficiente K (adimensional) de pérdida de
            forma por rugosidad del producto sobre la bandeja, aplicado
            como K·ρv²/2 una vez por bandeja. ``None`` indica
            autocalcular desde ``d_p / espacio_libre`` (cross-flow
            HORIZONTAL) o ignorar (en VERTICAL no aplica porque Ergun
            ya captura la rugosidad del producto).
    """

    n_bandejas: int = 5
    area_bandeja_m2: float = 0.50
    espesor_capa_m: float = 0.020
    separacion_entre_bandejas_m: float = 0.15
    tipo_malla: Optional[str] = None
    porosidad_lecho: float = 0.45
    diametro_eq_particula_m: Optional[float] = None
    esfericidad: float = 0.60
    K_rugosidad_producto: Optional[float] = None

    def __post_init__(self) -> None:
        if self.n_bandejas < 1:
            raise ValueError(
                "BAND_N_BANDEJAS_NO_POSITIVO: n_bandejas debe ser ≥ 1. "
                f"Recibido: {self.n_bandejas}."
            )
        if self.area_bandeja_m2 <= 0:
            raise ValueError(
                f"BAND_AREA_NO_POSITIVA: area_bandeja_m2={self.area_bandeja_m2:.4f} m² ≤ 0."
            )
        if self.espesor_capa_m <= 0:
            raise ValueError(
                f"BAND_ESPESOR_NO_POSITIVO: espesor_capa_m={self.espesor_capa_m:.4f} m ≤ 0."
            )
        if self.separacion_entre_bandejas_m <= 0:
            raise ValueError(
                f"BAND_SEPARACION_NO_POSITIVA: separacion_entre_bandejas_m="
                f"{self.separacion_entre_bandejas_m:.4f} m ≤ 0."
            )
        margen_min = self.espesor_capa_m + 0.01
        if self.separacion_entre_bandejas_m < margen_min:
            raise ValueError(
                f"BAND_SEPARACION_INSUFICIENTE: separación {self.separacion_entre_bandejas_m:.3f} m "
                f"< espesor_capa {self.espesor_capa_m:.3f} m + margen 0.01 m "
                f"= {margen_min:.3f} m mínimo."
            )
        if not (0.0 < self.porosidad_lecho < 1.0):
            raise ValueError(
                f"BAND_POROSIDAD_INVALIDA: porosidad_lecho={self.porosidad_lecho:.3f} "
                "fuera del rango válido (0, 1)."
            )
        if self.diametro_eq_particula_m is not None and self.diametro_eq_particula_m <= 0:
            raise ValueError(
                f"BAND_DIAMETRO_PARTICULA_NO_POSITIVO: diametro_eq_particula_m="
                f"{self.diametro_eq_particula_m:.6f} m ≤ 0."
            )
        if not (0.0 < self.esfericidad <= 1.0):
            raise ValueError(
                f"BAND_ESFERICIDAD_INVALIDA: esfericidad={self.esfericidad:.3f} "
                "fuera del rango válido (0, 1]."
            )
        if self.K_rugosidad_producto is not None and self.K_rugosidad_producto < 0:
            raise ValueError(
                f"BAND_K_RUGOSIDAD_INVALIDO: K_rugosidad_producto="
                f"{self.K_rugosidad_producto:.3f} debe ser ≥ 0."
            )


@dataclass
class ConfiguracionFlujo:
    """Configuración del flujo de aire a través de la cámara.

    Attributes:
        caudal_masico_kg_s: Caudal másico de aire seco que atraviesa la cámara [kg/s].
            Debe coincidir con el caudal del banco de colectores (cuando aplica).
        fraccion_recirculacion: Fracción del aire recirculado [0, 1].
            Solo 0 está implementado en v0.
        direccion_flujo: Dirección del flujo de aire en la cámara.
        HR_entrada_fraccion: Humedad relativa del aire en la entrada de la cámara
            [fracción 0–1]. None implica uso de fallback del catálogo.
        seguir_caudal_colector: Si True, ``caudal_masico_kg_s`` se toma del banco
            de colectores en vez de fijarse a mano — el sistema es hermético y lo
            que sale del banco entra a la cámara. Es una **decisión de diseño**
            del usuario y por eso se persiste: antes se infería comparando el
            caudal guardado con el del banco, y bastaba recalcular el clima con
            otro año (ρ cambia con la T media) para que la app dedujera que el
            usuario los había desacoplado a propósito (S58).
        area_entrada_aire_m2: Área libre de la(s) boca(s) de **entrada** de aire
            [m²]. ``None`` = sin definir. Junto con ``area_salida_aire_m2``
            habilita el **motor de convección natural** de un secador pasivo sin
            chimenea (S61): las bocas son la resistencia del lazo y la altura de
            la cámara, la columna de tiro. Sin ellas —y sin chimenea— el caudal
            queda en el valor de diseño constante, que es lo que hacía toda
            versión anterior.
        area_salida_aire_m2: Ídem para la(s) boca(s) de **salida** [m²].
    """

    caudal_masico_kg_s: float = 0.030
    fraccion_recirculacion: float = 0.0
    direccion_flujo: DireccionFlujo = DireccionFlujo.HORIZONTAL
    HR_entrada_fraccion: Optional[float] = None
    seguir_caudal_colector: bool = True
    area_entrada_aire_m2: Optional[float] = None
    area_salida_aire_m2: Optional[float] = None

    @property
    def bocas_definidas(self) -> bool:
        """True si están cargadas ambas áreas de boca (entrada y salida).

        Es la condición que habilita el motor de flotabilidad sin chimenea: con
        una sola de las dos el lazo no queda cerrado (falta una resistencia) y
        el caudal de equilibrio sería indeterminado.
        """
        return (
            self.area_entrada_aire_m2 is not None
            and self.area_salida_aire_m2 is not None
            and self.area_entrada_aire_m2 > 0
            and self.area_salida_aire_m2 > 0
        )

    def __post_init__(self) -> None:
        if self.caudal_masico_kg_s <= 0:
            raise ValueError(
                f"FLUJO_CAUDAL_NO_POSITIVO: caudal_masico_kg_s={self.caudal_masico_kg_s:.4f} "
                "kg/s ≤ 0. El caudal debe ser positivo."
            )
        if self.fraccion_recirculacion > 0:
            raise NotImplementedError(
                f"FLUJO_RECIRCULACION_NO_IMPLEMENTADA: fraccion={self.fraccion_recirculacion:.3f}. "
                "La recirculación de aire no está implementada en v0. "
                "Usar fraccion_recirculacion=0."
            )
        if self.direccion_flujo not in (
            DireccionFlujo.HORIZONTAL,
            DireccionFlujo.VERTICAL_ASCENDENTE,
        ):
            raise NotImplementedError(
                f"FLUJO_DIRECCION_NO_SOPORTADA: '{self.direccion_flujo}' no soportada en v0. "
                "Opciones: HORIZONTAL, VERTICAL_ASCENDENTE."
            )
        if self.HR_entrada_fraccion is not None and not (0.0 <= self.HR_entrada_fraccion <= 1.0):
            raise ValueError(
                f"FLUJO_HR_ENTRADA_INVALIDA: HR_entrada_fraccion={self.HR_entrada_fraccion:.3f} "
                "fuera del rango válido [0, 1]."
            )
        if self.area_entrada_aire_m2 is not None and self.area_entrada_aire_m2 <= 0:
            raise ValueError(
                f"FLUJO_AREA_ENTRADA_NO_POSITIVA: area_entrada_aire_m2="
                f"{self.area_entrada_aire_m2:.4f} m² ≤ 0. Usar None si no está definida."
            )
        if self.area_salida_aire_m2 is not None and self.area_salida_aire_m2 <= 0:
            raise ValueError(
                f"FLUJO_AREA_SALIDA_NO_POSITIVA: area_salida_aire_m2="
                f"{self.area_salida_aire_m2:.4f} m² ≤ 0. Usar None si no está definida."
            )


@dataclass
class CargaProducto:
    """Producto a secar y condiciones de secado objetivo.

    Attributes:
        producto_id: Clave del producto en el catálogo YAML (ej.: 'manzana').
        masa_total_kg: Masa total de producto fresco a secar [kg].
        humedad_inicial_X: Humedad inicial en base seca [kg agua / kg ms].
        humedad_objetivo_X: Humedad final objetivo en base seca [kg agua / kg ms].
            Debe ser menor que humedad_inicial_X.
        modelo_capa_fina: Nombre del modelo cinético de capa fina a usar.
            Opciones según catálogo: 'page', 'midilli', 'henderson', 'lewis', 'logaritmico'.
        modelo_isoterma: Modelo de isoterma de sorción para calcular X_eq.
            'gab' es el único implementado en v0.
    """

    producto_id: str = "manzana"
    masa_total_kg: float = 10.0
    humedad_inicial_X: float = 4.6
    humedad_objetivo_X: float = 0.15
    modelo_capa_fina: str = "logaritmico"
    modelo_isoterma: str = "gab"
    T_prod_inicial_K: Optional[float] = None

    def __post_init__(self) -> None:
        if self.masa_total_kg <= 0:
            raise ValueError(
                f"PROD_MASA_NO_POSITIVA: masa_total_kg={self.masa_total_kg:.3f} kg ≤ 0."
            )
        if self.humedad_inicial_X < 0:
            raise ValueError(
                f"PROD_HUMEDAD_INICIAL_NEGATIVA: humedad_inicial_X={self.humedad_inicial_X:.4f} < 0. "
                "La humedad en base seca no puede ser negativa."
            )
        if self.humedad_objetivo_X < 0:
            raise ValueError(
                f"PROD_HUMEDAD_OBJETIVO_NEGATIVA: humedad_objetivo_X={self.humedad_objetivo_X:.4f} < 0."
            )
        if self.humedad_objetivo_X >= self.humedad_inicial_X:
            raise ValueError(
                f"PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL: objetivo {self.humedad_objetivo_X:.4f} "
                f">= inicial {self.humedad_inicial_X:.4f}. El secado reduce la humedad."
            )
        if self.T_prod_inicial_K is not None:
            if not (_T_PROD_INICIAL_MIN_K <= self.T_prod_inicial_K <= _T_PROD_INICIAL_MAX_K):
                raise ValueError(
                    f"PROD_T_INICIAL_FUERA_RANGO: T_prod_inicial_K="
                    f"{self.T_prod_inicial_K:.2f} K ∉ "
                    f"[{_T_PROD_INICIAL_MIN_K:.2f}, {_T_PROD_INICIAL_MAX_K:.2f}] K. "
                    "Rango razonable: producto refrigerado (−10 °C) a precalentado (70 °C). "
                    "Si es None, el motor termodinámico usa T_amb como fallback."
                )


# ---------------------------------------------------------------------------
# Configuración del túnel semicontinuo (solo subtipo GRAN_ESCALA SEMICONTINUO)
# ---------------------------------------------------------------------------


@dataclass
class ConfiguracionTunel:
    """Configuración del túnel semicontinuo a contracorriente (estilo ADITAL).

    Solo aplica cuando ``configuracion.tipologia == GRAN_ESCALA`` y
    ``configuracion.subtipo_gran_escala == SEMICONTINUO``. La geometría total
    del túnel y la carga total de producto se toman de ``Camara`` (geometria,
    bandejas, carga_producto) y se reparten en ``n_zonas`` columnas iguales; el
    motor ``camara_termodinamica.simular_cascada`` integra la cascada.

    El producto avanza a contracorriente del aire: una columna avanza una
    posición cada ``intervalo_avance_h`` horas (cadencia fija → sequedad de
    salida emergente). La residencia total de un carro es
    ``n_zonas × intervalo_avance_h``.

    Attributes:
        n_zonas: Número de columnas (zonas) en serie (≥ 1). Default 6.
        intervalo_avance_h: Cada cuántas horas avanza una columna [h] (> 0).
            Default 24 h (una jornada, cadencia típica del operario de ADITAL).
    """

    n_zonas: int = 6
    intervalo_avance_h: float = 24.0

    def __post_init__(self) -> None:
        if self.n_zonas < 1:
            raise ValueError(f"TUNEL_N_ZONAS_INVALIDO: n_zonas={self.n_zonas} < 1.")
        if self.intervalo_avance_h <= 0:
            raise ValueError(
                f"TUNEL_INTERVALO_NO_POSITIVO: intervalo_avance_h="
                f"{self.intervalo_avance_h:.2f} h ≤ 0."
            )

    @property
    def intervalo_avance_s(self) -> float:
        """Intervalo de avance en segundos."""
        return self.intervalo_avance_h * 3600.0

    @property
    def residencia_total_h(self) -> float:
        """Residencia total de un carro a través del túnel [h]."""
        return self.n_zonas * self.intervalo_avance_h


@dataclass
class ConfiguracionCarros:
    """Disposición real del producto en gran escala: carros con bandejas (S41).

    En el secador industrial (estilo ADITAL) el producto no va en bandejas
    sueltas apiladas en la cámara: va en **carros** móviles, cada uno con una
    pila de bandejas. En el subtipo SEMICONTINUO el carro es la unidad física
    que avanza por el túnel (**cada zona aloja exactamente un carro**, por lo
    que ``ConfiguracionTunel.n_zonas`` debe coincidir con ``n_carros``); en
    BATCH los carros son estáticos dentro de la cámara.

    El número total de bandejas queda **derivado**:
    ``n_carros × bandejas_por_carro`` — ``Camara.__post_init__`` lo sincroniza
    sobre ``ConfiguracionBandejas.n_bandejas``. La geometría de cada bandeja
    (área, espesor de capa, separación vertical) sigue viviendo en
    ``ConfiguracionBandejas``.

    Attributes:
        n_carros: Carros en la cámara/túnel (≥ 1). ADITAL: 24.
        bandejas_por_carro: Bandejas apiladas en cada carro (≥ 1).
        largo_carro_m: Huella del carro en la dirección del túnel [m]
            (opcional, para la advertencia de encaje en fila).
        ancho_carro_m: Huella transversal del carro [m] (opcional).
    """

    n_carros: int = 24
    bandejas_por_carro: int = 14
    largo_carro_m: Optional[float] = None
    ancho_carro_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.n_carros < 1:
            raise ValueError(f"CARROS_N_NO_POSITIVO: n_carros={self.n_carros} < 1.")
        if self.bandejas_por_carro < 1:
            raise ValueError(
                f"CARROS_BANDEJAS_NO_POSITIVAS: bandejas_por_carro="
                f"{self.bandejas_por_carro} < 1."
            )
        if self.largo_carro_m is not None and self.largo_carro_m <= 0:
            raise ValueError(
                f"CARROS_LARGO_NO_POSITIVO: largo_carro_m={self.largo_carro_m:.3f} ≤ 0."
            )
        if self.ancho_carro_m is not None and self.ancho_carro_m <= 0:
            raise ValueError(
                f"CARROS_ANCHO_NO_POSITIVO: ancho_carro_m={self.ancho_carro_m:.3f} ≤ 0."
            )

    @property
    def n_bandejas_total(self) -> int:
        """Bandejas totales de la cámara: n_carros × bandejas_por_carro."""
        return self.n_carros * self.bandejas_por_carro


# ---------------------------------------------------------------------------
# Camara (raíz de la sección)
# ---------------------------------------------------------------------------


@dataclass
class Camara:
    """Cámara de secado solar completa.

    Almacenada en Proyecto.camara. Para CAJA se admite con
    `construccion.cubierta_translucida_id` obligatoria; para ARMARIO y
    GRAN_ESCALA es opcional (aire precalentado por colector externo).

    Attributes:
        geometria: Dimensiones internas de la cámara.
        construccion: Propiedades constructivas (cubierta, aislación lateral).
        bandejas: Configuración del sistema de bandejas.
        flujo: Configuración del flujo de aire.
        carga_producto: Producto y condiciones de secado.
        modo_calculo: Campo vestigial (desde S38). La cámara tiene un único
            motor físico (balance acoplado calor-masa). Cualquier valor se
            resuelve al motor termodinámico; el legacy 'capa_fina' se coacciona
            a 'termodinamico' en __post_init__ para back-compat de snapshots.
    """

    geometria: GeometriaCamara = field(default_factory=GeometriaCamara)
    construccion: ConstruccionCamara = field(default_factory=ConstruccionCamara)
    bandejas: ConfiguracionBandejas = field(default_factory=ConfiguracionBandejas)
    flujo: ConfiguracionFlujo = field(default_factory=ConfiguracionFlujo)
    carga_producto: CargaProducto = field(default_factory=CargaProducto)
    modo_calculo: Literal["capa_fina", "termodinamico"] = "termodinamico"
    tunel: Optional[ConfiguracionTunel] = None
    carros: Optional[ConfiguracionCarros] = None

    def __post_init__(self) -> None:
        # Back-compat (S38): el motor de capa fina fue eliminado. Snapshots y
        # llamadas antiguas con modo_calculo='capa_fina' se normalizan al único
        # motor disponible (termodinámico).
        if self.modo_calculo == "capa_fina":
            self.modo_calculo = "termodinamico"
        if self.modo_calculo not in _MODOS_CALCULO_VALIDOS:
            raise ValueError(
                f"CAM_MODO_INVALIDO: modo_calculo='{self.modo_calculo}' no es válido. "
                f"Opciones: {_MODOS_CALCULO_VALIDOS}."
            )
        # Carros (S41): el total de bandejas queda derivado de la jerarquía
        # carro → bandejas; en el túnel cada zona aloja exactamente un carro.
        if self.carros is not None:
            self.bandejas.n_bandejas = self.carros.n_bandejas_total
            if self.tunel is not None and self.tunel.n_zonas != self.carros.n_carros:
                raise ValueError(
                    f"CAM_CARROS_ZONAS_INCONSISTENTES: tunel.n_zonas="
                    f"{self.tunel.n_zonas} ≠ carros.n_carros={self.carros.n_carros}. "
                    "En el túnel semicontinuo cada zona aloja un carro."
                )
        self._validar_producto()
        self._validar_coherencia()

    def _validar_producto(self) -> None:
        """Valida que el producto y sus modelos existan en el catálogo.

        Raises:
            ValueError: Si el producto_id no existe, o si no hay isoterma de
                sorción ni fallback escalar de X_eq para el producto.
        """
        p = self.carga_producto

        if p.producto_id not in catalogo.PRODUCTOS:
            ids = list(catalogo.PRODUCTOS.keys())
            raise ValueError(
                f"PROD_ID_NO_ENCONTRADO: '{p.producto_id}' no existe en el catálogo "
                f"de productos. Disponibles: {ids}."
            )

        datos = catalogo.PRODUCTOS[p.producto_id]

        # Isoterma: error duro solo si no hay parámetros Y no hay fallback escalar
        iso = datos.get("isoterma") or {}
        iso_entry = iso.get(p.modelo_isoterma) or {}
        params_iso = iso_entry.get("params") or {} if iso_entry else {}
        params_iso_vacios = not params_iso or all(
            v is None for v in params_iso.values() if not isinstance(v, (list, dict))
        )
        X_eq_fallback = (datos.get("propiedades_basicas") or {}).get("humedad_equilibrio_aire_seco")
        if params_iso_vacios and X_eq_fallback is None:
            raise ValueError(
                f"MOD_ISOTERMA_NO_DISPONIBLE: isoterma '{p.modelo_isoterma}' sin parámetros "
                f"para '{p.producto_id}' y sin fallback escalar en catálogo. "
                "Cargar parámetros o agregar 'humedad_equilibrio_aire_seco' en propiedades_basicas."
            )

    def _validar_coherencia(self) -> None:
        """Valida invariantes de coherencia cruzada entre secciones.

        Raises:
            ValueError: Si las bandejas no caben en la cámara, si el área de
                bandeja supera el área de planta, o si la carga por m² excede
                el límite de capa fina.
        """
        g = self.geometria
        b = self.bandejas
        p = self.carga_producto

        # Con carros (S41) la pila vertical es POR CARRO, no el total de la
        # cámara (los carros se distribuyen en planta, no apilados).
        if self.carros is not None:
            n_pila = self.carros.bandejas_por_carro
            etiqueta_pila = f"{n_pila} bandejas/carro"
        else:
            n_pila = b.n_bandejas
            etiqueta_pila = f"{n_pila} bandejas"
        alto_requerido = n_pila * b.separacion_entre_bandejas_m
        # Se compara contra el alto MENOR (la cara más baja del techo a un
        # agua) para que la pila quepa en todo punto de la cámara; con
        # pendiente_techo_deg=0 alto_menor_m == alto_m (comportamiento
        # histórico sin cambios).
        if alto_requerido > g.alto_menor_m:
            raise ValueError(
                f"COHE_BANDEJAS_NO_CABEN_EN_CAMARA: {etiqueta_pila} × "
                f"{b.separacion_entre_bandejas_m:.3f} m = {alto_requerido:.3f} m > "
                f"alto menor de cámara {g.alto_menor_m:.3f} m."
            )

        area_planta = g.area_planta_m2
        if b.area_bandeja_m2 > area_planta:
            raise ValueError(
                f"COHE_AREA_BANDEJA_EXCEDE_CAMARA: área bandeja {b.area_bandeja_m2:.3f} m² > "
                f"área planta {area_planta:.3f} m²."
            )

        # Encaje de los carros en fila a lo largo del túnel/cámara (si se
        # declaró la huella del carro).
        if self.carros is not None and self.carros.largo_carro_m is not None:
            largo_fila = self.carros.n_carros * self.carros.largo_carro_m
            if largo_fila > g.largo_m:
                raise ValueError(
                    f"COHE_CARROS_NO_CABEN_EN_LARGO: {self.carros.n_carros} carros × "
                    f"{self.carros.largo_carro_m:.2f} m = {largo_fila:.2f} m > "
                    f"largo cámara {g.largo_m:.2f} m."
                )
        if self.carros is not None and self.carros.ancho_carro_m is not None:
            if self.carros.ancho_carro_m > g.ancho_m:
                raise ValueError(
                    f"COHE_CARRO_EXCEDE_ANCHO: ancho del carro "
                    f"{self.carros.ancho_carro_m:.2f} m > ancho cámara {g.ancho_m:.2f} m."
                )

        carga_por_m2 = p.masa_total_kg / b.n_bandejas / b.area_bandeja_m2
        if carga_por_m2 > _CARGA_MAX_KG_M2:
            raise ValueError(
                f"COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA: carga {carga_por_m2:.1f} kg/m²/bandeja "
                f"> {_CARGA_MAX_KG_M2:.0f} kg/m² máximo para capa fina. "
                "Revisar masa total o número/área de bandejas."
            )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _modelos_disponibles(datos_producto: dict) -> list[str]:
    """Retorna los IDs de modelos de capa fina con parámetros calibrados."""
    cf = datos_producto.get("capa_fina") or {}
    disponibles = []
    for modelo_id, entry in cf.items():
        if entry is None:
            continue
        params = entry.get("params") or {}
        tiene_params = params and not all(
            v is None for v in params.values() if not isinstance(v, (list, dict))
        )
        if tiene_params:
            disponibles.append(modelo_id)
    return disponibles


# ---------------------------------------------------------------------------
# Advertencias estáticas (chequeos de diseño no bloqueantes)
# ---------------------------------------------------------------------------


def advertencias_camara(camara: Camara, latitud_deg: Optional[float] = None) -> list[Advertencia]:
    """Genera la lista de advertencias estáticas de diseño para la cámara.

    Las advertencias no bloquean la instanciación pero deben mostrarse al usuario
    antes de calcular. Complementan los errores duros de __post_init__.

    Args:
        camara: Objeto Camara completamente instanciado.
        latitud_deg: Latitud del emplazamiento [°], convención Duffie/estándar
            (negativa = hemisferio sur). ``None`` → se omiten las
            advertencias que requieren conocer el hemisferio (orientación
            de caras verticales translúcidas).

    Returns:
        Lista de Advertencia, posiblemente vacía si el diseño es correcto.
    """
    adv: list[Advertencia] = []
    g = camara.geometria
    c = camara.construccion
    b = camara.bandejas
    f = camara.flujo
    p = camara.carga_producto

    datos = catalogo.PRODUCTOS.get(p.producto_id) or {}
    props = datos.get("propiedades_basicas") or {}

    # --- GEO: relación de aspecto ---
    ratio = g.largo_m / g.ancho_m
    if ratio > _RATIO_LARGO_ANCHO_MAX or ratio < _RATIO_LARGO_ANCHO_MIN:
        adv.append(
            Advertencia(
                codigo="GEO_RELACION_ASPECTO_EXTREMA",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Relación largo/ancho = {ratio:.1f}. "
                    f"Rango recomendado: {_RATIO_LARGO_ANCHO_MIN}–{_RATIO_LARGO_ANCHO_MAX}. "
                    "Una cámara muy alargada o cuadrada puede generar flujo no uniforme."
                ),
                campo="geometria",
                sugerencia="Verificar uniformidad de flujo de aire sobre las bandejas.",
                contexto={"ratio_largo_ancho": round(ratio, 2)},
            )
        )

    # --- GEO: alto inusual ---
    if not (_ALTO_MIN_TIPICO_M <= g.alto_m <= _ALTO_MAX_TIPICO_M):
        adv.append(
            Advertencia(
                codigo="GEO_ALTO_INUSUAL",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Alto de cámara {g.alto_m:.2f} m fuera del rango típico "
                    f"({_ALTO_MIN_TIPICO_M}–{_ALTO_MAX_TIPICO_M} m) para secadores solares."
                ),
                campo="geometria.alto_m",
                sugerencia="Verificar el dimensionamiento vertical del secador.",
                contexto={"alto_m": g.alto_m},
            )
        )

    # --- GEO: pendiente de techo extrema ---
    if g.pendiente_techo_deg > 45.0:
        adv.append(
            Advertencia(
                codigo="CAM_PENDIENTE_TECHO_EXTREMA",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Pendiente del techo {g.pendiente_techo_deg:.1f}° > 45°. "
                    "Poco habitual en secadores de caja; verificar constructibilidad "
                    "y el alto menor resultante."
                ),
                campo="geometria.pendiente_techo_deg",
                sugerencia="Revisar que la pendiente sea constructivamente razonable.",
                contexto={"pendiente_techo_deg": g.pendiente_techo_deg},
            )
        )

    # --- CAM: cubierta definida pero sin ninguna cara activa (equivale a opaca) ---
    if c.cubierta_translucida_id is not None and not c.caras_translucidas_activas():
        adv.append(
            Advertencia(
                codigo="CAM_VIDRIADO_SIN_CARAS",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Cubierta translúcida '{c.cubierta_translucida_id}' definida pero "
                    "ninguna cara está marcada como translúcida: la cámara queda "
                    "térmicamente opaca (sin ganancia radiativa)."
                ),
                campo="construccion.caras_translucidas",
                sugerencia="Activar al menos una cara (techo, frente, atrás o lateral).",
                contexto={"cubierta_id": c.cubierta_translucida_id},
            )
        )

    # --- CAM: A_rad mayor que el área real del techo ---
    if (
        c.cubierta_translucida_id is not None
        and c.A_rad_m2 is not None
        and c.A_rad_m2 > g.A_techo_geom_m2
    ):
        adv.append(
            Advertencia(
                codigo="CAM_A_RAD_MAYOR_QUE_TECHO",
                severidad=Severidad.INFO,
                mensaje=(
                    f"A_rad_m2={c.A_rad_m2:.2f} m² > área real del techo "
                    f"({g.A_techo_geom_m2:.2f} m²). La cota física de la ganancia "
                    "radiativa (Q_rad ≤ potencia interceptada) deja de estar garantizada."
                ),
                campo="construccion.A_rad_m2",
                sugerencia="Verificar que A_rad_m2 no exceda el área geométrica del techo.",
                contexto={"A_rad_m2": c.A_rad_m2, "A_techo_geom_m2": g.A_techo_geom_m2},
            )
        )

    # --- CAM: cara vertical translúcida orientada al polo (desfavorable) ---
    if latitud_deg is not None and c.cubierta_translucida_id is not None:
        acimut_ecuador = 180.0 if latitud_deg < 0 else 0.0
        caras_geom = g.caras()
        for nombre in ("frente", "atras", "lateral_izq", "lateral_der"):
            if not getattr(c.caras_translucidas, nombre):
                continue
            diff = abs(
                _normalizar_acimut_duffie(caras_geom[nombre].acimut_duffie_deg - acimut_ecuador)
            )
            if diff > 135.0:
                adv.append(
                    Advertencia(
                        codigo="CAM_CARA_ORIENTACION_DESFAVORABLE",
                        severidad=Severidad.INFO,
                        mensaje=(
                            f"Cara '{nombre}' translúcida orientada hacia el polo "
                            f"(acimut {caras_geom[nombre].acimut_duffie_deg:.0f}°). "
                            "Recibirá poca radiación directa en la mayor parte del año."
                        ),
                        campo="geometria.acimut_camara_deg",
                        sugerencia="Reorientar la cámara o desactivar esa cara.",
                        contexto={
                            "cara": nombre,
                            "acimut_deg": caras_geom[nombre].acimut_duffie_deg,
                        },
                    )
                )

    # --- CONS: cubierta translúcida + producto fotosensible ---
    if c.cubierta_translucida_id is not None and datos.get("fotosensible", False):
        adv.append(
            Advertencia(
                codigo="CONS_CUBIERTA_TRANSLUCIDA_FOTOSENSIBLE",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Producto fotosensible '{p.producto_id}' con cubierta translúcida "
                    f"'{c.cubierta_translucida_id}'. La exposición a radiación UV puede "
                    "degradar pigmentos o aceites esenciales."
                ),
                campo="construccion.cubierta_translucida_id",
                sugerencia="Considerar cubierta opaca o filtro UV.",
                contexto={"producto_id": p.producto_id, "cubierta_id": c.cubierta_translucida_id},
            )
        )

    # --- CONS: muros sin aislación ---
    if c.U_muros_W_m2K > _U_MUROS_ALTO_W_M2K:
        adv.append(
            Advertencia(
                codigo="CONS_SIN_AISLACION_LATERAL",
                severidad=Severidad.INFO,
                mensaje=(
                    f"Muros laterales con U = {c.U_muros_W_m2K:.1f} W/(m²·K) > "
                    f"{_U_MUROS_ALTO_W_M2K} W/(m²·K). Baja resistencia térmica."
                ),
                campo="construccion.U_muros_W_m2K",
                sugerencia="Agregar aislación para mejorar la eficiencia térmica del secador.",
                contexto={"U_muros": c.U_muros_W_m2K},
            )
        )

    # --- BAND: espesor de capa grande ---
    if b.espesor_capa_m > _ESPESOR_MAX_BANDEJA_M:
        adv.append(
            Advertencia(
                codigo="BAND_ESPESOR_CAPA_GRANDE",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Espesor de capa {b.espesor_capa_m * 100:.1f} cm > "
                    f"{_ESPESOR_MAX_BANDEJA_M * 100:.0f} cm. "
                    "En lechos gruesos la resistencia interna a la difusión de humedad "
                    "crece y el secado real puede ser más lento que el estimado."
                ),
                campo="bandejas.espesor_capa_m",
                sugerencia="Reducir el espesor de capa para acelerar y uniformar el secado.",
                contexto={"espesor_m": b.espesor_capa_m, "limite_m": _ESPESOR_MAX_BANDEJA_M},
            )
        )

    # --- BAND: muchas bandejas ---
    if b.n_bandejas > _N_BANDEJAS_ALTO:
        adv.append(
            Advertencia(
                codigo="BAND_N_BANDEJAS_ELEVADO",
                severidad=Severidad.INFO,
                mensaje=f"{b.n_bandejas} bandejas. Verificar uniformidad de flujo entre bandejas.",
                campo="bandejas.n_bandejas",
                sugerencia="Con muchas bandejas en serie, la última recibe aire más húmedo.",
                contexto={"n_bandejas": b.n_bandejas, "limite": _N_BANDEJAS_ALTO},
            )
        )

    # --- BAND: malla sin especificar ---
    if b.tipo_malla is None:
        adv.append(
            Advertencia(
                codigo="BAND_MALLA_SIN_ESPECIFICAR",
                severidad=Severidad.INFO,
                mensaje="Tipo de malla de bandeja no especificado. Afecta la caída de presión.",
                campo="bandejas.tipo_malla",
                sugerencia="Especificar tipo de malla para estimación de pérdida de carga en motor.",
                contexto={},
            )
        )

    # --- FLUJO: velocidad superficial ---
    Q_vol = f.caudal_masico_kg_s / _RHO_AIRE_EST
    v_sup = Q_vol / (g.ancho_m * g.alto_m)
    if v_sup < _V_SUP_MIN_MS:
        adv.append(
            Advertencia(
                codigo="FLUJO_VELOCIDAD_SUPERFICIAL_BAJA",
                severidad=Severidad.WARNING,
                mensaje=(
                    f"Velocidad superficial de aire {v_sup:.2f} m/s < {_V_SUP_MIN_MS} m/s. "
                    "El coeficiente convectivo externo puede ser bajo. "
                    "El modelo de capa fina puede sobrestimar la tasa de secado."
                ),
                campo="flujo.caudal_masico_kg_s",
                sugerencia=(
                    f"Aumentar caudal de aire para superar {_V_SUP_MIN_MS} m/s "
                    "de velocidad superficial."
                ),
                contexto={"v_sup_m_s": round(v_sup, 3)},
            )
        )
    elif v_sup > _V_SUP_MAX_MS:
        adv.append(
            Advertencia(
                codigo="FLUJO_VELOCIDAD_SUPERFICIAL_ALTA",
                severidad=Severidad.INFO,
                mensaje=(
                    f"Velocidad superficial de aire {v_sup:.2f} m/s > {_V_SUP_MAX_MS} m/s. "
                    "Verificar compatibilidad del motor con la pérdida de presión."
                ),
                campo="flujo.caudal_masico_kg_s",
                sugerencia="Reducir caudal o aumentar la sección transversal de la cámara.",
                contexto={"v_sup_m_s": round(v_sup, 3)},
            )
        )

    # --- FLUJO: HR de entrada no especificada ---
    if f.HR_entrada_fraccion is None:
        adv.append(
            Advertencia(
                codigo="FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA",
                severidad=Severidad.WARNING,
                mensaje=(
                    "HR de entrada del aire no especificada. "
                    "El cálculo de X_eq usará el fallback escalar del catálogo."
                ),
                campo="flujo.HR_entrada_fraccion",
                sugerencia="Especificar HR de entrada para mayor precisión en el cálculo de X_eq.",
                contexto={},
            )
        )

    # --- PROD: isoterma fallback ---
    iso = datos.get("isoterma") or {}
    iso_entry = iso.get(p.modelo_isoterma) or {}
    params_iso = iso_entry.get("params") or {} if iso_entry else {}
    params_iso_validos = (
        params_iso.get("X_m") is not None
        and params_iso.get("C") is not None
        and params_iso.get("K") is not None
    )
    X_eq_fallback = props.get("humedad_equilibrio_aire_seco")
    if not params_iso_validos and X_eq_fallback is not None:
        adv.append(
            Advertencia(
                codigo="PROD_ISOTERMA_FALLBACK",
                severidad=Severidad.CRITICAL,
                mensaje=(
                    f"Sin isoterma GAB calibrada para '{p.producto_id}'. "
                    f"Se usará X_eq = {X_eq_fallback:.3f} kg/kg ms (fallback escalar). "
                    "La humedad de equilibrio real depende de la HR del aire."
                ),
                campo="carga_producto.modelo_isoterma",
                sugerencia="Cargar parámetros GAB en el catálogo para mayor precisión.",
                contexto={"X_eq_fallback": X_eq_fallback},
            )
        )

    # --- PROD: humedad objetivo inalcanzable (vs fallback estático) ---
    if X_eq_fallback is not None and p.humedad_objetivo_X < X_eq_fallback * 0.95:
        adv.append(
            Advertencia(
                codigo="PROD_HUMEDAD_OBJETIVO_INALCANZABLE",
                severidad=Severidad.CRITICAL,
                mensaje=(
                    f"Humedad objetivo {p.humedad_objetivo_X:.3f} kg/kg ms está por debajo "
                    f"del X_eq estimado ({X_eq_fallback:.3f} × 0.95 = {X_eq_fallback * 0.95:.3f}). "
                    "El secador puede no alcanzar ese objetivo bajo las condiciones de operación."
                ),
                campo="carga_producto.humedad_objetivo_X",
                sugerencia="Aumentar X_objetivo o mejorar las condiciones de operación del secador.",
                contexto={"X_eq_estimado": X_eq_fallback, "X_objetivo": p.humedad_objetivo_X},
            )
        )

    # --- INIO: carne sin isoterma ---
    categoria = datos.get("categoria", "").upper()
    if categoria == "CARNE" and not params_iso_validos:
        adv.append(
            Advertencia(
                codigo="INIO_PRODUCTO_CARNE_SIN_ISOTERMA",
                severidad=Severidad.CRITICAL,
                mensaje=(
                    f"ALERTA DE INOCUIDAD: '{p.producto_id}' (CARNE) sin isoterma calibrada. "
                    "No es posible verificar que a_w < 0.85 en el producto seco."
                ),
                campo="carga_producto.modelo_isoterma",
                sugerencia=(
                    "Cargar isoterma de carne con el nivel de sal equivalente al producto "
                    "antes de usar los resultados para toma de decisiones."
                ),
                contexto={"producto_id": p.producto_id, "categoria": "CARNE"},
            )
        )

    return adv


# =============================================================================
# Motor dinámico de cámara — dataclasses de entrada y salida
# =============================================================================


@dataclass
class ForzantesAire:
    """Serie temporal de condiciones del aire de entrada a la cámara de secado.

    Todos los arrays deben tener la misma longitud N.
    t_s[0] = 0.0 siempre (el motor integra desde t=0).

    Attributes:
        t_s: Tiempos [s]. t_s[0] = 0.0, monótonamente creciente.
        T_ent_K: Temperatura del aire de entrada [K].
        omega_ent: Humedad absoluta del aire de entrada [kg agua/kg aire seco].
        m_dot_aire_seco_kg_s: Caudal másico de aire seco [kg/s].
        T_amb_K: Temperatura ambiente exterior [K].
        v_viento_ms: Velocidad del viento [m/s].
        I_g_W_m2: Irradiancia global horizontal incidente sobre el techo de
            la cámara [W/m²]. ``None`` → rellena con ceros (cámara opaca o
            modo Constantes sin ciclo día/noche).
        I_g_POA_W_m2: Irradiancia sobre el plano del colector (POA, Plane
            of Array) [W/m²]. Es la que reciben los 4 solvers de colector
            para calcular el aporte radiativo absorbido. ``None`` → no se
            re-corre el colector con caudal natural en la pipeline
            transitoria (los solvers que dependan de POA caen al fallback
            que documenten — típicamente ``I_g_W_m2`` con aviso). Calcúlese
            en el armado de forzantes con ``calcular_POA_horizonte`` cuando
            haya DNI/GHI/DHI de NASA POWER + tilt/azimut del emplazamiento.
        Q_rad_aire_W: Potencia radiativa [W] que calienta el aire de la
            cámara directamente (radiación transmitida por caras
            translúcidas que no intercepta el producto y calienta
            paredes/piso internos — efecto invernadero de la caja). ``None``
            → rellena con ceros (comportamiento histórico: sin este término).
            Calcúlese con ``calculos/radiacion_camara.py::series_radiacion_camara``.
        Q_aux_max_W: Potencia térmica [W] que el auxiliar en modo
            **RESPALDO_INDEPENDIENTE** tiene disponible para inyectar en el nodo
            de aire de la cámara. Es un **techo**, no la potencia entregada: con
            set-point el motor modula por debajo (y da 0 si el sol ya lo supera).
            La serie viene **ya enmascarada** por disponibilidad —calendario de
            arranque, nocturnidad— porque esa lógica vive en
            ``calculos/auxiliar_calc.py`` y no debe duplicarse acá; valdrá 0 en
            las horas en que el auxiliar no opera. ``None`` → rellena con ceros
            (sin auxiliar, o auxiliar en SERIE_POSCOLECTOR, donde el aporte no
            entra acá sino como ΔT sobre ``T_ent_K``).
        t0_utc: Instante absoluto (UTC) que corresponde a ``t_s[0] == 0``. El
            motor integra en tiempo relativo; este campo es el **ancla** que
            permite reanclar sus salidas a timestamps reales — necesario para
            contrastarlas contra datos medidos (mejora 38, fase 4). ``None``
            cuando la serie es sintética o no tiene fecha asociada. Se tipa
            laxo (``pd.Timestamp``) para no meter pandas en ``core/camara``.
    """

    t_s: np.ndarray
    T_ent_K: np.ndarray
    omega_ent: np.ndarray
    m_dot_aire_seco_kg_s: np.ndarray
    T_amb_K: np.ndarray
    v_viento_ms: np.ndarray
    I_g_W_m2: Optional[np.ndarray] = None
    I_g_POA_W_m2: Optional[np.ndarray] = None
    Q_rad_aire_W: Optional[np.ndarray] = None
    Q_aux_max_W: Optional[np.ndarray] = None
    t0_utc: Optional[object] = None

    def __post_init__(self):
        n = len(self.t_s)
        if self.I_g_W_m2 is None:
            self.I_g_W_m2 = np.zeros(n, dtype=float)
        if self.Q_rad_aire_W is None:
            self.Q_rad_aire_W = np.zeros(n, dtype=float)
        if self.Q_aux_max_W is None:
            self.Q_aux_max_W = np.zeros(n, dtype=float)
        # I_g_POA queda None si no se provee (señal de "no calculado");
        # el balance global decide el fallback con aviso explícito.
        _campos_validar = [
            ("T_ent_K", self.T_ent_K),
            ("omega_ent", self.omega_ent),
            ("m_dot_aire_seco_kg_s", self.m_dot_aire_seco_kg_s),
            ("T_amb_K", self.T_amb_K),
            ("v_viento_ms", self.v_viento_ms),
            ("I_g_W_m2", self.I_g_W_m2),
            ("Q_rad_aire_W", self.Q_rad_aire_W),
            ("Q_aux_max_W", self.Q_aux_max_W),
        ]
        if self.I_g_POA_W_m2 is not None:
            _campos_validar.append(("I_g_POA_W_m2", self.I_g_POA_W_m2))
        for nombre, arr in _campos_validar:
            if len(arr) != n:
                raise ValueError(
                    f"FORZANTES_LONGITUD_INCONSISTENTE: {nombre} tiene {len(arr)} "
                    f"elementos, esperado {n}."
                )
        if float(self.t_s[0]) != 0.0:
            raise ValueError(f"FORZANTES_T_INICIAL: t_s[0] debe ser 0.0. Recibido: {self.t_s[0]}.")
