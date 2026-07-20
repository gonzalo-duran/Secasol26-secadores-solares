"""Tests de integración para el modo 'Día real' de forzantes en P4.

Verifica que el cableado P2 (clima NASA) + P3 (T_salida_C horaria del colector)
→ `_construir_forzantes_reales` → `ForzantesAire` consumible por el motor TD
no se rompa silenciosamente.

El refactor que permite estos tests: `_construir_forzantes_reales` y
`_disponibilidad_forzantes_reales` reciben `p3_eval` como argumento explícito
en vez de leer `st.session_state`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from calculos.psicrometria import humedad_absoluta
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    ForzantesAire,
    GeometriaCamara,
    ParedCamara,
)
from core.clima import Clima
from core.emplazamiento import Emplazamiento
from core.proyecto import Proyecto
from ui.p4_camara import (
    _construir_forzantes_reales,
    _disponibilidad_forzantes_reales,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _proyecto_con_clima_diario(anio: int = 2023) -> tuple[Proyecto, list[pd.Timestamp]]:
    """Proyecto mínimo con Emplazamiento Salta + 24 h de clima sintético.

    Returns:
        (proyecto, horas_local) — `horas_local` es la lista de timestamps
        tz-aware en zona horaria local que va a entrar en p3_eval["r"]["horas"].
    """
    empl = Emplazamiento()  # defaults: Salta
    horas_local = pd.date_range(
        start=f"{anio}-06-15 00:00",
        periods=24,
        freq="h",
        tz=empl.zona_horaria,
    )
    # GHI sintético: semicampana positiva centrada al mediodía (h=12 → seno positivo).
    horas_idx = np.arange(24)
    ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (horas_idx - 6.0) / 12.0))
    df = pd.DataFrame(
        {
            "T_amb_K": 288.15 + 8.0 * np.sin(np.linspace(-np.pi / 2, 3 * np.pi / 2, 24)),
            "HR": np.full(24, 0.40),
            "WS_ms": np.full(24, 2.5),
            "GHI_Wm2": ghi,
        },
        index=horas_local,
    ).tz_convert("UTC")

    clima = Clima(datos=df, anio=anio)
    proyecto = Proyecto()
    proyecto.emplazamiento = empl
    proyecto.clima = clima
    return proyecto, list(horas_local)


def _p3_eval_diario(horas: list[pd.Timestamp]) -> dict:
    """p3_eval realista: T_sal_C con None nocturno (horas <7 o >=19)."""
    T_sal_C: list = []
    for ts in horas:
        h = ts.hour
        if h < 7 or h >= 19:
            T_sal_C.append(None)
        else:
            phase = (h - 7) / 11.0
            T_sal_C.append(15.0 + 50.0 * np.sin(np.pi * phase))
    return {
        "modo": "diario",
        "label": "2023-06-15",
        "r": {"horas": horas, "T_salida_C": T_sal_C},
    }


# ---------------------------------------------------------------------------
# Test: _disponibilidad_forzantes_reales
# ---------------------------------------------------------------------------


class TestDisponibilidad:

    def test_sin_p3_eval_falso(self):
        proy, _ = _proyecto_con_clima_diario()
        ok, msg = _disponibilidad_forzantes_reales(None, proy)
        assert not ok
        assert "P3" in msg

    def test_p3_modo_anual_falso(self):
        proy, _ = _proyecto_con_clima_diario()
        ok, msg = _disponibilidad_forzantes_reales({"modo": "anual", "r": {}}, proy)
        assert not ok
        assert "P3" in msg

    def test_sin_clima_falso(self):
        proy = Proyecto()
        proy.emplazamiento = Emplazamiento()
        ok, msg = _disponibilidad_forzantes_reales(
            {"modo": "diario", "r": {}},
            proy,
        )
        assert not ok
        assert "P2" in msg

    def test_todo_ok(self):
        proy, horas = _proyecto_con_clima_diario()
        ok, msg = _disponibilidad_forzantes_reales(_p3_eval_diario(horas), proy)
        assert ok
        assert msg == "OK"


# ---------------------------------------------------------------------------
# Test: _construir_forzantes_reales
# ---------------------------------------------------------------------------


class TestConstruirForzantesReales:

    def test_diario_estructura_basica(self):
        proy, horas = _proyecto_con_clima_diario()
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        assert isinstance(fz, ForzantesAire)
        assert len(fz.t_s) == 24
        assert fz.t_s[0] == 0.0
        assert np.all(np.isfinite(fz.T_ent_K))
        assert np.all(np.isfinite(fz.omega_ent))
        assert np.all(np.isfinite(fz.T_amb_K))
        assert np.all(np.isfinite(fz.v_viento_ms))
        assert np.all(fz.m_dot_aire_seco_kg_s == 0.060)
        assert np.all(fz.v_viento_ms == 2.5)

    def test_nocturna_T_ent_iguala_T_amb(self):
        """Donde T_sal_col es None (noche) se rellena con T_amb local."""
        proy, horas = _proyecto_con_clima_diario()
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        for i, ts in enumerate(horas):
            if ts.hour < 7 or ts.hour >= 19:
                assert fz.T_ent_K[i] == pytest.approx(fz.T_amb_K[i], abs=1e-9)

    def test_mediodia_T_ent_supera_T_amb(self):
        """Al pico solar (mediodía), T_ent > T_amb: el colector aporta calor."""
        proy, horas = _proyecto_con_clima_diario()
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        # Buscamos la hora local con T_sal_col más alto del p3_eval (mediodía sintético).
        T_sal_C = _p3_eval_diario(horas)["r"]["T_salida_C"]
        i_pico = max(
            range(len(T_sal_C)),
            key=lambda i: -1.0 if T_sal_C[i] is None else T_sal_C[i],
        )
        assert fz.T_ent_K[i_pico] > fz.T_amb_K[i_pico] + 10.0

    def test_multi_dia_replica_serie(self):
        proy, horas = _proyecto_con_clima_diario()
        fz1 = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        fz3 = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=3,
        )
        assert len(fz3.t_s) == 3 * len(fz1.t_s)
        np.testing.assert_allclose(fz3.T_ent_K[:24], fz3.T_ent_K[24:48])
        np.testing.assert_allclose(fz3.T_ent_K[24:48], fz3.T_ent_K[48:72])

    def test_omega_consistente_con_HR_y_T_amb(self):
        """ω(t) = humedad_absoluta(HR_NASA, T_amb_NASA(t), P_atm)."""
        proy, horas = _proyecto_con_clima_diario()
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        omega_esperado = np.array([humedad_absoluta(0.40, float(T), 101325.0) for T in fz.T_amb_K])
        np.testing.assert_allclose(fz.omega_ent, omega_esperado, rtol=1e-9)

    def test_p3_anual_levanta(self):
        proy, _ = _proyecto_con_clima_diario()
        with pytest.raises(RuntimeError, match="P3"):
            _construir_forzantes_reales(
                p3_eval={"modo": "anual", "r": {}},
                proyecto=proy,
                caudal_kg_s=0.060,
                n_dias=1,
            )

    def test_sin_clima_levanta(self):
        proy = Proyecto()
        proy.emplazamiento = Emplazamiento()
        with pytest.raises(RuntimeError, match="P2|clima"):
            _construir_forzantes_reales(
                p3_eval={"modo": "diario", "r": {"horas": [], "T_salida_C": []}},
                proyecto=proy,
                caudal_kg_s=0.060,
                n_dias=1,
            )


# ---------------------------------------------------------------------------
# Smoke test end-to-end: forzantes reales alimentan al motor TD
# ---------------------------------------------------------------------------


class TestSmokeMotorTD:
    """Verifica que las forzantes reales sean consumibles por el motor
    termodinámico sin levantar excepciones — captura regresiones de cableado."""

    def test_motor_TD_consume_forzantes_reales(self):
        from calculos.camara_calc import calcular_camara

        proy, horas = _proyecto_con_clima_diario()
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proy,
            caudal_kg_s=0.060,
            n_dias=1,
        )
        cam = Camara(
            geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.5),
            construccion=ConstruccionCamara(
                pared=ParedCamara(
                    capas=[
                        CapaPared(
                            material_id="lana_vidrio_media", espesor_m=0.080, catalogo="aislantes"
                        ),
                    ]
                ),
            ),
            bandejas=ConfiguracionBandejas(
                n_bandejas=5,
                area_bandeja_m2=0.5,
                espesor_capa_m=0.020,
                separacion_entre_bandejas_m=0.15,
            ),
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.060),
            carga_producto=CargaProducto(
                producto_id="yacon",
                masa_total_kg=5.0,
                humedad_inicial_X=9.0,
                humedad_objetivo_X=0.5,
                modelo_capa_fina="page",
            ),
            modo_calculo="termodinamico",
        )
        res = calcular_camara(
            cam,
            T_operacion_K=333.15,
            HR_operacion=0.15,
            T_amb_K=298.15,
            t_max_s=float(fz.t_s[-1]),
            forzantes_aire=fz,
        )
        assert res is not None
        assert hasattr(res, "status")
        assert len(res.X_prod_kg_kg) > 0
        assert len(res.t_array_s) == len(res.X_prod_kg_kg)


# ---------------------------------------------------------------------------
# Cámara radiativa orientada (S47) — I_eq_prod vs GHI, Q_rad_aire, POA colector
# ---------------------------------------------------------------------------


def _camara_translucida(**geo_overrides) -> Camara:
    from core.camara import CarasTranslucidas

    return Camara(
        geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.5, **geo_overrides),
        construccion=ConstruccionCamara(
            cubierta_translucida_id="vidrio_comun",
            caras_translucidas=CarasTranslucidas(techo=True, frente=True),
        ),
        bandejas=ConfiguracionBandejas(
            n_bandejas=5,
            area_bandeja_m2=0.5,
            espesor_capa_m=0.020,
            separacion_entre_bandejas_m=0.15,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.060),
    )


class TestCamaraOrientadaEnForzantesReales:
    """`_construir_forzantes_reales` debe usar la irradiancia equivalente de
    la cámara (no GHI cruda) y poblar Q_rad_aire_W cuando hay caras
    translúcidas más allá del techo horizontal."""

    def test_sin_camara_cae_a_GHI_y_ceros(self):
        """proyecto.camara is None → fallback histórico (GHI, sin Q_rad_aire)."""
        proy, horas = _proyecto_con_clima_diario()
        proy.camara = None
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas), proyecto=proy, caudal_kg_s=0.060, n_dias=1
        )
        ghi_esperado = np.maximum(0.0, 900.0 * np.sin(np.pi * (np.arange(24) - 6.0) / 12.0))
        np.testing.assert_allclose(fz.I_g_W_m2, ghi_esperado, atol=1e-6)
        assert np.all(fz.Q_rad_aire_W == 0.0)

    def test_camara_con_cara_frente_da_I_g_distinto_de_GHI_y_Q_rad_aire_positivo(self):
        proy, horas = _proyecto_con_clima_diario()
        ghi_clima = proy.clima.datos["GHI_Wm2"].to_numpy()
        proy.clima.datos["DNI_Wm2"] = ghi_clima * 0.7
        proy.clima.datos["DHI_Wm2"] = ghi_clima * 0.3
        proy.camara = _camara_translucida(pendiente_techo_deg=20.0)
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas), proyecto=proy, caudal_kg_s=0.060, n_dias=1
        )
        ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (np.arange(24) - 6.0) / 12.0))
        assert not np.allclose(fz.I_g_W_m2, ghi, atol=1e-6)
        assert np.any(fz.Q_rad_aire_W > 0.0)

    def test_POA_colector_no_se_ve_afectada_por_orientacion_de_camara(self):
        """I_g_POA_W_m2 (colector) es independiente de la cámara."""
        proy, horas = _proyecto_con_clima_diario()
        # DNI/DHI aproximados (no físicamente exactos) sólo para que
        # calcular_POA_horizonte no caiga al fallback por columnas faltantes.
        ghi = proy.clima.datos["GHI_Wm2"].to_numpy()
        proy.clima.datos["DNI_Wm2"] = ghi * 0.7
        proy.clima.datos["DHI_Wm2"] = ghi * 0.3

        proy.camara = None
        fz_sin = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas), proyecto=proy, caudal_kg_s=0.060, n_dias=1
        )
        proy.camara = _camara_translucida(pendiente_techo_deg=30.0, acimut_camara_deg=90.0)
        fz_con = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas), proyecto=proy, caudal_kg_s=0.060, n_dias=1
        )
        assert fz_sin.I_g_POA_W_m2 is not None
        np.testing.assert_allclose(fz_sin.I_g_POA_W_m2, fz_con.I_g_POA_W_m2, rtol=1e-9)


class TestAnclaTemporalT0:
    """El ancla absoluta ``t0_utc`` viaja del clima a las forzantes y al resultado.

    Sin ella, las trayectorias del motor (que integra desde t=0) no se pueden
    alinear contra una señal medida — es lo que habilita el diagnóstico de cadena
    completa de la fase 4.
    """

    def test_forzantes_reales_heredan_el_t0_del_clima(self):
        """El ancla sale del propio slice climático usado para forzar."""
        proyecto, horas = _proyecto_con_clima_diario()
        proyecto.camara = Camara(carga_producto=CargaProducto(producto_id="manzana"))
        fz = _construir_forzantes_reales(
            p3_eval=_p3_eval_diario(horas),
            proyecto=proyecto,
            caudal_kg_s=0.1,
            n_dias=1,
        )
        assert fz.t0_utc is not None
        assert fz.t0_utc == proyecto.clima.datos.index[0]

    def test_transitorio_propaga_t0(self):
        """``calcular_todo_transitorio`` hereda el ancla de las forzantes."""
        from calculos.balance_global import ResultadosCompletosTransitorio
        from core.camara import ForzantesAire

        fz = ForzantesAire(
            t_s=np.array([0.0, 3600.0]),
            T_ent_K=np.array([310.0, 312.0]),
            omega_ent=np.array([0.01, 0.01]),
            m_dot_aire_seco_kg_s=np.array([0.1, 0.1]),
            T_amb_K=np.array([293.0, 294.0]),
            v_viento_ms=np.array([2.0, 2.0]),
            t0_utc="2010-05-01T09:00:00Z",
        )
        res = ResultadosCompletosTransitorio(forzantes_base=fz, t0_utc=getattr(fz, "t0_utc", None))
        assert res.t0_utc == "2010-05-01T09:00:00Z"

    def test_forzantes_sin_ancla_por_defecto(self):
        """Serie sintética → sin fecha asociada (el diagnóstico de cadena lo avisa)."""
        from core.camara import ForzantesAire

        fz = ForzantesAire(
            t_s=np.array([0.0, 3600.0]),
            T_ent_K=np.array([310.0, 312.0]),
            omega_ent=np.array([0.01, 0.01]),
            m_dot_aire_seco_kg_s=np.array([0.1, 0.1]),
            T_amb_K=np.array([293.0, 294.0]),
            v_viento_ms=np.array([2.0, 2.0]),
        )
        assert fz.t0_utc is None
