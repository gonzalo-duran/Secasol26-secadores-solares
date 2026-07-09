# Technical · Drying chamber — coupled heat-mass balance

Technical reference of the chamber engine (Box and Cabinet typologies): heat
balance of the walls, momentum and mass balances of the air with evaporative
cooling, product model and the role of the sorption isotherm, and tray fluid
dynamics. The industrial mode (multi-zone batch and semi-continuous tunnel) is in
[Technical · Industrial mode](?manual=tec-industrial). The usage guide is in
[4 · Drying chamber](?manual=camara).

## 1. A single physical engine {#motor-unico}

The chamber has **a single engine**: the **coupled heat–mass balance**. An old
"thin-layer" engine (empirical MR(t) correlations of the Lewis/Page/
Henderson-Pabis type) was removed from the pipeline: it was a single-point
evaluator at the peak temperature, insensitive to the real bed thickness and air
velocity.

The current model integrates **two product ODEs** $(T_{prod}, X_{prod})$ coupled
with a **quasi-steady algebraic system** of the air and the walls (**CSTR** model
— perfect mixing), which is solved **analytically** at each time step. The
evaporation is **diffusive**.

## 2. Assumptions and boundary conditions {#hipotesis}

**Assumptions:**

1. **Indirect dryer** (opaque walls): no direct solar radiation on the product,
   except the **translucent surfaces** (§5.2) — glazed roof and/or walls with the
   radiation split between product and air.
2. **Global model (CSTR):** no internal gradients. Three nodes — product
   $T_{prod}$, chamber air $T_{flujo}$, walls $T_{cam,int}/T_{cam,ext}$.
3. **Only the product accumulates heat over time** (capacitance). The air and the
   walls are quasi-steady (solved without a time derivative).
4. **Moist air = binary mixture** dry air + vapor; **product = dry mass + bound
   water**, $M_{tot}=M_s+M_{liq}$, $X=M_{liq}/M_s$ (dry basis — see
   [Drying physics](?manual=secado)).
5. **Continuity:** a single inlet (collector outlet + auxiliary) and a single air
   outlet.

**Initial conditions (the ODEs):**
$$ T_{prod}(0)=T_{amb}, \qquad X_{prod}(0)=X_{inicial} $$

**Boundary conditions (the algebraic system, per step):**

- Inlet air $(T_{ent}, \omega_{ent})$ = collector outlet (+ auxiliary). In the
  modes with real climate these forcings come from the climate and the collector,
  **not** from the operating-condition controls of the Chamber section (which are
  only a boundary condition in Constants mode).
- Outer wall: wind convection $h_w = 5.7 + 3.8\,v_{viento}$ (McAdams).
- End event: $X_{prod}=X_{objetivo}$ (integrator event detection).

## 3. Body heat balance (walls) {#paredes}

The wall is modeled as a **3-node resistive cascade** (interior convection →
insulation conduction → exterior convection), combined into a global conductance:
$$
U_{total}=\left(\frac{1}{h_{conv}}+\frac{e_{cam}}{k_{ais}}+\frac{1}{h_w}\right)^{-1}
\qquad
Q_{pared}=U_{total}\,A_{cuerpo}\,(T_{flujo}-T_{amb})
$$

The nodes $T_{cam,int}$ and $T_{cam,ext}$ are **reconstructed** as a
post-computation from $Q_{pared}$ (the same power crosses each resistance in
series). Limiting cases treated explicitly: $k_{ais}=0$ → perfect insulating wall
($U_{total}=0$); $h_w=0$ → outer face decoupled from the environment.

## 4. Air balances — evaporative cooling {#aire}

### 4.1 The air algebraic system {#cstr}

The air circulating through the chamber is solved as a **quasi-steady CSTR**. The
algebraic system (direct solution, no iteration) is:

**(a) Water mass balance of the air** (linear in $\omega_{flujo}$):
$$
\dot m_{as}\,(\omega_{flujo}-\omega_{ent}) = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo})
$$
with $\omega_{sup}=\omega_{sat}(T_{prod})\cdot a_w(X_{prod})$ the humidity of the
**air layer in contact with the product** (saturation at $T_{prod}$ corrected by
the water activity $a_w$). The **evaporation rate** is:
$$
\boxed{\;\dot m_w = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo}) = \dot m_{as}(\omega_{flujo}-\omega_{ent})\;}
$$
(sign: + evaporation, − condensation). This is the **diffusive** form:
$\dot m_w = h_m\,A\,(\omega_{sat}\,a_w - \omega_{flujo})$.

**(b) Energy (enthalpy) balance of the air** (linear in $T_{flujo}$):
$$
\dot m_{as}\,[\,h(T_{flujo},\omega_{flujo})-h(T_{ent},\omega_{ent})\,]
 = -U_{total}A_{cuerpo}(T_{flujo}-T_{amb})
 - h_{conv}A_{prod}(T_{flujo}-T_{prod})
 + \dot m_w\,h_v(T_{prod})
 + Q_{rad,aire}
