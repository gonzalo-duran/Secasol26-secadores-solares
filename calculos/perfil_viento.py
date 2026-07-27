"""
Perfil logarítmico de viento en la capa límite atmosférica.

Matemática pura (sin streamlit, sin dependencias del modelo) para trasladar una
velocidad de viento entre alturas sobre el suelo. Vive en un módulo propio porque
lo necesitan dos capas que no se conocen entre sí: la **ingesta** de clima medido
(``calculos/clima_medido.py``, que normaliza el anemómetro del usuario al contrato)
y el **modelo de chimenea** (``calculos/chimenea_calc.py``, que evalúa el viento en
el tope para el extractor eólico). Antes la fórmula estaba duplicada en ambos, cada
uno con su propia constante de rugosidad — y con referencias de altura distintas,
lo que subestimaba el término motriz del extractor (ver S57).

**Convención de altura del viento (crítica):** ``Clima.WS_ms`` está referido a
**2 m** sobre el suelo (:data:`Z_CONTRATO_M`). Es el nativo de NASA POWER (WS2M) y
la altura a la que la ingesta normaliza las series medidas. Todo consumidor que
necesite el viento a otra altura debe pasar por este módulo declarando
``z_origen_m=Z_CONTRATO_M`` — nunca asumir 10 m.

**Excepción deliberada — `h_w` de McAdams (ADR-006):** los siete call sites de
``h_w = 5.7 + 3.8·v`` (colector Tipo 1, Tipos 2/3/4, pared y techo de cámara, film
externo del caño maestro) **no** pasan por este módulo: consumen el viento de 2 m
tal cual, aunque el equipo esté típicamente entre 0.5 y 1.5 m sobre el suelo. No es
un olvido. La regla de arriba aplica al viento como **variable atmosférica** (el
tope de la chimenea, la ingesta de series medidas), no a la ``v`` empírica de una
correlación de film: McAdams no tiene altura de referencia —sale de Jürges (1924),
placa de 0.5 m en túnel de viento con velocidad de corriente libre— y el scatter de
esa familia de correlaciones (±30–50 %) se come el factor de perfil. El fundamento
completo, la magnitud medida del sesgo y las condiciones para reabrir la decisión
están en ``docs/decisiones.md``. **No "arreglar" la incoherencia sin leer el ADR.**

Perfil de capa límite neutra (Monin-Obukhov simplificado, estratificación neutra):

    v(z) = v(z_ref) · ln(z/z₀) / ln(z_ref/z₀)

La hipótesis de neutralidad es razonable con viento moderado y es la práctica
estándar en ingeniería de secadores; con calma nocturna y fuerte estratificación
estable el perfil real cae más rápido que el logarítmico.
"""

from __future__ import annotations

import math

# Altura de referencia del viento en el contrato de `Clima` (NASA POWER WS2M) [m].
Z_CONTRATO_M: float = 2.0

# Longitud de rugosidad aerodinámica por defecto [m]: rural medio.
# Valores típicos: 0.001 (mar/lago), 0.03 (campo abierto/cultivo bajo),
# 0.05 (rural medio, default), 0.10-0.25 (suburbano), 0.5-1.0 (urbano denso).
Z0_DEFAULT_M: float = 0.05


def factor_altura(
    z_destino_m: float,
    *,
    z_origen_m: float = Z_CONTRATO_M,
    z0_m: float = Z0_DEFAULT_M,
) -> float:
    """Factor multiplicativo del perfil logarítmico entre dos alturas.

    Devuelve ``ln(z_destino/z₀) / ln(z_origen/z₀)``, el número por el que hay que
    multiplicar una velocidad medida en ``z_origen_m`` para llevarla a
    ``z_destino_m``. Se expone aparte de :func:`velocidad_a_altura` porque la
    ingesta de clima aplica el mismo factor a una serie completa de pandas.

    Args:
        z_destino_m: Altura a la que se quiere el viento [m].
        z_origen_m: Altura a la que está referida la velocidad de origen [m].
        z0_m: Longitud de rugosidad aerodinámica del terreno [m].

    Returns:
        Factor adimensional. Devuelve 0.0 si ``z_destino_m`` cae dentro de la capa
        de rugosidad (``≤ z0_m``): ahí no hay viento útil.

    Raises:
        ValueError: ``VIENTO_Z0_INVALIDO`` si ``z0_m ≤ 0``;
            ``VIENTO_Z_ORIGEN_INVALIDO`` si ``z_origen_m ≤ z0_m`` (el perfil no
            está definido: el denominador sería ≤ 0).
    """
    if z0_m <= 0:
        raise ValueError(f"VIENTO_Z0_INVALIDO: z0_m={z0_m} debe ser > 0.")
    if z_origen_m <= z0_m:
        raise ValueError(
            f"VIENTO_Z_ORIGEN_INVALIDO: z_origen_m={z_origen_m} m debe ser > "
            f"z0_m={z0_m} m para que el perfil logarítmico esté definido."
        )
    if z_destino_m <= z0_m:
        return 0.0
    return math.log(z_destino_m / z0_m) / math.log(z_origen_m / z0_m)


def velocidad_a_altura(
    v_ms: float,
    z_destino_m: float,
    *,
    z_origen_m: float = Z_CONTRATO_M,
    z0_m: float = Z0_DEFAULT_M,
) -> float:
    """Traslada una velocidad de viento de ``z_origen_m`` a ``z_destino_m``.

    Args:
        v_ms: Velocidad del viento en la altura de origen [m/s].
        z_destino_m: Altura de interés [m] (p. ej. el tope de la chimenea).
        z_origen_m: Altura de referencia de ``v_ms`` [m]. Por defecto
            :data:`Z_CONTRATO_M` (2 m), la del campo ``Clima.WS_ms``.
        z0_m: Longitud de rugosidad aerodinámica del terreno [m].

    Returns:
        v(z_destino) [m/s]. Devuelve 0.0 si ``v_ms ≤ 0`` o si la altura de destino
        queda dentro de la capa de rugosidad.

    Raises:
        ValueError: propaga las validaciones de :func:`factor_altura`.
    """
    if v_ms <= 0:
        return 0.0
    return v_ms * factor_altura(z_destino_m, z_origen_m=z_origen_m, z0_m=z0_m)
