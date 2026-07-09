# Física da secagem — o lado do produto

A [psicrometria](?manual=psicrometria) descreve o ar; este capítulo descreve o
**produto**: como se quantifica sua umidade, por que a água "ligada" custa mais para
sair que a água livre, e como a **isoterma de sorção** governa a velocidade da secagem.
É o fundamento do modelo de câmara ([Técnico · Câmara](?manual=tec-camara#producto)).

## Umidade em base seca {#base-seca}

O Secasol trabalha a umidade do produto em **base seca**:

$$
X = \frac{M_{agua}}{M_{seca}} \quad \left[\frac{\text{kg água}}{\text{kg seco}}\right]
$$

enquanto o uso comercial fala em **base úmida** ($w = M_{agua}/M_{total}$, o "% de
umidade" de um rótulo). A conversão:

$$
X = \frac{w}{1-w}, \qquad w = \frac{X}{1+X}
$$

Um tomate fresco com 94 % de umidade (base úmida) tem $X_0 \approx 15,7$ kg de água por
kg de matéria seca; o desidratado final a 10 % base úmida, $X_{obj} \approx 0,11$. A
base seca é a natural para os balanços porque a massa seca **se conserva** durante o
processo: a massa de produto seco resultante é $M_{total}/(1+X_0)\cdot(1+X_{obj})$.

## Atividade de água {#actividad}

Nem toda a água do produto está igualmente disponível. A **atividade de água** $a_w$
[0–1] mede quão "livre" ela está: é a umidade relativa de equilíbrio do ar em contato
íntimo com o produto.

- Produto muito úmido: $a_w \to 1$ — a água se comporta quase como água livre e evapora
  fácil.
- Produto quase seco: $a_w \ll 1$ — a água restante está adsorvida na matriz sólida e
  custa muito mais para extrair.

$a_w$ importa duplamente: governa a **velocidade de secagem** (ver abaixo) e é o
critério de **conservação** — abaixo de $a_w \approx 0,6$ não crescem microrganismos,
que é o objetivo último da secagem.

## A isoterma de sorção (GAB) {#isotermas}

A relação de equilíbrio entre a umidade do produto $X$ e sua atividade de água $a_w$, a
temperatura dada, é a **isoterma de sorção**. O Secasol usa o modelo **GAB**
(Guggenheim–Anderson–de Boer), o padrão em alimentos:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

com três parâmetros por produto ($X_m$ a monocamada, $C$ e $K$ constantes de sorção) que
vêm no **catálogo de produtos**. O modelo a usa **invertida**: dado o $X$ atual, obtém
$a_w(X)$.

<!-- profundidad: A inversão analítica da GAB -->
Isolar $a_w$ da equação GAB leva a uma **quadrática** em $a_w$:

$$
K\,(1-C)\,a_w^2\;X + \left[(C-2)\,K\,X + X_m\,C\,K\right]a_w + X = 0
\;\;\Rightarrow\;\;
a_w = f(X;\,X_m, C, K)
$$

da qual se toma a raiz física em [0, 1]. Por ser analítica (sem iteração), avalia-se
milhões de vezes dentro do integrador sem custo. Se um produto do catálogo não tem
parâmetros GAB calibrados, o sistema **avisa** que a curva de frenagem é genérica.
<!-- /profundidad -->

## Como a isoterma governa a velocidade de secagem {#velocidad}

O motor de câmara calcula a evaporação de forma **difusiva**:

$$
\dot m_w = K_m\,A_{prod}\,\big(\underbrace{\omega_{sat}(T_{prod})\cdot a_w(X)}_{\omega_{sup}} - \omega_{flujo}\big)
$$

A força motriz é a diferença entre a umidade da **camada de ar colada ao produto**
($\omega_{sup}$) e a do fluxo. E aí trabalha a isoterma: à medida que o produto seca,
$a_w(X)$ **cai**, $\omega_{sup}$ baixa, a força motriz encolhe e a taxa de secagem
**diminui sozinha**.

Assim aparecem os períodos clássicos da secagem **sem nenhuma curva empírica**:

- **Período de taxa ~constante** (produto úmido, $a_w\approx1$): a evaporação é limitada
  pelo ar (temperatura, umidade, velocidade), não pelo produto. O produto se mantém
  perto da temperatura de bulbo úmido.
- **Período de taxa decrescente** (produto secando, $a_w<1$): a matriz retém a água
  restante; a taxa cai e a temperatura do produto sobe rumo à do ar.

A consequência prática: os **últimos décimos de umidade são os mais caros** em tempo e
energia. Secar além do objetivo de conservação desperdiça horas de sol.

## A temperatura do produto {#temperatura}

O produto tem sua própria dinâmica térmica: recebe calor sensível do ar e gasta calor
latente ao evaporar,

$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = h_{conv}A_{prod}(T_{flujo}-T_{prod}) - \dot m_w\,L_v
$$

Enquanto evapora forte, o termo latente o mantém **frio** (perto do bulbo úmido); quando
a secagem se freia, sua temperatura sobe rumo à do ar. Isso importa para a **qualidade**:
a temperatura máxima admissível do produto (cor, nutrientes, caso de ervas e cogumelos)
costuma ser a restrição que limita a temperatura de operação do secador.

---

**Ver também:** [O catálogo de produtos](?manual=catalogo-productos) (os produtos
disponíveis e seus dados), [Psicrometria](?manual=psicrometria) (o lado do ar),
[4 · Câmara](?manual=camara#producto) (onde se configura o produto),
[Técnico · Câmara](?manual=tec-camara#isotermas) (as equações completas do balanço).
