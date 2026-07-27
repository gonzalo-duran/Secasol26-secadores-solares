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


# ---------------------------------------------------------------------------
# Operación anual: los widgets de política arrancan del proyecto (S59)
# ---------------------------------------------------------------------------


def _montar_anual(session_state) -> None:
    """Proyecto ANUAL completo (clima de 12 meses + colector) con política guardada."""
    from dataclasses import replace

    import numpy as np
    import pandas as pd

    from core.camara import Camara, CargaProducto, ConfiguracionFlujo, GeometriaCamara
    from core.clima import Clima
    from core.colector import BancoColectores, Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.operacion import PoliticaRecarga
    from core.proyecto import Configuracion, ModoAnalisis, Proyecto, Tipologia

    idx = pd.date_range("2020-01-01", periods=8784, freq="h", tz="UTC")
    horas = np.array([t.hour for t in idx], dtype=float)
    ghi = np.maximum(0.0, 900.0 * np.cos((horas - 15.0) / 24.0 * 2 * np.pi))
    datos = pd.DataFrame(
        {
            "T_amb_K": 288.0 + 8.0 * np.sin((horas - 9.0) / 24.0 * 2 * np.pi),
            "GHI_Wm2": ghi,
            "DNI_Wm2": ghi * 0.85,
            "DHI_Wm2": ghi * 0.15,
            "WS_ms": np.full(len(idx), 2.0),
            "presion_Pa": np.full(len(idx), 88000.0),
            "HR": np.clip(0.6 - 0.4 * (ghi / 900.0), 0.1, 0.9),
        },
        index=idx,
    )

    p = Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.ANUAL,
            # La política que el usuario dejó guardada en el proyecto.
            politica_recarga=PoliticaRecarga(
                hora_carga_h=6.5,
                maniobra_h=2.5,
                exigir_pronostico=False,
                umbral_pronostico_MJ_m2=12.0,
            ),
        )
    )
    p.emplazamiento = Emplazamiento()
    p.clima = Clima(datos=datos, anio=2020)
    p.colector = Colector(unidad=ColectorUnidad(), banco=BancoColectores())
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.0, alto_m=1.5),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.05),
        carga_producto=CargaProducto(producto_id="manzana", masa_total_kg=20.0),
    )
    p.configuracion = replace(p.configuracion)  # normaliza (ANUAL coacciona el paso)
    session_state.proyecto = p


def _script_anual() -> None:
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar_anual

    _montar_anual(st.session_state)

    import ui.p4_camara as p4

    p4.render()


def test_p4_anual_widgets_arrancan_de_la_politica_guardada():
    """Un proyecto cargado tiene que mostrar SU operación, no los defaults.

    Hasta S58 la política vivía solo en los widgets: reabrir el proyecto los
    dejaba en 8:00 / 1 h / pronóstico on / 8 MJ sin decir nada, y recalcular el
    año daba otro número que el del reporte guardado (S59).
    """
    at = AppTest.from_function(_script_anual)
    at.run(timeout=120)
    assert not at.exception
    assert at.session_state["p4_anual_recarga_hora"].hour == 6
    assert at.session_state["p4_anual_recarga_hora"].minute == 30
    assert at.session_state["p4_anual_recarga_maniobra"] == pytest.approx(2.5)
    assert at.session_state["p4_anual_pronostico_activo"] is False
    assert at.session_state["p4_anual_pronostico_umbral"] == pytest.approx(12.0)


def _script_anual_widget_movido() -> None:
    import streamlit as st

    from tests.test_ui.test_p4_render_smoke import _montar_anual

    _montar_anual(st.session_state)
    # El usuario mueve el umbral de pronóstico sin apretar "Calcular año".
    st.session_state["p4_anual_pronostico_activo"] = True
    st.session_state["p4_anual_pronostico_umbral"] = 20.0

    import ui.p4_camara as p4

    p4.render()


def test_mover_un_widget_de_politica_actualiza_el_proyecto():
    """La política se escribe en cada rerun, como `proyecto.camara`.

    Si solo se escribiera al calcular, el .json exportado podría decir una cosa
    y los widgets mostrar otra, y el año calculado no se marcaría viejo.
    """
    at = AppTest.from_function(_script_anual_widget_movido)
    at.run(timeout=120)
    assert not at.exception
    pol = at.session_state.proyecto.configuracion.politica_recarga
    assert pol.umbral_pronostico_MJ_m2 == pytest.approx(20.0)
    assert pol.exigir_pronostico is True


