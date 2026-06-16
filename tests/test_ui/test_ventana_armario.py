"""Tests del modo Ventana de producción para CAJA/ARMARIO (mejora 35).

VENTANA deja de ser exclusivo de gran escala: para CAJA/ARMARIO se comporta
como un multidía real sobre el lapso ``[ventana_inicio, ventana_fin]`` de P1,
construyendo forzantes horarias (día y noche) que alimentan la pipeline
transitoria de P7 (``calcular_todo_transitorio``).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from core.clima import Clima
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, ModoAnalisis, Proyecto, Tipologia
from ui.p4_camara import _construir_forzantes_ventana

DIAS = 5


def _proyecto_ventana_caja(anio: int = 2023) -> Proyecto:
    """Proyecto CAJA con clima horario sintético de varios días y ventana de 5 días."""
    empl = Emplazamiento()  # Salta
    horas = pd.date_range(
        start=f"{anio}-06-15 00:00", periods=24 * (DIAS + 2), freq="h", tz=empl.zona_horaria
    )
    h_idx = np.arange(len(horas))
    # GHI semicampana diaria (0 de noche), T_amb senoidal diaria.
    hora_del_dia = h_idx % 24
    ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (hora_del_dia - 6.0) / 12.0))
    t_amb = 288.15 + 8.0 * np.sin(2 * np.pi * (hora_del_dia - 9) / 24.0)
    df = pd.DataFrame(
        {
            "T_amb_K": t_amb,
            "HR": np.full(len(horas), 0.40),
            "WS_ms": np.full(len(horas), 2.5),
            "GHI_Wm2": ghi,
        },
        index=horas,
    ).tz_convert("UTC")

    p = Proyecto()
    p.emplazamiento = empl
    p.clima = Clima(datos=df, anio=anio)
    p.configuracion = Configuracion(
        tipologia=Tipologia.CAJA,
        modo_analisis=ModoAnalisis.VENTANA,
        ventana_inicio=date(anio, 6, 15),
        ventana_fin=date(anio, 6, 20),  # 5 días
    )
    p.colector = None
    return p


class TestForzantesVentana:

    def test_cubre_la_ventana_completa(self):
        p = _proyecto_ventana_caja()
        fz = _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
        # ~5 días × 24 h de forzantes horarias.
        assert len(fz.t_s) == DIAS * 24

    def test_incluye_horas_de_noche(self):
        """El colector/aire se resuelve día y noche: hay horas con I_g≈0."""
        p = _proyecto_ventana_caja()
        fz = _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
        # Todas las horas tienen T_ent finita (sin huecos None de noche).
        assert np.all(np.isfinite(fz.T_ent_K))
        # CAJA: T_ent = T_amb en todas las horas (incluida la noche).
        assert np.allclose(fz.T_ent_K, fz.T_amb_K)

    def test_horizonte_temporal_creciente(self):
        p = _proyecto_ventana_caja()
        fz = _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
        assert fz.t_s[-1] > fz.t_s[0]
        # dt horario.
        assert fz.t_s[1] - fz.t_s[0] == pytest.approx(3600.0)

    def test_sin_ventana_definida_falla(self):
        # Configuracion ya exige fechas en VENTANA; el guard de la función es
        # defensivo (nulear post-construcción simula una config inconsistente).
        p = _proyecto_ventana_caja()
        p.configuracion.ventana_inicio = None
        with pytest.raises(RuntimeError, match="ventana de producción"):
            _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)

    def test_sin_clima_falla(self):
        p = _proyecto_ventana_caja()
        p.clima = None
        with pytest.raises(RuntimeError, match="clima real"):
            _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
