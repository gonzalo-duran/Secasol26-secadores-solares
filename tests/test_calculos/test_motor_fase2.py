"""Tests de Fase 2 del refactor de motor:

- Haaland con rugosidad real del catálogo de placas.
- K_malla configurable por tipo_malla.
- Presión dinámica de salida del ventilador.
- ΔP por tipo de colector (1/2/3/4) con canales correctos.
"""

from __future__ import annotations

import pytest

from calculos.motor_calc import (
    K_MALLA,
    K_TRANSICION_LECHO,
    TIPOS_MALLA,
    _factor_friccion_haaland,
    _K_malla_efectivo,
    _K_rugosidad_default,
    densidad_aire,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
)
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    DireccionFlujo,
    GeometriaCamara,
)
from core.colector import (
    BancoColectores,
    Colector,
    ColectorUnidad,
)
from core.motor import Motor

# ---------------------------------------------------------------------------
# F2.1 — Haaland con rugosidad
# ---------------------------------------------------------------------------


class TestHaalandRugosidad:

    def test_haaland_laminar_es_64_sobre_Re(self):
        """En régimen laminar (Re < 2300), f = 64/Re — independiente de rugosidad."""
        assert _factor_friccion_haaland(Re=1000.0, eps_rel=0.001) == pytest.approx(64.0 / 1000.0)

    def test_haaland_turbulento_crece_con_rugosidad(self):
        """A Re fijo en turbulento, ε mayor → f mayor."""
        f_liso = _factor_friccion_haaland(Re=50_000.0, eps_rel=1e-6)
        f_rugoso = _factor_friccion_haaland(Re=50_000.0, eps_rel=0.01)
        assert f_rugoso > f_liso

    def test_haaland_turbulento_decrece_con_Re_a_eps_fijo(self):
        """A ε fijo, mayor Re → menor f en zona de transición turbulenta."""
        f_bajo_Re = _factor_friccion_haaland(Re=10_000.0, eps_rel=1e-4)
        f_alto_Re = _factor_friccion_haaland(Re=1_000_000.0, eps_rel=1e-4)
        assert f_alto_Re < f_bajo_Re

    def test_colector_con_rugosidad_mayor_da_dP_mayor(self):
        """Colector con placa de mayor rugosidad → ΔP mayor."""

        # Mismo geom, distinto material de placa
        def _make(placa_id):
            return Colector(
                unidad=ColectorUnidad(
                    largo_m=2.0,
                    ancho_m=1.0,
                    espaciado_m=0.04,
                    espesor_placa_m=0.001,
                    espesor_cubierta_m=0.004,
                    espesor_aislante_m=0.05,
                    espesor_fondo_m=0.001,
                    velocidad_diseno_ms=2.0,
                    id_cubierta="vidrio_comun",
                    id_placa=placa_id,
                    id_aislante="lana_vidrio_media",
                    id_fondo="galvanizada_sin_pintura",
                ),
                banco=BancoColectores(n_serie=1, n_paralelo=1),
            )

        dP_liso = estimar_delta_P_colector(_make("aluminio_tinox"))  # ε ≈ 2e-5
        dP_rugoso = estimar_delta_P_colector(_make("galvanizada_cruda"))  # ε ≈ 1e-4
        assert dP_rugoso > dP_liso


# ---------------------------------------------------------------------------
# F2.2 — K_malla configurable
# ---------------------------------------------------------------------------


class TestKMallaConfigurable:

    def test_lookup_tipos_estandar(self):
        for tipo, K_esp in TIPOS_MALLA.items():
            assert _K_malla_efectivo(tipo) == K_esp

    def test_fallback_a_default_si_none_o_desconocido(self):
        assert _K_malla_efectivo(None) == K_MALLA
        assert _K_malla_efectivo("tipo_inexistente") == K_MALLA

    def test_dP_camara_responde_al_tipo_malla(self):
        """Misma cámara, distinto tipo_malla → distinto ΔP."""
        from calculos.motor_calc import densidad_aire

        rho = densidad_aire(323.15, 101325.0)

        def _cam(tipo_m):
            return Camara(
                geometria=GeometriaCamara(largo_m=1.0, ancho_m=1.0, alto_m=1.0),
                bandejas=ConfiguracionBandejas(
                    n_bandejas=3,
                    area_bandeja_m2=0.5,
                    espesor_capa_m=0.02,
                    separacion_entre_bandejas_m=0.15,
                    tipo_malla=tipo_m,
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

        dP_grueso = estimar_delta_P_camara(_cam("alambre_grueso"))  # K=1.0
        dP_perf30 = estimar_delta_P_camara(_cam("chapa_perforada_30pc"))  # K=8.0
        # La chapa perforada cerrada debe pesar mucho más que el alambre grueso
        assert dP_perf30 > dP_grueso


# ---------------------------------------------------------------------------
# F2.3 — Presión dinámica de salida
# ---------------------------------------------------------------------------


class TestPresionDinamicaSalida:

    def test_v_descarga_none_no_aporta(self):
        m_sin = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
        )
        m_con_cero = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
            v_descarga_m_s=0.0,
        )
        assert m_sin.perdida_carga_total_Pa == m_con_cero.perdida_carga_total_Pa

    def test_v_descarga_positiva_suma_presion_dinamica(self):
        """A v=6 m/s, ρ≈1.09 → q_din ≈ 19.6 Pa."""
        m_sin = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
        )
        m_con = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0,
            delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
            v_descarga_m_s=6.0,
        )
        delta = m_con.perdida_carga_total_Pa - m_sin.perdida_carga_total_Pa
        # q_din teórica a 50 °C, 1 atm
        rho = 101325.0 / (287.058 * 323.15)
        q_din_teorica = rho * 36.0 / 2.0
        assert delta == pytest.approx(q_din_teorica, rel=1e-4)


