"""Bloque de operación asumida en el reporte PDF (ui/reporte.py, S59).

Un reporte que dice "169 lotes" sin decir a qué hora se carga, cuánto dura la
maniobra y contra qué umbral se miró el pronóstico no es reproducible: esos
valores mueven el conteo de lotes tanto como el tamaño del colector. Hasta S58
el PDF mostraba ``dias_salteados_pronostico`` sin decir contra qué umbral.
"""

from __future__ import annotations

import pytest
from reportlab.platypus import Paragraph, Table

from core.operacion import PoliticaRecarga
from ui.reporte import _bloque_politica_recarga, _hacer_tr, _politica_snapshot, _styles

IDIOMAS = ("es", "en", "pt")


def _texto(elems: list) -> str:
    """Aplana el texto de los flowables (párrafos + celdas de tabla)."""
    partes: list[str] = []
    for e in elems:
        if isinstance(e, Paragraph):
            partes.append(e.getPlainText())
        elif isinstance(e, Table):
            for fila in e._cellvalues:
                partes.extend(str(c) for c in fila)
    return " | ".join(partes)


class TestExtraccionDelSnapshot:
    def test_saca_la_politica_de_configuracion(self):
        snap = {"configuracion": {"politica_recarga": {"hora_carga_h": 6.5}}}
        assert _politica_snapshot(snap) == {"hora_carga_h": 6.5}

    def test_snapshot_viejo_sin_politica(self):
        """Anterior a S59: el bloque simplemente no se dibuja."""
        assert _politica_snapshot({"configuracion": {}}) is None
        assert _politica_snapshot({}) is None


class TestBloque:
    def test_sin_politica_no_dibuja_nada(self):
        assert _bloque_politica_recarga(_styles(), _hacer_tr("es"), None) == []

    @pytest.mark.parametrize("idioma", IDIOMAS)
    def test_muestra_hora_maniobra_y_umbral(self, idioma):
        """`_fmt` recorta los ceros de cola: 2.0 sale como "2", 6.5 como "6.5"."""
        pol = PoliticaRecarga(hora_carga_h=6.5, maniobra_h=2.5, umbral_pronostico_MJ_m2=12.0)
        txt = _texto(_bloque_politica_recarga(_styles(), _hacer_tr(idioma), pol.a_dict()))
        assert "6.5" in txt, "falta la hora de carga"
        assert "2.5" in txt, "falta la maniobra"
        assert "12" in txt, "falta el umbral de pronóstico"
        assert "reporte.operacion" not in txt, "clave i18n sin traducir"

    @pytest.mark.parametrize("idioma", IDIOMAS)
    def test_avisa_que_el_pronostico_es_perfecto(self, idioma):
        """La idealización tiene que estar dicha donde se leen los números."""
        pol = PoliticaRecarga(exigir_pronostico=True)
        txt = _texto(_bloque_politica_recarga(_styles(), _hacer_tr(idioma), pol.a_dict()))
        esperado = {"es": "perfecto", "en": "perfect", "pt": "perfeita"}[idioma]
        assert esperado in txt.lower()

    def test_sin_pronostico_no_promete_nada(self):
        pol = PoliticaRecarga(exigir_pronostico=False)
        txt = _texto(_bloque_politica_recarga(_styles(), _hacer_tr("es"), pol.a_dict()))
        assert "perfecto" not in txt.lower()
        assert "sin mirar el pronóstico" in txt

    def test_encadenado_inmediato_se_declara_cota_superior(self):
        """Con la espera desactivada la hora de carga no significa nada."""
        pol = PoliticaRecarga(activa=False, hora_carga_h=6.5)
        txt = _texto(_bloque_politica_recarga(_styles(), _hacer_tr("es"), pol.a_dict()))
        assert "cota superior" in txt
        assert "6.5" not in txt, "no debe informar una hora de carga que no se usa"


class TestCableadoEnLasSecciones:
    """El bloque tiene que llegar a las secciones que lo consumen.

    No se verifica sobre los bytes del PDF: las fuentes van subseteadas y el
    texto no se recupera de los streams sin una librería de extracción. El seam
    que importa es sección → bloque.
    """

    def test_la_seccion_anual_incluye_la_operacion(self):
        from ui.reporte import _seccion_operacion_anual

        elems = _seccion_operacion_anual(
            _styles(),
            _hacer_tr("es"),
            snap_anual={"masa_seca_anual_kg": 386.0, "n_lotes_completos": 94},
            figuras=[],
            politica=PoliticaRecarga(hora_carga_h=6.5).a_dict(),
        )
        assert "Operación asumida" in _texto(elems)

    def test_la_seccion_anual_sin_politica_no_rompe(self):
        """Snapshot anterior a S59."""
        from ui.reporte import _seccion_operacion_anual

        elems = _seccion_operacion_anual(
            _styles(),
            _hacer_tr("es"),
            snap_anual={"masa_seca_anual_kg": 386.0},
            figuras=[],
        )
        assert "Operación asumida" not in _texto(elems)

    def test_la_ventana_batch_incluye_la_operacion(self):
        from ui.reporte import _seccion_ventana

        elems = _seccion_ventana(
            _styles(),
            _hacer_tr("es"),
            snap_ventana={"subtipo": "BATCH", "masa_seca_producida_kg": 100.0},
            figuras=[],
            politica=PoliticaRecarga(hora_carga_h=6.5).a_dict(),
        )
        assert "Operación asumida" in _texto(elems)

    def test_el_tunel_semicontinuo_no_la_informa(self):
        """El túnel avanza columnas por cadencia: informar recarga sería engañoso."""
        from ui.reporte import _seccion_ventana

        elems = _seccion_ventana(
            _styles(),
            _hacer_tr("es"),
            snap_ventana={"subtipo": "SEMICONTINUO", "masa_seca_producida_kg": 100.0},
            figuras=[],
            politica=PoliticaRecarga(hora_carga_h=6.5).a_dict(),
        )
        assert "Operación asumida" not in _texto(elems)
