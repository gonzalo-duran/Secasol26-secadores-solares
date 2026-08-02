"""Topología de transferencia de la cámara — cross-flow único (S64).

Reemplaza al módulo de S63, que cubría la binaria over-flow / through-flow. El
through-flow se retiró: en un secador pasivo el lecho pide un orden de magnitud
más de presión que el tiro disponible, y la dirección local del flujo no es un
dato que un usuario de prediseño pueda responder. Ver
``docs/notas/plan_crossflow_unico_camara.md``.

Lo que se fija acá:

- los snapshots con ``VERTICAL_ASCENDENTE`` **migran** en vez de fallar;
- el área de transferencia cuenta las **dos caras** de la bandeja, con la
  inferior gateada por el área abierta de la malla;
- la sección de la cámara y la del canal son distintas y cada una alimenta a
  quien corresponde (film de pared / film de producto);
- el diagnóstico de NTU describe la **cadena de N etapas** que integra el motor,
  no el CSTR.
"""

from __future__ import annotations

import math

import pytest

from calculos.camara_calc import (
    _FACTOR_CARA_INFERIOR,
    _N_ETAPAS_OVERFLOW,
    _construir_params_termodinamico,
    area_canal_entre_bandejas_m2,
    area_transferencia_producto_m2,
    area_transversal_flujo_m2,
    diagnostico_transferencia,
)
from calculos.lecho_producto import (
    AREA_ABIERTA_DEFAULT,
    D_P_DEFAULT_M,
    area_abierta_malla_efectiva,
    d_p_es_default,
    espesor_capa_derivado_m,
    masa_que_llena_el_lecho_kg,
    volumen_lecho_m3,
)
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    DireccionFlujo,
    GeometriaCamara,
)

_P = 89202.0  # Salta, ~1187 m


def _camara(
    direccion=DireccionFlujo.HORIZONTAL,
    *,
    area_bandeja_m2: float = 0.25,
    espesor_capa_m: float = 0.02,
    masa_kg: float = 9.5,
    n_bandejas: int = 10,
    d_p_m: float | None = None,
    tipo_malla: str | None = None,
) -> Camara:
    """Armario del caso de referencia: 0.5×0.5×1.1 m, 10 bandejas, manzana."""
    return Camara(
        geometria=GeometriaCamara(largo_m=0.5, ancho_m=0.5, alto_m=1.1),
        bandejas=ConfiguracionBandejas(
            n_bandejas=n_bandejas,
            area_bandeja_m2=area_bandeja_m2,
            espesor_capa_m=espesor_capa_m,
            separacion_entre_bandejas_m=0.07,
            diametro_eq_particula_m=d_p_m,
            tipo_malla=tipo_malla,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.0342, direccion_flujo=direccion),
        construccion=ConstruccionCamara(),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=masa_kg,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
        ),
    )


def _params(cam: Camara):
    return _construir_params_termodinamico(
        cam, T_operacion_K=325.0, HR_operacion=0.2, T_amb_K=290.0, P_Pa=_P
    )


# ---------------------------------------------------------------------------
# Migración de la topología retirada
# ---------------------------------------------------------------------------


class TestMigracionVertical:
    """``VERTICAL_ASCENDENTE`` sobrevive en el enum pero se coacciona."""

    def test_el_miembro_del_enum_sigue_existiendo(self):
        # Los .json guardados lo traen: tiene que deserializar antes de migrar.
        assert DireccionFlujo("VERTICAL_ASCENDENTE") is DireccionFlujo.VERTICAL_ASCENDENTE

    def test_construir_con_vertical_lo_coacciona_a_horizontal(self):
        f = ConfiguracionFlujo(
            caudal_masico_kg_s=0.03, direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE
        )
        assert f.direccion_flujo is DireccionFlujo.HORIZONTAL

    def test_una_camara_vertical_da_lo_mismo_que_una_horizontal(self):
        cam_v = _camara(DireccionFlujo.VERTICAL_ASCENDENTE)
        cam_h = _camara(DireccionFlujo.HORIZONTAL)
        assert _params(cam_v).A_prod_total_m2 == pytest.approx(_params(cam_h).A_prod_total_m2)
        assert _params(cam_v).h_conv_W_m2K == pytest.approx(_params(cam_h).h_conv_W_m2K)


# ---------------------------------------------------------------------------
# Área de transferencia: las dos caras de la bandeja
# ---------------------------------------------------------------------------


class TestAreaDosCaras:
    def test_area_es_la_superior_mas_la_inferior_gateada(self):
        cam = _camara(tipo_malla="alambre_grueso")
        f_ab = area_abierta_malla_efectiva("alambre_grueso")
        esperado = 10 * 0.25 * (1.0 + f_ab * _FACTOR_CARA_INFERIOR)
        assert area_transferencia_producto_m2(cam) == pytest.approx(esperado)

    def test_esta_entre_una_y_dos_veces_la_cara_superior(self):
        cam = _camara(tipo_malla="alambre_grueso")
        superior = 10 * 0.25
        assert superior < area_transferencia_producto_m2(cam) < 2.0 * superior

    def test_malla_mas_cerrada_transfiere_menos(self):
        abierta = _camara(tipo_malla="chapa_perforada_50pc")
        cerrada = _camara(tipo_malla="chapa_perforada_30pc")
        assert area_transferencia_producto_m2(cerrada) < area_transferencia_producto_m2(abierta)

    def test_sin_malla_declarada_usa_el_default(self):
        cam = _camara(tipo_malla=None)
        esperado = 10 * 0.25 * (1.0 + AREA_ABIERTA_DEFAULT * _FACTOR_CARA_INFERIOR)
        assert area_transferencia_producto_m2(cam) == pytest.approx(esperado)

    def test_malla_desconocida_cae_al_default(self):
        assert area_abierta_malla_efectiva("no_existe") == AREA_ABIERTA_DEFAULT

    def test_el_area_llega_a_los_params_del_motor(self):
        cam = _camara(tipo_malla="alambre_grueso")
        assert _params(cam).A_prod_total_m2 == pytest.approx(area_transferencia_producto_m2(cam))


