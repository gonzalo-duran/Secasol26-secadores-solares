"""Geometría del lecho de producto sobre bandeja (S63; movido a core/ en S64).

Módulo **puro** compartido por los dos modelos que ven la misma bandeja:

- ``core/camara.py`` — deriva el espesor de capa de la carga uniforme.
- ``calculos/motor_calc.py`` — pérdida de carga (cross-flow entre bandejas: el
  lecho es la pared rugosa del canal, y ``d_p`` es su altura de rugosidad).
- ``calculos/camara_calc.py`` — transferencia de calor y masa (área de las dos
  caras de la bandeja, con la cara inferior gateada por el área abierta de la
  malla).

**Qué cambió en S64.** S63 usó este módulo para el modelo de *lecho atravesado*
(área específica de partícula ``a_v = 6(1−ε)/(Φ_s·d_p)`` y Ranz-Marshall). Esa
topología se retiró —ver ``docs/notas/plan_crossflow_unico_camara.md``— y con
ella ``area_especifica_lecho_m2_m3``, ``area_transferencia_lecho_m2`` y
``h_conv_lecho``. Lo que queda del lecho es:

- ``d_p``  → altura de rugosidad del canal en el ΔP de cross-flow.
- ``ε``    → la restricción de **carga uniforme** que acopla masa, área,
             número de bandejas y espesor de capa.
- ``Φ_s``  → **sin consumidor**: solo aparecía en el producto ``Φ_s·d_p`` de
             Ergun y del área específica. Se conserva el campo en
             ``ConfiguracionBandejas`` y en el catálogo por back-compat de
             snapshots, pero hoy es vestigial.

**Por qué vive en core/ y no en calculos/.** ``Camara.__post_init__`` necesita
``espesor_capa_derivado_m`` y ``geometria_lecho`` para derivar el espesor de capa,
y ``core/`` no puede importar de ``calculos/`` sin invertir las capas. El módulo
solo depende de ``core.catalogo`` y de las dataclasses, así que su lugar natural
es acá. ``calculos/lecho_producto.py`` lo re-exporta para los consumidores
históricos, igual que ``calculos/simulacion_ventana`` hace con ``PoliticaRecarga``.

Convención de unidades: SI estricto (longitudes [m], densidades [kg/m³]).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from core import catalogo

if TYPE_CHECKING:  # pragma: no cover
    from core.camara import ConfiguracionBandejas

# Defaults conservadores para geometría de lecho cuando ni el usuario ni el
# catálogo del producto proveen valores. Valor genérico de "trozo de comida
# tamaño medio sobre bandeja" (~8 mm, lecho con huecos medios, no esférico).
D_P_DEFAULT_M: float = 0.008
EPSILON_DEFAULT: float = 0.45
PHI_S_DEFAULT: float = 0.6

#: Fracción de área abierta por tipo de malla de bandeja [adim]. Es la fracción
#: de la cara **inferior** del lecho que el aire del canal de abajo alcanza;
#: complementa a ``motor_calc.TIPOS_MALLA``, que da el K de pérdida de carga de
#: la misma malla. Claves idénticas a las de aquel diccionario.
AREA_ABIERTA_MALLA: dict[str, float] = {
    "alambre_fino": 0.45,  # mosquitera ≤ 1 mm: mucho hilo, poca luz
    "alambre_grueso": 0.60,  # malla galvanizada de bandeja (1.5–3 mm)
    "chapa_perforada_50pc": 0.50,  # el nombre lo declara
    "chapa_perforada_30pc": 0.30,  # ídem
    "tela_metalica_densa": 0.35,  # tejido fino de paso pequeño
}

#: Default cuando ``tipo_malla`` es None o no figura en ``AREA_ABIERTA_MALLA``.
#: Mismo criterio que ``motor_calc.K_MALLA``: la bandeja típica de secador solar
#: es de alambre, ni chapa perforada industrial ni mosquitera.
AREA_ABIERTA_DEFAULT: float = 0.5


def area_abierta_malla_efectiva(tipo_malla: Optional[str]) -> float:
    """Fracción de área abierta de la malla de bandeja [adim, 0–1].

    Lookup contra ``AREA_ABIERTA_MALLA`` con fallback a
    ``AREA_ABIERTA_DEFAULT``. Calcado de ``motor_calc._K_malla_efectivo`` para
    que las dos propiedades de la misma malla se resuelvan igual.

    Args:
        tipo_malla: Identificador del catálogo de mallas. ``None`` → default.

    Returns:
        Fracción de área abierta [0–1].
    """
    if tipo_malla is None:
        return AREA_ABIERTA_DEFAULT
    return AREA_ABIERTA_MALLA.get(tipo_malla, AREA_ABIERTA_DEFAULT)


def geometria_lecho(
    bandejas: "ConfiguracionBandejas", producto_id: Optional[str] = None
) -> tuple[float, float, float]:
    """Resuelve (d_p, ε, Φ_s) del lecho con la cadena de prioridad:

    1. Si ``bandejas`` tiene el valor seteado explícitamente, usarlo.
    2. Si el producto tiene ``forma_geometrica`` en el catálogo, leerlo.
    3. Defaults conservadores (8 mm, 0.45, 0.6).

    ``Φ_s`` se devuelve por compatibilidad; desde S64 no lo consume nadie.

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
        else float(forma.get("diametro_eq_m", D_P_DEFAULT_M))
    )
    # ε y Φ_s tienen defaults en ConfiguracionBandejas (0.45 y 0.6). Si el
    # usuario los dejó en default y el catálogo del producto trae otros,
    # priorizamos el catálogo (más informativo). Para que esto funcione,
    # comparamos con los defaults conocidos de la dataclass.
    if forma.get("porosidad_lecho") is not None and bandejas.porosidad_lecho == EPSILON_DEFAULT:
        eps = float(forma["porosidad_lecho"])
    else:
        eps = bandejas.porosidad_lecho
    if forma.get("esfericidad") is not None and bandejas.esfericidad == PHI_S_DEFAULT:
        phi_s = float(forma["esfericidad"])
    else:
        phi_s = bandejas.esfericidad
    return d_p, eps, phi_s


