"""
Tests del caño maestro (manifold) del banco — gran escala (S40, Fase 3).

Cubre la dataclass ``CanoMaestro`` (validaciones + propiedades geométricas) y
los tres modelos de ``calculos.cano_maestro_calc``: pérdida de carga, balance
térmico con aporte solar, y criterio de uniformidad de distribución.
"""

from __future__ import annotations

import pytest

from calculos.cano_maestro_calc import (
    delta_T_cano_maestro,
    estimar_delta_P_cano_maestro,
    uniformidad_distribucion,
)
from core.colector import CanoMaestro

# ---------------------------------------------------------------------------
# Dataclass: validaciones y geometría
# ---------------------------------------------------------------------------


def test_defaults_y_propiedades():
    c = CanoMaestro()
    assert c.area_seccion_m2 == pytest.approx(0.5)
    assert c.diametro_hidraulico_m == pytest.approx(2.0 * 1.0 * 0.5 / 1.5)
    assert c.area_externa_m2 == pytest.approx(2.0 * (1.0 + 0.5) * 18.0)
    assert c.area_superior_m2 == pytest.approx(1.0 * 18.0)


def test_validacion_largo():
    with pytest.raises(ValueError, match="CANO_LARGO_NO_POSITIVO"):
        CanoMaestro(largo_m=0.0)


def test_validacion_seccion():
    with pytest.raises(ValueError, match="CANO_SECCION_NO_POSITIVA"):
        CanoMaestro(ancho_m=0.0)


def test_validacion_aislante_sin_espesor():
    with pytest.raises(ValueError, match="CANO_AISLANTE_SIN_ESPESOR"):
        CanoMaestro(aislado=True, espesor_aislante_m=0.0)


def test_validacion_absortancia():
    with pytest.raises(ValueError, match="CANO_ABSORTANCIA_FUERA_RANGO"):
        CanoMaestro(absortancia_solar=1.5)


# ---------------------------------------------------------------------------
# Pérdida de carga
# ---------------------------------------------------------------------------


def test_delta_P_positiva_y_componentes():
    c = CanoMaestro()
    dp = estimar_delta_P_cano_maestro(c, Q_vol_total_m3_s=1.8)
    assert dp["total"] > 0.0
    assert dp["friccion"] > 0.0
    assert dp["accesorios"] > 0.0
    assert dp["total"] == pytest.approx(dp["friccion"] + dp["accesorios"])
    assert dp["v_troncal_ms"] == pytest.approx(1.8 / 0.5)


def test_delta_P_crece_con_caudal():
    c = CanoMaestro()
    dp_bajo = estimar_delta_P_cano_maestro(c, Q_vol_total_m3_s=1.0)
    dp_alto = estimar_delta_P_cano_maestro(c, Q_vol_total_m3_s=3.0)
    assert dp_alto["total"] > dp_bajo["total"]


def test_seccion_mayor_reduce_delta_P():
    """Sección creciente (más área) → menor velocidad → menor ΔP."""
    chico = CanoMaestro(ancho_m=0.5, alto_m=0.4)
    grande = CanoMaestro(ancho_m=1.2, alto_m=0.9)
    dp_chico = estimar_delta_P_cano_maestro(chico, Q_vol_total_m3_s=1.8)
    dp_grande = estimar_delta_P_cano_maestro(grande, Q_vol_total_m3_s=1.8)
    assert dp_grande["total"] < dp_chico["total"]


def test_delta_P_caudal_nulo():
    c = CanoMaestro()
    dp = estimar_delta_P_cano_maestro(c, Q_vol_total_m3_s=0.0)
    assert dp["total"] == 0.0


# ---------------------------------------------------------------------------
# Balance térmico
# ---------------------------------------------------------------------------


def test_perdida_neta_de_noche():
    """Sin sol, el aire caliente pierde calor → ΔT < 0."""
    c = CanoMaestro()
    dT = delta_T_cano_maestro(
        c,
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=0.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=2.0,
    )
    assert dT < 0.0


def test_sol_reduce_la_perdida():
    """Con sol, el aporte radiativo reduce (o revierte) la pérdida neta."""
    c = CanoMaestro()
    dT_noche = delta_T_cano_maestro(
        c,
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=0.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=2.0,
    )
    dT_dia = delta_T_cano_maestro(
        c,
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=900.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=2.0,
    )
    assert dT_dia > dT_noche


def test_aislacion_reduce_perdida():
    """El caño aislado pierde menos calor que el desnudo (igual condición)."""
    desnudo = CanoMaestro(aislado=False)
    aislado = CanoMaestro(aislado=True, espesor_aislante_m=0.05, k_aislante_W_mK=0.04)
    kw = dict(T_aire_K=333.15, T_amb_K=288.15, I_g_W_m2=0.0, m_dot_as_kg_s=2.0, v_viento_ms=2.0)
    dT_desnudo = delta_T_cano_maestro(desnudo, **kw)
    dT_aislado = delta_T_cano_maestro(aislado, **kw)
    assert abs(dT_aislado) < abs(dT_desnudo)


