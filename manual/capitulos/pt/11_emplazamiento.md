# 2 · Localização e recursos climáticos

Aqui o projeto se ancora a um lugar real: com **latitude, longitude e altitude**, o
Secasol baixa um **ano completo de clima horário** (8760 horas) do serviço NASA
POWER e o converte nas séries que alimentam todos os cálculos: temperatura, radiação
(global, direta e difusa), vento, umidade e pressão. Também é aqui que se define a
**orientação do coletor** (inclinação e azimute), que determina quanta dessa
radiação efetivamente chega ao plano do coletor.

A filosofia da seção: **o usuário só informa as coordenadas**; o download, o cache,
as conversões de unidades e a transposição ao plano do coletor são automáticos.

## Coordenadas do local {#coordenadas}

Latitude e longitude em graus decimais (negativos para o hemisfério sul e para o
oeste de Greenwich — ex. Salta ≈ lat −24,8, lon −65,4). A **altitude** ajusta a
pressão atmosférica (afeta a densidade do ar e a psicrometria); se você não a
conhece, o NASA POWER traz a do ponto de grade. O **fuso horário** alinha as horas
do clima com a hora solar local.

## Download do clima {#descarga}

O botão de download traz o ano escolhido do **NASA POWER** (reanálise por satélite
global, grade ~0,5°, o mesmo serviço que a indústria fotovoltaica usa). O download é
**armazenado em cache no disco**: repetir o mesmo local e ano é instantâneo e sem
rede.

<!-- profundidad: O que se baixa e como se converte -->
Variáveis horárias: GHI, DNI, DHI [W/m²], temperatura a 2 m [°C→K], vento a 2 m
[m/s], umidade relativa [%→fração], pressão superficial [kPa→Pa]. A conversão para SI
ocorre uma única vez na camada de clima; daí em diante todo o sistema trabalha em SI
estrito (ver [Convenções](?manual=convenciones)). O cache usa uma chave criptográfica
de (lat, lon, ano), então mudar qualquer um dos três dispara um novo download. O
detalhe está em
[Técnico · Recurso solar e clima](?manual=tec-emplazamiento#nasa-power).
<!-- /profundidad -->

### Qualidade dos dados {#calidad}

O NASA POWER tem ocasionais lacunas. A política do Secasol é **explícita, não
silenciosa**:

- Lacunas de **até 3 horas** consecutivas são interpoladas linearmente (e informa-se
  quantas horas foram interpoladas).
- Lacunas **maiores** não são preenchidas: a seção mostra quantas horas ficaram
  bloqueadas e pede uma decisão (escolher outro ano, outro local, ou aceitar a
  lacuna sabendo quais dias afeta).

## Orientação do coletor {#orientacion}

A **inclinação** β (0° = horizontal) e o **azimute** (para onde o plano "olha", com
0° = Norte na entrada da interface) definem o plano do coletor. Com eles o Secasol
**transpõe** a radiação horizontal ao plano: a **POA** (*plane of array*), que é a
que todos os cálculos do coletor usam.

Regras rápidas: no hemisfério sul o coletor olha para o **Norte**; β próxima da
latitude para uso anual, maior para favorecer o inverno. A fundamentação completa
(componentes da radiação, ângulo de incidência, modelo de Liu-Jordan) está em
[Radiação solar e plano orientado](?manual=radiacion).

Na tipologia **Caixa** esta seção não aparece (não há coletor externo): o plano
captador é a própria câmara, e sua orientação e inclinação de teto se definem em
[4 · Câmara](?manual=camara#orientacion).

Também se configura o **albedo** do solo circundante (fração de radiação que o solo
reflete em direção ao coletor), com um catálogo de valores típicos.

## Gráficos: POA vs GHI {#graficas}

Os gráficos da seção comparam a radiação **horizontal** (GHI) com a radiação **no
plano do coletor** (POA) para o dia e o ano: são a ferramenta para escolher β e
azimute vendo o efeito real sobre o recurso. Todos os gráficos permitem baixar os
dados (CSV) e a imagem (PNG).

<!-- profundidad: Como ler a comparação POA vs GHI -->
- Se a POA fica **acima** da GHI nos meses de interesse, a inclinação está
  trabalhando a favor (típico no inverno com β > 0).
- Uma POA **menor** que a GHI no verão com β grande é esperada (o sol passa alto) e
  não necessariamente um problema se o projeto prioriza o inverno.
- O pico horário da POA se desloca se o azimute se desvia do Norte (sul geográfico →
  hemisfério norte): útil se a secagem precisa de mais energia de manhã ou de tarde.
<!-- /profundidad -->

## Janela de produção {#ventana}

Se o [modo de análise](?manual=tipologia#modo-analisis) for **Janela**, aqui se
visualiza o lapso escolhido sobre o clima real: serve para verificar que a campanha
cai em datas com recurso razoável antes de rodar o pré-projeto.

---

**Ver também:** [Radiação solar e plano orientado](?manual=radiacion) (fundamento da
transposição), [Técnico · Recurso solar e clima](?manual=tec-emplazamiento)
(download, cache, política de lacunas, equações), [3 · Coletor](?manual=colector)
(quem consome a POA).
