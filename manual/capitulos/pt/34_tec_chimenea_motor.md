# Técnico · Motor, chaminé solar e perdas de carga

Referência técnica do movimento do ar: perdas de carga globais do sistema (equações por
trecho), dimensionamento do ventilador em convecção forçada, vazão de equilíbrio em
convecção natural, laço Picard, exaustor eólico e dimensionamento da chaminé solar. O guia
de uso está em [6 · Motor e chaminé](?manual=motor).

## 1. Duas formas de mover o ar {#dos-formas}

O ar pode circular por **convecção forçada** (ventilador axial ou centrífugo) ou por
**convecção natural** (chaminé solar, opcionalmente com exaustor eólico). A seção Motor
habilita uma ou outra: com motor desligado aparece a chaminé. O exaustor eólico é
**acessório da chaminé**, não um tipo de motor.

Em ambos os casos é preciso a **perda de carga global** do laço. A diferença: em forçada a
$\Delta P$ **dimensiona o motor**; em natural a $\Delta P$ (como função da vazão) **determina
a vazão de equilíbrio**.

## 2. Perdas de carga globais — equações por trecho {#perdidas}

As perdas se decompõem em trechos em série. Todos usam o mesmo fator de atrito de
**Haaland** (aproximação explícita de Colebrook-White, ASHRAE cap. 21):

$$
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
\quad(Re>4000),
\qquad f=\frac{64}{Re}\ (Re<2300)
$$

com mistura linear na transição $2300<Re<4000$.

### 2.1 Coletor (canal retangular) — Darcy-Weisbach {#dp-colector}

$$
\Delta P_{col} = f\,\frac{L}{D_h}\,\frac{\rho v^2}{2},\qquad D_h=\frac{2We}{W+e}
$$

Série: $\Delta P_{rama}=\Delta P_{unidad}\times n_{serie}$; paralelo:
$\Delta P_{banco}=\Delta P_{rama}$.

### 2.2 Câmara — conforme a orientação do fluxo {#dp-camara}

- **HORIZONTAL (cross-flow):** os $n_{bandejas}-1$ canais entre bandejas estão **em
  paralelo** → a $\Delta P$ do sistema é a de **um** canal.
  $\Delta P_{cam}=\Delta P_{producto}+\Delta P_{malla}$, com $\Delta P_{producto}$ = atrito
  rugoso (rugosidade efetiva $\varepsilon_{eff}=\max(\varepsilon_{chapa},d_p)$) + obstrução
  por bloqueio $C_{obs}(\beta)$, $\beta=e_{capa}/\text{separação}$.
- **VERTICAL ASCENDENTE (through-bed):** por bandeja
  $\Delta P=\Delta P_{malla}+\Delta P_{lecho}$ com **Ergun**:
  $$
  \frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
  $$
  A $\Delta P$ de malha usa coeficientes K tipo Idelchik/Crane conforme o tipo de malha.

### 2.3 Dutos e singulares {#dp-ductos}

$\Delta P_{ductos}$ por Darcy-Weisbach (rugosidade de galvanizado $\varepsilon\approx0,15$
mm, ASHRAE) e singulares $\Delta P=K\,\rho v^2/2$ (curvas, expansões, entradas/saídas).

### 2.4 Duto mestre (só grande escala) {#dp-cano}

Em Grande escala **soma-se** a $\Delta P$ do duto mestre (fluxo acumulado, seção variável —
ver [Técnico · Modo industrial](?manual=tec-industrial#dp-cano)).

**Propriedades do ar:** $\rho(T,P)=P/(R_{aire}T)$ (gás ideal, $R_{aire}=287.058$); $\mu(T)$
por Sutherland; pressão atmosférica por altitude segundo a atmosfera padrão (ISA).

## 3. Convecção forçada — dimensionamento do motor {#forzada}

Com a $\Delta P$ total e a vazão volumétrica $Q$, as potências são calculadas em cascata:

$$
P_{hid}=Q\,\Delta P
\;\xrightarrow{/\eta_{vent}}\;
P_{eje}=\frac{P_{hid}}{\eta_{vent}}
\;\xrightarrow{/\eta_{motor}}\;
P_{elec}=\frac{P_{eje}}{\eta_{motor}}
\;\xrightarrow{\times FS}\;
P_{inst}=P_{elec}\cdot FS
$$

com $\eta_{vent}$ rendimento do ventilador, $\eta_{motor}$ do motor elétrico, $FS$ fator de
serviço. A **corrente nominal** sai de $I=P_{elec}/(V\cos\varphi)$, com $\cos\varphi=0.85$
(motor pequeno). Se o usuário fixa uma velocidade de descarga, acrescenta-se a pressão
dinâmica $\Delta P_{din}=\rho v_{desc}^2/2$ à $\Delta P$ total.

**Âncora empírica** para validar a ordem de grandeza: exaustor de 76 W / 900 m³/h num
armário de ~50 kg → $P_{elec}$ esperada **50–100 W**.

## 4. Convecção natural — vazão de equilíbrio {#natural}

Sem motor, o ar circula por **tiragem térmica**. A vazão de equilíbrio é aquela em que a
pressão **motriz** iguala a **resistiva**:

$$
\boxed{\;\Delta P_{tiro} + \Delta P_{turbina,motriz} = \Delta P_{chimenea}(\dot m) + \Delta P_{resto}(\dot m)\;}
$$

### 4.1 Tiragem térmica (stack effect) {#tiro}

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim}),
\qquad H_{eff}=H_{chimenea}+H_{camara}
$$

