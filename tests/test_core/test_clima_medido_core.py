"""Tests de las dataclasses de ingesta de clima medido (core/clima_medido.py)
y de la extensión back-compat de Clima (mejora 38, F1a)."""

import pandas as pd
import pytest

from core.clima import COLUMNA_POA_MEDIDA, FUENTES_CLIMA, Clima
from core.clima_medido import (
    CONVENCIONES_TIMESTAMP,
    PROCEDENCIA_DEFAULT,
    PROCEDENCIA_DERIVADA,
    PROCEDENCIA_MEDIDA,
    PROCEDENCIA_NASA,
    PROCEDENCIAS,
    UNIDADES_POR_VARIABLE,
    VARIABLES_MAPEABLES,
    ChequeoQC,
    ConfigMapeoClima,
    MapeoColumna,
    ReporteQC,
)


def _config_minima(**kwargs) -> ConfigMapeoClima:
    base = dict(
        columna_timestamp="TIMESTAMP",
        columnas=[MapeoColumna("T_amb_K", "Temp amb", "C")],
    )
    base.update(kwargs)
    return ConfigMapeoClima(**base)


# ---------------------------------------------------------------------------
# Back-compat de Clima
# ---------------------------------------------------------------------------


class TestClimaBackCompat:
    def test_clima_default_es_nasa_power(self):
        clima = Clima()
        assert clima.fuente == "nasa_power"
        assert clima.procedencia is None
        assert clima.frecuencia_nativa_s is None
        assert clima.datos_nativos is None
        assert clima.mapeo is None
        assert clima.qc is None

    def test_clima_constructor_historico_sigue_valido(self):
        df = pd.DataFrame({"T_amb_K": [300.0]})
        clima = Clima(datos=df, anio=2022, altitud_nasa_m=1200.0)
        assert clima.anio == 2022
        assert clima.fuente == "nasa_power"

    def test_CLIMA_FUENTE_INVALIDA(self):
        with pytest.raises(ValueError, match="CLIMA_FUENTE_INVALIDA"):
            Clima(fuente="satelital")

    def test_fuentes_validas_construyen(self):
        for fuente in FUENTES_CLIMA:
            assert Clima(fuente=fuente).fuente == fuente


# ---------------------------------------------------------------------------
# Constantes estables (la UI y los snapshots dependen de estos strings)
# ---------------------------------------------------------------------------


class TestConstantes:
    def test_procedencias_estables(self):
        assert PROCEDENCIAS == ("medida", "derivada", "completada_nasa", "default")
        assert PROCEDENCIA_MEDIDA == "medida"
        assert PROCEDENCIA_DERIVADA == "derivada"
        assert PROCEDENCIA_NASA == "completada_nasa"
        assert PROCEDENCIA_DEFAULT == "default"

    def test_variables_mapeables_cubren_columnas_si_y_poa(self):
        # Las 7 COLUMNAS_SI son mapeables, más la POA medida.
        assert set(VARIABLES_MAPEABLES) == {
            "T_amb_K",
            "GHI_Wm2",
            "DNI_Wm2",
            "DHI_Wm2",
            "WS_ms",
            "presion_Pa",
            "HR",
            COLUMNA_POA_MEDIDA,
        }

    def test_toda_variable_tiene_unidades(self):
        for v in VARIABLES_MAPEABLES:
            assert v in UNIDADES_POR_VARIABLE
            assert len(UNIDADES_POR_VARIABLE[v]) >= 1

    def test_convenciones_timestamp(self):
        assert CONVENCIONES_TIMESTAMP == ("instantanea", "promedio_fin", "promedio_inicio")


# ---------------------------------------------------------------------------
# Validaciones de MapeoColumna
# ---------------------------------------------------------------------------


