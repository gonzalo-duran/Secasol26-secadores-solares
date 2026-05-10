"""Motor numérico de la cámara de secado solar — modelos de capa fina.

Implementa:
    - Isoterma GAB: X_eq = f(a_w, X_m, C, K)
    - Modelos cinéticos de capa fina: Lewis, Page, Henderson, Midilli, Logarítmico
    - Función principal: calcular_tiempo_secado()

Supuestos del modelo de prediseño:
    - Condiciones cuasi-estacionarias: T_aire y HR_aire constantes durante el secado.
    - a_w ≈ HR_operacion (gas ideal, aproximación válida para prediseño).
    - Modelo de capa fina: resistencia de transferencia de masa externa despreciable
      frente a la interna (Biot de masa >> 1), o bien los coeficientes k, n, etc.
      ya absorben el efecto del coeficiente externo.
    - Tiempo t en MINUTOS en los modelos (convención de los papers de referencia).

Modelos implementados (Razón de Humedad MR = (X - X_eq) / (X₀ - X_eq)):
    - lewis:       MR = exp(-k·t)                   params: {k}
    - page:        MR = exp(-k·t^n)                 params: {k, n}
    - henderson:   MR = a·exp(-k·t)                 params: {a, k}
    - midilli:     MR = a·exp(-k·t^n) + b·t         params: {a, k, n, b}
    - logaritmico: MR = a·exp(-k·t) + c             params: {a, k, c}

Referencias:
    - Mujumdar AS (2007). Handbook of Industrial Drying, 3ª ed. CRC Press.
    - Midilli A, Kucuk H, Yapar Z (2002). A new model for single-layer drying.
      Drying Technology 20(7):1503-1513.
    - Anderson RB (1946). J Am Chem Soc 68:686; Guggenheim EA (1966);
      De Boer JH (1953) — modelo GAB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

import numpy as np
from scipy.optimize import brentq

from calculos.camara_termodinamica import (
    ResultadoMotorTermodinamico,
    simular_secado,
)
from calculos.psicrometria import (
    actividad_agua_desde_X_GAB,
    densidad_aire_humedo,
    humedad_absoluta,
)
from core import catalogo

if TYPE_CHECKING:
    from core.camara import Camara

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

T_MAX_MIN: float = 72.0 * 60.0    # 72 h — límite superior de búsqueda [min]
N_PUNTOS_CURVA: int = 200          # puntos de la curva de secado
TOL_BRENTQ_MIN: float = 0.5       # tolerancia del solver [min] ≈ 30 s

_MODELOS_CF = frozenset({"lewis", "page", "henderson", "midilli", "logaritmico"})


# ---------------------------------------------------------------------------
# Dataclass de resultados
# ---------------------------------------------------------------------------


@dataclass
class ResultadosCamara:
    """Resultados del cálculo de la cámara de secado.

    Attributes:
        X_eq_kg_kg: Humedad de equilibrio calculada [kg agua / kg ms].
        t_secado_s: Tiempo total estimado para secar de X₀ a X_obj [s].
            Si convergencia_ok=False, es T_MAX (cota superior).
        t_array_s: Array de tiempos de la curva de secado [s].
        X_array_kg_kg: Contenido de humedad en cada punto de la curva [kg/kg ms].
        MR_obj: Razón de humedad objetivo = (X_obj - X_eq) / (X₀ - X_eq).
        fuente_X_eq: 'gab' si se usó isoterma GAB, 'fallback_escalar' si se usó
            el valor del catálogo.
        modelo_usado: Nombre del modelo de capa fina aplicado.
        masa_agua_extraida_kg: Masa de agua que debe evaporarse [kg].
        convergencia_ok: True si se encontró t_secado dentro de T_MAX.
        mensaje_convergencia: Descripción del estado del solver.
        advertencias: Lista de códigos/mensajes de advertencia del cálculo.
    """

    X_eq_kg_kg: float
    t_secado_s: float
    t_array_s: np.ndarray
    X_array_kg_kg: np.ndarray
    MR_obj: float
    fuente_X_eq: str
    modelo_usado: str
    masa_agua_extraida_kg: float
    convergencia_ok: bool = True
    mensaje_convergencia: str = "OK"
    advertencias: list[str] = field(default_factory=list)

    # Corrección psicrométrica (None si no se pudo calcular)
    omega_entrada_kg_kg: Optional[float] = None   # ω entrada [kg_agua/kg_aire_seco]
    omega_salida_kg_kg: Optional[float] = None    # ω salida (tras tomar agua del producto)
    HR_salida: Optional[float] = None             # HR del aire a la salida de la cámara
    HR_media: Optional[float] = None              # HR media usada para X_eq corregida
    X_eq_corregido_kg_kg: Optional[float] = None  # X_eq con HR_media (más preciso)
    t_secado_corregido_s: Optional[float] = None  # t_secado recalculado con X_eq corregida


# ---------------------------------------------------------------------------
# Isoterma GAB
# ---------------------------------------------------------------------------


def calcular_X_eq_gab(a_w: float, X_m: float, C: float, K: float) -> float:
    """Isoterma GAB (Guggenheim-Anderson-De Boer) para desorción.

    Forma: X_eq = X_m · C · K · a_w / [(1 - K·a_w) · (1 - K·a_w + C·K·a_w)]

    Válida para a_w ∈ (0, 1/K). Para secar, usar siempre la rama de desorción.

    Args:
        a_w: Actividad de agua del aire ≈ HR [adim].
        X_m: Contenido de humedad de monocapa [kg/kg ms].
        C: Constante de Guggenheim [adim].
        K: Constante de De Boer [adim].

    Returns:
        X_eq: Humedad de equilibrio [kg/kg ms].

    Raises:
        ValueError: Si los parámetros llevan a denominador no positivo
            (generalmente a_w ≥ 1/K).
    """
    Ka_w = K * a_w
    denom = (1.0 - Ka_w) * (1.0 - Ka_w + C * Ka_w)
    if denom <= 0.0:
        raise ValueError(
            f"GAB_DENOMINADOR_NO_POSITIVO: a_w={a_w:.4f}, K={K:.4f} → K·a_w={Ka_w:.4f}. "
            "El denominador GAB no es positivo. Verificar parámetros de la isoterma."
        )
    return X_m * C * Ka_w / denom


# ---------------------------------------------------------------------------
# Modelos de capa fina
# ---------------------------------------------------------------------------


def evaluar_MR(t_min: float, modelo: str, params: dict) -> float:
    """Evalúa la Razón de Humedad MR para el modelo cinético dado.

    MR = (X - X_eq) / (X₀ - X_eq). La física impone MR ∈ [0, 1] en secado.
    Los parámetros provienen directamente del catálogo YAML (top-level escalares).

    Args:
        t_min: Tiempo de secado [minutos].
        modelo: Nombre del modelo ('lewis', 'page', 'henderson', 'midilli', 'logaritmico').
        params: Diccionario con los parámetros del modelo.

    Returns:
        MR: Razón de humedad [adim]. Puede ser ligeramente < 0 o > 1 para modelos
            empíricos en sus límites — el código llamador debe recortarla con clip(0, 1).

    Raises:
        ValueError: Si el modelo no es reconocido.
    """
    if modelo == "lewis":
        return math.exp(-params["k"] * t_min)
    elif modelo == "page":
        return math.exp(-params["k"] * t_min ** params["n"])
    elif modelo == "henderson":
        return params["a"] * math.exp(-params["k"] * t_min)
    elif modelo == "midilli":
        return (
            params["a"] * math.exp(-params["k"] * t_min ** params["n"])
            + params["b"] * t_min
        )
    elif modelo == "logaritmico":
        return params["a"] * math.exp(-params["k"] * t_min) + params["c"]
    else:
        raise ValueError(
            f"MODELO_CF_DESCONOCIDO: '{modelo}' no reconocido. "
            f"Opciones: {sorted(_MODELOS_CF)}."
        )


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def calcular_tiempo_secado(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    P_Pa: float = 101325.0,
) -> ResultadosCamara:
    """Estima el tiempo de secado y genera la curva X(t) mediante el modelo de capa fina.

    Flujo de cálculo:
        1. Recupera los parámetros del catálogo (isoterma y capa fina).
        2. Calcula X_eq desde la isoterma GAB (o fallback escalar) con HR_entrada.
        3. Calcula MR_obj = (X_obj - X_eq) / (X₀ - X_eq).
        4. Resuelve MR_modelo(t) = MR_obj con brentq para hallar t_secado.
        5. Genera la curva X(t) sobre N_PUNTOS_CURVA puntos.
        6. [Corrección psicrométrica] Calcula ω_entrada, ω_salida y HR_salida
           a partir del balance de masa en la cámara.  Recalcula X_eq con la
           HR_media = (HR_entrada + HR_salida) / 2 y corrige t_secado si cambió
           significativamente.

    Args:
        camara: Objeto Camara completamente instanciado.
        T_operacion_K: Temperatura de operación en la cámara [K].
            Típicamente ≈ T_salida del colector.
        HR_operacion: Humedad relativa del aire en la entrada de la cámara
            [fracción 0–1]. Se usa como a_w ≈ HR para la isoterma GAB.
        P_Pa: Presión atmosférica [Pa]. Usada en las ecuaciones psicrométricas.
            Default: 101 325 Pa (nivel del mar).

    Returns:
        ResultadosCamara con el tiempo estimado, la curva de secado, el balance
        psicrométrico y advertencias.

    Raises:
        ValueError: Si T_operacion_K ≤ 0 o HR_operacion fuera de [0, 1].
    """
    if T_operacion_K <= 0:
        raise ValueError(f"T_operacion_K debe ser > 0 K. Recibido: {T_operacion_K}")
    if not (0.0 <= HR_operacion <= 1.0):
        raise ValueError(f"HR_operacion debe estar en [0, 1]. Recibido: {HR_operacion}")

    p = camara.carga_producto
    advertencias: list[str] = []

    # --- Recuperar datos del catálogo ---
    datos = catalogo.PRODUCTOS[p.producto_id]
    props = datos.get("propiedades_basicas") or {}
    X_eq_fallback = props.get("humedad_equilibrio_aire_seco")

    # --- Calcular X_eq ---
    iso = datos.get("isoterma") or {}
    iso_entry = iso.get(p.modelo_isoterma) or {}
    params_iso = iso_entry.get("params") or {} if iso_entry else {}
    X_m = params_iso.get("X_m")
    C_gab = params_iso.get("C")
    K_gab = params_iso.get("K")
    params_iso_validos = (
        X_m is not None and C_gab is not None and K_gab is not None
    )

    fuente_X_eq = "fallback_escalar"
    if params_iso_validos:
        try:
            X_eq = calcular_X_eq_gab(HR_operacion, float(X_m), float(C_gab), float(K_gab))
            fuente_X_eq = "gab"
        except ValueError as exc:
            X_eq = float(X_eq_fallback) if X_eq_fallback is not None else 0.0
            advertencias.append(
                f"CAM_GAB_FALLBACK: error en isoterma GAB ({exc}). "
                f"Usando fallback escalar X_eq={X_eq:.3f} kg/kg ms."
            )
    else:
        X_eq = float(X_eq_fallback) if X_eq_fallback is not None else 0.0
        if X_eq_fallback is None:
            advertencias.append(
                "CAM_X_EQ_CERO: sin isoterma ni fallback escalar. "
                "Se usa X_eq=0 como cota conservadora."
            )

    # --- Verificar rango de temperatura de calibración ---
    cf = datos.get("capa_fina") or {}
    modelo_entry = cf.get(p.modelo_capa_fina) or {}
    params_cf = modelo_entry.get("params") or {} if modelo_entry else {}
    condiciones = modelo_entry.get("condiciones_calibracion") or {} if modelo_entry else {}
    T_K_cal = condiciones.get("T_K")
    if T_K_cal:
        T_vals = T_K_cal if isinstance(T_K_cal, list) else [T_K_cal]
        T_min_cal = min(T_vals)
        T_max_cal = max(T_vals)
        margen_K = 10.0  # ±10 K de margen sobre el rango calibrado
        if not (T_min_cal - margen_K <= T_operacion_K <= T_max_cal + margen_K):
            advertencias.append(
                f"CAM_T_FUERA_RANGO_CALIBRACION: T_operacion={T_operacion_K - 273.15:.1f} °C "
                f"fuera del rango de calibración del modelo '{p.modelo_capa_fina}' "
                f"({T_min_cal - 273.15:.0f}–{T_max_cal - 273.15:.0f} °C, margen ±{margen_K:.0f} K). "
                "La extrapolación puede ser imprecisa."
            )

    # --- MR objetivo ---
    X_0 = p.humedad_inicial_X
    X_obj = p.humedad_objetivo_X

    rango_MR = X_0 - X_eq
    if rango_MR <= 0.0:
        # X₀ ≤ X_eq: el producto ya está en equilibrio o por debajo
        advertencias.append(
            f"CAM_PRODUCTO_EN_EQUILIBRIO: X₀={X_0:.3f} ≤ X_eq={X_eq:.3f}. "
            "El producto ya está en equilibrio con el aire. No hay secado."
        )
        MR_obj = 0.0
        t_secado_min = 0.0
        t_arr_min = np.linspace(0, 1, N_PUNTOS_CURVA)
        X_arr = np.full(N_PUNTOS_CURVA, X_0)
        masa_agua_extraida = 0.0
        return ResultadosCamara(
            X_eq_kg_kg=X_eq,
            t_secado_s=0.0,
            t_array_s=t_arr_min * 60.0,
            X_array_kg_kg=X_arr,
            MR_obj=0.0,
            fuente_X_eq=fuente_X_eq,
            modelo_usado=p.modelo_capa_fina,
            masa_agua_extraida_kg=0.0,
            convergencia_ok=True,
            mensaje_convergencia="Producto en equilibrio — sin secado.",
            advertencias=advertencias,
        )

    if X_obj <= X_eq:
        advertencias.append(
            f"CAM_HUMEDAD_OBJETIVO_INALCANZABLE: X_obj={X_obj:.3f} ≤ X_eq={X_eq:.3f}. "
            "El objetivo es termodinámicamente inalcanzable bajo estas condiciones. "
            "Se calcula el tiempo hasta X_eq como cota."
        )
        X_obj_efectivo = X_eq + 1e-4  # ε por encima del equilibrio
    else:
        X_obj_efectivo = X_obj

    MR_obj = (X_obj_efectivo - X_eq) / rango_MR

    # --- Resolver t_secado con brentq ---
    convergencia_ok = True
    mensaje_convergencia = "OK"

    def f_residuo(t_min: float) -> float:
        return evaluar_MR(t_min, p.modelo_capa_fina, params_cf) - MR_obj

    try:
        MR_en_0 = evaluar_MR(1e-9, p.modelo_capa_fina, params_cf)
        MR_en_max = evaluar_MR(T_MAX_MIN, p.modelo_capa_fina, params_cf)

        if MR_obj >= MR_en_0:
            # MR objetivo mayor que el MR inicial del modelo (≈ 1): producto ya seco
            t_secado_min = 0.0
            mensaje_convergencia = "X₀ ya es menor o igual al objetivo."
        elif MR_en_max > MR_obj:
            convergencia_ok = False
            t_secado_min = T_MAX_MIN
            mensaje_convergencia = (
                f"CAM_TIEMPO_EXCEDE_LIMITE: MR({T_MAX_MIN/60:.0f} h) = {MR_en_max:.4f} "
                f"> MR_obj = {MR_obj:.4f}. El secado requiere más de {T_MAX_MIN/60:.0f} h."
            )
            advertencias.append(mensaje_convergencia)
        else:
            t_secado_min = brentq(
                f_residuo,
                0.0,
                T_MAX_MIN,
                xtol=TOL_BRENTQ_MIN,
                full_output=False,
            )
    except Exception as exc:
        convergencia_ok = False
        t_secado_min = T_MAX_MIN
        mensaje_convergencia = f"CAM_BRENTQ_ERROR: {exc}"
        advertencias.append(mensaje_convergencia)

    t_secado_s = t_secado_min * 60.0

    # --- Curva de secado X(t) ---
    t_arr_min = np.linspace(0.0, max(t_secado_min, 1.0), N_PUNTOS_CURVA)
    MR_arr = np.array([evaluar_MR(t, p.modelo_capa_fina, params_cf) for t in t_arr_min])
    MR_arr = np.clip(MR_arr, 0.0, 1.0)
    X_arr = X_eq + MR_arr * rango_MR

    # --- Masa de agua extraída ---
    ms_kg = p.masa_total_kg / (1.0 + X_0)  # masa sólido seco [kg]
    masa_agua_extraida = ms_kg * (X_0 - X_obj_efectivo)

    # -----------------------------------------------------------------------
    # Corrección psicrométrica
    # Balance de masa: ω_sal = ω_ent + masa_agua / (m_dot_seco × t_secado)
    # Corrección de X_eq con HR_media = (HR_ent + HR_sal) / 2
    # -----------------------------------------------------------------------
    from calculos.psicrometria import (
        HR_desde_omega,
        balance_masa_camara,
        humedad_absoluta,
        omega_saturacion,
    )

    omega_in: Optional[float] = None
    omega_out: Optional[float] = None
    HR_sal: Optional[float] = None
    HR_med: Optional[float] = None
    X_eq_corr: Optional[float] = X_eq
    t_secado_corr_s: Optional[float] = t_secado_s

    m_dot_seco = camara.flujo.caudal_masico_kg_s

    if t_secado_s > 0.0 and m_dot_seco > 0.0:
        try:
            omega_in = humedad_absoluta(HR_operacion, T_operacion_K, P_Pa)
            omega_sat = omega_saturacion(T_operacion_K, P_Pa)

            omega_out_calc = balance_masa_camara(
                omega_in, masa_agua_extraida, m_dot_seco, t_secado_s
            )

            if omega_out_calc > omega_sat:
                advertencias.append(
                    f"CAM_RIESGO_SATURACION_AIRE: ω_salida calculada "
                    f"({omega_out_calc:.4f} kg/kg) > ω_saturación "
                    f"({omega_sat:.4f} kg/kg). El caudal de aire es insuficiente "
                    "para transportar toda el agua evaporada sin saturarse. "
                    "Aumentar el caudal o reducir la carga de producto."
                )
                omega_out = omega_sat
            else:
                omega_out = omega_out_calc

            HR_sal_calc = HR_desde_omega(omega_out, T_operacion_K, P_Pa)
            HR_sal = min(HR_sal_calc, 1.0)

            if HR_sal > 0.90:
                advertencias.append(
                    f"CAM_HR_SALIDA_ALTA: HR_salida = {HR_sal:.1%}. "
                    "El aire sale casi saturado — condiciones de secado deficientes. "
                    "Considerar aumentar el caudal de aire o reducir la carga."
                )

            HR_med = (HR_operacion + HR_sal) / 2.0

            # Corregir X_eq con HR_media si hay isoterma GAB disponible
            if params_iso_validos:
                try:
                    X_eq_corr = calcular_X_eq_gab(
                        HR_med, float(X_m), float(C_gab), float(K_gab)
                    )
                except ValueError:
                    X_eq_corr = X_eq  # fallback si GAB falla con HR_med

            # Recalcular t_secado si X_eq cambió más de 1 g/kg ms
            if (X_eq_corr is not None
                    and abs(X_eq_corr - X_eq) > 0.001
                    and X_obj_efectivo > X_eq_corr):
                rango_corr = X_0 - X_eq_corr
                if rango_corr > 0:
                    MR_obj_corr = (X_obj_efectivo - X_eq_corr) / rango_corr
                    MR_0_corr = evaluar_MR(1e-9, p.modelo_capa_fina, params_cf)
                    MR_max_corr = evaluar_MR(T_MAX_MIN, p.modelo_capa_fina, params_cf)
                    if MR_max_corr < MR_obj_corr < MR_0_corr:
                        try:
                            t_corr_min = brentq(
                                lambda t: evaluar_MR(t, p.modelo_capa_fina, params_cf)
                                          - MR_obj_corr,
                                0.0,
                                T_MAX_MIN,
                                xtol=TOL_BRENTQ_MIN,
                            )
                            t_secado_corr_s = t_corr_min * 60.0
                        except Exception:
                            pass  # mantener t original si brentq falla

        except Exception as exc:
            advertencias.append(
                f"CAM_PSICROMETRIA_ERROR: error en corrección psicrométrica: {exc}"
            )

    return ResultadosCamara(
        X_eq_kg_kg=X_eq,
        t_secado_s=t_secado_s,
        t_array_s=t_arr_min * 60.0,
        X_array_kg_kg=X_arr,
        MR_obj=MR_obj,
        fuente_X_eq=fuente_X_eq,
        modelo_usado=p.modelo_capa_fina,
        masa_agua_extraida_kg=masa_agua_extraida,
        convergencia_ok=convergencia_ok,
        mensaje_convergencia=mensaje_convergencia,
        advertencias=advertencias,
        omega_entrada_kg_kg=omega_in,
        omega_salida_kg_kg=omega_out,
        HR_salida=HR_sal,
        HR_media=HR_med,
        X_eq_corregido_kg_kg=X_eq_corr,
        t_secado_corregido_s=t_secado_corr_s,
    )


# ============================================================================
# S4a — Despachador de motores y wire-up con el motor termodinámico (S3)
# ============================================================================
#
# `calcular_camara` es el punto de entrada único desde la UI. Selecciona entre
# el motor de capa fina (existente) y el termodinámico (nuevo) según
# `camara.modo_calculo`.
#
# El wire-up con S3 calcula h_conv (correlación de placa plana), K_m
# (Chilton-Colburn directo), cp efectivo del producto a X media, áreas y
# boundary del aire, y delega en simular_secado.
# ============================================================================

# Propiedades del aire a T_película de referencia (~50 °C, 1 atm). Constantes
# para v0 — variación < 5 % en el rango operativo de secado solar.
_MU_AIRE_PA_S: float = 1.96e-5
_K_AIRE_W_MK: float = 0.028
_PR_AIRE: float = 0.71
_LE_AGUA_AIRE: float = 1.0          # número de Lewis para aire-agua
_CP_AGUA_LIQ_J_KGK: float = 4186.0  # cp del agua líquida (cp efectivo del producto)
_RE_CRITICO_PLACA: float = 5.0e5    # transición laminar→turbulento


def _h_conv_camara_placa_plana(
    v_aire_ms: float,
    L_caracteristico_m: float,
    T_pelicula_K: float,
    omega_pelicula: float,
    P_Pa: float,
) -> float:
    """Coeficiente convectivo aire→bandeja por correlación de placa plana.

    Re < 5e5: Nu = 0.664·Re^0.5·Pr^(1/3)   (laminar, Pohlhausen)
    Re > 5e5: Nu = 0.037·Re^0.8·Pr^(1/3)   (turbulento, McAdams)
    """
    rho = densidad_aire_humedo(T_pelicula_K, omega_pelicula, P_Pa)
    Re = rho * v_aire_ms * L_caracteristico_m / _MU_AIRE_PA_S
    if Re < _RE_CRITICO_PLACA:
        Nu = 0.664 * Re ** 0.5 * _PR_AIRE ** (1.0 / 3.0)
    else:
        Nu = 0.037 * Re ** 0.8 * _PR_AIRE ** (1.0 / 3.0)
    return Nu * _K_AIRE_W_MK / L_caracteristico_m


def _calcular_termodinamico(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float,
    P_Pa: float,
    t_max_s: float = 24.0 * 3600.0,
) -> ResultadoMotorTermodinamico:
    """Wire-up de Camara → motor termodinámico transitorio (S3).

    Lee del catálogo del producto:
        - propiedades_basicas.calor_especifico_seco → para cp efectivo (X media).
        - isoterma.gab.params → para construir aw_func. Si faltan, usa rampa
          lineal aw = clip(X/X_inicial, 0, 1) como fallback con advertencia.

    Calcula:
        - cp efectivo = (X_med·cp_w + cp_seco)/(1+X_med).
        - A_prod = n_bandejas · area_bandeja.
        - A_cuerpo = 2·(largo·alto + ancho·alto + largo·ancho).
        - v_aire = ṁ_as/(ρ·ancho·alto), h_conv por placa plana, K_m por
          Chilton-Colburn directo: K_m = h_conv/(cp_hum·Le^(2/3)).

    Si T_prod_inicial_K es None en CargaProducto, usa T_amb_K como fallback.
    """
    p = camara.carga_producto
    g = camara.geometria
    b = camara.bandejas
    f = camara.flujo
    cons = camara.construccion

    advertencias: list[str] = []

    # --- Datos del producto desde catálogo ---
    datos = catalogo.PRODUCTOS[p.producto_id]
    propsb = datos.get("propiedades_basicas") or {}
    cp_seco = propsb.get("calor_especifico_seco")
    if cp_seco is None:
        cp_seco = 1500.0
        advertencias.append(
            f"CAM_TD_CP_SECO_FALTA: producto '{p.producto_id}' sin "
            "calor_especifico_seco en catálogo. Usando default 1500 J/(kg·K)."
        )

    # cp efectivo del producto a X media (opción B — bitácora §24.x)
    X_med = 0.5 * (p.humedad_inicial_X + p.humedad_objetivo_X)
    cp_prod_efectivo = (X_med * _CP_AGUA_LIQ_J_KGK + cp_seco) / (1.0 + X_med)

    # Masa seca: m_total = m_seco·(1 + X_inicial) → m_seco = m_total/(1+X_in)
    m_seco_prod = p.masa_total_kg / (1.0 + p.humedad_inicial_X)

    # --- aw_func: GAB del catálogo, fallback rampa lineal ---
    iso = (datos.get("isoterma") or {}).get("gab") or {}
    iso_params = iso.get("params") or {}
    tiene_gab = (
        iso_params.get("X_m") is not None
        and iso_params.get("C") is not None
        and iso_params.get("K") is not None
    )
    if tiene_gab:
        X_m_GAB = float(iso_params["X_m"])
        C_GAB = float(iso_params["C"])
        K_GAB = float(iso_params["K"])

        def _aw_func(X: float) -> float:
            try:
                return actividad_agua_desde_X_GAB(X, X_m_GAB, C_GAB, K_GAB)
            except ValueError:
                # X fuera del rango GAB → asumir extremo plausible
                return 1.0 if X > X_m_GAB else 0.0
    else:
        advertencias.append(
            f"CAM_TD_GAB_FALTA: producto '{p.producto_id}' sin parámetros "
            "GAB calibrados. Usando aw = clip(X/X_inicial, 0, 1) como fallback."
        )
        X0 = p.humedad_inicial_X

        def _aw_func(X: float) -> float:
            return max(0.0, min(1.0, X / X0)) if X0 > 0 else 0.0

    # --- Geometría ---
    A_prod = b.n_bandejas * b.area_bandeja_m2
    A_cuerpo = 2.0 * (
        g.largo_m * g.alto_m
        + g.ancho_m * g.alto_m
        + g.largo_m * g.ancho_m
    )

    # --- Boundary del aire ---
    omega_ent = humedad_absoluta(HR_operacion, T_operacion_K, P_Pa)

    # --- T inicial del producto: explícito o T_amb ---
    T_prod_inicial = (
        p.T_prod_inicial_K if p.T_prod_inicial_K is not None else T_amb_K
    )

    # --- h_conv y K_m congelados (opción ii — bitácora §24.10) ---
    T_pelicula = 0.5 * (T_operacion_K + T_prod_inicial)
    rho_pelicula = densidad_aire_humedo(T_pelicula, omega_ent, P_Pa)
    area_transversal_m2 = g.ancho_m * g.alto_m
    v_aire = f.caudal_masico_kg_s / (rho_pelicula * area_transversal_m2)

    h_conv = _h_conv_camara_placa_plana(
        v_aire, g.largo_m, T_pelicula, omega_ent, P_Pa,
    )
    # Chilton-Colburn directo en conductancia másica: K_m = h/(cp_hum·Le^(2/3))
    cp_hum = 1006.0 + omega_ent * 1805.0
    K_m = h_conv / (cp_hum * _LE_AGUA_AIRE ** (2.0 / 3.0))

    # --- Integración termodinámica ---
    res = simular_secado(
        T_prod_inicial_K=T_prod_inicial,
        X_prod_inicial_kg_kg=p.humedad_inicial_X,
        X_prod_objetivo_kg_kg=p.humedad_objetivo_X,
        m_seco_prod_kg=m_seco_prod,
        cp_prod_J_kgK=cp_prod_efectivo,
        T_ent_K=T_operacion_K,
        omega_ent_kg_kg=omega_ent,
        A_prod_m2=A_prod,
        A_cuerpo_m2=A_cuerpo,
        m_dot_as_kg_s=f.caudal_masico_kg_s,
        h_conv_W_m2K=h_conv,
        K_m_kg_m2s=K_m,
        U_muros_W_m2K=cons.U_muros_W_m2K,
        T_amb_K=T_amb_K,
        P_Pa=P_Pa,
        aw_func=_aw_func,
        t_max_s=t_max_s,
    )

    # Anexar advertencias del wire-up a las del motor
    return ResultadoMotorTermodinamico(
        t_secado_s=res.t_secado_s,
        status=res.status,
        t_array_s=res.t_array_s,
        T_prod_K=res.T_prod_K,
        X_prod_kg_kg=res.X_prod_kg_kg,
        T_flujo_K=res.T_flujo_K,
        omega_flujo_kg_kg=res.omega_flujo_kg_kg,
        m_dot_w_kg_s=res.m_dot_w_kg_s,
        q_prod_W=res.q_prod_W,
        q_pared_W=res.q_pared_W,
        masa_evaporada_total_kg=res.masa_evaporada_total_kg,
        advertencias=advertencias + list(res.advertencias),
    )


def calcular_camara(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float = 298.15,
    P_Pa: float = 101325.0,
    t_max_s: float = 72.0 * 3600.0,
) -> Union[ResultadosCamara, ResultadoMotorTermodinamico]:
    """Punto de entrada único — despacha al motor según camara.modo_calculo.

    - modo='capa_fina'    → delega a calcular_tiempo_secado, retorna ResultadosCamara.
    - modo='termodinamico' → delega a _calcular_termodinamico, retorna
      ResultadoMotorTermodinamico con curvas dinámicas.

    Args:
        camara: Camara configurada.
        T_operacion_K: T del aire que entra a la cámara [K].
        HR_operacion: HR del aire que entra [fracción 0-1].
        T_amb_K: T ambiente externa [K]. Solo se usa en modo termodinámico
            (pérdidas a paredes y fallback de T_prod_inicial).
        P_Pa: Presión total [Pa].
        t_max_s: Cota superior del tiempo de secado [s]. Default 72 h
            (peores casos pueden llegar a 5 días). Solo usado en modo
            termodinámico. Default histórico de capa_fina sigue siendo 72 h
            en `T_MAX_MIN`.

    Returns:
        ResultadosCamara (capa_fina) o ResultadoMotorTermodinamico (termodinámico).

    Raises:
        ValueError: Si camara.modo_calculo no es válido (caso patológico —
            la dataclass ya valida esto en __post_init__).
    """
    if camara.modo_calculo == "capa_fina":
        return calcular_tiempo_secado(
            camara, T_operacion_K, HR_operacion, P_Pa=P_Pa
        )
    elif camara.modo_calculo == "termodinamico":
        return _calcular_termodinamico(
            camara, T_operacion_K, HR_operacion, T_amb_K, P_Pa,
            t_max_s=t_max_s,
        )
    else:
        raise ValueError(
            f"CAM_MODO_INVALIDO: modo_calculo='{camara.modo_calculo}' no soportado."
        )
