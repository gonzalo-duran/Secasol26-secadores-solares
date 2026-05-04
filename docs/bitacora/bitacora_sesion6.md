# BITÁCORA — SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

**Última actualización:** Sesión 6 (Tanda 3 paso 2 abierta — shopping list bibliográfica generada, manzana en construcción como producto piloto, estrategia A+C consolidada)
**Estado:** Modelo de datos central definido hasta `Camara` (estructura completa). Catálogo de materiales v1 cerrado. Validaciones de `Colector` especificadas. Esqueleto del catálogo de productos definido (Tanda 3 paso 1). Tanda 3 paso 2 EN CURSO: shopping list bibliográfica generada (16 productos con DOIs), manzana arrancada como piloto con propiedades básicas verificables y slots de cinética/isoterma esperando PDFs en Project knowledge. Sin código aún.

---

## 1\. Contexto y objetivo del proyecto

Software de **prediseño** (no simulación detallada tipo Simusol, ni diseño mecánico final) de secadores solares de alimentos, orientado a usuarios técnicos con formación en transferencia de calor.

**Usuario destinatario:** Ingenieros y estudiantes del curso de posgrado "Secadores Solares" de la Maestría en Energías Renovables (M.E.R.), Facultad de Ciencias Exactas, UNSa, Argentina.

**Espíritu del proyecto:** Académico, comunitario, abierto. Pensado para compartirse vía GitHub entre colegas, alumnos y comunidad científica.

**Nivel de modelado:** Complejidad media. Suficiente para tomar decisiones de ingeniería de prediseño (dimensiones, áreas, caudales, potencias auxiliares) pero sin pretender reemplazar simulación nodal completa.

---

## 2\. Perfil del desarrollador (referencia para Claude)

