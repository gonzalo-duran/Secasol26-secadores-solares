"""Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.

Modelo cuasi-estacionario unidimensional. La chimenea induce flujo natural
por diferencia de densidad entre la columna de aire caliente (cámara + chimenea)
y la atmósfera circundante. El caudal de equilibrio se obtiene cuando el tiro
disponible iguala las pérdidas totales del lazo.

Fenómenos modelados:
- Tiro térmico (stack effect): ΔP_tiro = g·H_eff·(ρ_amb − ρ_chim).
- Fricción en el ducto de chimenea: Darcy-Weisbach con Haaland.
- Pérdidas singulares de entrada y salida (K bundleado por defecto = 1.5).
- Extractor eólico opcional en el tope (turbina sombrero chino): agrega un
  término motriz ΔP = Cp·ρ_amb·v_viento²/2 al balance, donde v_viento se
  corrige de la altura del contrato de `Clima` (2 m, ver `perfil_viento`) a la
  altura del tope via perfil logarítmico. La turbina también introduce una
  resistencia adicional al flujo Kt·ρ_chim·v_extractor²/2.

Convención termodinámica:
- T_chim es la temperatura promedio de la columna ascendente (cámara + chimenea).
- Para prediseño se recomienda T_chim ≈ T_salida_camara (el aire ya pasó por
  el enfriamiento evaporativo en la cámara), no T_salida_colector.
- H_eff = altura_chimenea + altura útil de la cámara (entrada de aire frío
  en la base, salida por la chimenea superior).

API pública:
- `delta_P_tiro_Pa`: tiro térmico disponible.
- `delta_P_turbina_motriz_Pa`: depresión motriz del extractor eólico.
- `delta_P_chimenea_Pa`: pérdida en el ducto (fricción + singulares + turbina).
- `caudal_natural_kgs`: caudal másico de equilibrio del lazo completo.

El módulo es puro: no depende de `core/` ni de `streamlit`. Toma primitivas
para mantenerse testeable y reusable desde cualquier capa.
"""

from __future__ import annotations

from math import pi
from typing import Optional

from scipy.optimize import brentq

# _factor_friccion_haaland es interno a motor_calc pero esta es la misma
# implementación que necesitamos; reusarla evita duplicar código y mantiene
# coherencia con las pérdidas del colector y de la cámara.
from calculos.motor_calc import (
    _factor_friccion_haaland as _haaland,
)
from calculos.motor_calc import (
    densidad_aire,
    viscosidad_aire,
)
from calculos.perfil_viento import Z0_DEFAULT_M, Z_CONTRATO_M, velocidad_a_altura

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_G_MS2: float = 9.81

# Rugosidad típica para chapa galvanizada (~0.15 mm). Cubre la mayoría de las
# chimeneas de secadores solares (galvanizada, acero pintado). Usuarios con
# materiales distintos pueden pasar el valor explícito.
_RUGOSIDAD_DEFAULT_M: float = 1.5e-4

# Coeficiente de pérdidas singulares por defecto: K_entrada (~0.5, contracción
# suave desde cámara) + K_salida (1.0, descarga a la atmósfera) = 1.5.
_K_SINGULAR_DEFAULT: float = 1.5

# Coeficientes de pérdida de las bocas de la cámara (secador pasivo sin
# chimenea). Son los mismos dos términos que bundlea _K_SINGULAR_DEFAULT, acá
# separados porque cada boca tiene su propia área. Constantes internas: el
# usuario carga áreas, que es el dato que conoce de su equipo.
_K_BOCA_ENTRADA: float = 0.5  # contracción de canto vivo desde ambiente en reposo
_K_BOCA_SALIDA: float = 1.0  # descarga del chorro a la atmósfera
# Variantes según lo que haya del otro lado de la boca (ver coeficientes_bocas):
_K_BOCA_ENTRADA_DUCTEADA: float = 0.3  # expansión ducto de colector → cámara
_K_BOCA_SALIDA_A_DUCTO: float = 0.5  # contracción cámara → base de chimenea
# Término de entrada que trae bundleado _K_SINGULAR_DEFAULT. Cuando la boca de
# salida está definida, esa entrada la aporta la boca (sobre su área real) y hay
# que descontarla de la chimenea para no contarla dos veces.
_K_ENTRADA_EN_SINGULAR_CHIM: float = 0.5

