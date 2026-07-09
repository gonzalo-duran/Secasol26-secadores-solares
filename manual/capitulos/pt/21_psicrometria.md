# Psicrometria — o ar úmido e sua carta

A secagem é, no fundo, um problema de **ar úmido**: o ar entra com certa capacidade de
levar embora água, a usa sobre o produto, e sai mais frio e mais úmido. A psicrometria é
a linguagem para descrever esse processo, e a **carta psicrométrica** é seu mapa. Este
capítulo define as magnitudes (umidade absoluta, umidade relativa, saturação, entalpia)
e ensina a ler a carta que o Secasol traça em [7 · Resultados](?manual=resultados#carta).

## Umidade absoluta e umidade relativa {#humedades}

Duas formas distintas — e complementares — de dizer "quanta água há no ar":

- **Umidade absoluta** $\omega$ [kg de água / kg de ar seco]: a massa de vapor por
  unidade de massa de ar seco. É a variável de **conservação**: se não se acrescenta nem
  retira água, $\omega$ não muda mesmo que a temperatura mude.
- **Umidade relativa** UR [0–1]: quão perto está o vapor da **saturação** nessa
  temperatura: $UR = p_v/p_{sat}(T)$. É a variável de **capacidade**: com UR baixa o ar
  "tem sede"; com UR = 1 não admite mais água.

A chave da secagem solar está na relação entre ambas: **aquecer o ar não muda sua
$\omega$, mas baixa sua UR** — porque $p_{sat}(T)$ cresce exponencialmente com a
temperatura. Ar ambiente a 20 °C e 60 % UR, aquecido a 50 °C, baixa para ~11 % UR:
passou de morno e úmido a sedento, sem lhe retirar uma gota de água. Isso é o que o
coletor faz.

<!-- profundidad: As relações psicrométricas que o Secasol usa -->
Com pressão total $P$ e pressão parcial de vapor $p_v$:

$$
\omega = 0.622\,\frac{p_v}{P - p_v},
\qquad
\omega_{sat}(T) = 0.622\,\frac{p_{sat}(T)}{P - p_{sat}(T)}
$$

A pressão de saturação $p_{sat}(T)$ é avaliada com a correlação padrão ASHRAE. Note a
dependência com $P$: a maior **altitude** (menor pressão), a mesma $p_v$ dá mais
$\omega$ — por isso o Secasol corrige toda a psicrometria pela pressão do local. A
**entalpia do ar úmido** (por kg de ar seco) é

$$
h = c_{p,as}\,T + \omega\,(L_v + c_{p,v}\,T)
$$

e o calor específico do ar úmido $c_{p,h}=1006+1805\,\omega$ J/(kg·K). Essas mesmas
funções são usadas pelo motor de câmara ([Técnico · Câmara](?manual=tec-camara#cstr)).
<!-- /profundidad -->

## O que acontece em cada componente do secador {#proceso}

Sobre as variáveis $(T, \omega)$:

| Trecho | T | ω | UR | Processo |
|---|---|---|---|---|
| Coletor | ↑ | = | ↓↓ | aquecimento sensível |
| Auxiliar | ↑ | = | ↓ | aquecimento sensível |
| Câmara | ↓ | ↑ | ↑ | secagem (≈ adiabática) |

Na câmara o ar cede calor sensível para evaporar água e a incorpora como vapor: por isso
se **resfria e umedece ao mesmo tempo**. Se a câmara fosse perfeitamente adiabática, a
entalpia do ar se conservaria (o calor sensível que perde ≈ o latente que ganha).

## A carta psicrométrica {#carta}

A carta é o plano **temperatura de bulbo seco (eixo X) vs umidade absoluta $\omega$
(eixo Y)**, com duas famílias de curvas de fundo:

- A **curva de saturação** (UR = 100 %): a fronteira superior; além dela a água
  condensa.
- As curvas de **UR constante** (10 % a 90 %): leque entre o eixo X e a saturação.

Sobre esse fundo, o Secasol traça a **poligonal do processo** com os estados calculados:
**ambiente → saída do coletor → entrada na câmara (após o auxiliar) → saída da câmara**,
mais uma **isentálpica de referência** pontilhada a partir da entrada da câmara.

Como lê-la:

- Os trechos de coletor e auxiliar são **horizontais para a direita** ($\omega$
  constante, T sobe). Seu comprimento é o trabalho térmico obtido.
- O trecho de câmara sobe **para a esquerda**: o ar se resfria e ganha água. Sua
  projeção vertical ($\Delta\omega$) multiplicada pela vazão de ar seco é a **taxa de
  água evaporada**.
- Se a saída da câmara cai **sobre** a isentálpica pontilhada, a secagem foi ≈
  adiabática (câmara indireta bem isolada). Se fica **acima**, houve aporte extra de
  calor na câmara (superfícies translúcidas); **abaixo**, perdas pelas paredes. Isso
  **não se impõe**: emerge do balanço.
- A distância do ponto de saída à **curva de saturação** é a margem que ficou sem usar:
  saída muito longe da saturação com produto ainda úmido sugere vazão alta ou câmara
  curta; saída colada à saturação indica ar esgotado (bem aproveitado, mas atenção à
  condensação).

A carta é desenhada **na pressão do local**: em altura, as curvas se deslocam e os
mesmos (T, UR) dão outra $\omega$.

## Bulbo úmido e temperatura de orvalho {#bulbo-humedo}

Duas temperaturas auxiliares úteis ao interpretar resultados:

- **Bulbo úmido** $T_{bh}$: a temperatura de equilíbrio de uma superfície molhada
  ventilada — o limite inferior ao qual o ar pode se resfriar por evaporação (e uma cota
  da temperatura do produto durante o período de secagem intensa).
- **Ponto de orvalho** $T_r$: a temperatura à qual o ar, resfriando-se a $\omega$
  constante, satura. Se alguma superfície do secador está abaixo de $T_r$, haverá
  condensação.

---

**Ver também:** [7 · Resultados](?manual=resultados#carta) (onde se traça a carta),
[Física da secagem](?manual=secado) (o lado do produto),
[Técnico · Câmara](?manual=tec-camara) (o balanço que produz os estados).
