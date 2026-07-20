"""Tests del pipeline de ingesta de clima medido (calculos/clima_medido.py).

Fixture central: tabla sintética "estilo ADITAL" que reproduce las trampas del
dataset real (docs/notas/dataset/secador ADITAL - Toto San Carlos): timestamps
como serial Excel en hora local, strings 'NAN', hueco de 220 min, canales de
proceso del secador mezclados con los climáticos, y una columna de señal cruda
fuera de rango físico.
"""

import json

import numpy as np
import pandas as pd
import pytest

from calculos.clima_medido import (
    aplicar_mapeo,
    completar_con_nasa,
    derivar_dni_dhi_erbs,
    inferir_frecuencia_s,
    ingerir_clima_medido,
    leer_tabla,
    listar_hojas,
    meses_cubiertos,
    qc_fisico,
    regularizar_grilla,
    remuestrear_horario,
    sugerir_mapeo,
)
from core.clima import COLUMNA_POA_MEDIDA, COLUMNAS_SI, CalidadClima, Clima
from core.clima_medido import (
    PROCEDENCIA_DERIVADA,
    PROCEDENCIA_MEDIDA,
    PROCEDENCIA_NASA,
    ConfigMapeoClima,
    MapeoColumna,
)
from core.emplazamiento import Emplazamiento

_TZ = "America/Argentina/Salta"  # UTC-3 (sin DST)
_LAT, _LON, _ALT = -25.9, -65.93, 1700.0
_ORIGEN_SERIAL = pd.Timestamp("1899-12-30")


def _emplazamiento() -> Emplazamiento:
    return Emplazamiento(latitud_deg=_LAT, longitud_deg=_LON, altitud_m=_ALT)


def _serial_excel(idx_local_naive: pd.DatetimeIndex) -> np.ndarray:
    """Convierte timestamps naive locales a serial Excel (float, días)."""
    return (idx_local_naive - _ORIGEN_SERIAL) / pd.Timedelta("1D")


def _tabla_adital(n_dias: int = 3, con_hueco: bool = True, anio: int = 2010) -> pd.DataFrame:
    """Tabla cruda 10-minutal estilo ADITAL (hora local, serial Excel)."""
    idx = pd.date_range(f"{anio}-05-01 00:00", periods=n_dias * 144, freq="10min")
    horas = (idx.hour + idx.minute / 60.0).to_numpy()

    t_amb_c = 15.0 + 10.0 * np.sin(np.pi * (horas - 6.0) / 12.0).clip(min=-0.7)
    rad = 900.0 * np.sin(np.pi * (horas - 7.0) / 11.0).clip(min=0.0)
    hr_pct = 60.0 - 35.0 * np.sin(np.pi * (horas - 6.0) / 12.0).clip(min=-0.8)

    df = pd.DataFrame(
        {
            "TIMESTAMP": _serial_excel(idx),
            "RECORD": np.arange(len(idx)),
            "Radiacion horizontal": rad.round(1),
            "Temperatura ambiente": t_amb_c.round(2).astype(object),
            "HR amb": hr_pct.round(1),
            "Temp entr caño": (t_amb_c + 20.0).round(2),
            "Temp salida col1": (t_amb_c + 30.0).round(2),
            "HR entrada": np.linspace(-1.8, 14.5, len(idx)).round(2),
            "DiffVolt(1)": np.full(len(idx), -111.0),
        }
    )
    # 'NAN' strings salpicados en la temperatura (marcador Campbell)
    df.loc[10:14, "Temperatura ambiente"] = "NAN"
    if con_hueco:
        # hueco de 220 min el primer día a las 08:50 (22 filas de 10 min)
        df = df.drop(index=range(53, 75)).reset_index(drop=True)
    return df


def _config_adital(**kwargs) -> ConfigMapeoClima:
    base = dict(
        columna_timestamp="TIMESTAMP",
        zona_horaria=_TZ,
        columnas=[
            MapeoColumna("T_amb_K", "Temperatura ambiente", "C"),
            MapeoColumna("GHI_Wm2", "Radiacion horizontal", "W_m2"),
            MapeoColumna("HR", "HR amb", "porcentaje"),
        ],
    )
    base.update(kwargs)
    return ConfigMapeoClima(**base)


