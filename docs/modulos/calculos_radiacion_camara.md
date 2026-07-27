<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/radiacion_camara

Ruta: `calculos/radiacion_camara.py`

## Descripción

Irradiancia equivalente sobre las superficies translúcidas de la cámara.

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

## Clases y funciones

**Funciones:**

- `factores_intercepcion()`
- `poa_caras_camara()`
- `series_radiacion_camara()`
- `factores_sinteticos()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
