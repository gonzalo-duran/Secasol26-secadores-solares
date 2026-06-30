# 03 · Cámara de secado (modos Caja y Armario)

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: balance de calor de la cámara, balances de momento y masa del aire con
> enfriamiento evaporativo, modelo del producto y rol de la isoterma de sorción,
> selección de materiales/aislantes/cubiertas, y fluidodinámica de bandejas
> (flujo horizontal vs vertical). El modo industrial va aparte (doc 04).

---

## 1. Un único motor físico (desde S38)

La cámara tiene **un solo motor**: el **balance acoplado calor–masa**. El antiguo
motor de "capa fina" (correlaciones empíricas MR(t) de Lewis/Page/Henderson-Pabis/
Midilli/Logarítmico) **fue eliminado**: era un evaluador de punto único a la
temperatura pico, insensible al espesor de lecho y a la velocidad de aire reales.

El modelo actual integra **dos EDOs del producto** $(T_{prod}, X_{prod})$
acopladas con un **sistema algebraico cuasi-estacionario** del aire y las paredes
(modelo **CSTR** — mezcla perfecta), que se resuelve **analíticamente** en cada
paso de tiempo. La evaporación es **difusiva**.

---

## 2. Hipótesis, condiciones de borde e iniciales

**Hipótesis:**
1. **Secador indirecto** (paredes opacas): sin radiación solar directa sobre el
   producto, salvo la variante de **techo translúcido** (§5.2).
2. **Modelo global (CSTR):** sin gradientes internos. Tres nodos —producto
   $T_{prod}$, aire de cámara $T_{flujo}$, paredes $T_{cam,int}/T_{cam,ext}$.
3. **Solo el producto acumula calor en el tiempo** (capacitancia). El aire y las
   paredes son cuasi-estacionarios (se resuelven sin derivada temporal).
4. **Aire húmedo = mezcla binaria** aire seco + vapor; **producto = masa seca +
   agua ligada**, $M_{tot}=M_s+M_{liq}$, $X=M_{liq}/M_s$.
5. **Continuidad:** una sola entrada (salida de colector + auxiliar) y una sola
   salida de aire.

**Condiciones iniciales (las EDOs):**
$$ T_{prod}(0)=T_{amb}, \qquad X_{prod}(0)=X_{inicial} $$

**Condiciones de borde (el sistema algebraico, por paso):**
- Aire de entrada $(T_{ent}, \omega_{ent})$ = salida del colector (+ auxiliar).
  En modos con clima real estas forzantes salen del clima/colector, **no** de los
  sliders de P4 (que solo son borde en modo Constantes — ver S39).
- Pared externa: convección de viento $h_w = 5.7 + 3.8\,v_{viento}$ (McAdams).
- Evento de fin: $X_{prod}=X_{objetivo}$ (event detection del solver).

---

## 3. Balance de calor del cuerpo (paredes)

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

---

## 4. Balances de momento y masa del aire — enfriamiento evaporativo

### 4.1 El sistema algebraico del aire

El aire que circula por la cámara se resuelve como **CSTR cuasi-estacionario**.
El sistema algebraico (resolución directa, $O(1)$, sin iteración) es:

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
$$
El último término (positivo) es el vapor que sale del producto a $T_{prod}$ y se
incorpora al aire. Aquí está el **enfriamiento evaporativo**: el aire cede calor
sensible al producto ($T_{flujo}\downarrow$) y gana humedad ($\omega_{flujo}\uparrow$).

### 4.2 Correlaciones de transferencia (calor y masa)

Los coeficientes $h_{conv}$ (aire→producto) y $K_m$ (transferencia de masa) se
reevalúan **en cada paso** (S39, no se congelan) con un closure de **placa plana +
analogía de Chilton-Colburn**, con todas las propiedades evaluadas en la película
$T_{film}=(T_{ent}+T_{prod})/2$.

**Convección de calor aire→producto — placa plana** (longitud característica = el
largo de la bandeja/cámara $L$; $Re=\rho\,v\,L/\mu$ con $\rho$ del aire húmedo y
$v$ del caudal másico sobre la sección transversal):

| Correlación | Expresión de Nu | Régimen / rango |
|---|---|---|
| **Pohlhausen** (laminar) | $Nu = 0.664\,Re^{1/2}\,Pr^{1/3}$ | Capa límite laminar sobre placa, $Re < 5\times10^{5}$ |
| **McAdams** (turbulento) | $Nu = 0.037\,Re^{0.8}\,Pr^{1/3}$ | Capa límite turbulenta, $Re > 5\times10^{5}$ |

con $h_{conv}=Nu\,k_{aire}/L$. El $Re$ crítico de transición es $5\times10^{5}$.