def _clima_nasa_fake(anio: int = 2010) -> Clima:
    """Clima NASA sintético de año completo, horario UTC, valores distintivos."""
    idx = pd.date_range(f"{anio}-01-01", f"{anio}-12-31 23:00", freq="h", tz="UTC")
    datos = pd.DataFrame(
        {
            "T_amb_K": 290.0,
            "GHI_Wm2": 400.0,
            "DNI_Wm2": 500.0,
            "DHI_Wm2": 120.0,
            "WS_ms": 2.5,
            "presion_Pa": 83_000.0,
            "HR": 0.45,
        },
        index=idx,
    )
    return Clima(datos=datos, anio=anio, calidad=CalidadClima(), altitud_nasa_m=1500.0)


def _fn_nasa_fake(emplazamiento, anio, **kwargs):
    return _clima_nasa_fake(anio)


# ---------------------------------------------------------------------------
# E2 — lectura
# ---------------------------------------------------------------------------


class TestLectura:
    def test_leer_tabla_csv_bytes_regional(self):
        # CSV "argentino": separador ';' y decimal ','
        csv_texto = "fecha;temp;rad\n01/05/2010 00:00;15,5;0,0\n01/05/2010 00:10;15,2;0,0\n"
        df = leer_tabla(csv_texto.encode("utf-8"), "datos.csv")
        assert list(df.columns) == ["fecha", "temp", "rad"]
        assert df["temp"].iloc[0] == pytest.approx(15.5)

    def test_leer_tabla_csv_coma(self):
        csv_texto = "fecha,temp\n2010-05-01 00:00,15.5\n2010-05-01 00:10,15.2\n"
        df = leer_tabla(csv_texto.encode("utf-8"), "datos.csv")
        assert df["temp"].iloc[1] == pytest.approx(15.2)

    def test_listar_hojas_csv_none(self):
        assert listar_hojas(b"a,b\n1,2\n", "datos.csv") is None

    def test_CLIMED_FORMATO_NO_SOPORTADO(self):
        with pytest.raises(ValueError, match="CLIMED_FORMATO_NO_SOPORTADO"):
            leer_tabla(b"", "datos.parquet")

    def test_CLIMED_LECTURA_FALLIDA_excel_corrupto(self):
        with pytest.raises(RuntimeError, match="CLIMED_LECTURA_FALLIDA"):
            listar_hojas(b"esto no es un xls", "datos.xls")


# ---------------------------------------------------------------------------
# E2 — sugerencia de mapeo
# ---------------------------------------------------------------------------


class TestSugerirMapeo:
    def test_sugerencia_sobre_headers_adital(self):
        cfg = sugerir_mapeo(_tabla_adital().columns)
        assert cfg.columna_timestamp == "TIMESTAMP"
        variables = dict((m.variable, m.columna_origen) for m in cfg.columnas)
        assert variables.get("T_amb_K") == "Temperatura ambiente"
        assert variables.get("GHI_Wm2") == "Radiacion horizontal"
        assert variables.get("HR") == "HR amb"

    def test_no_sugiere_canales_de_proceso(self):
        cfg = sugerir_mapeo(_tabla_adital().columns)
        origenes = [m.columna_origen for m in cfg.columnas]
        for canal in ("Temp entr caño", "Temp salida col1", "HR entrada", "DiffVolt(1)"):
            assert canal not in origenes

    def test_sin_columnas_devuelve_config_vacia(self):
        cfg = sugerir_mapeo([])
        assert cfg.columnas == []


# ---------------------------------------------------------------------------
# E2 — aplicar_mapeo
# ---------------------------------------------------------------------------


