# Technical · Industrial mode / Large scale

Technical reference of the **Large scale** typology: the two subtypes (batch and
semi-continuous), the array and the collector field, the main duct and the chamber
with moisture gradients. The physical reference of the semi-continuous subtype is
the **ADITAL** hybrid dryer of San Carlos (Salta). The usage guide of the typology
is in [1 · Typology](?manual=tipologia).

## 1. What the industrial mode is {#subtipos}

The **Large scale** typology has **two subtypes of equal rank**:

- **BATCH** — batch drying (cascade of **N=1** zone).
- **SEMI-CONTINUOUS** — a **counter-current** ADITAL-style tunnel (**N** zones in
  series, air and product in opposite directions).

**Period = window**: instead of the daily/annual binary, the analysis runs over a
**real span** [start, end] with hourly climate (a week, a month, a campaign). The
window is also available for Box/Cabinet as real multi-day.

The air circuit is: **collector array → main duct → (auxiliary) → chamber/tunnel →
outlet**.

## 2. Industrial collector — array and field {#campo}

### 2.1 Series/parallel array {#banco}

The array combines modules **in series** (the air heats progressively, the outlet
of one is the inlet of the next) and branches **in parallel** (they share the
flow). Each module is solved with the **same collector solver** of Types 1–4
([Technical · Collector](?manual=tec-colector)), hour by hour.

### 2.2 Collector field — real flow split {#reparto}

At large scale the flow split between branches **is not assumed uniform**: the full
**hydraulic network** is solved, following the methodology of **ASHRAE Handbook
2017, ch. 21 (Duct Design)**:

- **Per-segment friction** of the trunk: Darcy-Weisbach + Haaland, with the local
  duct section (constant or increasing).
- **Inlet fittings**: $\Delta P = C\,\rho v^2/2$ (reducing cone + butterfly valve)
  referred to the branch section.
- **Total pressure equality**: all trajectories (branch $i$ + trunk from its inlet
  to the fan) see the **same** $\Delta P$. The split $\{q_i\}$ is solved by
  **damped fixed point** over that equality.

Convention: inlet 1 is the far end from the fan; the trunk is discretized into N
segments and segment $i$ carries the accumulated flow of inlets $1..i$. Each branch
is thermally evaluated **at its own flow** → outlet temperature per branch.

## 3. Main duct (manifold) {#cano-maestro}

The **main duct** is the manifold that collects the air from all the branches and
takes it to the fan/chamber. It has three pre-design models:

### 3.1 Pressure drop with accumulated flow {#dp-cano}

The flow **grows linearly** along the duct: $Q(f)=Q_{total}\cdot f$, with $f=0$ at
the far end and $f=1$ at the fan. The friction is **integrated per segment** with
the **local** flow and section:
$$
\Delta P_{fric} = \sum_j f_j\,\frac{dx}{D_{h,j}}\,\frac{\rho\,v_j^2}{2},
\qquad v_j = \frac{Q(f_j)}{A_j}
$$
The fittings (reducing cone + butterfly valve of a representative path) are applied
to the dynamic pressure at the fan end:
$\Delta P_{acc}=(K_{campana}+K_{mariposa})\,\rho v_{fin}^2/2$.

**Section compensation:** an **increasing-section** duct keeps the velocity bounded
as it accumulates flow, whereas a small constant-section duct would spike the
velocity (and the friction $\propto v^2$) near the fan. The model reports the
maximum velocity along the duct — bounded if the section compensates the
accumulated flow. The key of the model is to use the **accumulated flow** (not the
constant total flow) so that the compensation is reflected.

### 3.2 Thermal balance — two variants {#dt-cano}

The duct may be outdoors. The balance gives
$\Delta T=(Q_{solar}-Q_{perdida})/(\dot m\,c_p)$:

$$
Q_{perdida} = (U_{lados}A_{resto} + U_{sup}A_{sup})\,(T_{aire}-T_{amb}),
\qquad
Q_{solar} = \tau\,\alpha\,A_{sup}\,I_g
$$

with $U=\big(1/h_{int}+R_{ais}+1/h_w\big)^{-1}$ — internal film by forced
convection (turbulent Dittus-Boelter, $Nu=3.66$ laminar), insulation conduction
(if insulated) and external McAdams film.

- **Variant without solar gain**: $Q_{solar}=0$ → the air only **loses** heat;
  $\Delta T<0$ (≈ −2.8 °C in the ADITAL case).
