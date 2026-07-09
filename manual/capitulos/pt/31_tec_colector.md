# Técnico · Coletor solar de ar — modelo físico e numérico

Referência técnica do modelo de coletor: as 4 configurações, os balanços de energia por
superfície, o coeficiente convectivo interno local, a solução numérica e as perdas de
carga. O guia de uso está em [3 · Coletor solar](?manual=colector).

## 1. As quatro configurações {#configuraciones}

O Secasol modela **coletores solares de placa plana de ar** (*air heaters*) em quatro
topologias, que compartilham materiais e critérios construtivos e só diferem em **a
localização do absorvedor e a circulação do fluxo**:

| Tipo | Absorvedor | Circulação |
|---|---|---|
| **1** | no fundo da caixa | ar **por cima** do absorvedor (canal único) |
| **2** | à meia altura (dois canais) | fluxo por **ambos** os canais (superior + inferior) |
| **3** | à meia altura | fluxo pelo canal **inferior**; superior estanque |
| **4** | à meia altura | fluxo pelo canal **superior**; inferior estanque |

<!-- esquema: colectores_seccion_transversal | Seção transversal dos 4 tipos. -->

A caixa se constrói em madeira ou dupla chapa galvanizada com isolante intermediário; a
cobertura é de material de alta transmitância (policarbonato alveolar, filme de estufa,
vidro). O absorvedor pode ter largura $W_{abs} \ge W$ (chapa ondulada).

## 2. Hipóteses físicas fundamentais {#hipotesis}

Comuns aos 4 tipos:

1. **Quase estacionário:** despreza-se o acúmulo de calor em todas as superfícies. As
   variações temporais só provêm das condições ambientais (temperatura, irradiância,
   vento) ou da vazão de ar.
2. **Fluxo unidirecional e desenvolvido** em x (sentido do fluxo). Pode ser laminar, em
   transição ou turbulento; natural ou forçado.
3. **Transferência 1D efetiva em x e y**, desprezível em z (largura): superfícies
   homogêneas e isótropas.
4. **Continuidade:** única entrada em $x=0$ (a $T_{amb}$ ou à saída do trecho anterior),
   única saída em $x=L$.
5. **Absorvedor de espessura desprezível** → sem condução interna; ambas as faces a
   $T_{abs}$. (A espessura de placa é exposta na interface mas **não entra no balanço**:
   decisão consciente, capacitância de placa desprezível.)
6. **Parede composta chapa+isolante+chapa** → resistência térmica = a do isolante
   (despreza-se a condução nas chapas).
7. **Perdas laterais** ≪ perdas por cima e por baixo → absorvidas na direção y.
8. **Absortividade da cobertura desprezível** ($\alpha_{cub}\approx 0$, só transmite e
   reemite IR).

**Condições de contorno:**

- Entrada do fluido: $T_f(x{=}0) = T_{entrada}$ (ambiente, ou saída do módulo anterior em
  série).
- Face superior: convecção de vento (McAdams) + radiação ao céu (Swinbank).
- Face inferior: condução pelo isolante + convecção de vento no fundo.
- A "condição inicial" do problema quase estacionário é o **warm-start** do nó prévio
  (não há transitório temporal dentro do coletor).

## 3. Balanços de energia por superfície {#balances}

Notação: $\sigma$ = Stefan-Boltzmann; $h_w$ = convecção de vento; $h_{int}$ = convecção
interna; $\tau_{cub}$, $\alpha_{abs}$ ópticas; $U_{ais}=k_{ais}/e_{ais}$; $T_{cie}$
temperatura de céu; $dA_{cub}=W\,dx$, $dA_{abs}=W_{abs}\,dx$. Todas as temperaturas em
**K**.

### 3.1 Tipo 1 — canal único, absorvedor no fundo {#tipo1}

