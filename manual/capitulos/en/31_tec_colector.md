# Technical · Solar air collector — physical and numerical model

Technical reference of the collector model: the 4 configurations, the
surface-by-surface energy balances, the local internal convective coefficient, the
numerical solution and the pressure drops. The usage guide is in
[3 · Solar collector](?manual=colector).

## 1. The four configurations {#configuraciones}

Secasol models **flat-plate solar air collectors** (*air heaters*) in four
topologies, which share materials and construction criteria and differ only in
**the location of the absorber and the flow circulation**:

| Type | Absorber | Circulation |
|---|---|---|
| **1** | at the bottom of the box | air **above** the absorber (single channel) |
| **2** | at mid-height (two channels) | flow through **both** channels (upper + lower) |
| **3** | at mid-height | flow through the **lower** channel; upper sealed |
| **4** | at mid-height | flow through the **upper** channel; lower sealed |

<!-- esquema: colectores_seccion_transversal | Cross-section of the 4 types. -->

The box is built of wood or double galvanized sheet with intermediate insulation;
the cover is of high-transmittance material (multiwall polycarbonate, greenhouse
film, glass). The absorber can have width $W_{abs} \ge W$ (corrugated sheet).

## 2. Fundamental physical assumptions {#hipotesis}

Common to all 4 types:

1. **Quasi-steady:** heat accumulation in all surfaces is neglected. The temporal
   variations come only from the ambient conditions (temperature, irradiance,
   wind) or from the air flow.
2. **Unidirectional and developed flow** in x (flow direction). It can be laminar,
   in transition or turbulent; natural or forced.
3. **Effective 1D transfer in x and y**, negligible in z (width): homogeneous and
   isotropic surfaces.
4. **Continuity:** a single inlet at $x=0$ (at $T_{amb}$ or at the outlet of the
   previous segment), a single outlet at $x=L$.
5. **Absorber of negligible thickness** → no internal conduction; both faces at
   $T_{abs}$. (The plate thickness is exposed in the UI but **does not enter the
   balance**: a conscious decision, negligible plate capacitance.)
6. **Composite wall sheet+insulation+sheet** → thermal resistance = that of the
   insulation (the conduction in the sheets is neglected).
7. **Lateral losses** ≪ losses up and down → absorbed into the y direction.
8. **Negligible cover absorptivity** ($\alpha_{cub}\approx 0$, it only transmits
   and re-emits IR).

**Boundary conditions:**

- Fluid inlet: $T_f(x{=}0) = T_{entrada}$ (ambient, or the outlet of the previous
  module in series).
- Upper face: wind convection (McAdams) + radiation to the sky (Swinbank).
- Lower face: conduction through the insulation + wind convection at the bottom.
- The "initial condition" of the quasi-steady problem is the **warm-start** of the
  previous node (there is no temporal transient within the collector).

## 3. Surface-by-surface energy balances {#balances}

Notation: $\sigma$ = Stefan-Boltzmann; $h_w$ = wind convection; $h_{int}$ =
internal convection; $\tau_{cub}$, $\alpha_{abs}$ optical; $U_{ais}=k_{ais}/e_{ais}$;
$T_{cie}$ sky temperature; $dA_{cub}=W\,dx$, $dA_{abs}=W_{abs}\,dx$. All
temperatures in **K**.

### 3.1 Type 1 — single channel, absorber at the bottom {#tipo1}

**Cover (outer face):**
$$
h_w(T_{cub,e}-T_{amb}) + \varepsilon_{cub}\sigma(T_{cub,e}^4-T_{cie}^4)
  + U_{cub}(T_{cub,e}-T_{cub,i}) = 0
$$

**Cover (inner face):**
$$
U_{cub}(T_{cub,e}-T_{cub,i}) - h_{int}(T_{cub,i}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{cub,i}^4-T_{abs}^4) = 0
$$

**Absorber:**
$$
I_g\,\tau_{cub}\,\alpha_{abs}
  - h_{int}(T_{abs}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{abs}^4-T_{cub,i}^4)
  - U_{ais}(T_{abs}-T_{bot}) = 0
$$

**Bottom (body):** balance that solves $T_{bot}$ analytically:
$$
U_{ais}(T_{abs}-T_{bot}) = h_w(T_{bot}-T_{amb})
\;\Rightarrow\;
T_{bot}=\frac{U_{ais}T_{abs}+h_w T_{amb}}{U_{ais}+h_w}
$$

