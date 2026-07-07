# 2 · Emplazamiento y recursos climáticos

Acá el proyecto se ancla a un lugar real: con **latitud, longitud y altitud**,
Secasol descarga un **año completo de clima horario** (8760 horas) del servicio
NASA POWER y lo convierte en las series que alimentan todos los cálculos:
temperatura, radiación (global, directa y difusa), viento, humedad y presión.
También se define acá la **orientación del colector** (pendiente y acimut), que
determina cuánta de esa radiación efectivamente llega al plano del colector.

La filosofía de la sección: **el usuario solo pone las coordenadas**; la
descarga, el cacheo, las conversiones de unidades y la transposición al plano
del colector son automáticas.

## Coordenadas del sitio {#coordenadas}

Latitud y longitud en grados decimales (negativos para el hemisferio sur y para
el oeste de Greenwich — ej. Salta ≈ lat −24.8, lon −65.4). La **altitud**
ajusta la presión atmosférica (afecta densidad del aire y psicrometría); si no
la conocés, NASA POWER trae la del punto de grilla. La **zona horaria** alinea
las horas del clima con la hora solar local.

## Descarga del clima {#descarga}

El botón de descarga trae el año elegido desde **NASA POWER** (reanálisis
satelital global, grilla ~0.5°, el mismo servicio que usa la industria
fotovoltaica). La descarga se **cachea en disco**: repetir el mismo sitio y año
es instantáneo y sin red.

<!-- profundidad: Qué se descarga y cómo se convierte -->
Variables horarias: GHI, DNI, DHI [W/m²], temperatura a 2 m [°C→K], viento a
2 m [m/s], humedad relativa [%→fracción], presión superficial [kPa→Pa]. La
conversión a SI ocurre una sola vez en la capa de clima; de ahí en más todo el
sistema trabaja en SI estricto (ver [Convenciones](?manual=convenciones)). El
caché usa una clave criptográfica de (lat, lon, año), así que cambiar
cualquiera de los tres dispara una descarga nueva. El detalle está en
[Técnico · Recurso solar y clima](?manual=tec-emplazamiento#nasa-power).
<!-- /profundidad -->

### Calidad de datos {#calidad}

NASA POWER tiene ocasionales huecos. La política de Secasol es **explícita, no
silenciosa**:

- Huecos de **hasta 3 horas** seguidas se interpolan linealmente (y se informa
  cuántas horas se interpolaron).
- Huecos **mayores** no se rellenan: la sección muestra cuántas horas quedaron
  bloqueadas y te pide una decisión (elegir otro año, otro sitio, o aceptar el
  hueco sabiendo qué días afecta).

## Orientación del colector {#orientacion}

La **pendiente** β (0° = horizontal) y el **acimut** (hacia dónde "mira" el
plano, con 0° = Norte en la entrada de la UI) definen el plano del colector.
Con ellas Secasol **transpone** la radiación horizontal al plano: la
**POA** (*plane of array*), que es la que usan todos los cálculos del colector.

Reglas rápidas: en el hemisferio sur el colector mira al **Norte**; β cercana a
la latitud para uso anual, mayor para favorecer el invierno. El fundamento
completo (componentes de la radiación, ángulo de incidencia, modelo de
Liu-Jordan) está en [Radiación solar y plano orientado](?manual=radiacion).

También se configura el **albedo** del suelo circundante (fracción de radiación
que el suelo refleja hacia el colector), con un catálogo de valores típicos.

## Gráficas: POA vs GHI {#graficas}

Las gráficas de la sección comparan la radiación **horizontal** (GHI) con la
radiación **en el plano del colector** (POA) para el día y el año: son la
herramienta para elegir β y acimut viendo el efecto real sobre el recurso.
Todas las gráficas permiten descargar los datos (CSV) y la imagen (PNG).

<!-- profundidad: Cómo leer la comparación POA vs GHI -->
- Si la POA queda **por encima** de la GHI en los meses de interés, la
  inclinación está trabajando a favor (típico en invierno con β > 0).
- Una POA **menor** que la GHI en verano con β grande es esperable (el sol pasa
  alto) y no necesariamente un problema si el diseño prioriza el invierno.
- El pico horario de la POA se corre si el acimut se desvía del Norte (sur
  geográfico → hemisferio norte): útil si el secado necesita más energía a la
  mañana o a la tarde.
<!-- /profundidad -->

## Ventana de producción {#ventana}

Si el [modo de análisis](?manual=tipologia#modo-analisis) es **Ventana**, acá
se visualiza el lapso elegido sobre el clima real: sirve para verificar que la
campaña cae en fechas con recurso razonable antes de correr el prediseño.

---

**Ver también:** [Radiación solar y plano orientado](?manual=radiacion)
(fundamento de la transposición),
[Técnico · Recurso solar y clima](?manual=tec-emplazamiento) (descarga,
caché, política de huecos, ecuaciones), [3 · Colector](?manual=colector)
(quién consume la POA).
