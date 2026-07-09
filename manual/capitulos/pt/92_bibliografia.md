# Bibliografia

Referências citadas nos capítulos do manual, agrupadas por tema. A base bibliográfica do
Secasol é deliberadamente **clássica**: os modelos vêm da literatura padrão de engenharia
solar e de secagem, sem surpresas metodológicas.

## Recurso solar e geometria {#duffie-beckman}

- **Duffie, J. A. & Beckman, W. A.** — *Solar Engineering of Thermal Processes*. Wiley. A
  referência mãe: geometria solar, convenção de ângulos, transposição, modelo de
  Hottel-Whillier-Bliss do coletor.
- **Liu, B. Y. H. & Jordan, R. C. (1963)** — *The long-term average performance of
  flat-plate solar-energy collectors*. Modelo isotrópico da componente difusa (transposição
  GHI→POA).
- **Reda, I. & Andreas, A.** — *Solar Position Algorithm for Solar Radiation Applications*
  (NREL). O algoritmo SPA usado via pvlib.
- **NASA POWER** — *Prediction Of Worldwide Energy Resources* (reanálise MERRA-2). Fonte dos
  dados climáticos horários.
- **pvlib-python** — Holmgren, Hansen & Mikofski. Biblioteca padrão de modelagem do recurso
  solar.

## Coletor solar de ar {#hollands}

- **Hollands, K. G. T. et al. (1976)** — convecção natural em cavidades inclinadas (dupla
  cobertura e canais estanques).
- **McAdams, W. H.** — *Heat Transmission*. Convecção de vento sobre placa ($h_w = 5.7+3.8\,v$)
  e camada limite turbulenta.
- **Swinbank, W. C.** — temperatura efetiva de céu para radiação noturna.
- **Shah, R. K. & London, A. L. (1978)** — *Laminar Flow Forced Convection in Ducts*. Nusselt
  laminar desenvolvido.
- **Heaton, Reynolds & Kays (1964)** — entrada térmica laminar.
- **Gnielinski, V. (1976)** — transição e turbulento inicial.
- **Sparrow & Liu (1979)** — turbulento com uma parede quente (air heaters).
- **Dittus & Boelter (1930)** — turbulento clássico em dutos.
- **Çengel, Y. & Ghajar, A. (2014)** — *Heat and Mass Transfer*. Entrada térmica turbulenta e
  correlações de referência.
- **Churchill, S. W.** — convecção natural sobre placa (Churchill-Chu) e combinação de
  convecção mista.

## Secagem e psicrometria {#mujumdar}

- **Mujumdar, A. S.** — *Handbook of Industrial Drying*. Marco geral da secagem industrial.
- **Van den Berg, C. & Bruin, S.** — modelo de sorção **GAB** (Guggenheim–Anderson–de Boer).
- **Incropera, F. & DeWitt, D.** — *Fundamentals of Heat and Mass Transfer*. Analogia de
  Chilton-Colburn e correlações de placa plana (Pohlhausen, McAdams).
- **Threlkeld, J. L. / ASHRAE Fundamentals** — psicrometria do ar úmido (pressão de
  saturação, entalpia, carta corrigida por altitude).

## Eficiências de secagem {#leon}

- **Augustus Leon, M., Kumar, S. & Bhattacharya, S. C. (2002)** — *A comprehensive procedure
  for performance evaluation of solar food dryers*. As quatro eficiências (drying, pickup,
  térmica, total) da análise anual.

## Hidráulica e perdas de carga {#ashrae}

- **ASHRAE Handbook — Fundamentals (2017), cap. 21** — *Duct Design*. Atrito, singulares e a
  metodologia de rede hidráulica do campo de coletores.
- **Colebrook, C. F. / Haaland, S. E. (1983)** — fator de atrito em dutos; Haaland é a
  aproximação explícita usada em todo o programa.
- **Idelchik, I. E.** — *Handbook of Hydraulic Resistance* / **Crane TP-410** — coeficientes
  K de singulares e malhas.
- **Ergun, S. (1952)** — perda de carga em leitos empacotados.
- **Sutherland, W. (1893)** — viscosidade do ar em função da temperatura.

## Chaminés solares {#chimeneas}

- **Bansal, N. K. et al. / Chen, Z. D. et al.** — chaminés solares e efeito chaminé (*stack
  effect*) aplicado a ventilação e secagem.

## Caso de validação {#adital}

- **Durán, G.** — tese de doutorado, cap. 3: secador híbrido **ADITAL** de San Carlos
  (Salta). Referência de campo para dimensões, vazões e temperaturas do modo industrial.

## Cinética e isotermas por produto {#productos}

Os parâmetros de sorção (GAB) e as propriedades de cada produto do catálogo provêm de
publicações específicas por produto, referenciadas no próprio catálogo do programa
(`catalogo/productos/*.yaml`) e no índice bibliográfico do repositório.

---

**Ver também:** [Apêndice · Implementação](?manual=apendice-codigo) (onde se usa cada
referência no código).
