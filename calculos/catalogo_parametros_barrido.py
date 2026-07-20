"""Catálogo de parámetros barrideables para las corridas paramétricas de P7.

Define la lista curada de parámetros que el usuario puede variar en un barrido
paramétrico, junto con su metadata: ``path`` al campo de la dataclass del
``Proyecto``, unidades, conversiones UI↔SI, rango admisible y filtros por
tipología y modo de cálculo.

Está en código Python (no YAML) a propósito:
    - Los ``path`` son referencias a campos de dataclasses; un typo se detecta
      temprano vía ``AttributeError`` al resolverlo (ver
      ``calculos/barrido_parametrico.py``), no en runtime de la UI.
    - Las conversiones (``si_a_ui``/``ui_a_si``) y ``transform_pre_set`` son
      callables que no serializan bien a YAML.

Sobre las conversiones:
    - ``si_a_ui`` / ``ui_a_si`` convierten entre la unidad que ve el usuario y
      el SI interno. Para ángulos reutilizan ``calculos/conversiones_angulo``.
      Para los dos forzantes escalares (HR, T_amb) las fórmulas son triviales y
      se declaran inline acá (este módulo es metadata declarativa, no lógica de
      cálculo; y ``calculos/`` no puede importar de ``ui/``).
    - ``transform_pre_set`` se aplica al valor SI ya resuelto, justo antes de
      asignarlo al campo (ej. ``int`` para contadores de colectores). ``None``
      cuando no hace falta.

Casos especiales — paths con prefijo ``"forzante:"`` (``HR_camara``, ``T_amb``):
    no mutan el ``Proyecto``; el barrido los inyecta como argumentos del modo
    Constantes (``calcular_todo``). Por eso solo soportan el modo ``constantes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from calculos.conversiones_angulo import acimut_duffie_a_ui360, acimut_ui360_a_duffie
from core.proyecto import Tipologia

# --- Conjuntos reutilizables de filtros -----------------------------------

_TODAS_TIPOLOGIAS: frozenset[Tipologia] = frozenset(Tipologia)
_CON_COLECTOR: frozenset[Tipologia] = frozenset({Tipologia.ARMARIO, Tipologia.GRAN_ESCALA})

_TODOS_MODOS: frozenset[str] = frozenset({"constantes", "transitorio", "anual"})
_SOLO_CONSTANTES: frozenset[str] = frozenset({"constantes"})
# La pendiente/acimut solo afectan el resultado cuando la POA se calcula a
# partir del clima (transitorio/anual). En Constantes la irradiancia en plano
# es un input directo (``calcular_todo(..., I_g_W_m2, ...)``), así que variarlos
# no tendría efecto.
_TRANSITORIO_ANUAL: frozenset[str] = frozenset({"transitorio", "anual"})


def _identidad(valor: float) -> float:
    """Conversión identidad (la unidad UI coincide con la SI)."""
    return valor


# --- Dataclass de parámetro -----------------------------------------------


@dataclass(frozen=True)
class ParametroBarrido:
    """Definición de un parámetro barrideable.

    Attributes:
        id: Identificador único y estable (snake_case).
        label: Etiqueta legible para el selectbox de la UI.
        path: Ruta punteada al campo dentro del ``Proyecto`` (ej.
            ``"camara.flujo.caudal_masico_kg_s"``), o ``"forzante:<nombre>"``
            para parámetros que se inyectan como argumento del modo Constantes.
        unidad_ui: Unidad mostrada al usuario (ej. ``"kg/s"``, ``"°"``).
        unidad_si: Unidad del valor interno SI.
        si_a_ui: Convierte un valor SI a la unidad de la UI (para mostrar).
        ui_a_si: Convierte un valor en unidad de UI al SI interno.
        valor_min_si: Cota inferior admisible del valor SI.
        valor_max_si: Cota superior admisible del valor SI.
        paso_sugerido_si: Paso sugerido para el slider/number_input (en SI).
        transform_pre_set: Coerción aplicada al valor SI antes de asignarlo al
            campo (ej. ``int``). ``None`` si no hace falta.
        tipologias: Tipologías para las que el parámetro es aplicable.
        modos_soportados: Modos de cálculo en los que tiene efecto.
        descripcion_corta: Ayuda breve para la UI.
    """

    id: str
    label: str
    path: str
    unidad_ui: str
    unidad_si: str
    si_a_ui: Callable[[float], float]
    ui_a_si: Callable[[float], float]
    valor_min_si: float
    valor_max_si: float
    paso_sugerido_si: float
    transform_pre_set: Callable[[float], Any] | None
    tipologias: frozenset[Tipologia]
    modos_soportados: frozenset[str]
    descripcion_corta: str

    @property
    def es_forzante(self) -> bool:
        """True si el parámetro se inyecta como forzante (no muta el Proyecto)."""
        return self.path.startswith("forzante:")

    @property
    def nombre_forzante(self) -> str | None:
        """Nombre del forzante (parte tras ``forzante:``) o ``None``."""
        return self.path.split(":", 1)[1] if self.es_forzante else None


# --- Catálogo v1 (15 parámetros) ------------------------------------------

CATALOGO_PARAMETROS: tuple[ParametroBarrido, ...] = (
    ParametroBarrido(
        id="caudal_masico",
        label="Caudal másico de aire",
        path="camara.flujo.caudal_masico_kg_s",
        unidad_ui="kg/s",
        unidad_si="kg/s",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.005,
        valor_max_si=0.20,
        paso_sugerido_si=0.005,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Caudal de aire seco que atraviesa la cámara.",
    ),
    ParametroBarrido(
        id="largo_colector",
        label="Largo del colector",
        path="colector.unidad.largo_m",
        unidad_ui="m",
        unidad_si="m",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.5,
        valor_max_si=6.0,
        paso_sugerido_si=0.25,
        transform_pre_set=None,
        tipologias=_CON_COLECTOR,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Longitud del módulo de colector en la dirección del flujo.",
    ),
    ParametroBarrido(
        id="velocidad_diseno",
        label="Velocidad de diseño en colector",
        path="colector.unidad.velocidad_diseno_ms",
        unidad_ui="m/s",
        unidad_si="m/s",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.2,
        valor_max_si=5.0,
        paso_sugerido_si=0.1,
        transform_pre_set=None,
        tipologias=_CON_COLECTOR,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Velocidad del aire en el canal del colector (cada rama del banco).",
    ),
    ParametroBarrido(
        id="n_colectores_serie",
        label="N° de colectores en serie",
        path="colector.banco.n_serie",
        unidad_ui="módulos",
        unidad_si="módulos",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=1,
        valor_max_si=10,
        paso_sugerido_si=1,
        transform_pre_set=int,
        tipologias=_CON_COLECTOR,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Cantidad de módulos de colector conectados en serie.",
    ),
    ParametroBarrido(
        id="n_colectores_paralelo",
        label="N° de colectores en paralelo",
        path="colector.banco.n_paralelo",
        unidad_ui="ramas",
        unidad_si="ramas",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=1,
        valor_max_si=20,
        paso_sugerido_si=1,
        transform_pre_set=int,
        tipologias=_CON_COLECTOR,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Cantidad de ramas de colector en paralelo.",
    ),
    ParametroBarrido(
        id="pendiente_colector",
        label="Pendiente del colector",
        path="emplazamiento.pendiente_colector_deg",
        unidad_ui="°",
        unidad_si="°",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.0,
        valor_max_si=90.0,
        paso_sugerido_si=5.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TRANSITORIO_ANUAL,
        descripcion_corta="Inclinación del plano del colector respecto a la horizontal.",
    ),
    ParametroBarrido(
        id="acimut_colector",
        label="Acimut del colector",
        path="emplazamiento.acimut_colector_deg",
        unidad_ui="° (UI360)",
        unidad_si="° (Duffie)",
        si_a_ui=acimut_duffie_a_ui360,
        ui_a_si=acimut_ui360_a_duffie,
        valor_min_si=-180.0,
        valor_max_si=180.0,
        paso_sugerido_si=15.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TRANSITORIO_ANUAL,
        descripcion_corta="Orientación acimutal del plano del colector (barrido lineal en Duffie).",
    ),
    ParametroBarrido(
        id="pendiente_techo_camara",
        label="Pendiente del techo de la cámara",
        path="camara.geometria.pendiente_techo_deg",
        unidad_ui="°",
        unidad_si="°",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.0,
        valor_max_si=60.0,
        paso_sugerido_si=5.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TRANSITORIO_ANUAL,
        descripcion_corta=(
            "Inclinación del techo a un agua de la cámara (independiente del "
            "colector). En modo Transitorio requiere que el barrido reconstruya "
            "las forzantes por punto (forzantes_builder) — no tiene efecto si "
            "se reutiliza una forzante_base congelada."
        ),
    ),
    ParametroBarrido(
        id="acimut_camara",
        label="Acimut de la cámara",
        path="camara.geometria.acimut_camara_deg",
        unidad_ui="° (UI360)",
        unidad_si="° (Duffie)",
        si_a_ui=acimut_duffie_a_ui360,
        ui_a_si=acimut_ui360_a_duffie,
        valor_min_si=-180.0,
        valor_max_si=180.0,
        paso_sugerido_si=15.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TRANSITORIO_ANUAL,
        descripcion_corta=(
            "Orientación acimutal de la cámara (independiente del colector; "
            "define el acimut de todas sus caras). Mismo requisito de "
            "forzantes_builder que 'pendiente_techo_camara' en Transitorio."
        ),
    ),
    ParametroBarrido(
        id="masa_producto",
        label="Masa de producto fresco",
        path="camara.carga_producto.masa_total_kg",
        unidad_ui="kg",
        unidad_si="kg",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.5,
        valor_max_si=500.0,
        paso_sugerido_si=1.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Masa total de producto fresco a secar en la tanda.",
    ),
    ParametroBarrido(
        id="area_bandeja",
        label="Área de bandeja (área efectiva de intercambio)",
        path="camara.bandejas.area_bandeja_m2",
        unidad_ui="m²",
        unidad_si="m²",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.05,
        valor_max_si=50.0,
        paso_sugerido_si=0.1,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta=(
            "Área de intercambio aire↔producto por bandeja. Multiplica tanto el calor "
            "sensible (h·A) como la evaporación (K_m·A), así que es el parámetro "
            "físicamente interpretable para calibrar contra un ensayo: el área efectiva "
            "de una capa de rodajas apiladas puede ser varias veces la de la bandeja."
        ),
    ),
    ParametroBarrido(
        id="humedad_inicial",
        label="Humedad inicial del producto",
        path="camara.carga_producto.humedad_inicial_X",
        unidad_ui="kg/kg ms",
        unidad_si="kg/kg ms",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.5,
        valor_max_si=10.0,
        paso_sugerido_si=0.5,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Contenido de humedad inicial en base seca.",
    ),
    ParametroBarrido(
        id="humedad_objetivo",
        label="Humedad objetivo del producto",
        path="camara.carga_producto.humedad_objetivo_X",
        unidad_ui="kg/kg ms",
        unidad_si="kg/kg ms",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.02,
        valor_max_si=1.0,
        paso_sugerido_si=0.02,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Contenido de humedad final objetivo en base seca.",
    ),
    ParametroBarrido(
        id="largo_camara",
        label="Largo de la cámara",
        path="camara.geometria.largo_m",
        unidad_ui="m",
        unidad_si="m",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.3,
        valor_max_si=10.0,
        paso_sugerido_si=0.2,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Dimensión de la cámara en la dirección del flujo.",
    ),
    ParametroBarrido(
        id="alto_camara",
        label="Alto de la cámara",
        path="camara.geometria.alto_m",
        unidad_ui="m",
        unidad_si="m",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.3,
        valor_max_si=5.0,
        paso_sugerido_si=0.1,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Altura libre interna de la cámara.",
    ),
    ParametroBarrido(
        id="ancho_camara",
        label="Ancho de la cámara",
        path="camara.geometria.ancho_m",
        unidad_ui="m",
        unidad_si="m",
        si_a_ui=_identidad,
        ui_a_si=_identidad,
        valor_min_si=0.3,
        valor_max_si=10.0,
        paso_sugerido_si=0.2,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_TODOS_MODOS,
        descripcion_corta="Dimensión de la cámara transversal al flujo.",
    ),
    ParametroBarrido(
        id="HR_camara",
        label="Humedad relativa de cámara",
        path="forzante:HR_camara",
        unidad_ui="%",
        unidad_si="fracción",
        si_a_ui=lambda fraccion: fraccion * 100.0,
        ui_a_si=lambda porcentaje: porcentaje / 100.0,
        valor_min_si=0.05,
        valor_max_si=0.95,
        paso_sugerido_si=0.05,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_SOLO_CONSTANTES,
        descripcion_corta="HR de operación de la cámara (solo modo Constantes).",
    ),
    ParametroBarrido(
        id="T_amb",
        label="Temperatura ambiente",
        path="forzante:T_amb",
        unidad_ui="°C",
        unidad_si="K",
        si_a_ui=lambda kelvin: kelvin - 273.15,
        ui_a_si=lambda celsius: celsius + 273.15,
        valor_min_si=273.15,
        valor_max_si=323.15,
        paso_sugerido_si=1.0,
        transform_pre_set=None,
        tipologias=_TODAS_TIPOLOGIAS,
        modos_soportados=_SOLO_CONSTANTES,
        descripcion_corta="Temperatura ambiente representativa (solo modo Constantes).",
    ),
)

# Índice por id para acceso O(1).
PARAMETROS_POR_ID: dict[str, ParametroBarrido] = {p.id: p for p in CATALOGO_PARAMETROS}


def obtener_parametro(parametro_id: str) -> ParametroBarrido:
    """Devuelve el parámetro de id ``parametro_id``.

    Raises:
        KeyError: Si el id no existe en el catálogo.
    """
    try:
        return PARAMETROS_POR_ID[parametro_id]
    except KeyError as exc:
        raise KeyError(
            f"BARRIDO_PARAMETRO_DESCONOCIDO: '{parametro_id}' no está en el catálogo."
        ) from exc


def parametros_para_tipologia(tipologia: Tipologia, modo: str) -> list[ParametroBarrido]:
    """Filtra el catálogo por tipología y modo de cálculo.

    Args:
        tipologia: Tipología del proyecto.
        modo: Modo de cálculo activo (``"constantes"``, ``"transitorio"`` o
            ``"anual"``).

    Returns:
        Lista de parámetros aplicables, en el orden del catálogo.
    """
    return [
        p for p in CATALOGO_PARAMETROS if tipologia in p.tipologias and modo in p.modos_soportados
    ]
