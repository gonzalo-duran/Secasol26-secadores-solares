# O catálogo de produtos

A [física da secagem](?manual=secado) explica *como* um produto seca; este capítulo
descreve *quais* produtos o Secasol traz, como foram escolhidos, com que dados estão
carregados e o que significa cada campo do catálogo. É a contraparte aplicada do
capítulo de física: lá estão as equações, aqui estão os tomates, as maçãs e a alfarroba
com seus números.

O catálogo vive em `catalogo/productos/*.yaml` e é escolhido em
[4 · Câmara](?manual=camara#producto).

## Como os produtos foram selecionados {#seleccion}

O critério não foi "os produtos mais secados do mundo" e sim **relevância para as
regiões onde o Secasol será usado** — o NOA, Cuyo, o Litoral argentinos — mais alguns
produtos nativos de valor cultural e econômico:

- **Hortaliças** de ampla disponibilidade regional (tomate, batata da Puna, cebola de
  Cuyo, pimentão para o pimentão salteño).
- **Frutas** dos cinturões frutícolas (maçã do Alto Valle, pêssego, ameixa mendocina) e
  um **tubérculo andino**, o yacón, de produção tradicional em Jujuy e Salta.
- **Folhas aromáticas** de exportação (orégano do NOA, erva-mate do Litoral).
- Produtos **nativos e identitários** como a **alfarroba** (*algarroba*: farinha,
  patay, arrope), com literatura argentina disponível incluindo trabalho do próprio
  INENCO.

Cada produto foi carregado a partir de **literatura científica publicada** (papers de
cinética e isotermas, referenciados no catálogo e na
[bibliografia](?manual=bibliografia#productos)); onde não havia dados diretos,
estimou-se **por analogia** com um produto morfologicamente parecido, e isso é declarado
explicitamente (ver [Casos que pedem cuidado](?manual=catalogo-productos#cuidados)).

## Os produtos disponíveis {#disponibles}

Hoje o catálogo traz **19 produtos** em 5 categorias. A umidade inicial típica está em
base seca (kg de água por kg de matéria seca — ver
[base seca](?manual=secado#base-seca)); o estado GAB indica se a isoterma de sorção está
calibrada ou pendente (ver [calibração](?manual=catalogo-productos#calibracion)).

| Produto | Categoria | X₀ típico (kg/kg ms) | GAB |
|---|---|---|---|
| Tomate | Hortaliça | 15,7 (~94 % bu) | pendente |
| Batata | Hortaliça | 4,5 | ✓ calibrado |
| Cebola | Hortaliça | 8,1 | pendente |
| Pimentão vermelho | Hortaliça | 10,7 | ✓ calibrado |
| Cenoura ralada | Hortaliça | 9,0 | pendente |
| Salsinha | Hortaliça | 5,7 | pendente |
| Aipo | Hortaliça | 22,2 (~96 % bu) | pendente |
| Mandioca | Hortaliça | 1,9 (~65 % bu) | pendente |
| Pimenta vermelha | Hortaliça | 3,25 | pendente |
| Maçã | Fruta | 4,6 | ✓ calibrado |
| Pêssego | Fruta | 6,3 | pendente |
| Yacón | Fruta | 9,0 | ✓ calibrado |
| Romã | Fruta | 2,72 | pendente |
| Ameixa | Fruta | 9,86 | pendente |
| Erva-mate | Folha aromática | 2,3 | pendente |
| Orégano | Folha aromática | 5,7 | pendente |
| Coca | Folha aromática | 1,3 | pendente |
| Charque bovino | Carne | 3,0 | pendente |
| Alfarroba | Legume/fruto | 0,25 (~20 % bu) | pendente |

Os X₀ são valores **típicos de referência**; o produto real varia com a variedade, a
maturação e o corte, e por isso em [4 · Câmara](?manual=camara) a umidade inicial é um
dado que você carrega (o catálogo apenas a sugere).

## Umidade inicial e final {#humedades}

Dois números definem o trabalho de secagem de uma leva:

- **Umidade inicial X₀** — quanta água o produto fresco traz. É alta em hortaliças e
  frutas suculentas (tomate ~15,7, aipo ~22) e baixa em produtos já parcialmente secos
  ou lenhosos (alfarroba ~0,25, mandioca ~1,9).
- **Umidade final ou objetivo X_obj** — aonde se quer chegar. Fixa-a o **critério de
  conservação**: abaixo de uma atividade de água de ~0,6 não crescem microrganismos
  ([física da secagem](?manual=secado#actividad)). O catálogo traz, como referência, a
  **umidade de equilíbrio com ar seco** de cada produto (o X mínimo alcançável com o ar
  daquele clima).

Ambas vão em **base seca**; a conversão a partir do "% de umidade" comercial (base
úmida) está em [física da secagem](?manual=secado#base-seca). Lembre que os últimos
décimos de umidade são os mais caros em tempo e energia: fixar um X_obj mais exigente
que o necessário desperdiça horas de sol.

## O que cada produto define no catálogo {#campos}

Cada entrada do catálogo tem:

- **Descrição** — espécie, variedade de referência, região de produção e notas de
  qualidade (sensibilidade ao escurecimento, à temperatura, etc.).
- **Propriedades básicas** — densidade aparente, calor específico da matéria seca,
  umidade inicial típica e umidade de equilíbrio, cada uma com sua **qualidade de dado**
  (ALTA / MÉDIA / BAIXA) e sua fonte.
- **Isoterma de sorção GAB** — os parâmetros $X_m, C, K$ que governam a velocidade de
  secagem (ver [física da secagem](?manual=secado#isotermas)). É **o dado que o motor
  realmente usa**.
- Metadados de operação: **categoria**, **fotossensibilidade** (se convém câmara opaca
  em vez de translúcida) e `tipo_secado`.

<!-- profundidad: As cinéticas de camada fina são vestigiais -->
O catálogo ainda guarda, para muitos produtos, parâmetros de **cinética de camada fina**
(curvas de razão de umidade MR(t) tipo Page ou Midilli, com sua constante $k$ e expoente
$n$). **O motor já não os usa para calcular**: o antigo avaliador de camada fina foi
substituído pelo balanço acoplado calor-massa, onde a curva de secagem *emerge* da
difusão governada pela isoterma GAB, não de um ajuste empírico
([Técnico · Câmara](?manual=tec-camara#motor-unico)).

Por que seguem ali, então? Esses blocos `capa_fina:` cumprem hoje uma única função:
**filtram quais produtos aparecem no seletor** da seção Câmara. São metadado de
disponibilidade, não parâmetros de cálculo. Ao ler uma ficha do catálogo, o número que
importa para o resultado é a **isoterma GAB**, não a cinética de camada fina.
<!-- /profundidad -->

## Estado de calibração {#calibracion}

O catálogo é **rico em estrutura mas está meio populado**, e convém saber disso antes de
confiar num número:

- **4 de 19 produtos têm a isoterma GAB calibrada** com dados publicados: **maçã,
  batata, yacón e pimentão vermelho**. Neles, a curva de secagem que o modelo produz se
  apoia numa isoterma real.
- Os **15 restantes têm a isoterma pendente** (marcada com parâmetros nulos e o DOI do
  paper a carregar). Com eles, o modelo usa uma isoterma genérica e **o sistema emite um
  aviso** avisando que a frenagem da secagem não está calibrada para esse produto.

Isso não invalida o pré-projeto com um produto pendente — serve para dimensionar em
ordem de grandeza — mas é um dado honesto: um resultado sobre maçã pesa mais que um sobre
ameixa, e o app diz isso.

## Casos que pedem cuidado {#cuidados}

- **Estimados por analogia** — a **coca** herda parâmetros da erva-mate (folha de
  arbusto de estrutura similar) por escassez de literatura, e o **aipo** os da salsinha.
  O próprio catálogo pede usá-los *com precaução*.
- **Fotossensíveis** — orégano, erva-mate, coca, pimentão vermelho, pimenta vermelha,
  salsinha e aipo degradam cor ou óleos essenciais com luz UV e calor excessivo; para
  eles convém **câmara opaca**, não teto translúcido ([4 · Câmara](?manual=camara#techo)).
- **Geometria não padrão** — a **cenoura ralada** tem uma espessura efetiva muito menor
  que as fatias dos ensaios de laboratório: seus parâmetros são apenas orientativos.
- **Charque** — o sal modifica fortemente a isoterma; os parâmetros devem corresponder ao
  nível de salga usado.

## Adicionar ou calibrar um produto {#agregar}

O catálogo é pensado para crescer. Para somar um produto novo ou completar a calibração
de um pendente:

1. Buscar na literatura a **isoterma de sorção** (parâmetros GAB) e as propriedades
   básicas; o repositório mantém um **índice bibliográfico por produto** como ponto de
   partida.
2. Carregar os valores no YAML seguindo o **modelo de referência do catálogo**, com sua
   qualidade de dado e sua fonte.
3. O app valida a estrutura ao iniciar; se falta a isoterma, o produto ainda aparece mas
   **avisa** que usa parâmetros genéricos.

O objetivo de longo prazo é que cada produto de interesse regional tenha sua isoterma
calibrada com dados publicados — é uma das linhas de trabalho abertas do projeto.

---

**Ver também:** [Física da secagem](?manual=secado) (a teoria por trás desses dados),
[4 · Câmara de secagem](?manual=camara#producto) (onde se escolhe o produto e se carregam
X₀ e X_obj), [Bibliografia](?manual=bibliografia#productos) (as fontes dos parâmetros).
