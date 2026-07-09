# Psychrometry — moist air and its chart

Drying is, at bottom, a problem of **moist air**: the air enters with a certain
capacity to carry away water, uses it on the product, and leaves colder and more
humid. Psychrometry is the language to describe that process, and the
**psychrometric chart** is its map. This chapter defines the quantities (absolute
humidity, relative humidity, saturation, enthalpy) and teaches how to read the
chart that Secasol draws in [7 · Results](?manual=resultados#carta).

## Absolute humidity and relative humidity {#humedades}

Two different — and complementary — ways of saying "how much water is in the air":

- **Absolute humidity** $\omega$ [kg of water / kg of dry air]: the mass of vapor
  per unit mass of dry air. It is the **conservation** variable: if no water is
  added or removed, $\omega$ does not change even if the temperature changes.
- **Relative humidity** RH [0–1]: how close the vapor is to **saturation** at
  that temperature: $RH = p_v/p_{sat}(T)$. It is the **capacity** variable: at
  low RH the air "is thirsty"; at RH = 1 it admits no more water.

The key to solar drying is the relationship between the two: **heating the air
does not change its $\omega$, but lowers its RH** — because $p_{sat}(T)$ grows
exponentially with temperature. Ambient air at 20 °C and 60 % RH, heated to
50 °C, drops to ~11 % RH: it went from warm and humid to thirsty, without
removing a single drop of water. That is what the collector does.

<!-- profundidad: The psychrometric relations Secasol uses -->
With total pressure $P$ and vapor partial pressure $p_v$:

$$
\omega = 0.622\,\frac{p_v}{P - p_v},
\qquad
\omega_{sat}(T) = 0.622\,\frac{p_{sat}(T)}{P - p_{sat}(T)}
$$

The saturation pressure $p_{sat}(T)$ is evaluated with the standard ASHRAE
correlation. Note the dependence on $P$: at higher **altitude** (lower pressure),
the same $p_v$ gives more $\omega$ — that is why Secasol corrects all the
psychrometry by the site pressure. The **enthalpy of moist air** (per kg of dry
air) is

$$
h = c_{p,as}\,T + \omega\,(L_v + c_{p,v}\,T)
$$

and the specific heat of moist air $c_{p,h}=1006+1805\,\omega$ J/(kg·K). These
same functions are used by the chamber engine
([Technical · Chamber](?manual=tec-camara#cstr)).
<!-- /profundidad -->

## What happens in each dryer component {#proceso}

On the variables $(T, \omega)$:

| Segment | T | ω | RH | Process |
|---|---|---|---|---|
| Collector | ↑ | = | ↓↓ | sensible heating |
| Auxiliary | ↑ | = | ↓ | sensible heating |
| Chamber | ↓ | ↑ | ↑ | drying (≈ adiabatic) |

In the chamber the air gives up sensible heat to evaporate water and takes it in
as vapor: that is why it **cools and humidifies at the same time**. If the chamber
were perfectly adiabatic, the air enthalpy would be conserved (the sensible heat
it loses ≈ the latent it gains).

## The psychrometric chart {#carta}

The chart is the plane **dry-bulb temperature (X axis) vs absolute humidity
$\omega$ (Y axis)**, with two families of background curves:

- The **saturation curve** (RH = 100 %): the upper boundary; beyond it water
  condenses.
- The **constant-RH** curves (10 % to 90 %): a fan between the X axis and
  saturation.

On that background, Secasol traces the **process polyline** with the computed
states: **ambient → collector outlet → chamber inlet (after the auxiliary) →
chamber outlet**, plus a dashed **reference isenthalpic** from the chamber inlet.

How to read it:

- The collector and auxiliary segments are **horizontal to the right** ($\omega$
  constant, T rises). Their length is the thermal work achieved.
- The chamber segment rises **to the left**: the air cools and gains water. Its
  vertical projection ($\Delta\omega$) multiplied by the dry air flow is the
  **evaporated water rate**.
- If the chamber outlet falls **on** the dashed isenthalpic, the drying was
  ≈ adiabatic (well-insulated indirect chamber). If it stays **above**, there was
  extra heat input in the chamber (translucent surfaces); **below**, wall losses.
  This **is not imposed**: it emerges from the balance.
- The distance from the outlet point to the **saturation curve** is the margin
  left unused: an outlet far from saturation with the product still wet suggests a
  high flow or a short chamber; an outlet stuck to saturation indicates exhausted
  air (well used, but watch for condensation).

The chart is drawn **at the site pressure**: at altitude, the curves shift and the
same (T, RH) give a different $\omega$.

## Wet-bulb and dew-point temperature {#bulbo-humedo}

Two auxiliary temperatures useful when interpreting results:

- **Wet-bulb** $T_{bh}$: the equilibrium temperature of a ventilated wet surface
  — the lower limit to which the air can be cooled by evaporation (and a bound on
  the product temperature during the intense drying period).
- **Dew point** $T_r$: the temperature at which the air, cooling at constant
  $\omega$, saturates. If any surface of the dryer is below $T_r$, there will be
  condensation.

---

**See also:** [7 · Results](?manual=resultados#carta) (where the chart is drawn),
[Drying physics](?manual=secado) (the product side),
[Technical · Chamber](?manual=tec-camara) (the balance that produces the
states).
