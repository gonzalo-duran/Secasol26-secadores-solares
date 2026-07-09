# Técnico · Balanço global e resultados

Referência técnica da integração final: como a seção Resultados resolve o sistema completo
de forma acoplada, os três modos de cálculo, o balanço energético, a carta psicrométrica do
processo, as simulações paramétricas e a exportação. O guia de uso está em
[7 · Resultados](?manual=resultados).

## 1. Resultados como fonte de verdade {#fuente-de-verdad}

As seções 1–6 **configuram** o sistema (cada uma escreve no objeto de projeto central). **A
seção Resultados é a que resolve tudo de forma acoplada** e é a **fonte de verdade**: as
prévias das seções intermediárias (botões "Calcular X") usam heurísticas ou modelos
preliminares; o número final, com o laço de Picard completo, sai de Resultados.

**Fluxo conceitual:** configuração (seções 1–6) → projeto central → balanço global acoplado
→ painel + relatório.

## 2. Verificação de coerência {#coherencia}

Antes de calcular verificam-se as **invariantes cruzadas** do projeto: por exemplo, Caixa
não admite coletor externo nem motor e exige ao menos uma face translúcida; auxiliar em
série pós-coletor exige coletor; motor exige câmara; análise anual não se aplica a Caixa. Os
erros são mostrados e bloqueiam o cálculo inconsistente.

Também se fixa a **pressão representativa** do local (média anual do clima se houver;
atmosfera padrão por altitude se não; 101325 Pa de fallback) — um único valor para coletor,
câmara e psicrométricas.

## 3. Três modos de cálculo {#modos}

Conforme o [modo de análise](?manual=tipologia#modo-analisis), o cálculo roteia para um de
três pipelines:

| Modo | Forçantes |
|---|---|
| **Constantes** | condições representativas únicas (T, irradiância, vento, UR) |
| **Transitório** | horizonte horário (dia de projeto / multidia) |
| **Janela** | lapso real [início, fim] com clima horário (grande escala / multidia) |

Os três encadeiam **coletor → auxiliar → câmara** e, se há chaminé, fecham o **laço natural
por Picard** ([Técnico · Motor e chaminé](?manual=tec-chimenea#picard)). A armadura de
forçantes do ar constrói $T_{ent}$, $\omega_{ent}$, $\dot m$, a **irradiância equivalente**
sobre as faces translúcidas da câmara (POA por face com repartição produto/ar —
[Técnico · Câmara](?manual=tec-camara#techo-translucido)) e a **POA sobre o plano do
coletor** ([Radiação solar](?manual=radiacion)).

### Sugestão automática de irradiância (modo Constantes) {#sugerencia}

Para não obrigar o usuário a inventar um valor "representativo", sugerem-se condições a
partir do clima baixado: o **quantil 90 da POA** representativa (transposição Liu-Jordan; em
Caixa, da **irradiância equivalente** sobre as faces translúcidas da câmara) e o quantil 75
da temperatura ambiente. Se não há POA, cai para o q90 de GHI (conservador).

## 4. Balanço energético integrado {#balance-energetico}

O resultado integra o **balanço energético completo**:

$$
E_{total}=E_{solar,util}+E_{auxiliar}+E_{motor},
\qquad
E_{secado}=m_{agua}\,L_v
$$
$$
\mathrm{COP}_{secado}=\frac{m_{agua}\,L_v}{E_{total}},
\qquad
\text{Fração solar}=\frac{E_{solar}}{E_{solar}+E_{auxiliar}}
$$

mais **tempo de secagem**, **massa de produto seco** ($m_{tot}/(1+X_0)$), rendimento de
massa, as saídas de cada subsistema (coletor, auxiliar, câmara, chaminé) e os avisos/erros
acumulados. O painel mostra métricas, um **Sankey** simplificado de energia e, conforme o
modo:

- **Transitório:** trajetórias horárias (temperaturas, umidade do produto, fluxos).
- **Janela (grande escala):** **painel de produção** — kg secos, taxa de regime (kg/dia),
  lenha, e **perfil espacial do túnel** em semicontínuo.
- **Anual:** painel de detalhe mensal se a seção Câmara calculou a operação anual (com as
  quatro eficiências de Augustus Leon: drying, pickup, térmica e total).

## 5. Carta psicrométrica do processo {#carta}

A **carta psicrométrica corrigida por altitude** traça o processo real do ar (implementação
própria, sem biblioteca externa):

$$
\text{Ambiente} \to \text{coletor (sensível, } \omega \text{ cte)}
\to \text{auxiliar (+T, } \omega \text{ cte)}
\to \text{câmara (secagem)} \to \text{saída}
$$

O trecho de câmara é **adiabático ou não adiabático conforme emerge do balanço** (não se
impõe): se a câmara perde calor às paredes, o processo se afasta da isentálpica. O estado
representativo é tomado no **meio-dia solar**. No **túnel semicontínuo** traça-se o **caminho
do ar por zonas** em contracorrente. Como ler a carta está explicado em
[Psicrometria](?manual=psicrometria#carta).

## 6. Simulações paramétricas (varreduras) {#barridos}

As varreduras permitem **comparar projetos** variando um parâmetro (geometria, vazão,
materiais…) e medindo KPIs (tempo de secagem, COP, fração solar, temperatura de saída…):

- Muta-se um campo do projeto pelo seu caminho (ex.
  `colector.unidad.velocidad_diseno_ms`) sobre um clone do projeto (sem re-baixar clima).
- Cada valor despacha o motor correspondente e extrai os KPIs, relatando também os pontos que
  não convergiram.

Serve para responder "e se eu duplicar a área de coletor / mudar a vazão / usar dupla
cobertura?" sem refazer a configuração à mão.

## 7. Exportação {#exportacion}

O projeto completo é exportado em três formatos:

| Formato | O quê | Para quê |
|---|---|---|
| **JSON** | snapshot serializado do projeto + resultados | **reproduzível**: pode ser recarregado e re-rodado idêntico |
| **TXT** | relatório de texto simples | leitura rápida / colar num e-mail |
| **PDF** | relatório com capa institucional, figuras e tabelas | **entregável** para terceiros |

O JSON serializa **cada componente** (coletor, câmara, auxiliar, motor/chaminé) — assim
pode-se versionar um projeto, compartilhá-lo ou reabri-lo.

## 8. Fluxo de trabalho de ponta a ponta {#flujo}

1. **Tipologia** — tipo de secador e modo de análise.
2. **Localização** — lat/lon → download NASA POWER → POA vs GHI.
3. **Coletor** — tipo, materiais, geometria, banco → avaliação gráfica.
4. **Câmara** — geometria, parede, produto, carga, bandejas.
5. **Auxiliar** (opcional).
6. **Motor** ou chaminé → ΔP do sistema.
7. **Resultados** — simulação acoplada completa → painel + carta psicrométrica → exportar
   JSON/TXT/PDF.

O fluxo é **guiado mas flexível**: cada seção escreve no projeto central; pode-se ir e
voltar, e Resultados integra tudo com o laço iterativo.

---

**Ver também:** [7 · Resultados](?manual=resultados) (guia de uso),
[Técnico · Motor e chaminé](?manual=tec-chimenea#picard) (o laço Picard),
[Psicrometria](?manual=psicrometria) (a carta),
[Apêndice · Implementação](?manual=apendice-codigo#resultados),
[Bibliografia](?manual=bibliografia#leon).
