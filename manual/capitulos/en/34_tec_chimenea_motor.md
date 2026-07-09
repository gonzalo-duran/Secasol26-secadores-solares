# Technical · Motor, solar chimney and pressure drops

Technical reference of the air movement: global system pressure drops (equations
per segment), fan sizing in forced convection, equilibrium flow in natural
convection, Picard loop, wind extractor and solar chimney sizing. The usage guide
is in [6 · Motor and chimney](?manual=motor).

## 1. Two ways to move the air {#dos-formas}

The air can circulate by **forced convection** (axial or centrifugal fan) or by
**natural convection** (solar chimney, optionally with a wind extractor). The
Motor section enables one or the other: with the motor off the chimney appears. The
wind extractor is a **chimney accessory**, not a type of motor.

In both cases the **global pressure drop** of the loop is needed. The difference:
in forced, the $\Delta P$ **sizes the motor**; in natural, the $\Delta P$ (as a
function of the flow) **determines the equilibrium flow**.

## 2. Global pressure drops — equations per segment {#perdidas}

The losses are decomposed into segments in series. All use the same **Haaland**
friction factor (explicit approximation of Colebrook-White, ASHRAE ch. 21):

$$
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
\quad(Re>4000),
\qquad f=\frac{64}{Re}\ (Re<2300)
$$

with a linear blend in the transition $2300<Re<4000$.

### 2.1 Collector (rectangular channel) — Darcy-Weisbach {#dp-colector}

$$
\Delta P_{col} = f\,\frac{L}{D_h}\,\frac{\rho v^2}{2},\qquad D_h=\frac{2We}{W+e}
$$

Series: $\Delta P_{rama}=\Delta P_{unidad}\times n_{serie}$; parallel:
$\Delta P_{banco}=\Delta P_{rama}$.

### 2.2 Chamber — according to flow orientation {#dp-camara}

- **HORIZONTAL (cross-flow):** the $n_{bandejas}-1$ channels between trays are **in
  parallel** → the system $\Delta P$ is that of **one** channel.
  $\Delta P_{cam}=\Delta P_{producto}+\Delta P_{malla}$, with $\Delta P_{producto}$
  = rough friction (effective roughness $\varepsilon_{eff}=\max(\varepsilon_{chapa},d_p)$)
  + blockage obstruction $C_{obs}(\beta)$, $\beta=e_{capa}/\text{spacing}$.
- **UPWARD VERTICAL (through-bed):** per tray $\Delta P=\Delta P_{malla}+\Delta P_{lecho}$
  with **Ergun**:
  $$
  \frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
  $$
  The mesh $\Delta P$ uses Idelchik/Crane-type K coefficients according to the mesh
  type.

### 2.3 Ducts and fittings {#dp-ductos}

$\Delta P_{ductos}$ by Darcy-Weisbach (galvanized roughness
$\varepsilon\approx0.15$ mm, ASHRAE) and fittings $\Delta P=K\,\rho v^2/2$ (bends,
expansions, inlets/outlets).

### 2.4 Main duct (large scale only) {#dp-cano}

In Large scale the $\Delta P$ of the main duct is **added** (accumulated flow,
variable section — see [Technical · Industrial mode](?manual=tec-industrial#dp-cano)).

**Air properties:** $\rho(T,P)=P/(R_{aire}T)$ (ideal gas, $R_{aire}=287.058$);
$\mu(T)$ by Sutherland; atmospheric pressure by altitude according to the standard
atmosphere (ISA).

## 3. Forced convection — motor sizing {#forzada}

With the total $\Delta P$ and the volumetric flow $Q$, the powers are computed in a
cascade:

$$
P_{hid}=Q\,\Delta P
\;\xrightarrow{/\eta_{vent}}\;
P_{eje}=\frac{P_{hid}}{\eta_{vent}}
\;\xrightarrow{/\eta_{motor}}\;
P_{elec}=\frac{P_{eje}}{\eta_{motor}}
\;\xrightarrow{\times FS}\;
P_{inst}=P_{elec}\cdot FS
$$

with $\eta_{vent}$ fan efficiency, $\eta_{motor}$ electric motor efficiency, $FS$
service factor. The **rated current** comes from $I=P_{elec}/(V\cos\varphi)$, with
$\cos\varphi=0.85$ (small motor). If the user sets a discharge velocity, the
dynamic pressure $\Delta P_{din}=\rho v_{desc}^2/2$ is added to the total
$\Delta P$.

**Empirical anchor** to validate the order of magnitude: a 76 W / 900 m³/h
extractor in a ~50 kg cabinet → expected $P_{elec}$ **50–100 W**.

## 4. Natural convection — equilibrium flow {#natural}

Without a motor, the air circulates by **thermal draft**. The equilibrium flow is
the one at which the **driving** pressure equals the **resistive** one:

$$
\boxed{\;\Delta P_{tiro} + \Delta P_{turbina,motriz} = \Delta P_{chimenea}(\dot m) + \Delta P_{resto}(\dot m)\;}
$$

### 4.1 Thermal draft (stack effect) {#tiro}

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim}),
\qquad H_{eff}=H_{chimenea}+H_{camara}
$$

