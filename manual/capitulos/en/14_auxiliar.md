# 5 · Auxiliary heating

The auxiliary is the dryer's **thermal backup**: an electric resistance or a
biomass burner that adds heat when the sun is not enough — cloudy days, early
start, dusk, or campaigns where losing a batch costs more than the firewood. It
is **optional**: a purely solar dryer simply does not include it.

## When it is worthwhile {#cuando}

Two typical signs that the design needs an auxiliary:

- The [transient or annual mode](?manual=resultados) shows that the product does
  not reach the target moisture within the safe window (risk of overnight
  spoilage or a lost batch).
- The **solar fraction** of the balance stays high but the drying time is
  unacceptable in the critical months.

The goal of the pre-design is to size it **to the minimum**: the Results
dashboard reports the auxiliary energy and the solar fraction to judge it.

## Type and location {#tipo}

- **Type**: **electric** resistance (efficiency ≈ 1, consumption in kWh) or
  **biomass** burner (consumption in kg of firewood via calorific value and
  burner efficiency).
- **Location**: **in series after the collector** (it takes the preheated air
  from the collector and finishes heating it — the usual case) or as an
  **independent backup** (it takes ambient air and heats on its own).

The auxiliary **does not add moisture**: it is pure sensible heating. On the
[psychrometric chart](?manual=psicrometria#carta) its segment is horizontal (T
rises, ω constant) — just like the collector.

## Power and set-point {#setpoint}

The **rated power** is defined and, optionally, a temperature **set-point**: with
a set-point, the auxiliary delivers **only the power needed** to reach it (ideal
modulating control). If the air already arrives hotter than the set-point, the
auxiliary spends nothing; if the power is not enough to get there, it delivers
the maximum and warns.

<!-- profundidad: The auxiliary balance -->
The auxiliary is modeled in steady state, without inertia:

$$
Q_{eff} = \dot m\,c_{p}\,(T_{salida}-T_{entrada})
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p}}
$$

With set-point $T_{sp}$: $Q_{set}=\dot m c_p (T_{sp}-T_{ent})$, clipped between 0
and $Q_{max}$. The firewood consumed comes from
$m_{leña}=E_{aux}/(PCI\cdot\eta_{quemador})$, with the energy integrated over the
horizon. Equations and limiting cases in
[Technical · Auxiliary](?manual=tec-auxiliar#balance).
<!-- /profundidad -->

## Availability and start-up schedule {#calendario}

- **Overnight availability**: the auxiliary can be turned off at night (when the
  irradiance is practically zero), typical if the operation has no night shift.
- **Start-up schedule** (industrial hybrid): the burner operates in **hourly
  windows** in the morning and at dusk — the real operation of an ADITAL-style
  hybrid dryer: light it early to start the batch and at dusk so as not to lose
  it. Each window is defined by a start time and duration, and the firewood
  consumption is accumulated per window.

---

**See also:** [Technical · Auxiliary](?manual=tec-auxiliar) (equations and
control), [4 · Chamber](?manual=camara) (where the air goes),
[7 · Results](?manual=resultados) (solar fraction and consumption in the
balance).
