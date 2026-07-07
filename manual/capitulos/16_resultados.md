# 7 · Resultados del prediseño

Las secciones 1 a 6 **configuran**; Resultados **resuelve**. Acá Secasol corre
el sistema completo de forma **acoplada** — colector → auxiliar → cámara, con
el lazo de la chimenea cerrado por iteración si corresponde — y entrega el
dashboard, la carta psicrométrica y los archivos de exportación. Es la **fuente
de verdad** del prediseño: los botones "Calcular" de las secciones intermedias
son vistas previas; el número final sale de acá.

## Antes de calcular: coherencia y condiciones {#checklist}

La sección verifica primero que el proyecto sea **coherente** (por ejemplo:
Caja no admite colector ni motor; el auxiliar en serie exige colector) y
muestra el checklist de qué está configurado. Los errores bloquean el cálculo;
las advertencias no, pero conviene leerlas.

En modo **Constantes**, Secasol **sugiere** las condiciones representativas
desde el clima descargado — irradiancia como el quantile 90 de la POA y
temperatura como el quantile 75 — para no obligarte a inventar un número.

## Los tres modos de corrida {#modos}

Según el [modo de análisis](?manual=tipologia#modo-analisis):

- **Constantes** — una foto en condiciones representativas: rápido, ideal para
  iterar el diseño.
- **Transitorio** — el día de diseño (o multidía) hora a hora: trayectorias de
  temperaturas, humedad del producto y flujos.
- **Ventana** — la campaña real: dashboard de **producción** (kg secos, tasa de
  régimen, leña) y, en túnel semicontinuo, el **perfil espacial por zonas**.

## El dashboard {#dashboard}

Las métricas centrales:

- **Tiempo de secado** — cuánto tarda el producto en llegar a la humedad
  objetivo (o cuánto le faltó).
- **COP de secado** — energía de evaporación obtenida por unidad de energía
  invertida: $\mathrm{COP}=m_{agua}L_v/E_{total}$.
- **Fracción solar** — qué parte del calor vino del sol:
  $E_{solar}/(E_{solar}+E_{auxiliar})$.
- **Masa de producto seco** y rendimiento de masa.

más el diagrama **Sankey** del balance de energía y las salidas de cada
subsistema (temperatura de salida del colector, estado del aire en cámara,
caudal natural de la chimenea, consumo del auxiliar). Las **advertencias**
acumuladas de todos los subsistemas se listan juntas: son parte del resultado.

## La carta psicrométrica del proceso {#carta}

La carta traza el **camino real del aire** sobre el diagrama psicrométrico
corregido por altitud: ambiente → colector (calentamiento sensible) → auxiliar
(si hay) → cámara (secado) → salida. Es la radiografía termodinámica del
diseño: de un vistazo se ve cuánto calienta el colector, cuánta humedad levanta
la cámara y qué margen queda. Cómo leerla, paso a paso, está en
[Psicrometría](?manual=psicrometria#carta).

<!-- profundidad: La adiabaticidad del tramo de cámara -->
En los libros, el secado ideal es **adiabático**: el aire se enfría exactamente
lo que se humedece, siguiendo la isentálpica. En Secasol el tramo de cámara
**no se impone adiabático**: sale del balance. Si la cámara pierde calor por
las paredes, el punto de salida cae por debajo de la isentálpica — y esa
desviación es información de diseño (aislar mejor). En el túnel semicontinuo la
carta muestra el camino del aire **zona por zona** a contracorriente.
<!-- /profundidad -->

## Corridas paramétricas (barridos) {#barridos}

Los barridos responden "¿qué pasa si…?" sin rehacer la configuración: se elige
un parámetro (velocidad de aire, área de colector, número de cubiertas…), un
rango de valores, y Secasol corre el prediseño completo para cada punto,
graficando los KPIs (tiempo de secado, COP, fracción solar, temperatura de
salida). Es la herramienta para **comparar diseños** y encontrar rendimientos
decrecientes antes de comprometer dimensiones.

## Exportación {#exportar}

Tres formatos:

- **JSON** — snapshot completo y **reproducible** del proyecto: se puede
  recargar en Secasol y re-correr idéntico, versionar o compartir con un
  colega.
- **TXT** — informe de texto plano para lectura rápida.
- **PDF** — reporte institucional con portada, figuras y tablas: el entregable.

---

**Ver también:** [Técnico · Balance global](?manual=tec-resultados) (cómo se
orquesta el cálculo), [Psicrometría](?manual=psicrometria) (la carta),
[Técnico · Motor y chimenea](?manual=tec-chimenea#picard) (el lazo Picard),
[Introducción](?manual=introduccion) (el flujo de trabajo completo).
