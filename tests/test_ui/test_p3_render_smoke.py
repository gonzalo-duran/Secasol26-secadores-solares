"""Smoke test del render completo de P3 vía AppTest (mejora 38, fase 2).

Atrapa errores de runtime del render (referencias de módulo mal puestas, claves
i18n faltantes que revientan) que los tests de helpers puros no ven — como el
`cm.CONVENCIONES_TIMESTAMP` inexistente que rompía la sección de validación.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _script() -> None:
    """Monta un proyecto ARMARIO con colector + clima y renderiza P3."""
    import numpy as np
    import pandas as pd
    import streamlit as st

    from core.clima import Clima
    from core.colector import Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    if "proyecto" not in st.session_state:
        empl = Emplazamiento()
        idx = pd.date_range("2023-06-15", periods=48, freq="h", tz="UTC")
        h = np.arange(48) % 24
        ghi = np.maximum(0.0, 900.0 * np.sin(np.pi * (h - 6.0) / 12.0))
        df = pd.DataFrame(
            {
                "T_amb_K": 288.15 + 8.0 * np.sin(2 * np.pi * (h - 9) / 24.0),
                "GHI_Wm2": ghi,
                "DNI_Wm2": np.full(48, np.nan),
                "DHI_Wm2": np.full(48, np.nan),
                "WS_ms": np.full(48, 2.5),
                "presion_Pa": np.full(48, 90000.0),
                "HR": np.full(48, 0.40),
            },
            index=idx,
        )
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        p.emplazamiento = empl
        p.clima = Clima(datos=df, anio=2023)
        p.colector = Colector(unidad=ColectorUnidad())
        st.session_state.proyecto = p

        # Inyecta un archivo de referencia falso para que la sección de validación
        # llegue a los widgets de mapeo (col timestamp/valor, unidad, convención, tz)
        # — ahí vivía el bug cm.CONVENCIONES_TIMESTAMP.
        from calculos import clima_medido as cm

        csv = (
            b"fecha,T_out,Ta,I\n"
            b"2023-06-15 06:00:00,20.0,15.0,700.0\n"
            b"2023-06-15 07:00:00,25.0,16.0,750.0\n"
        )
        st.session_state["p3_val_archivo"] = {
            "nombre": "ref.csv",
            "bytes": csv,
            "hash": cm.hash_archivo(csv),
        }
        # Fase 2b: enciende fecha-fija y forzado para renderizar esos widgets.
        st.session_state["p3_val_usar_fecha"] = True
        st.session_state["p3_val_forzar"] = True

    import ui.p3_colector as p3

    p3.render()


def test_p3_render_no_revienta():
    """El render de P3 (incl. la sección de validación) corre sin excepción."""
    at = AppTest.from_function(_script)
    at.run(timeout=60)
    assert not at.exception


def _script_aplicar():
    """Proyecto con colector v=1.5; simula 'aplicar óptimo' (velocidad→8)."""
    import streamlit as st

    from core.colector import Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia

    if "proyecto" not in st.session_state:
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        p.emplazamiento = Emplazamiento()
        p.colector = Colector(unidad=ColectorUnidad(velocidad_diseno_ms=1.5))
        st.session_state.proyecto = p

    if st.session_state.get("_do_apply"):
        # Réplica exacta del handler "aplicar óptimo" de _render_calibracion_colector.
        from calculos.barrido_parametrico import aplicar_parametro
        from ui.p3_colector import _WIDGET_KEY_POR_PARAM

        aplicar_parametro(st.session_state.proyecto, "velocidad_diseno", 8.0)
        st.session_state.pop(_WIDGET_KEY_POR_PARAM["velocidad_diseno"], None)
        del st.session_state["_do_apply"]

    import ui.p3_colector as p3

    p3.render()


def test_aplicar_optimo_refresca_campo_velocidad():
    """Regresión: 'aplicar óptimo' actualiza el number_input de velocidad de diseño."""
    at = AppTest.from_function(_script_aplicar)
    at.run(timeout=60)
    assert at.number_input(key="p3_velocidad").value == 1.5

    at.session_state["_do_apply"] = True
    at.run(timeout=60)
    assert at.session_state.proyecto.colector.unidad.velocidad_diseno_ms == 8.0
    # El campo de arriba (widget) refleja el óptimo aplicado.
    assert at.number_input(key="p3_velocidad").value == 8.0


def _script_flujo_completo_aplicar():
    """Flujo real: archivo + resultado de validación + calibración presentes."""
    import numpy as np
    import pandas as pd
    import streamlit as st

    from calculos import clima_medido as cm
    from calculos.calibracion import PuntoCalibracion, ResultadoCalibracion
    from calculos.metricas_validacion import MetricasAjuste
    from core.colector import Colector, ColectorUnidad
    from core.emplazamiento import Emplazamiento
    from core.proyecto import Configuracion, Proyecto, Tipologia
    from core.validacion import SenalReferencia

    if "proyecto" not in st.session_state:
        p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
        p.emplazamiento = Emplazamiento()
        p.colector = Colector(unidad=ColectorUnidad(velocidad_diseno_ms=1.5))
        st.session_state.proyecto = p

        csv = b"fecha,Tout,Ta,I\n2007-06-09 09:00:00,20,15,700\n2007-06-09 10:00:00,25,16,750\n"
        h = cm.hash_archivo(csv)
        st.session_state["p3_val_archivo"] = {"nombre": "ref.csv", "bytes": csv, "hash": h}
        st.session_state["_p3_val_tabla_cache"] = (
            (h, None, 0),
            cm.leer_tabla(csv, "ref.csv", hoja=None, fila_encabezado=0),
        )
        idx = pd.date_range("2023-06-16 09:00", periods=8, freq="h", tz="UTC")
        st.session_state["p3_val_resultado"] = {
            "senal": SenalReferencia(
                variable="T_salida_colector",
                serie=pd.Series(300.0 + np.arange(8), index=idx),
                unidad_origen="C",
                frecuencia_nativa_s=3600.0,
            ),
            "t_sim": idx,
            "y_sim_K": (300.0 + np.arange(8)).astype(float),
            "forzado_medido": False,
            "clima_forzante": None,
            "salida": "mezcla",
        }
        mo = MetricasAjuste(8, 0.9, 0.2, 0.5, 0.98, 0.9, 0.95)
        # Óptimo > 10 m/s: reproduce el caso real (gran escala, caudal alto) que
        # crasheaba por el max_value=10 hardcodeado del widget de velocidad.
        st.session_state["p3_cal_resultado"] = ResultadoCalibracion(
            parametro="velocidad_diseno",
            objetivo_nombre="rmse",
            puntos=[PuntoCalibracion(15.0, 0.9, mo)],
            valor_optimo=15.0,
            metricas_optimo=mo,
        )

    import ui.p3_colector as p3

    p3.render()


def test_aplicar_optimo_flujo_completo_con_boton_real():
    """Clic en 'Aplicar óptimo' con velocidad > 10 m/s (gran escala) NO crashea y refresca."""
    at = AppTest.from_function(_script_flujo_completo_aplicar)
    at.run(timeout=60)
    assert at.number_input(key="p3_velocidad").value == 1.5
    assert any(b.key == "p3_cal_aplicar" for b in at.button)

    at.button(key="p3_cal_aplicar").click().run(timeout=60)
    # No debe haber excepción (antes: StreamlitValueAboveMaxError con max_value=10).
    assert not at.exception
    assert at.session_state.proyecto.colector.unidad.velocidad_diseno_ms == 15.0
    assert at.number_input(key="p3_velocidad").value == 15.0
