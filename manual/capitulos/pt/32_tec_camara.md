# Técnico · Câmara de secagem — balanço acoplado calor-massa

Referência técnica do motor de câmara (tipologias Caixa e Armário): balanço de calor das
paredes, balanços de momento e massa do ar com resfriamento evaporativo, modelo do
produto e papel da isoterma de sorção, e fluidodinâmica de bandejas. O modo industrial
(batch multizona e túnel semicontínuo) está em
[Técnico · Modo industrial](?manual=tec-industrial). O guia de uso está em
[4 · Câmara de secagem](?manual=camara).

## 1. Um único motor físico {#motor-unico}

A câmara tem **um só motor**: o **balanço acoplado calor–massa**. Um antigo motor de
"camada fina" (correlações empíricas MR(t) do tipo Lewis/Page/Henderson-Pabis) foi
removido do pipeline: era um avaliador de ponto único na temperatura de pico, insensível
à espessura de leito e à velocidade de ar reais.

O modelo atual integra **duas EDOs do produto** $(T_{prod}, X_{prod})$ acopladas com um
**sistema algébrico quase estacionário** do ar e das paredes (modelo **CSTR** — mistura
perfeita), que é resolvido **analiticamente** em cada passo de tempo. A evaporação é
**difusiva**.

## 2. Hipóteses e condições de contorno {#hipotesis}

**Hipóteses:**

1. **Secador indireto** (paredes opacas): sem radiação solar direta sobre o produto,
   salvo as **superfícies translúcidas** (§5.2) — teto e/ou paredes envidraçadas com
   repartição da radiação entre produto e ar.
2. **Modelo global (CSTR):** sem gradientes internos. Três nós — produto $T_{prod}$, ar
   de câmara $T_{flujo}$, paredes $T_{cam,int}/T_{cam,ext}$.
3. **Só o produto acumula calor no tempo** (capacitância). O ar e as paredes são quase
   estacionários (resolvidos sem derivada temporal).
4. **Ar úmido = mistura binária** ar seco + vapor; **produto = massa seca + água ligada**,
   $M_{tot}=M_s+M_{liq}$, $X=M_{liq}/M_s$ (base seca — ver
   [Física da secagem](?manual=secado)).
5. **Continuidade:** uma só entrada (saída de coletor + auxiliar) e uma só saída de ar.

**Condições iniciais (as EDOs):**
$$ T_{prod}(0)=T_{amb}, \qquad X_{prod}(0)=X_{inicial} $$

**Condições de contorno (o sistema algébrico, por passo):**

- Ar de entrada $(T_{ent}, \omega_{ent})$ = saída do coletor (+ auxiliar). Nos modos com
  clima real essas forçantes saem do clima e do coletor, **não** dos controles de
  condição de operação da seção Câmara (que só são condição de contorno no modo
  Constantes).
- Parede externa: convecção de vento $h_w = 5.7 + 3.8\,v_{viento}$ (McAdams).
- Evento de fim: $X_{prod}=X_{objetivo}$ (detecção de evento do integrador).

## 3. Balanço de calor do corpo (paredes) {#paredes}

A parede é modelada como **cascata resistiva de 3 nós** (convecção interior → condução do
isolante → convecção exterior), combinada numa condutância global:
$$
U_{total}=\left(\frac{1}{h_{conv}}+\frac{e_{cam}}{k_{ais}}+\frac{1}{h_w}\right)^{-1}
\qquad
Q_{pared}=U_{total}\,A_{cuerpo}\,(T_{flujo}-T_{amb})
$$

Os nós $T_{cam,int}$ e $T_{cam,ext}$ são **reconstruídos** como pós-cálculo a partir de
$Q_{pared}$ (a mesma potência atravessa cada resistência em série). Casos-limite tratados
explicitamente: $k_{ais}=0$ → parede isolante perfeita ($U_{total}=0$); $h_w=0$ → face
externa desacoplada do ambiente.

## 4. Balanços do ar — resfriamento evaporativo {#aire}

