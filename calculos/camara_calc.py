"""Motor numérico de la cámara de secado solar — wire-up del motor termodinámico.

Desde S38 la cámara tiene un **único** motor físico: el balance acoplado
calor-masa (``calculos.camara_termodinamica.simular_secado``). Este módulo arma
los parámetros del motor a partir del objeto ``Camara`` (geometría, materiales,
flujo, producto) y expone el punto de entrada único ``calcular_camara``.

El antiguo motor de "capa fina" (correlaciones empíricas MR(t) de
Lewis/Page/Henderson-Pabis/Midilli/Logarítmico) fue eliminado: era un evaluador
de punto único a temperatura pico, insensible al espesor de lecho y a la
velocidad de aire reales, sin temperaturas ni flujos, y desacoplado de los
pipelines transitorio/multidía/anual. El motor termodinámico lo reemplaza con
física completa.

Lee del catálogo del producto:
    - propiedades_basicas.calor_especifico_seco → c_ps (sólido seco).
    - isoterma.gab.params → para construir aw_func (actividad de agua).

Referencias:
    - Mujumdar AS (2007). Handbook of Industrial Drying, 3ª ed. CRC Press.
    - Anderson RB (1946); Guggenheim EA (1966); De Boer JH (1953) — modelo GAB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

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
from core.camara import ForzantesAire

if TYPE_CHECKING:
    from core.camara import Camara


# ============================================================================
# Wire-up con el motor termodinámico
# ============================================================================
#
# El wire-up calcula h_conv (correlación de placa plana), K_m (Chilton-Colburn
# directo), cp efectivo del producto a X media, áreas y boundary del aire, y
# delega en simular_secado.
# ============================================================================

# Propiedades del aire a T_película de referencia (~50 °C, 1 atm). Constantes
# para v0 — variación < 5 % en el rango operativo de secado solar.
_MU_AIRE_PA_S: float = 1.96e-5
_K_AIRE_W_MK: float = 0.028
_PR_AIRE: float = 0.71
_LE_AGUA_AIRE: float = 1.0  # número de Lewis para aire-agua
_CP_AGUA_LIQ_J_KGK: float = 4186.0  # cp del agua líquida (cp efectivo del producto)
_RE_CRITICO_PLACA: float = 5.0e5  # transición laminar→turbulento


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
        Nu = 0.664 * Re**0.5 * _PR_AIRE ** (1.0 / 3.0)
    else:
        Nu = 0.037 * Re**0.8 * _PR_AIRE ** (1.0 / 3.0)
    return Nu * _K_AIRE_W_MK / L_caracteristico_m


def _calcular_termodinamico(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float,
    P_Pa: float,
    t_max_s: float = 24.0 * 3600.0,
    forzantes_aire: Optional["ForzantesAire"] = None,
) -> ResultadoMotorTermodinamico:
    """Wire-up de Camara → motor termodinámico transitorio.

    Lee del catálogo del producto:
        - propiedades_basicas.calor_especifico_seco → c_ps (sólido seco).
        - isoterma.gab.params → para construir aw_func. Si faltan, usa rampa
          lineal aw = clip(X/X_inicial, 0, 1) como fallback con advertencia.

    Calcula:
        - A_prod = n_bandejas · area_bandeja.
        - A_cuerpo = 2·(largo·alto + ancho·alto + largo·ancho).
        - v_aire = ṁ_as/(ρ·ancho·alto), h_conv por placa plana, K_m por
          Chilton-Colburn directo: K_m = h_conv/(cp_hum·Le^(2/3)).
        - Pared 3-nodos: deriva k_aisl desde U_muros del data model en
          condiciones de diseño (h_w McAdams a v_viento default).

    Si forzantes_aire se provee (modo "real" o "sintético"), se usa tal cual
    y los escalares T_operacion_K, HR_operacion, T_amb_K se ignoran (sólo se
    usan para los cálculos de h_conv/K_m de referencia y la decomposición de
    pared). Si no se provee, se arman forzantes degeneradas (2 puntos
    constantes) reproduciendo el comportamiento histórico.

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

    # --- Radiación solar al producto (techo translúcido) ---
    # Si la cámara tiene cubierta opaca (cubierta_translucida_id is None),
    # τ=0 y el motor anula el término Q_rad sin coste.
    if cons.cubierta_translucida_id is not None:
        tau_cub = float(catalogo.CUBIERTAS[cons.cubierta_translucida_id]["transmitancia_solar"])
        # α_producto: opcional en catálogo (default 0.6 — superficie sólida media)
        alfa_prod = float(propsb.get("alfa_solar", 0.6))
        # A_rad: explícito en construcción o, por defecto, una sola bandeja
        # (sólo la superior "ve" la radiación directa)
        A_rad = float(cons.A_rad_m2) if cons.A_rad_m2 is not None else b.area_bandeja_m2
    else:
        tau_cub = 0.0
        alfa_prod = 0.6  # irrelevante: τ·A_rad=0 anula el factor
        A_rad = 0.0

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
    A_cuerpo = 2.0 * (g.largo_m * g.alto_m + g.ancho_m * g.alto_m + g.largo_m * g.ancho_m)

    # --- Boundary del aire ---
    omega_ent = humedad_absoluta(HR_operacion, T_operacion_K, P_Pa)

    # --- T inicial del producto: explícito o T_amb ---
    T_prod_inicial = p.T_prod_inicial_K if p.T_prod_inicial_K is not None else T_amb_K

    # --- h_conv y K_m congelados (opción ii — bitácora §24.10) ---
    T_pelicula = 0.5 * (T_operacion_K + T_prod_inicial)
    rho_pelicula = densidad_aire_humedo(T_pelicula, omega_ent, P_Pa)
    area_transversal_m2 = g.ancho_m * g.alto_m
    v_aire = f.caudal_masico_kg_s / (rho_pelicula * area_transversal_m2)

    h_conv = _h_conv_camara_placa_plana(
        v_aire,
        g.largo_m,
        T_pelicula,
        omega_ent,
        P_Pa,
    )
    # Chilton-Colburn directo en conductancia másica: K_m = h/(cp_hum·Le^(2/3))
    cp_hum = 1006.0 + omega_ent * 1805.0
    K_m = h_conv / (cp_hum * _LE_AGUA_AIRE ** (2.0 / 3.0))

    # Coeficientes interiores variables en el tiempo: el motor llama a este
    # closure por paso con el estado del aire (T_ent(t), T_prod(t), ω_ent(t),
    # ṁ(t)). Reusa la misma correlación de placa plana + Chilton-Colburn, pero
    # con la película evaluada en (T_ent + T_prod)/2 y v_aire desde el ṁ(t)
    # actual. Los escalares h_conv/K_m de arriba quedan como fallback que el
    # motor usa sólo si no se le pasa este callable.
    def _coef_transporte(
        T_ent_local: float, T_prod_local: float, omega_ent_local: float, m_dot_local: float
    ) -> tuple[float, float]:
        T_pel = 0.5 * (T_ent_local + T_prod_local)
        rho = densidad_aire_humedo(T_pel, omega_ent_local, P_Pa)
        v_aire_t = m_dot_local / (rho * area_transversal_m2)
        h = _h_conv_camara_placa_plana(v_aire_t, g.largo_m, T_pel, omega_ent_local, P_Pa)
        cp_hum_t = 1006.0 + omega_ent_local * 1805.0
        return h, h / (cp_hum_t * _LE_AGUA_AIRE ** (2.0 / 3.0))

    # --- Decomposición de la pared en cascada 3-nodos ---
    # La pared opaca de la cámara está descrita como una composición de capas
    # (cons.pared) con R_conduccion = Σ(e_i/k_i). Pasamos al motor el espesor
    # total y un k equivalente tal que esp_total/k_eq = R_conduccion, así
    # internamente el motor reconstruye la misma R_cond sin necesidad de
    # cambiar su firma. Para pared simple (1 capa), k_eq = k_material; para
    # compuesta, k_eq es el promedio armónico ponderado por espesor.
    _V_VIENTO_DEFAULT_MS = 2.0
    R_cond_pared = cons.pared.R_conduccion_m2K_W
    esp_cam_total = cons.pared.espesor_total_m
    k_aisl = esp_cam_total / R_cond_pared

    # --- Forzantes: usar las del llamador o construir degeneradas ---
    if forzantes_aire is None:
        t_forz = np.array([0.0, t_max_s], dtype=float)
        forzantes_uso = ForzantesAire(
            t_s=t_forz,
            T_ent_K=np.full(2, T_operacion_K),
            omega_ent=np.full(2, omega_ent),
            m_dot_aire_seco_kg_s=np.full(2, f.caudal_masico_kg_s),
            T_amb_K=np.full(2, T_amb_K),
            v_viento_ms=np.full(2, _V_VIENTO_DEFAULT_MS),
        )
    else:
        forzantes_uso = forzantes_aire

    # --- Integración termodinámica ---
    res = simular_secado(
        T_prod_inicial_K=T_prod_inicial,
        X_prod_inicial_kg_kg=p.humedad_inicial_X,
        X_prod_objetivo_kg_kg=p.humedad_objetivo_X,
        m_seco_prod_kg=m_seco_prod,
        c_ps_J_kgK=cp_seco,
        forzantes=forzantes_uso,
        A_prod_m2=A_prod,
        A_cuerpo_m2=A_cuerpo,
        h_conv_W_m2K=h_conv,
        K_m_kg_m2s=K_m,
        k_aisl_W_mK=k_aisl,
        esp_cam_m=esp_cam_total,
        P_Pa=P_Pa,
        aw_func=_aw_func,
        coef_transporte_func=_coef_transporte,
        tau_cubierta_solar=tau_cub,
        alfa_producto_solar=alfa_prod,
        A_rad_m2=A_rad,
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
        T_cam_int_K=res.T_cam_int_K,
        T_cam_ext_K=res.T_cam_ext_K,
        U_pared_W_m2K=res.U_pared_W_m2K,
        HR_flujo=res.HR_flujo,
        masa_evaporada_total_kg=res.masa_evaporada_total_kg,
        Q_rad_W=res.Q_rad_W,
        energia_rad_total_J=res.energia_rad_total_J,
        horas_clipeo_nocturno_s=res.horas_clipeo_nocturno_s,
        horas_HR_alta_s=res.horas_HR_alta_s,
        T_max_alcanzada_K=res.T_max_alcanzada_K,
        advertencias=advertencias + list(res.advertencias),
    )


