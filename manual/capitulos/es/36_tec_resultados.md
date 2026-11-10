# Técnico · Balance global y resultados

Referencia técnica de la integración final: cómo la sección Resultados resuelve
el sistema completo de forma acoplada, los tres modos de cálculo, el balance
energético, la carta psicrométrica del proceso, las corridas paramétricas y la
exportación. La guía de uso está en [7 · Resultados](?manual=resultados).

## 1. Resultados como fuente de verdad {#fuente-de-verdad}

Las secciones 1–6 **configuran** el sistema (cada una escribe en el objeto de
proyecto central). **La sección Resultados es la que resuelve todo de forma
acoplada** y es la **fuente de verdad**: las vistas previas de las secciones
intermedias (botones "Calcular X") usan heurísticas o modelos preliminares; el
número final, con el lazo de Picard completo, sale de Resultados.

**Flujo conceptual:** configuración (secciones 1–6) → proyecto central →
balance global acoplado → dashboard + reporte.

## 2. Verificación de coherencia {#coherencia}

Antes de calcular se verifican las **invariantes cruzadas** del proyecto: por
ejemplo, Caja no admite colector externo ni motor y exige al menos una cara
translúcida;
auxiliar en serie poscolector exige colector; motor exige cámara; análisis
anual no aplica a Caja. Los errores se muestran y bloquean el cálculo
inconsistente.

También se fija la **presión representativa** del emplazamiento (media anual
del clima si hay; atmósfera estándar por altitud si no; 101325 Pa de fallback)
— un único valor para colector, cámara y psicrométricas.

## 3. Tres modos de cálculo {#modos}