### 4.1 O sistema algébrico do ar {#cstr}

O ar que circula pela câmara é resolvido como **CSTR quase estacionário**. O sistema
algébrico (resolução direta, sem iteração) é:

**(a) Balanço de massa de água do ar** (linear em $\omega_{flujo}$):
$$
\dot m_{as}\,(\omega_{flujo}-\omega_{ent}) = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo})
$$
com $\omega_{sup}=\omega_{sat}(T_{prod})\cdot a_w(X_{prod})$ a umidade da **camada de ar
em contato com o produto** (saturação a $T_{prod}$ corrigida pela atividade de água
$a_w$). A **taxa de evaporação** é:
$$
\boxed{\;\dot m_w = K_m\,A_{prod}\,(\omega_{sup}-\omega_{flujo}) = \dot m_{as}(\omega_{flujo}-\omega_{ent})\;}
$$
(sinal: + evaporação, − condensação). Esta é a forma **difusiva**:
$\dot m_w = h_m\,A\,(\omega_{sat}\,a_w - \omega_{flujo})$.

**(b) Balanço de energia (entalpia) do ar** (linear em $T_{flujo}$):
$$
\dot m_{as}\,[\,h(T_{flujo},\omega_{flujo})-h(T_{ent},\omega_{ent})\,]
 = -U_{total}A_{cuerpo}(T_{flujo}-T_{amb})
 - h_{conv}A_{prod}(T_{flujo}-T_{prod})
 + \dot m_w\,h_v(T_{prod})
 + Q_{rad,aire}
$$

O termo $\dot m_w\,h_v(T_{prod})$ (positivo) é o vapor que sai do produto a $T_{prod}$ e
se incorpora ao ar. $Q_{rad,aire}$ é a fração da radiação transmitida pelas superfícies
translúcidas que o produto **não** intercepta e que aquece o ar via as superfícies
internas opacas (§5.2); vale 0 com envelope opaco. Aqui está o **resfriamento
evaporativo**: o ar cede calor sensível ao produto ($T_{flujo}\downarrow$) e ganha
umidade ($\omega_{flujo}\uparrow$). Os conceitos psicrométricos ($\omega$, saturação,
entalpia do ar úmido) estão em [Psicrometria](?manual=psicrometria).

### 4.2 Correlações de transferência (calor e massa) {#coeficientes}

Os coeficientes $h_{conv}$ (ar→produto) e $K_m$ (transferência de massa) são reavaliados
**a cada passo** (não se congelam) com **placa plana + analogia de Chilton-Colburn**, com
todas as propriedades avaliadas na película $T_{film}=(T_{ent}+T_{prod})/2$.

**Convecção de calor ar→produto — placa plana** (comprimento característico = comprimento
da bandeja/câmara $L$; $Re=\rho\,v\,L/\mu$ com $\rho$ do ar úmido e $v$ da vazão mássica
sobre a seção transversal):

| Correlação | Expressão de Nu | Regime / faixa |
|---|---|---|
| **Pohlhausen** (laminar) | $Nu = 0.664\,Re^{1/2}\,Pr^{1/3}$ | Camada limite laminar sobre placa, $Re < 5\times10^{5}$ |
| **McAdams** (turbulento) | $Nu = 0.037\,Re^{0.8}\,Pr^{1/3}$ | Camada limite turbulenta, $Re > 5\times10^{5}$ |

com $h_{conv}=Nu\,k_{aire}/L$.

**Transferência de massa — analogia de Chilton-Colburn.** Liga o transporte de calor e o
de massa pelo número de Lewis:
$$
\frac{h_{conv}}{K_m\,c_{p,h}} = Le^{2/3},
\qquad Le=\frac{\alpha}{D_{AB}}\approx 1 \text{ (ar–água)}
\;\Rightarrow\;
K_m=\frac{h_{conv}}{c_{p,h}\,Le^{2/3}}
$$
com $K_m$ [kg/(m²·s)] o coeficiente de transferência de massa e $c_{p,h}=1006+1805\,\omega$
o calor específico do ar úmido. Como $Le\approx1$, o número de **Sherwood** herda a mesma
forma que o de Nusselt ($Sh = 0.664\,Re^{1/2}Sc^{1/3}$ laminar / $0.037\,Re^{0.8}Sc^{1/3}$
turbulento). Reavaliar $h_{conv},K_m$ a partir de quantidades conhecidas no início do
passo **não quebra a linearidade** do sistema algébrico do ar.

