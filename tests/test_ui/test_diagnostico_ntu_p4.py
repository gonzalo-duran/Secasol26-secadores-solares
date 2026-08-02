"""P4 muestra el acoplamiento aire↔producto (NTU) — S63, etapa 3.

Smoke de render: el bloque nuevo lee variables del scope de ``render()``
(``T_amb_calc_K``, ``P_proyecto_Pa``), así que un rename ahí se manifestaría
como ``NameError`` recién en la app. Este test lo levanta en CI.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _montar(session_state) -> None:
    from core.camara import Camara, CargaProducto, ConstruccionCamara, DireccionFlujo
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
    p.camara.flujo.direccion_flujo = DireccionFlujo.VERTICAL_ASCENDENTE
    session_state.proyecto = p


def _script() -> None:
    import streamlit as st

    from tests.test_ui.test_diagnostico_ntu_p4 import _montar

    _montar(st.session_state)

    import ui.p4_camara as p4

    p4.render()


class TestClavesDeTraduccion:
    """El bloque tiene que existir en los tres idiomas."""

    CLAVES = (
        "p4.transferencia.titulo",
        "p4.transferencia.topologia_sobre",
        "p4.transferencia.ntu.label",
        "p4.transferencia.ntu.help",
        "p4.transferencia.acercamiento.label",
        "p4.transferencia.area.label",
        "p4.transferencia.h.label",
        "p4.transferencia.regimen",
        "p4.transferencia.regimen_transferencia",
        "p4.transferencia.regimen_intermedio",
        "p4.transferencia.regimen_energia",
    )

    def test_existen_en_los_tres_idiomas(self):
        from ui.componentes.traducciones import cargar_diccionario

        for lang in ("es", "en", "pt"):
            d = cargar_diccionario(lang)
            for clave in self.CLAVES:
                assert d.get(clave, "").strip(), (lang, clave)

    def test_el_regimen_interpola_el_placeholder(self):
        from ui.componentes.traducciones import cargar_diccionario

        for lang in ("es", "en", "pt"):
            assert "{regimen}" in cargar_diccionario(lang)["p4.transferencia.regimen"]


class TestRenderNoRompe:

    def test_el_bloque_aparece_tras_calcular(self):
        """Hay que **apretar el botón**: el bloque vive en la vista de resultados.

        Sin el click, P4 renderiza sin llegar nunca al diagnóstico y el smoke no
        guardaría nada (verificado: sin click el bloque no aparece).
        """
        at = AppTest.from_function(_script)
        at.run(timeout=120)
        assert at.button, "P4 debería ofrecer el botón de cálculo"
        at.button[0].click().run(timeout=600)
        assert not at.exception, [str(e) for e in at.exception]

        etiquetas = [m.label for m in at.metric]
        assert "NTU" in etiquetas, etiquetas
        assert any("quilibrio" in e for e in etiquetas), etiquetas
