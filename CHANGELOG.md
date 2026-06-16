# Changelog

Todos los cambios notables a Secasol se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

Hoja de ruta a 1.0 (sin orden estricto):

- Refinamiento de la pestaña de análisis anual (métricas integradas sobre 8760 h).
- Manual de usuario estilo SAM (mejora 36) e internacionalización (idiomas).

---

## [0.14.0] — 2026-06-16

Tanda de mejoras de UX/física a partir del modo industrial (mejoras 25–35 de
`docs/notas/mejoras.md`; sesiones S41–S44).

### Added

- **Espesores de mercado** (mejoras 25 y 26): nuevo helper `ui/componentes/espesores.py`
  (`selector_espesor_mm`) que ofrece medidas estándar de mercado en lugar de un campo numérico
  libre. Maderas (`pino`/`contrachapado_fenolico`) en pulgadas + mm (1/4"…2") en P3 (fondo) y P4
  (paredes); policarbonato alveolar en 4/6/8/10/16 mm en P3 (cubierta). Ambos con escape
  "Otro (personalizado)…".
- **k efectivo del policarbonato según espesor** (mejora 26): mapa `k_efectivo_por_espesor_mm` en
  `cubiertas.yaml` (4→0.05 … 16→0.08 W/m·K) y nuevo campo `ColectorUnidad.k_cubierta_efectivo_W_mK`
  (override opcional, default None) consumido por los motores de colector. Elegir un espesor de
  mercado fija el k efectivo correspondiente sin mutar el catálogo global.
- **Carta psicrométrica del proceso** (mejora 27): nueva carta del proceso completo del secador
  (Ambiente → Salida colector → Entrada cámara → Salida cámara) en P7 (modos Constantes,
  Transitorio y Ventana) y en el reporte PDF. Sin dependencia externa: se construye sobre
  `calculos/psicrometria.py` (parametrizado por `P_Pa` → corrección por altitud). Nuevos
  `calculos/carta_psicrometrica.py` (puro) + `ui/componentes/carta_psicrometrica.py` (Plotly).
  Adiabático (cámara indirecta) vs no adiabático (cámara directa) emerge del balance; valor
  representativo = mediodía solar (POA máx).
- **Espesor del techo translúcido con pérdida conductiva al balance** (mejora 33): nuevo campo
  `ConstruccionCamara.cubierta_translucida_espesor_m` + selector de espesor en P4 (espejo de P3,
  medidas de mercado del alveolar). El techo translúcido ya no solo aporta `Q_rad`: su conducción
  `U_techo = k_efectivo/espesor` (en serie con films interior/McAdams) entra al balance térmico de
  cámara, descontando la cara del techo de la envolvente opaca para no doble-contar
  (`camara_calc` + `camara_termodinamica.resolver_estado_camara`/`simular_secado`/`simular_cascada`).
- **Ventana de producción para CAJA/ARMARIO como multidía real** (mejora 35): el modo
  `ModoAnalisis.VENTANA` deja de ser exclusivo de gran escala. Para CAJA/ARMARIO se comporta como un
  multidía real sobre el lapso `[ventana_inicio, ventana_fin]` con clima horario; P7 enruta el
  pipeline de producción (`_render_ventana`) solo en GRAN_ESCALA y el resto cae al transitorio normal,
  con forzantes construidas por `_construir_forzantes_ventana` (P4).
- **Resultados de colector sobre la ventana en P3** (mejora 34): `_evaluar_ventana` ahora resuelve día
  y noche (sin sol, T_salida ≈ T_amb), expone la serie de T del absorbedor, el perfil T(x) a mediodía
  solar del primer día y las marcas de POA máx + mediodía solar por día; render en dos tabs.

### Changed

- **Gráfica climática de la ventana de producción** (mejora 30): las figuras de P2 ahora cubren el
  dominio temporal completo de la ventana (1 semana, 1 mes, …) en vez de encimar todos los días sobre
  un "día imaginario de 24 h". Helper `_eje_x_temporal` que auto-detecta multi-día y usa eje datetime;
  el día de diseño (DIARIO) conserva las etiquetas de hora.