**Convecção de vento na parede externa — McAdams:** $h_w = 5.7 + 3.8\,v_{viento}$
[W/m²·K] (entra em $U_{total}$ e em $U_{techo}$).

## 5. Materiais, isolantes e coberturas {#materiales}

### 5.1 Parede composta {#pared-compuesta}

A parede se define como **camadas em série**, cada uma com sua resistência; a resistência
condutiva total $R_{cond}=\sum_i e_i/k_i$ é agregada e convertida a uma condutividade
efetiva $k_{ais}=e_{cam,total}/R_{cond}$. Materiais e isolantes vêm de catálogos.

### 5.2 Superfícies translúcidas — ganho + perda {#techo-translucido}

Até **5 faces** da câmara (teto + 4 paredes) podem ser translúcidas. Cada face $i$ tem
inclinação e azimute próprios, derivados da **orientação da câmara** e do **teto de uma
água** (`GeometriaCamara.caras()`; a altura da geometria é a altura **média**, o que
preserva o volume e a seção de fluxo ao inclinar o teto). A irradiância sobre cada face é
sua **POA** (transposição Liu-Jordan por face — [Radiação solar](?manual=radiacion); um
teto horizontal usa GHI diretamente, o caso histórico exato).

**Ganho — repartição produto/ar.** Cada face intercepta uma fração $f_i$ de sua radiação
transmitida diretamente sobre o produto; o resto é absorvido pelas superfícies internas
opacas (absortância interior $\alpha_{int}$, default 0,85) e aquece o ar:

$$
I_{eq,prod}=\frac{\sum_i f_i\,A_i\,POA_i}{A_{rad}},
\qquad
Q_{rad,aire}=\tau\,\alpha_{int}\sum_i (1-f_i)\,A_i\,POA_i
$$

O produto recebe $Q_{rad}=I_{eq,prod}\,\tau\,\alpha\,A_{rad}$ (como o teto translúcido
histórico, agora com a irradiância equivalente de todas as faces); $Q_{rad,aire}$ entra no
balanço de $T_{flujo}$ (§4.1b). Os fatores de interceptação: o teto "vê" o produto segundo
$f_{techo}=A_{rad}/A_{techo}$; as paredes segundo a **silhueta do leito empilhado**
($f_{pared}=N_{bandejas}\,e_{capa}/H$). É o **efeito estufa** de uma caixa envidraçada: na
tipologia Caixa, a câmara **é** o coletor.

**Perda condutiva** do envidraçamento:
$U_{techo}=\left(\tfrac{1}{h_{conv}}+\tfrac{e_{techo}}{k_{ef}}+\tfrac{1}{h_w}\right)^{-1}$,
com $k_{ef}$ do mapa por espessura do catálogo (policarbonato alveolar), aplicada à **área
translúcida total** $\sum_i A_i$.

A área translúcida é **descontada do envelope opaco** $A_{cuerpo}$ (para não contar em
dobro) e $U_{techo}\sum_i A_i$ é somada ao balanço de $T_{flujo}$. Envelope opaco → sem
efeito.

**Fora do modelo** (anotado como melhoria futura): perdas IR noturnas do envidraçamento e
discretização vertical do produto por bandeja.

## 6. Modelo do produto e a isoterma de sorção {#producto}

### 6.1 As duas EDOs do produto {#edos}

$$
\frac{dX_{prod}}{dt} = -\frac{\dot m_w}{M_s}
$$
$$
M_{prod}\,c_{p,prod}\,\frac{dT_{prod}}{dt} = q_{prod} - \dot m_w\,L_v(T_{prod})
$$

