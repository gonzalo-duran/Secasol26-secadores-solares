"""Test de integración de la ingesta contra los .xls REALES de ADITAL 2010.

Los archivos viven en docs/notas/dataset/ (no versionados en el deploy); si no
están presentes, todos los tests se saltean. La descarga NASA se inyecta fake
para no depender de red.
"""

import pathlib

import pandas as pd
import pytest

from calculos.clima_medido import (
    ingerir_clima_medido,
    leer_tabla,
    listar_hojas,
    sugerir_mapeo,
)
from core.clima import COLUMNAS_SI, CalidadClima, Clima
from core.clima_medido import ConfigMapeoClima, MapeoColumna
from core.emplazamiento import Emplazamiento

_DIR_ADITAL = (
    pathlib.Path(__file__).resolve().parents[2]
    / "docs"
    / "notas"
    / "dataset"
    / "secador ADITAL - Toto San Carlos"
)
_ARCHIVO_P3 = _DIR_ADITAL / "Medidas ADITAL 15-5-2010 a 18-6-2010.xls"
_ARCHIVO_MAESTRO = _DIR_ADITAL / "Medidas ADITAL 14-4-2010 a 28-4-2010.xls"

pytestmark = pytest.mark.skipif(
    not _ARCHIVO_P3.exists(), reason="dataset ADITAL no disponible en docs/notas/dataset/"
)

# Coordenadas correctas de San Carlos, Salta (typo de la tesis corregido).
_EMPL = Emplazamiento(latitud_deg=-25.9, longitud_deg=-65.93, altitud_m=1700.0)


def _fn_nasa_fake(emplazamiento, anio, **kwargs):
    idx = pd.date_range(f"{anio}-01-01", f"{anio}-12-31 23:00", freq="h", tz="UTC")
    datos = pd.DataFrame(
        {
            "T_amb_K": 285.0,
            "GHI_Wm2": 350.0,
            "DNI_Wm2": 450.0,
            "DHI_Wm2": 110.0,
            "WS_ms": 2.0,
            "presion_Pa": 82_500.0,
            "HR": 0.4,
        },
        index=idx,
    )
    return Clima(datos=datos, anio=anio, calidad=CalidadClima(), altitud_nasa_m=1650.0)


def test_listar_hojas_maestro():
    if not _ARCHIVO_MAESTRO.exists():
        pytest.skip("archivo maestro no disponible")
    hojas = listar_hojas(_ARCHIVO_MAESTRO.read_bytes(), _ARCHIVO_MAESTRO.name)
    assert "14-4 a 28-4 2010" in hojas
    assert "15-5 a 18-6 2010" in hojas


def test_sugerencia_sobre_headers_reales():
    tabla = leer_tabla(_ARCHIVO_P3.read_bytes(), _ARCHIVO_P3.name, hoja="Hoja1")
    cfg = sugerir_mapeo(tabla.columns)
    # el timestamp real se llama "dia y hora"
    assert cfg.columna_timestamp == "dia y hora"
    # ningún canal de proceso del secador debe sugerirse como clima
    origenes = [m.columna_origen for m in cfg.columnas]
    for canal in ("Temp sal col1", "Temp entr caño", "Temp quemador", "Temp prod"):
        assert canal not in origenes


def test_ingesta_end_to_end_hoja1():
    """Ingesta end-to-end del período 3 real (15-may → 18-jun 2010).

    La hoja solo trae canales de proceso del secador; para ejercitar el
    pipeline con una columna medida REAL se mapea la HR de entrada de cámara
    (valores en %, físicamente válidos) como si fuera ambiental. Es un
    artificio de test — el resto del clima sale del completador (fake NASA).
    """
    tabla = leer_tabla(_ARCHIVO_P3.read_bytes(), _ARCHIVO_P3.name, hoja="Hoja1")
    cfg = ConfigMapeoClima(
        columna_timestamp="dia y hora",
        zona_horaria="America/Argentina/Salta",
        columnas=[MapeoColumna("HR", "HR Entrada Cam(%)", "porcentaje")],
    )
    clima = ingerir_clima_medido(tabla, cfg, _EMPL, obtener_clima_fn=_fn_nasa_fake)

    assert clima.fuente == "hibrido"
    assert clima.anio == 2010
    assert list(clima.datos.columns) == list(COLUMNAS_SI)
    assert clima.frecuencia_nativa_s == pytest.approx(600.0)
    # período 3: 15-may 00:00 → 18-jun 14:30 hora local
    assert clima.qc is not None
    assert clima.qc.periodo_inicio.startswith("2010-05-15")
    assert clima.qc.periodo_fin.startswith("2010-06-18")
    assert clima.qc.meses_cubiertos == (5, 6)
    # la HR medida quedó en fracción [0,1]
    assert clima.datos["HR"].dropna().between(0.0, 1.0).all()
    # el resto vino del fake NASA
    assert clima.datos["GHI_Wm2"].iloc[12] == pytest.approx(350.0)
