"""Tests del catálogo de KPIs de barrido y sus extractores.

Los extractores se alimentan con objetos de resultado *mock* (SimpleNamespace
+ duck-typing) para verificar que leen el campo correcto y que toleran (con
``None``) los campos ausentes de otros modos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from calculos.catalogo_kpis_barrido import (
    KPIS_AVANZADOS,
    KPIS_FIJOS,
    KPIS_POR_ID,
    kpis_avanzados_para_modo,
    kpis_fijos_para_modo,
    obtener_kpi,
)

# --- Coherencia del catálogo ----------------------------------------------


def test_ids_unicos_globales():
    ids = [k.id for k in (*KPIS_FIJOS, *KPIS_AVANZADOS)]
    assert len(ids) == len(set(ids))


def test_hay_6_fijos():
    assert len(KPIS_FIJOS) == 6


def test_modos_validos_no_vacios():
    for k in (*KPIS_FIJOS, *KPIS_AVANZADOS):
        assert k.modos_validos, f"{k.id} no declara modos válidos."
        assert k.modos_validos <= {"constantes", "transitorio", "anual"}


def test_obtener_kpi_desconocido_lanza_keyerror():
    with pytest.raises(KeyError, match="BARRIDO_KPI_DESCONOCIDO"):
        obtener_kpi("kpi_inexistente")


def test_filtro_por_modo():
    # eta_termica_colector es solo Constantes.
    fijos_const = {k.id for k in kpis_fijos_para_modo("constantes")}
    fijos_trans = {k.id for k in kpis_fijos_para_modo("transitorio")}
    assert "eta_termica_colector" in fijos_const
    assert "eta_termica_colector" not in fijos_trans
    # Los avanzados anuales solo en anual.
    avz_anual = {k.id for k in kpis_avanzados_para_modo("anual")}
    assert "kg_secados_anual" in avz_anual
    assert "eta_total_anual_media" in avz_anual
    avz_const = {k.id for k in kpis_avanzados_para_modo("constantes")}
    assert "kg_secados_anual" not in avz_const


# --- Extractores: modo Constantes -----------------------------------------


def _camara_td_mock(t_secado_s, masa_kg, ok=True):
    """Mock duck-typed del resultado de cámara (motor termodinámico)."""
    return SimpleNamespace(
        status="X_obj_alcanzado" if ok else "t_max_alcanzado",
        t_secado_s=t_secado_s,
        masa_evaporada_total_kg=masa_kg,
    )


def test_extractor_t_secado_h_via_camara():
    res = SimpleNamespace(camara=_camara_td_mock(t_secado_s=7200.0, masa_kg=3.0))
    assert obtener_kpi("t_secado_h").extractor(res) == pytest.approx(2.0)


def test_extractor_masa_agua_via_camara():
    res = SimpleNamespace(camara=_camara_td_mock(t_secado_s=3600.0, masa_kg=4.2))
    assert obtener_kpi("masa_agua_evap_kg").extractor(res) == pytest.approx(4.2)


def test_extractor_cop_y_energia_total():
    res = SimpleNamespace(COP_secado=0.45, energia_total_MJ=12.3, fraccion_solar=0.8)
    assert obtener_kpi("cop_secado").extractor(res) == pytest.approx(0.45)
    assert obtener_kpi("energia_total_MJ").extractor(res) == pytest.approx(12.3)
    assert obtener_kpi("fraccion_solar").extractor(res) == pytest.approx(0.8)


def test_extractor_eta_colector_anidado():
    res = SimpleNamespace(
        colector=SimpleNamespace(eta_termica=0.62, T_salida_K=330.0, Re_medio=2500.0)
    )
    assert obtener_kpi("eta_termica_colector").extractor(res) == pytest.approx(0.62)
    assert obtener_kpi("T_salida_colector_K").extractor(res) == pytest.approx(330.0)
    assert obtener_kpi("Re_colector").extractor(res) == pytest.approx(2500.0)


def test_extractor_eta_colector_sin_colector_devuelve_none():
    res = SimpleNamespace(colector=None)
    assert obtener_kpi("eta_termica_colector").extractor(res) is None


# --- Extractores: campo ausente → None ------------------------------------


def test_extractor_devuelve_none_si_falta_campo():
    res = SimpleNamespace()  # sin atributos
    assert obtener_kpi("cop_secado").extractor(res) is None
    assert obtener_kpi("energia_total_MJ").extractor(res) is None
    assert obtener_kpi("t_secado_h").extractor(res) is None


def test_extractor_t_secado_h_modo_anual():
    """En anual el extractor usa t_secado_promedio_h directamente."""
    res = SimpleNamespace(t_secado_promedio_h=5.5)
    assert obtener_kpi("t_secado_h").extractor(res) == pytest.approx(5.5)


# --- Extractores: modo Transitorio / Anual --------------------------------


def test_extractor_T_prod_max_y_horas_hr():
    res = SimpleNamespace(T_prod_max_K=328.0, horas_HR_alta_s=7200.0)
    assert obtener_kpi("T_prod_max_K").extractor(res) == pytest.approx(328.0)
    assert obtener_kpi("horas_HR_alta_h").extractor(res) == pytest.approx(2.0)


def test_extractor_kpis_anuales():
    res = SimpleNamespace(
        kg_secados_anual=1234.0,
        eta_total_anual_media=0.41,
        E_solar_anual_MJ=9000.0,
    )
    assert obtener_kpi("kg_secados_anual").extractor(res) == pytest.approx(1234.0)
    assert obtener_kpi("eta_total_anual_media").extractor(res) == pytest.approx(0.41)
    assert obtener_kpi("E_solar_anual_MJ").extractor(res) == pytest.approx(9000.0)


def test_todos_los_kpis_indexados():
    assert KPIS_POR_ID["t_secado_h"].label == "Tiempo de secado"
    assert len(KPIS_POR_ID) == len(KPIS_FIJOS) + len(KPIS_AVANZADOS)
