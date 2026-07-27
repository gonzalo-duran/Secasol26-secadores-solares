"""Motor numérico de colectores solares de aire — Tipos 2, 3 y 4.

Tipo 2: absorbedor a media altura, flujo por ambos canales (superior e inferior).
Tipo 3: absorbedor a media altura, flujo por canal inferior, canal superior estanco.
Tipo 4: absorbedor a media altura, flujo por canal superior, canal inferior estanco.

Modelo cuasi-estacionario con discretización espacial en x (dirección del flujo).
En cada nodo x se resuelve un sistema algebraico no lineal para obtener las
temperaturas de las superficies sólidas. Las temperaturas del fluido se integran
con scipy.integrate.solve_ivp.

Geometría común (Tipos 2, 3, 4)
--------------------------------
    cubierta (esp_cub)
    ─────────────────────────────  ← T_cub_e / T_cub_i
    canal superior  (alto_c1)      ← fluido canal superior T_f_cs
    ─────────────────────────────  ← absorbedor T_abs  (espesor despreciable)
    canal inferior  (alto_c2)      ← fluido canal inferior T_f_ci
    ─────────────────────────────  ← cara interna fondo T_int / cara externa T_bot
    aislante        (esp_ais)

Diferencias entre tipos
-----------------------
- Tipo 2: ambos canales activos. Sistema: 2 EDOs + 4 ecuaciones algebraicas.
- Tipo 3: canal inferior activo, canal superior estanco.
          T_f_cs se despeja analíticamente: T_f_cs = (T_cub_i + T_abs) / 2
          Sistema: 1 EDO + 4 ecuaciones algebraicas.
- Tipo 4: canal superior activo, canal inferior estanco.
          T_f_ci se despeja analíticamente: T_f_ci = (T_abs + T_int) / 2
          Sistema: 1 EDO + 4 ecuaciones algebraicas.

Hipótesis
---------
- Cuasi-estacionario: sin acumulación de calor en superficies sólidas.
- Flujo unidireccional en x, desarrollado.
- Sin conducción de calor en el absorbedor (espesor despreciable) → ambas
  caras del absorbedor a T_abs.
- Factor de forma radiativo = 1 en todos los intercambios radiativos internos
  (cubierta↔absorbedor, absorbedor↔fondo interior).
- Absortividad de la cubierta despreciable.
- Coeficiente convectivo interno del canal activo con propiedades del aire LOCALES
  evaluadas en T_f(x) (Re y Nu locales, flotación; vía
  ``coef_conveccion_interna_local``, S36), y cp(T) local en los balances de energía;
  el caudal másico se fija con rho_aire(T_entrada). Quedan constantes a 323 K (50 °C)
  las propiedades del aire estanco (correlación de cavidad Hollands) y las de los
  evaluadores simplificados de campo/banco (preview de P3).
- En Tipo 2: ambos canales comparten T_entrada_K. Los caudales se especifican
  por la velocidad de diseño de cada canal independientemente.

Correlaciones
-------------
- T_cielo:  Swinbank (1963).
- h_viento: McAdams (1954); advertencia para v ≥ 5 m/s.
- h_int:    calculos.correlaciones_nusselt.calcular_h_int().
  - Tipo 2 canal superior: pared="una_pared" (absorbedor + cubierta, pero
    la cubierta es fría → asimétrico; se usa una_pared como aproximación).
  - Tipo 2 canal inferior: pared="dos_paredes" (absorbedor arriba, fondo abajo,
    ambos con flujo de calor → simétrico).
  - Tipos 3 y 4: pared="una_pared" en el canal activo.

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

from calculos.colector_calc import _U_cubierta_efectiva, coef_conveccion_interna_local
from calculos.correlaciones_nusselt import calcular_h_int, nusselt_hollands_inclinada
from calculos.propiedades_aire import cp_aire, rho_aire

if TYPE_CHECKING:
    from core.colector import Colector

# =============================================================================
# Constantes físicas (idénticas a colector_calc.py)
# =============================================================================

SIGMA_SB: float = 5.670374419e-8  # W/m²·K⁴
R_AIRE: float = 287.058  # J/kg·K

CP_AIRE: float = 1007.0  # J/kg·K
K_AIRE: float = 0.02814  # W/m·K
MU_AIRE: float = 1.963e-5  # Pa·s
PR_AIRE: float = 0.703  # adim
RHO_AIRE_REF: float = 1.093  # kg/m³ a 323 K, 101325 Pa

V_VIENTO_LIMITE_MCADAMS: float = 5.0  # m/s

G_ACELERACION: float = 9.81  # m/s²
NU_AIRE: float = MU_AIRE / RHO_AIRE_REF  # m²/s — viscosidad cinemática a 323 K

N_NODOS_MIN: int = 50
TOL_FSOLVE: float = 1e-8

# Mínimo absoluto de altura de canal aceptado por los motores Tipos 2/3/4.
# Debe mantenerse sincronizado con _ESP_MIN_M en core/colector.py (5 mm).
# Se duplica como constante local para que calculos/ no dependa de core/.
ALTO_CANAL_MIN_M: float = 0.005


# =============================================================================
# Dataclasses de resultados
# =============================================================================


@dataclass
class ResultadosColectorTipo2:
    """Resultados del motor numérico para el Colector Tipo 2.

    Flujo activo en ambos canales (superior e inferior).
    Arrays de longitud n_puntos. Temperaturas en K, potencias en W.

    Attributes:
        x_m: Coordenadas x [m].
        T_f_cs_K: Perfil T fluido canal superior [K].
        T_f_ci_K: Perfil T fluido canal inferior [K].
        T_abs_K: Perfil T absorbedor [K].
        T_cub_i_K: Perfil T cara interna cubierta [K].
        T_cub_e_K: Perfil T cara externa cubierta [K].
        T_int_K: Perfil T cara interna fondo [K].
        T_bot_K: Perfil T cara externa fondo [K].
        T_entrada_K: T de entrada compartida por ambos canales [K].
        T_salida_cs_K: T de salida canal superior [K].
        T_salida_ci_K: T de salida canal inferior [K].
        T_salida_mezcla_K: T de mezcla a la salida (ponderada por m_punto) [K].
        Q_util_W: Potencia útil total entregada al fluido [W].
        Q_incidente_W: Potencia solar incidente sobre cubierta [W].
        eta_termica: Eficiencia térmica = Q_util / Q_incidente [adim].
        h_int_cs: Coeficiente convectivo canal superior [W/m²·K].
        h_int_ci: Coeficiente convectivo canal inferior [W/m²·K].
        h_viento: Coeficiente convectivo de viento [W/m²·K].
        Re_cs: Reynolds canal superior.
        Re_ci: Reynolds canal inferior.
        regimen_cs: Régimen de flujo canal superior.
        regimen_ci: Régimen de flujo canal inferior.
        advertencias: Lista de códigos de advertencia.
        convergencia_ok: True si solve_ivp convergió.
        mensaje_convergencia: Estado de convergencia.
    """

    x_m: np.ndarray
    T_f_cs_K: np.ndarray
    T_f_ci_K: np.ndarray
    T_abs_K: np.ndarray
    T_cub_i_K: np.ndarray
    T_cub_e_K: np.ndarray
    T_int_K: np.ndarray
    T_bot_K: np.ndarray
    T_entrada_K: float
    T_salida_cs_K: float
    T_salida_ci_K: float
    T_salida_mezcla_K: float
    Q_util_W: float
    Q_incidente_W: float
    eta_termica: float
    h_int_cs: float
    h_int_ci: float
    h_viento: float
    Re_cs: float
    Re_ci: float
    regimen_cs: str
    regimen_ci: str
    advertencias: list[str] = field(default_factory=list)
    convergencia_ok: bool = True
    mensaje_convergencia: str = "OK"


@dataclass
class ResultadosColectorTipo3:
    """Resultados del motor numérico para el Colector Tipo 3.

    Flujo activo en canal inferior. Canal superior estanco.
    Arrays de longitud n_puntos. Temperaturas en K, potencias en W.

    Attributes:
        x_m: Coordenadas x [m].
        T_f_ci_K: Perfil T fluido canal inferior (activo) [K].
        T_f_cs_K: Perfil T aire canal superior estanco [K].
        T_abs_K: Perfil T absorbedor [K].
        T_cub_i_K: Perfil T cara interna cubierta [K].
        T_cub_e_K: Perfil T cara externa cubierta [K].
        T_int_K: Perfil T cara interna fondo [K].
        T_bot_K: Perfil T cara externa fondo [K].
        T_entrada_K: T de entrada canal inferior [K].
        T_salida_K: T de salida canal inferior [K].
        Q_util_W: Potencia útil entregada al fluido [W].
        Q_incidente_W: Potencia solar incidente [W].
        eta_termica: Eficiencia térmica [adim].
        h_int_ci: Coeficiente convectivo canal inferior [W/m²·K].
        h_int_cs: Coeficiente convectivo canal superior (estanco) [W/m²·K].
        h_viento: Coeficiente convectivo de viento [W/m²·K].
        Re_ci: Reynolds canal inferior.
        regimen_ci: Régimen de flujo canal inferior.
        advertencias: Lista de advertencias.
        convergencia_ok: True si solve_ivp convergió.
        mensaje_convergencia: Estado de convergencia.
    """

    x_m: np.ndarray
    T_f_ci_K: np.ndarray
    T_f_cs_K: np.ndarray
    T_abs_K: np.ndarray
    T_cub_i_K: np.ndarray
    T_cub_e_K: np.ndarray
    T_int_K: np.ndarray
    T_bot_K: np.ndarray
    T_entrada_K: float
    T_salida_K: float
    Q_util_W: float
    Q_incidente_W: float
    eta_termica: float
    h_int_ci: float
    h_int_cs: float
    h_viento: float
    Re_ci: float
    regimen_ci: str
    advertencias: list[str] = field(default_factory=list)
    convergencia_ok: bool = True
    mensaje_convergencia: str = "OK"


@dataclass
class ResultadosColectorTipo4:
    """Resultados del motor numérico para el Colector Tipo 4.

    Flujo activo en canal superior. Canal inferior estanco.
    Arrays de longitud n_puntos. Temperaturas en K, potencias en W.

    Attributes:
        x_m: Coordenadas x [m].
        T_f_cs_K: Perfil T fluido canal superior (activo) [K].
        T_f_ci_K: Perfil T aire canal inferior estanco [K].
        T_abs_K: Perfil T absorbedor [K].
        T_cub_i_K: Perfil T cara interna cubierta [K].
        T_cub_e_K: Perfil T cara externa cubierta [K].
        T_int_K: Perfil T cara interna fondo [K].
        T_bot_K: Perfil T cara externa fondo [K].
        T_entrada_K: T de entrada canal superior [K].
        T_salida_K: T de salida canal superior [K].
        Q_util_W: Potencia útil entregada al fluido [W].
        Q_incidente_W: Potencia solar incidente [W].
        eta_termica: Eficiencia térmica [adim].
        h_int_cs: Coeficiente convectivo canal superior [W/m²·K].
        h_int_ci: Coeficiente convectivo canal inferior (estanco) [W/m²·K].
        h_viento: Coeficiente convectivo de viento [W/m²·K].
        Re_cs: Reynolds canal superior.
        regimen_cs: Régimen de flujo canal superior.
        advertencias: Lista de advertencias.
        convergencia_ok: True si solve_ivp convergió.
        mensaje_convergencia: Estado de convergencia.
    """

    x_m: np.ndarray
    T_f_cs_K: np.ndarray
    T_f_ci_K: np.ndarray
    T_abs_K: np.ndarray
    T_cub_i_K: np.ndarray
    T_cub_e_K: np.ndarray
    T_int_K: np.ndarray
    T_bot_K: np.ndarray
    T_entrada_K: float
    T_salida_K: float
    Q_util_W: float
    Q_incidente_W: float
    eta_termica: float
    h_int_cs: float
    h_int_ci: float
    h_viento: float
    Re_cs: float
    regimen_cs: str
    advertencias: list[str] = field(default_factory=list)
    convergencia_ok: bool = True
    mensaje_convergencia: str = "OK"


# =============================================================================
# Funciones auxiliares compartidas
# =============================================================================


def _T_cielo_K(T_amb_K: float) -> float:
    """Temperatura de cielo — Swinbank (1963). T_amb_K en K, retorna K."""
    return 0.0552 * T_amb_K**1.5


def _h_viento_W_m2K(v_viento_ms: float) -> tuple[float, list[str]]:
    """h_wind por McAdams (1954). Retorna (h [W/m²K], advertencias).

    ``v_viento_ms`` viene referido a 2 m y **no se corrige a la altura del
    colector**, a propósito: ver ADR-006 y el docstring de
    :func:`calculos.colector_calc._h_viento_W_m2K` para el fundamento.
    """
    advertencias: list[str] = []
    if v_viento_ms >= V_VIENTO_LIMITE_MCADAMS:
        advertencias.append(
            f"COL_VIENTO_FUERA_RANGO_MCADAMS: v_viento={v_viento_ms:.1f} m/s ≥ 5 m/s. "
            "Correlación de McAdams aplicada fuera de su rango de validez."
        )
    return 5.7 + 3.8 * v_viento_ms, advertencias


def _diametro_hidraulico_m(alto_canal_m: float, ancho_m: float) -> float:
    """Dh de canal rectangular [m]. Dh = 2·alto·ancho / (alto + ancho)."""
    return 2.0 * alto_canal_m * ancho_m / (alto_canal_m + ancho_m)


def _em_efectiva_paralelas(em_a: float, em_b: float) -> float:
    """Emisividad efectiva entre superficies paralelas infinitas (F=1).
    1/em_eff = 1/em_a + 1/em_b - 1.
    """
    return 1.0 / (1.0 / em_a + 1.0 / em_b - 1.0)


def _T_bot_desde_T_int(
    T_int_K: float,
    T_amb_K: float,
    k_ais_W_mK: float,
    esp_ais_m: float,
    h_wind_W_m2K: float,
) -> float:
    """Temperatura cara externa del fondo desde T_int (despeje algebraico).

    Balance: conducción aislante = convección al ambiente.
        k_ais/esp_ais * (T_int - T_bot) = h_wind * (T_bot - T_amb)

    En Tipos 2, 3 y 4 el fondo tiene cara interna (T_int, hacia el canal
    inferior) y cara externa (T_bot, hacia el ambiente). A diferencia del
    Tipo 1 donde T_int = T_abs, aquí T_int es incógnita independiente.

    Args:
        T_int_K: Temperatura cara interna del fondo [K].
        T_amb_K: Temperatura ambiente [K].
        k_ais_W_mK: Conductividad del aislante [W/m·K].
        esp_ais_m: Espesor del aislante [m].
        h_wind_W_m2K: Coeficiente convectivo de viento [W/m²·K].

    Returns:
        T_bot [K].
    """
    U_ais = k_ais_W_mK / esp_ais_m
    return (U_ais * T_int_K + h_wind_W_m2K * T_amb_K) / (U_ais + h_wind_W_m2K)


def _Ra_canal_estanco(dT_K: float, L_m: float, T_film_K: float) -> float:
    """Número de Rayleigh para cavidad plana inclinada (canal estanco).

    Ra = g·β·ΔT·L³·Pr / ν²

    donde L es el alto del canal (separación entre las dos placas paralelas),
    β = 1/T_film (gas ideal), ν = μ/ρ a 323 K.

    Args:
        dT_K: Diferencia de temperatura entre pared caliente y fría [K].
        L_m: Alto del canal estanco [m].
        T_film_K: Temperatura de película ≈ (T_hot + T_cold)/2 [K].

    Returns:
        Número de Rayleigh [adim]. Mínimo 0.
    """
    beta = 1.0 / T_film_K
    return max(0.0, G_ACELERACION * beta * dT_K * L_m**3 * PR_AIRE / NU_AIRE**2)


def _Re_canal(
    m_punto_kgs: float,
    alto_canal_m: float,
    ancho_m: float,
) -> tuple[float, float]:
    """Reynolds y Dh para un canal rectangular con flujo másico dado.

    Args:
        m_punto_kgs: Flujo másico [kg/s].
        alto_canal_m: Altura del canal [m].
        ancho_m: Ancho del colector [m].

    Returns:
        Tupla (Re, Dh_m).
    """
    Dh = _diametro_hidraulico_m(alto_canal_m, ancho_m)
    A_sec = alto_canal_m * ancho_m
    v_media = m_punto_kgs / (RHO_AIRE_REF * A_sec)
    Re = RHO_AIRE_REF * v_media * Dh / MU_AIRE
    return Re, Dh


# =============================================================================
# Sistemas algebraicos — Tipo 2
# =============================================================================


def _sistema_nodo_tipo2(
    vars_: np.ndarray,
    T_f_cs_K: float,
    T_f_ci_K: float,
    T_amb_K: float,
    T_cie_K: float,
    I_g_W_m2: float,
    h_wind: float,
    h_int_cs: float,
    h_int_ci: float,
    k_cub: float,
    esp_cub: float,
    em_cub: float,
    k_ais: float,
    esp_ais: float,
    em_abs: float,
    em_fondo: float,
    tau_cub: float,
    alfa_abs: float,
    W_m: float,
    W_abs_m: float,
    n_cubiertas: int = 1,
    esp_cav_m: float = 0.025,
    pendiente_deg: float = 30.0,
    P_amb_Pa: float = 101325.0,
) -> np.ndarray:
    """Sistema de 4 ecuaciones algebraicas por nodo — Tipo 2.

    Incógnitas: vars_ = [T_cub_e, T_cub_i, T_abs, T_int].

    Balances:
    F1 — cubierta cara externa: conv viento + rad cielo = conducción interna.
    F2 — cubierta cara interna: conducción = conv cs + rad abs.
    F3 — absorbedor: rad solar + conv cs + conv ci = rad cub + rad fondo.
    F4 — cara interna fondo: rad abs→fondo = cond aislante + conv ci int→fluido.

    Nota sobre F3 — el absorbedor recibe calor de ambos lados:
    - Cara superior: rad solar (transmitida) + rad cubierta + conv canal superior.
    - Cara inferior: conv canal inferior + rad fondo interior.
    Sin conducción en el absorbedor → T igual en ambas caras.

    Args:
        vars_: [T_cub_e_K, T_cub_i_K, T_abs_K, T_int_K].
        T_f_cs_K: T fluido canal superior [K].
        T_f_ci_K: T fluido canal inferior [K].
        (resto: parámetros físicos y geométricos)

    Returns:
        Array de 4 residuos.
    """
    T_cub_e, T_cub_i, T_abs, T_int = vars_

    em_eff_cub_abs = _em_efectiva_paralelas(em_cub, em_abs)
    em_eff_abs_fondo = _em_efectiva_paralelas(em_abs, em_fondo)
    # Conductancia cubierta: simple (n=1) o serie cubierta-cavidad-cubierta (n=2).
    U_cub = _U_cubierta_efectiva(
        n_cubiertas=n_cubiertas,
        T_cub_e_K=T_cub_e,
        T_cub_i_K=T_cub_i,
        k_cub=k_cub,
        esp_cub_m=esp_cub,
        em_cub=em_cub,
        esp_cav_m=esp_cav_m,
        pendiente_deg=pendiente_deg,
        P_amb_Pa=P_amb_Pa,
    )
    T_bot = _T_bot_desde_T_int(T_int, T_amb_K, k_ais, esp_ais, h_wind)
    U_ais = k_ais / esp_ais

    # --- F1: balance cara externa cubierta ---
    # En operación normal T_cub_i > T_cub_e: la cara externa GANA por conducción
    # desde la interna y PIERDE por viento + cielo. Con cond_cub = U·(T_cub_e − T_cub_i)
    # negativo en op. normal, el aporte conductivo a T_cub_e es −cond_cub.
    # F1 = conv + rad + cond_cub = 0 (raíz física).
    conv_viento = h_wind * (T_cub_e - T_amb_K)
    rad_cielo = em_cub * SIGMA_SB * (T_cub_e**4 - T_cie_K**4)
    cond_cub = U_cub * (T_cub_e - T_cub_i)
    F1 = conv_viento + rad_cielo + cond_cub

    # --- F2: balance cara interna cubierta ---
    # Gana: radiación desde absorbedor (cuando T_abs > T_cub_i).
    # Pierde: conducción hacia la cara externa + convección al fluido del canal superior.
    conv_cs_cub = h_int_cs * (T_cub_i - T_f_cs_K)
    rad_cub_abs = em_eff_cub_abs * SIGMA_SB * (T_cub_i**4 - T_abs**4)
    F2 = cond_cub - conv_cs_cub - rad_cub_abs

    # --- F3: balance absorbedor ---
    # Gana: radiación solar transmitida + radiación neta desde cubierta
    #       (cuando T_cub_i > T_abs, lo que ocurre raramente; normalmente pierde).
    # Pierde: convección al canal superior + convección al canal inferior
    #         + radiación neta al fondo interior.
    # Escalado: conv y rad cubierta con W_m; solar, conv ci y rad fondo con W_abs_m.
    rad_solar = I_g_W_m2 * tau_cub * alfa_abs * W_abs_m
    conv_cs_abs = h_int_cs * (T_abs - T_f_cs_K) * W_abs_m  # pérdida → cs
    conv_ci_abs = h_int_ci * (T_abs - T_f_ci_K) * W_abs_m  # pérdida → ci
    rad_abs_fondo = em_eff_abs_fondo * SIGMA_SB * (T_abs**4 - T_int**4) * W_abs_m
    rad_cub_abs = em_eff_cub_abs * SIGMA_SB * (T_cub_i**4 - T_abs**4) * W_m
    # rad_cub_abs < 0 cuando T_cub_i < T_abs (el abs pierde calor por radiación a cubierta)
    F3 = rad_solar - conv_cs_abs - conv_ci_abs + rad_cub_abs - rad_abs_fondo

    # --- F4: balance cara interna fondo ---
    # Gana: radiación neta desde absorbedor (cuando T_abs > T_int).
    # Pierde/gana: convección con fluido del canal inferior (signo según T_int vs T_f_ci).
    # Pierde: conducción al exterior a través del aislante (T_int → T_bot → T_amb).
    # Nota: la EDO del fluido ci ya cobra h·(T_int−T_f_ci) como aporte al fluido,
    # así que el balance global cierra sólo si F4 incluye explícitamente conv_ci_int.
    cond_ais = U_ais * (T_int - T_bot)
    rad_abs_fondo_F4 = em_eff_abs_fondo * SIGMA_SB * (T_abs**4 - T_int**4) * W_abs_m
    conv_ci_int = h_int_ci * (T_int - T_f_ci_K) * W_abs_m
    F4 = rad_abs_fondo_F4 - cond_ais * W_abs_m - conv_ci_int

    return np.array([F1, F2, F3, F4])


# =============================================================================
# Sistemas algebraicos — Tipos 3 y 4 (comparten estructura 4×4)
# =============================================================================


def _sistema_nodo_tipos34(
    vars_: np.ndarray,
    T_f_activo_K: float,
    T_f_estanco_K: float,
    T_amb_K: float,
    T_cie_K: float,
    I_g_W_m2: float,
    h_wind: float,
    h_int_activo: float,
    h_int_estanco: float,
    k_cub: float,
    esp_cub: float,
    em_cub: float,
    k_ais: float,
    esp_ais: float,
    em_abs: float,
    em_fondo: float,
    tau_cub: float,
    alfa_abs: float,
    W_m: float,
    W_abs_m: float,
    canal_activo: str,
    n_cubiertas: int = 1,
    esp_cav_m: float = 0.025,
    pendiente_deg: float = 30.0,
    P_amb_Pa: float = 101325.0,
) -> np.ndarray:
    """Sistema de 4 ecuaciones algebraicas por nodo — Tipos 3 y 4.

    Incógnitas: vars_ = [T_cub_e, T_cub_i, T_abs, T_int].

    El canal estanco no tiene transporte de masa, por lo que T_f_estanco_K
    se obtiene analíticamente antes de llamar a esta función:
    - Tipo 3 (canal superior estanco): T_f_cs = (T_cub_i + T_abs) / 2
    - Tipo 4 (canal inferior estanco): T_f_ci = (T_abs + T_int) / 2

    Args:
        vars_: [T_cub_e, T_cub_i, T_abs, T_int].
        T_f_activo_K: T fluido en el canal con flujo másico [K].
        T_f_estanco_K: T fluido en el canal estanco (analítica) [K].
        canal_activo: ``"superior"`` (Tipo 4) o ``"inferior"`` (Tipo 3).
            Controla qué canal conecta a T_f_activo_K en los balances.

    Returns:
        Array de 4 residuos.
    """
    T_cub_e, T_cub_i, T_abs, T_int = vars_

    em_eff_cub_abs = _em_efectiva_paralelas(em_cub, em_abs)
    em_eff_abs_fondo = _em_efectiva_paralelas(em_abs, em_fondo)
    # Conductancia cubierta: simple (n=1) o serie cubierta-cavidad-cubierta (n=2).
    U_cub = _U_cubierta_efectiva(
        n_cubiertas=n_cubiertas,
        T_cub_e_K=T_cub_e,
        T_cub_i_K=T_cub_i,
        k_cub=k_cub,
        esp_cub_m=esp_cub,
        em_cub=em_cub,
        esp_cav_m=esp_cav_m,
        pendiente_deg=pendiente_deg,
        P_amb_Pa=P_amb_Pa,
    )
    U_ais = k_ais / esp_ais
    T_bot = _T_bot_desde_T_int(T_int, T_amb_K, k_ais, esp_ais, h_wind)

    # Asignar fluidos a canales según tipo
    if canal_activo == "superior":
        # Tipo 4: canal superior activo, canal inferior estanco
        T_f_cs = T_f_activo_K
        T_f_ci = T_f_estanco_K
        h_cs = h_int_activo
        h_ci = h_int_estanco
    else:
        # Tipo 3: canal inferior activo, canal superior estanco
        T_f_cs = T_f_estanco_K
        T_f_ci = T_f_activo_K
        h_cs = h_int_estanco
        h_ci = h_int_activo

    # --- F1: balance cara externa cubierta (idéntico a Tipo 2) ---
    # F1 = conv + rad + cond_cub = 0 (raíz física; ver nota en Tipo 2).
    conv_viento = h_wind * (T_cub_e - T_amb_K)
    rad_cielo = em_cub * SIGMA_SB * (T_cub_e**4 - T_cie_K**4)
    cond_cub = U_cub * (T_cub_e - T_cub_i)
    F1 = conv_viento + rad_cielo + cond_cub

    # --- F2: balance cara interna cubierta ---
    conv_cs_cub = h_cs * (T_cub_i - T_f_cs)
    rad_cub_abs = em_eff_cub_abs * SIGMA_SB * (T_cub_i**4 - T_abs**4)
    F2 = cond_cub - conv_cs_cub - rad_cub_abs

    # --- F3: balance absorbedor ---
    rad_solar = I_g_W_m2 * tau_cub * alfa_abs * W_abs_m
    conv_cs_abs = h_cs * (T_abs - T_f_cs) * W_abs_m  # pérdida → cs
    conv_ci_abs = h_ci * (T_abs - T_f_ci) * W_abs_m  # pérdida → ci
    rad_abs_fondo = em_eff_abs_fondo * SIGMA_SB * (T_abs**4 - T_int**4) * W_abs_m
    rad_cub_abs = em_eff_cub_abs * SIGMA_SB * (T_cub_i**4 - T_abs**4) * W_m
    F3 = rad_solar - conv_cs_abs - conv_ci_abs + rad_cub_abs - rad_abs_fondo

    # --- F4: balance cara interna fondo ---
    # Para Tipo 3 (canal ci activo): T_f_ci tiene perfil propio, conv_ci_int es real.
    # Para Tipo 4 (canal ci estanco): T_f_ci = (T_abs+T_int)/2 → conv_ci_int = −conv_ci_abs,
    # capturando el aporte convectivo mediado por el fluido estanco al fondo.
    rad_abs_fondo_F4 = em_eff_abs_fondo * SIGMA_SB * (T_abs**4 - T_int**4) * W_abs_m
    cond_ais = U_ais * (T_int - T_bot) * W_abs_m
    conv_ci_int = h_ci * (T_int - T_f_ci) * W_abs_m
    F4 = rad_abs_fondo_F4 - cond_ais - conv_ci_int

    return np.array([F1, F2, F3, F4])


# =============================================================================
# Constructores de RHS para solve_ivp
# =============================================================================


def _h_local_canal(params: dict, canal: str, T_f_K: float, T_pared_K: float, x_m: float) -> float:
    """h convectivo LOCAL del canal activo ``canal`` ('cs' o 'ci') en x.

    Toma la geometría y el flujo másico del canal desde ``params`` y delega en
    ``coef_conveccion_interna_local`` (propiedades a T_f(x), Re y Nu(x) locales,
    flotación con la T_abs del warm-start).
    """
    h, _ = coef_conveccion_interna_local(
        T_f_K=T_f_K,
        T_pared_K=T_pared_K,
        Dh_m=params[f"Dh_{canal}"],
        x_m=x_m,
        A_seccion_m2=params[f"A_{canal}_m2"],
        m_punto_kgs=params[f"m_punto_{canal}_kgs"],
        pared=params[f"pared_{canal}"],
        pendiente_deg=params.get("pendiente_deg", 30.0),
        P_amb_Pa=params.get("P_amb_Pa", 101325.0),
    )
    return h


def _construir_rhs_tipo2(params: dict) -> tuple:
    """RHS para solve_ivp Tipo 2: integra [T_f_cs, T_f_ci] simultáneamente.

    En cada x resuelve el sistema 4×4 con fsolve para obtener
    [T_cub_e, T_cub_i, T_abs, T_int] y luego evalúa las dos derivadas.

    Args:
        params: Diccionario con todos los parámetros físicos y geométricos.

    Returns:
        Tupla (rhs_fn, log_no_convergencia).
    """
    estado = {"guess": None}
    log_nc = []

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        T_f_cs, T_f_ci = float(y[0]), float(y[1])

        if estado["guess"] is None:
            T_amb = params["T_amb_K"]
            # El absorbedor debe partir por encima del fluido y el ambiente
            T_f_max = max(T_f_cs, T_f_ci, T_amb)
            T_g_abs = T_f_max + 20.0
            T_g_cub = T_amb + 5.0
            estado["guess"] = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])

        # Coeficientes LOCALES de ambos canales activos (pared caliente = absorbedor
        # del warm-start).
        T_abs_ws = float(estado["guess"][2])
        h_cs = _h_local_canal(params, "cs", T_f_cs, T_abs_ws, x)
        h_ci = _h_local_canal(params, "ci", T_f_ci, T_abs_ws, x)

        sol, _, ier, msg = fsolve(
            _sistema_nodo_tipo2,
            estado["guess"],
            args=(
                T_f_cs,
                T_f_ci,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                h_cs,
                h_ci,
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["em_fondo"],
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
            log_nc.append((x, msg))
        estado["guess"] = sol.copy()

        T_cub_i, T_abs = sol[1], sol[2]
        W_m = params["W_m"]
        W_abs_m = params["W_abs_m"]
        m_cs = params["m_punto_cs_kgs"]
        m_ci = params["m_punto_ci_kgs"]

        # dT_f_cs/dx: calor desde cubierta (W_m) y absorbedor (W_abs_m)
        dTcs_dx = (h_cs * (T_cub_i - T_f_cs) * W_m + h_cs * (T_abs - T_f_cs) * W_abs_m) / (
            m_cs * cp_aire(T_f_cs)
        )

        # dT_f_ci/dx: calor desde absorbedor y cara interna fondo (ambos W_abs_m)
        T_int = sol[3]
        dTci_dx = (h_ci * (T_abs - T_f_ci) * W_abs_m + h_ci * (T_int - T_f_ci) * W_abs_m) / (
            m_ci * cp_aire(T_f_ci)
        )

        return np.array([dTcs_dx, dTci_dx])

    return rhs, log_nc


def _construir_rhs_tipo3(params: dict) -> tuple:
    """RHS para solve_ivp Tipo 3: integra T_f_ci (canal inferior activo).

    T_f_cs (canal superior estanco) se despeja analíticamente en cada nodo:
        T_f_cs = (T_cub_i + T_abs) / 2
    (válido cuando h_int_cs es igual en ambas paredes del canal estanco).

    Args:
        params: Diccionario con parámetros físicos y geométricos.

    Returns:
        Tupla (rhs_fn, log_no_convergencia).
    """
    estado = {"guess": None}
    log_nc = []

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        T_f_ci = float(y[0])

        if estado["guess"] is None:
            T_amb = params["T_amb_K"]
            T_f_max = max(T_f_ci, T_amb)
            T_g_abs = T_f_max + 20.0
            T_g_cub = T_amb + 5.0
            estado["guess"] = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])

        # T_f_cs y h_int_cs del canal superior estanco se obtienen del warm-start
        # del nodo anterior (misma estrategia que T_f_cs analítico ya existente).
        T_cub_i_guess = estado["guess"][1]
        T_abs_guess = estado["guess"][2]
        T_f_cs = 0.5 * (T_cub_i_guess + T_abs_guess)

        # h_int_cs: convección natural en canal estanco superior.
        # Pared inferior = absorbedor (caliente), pared superior = cubierta (fría)
        # → configuración inestable → Hollands et al. (1976).
        dT_cs = max(T_abs_guess - T_cub_i_guess, 0.1)
        T_film_cs = 0.5 * (T_abs_guess + T_cub_i_guess)
        Ra_cs = _Ra_canal_estanco(dT_cs, params["alto_cs_m"], T_film_cs)
        h_int_cs = (
            nusselt_hollands_inclinada(Ra_cs, params["theta_deg"]) * K_AIRE / params["alto_cs_m"]
        )

        # Canal inferior activo: coeficiente LOCAL (pared caliente = absorbedor).
        h_ci_local = _h_local_canal(params, "ci", T_f_ci, float(T_abs_guess), x)

        sol, _, ier, msg = fsolve(
            _sistema_nodo_tipos34,
            estado["guess"],
            args=(
                T_f_ci,
                T_f_cs,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                h_ci_local,
                h_int_cs,
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["em_fondo"],
                params["tau_cub"],
                params["alfa_abs"],
                params["W_m"],
                params["W_abs_m"],
                "inferior",  # canal activo = inferior
                params.get("n_cubiertas", 1),
                params.get("esp_cav_m", 0.025),
                params.get("pendiente_deg", 30.0),
                params.get("P_amb_Pa", 101325.0),
            ),
            full_output=True,
            xtol=TOL_FSOLVE,
        )
        if ier != 1:
            log_nc.append((x, msg))
        estado["guess"] = sol.copy()

        _, T_abs, T_int = sol[1], sol[2], sol[3]

        W_abs_m = params["W_abs_m"]
        m_ci = params["m_punto_ci_kgs"]

        dTci_dx = (
            h_ci_local * (T_abs - T_f_ci) * W_abs_m + h_ci_local * (T_int - T_f_ci) * W_abs_m
        ) / (m_ci * cp_aire(T_f_ci))

        return np.array([dTci_dx])

    return rhs, log_nc


def _construir_rhs_tipo4(params: dict) -> tuple:
    """RHS para solve_ivp Tipo 4: integra T_f_cs (canal superior activo).

    T_f_ci (canal inferior estanco) se despeja analíticamente:
        T_f_ci = (T_abs + T_int) / 2

    Args:
        params: Diccionario con parámetros físicos y geométricos.

    Returns:
        Tupla (rhs_fn, log_no_convergencia).
    """
    estado = {"guess": None}
    log_nc = []

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        T_f_cs = float(y[0])

        if estado["guess"] is None:
            T_amb = params["T_amb_K"]
            T_f_max = max(T_f_cs, T_amb)
            T_g_abs = T_f_max + 20.0
            T_g_cub = T_amb + 5.0
            estado["guess"] = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])

        T_abs_guess = estado["guess"][2]
        T_int_guess = estado["guess"][3]
        T_f_ci = 0.5 * (T_abs_guess + T_int_guess)

        # Canal superior activo: coeficiente LOCAL (pared caliente = absorbedor).
        h_cs_local = _h_local_canal(params, "cs", T_f_cs, float(T_abs_guess), x)

        sol, _, ier, msg = fsolve(
            _sistema_nodo_tipos34,
            estado["guess"],
            args=(
                T_f_cs,
                T_f_ci,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                h_cs_local,
                params["h_int_ci"],
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["em_fondo"],
                params["tau_cub"],
                params["alfa_abs"],
                params["W_m"],
                params["W_abs_m"],
                "superior",  # canal activo = superior
                params.get("n_cubiertas", 1),
                params.get("esp_cav_m", 0.025),
                params.get("pendiente_deg", 30.0),
                params.get("P_amb_Pa", 101325.0),
            ),
            full_output=True,
            xtol=TOL_FSOLVE,
        )
        if ier != 1:
            log_nc.append((x, msg))
        estado["guess"] = sol.copy()

        T_cub_i, T_abs, _ = sol[1], sol[2], sol[3]

        W_m = params["W_m"]
        W_abs_m = params["W_abs_m"]
        m_cs = params["m_punto_cs_kgs"]

        dTcs_dx = (
            h_cs_local * (T_cub_i - T_f_cs) * W_m + h_cs_local * (T_abs - T_f_cs) * W_abs_m
        ) / (m_cs * cp_aire(T_f_cs))

        return np.array([dTcs_dx])

    return rhs, log_nc


# =============================================================================
# Reconstrucción de perfiles de superficie
# =============================================================================


def _reconstruir_perfiles_tipo2(
    x_arr: np.ndarray,
    T_f_cs_arr: np.ndarray,
    T_f_ci_arr: np.ndarray,
    params: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruye T_cub_e, T_cub_i, T_abs, T_int, T_bot post solve_ivp."""
    n = len(x_arr)
    T_cub_e = np.empty(n)
    T_cub_i = np.empty(n)
    T_abs = np.empty(n)
    T_int = np.empty(n)
    T_bot = np.empty(n)
    guess = None

    for i in range(n):
        if guess is None:
            T_amb = params["T_amb_K"]
            T_f_max = max(T_f_cs_arr[0], T_f_ci_arr[0], T_amb)
            T_g_abs = T_f_max + 20.0
            T_g_cub = T_amb + 5.0
            guess = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])
        T_abs_ws = float(guess[2])
        h_cs_loc = _h_local_canal(params, "cs", float(T_f_cs_arr[i]), T_abs_ws, float(x_arr[i]))
        h_ci_loc = _h_local_canal(params, "ci", float(T_f_ci_arr[i]), T_abs_ws, float(x_arr[i]))
        sol = fsolve(
            _sistema_nodo_tipo2,
            guess,
            args=(
                T_f_cs_arr[i],
                T_f_ci_arr[i],
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                h_cs_loc,
                h_ci_loc,
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["em_fondo"],
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
        T_cub_e[i] = sol[0]
        T_cub_i[i] = sol[1]
        T_abs[i] = sol[2]
        T_int[i] = sol[3]
        T_bot[i] = _T_bot_desde_T_int(
            sol[3], params["T_amb_K"], params["k_ais"], params["esp_ais_m"], params["h_wind"]
        )
        guess = sol.copy()

    return T_cub_e, T_cub_i, T_abs, T_int, T_bot


def _reconstruir_perfiles_tipos34(
    x_arr: np.ndarray,
    T_f_activo_arr: np.ndarray,
    params: dict,
    canal_activo: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruye perfiles de superficie para Tipos 3 y 4.

    Retorna: T_cub_e, T_cub_i, T_abs, T_int, T_bot, T_f_estanco.
    """
    n = len(x_arr)
    T_cub_e = np.empty(n)
    T_cub_i = np.empty(n)
    T_abs = np.empty(n)
    T_int = np.empty(n)
    T_bot = np.empty(n)
    T_f_estanco = np.empty(n)
    guess = None

    for i in range(n):
        if guess is None:
            T_amb = params["T_amb_K"]
            T_f_max = max(T_f_activo_arr[0], T_amb)
            T_g_abs = T_f_max + 20.0
            T_g_cub = T_amb + 5.0
            guess = np.array([T_g_cub, T_g_cub + 5.0, T_g_abs, T_g_cub + 5.0])

        # T_f_estanco y h_int_estanco desde el warm-start del nodo anterior.
        # El canal ACTIVO usa coeficiente local; el estanco mantiene su tratamiento.
        T_abs_ws = float(guess[2])
        if canal_activo == "inferior":
            # Tipo 3: canal superior estanco, absorbedor (caliente) abajo → Hollands
            T_f_est = 0.5 * (guess[1] + guess[2])  # (T_cub_i + T_abs)/2
            dT_est = max(guess[2] - guess[1], 0.1)
            T_film_est = 0.5 * (guess[2] + guess[1])
            Ra_est = _Ra_canal_estanco(dT_est, params["alto_cs_m"], T_film_est)
            h_int_estanco = (
                nusselt_hollands_inclinada(Ra_est, params["theta_deg"])
                * K_AIRE
                / params["alto_cs_m"]
            )
            h_int_activo = _h_local_canal(
                params, "ci", float(T_f_activo_arr[i]), T_abs_ws, float(x_arr[i])
            )
        else:
            # Tipo 4: canal inferior estanco, absorbedor (caliente) arriba → Nu=1
            T_f_est = 0.5 * (guess[2] + guess[3])  # (T_abs + T_int)/2
            h_int_estanco = params["h_int_ci"]  # K_AIRE / alto_ci_m, precomputado
            h_int_activo = _h_local_canal(
                params, "cs", float(T_f_activo_arr[i]), T_abs_ws, float(x_arr[i])
            )

        sol = fsolve(
            _sistema_nodo_tipos34,
            guess,
            args=(
                T_f_activo_arr[i],
                T_f_est,
                params["T_amb_K"],
                params["T_cie_K"],
                params["I_g_W_m2"],
                params["h_wind"],
                h_int_activo,
                h_int_estanco,
                params["k_cub"],
                params["esp_cub_m"],
                params["em_cub"],
                params["k_ais"],
                params["esp_ais_m"],
                params["em_abs"],
                params["em_fondo"],
                params["tau_cub"],
                params["alfa_abs"],
                params["W_m"],
                params["W_abs_m"],
                canal_activo,
                params.get("n_cubiertas", 1),
                params.get("esp_cav_m", 0.025),
                params.get("pendiente_deg", 30.0),
                params.get("P_amb_Pa", 101325.0),
            ),
            xtol=TOL_FSOLVE,
        )
        T_cub_e[i] = sol[0]
        T_cub_i[i] = sol[1]
        T_abs[i] = sol[2]
        T_int[i] = sol[3]
        T_bot[i] = _T_bot_desde_T_int(
            sol[3], params["T_amb_K"], params["k_ais"], params["esp_ais_m"], params["h_wind"]
        )
        # T_f_estanco con solución convergida
        if canal_activo == "inferior":
            T_f_estanco[i] = 0.5 * (sol[1] + sol[2])
        else:
            T_f_estanco[i] = 0.5 * (sol[2] + sol[3])
        guess = sol.copy()

    return T_cub_e, T_cub_i, T_abs, T_int, T_bot, T_f_estanco


# =============================================================================
# Extracción de parámetros del objeto Colector
# =============================================================================


def _extraer_params_materiales(colector: "Colector") -> dict:
    """Extrae propiedades ópticas y térmicas del catálogo de materiales.

    Args:
        colector: Instancia de Colector del core.

    Returns:
        Diccionario con tau_cub, em_cub, k_cub, alfa_abs, em_abs,
        k_ais, em_fondo y espesores.
    """
    from core.catalogo import AISLANTES, CUBIERTAS, FONDOS, PLACAS

    unidad = colector.unidad
    mat_cub = CUBIERTAS[unidad.id_cubierta]
    mat_placa = PLACAS[unidad.id_placa]
    mat_ais = AISLANTES[unidad.id_aislante]
    mat_fondo = FONDOS[unidad.id_fondo]

    return {
        "tau_cub": mat_cub["transmitancia_solar"],
        "em_cub": mat_cub["emisividad_ir"],
        # k efectivo: override del usuario (policarbonato alveolar → k(espesor))
        # o, en su defecto, el del catálogo.
        "k_cub": unidad.k_cubierta_efectivo_W_mK or mat_cub["conductividad_termica"],
        "esp_cub_m": unidad.espesor_cubierta_m,
        "alfa_abs": mat_placa["absortancia_solar"],
        "em_abs": mat_placa["emisividad_ir"],
        "k_ais": mat_ais["conductividad_termica"],
        "esp_ais_m": unidad.espesor_aislante_m,
        "em_fondo": mat_fondo["emisividad_ir"],
    }


def _solve_y_verificar(
    rhs_fn,
    L_total_m: float,
    y0: list[float],
    log_nc: list,
    advertencias: list[str],
) -> object:
    """Corre solve_ivp y verifica convergencia. Lanza RuntimeError si falla."""
    resultado = solve_ivp(
        fun=rhs_fn,
        t_span=(0.0, L_total_m),
        y0=y0,
        method="RK45",
        max_step=L_total_m / N_NODOS_MIN,
        dense_output=False,
        rtol=1e-6,
        atol=1e-6,
    )
    if not resultado.success:
        raise RuntimeError(f"solve_ivp no convergió: {resultado.message}")
    if log_nc:
        advertencias.append(
            f"COL_FSOLVE_NO_CONVERGE: fsolve no convergió en {len(log_nc)} "
            f"de {len(resultado.t)} nodos. Resultados pueden ser imprecisos."
        )
    return resultado


# =============================================================================
# Funciones principales — una por tipo
# =============================================================================


def calcular_colector_tipo2(
    colector: "Colector",
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    P_amb_Pa: float,
    T_entrada_K: float,
    v_diseno_cs_ms: float,
    v_diseno_ci_ms: float,
    alto_cs_m: float | None = None,
    alto_ci_m: float | None = None,
    correlacion_nusselt_cs: str | None = None,
    correlacion_nusselt_ci: str | None = None,
    pendiente_deg: float = 30.0,
) -> ResultadosColectorTipo2:
    """Calcula el comportamiento térmico del colector solar Tipo 2.

    Flujo activo en ambos canales. Las velocidades de diseño de cada canal
    se especifican independientemente (§15.3). Las alturas de cada canal
    también pueden especificarse independientemente (§15.11); por defecto
    ambas toman ``unidad.espaciado_m`` (canales simétricos).

    Args:
        colector: Instancia de Colector del core.
        T_amb_K: Temperatura ambiente [K].
        I_g_W_m2: Irradiancia global sobre plano del colector [W/m²].
        v_viento_ms: Velocidad del viento a 2 m [m/s].
        P_amb_Pa: Presión atmosférica [Pa].
        T_entrada_K: Temperatura de entrada compartida por ambos canales [K].
        v_diseno_cs_ms: Velocidad de diseño canal superior [m/s].
        v_diseno_ci_ms: Velocidad de diseño canal inferior [m/s].
        alto_cs_m: Altura del canal superior [m]. Si es None, usa
            ``colector.unidad.espaciado_m`` (canales simétricos).
        alto_ci_m: Altura del canal inferior [m]. Si es None, usa
            ``colector.unidad.espaciado_m`` (canales simétricos).
        correlacion_nusselt_cs: Correlación Nusselt canal superior (None=auto).
        correlacion_nusselt_ci: Correlación Nusselt canal inferior (None=auto).

    Returns:
        ResultadosColectorTipo2.

    Raises:
        ValueError: Si I_g_W_m2 < 0, T_entrada_K ≤ 0, o alguna altura de canal
            es menor a ``ALTO_CANAL_MIN_M`` (5 mm).
        RuntimeError: Si solve_ivp no converge.
    """
    if I_g_W_m2 < 0.0:
        raise ValueError(f"I_g_W_m2 debe ser ≥ 0. Recibido: {I_g_W_m2}")
    if T_entrada_K <= 0.0:
        raise ValueError(f"T_entrada_K debe ser > 0 K. Recibido: {T_entrada_K}")

    advertencias: list[str] = []
    unidad = colector.unidad
    banco = colector.banco

    W_m = unidad.ancho_m
    L_total_m = unidad.largo_m * banco.n_serie
    W_abs_m = W_m  # absorbedor plano; extender para ondulado

    # Alturas de canales (§15.11).
    # Si no se especifican, ambos canales toman el espaciado del core (simétricos).
    # Si se especifican, permiten geometrías asimétricas — útil p.ej. para Tipo 3
    # con canal estanco superior pequeño que reduce convección natural y pérdidas.
    alto_cs_m = unidad.espaciado_m if alto_cs_m is None else alto_cs_m
    alto_ci_m = unidad.espaciado_m if alto_ci_m is None else alto_ci_m
    if alto_cs_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CS_MINIMO: alto_cs_m={alto_cs_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal superior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )
    if alto_ci_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CI_MINIMO: alto_ci_m={alto_ci_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal inferior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )

    # Flujos másicos por rama paralela en cada canal (densidad a la entrada).
    rho_ent = rho_aire(T_entrada_K, P_amb_Pa)
    m_cs_rama = rho_ent * v_diseno_cs_ms * W_m * alto_cs_m
    m_ci_rama = rho_ent * v_diseno_ci_ms * W_m * alto_ci_m
    m_cs_total = m_cs_rama * banco.n_paralelo
    m_ci_total = m_ci_rama * banco.n_paralelo

    # Correlaciones y coeficientes convectivos
    T_cie_K = _T_cielo_K(T_amb_K)
    h_wind, adv_v = _h_viento_W_m2K(v_viento_ms)
    advertencias.extend(adv_v)

    Re_cs, Dh_cs = _Re_canal(m_cs_rama, alto_cs_m, W_m)
    Re_ci, Dh_ci = _Re_canal(m_ci_rama, alto_ci_m, W_m)

    # Canal superior: cubierta fría + absorbedor caliente → una_pared
    h_int_cs, _, _, regimen_cs, adv_cs = calcular_h_int(
        Re=Re_cs,
        Pr=PR_AIRE,
        Dh_m=Dh_cs,
        L_m=L_total_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",
        modo="forzado",
        correlacion=correlacion_nusselt_cs,
    )
    # Canal inferior: absorbedor caliente (arriba) + fondo caliente (abajo) → dos_paredes
    h_int_ci, _, _, regimen_ci, adv_ci = calcular_h_int(
        Re=Re_ci,
        Pr=PR_AIRE,
        Dh_m=Dh_ci,
        L_m=L_total_m,
        k_fluido_W_mK=K_AIRE,
        pared="dos_paredes",
        modo="forzado",
        correlacion=correlacion_nusselt_ci,
    )
    advertencias.extend(adv_cs)
    advertencias.extend(adv_ci)

    mat = _extraer_params_materiales(colector)

    params = {
        "T_amb_K": T_amb_K,
        "T_cie_K": T_cie_K,
        "I_g_W_m2": I_g_W_m2,
        "h_wind": h_wind,
        "h_int_cs": h_int_cs,
        "h_int_ci": h_int_ci,
        "k_cub": mat["k_cub"],
        "esp_cub_m": mat["esp_cub_m"],
        "em_cub": mat["em_cub"],
        "k_ais": mat["k_ais"],
        "esp_ais_m": mat["esp_ais_m"],
        "em_abs": mat["em_abs"],
        "em_fondo": mat["em_fondo"],
        "tau_cub": mat["tau_cub"],
        "alfa_abs": mat["alfa_abs"],
        "W_m": W_m,
        "W_abs_m": W_abs_m,
        "m_punto_cs_kgs": m_cs_rama,
        "m_punto_ci_kgs": m_ci_rama,
        "Dh_cs": Dh_cs,
        "Dh_ci": Dh_ci,
        "A_cs_m2": W_m * alto_cs_m,
        "A_ci_m2": W_m * alto_ci_m,
        "pared_cs": "una_pared",
        "pared_ci": "dos_paredes",
        "n_cubiertas": colector.unidad.n_cubiertas,
        "esp_cav_m": colector.unidad.espaciado_entre_cubiertas_m,
        "pendiente_deg": pendiente_deg,
        "P_amb_Pa": P_amb_Pa,
    }

    rhs_fn, log_nc = _construir_rhs_tipo2(params)
    resultado_ivp = _solve_y_verificar(
        rhs_fn, L_total_m, [T_entrada_K, T_entrada_K], log_nc, advertencias
    )

    x_arr = resultado_ivp.t
    T_f_cs_arr = resultado_ivp.y[0]
    T_f_ci_arr = resultado_ivp.y[1]

    T_cub_e, T_cub_i, T_abs, T_int, T_bot = _reconstruir_perfiles_tipo2(
        x_arr, T_f_cs_arr, T_f_ci_arr, params
    )

    T_salida_cs = float(T_f_cs_arr[-1])
    T_salida_ci = float(T_f_ci_arr[-1])
    T_salida_mezcla = (m_cs_total * T_salida_cs + m_ci_total * T_salida_ci) / (
        m_cs_total + m_ci_total
    )

    Q_util_cs = (
        m_cs_total * cp_aire(0.5 * (T_entrada_K + T_salida_cs)) * (T_salida_cs - T_entrada_K)
    )
    Q_util_ci = (
        m_ci_total * cp_aire(0.5 * (T_entrada_K + T_salida_ci)) * (T_salida_ci - T_entrada_K)
    )
    Q_util_W = Q_util_cs + Q_util_ci
    Q_incidente_W = I_g_W_m2 * mat["tau_cub"] * W_m * L_total_m * banco.n_paralelo
    eta_termica = Q_util_W / Q_incidente_W if Q_incidente_W > 0.0 else 0.0

    return ResultadosColectorTipo2(
        x_m=x_arr,
        T_f_cs_K=T_f_cs_arr,
        T_f_ci_K=T_f_ci_arr,
        T_abs_K=T_abs,
        T_cub_i_K=T_cub_i,
        T_cub_e_K=T_cub_e,
        T_int_K=T_int,
        T_bot_K=T_bot,
        T_entrada_K=T_entrada_K,
        T_salida_cs_K=T_salida_cs,
        T_salida_ci_K=T_salida_ci,
        T_salida_mezcla_K=T_salida_mezcla,
        Q_util_W=Q_util_W,
        Q_incidente_W=Q_incidente_W,
        eta_termica=eta_termica,
        h_int_cs=h_int_cs,
        h_int_ci=h_int_ci,
        h_viento=h_wind,
        Re_cs=Re_cs,
        Re_ci=Re_ci,
        regimen_cs=regimen_cs,
        regimen_ci=regimen_ci,
        advertencias=advertencias,
        convergencia_ok=resultado_ivp.success,
        mensaje_convergencia="OK",
    )


def calcular_colector_tipo3(
    colector: "Colector",
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    P_amb_Pa: float,
    T_entrada_K: float,
    alto_cs_m: float | None = None,
    alto_ci_m: float | None = None,
    correlacion_nusselt: str | None = None,
    theta_deg: float = 45.0,
) -> ResultadosColectorTipo3:
    """Calcula el comportamiento térmico del colector solar Tipo 3.

    Flujo activo en canal inferior. Canal superior estanco.
    La velocidad de diseño se toma de colector.unidad.velocidad_diseno_ms
    (correspondiente al canal activo).

    Las alturas de cada canal pueden especificarse independientemente
    (§15.11). Caso de uso típico: ``alto_cs_m`` pequeño (canal superior
    estanco angosto) para inhibir convección natural y reducir pérdidas.

    El canal superior estanco usa la correlación de Hollands et al. (1976)
    para convección natural entre placas inclinadas (absorbedor caliente
    abajo, cubierta fría arriba). El coeficiente h_int_cs se recalcula
    en cada nodo usando el warm-start de temperaturas del nodo previo.

    Args:
        colector: Instancia de Colector del core.
        T_amb_K: Temperatura ambiente [K].
        I_g_W_m2: Irradiancia global sobre plano del colector [W/m²].
        v_viento_ms: Velocidad del viento a 2 m [m/s].
        P_amb_Pa: Presión atmosférica [Pa].
        T_entrada_K: Temperatura de entrada al canal inferior [K].
        alto_cs_m: Altura del canal superior (estanco) [m]. Si es None, usa
            ``colector.unidad.espaciado_m``.
        alto_ci_m: Altura del canal inferior (activo) [m]. Si es None, usa
            ``colector.unidad.espaciado_m``.
        correlacion_nusselt: Correlación Nusselt canal activo (None=auto).
        theta_deg: Inclinación del colector desde la horizontal [°].
            Usado por la correlación de Hollands en el canal estanco.
            Default 45°.

    Returns:
        ResultadosColectorTipo3.

    Raises:
        ValueError: Si I_g_W_m2 < 0, T_entrada_K ≤ 0, o alguna altura de canal
            es menor a ``ALTO_CANAL_MIN_M`` (5 mm).
    """
    if I_g_W_m2 < 0.0:
        raise ValueError(f"I_g_W_m2 debe ser ≥ 0. Recibido: {I_g_W_m2}")
    if T_entrada_K <= 0.0:
        raise ValueError(f"T_entrada_K debe ser > 0 K. Recibido: {T_entrada_K}")

    advertencias: list[str] = []
    unidad = colector.unidad
    banco = colector.banco

    W_m = unidad.ancho_m
    L_total_m = unidad.largo_m * banco.n_serie
    W_abs_m = W_m
    # Alturas de canales (§15.11). Default simétrico = unidad.espaciado_m.
    alto_cs_m = unidad.espaciado_m if alto_cs_m is None else alto_cs_m
    alto_ci_m = unidad.espaciado_m if alto_ci_m is None else alto_ci_m
    if alto_cs_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CS_MINIMO: alto_cs_m={alto_cs_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal superior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )
    if alto_ci_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CI_MINIMO: alto_ci_m={alto_ci_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal inferior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )

    v_diseno = unidad.velocidad_diseno_ms
    m_ci_rama = rho_aire(T_entrada_K, P_amb_Pa) * v_diseno * W_m * alto_ci_m
    m_ci_total = m_ci_rama * banco.n_paralelo

    T_cie_K = _T_cielo_K(T_amb_K)
    h_wind, adv_v = _h_viento_W_m2K(v_viento_ms)
    advertencias.extend(adv_v)

    Re_ci, Dh_ci = _Re_canal(m_ci_rama, alto_ci_m, W_m)
    # Canal inferior activo: absorbedor (arriba) caliente + fondo (abajo) caliente
    # El fondo también cede calor al fluido → dos_paredes
    h_int_ci, _, _, regimen_ci, adv_nu = calcular_h_int(
        Re=Re_ci,
        Pr=PR_AIRE,
        Dh_m=Dh_ci,
        L_m=L_total_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",
        modo="forzado",
        correlacion=correlacion_nusselt,
    )
    advertencias.extend(adv_nu)

    mat = _extraer_params_materiales(colector)

    params = {
        "T_amb_K": T_amb_K,
        "T_cie_K": T_cie_K,
        "I_g_W_m2": I_g_W_m2,
        "h_wind": h_wind,
        "h_int_ci": h_int_ci,
        "k_cub": mat["k_cub"],
        "esp_cub_m": mat["esp_cub_m"],
        "em_cub": mat["em_cub"],
        "k_ais": mat["k_ais"],
        "esp_ais_m": mat["esp_ais_m"],
        "em_abs": mat["em_abs"],
        "em_fondo": mat["em_fondo"],
        "tau_cub": mat["tau_cub"],
        "alfa_abs": mat["alfa_abs"],
        "W_m": W_m,
        "W_abs_m": W_abs_m,
        "m_punto_ci_kgs": m_ci_rama,
        "Dh_ci": Dh_ci,
        "A_ci_m2": W_m * alto_ci_m,
        "pared_ci": "una_pared",
        "alto_cs_m": alto_cs_m,
        "theta_deg": theta_deg,
        "n_cubiertas": colector.unidad.n_cubiertas,
        "esp_cav_m": colector.unidad.espaciado_entre_cubiertas_m,
        "pendiente_deg": theta_deg,
        "P_amb_Pa": P_amb_Pa,
    }

    rhs_fn, log_nc = _construir_rhs_tipo3(params)
    resultado_ivp = _solve_y_verificar(rhs_fn, L_total_m, [T_entrada_K], log_nc, advertencias)

    x_arr = resultado_ivp.t
    T_f_ci_arr = resultado_ivp.y[0]

    T_cub_e, T_cub_i, T_abs, T_int, T_bot, T_f_cs_arr = _reconstruir_perfiles_tipos34(
        x_arr, T_f_ci_arr, params, "inferior"
    )

    T_salida = float(T_f_ci_arr[-1])
    Q_util_W = m_ci_total * cp_aire(0.5 * (T_entrada_K + T_salida)) * (T_salida - T_entrada_K)
    Q_incidente_W = I_g_W_m2 * mat["tau_cub"] * W_m * L_total_m * banco.n_paralelo
    eta_termica = Q_util_W / Q_incidente_W if Q_incidente_W > 0.0 else 0.0

    # h_int_cs representativo para el reporte (promedio sobre el colector)
    dT_cs_rep = float(np.mean(np.maximum(T_abs - T_cub_i, 0.1)))
    T_film_rep = float(np.mean(0.5 * (T_abs + T_cub_i)))
    Ra_rep = _Ra_canal_estanco(dT_cs_rep, alto_cs_m, T_film_rep)
    h_int_cs = nusselt_hollands_inclinada(Ra_rep, theta_deg) * K_AIRE / alto_cs_m

    return ResultadosColectorTipo3(
        x_m=x_arr,
        T_f_ci_K=T_f_ci_arr,
        T_f_cs_K=T_f_cs_arr,
        T_abs_K=T_abs,
        T_cub_i_K=T_cub_i,
        T_cub_e_K=T_cub_e,
        T_int_K=T_int,
        T_bot_K=T_bot,
        T_entrada_K=T_entrada_K,
        T_salida_K=T_salida,
        Q_util_W=Q_util_W,
        Q_incidente_W=Q_incidente_W,
        eta_termica=eta_termica,
        h_int_ci=h_int_ci,
        h_int_cs=h_int_cs,
        h_viento=h_wind,
        Re_ci=Re_ci,
        regimen_ci=regimen_ci,
        advertencias=advertencias,
        convergencia_ok=resultado_ivp.success,
        mensaje_convergencia="OK",
    )


def calcular_colector_tipo4(
    colector: "Colector",
    T_amb_K: float,
    I_g_W_m2: float,
    v_viento_ms: float,
    P_amb_Pa: float,
    T_entrada_K: float,
    alto_cs_m: float | None = None,
    alto_ci_m: float | None = None,
    correlacion_nusselt: str | None = None,
    pendiente_deg: float = 30.0,
) -> ResultadosColectorTipo4:
    """Calcula el comportamiento térmico del colector solar Tipo 4.

    Flujo activo en canal superior. Canal inferior estanco.
    La velocidad de diseño se toma de colector.unidad.velocidad_diseno_ms.

    Las alturas de cada canal pueden especificarse independientemente
    (§15.11). Por defecto ambas toman ``unidad.espaciado_m``.

    Args:
        colector: Instancia de Colector del core.
        T_amb_K: Temperatura ambiente [K].
        I_g_W_m2: Irradiancia global sobre plano del colector [W/m²].
        v_viento_ms: Velocidad del viento a 2 m [m/s].
        P_amb_Pa: Presión atmosférica [Pa].
        T_entrada_K: Temperatura de entrada al canal superior [K].
        alto_cs_m: Altura del canal superior (activo) [m]. Si es None, usa
            ``colector.unidad.espaciado_m``.
        alto_ci_m: Altura del canal inferior (estanco) [m]. Si es None, usa
            ``colector.unidad.espaciado_m``.
        correlacion_nusselt: Correlación Nusselt canal activo (None=auto).

    Returns:
        ResultadosColectorTipo4.

    Raises:
        ValueError: Si I_g_W_m2 < 0, T_entrada_K ≤ 0, o alguna altura de canal
            es menor a ``ALTO_CANAL_MIN_M`` (5 mm).
    """
    if I_g_W_m2 < 0.0:
        raise ValueError(f"I_g_W_m2 debe ser ≥ 0. Recibido: {I_g_W_m2}")
    if T_entrada_K <= 0.0:
        raise ValueError(f"T_entrada_K debe ser > 0 K. Recibido: {T_entrada_K}")

    advertencias: list[str] = []
    unidad = colector.unidad
    banco = colector.banco

    W_m = unidad.ancho_m
    L_total_m = unidad.largo_m * banco.n_serie
    W_abs_m = W_m
    # Alturas de canales (§15.11). Default simétrico = unidad.espaciado_m.
    alto_cs_m = unidad.espaciado_m if alto_cs_m is None else alto_cs_m
    alto_ci_m = unidad.espaciado_m if alto_ci_m is None else alto_ci_m
    if alto_cs_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CS_MINIMO: alto_cs_m={alto_cs_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal superior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )
    if alto_ci_m < ALTO_CANAL_MIN_M:
        raise ValueError(
            f"GEO_ALTO_CI_MINIMO: alto_ci_m={alto_ci_m*1000:.2f} mm < "
            f"{ALTO_CANAL_MIN_M*1000:.0f} mm. El canal inferior es demasiado "
            "estrecho para el modelo de canal rectangular."
        )

    v_diseno = unidad.velocidad_diseno_ms
    m_cs_rama = rho_aire(T_entrada_K, P_amb_Pa) * v_diseno * W_m * alto_cs_m
    m_cs_total = m_cs_rama * banco.n_paralelo

    T_cie_K = _T_cielo_K(T_amb_K)
    h_wind, adv_v = _h_viento_W_m2K(v_viento_ms)
    advertencias.extend(adv_v)

    Re_cs, Dh_cs = _Re_canal(m_cs_rama, alto_cs_m, W_m)
    # Canal superior activo: cubierta (fría) + absorbedor (caliente) → una_pared
    h_int_cs, _, _, regimen_cs, adv_nu = calcular_h_int(
        Re=Re_cs,
        Pr=PR_AIRE,
        Dh_m=Dh_cs,
        L_m=L_total_m,
        k_fluido_W_mK=K_AIRE,
        pared="una_pared",
        modo="forzado",
        correlacion=correlacion_nusselt,
    )
    advertencias.extend(adv_nu)

    # Canal inferior estanco: absorbedor caliente arriba, fondo frío abajo.
    # Configuración estable (estratificación estable) → convección suprimida → Nu = 1.
    h_int_ci = K_AIRE / alto_ci_m

    mat = _extraer_params_materiales(colector)

    params = {
        "T_amb_K": T_amb_K,
        "T_cie_K": T_cie_K,
        "I_g_W_m2": I_g_W_m2,
        "h_wind": h_wind,
        "h_int_cs": h_int_cs,
        "h_int_ci": h_int_ci,
        "k_cub": mat["k_cub"],
        "esp_cub_m": mat["esp_cub_m"],
        "em_cub": mat["em_cub"],
        "k_ais": mat["k_ais"],
        "esp_ais_m": mat["esp_ais_m"],
        "em_abs": mat["em_abs"],
        "em_fondo": mat["em_fondo"],
        "tau_cub": mat["tau_cub"],
        "alfa_abs": mat["alfa_abs"],
        "W_m": W_m,
        "W_abs_m": W_abs_m,
        "m_punto_cs_kgs": m_cs_rama,
        "Dh_cs": Dh_cs,
        "A_cs_m2": W_m * alto_cs_m,
        "pared_cs": "una_pared",
        "n_cubiertas": colector.unidad.n_cubiertas,
        "esp_cav_m": colector.unidad.espaciado_entre_cubiertas_m,
        "pendiente_deg": pendiente_deg,
        "P_amb_Pa": P_amb_Pa,
    }

    rhs_fn, log_nc = _construir_rhs_tipo4(params)
    resultado_ivp = _solve_y_verificar(rhs_fn, L_total_m, [T_entrada_K], log_nc, advertencias)

    x_arr = resultado_ivp.t
    T_f_cs_arr = resultado_ivp.y[0]

    T_cub_e, T_cub_i, T_abs, T_int, T_bot, T_f_ci_arr = _reconstruir_perfiles_tipos34(
        x_arr, T_f_cs_arr, params, "superior"
    )

    T_salida = float(T_f_cs_arr[-1])
    Q_util_W = m_cs_total * cp_aire(0.5 * (T_entrada_K + T_salida)) * (T_salida - T_entrada_K)
    Q_incidente_W = I_g_W_m2 * mat["tau_cub"] * W_m * L_total_m * banco.n_paralelo
    eta_termica = Q_util_W / Q_incidente_W if Q_incidente_W > 0.0 else 0.0

    return ResultadosColectorTipo4(
        x_m=x_arr,
        T_f_cs_K=T_f_cs_arr,
        T_f_ci_K=T_f_ci_arr,
        T_abs_K=T_abs,
        T_cub_i_K=T_cub_i,
        T_cub_e_K=T_cub_e,
        T_int_K=T_int,
        T_bot_K=T_bot,
        T_entrada_K=T_entrada_K,
        T_salida_K=T_salida,
        Q_util_W=Q_util_W,
        Q_incidente_W=Q_incidente_W,
        eta_termica=eta_termica,
        h_int_cs=h_int_cs,
        h_int_ci=h_int_ci,
        h_viento=h_wind,
        Re_cs=Re_cs,
        regimen_cs=regimen_cs,
        advertencias=advertencias,
        convergencia_ok=resultado_ivp.success,
        mensaje_convergencia="OK",
    )
