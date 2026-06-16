"""
Tests del orquestador de ventana `simular_ventana` (S40, Fase 2).

Acumula producción sobre una ventana [inicio, fin] para GRAN_ESCALA:
  - BATCH: encadena lotes (recarga event-driven al alcanzar X_objetivo),
  - SEMICONTINUO: corre el túnel a contracorriente una vez sobre la ventana.

Se usan forzantes sintéticas constantes (aire caliente y seco), sin tocar la
red NASA POWER. Producto con GAB calibrado (yacon) para que el motor TD opere.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.psicrometria import humedad_absoluta
from calculos.simulacion_ventana import ResultadoVentana, simular_ventana
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConfiguracionTunel,
    ForzantesAire,
    GeometriaCamara,
)
from core.proyecto import (
    Configuracion,
    ModoAnalisis,
    Proyecto,
    SubtipoGranEscala,
    Tipologia,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _forzantes_ventana(*, dias: float, T_ent_C: float = 60.0, HR: float = 0.15, m_dot: float = 2.0):
    """Forzantes constantes (aire caliente/seco del colector) sobre N días,
    muestreadas cada hora."""
    t_max = dias * 86400.0
    n = int(dias * 24) + 1
    t_s = np.linspace(0.0, t_max, n)
    T_ent = T_ent_C + 273.15
    return ForzantesAire(
        t_s=t_s,
        T_ent_K=np.full(n, T_ent),
        omega_ent=np.full(n, humedad_absoluta(HR, T_ent)),
        m_dot_aire_seco_kg_s=np.full(n, m_dot),
        T_amb_K=np.full(n, 293.15),
        v_viento_ms=np.full(n, 2.0),
    )


def _proyecto_gran_escala(
    subtipo: SubtipoGranEscala,
    *,
    con_tunel: bool = False,
    masa_total_kg: float = 60.0,
    n_zonas: int = 3,
    intervalo_avance_h: float = 12.0,
) -> Proyecto:
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
        tunel=(
            ConfiguracionTunel(n_zonas=n_zonas, intervalo_avance_h=intervalo_avance_h)
            if con_tunel
            else None
        ),
    )
    return Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.DIARIO,
            subtipo_gran_escala=subtipo,
        ),
        camara=camara,
    )


# ---------------------------------------------------------------------------
# BATCH
# ---------------------------------------------------------------------------


def test_batch_completa_lotes():
    """Ventana larga + aire caliente → ≥ 1 lote completo, producción y tasa > 0."""
    proy = _proyecto_gran_escala(SubtipoGranEscala.BATCH)
    fz = _forzantes_ventana(dias=8.0)
    res = simular_ventana(proy, forzantes_base=fz)
    assert isinstance(res, ResultadoVentana)
    assert res.subtipo == "BATCH"
    assert res.n_batches_completos >= 1
    assert res.masa_seca_producida_kg > 0.0
    assert res.tasa_regimen_kg_dia is not None and res.tasa_regimen_kg_dia > 0.0
    assert res.t_secado_medio_s is not None and res.t_secado_medio_s > 0.0


def test_batch_mas_dias_mas_produccion():
    """Más ventana → más producción acumulada (más lotes)."""
    proy = _proyecto_gran_escala(SubtipoGranEscala.BATCH)
    corto = simular_ventana(proy, forzantes_base=_forzantes_ventana(dias=6.0))
    largo = simular_ventana(proy, forzantes_base=_forzantes_ventana(dias=14.0))
    assert largo.masa_seca_producida_kg >= corto.masa_seca_producida_kg
    assert largo.n_batches_completos >= corto.n_batches_completos


def test_batch_ventana_corta_sin_lotes():
    """Ventana muy corta → no completa ningún lote."""
    proy = _proyecto_gran_escala(SubtipoGranEscala.BATCH)
    res = simular_ventana(proy, forzantes_base=_forzantes_ventana(dias=0.25))
    assert res.n_batches_completos == 0
    assert res.masa_seca_producida_kg == 0.0
    assert res.tasa_regimen_kg_dia is None


# ---------------------------------------------------------------------------
# SEMICONTINUO
# ---------------------------------------------------------------------------


def test_semicontinuo_regimen():
    """Túnel con horizonte suficiente → régimen, producción y throughput > 0."""
    proy = _proyecto_gran_escala(
        SubtipoGranEscala.SEMICONTINUO, con_tunel=True, n_zonas=3, intervalo_avance_h=12.0
    )
    fz = _forzantes_ventana(dias=6.0)  # 12 avances de 12 h
    res = simular_ventana(proy, forzantes_base=fz)
    assert res.subtipo == "SEMICONTINUO"
    assert res.status == "regimen_alcanzado"
    assert res.X_salida_regimen is not None
    assert res.masa_seca_producida_kg > 0.0
    assert res.throughput_fresco_kg_dia is not None and res.throughput_fresco_kg_dia > 0.0
    assert res.tasa_regimen_kg_dia is not None and res.tasa_regimen_kg_dia > 0.0


def test_semicontinuo_perfil_monotono():
    """El perfil espacial de X decrece de la zona fresca a la seca."""
    proy = _proyecto_gran_escala(
        SubtipoGranEscala.SEMICONTINUO, con_tunel=True, n_zonas=4, intervalo_avance_h=12.0
    )
    res = simular_ventana(proy, forzantes_base=_forzantes_ventana(dias=8.0))
    X = res.perfil_X_zonas
    assert X is not None and X.shape == (4,)
    assert np.all(np.diff(X) <= 1e-6)
    assert X[0] > X[-1]


def test_semicontinuo_sin_tunel_error():
    """SEMICONTINUO sin camara.tunel → status error con aviso."""
    proy = _proyecto_gran_escala(SubtipoGranEscala.SEMICONTINUO, con_tunel=False)
    res = simular_ventana(proy, forzantes_base=_forzantes_ventana(dias=4.0))
    assert res.status == "error"
    assert any("SIN_TUNEL" in a for a in res.advertencias)


# ---------------------------------------------------------------------------
# Comparación batch vs semicontinuo (misma carga total)
# ---------------------------------------------------------------------------


def test_ambos_subtipos_producen():
    """Con la misma carga total, ambos subtipos producen masa seca positiva."""
    proy_b = _proyecto_gran_escala(SubtipoGranEscala.BATCH, masa_total_kg=120.0)
    proy_s = _proyecto_gran_escala(
        SubtipoGranEscala.SEMICONTINUO,
        con_tunel=True,
        masa_total_kg=120.0,
        n_zonas=3,
        intervalo_avance_h=12.0,
    )
    fz = _forzantes_ventana(dias=8.0)
    rb = simular_ventana(proy_b, forzantes_base=fz)
    rs = simular_ventana(proy_s, forzantes_base=fz)
    assert rb.masa_seca_producida_kg > 0.0
    assert rs.masa_seca_producida_kg > 0.0


# ---------------------------------------------------------------------------
# Helper de slicing de forzantes
# ---------------------------------------------------------------------------


def test_slice_forzantes_rezera_tiempo():
    from calculos.simulacion_ventana import _slice_forzantes

    fz = _forzantes_ventana(dias=4.0)
    sub = _slice_forzantes(fz, 2.0 * 86400.0)
    assert sub is not None
    assert sub.t_s[0] == 0.0
    assert sub.t_s[-1] == pytest.approx(2.0 * 86400.0, rel=1e-6)


def test_slice_forzantes_fuera_de_rango():
    from calculos.simulacion_ventana import _slice_forzantes

    fz = _forzantes_ventana(dias=2.0)
    assert _slice_forzantes(fz, 3.0 * 86400.0) is None
