<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/advertencias

Ruta: `core/advertencias.py`

## Descripción

Clases base del sistema de advertencias y mecanismo de invalidación de resultados.

Contiene:
    - Severidad: Enum con niveles INFO, WARNING, CRITICAL.
    - Advertencia: dataclass frozen que representa un aviso de validación.
    - BloqueResultados: clase base para todos los sub-bloques de Resultados,
      con mecanismo de hash para detectar desactualización.

## Clases y funciones

**Clases:**

- `Severidad`
- `Advertencia`
- `BloqueResultados`

**Funciones:**

- `calcular_hash_entradas()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
