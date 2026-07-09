# Técnico · Recurso solar e clima do local

Referência técnica do subsistema de clima: download de dados NASA POWER, conversão para
SI, política de qualidade de dados, e a transposição do recurso global horizontal (GHI)
ao plano do coletor (POA). A versão introdutória desses conceitos está em
[Radiação solar e plano orientado](?manual=radiacion) e o guia de uso em
[2 · Localização e clima](?manual=emplazamiento).

## 1. O que o subsistema de clima entrega {#series}

A partir de três dados do usuário — **latitude, longitude, altitude** — mais a
**orientação do coletor** (inclinação β e azimute γ), o Secasol produz uma **série
climática horária anual** pronta para alimentar todos os motores físicos a jusante:

- Séries horárias em **SI estrito**: temperatura ambiente [K], GHI/DNI/DHI [W/m²], vento
  [m/s], umidade relativa [fração 0–1], pressão [Pa].
- A **irradiância sobre o plano inclinado e orientado (POA)**, que é a que o coletor de
  fato "vê", calculada por transposição de GHI/DNI/DHI.

A filosofia: o usuário só informa lat/lon; a mesma fonte e biblioteca padrão da indústria
fotovoltaica (NASA POWER + `pvlib`) fazem o resto.

## 2. Download de dados — NASA POWER via pvlib {#nasa-power}

Os dados vêm do serviço **NASA POWER** (*Prediction Of Worldwide Energy Resources*),
reanálise por satélite com cobertura global em grade de ~0,5°. O download usa
`pvlib.iotools.get_nasa_power`, que monta a URL da API, traduz os nomes de variáveis e
retorna um DataFrame horário tz-aware mais metadados (incluída a **altitude do ponto de
grade**).

Variáveis solicitadas:

| Variável | Código NASA | Unidade | Descrição |
|---|---|---|---|
| ghi | ALLSKY_SFC_SW_DWN | W/m² | global horizontal |
| dni | ALLSKY_SFC_SW_DNI | W/m² | direta normal |
| dhi | ALLSKY_SFC_SW_DIFF | W/m² | difusa horizontal |
| temp_air | T2M | °C | temperatura do ar a 2 m |
| wind_speed_2m | WS2M | m/s | vento a 2 m |
| RH2M | RH2M | % | umidade relativa a 2 m |
| PS | PS | kPa | pressão superficial |

O período pedido é o **ano-calendário completo** (8760 horas).

### Conversão para SI

$$
T:\ °C \to K\ (+273.15) \qquad
P:\ \mathrm{kPa} \to \mathrm{Pa}\ (\times 1000) \qquad
UR:\ \% \to \mathrm{fração}\ (\div 100)
$$

GHI/DNI/DHI [W/m²] e vento [m/s] não requerem conversão. A única conversão física de
unidades do recurso ocorre nesta camada; daí em diante tudo circula em SI estrito (ver
[Convenções](?manual=convenciones)).

### Cache transparente {#cache}

Para não bater na API a cada simulação, o resultado é salvo em **parquet** com chave
**SHA-256 de (lat, lon, ano)** (arredondados a 4 casas). A altitude do ponto de grade é
embutida nos metadados. Uma segunda simulação do mesmo local/ano lê do disco
(instantâneo, sem rede).

### Política de lacunas (qualidade explícita, não silenciosa) {#huecos}

O NASA POWER tem ocasionais valores faltantes. A política é:

- Lacunas de **≤ 3 h** consecutivas → **interpolação linear no tempo**.
- Lacunas de **> 3 h** → **deixadas como NaN**; um contador de horas bloqueadas maior que
  zero indica à interface que deve pedir uma decisão ao usuário.

A contagem de lacunas originais, maior lacuna, horas interpoladas e horas bloqueadas
viaja junto com a série num objeto de qualidade. **Nada é preenchido em silêncio.**

## 3. Do recurso horizontal (GHI) ao plano do coletor (POA) {#poa}

Este é o coração físico do subsistema. O NASA POWER entrega o recurso sobre **plano
horizontal**; o coletor está **inclinado** um ângulo β e **orientado** com azimute γ. É
preciso **transpor**.

### 3.1 Geometria solar (posição do Sol) {#spa}

Para cada timestamp horário calcula-se a posição solar com o algoritmo **SPA** (*Solar
Position Algorithm*) do `pvlib`, que retorna o **zenital aparente** $\theta_z$ e o
**azimute solar** $\gamma_s$. O SPA resolve internamente, em função de (lat, lon,
data-hora):

- **Declinação solar** $\delta$ (varia com o dia do ano $n$):
  $$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$
- **Ângulo horário** $\omega$ (a partir do meio-dia solar verdadeiro, com equação do
  tempo e correção de longitude).
- **Zenital solar**:
  $$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$
  com $\phi$ a latitude.

