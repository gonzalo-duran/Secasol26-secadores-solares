"""
Dataclasses del sistema de colectores solares de aire tipo placa plana.

Jerarquía:
    Colector
    ├── ColectorUnidad  — describe un módulo físico (materiales + geometría + velocidad)
    ├── BancoColectores — configuración en serie/paralelo
    └── Optional[Chimenea] — chimenea solar para convección natural

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

from core.advertencias import Advertencia, Severidad
from core import catalogo

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_V_MIN_MS: float = 0.3          # velocidad mínima recomendada [m/s]
_V_MAX_MS: float = 3.0          # velocidad máxima recomendada [m/s]
_ESP_MIN_M: float = 0.005       # espaciado mínimo absoluto [m]
_ESP_BAJO_M: float = 0.015      # espaciado bajo → advertencia presión [m]
_ESP_ALTO_M: float = 0.080      # espaciado alto → advertencia convección [m]
_LARGO_MIN_M: float = 0.5       # largo mínimo recomendado [m]
_LARGO_MAX_M: float = 10.0      # largo máximo recomendado [m]
_N_SERIE_MAX: int = 3           # series máximas antes de advertencia
_CHIM_D_MIN_M: float = 0.10     # diámetro mínimo chimenea [m]
_CHIM_H_MIN_M: float = 1.0      # altura mínima chimenea [m]
_T_AISLANTE_CRITICA_K: float = 400.0  # T_max mínima aceptable para aislante [K]
_T_CUBIERTA_MIN_K: float = 423.0      # T_max mínima recomendada para cubierta [K]


# ---------------------------------------------------------------------------
# Chimenea
# ---------------------------------------------------------------------------


@dataclass
class Chimenea:
    """Chimenea solar para inducir convección natural.

    El material se selecciona del catálogo de fondos (materiales estructurales).
    El diámetro y la altura determinan el tiraje disponible.

    Attributes:
        diametro_m: Diámetro interno de la chimenea [m].
        altura_m: Altura de la chimenea sobre la cámara de secado [m].
        id_material: Identificador del material en fondos.yaml.
    """

    diametro_m: float = 0.20
    altura_m: float = 2.0
    id_material: str = "galvanizada_sin_pintura"

    def __post_init__(self) -> None:
        if self.diametro_m <= 0:
            raise ValueError(
                f"CHIM_DIAMETRO_NO_POSITIVO: diámetro {self.diametro_m:.4f} m ≤ 0. "
                "El diámetro interno de la chimenea debe ser positivo."
            )
        if self.altura_m <= 0:
            raise ValueError(
                f"CHIM_ALTURA_NO_POSITIVA: altura {self.altura_m:.2f} m ≤ 0. "
                "La altura de la chimenea debe ser positiva."
            )
        if self.id_material not in catalogo.FONDOS:
            ids = list(catalogo.FONDOS.keys())
            raise ValueError(
                f"CHIM_MATERIAL_NO_ENCONTRADO: '{self.id_material}' no existe en el "
                f"catálogo de materiales estructurales. Disponibles: {ids}."
            )


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
    """

    ancho_m: float = 1.0
    largo_m: float = 2.0
    espaciado_m: float = 0.025
    n_cubiertas: int = 1
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

    def __post_init__(self) -> None:
        # GEO_ — geometría del canal
        if self.ancho_m <= 0 or self.largo_m <= 0:
            raise ValueError(
                f"GEO_DIMENSIONES_NO_POSITIVAS: ancho={self.ancho_m:.3f} m, "
                f"largo={self.largo_m:.3f} m. Ambas dimensiones deben ser positivas."
            )
        if self.espaciado_m <= 0:
            raise ValueError(
                f"GEO_ESPACIADO_NO_POSITIVO: espaciado={self.espaciado_m:.4f} m ≤ 0."
            )
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
    """

    n_serie: int = 1
    n_paralelo: int = 1

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
        chimenea: Chimenea solar opcional (convección natural).
    """

    unidad: ColectorUnidad = field(default_factory=ColectorUnidad)
    banco: BancoColectores = field(default_factory=BancoColectores)
    chimenea: Optional[Chimenea] = None

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
        adv.append(Advertencia(
            codigo="GEO_LARGO_PEQUENO",
            severidad=Severidad.INFO,
            mensaje=f"Largo del colector ({u.largo_m:.2f} m) menor al mínimo recomendado "
                    f"({_LARGO_MIN_M} m). Puede no ser suficiente para elevar la temperatura del aire.",
            campo="largo_m",
            sugerencia="Incrementá el largo o revisá si la tipología es CAJA.",
            contexto={"largo_m": u.largo_m, "largo_min_m": _LARGO_MIN_M},
        ))
    elif u.largo_m > _LARGO_MAX_M:
        adv.append(Advertencia(
            codigo="GEO_LARGO_GRANDE",
            severidad=Severidad.WARNING,
            mensaje=f"Largo del colector ({u.largo_m:.1f} m) supera {_LARGO_MAX_M} m. "
                    "Puede implicar problemas estructurales o de mantenimiento.",
            campo="largo_m",
            sugerencia="Considerá dividir en más unidades en serie o revisar el diseño estructural.",
            contexto={"largo_m": u.largo_m, "largo_max_m": _LARGO_MAX_M},
        ))

    # --- GEO: espaciado ---
    if _ESP_MIN_M <= u.espaciado_m < _ESP_BAJO_M:
        adv.append(Advertencia(
            codigo="GEO_ESPACIADO_PEQUENO",
            severidad=Severidad.WARNING,
            mensaje=f"Espaciado cubierta-placa ({u.espaciado_m*1000:.1f} mm) menor a "
                    f"{_ESP_BAJO_M*1000:.0f} mm. Esperar alta pérdida de carga en el canal.",
            campo="espaciado_m",
            sugerencia="Aumentá el espaciado o reducí la velocidad de diseño para compensar.",
            contexto={"espaciado_mm": u.espaciado_m * 1000, "umbral_mm": _ESP_BAJO_M * 1000},
        ))
    elif u.espaciado_m > _ESP_ALTO_M:
        adv.append(Advertencia(
            codigo="GEO_ESPACIADO_GRANDE",
            severidad=Severidad.INFO,
            mensaje=f"Espaciado cubierta-placa ({u.espaciado_m*1000:.0f} mm) mayor a "
                    f"{_ESP_ALTO_M*1000:.0f} mm. El coeficiente convectivo placa-aire será bajo.",
            campo="espaciado_m",
            sugerencia="Reducí el espaciado para mejorar la transferencia de calor convectiva.",
            contexto={"espaciado_mm": u.espaciado_m * 1000, "umbral_mm": _ESP_ALTO_M * 1000},
        ))

    # --- GEO: espaciado inferior (Tipos 2, 3, 4) ---
    if u.tipo_colector in (2, 3, 4):
        if _ESP_MIN_M <= u.espaciado_inferior_m < _ESP_BAJO_M:
            adv.append(Advertencia(
                codigo="GEO_ESPACIADO_INF_PEQUENO",
                severidad=Severidad.WARNING,
                mensaje=f"Espaciado inferior absorbedor–fondo ({u.espaciado_inferior_m*1000:.1f} mm) "
                        f"menor a {_ESP_BAJO_M*1000:.0f} mm. Esperar alta pérdida de carga en el canal inferior.",
                campo="espaciado_inferior_m",
                sugerencia="Aumentá el espaciado inferior o reducí la velocidad de diseño.",
                contexto={"espaciado_inf_mm": u.espaciado_inferior_m * 1000, "umbral_mm": _ESP_BAJO_M * 1000},
            ))
        elif u.espaciado_inferior_m > _ESP_ALTO_M:
            adv.append(Advertencia(
                codigo="GEO_ESPACIADO_INF_GRANDE",
                severidad=Severidad.INFO,
                mensaje=f"Espaciado inferior absorbedor–fondo ({u.espaciado_inferior_m*1000:.0f} mm) "
                        f"mayor a {_ESP_ALTO_M*1000:.0f} mm. El coeficiente convectivo será bajo.",
                campo="espaciado_inferior_m",
                sugerencia="Reducí el espaciado inferior para mejorar la transferencia de calor convectiva.",
                contexto={"espaciado_inf_mm": u.espaciado_inferior_m * 1000, "umbral_mm": _ESP_ALTO_M * 1000},
            ))

    # --- GEO: velocidad ---
    if u.velocidad_diseno_ms < _V_MIN_MS:
        adv.append(Advertencia(
            codigo="GEO_VELOCIDAD_BAJA",
            severidad=Severidad.WARNING,
            mensaje=f"Velocidad de diseño ({u.velocidad_diseno_ms:.2f} m/s) < {_V_MIN_MS} m/s. "
                    "El régimen puede ser laminar con coeficientes de convección pobres.",
            campo="velocidad_diseno_ms",
            sugerencia=f"Usá velocidades entre {_V_MIN_MS} y {_V_MAX_MS} m/s para buen desempeño.",
            contexto={"velocidad_ms": u.velocidad_diseno_ms, "v_min_ms": _V_MIN_MS},
        ))
    elif u.velocidad_diseno_ms > _V_MAX_MS:
        adv.append(Advertencia(
            codigo="GEO_VELOCIDAD_ALTA",
            severidad=Severidad.WARNING,
            mensaje=f"Velocidad de diseño ({u.velocidad_diseno_ms:.2f} m/s) > {_V_MAX_MS} m/s. "
                    "Alta pérdida de carga → motor sobredimensionado y ruido.",
            campo="velocidad_diseno_ms",
            sugerencia=f"Reducí la velocidad o aumentá la sección del canal (ancho × espaciado).",
            contexto={"velocidad_ms": u.velocidad_diseno_ms, "v_max_ms": _V_MAX_MS},
        ))

    # --- MAT: temperatura máxima de la cubierta ---
    t_max_cubierta = mat_cubierta.get("T_max_servicio", float("inf"))
    if t_max_cubierta < _T_CUBIERTA_MIN_K:
        adv.append(Advertencia(
            codigo="MAT_CUBIERTA_T_MAX_BAJA",
            severidad=Severidad.WARNING,
            mensaje=f"T_max_servicio de la cubierta '{u.id_cubierta}' = "
                    f"{t_max_cubierta - 273.15:.0f} °C. "
                    "Puede ser excedida bajo condiciones de estancamiento (sin flujo de aire).",
            campo="id_cubierta",
            sugerencia="Verificá que el material soporte la temperatura de estancamiento del colector.",
            contexto={"T_max_K": t_max_cubierta, "umbral_K": _T_CUBIERTA_MIN_K},
        ))

    # --- MAT: temperatura máxima del aislante (CRITICAL si muy baja) ---
    t_max_aislante = mat_aislante.get("T_max_servicio", float("inf"))
    if t_max_aislante < _T_AISLANTE_CRITICA_K:
        adv.append(Advertencia(
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
        ))

    # --- COHE: aislante con T_max mucho menor que la placa ---
    t_max_placa = mat_placa.get("T_max_servicio", float("inf"))
    if t_max_aislante < t_max_placa * 0.75:
        adv.append(Advertencia(
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
        ))

    # --- MAT: placa no selectiva con doble cubierta ---
    eps_placa = mat_placa.get("emisividad_ir", 1.0)
    if u.n_cubiertas == 2 and eps_placa > 0.5:
        adv.append(Advertencia(
            codigo="MAT_PLACA_NO_SELECTIVA_CON_DOBLE_CUBIERTA",
            severidad=Severidad.INFO,
            mensaje=f"Doble cubierta con placa no selectiva (ε_ir={eps_placa:.2f}). "
                    "La doble cubierta reduce pérdidas por convección pero la alta emisividad "
                    "de la placa limita la ganancia. El costo adicional puede no justificarse.",
            campo="n_cubiertas",
            sugerencia="Considerá placa selectiva (TiNOX o cromo negro) para aprovechar la doble cubierta.",
            contexto={"emisividad_placa": eps_placa, "n_cubiertas": u.n_cubiertas},
        ))

    # --- BANCO: n_serie alto ---
    if b.n_serie > _N_SERIE_MAX:
        adv.append(Advertencia(
            codigo="BANCO_SERIE_ALTO",
            severidad=Severidad.WARNING,
            mensaje=f"n_serie={b.n_serie} colectores en serie. Con más de {_N_SERIE_MAX} en serie "
                    "la temperatura de salida puede ser muy alta y estresar los materiales aguas abajo.",
            campo="n_serie",
            sugerencia="Verificá que los materiales y las juntas soporten la temperatura de salida esperada.",
            contexto={"n_serie": b.n_serie, "n_serie_max_recomendado": _N_SERIE_MAX},
        ))

    # --- CHIM: dimensiones de chimenea ---
    if colector.chimenea is not None:
        ch = colector.chimenea
        if ch.diametro_m < _CHIM_D_MIN_M:
            adv.append(Advertencia(
                codigo="CHIM_DIAMETRO_PEQUENO",
                severidad=Severidad.WARNING,
                mensaje=f"Diámetro de chimenea ({ch.diametro_m*100:.0f} cm) < "
                        f"{_CHIM_D_MIN_M*100:.0f} cm. Puede ser insuficiente para el tiraje necesario.",
                campo="chimenea.diametro_m",
                sugerencia=f"Usá un diámetro ≥ {_CHIM_D_MIN_M*100:.0f} cm para garantizar tiraje efectivo.",
                contexto={"diametro_m": ch.diametro_m, "minimo_m": _CHIM_D_MIN_M},
            ))
        if ch.altura_m < _CHIM_H_MIN_M:
            adv.append(Advertencia(
                codigo="CHIM_ALTURA_PEQUENA",
                severidad=Severidad.WARNING,
                mensaje=f"Altura de chimenea ({ch.altura_m:.1f} m) < {_CHIM_H_MIN_M} m. "
                        "El tiraje natural puede ser insuficiente para mover el aire.",
                campo="chimenea.altura_m",
                sugerencia=f"Aumentá la altura a ≥ {_CHIM_H_MIN_M} m para asegurar convección natural.",
                contexto={"altura_m": ch.altura_m, "minima_m": _CHIM_H_MIN_M},
            ))

    return adv
