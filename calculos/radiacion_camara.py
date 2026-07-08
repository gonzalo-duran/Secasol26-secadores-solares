"""Irradiancia equivalente sobre las superficies translúcidas de la cámara.

Generaliza el techo translúcido histórico (única superficie horizontal, GHI
cruda) a hasta 5 caras (techo + 4 paredes) con orientación e inclinación
propias, calculadas a partir de ``GeometriaCamara.caras()``. La cámara puede
operar como colector propio (tipología CAJA) o tener una orientación
independiente del banco de colectores (ARMARIO / GRAN_ESCALA).

Reparto producto/aire: cada cara translúcida intercepta una fracción ``f_i``
de su radiación transmitida directamente sobre el producto (el resto la
absorben las superficies internas opacas y calienta el aire — efecto
invernadero de la caja):

    I_eq_prod(t)    = Σᵢ fᵢ·Aᵢ·POAᵢ(t) / A_rad   [W/m², sin τ·α — los aplica
                      el motor termodinámico como siempre: Q_rad = τ·α·A_rad·I_g]
    Q_rad_aire_W(t) = τ·α_interior·Σᵢ (1−fᵢ)·Aᵢ·POAᵢ(t)   [W, ya escalado]

Back-compat exacta: con solo el techo translúcido y ``pendiente_techo_deg=0``
(configuración histórica), ``I_eq_prod`` coincide algebraicamente con GHI
(no se llama a pvlib: la cara techo con tilt=0 usa GHI directamente).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from calculos.clima_calc import calcular_POA_horizonte
from core import catalogo

if TYPE_CHECKING:
    from core.camara import Camara
    from core.emplazamiento import Emplazamiento

_TILT_HORIZONTAL_TOL_DEG: float = 1e-9


def factores_intercepcion(camara: "Camara") -> dict[str, float]:
    """Fracción de la radiación transmitida por cada cara que intercepta el producto.

    El techo intercepta la fracción de su área real que corresponde al área
    de intercepción del producto (``A_rad``, histórico: bandeja superior). Las
    caras verticales interceptan según la silueta del lecho apilado: cuanto
    más separación entre bandejas, menos área de producto queda expuesta a
    la pared (aproximación de silueta — no depende de la posición de cada
    bandeja en la pila).

    Args:
        camara: Cámara completamente instanciada.

    Returns:
        Diccionario con clave por cara ("techo", "frente", "atras",
        "lateral_izq", "lateral_der") y valor en [0, 1].
    """
    g = camara.geometria
    c = camara.construccion
    b = camara.bandejas

    A_rad = c.A_rad_m2 if c.A_rad_m2 is not None else b.area_bandeja_m2
    A_techo_geom = g.A_techo_geom_m2
    f_techo = min(1.0, A_rad / A_techo_geom) if A_techo_geom > 0 else 0.0
    f_pared = max(0.0, min(1.0, b.n_bandejas * b.espesor_capa_m / g.alto_m))

    return {
        "techo": f_techo,
        "frente": f_pared,
        "atras": f_pared,
        "lateral_izq": f_pared,
        "lateral_der": f_pared,
    }


def poa_caras_camara(
    datos_clima: pd.DataFrame,
    emplazamiento: "Emplazamiento",
    camara: "Camara",
    *,
    modelo_difuso: str = "isotropic",
) -> dict[str, pd.Series]:
    """POA horaria sobre cada cara translúcida activa de la cámara [W/m²].

    Args:
        datos_clima: DataFrame horario con GHI/DNI/DHI (ver
            ``calcular_POA_horizonte``).
        emplazamiento: Emplazamiento del secador (lat/lon/altitud + albedo).
        camara: Cámara completamente instanciada.
        modelo_difuso: Modelo de transposición difusa de pvlib.

    Returns:
        Diccionario cara → serie POA [W/m²], solo para las caras
        translúcidas activas.
    """
    caras_activas = camara.construccion.caras_translucidas_activas()
    caras_geom = camara.geometria.caras()

    resultado: dict[str, pd.Series] = {}
    for nombre in caras_activas:
        cara = caras_geom[nombre]
        if abs(cara.tilt_deg) < _TILT_HORIZONTAL_TOL_DEG:
            # Plano horizontal: la transposición Liu-Jordan se reduce
            # algebraicamente a GHI (directa·cos0 + difusa·1 + reflejada·0).
            # Se evita la llamada a pvlib por costo y para no introducir
            # ruido de punto flotante en el caso histórico (techo plano).
            resultado[nombre] = datos_clima["GHI_Wm2"].clip(lower=0.0)
        else:
            resultado[nombre] = calcular_POA_horizonte(
                datos_clima,
                emplazamiento,
                modelo_difuso=modelo_difuso,
                tilt_deg=cara.tilt_deg,
                acimut_duffie_deg=cara.acimut_duffie_deg,
            )
    return resultado


def series_radiacion_camara(
    datos_clima: pd.DataFrame,
    emplazamiento: "Emplazamiento",
    camara: "Camara",
    *,
    modelo_difuso: str = "isotropic",
) -> tuple[pd.Series, pd.Series]:
    """Series de irradiancia equivalente al producto y potencia al aire.

    Ver docstring del módulo para las fórmulas. Sin cara translúcida activa
    (incluye ``cubierta_translucida_id is None``) devuelve dos series de
    ceros con el índice de ``datos_clima``.

    Args:
        datos_clima: DataFrame horario con GHI/DNI/DHI.
        emplazamiento: Emplazamiento del secador.
        camara: Cámara completamente instanciada.
        modelo_difuso: Modelo de transposición difusa de pvlib.

    Returns:
        Tupla ``(I_eq_prod, Q_rad_aire_W)``: irradiancia equivalente al
        producto [W/m², referida a ``A_rad``] y potencia radiativa que
        calienta el aire vía superficies internas [W].
    """
    c = camara.construccion
    caras_activas = c.caras_translucidas_activas()
    if not caras_activas:
        ceros = pd.Series(0.0, index=datos_clima.index)
        return ceros.copy(), ceros.copy()

    g = camara.geometria
    b = camara.bandejas
    caras_geom = g.caras()
    f = factores_intercepcion(camara)
    poas = poa_caras_camara(datos_clima, emplazamiento, camara, modelo_difuso=modelo_difuso)

    A_rad = c.A_rad_m2 if c.A_rad_m2 is not None else b.area_bandeja_m2
    tau = float(catalogo.CUBIERTAS[c.cubierta_translucida_id]["transmitancia_solar"])

    suma_prod: pd.Series | None = None
    suma_aire: pd.Series | None = None
    for nombre in caras_activas:
        area_i = caras_geom[nombre].area_m2
        f_i = f[nombre]
        poa_i = poas[nombre]
        termino_prod = f_i * area_i * poa_i
        termino_aire = (1.0 - f_i) * area_i * poa_i
        suma_prod = termino_prod if suma_prod is None else suma_prod + termino_prod
        suma_aire = termino_aire if suma_aire is None else suma_aire + termino_aire

    I_eq_prod = suma_prod / A_rad
    Q_rad_aire_W = tau * c.absortancia_interior * suma_aire
    return I_eq_prod, Q_rad_aire_W


def factores_sinteticos(camara: "Camara") -> tuple[float, float]:
    """Factores escalares para el modo Sintético (sin serie real de clima).

    En modo Sintético ``I_g_max`` es un escalar interpretado como la
    irradiancia pico sobre CADA cara translúcida activa (aproximación: se
    ignoran las diferencias de orientación entre caras, ya que no hay
    posición solar horaria disponible). Dada una semicampana sintética
    ``I_g_sint(t)`` [W/m²] con pico ``I_g_max``:

        I_eq_prod(t)    = factor_prod · I_g_sint(t)
        Q_rad_aire_W(t) = factor_aire · I_g_sint(t)   [W, ya con τ·α_interior]

    Args:
        camara: Cámara completamente instanciada.

    Returns:
        Tupla ``(factor_prod, factor_aire)``. Ambos 0.0 si no hay cara
        translúcida activa. ``factor_prod`` es exactamente 1.0 en el caso
        histórico (techo-solo, ``A_rad`` ≤ área real del techo) — back-compat.
    """
    c = camara.construccion
    caras_activas = c.caras_translucidas_activas()
    if not caras_activas:
        return 0.0, 0.0

    g = camara.geometria
    b = camara.bandejas
    caras_geom = g.caras()
    f = factores_intercepcion(camara)

    A_rad = c.A_rad_m2 if c.A_rad_m2 is not None else b.area_bandeja_m2
    tau = float(catalogo.CUBIERTAS[c.cubierta_translucida_id]["transmitancia_solar"])

    suma_prod = sum(f[nombre] * caras_geom[nombre].area_m2 for nombre in caras_activas)
    suma_aire = sum((1.0 - f[nombre]) * caras_geom[nombre].area_m2 for nombre in caras_activas)
    factor_prod = suma_prod / A_rad
    factor_aire = tau * c.absortancia_interior * suma_aire
    return factor_prod, factor_aire
