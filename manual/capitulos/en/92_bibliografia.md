# Bibliography

References cited in the manual chapters, grouped by topic. Secasol's bibliographic
base is deliberately **classic**: the models come from the standard literature of
solar engineering and drying, without methodological surprises.

## Solar resource and geometry {#duffie-beckman}

- **Duffie, J. A. & Beckman, W. A.** — *Solar Engineering of Thermal Processes*.
  Wiley. The parent reference: solar geometry, angle convention, transposition, the
  Hottel-Whillier-Bliss collector model.
- **Liu, B. Y. H. & Jordan, R. C. (1963)** — *The long-term average performance of
  flat-plate solar-energy collectors*. Isotropic model of the diffuse component
  (GHI→POA transposition).
- **Reda, I. & Andreas, A.** — *Solar Position Algorithm for Solar Radiation
  Applications* (NREL). The SPA algorithm used via pvlib.
- **NASA POWER** — *Prediction Of Worldwide Energy Resources* (MERRA-2 reanalysis).
  Source of the hourly climate data.
- **pvlib-python** — Holmgren, Hansen & Mikofski. Standard library for modeling the
  solar resource.

## Solar air collector {#hollands}

- **Hollands, K. G. T. et al. (1976)** — natural convection in inclined cavities
  (double cover and sealed channels).
- **McAdams, W. H.** — *Heat Transmission*. Wind convection over a plate
  ($h_w = 5.7+3.8\,v$) and turbulent boundary layer.
- **Swinbank, W. C.** — effective sky temperature for nighttime radiation.
- **Shah, R. K. & London, A. L. (1978)** — *Laminar Flow Forced Convection in
  Ducts*. Developed laminar Nusselt.
- **Heaton, Reynolds & Kays (1964)** — laminar thermal entry.
- **Gnielinski, V. (1976)** — transition and early turbulent.
- **Sparrow & Liu (1979)** — turbulent with one heated wall (air heaters).
- **Dittus & Boelter (1930)** — classic turbulent in ducts.
- **Çengel, Y. & Ghajar, A. (2014)** — *Heat and Mass Transfer*. Turbulent thermal
  entry and reference correlations.
- **Churchill, S. W.** — natural convection over a plate (Churchill-Chu) and mixed
  convection combination.

## Drying and psychrometry {#mujumdar}

- **Mujumdar, A. S.** — *Handbook of Industrial Drying*. General framework of
  industrial drying.
- **Van den Berg, C. & Bruin, S.** — the **GAB** sorption model
  (Guggenheim–Anderson–de Boer).
- **Incropera, F. & DeWitt, D.** — *Fundamentals of Heat and Mass Transfer*. The
  Chilton-Colburn analogy and flat-plate correlations (Pohlhausen, McAdams).
- **Threlkeld, J. L. / ASHRAE Fundamentals** — moist-air psychrometry (saturation
  pressure, enthalpy, altitude-corrected chart).

## Drying efficiencies {#leon}

- **Augustus Leon, M., Kumar, S. & Bhattacharya, S. C. (2002)** — *A comprehensive
  procedure for performance evaluation of solar food dryers*. The four efficiencies
  (drying, pickup, thermal, total) of the annual analysis.

## Hydraulics and pressure drops {#ashrae}

- **ASHRAE Handbook — Fundamentals (2017), ch. 21** — *Duct Design*. Friction,
  fittings and the hydraulic-network methodology of the collector field.
- **Colebrook, C. F. / Haaland, S. E. (1983)** — friction factor in ducts; Haaland
  is the explicit approximation used throughout the program.
- **Idelchik, I. E.** — *Handbook of Hydraulic Resistance* / **Crane TP-410** — K
  coefficients of fittings and meshes.
- **Ergun, S. (1952)** — pressure drop in packed beds.
- **Sutherland, W. (1893)** — air viscosity as a function of temperature.

## Solar chimneys {#chimeneas}

- **Bansal, N. K. et al. / Chen, Z. D. et al.** — solar chimneys and the stack
  effect applied to ventilation and drying.

## Validation case {#adital}

- **Durán, G.** — doctoral thesis, ch. 3: the **ADITAL** hybrid dryer of San Carlos
  (Salta). Field reference for dimensions, flows and temperatures of the industrial
  mode.

## Kinetics and isotherms per product {#productos}

The sorption parameters (GAB) and the properties of each catalog product come from
product-specific publications, referenced in the program's own catalog
(`catalogo/productos/*.yaml`) and in the repository's bibliographic index.

---

**See also:** [Appendix · Implementation](?manual=apendice-codigo) (where each
reference is used in the code).
