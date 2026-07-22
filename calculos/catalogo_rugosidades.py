"""Catálogo de rugosidades aerodinámicas del terreno para el perfil de viento.

La longitud de rugosidad z₀ caracteriza cuánto frena el terreno al viento cerca
del suelo y fija la forma del perfil logarítmico de capa límite
(``calculos/perfil_viento.py``). Es una propiedad **del sitio**, igual que el
albedo del suelo: la consumen tanto la ingesta de clima medido (para normalizar
el anemómetro del usuario a los 2 m del contrato de ``Clima``) como el extractor
eólico de la chimenea (para llevar el viento al tope).

Los valores siguen la clasificación de Davenport-Wieringa, estándar en ingeniería
de viento y adoptada por la Eurocódigo EN 1991-1-4 y la WMO. El módulo es puro
(sin Streamlit) y testeable.

Referencias
-----------
- Wieringa, J. (1992). "Updating the Davenport roughness classification".
  J. Wind Eng. Ind. Aerodyn. 41, 357-368.
- EN 1991-1-4 (Eurocódigo 1, acciones del viento), tabla de categorías de terreno.
"""

from __future__ import annotations

# Identificador estable → z₀ [m]. El id es lo que se persiste y lo que indexa las
# traducciones (`catalogo.rugosidad.<id>`); la etiqueta visible sale de la UI.
# Los ids se mantienen compatibles con el selector histórico de P6.
RUGOSIDADES_TERRENO: dict[str, float] = {
    "mar": 0.001,  # mar abierto, lagos, superficie lisa sin obstáculos
    "campo": 0.03,  # campo abierto, cultivo bajo, aeropuertos
    "rural": 0.05,  # rural medio, cultivos con setos dispersos (default)
    "suburbano": 0.20,  # suburbano, arbustos, arbolado disperso
    "urbano": 0.50,  # urbano denso, bosque, árboles altos
}

# Identificador de entrada manual del valor.
ID_PERSONALIZADO: str = "personalizado"

# Valor por defecto: rural medio. Coincide con `perfil_viento.Z0_DEFAULT_M`.
Z0_DEFAULT_M: float = RUGOSIDADES_TERRENO["rural"]

# Tolerancia para considerar que un float coincide con un valor del catálogo.
_TOL_Z0: float = 1e-6


def id_desde_z0(z0_m: float) -> str:
    """Mapea un valor de z₀ al identificador de terreno del catálogo más cercano.

    Permite que la UI refleje el estado guardado: si el valor almacenado coincide
    (dentro de tolerancia) con un terreno del catálogo, devuelve su id; si no,
    devuelve :data:`ID_PERSONALIZADO`.

    Args:
        z0_m: Longitud de rugosidad almacenada [m].

    Returns:
        Identificador de terreno del catálogo, o ``"personalizado"``.
    """
    for id_terreno, valor in RUGOSIDADES_TERRENO.items():
        if abs(valor - z0_m) <= _TOL_Z0:
            return id_terreno
    return ID_PERSONALIZADO


def z0_desde_id(id_terreno: str) -> float:
    """Devuelve el z₀ de un identificador del catálogo.

    Args:
        id_terreno: Identificador de terreno.

    Returns:
        Longitud de rugosidad [m].

    Raises:
        KeyError: si el identificador no está en el catálogo.
    """
    return RUGOSIDADES_TERRENO[id_terreno]
