"""
Tests de la superficie de respuesta del colector (calculos/superficie_colector.py).

El test que importa es :class:`TestExactitud`: la superficie debe reproducir el
solver que muestrea dentro de una tolerancia muy por debajo del error del propio
modelo contra medición real (RMSE 0.9 °C contra el prototipo de 10 m del INENCO,
mejora 38 fase 2). Si ese test empieza a fallar, la superficie dejó de ser un
sustituto legítimo y hay que revisar la grilla, no aflojar el umbral.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.superficie_colector import (
    SuperficieColector,
    _eje_lineal,
    _eje_POA,
    _rellenar_fallas,
    construir_superficie,
)
from core.colector import BancoColectores, Colector, ColectorUnidad
from core.proyecto import Proyecto


def _proyecto_con_colector(velocidad_ms: float = 1.5) -> Proyecto:
    proy = Proyecto()
    proy.colector = Colector(
        unidad=ColectorUnidad(
            largo_m=2.0,
            ancho_m=1.0,
            espaciado_m=0.05,
            velocidad_diseno_ms=velocidad_ms,
        ),
        banco=BancoColectores(n_serie=1, n_paralelo=4),
    )
    return proy


def _solver(proyecto, POA: float, T_amb: float, v: float, P_Pa: float = 101325.0) -> float:
    """ΔT del solver real, con el mismo contrato que usa la superficie."""
    from calculos.balance_global import _correr_colector

    _s, T_sal = _correr_colector(
        proyecto,
        T_amb_K=T_amb,
        I_g_W_m2=POA,
        v_viento_ms=v,
        T_entrada_K=T_amb,
        P_amb_Pa=P_Pa,
    )
    return max(0.0, T_sal - T_amb)


# ---------------------------------------------------------------------------
# Ejes
# ---------------------------------------------------------------------------


class TestEjes:
    def test_eje_POA_arranca_en_cero_y_llega_al_max(self):
        eje = _eje_POA(1200.0)
        assert eje[0] == 0.0
        assert eje[-1] == pytest.approx(1200.0)
        assert np.all(np.diff(eje) > 0)

    def test_eje_POA_mas_denso_cerca_de_cero(self):
        """La curvatura de la respuesta está en el arranque del colector."""
        eje = _eje_POA(1000.0)
        saltos = np.diff(eje)
        assert saltos[0] < saltos[-1]

    def test_eje_lineal_respeta_span_minimo(self):
        """Un clima con T constante no puede degenerar el eje."""
        eje = _eje_lineal(300.0, 300.0, 5, span_min=1.0)
        assert len(eje) == 5
        assert np.all(np.diff(eje) > 0)
        assert eje[-1] - eje[0] == pytest.approx(1.0)

    def test_eje_lineal_ordena_argumentos_invertidos(self):
        eje = _eje_lineal(320.0, 280.0, 4, span_min=1.0)
        assert eje[0] == pytest.approx(280.0)
        assert eje[-1] == pytest.approx(320.0)


# ---------------------------------------------------------------------------
# Validaciones de la dataclass
# ---------------------------------------------------------------------------


class TestValidaciones:
    def _superficie_minima(self, **over):
        kw = dict(
            POA_nodos=np.array([0.0, 500.0, 1000.0]),
            T_amb_nodos=np.array([280.0, 300.0]),
            v_viento_nodos=np.array([1.0, 5.0]),
            delta_T_K=np.zeros((3, 2, 2)),
        )
        kw.update(over)
        return SuperficieColector(**kw)

    def test_SUPCOL_EJE_INSUFICIENTE(self):
        with pytest.raises(ValueError, match="SUPCOL_EJE_INSUFICIENTE"):
            self._superficie_minima(v_viento_nodos=np.array([1.0]), delta_T_K=np.zeros((3, 2, 1)))

    def test_SUPCOL_EJE_NO_CRECIENTE(self):
        with pytest.raises(ValueError, match="SUPCOL_EJE_NO_CRECIENTE"):
            self._superficie_minima(T_amb_nodos=np.array([300.0, 280.0]))

    def test_SUPCOL_FORMA_INVALIDA(self):
        with pytest.raises(ValueError, match="SUPCOL_FORMA_INVALIDA"):
            self._superficie_minima(delta_T_K=np.zeros((2, 2, 2)))

    def test_SUPCOL_SIN_COLECTOR(self):
        with pytest.raises(ValueError, match="SUPCOL_SIN_COLECTOR"):
            construir_superficie(Proyecto())


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------


class TestEvaluar:
    def _superficie(self):
        # ΔT = POA/100, independiente de T y v: interpolación exacta esperada.
        POA = np.array([0.0, 500.0, 1000.0])
        dT = np.zeros((3, 2, 2))
        for i, p in enumerate(POA):
            dT[i, :, :] = p / 100.0
        return SuperficieColector(
            POA_nodos=POA,
            T_amb_nodos=np.array([280.0, 300.0]),
            v_viento_nodos=np.array([1.0, 5.0]),
            delta_T_K=dT,
        )

    def test_reproduce_los_nodos(self):
        s = self._superficie()
        assert float(s.evaluar(500.0, 290.0, 3.0)) == pytest.approx(5.0)

    def test_interpola_linealmente(self):
        s = self._superficie()
        assert float(s.evaluar(250.0, 290.0, 3.0)) == pytest.approx(2.5)

    def test_vectorizado(self):
        s = self._superficie()
        dT = s.evaluar(
            np.array([0.0, 500.0, 1000.0]),
            np.array([285.0, 290.0, 295.0]),
            np.array([2.0, 3.0, 4.0]),
        )
        assert dT.shape == (3,)
        assert dT == pytest.approx([0.0, 5.0, 10.0])

    def test_recorta_fuera_de_grilla_sin_extrapolar(self):
        """Por encima del POA muestreado se sostiene el borde, no se dispara."""
        s = self._superficie()
        assert float(s.evaluar(5000.0, 290.0, 3.0)) == pytest.approx(10.0)

    def test_delta_T_nunca_negativo(self):
        """El colector no enfría por debajo del ambiente (mismo recorte que el lazo)."""
        POA = np.array([0.0, 500.0])
        dT = np.full((2, 2, 2), -3.0)
        s = SuperficieColector(
            POA_nodos=POA,
            T_amb_nodos=np.array([280.0, 300.0]),
            v_viento_nodos=np.array([1.0, 5.0]),
            delta_T_K=dT,
        )
        assert float(s.evaluar(250.0, 290.0, 3.0)) == 0.0

    def test_T_salida_suma_el_ambiente(self):
        s = self._superficie()
        assert float(s.T_salida_K(500.0, 300.0, 3.0)) == pytest.approx(305.0)


# ---------------------------------------------------------------------------
# Relleno de fallas del solver
# ---------------------------------------------------------------------------


class TestRellenoDeFallas:
    def test_interpola_el_hueco_sobre_el_eje_POA(self):
        dT = np.zeros((3, 1, 1))
        dT[0, 0, 0], dT[2, 0, 0] = 0.0, 20.0
        ok = np.array([[[True]], [[False]], [[True]]])
        out = _rellenar_fallas(dT, ok)
        assert out[1, 0, 0] == pytest.approx(10.0)

    def test_columna_entera_fallada_queda_en_cero(self):
        dT = np.full((3, 1, 1), 7.0)
        ok = np.zeros((3, 1, 1), dtype=bool)
        out = _rellenar_fallas(dT, ok)
        assert np.all(out == 0.0)

    def test_no_toca_columnas_sanas(self):
        dT = np.array([[[1.0]], [[2.0]], [[3.0]]])
        ok = np.ones((3, 1, 1), dtype=bool)
        assert _rellenar_fallas(dT, ok) == pytest.approx(dT)


# ---------------------------------------------------------------------------
# Exactitud contra el solver — el test que justifica el módulo
# ---------------------------------------------------------------------------


class TestExactitud:
    """La superficie debe ser indistinguible del solver a efectos de prediseño."""

    def test_error_contra_el_solver_bajo_umbral(self):
        proy = _proyecto_con_colector()
        POA_serie = np.linspace(0.0, 1100.0, 40)
        T_serie = np.linspace(275.0, 315.0, 40)
        v_serie = np.linspace(0.5, 9.0, 40)
        sup = construir_superficie(
            proy,
            POA_W_m2_serie=POA_serie,
            T_amb_K_serie=T_serie,
            v_viento_ms_serie=v_serie,
        )

        rng = np.random.default_rng(20570)
        errores = []
        for _ in range(40):
            POA = float(rng.uniform(0.0, 1100.0))
            T = float(rng.uniform(276.0, 314.0))
            v = float(rng.uniform(0.6, 8.5))
            try:
                real = _solver(proy, POA, T, v)
            except Exception:
                continue
            errores.append(abs(float(sup.evaluar(POA, T, v)) - real))

        assert len(errores) >= 30, "muy pocos puntos de comparación válidos"
        err = np.array(errores)
        # Umbral con margen frente al RMSE de 0.9 °C del modelo contra medición
        # real: la interpolación debe ser un orden más chica que ese error.
        assert np.percentile(err, 95) < 0.35, f"p95={np.percentile(err, 95):.3f} K"
        assert err.max() < 0.6, f"max={err.max():.3f} K"

    def test_es_monotona_creciente_en_POA(self):
        proy = _proyecto_con_colector()
        sup = construir_superficie(proy, POA_W_m2_serie=np.array([0.0, 1000.0]))
        dT = sup.evaluar(np.linspace(0.0, 1000.0, 25), 295.0, 3.0)
        assert np.all(np.diff(dT) >= -1e-9)

    def test_sin_irradiancia_no_hay_aporte(self):
        proy = _proyecto_con_colector()
        sup = construir_superficie(proy, POA_W_m2_serie=np.array([0.0, 1000.0]))
        assert float(sup.evaluar(0.0, 295.0, 3.0)) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Metadatos del muestreo
# ---------------------------------------------------------------------------


class TestMuestreo:
    def test_cuenta_los_solves(self):
        proy = _proyecto_con_colector()
        sup = construir_superficie(proy, n_nodos_T=2, n_nodos_v=2)
        assert sup.n_solves == len(sup.POA_nodos) * 2 * 2

    def test_restaura_la_velocidad_de_diseno(self):
        """El muestreo muta velocidad_diseno_ms; debe dejarla como estaba."""
        proy = _proyecto_con_colector(velocidad_ms=1.5)
        construir_superficie(proy, m_dot_sistema_kg_s=0.05, n_nodos_T=2, n_nodos_v=2)
        assert proy.colector.unidad.velocidad_diseno_ms == pytest.approx(1.5)

    def test_registra_el_caudal_del_sistema(self):
        proy = _proyecto_con_colector()
        sup = construir_superficie(proy, m_dot_sistema_kg_s=0.05, n_nodos_T=2, n_nodos_v=2)
        assert sup.m_dot_sistema_kg_s == pytest.approx(0.05)

    def test_sin_caudal_no_registra_ninguno(self):
        proy = _proyecto_con_colector()
        sup = construir_superficie(proy, n_nodos_T=2, n_nodos_v=2)
        assert sup.m_dot_sistema_kg_s is None