com $q_{prod}=h_{conv}A_{prod}(T_{flujo}-T_{prod})$ o calor sensível que o ar entrega ao
produto, e $c_{p,prod}=c_{ps}+c_{pa}X$ (mistura seco+água). O segundo termo é o
**resfriamento por evaporação** do produto (calor latente $L_v$). São integradas com
`scipy.integrate.solve_ivp` e **detecção de evento** em $X_{objetivo}$.

### 6.2 O papel da curva de sorção {#isotermas}

**Não há uma curva cinética empírica MR(t):** a "curva de secagem" **emerge** de integrar
o balanço difusivo. O que governa o processo é a **isoterma de sorção de equilíbrio GAB**,
que entrega a **atividade de água** $a_w(X)$:

$$
X = \frac{X_m\,C\,K\,a_w}{(1-K a_w)(1-K a_w + C K a_w)}
$$

O Secasol usa a **inversão analítica** $a_w = f(X; X_m, C, K)$ (quadrática) para fixar
$\omega_{sup}=\omega_{sat}(T_{prod})\,a_w(X)$. Fisicamente: à medida que o produto seca,
$a_w$ **cai** → a força motriz $(\omega_{sup}-\omega_{flujo})$ **diminui** → a taxa de
secagem **baixa** sozinha. Assim se reproduzem os **períodos de secagem** (taxa
decrescente) **sem** correlação empírica: a frenagem sai da termodinâmica de sorção, não
de um ajuste. Cada produto traz seus parâmetros $X_m, C, K$ no catálogo; se falta
calibração, o sistema **avisa**. O fundamento conceitual está em
[Física da secagem](?manual=secado#isotermas).

## 7. Fluidodinâmica das bandejas — horizontal vs vertical {#bandejas}

A área de troca do produto é $A_{prod}=N_{bandejas}\cdot A_{bandeja}$. A **direção do
fluxo** muda tanto a perda de carga quanto o regime convectivo:

- **HORIZONTAL (cross-flow):** o ar passa **sobre** as bandejas. O coeficiente convectivo
  é calculado como **placa plana** (Pohlhausen/McAdams, §4.2); a perda de carga é
  $\Delta P_{malla}$ (coeficiente de forma $K\rho v^2/2$ por bandeja) **mais**, se o leito
  é apreciável, $\Delta P_{lecho}$ por **Ergun**.
- **VERTICAL ASCENDENTE (through-bed):** o ar **atravessa** o leito de produto. Domina a
  perda de carga do **leito empacotado (Ergun)**:
  $$
  \frac{\Delta P}{L} = \underbrace{\frac{150\,\mu\,v_0\,(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}}_{\text{viscoso (laminar)}}
   + \underbrace{\frac{1.75\,\rho\,v_0^2\,(1-\varepsilon)}{(\Phi_s d_p)\,\varepsilon^3}}_{\text{inercial (turbulento)}}
  $$
  com $\varepsilon$ porosidade do leito, $d_p$ diâmetro de partícula, $\Phi_s$
  esfericidade. A geometria do leito é resolvida por cadeia de prioridade (catálogo do
  produto → bandeja → defaults conservadores).

**O trade-off:** o fluxo vertical maximiza o **contato ar–produto** (melhor transferência,
secagem mais uniforme), mas ao custo de **muito mais perda de carga** (penaliza o
ventilador ou a tiragem natural — ver
[Técnico · Motor e perdas de carga](?manual=tec-chimenea)). O fluxo horizontal é mais suave
hidraulicamente mas transfere menos. O aviso de **leito fino (<5 cm)** limita a validade do
modelo difusivo.

---

**Ver também:** [4 · Câmara de secagem](?manual=camara) (guia de uso),
[Psicrometria](?manual=psicrometria) e [Física da secagem](?manual=secado) (fundamentos),
[Técnico · Modo industrial](?manual=tec-industrial) (batch multizona e túnel),
[Apêndice · Implementação](?manual=apendice-codigo#camara),
[Bibliografia](?manual=bibliografia#mujumdar).
