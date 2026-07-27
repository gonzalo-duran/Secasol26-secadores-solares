<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/carga_proyecto

Ruta: `ui/componentes/carga_proyecto.py`

## Descripción

Carga de un proyecto completo desde el JSON que exporta P7.

P7 sabía **guardar** el proyecto entero (``prediseno_completo.json``) pero no
había forma de volver a cargarlo: solo existían cargadores por sección
(colector en P3, cámara en P4, auxiliar en P5, motor/chimenea en P6), y ni
siquiera servían para el archivo completo, porque ``parsear_json_seccion``
valida el campo ``seccion`` de la raíz —que dice ``"prediseno_completo"``— y lo
rechazaba. Meta, configuración y emplazamiento no se cargaban en ningún lado.
Resultado: el snapshot completo era un artefacto de archivo, no un "guardar
proyecto" (S58).

Este módulo desarma ese JSON y reparte cada sub-dict al deserializador que ya
existía. Es la capa de plomería: no reimplementa ninguna reconstrucción.

**El clima no viaja en el snapshot** — solo su metadato (año, fuente, calidad),
porque las 8760 filas harían un archivo enorme. Al cargar se restauran los
parámetros con los que se lo descargó y se avisa que hay que volver a traerlo en
P2; como la caché parquet es por (lat, lon, año), en general es instantáneo.

## Clases y funciones

**Clases:**

- `ErrorCargaProyecto`

**Funciones:**

- `cargar_proyecto_completo()`
- `resumen_clima_snapshot()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