def calcular_camara(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float = 298.15,
    P_Pa: float = 101325.0,
    t_max_s: float = 72.0 * 3600.0,
    forzantes_aire: Optional["ForzantesAire"] = None,
) -> ResultadoMotorTermodinamico:
    """Punto de entrada único de la cámara — motor termodinámico.

    Desde S38 la cámara tiene un único motor físico (balance acoplado
    calor-masa). El campo ``camara.modo_calculo`` quedó como vestigial para
    back-compat de snapshots: cualquier valor se resuelve al motor
    termodinámico (la coerción ``'capa_fina' → 'termodinamico'`` ocurre en
    ``Camara.__post_init__``).

    Args:
        camara: Camara configurada.
        T_operacion_K: T del aire que entra a la cámara [K].
        HR_operacion: HR del aire que entra [fracción 0-1].
        T_amb_K: T ambiente externa [K]. Se usa para pérdidas a paredes y
            fallback de T_prod_inicial. Si se pasa forzantes_aire, se ignora.
        P_Pa: Presión total [Pa].
        t_max_s: Cota superior del tiempo de secado [s]. Default 72 h.
        forzantes_aire: Forzantes horarias de aire. None → motor arma
            forzantes degeneradas constantes desde los escalares
            (comportamiento histórico). Use
            `calculos.balance_global.construir_serie_sintetica_dia_tipo` o
            `armar_forzantes_aire` para construirlas.

    Returns:
        ResultadoMotorTermodinamico con curvas dinámicas.
    """
    return _calcular_termodinamico(
        camara,
        T_operacion_K,
        HR_operacion,
        T_amb_K,
        P_Pa,
        t_max_s=t_max_s,
        forzantes_aire=forzantes_aire,
    )