# ---------------------------------------------------------------------------
# F2.4 — ΔP por tipo de colector
# ---------------------------------------------------------------------------


class TestDeltaPPorTipoColector:

    def _colector(self, tipo: int, espac_sup=0.04, espac_inf=0.02):
        """Helper: colector con tipo y espaciados configurables."""
        return Colector(
            unidad=ColectorUnidad(
                largo_m=2.0,
                ancho_m=1.0,
                espaciado_m=espac_sup,
                espaciado_inferior_m=espac_inf,
                espesor_placa_m=0.001,
                espesor_cubierta_m=0.004,
                espesor_aislante_m=0.05,
                espesor_fondo_m=0.001,
                velocidad_diseno_ms=2.0,
                tipo_colector=tipo,
                id_cubierta="vidrio_comun",
                id_placa="galvanizada_pintada_negro_mate",
                id_aislante="lana_vidrio_media",
                id_fondo="galvanizada_sin_pintura",
            ),
            banco=BancoColectores(n_serie=1, n_paralelo=1),
        )

    def test_tipo_3_usa_canal_inferior(self):
        """Tipo 3: canal inferior activo. ΔP debe ser MAYOR cuando ese canal
        es más angosto (espac_inf = 1 cm vs 4 cm). El canal superior (espac_m)
        no debería afectar."""
        col_inf_angosto = self._colector(tipo=3, espac_sup=0.04, espac_inf=0.01)
        col_inf_ancho = self._colector(tipo=3, espac_sup=0.04, espac_inf=0.04)
        dP_angosto = estimar_delta_P_colector(col_inf_angosto)
        dP_ancho = estimar_delta_P_colector(col_inf_ancho)
        assert dP_angosto > dP_ancho

    def test_tipo_4_usa_canal_superior(self):
        """Tipo 4: canal superior activo. ΔP responde a espac_sup."""
        col_sup_angosto = self._colector(tipo=4, espac_sup=0.01, espac_inf=0.04)
        col_sup_ancho = self._colector(tipo=4, espac_sup=0.04, espac_inf=0.04)
        dP_angosto = estimar_delta_P_colector(col_sup_angosto)
        dP_ancho = estimar_delta_P_colector(col_sup_ancho)
        assert dP_angosto > dP_ancho

    def test_tipo_2_toma_mayor_de_dos_canales(self):
        """Tipo 2: ambos canales. ΔP = max(ΔP_cs, ΔP_ci). Si los dos canales
        son distintos, el resultado debe coincidir con el más restrictivo."""
        col_2_simetrico = self._colector(tipo=2, espac_sup=0.04, espac_inf=0.04)
        col_2_ci_chico = self._colector(tipo=2, espac_sup=0.04, espac_inf=0.01)
        dP_sim = estimar_delta_P_colector(col_2_simetrico)
        dP_asim = estimar_delta_P_colector(col_2_ci_chico)
        # Asimétrico (canal inferior más chico) → ΔP del canal estrecho domina
        assert dP_asim > dP_sim


# ---------------------------------------------------------------------------
# K_rugosidad del producto y K_transicion del lecho
# ---------------------------------------------------------------------------


def _cam_horizontal(K_rug=None, espesor_capa=0.02, sep=0.10):
    """Cámara horizontal canónica para tests de K_rugosidad."""
    rho_est = 1.1
    return Camara(
        geometria=GeometriaCamara(largo_m=1.0, ancho_m=1.0, alto_m=1.0),
        bandejas=ConfiguracionBandejas(
            n_bandejas=5,
            area_bandeja_m2=0.5,
            espesor_capa_m=espesor_capa,
            separacion_entre_bandejas_m=sep,
            tipo_malla="alambre_grueso",
            K_rugosidad_producto=K_rug,
        ),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=rho_est * 0.1,
            direccion_flujo=DireccionFlujo.HORIZONTAL,
        ),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
    )


