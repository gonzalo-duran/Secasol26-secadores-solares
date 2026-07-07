# Técnico · Recurso solar y clima del sitio

Referencia técnica del subsistema de clima: descarga de datos NASA POWER,
conversión a SI, política de calidad de datos, y la transposición del recurso
global horizontal (GHI) al plano del colector (POA). La versión introductoria de
estos conceptos está en [Radiación solar y plano orientado](?manual=radiacion) y
la guía de uso en [2 · Emplazamiento y clima](?manual=emplazamiento).

## 1. Qué entrega el subsistema de clima {#series}

A partir de tres datos del usuario —**latitud, longitud, altitud**— más la
**orientación del colector** (pendiente β y acimut γ), Secasol produce una
**serie climática horaria anual** lista para alimentar todos los motores físicos
aguas abajo:

- Series horarias en **SI estricto**: temperatura ambiente [K], GHI/DNI/DHI
  [W/m²], viento [m/s], humedad relativa [fracción 0–1], presión [Pa].
- La **irradiancia sobre plano inclinado y orientado (POA)**, que es la que
  realmente "ve" el colector, calculada por transposición de GHI/DNI/DHI.

La filosofía: el usuario solo pone lat/lon; la misma fuente y librería estándar
de la industria fotovoltaica (NASA POWER + `pvlib`) hacen el resto.

## 2. Descarga de datos — NASA POWER vía pvlib {#nasa-power}

Los datos provienen del servicio **NASA POWER** (*Prediction Of Worldwide Energy
Resources*), reanálisis satelital con cobertura global en grilla de ~0.5°. La
descarga usa `pvlib.iotools.get_nasa_power`, que arma la URL de la API, traduce
los nombres de variables y devuelve un DataFrame horario tz-aware más metadatos
(incluida la **altitud del punto de grilla**).

Variables solicitadas:

| Variable | Código NASA | Unidad | Descripción |
|---|---|---|---|
| ghi | ALLSKY_SFC_SW_DWN | W/m² | global horizontal |
| dni | ALLSKY_SFC_SW_DNI | W/m² | directa normal |
| dhi | ALLSKY_SFC_SW_DIFF | W/m² | difusa horizontal |
| temp_air | T2M | °C | temperatura del aire a 2 m |
| wind_speed_2m | WS2M | m/s | viento a 2 m |
| RH2M | RH2M | % | humedad relativa a 2 m |
| PS | PS | kPa | presión superficial |

El período pedido es el **año calendario completo** (8760 horas).

### Conversión a SI

$$
T:\ °C \to K\ (+273.15) \qquad
P:\ \mathrm{kPa} \to \mathrm{Pa}\ (\times 1000) \qquad
HR:\ \% \to \mathrm{fracción}\ (\div 100)
$$

GHI/DNI/DHI [W/m²] y viento [m/s] no requieren conversión. La única conversión
física de unidades del recurso ocurre en esta capa; de ahí en más todo circula
en SI estricto (ver [Convenciones](?manual=convenciones)).

### Caché transparente {#cache}

Para no golpear la API en cada corrida, el resultado se guarda en **parquet**
con clave **SHA-256 de (lat, lon, año)** (redondeados a 4 decimales). La altitud
del punto de grilla se embebe en los metadatos. Una segunda corrida del mismo
sitio/año lee del disco (instantáneo, sin red).

### Política de huecos (calidad explícita, no silenciosa) {#huecos}

NASA POWER tiene ocasionales valores faltantes. La política es:

- Huecos de **≤ 3 h** consecutivas → **interpolación lineal en el tiempo**.
- Huecos de **> 3 h** → se **dejan como NaN**; un contador de horas bloqueadas
  mayor que cero le indica a la UI que debe pedirle una decisión al usuario.

El conteo de huecos originales, mayor hueco, horas interpoladas y horas
bloqueadas viaja junto a la serie en un objeto de calidad. **No se rellena en
silencio.**

## 3. Del recurso horizontal (GHI) al plano del colector (POA) {#poa}

Este es el corazón físico del subsistema. NASA POWER entrega el recurso sobre
**plano horizontal**; el colector está **inclinado** un ángulo β y **orientado**
con acimut γ. Hay que **transponer**.

### 3.1 Geometría solar (posición del Sol) {#spa}

Para cada timestamp horario se calcula la posición solar con el algoritmo
**SPA** (*Solar Position Algorithm*) de `pvlib`, que devuelve el **cenital
aparente** $\theta_z$ y el **acimut solar** $\gamma_s$. SPA resuelve
internamente, en función de (lat, lon, fecha-hora):

- **Declinación solar** $\delta$ (varía con el día del año $n$):
  $$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$
- **Ángulo horario** $\omega$ (desde el mediodía solar verdadero, con ecuación
  del tiempo y corrección de longitud).
- **Cenital solar**:
  $$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$
  con $\phi$ la latitud.

