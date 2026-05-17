"""Tests del Motor (core/motor.py) y de las estimaciones de ΔP (calculos/motor_calc.py)."""

from __future__ import annotations

import pytest

from calculos.motor_calc import (
    K_MALLA,
    caudal_masico_a_volumetrico,
    densidad_aire,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
    presion_atmosferica,
    viscosidad_aire,
)
from core.advertencias import Severidad
from core.camara import Camara
from core.colector import Colector
from core.motor import Motor, TipoAccionamiento


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def motor_minimo():
    """Motor con ΔP total directa, sin cálculo de componentes."""
    return Motor(
        tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
        caudal_volumetrico_m3_s=0.020,
        perdida_carga_total_Pa=50.0,
        eficiencia_ventilador=0.55,
        eficiencia_motor=0.85,
        factor_servicio=1.15,
    )


@pytest.fixture
def motor_con_componentes():
    """Motor con ΔP calculada desde componentes."""
    return Motor(
        tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
        caudal_volumetrico_m3_s=0.030,
        delta_P_colector_Pa=30.0,
        delta_P_camara_Pa=15.0,
        delta_P_ductos_Pa=10.0,
        eficiencia_ventilador=0.60,
        eficiencia_motor=0.85,
        factor_servicio=1.15,
        tension_V=220.0,
    )


# ---------------------------------------------------------------------------
# Motor — errores duros
# ---------------------------------------------------------------------------

class TestMotorErroresDuros:

    def test_instancia_valida(self, motor_minimo):
        assert motor_minimo.caudal_volumetrico_m3_s == 0.020

    def test_conveccion_natural_lanza(self):
        with pytest.raises(ValueError, match="MOT_CONVECCION_NATURAL_CON_MOTOR"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.CONVECCION_NATURAL,
                caudal_volumetrico_m3_s=0.020,
            )

    def test_caudal_no_positivo(self):
        with pytest.raises(ValueError, match="MOT_CAUDAL_NO_POSITIVO"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
                caudal_volumetrico_m3_s=0.0,
                perdida_carga_total_Pa=50.0,
            )

    def test_eficiencia_ventilador_cero(self):
        with pytest.raises(ValueError, match="MOT_EFICIENCIA_VENTILADOR_INVALIDA"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
                caudal_volumetrico_m3_s=0.020,
                perdida_carga_total_Pa=50.0,
                eficiencia_ventilador=0.0,
            )

    def test_eficiencia_ventilador_mayor_uno(self):
        with pytest.raises(ValueError, match="MOT_EFICIENCIA_VENTILADOR_INVALIDA"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
                caudal_volumetrico_m3_s=0.020,
                perdida_carga_total_Pa=50.0,
                eficiencia_ventilador=1.1,
            )

    def test_eficiencia_motor_invalida(self):
        with pytest.raises(ValueError, match="MOT_EFICIENCIA_MOTOR_INVALIDA"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
                caudal_volumetrico_m3_s=0.020,
                perdida_carga_total_Pa=50.0,
                eficiencia_motor=0.0,
            )

    def test_factor_servicio_menor_uno(self):
        with pytest.raises(ValueError, match="MOT_FACTOR_SERVICIO_INVALIDO"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
                caudal_volumetrico_m3_s=0.020,
                perdida_carga_total_Pa=50.0,
                factor_servicio=0.9,
            )

    def test_extractor_sin_diametro(self):
        with pytest.raises(ValueError, match="MOT_EXTRACTOR_SIN_DIAMETRO"):
            Motor(
                tipo_accionamiento=TipoAccionamiento.EXTRACTOR_EOLICO,
                caudal_volumetrico_m3_s=0.020,
                perdida_carga_total_Pa=30.0,
            )

    def test_extractor_con_diametro_valido(self):
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.EXTRACTOR_EOLICO,
            caudal_volumetrico_m3_s=0.020,
            perdida_carga_total_Pa=30.0,
            diametro_extractor_m=0.45,
        )
        assert motor.diametro_extractor_m == 0.45


# ---------------------------------------------------------------------------
# Motor — cálculo de potencias
# ---------------------------------------------------------------------------