class TestAplicarMapeo:
    def test_nan_strings_a_nan(self):
        df = aplicar_mapeo(_tabla_adital(con_hueco=False), _config_adital())
        assert df["T_amb_K"].iloc[10:15].isna().all()

    def test_tz_local_a_utc(self):
        df = aplicar_mapeo(_tabla_adital(con_hueco=False), _config_adital())
        # 2010-05-01 00:00 -03 == 03:00 UTC
        assert df.index[0] == pd.Timestamp("2010-05-01 03:00", tz="UTC")
        assert str(df.index.tz) == "UTC"

    def test_unidades_C_y_porcentaje(self):
        tabla = _tabla_adital(con_hueco=False)
        df = aplicar_mapeo(tabla, _config_adital())
        assert df["T_amb_K"].iloc[0] == pytest.approx(
            float(tabla["Temperatura ambiente"].iloc[0]) + 273.15
        )
        assert df["HR"].iloc[0] == pytest.approx(tabla["HR amb"].iloc[0] / 100.0)

    def test_viento_3m_a_2m(self):
        tabla = _tabla_adital(con_hueco=False)
        tabla["Viento"] = 3.0
        cfg = _config_adital(
            columnas=[MapeoColumna("WS_ms", "Viento", "m_s")],
            altura_anemometro_m=3.0,
        )
        df = aplicar_mapeo(tabla, cfg)
        factor = np.log(2.0 / 0.05) / np.log(3.0 / 0.05)
        assert df["WS_ms"].iloc[0] == pytest.approx(3.0 * factor)

    def test_plano_colector_renombra_a_poa(self):
        cfg = _config_adital(plano_piranometro="plano_colector")
        df = aplicar_mapeo(_tabla_adital(con_hueco=False), cfg)
        assert COLUMNA_POA_MEDIDA in df.columns
        assert "GHI_Wm2" not in df.columns

    def test_timestamp_duplicado_keep_first(self):
        tabla = _tabla_adital(con_hueco=False)
        tabla = pd.concat([tabla, tabla.iloc[[5]]], ignore_index=True)
        df = aplicar_mapeo(tabla, _config_adital())
        assert not df.index.duplicated().any()

    def test_CLIMED_COLUMNA_INEXISTENTE(self):
        cfg = _config_adital(columnas=[MapeoColumna("T_amb_K", "NoExiste", "C")])
        with pytest.raises(ValueError, match="CLIMED_COLUMNA_INEXISTENTE"):
            aplicar_mapeo(_tabla_adital(), cfg)

    def test_CLIMED_SIN_VARIABLES(self):
        cfg = _config_adital(columnas=[])
        with pytest.raises(ValueError, match="CLIMED_SIN_VARIABLES"):
            aplicar_mapeo(_tabla_adital(), cfg)

    def test_CLIMED_TZ_INVALIDA(self):
        cfg = _config_adital(zona_horaria="America/Ciudad_Inventada")
        with pytest.raises(ValueError, match="CLIMED_TZ_INVALIDA"):
            aplicar_mapeo(_tabla_adital(), cfg)

    def test_timestamps_texto_dayfirst(self):
        tabla = pd.DataFrame(
            {
                "fecha": ["01/05/2010 00:00", "01/05/2010 00:10", "01/05/2010 00:20"],
                "temp": [15.0, 15.1, 15.2],
            }
        )
        cfg = ConfigMapeoClima(
            columna_timestamp="fecha",
            zona_horaria=_TZ,
            columnas=[MapeoColumna("T_amb_K", "temp", "C")],
        )
        df = aplicar_mapeo(tabla, cfg)
        assert df.index[0] == pd.Timestamp("2010-05-01 03:00", tz="UTC")


# ---------------------------------------------------------------------------
# E2 — frecuencia, grilla, remuestreo
# ---------------------------------------------------------------------------