**Fluid (ODE in x)** — the air gains from the inner cover and the absorber:
$$
\dot m\,c_p\,\frac{dT_f}{dx}
  = h_{int}\,W\,(T_{cub,i}-T_f) + h_{int}\,W_{abs}\,(T_{abs}-T_f)
$$

### 3.2 Type 2 — two active channels {#tipo2}

The inner face of the bottom $T_{int}$ appears and a second channel with its own
$h_{int,2}$, $\dot m_2$. The absorber exchanges with **both** flows by convection,
with the cover and with the bottom by radiation:
$$
I_g\tau_{cub}\alpha_{abs}
= \varepsilon_{eff}\sigma(T_{abs}^4-T_{cub,i}^4)
 + h_{int,1}(T_{abs}-T_{cs})
 + h_{int,2}(T_{abs}-T_{ci})
 + \varepsilon_{eff}\sigma(T_{abs}^4-T_{int}^4)
$$

Fluid ODEs in the upper and lower channel (analogous, each with its $\dot m$):
$$
\dot m_1 c_p \frac{dT_{cs}}{dx}=h_{int,1}W(T_{cub,i}-T_{cs})+h_{int,1}W_{abs}(T_{abs}-T_{cs})
$$
$$
\dot m_2 c_p \frac{dT_{ci}}{dx}=h_{int,2}W_{abs}(T_{abs}-T_{ci})+h_{int,2}W(T_{int}-T_{ci})
$$

Bottom: $U_{ais}(T_{int}-T_{bot})=h_w(T_{bot}-T_{amb})$.

### 3.3 Type 3 — only the lower channel active {#tipo3}

The upper channel is a **sealed enclosure** (air cavity): the cover↔absorber
transfer goes from forced convection to **natural convection in a cavity
(Hollands) + radiation**. The fluid balance exists only in the lower channel
(identical to that of the lower Type 2). The absorber loses to the upper channel
only by natural convection and radiation.

### 3.4 Type 4 — only the upper channel active {#tipo4}

Symmetric to Type 3: the **lower** channel is the sealed cavity; the fluid
circulates through the upper channel (ODE identical to the upper Type 2). The
lower cavity provides absorber↔bottom coupling by natural convection + radiation.

### Double cover (all types) {#doble-cubierta}

With two covers, the cover conductance $U_{cub}$ is no longer $k_{cub}/e_{cub}$ and
becomes an **effective conductance** that combines conduction in each sheet +
**Hollands natural convection** in the air cavity between covers + **gray
radiation** between parallel surfaces.

## 4. Local internal convective coefficient {#nusselt}

The internal convective coefficient **is not a single scalar** at a fixed
temperature: it is evaluated **locally, node by node**.

### 4.1 Local recipe per node {#receta-local}

For each node x:

1. **Air properties varying with T** evaluated at the film temperature
   $T_{film}=(T_f+T_{pared})/2$: $k(T),\mu(T),Pr(T),c_p(T),\rho(T,P)$.
2. **Local Reynolds** with the mass flux per unit area $G=\dot m/A_{sec}$
   (constant) and the local viscosity: $Re = G\,D_h/\mu(T_{film})$. The hydraulic
   diameter of a rectangular channel is $D_h = 2\,W\,a/(W+a)$ with $a$ the channel
   height.
3. **Local mixed Nusselt** = forced (with thermal entry + continuous regime
   blending at $Re=2300$ and $Re=10000$) combined with **buoyancy**: local
   Rayleigh with the gravity component along the channel,
   $Ra = g\sin\beta\,\beta_{exp}\,\Delta T\,D_h^3/(\nu\,\alpha)$, via the
   **Churchill mixed convection** correlation.
4. $h_{int}(x) = Nu(x)\,k(T_{film})/D_h$.

The correlation catalog provides both the correlations **averaged** over $L$
(automatic selection, used in previews and validation) and the **local** versions
node by node, used by the solvers. The local ones are built so that their
**average over $0\!\to\!L$ exactly reproduces** the equivalent averaged
correlation (Heaton in laminar, Cengel in turbulent — see §4.4).

### 4.2 Forced-flow correlations {#correlaciones-forzado}

Regime by Reynolds number: **laminar** $Re<2300$, **transition**
$2300\le Re\le 10^4$, **turbulent** $Re>10^4$. The choice within each regime also
depends on $L/D_h$ (thermal entry effects) and on how many walls of the channel
heat the flow (one wall → Types 1, 3, 4; two walls → Type 2).

