# Introducción — qué es Secasol y cómo usarlo

**Secasol** es una herramienta de **prediseño de secadores solares**
desarrollada por el grupo GEEDSP (INENCO, CONICET–UNSa). Integra clima real,
física acoplada de calor y masa, y tres escalas de secador — desde la caja
familiar hasta el túnel industrial — en una sola aplicación, libre y accesible
por navegador.

**Prediseño** significa orden de magnitud: Secasol sirve para explorar,
dimensionar y comparar diseños rápido, *antes de cortar la primera chapa*. No
reemplaza el cálculo de detalle, el ensayo ni la medición.

## Para quién es {#publico}

- **Docentes, investigadores y estudiantes avanzados** de energías renovables e
  ingeniería: el público primario. Todo el modelo físico está documentado en
  este manual (Parte IV), con sus ecuaciones, hipótesis y referencias.
- **Productores y técnicos** con una capacitación básica: el flujo guiado en 7
  secciones y las guías de la Parte II permiten llegar a un prediseño sin
  entrar en las ecuaciones.

## Cómo está organizado el programa {#flujo}

El diseño se construye recorriendo **7 secciones** (menú lateral izquierdo), en
orden. Cada una escribe sobre un único proyecto central, así que podés ir y
volver sin perder nada:

1. [**Tipología**](?manual=tipologia) — qué secador (caja / armario / gran
   escala) y qué análisis (diario / anual / ventana).
2. [**Emplazamiento**](?manual=emplazamiento) — coordenadas del sitio; descarga
   automática del clima (NASA POWER) y orientación del colector.
3. [**Colector**](?manual=colector) — tipo, materiales, geometría y banco (no
   aplica en Caja).
4. [**Cámara**](?manual=camara) — geometría, paredes, bandejas, producto y
   carga.
5. [**Auxiliar**](?manual=auxiliar) — respaldo eléctrico o a leña (opcional).
6. [**Motor**](?manual=motor) — ventilador o chimenea solar.
7. [**Resultados**](?manual=resultados) — la corrida acoplada completa:
   dashboard, carta psicrométrica, exportación.

**Tené a mano** para empezar: latitud/longitud del sitio y el producto a secar.

## Guardar y cargar proyectos {#guardar}

Cada sección permite guardar su configuración, y Resultados exporta el
**snapshot JSON completo** del proyecto: un archivo reproducible que se puede
recargar en Secasol (misma versión o posterior), versionar o compartir. El
reporte final sale también en TXT y **PDF**.

## Cómo usar este manual {#como-usar}

El manual se abre **en paralelo** al programa: los botones **📖 Manual** de
cada sección abren el capítulo correspondiente en otra pestaña del navegador,
así consultás sin perder tu diseño. (Si tu navegador bloquea la pestaña
emergente, habilitá los pop-ups para el sitio o abrí el enlace con clic de
rueda/botón central.)

Cada capítulo tiene **dos niveles de lectura**: el texto principal da la idea
general, y los bloques desplegables **🔬 En profundidad** contienen los
entresijos — ecuaciones, correlaciones, decisiones de modelo. Para el detalle
completo de cada subsistema está la **Parte IV (Referencia técnica)**, con la
física ecuación por ecuación.

Estructura del manual:

- **Parte II — Guía por secciones**: un capítulo por sección del programa,
  espejo de las 7 pestañas.
- **Parte III — Fundamentos**: los conceptos transversales —
  [radiación y plano orientado](?manual=radiacion),
  [psicrometría](?manual=psicrometria), [física del secado](?manual=secado),
  [convenciones](?manual=convenciones).
- **Parte IV — Referencia técnica**: el modelo físico completo por subsistema.
- **Apéndices**: [implementación en código](?manual=apendice-codigo),
  [glosario](?manual=glosario), [bibliografía](?manual=bibliografia).

## Qué hace distinto a Secasol {#distintivo}

- **Física acoplada de verdad** — colector, cámara, producto, aire y auxiliar
  se resuelven **juntos** con un lazo global iterativo, no por separado.
- **Clima real horario del sitio** — NASA POWER + pvlib, transposición al plano
  del colector; el usuario solo da lat/lon.
- **Tres tipologías × tres modos de análisis** — de la caja de 10 kg al túnel
  de toneladas; del día de diseño a la campaña real.
- **Sequedad de salida emergente** — el sistema te dice cuánto seca; no se
  fuerza el resultado.
- **Sistema de advertencias** — atrapa errores de diseño temprano y no falla en
  silencio.
- **Validado** — contra el modelo clásico de Hottel-Whillier-Bliss (R²≥0.999) y
  contra un secador industrial real (ADITAL, San Carlos).

<!-- profundidad: Límites honestos del modelo -->
- Es **prediseño** (orden de magnitud), no certificación ni medición.
- El catálogo de productos tiene pocos con isoterma **GAB calibrada**; un
  producto nuevo requiere calibración previa (el sistema avisa cuando usa
  parámetros genéricos).
- Lechos gruesos (> 5 cm): el modelo difusivo sobreestima la tasa; el software
  **lo advierte**. La difusión interna del producto es una extensión futura.
- En los colectores Tipos 2/3/4 algunas propiedades del aire se evalúan aún
  como constantes (impacto ~2–3 % en el calor útil).
<!-- /profundidad -->

---

**Siguiente paso:** [1 · Tipología](?manual=tipologia), o directo al
[índice](?manual=indice) del manual.