- **Modelo hidrodinámico de pérdidas de carga** (mejora 29, auditoría con ASHRAE cap. 3/21):
  - ΔP del **producto en cross-flow** ahora usa un modelo combinado general (`_delta_P_producto_crossflow`):
    fricción de pared rugosa (Colebrook con ε = tamaño del producto) + obstrucción por bloqueo
    `C_obs(β)`. Reemplaza la tabla heurística `_K_rugosidad_default`.
  - **Fricción unificada en Colebrook/Haaland** en todo el circuito (se retiró el Blasius del canal
    horizontal de cámara); rugosidad de galvanizado ε≈0.15 mm (ASHRAE Tabla 1).
  - **Pérdidas singulares ampliadas** (taxonomía ASHRAE cap. 21): se agregó el difusor de entrada a
    cámara (`estimar_delta_P_singulares` ahora devuelve `'difusor'`) y se documentó el manifold
    banco→caño como confluencia (Junction).
  - El campo `Camara.bandejas.K_rugosidad_producto` pasa a ser override del coeficiente de obstrucción.
- **Orden de evaluación en la pestaña colectores** (mejora 31): "Evaluación del desempeño del colector
  unitario" aparece antes que "Evaluación del campo de colectores" (gateada a GRAN_ESCALA), reflejando
  el flujo correcto colector → banco.

### Fixed

- **Persistencia de la ventana/año al navegar** (mejora 28): en modo industrial, navegar P1↔P2 varias
  veces ya no pierde la referencia de la ventana de producción ni revierte el año de descarga al
  default 2022. Re-touch curado de widget-keys en `Secasol.py` (antes del dispatch) + sembrado robusto
  del año desde P1 (`_resolver_anio_descarga`).