O Secasol **não reimplementa** essas fórmulas: delega ao SPA (precisão sub-grau, inclui
refração e equação do tempo). O **trânsito solar** (meio-dia verdadeiro) é calculado à
parte para escolher a hora representativa do dia, sem depender do máximo horário de GHI.

### 3.2 Ângulo de incidência sobre o plano {#incidencia}

O **ângulo de incidência** $\theta_i$ entre o raio direto e a normal do plano inclinado
(β, γ) é a magnitude-chave da componente direta:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

### 3.3 Transposição de Liu-Jordan (modelo isotrópico) {#liu-jordan}

A irradiância total sobre o plano (POA) se decompõe em **três contribuições** (modelo de
Liu-Jordan, difuso isotrópico):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{direta}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{difusa de céu}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{refletida do solo}}\,}
$$

onde:

- $I_b = \mathrm{DNI}$ (direta normal), projetada por $\cos\theta_i$.
- $I_d = \mathrm{DHI}$ (difusa horizontal), atenuada pelo **fator de vista do céu**
  $(1+\cos\beta)/2$.
- $I = \mathrm{GHI}$ (global horizontal), refletida pelo solo com **albedo** $\rho_g$ e
  fator de vista $(1-\cos\beta)/2$.

O **albedo** $\rho_g$ é configurável (default 0,25; catálogo de albedos por tipo de
superfície). No código, as três componentes são somadas por
`pvlib.irradiance.get_total_irradiance`, ao qual o Secasol passa β, γ já convertido à
convenção pvlib, a posição solar SPA, DNI/GHI/DHI e o albedo.

Usa-se o modelo **isotrópico** por simplicidade e coerência entre todos os pipelines; o
`pvlib` também suporta Hay-Davies, Reindl, Klucher, King e Perez, e o parâmetro de modelo
difuso deixa a substituição aberta.

### 3.4 Hipóteses da transposição {#hipotesis-poa}

- **Céu difuso isotrópico**: a difusa se reparte uniforme na abóbada (subestima
  levemente a circumsolar; conservador para pré-projeto).
- **Solo lambertiano** de albedo uniforme.
- **Cada hora é tratada como quase instantânea** na posição solar do bin horário
  (resolução horária do NASA POWER).
- **Fallback conservador**: se DNI ou DHI faltam numa dada hora, não se pode separar
  direta/difusa → assume-se **POA = GHI** nessa hora (subestima POA com β>0, mas evita
  propagar NaN ao solver do coletor). Valores negativos por artefato numérico perto do
  horizonte são recortados a 0.

## 4. Convenção de ângulos {#angulos}

O azimute tem **três convenções** e misturá-las é uma fonte clássica de erros de
orientação:

| Convenção | 0° | +90° | Faixa | Uso |
|---|---|---|---|---|
| **Duffie & Beckman** | Sul | Oeste | [−180, +180] | armazenamento interno e lógica de cálculo |
| **UI360** | Norte | Leste | [0, 360) | entrada do usuário na seção Localização |
| **pvlib** | Norte | Leste | [0, 360) | cálculo interno de irradiância |

Conversão usada na transposição POA:

$$\psi_{pvlib} = (180^\circ + \gamma_{Duffie}) \bmod 360^\circ$$

Verificação: γ=0° (Sul)→ψ=180° ✓; γ=90° (Oeste)→ψ=270° ✓; γ=−90° (Leste)→ψ=90° ✓;
γ=±180° (Norte)→ψ=0° ✓. As fórmulas de conversão **vivem num único módulo** e nunca se
duplicam. O detalhe completo está em
[Convenções de unidades e ângulos](?manual=convenciones).

## 5. Recortes temporais (modos de análise) {#recortes}

O subsistema também fornece os recortes da série anual que os distintos
[modos de análise](?manual=tipologia) consomem:

- **Dia típico mensal** — faz a média hora a hora de todos os registros de um mês → "dia
  típico" de 24 h. Converte para hora local antes de agrupar para que o pico solar caia
  perto das 12 locais. Alimenta o modo **Anual** (um lote representativo por mês).
- **N dias reais consecutivos** — recorta um lapso multidia; se cruza o 31-dez, trunca e
  o marca explicitamente, sem inventar emendas.
- **Janela** — recorta o lapso [início, fim] mapeado ao ano da série. Compartilhado pelas
  seções Localização, Coletor e Resultados (modo **Janela**).

---

**Ver também:** [Radiação solar e plano orientado](?manual=radiacion) (versão
introdutória), [2 · Localização e clima](?manual=emplazamiento) (guia de uso),
[Apêndice · Implementação](?manual=apendice-codigo#emplazamiento) (onde vive cada peça no
código), [Bibliografia](?manual=bibliografia#duffie-beckman).