class TestFrecuenciaYRemuestreo:
    def test_inferir_frecuencia_600s(self):
        df = aplicar_mapeo(_tabla_adital(), _config_adital())
        assert inferir_frecuencia_s(df.index) == pytest.approx(600.0)

    def test_CLIMED_FRECUENCIA_IRREGULAR(self):
        base = pd.Timestamp("2010-05-01", tz="UTC")
        saltos = np.cumsum(np.tile([600, 300, 900, 60], 10))
        idx = pd.DatetimeIndex([base + pd.Timedelta(seconds=int(s)) for s in saltos])
        with pytest.raises(ValueError, match="CLIMED_FRECUENCIA_IRREGULAR"):
            inferir_frecuencia_s(idx)

    def test_regularizar_grilla_hueco_como_nan(self):
        df = aplicar_mapeo(_tabla_adital(con_hueco=True), _config_adital())
        reg = regularizar_grilla(df, 600.0)
        # el hueco de 220 min reaparece como 22 filas NaN
        assert len(reg) == len(df) + 22
        assert int(reg["T_amb_K"].isna().sum()) >= 22

    def test_remuestreo_media_horaria_etiqueta_inicio(self):
        idx = pd.date_range("2010-05-01 00:00", periods=12, freq="10min", tz="UTC")
        df = pd.DataFrame({"T_amb_K": np.arange(12.0) + 290.0}, index=idx)
        res = remuestrear_horario(df, paso_nativo_s=600.0)
        assert res.index[0] == idx[0]
        assert res["T_amb_K"].iloc[0] == pytest.approx(np.mean(np.arange(6.0) + 290.0))
        assert res["T_amb_K"].iloc[1] == pytest.approx(np.mean(np.arange(6.0, 12.0) + 290.0))

    def test_remuestreo_hora_con_pocas_muestras_es_nan(self):
        idx = pd.date_range("2010-05-01 00:00", periods=12, freq="10min", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 300.0}, index=idx)
        df.iloc[6:10, 0] = np.nan  # segunda hora: solo 2 de 6 muestras válidas
        res = remuestrear_horario(df, paso_nativo_s=600.0)
        assert np.isnan(res["T_amb_K"].iloc[1])
        assert res["T_amb_K"].iloc[0] == pytest.approx(300.0)

    def test_remuestreo_promedio_fin_corre_media_muestra(self):
        # Valores "promedio del intervalo que termina en t": el valor de las
        # 01:00 pertenece a la hora [00:00, 01:00) y no a la [01:00, 02:00).
        idx = pd.date_range("2010-05-01 00:10", periods=12, freq="10min", tz="UTC")
        df = pd.DataFrame({"GHI_Wm2": [100.0] * 6 + [200.0] * 6}, index=idx)
        res = remuestrear_horario(df, paso_nativo_s=600.0, convencion="promedio_fin")
        assert res["GHI_Wm2"].iloc[0] == pytest.approx(100.0)

    # --- Fase 1b: remuestreo a paso arbitrario ---

    def test_remuestrear_a_paso_agrega_a_15min(self):
        """Nativo 5 min → paso de trabajo 15 min: media de 3 muestras por bin."""
        from calculos.clima_medido import remuestrear_a_paso

        idx = pd.date_range("2010-05-01 00:00", periods=12, freq="5min", tz="UTC")
        df = pd.DataFrame({"T_amb_K": np.arange(12.0) + 290.0}, index=idx)
        res = remuestrear_a_paso(df, paso_nativo_s=300.0, paso_destino_s=900.0)
        # 12 muestras de 5 min = 60 min → 4 bines de 15 min.
        assert len(res) == 4
        assert (res.index.freq or (res.index[1] - res.index[0])) == pd.Timedelta("15min")
        assert res["T_amb_K"].iloc[0] == pytest.approx(np.mean([290.0, 291.0, 292.0]))

    def test_remuestrear_a_paso_upsampling_interpola(self):
        """Nativo 15 min → paso 5 min (más fino que el nativo) → interpolación lineal."""
        from calculos.clima_medido import remuestrear_a_paso

        idx = pd.date_range("2010-05-01 00:00", periods=5, freq="15min", tz="UTC")
        df = pd.DataFrame({"T_amb_K": [290.0, 293.0, 296.0, 299.0, 302.0]}, index=idx)
        res = remuestrear_a_paso(df, paso_nativo_s=900.0, paso_destino_s=300.0)
        # Punto intermedio 00:05 = 290 + (293-290)/3 = 291.0 (lineal en el tiempo).
        assert res["T_amb_K"].loc["2010-05-01 00:05+00:00"] == pytest.approx(291.0)
        assert res["T_amb_K"].iloc[0] == pytest.approx(290.0)

    def test_remuestrear_horario_es_caso_particular(self):
        """remuestrear_horario == remuestrear_a_paso con paso_destino 3600."""
        from calculos.clima_medido import remuestrear_a_paso

        idx = pd.date_range("2010-05-01 00:00", periods=12, freq="10min", tz="UTC")
        df = pd.DataFrame({"T_amb_K": np.arange(12.0) + 290.0}, index=idx)
        a = remuestrear_horario(df, paso_nativo_s=600.0)
        b = remuestrear_a_paso(df, paso_nativo_s=600.0, paso_destino_s=3600.0)
        pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------------------
# E3 — QC físico
# ---------------------------------------------------------------------------


