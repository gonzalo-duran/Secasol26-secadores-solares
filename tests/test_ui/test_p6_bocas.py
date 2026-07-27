"""Tests de las bocas de cámara en el circuito **forzado** (P6, S61).

Con ventilador las bocas no cambian el caudal —lo impone el ventilador— pero sí
la presión que tiene que entregar, y con ella la potencia eléctrica. Hasta S60
el dato no existía: ``estimar_delta_P_singulares`` estimaba entrada, salida y
difusor sobre la velocidad del **ducto**, o sea suponiendo bocas del tamaño del
ducto. Estrangular la entrada de la cámara no movía el dimensionado del motor.
"""

from __future__ import annotations

import pytest

from calculos.motor_calc import estimar_delta_P_singulares
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    GeometriaCamara,
)
from core.motor import Motor
from core.proyecto import Configuracion, Proyecto, Tipologia
from ui.p6_motor import _delta_P_bocas_forzado

P_ATM = 101325.0


def _proyecto(A_boca: float | None = 0.05, con_motor: bool = True) -> Proyecto:
    cam = Camara(
        geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.0),
        bandejas=ConfiguracionBandejas(n_bandejas=5, area_bandeja_m2=0.5),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=0.05,
            area_entrada_aire_m2=A_boca,
            area_salida_aire_m2=A_boca,
        ),
        carga_producto=CargaProducto(
            producto_id="tomate",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
    )
    return Proyecto(
        configuracion=Configuracion(tipologia=Tipologia.ARMARIO),
        camara=cam,
        motor=Motor() if con_motor else None,
    )


class TestDeltaPBocasForzado:

    def test_sin_bocas_no_toca_la_cadena_de_singulares(self):
        """Back-compat: sin áreas cargadas, P6 calcula como siempre."""
        dp, overrides = _delta_P_bocas_forzado(_proyecto(A_boca=None), 0.05, P_ATM)
        assert dp == 0.0
        assert overrides == {}

    def test_con_bocas_apaga_entrada_salida_y_difusor(self):
        """Las transiciones genéricas se apagan: ahora las calcula el área real.

        Sumar ambas contaría dos veces la misma transición.
        """
        dp, overrides = _delta_P_bocas_forzado(_proyecto(A_boca=0.05), 0.05, P_ATM)
        assert dp > 0.0
        assert overrides == {"K_entrada": 0.0, "K_salida": 0.0, "K_difusor": 0.0}

    def test_los_codos_y_el_manifold_sobreviven(self):
        """Solo se apagan las transiciones de cámara, no las del ducto."""
        _, overrides = _delta_P_bocas_forzado(_proyecto(A_boca=0.05), 0.05, P_ATM)
        sing = estimar_delta_P_singulares(
            Q_vol_m3_s=0.05, v_ducto_m_s=6.0, n_paralelo=2, P_Pa=P_ATM, **overrides
        )
        assert sing["entrada"] == 0.0
        assert sing["salida"] == 0.0
        assert sing["difusor"] == 0.0
        assert sing["codos"] > 0.0
        assert sing["manifold"] > 0.0

    def test_boca_mas_angosta_exige_mas_presion(self):
        """El efecto que antes no existía: estrangular la cámara encarece el
        ventilador."""
        dp_ancha, _ = _delta_P_bocas_forzado(_proyecto(A_boca=0.20), 0.05, P_ATM)
        dp_angosta, _ = _delta_P_bocas_forzado(_proyecto(A_boca=0.02), 0.05, P_ATM)
        assert dp_angosta > dp_ancha

    def test_escala_con_el_cuadrado_del_caudal(self):
        uno, _ = _delta_P_bocas_forzado(_proyecto(A_boca=0.05), 0.05, P_ATM)
        doble, _ = _delta_P_bocas_forzado(_proyecto(A_boca=0.05), 0.10, P_ATM)
        assert doble == pytest.approx(4.0 * uno, rel=1e-6)

    def test_tambien_aplica_sin_motor(self):
        """El helper no discrimina: la presión de bocas existe igual. Quien
        decide si hay ventilador es P6 al armar el circuito."""
        dp, _ = _delta_P_bocas_forzado(_proyecto(A_boca=0.05, con_motor=False), 0.05, P_ATM)
        assert dp > 0.0

    def test_sin_camara_no_rompe(self):
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        assert _delta_P_bocas_forzado(p, 0.05, P_ATM) == (0.0, {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
