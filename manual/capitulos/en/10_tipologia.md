# 1 · Typology and analysis configuration

The first section defines **which dryer** you are going to pre-design and **how**
it will be analyzed. Everything that follows depends on these two decisions: the
typology determines which sections apply (a Box has no external collector; a
Large scale adds an array, main duct and tunnel), and the analysis mode
determines which question the calculation answers (a design day? the whole year?
a real campaign?).

This is also where the project **metadata** (name, author, notes) is entered,
which later heads the PDF report.

## The three typologies {#tipologias}

| Typology | Typical scale | What it is |
|---|---|---|
| **Box** | ~10 kg | Compact direct dryer: the chamber captures the sun through its own translucent cover. Natural convection. No external collector or fan. |
| **Cabinet** | 0–100 kg | Indirect dryer: solar air collector + chamber with trays. With a fan or solar chimney. |
| **Large scale** | 100 kg – tonnes | Collector array + main duct + industrial chamber (batches or semi-continuous tunnel). |

<!-- esquema: circuito_caja | Air circuit of the Box-type dryer. -->

<!-- esquema: circuito_armario | Air circuit of the Cabinet-type dryer. -->

**Be careful when changing typology with an advanced project:** switching to
**Box** clears the collector and the fan (they do not apply), with a prior
warning. It is an intentional cascade to keep the project consistent.

<!-- profundidad: What each typology implies in the model -->
- **Box**: the chamber acts as the collector — the **translucent surfaces**
  (roof and/or walls, with the chamber's own orientation and mono-pitch roof)
  provide the solar gain, split between the product and the air (see
  [Technical · Chamber](?manual=tec-camara#techo-translucido)) and the air moves
  by thermal draft (a solar chimney can be added to reinforce it).
- **Cabinet**: the full chain collector → (auxiliary) → chamber, with the
  chamber inlet temperature given by the collector outlet.
- **Large scale**: on top of the cabinet, the flow split between array branches
  appears, the main duct with its loss and thermal gain, and the two chamber
  subtypes (see below). The analysis becomes a **production window**.
<!-- /profundidad -->

## Analysis mode {#modo-analisis}

The analysis mode defines the **forcings** with which the pre-design is run in
[7 · Results](?manual=resultados):

- **Daily** — a design day: either representative constant conditions, or the
  hourly transient of a day (real or synthetic) chosen by criterion (clear day,
  average day, etc.).
- **Annual** — the full year, month by month: each month is represented by its
  **typical day** (hourly average of the month) and the annual production is
  estimated by batches. Enables the "Annual operation" section in
  [4 · Chamber](?manual=camara#operacion-anual).
- **Window** — a real span [start, end] with continuous hourly climate: a week, a
  month, a harvest campaign. It is the natural mode for **Large scale**
  (production dashboards) and is also available for Box/Cabinet as **real
  multi-day**.

The section offers window presets (1 week, 1 month, campaign) and the selection
criterion for the representative day in daily mode.

## Large-scale subtypes {#subtipo}

With the Large-scale typology you also choose the **chamber subtype**:

- **Batch** — the chamber is loaded, the whole batch is dried, unloaded and
  repeated. The window production comes from chaining batches.
- **Semi-continuous (tunnel)** — a **counter-current** ADITAL-style tunnel: the
  product advances through zones while the hot air enters from the opposite end.
  The tunnel topology (number of zones and advance cadence) is configured in
  [4 · Chamber](?manual=camara).

<!-- profundidad: Why counter-current -->
In the counter-current tunnel the hottest, driest air meets the **almost dry**
product (which tolerates temperature and needs the maximum driving force), and
the already-humidified air meets the **fresh** product (which still evaporates a
lot because its water activity is high). That distributes the drying capacity
better than parallel flow. The model solves the N zones in series with the air
marching from the hot zone to the cold one — the detail is in
[Technical · Industrial mode](?manual=tec-industrial#semicontinuo).
<!-- /profundidad -->

---

**See also:** [Introduction](?manual=introduccion) (the full workflow),
[2 · Site](?manual=emplazamiento) (the next step),
[Technical · Industrial mode](?manual=tec-industrial) (batch, tunnel and main
duct in detail).