class TestQCFisico:
    def _df_utc(self, n_horas: int = 24, paso_s: float = 600.0) -> pd.DataFrame:
        idx = pd.date_range(
            "2010-05-01 03:00", periods=int(n_horas * 3600 / paso_s), freq="10min", tz="UTC"
        )
        horas_loc = (idx.tz_convert(_TZ).hour + idx.tz_convert(_TZ).minute / 60.0).to_numpy()
        rad = 900.0 * np.clip(np.sin(np.pi * (horas_loc - 7.0) / 11.0), 0.0, None)
        return pd.DataFrame(
            {
                "T_amb_K": 290.0 + 5.0 * np.sin(horas_loc),
                "GHI_Wm2": rad,
                "HR": 0.5 + 0.0 * horas_loc,
            },
            index=idx,
        )

    def test_rango_fisico_marca_nan(self):
        df = self._df_utc()
        df.iloc[3, df.columns.get_loc("T_amb_K")] = 999.0
        limpio, rep = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert np.isnan(limpio["T_amb_K"].iloc[3])
        assert any(c.codigo == "rango_fisico" and c.variable == "T_amb_K" for c in rep.chequeos)

    def test_hr_leve_se_clipea_no_anula(self):
        df = self._df_utc()
        df.iloc[4, df.columns.get_loc("HR")] = 1.015
        limpio, _ = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert limpio["HR"].iloc[4] == pytest.approx(1.0)

    def test_irradiancia_negativa_leve_a_cero(self):
        df = self._df_utc()
        df.iloc[5, df.columns.get_loc("GHI_Wm2")] = -3.0
        limpio, _ = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert limpio["GHI_Wm2"].iloc[5] == pytest.approx(0.0)

    def test_ghi_nocturna_clip(self):
        df = self._df_utc()
        # 03:00 UTC = medianoche local → sol bien abajo
        df.iloc[0, df.columns.get_loc("GHI_Wm2")] = 150.0
        limpio, rep = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert limpio["GHI_Wm2"].iloc[0] == pytest.approx(0.0)
        assert any(c.codigo == "ghi_nocturna" for c in rep.chequeos)

    def test_ghi_supera_extraterrestre_nan(self):
        df = self._df_utc()
        # mediodía local (≈ 15:00-16:00 UTC): GHI absurda de 1400 W/m² en mayo
        mediodia = df.index.tz_convert(_TZ).hour == 13
        df.loc[mediodia, "GHI_Wm2"] = 1400.0
        limpio, rep = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert limpio.loc[mediodia, "GHI_Wm2"].isna().all()
        assert any(c.codigo == "ghi_extraterrestre" for c in rep.chequeos)

    def test_sensor_congelado_solo_aviso(self):
        df = self._df_utc()
        df.iloc[10:40, df.columns.get_loc("T_amb_K")] = 293.15  # 5 h idénticas
        limpio, rep = qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        # aviso presente pero valores intactos
        assert any(c.codigo == "sensor_congelado" and c.variable == "T_amb_K" for c in rep.chequeos)
        assert limpio["T_amb_K"].iloc[20] == pytest.approx(293.15)

    def test_CLIMED_TODO_INVALIDO(self):
        df = self._df_utc()
        df["HR"] = 55.0  # "porcentaje" sin convertir: 55 > 1.02 en TODAS las filas
        with pytest.raises(ValueError, match="CLIMED_TODO_INVALIDO.*HR"):
            qc_fisico(df, lat=_LAT, lon=_LON, alt_m=_ALT)


# ---------------------------------------------------------------------------
# E4 — derivación, completado, orquestador
# ---------------------------------------------------------------------------


