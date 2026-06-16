"""
Tests de la red hidráulica y térmica del campo de colectores (S41, ítem 6).

Cubre ``calculos/campo_colectores_calc.py``: conservación de masa, límites de
reparto uniforme, asimetría boca lejana vs cercana, beneficio de la sección
variable y mezcla térmica en el manifold.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.campo_colectores_calc import evaluar_campo_colectores
from core.colector import BancoColectores, CanoMaestro, Colector, ColectorUnidad

# Config tipo ADITAL reducida (8 ramas para velocidad de test).
_N_RAMAS = 8


def _colector(cano: CanoMaestro | None) -> Colector:
    return Colector(
        unidad=ColectorUnidad(largo_m=7.5, ancho_m=0.94, espaciado_m=0.05, velocidad_diseno_ms=1.8),
        banco=BancoColectores(n_serie=1, n_paralelo=_N_RAMAS, cano_maestro=cano),
    )


def _Q_diseno(col: Colector) -> float:
    u = col.unidad
    return col.banco.n_paralelo * u.velocidad_diseno_ms * u.ancho_m * u.espaciado_m


_KWARGS = dict(T_amb_K=293.15, I_g_POA_W_m2=900.0, v_viento_ms=2.0, P_Pa=81000.0)


def test_conservacion_de_masa():
    col = _colector(CanoMaestro(largo_m=18.0, ancho_m=1.0, alto_m=0.9))
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert r.q_ramas_m3_s.sum() == pytest.approx(Q, rel=1e-9)
    assert r.convergio


def test_reparto_uniforme_sin_cano():
    col = _colector(None)
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert np.allclose(r.q_ramas_m3_s, Q / _N_RAMAS)
    assert r.uniformidad["desviacion_max_pct"] == pytest.approx(0.0)


def test_troncal_holgado_reparto_casi_uniforme():
    """Troncal enorme (ΔP→0): el reparto tiende al uniforme."""
    col = _colector(CanoMaestro(largo_m=18.0, ancho_m=4.0, alto_m=4.0))
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert r.uniformidad["desviacion_max_pct"] < 1.0


def test_boca_lejana_recibe_menos_caudal():
    """La boca lejana ve más troncal en su camino → menos caudal."""
    col = _colector(CanoMaestro(largo_m=18.0, ancho_m=0.5, alto_m=0.5))
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert r.convergio
    assert r.q_ramas_m3_s[0] < r.q_ramas_m3_s[-1]


def test_seccion_variable_mejora_uniformidad_vs_constante_chica():
    """Sección creciente reparte mejor que la constante igual a la sección
    de inicio (el tramo final holgado descarga el troncal)."""
    Q = _Q_diseno(_colector(None))
    cano_chico = CanoMaestro(largo_m=18.0, ancho_m=0.4, alto_m=0.4)
    cano_var = CanoMaestro(
        largo_m=18.0, ancho_m=1.0, alto_m=0.9, ancho_inicio_m=0.4, alto_inicio_m=0.4
    )
    r_chico = evaluar_campo_colectores(
        _colector(cano_chico), Q_total_m3_s=Q, calcular_termica=False, **_KWARGS
    )
    r_var = evaluar_campo_colectores(
        _colector(cano_var), Q_total_m3_s=Q, calcular_termica=False, **_KWARGS
    )
    assert r_var.uniformidad["desviacion_max_pct"] < r_chico.uniformidad["desviacion_max_pct"]


def test_termica_mezcla_y_salida_cano():
    """T_mezcla acotada por las ramas; T_salida_cano = mezcla + ΔT térmica."""
    col = _colector(CanoMaestro(largo_m=18.0, ancho_m=1.0, alto_m=0.9, absortancia_solar=0.35))
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, **_KWARGS)
    assert r.T_salida_ramas_K is not None
    assert r.T_salida_ramas_K.min() > _KWARGS["T_amb_K"]  # con sol, calienta
    assert r.T_salida_ramas_K.min() <= r.T_mezcla_K <= r.T_salida_ramas_K.max()
    assert r.T_salida_cano_K == pytest.approx(r.T_mezcla_K + r.dT_cano_K)
    # ΔT térmica del caño acotada en magnitud (±6 K en prediseño; el signo
    # depende del balance pérdida convectiva vs aporte solar al caudal dado).
    assert -6.0 < r.dT_cano_K < 6.0


def test_caudal_no_positivo():
    col = _colector(None)
    with pytest.raises(ValueError, match="CAMPO_CAUDAL_NO_POSITIVO"):
        evaluar_campo_colectores(col, Q_total_m3_s=0.0, **_KWARGS)


# ---------------------------------------------------------------------------
# Troncal aislado y perfil de velocidad (mejora 32, S42)
# ---------------------------------------------------------------------------


def test_troncal_y_perfil_expuestos_con_cano():
    """Con caño maestro y N>1 se expone el ΔP del troncal (aislado de la rama)
    y el perfil de velocidad por tramo (largo == n_ramas)."""
    col = _colector(CanoMaestro(largo_m=18.0, ancho_m=0.5, alto_m=0.5))
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert r.dP_troncal_Pa > 0.0
    assert len(r.v_troncal_perfil_ms) == _N_RAMAS
    assert np.all(r.v_troncal_perfil_ms >= 0.0)


def test_perfil_vacio_sin_cano():
    """Sin caño maestro no hay troncal: ΔP troncal nulo y perfil vacío."""
    col = _colector(None)
    Q = _Q_diseno(col)
    r = evaluar_campo_colectores(col, Q_total_m3_s=Q, calcular_termica=False, **_KWARGS)
    assert r.dP_troncal_Pa == 0.0
    assert len(r.v_troncal_perfil_ms) == 0


def test_troncal_responde_a_seccion():
    """La compensación es observable: estrechar el inicio (sección más chica)
    sube el ΔP del troncal y la velocidad máxima del perfil."""
    Q = _Q_diseno(_colector(None))
    cano_holgado = CanoMaestro(
        largo_m=18.0, ancho_m=1.0, alto_m=0.9, ancho_inicio_m=0.8, alto_inicio_m=0.8
    )
    cano_estrecho = CanoMaestro(
        largo_m=18.0, ancho_m=1.0, alto_m=0.9, ancho_inicio_m=0.3, alto_inicio_m=0.3
    )
    r_holgado = evaluar_campo_colectores(
        _colector(cano_holgado), Q_total_m3_s=Q, calcular_termica=False, **_KWARGS
    )
    r_estrecho = evaluar_campo_colectores(
        _colector(cano_estrecho), Q_total_m3_s=Q, calcular_termica=False, **_KWARGS
    )
    assert r_estrecho.dP_troncal_Pa > r_holgado.dP_troncal_Pa
    assert r_estrecho.v_troncal_perfil_ms.max() > r_holgado.v_troncal_perfil_ms.max()
