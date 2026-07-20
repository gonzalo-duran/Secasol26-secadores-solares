"""Tests de la sección de validación del colector en P3 (mejora 38, fase 2, E4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.clima import Clima
from core.colector import Colector, ColectorUnidad
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, Proyecto, Tipologia
from core.validacion import ConfigReferencia, SenalReferencia
from ui.p3_colector import (
    _config_referencia_desde_widgets,
    _filas_metricas,
    _series_simuladas_colector,
)

# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------


def test_config_referencia_desde_widgets():
    cfg = _config_referencia_desde_widgets(
        col_ts="fecha",
        col_val="T_out",
        unidad="C",
        zona="America/Argentina/Salta",
        conv="instantanea",
        hoja=None,
        fila_enc=0,
    )
    assert isinstance(cfg, ConfigReferencia)
    assert cfg.variable == "T_salida_colector"
    assert cfg.columna_valor == "T_out"


def test_filas_metricas_estructura():
    from calculos.metricas_validacion import calcular_metricas

    m = calcular_metricas(np.array([10.0, 20.0, 30.0]), np.array([12.0, 22.0, 32.0]))
    filas = _filas_metricas(m)
    ids = [f[0] for f in filas]
    assert ids == ["rmse", "mbe", "mae", "r2", "nse", "d"]
    # RMSE/MBE/MAE en °C; R²/NSE/d adimensionales.
    unidades = {f[0]: f[2] for f in filas}
    assert unidades["rmse"] == "C" and unidades["r2"] == ""
    # MBE = +2 (el "simulado" está 2 por encima).
    mbe = next(v for i, v, _ in filas if i == "mbe")
    assert mbe == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Orquestación: correr el colector sobre el período de la referencia
# ---------------------------------------------------------------------------


def _proyecto_con_clima(anio: int = 2023, dias: int = 2) -> Proyecto:
    empl = Emplazamiento()  # Salta
    n = 24 * dias
    idx = pd.date_range(f"{anio}-06-15 00:00", periods=n, freq="h", tz="UTC")
    h = np.arange(n) % 24
    ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (h - 6.0) / 12.0))
    df = pd.DataFrame(
        {
            "T_amb_K": 288.15 + 8.0 * np.sin(2 * np.pi * (h - 9) / 24.0),
            "GHI_Wm2": ghi,
            "DNI_Wm2": np.full(n, np.nan),
            "DHI_Wm2": np.full(n, np.nan),
            "WS_ms": np.full(n, 2.5),
            "presion_Pa": np.full(n, 90000.0),
            "HR": np.full(n, 0.40),
        },
        index=idx,
    )
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.emplazamiento = empl
    p.clima = Clima(datos=df, anio=anio)
    p.colector = Colector(unidad=ColectorUnidad())
    return p


def _senal(idx) -> SenalReferencia:
    serie = pd.Series(300.0 + np.arange(len(idx)) * 0.1, index=idx)
    return SenalReferencia(
        variable="T_salida_colector",
        serie=serie,
        unidad_origen="C",
        frecuencia_nativa_s=3600.0,
    )


def test_series_simuladas_cubre_periodo():
    p = _proyecto_con_clima()
    # Referencia sobre un sub-rango del clima (segundo día).
    idx_ref = pd.date_range("2023-06-16 06:00", "2023-06-16 18:00", freq="h", tz="UTC")
    t_sim, y_sim_K = _series_simuladas_colector(p, _senal(idx_ref))
    assert t_sim is not None
    assert len(t_sim) == len(y_sim_K) > 0
    # Salidas físicas (K plausibles).
    assert np.all((y_sim_K > 250.0) & (y_sim_K < 400.0))


def test_series_simuladas_sin_cobertura_devuelve_none():
    p = _proyecto_con_clima()
    # Referencia en otro año → el clima no la cubre.
    idx_ref = pd.date_range("2019-01-01", periods=6, freq="h", tz="UTC")
    t_sim, y_sim_K = _series_simuladas_colector(p, _senal(idx_ref))
    assert t_sim is None
    assert y_sim_K is None


def test_series_simuladas_sin_colector_devuelve_none():
    p = _proyecto_con_clima()
    p.colector = None
    idx_ref = pd.date_range("2023-06-16 06:00", periods=6, freq="h", tz="UTC")
    t_sim, y_sim_K = _series_simuladas_colector(p, _senal(idx_ref))
    assert t_sim is None


# ---------------------------------------------------------------------------
# Fase 2b: forzar con el clima medido del propio archivo
# ---------------------------------------------------------------------------


def test_series_simuladas_con_clima_forzante():
    """Con clima_forzante (Ta+POA del ensayo), corre sin depender del clima de P2."""
    from datetime import date

    from calculos.ingesta_referencia import ingerir_clima_forzante
    from core.validacion import ConfigReferencia

    p = _proyecto_con_clima()
    p.clima = None  # sin clima de P2: debe usar el forzante

    # Archivo con hora-sola + Ta + I (POA), un mediodía.
    horas = [f"{9 + i // 12:02d}:{(i % 12) * 5:02d}:00" for i in range(60)]
    df = pd.DataFrame(
        {
            "hora": horas,
            "Tout": np.linspace(15.0, 35.0, 60),
            "Ta": np.linspace(10.0, 22.0, 60),
            "I": np.linspace(300.0, 850.0, 60),
        }
    )
    cfg = ConfigReferencia(
        columna_timestamp="hora",
        columna_valor="Tout",
        zona_horaria="America/Argentina/Salta",
        fecha_fija=date(2007, 6, 9),
    )
    senal = _senal(pd.date_range("2007-06-09 12:00", periods=30, freq="5min", tz="UTC"))
    clima_forz = ingerir_clima_forzante(
        df, cfg, columna_T_amb="Ta", columna_POA="I", unidad_POA="W_m2"
    )
    t_sim, y_sim_K = _series_simuladas_colector(p, senal, clima_forzante=clima_forz)
    assert t_sim is not None
    assert len(t_sim) == len(y_sim_K) > 0
    assert np.all((y_sim_K > 250.0) & (y_sim_K < 400.0))


# ---------------------------------------------------------------------------
# Salida por canal (Tipo 2) — pedido del usuario
# ---------------------------------------------------------------------------


def test_T_salida_canal_tipo2_distingue():
    from types import SimpleNamespace

    from ui.p3_colector import _T_salida_canal_K

    res = SimpleNamespace(T_salida_cs_K=330.0, T_salida_ci_K=340.0, T_salida_mezcla_K=335.0)
    assert _T_salida_canal_K(res, 2, "superior") == 330.0
    assert _T_salida_canal_K(res, 2, "inferior") == 340.0
    assert _T_salida_canal_K(res, 2, "mezcla") == 335.0


def test_T_salida_canal_tipo1_colapsa():
    from types import SimpleNamespace

    from ui.p3_colector import _T_salida_canal_K

    res = SimpleNamespace(T_salida_K=333.0)
    # Tipo 1: los tres canales devuelven la única salida.
    for canal in ("mezcla", "superior", "inferior"):
        assert _T_salida_canal_K(res, 1, canal) == 333.0


def test_series_simuladas_salida_por_canal_tipo2():
    """En Tipo 2, superior/inferior/mezcla dan series distintas."""
    p = _proyecto_con_clima()
    p.colector = Colector(unidad=ColectorUnidad(tipo_colector=2, largo_m=3.0, ancho_m=0.9))
    idx_ref = pd.date_range("2023-06-16 09:00", "2023-06-16 16:00", freq="h", tz="UTC")
    senal = _senal(idx_ref)

    _, y_mez = _series_simuladas_colector(p, senal, salida="mezcla")
    _, y_sup = _series_simuladas_colector(p, senal, salida="superior")
    _, y_inf = _series_simuladas_colector(p, senal, salida="inferior")
    # Al menos un instante diurno debe diferir entre canales.
    assert not np.allclose(y_sup, y_inf)
    # La mezcla queda entre ambos canales (media ponderada).
    assert np.all(
        (y_mez >= np.minimum(y_sup, y_inf) - 1e-6) & (y_mez <= np.maximum(y_sup, y_inf) + 1e-6)
    )
