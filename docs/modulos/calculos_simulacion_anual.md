<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/simulacion_anual

Ruta: `calculos/simulacion_anual.py`

## Descripción

Modo anual sobre las 8760 h reales del clima.

Reemplaza al esquema de "12 días típicos mensuales" (módulo
``calculos/operacion_anual_camara.py``, eliminado en S57) por una simulación
continua sobre la serie horaria del año: el secador encadena lotes uno tras
otro, cada uno con el clima que efectivamente le tocó, y la producción se
atribuye al mes en que cada lote se descarga.

**Qué gana el usuario respecto del día típico.** El día típico
(``groupby(hour).mean()``) construye un día que nunca está nublado, y el secado
es no lineal: un lote que en el día promedio de julio cierra en 30 h puede no
cerrar nunca durante una racha de mal tiempo. Acá eso aparece: los lotes se
alargan, y los que no llegan quedan contados como frustrados. Además la cantidad
de lotes deja de ser un dato que el usuario asegura (``batches_por_mes``) y pasa
a ser un **resultado**.

**Convención de atribución mensual.** Un lote se cuenta en el mes en que
**termina**, porque es cuando se descarga el producto. Un lote que arranca el 29
de junio y sale el 2 de julio es producción de julio. La energía solar, en
cambio, se integra por mes calendario sobre las horas de ese mes, porque es un
flujo y no un evento.

**Alcance.** El anual simula **encadenado de lotes**, que es cómo opera un
secador batch (tipologías CAJA, ARMARIO y GRAN_ESCALA/BATCH). El túnel
semicontinuo tiene una operación conceptualmente distinta —flujo continuo con
avance de columnas, sin lotes— y no está cubierto todavía; se rechaza con un
error explícito en vez de devolver un número sin sentido.

Ver ``docs/notas/plan_anual_8760.md`` §4 para los límites físicos del modelo
(CSTR de nodo único, colector cuasi-estacionario, y sobre todo: el operador
decide con **pronóstico perfecto**, así que el resultado es la cota superior de
la buena decisión).

## Clases y funciones

**Clases:**

- `PuntoMensualAnual`
- `ResultadosAnual`

**Funciones:**

- `hash_entradas_anual()`
- `simular_anual()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
