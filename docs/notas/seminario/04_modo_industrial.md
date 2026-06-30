# 04 · Modo industrial / Gran escala

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: la tipología GRAN_ESCALA y sus dos subtipos, el banco de colectores y su
> pérdida de carga, el caño maestro (2 variantes, sección variable y compensación),
> y la cámara con gradientes de humedad en batch y semicontinuo. Referencia física:
> secador híbrido **ADITAL** de San Carlos (tesis doctoral, cap. 3).

---

## 1. Qué es el modo industrial

Desde S40 la tipología **GRAN_ESCALA** es funcional (antes era cosmética). Tiene
**dos subtipos de igual jerarquía** (`SubtipoGranEscala`):

- **BATCH** — secado por lotes (cascada de **N=1** zona).
- **SEMICONTINUO** — túnel a **contracorriente** estilo ADITAL (**N** zonas en
  serie, aire y producto en sentidos opuestos).

**Período = ventana** (`ModoAnalisis.VENTANA`): en vez del binario diario/anual,
el análisis corre sobre un **lapso real** `[inicio, fin]` con clima horario (una
semana, un mes, una campaña). Desde S44 la ventana también está disponible para
CAJA/ARMARIO (como multidía real).

El circuito de aire es: **banco de colectores → caño maestro → (auxiliar) →
cámara/túnel → salida**.

---

## 2. Colector industrial — banco y campo

### 2.1 Banco serie/paralelo

El banco (`BancoColectores`) combina `n_serie` módulos en serie (el aire se
calienta progresivamente, la salida de uno es la entrada del siguiente) y
`n_paralelo` ramas en paralelo (reparten el caudal). Cada módulo se resuelve con
el **mismo solver de colector** de los Tipos 1–4 (doc 02), hora a hora.

### 2.2 Campo de colectores — reparto real de caudal (S41)

En gran escala el reparto de caudal entre ramas **no se asume uniforme**: se
resuelve la **red hidráulica** completa (`campo_colectores_calc.py`), siguiendo la
metodología de **ASHRAE Handbook 2017, cap. 21 (Duct Design)**:

- **Fricción por tramo** del troncal: Darcy-Weisbach + Haaland, con la sección
  local del caño (constante o creciente).
- **Singulares de boca**: $\Delta P = C\,\rho v^2/2$ (campana de reducción + llave
  mariposa) referidos a la sección de la rama.
- **Igualdad de presión total**: todas las trayectorias (rama $i$ + troncal desde
  su boca al ventilador) ven la **misma** $\Delta P$. El reparto $\{q_i\}$ se
  resuelve por **punto fijo amortiguado** ($\text{damping}=0.5$, hasta 200 iter,
  tol de spread $10^{-3}$) sobre esa igualdad.

Convención: la **boca 1 es el extremo lejano** al ventilador; el troncal se
discretiza en N tramos y el tramo $i$ transporta el caudal acumulado de las bocas
$1..i$. Cada rama se evalúa térmicamente **a su caudal propio** → temperatura de
salida por rama.

### 2.3 Pérdida de carga del colector industrial

Misma física que doc 02 (Haaland sobre el largo total del camino), pero ahora la
$\Delta P$ de una rama es la referencia contra la que se compara el troncal del
caño maestro para juzgar **uniformidad** (§3.3).

---

## 3. Caño maestro (manifold) — elemento propio del modo industrial

El **caño maestro** (`core.colector.BancoColectores.cano_maestro: CanoMaestro`) es
el manifold que colecta el aire de todas las ramas y lo lleva al ventilador/cámara.
Tiene **tres modelos de prediseño** (`cano_maestro_calc.py`):

### 3.1 Pérdida de carga con **flujo acumulado** (clave de la compensación)

El caudal **crece linealmente** a lo largo del caño: $Q(f)=Q_{total}\cdot f$, con
$f=0$ en el extremo lejano y $f=1$ en el ventilador. La fricción se **integra por
tramos** (20 segmentos) con el caudal y la sección **locales**:
$$
\Delta P_{fric} = \sum_j f_j\,\frac{dx}{D_{h,j}}\,\frac{\rho\,v_j^2}{2},
\qquad v_j = \frac{Q(f_j)}{A_j}
$$
Los accesorios (campana de reducción + llave mariposa de un camino representativo)
se aplican sobre la presión dinámica del extremo del ventilador:
$\Delta P_{acc}=(K_{campana}+K_{mariposa})\,\rho v_{fin}^2/2$.

