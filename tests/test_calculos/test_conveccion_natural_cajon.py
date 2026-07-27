"""Tests del motor de caudal por flotabilidad sin chimenea (cajón pasivo, S61).

Hasta S60 un secador de tipo CAJA o ARMARIO **sin chimenea ni ventilador** —el
cajón con bocas, que es un caso de mucha aplicación— corría con el **caudal de
diseño constante** que cargaba el usuario. El caudal de un secador pasivo no es
un dato: es un resultado del equilibrio entre el tiro térmico (la columna de
aire caliente dentro de la cámara) y la resistencia del lazo (las bocas).

Estos tests fijan: la resistencia de bocas, el equilibrio sin chimenea, la
back-compat de la chimenea existente, y el enganche en el balance global.
"""

from __future__ import annotations

import pytest

from calculos.balance_global import (
    _areas_bocas,
    calcular_todo,
    conveccion_natural_activa,
)
from calculos.camara_calc import estimar_T_flujo_estacionario
from calculos.chimenea_calc import caudal_natural_kgs, coeficientes_bocas, delta_P_bocas_Pa
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    GeometriaCamara,
)
from core.chimenea import Chimenea
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, Proyecto, Tipologia

P_ATM = 101325.0


def _camara(A_boca: float | None = 0.05, translucida: bool = True) -> Camara:
    cons = (
        ConstruccionCamara(cubierta_translucida_id="policarbonato_alveolar")
        if translucida
        else ConstruccionCamara()
    )
    return Camara(
        geometria=GeometriaCamara(largo_m=1.2, ancho_m=0.8, alto_m=1.0),
        bandejas=ConfiguracionBandejas(n_bandejas=5, area_bandeja_m2=0.5),
        flujo=ConfiguracionFlujo(
            caudal_masico_kg_s=0.05,
            area_entrada_aire_m2=A_boca,
            area_salida_aire_m2=A_boca,
        ),
        construccion=cons,
        carga_producto=CargaProducto(
            producto_id="tomate",
            masa_total_kg=10.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.20,
        ),
    )


def _proyecto(A_boca: float | None = 0.05, con_chimenea: bool = False) -> Proyecto:
    return Proyecto(
        configuracion=Configuracion(tipologia=Tipologia.CAJA),
        emplazamiento=Emplazamiento(),
        camara=_camara(A_boca),
        chimenea=Chimenea(altura_m=2.0, diametro_m=0.25) if con_chimenea else None,
    )


# ---------------------------------------------------------------------------
# Resistencia de las bocas
# ---------------------------------------------------------------------------


class TestDeltaPBocas:

    def test_crece_al_achicar_el_area(self):
        """ΔP ∝ 1/A²: achicar la boca a la mitad cuadruplica la pérdida."""
        grande = delta_P_bocas_Pa(0.05, 0.10, 0.10, 313.15, P_ATM)
        chica = delta_P_bocas_Pa(0.05, 0.05, 0.05, 313.15, P_ATM)
        assert chica == pytest.approx(4.0 * grande, rel=1e-6)

    def test_crece_con_el_cuadrado_del_caudal(self):
        uno = delta_P_bocas_Pa(0.02, 0.05, 0.05, 313.15, P_ATM)
        doble = delta_P_bocas_Pa(0.04, 0.05, 0.05, 313.15, P_ATM)
        assert doble == pytest.approx(4.0 * uno, rel=1e-6)

    def test_salida_pesa_mas_que_entrada(self):
        """K_out (1.0) > K_in (0.5): estrangular la salida cuesta más."""
        entrada_chica = delta_P_bocas_Pa(0.05, 0.02, 0.10, 313.15, P_ATM)
        salida_chica = delta_P_bocas_Pa(0.05, 0.10, 0.02, 313.15, P_ATM)
        assert salida_chica > entrada_chica

    def test_sin_areas_no_hay_resistencia(self):
        assert delta_P_bocas_Pa(0.05, None, None, 313.15, P_ATM) == 0.0
        assert delta_P_bocas_Pa(0.05, 0.05, None, 313.15, P_ATM) == 0.0

    def test_sin_caudal_no_hay_perdida(self):
        assert delta_P_bocas_Pa(0.0, 0.05, 0.05, 313.15, P_ATM) == 0.0


# ---------------------------------------------------------------------------
# Equilibrio de flotabilidad sin chimenea
# ---------------------------------------------------------------------------