| Correlation | Nu expression | Regime / range | Walls |
|---|---|---|---|
| **Shah & London (1978)** | $Nu = 5.385$ | Developed laminar, $Re<2300$, $L/D_h\ge 50$ | 1 wall (H2 case) |
| **Shah & London symmetric** | $Nu = 8.235$ | Developed laminar, $Re<2300$, $L/D_h\ge 50$ (Type 2) | 2 walls (H1 case) |
| **Heaton, Reynolds & Kays (1964)** | $Nu = 5.385\,(1+0.0668\,Gz^{2/3})$, $\;Gz=Re\,Pr\,D_h/L$ | Laminar in **thermal entry**, $Re<2300$, $L/D_h<50$, $Pr>0.5$ | 1 wall |
| **Gnielinski (1976)** | $Nu = \dfrac{(f/8)(Re-1000)Pr}{1+12.7\sqrt{f/8}\,(Pr^{2/3}-1)}$, $\;f=(0.790\ln Re-1.64)^{-2}$ | **Transition**, $2300\le Re\le 10^4$, $0.5<Pr<2000$ | (either) |
| **Sparrow & Liu (1979)** | $Nu = 0.0158\,Re^{0.8}$ | Turbulent, $Re>10^4$; default for **one heated wall** (Types 1, 3, 4) | 1 wall |
| **Dittus-Boelter (1930)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}$ (exp. 0.4: heated fluid) | Turbulent, $Re>10^4$, $0.6<Pr<160$, $L/D_h>10$; default for **two walls** (Type 2) | 2 walls |
| **Cengel & Ghajar (2014)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}\,[1+(D_h/L)^{0.7}]$ | Turbulent with **thermal entry**, $Re>10^4$, $L/D_h<10$; converges to Dittus-Boelter for $L/D_h>60$ | (either) |

### 4.3 Natural and mixed convection {#correlaciones-natural}

It appears in two contexts: (a) the **sealed cavities** and the **double-cover
cavity** (Types 3/4 and double cover), and (b) the **buoyancy** component that adds
to the forced one in the active channel at low velocity or high tilt.

| Correlation | Nu expression | Application range |
|---|---|---|
| **Hollands et al. (1976)** — inclined cavity | $Nu = 1 + 1.44\big[1-\tfrac{1708}{Ra\cos\theta}\big]^{+}\!\big[1-\tfrac{1708\sin(1.8\theta)^{1.6}}{Ra\cos\theta}\big] + \big[(\tfrac{Ra\cos\theta}{5830})^{1/3}-1\big]^{+}$ | Cavity, $\theta\in[0°,75°]$, $Ra\lesssim 10^{8}$. For $Ra\cos\theta<1708$: $Nu=1$ (pure conduction). $[x]^{+}=\max(0,x)$ |
| **Churchill-Chu** (natural component of the channel) | $Nu_{nat} = \dfrac{0.670\,Ra^{1/4}}{[1+(0.492/Pr)^{9/16}]^{4/9}}$ | Local **buoyancy** contribution (plate, laminar); $Ra$ with the $g\sin\beta$ component. $Nu_{nat}\to0$ when $Ra\to0$ |
| **Churchill mixed convection** | $Nu = (Nu_{forz}^{3} + Nu_{nat}^{3})^{1/3}$ | **Assisted** buoyancy. Reduces to forced if $Ra\to0$; the natural dominates if $Gr/Re^{2}\gg1$ |

### 4.4 Automatic selection and regime blending {#seleccion}

With automatic selection, the logic is:

- **$Re<2300$ (laminar):** Heaton if $L/D_h<50$ (thermal entry), otherwise Shah &
  London — symmetric for two walls (Type 2), asymmetric for one wall.
- **$2300\le Re\le 10^4$ (transition):** Gnielinski.
- **$Re>10^4$ (turbulent):** Cengel if $L/D_h<10$ (pronounced entry); otherwise
  Sparrow & Liu for one wall or Dittus-Boelter for two walls.

If the user forces a correlation outside its $Re$ range or wall type, a warning is
emitted without aborting the calculation.

