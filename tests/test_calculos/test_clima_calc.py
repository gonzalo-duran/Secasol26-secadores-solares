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

from calculos.clima_calc import _aplicar_politica_huecos, _hash_cache, calcular_POA_horizonte
from core.emplazamiento import Emplazamiento

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
    df.iloc[5:7] = np.nan  # hueco de 2 h → se interpola
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


def _df_clima_dia_claro(
    lat: float = -24.79,
    lon: float = -65.41,
    n_horas: int = 24,
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
        fecha,
        periods=n_horas,
        freq="h",
        tz="America/Argentina/Salta",
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
        ghi=ghi,
        zenith=sol_pos["apparent_zenith"],
        datetime_or_doy=idx,
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
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,  # Norte en Duffie — irrelevante con tilt=0
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
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,  # 180° en Duffie = Norte hemisferio S
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
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,
        pendiente_colector_deg=30.0,
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
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,
        pendiente_colector_deg=30.0,
        zona_horaria="America/Argentina/Salta",
    )
    df = _df_clima_dia_claro()
    # Inyectar NaN en una hora puntual del mediodía
    h_pico = df["GHI_Wm2"].idxmax()
    df.loc[h_pico, "DNI_Wm2"] = np.nan
    poa = calcular_POA_horizonte(df, empl)
    assert float(poa.loc[h_pico]) == pytest.approx(
        float(df.loc[h_pico, "GHI_Wm2"]),
        rel=1e-9,
    )


def test_POA_rechaza_indice_naive():
    """Sin tz-aware en el índice, debe rechazar con mensaje claro."""
    empl = Emplazamiento(latitud_deg=-24.79, longitud_deg=-65.41, altitud_m=1200.0)
    df = _df_clima_dia_claro()
    df.index = df.index.tz_localize(None)  # naive
    with pytest.raises(ValueError, match="CLIMA_INDICE_NAIVE"):
        calcular_POA_horizonte(df, empl)


def test_POA_crece_con_albedo_en_colector_inclinado():
    """Con tilt > 0, mayor albedo del suelo → mayor POA (componente reflejada).

    El término reflejado es GHI·ρ·(1−cos β)/2: crece monótonamente con ρ. Se
    compara la energía diurna total para ρ=0.2 vs ρ=0.6 en un colector a 30°.
    """

    def _empl(albedo: float) -> Emplazamiento:
        return Emplazamiento(
            latitud_deg=-24.79,
            longitud_deg=-65.41,
            altitud_m=1200.0,
            acimut_colector_deg=180.0,
            pendiente_colector_deg=30.0,
            zona_horaria="America/Argentina/Salta",
            albedo_suelo=albedo,
        )

    df = _df_clima_dia_claro()
    poa_bajo = calcular_POA_horizonte(df, _empl(0.20))
    poa_alto = calcular_POA_horizonte(df, _empl(0.60))
    assert poa_alto.sum() > poa_bajo.sum()


def test_POA_albedo_irrelevante_en_horizontal():
    """Con tilt = 0, (1−cos β)/2 = 0 → el albedo no cambia la POA."""

    def _empl(albedo: float) -> Emplazamiento:
        return Emplazamiento(
            latitud_deg=-24.79,
            longitud_deg=-65.41,
            altitud_m=1200.0,
            acimut_colector_deg=180.0,
            pendiente_colector_deg=0.0,
            zona_horaria="America/Argentina/Salta",
            albedo_suelo=albedo,
        )

    df = _df_clima_dia_claro()
    poa_bajo = calcular_POA_horizonte(df, _empl(0.20))
    poa_alto = calcular_POA_horizonte(df, _empl(0.90))
    np.testing.assert_allclose(poa_alto.values, poa_bajo.values, rtol=1e-9)


# =============================================================================
# slice_n_dias_consecutivos — recorte de N días reales consecutivos
# =============================================================================

from datetime import date  # noqa: E402

from calculos.clima_calc import slice_n_dias_consecutivos  # noqa: E402


def _df_multidia_dic(anio: int = 2022) -> pd.DataFrame:
    """Clima horario de diciembre de un año (tz local), valor distinto por hora."""
    idx = pd.date_range(
        f"{anio}-12-01", f"{anio}-12-31 23:00", freq="h", tz="America/Argentina/Salta"
    )
    n = len(idx)
    return pd.DataFrame(
        {
            "T_amb_K": 290.0 + np.arange(n) * 0.01,  # crece monótono → días distintos
            "GHI_Wm2": np.zeros(n),
            "DNI_Wm2": np.zeros(n),
            "DHI_Wm2": np.zeros(n),
            "WS_ms": np.full(n, 2.0),
            "presion_Pa": np.full(n, 101325.0),
            "HR": np.full(n, 0.5),
        },
        index=idx,
    )


