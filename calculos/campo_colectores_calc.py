"""Red hidráulica y térmica del campo de colectores — gran escala (S41).

Modelo de prediseño del **campo completo** (banco + caño maestro): resuelve el
reparto real de caudal entre las ramas del banco considerando la pérdida de
carga acumulada del troncal del caño maestro, y evalúa la temperatura de salida
de cada rama a su caudal propio.

Física / metodología (ASHRAE Handbook 2017, cap. 21 "Duct Design"):
    - Fricción por tramo: Darcy-Weisbach con factor de Haaland (Ec. 34),
      sección local del troncal interpolada (constante o creciente, S41).
    - Pérdidas singulares de boca: ΔP = C·(ρv²/2) con C referido a la sección
      de la rama (Ec. 33) — campana de reducción + llave mariposa del
      ``CanoMaestro``. La pérdida de mezcla de la unión convergente (Ec. 32/33
      con C de la Duct Fitting Database) se desprecia en v1: es de segundo
      orden frente a fricción de troncal + resistencia de rama.
    - Igualdad de presión total: todas las trayectorias (rama i + troncal desde
      su boca hasta el ventilador) ven la misma ΔP total. El reparto {q_i} se
      resuelve por punto fijo amortiguado sobre esa igualdad.

Convención de numeración: la **boca 1 es el extremo lejano** al ventilador
(inicio del caño, sección mínima si es variable); la boca N descarga junto al
ventilador. El troncal se discretiza en N tramos de largo L/N; el tramo i
transporta el caudal acumulado de las bocas 1..i.

Capa calculos/: sin Streamlit. Consumido por la UI de P3 (sección "Evaluación
del campo de colectores").
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional

import numpy as np

from calculos.cano_maestro_calc import delta_T_cano_maestro
from calculos.motor_calc import (
    _factor_friccion_haaland,
    densidad_aire,
    estimar_delta_P_colector,
    viscosidad_aire,
)

if TYPE_CHECKING:
    from core.colector import CanoMaestro, Colector

# Iteraciones máximas y tolerancia del punto fijo (spread relativo de ΔP).
_MAX_ITER: int = 200
_TOL_SPREAD: float = 1e-3
# Amortiguación del punto fijo (0 = sin actualizar, 1 = sin amortiguar).
_DAMPING: float = 0.5
# Clip de velocidad del módulo para el solver térmico (igual que el lazo
# natural y el pipeline de ventana).
_V_MODULO_MIN_MS: float = 0.05
_V_MODULO_MAX_MS: float = 15.0


@dataclass
class ResultadoCampoColectores:
    """Reparto hidráulico y temperaturas del campo de colectores.

    Attributes:
        q_ramas_m3_s: Caudal volumétrico por rama [m³/s], boca 1 = extremo
            lejano al ventilador.
        v_modulo_ms: Velocidad de aire en el canal del módulo de cada rama [m/s].
        dP_ramas_Pa: ΔP propia de cada rama (colector + accesorios de boca) a
            su caudal [Pa].
        dP_sistema_Pa: ΔP total de trayectoria igualada (rama + troncal) [Pa].
        dP_troncal_Pa: ΔP del troncal del caño maestro recorrido completo
            (desde la boca 1, extremo lejano, hasta el ventilador) [Pa]. Aísla
            el costo del manifold del de la rama: es lo que responde a la
            compensación de sección. 0.0 sin caño maestro.
        v_troncal_perfil_ms: Velocidad del aire en el troncal por tramo
            (extremo lejano → ventilador) [m/s]. Con sección creciente se
            mantiene acotada; con sección chica constante se dispara cerca del
            ventilador. Array vacío sin caño maestro.
        T_salida_ramas_K: T de salida del colector de cada rama [K] (None si
            no se pidió térmica).
        T_mezcla_K: T de mezcla ponderada por caudal en el manifold [K].
        dT_cano_K: ΔT térmica del caño maestro [K] (None sin caño).
        T_salida_cano_K: T del flujo a la salida del caño maestro [K].
        Q_total_m3_s: Caudal total del campo [m³/s].
        uniformidad: Métricas de reparto: ``q_min_m3_s``, ``q_max_m3_s``,
            ``desviacion_max_pct`` ((q_max−q_min)/q_medio×100).
        convergio: True si el punto fijo cerró bajo tolerancia.
        n_iter: Iteraciones usadas.
        advertencias: Mensajes de diagnóstico.
    """

    q_ramas_m3_s: np.ndarray
    v_modulo_ms: np.ndarray
    dP_ramas_Pa: np.ndarray
    dP_sistema_Pa: float
    Q_total_m3_s: float
    dP_troncal_Pa: float = 0.0
    v_troncal_perfil_ms: np.ndarray = field(default_factory=lambda: np.array([]))
    T_salida_ramas_K: Optional[np.ndarray] = None
    T_mezcla_K: Optional[float] = None
    dT_cano_K: Optional[float] = None
    T_salida_cano_K: Optional[float] = None
    uniformidad: dict = field(default_factory=dict)
    convergio: bool = True
    n_iter: int = 0
    advertencias: list[str] = field(default_factory=list)


def _dP_rama_Pa(
    colector: "Colector",
    q_m3_s: float,
    rho: float,
    A_canal_m2: float,
    T_K: float,
    P_Pa: float,
) -> float:
    """ΔP de una rama a su caudal: colector (clonado a v propia) + boca.

    La boca (campana de reducción + llave mariposa) se referencia a la
    velocidad del canal de la rama (ASHRAE Ec. 33, C referido a la sección b).
    """
    v = q_m3_s / A_canal_m2 if A_canal_m2 > 0 else 0.0
    u_clone = dataclasses.replace(colector.unidad, velocidad_diseno_ms=max(v, 1e-6))
    col_clone = dataclasses.replace(colector, unidad=u_clone)
    dP_col = estimar_delta_P_colector(col_clone, T_K=T_K, P_Pa=P_Pa)

    cano = colector.banco.cano_maestro
    K_boca = (cano.K_campana_reduccion + cano.K_llave_mariposa) if cano is not None else 0.0
    dP_boca = K_boca * rho * v**2 / 2.0
    return dP_col + dP_boca


def _dP_troncal_tramos_Pa(
    cano: "CanoMaestro",
    Q_acum_m3_s: np.ndarray,
    rho: float,
    mu: float,
) -> np.ndarray:
    """ΔP de fricción de cada tramo del troncal [Pa], tramo i con Q_acum[i].

    Sección local interpolada en el punto medio del tramo (lineal entre la
    sección de inicio y la del extremo del ventilador si es variable).
    """
    n = len(Q_acum_m3_s)
    dx = cano.largo_m / n
    dP = np.zeros(n)
    for i in range(n):
        ancho_i, alto_i = cano.seccion_en_fraccion((i + 0.5) / n)
        A_i = ancho_i * alto_i
        Dh_i = 2.0 * ancho_i * alto_i / (ancho_i + alto_i)
        Q_i = float(Q_acum_m3_s[i])
        if Q_i <= 0 or A_i <= 0:
            continue
        v_i = Q_i / A_i
        Re_i = rho * v_i * Dh_i / mu
        eps_rel = cano.rugosidad_m / Dh_i if Dh_i > 0 else 0.0
        f_i = _factor_friccion_haaland(Re_i, eps_rel)
        dP[i] = f_i * (dx / Dh_i) * (rho * v_i**2 / 2.0)
    return dP


def evaluar_campo_colectores(
    colector: "Colector",
    *,
    Q_total_m3_s: float,
    T_amb_K: float,
    I_g_POA_W_m2: float,
    v_viento_ms: float = 2.0,
    P_Pa: float = 101325.0,
    pendiente_deg: float = 25.0,
    T_hidraulica_K: float = 323.15,
    I_g_horizontal_W_m2: Optional[float] = None,
    calcular_termica: bool = True,
) -> ResultadoCampoColectores:
    """Evalúa el campo de colectores completo: reparto {q_i} + térmica por rama.

    Args:
        colector: Colector con banco configurado (con o sin caño maestro; sin
            caño el reparto es uniforme por definición del modelo).
        Q_total_m3_s: Caudal volumétrico total del sistema [m³/s] (lo fija el
            ventilador — caudal único S41).
        T_amb_K: Temperatura ambiente [K].
        I_g_POA_W_m2: Irradiancia POA sobre el plano del colector [W/m²].
        v_viento_ms: Viento [m/s].
        P_Pa: Presión [Pa].
        pendiente_deg: Pendiente del colector [°] para el solver térmico.
        T_hidraulica_K: T del aire para ρ/μ del cálculo hidráulico [K].
        I_g_horizontal_W_m2: Irradiancia sobre la cara superior del caño
            (global horizontal). None → usa ``I_g_POA_W_m2`` (prediseño).
        calcular_termica: Si False, solo resuelve la hidráulica (más rápido).

    Returns:
        ResultadoCampoColectores.

    Raises:
        ValueError: Si el caudal total no es positivo.
    """
    if Q_total_m3_s <= 0:
        raise ValueError(f"CAMPO_CAUDAL_NO_POSITIVO: Q_total_m3_s={Q_total_m3_s:.4f} ≤ 0.")

    banco = colector.banco
    cano = banco.cano_maestro
    N = max(1, int(banco.n_paralelo))
    u = colector.unidad
    A_canal = float(u.ancho_m) * float(u.espaciado_m)

    rho = densidad_aire(T_hidraulica_K, P_Pa)
    mu = viscosidad_aire(T_hidraulica_K)

    advertencias: list[str] = []
    q = np.full(N, Q_total_m3_s / N)
    convergio = True
    n_iter = 0

    if cano is None or N == 1:
        # Sin troncal (o una sola rama): reparto uniforme por definición.
        dP_ramas = np.array(
            [_dP_rama_Pa(colector, float(qi), rho, A_canal, T_hidraulica_K, P_Pa) for qi in q]
        )
        dP_sistema = float(np.max(dP_ramas)) if len(dP_ramas) else 0.0
    else:
        # Punto fijo amortiguado sobre la igualdad de ΔP de trayectorias.
        for n_iter in range(1, _MAX_ITER + 1):
            dP_ramas = np.array(
                [_dP_rama_Pa(colector, float(qi), rho, A_canal, T_hidraulica_K, P_Pa) for qi in q]
            )
            Q_acum = np.cumsum(q)
            dP_tramos = _dP_troncal_tramos_Pa(cano, Q_acum, rho, mu)
            # Troncal acumulado desde la boca i hasta el ventilador.
            dP_tronc_desde = np.cumsum(dP_tramos[::-1])[::-1]
            dP_path = dP_ramas + dP_tronc_desde

            dP_obj = float(np.mean(dP_path))
            spread = (np.max(dP_path) - np.min(dP_path)) / max(dP_obj, 1e-9)
            if spread < _TOL_SPREAD:
                break
            # Resistencia cuadrática: q ∝ √(ΔP) → corrección con amortiguación.
            factor = np.sqrt(dP_obj / np.maximum(dP_path, 1e-9))
            q_nuevo = q * (1.0 + _DAMPING * (factor - 1.0))
            q = q_nuevo * (Q_total_m3_s / float(np.sum(q_nuevo)))
        else:
            convergio = False
            advertencias.append(
                f"CAMPO_NO_CONVERGIO: el reparto de caudal no cerró en "
                f"{_MAX_ITER} iteraciones (spread {spread:.2e})."
            )
        dP_sistema = float(np.mean(dP_path))

    v_modulo = q / A_canal if A_canal > 0 else np.zeros(N)

    # Troncal del caño maestro: ΔP del recorrido completo (boca 1 → ventilador)
    # y perfil de velocidad por tramo. Aísla el costo del manifold del de la
    # rama y hace visible la compensación de sección (velocidad acotada).
    dP_troncal = 0.0
    v_troncal_perfil = np.array([])
    if cano is not None and N > 1:
        Q_acum = np.cumsum(q)
        dP_tramos = _dP_troncal_tramos_Pa(cano, Q_acum, rho, mu)
        dP_troncal = float(np.sum(dP_tramos))
        v_perfil = np.empty(N)
        for i in range(N):
            ancho_i, alto_i = cano.seccion_en_fraccion((i + 0.5) / N)
            A_i = ancho_i * alto_i
            v_perfil[i] = float(Q_acum[i]) / A_i if A_i > 0 else 0.0
        v_troncal_perfil = v_perfil

    resultado = ResultadoCampoColectores(
        q_ramas_m3_s=q,
        v_modulo_ms=v_modulo,
        dP_ramas_Pa=dP_ramas,
        dP_sistema_Pa=dP_sistema,
        Q_total_m3_s=Q_total_m3_s,
        dP_troncal_Pa=dP_troncal,
        v_troncal_perfil_ms=v_troncal_perfil,
        uniformidad={
            "q_min_m3_s": float(np.min(q)),
            "q_max_m3_s": float(np.max(q)),
            "desviacion_max_pct": float((np.max(q) - np.min(q)) / np.mean(q) * 100.0),
        },
        convergio=convergio,
        n_iter=n_iter,
        advertencias=advertencias,
    )

    if not calcular_termica:
        return resultado

    # ------------------------------------------------------------------
    # Térmica por rama: solver del colector a la velocidad propia de cada
    # rama (mismo dispatch de tipos 1-4 que el balance global).
    # ------------------------------------------------------------------
    from calculos.balance_global import _correr_colector

    T_sal = np.empty(N)
    n_fallas = 0
    for i in range(N):
        v_i = float(np.clip(v_modulo[i], _V_MODULO_MIN_MS, _V_MODULO_MAX_MS))
        u_i = dataclasses.replace(u, velocidad_diseno_ms=v_i)
        col_i = dataclasses.replace(colector, unidad=u_i)
        shim = SimpleNamespace(
            colector=col_i,
            emplazamiento=SimpleNamespace(pendiente_colector_deg=pendiente_deg),
        )
        try:
            _solver, T_sal_K = _correr_colector(
                shim,
                T_amb_K=T_amb_K,
                I_g_W_m2=I_g_POA_W_m2,
                v_viento_ms=v_viento_ms,
                T_entrada_K=T_amb_K,
                P_amb_Pa=P_Pa,
            )
            T_sal[i] = max(T_sal_K, T_amb_K)
        except Exception:
            T_sal[i] = T_amb_K
            n_fallas += 1
    if n_fallas:
        resultado.advertencias.append(
            f"CAMPO_COLECTOR_FALLO_RAMAS: el solver del colector falló en "
            f"{n_fallas} de {N} ramas (se asumió T_salida = T_amb)."
        )

    resultado.T_salida_ramas_K = T_sal
    T_mezcla = float(np.sum(q * T_sal) / np.sum(q))
    resultado.T_mezcla_K = T_mezcla

    if cano is not None:
        I_h = I_g_POA_W_m2 if I_g_horizontal_W_m2 is None else I_g_horizontal_W_m2
        m_dot = Q_total_m3_s * rho
        dT = delta_T_cano_maestro(
            cano,
            T_aire_K=T_mezcla,
            T_amb_K=T_amb_K,
            I_g_W_m2=I_h,
            m_dot_as_kg_s=m_dot,
            v_viento_ms=v_viento_ms,
            P_Pa=P_Pa,
        )
        resultado.dT_cano_K = float(dT)
        resultado.T_salida_cano_K = T_mezcla + float(dT)
    else:
        resultado.T_salida_cano_K = T_mezcla

    return resultado
