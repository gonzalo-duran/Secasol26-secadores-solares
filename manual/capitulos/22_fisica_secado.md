# Física del secado — el lado del producto

La [psicrometría](?manual=psicrometria) describe el aire; este capítulo
describe el **producto**: cómo se cuantifica su humedad, por qué el agua
"ligada" cuesta más de sacar que el agua libre, y cómo la **isoterma de
sorción** gobierna la velocidad del secado. Es el fundamento del modelo de
cámara ([Técnico · Cámara](?manual=tec-camara#producto)).

## Humedad en base seca {#base-seca}

Secasol trabaja la humedad del producto en **base seca**:

$$
X = \frac{M_{agua}}{M_{seca}} \quad \left[\frac{\text{kg agua}}{\text{kg seco}}\right]
$$

mientras que el uso comercial habla en **base húmeda**
($w = M_{agua}/M_{total}$, el "% de humedad" de una etiqueta). La conversión:

$$
X = \frac{w}{1-w}, \qquad w = \frac{X}{1+X}
$$

Un tomate fresco con 94 % de humedad (base húmeda) tiene $X_0 \approx 15.7$ kg
de agua por kg de materia seca; el deshidratado final a 10 % base húmeda,
$X_{obj} \approx 0.11$. La base seca es la natural para los balances porque la
masa seca **se conserva** durante el proceso: la masa de producto seco
resultante es $M_{total}/(1+X_0)\cdot(1+X_{obj})$.

## Actividad de agua {#actividad}

No toda el agua del producto está igualmente disponible. La **actividad de
agua** $a_w$ [0–1] mide cuán "libre" está: es la humedad relativa de equilibrio
del aire en contacto íntimo con el producto.

- Producto muy húmedo: $a_w \to 1$ — el agua se comporta casi como agua libre
  y evapora fácil.
- Producto casi seco: $a_w \ll 1$ — el agua restante está adsorbida en la
  matriz sólida y cuesta mucho más extraerla.

$a_w$ importa doblemente: gobierna la **velocidad de secado** (ver abajo) y es
el criterio de **conservación** — por debajo de $a_w \approx 0.6$ no crecen
microorganismos, que es el objetivo último del secado.

## La isoterma de sorción (GAB) {#isotermas}

La relación de equilibrio entre la humedad del producto $X$ y su actividad de
agua $a_w$, a temperatura dada, es la **isoterma de sorción**. Secasol usa el
modelo **GAB** (Guggenheim–Anderson–de Boer), el estándar en alimentos:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

con tres parámetros por producto ($X_m$ la monocapa, $C$ y $K$ constantes de
sorción) que vienen en el **catálogo de productos**. El modelo la usa
**invertida**: dado el $X$ actual, obtiene $a_w(X)$.

<!-- profundidad: La inversión analítica de GAB -->
Despejar $a_w$ de la ecuación GAB lleva a una **cuadrática** en $a_w$:

$$
K\,(1-C)\,a_w^2\;X + \left[(C-2)\,K\,X + X_m\,C\,K\right]a_w + X = 0
\;\;\Rightarrow\;\;
a_w = f(X;\,X_m, C, K)
$$

de la que se toma la raíz física en [0, 1]. Al ser analítica (sin iteración),
se evalúa millones de veces dentro del integrador sin costo. Si un producto del
catálogo no tiene parámetros GAB calibrados, el sistema **advierte** que la
curva de frenado es genérica.
<!-- /profundidad -->

## Cómo la isoterma gobierna la velocidad de secado {#velocidad}

El motor de cámara calcula la evaporación en forma **difusiva**:

$$
\dot m_w = K_m\,A_{prod}\,\big(\underbrace{\omega_{sat}(T_{prod})\cdot a_w(X)}_{\omega_{sup}} - \omega_{flujo}\big)
$$

La fuerza motriz es la diferencia entre la humedad de la **capa de aire pegada
al producto** ($\omega_{sup}$) y la del flujo. Y ahí trabaja la isoterma: a
medida que el producto se seca, $a_w(X)$ **cae**, $\omega_{sup}$ baja, la
fuerza motriz se achica y la tasa de secado **disminuye sola**.

Así aparecen los períodos clásicos del secado **sin ninguna curva empírica**:

- **Período de tasa ~constante** (producto húmedo, $a_w\approx1$): la
  evaporación la limita el aire (temperatura, humedad, velocidad), no el
  producto. El producto se mantiene cerca de la temperatura de bulbo húmedo.
- **Período de tasa decreciente** (producto secándose, $a_w<1$): la matriz
  retiene el agua restante; la tasa cae y la temperatura del producto sube
  hacia la del aire.

La consecuencia práctica: las **últimas décimas de humedad son las más caras**
en tiempo y energía. Secar más allá del objetivo de conservación desperdicia
horas de sol.

## La temperatura del producto {#temperatura}

El producto tiene su propia dinámica térmica: recibe calor sensible del aire y
gasta calor latente en evaporar,

$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = h_{conv}A_{prod}(T_{flujo}-T_{prod}) - \dot m_w\,L_v
$$

Mientras evapora fuerte, el término latente lo mantiene **frío** (cerca del
bulbo húmedo); cuando el secado se frena, su temperatura sube hacia la del
aire. Esto importa para la **calidad**: la temperatura máxima admisible del
producto (color, nutrientes, caso de hierbas y hongos) suele ser la restricción
que limita la temperatura de operación del secador.

---

**Ver también:** [Psicrometría](?manual=psicrometria) (el lado del aire),
[4 · Cámara](?manual=camara#producto) (dónde se configura el producto),
[Técnico · Cámara](?manual=tec-camara#isotermas) (las ecuaciones completas del
balance).
