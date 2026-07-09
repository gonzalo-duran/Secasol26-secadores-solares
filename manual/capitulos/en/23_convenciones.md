# Unit and angle conventions

Secasol is strict with units and angular conventions: they are the classic source
of errors in engineering tools. This chapter documents the rules so you can
interpret any number in the program (and in this manual) without ambiguity.

## Units: strict SI inside {#si}

Internally **everything circulates in strict SI**; the interface converts to
convenient units only when displaying and when reading your inputs:

| Quantity | Internal (SI) | In the interface |
|---|---|---|
| Temperature | K | °C |
| Pressure | Pa | kPa / Pa by context |
| Relative humidity | fraction 0–1 | % |
| Absolute air humidity | $\omega$ [kg water / kg dry air] | g/kg on the chart |
| Product moisture | $X$ [kg water / kg dry] (**dry basis**) | dry basis (and wet basis as reference) |
| Time | s | hours / days |
| Mass flow | kg/s | kg/s or m³/h |
| Irradiance | W/m² | W/m² |

Two conventions worth keeping in mind when reading results:

- The **product moisture is dry basis** ($X$): it can exceed 1 (a fresh product
  with 90 % water on wet basis has $X=9$). The conversion is in
  [Drying physics](?manual=secado#base-seca).
- The **internal relative humidity is a fraction** (0.60, not 60 %) — in the
  equations of this manual, RH and $a_w$ always go as a fraction.

## Angles: three azimuth conventions {#acimut}

The azimuth (where the collector "looks") has three conventions in play, and they
**do not mix**:

| Convention | 0° | +90° | Range | Where it is used |
|---|---|---|---|---|
| **UI360** | North | East | [0, 360) | what **you** enter in [2 · Site](?manual=emplazamiento) |
| **Duffie & Beckman** | South | West | [−180, +180] | internal storage and solar-geometry equations |
| **pvlib** | North | East | [0, 360) | the irradiance calculation inside the pvlib library |

In the interface you always see **UI360** (0° = North, clockwise, like a compass).
The equations of the technical chapters (for example the
[angle of incidence](?manual=radiacion#incidencia)) use the **Duffie & Beckman**
convention, the standard of the solar literature.

<!-- profundidad: The conversion formulas -->
Exact conversions (γ = Duffie, α = UI360, ψ = pvlib):

$$
\alpha = (-\gamma) \bmod 360
\qquad\qquad
\gamma = (-\alpha) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

$$
\psi = (180 + \gamma) \bmod 360
\qquad\qquad
\gamma = (\psi - 180) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

Verification cases: South → γ=0, α=180, ψ=180. North → γ=±180, α=0, ψ=0. East →
γ=−90, α=90, ψ=90. West → γ=90, α=270, ψ=270. In the code, these formulas live in
a single conversions module and are never duplicated.
<!-- /profundidad -->

The **tilt** β is unique across all conventions: 0° = horizontal, 90° = vertical.

## Signs and various references {#signos}

- **Latitude**: negative in the southern hemisphere (Salta ≈ −24.8°).
- **Longitude**: negative west of Greenwich (Argentina ≈ −54° to −73°).
- **Evaporation rate** $\dot m_w$: positive = the product loses water; negative =
  condensation on the product.
- **Main-duct ΔT**: negative = the air reaches the chamber colder (loss),
  positive = solar gain of the duct.
- **Cavity angle** in the Hollands correlation: measured from the horizontal,
  valid up to 75°.

---

**See also:** [Solar radiation and oriented plane](?manual=radiacion) (where these
conventions are used), [Glossary](?manual=glosario) (symbols and terms).
