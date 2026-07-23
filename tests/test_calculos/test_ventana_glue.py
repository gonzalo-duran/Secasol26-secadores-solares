"""
Tests del glue de ventana de producción (S40, Fase 5 — capa cálculo).

Cubre ``armar_forzantes_ventana`` y ``calcular_todo_ventana`` con clima
sintético horario (sin red NASA POWER): construcción de forzantes desde
colector forzado + caño maestro + auxiliar con calendario, y la corrida
end-to-end de la ventana para ambos subtipos.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from calculos.balance_global import armar_forzantes_ventana, calcular_todo_ventana
from calculos.simulacion_ventana import ResultadoVentana
from core.auxiliar import Auxiliar, CargaArranque, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConfiguracionTunel,
    GeometriaCamara,
)
from core.colector import BancoColectores, CanoMaestro, Colector
from core.emplazamiento import Emplazamiento
from core.proyecto import (
    Configuracion,
    ModoAnalisis,
    Proyecto,
    SubtipoGranEscala,
    Tipologia,
)


def _clima_sintetico(dias: int = 3) -> pd.DataFrame:
    """Clima horario sintético con DatetimeIndex UTC y columnas COLUMNAS_SI."""
    n = dias * 24
    idx = pd.date_range("2020-03-20 00:00", periods=n, freq="h", tz="UTC")
    horas = np.array([t.hour for t in idx], dtype=float)
    # Diurno: GHI tipo coseno centrado al mediodía local (~15 UTC en Salta).
    ghi = np.maximum(0.0, 950.0 * np.cos((horas - 15.0) / 24.0 * 2 * np.pi))
    T_amb = 288.0 + 8.0 * np.sin((horas - 9.0) / 24.0 * 2 * np.pi)
    return pd.DataFrame(
        {
            "T_amb_K": T_amb,
            "GHI_Wm2": ghi,
            "DNI_Wm2": ghi * 0.85,
            "DHI_Wm2": ghi * 0.15,
            "WS_ms": np.full(n, 2.0),
            "presion_Pa": np.full(n, 88000.0),
            "HR": np.clip(0.6 - 0.4 * (ghi / 950.0), 0.1, 0.9),
        },
        index=idx,
    )


def _proyecto(
    subtipo: SubtipoGranEscala,
    *,
    con_tunel=False,
    con_cano=False,
    con_aux=False,
    masa_total_kg=60.0,
) -> Proyecto:
    banco = BancoColectores(
        n_serie=1,
        n_paralelo=10,
        cano_maestro=CanoMaestro() if con_cano else None,
    )
    camara = Camara(
        geometria=GeometriaCamara(largo_m=3.0, ancho_m=2.0, alto_m=2.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=15,
            area_bandeja_m2=1.5,
            espesor_capa_m=0.03,
            separacion_entre_bandejas_m=0.12,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=2.0),
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=masa_total_kg,
            humedad_inicial_X=3.0,
            humedad_objetivo_X=0.20,
        ),
        tunel=ConfiguracionTunel(n_zonas=3, intervalo_avance_h=12.0) if con_tunel else None,
    )
    aux = None
    if con_aux:
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=30000.0,
            temperatura_maxima_salida_K=343.15,
            PCI_MJ_kg=15.0,
            eficiencia_quemador=0.5,
            cargas_arranque=[CargaArranque(6.0, 2.0), CargaArranque(19.0, 3.0)],
        )
    return Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.VENTANA,
            subtipo_gran_escala=subtipo,
            ventana_inicio=date(2020, 3, 20),
            ventana_fin=date(2020, 3, 23),
        ),
        emplazamiento=Emplazamiento(),
        colector=Colector(banco=banco),
        camara=camara,
        auxiliar=aux,
    )


# ---------------------------------------------------------------------------
# armar_forzantes_ventana
# ---------------------------------------------------------------------------


def test_forzantes_longitud_y_calentamiento():
    proy = _proyecto(SubtipoGranEscala.BATCH)
    df = _clima_sintetico(dias=2)
    fz, lena, adv, _diag = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert len(fz.t_s) == len(df)
    assert fz.I_g_POA_W_m2 is not None
    # El colector calienta: T_ent ≥ T_amb en todo el horizonte.
    assert np.all(fz.T_ent_K >= fz.T_amb_K - 1e-6)
    # Al mediodía (POA alta) hay calentamiento neto positivo.
    assert np.max(fz.T_ent_K - fz.T_amb_K) > 2.0
    assert lena == 0.0  # sin auxiliar


def test_cano_maestro_modifica_T_ent():
    df = _clima_sintetico(dias=2)
    sin_cano = _proyecto(SubtipoGranEscala.BATCH, con_cano=False)
    con_cano = _proyecto(SubtipoGranEscala.BATCH, con_cano=True)
    fz_sin, _, _, _ = armar_forzantes_ventana(sin_cano, df, P_Pa=88000.0)
    fz_con, _, _, _ = armar_forzantes_ventana(con_cano, df, P_Pa=88000.0)
    # El caño introduce una ΔT térmica → T_ent difiere.
    assert not np.allclose(fz_sin.T_ent_K, fz_con.T_ent_K)


def test_diag_cano_maestro_para_exports():
    """Con caño maestro el diag trae ΔT media/mínima y ΔP > 0; sin caño, ninguna
    de esas claves. (El diag lleva además la energía útil del colector, que no
    depende del caño — por eso se chequean las claves y no que el dict esté
    vacío.)"""
    df = _clima_sintetico(dias=2)
    sin_cano = _proyecto(SubtipoGranEscala.BATCH, con_cano=False)
    con_cano = _proyecto(SubtipoGranEscala.BATCH, con_cano=True)
    _, _, _, diag_sin = armar_forzantes_ventana(sin_cano, df, P_Pa=88000.0)
    _, _, _, diag_con = armar_forzantes_ventana(con_cano, df, P_Pa=88000.0)
    assert not any(k.startswith("cano_") for k in diag_sin)
    assert "cano_delta_T_media_K" in diag_con
    assert "cano_delta_T_minima_K" in diag_con
    assert diag_con["cano_delta_T_minima_K"] <= diag_con["cano_delta_T_media_K"]
    assert diag_con["cano_delta_P_Pa"] > 0.0


def test_calcular_todo_ventana_copia_diag_cano():
    """El resultado de ventana expone los diagnósticos del caño maestro."""
    proy = _proyecto(SubtipoGranEscala.BATCH, con_cano=True)
    df = _clima_sintetico(dias=2)
    res = calcular_todo_ventana(proy, df, P_Pa=88000.0)
    assert res.cano_delta_P_Pa is not None and res.cano_delta_P_Pa > 0.0
    assert res.cano_delta_T_media_K is not None

    sin_cano = _proyecto(SubtipoGranEscala.BATCH, con_cano=False)
    res_sin = calcular_todo_ventana(sin_cano, df, P_Pa=88000.0)
    assert res_sin.cano_delta_P_Pa is None


def test_auxiliar_arranque_suma_lena():
    proy = _proyecto(SubtipoGranEscala.BATCH, con_aux=True)
    df = _clima_sintetico(dias=3)
    fz, lena, adv, _diag = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert lena > 0.0  # el quemador arrancó en las ventanas mañana/tarde


# ---------------------------------------------------------------------------
# Caudal único de sistema (S41)
# ---------------------------------------------------------------------------


def test_colector_forzado_usa_caudal_sistema():
    """El colector se evalúa al caudal del ventilador: menos caudal → más ΔT."""
    df = _clima_sintetico(dias=2)
    proy_lento = _proyecto(SubtipoGranEscala.BATCH)
    proy_lento.camara.flujo = ConfiguracionFlujo(caudal_masico_kg_s=0.05)
    proy_rapido = _proyecto(SubtipoGranEscala.BATCH)
    proy_rapido.camara.flujo = ConfiguracionFlujo(caudal_masico_kg_s=1.0)

    v_diseno_antes = proy_lento.colector.unidad.velocidad_diseno_ms
    fz_lento, _, _, _ = armar_forzantes_ventana(proy_lento, df, P_Pa=88000.0)
    fz_rapido, _, _, _ = armar_forzantes_ventana(proy_rapido, df, P_Pa=88000.0)

    # Mismo banco, menos caudal → el aire sale más caliente al mediodía.
    assert np.max(fz_lento.T_ent_K) > np.max(fz_rapido.T_ent_K) + 5.0
    # La mutación de velocidad_diseno_ms se restaura (try/finally).
    assert proy_lento.colector.unidad.velocidad_diseno_ms == v_diseno_antes


def test_adv_ventana_caudal_banco_incoherente():
    """Banco a v_diseño muy distinto del caudal del sistema → advertencia."""
    df = _clima_sintetico(dias=2)
    proy = _proyecto(SubtipoGranEscala.BATCH)
    # Banco: 10 ramas × 0.5 m/s × 0.025 m² ≈ 0.13 kg/s vs sistema 2.0 kg/s.
    _, _, adv, _ = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert any("ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE" in a for a in adv)


def test_adv_ventana_caudal_coherente_sin_advertencia():
    """Caudal del sistema ≈ caudal de diseño del banco → sin advertencia."""
    df = _clima_sintetico(dias=2)
    proy = _proyecto(SubtipoGranEscala.BATCH)
    # Igualar: 10 ramas × 2.0 m/s × 0.025 m² × ρ(~1.05) ≈ 0.52 kg/s.
    proy.colector.unidad.velocidad_diseno_ms = 2.0
    proy.camara.flujo = ConfiguracionFlujo(caudal_masico_kg_s=0.52)
    # Sección frontal chica para que la velocidad en cámara no dispare la otra.
    proy.camara.geometria = GeometriaCamara(largo_m=3.0, ancho_m=1.0, alto_m=1.2)
    _, _, adv, _ = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert not any("ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE" in a for a in adv)
    assert not any("ADV_VENTANA_VELOCIDAD_CAMARA_BAJA" in a for a in adv)


def test_adv_ventana_velocidad_camara_baja():
    """Caudal chico en cámara grande → velocidad < 10 cm/s → advertencia."""
    df = _clima_sintetico(dias=2)
    proy = _proyecto(SubtipoGranEscala.BATCH)
    proy.camara.flujo = ConfiguracionFlujo(caudal_masico_kg_s=0.05)
    _, _, adv, _ = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert any("ADV_VENTANA_VELOCIDAD_CAMARA_BAJA" in a for a in adv)


# ---------------------------------------------------------------------------
# calcular_todo_ventana (end-to-end)
# ---------------------------------------------------------------------------


def test_calcular_todo_ventana_batch():
    proy = _proyecto(SubtipoGranEscala.BATCH, masa_total_kg=40.0)
    df = _clima_sintetico(dias=3)
    res = calcular_todo_ventana(proy, df, P_Pa=88000.0)
    assert isinstance(res, ResultadoVentana)
    assert res.subtipo == "BATCH"
    assert res.masa_evaporada_kg >= 0.0
    assert res.status != "error"


def test_calcular_todo_ventana_semicontinuo():
    proy = _proyecto(
        SubtipoGranEscala.SEMICONTINUO, con_tunel=True, con_cano=True, masa_total_kg=120.0
    )
    df = _clima_sintetico(dias=3)
    res = calcular_todo_ventana(proy, df, P_Pa=88000.0)
    assert res.subtipo == "SEMICONTINUO"
    assert res.status != "error"
    assert res.masa_evaporada_kg >= 0.0
    assert res.perfil_X_zonas is not None


def test_ventana_con_hibrido_completo():
    """Semicontinuo + caño maestro + híbrido arranque: corre y suma leña."""
    proy = _proyecto(
        SubtipoGranEscala.SEMICONTINUO,
        con_tunel=True,
        con_cano=True,
        con_aux=True,
        masa_total_kg=120.0,
    )
    df = _clima_sintetico(dias=3)
    res = calcular_todo_ventana(proy, df, P_Pa=88000.0)
    assert res.status != "error"
    assert res.lena_consumida_kg > 0.0


# ---------------------------------------------------------------------------
# Paso de trabajo sub-horario (mejora 38, fase 1b)
# ---------------------------------------------------------------------------


def _clima_15min(dias: int = 2) -> pd.DataFrame:
    """Clima sintético a 15 min: interpola linealmente el horario a la grilla fina."""
    horario = _clima_sintetico(dias=dias)
    idx = pd.date_range(horario.index[0], horario.index[-1], freq="15min")
    return horario.reindex(horario.index.union(idx)).interpolate(method="time").reindex(idx)


def test_forzantes_ventana_deriva_dt_del_indice():
    """armar_forzantes_ventana deriva el paso del índice (15 min), no asume 3600 s."""
    proy = _proyecto(SubtipoGranEscala.BATCH)
    df = _clima_15min(dias=2)
    fz, _lena, _adv, _ = armar_forzantes_ventana(proy, df, P_Pa=88000.0)
    assert len(fz.t_s) == len(df)
    # Paso de la serie de forzantes = 900 s (15 min).
    assert fz.t_s[1] - fz.t_s[0] == pytest.approx(900.0)
    assert fz.t_s[-1] == pytest.approx((len(df) - 1) * 900.0)


def test_ventana_1h_vs_15min_converge():
    """Sobre clima suave, la misma ventana a 1 h y a 15 min da masa evaporada
    y sequedad coherentes (el motor interpola las forzantes → convergencia)."""
    proy = _proyecto(SubtipoGranEscala.BATCH, masa_total_kg=60.0)
    df_h = _clima_sintetico(dias=3)
    df_q = _clima_15min(dias=3)

    res_h = calcular_todo_ventana(proy, df_h, P_Pa=88000.0)
    res_q = calcular_todo_ventana(proy, df_q, P_Pa=88000.0)

    assert res_h.status != "error"
    assert res_q.status != "error"
    # La serie fina tiene ~4× nodos.
    assert len(df_q) > 3 * len(df_h)
    # Masa seca producida coherente entre pasos (tolerancia amplia: distinta grilla).
    assert res_q.masa_seca_producida_kg == pytest.approx(res_h.masa_seca_producida_kg, rel=0.10)
