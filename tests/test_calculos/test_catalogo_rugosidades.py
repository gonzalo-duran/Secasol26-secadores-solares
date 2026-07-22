"""
Tests del catálogo de rugosidades del terreno (calculos/catalogo_rugosidades.py).

z₀ es propiedad del sitio y vive en ``Emplazamiento.z0_terreno_m`` desde S57; este
catálogo puebla el desplegable de P2 y traduce el valor guardado a un id estable.
"""

from __future__ import annotations

import pytest

from calculos.catalogo_rugosidades import (
    ID_PERSONALIZADO,
    RUGOSIDADES_TERRENO,
    Z0_DEFAULT_M,
    id_desde_z0,
    z0_desde_id,
)
from calculos.perfil_viento import Z0_DEFAULT_M as Z0_PERFIL


def test_default_coincide_con_perfil_viento():
    """El default del catálogo y el del motor de perfil no pueden divergir."""
    assert Z0_DEFAULT_M == Z0_PERFIL == 0.05


def test_valores_crecen_con_la_rugosidad_del_terreno():
    valores = list(RUGOSIDADES_TERRENO.values())
    assert valores == sorted(valores)


def test_todos_los_valores_admiten_el_perfil_a_2m():
    """Todo z₀ del catálogo debe ser < 2 m para que el perfil esté definido."""
    for z0 in RUGOSIDADES_TERRENO.values():
        assert 0.0 < z0 < 2.0


class TestIdDesdeZ0:
    @pytest.mark.parametrize("id_terreno,z0", list(RUGOSIDADES_TERRENO.items()))
    def test_round_trip(self, id_terreno, z0):
        assert id_desde_z0(z0) == id_terreno
        assert z0_desde_id(id_terreno) == z0

    def test_valor_fuera_del_catalogo_es_personalizado(self):
        assert id_desde_z0(0.137) == ID_PERSONALIZADO

    def test_id_desconocido_lanza(self):
        with pytest.raises(KeyError):
            z0_desde_id("pantano")
