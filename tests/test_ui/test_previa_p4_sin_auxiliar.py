"""La previa de P4 avisa que sus números no incluyen el auxiliar (S62).

P4 resuelve la cámara con el aire **tal como llega antes de P5**; el aporte del
calentamiento auxiliar entra recién en el balance de P7. Es una división
deliberada —así está declarada en el registro de vigencia, donde el horizonte no
depende del auxiliar— pero los dos resultados se rotulaban igual, "tiempo de
secado", y conviven en el mismo PDF: en una corrida real del usuario, 34.6 h en
la sección de cámara y 16.8 h en la de resultados globales, sin nada que
explicara la diferencia.

Se arregla con un rótulo, no con física.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _montar(session_state, con_auxiliar: bool) -> None:
    from core.auxiliar import Auxiliar, ModoOperacionAuxiliar
    from core.camara import Camara, CargaProducto, ConstruccionCamara
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.CAJA))
    p.emplazamiento = Emplazamiento()
    p.colector = None
    p.camara = Camara(
        construccion=ConstruccionCamara(cubierta_translucida_id="policarbonato_alveolar"),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
    )
    if con_auxiliar:
        p.auxiliar = Auxiliar(
            potencia_nominal_W=1000.0,
            modo_operacion=ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
            disponible_nocturno=True,
        )
    session_state.proyecto = p


def _script_con_aux() -> None:
    import streamlit as st

    from tests.test_ui.test_previa_p4_sin_auxiliar import _montar

    _montar(st.session_state, con_auxiliar=True)

    import ui.p4_camara as p4

    p4.render()


def _script_sin_aux() -> None:
    import streamlit as st

    from tests.test_ui.test_previa_p4_sin_auxiliar import _montar

    _montar(st.session_state, con_auxiliar=False)

    import ui.p4_camara as p4

    p4.render()


class TestClaveDeTraduccion:
    """El aviso tiene que existir en los tres idiomas y decir lo que importa."""

    def test_existe_y_menciona_la_pestana_7(self):
        from ui.componentes.traducciones import cargar_diccionario

        for lang in ("es", "en", "pt"):
            texto = cargar_diccionario(lang)["p4.resultados_td.aviso_sin_auxiliar"]
            assert texto.strip(), lang
            assert "7" in texto, (lang, texto)

    def test_el_aviso_del_pdf_existe_en_la_seccion_de_camara(self):
        """Y no en la de colector, que es donde cayó al insertarlo por primera vez."""
        from ui.componentes.traducciones import cargar_diccionario

        for lang in ("es", "en", "pt"):
            d = cargar_diccionario(lang)
            assert "reporte.camara.res_sin_auxiliar" in d, lang
            assert "reporte.colector.res_sin_auxiliar" not in d, lang


class TestRenderP4:
    def test_render_no_explota_con_auxiliar(self):
        at = AppTest.from_function(_script_con_aux).run(timeout=90)
        assert not at.exception, at.exception

    def test_render_no_explota_sin_auxiliar(self):
        at = AppTest.from_function(_script_sin_aux).run(timeout=90)
        assert not at.exception, at.exception
