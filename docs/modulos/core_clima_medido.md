<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/clima_medido

Ruta: `core/clima_medido.py`

## Descripción

Dataclasses de configuración y reporte para la ingesta de datos climáticos medidos.

Mejora 38, fase 1a. Este módulo define los tipos puros (sin pandas pesado ni
streamlit) que describen CÓMO interpretar un archivo de datos medidos por el
usuario (mapeo de columnas, unidades, zona horaria, convención de timestamp) y
QUÉ encontró el control de calidad físico al procesarlo.

El pipeline que los consume vive en ``calculos/clima_medido.py``. El objeto
``core.clima.Clima`` referencia estos tipos (campos ``mapeo`` y ``qc``); la
dirección de import es clima → clima_medido (este módulo no importa nada de
``core.clima``).

Contiene:
    - Constantes de procedencia por columna (PROCEDENCIA_*).
    - VARIABLES_MAPEABLES y UNIDADES_POR_VARIABLE: qué se puede mapear y en qué
      unidades de origen.
    - MapeoColumna / ConfigMapeoClima: configuración declarativa de la ingesta.
    - ChequeoQC / ReporteQC: resultado del control de calidad físico.

## Clases y funciones

**Clases:**

- `MapeoColumna`
- `ConfigMapeoClima`
- `ChequeoQC`
- `ReporteQC`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