class TestDerivacionYCompletado:
    def test_erbs_deriva_dni_dhi_coherentes(self):
        idx = pd.date_range("2010-05-01 03:00", periods=48, freq="h", tz="UTC")
        horas_loc = idx.tz_convert(_TZ).hour.to_numpy()
        ghi = 800.0 * np.clip(np.sin(np.pi * (horas_loc - 7.0) / 11.0), 0.0, None)
        df = pd.DataFrame({"GHI_Wm2": ghi}, index=idx)
        out, derivadas = derivar_dni_dhi_erbs(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert set(derivadas) == {"DNI_Wm2", "DHI_Wm2"}
        # cierre físico GHI ≈ DHI + DNI·cos(z) donde hay sol
        import pvlib

        solpos = pvlib.solarposition.get_solarposition(idx, _LAT, _LON, altitude=_ALT)
        cosz = np.cos(np.radians(solpos["apparent_zenith"].to_numpy())).clip(min=0)
        con_sol = ghi > 100.0
        recompuesta = out["DHI_Wm2"].to_numpy() + out["DNI_Wm2"].to_numpy() * cosz
        assert np.allclose(recompuesta[con_sol], ghi[con_sol], rtol=0.05)

    def test_no_deriva_si_ya_estan(self):
        idx = pd.date_range("2010-05-01", periods=24, freq="h", tz="UTC")
        df = pd.DataFrame({"GHI_Wm2": 500.0, "DNI_Wm2": 600.0, "DHI_Wm2": 100.0}, index=idx)
        out, derivadas = derivar_dni_dhi_erbs(df, lat=_LAT, lon=_LON, alt_m=_ALT)
        assert derivadas == []
        assert out["DNI_Wm2"].iloc[0] == pytest.approx(600.0)

    def test_completar_columnas_ausentes_desde_nasa_alineado(self):
        idx = pd.date_range("2010-05-01 03:00", periods=72, freq="h", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 295.0, "GHI_Wm2": 300.0}, index=idx)
        out, proc, alt_nasa = completar_con_nasa(
            df, _emplazamiento(), 2010, obtener_clima_fn=_fn_nasa_fake
        )
        assert list(out.columns) == list(COLUMNAS_SI)
        assert out["WS_ms"].iloc[0] == pytest.approx(2.5)
        assert out["presion_Pa"].iloc[0] == pytest.approx(83_000.0)
        assert proc == {
            "DNI_Wm2": PROCEDENCIA_NASA,
            "DHI_Wm2": PROCEDENCIA_NASA,
            "WS_ms": PROCEDENCIA_NASA,
            "presion_Pa": PROCEDENCIA_NASA,
            "HR": PROCEDENCIA_NASA,
        }
        assert alt_nasa == pytest.approx(1500.0)

    def test_completo_no_descarga_nada(self):
        idx = pd.date_range("2010-05-01", periods=24, freq="h", tz="UTC")
        df = pd.DataFrame({c: 1.0 for c in COLUMNAS_SI}, index=idx)

        def _fn_explota(*a, **k):
            raise AssertionError("no debería descargarse NASA")

        out, proc, alt_nasa = completar_con_nasa(
            df, _emplazamiento(), 2010, obtener_clima_fn=_fn_explota
        )
        assert proc == {} and alt_nasa is None

    def test_CLIMED_ANIO_FUERA_NASA(self):
        idx = pd.date_range("2035-05-01", periods=24, freq="h", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 295.0}, index=idx)
        with pytest.raises(ValueError, match="CLIMED_ANIO_FUERA_NASA"):
            completar_con_nasa(df, _emplazamiento(), 2035, obtener_clima_fn=_fn_nasa_fake)

    def test_CLIMED_COMPLETADO_FALLIDO(self):
        idx = pd.date_range("2010-05-01", periods=24, freq="h", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 295.0}, index=idx)

        def _fn_falla(*a, **k):
            raise RuntimeError("CLIMA_DESCARGA_FALLIDA: sin red")

        with pytest.raises(RuntimeError, match="CLIMED_COMPLETADO_FALLIDO"):
            completar_con_nasa(df, _emplazamiento(), 2010, obtener_clima_fn=_fn_falla)


class TestMesesCubiertos:
    def test_parcial(self):
        idx = pd.date_range("2010-04-14", "2010-06-18", freq="h", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 290.0, "GHI_Wm2": 300.0}, index=idx)
        assert meses_cubiertos(df, _TZ) == (4, 5, 6)

    def test_mes_con_pocas_horas_no_cuenta(self):
        idx = pd.date_range("2010-04-30 20:00", "2010-05-31", freq="h", tz="UTC")
        df = pd.DataFrame({"T_amb_K": 290.0, "GHI_Wm2": 300.0}, index=idx)
        # abril solo aporta ~7 h (< 24) → no cuenta
        assert meses_cubiertos(df, _TZ) == (5,)

    def test_vacio(self):
        assert meses_cubiertos(pd.DataFrame()) == ()


