# El catálogo de productos

La [física del secado](?manual=secado) explica *cómo* se seca un producto; este
capítulo describe *qué* productos trae Secasol, cómo se eligieron, con qué datos
están cargados y qué significa cada campo del catálogo. Es la contraparte
aplicada del capítulo de física: ahí están las ecuaciones, acá están los
tomates, las manzanas y la algarroba con sus números.

El catálogo vive en `catalogo/productos/*.yaml` y se elige desde
[4 · Cámara](?manual=camara#producto).

## Cómo se seleccionaron los productos {#seleccion}

El criterio no fue "los productos más secados del mundo" sino **relevancia para
las regiones donde Secasol se va a usar** — el NOA, Cuyo, el Litoral — más
algunos productos nativos de valor cultural y económico:

- **Hortalizas** de amplia disponibilidad regional (tomate, papa de la Puna,
  cebolla de Cuyo, pimiento para pimentón salteño).
- **Frutas** de los cinturones frutícolas (manzana del Alto Valle, durazno,
  ciruela mendocina) y un **tubérculo andino**, el yacón, de producción
  tradicional en Jujuy y Salta.
- **Hojas aromáticas** de exportación (orégano del NOA, yerba mate del Litoral).
- Productos **nativos e identitarios** como la **algarroba** (harina, patay,
  arrope), con literatura argentina disponible incluido trabajo del propio
  INENCO.

Cada producto se cargó a partir de **literatura científica publicada** (papers
de cinética e isotermas, referenciados en el catálogo y en la
[bibliografía](?manual=bibliografia#productos)); donde no había datos directos,
se estimó **por analogía** con un producto morfológicamente parecido, y eso se
declara explícitamente (ver
[Casos que piden cuidado](?manual=catalogo-productos#cuidados)).

## Los productos disponibles {#disponibles}

Hoy el catálogo trae **19 productos** en 5 categorías. La humedad inicial típica
está en base seca (kg de agua por kg de materia seca — ver
[base seca](?manual=secado#base-seca)); el estado GAB indica si la isoterma de
sorción está calibrada o pendiente (ver
[calibración](?manual=catalogo-productos#calibracion)).

| Producto | Categoría | X₀ típico (kg/kg ms) | GAB |
|---|---|---|---|
| Tomate | Hortaliza | 15.7 (~94 % bh) | pendiente |
| Papa | Hortaliza | 4.5 | ✓ calibrado |
| Cebolla | Hortaliza | 8.1 | pendiente |
| Pimiento rojo | Hortaliza | 10.7 | ✓ calibrado |
| Zanahoria rallada | Hortaliza | 9.0 | pendiente |
| Perejil | Hortaliza | 5.7 | pendiente |
| Apio | Hortaliza | 22.2 (~96 % bh) | pendiente |
| Mandioca | Hortaliza | 1.9 (~65 % bh) | pendiente |
| Ají rojo | Hortaliza | 3.25 | pendiente |
| Manzana | Fruta | 4.6 | ✓ calibrado |
| Durazno | Fruta | 6.3 | pendiente |
| Yacón | Fruta | 9.0 | ✓ calibrado |
| Granada | Fruta | 2.72 | pendiente |
| Ciruela | Fruta | 9.86 | pendiente |
| Yerba mate | Hoja aromática | 2.3 | pendiente |
| Orégano | Hoja aromática | 5.7 | pendiente |
| Coca | Hoja aromática | 1.3 | pendiente |
| Charqui vacuno | Carne | 3.0 | pendiente |
| Algarroba | Legumbre/fruto | 0.25 (~20 % bh) | pendiente |

Los X₀ son valores **típicos de referencia**; el producto real varía con la
variedad, la madurez y el corte, y por eso en [4 · Cámara](?manual=camara) la
humedad inicial es un dato que cargás vos (el catálogo solo la sugiere).

## Humedad inicial y final {#humedades}

Dos números definen el trabajo de secado de una tanda:

- **Humedad inicial X₀** — cuánta agua trae el producto fresco. Es alta en
  hortalizas y frutas jugosas (tomate ~15.7, apio ~22) y baja en productos ya
  parcialmente secos o leñosos (algarroba ~0.25, mandioca ~1.9).
- **Humedad final u objetivo X_obj** — a dónde se quiere llegar. La fija el
  **criterio de conservación**: por debajo de una actividad de agua de ~0.6 no
  crecen microorganismos ([física del secado](?manual=secado#actividad)). El
  catálogo trae, como referencia, la **humedad de equilibrio con aire seco** de
  cada producto (el X mínimo alcanzable con el aire de ese clima).

Ambas van en **base seca**; la conversión desde el "% de humedad" comercial
(base húmeda) está en [física del secado](?manual=secado#base-seca). Recordá que
las últimas décimas de humedad son las más caras en tiempo y energía: fijar un
X_obj más exigente que el necesario desperdicia horas de sol.

## Qué define cada producto en el catálogo {#campos}

Cada entrada del catálogo tiene:

- **Descripción** — especie, variedad de referencia, región de producción y
  notas de calidad (sensibilidad al pardeado, a la temperatura, etc.).
- **Propiedades básicas** — densidad aparente, calor específico de la materia
  seca, humedad inicial típica y humedad de equilibrio, cada una con su
  **calidad de dato** (ALTA / MEDIA / BAJA) y su fuente.
- **Isoterma de sorción GAB** — los parámetros $X_m, C, K$ que gobiernan la
  velocidad de secado (ver [física del secado](?manual=secado#isotermas)). Es
  **el dato que realmente usa el motor**.
- Metadatos de operación: **categoría**, **fotosensibilidad** (si conviene
  cámara opaca en vez de translúcida) y `tipo_secado`.

<!-- profundidad: Las cinéticas de capa fina son vestigiales -->
El catálogo todavía guarda, para muchos productos, parámetros de **cinética de
capa fina** (curvas de razón de humedad MR(t) tipo Page o Midilli, con su
constante $k$ y exponente $n$). **El motor ya no los usa para calcular**: el
antiguo evaluador de capa fina fue reemplazado por el balance acoplado
calor-masa, donde la curva de secado *emerge* de la difusión gobernada por la
isoterma GAB, no de un ajuste empírico
([Técnico · Cámara](?manual=tec-camara#motor-unico)).

¿Por qué siguen ahí, entonces? Esos bloques `capa_fina:` cumplen hoy una única
función: **filtran qué productos aparecen en el selector** de la sección Cámara.
Son metadato de disponibilidad, no parámetros de cálculo. Al leer una ficha del
catálogo, el número que importa para el resultado es la **isoterma GAB**, no la
cinética de capa fina.
<!-- /profundidad -->

## Estado de calibración {#calibracion}

El catálogo es **rico en estructura pero está a medio poblar**, y conviene
saberlo antes de confiar en un número:

- **4 de 19 productos tienen la isoterma GAB calibrada** con datos publicados:
  **manzana, papa, yacón y pimiento rojo**. En estos, la curva de secado que
  produce el modelo se apoya en una isoterma real.
- Los **15 restantes tienen la isoterma pendiente** (marcada con parámetros
  nulos y el DOI del paper a cargar). Con ellos, el modelo usa una isoterma
  genérica y **el sistema emite una advertencia** avisando que el frenado del
  secado no está calibrado para ese producto.

Esto no invalida el prediseño con un producto pendiente —sirve para dimensionar
en orden de magnitud— pero sí es un dato honesto: un resultado sobre manzana
pesa más que uno sobre ciruela, y la app te lo dice.

## Casos que piden cuidado {#cuidados}

- **Estimados por analogía** — la **coca** hereda parámetros de la yerba mate
  (hoja de arbusto de estructura similar) por escasez de literatura, y el
  **apio** los del perejil. El propio catálogo pide usarlos *con precaución*.
- **Fotosensibles** — orégano, yerba, coca, pimiento rojo, ají rojo, perejil y
  apio degradan color o aceites esenciales con luz UV y calor excesivo; para
  ellos conviene **cámara opaca**, no techo translúcido
  ([4 · Cámara](?manual=camara#techo)).
- **Geometría no estándar** — la **zanahoria rallada** tiene un espesor efectivo
  mucho menor que las rodajas de los ensayos de laboratorio: sus parámetros son
  solo orientativos.
- **Charqui** — la sal modifica fuertemente la isoterma; los parámetros deben
  corresponder al nivel de salado usado.

## Agregar o calibrar un producto {#agregar}

El catálogo está pensado para crecer. Para sumar un producto nuevo o completar
la calibración de uno pendiente:

1. Buscar en la literatura la **isoterma de sorción** (parámetros GAB) y las
   propiedades básicas; el repositorio mantiene un **índice bibliográfico por
   producto** como punto de partida.
2. Cargar los valores en el YAML siguiendo la **plantilla de referencia del
   catálogo**, con su calidad de dato y su fuente.
3. La app valida la estructura al arrancar; si falta la isoterma, el producto
   igual aparece pero **advierte** que usa parámetros genéricos.

El objetivo de largo plazo es que cada producto de interés regional tenga su
isoterma calibrada con datos publicados — es una de las líneas de trabajo
abiertas del proyecto.

---

**Ver también:** [Física del secado](?manual=secado) (la teoría detrás de estos
datos), [4 · Cámara de secado](?manual=camara#producto) (dónde se elige el
producto y se cargan X₀ y X_obj), [Bibliografía](?manual=bibliografia#productos)
(las fuentes de los parámetros).