def d_p_es_default(bandejas: "ConfiguracionBandejas", producto_id: Optional[str] = None) -> bool:
    """True si ``d_p`` sale del default genérico (ni el usuario ni el catálogo).

    ``d_p`` gobierna la rugosidad del canal en el ΔP de cross-flow, así que un
    valor inventado se propaga al caudal y la UI tiene que poder avisarlo.
    """
    if bandejas.diametro_eq_particula_m is not None:
        return False
    if producto_id is None:
        return True
    forma = (catalogo.PRODUCTOS.get(producto_id) or {}).get("forma_geometrica") or {}
    return forma.get("diametro_eq_m") is None


def volumen_lecho_m3(bandejas: "ConfiguracionBandejas") -> float:
    """Volumen total del lecho [m³] = n_bandejas · área_bandeja · espesor_capa."""
    return float(bandejas.n_bandejas * bandejas.area_bandeja_m2 * bandejas.espesor_capa_m)


def masa_que_llena_el_lecho_kg(
    bandejas: "ConfiguracionBandejas",
    densidad_material_kg_m3: float,
    producto_id: Optional[str] = None,
) -> float:
    """Masa de producto que ocuparía el lecho declarado [kg].

    ``m = V_lecho·(1−ε)·ρ_material``. Es la **restricción de carga uniforme**:
    masa, área de bandeja, número de bandejas y espesor de capa no son cuatro
    variables libres sino cuatro ligadas por esta ecuación.

    **El ``(1−ε)`` va.** El campo del catálogo se llama ``densidad_aparente``
    pero el valor es densidad de **material** (manzana 840 kg/m³, ASHRAE Ch.19),
    no densidad de lecho: sin el ``(1−ε)`` el resultado se va ~2.2×.

    Args:
        bandejas: ``ConfiguracionBandejas`` del usuario.
        densidad_material_kg_m3: Densidad del producto [kg/m³] (catálogo).
        producto_id: Producto para resolver ε desde el catálogo.

    Returns:
        Masa [kg]. 0.0 si falta la densidad o el lecho es degenerado.
    """
    if densidad_material_kg_m3 <= 0.0:
        return 0.0
    _d_p, eps, _phi_s = geometria_lecho(bandejas, producto_id)
    return volumen_lecho_m3(bandejas) * max(0.0, 1.0 - eps) * densidad_material_kg_m3


def espesor_capa_derivado_m(
    masa_total_kg: float,
    area_bandeja_m2: float,
    n_bandejas: int,
    densidad_material_kg_m3: float,
    porosidad: float,
) -> float:
    """Espesor de capa que corresponde a una carga uniforme [m].

    Inversa exacta de :func:`masa_que_llena_el_lecho_kg`:

        ``espesor = m / (ρ_material·(1−ε)·A_bandeja·n_bandejas)``

    Con carga uniforme y espesor único, masa/área/n_bandejas/espesor están
    ligados por una sola ecuación: el espesor es el que menos puede responder
    con confianza un usuario de prediseño, así que es el que se deriva.

    Args:
        masa_total_kg: Carga de producto húmedo [kg].
        area_bandeja_m2: Área de una bandeja [m²].
        n_bandejas: Cantidad de bandejas.
        densidad_material_kg_m3: Densidad del producto [kg/m³] (catálogo).
        porosidad: ε del lecho [adim].

    Returns:
        Espesor de capa [m]. 0.0 si algún factor del denominador es nulo (el
        llamador decide: sin producto o sin geometría no hay nada que derivar).
    """
    solido = max(0.0, 1.0 - porosidad)
    denom = densidad_material_kg_m3 * solido * area_bandeja_m2 * n_bandejas
    if denom <= 0.0 or masa_total_kg <= 0.0:
        return 0.0
    return float(masa_total_kg / denom)
