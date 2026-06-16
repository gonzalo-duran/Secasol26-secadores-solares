"""
Estimación de pérdidas de carga para el dimensionamiento del motor.

Provee funciones para calcular ΔP en el banco de colectores y en la cámara
de secado. Estos valores se usan como entrada al objeto Motor.

Modelos:
    Colector (canal rectangular) — Darcy-Weisbach:
        ΔP = f × (L/Dh) × (ρ × v²/2)
        Dh = 2·W·e / (W + e)    [diámetro hidráulico canal plano]
        f  = 64/Re                         (laminar, Re < 2 300)
        f  = Haaland(Re, ε/Dh)             (turbulento; aprox. de Colebrook,
             ASHRAE cap. 21 ec. 19; mismo f en colector, caño maestro y cámara)
        En banco serie: ΔP_rama = ΔP_unidad × n_serie
        En paralelo:   ΔP banco = ΔP rama

    Cámara — flujo HORIZONTAL (cross-flow, canales EN PARALELO):
        Los n_canales = n_bandejas−1 espacios entre bandejas están en paralelo:
        el ΔP del sistema es el de UN canal (no la suma). v_canal reparte el
        caudal: v_canal = Q_vol / (ancho · espacio_libre · n_canales).
        ΔP_cam = ΔP_producto + ΔP_malla_lateral, con
        ΔP_producto = fricción rugosa (Colebrook, ε_eff = max(ε_chapa, d_p)) +
                      obstrucción por bloqueo C_obs(β), β = espesor_capa/separacion.
        (Modelo combinado, mejora 29; reemplaza el Blasius + tabla heurística.)

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

# Rugosidad absoluta de chapa galvanizada para ductos/canales de cámara.
# ASHRAE 2017 HVAC Fundamentals cap. 21, Tabla 1 (galvanizado rectangular,
# juntas varias): ε ≈ 0.09–0.15 mm. Se toma 0.15 mm (extremo conservador).
_RUGOSIDAD_GALVANIZADO_M: float = 1.5e-4


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

    Solo aplica a flujo VERTICAL_ASCENDENTE (el aire ATRAVIESA el lecho). En
    cross-flow (HORIZONTAL) el aire pasa paralelo sobre la bandeja y se usa el
    modelo combinado ``_delta_P_producto_crossflow``, no Ergun.

    Rango de validez (mejora 29): Ergun es el estándar para lechos empacados de
    partículas razonablemente uniformes. Para rodajas/trozos de alimento (no
    esféricos, polidispersos) es una aproximación a través de la esfericidad Φ_s
    y el diámetro equivalente d_p del catálogo del producto; los parámetros del
    lecho (ε, Φ_s, d_p) gobiernan fuertemente el resultado.

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


def _C_obstruccion_bloqueo(beta: float) -> float:
    """Coeficiente de obstrucción por bloqueo del lecho en cross-flow [adim].

    El producto sobre la bandeja ocupa una fracción ``β = espesor_capa/separacion``
    del gap entre bandejas. La pérdida de forma se modela como una contracción
    brusca al entrar al canal estrechado por el lecho (K_c ≈ 0.5·σ', Idelchik)
    más una expansión Borda-Carnot a la salida (K_e ≈ σ'²), referidas a la
    velocidad del canal libre, con ``σ' = β/(1−β)`` el factor de obstrucción:

        C_obs(β) = 0.5·[β/(1−β)] + [β/(1−β)]²

    Crece monótonamente con β, vale 0 para lecho despreciable y diverge cuando
    β→1 (gap totalmente bloqueado). Reemplaza la antigua tabla heurística
    ``_K_rugosidad`` (S41, mejora 29).

    Args:
        beta: Fracción del gap ocupada por el producto, β ∈ [0, 1).

    Returns:
        Coeficiente de obstrucción C_obs para aplicar como C·ρv²/2.
    """
    if beta <= 0.0:
        return 0.0
    beta = min(beta, 0.95)  # cota para evitar divergencia numérica en β→1
    sigma = beta / (1.0 - beta)
    return 0.5 * sigma + sigma**2


def _delta_P_producto_crossflow(
    *,
    v_canal: float,
    Dh: float,
    L: float,
    rho: float,
    mu: float,
    d_p: float,
    espesor_capa: float,
    separacion: float,
    K_obstruccion_override: Optional[float] = None,
    n_obstruccion_serie: int = 1,
) -> dict[str, float]:
    """ΔP del producto en cross-flow (flujo paralelo sobre la bandeja) [Pa].

    Modelo COMBINADO (mejora 29), referido a un canal entre bandejas (los canales
    de un mismo grupo están en paralelo, así que este es el ΔP del sistema, no la
    suma de canales):

    1. **Fricción con rugosidad aumentada:** el lecho de producto es la pared
       rugosa del canal. Rugosidad efectiva ``ε_eff = max(ε_galvanizado, d_p)``
       (el producto domina sobre la chapa), Colebrook/Haaland sobre el largo L.
    2. **Obstrucción por bloqueo:** ``C_obs(β)·ρv²/2 × n_obstruccion_serie`` con
       ``β = espesor_capa/separacion`` (ver ``_C_obstruccion_bloqueo``). El
       multiplicador en serie cuenta los grupos de bandejas que el aire atraviesa
       uno tras otro (p. ej. los carros de un túnel; =1 en cámara simple). Si se
       pasa ``K_obstruccion_override`` se usa ese C en lugar del auto-cálculo.

    Args:
        v_canal: Velocidad del aire en el canal libre entre bandejas [m/s].
        Dh: Diámetro hidráulico del canal [m].
        L: Largo del recorrido del aire (largo de la cámara) [m].
        rho: Densidad del aire [kg/m³].
        mu: Viscosidad dinámica del aire [Pa·s].
        d_p: Dimensión característica del producto [m] (rugosidad del lecho).
        espesor_capa: Espesor de la capa de producto sobre la bandeja [m].
        separacion: Separación entre bandejas consecutivas [m].
        K_obstruccion_override: Override manual del coeficiente de obstrucción.
            ``None`` usa el auto-cálculo ``_C_obstruccion_bloqueo(β)``.
        n_obstruccion_serie: Grupos de bandejas en serie a lo largo del flujo
            (carros de un túnel). Multiplica la obstrucción. Default 1.

    Returns:
        Dict con 'friccion_rugosa', 'obstruccion' y 'total' [Pa].
    """
    if v_canal <= 0.0 or Dh <= 0.0:
        return {"friccion_rugosa": 0.0, "obstruccion": 0.0, "total": 0.0}

    q_din = rho * v_canal**2 / 2.0
    eps_eff = max(_RUGOSIDAD_GALVANIZADO_M, d_p)
    Re = rho * v_canal * Dh / mu if mu > 0 else 0.0
    f = _factor_friccion_haaland(Re, eps_eff / Dh)
    dP_fric = f * (L / Dh) * q_din if Dh > 0 else 0.0

    beta = espesor_capa / separacion if separacion > 0 else 0.0
    C_obs = (
        float(K_obstruccion_override)
        if K_obstruccion_override is not None
        else _C_obstruccion_bloqueo(beta)
    )
    dP_obs = C_obs * q_din * max(1, n_obstruccion_serie)
    return {
        "friccion_rugosa": dP_fric,
        "obstruccion": dP_obs,
        "total": dP_fric + dP_obs,
    }


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

    Flujo HORIZONTAL (cross-flow: el aire pasa entre bandejas en PARALELO):
        Los n_canales = n_bandejas−1 espacios entre bandejas están en paralelo,
        así que el ΔP del sistema es el de UN canal (no la suma):
            v_canal = Q_vol / [ancho · espacio_libre · (n_bandejas − 1)]
            Dh_canal = 2·ancho·espacio_libre / (ancho + espacio_libre)
        ΔP = ΔP_producto + ΔP_malla_lateral, con el modelo COMBINADO del
        producto (``_delta_P_producto_crossflow``, mejora 29):
            ΔP_producto = fricción rugosa (Colebrook, ε_eff = max(ε_chapa, d_p))
                          + obstrucción C_obs(β)·ρv²/2,  β = espesor_capa/separacion
            ΔP_malla    = 0.25·K_malla·(ρ·v_canal²/2)  (placa perforada paralela)
            El override ``bandejas.K_rugosidad_producto`` reemplaza el C_obs auto.

        Nota: corrige el sobreconteo previo (×n_canales y ×n_bandejas), que
        ignoraba que los canales están en paralelo.

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

    # --- HORIZONTAL: cross-flow entre bandejas (paralelo + serie) ---
    # Topología (mejora 29):
    #  - Dentro de un grupo de bandejas apiladas el aire se reparte entre los
    #    canales EN PARALELO → todos con el mismo ΔP, así que el ΔP del grupo es
    #    el de UN canal (no la suma de los n canales).
    #  - Si la cámara tiene carros (túnel), el aire atraviesa los carros EN SERIE
    #    a lo largo del túnel → la obstrucción se acumula × n_carros.
    # (Antes se tomaban TODAS las bandejas como paralelas y se multiplicaba por
    # n_canales y n_bandejas, lo que sobreestimaba el roce y, en el túnel,
    # subestimaba la obstrucción del producto al diluir la velocidad del canal.)
    carros = camara.carros
    if carros is not None:
        n_canales = max(1, carros.bandejas_por_carro - 1)  # paralelo dentro del carro
        n_serie = carros.n_carros  # carros en serie a lo largo del túnel
    else:
        n_canales = max(1, b.n_bandejas - 1)  # entre N bandejas hay N-1 canales
        n_serie = 1

    espacio_libre = max(0.0, b.separacion_entre_bandejas_m - b.espesor_capa_m)
    if espacio_libre <= 0 or g.ancho_m <= 0:
        return 0.0

    area_canal = g.ancho_m * espacio_libre
    v_canal = Q_vol / (area_canal * n_canales)  # caudal repartido en paralelo
    Dh = 2.0 * g.ancho_m * espacio_libre / (g.ancho_m + espacio_libre)
    L = g.largo_m  # largo del recorrido del aire (igual al largo de la cámara)
    q_din = rho * v_canal**2 / 2.0

    # ΔP del producto: modelo combinado (mejora 29) — fricción con rugosidad
    # aumentada (el lecho es la pared rugosa del canal, sustituye al Darcy de
    # pared lisa) + obstrucción por bloqueo β = espesor_capa/separacion × n_serie.
    d_p, _eps, _phi_s = _geometria_lecho(b, producto_id)
    dP_prod = _delta_P_producto_crossflow(
        v_canal=v_canal,
        Dh=Dh,
        L=L,
        rho=rho,
        mu=mu,
        d_p=d_p,
        espesor_capa=b.espesor_capa_m,
        separacion=b.separacion_entre_bandejas_m,
        K_obstruccion_override=b.K_rugosidad_producto,
        n_obstruccion_serie=n_serie,
    )

    # Pérdida lateral por la malla/placa perforada de la bandeja (paralela al
    # flujo): aporta rozamiento adicional, fracción del K perpendicular.
    dP_malla = 0.25 * K_malla_eff * q_din

    return dP_prod["total"] + dP_malla


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
    K_difusor: float = 0.3,
    T_K: float = 323.15,
    P_Pa: float = 101325.0,
) -> dict[str, float]:
    """Estima las pérdidas singulares del sistema (taxonomía ASHRAE cap. 21).

    Los coeficientes de pérdida C se aplican sobre la presión dinámica del ducto
    principal (ρ·v_ducto²/2), método de ASHRAE 2017 cap. 21 (Dynamic Losses) y
    Idelchik. Categorías cubiertas: Entries, Exits, Elbows, Junctions, Transitions.

    Valores C conservadores (ASHRAE cap. 21 / Idelchik / Crane TP-410):
    - Entrada (Entries) borde vivo: C = 0.5
    - Salida (Exits) descarga libre: C = 1.0 (toda la energía cinética se pierde)
    - Codo 90° (Elbows) bridado liso C = 0.3; gajos de chapa C = 1.3.
      Default 0.9 (promedio conservador).
    - Manifold banco→caño maestro (Junctions, confluencia convergente): C = 1.5
      (par distribuidor/colector simétrico). Solo si n_paralelo > 1.
    - Difusor de entrada a cámara (Transitions, expansión ducto→cámara): C = 0.3
      (difusor con cierto diseño; expansión brusca Borda-Carnot daría C ≈ 1.0).

    Args:
        Q_vol_m3_s: Caudal volumétrico del sistema [m³/s].
        v_ducto_m_s: Velocidad del aire en el ducto principal [m/s].
            Típico: 4–7 m/s en secadores solares.
        n_paralelo: Ramas paralelas del banco. >1 activa el término manifold.
        n_codos: Cambios de dirección 90° en el circuito. Default 2.
        K_entrada, K_salida, K_codo, K_manifold, K_difusor: Coeficientes C.
        T_K, P_Pa: Condiciones del aire para ρ.

    Returns:
        Dict con 'entrada', 'salida', 'codos', 'manifold', 'difusor', 'total' [Pa].
    """
    rho = densidad_aire(T_K, P_Pa)
    q_dinamica = rho * v_ducto_m_s**2 / 2.0

    dP_entrada = K_entrada * q_dinamica
    dP_salida = K_salida * q_dinamica
    dP_codos = max(0, n_codos) * K_codo * q_dinamica
    dP_manifold = K_manifold * q_dinamica if n_paralelo > 1 else 0.0
    dP_difusor = K_difusor * q_dinamica
    total = dP_entrada + dP_salida + dP_codos + dP_manifold + dP_difusor

    return {
        "entrada": dP_entrada,
        "salida": dP_salida,
        "codos": dP_codos,
        "manifold": dP_manifold,
        "difusor": dP_difusor,
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