def _cam_vertical(caudal_kg_s=0.1):
    rho_est = 1.1
    return Camara(
        geometria=GeometriaCamara(largo_m=1.0, ancho_m=1.0, alto_m=1.0),
        bandejas=ConfiguracionBandejas(
            n_bandejas=5,
            area_bandeja_m2=0.5,
            espesor_capa_m=0.02,
            separacion_entre_bandejas_m=0.15,
            tipo_malla="alambre_grueso",
        ),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=rho_est * caudal_kg_s,
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


class TestKRugosidadDefault:

    def test_ratio_bajo_satura_en_K_minimo(self):
        # Ratio = 0.001 / 0.5 = 0.002 << 0.05 → K = 0.2 (saturado)
        assert _K_rugosidad_default(d_p=0.001, espacio_libre=0.5) == pytest.approx(0.2)

    def test_ratio_alto_satura_en_K_maximo(self):
        # Ratio = 0.5 / 0.5 = 1.0 >> 0.50 → K = 2.0 (saturado)
        assert _K_rugosidad_default(d_p=0.5, espacio_libre=0.5) == pytest.approx(2.0)

    def test_ratio_en_punto_tabulado(self):
        # Ratio = 0.015 / 0.10 = 0.15 → exactamente K = 0.5 de la tabla
        assert _K_rugosidad_default(d_p=0.015, espacio_libre=0.10) == pytest.approx(0.5)

    def test_interpolacion_lineal_entre_puntos(self):
        # Ratio = 0.10 → entre 0.05 (K=0.2) y 0.15 (K=0.5), centro → K = 0.35
        K = _K_rugosidad_default(d_p=0.010, espacio_libre=0.10)
        assert K == pytest.approx(0.35, abs=1e-6)

    def test_d_p_o_espacio_no_positivo_devuelve_cero(self):
        assert _K_rugosidad_default(d_p=0.0, espacio_libre=0.1) == 0.0
        assert _K_rugosidad_default(d_p=0.01, espacio_libre=0.0) == 0.0


class TestKRugosidadEnCamara:

    def test_horizontal_K_rug_aumenta_dP(self):
        """Mayor K_rugosidad → mayor ΔP en HORIZONTAL, todo lo demás igual."""
        dP_bajo = estimar_delta_P_camara(_cam_horizontal(K_rug=0.0))
        dP_alto = estimar_delta_P_camara(_cam_horizontal(K_rug=2.0))
        assert dP_alto > dP_bajo

    def test_horizontal_auto_no_es_cero(self):
        """K_rug=None (auto) debe estimar K > 0 y por ende ΔP > caso K=0."""
        dP_cero = estimar_delta_P_camara(_cam_horizontal(K_rug=0.0))
        dP_auto = estimar_delta_P_camara(_cam_horizontal(K_rug=None))
        assert dP_auto > dP_cero

    def test_horizontal_override_es_respetado(self):
        """Override K_rug=5.0 debe dar más ΔP que el default automático."""
        dP_auto = estimar_delta_P_camara(_cam_horizontal(K_rug=None))
        dP_force = estimar_delta_P_camara(_cam_horizontal(K_rug=5.0))
        assert dP_force > dP_auto

    def test_vertical_incluye_termino_transicion(self):
        """En VERTICAL, ΔP debe incluir K_TRANSICION · ρ·v₀²/2 · n_bandejas
        además de malla + Ergun. Verificamos comparando con un cálculo manual
        del término de transición a partir de la velocidad superficial."""
        cam = _cam_vertical(caudal_kg_s=0.1)
        dP = estimar_delta_P_camara(cam)
        # El término de transición es estrictamente positivo
        rho = densidad_aire(323.15, 101325.0)
        Q_vol = cam.flujo.caudal_masico_kg_s / rho
        v0 = Q_vol / cam.bandejas.area_bandeja_m2
        dP_transicion = K_TRANSICION_LECHO * (rho * v0**2 / 2.0) * cam.bandejas.n_bandejas
        # El ΔP total debe ser estrictamente mayor que el término de transición
        # (porque también incluye malla + Ergun).
        assert dP > dP_transicion > 0.0

    def test_validacion_K_negativo_lanza_error(self):
        with pytest.raises(ValueError, match="BAND_K_RUGOSIDAD_INVALIDO"):
            ConfiguracionBandejas(K_rugosidad_producto=-0.5)
