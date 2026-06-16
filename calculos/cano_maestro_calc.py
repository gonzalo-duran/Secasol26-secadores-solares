"""Física del caño maestro (manifold) del banco de colectores — gran escala (S40).

Tres modelos de prediseño para el caño maestro que colecta el aire de las ramas
del banco y lo conduce al ventilador (estilo túnel ADITAL):

1. **Pérdida de carga** (``estimar_delta_P_cano_maestro``): fricción del tramo
   troncal sobre ``largo_m`` a la velocidad del caudal total, más las pérdidas
   singulares de la campana de reducción y la llave mariposa de un camino
   representativo (las ramas están en paralelo → el ventilador ve un camino).

2. **Balance térmico** (``delta_T_cano_maestro``): el caño no aislado pierde
   calor al ambiente por convección externa pero colecta radiación en su cara
   superior; la pérdida neta del aire suele ser pequeña (≈ 3 °C en ADITAL).

3. **Uniformidad de distribución** (``uniformidad_distribucion``): criterio
   simple de reparto de caudal entre ramas — uniforme si la ΔP del troncal es
   pequeña frente a la ΔP de una rama (colector + accesorios).

Reusa los helpers hidráulicos de ``motor_calc`` (Haaland, densidad, viscosidad).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from calculos.motor_calc import (
    _factor_friccion_haaland,
    densidad_aire,
    viscosidad_aire,
)

if TYPE_CHECKING:
    from core.colector import CanoMaestro

# Calor específico del aire [J/(kg·K)] — constante de prediseño (~50 °C).
_CP_AIRE_J_KGK: float = 1006.0
# Conductividad y Prandtl del aire (~50 °C) para el film interno.
_K_AIRE_W_MK: float = 0.028
_PR_AIRE: float = 0.71
# Umbral de uniformidad: ΔP_manifold / ΔP_rama por debajo del cual el reparto
# de caudal entre ramas se considera uniforme.
_UMBRAL_UNIFORMIDAD: float = 0.15
# Coeficiente combinado (convección natural + radiación) de la cavidad de aire
# bajo la cubierta translúcida del caño [W/m²K] — prediseño (~2–5 cm de cámara
# de aire quieta; cf. _U_cubierta_efectiva del colector para el modelo fino).
_H_CAVIDAD_CUBIERTA_W_M2K: float = 6.0
# Segmentos de integración de la fricción cuando la sección es variable (S41).
_N_SEGMENTOS_FRICCION: int = 20


def estimar_delta_P_cano_maestro(
    cano: "CanoMaestro",
    Q_vol_total_m3_s: float,
    *,
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> dict[str, float]:
    """Estima la pérdida de carga del caño maestro [Pa].

    Modelo de prediseño con **flujo acumulado** (manifold colector): el caudal
    crece linealmente a lo largo del caño a medida que cada boca suma su aporte,
    ``Q(f) = Q_total · f`` (f = 0 en el extremo lejano, f = 1 en el ventilador).
    La fricción se integra por tramos con el caudal y la sección locales
    (Darcy-Weisbach + Haaland) — mismo criterio que ``_dP_troncal_tramos_Pa`` de
    ``campo_colectores_calc``. Los accesorios (campana de reducción + llave
    mariposa de un camino representativo) se aplican sobre la presión dinámica
    del extremo del ventilador (caudal total).

    Esta es la clave de la **compensación de sección**: un caño de sección
    creciente mantiene la velocidad acotada a medida que acumula caudal, mientras
    que un caño chico constante dispararía la velocidad (y la fricción) cerca del
    ventilador. Las ramas están en paralelo, por lo que el ventilador ve la ΔP de
    un solo camino (no la suma de las ramas).

    Args:
        cano: Configuración del caño maestro.
        Q_vol_total_m3_s: Caudal volumétrico total del banco [m³/s].
        T_K, P_Pa: Condiciones del aire para ρ y μ.

    Returns:
        Dict con 'friccion', 'accesorios', 'total' [Pa], 'v_troncal_ms' y
        'v_fin_ms' (velocidad en el extremo del ventilador, caudal total) y
        'v_max_ms' (velocidad máxima a lo largo del caño — acotada si la sección
        compensa el caudal acumulado).
    """
    rho = densidad_aire(T_K, P_Pa)
    mu = viscosidad_aire(T_K)
    if Q_vol_total_m3_s <= 0:
        return {
            "friccion": 0.0,
            "accesorios": 0.0,
            "total": 0.0,
            "v_troncal_ms": 0.0,
            "v_fin_ms": 0.0,
            "v_max_ms": 0.0,
        }

    # Velocidad en el extremo del ventilador (caudal total, sección de salida).
    v_fin = Q_vol_total_m3_s / cano.area_seccion_m2
    q_dinamica_fin = rho * v_fin**2 / 2.0

    # Fricción con flujo acumulado: Q(f) = Q_total·f por tramo, sección local.
    dP_friccion = 0.0
    v_max = 0.0
    dx = cano.largo_m / _N_SEGMENTOS_FRICCION
    for j in range(_N_SEGMENTOS_FRICCION):
        f = (j + 0.5) / _N_SEGMENTOS_FRICCION
        ancho_j, alto_j = cano.seccion_en_fraccion(f)
        A_j = ancho_j * alto_j
        Dh_j = 2.0 * ancho_j * alto_j / (ancho_j + alto_j)
        Q_j = Q_vol_total_m3_s * f
        v_j = Q_j / A_j if A_j > 0 else 0.0
        v_max = max(v_max, v_j)
        Re_j = rho * v_j * Dh_j / mu
        eps_rel_j = cano.rugosidad_m / Dh_j if Dh_j > 0 else 0.0
        f_j = _factor_friccion_haaland(Re_j, eps_rel_j)
        dP_friccion += f_j * (dx / Dh_j) * (rho * v_j**2 / 2.0)

    K_accesorios = cano.K_campana_reduccion + cano.K_llave_mariposa
    dP_accesorios = K_accesorios * q_dinamica_fin

    return {
        "friccion": dP_friccion,
        "accesorios": dP_accesorios,
        "total": dP_friccion + dP_accesorios,
        "v_troncal_ms": v_fin,
        "v_fin_ms": v_fin,
        "v_max_ms": v_max,
    }


def delta_T_cano_maestro(
    cano: "CanoMaestro",
    *,
    T_aire_K: float,
    T_amb_K: float,
    I_g_W_m2: float,
    m_dot_as_kg_s: float,
    v_viento_ms: float,
    P_Pa: float = 101325.0,
) -> float:
    """Cambio de temperatura del aire al atravesar el caño maestro [K].

    Balance: el aire pierde calor al ambiente y gana radiación solar en su cara
    superior si ``aporte_solar``. Devuelve ΔT = (Q_solar − Q_perdida)/(ṁ·cp);
    negativo = enfriamiento neto.

    El coeficiente global U combina el film interno (convección forzada del aire
    en el ducto, Dittus-Boelter), la conducción del aislante (si está aislado;
    la chapa metálica tiene R ≈ 0) y el film externo (h_w McAdams por viento):
    ``U = 1/(1/h_int + R_aisl + 1/h_w)``.

    Args:
        cano: Configuración del caño maestro.
        T_aire_K: Temperatura del aire que entra al caño (salida del banco) [K].
        T_amb_K: Temperatura ambiente [K].
        I_g_W_m2: Irradiancia global sobre la cara superior del caño [W/m²].
        m_dot_as_kg_s: Caudal másico de aire seco total [kg/s].
        v_viento_ms: Velocidad del viento [m/s] (para h_w McAdams).
        P_Pa: Presión total [Pa] (para ρ del film interno).

    Returns:
        ΔT del aire [K] (T_salida_cano = T_aire_K + ΔT).
    """
    if m_dot_as_kg_s <= 0:
        return 0.0

    h_w = 5.7 + 3.8 * max(0.0, v_viento_ms)  # McAdams (film externo)

    # Film interno: convección forzada del aire en el ducto (Dittus-Boelter,
    # enfriamiento n=0.3). v_int desde el caudal másico y la sección.
    rho_int = densidad_aire(T_aire_K, P_Pa)
    mu_int = viscosidad_aire(T_aire_K)
    Dh = cano.diametro_hidraulico_m
    v_int = m_dot_as_kg_s / (rho_int * cano.area_seccion_m2)
    Re_int = rho_int * v_int * Dh / mu_int if Dh > 0 else 0.0
    if Re_int > 4000.0:
        Nu_int = 0.023 * Re_int**0.8 * _PR_AIRE**0.3
    else:
        Nu_int = 3.66  # laminar desarrollado, T pared ~ constante
    h_int = Nu_int * _K_AIRE_W_MK / Dh if Dh > 0 else h_w

    R_aisl = (
        cano.espesor_aislante_m / cano.k_aislante_W_mK
        if (cano.aislado and cano.espesor_aislante_m > 0 and cano.k_aislante_W_mK > 0)
        else 0.0
    )
    U_lados = 1.0 / (1.0 / h_int + R_aisl + 1.0 / h_w)

    # Cara superior: si hay cubierta translúcida (S41), la cavidad de aire
    # entre la chapa y la cubierta agrega resistencia (efecto invernadero del
    # mini-colector): U_sup < U_lados y la ganancia solar se afecta por τ.
    A_sup = cano.area_superior_m2
    A_resto = max(0.0, cano.area_externa_m2 - A_sup)
    if cano.cubierta is not None:
        U_sup = 1.0 / (1.0 / h_int + R_aisl + 1.0 / _H_CAVIDAD_CUBIERTA_W_M2K + 1.0 / h_w)
    else:
        U_sup = U_lados

    Q_perdida = (U_lados * A_resto + U_sup * A_sup) * (T_aire_K - T_amb_K)
    Q_solar = (
        cano.transmitancia_cubierta * cano.absortancia_solar * A_sup * max(0.0, I_g_W_m2)
        if cano.aporte_solar
        else 0.0
    )
    return (Q_solar - Q_perdida) / (m_dot_as_kg_s * _CP_AIRE_J_KGK)


def uniformidad_distribucion(
    dP_cano_maestro_Pa: float,
    dP_rama_Pa: float,
) -> dict[str, float | bool]:
    """Criterio simple de uniformidad de reparto de caudal entre ramas.

    El reparto es tanto más uniforme cuanto menor sea la ΔP del troncal del
    caño maestro frente a la ΔP de una rama (colector + accesorios): si el
    troncal "cuesta" poco comparado con la rama, todas las ramas ven
    aproximadamente la misma presión motriz.

    Args:
        dP_cano_maestro_Pa: ΔP del troncal del caño maestro [Pa].
        dP_rama_Pa: ΔP de una rama (colector + campana + llave) [Pa].

    Returns:
        Dict con 'ratio' (dP_cano/dP_rama) y 'es_uniforme' (ratio < umbral).
    """
    if dP_rama_Pa <= 0:
        return {"ratio": float("inf"), "es_uniforme": False}
    ratio = dP_cano_maestro_Pa / dP_rama_Pa
    return {"ratio": ratio, "es_uniforme": ratio < _UMBRAL_UNIFORMIDAD}
