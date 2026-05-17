"""Tests del modelo de datos de la cámara de secado (core/camara.py).

Cubre:
    - GeometriaCamara: errores duros de dimensiones y volumen
    - ConfiguracionBandejas: errores duros de separación, espesor, área
    - ConfiguracionFlujo: errores duros de caudal, recirculación, dirección
    - CargaProducto: errores duros de masas y humedades
    - Camara.__post_init__: validación de producto en catálogo, modelos, coherencia
    - advertencias_camara: advertencias de diseño (no bloqueantes)
"""

from __future__ import annotations

import pytest

from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    DireccionFlujo,
    GeometriaCamara,
    ParedCamara,
    advertencias_camara,
)
from core.advertencias import Severidad


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def camara_minima():
    """Camara con configuración válida mínima (manzana, modelo logaritmico)."""
    return Camara()


@pytest.fixture
def camara_yacon():
    """Camara con yacón (tiene GAB y modelos page + midilli)."""
    return Camara(
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=5.0,
            humedad_inicial_X=9.0,
            humedad_objetivo_X=0.20,
            modelo_capa_fina="page",
            modelo_isoterma="gab",
        )
    )


# ---------------------------------------------------------------------------
# GeometriaCamara
# ---------------------------------------------------------------------------


class TestGeometriaCamara:

    def test_instancia_valida(self):
        geo = GeometriaCamara(largo_m=1.0, ancho_m=0.8, alto_m=1.5)
        assert geo.largo_m == 1.0

    def test_dimensiones_no_positivas_largo(self):
        with pytest.raises(ValueError, match="GEO_DIMENSIONES_NO_POSITIVAS"):
            GeometriaCamara(largo_m=0.0, ancho_m=0.8, alto_m=1.0)

    def test_dimensiones_no_positivas_alto(self):
        with pytest.raises(ValueError, match="GEO_DIMENSIONES_NO_POSITIVAS"):
            GeometriaCamara(largo_m=1.0, ancho_m=0.8, alto_m=-0.1)

    def test_volumen_minimo(self):
        with pytest.raises(ValueError, match="GEO_VOLUMEN_MINIMO"):
            GeometriaCamara(largo_m=0.1, ancho_m=0.1, alto_m=0.5)  # vol=0.005 m³

    def test_volumen_exactamente_en_limite(self):
        # 0.2 * 0.5 * 0.1 = 0.01 m³ — exactamente en el límite, debe pasar
        geo = GeometriaCamara(largo_m=0.2, ancho_m=0.5, alto_m=0.1)
        assert pytest.approx(geo.largo_m * geo.ancho_m * geo.alto_m, abs=1e-10) == 0.01


# ---------------------------------------------------------------------------
# ConfiguracionBandejas
# ---------------------------------------------------------------------------


class TestConfiguracionBandejas:

    def test_instancia_valida(self):
        b = ConfiguracionBandejas(
            n_bandejas=3, area_bandeja_m2=0.5, espesor_capa_m=0.02,
            separacion_entre_bandejas_m=0.10,
        )
        assert b.n_bandejas == 3

    def test_n_bandejas_cero(self):
        with pytest.raises(ValueError, match="BAND_N_BANDEJAS_NO_POSITIVO"):
            ConfiguracionBandejas(n_bandejas=0)

    def test_espesor_no_positivo(self):
        with pytest.raises(ValueError, match="BAND_ESPESOR_NO_POSITIVO"):
            ConfiguracionBandejas(espesor_capa_m=0.0)

    def test_separacion_insuficiente(self):
        # sep=0.025 m < espesor=0.02 m + 0.01 m = 0.03 m
        with pytest.raises(ValueError, match="BAND_SEPARACION_INSUFICIENTE"):
            ConfiguracionBandejas(espesor_capa_m=0.02, separacion_entre_bandejas_m=0.025)

    def test_separacion_exactamente_suficiente(self):
        # sep = espesor + 0.01 = 0.03 m — exactamente en el límite, debe pasar
        b = ConfiguracionBandejas(espesor_capa_m=0.02, separacion_entre_bandejas_m=0.030)
        assert b.separacion_entre_bandejas_m == pytest.approx(0.030)

    def test_area_no_positiva(self):
        with pytest.raises(ValueError, match="BAND_AREA_NO_POSITIVA"):
            ConfiguracionBandejas(area_bandeja_m2=0.0)


# ---------------------------------------------------------------------------
# ConfiguracionFlujo
# ---------------------------------------------------------------------------


