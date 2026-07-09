# Drying physics — the product side

[Psychrometry](?manual=psicrometria) describes the air; this chapter describes the
**product**: how its moisture is quantified, why "bound" water is harder to remove
than free water, and how the **sorption isotherm** governs the drying rate. It is
the foundation of the chamber model
([Technical · Chamber](?manual=tec-camara#producto)).

## Moisture on a dry basis {#base-seca}

Secasol works the product moisture on a **dry basis**:

$$
X = \frac{M_{agua}}{M_{seca}} \quad \left[\frac{\text{kg water}}{\text{kg dry}}\right]
$$

whereas commercial usage speaks in **wet basis** ($w = M_{agua}/M_{total}$, the
"% moisture" on a label). The conversion:

$$
X = \frac{w}{1-w}, \qquad w = \frac{X}{1+X}
$$

A fresh tomato with 94 % moisture (wet basis) has $X_0 \approx 15.7$ kg of water
per kg of dry matter; the final dehydrate at 10 % wet basis, $X_{obj} \approx
0.11$. The dry basis is the natural one for the balances because the dry mass **is
conserved** during the process: the resulting dry product mass is
$M_{total}/(1+X_0)\cdot(1+X_{obj})$.

## Water activity {#actividad}

Not all the water in the product is equally available. The **water activity**
$a_w$ [0–1] measures how "free" it is: it is the equilibrium relative humidity of
the air in intimate contact with the product.

- Very wet product: $a_w \to 1$ — the water behaves almost like free water and
  evaporates easily.
- Almost dry product: $a_w \ll 1$ — the remaining water is adsorbed in the solid
  matrix and is much harder to extract.

$a_w$ matters doubly: it governs the **drying rate** (see below) and is the
**preservation** criterion — below $a_w \approx 0.6$ microorganisms do not grow,
which is the ultimate goal of drying.

## The sorption isotherm (GAB) {#isotermas}

The equilibrium relationship between the product moisture $X$ and its water
activity $a_w$, at a given temperature, is the **sorption isotherm**. Secasol uses
the **GAB** model (Guggenheim–Anderson–de Boer), the standard for foods:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

with three parameters per product ($X_m$ the monolayer, $C$ and $K$ sorption
constants) that come in the **product catalog**. The model uses it **inverted**:
given the current $X$, it obtains $a_w(X)$.

<!-- profundidad: The analytical inversion of GAB -->
Solving for $a_w$ from the GAB equation leads to a **quadratic** in $a_w$:

$$
K\,(1-C)\,a_w^2\;X + \left[(C-2)\,K\,X + X_m\,C\,K\right]a_w + X = 0
\;\;\Rightarrow\;\;
a_w = f(X;\,X_m, C, K)
$$

from which the physical root in [0, 1] is taken. Being analytical (without
iteration), it is evaluated millions of times inside the integrator at no cost. If
a catalog product has no calibrated GAB parameters, the system **warns** that the
slowdown curve is generic.
<!-- /profundidad -->

## How the isotherm governs the drying rate {#velocidad}

The chamber engine computes the evaporation in a **diffusive** way:

$$
\dot m_w = K_m\,A_{prod}\,\big(\underbrace{\omega_{sat}(T_{prod})\cdot a_w(X)}_{\omega_{sup}} - \omega_{flujo}\big)
$$

The driving force is the difference between the humidity of the **air layer stuck
to the product** ($\omega_{sup}$) and that of the flow. And that is where the
isotherm works: as the product dries, $a_w(X)$ **falls**, $\omega_{sup}$ drops, the
driving force shrinks and the drying rate **decreases by itself**.

This is how the classic drying periods appear **without any empirical curve**:

- **Constant-rate period** (wet product, $a_w\approx1$): the evaporation is
  limited by the air (temperature, humidity, velocity), not by the product. The
  product stays close to the wet-bulb temperature.
- **Falling-rate period** (product drying out, $a_w<1$): the matrix retains the
  remaining water; the rate falls and the product temperature rises toward that of
  the air.

The practical consequence: the **last tenths of moisture are the most expensive**
in time and energy. Drying beyond the preservation target wastes hours of sun.

## The product temperature {#temperatura}

The product has its own thermal dynamics: it receives sensible heat from the air
and spends latent heat evaporating,

$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = h_{conv}A_{prod}(T_{flujo}-T_{prod}) - \dot m_w\,L_v
$$

While it evaporates strongly, the latent term keeps it **cold** (near the
wet-bulb); when the drying slows, its temperature rises toward that of the air.
This matters for **quality**: the maximum admissible product temperature (color,
nutrients, the case of herbs and mushrooms) is usually the constraint that limits
the dryer's operating temperature.

---

**See also:** [The product catalog](?manual=catalogo-productos) (the available
products and their data), [Psychrometry](?manual=psicrometria) (the air side),
[4 · Chamber](?manual=camara#producto) (where the product is configured),
[Technical · Chamber](?manual=tec-camara#isotermas) (the full balance equations).
