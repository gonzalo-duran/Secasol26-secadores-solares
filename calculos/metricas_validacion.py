"""Métricas de bondad de ajuste — validación medido vs simulado (mejora 38, fase 2).

Funciones puras (numpy, sin pandas ni streamlit) que cuantifican el ajuste entre
una serie **medida** de referencia y una serie **simulada** ya alineadas (mismos
instantes, misma longitud). Diseñadas para ser reusadas como **función objetivo**
por la calibración (fase 3), por eso no dependen de la UI ni del pipeline.

Convención: ``medido`` es la referencia (verdad de campo), ``simulado`` la salida
del modelo. El signo del sesgo (MBE) es ``simulado − medido`` (positivo = el modelo
sobreestima). Las métricas se calculan sobre los pares **sin NaN** en ninguna de
las dos series; ``n_pares`` reporta cuántos quedaron.

Definiciones (sobre los ``n`` pares válidos):
    RMSE = √⟨(s − m)²⟩                        [unidades de la señal]
    MBE  = ⟨s − m⟩                            [unidades de la señal, con signo]
    MAE  = ⟨|s − m|⟩                          [unidades de la señal]
    R²   = corr(m, s)²                        [adimensional, ciego al sesgo]
    NSE  = 1 − Σ(s − m)² / Σ(m − ⟨m⟩)²        [adimensional, skill vs la media]
    d    = 1 − Σ(s − m)² / Σ(|s − ⟨m⟩| + |m − ⟨m⟩|)²   [índice de Willmott, [0, 1]]
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetricasAjuste:
    """Resultado de la comparación medido vs simulado.

    Attributes:
        n_pares: Número de pares (m, s) válidos (sin NaN) usados en el cálculo.
        rmse: Raíz del error cuadrático medio [unidades de la señal].
        mbe: Error medio con signo (simulado − medido) [unidades de la señal].
        mae: Error absoluto medio [unidades de la señal].
        r2: Coeficiente de determinación (correlación²) [adimensional].
        nse: Eficiencia de Nash–Sutcliffe [adimensional, puede ser < 0].
        d_willmott: Índice de acuerdo de Willmott [adimensional, [0, 1]].
    """

    n_pares: int
    rmse: float
    mbe: float
    mae: float
    r2: float
    nse: float
    d_willmott: float


def _pares_validos(medido: np.ndarray, simulado: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Filtra a los pares finitos en ambas series.

    Args:
        medido: Serie de referencia.
        simulado: Serie del modelo (misma longitud que ``medido``).

    Returns:
        ``(m, s)`` con solo los índices finitos en ambas.

    Raises:
        ValueError: ``MVAL_LONGITUD_DISTINTA`` si las longitudes difieren;
            ``MVAL_SERIES_VACIAS`` si no queda ningún par válido.
    """
    m = np.asarray(medido, dtype=float)
    s = np.asarray(simulado, dtype=float)
    if m.shape != s.shape:
        raise ValueError(
            f"MVAL_LONGITUD_DISTINTA: medido ({m.shape}) y simulado ({s.shape}) "
            "deben tener la misma forma."
        )
    mask = np.isfinite(m) & np.isfinite(s)
    if not mask.any():
        raise ValueError("MVAL_SERIES_VACIAS: no hay pares válidos (sin NaN) para comparar.")
    return m[mask], s[mask]


def rmse(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Raíz del error cuadrático medio [unidades de la señal]."""
    m, s = _pares_validos(medido, simulado)
    return float(np.sqrt(np.mean((s - m) ** 2)))


def mbe(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Error medio con signo (simulado − medido) [unidades de la señal]."""
    m, s = _pares_validos(medido, simulado)
    return float(np.mean(s - m))


def mae(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Error absoluto medio [unidades de la señal]."""
    m, s = _pares_validos(medido, simulado)
    return float(np.mean(np.abs(s - m)))


def r2(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Coeficiente de determinación (correlación² de Pearson) [adimensional].

    Devuelve 0.0 si alguna serie es constante (correlación indefinida).
    """
    m, s = _pares_validos(medido, simulado)
    if m.size < 2 or np.std(m) == 0.0 or np.std(s) == 0.0:
        return 0.0
    r = np.corrcoef(m, s)[0, 1]
    return float(r * r)


def nse(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Eficiencia de Nash–Sutcliffe [adimensional, ≤ 1; puede ser < 0].

    NSE = 1 significa ajuste perfecto; NSE = 0, tan bueno como usar la media del
    medido; NSE < 0, peor que la media. Devuelve 0.0 si el medido es constante.
    """
    m, s = _pares_validos(medido, simulado)
    denom = float(np.sum((m - np.mean(m)) ** 2))
    if denom == 0.0:
        return 0.0
    return float(1.0 - np.sum((s - m) ** 2) / denom)


def indice_willmott(medido: np.ndarray, simulado: np.ndarray) -> float:
    """Índice de acuerdo de Willmott (d) [adimensional, [0, 1]].

    d = 1 es acuerdo perfecto; d = 0, desacuerdo total. Acotado y menos sensible
    que R² a valores extremos. Devuelve 0.0 si el denominador se anula.
    """
    m, s = _pares_validos(medido, simulado)
    m_media = float(np.mean(m))
    denom = float(np.sum((np.abs(s - m_media) + np.abs(m - m_media)) ** 2))
    if denom == 0.0:
        return 0.0
    return float(1.0 - np.sum((s - m) ** 2) / denom)


def calcular_metricas(medido: np.ndarray, simulado: np.ndarray) -> MetricasAjuste:
    """Calcula todas las métricas de ajuste de una vez.

    Args:
        medido: Serie de referencia (verdad de campo).
        simulado: Serie del modelo, alineada con ``medido`` (misma longitud).

    Returns:
        ``MetricasAjuste`` con las métricas y el número de pares válidos.

    Raises:
        ValueError: ``MVAL_LONGITUD_DISTINTA`` o ``MVAL_SERIES_VACIAS``.
    """
    m, s = _pares_validos(medido, simulado)
    return MetricasAjuste(
        n_pares=int(m.size),
        rmse=rmse(m, s),
        mbe=mbe(m, s),
        mae=mae(m, s),
        r2=r2(m, s),
        nse=nse(m, s),
        d_willmott=indice_willmott(m, s),
    )