# Bracket para brentq al buscar el caudal de equilibrio. Cubre desde flujo
# imperceptible (1e-8 kg/s ≈ 0.01 g/s) hasta caudales de chimeneas grandes
# (10 kg/s ≈ 36 000 m³/h). Si el problema cae fuera, brentq lanza ValueError.
_M_MIN_KGS: float = 1.0e-8
_M_MAX_KGS: float = 10.0

# Altura de referencia del viento de entrada [m]. Es la del contrato de `Clima`
# (`WS_ms` a 2 m, nativo de NASA POWER WS2M y altura a la que la ingesta normaliza
# las series medidas), NO el estándar meteorológico de 10 m. Hasta S57 este módulo
# asumía 10 m y recibía el viento de 2 m sin convertir, lo que subestimaba la
# velocidad en el tope por el factor ln(2/z₀)/ln(10/z₀) ≈ 0.70 y el término motriz
# del extractor —que va con v²— a la mitad.
_Z_REF_VIENTO_M: float = Z_CONTRATO_M


# ---------------------------------------------------------------------------
# Perfil logarítmico de viento (capa límite atmosférica)
# ---------------------------------------------------------------------------


def _v_viento_a_altura(v_ref_ms: float, z_m: float, z0_m: float = Z0_DEFAULT_M) -> float:
    """Corrige el viento del contrato (2 m) a una altura ``z``.

    Envoltorio delgado sobre :func:`calculos.perfil_viento.velocidad_a_altura` que
    fija la altura de origen en la del contrato de ``Clima``. Se conserva como
    función propia porque la UI de P6 la importa para el preview del extractor.

    Args:
        v_ref_ms: Velocidad del viento a :data:`_Z_REF_VIENTO_M` sobre el suelo
            [m/s] — el campo ``Clima.WS_ms``.
        z_m: Altura de interés [m] (tope de la chimenea).
        z0_m: Longitud de rugosidad aerodinámica del terreno [m]. Valores
            típicos: 0.001 (mar/lago), 0.03 (campo abierto/cultivo bajo),
            0.05 (rural medio, default), 0.10-0.25 (suburbano), 0.5-1.0
            (urbano denso, árboles altos).

    Returns:
        v(z) [m/s]. Devuelve 0 si v_ref_ms ≤ 0 o z ≤ z0 (dentro de la capa
        de rugosidad, sin viento útil).
    """
    if z0_m <= 0 or _Z_REF_VIENTO_M <= z0_m:
        return 0.0
    return velocidad_a_altura(v_ref_ms, z_m, z_origen_m=_Z_REF_VIENTO_M, z0_m=z0_m)


# ---------------------------------------------------------------------------
# Tiro térmico (driving force)
# ---------------------------------------------------------------------------


def delta_P_tiro_Pa(
    T_amb_K: float,
    T_chim_K: float,
    H_eff_m: float,
    P_amb_Pa: float = 101325.0,
) -> float:
    """Tiro térmico disponible en la base de la chimenea [Pa].

    Formula de empuje hidrostático para columnas de aire a P común:

        ΔP_tiro = g · H_eff · (ρ_amb − ρ_chim)

    Con gas ideal a P común: ρ ∝ 1/T, así que ΔP_tiro > 0 cuando T_chim > T_amb
    (flujo ascendente en la chimenea) y ΔP_tiro < 0 cuando T_chim < T_amb
    (contraflujo, ej. de noche o con sombras).

    Args:
        T_amb_K: Temperatura del aire ambiente [K].
        T_chim_K: Temperatura promedio de la columna ascendente [K]. Para
            prediseño, usar T_salida_camara.
        H_eff_m: Altura efectiva de la columna [m]: altura de chimenea +
            altura útil de la cámara (desde la entrada de aire frío hasta la
            salida de la chimenea).
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        ΔP_tiro [Pa]. Positivo si la columna caliente es menos densa que el
        ambiente (caso normal de operación diurna).
    """
    if H_eff_m <= 0:
        return 0.0
    rho_amb = densidad_aire(T_amb_K, P_amb_Pa)
    rho_chim = densidad_aire(T_chim_K, P_amb_Pa)
    return _G_MS2 * H_eff_m * (rho_amb - rho_chim)


# ---------------------------------------------------------------------------
# Extractor eólico — término motriz
# ---------------------------------------------------------------------------