def _script_ventana_batch() -> None:
    """Gran escala BATCH en modo VENTANA: la política tiene que estar editable."""
    import datetime as _dt

    import streamlit as st

    from core.camara import (
        Camara,
        CargaProducto,
        ConfiguracionBandejas,
        ConfiguracionFlujo,
        GeometriaCamara,
    )
    from core.colector import BancoColectores, Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.operacion import PoliticaRecarga
    from core.proyecto import (
        Configuracion,
        ModoAnalisis,
        Proyecto,
        SubtipoGranEscala,
        Tipologia,
    )

    p = Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.VENTANA,
            subtipo_gran_escala=SubtipoGranEscala.BATCH,
            ventana_inicio=_dt.date(2020, 3, 1),
            ventana_fin=_dt.date(2020, 3, 15),
            politica_recarga=PoliticaRecarga(hora_carga_h=7.0, maniobra_h=3.0),
        )
    )
    p.emplazamiento = Emplazamiento()
    p.colector = Colector(unidad=ColectorUnidad(), banco=BancoColectores())
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=3.0, ancho_m=2.0, alto_m=2.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=15,
            area_bandeja_m2=1.5,
            espesor_capa_m=0.03,
            separacion_entre_bandejas_m=0.12,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=1.0),
        carga_producto=CargaProducto(producto_id="manzana", masa_total_kg=60.0),
    )
    st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_p4_ventana_batch_expone_la_politica():
    """En VENTANA de gran escala BATCH la política es editable (S59).

    Hasta S58 los widgets solo existían en la sección anual, así que este modo
    encadenaba lotes con los defaults del motor y sin forma de tocarlos.
    """
    at = AppTest.from_function(_script_ventana_batch)
    at.run(timeout=120)
    assert not at.exception
    # Los widgets existen y arrancan de la política guardada.
    assert at.session_state["p4_anual_recarga_hora"].hour == 7
    assert at.session_state["p4_anual_recarga_maniobra"] == pytest.approx(3.0)
    # Y no aparece el botón de cálculo anual: el de ventana vive en P7.
    assert "p4_anual_calcular" not in at.session_state


def _script_ventana_semicontinuo() -> None:
    import datetime as _dt

    import streamlit as st

    from core.camara import (
        Camara,
        CargaProducto,
        ConfiguracionBandejas,
        ConfiguracionFlujo,
        ConfiguracionTunel,
        GeometriaCamara,
    )
    from core.colector import BancoColectores, Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.proyecto import (
        Configuracion,
        ModoAnalisis,
        Proyecto,
        SubtipoGranEscala,
        Tipologia,
    )

    p = Proyecto(
        configuracion=Configuracion(
            tipologia=Tipologia.GRAN_ESCALA,
            modo_analisis=ModoAnalisis.VENTANA,
            subtipo_gran_escala=SubtipoGranEscala.SEMICONTINUO,
            ventana_inicio=_dt.date(2020, 3, 1),
            ventana_fin=_dt.date(2020, 3, 15),
        )
    )
    p.emplazamiento = Emplazamiento()
    p.colector = Colector(unidad=ColectorUnidad(), banco=BancoColectores())
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=3.0, ancho_m=2.0, alto_m=2.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=15,
            area_bandeja_m2=1.5,
            espesor_capa_m=0.03,
            separacion_entre_bandejas_m=0.12,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=1.0),
        carga_producto=CargaProducto(producto_id="manzana", masa_total_kg=60.0),
        tunel=ConfiguracionTunel(n_zonas=3, intervalo_avance_h=12.0),
    )
    st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_p4_ventana_semicontinuo_no_muestra_la_politica():
    """El túnel avanza columnas por cadencia: no recarga, no aplica la política."""
    at = AppTest.from_function(_script_ventana_semicontinuo)
    at.run(timeout=120)
    assert not at.exception
    assert "p4_anual_recarga_hora" not in at.session_state


def _script_sin_camara_construible() -> None:
    """P4 con `proyecto.camara = None` — el estado real cuando la geometría que
    el usuario está editando todavía no es coherente."""
    import streamlit as st

    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.emplazamiento = Emplazamiento()
    p.camara = None
    st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_bocas_se_dibujan_aunque_la_camara_no_sea_construible():
    """Regresión S61: el bloque de bocas colgaba de `proyecto.camara`.

    Una pila de bandejas más alta que la cámara (8 × 0.07 m en 0.50 m) hace que
    `Camara.__post_init__` levante `COHE_BANDEJAS_NO_CABEN_EN_CAMARA` y
    `proyecto.camara` quede en None. Los widgets tienen que seguir dibujándose:
    es justo cuando el usuario está editando y necesita verlos.
    """
    at = AppTest.from_function(_script_sin_camara_construible)
    at.run(timeout=120)
    assert not at.exception
    assert "p4_flujo_usar_bocas" in [w.key for w in at.checkbox]


