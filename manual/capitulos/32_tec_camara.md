# Técnico · Cámara de secado — balance acoplado calor-masa

Referencia técnica del motor de cámara (tipologías Caja y Armario): balance de
calor de las paredes, balances de momento y masa del aire con enfriamiento
evaporativo, modelo del producto y rol de la isoterma de sorción, y
fluidodinámica de bandejas. El modo industrial (batch multi-zona y túnel
semicontinuo) está en [Técnico · Modo industrial](?manual=tec-industrial). La
guía de uso está en [4 · Cámara de secado](?manual=camara).

## 1. Un único motor físico {#motor-unico}

La cámara tiene **un solo motor**: el **balance acoplado calor–masa**. Un
antiguo motor de "capa fina" (correlaciones empíricas MR(t) de tipo Lewis/Page/
Henderson-Pabis) fue eliminado del pipeline: era un evaluador de punto único a
la temperatura pico, insensible al espesor de lecho y a la velocidad de aire
reales.

El modelo actual integra **dos EDOs del producto** $(T_{prod}, X_{prod})$
acopladas con un **sistema algebraico cuasi-estacionario** del aire y las
paredes (modelo **CSTR** — mezcla perfecta), que se resuelve **analíticamente**
en cada paso de tiempo. La evaporación es **difusiva**.

## 2. Hipótesis y condiciones de borde {#hipotesis}

**Hipótesis:**

1. **Secador indirecto** (paredes opacas): sin radiación solar directa sobre el
   producto, salvo las **superficies translúcidas** (§5.2) — techo y/o paredes
   vidriadas con reparto de la radiación entre producto y aire.
2. **Modelo global (CSTR):** sin gradientes internos. Tres nodos — producto
   $T_{prod}$, aire de cámara $T_{flujo}$, paredes $T_{cam,int}/T_{cam,ext}$.
3. **Solo el producto acumula calor en el tiempo** (capacitancia). El aire y
   las paredes son cuasi-estacionarios (se resuelven sin derivada temporal).
4. **Aire húmedo = mezcla binaria** aire seco + vapor; **producto = masa seca +
   agua ligada**, $M_{tot}=M_s+M_{liq}$, $X=M_{liq}/M_s$ (base seca — ver
   [Física del secado](?manual=secado)).
5. **Continuidad:** una sola entrada (salida de colector + auxiliar) y una sola
   salida de aire.

**Condiciones iniciales (las EDOs):**
$$ T_{prod}(0)=T_{amb}, \qquad X_{prod}(0)=X_{inicial} $$

**Condiciones de borde (el sistema algebraico, por paso):**

- Aire de entrada $(T_{ent}, \omega_{ent})$ = salida del colector (+ auxiliar).
  En los modos con clima real estas forzantes salen del clima y del colector,
  **no** de los controles de condición de operación de la sección Cámara (que
  solo son condición de borde en modo Constantes).
- Pared externa: convección de viento $h_w = 5.7 + 3.8\,v_{viento}$ (McAdams).
- Evento de fin: $X_{prod}=X_{objetivo}$ (detección de evento del integrador).

## 3. Balance de calor del cuerpo (paredes) {#paredes}

La pared se modela como **cascada resistiva de 3 nodos** (convección interior →
conducción del aislante → convección exterior), combinada en una conductancia
global:
$$
U_{total}=\left(\frac{1}{h_{conv}}+\frac{e_{cam}}{k_{ais}}+\frac{1}{h_w}\right)^{-1}
\qquad
Q_{pared}=U_{total}\,A_{cuerpo}\,(T_{flujo}-T_{amb})
$$

Los nodos $T_{cam,int}$ y $T_{cam,ext}$ se **reconstruyen** como post-cómputo a
partir de $Q_{pared}$ (la misma potencia atraviesa cada resistencia en serie).
Casos límite tratados explícitamente: $k_{ais}=0$ → pared aislante perfecta
($U_{total}=0$); $h_w=0$ → cara externa desacoplada del ambiente.