> **Compensación de sección (S41/S42):** un caño de **sección creciente** mantiene
> la velocidad acotada a medida que acumula caudal, mientras que un caño chico
> constante dispararía la velocidad (y la fricción $\propto v^2$) cerca del
> ventilador. La función reporta `v_max_ms` a lo largo del caño — acotada si la
> sección compensa el caudal acumulado. **El fix de S42** fue precisamente usar el
> **flujo acumulado** (no el caudal total constante) para que la compensación se
> refleje.

### 3.2 Balance térmico — **dos variantes** (con y sin ganancia de radiación)

El caño puede estar a la intemperie. El balance da
$\Delta T=(Q_{solar}-Q_{perdida})/(\dot m\,c_p)$:

$$
Q_{perdida} = (U_{lados}A_{resto} + U_{sup}A_{sup})\,(T_{aire}-T_{amb}),
\qquad
Q_{solar} = \tau\,\alpha\,A_{sup}\,I_g
$$

con $U=\big(1/h_{int}+R_{ais}+1/h_w\big)^{-1}$ — film interno por convección
forzada (Dittus-Boelter, $Nu=0.023Re^{0.8}Pr^{0.3}$ turbulento, $Nu=3.66$
laminar), conducción del aislante (si está aislado) y film externo McAdams.

- **Variante SIN ganancia** (`aporte_solar=False`): $Q_{solar}=0$ → el aire solo
  **pierde** calor; $\Delta T<0$ (≈ −2.8 °C en ADITAL).
- **Variante CON ganancia** (`aporte_solar=True`): la cara superior actúa como
  mini-colector ($Q_{solar}=\tau\alpha A_{sup}I_g$). Si además lleva **cubierta
  translúcida**, la cavidad de aire agrega resistencia ($U_{sup}<U_{lados}$,
  efecto invernadero) y la ganancia se afecta por $\tau$.

> **Gotcha de prediseño:** el default `absortancia_solar=0.90` es de **chapa
> pintada**; el **galvanizado desnudo** necesita $\alpha\approx0.35$ (ver
> `validacion/validacion_adital.py`).

### 3.3 Uniformidad de distribución

Criterio simple: el reparto es uniforme si la $\Delta P$ del troncal es **pequeña
frente a** la $\Delta P$ de una rama:
$\text{ratio}=\Delta P_{cano}/\Delta P_{rama}$, uniforme si $<0.15$.

---

## 4. Cámara con gradientes de humedad — motor multi-etapa unificado

Batch y semicontinuo son **el mismo motor** (`camara_termodinamica.simular_cascada`)
con distinta **topología**. Reusa intacto el núcleo físico de la cámara
(evaporación difusiva + GAB + coeficientes variables en t — doc 03).

### 4.1 Batch = cascada de N=1

Un único CSTR con un solo paso de aire. Equivale al motor de armario pero corrido
sobre la ventana de producción, acumulando lotes.

### 4.2 Semicontinuo = N zonas a contracorriente

El túnel tipo ADITAL son **N columnas de carros en serie**:
- El **aire** marcha de la zona $N{-}1$ (extremo seco/caliente, recibe el aire del
  colector+auxiliar) hacia la zona $0$ (extremo fresco/húmedo, descarga al
  ambiente).
- El **producto avanza en sentido opuesto**: entra fresco por la zona $0$ y se
  descarga seco por la zona $N{-}1$.

**Estado integrado:** $y=[T_0,X_0,T_1,X_1,\dots,T_{N-1},X_{N-1}]$ (2N variables).
En cada evaluación del RHS se **marcha el aire** $N{-}1\to0$ (N solves algebraicos
**secuenciales**, reusando `resolver_estado_camara`): para la zona $i$, el aire de
entrada es la **salida de la zona $i{+}1$** (la vecina más caliente). **No hay
Picard intra-paso**: el producto está cuasi-congelado en el paso, así que el
sistema de aire es lineal y directo.

**Avance de columnas:** cada `intervalo_avance_s` las columnas saltan una posición
(salto discreto del estado: zona $i \leftarrow$ producto de zona $i{-}1$; zona $0
\leftarrow$ carga fresca; zona $N{-}1 \rightarrow$ descarga). Entre avances se
integra un tramo con `solve_ivp`.

