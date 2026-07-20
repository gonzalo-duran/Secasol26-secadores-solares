"""Smoke test del render de P4 vía AppTest (mejora 38, fase 4).

Atrapa errores de runtime del render de la sección "🔬 Validación con datos
medidos" (referencias de módulo mal puestas, claves i18n que revientan) que los
tests de helpers puros no ven — misma lección que el `cm.CONVENCIONES_TIMESTAMP`
de la fase 2b en P3.

Ojo: ``AppTest.from_function`` serializa **solo** el cuerpo de la función, así que
cada script tiene que ser autocontenido (nada de helpers module-level).
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _montar(session_state, extra: dict | None = None) -> None:
    """Deja proyecto + archivo de ensayo en sesión (se inlinea en cada script)."""
    from calculos import clima_medido as cm
    from core.camara import Camara, CargaProducto
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    if "proyecto" not in session_state:
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        p.emplazamiento = Emplazamiento()
        p.camara = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.20,
            )
        )
        session_state.proyecto = p
    csv = (
        b"fecha,T_cam,HR_cam,T_in,HR_in,Tamb,masa\n"
        b"2010-05-01 09:00:00,40.0,35.0,45.0,20.0,18.0,10.0\n"
        b"2010-05-01 10:00:00,41.0,33.0,46.0,19.0,19.0,9.2\n"
        b"2010-05-01 11:00:00,42.0,31.0,47.0,18.0,20.0,8.5\n"
        b"2010-05-01 12:00:00,43.0,30.0,48.0,18.0,21.0,7.9\n"
    )
    session_state["p4_val_archivo"] = {
        "nombre": "ensayo.csv",
        "bytes": csv,
        "hash": cm.hash_archivo(csv),
    }
    for k, v in (extra or {}).items():
        session_state[k] = v


def _script_base() -> None:
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar

    _montar(st.session_state)

    import ui.p4_camara as p4

    p4.render()


def test_p4_render_no_revienta():
    """El render de P4 (incl. la sección de validación) corre sin excepción."""
    at = AppTest.from_function(_script_base)
    at.run(timeout=90)
    assert not at.exception


def _script_masa() -> None:
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar

    _montar(
        st.session_state,
        {"p4_val_variable": "masa_producto", "p4_val_usar_fecha": True},
    )

    import ui.p4_camara as p4

    p4.render()


def test_p4_render_masa_producto_y_fecha_fija():
    """La rama de pesadas (masa seca obligatoria) y la de fecha fija renderizan."""
    at = AppTest.from_function(_script_masa)
    at.run(timeout=90)
    assert not at.exception
    assert at.session_state["p4_val_variable"] == "masa_producto"


def _script_procesar() -> None:
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar

    _montar(
        st.session_state,
        {
            "p4_val_col_ts": "fecha",
            "p4_val_variable": "T_camara",
            "p4_val_col_val": "T_cam",
            "p4_val_unidad_T_camara": "C",
            "p4_val_zona": "UTC",
            "p4_val_t_ent": "T_in",
            "p4_val_hr_ent": "HR_in",
            "p4_val_t_amb": "Tamb",
        },
    )

    import ui.p4_camara as p4

    p4.render()


def test_p4_procesar_produce_metricas():
    """Apretar el botón real corre la cámara aislada y deja métricas en sesión."""
    at = AppTest.from_function(_script_procesar)
    at.run(timeout=90)
    assert not at.exception

    boton = [b for b in at.button if b.key == "p4_val_procesar"]
    assert boton, "no se encontró el botón de procesar"
    boton[0].click().run(timeout=180)
    assert not at.exception

    res = at.session_state["p4_val_resultado"]
    assert res is not None
    assert res["variable"] == "T_camara"
    # Hubo solape temporal y se calcularon métricas sobre pares alineados.
    assert res["metricas"] is not None
    assert res["metricas"].n_pares >= 2


def _script_aplicar() -> None:
    """Simula el handler 'aplicar óptimo' del área efectiva (patrón pendiente)."""
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar

    _montar(st.session_state)

    if st.session_state.get("_do_apply"):
        # Réplica exacta del handler de _render_calibracion_camara.
        from calculos.barrido_parametrico import aplicar_parametro
        from ui.p4_camara import _WIDGET_KEY_POR_PARAM_P4

        aplicar_parametro(st.session_state.proyecto, "area_bandeja", 1.8)
        st.session_state["_p4_pending_widget"] = {_WIDGET_KEY_POR_PARAM_P4["area_bandeja"]: 1.8}
        del st.session_state["_do_apply"]

    import ui.p4_camara as p4

    p4.render()


def test_aplicar_optimo_refresca_area_bandeja():
    """Regresión: 'aplicar óptimo' escribe el campo Y refresca el number_input."""
    at = AppTest.from_function(_script_aplicar)
    at.run(timeout=90)
    assert not at.exception
    assert at.number_input(key="p4_area_bandeja").value == 0.5

    at.session_state["_do_apply"] = True
    at.run(timeout=90)
    assert not at.exception
    assert at.session_state.proyecto.camara.bandejas.area_bandeja_m2 == 1.8
    # El widget de arriba refleja el óptimo aplicado (si no, el usuario aplica y
    # el campo sigue mostrando el valor viejo — el bug que ya vivimos en P3).
    assert at.number_input(key="p4_area_bandeja").value == 1.8


def _script_semicontinuo() -> None:
    """Gran escala semicontinuo: la previa debe avisar que es de un solo nodo."""
    import streamlit as st

    from core.camara import Camara, CargaProducto, ConfiguracionTunel
    from core.emplazamiento import Emplazamiento
    from core.proyecto import (
        Configuracion,
        ModoAnalisis,
        Proyecto,
        SubtipoGranEscala,
        Tipologia,
    )

    if "proyecto" not in st.session_state:
        p = Proyecto(
            configuracion=Configuracion(
                tipologia=Tipologia.GRAN_ESCALA,
                subtipo_gran_escala=SubtipoGranEscala.SEMICONTINUO,
                modo_analisis=ModoAnalisis.DIARIO,
            )
        )
        p.emplazamiento = Emplazamiento()
        p.camara = Camara(
            carga_producto=CargaProducto(producto_id="manzana"),
            tunel=ConfiguracionTunel(n_zonas=3, intervalo_avance_h=2.0),
        )
        st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_semicontinuo_avisa_que_la_previa_es_de_un_nodo():
    """El usuario tiene que saber que P4 no resuelve el túnel de N zonas."""
    at = AppTest.from_function(_script_semicontinuo)
    at.run(timeout=90)
    assert not at.exception

    textos = " ".join(w.value for w in at.warning)
    assert "P7" in textos, "la previa de semicontinuo debe remitir a P7"
    assert "nodo" in textos.lower()
