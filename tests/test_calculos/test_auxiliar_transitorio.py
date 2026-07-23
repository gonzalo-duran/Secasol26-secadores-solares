"""Tests del solver transitorio del auxiliar (mejora 19).

Verifica que ``calcular_auxiliar_transitorio`` aplica la lógica escalar paso a
paso, integra correctamente la energía sobre el horizonte, deduplica
advertencias y respeta ``disponible_nocturno`` cuando se provee la serie de
irradiancia.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.auxiliar_calc import (
    calcular_auxiliar,
    calcular_auxiliar_transitorio,
)
from core.auxiliar import (
    Auxiliar,
    ModoOperacionAuxiliar,
    TipoAuxiliar,
)


def _aux_resistencia_500W(
    *, set_point_C: float | None = None, disponible_nocturno: bool = True
) -> Auxiliar:
    return Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=500.0,
        temperatura_maxima_salida_K=343.15,
        set_point_T_K=None if set_point_C is None else 273.15 + set_point_C,
        fraccion_potencia_operacion=1.0,
        disponible_nocturno=disponible_nocturno,
    )


# ---------------------------------------------------------------------------
# Comportamiento básico — vectorización vs escalar
# ---------------------------------------------------------------------------


class TestVectorizacion:

    def test_serie_constante_replica_escalar(self):
        """T_ent constante → todos los pasos dan la misma T_sal que el escalar."""
        aux = _aux_resistencia_500W()
        t = np.linspace(0.0, 3600.0, 25)
        T_in = np.full(25, 320.0)
        m_dot = 0.030

        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=m_dot,
        )
        ref = calcular_auxiliar(aux, T_entrada_K=320.0, caudal_masico_kg_s=m_dot)
        assert res.T_salida_K == pytest.approx(ref.T_salida_K, abs=1e-6)
        assert res.delta_T_K == pytest.approx(ref.delta_T_K, abs=1e-6)
        assert res.Q_efectivo_W == pytest.approx(ref.Q_efectivo_W, abs=1e-6)

    def test_T_salida_es_T_entrada_mas_delta_T(self):
        aux = _aux_resistencia_500W()
        t = np.array([0.0, 1800.0, 3600.0])
        T_in = np.array([300.0, 310.0, 320.0])
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
        )
        np.testing.assert_allclose(res.T_salida_K, res.T_entrada_K + res.delta_T_K, atol=1e-9)


# ---------------------------------------------------------------------------
# Set-point
# ---------------------------------------------------------------------------


class TestSetPoint:

    def test_set_point_limita_Q_cuando_T_ent_se_acerca(self):
        """T_ent crece y se acerca al set_point → Q_eff baja a lo necesario."""
        aux = _aux_resistencia_500W(set_point_C=60.0)  # set_point = 333.15 K
        t = np.linspace(0.0, 3600.0, 13)
        T_in = np.linspace(290.0, 332.0, 13)  # va subiendo
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
        )
        # En el último paso (T_in muy cerca del set_point), Q_eff debería ser
        # mucho menor que la nominal (500 W).
        assert res.Q_efectivo_W[-1] < 100.0
        # Y en el primer paso (T_in lejos del set_point), Q_eff cerca de nominal.
        assert res.Q_efectivo_W[0] > 400.0

    def test_T_ent_supera_set_point_apaga_auxiliar(self):
        aux = _aux_resistencia_500W(set_point_C=40.0)  # set_point = 313.15 K
        t = np.array([0.0, 3600.0])
        T_in = np.array([320.0, 320.0])  # ya por encima
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
        )
        assert np.all(res.Q_efectivo_W == 0.0)
        assert res.activado_alguna_vez is False
        # Y la advertencia escalar se deduplica a una sola entrada.
        assert any("AUX_T_ENTRADA_SUPERA_SET_POINT" in a for a in res.advertencias_unicas)
        # No debe haber 2 copias.
        n_dup = sum("AUX_T_ENTRADA_SUPERA_SET_POINT" in a for a in res.advertencias_unicas)
        assert n_dup == 1


# ---------------------------------------------------------------------------
# disponible_nocturno
# ---------------------------------------------------------------------------


class TestDisponibleNocturno:

    def test_nocturno_off_apaga_de_noche(self):
        """Con disponible_nocturno=False y I_g=0 nocturno → Q_eff=0 en esos pasos."""
        aux = _aux_resistencia_500W(disponible_nocturno=False)
        t = np.linspace(0.0, 24 * 3600.0, 25)  # 24 h horarias
        T_in = np.full(25, 290.0)
        # Día: horas 6–18; noche: el resto.
        horas = np.arange(25)
        I_g = np.where((horas >= 6) & (horas <= 18), 800.0, 0.0)
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
            I_g_W_m2_serie=I_g,
        )
        # En la noche (h<6 y h>18) Q debe ser cero.
        mask_noche = (horas < 6) | (horas > 18)
        assert np.all(res.Q_efectivo_W[mask_noche] == 0.0)
        # De día sí debe haber aporte.
        assert np.all(res.Q_efectivo_W[~mask_noche] > 0.0)

    def test_nocturno_on_ignora_I_g(self):
        """Con disponible_nocturno=True, la serie de I_g no influye."""
        aux = _aux_resistencia_500W(disponible_nocturno=True)
        t = np.linspace(0.0, 24 * 3600.0, 25)
        T_in = np.full(25, 290.0)
        I_g = np.zeros(25)  # toda "noche"
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
            I_g_W_m2_serie=I_g,
        )
        # Disponible nocturno: aporta siempre.
        assert np.all(res.Q_efectivo_W > 0.0)


# ---------------------------------------------------------------------------
# Energía integrada
# ---------------------------------------------------------------------------


class TestEnergiaIntegrada:

    def test_Q_constante_E_aux_es_Q_por_dt(self):
        """Si Q es constante a lo largo del horizonte, E_MJ = Q · Δt / 1e6."""
        aux = _aux_resistencia_500W()
        t = np.linspace(0.0, 3600.0, 13)  # 1 h
        T_in = np.full(13, 300.0)
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
        )
        Q = res.Q_efectivo_W[0]
        E_esperada = Q * 3600.0 / 1e6
        assert res.E_aux_MJ == pytest.approx(E_esperada, rel=1e-6)

    def test_horas_activo_cuenta_solo_pasos_con_Q_positivo(self):
        aux = _aux_resistencia_500W(disponible_nocturno=False)
        t = np.linspace(0.0, 24 * 3600.0, 25)
        T_in = np.full(25, 290.0)
        horas = np.arange(25)
        I_g = np.where((horas >= 6) & (horas <= 18), 800.0, 0.0)
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_in,
            t_s=t,
            caudal_masico_kg_s=0.030,
            I_g_W_m2_serie=I_g,
        )
        # 13 horas activas (06–18 inclusive).
        # Trapezoidal sobre el indicador 1_{Q>0} → ~12 h (porque los puntos
        # borde aportan media unidad cada uno).
        assert 11 * 3600 <= res.horas_activo_s <= 13 * 3600
        assert 0.4 < res.fraccion_horas_activo < 0.6


# ---------------------------------------------------------------------------
# Errores de entrada
# ---------------------------------------------------------------------------


class TestErrores:

    def test_longitud_inconsistente_levanta(self):
        aux = _aux_resistencia_500W()
        with pytest.raises(ValueError, match="AUX_TR_LONGITUD_INCONSISTENTE"):
            calcular_auxiliar_transitorio(
                aux,
                T_entrada_K_serie=np.zeros(5),
                t_s=np.zeros(7),
                caudal_masico_kg_s=0.030,
            )

    def test_caudal_no_positivo_levanta(self):
        aux = _aux_resistencia_500W()
        with pytest.raises(ValueError, match="AUX_TR_CAUDAL_NO_POSITIVO"):
            calcular_auxiliar_transitorio(
                aux,
                T_entrada_K_serie=np.zeros(3),
                t_s=np.zeros(3),
                caudal_masico_kg_s=0.0,
            )


# ---------------------------------------------------------------------------
# Agregación de advertencias por código (S58)
# ---------------------------------------------------------------------------


class TestAgregacionDeAdvertencias:
    """Un setpoint inalcanzable no puede producir un aviso por hora.

    Los mensajes de la corrida escalar llevan el valor de la hora ("T_salida
    real: 12.5 °C"), así que deduplicar por string exacto no filtraba nada:
    sobre un año, la corrida real del usuario daba **230 avisos** casi idénticos
    que tapaban los dos que sí eran distintos (S58). Mismo bug que el del
    encadenado de lotes en S57, en otro módulo.
    """

    def _serie_con_setpoint_inalcanzable(self, n=200):
        """Aire frío y variable + resistencia chica: el setpoint nunca se alcanza."""
        aux = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=500.0,
            set_point_T_K=353.15,  # 80 °C, fuera de alcance
            temperatura_maxima_salida_K=373.15,
            disponible_nocturno=True,
        )
        t_s = np.arange(n, dtype=float) * 3600.0
        # Temperaturas todas distintas → cada hora genera un mensaje distinto.
        T_ent = 280.0 + np.arange(n, dtype=float) * 0.1
        return calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=T_ent,
            t_s=t_s,
            caudal_masico_kg_s=0.030,
        )

    def test_un_solo_aviso_por_codigo(self):
        res = self._serie_con_setpoint_inalcanzable()
        codigos = [a.split(":", 1)[0].strip() for a in res.advertencias_unicas]
        assert len(codigos) == len(set(codigos)), f"códigos repetidos: {codigos}"
        assert len(res.advertencias_unicas) <= 2, (
            f"200 horas produjeron {len(res.advertencias_unicas)} avisos: "
            "la agregación por código no está filtrando"
        )

    def test_el_aviso_dice_en_cuantas_horas_paso(self):
        """'Se repitió en N de M horas' es información, no ruido."""
        res = self._serie_con_setpoint_inalcanzable()
        assert any("AUX_SET_POINT_NO_ALCANZABLE" in a for a in res.advertencias_unicas)
        mensaje = next(a for a in res.advertencias_unicas if "AUX_SET_POINT" in a)
        assert "Se repitió en" in mensaje and "horas de operación" in mensaje

    def test_sin_repeticion_no_agrega_el_conteo(self):
        """Un aviso que dispara una sola vez se muestra tal cual."""
        aux = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=500.0,
            set_point_T_K=353.15,
            temperatura_maxima_salida_K=373.15,
            disponible_nocturno=True,
        )
        res = calcular_auxiliar_transitorio(
            aux,
            T_entrada_K_serie=np.array([290.0, 290.0]),
            t_s=np.array([0.0, 3600.0]),
            caudal_masico_kg_s=0.030,
        )
        for a in res.advertencias_unicas:
            if "Se repitió" in a:
                assert " de 2 horas" in a