**Transferencia de masa — analogía de Chilton-Colburn.** Liga el transporte de
calor y el de masa por el número de Lewis:
$$
\frac{h_{conv}}{K_m\,c_{p,h}} = Le^{2/3},
\qquad Le=\frac{\alpha}{D_{AB}}\approx 1 \text{ (aire–agua)}
\;\Rightarrow\;
K_m=\frac{h_{conv}}{c_{p,h}\,Le^{2/3}}
$$
con $K_m$ [kg/(m²·s)] el coeficiente de transferencia de masa y
$c_{p,h}=1006+1805\,\omega$ el calor específico del aire húmedo. Como $Le\approx1$,
el número de **Sherwood** hereda la misma forma que el de Nusselt
($Sh = 0.664\,Re^{1/2}Sc^{1/3}$ laminar / $0.037\,Re^{0.8}Sc^{1/3}$ turbulento).
Reevaluar $h_{conv},K_m$ desde cantidades conocidas al inicio del paso **no rompe
la linealidad** del sistema algebraico del aire.

**Convección de viento en la pared externa — McAdams:**
$h_w = 5.7 + 3.8\,v_{viento}$ [W/m²·K] (entra en $U_{total}$ y en $U_{techo}$).

---

## 5. Materiales, aislantes y cubiertas (con sus ecuaciones)

### 5.1 Pared compuesta

La pared se define como **capas en serie** (`ConstruccionCamara.pared`), cada una
con su resistencia; la resistencia conductiva total $R_{cond}=\sum_i e_i/k_i$ se
agrega y se convierte a un $k_{ais}$ efectivo:
$k_{ais}=e_{cam,total}/R_{cond}$. Materiales y aislantes salen de catálogos YAML.

### 5.2 Techo translúcido — ganancia + pérdida (S44)

Si la cámara tiene techo translúcido, este aporta **dos** efectos:
- **Ganancia radiativa** al producto: $Q_{rad}=I_g\,\tau\,\alpha\,A_{rad}$
  (solo la primera bandeja "ve" el sol).
- **Pérdida conductiva** del vidriado:
  $U_{techo}=\left(\tfrac{1}{h_{conv}}+\tfrac{e_{techo}}{k_{ef}}+\tfrac{1}{h_w}\right)^{-1}$,
  con $k_{ef}$ del mapa por espesor del catálogo (policarbonato alveolar).

El área del techo se **descuenta de la envolvente opaca** $A_{cuerpo}$ (para no
doble-contar) y $UA_{techo}$ se suma al balance de $T_{flujo}$. Techo opaco →
$A_{techo}=0$, sin efecto.

---

## 6. Modelo del producto y rol de la isoterma de sorción

### 6.1 Las dos EDOs del producto

$$
\frac{dX_{prod}}{dt} = -\frac{\dot m_w}{M_s}
$$
$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = q_{prod} - \dot m_w\,L_v(T_{prod})
$$
con $q_{prod}=h_{conv}A_{prod}(T_{flujo}-T_{prod})$ el calor sensible que el aire
entrega al producto, y $c_{p,prod}=c_{ps}+c_{pa}X$ (mezcla seco+agua). El segundo
término es el **enfriamiento por evaporación** del producto (calor latente
$L_v$). Se integran con `scipy.integrate.solve_ivp` y **event detection** en
$X_{objetivo}$.

### 6.2 Para qué usamos la curva de sorción (¿"cinética"?)

Punto importante para la charla: **ya no hay una curva cinética empírica MR(t)**.
La "curva de secado" **emerge** de integrar el balance difusivo. Lo que sí
gobierna el proceso es la **isoterma de sorción de equilibrio GAB**, que entrega
la **actividad de agua** $a_w(X)$:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

Secasol usa la **inversión analítica** $a_w = f(X; X_m, C, K)$ (cuadrática) para
fijar $\omega_{sup}=\omega_{sat}(T_{prod})\,a_w(X)$. Físicamente: a medida que el
producto se seca, $a_w$ **cae** → la fuerza motriz $(\omega_{sup}-\omega_{flujo})$
**disminuye** → la tasa de secado **baja** sola. Así reproducimos los **periodos
de secado** (tasa decreciente) **sin** correlación empírica: el frenado sale de
la termodinámica de sorción, no de un ajuste. Cada producto trae sus parámetros
$X_m, C, K$ en el catálogo; si falta calibración, el sistema **advierte**.

> Nota de back-compat: `modelo_capa_fina` y `modo_calculo` son campos
> **vestigiales** (se coacciona cualquier `"capa_fina"` heredado a
> `"termodinamico"`). Los bloques `capa_fina:` de los catálogos **no son
> inertes**: filtran qué productos aparecen en el selector de P4.