With an ideal gas at common pressure $\rho\propto1/T$, so $\Delta P_{tiro}>0$ when
$T_{chim}>T_{amb}$ (upward flow) and $\Delta P_{tiro}<0$ when $T_{chim}<T_{amb}$
(null draft at night → $\dot m=0$). $H_{eff}$ includes the useful height of the
chamber (from the cold-air inlet to the base of the chimney).

### 4.2 Numerical solution {#brentq}

$\Delta P_{chimenea}(\dot m)$ (friction + fittings + extractor resistance) and
$\Delta P_{resto}(\dot m)$ (collector + chamber + ducts, a monotonic function with
$f(0)=0$) are functions of the flow. The root of the equilibrium equation is solved
with **`scipy.optimize.brentq`** bounded to $[\dot m_{min}, \dot m_{max}]$. It
returns $\dot m$, the chimney velocity and all the $\Delta P$ components.

## 5. Wind extractor (Chinese-hat turbine) {#extractor}

Optional accessory on top of the chimney. It adds **two** terms:

- **Driving** — depression generated by the rotation of the turbine:
  $$\Delta P_{turbina}=C_p\,\rho_{amb}\,v_{viento}^2/2$$
  with $C_p\approx0.3$–$0.6$. The NASA POWER wind (measured at **10 m**) is
  corrected to the **top height** $z=H_{camara}+H_{chimenea}$ by a **logarithmic
  profile**:
  $$v(z)=v_{10}\,\frac{\ln(z/z_0)}{\ln(10/z_0)}$$
  with $z_0$ the aerodynamic roughness of the terrain.
- **Resistive** — the turbine obstructs the flow:
  $\Delta P=K_t\,\rho_{chim}\,v_{ext}^2/2$, evaluated at the velocity through the
  extractor's own diameter.

The driving term enters the left side of the equilibrium equation; the resistive
one, the $\Delta P_{chimenea}$.

## 6. Picard loop — thermal-hydraulic coupling {#picard}

The natural flow takes $T_{chim}$ **as a given**, but physically $T_{chim}$ depends
on the flow (more flow, less $\Delta T$ in the collector → $T_{chim}$ drops → less
draft). This coupling is closed with **fixed-point iteration (Picard)** over the
triangle:

$$
T_{chim} \longleftrightarrow \dot m_{nat} \longleftrightarrow T_{salida,colector}
$$

- **Constants mode**: up to 10 iterations, tolerance 0.5 K. In each iteration the
  steady collector is re-run with the velocity implied by the natural flow,
  $\dot m_{nat}$ is recomputed, and the chamber air temperature feeds back
  $T_{chim}$.
- **Transient mode**: Picard over the **whole hourly horizon**, up to 5 iterations,
  tolerance 0.5 K. Per iteration $\dot m(t)$ is computed hour by hour, the collector
  solver is re-run each hour with the effective velocity
  $v(t)=\dot m_{nat}(t)/(\rho A_{canal} n_{par})$, the chamber engine consumes the
  new forcings and $T_{flujo}(t)$ feeds back $T_{chim}(t)$.

If the chimney has an **active extractor**, the loop balance also adds
$\Delta P_{turbina,motriz}(v_{viento}(t))$ to the driving side and $K_t\rho v^2/2$
to the resistive one. The hours with null draft ($T_{chim}\le T_{amb}$) receive
$\dot m=0$.

## 7. Solar chimney sizing {#chimenea}

The chimney is sized by its **geometry** (diameter, height), which fixes:

- The **available draft** via $H_{eff}$ (the greater the height, the greater the
  $\Delta P_{tiro}$).
- Its **own resistance** $\Delta P_{chimenea}=K_{total}\,\rho v^2/2$ with
  $K_{total}=f\,H/D+K_{singular}$.

The pre-design seeks the diameter/height combination that delivers the target flow
with the collector's expected $\Delta T$. The chimney is a **top-level** component
of the project (not a subcomponent of the collector), which allows a solar chimney
in the Box typology too.

---

**See also:** [6 · Motor and chimney](?manual=motor) (usage guide),
[Technical · Collector](?manual=tec-colector#perdidas) and
[Technical · Chamber](?manual=tec-camara#bandejas) (the $\Delta P$ of each segment),
[Technical · Global balance](?manual=tec-resultados) (where the loop is closed),
[Appendix · Implementation](?manual=apendice-codigo#motor),
[Bibliography](?manual=bibliografia#ashrae).
