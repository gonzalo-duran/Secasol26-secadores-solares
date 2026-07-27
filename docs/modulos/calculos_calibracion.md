<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/calibracion

Ruta: `calculos/calibracion.py`

## Descripción

Calibración 1-D contra datos medidos (mejora 38, fase 3).

Motor **puro** (sin streamlit ni el colector) que barre los valores candidatos de
un parámetro y se queda con el que **minimiza una función objetivo** de ajuste
(RMSE, |MBE| o MAE) contra una señal medida. Es la automatización del barrido
manual de la fase 2: para cada valor del parámetro se evalúa el modelo, se
comparan simulado vs medido (``metricas_validacion``) y se elige el óptimo.

El motor recibe un ``evaluar_fn(valor) -> MetricasAjuste | None`` (closure que el
llamador arma: setea el parámetro, corre el modelo y alinea contra el medido),
por lo que no depende de la capa de simulación ni de la UI y es reusable/testeable.

## Clases y funciones

**Clases:**

- `PuntoCalibracion`
- `ResultadoCalibracion`

**Funciones:**

- `calibrar_1d()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