**Sequedad de salida emergente:** la cadencia es **fija**; **no** se ajusta para
alcanzar $X_{objetivo}$. La sequedad de salida es un **resultado** del sistema
(no una restricción que se fuerza). $X_{objetivo}$ solo sirve para **avisar**
sub/sobre-secado. El túnel arranca lleno de producto fresco; tras ~N avances
alcanza **régimen estacionario** y se reporta el **perfil espacial** $X(zona)$,
$T_{prod}(zona)$, $T_{aire}(zona)$.

---

## 5. Híbrido con calendario de arranque

El quemador de biomasa opera en **ventanas horarias** de mañana/atardecer
(independiente de la irradiancia), no a potencia constante, y **acumula leña**
(`Auxiliar.cargas_arranque: list[CargaArranque]`). Detalle físico en el doc 06.

---

## 6. Orquestación de la ventana

| Capa | Función | Qué hace |
|---|---|---|
| Forzantes | `balance_global.armar_forzantes_ventana` | colector forzado hora a hora + ΔT caño maestro + auxiliar con calendario |
| Despacho | `simulacion_ventana.simular_ventana` | despacha batch↔cascada según subtipo; acumula producción (kg seco + tasa kg/día + leña) |
| Entrada P7 | `balance_global.calcular_todo_ventana(proyecto, clima_df)` | punto de entrada del dashboard de producción |

---

## 7. Validación contra ADITAL

`validacion/validacion_adital.py` (standalone, fuera de pytest) contrasta la
cadena térmica completa contra datos de campo del secador ADITAL de San Carlos:

| Check | Esperado | Estado |
|---|---|---|
| Salida del colector | ~55 / 78 °C | ✓ |
| ΔT caño maestro | −2.8 °C | ✓ |
| Cámara | 57 °C | ✓ |
| Campaña | 5000 kg en ~5 días | ✓ |

**4/4 checks** (la memoria de proyecto reporta 7/7 en la corrida ampliada). Es un
**chequeo de orden de magnitud**, no una calibración: Secasol es un prediseñador
**general**; ADITAL/tesis son referencia de dimensiones/caudales/T, no objetivo de
ajuste.

---

## 8. Highlights de implementación (a nivel código)

| Qué | Dónde |
|---|---|
| Reparto de caudal del campo (ASHRAE cap. 21) | `calculos/campo_colectores_calc.py` |
| ΔP caño maestro (flujo acumulado) | `calculos/cano_maestro_calc.py::estimar_delta_P_cano_maestro` |
| ΔT caño maestro (2 variantes) | `cano_maestro_calc.py::delta_T_cano_maestro` |
| Uniformidad de distribución | `cano_maestro_calc.py::uniformidad_distribucion` |
| Sección variable del caño | `core.colector.CanoMaestro.seccion_en_fraccion` |
| Motor batch/semicontinuo | `calculos/camara_termodinamica.py::simular_cascada` |
| Topología del túnel | `core.camara.ConfiguracionTunel` (`n_zonas`, `intervalo_avance_h`) |
| Despacho de ventana | `calculos/simulacion_ventana.py::simular_ventana` |
| Forzantes + entrada P7 | `calculos/balance_global.py::armar_forzantes_ventana`, `calcular_todo_ventana` |
| Validación ADITAL | `validacion/validacion_adital.py` |

**Puntos a destacar en la charla:**
1. *Un mismo motor de cámara* sirve batch (N=1) y túnel (N zonas) — economía de
   modelo.
2. *La sequedad de salida es emergente*, no impuesta: el sistema te dice qué tan
   seco sale el producto a una cadencia dada.
3. *El caño maestro es un elemento físico propio* con ΔP, ΔT y uniformidad, y la
   **sección creciente compensa** la pérdida de carga.
4. *El reparto de caudal se resuelve* (red ASHRAE), no se asume uniforme.
5. *Validado contra un caso real de campo* (ADITAL) en orden de magnitud.

---

## Referencias

- ASHRAE Handbook 2017, cap. 21 — *Duct Design* (red hidráulica del campo).
- Haaland (1983) / Colebrook-White — fricción.
- Dittus-Boelter — convección forzada en ducto (film interno del caño).
- Tesis doctoral del autor, cap. 3 — secador híbrido ADITAL de San Carlos.
