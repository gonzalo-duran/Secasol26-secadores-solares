"""Catálogo de KPIs extraíbles de un resultado de simulación para los barridos.

Cada :class:`KpiBarrido` envuelve un *extractor*: una función tolerante que,
dado un objeto de resultado (``ResultadosCompletos`` en Constantes,
``ResultadosCompletosTransitorio`` en Transitorio, o ``ResultadosAnualCamara``
en Operación anual), devuelve un escalar ``float`` o ``None`` cuando el campo
no aplica a ese modo. Esa tolerancia (vía ``getattr`` con default) permite que
el mismo catálogo de KPIs sirva a los tres modos sin ramificar en la UI.

Dos grupos:
    - ``KPIS_FIJOS``: los 6 indicadores que siempre se grafican.
    - ``KPIS_AVANZADOS``: extras opt-in (checkbox en un expander de P7).

El campo ``modos_validos`` de cada KPI gobierna en qué modos se ofrece.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from calculos.balance_global import resumen_camara

# --- Conjuntos de modos -----------------------------------------------------

_CONST = "constantes"
_TRANS = "transitorio"
_ANUAL = "anual"
_CONST_TRANS: frozenset[str] = frozenset({_CONST, _TRANS})
_TODOS: frozenset[str] = frozenset({_CONST, _TRANS, _ANUAL})


# --- Dataclass de KPI -------------------------------------------------------


@dataclass(frozen=True)
class KpiBarrido:
    """Definición de un KPI extraíble de un resultado de simulación.

    Attributes:
        id: Identificador único y estable.
        label: Etiqueta legible para tablas y gráficas.
        unidad: Unidad del valor devuelto por el extractor.
        extractor: ``Callable[[resultado], float | None]`` tolerante al modo.
        modos_validos: Modos en los que el KPI tiene sentido.
        formato: Formato de impresión estilo ``str.format`` (ej. ``".2f"``).
    """

    id: str
    label: str
    unidad: str
    extractor: Callable[[Any], float | None]
    modos_validos: frozenset[str]
    formato: str


# --- Helpers de extracción --------------------------------------------------


def _attr(res: Any, nombre: str) -> float | None:
    """getattr tolerante: devuelve el valor o None si no existe/está None."""
    valor = getattr(res, nombre, None)
    return valor if valor is None else float(valor)


def _camara_de(res: Any) -> Any | None:
    """Devuelve el resultado de cámara del resultado global, o None."""
    return getattr(res, "camara", None)


def _ext_t_secado_h(res: Any) -> float | None:
    # Modo anual: promedio mensual ya en horas.
    promedio = getattr(res, "t_secado_promedio_h", None)
    if promedio is not None:
        return float(promedio)
    cam = _camara_de(res)
    if cam is None:
        return None
    t_s = resumen_camara(cam)["t_secado_s"]
    return t_s / 3600.0 if t_s is not None else None


def _ext_masa_agua_evap(res: Any) -> float | None:
    cam = _camara_de(res)
    if cam is None:
        return None
    return resumen_camara(cam)["masa_agua_kg"]


def _ext_eta_termica_colector(res: Any) -> float | None:
    col = getattr(res, "colector", None)
    if col is None:
        return None
    return _attr(col, "eta_termica")


def _ext_T_salida_colector(res: Any) -> float | None:
    col = getattr(res, "colector", None)
    if col is None:
        return None
    return _attr(col, "T_salida_K")


def _ext_Re_colector(res: Any) -> float | None:
    col = getattr(res, "colector", None)
    if col is None:
        return None
    return _attr(col, "Re_medio")


def _ext_horas_HR_alta_h(res: Any) -> float | None:
    seg = getattr(res, "horas_HR_alta_s", None)
    return seg / 3600.0 if seg is not None else None


# --- KPIs fijos (6) ---------------------------------------------------------

KPIS_FIJOS: tuple[KpiBarrido, ...] = (
    KpiBarrido(
        id="t_secado_h",
        label="Tiempo de secado",
        unidad="h",
        extractor=_ext_t_secado_h,
        modos_validos=_TODOS,
        formato=".2f",
    ),
    KpiBarrido(
        id="masa_agua_evap_kg",
        label="Agua evaporada",
        unidad="kg",
        extractor=_ext_masa_agua_evap,
        modos_validos=_CONST_TRANS,
        formato=".3f",
    ),
    KpiBarrido(
        id="cop_secado",
        label="COP de secado",
        unidad="—",
        extractor=lambda res: _attr(res, "COP_secado"),
        modos_validos=_CONST_TRANS,
        formato=".2f",
    ),
    KpiBarrido(
        id="fraccion_solar",
        label="Fracción solar",
        unidad="—",
        extractor=lambda res: _attr(res, "fraccion_solar"),
        modos_validos=_CONST_TRANS,
        formato=".3f",
    ),
    KpiBarrido(
        id="eta_termica_colector",
        label="η térmica del colector",
        unidad="—",
        extractor=_ext_eta_termica_colector,
        modos_validos=frozenset({_CONST}),
        formato=".3f",
    ),
    KpiBarrido(
        id="energia_total_MJ",
        label="Energía total",
        unidad="MJ",
        extractor=lambda res: _attr(res, "energia_total_MJ"),
        modos_validos=_CONST_TRANS,
        formato=".2f",
    ),
)


# --- KPIs avanzados (opt-in) ------------------------------------------------

KPIS_AVANZADOS: tuple[KpiBarrido, ...] = (
    KpiBarrido(
        id="T_salida_colector_K",
        label="T salida del colector",
        unidad="K",
        extractor=_ext_T_salida_colector,
        modos_validos=frozenset({_CONST}),
        formato=".1f",
    ),
    KpiBarrido(
        id="T_prod_max_K",
        label="T máx del producto",
        unidad="K",
        extractor=lambda res: _attr(res, "T_prod_max_K"),
        modos_validos=frozenset({_TRANS}),
        formato=".1f",
    ),
    KpiBarrido(
        id="Re_colector",
        label="Re medio en colector",
        unidad="—",
        extractor=_ext_Re_colector,
        modos_validos=frozenset({_CONST}),
        formato=".0f",
    ),
    KpiBarrido(
        id="energia_solar_util_MJ",
        label="Energía solar útil",
        unidad="MJ",
        extractor=lambda res: _attr(res, "energia_solar_util_MJ"),
        modos_validos=_CONST_TRANS,
        formato=".2f",
    ),
    KpiBarrido(
        id="energia_auxiliar_MJ",
        label="Energía auxiliar",
        unidad="MJ",
        extractor=lambda res: _attr(res, "energia_auxiliar_MJ"),
        modos_validos=_CONST_TRANS,
        formato=".2f",
    ),
    KpiBarrido(
        id="masa_producto_seco_kg",
        label="Masa de producto seco",
        unidad="kg",
        extractor=lambda res: _attr(res, "masa_producto_seco_kg"),
        modos_validos=_CONST_TRANS,
        formato=".3f",
    ),
    KpiBarrido(
        id="horas_HR_alta_h",
        label="Horas con HR alta",
        unidad="h",
        extractor=_ext_horas_HR_alta_h,
        modos_validos=frozenset({_TRANS}),
        formato=".1f",
    ),
    KpiBarrido(
        id="kg_secados_anual",
        label="Producto secado anual",
        unidad="kg/año",
        extractor=lambda res: _attr(res, "kg_secados_anual"),
        modos_validos=frozenset({_ANUAL}),
        formato=".0f",
    ),
    KpiBarrido(
        id="eta_drying_anual_media",
        label="η drying anual media",
        unidad="—",
        extractor=lambda res: _attr(res, "eta_drying_anual_media"),
        modos_validos=frozenset({_ANUAL}),
        formato=".3f",
    ),
    KpiBarrido(
        id="eta_pickup_anual_media",
        label="η pickup anual media",
        unidad="—",
        extractor=lambda res: _attr(res, "eta_pickup_anual_media"),
        modos_validos=frozenset({_ANUAL}),
        formato=".3f",
    ),
    KpiBarrido(
        id="eta_termica_anual_media",
        label="η térmica anual media",
        unidad="—",
        extractor=lambda res: _attr(res, "eta_termica_anual_media"),
        modos_validos=frozenset({_ANUAL}),
        formato=".3f",
    ),
    KpiBarrido(
        id="eta_total_anual_media",
        label="η total anual media",
        unidad="—",
        extractor=lambda res: _attr(res, "eta_total_anual_media"),
        modos_validos=frozenset({_ANUAL}),
        formato=".3f",
    ),
    KpiBarrido(
        id="E_solar_anual_MJ",
        label="Energía solar anual",
        unidad="MJ/año",
        extractor=lambda res: _attr(res, "E_solar_anual_MJ"),
        modos_validos=frozenset({_ANUAL}),
        formato=".0f",
    ),
    KpiBarrido(
        id="E_auxiliar_anual_MJ",
        label="Energía auxiliar anual",
        unidad="MJ/año",
        extractor=lambda res: _attr(res, "E_auxiliar_anual_MJ"),
        modos_validos=frozenset({_ANUAL}),
        formato=".0f",
    ),
)

# Índice por id sobre todos los KPIs (fijos + avanzados).
TODOS_LOS_KPIS: tuple[KpiBarrido, ...] = KPIS_FIJOS + KPIS_AVANZADOS
KPIS_POR_ID: dict[str, KpiBarrido] = {k.id: k for k in TODOS_LOS_KPIS}


def obtener_kpi(kpi_id: str) -> KpiBarrido:
    """Devuelve el KPI de id ``kpi_id`` (fijo o avanzado).

    Raises:
        KeyError: Si el id no existe en el catálogo.
    """
    try:
        return KPIS_POR_ID[kpi_id]
    except KeyError as exc:
        raise KeyError(f"BARRIDO_KPI_DESCONOCIDO: '{kpi_id}' no está en el catálogo.") from exc


def kpis_fijos_para_modo(modo: str) -> list[KpiBarrido]:
    """KPIs fijos aplicables a un modo de cálculo."""
    return [k for k in KPIS_FIJOS if modo in k.modos_validos]


def kpis_avanzados_para_modo(modo: str) -> list[KpiBarrido]:
    """KPIs avanzados aplicables a un modo de cálculo."""
    return [k for k in KPIS_AVANZADOS if modo in k.modos_validos]
