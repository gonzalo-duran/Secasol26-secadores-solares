# Técnico · Colector solar de aire — modelo físico y numérico

Referencia técnica del modelo de colector: las 4 configuraciones, los balances
de energía por superficie, el coeficiente convectivo interno local, la solución
numérica y las pérdidas de carga. La guía de uso está en
[3 · Colector solar](?manual=colector).

## 1. Las cuatro configuraciones {#configuraciones}

Secasol modela **colectores solares de placa plana de aire** (*air heaters*) en
cuatro topologías, que comparten materiales y criterios constructivos y solo
difieren en **la ubicación del absorbedor y la circulación del flujo**:

| Tipo | Absorbedor | Circulación |
|---|---|---|
| **1** | en el fondo del cajón | aire **por encima** del absorbedor (canal único) |
| **2** | a media altura (dos canales) | flujo por **ambos** canales (superior + inferior) |
| **3** | a media altura | flujo por el canal **inferior**; superior estanco |
| **4** | a media altura | flujo por el canal **superior**; inferior estanco |

<!-- esquema: colectores_seccion_transversal | Sección transversal de los 4 tipos. -->

El cajón se construye en madera o doble chapa galvanizada con aislante
intermedio; la cubierta es de material de alta transmitancia (policarbonato
alveolar, film de invernadero, vidrio). El absorbedor puede tener ancho
$W_{abs} \ge W$ (chapa ondulada).

## 2. Hipótesis físicas fundamentales {#hipotesis}

Comunes a los 4 tipos:

1. **Cuasi-estacionario:** se desprecia la acumulación de calor en todas las
   superficies. Las variaciones temporales solo provienen de las condiciones
   ambientales (temperatura, irradiancia, viento) o del caudal de aire.
2. **Flujo unidireccional y desarrollado** en x (sentido del flujo). Puede ser
   laminar, en transición o turbulento; natural o forzado.
3. **Transferencia 1D efectiva en x e y**, despreciable en z (ancho):
   superficies homogéneas e isótropas.
4. **Continuidad:** única entrada en $x=0$ (a $T_{amb}$ o a la salida del tramo
   anterior), única salida en $x=L$.
5. **Absorbedor de espesor despreciable** → sin conducción interna; ambas caras
   a $T_{abs}$. (El espesor de placa se expone en la UI pero **no entra al
   balance**: decisión consciente, capacitancia de placa despreciable.)
6. **Pared compuesta chapa+aislante+chapa** → resistencia térmica = la del
   aislante (se desprecia la conducción en las chapas).
7. **Pérdidas laterales** ≪ pérdidas por arriba y abajo → se absorben en la
   dirección y.
8. **Absortividad de la cubierta despreciable** ($\alpha_{cub}\approx 0$,
   solo transmite y reemite IR).

**Condiciones de borde:**

- Entrada del fluido: $T_f(x{=}0) = T_{entrada}$ (ambiente, o salida del módulo
  anterior en serie).
- Cara superior: convección de viento (McAdams) + radiación al cielo (Swinbank).
- Cara inferior: conducción por el aislante + convección de viento en el fondo.
- La "condición inicial" del problema cuasi-estacionario es el **warm-start**
  del nodo previo (no hay transitorio temporal dentro del colector).

## 3. Balances de energía por superficie {#balances}

Notación: $\sigma$ = Stefan-Boltzmann; $h_w$ = convección de viento; $h_{int}$ =
convección interna; $\tau_{cub}$, $\alpha_{abs}$ ópticas;
$U_{ais}=k_{ais}/e_{ais}$; $T_{cie}$ temperatura de cielo; $dA_{cub}=W\,dx$,
$dA_{abs}=W_{abs}\,dx$. Todas las temperaturas en **K**.

### 3.1 Tipo 1 — canal único, absorbedor al fondo {#tipo1}

