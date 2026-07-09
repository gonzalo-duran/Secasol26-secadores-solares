# Técnico · Modo industrial / Grande escala

Referência técnica da tipologia **Grande escala**: os dois subtipos (batch e
semicontínuo), o banco e o campo de coletores, o duto mestre e a câmara com gradientes de
umidade. A referência física do subtipo semicontínuo é o secador híbrido **ADITAL** de San
Carlos (Salta). O guia de uso da tipologia está em [1 · Tipologia](?manual=tipologia).

## 1. O que é o modo industrial {#subtipos}

A tipologia **Grande escala** tem **dois subtipos de igual hierarquia**:

- **BATCH** — secagem por lotes (cascata de **N=1** zona).
- **SEMICONTÍNUO** — túnel em **contracorrente** estilo ADITAL (**N** zonas em série, ar e
  produto em sentidos opostos).

**Período = janela**: em vez do binário diário/anual, a análise roda sobre um **lapso
real** [início, fim] com clima horário (uma semana, um mês, uma campanha). A janela também
está disponível para Caixa/Armário como multidia real.

O circuito de ar é: **banco de coletores → duto mestre → (auxiliar) → câmara/túnel →
saída**.

## 2. Coletor industrial — banco e campo {#campo}

### 2.1 Banco série/paralelo {#banco}

O banco combina módulos **em série** (o ar se aquece progressivamente, a saída de um é a
entrada do seguinte) e ramais **em paralelo** (repartem a vazão). Cada módulo é resolvido
com o **mesmo solver de coletor** dos Tipos 1–4 ([Técnico · Coletor](?manual=tec-colector)),
hora a hora.

### 2.2 Campo de coletores — repartição real de vazão {#reparto}

Em grande escala a repartição de vazão entre ramais **não se assume uniforme**: resolve-se
a **rede hidráulica** completa, seguindo a metodologia do **ASHRAE Handbook 2017, cap. 21
(Duct Design)**:

- **Atrito por trecho** do tronco: Darcy-Weisbach + Haaland, com a seção local do duto
  (constante ou crescente).
- **Singulares de boca**: $\Delta P = C\,\rho v^2/2$ (campânula de redução + válvula
  borboleta) referidos à seção do ramal.
- **Igualdade de pressão total**: todas as trajetórias (ramal $i$ + tronco desde sua boca
  ao ventilador) veem a **mesma** $\Delta P$. A repartição $\{q_i\}$ é resolvida por
  **ponto fixo amortecido** sobre essa igualdade.

Convenção: a boca 1 é a extremidade longe do ventilador; o tronco é discretizado em N
trechos e o trecho $i$ transporta a vazão acumulada das bocas $1..i$. Cada ramal é
avaliado termicamente **na sua vazão própria** → temperatura de saída por ramal.

## 3. Duto mestre (manifold) {#cano-maestro}

O **duto mestre** é o coletor (manifold) que recolhe o ar de todos os ramais e o leva ao
ventilador/câmara. Tem três modelos de pré-projeto:

### 3.1 Perda de carga com fluxo acumulado {#dp-cano}

A vazão **cresce linearmente** ao longo do duto: $Q(f)=Q_{total}\cdot f$, com $f=0$ na
extremidade longínqua e $f=1$ no ventilador. O atrito é **integrado por trechos** com a
vazão e a seção **locais**:
$$
\Delta P_{fric} = \sum_j f_j\,\frac{dx}{D_{h,j}}\,\frac{\rho\,v_j^2}{2},
\qquad v_j = \frac{Q(f_j)}{A_j}
$$
Os acessórios (campânula de redução + válvula borboleta de um caminho representativo) são
aplicados sobre a pressão dinâmica da extremidade do ventilador:
$\Delta P_{acc}=(K_{campana}+K_{mariposa})\,\rho v_{fin}^2/2$.

**Compensação de seção:** um duto de **seção crescente** mantém a velocidade limitada à
medida que acumula vazão, enquanto um duto pequeno de seção constante dispararia a
velocidade (e o atrito $\propto v^2$) perto do ventilador. O modelo relata a velocidade
máxima ao longo do duto — limitada se a seção compensa a vazão acumulada. A chave do modelo
é usar o **fluxo acumulado** (não a vazão total constante) para que a compensação se
reflita.

### 3.2 Balanço térmico — duas variantes {#dt-cano}

O duto pode estar ao relento. O balanço dá $\Delta T=(Q_{solar}-Q_{perdida})/(\dot m\,c_p)$:

$$
Q_{perdida} = (U_{lados}A_{resto} + U_{sup}A_{sup})\,(T_{aire}-T_{amb}),
\qquad
Q_{solar} = \tau\,\alpha\,A_{sup}\,I_g
$$

com $U=\big(1/h_{int}+R_{ais}+1/h_w\big)^{-1}$ — película interna por convecção forçada
(Dittus-Boelter turbulento, $Nu=3.66$ laminar), condução do isolante (se isolado) e
película externa McAdams.

- **Variante sem ganho solar**: $Q_{solar}=0$ → o ar só **perde** calor; $\Delta T<0$ (≈
  −2,8 °C no caso ADITAL).
