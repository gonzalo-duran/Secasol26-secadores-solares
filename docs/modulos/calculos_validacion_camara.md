<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/validacion_camara

Ruta: `calculos/validacion_camara.py`

## Descripción

Orquestación de la validación de cámara y producto (mejora 38, fase 4).

Corre la **cámara aislada** forzada con el aire de entrada medido en el propio
ensayo y expone sus salidas como series temporales absolutas, listas para
contrastar contra una señal medida con
``calculos.ingesta_referencia.evaluar_ajuste``.

En el colector (fase 2) esta orquestación vivía en la UI porque dependía de
helpers de esa capa; acá es **pura** (sin streamlit), lo que la hace testeable y
reusable tanto por P4 (series) como por P7 (túnel).

Por qué la cámara **aislada**: el ensayo de un lote es, físicamente, un nodo
único (CSTR), aun cuando el proyecto sea de gran escala en modo batch — el
encadenado de lotes de una ventana es un artefacto de producción, no de física.
Forzarla con el aire medido a su entrada aísla el error del modelo de cámara del
error del colector, que es lo único que permite calibrar sin contaminación.

Limitación conocida del túnel semicontinuo: ``ResultadoCascada`` no guarda
historia temporal por zona, solo perfiles espaciales finales y valores por
avance. Por eso :func:`pares_descarga_tunel` y :func:`perfil_zonas` comparan
contra esos dos objetos, que además son los libres del artefacto
euleriano↔lagrangiano (ver ``docs/notas/plan_datos_medidos_4.md``).

## Clases y funciones

**Funciones:**

- `simular_camara_aislada()`
- `serie_simulada()`
- `unidad_display()`
- `a_display()`
- `pares_descarga_tunel()`
- `perfil_zonas()`
- `evaluar_camara()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
