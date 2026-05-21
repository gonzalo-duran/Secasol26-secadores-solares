"""
Estimación de pérdidas de carga para el dimensionamiento del motor.

Provee funciones para calcular ΔP en el banco de colectores y en la cámara
de secado. Estos valores se usan como entrada al objeto Motor.

Modelos:
    Colector (canal rectangular) — Darcy-Weisbach:
        ΔP = f × (L/Dh) × (ρ × v²/2)
        Dh = 2·W·e / (W + e)    [diámetro hidráulico canal plano]
        f  = 64/Re               (laminar, Re < 2 300)
        f  = 0.316·Re^(-0.25)   (Blasius turbulento, 2 300 ≤ Re < 100 000)
        En banco serie: ΔP_rama = ΔP_unidad × n_serie
        En paralelo:   ΔP banco = ΔP rama

    Cámara — flujo HORIZONTAL:
        ΔP_cam = K_malla × (ρ · v_sup²/2) × n_bandejas
        v_sup = Q_vol / (ancho × alto)
        K_malla = 2.0 (malla de alambre, conservador)

    Cámara — flujo VERTICAL_ASCENDENTE:
        Por bandeja: ΔP = ΔP_malla + ΔP_lecho
        ΔP_malla = K_malla × (ρ · v₀²/2)
        ΔP_lecho = Ergun(v₀, ε, Φ_s, d_p, L)   [si d_p está definido]
        v₀ = Q_vol / area_bandeja

    Ergun (lecho empacado):
        ΔP/L = 150·μ·v₀·(1-ε)² / [(Φ_s·d_p)²·ε³]
             + 1.75·ρ·v₀²·(1-ε) / [(Φ_s·d_p)·ε³]

Propiedades del aire:
    ρ(T,P) = P / (R_aire · T)          [gas ideal, R_aire = 287.058 J/(kg·K)]
    μ(T)   = Sutherland (1893)         [válido 200–2 000 K, error < 2 %]
    P_atm(h) = ISA (atmósfera estándar, troposfera, h < 11 000 m)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from core import catalogo

if TYPE_CHECKING:
    from core.camara import Camara, ConfiguracionBandejas
    from core.colector import Colector

# ---------------------------------------------------------------------------
# Constantes físicas
# ---------------------------------------------------------------------------

_R_AIRE: float = 287.058  # J/(kg·K) — constante gas ideal aire seco
_MU_REF: float = 1.716e-5  # Pa·s     — viscosidad referencia Sutherland
_T_REF_MU: float = 273.11  # K        — temperatura referencia Sutherland
_S_SUTH: float = 110.4  # K        — constante Sutherland del aire

# Coeficientes K de resistencia para diferentes tipos de malla/bandeja
# (adimensional, aplicado sobre la presión dinámica ρ·v²/2 del aire que la
# atraviesa). Valores típicos de Idelchik / Crane TP-410, conservadores:
TIPOS_MALLA: dict[str, float] = {
    "alambre_fino": 2.0,  # malla mosquitera ≤ 1 mm, alta densidad
    "alambre_grueso": 1.0,  # malla galvanizada típica de bandeja (1.5–3 mm)
    "chapa_perforada_50pc": 3.5,  # chapa con 50 % de área abierta
    "chapa_perforada_30pc": 8.0,  # chapa con 30 % de área abierta (común en industrial)
    "tela_metalica_densa": 4.0,  # tela tejida fina, paso pequeño
}

# Default usado cuando ``bandejas.tipo_malla`` es None o no figura en TIPOS_MALLA.
# Cambiado de 2.0 (alambre fino) a 1.0 (alambre grueso) — más representativo
# de las bandejas de secador solar típicas. Pre-F2 era 2.0 (subestimación
# moderada para bandejas comunes, sobreestimación para mallas industriales).
K_MALLA: float = 1.0


def _K_malla_efectivo(tipo_malla: Optional[str]) -> float:
    """Devuelve el coeficiente K de la malla según el tipo.

    Lookup case-insensitive contra ``TIPOS_MALLA``; fallback a ``K_MALLA``
    (default) si el tipo no está registrado o es ``None``.
    """
    if tipo_malla is None:
        return K_MALLA
    return TIPOS_MALLA.get(tipo_malla, K_MALLA)


# Defaults conservadores para geometría de lecho cuando ni el usuario ni el
# catálogo del producto proveen valores. Valor genérico de "trozo de comida
# tamaño medio sobre bandeja" (~8 mm, lecho con huecos medios, no esférico).
_D_P_DEFAULT_M: float = 0.008
_EPSILON_DEFAULT: float = 0.45
_PHI_S_DEFAULT: float = 0.6

# Rugosidad por defecto del canal del colector si la placa absorbedora no
# trae ``rugosidad_m`` en el catálogo. Valor representativo para chapa
# metálica pintada (~50 µm), conservador.
_RUGOSIDAD_DEFAULT_M: float = 5.0e-5


def _factor_friccion_haaland(Re: float, eps_rel: float) -> float:
    """Factor de fricción de Darcy via correlación de Haaland (1983).

    Aproximación explícita de Colebrook-White, error < 2 % vs implícita:

        1/√f = -1.8 · log10[ (ε/(3.7·Dh))^1.11 + 6.9/Re ]

    Válida en régimen turbulento (Re > 4000). Para Re < 2300 (laminar) usar
    f = 64/Re. En el rango de transición 2300–4000 se mezcla linealmente.

    Args:
        Re: Reynolds del canal [adim].
        eps_rel: Rugosidad relativa ε/Dh [adim].

    Returns:
        Factor de fricción de Darcy f [adim].
    """
    if Re <= 0:
        return 0.0
    if Re < 2300.0:
        return 64.0 / Re
    import math

    inv_sqrt_f_turb = -1.8 * math.log10((eps_rel / 3.7) ** 1.11 + 6.9 / Re)
    f_turb = 1.0 / (inv_sqrt_f_turb**2)
    if Re < 4000.0:
        # Mezcla lineal en zona de transición
        f_lam = 64.0 / Re
        w = (Re - 2300.0) / (4000.0 - 2300.0)
        return f_lam * (1.0 - w) + f_turb * w
    return f_turb


def _geometria_lecho(
    bandejas: "ConfiguracionBandejas", producto_id: Optional[str] = None
) -> tuple[float, float, float]:
    """Resuelve (d_p, ε, Φ_s) del lecho con la cadena de prioridad:

    1. Si ``bandejas`` tiene el valor seteado explícitamente, usarlo.
    2. Si el producto tiene ``forma_geometrica`` en el catálogo, leerlo.
    3. Defaults conservadores (8 mm, 0.45, 0.6).

    Args:
        bandejas: ``ConfiguracionBandejas`` del usuario.
        producto_id: Identificador del producto para lookup en catálogo.
            ``None`` salta el paso 2.

    Returns:
        (d_p [m], ε [adim], Φ_s [adim]).
    """
    forma = {}
    if producto_id is not None:
        prod = catalogo.PRODUCTOS.get(producto_id) or {}
        forma = prod.get("forma_geometrica") or {}

    d_p = (
        bandejas.diametro_eq_particula_m
        if bandejas.diametro_eq_particula_m is not None
        else float(forma.get("diametro_eq_m", _D_P_DEFAULT_M))
    )
    # ε y Φ_s tienen defaults en ConfiguracionBandejas (0.45 y 0.6). Si el
    # usuario los dejó en default y el catálogo del producto trae otros,
    # priorizamos el catálogo (más informativo). Para que esto funcione,
    # comparamos con los defaults conocidos de la dataclass.
    if forma.get("porosidad_lecho") is not None and bandejas.porosidad_lecho == 0.45:
        eps = float(forma["porosidad_lecho"])
    else:
        eps = bandejas.porosidad_lecho
    if forma.get("esfericidad") is not None and bandejas.esfericidad == 0.60:
        phi_s = float(forma["esfericidad"])
    else:
        phi_s = bandejas.esfericidad
    return d_p, eps, phi_s


# ---------------------------------------------------------------------------
# Propiedades del aire en función de T y P
# ---------------------------------------------------------------------------


def presion_atmosferica(altitud_m: float) -> float:
    """Presión atmosférica estándar ISA en función de la altitud [Pa].

    P = 101 325 × (1 − 2.25577×10⁻⁵ · h)^5.25588

    Válida para h < 11 000 m (troposfera).

    Args:
        altitud_m: Altitud sobre el nivel del mar [m].

    Returns:
        P_atm [Pa].
    """
    return 101325.0 * (1.0 - 2.25577e-5 * altitud_m) ** 5.25588


def densidad_aire(T_K: float, P_Pa: float = 101325.0) -> float:
    """Densidad del aire seco via gas ideal [kg/m³].

    ρ = P / (R_aire · T)

    Args:
        T_K: Temperatura [K].
        P_Pa: Presión [Pa].

    Returns:
        ρ [kg/m³].
    """
    return P_Pa / (_R_AIRE * T_K)


def viscosidad_aire(T_K: float) -> float:
    """Viscosidad dinámica del aire via ley de Sutherland [Pa·s].

    μ = μ_ref × (T/T_ref)^1.5 × (T_ref + S) / (T + S)

    Válida para 200–2 000 K con error < 2 %.

    Args:
        T_K: Temperatura [K].

    Returns:
        μ [Pa·s].
    """
    return _MU_REF * (T_K / _T_REF_MU) ** 1.5 * (_T_REF_MU + _S_SUTH) / (T_K + _S_SUTH)


# ---------------------------------------------------------------------------
# Estimación ΔP colector
# ---------------------------------------------------------------------------


def _delta_P_canal_colector(
    ancho_m: float,
    alto_m: float,
    largo_total_m: float,
    v_ms: float,
    rugosidad_m: float,
    rho: float,
    mu: float,
) -> float:
    """ΔP friccional en un canal rectangular del colector via Haaland.

    Args:
        ancho_m: Ancho del canal [m].
        alto_m: Altura del canal [m].
        largo_total_m: Longitud total del camino (incluye módulos en serie) [m].
        v_ms: Velocidad superficial del aire [m/s].
        rugosidad_m: Rugosidad absoluta de la pared [m].
        rho, mu: Densidad y viscosidad del aire.

    Returns:
        ΔP del canal [Pa].
    """
    if ancho_m <= 0 or alto_m <= 0 or largo_total_m <= 0 or v_ms <= 0:
        return 0.0
    Dh = 2.0 * ancho_m * alto_m / (ancho_m + alto_m)
    Re = rho * v_ms * Dh / mu
    eps_rel = rugosidad_m / Dh if Dh > 0 else 0.0
    f = _factor_friccion_haaland(Re, eps_rel)
    return f * (largo_total_m / Dh) * (rho * v_ms**2 / 2.0)


def estimar_delta_P_colector(
    colector: "Colector",
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> float:
    """Estima la pérdida de carga en el banco de colectores via Darcy-Weisbach.

    Usa correlación de Haaland (1983) con rugosidad real de la placa absorbedora
    leída del catálogo (`placas.yaml`, campo `rugosidad_m`). Si la placa no
    declara rugosidad, usa default conservador (5e-5 m, chapa pintada).

    Para banco en serie, ΔP escala con la longitud total del camino. Para ramas
    en paralelo, ΔP banco = ΔP de una rama.

    Por tipo de colector:
    - **Tipo 1**: canal único sobre absorbedor (altura ``espaciado_m``).
    - **Tipo 2**: ambos canales activos en paralelo. ΔP = max(ΔP_cs, ΔP_ci)
      (en paralelo balanceado deberían ser iguales; tomamos el más restrictivo
      como referencia).
    - **Tipo 3**: canal inferior activo (altura ``espaciado_inferior_m``).
    - **Tipo 4**: canal superior activo (altura ``espaciado_m``).

    Args:
        colector: Objeto Colector con geometría y banco definidos.
        T_K: Temperatura de operación del aire en el colector [K]. Default: 323.15 K (50 °C).
        P_Pa: Presión atmosférica en el emplazamiento [Pa]. Default: 101 325 Pa (nivel del mar).

    Returns:
        ΔP estimada en el banco de colectores [Pa].
    """
    u = colector.unidad
    b = colector.banco

    rho = densidad_aire(T_K, P_Pa)
    mu = viscosidad_aire(T_K)

    ancho = u.ancho_m
    v = u.velocidad_diseno_ms
    L_total = u.largo_m * b.n_serie

    # Rugosidad de la placa absorbedora desde el catálogo
    placa = catalogo.PLACAS.get(u.id_placa, {})
    rugosidad = float(placa.get("rugosidad_m", _RUGOSIDAD_DEFAULT_M))

    tipo = u.tipo_colector
    if tipo == 1:
        # Canal único sobre el absorbedor
        return _delta_P_canal_colector(
            ancho,
            u.espaciado_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )
    elif tipo == 4:
        # Canal superior activo, inferior estanco
        return _delta_P_canal_colector(
            ancho,
            u.espaciado_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )
    elif tipo == 3:
        # Canal inferior activo, superior estanco
        return _delta_P_canal_colector(
            ancho,
            u.espaciado_inferior_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )
    elif tipo == 2:
        # Ambos canales activos en paralelo. Tomamos el más restrictivo.
        dP_cs = _delta_P_canal_colector(
            ancho,
            u.espaciado_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )
        dP_ci = _delta_P_canal_colector(
            ancho,
            u.espaciado_inferior_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )
        return max(dP_cs, dP_ci)
    else:
        # Fallback defensivo (no debería pasar por validación de dataclass)
        return _delta_P_canal_colector(
            ancho,
            u.espaciado_m,
            L_total,
            v,
            rugosidad,
            rho,
            mu,
        )


# ---------------------------------------------------------------------------
# Ergun — lecho empacado (uso interno)
# ---------------------------------------------------------------------------


def _delta_P_lecho_por_bandeja(
    bandejas: "ConfiguracionBandejas",
    v0: float,
    rho: float,
    mu: float,
    producto_id: Optional[str] = None,
) -> float:
    """ΔP a través de la capa de producto en una bandeja via ecuación de Ergun [Pa].

    Geometría del lecho (d_p, ε, Φ_s) resuelta por ``_geometria_lecho``:
    bandejas explícito → catálogo del producto → defaults conservadores.

    Args:
        bandejas: Configuración de bandejas (contiene ε, Φ_s, d_p, L).
        v0: Velocidad superficial del aire sobre la bandeja [m/s].
        rho: Densidad del aire [kg/m³].
        mu: Viscosidad dinámica del aire [Pa·s].
        producto_id: Identificador del producto para lookup en catálogo si
            ``bandejas`` no tiene valores explícitos. ``None`` usa defaults.

    Returns:
        ΔP_lecho por bandeja [Pa].
    """
    d_p, eps, phi_s = _geometria_lecho(bandejas, producto_id)
    L = bandejas.espesor_capa_m

    phi_dp = phi_s * d_p
    eps3 = eps**3
    one_minus_eps = 1.0 - eps

    grad_viscoso = 150.0 * mu * v0 * one_minus_eps**2 / (phi_dp**2 * eps3)
    grad_inercial = 1.75 * rho * v0**2 * one_minus_eps / (phi_dp * eps3)

    return (grad_viscoso + grad_inercial) * L


# ---------------------------------------------------------------------------
# Pérdida de forma por rugosidad del producto y por transición de lecho
# ---------------------------------------------------------------------------

# Pérdida de transición entrada/salida del lecho en flujo VERTICAL_ASCENDENTE:
# contracción brusca al entrar al lecho desde el espacio libre superior
# (K ≈ 0.5) + expansión brusca al salir al espacio libre inferior
# (K ≈ 1.0 Borda-Carnot). Aplicado una vez por bandeja, sobre ρ·v₀²/2.
# Independiente del producto.
K_TRANSICION_LECHO: float = 1.5

# Tabla de anclajes para K_rugosidad en función de d_p / espacio_libre (sin
# correlación específica de literatura para "cross-flow sobre lecho rugoso de
# secador"; valores inspirados en Idelchik para superficies con rugosidad
# elevada y bancos de obstáculos). Interpolación lineal entre puntos; valor
# constante fuera de los extremos.
_K_RUGOSIDAD_TABLA: tuple[tuple[float, float], ...] = (
    (0.05, 0.2),  # casi liso: pequeñas perturbaciones
    (0.15, 0.5),  # rugosidad significativa, estelas pequeñas
    (0.30, 1.0),  # producto comparable al canal, obstrucción parcial
    (0.50, 2.0),  # cuasi-bloqueo, el aire tropieza
)


def _K_rugosidad_default(d_p: float, espacio_libre: float) -> float:
    """Estima K_rugosidad por bandeja en función del ratio ``d_p/espacio_libre``.

    Interpolación lineal por tramos sobre ``_K_RUGOSIDAD_TABLA``. Saturada
    por debajo del primer punto (K = 0.2) y por encima del último (K = 2.0).

    Args:
        d_p: Diámetro equivalente de partícula [m].
        espacio_libre: Altura libre del canal entre bandejas [m] en flujo
            HORIZONTAL. Si ≤ 0 devuelve 0 (degenerado).

    Returns:
        K adimensional para aplicar como K·ρv²/2 una vez por bandeja.
    """
    if d_p <= 0 or espacio_libre <= 0:
        return 0.0
    ratio = d_p / espacio_libre
    x0, y0 = _K_RUGOSIDAD_TABLA[0]
    xN, yN = _K_RUGOSIDAD_TABLA[-1]
    if ratio <= x0:
        return y0
    if ratio >= xN:
        return yN
    for (x1, y1), (x2, y2) in zip(_K_RUGOSIDAD_TABLA, _K_RUGOSIDAD_TABLA[1:]):
        if x1 <= ratio <= x2:
            t = (ratio - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)
    return yN  # defensa contra inexactitud de float


# ---------------------------------------------------------------------------
# Estimación ΔP cámara
# ---------------------------------------------------------------------------


def estimar_delta_P_camara(
    camara: "Camara",
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> float:
    """Estima la pérdida de carga en la cámara de secado.

    Flujo VERTICAL_ASCENDENTE (aire atraviesa cada bandeja):
        ΔP = (ΔP_malla + ΔP_lecho + ΔP_transicion) × n_bandejas
        ΔP_malla       = K_malla × (ρ·v₀²/2),   v₀ = Q_vol / area_bandeja
        ΔP_lecho       = Ergun(v₀, ε, Φ_s, d_p, L)  con d_p del catálogo del
                         producto si no está explícito en ``bandejas``.
        ΔP_transicion  = K_TRANSICION_LECHO × (ρ·v₀²/2)  (contracción al
                         entrar al lecho + expansión a la salida, ~1.5)
        En VERTICAL no se aplica K_rugosidad explícito porque Ergun ya
        captura la rugosidad del producto vía Φ_s y d_p.

    Flujo HORIZONTAL (aire pasa entre bandejas, no las atraviesa):
        Modelo de canal rectangular Darcy-Weisbach por par de bandejas:
            Dh_canal = 2·ancho·sep / (ancho + sep)
            v_canal = Q_vol / [ancho · sep · (n_bandejas − 1)]
                      (Q se reparte entre los espacios libres entre bandejas)
            ΔP_friccion = f · (largo/Dh) · (ρ·v_canal²/2)   por espacio
            ΔP_malla    = K_malla_lateral · (ρ·v_canal²/2)   (~0.5, baja)
        ΔP_rugosidad = K_rug × (ρ·v_canal²/2) × n_bandejas
            K_rug del usuario (``bandejas.K_rugosidad_producto``) o
            autocalculado por ``_K_rugosidad_default`` a partir del ratio
            ``d_p / espacio_libre``. Captura la pérdida de forma por
            superficie rugosa del lecho de producto en cross-flow, que
            Darcy-Weisbach de pared lisa subestima.
        Total = (ΔP_friccion + ΔP_malla) × (n_bandejas − 1) + ΔP_rugosidad

        Notas:
        - K_malla aplicado lateralmente es bajo (~0.5) porque la malla está
          paralela al flujo, no atravesada. La pérdida principal es por
          fricción contra la pared y las superficies de las bandejas.
        - Si hay sólo 1 bandeja, no hay canal definido; se omite el término
          de fricción/malla y queda sólo K_rugosidad sobre la velocidad del
          ducto vacío.

    Args:
        camara: Objeto Camara con geometría, bandejas y flujo definidos.
        T_K: Temperatura de operación del aire en la cámara [K]. Default: 323.15 K (50 °C).
        P_Pa: Presión atmosférica en el emplazamiento [Pa]. Default: 101 325 Pa.

    Returns:
        ΔP estimada en la cámara de secado [Pa]. NO incluye pérdidas
        singulares de entrada/salida (esas se acumulan en `estimar_delta_P_singulares`).
    """
    from core.camara import DireccionFlujo

    g = camara.geometria
    f = camara.flujo
    b = camara.bandejas

    rho = densidad_aire(T_K, P_Pa)
    mu = viscosidad_aire(T_K)
    Q_vol = f.caudal_masico_kg_s / rho

    producto_id = camara.carga_producto.producto_id if camara.carga_producto is not None else None

    K_malla_eff = _K_malla_efectivo(b.tipo_malla)

    if f.direccion_flujo == DireccionFlujo.VERTICAL_ASCENDENTE:
        v0 = Q_vol / b.area_bandeja_m2 if b.area_bandeja_m2 > 0 else 0.0
        dP_malla = K_malla_eff * (rho * v0**2 / 2.0)
        dP_lecho = _delta_P_lecho_por_bandeja(b, v0, rho, mu, producto_id=producto_id)
        dP_transicion = K_TRANSICION_LECHO * (rho * v0**2 / 2.0)
        return (dP_malla + dP_lecho + dP_transicion) * b.n_bandejas

    # --- HORIZONTAL: canal rectangular entre bandejas ---
    # Espaciado entre bandejas = sep − espesor_capa_producto (espacio libre real)
    espacio_libre = max(0.0, b.separacion_entre_bandejas_m - b.espesor_capa_m)
    n_canales = max(1, b.n_bandejas - 1)  # entre N bandejas hay N-1 canales

    if espacio_libre <= 0 or g.ancho_m <= 0:
        return 0.0

    # Caudal repartido entre canales paralelos
    area_canal = g.ancho_m * espacio_libre
    v_canal = Q_vol / (area_canal * n_canales)
    Dh = 2.0 * g.ancho_m * espacio_libre / (g.ancho_m + espacio_libre)
    Re = rho * v_canal * Dh / mu if mu > 0 else 0.0
    if Re <= 0:
        f_fric = 0.0
    elif Re < 2300.0:
        f_fric = 64.0 / Re
    else:
        f_fric = 0.316 * Re ** (-0.25)

    L = g.largo_m  # largo del recorrido del aire (igual al largo de la cámara)
    dP_friccion_por_canal = f_fric * (L / Dh) * (rho * v_canal**2 / 2.0)
    # Pérdida lateral por la malla (paralela al flujo). Se aplica una fracción
    # del K_malla (típicamente ~25 %) porque la malla no está perpendicular al
    # flujo en este caso, sólo le agrega rozamiento adicional.
    dP_malla_por_canal = 0.25 * K_malla_eff * (rho * v_canal**2 / 2.0)
    dP_canales = (dP_friccion_por_canal + dP_malla_por_canal) * n_canales

    # Pérdida de forma por rugosidad del producto sobre cada bandeja. K override
    # del usuario o autocalculado desde d_p/espacio_libre. Aplicado n_bandejas
    # veces (una por superficie rugosa, no por canal): si N=1 hay una sola
    # superficie expuesta; si N>1, cada bandeja agrega su contribución.
    if b.K_rugosidad_producto is not None:
        K_rug = float(b.K_rugosidad_producto)
    else:
        d_p, _eps, _phi_s = _geometria_lecho(b, producto_id)
        K_rug = _K_rugosidad_default(d_p, espacio_libre)
    dP_rugosidad = K_rug * (rho * v_canal**2 / 2.0) * b.n_bandejas

    return dP_canales + dP_rugosidad


# ---------------------------------------------------------------------------
# Caudal volumétrico desde caudal másico
# ---------------------------------------------------------------------------


def estimar_delta_P_singulares(
    *,
    Q_vol_m3_s: float,
    v_ducto_m_s: float,
    n_paralelo: int = 1,
    n_codos: int = 2,
    K_entrada: float = 0.5,
    K_salida: float = 1.0,
    K_codo: float = 0.9,
    K_manifold: float = 1.5,
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> dict[str, float]:
    """Estima las pérdidas singulares del sistema (entrada, salida, codos, manifold).

    Los K-coefficients se aplican sobre la presión dinámica del ducto principal
    (ρ·v_ducto²/2). Para banco con n_paralelo > 1, se agrega un par
    distribuidor/colector (manifold) con K combinado.

    Valores K conservadores estándar (Idelchik, Crane TP-410):
    - Entrada borde vivo: K = 0.5
    - Salida descarga libre: K = 1.0 (toda la energía cinética se pierde)
    - Codo 90° bridado liso: K = 0.3; codo 90° gajos chapa: K = 1.3.
      Default 0.9 (promedio conservador).
    - Manifold simétrico distribuidor+colector: K_total = 1.5

    Args:
        Q_vol_m3_s: Caudal volumétrico del sistema [m³/s].
        v_ducto_m_s: Velocidad del aire en el ducto principal [m/s].
            Típico: 4–7 m/s en secadores solares.
        n_paralelo: Ramas paralelas del banco. >1 activa el término manifold.
        n_codos: Cambios de dirección 90° en el circuito. Default 2.
        K_entrada, K_salida, K_codo, K_manifold: Coeficientes singulares.
        T_K, P_Pa: Condiciones del aire para ρ.

    Returns:
        Dict con claves 'entrada', 'salida', 'codos', 'manifold', 'total' [Pa].
    """
    rho = densidad_aire(T_K, P_Pa)
    q_dinamica = rho * v_ducto_m_s**2 / 2.0

    dP_entrada = K_entrada * q_dinamica
    dP_salida = K_salida * q_dinamica
    dP_codos = max(0, n_codos) * K_codo * q_dinamica
    dP_manifold = K_manifold * q_dinamica if n_paralelo > 1 else 0.0
    total = dP_entrada + dP_salida + dP_codos + dP_manifold

    return {
        "entrada": dP_entrada,
        "salida": dP_salida,
        "codos": dP_codos,
        "manifold": dP_manifold,
        "total": total,
    }


def caudal_masico_a_volumetrico(
    caudal_masico_kg_s: float,
    T_K: float,
    P_Pa: float = 101325.0,
) -> float:
    """Convierte caudal másico a volumétrico usando gas ideal.

    Args:
        caudal_masico_kg_s: Caudal másico de aire seco [kg/s].
        T_K: Temperatura del aire [K].
        P_Pa: Presión absoluta [Pa]. Default: 101 325 Pa.

    Returns:
        Caudal volumétrico [m³/s].
    """
    rho = densidad_aire(T_K, P_Pa)
    return caudal_masico_kg_s / rho
