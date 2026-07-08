"""Tests de irradiancia equivalente y reparto producto/aire de la cámara.

Generaliza el techo translúcido histórico (horizontal, GHI cruda) a caras
orientadas. Ver ``calculos/radiacion_camara.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.radiacion_camara import (
    factores_intercepcion,
    factores_sinteticos,
    poa_caras_camara,
    series_radiacion_camara,
)
from core.camara import (
    Camara,
    CarasTranslucidas,
    ConfiguracionBandejas,
    ConstruccionCamara,
    GeometriaCamara,
)
from core.emplazamiento import Emplazamiento


def _df_clima_dia_claro(
    lat: float = -24.79,
    lon: float = -65.41,
    n_horas: int = 24,
    fecha: str = "2022-06-21",
) -> pd.DataFrame:
    """DataFrame horario con GHI/DNI/DHI coherentes (mismo patrón que test_clima_calc)."""
    import pvlib.irradiance
    import pvlib.solarposition

    idx = pd.date_range(fecha, periods=n_horas, freq="h", tz="America/Argentina/Salta")
    horas = np.arange(n_horas, dtype=float)
    fase = np.pi * (horas - 6.0) / 12.0
    ghi = np.where((horas >= 6) & (horas <= 18), 900.0 * np.sin(np.clip(fase, 0, np.pi)), 0.0)
    sol_pos = pvlib.solarposition.get_solarposition(idx, lat, lon)
    descomp = pvlib.irradiance.erbs(ghi=ghi, zenith=sol_pos["apparent_zenith"], datetime_or_doy=idx)
    dni = np.asarray(descomp["dni"], dtype=float)
    dhi = np.asarray(descomp["dhi"], dtype=float)
    return pd.DataFrame(
        {"GHI_Wm2": ghi, "DNI_Wm2": dni, "DHI_Wm2": dhi},
        index=idx,
    )


def _empl(**overrides) -> Emplazamiento:
    base = dict(
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,
        pendiente_colector_deg=25.0,
        zona_horaria="America/Argentina/Salta",
    )
    base.update(overrides)
    return Emplazamiento(**base)


def _camara(**overrides) -> Camara:
    geo_kwargs = {}
    for k in ("pendiente_techo_deg", "acimut_camara_deg", "cara_caida_techo"):
        if k in overrides:
            geo_kwargs[k] = overrides.pop(k)
    cons_kwargs = {}
    for k in ("caras_translucidas", "cubierta_translucida_id", "A_rad_m2", "absortancia_interior"):
        if k in overrides:
            cons_kwargs[k] = overrides.pop(k)
    cons_kwargs.setdefault("cubierta_translucida_id", "vidrio_comun")
    band_kwargs = {}
    for k in ("n_bandejas", "espesor_capa_m", "area_bandeja_m2"):
        if k in overrides:
            band_kwargs[k] = overrides.pop(k)
    assert not overrides, f"kwargs no reconocidos: {overrides}"
    return Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.5, alto_m=1.2, **geo_kwargs),
        construccion=ConstruccionCamara(**cons_kwargs),
        bandejas=ConfiguracionBandejas(**band_kwargs),
    )


# ---------------------------------------------------------------------------
# factores_intercepcion
# ---------------------------------------------------------------------------


class TestFactoresIntercepcion:
    def test_techo_default_es_area_bandeja_sobre_techo(self):
        cam = _camara()
        f = factores_intercepcion(cam)
        esperado = cam.bandejas.area_bandeja_m2 / cam.geometria.A_techo_geom_m2
        assert f["techo"] == pytest.approx(esperado)

    def test_techo_capado_a_1_si_A_rad_mayor_que_techo(self):
        cam = _camara(A_rad_m2=100.0)  # mucho mayor que área real del techo
        f = factores_intercepcion(cam)
        assert f["techo"] == 1.0

    def test_pared_a_mano_con_bandejas_conocidas(self):
        cam = _camara(n_bandejas=4, espesor_capa_m=0.03)  # alto_m=1.2
        f = factores_intercepcion(cam)
        esperado = min(1.0, 4 * 0.03 / 1.2)
        assert f["frente"] == pytest.approx(esperado)
        assert f["atras"] == pytest.approx(esperado)
        assert f["lateral_izq"] == pytest.approx(esperado)
        assert f["lateral_der"] == pytest.approx(esperado)

    def test_pared_siempre_en_rango_0_1(self):
        """clip(...,0,1): las restricciones de coherencia (separación >
        espesor + margen, pila <= alto_menor) implican n·espesor < alto_menor
        <= alto_m, así que en la práctica nunca se satura — pero la fórmula
        debe seguir siendo robusta (clip defensivo)."""
        cam = _camara(n_bandejas=6, espesor_capa_m=0.04)
        f = factores_intercepcion(cam)
        assert 0.0 <= f["frente"] <= 1.0


# ---------------------------------------------------------------------------
# poa_caras_camara
# ---------------------------------------------------------------------------


class TestPoaCarasCamara:
    def test_techo_horizontal_es_GHI_exacto(self):
        cam = _camara()  # pendiente_techo_deg=0 default
        empl = _empl()
        df = _df_clima_dia_claro()
        poas = poa_caras_camara(df, empl, cam)
        assert set(poas.keys()) == {"techo"}
        np.testing.assert_allclose(poas["techo"].values, df["GHI_Wm2"].clip(lower=0.0).values)

    def test_cara_vertical_coincide_con_calculo_directo(self):
        from calculos.clima_calc import calcular_POA_horizonte

        caras = CarasTranslucidas(techo=True, frente=True)
        cam = _camara(caras_translucidas=caras, acimut_camara_deg=180.0)
        empl = _empl()
        df = _df_clima_dia_claro()
        poas = poa_caras_camara(df, empl, cam)
        assert set(poas.keys()) == {"techo", "frente"}
        directo = calcular_POA_horizonte(df, empl, tilt_deg=90.0, acimut_duffie_deg=180.0)
        np.testing.assert_allclose(poas["frente"].values, directo.values)

    def test_sin_cubierta_no_hay_caras(self):
        cam = _camara(cubierta_translucida_id=None)
        empl = _empl()
        df = _df_clima_dia_claro()
        poas = poa_caras_camara(df, empl, cam)
        assert poas == {}


# ---------------------------------------------------------------------------
# series_radiacion_camara — shortcut, monotonía, ceros
# ---------------------------------------------------------------------------


class TestSeriesRadiacionCamara:
    def test_shortcut_techo_solo_beta_cero_da_GHI_exacto(self):
        """Configuración histórica: I_eq_prod coincide algebraicamente con GHI."""
        cam = _camara()
        empl = _empl()
        df = _df_clima_dia_claro()
        i_eq, q_aire = series_radiacion_camara(df, empl, cam)
        np.testing.assert_allclose(
            i_eq.values, df["GHI_Wm2"].clip(lower=0.0).values, rtol=1e-9, atol=1e-9
        )
        # La fracción del techo fuera de A_rad ahora calienta el aire (cambio
        # numérico deliberado): Q_rad_aire > 0 en horas de sol.
        assert (q_aire[df["GHI_Wm2"] > 50.0] > 0.0).all()

    def test_sin_caras_activas_da_ceros(self):
        cam = _camara(cubierta_translucida_id=None)
        empl = _empl()
        df = _df_clima_dia_claro()
        i_eq, q_aire = series_radiacion_camara(df, empl, cam)
        assert (i_eq == 0.0).all()
        assert (q_aire == 0.0).all()

    def test_agregar_cara_no_reduce_i_eq_prod(self):
        """Monotonía: agregar una cara translúcida no puede reducir I_eq_prod."""
        solo_techo = _camara()
        techo_y_frente = _camara(caras_translucidas=CarasTranslucidas(techo=True, frente=True))
        empl = _empl()
        df = _df_clima_dia_claro()
        i_eq_1, _ = series_radiacion_camara(df, empl, solo_techo)
        i_eq_2, _ = series_radiacion_camara(df, empl, techo_y_frente)
        assert (i_eq_2 >= i_eq_1 - 1e-9).all()

    def test_agregar_cara_no_reduce_q_rad_aire(self):
        solo_techo = _camara()
        techo_y_frente = _camara(caras_translucidas=CarasTranslucidas(techo=True, frente=True))
        empl = _empl()
        df = _df_clima_dia_claro()
        _, q_1 = series_radiacion_camara(df, empl, solo_techo)
        _, q_2 = series_radiacion_camara(df, empl, techo_y_frente)
        assert (q_2 >= q_1 - 1e-9).all()

    def test_indice_preservado(self):
        cam = _camara(cubierta_translucida_id=None)
        empl = _empl()
        df = _df_clima_dia_claro()
        i_eq, q_aire = series_radiacion_camara(df, empl, cam)
        assert i_eq.index.equals(df.index)
        assert q_aire.index.equals(df.index)


# ---------------------------------------------------------------------------
# factores_sinteticos
# ---------------------------------------------------------------------------


class TestFactoresSinteticos:
    def test_techo_solo_factor_prod_es_uno(self):
        cam = _camara()
        factor_prod, factor_aire = factores_sinteticos(cam)
        assert factor_prod == pytest.approx(1.0, rel=1e-9)
        assert factor_aire > 0.0

    def test_sin_caras_activas_da_ceros(self):
        cam = _camara(cubierta_translucida_id=None)
        assert factores_sinteticos(cam) == (0.0, 0.0)

    def test_agregar_cara_no_reduce_factores(self):
        solo_techo = _camara()
        techo_y_frente = _camara(caras_translucidas=CarasTranslucidas(techo=True, frente=True))
        fp1, fa1 = factores_sinteticos(solo_techo)
        fp2, fa2 = factores_sinteticos(techo_y_frente)
        assert fp2 >= fp1 - 1e-9
        assert fa2 >= fa1 - 1e-9
