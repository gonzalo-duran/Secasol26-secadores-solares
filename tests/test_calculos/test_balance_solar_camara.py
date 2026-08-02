"""El aporte solar de una cámara translúcida entra al balance energético (S62).

``energia_solar_util_MJ`` se calculaba **solo** como
``ṁ·cp·(T_salida_colector − T_amb)``, que sin colector da cero por construcción.
Una caja translúcida —donde la radiación transmitida es la única fuente de
energía del producto— se reportaba con **fracción solar 0 %** y un ``COP_secado``
mayor que 1 teniendo a la resistencia eléctrica como única entrada contabilizada,
que no significa nada físicamente.

La energía ya estaba calculada por el motor (``Q_rad`` al producto y
``Q_rad_aire`` a las superficies internas); lo que faltaba era sumarla.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.balance_global import (
    calcular_todo,
    calcular_todo_transitorio,
    energia_solar_camara_MJ,
)
from calculos.psicrometria import humedad_absoluta
from core.camara import ForzantesAire

from .test_conveccion_natural_cajon import _proyecto


class TestEnergiaSolarCamara:
    """El helper puro."""

    def test_suma_producto_y_aire(self):
        class _Res:
            energia_rad_total_J = 5.0e6
            energia_rad_aire_total_J = 3.0e6

        assert energia_solar_camara_MJ(_Res()) == pytest.approx(8.0)

    def test_sin_camara_es_cero(self):
        assert energia_solar_camara_MJ(None) == 0.0

    def test_camara_opaca_no_aporta(self):
        """Sin caras translúcidas los dos términos son cero: back-compat."""

        class _Res:
            energia_rad_total_J = 0.0
            energia_rad_aire_total_J = 0.0

        assert energia_solar_camara_MJ(_Res()) == 0.0


def _forzantes(horas: int = 24):
    t = np.arange(horas, dtype=float) * 3600.0
    hora = np.arange(horas) % 24
    T_amb = np.full(horas, 293.15)
    I_g = np.where((hora >= 8) & (hora <= 18), 900.0, 0.0)
    return ForzantesAire(
        t_s=t,
        T_ent_K=T_amb.copy(),  # CAJA: el aire entra a la ambiente
        omega_ent=np.full(horas, humedad_absoluta(0.5, 293.15)),
        m_dot_aire_seco_kg_s=np.full(horas, 0.02),
        T_amb_K=T_amb,
        v_viento_ms=np.full(horas, 2.0),
        I_g_W_m2=I_g,
        I_g_POA_W_m2=I_g,
    )


class TestCajaTranslucidaEnElBalance:
    """El caso que lo destapó: caja sin colector, con sol entrando por el vidriado."""

    def _res(self):
        return calcular_todo_transitorio(_proyecto(A_boca=0.05), forzantes_base=_forzantes())

    def test_el_sol_deja_de_reportarse_como_cero(self):
        res = self._res()
        assert res.camara is not None
        assert res.energia_solar_util_MJ > 0.0

    def test_coincide_con_la_radiacion_que_integro_el_motor(self):
        """Sin colector, TODO el aporte solar es el de la cámara."""
        res = self._res()
        assert res.energia_solar_util_MJ == pytest.approx(
            energia_solar_camara_MJ(res.camara), rel=1e-9
        )

    def test_la_fraccion_solar_deja_de_ser_nula(self):
        res = self._res()
        assert res.fraccion_solar is not None
        assert res.fraccion_solar > 0.5, res.fraccion_solar

    def test_el_COP_no_supera_1_con_la_energia_bien_contada(self):
        """Un COP > 1 con la sola entrada eléctrica era la señal del problema.

        Contando el sol, el denominador incluye toda la energía que entra y el
        cociente vuelve a ser interpretable.
        """
        res = self._res()
        assert res.COP_secado is not None
        assert res.COP_secado < 1.0, res.COP_secado

    def test_el_total_es_la_suma_de_sus_partes(self):
        res = self._res()
        assert res.energia_total_MJ == pytest.approx(
            res.energia_solar_util_MJ + res.energia_auxiliar_MJ + res.energia_motor_MJ
        )


class TestAreaTranslucida:
    """El área captadora de un secador directo, análoga a la del colector."""

    def test_suma_las_caras_activas(self):
        from calculos.simulacion_anual import _area_translucida_m2

        proyecto = _proyecto(A_boca=0.05)
        # La fixture tiene techo translúcido en una cámara de 1.2 x 0.8 x 1.0.
        assert _area_translucida_m2(proyecto) == pytest.approx(1.2 * 0.8)

    def test_camara_opaca_da_cero(self):
        from calculos.simulacion_anual import _area_translucida_m2
        from core.camara import ConstruccionCamara

        proyecto = _proyecto(A_boca=0.05)
        proyecto.camara.construccion = ConstruccionCamara()
        assert _area_translucida_m2(proyecto) == 0.0

    def test_sin_camara_da_cero(self):
        from calculos.simulacion_anual import _area_translucida_m2

        proyecto = _proyecto(A_boca=0.05)
        proyecto.camara = None
        assert _area_translucida_m2(proyecto) == 0.0


class TestModoConstantes:
    def test_tambien_cuenta_el_sol_de_la_camara(self):
        res = calcular_todo(
            _proyecto(A_boca=0.05),
            T_amb_K=293.15,
            I_g_W_m2=800.0,
            v_viento_ms=2.0,
            T_entrada_K=293.15,
            HR_camara=0.5,
        )
        if res.camara is None or res.energia_solar_util_MJ is None:
            pytest.skip("el ciclo no cerró en modo constantes con esta configuración")
        assert res.energia_solar_util_MJ > 0.0
