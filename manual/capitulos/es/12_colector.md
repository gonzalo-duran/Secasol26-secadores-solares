# 3 · Colector solar de aire

El colector es el corazón térmico del secador: convierte radiación solar en aire
caliente. En esta sección se define **qué colector** se usa (tipo, materiales,
geometría) y **cuántos** (banco en serie/paralelo). Secasol modela colectores de
placa plana de aire con un modelo físico de balances por superficie — no una
eficiencia tabulada — así que cada decisión constructiva (una o dos cubiertas,
tipo de placa, espesor de aislante) tiene efecto directo y visible en la
temperatura de salida.

En la tipología **Caja** esta sección no aplica (la caja capta directamente por
su cubierta); aparece con **Armario** y **Gran escala**.

## Elegir el tipo de colector {#tipos}

Secasol ofrece cuatro topologías que comparten materiales y criterios
constructivos y difieren en **dónde está el absorbedor y por dónde circula el
aire**:

| Tipo | Absorbedor | Circulación del aire |
|---|---|---|
| **1** | en el fondo del cajón | por **encima** del absorbedor (canal único) |
| **2** | a media altura (dos canales) | por **ambos** canales (superior + inferior) |
| **3** | a media altura | por el canal **inferior**; el superior queda estanco |
| **4** | a media altura | por el canal **superior**; el inferior queda estanco |

<!-- esquema: colectores_seccion_transversal | Sección transversal comparativa de los 4 tipos. -->

Como guía rápida: el **Tipo 1** es el más simple de construir; los tipos con
absorbedor a media altura aumentan la superficie de intercambio con el aire, y
las variantes con canal estanco (3 y 4) usan esa cavidad de aire quieto como
aislación adicional.

<!-- profundidad: Qué cambia físicamente entre los tipos -->
En el modelo, cada tipo es una topología distinta de balances de energía:

- En el **Tipo 1** el aire intercambia con la cara interna de la cubierta y con
  el absorbedor; cubierta y absorbedor se acoplan además por radiación.
- En el **Tipo 2** el absorbedor entrega calor por convección a **dos** flujos
  (canal superior e inferior), y por radiación a la cubierta y al fondo.
- En los **Tipos 3 y 4** el canal estanco se comporta como una **cavidad de
  convección natural**: la transferencia a través de él se modela con la
  correlación de Hollands para cavidades inclinadas más la radiación entre
  superficies. Eso reduce las pérdidas del lado estanco, a costa de perder esa
  cara como superficie de intercambio con el flujo.

