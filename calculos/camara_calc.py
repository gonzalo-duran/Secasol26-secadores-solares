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
    - isoterma GAB (propia o por analogía, core.catalogo.isoterma_gab) → aw_func.

Coeficientes convectivos interiores (S61)
-----------------------------------------
Hasta S60 había **uno solo**, forzado (placa plana con μ/Pr/k congelados a
~50 °C), compartido entre el producto y el film interior de la pared. A bajo
caudal —el caso de todo secador de convección natural— eso daba ``h → 0`` y, con
el film de pared atado a él, ``U_total → 0``: la cámara aparecía perfectamente
aislada justo cuando más pierde. Ahora hay dos, ambos de convección **mixta** y
con propiedades del aire variables con T:

- ``coef_conveccion_producto_local`` — placa horizontal (bandeja), rama según el
  signo de ΔT, combinación transversal ``n = 7/2``.
- ``coef_conveccion_pared_local`` — placa vertical (Churchill-Chu), combinación
  asistida ``n = 3``, con el piso conductivo ``Nu → 0.68``.

A velocidades de convección forzada (≳0.5 m/s) el resultado queda dentro del
~4 % del modelo viejo; la diferencia aparece cuando el flujo se apaga. Ver
``docs/notas/estado_conveccion_natural_secasol.md``.

Topología de transferencia — cross-flow único (S64)
--------------------------------------------------
El aire pasa **entre** bandejas y toca las dos caras libres del lecho: área de
bandeja y placa plana, con la velocidad **del canal** (``motor_calc`` usa esa
misma sección para su pérdida de carga).

La posición de las bocas —entrada abajo en una cara, salida arriba en la
opuesta— hace que el flujo **global** de una CAJA o un ARMARIO sea diagonal
ascendente, pero **local sobre la bandeja** es cross-flow: la disposición de las
aberturas fija la escala del flujo y la de las bandejas fija la dirección local
sobre el producto. Son dos problemas separados.

S63 había agregado una segunda topología (``VERTICAL_ASCENDENTE`` → through-flow,
el aire atravesando el lecho, con área de partícula y Ranz-Marshall). Se retiró
en S64: en un secador pasivo el lecho pide ~31 Pa contra ~1.3 Pa de tiro térmico
disponible, o sea que el aire **no puede** tomar ese camino, y la dirección local
del flujo no es un dato que un usuario de prediseño pueda responder con
confianza. Ver ``docs/notas/plan_crossflow_unico_camara.md``.

El área cuenta las **dos caras** de la bandeja (la inferior descontada por el
área abierta de la malla y por transferir peor); ver ``_FACTOR_CARA_INFERIOR``.

Referencias:
    - Mujumdar AS (2007). Handbook of Industrial Drying, 3ª ed. CRC Press.
    - Anderson RB (1946); Guggenheim EA (1966); De Boer JH (1953) — modelo GAB.
    - Incropera & DeWitt (7ª ed.), cap. 9 "Free Convection".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np
from scipy.optimize import brentq

from calculos.camara_termodinamica import (
    ResultadoCascada,
    ResultadoMotorTermodinamico,
    resolver_cadena_camara,
    simular_cascada,
    simular_secado,
)
from calculos.correlaciones_nusselt import (
    N_MIXTO_ASISTIDA,
    N_MIXTO_TRANSVERSAL,
    nusselt_mixto,
    nusselt_placa_horizontal,
    nusselt_placa_vertical,
)
from calculos.lecho_producto import area_abierta_malla_efectiva
from calculos.propiedades_aire import propiedades_aire
from calculos.psicrometria import (
    HR_desde_omega,
    actividad_agua_desde_X_GAB,
    calor_latente_vaporizacion,
    densidad_aire_humedo,
    humedad_absoluta,
)
from core import catalogo
from core.camara import ForzantesAire
from core.lecho import geometria_lecho

if TYPE_CHECKING:
    from core.camara import Camara


# ============================================================================
# Wire-up con el motor termodinámico
# ============================================================================
#
# El wire-up calcula h_conv y el área de transferencia (según la topología de
# flujo, ver más abajo), K_m (Chilton-Colburn directo), cp efectivo del producto
# a X media, el resto de las áreas y el boundary del aire, y delega en
# simular_secado.
# ============================================================================

_LE_AGUA_AIRE: float = 1.0  # número de Lewis para aire-agua
_CP_AGUA_LIQ_J_KGK: float = 4186.0  # cp del agua líquida (cp efectivo del producto)
_RE_CRITICO_PLACA: float = 5.0e5  # transición laminar→turbulento
_ESPESOR_CUBIERTA_DEFAULT_M: float = 0.006  # 6 mm — default del techo translúcido
_G_MS2: float = 9.81  # aceleración de la gravedad
# Penalización de la cara INFERIOR de la bandeja frente a la superior (S64).
#
# El aire circula por encima y por debajo de la bandeja, así que la cota superior
# del área de transferencia es 2× la cara superior. Pero la cara de abajo
# transfiere peor: es el análogo de la placa caliente mirando hacia abajo, con
# estratificación estable en vez de desprendimiento de pluma. El factor sale del
# cociente entre la rama débil y la fuerte de ``nusselt_placa_horizontal`` en el
# rango de Ra de una bandeja (L = A_s/P ≈ 0.1 m, ΔT 10–30 K ⇒ Ra ~1e5–1e7):
#
#     Ra      Nu fuerte   Nu débil   débil/fuerte
#     1e4        5.40       3.28        0.61
#     1e5        9.60       5.20        0.54
#     1e6       17.08       8.24        0.48
#     1e7       32.32      13.06        0.40
#
# LÍMITE DECLARADO: el signo real del empuje en la cara inferior lo decide la
# competencia entre el término térmico y el solutal —el aire húmedo es más
# liviano que el seco (M_agua 18 vs M_aire 29)—, y se invierte. Con el producto
# por debajo del aire (armario indirecto, producto en bulbo húmedo) la película
# de abajo se enfría más de lo que se humedece, queda más pesada y drena: rama
# fuerte. Con el producto por encima (CAJA con producto insolado) los dos
# términos la alivianan y queda atrapada: rama débil. El cruce está en |ΔT| ≈ 2 K.
# Resolverlo exige el empuje solutal (Incropera Ec. 9.65), que ``_rayleigh``
# declara pendiente; mientras tanto se adopta el factor fijo.
_FACTOR_CARA_INFERIOR: float = 0.5
# Sub-etapas con que se discretiza el camino del aire en over-flow (S63). El
# canal entre bandejas es un intercambiador CONTINUO a lo largo de la bandeja,
# no un tanque mezclado: hay que partirlo para que tienda a flujo pistón.
#
# Con 8 el acercamiento queda ~1 % por debajo del límite de pistón en el régimen
# típico de over-flow (NTU ≲ 0.5) y ~4 % a NTU ≈ 2. Quedar un poco corto es
# deliberado y no solo barato: el pistón perfecto también es una idealización
# —una cámara real tiene mezcla axial— así que la verdad está entre el CSTR y el
# pistón, no en el pistón.
_N_ETAPAS_OVERFLOW: int = 8