class TestIngerirEndToEnd:
    def test_ingesta_adital_hibrida(self):
        clima = ingerir_clima_medido(
            _tabla_adital(),
            _config_adital(),
            _emplazamiento(),
            obtener_clima_fn=_fn_nasa_fake,
        )
        # contrato
        assert list(clima.datos.columns) == list(COLUMNAS_SI)
        assert str(clima.datos.index.tz) == "UTC"
        assert clima.anio == 2010
        # fuente y procedencia
        assert clima.fuente == "hibrido"
        assert clima.procedencia["T_amb_K"] == PROCEDENCIA_MEDIDA
        assert clima.procedencia["GHI_Wm2"] == PROCEDENCIA_MEDIDA
        assert clima.procedencia["HR"] == PROCEDENCIA_MEDIDA
        assert clima.procedencia["DNI_Wm2"] == PROCEDENCIA_DERIVADA
        assert clima.procedencia["DHI_Wm2"] == PROCEDENCIA_DERIVADA
        assert clima.procedencia["WS_ms"] == PROCEDENCIA_NASA
        assert clima.procedencia["presion_Pa"] == PROCEDENCIA_NASA
        # nativo preservado para 1b
        assert clima.frecuencia_nativa_s == pytest.approx(600.0)
        assert clima.datos_nativos is not None
        assert len(clima.datos_nativos) > len(clima.datos)
        # reporte QC poblado
        assert clima.qc is not None
        assert clima.qc.meses_cubiertos == (5,)
        assert clima.mapeo is not None
        assert clima.altitud_nasa_m == pytest.approx(1500.0)

    def test_ingesta_todo_medido_es_fuente_medido(self):
        tabla = _tabla_adital(con_hueco=False)
        tabla["Viento"] = 2.0
        tabla["Presion"] = 830.0  # hPa
        tabla["Directa"] = 500.0
        tabla["Difusa"] = 100.0
        cfg = _config_adital(
            columnas=[
                MapeoColumna("T_amb_K", "Temperatura ambiente", "C"),
                MapeoColumna("GHI_Wm2", "Radiacion horizontal", "W_m2"),
                MapeoColumna("HR", "HR amb", "porcentaje"),
                MapeoColumna("WS_ms", "Viento", "m_s"),
                MapeoColumna("presion_Pa", "Presion", "hPa"),
                MapeoColumna("DNI_Wm2", "Directa", "W_m2"),
                MapeoColumna("DHI_Wm2", "Difusa", "W_m2"),
            ]
        )

        def _fn_explota(*a, **k):
            raise AssertionError("no debería descargarse NASA")

        clima = ingerir_clima_medido(tabla, cfg, _emplazamiento(), obtener_clima_fn=_fn_explota)
        assert clima.fuente == "medido"
        assert clima.altitud_nasa_m is None
        assert set(clima.procedencia.values()) == {PROCEDENCIA_MEDIDA}

    def test_CLIMED_PERIODO_MULTIANIO(self):
        idx = pd.date_range("2010-12-30 00:00", periods=6 * 144, freq="10min")
        tabla = pd.DataFrame(
            {
                "TIMESTAMP": _serial_excel(idx),
                "Temperatura ambiente": 20.0,
                "Radiacion horizontal": 300.0,
                "HR amb": 50.0,
            }
        )
        with pytest.raises(ValueError, match="CLIMED_PERIODO_MULTIANIO"):
            ingerir_clima_medido(
                tabla, _config_adital(), _emplazamiento(), obtener_clima_fn=_fn_nasa_fake
            )

    def test_resultado_compatible_con_consumidores(self):
        from calculos.clima_calc import dia_tipo_mensual, slice_clima_ventana

        clima = ingerir_clima_medido(
            _tabla_adital(),
            _config_adital(),
            _emplazamiento(),
            obtener_clima_fn=_fn_nasa_fake,
        )
        dia = dia_tipo_mensual(clima.datos, 5, tz_local=_TZ)
        assert len(dia) == 24
        from datetime import date

        rec, msg = slice_clima_ventana(clima, date(2010, 5, 1), date(2010, 5, 2))
        assert rec is not None and len(rec) > 0


# ---------------------------------------------------------------------------
# E6 — cache parquet + serialización del mapeo
# ---------------------------------------------------------------------------


class TestCacheMedido:
    def _clima(self):
        return ingerir_clima_medido(
            _tabla_adital(),
            _config_adital(),
            _emplazamiento(),
            obtener_clima_fn=_fn_nasa_fake,
        )

    def test_cache_roundtrip_preserva_todo(self, tmp_path):
        from calculos.clima_medido import (
            cargar_cache_medido,
            guardar_cache_medido,
            hash_archivo,
            hash_ingesta,
        )

        clima = self._clima()
        h = hash_ingesta(hash_archivo(b"contenido"), clima.mapeo)
        guardar_cache_medido(clima, h, dir_cache=tmp_path)
        rec = cargar_cache_medido(h, dir_cache=tmp_path)

        assert rec is not None
        pd.testing.assert_frame_equal(rec.datos, clima.datos, check_freq=False)
        pd.testing.assert_frame_equal(rec.datos_nativos, clima.datos_nativos, check_freq=False)
        assert rec.fuente == clima.fuente
        assert rec.anio == clima.anio
        assert rec.procedencia == clima.procedencia
        assert rec.frecuencia_nativa_s == clima.frecuencia_nativa_s
        assert rec.altitud_nasa_m == clima.altitud_nasa_m
        assert rec.calidad == clima.calidad
        assert rec.qc == clima.qc
        assert rec.mapeo == clima.mapeo

    def test_hash_ingesta_cambia_con_mapeo(self):
        from calculos.clima_medido import hash_archivo, hash_ingesta

        h_arch = hash_archivo(b"contenido")
        cfg1 = _config_adital()
        cfg2 = _config_adital(convencion_timestamp="promedio_fin")
        assert hash_ingesta(h_arch, cfg1) != hash_ingesta(h_arch, cfg2)
        assert hash_ingesta(h_arch, cfg1) == hash_ingesta(h_arch, _config_adital())

    def test_config_roundtrip_dict(self):
        from calculos.clima_medido import config_a_dict, config_desde_dict

        cfg = _config_adital(altura_anemometro_m=3.0, hoja="Hoja1")
        rec = config_desde_dict(json.loads(json.dumps(config_a_dict(cfg))))
        assert rec == cfg

    def test_cargar_cache_inexistente_none(self, tmp_path):
        from calculos.clima_medido import cargar_cache_medido

        assert cargar_cache_medido("0" * 64, dir_cache=tmp_path) is None


