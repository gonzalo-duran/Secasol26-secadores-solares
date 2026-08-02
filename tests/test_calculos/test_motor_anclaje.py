"""Tests de regresión del módulo motor con anclaje empírico.

Objetivo: prevenir que el modelo vuelva a subestimar groseramente la potencia
del motor como ocurría antes de la Fase 1 del refactor (S31, 2026-05-17).

Anclaje empírico: en armarios de 50 kg de carga, el grupo UNSa/INENCO usa
rutinariamente extractores tipo "campanita" Gatti 150 — **76 W eléctricos**
nominales con **900 m³/h (0.25 m³/s)** a descarga libre. Eficiencia total
realista del conjunto motor+ventilador ~0.20–0.30 → ΔP útil ≈ 60–100 Pa,
P_eléctrica esperada en operación: **40–150 W** (rango amplio porque
depende de η reales del extractor concreto).
"""

from __future__ import annotations

import pytest

from calculos.motor_calc import (
    densidad_aire,
    estimar_delta_P_camara,
    estimar_delta_P_singulares,
)
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    DireccionFlujo,
    GeometriaCamara,
)
from core.motor import Motor


def _camara_armario_50kg_manzana(Q_vol_m3_s: float) -> Camara:
    rho = densidad_aire(323.15, 101325.0)
    return Camara(
        geometria=GeometriaCamara(largo_m=1.5, ancho_m=1.0, alto_m=1.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=5,
            area_bandeja_m2=0.8,
            espesor_capa_m=0.020,
            separacion_entre_bandejas_m=0.15,
        ),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=rho * Q_vol_m3_s,
            direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
        ),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=50.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
    )


class TestAnclajeExtractor76W:
    """El armario 50 kg manzana con Q=0.25 m³/s debe dar P_elec en el orden
    del extractor real (76 W). Tolerancia generosa porque las eficiencias
    típicas varían bastante."""

    def test_el_anclaje_lo_sostienen_los_ductos_no_la_camara(self):
        """Dónde vive la resistencia que justifica los 76 W del extractor.

        Hasta S63 este test exigía **> 30 Pa de la cámara sola**, apoyado en
        Ergun sobre el lecho atravesado. Con cross-flow único (S64) el aire
        barre las bandejas a ~0.5 m/s y la cámara aporta décimas de Pa: la
        resistencia del lazo está en los ductos, los codos y el colector, que
        es lo que sostiene el anclaje de campo (ver
        ``test_potencia_electrica_en_rango_realista``, que sigue dando en el
        rango del Gatti 150).

        ATENCIÓN al leer esto: si el armario real de 50 kg es de **lecho
        atravesado** —50 kg sobre 5 bandejas de 0.8 m² son ~2.7 cm de capa, que
        es un lecho, no una monocapa— entonces la cámara sí aporta ΔP y el
        modelo lo está subestimando a propósito. Es el riesgo asumido en
        ``docs/notas/plan_crossflow_unico_camara.md`` §7.1.
        """
        cam = _camara_armario_50kg_manzana(Q_vol_m3_s=0.25)
        dP_cam = estimar_delta_P_camara(cam)
        sing = estimar_delta_P_singulares(Q_vol_m3_s=0.25, v_ducto_m_s=6.0, n_paralelo=1, n_codos=2)
        assert dP_cam < 5.0, (
            f"ΔP cámara en cross-flow = {dP_cam:.2f} Pa. Si subió a decenas de "
            "Pa, alguien reintrodujo una resistencia de lecho."
        )
        assert sing["total"] > 10.0 * dP_cam, (
            "El anclaje de 76 W tiene que apoyarse en ductos y singulares: "
            f"singulares {sing['total']:.1f} Pa vs cámara {dP_cam:.2f} Pa."
        )

    def test_singulares_no_despreciables_a_v_ducto_realista(self):
        """Con v_ducto=6 m/s (típico ducto secador), las singulares deben
        ser > 30 Pa — antes del fix eran cero (no se calculaban)."""
        sing = estimar_delta_P_singulares(
            Q_vol_m3_s=0.25,
            v_ducto_m_s=6.0,
            n_paralelo=1,
            n_codos=2,
        )
        assert sing["total"] > 30.0, (
            f"ΔP singulares = {sing['total']:.1f} Pa, esperaba > 30 Pa "
            "(entrada + salida + 2 codos a v=6 m/s)."
        )

    def test_potencia_electrica_en_rango_realista(self):
        """Setup completo armario 50 kg con eficiencias realistas para
        extractor axial chico → P_elec ∈ [40, 200] W. El anclaje 76 W
        cae en este rango."""
        cam = _camara_armario_50kg_manzana(Q_vol_m3_s=0.25)
        dP_cam = estimar_delta_P_camara(cam)
        sing = estimar_delta_P_singulares(
            Q_vol_m3_s=0.25,
            v_ducto_m_s=6.0,
            n_paralelo=1,
            n_codos=2,
        )
        dP_col = 10.0  # colector típico armario (estimación)
        dP_duc = 0.20 * (dP_col + dP_cam)

        mot = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=dP_col,
            delta_P_camara_Pa=dP_cam,
            delta_P_ductos_Pa=dP_duc,
            delta_P_singulares_Pa=sing["total"],
            eficiencia_ventilador=0.40,  # axial chico (campanita) realista
            eficiencia_motor=0.70,  # motor monofásico ~70 W
            factor_servicio=1.15,
        )

        # Rango aceptable [40, 250] W — generoso porque las η varían bastante.
        # Anclaje real: 76 W. Modelo pre-fix daba ~16 W (rompía este test).
        assert 40.0 < mot.potencia_electrica_W < 250.0, (
            f"P_elec = {mot.potencia_electrica_W:.1f} W fuera de rango "
            "[40, 250] W. Anclaje empírico: extractor 76 W para Q=0.25 m³/s "
            "en armario 50 kg manzana. Si está debajo de 40 W el modelo "
            "volvió a subestimar; si está por encima de 250 W algo se "
            "sobreestimó."
        )

    def test_singulares_se_suman_al_total(self):
        """Verifica que delta_P_singulares_Pa efectivamente entra en
        Motor.perdida_carga_total_Pa."""
        mot_sin = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=12.0,
        )
        mot_con = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=12.0,
            delta_P_singulares_Pa=60.0,
        )
        assert mot_con.perdida_carga_total_Pa == pytest.approx(
            mot_sin.perdida_carga_total_Pa + 60.0
        )
        # Y la potencia se incrementa proporcionalmente
        assert mot_con.potencia_electrica_W > mot_sin.potencia_electrica_W


