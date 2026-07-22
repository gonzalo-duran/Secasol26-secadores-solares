"""Tests del modelo de datos del sistema auxiliar (core/auxiliar.py) y
del motor numérico (calculos/auxiliar_calc.py).
"""

from __future__ import annotations

import pytest

from calculos.auxiliar_calc import ResultadosAuxiliar, calcular_auxiliar
from core.advertencias import Severidad
from core.auxiliar import (
    Auxiliar,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
    advertencias_auxiliar,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def resistencia_minima():
    return Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=1000.0,
        temperatura_maxima_salida_K=343.15,
    )


@pytest.fixture
def quemador_minimo():
    return Auxiliar(
        tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
        modo_operacion=ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
        potencia_nominal_W=3000.0,
        temperatura_maxima_salida_K=353.15,
        PCI_MJ_kg=15.0,
        eficiencia_quemador=0.65,
        disponible_nocturno=True,
    )


# ---------------------------------------------------------------------------
# Auxiliar — errores duros
# ---------------------------------------------------------------------------


class TestAuxiliarErroresDuros:

    def test_instancia_valida_resistencia(self, resistencia_minima):
        assert resistencia_minima.potencia_nominal_W == 1000.0

    def test_instancia_valida_quemador(self, quemador_minimo):
        assert quemador_minimo.PCI_MJ_kg == 15.0

    def test_potencia_no_positiva(self):
        with pytest.raises(ValueError, match="AUX_POTENCIA_NO_POSITIVA"):
            Auxiliar(potencia_nominal_W=0.0, temperatura_maxima_salida_K=343.15)

    def test_T_max_bajo_cero(self):
        with pytest.raises(ValueError, match="AUX_T_MAX_SALIDA_INVALIDA"):
            Auxiliar(potencia_nominal_W=500.0, temperatura_maxima_salida_K=270.0)

    def test_T_max_sobre_200C(self):
        with pytest.raises(ValueError, match="AUX_T_MAX_SALIDA_INVALIDA"):
            Auxiliar(potencia_nominal_W=500.0, temperatura_maxima_salida_K=480.0)

    def test_set_point_excede_T_max(self):
        with pytest.raises(ValueError, match="AUX_SET_POINT_EXCEDE_T_MAX"):
            Auxiliar(
                potencia_nominal_W=1000.0,
                temperatura_maxima_salida_K=343.15,
                set_point_T_K=350.0,
            )

    def test_fraccion_negativa(self):
        with pytest.raises(ValueError, match="AUX_FRACCION_INVALIDA"):
            Auxiliar(
                potencia_nominal_W=1000.0,
                temperatura_maxima_salida_K=343.15,
                fraccion_potencia_operacion=-0.1,
            )

    def test_fraccion_mayor_uno(self):
        with pytest.raises(ValueError, match="AUX_FRACCION_INVALIDA"):
            Auxiliar(
                potencia_nominal_W=1000.0,
                temperatura_maxima_salida_K=343.15,
                fraccion_potencia_operacion=1.1,
            )

    def test_biomasa_sin_PCI_ni_consumo(self):
        with pytest.raises(ValueError, match="AUX_BIOMASA_SIN_PCI"):
            Auxiliar(
                tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
                potencia_nominal_W=2000.0,
                temperatura_maxima_salida_K=353.15,
            )

    def test_biomasa_con_PCI_sin_eficiencia(self):
        with pytest.raises(ValueError, match="AUX_BIOMASA_SIN_EFICIENCIA"):
            Auxiliar(
                tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
                potencia_nominal_W=2000.0,
                temperatura_maxima_salida_K=353.15,
                PCI_MJ_kg=15.0,
                eficiencia_quemador=None,
            )

    def test_biomasa_con_consumo_directo_valido(self):
        """Consumo override sin PCI ni η debe ser válido."""
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=353.15,
            consumo_biomasa_kg_h=0.5,
        )
        assert aux.consumo_biomasa_kg_h == 0.5


# ---------------------------------------------------------------------------
# Auxiliar — métodos auxiliares
# ---------------------------------------------------------------------------


