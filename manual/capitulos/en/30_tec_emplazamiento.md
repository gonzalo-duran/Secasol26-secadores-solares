# Technical · Solar resource and site climate

Technical reference of the climate subsystem: NASA POWER data download,
conversion to SI, data-quality policy, and the transposition of the global
horizontal resource (GHI) to the collector plane (POA). The introductory version
of these concepts is in [Solar radiation and oriented plane](?manual=radiacion)
and the usage guide in [2 · Site and climate](?manual=emplazamiento).

## 1. What the climate subsystem delivers {#series}

From three user data — **latitude, longitude, altitude** — plus the **collector
orientation** (tilt β and azimuth γ), Secasol produces an **annual hourly climate
series** ready to feed all the downstream physical engines:

- Hourly series in **strict SI**: ambient temperature [K], GHI/DNI/DHI [W/m²],
  wind [m/s], relative humidity [fraction 0–1], pressure [Pa].
- The **irradiance on the tilted and oriented plane (POA)**, which is what the
  collector actually "sees", computed by transposition of GHI/DNI/DHI.

The philosophy: the user only enters lat/lon; the same source and standard library
of the photovoltaic industry (NASA POWER + `pvlib`) do the rest.

## 2. Data download — NASA POWER via pvlib {#nasa-power}

The data come from the **NASA POWER** service (*Prediction Of Worldwide Energy
Resources*), a satellite reanalysis with global coverage on a ~0.5° grid. The
download uses `pvlib.iotools.get_nasa_power`, which builds the API URL, translates
the variable names and returns a tz-aware hourly DataFrame plus metadata
(including the **grid-point altitude**).

Requested variables:

| Variable | NASA code | Unit | Description |
|---|---|---|---|
| ghi | ALLSKY_SFC_SW_DWN | W/m² | global horizontal |
| dni | ALLSKY_SFC_SW_DNI | W/m² | direct normal |
| dhi | ALLSKY_SFC_SW_DIFF | W/m² | diffuse horizontal |
| temp_air | T2M | °C | air temperature at 2 m |
| wind_speed_2m | WS2M | m/s | wind at 2 m |
| RH2M | RH2M | % | relative humidity at 2 m |
| PS | PS | kPa | surface pressure |

The requested period is the **full calendar year** (8760 hours).

### Conversion to SI

$$
T:\ °C \to K\ (+273.15) \qquad
P:\ \mathrm{kPa} \to \mathrm{Pa}\ (\times 1000) \qquad
RH:\ \% \to \mathrm{fraction}\ (\div 100)
$$

GHI/DNI/DHI [W/m²] and wind [m/s] require no conversion. The only physical unit
conversion of the resource happens in this layer; from there on everything
circulates in strict SI (see [Conventions](?manual=convenciones)).

### Transparent cache {#cache}

To avoid hitting the API on every run, the result is saved in **parquet** with a
**SHA-256 key of (lat, lon, year)** (rounded to 4 decimals). The grid-point
altitude is embedded in the metadata. A second run of the same site/year reads
from disk (instantaneous, network-free).

### Gap policy (explicit quality, not silent) {#huecos}

NASA POWER has occasional missing values. The policy is:

- Gaps of **≤ 3 h** consecutive → **linear interpolation in time**.
- Gaps of **> 3 h** → **left as NaN**; a blocked-hours counter greater than zero
  signals the UI that it must ask the user for a decision.

The count of original gaps, largest gap, interpolated hours and blocked hours
travels with the series in a quality object. **Nothing is filled silently.**

## 3. From the horizontal resource (GHI) to the collector plane (POA) {#poa}

This is the physical heart of the subsystem. NASA POWER delivers the resource on a
**horizontal plane**; the collector is **tilted** by an angle β and **oriented**
with azimuth γ. It must be **transposed**.

### 3.1 Solar geometry (the Sun's position) {#spa}

For each hourly timestamp the solar position is computed with the **SPA** (*Solar
Position Algorithm*) of `pvlib`, which returns the **apparent zenith** $\theta_z$
and the **solar azimuth** $\gamma_s$. SPA internally solves, as a function of
(lat, lon, date-time):

- **Solar declination** $\delta$ (varies with the day of the year $n$):
  $$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$
- **Hour angle** $\omega$ (from true solar noon, with equation of time and
  longitude correction).
