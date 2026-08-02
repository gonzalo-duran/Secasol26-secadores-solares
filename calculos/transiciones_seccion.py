"""Pérdida de carga en los cambios de sección del circuito de aire.

Un secador empalma tramos de sección distinta: la salida del colector con la boca
de entrada de la cámara, y la boca de salida con la base de la chimenea. Cuando
las áreas no coinciden hay una **contracción** o una **expansión**, y ambas
disipan energía que hasta S62 el modelo no representaba: las bocas se trataban
con coeficientes fijos de manual, evaluados sobre su propia velocidad, sin mirar
qué había del otro lado.

El módulo es puro y lo consumen los dos circuitos —el lazo de convección natural,
donde la pérdida define el caudal de equilibrio, y el forzado, donde define la
presión que el ventilador tiene que entregar—.

Convención de referencia
------------------------
Los dos coeficientes se refieren a la **velocidad en la sección menor**, que es
la convención de Idelchik y la de ASHRAE. Referirlos a la mayor daría números
distintos para la misma pérdida física, así que el sentido del empalme
(``A_origen`` → ``A_destino``) solo decide si es contracción o expansión: la
velocidad de referencia siempre sale del área más chica.

Transición brusca vs gradual
----------------------------
Un escalón abrupto es el caso conservador y el más común en un secador armado en
taller (un plenum, una brida). Una transición desarrollada —un tronco de cono o
de pirámide entre las dos secciones— recupera buena parte de la presión, y por
eso se admite declarar su **longitud**: de ahí sale el ángulo, que es lo que
gobierna la pérdida.

    θ_total = 2 · atan( (r_mayor − r_menor) / L )

con radios equivalentes ``r = √(A/π)``. Longitud nula (o no declarada) ⇒ ángulo
de 180°, que devuelve exactamente el caso brusco.

Referencias:
    - Idelchik IE (1994). *Handbook of Hydraulic Resistance*, 3ª ed., diagramas
      de ensanchamiento y estrechamiento bruscos y cónicos.
    - Gibson AH (1912), correlación clásica del difusor cónico.
    - ASHRAE Handbook — Fundamentals (2017), cap. 21 "Duct Design".
"""

from __future__ import annotations

import math

# Coeficiente de la expansión brusca: Borda-Carnot, K = (1 − A_menor/A_mayor)².
# Es **exacto**, no una correlación: sale del balance de cantidad de movimiento
# sobre el volumen de control del chorro que se ensancha.
#
# Para la contracción brusca no hay solución cerrada equivalente (la pérdida
# ocurre en la re-expansión después de la vena contracta), así que se usa el
# ajuste de Idelchik.
_EXP_CONTRACCION_IDELCHIK: float = 0.75
_K_CONTRACCION_BRUSCA: float = 0.5

# Gibson para el difusor cónico: k(θ) = 2.61·sin(θ/2), acotado a 1. En θ = 180°
# (brusco) la cota lo lleva a 1 y se recupera Borda-Carnot exactamente, así que
# el caso brusco es el límite de la fórmula gradual y no una rama aparte.
_GIBSON_COEF: float = 2.61

# Ángulo por encima del cual una transición ya no recupera nada y se comporta
# como un escalón [°].
_ANGULO_BRUSCO_DEG: float = 180.0


def radio_equivalente_m(area_m2: float) -> float:
    """Radio del círculo de igual área [m]. 0 si el área no es positiva."""
    if area_m2 <= 0.0:
        return 0.0
    return math.sqrt(area_m2 / math.pi)


def angulo_transicion_deg(area_1_m2: float, area_2_m2: float, longitud_m: float) -> float:
    """Ángulo total del tronco de cono que une las dos secciones [°].

    Args:
        area_1_m2: Área de una de las secciones [m²].
        area_2_m2: Área de la otra [m²].
        longitud_m: Largo de la transición [m]. ``0`` o negativo ⇒ escalón.

    Returns:
        Ángulo total incluido [°]; 180 si la transición es brusca o si las áreas
        son iguales y no hay nada que desarrollar.
    """
    if longitud_m <= 0.0 or area_1_m2 <= 0.0 or area_2_m2 <= 0.0:
        return _ANGULO_BRUSCO_DEG
    dr = abs(radio_equivalente_m(area_1_m2) - radio_equivalente_m(area_2_m2))
    if dr == 0.0:
        return _ANGULO_BRUSCO_DEG  # sin cambio de sección el ángulo es irrelevante
    return 2.0 * math.degrees(math.atan(dr / longitud_m))