Secasol **no reimplementa** estas fórmulas: delega en SPA (precisión sub-grado,
incluye refracción y ecuación del tiempo). El **tránsito solar** (mediodía
verdadero) se calcula aparte para elegir la hora representativa del día, sin
depender del máximo horario de GHI.

### 3.2 Ángulo de incidencia sobre el plano {#incidencia}

El **ángulo de incidencia** $\theta_i$ entre el rayo directo y la normal del
plano inclinado (β, γ) es la magnitud clave de la componente directa:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

### 3.3 Transposición de Liu-Jordan (modelo isotrópico) {#liu-jordan}

La irradiancia total sobre el plano (POA) se descompone en **tres
contribuciones** (modelo de Liu-Jordan, difuso isotrópico):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{directa}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{difusa de cielo}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{reflejada del suelo}}\,}
$$

donde:

- $I_b = \mathrm{DNI}$ (directa normal), proyectada por $\cos\theta_i$.
- $I_d = \mathrm{DHI}$ (difusa horizontal), atenuada por el **factor de vista
  del cielo** $(1+\cos\beta)/2$.
- $I = \mathrm{GHI}$ (global horizontal), reflejada por el suelo con **albedo**
  $\rho_g$ y factor de vista $(1-\cos\beta)/2$.

El **albedo** $\rho_g$ es configurable (default 0.25; catálogo de albedos por
tipo de superficie). En código, las tres componentes las suma
`pvlib.irradiance.get_total_irradiance`, al que Secasol le pasa β, γ ya
convertido a convención pvlib, la posición solar SPA, DNI/GHI/DHI y el albedo.

Se usa el modelo **isotrópico** por simplicidad y coherencia entre todos los
pipelines; `pvlib` también soporta Hay-Davies, Reindl, Klucher, King y Perez, y
el parámetro de modelo difuso deja abierta la sustitución.

### 3.4 Hipótesis de la transposición {#hipotesis-poa}

- **Cielo difuso isotrópico**: la difusa se reparte uniforme en la bóveda
  (subestima levemente la circumsolar; conservador para prediseño).
- **Suelo lambertiano** de albedo uniforme.
- **Cada hora se trata como cuasi-instantánea** a la posición solar del bin
  horario (resolución horaria de NASA POWER).
- **Fallback conservador**: si DNI o DHI faltan una hora dada, no se puede
  separar directa/difusa → se asume **POA = GHI** esa hora (subestima POA con
  β>0, pero evita propagar NaN al solver del colector). Valores negativos por
  artefacto numérico cerca del horizonte se recortan a 0.

## 4. Convención de ángulos {#angulos}

El acimut tiene **tres convenciones** y mezclarlas es una fuente clásica de
errores de orientación:

| Convención | 0° | +90° | Rango | Uso |
|---|---|---|---|---|
| **Duffie & Beckman** | Sur | Oeste | [−180, +180] | almacenamiento interno y lógica de cálculo |
| **UI360** | Norte | Este | [0, 360) | entrada del usuario en la sección Emplazamiento |
| **pvlib** | Norte | Este | [0, 360) | cálculo interno de irradiancia |

Conversión usada en la transposición POA:

$$\psi_{pvlib} = (180^\circ + \gamma_{Duffie}) \bmod 360^\circ$$

Verificación: γ=0° (Sur)→ψ=180° ✓; γ=90° (Oeste)→ψ=270° ✓; γ=−90° (Este)→ψ=90° ✓;
γ=±180° (Norte)→ψ=0° ✓. Las fórmulas de conversión **viven en un solo módulo** y
nunca se duplican. El detalle completo está en
[Convenciones de unidades y ángulos](?manual=convenciones).

## 5. Recortes temporales (modos de análisis) {#recortes}

El subsistema también provee los recortes de la serie anual que consumen los
distintos [modos de análisis](?manual=tipologia):

- **Día típico mensual** — promedia hora a hora todos los registros de un mes →
  "día típico" de 24 h. Convierte a hora local antes de agrupar para que el pico
  solar caiga cerca de las 12 locales. Alimenta el modo **Anual** (un batch
  representativo por mes).
- **N días reales consecutivos** — recorta un lapso multidía; si cruza el
  31-dic, trunca y lo marca explícitamente, sin inventar empalmes.
- **Ventana** — recorta el lapso [inicio, fin] mapeado al año de la serie.
  Compartido por las secciones Emplazamiento, Colector y Resultados (modo
  **Ventana**).

---

**Ver también:** [Radiación solar y plano orientado](?manual=radiacion)
(versión introductoria), [2 · Emplazamiento y clima](?manual=emplazamiento)
(guía de uso), [Apéndice · Implementación](?manual=apendice-codigo#emplazamiento)
(dónde vive cada pieza en el código),
[Bibliografía](?manual=bibliografia#duffie-beckman).
