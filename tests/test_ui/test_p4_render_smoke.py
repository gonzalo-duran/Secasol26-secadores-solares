"""Smoke test del render de P4 vía AppTest (mejora 38, fase 4).

Atrapa errores de runtime del render de la sección "🔬 Validación con datos
medidos" (referencias de módulo mal puestas, claves i18n que revientan) que los
tests de helpers puros no ven — misma lección que el `cm.CONVENCIONES_TIMESTAMP`
de la fase 2b en P3.

Ojo: ``AppTest.from_function`` serializa **solo** el cuerpo de la función, así que
cada script tiene que ser autocontenido (nada de helpers module-level).
"""

from __future__ import annotations

import pytest
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


# ---------------------------------------------------------------------------
# Caudal de cámara acoplado al del colector (S58)
# ---------------------------------------------------------------------------


def _script_caudal_colector() -> None:
    import streamlit as st

    from core.camara import Camara, CargaProducto
    from core.colector import BancoColectores, Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    if "proyecto" not in st.session_state:
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        p.emplazamiento = Emplazamiento()
        p.colector = Colector(
            unidad=ColectorUnidad(largo_m=2.5, velocidad_diseno_ms=2.0),
            banco=BancoColectores(n_serie=1, n_paralelo=1),
        )
        p.camara = Camara(carga_producto=CargaProducto(producto_id="manzana"))
        st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_el_caudal_de_camara_arranca_en_el_del_colector():
    """Sistema hermético: lo que sale del banco entra a la cámara.

    Reportado por el usuario (S58) sobre un armario en Salta: el caudal de P4
    arrancaba en el default de ``ConfiguracionFlujo`` (0.030 kg/s) mientras el
    banco entregaba 0.055, y la única señal era una advertencia al final de la
    corrida anual (``ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE``).
    """
    from calculos.balance_global import caudal_masico_banco_kg_s
    from core.camara import ConfiguracionFlujo
    from ui.p4_camara import _P_ref_Pa, _T_amb_ref_K

    at = AppTest.from_function(_script_caudal_colector)
    at.run(timeout=90)
    assert not at.exception

    proy = at.session_state["proyecto"]
    # Caudal del banco evaluado en las condiciones del sitio, que es lo mismo
    # que mira ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE.
    esperado = caudal_masico_banco_kg_s(proy.colector, _T_amb_ref_K(proy), _P_ref_Pa(proy))

    caudales = [n for n in at.number_input if "kg/s" in (n.label or "")]
    assert caudales, "no se encontró el number_input de caudal másico"
    assert caudales[0].value == pytest.approx(esperado, rel=1e-3)
    assert caudales[0].value != pytest.approx(
        ConfiguracionFlujo().caudal_masico_kg_s
    ), "el caudal no puede quedarse en el default de fábrica habiendo colector"
    assert caudales[0].disabled, "con el caudal atado al colector el input va deshabilitado"


def test_desacoplar_el_caudal_deja_editarlo():
    """Desacoplar es legítimo (mezcla con aire ambiente) y debe ser posible."""
    at = AppTest.from_function(_script_caudal_colector)
    at.session_state["p4_flujo_seguir_colector"] = False
    at.run(timeout=90)
    assert not at.exception

    caudales = [n for n in at.number_input if "kg/s" in (n.label or "")]
    assert caudales and not caudales[0].disabled


class TestSeguirColectorDefault:
    """Cuándo el caudal de cámara arranca atado al del colector.

    Es una **decisión persistida**, no una deducción. Deducirla comparando el
    caudal guardado con el del banco era frágil: el del banco es
    ``v·A·n·ρ(T_amb, P)``, así que recalcular el clima con otro año movía ρ y el
    checkbox se destildaba solo al cargar un proyecto (S58, reportado por el
    usuario).
    """

    def test_activo_por_default(self):
        from core.camara import ConfiguracionFlujo
        from ui.p4_camara import _seguir_colector_default

        assert _seguir_colector_default(ConfiguracionFlujo(), 0.055) is True

    def test_respeta_la_decision_guardada_de_desacoplar(self):
        """Desacoplar es legítimo (mezcla con aire ambiente) y debe sobrevivir."""
        from core.camara import ConfiguracionFlujo
        from ui.p4_camara import _seguir_colector_default

        flujo = ConfiguracionFlujo(caudal_masico_kg_s=0.12, seguir_caudal_colector=False)
        assert _seguir_colector_default(flujo, 0.055) is False

    def test_un_caudal_distinto_no_lo_desactiva_por_si_solo(self):
        """El caso que rompía: ρ cambia con el año y el caudal ya no coincide."""
        from core.camara import ConfiguracionFlujo
        from ui.p4_camara import _seguir_colector_default

        flujo = ConfiguracionFlujo(caudal_masico_kg_s=0.16410, seguir_caudal_colector=True)
        assert _seguir_colector_default(flujo, 0.16395) is True

    def test_snapshot_viejo_sin_el_campo_cae_a_la_coincidencia(self):
        """Back-compat: sin decisión que leer, se infiere con 2 % de tolerancia."""
        from ui.p4_camara import _seguir_colector_default

        class _FlujoViejo:
            caudal_masico_kg_s = 0.055

        assert _seguir_colector_default(_FlujoViejo(), 0.0551) is True
        assert _seguir_colector_default(_FlujoViejo(), 0.12) is False
