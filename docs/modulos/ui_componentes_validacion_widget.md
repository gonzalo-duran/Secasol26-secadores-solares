<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/validacion_widget

Ruta: `ui/componentes/validacion_widget.py`

## Descripción

Widgets compartidos de validación contra datos medidos (mejora 38).

Helpers de presentación reusados por la validación del **colector** (P3, fase 2/3)
y la de **cámara/producto** (P4/P7, fase 4): tabla de métricas, overlay
medido-vs-simulado y curva de calibración. Son funciones puras que arman objetos
Plotly o listas de filas — no tocan ``st.session_state`` ni el proyecto, así que
se testean sin servidor.

Las etiquetas llegan ya traducidas desde la pestaña llamadora (estos helpers no
llaman a ``t()``), para que el mismo widget sirva a cualquier variable validada.

## Clases y funciones

**Funciones:**

- `filas_metricas()`
- `fig_overlay()`
- `fig_curva_calibracion()`
- `fig_perfil_zonas()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
