"""Tests del catálogo de parámetros barrideables.

Cubren unicidad de ids, filtrado por tipología/modo, coherencia de los
forzantes y reversibilidad de las conversiones UI↔SI declaradas.
"""

from __future__ import annotations

import pytest

from calculos.catalogo_parametros_barrido import (
    CATALOGO_PARAMETROS,
    obtener_parametro,
    parametros_para_tipologia,
)
from core.proyecto import Tipologia

_PATHS_QUE_REQUIEREN_COLECTOR = {
    "colector.unidad.largo_m",
    "colector.unidad.velocidad_diseno_ms",
    "colector.banco.n_serie",
    "colector.banco.n_paralelo",
}


def test_ids_unicos():
    ids = [p.id for p in CATALOGO_PARAMETROS]
    assert len(ids) == len(set(ids)), "Hay ids duplicados en el catálogo de parámetros."


def test_catalogo_tiene_18_parametros():
    """15 + pendiente_techo_camara + acimut_camara (S47) + area_bandeja (S55)."""
    assert len(CATALOGO_PARAMETROS) == 18


def test_modos_soportados_validos():
    validos = {"constantes", "transitorio", "anual"}
    for p in CATALOGO_PARAMETROS:
        assert p.modos_soportados, f"{p.id} no declara modos soportados."
        assert p.modos_soportados <= validos, f"{p.id} declara un modo desconocido."


def test_rango_coherente():
    for p in CATALOGO_PARAMETROS:
        assert p.valor_min_si < p.valor_max_si, f"{p.id}: min >= max."
        assert p.paso_sugerido_si > 0, f"{p.id}: paso no positivo."


def test_caja_excluye_parametros_de_colector():
    """En tipología CAJA no aparecen los parámetros que requieren colector."""
    paths = {p.path for p in parametros_para_tipologia(Tipologia.CAJA, "constantes")}
    assert paths.isdisjoint(_PATHS_QUE_REQUIEREN_COLECTOR)


def test_armario_incluye_parametros_de_colector():
    """En ARMARIO modo transitorio sí aparecen los parámetros de colector."""
    paths = {p.path for p in parametros_para_tipologia(Tipologia.ARMARIO, "transitorio")}
    assert _PATHS_QUE_REQUIEREN_COLECTOR <= paths


def test_forzantes_solo_en_constantes():
    """HR_camara y T_amb (forzantes) solo se ofrecen en modo Constantes."""
    forzantes = {p.id for p in CATALOGO_PARAMETROS if p.es_forzante}
    assert forzantes == {"HR_camara", "T_amb"}
    for fid in forzantes:
        p = obtener_parametro(fid)
        assert p.modos_soportados == frozenset({"constantes"})
    # Y no aparecen al filtrar por transitorio.
    ids_trans = {p.id for p in parametros_para_tipologia(Tipologia.ARMARIO, "transitorio")}
    assert forzantes.isdisjoint(ids_trans)


def test_pendiente_acimut_no_en_constantes():
    """Pendiente/acimut no tienen efecto en Constantes (POA es input) → excluidos."""
    ids_const = {p.id for p in parametros_para_tipologia(Tipologia.ARMARIO, "constantes")}
    assert "pendiente_colector" not in ids_const
    assert "acimut_colector" not in ids_const
    ids_trans = {p.id for p in parametros_para_tipologia(Tipologia.ARMARIO, "transitorio")}
    assert {"pendiente_colector", "acimut_colector"} <= ids_trans


def test_orientacion_camara_disponible_en_todas_las_tipologias():
    """pendiente_techo_camara/acimut_camara aplican a CAJA/ARMARIO/GRAN_ESCALA
    (la cámara tiene orientación propia, S47) y no en Constantes."""
    for tip in Tipologia:
        ids_trans = {p.id for p in parametros_para_tipologia(tip, "transitorio")}
        assert {"pendiente_techo_camara", "acimut_camara"} <= ids_trans
        ids_const = {p.id for p in parametros_para_tipologia(tip, "constantes")}
        assert "pendiente_techo_camara" not in ids_const
        assert "acimut_camara" not in ids_const


def test_obtener_parametro_desconocido_lanza_keyerror():
    with pytest.raises(KeyError, match="BARRIDO_PARAMETRO_DESCONOCIDO"):
        obtener_parametro("parametro_que_no_existe")


@pytest.mark.parametrize("parametro_id", ["acimut_colector", "acimut_camara", "HR_camara", "T_amb"])
def test_conversiones_ui_si_reversibles(parametro_id):
    """si_a_ui ∘ ui_a_si ≈ identidad en el interior del rango.

    Se muestrean puntos interiores (no los extremos): para el acimut, los
    extremos ±180° son el antípoda Norte donde la convención circular Duffie
    (−180, +180] es intencionalmente no reversible (−180 ≡ +180).
    """
    p = obtener_parametro(parametro_id)
    rango = p.valor_max_si - p.valor_min_si
    for frac in (0.25, 0.5, 0.75):
        valor_si = p.valor_min_si + frac * rango
        recuperado = p.ui_a_si(p.si_a_ui(valor_si))
        assert recuperado == pytest.approx(valor_si, abs=1e-9)


def test_forzante_helpers():
    p = obtener_parametro("HR_camara")
    assert p.es_forzante is True
    assert p.nombre_forzante == "HR_camara"
    p2 = obtener_parametro("caudal_masico")
    assert p2.es_forzante is False
    assert p2.nombre_forzante is None
