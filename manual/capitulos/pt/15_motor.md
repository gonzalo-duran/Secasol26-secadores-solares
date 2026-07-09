# 6 · Motor, ventilador e chaminé solar

Algo tem que mover o ar através do coletor, da câmara e dos dutos. Há dois caminhos:
**convecção forçada** (um ventilador com motor elétrico — mais controle, mais vazão,
consome energia) ou **convecção natural** (uma chaminé solar que induz tiragem térmica
— sem eletricidade, vazão menor e variável com o sol). Esta seção dimensiona um ou
outro a partir da **perda de carga** de todo o circuito.

## Escolher o acionamento {#eleccion}

Regras práticas:

- **Forçada**: necessária com leitos grossos ou fluxo vertical (muita perda de carga),
  bancos de coletores grandes, ou quando o processo exige vazão estável. É a opção
  segura em escala industrial.
- **Natural**: atraente onde não há rede elétrica ou se busca custo operacional zero.
  Exige um circuito hidraulicamente "suave" (perdas baixas) e aceita que a vazão siga o
  sol: à noite não há tiragem.

Com o motor desligado, a seção oferece a **chaminé solar**; são mutuamente exclusivos.

## Motor / ventilador {#motor}

Escolhe-se o tipo (axial/centrífugo), a vazão de projeto e os rendimentos. Com a perda
de carga total do sistema, o Secasol calcula a cascata de potências:

$$
P_{hid}=Q\,\Delta P
\;\to\; P_{eje}=P_{hid}/\eta_{vent}
\;\to\; P_{elec}=P_{eje}/\eta_{motor}
\;\to\; P_{inst}=P_{elec}\cdot FS
$$

e a corrente nominal estimada. Ordem de grandeza saudável para um armário de ~50 kg:
**50–100 W elétricos** (um exaustor comercial de 900 m³/h ronda os 76 W). Se o número
der muito acima, o circuito tem perda de carga demais — revisar leito, velocidades e
dutos antes de aumentar o motor.

## Chaminé solar {#chimenea}

A chaminé gera **tiragem térmica**: o ar quente do seu interior pesa menos que o
ambiente e "flutua", aspirando ar através do secador:

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim})
$$

A maior **altura** e maior **temperatura** interior, mais tiragem. A vazão resultante
**não se assume: resolve-se** — é o ponto onde a tiragem disponível iguala a
resistência do circuito. À noite ($T_{chim}\le T_{amb}$) a tiragem é nula e a vazão
zero: a secagem natural é intrinsecamente diurna.

<!-- profundidad: O acoplamento coletor–chaminé (laço Picard) -->
Há um acoplamento sutil: a tiragem depende da temperatura da chaminé, que depende da
saída do coletor, que depende da vazão… que depende da tiragem. O Secasol fecha esse
laço por **iteração de ponto fixo (Picard)**: parte de uma estimativa, roda o coletor,
recalcula a vazão natural e repete até convergir (tanto no modo constantes quanto hora
a hora no transitório). Por isso o botão "Calcular chaminé" desta seção dá um número
**preliminar** com uma heurística de temperatura, e o número final — com o laço
completo — sai de [7 · Resultados](?manual=resultados). O detalhe está em
[Técnico · Motor e chaminé](?manual=tec-chimenea#picard).
<!-- /profundidad -->

## Exaustor eólico {#extractor}

A chaminé pode levar no topo um **exaustor eólico** (turbina "chapéu chinês"): o vento
a faz girar e gera uma depressão adicional que ajuda a tiragem, ao custo de uma pequena
obstrução do fluxo. O vento do clima (medido a 10 m) é corrigido à altura real do topo
por perfil logarítmico. É um **acessório da chaminé**, não um tipo de motor: soma seu
termo motriz ao balanço da tiragem.

## Perdas de carga do sistema {#dp}

A seção estima e detalha a $\Delta P$ total: coletor (canal), câmara (bandejas/leito
conforme a direção de fluxo), dutos e singulares (curvas, entradas, saídas) e — em
Grande escala — o **duto mestre**. Esse detalhamento é a ferramenta de diagnóstico: se
um trecho domina, ali está a oportunidade de projeto (aumentar o canal, baixar a
velocidade, repartir o leito).

---

**Ver também:** [Técnico · Motor, chaminé e perdas de carga](?manual=tec-chimenea)
(todas as equações por trecho), [3 · Coletor](?manual=colector#geometria) e
[4 · Câmara](?manual=camara#bandejas) (onde se origina a perda de carga),
[7 · Resultados](?manual=resultados) (o laço completo).