class TestAuxiliarMetodos:

    def test_potencia_efectiva_fraccion_completa(self, resistencia_minima):
        assert resistencia_minima.potencia_efectiva_W() == pytest.approx(1000.0)

    def test_potencia_efectiva_fraccion_parcial(self):
        aux = Auxiliar(
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=343.15,
            fraccion_potencia_operacion=0.6,
        )
        assert aux.potencia_efectiva_W() == pytest.approx(1200.0)

    def test_consumo_biomasa_calculado(self, quemador_minimo):
        consumo = quemador_minimo.consumo_biomasa_efectivo_kg_h()
        # consumo = 3000 * 3600 / (15e6 * 0.65) = 1.108 kg/h
        esperado = 3000.0 * 3600.0 / (15.0e6 * 0.65)
        assert consumo == pytest.approx(esperado, rel=1e-4)

    def test_consumo_biomasa_none_para_resistencia(self, resistencia_minima):
        assert resistencia_minima.consumo_biomasa_efectivo_kg_h() is None

    def test_consumo_biomasa_override(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=343.15,
            consumo_biomasa_kg_h=0.8,
        )
        # Con fraccion=1.0, el consumo = 0.8 * (1.0 / 1.0) = 0.8 kg/h
        assert aux.consumo_biomasa_efectivo_kg_h() == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Advertencias
# ---------------------------------------------------------------------------


class TestAdvertenciasAuxiliar:

    def test_sin_advertencias_resistencia_bien_configurada(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            potencia_nominal_W=1000.0,
            temperatura_maxima_salida_K=333.15,  # 60 °C ≤ 70 °C
            tension_V=220.0,
        )
        adv = advertencias_auxiliar(aux)
        codigos = [a.codigo for a in adv]
        assert "AUX_T_MAX_ALTA_PARA_PRODUCTO" not in codigos
        assert "AUX_RESISTENCIA_SIN_TENSION" not in codigos

    def test_advertencia_T_max_alta(self):
        aux = Auxiliar(
            potencia_nominal_W=1000.0,
            temperatura_maxima_salida_K=363.15,  # 90 °C > 70 °C
        )
        adv = advertencias_auxiliar(aux)
        codigos = [a.codigo for a in adv]
        assert "AUX_T_MAX_ALTA_PARA_PRODUCTO" in codigos
        a = next(x for x in adv if x.codigo == "AUX_T_MAX_ALTA_PARA_PRODUCTO")
        assert a.severidad == Severidad.WARNING

    def test_advertencia_resistencia_sin_tension(self, resistencia_minima):
        adv = advertencias_auxiliar(resistencia_minima)
        codigos = [a.codigo for a in adv]
        assert "AUX_RESISTENCIA_SIN_TENSION" in codigos

    def test_sin_advertencia_resistencia_con_tension(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            potencia_nominal_W=500.0,
            temperatura_maxima_salida_K=333.15,
            tension_V=220.0,
        )
        adv = advertencias_auxiliar(aux)
        codigos = [a.codigo for a in adv]
        assert "AUX_RESISTENCIA_SIN_TENSION" not in codigos

    def test_advertencia_biomasa_eficiencia_baja(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=343.15,
            PCI_MJ_kg=15.0,
            eficiencia_quemador=0.40,  # < 0.50
        )
        adv = advertencias_auxiliar(aux)
        codigos = [a.codigo for a in adv]
        assert "AUX_BIOMASA_EFICIENCIA_BAJA" in codigos

    def test_sin_advertencia_biomasa_eficiencia_ok(self, quemador_minimo):
        adv = advertencias_auxiliar(quemador_minimo)
        codigos = [a.codigo for a in adv]
        assert "AUX_BIOMASA_EFICIENCIA_BAJA" not in codigos

    def test_advertencia_respaldo_sin_nocturno(self):
        aux = Auxiliar(
            tipo=TipoAuxiliar.QUEMADOR_BIOMASA,
            modo_operacion=ModoOperacionAuxiliar.RESPALDO_INDEPENDIENTE,
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=343.15,
            PCI_MJ_kg=15.0,
            eficiencia_quemador=0.65,
            disponible_nocturno=False,
        )
        adv = advertencias_auxiliar(aux)
        codigos = [a.codigo for a in adv]
        assert "AUX_RESPALDO_SIN_DISPONIBILIDAD_NOCTURNA" in codigos


# ---------------------------------------------------------------------------
# calcular_auxiliar
# ---------------------------------------------------------------------------


