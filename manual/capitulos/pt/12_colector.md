# 3 · Coletor solar de ar

O coletor é o coração térmico do secador: converte radiação solar em ar quente.
Nesta seção define-se **qual coletor** se usa (tipo, materiais, geometria) e
**quantos** (banco em série/paralelo). O Secasol modela coletores de placa plana de
ar com um modelo físico de balanços por superfície — não uma eficiência tabelada —
de modo que cada decisão construtiva (uma ou duas coberturas, tipo de placa,
espessura de isolante) tem efeito direto e visível na temperatura de saída.

Na tipologia **Caixa** esta seção não se aplica (a caixa capta diretamente pela sua
cobertura); aparece com **Armário** e **Grande escala**.

## Escolher o tipo de coletor {#tipos}

O Secasol oferece quatro topologias que compartilham materiais e critérios
construtivos e diferem em **onde está o absorvedor e por onde circula o ar**:

| Tipo | Absorvedor | Circulação do ar |
|---|---|---|
| **1** | no fundo da caixa | por **cima** do absorvedor (canal único) |
| **2** | à meia altura (dois canais) | por **ambos** os canais (superior + inferior) |
| **3** | à meia altura | pelo canal **inferior**; o superior fica estanque |
| **4** | à meia altura | pelo canal **superior**; o inferior fica estanque |

<!-- esquema: colectores_seccion_transversal | Seção transversal comparativa dos 4 tipos. -->

Como guia rápido: o **Tipo 1** é o mais simples de construir; os tipos com absorvedor
à meia altura aumentam a superfície de troca com o ar, e as variantes com canal
estanque (3 e 4) usam essa cavidade de ar parado como isolamento adicional.

<!-- profundidad: O que muda fisicamente entre os tipos -->
No modelo, cada tipo é uma topologia distinta de balanços de energia:

- No **Tipo 1** o ar troca com a face interna da cobertura e com o absorvedor;
  cobertura e absorvedor se acoplam também por radiação.
- No **Tipo 2** o absorvedor entrega calor por convecção a **dois** fluxos (canal
  superior e inferior), e por radiação à cobertura e ao fundo.
- Nos **Tipos 3 e 4** o canal estanque se comporta como uma **cavidade de convecção
  natural**: a transferência através dele é modelada com a correlação de Hollands
  para cavidades inclinadas mais a radiação entre superfícies. Isso reduz as perdas
  do lado estanque, ao custo de perder essa face como superfície de troca com o
  fluxo.

