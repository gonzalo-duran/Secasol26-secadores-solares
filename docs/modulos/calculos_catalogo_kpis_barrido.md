<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/catalogo_kpis_barrido

Ruta: `calculos/catalogo_kpis_barrido.py`

## Descripción

Catálogo de KPIs extraíbles de un resultado de simulación para los barridos.

Cada :class:`KpiBarrido` envuelve un *extractor*: una función tolerante que,
dado un objeto de resultado (``ResultadosCompletos`` en Constantes,
``ResultadosCompletosTransitorio`` en Transitorio, o ``ResultadosAnual``
en Anual), devuelve un escalar ``float`` o ``None`` cuando el campo
no aplica a ese modo. Esa tolerancia (vía ``getattr`` con default) permite que
el mismo catálogo de KPIs sirva a los tres modos sin ramificar en la UI.

Dos grupos:
    - ``KPIS_FIJOS``: los 6 indicadores que siempre se grafican.
    - ``KPIS_AVANZADOS``: extras opt-in (checkbox en un expander de P7).

El campo ``modos_validos`` de cada KPI gobierna en qué modos se ofrece.

## Clases y funciones

**Clases:**

- `KpiBarrido`

**Funciones:**

- `obtener_kpi()`
- `kpis_fijos_para_modo()`
- `kpis_avanzados_para_modo()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
