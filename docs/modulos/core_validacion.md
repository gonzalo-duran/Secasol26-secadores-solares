<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/validacion

Ruta: `core/validacion.py`

## Descripción

Dataclasses de validación medido vs simulado (mejora 38, fase 2).

Estructuras puras (sin streamlit ni calculos) que describen una **señal de
referencia** medida por el usuario y cómo interpretarla, para contrastarla contra
la salida simulada. El primer corte de la fase 2 valida la **temperatura de salida
del colector** (caso ideal: prototipo colector 10 m del INENCO).

La ingesta (`calculos/ingesta_referencia.py`) reusa la maquinaria de lectura y
parseo de `clima_medido` (fase 1a). Convención: la señal se guarda en SI (K para
temperatura); las métricas de diferencia (RMSE/MBE/MAE) son invariantes al offset
K↔°C, y la UI muestra °C.

## Clases y funciones

**Clases:**

- `ConfigReferencia`
- `ForzantesMedidas`
- `SenalReferencia`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
