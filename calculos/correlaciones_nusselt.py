"""Catálogo de correlaciones de Nusselt para colectores solares de aire.

Provee todas las correlaciones de transferencia de calor por convección
utilizadas en los 4 tipos de colector solar de aire. El módulo es
independiente del core y de la UI.

Organización
------------
- Dataclass ``CorrelacionNusselt``: metadatos de cada correlación (para UI).
- Funciones ``nusselt_*()``: implementación pura de cada correlación.
- Diccionarios ``CORRELACIONES_FORZADO`` y ``CORRELACIONES_NATURAL``: catálogos.
- Función ``calcular_h_int()``: punto de entrada principal. Selecciona
  automáticamente la correlación más apropiada o usa la indicada por el usuario.

Geometría de canal por tipo de colector
----------------------------------------
- Tipo 1: canal rectangular simple. Pared inferior caliente (absorbedor),
          pared superior fría (cubierta). Flujo por encima del absorbedor.
- Tipo 2: dos canales en paralelo (arriba y abajo del absorbedor).
          Ambas paredes calientes asimétricamente.
- Tipo 3: canal inferior. Pared inferior caliente (absorbedor), pared
          superior fría (cara inferior del absorbedor). Recinto estanco
          superior.
- Tipo 4: canal superior. Pared superior caliente (cara superior del
          absorbedor), pared inferior fría (cubierta). Recinto estanco
          inferior.

Lógica de selección automática (correlacion=None)
--------------------------------------------------
Flujo forzado:
  Re < 2300   → shah_london  (laminar, desarrollado)
               Si L/Dh < 50 → heaton  (laminar, en desarrollo térmico)
  2300–10000  → gnielinski   (transición)
  Re > 10000  → sparrow_liu  (turbulento, 1 pared caliente: Tipos 1, 3, 4)
               → dittus_boelter (turbulento, ambas paredes: Tipo 2)
               → cengel      (si L/Dh < 10, efectos de entrada pronunciados)

Flujo natural:
  → hollands_inclinada (único default; rango θ: 0°–75°)

Unidades
--------
Todas las funciones reciben y devuelven en SI:
  - Re, Ra, Pr: adimensionales
  - L_m, Dh_m: metros
  - theta_deg: grados
  - h_int: W/m²·K

Referencias
-----------
- Shah & London (1978). Laminar Flow Forced Convection in Ducts. Academic Press.
- Heaton, Reynolds & Kays (1964). Int. J. Heat Mass Transfer 7, 763-781.
- Gnielinski (1976). Int. Chem. Eng. 16, 359-368.
- Dittus & Boelter (1930). Univ. Calif. Publ. Eng. 2, 443.
- Sparrow & Liu (1979). Int. J. Heat Mass Transfer 22, 1433-1440.
- Cengel & Ghajar (2014). Heat and Mass Transfer, 5ª ed. McGraw-Hill.
- Hollands, Unny, Raithby & Konicek (1976). Solar Energy 18, 183-193.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Constantes físicas del módulo
# ---------------------------------------------------------------------------

K_AIRE: float = 0.02814    # W/m·K  — conductividad a 323 K
PR_AIRE: float = 0.703     # —       — número de Prandtl a 323 K

# Límites de régimen
RE_LAMINAR_MAX: float = 2300.0
RE_TURBULENTO_MIN: float = 10000.0

# Umbral de relación L/Dh para considerar efectos de entrada
L_DH_DESARROLLADO: float = 50.0   # L/Dh ≥ 50 → flujo térmicamente desarrollado
L_DH_ENTRADA_PRONUNCIADA: float = 10.0  # L/Dh < 10 → Cengel gana a Dittus-Boelter

# Tipo de pared caliente
TipoPared = Literal["una_pared", "dos_paredes"]


# ---------------------------------------------------------------------------
# Metadatos de correlaciones (para UI)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CorrelacionNusselt:
    """Metadatos de una correlación de Nusselt.

    Usada por la UI para poblar selectboxes y mostrar advertencias de
    aplicabilidad cuando el usuario elige una correlación fuera de rango.

    Attributes:
        nombre: Clave del catálogo (e.g. ``"gnielinski"``).
        nombre_display: Texto para selectbox en UI.
        modo: ``"forzado"`` o ``"natural"``.
        regimen: Régimen de flujo para el que fue desarrollada.
        Re_min: Límite inferior de Re (None si natural).
        Re_max: Límite superior de Re (None si natural).
        Ra_min: Límite inferior de Ra (None si forzado).
        Ra_max: Límite superior de Ra (None si forzado).
        pared: ``"una_pared"`` o ``"dos_paredes"`` (None si natural).
        referencia: Cita bibliográfica completa.
        notas: Advertencias de aplicabilidad.
    """

    nombre: str
    nombre_display: str
    modo: Literal["forzado", "natural"]
    regimen: str
    Re_min: float | None
    Re_max: float | None
    Ra_min: float | None
    Ra_max: float | None
    pared: TipoPared | None
    referencia: str
    notas: str


# ---------------------------------------------------------------------------
# Implementaciones de correlaciones — flujo forzado
# ---------------------------------------------------------------------------

def nusselt_shah_london(Re: float, Pr: float) -> float:
    """Nu para flujo laminar desarrollado en canal plano — Shah & London (1978).

    Condición de contorno: temperatura de pared uniforme en la pared caliente,
    pared opuesta adiabática. Aplicable cuando L/Dh ≥ 50.

    Nu = 5.385  (asimétrico: una pared isoterma, otra adiabática)

    Válido para Re < 2300, Pr > 0.

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re ≥ 2300 (flujo no laminar).

    References:
        Shah, R.K. & London, A.L. (1978). Laminar Flow Forced Convection
        in Ducts. Academic Press, New York. Tabla 42, caso H2.
    """
    if Re >= RE_LAMINAR_MAX:
        raise ValueError(
            f"Shah & London requiere Re < {RE_LAMINAR_MAX}. Re={Re:.0f}."
        )
    # Nu asimétrico (una pared caliente): 5.385
    # Nu simétrico (ambas paredes calientes): 8.235 — ver nusselt_shah_london_simetrico
    return 5.385


def nusselt_shah_london_simetrico(Re: float, Pr: float) -> float:
    """Nu para flujo laminar desarrollado, ambas paredes calientes — Shah & London (1978).

    Condición de contorno: flujo de calor uniforme en ambas paredes (H1).
    Aplicable al Tipo 2 donde el absorbedor calienta por arriba y por abajo.

    Nu = 8.235

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re ≥ 2300.

    References:
        Shah & London (1978). Tabla 42, caso H1.
    """
    if Re >= RE_LAMINAR_MAX:
        raise ValueError(
            f"Shah & London requiere Re < {RE_LAMINAR_MAX}. Re={Re:.0f}."
        )
    return 8.235


def nusselt_heaton(Re: float, Pr: float, L_m: float, Dh_m: float) -> float:
    """Nu para flujo laminar en desarrollo térmico — Heaton, Reynolds & Kays (1964).

    Aplica cuando la longitud L/Dh < 50, es decir cuando el perfil térmico
    no está completamente desarrollado a la salida del canal. El Nu efectivo
    resulta mayor que el valor de placa plana (Shah & London) por el efecto
    de entrada térmica.

    Expresión:
        Nu = 5.385 · (1 + C · (Dh/L)^n)
        con C = 0.0668, n = 2/3  (análisis de Graetz extendido a canal plano)

    Válido para Re < 2300, Pr > 0.5, L/Dh > 1.

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].
        L_m: Longitud del canal [m].
        Dh_m: Diámetro hidráulico [m].

    Returns:
        Número de Nusselt efectivo [adim].

    Raises:
        ValueError: Si Re ≥ 2300.

    References:
        Heaton, H.S., Reynolds, W.C. & Kays, W.M. (1964). Heat transfer in
        annular passages. Int. J. Heat Mass Transfer 7, 763-781.
    """
    if Re >= RE_LAMINAR_MAX:
        raise ValueError(
            f"Heaton requiere Re < {RE_LAMINAR_MAX}. Re={Re:.0f}."
        )
    if L_m <= 0 or Dh_m <= 0:
        raise ValueError("L_m y Dh_m deben ser positivos.")

    Gz = Re * Pr * Dh_m / L_m  # número de Graetz
    Nu_inf = 5.385              # límite desarrollado (una pared caliente)
    Nu = Nu_inf * (1.0 + 0.0668 * Gz ** (2.0 / 3.0))
    return Nu


def nusselt_gnielinski(Re: float, Pr: float) -> float:
    """Nu para flujo en transición y turbulento inicial — Gnielinski (1976).

    La correlación más precisa para 2300 ≤ Re ≤ 5×10⁶. Se aplica aquí
    en el rango de transición (2300–10000).

    Expresión:
        f  = (0.790·ln(Re) - 1.64)^{-2}          (Petukhov, factor de fricción)
        Nu = (f/8)·(Re-1000)·Pr
             / [1 + 12.7·√(f/8)·(Pr^{2/3} - 1)]

    Válido para 0.5 < Pr < 2000, Re > 3000 (se aplica desde 2300 con
    ligera imprecisión en el extremo inferior).

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re < 2300.

    References:
        Gnielinski, V. (1976). New equations for heat and mass transfer in
        turbulent pipe and channel flow. Int. Chem. Eng. 16, 359-368.
    """
    if Re < RE_LAMINAR_MAX:
        raise ValueError(
            f"Gnielinski requiere Re ≥ {RE_LAMINAR_MAX}. Re={Re:.0f}."
        )
    f = (0.790 * math.log(Re) - 1.64) ** (-2)
    Nu = (f / 8.0) * (Re - 1000.0) * Pr / (
        1.0 + 12.7 * math.sqrt(f / 8.0) * (Pr ** (2.0 / 3.0) - 1.0)
    )
    return max(Nu, 0.0)


def nusselt_dittus_boelter(Re: float, Pr: float) -> float:
    """Nu para flujo turbulento desarrollado — Dittus & Boelter (1930).

    Expresión clásica de referencia. Menos precisa que Gnielinski cerca de
    Re = 10000, pero muy usada en la literatura de colectores solares.

    Nu = 0.023 · Re^{0.8} · Pr^{0.4}  (exponente 0.4: fluido calentado)

    Válido para Re > 10000, 0.6 < Pr < 160, L/Dh > 10.

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re < 10000.

    References:
        Dittus, F.W. & Boelter, L.M.K. (1930). Heat transfer in automobile
        radiators of the tubular type. Univ. Calif. Publ. Eng. 2, 443.
    """
    if Re < RE_TURBULENTO_MIN:
        raise ValueError(
            f"Dittus-Boelter requiere Re ≥ {RE_TURBULENTO_MIN}. Re={Re:.0f}."
        )
    return 0.023 * Re ** 0.8 * Pr ** 0.4


def nusselt_sparrow_liu(Re: float, Pr: float) -> float:
    """Nu para canal con una pared caliente y una adiabática — Sparrow & Liu (1979).

    Desarrollada específicamente para colectores solares de aire donde el
    calor se suministra solo por una pared (el absorbedor) mientras la
    opuesta (cubierta o fondo) es esencialmente adiabática.

    Expresión:
        Nu = 0.0158 · Re^{0.8}   (Pr = 0.7, una pared caliente)

    Válido para Re > 10000. Para Re < 10000 se recomienda Gnielinski.

    Aplicabilidad por tipo de colector:
        Tipo 1: absorbedor (inferior) caliente, cubierta (superior) fría → ✓
        Tipo 2: ambas paredes calientes → usar Dittus-Boelter
        Tipo 3: absorbedor caliente, fondo del absorbedor frío → ✓
        Tipo 4: absorbedor caliente, cubierta fría → ✓

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim]. Se usa implícitamente (correlación
            desarrollada para Pr ≈ 0.7). Incluido por consistencia de firma.

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re < 10000.

    References:
        Sparrow, E.M. & Liu, C.H. (1979). Heat transfer, pressure drop and
        performance relationships for in-line, staggered, and continuous plate
        heat exchangers. Int. J. Heat Mass Transfer 22, 1433-1440.
    """
    if Re < RE_TURBULENTO_MIN:
        raise ValueError(
            f"Sparrow & Liu requiere Re ≥ {RE_TURBULENTO_MIN}. Re={Re:.0f}."
        )
    return 0.0158 * Re ** 0.8


def nusselt_cengel(Re: float, Pr: float, L_m: float, Dh_m: float) -> float:
    """Nu con corrección de longitud de entrada — Cengel & Ghajar (2014).

    Modifica Dittus-Boelter con un factor que amplifica Nu en la zona de
    entrada (L/Dh < 10), donde el perfil térmico no está desarrollado y
    el coeficiente convectivo local es significativamente mayor.

    Expresión:
        Nu = 0.023 · Re^{0.8} · Pr^{0.4} · [1 + (Dh/L)^{0.7}]

    Válido para Re > 10000, 0.6 < Pr < 160. Para L/Dh > 60 el factor
    corrector es < 3% y converge a Dittus-Boelter.

    Args:
        Re: Número de Reynolds [adim].
        Pr: Número de Prandtl [adim].
        L_m: Longitud del canal [m].
        Dh_m: Diámetro hidráulico [m].

    Returns:
        Número de Nusselt [adim].

    Raises:
        ValueError: Si Re < 10000 o L_m/Dh_m ≤ 0.

    References:
        Cengel, Y.A. & Ghajar, A.J. (2014). Heat and Mass Transfer, 5ª ed.
        McGraw-Hill. Ec. 8-70.
    """
    if Re < RE_TURBULENTO_MIN:
        raise ValueError(
            f"Cengel requiere Re ≥ {RE_TURBULENTO_MIN}. Re={Re:.0f}."
        )
    if L_m <= 0 or Dh_m <= 0:
        raise ValueError("L_m y Dh_m deben ser positivos.")

    Nu_db = 0.023 * Re ** 0.8 * Pr ** 0.4
    factor_entrada = 1.0 + (Dh_m / L_m) ** 0.7
    return Nu_db * factor_entrada


# ---------------------------------------------------------------------------
# Implementaciones de correlaciones — convección natural
# ---------------------------------------------------------------------------

def nusselt_hollands_inclinada(Ra: float, theta_deg: float) -> float:
    """Nu para convección natural en cavidad inclinada — Hollands et al. (1976).

    Correlación desarrollada para colectores solares planos inclinados
    entre 0° (horizontal) y 75° (casi vertical). El calentamiento viene
    de la pared inferior (absorbedor) hacia la superior (cubierta).

    Expresión:
        Nu = 1 + 1.44·[1 - 1708/(Ra·cosθ)]⁺·[1 - 1708·sin(1.8θ)^{1.6}/(Ra·cosθ)]
             + [(Ra·cosθ/5830)^{1/3} - 1]⁺

    donde [x]⁺ = max(0, x).

    Válido para Ra·cosθ > 0, θ ∈ [0°, 75°].
    Para Ra·cosθ < 1708: Nu = 1 (solo conducción — sin convección).

    Args:
        Ra: Número de Rayleigh basado en la separación del canal [adim].
        theta_deg: Ángulo de inclinación respecto a la horizontal [°].

    Returns:
        Número de Nusselt [adim]. Mínimo = 1.0 (conducción pura).

    References:
        Hollands, K.G.T., Unny, T.E., Raithby, G.D. & Konicek, L. (1976).
        Free convective heat transfer across inclined air layers. Solar
        Energy 18, 183-193.
    """
    if theta_deg < 0.0 or theta_deg > 90.0:
        raise ValueError(
            f"theta_deg debe estar en [0°, 90°]. Recibido: {theta_deg:.1f}°."
        )

    theta_rad = math.radians(theta_deg)
    cos_theta = math.cos(theta_rad)

    if cos_theta <= 0.0 or Ra <= 0.0:
        return 1.0  # solo conducción

    Ra_cos = Ra * cos_theta

    # Término 1: [1 - 1708/(Ra·cosθ)]⁺
    term1 = max(0.0, 1.0 - 1708.0 / Ra_cos)

    # Término 2: [1 - 1708·sin(1.8θ)^{1.6}/(Ra·cosθ)] — puede ser negativo,
    # entra multiplicado por term1 (que ya es ≥ 0)
    sin_factor = math.sin(1.8 * theta_rad) ** 1.6
    term2 = 1.0 - 1708.0 * sin_factor / Ra_cos

    # Término 3: [(Ra·cosθ/5830)^{1/3} - 1]⁺
    term3 = max(0.0, (Ra_cos / 5830.0) ** (1.0 / 3.0) - 1.0)

    Nu = 1.0 + 1.44 * term1 * term2 + term3
    return max(Nu, 1.0)  # Nu nunca puede ser menor que 1 (conducción pura)


# ---------------------------------------------------------------------------
# Catálogos de correlaciones
# ---------------------------------------------------------------------------

CORRELACIONES_FORZADO: dict[str, CorrelacionNusselt] = {
    "shah_london": CorrelacionNusselt(
        nombre="shah_london",
        nombre_display="Shah & London (1978) — laminar, una pared caliente",
        modo="forzado",
        regimen="laminar",
        Re_min=0.0,
        Re_max=2300.0,
        Ra_min=None,
        Ra_max=None,
        pared="una_pared",
        referencia="Shah, R.K. & London, A.L. (1978). Laminar Flow Forced "
                   "Convection in Ducts. Academic Press.",
        notas="Nu = 5.385. Válida para flujo térmicamente desarrollado "
              "(L/Dh ≥ 50). Una pared isoterma, otra adiabática. "
              "Para efectos de entrada usar Heaton.",
    ),
    "shah_london_simetrico": CorrelacionNusselt(
        nombre="shah_london_simetrico",
        nombre_display="Shah & London (1978) — laminar, dos paredes calientes",
        modo="forzado",
        regimen="laminar",
        Re_min=0.0,
        Re_max=2300.0,
        Ra_min=None,
        Ra_max=None,
        pared="dos_paredes",
        referencia="Shah, R.K. & London, A.L. (1978). Laminar Flow Forced "
                   "Convection in Ducts. Academic Press.",
        notas="Nu = 8.235. Aplicable al Tipo 2 donde ambas caras del "
              "absorbedor calientan el fluido. Flujo de calor uniforme "
              "en ambas paredes (condición H1).",
    ),
    "heaton": CorrelacionNusselt(
        nombre="heaton",
        nombre_display="Heaton, Reynolds & Kays (1964) — laminar, entrada térmica",
        modo="forzado",
        regimen="laminar",
        Re_min=0.0,
        Re_max=2300.0,
        Ra_min=None,
        Ra_max=None,
        pared="una_pared",
        referencia="Heaton, H.S., Reynolds, W.C. & Kays, W.M. (1964). "
                   "Int. J. Heat Mass Transfer 7, 763-781.",
        notas="Nu = 5.385·(1 + 0.0668·Gz^{2/3}). Recomendada cuando L/Dh < 50. "
              "Nu siempre mayor o igual que Shah & London. Válida Pr > 0.5.",
    ),
    "gnielinski": CorrelacionNusselt(
        nombre="gnielinski",
        nombre_display="Gnielinski (1976) — transición y turbulento inicial",
        modo="forzado",
        regimen="transicion",
        Re_min=2300.0,
        Re_max=10000.0,
        Ra_min=None,
        Ra_max=None,
        pared=None,
        referencia="Gnielinski, V. (1976). Int. Chem. Eng. 16, 359-368.",
        notas="La más precisa para Re 2300–10000. Error < 10% en rango de "
              "validez. Pr debe estar entre 0.5 y 2000.",
    ),
    "dittus_boelter": CorrelacionNusselt(
        nombre="dittus_boelter",
        nombre_display="Dittus-Boelter (1930) — turbulento clásico",
        modo="forzado",
        regimen="turbulento",
        Re_min=10000.0,
        Re_max=None,
        Ra_min=None,
        Ra_max=None,
        pared="dos_paredes",
        referencia="Dittus, F.W. & Boelter, L.M.K. (1930). "
                   "Univ. Calif. Publ. Eng. 2, 443.",
        notas="Nu = 0.023·Re^0.8·Pr^0.4. Clásica, error ~25% cerca de Re=10000. "
              "Usar Gnielinski en transición. Requiere L/Dh > 10.",
    ),
    "sparrow_liu": CorrelacionNusselt(
        nombre="sparrow_liu",
        nombre_display="Sparrow & Liu (1979) — turbulento, una pared caliente",
        modo="forzado",
        regimen="turbulento",
        Re_min=10000.0,
        Re_max=None,
        Ra_min=None,
        Ra_max=None,
        pared="una_pared",
        referencia="Sparrow, E.M. & Liu, C.H. (1979). "
                   "Int. J. Heat Mass Transfer 22, 1433-1440.",
        notas="Nu = 0.0158·Re^0.8. Desarrollada para colectores solares de "
              "aire con una pared caliente (absorbedor) y otra fría o adiabática. "
              "Default turbulento para Tipos 1, 3 y 4.",
    ),
    "cengel": CorrelacionNusselt(
        nombre="cengel",
        nombre_display="Cengel & Ghajar (2014) — turbulento, corrección entrada",
        modo="forzado",
        regimen="turbulento",
        Re_min=10000.0,
        Re_max=None,
        Ra_min=None,
        Ra_max=None,
        pared=None,
        referencia="Cengel, Y.A. & Ghajar, A.J. (2014). Heat and Mass Transfer, "
                   "5ª ed. McGraw-Hill. Ec. 8-70.",
        notas="Nu = 0.023·Re^0.8·Pr^0.4·[1+(Dh/L)^0.7]. Recomendada cuando "
              "L/Dh < 10. Para L/Dh > 60 converge a Dittus-Boelter (error < 3%).",
    ),
}

CORRELACIONES_NATURAL: dict[str, CorrelacionNusselt] = {
    "hollands": CorrelacionNusselt(
        nombre="hollands",
        nombre_display="Hollands et al. (1976) — cavidad inclinada",
        modo="natural",
        regimen="natural",
        Re_min=None,
        Re_max=None,
        Ra_min=0.0,
        Ra_max=1e8,
        pared=None,
        referencia="Hollands, K.G.T., Unny, T.E., Raithby, G.D. & Konicek, L. "
                   "(1976). Solar Energy 18, 183-193.",
        notas="Desarrollada específicamente para colectores solares. "
              "Válida para θ ∈ [0°, 75°]. Para θ > 75° la correlación "
              "sobreestima Nu. Incluye supresión de convección para Ra < 1708/cosθ.",
    ),
}


# ---------------------------------------------------------------------------
# Función principal — selección y cálculo
# ---------------------------------------------------------------------------

def calcular_h_int(
    Re: float,
    Pr: float,
    Dh_m: float,
    L_m: float,
    k_fluido_W_mK: float,
    pared: TipoPared,
    modo: Literal["forzado", "natural"],
    Ra: float = 0.0,
    theta_deg: float = 45.0,
    correlacion: str | None = None,
) -> tuple[float, float, str, str, list[str]]:
    """Calcula el coeficiente convectivo interno h_int [W/m²·K].

    Selecciona automáticamente la correlación más apropiada según el
    régimen de flujo y la geometría, o usa la indicada por el usuario.

    Args:
        Re: Número de Reynolds [adim]. Requerido para modo forzado.
        Pr: Número de Prandtl [adim].
        Dh_m: Diámetro hidráulico del canal [m].
        L_m: Longitud del canal [m].
        k_fluido_W_mK: Conductividad térmica del fluido [W/m·K].
        pared: ``"una_pared"`` (Tipos 1, 3, 4) o ``"dos_paredes"`` (Tipo 2).
        modo: ``"forzado"`` o ``"natural"``.
        Ra: Número de Rayleigh [adim]. Solo para modo natural.
        theta_deg: Inclinación del colector [°]. Solo para modo natural.
        correlacion: Nombre de la correlación a forzar (str del catálogo).
            Si None, se selecciona automáticamente.

    Returns:
        Tupla ``(h_int, Nu, nombre_correlacion, regimen, advertencias)`` donde:
        - h_int [W/m²·K]
        - Nu [adim]
        - nombre_correlacion: clave usada
        - regimen: ``"laminar"``, ``"transicion"``, ``"turbulento"`` o ``"natural"``
        - advertencias: lista de códigos COL_* si aplica

    Raises:
        ValueError: Si correlacion no está en el catálogo correspondiente,
            o si los parámetros son inconsistentes.
    """
    advertencias: list[str] = []
    L_Dh = L_m / Dh_m if Dh_m > 0 else float("inf")

    # -----------------------------------------------------------------------
    # Modo natural
    # -----------------------------------------------------------------------
    if modo == "natural":
        nombre = correlacion if correlacion else "hollands"
        if nombre not in CORRELACIONES_NATURAL:
            raise ValueError(
                f"Correlación '{nombre}' no disponible para convección natural. "
                f"Opciones: {list(CORRELACIONES_NATURAL.keys())}"
            )
        meta = CORRELACIONES_NATURAL[nombre]

        if theta_deg > 75.0:
            advertencias.append(
                f"COL_NUSSELT_THETA_FUERA_RANGO: θ={theta_deg:.1f}° > 75°. "
                "Hollands et al. sobreestima Nu en este rango. Resultados "
                "conservadores (h_int mayor de lo real)."
            )

        Nu = nusselt_hollands_inclinada(Ra, theta_deg)
        h_int = Nu * k_fluido_W_mK / Dh_m
        return h_int, Nu, nombre, "natural", advertencias

    # -----------------------------------------------------------------------
    # Modo forzado — selección automática
    # -----------------------------------------------------------------------
    if correlacion is None:
        nombre, Nu = _seleccion_automatica(Re, Pr, Dh_m, L_m, L_Dh, pared, advertencias)
    else:
        # Usuario eligió correlación específica — validar y advertir si está fuera de rango
        nombre, Nu = _correlacion_usuario(
            correlacion, Re, Pr, Dh_m, L_m, L_Dh, pared, advertencias
        )

    meta = CORRELACIONES_FORZADO[nombre]
    regimen = meta.regimen
    h_int = Nu * k_fluido_W_mK / Dh_m
    return h_int, Nu, nombre, regimen, advertencias


def _seleccion_automatica(
    Re: float,
    Pr: float,
    Dh_m: float,
    L_m: float,
    L_Dh: float,
    pared: TipoPared,
    advertencias: list[str],
) -> tuple[str, float]:
    """Lógica de selección automática de correlación para flujo forzado."""

    if Re < RE_LAMINAR_MAX:
        # --- Laminar ---
        if L_Dh < L_DH_DESARROLLADO:
            # Perfil térmico en desarrollo: Heaton es más preciso
            nombre = "heaton"
            Nu = nusselt_heaton(Re, Pr, L_m, Dh_m)
        else:
            # Flujo desarrollado: Shah & London según tipo de pared
            if pared == "dos_paredes":
                nombre = "shah_london_simetrico"
                Nu = nusselt_shah_london_simetrico(Re, Pr)
            else:
                nombre = "shah_london"
                Nu = nusselt_shah_london(Re, Pr)
        regimen_str = "laminar"
        advertencias.append(
            f"COL_FLUJO_LAMINAR: Re={Re:.0f} < {RE_LAMINAR_MAX:.0f}. "
            "Flujo laminar — eficiencia de transferencia de calor reducida. "
            "Considerar aumentar velocidad de diseño o reducir espaciado del canal."
        )

    elif Re <= RE_TURBULENTO_MIN:
        # --- Transición ---
        nombre = "gnielinski"
        Nu = nusselt_gnielinski(Re, Pr)

    else:
        # --- Turbulento ---
        if L_Dh < L_DH_ENTRADA_PRONUNCIADA:
            # Efectos de entrada pronunciados: Cengel da mejor resultado
            nombre = "cengel"
            Nu = nusselt_cengel(Re, Pr, L_m, Dh_m)
            advertencias.append(
                f"COL_ENTRADA_TERMICA: L/Dh={L_Dh:.1f} < {L_DH_ENTRADA_PRONUNCIADA:.0f}. "
                "Perfil térmico no desarrollado. Se usa Cengel con corrección "
                "de longitud de entrada."
            )
        elif pared == "una_pared":
            # Tipos 1, 3, 4: Sparrow & Liu es más específico para colectores
            nombre = "sparrow_liu"
            Nu = nusselt_sparrow_liu(Re, Pr)
        else:
            # Tipo 2: ambas paredes calientes
            nombre = "dittus_boelter"
            Nu = nusselt_dittus_boelter(Re, Pr)

    return nombre, Nu


def _correlacion_usuario(
    correlacion: str,
    Re: float,
    Pr: float,
    Dh_m: float,
    L_m: float,
    L_Dh: float,
    pared: TipoPared,
    advertencias: list[str],
) -> tuple[str, float]:
    """Evalúa la correlación elegida por el usuario, con advertencias si está fuera de rango."""

    if correlacion not in CORRELACIONES_FORZADO:
        raise ValueError(
            f"Correlación '{correlacion}' no disponible. "
            f"Opciones: {list(CORRELACIONES_FORZADO.keys())}"
        )

    meta = CORRELACIONES_FORZADO[correlacion]

    # Advertir si Re está fuera del rango de la correlación elegida
    if meta.Re_min is not None and Re < meta.Re_min:
        advertencias.append(
            f"COL_NUSSELT_FUERA_RANGO: correlación '{correlacion}' fue desarrollada "
            f"para Re ≥ {meta.Re_min:.0f}. Re actual = {Re:.0f}. "
            "Resultados pueden ser imprecisos."
        )
    if meta.Re_max is not None and Re > meta.Re_max:
        advertencias.append(
            f"COL_NUSSELT_FUERA_RANGO: correlación '{correlacion}' fue desarrollada "
            f"para Re ≤ {meta.Re_max:.0f}. Re actual = {Re:.0f}. "
            "Resultados pueden ser imprecisos."
        )

    # Advertir si la correlación es de una pared pero se usa en Tipo 2
    if meta.pared == "una_pared" and pared == "dos_paredes":
        advertencias.append(
            f"COL_NUSSELT_PARED_INCOMPATIBLE: '{correlacion}' fue desarrollada "
            "para una pared caliente. El colector Tipo 2 tiene dos paredes "
            "calientes. Se recomienda 'shah_london_simetrico' (laminar) o "
            "'dittus_boelter' (turbulento)."
        )

    # Evaluar la función correspondiente
    dispatch = {
        "shah_london": lambda: nusselt_shah_london(Re, Pr),
        "shah_london_simetrico": lambda: nusselt_shah_london_simetrico(Re, Pr),
        "heaton": lambda: nusselt_heaton(Re, Pr, L_m, Dh_m),
        "gnielinski": lambda: nusselt_gnielinski(Re, Pr),
        "dittus_boelter": lambda: nusselt_dittus_boelter(Re, Pr),
        "sparrow_liu": lambda: nusselt_sparrow_liu(Re, Pr),
        "cengel": lambda: nusselt_cengel(Re, Pr, L_m, Dh_m),
    }

    try:
        Nu = dispatch[correlacion]()
    except ValueError as exc:
        # La función interna ya lanzó ValueError por Re fuera de rango;
        # capturamos y relanzamos solo si no habíamos advertido ya
        raise ValueError(
            f"Error al evaluar '{correlacion}' con Re={Re:.0f}: {exc}"
        ) from exc

    return correlacion, Nu