def _h_conv_camara_placa_plana(
    v_aire_ms: float,
    L_caracteristico_m: float,
    T_pelicula_K: float,
    omega_pelicula: float,
    P_Pa: float,
) -> float:
    """Coeficiente convectivo **forzado** aire→superficie por placa plana.

    Re < 5e5: Nu = 0.664·Re^0.5·Pr^(1/3)   (laminar, Pohlhausen)
    Re > 5e5: Nu = 0.037·Re^0.8·Pr^(1/3)   (turbulento, McAdams)

    Desde S61 evalúa μ, k y Pr con ``propiedades_aire(T_película)`` en vez de
    congelarlas a ~50 °C (mismo criterio que el colector desde S36).

    Args:
        v_aire_ms: Velocidad media del aire sobre la superficie [m/s].
        L_caracteristico_m: Longitud de la placa en la dirección del flujo [m].
        T_pelicula_K: Temperatura de película [K].
        omega_pelicula: Humedad absoluta de película [kg_w/kg_as] (solo entra en ρ).
        P_Pa: Presión absoluta [Pa].

    Returns:
        h forzado [W/(m²·K)].
    """
    if L_caracteristico_m <= 0.0:
        return 0.0
    props = propiedades_aire(T_pelicula_K, P_Pa)
    rho = densidad_aire_humedo(T_pelicula_K, omega_pelicula, P_Pa)
    Re = rho * v_aire_ms * L_caracteristico_m / props["mu"]
    if Re < _RE_CRITICO_PLACA:
        Nu = 0.664 * Re**0.5 * props["pr"] ** (1.0 / 3.0)
    else:
        Nu = 0.037 * Re**0.8 * props["pr"] ** (1.0 / 3.0)
    return Nu * props["k"] / L_caracteristico_m


def _rayleigh(
    delta_T_K: float,
    L_m: float,
    T_pelicula_K: float,
    omega_pelicula: float,
    P_Pa: float,
) -> float:
    """Rayleigh ``Ra = g·β·|ΔT|·L³/(ν·α)`` con propiedades a T de película.

    Con β = 1/T_película (gas ideal, Incropera Ec. 9.9). Solo empuje **térmico**:
    el empuje por concentración de vapor (Ec. 9.65) queda como refinamiento
    pendiente — ver ``docs/notas/estado_conveccion_natural_secasol.md`` §6.3.

    Args:
        delta_T_K: Diferencia de temperatura fluido↔superficie [K] (se usa |ΔT|).
        L_m: Longitud característica [m].
        T_pelicula_K: Temperatura de película [K].
        omega_pelicula: Humedad absoluta de película [kg_w/kg_as].
        P_Pa: Presión absoluta [Pa].

    Returns:
        Ra [adim] (0 si ΔT o L son nulos).
    """
    if L_m <= 0.0 or delta_T_K == 0.0:
        return 0.0
    props = propiedades_aire(T_pelicula_K, P_Pa)
    rho = densidad_aire_humedo(T_pelicula_K, omega_pelicula, P_Pa)
    nu = props["mu"] / rho
    alfa = props["k"] / (rho * props["cp"])
    return _G_MS2 * props["beta"] * abs(delta_T_K) * L_m**3 / (nu * alfa)


def _L_caracteristica_bandeja(area_bandeja_m2: float, largo_m: float, ancho_m: float) -> float:
    """Longitud característica ``L = A_s/P`` de una bandeja (Incropera Ec. 9.29).

    El catálogo de la cámara guarda el **área** de bandeja pero no sus lados, así
    que se supone una bandeja rectangular con la misma relación de aspecto que la
    planta de la cámara: ``a = √(A·r)``, ``c = √(A/r)`` con ``r = largo/ancho``.
    Para una bandeja cuadrada de lado ``s`` da ``L = s/4``, como corresponde.

    Args:
        area_bandeja_m2: Área de carga de una bandeja [m²].
        largo_m: Largo de la cámara [m].
        ancho_m: Ancho de la cámara [m].

    Returns:
        L característica [m] (0 si el área no es positiva).
    """
    if area_bandeja_m2 <= 0.0:
        return 0.0
    r = largo_m / ancho_m if ancho_m > 0.0 else 1.0
    a = (area_bandeja_m2 * r) ** 0.5
    c = (area_bandeja_m2 / r) ** 0.5
    perimetro = 2.0 * (a + c)
    return area_bandeja_m2 / perimetro if perimetro > 0.0 else 0.0


def area_transversal_flujo_m2(camara: "Camara") -> float:
    """Sección de paso del aire por la cámara [m²].

    Es la cara **perpendicular** al recorrido del aire. Con cross-flow único
    (S64) el aire recorre el largo de la cámara, así que la sección es
    ``ancho × alto``.

    Es la sección de la **cámara**, no la del canal entre bandejas: la usa el
    film de pared, que ve el aire de todo el recinto. La velocidad que ve el
    producto sale de ``area_canal_entre_bandejas_m2``.

    Args:
        camara: Cámara con geometría.

    Returns:
        Área de la sección transversal al flujo [m²].
    """
    g = camara.geometria
    return float(g.ancho_m * g.alto_m)


def area_canal_entre_bandejas_m2(camara: "Camara") -> float:
    """Sección de paso **entre** bandejas [m²] — la que ve el producto.

    En cross-flow el aire no atraviesa la sección completa de la cámara: pasa
    por los ``n_bandejas − 1`` canales que quedan entre bandejas, en paralelo,
    con altura libre ``separacion − espesor_capa``. Es exactamente la sección
    con la que ``motor_calc`` calcula la pérdida de carga del mismo tramo, y
    desde S63 también la que fija la velocidad de transferencia: hasta entonces
    la transferencia usaba la cara entera (``ancho × alto``) y la pérdida de
    carga el canal, o sea dos velocidades distintas para el mismo aire (en el
    armario de referencia, 0.55 m² contra 0.225 m²).

    Args:
        camara: Cámara con geometría y bandejas.

    Returns:
        Sección de los canales [m²]. Cae a la sección de la cámara si la
        geometría no define canales (una sola bandeja, o capa que llena la
        separación).
    """
    g, b = camara.geometria, camara.bandejas
    espacio_libre = max(0.0, b.separacion_entre_bandejas_m - b.espesor_capa_m)
    # Con carros (túnel, S70) el aire los atraviesa EN SERIE: en cada sección
    # transversal solo están los canales de UN carro. Hasta S70 se tomaban las
    # n_carros × bandejas_por_carro bandejas como una única pila en paralelo, y
    # en ADITAL (24 × 14) la velocidad sobre el producto salía ~26× baja
    # (0.06 m/s contra 0.2–1.25 m/s medidos, Condorí 2009). `motor_calc` ya lo
    # hacía así para la pérdida de carga.
    if camara.carros is not None:
        n_canales = max(0, camara.carros.bandejas_por_carro - 1)
    else:
        n_canales = max(0, b.n_bandejas - 1)
    area = g.ancho_m * espacio_libre * n_canales
    if area <= 0.0:
        return area_transversal_flujo_m2(camara)
    return float(area)


def longitud_flujo_producto_m(camara: "Camara") -> float:
    """Largo de placa que recorre el aire sobre el producto antes de reiniciar la capa límite.

    Es el largo de la **bandeja** en la dirección del aire: la capa límite se corta en
    su borde (S70, Fase 1 del plan de evaporación). Las bandejas ocupan el ancho de la
    cámara, así que su largo es ``área_bandeja / ancho``, sin pasar del largo de la
    cámara ni, con carros, del largo del carro (o del túnel repartido entre los carros
    en fila).

    Hasta S70 se usaba el largo de la cámara (o del túnel). Contra la evaporación de agua
    libre de Durán et al. 2008 (bandejas de 20 × 10 cm en la caja forzada, 0.61 kg/m²h
    medidos) la película con el largo de la caja daba 0.43 kg/m²h y con el de la
    bandeja 0.57; contra la correlación de Carrier/ASHRAE para superficies de agua, el
    largo de la cámara subestimaba 2–3× a 1–3 m/s. En ADITAL, con 18 m de placa
    laminar, el ``h`` caía a ~2 W/(m²·K).
    """
    g, b = camara.geometria, camara.bandejas
    L = g.largo_m
    if g.ancho_m > 0.0 and b.area_bandeja_m2 > 0.0:
        L = min(L, b.area_bandeja_m2 / g.ancho_m)
    carros = camara.carros
    if carros is not None:
        L_carro = (
            carros.largo_carro_m
            if carros.largo_carro_m is not None
            else g.largo_m / carros.n_carros
        )
        L = min(L, L_carro)
    return L