# ---------------------------------------------------------------------------
# Secciones de paso
# ---------------------------------------------------------------------------


class TestSecciones:
    def test_seccion_de_camara_es_ancho_por_alto(self):
        cam = _camara()
        assert area_transversal_flujo_m2(cam) == pytest.approx(0.5 * 1.1)

    def test_la_seccion_del_canal_es_menor_que_la_de_camara(self):
        cam = _camara()
        assert area_canal_entre_bandejas_m2(cam) < area_transversal_flujo_m2(cam)

    def test_canal_es_ancho_por_libre_por_n_menos_uno(self):
        cam = _camara()
        # El espesor de capa se deriva de la carga (S64): hay que leerlo, no
        # suponer el que declaró la fixture.
        libre = 0.07 - cam.bandejas.espesor_capa_m
        assert area_canal_entre_bandejas_m2(cam) == pytest.approx(0.5 * libre * 9)

    def test_una_sola_bandeja_no_tiene_canales(self):
        # Sin canales el aire ve la cámara entera: es el fallback del helper.
        cam = _camara(n_bandejas=1, masa_kg=4.0)
        assert area_canal_entre_bandejas_m2(cam) == pytest.approx(area_transversal_flujo_m2(cam))

    def test_la_capa_no_puede_llenar_la_separacion(self):
        # El otro camino al fallback (espacio libre nulo) es inalcanzable: la
        # dataclass rechaza que la capa iguale o supere la separación.
        with pytest.raises(ValueError, match="BAND_SEPARACION_INSUFICIENTE"):
            _camara(espesor_capa_m=0.07)


# ---------------------------------------------------------------------------
# Geometría del lecho que sobrevive
# ---------------------------------------------------------------------------


class TestGeometriaLecho:
    def test_volumen_de_lecho(self):
        cam = _camara()
        e = cam.bandejas.espesor_capa_m
        assert volumen_lecho_m3(cam.bandejas) == pytest.approx(10 * 0.25 * e)

    def test_d_p_del_catalogo_no_es_default(self):
        cam = _camara()
        assert d_p_es_default(cam.bandejas, "manzana") is False

    def test_d_p_explicito_gana_al_catalogo(self):
        cam = _camara(d_p_m=0.02)
        assert d_p_es_default(cam.bandejas, "manzana") is False

    def test_sin_producto_ni_valor_explicito_es_default(self):
        cam = _camara()
        assert d_p_es_default(cam.bandejas, None) is True
        assert D_P_DEFAULT_M > 0.0

    def test_la_masa_del_lecho_cierra_con_la_carga_declarada(self):
        """Con el espesor derivado (S64) la relación cierra por construcción.

        Es la comprobación fuerte de la restricción de carga uniforme: el lecho
        que ve el modelo es exactamente el que hay adentro de la cámara.
        """
        cam = _camara(masa_kg=9.5)
        m = masa_que_llena_el_lecho_kg(cam.bandejas, 840.0, "manzana")
        assert m == pytest.approx(9.5)

    def test_espesor_derivado_es_la_inversa_de_la_masa(self):
        cam = _camara()
        m = masa_que_llena_el_lecho_kg(cam.bandejas, 840.0, "manzana")
        e = espesor_capa_derivado_m(m, 0.25, 10, 840.0, 0.45)
        assert e == pytest.approx(cam.bandejas.espesor_capa_m)

    def test_espesor_derivado_degenerado_es_cero(self):
        assert espesor_capa_derivado_m(10.0, 0.0, 10, 840.0, 0.45) == 0.0
        assert espesor_capa_derivado_m(0.0, 0.25, 10, 840.0, 0.45) == 0.0


# ---------------------------------------------------------------------------
# Diagnóstico de NTU
# ---------------------------------------------------------------------------


class TestDiagnostico:
    def _diag(self, cam):
        return diagnostico_transferencia(
            cam, T_operacion_K=325.0, HR_operacion=0.2, T_amb_K=290.0, P_Pa=_P
        )

    def test_el_acercamiento_usa_la_cadena_no_el_cstr(self):
        d = self._diag(_camara())
        cstr = d.NTU / (1.0 + d.NTU)
        cadena = 1.0 - (1.0 + d.NTU / _N_ETAPAS_OVERFLOW) ** (-_N_ETAPAS_OVERFLOW)
        assert d.acercamiento_equilibrio == pytest.approx(cadena)
        assert d.acercamiento_equilibrio > cstr

    def test_el_acercamiento_esta_acotado_por_el_piston(self):
        d = self._diag(_camara())
        assert d.acercamiento_equilibrio < 1.0 - math.exp(-d.NTU)

    def test_mas_area_da_mas_ntu(self):
        pocas = self._diag(_camara(n_bandejas=4))
        muchas = self._diag(_camara(n_bandejas=12))
        assert muchas.NTU > pocas.NTU

    def test_el_area_del_diagnostico_es_la_de_dos_caras(self):
        cam = _camara(tipo_malla="alambre_grueso")
        assert self._diag(cam).A_prod_m2 == pytest.approx(area_transferencia_producto_m2(cam))
