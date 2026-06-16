"""Tests de la carta psicrométrica del proceso (calculos/carta_psicrometrica.py).

Cubre la capa pura: curvas de fondo (saturación, HR, isentálpica), corrección por
altitud, y extracción de los estados del proceso desde resultados (Constantes /
Transitorio / Ventana) con detección de cámara directa.
"""

from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pytest

from calculos.carta_psicrometrica import (
    curvas_fondo,
    estados_proceso,
    isentalpica,
)
from calculos.psicrometria import (
    entalpia_aire_humedo,
    humedad_absoluta,
    omega_saturacion,
)

_P_SALTA = 88000.0  # ~1187 m
_P_MAR = 101325.0


# ---------------------------------------------------------------------------
# Curvas de fondo
# ---------------------------------------------------------------------------


def test_saturacion_monotona_creciente():
    c = curvas_fondo(0, 80, _P_MAR)
    sat = c["omega_sat"]
    sat = sat[np.isfinite(sat)]
    assert np.all(np.diff(sat) > 0)


def test_familia_hr_ordenada():
    c = curvas_fondo(0, 80, _P_MAR)
    j = int(np.argmin(np.abs(c["T_C"] - 40.0)))
    assert c["hr"][0.9][j] > c["hr"][0.5][j] > c["hr"][0.1][j]


def test_altitud_sube_omega_saturacion():
    # A menor presión (altitud), ω de saturación es mayor a la misma T.
    j_T = 50.0
    w_alta = humedad_absoluta(0.99, j_T + 273.15, _P_SALTA)
    w_mar = humedad_absoluta(0.99, j_T + 273.15, _P_MAR)
    assert w_alta > w_mar


def test_isentalpica_conserva_entalpia():
    h_obj = entalpia_aire_humedo(318.15, 0.012)
    T_C, omega = isentalpica(h_obj, 30, 70, _P_MAR, n=40)
    # Chequear solo los puntos no recortados por saturación (ω < ω_sat).
    val = [
        entalpia_aire_humedo(t + 273.15, w)
        for t, w in zip(T_C, omega)
        if np.isfinite(w) and w < omega_saturacion(t + 273.15, _P_MAR) - 1e-6
    ]
    assert len(val) > 5
    assert max(abs(h - h_obj) for h in val) < 1.0  # J/kg, exacto por construcción


# ---------------------------------------------------------------------------
# Extracción de estados — transitorio
# ---------------------------------------------------------------------------


def _res_transitorio(*, q_rad=False, T_flujo_K=313.15):
    n = 12
    t_s = np.arange(n) * 3600.0
    poa = np.array([0, 0, 100, 300, 600, 800, 950, 800, 500, 200, 0, 0], float)
    T_amb = np.full(n, 293.15)
    omega = np.full(n, humedad_absoluta(0.4, 293.15, _P_SALTA))
    fb = NS(t_s=t_s, T_ent_K=T_amb + 15, omega_ent=omega, T_amb_K=T_amb, I_g_POA_W_m2=poa)
    fa = NS(t_s=t_s, T_ent_K=T_amb + 25, omega_ent=omega, T_amb_K=T_amb, I_g_POA_W_m2=poa)
    m = 200
    tc = np.linspace(0, (n - 1) * 3600.0, m)
    cam = NS(
        t_array_s=tc,
        T_flujo_K=np.full(m, T_flujo_K),
        omega_flujo_kg_kg=omega[0] + np.linspace(0, 0.01, m),
        Q_rad_W=(np.full(m, 500.0) if q_rad else np.zeros(m)),
    )
    return NS(camara=cam, forzantes_aplicadas=fa, forzantes_base=fb)


def test_transitorio_cuatro_estados_y_omega_constante():
    d = estados_proceso(_res_transitorio(), P_Pa=_P_SALTA)
    assert d is not None
    estados = d["estados"]
    assert len(estados) == 4
    assert [e.nombre for e in estados][0] == "Ambiente"
    assert [e.nombre for e in estados][-1] == "Salida cámara"
    # ω constante en el calentamiento sensible (ambiente → entrada cámara).
    ws = [e.omega_kg_kg for e in estados[:-1]]
    assert max(ws) - min(ws) < 1e-9
    # La salida de cámara gana humedad.
    assert estados[-1].omega_kg_kg > estados[-2].omega_kg_kg


def test_idx_representativo_es_pico_poa():
    # El estado del colector debe tomarse en la hora de POA máxima (idx=6 → +15 K).
    d = estados_proceso(_res_transitorio(), P_Pa=_P_SALTA)
    salida_col = next(e for e in d["estados"] if e.nombre == "Salida colector")
    assert salida_col.T_C == pytest.approx(293.15 + 15 - 273.15, abs=0.01)


def test_camara_directa_detectada_por_q_rad():
    assert estados_proceso(_res_transitorio(q_rad=False), P_Pa=_P_SALTA)["camara_directa"] is False
    assert estados_proceso(_res_transitorio(q_rad=True), P_Pa=_P_SALTA)["camara_directa"] is True


