"""Mecanismo general de vigencia (core/huellas + ui/componentes/vigencia).

El resultado anual (S58) fue el primer caso, pero el mismo hueco lo tenían el
horizonte transitorio, los resultados de P7 (transitorio/constantes/ventana) y
los exports: se calculan de un lado y se muestran del otro sin recalcular, así
que cambiar la configuración después de calcular dejaba números viejos en
pantalla. Estos tests cubren el registro genérico —``registrar``/``estado``/
``invalidar``— y que cada derivado se invalide ante lo que efectivamente lo
determina.
"""

from __future__ import annotations

from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar
from core.camara import Camara, CargaProducto, GeometriaCamara
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, Proyecto, Tipologia
from ui.componentes import vigencia


def _proyecto() -> Proyecto:
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.emplazamiento = Emplazamiento()
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.0, alto_m=1.5),
        carga_producto=CargaProducto(producto_id="manzana"),
    )
    return p


def _auxiliar() -> Auxiliar:
    return Auxiliar(
        tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
        modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
        potencia_nominal_W=2000.0,
        set_point_T_K=328.15,
    )


class TestRegistrarEstado:
    def test_sin_resultado_no_hay_nada_desactualizado(self):
        val, vig = vigencia.estado(_proyecto(), {}, "constantes")
        assert val is None and vig is True

    def test_registrar_y_leer_vigente(self):
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar(estado_ss, "constantes", "RESULTADO", proy)
        val, vig = vigencia.estado(proy, estado_ss, "constantes")
        assert val == "RESULTADO" and vig is True

    def test_cambiar_una_seccion_invalida(self):
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar(estado_ss, "constantes", "RESULTADO", proy)
        proy.auxiliar = _auxiliar()  # entra a la huella de "constantes"
        val, vig = vigencia.estado(proy, estado_ss, "constantes")
        assert val == "RESULTADO", "el valor se devuelve igual, para poder avisar"
        assert vig is False

    def test_sin_hash_guardado_no_se_da_por_vigente(self):
        estado_ss = {vigencia.DERIVADOS["constantes"].clave: "RESULTADO"}
        _val, vig = vigencia.estado(_proyecto(), estado_ss, "constantes")
        assert vig is False

    def test_invalidar_borra_valor_y_hash(self):
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar(estado_ss, "constantes", "RESULTADO", proy)
        vigencia.invalidar(estado_ss, "constantes")
        assert vigencia.DERIVADOS["constantes"].clave not in estado_ss
        assert vigencia.DERIVADOS["constantes"].clave_hash not in estado_ss


class TestExtrasComoEntrada:
    """Las condiciones de borde (sliders de Constantes) son entradas tanto como
    el equipo: cambiar un slider sin recalcular deja el resultado viejo."""

    def test_cambiar_un_extra_invalida(self):
        proy = _proyecto()
        estado_ss: dict = {}
        extras = {"T_amb_K": 298.15, "I_g_W_m2": 800.0}
        vigencia.registrar(estado_ss, "constantes", "RESULTADO", proy, extras=extras)
        _val, vig = vigencia.estado(proy, estado_ss, "constantes", extras=extras)
        assert vig is True
        _val, vig = vigencia.estado(
            proy, estado_ss, "constantes", extras={"T_amb_K": 303.15, "I_g_W_m2": 800.0}
        )
        assert vig is False


class TestHorizonteNoDependeDelAuxiliar:
    """Las forzantes del horizonte son el aire ANTES del auxiliar: P7 le suma el
    auxiliar y el motor encima, así que configurar P5 no las invalida."""

    def test_agregar_auxiliar_no_invalida_el_horizonte(self):
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar(estado_ss, "horizonte", "FORZANTES", proy)
        proy.auxiliar = _auxiliar()
        _val, vig = vigencia.estado(proy, estado_ss, "horizonte")
        assert vig is True

    def test_agregar_auxiliar_si_invalida_el_transitorio(self):
        """El resultado transitorio de P7 sí incorpora el auxiliar."""
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar(estado_ss, "transitorio", "RES_TR", proy)
        proy.auxiliar = _auxiliar()
        _val, vig = vigencia.estado(proy, estado_ss, "transitorio")
        assert vig is False


class TestExtrasHorizonte:
    def test_solo_toma_kwargs_del_builder(self):
        meta = {
            "usar_ventana": False,
            "tipo_forzantes": "sintetico",
            "T_op_K": 328.15,
            "HR_op": 0.2,
            "T_amb_calc_K": 298.15,
            "n_dias_solicitado": 3,
            "I_g_max_W_m2": 0.0,
            "P_proyecto_Pa": 88000.0,
            "dias_consecutivos": False,
            # Derivados del cálculo, NO entradas: no deben entrar a la huella.
            "n_dias": 3,
            "modo_forzantes": "sintetico",
            "horizonte_tipo": "día típico repetido",
        }
        extras = vigencia.extras_horizonte(meta)
        assert "tipo_forzantes" in extras
        assert "n_dias" not in extras and "horizonte_tipo" not in extras

    def test_meta_vacio_da_extras_vacios(self):
        assert vigencia.extras_horizonte(None) == {}
        assert vigencia.extras_horizonte({}) == {}


class TestCompatAnual:
    """Los envoltorios del anual siguen andando sobre el mecanismo general."""

    def test_registrar_anual_y_vigencia(self):
        proy = _proyecto()
        estado_ss: dict = {}
        vigencia.registrar_anual(estado_ss, "RES_ANUAL", proy, politica=None)
        val, vig = vigencia.resultado_anual_vigente(proy, estado_ss)
        assert val == "RES_ANUAL" and vig is True

    def test_registrar_anual_guarda_la_politica(self):
        estado_ss: dict = {}
        vigencia.registrar_anual(estado_ss, "RES", _proyecto(), politica="POL")
        assert vigencia.politica_anual_guardada(estado_ss) == "POL"
