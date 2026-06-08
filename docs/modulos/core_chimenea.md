<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/chimenea

Ruta: `core/chimenea.py`

## Descripción

Chimenea solar — componente independiente del lazo aerodinámico.

Almacenada en ``Proyecto.chimenea`` (top-level), independiente del colector
porque puede usarse tanto en tipologías con colector externo (ARMARIO,
GRAN_ESCALA) como en CAJA (donde ``Proyecto.colector`` es ``None``).

El modelo numérico del tiro térmico vive en ``calculos.chimenea_calc``.
Este módulo solo define la dataclass de configuración y sus advertencias
estáticas de diseño.

## Clases y funciones

**Clases:**

- `Chimenea`

**Funciones:**

- `advertencias_chimenea()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
