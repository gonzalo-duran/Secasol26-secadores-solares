# Solar radiation and the oriented plane

The collector does not "see" the radiation that meteorological databases report:
those series are measured on a **horizontal plane**, and the collector is
**tilted and oriented**. This chapter explains the components of solar radiation,
how the Sun's position is described, and how Secasol **transposes** the horizontal
resource to the collector plane (the so-called **POA**, *plane of array*). It is
the basis of the [2 · Site](?manual=emplazamiento) section and of all the
downstream calculations: **the collector always receives POA, not GHI**.

## The three radiation components {#componentes}

The solar radiation reaching a surface breaks down into three parts, and the
databases (NASA POWER in Secasol's case) report them separately:

| Acronym | Name | What it is |
|---|---|---|
| **GHI** | Global horizontal | Total received by a horizontal surface (sum of projected direct + diffuse). |
| **DNI** | Direct normal | The one coming from the solar disk, measured on a plane perpendicular to the ray. |
| **DHI** | Diffuse horizontal | The one arriving from the rest of the sky dome (scattered by atmosphere and clouds). |

At a clear noon the direct component dominates; on a cloudy day almost all the
resource is diffuse. The distinction matters because each component responds
**differently** to the collector tilt: the direct depends on the angle at which
the ray strikes, the diffuse on how much sky dome the plane "sees", and a third,
new contribution appears — the **ground-reflected** one — which on a horizontal
plane is null.

## The Sun's position {#posicion-solar}

To project the direct component you need to know where the Sun is at each moment.
The position is described with two angles: the **zenith** $\theta_z$ (angular
distance between the Sun and the vertical) and the **solar azimuth** $\gamma_s$
(the Sun's orientation over the horizon).

Secasol does not reimplement the astronomy: it delegates to the **SPA** (*Solar
Position Algorithm*) via `pvlib`, with sub-degree precision, atmospheric
refraction and the equation of time included. With that it also computes the
**true solar noon** (transit) of each day, which is the time the "representative
day" views use.

<!-- profundidad: The astronomical equations that SPA solves -->
Although SPA uses a high-precision algorithm, the quantities it solves are the
classical ones of solar geometry (Duffie & Beckman):

**Solar declination** $\delta$ — the angle between the equatorial plane and the
Earth-Sun line; it varies with the day of the year $n$:

$$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$

**Hour angle** $\omega$ — the Sun's position relative to true solar noon (15° per
hour), with equation of time and longitude correction.

**Solar zenith** — combining latitude $\phi$, declination and hour angle:

$$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$

The complement of $\theta_z$ is the **solar elevation**. When $\theta_z > 90°$
the Sun is below the horizon and there is no direct component.
<!-- /profundidad -->

## The angle of incidence {#incidencia}

A plane tilted by an angle $\beta$ and oriented with azimuth $\gamma$ has its own
normal. The **angle of incidence** $\theta_i$ is the one the direct ray forms
with that normal, and it governs how much direct radiation the plane captures:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

When the Sun is "facing" the collector, $\cos\theta_i \to 1$ and the direct
capture is maximum; when the ray arrives grazing, $\cos\theta_i \to 0$. Note that
the formula uses the azimuth in the **Duffie & Beckman convention** (0° = South):
see [Unit and angle conventions](?manual=convenciones).

## From the horizontal plane to the collector plane {#transposicion}

With the solar position and the plane geometry, the total irradiance on the
collector plane is built by adding three contributions. Secasol uses the
**Liu-Jordan** model (isotropic diffuse):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{direct}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{sky diffuse}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{ground reflected}}\,}
$$

where:

- $I_b = \mathrm{DNI}$, projected by $\cos\theta_i$: it is the component sensitive
  to the orientation.
- $I_d = \mathrm{DHI}$, scaled by the **sky view factor** $(1+\cos\beta)/2$: a
  horizontal plane ($\beta=0$) sees the whole dome (factor 1); a vertical plane
  sees half (factor 0.5).
- $I = \mathrm{GHI}$, reflected by the ground with **albedo** $\rho_g$ and ground
  view factor $(1-\cos\beta)/2$: null in horizontal, growing as it tilts.

The albedo is configurable in the Site section (default 0.25, with a catalog of
typical values by surface type: grass, soil, snow, etc.).

<!-- profundidad: Assumptions of the isotropic model and fallback -->
The Liu-Jordan model assumes:

- **Isotropic diffuse sky**: the diffuse radiation arrives uniformly from the
  whole dome. It slightly underestimates the circumsolar component (the bright
  halo around the solar disk), which makes it **conservative** for pre-design.
- **Lambertian ground** of uniform albedo (it reflects diffusely in all
  directions).
- **Each hour is quasi-instantaneous**: the solar position of the hourly bin is
  evaluated (NASA POWER's resolution is hourly).

`pvlib` also implements anisotropic models (Hay-Davies, Reindl, Klucher, Perez);
Secasol uses the isotropic one for simplicity and consistency across all its
pipelines, and leaves the `modelo_difuso` parameter open to substitute it.

**Conservative fallback:** if in one hour DNI or DHI is missing, direct cannot be
separated from diffuse; that hour is assumed $I_{POA} = \mathrm{GHI}$
(underestimating with $\beta>0$, but avoiding propagating `NaN` to the collector
solver). Negative values from numerical artifacts near the horizon are clipped to
0.
<!-- /profundidad -->

## What this means for your design {#criterios}

Two practical rules follow directly from the physics above:

- **Tilt** $\beta$: tilting the collector brings its normal closer to the Sun of
  the useful hours. As a rough rule for annual use, $\beta \approx$ latitude; to
  favor winter (low sun), $\beta >$ latitude; for summer, $\beta <$ latitude. The
  [3 · Collector](?manual=colector) section lets you graphically evaluate the
  resulting POA day by day and over the year.
- **Orientation** $\gamma$: in the southern hemisphere the collector "looks"
  North (and South in the northern hemisphere). Deviations of ±15° cost little;
  larger turns shift the capture peak toward the morning or the afternoon.

The gain from transposing is not minor: at mid-latitude sites, a well-tilted
plane can capture in winter considerably more energy than the horizontal plane —
and that winter is usually precisely when the drying needs more help.

---

**See also:** [2 · Site and climate](?manual=emplazamiento) (where all of this is
configured), [Technical · Solar resource and climate](?manual=tec-emplazamiento)
(NASA POWER download, gap policy and implementation details),
[Unit and angle conventions](?manual=convenciones) (the three azimuth
conventions).
