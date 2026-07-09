# 1 · Tipologia e configuração da análise

A primeira seção define **qual secador** você vai pré-projetar e **como** ele será
analisado. Tudo o que segue depende dessas duas decisões: a tipologia determina
quais seções se aplicam (uma Caixa não tem coletor externo; uma Grande escala
acrescenta banco, duto mestre e túnel), e o modo de análise determina qual pergunta
o cálculo responde (um dia de projeto? o ano inteiro? uma campanha real?).

Também é aqui que se carregam os **metadados** do projeto (nome, autor, notas), que
depois encabeçam o relatório PDF.

## As três tipologias {#tipologias}

| Tipologia | Escala típica | O que é |
|---|---|---|
| **Caixa** | ~10 kg | Secador direto compacto: a câmara capta o sol pela sua própria cobertura translúcida. Convecção natural. Sem coletor externo nem motor. |
| **Armário** | 0–100 kg | Secador indireto: coletor solar de ar + câmara com bandejas. Com ventilador ou chaminé solar. |
| **Grande escala** | 100 kg – toneladas | Banco de coletores + duto mestre + câmara industrial (lotes ou túnel semicontínuo). |

<!-- esquema: circuito_caja | Circuito de ar do secador tipo Caixa. -->

<!-- esquema: circuito_armario | Circuito de ar do secador tipo Armário. -->

**Cuidado ao mudar de tipologia com um projeto avançado:** passar para **Caixa**
anula o coletor e o motor (não se aplicam), com um aviso prévio. É uma cascata
intencional para manter o projeto coerente.

<!-- profundidad: O que cada tipologia implica no modelo -->
- **Caixa**: a câmara atua como coletor — as **superfícies translúcidas** (teto
  e/ou paredes, com orientação e teto de uma água próprios da câmara) fornecem o
  ganho solar, repartido entre o produto e o ar (ver
  [Técnico · Câmara](?manual=tec-camara#techo-translucido)) e o ar se move por
  tiragem térmica (pode-se acrescentar chaminé solar para reforçá-la).
- **Armário**: a cadeia completa coletor → (auxiliar) → câmara, com a temperatura de
  entrada na câmara dada pela saída do coletor.
- **Grande escala**: além do armário, aparecem a repartição de vazão entre ramais do
  banco, o duto mestre com sua perda e ganho térmico, e os dois subtipos de câmara
  (ver abaixo). A análise passa a ser por **janela de produção**.
<!-- /profundidad -->

## Modo de análise {#modo-analisis}

O modo de análise define as **forçantes** com que se corre o pré-projeto em
[7 · Resultados](?manual=resultados):

- **Diário** — um dia de projeto: ou condições constantes representativas, ou o
  transitório horário de um dia (real ou sintético) escolhido por critério (dia
  limpo, dia médio, etc.).
- **Anual** — o ano completo, mês a mês: cada mês é representado pelo seu **dia
  típico** (média horária do mês) e a produção anual é estimada por lotes. Habilita
  a seção "Operação anual" em [4 · Câmara](?manual=camara#operacion-anual).
- **Janela** — um lapso real [início, fim] com clima horário contínuo: uma semana,
  um mês, uma campanha de colheita. É o modo natural de **Grande escala** (painéis
  de produção) e também está disponível para Caixa/Armário como **multidia real**.

A seção oferece presets de janela (1 semana, 1 mês, campanha) e o critério de
seleção do dia representativo para o modo diário.

## Subtipos de Grande escala {#subtipo}

Com a tipologia Grande escala escolhe-se também o **subtipo de câmara**:

- **Batch (lotes)** — carrega-se a câmara, seca-se a leva completa, descarrega-se e
  repete-se. A produção da janela vem de encadear lotes.
- **Semicontínuo (túnel)** — túnel em **contracorrente** estilo ADITAL: o produto
  avança por zonas enquanto o ar quente entra pela extremidade oposta. A topologia
  do túnel (número de zonas e cadência de avanço) é configurada em
  [4 · Câmara](?manual=camara).

<!-- profundidad: Por que contracorrente -->
No túnel em contracorrente o ar mais quente e seco encontra o produto **quase seco**
(que tolera temperatura e precisa da máxima força motriz), e o ar já umedecido
encontra o produto **fresco** (que ainda evapora muito porque sua atividade de água
é alta). Isso reparte melhor a capacidade de secagem que o fluxo paralelo. O modelo
resolve as N zonas em série com o ar marchando da zona quente à fria — o detalhe
está em [Técnico · Modo industrial](?manual=tec-industrial#semicontinuo).
<!-- /profundidad -->

---

**Ver também:** [Introdução](?manual=introduccion) (o fluxo de trabalho completo),
[2 · Localização](?manual=emplazamiento) (o passo seguinte),
[Técnico · Modo industrial](?manual=tec-industrial) (batch, túnel e duto mestre em
detalhe).