**Cubierta (cara externa):**
$$
h_w(T_{cub,e}-T_{amb}) + \varepsilon_{cub}\sigma(T_{cub,e}^4-T_{cie}^4)
  + U_{cub}(T_{cub,e}-T_{cub,i}) = 0
$$

**Cubierta (cara interna):**
$$
U_{cub}(T_{cub,e}-T_{cub,i}) - h_{int}(T_{cub,i}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{cub,i}^4-T_{abs}^4) = 0
$$

**Absorbedor:**
$$
I_g\,\tau_{cub}\,\alpha_{abs}
  - h_{int}(T_{abs}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{abs}^4-T_{cub,i}^4)
  - U_{ais}(T_{abs}-T_{bot}) = 0
$$

**Fondo (cuerpo):** balance que despeja $T_{bot}$ analíticamente:
$$
U_{ais}(T_{abs}-T_{bot}) = h_w(T_{bot}-T_{amb})
\;\Rightarrow\;
T_{bot}=\frac{U_{ais}T_{abs}+h_w T_{amb}}{U_{ais}+h_w}
$$

**Fluido (EDO en x)** — el aire gana de cubierta interna y absorbedor:
$$
\dot m\,c_p\,\frac{dT_f}{dx}
  = h_{int}\,W\,(T_{cub,i}-T_f) + h_{int}\,W_{abs}\,(T_{abs}-T_f)
$$

### 3.2 Tipo 2 — dos canales activos {#tipo2}

Aparece la cara interna del fondo $T_{int}$ y un segundo canal con su propio
$h_{int,2}$, $\dot m_2$. El absorbedor intercambia con **ambos** flujos por
convección, con la cubierta y con el fondo por radiación:
$$
I_g\tau_{cub}\alpha_{abs}
= \varepsilon_{eff}\sigma(T_{abs}^4-T_{cub,i}^4)
 + h_{int,1}(T_{abs}-T_{cs})
 + h_{int,2}(T_{abs}-T_{ci})
 + \varepsilon_{eff}\sigma(T_{abs}^4-T_{int}^4)
$$

EDOs de fluido en canal superior e inferior (análogas, cada una con su $\dot m$):
$$
\dot m_1 c_p \frac{dT_{cs}}{dx}=h_{int,1}W(T_{cub,i}-T_{cs})+h_{int,1}W_{abs}(T_{abs}-T_{cs})
$$
$$
\dot m_2 c_p \frac{dT_{ci}}{dx}=h_{int,2}W_{abs}(T_{abs}-T_{ci})+h_{int,2}W(T_{int}-T_{ci})
$$

Fondo: $U_{ais}(T_{int}-T_{bot})=h_w(T_{bot}-T_{amb})$.

### 3.3 Tipo 3 — solo canal inferior activo {#tipo3}

El canal superior es un **recinto estanco** (cavidad de aire): la transferencia
cubierta↔absorbedor pasa de convección forzada a **convección natural en cavidad
(Hollands) + radiación**. El balance del fluido solo existe en el canal inferior
(idéntico al de Tipo 2 inferior). El absorbedor pierde al canal superior
únicamente por convección natural y radiación.

### 3.4 Tipo 4 — solo canal superior activo {#tipo4}

Simétrico al Tipo 3: el canal **inferior** es la cavidad estanca; el fluido
circula por el canal superior (EDO idéntica a Tipo 2 superior). La cavidad
inferior aporta acoplamiento absorbedor↔fondo por convección natural + radiación.

### Doble cubierta (todos los tipos) {#doble-cubierta}

Con dos cubiertas, la conductancia de la cubierta $U_{cub}$ deja de ser
$k_{cub}/e_{cub}$ y pasa a ser una **conductancia efectiva** que combina
conducción en cada lámina + **convección natural de Hollands** en la cavidad de
aire entre cubiertas + **radiación gris** entre superficies paralelas.

## 4. Coeficiente convectivo interno local {#nusselt}

