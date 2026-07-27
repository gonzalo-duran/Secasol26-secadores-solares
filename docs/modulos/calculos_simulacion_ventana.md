<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/simulacion_ventana

Ruta: `calculos/simulacion_ventana.py`

## Descripción

Orquestador de ventana — simulación de producción sobre un lapso [inicio, fin].

Para tipología GRAN_ESCALA (S40). Sobre una ventana de producción (clima real
horario, modo VENTANA) acumula la producción del secador según el subtipo:

- **BATCH**: encadena lotes. Corre el motor termodinámico batch; cada vez que el
  producto alcanza X_objetivo cuenta un lote completo, recarga producto fresco
  y continúa con el clima restante de la ventana (recarga *event-driven*).
- **SEMICONTINUO**: corre el túnel a contracorriente (``simular_cascada`` vía
  ``calcular_camara_cascada``) una vez sobre toda la ventana; el producto avanza
  a cadencia fija y la sequedad de salida es emergente.

Métrica de salida: masa de producto seco acumulada en la ventana + tasa de
régimen sostenible (kg/día) + masa evaporada. El consumo de leña del híbrido se
integra en la Fase 4 (hoy queda en 0).

Este módulo recibe las forzantes del aire ya armadas sobre la ventana (T_ent =
salida del colector/auxiliar). El armado de forzantes desde clima real NASA
POWER vive en el wire-up de UI/balance (consume ``clima_calc`` +
``_correr_colector_horizonte``).

## Clases y funciones

**Clases:**

- `LoteVentana`
- `ResultadoVentana`

**Funciones:**

- `simular_ventana()`
- `simular_encadenado_lotes()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