def delta_P_turbina_motriz_Pa(
    v_viento_local_ms: float,
    Cp_turbina: float,
    T_amb_K: float,
    P_amb_Pa: float = 101325.0,
) -> float:
    """Depresión motriz generada por un extractor eólico en su base [Pa].

    Modelo empírico de turbina pasiva tipo "sombrero chino": la rotación de
    los álabes inclinados por la presión dinámica del viento crea depresión
    en la base, succionando aire desde la chimenea hacia afuera.

        ΔP_turbina = Cp · ρ_amb · v_viento² / 2

    La densidad se evalúa a T_amb porque es el aire externo el que mueve la
    turbina (no la columna ascendente caliente).

    Args:
        v_viento_local_ms: Velocidad del viento a la altura del extractor,
            ya corregida por perfil logarítmico desde los 2 m del contrato [m/s].
        Cp_turbina: Coeficiente de presión motriz [adim]. Típico 0.3-0.6
            para turbinas comerciales tipo sombrero chino.
        T_amb_K: Temperatura ambiente [K].
        P_amb_Pa: Presión ambiente [Pa].

    Returns:
        ΔP_turbina [Pa]. Cero si v_viento o Cp son ≤ 0.
    """
    if v_viento_local_ms <= 0 or Cp_turbina <= 0:
        return 0.0
    rho_amb = densidad_aire(T_amb_K, P_amb_Pa)
    return Cp_turbina * rho_amb * v_viento_local_ms**2 / 2.0


# ---------------------------------------------------------------------------
# Pérdida de carga del ducto de chimenea
# ---------------------------------------------------------------------------


def delta_P_chimenea_Pa(
    m_punto_kgs: float,
    T_chim_K: float,
    diametro_m: float,
    altura_m: float,
    P_amb_Pa: float = 101325.0,
    rugosidad_m: float = _RUGOSIDAD_DEFAULT_M,
    K_singular: float = _K_SINGULAR_DEFAULT,
    Kt_turbina: float = 0.0,
    diametro_extractor_m: Optional[float] = None,
) -> float:
    """Pérdida de carga en el ducto de chimenea [Pa].

    Incluye fricción (Darcy-Weisbach con Haaland), singulares de entrada+salida
    y, opcionalmente, la resistencia adicional de un extractor eólico montado
    en el tope:

        ΔP_chim   = (f · L/D + K_singular) · ρ_chim · v² / 2
        ΔP_turb_K = Kt · ρ_chim · v_extractor² / 2
        v_extractor = ṁ / (ρ_chim · A_extractor)

    Total = ΔP_chim + ΔP_turb_K. Las propiedades del aire (ρ, μ) se evalúan a
    T_chim (temperatura local dentro de la columna).

    Args:
        m_punto_kgs: Caudal másico [kg/s].
        T_chim_K: Temperatura del aire en la chimenea [K].
        diametro_m: Diámetro interno de la chimenea [m].
        altura_m: Largo del ducto de chimenea [m].
        P_amb_Pa: Presión ambiente [Pa].
        rugosidad_m: Rugosidad absoluta de la pared interna [m]. Default
            1.5e-4 m (chapa galvanizada).
        K_singular: Coeficiente bundleado de pérdidas singulares
            (entrada + salida). Default 1.5 = 0.5 (contracción suave) +
            1.0 (descarga a atmósfera).
        Kt_turbina: Coeficiente resistivo del extractor eólico [adim]. 0
            (default) si no hay extractor.
        diametro_extractor_m: Diámetro del extractor [m]. None (default) si
            no hay extractor. Si está, se calcula v_extractor con su área.

    Returns:
        ΔP [Pa]. Siempre ≥ 0.
    """
    if m_punto_kgs <= 0 or diametro_m <= 0 or altura_m <= 0:
        return 0.0
    rho = densidad_aire(T_chim_K, P_amb_Pa)
    mu = viscosidad_aire(T_chim_K)
    A = pi * (diametro_m / 2.0) ** 2
    v = m_punto_kgs / (rho * A)
    Re = rho * v * diametro_m / mu
    eps_rel = rugosidad_m / diametro_m
    f = _haaland(Re, eps_rel)
    K_total = f * (altura_m / diametro_m) + K_singular
    dP_ducto = K_total * (rho * v**2) / 2.0

    # Resistencia del extractor (si aplica). Se aplica sobre la velocidad
    # del flujo a través del diámetro propio del extractor (que puede ser
    # mayor o menor que el de la chimenea).
    dP_turbina_K = 0.0
    if Kt_turbina > 0 and diametro_extractor_m is not None and diametro_extractor_m > 0:
        A_ext = pi * (diametro_extractor_m / 2.0) ** 2
        v_ext = m_punto_kgs / (rho * A_ext)
        dP_turbina_K = Kt_turbina * (rho * v_ext**2) / 2.0

    return dP_ducto + dP_turbina_K