def area_transferencia_producto_m2(camara: "Camara") -> float:
    """Superficie de producto expuesta al aire [m²] — las dos caras (S64).

    El aire circula por encima **y por debajo** de la bandeja, así que la cota
    superior es 2× la cara superior. La cara inferior se descuenta dos veces:

    - por el **área abierta de la malla**, que es la fracción de la cara de
      abajo que el aire realmente alcanza (``area_abierta_malla_efectiva``);
    - por transferir peor que la de arriba (``_FACTOR_CARA_INFERIOR``, ver la
      constante para el anclaje y su límite de validez).

    Args:
        camara: Cámara con bandejas.

    Returns:
        Área de transferencia aire↔producto [m²].
    """
    b = camara.bandejas
    f_abierta = area_abierta_malla_efectiva(b.tipo_malla)
    return float(b.n_bandejas * b.area_bandeja_m2 * (1.0 + f_abierta * _FACTOR_CARA_INFERIOR))


def coef_conveccion_producto_local(
    v_aire_ms: float,
    T_flujo_K: float,
    T_prod_K: float,
    omega: float,
    P_Pa: float,
    L_flujo_m: float,
    L_bandeja_m: float,
) -> float:
    """Coeficiente convectivo aire↔producto — convección **mixta transversal**.

    El aire barre la bandeja horizontalmente mientras el empuje actúa en
    vertical: forzada y natural son **perpendiculares**, no asistidas. Por eso
    se combinan con ``n = 7/2`` (Incropera Ec. 9.64) y no con el ``n = 3`` del
    colector.

    - Componente forzada: placa plana sobre ``L_flujo_m`` (largo de cámara).
    - Componente natural: placa **horizontal** con ``L = A_s/P`` (Ec. 9.29). La
      rama la decide el signo de ΔT: con el aire más caliente que el producto
      —caso normal del secado, el producto se enfría por evaporación— la
      bandeja es una superficie *fría mirando arriba* ⇒ estratificación estable
      ⇒ rama débil (Ec. 9.32). Con el producto más caliente (transitorio
      temprano, bandeja insolada) ⇒ rama fuerte (9.30/9.31).

    La combinación se aplica sobre los **coeficientes h** y no sobre los Nusselt
    porque cada componente usa su propia longitud característica (largo de flujo
    vs. A/P); es la misma media potencial de la Ec. 9.64.

    Args:
        v_aire_ms: Velocidad media del aire en la cámara [m/s].
        T_flujo_K: Temperatura del aire interior [K].
        T_prod_K: Temperatura del producto [K].
        omega: Humedad absoluta del aire [kg_w/kg_as].
        P_Pa: Presión absoluta [Pa].
        L_flujo_m: Longitud recorrida por el aire (largo de cámara) [m].
        L_bandeja_m: Longitud característica de la bandeja ``A_s/P`` [m].

    Returns:
        h aire↔producto [W/(m²·K)].
    """
    T_pel = 0.5 * (T_flujo_K + T_prod_K)
    h_forzado = _h_conv_camara_placa_plana(v_aire_ms, L_flujo_m, T_pel, omega, P_Pa)
    delta_T = T_flujo_K - T_prod_K
    Ra = _rayleigh(delta_T, L_bandeja_m, T_pel, omega, P_Pa)
    # Aire más caliente que el producto (ΔT > 0) ⇒ superficie fría mirando
    # arriba ⇒ estratificación ESTABLE (rama débil).
    Nu_nat = nusselt_placa_horizontal(Ra, inestable=delta_T < 0.0)
    h_natural = (
        Nu_nat * propiedades_aire(T_pel, P_Pa)["k"] / L_bandeja_m if L_bandeja_m > 0 else 0.0
    )
    return nusselt_mixto(h_forzado, h_natural, N_MIXTO_TRANSVERSAL)


def coef_conveccion_pared_local(
    v_aire_ms: float,
    T_flujo_K: float,
    T_amb_K: float,
    omega: float,
    P_Pa: float,
    L_flujo_m: float,
    alto_m: float,
    R_cond_pared_m2K_W: float,
    h_w_W_m2K: float,
) -> float:
    """Coeficiente convectivo interior aire↔pared — mixta sobre placa vertical.

    Separado del de producto desde S61 (decisión §6.2): comparten el aire pero
    no la geometría, y sobre todo la pared necesita el **piso conductivo**
    ``Nu → 0.68`` de Churchill-Chu (Ec. 9.27). Con el film interior atado al
    coeficiente forzado, a caudal casi nulo ``h → 0`` hacía ``U_total → 0`` y la
    cámara aparecía perfectamente aislada.

    Combinación mixta con ``n = 3``: sobre una pared vertical el empuje corre a
    lo largo de la superficie (no transversal como en la bandeja).

    El ΔT que gobierna el empuje es el que cae en la **película interior**, no
    ``T_flujo − T_amb``. Como la partición depende del propio ``h`` que estamos
    calculando, se resuelve con dos pasadas de punto fijo (sobra: Nu ~ Ra^{1/4}).

    Args:
        v_aire_ms: Velocidad media del aire en la cámara [m/s].
        T_flujo_K: Temperatura del aire interior [K].
        T_amb_K: Temperatura ambiente exterior [K].
        omega: Humedad absoluta del aire [kg_w/kg_as].
        P_Pa: Presión absoluta [Pa].
        L_flujo_m: Longitud recorrida por el aire (largo de cámara) [m].
        alto_m: Altura de la pared [m] — longitud característica de la natural.
        R_cond_pared_m2K_W: Resistencia conductiva de la pared [m²·K/W].
        h_w_W_m2K: Coeficiente exterior por viento (McAdams) [W/(m²·K)].

    Returns:
        h aire↔cara interior de la pared [W/(m²·K)].
    """
    delta_T_total = T_flujo_K - T_amb_K
    T_pel = 0.5 * (T_flujo_K + T_amb_K)
    h_forzado = _h_conv_camara_placa_plana(v_aire_ms, L_flujo_m, T_pel, omega, P_Pa)
    k_aire = propiedades_aire(T_pel, P_Pa)["k"]
    R_ext = 1.0 / h_w_W_m2K if h_w_W_m2K > 0.0 else 0.0

    Pr = propiedades_aire(T_pel, P_Pa)["pr"]
    h = h_forzado
    delta_T_int = delta_T_total
    for _ in range(2):
        Ra = _rayleigh(delta_T_int, alto_m, T_pel, omega, P_Pa)
        Nu_nat = nusselt_placa_vertical(Ra, Pr)
        h_natural = Nu_nat * k_aire / alto_m if alto_m > 0 else 0.0
        h = nusselt_mixto(h_forzado, h_natural, N_MIXTO_ASISTIDA)
        # Reparto de ΔT por resistencias en serie: la película interior se lleva
        # R_int/(R_int + R_cond + R_ext) del salto total.
        if h > 0.0:
            R_int = 1.0 / h
            R_total = R_int + R_cond_pared_m2K_W + R_ext
            delta_T_int = delta_T_total * R_int / R_total if R_total > 0.0 else delta_T_total
    return h


@dataclass
class _ParamsCamaraTD:
    """Parámetros del motor termodinámico derivados de una ``Camara``.

    Empaqueta el wire-up común a los dos subtipos de cámara (batch monozona y
    túnel semicontinuo): propiedades del producto, isoterma, geometría TOTAL,
    coeficientes de transporte y decomposición de pared. El consumidor batch
    los usa tal cual; el consumidor cascada reparte las áreas y la masa en
    ``n_zonas`` columnas.
    """

    cp_seco: float
    m_seco_total_kg: float
    T_prod_inicial_K: float
    X_inicial: float
    X_objetivo: float
    aw_func: Callable[[float], float]
    A_prod_total_m2: float
    n_etapas_aire: int
    A_cuerpo_total_m2: float
    h_conv_W_m2K: float
    K_m_kg_m2s: float
    coef_transporte_func: Callable[[float, float, float, float], tuple[float, float]]
    coef_pared_func: Callable[[float, float, float, float], float]
    k_aisl_W_mK: float
    esp_cam_total_m: float
    tau_cubierta_solar: float
    alfa_producto_solar: float
    A_rad_total_m2: float
    R_cond_techo_m2K_W: float
    A_techo_total_m2: float
    advertencias: list[str]
    # Resistencia interna (S70): T_prod → λ [1/s]; None sin difusividad en catálogo.
    tasa_difusion_func: Optional[Callable[[float], float]] = None


