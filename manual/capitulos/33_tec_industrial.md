# Técnico · Modo industrial / Gran escala

Referencia técnica de la tipología **Gran escala**: los dos subtipos (batch y
semicontinuo), el banco y el campo de colectores, el caño maestro y la cámara
con gradientes de humedad. La referencia física del subtipo semicontinuo es el
secador híbrido **ADITAL** de San Carlos (Salta). La guía de uso de la
tipología está en [1 · Tipología](?manual=tipologia).

## 1. Qué es el modo industrial {#subtipos}

La tipología **Gran escala** tiene **dos subtipos de igual jerarquía**:

- **BATCH** — secado por lotes (cascada de **N=1** zona).
- **SEMICONTINUO** — túnel a **contracorriente** estilo ADITAL (**N** zonas en
  serie, aire y producto en sentidos opuestos).

**Período = ventana**: en vez del binario diario/anual, el análisis corre sobre
un **lapso real** [inicio, fin] con clima horario (una semana, un mes, una
campaña). La ventana también está disponible para Caja/Armario como multidía
real.

El circuito de aire es: **banco de colectores → caño maestro → (auxiliar) →
cámara/túnel → salida**.

## 2. Colector industrial — banco y campo {#campo}

### 2.1 Banco serie/paralelo {#banco}

El banco combina módulos **en serie** (el aire se calienta progresivamente, la
salida de uno es la entrada del siguiente) y ramas **en paralelo** (reparten el
caudal). Cada módulo se resuelve con el **mismo solver de colector** de los
Tipos 1–4 ([Técnico · Colector](?manual=tec-colector)), hora a hora.

### 2.2 Campo de colectores — reparto real de caudal {#reparto}

En gran escala el reparto de caudal entre ramas **no se asume uniforme**: se
resuelve la **red hidráulica** completa, siguiendo la metodología de **ASHRAE
Handbook 2017, cap. 21 (Duct Design)**:

- **Fricción por tramo** del troncal: Darcy-Weisbach + Haaland, con la sección
  local del caño (constante o creciente).
- **Singulares de boca**: $\Delta P = C\,\rho v^2/2$ (campana de reducción +
  llave mariposa) referidos a la sección de la rama.
- **Igualdad de presión total**: todas las trayectorias (rama $i$ + troncal
  desde su boca al ventilador) ven la **misma** $\Delta P$. El reparto
  $\{q_i\}$ se resuelve por **punto fijo amortiguado** sobre esa igualdad.

Convención: la boca 1 es el extremo lejano al ventilador; el troncal se
discretiza en N tramos y el tramo $i$ transporta el caudal acumulado de las
bocas $1..i$. Cada rama se evalúa térmicamente **a su caudal propio** →
temperatura de salida por rama.

## 3. Caño maestro (manifold) {#cano-maestro}

El **caño maestro** es el manifold que colecta el aire de todas las ramas y lo
lleva al ventilador/cámara. Tiene tres modelos de prediseño:

### 3.1 Pérdida de carga con flujo acumulado {#dp-cano}

El caudal **crece linealmente** a lo largo del caño: $Q(f)=Q_{total}\cdot f$,
con $f=0$ en el extremo lejano y $f=1$ en el ventilador. La fricción se
**integra por tramos** con el caudal y la sección **locales**:
$$
\Delta P_{fric} = \sum_j f_j\,\frac{dx}{D_{h,j}}\,\frac{\rho\,v_j^2}{2},
\qquad v_j = \frac{Q(f_j)}{A_j}
$$
Los accesorios (campana de reducción + llave mariposa de un camino
representativo) se aplican sobre la presión dinámica del extremo del
ventilador: $\Delta P_{acc}=(K_{campana}+K_{mariposa})\,\rho v_{fin}^2/2$.

**Compensación de sección:** un caño de **sección creciente** mantiene la
velocidad acotada a medida que acumula caudal, mientras que un caño chico de
sección constante dispararía la velocidad (y la fricción $\propto v^2$) cerca
del ventilador. El modelo reporta la velocidad máxima a lo largo del caño —
acotada si la sección compensa el caudal acumulado. La clave del modelo es usar
el **flujo acumulado** (no el caudal total constante) para que la compensación
se refleje.

### 3.2 Balance térmico — dos variantes {#dt-cano}

El caño puede estar a la intemperie. El balance da
$\Delta T=(Q_{solar}-Q_{perdida})/(\dot m\,c_p)$:

$$
Q_{perdida} = (U_{lados}A_{resto} + U_{sup}A_{sup})\,(T_{aire}-T_{amb}),
\qquad
Q_{solar} = \tau\,\alpha\,A_{sup}\,I_g
$$

con $U=\big(1/h_{int}+R_{ais}+1/h_w\big)^{-1}$ — film interno por convección
forzada (Dittus-Boelter turbulento, $Nu=3.66$ laminar), conducción del aislante
(si está aislado) y film externo McAdams.

- **Variante sin ganancia solar**: $Q_{solar}=0$ → el aire solo **pierde**
  calor; $\Delta T<0$ (≈ −2.8 °C en el caso ADITAL).
