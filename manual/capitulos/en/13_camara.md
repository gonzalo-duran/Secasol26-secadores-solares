# 4 · Drying chamber

The chamber is where drying happens: the hot air from the collector (or the
auxiliary) passes over the product trays, delivers heat and carries away the
moisture. This section defines the chamber **geometry**, its **construction**
(walls, roof), the **trays**, the **product** and its **load**. The physical
engine that solves it is a coupled heat-and-mass balance: the air cools and
humidifies as it dries, and the drying rate "emerges" from the physics — not from
an empirical curve.

<!-- esquema: camara_dimensiones | Chamber geometry with its dimensions. -->

## Geometry {#geometria}

Length, width and height define the volume and — together with the roof — the
**envelope** through which the chamber loses heat to the environment. The length
in the flow direction is also the characteristic length of the air→product
transfer.

## Orientation and mono-pitch roof {#orientacion}

The chamber has its **own orientation**, independent of the collector array: the
**roof pitch** (mono-pitch roof), the **chamber azimuth** (where it "looks", with
0° = North in the UI input) and the roof **downslope face**. The geometry height
is the **mean height** of the box: tilting the roof changes neither the volume
nor the air passage cross-section.

This matters because each translucent face captures radiation according to its
own tilt and orientation (transposition to the plane of each face — see
[Solar radiation and oriented plane](?manual=radiacion)). In the **Box** typology
the chamber **is** the collector: that is why in
[2 · Site](?manual=emplazamiento) the collector orientation does not appear and
the collecting plane is defined here.

## Walls {#pared}

The wall can be **simple** (one material with its thickness) or **composite**
(layers in series: sheet + insulation + sheet, wood + polystyrene, etc.). The
model adds the resistances of the layers and computes the loss
$Q_{pared}=U\,A\,(T_{flujo}-T_{amb})$, where $U$ combines the interior
convection, the conduction of the layers and the exterior wind.

In practice: the insulation rules. Doubling the insulation thickness nearly
halves the losses; changing the outer sheet barely changes anything.

## Translucent surfaces {#techo}

Optionally the roof **and even the four walls** (front, back, sides) can be
translucent (multiwall polycarbonate; same material and thickness for all faces):
they provide **direct solar gain** — this is what turns a Box into a dryer — but
they also **lose more heat** than an insulated opaque face. The model captures
both effects, with the multiwall thickness as a parameter.

The radiation each face transmits is **split**: a fraction falls directly on the
product and the rest is absorbed by the opaque inner surfaces and heats the air —
the **greenhouse effect** of a glazed box. The section shows a preview of the
area, tilt and orientation of each active face. The equations of the split are in
[Technical · Chamber](?manual=tec-camara#techo-translucido).

## Trays and flow direction {#bandejas}

The number of trays and their dimensions fix the air–product **contact area**.
The **flow direction** is an important design decision:

- **Horizontal** (the air passes *over* the trays): hydraulically gentle,
  moderate transfer.
- **Upward vertical** (the air *crosses* the bed): maximum contact and more even
  drying, but the bed pressure drop grows a lot — paid by the fan or the chimney
  draft ([6 · Fan](?manual=motor)).

<!-- profundidad: The bed pressure drop (Ergun) -->
In vertical flow, the pressure drop of the packed bed is computed with the
**Ergun** equation, which adds a viscous term (dominant at low velocity) and an
inertial one:

$$
\frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
$$

with $\varepsilon$ the bed porosity, $d_p$ the particle diameter and $\Phi_s$ the
sphericity. These parameters come from the product catalog or from conservative
defaults. A bed of thin, compact slices can multiply the $\Delta P$ compared to a
bed of coarse chunks.
<!-- /profundidad -->

## Product and load {#producto}

The product is chosen from the **catalog** (with its sorption properties and
thermal constants already loaded — see
[The product catalog](?manual=catalogo-productos) for what each one brings and
its calibration status) and the **load** is defined: fresh mass, initial moisture
$X_0$ and target moisture $X_{obj}$, both on a **dry basis** (kg of water per kg
of dry matter — the difference from the wet basis is explained in
[Drying physics](?manual=secado#base-seca)).

The heart of the product model is the **GAB sorption isotherm**: as the product
dries, its water activity drops and the drying slows by itself — this is how the
falling-rate periods appear without any fitted empirical curve
([Drying physics](?manual=secado#isotermas)).

## Operating conditions and forcings {#modos-forzantes}

The section lets you choose where the conditions of the air entering the chamber
come from:

- **Constants**: operating temperature and humidity set by hand (the T/RH
  controls in this section). Useful for quick exploration.
- **Synthetic / Real day / Annual**: the forcings come from the **climate and the
  collector** hour by hour. **In these modes the operating T/RH controls have no
  effect** — the real boundary condition is the collector outlet (plus the
  auxiliary if it exists).

The **simulation horizon** (transient mode) defines how many hours the balance is
integrated over.

## Annual operation {#operacion-anual}

With [Annual analysis mode](?manual=tipologia#modo-analisis), the **annual
operation** section appears: you define how many **batches per month** are
processed and Secasol runs the typical day of each month, estimating annual
production and the four **drying efficiencies** (drying, pickup, thermal, total)
per month. The monthly detail is then shown in [7 · Results](?manual=resultados).

## Semi-continuous tunnel (Large scale) {#tunel}

With the **Semi-continuous** subtype, here the **tunnel topology** is configured:
number of zones and advance cadence of the cart columns. The outlet dryness is
**not imposed**: it is a result — if the product comes out wetter than the
target, you have to lengthen the tunnel, lower the cadence or raise the
temperature ([Technical · Industrial mode](?manual=tec-industrial#semicontinuo)).

---

**See also:** [Technical · Chamber](?manual=tec-camara) (the coupled balance
equations), [Drying physics](?manual=secado) and
[Psychrometry](?manual=psicrometria) (fundamentals),
[5 · Auxiliary](?manual=auxiliar) (if the sun is not enough).
