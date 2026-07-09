# 3 · Solar air collector

The collector is the thermal heart of the dryer: it turns solar radiation into
hot air. This section defines **which collector** is used (type, materials,
geometry) and **how many** (series/parallel array). Secasol models flat-plate
air collectors with a physical surface-by-surface balance model — not a tabulated
efficiency — so every construction decision (one or two covers, plate type,
insulation thickness) has a direct, visible effect on the outlet temperature.

In the **Box** typology this section does not apply (the box captures directly
through its cover); it appears with **Cabinet** and **Large scale**.

## Choosing the collector type {#tipos}

Secasol offers four topologies that share materials and construction criteria and
differ in **where the absorber is and where the air flows**:

| Type | Absorber | Air circulation |
|---|---|---|
| **1** | at the bottom of the box | **above** the absorber (single channel) |
| **2** | at mid-height (two channels) | through **both** channels (upper + lower) |
| **3** | at mid-height | through the **lower** channel; the upper stays sealed |
| **4** | at mid-height | through the **upper** channel; the lower stays sealed |

<!-- esquema: colectores_seccion_transversal | Comparative cross-section of the 4 types. -->

As a quick guide: **Type 1** is the simplest to build; the types with the
absorber at mid-height increase the exchange area with the air, and the variants
with a sealed channel (3 and 4) use that still-air cavity as extra insulation.

<!-- profundidad: What changes physically between the types -->
In the model, each type is a different topology of energy balances:

- In **Type 1** the air exchanges with the inner face of the cover and with the
  absorber; cover and absorber are also coupled by radiation.
- In **Type 2** the absorber delivers heat by convection to **two** flows (upper
  and lower channel), and by radiation to the cover and the bottom.
- In **Types 3 and 4** the sealed channel behaves as a **natural convection
  cavity**: the transfer through it is modeled with the Hollands correlation for
  inclined cavities plus the radiation between surfaces. That reduces the losses
  on the sealed side, at the cost of losing that face as an exchange surface with
  the flow.

The full equations of the four balances are in
[Technical · Flat-plate collector](?manual=tec-colector#balances).
<!-- /profundidad -->

## Collector materials {#materiales}

Each component is chosen from a **materials catalog** with properties already
loaded (transmittance, absorptance, emissivity, conductivity, roughness):

- **Cover** — the top glazing: multiwall polycarbonate, greenhouse film, glass.
  Its **transmittance** $\tau$ matters (how much radiation it lets through) and
  its infrared emissivity (how much it re-radiates).
- **Absorber plate** — the surface that captures: painted sheet, corrugated
  sheet, etc. Its **absorptance** $\alpha$ matters and its roughness (it affects
  the pressure drop).
- **Insulation** — glass wool, polystyrene, sheep wool…: its conductivity and
  thickness define the loss through the bottom.
- **Bottom** — the lower closure of the box (sheet metal, wood).

The number of **covers** can be 1 (standard) or 2: the double cover reduces the
upward losses at the cost of losing some transmittance, and is worthwhile in cold
or windy climates.

<!-- profundidad: How the double cover is modeled -->
With two covers, the upward conductance is no longer the simple conduction of a
sheet and becomes an **effective conductance** in series: conduction in each
sheet + **Hollands natural convection** in the air cavity between covers + **gray
radiation** between parallel surfaces. The spacing between covers is configurable
and enters the Rayleigh number of the cavity: if the cavity is very thin,
conduction dominates; if it is very thick, natural convection "short-circuits"
part of the benefit.
<!-- /profundidad -->

## Geometry and design condition {#geometria}

The module geometry is defined with **length** (flow direction), **width** and
**channel spacing** (the height through which the air flows). Together with the
air **design velocity**, this fixes the mass flow rate and the flow regime
(laminar, transition or turbulent), on which the internal convection coefficient
strongly depends.

Two practical remarks:

- A lower channel increases velocity (better transfer) but also the **pressure
  drop**, which is later paid by the fan or the chimney draft (see
  [6 · Fan and chimney](?manual=motor)).
- The **absorber plate thickness** can be configured but **does not enter the
  thermal balance**: the model assumes negligible plate thermal capacitance
  (quasi-steady hypothesis). It is a conscious model decision, not an oversight.

<!-- profundidad: Flow regime and local convective coefficient -->
The internal convection coefficient **is not a single scalar**: it is evaluated
locally node by node along the collector, with air properties varying with
temperature ($k, \mu, Pr, c_p, \rho$ evaluated at the local film temperature). At
each node the local Reynolds is computed

$$Re = \frac{G\,D_h}{\mu(T_{film})}, \qquad D_h = \frac{2\,W\,a}{W+a}$$

with $G$ the mass flux per unit area and $D_h$ the hydraulic diameter of the
rectangular channel, and the appropriate Nusselt correlation is selected
automatically (Shah-London, Heaton, Gnielinski, Sparrow-Liu, Dittus-Boelter,
Cengel-Ghajar) with smooth transitions between regimes. At low velocity or high
tilt the **buoyancy** component is added (Churchill mixed convection). The full
detail, with the correlation table and its ranges, is in
[Technical · Flat-plate collector](?manual=tec-colector#nusselt).
<!-- /profundidad -->

## Collector array {#banco}

A single module rarely suffices: the **array** replicates the module **in
series** (the air leaves one and enters the next, adding heating length) and **in
parallel** (several branches sharing the total flow).

- **Series** raises the outlet temperature, with diminishing returns: each module
  works with hotter air and loses more. It also multiplies the pressure drop.
- **Parallel** multiplies the flow at the same outlet temperature.

In **Large scale** the **main duct** also appears: the manifold that collects the
air from the branches and takes it to the chamber, with its own pressure drop and
thermal balance (it can lose heat to the environment or gain by radiation on its
upper face). See [Technical · Industrial mode](?manual=tec-industrial#cano-maestro).

## Evaluating the collector {#evaluar}

The **Calculate collector** button runs the model with the chosen condition and
shows outlet temperature, useful power and efficiency. The **daily** and
**annual** evaluation charts use the climate downloaded in
[2 · Site](?manual=emplazamiento) and always work on the irradiance **in the
collector plane** (POA), not on the global horizontal — the difference is
explained by [Solar radiation and oriented plane](?manual=radiacion).

When reading the results it is worth looking at, besides the outlet temperature:

- the collector **efficiency** (it drops when the thermal rise over the ambient
  grows — it is the Hottel-Whillier-Bliss signature);
- the design **warnings** (geometries out of range, a correlation forced outside
  its validity, etc.), which are shown before calculating;
- the **pressure drop**, which constrains the
  [6 · Fan and chimney](?manual=motor) section.

---

**See also:** [Technical · Flat-plate collector](?manual=tec-colector)
(surface-by-surface balances, correlations, numerical solution),
[Solar radiation and oriented plane](?manual=radiacion) (why POA),
[4 · Drying chamber](?manual=camara) (where the hot air goes).
