# Technical · Auxiliary heating system

Technical reference of the auxiliary: energy balance, set-point control,
consumption, impact on the global balance and start-up schedule of the industrial
hybrid. The usage guide is in [5 · Auxiliary heating](?manual=auxiliar).

## 1. What it is for and where it sits {#ubicacion}

The auxiliary (electric or biomass) is the dryer's **thermal backup**: it adds heat
when the sun is not enough (cloudy days, early start, dusk). It is **optional**. It
has two location modes:

- **IN SERIES AFTER THE COLLECTOR** — the auxiliary is **between the collector and
  the chamber**: it takes the air already preheated by the collector
  ($T_{ent}=T_{salida,colector}$) and finishes heating it before the chamber.
- **INDEPENDENT BACKUP** — it takes ambient air ($T_{ent}=T_{amb}$) and heats it on
  its own (total backup).

In **large scale** the air of all the branches is summed in the main duct and
**only then** enters the auxiliary (or directly the chamber).

## 2. Steady-state energy balance {#balance}

The auxiliary is modeled as a heater in **steady state, without thermal inertia**.
The energy balance over the air is:

$$
\boxed{\;Q_{eff} = \dot m\,c_{p,aire}\,(T_{salida}-T_{entrada})\;}
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p,aire}}
$$

with $c_{p,aire}\approx1007$ J/(kg·K). The available power is
$Q_{max}=P_{nominal}\cdot f_{operacion}$ (operating power fraction).

### 2.1 Set-point control (ideal proportional) {#set-point}

If there is a set-point $T_{sp}$, the auxiliary delivers **only** the power needed
to reach it:
$$
Q_{set} = \dot m\,c_{p}\,(T_{sp}-T_{entrada})
$$

- $Q_{set}<0$ → the air already exceeds the set-point: $Q_{eff}=0$ (with a
  warning).
- $0\le Q_{set}\le Q_{max}$ → $Q_{eff}=Q_{set}$ (active control, modulates).
- $Q_{set}>Q_{max}$ → $Q_{eff}=Q_{max}$ at full (warning of an unreachable
  set-point).

If there is no set-point, $Q_{eff}=Q_{max}$. There is also a physical cap
$T_{max,salida}$ that triggers a warning if exceeded.

### 2.2 Consumption {#consumos}

- **Electric resistance** ($\eta\approx1$): $P_{elec}=Q_{eff}$.
- **Biomass burner:** consumption [kg/h] proportional to the active fraction; the
  **total firewood** comes from the delivered energy, the LCV (lower calorific
  value) and the burner efficiency:
  $$ m_{leña} = \frac{E_{aux}}{PCI\cdot\eta_{quemador}} $$
  with $E_{aux}=\int Q_{eff}\,dt$ (trapezoidal integration over the horizon).

## 3. Impact on the global balance {#impacto}

The auxiliary **raises the temperature of the air stream** that feeds the chamber.
In the air chain (cabinet mode):

$$
T_{amb} \xrightarrow{\text{collector: }+\Delta T} T_1
\xrightarrow{\text{auxiliary: }+\Delta T} T_2
\xrightarrow{\text{chamber}} T_3 < T_2
$$

The $T_{salida}$ of the auxiliary becomes the **boundary condition** $T_{ent}$ of
the chamber thermodynamic engine ([Technical · Chamber](?manual=tec-camara)),
modifying the whole heat–mass balance downstream (more air temperature → more
evaporation capacity → faster drying). The auxiliary **does not add moisture**
($\omega$ constant): it is pure **sensible** heating — on the
[psychrometric chart](?manual=psicrometria) it is a horizontal segment.

In the **Transient/Window** modes, the auxiliary is evaluated **hour by hour** over
the series of $T_{ent}(t)$, reusing the scalar step-by-step logic, and accumulates
energy and firewood.

## 4. Temporal availability and start-up schedule {#calendario}

The auxiliary has a **temporal operation policy**:

- **Overnight availability**: if disabled and the irradiance series is available,
  the steps with $I_g \le 10$ W/m² (night) are forced to $Q_{eff}=0$ (auxiliary off
  at night).
- **Start-up schedule**: for the **industrial hybrid**, the burner operates in
  specific morning/dusk **hourly windows** (independent of the irradiance), not at
  constant power. Each step is mapped to its hour of the day
  $((t/3600)+\text{offset})\bmod 24$ and marked active if it falls within some
  window $[\text{start}, \text{start}+\text{duration})$ (with wrap if it crosses
  midnight).

This reproduces the real operation of an ADITAL-style hybrid dryer: the burner is
lit early to start the drying and at dusk so as not to lose the batch, accumulating
firewood in each window (see
[Technical · Industrial mode](?manual=tec-industrial#calendario)).

---

**See also:** [5 · Auxiliary heating](?manual=auxiliar) (usage guide),
[Technical · Chamber](?manual=tec-camara) (where the heated air enters),
[Appendix · Implementation](?manual=apendice-codigo#auxiliar).