El coeficiente convectivo interno **no es un escalar único** a temperatura
fija: se evalúa **localmente, nodo a nodo**.

### 4.1 Receta local por nodo {#receta-local}

Para cada nodo x:

1. **Propiedades del aire variables con T** evaluadas a la temperatura de
   película $T_{film}=(T_f+T_{pared})/2$: $k(T),\mu(T),Pr(T),c_p(T),\rho(T,P)$.
2. **Reynolds local** con el flujo másico por unidad de área
   $G=\dot m/A_{sec}$ (constante) y la viscosidad local:
   $Re = G\,D_h/\mu(T_{film})$. El diámetro hidráulico de un canal rectangular
   es $D_h = 2\,W\,a/(W+a)$ con $a$ la altura del canal.
3. **Nusselt local mixto** = forzado (con entrada térmica + blending continuo de
   régimen en $Re=2300$ y $Re=10000$) combinado con **flotación**: Rayleigh
   local con la componente de gravedad a lo largo del canal,
   $Ra = g\sin\beta\,\beta_{exp}\,\Delta T\,D_h^3/(\nu\,\alpha)$, vía la
   correlación de **convección mixta de Churchill**.
4. $h_{int}(x) = Nu(x)\,k(T_{film})/D_h$.

El catálogo de correlaciones provee tanto las correlaciones **promediadas**
sobre $L$ (selección automática, usadas en vistas previas y validación) como las
versiones **locales** nodo a nodo, usadas por los solvers. Las locales están
construidas para que su **promedio sobre $0\!\to\!L$ reproduzca exactamente** la
correlación promediada equivalente (Heaton en laminar, Cengel en turbulento —
ver §4.4).

### 4.2 Correlaciones de flujo forzado {#correlaciones-forzado}

Régimen por número de Reynolds: **laminar** $Re<2300$, **transición**
$2300\le Re\le 10^4$, **turbulento** $Re>10^4$. La elección dentro de cada
régimen depende además de $L/D_h$ (efectos de entrada térmica) y de cuántas
paredes del canal calientan el flujo (una pared → Tipos 1, 3, 4; dos paredes →
Tipo 2).

| Correlación | Expresión de Nu | Régimen / rango | Paredes |
|---|---|---|---|
| **Shah & London (1978)** | $Nu = 5.385$ | Laminar desarrollado, $Re<2300$, $L/D_h\ge 50$ | 1 pared (caso H2) |
| **Shah & London simétrico** | $Nu = 8.235$ | Laminar desarrollado, $Re<2300$, $L/D_h\ge 50$ (Tipo 2) | 2 paredes (caso H1) |
| **Heaton, Reynolds & Kays (1964)** | $Nu = 5.385\,(1+0.0668\,Gz^{2/3})$, $\;Gz=Re\,Pr\,D_h/L$ | Laminar en **entrada térmica**, $Re<2300$, $L/D_h<50$, $Pr>0.5$ | 1 pared |
| **Gnielinski (1976)** | $Nu = \dfrac{(f/8)(Re-1000)Pr}{1+12.7\sqrt{f/8}\,(Pr^{2/3}-1)}$, $\;f=(0.790\ln Re-1.64)^{-2}$ | **Transición**, $2300\le Re\le 10^4$, $0.5<Pr<2000$ | (indistinta) |
| **Sparrow & Liu (1979)** | $Nu = 0.0158\,Re^{0.8}$ | Turbulento, $Re>10^4$; default de **una pared caliente** (Tipos 1, 3, 4) | 1 pared |
| **Dittus-Boelter (1930)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}$ (exp. 0.4: fluido calentado) | Turbulento, $Re>10^4$, $0.6<Pr<160$, $L/D_h>10$; default de **dos paredes** (Tipo 2) | 2 paredes |
| **Cengel & Ghajar (2014)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}\,[1+(D_h/L)^{0.7}]$ | Turbulento con **entrada térmica**, $Re>10^4$, $L/D_h<10$; converge a Dittus-Boelter para $L/D_h>60$ | (indistinta) |

