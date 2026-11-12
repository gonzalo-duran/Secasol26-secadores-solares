"""Carta psicrométrica en modo Constantes sobre un proyecto real (S67).

Cubre los tres defectos que hicieron apagar la carta en producción (hotfix
1.4.1), con el armario indirecto forzado de referencia:

- el punto "Ambiente" quedaba **sobresaturado** (la HR del slider se evaluaba a
  la temperatura de entrada a la cámara, no a la ambiente);
- el eje de humedad se escalaba a la curva de saturación y aplastaba el proceso;
- el instante representativo podía caer en el arranque del producto.

Y deja escrito lo que el diagnóstico confirmó: el balance de cámara **cierra**.
El apartamiento de la isentálpica es la pérdida de pared menos la entalpía del
agua líquida que se evapora.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from calculos.balance_global import calcular_todo, presion_representativa_proyecto
from calculos.carta_psicrometrica import estados_proceso
from calculos.psicrometria import humedad_absoluta
from ui.componentes.carga_proyecto import cargar_proyecto_completo
from ui.componentes.carta_psicrometrica import _rango_omega_g_kg, fig_carta_psicrometrica

_JSON = (
    Path(__file__).parents[1]
    / "armario indirecto forzado"
    / "nuevo_proyecto_prediseno_completo_2026-07-29_19-16.json"
)
_T_AMB_K = 298.15
_CP_AGUA_J_KG_K = 4186.0


def _corrida(I_g: float, HR: float, *, ambiente: bool = True):
    proyecto, _ = cargar_proyecto_completo(json.loads(_JSON.read_text()))
    res = calcular_todo(
        proyecto,
        T_amb_K=_T_AMB_K,
        I_g_W_m2=I_g,
        v_viento_ms=2.0,
        T_entrada_K=_T_AMB_K,
        HR_camara=HR,
        HR_referida_a_ambiente=ambiente,
    )
    assert not res.errores
    P_Pa, _ = presion_representativa_proyecto(proyecto)
    return proyecto, res, P_Pa


@pytest.fixture(scope="module")
def base():
    return _corrida(800.0, 0.50)


def test_omega_del_proceso_es_la_del_ambiente(base):
    _, res, P_Pa = base
    assert res.omega_entrada_kg_kg == pytest.approx(humedad_absoluta(0.50, _T_AMB_K, P_Pa))


def test_ambiente_nunca_sobresaturado(base):
    _, res, P_Pa = base
    estados = estados_proceso(res, P_Pa=P_Pa)["estados"]
    assert estados[0].nombre == "Ambiente"
    assert estados[0].HR == pytest.approx(0.50, abs=1e-6)
    # El calentamiento sensible baja la HR: a la cámara llega aire mucho más seco.
    entrada = next(e for e in estados if e.nombre == "Entrada cámara")
    assert entrada.HR < 0.15


def test_modo_compatibilidad_conserva_la_semantica_vieja():
    """Sin el flag, HR_camara sigue siendo la HR a la T de entrada a la cámara."""
    _, res, P_Pa = _corrida(800.0, 0.20, ambiente=False)
    assert res.omega_entrada_kg_kg == pytest.approx(
        humedad_absoluta(0.20, res.T_entrada_camara_K, P_Pa)
    )


def test_balance_de_entalpia_del_aire_cierra(base):
    """ṁ·Δh = −q_pared + ṁ_w·h_líquido(T_prod): la cámara se aparta de la
    isentálpica exactamente por la pérdida de pared, no por un error del modelo."""
    proyecto, res, P_Pa = base
    d = estados_proceso(res, P_Pa=P_Pa)
    cam = res.camara
    i = int(np.argmin(np.abs(cam.t_array_s - d["t_repr_s"])))
    entrada = next(e for e in d["estados"] if e.nombre == "Entrada cámara")
    salida = d["estados"][-1]
    m_as = proyecto.camara.flujo.caudal_masico_kg_s
    lado_aire_W = m_as * (salida.h_J_kg - entrada.h_J_kg)
    agua_W = cam.m_dot_w_kg_s[i] * _CP_AGUA_J_KG_K * (cam.T_prod_K[i] - 273.15)
    assert lado_aire_W == pytest.approx(-cam.q_pared_W[i] + agua_W, abs=1.0)
    # Cámara opaca con pérdidas: la salida cae POR DEBAJO de la isentálpica.
    assert salida.h_J_kg < entrada.h_J_kg


def test_instante_representativo_fuera_del_arranque():
    """Sol bajo + aire seco: el producto arranca sobre el bulbo húmedo y la
    evaporación máxima está en t = 0. La carta mostraba Δh > 0 en cámara opaca."""
    _, res, P_Pa = _corrida(400.0, 0.50)
    d = estados_proceso(res, P_Pa=P_Pa)
    assert int(np.nanargmax(res.camara.m_dot_w_kg_s)) == 0  # el caso es el que decimos
    assert d["t_repr_s"] > 0.0
    entrada = next(e for e in d["estados"] if e.nombre == "Entrada cámara")
    assert d["estados"][-1].h_J_kg < entrada.h_J_kg


def test_eje_de_humedad_ajustado_al_proceso(base):
    proyecto, res, P_Pa = base
    fig = fig_carta_psicrometrica(res, proyecto)
    assert fig is not None
    piso, techo = fig.layout.yaxis.range
    omegas = [e.omega_kg_kg * 1000.0 for e in estados_proceso(res, P_Pa=P_Pa)["estados"]]
    assert piso <= min(omegas) and max(omegas) <= techo
    # El tramo de cámara ocupa una fracción visible del eje (antes: < 1 %).
    assert (max(omegas) - min(omegas)) / (techo - piso) > 0.08


def test_rango_omega_incluye_la_saturacion_adiabatica():
    piso, techo = _rango_omega_g_kg([11.4, 11.4, 13.9], np.array([np.nan, 22.0, 15.0, 9.0]))
    assert techo > 22.0
    assert piso < 11.4
    # Proceso cerca del origen: el eje arranca en cero.
    assert _rango_omega_g_kg([2.0, 4.0], np.array([8.0, 3.0]))[0] == 0.0
