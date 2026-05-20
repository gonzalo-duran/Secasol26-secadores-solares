"""
Tests del módulo calculos/clima_calc.py.

Los tests de la función obtener_clima() que requieren red están marcados con
pytest.mark.network y se omiten por defecto en el CI sin red.

Los tests de _aplicar_politica_huecos() son unitarios puros (sin red).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.clima_calc import _aplicar_politica_huecos, _hash_cache
from core.clima import COLUMNAS_SI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_sin_huecos(n: int = 24) -> pd.DataFrame:
    """DataFrame SI completo sin NaN, índice UTC horario."""
    idx = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    data = {
        "T_amb_K": np.full(n, 293.15),
        "GHI_Wm2": np.linspace(0, 800, n),
        "DNI_Wm2": np.linspace(0, 700, n),
        "DHI_Wm2": np.linspace(0, 200, n),
        "WS_ms": np.full(n, 2.5),
        "presion_Pa": np.full(n, 90000.0),
        "HR": np.full(n, 0.6),
    }
    return pd.DataFrame(data, index=idx)


def _df_con_hueco(inicio_hueco: int, duracion: int) -> pd.DataFrame:
    """DataFrame de 48 h con un hueco de NaN de longitud dada."""
    df = _df_sin_huecos(n=48)
    df.iloc[inicio_hueco : inicio_hueco + duracion] = np.nan
    return df


# ---------------------------------------------------------------------------
# Tests de _hash_cache
# ---------------------------------------------------------------------------


def test_hash_cache_determinista():
    """El mismo (lat, lon, año) produce siempre el mismo hash."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-24.72, -65.41, 2022)
    assert h1 == h2


