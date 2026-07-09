# Introdução — o que é o Secasol e como usá-lo

O **Secasol** é uma ferramenta de **pré-projeto de secadores solares**
desenvolvida pelo grupo GEEDSP (INENCO, CONICET–UNSa). Integra clima real, física
acoplada de calor e massa, e três escalas de secador — da caixa familiar ao túnel
industrial — em um único aplicativo, livre e acessível pelo navegador.

**Pré-projeto** significa ordem de grandeza: o Secasol serve para explorar,
dimensionar e comparar projetos rapidamente, *antes de cortar a primeira chapa*.
Não substitui o cálculo de detalhe, o ensaio nem a medição.

## Para quem é {#publico}

- **Docentes, pesquisadores e estudantes avançados** de energias renováveis e
  engenharia: o público primário. Todo o modelo físico está documentado neste
  manual (Parte IV), com suas equações, hipóteses e referências.
- **Produtores e técnicos** com uma capacitação básica: o fluxo guiado em 7 seções
  e os guias da Parte II permitem chegar a um pré-projeto sem entrar nas equações.

## Como o programa está organizado {#flujo}

O projeto se constrói percorrendo **7 seções** (menu lateral esquerdo), em ordem.
Cada uma escreve sobre um único projeto central, então você pode ir e voltar sem
perder nada:

1. [**Tipologia**](?manual=tipologia) — qual secador (caixa / armário / grande
   escala) e qual análise (diária / anual / janela).
2. [**Localização**](?manual=emplazamiento) — coordenadas do local; download
   automático do clima (NASA POWER) e orientação do coletor.
3. [**Coletor**](?manual=colector) — tipo, materiais, geometria e banco (não se
   aplica à Caixa).
4. [**Câmara**](?manual=camara) — geometria, paredes, bandejas, produto e carga.
5. [**Auxiliar**](?manual=auxiliar) — apoio elétrico ou a lenha (opcional).
6. [**Motor**](?manual=motor) — ventilador ou chaminé solar.
7. [**Resultados**](?manual=resultados) — a simulação acoplada completa: painel,
   carta psicrométrica, exportação.

**Tenha à mão** para começar: latitude/longitude do local e o produto a secar.

## Salvar e carregar projetos {#guardar}

Cada seção permite salvar sua configuração, e Resultados exporta o **snapshot JSON
completo** do projeto: um arquivo reproduzível que pode ser recarregado no Secasol
(mesma versão ou posterior), versionado ou compartilhado. O relatório final sai
também em TXT e **PDF**.

## Como usar este manual {#como-usar}

O manual abre **em paralelo** ao programa: os botões **📖 Manual** de cada seção
abrem o capítulo correspondente em outra aba do navegador, para você consultar sem
perder seu projeto. (Se o seu navegador bloquear a aba pop-up, habilite os pop-ups
para o site ou abra o link com clique do botão do meio/rodinha.)

Cada capítulo tem **dois níveis de leitura**: o texto principal dá a ideia geral, e
os blocos recolhíveis **🔬 Em profundidade** contêm os detalhes — equações,
correlações, decisões de modelo. Para o detalhe completo de cada subsistema há a
**Parte IV (Referência técnica)**, com a física equação por equação.

Estrutura do manual:

- **Parte II — Guia por seções**: um capítulo por seção do programa, espelho das 7
  abas.
- **Parte III — Fundamentos**: os conceitos transversais —
  [radiação e plano orientado](?manual=radiacion),
  [psicrometria](?manual=psicrometria), [física da secagem](?manual=secado),
  [convenções](?manual=convenciones).
- **Parte IV — Referência técnica**: o modelo físico completo por subsistema.
- **Apêndices**: [implementação em código](?manual=apendice-codigo),
  [glossário](?manual=glosario), [bibliografia](?manual=bibliografia).

## O que torna o Secasol diferente {#distintivo}

- **Física realmente acoplada** — coletor, câmara, produto, ar e auxiliar são
  resolvidos **juntos** com um laço global iterativo, não separadamente.
- **Clima real horário do local** — NASA POWER + pvlib, transposição ao plano do
  coletor; o usuário só informa lat/lon.
- **Três tipologias × três modos de análise** — da caixa de 10 kg ao túnel de
  toneladas; do dia de projeto à campanha real.
- **Secura de saída emergente** — o sistema diz quanto seca; o resultado não é
  forçado.
- **Sistema de avisos** — captura erros de projeto cedo e não falha em silêncio.
- **Validado** — contra o modelo clássico de Hottel-Whillier-Bliss (R²≥0,999) e
  contra um secador industrial real (ADITAL, San Carlos).

<!-- profundidad: Limites honestos do modelo -->
- É **pré-projeto** (ordem de grandeza), não certificação nem medição.
- O catálogo de produtos tem poucos com isoterma **GAB calibrada**; um produto novo
  requer calibração prévia (o sistema avisa quando usa parâmetros genéricos).
- Leitos grossos (> 5 cm): o modelo difusivo superestima a taxa; o software **avisa
  sobre isso**. A difusão interna do produto é uma extensão futura.
- Nos coletores Tipos 2/3/4 algumas propriedades do ar ainda são avaliadas como
  constantes (impacto ~2–3 % no calor útil).
<!-- /profundidad -->

---

**Próximo passo:** [1 · Tipologia](?manual=tipologia), ou direto ao
[índice](?manual=indice) do manual.