**Cobertura (face externa):**
$$
h_w(T_{cub,e}-T_{amb}) + \varepsilon_{cub}\sigma(T_{cub,e}^4-T_{cie}^4)
  + U_{cub}(T_{cub,e}-T_{cub,i}) = 0
$$

**Cobertura (face interna):**
$$
U_{cub}(T_{cub,e}-T_{cub,i}) - h_{int}(T_{cub,i}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{cub,i}^4-T_{abs}^4) = 0
$$

**Absorvedor:**
$$
I_g\,\tau_{cub}\,\alpha_{abs}
  - h_{int}(T_{abs}-T_f)
  - \varepsilon_{eff}\,\sigma(T_{abs}^4-T_{cub,i}^4)
  - U_{ais}(T_{abs}-T_{bot}) = 0
$$

**Fundo (corpo):** balanço que isola $T_{bot}$ analiticamente:
$$
U_{ais}(T_{abs}-T_{bot}) = h_w(T_{bot}-T_{amb})
\;\Rightarrow\;
T_{bot}=\frac{U_{ais}T_{abs}+h_w T_{amb}}{U_{ais}+h_w}
$$

**Fluido (EDO em x)** — o ar ganha da cobertura interna e do absorvedor:
$$
\dot m\,c_p\,\frac{dT_f}{dx}
  = h_{int}\,W\,(T_{cub,i}-T_f) + h_{int}\,W_{abs}\,(T_{abs}-T_f)
$$

### 3.2 Tipo 2 — dois canais ativos {#tipo2}

Aparece a face interna do fundo $T_{int}$ e um segundo canal com seu próprio $h_{int,2}$,
$\dot m_2$. O absorvedor troca com **ambos** os fluxos por convecção, com a cobertura e
com o fundo por radiação:
$$
I_g\tau_{cub}\alpha_{abs}
= \varepsilon_{eff}\sigma(T_{abs}^4-T_{cub,i}^4)
 + h_{int,1}(T_{abs}-T_{cs})
 + h_{int,2}(T_{abs}-T_{ci})
 + \varepsilon_{eff}\sigma(T_{abs}^4-T_{int}^4)
$$

EDOs de fluido no canal superior e inferior (análogas, cada uma com seu $\dot m$):
$$
\dot m_1 c_p \frac{dT_{cs}}{dx}=h_{int,1}W(T_{cub,i}-T_{cs})+h_{int,1}W_{abs}(T_{abs}-T_{cs})
$$
$$
\dot m_2 c_p \frac{dT_{ci}}{dx}=h_{int,2}W_{abs}(T_{abs}-T_{ci})+h_{int,2}W(T_{int}-T_{ci})
$$

Fundo: $U_{ais}(T_{int}-T_{bot})=h_w(T_{bot}-T_{amb})$.

### 3.3 Tipo 3 — só canal inferior ativo {#tipo3}

O canal superior é um **recinto estanque** (cavidade de ar): a transferência
cobertura↔absorvedor passa de convecção forçada a **convecção natural em cavidade
(Hollands) + radiação**. O balanço do fluido só existe no canal inferior (idêntico ao do
Tipo 2 inferior). O absorvedor perde ao canal superior unicamente por convecção natural e
radiação.

### 3.4 Tipo 4 — só canal superior ativo {#tipo4}

Simétrico ao Tipo 3: o canal **inferior** é a cavidade estanque; o fluido circula pelo
canal superior (EDO idêntica ao Tipo 2 superior). A cavidade inferior aporta acoplamento
absorvedor↔fundo por convecção natural + radiação.

### Dupla cobertura (todos os tipos) {#doble-cubierta}

Com duas coberturas, a condutância da cobertura $U_{cub}$ deixa de ser $k_{cub}/e_{cub}$ e
passa a ser uma **condutância efetiva** que combina condução em cada lâmina + **convecção
natural de Hollands** na cavidade de ar entre coberturas + **radiação cinza** entre
superfícies paralelas.

## 4. Coeficiente convectivo interno local {#nusselt}

