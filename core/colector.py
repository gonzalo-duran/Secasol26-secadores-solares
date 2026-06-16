"""
Dataclasses del sistema de colectores solares de aire tipo placa plana.

Jerarquía:
    Colector
    ├── ColectorUnidad  — describe un módulo físico (materiales + geometría + velocidad)
    └── BancoColectores — configuración en serie/paralelo

La chimenea solar es ahora un componente top-level (``Proyecto.chimenea``,
definido en ``core/chimenea.py``) porque es utilizable también en tipología
CAJA donde ``Proyecto.colector`` es None.

Flujo de aire en banco en paralelo:
    Q_total = n_paralelo × (v × ancho × espaciado)  [m³/s]
    El motor ve Q_total; cada rama del banco trabaja a velocidad_diseno_ms.

Almacenamiento de ángulos: Duffie (acimut 0° = Sur) en Emplazamiento.
La irradiancia en plano inclinado (POA) se calcula on-the-fly en calculos/
con pvlib.irradiance, no se guarda en Colector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core import catalogo
from core.advertencias import Advertencia, Severidad

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_V_MIN_MS: float = 0.3  # velocidad mínima recomendada [m/s]
_V_MAX_MS: float = 3.0  # velocidad máxima recomendada [m/s]
_ESP_MIN_M: float = 0.005  # espaciado mínimo absoluto [m]
_ESP_BAJO_M: float = 0.015  # espaciado bajo → advertencia presión [m]
_ESP_ALTO_M: float = 0.080  # espaciado alto → advertencia convección [m]
_LARGO_MIN_M: float = 0.5  # largo mínimo recomendado [m]
_LARGO_MAX_M: float = 10.0  # largo máximo recomendado [m]
_N_SERIE_MAX: int = 3  # series máximas antes de advertencia
_T_AISLANTE_CRITICA_K: float = 400.0  # T_max mínima aceptable para aislante [K]
_T_CUBIERTA_MIN_K: float = 423.0  # T_max mínima recomendada para cubierta [K]
_ESP_CUB_CUB_MIN_M: float = 0.010  # separación mínima entre cubiertas [m]
_ESP_CUB_CUB_MAX_M: float = 0.050  # separación máxima recomendada entre cubiertas [m]


# ---------------------------------------------------------------------------
# ColectorUnidad
# ---------------------------------------------------------------------------


@dataclass
class ColectorUnidad:
    """Un módulo de colector solar de aire tipo placa plana.

    El flujo de aire circula por el canal formado entre la cubierta transparente
    y la placa absorbedora. La velocidad de diseño determina el caudal por unidad
    y, junto con n_paralelo del banco, el caudal total que debe mover el motor.

    Attributes:
        ancho_m: Ancho interior del canal de flujo [m].
        largo_m: Largo del colector [m]. Variable de diseño para la optimización.
        espaciado_m: Separación cubierta-placa = altura del canal de flujo [m].
        n_cubiertas: Número de cubiertas transparentes (1 ó 2).
        espaciado_entre_cubiertas_m: Separación entre cubiertas cuando
            n_cubiertas=2 [m]. Define la cavidad de aire que actúa como
            resistencia adicional contra pérdidas superiores. Ignorado si
            n_cubiertas=1. Rango recomendado: 10–50 mm (Duffie & Beckman).
        velocidad_diseno_ms: Velocidad superficial del aire en el canal [m/s].
            Rango recomendado: 0.3–3.0 m/s.
        tipo_colector: Configuración del canal de flujo: 1=canal único sobre el
            absorbedor (absorbedor en el fondo), 2=absorbedor a media altura con
            ambos canales activos, 3=canal inferior activo (superior estanco),
            4=canal superior activo (inferior estanco).
        espaciado_inferior_m: Altura del canal inferior absorbedor–fondo [m].
            Solo relevante para Tipos 2, 3 y 4. Ignorado en Tipo 1.
        id_cubierta: Clave del material en cubiertas.yaml.
        espesor_cubierta_m: Espesor de CADA cubierta [m].
        id_placa: Clave del material en placas.yaml.
        espesor_placa_m: Espesor de la placa absorbedora [m].
        id_aislante: Clave del material en aislantes.yaml.
        espesor_aislante_m: Espesor del aislante lateral/posterior [m].
        id_fondo: Clave del material en fondos.yaml.
        espesor_fondo_m: Espesor del fondo/carcasa [m].
        k_cubierta_efectivo_W_mK: Override opcional de la conductividad efectiva
            de la cubierta [W/m·K]. Si es None se usa el ``conductividad_termica``
            del catálogo. Lo setea la UI para el policarbonato alveolar, cuyo k
            efectivo depende del espesor (4 mm→0.05, 6 mm→0.06, …); ver
            ``k_efectivo_por_espesor_mm`` en cubiertas.yaml.
    """

    ancho_m: float = 1.0
    largo_m: float = 2.0
    espaciado_m: float = 0.025
    n_cubiertas: int = 1
    espaciado_entre_cubiertas_m: float = 0.025
    velocidad_diseno_ms: float = 0.5

    tipo_colector: int = 1
    espaciado_inferior_m: float = 0.025  # canal absorbedor–fondo (Tipos 2, 3, 4)

    id_cubierta: str = "policarbonato_alveolar"
    espesor_cubierta_m: float = 0.004

    id_placa: str = "galvanizada_pintada_negro_mate"
    espesor_placa_m: float = 0.0006

    id_aislante: str = "lana_vidrio_media"
    espesor_aislante_m: float = 0.05

    id_fondo: str = "galvanizada_sin_pintura"
    espesor_fondo_m: float = 0.0006

    k_cubierta_efectivo_W_mK: float | None = None

    def __post_init__(self) -> None:
        # GEO_ — geometría del canal
        if self.ancho_m <= 0 or self.largo_m <= 0:
            raise ValueError(
                f"GEO_DIMENSIONES_NO_POSITIVAS: ancho={self.ancho_m:.3f} m, "
                f"largo={self.largo_m:.3f} m. Ambas dimensiones deben ser positivas."
            )
        if self.espaciado_m <= 0:
            raise ValueError(f"GEO_ESPACIADO_NO_POSITIVO: espaciado={self.espaciado_m:.4f} m ≤ 0.")
        if self.espaciado_m < _ESP_MIN_M:
            raise ValueError(
                f"GEO_ESPACIADO_MINIMO: espaciado={self.espaciado_m*1000:.1f} mm < "
                f"{_ESP_MIN_M*1000:.0f} mm mínimo. El canal es demasiado estrecho "
                "para un flujo de aire significativo."
            )
        if self.n_cubiertas not in (1, 2):
            raise ValueError(
                f"GEO_N_CUBIERTAS_INVALIDO: n_cubiertas={self.n_cubiertas}. "
                "Solo se soportan 1 ó 2 cubiertas transparentes."
            )
        if self.n_cubiertas == 2 and self.espaciado_entre_cubiertas_m <= 0:
            raise ValueError(
                f"GEO_ESP_CUB_CUB_NO_POSITIVO: espaciado_entre_cubiertas="
                f"{self.espaciado_entre_cubiertas_m:.4f} m ≤ 0. "
                "Con n_cubiertas=2 se requiere un espaciado positivo entre las cubiertas."
            )
        if self.velocidad_diseno_ms <= 0:
            raise ValueError(
                f"GEO_VELOCIDAD_NO_POSITIVA: velocidad={self.velocidad_diseno_ms:.3f} m/s ≤ 0."
            )
        if self.tipo_colector not in (1, 2, 3, 4):
            raise ValueError(
                f"COL_TIPO_INVALIDO: tipo_colector={self.tipo_colector}. "
                "Tipos válidos: 1, 2, 3 ó 4."
            )
        if self.espaciado_inferior_m < _ESP_MIN_M:
            raise ValueError(
                f"GEO_ESPACIADO_INF_MINIMO: espaciado_inferior={self.espaciado_inferior_m*1000:.1f} mm < "
                f"{_ESP_MIN_M*1000:.0f} mm mínimo."
            )

        # GEO_ — espesores
        espesores = {
            "cubierta": self.espesor_cubierta_m,
            "placa": self.espesor_placa_m,
            "aislante": self.espesor_aislante_m,
            "fondo": self.espesor_fondo_m,
        }
        no_positivos = [k for k, v in espesores.items() if v <= 0]
        if no_positivos:
            raise ValueError(
                f"GEO_ESPESORES_NO_POSITIVOS: espesores no positivos en: "
                f"{no_positivos}. Todos los espesores deben ser > 0."
            )

        # MAT_ — override de conductividad de cubierta (si se especifica)
        if self.k_cubierta_efectivo_W_mK is not None and self.k_cubierta_efectivo_W_mK <= 0:
            raise ValueError(
                f"MAT_K_CUBIERTA_NO_POSITIVA: k_cubierta_efectivo_W_mK="
                f"{self.k_cubierta_efectivo_W_mK} ≤ 0. Si se especifica debe ser > 0."
            )

        # MAT_ — existencia en catálogo
        if self.id_cubierta not in catalogo.CUBIERTAS:
            raise ValueError(
                f"MAT_CUBIERTA_NO_ENCONTRADA: '{self.id_cubierta}' no existe en "
                f"cubiertas.yaml. Disponibles: {list(catalogo.CUBIERTAS.keys())}."
            )
        if self.id_placa not in catalogo.PLACAS:
            raise ValueError(
                f"MAT_PLACA_NO_ENCONTRADA: '{self.id_placa}' no existe en "
                f"placas.yaml. Disponibles: {list(catalogo.PLACAS.keys())}."
            )
        if self.id_aislante not in catalogo.AISLANTES:
            raise ValueError(
                f"MAT_AISLANTE_NO_ENCONTRADO: '{self.id_aislante}' no existe en "
                f"aislantes.yaml. Disponibles: {list(catalogo.AISLANTES.keys())}."
            )
        if self.id_fondo not in catalogo.FONDOS:
            raise ValueError(
                f"MAT_FONDO_NO_ENCONTRADO: '{self.id_fondo}' no existe en "
                f"fondos.yaml. Disponibles: {list(catalogo.FONDOS.keys())}."
            )

    def seccion_canal_m2(self) -> float:
        """Área de la sección transversal del canal de flujo [m²].

        Returns:
            ancho_m × espaciado_m.
        """
        return self.ancho_m * self.espaciado_m

    def caudal_volumetrico_m3_s(self) -> float:
        """Caudal volumétrico de diseño por unidad [m³/s].

        Returns:
            v × ancho × espaciado.
        """
        return self.velocidad_diseno_ms * self.seccion_canal_m2()

    def area_captacion_m2(self) -> float:
        """Área de captación solar de una unidad [m²].

        Returns:
            ancho_m × largo_m.
        """
        return self.ancho_m * self.largo_m


# ---------------------------------------------------------------------------
# CanoMaestro (manifold del banco — gran escala)
# ---------------------------------------------------------------------------


@dataclass
class CanoMaestro:
    """Caño maestro (manifold) que colecta el aire de las ramas del banco.

    En un secador de gran escala (estilo túnel ADITAL) las ramas del banco no
    descargan directamente al ventilador: lo hacen a un **caño maestro** de
    sección creciente que suma los caudales y los conduce al ventilador. Trabaja
    en depresión (aguas arriba del ventilador). La sección crece para mantener
    la velocidad acotada a medida que se acumula el caudal, evitando un salto
    brusco de pérdida de carga.

    El caño no suele aislarse: pierde calor al ambiente por convección externa,
    pero también colecta radiación solar en su cara superior, por lo que la
    pérdida térmica neta del aire es pequeña (≈ 3 °C en ADITAL).

    La sección representativa (``ancho_m`` × ``alto_m``) es la del extremo del
    ventilador (caudal total). El modelo de prediseño calcula la fricción sobre
    ``largo_m`` a la velocidad del caudal total en esa sección, más las pérdidas
    singulares de las campanas de reducción (una por boca/rama) y las llaves
    mariposa de regulación.

    Attributes:
        largo_m: Longitud del caño maestro [m].
        ancho_m, alto_m: Sección transversal representativa (extremo del
            ventilador, caudal total) [m].
        rugosidad_m: Rugosidad absoluta de la pared [m] (chapa ≈ 1.5e-4).
        aislado: Si el caño está aislado térmicamente. ADITAL: False.
        espesor_aislante_m, k_aislante_W_mK: Aislación (solo si ``aislado``).
        aporte_solar: Si la cara superior colecta radiación (reduce la pérdida
            térmica neta). ADITAL: True (caño expuesto al sol).
        absortancia_solar: Absortancia solar de la cara superior [0–1].
        K_campana_reduccion: Coef. de pérdida singular de la campana de
            reducción de cada boca (rect → circular).
        K_llave_mariposa: Coef. de pérdida singular de la llave mariposa
            (abierta) de regulación de cada rama.
    """

    largo_m: float = 18.0
    ancho_m: float = 1.0
    alto_m: float = 0.5
    rugosidad_m: float = 1.5e-4
    aislado: bool = False
    espesor_aislante_m: float = 0.0
    k_aislante_W_mK: float = 0.04
    material_aislante: Optional[str] = None
    aporte_solar: bool = True
    absortancia_solar: float = 0.90
    cubierta: Optional[str] = None
    K_campana_reduccion: float = 0.5
    K_llave_mariposa: float = 0.3
    ancho_inicio_m: Optional[float] = None
    alto_inicio_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.largo_m <= 0:
            raise ValueError(f"CANO_LARGO_NO_POSITIVO: largo_m={self.largo_m:.3f} m ≤ 0.")
        if self.ancho_m <= 0 or self.alto_m <= 0:
            raise ValueError(
                f"CANO_SECCION_NO_POSITIVA: ancho={self.ancho_m:.3f}, alto={self.alto_m:.3f} m."
            )
        if self.rugosidad_m < 0:
            raise ValueError(f"CANO_RUGOSIDAD_NEGATIVA: rugosidad_m={self.rugosidad_m:.5f} < 0.")
        if self.aislado and self.espesor_aislante_m <= 0:
            raise ValueError(
                "CANO_AISLANTE_SIN_ESPESOR: aislado=True requiere espesor_aislante_m > 0."
            )
        if self.material_aislante is not None:
            if self.material_aislante not in catalogo.AISLANTES:
                raise ValueError(
                    f"CANO_AISLANTE_DESCONOCIDO: material_aislante="
                    f"{self.material_aislante!r} no está en aislantes.yaml. "
                    f"Disponibles: {list(catalogo.AISLANTES.keys())}."
                )
            # El material manda: k sale del catálogo (conductividad_termica).
            self.k_aislante_W_mK = float(
                catalogo.AISLANTES[self.material_aislante]["conductividad_termica"]
            )
        if not (0.0 <= self.absortancia_solar <= 1.0):
            raise ValueError(
                f"CANO_ABSORTANCIA_FUERA_RANGO: absortancia_solar="
                f"{self.absortancia_solar:.2f} ∉ [0, 1]."
            )
        if self.cubierta is not None and self.cubierta not in catalogo.CUBIERTAS:
            raise ValueError(
                f"CANO_CUBIERTA_DESCONOCIDA: cubierta={self.cubierta!r} no está "
                f"en cubiertas.yaml. Disponibles: {list(catalogo.CUBIERTAS.keys())}."
            )
        if (self.ancho_inicio_m is None) != (self.alto_inicio_m is None):
            raise ValueError(
                "CANO_SECCION_INICIO_INCOMPLETA: la sección variable requiere "
                "ancho_inicio_m y alto_inicio_m juntos (o ninguno)."
            )
        if self.ancho_inicio_m is not None and (
            self.ancho_inicio_m <= 0 or self.alto_inicio_m <= 0
        ):
            raise ValueError(
                f"CANO_SECCION_INICIO_NO_POSITIVA: ancho_inicio="
                f"{self.ancho_inicio_m:.3f}, alto_inicio={self.alto_inicio_m:.3f} m."
            )

    @property
    def area_seccion_m2(self) -> float:
        """Área de la sección transversal representativa (extremo del ventilador) [m²]."""
        return self.ancho_m * self.alto_m

    @property
    def seccion_variable(self) -> bool:
        """True si el caño tiene sección creciente configurada (S41)."""
        return self.ancho_inicio_m is not None

    @property
    def area_seccion_inicio_m2(self) -> float:
        """Área de la sección en el extremo lejano al ventilador [m²].

        Si la sección es constante, coincide con ``area_seccion_m2``.
        """
        if not self.seccion_variable:
            return self.area_seccion_m2
        return self.ancho_inicio_m * self.alto_inicio_m

    def seccion_en_fraccion(self, frac: float) -> tuple[float, float]:
        """(ancho, alto) interpolados linealmente a la fracción del largo [0–1].

        ``frac = 0`` es el extremo lejano (inicio del caño, primera boca);
        ``frac = 1`` es el extremo del ventilador (caudal total).
        """
        if not self.seccion_variable:
            return self.ancho_m, self.alto_m
        f = min(1.0, max(0.0, float(frac)))
        ancho = self.ancho_inicio_m + f * (self.ancho_m - self.ancho_inicio_m)
        alto = self.alto_inicio_m + f * (self.alto_m - self.alto_inicio_m)
        return ancho, alto

    @property
    def transmitancia_cubierta(self) -> float:
        """Transmitancia solar de la cubierta translúcida (1.0 si no hay) [-]."""
        if self.cubierta is None:
            return 1.0
        return float(catalogo.CUBIERTAS[self.cubierta]["transmitancia_solar"])

    @property
    def diametro_hidraulico_m(self) -> float:
        """Diámetro hidráulico de la sección rectangular [m]."""
        return 2.0 * self.ancho_m * self.alto_m / (self.ancho_m + self.alto_m)

    @property
    def area_externa_m2(self) -> float:
        """Área externa total (perímetro × largo) para pérdida convectiva [m²]."""
        return 2.0 * (self.ancho_m + self.alto_m) * self.largo_m

    @property
    def area_superior_m2(self) -> float:
        """Área de la cara superior expuesta al sol [m²]."""
        return self.ancho_m * self.largo_m


# ---------------------------------------------------------------------------
# BancoColectores
# ---------------------------------------------------------------------------


@dataclass
class BancoColectores:
    """Configuración de la batería de colectores.

    Los colectores en serie aumentan la longitud del camino del aire
    (mayor delta T, misma área por rama). Los colectores en paralelo
    aumentan el caudal total; el motor ve la suma de los caudales.

    Attributes:
        n_serie: Colectores en serie por rama (incrementa ΔT de salida).
        n_paralelo: Ramas paralelas (incrementa Q_total al motor y cámara).
        cano_maestro: Caño maestro (manifold) del banco para gran escala.
            ``None`` → conexión directa simple (ARMARIO / banco chico); el ΔP
            de distribución cae en la heurística de ductos del motor.
    """

    n_serie: int = 1
    n_paralelo: int = 1
    cano_maestro: CanoMaestro | None = None

    def __post_init__(self) -> None:
        if self.n_serie <= 0:
            raise ValueError(
                f"BANCO_N_SERIE_NO_POSITIVO: n_serie={self.n_serie}. "
                "El número de colectores en serie debe ser ≥ 1."
            )
        if self.n_paralelo <= 0:
            raise ValueError(
                f"BANCO_N_PARALELO_NO_POSITIVO: n_paralelo={self.n_paralelo}. "
                "El número de ramas en paralelo debe ser ≥ 1."
            )


# ---------------------------------------------------------------------------
# Colector (objeto raíz de la sección)
# ---------------------------------------------------------------------------


@dataclass
class Colector:
    """Sistema completo de colectores solares de aire.

    Almacenado en Proyecto.colector. Es None para tipología CAJA.

    Attributes:
        unidad: Descripción física de un colector unitario.
        banco: Configuración en serie/paralelo.
    """

    unidad: ColectorUnidad = field(default_factory=ColectorUnidad)
    banco: BancoColectores = field(default_factory=BancoColectores)

    def caudal_total_m3_s(self) -> float:
        """Caudal volumétrico total del banco de colectores [m³/s].

        El motor debe mover este caudal total.

        Returns:
            n_paralelo × caudal_volumétrico de una unidad.
        """
        return self.banco.n_paralelo * self.unidad.caudal_volumetrico_m3_s()

    def area_total_m2(self) -> float:
        """Área de captación total del banco [m²].

        Returns:
            n_serie × n_paralelo × área de una unidad.
        """
        return self.banco.n_serie * self.banco.n_paralelo * self.unidad.area_captacion_m2()

    def largo_camino_aire_m(self) -> float:
        """Longitud total del camino del aire a través del banco en serie [m].

        Returns:
            n_serie × largo_m de una unidad.
        """
        return self.banco.n_serie * self.unidad.largo_m


# ---------------------------------------------------------------------------
# Advertencias estáticas (chequeos de diseño no bloqueantes)
# ---------------------------------------------------------------------------


def advertencias_colector(colector: Colector) -> list[Advertencia]:
    """Genera la lista de advertencias estáticas de diseño para el colector.

    Las advertencias no bloquean la instanciación pero deben mostrarse al usuario
    antes de calcular. Complementan los errores duros de __post_init__.

    Args:
        colector: Objeto Colector completamente instanciado.

    Returns:
        Lista de Advertencia, posiblemente vacía si el diseño es correcto.
    """
    adv: list[Advertencia] = []
    u = colector.unidad
    b = colector.banco

    mat_cubierta = catalogo.CUBIERTAS[u.id_cubierta]
    mat_placa = catalogo.PLACAS[u.id_placa]
    mat_aislante = catalogo.AISLANTES[u.id_aislante]

    # --- GEO: largo ---
    if u.largo_m < _LARGO_MIN_M:
        adv.append(
            Advertencia(
                codigo="GEO_LARGO_PEQUENO",
                severidad=Severidad.INFO,
                mensaje=f"Largo del colector ({u.largo_m:.2f} m) menor al mínimo recomendado "
                f"({_LARGO_MIN_M} m). Puede no ser suficiente para elevar la temperatura del aire.",
                campo="largo_m",
                sugerencia="Incrementá el largo o revisá si la tipología es CAJA.",
                contexto={"largo_m": u.largo_m, "largo_min_m": _LARGO_MIN_M},
            )
        )
    elif u.largo_m > _LARGO_MAX_M:
        adv.append(
            Advertencia(
                codigo="GEO_LARGO_GRANDE",
                severidad=Severidad.WARNING,
                mensaje=f"Largo del colector ({u.largo_m:.1f} m) supera {_LARGO_MAX_M} m. "
                "Puede implicar problemas estructurales o de mantenimiento.",
                campo="largo_m",
                sugerencia="Considerá dividir en más unidades en serie o revisar el diseño estructural.",
                contexto={"largo_m": u.largo_m, "largo_max_m": _LARGO_MAX_M},
            )
        )

    # --- GEO: espaciado ---
    if _ESP_MIN_M <= u.espaciado_m < _ESP_BAJO_M:
        adv.append(
            Advertencia(
                codigo="GEO_ESPACIADO_PEQUENO",
                severidad=Severidad.WARNING,
                mensaje=f"Espaciado cubierta-placa ({u.espaciado_m*1000:.1f} mm) menor a "
                f"{_ESP_BAJO_M*1000:.0f} mm. Esperar alta pérdida de carga en el canal.",
                campo="espaciado_m",
                sugerencia="Aumentá el espaciado o reducí la velocidad de diseño para compensar.",
                contexto={"espaciado_mm": u.espaciado_m * 1000, "umbral_mm": _ESP_BAJO_M * 1000},
            )
        )
    elif u.espaciado_m > _ESP_ALTO_M:
        adv.append(
            Advertencia(
                codigo="GEO_ESPACIADO_GRANDE",
                severidad=Severidad.INFO,
                mensaje=f"Espaciado cubierta-placa ({u.espaciado_m*1000:.0f} mm) mayor a "
                f"{_ESP_ALTO_M*1000:.0f} mm. El coeficiente convectivo placa-aire será bajo.",
                campo="espaciado_m",
                sugerencia="Reducí el espaciado para mejorar la transferencia de calor convectiva.",
                contexto={"espaciado_mm": u.espaciado_m * 1000, "umbral_mm": _ESP_ALTO_M * 1000},
            )
        )

    # --- GEO: espaciado inferior (Tipos 2, 3, 4) ---
    if u.tipo_colector in (2, 3, 4):
        if _ESP_MIN_M <= u.espaciado_inferior_m < _ESP_BAJO_M:
            adv.append(
                Advertencia(
                    codigo="GEO_ESPACIADO_INF_PEQUENO",
                    severidad=Severidad.WARNING,
                    mensaje=f"Espaciado inferior absorbedor–fondo ({u.espaciado_inferior_m*1000:.1f} mm) "
                    f"menor a {_ESP_BAJO_M*1000:.0f} mm. Esperar alta pérdida de carga en el canal inferior.",
                    campo="espaciado_inferior_m",
                    sugerencia="Aumentá el espaciado inferior o reducí la velocidad de diseño.",
                    contexto={
                        "espaciado_inf_mm": u.espaciado_inferior_m * 1000,
                        "umbral_mm": _ESP_BAJO_M * 1000,
                    },
                )
            )
        elif u.espaciado_inferior_m > _ESP_ALTO_M:
            adv.append(
                Advertencia(
                    codigo="GEO_ESPACIADO_INF_GRANDE",
                    severidad=Severidad.INFO,
                    mensaje=f"Espaciado inferior absorbedor–fondo ({u.espaciado_inferior_m*1000:.0f} mm) "
                    f"mayor a {_ESP_ALTO_M*1000:.0f} mm. El coeficiente convectivo será bajo.",
                    campo="espaciado_inferior_m",
                    sugerencia="Reducí el espaciado inferior para mejorar la transferencia de calor convectiva.",
                    contexto={
                        "espaciado_inf_mm": u.espaciado_inferior_m * 1000,
                        "umbral_mm": _ESP_ALTO_M * 1000,
                    },
                )
            )

    # --- GEO: velocidad ---
    if u.velocidad_diseno_ms < _V_MIN_MS:
        adv.append(
            Advertencia(
                codigo="GEO_VELOCIDAD_BAJA",
                severidad=Severidad.WARNING,
                mensaje=f"Velocidad de diseño ({u.velocidad_diseno_ms:.2f} m/s) < {_V_MIN_MS} m/s. "
                "El régimen puede ser laminar con coeficientes de convección pobres.",
                campo="velocidad_diseno_ms",
                sugerencia=f"Usá velocidades entre {_V_MIN_MS} y {_V_MAX_MS} m/s para buen desempeño.",
                contexto={"velocidad_ms": u.velocidad_diseno_ms, "v_min_ms": _V_MIN_MS},
            )
        )
    elif u.velocidad_diseno_ms > _V_MAX_MS:
        adv.append(
            Advertencia(
                codigo="GEO_VELOCIDAD_ALTA",
                severidad=Severidad.WARNING,
                mensaje=f"Velocidad de diseño ({u.velocidad_diseno_ms:.2f} m/s) > {_V_MAX_MS} m/s. "
                "Alta pérdida de carga → motor sobredimensionado y ruido.",
                campo="velocidad_diseno_ms",
                sugerencia="Reducí la velocidad o aumentá la sección del canal (ancho × espaciado).",
                contexto={"velocidad_ms": u.velocidad_diseno_ms, "v_max_ms": _V_MAX_MS},
            )
        )

    # --- MAT: temperatura máxima de la cubierta ---
    t_max_cubierta = mat_cubierta.get("T_max_servicio", float("inf"))
    if t_max_cubierta < _T_CUBIERTA_MIN_K:
        adv.append(
            Advertencia(
                codigo="MAT_CUBIERTA_T_MAX_BAJA",
                severidad=Severidad.WARNING,
                mensaje=f"T_max_servicio de la cubierta '{u.id_cubierta}' = "
                f"{t_max_cubierta - 273.15:.0f} °C. "
                "Puede ser excedida bajo condiciones de estancamiento (sin flujo de aire).",
                campo="id_cubierta",
                sugerencia="Verificá que el material soporte la temperatura de estancamiento del colector.",
                contexto={"T_max_K": t_max_cubierta, "umbral_K": _T_CUBIERTA_MIN_K},
            )
        )

    # --- MAT: temperatura máxima del aislante (CRITICAL si muy baja) ---
    t_max_aislante = mat_aislante.get("T_max_servicio", float("inf"))
    if t_max_aislante < _T_AISLANTE_CRITICA_K:
        adv.append(
            Advertencia(
                codigo="MAT_AISLANTE_T_MAX_BAJA",
                severidad=Severidad.CRITICAL,
                mensaje=f"T_max_servicio del aislante '{u.id_aislante}' = "
                f"{t_max_aislante - 273.15:.0f} °C ({t_max_aislante:.0f} K). "
                f"Umbral mínimo recomendado: {_T_AISLANTE_CRITICA_K - 273.15:.0f} °C. "
                "El aislante puede degradarse o deformarse en contacto con la placa caliente.",
                campo="id_aislante",
                sugerencia="Usá lana mineral de roca o lana de vidrio de alta densidad en lugar de EPS o PUR.",
                contexto={
                    "T_max_aislante_K": t_max_aislante,
                    "umbral_K": _T_AISLANTE_CRITICA_K,
                    "material": u.id_aislante,
                },
            )
        )

    # --- COHE: aislante con T_max mucho menor que la placa ---
    t_max_placa = mat_placa.get("T_max_servicio", float("inf"))
    if t_max_aislante < t_max_placa * 0.75:
        adv.append(
            Advertencia(
                codigo="COHE_AISLANTE_T_MAX_INSUFICIENTE",
                severidad=Severidad.CRITICAL,
                mensaje=f"T_max del aislante ({t_max_aislante - 273.15:.0f} °C) es menos del 75% "
                f"de la T_max de la placa ({t_max_placa - 273.15:.0f} °C). "
                "El aislante no puede manejar las temperaturas que la placa puede generar.",
                campo="id_aislante",
                sugerencia="Seleccioná un aislante con T_max_servicio más alta, como lana mineral de roca.",
                contexto={
                    "T_max_aislante_K": t_max_aislante,
                    "T_max_placa_K": t_max_placa,
                    "ratio": round(t_max_aislante / t_max_placa, 2),
                },
            )
        )

    # --- GEO: espaciado entre cubiertas (solo si n_cubiertas == 2) ---
    if u.n_cubiertas == 2:
        if u.espaciado_entre_cubiertas_m < _ESP_CUB_CUB_MIN_M:
            adv.append(
                Advertencia(
                    codigo="GEO_ESP_CUB_CUB_PEQUENO",
                    severidad=Severidad.WARNING,
                    mensaje=f"Separación entre cubiertas ({u.espaciado_entre_cubiertas_m*1000:.1f} mm) "
                    f"< {_ESP_CUB_CUB_MIN_M*1000:.0f} mm. Cavidad muy estrecha: la "
                    "convección natural es despreciable pero la conducción de aire domina, "
                    "reduciendo el efecto de la doble cubierta.",
                    campo="espaciado_entre_cubiertas_m",
                    sugerencia="Aumentá la separación a 20–40 mm para minimizar pérdidas superiores.",
                    contexto={
                        "espaciado_mm": u.espaciado_entre_cubiertas_m * 1000,
                        "minimo_mm": _ESP_CUB_CUB_MIN_M * 1000,
                    },
                )
            )
        elif u.espaciado_entre_cubiertas_m > _ESP_CUB_CUB_MAX_M:
            adv.append(
                Advertencia(
                    codigo="GEO_ESP_CUB_CUB_GRANDE",
                    severidad=Severidad.INFO,
                    mensaje=f"Separación entre cubiertas ({u.espaciado_entre_cubiertas_m*1000:.0f} mm) "
                    f"> {_ESP_CUB_CUB_MAX_M*1000:.0f} mm. La convección natural en la cavidad "
                    "puede activarse y reducir el beneficio de la doble cubierta.",
                    campo="espaciado_entre_cubiertas_m",
                    sugerencia="Reducí la separación a 20–40 mm para mantener la cavidad en régimen "
                    "principalmente conductivo.",
                    contexto={
                        "espaciado_mm": u.espaciado_entre_cubiertas_m * 1000,
                        "maximo_mm": _ESP_CUB_CUB_MAX_M * 1000,
                    },
                )
            )

    # --- MAT: placa no selectiva con doble cubierta ---
    eps_placa = mat_placa.get("emisividad_ir", 1.0)
    if u.n_cubiertas == 2 and eps_placa > 0.5:
        adv.append(
            Advertencia(
                codigo="MAT_PLACA_NO_SELECTIVA_CON_DOBLE_CUBIERTA",
                severidad=Severidad.INFO,
                mensaje=f"Doble cubierta con placa no selectiva (ε_ir={eps_placa:.2f}). "
                "La doble cubierta reduce pérdidas por convección pero la alta emisividad "
                "de la placa limita la ganancia. El costo adicional puede no justificarse.",
                campo="n_cubiertas",
                sugerencia="Considerá placa selectiva (TiNOX o cromo negro) para aprovechar la doble cubierta.",
                contexto={"emisividad_placa": eps_placa, "n_cubiertas": u.n_cubiertas},
            )
        )

    # --- BANCO: n_serie alto ---
    if b.n_serie > _N_SERIE_MAX:
        adv.append(
            Advertencia(
                codigo="BANCO_SERIE_ALTO",
                severidad=Severidad.WARNING,
                mensaje=f"n_serie={b.n_serie} colectores en serie. Con más de {_N_SERIE_MAX} en serie "
                "la temperatura de salida puede ser muy alta y estresar los materiales aguas abajo.",
                campo="n_serie",
                sugerencia="Verificá que los materiales y las juntas soporten la temperatura de salida esperada.",
                contexto={"n_serie": b.n_serie, "n_serie_max_recomendado": _N_SERIE_MAX},
            )
        )

    return adv
