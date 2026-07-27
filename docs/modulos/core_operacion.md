<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/operacion

Ruta: `core/operacion.py`

## Descripción

Configuración de operación del secador — cómo lo maneja el operador.

Separa las decisiones de **operación** (a qué hora se carga, si se mira el cielo
antes de llenar) de la descripción **física** del equipo (`core/camara.py`,
`core/colector.py`) y del escenario de **análisis** (tipología, modo, ventana).

Vive en `core/` y no en `calculos/` porque forma parte del modelo de datos: cuelga
de `Configuracion.politica_recarga`, viaja en el snapshot `.json` del proyecto y
entra en la huella de vigencia del resultado anual. `calculos/simulacion_ventana.py`
—que es quien la consume— la reexporta por compatibilidad, porque nació ahí en S57
antes de que hubiera un proyecto que la persistiera.

## Clases y funciones

**Clases:**

- `PoliticaRecarga`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