class TestMotorCalculoPotencias:

    def test_potencia_hidraulica_formula(self, motor_minimo):
        P_hid_esperada = 0.020 * 50.0
        assert motor_minimo.potencia_hidraulica_W == pytest.approx(P_hid_esperada)

    def test_potencia_eje_formula(self, motor_minimo):
        P_hid = 0.020 * 50.0
        P_eje_esperada = P_hid / 0.55
        assert motor_minimo.potencia_eje_W == pytest.approx(P_eje_esperada)

    def test_potencia_electrica_formula(self, motor_minimo):
        P_hid = 0.020 * 50.0
        P_elec_esperada = (P_hid / 0.55) / 0.85
        assert motor_minimo.potencia_electrica_W == pytest.approx(P_elec_esperada)

    def test_potencia_a_instalar_formula(self, motor_minimo):
        P_hid = 0.020 * 50.0
        P_inst_esperada = (P_hid / 0.55 / 0.85) * 1.15
        assert motor_minimo.potencia_a_instalar_W == pytest.approx(P_inst_esperada)

    def test_corriente_none_sin_tension(self, motor_minimo):
        assert motor_minimo.corriente_nominal_A is None

    def test_corriente_calculada_con_tension(self, motor_con_componentes):
        from core.motor import _COS_PHI
        P_elec = motor_con_componentes.potencia_electrica_W
        I_esperada = P_elec / (220.0 * _COS_PHI)
        assert motor_con_componentes.corriente_nominal_A == pytest.approx(I_esperada)

    def test_potencias_crecientes(self, motor_minimo):
        """P_hid < P_eje < P_elec < P_inst."""
        assert (motor_minimo.potencia_hidraulica_W
                < motor_minimo.potencia_eje_W
                < motor_minimo.potencia_electrica_W
                < motor_minimo.potencia_a_instalar_W)


# ---------------------------------------------------------------------------
# Motor — ΔP desde componentes
# ---------------------------------------------------------------------------

class TestMotorDeltaP:

    def test_dP_total_desde_componentes(self, motor_con_componentes):
        assert motor_con_componentes.perdida_carga_total_Pa == pytest.approx(55.0)

    def test_dP_ductos_automatico(self):
        """Sin delta_P_ductos_Pa, se estima como 20% de col+cam."""
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.020,
            delta_P_colector_Pa=30.0,
            delta_P_camara_Pa=20.0,
        )
        dP_ductos_esperado = 0.20 * (30.0 + 20.0)
        dP_total_esperado = 30.0 + 20.0 + dP_ductos_esperado
        assert motor.perdida_carga_total_Pa == pytest.approx(dP_total_esperado)

    def test_advertencia_ductos_estimados(self):
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.020,
            delta_P_colector_Pa=30.0,
            delta_P_camara_Pa=20.0,
        )
        codigos = [a.codigo for a in motor.advertencias]
        assert "MOT_DUCTOS_ESTIMADOS" in codigos

    def test_sin_advertencia_ductos_si_especificado(self, motor_con_componentes):
        codigos = [a.codigo for a in motor_con_componentes.advertencias]
        assert "MOT_DUCTOS_ESTIMADOS" not in codigos

    def test_dP_cero_cuando_sin_entradas(self):
        """Sin ΔP_total ni componentes → ΔP_total = 0 y potencias = None."""
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.020,
        )
        assert motor.perdida_carga_total_Pa == pytest.approx(0.0)
        assert motor.potencia_hidraulica_W is None


# ---------------------------------------------------------------------------
# Motor — advertencias de diseño
# ---------------------------------------------------------------------------