KW_CAJON = dict(
    diametro_chim_m=0.0,
    altura_chim_m=0.0,
    H_camara_m=1.0,
    delta_P_resto_fn=lambda m: 0.0,
    A_boca_entrada_m2=0.05,
    A_boca_salida_m2=0.05,
)


class TestEquilibrioCajon:

    def test_hay_caudal_sin_chimenea(self):
        """El hueco que motivó S61: un cajón con bocas mueve aire."""
        r = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)
        assert r["m_punto_kgs"] > 0.0
        assert r["v_chim_ms"] > 0.0

    def test_caudal_crece_con_el_salto_termico(self):
        m = [
            caudal_natural_kgs(T_amb_K=293.15, T_chim_K=293.15 + dT, **KW_CAJON)["m_punto_kgs"]
            for dT in (2.0, 5.0, 10.0, 20.0)
        ]
        assert m == sorted(m)

    def test_escala_con_raiz_de_delta_T(self):
        """ṁ ∝ √ΔT: el tiro es lineal en ΔT y la resistencia cuadrática en ṁ."""
        m_5 = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=298.15, **KW_CAJON)["m_punto_kgs"]
        m_20 = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)["m_punto_kgs"]
        assert m_20 / m_5 == pytest.approx(2.0, rel=0.05)

    def test_caudal_crece_con_la_altura_de_camara(self):
        kw = dict(KW_CAJON)
        kw["H_camara_m"] = 2.0
        m_alto = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **kw)["m_punto_kgs"]
        m_bajo = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)["m_punto_kgs"]
        assert m_alto > m_bajo

    def test_bocas_mas_grandes_dan_mas_caudal(self):
        kw = dict(KW_CAJON)
        kw["A_boca_entrada_m2"] = kw["A_boca_salida_m2"] = 0.15
        m_ancho = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **kw)["m_punto_kgs"]
        m_angosto = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)["m_punto_kgs"]
        assert m_ancho > m_angosto

    def test_equilibrio_real_tiro_igual_resistencia(self):
        """Sin ΔP_resto, todo el tiro lo consumen las bocas."""
        r = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)
        assert r["delta_P_bocas_Pa"] == pytest.approx(r["delta_P_tiro_Pa"], rel=1e-4)

    def test_sin_tiro_de_noche(self):
        """Cámara más fría que el ambiente ⇒ no hay flujo natural."""
        r = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=291.15, **KW_CAJON)
        assert r["m_punto_kgs"] == 0.0
        assert any("CHIM_SIN_TIRO" in a for a in r["advertencias"])

    def test_CHIM_LAZO_SIN_RESISTENCIA(self):
        """Sin chimenea, sin bocas y sin pérdidas el equilibrio no existe."""
        with pytest.raises(ValueError, match="CHIM_LAZO_SIN_RESISTENCIA"):
            caudal_natural_kgs(
                T_amb_K=293.15,
                T_chim_K=313.15,
                diametro_chim_m=0.0,
                altura_chim_m=0.0,
                H_camara_m=1.0,
                delta_P_resto_fn=lambda m: 0.0,
            )

    def test_velocidad_reportada_es_la_de_la_boca(self):
        """Sin ducto, v_chim_ms es la velocidad de descarga de la boca."""
        from calculos.motor_calc import densidad_aire

        r = caudal_natural_kgs(T_amb_K=293.15, T_chim_K=313.15, **KW_CAJON)
        rho = densidad_aire(313.15, P_ATM)
        v_esperada = r["m_punto_kgs"] / (rho * 0.05)
        assert r["v_chim_ms"] == pytest.approx(v_esperada, rel=1e-6)
        assert r["Re_chimenea"] == 0.0


