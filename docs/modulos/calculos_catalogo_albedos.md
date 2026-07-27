<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/catalogo_albedos

Ruta: `calculos/catalogo_albedos.py`

## Descripción

Catálogo de albedos de superficies usuales para la transposición POA.

El albedo (reflectancia solar de onda corta) de la superficie que rodea al
colector alimenta la componente reflejada del suelo en la POA
(``GHI·ρ·(1−cos β)/2``). Este módulo provee un catálogo curado de superficies
típicas con etiquetas en español, para poblar el desplegable de P3.

Los valores numéricos se toman de la tabla de referencia de pvlib
(``pvlib.albedo.SURFACE_ALBEDOS``) para mantener consistencia con la literatura
solar. El módulo es puro (sin Streamlit) y testeable.

Referencias
-----------
- pvlib.albedo.SURFACE_ALBEDOS (valores de referencia broadband).

## Clases y funciones

**Funciones:**

- `etiqueta_desde_albedo()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
