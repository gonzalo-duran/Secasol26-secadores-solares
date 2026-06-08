"""Catálogo de albedos de superficies usuales para la transposición POA.

El albedo (reflectancia solar de onda corta) de la superficie que rodea al
colector alimenta la componente reflejada del suelo en la POA
(``GHI·ρ·(1−cos β)/2``). Este módulo provee un catálogo curado de superficies
típicas con etiquetas en español, para poblar el desplegable de P3.

Los valores numéricos se toman de la tabla de referencia de pvlib
(``pvlib.albedo.SURFACE_ALBEDOS``) para mantener consistencia con la literatura
solar. El módulo es puro (sin Streamlit) y testeable.

Referencias
-----------
- pvlib.albedo.SURFACE_ALBEDOS (valores de referencia broadband).
"""

from __future__ import annotations

# Etiqueta en español → albedo [adim]. Valores de pvlib.albedo.SURFACE_ALBEDOS.
ALBEDOS_SUPERFICIE: dict[str, float] = {
    "Cemento / hormigón": 0.30,  # pvlib 'concrete'
    "Suelo desnudo": 0.17,  # pvlib 'soil'
    "Suelo con pasto": 0.20,  # pvlib 'grass'
    "Pasto fresco": 0.26,  # pvlib 'fresh grass'
    "Arena": 0.40,  # pvlib 'sand'
    "Urbano / asfalto": 0.18,  # pvlib 'urban'
    "Nieve": 0.65,  # pvlib 'snow'
}

# Etiqueta para entrada manual del valor.
ETIQUETA_PERSONALIZADO: str = "Personalizado"

# Tolerancia para considerar que un valor float coincide con uno del catálogo.
_TOL_ALBEDO: float = 1e-3


def etiqueta_desde_albedo(albedo: float) -> str:
    """Mapea un valor de albedo a la etiqueta de superficie conocida más cercana.

    Permite que la UI refleje el estado guardado: si el valor almacenado
    coincide (dentro de tolerancia) con una superficie del catálogo, devuelve
    su etiqueta; si no, devuelve ``ETIQUETA_PERSONALIZADO``.

    Args:
        albedo: Valor de albedo almacenado [adim].

    Returns:
        Etiqueta de superficie del catálogo, o ``"Personalizado"`` si no coincide.
    """
    for etiqueta, valor in ALBEDOS_SUPERFICIE.items():
        if abs(valor - albedo) <= _TOL_ALBEDO:
            return etiqueta
    return ETIQUETA_PERSONALIZADO