- **Solar zenith**:
  $$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$
  with $\phi$ the latitude.

Secasol **does not reimplement** these formulas: it delegates to SPA (sub-degree
precision, includes refraction and equation of time). The **solar transit** (true
noon) is computed separately to choose the day's representative hour, without
depending on the hourly GHI maximum.

### 3.2 Angle of incidence on the plane {#incidencia}

The **angle of incidence** $\theta_i$ between the direct ray and the normal of the
tilted plane (β, γ) is the key quantity of the direct component:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

### 3.3 Liu-Jordan transposition (isotropic model) {#liu-jordan}

The total irradiance on the plane (POA) breaks down into **three contributions**
(Liu-Jordan model, isotropic diffuse):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{direct}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{sky diffuse}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{ground reflected}}\,}
$$

where:

- $I_b = \mathrm{DNI}$ (direct normal), projected by $\cos\theta_i$.
- $I_d = \mathrm{DHI}$ (diffuse horizontal), attenuated by the **sky view factor**
  $(1+\cos\beta)/2$.
- $I = \mathrm{GHI}$ (global horizontal), reflected by the ground with **albedo**
  $\rho_g$ and view factor $(1-\cos\beta)/2$.

The **albedo** $\rho_g$ is configurable (default 0.25; albedo catalog by surface
type). In code, the three components are summed by
`pvlib.irradiance.get_total_irradiance`, to which Secasol passes β, γ already
converted to the pvlib convention, the SPA solar position, DNI/GHI/DHI and the
albedo.

The **isotropic** model is used for simplicity and consistency across all
pipelines; `pvlib` also supports Hay-Davies, Reindl, Klucher, King and Perez, and
the diffuse-model parameter leaves the substitution open.

### 3.4 Assumptions of the transposition {#hipotesis-poa}

- **Isotropic diffuse sky**: the diffuse is distributed uniformly over the dome
  (slightly underestimates the circumsolar; conservative for pre-design).
- **Lambertian ground** of uniform albedo.
- **Each hour is treated as quasi-instantaneous** at the solar position of the
  hourly bin (NASA POWER's hourly resolution).
- **Conservative fallback**: if DNI or DHI is missing for a given hour,
  direct/diffuse cannot be separated → **POA = GHI** is assumed for that hour
  (underestimating POA with β>0, but avoiding propagating NaN to the collector
  solver). Negative values from numerical artifacts near the horizon are clipped
  to 0.

## 4. Angle convention {#angulos}

The azimuth has **three conventions** and mixing them is a classic source of
orientation errors:

| Convention | 0° | +90° | Range | Use |
|---|---|---|---|---|
| **Duffie & Beckman** | South | West | [−180, +180] | internal storage and calculation logic |
| **UI360** | North | East | [0, 360) | user input in the Site section |
| **pvlib** | North | East | [0, 360) | internal irradiance calculation |

Conversion used in the POA transposition:

$$\psi_{pvlib} = (180^\circ + \gamma_{Duffie}) \bmod 360^\circ$$

Verification: γ=0° (South)→ψ=180° ✓; γ=90° (West)→ψ=270° ✓; γ=−90° (East)→ψ=90° ✓;
γ=±180° (North)→ψ=0° ✓. The conversion formulas **live in a single module** and
are never duplicated. The full detail is in
[Unit and angle conventions](?manual=convenciones).

## 5. Temporal slices (analysis modes) {#recortes}

The subsystem also provides the slices of the annual series consumed by the
different [analysis modes](?manual=tipologia):

- **Monthly typical day** — averages hour by hour all the records of a month →
  a 24 h "typical day". It converts to local time before grouping so the solar
  peak falls near 12 local. Feeds the **Annual** mode (one representative batch
  per month).
- **N consecutive real days** — slices a multi-day span; if it crosses Dec 31, it
  truncates and marks it explicitly, without inventing splices.
- **Window** — slices the [start, end] span mapped to the series year. Shared by
  the Site, Collector and Results sections (**Window** mode).

---

**See also:** [Solar radiation and oriented plane](?manual=radiacion)
(introductory version), [2 · Site and climate](?manual=emplazamiento) (usage
guide), [Appendix · Implementation](?manual=apendice-codigo#emplazamiento) (where
each piece lives in the code),
[Bibliography](?manual=bibliografia#duffie-beckman).