def test_hash_cache_diferente_anio():
    """Años distintos producen hashes distintos."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-24.72, -65.41, 2023)
    assert h1 != h2


def test_hash_cache_diferente_ubicacion():
    """Ubicaciones distintas producen hashes distintos."""
    h1 = _hash_cache(-24.72, -65.41, 2022)
    h2 = _hash_cache(-25.00, -65.41, 2022)
    assert h1 != h2


# ---------------------------------------------------------------------------
# Tests de _aplicar_politica_huecos
# ---------------------------------------------------------------------------


def test_politica_sin_huecos():
    """DataFrame sin NaN no debe generar huecos ni horas interpoladas."""
    df = _df_sin_huecos()
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 0
    assert calidad.n_horas_interpoladas == 0
    assert calidad.n_horas_bloqueadas == 0
    assert calidad.mayor_hueco_h == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_1h_interpolado():
    """Hueco de 1 h debe interpolarse completamente."""
    df = _df_con_hueco(inicio_hueco=10, duracion=1)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 1
    assert calidad.n_horas_interpoladas == 1
    assert calidad.n_horas_bloqueadas == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_3h_interpolado():
    """Hueco de exactamente 3 h debe interpolarse completamente."""
    df = _df_con_hueco(inicio_hueco=5, duracion=3)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_horas_interpoladas == 3
    assert calidad.n_horas_bloqueadas == 0
    assert df_corr.isna().sum().sum() == 0


def test_politica_hueco_4h_bloqueado():
    """Hueco de 4 h (> 3 h) debe quedar bloqueado como NaN."""
    df = _df_con_hueco(inicio_hueco=5, duracion=4)
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.mayor_hueco_h == 4
    assert calidad.n_horas_bloqueadas == 4
    # Las 4 filas centrales del hueco deben seguir siendo NaN
    assert df_corr.iloc[5:9].isna().any().any()


def test_politica_dos_huecos_mixtos():
    """Un hueco de 2 h (interpolado) y otro de 5 h (bloqueado) coexisten."""
    df = _df_sin_huecos(n=72)
    df.iloc[5:7] = np.nan    # hueco de 2 h → se interpola
    df.iloc[20:25] = np.nan  # hueco de 5 h → se bloquea
    df_corr, calidad = _aplicar_politica_huecos(df)
    assert calidad.n_huecos_originales == 2
    assert calidad.n_horas_interpoladas == 2
    assert calidad.n_horas_bloqueadas == 5
    assert calidad.mayor_hueco_h == 5


def test_politica_columnas_preservadas():
    """El DataFrame resultante debe conservar exactamente las columnas de COLUMNAS_SI."""
    df = _df_con_hueco(inicio_hueco=2, duracion=2)
    df_corr, _ = _aplicar_politica_huecos(df)
    assert list(df_corr.columns) == list(df.columns)


# ---------------------------------------------------------------------------
# POA (Plane of Array) — transposición GHI/DNI/DHI → plano inclinado
# ---------------------------------------------------------------------------


from calculos.clima_calc import calcular_POA_horizonte
from core.emplazamiento import Emplazamiento


def _df_clima_dia_claro(
    lat: float = -24.79, lon: float = -65.41, n_horas: int = 24,
    fecha: str = "2022-06-21",
) -> pd.DataFrame:
    """DataFrame horario con perfil de día claro y DNI/DHI coherentes con GHI.

    El timestamp se localiza en Argentina/Salta — pvlib requiere tz-aware.
    Se genera una GHI semicampana razonable y luego se descompone en DNI/DHI
    con el modelo Erbs (que respeta GHI = DNI·cosθz + DHI), de modo que el
    test horizontal (tilt=0) tenga POA ≡ GHI.
    """
    import pvlib.irradiance
    import pvlib.solarposition

    idx = pd.date_range(
        fecha, periods=n_horas, freq="h", tz="America/Argentina/Salta",
    )
    horas = np.arange(n_horas, dtype=float)
    fase = np.pi * (horas - 6.0) / 12.0
    ghi = np.where(
        (horas >= 6) & (horas <= 18),
        900.0 * np.sin(np.clip(fase, 0, np.pi)),
        0.0,
    )
    sol_pos = pvlib.solarposition.get_solarposition(idx, lat, lon)
    # Erbs descompone GHI → DNI/DHI consistentes con la geometría solar.
    descomp = pvlib.irradiance.erbs(
        ghi=ghi, zenith=sol_pos["apparent_zenith"], datetime_or_doy=idx,
    )
    dni = np.asarray(descomp["dni"], dtype=float)
    dhi = np.asarray(descomp["dhi"], dtype=float)
    return pd.DataFrame(
        {
            "T_amb_K": np.full(n_horas, 288.15),
            "GHI_Wm2": ghi,
            "DNI_Wm2": dni,
            "DHI_Wm2": dhi,
            "HR": np.full(n_horas, 0.40),
            "WS_ms": np.full(n_horas, 2.0),
            "presion_Pa": np.full(n_horas, 101325.0),
        },
        index=idx,
    )


def test_POA_horizontal_aproxima_GHI():
    """Colector horizontal (tilt=0): POA debe ser ~GHI hora a hora."""
    empl = Emplazamiento(
        latitud_deg=-24.79, longitud_deg=-65.41, altitud_m=1200.0,
        acimut_colector_deg=180.0,    # Norte en Duffie — irrelevante con tilt=0
        pendiente_colector_deg=0.0,
        zona_horaria="America/Argentina/Salta",
    )
    df = _df_clima_dia_claro()
    poa = calcular_POA_horizonte(df, empl)
    # En tilt=0 el plano coincide con horizontal → POA = GHI (modulo
    # contribución del suelo, que es 0 con β=0).
    ghi_diurno = df["GHI_Wm2"][df["GHI_Wm2"] > 50.0]
    poa_diurno = poa[df["GHI_Wm2"] > 50.0]
    # Tolerancia 1 % — pequeño desajuste numérico entre Erbs (separa GHI en
    # DNI/DHI) y la transposición inversa de pvlib (modelo isotrópico).
    np.testing.assert_allclose(poa_diurno.values, ghi_diurno.values, rtol=1e-2)


def test_POA_invierno_Salta_supera_GHI_al_mediodia():
    """Lat -24.79°, tilt 30°, azimut Norte, junio (invierno hemisferio Sur):
    al mediodía la POA debe superar a GHI por el factor de incidencia más
    favorable al plano inclinado. Cociente esperado en rango razonable."""
    empl = Emplazamiento(
        latitud_deg=-24.79, longitud_deg=-65.41, altitud_m=1200.0,
        acimut_colector_deg=180.0,    # 180° en Duffie = Norte hemisferio S
        pendiente_colector_deg=30.0,
        zona_horaria="America/Argentina/Salta",
    )
    df = _df_clima_dia_claro()
    poa = calcular_POA_horizonte(df, empl)
    # Hora con GHI máximo (mediodía solar aproximado, hora 12 en el día tipo).
    h_pico = df["GHI_Wm2"].idxmax()
    ratio = float(poa.loc[h_pico]) / float(df.loc[h_pico, "GHI_Wm2"])
    # Para invierno (junio) en lat sur con tilt 30°, el cociente debe ser
    # claramente > 1. Rango amplio para no quedar atado al modelo difuso.
    assert 1.10 < ratio < 1.80, f"POA/GHI al mediodía = {ratio:.3f}, fuera de rango"


def test_POA_clipea_negativos_y_nan():
    """POA siempre ≥ 0; horas nocturnas con DNI/DHI=0 → POA=0."""
    empl = Emplazamiento(
        latitud_deg=-24.79, longitud_deg=-65.41, altitud_m=1200.0,
        acimut_colector_deg=180.0, pendiente_colector_deg=30.0,
        zona_horaria="America/Argentina/Salta",
    )
    df = _df_clima_dia_claro()
    poa = calcular_POA_horizonte(df, empl)
    assert (poa >= 0.0).all()
    # Horas nocturnas (GHI=0) → POA = 0
    nocturnas = df["GHI_Wm2"] == 0.0
    assert (poa[nocturnas] == 0.0).all()


def test_POA_fallback_a_GHI_con_dni_nan():
    """Si DNI o DHI son NaN en una hora, esa hora cae a POA=GHI (clip)."""
    empl = Emplazamiento(
        latitud_deg=-24.79, longitud_deg=-65.41, altitud_m=1200.0,
        acimut_colector_deg=180.0, pendiente_colector_deg=30.0,
        zona_horaria="America/Argentina/Salta",
    )
    df = _df_clima_dia_claro()
    # Inyectar NaN en una hora puntual del mediodía
    h_pico = df["GHI_Wm2"].idxmax()
    df.loc[h_pico, "DNI_Wm2"] = np.nan
    poa = calcular_POA_horizonte(df, empl)
    assert float(poa.loc[h_pico]) == pytest.approx(
        float(df.loc[h_pico, "GHI_Wm2"]), rel=1e-9,
    )


def test_POA_rechaza_indice_naive():
    """Sin tz-aware en el índice, debe rechazar con mensaje claro."""
    empl = Emplazamiento(latitud_deg=-24.79, longitud_deg=-65.41,
                          altitud_m=1200.0)
    df = _df_clima_dia_claro()
    df.index = df.index.tz_localize(None)  # naive
    with pytest.raises(ValueError, match="CLIMA_INDICE_NAIVE"):
        calcular_POA_horizonte(df, empl)
