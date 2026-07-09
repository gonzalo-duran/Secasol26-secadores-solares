# Radiação solar e plano orientado

O coletor não "vê" a radiação que as bases de dados meteorológicas reportam: essas
séries são medidas sobre **plano horizontal**, e o coletor está **inclinado e
orientado**. Este capítulo explica as componentes da radiação solar, como se descreve
a posição do Sol e como o Secasol **transpõe** o recurso horizontal ao plano do coletor
(a chamada **POA**, *plane of array*). É o fundamento da seção
[2 · Localização](?manual=emplazamiento) e de todos os cálculos a jusante: **o coletor
sempre recebe POA, não GHI**.

## As três componentes da radiação {#componentes}

A radiação solar que chega a uma superfície se decompõe em três partes, e as bases de
dados (NASA POWER no caso do Secasol) as reportam separadamente:

| Sigla | Nome | O que é |
|---|---|---|
| **GHI** | Global horizontal | Total que recebe uma superfície horizontal (soma de direta projetada + difusa). |
| **DNI** | Direta normal | A que vem do disco solar, medida sobre um plano perpendicular ao raio. |
| **DHI** | Difusa horizontal | A que chega do resto da abóbada celeste (dispersada pela atmosfera e nuvens). |

Num meio-dia limpo domina a direta; num dia nublado quase todo o recurso é difuso. A
distinção importa porque cada componente responde **diferente** à inclinação do
coletor: a direta depende do ângulo com que o raio incide, a difusa de quanta abóbada
celeste o plano "vê", e aparece uma terceira contribuição nova — a **refletida do solo**
— que sobre plano horizontal é nula.

## A posição do Sol {#posicion-solar}

Para projetar a componente direta é preciso saber onde está o Sol a cada momento. A
posição se descreve com dois ângulos: o **zenital** $\theta_z$ (distância angular entre
o Sol e a vertical) e o **azimute solar** $\gamma_s$ (orientação do Sol sobre o
horizonte).

O Secasol não reimplementa a astronomia: delega ao algoritmo **SPA** (*Solar Position
Algorithm*) via `pvlib`, com precisão sub-grau, refração atmosférica e equação do tempo
incluídas. Com isso, além disso, calcula o **meio-dia solar verdadeiro** (trânsito) de
cada dia, que é a hora que as visões "dia representativo" usam.

<!-- profundidad: As equações astronômicas que o SPA resolve -->
Embora o SPA use um algoritmo de alta precisão, as magnitudes que resolve são as
clássicas da geometria solar (Duffie & Beckman):

**Declinação solar** $\delta$ — o ângulo entre o plano equatorial e a linha Terra-Sol;
varia com o dia do ano $n$:

$$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$

**Ângulo horário** $\omega$ — a posição do Sol em relação ao meio-dia solar verdadeiro
(15° por hora), com equação do tempo e correção de longitude.

**Zenital solar** — combinando latitude $\phi$, declinação e ângulo horário:

$$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$

O complemento de $\theta_z$ é a **altura solar**. Quando $\theta_z > 90°$ o Sol está
abaixo do horizonte e não há componente direta.
<!-- /profundidad -->

## O ângulo de incidência {#incidencia}

Um plano inclinado um ângulo $\beta$ e orientado com azimute $\gamma$ tem uma normal
própria. O **ângulo de incidência** $\theta_i$ é o que o raio direto forma com essa
normal, e governa quanta direta o plano capta:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

Quando o Sol está "de frente" para o coletor, $\cos\theta_i \to 1$ e a captação direta é
máxima; quando o raio chega rasante, $\cos\theta_i \to 0$. Note que a fórmula usa o
azimute na **convenção Duffie & Beckman** (0° = Sul): ver
[Convenções de unidades e ângulos](?manual=convenciones).

## Do plano horizontal ao plano do coletor {#transposicion}

Com a posição solar e a geometria do plano, a irradiância total sobre o plano do coletor
se monta somando três contribuições. O Secasol usa o modelo de **Liu-Jordan** (difuso
isotrópico):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{direta}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{difusa de céu}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{refletida do solo}}\,}
$$

onde:

- $I_b = \mathrm{DNI}$, projetada por $\cos\theta_i$: é a componente sensível à
  orientação.
- $I_d = \mathrm{DHI}$, escalada pelo **fator de vista do céu** $(1+\cos\beta)/2$: um
  plano horizontal ($\beta=0$) vê toda a abóbada (fator 1); um plano vertical vê a
  metade (fator 0,5).
- $I = \mathrm{GHI}$, refletida pelo solo com **albedo** $\rho_g$ e fator de vista do
  solo $(1-\cos\beta)/2$: nula em horizontal, cresce ao inclinar.

O albedo é configurável na seção Localização (default 0,25, com um catálogo de valores
típicos por tipo de superfície: grama, terra, neve, etc.).

<!-- profundidad: Hipóteses do modelo isotrópico e fallback -->
O modelo de Liu-Jordan assume:

- **Céu difuso isotrópico**: a radiação difusa chega uniforme de toda a abóbada.
  Subestima levemente a componente circumsolar (o halo brilhante ao redor do disco
  solar), o que o torna **conservador** para pré-projeto.
- **Solo lambertiano** de albedo uniforme (reflete difusamente em todas as direções).
- **Cada hora é quase instantânea**: avalia-se a posição solar do bin horário (a
  resolução do NASA POWER é horária).

O `pvlib` também implementa modelos anisotrópicos (Hay-Davies, Reindl, Klucher, Perez);
o Secasol usa o isotrópico por simplicidade e coerência entre todos os seus pipelines, e
deixa o parâmetro `modelo_difuso` aberto para substituí-lo.

**Fallback conservador:** se numa hora falta DNI ou DHI não se pode separar direta de
difusa; essa hora assume-se $I_{POA} = \mathrm{GHI}$ (subestima com $\beta>0$, mas evita
propagar `NaN` ao solver do coletor). Os valores negativos por artefato numérico perto
do horizonte são recortados a 0.
<!-- /profundidad -->

## O que isso significa para seu projeto {#criterios}

Duas regras práticas saem diretas da física anterior:

- **Inclinação** $\beta$: inclinar o coletor aproxima sua normal do Sol das horas úteis.
  Como regra grosseira para uso anual, $\beta \approx$ latitude; para favorecer o
  inverno (sol baixo), $\beta >$ latitude; para o verão, $\beta <$ latitude. A seção
  [3 · Coletor](?manual=colector) permite avaliar graficamente a POA resultante dia a
  dia e no ano.
- **Orientação** $\gamma$: no hemisfério sul o coletor "olha" para o Norte (e para o Sul
  no hemisfério norte). Desvios de ±15° custam pouco; giros maiores deslocam o pico de
  captação para a manhã ou a tarde.

O ganho de transpor não é pequeno: em locais de latitude média, um plano bem inclinado
pode captar no inverno bem mais energia que o plano horizontal — e esse inverno costuma
ser justamente quando a secagem precisa de mais ajuda.

---

**Ver também:** [2 · Localização e clima](?manual=emplazamiento) (onde tudo isso se
configura), [Técnico · Recurso solar e clima](?manual=tec-emplazamiento) (download NASA
POWER, política de lacunas e detalhes de implementação),
[Convenções de unidades e ângulos](?manual=convenciones) (as três convenções de
azimute).
