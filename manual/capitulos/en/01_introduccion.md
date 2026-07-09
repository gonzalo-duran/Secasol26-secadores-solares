# Introduction — what Secasol is and how to use it

**Secasol** is a **solar dryer pre-design** tool developed by the GEEDSP group
(INENCO, CONICET–UNSa). It integrates real climate data, coupled heat-and-mass
physics, and three dryer scales — from the family-sized box to the industrial
tunnel — in a single application, free and accessible from a browser.

**Pre-design** means order of magnitude: Secasol is meant to explore, size and
compare designs quickly, *before cutting the first sheet of metal*. It does not
replace detailed calculation, testing or measurement.

## Who it is for {#publico}

- **Teachers, researchers and advanced students** of renewable energy and
  engineering: the primary audience. The whole physical model is documented in
  this manual (Part IV), with its equations, assumptions and references.
- **Producers and technicians** with basic training: the guided 7-section flow
  and the Part II guides let you reach a pre-design without going into the
  equations.

## How the program is organized {#flujo}

The design is built by walking through **7 sections** (left-hand side menu), in
order. Each one writes to a single central project, so you can go back and forth
without losing anything:

1. [**Typology**](?manual=tipologia) — which dryer (box / cabinet / large
   scale) and which analysis (daily / annual / window).
2. [**Site**](?manual=emplazamiento) — site coordinates; automatic climate
   download (NASA POWER) and collector orientation.
3. [**Collector**](?manual=colector) — type, materials, geometry and array (does
   not apply to Box).
4. [**Chamber**](?manual=camara) — geometry, walls, trays, product and load.
5. [**Auxiliary**](?manual=auxiliar) — electric or wood-fired backup (optional).
6. [**Fan/drive**](?manual=motor) — fan or solar chimney.
7. [**Results**](?manual=resultados) — the full coupled run: dashboard,
   psychrometric chart, export.

**Have ready** to start: the site latitude/longitude and the product to dry.

## Saving and loading projects {#guardar}

Each section lets you save its configuration, and Results exports the **complete
JSON snapshot** of the project: a reproducible file that can be reloaded into
Secasol (same version or later), versioned or shared. The final report is also
produced in TXT and **PDF**.

## How to use this manual {#como-usar}

The manual opens **alongside** the program: the **📖 Manual** buttons in each
section open the corresponding chapter in another browser tab, so you can consult
it without losing your design. (If your browser blocks the pop-up tab, enable
pop-ups for the site or open the link with a wheel/middle-button click.)

Each chapter has **two reading levels**: the main text gives the general idea,
and the collapsible **🔬 In depth** blocks contain the inner workings —
equations, correlations, model decisions. For the full detail of each subsystem
there is **Part IV (Technical reference)**, with the physics equation by
equation.

Structure of the manual:

- **Part II — Guide by section**: one chapter per program section, mirroring the
  7 tabs.
- **Part III — Fundamentals**: the cross-cutting concepts —
  [radiation and oriented plane](?manual=radiacion),
  [psychrometry](?manual=psicrometria), [drying physics](?manual=secado),
  [conventions](?manual=convenciones).
- **Part IV — Technical reference**: the full physical model by subsystem.
- **Appendices**: [code implementation](?manual=apendice-codigo),
  [glossary](?manual=glosario), [bibliography](?manual=bibliografia).

## What makes Secasol different {#distintivo}

- **Truly coupled physics** — collector, chamber, product, air and auxiliary are
  solved **together** with a global iterative loop, not separately.
- **Real hourly site climate** — NASA POWER + pvlib, transposition to the
  collector plane; the user only provides lat/lon.
- **Three typologies × three analysis modes** — from the 10 kg box to the
  tonne-scale tunnel; from the design day to the real campaign.
- **Emergent outlet dryness** — the system tells you how much it dries; the
  result is not forced.
- **Warning system** — catches design errors early and does not fail silently.
- **Validated** — against the classic Hottel-Whillier-Bliss model (R²≥0.999) and
  against a real industrial dryer (ADITAL, San Carlos).

<!-- profundidad: Honest limits of the model -->
- It is **pre-design** (order of magnitude), not certification or measurement.
- The product catalog has few items with a **calibrated GAB** isotherm; a new
  product requires prior calibration (the system warns when it uses generic
  parameters).
- Thick beds (> 5 cm): the diffusive model overestimates the rate; the software
  **warns about it**. Internal product diffusion is a future extension.
- In the Type 2/3/4 collectors some air properties are still evaluated as
  constants (impact ~2–3 % on useful heat).
<!-- /profundidad -->

---

**Next step:** [1 · Typology](?manual=tipologia), or straight to the
[index](?manual=indice) of the manual.