class TestMotorAdvertencias:

    def test_advertencia_potencia_baja(self):
        """Potencia a instalar < 30 W → MOT_POTENCIA_BAJA."""
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.001,   # caudal muy bajo
            perdida_carga_total_Pa=5.0,
        )
        codigos = [a.codigo for a in motor.advertencias]
        assert "MOT_POTENCIA_BAJA" in codigos

    def test_advertencia_potencia_alta(self):
        """Potencia a instalar > 5000 W → MOT_POTENCIA_ALTA.
        Q=1.0 m³/s, ΔP=5000 Pa → P_inst ≈ 12 650 W > 5000 W."""
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=1.0,
            perdida_carga_total_Pa=5000.0,
        )
        codigos = [a.codigo for a in motor.advertencias]
        assert "MOT_POTENCIA_ALTA" in codigos
        a = next(x for x in motor.advertencias if x.codigo == "MOT_POTENCIA_ALTA")
        assert a.severidad == Severidad.WARNING

    def test_advertencia_sin_tension(self, motor_minimo):
        codigos = [a.codigo for a in motor_minimo.advertencias]
        assert "MOT_SIN_TENSION" in codigos

    def test_sin_advertencia_tension_especificada(self, motor_con_componentes):
        codigos = [a.codigo for a in motor_con_componentes.advertencias]
        assert "MOT_SIN_TENSION" not in codigos

    def test_advertencia_extractor_viento_bajo(self):
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.EXTRACTOR_EOLICO,
            caudal_volumetrico_m3_s=0.010,
            perdida_carga_total_Pa=20.0,
            diametro_extractor_m=0.45,
            velocidad_viento_diseno_m_s=1.5,  # < 2.0 m/s
        )
        codigos = [a.codigo for a in motor.advertencias]
        assert "MOT_EXTRACTOR_VIENTO_BAJO" in codigos

    def test_sin_advertencia_extractor_viento_ok(self):
        motor = Motor(
            tipo_accionamiento=TipoAccionamiento.EXTRACTOR_EOLICO,
            caudal_volumetrico_m3_s=0.010,
            perdida_carga_total_Pa=20.0,
            diametro_extractor_m=0.45,
            velocidad_viento_diseno_m_s=3.0,  # ≥ 2.0 m/s
        )
        codigos = [a.codigo for a in motor.advertencias]
        assert "MOT_EXTRACTOR_VIENTO_BAJO" not in codigos


# ---------------------------------------------------------------------------
# estimar_delta_P_colector
# ---------------------------------------------------------------------------

class TestEstimarDeltaPColector:

    def test_dP_positivo_flujo_laminar(self):
        colector = Colector()
        dP = estimar_delta_P_colector(colector)
        assert dP > 0

    def test_dP_crece_con_velocidad(self):
        from core.colector import ColectorUnidad, BancoColectores
        col_lento = Colector(
            unidad=ColectorUnidad(velocidad_diseno_ms=0.3),
        )
        col_rapido = Colector(
            unidad=ColectorUnidad(velocidad_diseno_ms=1.5),
        )
        assert estimar_delta_P_colector(col_rapido) > estimar_delta_P_colector(col_lento)

    def test_dP_crece_con_largo(self):
        from core.colector import ColectorUnidad
        col_corto = Colector(unidad=ColectorUnidad(largo_m=1.0))
        col_largo = Colector(unidad=ColectorUnidad(largo_m=4.0))
        assert estimar_delta_P_colector(col_largo) > estimar_delta_P_colector(col_corto)

    def test_dP_crece_con_n_serie(self):
        from core.colector import BancoColectores
        col_1 = Colector(banco=BancoColectores(n_serie=1))
        col_3 = Colector(banco=BancoColectores(n_serie=3))
        assert estimar_delta_P_colector(col_3) > estimar_delta_P_colector(col_1)

    def test_regimen_turbulento_friccion_menor(self):
        """Para Re turbulento, f_Blasius < f_laminar → ΔP escala diferente."""
        from core.colector import ColectorUnidad
        # v=0.1 m/s → Re ≈ 300 (laminar), v=3.0 m/s → Re ≈ 9000 (turbulento)
        col_lam = Colector(unidad=ColectorUnidad(velocidad_diseno_ms=0.1))
        col_turb = Colector(unidad=ColectorUnidad(velocidad_diseno_ms=3.0))
        # Solo verificamos que la función corre sin error y produce positivo
        assert estimar_delta_P_colector(col_lam) > 0
        assert estimar_delta_P_colector(col_turb) > 0


# ---------------------------------------------------------------------------
# estimar_delta_P_camara
# ---------------------------------------------------------------------------

class TestEstimarDeltaPCamara:

    def test_dP_positivo(self):
        camara = Camara()
        dP = estimar_delta_P_camara(camara)
        assert dP > 0

    def test_dP_crece_con_n_bandejas(self):
        from core.camara import ConfiguracionBandejas
        cam_5 = Camara(bandejas=ConfiguracionBandejas(
            n_bandejas=5, area_bandeja_m2=0.5,
            espesor_capa_m=0.02, separacion_entre_bandejas_m=0.15,
        ))
        cam_10 = Camara(bandejas=ConfiguracionBandejas(
            n_bandejas=10, area_bandeja_m2=0.5,
            espesor_capa_m=0.02, separacion_entre_bandejas_m=0.08,
        ))
        assert estimar_delta_P_camara(cam_10) > estimar_delta_P_camara(cam_5)

    def test_dP_escala_con_caudal(self):
        """ΔP ∝ v_sup² ∝ Q²."""
        from core.camara import ConfiguracionFlujo
        cam_bajo = Camara(flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.02))
        cam_alto = Camara(flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.10))
        dP_bajo = estimar_delta_P_camara(cam_bajo)
        dP_alto = estimar_delta_P_camara(cam_alto)
        assert dP_alto > dP_bajo