class TestMapeoColumna:
    def test_mapeo_valido_construye(self):
        m = MapeoColumna("GHI_Wm2", "Radiacion horizontal", "W_m2")
        assert m.variable == "GHI_Wm2"

    def test_CLIMED_CONFIG_VARIABLE_DESCONOCIDA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_VARIABLE_DESCONOCIDA"):
            MapeoColumna("T_flujo_K", "Temp caño", "C")

    def test_CLIMED_CONFIG_COLUMNA_VACIA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_COLUMNA_VACIA"):
            MapeoColumna("T_amb_K", "   ", "C")

    def test_CLIMED_CONFIG_UNIDAD_INVALIDA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_UNIDAD_INVALIDA"):
            MapeoColumna("T_amb_K", "Temp amb", "W_m2")


# ---------------------------------------------------------------------------
# Validaciones de ConfigMapeoClima
# ---------------------------------------------------------------------------


class TestConfigMapeoClima:
    def test_config_valida_construye(self):
        cfg = _config_minima()
        assert cfg.variables_mapeadas() == ("T_amb_K",)
        assert cfg.convencion_timestamp == "instantanea"

    def test_CLIMED_CONFIG_SIN_TIMESTAMP(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_SIN_TIMESTAMP"):
            _config_minima(columna_timestamp="")

    def test_CLIMED_CONFIG_CONVENCION_INVALIDA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_CONVENCION_INVALIDA"):
            _config_minima(convencion_timestamp="promedio")

    def test_CLIMED_CONFIG_PLANO_INVALIDO(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_PLANO_INVALIDO"):
            _config_minima(plano_piranometro="inclinado")

    def test_CLIMED_CONFIG_ALTURA_NO_POSITIVA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_ALTURA_NO_POSITIVA"):
            _config_minima(altura_anemometro_m=0.0)

    def test_CLIMED_CONFIG_Z0_INVALIDO(self):
        # z0 debe ser > 0 y menor que la altura del anemómetro (perfil log).
        with pytest.raises(ValueError, match="CLIMED_CONFIG_Z0_INVALIDO"):
            _config_minima(z0_terreno_m=0.0)
        with pytest.raises(ValueError, match="CLIMED_CONFIG_Z0_INVALIDO"):
            _config_minima(altura_anemometro_m=2.0, z0_terreno_m=2.5)

    def test_z0_entra_en_el_hash_de_ingesta(self):
        """Cambiar el terreno debe invalidar la caché parquet del clima medido."""
        from calculos.clima_medido import hash_ingesta

        cfg_a = _config_minima(altura_anemometro_m=10.0, z0_terreno_m=0.05)
        cfg_b = _config_minima(altura_anemometro_m=10.0, z0_terreno_m=0.25)
        assert hash_ingesta("abc", cfg_a) != hash_ingesta("abc", cfg_b)

    def test_CLIMED_CONFIG_FILA_ENCABEZADO_NEGATIVA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_FILA_ENCABEZADO_NEGATIVA"):
            _config_minima(fila_encabezado=-1)

    def test_CLIMED_CONFIG_VARIABLE_DUPLICADA(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_VARIABLE_DUPLICADA"):
            _config_minima(
                columnas=[
                    MapeoColumna("T_amb_K", "Temp amb", "C"),
                    MapeoColumna("T_amb_K", "Temp amb 2", "K"),
                ]
            )

    def test_CLIMED_CONFIG_TIMESTAMP_MAPEADO(self):
        with pytest.raises(ValueError, match="CLIMED_CONFIG_TIMESTAMP_MAPEADO"):
            _config_minima(
                columnas=[MapeoColumna("T_amb_K", "TIMESTAMP", "C")],
            )


# ---------------------------------------------------------------------------
# ReporteQC
# ---------------------------------------------------------------------------


class TestReporteQC:
    def test_con_hallazgos_filtra(self):
        rep = ReporteQC(
            chequeos=[
                ChequeoQC("rango_fisico", "T_amb_K", n_marcados=0, n_avisos=0),
                ChequeoQC("ghi_nocturna", "GHI_Wm2", n_marcados=3),
                ChequeoQC("sensor_congelado", "HR", n_avisos=2),
            ]
        )
        codigos = [c.codigo for c in rep.con_hallazgos()]
        assert codigos == ["ghi_nocturna", "sensor_congelado"]

    def test_reporte_vacio(self):
        assert ReporteQC().con_hallazgos() == []