Las ecuaciones completas de los cuatro balances están en
[Técnico · Colector de placa plana](?manual=tec-colector#balances).
<!-- /profundidad -->

## Materiales del colector {#materiales}

Cada componente se elige de un **catálogo de materiales** con propiedades ya
cargadas (transmitancia, absortancia, emisividad, conductividad, rugosidad):

- **Cubierta** — el vidriado superior: policarbonato alveolar, film de
  invernadero, vidrio. Interesa su **transmitancia** $\tau$ (cuánta radiación
  deja pasar) y su emisividad infrarroja (cuánto re-irradia).
- **Placa absorbedora** — la superficie que capta: chapa pintada, chapa
  ondulada, etc. Interesa su **absortancia** $\alpha$ y su rugosidad (afecta la
  pérdida de carga).
- **Aislante** — lana de vidrio, poliestireno, lana de oveja…: su conductividad
  y espesor definen la pérdida por el fondo.
- **Fondo** — el cierre inferior del cajón (chapa, madera).

El número de **cubiertas** puede ser 1 (estándar) o 2: la doble cubierta reduce
las pérdidas hacia arriba a costa de perder algo de transmitancia, y conviene en
climas fríos o ventosos.

<!-- profundidad: Cómo se modela la doble cubierta -->
Con dos cubiertas, la conductancia hacia arriba deja de ser la conducción simple
de una lámina y pasa a ser una **conductancia efectiva** en serie: conducción en
cada lámina + **convección natural de Hollands** en la cavidad de aire entre
cubiertas + **radiación gris** entre superficies paralelas. El espaciado entre
cubiertas es configurable y entra en el número de Rayleigh de la cavidad: si la
cavidad es muy fina domina la conducción; si es muy gruesa, la convección
natural "cortocircuita" parte del beneficio.
<!-- /profundidad -->

## Geometría y condición de diseño {#geometria}

La geometría del módulo se define con **largo** (sentido del flujo), **ancho** y
**espaciado del canal** (la altura por donde circula el aire). Junto con la
**velocidad de diseño** del aire, esto fija el caudal másico y el régimen de
flujo (laminar, transición o turbulento), del que depende fuertemente el
coeficiente de convección interna.

Dos observaciones prácticas:

- Un canal más bajo aumenta la velocidad (mejor transferencia) pero también la
  **pérdida de carga**, que después paga el ventilador o el tiro de la chimenea
  (ver [6 · Motor y chimenea](?manual=motor)).
- El **espesor de la placa absorbedora** se puede configurar pero **no entra al
  balance térmico**: el modelo asume capacitancia térmica de placa despreciable
  (hipótesis cuasi-estacionaria). Es una decisión consciente del modelo, no un
  olvido.

<!-- profundidad: Régimen de flujo y coeficiente convectivo local -->
El coeficiente de convección interna **no es un escalar único**: se evalúa
localmente nodo a nodo a lo largo del colector, con propiedades del aire
variables con la temperatura ($k, \mu, Pr, c_p, \rho$ evaluadas a la temperatura
de película local). En cada nodo se calcula el Reynolds local

$$Re = \frac{G\,D_h}{\mu(T_{film})}, \qquad D_h = \frac{2\,W\,a}{W+a}$$

con $G$ el flujo másico por unidad de área y $D_h$ el diámetro hidráulico del
canal rectangular, y se selecciona automáticamente la correlación de Nusselt
adecuada (Shah-London, Heaton, Gnielinski, Sparrow-Liu, Dittus-Boelter,
Cengel-Ghajar) con transiciones suaves entre regímenes. A baja velocidad o gran
inclinación se suma la componente de **flotación** (convección mixta de
Churchill). El detalle completo, con la tabla de correlaciones y sus rangos,
está en [Técnico · Colector de placa plana](?manual=tec-colector#nusselt).
<!-- /profundidad -->

## Banco de colectores {#banco}

Un solo módulo rara vez alcanza: el **banco** replica el módulo **en serie**
(el aire sale de uno y entra al siguiente, sumando largo de calentamiento) y
**en paralelo** (varias ramas que reparten el caudal total).

- **Serie** sube la temperatura de salida, con rendimiento decreciente: cada
  módulo trabaja con aire más caliente y pierde más. También multiplica la
  pérdida de carga.
- **Paralelo** multiplica el caudal a la misma temperatura de salida.

En **Gran escala** aparece además el **caño maestro**: el manifold que colecta
el aire de las ramas y lo lleva a la cámara, con su propia pérdida de carga y su
balance térmico (puede perder calor al ambiente o ganar por radiación en su cara
superior). Ver [Técnico · Modo industrial](?manual=tec-industrial#cano-maestro).

## Evaluar el colector {#evaluar}

El botón **Calcular colector** corre el modelo con la condición elegida y
muestra temperatura de salida, potencia útil y rendimiento. Las gráficas de
evaluación **diaria** y **anual** usan el clima descargado en
[2 · Emplazamiento](?manual=emplazamiento) y trabajan siempre sobre la
irradiancia **en el plano del colector** (POA), no sobre la global horizontal —
la diferencia la explica [Radiación solar y plano orientado](?manual=radiacion).

Al leer los resultados conviene mirar, además de la temperatura de salida:

- el **rendimiento** del colector (cae cuando el salto térmico sobre el ambiente
  crece — es la firma de Hottel-Whillier-Bliss);
- las **advertencias** de diseño (geometrías fuera de rango, correlación forzada
  fuera de su validez, etc.), que se muestran antes de calcular;
- la **pérdida de carga**, que condiciona la sección
  [6 · Motor y chimenea](?manual=motor).

---

**Ver también:** [Técnico · Colector de placa plana](?manual=tec-colector)
(balances por superficie, correlaciones, solución numérica),
[Radiación solar y plano orientado](?manual=radiacion) (por qué POA),
[4 · Cámara de secado](?manual=camara) (a dónde va el aire caliente).
