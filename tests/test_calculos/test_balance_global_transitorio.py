"""Tests de la pipeline transitoria de P7 (mejora 19).

Verifica que ``calcular_todo_transitorio``:
  - propaga el horizonte de cámara hasta el balance completo;
  - sin auxiliar, deja las forzantes intactas;
  - con auxiliar SERIE_POSCOLECTOR, eleva T_ent de cámara hora a hora;
  - integra correctamente energía solar útil, auxiliar y motor;
  - falla con coherencia clara si la cámara está en modo capa fina.
"""

from __future__ import annotations

import numpy as np
import pytest

from calculos.balance_global import (
    ResultadosCompletosTransitorio,
    armar_forzantes_aire,
    calcular_todo_transitorio,
)
from calculos.psicrometria import humedad_absoluta
from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    GeometriaCamara,
)
from core.colector import Colector
from core.motor import Motor, TipoAccionamiento
from core.proyecto import (
    Configuracion, Meta, ModoAnalisis, Proyecto, Tipologia,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _forzantes_dia_sintetico(n_horas: int = 24):
    """Forzantes 1 día — T_sal_col oscilante 295–325 K, ω 0.008, I_g coseno."""
    t = np.linspace(0.0, n_horas * 3600.0, n_horas + 1)
    horas = t / 3600.0
    # T_sal_col semi-senoidal centrada al mediodía
    T_amb = 290.0 + 8.0 * np.sin(2 * np.pi * (horas - 6) / 24)
    T_sal_col = T_amb + np.maximum(0.0, 25.0 * np.sin(np.pi * np.clip((horas - 6) / 12, 0, 1)))
    I_g = np.maximum(0.0, 900.0 * np.sin(np.pi * np.clip((horas - 6) / 12, 0, 1)))
    omega = humedad_absoluta(0.4, 295.0)
    return armar_forzantes_aire(
        modo="diario",
        T_salida_colector_K=T_sal_col,
        omega_ambiente=np.full(n_horas + 1, omega),
        m_dot_aire_seco_kg_s=0.030,
        T_amb_K=T_amb,
        v_viento_ms=np.full(n_horas + 1, 2.0),
        I_g_W_m2=I_g,
    )


def _proyecto_armario(*, con_auxiliar: bool = False, con_motor: bool = True,
                       set_point_aux_C: float | None = None,
                       disponible_nocturno: bool = True) -> Proyecto:
    p = Proyecto(
        meta=Meta(nombre="Test P7 TR", autor="pytest"),
        configuracion=Configuracion(
            tipologia=Tipologia.ARMARIO,
            modo_analisis=ModoAnalisis.DIARIO,
        ),
    )
    p.colector = Colector()
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=1.5, ancho_m=1.0, alto_m=1.5),
        bandejas=ConfiguracionBandejas(
            n_bandejas=3, area_bandeja_m2=0.5,
            espesor_capa_m=0.02, separacion_entre_bandejas_m=0.15,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=0.030),
        carga_producto=CargaProducto(
            producto_id="manzana",
            masa_total_kg=5.0,
            humedad_inicial_X=4.6,
            humedad_objetivo_X=0.15,
            modelo_capa_fina="logaritmico",
        ),
        modo_calculo="termodinamico",
    )
    if con_auxiliar:
        p.auxiliar = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=600.0,
            temperatura_maxima_salida_K=343.15,
            set_point_T_K=None if set_point_aux_C is None else 273.15 + set_point_aux_C,
            fraccion_potencia_operacion=1.0,
            disponible_nocturno=disponible_nocturno,
        )
    if con_motor:
        p.motor = Motor(
            tipo_accionamiento=TipoAccionamiento.MOTOR_ELECTRICO,
            caudal_volumetrico_m3_s=0.025,
            perdida_carga_total_Pa=80.0,
        )
    return p


# ---------------------------------------------------------------------------
# Sin auxiliar — el horizonte se propaga intacto
# ---------------------------------------------------------------------------


class TestSinAuxiliar:

    def test_forzantes_aplicadas_son_iguales_a_base(self):
        proy = _proyecto_armario(con_auxiliar=False)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert isinstance(res, ResultadosCompletosTransitorio)
        assert res.auxiliar is None
        assert res.energia_auxiliar_MJ == 0.0
        np.testing.assert_allclose(
            res.forzantes_aplicadas.T_ent_K, res.forzantes_base.T_ent_K,
        )

    def test_motor_electrico_se_integra(self):
        proy = _proyecto_armario(con_auxiliar=False, con_motor=True)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        # P_elec · 24 h
        if res.motor_P_elec_W > 0:
            esperado = res.motor_P_elec_W * 24 * 3600.0 / 1e6
            assert res.energia_motor_MJ == pytest.approx(esperado, rel=1e-6)
        else:
            # Si el motor no calculó potencia, energía es 0.
            assert res.energia_motor_MJ == 0.0


