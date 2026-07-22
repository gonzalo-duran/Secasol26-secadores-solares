"""Tests de tipología CAJA: cámara con techo translúcido obligatorio,
sin colector externo, aire entrante a T_amb.

Etapa A del plan CAJA (S29): admite Camara para CAJA, reusando el motor
termodinámico con T_ent = T_amb y aporte Q_rad a través de la cubierta.
"""

from __future__ import annotations

import numpy as np

from calculos.balance_global import (
    construir_serie_sintetica_dia_tipo,
    verificar_coherencia_proyecto,
)
from calculos.camara_calc import calcular_camara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.psicrometria import humedad_absoluta
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    GeometriaCamara,
    ParedCamara,
)
from core.proyecto import (
    Configuracion,
    Meta,
    ModoAnalisis,
    Proyecto,
    Tipologia,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _camara_caja(*, cubierta_id: str | None = "vidrio_comun") -> Camara:
    """Cámara pequeña tipo caja: 0.6×0.4×0.3 m, 1 bandeja, 1 kg manzana."""
    return Camara(
        geometria=GeometriaCamara(largo_m=0.6, ancho_m=0.4, alto_m=0.3),
        construccion=ConstruccionCamara(
            cubierta_translucida_id=cubierta_id,
            pared=ParedCamara(
                capas=[
                    CapaPared(
                        material_id="lana_vidrio_media", espesor_m=0.040, catalogo="aislantes"
                    ),
                ]
            ),
        ),
        bandejas=ConfiguracionBandejas(
            n_bandejas=1,
            area_bandeja_m2=0.20,
            espesor_capa_m=0.01,
            separacion_entre_bandejas_m=0.15,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.005),  # convección natural baja
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=1.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
    )


def _proyecto_caja(*, camara: Camara | None) -> Proyecto:
    p = Proyecto(
        meta=Meta(nombre="Caja test", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.CAJA,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.camara = camara
    return p


# ---------------------------------------------------------------------------
# Coherencia
# ---------------------------------------------------------------------------


class TestCoherenciaCaja:

    def test_caja_con_camara_translucida_sin_errores(self):
        p = _proyecto_caja(camara=_camara_caja(cubierta_id="vidrio_comun"))
        errores = verificar_coherencia_proyecto(p)
        # No debería haber errores de tipo CAJA (los relacionados con colector/motor/cubierta).
        assert not any("PROY_CAJA" in e for e in errores), errores

    def test_caja_con_camara_opaca_falla(self):
        p = _proyecto_caja(camara=_camara_caja(cubierta_id=None))
        errores = verificar_coherencia_proyecto(p)
        assert any("PROY_CAJA_SIN_CUBIERTA_TRANSLUCIDA" in e for e in errores), errores

    def test_caja_sin_camara_no_falla_por_cubierta(self):
        """Si no hay cámara, no se evalúa la regla de cubierta."""
        p = _proyecto_caja(camara=None)
        errores = verificar_coherencia_proyecto(p)
        assert not any("CUBIERTA" in e for e in errores)


# ---------------------------------------------------------------------------
# Smoke E2E: motor termodinámico con CAJA + cubierta translúcida
# ---------------------------------------------------------------------------


class TestMotorTDConCaja:

    def test_smoke_caja_termodinamico_con_radiacion(self):
        """CAJA con cubierta translúcida + I_g positiva durante el día debe
        ejecutar el motor termodinámico y aportar energía radiativa al producto."""
        camara = _camara_caja(cubierta_id="vidrio_comun")
        # T_op = T_amb (sin colector). Forzantes sintéticas con I_g pico 800 W/m².
        T_amb_K = 293.15  # 20 °C
        omega_amb = humedad_absoluta(0.40, T_amb_K)
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=T_amb_K,
            T_sal_col_amplitud_K=0.0,  # sin colector → T_ent constante a T_amb
            omega_amb=omega_amb,
            m_dot_aire_seco_kg_s=camara.flujo.caudal_masico_kg_s,
            T_amb_promedio_K=T_amb_K,
            T_amb_amplitud_K=5.0,
            I_g_max_W_m2=800.0,
            n_horas=24,
            n_dias=2,
        )

        res = calcular_camara(
            camara=camara,
            T_operacion_K=T_amb_K,
            HR_operacion=0.40,
            T_amb_K=T_amb_K,
            forzantes_aire=fz,
            t_max_s=2 * 24 * 3600.0,
        )
        assert isinstance(res, ResultadoMotorTermodinamico)
        # El motor debe correr (sin errores) y reportar Q_rad > 0 al mediodía.
        assert np.max(res.Q_rad_W) > 0.0
        # Energía radiativa acumulada debe ser positiva.
        assert res.energia_rad_total_J > 0.0
        # El producto debe haberse secado al menos parcialmente.
        assert res.X_prod_kg_kg[-1] < res.X_prod_kg_kg[0]

    def test_caja_sin_radiacion_no_seca(self):
        """CAJA con techo translúcido pero I_g=0 (noche perpetua, o caso patológico):
        T_ent = T_amb y sin Q_rad, no debería secar significativamente."""
        camara = _camara_caja(cubierta_id="vidrio_comun")
        T_amb_K = 293.15
        omega_amb = humedad_absoluta(0.40, T_amb_K)
        # Forzantes degeneradas: T_ent = T_amb, I_g = 0.
        fz = construir_serie_sintetica_dia_tipo(
            T_sal_col_promedio_K=T_amb_K,
            T_sal_col_amplitud_K=0.0,
            omega_amb=omega_amb,
            m_dot_aire_seco_kg_s=camara.flujo.caudal_masico_kg_s,
            T_amb_promedio_K=T_amb_K,
            T_amb_amplitud_K=0.0,
            I_g_max_W_m2=0.0,
            n_horas=24,
            n_dias=1,
        )

        res = calcular_camara(
            camara=camara,
            T_operacion_K=T_amb_K,
            HR_operacion=0.40,
            T_amb_K=T_amb_K,
            forzantes_aire=fz,
            t_max_s=24 * 3600.0,
        )
        # Sin aporte energético (T_ent=T_amb, I_g=0), Q_rad=0 todo el día.
        assert np.all(res.Q_rad_W == 0.0)
        assert res.energia_rad_total_J == 0.0
