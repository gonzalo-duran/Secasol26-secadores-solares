<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/cano_maestro_calc

Ruta: `calculos/cano_maestro_calc.py`

## Descripción

Física del caño maestro (manifold) del banco de colectores — gran escala (S40).

Tres modelos de prediseño para el caño maestro que colecta el aire de las ramas
del banco y lo conduce al ventilador (estilo túnel ADITAL):

1. **Pérdida de carga** (``estimar_delta_P_cano_maestro``): fricción del tramo
   troncal sobre ``largo_m`` a la velocidad del caudal total, más las pérdidas
   singulares de la campana de reducción y la llave mariposa de un camino
   representativo (las ramas están en paralelo → el ventilador ve un camino).

2. **Balance térmico** (``delta_T_cano_maestro``): el caño no aislado pierde
   calor al ambiente por convección externa pero colecta radiación en su cara
   superior; la pérdida neta del aire suele ser pequeña (≈ 3 °C en ADITAL).

3. **Uniformidad de distribución** (``uniformidad_distribucion``): criterio
   simple de reparto de caudal entre ramas — uniforme si la ΔP del troncal es
   pequeña frente a la ΔP de una rama (colector + accesorios).

Reusa los helpers hidráulicos de ``motor_calc`` (Haaland, densidad, viscosidad).

## Clases y funciones

**Funciones:**

- `estimar_delta_P_cano_maestro()`
- `delta_T_cano_maestro()`
- `uniformidad_distribucion()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