$$

The term $\dot m_w\,h_v(T_{prod})$ (positive) is the vapor that leaves the product
at $T_{prod}$ and joins the air. $Q_{rad,aire}$ is the fraction of the radiation
transmitted by the translucent surfaces that the product does **not** intercept
and that heats the air via the opaque inner surfaces (§5.2); it is 0 with an
opaque envelope. Here is the **evaporative cooling**: the air gives up sensible
heat to the product ($T_{flujo}\downarrow$) and gains humidity
($\omega_{flujo}\uparrow$). The psychrometric concepts ($\omega$, saturation,
moist-air enthalpy) are in [Psychrometry](?manual=psicrometria).

### 4.2 Transfer correlations (heat and mass) {#coeficientes}

The coefficients $h_{conv}$ (air→product) and $K_m$ (mass transfer) are
re-evaluated **at each step** (not frozen) with **flat plate + Chilton-Colburn
analogy**, with all properties evaluated at the film
$T_{film}=(T_{ent}+T_{prod})/2$.

**Air→product heat convection — flat plate** (characteristic length = length of
the tray/chamber $L$; $Re=\rho\,v\,L/\mu$ with $\rho$ of the moist air and $v$ of
the mass flow over the cross-section):

| Correlation | Nu expression | Regime / range |
|---|---|---|
| **Pohlhausen** (laminar) | $Nu = 0.664\,Re^{1/2}\,Pr^{1/3}$ | Laminar boundary layer over a plate, $Re < 5\times10^{5}$ |
| **McAdams** (turbulent) | $Nu = 0.037\,Re^{0.8}\,Pr^{1/3}$ | Turbulent boundary layer, $Re > 5\times10^{5}$ |

with $h_{conv}=Nu\,k_{aire}/L$.

**Mass transfer — Chilton-Colburn analogy.** It links heat and mass transport by
the Lewis number:
$$
\frac{h_{conv}}{K_m\,c_{p,h}} = Le^{2/3},
\qquad Le=\frac{\alpha}{D_{AB}}\approx 1 \text{ (air–water)}
\;\Rightarrow\;
K_m=\frac{h_{conv}}{c_{p,h}\,Le^{2/3}}
$$
with $K_m$ [kg/(m²·s)] the mass-transfer coefficient and
$c_{p,h}=1006+1805\,\omega$ the specific heat of moist air. Since $Le\approx1$,
the **Sherwood** number inherits the same form as the Nusselt one
($Sh = 0.664\,Re^{1/2}Sc^{1/3}$ laminar / $0.037\,Re^{0.8}Sc^{1/3}$ turbulent).
Re-evaluating $h_{conv},K_m$ from quantities known at the start of the step **does
not break the linearity** of the air algebraic system.

**Wind convection on the outer wall — McAdams:**
$h_w = 5.7 + 3.8\,v_{viento}$ [W/m²·K] (enters $U_{total}$ and $U_{techo}$).

## 5. Materials, insulation and covers {#materiales}

### 5.1 Composite wall {#pared-compuesta}

The wall is defined as **layers in series**, each with its resistance; the total
conductive resistance $R_{cond}=\sum_i e_i/k_i$ is aggregated and converted to an
effective conductivity $k_{ais}=e_{cam,total}/R_{cond}$. Materials and insulation
come from catalogs.

### 5.2 Translucent surfaces — gain + loss {#techo-translucido}

Up to **5 faces** of the chamber (roof + 4 walls) can be translucent. Each face
$i$ has its own tilt and azimuth, derived from the **chamber orientation** and the
**mono-pitch roof** (`GeometriaCamara.caras()`; the geometry height is the **mean**
height, which preserves the volume and the flow section when the roof is tilted).
The irradiance on each face is its **POA** (Liu-Jordan transposition per face —
[Solar radiation](?manual=radiacion); a horizontal roof uses GHI directly, the
exact historical case).

**Gain — product/air split.** Each face intercepts a fraction $f_i$ of its
transmitted radiation directly on the product; the rest is absorbed by the opaque
inner surfaces (interior absorptance $\alpha_{int}$, default 0.85) and heats the
air:

$$
I_{eq,prod}=\frac{\sum_i f_i\,A_i\,POA_i}{A_{rad}},
\qquad
Q_{rad,aire}=\tau\,\alpha_{int}\sum_i (1-f_i)\,A_i\,POA_i
$$