def test_slice_consecutivo_normal():
    """Recorte de 3 días desde una fecha interior: 72 h, 3 días distintos, sin truncar."""
    df = _df_multidia_dic()
    sl, n_ef, trunc = slice_n_dias_consecutivos(df, date(2022, 12, 10), 3)
    assert len(sl) == 72
    assert n_ef == 3
    assert trunc is False
    # los días no son idénticos (T_amb crece) — a diferencia del tile del modo repetir
    dia0 = sl[sl.index.date == date(2022, 12, 10)]["T_amb_K"].to_numpy()
    dia1 = sl[sl.index.date == date(2022, 12, 11)]["T_amb_K"].to_numpy()
    assert not np.allclose(dia0, dia1)


def test_slice_consecutivo_trunca_en_borde_de_anio():
    """Pedir 5 días desde el 30-dic con clima de un solo año trunca a 2 días."""
    df = _df_multidia_dic(2022)
    sl, n_ef, trunc = slice_n_dias_consecutivos(df, date(2022, 12, 30), 5)
    assert n_ef == 2  # solo 30 y 31 de diciembre disponibles
    assert trunc is True
    assert len(sl) == 48


# ---------------------------------------------------------------------------
# slice_clima_ventana (S41 — compartido por P2/P3/P7)
# ---------------------------------------------------------------------------

from calculos.clima_calc import slice_clima_ventana  # noqa: E402
from core.clima import Clima  # noqa: E402


def test_slice_ventana_normal():
    """Ventana interior al año: devuelve el lapso completo con df no-None."""
    clima = Clima(datos=_df_multidia_dic(2022), anio=2022)
    df, msg = slice_clima_ventana(clima, date(2022, 12, 5), date(2022, 12, 12))
    assert df is not None
    assert msg == ""
    assert len(df) == 8 * 24  # 5 al 12 inclusive


def test_slice_ventana_mapea_anio_del_clima():
    """Ventana definida en otro año: se mapea por mes/día al año del clima."""
    clima = Clima(datos=_df_multidia_dic(2022), anio=2022)
    df, msg = slice_clima_ventana(clima, date(2023, 12, 5), date(2023, 12, 8))
    assert df is not None
    assert df.index[0].year == 2022


def test_slice_ventana_sin_clima():
    """Sin clima descargado → (None, mensaje)."""
    df, msg = slice_clima_ventana(None, date(2022, 12, 5), date(2022, 12, 8))
    assert df is None
    assert "Sin datos" in msg


def test_slice_ventana_lapso_fuera_de_datos():
    """Lapso que no intersecta los datos (clima solo de diciembre) → None."""
    clima = Clima(datos=_df_multidia_dic(2022), anio=2022)
    df, msg = slice_clima_ventana(clima, date(2022, 3, 1), date(2022, 3, 8))
    assert df is None
    assert "no intersecta" in msg


# ---------------------------------------------------------------------------
# POA medida en plano de colector (mejora 38, F1a)
# ---------------------------------------------------------------------------


def _empl_inclinado() -> Emplazamiento:
    return Emplazamiento(
        latitud_deg=-24.79,
        longitud_deg=-65.41,
        altitud_m=1200.0,
        acimut_colector_deg=180.0,
        pendiente_colector_deg=30.0,
        zona_horaria="America/Argentina/Salta",
    )


def test_poa_medida_directa_sin_overrides():
    """Con POA_med_Wm2 presente y sin overrides, la medición manda."""
    from core.clima import COLUMNA_POA_MEDIDA

    df = _df_clima_dia_claro()
    df[COLUMNA_POA_MEDIDA] = 555.0
    poa = calcular_POA_horizonte(df, _empl_inclinado())
    np.testing.assert_allclose(poa.values, 555.0)


def test_poa_medida_ignorada_con_tilt_override():
    """Con overrides explícitos (caras de cámara) SIEMPRE se transpone."""
    from core.clima import COLUMNA_POA_MEDIDA

    df = _df_clima_dia_claro()
    df[COLUMNA_POA_MEDIDA] = 555.0
    poa = calcular_POA_horizonte(df, _empl_inclinado(), tilt_deg=0.0, acimut_duffie_deg=0.0)
    # tilt=0 → POA ≈ GHI, no la constante medida
    diurno = df["GHI_Wm2"] > 50.0
    np.testing.assert_allclose(poa[diurno].values, df["GHI_Wm2"][diurno].values, rtol=1e-2)