# ---------------------------------------------------------------------------
# caudal_masico_a_volumetrico
# ---------------------------------------------------------------------------

class TestCaudalMasicoAVolumetrico:

    def test_formula_gas_ideal(self):
        R = 287.058
        T = 323.15
        P = 101325.0
        rho = P / (R * T)
        Q_vol = caudal_masico_a_volumetrico(0.03, T, P)
        assert Q_vol == pytest.approx(0.03 / rho, rel=1e-6)

    def test_mayor_Q_a_mayor_T(self):
        """A mayor temperatura, menor densidad → mayor caudal volumétrico."""
        Q_50 = caudal_masico_a_volumetrico(0.03, T_K=323.15)
        Q_80 = caudal_masico_a_volumetrico(0.03, T_K=353.15)
        assert Q_80 > Q_50


# ---------------------------------------------------------------------------
# presion_atmosferica
# ---------------------------------------------------------------------------

class TestPresionAtmosferica:

    def test_nivel_del_mar(self):
        """P(0 m) = 101 325 Pa."""
        assert presion_atmosferica(0.0) == pytest.approx(101325.0, rel=1e-6)

    def test_1000m_menor_que_nivel_del_mar(self):
        assert presion_atmosferica(1000.0) < presion_atmosferica(0.0)

    def test_salta_1187m(self):
        """Salta ≈ 1 187 m → P ≈ 87 500 Pa (ISA)."""
        P = presion_atmosferica(1187.0)
        assert P == pytest.approx(87500.0, rel=0.01)

    def test_monotona_decreciente(self):
        for h1, h2 in [(0, 500), (500, 1000), (1000, 3000)]:
            assert presion_atmosferica(h1) > presion_atmosferica(h2)


# ---------------------------------------------------------------------------
# densidad_aire
# ---------------------------------------------------------------------------

class TestDensidadAire:

    def test_valor_0C_1atm(self):
        """ρ(273.15 K, 101325 Pa) ≈ 1.293 kg/m³."""
        rho = densidad_aire(273.15, 101325.0)
        assert rho == pytest.approx(1.293, rel=0.005)

    def test_valor_50C_1atm(self):
        """ρ(323.15 K, 101325 Pa) ≈ 1.093 kg/m³."""
        rho = densidad_aire(323.15, 101325.0)
        assert rho == pytest.approx(1.093, rel=0.005)

    def test_decrece_con_T(self):
        assert densidad_aire(323.15) > densidad_aire(353.15)

    def test_decrece_con_altitud(self):
        """A mayor altitud (menor P), menor densidad."""
        rho_mar = densidad_aire(323.15, presion_atmosferica(0.0))
        rho_salta = densidad_aire(323.15, presion_atmosferica(1187.0))
        assert rho_salta < rho_mar

    def test_gas_ideal_exacto(self):
        R = 287.058
        T, P = 350.0, 90000.0
        assert densidad_aire(T, P) == pytest.approx(P / (R * T), rel=1e-9)


# ---------------------------------------------------------------------------
# viscosidad_aire
# ---------------------------------------------------------------------------

class TestViscosidadAire:

    def test_valor_0C(self):
        """μ(273.15 K) ≈ 1.716×10⁻⁵ Pa·s (valor de referencia Sutherland)."""
        mu = viscosidad_aire(273.15)
        assert mu == pytest.approx(1.716e-5, rel=0.01)

    def test_valor_50C(self):
        """μ(323.15 K) ≈ 1.963×10⁻⁵ Pa·s (tablas de aire)."""
        mu = viscosidad_aire(323.15)
        assert mu == pytest.approx(1.963e-5, rel=0.02)

    def test_crece_con_T(self):
        """Gases: viscosidad aumenta con temperatura (inverso a líquidos)."""
        assert viscosidad_aire(300.0) < viscosidad_aire(400.0)

    def test_positiva_siempre(self):
        for T in [273.15, 323.15, 373.15]:
            assert viscosidad_aire(T) > 0


