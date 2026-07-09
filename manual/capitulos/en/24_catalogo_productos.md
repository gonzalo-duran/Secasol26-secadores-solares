# The product catalog

[Drying physics](?manual=secado) explains *how* a product dries; this chapter
describes *which* products Secasol brings, how they were chosen, what data they
are loaded with and what each catalog field means. It is the applied counterpart
of the physics chapter: there are the equations, here are the tomatoes, the apples
and the carob with their numbers.

The catalog lives in `catalogo/productos/*.yaml` and is chosen from
[4 · Chamber](?manual=camara#producto).

## How the products were selected {#seleccion}

The criterion was not "the most-dried products in the world" but **relevance for
the regions where Secasol will be used** — the Argentine Northwest (NOA), Cuyo,
the Litoral — plus some native products of cultural and economic value:

- **Vegetables** of wide regional availability (tomato, Puna potato, Cuyo onion,
  pepper for Salta paprika).
- **Fruits** from the fruit belts (Alto Valle apple, peach, Mendoza plum) and an
  **Andean tuber**, yacón, of traditional production in Jujuy and Salta.
- **Aromatic leaves** for export (NOA oregano, Litoral yerba mate).
- **Native and identity** products such as **carob** (*algarroba*: flour, patay,
  arrope), with Argentine literature available including work by INENCO itself.

Each product was loaded from **published scientific literature** (kinetics and
isotherm papers, referenced in the catalog and in the
[bibliography](?manual=bibliografia#productos)); where there were no direct data,
it was estimated **by analogy** with a morphologically similar product, and that
is declared explicitly (see
[Cases that call for care](?manual=catalogo-productos#cuidados)).

## The available products {#disponibles}

Today the catalog brings **19 products** in 5 categories. The typical initial
moisture is on a dry basis (kg of water per kg of dry matter — see
[dry basis](?manual=secado#base-seca)); the GAB status indicates whether the
sorption isotherm is calibrated or pending (see
[calibration](?manual=catalogo-productos#calibracion)).

| Product | Category | X₀ typical (kg/kg dm) | GAB |
|---|---|---|---|
| Tomato | Vegetable | 15.7 (~94 % wb) | pending |
| Potato | Vegetable | 4.5 | ✓ calibrated |
| Onion | Vegetable | 8.1 | pending |
| Red pepper | Vegetable | 10.7 | ✓ calibrated |
| Grated carrot | Vegetable | 9.0 | pending |
| Parsley | Vegetable | 5.7 | pending |
| Celery | Vegetable | 22.2 (~96 % wb) | pending |
| Cassava | Vegetable | 1.9 (~65 % wb) | pending |
| Red chili | Vegetable | 3.25 | pending |
| Apple | Fruit | 4.6 | ✓ calibrated |
| Peach | Fruit | 6.3 | pending |
| Yacón | Fruit | 9.0 | ✓ calibrated |
| Pomegranate | Fruit | 2.72 | pending |
| Plum | Fruit | 9.86 | pending |
| Yerba mate | Aromatic leaf | 2.3 | pending |
| Oregano | Aromatic leaf | 5.7 | pending |
| Coca | Aromatic leaf | 1.3 | pending |
| Beef charqui | Meat | 3.0 | pending |
| Carob | Legume/fruit | 0.25 (~20 % wb) | pending |

The X₀ values are **typical reference** values; the real product varies with the
variety, ripeness and cut, and that is why in [4 · Chamber](?manual=camara) the
initial moisture is a value you enter yourself (the catalog only suggests it).

## Initial and final moisture {#humedades}

Two numbers define the drying work of a batch:

- **Initial moisture X₀** — how much water the fresh product brings. It is high in
  juicy vegetables and fruits (tomato ~15.7, celery ~22) and low in already
  partially dry or woody products (carob ~0.25, cassava ~1.9).
- **Final or target moisture X_obj** — where you want to get to. It is set by the
  **preservation criterion**: below a water activity of ~0.6 microorganisms do not
  grow ([drying physics](?manual=secado#actividad)). The catalog brings, as a
  reference, the **equilibrium moisture with dry air** of each product (the minimum
  X achievable with the air of that climate).

Both go on a **dry basis**; the conversion from the commercial "% moisture" (wet
basis) is in [drying physics](?manual=secado#base-seca). Remember that the last
tenths of moisture are the most expensive in time and energy: setting an X_obj more
demanding than needed wastes hours of sun.

## What each product defines in the catalog {#campos}

Each catalog entry has:

- **Description** — species, reference variety, production region and quality
  notes (sensitivity to browning, to temperature, etc.).
- **Basic properties** — bulk density, specific heat of the dry matter, typical
  initial moisture and equilibrium moisture, each with its **data quality** (HIGH /
  MEDIUM / LOW) and its source.
- **GAB sorption isotherm** — the parameters $X_m, C, K$ that govern the drying
  rate (see [drying physics](?manual=secado#isotermas)). It is **the data the
  engine actually uses**.
- Operation metadata: **category**, **photosensitivity** (whether an opaque
  chamber is preferable to a translucent one) and `tipo_secado`.

<!-- profundidad: The thin-layer kinetics are vestigial -->
The catalog still stores, for many products, **thin-layer kinetics** parameters
(moisture-ratio curves MR(t) of the Page or Midilli type, with their constant $k$
and exponent $n$). **The engine no longer uses them to calculate**: the old
thin-layer evaluator was replaced by the coupled heat-mass balance, where the
drying curve *emerges* from the diffusion governed by the GAB isotherm, not from
an empirical fit ([Technical · Chamber](?manual=tec-camara#motor-unico)).

Why are they still there, then? Those `capa_fina:` blocks fulfill a single
function today: **they filter which products appear in the selector** of the
Chamber section. They are availability metadata, not calculation parameters. When
reading a catalog sheet, the number that matters for the result is the **GAB
isotherm**, not the thin-layer kinetics.
<!-- /profundidad -->

## Calibration status {#calibracion}

The catalog is **rich in structure but half-populated**, and it is worth knowing
this before trusting a number:

- **4 of 19 products have the GAB isotherm calibrated** with published data:
  **apple, potato, yacón and red pepper**. In these, the drying curve the model
  produces rests on a real isotherm.
- The **remaining 15 have the isotherm pending** (marked with null parameters and
  the DOI of the paper to be loaded). With them, the model uses a generic isotherm
  and **the system emits a warning** noting that the drying slowdown is not
  calibrated for that product.

This does not invalidate the pre-design with a pending product — it serves to size
in order of magnitude — but it is an honest fact: a result on apple weighs more
than one on plum, and the app tells you so.

## Cases that call for care {#cuidados}

- **Estimated by analogy** — **coca** inherits parameters from yerba mate (a
  similarly structured shrub leaf) due to scarce literature, and **celery** those
  of parsley. The catalog itself asks to use them *with caution*.
- **Photosensitive** — oregano, yerba, coca, red pepper, red chili, parsley and
  celery degrade color or essential oils with UV light and excessive heat; for
  them an **opaque chamber** is preferable, not a translucent roof
  ([4 · Chamber](?manual=camara#techo)).
- **Non-standard geometry** — **grated carrot** has an effective thickness much
  smaller than the slices of the laboratory tests: its parameters are only
  indicative.
- **Charqui** — the salt strongly modifies the isotherm; the parameters must
  correspond to the salting level used.

## Adding or calibrating a product {#agregar}

The catalog is designed to grow. To add a new product or complete the calibration
of a pending one:

1. Look up in the literature the **sorption isotherm** (GAB parameters) and the
   basic properties; the repository keeps a **bibliographic index per product** as
   a starting point.
2. Load the values into the YAML following the **catalog reference template**,
   with their data quality and source.
3. The app validates the structure at startup; if the isotherm is missing, the
   product still appears but **warns** that it uses generic parameters.

The long-term goal is that every product of regional interest has its isotherm
calibrated with published data — it is one of the project's open lines of work.

---

**See also:** [Drying physics](?manual=secado) (the theory behind these data),
[4 · Drying chamber](?manual=camara#producto) (where the product is chosen and X₀
and X_obj are loaded), [Bibliography](?manual=bibliografia#productos) (the sources
of the parameters).