### 4.3 Convección natural y mixta {#correlaciones-natural}

Aparece en dos contextos: (a) las **cavidades estancas** y la **cavidad de doble
cubierta** (Tipos 3/4 y doble cubierta), y (b) la componente de **flotación**
que se suma al forzado en el canal activo a baja velocidad o gran inclinación.

| Correlación | Expresión de Nu | Rango de aplicación |
|---|---|---|
| **Hollands et al. (1976)** — cavidad inclinada | $Nu = 1 + 1.44\big[1-\tfrac{1708}{Ra\cos\theta}\big]^{+}\!\big[1-\tfrac{1708\sin(1.8\theta)^{1.6}}{Ra\cos\theta}\big] + \big[(\tfrac{Ra\cos\theta}{5830})^{1/3}-1\big]^{+}$ | Cavidad, $\theta\in[0°,75°]$, $Ra\lesssim 10^{8}$. Para $Ra\cos\theta<1708$: $Nu=1$ (conducción pura). $[x]^{+}=\max(0,x)$ |
| **Churchill-Chu** (componente natural del canal) | $Nu_{nat} = \dfrac{0.670\,Ra^{1/4}}{[1+(0.492/Pr)^{9/16}]^{4/9}}$ | Aporte de **flotación** local (placa, laminar); $Ra$ con la componente $g\sin\beta$. $Nu_{nat}\to0$ cuando $Ra\to0$ |
| **Convección mixta de Churchill** | $Nu = (Nu_{forz}^{3} + Nu_{nat}^{3})^{1/3}$ | Flotación **asistida**. Reduce al forzado si $Ra\to0$; domina el natural si $Gr/Re^{2}\gg1$ |

### 4.4 Selección automática y blending de régimen {#seleccion}

Con selección automática, la lógica es:

- **$Re<2300$ (laminar):** Heaton si $L/D_h<50$ (entrada térmica), si no Shah &
  London — simétrico para dos paredes (Tipo 2), asimétrico para una pared.
- **$2300\le Re\le 10^4$ (transición):** Gnielinski.
- **$Re>10^4$ (turbulento):** Cengel si $L/D_h<10$ (entrada pronunciada); si
  no, Sparrow & Liu para una pared o Dittus-Boelter para dos paredes.

Si el usuario fuerza una correlación fuera de su rango de $Re$ o de tipo de
pared, se emite una advertencia sin abortar el cálculo.

En las versiones **locales**, la conmutación entre regímenes no es un salto:
hay un **blending continuo C¹** en bandas de $\pm400$ en torno a $Re=2300$ y
$Re=10^4$, para que $Nu(x)$ no salte si el $Re$ local cruza un umbral a lo largo
del colector al variar $\mu(T)$. Los realces de entrada local están calibrados
para que su integral reproduzca las correlaciones promediadas: laminar
$Nu_x = Nu_\infty(1+0.02227\,Gz_x^{2/3})$ promedia a Heaton
($3\times0.02227=0.0668$); turbulento $(1+0.3\,(D_h/x)^{0.7})$ promedia a
Cengel ($3.333\times0.3=1$).

### 4.5 Caudal másico {#caudal}

El caudal másico se fija con $\rho(T_{entrada})$ — el caudal **volumétrico** de
diseño se establece a la entrada:
$$Q = n_{par}\,v_{dis}\,W\,a, \qquad \dot m = \rho(T_{ent})\,Q$$

## 5. Solución numérica {#numerica}

El modelo es **cuasi-estacionario acoplado**: una EDO del fluido en x más un
sistema algebraico no lineal de superficies en cada nodo.

### 5.1 Esquema de dos niveles {#dos-niveles}