class TestErroresLectura:
    """Códigos de error de lectura detectados por el revisor de convenciones (S51)."""

    def test_CLIMED_HOJA_INEXISTENTE(self):
        import io

        buf = io.BytesIO()
        pd.DataFrame({"a": [1.0]}).to_excel(buf, sheet_name="Datos", index=False)
        with pytest.raises(ValueError, match="CLIMED_HOJA_INEXISTENTE"):
            leer_tabla(buf.getvalue(), "datos.xlsx", hoja="NoExiste")

    def test_CLIMED_TIMESTAMP_INVALIDO(self):
        tabla = pd.DataFrame(
            {
                "TIMESTAMP": ["basura", "sin fecha", "???"],
                "Temperatura ambiente": [15.0, 16.0, 17.0],
            }
        )
        cfg = _config_adital(columnas=[MapeoColumna("T_amb_K", "Temperatura ambiente", "C")])
        with pytest.raises(ValueError, match="CLIMED_TIMESTAMP_INVALIDO"):
            aplicar_mapeo(tabla, cfg)


# ---------------------------------------------------------------------------
# Fase 1a + fecha fija / datetime.time (regresión: prototipo colector 10 m)
# ---------------------------------------------------------------------------


class TestFechaFijaClimaMedido:

    def _df_hora_time(self, n=6):
        from datetime import time

        return pd.DataFrame(
            {
                "hora": [time(9, i * 5 // 1) if i * 5 < 60 else time(10, 0) for i in range(n)],
                "Ta": [15.0 + i for i in range(n)],
                "I": [700.0 + 10 * i for i in range(n)],
            }
        )

    def test_aplicar_mapeo_con_fecha_fija_y_datetime_time(self):
        from datetime import date

        from calculos.clima_medido import aplicar_mapeo
        from core.clima_medido import ConfigMapeoClima, MapeoColumna

        df = self._df_hora_time()
        cfg = ConfigMapeoClima(
            columna_timestamp="hora",
            zona_horaria="America/Argentina/Salta",
            columnas=[MapeoColumna("T_amb_K", "Ta", "C"), MapeoColumna("POA_med_Wm2", "I", "W_m2")],
            plano_piranometro="plano_colector",
            fecha_fija=date(2007, 6, 9),
        )
        out = aplicar_mapeo(df, cfg)
        assert len(out) == 6
        # 09:00 Salta (UTC−3) → 12:00 UTC del 2007-06-09.
        assert out.index[0] == pd.Timestamp("2007-06-09 12:00:00", tz="UTC")

    def test_CLIMED_TIMESTAMP_SOLO_HORA_sin_fecha(self):
        from calculos.clima_medido import _parsear_timestamps

        df = self._df_hora_time()
        with pytest.raises(ValueError, match="CLIMED_TIMESTAMP_SOLO_HORA"):
            _parsear_timestamps(df["hora"], "America/Argentina/Salta")

    def test_hash_y_roundtrip_config_con_fecha_fija(self):
        from datetime import date

        from calculos.clima_medido import config_a_dict, config_desde_dict, hash_ingesta
        from core.clima_medido import ConfigMapeoClima

        cfg = ConfigMapeoClima(columna_timestamp="hora", fecha_fija=date(2007, 6, 9))
        # hash no debe romper por date no-serializable.
        assert isinstance(hash_ingesta("abc", cfg), str)
        d = config_a_dict(cfg)
        assert d["fecha_fija"] == "2007-06-09"  # isoformat
        cfg2 = config_desde_dict(d)
        assert cfg2.fecha_fija == date(2007, 6, 9)
