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

    def test_camara_armario_50kg_da_dP_sobre_30_pa(self):
        """Lo crítico: ΔP cámara con Ergun activo por catálogo debe estar
        por encima de 30 Pa para manzana 50 kg, no los ~5 Pa del modelo
        previo (que asumía Ergun=0 sin d_p explícito)."""
        cam = _camara_armario_50kg_manzana(Q_vol_m3_s=0.25)
        dP_cam = estimar_delta_P_camara(cam)
        assert dP_cam > 30.0, (
            f"ΔP cámara armario 50 kg manzana = {dP_cam:.1f} Pa, "
            "esperaba > 30 Pa con Ergun activo por catálogo (manzana d_p=6 mm)."
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
    sobreescribe — esto habilita Ergun no-cero por default y es la clave
    del fix de la subestimación."""

    def test_manzana_ergun_no_cero_sin_d_p_explicito(self):
        """Para manzana, sin setear d_p en ConfiguracionBandejas, el motor
        debe usar el d_p del catálogo (6 mm) y dar ΔP > 0 por Ergun."""
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
        # Solo malla daría algo pequeño; con Ergun activo (d_p del catálogo
        # = 6 mm) debe ser significativamente mayor.
        Q_vol = cam.flujo.caudal_masico_kg_s / rho
        v0 = Q_vol / cam.bandejas.area_bandeja_m2
        dP_malla_sola = 2.0 * (rho * v0**2 / 2.0) * cam.bandejas.n_bandejas
        dP_total = estimar_delta_P_camara(cam)
        assert dP_total > 2.0 * dP_malla_sola, (
            f"ΔP_total = {dP_total:.2f} Pa apenas supera ΔP_malla_sola = "
            f"{dP_malla_sola:.2f} Pa — Ergun no se está activando con d_p "
            "del catálogo."
        )

    def test_producto_inexistente_usa_default(self):
        """Si producto_id no está en el catálogo, motor_calc cae a defaults
        conservadores (8 mm, 0.45, 0.6) sin romper. Test directo del helper
        para evitar la validación de CargaProducto."""
        from calculos.motor_calc import _delta_P_lecho_por_bandeja
        from core.camara import ConfiguracionBandejas

        b = ConfiguracionBandejas(
            n_bandejas=3,
            area_bandeja_m2=0.5,
            espesor_capa_m=0.020,
            separacion_entre_bandejas_m=0.15,
            diametro_eq_particula_m=None,
        )
        # producto inexistente → defaults (8 mm) → Ergun no-cero
        dP = _delta_P_lecho_por_bandeja(
            b,
            v0=0.2,
            rho=1.09,
            mu=1.96e-5,
            producto_id="producto_que_no_existe",
        )
        assert dP > 0, f"Esperaba ΔP_Ergun > 0 con defaults (8 mm). Obtuve {dP:.3f} Pa."
