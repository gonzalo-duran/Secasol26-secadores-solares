"""Tests del motor de barridos paramétricos.

Etapa actual: aplicación de un valor al proyecto (``aplicar_parametro`` +
resolución de path). El loop ``correr_barrido`` se testea en una etapa posterior.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from calculos.balance_global import armar_forzantes_aire
from calculos.barrido_parametrico import (
    BarridoConfig,
    aplicar_parametro,
    correr_barrido,
)
from calculos.psicrometria import humedad_absoluta
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    GeometriaCamara,
    OperacionAnualConfig,
)
from core.clima import Clima
from core.colector import Colector
from core.emplazamiento import Emplazamiento
from core.proyecto import (
    Configuracion,
    Meta,
    ModoAnalisis,
    Proyecto,
    Tipologia,
)

# Condiciones representativas para el modo Constantes.
_COND_CONST = dict(
    T_amb_K=298.15,
    I_g_W_m2=800.0,
    v_viento_ms=2.0,
    T_entrada_K=298.15,
    HR_camara=0.20,
)


@pytest.fixture
def proyecto_completo() -> Proyecto:
    """ARMARIO con colector, cámara y emplazamiento configurados."""
    p = Proyecto(
        meta=Meta(nombre="Test barrido", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.emplazamiento = Emplazamiento(latitud_deg=-24.7, longitud_deg=-65.4)
    p.colector = Colector()
    # Cámara dimensionada para que el motor termodinámico converja a X_obj en
    # el rango de caudales barridos (yacón con GAB real, cámara chica). Desde
    # S38 el motor de cámara es único (termodinámico).
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=0.6, ancho_m=0.4, alto_m=0.6),
        bandejas=ConfiguracionBandejas(
            n_bandejas=3,
            area_bandeja_m2=0.20,
            espesor_capa_m=0.015,
            separacion_entre_bandejas_m=0.06,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.10),
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=2.0,
            humedad_inicial_X=9.0,
            humedad_objetivo_X=0.50,
        ),
    )
    return p


def test_aplicar_caudal_muta_proyecto(proyecto_completo):
    ret = aplicar_parametro(proyecto_completo, "caudal_masico", 0.05)
    assert ret is None
    assert proyecto_completo.camara.flujo.caudal_masico_kg_s == pytest.approx(0.05)


def test_aplicar_parametro_anidado_3_niveles(proyecto_completo):
    """Path de 3 niveles (camara.geometria.largo_m) resuelve y muta."""
    aplicar_parametro(proyecto_completo, "largo_camara", 2.5)
    assert proyecto_completo.camara.geometria.largo_m == pytest.approx(2.5)


def test_aplicar_parametro_2_niveles_emplazamiento(proyecto_completo):
    """Path de 2 niveles (emplazamiento.pendiente_colector_deg)."""
    aplicar_parametro(proyecto_completo, "pendiente_colector", 40.0)
    assert proyecto_completo.emplazamiento.pendiente_colector_deg == pytest.approx(40.0)


def test_transform_pre_set_int(proyecto_completo):
    """n_colectores_serie aplica int() al valor SI flotante."""
    aplicar_parametro(proyecto_completo, "n_colectores_serie", 3.0)
    n = proyecto_completo.colector.banco.n_serie
    assert n == 3
    assert isinstance(n, int)


def test_valor_invalido_propaga_valueerror(proyecto_completo):
    """n_paralelo = 0 dispara el ValueError del __post_init__ de BancoColectores."""
    with pytest.raises(ValueError, match="BANCO_N_PARALELO_NO_POSITIVO"):
        aplicar_parametro(proyecto_completo, "n_colectores_paralelo", 0.0)


def test_forzante_no_muta_y_devuelve_override(proyecto_completo):
    """HR_camara es forzante: no muta el proyecto, devuelve el override."""
    antes = copy.deepcopy(proyecto_completo)
    ret = aplicar_parametro(proyecto_completo, "HR_camara", 0.4)
    assert ret == {"forzante": "HR_camara", "valor_si": 0.4}
    # El proyecto no cambió.
    assert proyecto_completo.camara.flujo.caudal_masico_kg_s == pytest.approx(
        antes.camara.flujo.caudal_masico_kg_s
    )


def test_forzante_t_amb_override(proyecto_completo):
    ret = aplicar_parametro(proyecto_completo, "T_amb", 303.15)
    assert ret == {"forzante": "T_amb", "valor_si": 303.15}


def test_contenedor_none_da_error_claro():
    """Aplicar un parámetro de colector a un proyecto CAJA (colector None)."""
    p = Proyecto(
        meta=Meta(nombre="caja", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.CAJA,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.camara = Camara()
    with pytest.raises(ValueError, match="BARRIDO_CONTENEDOR_NONE"):
        aplicar_parametro(p, "largo_colector", 2.0)


def test_parametro_desconocido_da_keyerror(proyecto_completo):
    with pytest.raises(KeyError, match="BARRIDO_PARAMETRO_DESCONOCIDO"):
        aplicar_parametro(proyecto_completo, "no_existe", 1.0)


def test_aplicar_sobre_clon_no_toca_original(proyecto_completo):
    """deepcopy + aplicar no contamina el proyecto base (patrón del loop)."""
    clon = copy.deepcopy(proyecto_completo)
    aplicar_parametro(clon, "caudal_masico", 0.123)
    assert clon.camara.flujo.caudal_masico_kg_s == pytest.approx(0.123)
    assert proyecto_completo.camara.flujo.caudal_masico_kg_s == pytest.approx(0.10)


# ===========================================================================
# correr_barrido — modo Constantes (etapa 5)
# ===========================================================================


def test_correr_barrido_constantes_3_puntos(proyecto_completo):
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.02, 0.04, 0.06),
        modo="constantes",
        nombre="caudal",
        condiciones_constantes=_COND_CONST,
    )
    res = correr_barrido(proyecto_completo, cfg)
    assert len(res.puntos) == 3
    assert res.t_ejecucion_s >= 0.0
    assert res.creado_en  # ISO no vacío
    for pt, esperado in zip(res.puntos, (0.02, 0.04, 0.06)):
        assert pt.valor_si == pytest.approx(esperado)
        assert pt.error is None
        assert pt.convergio is True
        # Los 6 KPIs fijos de Constantes están presentes como claves.
        assert "t_secado_h" in pt.kpis
        assert "eta_termica_colector" in pt.kpis


def test_callback_llamado_n_veces(proyecto_completo):
    llamadas = []
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.02, 0.04),
        modo="constantes",
        nombre="cb",
        condiciones_constantes=_COND_CONST,
    )
    correr_barrido(
        proyecto_completo,
        cfg,
        callback_progreso=lambda i, n, v: llamadas.append((i, n)),
    )
    assert llamadas == [(1, 2), (2, 2)]


def test_correr_barrido_no_muta_proyecto_base(proyecto_completo):
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.02, 0.09),
        modo="constantes",
        nombre="nomut",
        condiciones_constantes=_COND_CONST,
    )
    correr_barrido(proyecto_completo, cfg)
    assert proyecto_completo.camara.flujo.caudal_masico_kg_s == pytest.approx(0.10)


def test_punto_invalido_no_aborta_barrido(proyecto_completo):
    """Un valor inválido (n_paralelo=0) marca el punto con error; los demás corren."""
    cfg = BarridoConfig(
        parametro_id="n_colectores_paralelo",
        valores_si=(1.0, 0.0, 2.0),
        modo="constantes",
        nombre="invalido",
        condiciones_constantes=_COND_CONST,
    )
    res = correr_barrido(proyecto_completo, cfg)
    assert len(res.puntos) == 3
    assert res.puntos[0].error is None
    assert res.puntos[1].error is not None
    assert "BANCO_N_PARALELO_NO_POSITIVO" in res.puntos[1].error
    assert res.puntos[1].convergio is False
    assert all(v is None for v in res.puntos[1].kpis.values())
    assert res.puntos[2].error is None


def test_forzante_constantes_no_muta_base(proyecto_completo):
    """Barrido de HR_camara (forzante): corre y no toca el proyecto base."""
    cfg = BarridoConfig(
        parametro_id="HR_camara",
        valores_si=(0.2, 0.5),
        modo="constantes",
        nombre="hr",
        condiciones_constantes=_COND_CONST,
    )
    res = correr_barrido(proyecto_completo, cfg)
    assert len(res.puntos) == 2
    assert all(pt.error is None for pt in res.puntos)
    # El dict de condiciones original no fue mutado.
    assert _COND_CONST["HR_camara"] == pytest.approx(0.20)


def test_kpis_extra_se_incluyen(proyecto_completo):
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.03,),
        modo="constantes",
        nombre="extra",
        kpis_extra=("energia_auxiliar_MJ",),
        condiciones_constantes=_COND_CONST,
    )
    res = correr_barrido(proyecto_completo, cfg)
    assert "energia_auxiliar_MJ" in res.puntos[0].kpis


# ===========================================================================
# correr_barrido — modo Transitorio (etapa 6)
# ===========================================================================


def _forzantes_dia_sintetico(n_horas: int = 24):
    horas = np.linspace(0.0, float(n_horas), n_horas + 1)
    T_amb = 290.0 + 8.0 * np.sin(2 * np.pi * (horas - 6) / 24)
    T_sal_col = T_amb + np.maximum(0.0, 25.0 * np.sin(np.pi * np.clip((horas - 6) / 12, 0, 1)))
    I_g = np.maximum(0.0, 900.0 * np.sin(np.pi * np.clip((horas - 6) / 12, 0, 1)))
    omega = humedad_absoluta(0.4, 295.0)
    return armar_forzantes_aire(
        modo="diario",
        T_salida_colector_K=T_sal_col,
        omega_ambiente=np.full(n_horas + 1, omega),
        m_dot_aire_seco_kg_s=0.030,
        T_amb_K=T_amb,
        v_viento_ms=np.full(n_horas + 1, 2.0),
        I_g_W_m2=I_g,
    )


@pytest.fixture
def proyecto_td() -> Proyecto:
    """ARMARIO con cámara en modo termodinámico (requerido por el transitorio)."""
    p = Proyecto(
        meta=Meta(nombre="TD", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.emplazamiento = Emplazamiento(latitud_deg=-24.7, longitud_deg=-65.4)
    p.colector = Colector()
    p.camara = Camara(
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=5.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
    )
    return p


def test_correr_barrido_transitorio(proyecto_td):
    cfg = BarridoConfig(
        parametro_id="caudal_masico",
        valores_si=(0.02, 0.03, 0.04),
        modo="transitorio",
        nombre="caudal_tr",
        forzantes_base=_forzantes_dia_sintetico(),
        n_dias=1,
    )
    res = correr_barrido(proyecto_td, cfg)
    assert len(res.puntos) == 3
    assert all(pt.error is None for pt in res.puntos)
    # t_secado_h es KPI fijo válido en transitorio.
    assert all("t_secado_h" in pt.kpis for pt in res.puntos)
    # El proyecto base no se mutó.
    assert proyecto_td.camara.flujo.caudal_masico_kg_s == pytest.approx(0.030)


# ===========================================================================
# correr_barrido — modo Anual (etapa 7)
# ===========================================================================


def _clima_sintetico() -> pd.DataFrame:
    """Clima sintético anual mínimo (ciclo estacional + diurno)."""
    ts = pd.date_range("2020-01-01", periods=8784, freq="1h", tz="UTC")
    dia = np.array([t.timetuple().tm_yday for t in ts], dtype=float)
    hora = np.array([t.hour for t in ts], dtype=float)
    T_amb_K = (
        293.15
        + 8.0 * np.sin(2 * np.pi * (dia - 30) / 365)
        + 5.0 * np.sin(2 * np.pi * (hora - 6) / 24)
    )
    factor_dia = np.maximum(0.0, np.sin(np.pi * (hora - 6) / 12))
    GHI = 900.0 * factor_dia * (0.7 + 0.3 * np.sin(2 * np.pi * (dia - 30) / 365))
    return pd.DataFrame(
        {
            "T_amb_K": T_amb_K,
            "GHI_Wm2": GHI,
            "DNI_Wm2": GHI * 0.7,
            "DHI_Wm2": GHI * 0.2,
            "WS_ms": np.full(len(ts), 2.5),
            "HR": 60.0 + 15.0 * np.sin(2 * np.pi * (hora - 4) / 24),
        },
        index=ts,
    )


@pytest.fixture
def proyecto_anual() -> Proyecto:
    """ARMARIO ANUAL con clima sintético y operación anual configurada."""
    p = Proyecto(
        meta=Meta(nombre="Anual", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.ANUAL,
        ),
    )
    p.emplazamiento = Emplazamiento(latitud_deg=-24.7, longitud_deg=-65.4)
    p.clima = Clima(datos=_clima_sintetico(), anio=2020)
    p.colector = Colector()
    p.camara = Camara(
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.05),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
        operacion_anual=OperacionAnualConfig(batches_por_mes=4),
    )
    return p


def test_correr_barrido_anual(proyecto_anual):
    cfg = BarridoConfig(
        parametro_id="masa_producto",
        valores_si=(8.0, 12.0),
        modo="anual",
        nombre="masa_anual",
        kpis_extra=("kg_secados_anual", "eta_total_anual_media"),
    )
    res = correr_barrido(proyecto_anual, cfg)
    assert len(res.puntos) == 2
    assert all(pt.error is None for pt in res.puntos)
    for pt in res.puntos:
        assert pt.kpis.get("kg_secados_anual") is not None
        assert pt.kpis.get("eta_total_anual_media") is not None
    # El clima se compartió por referencia, no se duplicó ni perdió.
    assert proyecto_anual.clima is not None
    assert proyecto_anual.camara.carga_producto.masa_total_kg == pytest.approx(10.0)
