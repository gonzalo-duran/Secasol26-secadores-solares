# 4 · Câmara de secagem

A câmara é onde ocorre a secagem: o ar quente do coletor (ou do auxiliar) passa pelas
bandejas de produto, entrega-lhe calor e leva embora a umidade. Nesta seção define-se
a **geometria** da câmara, sua **construção** (paredes, teto), as **bandejas**, o
**produto** e sua **carga**. O motor físico que a resolve é um balanço acoplado de
calor e massa: o ar se resfria e se umedece ao secar, e a velocidade de secagem
"emerge" da física — não de uma curva empírica.

<!-- esquema: camara_dimensiones | Geometria da câmara com suas cotas. -->

## Geometria {#geometria}

Comprimento, largura e altura definem o volume e — junto com o teto — o **envelope**
por onde a câmara perde calor para o ambiente. O comprimento no sentido do fluxo é
ainda o comprimento característico da transferência ar→produto.

## Orientação e teto de uma água {#orientacion}

A câmara tem **orientação própria**, independente do banco de coletores: a
**inclinação do teto** (teto de uma água), o **azimute da câmara** (para onde "olha",
com 0° = Norte na entrada da interface) e a **face de queda** do teto. A altura da
geometria é a **altura média** da caixa: inclinar o teto não muda nem o volume nem a
seção de passagem do ar.

Isso importa porque cada face translúcida capta radiação segundo sua própria
inclinação e orientação (transposição ao plano de cada face — ver
[Radiação solar e plano orientado](?manual=radiacion)). Na tipologia **Caixa** a
câmara **é** o coletor: por isso em [2 · Localização](?manual=emplazamiento) não
aparece a orientação do coletor e o plano captador se define aqui.

## Paredes {#pared}

A parede pode ser **simples** (um material com sua espessura) ou **composta** (camadas
em série: chapa + isolante + chapa, madeira + poliestireno, etc.). O modelo agrega as
resistências das camadas e calcula a perda $Q_{pared}=U\,A\,(T_{flujo}-T_{amb})$, onde
$U$ combina a convecção interior, a condução das camadas e o vento exterior.

Na prática: o isolante manda. Duplicar a espessura de isolante baixa as perdas quase à
metade; trocar a chapa exterior quase não muda nada.

## Superfícies translúcidas {#techo}

Opcionalmente o teto **e até as quatro paredes** (frente, trás, laterais) podem ser
translúcidos (policarbonato alveolar; mesmo material e espessura para todas as faces):
fornecem **ganho solar direto** — é o que converte uma Caixa em secador — mas também
**perdem mais calor** que uma face opaca isolada. O modelo captura os dois efeitos,
com a espessura do alveolar como parâmetro.

A radiação que cada face transmite se **reparte**: uma fração incide diretamente sobre
o produto e o resto é absorvido pelas superfícies internas opacas e aquece o ar — o
**efeito estufa** de uma caixa envidraçada. A seção mostra uma prévia da área, da
inclinação e da orientação de cada face ativa. As equações da repartição estão em
[Técnico · Câmara](?manual=tec-camara#techo-translucido).

## Bandejas e direção do fluxo {#bandejas}

O número de bandejas e suas dimensões fixam a **área de contato** ar–produto. A
**direção do fluxo** é uma decisão de projeto importante:

- **Horizontal** (o ar passa *sobre* as bandejas): hidraulicamente suave,
  transferência moderada.
- **Vertical ascendente** (o ar *atravessa* o leito): máximo contato e secagem mais
  uniforme, mas a perda de carga do leito cresce muito — paga-a o ventilador ou a
  tiragem da chaminé ([6 · Motor](?manual=motor)).

<!-- profundidad: A perda de carga do leito (Ergun) -->
Em fluxo vertical, a queda de pressão do leito empacotado é calculada com a equação de
**Ergun**, que soma um termo viscoso (dominante a baixa velocidade) e um inercial:

$$
\frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
$$

com $\varepsilon$ a porosidade do leito, $d_p$ o diâmetro de partícula e $\Phi_s$ a
esfericidade. Esses parâmetros vêm do catálogo do produto ou de defaults
conservadores. Um leito de fatias finas e compactas pode multiplicar a $\Delta P$ em
relação a um leito de pedaços grossos.
<!-- /profundidad -->

## Produto e carga {#producto}

O produto é escolhido do **catálogo** (com suas propriedades de sorção e constantes
térmicas já carregadas — ver [O catálogo de produtos](?manual=catalogo-productos) para
o que cada um traz e seu estado de calibração) e define-se a **carga**: massa fresca,
umidade inicial $X_0$ e umidade objetivo $X_{obj}$, ambas em **base seca** (kg de água
por kg de matéria seca — a diferença com a base úmida está explicada em
[Física da secagem](?manual=secado#base-seca)).

O coração do modelo de produto é a **isoterma de sorção GAB**: à medida que o produto
seca, sua atividade de água cai e a secagem se freia sozinha — assim aparecem os
períodos de taxa decrescente sem nenhuma curva empírica ajustada
([Física da secagem](?manual=secado#isotermas)).

## Condições de operação e forçantes {#modos-forzantes}

A seção permite escolher de onde saem as condições do ar que entra na câmara:

- **Constantes**: temperatura e umidade de operação fixadas à mão (os controles T/UR
  desta seção). Útil para exploração rápida.
- **Sintético / Dia real / Anual**: as forçantes saem do **clima e do coletor** hora a
  hora. **Nesses modos os controles T/UR de operação não influem** — a condição de
  contorno real é a saída do coletor (mais o auxiliar se existir).

O **horizonte de simulação** (modo transitório) define quantas horas o balanço é
integrado.

## Operação anual {#operacion-anual}

Com [modo de análise Anual](?manual=tipologia#modo-analisis), aparece a seção de
**operação anual**: define-se quantos **lotes por mês** se processam e o Secasol roda o
dia típico de cada mês, estimando produção anual e as quatro **eficiências de secagem**
(drying, pickup, térmica, total) por mês. O detalhe mensal é mostrado depois em
[7 · Resultados](?manual=resultados).

## Túnel semicontínuo (Grande escala) {#tunel}

Com subtipo **Semicontínuo**, aqui se configura a **topologia do túnel**: número de
zonas e cadência de avanço das colunas de carros. A secura de saída **não se impõe**: é
um resultado — se o produto sai mais úmido que o objetivo, é preciso alongar o túnel,
baixar a cadência ou subir a temperatura
([Técnico · Modo industrial](?manual=tec-industrial#semicontinuo)).

---

**Ver também:** [Técnico · Câmara](?manual=tec-camara) (as equações do balanço
acoplado), [Física da secagem](?manual=secado) e
[Psicrometria](?manual=psicrometria) (fundamentos),
[5 · Auxiliar](?manual=auxiliar) (se o sol não bastar).
