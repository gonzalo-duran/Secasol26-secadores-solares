# 7 · Pre-design results

Sections 1 to 6 **configure**; Results **solves**. Here Secasol runs the complete
system in a **coupled** way — collector → auxiliary → chamber, with the chimney
loop closed by iteration if applicable — and delivers the dashboard, the
psychrometric chart and the export files. It is the pre-design's **source of
truth**: the "Calculate" buttons of the intermediate sections are previews; the
final number comes from here.

## Before calculating: consistency and conditions {#checklist}

The section first verifies that the project is **consistent** (for example: a Box
does not admit a collector or a fan; the in-series auxiliary requires a
collector) and shows the checklist of what is configured. Errors block the
calculation; warnings do not, but it is worth reading them.

In **Constants** mode, Secasol **suggests** the representative conditions from the
downloaded climate — irradiance as the 90th percentile of the POA and temperature
as the 75th percentile — so you do not have to invent a number.

## The three run modes {#modos}

According to the [analysis mode](?manual=tipologia#modo-analisis):

- **Constants** — a snapshot at representative conditions: fast, ideal for
  iterating the design.
- **Transient** — the design day (or multi-day) hour by hour: trajectories of
  temperatures, product moisture and flows.
- **Window** — the real campaign: **production** dashboard (dry kg, steady-state
  rate, firewood) and, in a semi-continuous tunnel, the **spatial profile by
  zones**.

## The dashboard {#dashboard}

The central metrics:

- **Drying time** — how long the product takes to reach the target moisture (or
  how much it fell short).
- **Drying COP** — evaporation energy obtained per unit of energy invested:
  $\mathrm{COP}=m_{agua}L_v/E_{total}$.
- **Solar fraction** — what share of the heat came from the sun:
  $E_{solar}/(E_{solar}+E_{auxiliar})$.
- **Dry product mass** and mass yield.

plus the energy-balance **Sankey** diagram and the outputs of each subsystem
(collector outlet temperature, air state in the chamber, natural chimney flow,
auxiliary consumption). The accumulated **warnings** from all subsystems are
listed together: they are part of the result.

## The process psychrometric chart {#carta}

The chart traces the **real path of the air** on the altitude-corrected
psychrometric diagram: ambient → collector (sensible heating) → auxiliary (if
any) → chamber (drying) → outlet. It is the thermodynamic X-ray of the design: at
a glance you see how much the collector heats, how much moisture the chamber
picks up and what margin is left. How to read it, step by step, is in
[Psychrometry](?manual=psicrometria#carta).

<!-- profundidad: The adiabaticity of the chamber segment -->
In textbooks, ideal drying is **adiabatic**: the air cools exactly as much as it
humidifies, following the isenthalpic. In Secasol the chamber segment **is not
imposed as adiabatic**: it comes from the balance. If the chamber loses heat
through the walls, the outlet point falls below the isenthalpic — and that
deviation is design information (insulate better). In the semi-continuous tunnel
the chart shows the air path **zone by zone** counter-current.
<!-- /profundidad -->

## Parametric runs (sweeps) {#barridos}

Sweeps answer "what if…?" without redoing the configuration: you choose a
parameter (air velocity, collector area, number of covers, roof pitch or chamber
azimuth…), a range of values, and Secasol runs the complete pre-design for each
point, plotting the KPIs (drying time, COP, solar fraction, outlet temperature).
It is the tool for **comparing designs** and finding diminishing returns before
committing dimensions.

## Export {#exportar}

Three formats:

- **JSON** — complete and **reproducible** snapshot of the project: it can be
  reloaded into Secasol and re-run identically, versioned or shared with a
  colleague.
- **TXT** — plain-text report for a quick read.
- **PDF** — institutional report with a cover, figures and tables: the
  deliverable.

---

**See also:** [Technical · Global balance](?manual=tec-resultados) (how the
calculation is orchestrated), [Psychrometry](?manual=psicrometria) (the chart),
[Technical · Motor and chimney](?manual=tec-chimenea#picard) (the Picard loop),
[Introduction](?manual=introduccion) (the full workflow).