Com gás ideal a pressão comum $\rho\propto1/T$, de modo que $\Delta P_{tiro}>0$ quando
$T_{chim}>T_{amb}$ (fluxo ascendente) e $\Delta P_{tiro}<0$ quando $T_{chim}<T_{amb}$
(tiragem nula à noite → $\dot m=0$). $H_{eff}$ inclui a altura útil da câmara (desde a
entrada de ar frio até a base da chaminé).

### 4.2 Resolução numérica {#brentq}

$\Delta P_{chimenea}(\dot m)$ (atrito + singulares + resistência do exaustor) e
$\Delta P_{resto}(\dot m)$ (coletor + câmara + dutos, função monótona com $f(0)=0$) são
funções da vazão. A raiz da equação de equilíbrio é resolvida com **`scipy.optimize.brentq`**
limitada a $[\dot m_{min}, \dot m_{max}]$. Retorna $\dot m$, a velocidade na chaminé e todas
as componentes de $\Delta P$.

## 5. Exaustor eólico (turbina chapéu chinês) {#extractor}

Acessório opcional no topo da chaminé. Acrescenta **dois** termos:

- **Motriz** — depressão que a rotação da turbina gera:
  $$\Delta P_{turbina}=C_p\,\rho_{amb}\,v_{viento}^2/2$$
  com $C_p\approx0.3$–$0.6$. O vento NASA POWER (medido a **10 m**) é corrigido à **altura do
  topo** $z=H_{camara}+H_{chimenea}$ por **perfil logarítmico**:
  $$v(z)=v_{10}\,\frac{\ln(z/z_0)}{\ln(10/z_0)}$$
  com $z_0$ a rugosidade aerodinâmica do terreno.
- **Resistivo** — a turbina obstrui o fluxo: $\Delta P=K_t\,\rho_{chim}\,v_{ext}^2/2$,
  avaliado na velocidade pelo diâmetro próprio do exaustor.

O termo motriz entra no lado esquerdo da equação de equilíbrio; o resistivo, na
$\Delta P_{chimenea}$.

## 6. Laço Picard — acoplamento térmico-hidráulico {#picard}

A vazão natural toma $T_{chim}$ **como dado**, mas fisicamente $T_{chim}$ depende da vazão
(a mais vazão, menos $\Delta T$ no coletor → $T_{chim}$ baixa → menos tiragem). Esse
acoplamento é fechado com **iteração de ponto fixo (Picard)** sobre o triângulo:

$$
T_{chim} \longleftrightarrow \dot m_{nat} \longleftrightarrow T_{salida,colector}
$$

- **Modo Constantes**: até 10 iterações, tolerância 0,5 K. Em cada iteração re-roda-se o
  coletor estacionário com a velocidade implicada pela vazão natural, recalcula-se
  $\dot m_{nat}$, e a temperatura do ar de câmara realimenta $T_{chim}$.
- **Modo Transitório**: Picard sobre **todo o horizonte** horário, até 5 iterações,
  tolerância 0,5 K. Por iteração calcula-se $\dot m(t)$ hora a hora, re-roda-se o solver do
  coletor a cada hora com a velocidade efetiva
  $v(t)=\dot m_{nat}(t)/(\rho A_{canal} n_{par})$, o motor de câmara consome as novas
  forçantes e $T_{flujo}(t)$ realimenta $T_{chim}(t)$.

Se a chaminé tem **exaustor ativo**, o balanço do laço soma ainda
$\Delta P_{turbina,motriz}(v_{viento}(t))$ ao lado motriz e $K_t\rho v^2/2$ ao resistivo. As
horas com tiragem nula ($T_{chim}\le T_{amb}$) recebem $\dot m=0$.

## 7. Dimensionamento da chaminé solar {#chimenea}

A chaminé é dimensionada por sua **geometria** (diâmetro, altura), que fixa:

- A **tiragem disponível** via $H_{eff}$ (a maior altura, maior $\Delta P_{tiro}$).
- A **resistência própria** $\Delta P_{chimenea}=K_{total}\,\rho v^2/2$ com
  $K_{total}=f\,H/D+K_{singular}$.

O pré-projeto busca a combinação diâmetro/altura que entrega a vazão objetivo com o
$\Delta T$ esperado do coletor. A chaminé é um componente de **nível superior** do projeto
(não um subcomponente do coletor), o que permite chaminé solar também na tipologia Caixa.

---

**Ver também:** [6 · Motor e chaminé](?manual=motor) (guia de uso),
[Técnico · Coletor](?manual=tec-colector#perdidas) e
[Técnico · Câmara](?manual=tec-camara#bandejas) (as $\Delta P$ de cada trecho),
[Técnico · Balanço global](?manual=tec-resultados) (onde se fecha o laço),
[Apêndice · Implementação](?manual=apendice-codigo#motor),
[Bibliografia](?manual=bibliografia#ashrae).
