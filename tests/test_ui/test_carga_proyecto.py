"""Carga de un proyecto completo (ui/componentes/carga_proyecto.py).

P7 sabía guardar el proyecto entero pero no había forma de volver a cargarlo:
solo existían cargadores por sección, y ni siquiera servían para el archivo
completo porque ``parsear_json_seccion`` valida el ``seccion`` de la raíz. El
snapshot completo era un artefacto de archivo, no un "guardar proyecto" (S58).

El test que importa es el **round-trip**: lo que P7 exporta tiene que volver a
entrar. Si alguien agrega un campo al modelo y lo olvida en el exportador o en
el cargador, el proyecto se degrada en silencio al guardar y cargar.
"""

from __future__ import annotations

import pytest

from core.auxiliar import Auxiliar, CargaArranque, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import Camara, CargaProducto, ConfiguracionFlujo, GeometriaCamara
from core.colector import BancoColectores, Colector, ColectorUnidad
from core.emplazamiento import Emplazamiento
from core.operacion import PoliticaRecarga
from core.proyecto import (
    Configuracion,
    DiaAnalisis,
    ModoAnalisis,
    Proyecto,
    Tipologia,
)
from ui.componentes.carga_proyecto import (
    ErrorCargaProyecto,
    cargar_proyecto_completo,
    resumen_clima_snapshot,
)


def _proyecto_completo() -> Proyecto:
    """Proyecto con todas las secciones pobladas y valores no-default."""
    p = Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.ANUAL,
            dia_analisis=DiaAnalisis.SOLSTICIO_INVIERNO,
            # Todos los campos distintos del default: si el round-trip los
            # perdiera, volverían a 8:00 / 1 h / pronóstico on / 8 MJ.
            politica_recarga=PoliticaRecarga(
                hora_carga_h=6.5,
                maniobra_h=2.0,
                exigir_pronostico=False,
                umbral_pronostico_MJ_m2=12.0,
            ),
        )
    )
    p.meta.nombre = "Secador de prueba"
    p.meta.autor = "G. Durán"
    p.meta.notas = "round-trip"
    p.emplazamiento = Emplazamiento(
        latitud_deg=-24.72,
        longitud_deg=-65.41,
        altitud_m=1187.0,
        albedo_suelo=0.30,
        acimut_colector_deg=170.0,
        pendiente_colector_deg=30.0,
        z0_terreno_m=0.25,
    )
    p.colector = Colector(
        unidad=ColectorUnidad(largo_m=2.5, velocidad_diseno_ms=2.0),
        banco=BancoColectores(n_serie=1, n_paralelo=3),
    )
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.2, alto_m=1.8),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.055),
        carga_producto=CargaProducto(producto_id="manzana", masa_total_kg=25.0),
    )
    p.auxiliar = Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=2000.0,
        set_point_T_K=328.15,
        cargas_arranque=[CargaArranque(hora_inicio_h=5.0, duracion_h=3.0)],
    )
    return p


def _exportar(proyecto) -> dict:
    """Arma el JSON completo como lo hace el botón de descarga de P7."""
    from ui.p7_resultados import _json_resultados_completo

    return _json_resultados_completo(proyecto, None)


class TestGuardas:
    def test_rechaza_un_json_que_no_es_objeto(self):
        with pytest.raises(ErrorCargaProyecto, match="CARGA_JSON_NO_ES_OBJETO"):
            cargar_proyecto_completo([1, 2, 3])

    def test_rechaza_una_seccion_suelta(self):
        """Un .json de solo-cámara va a su pestaña, no acá."""
        with pytest.raises(ErrorCargaProyecto, match="CARGA_SECCION_INCORRECTA"):
            cargar_proyecto_completo({"seccion": "camara", "geometria": {}})

    def test_enum_invalido_es_explicito(self):
        with pytest.raises(ErrorCargaProyecto, match="CARGA_ENUM_INVALIDO"):
            cargar_proyecto_completo(
                {"seccion": "prediseno_completo", "configuracion": {"tipologia": "IGLU"}}
            )


