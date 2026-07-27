<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/catalogo_rugosidades

Ruta: `calculos/catalogo_rugosidades.py`

## Descripción

Catálogo de rugosidades aerodinámicas del terreno para el perfil de viento.

La longitud de rugosidad z₀ caracteriza cuánto frena el terreno al viento cerca
del suelo y fija la forma del perfil logarítmico de capa límite
(``calculos/perfil_viento.py``). Es una propiedad **del sitio**, igual que el
albedo del suelo: la consumen tanto la ingesta de clima medido (para normalizar
el anemómetro del usuario a los 2 m del contrato de ``Clima``) como el extractor
eólico de la chimenea (para llevar el viento al tope).

Los valores siguen la clasificación de Davenport-Wieringa, estándar en ingeniería
de viento y adoptada por la Eurocódigo EN 1991-1-4 y la WMO. El módulo es puro
(sin Streamlit) y testeable.

Referencias
-----------
- Wieringa, J. (1992). "Updating the Davenport roughness classification".
  J. Wind Eng. Ind. Aerodyn. 41, 357-368.
- EN 1991-1-4 (Eurocódigo 1, acciones del viento), tabla de categorías de terreno.

## Clases y funciones

**Funciones:**

- `id_desde_z0()`
- `z0_desde_id()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
