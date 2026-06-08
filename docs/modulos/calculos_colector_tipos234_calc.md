<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/colector_tipos234_calc

Ruta: `calculos/colector_tipos234_calc.py`

## Descripción

Motor numérico de colectores solares de aire — Tipos 2, 3 y 4.

Tipo 2: absorbedor a media altura, flujo por ambos canales (superior e inferior).
Tipo 3: absorbedor a media altura, flujo por canal inferior, canal superior estanco.
Tipo 4: absorbedor a media altura, flujo por canal superior, canal inferior estanco.

Modelo cuasi-estacionario con discretización espacial en x (dirección del flujo).
En cada nodo x se resuelve un sistema algebraico no lineal para obtener las
temperaturas de las superficies sólidas. Las temperaturas del fluido se integran
con scipy.integrate.solve_ivp.

Geometría común (Tipos 2, 3, 4)
--------------------------------
    cubierta (esp_cub)
    ─────────────────────────────  ← T_cub_e / T_cub_i
    canal superior  (alto_c1)      ← fluido canal superior T_f_cs
    ─────────────────────────────  ← absorbedor T_abs  (espesor despreciable)
    canal inferior  (alto_c2)      ← fluido canal inferior T_f_ci
    ─────────────────────────────  ← cara interna fondo T_int / cara externa T_bot
    aislante        (esp_ais)

Diferencias entre tipos
-----------------------
- Tipo 2: ambos canales activos. Sistema: 2 EDOs + 4 ecuaciones algebraicas.
- Tipo 3: canal inferior activo, canal superior estanco.
          T_f_cs se despeja analíticamente: T_f_cs = (T_cub_i + T_abs) / 2
          Sistema: 1 EDO + 4 ecuaciones algebraicas.
- Tipo 4: canal superior activo, canal inferior estanco.
          T_f_ci se despeja analíticamente: T_f_ci = (T_abs + T_int) / 2
          Sistema: 1 EDO + 4 ecuaciones algebraicas.

Hipótesis
---------
- Cuasi-estacionario: sin acumulación de calor en superficies sólidas.
- Flujo unidireccional en x, desarrollado.
- Sin conducción de calor en el absorbedor (espesor despreciable) → ambas
  caras del absorbedor a T_abs.
- Factor de forma radiativo = 1 en todos los intercambios radiativos internos
  (cubierta↔absorbedor, absorbedor↔fondo interior).
- Absortividad de la cubierta despreciable.
- Propiedades del aire constantes a 323 K (50 °C).
- En Tipo 2: ambos canales comparten T_entrada_K. Los caudales se especifican
  por la velocidad de diseño de cada canal independientemente.

Correlaciones
-------------
- T_cielo:  Swinbank (1963).
- h_viento: McAdams (1954); advertencia para v ≥ 5 m/s.
- h_int:    calculos.correlaciones_nusselt.calcular_h_int().
  - Tipo 2 canal superior: pared="una_pared" (absorbedor + cubierta, pero
    la cubierta es fría → asimétrico; se usa una_pared como aproximación).
  - Tipo 2 canal inferior: pared="dos_paredes" (absorbedor arriba, fondo abajo,
    ambos con flujo de calor → simétrico).
  - Tipos 3 y 4: pared="una_pared" en el canal activo.

Referencias
-----------
- Duffie & Beckman, "Solar Engineering of Thermal Processes", 4ª ed.
- Swinbank, Q. J. R. Meteorol. Soc. 89, 339-348, 1963.
- McAdams, "Heat Transmission", 3ª ed., 1954.
- Ver calculos/correlaciones_nusselt.py para referencias de Nusselt.

## Clases y funciones

**Clases:**

- `ResultadosColectorTipo2`
- `ResultadosColectorTipo3`
- `ResultadosColectorTipo4`

**Funciones:**

- `calcular_colector_tipo2()`
- `calcular_colector_tipo3()`
- `calcular_colector_tipo4()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
