"""Tests de la pérdida conductiva del techo translúcido (mejora 33).

El techo translúcido deja de modelarse sólo como ganancia radiativa (Q_rad):
ahora su conducción (vidriado) entra al balance de la cámara como
``UA_techo = A_techo / (1/h_conv + espesor/k_efectivo + 1/h_w)``. La cara del
techo se descuenta de la envolvente opaca para no doble-contar (ver
``camara_calc._construir_params_termodinamico``).
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.camara_termodinamica import resolver_estado_camara
from calculos.psicrometria import humedad_absoluta
from core.camara import ConstruccionCamara


def _kwargs_base(**overrides):
    base = dict(
        T_prod_K=313.15,
        X_prod_kg_kg=2.0,
        T_ent_K=323.15,
        omega_ent_kg_kg=humedad_absoluta(0.20, 323.15),
        A_prod_m2=2.5,
        A_cuerpo_m2=8.0,
        m_dot_as_kg_s=0.030,
        h_conv_W_m2K=15.0,
        K_m_kg_m2s=0.015,
        h_w_W_m2K=15.0,
        k_aisl_W_mK=0.02679,
        esp_cam_m=0.05,
        T_amb_K=298.15,
        P_Pa=101325.0,
        aw_func=lambda X: 0.85,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Modelo de datos: validación y default
# ---------------------------------------------------------------------------


class TestConstruccionEspesorTecho:

    def test_espesor_negativo_falla(self):
        with pytest.raises(ValueError, match="CONS_ESPESOR_CUBIERTA_NO_POSITIVO"):
            ConstruccionCamara(
                cubierta_translucida_id="vidrio_comun",
                cubierta_translucida_espesor_m=-0.004,
            )

    def test_espesor_cero_falla(self):
        with pytest.raises(ValueError, match="CONS_ESPESOR_CUBIERTA_NO_POSITIVO"):
            ConstruccionCamara(
                cubierta_translucida_id="vidrio_comun",
                cubierta_translucida_espesor_m=0.0,
            )

    def test_default_none_valido(self):
        cons = ConstruccionCamara(cubierta_translucida_id="policarbonato_alveolar")
        assert cons.cubierta_translucida_espesor_m is None

    def test_espesor_valido_se_guarda(self):
        cons = ConstruccionCamara(
            cubierta_translucida_id="policarbonato_alveolar",
            cubierta_translucida_espesor_m=0.010,
        )
        assert cons.cubierta_translucida_espesor_m == 0.010


# ---------------------------------------------------------------------------
# Física: la pérdida del techo baja T_flujo
# ---------------------------------------------------------------------------


class TestUATechoEnBalance:

    def test_techo_default_cero_no_cambia_nada(self):
        """A_techo=0 (defaults) → idéntico al comportamiento histórico."""
        base = resolver_estado_camara(**_kwargs_base())
        con_defaults = resolver_estado_camara(
            **_kwargs_base(R_cond_techo_m2K_W=0.0, A_techo_m2=0.0)
        )
        assert con_defaults.T_flujo_K == pytest.approx(base.T_flujo_K, rel=1e-12)

    def test_techo_translucido_baja_T_flujo(self):
        """Con T_flujo > T_amb, agregar pérdida por el techo enfría el aire."""
        sin_techo = resolver_estado_camara(**_kwargs_base())
        con_techo = resolver_estado_camara(
            **_kwargs_base(R_cond_techo_m2K_W=0.006 / 0.06, A_techo_m2=2.0)
        )
        assert con_techo.T_flujo_K < sin_techo.T_flujo_K

    def test_vidriado_mas_grueso_pierde_menos(self):
        """Mayor espesor → mayor R_cond → menor U_techo → menos pérdida → más caliente."""
        fino = resolver_estado_camara(
            **_kwargs_base(R_cond_techo_m2K_W=0.004 / 0.05, A_techo_m2=2.0)
        )
        grueso = resolver_estado_camara(
            **_kwargs_base(R_cond_techo_m2K_W=0.016 / 0.08, A_techo_m2=2.0)
        )
        assert grueso.T_flujo_K > fino.T_flujo_K

    def test_q_pared_diagnostico_no_incluye_techo(self):
        """q_pared (reconstrucción de nodos opacos) no se ve alterado por el techo."""
        sin_techo = resolver_estado_camara(**_kwargs_base())
        con_techo = resolver_estado_camara(
            **_kwargs_base(R_cond_techo_m2K_W=0.006 / 0.06, A_techo_m2=2.0)
        )
        # q_pared = UA_c·(T_flujo - T_amb); cambia sólo por el T_flujo levemente
        # distinto, no por sumar el área del techo (que se descontó de A_cuerpo).
        assert con_techo.q_pared_W < sin_techo.q_pared_W  # T_flujo menor → menos flujo


# ---------------------------------------------------------------------------
# End-to-end: el espesor del techo cambia el resultado de calcular_camara
# ---------------------------------------------------------------------------


def _camara_caja(espesor_mm: float):
    """Cámara CAJA translúcida (alveolar) con espesor de techo parametrizable."""
    from core.camara import (
        Camara,
        CapaPared,
        CargaProducto,
        ConfiguracionBandejas,
        ConfiguracionFlujo,
        GeometriaCamara,
        ParedCamara,
    )

    return Camara(
        geometria=GeometriaCamara(largo_m=0.6, ancho_m=0.4, alto_m=0.3),
        construccion=ConstruccionCamara(
            cubierta_translucida_id="policarbonato_alveolar",
            cubierta_translucida_espesor_m=espesor_mm / 1000.0,
            pared=ParedCamara(
                capas=[
                    CapaPared(material_id="lana_vidrio_media", espesor_m=0.04, catalogo="aislantes")
                ]
            ),
        ),
        bandejas=ConfiguracionBandejas(
            n_bandejas=1,
            area_bandeja_m2=0.20,
            espesor_capa_m=0.01,
            separacion_entre_bandejas_m=0.15,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.005),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=1.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
    )


class TestEspesorTechoEndToEnd:

    def test_espesor_cambia_T_flujo(self):
        from calculos.camara_calc import calcular_camara

        def media(esp_mm):
            r = calcular_camara(
                _camara_caja(esp_mm),
                T_operacion_K=323.15,
                HR_operacion=0.3,
                T_amb_K=298.15,
                t_max_s=6 * 3600,
            )
            return float(np.nanmean(r.T_flujo_K))

        t_fino = media(4)
        t_grueso = media(16)
        # Direccional: vidriado grueso aísla más → aire algo más caliente.
        assert t_grueso > t_fino
