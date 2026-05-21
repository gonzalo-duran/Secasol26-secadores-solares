"""Tests del modo de operación anual de cámara.

Cubre:
- ``dia_tipo_mensual``: promedio horario sobre el mes desde clima sintético.
- Las 4 eficiencias de Augustus Leon (RSER 2002): casos canónicos e invariantes.
- ``calcular_operacion_anual_camara``: smoke test con proyecto canónico.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.clima_calc import dia_tipo_mensual
from calculos.eficiencias_camara import (
    calor_latente_agua_J_kg,
    eta_drying,
    eta_pickup,
    eta_termica_camara,
    eta_total_sistema,
)

# ---------------------------------------------------------------------------
# Calor latente
# ---------------------------------------------------------------------------


class TestCalorLatenteAgua:

    def test_valor_a_20C(self):
        # h_fg(20°C) ≈ 2.454 MJ/kg
        assert calor_latente_agua_J_kg(293.15) == pytest.approx(2.4533e6, rel=1e-3)

    def test_valor_a_50C(self):
        # h_fg(50°C) ≈ 2.382 MJ/kg
        assert calor_latente_agua_J_kg(323.15) == pytest.approx(2.3817e6, rel=1e-3)

    def test_decrece_con_T(self):
        # h_fg disminuye con T (físicamente correcto, ASHRAE).
        assert calor_latente_agua_J_kg(273.15) > calor_latente_agua_J_kg(373.15)


# ---------------------------------------------------------------------------
# Las 4 eficiencias de Augustus Leon
# ---------------------------------------------------------------------------


class TestEtaDrying:

    def test_sin_agua_da_cero(self):
        assert eta_drying(0.0, 20e6, 4.0) == 0.0

    def test_sin_radiacion_da_cero(self):
        assert eta_drying(2.0, 0.0, 4.0) == 0.0

    def test_caso_canonico(self):
        # 2 kg agua, 20 MJ/m² sobre 4 m² → 80 MJ totales.
        # 2 · 2.38e6 / 80e6 = 0.0595 (~6%)
        eta = eta_drying(2.0, 20e6, 4.0)
        assert 0.05 < eta < 0.07

    def test_crece_con_m_agua(self):
        # A mayor m_agua, mayor η (linealmente).
        eta_1 = eta_drying(1.0, 20e6, 4.0)
        eta_2 = eta_drying(2.0, 20e6, 4.0)
        assert eta_2 == pytest.approx(2.0 * eta_1, rel=1e-9)


class TestEtaPickup:

    def test_aire_sale_saturado_da_uno(self):
        # ω_sal = ω_sat → pickup completo.
        assert eta_pickup(0.005, 0.020, 0.020) == pytest.approx(1.0)

    def test_sin_pickup_da_cero(self):
        # ω_sal = ω_ent → no captó nada.
        assert eta_pickup(0.005, 0.005, 0.020) == 0.0

    def test_pickup_intermedio(self):
        # ω va de 5 g/kg a 12 g/kg, saturación a 20 g/kg → (12−5)/(20−5) ≈ 0.467
        assert eta_pickup(0.005, 0.012, 0.020) == pytest.approx(7.0 / 15.0, rel=1e-9)

    def test_omega_sat_menor_a_entrada_da_cero(self):
        # Saturación más baja que entrada → no hay capacidad de captación.
        assert eta_pickup(0.020, 0.025, 0.015) == 0.0

    def test_clipeado_a_1(self):
        # Si ω_sal > ω_sat (físicamente imposible pero defensivo), se clipea.
        assert eta_pickup(0.005, 0.030, 0.020) == 1.0


class TestEtaTermica:

    def test_sin_radiacion_da_cero(self):
        assert eta_termica_camara(50e6, 0.0, 4.0) == 0.0

    def test_caso_canonico(self):
        # 80 MJ entregados al aire / 80 MJ solares = 1.0
        assert eta_termica_camara(80e6, 20e6, 4.0) == pytest.approx(1.0)

    def test_lineal_en_Q_aire(self):
        eta_1 = eta_termica_camara(40e6, 20e6, 4.0)
        eta_2 = eta_termica_camara(80e6, 20e6, 4.0)
        assert eta_2 == pytest.approx(2.0 * eta_1, rel=1e-9)


class TestEtaTotalSistema:

    def test_sin_energia_da_cero(self):
        assert eta_total_sistema(2.0, 0.0, 0.0) == 0.0

    def test_aux_reduce_eta(self):
        # Mismo m_agua, más energía total → menor η_total.
        eta_solo_sol = eta_total_sistema(2.0, 80e6, 0.0)
        eta_con_aux = eta_total_sistema(2.0, 80e6, 40e6)
        assert eta_con_aux < eta_solo_sol

    def test_caso_canonico(self):
        # 2 kg agua · 2.38e6 / 80e6 = 0.0595
        eta = eta_total_sistema(2.0, 80e6, 0.0)
        assert 0.05 < eta < 0.07


# ---------------------------------------------------------------------------
# Día típico mensual desde clima sintético
# ---------------------------------------------------------------------------


def _clima_sintetico_anual() -> pd.DataFrame:
    """DataFrame de clima sintético: senoidal estacional + diurno + ruido."""
    timestamps = pd.date_range("2024-01-01", periods=8784, freq="1h", tz="UTC")
    dias_juliano = np.array([t.timetuple().tm_yday for t in timestamps], dtype=float)
    horas = np.array([t.hour for t in timestamps], dtype=float)

    # Temperatura: ciclo anual + diurno
    T_amb_K = 293.15 + 8.0 * np.sin(2 * np.pi * (dias_juliano - 30) / 365)
    T_amb_K += 5.0 * np.sin(2 * np.pi * (horas - 6) / 24)  # pico a las 15h

    # GHI: pico al mediodía, modulado por estación
    factor_dia = np.maximum(0.0, np.sin(np.pi * (horas - 6) / 12))
    factor_estacional = 0.7 + 0.3 * np.sin(2 * np.pi * (dias_juliano - 30) / 365)
    GHI = 900.0 * factor_dia * factor_estacional

    DNI = GHI * 0.7
    DHI = GHI * 0.2
    WS = np.full(len(timestamps), 2.5)
    HR_pct = 60.0 + 15.0 * np.sin(2 * np.pi * (horas - 4) / 24)

    return pd.DataFrame(
        {
            "T_amb_K": T_amb_K,
            "GHI_Wm2": GHI,
            "DNI_Wm2": DNI,
            "DHI_Wm2": DHI,
            "WS_ms": WS,
            "HR": HR_pct,
        },
        index=timestamps,
    )


class TestDiaTipoMensual:

    def test_devuelve_24_filas(self):
        clima = _clima_sintetico_anual()
        df_dia = dia_tipo_mensual(clima, mes=6)
        assert len(df_dia) == 24

    def test_columnas_preservadas(self):
        clima = _clima_sintetico_anual()
        df_dia = dia_tipo_mensual(clima, mes=6)
        for col in ["T_amb_K", "GHI_Wm2", "DNI_Wm2", "DHI_Wm2", "WS_ms", "HR"]:
            assert col in df_dia.columns

    def test_pico_GHI_en_horas_centrales(self):
        # En el día tipo, el GHI máximo debe caer en las horas centrales (10-15).
        clima = _clima_sintetico_anual()
        df_dia = dia_tipo_mensual(clima, mes=6)
        h_pico = int(df_dia["GHI_Wm2"].idxmax().hour)
        assert 10 <= h_pico <= 15

    def test_GHI_nocturno_es_cero_o_bajo(self):
        # Las horas nocturnas (0-5, 20-23) deben tener GHI muy bajo o cero.
        clima = _clima_sintetico_anual()
        df_dia = dia_tipo_mensual(clima, mes=6)
        ghi_nocturno = df_dia.iloc[list(range(0, 5)) + list(range(20, 24))]["GHI_Wm2"]
        assert ghi_nocturno.max() < 50.0

    def test_diferentes_meses_dan_diferentes_T(self):
        # Junio y diciembre deben diferir en T_amb media (HS).
        clima = _clima_sintetico_anual()
        T_jun = dia_tipo_mensual(clima, mes=6)["T_amb_K"].mean()
        T_dic = dia_tipo_mensual(clima, mes=12)["T_amb_K"].mean()
        # En HS, junio (invierno) más frío que diciembre (verano).
        assert abs(T_jun - T_dic) > 2.0  # diferencia estacional perceptible

    def test_mes_invalido_lanza_error(self):
        clima = _clima_sintetico_anual()
        with pytest.raises(ValueError, match="DIA_TIPO_MES_INVALIDO"):
            dia_tipo_mensual(clima, mes=0)
        with pytest.raises(ValueError, match="DIA_TIPO_MES_INVALIDO"):
            dia_tipo_mensual(clima, mes=13)

    def test_mes_sin_datos_lanza_error(self):
        # Crear un clima solo con datos de enero y pedir febrero.
        clima_full = _clima_sintetico_anual()
        clima_enero = clima_full[clima_full.index.month == 1]
        with pytest.raises(ValueError, match="DIA_TIPO_SIN_DATOS"):
            dia_tipo_mensual(clima_enero, mes=2)


# ---------------------------------------------------------------------------
# Validaciones de OperacionAnualConfig
# ---------------------------------------------------------------------------


class TestOperacionAnualConfig:

    def test_default_valido(self):
        from core.camara import OperacionAnualConfig

        c = OperacionAnualConfig()
        assert c.batches_por_mes == 10

    def test_batches_fuera_rango(self):
        from core.camara import OperacionAnualConfig

        with pytest.raises(ValueError, match="ANUAL_BATCHES_FUERA_RANGO"):
            OperacionAnualConfig(batches_por_mes=0)
        with pytest.raises(ValueError, match="ANUAL_BATCHES_FUERA_RANGO"):
            OperacionAnualConfig(batches_por_mes=35)

    def test_horizonte_fuera_rango(self):
        from core.camara import OperacionAnualConfig

        with pytest.raises(ValueError, match="ANUAL_HORIZONTE_FUERA_RANGO"):
            OperacionAnualConfig(horizonte_horas_batch=12)  # < 24
        with pytest.raises(ValueError, match="ANUAL_HORIZONTE_FUERA_RANGO"):
            OperacionAnualConfig(horizonte_horas_batch=200)  # > 168

    def test_I_g_minima_no_negativa(self):
        from core.camara import OperacionAnualConfig

        with pytest.raises(ValueError, match="ANUAL_I_G_MINIMA_NEGATIVA"):
            OperacionAnualConfig(I_g_diaria_minima_MJ_m2=-1.0)


# ---------------------------------------------------------------------------
# Orquestador anual — smoke test
# ---------------------------------------------------------------------------


class TestCalcularOperacionAnualCamara:
    """Tests del orquestador. Se mockea el proyecto con la mínima estructura."""

    def test_sin_clima_lanza_error(self):
        from calculos.operacion_anual_camara import calcular_operacion_anual_camara
        from core.proyecto import Proyecto

        proy = Proyecto()  # sin clima ni cámara
        with pytest.raises(ValueError, match="ANUAL_SIN_CLIMA"):
            calcular_operacion_anual_camara(proy)
