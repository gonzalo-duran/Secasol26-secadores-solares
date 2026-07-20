"""Calibración 1-D contra datos medidos (mejora 38, fase 3).

Motor **puro** (sin streamlit ni el colector) que barre los valores candidatos de
un parámetro y se queda con el que **minimiza una función objetivo** de ajuste
(RMSE, |MBE| o MAE) contra una señal medida. Es la automatización del barrido
manual de la fase 2: para cada valor del parámetro se evalúa el modelo, se
comparan simulado vs medido (``metricas_validacion``) y se elige el óptimo.

El motor recibe un ``evaluar_fn(valor) -> MetricasAjuste | None`` (closure que el
llamador arma: setea el parámetro, corre el modelo y alinea contra el medido),
por lo que no depende de la capa de simulación ni de la UI y es reusable/testeable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from calculos.metricas_validacion import MetricasAjuste

# Funciones objetivo disponibles: MetricasAjuste → escalar a minimizar.
OBJETIVOS: dict[str, Callable[[MetricasAjuste], float]] = {
    "rmse": lambda m: m.rmse,
    "mbe_abs": lambda m: abs(m.mbe),
    "mae": lambda m: m.mae,
}


@dataclass(frozen=True)
class PuntoCalibracion:
    """Un punto del barrido de calibración.

    Attributes:
        valor: Valor del parámetro calibrado (SI).
        objetivo: Valor de la función objetivo en ese punto (None si el modelo no
            convergió o no hubo solape temporal con el medido).
        metricas: ``MetricasAjuste`` completas en ese punto (None si no aplica).
    """

    valor: float
    objetivo: Optional[float]
    metricas: Optional[MetricasAjuste]


@dataclass
class ResultadoCalibracion:
    """Resultado de una calibración 1-D.

    Attributes:
        parametro: Id/nombre del parámetro calibrado (informativo).
        objetivo_nombre: Función objetivo usada ("rmse" | "mbe_abs" | "mae").
        puntos: Todos los puntos evaluados (para graficar la curva objetivo).
        valor_optimo: Valor del parámetro que minimiza el objetivo (None si ningún
            punto fue evaluable).
        metricas_optimo: ``MetricasAjuste`` en el óptimo (None si no hay óptimo).
    """

    parametro: str
    objetivo_nombre: str
    puntos: list[PuntoCalibracion]
    valor_optimo: Optional[float]
    metricas_optimo: Optional[MetricasAjuste]


def calibrar_1d(
    valores,
    evaluar_fn: Callable[[float], Optional[MetricasAjuste]],
    *,
    parametro: str = "",
    objetivo: str = "rmse",
) -> ResultadoCalibracion:
    """Barre ``valores`` y devuelve el que minimiza la función objetivo.

    Args:
        valores: Iterable de valores candidatos del parámetro (SI).
        evaluar_fn: Callable ``valor -> MetricasAjuste | None`` que corre el modelo
            con ese valor y lo compara contra el medido (None si no evaluable).
        parametro: Nombre del parámetro (informativo, va al resultado).
        objetivo: Clave de :data:`OBJETIVOS` a minimizar.

    Returns:
        ``ResultadoCalibracion`` con todos los puntos y el óptimo.

    Raises:
        ValueError: ``CAL_OBJETIVO_INVALIDO`` si ``objetivo`` no está en OBJETIVOS.
    """
    if objetivo not in OBJETIVOS:
        raise ValueError(f"CAL_OBJETIVO_INVALIDO: '{objetivo}' (válidos: {', '.join(OBJETIVOS)}).")
    f_obj = OBJETIVOS[objetivo]

    puntos: list[PuntoCalibracion] = []
    for v in valores:
        met = evaluar_fn(float(v))
        obj = float(f_obj(met)) if met is not None else None
        puntos.append(PuntoCalibracion(valor=float(v), objetivo=obj, metricas=met))

    evaluables = [p for p in puntos if p.objetivo is not None]
    if not evaluables:
        return ResultadoCalibracion(parametro, objetivo, puntos, None, None)

    mejor = min(evaluables, key=lambda p: p.objetivo)
    return ResultadoCalibracion(parametro, objetivo, puntos, mejor.valor, mejor.metricas)
