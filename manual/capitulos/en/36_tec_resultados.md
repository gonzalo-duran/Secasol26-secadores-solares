# Technical · Global balance and results

Technical reference of the final integration: how the Results section solves the
complete system in a coupled way, the three calculation modes, the energy balance,
the process psychrometric chart, the parametric runs and the export. The usage
guide is in [7 · Results](?manual=resultados).

## 1. Results as the source of truth {#fuente-de-verdad}

Sections 1–6 **configure** the system (each one writes to the central project
object). **The Results section is the one that solves everything in a coupled way**
and is the **source of truth**: the previews of the intermediate sections
("Calculate X" buttons) use heuristics or preliminary models; the final number,
with the full Picard loop, comes from Results.

**Conceptual flow:** configuration (sections 1–6) → central project → coupled
global balance → dashboard + report.

## 2. Consistency verification {#coherencia}

Before calculating, the project's **cross invariants** are verified: for example, a
Box does not admit an external collector or a motor and requires at least one
translucent face; an in-series auxiliary requires a collector; a motor requires a
chamber; annual analysis does not apply to a Box. Errors are shown and block the
inconsistent calculation.

The **representative pressure** of the site is also fixed (annual mean of the
climate if available; standard atmosphere by altitude if not; 101325 Pa fallback) —
a single value for collector, chamber and psychrometrics.

## 3. Three calculation modes {#modos}

According to the [analysis mode](?manual=tipologia#modo-analisis), the calculation
routes to one of three pipelines:

| Mode | Forcings |
|---|---|
| **Constants** | single representative conditions (T, irradiance, wind, RH) |
| **Transient** | hourly horizon (design day / multi-day) |
| **Window** | real span [start, end] with hourly climate (large scale / multi-day) |

The three chain **collector → auxiliary → chamber** and, if there is a chimney,
close the **natural loop by Picard**
([Technical · Motor and chimney](?manual=tec-chimenea#picard)). The air-forcing
assembly builds $T_{ent}$, $\omega_{ent}$, $\dot m$, the **equivalent irradiance**
on the translucent faces of the chamber (POA per face with product/air split —
[Technical · Chamber](?manual=tec-camara#techo-translucido)) and the **POA on the
collector plane** ([Solar radiation](?manual=radiacion)).

### Automatic irradiance suggestion (Constants mode) {#sugerencia}

So as not to force the user to invent a "representative" value, conditions are
suggested from the downloaded climate: the **90th percentile of the representative
POA** (Liu-Jordan transposition; in a Box, of the **equivalent irradiance** on the
translucent faces of the chamber) and the 75th percentile of the ambient
temperature. If there is no POA, it falls back to the q90 of GHI (conservative).

## 4. Integrated energy balance {#balance-energetico}

The result integrates the **complete energy balance**:

$$
E_{total}=E_{solar,util}+E_{auxiliar}+E_{motor},
\qquad
E_{secado}=m_{agua}\,L_v
$$
$$
\mathrm{COP}_{secado}=\frac{m_{agua}\,L_v}{E_{total}},
\qquad
\text{Solar fraction}=\frac{E_{solar}}{E_{solar}+E_{auxiliar}}
$$

plus **drying time**, **dry product mass** ($m_{tot}/(1+X_0)$), mass yield, the
outputs of each subsystem (collector, auxiliary, chamber, chimney) and the
accumulated warnings/errors. The dashboard shows metrics, a simplified energy
**Sankey** and, according to the mode:

- **Transient:** hourly trajectories (temperatures, product moisture, flows).
- **Window (large scale):** **production dashboard** — dry kg, steady-state rate
  (kg/day), firewood, and **spatial profile of the tunnel** in semi-continuous.
- **Annual:** monthly detail panel if the Chamber section computed the annual
  operation (with the four Augustus Leon efficiencies: drying, pickup, thermal and
  total).

## 5. Process psychrometric chart {#carta}

> **Temporarily disabled (version 1.4.1).** The process psychrometric chart has been removed from tab 7 and from the PDF report while its results are reviewed. It will return in a later version. The rest of the calculation is unchanged.

The **altitude-corrected psychrometric chart** traces the real air process (own
implementation, without an external library):

$$
\text{Ambient} \to \text{collector (sensible, } \omega \text{ const)}
\to \text{auxiliary (+T, } \omega \text{ const)}
\to \text{chamber (drying)} \to \text{outlet}
$$

The chamber segment is **adiabatic or non-adiabatic as it emerges from the balance**
(it is not imposed): if the chamber loses heat to the walls, the process departs
from the isenthalpic. The representative state is taken at **solar noon**. In the
**semi-continuous tunnel** the **air path by zones** counter-current is traced. How
to read the chart is explained in [Psychrometry](?manual=psicrometria#carta).

## 6. Parametric runs (sweeps) {#barridos}

Sweeps allow **comparing designs** by varying a parameter (geometry, flow,
materials…) and measuring KPIs (drying time, COP, solar fraction, outlet
temperature…):

- A project field is mutated by its path (e.g.
  `colector.unidad.velocidad_diseno_ms`) over a clone of the project (without
  re-downloading the climate).
- Each value dispatches the corresponding engine and extracts the KPIs, also
  reporting the points that did not converge.

It serves to answer "what if I double the collector area / change the flow / use a
double cover?" without redoing the configuration by hand.

## 7. Export {#exportacion}

The complete project is exported in three formats:

| Format | What | For what |
|---|---|---|
| **JSON** | serialized snapshot of the project + results | **reproducible**: it can be reloaded and re-run identically |
| **TXT** | plain-text report | quick read / paste into an email |
| **PDF** | report with institutional cover, figures and tables | **deliverable** for third parties |

The JSON serializes **each component** (collector, chamber, auxiliary,
motor/chimney) — so a design can be versioned, shared or reopened.

## 8. End-to-end workflow {#flujo}

1. **Typology** — dryer type and analysis mode.
2. **Site** — lat/lon → NASA POWER download → POA vs GHI.
3. **Collector** — type, materials, geometry, array → graphical evaluation.
4. **Chamber** — geometry, wall, product, load, trays.
5. **Auxiliary** (optional).
6. **Motor** or chimney → system ΔP.
7. **Results** — full coupled run → dashboard + psychrometric chart + export
   JSON/TXT/PDF.

The flow is **guided but flexible**: each section writes to the central project;
you can go back and forth, and Results integrates everything with the iterative
loop.

---

**See also:** [7 · Results](?manual=resultados) (usage guide),
[Technical · Motor and chimney](?manual=tec-chimenea#picard) (the Picard loop),
[Psychrometry](?manual=psicrometria) (the chart),
[Appendix · Implementation](?manual=apendice-codigo#resultados),
[Bibliography](?manual=bibliografia#leon).
