"""Tests de CapaPared y ParedCamara (mejora 18).

Verifica el cómputo de resistencia térmica de pared simple y compuesta a
partir del catálogo de materiales (fondos.yaml + aislantes.yaml), y la
exposición de U_muros_W_m2K como property derivada en ConstruccionCamara.
"""

from __future__ import annotations

import pytest

from core import catalogo
from core.camara import (
    CapaPared,
    ConstruccionCamara,
    ParedCamara,
)

# ---------------------------------------------------------------------------
# CapaPared
# ---------------------------------------------------------------------------


class TestCapaPared:

    def test_capa_fondos_valida(self):
        c = CapaPared(material_id="pino", espesor_m=0.018, catalogo="fondos")
        k_pino = float(catalogo.FONDOS["pino"]["conductividad_termica"])
        assert c.conductividad_termica_W_mK == pytest.approx(k_pino)
        assert c.R_conduccion_m2K_W == pytest.approx(0.018 / k_pino)

    def test_capa_aislante_valida(self):
        c = CapaPared(material_id="lana_vidrio_media", espesor_m=0.050, catalogo="aislantes")
        assert c.conductividad_termica_W_mK == pytest.approx(0.040)
        assert c.R_conduccion_m2K_W == pytest.approx(0.050 / 0.040)

    def test_espesor_no_positivo_falla(self):
        with pytest.raises(ValueError, match="CAPA_ESPESOR_NO_POSITIVO"):
            CapaPared(material_id="pino", espesor_m=0.0, catalogo="fondos")

    def test_catalogo_invalido_falla(self):
        with pytest.raises(ValueError, match="CAPA_CATALOGO_INVALIDO"):
            CapaPared(material_id="pino", espesor_m=0.018, catalogo="placas")

    def test_material_no_encontrado_en_fondos_falla(self):
        with pytest.raises(ValueError, match="CAPA_MATERIAL_NO_ENCONTRADO"):
            CapaPared(material_id="ladrillo_inventado", espesor_m=0.10, catalogo="fondos")

    def test_material_no_encontrado_en_aislantes_falla(self):
        with pytest.raises(ValueError, match="CAPA_MATERIAL_NO_ENCONTRADO"):
            CapaPared(material_id="aerogel_marciano", espesor_m=0.05, catalogo="aislantes")


# ---------------------------------------------------------------------------
# ParedCamara
# ---------------------------------------------------------------------------


