"""Motor numérico del colector solar de aire — Tipo 1.

Modela un colector solar de placa plana con absorbedor en el fondo del cuerpo
del colector y circulación de aire por encima del absorbedor (canal único).

Modelo cuasi-estacionario con discretización espacial a lo largo del eje x
(dirección del flujo). En cada posición x se resuelve un sistema no lineal
algebraico de 3 ecuaciones (cubierta cara externa, cubierta cara interna,
absorbedor) para obtener T_cub_e, T_cub_i y T_abs. La temperatura del fluido
T_f(x) se integra con scipy.integrate.solve_ivp.

Hipótesis principales
---------------------
- Modelo cuasi-estacionario: sin acumulación de calor en superficies sólidas.
- Flujo unidireccional en x, desarrollado hidráulica y térmicamente.
- Transferencia de calor despreciable en dirección z (ancho).
- Factor de forma radiativo cubierta–absorbedor = 1 (superficies paralelas
  infinitas).
- Absortividad de la cubierta despreciable.
- Pérdidas laterales contabilizadas en U_bottom (despreciadas explícitamente).
- Propiedades del aire (cp, k, mu, Pr) constantes evaluadas a 323 K (50 °C).
- En convección natural: densidad calculada como gas ideal rho(T, P).

Correlaciones
-------------
- T_cielo:  Swinbank (1963).
- h_viento: McAdams (1954), válida estrictamente para v < 5 m/s;
            se emite advertencia para v ≥ 5 m/s.
- h_int: delegado a ``calculos.correlaciones_nusselt.calcular_h_int()``.
         Selección automática según Re y L/Dh, o correlación elegida por
         el usuario. Ver ese módulo para detalle de cada correlación.

Referencias
-----------
- Duffie & Beckman, "Solar Engineering of Thermal Processes", 4ª ed.
- Swinbank, Q. J. R. Meteorol. Soc. 89, 339-348, 1963.
- McAdams, "Heat Transmission", 3ª ed., 1954.
- Ver calculos/correlaciones_nusselt.py para referencias de Nusselt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import fsolve

from calculos.correlaciones_nusselt import calcular_h_int, nusselt_hollands_inclinada

if TYPE_CHECKING:
    from core.colector import Colector

# =============================================================================
# Constantes físicas
# =============================================================================

SIGMA_SB: float = 5.670374419e-8  # W/m²·K⁴ — constante de Stefan-Boltzmann
R_AIRE: float = 287.058           # J/kg·K  — constante específica del aire seco
G_GRAVEDAD: float = 9.81          # m/s² — aceleración gravitatoria

# Propiedades del aire a 323 K (50 °C), presión estándar
CP_AIRE: float = 1007.0      # J/kg·K
K_AIRE: float = 0.02814      # W/m·K
MU_AIRE: float = 1.963e-5    # Pa·s
PR_AIRE: float = 0.703       # adimensional
RHO_AIRE_REF: float = 1.093  # kg/m³ a 323 K, 101325 Pa

# Límites de validez
V_VIENTO_LIMITE_MCADAMS: float = 5.0  # m/s — por encima se emite advertencia

# Parámetros del solver
N_NODOS_MIN: int = 50    # número mínimo de nodos de integración
TOL_FSOLVE: float = 1e-8


# =============================================================================
# Dataclass de resultados
# =============================================================================

@dataclass
class ResultadosColectorTipo1:
    """Resultados del motor numérico para el Colector Tipo 1.

    Todos los arrays tienen longitud n_puntos (coordenadas x del solver).
    Temperaturas en Kelvin. Potencias en Watts. Longitudes en metros.

    Attributes:
        x_m: Coordenadas x a lo largo del colector [m].
        T_fluido_K: Perfil de temperatura del fluido [K].
        T_abs_K: Perfil de temperatura del absorbedor [K].
        T_cub_i_K: Perfil de temperatura cara interna de cubierta [K].
        T_cub_e_K: Perfil de temperatura cara externa de cubierta [K].
        T_bot_K: Perfil de temperatura cara externa del fondo [K].
        T_entrada_K: Temperatura de entrada del fluido [K].
        T_salida_K: Temperatura de salida del fluido [K].
        Q_util_W: Potencia útil entregada al fluido [W].
        Q_incidente_W: Potencia solar incidente sobre la cubierta [W].
        eta_termica: Eficiencia térmica = Q_util / Q_incidente [adim].
        h_int_medio: Coeficiente convectivo interno medio [W/m²·K].
        h_viento: Coeficiente convectivo de viento [W/m²·K].
        Re_medio: Número de Reynolds medio en el canal.
        regimen_flujo: 'laminar', 'transicion' o 'turbulento'.
        advertencias: Lista de códigos de advertencia generados.
        convergencia_ok: True si solve_ivp y todos los fsolve convergieron.
        mensaje_convergencia: Descripción del estado de convergencia.
    """

    x_m: np.ndarray
    T_fluido_K: np.ndarray
    T_abs_K: np.ndarray
    T_cub_i_K: np.ndarray
    T_cub_e_K: np.ndarray
    T_bot_K: np.ndarray
    T_entrada_K: float
    T_salida_K: float
    Q_util_W: float
    Q_incidente_W: float
    eta_termica: float
    h_int_medio: float
    h_viento: float
    Re_medio: float
    regimen_flujo: str
    advertencias: list[str] = field(default_factory=list)
    convergencia_ok: bool = True
    mensaje_convergencia: str = "OK"


# =============================================================================
# Funciones auxiliares — correlaciones y propiedades
# =============================================================================

def _T_cielo_K(T_amb_K: float) -> float:
    """Temperatura de cielo según correlación de Swinbank (1963).

    Args:
        T_amb_K: Temperatura ambiente [K].

    Returns:
        Temperatura efectiva del cielo [K].

    References:
        Swinbank, W.C. (1963). Q. J. R. Meteorol. Soc. 89, 339-348.
    """
    return 0.0552 * T_amb_K ** 1.5


def _h_viento_W_m2K(v_viento_ms: float) -> tuple[float, list[str]]:
    """Coeficiente convectivo superficial por viento según McAdams (1954).

    Válida estrictamente para v < 5 m/s. Para v ≥ 5 m/s se aplica la misma
    expresión pero se emite advertencia COL_VIENTO_FUERA_RANGO_MCADAMS.

    Args:
        v_viento_ms: Velocidad del viento a 2 m de altura [m/s].

    Returns:
        Tupla (h_wind [W/m²·K], lista_advertencias).

    References:
        McAdams, W.H. (1954). Heat Transmission, 3ª ed. McGraw-Hill.
    """
    advertencias: list[str] = []
    if v_viento_ms >= V_VIENTO_LIMITE_MCADAMS:
        advertencias.append(
            f"COL_VIENTO_FUERA_RANGO_MCADAMS: v_viento={v_viento_ms:.1f} m/s ≥ 5 m/s. "
            "Correlación de McAdams aplicada fuera de su rango de validez."
        )
    h_wind = 5.7 + 3.8 * v_viento_ms
    return h_wind, advertencias


def _diametro_hidraulico_m(alto_canal_m: float, ancho_m: float) -> float:
    """Diámetro hidráulico de un canal rectangular [m].

    Para un canal muy ancho (W >> Alto), Dh → 2*Alto (canal plano).

    Args:
        alto_canal_m: Altura del canal de flujo [m].
        ancho_m: Ancho del colector [m].

    Returns:
        Diámetro hidráulico [m].
    """
    return 2.0 * alto_canal_m * ancho_m / (alto_canal_m + ancho_m)





def _T_bot_K(
    T_abs_K: float,
    T_amb_K: float,
    k_ais_W_mK: float,
    esp_ais_m: float,
    h_wind_W_m2K: float,
) -> float:
    """Temperatura de la cara externa del fondo del colector (despeje algebraico).

    Balance: conducción aislante = convección al ambiente.
        k_ais/esp_ais * (T_abs - T_bot) = h_wind * (T_bot - T_amb)

    Args:
        T_abs_K: Temperatura del absorbedor [K].
        T_amb_K: Temperatura ambiente [K].
        k_ais_W_mK: Conductividad térmica del aislante [W/m·K].
        esp_ais_m: Espesor del aislante [m].
        h_wind_W_m2K: Coeficiente convectivo de viento [W/m²·K].

    Returns:
        Temperatura cara externa del fondo [K].
    """
    U_ais = k_ais_W_mK / esp_ais_m  # conductancia aislante [W/m²·K]
    return (U_ais * T_abs_K + h_wind_W_m2K * T_amb_K) / (U_ais + h_wind_W_m2K)


def _em_efectiva_paralelas(em_cub: float, em_abs: float) -> float:
    """Emisividad efectiva para intercambio radiativo entre superficies paralelas.

    Hipótesis: factor de forma F = 1 (superficies infinitas paralelas).
        1/em_eff = 1/em_cub + 1/em_abs - 1

    Args:
        em_cub: Emisividad IR de la cubierta [adim].
        em_abs: Emisividad IR del absorbedor [adim].

    Returns:
        Emisividad efectiva [adim].
    """
    return 1.0 / (1.0 / em_cub + 1.0 / em_abs - 1.0)


def _h_cavidad_aire(
    T_sup_K: float,
    T_inf_K: float,
    esp_cav_m: float,
    em_sup: float,
    em_inf: float,
    pendiente_deg: float,
    P_amb_Pa: float,
) -> float:
    """Coeficiente de transferencia en cavidad de aire entre dos superficies paralelas.

    Combina convección natural (Hollands inclinada) y radiación entre superficies
    grises paralelas. Usado para modelar la cavidad entre cubiertas cuando
    n_cubiertas == 2.

    Las temperaturas T_sup_K y T_inf_K son las que bordean la cavidad. En el
    modelo simplificado de doble cubierta se usan como proxies T_cub_e (cara
    externa de la cubierta exterior) y T_cub_i (cara interna de la interior),
    aceptando un error <5% porque la resistencia conductiva de cada cubierta
    es despreciable frente a la de la cavidad.

    Args:
        T_sup_K: Temperatura de la superficie superior (más fría) [K].
        T_inf_K: Temperatura de la superficie inferior (más caliente) [K].
        esp_cav_m: Espesor de la cavidad [m].
        em_sup: Emisividad IR de la superficie superior [adim].
        em_inf: Emisividad IR de la superficie inferior [adim].
        pendiente_deg: Inclinación del colector respecto a la horizontal [°].
        P_amb_Pa: Presión ambiente para evaluar densidad del aire [Pa].

    Returns:
        h_cav [W/m²·K] = h_conv_natural + h_rad.
    """
    # Propiedades del aire a la temperatura media de cavidad (gas ideal).
    T_film = 0.5 * (T_sup_K + T_inf_K)
    rho = P_amb_Pa / (R_AIRE * T_film)
    beta = 1.0 / T_film
    nu = MU_AIRE / rho
    alpha = K_AIRE / (rho * CP_AIRE)

    delta_T = abs(T_inf_K - T_sup_K)
    if delta_T < 1e-6:
        # cavidad isotérmica → solo conducción pura del aire
        Nu = 1.0
    else:
        Ra = G_GRAVEDAD * beta * delta_T * esp_cav_m**3 / (nu * alpha)
        Nu = nusselt_hollands_inclinada(Ra, min(pendiente_deg, 75.0))

    h_conv = Nu * K_AIRE / esp_cav_m

    # Radiación entre superficies grises paralelas: linealizada como
    # h_rad = ε_eff·σ·(T_sup² + T_inf²)(T_sup + T_inf)
    em_eff = 1.0 / (1.0 / em_sup + 1.0 / em_inf - 1.0)
    h_rad = em_eff * SIGMA_SB * (T_sup_K**2 + T_inf_K**2) * (T_sup_K + T_inf_K)

    return h_conv + h_rad


def _U_cubierta_efectiva(
    n_cubiertas: int,
    T_cub_e_K: float,
    T_cub_i_K: float,
    k_cub: float,
    esp_cub_m: float,
    em_cub: float,
    esp_cav_m: float,
    pendiente_deg: float,
    P_amb_Pa: float,
) -> float:
    """Conductancia efectiva entre la cara externa y la cara interna de la cubierta.

    Para n_cubiertas == 1, devuelve la conductancia conductiva clásica
    k_cub/esp_cub. Para n_cubiertas == 2, devuelve una conductancia serie que
    suma dos conductancias conductivas (una por cubierta) y la cavidad de aire
    entre ellas (convección natural + radiación entre superficies grises).

    Args:
        n_cubiertas: 1 ó 2.
        T_cub_e_K: Temperatura cara externa de la cubierta exterior [K].
        T_cub_i_K: Temperatura cara interna de la cubierta interior [K].
        k_cub: Conductividad térmica del material de cubierta [W/m·K].
        esp_cub_m: Espesor de CADA cubierta [m].
        em_cub: Emisividad IR de la cubierta [adim].
        esp_cav_m: Espaciado entre cubiertas (solo usado si n_cubiertas==2) [m].
        pendiente_deg: Inclinación del colector [°].
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        U_eff [W/m²·K].
    """
    if n_cubiertas == 1:
        return k_cub / esp_cub_m

    h_cav = _h_cavidad_aire(
        T_sup_K=T_cub_e_K, T_inf_K=T_cub_i_K,
        esp_cav_m=esp_cav_m,
        em_sup=em_cub, em_inf=em_cub,
        pendiente_deg=pendiente_deg,
        P_amb_Pa=P_amb_Pa,
    )
    R_total = 2.0 * (esp_cub_m / k_cub) + 1.0 / h_cav
    return 1.0 / R_total


# =============================================================================
# Sistema no lineal en cada nodo
# =============================================================================

def _sistema_nodo(
    vars_: np.ndarray,
    T_f_K: float,
    T_amb_K: float,
    T_cie_K: float,
    I_g_W_m2: float,
    h_wind: float,
    h_int: float,
    k_cub: float,
    esp_cub: float,
    em_cub: float,
    k_ais: float,
    esp_ais: float,
    em_abs: float,
    tau_cub: float,
    alfa_abs: float,
    W_m: float,
    W_abs_m: float,
    n_cubiertas: int = 1,
    esp_cav_m: float = 0.025,
    pendiente_deg: float = 30.0,
    P_amb_Pa: float = 101325.0,
) -> np.ndarray:
    """Sistema de 3 ecuaciones algebraicas no lineales en cada nodo x.

    Incógnitas en vars_: [T_cub_e_K, T_cub_i_K, T_abs_K].

    Las ecuaciones corresponden a los balances de energía (en régimen
    cuasi-estacionario, por unidad de área diferencial dA = W·dx):

    F1: balance cubierta — cara externa e interna acopladas por conducción.
    F2: balance cubierta cara interna — convección con fluido + radiación abs.
    F3: balance absorbedor — radiación incidente + conv fluido + rad cubierta
        + conducción al fondo.

    Todos los términos radiativos usan temperaturas en Kelvin directamente
    (sin conversión +273.15 dado que las T ya están en K).

    Args:
        vars_: Array [T_cub_e_K, T_cub_i_K, T_abs_K].
        T_f_K: Temperatura local del fluido [K].
        T_amb_K: Temperatura ambiente [K].
        T_cie_K: Temperatura efectiva de cielo [K].
        I_g_W_m2: Irradiancia global sobre plano inclinado [W/m²].
        h_wind: Coeficiente convectivo de viento [W/m²·K].
        h_int: Coeficiente convectivo interno [W/m²·K].
        k_cub: Conductividad térmica de la cubierta [W/m·K].
        esp_cub: Espesor de la cubierta [m].
        em_cub: Emisividad IR de la cubierta [adim].
        k_ais: Conductividad térmica del aislante [m].
        esp_ais: Espesor del aislante [m].
        em_abs: Emisividad IR del absorbedor [adim].
        tau_cub: Transmitancia solar de la cubierta [adim].
        alfa_abs: Absortividad solar del absorbedor [adim].
        W_m: Ancho del colector [m].
        W_abs_m: Ancho efectivo del absorbedor [m].

    Returns:
        Array de residuos [F1, F2, F3]. El solver busca la raíz (residuos = 0).
    """
    T_cub_e, T_cub_i, T_abs = vars_

    em_eff = _em_efectiva_paralelas(em_cub, em_abs)
    # Conductancia cubierta: simple (n=1) o efectiva con cavidad de aire (n=2).
    U_cub = _U_cubierta_efectiva(
        n_cubiertas=n_cubiertas,
        T_cub_e_K=T_cub_e, T_cub_i_K=T_cub_i,
        k_cub=k_cub, esp_cub_m=esp_cub, em_cub=em_cub,
        esp_cav_m=esp_cav_m, pendiente_deg=pendiente_deg,
        P_amb_Pa=P_amb_Pa,
    )
    U_ais = k_ais / esp_ais   # conductancia aislante [W/m²·K]
    T_bot = _T_bot_K(T_abs, T_amb_K, k_ais, esp_ais, h_wind)

    # --- F1: balance cara externa de cubierta ---
    # En operación normal T_cub_i > T_cub_e: la cara externa GANA por conducción
    # desde la cara interna y PIERDE por convección al viento + radiación al cielo.
    # Con conduccion_cub = U·(T_cub_e − T_cub_i), eso es NEGATIVO en op. normal,
    # por lo que el aporte conductivo a T_cub_e es −conduccion_cub (positivo).
    # Balance: ganancia − pérdidas = 0  →  −conduccion_cub − (conv + rad) = 0
    # equivalente a:  conv + rad + conduccion_cub = 0.
    conv_viento = h_wind * (T_cub_e - T_amb_K)
    rad_cielo = em_cub * SIGMA_SB * (T_cub_e ** 4 - T_cie_K ** 4)
    conduccion_cub = U_cub * (T_cub_e - T_cub_i)
    F1 = conv_viento + rad_cielo + conduccion_cub

    # --- F2: balance cara interna de cubierta ---
    # Ganancia: conducción desde cara externa.
    # Pérdidas: convección al fluido + radiación al absorbedor.
    conv_fluido_cub = h_int * (T_cub_i - T_f_K)          # pérdida → fluido
    rad_abs_cub = em_eff * SIGMA_SB * (T_cub_i ** 4 - T_abs ** 4)  # pérdida → abs
    F2 = conduccion_cub - conv_fluido_cub - rad_abs_cub

    # --- F3: balance absorbedor ---
    # Ganancia: radiación solar transmitida y absorbida.
    # Pérdidas: convección al fluido (T_abs > T_f), radiación a la cubierta
    # interna (T_abs > T_cub_i) y conducción a la cara externa del fondo
    # vía el aislante (T_abs > T_bot).
    # Nota: W_abs_m puede diferir de W_m (absorbedor ondulado).
    # Los términos que involucran el canal (conv fluido, rad cubierta)
    # se escalan con W_m (área proyectada); la absorción solar y la pérdida
    # al fondo se escalan con W_abs_m.
    # Por unidad de longitud dx (se cancela en el cociente):
    rad_solar_abs = I_g_W_m2 * tau_cub * alfa_abs * W_abs_m
    conv_fluido_abs = h_int * (T_abs - T_f_K) * W_abs_m
    rad_cub_abs = em_eff * SIGMA_SB * (T_abs ** 4 - T_cub_i ** 4) * W_m
    cond_fondo = U_ais * (T_abs - T_bot) * W_abs_m

    F3 = rad_solar_abs - conv_fluido_abs - rad_cub_abs - cond_fondo

    return np.array([F1, F2, F3])


# =============================================================================
# RHS de la EDO del fluido
# =============================================================================

def _construir_rhs(params: dict):
    """Construye la función RHS para solve_ivp dado el diccionario de parámetros.

    La EDO del fluido es:
        dT_f/dx = [h_int*(T_cub_i - T_f)*W + h_int*(T_abs - T_f)*W_abs]
                  / (m_punto * cp_aire)

    El sistema algebraico (T_cub_e, T_cub_i, T_abs) se resuelve en cada
    evaluación con fsolve, usando el valor previo como punto de partida.

    Args:
        params: Diccionario con todos los parámetros físicos y geométricos.

    Returns:
        Función rhs(x, y) compatible con solve_ivp, donde y = [T_f_K].
    """
    # Estado mutable para warm-start de fsolve (mejora convergencia y velocidad)
    estado = {"guess": None}
    log_no_convergencia = []

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        T_f_K = float(y[0])

        # Punto de partida para fsolve
        if estado["guess"] is None:
            # Estimación inicial conservadora en el primer nodo
            T_amb = params["T_amb_K"]
            T_g = T_amb + 0.5 * params["I_g_W_m2"] / 10.0  # estimación grosera
            estado["guess"] = np.array([T_g, T_g + 5.0, T_g + 20.0])

        sol, info, ier, msg = fsolve(
            _sistema_nodo,
            estado["guess"],
            args=(
                T_f_K,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                params["h_int"],
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["tau_cub"],
                params["alfa_abs"],
                params["W_m"],
                params["W_abs_m"],
                params.get("n_cubiertas", 1),
                params.get("esp_cav_m", 0.025),
                params.get("pendiente_deg", 30.0),
                params.get("P_amb_Pa", 101325.0),
            ),
            full_output=True,
            xtol=TOL_FSOLVE,
        )

        if ier != 1:
            log_no_convergencia.append((x, msg))
            # Continúa con la solución aproximada (solve_ivp es robusto)

        # Warm-start: la solución actual es buen punto de partida para x + dx
        estado["guess"] = sol.copy()

        T_cub_i = sol[1]
        T_abs = sol[2]
        W_m = params["W_m"]
        W_abs_m = params["W_abs_m"]
        h_int = params["h_int"]
        m_punto = params["m_punto_kgs"]

        dTf_dx = (
            h_int * (T_cub_i - T_f_K) * W_m
            + h_int * (T_abs - T_f_K) * W_abs_m
        ) / (m_punto * CP_AIRE)

        return np.array([dTf_dx])

    return rhs, log_no_convergencia


# =============================================================================
# Función principal
# =============================================================================

def calcular_colector_tipo1(
    colector: "Colector",
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    P_amb_Pa: float,
    T_entrada_K: float,
    correlacion_nusselt: str | None = None,
    pendiente_deg: float = 30.0,
) -> ResultadosColectorTipo1:
    """Calcula el comportamiento térmico del colector solar Tipo 1.

    Integra la EDO de temperatura del fluido a lo largo del colector y
    resuelve el sistema algebraico de superficies en cada punto.

    Args:
        colector: Instancia de Colector del core (con ColectorUnidad y
            BancoColectores definidos).
        T_amb_K: Temperatura ambiente [K].
        I_g_W_m2: Irradiancia global sobre el plano del colector [W/m²].
        v_viento_ms: Velocidad del viento a 2 m [m/s].
        P_amb_Pa: Presión atmosférica ambiente [Pa].
        T_entrada_K: Temperatura del aire a la entrada del colector [K].
        correlacion_nusselt: Nombre de la correlación de Nusselt a usar
            (ver ``calculos.correlaciones_nusselt.CORRELACIONES_FORZADO``).
            Si None, se selecciona automáticamente según Re y L/Dh.

    Returns:
        ResultadosColectorTipo1 con perfiles de temperatura y métricas globales.

    Raises:
        ValueError: Si I_g_W_m2 < 0 o T_entrada_K ≤ 0.
        RuntimeError: Si solve_ivp no converge.
    """
    # --- Validaciones de entrada ---
    if I_g_W_m2 < 0.0:
        raise ValueError(f"I_g_W_m2 debe ser ≥ 0. Recibido: {I_g_W_m2}")
    if T_entrada_K <= 0.0:
        raise ValueError(f"T_entrada_K debe ser > 0 K. Recibido: {T_entrada_K}")

    advertencias: list[str] = []

    # --- Extraer geometría y materiales del colector ---
    unidad = colector.unidad           # ColectorUnidad
    banco = colector.banco             # BancoColectores

    W_m: float = unidad.ancho_m
    L_unidad_m: float = unidad.largo_m
    esp_canal_m: float = unidad.espaciado_m   # alto del canal de flujo

    # Largo total del camino del aire (n_serie unidades en serie)
    L_total_m: float = L_unidad_m * banco.n_serie

    # Ancho efectivo del absorbedor (puede ser > W para chapa ondulada)
    # Por ahora W_abs = W (absorbedor plano). El usuario puede extender esto.
    W_abs_m: float = W_m

    # Flujo másico total y por rama paralela
    # Q_total = n_paralelo * v_diseno * ancho * espaciado
    v_diseno = unidad.velocidad_diseno_ms
    Q_total_m3s = banco.n_paralelo * v_diseno * W_m * esp_canal_m
    m_punto_total_kgs = RHO_AIRE_REF * Q_total_m3s
    # Cada rama paralela ve el mismo flujo másico
    m_punto_rama_kgs = m_punto_total_kgs / banco.n_paralelo

    # Propiedades ópticas y térmicas de materiales
    # (acceso directo a los catálogos ya cargados en ColectorUnidad)
    from core.catalogo import CUBIERTAS, PLACAS, AISLANTES

    mat_cub = CUBIERTAS[unidad.id_cubierta]
    mat_placa = PLACAS[unidad.id_placa]
    mat_ais = AISLANTES[unidad.id_aislante]

    tau_cub: float = mat_cub["transmitancia_solar"]
    em_cub: float = mat_cub["emisividad_ir"]
    k_cub: float = mat_cub["conductividad_termica"]
    esp_cub_m: float = unidad.espesor_cubierta_m

    alfa_abs: float = mat_placa["absortancia_solar"]
    em_abs: float = mat_placa["emisividad_ir"]

    k_ais: float = mat_ais["conductividad_termica"]
    esp_ais_m: float = unidad.espesor_aislante_m

    # --- Correlaciones atmosféricas ---
    T_cie_K = _T_cielo_K(T_amb_K)
    h_wind, adv_viento = _h_viento_W_m2K(v_viento_ms)
    advertencias.extend(adv_viento)

    # --- Coeficiente convectivo interno ---
    # Tipo 1: pared inferior caliente (absorbedor), pared superior fría (cubierta).
    # Se delega a correlaciones_nusselt.calcular_h_int() que selecciona
    # automáticamente la correlación según Re y L/Dh. El parámetro
    # correlacion_nusselt permite al usuario elegir una correlación específica
    # desde la UI (None = selección automática).
    Dh_m = _diametro_hidraulico_m(esp_canal_m, W_m)
    A_seccion_m2 = esp_canal_m * W_m
    v_media_ms = m_punto_rama_kgs / (RHO_AIRE_REF * A_seccion_m2)
    Re_medio = RHO_AIRE_REF * v_media_ms * Dh_m / MU_AIRE

    h_int, _, nombre_correlacion, regimen, adv_nusselt = calcular_h_int(
        Re=Re_medio,
        Pr=PR_AIRE,
        Dh_m=Dh_m,
        L_m=L_total_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",   # Tipo 1: absorbedor caliente, cubierta fría
        modo="forzado",
        correlacion=correlacion_nusselt,
    )
    advertencias.extend(adv_nusselt)

    # --- Empaquetar parámetros para el solver ---
    params = {
        "T_amb_K": T_amb_K,
        "T_cie_K": T_cie_K,
        "I_g_W_m2": I_g_W_m2,
        "h_wind": h_wind,
        "h_int": h_int,
        "k_cub": k_cub,
        "esp_cub_m": esp_cub_m,
        "em_cub": em_cub,
        "k_ais": k_ais,
        "esp_ais_m": esp_ais_m,
        "em_abs": em_abs,
        "tau_cub": tau_cub,
        "alfa_abs": alfa_abs,
        "W_m": W_m,
        "W_abs_m": W_abs_m,
        "m_punto_kgs": m_punto_rama_kgs,
        "n_cubiertas": unidad.n_cubiertas,
        "esp_cav_m": unidad.espaciado_entre_cubiertas_m,
        "pendiente_deg": pendiente_deg,
        "P_amb_Pa": P_amb_Pa,
    }

    # --- Integración con solve_ivp ---
    rhs_fn, log_no_conv = _construir_rhs(params)

    max_step = L_total_m / N_NODOS_MIN

    resultado_ivp = solve_ivp(
        fun=rhs_fn,
        t_span=(0.0, L_total_m),
        y0=[T_entrada_K],
        method="RK45",
        max_step=max_step,
        dense_output=False,
        rtol=1e-6,
        atol=1e-6,
    )

    convergencia_ok = resultado_ivp.success
    mensaje_convergencia = resultado_ivp.message if not convergencia_ok else "OK"

    if not convergencia_ok:
        raise RuntimeError(
            f"solve_ivp no convergió: {mensaje_convergencia}"
        )

    if log_no_conv:
        advertencias.append(
            f"COL_FSOLVE_NO_CONVERGE: fsolve no convergió en {len(log_no_conv)} "
            f"de {len(resultado_ivp.t)} nodos. Resultados pueden ser imprecisos."
        )

    # --- Reconstruir perfiles de superficies ---
    x_arr = resultado_ivp.t
    T_f_arr = resultado_ivp.y[0]
    n_puntos = len(x_arr)

    T_cub_e_arr = np.empty(n_puntos)
    T_cub_i_arr = np.empty(n_puntos)
    T_abs_arr = np.empty(n_puntos)
    T_bot_arr = np.empty(n_puntos)

    guess = None
    for i, (T_f_i) in enumerate(T_f_arr):
        if guess is None:
            T_g = T_amb_K + 0.5 * I_g_W_m2 / 10.0
            guess = np.array([T_g, T_g + 5.0, T_g + 20.0])

        sol = fsolve(
            _sistema_nodo,
            guess,
            args=(
                T_f_i,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                params["h_int"],
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["tau_cub"],
                params["alfa_abs"],
                params["W_m"],
                params["W_abs_m"],
                params.get("n_cubiertas", 1),
                params.get("esp_cav_m", 0.025),
                params.get("pendiente_deg", 30.0),
                params.get("P_amb_Pa", 101325.0),
            ),
            xtol=TOL_FSOLVE,
        )
        T_cub_e_arr[i] = sol[0]
        T_cub_i_arr[i] = sol[1]
        T_abs_arr[i] = sol[2]
        T_bot_arr[i] = _T_bot_K(sol[2], T_amb_K, k_ais, esp_ais_m, h_wind)
        guess = sol.copy()

    # --- Métricas globales ---
    T_salida_K = float(T_f_arr[-1])
    Q_util_W = m_punto_total_kgs * CP_AIRE * (T_salida_K - T_entrada_K)
    A_colector_total_m2 = W_m * L_total_m * banco.n_paralelo
    Q_incidente_W = I_g_W_m2 * tau_cub * A_colector_total_m2

    eta_termica = Q_util_W / Q_incidente_W if Q_incidente_W > 0.0 else 0.0

    return ResultadosColectorTipo1(
        x_m=x_arr,
        T_fluido_K=T_f_arr,
        T_abs_K=T_abs_arr,
        T_cub_i_K=T_cub_i_arr,
        T_cub_e_K=T_cub_e_arr,
        T_bot_K=T_bot_arr,
        T_entrada_K=T_entrada_K,
        T_salida_K=T_salida_K,
        Q_util_W=Q_util_W,
        Q_incidente_W=Q_incidente_W,
        eta_termica=eta_termica,
        h_int_medio=h_int,
        h_viento=h_wind,
        Re_medio=Re_medio,
        regimen_flujo=regimen,
        advertencias=advertencias,
        convergencia_ok=convergencia_ok,
        mensaje_convergencia=mensaje_convergencia,
    )
