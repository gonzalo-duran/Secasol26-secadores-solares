<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/perfil_viento

Ruta: `calculos/perfil_viento.py`

## Descripción

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

## Clases y funciones

**Funciones:**

- `factor_altura()`
- `velocidad_a_altura()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