class TestConfiguracionFlujo:

    def test_instancia_valida(self):
        f = ConfiguracionFlujo(caudal_masico_kg_s=0.05)
        assert f.caudal_masico_kg_s == 0.05

    def test_caudal_no_positivo(self):
        with pytest.raises(ValueError, match="FLUJO_CAUDAL_NO_POSITIVO"):
            ConfiguracionFlujo(caudal_masico_kg_s=0.0)

    def test_recirculacion_no_implementada(self):
        with pytest.raises(NotImplementedError, match="FLUJO_RECIRCULACION_NO_IMPLEMENTADA"):
            ConfiguracionFlujo(fraccion_recirculacion=0.1)

    def test_HR_fuera_de_rango(self):
        with pytest.raises(ValueError, match="FLUJO_HR_ENTRADA_INVALIDA"):
            ConfiguracionFlujo(HR_entrada_fraccion=1.1)

    def test_HR_valida(self):
        f = ConfiguracionFlujo(HR_entrada_fraccion=0.30)
        assert f.HR_entrada_fraccion == pytest.approx(0.30)

    def test_HR_none_valido(self):
        f = ConfiguracionFlujo(HR_entrada_fraccion=None)
        assert f.HR_entrada_fraccion is None


# ---------------------------------------------------------------------------
# CargaProducto
# ---------------------------------------------------------------------------


class TestCargaProducto:

    def test_instancia_valida(self):
        p = CargaProducto(masa_total_kg=10.0, humedad_inicial_X=4.6, humedad_objetivo_X=0.15)
        assert p.masa_total_kg == 10.0

    def test_masa_no_positiva(self):
        with pytest.raises(ValueError, match="PROD_MASA_NO_POSITIVA"):
            CargaProducto(masa_total_kg=0.0)

    def test_humedad_inicial_negativa(self):
        with pytest.raises(ValueError, match="PROD_HUMEDAD_INICIAL_NEGATIVA"):
            CargaProducto(humedad_inicial_X=-0.1)

    def test_humedad_objetivo_negativa(self):
        with pytest.raises(ValueError, match="PROD_HUMEDAD_OBJETIVO_NEGATIVA"):
            CargaProducto(humedad_objetivo_X=-0.01)

    def test_humedad_objetivo_mayor_inicial(self):
        with pytest.raises(ValueError, match="PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL"):
            CargaProducto(humedad_inicial_X=4.0, humedad_objetivo_X=4.5)

    def test_humedad_objetivo_igual_inicial(self):
        with pytest.raises(ValueError, match="PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL"):
            CargaProducto(humedad_inicial_X=4.0, humedad_objetivo_X=4.0)


# ---------------------------------------------------------------------------
# Camara — validación de producto
# ---------------------------------------------------------------------------


class TestCamaraValidacionProducto:

    def test_producto_inexistente(self):
        with pytest.raises(ValueError, match="PROD_ID_NO_ENCONTRADO"):
            Camara(carga_producto=CargaProducto(producto_id="producto_imaginario_xyz"))

    def test_modelo_cf_sin_params(self):
        # durazno no tiene parámetros de capa fina en v1
        with pytest.raises(ValueError, match="MOD_CAPA_FINA_NO_DISPONIBLE"):
            Camara(
                carga_producto=CargaProducto(
                    producto_id="durazno",
                    humedad_inicial_X=6.3,
                    modelo_capa_fina="page",
                )
            )

    def test_manzana_logaritmico_valido(self, camara_minima):
        assert camara_minima.carga_producto.producto_id == "manzana"
        assert camara_minima.carga_producto.modelo_capa_fina == "logaritmico"

    def test_yacon_page_valido(self, camara_yacon):
        assert camara_yacon.carga_producto.producto_id == "yacon"

    def test_manzana_page_valido(self):
        camara = Camara(
            carga_producto=CargaProducto(
                producto_id="manzana",
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="page",
            )
        )
        assert camara.carga_producto.modelo_capa_fina == "page"


# ---------------------------------------------------------------------------
# Camara — coherencia cruzada
# ---------------------------------------------------------------------------


