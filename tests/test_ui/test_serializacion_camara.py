"""Tests de serialización/deserialización de Camara (P4).

Cubre el round-trip `_json_config_camara` → `_from_json_camara` con los
campos nuevos de la cámara radiativa orientada (pendiente/acimut/cara de
caída del techo, caras translúcidas, absortancia interior) y el back-compat
de snapshots viejos (sin esos campos → defaults históricos).
"""

from __future__ import annotations

from core.camara import (
    Camara,
    CapaPared,
    CarasTranslucidas,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    GeometriaCamara,
    ParedCamara,
)
from ui.p4_camara import _from_json_camara, _json_config_camara


def _camara_orientada() -> Camara:
    return Camara(
        geometria=GeometriaCamara(
            largo_m=1.5,
            ancho_m=1.0,
            alto_m=1.2,
            pendiente_techo_deg=25.0,
            acimut_camara_deg=90.0,
            cara_caida_techo="lateral_der",
        ),
        construccion=ConstruccionCamara(
            cubierta_translucida_id="policarbonato_alveolar",
            cubierta_translucida_espesor_m=0.008,
            caras_translucidas=CarasTranslucidas(techo=True, frente=True, lateral_der=True),
            absortancia_interior=0.75,
            pared=ParedCamara(
                capas=[
                    CapaPared(material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes")
                ]
            ),
        ),
        bandejas=ConfiguracionBandejas(n_bandejas=4, area_bandeja_m2=0.4),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.05),
        carga_producto=CargaProducto(producto_id="manzana"),
    )


def _camara_default() -> Camara:
    return Camara(
        bandejas=ConfiguracionBandejas(n_bandejas=4, area_bandeja_m2=0.4),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.05),
        carga_producto=CargaProducto(producto_id="manzana"),
    )


class TestRoundTripCamaraOrientada:
    def test_geometria_preserva_campos_nuevos(self):
        cam = _camara_orientada()
        data = _json_config_camara(cam)
        cam2 = _from_json_camara(data)
        assert cam2.geometria.pendiente_techo_deg == cam.geometria.pendiente_techo_deg
        assert cam2.geometria.acimut_camara_deg == cam.geometria.acimut_camara_deg
        assert cam2.geometria.cara_caida_techo == cam.geometria.cara_caida_techo

    def test_construccion_preserva_caras_translucidas_y_absortancia(self):
        cam = _camara_orientada()
        data = _json_config_camara(cam)
        cam2 = _from_json_camara(data)
        assert cam2.construccion.caras_translucidas == cam.construccion.caras_translucidas
        assert cam2.construccion.absortancia_interior == cam.construccion.absortancia_interior
        assert cam2.construccion.cubierta_translucida_id == cam.construccion.cubierta_translucida_id

    def test_round_trip_default_reproduce_comportamiento_historico(self):
        """Cámara default (techo-solo, β=0) hace round-trip exacto."""
        cam = _camara_default()
        cam2 = _from_json_camara(_json_config_camara(cam))
        assert cam2.geometria.pendiente_techo_deg == 0.0
        # Sin cubierta (master switch None) → sin caras activas, aunque
        # CarasTranslucidas() por sí sola tenga techo=True por default.
        assert cam2.construccion.caras_translucidas_activas() == ()


class TestBackCompatSnapshotViejo:
    """Snapshot sin los campos nuevos (sesiones anteriores a S47) → defaults."""

    def test_dict_viejo_sin_campos_nuevos_da_defaults(self):
        data_viejo = {
            "geometria": {"largo_m": 1.2, "ancho_m": 0.8, "alto_m": 1.5},
            "construccion": {
                "cubierta_translucida_id": "vidrio_comun",
                "A_rad_m2": None,
                "cubierta_translucida_espesor_m": None,
                "pared": {
                    "capas": [
                        {
                            "material_id": "lana_vidrio_media",
                            "espesor_m": 0.05,
                            "catalogo": "aislantes",
                        }
                    ]
                },
            },
            "bandejas": {
                "n_bandejas": 5,
                "area_bandeja_m2": 0.5,
                "espesor_capa_m": 0.02,
                "separacion_entre_bandejas_m": 0.15,
            },
            "carga_producto": {
                "producto_id": "manzana",
                "masa_total_kg": 10.0,
                "humedad_inicial_X": 4.6,
                "humedad_objetivo_X": 0.15,
                "modelo_capa_fina": "logaritmico",
                "modelo_isoterma": "gab",
            },
            "flujo": {"caudal_masico_kg_s": 0.03},
        }
        cam = _from_json_camara(data_viejo)
        assert cam.geometria.pendiente_techo_deg == 0.0
        assert cam.geometria.acimut_camara_deg == 180.0
        assert cam.geometria.cara_caida_techo == "frente"
        assert cam.construccion.caras_translucidas == CarasTranslucidas()
        assert cam.construccion.caras_translucidas_activas() == ("techo",)
        assert cam.construccion.absortancia_interior == 0.85
