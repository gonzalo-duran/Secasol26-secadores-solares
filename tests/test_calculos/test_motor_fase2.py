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
    TIPOS_MALLA,
    _factor_friccion_haaland,
    _K_malla_efectivo,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
)
from core.camara import (
    Camara, CargaProducto, ConfiguracionBandejas, ConfiguracionFlujo,
    DireccionFlujo, GeometriaCamara,
)
from core.colector import (
    BancoColectores, Colector, ColectorUnidad, Chimenea,
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
                    largo_m=2.0, ancho_m=1.0, espaciado_m=0.04,
                    espesor_placa_m=0.001, espesor_cubierta_m=0.004,
                    espesor_aislante_m=0.05, espesor_fondo_m=0.001,
                    velocidad_diseno_ms=2.0,
                    id_cubierta="vidrio_comun",
                    id_placa=placa_id,
                    id_aislante="lana_vidrio_media",
                    id_fondo="galvanizada_sin_pintura",
                ),
                banco=BancoColectores(n_serie=1, n_paralelo=1),
            )
        dP_liso = estimar_delta_P_colector(_make("aluminio_tinox"))     # ε ≈ 2e-5
        dP_rugoso = estimar_delta_P_colector(_make("galvanizada_cruda")) # ε ≈ 1e-4
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
                    n_bandejas=3, area_bandeja_m2=0.5,
                    espesor_capa_m=0.02, separacion_entre_bandejas_m=0.15,
                    tipo_malla=tipo_m,
                ),
                flujo=ConfiguracionFlujo(
                    caudal_masico_kg_s=rho*0.1,
                    direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
                ),
                carga_producto=CargaProducto(
                    producto_id="manzana", masa_total_kg=10.0,
                    humedad_inicial_X=4.6, humedad_objetivo_X=0.15,
                    modelo_capa_fina="logaritmico",
                ),
            )
        dP_grueso = estimar_delta_P_camara(_cam("alambre_grueso"))   # K=1.0
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
            delta_P_colector_Pa=10.0, delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
        )
        m_con_cero = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0, delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
            v_descarga_m_s=0.0,
        )
        assert m_sin.perdida_carga_total_Pa == m_con_cero.perdida_carga_total_Pa

    def test_v_descarga_positiva_suma_presion_dinamica(self):
        """A v=6 m/s, ρ≈1.09 → q_din ≈ 19.6 Pa."""
        m_sin = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0, delta_P_camara_Pa=50.0,
            delta_P_ductos_Pa=10.0,
        )
        m_con = Motor(
            caudal_volumetrico_m3_s=0.25,
            delta_P_colector_Pa=10.0, delta_P_camara_Pa=50.0,
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
                largo_m=2.0, ancho_m=1.0,
                espaciado_m=espac_sup,
                espaciado_inferior_m=espac_inf,
                espesor_placa_m=0.001, espesor_cubierta_m=0.004,
                espesor_aislante_m=0.05, espesor_fondo_m=0.001,
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
