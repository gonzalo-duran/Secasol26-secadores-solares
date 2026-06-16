"""
Tests del híbrido con arranque mañana/tarde + leña consumida (S40, Fase 4).

Cubre ``CargaArranque``, la máscara de calendario y la integración en
``calcular_auxiliar_transitorio``: el quemador opera solo en las ventanas
horarias programadas (independiente de I_g), y reporta la leña consumida.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.auxiliar_calc import _mascara_calendario, calcular_auxiliar_transitorio
from core.auxiliar import (
    Auxiliar,
    CargaArranque,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
)


def _t_s_dias(dias: float) -> np.ndarray:
    """Serie horaria de N días desde t=0 (medianoche)."""
    n = int(dias * 24) + 1
    return np.linspace(0.0, dias * 86400.0, n)


# ---------------------------------------------------------------------------
# CargaArranque
# ---------------------------------------------------------------------------


def test_carga_validacion_hora():
    with pytest.raises(ValueError, match="ARRANQUE_HORA_FUERA_RANGO"):
        CargaArranque(hora_inicio_h=25.0, duracion_h=2.0)


def test_carga_validacion_duracion():
    with pytest.raises(ValueError, match="ARRANQUE_DURACION_NO_POSITIVA"):
        CargaArranque(hora_inicio_h=6.0, duracion_h=0.0)


# ---------------------------------------------------------------------------
# Máscara de calendario
# ---------------------------------------------------------------------------


def test_mascara_ventana_simple():
    t_s = _t_s_dias(1.0)  # 0..24 h, paso 1 h
    cargas = [CargaArranque(hora_inicio_h=6.0, duracion_h=2.0)]
    m = _mascara_calendario(t_s, cargas, 0.0)
    horas = (t_s / 3600.0) % 24.0
    assert m[np.where(horas == 6.0)[0][0]]  # 6:00 activo
    assert m[np.where(horas == 7.0)[0][0]]  # 7:00 activo
    assert not m[np.where(horas == 8.0)[0][0]]  # 8:00 fuera [6,8)
    assert not m[np.where(horas == 12.0)[0][0]]  # mediodía inactivo


def test_mascara_dos_ventanas_manana_tarde():
    t_s = _t_s_dias(1.0)
    cargas = [CargaArranque(6.0, 2.0), CargaArranque(19.0, 3.0)]
    m = _mascara_calendario(t_s, cargas, 0.0)
    horas = (t_s / 3600.0) % 24.0
    assert m[np.where(horas == 6.0)[0][0]]
    assert m[np.where(horas == 20.0)[0][0]]
    assert m[np.where(horas == 21.0)[0][0]]
    assert not m[np.where(horas == 12.0)[0][0]]


def test_mascara_cruza_medianoche():
    t_s = _t_s_dias(1.0)
    cargas = [CargaArranque(hora_inicio_h=23.0, duracion_h=3.0)]  # 23→02
    m = _mascara_calendario(t_s, cargas, 0.0)
    horas = (t_s / 3600.0) % 24.0
    assert m[np.where(horas == 23.0)[0][0]]
    assert m[np.where(horas == 0.0)[0][0]]
    assert m[np.where(horas == 1.0)[0][0]]
    assert not m[np.where(horas == 12.0)[0][0]]


def test_mascara_offset():
    """Con offset, t=0 ya no es medianoche."""
    t_s = _t_s_dias(1.0)
    cargas = [CargaArranque(hora_inicio_h=6.0, duracion_h=2.0)]
    # offset 6 h: t=0 → 6:00 → activo
    m = _mascara_calendario(t_s, cargas, 6.0)
    assert m[0]


# ---------------------------------------------------------------------------
# Integración en el transitorio
# ---------------------------------------------------------------------------


def _aux_biomasa(cargas):
    return Auxiliar(
        tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=20000.0,
        temperatura_maxima_salida_K=343.15,
        PCI_MJ_kg=15.0,
        eficiencia_quemador=0.5,
        cargas_arranque=cargas,
    )


def test_transitorio_opera_solo_en_ventanas():
    """Con calendario, Q_eff > 0 solo en las ventanas; cero al mediodía aunque
    haya sol pleno."""
    aux = _aux_biomasa([CargaArranque(6.0, 2.0), CargaArranque(19.0, 3.0)])
    t_s = _t_s_dias(2.0)
    T_ent = np.full(len(t_s), 300.0)
    I_g = np.full(len(t_s), 900.0)  # sol pleno todo el tiempo (irrelevante con calendario)
    res = calcular_auxiliar_transitorio(
        aux, T_entrada_K_serie=T_ent, t_s=t_s, caudal_masico_kg_s=2.0, I_g_W_m2_serie=I_g
    )
    horas = (t_s / 3600.0) % 24.0
    idx_mediodia = np.where(horas == 12.0)[0]
    idx_manana = np.where(horas == 6.0)[0]
    assert np.all(res.Q_efectivo_W[idx_mediodia] == 0.0)
    assert np.all(res.Q_efectivo_W[idx_manana] > 0.0)


def test_transitorio_lena_consumida():
    """El quemador reporta leña consumida coherente con E_aux/(PCI·η)."""
    aux = _aux_biomasa([CargaArranque(6.0, 2.0), CargaArranque(19.0, 3.0)])
    t_s = _t_s_dias(3.0)
    T_ent = np.full(len(t_s), 300.0)
    res = calcular_auxiliar_transitorio(
        aux, T_entrada_K_serie=T_ent, t_s=t_s, caudal_masico_kg_s=2.0
    )
    assert res.lena_consumida_kg > 0.0
    esperado = res.E_aux_MJ / (15.0 * 0.5)
    assert res.lena_consumida_kg == pytest.approx(esperado, rel=1e-9)


def test_electrico_sin_lena():
    """Auxiliar eléctrico → leña consumida = 0."""
    aux = Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        potencia_nominal_W=5000.0,
        cargas_arranque=[CargaArranque(6.0, 2.0)],
    )
    t_s = _t_s_dias(2.0)
    res = calcular_auxiliar_transitorio(
        aux, T_entrada_K_serie=np.full(len(t_s), 300.0), t_s=t_s, caudal_masico_kg_s=2.0
    )
    assert res.lena_consumida_kg == 0.0


def test_back_compat_sin_calendario():
    """Sin cargas_arranque, el transitorio opera como antes (por día/I_g)."""
    aux = Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        potencia_nominal_W=5000.0,
        disponible_nocturno=False,
    )
    t_s = _t_s_dias(1.0)
    # I_g alto solo en 6 horas centrales → activo solo ahí
    horas = (t_s / 3600.0) % 24.0
    I_g = np.where((horas >= 9.0) & (horas <= 15.0), 800.0, 0.0)
    res = calcular_auxiliar_transitorio(
        aux,
        T_entrada_K_serie=np.full(len(t_s), 300.0),
        t_s=t_s,
        caudal_masico_kg_s=2.0,
        I_g_W_m2_serie=I_g,
    )
    assert np.all(res.Q_efectivo_W[horas < 8.0] == 0.0)
    assert np.any(res.Q_efectivo_W[(horas >= 9.0) & (horas <= 15.0)] > 0.0)
