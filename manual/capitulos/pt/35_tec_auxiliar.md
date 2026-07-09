# Técnico · Sistema de aquecimento auxiliar

Referência técnica do auxiliar: balanço de energia, controle por set-point, consumos,
impacto no balanço global e calendário de arranque do híbrido industrial. O guia de uso
está em [5 · Aquecimento auxiliar](?manual=auxiliar).

## 1. Para que serve e onde se localiza {#ubicacion}

O auxiliar (elétrico ou de biomassa) é o **apoio térmico** do secador: fornece calor quando
o sol não basta (dias nublados, arranque cedo, entardecer). É **opcional**. Tem dois modos
de localização:

- **SÉRIE PÓS-COLETOR** — o auxiliar está **entre o coletor e a câmara**: toma o ar já
  pré-aquecido pelo coletor ($T_{ent}=T_{salida,colector}$) e o termina de aquecer antes da
  câmara.
- **APOIO INDEPENDENTE** — toma ar ambiente ($T_{ent}=T_{amb}$) e o aquece por conta própria
  (apoio total).

Em **grande escala** o ar de todos os ramais é somado no duto mestre e **só então** entra no
auxiliar (ou direto na câmara).

## 2. Balanço de energia estacionário {#balance}

O auxiliar é modelado como um aquecedor em **regime estacionário, sem inércia térmica**. O
balanço de energia sobre o ar é:

$$
\boxed{\;Q_{eff} = \dot m\,c_{p,aire}\,(T_{salida}-T_{entrada})\;}
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p,aire}}
$$

com $c_{p,aire}\approx1007$ J/(kg·K). A potência disponível é
$Q_{max}=P_{nominal}\cdot f_{operacion}$ (fração de potência de operação).

### 2.1 Controle por set-point (proporcional ideal) {#set-point}

Se há set-point $T_{sp}$, o auxiliar entrega **apenas** a potência necessária para
alcançá-lo:
$$
Q_{set} = \dot m\,c_{p}\,(T_{sp}-T_{entrada})
$$

- $Q_{set}<0$ → o ar já ultrapassa o set-point: $Q_{eff}=0$ (com aviso).
- $0\le Q_{set}\le Q_{max}$ → $Q_{eff}=Q_{set}$ (controle ativo, modula).
- $Q_{set}>Q_{max}$ → $Q_{eff}=Q_{max}$ no máximo (aviso de set-point não alcançável).

Se não há set-point, $Q_{eff}=Q_{max}$. Há ainda um teto físico $T_{max,salida}$ que dispara
aviso se excedido.

### 2.2 Consumos {#consumos}

- **Resistência elétrica** ($\eta\approx1$): $P_{elec}=Q_{eff}$.
- **Queimador de biomassa:** consumo [kg/h] proporcional à fração ativa; a **lenha total**
  sai da energia entregue, do PCI (poder calorífico inferior) e do rendimento do queimador:
  $$ m_{leña} = \frac{E_{aux}}{PCI\cdot\eta_{quemador}} $$
  com $E_{aux}=\int Q_{eff}\,dt$ (integração trapezoidal sobre o horizonte).

## 3. Impacto no balanço global {#impacto}

O auxiliar **eleva a temperatura da corrente de ar** que alimenta a câmara. Na cadeia do ar
(modo armário):

$$
T_{amb} \xrightarrow{\text{coletor: }+\Delta T} T_1
\xrightarrow{\text{auxiliar: }+\Delta T} T_2
\xrightarrow{\text{câmara}} T_3 < T_2
$$

A $T_{salida}$ do auxiliar passa a ser a **condição de contorno** $T_{ent}$ do motor
termodinâmico de câmara ([Técnico · Câmara](?manual=tec-camara)), modificando todo o balanço
calor–massa a jusante (mais temperatura do ar → mais capacidade de evaporação → secagem mais
rápida). O auxiliar **não acrescenta umidade** ($\omega$ constante): é aquecimento
**sensível** puro — na [carta psicrométrica](?manual=psicrometria) é um trecho horizontal.

Nos modos **Transitório/Janela**, o auxiliar é avaliado **hora a hora** sobre a série de
$T_{ent}(t)$, reusando a lógica escalar passo a passo, e acumula energia e lenha.

## 4. Disponibilidade temporal e calendário de arranque {#calendario}

O auxiliar tem uma **política de operação temporal**:

- **Disponibilidade noturna**: se desabilitada e a série de irradiância está disponível, os
  passos com $I_g \le 10$ W/m² (noite) são forçados a $Q_{eff}=0$ (auxiliar desligado à
  noite).
- **Calendário de arranque**: para o **híbrido industrial**, o queimador opera em **janelas
  horárias** específicas de manhã/entardecer (independente da irradiância), não a potência
  constante. Cada passo é mapeado à sua hora do dia $((t/3600)+\text{offset})\bmod 24$ e
  marcado ativo se cai dentro de alguma janela $[\text{início}, \text{início}+\text{duração})$
  (com envoltório se cruza a meia-noite).

Isso reproduz a operação real de um secador híbrido tipo ADITAL: o queimador é ligado cedo
para arrancar a secagem e ao entardecer para não perder a leva, acumulando lenha em cada
janela (ver [Técnico · Modo industrial](?manual=tec-industrial#calendario)).

---

**Ver também:** [5 · Aquecimento auxiliar](?manual=auxiliar) (guia de uso),
[Técnico · Câmara](?manual=tec-camara) (para onde entra o ar aquecido),
[Apêndice · Implementação](?manual=apendice-codigo#auxiliar).