# ---------------------------------------------------------------------------
# Pérdida de carga de las bocas (secador pasivo sin chimenea)
# ---------------------------------------------------------------------------


def coeficientes_bocas(hay_colector: bool, hay_chimenea: bool) -> tuple[float, float]:
    """Coeficientes de pérdida de las bocas según la **topología** del secador.

    Las bocas de la cámara no son siempre la misma singularidad: lo que hay
    aguas arriba y aguas abajo cambia el coeficiente.

    **Entrada:**

    - Sin colector (caja): el aire viene del ambiente en reposo y se contrae al
      entrar por un borde vivo ⇒ ``K = 0.5``.
    - Con colector (armario): el aire llega **ducteado** desde la salida del
      colector y se expande dentro de la cámara ⇒ ``K = 0.3`` (transición tipo
      difusor, el mismo valor que usa la cadena forzada de
      ``motor_calc.estimar_delta_P_singulares``).

    **Salida:**

    - Sin chimenea: el chorro descarga a la atmósfera y pierde toda su energía
      cinética ⇒ ``K = 1.0``.
    - Con chimenea: la boca **no** descarga al ambiente, alimenta el ducto. La
      pérdida es la contracción de entrada al ducto (``K = 0.5``) y la descarga
      real ocurre en el tope de la chimenea, que ya la contabiliza
      ``K_singular_chim``. Usar 1.0 acá contaría dos veces la misma descarga.

    **Limitación conocida (S61):** se supone que las secciones **coinciden** en
    los dos acoples —salida de colector ↔ boca de entrada, y boca de salida ↔
    base de chimenea—. Cuando no coinciden hay una contracción/expansión extra
    que cambia la presión dinámica y que este modelo **no** representa; queda
    anotado como corrección futura (ver `docs/notas/estado_conveccion_natural_secasol.md`).

    Args:
        hay_colector: True si el aire entra a la cámara desde un colector.
        hay_chimenea: True si la salida de la cámara alimenta una chimenea.

    Returns:
        ``(K_in, K_out)`` [adim].
    """
    K_in = _K_BOCA_ENTRADA_DUCTEADA if hay_colector else _K_BOCA_ENTRADA
    K_out = _K_BOCA_SALIDA_A_DUCTO if hay_chimenea else _K_BOCA_SALIDA
    return (K_in, K_out)


def delta_P_bocas_Pa(
    m_punto_kgs: float,
    A_in_m2: Optional[float],
    A_out_m2: Optional[float],
    T_flujo_K: float,
    P_amb_Pa: float = 101325.0,
    K_in: float = _K_BOCA_ENTRADA,
    K_out: float = _K_BOCA_SALIDA,
) -> float:
    """Pérdida de carga en las bocas de entrada y salida de la cámara [Pa].

        ΔP_bocas = K_in·½·ρ·v_in²  +  K_out·½·ρ·v_out²
        v_in  = ṁ/(ρ·A_in)        v_out = ṁ/(ρ·A_out)

    Es la resistencia del lazo en un secador pasivo **sin chimenea** (un cajón
    o armario con aberturas): sin ella el equilibrio de flotabilidad no tiene
    solución acotada. Mismo rol que ``K_singular`` en el ducto de chimenea.

    La densidad se evalúa a ``T_flujo`` para las dos bocas. Es una
    simplificación —el aire entra a T_amb y sale a T_flujo—, coherente con el
    supuesto de un solo nodo (CSTR) del resto del modelo de cámara: el error
    queda en el orden del cociente de densidades (~10 % con ΔT = 30 K) y no
    cambia el orden de magnitud del caudal, que va con √(ΔP).

    Args:
        m_punto_kgs: Caudal másico [kg/s].
        A_in_m2: Área libre de la boca de entrada [m²]. None ⇒ sin bocas.
        A_out_m2: Área libre de la boca de salida [m²]. None ⇒ sin bocas.
        T_flujo_K: Temperatura del aire dentro de la cámara [K].
        P_amb_Pa: Presión ambiente [Pa].
        K_in: Coeficiente de pérdida de la entrada [adim]. Default 0.5
            (contracción de canto vivo).
        K_out: Coeficiente de pérdida de la salida [adim]. Default 1.0
            (pérdida de la energía cinética del chorro que descarga).

    Returns:
        ΔP [Pa]. 0 si no hay caudal o si falta alguna de las dos áreas.
    """
    if m_punto_kgs <= 0 or not A_in_m2 or not A_out_m2 or A_in_m2 <= 0 or A_out_m2 <= 0:
        return 0.0
    rho = densidad_aire(T_flujo_K, P_amb_Pa)
    v_in = m_punto_kgs / (rho * A_in_m2)
    v_out = m_punto_kgs / (rho * A_out_m2)
    return (K_in * v_in**2 + K_out * v_out**2) * rho / 2.0