- Licenciado en Física, Doctor en Ciencias especialidad Energías Renovables.
- Investigador Adjunto CONICET, INENCO–UNSa.
- Docente de Transferencia de Calor y Materia (5° año Lic. Física y Lic. Energías Renovables).
- Docente posgrado M.E.R.–UNSa: Transferencia de Calor y Materia, Energía Solar 1 y 2, Simulación de Procesos Termodinámicos en EERR, Secado Solar Industrial, Eficiencia Energética en la Industria, Domótica para Arquitectura Bioclimática.
- Experiencia: diseño de secadores solares de alimentos a amplia escala de producción.
- Software de simulación de referencia: **Simusol** ([www.simusol.org](http://www.simusol.org)), nivel experto.
- Experiencia de programación: Visual Basic y C++ (oxidado). Entiende lógica de Python pero requiere que Claude codee.
- Datos experimentales: dispone de mediciones de muchos secadores reales (a usar como casos de validación).
- **Acceso bibliográfico:** Biblioteca Electrónica MINCyT (CONICET) — paywall-free a Elsevier (J Food Eng, Drying Technology, Energy Convers Manag, Food Res Int), Wiley, Springer, Tandfonline.

**Hardware:**

- Notebook DELL G15 5515, Ryzen 5000, 32 GB DDR4, GeForce RTX 3050 4 GB.
- Sistema operativo: Fedora 44 con Plasma 6.6.4.
- IDE: VS Code instalado. Estado de Python/integración con VS Code: a verificar.
- Cuenta Claude Pro recién obtenida. Sin integraciones previas.

---

## 3\. Decisiones técnicas tomadas

### 3.1 Stack tecnológico

| Área | Decisión |
| :---- | :---- |
| Lenguaje | Python 3 |
| Cálculo científico | NumPy, SciPy, Matplotlib, pvlib, pandas |
| Interfaz | **Streamlit** (renderizado en navegador, multidispositivo) |
| Motor de EDOs | `scipy.integrate.solve_ivp` |
| Datos climáticos | NASA POWER vía `pvlib.iotools.get_nasa_power` |
| Repositorio | GitHub (cuenta del usuario disponible) — **público desde el inicio** |
| Licencia | **MIT** (permisiva, simple, estándar del ecosistema científico Python) |
| Deploy opcional | Streamlit Community Cloud (gratuito, conecta directo a GitHub) |

### 3.2 Idioma

- Versión inicial: **español** completo (interfaz y código/comentarios).
- Versión bilingüe (español/inglés): considerada como mejora futura.

### 3.3 Sistema de unidades

**Sistema Internacional (SI) estricto en todo el cálculo interno.**

**Convención dura sobre temperatura:**

- Toda variable de temperatura en el modelo de datos central y en funciones de cálculo está en **Kelvin**, sin excepción.
- La conversión a °C ocurre **únicamente** en las dos fronteras:
  - Cuando el usuario ingresa un valor en Streamlit → callback convierte °C → K antes de guardar.
  - Cuando se muestra un valor en pantalla o gráfico → conversión K → °C para display.
- Esta convención debe documentarse en el README y en una guía de convenciones de código del repo.
- Motivo: prevenir el bug clásico de sumar K con ΔT sin convertir.

**Otras unidades internas (SI estricto):**

- Humedad absoluta: kg agua / kg aire seco.
- Humedad relativa: fracción \[0, 1\] internamente, % en UI.
- **Humedad del producto (sólido) en base seca:** `X = m_agua / m_solido_seco` \[kg agua / kg materia seca\]. Decisión interna fija. La UI puede ofrecer entrada/lectura en base húmeda (`X_bh = m_agua / m_total`) con conversión automática: `X = X_bh / (1 - X_bh)`.
- Caudal másico: kg/s.
- Presión: Pa.
- Series temporales: `pandas.DataFrame` con `DatetimeIndex` tz-aware (tz del emplazamiento).

### 3.4 Convención de ángulos solares

- **Hacia el usuario** (interfaz y documentación): convención clásica de Duffie & Beckman adaptada al hemisferio sur.
  - Acimut 0° \= Sur, girando hacia el Norte pasando por el Este (sentido antihorario).
  - Pendiente: 0° \= horizontal, 90° \= vertical.
- **Internamente** (dentro de pvlib y funciones que usen pvlib): convención de navegación.
  - 0° \= Norte, 90° \= Este, 180° \= Sur, 270° \= Oeste.
- **Almacenamiento en el modelo de datos: grados** (no radianes), convención Duffie hacia el usuario.
- La conversión a radianes ocurre dentro de las funciones de cálculo que la requieran.
- La conversión a convención de navegación ocurre en la capa que llama a `pvlib`.
- Se implementará una **capa de conversión** entre ambas convenciones. Documentar para evitar bugs silenciosos.

### 3.5 Modelo físico de los colectores

- **Decisión clave:** modelo con **discretización espacial** a lo largo de la dirección de flujo (no Hottel-Whillier-Bliss estacionario simple).
- Motivación: el usuario quiere poder determinar el **largo óptimo de colector** para una tipología y caudal dados, lo cual exige el perfil T(x) y η(x) y no solo valores globales.
- **Ecuaciones**: el usuario aportará un sistema de **ecuaciones diferenciales acopladas** que representan los balances de energía en placa absorbente, fluido (aire), cubierta y fondo del colector, más una **ecuación de difusión de vapor** para el aporte de vapor de agua al aire en cámara de secado (enfriamiento evaporativo).
- **Motor numérico:** `scipy.integrate.solve_ivp`.
  - Si los balances son estacionarios espaciales (derivada en x), se integra en x.
  - Si se requiere transitorio temporal, método de líneas: discretizar x con diferencias finitas e integrar en t.
- **Optimización de largo de colector:**
  - **Versión inicial (didáctica):** barrido paramétrico graficado — calcular para varios largos y mostrar T\_salida vs L y η vs L.
  - **Versión avanzada (futura):** optimización formal con `scipy.optimize`.
- **Cámara de secado:** sistema EDO acoplado calor-masa (T del aire, humedad absoluta del aire, T y humedad del producto en modelo de capa fina o similar).
  - Para prediseño se evaluará desacoplar colector-cámara: el colector entrega T\_salida(t) como condición de borde a la cámara.
  - Decisión definitiva de acople/desacople se tomará al recibir las ecuaciones específicas del usuario.

### 3.6 Validación

- El usuario dispone de datos experimentales de secadores reales.
- Los datos se almacenarán en `validation_data/` del repo desde el inicio.
- Se desarrollarán **tests automáticos** que validen los modelos contra esos datos para evitar regresiones al refactorizar.

---

## 4\. Arquitectura del software (pestañas)

Diseño modular en pestañas/secciones interconectadas. Cada pestaña lee y escribe sobre un **modelo de datos central** (definido en sección 5).

### 4.1 Pestaña 1 — Inicio

**Función:** elegir tipología de secador y modo de análisis.

#### 4.1.1 Tipologías de secador

**(a) Secador solar tipo caja**

- Carga: pequeña, hasta \~10 kg de producto fresco.
- Usuario típico: doméstico o muy pequeño productor.
- Sin colectores externos: efecto invernadero ocurre en la propia cámara de secado.
- Circulación de aire: convección natural, opcionalmente asistida por chimenea solar.
- **Nota de arquitectura:** modelo físico distinto a las otras tipologías porque la cámara *es* el colector. En el modelo de datos: `proyecto.colector = None` para esta tipología.

**(b) Secador solar tipo armario**

- Carga: media, 0–100 kg de producto fresco.
- Cámara de secado (opaca o translúcida) \+ banco de 1 o 2 colectores solares de aire.
- Circulación: natural o forzada (ventilador o extractor eólico de turbina).
- Auxiliares opcionales: quemador de biomasa, resistencia eléctrica calentadora de aire.

**(c) Secador solar de gran escala con banco de colectores**

- Carga: 100 kg a varias toneladas de producto fresco.
- Circulación de aire: forzada (motor \+ ventilador).
- Cámara de secado (opaca o translúcida) \+ banco de 2 o más colectores con caño maestro de ventilación que dirige el aire caliente a la cámara.
- Auxiliares opcionales: quemador de biomasa, resistencia eléctrica.

**Decisión arquitectural pendiente:** ¿clases/módulos separados por tipología con interfaz común, o un modelo general parametrizado? Intuición preliminar: módulos separados con interfaz común. **A confirmar al armar estructura de carpetas.**

#### 4.1.2 Modo de análisis

**(a) Análisis diario (datos horarios para un día)**

- Selección del día por uno de estos criterios:
  - Día específico elegido por el usuario.
  - Día más frío del año (menor temperatura ambiente media).
  - Día más caluroso del año (mayor temperatura ambiente media).
  - Cuatro días característicos: solsticios y equinoccios.

**(b) Análisis anual completo (datos horarios de los 8760 h)**

- Requiere **vectorización con NumPy** desde el inicio para que sea performante.

### 4.2 Pestaña 2 — Emplazamiento y recursos climáticos

**Función:** ubicar geográficamente el secador, orientarlo, y estimar el recurso energético en el sitio.

#### 4.2.1 Entradas del usuario

- Latitud y longitud del emplazamiento.
- Acimut del secador (convención usuario, ver §3.4).
- Pendiente del plano de colección.
- Altura sobre el nivel del mar (opcional; si el usuario la conoce, la ingresa; si no, se toma de NASA POWER). **Importante para psicrometría** (presión atmosférica local, presión parcial de vapor, balance de masa de agua en cámara).

#### 4.2.2 Datos a obtener de NASA POWER

- Temperatura ambiente.
- Radiación solar global, directa y difusa horizontal (GHI, DNI, DHI).
- **Velocidad de viento a 2 m sobre el suelo** (parámetro WS2M de NASA POWER), ya que el secador se encuentra a nivel de suelo.
- Presión atmosférica.
- Altura del lugar (si el usuario no la ingresó).
- Humedad relativa ambiente.

**Procesamiento condicionado por la elección de §4.1.2** (un día específico o año completo).

**Notas técnicas sobre NASA POWER:**

- Resolución espacial \~0.5° × 0.625°. Para zonas con gradientes orográficos fuertes (Puna, Cuyo, etc.) puede haber error notable.
- Datos horarios disponibles, con latencia de varios meses.
- Se usa `pvlib.iotools.get_nasa_power` (no requests manuales).
- **A futuro:** dejar abierta la posibilidad de alimentar el software con datos de SMN o estaciones del INENCO para validación.

**Política de huecos:**

- Detección automática de datos faltantes y reporte al usuario con métrica de calidad (ej: "3 horas faltantes en el período seleccionado, 0.03%").
- Interpolación lineal automática para huecos cortos (≤3 h consecutivas).
- Para huecos largos (\>3 h): marcar como NaN y bloquear cálculos aguas abajo hasta que el usuario decida una de tres acciones:
  - `INTERPOLAR_FORZADO`: interpolar igualmente.
  - `DESCARTAR_DIAS`: descartar los días afectados.
  - `CAMBIAR_PERIODO`: elegir otro período.

**Caché NASA POWER:** archivos parquet en `data/cache/nasa_power/{hash}.parquet`, hash sobre (lat, lon, periodo\_inicio, periodo\_fin, fuente). Pensado también para que usuarios con colección de sitios trabajen offline (independencia de la API una vez descargados los datos).

#### 4.2.3 Salidas de la pestaña

- Gráficas de: irradiancia global horizontal, irradiancia en plano de colección, temperatura ambiente, velocidad de viento, presión atmosférica, humedad relativa.
- Archivo **CSV descargable** con toda la información recabada.

### 4.3 Pestaña 3 — Definición y dimensionamiento de colectores solares

Estructura de datos definida en sección 5 (Tanda 2 paso 1). Implica el modelo de discretización espacial y el sub-análisis de optimización de largo (§3.5).

### 4.4 Pestaña 4 — Definición y dimensionamiento de cámara de secado

Estructura de datos definida en sección 5 (Tanda 3 paso 1). Modelo acoplado calor-masa (§3.5).

### 4.5 Pestaña 5 — Definición y dimensionamiento de sistema de calentamiento auxiliar

A desarrollar (Tanda 4).

### 4.6 Pestaña 6 — Dimensionamiento de motores

Aplica solo a tipologías con convección forzada. A desarrollar (Tanda 4, junto con auxiliar).

### 4.7 Pestaña 7 — Resultados finales

A desarrollar (Tanda 5, estructura `Resultados` espejo).

---

## 5\. Modelo de datos central

### 5.1 Filosofía

**Estructura general:** dataclasses anidadas (no diccionarios crudos, no pydantic). Objeto raíz `Proyecto` que vive en `st.session_state.proyecto` con secciones bien delimitadas.

**Razones de la elección de dataclasses sobre dict:**

- Tipado explícito (los `type hints` aparecen en el editor y Claude Code los respeta).
- Validación natural con `__post_init__` (chequeo de rangos físicos, atajar bugs temprano).
- Serialización a JSON/YAML casi gratis con `dataclasses.asdict`.
- Documentación viva: la propia clase es la especificación.

**Razón de no usar pydantic en v0:** agrega una dependencia pesada para lo que necesitamos. Si en el futuro hace falta validación más rica, migrar dataclass → pydantic es mecánico.

### 5.2 Vista general

Proyecto

├── meta            (admin)

├── configuracion   (tipología, modo análisis)

├── emplazamiento   (sitio)

├── clima           (datos NASA POWER)

├── colector        (None si tipologia \== CAJA)

├── camara          (a definir Tanda 3\)

├── auxiliar        (a definir Tanda 4\)

├── motor           (a definir Tanda 4\)

└── resultados      (espejo, a definir Tanda 5\)

### 5.3 Separación entrada/salida

Decisión: **opción (b) — sección `Resultados` separada y espejo**. Cada sección guarda solo entradas del usuario; los resultados calculados van en una sección `Resultados` espejo.

**Mecanismo de invalidación de resultados (por hash de entradas):**

Cada bloque de resultados guarda:

ResultadosColector

├── perfiles, globales, ...     \# contenido calculado

├── \_stale: bool                \# ¿está actualizado?

├── \_hash\_entradas: str         \# firma de las entradas usadas para calcularlo

└── \_timestamp: datetime        \# cuándo se calculó

Al entrar a una pestaña, se compara el hash actual de las entradas con el hash usado en el último cálculo. Si difieren, se marca stale y la UI muestra aviso. **No** se borran ni recalculan automáticamente. El usuario decide cuándo recomputar. Esto soporta:

- Navegación libre entre pestañas (volver atrás, modificar entradas, ver qué quedó desactualizado).
- Comparación de escenarios (serializar el `Proyecto` completo bajo un nombre, modificar, recalcular, comparar lado a lado).

### 5.4 Grafo de dependencias

emplazamiento → clima → colector → auxiliar ─┐

                          │                   ├→ camara → motor → global

                          └───────────────────┘

- `clima` depende de `emplazamiento`.
- `colector` depende de `clima`.
- `camara` depende de `colector` y `auxiliar`.
- `motor` depende de `camara`.
- `global` agrega todo.

**Nota:** la irradiancia en plano inclinado (POA) se calcula on-the-fly en el módulo de colector (con `pvlib.irradiance.get_total_irradiance`), **no** se guarda en `Clima`. Esto deja `Clima` como "datos del sitio" puros y reutilizables si el usuario explora distintas orientaciones sin volver a descargar NASA POWER.

### 5.5 TANDA 1 — APROBADA

[Contenido sin cambios. Ver bitácora previa para detalles de Meta, Configuracion, Emplazamiento, Clima, CalidadClima.]

### 5.6 TANDA 2 PASO 1 — APROBADA — Estructura de `Colector`

[Contenido sin cambios. Ver bitácora previa para detalles de ColectorUnidad, BancoColectores, Chimenea.]

### 5.7 TANDA 2 PASO 2 — CERRADA — Catálogo de materiales v1

[Contenido sin cambios. 23 materiales en 5 categorías. Ver bitácora previa.]

### 5.8 TANDA 2 PASO 3 — CERRADA — Validaciones e invariantes de `Colector`

[Contenido sin cambios. Ver bitácora previa para errores duros y advertencias estáticas.]

### 5.9 TANDA 3 PASO 1 — CERRADA — Estructura de `Camara`

[Contenido sin cambios. Ver bitácora previa para detalles de GeometriaCamara, ConstruccionCamara, ConfiguracionBandejas, ConfiguracionFlujo, CargaProducto, ModelosCamara, esquema YAML del producto y catálogo de productos.]

### 5.10 TANDA 3 PASO 2 — EN CURSO — Poblado del catálogo de productos

#### 5.10.1 Estado actual (cierre Sesión 6)

- **Estrategia adoptada:** A+C combinadas.
  - **A:** El usuario consigue PDFs vía MINCyT (CONICET) y los sube al Project knowledge.
  - **C:** Claude entrega para cada producto: estructura YAML cerrada + propiedades básicas con fuente verificable + slots de capa fina/isoterma vacíos con cita esperada. Cuando los PDFs están en Project knowledge, Claude extrae los números y cierra el bloque.
- **Razón del cambio de plan original:** los valores numéricos exactos de las constantes (k, n, a, b por T) están en tablas dentro de PDFs cerrados o en servidores con timeout. Sin acceso institucional, la búsqueda libre no puede pasar de "calidad MEDIA con duda". Con MINCyT del usuario, la cobertura sube a ~80% de literatura relevante con calidad ALTA.

#### 5.10.2 Decisiones cerradas en Sesión 6

- [x] **Modelos de capa fina por producto:** Page + Midilli como mínimo, otros si aparecen.
- [x] **Productos con literatura abundante:** default + 1-2 alternativas en notas (no catálogo ancho con un set por estudio).
- [x] **Ritmo de validación:** producto por producto, validación del usuario antes de cerrar cada uno.
- [x] **`te_yerba`:** entrada ÚNICA con default = yerba mate (Goneli 2014). Té negro queda como nota interna para update futuro o carga manual del usuario. La lista permanece en 19 productos.
- [x] **`apio`:** marcado como `ESTIMADA_POR_ANALOGIA` con perejil. No se hará búsqueda extendida.
- [x] **`yacon`:** default = Shi 2013 (literatura externa). El usuario confirma que no tiene papers propios INENCO con cinética calibrada. Trabajos del grupo (Durán/Condorí) se centran en colector y secador como sistema, no en cinética del producto.
- [x] **Estructura del archivo YAML:** diccionario top-level con clave = `producto_id` (consistente con ejemplo de `yacon` en §5.9.9).
- [x] **Campo nuevo propuesto al esquema:** `propiedades_basicas` ahora incluye `calidad_propiedades_basicas` y `fuente_propiedades_basicas` (paralelos a `calidad_datos`/`fuente` de los modelos). Razón: las propiedades básicas tienen trazabilidad propia (handbooks, hojas de propiedades) distinta de los estudios cinéticos. **Este agregado al esquema queda registrado y se aplicará a los 19 productos.**
- [x] **Convención `humedad_equilibrio_aire_seco`:** se mantiene como valor escalar de fallback para estimación inicial cuando no hay isoterma calibrada. El módulo de cámara debe usar la isoterma con la HR del aire real; este campo es respaldo, no la verdad oficial.

#### 5.10.3 Entregables generados en Sesión 6

1. **`shopping_list_bibliografica_tanda3.md`** (~16 KB):
   - Lista priorizada de papers a conseguir, organizada por producto.
   - Para cada producto: 1-3 papers con DOI, vía de acceso (MINCyT/OA/SEDICI/improbable), qué extraer, y calidad esperada del set.
   - Incluye notas operativas (apio con literatura escasa, coca con `ESTIMADA_POR_ANALOGIA` con yerba mate, charqui con consideración de a_w para riesgo microbiológico, zanahoria con caveat geométrico de rallado vs rodajas).
   - Resumen final con cobertura esperada y productos que requerían decisión del usuario (ya tomadas).
   - **Ubicación**: descargado por el usuario, queda como referencia operativa fuera del Project knowledge a menos que el usuario lo cargue.

2. **`frutas_v0.1_manzana.yaml`** (~9 KB):
   - Bloque YAML de manzana en versión "estructura cerrada + básicas verificables + slots vacíos".
   - Propiedades básicas pobladas con fuente:
     - `densidad_aparente` = 840 kg/m³ (ASHRAE Handbook Refrig. 2018, USDA SR-28).
     - `calor_especifico_seco` = 1810 J/(kg·K) (Mykhailyk & Lebovka 2013, arXiv:1305.1340).
     - `humedad_inicial_tipica` = 7.0 kg/kg ms (USDA SR-28 + Sacilik 2006).
     - `humedad_equilibrio_aire_seco` = 0.10 (Tsami 1990).
     - `calidad_propiedades_basicas`: ALTA.
   - Slots `capa_fina.page`, `capa_fina.midilli`, `isoterma.gab` con cita esperada y `params: null`. Pendiente de Sacilik 2006, Meisami-Asl 2009, Tsami 1990.
   - Comentarios extensivos con razonamiento físico, autodocumentado para alumnos del curso M.E.R.
   - Sirve como **plantilla** para los otros 18 productos.

#### 5.10.4 Productos pendientes en Tanda 3 paso 2

19 productos en 5 archivos. Estado al cierre Sesión 6:

| Archivo | Producto | Estado | Calidad esperada |
|---|---|---|---|
| `frutas.yaml` | manzana | **PILOTO en construcción** (estructura + básicas listas, cinética/isoterma esperando PDFs) | ALTA |
| `frutas.yaml` | durazno | Pendiente | ALTA-MEDIA |
| `frutas.yaml` | yacón | Pendiente (default Shi 2013) | ALTA |
| `hortalizas.yaml` | pimiento_rojo | Pendiente | ALTA |
| `hortalizas.yaml` | cebolla | Pendiente | ALTA |
| `hortalizas.yaml` | papa | Pendiente | ALTA |
| `hortalizas.yaml` | tomate | Pendiente | ALTA |
| `hortalizas.yaml` | zanahoria_rallada | Pendiente | MEDIA (mismatch geométrico rodaja↔rallado) |
| `hortalizas.yaml` | apio | Pendiente — ANALOGIA con perejil | ESTIMADA_POR_ANALOGIA |
| `hortalizas.yaml` | perejil | Pendiente | MEDIA |
| `hortalizas.yaml` | mandioca | Pendiente | ALTA |
| `hojas_aromaticas.yaml` | coca | Pendiente — ANALOGIA con yerba mate | ESTIMADA_POR_ANALOGIA |
| `hojas_aromaticas.yaml` | te_yerba | Pendiente (default yerba mate) | ALTA |
| `hojas_aromaticas.yaml` | oregano | Pendiente | ALTA |
| `legumbres_frutos.yaml` | algarroba | Pendiente — fuentes argentinas accesibles | ALTA |
| `carnes.yaml` | charqui_vacuno | Pendiente — agregar nota sobre a_w | ALTA |

(Conté 16 entradas. Los 3 restantes para llegar a 19 son verificación pendiente del listado original §5.9.10. **Acción pendiente:** revisar al retomar si la lista canónica era 19 o si el conteo verdadero es 16. Si son 19, identificar los 3 faltantes.)

#### 5.10.5 Workflow para sesiones siguientes

1. Usuario sube al Project knowledge los PDFs de prioridad 1 según shopping list, con nombre `producto_AutorAño.pdf`.
2. Claude lee los PDFs, extrae números a slots correspondientes, cierra bloque del producto.
3. Validación turn-by-turn por producto.
4. Para productos con `ESTIMADA_POR_ANALOGIA` (coca, apio): copiar parámetros del producto análogo + nota explícita en YAML.
5. Cuando los 19 productos estén poblados, cerrar Tanda 3 paso 2 y pasar a paso 3 (validaciones de `Camara`).

#### 5.10.6 Ritmo realista estimado

Con esta estrategia, sesiones siguientes deberían cerrar 3–5 productos cada una a calidad ALTA. **19 productos en 4–5 sesiones de trabajo** una vez que los PDFs estén en Project knowledge.

---

## 6\. Plan de trabajo acordado

**Antes de codear:**

1. Definir el **modelo de datos central** (sección 5). EN CURSO — falta `Auxiliar`, `Motor`, `Resultados`. `Camara` estructuralmente cerrada; falta poblar catálogo de productos (Tanda 3 paso 2) y validaciones (Tanda 3 paso 3).
2. Definir la **estructura de carpetas del repo**: `core/`, `app/` o `pages/`, `data/`, `validation_data/`, `tests/`, `docs/`.
3. Definir **convenciones de código**: naming, unidades, docstrings, type hints, formato.
4. Definir **lista preliminar de dependencias** (`requirements.txt`).

**Una vez aprobado lo anterior:**

5. Generar el esqueleto del proyecto: `requirements.txt`, `README.md`, `LICENSE` (MIT), estructura de módulos vacíos, y `app.py` mínimo de Streamlit con pestañas vacías navegables.
6. Crear repositorio en GitHub (público).
7. Comenzar a llenar pestaña por pestaña, **empezando por la Pestaña 2** (emplazamiento y recursos climáticos) porque alimenta a todas las demás.

**Para cada tipología de secador (cuando llegue su turno):**

8. El usuario aporta las ecuaciones diferenciales acopladas de balance de energía en colector \+ ecuación de difusión de vapor en cámara, con notación clara, símbolos definidos, unidades, y referencias bibliográficas si están disponibles.
9. Claude codea los modelos numéricos correspondientes.
10. Tests de validación contra datos experimentales de `validation_data/`.

---

## 7\. Tandas pendientes (orden acordado)

- **Tanda 3 paso 2 (EN CURSO):** búsqueda bibliográfica y poblado del catálogo `data/productos/`. 19 productos en 5 archivos. **Workflow A+C** establecido: usuario sube PDFs vía MINCyT, Claude extrae números. Manzana arrancada como piloto. Shopping list generada como guía.
- **Tanda 3 paso 3:** validaciones e invariantes de `Camara` (errores duros \+ advertencias estáticas, análoga a Tanda 2 paso 3). Lista preliminar de códigos en §5.9.11.
- **Tanda 4:** dataclasses `Auxiliar` \+ `Motor` juntas.
- **Tanda 5:** dataclass `Resultados` espejo (cierra el círculo, define grafo de invalidación concreto). Incluye `Resultados.colector.advertencias_runtime` y `Resultados.camara.advertencias_runtime` (chequeos dinámicos post-solver, complemento de las advertencias estáticas).
- Después: estructura de carpetas, convenciones de código, `requirements.txt`, esqueleto del repo.

---

## 8\. Herramientas Claude Pro recomendadas para este proyecto

| Herramienta | Uso para este proyecto | Cuándo |
| :---- | :---- | :---- |
| **Projects** | Imprescindible. Carga contexto persistente (rol del usuario, bitácora, papers). | Crear desde el inicio. |
| **Artifacts** | Renderizado de código y documentos largos. | Día a día durante desarrollo en chat. |
| **Claude Code** (terminal) | Opera directamente sobre el repo: lee, modifica archivos, corre tests, hace commits. | **Más adelante**, una vez que el repo tenga estructura. |
| **Extensión Claude Code para VS Code** | Integra Claude Code dentro del editor. | Cuando se pase a Claude Code. |
| **Búsqueda web** | Uso puntual (verificar APIs, papers, propiedades). | Casos específicos. |
| **Creación de docx/xlsx/pptx** | NO aplica para este proyecto. | — |

**Aclaración importante (sesión 3):** los archivos generados en chat de claude.ai (este entorno) no se guardan en el Project knowledge automáticamente; el Project knowledge es read-only para Claude. El usuario debe descargar los archivos generados y guardarlos en su máquina, y subir manualmente la bitácora actualizada al Project knowledge tras cada sesión. Cuando se pase a Claude Code, los archivos del repo serán persistentes en disco y trabajaremos con commits reales.

**Aclaración nueva (sesión 6):** para Tanda 3 paso 2 los PDFs de papers científicos (cinética e isotermas) deben subirse al Project knowledge con nombre `producto_AutorAño.pdf`. Claude los lee desde ahí y extrae los números a los YAML correspondientes. **No usar SciHub ni servicios similares**: el usuario tiene acceso institucional CONICET vía MINCyT que cubre la mayoría de la literatura relevante (Elsevier, Wiley, Springer, Tandfonline).

---

## 9\. Decisiones tomadas (síntesis)

[Decisiones de Tandas 1, 2, 3 paso 1 sin cambios. Ver bitácora previa.]

**Decisiones nuevas en Sesión 6 (Tanda 3 paso 2):**

- [x] **Estrategia para poblar catálogo de productos: A+C combinadas.** Usuario consigue PDFs vía MINCyT, sube a Project knowledge; Claude entrega estructura YAML + básicas verificables + extrae números cuando los PDFs están disponibles.
- [x] **Modelos de capa fina:** Page + Midilli como prioridad por producto, otros si aparecen.
- [x] **Múltiples sets por producto:** default + 1-2 alternativas en notas (no catálogo ancho).
- [x] **Validación:** producto por producto, validación del usuario antes de cerrar.
- [x] **`te_yerba`:** entrada única, default yerba mate (Goneli 2014). Té negro como update futuro.
- [x] **`apio`:** `ESTIMADA_POR_ANALOGIA` con perejil. Sin búsqueda extendida.
- [x] **`yacon`:** default Shi 2013. Sin papers propios INENCO con cinética.
- [x] **Estructura YAML por archivo:** diccionario top-level con clave = `producto_id`.
- [x] **Esquema YAML extendido:** `propiedades_basicas` ahora lleva `calidad_propiedades_basicas` y `fuente_propiedades_basicas` propios. Aplicar a los 19 productos.
- [x] **`humedad_equilibrio_aire_seco`:** se mantiene como valor escalar de fallback. La verdad oficial es la isoterma calibrada.

## 10\. Decisiones pendientes

- [ ] **Modular por tipología vs. modelo parametrizado único:** confirmar enfoque modular separado al armar estructura de carpetas.
- [ ] **Acople vs. desacople colector-cámara:** decidir al recibir las ecuaciones específicas.
- [ ] **Tipología CAJA:** modelo físico distinto (cámara \= colector). Definir cuando se aborde el módulo de tipología CAJA, fuera del alcance de Tandas 2-3.
- [ ] **Verificar conteo de productos:** Sesión 6 contó 16 entradas en la lista de §5.10.4; §5.9.10 menciona 19. Identificar los 3 faltantes al retomar.
- [ ] Poblar catálogo de productos (Tanda 3 paso 2 EN CURSO).
- [ ] Definir validaciones de `__post_init__` para `Camara` (Tanda 3 paso 3).
- [ ] Definir `Auxiliar`, `Motor`, `Resultados` (Tandas 4, 5).

---

## 11\. Próximo paso al retomar

**Tanda 3 paso 2 — continuación: extracción de números desde PDFs en Project knowledge.**

### Estado al retomar

- Shopping list bibliográfica generada (descargada por el usuario en Sesión 6).
- Manzana arrancada como piloto (`frutas_v0.1_manzana.yaml`): estructura cerrada, propiedades básicas verificables, slots de cinética/isoterma esperando PDFs.
- Workflow A+C consolidado.

### Acción del usuario antes de la próxima sesión

Conseguir vía MINCyT y subir al Project knowledge los siguientes PDFs (prioridad 1 de la shopping list, en orden de prioridad operativa):

1. **Sacilik & Elicin (2006)** — manzana orgánica. *J Food Eng* 73(3):281-289. DOI:10.1016/j.jfoodeng.2005.01.024
2. **Meisami-Asl et al. (2009)** — manzana var. Golab. *Pakistan J Nutr* 8(6):804-809. (OA, intentar también)
3. **Tsami et al. (1990)** — isotermas frutas (verificar si incluye manzana). *J Food Sci* 55(6):1594-1597. DOI:10.1111/j.1365-2621.1990.tb03583.x
4. **Akpinar et al. (2003)** — papa. *Energy Convers Manag* 44(10):1689-1705. DOI:10.1016/S0196-8904(02)00171-1
5. **Naderinezhad et al. (2016)** — papa. *Food Sci Nutr* 4(1):110-118. (OA)
6. **Doymaz (2007)** — tomate. *J Food Eng* 78(4):1291-1297. DOI:10.1016/j.jfoodeng.2005.12.047
7. **Akpinar et al. (2003)** — pimiento rojo. *J Food Eng* 59(1):99-104. DOI:10.1016/S0260-8774(02)00425-9
8. **Sharma et al. (2005)** — cebolla. *J Food Eng* 71(3):282-286. DOI:10.1016/j.jfoodeng.2005.02.010
9. **Shi et al. (2013)** — yacón. *Energy Convers Manag* 71:208-216. DOI:10.1016/j.enconman.2013.03.032

Con estos 9 PDFs (5 productos: manzana, papa, tomate, pimiento, cebolla, yacón) cerramos el primer batch en una sola sesión.

### Modo de trabajo de la sesión siguiente

1. Verificar PDFs disponibles en Project knowledge.
2. Cerrar manzana primero (es el piloto, ya tiene estructura).
3. Replicar patrón en los siguientes 5 productos.
4. Validación turn-by-turn.

### Para retomar en chat nuevo

Cargar bitácora actualizada (este archivo) más los PDFs descargados al Project knowledge. Abrir con:

> *"Retomemos en Tanda 3 paso 2: extracción de números desde PDFs. Subí al Project knowledge los siguientes PDFs: [lista]. Empecemos cerrando manzana, después seguimos con [lista de productos del batch]."*

Si el usuario sólo consiguió algunos PDFs, igual se puede arrancar y cerrar los productos disponibles. Los demás esperan el siguiente batch.