## 4. Balances del aire — enfriamiento evaporativo {#aire}

### 4.1 El sistema algebraico del aire {#cstr}

El aire que circula por la cámara se resuelve como **CSTR cuasi-estacionario**.
El sistema algebraico (resolución directa, sin iteración) es:

**(a) Balance de masa de agua del aire** (lineal en $\omega_{flujo}$):
$$
\dot m_{as}\,(\omega_{flujo}-\omega_{ent}) = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo})
$$
con $\omega_{sup}=\omega_{sat}(T_{prod})\cdot a_w(X_{prod})$ la humedad de la
**capa de aire en contacto con el producto** (saturación a $T_{prod}$ corregida
por la actividad de agua $a_w$). La **tasa de evaporación** es:
$$
\boxed{\;\dot m_w = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo}) = \dot m_{as}(\omega_{flujo}-\omega_{ent})\;}
$$
(signo: + evaporación, − condensación). Esta es la forma **difusiva**:
$\dot m_w = h_m\,A\,(\omega_{sat}\,a_w - \omega_{flujo})$.

**(b) Balance de energía (entalpía) del aire** (lineal en $T_{flujo}$):
$$
\dot m_{as}\,[\,h(T_{flujo},\omega_{flujo})-h(T_{ent},\omega_{ent})\,]
 = -U_{total}A_{cuerpo}(T_{flujo}-T_{amb})
 - h_{conv}A_{prod}(T_{flujo}-T_{prod})
 + \dot m_w\,h_v(T_{prod})
 + Q_{rad,aire}
$$

El término $\dot m_w\,h_v(T_{prod})$ (positivo) es el vapor que sale del
producto a $T_{prod}$ y se incorpora al aire. $Q_{rad,aire}$ es la fracción de
la radiación transmitida por las superficies translúcidas que **no** intercepta
el producto y calienta el aire vía las superficies internas opacas (§5.2);
vale 0 con envolvente opaca. Aquí está el **enfriamiento evaporativo**: el aire cede
calor sensible al producto ($T_{flujo}\downarrow$) y gana humedad
($\omega_{flujo}\uparrow$). Los conceptos psicrométricos ($\omega$, saturación,
entalpía del aire húmedo) están en [Psicrometría](?manual=psicrometria).

### 4.2 Correlaciones de transferencia (calor y masa) {#coeficientes}

Los coeficientes $h_{conv}$ (aire→producto) y $K_m$ (transferencia de masa) se
reevalúan **en cada paso** (no se congelan) con **placa plana + analogía de
Chilton-Colburn**, con todas las propiedades evaluadas en la película
$T_{film}=(T_{ent}+T_{prod})/2$.

**Convección de calor aire→producto — placa plana** (longitud característica =
largo de la bandeja/cámara $L$; $Re=\rho\,v\,L/\mu$ con $\rho$ del aire húmedo
y $v$ del caudal másico sobre la sección transversal):

| Correlación | Expresión de Nu | Régimen / rango |
|---|---|---|
| **Pohlhausen** (laminar) | $Nu = 0.664\,Re^{1/2}\,Pr^{1/3}$ | Capa límite laminar sobre placa, $Re < 5\times10^{5}$ |
| **McAdams** (turbulento) | $Nu = 0.037\,Re^{0.8}\,Pr^{1/3}$ | Capa límite turbulenta, $Re > 5\times10^{5}$ |

con $h_{conv}=Nu\,k_{aire}/L$.

**Transferencia de masa — analogía de Chilton-Colburn.** Liga el transporte de
calor y el de masa por el número de Lewis:
$$
\frac{h_{conv}}{K_m\,c_{p,h}} = Le^{2/3},
\qquad Le=\frac{\alpha}{D_{AB}}\approx 1 \text{ (aire–agua)}
\;\Rightarrow\;
K_m=\frac{h_{conv}}{c_{p,h}\,Le^{2/3}}
$$
con $K_m$ [kg/(m²·s)] el coeficiente de transferencia de masa y
$c_{p,h}=1006+1805\,\omega$ el calor específico del aire húmedo. Como
$Le\approx1$, el número de **Sherwood** hereda la misma forma que el de Nusselt
($Sh = 0.664\,Re^{1/2}Sc^{1/3}$ laminar / $0.037\,Re^{0.8}Sc^{1/3}$
turbulento). Reevaluar $h_{conv},K_m$ desde cantidades conocidas al inicio del
paso **no rompe la linealidad** del sistema algebraico del aire.