# ---------------------------------------------------------------------------
# Con auxiliar SERIE_POSCOLECTOR — T_ent aumenta hora a hora
# ---------------------------------------------------------------------------


class TestConAuxiliar:

    def test_forzantes_aplicadas_T_ent_supera_base(self):
        """ΔT_aux > 0 → T_ent aplicada > T_ent base en al menos algún paso."""
        proy = _proyecto_armario(con_auxiliar=True, set_point_aux_C=70.0)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert res.auxiliar is not None
        assert res.auxiliar.activado_alguna_vez is True
        assert np.any(res.forzantes_aplicadas.T_ent_K > res.forzantes_base.T_ent_K)
        # ΔT debe coincidir con la serie del auxiliar.
        delta = res.forzantes_aplicadas.T_ent_K - res.forzantes_base.T_ent_K
        np.testing.assert_allclose(delta, res.auxiliar.delta_T_K, atol=1e-9)

    def test_E_aux_positiva_si_auxiliar_aporta(self):
        proy = _proyecto_armario(con_auxiliar=True, set_point_aux_C=70.0)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert res.energia_auxiliar_MJ > 0.0
        # Fracción solar < 1 cuando hay auxiliar activo
        if res.energia_solar_util_MJ > 0:
            assert 0.0 < res.fraccion_solar < 1.0

    def test_disponible_nocturno_false_apaga_de_noche(self):
        """Con disponible_nocturno=False, ΔT_aux=0 cuando I_g=0."""
        proy = _proyecto_armario(
            con_auxiliar=True, set_point_aux_C=70.0, disponible_nocturno=False,
        )
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        mask_noche = fz.I_g_W_m2 <= 10.0
        if mask_noche.any():
            assert np.all(res.auxiliar.delta_T_K[mask_noche] == 0.0)

    def test_set_point_no_supera_T_ent_max(self):
        """T_sal_aux ≤ set_point en todos los pasos (control proporcional ideal)."""
        proy = _proyecto_armario(con_auxiliar=True, set_point_aux_C=70.0)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        # T_salida del auxiliar = T_entrada + delta_T
        T_sal_aux = res.auxiliar.T_entrada_K + res.auxiliar.delta_T_K
        # En ningún paso debe superar set_point + un margen (≈ no alcanzable).
        # Como con potencia 600 W y caudal 0.03 kg/s la nominal levanta ~20 K,
        # cuando T_ent + 20 > set_point el control limita: T_sal ≈ set_point.
        # Si T_ent ya está por encima del set_point, T_sal = T_ent (sin aporte).
        # Por lo tanto T_sal_aux ≤ max(T_ent, set_point + ε).
        set_point_K = 273.15 + 70.0
        assert np.all(T_sal_aux <= np.maximum(res.auxiliar.T_entrada_K, set_point_K) + 1e-6)


# ---------------------------------------------------------------------------
# Energía solar útil
# ---------------------------------------------------------------------------


class TestEnergiaSolar:

    def test_E_sol_positiva_cuando_T_sal_col_supera_T_amb(self):
        proy = _proyecto_armario(con_auxiliar=False)
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert res.energia_solar_util_MJ > 0.0

    def test_E_sol_no_es_negativa_aunque_T_amb_supere_T_sal_col(self):
        """En nodos nocturnos con T_sal_col = T_amb, el integral debe quedar ≥ 0."""
        proy = _proyecto_armario(con_auxiliar=False)
        # Forzantes "todo noche": T_sal_col = T_amb, I_g = 0
        n = 13
        t = np.linspace(0.0, 12 * 3600.0, n)
        T_amb = np.full(n, 290.0)
        T_sal_col = T_amb.copy()
        omega = np.full(n, humedad_absoluta(0.4, 290.0))
        fz = armar_forzantes_aire(
            modo="diario",
            T_salida_colector_K=T_sal_col,
            omega_ambiente=omega,
            m_dot_aire_seco_kg_s=0.030,
            T_amb_K=T_amb,
            v_viento_ms=np.full(n, 2.0),
            I_g_W_m2=np.zeros(n),
        )
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert res.energia_solar_util_MJ == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Coherencia
# ---------------------------------------------------------------------------


class TestCoherencia:

    def test_modo_capa_fina_levanta_error_coherente(self):
        proy = _proyecto_armario(con_auxiliar=False)
        proy.camara.modo_calculo = "capa_fina"
        fz = _forzantes_dia_sintetico()
        res = calcular_todo_transitorio(proy, forzantes_base=fz, n_dias=1)
        assert res.camara is None
        assert any("BG_TR_MODO_CAMARA_INCOMPATIBLE" in e for e in res.errores)