def test_sin_aporte_solar_pierde_aunque_haya_sol():
    """Con aporte_solar=False, el sol no entra al balance → pérdida como de noche."""
    c = CanoMaestro(aporte_solar=False)
    dT = delta_T_cano_maestro(
        c,
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=900.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=2.0,
    )
    assert dT < 0.0


def test_delta_T_caudal_nulo():
    c = CanoMaestro()
    dT = delta_T_cano_maestro(
        c,
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=0.0,
        m_dot_as_kg_s=0.0,
        v_viento_ms=2.0,
    )
    assert dT == 0.0


# ---------------------------------------------------------------------------
# Uniformidad de distribución
# ---------------------------------------------------------------------------


def test_uniforme_si_troncal_barato():
    """ΔP del troncal pequeña frente a la rama → reparto uniforme."""
    u = uniformidad_distribucion(dP_cano_maestro_Pa=5.0, dP_rama_Pa=200.0)
    assert u["es_uniforme"] is True
    assert u["ratio"] == pytest.approx(0.025)


def test_no_uniforme_si_troncal_caro():
    """ΔP del troncal comparable a la rama → reparto no uniforme."""
    u = uniformidad_distribucion(dP_cano_maestro_Pa=100.0, dP_rama_Pa=200.0)
    assert u["es_uniforme"] is False


def test_uniformidad_rama_nula():
    u = uniformidad_distribucion(dP_cano_maestro_Pa=10.0, dP_rama_Pa=0.0)
    assert u["es_uniforme"] is False


# ---------------------------------------------------------------------------
# S41: material aislante, cubierta translúcida y sección variable
# ---------------------------------------------------------------------------


def test_material_aislante_setea_k_desde_catalogo():
    """material_aislante manda: k_aislante sale de aislantes.yaml."""
    cano = CanoMaestro(aislado=True, espesor_aislante_m=0.05, material_aislante="eps")
    assert cano.k_aislante_W_mK == pytest.approx(0.038)


def test_cano_aislante_desconocido():
    with pytest.raises(ValueError, match="CANO_AISLANTE_DESCONOCIDO"):
        CanoMaestro(aislado=True, espesor_aislante_m=0.05, material_aislante="unobtainium")


def test_cano_cubierta_desconocida():
    with pytest.raises(ValueError, match="CANO_CUBIERTA_DESCONOCIDA"):
        CanoMaestro(cubierta="cristal_de_kriptonita")


def test_cano_seccion_inicio_incompleta():
    with pytest.raises(ValueError, match="CANO_SECCION_INICIO_INCOMPLETA"):
        CanoMaestro(ancho_inicio_m=0.4)  # sin alto_inicio_m


def test_cano_seccion_inicio_no_positiva():
    with pytest.raises(ValueError, match="CANO_SECCION_INICIO_NO_POSITIVA"):
        CanoMaestro(ancho_inicio_m=0.4, alto_inicio_m=-0.1)


def test_transmitancia_cubierta_default_es_uno():
    assert CanoMaestro().transmitancia_cubierta == pytest.approx(1.0)
    cano = CanoMaestro(cubierta="vidrio_comun")
    assert cano.transmitancia_cubierta == pytest.approx(0.84)


def test_seccion_en_fraccion_interpola_lineal():
    cano = CanoMaestro(ancho_m=1.0, alto_m=0.9, ancho_inicio_m=0.4, alto_inicio_m=0.3)
    assert cano.seccion_variable is True
    assert cano.seccion_en_fraccion(0.0) == pytest.approx((0.4, 0.3))
    assert cano.seccion_en_fraccion(1.0) == pytest.approx((1.0, 0.9))
    assert cano.seccion_en_fraccion(0.5) == pytest.approx((0.7, 0.6))


def test_cubierta_reduce_perdida_nocturna():
    """De noche (I=0), la cavidad bajo la cubierta reduce la pérdida neta."""
    base = dict(
        T_aire_K=333.15,
        T_amb_K=288.15,
        I_g_W_m2=0.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=3.0,
    )
    dT_sin = delta_T_cano_maestro(CanoMaestro(), **base)
    dT_con = delta_T_cano_maestro(CanoMaestro(cubierta="policarbonato_alveolar"), **base)
    assert dT_sin < 0 and dT_con < 0
    assert dT_con > dT_sin  # menos negativo = pierde menos


