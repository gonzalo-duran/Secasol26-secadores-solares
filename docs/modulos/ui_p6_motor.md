<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/p6_motor

Ruta: `ui/p6_motor.py`

## Descripción

Pestaña 6 — Motor / Ventilador.

Dimensiona el sistema de convección forzada calculando la pérdida de carga
total del sistema (colector + cámara + ductos) y la potencia eléctrica del
motor necesaria para vencerla.

Soporta:
    - Motor eléctrico con ventilador axial o centrífugo.

La convección natural no requiere motor (proyecto.motor = None). En ese caso,
se configura la chimenea solar — opcionalmente con extractor eólico en el
tope — desde esta misma pestaña.

## Clases y funciones

**Funciones:**

- `render()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