**Convección de viento en la pared externa — McAdams:**
$h_w = 5.7 + 3.8\,v_{viento}$ [W/m²·K] (entra en $U_{total}$ y en $U_{techo}$).

## 5. Materiales, aislantes y cubiertas {#materiales}

### 5.1 Pared compuesta {#pared-compuesta}

La pared se define como **capas en serie**, cada una con su resistencia; la
resistencia conductiva total $R_{cond}=\sum_i e_i/k_i$ se agrega y se convierte
a una conductividad efectiva $k_{ais}=e_{cam,total}/R_{cond}$. Materiales y
aislantes salen de catálogos.

### 5.2 Superficies translúcidas — ganancia + pérdida {#techo-translucido}

Hasta **5 caras** de la cámara (techo + 4 paredes) pueden ser translúcidas.
Cada cara $i$ tiene inclinación y acimut propios, derivados de la
**orientación de la cámara** y del **techo a un agua**
(`GeometriaCamara.caras()`; el alto de la geometría es la altura **media**, lo
que preserva el volumen y la sección de flujo al inclinar el techo). La
irradiancia sobre cada cara es su **POA** (transposición Liu-Jordan por cara —
[Radiación solar](?manual=radiacion); un techo horizontal usa GHI directamente,
el caso histórico exacto).

**Ganancia — reparto producto/aire.** Cada cara intercepta una fracción $f_i$
de su radiación transmitida directamente sobre el producto; el resto lo
absorben las superficies internas opacas (absortancia interior $\alpha_{int}$,
default 0.85) y calienta el aire:

$$
I_{eq,prod}=\frac{\sum_i f_i\,A_i\,POA_i}{A_{rad}},
\qquad
Q_{rad,aire}=\tau\,\alpha_{int}\sum_i (1-f_i)\,A_i\,POA_i
$$

El producto recibe $Q_{rad}=I_{eq,prod}\,\tau\,\alpha\,A_{rad}$ (como el techo
translúcido histórico, ahora con la irradiancia equivalente de todas las
caras); $Q_{rad,aire}$ entra al balance de $T_{flujo}$ (§4.1b). Los factores de
intercepción: el techo "ve" el producto según $f_{techo}=A_{rad}/A_{techo}$;
las paredes según la **silueta del lecho apilado**
($f_{pared}=N_{bandejas}\,e_{capa}/H$). Es el **efecto invernadero** de una
caja vidriada: en tipología Caja, la cámara **es** el colector.

**Pérdida conductiva** del vidriado:
$U_{techo}=\left(\tfrac{1}{h_{conv}}+\tfrac{e_{techo}}{k_{ef}}+\tfrac{1}{h_w}\right)^{-1}$,
con $k_{ef}$ del mapa por espesor del catálogo (policarbonato alveolar),
aplicada al **área translúcida total** $\sum_i A_i$.

El área translúcida se **descuenta de la envolvente opaca** $A_{cuerpo}$ (para
no doble-contar) y $U_{techo}\sum_i A_i$ se suma al balance de $T_{flujo}$.
Envolvente opaca → sin efecto.

**Fuera del modelo** (anotado como mejora futura): pérdidas IR nocturnas del
vidriado y discretización vertical del producto por bandeja.

## 6. Modelo del producto y la isoterma de sorción {#producto}

### 6.1 Las dos EDOs del producto {#edos}

$$
\frac{dX_{prod}}{dt} = -\frac{\dot m_w}{M_s}
$$
$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = q_{prod} - \dot m_w\,L_v(T_{prod})
$$