Según el [modo de análisis](?manual=tipologia#modo-analisis), el cálculo enruta
a uno de tres pipelines:

| Modo | Forzantes |
|---|---|
| **Constantes** | condiciones representativas únicas (T, irradiancia, viento, HR) |
| **Transitorio** | horizonte horario (día de diseño / multidía) |
| **Ventana** | lapso real [inicio, fin] con clima horario (gran escala / multidía) |

Los tres encadenan **colector → auxiliar → cámara** y, si hay chimenea, cierran
el **lazo natural por Picard**
([Técnico · Motor y chimenea](?manual=tec-chimenea#picard)). La armadura de
forzantes del aire construye $T_{ent}$, $\omega_{ent}$, $\dot m$, la
**irradiancia equivalente** sobre las caras translúcidas de la cámara (POA por
cara con reparto producto/aire —
[Técnico · Cámara](?manual=tec-camara#techo-translucido)) y la **POA sobre el
plano del colector** ([Radiación solar](?manual=radiacion)).

### Sugerencia automática de irradiancia (modo Constantes) {#sugerencia}

Para no obligar al usuario a inventar un valor "representativo", se sugieren
condiciones desde el clima descargado: el **quantile 90 de la POA**
representativa (transposición Liu-Jordan; en Caja, de la **irradiancia
equivalente** sobre las caras translúcidas de la cámara) y el quantile 75 de la
temperatura ambiente. Si no hay POA, cae al q90 de GHI (conservador).

## 4. Balance energético integrado {#balance-energetico}

El resultado integra el **balance energético completo**:

$$
E_{total}=E_{solar,util}+E_{auxiliar}+E_{motor},
\qquad
E_{secado}=m_{agua}\,L_v
$$
$$
\mathrm{COP}_{secado}=\frac{m_{agua}\,L_v}{E_{total}},
\qquad
\text{Fracción solar}=\frac{E_{solar}}{E_{solar}+E_{auxiliar}}
$$

más **tiempo de secado**, **masa de producto seco** ($m_{tot}/(1+X_0)$),
rendimiento de masa, las salidas de cada subsistema (colector, auxiliar,
cámara, chimenea) y las advertencias/errores acumulados. El dashboard muestra
métricas, un **Sankey** simplificado de energía y, según el modo:

- **Transitorio:** trayectorias horarias (temperaturas, humedad del producto,
  flujos).
- **Ventana (gran escala):** **dashboard de producción** — kg secos, tasa de
  régimen (kg/día), leña, y **perfil espacial del túnel** en semicontinuo.
- **Anual:** panel de detalle mensual si la sección Cámara calculó la
  operación anual (con las cuatro eficiencias de Augustus Leon: drying, pickup,
  térmica y total).

## 5. Carta psicrométrica del proceso {#carta}

> **Desactivada temporalmente (versión 1.4.1).** La carta psicrométrica del proceso se retiró de la pestaña 7 y del reporte PDF mientras se revisan sus resultados. Volverá en una versión posterior. El resto del cálculo no cambia.

La **carta psicrométrica corregida por altitud** traza el proceso real del
aire (implementación propia, sin librería externa):

$$
\text{Ambiente} \to \text{colector (sensible, } \omega \text{ cte)}
\to \text{auxiliar (+T, } \omega \text{ cte)}
\to \text{cámara (secado)} \to \text{salida}
$$

El tramo de cámara es **adiabático o no-adiabático según emerge del balance**
(no se impone): si la cámara pierde calor a las paredes, el proceso se aparta
de la isentálpica. El estado representativo se toma al **mediodía solar**. En
el **túnel semicontinuo** se traza el **camino del aire por zonas** a
contracorriente. Cómo leer la carta está explicado en
[Psicrometría](?manual=psicrometria#carta).

## 6. Corridas paramétricas (barridos) {#barridos}

Los barridos permiten **comparar diseños** variando un parámetro (geometría,
caudal, materiales…) y midiendo KPIs (tiempo de secado, COP, fracción solar,
temperatura de salida…):

- Se muta un campo del proyecto por su ruta (ej.
  `colector.unidad.velocidad_diseno_ms`) sobre un clon del proyecto (sin
  re-descargar clima).
- Cada valor despacha el motor correspondiente y extrae los KPIs, reportando
  también los puntos que no convergieron.

Sirve para responder "¿qué pasa si duplico el área de colector / cambio el
caudal / uso doble cubierta?" sin rehacer la configuración a mano.

## 7. Exportación {#exportacion}

El proyecto completo se exporta en tres formatos:

| Formato | Qué | Para qué |
|---|---|---|
| **JSON** | snapshot serializado del proyecto + resultados | **reproducible**: se puede recargar y re-correr idéntico |
| **TXT** | informe de texto plano | lectura rápida / pegar en un mail |
| **PDF** | reporte con portada institucional, figuras y tablas | **entregable** para terceros |

El JSON serializa **cada componente** (colector, cámara, auxiliar,
motor/chimenea) — así se puede versionar un diseño, compartirlo o reabrirlo.

## 8. Flujo de trabajo de punta a punta {#flujo}

1. **Tipología** — tipo de secador y modo de análisis.
2. **Emplazamiento** — lat/lon → descarga NASA POWER → POA vs GHI.
3. **Colector** — tipo, materiales, geometría, banco → evaluación gráfica.
4. **Cámara** — geometría, pared, producto, carga, bandejas.
5. **Auxiliar** (opcional).
6. **Motor** o chimenea → ΔP del sistema.
7. **Resultados** — corrida acoplada completa → dashboard + carta
   psicrométrica + exportar JSON/TXT/PDF.

El flujo es **guiado pero flexible**: cada sección escribe en el proyecto
central; se puede ir y volver, y Resultados integra todo con el lazo iterativo.

---

**Ver también:** [7 · Resultados](?manual=resultados) (guía de uso),
[Técnico · Motor y chimenea](?manual=tec-chimenea#picard) (el lazo Picard),
[Psicrometría](?manual=psicrometria) (la carta),
[Apéndice · Implementación](?manual=apendice-codigo#resultados),
[Bibliografía](?manual=bibliografia#leon).
