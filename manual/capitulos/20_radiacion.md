# Radiación solar y plano orientado

El colector no "ve" la radiación que reportan las bases de datos meteorológicas:
esas series se miden sobre **plano horizontal**, y el colector está **inclinado y
orientado**. Este capítulo explica las componentes de la radiación solar, cómo se
describe la posición del Sol y cómo Secasol **transpone** el recurso horizontal al
plano del colector (la llamada **POA**, *plane of array*). Es el fundamento de la
sección [2 · Emplazamiento](?manual=emplazamiento) y de todos los cálculos aguas
abajo: **el colector siempre recibe POA, no GHI**.

## Las tres componentes de la radiación {#componentes}

La radiación solar que llega a una superficie se descompone en tres partes, y las
bases de datos (NASA POWER en el caso de Secasol) las reportan por separado:

| Sigla | Nombre | Qué es |
|---|---|---|
| **GHI** | Global horizontal | Total que recibe una superficie horizontal (suma de directa proyectada + difusa). |
| **DNI** | Directa normal | La que viene del disco solar, medida sobre un plano perpendicular al rayo. |
| **DHI** | Difusa horizontal | La que llega desde el resto de la bóveda celeste (dispersada por atmósfera y nubes). |

En un mediodía despejado domina la directa; en un día nublado casi todo el recurso
es difuso. La distinción importa porque cada componente responde **distinto** a la
inclinación del colector: la directa depende del ángulo con que incide el rayo,
la difusa de cuánta bóveda celeste "ve" el plano, y aparece una tercera
contribución nueva — la **reflejada del suelo** — que sobre plano horizontal es
nula.

## La posición del Sol {#posicion-solar}

Para proyectar la componente directa hay que saber dónde está el Sol en cada
momento. La posición se describe con dos ángulos: el **cenital** $\theta_z$
(distancia angular entre el Sol y la vertical) y el **acimut solar** $\gamma_s$
(orientación del Sol sobre el horizonte).

Secasol no reimplementa la astronomía: delega en el algoritmo **SPA**
(*Solar Position Algorithm*) vía `pvlib`, con precisión sub-grado, refracción
atmosférica y ecuación del tiempo incluidas. Con eso, además, calcula el
**mediodía solar verdadero** (tránsito) de cada día, que es la hora que usan las
vistas "día representativo".

<!-- profundidad: Las ecuaciones astronómicas que SPA resuelve -->
Aunque SPA usa un algoritmo de alta precisión, las magnitudes que resuelve son
las clásicas de la geometría solar (Duffie & Beckman):

**Declinación solar** $\delta$ — el ángulo entre el plano ecuatorial y la línea
Tierra-Sol; varía con el día del año $n$:

$$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$

**Ángulo horario** $\omega$ — la posición del Sol respecto del mediodía solar
verdadero (15° por hora), con ecuación del tiempo y corrección de longitud.

**Cenital solar** — combinando latitud $\phi$, declinación y ángulo horario:

$$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$

El complemento de $\theta_z$ es la **altura solar**. Cuando $\theta_z > 90°$ el
Sol está bajo el horizonte y no hay componente directa.
<!-- /profundidad -->

## El ángulo de incidencia {#incidencia}

Un plano inclinado un ángulo $\beta$ y orientado con acimut $\gamma$ tiene una
normal propia. El **ángulo de incidencia** $\theta_i$ es el que forma el rayo
directo con esa normal, y gobierna cuánta directa capta el plano:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

Cuando el Sol está "de frente" al colector, $\cos\theta_i \to 1$ y la captación
directa es máxima; cuando el rayo llega rasante, $\cos\theta_i \to 0$. Nótese que
la fórmula usa el acimut en **convención Duffie & Beckman** (0° = Sur): ver
[Convenciones de unidades y ángulos](?manual=convenciones).

## Del plano horizontal al plano del colector {#transposicion}

Con la posición solar y la geometría del plano, la irradiancia total sobre el
plano del colector se arma sumando tres contribuciones. Secasol usa el modelo de
**Liu-Jordan** (difuso isotrópico):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{directa}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{difusa de cielo}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{reflejada del suelo}}\,}
$$

donde:

- $I_b = \mathrm{DNI}$, proyectada por $\cos\theta_i$: es la componente sensible a
  la orientación.
- $I_d = \mathrm{DHI}$, escalada por el **factor de vista del cielo**
  $(1+\cos\beta)/2$: un plano horizontal ($\beta=0$) ve toda la bóveda (factor 1);
  un plano vertical ve la mitad (factor 0.5).
- $I = \mathrm{GHI}$, reflejada por el suelo con **albedo** $\rho_g$ y factor de
  vista del suelo $(1-\cos\beta)/2$: nula en horizontal, crece al inclinar.

El albedo es configurable en la sección Emplazamiento (default 0.25, con un
catálogo de valores típicos por tipo de superficie: pasto, tierra, nieve, etc.).

<!-- profundidad: Hipótesis del modelo isotrópico y fallback -->
El modelo de Liu-Jordan asume:

- **Cielo difuso isotrópico**: la radiación difusa llega uniforme desde toda la
  bóveda. Subestima levemente la componente circumsolar (el halo brillante
  alrededor del disco solar), lo que lo hace **conservador** para prediseño.
- **Suelo lambertiano** de albedo uniforme (refleja difusamente en todas
  direcciones).
- **Cada hora es cuasi-instantánea**: se evalúa la posición solar del bin horario
  (la resolución de NASA POWER es horaria).

`pvlib` también implementa modelos anisotrópicos (Hay-Davies, Reindl, Klucher,
Perez); Secasol usa el isotrópico por simplicidad y coherencia entre todos sus
pipelines, y deja el parámetro `modelo_difuso` abierto para sustituirlo.

**Fallback conservador:** si en una hora falta DNI o DHI no se puede separar
directa de difusa; esa hora se asume $I_{POA} = \mathrm{GHI}$ (subestima con
$\beta>0$, pero evita propagar `NaN` al solver del colector). Los valores
negativos por artefacto numérico cerca del horizonte se recortan a 0.
<!-- /profundidad -->

## Qué significa esto para tu diseño {#criterios}

Dos reglas prácticas salen directas de la física anterior:

- **Inclinación** $\beta$: inclinar el colector acerca su normal al Sol de las
  horas útiles. Como regla gruesa para uso anual, $\beta \approx$ latitud; para
  favorecer el invierno (sol bajo), $\beta >$ latitud; para el verano,
  $\beta <$ latitud. La sección [3 · Colector](?manual=colector) permite evaluar
  gráficamente el POA resultante día a día y en el año.
- **Orientación** $\gamma$: en el hemisferio sur el colector "mira" al Norte
  (y al Sur en el hemisferio norte). Desviaciones de ±15° cuestan poco; giros
  mayores corren el pico de captación hacia la mañana o la tarde.

La ganancia de transponer no es menor: en sitios de latitud media, un plano bien
inclinado puede captar en invierno bastante más energía que el plano horizontal —
y ese invierno suele ser justamente cuando el secado necesita más ayuda.

---

**Ver también:** [2 · Emplazamiento y clima](?manual=emplazamiento) (dónde se
configura todo esto), [Técnico · Recurso solar y clima](?manual=tec-emplazamiento)
(descarga NASA POWER, política de huecos y detalles de implementación),
[Convenciones de unidades y ángulos](?manual=convenciones) (las tres convenciones
de acimut).