con $q_{prod}=h_{conv}A_{prod}(T_{flujo}-T_{prod})$ el calor sensible que el
aire entrega al producto, y $c_{p,prod}=c_{ps}+c_{pa}X$ (mezcla seco+agua). El
segundo término es el **enfriamiento por evaporación** del producto (calor
latente $L_v$). Se integran con `scipy.integrate.solve_ivp` y **detección de
evento** en $X_{objetivo}$.

### 6.2 El rol de la curva de sorción {#isotermas}

**No hay una curva cinética empírica MR(t):** la "curva de secado" **emerge**
de integrar el balance difusivo. Lo que gobierna el proceso es la **isoterma de
sorción de equilibrio GAB**, que entrega la **actividad de agua** $a_w(X)$:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

Secasol usa la **inversión analítica** $a_w = f(X; X_m, C, K)$ (cuadrática)
para fijar $\omega_{sup}=\omega_{sat}(T_{prod})\,a_w(X)$. Físicamente: a medida
que el producto se seca, $a_w$ **cae** → la fuerza motriz
$(\omega_{sup}-\omega_{flujo})$ **disminuye** → la tasa de secado **baja**
sola. Así se reproducen los **periodos de secado** (tasa decreciente) **sin**
correlación empírica: el frenado sale de la termodinámica de sorción, no de un
ajuste. Cada producto trae sus parámetros $X_m, C, K$ en el catálogo; si falta
calibración, el sistema **advierte**. El fundamento conceptual está en
[Física del secado](?manual=secado#isotermas).

## 7. Fluidodinámica de las bandejas — horizontal vs vertical {#bandejas}

El área de intercambio del producto es $A_{prod}=N_{bandejas}\cdot A_{bandeja}$.
La **dirección del flujo** cambia tanto la pérdida de carga como el régimen
convectivo:

- **HORIZONTAL (cross-flow):** el aire pasa **sobre** las bandejas. El
  coeficiente convectivo se calcula como **placa plana** (Pohlhausen/McAdams,
  §4.2); la pérdida de carga es $\Delta P_{malla}$ (coeficiente de forma
  $K\rho v^2/2$ por bandeja) **más**, si el lecho es apreciable,
  $\Delta P_{lecho}$ por **Ergun**.
- **VERTICAL ASCENDENTE (through-bed):** el aire **atraviesa** el lecho de
  producto. Domina la pérdida de carga del **lecho empacado (Ergun)**:
  $$
  \frac{\Delta P}{L} = \underbrace{\frac{150\,\mu\,v_0\,(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}}_{\text{viscoso (laminar)}}
   + \underbrace{\frac{1.75\,\rho\,v_0^2\,(1-\varepsilon)}{(\Phi_s d_p)\,\varepsilon^3}}_{\text{inercial (turbulento)}}
  $$
  con $\varepsilon$ porosidad del lecho, $d_p$ diámetro de partícula, $\Phi_s$
  esfericidad. La geometría del lecho se resuelve por cadena de prioridad
  (catálogo del producto → bandeja → defaults conservadores).

**El trade-off:** el flujo vertical maximiza el **contacto aire–producto**
(mejor transferencia, secado más parejo), pero a costa de **mucha más pérdida
de carga** (penaliza el ventilador o el tiro natural — ver
[Técnico · Motor y pérdidas de carga](?manual=tec-chimenea)). El flujo
horizontal es más suave hidráulicamente pero transfiere menos. La advertencia
de **lecho delgado (<5 cm)** acota la validez del modelo difusivo.

---

**Ver también:** [4 · Cámara de secado](?manual=camara) (guía de uso),
[Psicrometría](?manual=psicrometria) y [Física del secado](?manual=secado)
(fundamentos), [Técnico · Modo industrial](?manual=tec-industrial) (batch
multi-zona y túnel), [Apéndice · Implementación](?manual=apendice-codigo#camara),
[Bibliografía](?manual=bibliografia#mujumdar).