As equações completas dos quatro balanços estão em
[Técnico · Coletor de placa plana](?manual=tec-colector#balances).
<!-- /profundidad -->

## Materiais do coletor {#materiales}

Cada componente é escolhido de um **catálogo de materiais** com propriedades já
carregadas (transmitância, absortância, emissividade, condutividade, rugosidade):

- **Cobertura** — o envidraçamento superior: policarbonato alveolar, filme de estufa,
  vidro. Interessa sua **transmitância** $\tau$ (quanta radiação deixa passar) e sua
  emissividade infravermelha (quanto reirradia).
- **Placa absorvedora** — a superfície que capta: chapa pintada, chapa ondulada,
  etc. Interessa sua **absortância** $\alpha$ e sua rugosidade (afeta a perda de
  carga).
- **Isolante** — lã de vidro, poliestireno, lã de ovelha…: sua condutividade e
  espessura definem a perda pelo fundo.
- **Fundo** — o fechamento inferior da caixa (chapa, madeira).

O número de **coberturas** pode ser 1 (padrão) ou 2: a dupla cobertura reduz as
perdas para cima ao custo de perder um pouco de transmitância, e convém em climas
frios ou ventosos.

<!-- profundidad: Como se modela a dupla cobertura -->
Com duas coberturas, a condutância para cima deixa de ser a condução simples de uma
lâmina e passa a ser uma **condutância efetiva** em série: condução em cada lâmina +
**convecção natural de Hollands** na cavidade de ar entre coberturas + **radiação
cinza** entre superfícies paralelas. O espaçamento entre coberturas é configurável e
entra no número de Rayleigh da cavidade: se a cavidade é muito fina domina a condução;
se é muito grossa, a convecção natural "curto-circuita" parte do benefício.
<!-- /profundidad -->

## Geometria e condição de projeto {#geometria}

A geometria do módulo se define com **comprimento** (sentido do fluxo), **largura** e
**espaçamento do canal** (a altura por onde circula o ar). Junto com a **velocidade
de projeto** do ar, isso fixa a vazão mássica e o regime de fluxo (laminar, transição
ou turbulento), do qual depende fortemente o coeficiente de convecção interna.

Duas observações práticas:

- Um canal mais baixo aumenta a velocidade (melhor transferência) mas também a
  **perda de carga**, que depois o ventilador ou a tiragem da chaminé paga (ver
  [6 · Motor e chaminé](?manual=motor)).
- A **espessura da placa absorvedora** pode ser configurada mas **não entra no
  balanço térmico**: o modelo assume capacitância térmica de placa desprezível
  (hipótese quase estacionária). É uma decisão consciente do modelo, não um
  esquecimento.

<!-- profundidad: Regime de fluxo e coeficiente convectivo local -->
O coeficiente de convecção interna **não é um escalar único**: é avaliado localmente
nó a nó ao longo do coletor, com propriedades do ar variáveis com a temperatura
($k, \mu, Pr, c_p, \rho$ avaliadas na temperatura de película local). Em cada nó
calcula-se o Reynolds local

$$Re = \frac{G\,D_h}{\mu(T_{film})}, \qquad D_h = \frac{2\,W\,a}{W+a}$$

com $G$ o fluxo mássico por unidade de área e $D_h$ o diâmetro hidráulico do canal
retangular, e seleciona-se automaticamente a correlação de Nusselt adequada
(Shah-London, Heaton, Gnielinski, Sparrow-Liu, Dittus-Boelter, Cengel-Ghajar) com
transições suaves entre regimes. A baixa velocidade ou grande inclinação soma-se a
componente de **empuxo** (convecção mista de Churchill). O detalhe completo, com a
tabela de correlações e suas faixas, está em
[Técnico · Coletor de placa plana](?manual=tec-colector#nusselt).
<!-- /profundidad -->

## Banco de coletores {#banco}

Um só módulo raramente é suficiente: o **banco** replica o módulo **em série** (o ar
sai de um e entra no seguinte, somando comprimento de aquecimento) e **em paralelo**
(vários ramais que repartem a vazão total).

- **Série** eleva a temperatura de saída, com rendimento decrescente: cada módulo
  trabalha com ar mais quente e perde mais. Também multiplica a perda de carga.
- **Paralelo** multiplica a vazão à mesma temperatura de saída.

Em **Grande escala** aparece ainda o **duto mestre**: o coletor (manifold) que
recolhe o ar dos ramais e o leva à câmara, com sua própria perda de carga e seu
balanço térmico (pode perder calor para o ambiente ou ganhar por radiação em sua face
superior). Ver [Técnico · Modo industrial](?manual=tec-industrial#cano-maestro).

## Avaliar o coletor {#evaluar}

O botão **Calcular coletor** roda o modelo com a condição escolhida e mostra
temperatura de saída, potência útil e rendimento. Os gráficos de avaliação **diária**
e **anual** usam o clima baixado em [2 · Localização](?manual=emplazamiento) e
trabalham sempre sobre a irradiância **no plano do coletor** (POA), não sobre a global
horizontal — a diferença é explicada por
[Radiação solar e plano orientado](?manual=radiacion).

Ao ler os resultados convém olhar, além da temperatura de saída:

- o **rendimento** do coletor (cai quando o salto térmico sobre o ambiente cresce — é
  a assinatura de Hottel-Whillier-Bliss);
- os **avisos** de projeto (geometrias fora de faixa, correlação forçada fora de sua
  validade, etc.), que são mostrados antes de calcular;
- a **perda de carga**, que condiciona a seção [6 · Motor e chaminé](?manual=motor).

---

**Ver também:** [Técnico · Coletor de placa plana](?manual=tec-colector) (balanços por
superfície, correlações, solução numérica),
[Radiação solar e plano orientado](?manual=radiacion) (por que POA),
[4 · Câmara de secagem](?manual=camara) (para onde vai o ar quente).