The product receives $Q_{rad}=I_{eq,prod}\,\tau\,\alpha\,A_{rad}$ (like the
historical translucent roof, now with the equivalent irradiance of all the
faces); $Q_{rad,aire}$ enters the balance of $T_{flujo}$ (§4.1b). The interception
factors: the roof "sees" the product according to $f_{techo}=A_{rad}/A_{techo}$;
the walls according to the **silhouette of the stacked bed**
($f_{pared}=N_{bandejas}\,e_{capa}/H$). It is the **greenhouse effect** of a glazed
box: in the Box typology, the chamber **is** the collector.

**Conductive loss** of the glazing:
$U_{techo}=\left(\tfrac{1}{h_{conv}}+\tfrac{e_{techo}}{k_{ef}}+\tfrac{1}{h_w}\right)^{-1}$,
with $k_{ef}$ from the catalog's per-thickness map (multiwall polycarbonate),
applied to the **total translucent area** $\sum_i A_i$.

The translucent area is **subtracted from the opaque envelope** $A_{cuerpo}$ (to
avoid double-counting) and $U_{techo}\sum_i A_i$ is added to the balance of
$T_{flujo}$. Opaque envelope → no effect.

**Outside the model** (noted as a future improvement): overnight IR losses of the
glazing and vertical discretization of the product per tray.

## 6. Product model and the sorption isotherm {#producto}

### 6.1 The two product ODEs {#edos}

$$
\frac{dX_{prod}}{dt} = -\frac{\dot m_w}{M_s}
$$
$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = q_{prod} - \dot m_w\,L_v(T_{prod})
$$

with $q_{prod}=h_{conv}A_{prod}(T_{flujo}-T_{prod})$ the sensible heat the air
delivers to the product, and $c_{p,prod}=c_{ps}+c_{pa}X$ (dry+water mixture). The
second term is the **evaporative cooling** of the product (latent heat $L_v$).
They are integrated with `scipy.integrate.solve_ivp` and **event detection** at
$X_{objetivo}$.

### 6.2 The role of the sorption curve {#isotermas}

**There is no empirical kinetic curve MR(t):** the "drying curve" **emerges** from
integrating the diffusive balance. What governs the process is the **GAB
equilibrium sorption isotherm**, which delivers the **water activity** $a_w(X)$:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

Secasol uses the **analytical inversion** $a_w = f(X; X_m, C, K)$ (quadratic) to
fix $\omega_{sup}=\omega_{sat}(T_{prod})\,a_w(X)$. Physically: as the product
dries, $a_w$ **falls** → the driving force $(\omega_{sup}-\omega_{flujo})$
**decreases** → the drying rate **drops** by itself. Thus the **drying periods**
(falling rate) are reproduced **without** an empirical correlation: the slowdown
comes from the sorption thermodynamics, not from a fit. Each product brings its
parameters $X_m, C, K$ in the catalog; if calibration is missing, the system
**warns**. The conceptual basis is in [Drying physics](?manual=secado#isotermas).

## 7. Tray fluid dynamics — horizontal vs vertical {#bandejas}

The product exchange area is $A_{prod}=N_{bandejas}\cdot A_{bandeja}$. The **flow
direction** changes both the pressure drop and the convective regime:

- **HORIZONTAL (cross-flow):** the air passes **over** the trays. The convective
  coefficient is computed as **flat plate** (Pohlhausen/McAdams, §4.2); the
  pressure drop is $\Delta P_{malla}$ (form coefficient $K\rho v^2/2$ per tray)
  **plus**, if the bed is appreciable, $\Delta P_{lecho}$ by **Ergun**.
- **UPWARD VERTICAL (through-bed):** the air **crosses** the product bed. The
  pressure drop of the **packed bed (Ergun)** dominates:
  $$
  \frac{\Delta P}{L} = \underbrace{\frac{150\,\mu\,v_0\,(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}}_{\text{viscous (laminar)}}
   + \underbrace{\frac{1.75\,\rho\,v_0^2\,(1-\varepsilon)}{(\Phi_s d_p)\,\varepsilon^3}}_{\text{inertial (turbulent)}}
  $$
  with $\varepsilon$ bed porosity, $d_p$ particle diameter, $\Phi_s$ sphericity.
  The bed geometry is resolved by a priority chain (product catalog → tray →
  conservative defaults).

**The trade-off:** vertical flow maximizes the **air–product contact** (better
transfer, more even drying), but at the cost of **much greater pressure drop**
(penalizing the fan or the natural draft — see
[Technical · Motor and pressure drops](?manual=tec-chimenea)). Horizontal flow is
hydraulically gentler but transfers less. The **thin-bed (<5 cm)** warning bounds
the validity of the diffusive model.

---

**See also:** [4 · Drying chamber](?manual=camara) (usage guide),
[Psychrometry](?manual=psicrometria) and [Drying physics](?manual=secado)
(fundamentals), [Technical · Industrial mode](?manual=tec-industrial) (multi-zone
batch and tunnel), [Appendix · Implementation](?manual=apendice-codigo#camara),
[Bibliography](?manual=bibliografia#mujumdar).
