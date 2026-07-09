# Bibliografía

Referencias citadas en los capítulos del manual, agrupadas por tema. La base
bibliográfica de Secasol es deliberadamente **clásica**: los modelos vienen de
la literatura estándar de ingeniería solar y de secado, sin sorpresas
metodológicas.

## Recurso solar y geometría {#duffie-beckman}

- **Duffie, J. A. & Beckman, W. A.** — *Solar Engineering of Thermal
  Processes*. Wiley. La referencia madre: geometría solar, convención de
  ángulos, transposición, modelo de Hottel-Whillier-Bliss del colector.
- **Liu, B. Y. H. & Jordan, R. C. (1963)** — *The long-term average performance
  of flat-plate solar-energy collectors*. Modelo isotrópico de la componente
  difusa (transposición GHI→POA).
- **Reda, I. & Andreas, A.** — *Solar Position Algorithm for Solar Radiation
  Applications* (NREL). El algoritmo SPA usado vía pvlib.
- **NASA POWER** — *Prediction Of Worldwide Energy Resources* (reanálisis
  MERRA-2). Fuente de los datos climáticos horarios.
- **pvlib-python** — Holmgren, Hansen & Mikofski. Librería estándar de modelado
  del recurso solar.

## Colector solar de aire {#hollands}

- **Hollands, K. G. T. et al. (1976)** — convección natural en cavidades
  inclinadas (doble cubierta y canales estancos).
- **McAdams, W. H.** — *Heat Transmission*. Convección de viento sobre placa
  ($h_w = 5.7+3.8\,v$) y capa límite turbulenta.
- **Swinbank, W. C.** — temperatura efectiva de cielo para radiación nocturna.
- **Shah, R. K. & London, A. L. (1978)** — *Laminar Flow Forced Convection in
  Ducts*. Nusselt laminar desarrollado.
- **Heaton, Reynolds & Kays (1964)** — entrada térmica laminar.
- **Gnielinski, V. (1976)** — transición y turbulento inicial.
- **Sparrow & Liu (1979)** — turbulento con una pared caliente (air heaters).
- **Dittus & Boelter (1930)** — turbulento clásico en ductos.
- **Çengel, Y. & Ghajar, A. (2014)** — *Heat and Mass Transfer*. Entrada
  térmica turbulenta y correlaciones de referencia.
- **Churchill, S. W.** — convección natural sobre placa (Churchill-Chu) y
  combinación de convección mixta.

## Secado y psicrometría {#mujumdar}

- **Mujumdar, A. S.** — *Handbook of Industrial Drying*. Marco general del
  secado industrial.
- **Van den Berg, C. & Bruin, S.** — modelo de sorción **GAB**
  (Guggenheim–Anderson–de Boer).
- **Incropera, F. & DeWitt, D.** — *Fundamentals of Heat and Mass Transfer*.
  Analogía de Chilton-Colburn y correlaciones de placa plana (Pohlhausen,
  McAdams).
- **Threlkeld, J. L. / ASHRAE Fundamentals** — psicrometría del aire húmedo
  (presión de saturación, entalpía, carta corregida por altitud).

## Eficiencias de secado {#leon}

- **Augustus Leon, M., Kumar, S. & Bhattacharya, S. C. (2002)** — *A
  comprehensive procedure for performance evaluation of solar food dryers*.
  Las cuatro eficiencias (drying, pickup, térmica, total) del análisis anual.

## Hidráulica y pérdidas de carga {#ashrae}

- **ASHRAE Handbook — Fundamentals (2017), cap. 21** — *Duct Design*. Fricción,
  singulares y la metodología de red hidráulica del campo de colectores.
- **Colebrook, C. F. / Haaland, S. E. (1983)** — factor de fricción en ductos;
  Haaland es la aproximación explícita usada en todo el programa.
- **Idelchik, I. E.** — *Handbook of Hydraulic Resistance* / **Crane TP-410** —
  coeficientes K de singulares y mallas.
- **Ergun, S. (1952)** — pérdida de carga en lechos empacados.
- **Sutherland, W. (1893)** — viscosidad del aire en función de la temperatura.

## Chimeneas solares {#chimeneas}

- **Bansal, N. K. et al. / Chen, Z. D. et al.** — chimeneas solares y efecto
  chimenea (*stack effect*) aplicado a ventilación y secado.

## Caso de validación {#adital}

- **Durán, G.** — tesis doctoral, cap. 3: secador híbrido **ADITAL** de San
  Carlos (Salta). Referencia de campo para dimensiones, caudales y temperaturas
  del modo industrial.

## Cinética e isotermas por producto {#productos}

Los parámetros de sorción (GAB) y las propiedades de cada producto del catálogo
provienen de publicaciones específicas por producto, referenciadas en el
propio catálogo del programa (`catalogo/productos/*.yaml`) y en el índice
bibliográfico del repositorio.

---

**Ver también:** [Apéndice · Implementación](?manual=apendice-codigo) (dónde se
usa cada referencia en el código).