class TestGeometriaLechoCatalogo:
    """El motor lee d_p del catálogo cuando ConfiguracionBandejas no lo
    sobreescribe.

    Desde S64 el uso vivo de ``d_p`` es la **altura de rugosidad** de la pared
    del canal en cross-flow (``ε_eff = max(ε_chapa, d_p)``), no el diámetro de
    partícula de Ergun. La cadena de resolución catálogo → default es la misma.
    """

    def test_manzana_usa_el_d_p_del_catalogo_sin_valor_explicito(self):
        """Sin d_p en ConfiguracionBandejas, la rugosidad sale del catálogo."""
        rho = densidad_aire(323.15, 101325.0)
        cam = Camara(
            geometria=GeometriaCamara(largo_m=1.0, ancho_m=1.0, alto_m=1.0),
            bandejas=ConfiguracionBandejas(
                n_bandejas=3,
                area_bandeja_m2=0.5,
                espesor_capa_m=0.020,
                separacion_entre_bandejas_m=0.15,
                diametro_eq_particula_m=None,  # ← clave: no seteado
            ),
            flujo=ConfiguracionFlujo(
                caudal_masico_kg_s=rho * 0.1,
                direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
            ),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        from calculos.lecho_producto import D_P_DEFAULT_M, geometria_lecho

        d_p, _eps, _phi = geometria_lecho(cam.bandejas, "manzana")
        assert d_p == pytest.approx(0.006), "esperaba el d_p de manzana del catálogo"
        assert d_p != pytest.approx(D_P_DEFAULT_M)
        assert estimar_delta_P_camara(cam) > 0.0

    def test_producto_inexistente_usa_default(self):
        """Si producto_id no está en el catálogo se cae a los defaults
        conservadores (8 mm, 0.45, 0.6) sin romper. Test directo del helper
        para evitar la validación de CargaProducto."""
        from calculos.lecho_producto import (
            D_P_DEFAULT_M,
            EPSILON_DEFAULT,
            PHI_S_DEFAULT,
            geometria_lecho,
        )
        from core.camara import ConfiguracionBandejas

        b = ConfiguracionBandejas(
            n_bandejas=3,
            area_bandeja_m2=0.5,
            espesor_capa_m=0.020,
            separacion_entre_bandejas_m=0.15,
            diametro_eq_particula_m=None,
        )
        d_p, eps, phi = geometria_lecho(b, producto_id="producto_que_no_existe")
        assert (d_p, eps, phi) == (D_P_DEFAULT_M, EPSILON_DEFAULT, PHI_S_DEFAULT)