In the **local** versions, the switching between regimes is not a jump: there is a
**continuous C¹ blending** in bands of $\pm400$ around $Re=2300$ and $Re=10^4$, so
$Nu(x)$ does not jump if the local $Re$ crosses a threshold along the collector as
$\mu(T)$ varies. The local entry enhancements are calibrated so their integral
reproduces the averaged correlations: laminar
$Nu_x = Nu_\infty(1+0.02227\,Gz_x^{2/3})$ averages to Heaton
($3\times0.02227=0.0668$); turbulent $(1+0.3\,(D_h/x)^{0.7})$ averages to Cengel
($3.333\times0.3=1$).

### 4.5 Mass flow {#caudal}

The mass flow is fixed with $\rho(T_{entrada})$ — the design **volumetric** flow is
set at the inlet:
$$Q = n_{par}\,v_{dis}\,W\,a, \qquad \dot m = \rho(T_{ent})\,Q$$

## 5. Numerical solution {#numerica}

The model is **coupled quasi-steady**: an ODE of the fluid in x plus a nonlinear
algebraic system of surfaces at each node.

### 5.1 Two-level scheme {#dos-niveles}

- **Outer level — integration of the fluid ODE** $dT_f/dx$ with
  `scipy.integrate.solve_ivp`, **RK45** method, tolerances $10^{-6}$, over
  $x\in[0, L_{total}]$ with $L_{total}=L_{unidad}\cdot n_{serie}$ and a bounded max
  step to guarantee a minimum discretization.
- **Inner level — algebraic system per node** with `scipy.optimize.fsolve`. In
  Type 1 the unknowns are **3**: $[T_{cub,e}, T_{cub,i}, T_{abs}]$, with $T_{bot}$
  solved analytically; in Types 2–4 $T_{int}$ and/or cavity couplings are added.
  The residual is the vector of surface balances; the solver finds its root.

### 5.2 Warm-start {#warm-start}

Each call to the node solver starts from the solution of the **previous node**.
This speeds convergence and gives robustness. The warm-start wall temperature in
turn feeds the $T_{film}$ and the Rayleigh of the local $h_{int}$
(convection–buoyancy coupling).

### 5.3 Discretization {#discretizacion}

The collector is discretized **in the axial coordinate x** (flow direction): the
adaptive integrator places the nodes, with a minimum node floor. At each node the
full transverse plane is solved (cover, absorber, bottom, fluid). It is not
discretized in y or z (1D assumption). In a series array, the outlet of one module
is the inlet condition of the next.

### 5.4 Convergence and diagnostics {#convergencia}

If the integration does not converge, the calculation fails explicitly. If a
node's system does not converge, a warning is logged but the integration continues
with the approximate solution. The result carries a convergence indicator.

## 6. Modularity {#modularidad}

Modularity operates at **three levels**:

1. **Sections** — the project is built section by section; the physics of each one
   lives isolated from the interface.
2. **Components** — the collector chooses type 1–4: same calculation interface,
   different balance topology. The core of the local $h_{int}$ is **reused** across
   types.
3. **Subcomponents** — cover, plate, insulation and bottom are chosen from
   **materials catalogs** and validated when building the data model. Changing a
   material is changing a catalog entry, without touching the physics. The geometry
   is separated into a unit module and array (series/parallel).

## 7. Pressure drops in the collector {#perdidas}

The frictional pressure drop of the channel is computed with **Darcy-Weisbach** and
the **Haaland friction factor (1983)** (an explicit approximation of
Colebrook-White, error < 2 %):

$$
\Delta P = f\,\frac{L_{total}}{D_h}\,\frac{\rho\,v^2}{2},
\qquad
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
$$

with $\varepsilon$ the **real roughness** of the absorber plate (from the catalog;
conservative default $5\times10^{-5}$ m of painted sheet). Rules by type:

- **Type 1:** single channel (channel height).
- **Type 2:** two channels in parallel → $\Delta P = \max(\Delta P_{cs}, \Delta P_{ci})$.
- **Type 3:** lower channel active.
- **Type 4:** upper channel active.

In an **array**: series → $\Delta P$ scales with the total length; parallel →
$\Delta P$ of one branch. This $\Delta P$ feeds the sizing of the fan (forced) or
the draft loop (natural) — see
[Technical · Motor, chimney and pressure drops](?manual=tec-chimenea).

---

**See also:** [3 · Solar collector](?manual=colector) (usage guide),
[Solar radiation and oriented plane](?manual=radiacion) (the collector receives
POA, not GHI), [Appendix · Implementation](?manual=apendice-codigo#colector),
[Bibliography](?manual=bibliografia#duffie-beckman).
