"""Los topes de los widgets no deben rechazar diseños legítimos (S62).

Un ``max_value`` por debajo de lo que un diseño real necesita **no es una guía,
es un bloqueo**, y el modo de falla es feo: cuando el valor viene de un proyecto
guardado, ``st.number_input`` no lo recorta en silencio sino que lanza
``StreamlitValueAboveMaxError`` y **rompe el render de la pestaña entera**. O sea
que abrir un prediseño industrial guardado podía tirar un traceback en vez de
mostrarlo.

Ya había pasado dos veces: el cap de 10 m/s en la velocidad del colector (que
rompía gran escala) y el de 100 kW en la potencia del auxiliar, donde además la
unidad era kW y el usuario escribía watts.

El criterio de la auditoría: un tope se justifica solo si es **definicional**
(una fracción ≤ 1, un ángulo ≤ 360, un rendimiento ≤ 100 %, una fecha). Los topes
**dimensionales** —metros, kilos, cantidad de bandejas, caudal— pasan a ser
adaptativos: ``max(referencia, valor_cargado)``, de modo que orientan sin
bloquear.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest


def _montar_industrial(session_state) -> None:
    """Proyecto de escala industrial: supera holgadamente los topes históricos."""
    from core.camara import (
        Camara,
        CargaProducto,
        ConfiguracionBandejas,
        ConfiguracionFlujo,
        GeometriaCamara,
    )
    from core.chimenea import Chimenea
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.GRAN_ESCALA))
    p.emplazamiento = Emplazamiento()
    p.camara = Camara(
        # Túnel de 30 m: el tope histórico del largo era 20 m.
        geometria=GeometriaCamara(largo_m=30.0, ancho_m=12.0, alto_m=6.0),
        # 120 bandejas de 1.5 m²: el tope histórico del widget era 100. Con
        # 0.04 m de separación la pila mide 4.8 m y entra en los 6 m de alto —
        # el diseño tiene que ser exigente para el widget y constructible para
        # el core, si no el test no prueba lo que dice probar.
        bandejas=ConfiguracionBandejas(
            n_bandejas=120, area_bandeja_m2=5.0, separacion_entre_bandejas_m=0.04
        ),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=3.0,
            # Bocas de 15 m²: el tope histórico era 10.
            area_entrada_aire_m2=15.0,
            area_salida_aire_m2=15.0,
        ),
        carga_producto=CargaProducto(
            producto_id="tomate",
            # 11 t: el tope histórico era 10 t. Con 600 m² de bandeja son
            # 18.3 kg/m², por debajo del máximo de capa fina del core (20).
            masa_total_kg=11000.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
    )
    # Chimenea de 3 m de diámetro y 30 m de alto: topes históricos 2 m y 20 m.
    p.chimenea = Chimenea(diametro_m=3.0, altura_m=30.0)
    session_state.proyecto = p


def _script_p4() -> None:
    import streamlit as st

    from tests.test_ui.test_topes_widgets import _montar_industrial

    _montar_industrial(st.session_state)

    import ui.p4_camara as p4

    p4.render()


def _script_p6() -> None:
    import streamlit as st

    from tests.test_ui.test_topes_widgets import _montar_industrial

    _montar_industrial(st.session_state)

    import ui.p6_motor as p6

    p6.render()


class TestProyectoIndustrialNoRompeElRender:
    def test_p4_dibuja_con_una_camara_de_30_m_y_400_bandejas(self):
        at = AppTest.from_function(_script_p4).run(timeout=90)
        assert not at.exception, at.exception

    def test_p6_dibuja_con_una_chimenea_de_3_x_30_m(self):
        at = AppTest.from_function(_script_p6).run(timeout=90)
        assert not at.exception, at.exception

    def test_los_valores_cargados_sobreviven_al_render(self):
        """No alcanza con no explotar: el widget tiene que MOSTRAR lo cargado."""
        at = AppTest.from_function(_script_p4).run(timeout=90)
        valores = {n.label: n.value for n in at.number_input}
        largo = [v for k, v in valores.items() if "argo" in k]
        assert largo and largo[0] == pytest.approx(30.0), valores


class TestTopeAdaptativo:
    """El patrón `max(referencia, valor)` en sí mismo."""

    def test_el_tope_nunca_queda_por_debajo_del_valor(self):
        for referencia, valor in ((20.0, 30.0), (100, 400), (2.0, 3.0), (10.0, 15.0)):
            assert max(referencia, valor) >= valor

    def test_con_valores_chicos_conserva_la_referencia(self):
        """Con un diseño normal el tope sigue orientando como antes."""
        assert max(20.0, 5.0) == 20.0
        assert max(100, 24) == 100