class TestCalcularAuxiliar:

    def test_resultado_tipo_correcto(self, resistencia_minima):
        res = calcular_auxiliar(resistencia_minima, T_entrada_K=323.15, caudal_masico_kg_s=0.03)
        assert isinstance(res, ResultadosAuxiliar)

    def test_T_salida_mayor_que_T_entrada(self, resistencia_minima):
        res = calcular_auxiliar(resistencia_minima, T_entrada_K=323.15, caudal_masico_kg_s=0.03)
        assert res.T_salida_K > res.T_entrada_K

    def test_delta_T_formula(self, resistencia_minima):
        """ΔT = Q_eff / (m_dot × cp)."""
        from calculos.auxiliar_calc import CP_AIRE

        m_dot = 0.03
        T_ent = 323.15
        res = calcular_auxiliar(resistencia_minima, T_entrada_K=T_ent, caudal_masico_kg_s=m_dot)
        delta_T_esperado = resistencia_minima.potencia_efectiva_W() / (m_dot * CP_AIRE)
        assert res.delta_T_K == pytest.approx(delta_T_esperado, rel=1e-6)

    def test_consumo_electrico_igual_Q_efectivo(self, resistencia_minima):
        res = calcular_auxiliar(resistencia_minima, T_entrada_K=323.15, caudal_masico_kg_s=0.03)
        assert res.consumo_electrico_W == pytest.approx(res.Q_efectivo_W, rel=1e-9)

    def test_consumo_biomasa_calculado(self, quemador_minimo):
        res = calcular_auxiliar(quemador_minimo, T_entrada_K=298.15, caudal_masico_kg_s=0.05)
        assert res.consumo_biomasa_kg_h is not None
        assert res.consumo_biomasa_kg_h > 0

    def test_T_invalida_lanza(self, resistencia_minima):
        with pytest.raises(ValueError):
            calcular_auxiliar(resistencia_minima, T_entrada_K=0.0, caudal_masico_kg_s=0.03)

    def test_caudal_invalido_lanza(self, resistencia_minima):
        with pytest.raises(ValueError):
            calcular_auxiliar(resistencia_minima, T_entrada_K=323.15, caudal_masico_kg_s=0.0)

    def test_set_point_limita_potencia(self):
        """Con set point por debajo de lo que daría potencia nominal, Q_eff < Q_nominal."""
        from calculos.auxiliar_calc import CP_AIRE

        m_dot = 0.10
        T_ent = 313.15  # 40 °C
        set_point = 323.15  # 50 °C — solo necesita 10 K de ΔT
        Q_para_set = m_dot * CP_AIRE * (set_point - T_ent)  # ≈ 1007 W

        aux = Auxiliar(
            potencia_nominal_W=5000.0,  # mucho más de lo necesario
            temperatura_maxima_salida_K=353.15,
            set_point_T_K=set_point,
        )
        res = calcular_auxiliar(aux, T_entrada_K=T_ent, caudal_masico_kg_s=m_dot)
        assert res.set_point_activo
        assert res.Q_efectivo_W == pytest.approx(Q_para_set, rel=1e-5)
        assert res.T_salida_K == pytest.approx(set_point, abs=0.01)

    def test_T_entrada_supera_set_point(self):
        """Si T_entrada > set_point, el auxiliar no aporta calor."""
        aux = Auxiliar(
            potencia_nominal_W=1000.0,
            temperatura_maxima_salida_K=353.15,
            set_point_T_K=323.15,  # 50 °C
        )
        res = calcular_auxiliar(aux, T_entrada_K=333.15, caudal_masico_kg_s=0.03)
        assert res.Q_efectivo_W == pytest.approx(0.0, abs=1e-9)
        assert res.set_point_activo
        assert any("SET_POINT" in msg for msg in res.advertencias)

    def test_fraccion_potencia_parcial(self):
        """Con fraccion=0.5, Q_eff = 0.5 × Q_nominal."""
        aux = Auxiliar(
            potencia_nominal_W=2000.0,
            temperatura_maxima_salida_K=353.15,
            fraccion_potencia_operacion=0.5,
        )
        res = calcular_auxiliar(aux, T_entrada_K=313.15, caudal_masico_kg_s=0.05)
        assert res.Q_efectivo_W == pytest.approx(1000.0, rel=1e-9)

    def test_T_salida_no_excede_T_max_genera_advertencia(self):
        """T_salida > T_max debe generar advertencia, no error."""

        m_dot = 0.005  # caudal muy bajo → ΔT muy grande
        aux = Auxiliar(
            potencia_nominal_W=5000.0,
            temperatura_maxima_salida_K=343.15,  # 70 °C
        )
        res = calcular_auxiliar(aux, T_entrada_K=313.15, caudal_masico_kg_s=m_dot)
        # ΔT = 5000 / (0.005 × 1007) ≈ 994 K → T_salida >> T_max
        assert any("T_SALIDA_EXCEDE_T_MAX" in msg for msg in res.advertencias)
