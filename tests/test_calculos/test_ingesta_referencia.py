"""Tests de la ingesta de la señal de referencia (mejora 38, fase 2, E2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.ingesta_referencia import (
    alinear_con_simulada,
    evaluar_ajuste,
    ingerir_referencia,
)
from core.validacion import ConfigReferencia, SenalReferencia

# ---------------------------------------------------------------------------
# ConfigReferencia — validaciones
# ---------------------------------------------------------------------------


class TestConfigReferencia:

    def test_config_valida(self):
        cfg = ConfigReferencia(
            columna_timestamp="fecha", columna_valor="T_out", unidad="C", zona_horaria="UTC"
        )
        assert cfg.variable == "T_salida_colector"

    def test_VREF_CONFIG_TIMESTAMP_VACIO(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_TIMESTAMP_VACIO"):
            ConfigReferencia(columna_timestamp="  ", columna_valor="T_out")

    def test_VREF_CONFIG_VALOR_VACIO(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_VALOR_VACIO"):
            ConfigReferencia(columna_timestamp="fecha", columna_valor="")

    def test_VREF_CONFIG_UNIDAD_INVALIDA(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_UNIDAD_INVALIDA"):
            ConfigReferencia(columna_timestamp="fecha", columna_valor="T", unidad="bananas")

    def test_VREF_CONFIG_VARIABLE_DESCONOCIDA(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_VARIABLE_DESCONOCIDA"):
            ConfigReferencia(columna_timestamp="f", columna_valor="v", variable="X_producto")


# ---------------------------------------------------------------------------
# ingerir_referencia
# ---------------------------------------------------------------------------


def _df_referencia_texto(n: int = 24, paso_min: int = 10) -> pd.DataFrame:
    """Referencia estilo datalogger: timestamps de texto, T en °C, con 'NAN'."""
    idx = pd.date_range("2010-05-01 00:00", periods=n, freq=f"{paso_min}min")
    t_out_c = 20.0 + 30.0 * np.sin(np.linspace(0, np.pi, n))  # 20→50→20 °C
    valores = [f"{v:.2f}" for v in t_out_c]
    valores[3] = "NAN"  # marcador de dato inválido
    return pd.DataFrame({"fecha": idx.strftime("%Y-%m-%d %H:%M:%S"), "T_out": valores})


class TestIngerirReferencia:

    def test_ingesta_basica_a_kelvin(self):
        df = _df_referencia_texto()
        cfg = ConfigReferencia(
            columna_timestamp="fecha",
            columna_valor="T_out",
            unidad="C",
            zona_horaria="America/Argentina/Salta",
        )
        sr = ingerir_referencia(df, cfg)
        assert isinstance(sr, SenalReferencia)
        assert sr.frecuencia_nativa_s == pytest.approx(600.0)
        # Primer valor 20 °C → 293.15 K.
        assert sr.serie.dropna().iloc[0] == pytest.approx(293.15, abs=0.05)
        # El 'NAN' quedó como NaN.
        assert sr.n_invalidos >= 1
        # Índice UTC.
        assert str(sr.serie.index.tz) == "UTC"

    def test_columna_ausente(self):
        df = _df_referencia_texto()
        cfg = ConfigReferencia(columna_timestamp="fecha", columna_valor="NO_EXISTE")
        with pytest.raises(ValueError, match="VREF_COLUMNA_VALOR_AUSENTE"):
            ingerir_referencia(df, cfg)

    def test_qc_fuera_de_rango_anula(self):
        df = _df_referencia_texto()
        df.loc[5, "T_out"] = "500.0"  # 500 °C imposible
        cfg = ConfigReferencia(columna_timestamp="fecha", columna_valor="T_out", unidad="C")
        sr = ingerir_referencia(df, cfg)
        assert any("VREF_QC_FUERA_DE_RANGO" in a for a in sr.advertencias)

    def test_unidad_kelvin_no_convierte(self):
        idx = pd.date_range("2010-05-01", periods=6, freq="10min")
        df = pd.DataFrame({"fecha": idx.strftime("%Y-%m-%d %H:%M:%S"), "T_out": [300.0] * 6})
        cfg = ConfigReferencia(columna_timestamp="fecha", columna_valor="T_out", unidad="K")
        sr = ingerir_referencia(df, cfg)
        assert sr.serie.dropna().iloc[0] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# alinear_con_simulada
# ---------------------------------------------------------------------------


class TestAlinearConSimulada:

    def _senal(self) -> SenalReferencia:
        idx = pd.date_range("2010-05-01 00:00", periods=12, freq="10min", tz="UTC")
        serie = pd.Series(293.15 + np.arange(12) * 1.0, index=idx)
        return SenalReferencia(
            variable="T_salida_colector",
            serie=serie,
            unidad_origen="C",
            frecuencia_nativa_s=600.0,
        )

    def test_alinea_interpolando_simulada(self):
        senal = self._senal()
        # Simulada horaria que coincide exactamente con la recta medida.
        t_sim = pd.date_range("2010-05-01 00:00", periods=3, freq="h", tz="UTC")
        # A 10 min, +1 K/paso → +6 K/hora. Simulada: 293.15, 299.15, 305.15.
        y_sim = np.array([293.15, 299.15, 305.15])
        y_med, y_sim_al, ts = alinear_con_simulada(senal, t_sim, y_sim)
        assert len(y_med) == len(y_sim_al) > 0
        # La interpolación reproduce la recta → error ~0.
        assert np.allclose(y_med, y_sim_al, atol=1e-6)

    def test_sin_solape_devuelve_vacio(self):
        senal = self._senal()
        t_sim = pd.date_range("2011-01-01", periods=3, freq="h", tz="UTC")
        y_sim = np.array([300.0, 301.0, 302.0])
        y_med, y_sim_al, ts = alinear_con_simulada(senal, t_sim, y_sim)
        assert len(y_med) == 0
        assert len(ts) == 0

    def test_sim_vacia_falla(self):
        senal = self._senal()
        t_sim = pd.date_range("2010-05-01", periods=2, freq="h", tz="UTC")
        with pytest.raises(ValueError, match="VREF_SIM_VACIA"):
            alinear_con_simulada(senal, t_sim, np.array([np.nan, np.nan]))


class TestEvaluarAjuste:

    def _senal(self):
        idx = pd.date_range("2010-05-01 00:00", periods=13, freq="10min", tz="UTC")
        serie = pd.Series(293.15 + np.arange(13) * 1.0, index=idx)
        return SenalReferencia(
            variable="T_salida_colector",
            serie=serie,
            unidad_origen="C",
            frecuencia_nativa_s=600.0,
        )

    def test_ajuste_perfecto_da_rmse_cero(self):
        senal = self._senal()
        t_sim = pd.date_range("2010-05-01 00:00", periods=3, freq="h", tz="UTC")
        y_sim = np.array([293.15, 299.15, 305.15])  # misma recta que la medida
        metricas, y_med, y_sim_al, ts = evaluar_ajuste(senal, t_sim, y_sim)
        assert metricas is not None
        assert metricas.rmse == pytest.approx(0.0, abs=1e-6)
        assert metricas.r2 == pytest.approx(1.0)
        assert metricas.n_pares > 0

    def test_sesgo_conocido_en_mbe(self):
        senal = self._senal()
        t_sim = pd.date_range("2010-05-01 00:00", periods=3, freq="h", tz="UTC")
        y_sim = np.array([295.15, 301.15, 307.15])  # +2 K de sesgo
        metricas, *_ = evaluar_ajuste(senal, t_sim, y_sim)
        assert metricas.mbe == pytest.approx(2.0, abs=1e-6)

    def test_sin_solape_metricas_none(self):
        senal = self._senal()
        t_sim = pd.date_range("2011-01-01", periods=3, freq="h", tz="UTC")
        metricas, y_med, _, _ = evaluar_ajuste(senal, t_sim, np.array([300.0, 301.0, 302.0]))
        assert metricas is None
        assert len(y_med) == 0


# ---------------------------------------------------------------------------
# Fase 2b: fecha fija + clima de forzado del propio archivo
# ---------------------------------------------------------------------------


def _df_hora_sola(n=6):
    """Archivo con timestamp de SOLO hora (sin fecha), estilo prototipo 10 m."""
    from datetime import datetime, timedelta

    t0 = datetime(1900, 1, 1, 9, 0, 0)
    horas = [(t0 + timedelta(minutes=5 * i)).strftime("%H:%M:%S") for i in range(n)]
    return pd.DataFrame(
        {
            "hora": horas,
            "Tout": [20.0 + i for i in range(n)],
            "Ta": [15.0 + i for i in range(n)],
            "I": [700.0 + 10 * i for i in range(n)],
        }
    )


def test_ingerir_referencia_con_fecha_fija():
    from datetime import date

    df = _df_hora_sola()
    cfg = ConfigReferencia(
        columna_timestamp="hora",
        columna_valor="Tout",
        unidad="C",
        zona_horaria="America/Argentina/Salta",
        fecha_fija=date(2007, 6, 9),
    )
    sr = ingerir_referencia(df, cfg)
    # 09:00 local Salta (UTC−3) → 12:00 UTC del 2007-06-09.
    assert sr.serie.index[0] == pd.Timestamp("2007-06-09 12:00:00", tz="UTC")
    assert sr.frecuencia_nativa_s == pytest.approx(300.0)


def test_ingerir_clima_forzante():
    from datetime import date

    from calculos.ingesta_referencia import ingerir_clima_forzante

    df = _df_hora_sola()
    cfg = ConfigReferencia(
        columna_timestamp="hora",
        columna_valor="Tout",
        zona_horaria="America/Argentina/Salta",
        fecha_fija=date(2007, 6, 9),
    )
    clima = ingerir_clima_forzante(
        df, cfg, columna_T_amb="Ta", unidad_T_amb="C", columna_POA="I", unidad_POA="W_m2"
    )
    assert {"T_amb_K", "WS_ms", "POA_med_Wm2", "GHI_Wm2", "DNI_Wm2", "DHI_Wm2"} <= set(
        clima.columns
    )
    # Ta 15 °C → 288.15 K; POA = I.
    assert clima["T_amb_K"].iloc[0] == pytest.approx(288.15, abs=0.05)
    assert clima["POA_med_Wm2"].iloc[0] == pytest.approx(700.0)
    # Sin columna de viento → default 2 m/s.
    assert clima["WS_ms"].iloc[0] == pytest.approx(2.0)
    assert str(clima.index.tz) == "UTC"


def test_ingerir_clima_forzante_columna_ausente():
    from calculos.ingesta_referencia import ingerir_clima_forzante

    df = _df_hora_sola()
    cfg = ConfigReferencia(columna_timestamp="hora", columna_valor="Tout")
    with pytest.raises(ValueError, match="VREF_COLUMNA_POA_AUSENTE"):
        ingerir_clima_forzante(df, cfg, columna_T_amb="Ta", columna_POA="NO_EXISTE")


def test_ingerir_referencia_hora_como_datetime_time():
    """Regresión: columna de solo-hora leída como datetime.time (típico de .xls).

    pd.read_excel devuelve las horas como objetos datetime.time, no strings; el
    parser con fecha_fija debe combinarlas correctamente (no dar NaT → TODO_INVALIDO).
    """
    from datetime import date, time

    df = pd.DataFrame(
        {
            "hora": [time(9, 0), time(9, 5), time(9, 10), time(9, 15)],
            "Tout": [20.0, 21.0, 22.0, 23.0],
        }
    )
    cfg = ConfigReferencia(
        columna_timestamp="hora",
        columna_valor="Tout",
        unidad="C",
        zona_horaria="America/Argentina/Salta",
        fecha_fija=date(2007, 6, 9),
    )
    sr = ingerir_referencia(df, cfg)
    assert sr.serie.notna().sum() == 4
    # 09:00 Salta (UTC−3) → 12:00 UTC del 2007-06-09.
    assert sr.serie.index[0] == pd.Timestamp("2007-06-09 12:00:00", tz="UTC")
