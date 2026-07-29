"""Smoke test del render de P5 en modo RESPALDO_INDEPENDIENTE (S62).

La sección "Ventana de operación del respaldo" reemplaza a la gráfica
``T_sal_aux(t)`` cuando el auxiliar opera adentro de la cámara, y el selector de
tipo de fuente queda restringido a resistencia eléctrica. Nada de eso lo ven los
tests de helpers puros.

Los asserts miran **contenido**, no solo ``not at.exception``: un smoke que solo
comprueba que no explotó puede pasar sin haber ejercitado la rama (lección S59).

Ojo: ``AppTest.from_function`` serializa **solo** el cuerpo de la función, así que
cada script tiene que ser autocontenido.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _montar(session_state, modo_respaldo: bool) -> None:
    """Deja un proyecto con auxiliar en el modo pedido (se inlinea en el script)."""
    from core.auxiliar import Auxiliar, ModoOperacionAuxiliar
    from core.camara import Camara, CargaProducto
    from core.colector import Colector
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    modo = (
        ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE
        if modo_respaldo
        else ModoOperacionAuxiliar.SERIE_POSCOLECTOR
    )
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.emplazamiento = Emplazamiento()
    # Con colector: sin él, el modo serie no está disponible (y no debería), así
    # que un ARMARIO sin colector no sirve para probar la rama serie.
    p.colector = Colector()
    p.camara = Camara(
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        )
    )
    p.auxiliar = Auxiliar(
        potencia_nominal_W=1200.0,
        modo_operacion=modo,
        disponible_nocturno=True,
    )
    session_state.proyecto = p


def _montar_caja(session_state) -> None:
    """Secador CAJA: sin colector, así que el aire entra a T ambiente."""
    from core.auxiliar import Auxiliar, ModoOperacionAuxiliar
    from core.camara import Camara, CargaProducto, ConstruccionCamara
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.CAJA))
    p.emplazamiento = Emplazamiento()
    p.colector = None
    # El toggle "usar auxiliar" arranca según haya auxiliar en el proyecto; sin
    # esto P5 devuelve temprano y no se renderiza ningún widget que mirar.
    p.auxiliar = Auxiliar(
        potencia_nominal_W=1200.0,
        modo_operacion=ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
        disponible_nocturno=True,
    )
    p.camara = Camara(
        construccion=ConstruccionCamara(cubierta_translucida_id="policarbonato_alveolar"),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
    )
    session_state.proyecto = p


def _script_caja() -> None:
    import streamlit as st

    from tests.test_ui.test_p5_respaldo_render import _montar_caja

    _montar_caja(st.session_state)

    import ui.p5_auxiliar as p5

    p5.render()


def _script_respaldo() -> None:
    import streamlit as st

    from tests.test_ui.test_p5_respaldo_render import _montar

    _montar(st.session_state, modo_respaldo=True)

    import ui.p5_auxiliar as p5

    p5.render()


def _script_serie() -> None:
    import streamlit as st

    from tests.test_ui.test_p5_respaldo_render import _montar

    _montar(st.session_state, modo_respaldo=False)

    import ui.p5_auxiliar as p5

    p5.render()


def _textos(at) -> str:
    """Todo el texto renderizado, para buscar rótulos sin depender del widget."""
    partes = []
    for coleccion in (at.markdown, at.caption, at.info, at.subheader, at.warning, at.success):
        partes.extend(el.value for el in coleccion)
    return "\n".join(partes)


class TestRenderRespaldo:
    def test_render_no_explota(self):
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        assert not at.exception

    def test_el_tipo_de_fuente_queda_restringido_a_resistencia(self):
        """En respaldo el quemador no debe ser elegible (coacción visible en la UI)."""
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        selects = [s for s in at.selectbox if "fuente" in (s.label or "").lower()]
        assert selects, "no se encontró el selector de tipo de fuente"
        assert len(selects[0].options) == 1
        assert selects[0].disabled is True

    def test_muestra_la_ventana_de_operacion_y_no_el_delta_T(self):
        """Hay que APRETAR "Aplicar auxiliar": la sección del entregable vive
        detrás de ese botón, y sin el clic el test pasaría sin ejercitar nada
        (el rótulo del selector menciona la cámara y alcanzaría para engañarlo).
        """
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        at.button[0].click().run(timeout=60)
        assert not at.exception
        sub = [s.value for s in at.subheader]
        assert any("respaldo" in s.lower() for s in sub), sub
        # El entregable de SERIE (ΔT sobre la entrada) no debe aparecer.
        assert not any("T_sal_aux" in s for s in sub), sub


class TestSecadorCaja:
    """En una CAJA no hay colector, así que el modo serie no describe nada.

    Antes de S62 P5 lo ofrecía igual y el rechazo llegaba en P7 como error duro
    (`PROY_AUXILIAR_SERIE_SIN_COLECTOR`), abortando la corrida entera. Misma
    clase que el slider de T de entrada con rango 30–90 °C cuya ayuda pedía
    T ambiente.
    """

    def test_el_modo_queda_restringido_a_respaldo(self):
        at = AppTest.from_function(_script_caja).run(timeout=60)
        assert not at.exception
        selects = [s for s in at.selectbox if "modo" in (s.label or "").lower()]
        assert selects, "no se encontró el selector de modo"
        assert len(selects[0].options) == 1
        assert selects[0].disabled is True

    def test_la_resistencia_en_caja_llega_al_balance(self):
        """La cadena completa: elegir el auxiliar en P5 deja un proyecto que P7
        puede calcular, en vez de uno que revienta con un error de validación."""
        at = AppTest.from_function(_script_caja).run(timeout=60)
        at.button[0].click().run(timeout=60)
        assert not at.exception

        from calculos.balance_global import calcular_todo

        proyecto = at.session_state.proyecto
        assert proyecto.auxiliar is not None
        res = calcular_todo(
            proyecto,
            T_amb_K=293.15,
            I_g_W_m2=500.0,
            v_viento_ms=2.0,
            T_entrada_K=293.15,
            HR_camara=0.5,
        )
        assert not res.errores, res.errores
        assert res.camara is not None
        # La resistencia entregó calor al nodo de aire de la cámara.
        assert float(res.camara.energia_aux_total_J) > 0.0


class TestPotenciaNominal:
    """El campo de potencia debe aceptar la escala real de estos equipos.

    Estaba en kW con tope 100: escribir "5000" —pensando en watts— daba 5000 kW,
    chocaba contra el tope y el valor **no se aplicaba**, así que la corrida
    seguía con la potencia anterior sin que la pantalla de resultados lo dijera.
    Misma clase que el tope de 10 m/s de velocidad que rompía gran escala.
    """

    def _widget(self, at):
        campos = [n for n in at.number_input if "potencia" in (n.label or "").lower()]
        assert campos, [n.label for n in at.number_input]
        return campos[0]

    def test_esta_en_watts(self):
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        assert "[W]" in self._widget(at).label

    def test_no_tiene_tope_superior_arbitrario(self):
        """Streamlit representa "sin límite" como el máximo del float."""
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        w = self._widget(at)
        assert w.max is None or w.max > 1e6, f"tope artificial en {w.max}"

    def test_acepta_5000_W_y_llega_al_proyecto(self):
        at = AppTest.from_function(_script_respaldo).run(timeout=60)
        self._widget(at).set_value(5000.0).run(timeout=60)
        at.button[0].click().run(timeout=60)
        assert not at.exception
        assert at.session_state.proyecto.auxiliar.potencia_nominal_W == 5000.0


class TestRenderSerieSigueIgual:
    def test_el_quemador_sigue_disponible_en_serie(self):
        at = AppTest.from_function(_script_serie).run(timeout=60)
        assert not at.exception
        selects = [s for s in at.selectbox if "fuente" in (s.label or "").lower()]
        assert selects, "no se encontró el selector de tipo de fuente"
        assert len(selects[0].options) == 2
        assert not selects[0].disabled

    def test_en_serie_sigue_el_entregable_de_siempre(self):
        """Contraprueba de la rama: en serie NO debe aparecer la del respaldo."""
        at = AppTest.from_function(_script_serie).run(timeout=60)
        at.button[0].click().run(timeout=60)
        assert not at.exception
        sub = [s.value for s in at.subheader]
        assert any("T_sal_aux" in s for s in sub), sub
        assert not any("respaldo" in s.lower() for s in sub), sub
