# 6 · Fan, blower and solar chimney

Something has to move the air through the collector, the chamber and the ducts.
There are two paths: **forced convection** (a fan with an electric motor — more
control, more flow, consumes energy) or **natural convection** (a solar chimney
that induces thermal draft — no electricity, lower flow that varies with the
sun). This section sizes one or the other from the **pressure drop** of the whole
circuit.

## Choosing the drive {#eleccion}

Practical rules:

- **Forced**: necessary with thick beds or vertical flow (high pressure drop),
  large collector arrays, or when the process demands a stable flow. It is the
  safe option at industrial scale.
- **Natural**: attractive where there is no electrical grid or a zero operating
  cost is sought. It requires a hydraulically "gentle" circuit (low losses) and
  accepts that the flow follows the sun: at night there is no draft.

With the motor off, the section offers the **solar chimney**; they are mutually
exclusive.

## Motor / fan {#motor}

You choose the type (axial/centrifugal), the design flow and the efficiencies.
With the total system pressure drop, Secasol computes the power cascade:

$$
P_{hid}=Q\,\Delta P
\;\to\; P_{eje}=P_{hid}/\eta_{vent}
\;\to\; P_{elec}=P_{eje}/\eta_{motor}
\;\to\; P_{inst}=P_{elec}\cdot FS
$$

and the estimated rated current. A healthy order of magnitude for a ~50 kg
cabinet: **50–100 electrical W** (a commercial 900 m³/h extractor is around
76 W). If the number comes out far above, the circuit has too much pressure drop
— check the bed, velocities and ducts before enlarging the motor.

## Solar chimney {#chimenea}

The chimney generates **thermal draft**: the hot air inside it weighs less than
the ambient and "floats", drawing air through the dryer:

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim})
$$

The greater the **height** and the higher the interior **temperature**, the more
draft. The resulting flow **is not assumed: it is solved** — it is the point
where the available draft equals the circuit resistance. At night
($T_{chim}\le T_{amb}$) the draft is null and the flow zero: natural drying is
intrinsically daytime.

<!-- profundidad: The collector–chimney coupling (Picard loop) -->
There is a subtle coupling: the draft depends on the chimney temperature, which
depends on the collector outlet, which depends on the flow… which depends on the
draft. Secasol closes this loop by **fixed-point iteration (Picard)**: it starts
from an estimate, runs the collector, recomputes the natural flow and repeats
until it converges (both in constants mode and hour by hour in the transient).
That is why the "Calculate chimney" button in this section gives a **preliminary**
number with a temperature heuristic, and the final number — with the full loop —
comes from [7 · Results](?manual=resultados). The detail is in
[Technical · Fan and chimney](?manual=tec-chimenea#picard).
<!-- /profundidad -->

## Wind extractor {#extractor}

The chimney can carry a **wind extractor** on top (a "Chinese hat" turbine): the
wind spins it and generates an additional depression that helps the draft, at the
cost of a small flow obstruction. The climate wind (measured at 10 m) is
corrected to the real top height by a logarithmic profile. It is a **chimney
accessory**, not a type of motor: it adds its driving term to the draft balance.

## System pressure drops {#dp}

The section estimates and breaks down the total $\Delta P$: collector (channel),
chamber (trays/bed according to flow direction), ducts and fittings (bends,
inlets, outlets) and — in Large scale — the **main duct**. This breakdown is the
diagnostic tool: if one segment dominates, that is where the design opportunity
is (enlarge the channel, lower the velocity, spread the bed).

---

**See also:** [Technical · Motor, chimney and pressure
drops](?manual=tec-chimenea) (all the equations per segment),
[3 · Collector](?manual=colector#geometria) and
[4 · Chamber](?manual=camara#bandejas) (where the pressure drop originates),
[7 · Results](?manual=resultados) (the full loop).