---

## 7. Fluidodinámica de las bandejas — horizontal vs vertical

El área de intercambio del producto es $A_{prod}=N_{bandejas}\cdot A_{bandeja}$.
La **dirección del flujo** (`ConfiguracionFlujo.direccion_flujo`) cambia tanto la
pérdida de carga como el régimen convectivo:

- **HORIZONTAL (cross-flow):** el aire pasa **sobre** las bandejas. El coeficiente
  convectivo se calcula como **placa plana** (Pohlhausen/McAdams, §4.2); la pérdida de carga es
  $\Delta P_{malla}$ (coeficiente de forma $K\rho v^2/2$ por bandeja) **más**, si
  el lecho es apreciable, $\Delta P_{lecho}$ por **Ergun**.
- **VERTICAL_ASCENDENTE (through-bed):** el aire **atraviesa** el lecho de
  producto. Domina la pérdida de carga del **lecho empacado (Ergun)**:
  $$
  \frac{\Delta P}{L} = \underbrace{\frac{150\,\mu\,v_0\,(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}}_{\text{viscoso (laminar)}}
   + \underbrace{\frac{1.75\,\rho\,v_0^2\,(1-\varepsilon)}{(\Phi_s d_p)\,\varepsilon^3}}_{\text{inercial (turbulento)}}
  $$
  con $\varepsilon$ porosidad del lecho, $d_p$ diámetro de partícula,
  $\Phi_s$ esfericidad. La geometría del lecho se resuelve por cadena de
  prioridad (catálogo del producto → bandeja → defaults conservadores).

**Impacto del trade-off:** el flujo vertical maximiza el **contacto aire–producto**
(mejor transferencia, secado más parejo), pero a costa de **mucha más pérdida de
carga** (penaliza el ventilador o el tiro natural). El flujo horizontal es más
suave hidráulicamente pero transfiere menos. La velocidad del aire también entra
al $h_{conv}/K_m$ vía la película. La advertencia de **lecho delgado (<5 cm)**
acota la validez del modelo difusivo.

---

## 8. Highlights de implementación (a nivel código)

| Qué | Dónde |
|---|---|
| Punto de entrada de cámara | `calculos/camara_calc.py::calcular_camara` |
| Sistema algebraico CSTR (analítico) | `calculos/camara_termodinamica.py::resolver_estado_camara` |
| Integración de las 2 EDOs + event | `camara_termodinamica.py::simular_secado` (`solve_ivp` + evento $X_{obj}$) |
| Coeficientes variables en t (closure) | `camara_calc.py::_construir_params_termodinamico::_coef_transporte` |
| $h_{conv}$ placa plana / Chilton-Colburn | `camara_calc.py::_h_conv_camara_placa_plana` |
| Inversión GAB → $a_w(X)$ | `calculos/psicrometria.py::actividad_agua_desde_X_GAB` |
| $\omega_{sat}(T)$, entalpía, $c_p$ húmedo | `calculos/psicrometria.py` |
| Pared compuesta (R en serie) | `core/camara.py::ConstruccionCamara.pared` |
| Techo translúcido $U_{techo}$ + $Q_{rad}$ | `camara_calc.py` (decomposición) + `resolver_estado_camara` |
| ΔP de lecho (Ergun) y malla | `calculos/motor_calc.py::_delta_P_lecho_por_bandeja`, `_geometria_lecho` |
| Dirección de flujo | `core/camara.py::DireccionFlujo`, `ConfiguracionFlujo` |

**Puntos a destacar en la charla:**
1. *Un solo motor acoplado calor–masa*, sensible al espesor de lecho, la
   velocidad de aire y el clima real — no una correlación a T pico.
2. *La curva de secado emerge de la física* (GAB + difusión), no de un ajuste
   empírico.
3. *Enfriamiento evaporativo explícito*: el aire se enfría y se humidifica al
   secar; el balance lo captura término a término.
4. *Coeficientes de transporte variables en el tiempo* (Chilton-Colburn).
5. *La orientación del flujo* (horizontal/vertical) es un trade-off real
   transferencia ↔ pérdida de carga, no cosmético.

---

## Referencias

- Mujumdar — *Handbook of Industrial Drying*.
- Van den Berg & Bruin — modelo de sorción **GAB**.
- Incropera & DeWitt — analogía de **Chilton-Colburn** (calor↔masa) y correlaciones
  de placa plana (**Pohlhausen** laminar, **McAdams** turbulento).
- McAdams — convección de viento sobre superficie ($h_w=5.7+3.8\,v$).
- Ergun (1952) — pérdida de carga en lechos empacados.
- Threlkeld / ASHRAE — psicrometría del aire húmedo.
