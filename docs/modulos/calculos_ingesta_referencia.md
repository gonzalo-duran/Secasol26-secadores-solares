<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/ingesta_referencia

Ruta: `calculos/ingesta_referencia.py`

## Descripción

Ingesta de la señal de referencia medida (mejora 38, fase 2).

Parsea el archivo de validación del usuario (CSV/.xls/.xlsx) y produce una
`SenalReferencia` en SI, reusando la maquinaria de lectura y parseo de
`clima_medido` (fase 1a): lectura de tablas, timestamps serial-Excel/texto,
limpieza de marcadores, inferencia de frecuencia y regularización de grilla.

Errores con prefijo ``VREF_``. Convención de unidades: la señal se guarda en SI
(K para temperatura). La lectura de hojas/tablas la hace la UI directamente con
`clima_medido.listar_hojas`/`leer_tabla`.

## Clases y funciones

**Funciones:**

- `ingerir_referencia()`
- `ingerir_clima_forzante()`
- `ingerir_forzantes_camara()`
- `alinear_con_simulada()`
- `evaluar_ajuste()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
