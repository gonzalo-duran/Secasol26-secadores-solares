# 5 · Aquecimento auxiliar

O auxiliar é o **apoio térmico** do secador: uma resistência elétrica ou um queimador
de biomassa que fornece calor quando o sol não basta — dias nublados, arranque cedo,
entardecer, ou campanhas onde perder uma leva custa mais que a lenha. É **opcional**:
um secador puramente solar simplesmente não o incorpora.

## Quando convém {#cuando}

Dois sinais típicos de que o projeto precisa de auxiliar:

- O [modo transitório ou anual](?manual=resultados) mostra que o produto não chega à
  umidade objetivo dentro da janela segura (risco de deterioração noturna ou de leva
  perdida).
- A **fração solar** do balanço fica alta mas o tempo de secagem é inaceitável nos
  meses críticos.

O objetivo do pré-projeto é dimensioná-lo **ao mínimo**: o painel de Resultados relata
a energia auxiliar e a fração solar para julgá-lo.

## Tipo e localização {#tipo}

- **Tipo**: resistência **elétrica** (rendimento ≈ 1, consumo em kWh) ou queimador de
  **biomassa** (consumo em kg de lenha via poder calorífico e rendimento do
  queimador).
- **Localização**: em **série pós-coletor** (toma o ar pré-aquecido do coletor e o
  termina de aquecer — o usual) ou como **apoio independente** (toma ar ambiente e
  aquece por conta própria).

O auxiliar **não acrescenta umidade**: é aquecimento sensível puro. Na
[carta psicrométrica](?manual=psicrometria#carta) seu trecho é horizontal (sobe T, ω
constante) — igual ao coletor.

## Potência e set-point {#setpoint}

Define-se a **potência nominal** e, opcionalmente, um **set-point** de temperatura: com
set-point, o auxiliar entrega **apenas a potência necessária** para alcançá-lo
(controle modulante ideal). Se o ar já chega mais quente que o set-point, o auxiliar
não gasta nada; se a potência não basta para chegar, entrega o máximo e avisa.

<!-- profundidad: O balanço do auxiliar -->
O auxiliar é modelado em regime estacionário, sem inércia:

$$
Q_{eff} = \dot m\,c_{p}\,(T_{salida}-T_{entrada})
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p}}
$$

Com set-point $T_{sp}$: $Q_{set}=\dot m c_p (T_{sp}-T_{ent})$, recortado entre 0 e
$Q_{max}$. A lenha consumida sai de
$m_{leña}=E_{aux}/(PCI\cdot\eta_{quemador})$, com a energia integrada sobre o horizonte.
Equações e casos-limite em [Técnico · Auxiliar](?manual=tec-auxiliar#balance).
<!-- /profundidad -->

## Disponibilidade e calendário de arranque {#calendario}

- **Disponibilidade noturna**: pode-se desligar o auxiliar à noite (quando a
  irradiância é praticamente nula), típico se a operação não tem turno noturno.
- **Calendário de arranque** (híbrido industrial): o queimador opera em **janelas
  horárias** de manhã e entardecer — a operação real de um secador híbrido tipo ADITAL:
  ligar cedo para arrancar a leva e ao entardecer para não perdê-la. Cada janela é
  definida por hora de início e duração, e o consumo de lenha é acumulado por janela.

---

**Ver também:** [Técnico · Auxiliar](?manual=tec-auxiliar) (equações e controle),
[4 · Câmara](?manual=camara) (para onde vai o ar),
[7 · Resultados](?manual=resultados) (fração solar e consumo no balanço).
