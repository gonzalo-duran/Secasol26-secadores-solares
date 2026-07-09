# Convenções de unidades e ângulos

O Secasol é estrito com as unidades e as convenções angulares: são a fonte clássica de
erros em ferramentas de engenharia. Este capítulo documenta as regras para você poder
interpretar qualquer número do programa (e deste manual) sem ambiguidade.

## Unidades: SI estrito por dentro {#si}

Internamente **tudo circula em SI estrito**; a interface converte para unidades
confortáveis apenas ao mostrar e ao ler suas entradas:

| Magnitude | Interno (SI) | Na interface |
|---|---|---|
| Temperatura | K | °C |
| Pressão | Pa | kPa / Pa conforme o contexto |
| Umidade relativa | fração 0–1 | % |
| Umidade absoluta do ar | $\omega$ [kg água / kg ar seco] | g/kg na carta |
| Umidade do produto | $X$ [kg água / kg seco] (**base seca**) | base seca (e base úmida como referência) |
| Tempo | s | horas / dias |
| Vazão mássica | kg/s | kg/s ou m³/h |
| Irradiância | W/m² | W/m² |

Duas convenções que convém ter presentes ao ler resultados:

- A **umidade do produto é base seca** ($X$): pode ultrapassar 1 (um produto fresco com
  90 % de água em base úmida tem $X=9$). A conversão está em
  [Física da secagem](?manual=secado#base-seca).
- A **umidade relativa interna é fração** (0,60, não 60 %) — nas equações deste manual,
  UR e $a_w$ vão sempre em fração.

## Ângulos: três convenções de azimute {#acimut}

O azimute (para onde o coletor "olha") tem três convenções em jogo, e **não se
misturam**:

| Convenção | 0° | +90° | Faixa | Onde se usa |
|---|---|---|---|---|
| **UI360** | Norte | Leste | [0, 360) | o que **você** carrega em [2 · Localização](?manual=emplazamiento) |
| **Duffie & Beckman** | Sul | Oeste | [−180, +180] | armazenamento interno e equações de geometria solar |
| **pvlib** | Norte | Leste | [0, 360) | o cálculo de irradiância dentro da biblioteca pvlib |

Na interface você sempre vê **UI360** (0° = Norte, sentido horário, como uma bússola).
As equações dos capítulos técnicos (por exemplo o
[ângulo de incidência](?manual=radiacion#incidencia)) usam a convenção de **Duffie &
Beckman**, a padrão da bibliografia solar.

<!-- profundidad: As fórmulas de conversão -->
Conversões exatas (γ = Duffie, α = UI360, ψ = pvlib):

$$
\alpha = (-\gamma) \bmod 360
\qquad\qquad
\gamma = (-\alpha) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

$$
\psi = (180 + \gamma) \bmod 360
\qquad\qquad
\gamma = (\psi - 180) \bmod 360,\ \ \gamma>180 \Rightarrow \gamma \mathrel{-}= 360
$$

Casos de verificação: Sul → γ=0, α=180, ψ=180. Norte → γ=±180, α=0, ψ=0. Leste →
γ=−90, α=90, ψ=90. Oeste → γ=90, α=270, ψ=270. No código, essas fórmulas vivem num único
módulo de conversões e nunca se duplicam.
<!-- /profundidad -->

A **inclinação** β é única em todas as convenções: 0° = horizontal, 90° = vertical.

## Sinais e referências diversas {#signos}

- **Latitude**: negativa no hemisfério sul (Salta ≈ −24,8°).
- **Longitude**: negativa a oeste de Greenwich (Argentina ≈ −54° a −73°).
- **Taxa de evaporação** $\dot m_w$: positiva = o produto perde água; negativa =
  condensação sobre o produto.
- **ΔT do duto mestre**: negativo = o ar chega mais frio à câmara (perda), positivo =
  ganho solar do duto.
- **Ângulo da cavidade** na correlação de Hollands: medido a partir da horizontal,
  válido até 75°.

---

**Ver também:** [Radiação solar e plano orientado](?manual=radiacion) (onde essas
convenções se usam), [Glossário](?manual=glosario) (símbolos e termos).