def _construir_params_termodinamico(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float,
    P_Pa: float,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
) -> _ParamsCamaraTD:
    """Arma los parámetros del motor termodinámico desde la ``Camara``.

    Lógica compartida por el batch (``_calcular_termodinamico``) y el túnel
    semicontinuo (``calcular_camara_cascada``). Lee el catálogo del producto
    (cp seco, GAB), calcula h_conv y el área de transferencia según la
    topología de flujo (lecho atravesado o placa) y K_m (Chilton-Colburn),
    el closure de coeficientes variables en t, y la decomposición de pared.

    Args:
        camara: Cámara configurada.
        T_operacion_K, HR_operacion, T_amb_K, P_Pa: Condiciones de referencia.
        factor_h_conv: Multiplicador del coeficiente convectivo interior. Como K_m
            se deriva de h_conv por Chilton-Colburn, escalar h **también** escala la
            transferencia de masa (es el efecto físico de cambiar la convección).
        factor_K_m: Multiplicador **adicional** solo sobre el coeficiente de
            transferencia de masa, para calibrar la evaporación sin tocar el calor
            sensible (absorbe la incertidumbre de área efectiva de producto y de la
            correlación de Chilton-Colburn).

    Con ambos factores en 1.0 (default) el resultado es idéntico al histórico.
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

    # --- Radiación solar al producto (superficies translúcidas) ---
    # Área conductiva vidriada = suma de las caras activas (techo, y en su caso
    # frente/atrás/laterales — ver GeometriaCamara.caras()). Esas caras se
    # modelan como vidriado (R_cond = espesor/k_efectivo) y se *quitan* de la
    # envolvente opaca A_cuerpo para no doble-contar.
    A_techo = 0.0
    R_cond_techo = 0.0
    caras_activas = cons.caras_translucidas_activas()
    if cons.cubierta_translucida_id is not None:
        cub = catalogo.CUBIERTAS[cons.cubierta_translucida_id]
        tau_cub = float(cub["transmitancia_solar"])
        alfa_prod = float(propsb.get("alfa_solar", 0.6))
        A_rad = float(cons.A_rad_m2) if cons.A_rad_m2 is not None else b.area_bandeja_m2
        # Espesor del vidriado (default 6 mm) y k efectivo según espesor (alveolar)
        # o conductividad del catálogo.
        espesor_techo_m = (
            cons.cubierta_translucida_espesor_m
            if cons.cubierta_translucida_espesor_m is not None
            else _ESPESOR_CUBIERTA_DEFAULT_M
        )
        mapa_k = cub.get("k_efectivo_por_espesor_mm")
        k_techo = None
        if mapa_k:
            k_techo = mapa_k.get(int(round(espesor_techo_m * 1000)))
        if k_techo is None:
            k_techo = cub.get("conductividad_termica")
        if k_techo and k_techo > 0 and caras_activas:
            caras_geom = g.caras()
            A_techo = sum(caras_geom[nombre].area_m2 for nombre in caras_activas)
            R_cond_techo = espesor_techo_m / float(k_techo)
        elif not (k_techo and k_techo > 0):
            advertencias.append(
                f"CAM_TD_K_TECHO_FALTA: cubierta '{cons.cubierta_translucida_id}' sin "
                "conductividad para el vidriado; su pérdida conductiva se omite."
            )
    else:
        tau_cub = 0.0
        alfa_prod = 0.6
        A_rad = 0.0

    # Masa seca total: m_total = m_seco·(1 + X_inicial)
    m_seco_prod = p.masa_total_kg / (1.0 + p.humedad_inicial_X)

    # --- aw_func: GAB propia o por analogía (S70); reserva sin isoterma ---
    iso_gab = catalogo.isoterma_gab(p.producto_id)
    if iso_gab is not None:
        X_m_GAB, C_GAB, K_GAB = iso_gab.X_m, iso_gab.C, iso_gab.K
        if iso_gab.origen == "analogia":
            advertencias.append(
                f"CAM_TD_GAB_ANALOGIA: '{p.producto_id}' no tiene isoterma propia; "
                f"usa la de '{iso_gab.material_fuente}' por analogía (ver catálogo)."
            )
        if K_GAB >= 1.0:
            advertencias.append(
                f"CAM_TD_GAB_K_MAYOR_1: la isoterma GAB de '{p.producto_id}' tiene "
                f"K={K_GAB:.3f} ≥ 1, fuera del rango teórico del modelo (ajuste "
                "empírico de desorción). a_w queda acotada por "
                f"1/K={1.0 / K_GAB:.3f}: el producto fresco no alcanza a_w = 1."
            )

        def _aw_func(X: float) -> float:
            try:
                return actividad_agua_desde_X_GAB(X, X_m_GAB, C_GAB, K_GAB)
            except ValueError:
                # S70: con parámetros validados (X_m, C, K > 0), la única falla
                # posible es K < 1 y X por encima del máximo de la isoterma
                # (a_w > 1): agua libre, a_w = 1. Hasta S69 había acá un
                # escalón 1/0 en X_m que atrapaba también el rechazo de K ≥ 1
                # (el pimiento entero corría con ese escalón).
                return 1.0

    else:
        # Reserva sin isoterma (S70; hasta S69 era la rampa a_w = X/X_inicial,
        # que multiplicaba a ω_sat una actividad de agua físicamente falsa — 0.5
        # con el producto a medio secar — y simulaba mal un período decreciente).
        # Ahora: agua libre (a_w = 1, película pura) hasta la humedad de
        # equilibrio escalar del catálogo, y caída lineal debajo para que el
        # secado se detenga cerca de ella. Explícitamente optimista.
        X_eq_cat = (datos.get("propiedades_basicas") or {}).get("humedad_equilibrio_aire_seco")
        X_eq_res = float(X_eq_cat) if X_eq_cat else 0.0
        advertencias.append(
            f"CAM_TD_GAB_FALTA: '{p.producto_id}' sin isoterma propia ni analogía. "
            f"Se usa a_w = 1 hasta X_eq = {X_eq_res:.3f} kg/kg (agua libre): la "
            "velocidad de secado queda sobreestimada en todo el lote."
        )

        def _aw_func(X: float) -> float:
            if X_eq_res <= 0.0:
                return 1.0
            return max(0.0, min(1.0, X / X_eq_res))

    # --- Resistencia interna a la difusión (S70, Fase 2) ---
    # λ(T) = μ₁²·D_eff(T)/L², con L la mitad de la dimensión de la PIEZA (el
    # mismo d_p del lecho: espesor de rodaja, diámetro de arilo), no el espesor
    # de capa. Sin difusividad en el catálogo la superficie es la humedad media
    # (película pura) y se avisa: el secado queda sobreestimado.
    _difusion = catalogo.difusion_interna(p.producto_id)
    _tasa_difusion: Optional[Callable[[float], float]] = None
    if _difusion is not None:
        # Prioridad: d_p explícito del usuario → dimensión de pieza del bloque de
        # difusión → d_p del catálogo/lecho.
        _d_pieza_m, _, _ = geometria_lecho(camara.bandejas, p.producto_id)
        if (
            camara.bandejas.diametro_eq_particula_m is None
            and _difusion.dimension_pieza_m is not None
        ):
            _d_pieza_m = _difusion.dimension_pieza_m

        def _tasa_difusion(T_prod_K: float) -> float:
            return _difusion.tasa_primer_modo_s(T_prod_K, _d_pieza_m)

    else:
        advertencias.append(
            f"CAM_TD_DIFUSION_FALTA: '{p.producto_id}' sin difusividad efectiva en el "
            "catálogo. Se evapora sin resistencia interna (solo la película del aire): "
            "el período decreciente no está representado y el tiempo de secado queda "
            "subestimado."
        )

    # --- Geometría total ---
    # TOPOLOGÍA DE TRANSFERENCIA (S64): cross-flow único. El aire pasa entre
    # bandejas y toca las DOS caras libres del lecho; la de abajo, gateada por
    # el área abierta de la malla y penalizada por transferir peor.
    A_prod = area_transferencia_producto_m2(camara)

    # Sub-etapas en serie del camino del aire (S63, etapa 4). El aire no está
    # perfectamente mezclado: recorre el canal humedeciéndose, o sea flujo
    # pistón, y un CSTR no puede saturar por construcción. Los canales entre
    # bandejas están en PARALELO —cada uno recibe aire de entrada— pero cada
    # canal es un intercambiador continuo a lo largo de la bandeja, así que lo
    # que se discretiza es su largo.
    n_etapas_aire = _N_ETAPAS_OVERFLOW
    # A_cuerpo_total_m2 incluye piso + techo (a un agua) + 4 paredes; con
    # pendiente_techo_deg=0 es idéntica a la fórmula histórica de caja
    # rectangular: 2·(largo·alto + ancho·alto + largo·ancho).
    A_cuerpo = g.A_cuerpo_total_m2
    # Envolvente opaca: las caras translúcidas activas se modelan como
    # vidriado (U_techo) aparte y se descuentan del cuerpo opaco.
    A_cuerpo_opaco = A_cuerpo - A_techo

    # --- Boundary del aire de referencia ---
    omega_ent = humedad_absoluta(HR_operacion, T_operacion_K, P_Pa)
    T_prod_inicial = p.T_prod_inicial_K if p.T_prod_inicial_K is not None else T_amb_K

    # --- Decomposición de la pared en cascada 3-nodos ---
    R_cond_pared = cons.pared.R_conduccion_m2K_W
    esp_cam_total = cons.pared.espesor_total_m
    k_aisl = esp_cam_total / R_cond_pared

    # --- h_conv y K_m congelados (referencia / fallback) ---
    # Sección de la CÁMARA: la que ve el film de pared (aire de todo el recinto).
    area_transversal_m2 = area_transversal_flujo_m2(camara)
    # Sección que ve el PRODUCTO: los canales entre bandejas, la misma con la
    # que motor_calc calcula la pérdida de carga del tramo.
    area_paso_producto_m2 = area_canal_entre_bandejas_m2(camara)
    L_bandeja = _L_caracteristica_bandeja(b.area_bandeja_m2, g.largo_m, g.ancho_m)
    L_flujo_producto = longitud_flujo_producto_m(camara)

    def _h_producto(
        T_aire_camara_K: float, T_prod_local: float, omega_local: float, m_dot_local: float
    ) -> float:
        """h aire↔producto en cross-flow, con la velocidad del canal.

        El primer argumento es la temperatura del aire **dentro** de la cámara
        (``T_flujo``), la misma que aparece en la fuerza impulsora
        ``h·A·(T_flujo − T_prod)``. Hasta S63 llegaba ``T_ent``, que mezclaba dos
        temperaturas del aire en un mismo término (ver ``simular_secado``).

        El coeficiente es el de la cara **superior**; la penalización de la cara
        inferior está del lado del área (``area_transferencia_producto_m2``).
        """
        T_pel = 0.5 * (T_aire_camara_K + T_prod_local)
        rho = densidad_aire_humedo(T_pel, omega_local, P_Pa)
        v_aire_t = (
            m_dot_local / (rho * area_paso_producto_m2) if area_paso_producto_m2 > 0.0 else 0.0
        )
        return (
            coef_conveccion_producto_local(
                v_aire_t,
                T_aire_camara_K,
                T_prod_local,
                omega_local,
                P_Pa,
                L_flujo_producto,
                L_bandeja,
            )
            * factor_h_conv
        )

    h_conv = _h_producto(T_operacion_K, T_prod_inicial, omega_ent, f.caudal_masico_kg_s)
    cp_hum = 1006.0 + omega_ent * 1805.0
    K_m = h_conv / (cp_hum * _LE_AGUA_AIRE ** (2.0 / 3.0)) * factor_K_m

    # --- Coeficientes interiores variables en t (closure) ---
    def _coef_transporte(
        T_aire_camara_K: float, T_prod_local: float, omega_ent_local: float, m_dot_local: float
    ) -> tuple[float, float]:
        h = _h_producto(T_aire_camara_K, T_prod_local, omega_ent_local, m_dot_local)
        cp_hum_t = 1006.0 + omega_ent_local * 1805.0
        return h, h / (cp_hum_t * _LE_AGUA_AIRE ** (2.0 / 3.0)) * factor_K_m

    def _coef_pared(
        T_aire_camara_K: float, T_amb_local: float, m_dot_local: float, h_w_local: float
    ) -> float:
        """Film interior de pared/techo, separado del de producto (S61).

        El primer argumento es la temperatura del aire **dentro de la cámara**
        (``T_flujo``), no la del aire que entra: es el ΔT contra el ambiente el
        que mueve la convección natural sobre la cara interna. Pasarle ``T_ent``
        anulaba el empuje en tipología CAJA, donde el aire entra a la ambiente
        (ver ``simular_secado._resolver``, S62). Como ``T_flujo`` es la incógnita
        del solve, el motor llama a este closure dos veces por paso.
        """
        T_pel = 0.5 * (T_aire_camara_K + T_amb_local)
        rho = densidad_aire_humedo(T_pel, omega_ent, P_Pa)
        v_aire_t = m_dot_local / (rho * area_transversal_m2)
        return (
            coef_conveccion_pared_local(
                v_aire_t,
                T_aire_camara_K,
                T_amb_local,
                omega_ent,
                P_Pa,
                g.largo_m,
                g.alto_m,
                R_cond_pared,
                h_w_local,
            )
            * factor_h_conv
        )

    return _ParamsCamaraTD(
        cp_seco=cp_seco,
        m_seco_total_kg=m_seco_prod,
        T_prod_inicial_K=T_prod_inicial,
        X_inicial=p.humedad_inicial_X,
        X_objetivo=p.humedad_objetivo_X,
        aw_func=_aw_func,
        A_prod_total_m2=A_prod,
        n_etapas_aire=n_etapas_aire,
        A_cuerpo_total_m2=A_cuerpo_opaco,
        h_conv_W_m2K=h_conv,
        K_m_kg_m2s=K_m,
        coef_transporte_func=_coef_transporte,
        coef_pared_func=_coef_pared,
        k_aisl_W_mK=k_aisl,
        esp_cam_total_m=esp_cam_total,
        tau_cubierta_solar=tau_cub,
        alfa_producto_solar=alfa_prod,
        A_rad_total_m2=A_rad,
        R_cond_techo_m2K_W=R_cond_techo,
        A_techo_total_m2=A_techo,
        advertencias=advertencias,
        tasa_difusion_func=_tasa_difusion,
    )


def _calcular_termodinamico(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float,
    P_Pa: float,
    t_max_s: float = 24.0 * 3600.0,
    forzantes_aire: Optional["ForzantesAire"] = None,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
    T_set_aux_K: Optional[float] = None,
    Q_aux_max_W: float = 0.0,
) -> ResultadoMotorTermodinamico:
    """Wire-up de Camara → motor termodinámico transitorio.

    Lee del catálogo del producto:
        - propiedades_basicas.calor_especifico_seco → c_ps (sólido seco).
        - isoterma GAB vía `core.catalogo.isoterma_gab` (propia o por analogía,
          S70) → aw_func. Sin ninguna, a_w = 1 hasta humedad_equilibrio_aire_seco
          (agua libre, optimista) con advertencia CAM_TD_GAB_FALTA.

    Calcula:
        - A_prod y h_conv según la **topología de flujo** (S63): atravesado
          (vertical) → área de partícula ``a_v·V_lecho`` + Ranz-Marshall;
          over-flow (horizontal) → área de bandeja + placa plana con la
          velocidad del canal entre bandejas.
        - A_cuerpo = 2·(largo·alto + ancho·alto + largo·ancho).
        - K_m por Chilton-Colburn directo desde h_conv, en las dos topologías:
          K_m = h_conv/(cp_hum·Le^(2/3)).
        - Pared 3-nodos: deriva k_aisl desde U_muros del data model en
          condiciones de diseño (h_w McAdams a v_viento default).

    Si forzantes_aire se provee (modo "real" o "sintético"), se usa tal cual
    y los escalares T_operacion_K, HR_operacion, T_amb_K se ignoran (sólo se
    usan para los cálculos de h_conv/K_m de referencia y la decomposición de
    pared). Si no se provee, se arman forzantes degeneradas (2 puntos
    constantes) reproduciendo el comportamiento histórico.

    Si T_prod_inicial_K es None en CargaProducto, usa T_amb_K como fallback.
    """
    pr = _construir_params_termodinamico(
        camara,
        T_operacion_K,
        HR_operacion,
        T_amb_K,
        P_Pa,
        factor_h_conv=factor_h_conv,
        factor_K_m=factor_K_m,
    )
    advertencias = pr.advertencias

    # --- Forzantes: usar las del llamador o construir degeneradas ---
    if forzantes_aire is None:
        _V_VIENTO_DEFAULT_MS = 2.0
        omega_ent = humedad_absoluta(HR_operacion, T_operacion_K, P_Pa)
        t_forz = np.array([0.0, t_max_s], dtype=float)
        forzantes_uso = ForzantesAire(
            t_s=t_forz,
            T_ent_K=np.full(2, T_operacion_K),
            omega_ent=np.full(2, omega_ent),
            m_dot_aire_seco_kg_s=np.full(2, camara.flujo.caudal_masico_kg_s),
            T_amb_K=np.full(2, T_amb_K),
            v_viento_ms=np.full(2, _V_VIENTO_DEFAULT_MS),
            Q_aux_max_W=np.full(2, Q_aux_max_W),
        )
    else:
        # Con forzantes del llamador manda la SERIE (trae la máscara horaria del
        # auxiliar); el escalar es solo para el modo Constantes, que no la tiene.
        forzantes_uso = forzantes_aire

    # --- Integración termodinámica ---
    res = simular_secado(
        T_prod_inicial_K=pr.T_prod_inicial_K,
        X_prod_inicial_kg_kg=pr.X_inicial,
        X_prod_objetivo_kg_kg=pr.X_objetivo,
        m_seco_prod_kg=pr.m_seco_total_kg,
        c_ps_J_kgK=pr.cp_seco,
        forzantes=forzantes_uso,
        A_prod_m2=pr.A_prod_total_m2,
        A_cuerpo_m2=pr.A_cuerpo_total_m2,
        h_conv_W_m2K=pr.h_conv_W_m2K,
        K_m_kg_m2s=pr.K_m_kg_m2s,
        k_aisl_W_mK=pr.k_aisl_W_mK,
        esp_cam_m=pr.esp_cam_total_m,
        P_Pa=P_Pa,
        aw_func=pr.aw_func,
        coef_transporte_func=pr.coef_transporte_func,
        coef_pared_func=pr.coef_pared_func,
        tasa_difusion_func=pr.tasa_difusion_func,
        tau_cubierta_solar=pr.tau_cubierta_solar,
        alfa_producto_solar=pr.alfa_producto_solar,
        A_rad_m2=pr.A_rad_total_m2,
        R_cond_techo_m2K_W=pr.R_cond_techo_m2K_W,
        A_techo_m2=pr.A_techo_total_m2,
        T_set_aux_K=T_set_aux_K,
        n_etapas_aire=pr.n_etapas_aire,
        t_max_s=t_max_s,
    )

    # Anexar advertencias del wire-up a las del motor.
    #
    # `replace` y NO una reconstrucción campo por campo: enumerar los campos deja
    # afuera —en su default vacío— todo campo nuevo que se agregue al resultado, y
    # es un olvido silencioso. Ya había pasado: `Q_rad_aire_W` y
    # `energia_rad_aire_total_J` (S44) se perdían acá, así que la radiación al aire
    # entraba al balance pero no llegaba a los diagnósticos. Mismo patrón que el
    # albedo de S36 en la UI.
    HR_seco = _HR_aire_sin_evaporacion(res, forzantes_uso, P_Pa)
    X_eq = humedad_equilibrio_alcanzable(pr.aw_func, HR_seco)
    if X_eq is not None and res.status == "t_max_alcanzado" and pr.X_objetivo < X_eq:
        advertencias.append(
            f"CAM_TD_X_OBJ_BAJO_EQUILIBRIO: X_obj = {pr.X_objetivo:.3f} kg/kg ms está por "
            f"debajo de la humedad de equilibrio con el aire más seco que pudo tener la "
            f"cámara (HR {float(np.nanmin(HR_seco)) * 100:.0f} %): X_eq = {X_eq:.3f} "
            "kg/kg ms. El objetivo es inalcanzable con este aire, sin importar el horizonte: "
            "subir el X_obj, o calentar/secar más el aire (colector, auxiliar)."
        )
    return replace(
        res,
        advertencias=advertencias + list(res.advertencias),
        X_equilibrio_kg_kg=X_eq,
    )


def _HR_aire_sin_evaporacion(res, forzantes: "ForzantesAire", P_Pa: float) -> np.ndarray:
    """HR del aire de la cámara si el producto ya no aportara humedad (S70).

    Es el aire **más seco** que el producto puede llegar a ver: la ω de entrada a
    la temperatura de la cámara (``max(T_flujo, T_ent)``, que ya incluye colector,
    auxiliar y radiación). No se usa ``HR_flujo`` porque, si la corrida termina
    con el producto húmedo, ese aire nunca se secó y el equilibrio quedaría
    sobrestimado: diría "inalcanzable" cuando solo faltaba tiempo.
    """
    t = np.asarray(res.t_array_s, dtype=float)
    if t.size == 0 or len(res.T_flujo_K) != t.size:
        return np.array([])
    t_fz = np.asarray(forzantes.t_s, dtype=float)
    omega = np.interp(t, t_fz, np.asarray(forzantes.omega_ent, dtype=float))
    T_ent = np.interp(t, t_fz, np.asarray(forzantes.T_ent_K, dtype=float))
    T = np.maximum(np.asarray(res.T_flujo_K, dtype=float), T_ent)
    return np.array([HR_desde_omega(w, Ti, P_Pa) for w, Ti in zip(omega, T)])


def humedad_equilibrio_alcanzable(
    aw_func: Callable[[float], float], HR_flujo: np.ndarray
) -> Optional[float]:
    """Humedad de equilibrio del producto con el aire más seco de la corrida (S70).

    El producto no puede bajar de la humedad cuya ``a_w`` iguala la HR del aire que
    lo rodea: ``a_w(X_eq) = HR``. Se toma la **mínima** HR de la serie (el
    llamador pasa la del aire sin la humedad del propio producto, ver
    ``_HR_aire_sin_evaporacion``), así que ``X_eq`` es la humedad más baja que
    la corrida pudo alcanzar, y un ``X_obj`` por debajo es inalcanzable. Se invierte el **mismo** ``aw_func`` que
    usa el motor (GAB propia, por analogía, o la reserva lineal sin isoterma), así
    que el valor es coherente con lo que simula.

    Args:
        aw_func: Isoterma X → a_w del motor (monótona creciente).
        HR_flujo: Serie de HR del aire que ve el producto [fracción 0-1].

    Returns:
        ``X_eq`` [kg/kg ms], o None si no hay serie de HR válida.
    """
    hr = np.asarray(HR_flujo, dtype=float)
    hr = hr[np.isfinite(hr)]
    if hr.size == 0:
        return None
    HR_min = float(np.clip(hr.min(), 1e-6, 0.999))

    def _f(X: float) -> float:
        return max(0.0, min(1.0, aw_func(X))) - HR_min

    X_max = 50.0
    if _f(X_max) <= 0.0:
        return None
    return float(brentq(_f, 1e-9, X_max, xtol=1e-6))


@dataclass(frozen=True)
class DiagnosticoTransferencia:
    """Cuán bien acoplados están el aire y el producto, en el punto de diseño.

    Atributos:
        A_prod_m2: Superficie de transferencia efectiva [m²] — las dos caras de
            la bandeja, con la inferior gateada por la malla.
        h_conv_W_m2K: Coeficiente convectivo aire↔producto [W/(m²·K)].
        K_m_kg_m2s: Conductancia másica [kg/(m²·s)].
        NTU: ``K_m·A_prod/ṁ_as`` — número de unidades de transferencia. Es **el**
            número que dice si el secador está bien cargado: mide cuánto camino
            hacia el equilibrio con el producto puede recorrer el aire en su
            pasada. Con NTU ≪ 1 el aire sale casi como entró y el secador está
            limitado por transferencia; con NTU ≳ 3 sale prácticamente saturado
            y pasa a estar limitado por energía, que es donde conviene estar.
        acercamiento_equilibrio: Fracción del camino al equilibrio que recorre
            el aire. Se evalúa con la **misma cadena de N etapas** que integra el
            motor, ``1 − (1 + NTU/N)^(−N)``, y no con el ``NTU/(1+NTU)`` del CSTR:
            el diagnóstico tiene que describir el modelo que después simula. A
            NTU = 2 son 83 % contra 67 %.
    """

    A_prod_m2: float
    h_conv_W_m2K: float
    K_m_kg_m2s: float
    NTU: float
    acercamiento_equilibrio: float


def diagnostico_transferencia(
    camara: "Camara",
    *,
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float,
    P_Pa: float = 101325.0,
) -> DiagnosticoTransferencia:
    """Diagnóstico de transferencia de la cámara en el punto de diseño (S63).

    No integra el secado: arma los mismos parámetros que usaría el motor y
    devuelve el NTU resultante. Sirve para que la UI muestre, mientras se diseña
    la cámara, si el aire y el producto están acoplados o no — que hasta S63 no
    se veía en ninguna vista, y era justo lo que estaba mal.

    Args:
        camara: Cámara configurada.
        T_operacion_K: Temperatura del aire de referencia [K].
        HR_operacion: Humedad relativa del aire de referencia [fracción 0–1].
        T_amb_K: Temperatura ambiente [K].
        P_Pa: Presión total [Pa].

    Returns:
        ``DiagnosticoTransferencia``.
    """
    pr = _construir_params_termodinamico(
        camara,
        T_operacion_K=T_operacion_K,
        HR_operacion=HR_operacion,
        T_amb_K=T_amb_K,
        P_Pa=P_Pa,
    )
    m_dot = camara.flujo.caudal_masico_kg_s
    NTU = pr.K_m_kg_m2s * pr.A_prod_total_m2 / m_dot if m_dot > 0.0 else 0.0
    N = max(1, pr.n_etapas_aire)
    return DiagnosticoTransferencia(
        A_prod_m2=pr.A_prod_total_m2,
        h_conv_W_m2K=pr.h_conv_W_m2K,
        K_m_kg_m2s=pr.K_m_kg_m2s,
        NTU=NTU,
        acercamiento_equilibrio=(1.0 - (1.0 + NTU / N) ** (-N) if NTU > 0.0 else 0.0),
    )


def estimar_T_flujo_estacionario(
    camara: "Camara",
    T_ent_K: float,
    HR_ent: float,
    m_dot_as_kg_s: float,
    T_amb_K: float,
    P_Pa: float = 101325.0,
    v_viento_ms: float = 2.0,
    I_g_W_m2: float = 0.0,
    Q_aux_max_W: float = 0.0,
    T_set_aux_K: Optional[float] = None,
) -> float:
    """Temperatura del aire dentro de la cámara en régimen, sin integrar [K].

    Resuelve **una sola vez** el sistema algebraico del CSTR
    (``resolver_estado_camara``) con el producto en su estado inicial, en vez de
    integrar el secado completo. Es O(1) y devuelve exactamente la cantidad que
    gobierna el empuje del tiro térmico: la temperatura del aire **interior**.

    Existe para el lazo de convección natural (S61). El motor de flotabilidad
    necesita ``T_flujo`` en cada iteración de Picard, y para un cajón sin
    colector el balance no tenía de dónde sacarla: usaba la heurística fija
    ``T_amb + 25 K``, que no depende del caudal y por lo tanto **congelaba el
    lazo** (convergía trivialmente en una iteración, con un empuje inventado).

    Es una estimación de punto de diseño, no un resultado: toma el producto
    recién cargado (``T_prod_inicial``, ``X_inicial``), que es cuando el
    enfriamiento evaporativo es máximo, así que subestima ``T_flujo`` —y con él
    el tiro— a medida que el producto se seca. Conservador para prediseño.

    Args:
        camara: Cámara configurada.
        T_ent_K: Temperatura del aire que entra [K].
        HR_ent: Humedad relativa del aire que entra [fracción 0–1].
        m_dot_as_kg_s: Caudal másico de aire seco [kg/s].
        T_amb_K: Temperatura ambiente exterior [K].
        P_Pa: Presión total [Pa].
        v_viento_ms: Viento a 2 m [m/s], para el film exterior McAdams.
        I_g_W_m2: Irradiancia sobre las caras translúcidas [W/m²]. Alimenta el
            término radiativo al producto cuando la cámara tiene techo/caras
            translúcidas; 0 = cámara opaca o sin sol.

    Returns:
        ``T_flujo`` [K]. Si el caudal no es positivo devuelve ``T_ent_K``.
    """
    if m_dot_as_kg_s <= 0:
        return T_ent_K
    pr = _construir_params_termodinamico(camara, T_ent_K, HR_ent, T_amb_K, P_Pa)
    omega_ent = humedad_absoluta(HR_ent, T_ent_K, P_Pa)
    h_w = 5.7 + 3.8 * max(v_viento_ms, 0.0)  # McAdams (ADR-006: v a 2 m, sin corregir)
    h_conv, K_m = pr.coef_transporte_func(T_ent_K, pr.T_prod_inicial_K, omega_ent, m_dot_as_kg_s)
    h_pared = pr.coef_pared_func(T_ent_K, T_amb_K, m_dot_as_kg_s, h_w)
    # Radiación transmitida que intercepta el PRODUCTO (no el aire: ver
    # docs/notas/cubiertas translucidas en camara de secado.md).
    Q_rad_W = I_g_W_m2 * pr.tau_cubierta_solar * pr.alfa_producto_solar * pr.A_rad_total_m2

    def _estado(T_prod_K: float, h_pared_override: Optional[float] = None):
        # Misma cadena de sub-etapas que el motor (S63): esta estimación
        # alimenta el empuje del tiro térmico, y con un CSTR único daba una
        # T_flujo distinta de la que después calcula la simulación.
        return resolver_cadena_camara(
            n_etapas=pr.n_etapas_aire,
            T_prod_K=T_prod_K,
            X_prod_kg_kg=pr.X_inicial,
            T_ent_K=T_ent_K,
            omega_ent_kg_kg=omega_ent,
            A_prod_m2=pr.A_prod_total_m2,
            A_cuerpo_m2=pr.A_cuerpo_total_m2,
            m_dot_as_kg_s=m_dot_as_kg_s,
            h_conv_W_m2K=h_conv,
            K_m_kg_m2s=K_m,
            h_w_W_m2K=h_w,
            k_aisl_W_mK=pr.k_aisl_W_mK,
            esp_cam_m=pr.esp_cam_total_m,
            T_amb_K=T_amb_K,
            P_Pa=P_Pa,
            aw_func=pr.aw_func,
            R_cond_techo_m2K_W=pr.R_cond_techo_m2K_W,
            A_techo_m2=pr.A_techo_total_m2,
            h_conv_pared_W_m2K=(h_pared if h_pared_override is None else h_pared_override),
            Q_aux_max_W=Q_aux_max_W,
            T_set_aux_K=T_set_aux_K,
        )

    # Estado estacionario del producto: el mismo balance de la EDO con
    # dT_prod/dt = 0  ⇒  q_prod + Q_rad − ṁ_w·L_v = 0. Es monótono decreciente
    # en T_prod (más caliente ⇒ menos calor recibido y más evaporación), así
    # que la raíz es única. Sin esto habría que suponer T_prod, y en una caja
    # translúcida —donde el aire entra a T_amb y **todo** el calor llega por el
    # producto insolado— cualquier suposición decide sola el resultado.
    def _residuo_prod(T_prod_K: float) -> float:
        est = _estado(T_prod_K)
        L_v = calor_latente_vaporizacion(min(373.0, max(250.0, T_prod_K)))
        return est.q_prod_W + Q_rad_W - est.m_dot_w_kg_s * L_v

    T_lo = min(T_amb_K, T_ent_K) - 5.0
    T_hi = max(T_amb_K, T_ent_K) + 90.0
    try:
        if _residuo_prod(T_lo) <= 0.0:
            T_prod_eq = T_lo
        elif _residuo_prod(T_hi) >= 0.0:
            T_prod_eq = T_hi
        else:
            T_prod_eq = float(brentq(_residuo_prod, T_lo, T_hi, xtol=1e-3, rtol=1e-6))
    except (ValueError, ZeroDivisionError):
        # Sin raíz utilizable, caemos al producto recién cargado (frío): es la
        # cota conservadora, subestima el tiro.
        T_prod_eq = pr.T_prod_inicial_K
    # Segunda pasada con el film de pared recalculado sobre la T de aire ya
    # estimada: `h_pared` se computó arriba con `T_ent_K`, que en una CAJA es la
    # ambiente y da ΔT = 0 (ver el comentario en `simular_secado._resolver`).
    # Acá importa doblemente, porque esta función alimenta el empuje del tiro.
    est_1 = _estado(T_prod_eq)
    h_pared_2 = pr.coef_pared_func(est_1.T_flujo_K, T_amb_K, m_dot_as_kg_s, h_w)
    return float(_estado(T_prod_eq, h_pared_override=h_pared_2).T_flujo_K)


def calcular_camara(
    camara: "Camara",
    T_operacion_K: float,
    HR_operacion: float,
    T_amb_K: float = 298.15,
    P_Pa: float = 101325.0,
    t_max_s: float = 72.0 * 3600.0,
    forzantes_aire: Optional["ForzantesAire"] = None,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
    T_set_aux_K: Optional[float] = None,
    Q_aux_max_W: float = 0.0,
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
        factor_h_conv: Multiplicador del coeficiente convectivo interior (1.0 =
            sin cambios). Perilla de **calibración** contra datos medidos.
        factor_K_m: Multiplicador adicional del coeficiente de transferencia de
            masa (1.0 = sin cambios). Es la perilla principal para calibrar la
            velocidad de secado; ver `calculos/validacion_camara.py`.
        T_set_aux_K: Objetivo de control del auxiliar en modo respaldo [K].
            ``None`` → potencia constante. El **techo** de potencia no viaja
            acá sino como serie en ``forzantes_aire.Q_aux_max_W``, porque
            depende de la hora (calendario de arranque, disponibilidad
            nocturna) y esa lógica vive en ``calculos/auxiliar_calc.py``.

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
        factor_h_conv=factor_h_conv,
        factor_K_m=factor_K_m,
        T_set_aux_K=T_set_aux_K,
        Q_aux_max_W=Q_aux_max_W,
    )


def calcular_camara_cascada(
    camara: "Camara",
    *,
    T_operacion_K: float,
    HR_operacion: float,
    forzantes_aire: "ForzantesAire",
    T_amb_K: float = 298.15,
    P_Pa: float = 101325.0,
    n_avances: Optional[int] = None,
    factor_h_conv: float = 1.0,
    factor_K_m: float = 1.0,
) -> ResultadoCascada:
    """Punto de entrada de la cámara semicontinua (túnel a contracorriente).

    Wire-up de ``Camara`` (+ ``Camara.tunel``) al motor
    ``camara_termodinamica.simular_cascada``. La geometría total de la cámara y
    la carga total de producto se reparten en ``tunel.n_zonas`` columnas iguales.
    Reusa el mismo armado de parámetros que el batch (``_construir_params_*``):
    propiedades del producto, isoterma GAB, coeficientes de transporte (closure
    variable en t) y decomposición de pared.

    Args:
        camara: Camara con ``camara.tunel`` configurado (ConfiguracionTunel).
        T_operacion_K, HR_operacion: Aire de referencia para h_conv/K_m y la
            T inicial del producto (típicamente las medias de las forzantes).
        forzantes_aire: Serie horaria del aire que entra a la zona seca (salida
            del colector/auxiliar) sobre toda la ventana.
        T_amb_K, P_Pa: Ambiente y presión.
        n_avances: Avances a simular. None → se derivan del horizonte de las
            forzantes (floor(t_max / intervalo_avance)).
        factor_h_conv, factor_K_m: Perillas de calibración de los coeficientes de
            transporte interiores (1.0 = sin cambios). Ver ``calcular_camara``.

    Returns:
        ResultadoCascada (sequedad emergente, throughput, perfil espacial...).

    Raises:
        ValueError: Si ``camara.tunel is None``.
    """
    if camara.tunel is None:
        raise ValueError(
            "CAM_CASCADA_SIN_TUNEL: el subtipo semicontinuo requiere "
            "camara.tunel (ConfiguracionTunel) configurado."
        )
    tun = camara.tunel
    pr = _construir_params_termodinamico(
        camara,
        T_operacion_K,
        HR_operacion,
        T_amb_K,
        P_Pa,
        factor_h_conv=factor_h_conv,
        factor_K_m=factor_K_m,
    )
    N = tun.n_zonas

    res = simular_cascada(
        n_zonas=N,
        intervalo_avance_s=tun.intervalo_avance_s,
        n_avances=n_avances,
        T_prod_inicial_K=pr.T_prod_inicial_K,
        X_prod_inicial_kg_kg=pr.X_inicial,
        X_prod_objetivo_kg_kg=pr.X_objetivo,
        m_seco_por_zona_kg=pr.m_seco_total_kg / N,
        c_ps_J_kgK=pr.cp_seco,
        forzantes=forzantes_aire,
        A_prod_por_zona_m2=pr.A_prod_total_m2 / N,
        A_cuerpo_por_zona_m2=pr.A_cuerpo_total_m2 / N,
        h_conv_W_m2K=pr.h_conv_W_m2K,
        K_m_kg_m2s=pr.K_m_kg_m2s,
        k_aisl_W_mK=pr.k_aisl_W_mK,
        esp_cam_m=pr.esp_cam_total_m,
        P_Pa=P_Pa,
        aw_func=pr.aw_func,
        coef_transporte_func=pr.coef_transporte_func,
        coef_pared_func=pr.coef_pared_func,
        tasa_difusion_func=pr.tasa_difusion_func,
        tau_cubierta_solar=pr.tau_cubierta_solar,
        alfa_producto_solar=pr.alfa_producto_solar,
        A_rad_por_zona_m2=pr.A_rad_total_m2 / N,
        R_cond_techo_m2K_W=pr.R_cond_techo_m2K_W,
        A_techo_por_zona_m2=pr.A_techo_total_m2 / N,
    )
    if pr.advertencias:
        res = replace(res, advertencias=pr.advertencias + list(res.advertencias))
    return res