def test_poa_medida_nan_cae_a_transposicion():
    """Las horas con medida NaN se rellenan con la transposición estándar."""
    from core.clima import COLUMNA_POA_MEDIDA

    df = _df_clima_dia_claro()
    empl = _empl_inclinado()
    poa_trans = calcular_POA_horizonte(df.copy(), empl)
    df[COLUMNA_POA_MEDIDA] = 555.0
    df.loc[df.index[12], COLUMNA_POA_MEDIDA] = np.nan
    poa = calcular_POA_horizonte(df, empl)
    assert poa.iloc[12] == pytest.approx(poa_trans.iloc[12])
    assert poa.iloc[13] == pytest.approx(555.0)


def test_poa_medida_clip_negativos():
    from core.clima import COLUMNA_POA_MEDIDA

    df = _df_clima_dia_claro()
    df[COLUMNA_POA_MEDIDA] = -4.0
    poa = calcular_POA_horizonte(df, _empl_inclinado())
    assert (poa.values == 0.0).all()


def test_dia_tipo_mensual_preserva_poa_medida():
    """El día típico mensual promedia también la columna de POA medida."""
    from calculos.clima_calc import dia_tipo_mensual
    from core.clima import COLUMNA_POA_MEDIDA

    df = _df_multidia_dic(2022)
    df[COLUMNA_POA_MEDIDA] = 321.0
    dia = dia_tipo_mensual(df, 12, tz_local="America/Argentina/Salta")
    assert COLUMNA_POA_MEDIDA in dia.columns
    np.testing.assert_allclose(dia[COLUMNA_POA_MEDIDA].values, 321.0)


# ---------------------------------------------------------------------------
# resolver_datos_trabajo (mejora 38, fase 1b — paso de trabajo sub-horario)
# ---------------------------------------------------------------------------

from calculos.clima_calc import resolver_datos_trabajo  # noqa: E402


def test_resolver_horario_devuelve_datos_intactos():
    """paso 3600 → clima.datos tal cual, sin advertencias (camino histórico)."""
    clima = Clima(datos=_df_multidia_dic(2022), anio=2022)
    df, adv = resolver_datos_trabajo(clima, 3600.0)
    assert df is clima.datos
    assert adv == []


def test_resolver_none_sin_datos():
    df, adv = resolver_datos_trabajo(None, 900.0)
    assert df is None
    assert adv == []


def test_resolver_subhorario_nasa_interpola_y_avisa():
    """Clima solo horario (NASA) a 15 min → baseline sintético + ADV_PASO_SINTETICO."""
    clima = Clima(datos=_df_multidia_dic(2022), anio=2022)
    df, adv = resolver_datos_trabajo(clima, 900.0)
    assert df is not None
    # Grilla de 15 min: 4× más puntos que la horaria (aprox).
    paso = df.index[1] - df.index[0]
    assert paso == pd.Timedelta("15min")
    assert any("ADV_PASO_SINTETICO" in a for a in adv)
    # Interpolación lineal de T_amb entre dos horas consecutivas.
    t0 = clima.datos["T_amb_K"].iloc[0]
    t1 = clima.datos["T_amb_K"].iloc[1]
    assert df["T_amb_K"].iloc[1] == pytest.approx(t0 + (t1 - t0) * 0.25, rel=1e-6)


def test_resolver_subhorario_con_nativo_usa_real():
    """Con datos_nativos a 5 min, el paso 15 min NO marca esa columna como sintética."""
    idx_h = pd.date_range("2022-12-01", periods=6, freq="h", tz="UTC")
    datos = pd.DataFrame(
        {
            "T_amb_K": 290.0 + np.arange(6) * 1.0,
            "GHI_Wm2": np.zeros(6),
            "DNI_Wm2": np.zeros(6),
            "DHI_Wm2": np.zeros(6),
            "WS_ms": np.full(6, 2.0),
            "presion_Pa": np.full(6, 101325.0),
            "HR": np.full(6, 0.5),
        },
        index=idx_h,
    )
    idx_n = pd.date_range("2022-12-01", "2022-12-01 05:00", freq="5min", tz="UTC")
    nativos = pd.DataFrame({"T_amb_K": 300.0 + np.arange(len(idx_n)) * 0.1}, index=idx_n)
    clima = Clima(datos=datos, anio=2022)
    clima.datos_nativos = nativos
    clima.frecuencia_nativa_s = 300.0

    df, adv = resolver_datos_trabajo(clima, 900.0)
    # T_amb viene del nativo real (~300 K), no del baseline horario (~290 K).
    assert df["T_amb_K"].iloc[0] == pytest.approx(300.0, abs=0.5)
    # La advertencia sintética menciona las columnas SIN nativo, no T_amb_K.
    assert adv  # sigue habiendo columnas sintéticas (GHI, HR, etc.)
    assert all("T_amb_K" not in a.split("(")[-1] for a in adv)
