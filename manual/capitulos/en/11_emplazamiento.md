# 2 · Site and climate resources

Here the project is anchored to a real place: with **latitude, longitude and
altitude**, Secasol downloads a **full year of hourly climate** (8760 hours)
from the NASA POWER service and turns it into the series that feed all the
calculations: temperature, radiation (global, direct and diffuse), wind,
humidity and pressure. This is also where the **collector orientation** (tilt
and azimuth) is defined, which determines how much of that radiation actually
reaches the collector plane.

The philosophy of the section: **the user only enters the coordinates**; the
download, caching, unit conversions and transposition to the collector plane are
automatic.

## Site coordinates {#coordenadas}

Latitude and longitude in decimal degrees (negative for the southern hemisphere
and for the west of Greenwich — e.g. Salta ≈ lat −24.8, lon −65.4). The
**altitude** adjusts atmospheric pressure (it affects air density and
psychrometry); if you do not know it, NASA POWER brings the grid-point value.
The **time zone** aligns the climate hours with the local solar time.

## Climate download {#descarga}

The download button fetches the chosen year from **NASA POWER** (global
satellite reanalysis, ~0.5° grid, the same service the photovoltaic industry
uses). The download is **cached to disk**: repeating the same site and year is
instantaneous and network-free.

<!-- profundidad: What is downloaded and how it is converted -->
Hourly variables: GHI, DNI, DHI [W/m²], temperature at 2 m [°C→K], wind at 2 m
[m/s], relative humidity [%→fraction], surface pressure [kPa→Pa]. The conversion
to SI happens only once in the climate layer; from there on the whole system
works in strict SI (see [Conventions](?manual=convenciones)). The cache uses a
cryptographic key of (lat, lon, year), so changing any of the three triggers a
fresh download. The detail is in
[Technical · Solar resource and climate](?manual=tec-emplazamiento#nasa-power).
<!-- /profundidad -->

### Data quality {#calidad}

NASA POWER has occasional gaps. Secasol's policy is **explicit, not silent**:

- Gaps of **up to 3 consecutive hours** are linearly interpolated (and it is
  reported how many hours were interpolated).
- **Larger** gaps are not filled: the section shows how many hours were left
  blocked and asks you for a decision (choose another year, another site, or
  accept the gap knowing which days it affects).

## Collector orientation {#orientacion}

The **tilt** β (0° = horizontal) and the **azimuth** (where the plane "looks",
with 0° = North in the UI input) define the collector plane. With them Secasol
**transposes** the horizontal radiation to the plane: the **POA** (*plane of
array*), which is what all the collector calculations use.

Quick rules: in the southern hemisphere the collector faces **North**; β close
to the latitude for annual use, larger to favor winter. The full basis
(radiation components, angle of incidence, Liu-Jordan model) is in
[Solar radiation and oriented plane](?manual=radiacion).

In the **Box** typology this section does not appear (there is no external
collector): the collecting plane is the chamber itself, and its orientation and
roof pitch are defined in [4 · Chamber](?manual=camara#orientacion).

The ground **albedo** of the surroundings is also configured (the fraction of
radiation the ground reflects toward the collector), with a catalog of typical
values.

## Charts: POA vs GHI {#graficas}

The section charts compare the **horizontal** radiation (GHI) with the radiation
**in the collector plane** (POA) for the day and the year: they are the tool for
choosing β and azimuth by seeing the real effect on the resource. All charts
allow downloading the data (CSV) and the image (PNG).

<!-- profundidad: How to read the POA vs GHI comparison -->
- If the POA stays **above** the GHI in the months of interest, the tilt is
  working in your favor (typical in winter with β > 0).
- A POA **lower** than the GHI in summer with a large β is expected (the sun
  passes high) and not necessarily a problem if the design prioritizes winter.
- The hourly peak of the POA shifts if the azimuth deviates from North
  (geographic south → northern hemisphere): useful if the drying needs more
  energy in the morning or the afternoon.
<!-- /profundidad -->

## Production window {#ventana}

If the [analysis mode](?manual=tipologia#modo-analisis) is **Window**, here the
chosen span is visualized over the real climate: it serves to verify that the
campaign falls on dates with a reasonable resource before running the
pre-design.

---

**See also:** [Solar radiation and oriented plane](?manual=radiacion) (basis of
the transposition),
[Technical · Solar resource and climate](?manual=tec-emplazamiento) (download,
cache, gap policy, equations), [3 · Collector](?manual=colector) (who consumes
the POA).