class TestCamaraCoherencia:

    def test_bandejas_no_caben_en_camara(self):
        # 10 bandejas × 0.20 m = 2.0 m > alto_m = 1.5 m
        with pytest.raises(ValueError, match="COHE_BANDEJAS_NO_CABEN_EN_CAMARA"):
            Camara(
                geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.5),
                bandejas=ConfiguracionBandejas(
                    n_bandejas=10,
                    area_bandeja_m2=0.5,
                    espesor_capa_m=0.02,
                    separacion_entre_bandejas_m=0.20,
                ),
            )

    def test_area_bandeja_excede_camara(self):
        # area_bandeja=2.0 > largo*ancho=1.2*0.8=0.96 m²
        with pytest.raises(ValueError, match="COHE_AREA_BANDEJA_EXCEDE_CAMARA"):
            Camara(
                geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=2.0),
                bandejas=ConfiguracionBandejas(
                    n_bandejas=3,
                    area_bandeja_m2=2.0,
                    espesor_capa_m=0.02,
                    separacion_entre_bandejas_m=0.15,
                ),
            )

    def test_carga_excede_capacidad_geometrica(self):
        # masa=500 kg / 5 bandejas / 0.5 m² = 200 kg/m² >> 20 kg/m²
        with pytest.raises(ValueError, match="COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA"):
            Camara(
                carga_producto=CargaProducto(
                    masa_total_kg=500.0,
                    humedad_inicial_X=4.6,
                    humedad_objetivo_X=0.15,
                )
            )

    def test_camara_valida_no_lanza(self, camara_minima):
        assert camara_minima is not None


# ---------------------------------------------------------------------------
# advertencias_camara
# ---------------------------------------------------------------------------