# ---------------------------------------------------------------------------
# estimar_delta_P_colector — variable density
# ---------------------------------------------------------------------------

class TestDeltaPColectorDensidadVariable:

    def test_mayor_dP_en_altura(self):
        """A mayor altitud, menor ρ → menor Re → puede cambiar régimen.
        Para Re laminar ΔP ∝ μ·v·L/Dh² (independiente de ρ si μ cambia poco).
        Verificamos que la función corre sin error con altitud."""
        colector = Colector()
        dP_mar = estimar_delta_P_colector(colector, T_K=323.15, P_Pa=101325.0)
        dP_salta = estimar_delta_P_colector(colector, T_K=323.15,
                                            P_Pa=presion_atmosferica(1187.0))
        assert dP_mar > 0 and dP_salta > 0

    def test_mayor_T_cambia_dP(self):
        """A mayor temperatura, μ aumenta y ρ disminuye — el efecto neto sobre ΔP
        laminar es menor ρ (menor velocidad de referencia implica misma μ·v/Dh²)."""
        colector = Colector()
        dP_50 = estimar_delta_P_colector(colector, T_K=323.15)
        dP_80 = estimar_delta_P_colector(colector, T_K=353.15)
        # Solo verificamos que no lanza y da positivo
        assert dP_50 > 0 and dP_80 > 0


# ---------------------------------------------------------------------------
# estimar_delta_P_camara — VERTICAL con Ergun
# ---------------------------------------------------------------------------

class TestDeltaPCamaraVerticalErgun:

    @pytest.fixture
    def camara_vertical_con_particulas(self):
        """Cámara VERTICAL_ASCENDENTE con d_p definido → aplica Ergun."""
        from core.camara import (
            Camara, ConfiguracionBandejas, ConfiguracionFlujo, DireccionFlujo
        )
        return Camara(
            bandejas=ConfiguracionBandejas(
                n_bandejas=5,
                area_bandeja_m2=0.50,
                espesor_capa_m=0.020,
                separacion_entre_bandejas_m=0.15,
                porosidad_lecho=0.40,
                diametro_eq_particula_m=0.010,  # 10 mm (rodajas de manzana)
                esfericidad=0.60,
            ),
            flujo=ConfiguracionFlujo(
                caudal_masico_kg_s=0.030,
                direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
            ),
        )

    @pytest.fixture
    def camara_vertical_sin_d_p_explicito(self):
        """Cámara VERTICAL sin d_p explícito → motor_calc usa defaults del
        catálogo/conservadores (Ergun activo de todos modos)."""
        from core.camara import (
            Camara, ConfiguracionBandejas, ConfiguracionFlujo, DireccionFlujo
        )
        return Camara(
            bandejas=ConfiguracionBandejas(
                n_bandejas=5,
                area_bandeja_m2=0.50,
                espesor_capa_m=0.020,
                separacion_entre_bandejas_m=0.15,
                diametro_eq_particula_m=None,
            ),
            flujo=ConfiguracionFlujo(
                caudal_masico_kg_s=0.030,
                direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
            ),
        )

    def test_vertical_d_p_pequeno_mayor_que_grande(
        self, camara_vertical_con_particulas, camara_vertical_sin_d_p_explicito
    ):
        """A menor d_p, ΔP_Ergun es mayor (mayor superficie/volumen).
        El default sin d_p explícito (8 mm) es menor que 10 mm de la fixture."""
        dP_10mm = estimar_delta_P_camara(camara_vertical_con_particulas)
        dP_default = estimar_delta_P_camara(camara_vertical_sin_d_p_explicito)
        # default = 8 mm → más Ergun que 10 mm
        assert dP_default > dP_10mm

    def test_vertical_sin_d_p_usa_default_ergun(
        self, camara_vertical_sin_d_p_explicito
    ):
        """Sin d_p explícito ni producto, motor_calc usa defaults (d_p=8 mm,
        ε=0.45, Φ=0.6) → Ergun activo, ΔP > solo malla."""
        from core.camara import DireccionFlujo
        cam = camara_vertical_sin_d_p_explicito
        f = cam.flujo
        b = cam.bandejas
        rho = densidad_aire(323.15, 101325.0)
        Q_vol = f.caudal_masico_kg_s / rho
        v0 = Q_vol / b.area_bandeja_m2
        dP_malla_sola = K_MALLA * (rho * v0**2 / 2.0) * b.n_bandejas
        dP_calc = estimar_delta_P_camara(cam)
        # Con Ergun activo por default, debe ser estrictamente mayor que sólo malla.
        assert dP_calc > dP_malla_sola

    def test_vertical_positivo(self, camara_vertical_con_particulas):
        assert estimar_delta_P_camara(camara_vertical_con_particulas) > 0

    def test_ergun_crece_con_caudal(self):
        """Mayor caudal → mayor v₀ → mayor ΔP Ergun."""
        from core.camara import (
            Camara, ConfiguracionBandejas, ConfiguracionFlujo, DireccionFlujo
        )
        def make_cam(q):
            return Camara(
                bandejas=ConfiguracionBandejas(
                    n_bandejas=3, area_bandeja_m2=0.5,
                    espesor_capa_m=0.02, separacion_entre_bandejas_m=0.15,
                    diametro_eq_particula_m=0.008, esfericidad=0.60,
                ),
                flujo=ConfiguracionFlujo(
                    caudal_masico_kg_s=q,
                    direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
                ),
            )
        assert estimar_delta_P_camara(make_cam(0.10)) > estimar_delta_P_camara(make_cam(0.03))

    def test_ergun_crece_con_espesor_capa(self):
        """Mayor L → mayor ΔP_lecho (ΔP/L × L)."""
        from core.camara import (
            Camara, ConfiguracionBandejas, ConfiguracionFlujo, DireccionFlujo
        )
        def make_cam(L):
            return Camara(
                bandejas=ConfiguracionBandejas(
                    n_bandejas=3, area_bandeja_m2=0.5,
                    espesor_capa_m=L,
                    separacion_entre_bandejas_m=max(0.10, L + 0.015),
                    diametro_eq_particula_m=0.008, esfericidad=0.60,
                ),
                flujo=ConfiguracionFlujo(
                    caudal_masico_kg_s=0.03,
                    direccion_flujo=DireccionFlujo.VERTICAL_ASCENDENTE,
                ),
            )
        assert estimar_delta_P_camara(make_cam(0.04)) > estimar_delta_P_camara(make_cam(0.02))