O coeficiente convectivo interno **não é um escalar único** a temperatura fixa: é
avaliado **localmente, nó a nó**.

### 4.1 Receita local por nó {#receta-local}

Para cada nó x:

1. **Propriedades do ar variáveis com T** avaliadas na temperatura de película
   $T_{film}=(T_f+T_{pared})/2$: $k(T),\mu(T),Pr(T),c_p(T),\rho(T,P)$.
2. **Reynolds local** com o fluxo mássico por unidade de área $G=\dot m/A_{sec}$
   (constante) e a viscosidade local: $Re = G\,D_h/\mu(T_{film})$. O diâmetro hidráulico
   de um canal retangular é $D_h = 2\,W\,a/(W+a)$ com $a$ a altura do canal.
3. **Nusselt local misto** = forçado (com entrada térmica + blending contínuo de regime
   em $Re=2300$ e $Re=10000$) combinado com **empuxo**: Rayleigh local com a componente
   de gravidade ao longo do canal,
   $Ra = g\sin\beta\,\beta_{exp}\,\Delta T\,D_h^3/(\nu\,\alpha)$, via a correlação de
   **convecção mista de Churchill**.
4. $h_{int}(x) = Nu(x)\,k(T_{film})/D_h$.

O catálogo de correlações fornece tanto as correlações **médias** sobre $L$ (seleção
automática, usadas em prévias e validação) quanto as versões **locais** nó a nó, usadas
pelos solvers. As locais são construídas para que sua **média sobre $0\!\to\!L$
reproduza exatamente** a correlação média equivalente (Heaton em laminar, Cengel em
turbulento — ver §4.4).

### 4.2 Correlações de fluxo forçado {#correlaciones-forzado}

Regime pelo número de Reynolds: **laminar** $Re<2300$, **transição**
$2300\le Re\le 10^4$, **turbulento** $Re>10^4$. A escolha dentro de cada regime depende
ainda de $L/D_h$ (efeitos de entrada térmica) e de quantas paredes do canal aquecem o
fluxo (uma parede → Tipos 1, 3, 4; duas paredes → Tipo 2).

| Correlação | Expressão de Nu | Regime / faixa | Paredes |
|---|---|---|---|
| **Shah & London (1978)** | $Nu = 5.385$ | Laminar desenvolvido, $Re<2300$, $L/D_h\ge 50$ | 1 parede (caso H2) |
| **Shah & London simétrico** | $Nu = 8.235$ | Laminar desenvolvido, $Re<2300$, $L/D_h\ge 50$ (Tipo 2) | 2 paredes (caso H1) |
| **Heaton, Reynolds & Kays (1964)** | $Nu = 5.385\,(1+0.0668\,Gz^{2/3})$, $\;Gz=Re\,Pr\,D_h/L$ | Laminar em **entrada térmica**, $Re<2300$, $L/D_h<50$, $Pr>0.5$ | 1 parede |
| **Gnielinski (1976)** | $Nu = \dfrac{(f/8)(Re-1000)Pr}{1+12.7\sqrt{f/8}\,(Pr^{2/3}-1)}$, $\;f=(0.790\ln Re-1.64)^{-2}$ | **Transição**, $2300\le Re\le 10^4$, $0.5<Pr<2000$ | (indistinta) |
| **Sparrow & Liu (1979)** | $Nu = 0.0158\,Re^{0.8}$ | Turbulento, $Re>10^4$; default de **uma parede quente** (Tipos 1, 3, 4) | 1 parede |
| **Dittus-Boelter (1930)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}$ (exp. 0.4: fluido aquecido) | Turbulento, $Re>10^4$, $0.6<Pr<160$, $L/D_h>10$; default de **duas paredes** (Tipo 2) | 2 paredes |
| **Cengel & Ghajar (2014)** | $Nu = 0.023\,Re^{0.8}\,Pr^{0.4}\,[1+(D_h/L)^{0.7}]$ | Turbulento com **entrada térmica**, $Re>10^4$, $L/D_h<10$; converge a Dittus-Boelter para $L/D_h>60$ | (indistinta) |

