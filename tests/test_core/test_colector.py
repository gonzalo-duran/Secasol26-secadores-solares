"""
Tests de validación de ColectorUnidad, BancoColectores y Chimenea.

Un test por error duro, siguiendo la convención del proyecto.
Los tests de advertencias cubren los casos principales de advertencias_colector().
"""

from __future__ import annotations

import pytest

from core.advertencias import Severidad
from core.chimenea import Chimenea, advertencias_chimenea
from core.colector import (
    BancoColectores,
    Colector,
    ColectorUnidad,
    advertencias_colector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unidad_valida(**kwargs) -> ColectorUnidad:
    """Devuelve un ColectorUnidad válido con overrides opcionales."""
    defaults = dict(
        ancho_m=1.0,
        largo_m=2.0,
        espaciado_m=0.025,
        n_cubiertas=1,
        velocidad_diseno_ms=0.5,
        id_cubierta="vidrio_comun",
        espesor_cubierta_m=0.004,
        id_placa="galvanizada_pintada_negro_mate",
        espesor_placa_m=0.0006,
        id_aislante="lana_vidrio_media",
        espesor_aislante_m=0.05,
        id_fondo="galvanizada_sin_pintura",
        espesor_fondo_m=0.0006,
    )
    defaults.update(kwargs)
    return ColectorUnidad(**defaults)


def _colector_valido(**kwargs_unidad) -> Colector:
    return Colector(unidad=_unidad_valida(**kwargs_unidad))


# ---------------------------------------------------------------------------
# ColectorUnidad — instanciación válida
# ---------------------------------------------------------------------------


def test_colector_unidad_defaults_validos():
    """Los valores por defecto de ColectorUnidad deben instanciarse sin error."""
    u = ColectorUnidad()
    assert u.ancho_m == 1.0
    assert u.n_cubiertas == 1


def test_colector_valido_completo():
    """Colector completo con banco debe instanciarse sin error."""
    c = Colector(
        unidad=_unidad_valida(),
        banco=BancoColectores(n_serie=2, n_paralelo=3),
    )
    assert c.banco.n_serie == 2


# ---------------------------------------------------------------------------
# ColectorUnidad — errores duros GEO_
# ---------------------------------------------------------------------------


def test_geo_dimensiones_no_positivas_ancho():
    """Ancho ≤ 0 debe lanzar GEO_DIMENSIONES_NO_POSITIVAS."""
    with pytest.raises(ValueError, match="GEO_DIMENSIONES_NO_POSITIVAS"):
        _unidad_valida(ancho_m=0.0)


def test_geo_dimensiones_no_positivas_largo():
    """Largo ≤ 0 debe lanzar GEO_DIMENSIONES_NO_POSITIVAS."""
    with pytest.raises(ValueError, match="GEO_DIMENSIONES_NO_POSITIVAS"):
        _unidad_valida(largo_m=-1.0)


def test_geo_espaciado_no_positivo():
    """Espaciado ≤ 0 debe lanzar GEO_ESPACIADO_NO_POSITIVO."""
    with pytest.raises(ValueError, match="GEO_ESPACIADO_NO_POSITIVO"):
        _unidad_valida(espaciado_m=0.0)


def test_geo_espaciado_minimo():
    """Espaciado < 5 mm debe lanzar GEO_ESPACIADO_MINIMO."""
    with pytest.raises(ValueError, match="GEO_ESPACIADO_MINIMO"):
        _unidad_valida(espaciado_m=0.004)


def test_geo_n_cubiertas_invalido_cero():
    """n_cubiertas=0 debe lanzar GEO_N_CUBIERTAS_INVALIDO."""
    with pytest.raises(ValueError, match="GEO_N_CUBIERTAS_INVALIDO"):
        _unidad_valida(n_cubiertas=0)


def test_geo_n_cubiertas_invalido_tres():
    """n_cubiertas=3 debe lanzar GEO_N_CUBIERTAS_INVALIDO."""
    with pytest.raises(ValueError, match="GEO_N_CUBIERTAS_INVALIDO"):
        _unidad_valida(n_cubiertas=3)


def test_geo_espesores_no_positivos_cubierta():
    """Espesor de cubierta ≤ 0 debe lanzar GEO_ESPESORES_NO_POSITIVOS."""
    with pytest.raises(ValueError, match="GEO_ESPESORES_NO_POSITIVOS"):
        _unidad_valida(espesor_cubierta_m=0.0)


def test_geo_espesores_no_positivos_placa():
    """Espesor de placa ≤ 0 debe lanzar GEO_ESPESORES_NO_POSITIVOS."""
    with pytest.raises(ValueError, match="GEO_ESPESORES_NO_POSITIVOS"):
        _unidad_valida(espesor_placa_m=-0.001)


def test_geo_espesores_no_positivos_aislante():
    """Espesor de aislante ≤ 0 debe lanzar GEO_ESPESORES_NO_POSITIVOS."""
    with pytest.raises(ValueError, match="GEO_ESPESORES_NO_POSITIVOS"):
        _unidad_valida(espesor_aislante_m=0.0)


def test_geo_velocidad_no_positiva():
    """Velocidad ≤ 0 debe lanzar GEO_VELOCIDAD_NO_POSITIVA."""
    with pytest.raises(ValueError, match="GEO_VELOCIDAD_NO_POSITIVA"):
        _unidad_valida(velocidad_diseno_ms=0.0)


# ---------------------------------------------------------------------------
# ColectorUnidad — errores duros MAT_
# ---------------------------------------------------------------------------


def test_mat_cubierta_no_encontrada():
    """ID de cubierta inexistente debe lanzar MAT_CUBIERTA_NO_ENCONTRADA."""
    with pytest.raises(ValueError, match="MAT_CUBIERTA_NO_ENCONTRADA"):
        _unidad_valida(id_cubierta="cubierta_inexistente_xyz")


def test_mat_placa_no_encontrada():
    """ID de placa inexistente debe lanzar MAT_PLACA_NO_ENCONTRADA."""
    with pytest.raises(ValueError, match="MAT_PLACA_NO_ENCONTRADA"):
        _unidad_valida(id_placa="placa_inexistente_xyz")


def test_mat_aislante_no_encontrado():
    """ID de aislante inexistente debe lanzar MAT_AISLANTE_NO_ENCONTRADO."""
    with pytest.raises(ValueError, match="MAT_AISLANTE_NO_ENCONTRADO"):
        _unidad_valida(id_aislante="aislante_inexistente_xyz")


def test_mat_fondo_no_encontrado():
    """ID de fondo inexistente debe lanzar MAT_FONDO_NO_ENCONTRADO."""
    with pytest.raises(ValueError, match="MAT_FONDO_NO_ENCONTRADO"):
        _unidad_valida(id_fondo="fondo_inexistente_xyz")


# ---------------------------------------------------------------------------
# BancoColectores — errores duros BANCO_
# ---------------------------------------------------------------------------


def test_banco_n_serie_no_positivo():
    """n_serie ≤ 0 debe lanzar BANCO_N_SERIE_NO_POSITIVO."""
    with pytest.raises(ValueError, match="BANCO_N_SERIE_NO_POSITIVO"):
        BancoColectores(n_serie=0, n_paralelo=1)


def test_banco_n_paralelo_no_positivo():
    """n_paralelo ≤ 0 debe lanzar BANCO_N_PARALELO_NO_POSITIVO."""
    with pytest.raises(ValueError, match="BANCO_N_PARALELO_NO_POSITIVO"):
        BancoColectores(n_serie=1, n_paralelo=-1)


# ---------------------------------------------------------------------------
# Chimenea — errores duros CHIM_
# ---------------------------------------------------------------------------


def test_chim_diametro_no_positivo():
    """Diámetro ≤ 0 debe lanzar CHIM_DIAMETRO_NO_POSITIVO."""
    with pytest.raises(ValueError, match="CHIM_DIAMETRO_NO_POSITIVO"):
        Chimenea(diametro_m=0.0, altura_m=2.0)


def test_chim_altura_no_positiva():
    """Altura ≤ 0 debe lanzar CHIM_ALTURA_NO_POSITIVA."""
    with pytest.raises(ValueError, match="CHIM_ALTURA_NO_POSITIVA"):
        Chimenea(diametro_m=0.2, altura_m=-1.0)


def test_chim_material_no_encontrado():
    """Material inexistente debe lanzar CHIM_MATERIAL_NO_ENCONTRADO."""
    with pytest.raises(ValueError, match="CHIM_MATERIAL_NO_ENCONTRADO"):
        Chimenea(diametro_m=0.2, altura_m=2.0, id_material="material_xyz")


# ---------------------------------------------------------------------------
# Métodos de cálculo en ColectorUnidad y Colector
# ---------------------------------------------------------------------------


def test_seccion_canal():
    """seccion_canal_m2 = ancho × espaciado."""
    u = _unidad_valida(ancho_m=1.0, espaciado_m=0.025)
    assert u.seccion_canal_m2() == pytest.approx(0.025)


def test_caudal_volumetrico():
    """caudal_volumetrico_m3_s = v × ancho × espaciado."""
    u = _unidad_valida(ancho_m=1.0, espaciado_m=0.025, velocidad_diseno_ms=0.5)
    assert u.caudal_volumetrico_m3_s() == pytest.approx(0.0125)


def test_caudal_total_banco():
    """caudal_total = n_paralelo × caudal unitario."""
    c = Colector(
        unidad=_unidad_valida(ancho_m=1.0, espaciado_m=0.025, velocidad_diseno_ms=0.5),
        banco=BancoColectores(n_serie=1, n_paralelo=4),
    )
    assert c.caudal_total_m3_s() == pytest.approx(4 * 0.0125)


def test_area_total_banco():
    """area_total = n_serie × n_paralelo × ancho × largo."""
    c = Colector(
        unidad=_unidad_valida(ancho_m=1.0, largo_m=2.0),
        banco=BancoColectores(n_serie=2, n_paralelo=3),
    )
    assert c.area_total_m2() == pytest.approx(2 * 3 * 1.0 * 2.0)


def test_largo_camino_aire():
    """largo_camino = n_serie × largo_m."""
    c = Colector(
        unidad=_unidad_valida(largo_m=2.0),
        banco=BancoColectores(n_serie=3, n_paralelo=1),
    )
    assert c.largo_camino_aire_m() == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Advertencias estáticas
# ---------------------------------------------------------------------------


def test_adv_sin_advertencias_diseno_estandar():
    """Un diseño estándar sin problemas no debe generar advertencias críticas."""
    c = _colector_valido(
        velocidad_diseno_ms=0.5,
        espaciado_m=0.025,
        largo_m=2.0,
        id_aislante="lana_vidrio_media",
    )
    adv = advertencias_colector(c)
    criticas = [a for a in adv if a.severidad == Severidad.CRITICAL]
    assert len(criticas) == 0


def test_adv_velocidad_baja():
    """Velocidad < 0.3 m/s debe generar GEO_VELOCIDAD_BAJA."""
    c = _colector_valido(velocidad_diseno_ms=0.1)
    codigos = [a.codigo for a in advertencias_colector(c)]
    assert "GEO_VELOCIDAD_BAJA" in codigos


def test_adv_velocidad_alta():
    """Velocidad > 3.0 m/s debe generar GEO_VELOCIDAD_ALTA."""
    c = _colector_valido(velocidad_diseno_ms=4.0)
    codigos = [a.codigo for a in advertencias_colector(c)]
    assert "GEO_VELOCIDAD_ALTA" in codigos


def test_adv_aislante_t_max_baja_eps():
    """EPS (T_max 348 K) debe generar MAT_AISLANTE_T_MAX_BAJA (CRITICAL)."""
    c = _colector_valido(id_aislante="eps")
    adv = advertencias_colector(c)
    criticas = [a for a in adv if a.codigo == "MAT_AISLANTE_T_MAX_BAJA"]
    assert len(criticas) == 1
    assert criticas[0].severidad == Severidad.CRITICAL


def test_adv_banco_serie_alto():
    """n_serie > 3 debe generar BANCO_SERIE_ALTO."""
    c = Colector(
        unidad=_unidad_valida(),
        banco=BancoColectores(n_serie=4, n_paralelo=1),
    )
    codigos = [a.codigo for a in advertencias_colector(c)]
    assert "BANCO_SERIE_ALTO" in codigos


def test_adv_chimenea_diametro_pequeno():
    """Chimenea con diámetro < 10 cm debe generar CHIM_DIAMETRO_PEQUENO."""
    ch = Chimenea(diametro_m=0.05, altura_m=2.0)
    codigos = [a.codigo for a in advertencias_chimenea(ch)]
    assert "CHIM_DIAMETRO_PEQUENO" in codigos


def test_adv_chimenea_altura_pequena():
    """Chimenea con altura < 1 m debe generar CHIM_ALTURA_PEQUENA."""
    ch = Chimenea(diametro_m=0.20, altura_m=0.5)
    codigos = [a.codigo for a in advertencias_chimenea(ch)]
    assert "CHIM_ALTURA_PEQUENA" in codigos


def test_adv_chimenea_none_sin_advertencias():
    """Si no hay chimenea, advertencias_chimenea(None) devuelve []."""
    assert advertencias_chimenea(None) == []


# ---------------------------------------------------------------------------
# k_cubierta_efectivo_W_mK — override de conductividad de cubierta (mejora 26)
# ---------------------------------------------------------------------------


def test_k_cubierta_override_default_none():
    """Por defecto el override de k de cubierta es None (usa el catálogo)."""
    assert _unidad_valida().k_cubierta_efectivo_W_mK is None


def test_k_cubierta_override_valido():
    """Un override positivo se acepta sin error."""
    u = _unidad_valida(k_cubierta_efectivo_W_mK=0.06)
    assert u.k_cubierta_efectivo_W_mK == pytest.approx(0.06)


def test_MAT_K_CUBIERTA_NO_POSITIVA():
    """Un override de k de cubierta ≤ 0 debe levantar ValueError."""
    with pytest.raises(ValueError, match="MAT_K_CUBIERTA_NO_POSITIVA"):
        _unidad_valida(k_cubierta_efectivo_W_mK=0.0)


def test_catalogo_policarbonato_k_por_espesor():
    """El catálogo del policarbonato alveolar trae el mapa k(espesor) de mercado."""
    from core.catalogo import CUBIERTAS

    mapa = CUBIERTAS["policarbonato_alveolar"].get("k_efectivo_por_espesor_mm")
    assert mapa is not None
    assert set(mapa.keys()) == {4, 6, 8, 10, 16}
    assert all(v > 0 for v in mapa.values())