class TestParedCamara:

    def test_pared_simple_madera_18mm(self):
        """Pared simple de pino 18 mm → R = e/k, U alto (sin aislación)."""
        p = ParedCamara(
            capas=[
                CapaPared(material_id="pino", espesor_m=0.018, catalogo="fondos"),
            ]
        )
        k = float(catalogo.FONDOS["pino"]["conductividad_termica"])
        assert p.R_conduccion_m2K_W == pytest.approx(0.018 / k)
        assert p.U_conduccion_W_m2K == pytest.approx(k / 0.018)
        assert p.espesor_total_m == pytest.approx(0.018)
        assert not p.es_compuesta

    def test_pared_compuesta_sandwich_aislada(self):
        """Pared compuesta chapa + lana de vidrio 50 mm + chapa.

        R_total = 2·R_chapa + R_aislante
                ≈ 2·(0.0006/50) + (0.050/0.040)
                ≈ 1.250 m²K/W
        U_cond ≈ 0.8 W/(m²·K), próximo al U=0.5 histórico de armario aislado.
        """
        p = ParedCamara(
            capas=[
                CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.050, catalogo="aislantes"),
                CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
            ]
        )
        assert p.es_compuesta
        # R chapa = 0.0006 / 50 ≈ 1.2e-5 (despreciable)
        R_esperado = 2 * (0.0006 / 50.0) + (0.050 / 0.040)
        assert p.R_conduccion_m2K_W == pytest.approx(R_esperado, rel=1e-6)
        assert p.U_conduccion_W_m2K == pytest.approx(1.0 / R_esperado)
        assert p.espesor_total_m == pytest.approx(0.0512)

    def test_capas_en_serie_se_suman(self):
        """Dos capas iguales en serie → R total = 2·R individual."""
        p1 = ParedCamara(
            capas=[
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.040, catalogo="aislantes"),
            ]
        )
        p2 = ParedCamara(
            capas=[
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.040, catalogo="aislantes"),
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.040, catalogo="aislantes"),
            ]
        )
        assert p2.R_conduccion_m2K_W == pytest.approx(2 * p1.R_conduccion_m2K_W)

    def test_sin_capas_falla(self):
        with pytest.raises(ValueError, match="PARED_SIN_CAPAS"):
            ParedCamara(capas=[])

    def test_aislante_mejor_que_madera(self):
        """A igual espesor, lana de vidrio aísla mucho más que madera."""
        pared_aisl = ParedCamara(
            capas=[
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes"),
            ]
        )
        pared_mad = ParedCamara(
            capas=[
                CapaPared(material_id="pino", espesor_m=0.05, catalogo="fondos"),
            ]
        )
        assert pared_aisl.U_conduccion_W_m2K < pared_mad.U_conduccion_W_m2K
        # k_pino ≈ 0.12, k_lana ≈ 0.04 → ratio ≈ 3
        assert pared_mad.U_conduccion_W_m2K / pared_aisl.U_conduccion_W_m2K == pytest.approx(
            0.12 / 0.040, rel=0.05
        )


# ---------------------------------------------------------------------------
# ConstruccionCamara — integración con ParedCamara
# ---------------------------------------------------------------------------


class TestConstruccionCamaraConPared:

    def test_default_es_compuesto_y_U_razonable(self):
        """Default es pared compuesta sándwich aislado; U ≈ 0.8 W/(m²·K)."""
        cons = ConstruccionCamara()
        assert cons.pared.es_compuesta
        # Default = chapa + lana vidrio 50 mm + chapa → U ≈ 0.8
        assert 0.5 < cons.U_muros_W_m2K < 1.0

    def test_U_muros_es_property_de_pared(self):
        """U_muros_W_m2K es derivado de pared.U_conduccion_W_m2K (sin films)."""
        cons = ConstruccionCamara(
            pared=ParedCamara(
                capas=[
                    CapaPared(
                        material_id="lana_vidrio_media", espesor_m=0.040, catalogo="aislantes"
                    ),
                ]
            )
        )
        assert cons.U_muros_W_m2K == pytest.approx(1.0)  # R=1, U=1

    def test_pared_simple_acepta_solo_madera(self):
        """Pared simple sin aislante (peor caso aislación)."""
        cons = ConstruccionCamara(
            pared=ParedCamara(
                capas=[
                    CapaPared(material_id="pino", espesor_m=0.018, catalogo="fondos"),
                ]
            )
        )
        k = float(catalogo.FONDOS["pino"]["conductividad_termica"])
        assert cons.U_muros_W_m2K == pytest.approx(k / 0.018)
        assert cons.U_muros_W_m2K > 5.0  # sin aislación

    def test_cambiar_aislante_baja_U(self):
        """Aislante con menor k (poliuretano) → U más bajo a igual espesor."""
        pared_lana = ParedCamara(
            capas=[
                CapaPared(material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes"),
            ]
        )
        pared_pur = ParedCamara(
            capas=[
                CapaPared(
                    material_id="poliuretano_expandido", espesor_m=0.05, catalogo="aislantes"
                ),
            ]
        )
        cons_lana = ConstruccionCamara(pared=pared_lana)
        cons_pur = ConstruccionCamara(pared=pared_pur)
        # k_lana = 0.040, k_pur = 0.025 → U_pur < U_lana
        assert cons_pur.U_muros_W_m2K < cons_lana.U_muros_W_m2K
