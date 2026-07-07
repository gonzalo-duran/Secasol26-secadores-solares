# 1 · Tipología y configuración del análisis

La primera sección define **qué secador** vas a prediseñar y **cómo** se lo va a
analizar. Todo lo que sigue depende de estas dos decisiones: la tipología
determina qué secciones aplican (una Caja no tiene colector externo; una Gran
escala agrega banco, caño maestro y túnel), y el modo de análisis determina qué
pregunta responde el cálculo (¿un día de diseño? ¿el año entero? ¿una campaña
real?).

También se cargan acá los **metadatos** del proyecto (nombre, autor, notas), que
después encabezan el reporte PDF.

## Las tres tipologías {#tipologias}

| Tipología | Escala típica | Qué es |
|---|---|---|
| **Caja** | ~10 kg | Secador directo compacto: la cámara capta el sol por su propia cubierta translúcida. Convección natural. Sin colector externo ni motor. |
| **Armario** | 0–100 kg | Secador indirecto: colector solar de aire + cámara con bandejas. Con ventilador o chimenea solar. |
| **Gran escala** | 100 kg – toneladas | Banco de colectores + caño maestro + cámara industrial (lotes o túnel semicontinuo). |

<!-- esquema: circuito_caja | Circuito de aire del secador tipo Caja. -->

<!-- esquema: circuito_armario | Circuito de aire del secador tipo Armario. -->

**Cuidado al cambiar de tipología con un proyecto avanzado:** pasar a **Caja**
anula el colector y el motor (no aplican), con un aviso previo. Es una cascada
intencional para mantener el proyecto coherente.

<!-- profundidad: Qué implica cada tipología en el modelo -->
- **Caja**: la cámara actúa como colector — el techo translúcido aporta la
  ganancia solar ($Q_{rad}=I_g\,\tau\,\alpha\,A_{rad}$, ver
  [Técnico · Cámara](?manual=tec-camara#techo-translucido)) y el aire se mueve
  por tiro térmico (puede agregarse chimenea solar para reforzarlo).
- **Armario**: la cadena completa colector → (auxiliar) → cámara, con la
  temperatura de entrada a la cámara dada por la salida del colector.
- **Gran escala**: además del armario, aparecen el reparto de caudal entre
  ramas del banco, el caño maestro con su pérdida y ganancia térmica, y los dos
  subtipos de cámara (ver abajo). El análisis pasa a ser por **ventana de
  producción**.
<!-- /profundidad -->

## Modo de análisis {#modo-analisis}

El modo de análisis define las **forzantes** con que se corre el prediseño en
[7 · Resultados](?manual=resultados):

- **Diario** — un día de diseño: o bien condiciones constantes representativas,
  o bien el transitorio horario de un día (real o sintético) elegido por
  criterio (día despejado, día medio, etc.).
- **Anual** — el año completo, mes a mes: cada mes se representa con su **día
  típico** (promedio horario del mes) y se estima la producción anual por
  batches. Habilita la sección "Operación anual" en
  [4 · Cámara](?manual=camara#operacion-anual).
- **Ventana** — un lapso real [inicio, fin] con clima horario continuo: una
  semana, un mes, una campaña de cosecha. Es el modo natural de **Gran escala**
  (dashboards de producción) y también está disponible para Caja/Armario como
  **multidía real**.

La sección ofrece presets de ventana (1 semana, 1 mes, campaña) y el criterio
de selección del día representativo para el modo diario.

## Subtipos de Gran escala {#subtipo}

Con tipología Gran escala se elige además el **subtipo de cámara**:

- **Batch (lotes)** — se carga la cámara, se seca la tanda completa, se
  descarga y se repite. La producción de la ventana sale de encadenar lotes.
- **Semicontinuo (túnel)** — túnel a **contracorriente** estilo ADITAL: el
  producto avanza por zonas mientras el aire caliente entra por el extremo
  opuesto. La topología del túnel (número de zonas y cadencia de avance) se
  configura en [4 · Cámara](?manual=camara).

<!-- profundidad: Por qué contracorriente -->
En el túnel a contracorriente el aire más caliente y seco encuentra al producto
**casi seco** (que tolera temperatura y necesita la máxima fuerza motriz), y el
aire ya humedecido encuentra al producto **fresco** (que igual evapora mucho
porque su actividad de agua es alta). Eso reparte mejor la capacidad de secado
que el flujo paralelo. El modelo resuelve las N zonas en serie con el aire
marchando de la zona caliente a la fría — el detalle está en
[Técnico · Modo industrial](?manual=tec-industrial#semicontinuo).
<!-- /profundidad -->

---

**Ver también:** [Introducción](?manual=introduccion) (el flujo de trabajo
completo), [2 · Emplazamiento](?manual=emplazamiento) (el paso siguiente),
[Técnico · Modo industrial](?manual=tec-industrial) (batch, túnel y caño
maestro en detalle).
