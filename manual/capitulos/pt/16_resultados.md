# 7 · Resultados do pré-projeto

As seções 1 a 6 **configuram**; Resultados **resolve**. Aqui o Secasol roda o sistema
completo de forma **acoplada** — coletor → auxiliar → câmara, com o laço da chaminé
fechado por iteração se aplicável — e entrega o painel, a carta psicrométrica e os
arquivos de exportação. É a **fonte de verdade** do pré-projeto: os botões "Calcular"
das seções intermediárias são prévias; o número final sai daqui.

## Antes de calcular: coerência e condições {#checklist}

A seção verifica primeiro que o projeto seja **coerente** (por exemplo: Caixa não
admite coletor nem motor; o auxiliar em série exige coletor) e mostra o checklist do
que está configurado. Os erros bloqueiam o cálculo; os avisos não, mas convém lê-los.

No modo **Constantes**, o Secasol **sugere** as condições representativas a partir do
clima baixado — irradiância como o quantil 90 da POA e temperatura como o quantil 75 —
para não obrigá-lo a inventar um número.

## Os três modos de simulação {#modos}

Conforme o [modo de análise](?manual=tipologia#modo-analisis):

- **Constantes** — uma foto em condições representativas: rápido, ideal para iterar o
  projeto.
- **Transitório** — o dia de projeto (ou multidia) hora a hora: trajetórias de
  temperaturas, umidade do produto e fluxos.
- **Janela** — a campanha real: painel de **produção** (kg secos, taxa de regime,
  lenha) e, em túnel semicontínuo, o **perfil espacial por zonas**.

## O painel {#dashboard}

As métricas centrais:

- **Tempo de secagem** — quanto tempo o produto leva para chegar à umidade objetivo
  (ou quanto lhe faltou).
- **COP de secagem** — energia de evaporação obtida por unidade de energia investida:
  $\mathrm{COP}=m_{agua}L_v/E_{total}$.
- **Fração solar** — que parte do calor veio do sol:
  $E_{solar}/(E_{solar}+E_{auxiliar})$.
- **Massa de produto seco** e rendimento de massa.

mais o diagrama **Sankey** do balanço de energia e as saídas de cada subsistema
(temperatura de saída do coletor, estado do ar na câmara, vazão natural da chaminé,
consumo do auxiliar). Os **avisos** acumulados de todos os subsistemas são listados
juntos: são parte do resultado.

## A carta psicrométrica do processo {#carta}

> **Desativada temporariamente (versão 1.4.1).** A carta psicrométrica do processo foi retirada da aba 7 e do relatório PDF enquanto seus resultados são revisados. Voltará numa versão posterior. O restante do cálculo não muda.

A carta traça o **caminho real do ar** sobre o diagrama psicrométrico corrigido por
altitude: ambiente → coletor (aquecimento sensível) → auxiliar (se houver) → câmara
(secagem) → saída. É a radiografia termodinâmica do projeto: de relance vê-se quanto o
coletor aquece, quanta umidade a câmara levanta e que margem resta. Como lê-la, passo a
passo, está em [Psicrometria](?manual=psicrometria#carta).

<!-- profundidad: A adiabaticidade do trecho de câmara -->
Nos livros, a secagem ideal é **adiabática**: o ar se resfria exatamente o que se
umedece, seguindo a isentálpica. No Secasol o trecho de câmara **não se impõe
adiabático**: sai do balanço. Se a câmara perde calor pelas paredes, o ponto de saída
cai abaixo da isentálpica — e esse desvio é informação de projeto (isolar melhor). No
túnel semicontínuo a carta mostra o caminho do ar **zona por zona** em contracorrente.
<!-- /profundidad -->

## Simulações paramétricas (varreduras) {#barridos}

As varreduras respondem "e se…?" sem refazer a configuração: escolhe-se um parâmetro
(velocidade de ar, área de coletor, número de coberturas, inclinação do teto ou azimute
da câmara…), uma faixa de valores, e o Secasol roda o pré-projeto completo para cada
ponto, plotando os KPIs (tempo de secagem, COP, fração solar, temperatura de saída). É
a ferramenta para **comparar projetos** e encontrar rendimentos decrescentes antes de
comprometer dimensões.

## Exportação {#exportar}

Três formatos:

- **JSON** — snapshot completo e **reproduzível** do projeto: pode ser recarregado no
  Secasol e re-rodado idêntico, versionado ou compartilhado com um colega.
- **TXT** — relatório de texto simples para leitura rápida.
- **PDF** — relatório institucional com capa, figuras e tabelas: o entregável.

---

**Ver também:** [Técnico · Balanço global](?manual=tec-resultados) (como se orquestra o
cálculo), [Psicrometria](?manual=psicrometria) (a carta),
[Técnico · Motor e chaminé](?manual=tec-chimenea#picard) (o laço Picard),
[Introdução](?manual=introduccion) (o fluxo de trabalho completo).