class TestAcoples:
    """Topología: qué hay del otro lado de cada boca (S61)."""

    def test_entrada_ducteada_pesa_menos_que_desde_ambiente(self):
        """Armario: el aire llega ducteado del colector y se expande (K=0.3);
        caja: se contrae desde el ambiente en reposo (K=0.5)."""
        K_caja, _ = coeficientes_bocas(hay_colector=False, hay_chimenea=False)
        K_armario, _ = coeficientes_bocas(hay_colector=True, hay_chimenea=False)
        assert K_armario < K_caja

    def test_salida_a_chimenea_no_es_descarga_libre(self):
        """Con chimenea la boca alimenta el ducto (contracción), no descarga al
        ambiente: la descarga real ocurre en el tope."""
        _, K_libre = coeficientes_bocas(hay_colector=False, hay_chimenea=False)
        _, K_a_ducto = coeficientes_bocas(hay_colector=False, hay_chimenea=True)
        assert K_libre == 1.0
        assert K_a_ducto < K_libre

    def test_la_descarga_no_se_cuenta_dos_veces(self):
        """Con la boca de salida a la sección de la chimenea, la resistencia
        total no cambia: el término de entrada al ducto se descuenta del bundle
        de singulares de la chimenea.

        La boca de entrada se hace enorme para aislar el efecto de la salida.
        """
        import math

        D = 0.3
        A_chim = math.pi * (D / 2) ** 2
        kw = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=D,
            altura_chim_m=3.0,
            H_camara_m=1.0,
            delta_P_resto_fn=lambda m: 10.0 * m**2,
        )
        sin_bocas = caudal_natural_kgs(**kw)["m_punto_kgs"]
        K_in, K_out = coeficientes_bocas(hay_colector=False, hay_chimenea=True)
        con_boca_salida = caudal_natural_kgs(
            **kw,
            A_boca_entrada_m2=100.0,  # entrada irrelevante
            A_boca_salida_m2=A_chim,
            K_boca_entrada=K_in,
            K_boca_salida=K_out,
        )["m_punto_kgs"]
        assert con_boca_salida == pytest.approx(sin_bocas, rel=1e-3)

    def test_boca_de_salida_angosta_frena_el_lazo(self):
        """Si la boca es más chica que la chimenea, sí agrega resistencia."""
        import math

        D = 0.3
        kw = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=D,
            altura_chim_m=3.0,
            H_camara_m=1.0,
            delta_P_resto_fn=lambda m: 10.0 * m**2,
        )
        K_in, K_out = coeficientes_bocas(hay_colector=False, hay_chimenea=True)
        holgada = caudal_natural_kgs(
            **kw,
            A_boca_entrada_m2=100.0,
            A_boca_salida_m2=math.pi * (D / 2) ** 2,
            K_boca_entrada=K_in,
            K_boca_salida=K_out,
        )["m_punto_kgs"]
        angosta = caudal_natural_kgs(
            **kw,
            A_boca_entrada_m2=100.0,
            A_boca_salida_m2=0.02,
            K_boca_entrada=K_in,
            K_boca_salida=K_out,
        )["m_punto_kgs"]
        assert angosta < holgada


class TestBackCompatChimenea:

    def test_chimenea_sin_bocas_no_cambia(self):
        """Proyecto con chimenea y sin bocas: resultado idéntico al histórico."""
        kw = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.3,
            altura_chim_m=3.0,
            H_camara_m=1.0,
            delta_P_resto_fn=lambda m: 10.0 * m**2,
        )
        sin_bocas = caudal_natural_kgs(**kw)
        con_none = caudal_natural_kgs(**kw, A_boca_entrada_m2=None, A_boca_salida_m2=None)
        assert sin_bocas["m_punto_kgs"] == pytest.approx(con_none["m_punto_kgs"])
        assert sin_bocas["delta_P_bocas_Pa"] == 0.0

    def test_bocas_agregan_resistencia_a_la_chimenea(self):
        """Con chimenea, las bocas son aditivas: bajan el caudal."""
        kw = dict(
            T_amb_K=293.15,
            T_chim_K=323.15,
            diametro_chim_m=0.3,
            altura_chim_m=3.0,
            H_camara_m=1.0,
            delta_P_resto_fn=lambda m: 10.0 * m**2,
        )
        libre = caudal_natural_kgs(**kw)["m_punto_kgs"]
        con_bocas = caudal_natural_kgs(**kw, A_boca_entrada_m2=0.02, A_boca_salida_m2=0.02)
        assert con_bocas["m_punto_kgs"] < libre
        assert con_bocas["delta_P_bocas_Pa"] > 0.0


# ---------------------------------------------------------------------------
# Estimación de T_flujo (el empuje del cajón)
# ---------------------------------------------------------------------------