class TestRoundTrip:
    """Lo que P7 exporta tiene que volver a entrar, sin perder nada por el camino."""

    @pytest.fixture(scope="class")
    def _ida_y_vuelta(self):
        original = _proyecto_completo()
        cargado, avisos = cargar_proyecto_completo(_exportar(original))
        return original, cargado, avisos

    def test_no_hay_avisos(self, _ida_y_vuelta):
        _orig, _carg, avisos = _ida_y_vuelta
        assert avisos == [], f"la carga reportó problemas: {avisos}"

    def test_meta_y_configuracion(self, _ida_y_vuelta):
        orig, carg, _ = _ida_y_vuelta
        assert carg.meta.nombre == orig.meta.nombre
        assert carg.meta.autor == orig.meta.autor
        assert carg.meta.notas == orig.meta.notas
        assert carg.configuracion.tipologia == orig.configuracion.tipologia
        assert carg.configuracion.modo_analisis == orig.configuracion.modo_analisis
        assert carg.configuracion.dia_analisis == orig.configuracion.dia_analisis

    def test_emplazamiento_incluida_la_rugosidad(self, _ida_y_vuelta):
        """z0 faltaba en el exportador: se guardaba y volvía al default (S58)."""
        orig, carg, _ = _ida_y_vuelta
        assert carg.emplazamiento.latitud_deg == pytest.approx(orig.emplazamiento.latitud_deg)
        assert carg.emplazamiento.longitud_deg == pytest.approx(orig.emplazamiento.longitud_deg)
        assert carg.emplazamiento.altitud_m == pytest.approx(orig.emplazamiento.altitud_m)
        assert carg.emplazamiento.albedo_suelo == pytest.approx(orig.emplazamiento.albedo_suelo)
        assert carg.emplazamiento.zona_horaria == orig.emplazamiento.zona_horaria
        assert carg.emplazamiento.z0_terreno_m == pytest.approx(
            orig.emplazamiento.z0_terreno_m
        ), "la rugosidad del terreno no sobrevivió el round-trip"

    def test_el_acimut_no_cambia_de_convencion(self, _ida_y_vuelta):
        """Se guarda en Duffie y se lee en Duffie: sin doble conversión."""
        orig, carg, _ = _ida_y_vuelta
        assert carg.emplazamiento.acimut_colector_deg == pytest.approx(
            orig.emplazamiento.acimut_colector_deg
        )
        assert carg.emplazamiento.pendiente_colector_deg == pytest.approx(
            orig.emplazamiento.pendiente_colector_deg
        )

    def test_colector(self, _ida_y_vuelta):
        orig, carg, _ = _ida_y_vuelta
        assert carg.colector.unidad.largo_m == pytest.approx(orig.colector.unidad.largo_m)
        assert carg.colector.unidad.velocidad_diseno_ms == pytest.approx(
            orig.colector.unidad.velocidad_diseno_ms
        )
        assert carg.colector.banco.n_paralelo == orig.colector.banco.n_paralelo

    def test_camara(self, _ida_y_vuelta):
        orig, carg, _ = _ida_y_vuelta
        assert carg.camara.flujo.caudal_masico_kg_s == pytest.approx(
            orig.camara.flujo.caudal_masico_kg_s
        )
        assert carg.camara.carga_producto.producto_id == orig.camara.carga_producto.producto_id
        assert carg.camara.geometria.largo_m == pytest.approx(orig.camara.geometria.largo_m)

    def test_auxiliar_con_su_calendario(self, _ida_y_vuelta):
        """El calendario de arranque es lo que distingue al híbrido."""
        orig, carg, _ = _ida_y_vuelta
        assert carg.auxiliar.potencia_nominal_W == pytest.approx(orig.auxiliar.potencia_nominal_W)
        assert carg.auxiliar.set_point_T_K == pytest.approx(orig.auxiliar.set_point_T_K)
        assert len(carg.auxiliar.cargas_arranque) == len(orig.auxiliar.cargas_arranque)
        assert carg.auxiliar.cargas_arranque[0].hora_inicio_h == pytest.approx(5.0)

    def test_politica_de_recarga(self, _ida_y_vuelta):
        """La operación se perdía al guardar/cargar: vivía en los widgets (S59).

        Sin esto, reabrir el proyecto y recalcular el año daba otro número que el
        del reporte guardado, sin ningún aviso.
        """
        orig, carg, _ = _ida_y_vuelta
        assert carg.configuracion.politica_recarga == orig.configuracion.politica_recarga

    def test_un_snapshot_sin_politica_usa_los_defaults(self):
        """Proyectos guardados antes de S59: los defaults son los que usaron."""
        datos = _exportar(_proyecto_completo())
        del datos["configuracion"]["politica_recarga"]
        proy, avisos = cargar_proyecto_completo(datos)
        assert proy.configuracion.politica_recarga == PoliticaRecarga()
        assert avisos == []

    def test_una_politica_corrupta_es_explicita(self):
        datos = _exportar(_proyecto_completo())
        datos["configuracion"]["politica_recarga"]["hora_carga_h"] = 25.0
        with pytest.raises(ErrorCargaProyecto, match="CARGA_POLITICA_INVALIDA"):
            cargar_proyecto_completo(datos)

    def test_el_hash_anual_coincide(self, _ida_y_vuelta):
        """La prueba fuerte: el proyecto cargado es el mismo para el motor.

        Si algún campo que entra al cálculo se perdiera en el round-trip, la
        huella de entradas del modo anual cambiaría.
        """
        from calculos.simulacion_anual import hash_entradas_anual

        orig, carg, _ = _ida_y_vuelta
        assert hash_entradas_anual(carg) == hash_entradas_anual(orig)