### 4.3 Convecção natural e mista {#correlaciones-natural}

Aparece em dois contextos: (a) as **cavidades estanques** e a **cavidade de dupla
cobertura** (Tipos 3/4 e dupla cobertura), e (b) a componente de **empuxo** que se soma ao
forçado no canal ativo a baixa velocidade ou grande inclinação.

| Correlação | Expressão de Nu | Faixa de aplicação |
|---|---|---|
| **Hollands et al. (1976)** — cavidade inclinada | $Nu = 1 + 1.44\big[1-\tfrac{1708}{Ra\cos\theta}\big]^{+}\!\big[1-\tfrac{1708\sin(1.8\theta)^{1.6}}{Ra\cos\theta}\big] + \big[(\tfrac{Ra\cos\theta}{5830})^{1/3}-1\big]^{+}$ | Cavidade, $\theta\in[0°,75°]$, $Ra\lesssim 10^{8}$. Para $Ra\cos\theta<1708$: $Nu=1$ (condução pura). $[x]^{+}=\max(0,x)$ |
| **Churchill-Chu** (componente natural do canal) | $Nu_{nat} = \dfrac{0.670\,Ra^{1/4}}{[1+(0.492/Pr)^{9/16}]^{4/9}}$ | Aporte de **empuxo** local (placa, laminar); $Ra$ com a componente $g\sin\beta$. $Nu_{nat}\to0$ quando $Ra\to0$ |
| **Convecção mista de Churchill** | $Nu = (Nu_{forz}^{3} + Nu_{nat}^{3})^{1/3}$ | Empuxo **assistido**. Reduz ao forçado se $Ra\to0$; domina o natural se $Gr/Re^{2}\gg1$ |

### 4.4 Seleção automática e blending de regime {#seleccion}

Com seleção automática, a lógica é:

- **$Re<2300$ (laminar):** Heaton se $L/D_h<50$ (entrada térmica), senão Shah & London —
  simétrico para duas paredes (Tipo 2), assimétrico para uma parede.
- **$2300\le Re\le 10^4$ (transição):** Gnielinski.
- **$Re>10^4$ (turbulento):** Cengel se $L/D_h<10$ (entrada pronunciada); senão Sparrow &
  Liu para uma parede ou Dittus-Boelter para duas paredes.

Se o usuário força uma correlação fora de sua faixa de $Re$ ou de tipo de parede, emite-se
um aviso sem abortar o cálculo.

Nas versões **locais**, a comutação entre regimes não é um salto: há um **blending
contínuo C¹** em bandas de $\pm400$ em torno de $Re=2300$ e $Re=10^4$, para que $Nu(x)$
não salte se o $Re$ local cruza um limiar ao longo do coletor ao variar $\mu(T)$. Os
realces de entrada local estão calibrados para que sua integral reproduza as correlações
médias: laminar $Nu_x = Nu_\infty(1+0.02227\,Gz_x^{2/3})$ tem por média Heaton
($3\times0.02227=0.0668$); turbulento $(1+0.3\,(D_h/x)^{0.7})$ tem por média Cengel
($3.333\times0.3=1$).

### 4.5 Vazão mássica {#caudal}

A vazão mássica é fixada com $\rho(T_{entrada})$ — a vazão **volumétrica** de projeto é
estabelecida na entrada:
$$Q = n_{par}\,v_{dis}\,W\,a, \qquad \dot m = \rho(T_{ent})\,Q$$

## 5. Solução numérica {#numerica}

O modelo é **quase estacionário acoplado**: uma EDO do fluido em x mais um sistema
algébrico não linear de superfícies em cada nó.

### 5.1 Esquema de dois níveis {#dos-niveles}