- **Variante con ganancia solar**: la cara superior actúa como mini-colector
  ($Q_{solar}=\tau\alpha A_{sup}I_g$). Si además lleva **cubierta translúcida**,
  la cavidad de aire agrega resistencia ($U_{sup}<U_{lados}$, efecto
  invernadero) y la ganancia se afecta por $\tau$.

**Atención en prediseño:** la absortancia solar default (0.90) es de **chapa
pintada**; el **galvanizado desnudo** necesita $\alpha\approx0.35$.

### 3.3 Uniformidad de distribución {#uniformidad}

Criterio simple: el reparto es uniforme si la $\Delta P$ del troncal es
**pequeña frente a** la $\Delta P$ de una rama:
$\text{ratio}=\Delta P_{cano}/\Delta P_{rama}$, uniforme si $<0.15$.

## 4. Cámara con gradientes de humedad — motor multi-etapa {#cascada}

Batch y semicontinuo son **el mismo motor** de cascada con distinta
**topología**. Reusa intacto el núcleo físico de la cámara (evaporación
difusiva + GAB + coeficientes variables en el tiempo —
[Técnico · Cámara](?manual=tec-camara)).

### 4.1 Batch = cascada de N=1 {#batch}

Un único CSTR con un solo paso de aire. Equivale al motor de armario pero
corrido sobre la ventana de producción, acumulando lotes.

### 4.2 Semicontinuo = N zonas a contracorriente {#semicontinuo}

El túnel tipo ADITAL son **N columnas de carros en serie**:

- El **aire** marcha de la zona $N{-}1$ (extremo seco/caliente, recibe el aire
  del colector+auxiliar) hacia la zona $0$ (extremo fresco/húmedo, descarga al
  ambiente).
- El **producto avanza en sentido opuesto**: entra fresco por la zona $0$ y se
  descarga seco por la zona $N{-}1$.

**Estado integrado:** $y=[T_0,X_0,T_1,X_1,\dots,T_{N-1},X_{N-1}]$ (2N
variables). En cada evaluación del sistema se **marcha el aire** $N{-}1\to0$
(N resoluciones algebraicas **secuenciales** del mismo CSTR): para la zona $i$,
el aire de entrada es la **salida de la zona $i{+}1$** (la vecina más
caliente). **No hay iteración intra-paso**: el producto está cuasi-congelado en
el paso, así que el sistema de aire es lineal y directo.

**Avance de columnas:** con cadencia fija, las columnas saltan una posición
(salto discreto del estado: zona $i \leftarrow$ producto de zona $i{-}1$; zona
$0 \leftarrow$ carga fresca; zona $N{-}1 \rightarrow$ descarga). Entre avances
se integra un tramo con el integrador de EDOs.

**Sequedad de salida emergente:** la cadencia es **fija**; **no** se ajusta
para alcanzar $X_{objetivo}$. La sequedad de salida es un **resultado** del
sistema, no una restricción que se fuerza. $X_{objetivo}$ solo sirve para
**avisar** sub/sobre-secado. El túnel arranca lleno de producto fresco; tras
~N avances alcanza **régimen estacionario** y se reporta el **perfil espacial**
$X(\text{zona})$, $T_{prod}(\text{zona})$, $T_{aire}(\text{zona})$.

## 5. Híbrido con calendario de arranque {#calendario}

El quemador de biomasa opera en **ventanas horarias** de mañana/atardecer
(independiente de la irradiancia), no a potencia constante, y **acumula leña**.
Detalle físico en [Técnico · Calentamiento auxiliar](?manual=tec-auxiliar).

## 6. Orquestación de la ventana {#orquestacion}

Tres capas: las **forzantes** horarias (colector forzado hora a hora + ΔT del
caño maestro + auxiliar con calendario), el **despacho** batch↔cascada según el
subtipo (acumulando producción: kg de producto seco + tasa de régimen kg/día +
leña), y el **punto de entrada** que consume la sección
[7 · Resultados](?manual=resultados) para el dashboard de producción.

## 7. Validación contra ADITAL {#adital}

Un script de validación standalone contrasta la cadena térmica completa contra
datos de campo del secador ADITAL de San Carlos:

| Check | Esperado | Estado |
|---|---|---|
| Salida del colector | ~55 / 78 °C | ✓ |
| ΔT caño maestro | −2.8 °C | ✓ |
| Cámara | 57 °C | ✓ |
| Campaña | 5000 kg en ~5 días | ✓ |

Es un **chequeo de orden de magnitud**, no una calibración: Secasol es un
prediseñador **general**; ADITAL es referencia de dimensiones/caudales/
temperaturas, no objetivo de ajuste.

---

**Ver también:** [1 · Tipología](?manual=tipologia) (dónde se elige el subtipo
y la ventana), [Técnico · Cámara](?manual=tec-camara) (el núcleo físico que la
cascada reusa), [Técnico · Motor y pérdidas de carga](?manual=tec-chimenea),
[Apéndice · Implementación](?manual=apendice-codigo#industrial),
[Bibliografía](?manual=bibliografia#ashrae).