def test_cubierta_aplica_tau_a_la_ganancia():
    """Con sol fuerte, la ganancia se afecta por τ pero la pérdida por la
    cavidad baja: el efecto neto con poco viento debe seguir siendo ganancia."""
    base = dict(
        T_aire_K=313.15,
        T_amb_K=308.15,  # ΔT chico → domina el término solar
        I_g_W_m2=1000.0,
        m_dot_as_kg_s=2.0,
        v_viento_ms=1.0,
    )
    dT_sin = delta_T_cano_maestro(CanoMaestro(absortancia_solar=0.9), **base)
    dT_con = delta_T_cano_maestro(
        CanoMaestro(absortancia_solar=0.9, cubierta="vidrio_comun"), **base
    )
    assert dT_sin > 0
    assert dT_con > 0
    # τ=0.84 recorta la ganancia bruta: con ΔT≈0 la versión cubierta gana menos.
    assert dT_con < dT_sin


def test_seccion_variable_friccion_mayor_que_constante_final():
    """Sección creciente (chica aguas arriba) fricciona más que la constante
    igual a la sección final (la más grande): es el caso de menos material pero
    más fricción que el caño grande constante, al mismo caudal total."""
    cano_cte = CanoMaestro(largo_m=18.0, ancho_m=1.0, alto_m=0.9)
    cano_var = CanoMaestro(
        largo_m=18.0, ancho_m=1.0, alto_m=0.9, ancho_inicio_m=0.3, alto_inicio_m=0.3
    )
    dP_cte = estimar_delta_P_cano_maestro(cano_cte, 2.0)
    dP_var = estimar_delta_P_cano_maestro(cano_var, 2.0)
    assert dP_var["friccion"] > dP_cte["friccion"]
    # Los accesorios se referencian a la sección del ventilador: no cambian.
    assert dP_var["accesorios"] == pytest.approx(dP_cte["accesorios"])


# ---------------------------------------------------------------------------
# Flujo acumulado y compensación de sección (mejora 32, S42)
# ---------------------------------------------------------------------------


def test_retorno_incluye_v_fin_y_v_max():
    """El dict expone v_fin_ms (extremo ventilador) y v_max_ms (máx del perfil);
    v_troncal_ms se mantiene == v_fin_ms por back-compat."""
    cano = CanoMaestro(largo_m=18.0, ancho_m=1.0, alto_m=0.5)
    dp = estimar_delta_P_cano_maestro(cano, 1.0)
    assert "v_fin_ms" in dp and "v_max_ms" in dp
    assert dp["v_fin_ms"] == pytest.approx(1.0 / cano.area_seccion_m2)
    assert dp["v_troncal_ms"] == pytest.approx(dp["v_fin_ms"])
    assert dp["v_max_ms"] >= 0.0


def test_cano_chico_constante_fricciona_mucho_mas_que_grande():
    """Flujo acumulado: un caño chico constante dispara la fricción frente al
    caño grande constante (la velocidad crece al acumular caudal en poca área)."""
    grande = CanoMaestro(largo_m=18.0, ancho_m=1.0, alto_m=0.5)  # A = 0.50 m²
    chico = CanoMaestro(largo_m=18.0, ancho_m=0.5, alto_m=0.25)  # A = 0.125 m²
    dp_grande = estimar_delta_P_cano_maestro(grande, 1.0)
    dp_chico = estimar_delta_P_cano_maestro(chico, 1.0)
    assert dp_chico["friccion"] > 5.0 * dp_grande["friccion"]
    assert dp_chico["v_max_ms"] > dp_grande["v_max_ms"]


def test_seccion_creciente_acota_velocidad_y_no_invierte():
    """La compensación funciona: una sección creciente (A_0 → A_L) mantiene la
    velocidad acotada y fricciona MUCHO menos que un caño chico constante igual
    a su sección de inicio. (Antes el modelo invertía esto: el creciente daba
    más fricción que el chico al meterle el caudal total en la sección chica.)"""
    Q = 1.0
    chico_cte = CanoMaestro(largo_m=18.0, ancho_m=0.5, alto_m=0.25)
    creciente = CanoMaestro(
        largo_m=18.0, ancho_m=1.0, alto_m=0.5, ancho_inicio_m=0.5, alto_inicio_m=0.25
    )
    dp_chico = estimar_delta_P_cano_maestro(chico_cte, Q)
    dp_crec = estimar_delta_P_cano_maestro(creciente, Q)
    # El creciente fricciona mucho menos que el chico constante.
    assert dp_crec["friccion"] < 0.5 * dp_chico["friccion"]
    # Y mantiene la velocidad acotada al valor del extremo del ventilador.
    assert dp_crec["v_max_ms"] == pytest.approx(dp_crec["v_fin_ms"], rel=0.05)
    assert dp_crec["v_max_ms"] < 0.5 * dp_chico["v_max_ms"]