def _script_caja_sin_colector_con_clima() -> None:
    """Cajón pasivo con clima cargado (media 10.5 °C, HR 45 %)."""
    import numpy as np
    import pandas as pd
    import streamlit as st

    from core.camara import (
        Camara,
        CarasTranslucidas,
        CargaProducto,
        ConfiguracionBandejas,
        ConfiguracionFlujo,
        ConstruccionCamara,
        GeometriaCamara,
    )
    from core.clima import Clima
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.CAJA))
    p.emplazamiento = Emplazamiento()
    idx = pd.date_range("2023-01-01", periods=8760, freq="h", tz="UTC")
    p.clima = Clima(
        datos=pd.DataFrame(
            {
                "T_amb_K": np.full(8760, 283.65),
                "GHI_Wm2": np.zeros(8760),
                "DNI_Wm2": np.zeros(8760),
                "DHI_Wm2": np.zeros(8760),
                "WS_ms": np.full(8760, 1.5),
                "presion_Pa": np.full(8760, 88000.0),
                "HR": np.full(8760, 0.45),
            },
            index=idx,
        ),
        anio=2023,
    )
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=0.5, ancho_m=0.5, alto_m=0.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=3,
            area_bandeja_m2=0.2,
            separacion_entre_bandejas_m=0.07,
            espesor_capa_m=0.015,
        ),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=0.03,
            area_entrada_aire_m2=0.02,
            area_salida_aire_m2=0.02,
        ),
        construccion=ConstruccionCamara(
            cubierta_translucida_id="policarbonato_alveolar",
            caras_translucidas=CarasTranslucidas(techo=True, frente=True, atras=True),
        ),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=6.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
        ),
    )
    st.session_state.proyecto = p

    import ui.p4_camara as p4

    p4.render()


def test_sin_colector_el_borde_se_deriva_del_ambiente():
    """S61: sin colector no hay nada que caliente el aire de entrada.

    Los sliders permitían declarar aire a 55 °C entrando a un cajón sin fuente
    de calor, y su rango (30–90 °C) ni siquiera llegaba a las temperaturas
    ambiente reales — el propio texto de ayuda pedía algo que el control
    prohibía.
    """
    at = AppTest.from_function(_script_caja_sin_colector_con_clima)
    at.run(timeout=120)
    assert not at.exception
    labels = [str(s.label) for s in at.slider]
    assert not [x for x in labels if "aire de entrada" in x]
    textos = " ".join(str(m.value) for m in list(at.info) + list(at.caption))
    assert "es el ambiente" in textos
    assert "10.5 °C" in textos  # media del clima, no el fallback de 25 °C


def test_T_amb_representativa_lee_el_dataframe_de_clima():
    """Regresión: leía `clima.T_amb_K`, que no existe (las series están en
    `clima.datos`), así que caía siempre al fallback de 25 °C."""
    at = AppTest.from_function(_script_caja_sin_colector_con_clima)
    at.run(timeout=120)
    textos = " ".join(str(m.value) for m in list(at.info) + list(at.caption) + list(at.markdown))
    assert "fallback" not in textos


def test_cajon_pasivo_pide_renovaciones_no_kg_s():
    """S61: en un cajón sin ventilador ni colector el caudal se pide en
    renovaciones de aire por minuto.

    Pedirlo en kg/s no tiene anclaje —nadie lo impone— y el default de fábrica
    (0.030 kg/s) son ~12 renovaciones/min en una caja chica: un orden de
    magnitud por encima de lo que el tiro mueve. Medido sobre el cajón del
    usuario, la previa con ese default sobrestimaba el agua evaporada un 28 %
    frente al lazo natural; con 1 renovación/min queda dentro del 1 %.
    """
    at = AppTest.from_function(_script_caja_sin_colector_con_clima)
    at.run(timeout=120)
    assert not at.exception
    keys = {w.key: w for w in at.number_input}
    assert "p4_flujo_renovaciones_min" in keys
    # Arranca del anclaje físico, no del caudal de fábrica heredado.
    assert keys["p4_flujo_renovaciones_min"].value == pytest.approx(1.0)


def test_rho_ambiente_usa_la_altitud_y_la_T_del_sitio():
    """La conversión renovaciones → kg/s no puede usar 1.2 kg/m³ de manual:
    a 10 °C y 1187 m de altitud el aire pesa ~0.90 kg/m³ (25 % menos)."""
    import pandas as pd

    from core.clima import Clima
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia
    from ui.p4_camara import _rho_aire_ambiente

    idx = pd.date_range("2023-01-01", periods=24, freq="h", tz="UTC")
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.CAJA))
    p.emplazamiento = Emplazamiento(altitud_m=1187.0)
    p.clima = Clima(
        datos=pd.DataFrame(
            {
                "T_amb_K": [283.65] * 24,
                "GHI_Wm2": [0.0] * 24,
                "DNI_Wm2": [0.0] * 24,
                "DHI_Wm2": [0.0] * 24,
                "WS_ms": [1.5] * 24,
                "presion_Pa": [88000.0] * 24,
                "HR": [0.45] * 24,
            },
            index=idx,
        ),
        anio=2023,
    )
    from ui.p4_camara import _P_ref_Pa, _T_amb_representativa_K

    rho = _rho_aire_ambiente(p)
    P_ref = _P_ref_Pa(p)
    T_ref, _ = _T_amb_representativa_K(p)
    assert rho == pytest.approx(P_ref / (287.058 * T_ref))
    # Bien por debajo del 1.20 kg/m³ de manual (nivel del mar, 20 °C).
    assert rho < 1.15