# ---------------------------------------------------------------------------
# Caudal de equilibrio del lazo
# ---------------------------------------------------------------------------


def caudal_natural_kgs(
    T_amb_K: float,
    T_chim_K: float,
    diametro_chim_m: float,
    altura_chim_m: float,
    H_camara_m: float,
    delta_P_resto_fn,
    P_amb_Pa: float = 101325.0,
    rugosidad_m: float = _RUGOSIDAD_DEFAULT_M,
    K_singular_chim: float = _K_SINGULAR_DEFAULT,
    extractor_activo: bool = False,
    Cp_turbina: float = 0.0,
    Kt_turbina: float = 0.0,
    diametro_extractor_m: Optional[float] = None,
    z0_terreno_m: float = 0.05,
    v_viento_ref_ms: float = 0.0,
    A_boca_entrada_m2: Optional[float] = None,
    A_boca_salida_m2: Optional[float] = None,
    K_boca_entrada: float = _K_BOCA_ENTRADA,
    K_boca_salida: float = _K_BOCA_SALIDA,
) -> dict:
    """Caudal másico de equilibrio del lazo movido por flotabilidad [kg/s].

    Resuelve la ecuación de equilibrio motriz vs resistiva:

        ΔP_tiro_térmico + ΔP_turbina_motriz
            = ΔP_chimenea(ṁ) + ΔP_bocas(ṁ) + ΔP_resto(ṁ)

    donde:
        ΔP_chimenea = fricción + singulares + Kt·turbina (función de ṁ)
        ΔP_bocas    = entrada + salida de la cámara (función de ṁ)
        ΔP_resto    = colector + cámara + ductos + singulares (función de ṁ)

    **Sirve con o sin chimenea** (S61). Con `diametro_chim_m = altura_chim_m = 0`
    la columna de tiro es la propia cámara (`H_eff = H_camara_m`) y la
    resistencia son las bocas: es el secador pasivo tipo cajón, cuyo caudal
    hasta S60 se suponía constante. Con chimenea y sin bocas el resultado es
    idéntico al histórico.

    El término ΔP_turbina_motriz aparece sólo si ``extractor_activo``. La
    temperatura T_chim se toma como dato; el acoplamiento térmico completo
    (T_chim depende de ṁ) requiere iteración externa sobre esta función.

    Args:
        T_amb_K: Temperatura del aire ambiente [K].
        T_chim_K: Temperatura promedio de la columna ascendente [K].
            Recomendación: usar T_salida_camara. Sin chimenea es directamente
            la temperatura del aire dentro de la cámara.
        diametro_chim_m: Diámetro interno de la chimenea [m]. 0 = sin chimenea.
        altura_chim_m: Altura de la chimenea sobre la cámara [m]. 0 = sin chimenea.
        H_camara_m: Altura útil de la cámara (entrada-de-aire a base-de-chimenea) [m].
        delta_P_resto_fn: Callable ``f(m_punto_kgs) → ΔP [Pa]`` que devuelve
            la pérdida de carga del resto del lazo (todo excepto la propia
            chimenea). Debe ser monótona creciente y satisfacer f(0) = 0.
            En la práctica se construye con
            ``estimar_delta_P_colector + estimar_delta_P_camara + estimar_delta_P_singulares``.
        P_amb_Pa: Presión ambiente [Pa].
        rugosidad_m: Rugosidad de la chimenea [m].
        K_singular_chim: Pérdidas singulares de la chimenea (entrada+salida).
        extractor_activo: Si True, se modela un extractor eólico en el tope.
        Cp_turbina: Coeficiente de presión motriz del extractor [adim].
        Kt_turbina: Coeficiente resistivo del extractor [adim].
        diametro_extractor_m: Diámetro del extractor [m]. Obligatorio si
            ``extractor_activo``.
        z0_terreno_m: Rugosidad aerodinámica del terreno [m] para corregir
            v_viento por perfil logarítmico.
        v_viento_ref_ms: Velocidad del viento a la altura del contrato de
            ``Clima`` (2 m, ``WS_ms``) [m/s]. Se corrige internamente al tope.
        A_boca_entrada_m2: Área libre de la boca de entrada de la cámara [m²].
            None ⇒ sin resistencia de bocas (comportamiento histórico).
        A_boca_salida_m2: Área libre de la boca de salida [m²].
        K_boca_entrada, K_boca_salida: Coeficientes de pérdida de las bocas.
            Dependen de la topología — usar :func:`coeficientes_bocas`. Cuando
            la boca de salida está definida **y** hay chimenea, el término de
            entrada al ducto se descuenta de ``K_singular_chim``: lo aporta la
            boca sobre su área real, y sumarlo dos veces sería contar la misma
            transición en dos lugares.

    Returns:
        Dict con:
            - ``m_punto_kgs``: caudal másico de equilibrio.
            - ``v_chim_ms``: velocidad media en la chimenea (sin chimenea, la
              velocidad en la boca de salida).
            - ``delta_P_tiro_Pa``: tiro térmico disponible.
            - ``delta_P_turbina_motriz_Pa``: depresión motriz del extractor
              (0 si no hay extractor).
            - ``delta_P_chimenea_Pa``: pérdida en el ducto de chimenea
              (incluye Kt del extractor si aplica).
            - ``delta_P_bocas_Pa``: pérdida en las bocas de la cámara.
            - ``delta_P_resto_Pa``: pérdida en el resto del lazo.
            - ``Re_chimenea``: Reynolds en la chimenea.
            - ``H_eff_m``: altura efectiva usada.
            - ``v_viento_local_ms``: velocidad de viento corregida a la
              altura del tope (0 si no hay extractor).
            - ``advertencias``: lista de códigos.

    Raises:
        ValueError: Si el bracket de brentq no encierra la raíz (lazo muy
            restrictivo o caudal de equilibrio fuera de ``[_M_MIN_KGS, _M_MAX_KGS]``).
    """
    H_eff = altura_chim_m + H_camara_m
    dPT_termico = delta_P_tiro_Pa(T_amb_K, T_chim_K, H_eff, P_amb_Pa)
    advertencias: list[str] = []

    # Componente motriz del extractor (si aplica). El viento se evalúa a la
    # altura del tope de la chimenea = H_camara + altura_chim.
    if extractor_activo:
        z_top = H_camara_m + altura_chim_m
        v_loc = _v_viento_a_altura(v_viento_ref_ms, z_top, z0_terreno_m)
        dPT_turbina = delta_P_turbina_motriz_Pa(v_loc, Cp_turbina, T_amb_K, P_amb_Pa)
        Kt_eff = Kt_turbina
        d_ext_eff = diametro_extractor_m
    else:
        v_loc = 0.0
        dPT_turbina = 0.0
        Kt_eff = 0.0
        d_ext_eff = None

    dPT_total = dPT_termico + dPT_turbina

    # Caso sin tiro motriz: ni térmico ni eólico.
    if dPT_total <= 0.0:
        return {
            "m_punto_kgs": 0.0,
            "v_chim_ms": 0.0,
            "delta_P_tiro_Pa": dPT_termico,
            "delta_P_turbina_motriz_Pa": dPT_turbina,
            "delta_P_chimenea_Pa": 0.0,
            "delta_P_bocas_Pa": 0.0,
            "delta_P_resto_Pa": 0.0,
            "Re_chimenea": 0.0,
            "H_eff_m": H_eff,
            "v_viento_local_ms": v_loc,
            "advertencias": [
                "CHIM_SIN_TIRO: T_chim ≤ T_amb y sin viento útil — no hay flujo natural."
            ],
        }

    # La boca de salida se lleva la entrada al ducto: se descuenta del bundle de
    # singulares de la chimenea para no contar dos veces la misma transición.
    hay_ducto = diametro_chim_m > 0 and altura_chim_m > 0
    bocas_activas = bool(A_boca_entrada_m2 and A_boca_salida_m2)
    K_sing_chim_eff = (
        max(0.0, K_singular_chim - _K_ENTRADA_EN_SINGULAR_CHIM)
        if (hay_ducto and bocas_activas)
        else K_singular_chim
    )

    def _dP_bocas(m: float) -> float:
        return delta_P_bocas_Pa(
            m,
            A_boca_entrada_m2,
            A_boca_salida_m2,
            T_chim_K,
            P_amb_Pa,
            K_in=K_boca_entrada,
            K_out=K_boca_salida,
        )

    def residuo(m: float) -> float:
        dPC = delta_P_chimenea_Pa(
            m,
            T_chim_K,
            diametro_chim_m,
            altura_chim_m,
            P_amb_Pa,
            rugosidad_m,
            K_sing_chim_eff,
            Kt_turbina=Kt_eff,
            diametro_extractor_m=d_ext_eff,
        )
        dPR = float(delta_P_resto_fn(m))
        return dPT_total - dPC - _dP_bocas(m) - dPR

    if residuo(_M_MAX_KGS) > 0.0:
        # El lazo no ofrece resistencia suficiente para equilibrar el tiro
        # dentro del bracket. Pasa solo si no hay chimenea NI bocas NI ΔP_resto
        # (lazo idealmente abierto): el equilibrio sería infinito, no cero.
        raise ValueError(
            "CHIM_LAZO_SIN_RESISTENCIA: el tiro no se equilibra dentro de "
            f"{_M_MAX_KGS} kg/s. Un lazo por convección natural necesita al menos "
            "una resistencia (chimenea, bocas de la cámara o pérdidas del lecho)."
        )

    m_eq = brentq(residuo, _M_MIN_KGS, _M_MAX_KGS, xtol=1e-8, rtol=1e-6)

    rho_chim = densidad_aire(T_chim_K, P_amb_Pa)
    mu_chim = viscosidad_aire(T_chim_K)
    if diametro_chim_m > 0:
        A_chim = pi * (diametro_chim_m / 2.0) ** 2
        v_chim = m_eq / (rho_chim * A_chim)
        Re = rho_chim * v_chim * diametro_chim_m / mu_chim
    else:
        # Sin chimenea la velocidad representativa es la de la boca de salida
        # (es la sección por la que descarga el lazo). Sin ducto no hay Reynolds
        # de ducto que reportar.
        v_chim = (
            m_eq / (rho_chim * A_boca_salida_m2)
            if A_boca_salida_m2 and A_boca_salida_m2 > 0
            else 0.0
        )
        Re = 0.0
    dPC_eq = delta_P_chimenea_Pa(
        m_eq,
        T_chim_K,
        diametro_chim_m,
        altura_chim_m,
        P_amb_Pa,
        rugosidad_m,
        K_sing_chim_eff,
        Kt_turbina=Kt_eff,
        diametro_extractor_m=d_ext_eff,
    )
    dPR_eq = float(delta_P_resto_fn(m_eq))
    dPB_eq = _dP_bocas(m_eq)

    if diametro_chim_m > 0:
        if Re < 2300.0:
            advertencias.append("CHIM_FLUJO_LAMINAR: Re < 2300, fricción dominada por viscosidad.")
        if v_chim > 5.0:
            advertencias.append(
                f"CHIM_VEL_ALTA: v_chim = {v_chim:.2f} m/s > 5 m/s. "
                "Revisar diámetro o pérdidas singulares."
            )
    elif v_chim > 5.0:
        advertencias.append(
            f"NAT_VEL_BOCA_ALTA: v_salida = {v_chim:.2f} m/s > 5 m/s. "
            "Revisar el área de las bocas."
        )

    return {
        "m_punto_kgs": float(m_eq),
        "v_chim_ms": float(v_chim),
        "delta_P_tiro_Pa": float(dPT_termico),
        "delta_P_turbina_motriz_Pa": float(dPT_turbina),
        "delta_P_chimenea_Pa": float(dPC_eq),
        "delta_P_bocas_Pa": float(dPB_eq),
        "delta_P_resto_Pa": float(dPR_eq),
        "Re_chimenea": float(Re),
        "H_eff_m": float(H_eff),
        "v_viento_local_ms": float(v_loc),
        "advertencias": advertencias,
    }