# ---------------------------------------------------------------------------
# Extracción de estados — constantes y casos None
# ---------------------------------------------------------------------------


def test_constantes_requiere_omega_amb():
    cam = NS(
        t_array_s=np.array([0.0, 1.0]),
        T_flujo_K=np.array([313.15, 313.15]),
        omega_flujo_kg_kg=np.array([0.01, 0.012]),
        m_dot_w_kg_s=np.array([1e-4, 2e-4]),
        Q_rad_W=np.zeros(2),
    )
    col = NS(T_entrada_K=293.15, T_salida_K=313.15)
    res = NS(camara=cam, colector=col, T_entrada_camara_K=318.15, forzantes_aplicadas=None)
    # Sin omega_amb → None.
    assert estados_proceso(res, P_Pa=_P_SALTA) is None
    # Con omega_amb → 4 estados, ω constante en el calentamiento.
    d = estados_proceso(res, P_Pa=_P_SALTA, omega_amb=humedad_absoluta(0.4, 293.15, _P_SALTA))
    assert d is not None and len(d["estados"]) == 4
    ws = [e.omega_kg_kg for e in d["estados"][:-1]]
    assert max(ws) - min(ws) < 1e-9


def test_sin_camara_ni_subtipo_devuelve_none():
    # Sin cámara y sin subtipo → None (resultado incompatible).
    assert estados_proceso(NS(camara=None), P_Pa=_P_MAR) is None
    # ResultadoVentana sin estados de aire poblados → None.
    assert estados_proceso(NS(subtipo="BATCH", aire_T_ent_K=None), P_Pa=_P_MAR) is None


# ---------------------------------------------------------------------------
# Extracción de estados — Ventana (gran escala)
# ---------------------------------------------------------------------------


def test_ventana_batch_tres_estados():
    res = NS(
        subtipo="BATCH",
        aire_T_amb_K=293.15,
        aire_T_ent_K=333.15,
        aire_omega_ent=humedad_absoluta(0.5, 293.15, _P_SALTA),
        aire_T_salida_K=331.0,
        aire_omega_salida=0.011,
        camara_directa=False,
        perfil_T_aire_zonas_K=None,
        perfil_omega_aire_zonas=None,
    )
    d = estados_proceso(res, P_Pa=_P_SALTA)
    assert d is not None
    nombres = [e.nombre for e in d["estados"]]
    assert nombres == ["Ambiente", "Entrada cámara", "Salida cámara"]
    # ω constante en el calentamiento sensible (ambiente → entrada).
    assert d["estados"][0].omega_kg_kg == pytest.approx(d["estados"][1].omega_kg_kg)
    # La salida gana humedad.
    assert d["estados"][2].omega_kg_kg > d["estados"][1].omega_kg_kg


def test_ventana_semicontinuo_path_zonas_no_colapsa():
    # Convención: índice 0 = salida del aire (húmedo), N−1 = entrada (seco).
    res = NS(
        subtipo="SEMICONTINUO",
        aire_T_amb_K=293.15,
        aire_T_ent_K=333.15,
        aire_omega_ent=humedad_absoluta(0.5, 293.15, _P_SALTA),
        perfil_T_aire_zonas_K=np.array([330.0, 331.0, 332.0]),
        perfil_omega_aire_zonas=np.array([0.0100, 0.0090, 0.0085]),
        camara_directa=False,
    )
    d = estados_proceso(res, P_Pa=_P_SALTA)
    assert d is not None
    nombres = [e.nombre for e in d["estados"]]
    # Ambiente + Entrada túnel + 3 zonas (no se colapsan).
    assert nombres[0] == "Ambiente"
    assert nombres[1] == "Entrada túnel"
    assert nombres[-1] == "Salida túnel"
    assert len(d["estados"]) == 5
    assert d["idx_inlet"] == 1
    # ω no decrece al atravesar el túnel (gana humedad a contracorriente).
    ws = [e.omega_kg_kg for e in d["estados"][d["idx_inlet"] :]]
    assert all(ws[i + 1] >= ws[i] - 1e-12 for i in range(len(ws) - 1))


def test_caja_sin_colector_colapsa_estados():
    # CAJA: sin colector, ambiente = entrada cámara → estados consecutivos se colapsan.
    cam = NS(
        t_array_s=np.array([0.0, 1.0]),
        T_flujo_K=np.array([305.15, 306.15]),
        omega_flujo_kg_kg=np.array([0.01, 0.013]),
        m_dot_w_kg_s=np.array([1e-4, 3e-4]),
        Q_rad_W=np.array([400.0, 400.0]),
    )
    res = NS(camara=cam, colector=None, T_entrada_camara_K=298.15, forzantes_aplicadas=None)
    d = estados_proceso(res, P_Pa=_P_MAR, omega_amb=humedad_absoluta(0.5, 298.15, _P_MAR))
    assert d is not None
    # Ambiente/colector/entrada coinciden → se colapsan a ≤ 2 estados (entrada + salida).
    assert len(d["estados"]) == 2
    assert d["camara_directa"] is True