- **Tope de espesor de fondo de colector** (mejora 25): el espesor de fondo en P3 estaba limitado a
  5 mm, imposible para tableros de madera (3/4" = 19 mm). Ahora hasta 100 mm en madera.
- **Sobreconteo del ΔP de cámara horizontal** (mejora 29): los canales entre bandejas están en
  paralelo, así que el ΔP del sistema es el de un canal (antes se multiplicaba por `n_canales` y
  `n_bandejas`). En túnel con carros, la obstrucción ahora se acumula en serie × n_carros (antes se
  tomaban todas las bandejas como paralelas, subestimando la pérdida por producto industrial).
- **Compensación de presiones del caño maestro** (mejora 32): el preview `estimar_delta_P_cano_maestro`
  metía el caudal total por toda la sección creciente, invirtiendo la compensación al activar el toggle.
  Ahora usa el modelo de flujo acumulado `Q(f)=Q_total·f` con sección local (coincide con la eval de
  campo); `ResultadoCampoColectores` expone `dP_troncal_Pa` + `v_troncal_perfil_ms` y P3 muestra el
  perfil de velocidad del troncal. Física unificada en todos los consumidores (incl. sizing del
  ventilador en P6).

---

## [0.13.0] — 2026-06-10

**Modo secador industrial / gran escala (`Tipologia.GRAN_ESCALA`)** — último hito hacia v1.0.
Hasta ahora `GRAN_ESCALA` era cosmético (idéntico a `ARMARIO`). Se implementó por completo,
con dos subtipos de igual jerarquía: **Batch** (lotes) y **Semicontinuo** (túnel a
contracorriente, estilo ADITAL). Suite: 942 tests.

### Added

- **Ventana de producción** (`ModoAnalisis.VENTANA`): el período de análisis pasa a ser un lapso
  `[inicio, fin]` libre con presets (1 semana / 1 mes / campaña), simulado con clima real horario.
  Subsume el binario DIARIO/ANUAL (que se mantiene para tipologías chicas). Configurable en **P1**.
- **Motor de cámara multi-etapa** (`camara_termodinamica.simular_cascada`): el túnel semicontinuo
  es una cascada de N zonas a contracorriente con avance de columnas por cadencia fija; la sequedad
  de salida es emergente. Batch = caso N=1. Reusa intacto el núcleo físico (evaporación difusiva +
  GAB + coeficientes variables en t de S39). Punto de entrada `camara_calc.calcular_camara_cascada`.
- **Orquestador de ventana** (`simulacion_ventana.simular_ventana` + `balance_global.calcular_todo_ventana`):
  arma forzantes horarias desde clima real (colector hora a hora + caño maestro + auxiliar) y acumula
  producción sobre el lapso. Métrica: kg seco + tasa de régimen (kg/día) + leña consumida.
- **Caño maestro** (`core.colector.CanoMaestro` + `calculos/cano_maestro_calc.py`): manifold de
  sección creciente que colecta el aire de las ramas; modelos de ΔP (fricción Haaland + accesorios),
  ΔT térmica (pérdida convectiva + aporte solar) y uniformidad de distribución. Configurable en **P3**.
- **Híbrido con calendario de arranque** (`core.auxiliar.CargaArranque` + `auxiliar.cargas_arranque`):
  el quemador opera en ventanas horarias de mañana/atardecer (independiente de la irradiancia) en vez
  de potencia constante; acumula leña consumida. Configurable en **P5**. Aplica a todos los modos
  transitorios.
- **UI completa**: P1 (subtipo + ventana), P3 (caño maestro), P4 (topología del túnel: n_zonas +
  cadencia), P5 (calendario de arranque), P6 (ΔP del sistema incluye el caño maestro), P7 (dashboard
  de producción sobre la ventana: producto seco, tasa de régimen, leña + perfil espacial del túnel).
  Serialización JSON + `.txt` con back-compat en todas.
- **Validación de campo** (`validacion/validacion_adital.py`): la cadena térmica del modo industrial
  se contrasta contra las mediciones del secador ADITAL (tesis doctoral, San Carlos, marzo 2009).
  4/4 checks térmicos OK (salida colector 55/78 °C, caño maestro ΔT −2.8 °C, cámara 57 °C) y campaña
  de 5000 kg en ~5 días, todos dentro de los rangos medidos en campo.

---

## [0.12.0] — 2026-06-09

Coeficientes de transporte de cámara variables en el tiempo + limpieza de los inputs de operación
(T_op/HR_op) que eran residuo del motor de capa fina. Suite: 875 tests.

### Changed

- **`h_conv` y `K_m` interiores de la cámara dejan de congelarse** (antes "opción ii" §24.10). El
  motor termodinámico (`camara_termodinamica.simular_secado`) acepta un `coef_transporte_func`
  opcional que recalcula los coeficientes **por paso** desde el estado real del aire
  (`T_ent(t)`, `T_prod(t)`, `ω_ent(t)`, `ṁ(t)`); el closure se arma en
  `camara_calc._calcular_termodinamico` (placa plana + Chilton-Colburn, película en
  `(T_ent+T_prod)/2`). Reevaluar desde cantidades conocidas no rompe la linealidad del sistema
  algebraico por paso. Back-compat: sin el callable se usan los escalares congelados. **Efecto:** en
  los modos Sintético/Día real/Anual los valores de T_op/HR_op ya **no influyen** en el resultado
  (la cámara queda gobernada por el clima/colector y los coeficientes variables); solo son
  condición de borde en modo Constantes.
- **UX P4/P7:** los sliders de "operación de cámara" se renombraron a **aire de entrada** (condición
  de borde) y se eliminó el texto "HR → X_eq vía GAB" (residuo de capa fina). Se aclara que la T y
  la HR **dentro** de la cámara son salida dinámica del motor. Además, en P4 los sliders T_op/HR_op
  se **ocultan** en modo **Día real** (con datos reales disponibles), reemplazados por una nota — no
  intervienen en ese modo (si "Día real" cae a "Sintético" por falta de datos, se siguen mostrando).
  Para leer el modo sin lag, el radio de forzantes pasó a usar `key="cam_forz_sel"`.

### Added

- Tests del callable de coeficientes en `tests/test_calculos/test_camara_termodinamica.py`
  (consistencia con el caso congelado, los coeficientes mandan en el secado, evaluación por paso
  con `ṁ(t)` variable).

---

## [0.11.0] — 2026-06-08

Eliminación del motor de capa fina: la cámara de secado pasa a tener un **único** motor físico (termodinámico, balance acoplado calor-masa). Suite: 872 tests.

### Removed

- **Motor de cámara "capa fina"** (correlaciones empíricas MR(t) de Lewis/Page/Henderson-Pabis/Midilli/Logarítmico). Diagnóstico (ver `docs/bitacora/bitacora_sesion38.md`): era un evaluador de punto único a temperatura pico, insensible al espesor de lecho y a la velocidad de aire reales (el k está calibrado a un espesor y velocidad de laboratorio), no entregaba temperaturas ni flujos, y no existía en los pipelines transitorio/multidía/anual — produciendo tiempos de secado irreales. El motor termodinámico, físicamente completo e independiente, lo reemplaza. Se eliminaron `calcular_tiempo_secado_estatico`, `evaluar_MR`, `calcular_X_eq_gab`, `_interpolar_params_cf` y la dataclass `ResultadosCamara` de `calculos/camara_calc.py`, el selector de motor en P4, y las ramas de capa fina en P7. Tests del motor borrados/migrados.

### Changed

- **`calcular_camara` despacha siempre al motor termodinámico**. El campo `Camara.modo_calculo` queda **vestigial**: `Camara.__post_init__` coacciona el legacy `"capa_fina"` → `"termodinamico"`, de modo que los snapshots `.json` antiguos cargan sin error. Los campos `modelo_capa_fina`/`modelo_isoterma` y los bloques `capa_fina:` de los catálogos se conservan como dato (no los consume el cálculo).
- **`balance_global.resumen_camara`** se simplifica a la única firma de resultado (`ResultadoMotorTermodinamico`).

---

## [0.10.0] — 2026-06-04

Tanda de mejoras UX/UI (backlog `docs/notas/mejoras.md`, ítems 20–24): navegación lateral persistente, subsecciones colapsadas al inicio, consistencia de materiales en cámara, y descarga de imágenes y datos por gráfico. Suite: 919 tests + 2 xfailed.

### Added

- **Descarga de imágenes Plotly con la vista del usuario** (S37, mejora 23). Helper `ui/componentes/graficas.mostrar_plotly` que centraliza el render con la modebar **siempre visible** y descarga **PNG ×2**; al correr en el navegador, captura el zoom/pan/ejes que el usuario dejó (no la figura original). Aplicado a los 22 gráficos de P2/P3/P4/P7.
- **Descarga de los datos numéricos por gráfico (CSV)** (S37, mejora 24). Bajo cada gráfico, botón "⬇ Datos (CSV)" con la serie detrás del gráfico, extraída server-side de `fig.data` (`_fig_a_dataframe`: formato ancho si comparten x, lado a lado si difieren). +4 tests.

### Changed

- **Navegación por secciones movida a una cinta lateral persistente** (S37, mejora 20). `Secasol.py` reemplaza `st.tabs` por un `st.radio` en el sidebar (fijo al scrollear) con dispatch que renderiza solo la sección activa (más rápido y aislado; el estado vive en `session_state.proyecto`). Fix asociado en `ui/componentes/header.py`: se dejó de ocultar todo el `stToolbar` (que escondía el botón nativo de reapertura del sidebar); ahora se oculta solo `stToolbarActions` + `stDecoration`.
- **Subsecciones de P1–P6 colapsadas al iniciar** (S37, mejora 21). Los 18 `st.expander` de subsección arrancan con `expanded=False` (vista compacta; P7 sin colapsar, `st.subheader` sin convertir).
- **Materiales de la cámara con nombres y unidades amigables** (S37, mejora 22). Los selectores de material de P4 (techo translúcido + pared simple/compuesta) muestran la `descripcion` del catálogo (no la key interna) y los espesores pasan de m a mm, alineando P4 con P3. Solo presentación; sin cambios en el modelo.

### Fixed

- **Extractor de datos de gráficos robusto** (S37). `_fig_a_dataframe` (mejora 24) crasheaba en la figura anual de colector (trazas con el mismo `x` pero perfiles `y` de distinto largo por el paso adaptativo del solver). Ahora alinea cada `y` a la longitud del `x` compartido y envuelve la extracción en `try/except` para que un fallo de exportación nunca rompa el render del gráfico.

---

## [0.9.0] — 2026-06-03

Tres mejoras del modelo físico del colector y la cámara: albedo del suelo seleccionable (componente solar reflejada en la POA), coeficiente convectivo interno calculado localmente nodo a nodo, y modo multi-día con días reales consecutivos. Suite: 914 tests + 2 xfailed.

### Added

- **Albedo del suelo seleccionable → POA** (S36, 2026-06-03). Nuevo campo `Emplazamiento.albedo_suelo` (default 0.25) con desplegable de superficies usuales en P3 (`calculos/catalogo_albedos.py`: cemento, suelo desnudo, pasto, arena, urbano, nieve — valores de `pvlib.albedo.SURFACE_ALBEDOS` — + "Personalizado"). Reemplaza el albedo fijo 0.25 que usaba `calcular_POA_horizonte`; alimenta la componente reflejada `GHI·ρ·(1−cos β)/2`, relevante para colectores inclinados/verticales. Se propaga a todos los consumidores de POA (P3, P4, P7, operación anual, transitorio) por el único choke point. Snapshot JSON/TXT y reporte PDF incluyen el valor. +9 tests.
- **Coeficiente convectivo interno LOCAL** (S36, 2026-06-03). `h_int` se calcula **nodo a nodo** (antes un escalar único) con propiedades del aire dependientes de `T_f(x)` (`calculos/propiedades_aire.py`: `k(T), μ(T), Pr(T), cp(T), ρ(T,P)`), Nusselt de entrada térmica local, blending continuo de régimen (Re=2300/10000) y convección mixta de Churchill para baja velocidad/vertical (`nusselt_forzado_local`, `nusselt_natural_canal`, `nusselt_mixto_local`). Aplica a los 4 tipos de colector vía el helper `colector_calc.coef_conveccion_interna_local`. El caudal másico se fija con `ρ(T_entrada)`. En colectores largos a bajo caudal (laminar) el realce de entrada — antes descartado por el ruteo `L/Dh≥50` — eleva `h` ~2×. +17 tests.
- **Modo multi-día: "días reales consecutivos"** (S36, 2026-06-03). En el motor termodinámico de cámara con horizonte Multi-día y forzantes "Día real", P4 ofrece un selector "Repetir día típico" (actual) vs "Días reales consecutivos" (N días calendario del clima NASA desde el día de diseño, con variabilidad real día a día). Nuevo helper puro `clima_calc.slice_n_dias_consecutivos` (recorta N días y trunca en el borde de año avisando). En ARMARIO corre el colector hora a hora sobre el horizonte real (reusa `p3_colector._evaluar_diario`). El consumidor `calcular_todo_transitorio` no cambia (ya procesa horizontes no periódicos). +3 tests.

### Changed

- **`ui/p2_emplazamiento.py` reconstruye `Emplazamiento` con `dataclasses.replace`** (S36) en vez de enumerar los campos a mano. El patrón anterior reseteaba silenciosamente cualquier campo no listado en cada rerun (bug que mataba la persistencia del albedo); `replace` preserva todos los campos no modificados y elimina la clase de bug para futuros campos.
- **Caudal másico del colector con densidad a la temperatura de entrada** (S36, antes `RHO_AIRE_REF` constante a 323 K).

### Fixed

- **Persistencia del albedo del suelo entre reruns** (S36): ver el cambio de `dataclasses.replace` en P2.

### Docs

- **Validación HWB con propiedades variables** (S36). `validacion/validacion_hwb.py` adopta piso de linealidad `R²≥0.99` (el observado baja de 1.0000 a ≈0.999 por la curvatura física de propiedades variables) + chequeo de monotonía de η + rangos de `F_R·(τα)` y `F_R·U_L`. La corrección física se valida por parámetros, no por R². CLAUDE.md y `docs/mapa_conexiones.md` actualizados.

---

## [0.8.0] — 2026-06-01

Corridas paramétricas en P7, refactor de conversiones de ángulo a la capa de cálculo, e integración del proyecto con Obsidian. Migración de deploy a Hugging Face Spaces y motor termodinámico de cámara como default. Suite: 885 tests + 2 xfailed.

### Added

- **Corridas paramétricas (barridos) en P7** (S35, 2026-06-01). El usuario varía un único parámetro curado, corre N simulaciones y compara hasta 3 corridas con gráficas superpuestas por KPI. Disponible en los 3 modos (Constantes, Transitorio, Anual). Resultados efímeros (solo `session_state`, no se persisten al JSON). Nuevos módulos: `calculos/catalogo_parametros_barrido.py` (~15 parámetros con metadata, filtros por tipología y modo), `calculos/barrido_parametrico.py` (motor `correr_barrido` con captura de error por punto — un punto inválido deja hueco sin abortar), `calculos/catalogo_kpis_barrido.py` (6 KPIs fijos + 14 avanzados opt-in, extractores tolerantes a los 3 modos). UI en `ui/p7_resultados.py`. +52 tests.

### Changed

- **Conversiones de acimut movidas a `calculos/conversiones_angulo.py`** (S35, 2026-06-01). Las 4 funciones `acimut_*` (Duffie ↔ UI360 ↔ pvlib) eran matemática pura que vivía en `ui/componentes/unidades.py`; ahora la fuente de verdad es `calculos/` (consumible por la capa de cálculo, que no puede importar de `ui/`). `unidades.py` las re-exporta por compatibilidad. `clima_calc.py` ya no tiene su copia privada. Cambia una invariante documentada: las conversiones de unidades **físicas** (°C↔K, kPa↔Pa, %↔fracción) siguen en `unidades.py`; las de **ángulos** son matemática pura en `calculos/`.

- **`resumen_camara()` como fuente de verdad única** del resumen de cámara (S35). Abstrae las firmas divergentes de `ResultadoMotorTermodinamico` y `ResultadosCamara` en un dict (`t_secado_s`, `masa_agua_kg`, `status`, `convergio`). `balance_global._extraer_t_y_masa` y `ui/p7_resultados._resumen_camara` ahora delegan en él (antes duplicaban la lógica).

- **Default de `Camara.modo_calculo` cambiado a `"termodinamico"`** (S34, 2026-05-29). Hasta la S33 el default era `"capa_fina"` "para preservar comportamiento histórico"; ahora es el motor termodinámico (balance acoplado calor-masa con `solve_ivp`, único soportado por la operación anual). Snapshots `.json` antiguos sin el campo cargan con el nuevo default; los que tienen el campo explícito lo respetan.

- **`st.components.v1.html` → `st.iframe`** en `ui/componentes/esquemas.py`. La API anterior está deprecada y se elimina después del 2026-06-01. `st.iframe` (Streamlit ≥1.57) acepta HTML crudo como `src` y mantiene el aislamiento del CSS de Streamlit que necesitamos para que el tema oscuro no repinte los textos de los SVG.

- **Esquema de tipo de colector en P3 reorganizado**: se ocultó la vista isométrica `colector_tipo1.svg` (no aportaba contenido nuevo) y la sección transversal comparativa de los 4 tipos se movió a un `st.expander` colapsado por defecto, siguiendo el patrón de P1 (circuito de aire) y P4 (esquema de cámara). El SVG queda en `assets/esquemas/` por si se quiere reactivar.

### Docs

- **Integración con Obsidian** (S35, 2026-06-01). Script `scripts/generar_notas_obsidian.py` (solo stdlib, no toca código, idempotente) genera una nota por módulo en `docs/modulos/`. Nuevos documentos de navegación `docs/arquitectura.md`, `docs/tareas.md`, `docs/decisiones.md`, `docs/obsidian-integracion-proyecto.md`. Bloques "Ver también (Obsidian)" con enlaces `[[...]]` al pie de `README.md`, `CLAUDE.md` y `CHANGELOG.md`. `.obsidian/` agregado a `.gitignore`.

### Infrastructure

- **Migración de deploy a Hugging Face Spaces** (S33, 2026-05-23). Repo de GitHub cambiado a privado. La app ahora corre en `https://huggingface.co/spaces/gonzalojduran/Secasol26` vía Docker + template Streamlit. Deploy automático en cada push a `main` mediante GitHub Action (`.github/workflows/deploy_hf.yml`) que sincroniza el código al Space y dispara rebuild. Git LFS configurado en el Space para fonts `.ttf` y logos `.png`. Caché de NASA POWER excluido del deploy — se regenera en runtime.

---

## [0.7.0] — 2026-05-20

Primer release post-prototipo. Cierre físico del modelo de colector solar y del lazo natural por chimenea. Validación contra Hottel-Whillier-Bliss (R²=1.0000). Suite: 774 tests + 2 xfailed.

### Added

- **Chimenea solar** como componente top-level del proyecto.
  - Modelo físico de tiro térmico, fricción y pérdidas singulares (`calculos/chimenea_calc.py`).
  - UI propia en P6 (accesible cuando el motor está apagado — convección natural).
  - Lazo natural acoplado completamente: en modo Constantes y en modo Transitorio el caudal se resuelve por iteración Picard hasta convergencia, re-corriendo el colector con la velocidad efectiva impuesta por el caudal natural.
  - Visualización completa en P7 (ambos modos): métricas instantáneas, series horarias, balance del lazo, advertencia automática si el caudal natural difiere más del 30% del caudal manual configurado en P4.

- **Doble cubierta** para colectores: parámetro `n_cubiertas` (1 o 2) con espaciado configurable. El modelo agrega resistencia serie cubierta–cavidad–cubierta usando Hollands (convección natural inclinada) + radiación entre superficies grises paralelas. Aplica a los 4 tipos de colector. Ganancia típica de eficiencia: +5 a +8 pp.

- **POA (Plane of Array)** computada hora a hora desde DNI/GHI/DHI del clima NASA POWER, propagada como variable de primera clase en las forzantes (`ForzantesAire.I_g_POA_W_m2`). Garantiza que el solver del colector reciba la irradiancia sobre el plano inclinado del absorbedor, no la horizontal del piranómetro.

- **Persistencia por pestaña**: cada una de P3/P4/P5/P6 tiene botones "Guardar configuración (.txt)" y "Guardar configuración (.json)" con snapshot reconstruible. P7 guarda el prediseño completo con todos los inputs, propiedades del catálogo, advertencias estáticas y resultados de simulación si fueron corridos.

- **Carga de configuración guardada (.json)** en P3/P4/P5/P6: file_uploader al inicio de cada pestaña que reconstruye los dataclasses desde el JSON, valida la sección y actualiza la UI.

- **Reporte PDF integral** en P7 (`ui/reporte.py`): header institucional GEEDSP/INENCO con logos, secciones tabuladas para cada pestaña, gráficas reconstruidas desde la sesión, advertencias activas. Tipografía DejaVu Sans incrustada para soporte completo de Unicode.

- **Validación física del modelo de colector** contra Hottel-Whillier-Bliss (HWB) y modelo de Klein para los 4 tipos (`validacion/validacion_hwb.py`, `validacion/validacion_klein.py`). Linealidad perfecta de η vs (T_med − T_amb)/I con R² = 1.0000.

### Changed

- **Entry point renombrado**: el script principal pasa de `app.py` a `Secasol.py`. Ejecutar con `streamlit run Secasol.py`.

- **Chimenea solar** migrada de subcomponente de Colector a componente top-level (`Proyecto.chimenea`). Esto permite chimenea también en tipología CAJA (donde no hay colector externo). Los snapshots `.json` antiguos que traen la chimenea bajo `colector.chimenea` la restauran automáticamente en `proyecto.chimenea`.

- **Sugerido automático de irradiancia** en P7 modo Constantes: ahora calcula POA representativa con `pvlib` sobre el año de clima cargado y toma el quantile 90 (antes salía del quantile 90 de GHI con label engañoso "POA").

- **Adaptación a deprecación de Streamlit**: reemplazo global de `use_container_width=True` por `width="stretch"` (deprecación programada para 2025-12-31).

- **Limpieza de dependencias**: se quita `matplotlib` de `requirements.txt`. La migración a Plotly para gráficas interactivas ocurrió durante el ciclo S23-S29; ningún módulo del proyecto importa matplotlib hoy, y ninguna otra dependencia lo requiere. Instalaciones nuevas pesan ~30 MB menos.

### Fixed

- **Corrección crítica de signos** en el residual algebraico del solver de colector (F1 en los 4 tipos y F3 en Tipo 1). El bug producía raíces espurias con la cara externa de la cubierta a temperaturas físicamente imposibles (≈ −200 °C) y residuos numéricos cero, enmascarando el problema. Impacto al corregir: la eficiencia térmica η baja aproximadamente 25 puntos porcentuales en air heaters (los valores anteriores estaban sobreestimados). Validación HWB con R² = 1.0000 confirma el nuevo modelo.

- **Coherencia local del balance térmico** en colectores Tipos 2/3/4: agregado el término convectivo de la cara interna del fondo (`conv_ci_int = h·ΔT·W_abs`) que faltaba en el balance, restaurando coherencia con la EDO del fluido del canal inferior. Impacto: Δη ≈ −10 a −12 pp en Tipos 2 y 3 (Tipo 4 sin cambio significativo).

- **POA correcta en el solver del colector** en todos los caminos del pipeline (P3 horario/diario, P3 constantes, P7 constantes, P7 transitorio con clima real). Antes, el pipeline transitorio le pasaba GHI etiquetada como POA al solver, lo que subestimaba la T de salida del colector y, en cadena, el tiro térmico y el caudal natural. Para latitudes intermedias (ej. Salta, lat −24.79°) y tilt típico (25–30°) el efecto puede ser de hasta 25–30% en invierno.

### Removed

- **Sección de chimenea de P3**: la UI de chimenea ya no aparece en la pestaña del Colector. Su lugar es P6 (Motor), accesible cuando se desactiva el motor eléctrico.

### Incompatibilidad de archivos guardados

> **Importante para quien tenga snapshots `.json` o `.txt` anteriores a 0.7.0:**
>
> Los archivos cargan sin error, pero las corridas nuevas darán **números distintos** a los originales, por las correcciones físicas y el lazo natural acoplado. Concretamente:
>
> - Las eficiencias η de los colectores serán menores (típicamente −25 pp por el fix de signos F1/F3, y −10/−12 pp adicionales en Tipos 2/3 por el fix F4).
> - El caudal natural por chimenea será distinto al single-pass anterior (típicamente menor cuando antes estaba sobreestimado por correr el colector con velocidad de diseño en lugar de la velocidad efectiva del lazo).
> - La T de salida del colector en pipeline transitorio cambia porque ahora se calcula con POA real, no con GHI.
>
> Los valores anteriores no eran "correctos en otro sentido": eran simplemente erróneos por bugs físicos que se mantuvieron sin detectar. Los resultados post-0.7.0 son los físicamente válidos.

---

## [0.1.0]

Estado de prototipo. 7 pestañas operativas (Tipología/Configuración, Emplazamiento/Clima, Colector, Cámara, Auxiliar, Motor, Resultados). Motor termodinámico de cámara con pared 3 nodos, forzantes horarias multi-día (sintéticas o reales NASA POWER), política anti-rehumectación, eventos de humedad objetivo y temperatura máxima del producto. Tipología CAJA con cubierta translúcida y radiación directa al producto. Capa fina con dependencia de temperatura. 4 tipos de colector de placa plana. Pared compuesta multi-capa de cámara. Pipeline P7 transitoria. UI Plotly. 717 tests + 2 xfailed.

---

## Ver también (Obsidian)

- [[README]] — descripción de producto.
- [[docs/tareas]] — backlog y estado actual.
