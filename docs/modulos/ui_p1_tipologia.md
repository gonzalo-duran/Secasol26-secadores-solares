<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/p1_tipologia

Ruta: `ui/p1_tipologia.py`

## Descripción

Pestaña 1 — Tipología y Configuración del Análisis.

Permite al usuario:
    - Definir los metadatos del proyecto (nombre, autor, notas).
    - Seleccionar la tipología del secador (CAJA, ARMARIO, GRAN_ESCALA).
    - Configurar el tipo de análisis (DIARIO o ANUAL) y el criterio de día.

Los cambios se aplican de inmediato a st.session_state.proyecto.
Si la tipología cambia a CAJA, colector y motor se anulan automáticamente
(la tipología CAJA no admite colector externo ni motor).

i18n (F1): todos los textos visibles pasan por ``t()`` con claves ``p1.*``
(ver ``ui/idiomas/``). Los widgets de opciones usan como options los enums
(valores estables) + ``format_func`` — nunca el rótulo traducido como valor.

## Clases y funciones

**Funciones:**

- `render()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