class TestTFlujoEstacionario:

    def test_caja_insolada_se_calienta_sobre_el_ambiente(self):
        """Sin colector, el sol sobre las caras translúcidas es lo que da tiro."""
        T = estimar_T_flujo_estacionario(
            _camara(),
            T_ent_K=293.15,
            HR_ent=0.40,
            m_dot_as_kg_s=0.01,
            T_amb_K=293.15,
            I_g_W_m2=800.0,
        )
        assert T > 293.15

    def test_de_noche_no_hay_empuje(self):
        """Sin sol y con el aire entrando a T_amb, el aire de cámara no calienta."""
        T = estimar_T_flujo_estacionario(
            _camara(),
            T_ent_K=293.15,
            HR_ent=0.40,
            m_dot_as_kg_s=0.01,
            T_amb_K=293.15,
            I_g_W_m2=0.0,
        )
        assert T <= 293.15

    def test_depende_del_caudal(self):
        """Es la condición que la heurística T_amb+25 K no cumplía: sin esto el
        lazo de Picard se congela en la primera iteración."""
        T_lento = estimar_T_flujo_estacionario(
            _camara(), 293.15, 0.40, 0.005, 293.15, I_g_W_m2=800.0
        )
        T_rapido = estimar_T_flujo_estacionario(
            _camara(), 293.15, 0.40, 0.100, 293.15, I_g_W_m2=800.0
        )
        assert T_lento > T_rapido  # más caudal reparte el mismo calor en más masa

    def test_armario_con_aire_caliente_tiende_a_la_entrada(self):
        """Con caudal alto el aire no alcanza a enfriarse: T_flujo → T_ent."""
        cam = _camara(translucida=False)
        T = estimar_T_flujo_estacionario(cam, 318.15, 0.20, 1.0, 293.15)
        assert T == pytest.approx(318.15, abs=1.0)

    def test_caudal_nulo_devuelve_la_entrada(self):
        assert estimar_T_flujo_estacionario(_camara(), 313.15, 0.3, 0.0, 293.15) == 313.15


# ---------------------------------------------------------------------------
# Enganche en el balance global
# ---------------------------------------------------------------------------


class TestActivacion:

    def test_cajon_con_bocas_activa_conveccion_natural(self):
        assert conveccion_natural_activa(_proyecto(A_boca=0.05)) is True

    def test_cajon_sin_bocas_cae_a_caudal_de_diseno(self):
        """Migración suave: sin bocas se conserva el comportamiento previo."""
        assert conveccion_natural_activa(_proyecto(A_boca=None)) is False

    def test_chimenea_sin_bocas_sigue_activa(self):
        assert conveccion_natural_activa(_proyecto(A_boca=None, con_chimenea=True)) is True

    def test_una_sola_boca_no_alcanza(self):
        p = _proyecto(A_boca=None)
        p.camara.flujo.area_entrada_aire_m2 = 0.05
        assert p.camara.flujo.bocas_definidas is False
        assert conveccion_natural_activa(p) is False
        assert _areas_bocas(p) == (None, None)

    def test_con_motor_no_hay_conveccion_natural(self):
        from core.motor import Motor

        p = _proyecto(A_boca=0.05)
        p.motor = Motor()
        assert conveccion_natural_activa(p) is False


class TestBalanceGlobalCajon:

    def _correr(self, p):
        return calcular_todo(
            p,
            T_amb_K=293.15,
            I_g_W_m2=800.0,
            v_viento_ms=2.0,
            T_entrada_K=293.15,
            HR_camara=0.40,
        )

    def test_el_caudal_deja_de_ser_el_de_diseno(self):
        """El resultado del cajón ya no es el número que cargó el usuario."""
        p = _proyecto(A_boca=0.05)
        res = self._correr(p)
        assert res.chimenea is not None
        m_nat = res.chimenea["m_punto_kgs"]
        assert m_nat > 0.0
        assert m_nat != pytest.approx(0.05)

    def test_sin_bocas_no_hay_lazo(self):
        res = self._correr(_proyecto(A_boca=None))
        assert res.chimenea is None

    def test_bocas_mas_anchas_mueven_mas_aire(self):
        m_angosto = self._correr(_proyecto(A_boca=0.02)).chimenea["m_punto_kgs"]
        m_ancho = self._correr(_proyecto(A_boca=0.20)).chimenea["m_punto_kgs"]
        assert m_ancho > m_angosto

    def test_el_proyecto_queda_intacto(self):
        """El lazo muta el caudal de la cámara y tiene que restaurarlo."""
        p = _proyecto(A_boca=0.05)
        self._correr(p)
        assert p.camara.flujo.caudal_masico_kg_s == pytest.approx(0.05)

    def test_converge(self):
        res = self._correr(_proyecto(A_boca=0.05))
        assert res.chimenea["convergio"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
