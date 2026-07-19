"""Tests de los helpers puros de la sección de clima medido de P2 (mejora 38, F1a)."""

import pandas as pd

from core.clima import Clima
from core.clima_medido import PROCEDENCIA_MEDIDA, PROCEDENCIA_NASA, ReporteQC
from ui.p2_emplazamiento import (
    _construir_config_medido,
    _resumen_medido_dict,
    _tabla_procedencia,
)


def _traducir_fake(clave: str, **kwargs) -> str:
    return clave.rsplit(".", 1)[-1]


class TestConstruirConfigMedido:
    def test_construye_solo_variables_mapeadas(self):
        seleccion = {
            "T_amb_K": ("Temp amb", "C"),
            "GHI_Wm2": (None, "W_m2"),
            "HR": ("HR amb", "porcentaje"),
        }
        cfg = _construir_config_medido(
            "TIMESTAMP",
            seleccion,
            "America/Argentina/Salta",
            "instantanea",
            3.0,
            "horizontal",
            "Hoja1",
            0,
        )
        assert cfg.columna_timestamp == "TIMESTAMP"
        assert cfg.variables_mapeadas() == ("T_amb_K", "HR")
        assert cfg.altura_anemometro_m == 3.0
        assert cfg.hoja == "Hoja1"


class TestTablaProcedencia:
    def test_tabla_traducida(self):
        clima = Clima(
            fuente="hibrido",
            procedencia={"T_amb_K": PROCEDENCIA_MEDIDA, "WS_ms": PROCEDENCIA_NASA},
        )
        tabla = _tabla_procedencia(clima, _traducir_fake)
        assert len(tabla) == 2
        assert list(tabla.columns) == ["variable", "origen"]
        assert set(tabla["origen"]) == {"medida", "completada_nasa"}

    def test_sin_procedencia_tabla_vacia(self):
        assert len(_tabla_procedencia(Clima(), _traducir_fake)) == 0


class TestResumenMedido:
    def test_campos(self):
        qc = ReporteQC(
            periodo_inicio="2010-05-01T00:00:00-03:00",
            periodo_fin="2010-05-03T23:50:00-03:00",
            meses_cubiertos=(5,),
        )
        clima = Clima(
            datos=pd.DataFrame({"T_amb_K": [290.0]}),
            anio=2010,
            fuente="hibrido",
            frecuencia_nativa_s=600.0,
            qc=qc,
        )
        resumen = _resumen_medido_dict(clima)
        assert resumen["fuente"] == "hibrido"
        assert resumen["anio"] == 2010
        assert resumen["paso_s"] == 600.0
        assert resumen["meses"] == (5,)

    def test_sin_qc(self):
        resumen = _resumen_medido_dict(Clima(fuente="medido"))
        assert resumen["periodo_inicio"] is None
        assert resumen["meses"] == ()