def coeficiente_transicion(
    area_origen_m2: float, area_destino_m2: float, longitud_m: float = 0.0
) -> float:
    """Coeficiente de pérdida ``K`` del empalme, referido a la velocidad menor.

    Contracción (``A_destino < A_origen``)::

        K = 0.5·(1 − A_destino/A_origen)^0.75 · sin(θ/2)

    Expansión (``A_destino > A_origen``)::

        K = min(1, 2.61·sin(θ/2)) · (1 − A_origen/A_destino)²

    El factor ``sin(θ/2)`` interpola entre la transición desarrollada y el
    escalón: vale 1 en θ = 180° —donde ambas expresiones recuperan sus formas
    bruscas, Idelchik y Borda-Carnot— y baja monótonamente al abrir el cono. Para
    la contracción es una interpolación, no un ajuste publicado: Idelchik da la
    contracción cónica en tablas por ángulo y este factor las reproduce en orden
    de magnitud siendo algo conservador (a 30° da ~26 % del valor brusco contra
    el ~10-20 % de la tabla). Se prefirió pecar de conservador.

    Args:
        area_origen_m2: Sección aguas arriba del empalme [m²].
        area_destino_m2: Sección aguas abajo [m²].
        longitud_m: Largo de la transición [m]. 0 ⇒ brusca.

    Returns:
        K adimensional, referido a ``½·ρ·v²`` con ``v`` en la sección **menor**.
        Cero si las áreas coinciden o alguna no es positiva.
    """
    if area_origen_m2 <= 0.0 or area_destino_m2 <= 0.0:
        return 0.0
    if area_origen_m2 == area_destino_m2:
        return 0.0

    theta = angulo_transicion_deg(area_origen_m2, area_destino_m2, longitud_m)
    factor_angulo = math.sin(math.radians(theta) / 2.0)

    if area_destino_m2 < area_origen_m2:  # contracción
        razon = area_destino_m2 / area_origen_m2
        return _K_CONTRACCION_BRUSCA * (1.0 - razon) ** _EXP_CONTRACCION_IDELCHIK * factor_angulo

    # expansión
    razon = area_origen_m2 / area_destino_m2
    k_gibson = min(1.0, _GIBSON_COEF * factor_angulo)
    return k_gibson * (1.0 - razon) ** 2


def delta_P_transicion_Pa(
    m_dot_kg_s: float,
    area_origen_m2: float,
    area_destino_m2: float,
    rho_kg_m3: float,
    longitud_m: float = 0.0,
) -> float:
    """Pérdida de carga del empalme entre dos secciones [Pa].

    ``ΔP = K · ½·ρ·v_menor²``, con ``v_menor = ṁ/(ρ·A_menor)``.

    Args:
        m_dot_kg_s: Caudal másico que atraviesa el empalme [kg/s].
        area_origen_m2: Sección aguas arriba [m²].
        area_destino_m2: Sección aguas abajo [m²].
        rho_kg_m3: Densidad del aire [kg/m³].
        longitud_m: Largo de la transición [m]. 0 ⇒ brusca (conservador).

    Returns:
        ΔP ≥ 0 [Pa]. Cero si las áreas coinciden, si alguna no es positiva, o si
        no hay caudal.
    """
    if m_dot_kg_s <= 0.0 or rho_kg_m3 <= 0.0:
        return 0.0
    K = coeficiente_transicion(area_origen_m2, area_destino_m2, longitud_m)
    if K == 0.0:
        return 0.0
    area_menor = min(area_origen_m2, area_destino_m2)
    v_menor = m_dot_kg_s / (rho_kg_m3 * area_menor)
    return K * 0.5 * rho_kg_m3 * v_menor**2
