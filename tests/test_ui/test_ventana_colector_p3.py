"""Tests de la evaluación de colector sobre la ventana en P3 (mejora 34).

`_evaluar_ventana` ahora resuelve día y noche (de noche T_salida ≈ T_amb, no
None), expone la serie del absorbedor, el perfil T(x) del mediodía solar del
primer día y las marcas (POA máx + mediodía solar) de cada día.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.colector import Colector, ColectorUnidad
from core.emplazamiento import Emplazamiento
from ui.p3_colector import _evaluar_ventana, _fig_T_salida_ventana

DIAS = 3


def _datos_ventana(anio: int = 2023) -> tuple[pd.DataFrame, Emplazamiento]:
    empl = Emplazamiento()  # Salta
    horas = pd.date_range(
        start=f"{anio}-06-15 00:00", periods=24 * DIAS, freq="h", tz=empl.zona_horaria
    )
    h = np.arange(len(horas)) % 24
    ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (h - 6.0) / 12.0))
    df = pd.DataFrame(
        {
            "T_amb_K": 288.15 + 8.0 * np.sin(2 * np.pi * (h - 9) / 24.0),
            "HR": np.full(len(horas), 0.40),
            "WS_ms": np.full(len(horas), 2.5),
            "GHI_Wm2": ghi,
            "DNI_Wm2": np.full(len(horas), np.nan),  # → POA cae a GHI
            "DHI_Wm2": np.full(len(horas), np.nan),
        },
        index=horas,
    )
    return df, empl


def _colector() -> Colector:
    return Colector(unidad=ColectorUnidad())


class TestEvaluarVentana:

    def test_dia_y_noche_sin_none(self):
        df, empl = _datos_ventana()
        r = _evaluar_ventana(_colector(), df, empl)
        assert len(r["T_salida_C"]) == len(r["horas"]) == 24 * DIAS
        assert all(t is not None for t in r["T_salida_C"])
        assert all(t is not None for t in r["T_abs_C"])

    def test_noche_T_salida_igual_T_amb(self):
        df, empl = _datos_ventana()
        r = _evaluar_ventana(_colector(), df, empl)
        poa = r["poa"]
        noches = [i for i, p in enumerate(poa) if p < 50.0]
        assert noches  # hay horas nocturnas
        for i in noches:
            assert r["T_salida_C"][i] == pytest.approx(r["T_amb_C"][i], abs=1e-9)

    def test_perfil_primer_dia_presente(self):
        df, empl = _datos_ventana()
        r = _evaluar_ventana(_colector(), df, empl)
        assert r["x_noon"] is not None
        assert r["T_perfil_noon_C"] is not None
        assert len(r["x_noon"]) == len(r["T_perfil_noon_C"])

    def test_marcas_por_dia(self):
        df, empl = _datos_ventana()
        r = _evaluar_ventana(_colector(), df, empl)
        # Una marca por día con sol (los 3 días tienen semicampana).
        assert len(r["marcas_poa_max"]) == DIAS
        assert len(r["marcas_mediodia"]) == DIAS
        # Cada marca de POA es (timestamp, valor>0).
        for ts, val in r["marcas_poa_max"]:
            assert val > 0.0

    def test_figura_se_construye(self):
        df, empl = _datos_ventana()
        r = _evaluar_ventana(_colector(), df, empl)
        fig = _fig_T_salida_ventana(r, "2023-06-15 → 2023-06-18")
        nombres = {tr.name for tr in fig.data}
        assert "T salida colector [°C]" in nombres
        assert "T absorbedor [°C]" in nombres
        assert "Mediodía solar" in nombres
