# Convenciones de unidades y ángulos

Secasol es estricto con las unidades y las convenciones angulares: son la
fuente clásica de errores en herramientas de ingeniería. Este capítulo
documenta las reglas para que puedas interpretar cualquier número del programa
(y de este manual) sin ambigüedad.

## Unidades: SI estricto por dentro {#si}

Internamente **todo circula en SI estricto**; la interfaz convierte a unidades
cómodas solo al mostrar y al leer tus entradas:

| Magnitud | Interno (SI) | En la interfaz |
|---|---|---|
| Temperatura | K | °C |
| Presión | Pa | kPa / Pa según contexto |
| Humedad relativa | fracción 0–1 | % |
| Humedad absoluta del aire | $\omega$ [kg agua / kg aire seco] | g/kg en la carta |
| Humedad del producto | $X$ [kg agua / kg seco] (**base seca**) | base seca (y base húmeda como referencia) |
| Tiempo | s | horas / días |
| Caudal másico | kg/s | kg/s o m³/h |
| Irradiancia | W/m² | W/m² |

Dos convenciones que conviene tener presentes al leer resultados:

- La **humedad del producto es base seca** ($X$): puede superar 1 (un producto
  fresco con 90 % de agua en base húmeda tiene $X=9$). La conversión está en
  [Física del secado](?manual=secado#base-seca).
- La **humedad relativa interna es fracción** (0.60, no 60 %) — en las
  ecuaciones de este manual, HR y $a_w$ van siempre en fracción.

## Ángulos: tres convenciones de acimut {#acimut}

El acimut (hacia dónde "mira" el colector) tiene tres convenciones en juego, y
**no se mezclan**:

| Convención | 0° | +90° | Rango | Dónde se usa |
|---|---|---|---|---|
| **UI360** | Norte | Este | [0, 360) | lo que **vos** cargás en [2 · Emplazamiento](?manual=emplazamiento) |
| **Duffie & Beckman** | Sur | Oeste | [−180, +180] | almacenamiento interno y ecuaciones de geometría solar |
| **pvlib** | Norte | Este | [0, 360) | el cálculo de irradiancia dentro de la librería pvlib |

En la interfaz siempre ves **UI360** (0° = Norte, sentido horario, como una
brújula). Las ecuaciones de los capítulos técnicos (por ejemplo el
[ángulo de incidencia](?manual=radiacion#incidencia)) usan la convención de
**Duffie & Beckman**, la estándar de la bibliografía solar.

<!-- profundidad: Las fórmulas de conversión -->
Conversiones exactas (γ = Duffie, α = UI360, ψ = pvlib):

$$
\alpha = (-\gamma) \bmod 360
\qquad\qquad
\gamma = (-\alpha) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

$$
\psi = (180 + \gamma) \bmod 360
\qquad\qquad
\gamma = (\psi - 180) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

Casos de verificación: Sur → γ=0, α=180, ψ=180. Norte → γ=±180, α=0, ψ=0.
Este → γ=−90, α=90, ψ=90. Oeste → γ=90, α=270, ψ=270. En el código, estas
fórmulas viven en un único módulo de conversiones y nunca se duplican.
<!-- /profundidad -->

La **pendiente** β es única en todas las convenciones: 0° = horizontal,
90° = vertical.

## Signos y referencias varias {#signos}

- **Latitud**: negativa en el hemisferio sur (Salta ≈ −24.8°).
- **Longitud**: negativa al oeste de Greenwich (Argentina ≈ −54° a −73°).
- **Tasa de evaporación** $\dot m_w$: positiva = el producto pierde agua;
  negativa = condensación sobre el producto.
- **ΔT del caño maestro**: negativo = el aire llega más frío a la cámara
  (pérdida), positivo = ganancia solar del caño.
- **Ángulo de la cavidad** en la correlación de Hollands: medido desde la
  horizontal, válido hasta 75°.

---

**Ver también:** [Radiación solar y plano orientado](?manual=radiacion) (dónde
se usan estas convenciones), [Glosario](?manual=glosario) (símbolos y
términos).