- **Variante com ganho solar**: a face superior atua como mini-coletor
  ($Q_{solar}=\tau\alpha A_{sup}I_g$). Se ainda leva **cobertura translúcida**, a cavidade
  de ar acrescenta resistência ($U_{sup}<U_{lados}$, efeito estufa) e o ganho é afetado por
  $\tau$.

**Atenção no pré-projeto:** a absortância solar default (0,90) é de **chapa pintada**; o
**galvanizado nu** precisa de $\alpha\approx0,35$.

### 3.3 Uniformidade de distribuição {#uniformidad}

Critério simples: a repartição é uniforme se a $\Delta P$ do tronco é **pequena frente à**
$\Delta P$ de um ramal: $\text{ratio}=\Delta P_{cano}/\Delta P_{rama}$, uniforme se
$<0,15$.

## 4. Câmara com gradientes de umidade — motor multietapa {#cascada}

Batch e semicontínuo são **o mesmo motor** de cascata com topologia distinta. Reusa intacto
o núcleo físico da câmara (evaporação difusiva + GAB + coeficientes variáveis no tempo —
[Técnico · Câmara](?manual=tec-camara)).

### 4.1 Batch = cascata de N=1 {#batch}

Um único CSTR com uma só passagem de ar. Equivale ao motor de armário mas rodado sobre a
janela de produção, acumulando lotes.

### 4.2 Semicontínuo = N zonas em contracorrente {#semicontinuo}

O túnel tipo ADITAL são **N colunas de carros em série**:

- O **ar** marcha da zona $N{-}1$ (extremidade seca/quente, recebe o ar do coletor+auxiliar)
  rumo à zona $0$ (extremidade fresca/úmida, descarrega ao ambiente).
- O **produto avança em sentido oposto**: entra fresco pela zona $0$ e é descarregado seco
  pela zona $N{-}1$.

**Estado integrado:** $y=[T_0,X_0,T_1,X_1,\dots,T_{N-1},X_{N-1}]$ (2N variáveis). Em cada
avaliação do sistema **marcha-se o ar** $N{-}1\to0$ (N resoluções algébricas
**sequenciais** do mesmo CSTR): para a zona $i$, o ar de entrada é a **saída da zona
$i{+}1$** (a vizinha mais quente). **Não há iteração intra-passo**: o produto está quase
congelado no passo, então o sistema de ar é linear e direto.

**Avanço de colunas:** com cadência fixa, as colunas saltam uma posição (salto discreto do
estado: zona $i \leftarrow$ produto da zona $i{-}1$; zona $0 \leftarrow$ carga fresca; zona
$N{-}1 \rightarrow$ descarga). Entre avanços integra-se um trecho com o integrador de EDOs.

**Secura de saída emergente:** a cadência é **fixa**; **não** é ajustada para alcançar
$X_{objetivo}$. A secura de saída é um **resultado** do sistema, não uma restrição que se
força. $X_{objetivo}$ só serve para **avisar** sub/sobre-secagem. O túnel arranca cheio de
produto fresco; após ~N avanços alcança **regime estacionário** e relata-se o **perfil
espacial** $X(\text{zona})$, $T_{prod}(\text{zona})$, $T_{aire}(\text{zona})$.

## 5. Híbrido com calendário de arranque {#calendario}

O queimador de biomassa opera em **janelas horárias** de manhã/entardecer (independente da
irradiância), não a potência constante, e **acumula lenha**. Detalhe físico em
[Técnico · Aquecimento auxiliar](?manual=tec-auxiliar).

## 6. Orquestração da janela {#orquestacion}

Três camadas: as **forçantes** horárias (coletor forçado hora a hora + ΔT do duto mestre +
auxiliar com calendário), o **despacho** batch↔cascata conforme o subtipo (acumulando
produção: kg de produto seco + taxa de regime kg/dia + lenha), e o **ponto de entrada** que
a seção [7 · Resultados](?manual=resultados) consome para o painel de produção.

## 7. Validação contra ADITAL {#adital}

Um script de validação standalone contrasta a cadeia térmica completa contra dados de campo
do secador ADITAL de San Carlos:

| Check | Esperado | Estado |
|---|---|---|
| Saída do coletor | ~55 / 78 °C | ✓ |
| ΔT duto mestre | −2,8 °C | ✓ |
| Câmara | 57 °C | ✓ |
| Campanha | 5000 kg em ~5 dias | ✓ |

É um **check de ordem de grandeza**, não uma calibração: o Secasol é um pré-projetista
**geral**; ADITAL é referência de dimensões/vazões/temperaturas, não objetivo de ajuste.

---

**Ver também:** [1 · Tipologia](?manual=tipologia) (onde se escolhe o subtipo e a janela),
[Técnico · Câmara](?manual=tec-camara) (o núcleo físico que a cascata reusa),
[Técnico · Motor e perdas de carga](?manual=tec-chimenea),
[Apêndice · Implementação](?manual=apendice-codigo#industrial),
[Bibliografia](?manual=bibliografia#ashrae).
