"""Tests de la ingesta de la señal de referencia (mejora 38, fase 2, E2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.ingesta_referencia import (
    alinear_con_simulada,
    evaluar_ajuste,
    ingerir_forzantes_camara,
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
            ConfigReferencia(columna_timestamp="f", columna_valor="v", variable="color_del_secador")


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


# ---------------------------------------------------------------------------
# Fase 4 (E1): las cuatro señales de cámara/producto
# ---------------------------------------------------------------------------


def _df_senal(valores, columna="senal", n_paso_min=10) -> pd.DataFrame:
    """Tabla mínima con timestamps de texto y una columna de señal."""
    idx = pd.date_range("2010-05-01 09:00", periods=len(valores), freq=f"{n_paso_min}min")
    return pd.DataFrame(
        {"fecha": idx.strftime("%Y-%m-%d %H:%M:%S"), columna: [str(v) for v in valores]}
    )


def _cfg(variable, unidad, **kw) -> ConfigReferencia:
    return ConfigReferencia(
        columna_timestamp="fecha",
        columna_valor="senal",
        variable=variable,
        unidad=unidad,
        zona_horaria="UTC",
        **kw,
    )


class TestVariablesCamaraProducto:

    def test_T_camara_en_C_va_a_kelvin(self):
        sen = ingerir_referencia(_df_senal([40.0, 41.0, 42.0]), _cfg("T_camara", "C"))
        assert sen.variable == "T_camara"
        assert sen.serie.iloc[0] == pytest.approx(313.15)

    def test_T_producto_en_F(self):
        sen = ingerir_referencia(_df_senal([104.0, 104.0]), _cfg("T_producto", "F"))
        assert sen.serie.iloc[0] == pytest.approx(313.15)  # 104 °F = 40 °C

    def test_HR_camara_porcentaje_a_fraccion(self):
        sen = ingerir_referencia(_df_senal([35.0, 60.0, 90.0]), _cfg("HR_camara", "pct"))
        assert list(sen.serie.round(2)) == pytest.approx([0.35, 0.60, 0.90])

    def test_HR_camara_fraccion_se_mantiene(self):
        sen = ingerir_referencia(_df_senal([0.35, 0.60]), _cfg("HR_camara", "frac"))
        assert sen.serie.iloc[1] == pytest.approx(0.60)

    def test_HR_saturada_se_clipea_a_1(self):
        """1 < HR ≤ 1.02 es sensor saturado: se lleva a 1, no se anula."""
        sen = ingerir_referencia(_df_senal([0.9, 1.01, 1.5]), _cfg("HR_camara", "frac"))
        assert sen.serie.iloc[1] == pytest.approx(1.0)
        assert np.isnan(sen.serie.iloc[2])  # 1.5 sí es inválida
        assert any("VREF_QC_HR_CLIPEADA" in a for a in sen.advertencias)

    def test_X_producto_base_seca_directa(self):
        sen = ingerir_referencia(_df_senal([4.0, 2.0, 0.5]), _cfg("X_producto", "kg_kg"))
        assert list(sen.serie) == pytest.approx([4.0, 2.0, 0.5])

    def test_X_producto_porcentaje_base_seca(self):
        sen = ingerir_referencia(_df_senal([400.0, 50.0]), _cfg("X_producto", "pct_bs"))
        assert list(sen.serie) == pytest.approx([4.0, 0.5])

    def test_X_producto_base_humeda_a_base_seca(self):
        """X_bh = 0.80 → X_bs = 0.80/0.20 = 4.0 kg/kg."""
        sen = ingerir_referencia(_df_senal([0.80, 0.50]), _cfg("X_producto", "kg_kg_bh"))
        assert list(sen.serie) == pytest.approx([4.0, 1.0])

    def test_X_producto_pct_base_humeda(self):
        sen = ingerir_referencia(_df_senal([80.0, 50.0]), _cfg("X_producto", "pct_bh"))
        assert list(sen.serie) == pytest.approx([4.0, 1.0])

    def test_X_base_humeda_mayor_a_1_es_invalida(self):
        """X_bh ≥ 1 sería más agua que masa total: no es físico."""
        sen = ingerir_referencia(_df_senal([0.5, 1.0, 0.4]), _cfg("X_producto", "kg_kg_bh"))
        assert np.isnan(sen.serie.iloc[1])

    def test_masa_producto_a_humedad_base_seca(self):
        """Pesada de bandeja: m_seco = 2 kg, m = 10 kg → X = 10/2 − 1 = 4 kg/kg."""
        cfg = _cfg("masa_producto", "kg", masa_seca_kg=2.0)
        sen = ingerir_referencia(_df_senal([10.0, 6.0, 2.4]), cfg)
        assert list(sen.serie) == pytest.approx([4.0, 2.0, 0.2])

    def test_masa_producto_en_gramos(self):
        cfg = _cfg("masa_producto", "g", masa_seca_kg=0.2)
        sen = ingerir_referencia(_df_senal([1000.0, 400.0]), cfg)
        assert list(sen.serie) == pytest.approx([4.0, 1.0])

    def test_VREF_CONFIG_MASA_SECA_REQUERIDA(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_MASA_SECA_REQUERIDA"):
            _cfg("masa_producto", "kg")

    def test_VREF_CONFIG_MASA_SECA_NO_POSITIVA(self):
        with pytest.raises(ValueError, match="VREF_CONFIG_MASA_SECA_NO_POSITIVA"):
            _cfg("masa_producto", "kg", masa_seca_kg=0.0)

    def test_unidad_de_otra_variable_es_rechazada(self):
        """Las unidades son por variable: '%' de HR no aplica a una temperatura."""
        with pytest.raises(ValueError, match="VREF_CONFIG_UNIDAD_INVALIDA"):
            _cfg("T_camara", "pct")
        with pytest.raises(ValueError, match="VREF_CONFIG_UNIDAD_INVALIDA"):
            _cfg("HR_camara", "C")

    def test_QC_de_rango_usa_la_unidad_de_la_variable(self):
        """X negativa no es física; el mensaje habla de kg/kg, no de °C."""
        sen = ingerir_referencia(_df_senal([4.0, -1.0, 2.0]), _cfg("X_producto", "kg_kg"))
        assert np.isnan(sen.serie.iloc[1])
        assert any("kg/kg base seca" in a for a in sen.advertencias)

    def test_back_compat_T_salida_colector(self):
        """La variable de la fase 2 conserva exactamente su comportamiento."""
        sen = ingerir_referencia(_df_senal([25.0, 45.0]), _cfg("T_salida_colector", "C"))
        assert sen.serie.iloc[0] == pytest.approx(298.15)
        assert sen.unidad_origen == "C"
        assert sen.frecuencia_nativa_s == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# Fase 4 (E2): forzantes de la cámara aislada desde el archivo del ensayo
# ---------------------------------------------------------------------------


def _df_ensayo_camara(n: int = 13, paso_min: int = 30) -> pd.DataFrame:
    """Ensayo de cámara: aire de entrada medido (T, HR), ambiente y caudal."""
    idx = pd.date_range("2010-05-01 09:00", periods=n, freq=f"{paso_min}min")
    return pd.DataFrame(
        {
            "fecha": idx.strftime("%Y-%m-%d %H:%M:%S"),
            "T_in": [40.0 + 2.0 * np.sin(i / 2.0) for i in range(n)],
            "HR_in": [25.0] * n,
            "Tamb": [18.0] * n,
            "Q": [0.15] * n,
        }
    )


def _cfg_camara() -> ConfigReferencia:
    return ConfigReferencia(
        columna_timestamp="fecha",
        columna_valor="T_in",
        variable="T_camara",
        unidad="C",
        zona_horaria="UTC",
    )


class TestIngerirForzantesCamara:

    def test_forzantes_basicas(self):
        fm = ingerir_forzantes_camara(
            _df_ensayo_camara(),
            _cfg_camara(),
            columna_T_ent="T_in",
            columna_HR_ent="HR_in",
            columna_T_amb="Tamb",
            columna_caudal="Q",
        )
        f = fm.forzantes
        # El motor integra desde t=0; t0_utc guarda a qué instante corresponde.
        assert f.t_s[0] == 0.0
        assert f.t_s[1] == pytest.approx(1800.0)
        assert str(fm.t0_utc.tz) == "UTC"
        assert f.T_ent_K[0] == pytest.approx(313.15)
        assert f.m_dot_aire_seco_kg_s[0] == pytest.approx(0.15)
        assert len(f.omega_ent) == len(f.t_s)

    def test_omega_coherente_con_HR_y_T(self):
        from calculos.psicrometria import humedad_absoluta

        fm = ingerir_forzantes_camara(
            _df_ensayo_camara(),
            _cfg_camara(),
            columna_T_ent="T_in",
            columna_HR_ent="HR_in",
            columna_caudal="Q",
        )
        esperado = humedad_absoluta(0.25, 313.15, 101325.0)
        assert fm.forzantes.omega_ent[0] == pytest.approx(esperado, rel=1e-9)

    def test_VREF_HR_ENT_ASUMIDA(self):
        """Sin HR medida, el supuesto queda explícito (sesga la evaporación)."""
        fm = ingerir_forzantes_camara(
            _df_ensayo_camara(),
            _cfg_camara(),
            columna_T_ent="T_in",
            HR_ent_fija=0.4,
            m_dot_fijo_kg_s=0.2,
        )
        assert any("VREF_HR_ENT_ASUMIDA" in a for a in fm.advertencias)
        assert any("K_m" in a for a in fm.advertencias)  # el aviso explica la consecuencia

    def test_supuestos_dejan_advertencia_cada_uno(self):
        fm = ingerir_forzantes_camara(
            _df_ensayo_camara(), _cfg_camara(), columna_T_ent="T_in", m_dot_fijo_kg_s=0.2
        )
        codigos = {a.split(":")[0] for a in fm.advertencias}
        assert codigos == {
            "VREF_HR_ENT_ASUMIDA",
            "VREF_T_AMB_ASUMIDA",
            "VREF_VIENTO_ASUMIDO",
            "VREF_CAUDAL_ASUMIDO",
        }

    def test_caudal_volumetrico_a_masico_seco(self):
        """m3/h → kg/s de aire seco, con densidad de mezcla y descuento de vapor."""
        from calculos.psicrometria import densidad_aire_humedo, humedad_absoluta

        df = _df_ensayo_camara()
        df["Vdot"] = 500.0  # m³/h
        fm = ingerir_forzantes_camara(
            df,
            _cfg_camara(),
            columna_T_ent="T_in",
            columna_HR_ent="HR_in",
            columna_caudal="Vdot",
            unidad_caudal="m3_h",
        )
        omega = humedad_absoluta(0.25, 313.15, 101325.0)
        rho = densidad_aire_humedo(313.15, omega, 101325.0)
        esperado = rho * (500.0 / 3600.0) / (1.0 + omega)
        assert fm.forzantes.m_dot_aire_seco_kg_s[0] == pytest.approx(esperado, rel=1e-9)

    def test_VREF_CAUDAL_NO_DEFINIDO(self):
        with pytest.raises(ValueError, match="VREF_CAUDAL_NO_DEFINIDO"):
            ingerir_forzantes_camara(_df_ensayo_camara(), _cfg_camara(), columna_T_ent="T_in")

    def test_VREF_COLUMNA_TENT_AUSENTE(self):
        with pytest.raises(ValueError, match="VREF_COLUMNA_TENT_AUSENTE"):
            ingerir_forzantes_camara(
                _df_ensayo_camara(), _cfg_camara(), columna_T_ent="no_existe", m_dot_fijo_kg_s=0.2
            )

    def test_VREF_FORZANTES_VACIAS(self):
        df = _df_ensayo_camara(n=4)
        df["T_in"] = "NAN"
        with pytest.raises(ValueError, match="VREF_FORZANTES_VACIAS"):
            ingerir_forzantes_camara(df, _cfg_camara(), columna_T_ent="T_in", m_dot_fijo_kg_s=0.2)

    def test_irradiancia_opcional_por_defecto_cero(self):
        fm = ingerir_forzantes_camara(
            _df_ensayo_camara(), _cfg_camara(), columna_T_ent="T_in", m_dot_fijo_kg_s=0.2
        )
        assert float(np.max(fm.forzantes.I_g_W_m2)) == 0.0