# ---------------------------------------------------------------------------
# ConfiguracionBandejas — nuevos campos Ergun
# ---------------------------------------------------------------------------

class TestConfiguracionBandejasErgun:

    def test_porosidad_cero_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_POROSIDAD_INVALIDA"):
            ConfiguracionBandejas(porosidad_lecho=0.0)

    def test_porosidad_uno_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_POROSIDAD_INVALIDA"):
            ConfiguracionBandejas(porosidad_lecho=1.0)

    def test_porosidad_valida(self):
        from core.camara import ConfiguracionBandejas
        b = ConfiguracionBandejas(porosidad_lecho=0.40)
        assert b.porosidad_lecho == pytest.approx(0.40)

    def test_diametro_no_positivo_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_DIAMETRO_PARTICULA_NO_POSITIVO"):
            ConfiguracionBandejas(diametro_eq_particula_m=0.0)

    def test_diametro_negativo_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_DIAMETRO_PARTICULA_NO_POSITIVO"):
            ConfiguracionBandejas(diametro_eq_particula_m=-0.005)

    def test_diametro_none_valido(self):
        from core.camara import ConfiguracionBandejas
        b = ConfiguracionBandejas(diametro_eq_particula_m=None)
        assert b.diametro_eq_particula_m is None

    def test_diametro_positivo_valido(self):
        from core.camara import ConfiguracionBandejas
        b = ConfiguracionBandejas(diametro_eq_particula_m=0.010)
        assert b.diametro_eq_particula_m == pytest.approx(0.010)

    def test_esfericidad_cero_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_ESFERICIDAD_INVALIDA"):
            ConfiguracionBandejas(esfericidad=0.0)

    def test_esfericidad_mayor_uno_lanza(self):
        from core.camara import ConfiguracionBandejas
        with pytest.raises(ValueError, match="BAND_ESFERICIDAD_INVALIDA"):
            ConfiguracionBandejas(esfericidad=1.1)

    def test_esfericidad_uno_valido(self):
        """Esfericidad = 1.0 (esfera perfecta) es válida."""
        from core.camara import ConfiguracionBandejas
        b = ConfiguracionBandejas(esfericidad=1.0)
        assert b.esfericidad == pytest.approx(1.0)
