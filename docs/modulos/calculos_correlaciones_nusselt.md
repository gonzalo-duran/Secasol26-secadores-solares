<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/correlaciones_nusselt

Ruta: `calculos/correlaciones_nusselt.py`

## Descripción

Catálogo de correlaciones de Nusselt para colectores solares de aire.

Provee todas las correlaciones de transferencia de calor por convección
utilizadas en los 4 tipos de colector solar de aire. El módulo es
independiente del core y de la UI.

Organización
------------
- Dataclass ``CorrelacionNusselt``: metadatos de cada correlación (para UI).
- Funciones ``nusselt_*()``: implementación pura de cada correlación.
- Diccionarios ``CORRELACIONES_FORZADO`` y ``CORRELACIONES_NATURAL``: catálogos.
- Función ``calcular_h_int()``: punto de entrada principal. Selecciona
  automáticamente la correlación más apropiada o usa la indicada por el usuario.

Geometría de canal por tipo de colector
----------------------------------------
- Tipo 1: canal rectangular simple. Pared inferior caliente (absorbedor),
          pared superior fría (cubierta). Flujo por encima del absorbedor.
- Tipo 2: dos canales en paralelo (arriba y abajo del absorbedor).
          Ambas paredes calientes asimétricamente.
- Tipo 3: canal inferior. Pared inferior caliente (absorbedor), pared
          superior fría (cara inferior del absorbedor). Recinto estanco
          superior.
- Tipo 4: canal superior. Pared superior caliente (cara superior del
          absorbedor), pared inferior fría (cubierta). Recinto estanco
          inferior.

Lógica de selección automática (correlacion=None)
--------------------------------------------------
Flujo forzado:
  Re < 2300   → shah_london  (laminar, desarrollado)
               Si L/Dh < 50 → heaton  (laminar, en desarrollo térmico)
  2300–10000  → gnielinski   (transición)
  Re > 10000  → sparrow_liu  (turbulento, 1 pared caliente: Tipos 1, 3, 4)
               → dittus_boelter (turbulento, ambas paredes: Tipo 2)
               → cengel      (si L/Dh < 10, efectos de entrada pronunciados)

Flujo natural:
  → hollands_inclinada (único default; rango θ: 0°–75°)

Unidades
--------
Todas las funciones reciben y devuelven en SI:
  - Re, Ra, Pr: adimensionales
  - L_m, Dh_m: metros
  - theta_deg: grados
  - h_int: W/m²·K

Referencias
-----------
- Shah & London (1978). Laminar Flow Forced Convection in Ducts. Academic Press.
- Heaton, Reynolds & Kays (1964). Int. J. Heat Mass Transfer 7, 763-781.
- Gnielinski (1976). Int. Chem. Eng. 16, 359-368.
- Dittus & Boelter (1930). Univ. Calif. Publ. Eng. 2, 443.
- Sparrow & Liu (1979). Int. J. Heat Mass Transfer 22, 1433-1440.
- Cengel & Ghajar (2014). Heat and Mass Transfer, 5ª ed. McGraw-Hill.
- Hollands, Unny, Raithby & Konicek (1976). Solar Energy 18, 183-193.

## Clases y funciones

**Clases:**

- `CorrelacionNusselt`

**Funciones:**

- `nusselt_shah_london()`
- `nusselt_shah_london_simetrico()`
- `nusselt_heaton()`
- `nusselt_gnielinski()`
- `nusselt_dittus_boelter()`
- `nusselt_sparrow_liu()`
- `nusselt_cengel()`
- `nusselt_hollands_inclinada()`
- `calcular_h_int()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