- **Nivel externo — integración de la EDO del fluido** $dT_f/dx$ con
  `scipy.integrate.solve_ivp`, método **RK45**, tolerancias $10^{-6}$, sobre
  $x\in[0, L_{total}]$ con $L_{total}=L_{unidad}\cdot n_{serie}$ y paso máximo
  acotado para garantizar una discretización mínima.
- **Nivel interno — sistema algebraico por nodo** con `scipy.optimize.fsolve`.
  En Tipo 1 las incógnitas son **3**: $[T_{cub,e}, T_{cub,i}, T_{abs}]$, con
  $T_{bot}$ despejada analíticamente; en Tipos 2–4 se añade $T_{int}$ y/o
  acoplamientos de cavidad. El residuo es el vector de balances de superficie;
  el solver busca su raíz.

### 5.2 Warm-start {#warm-start}

Cada llamada al solver de nodo arranca desde la solución del **nodo previo**.
Esto acelera la convergencia y da robustez. La temperatura de pared del
warm-start alimenta a su vez el $T_{film}$ y el Rayleigh del $h_{int}$ local
(acople convección–flotación).

### 5.3 Discretización {#discretizacion}

El colector se discretiza **en la coordenada axial x** (sentido del flujo): el
integrador adaptativo coloca los nodos, con un piso de nodos mínimo. En cada
nodo se resuelve el plano transversal completo (cubierta, absorbedor, fondo,
fluido). No se discretiza en y ni en z (hipótesis 1D). En un banco en serie, la
salida de un módulo es la condición de entrada del siguiente.

### 5.4 Convergencia y diagnóstico {#convergencia}

Si la integración no converge, el cálculo falla explícitamente. Si el sistema de
un nodo no converge se registra una advertencia pero la integración continúa
con la solución aproximada. El resultado lleva un indicador de convergencia.

## 6. Modularidad {#modularidad}

La modularidad opera en **tres niveles**:

1. **Secciones** — el proyecto se arma sección a sección; la física de cada una
   vive aislada de la interfaz.
2. **Componentes** — el colector elige tipo 1–4: misma interfaz de cálculo,
   distinta topología de balances. El núcleo del $h_{int}$ local se **reusa**
   entre tipos.
3. **Subcomponentes** — cubierta, placa, aislante y fondo se eligen de
   **catálogos de materiales** y se validan al construir el modelo de datos.
   Cambiar un material es cambiar una entrada del catálogo, sin tocar la
   física. La geometría se separa en módulo unitario y banco (serie/paralelo).

## 7. Pérdidas de carga en el colector {#perdidas}

La pérdida de carga friccional del canal se calcula con **Darcy-Weisbach** y el
**factor de fricción de Haaland (1983)** (aproximación explícita de
Colebrook-White, error < 2 %):

$$
\Delta P = f\,\frac{L_{total}}{D_h}\,\frac{\rho\,v^2}{2},
\qquad
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
$$

con $\varepsilon$ la **rugosidad real** de la placa absorbedora (del catálogo;
default conservador $5\times10^{-5}$ m de chapa pintada). Reglas por tipo:

- **Tipo 1:** canal único (altura del canal).
- **Tipo 2:** dos canales en paralelo → $\Delta P = \max(\Delta P_{cs}, \Delta P_{ci})$.
- **Tipo 3:** canal inferior activo.
- **Tipo 4:** canal superior activo.

En **banco**: serie → $\Delta P$ escala con el largo total; paralelo →
$\Delta P$ de una rama. Esta $\Delta P$ alimenta el dimensionamiento del
ventilador (forzada) o el lazo de tiro (natural) — ver
[Técnico · Motor, chimenea y pérdidas de carga](?manual=tec-chimenea).

---

**Ver también:** [3 · Colector solar](?manual=colector) (guía de uso),
[Radiación solar y plano orientado](?manual=radiacion) (el colector recibe POA,
no GHI), [Apéndice · Implementación](?manual=apendice-codigo#colector),
[Bibliografía](?manual=bibliografia#duffie-beckman).
