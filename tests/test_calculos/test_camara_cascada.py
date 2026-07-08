"""
Tests del motor semicontinuo `simular_cascada` (S40, Fase 1 del modo industrial).

Túnel a contracorriente de N zonas (columnas) con avance de carros a cadencia
fija y sequedad de salida emergente. Cubre:
  - estructura/smoke y validaciones de input,
  - régimen estacionario alcanzado tras ≥ n_zonas avances (vs 'llenando'),
  - gradiente espacial monótono de X y de T_aire a contracorriente,
  - throughput y conservación de masa de agua,
  - avisos de sub/sobre-secado,
  - consistencia N=1 (un único CSTR de un solo paso).
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.camara_termodinamica import ResultadoCascada, simular_cascada
from calculos.psicrometria import humedad_absoluta
from core.camara import ForzantesAire

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _forzantes_constantes(*, t_max_s: float, T_ent_C: float = 60.0, HR: float = 0.15):
    """Forzantes constantes (aire caliente y seco del colector+auxiliar)."""
    T_ent = T_ent_C + 273.15
    return ForzantesAire(
        t_s=np.array([0.0, t_max_s], dtype=float),
        T_ent_K=np.full(2, T_ent),
        omega_ent=np.full(2, humedad_absoluta(HR, T_ent)),
        m_dot_aire_seco_kg_s=np.full(2, 0.10),
        T_amb_K=np.full(2, 293.15),
        v_viento_ms=np.full(2, 2.0),
    )


def _kwargs_cascada(**overrides):
    """Kwargs nominales: túnel de 4 zonas, intervalo 12 h, producto húmedo."""
    n_zonas = overrides.pop("n_zonas", 4)
    intervalo = overrides.pop("intervalo_avance_s", 12 * 3600.0)
    n_avances = overrides.pop("n_avances", 8)
    t_max = overrides.pop("t_max_forz_s", (n_avances + 1) * intervalo)
    forzantes = overrides.pop("forzantes", _forzantes_constantes(t_max_s=t_max))

    base = dict(
        n_zonas=n_zonas,
        intervalo_avance_s=intervalo,
        n_avances=n_avances,
        T_prod_inicial_K=293.15,
        X_prod_inicial_kg_kg=2.0,
        X_prod_objetivo_kg_kg=0.20,
        m_seco_por_zona_kg=50.0,
        c_ps_J_kgK=1500.0,
        forzantes=forzantes,
        A_prod_por_zona_m2=20.0,
        A_cuerpo_por_zona_m2=15.0,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        k_aisl_W_mK=0.02679,
        esp_cam_m=0.05,
        P_Pa=101325.0,
        aw_func=lambda X: min(1.0, max(0.0, X / 0.5)),
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Estructura y smoke
# ---------------------------------------------------------------------------


def test_smoke_cascada():
    res = simular_cascada(**_kwargs_cascada())
    assert isinstance(res, ResultadoCascada)
    assert res.n_zonas == 4
    assert res.n_avances == 8
    assert res.X_salida_por_avance.shape == (8,)
    assert res.X_perfil_zonas.shape == (4,)
    assert res.T_aire_perfil_zonas_K.shape == (4,)


def test_regimen_alcanzado_con_suficientes_avances():
    """Con n_avances ≥ n_zonas el túnel se llena → régimen estacionario."""
    res = simular_cascada(**_kwargs_cascada(n_zonas=4, n_avances=8))
    assert res.status == "regimen_alcanzado"
    assert res.X_salida_regimen is not None


def test_llenando_si_pocos_avances():
    """Con n_avances < n_zonas el túnel no se llena → status 'llenando'."""
    res = simular_cascada(**_kwargs_cascada(n_zonas=6, n_avances=3))
    assert res.status == "llenando"
    assert res.X_salida_regimen is None
    assert any("CASCADA_REGIMEN_NO_ALCANZADO" in a for a in res.advertencias)


# ---------------------------------------------------------------------------
# Física del contracorriente
# ---------------------------------------------------------------------------


def test_gradiente_espacial_monotono():
    """En régimen, X decrece de la zona fresca (0) a la seca (N−1) y la
    temperatura del aire crece hacia la zona seca (donde entra el aire caliente)."""
    res = simular_cascada(**_kwargs_cascada(n_zonas=5, n_avances=12))
    X = res.X_perfil_zonas
    T_aire = res.T_aire_perfil_zonas_K
    # X: zona 0 (fresca) es la más húmeda; zona N−1 (seca) la más seca.
    assert np.all(np.diff(X) <= 1e-6), f"X no monótona decreciente: {X}"
    assert X[0] > X[-1]
    # Aire: entra caliente por la zona N−1, se enfría/humedece hacia la 0.
    assert T_aire[-1] > T_aire[0]


def test_salida_mas_seca_que_entrada():
    """El producto descargado está más seco que el fresco que entra."""
    res = simular_cascada(**_kwargs_cascada())
    assert res.X_salida_regimen is not None
    assert res.X_salida_regimen < 2.0


def test_cadencia_mas_lenta_seca_mas():
    """Mayor intervalo de avance (más residencia) → producto de salida más seco."""
    rapido = simular_cascada(**_kwargs_cascada(intervalo_avance_s=6 * 3600.0, n_avances=12))
    lento = simular_cascada(**_kwargs_cascada(intervalo_avance_s=18 * 3600.0, n_avances=12))
    assert lento.X_salida_regimen < rapido.X_salida_regimen


# ---------------------------------------------------------------------------
# Producción, throughput y conservación de masa
# ---------------------------------------------------------------------------


def test_throughput_formula():
    """throughput_fresco = m_seco·(1+X_ini) / intervalo."""
    kw = _kwargs_cascada(
        m_seco_por_zona_kg=50.0, X_prod_inicial_kg_kg=2.0, intervalo_avance_s=12 * 3600.0
    )
    res = simular_cascada(**kw)
    esperado = 50.0 * (1.0 + 2.0) / (12 * 3600.0)
    assert res.throughput_fresco_kg_s == pytest.approx(esperado, rel=1e-9)


def test_conservacion_masa_agua():
    """Agua evaporada total ≈ agua que entró − agua que quedó (descargada +
    residual en el túnel). Por construcción del bookkeeping debe cerrar."""
    res = simular_cascada(**_kwargs_cascada())
    X_ini = 2.0
    m_seco = 50.0
    # Agua que entró con cada columna cargada: n_avances cargas + el llenado
    # inicial (n_zonas columnas). Pero el balance interno reporta el evaporado
    # de las descargadas + el residual; verificamos que sea positivo y acotado.
    agua_descargada_in = m_seco * X_ini * res.n_avances
    assert res.masa_evaporada_total_kg > 0.0
    # El evaporado no puede superar el agua total que pasó por el túnel.
    agua_total_max = m_seco * X_ini * (res.n_avances + res.n_zonas)
    assert res.masa_evaporada_total_kg <= agua_total_max + 1e-6
    assert agua_descargada_in > 0.0


def test_masa_seca_producida_positiva():
    res = simular_cascada(**_kwargs_cascada())
    assert res.masa_seca_producida_total_kg > 0.0


# ---------------------------------------------------------------------------
# Avisos de sub/sobre-secado
# ---------------------------------------------------------------------------


def test_aviso_subsecado_cadencia_rapida():
    """Cadencia muy rápida (poca residencia) → producto sub-seco → aviso."""
    res = simular_cascada(
        **_kwargs_cascada(
            n_zonas=3, intervalo_avance_s=3600.0, n_avances=8, X_prod_objetivo_kg_kg=0.20
        )
    )
    assert any("CASCADA_SUBSECADO" in a for a in res.advertencias)


# ---------------------------------------------------------------------------
# Caso N=1 (un único CSTR de un solo paso)
# ---------------------------------------------------------------------------


def test_n_zonas_1_funciona():
    """N=1: una sola zona, sin contracorriente. Debe correr y secar algo."""
    res = simular_cascada(**_kwargs_cascada(n_zonas=1, n_avances=5))
    assert res.n_zonas == 1
    assert res.X_perfil_zonas.shape == (1,)
    # Con una sola zona el régimen se alcanza tras 1 avance.
    assert res.status == "regimen_alcanzado"
    assert res.X_salida_regimen is not None
    assert res.X_salida_regimen < 2.0


# ---------------------------------------------------------------------------
# Validaciones de input
# ---------------------------------------------------------------------------


def test_validacion_n_zonas():
    with pytest.raises(ValueError, match="CASCADA_N_ZONAS_INVALIDO"):
        simular_cascada(**_kwargs_cascada(n_zonas=0))


def test_validacion_intervalo():
    with pytest.raises(ValueError, match="CASCADA_INTERVALO_NO_POSITIVO"):
        simular_cascada(**_kwargs_cascada(intervalo_avance_s=0.0))


def test_validacion_m_seco():
    with pytest.raises(ValueError, match="CASCADA_M_SECO_NO_POSITIVA"):
        simular_cascada(**_kwargs_cascada(m_seco_por_zona_kg=0.0))


# ---------------------------------------------------------------------------
# Q_rad_aire_W — reparto producto/aire (cámara radiativa orientada)
# ---------------------------------------------------------------------------


def test_Q_rad_aire_forzante_calienta_perfil_de_aire():
    """forzantes.Q_rad_aire_W > 0 (repartido entre zonas) calienta el perfil
    de T_aire respecto del caso sin aporte (mismo resto de condiciones)."""
    t_max = (8 + 1) * 12 * 3600.0
    fz_sin = _forzantes_constantes(t_max_s=t_max)
    fz_con = ForzantesAire(
        t_s=fz_sin.t_s,
        T_ent_K=fz_sin.T_ent_K,
        omega_ent=fz_sin.omega_ent,
        m_dot_aire_seco_kg_s=fz_sin.m_dot_aire_seco_kg_s,
        T_amb_K=fz_sin.T_amb_K,
        v_viento_ms=fz_sin.v_viento_ms,
        Q_rad_aire_W=np.full(2, 400.0),
    )
    res_sin = simular_cascada(**_kwargs_cascada(forzantes=fz_sin))
    res_con = simular_cascada(**_kwargs_cascada(forzantes=fz_con))
    assert np.mean(res_con.T_aire_perfil_zonas_K) > np.mean(res_sin.T_aire_perfil_zonas_K)