class TestAdvertenciasCamara:

    def test_sin_advertencias_diseno_correcto(self):
        # caudal = 0.9 kg/s → v_sup = (0.9/1.1)/(1.0*1.5) = 0.55 m/s (dentro del rango)
        camara = Camara(
            geometria=GeometriaCamara(largo_m=1.5, ancho_m=1.0, alto_m=1.5),
            construccion=ConstruccionCamara(
                cubierta_translucida_id=None,
                pared=ParedCamara(capas=[
                    CapaPared(material_id="lana_vidrio_media", espesor_m=0.080, catalogo="aislantes"),
                ]),
            ),
            bandejas=ConfiguracionBandejas(
                n_bandejas=5, area_bandeja_m2=0.5,
                espesor_capa_m=0.02, separacion_entre_bandejas_m=0.15,
            ),
            flujo=ConfiguracionFlujo(
                caudal_masico_kg_s=0.9,
                HR_entrada_fraccion=0.20,
            ),
            carga_producto=CargaProducto(
                producto_id="manzana",
                masa_total_kg=10.0,
                humedad_inicial_X=4.6,
                humedad_objetivo_X=0.15,
                modelo_capa_fina="logaritmico",
            ),
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        # Solo debe aparecer el fallback de isoterma (manzana no tiene GAB)
        assert "GEO_RELACION_ASPECTO_EXTREMA" not in codigos
        assert "FLUJO_VELOCIDAD_SUPERFICIAL_BAJA" not in codigos

    @pytest.mark.xfail(
        reason="Todos los productos del catálogo con capa fina calibrada ahora "
               "también tienen GAB cargado. Para reactivar este test, instanciar "
               "una Camara con un producto que tenga capa fina pero NO GAB — "
               "ningún producto cumple esa condición hoy. La rama PROD_ISOTERMA_"
               "FALLBACK del código sigue existiendo y se ejercita en producción "
               "cuando un usuario carga manualmente un producto sin GAB.",
        strict=True,
    )
    def test_advertencia_isoterma_fallback_sin_gab(self):
        """Producto sin GAB calibrado debe emitir PROD_ISOTERMA_FALLBACK CRITICAL.
        Tomate sirve conceptualmente (no tiene GAB) pero su capa fina tampoco
        está calibrada → instanciar Camara levanta MOD_CAPA_FINA_NO_DISPONIBLE
        antes de poder llamar advertencias_camara."""
        camara = Camara(
            carga_producto=CargaProducto(
                producto_id="tomate",
                masa_total_kg=3.0,
                humedad_inicial_X=12.0,
                humedad_objetivo_X=0.10,
            ),
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "PROD_ISOTERMA_FALLBACK" in codigos
        fallback_adv = next(a for a in adv if a.codigo == "PROD_ISOTERMA_FALLBACK")
        assert fallback_adv.severidad == Severidad.CRITICAL

    def test_advertencia_relacion_aspecto_extrema(self):
        camara = Camara(
            geometria=GeometriaCamara(largo_m=5.0, ancho_m=0.3, alto_m=1.5),  # ratio=16.7
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "GEO_RELACION_ASPECTO_EXTREMA" in codigos

    def test_advertencia_alto_inusual(self):
        # alto=0.2 m < 0.3 m
        camara = Camara(
            geometria=GeometriaCamara(largo_m=1.5, ancho_m=1.0, alto_m=0.20),
            bandejas=ConfiguracionBandejas(
                n_bandejas=1,
                area_bandeja_m2=0.5,
                espesor_capa_m=0.02,
                separacion_entre_bandejas_m=0.03,
            ),
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "GEO_ALTO_INUSUAL" in codigos

    def test_advertencia_espesor_capa_grande(self):
        camara = Camara(
            bandejas=ConfiguracionBandejas(
                n_bandejas=3,
                area_bandeja_m2=0.5,
                espesor_capa_m=0.08,  # > 0.05 m
                separacion_entre_bandejas_m=0.10,
            ),
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "BAND_ESPESOR_CAPA_GRANDE" in codigos

    def test_advertencia_malla_sin_especificar(self, camara_minima):
        adv = advertencias_camara(camara_minima)
        codigos = [a.codigo for a in adv]
        assert "BAND_MALLA_SIN_ESPECIFICAR" in codigos

    def test_advertencia_velocidad_superficial_baja(self):
        # caudal muy bajo → v_sup muy baja
        camara = Camara(
            flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.001),
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "FLUJO_VELOCIDAD_SUPERFICIAL_BAJA" in codigos

    def test_advertencia_HR_entrada_no_especificada(self, camara_minima):
        # El default de ConfiguracionFlujo tiene HR_entrada=None
        adv = advertencias_camara(camara_minima)
        codigos = [a.codigo for a in adv]
        assert "FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA" in codigos

    def test_no_advertencia_HR_entrada_especificada(self):
        camara = Camara(
            flujo=ConfiguracionFlujo(
                caudal_masico_kg_s=0.05, HR_entrada_fraccion=0.20
            )
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA" not in codigos

    @pytest.mark.xfail(
        reason="charqui_vacuno no tiene parámetros de capa fina en el catálogo v1. "
               "Habilitar cuando se carguen los coeficientes cinéticos.",
        strict=True,
    )
    def test_advertencia_inio_carne_sin_isoterma(self):
        # Este test falla porque charqui_vacuno no tiene capa_fina params → MOD_CAPA_FINA_NO_DISPONIBLE
        # antes de poder instanciar Camara y llamar advertencias_camara().
        # Cuando se carguen los coeficientes, el test debe pasar directamente.
        camara = Camara(
            carga_producto=CargaProducto(
                producto_id="charqui_vacuno",
                masa_total_kg=5.0,
                humedad_inicial_X=3.0,
                humedad_objetivo_X=0.30,
                modelo_capa_fina="page",
            )
        )
        adv = advertencias_camara(camara)
        codigos = [a.codigo for a in adv]
        assert "INIO_PRODUCTO_CARNE_SIN_ISOTERMA" in codigos

    def test_yacon_tiene_gab_no_genera_fallback(self, camara_yacon):
        adv = advertencias_camara(camara_yacon)
        codigos = [a.codigo for a in adv]
        assert "PROD_ISOTERMA_FALLBACK" not in codigos


# ===========================================================================
# Tests S4a — campos nuevos del motor termodinámico
# ===========================================================================


class TestCamaraModoCalculo:
    """Validación del nuevo campo `modo_calculo` en Camara."""

    def test_default_es_capa_fina(self):
        cam = Camara()
        assert cam.modo_calculo == "capa_fina"

    def test_termodinamico_valido(self):
        cam = Camara(modo_calculo="termodinamico")
        assert cam.modo_calculo == "termodinamico"

    def test_modo_invalido_lanza(self):
        with pytest.raises(ValueError, match="CAM_MODO_INVALIDO"):
            Camara(modo_calculo="otro_modo")

    def test_modo_string_vacio_lanza(self):
        with pytest.raises(ValueError, match="CAM_MODO_INVALIDO"):
            Camara(modo_calculo="")


class TestCargaProductoTInicial:
    """Validación del nuevo campo `T_prod_inicial_K` en CargaProducto."""

    def test_default_es_none(self):
        p = CargaProducto()
        assert p.T_prod_inicial_K is None

    def test_valor_razonable_pasa(self):
        p = CargaProducto(T_prod_inicial_K=298.15)   # 25 °C
        assert p.T_prod_inicial_K == 298.15

    def test_refrigerado_pasa(self):
        p = CargaProducto(T_prod_inicial_K=278.15)   # 5 °C
        assert p.T_prod_inicial_K == 278.15

    def test_demasiado_frio_lanza(self):
        with pytest.raises(ValueError, match="PROD_T_INICIAL_FUERA_RANGO"):
            CargaProducto(T_prod_inicial_K=253.15)   # −20 °C

    def test_demasiado_caliente_lanza(self):
        with pytest.raises(ValueError, match="PROD_T_INICIAL_FUERA_RANGO"):
            CargaProducto(T_prod_inicial_K=373.15)   # 100 °C