- **Nível externo — integração da EDO do fluido** $dT_f/dx$ com
  `scipy.integrate.solve_ivp`, método **RK45**, tolerâncias $10^{-6}$, sobre
  $x\in[0, L_{total}]$ com $L_{total}=L_{unidad}\cdot n_{serie}$ e passo máximo limitado
  para garantir uma discretização mínima.
- **Nível interno — sistema algébrico por nó** com `scipy.optimize.fsolve`. No Tipo 1 as
  incógnitas são **3**: $[T_{cub,e}, T_{cub,i}, T_{abs}]$, com $T_{bot}$ isolada
  analiticamente; nos Tipos 2–4 acrescenta-se $T_{int}$ e/ou acoplamentos de cavidade. O
  resíduo é o vetor de balanços de superfície; o solver busca sua raiz.

### 5.2 Warm-start {#warm-start}

Cada chamada ao solver de nó arranca da solução do **nó prévio**. Isso acelera a
convergência e dá robustez. A temperatura de parede do warm-start alimenta por sua vez o
$T_{film}$ e o Rayleigh do $h_{int}$ local (acoplamento convecção–empuxo).

### 5.3 Discretização {#discretizacion}

O coletor é discretizado **na coordenada axial x** (sentido do fluxo): o integrador
adaptativo coloca os nós, com um piso de nós mínimo. Em cada nó resolve-se o plano
transversal completo (cobertura, absorvedor, fundo, fluido). Não se discretiza em y nem
em z (hipótese 1D). Num banco em série, a saída de um módulo é a condição de entrada do
seguinte.

### 5.4 Convergência e diagnóstico {#convergencia}

Se a integração não converge, o cálculo falha explicitamente. Se o sistema de um nó não
converge registra-se um aviso mas a integração continua com a solução aproximada. O
resultado leva um indicador de convergência.

## 6. Modularidade {#modularidad}

A modularidade opera em **três níveis**:

1. **Seções** — o projeto se monta seção a seção; a física de cada uma vive isolada da
   interface.
2. **Componentes** — o coletor escolhe tipo 1–4: mesma interface de cálculo, topologia de
   balanços distinta. O núcleo do $h_{int}$ local é **reusado** entre tipos.
3. **Subcomponentes** — cobertura, placa, isolante e fundo são escolhidos de **catálogos
   de materiais** e validados ao construir o modelo de dados. Trocar um material é trocar
   uma entrada do catálogo, sem tocar na física. A geometria se separa em módulo unitário
   e banco (série/paralelo).

## 7. Perdas de carga no coletor {#perdidas}

A perda de carga por atrito do canal é calculada com **Darcy-Weisbach** e o **fator de
atrito de Haaland (1983)** (aproximação explícita de Colebrook-White, erro < 2 %):

$$
\Delta P = f\,\frac{L_{total}}{D_h}\,\frac{\rho\,v^2}{2},
\qquad
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
$$

com $\varepsilon$ a **rugosidade real** da placa absorvedora (do catálogo; default
conservador $5\times10^{-5}$ m de chapa pintada). Regras por tipo:

- **Tipo 1:** canal único (altura do canal).
- **Tipo 2:** dois canais em paralelo → $\Delta P = \max(\Delta P_{cs}, \Delta P_{ci})$.
- **Tipo 3:** canal inferior ativo.
- **Tipo 4:** canal superior ativo.

Em **banco**: série → $\Delta P$ escala com o comprimento total; paralelo → $\Delta P$ de
um ramal. Essa $\Delta P$ alimenta o dimensionamento do ventilador (forçada) ou o laço de
tiragem (natural) — ver
[Técnico · Motor, chaminé e perdas de carga](?manual=tec-chimenea).

---

**Ver também:** [3 · Coletor solar](?manual=colector) (guia de uso),
[Radiação solar e plano orientado](?manual=radiacion) (o coletor recebe POA, não GHI),
[Apêndice · Implementação](?manual=apendice-codigo#colector),
[Bibliografia](?manual=bibliografia#duffie-beckman).
