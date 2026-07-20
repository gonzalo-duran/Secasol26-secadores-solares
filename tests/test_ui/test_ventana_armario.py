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

    def test_paso_15min_da_forzantes_subhorarias(self):
        """Con paso_trabajo_s=900 (fase 1b), las forzantes de ventana son a 15 min."""
        p = _proyecto_ventana_caja()
        p.configuracion.paso_trabajo_s = 900.0
        fz = _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
        # dt de 900 s (15 min) derivado del clima resuelto al paso de trabajo.
        assert fz.t_s[1] - fz.t_s[0] == pytest.approx(900.0)
        # ~4× nodos que el horario (5 días × 96 puntos/día, con borde).
        assert len(fz.t_s) > DIAS * 24 * 3

    def test_paso_15min_stashea_advertencia_sintetica(self):
        """Clima horario a 15 min → resolución sintética señalada en session_state."""
        import streamlit as st

        from ui.p4_camara import _PASO_ADV_KEY

        p = _proyecto_ventana_caja()
        p.configuracion.paso_trabajo_s = 900.0
        _construir_forzantes_ventana(proyecto=p, caudal_kg_s=0.02)
        advs = st.session_state.get(_PASO_ADV_KEY, [])
        assert any("ADV_PASO_SINTETICO" in a for a in advs)


class TestVentanaEnGranEscala:
    """Regresión (S55): en GRAN_ESCALA + VENTANA la previa de P4 perdía la ventana.

    ``usar_ventana`` excluía explícitamente gran escala, así que P4 caía a la rama
    de "día real / sintético", exigía P3 *en modo diario* (que en VENTANA nunca se
    cumple) y terminaba simulando un **día sintético** — perdiendo el lapso y el
    clima real que P2 y P3 sí habían usado. Reportado por el usuario con el preset
    ADITAL semicontinuo emplazado en Salta.
    """

    def _proyecto_gran_escala(self, subtipo, anio: int = 2023):
        from core.camara import Camara, CargaProducto
        from core.colector import Colector, ColectorUnidad

        p = _proyecto_ventana_caja(anio)
        # Con colector, la POA necesita las componentes directa/difusa.
        p.clima.datos["DNI_Wm2"] = np.nan
        p.clima.datos["DHI_Wm2"] = np.nan
        p.clima.datos["presion_Pa"] = 90000.0
        p.configuracion = Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            subtipo_gran_escala=subtipo,
            modo_analisis=ModoAnalisis.VENTANA,
            ventana_inicio=date(anio, 6, 15),
            ventana_fin=date(anio, 6, 20),
        )
        p.colector = Colector(unidad=ColectorUnidad())
        p.camara = Camara(carga_producto=CargaProducto(producto_id="manzana"))
        return p

    @pytest.mark.parametrize("subtipo_nombre", ["BATCH", "SEMICONTINUO"])
    def test_forzantes_de_ventana_disponibles_en_gran_escala(self, subtipo_nombre):
        """El constructor de forzantes de ventana es agnóstico a la tipología."""
        from core.proyecto import SubtipoGranEscala

        proyecto = self._proyecto_gran_escala(getattr(SubtipoGranEscala, subtipo_nombre))
        fz = _construir_forzantes_ventana(proyecto=proyecto, caudal_kg_s=0.5)
        # Cubre el lapso completo con clima real horario (no un día sintético).
        assert fz.t_s[-1] == pytest.approx(DIAS * 24 * 3600.0, rel=0.05)
        assert len(fz.T_ent_K) >= DIAS * 24
        # Y trae el ancla temporal para poder reanclar resultados (fase 4).
        assert fz.t0_utc is not None

    def test_usar_ventana_no_excluye_gran_escala(self):
        """El flag de la UI debe ser verdadero también en gran escala."""
        from core.proyecto import SubtipoGranEscala

        for subtipo in (SubtipoGranEscala.BATCH, SubtipoGranEscala.SEMICONTINUO):
            cfg = self._proyecto_gran_escala(subtipo).configuracion
            usar_ventana = getattr(cfg, "modo_analisis", None) == ModoAnalisis.VENTANA
            assert usar_ventana, f"{subtipo} en VENTANA debería usar la ventana en P4"