- **Variant with solar gain**: the upper face acts as a mini-collector
  ($Q_{solar}=\tau\alpha A_{sup}I_g$). If it also carries a **translucent cover**,
  the air cavity adds resistance ($U_{sup}<U_{lados}$, greenhouse effect) and the
  gain is affected by $\tau$.

**Watch out in pre-design:** the default solar absorptance (0.90) is for **painted
sheet**; **bare galvanized** needs $\alpha\approx0.35$.

### 3.3 Distribution uniformity {#uniformidad}

Simple criterion: the split is uniform if the trunk $\Delta P$ is **small compared
to** the $\Delta P$ of one branch: $\text{ratio}=\Delta P_{cano}/\Delta P_{rama}$,
uniform if $<0.15$.

## 4. Chamber with moisture gradients — multi-stage engine {#cascada}

Batch and semi-continuous are **the same** cascade engine with a different
**topology**. It reuses intact the physical core of the chamber (diffusive
evaporation + GAB + time-varying coefficients — [Technical · Chamber](?manual=tec-camara)).

### 4.1 Batch = cascade of N=1 {#batch}

A single CSTR with a single air pass. Equivalent to the cabinet engine but run over
the production window, accumulating batches.

### 4.2 Semi-continuous = N counter-current zones {#semicontinuo}

The ADITAL-style tunnel is **N cart columns in series**:

- The **air** marches from zone $N{-}1$ (dry/hot end, receives the air from the
  collector+auxiliary) toward zone $0$ (cool/humid end, discharges to the
  environment).
- The **product advances in the opposite direction**: it enters fresh through zone
  $0$ and is discharged dry through zone $N{-}1$.

**Integrated state:** $y=[T_0,X_0,T_1,X_1,\dots,T_{N-1},X_{N-1}]$ (2N variables).
At each evaluation of the system the **air is marched** $N{-}1\to0$ (N
**sequential** algebraic solutions of the same CSTR): for zone $i$, the inlet air
is the **outlet of zone $i{+}1$** (the hotter neighbor). **There is no intra-step
iteration**: the product is quasi-frozen in the step, so the air system is linear
and direct.

**Column advance:** with a fixed cadence, the columns jump one position (discrete
jump of the state: zone $i \leftarrow$ product of zone $i{-}1$; zone $0 \leftarrow$
fresh load; zone $N{-}1 \rightarrow$ discharge). Between advances a segment is
integrated with the ODE integrator.

**Emergent outlet dryness:** the cadence is **fixed**; it is **not** adjusted to
reach $X_{objetivo}$. The outlet dryness is a **result** of the system, not a
constraint that is forced. $X_{objetivo}$ only serves to **warn** of
under/over-drying. The tunnel starts full of fresh product; after ~N advances it
reaches **steady state** and the **spatial profile** $X(\text{zone})$,
$T_{prod}(\text{zone})$, $T_{aire}(\text{zone})$ is reported.

## 5. Hybrid with start-up schedule {#calendario}

The biomass burner operates in **hourly windows** in the morning/at dusk
(independent of the irradiance), not at constant power, and **accumulates
firewood**. Physical detail in [Technical · Auxiliary heating](?manual=tec-auxiliar).

## 6. Window orchestration {#orquestacion}

Three layers: the hourly **forcings** (forced collector hour by hour + main-duct ΔT
+ auxiliary with schedule), the batch↔cascade **dispatch** according to the subtype
(accumulating production: kg of dry product + steady-state rate kg/day + firewood),
and the **entry point** that the [7 · Results](?manual=resultados) section consumes
for the production dashboard.

## 7. Validation against ADITAL {#adital}

A standalone validation script contrasts the full thermal chain against field data
of the ADITAL dryer of San Carlos:

| Check | Expected | Status |
|---|---|---|
| Collector outlet | ~55 / 78 °C | ✓ |
| Main-duct ΔT | −2.8 °C | ✓ |
| Chamber | 57 °C | ✓ |
| Campaign | 5000 kg in ~5 days | ✓ |

It is an **order-of-magnitude check**, not a calibration: Secasol is a **general**
pre-designer; ADITAL is a reference for dimensions/flows/temperatures, not a fitting
target.

---

**See also:** [1 · Typology](?manual=tipologia) (where the subtype and the window
are chosen), [Technical · Chamber](?manual=tec-camara) (the physical core the
cascade reuses), [Technical · Motor and pressure drops](?manual=tec-chimenea),
[Appendix · Implementation](?manual=apendice-codigo#industrial),
[Bibliography](?manual=bibliografia#ashrae).