class TestSeccionesFaltantes:
    def test_un_proyecto_minimo_carga(self):
        proy, avisos = cargar_proyecto_completo({"seccion": "prediseno_completo"})
        assert proy.colector is None and proy.camara is None
        assert avisos == []

    def test_una_seccion_corrupta_no_aborta_el_resto(self):
        """Recuperar el 90 % con un aviso es mejor que rechazar el archivo."""
        datos = _exportar(_proyecto_completo())
        datos["camara"]["carga_producto"]["producto_id"] = "producto_que_no_existe"
        proy, avisos = cargar_proyecto_completo(datos)
        assert proy.colector is not None, "el colector no tiene por qué caerse con la cámara"
        assert proy.camara is None
        assert any("camara" in a for a in avisos)


class TestResumenClima:
    def test_sin_clima_devuelve_none(self):
        assert resumen_clima_snapshot({"seccion": "prediseno_completo"}) is None

    def test_expone_el_anio_para_rehacer_la_descarga(self):
        datos = {"clima": {"anio": 2005, "fuente": "nasa_power", "n_horas": 8760}}
        assert resumen_clima_snapshot(datos)["anio"] == 2005


# ---------------------------------------------------------------------------
# Render de P1 con el cargador montado
# ---------------------------------------------------------------------------


def _script_p1() -> None:
    import streamlit as st

    from core.proyecto import Proyecto

    if "proyecto" not in st.session_state:
        st.session_state.proyecto = Proyecto()

    import ui.p1_tipologia as p1

    p1.render()


def test_p1_renderiza_con_el_cargador():
    """El cargador se monta antes de leer el proyecto: no puede romper P1."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_script_p1)
    at.run(timeout=60)
    assert not at.exception
    assert any(
        u.key == "p1_cargar_proyecto" for u in at.get("file_uploader")
    ), "falta el uploader de proyecto completo en P1"
