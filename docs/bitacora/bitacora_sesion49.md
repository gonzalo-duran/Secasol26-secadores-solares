# Bitácora — Sesión 49 (2026-07-08)

**Tema:** Integración y doble deploy según `docs/notas/plan_integracion_S48.md`:
la **cámara radiativa orientada** (S47, working tree de la Dell) y el **manual de
usuario** (S48, rama remota `claude/hola-code-vs-local-cli-vjvre6`) llegan a `main`
y a producción en dos deploys separados y verificables. Sesión local en la Dell G15
con Claude Code.

**Estado al cierre:** **v0.16.0 en producción** (Space `gonzalojduran/Secasol26`),
`main` = `caf74be`, ambos Actions de deploy en success. Suite **1221 tests**
(1073 cámara + 148 manual), `black` limpio, `ruff` en el baseline preexistente.
Ramas de trabajo borradas (remoto + local).

---

## Qué se hizo (por fase del plan)

- **Fase 0 — asegurar la cámara.** Suite verde (1073) sobre el working tree;
  rama `feature/camara-ampliada`, commit `b36f3c8` (27 archivos, +2173/−200) y
  push. Excluidos a propósito: `.trash/` y la copia local de
  `plan_integracion_S48.md` (la rama del manual ya lo traía en `docs/notas/`).
  Antes hubo que **restaurar la credencial de GitHub**: `~/.git-credentials`
  había quedado solo con la entrada de Hugging Face (pisada el mismo día,
  probablemente por el trabajo en Simusol) — token fine-grained nuevo, playbook
  de la S de 2026-06-08.
- **Fase 1 — cámara → producción.** Merge `--no-ff` a `main` (`6dc9ee6`), suite
  verde, push → deploy OK. **v0.15.0 en producción.**
- **Fase 2 — integrar el manual.** Merge de `main` en la rama del manual
  (`12fafe7`). Conflictos según lo previsto: `CHANGELOG.md` (se conservaron
  ambas entradas) y colisión add/add de `bitacora_sesion47.md` — la de la Dell
  (cámara, 2026-07-06) quedó como **S47** y la del manual (2026-07-07) pasó a
  **S48**, con las menciones ajustadas en `docs/tareas.md` y
  `docs/mapa_conexiones.md`. Después, **actualización del manual a la cámara
  nueva** (commit `d80ce89`): `13_camara.md` ganó "Orientación y techo a un
  agua" y "Superficies translúcidas"; `32_tec_camara.md` documenta el reparto
  producto/aire (I_eq_prod, Q_rad_aire, factores de intercepción) y el término
  nuevo del balance del aire; menciones ajustadas en `10_tipologia`,
  `11_emplazamiento`, `16/36_resultados`, `21_psicrometria`, `91_glosario` y
  `90_apendice_codigo`. `24_catalogo_productos` no necesitó cambios (la
  ampliación no tocó el catálogo). 148 tests del manual + suite completa 1221
  verdes.
- **Fix UX detectado por el usuario probando en local** (`5ac9e6d`): en la
  pestaña del manual no había vía de vuelta al diseñador (el toggle « solo
  colapsa el sidebar del manual). Nuevo enlace **"⬅ Volver al diseñador"** al
  tope del sidebar del manual (navega en la misma pestaña, quita `?manual=`;
  la sesión de diseño de la pestaña original no se toca) + caption aclaratoria.
  Verificado con `AppTest`.
- **Fase 3 — manual → producción.** Bump **0.16.0** (`core/proyecto.py` +
  CHANGELOG: entrada de manual movida de `[Unreleased]` a `[0.16.0]`, con el
  fix y la actualización de capítulos). Merge `--no-ff` a `main` (`caf74be`),
  suite verde, push → deploy OK.
- **Fase 4 — limpieza.** Ramas `feature/camara-ampliada` y
  `claude/hola-code-vs-local-cli-vjvre6` borradas (remoto y local). Esta
  bitácora + estado en `docs/tareas.md` → S49 / v0.16.0.

## Numeración de sesiones (resolución de la colisión)

| Sesión | Fecha | Tema |
|---|---|---|
| S47 | 2026-07-06 | Cámara radiativa orientada (Dell, local) |
| S48 | 2026-07-07 | Manual de usuario (Claude Code remoto) |
| S49 | 2026-07-08 | Esta integración + deploys 0.15.0 / 0.16.0 |

## Continuación de la sesión — i18n F0+F1 (working tree, sin commitear)

Arrancó la **internacionalización ES/EN/PT** según `docs/notas/plan_i18n.md`
(plan cerrado en la S48 remota), con el workflow usual: todo en working tree
local, commit/push cuando el usuario lo pida.

- **F0 (re-censo)**: `scripts/auditar_i18n.py` (nuevo, read-only) mide el
  residuo de literales visibles por archivo: P2 29 · P3 48 · **P4 72** (la
  cámara radiativa sumó strings, como anticipaba el plan) · P5 26 · P6 46 ·
  P7 68 → ~299 para F2–F4 (cota inferior).
- **F1 (infraestructura + piloto)**:
  - `ui/componentes/traducciones.py` (puro): loader YAML con aplanado a claves
    con puntos (stem del archivo = namespace raíz), `traducir()` con fallback
    idioma→ES→default→clave literal, interpolación `str.format` que **nunca
    lanza**; `campo_i18n()` para catálogos (F7); `recargar()`.
  - `ui/componentes/idiomas.py` (estado): `idioma_actual()` (session_state →
    `?lang=` → ES, seguro fuera de runtime), `t()`, `selector_idioma()` 🌐 en
    el sidebar (options estables + format_func, sincroniza `?lang=`).
  - Diccionarios `ui/idiomas/{es,en,pt}/{sidebar,p1}.yaml` (~140 claves por
    idioma; ES copia fiel de los literales; PT-BR).
  - **Fix del bug latente `nav_seccion`** (hallazgo del audit del plan): el
    radio de navegación guardaba el rótulo como valor → con rótulos por idioma
    la selección se rompía. Ahora options = claves estables `p1..p7` +
    `format_func`, con guard de migración para sesiones vivas con el rótulo
    viejo. Verificado: la sección activa sobrevive al cambio de idioma.
  - Migrados: `Secasol.py` (sidebar completo) y `ui/p1_tipologia.py` (piloto —
    los dicts module-level `_ETIQUETAS_*`/`_DESC_*` desaparecen; los radios
    usan enums como options + `format_func`, regla del plan).
  - Tests: `tests/test_ui/test_idiomas.py` (**18**): parseo/valores no vacíos,
    paridad de claves y de placeholders entre los 3 idiomas, unidad de
    `traducir`/`campo_i18n`/`idioma_actual`, cobertura de claves usadas
    (estáticas + familias derivadas de enums), heurística anti-regresión de
    literales en archivos migrados (escape `# i18n: exento`).
  - Verificación e2e con `AppTest`: render ES/EN/PT sin excepciones ni claves
    crudas; `nav_seccion` estable al cambiar idioma; sidebar en inglés en
    vivo. Nota: `AppTest` no refleja escrituras a `st.query_params` (el sync
    de `?lang=` se verifica en navegador).
  - Docs: sección "Internacionalización" en `CLAUDE.md` (reglas duras),
    CHANGELOG `[Unreleased]`, ítem 37 en `mejoras.md`, `tareas.md`.
- **Suite: 1239 passed** (1221 + 18). `black` limpio; `ruff` en el baseline
  preexistente (54).
- **F2 (P2 + P3)**: `ui/p2_emplazamiento.py` y `ui/p3_colector.py` migradas
  **completas** a `t()` — widgets, helps, métricas, spinners, warnings, tabs,
  y también las **figuras Plotly** (nombres de serie, títulos de ejes y de
  figura, marcas de mediodía/POA máx), la tabla mensual y los encabezados del
  CSV exportado. Nuevo diccionario compartido `graficas.yaml` (meses
  abreviados como lista CSV en una clave, ejes y series comunes). Los dicts
  module-level de P3 (`_TIPOS_COLECTOR`, `_TIPOS_HELP`, `_MES_ABBR`)
  eliminados (regla: nunca `t()` a nivel de módulo); los snapshots .txt/.json
  usan `t()` (exportan en el idioma de la sesión). Passthroughs de mensajes de
  `calculos/` y de advertencias de `core/` marcados `# i18n: exento` (son F5).
  ~370 claves nuevas por idioma (p2+p3+graficas). Suite **1241** (+2),
  AppTest: P2 y P3 renderizan en ES/EN/PT sin claves crudas. Gotcha AppTest
  adicional: `set_value().run()` re-evalúa `format_func` fuera del contexto
  del script → para verificar secciones se pre-siembra
  `at.session_state["nav_seccion"]` antes del primer `run()`.

- **F3 (P4 + P5 + P6)**: las tres pestañas migradas **completas** a `t()`.
  P4 (Cámara, el archivo más grande de la UI, ~3100 líneas) — producto,
  geometría/orientación, vidriado y caras translúcidas, materiales de pared
  (simple/compuesta), bandejas/carros, túnel semicontinuo, flujo, aire de
  entrada, forzantes+horizonte, operación anual, resultados TD/capa fina y las
  dos figuras Plotly (curva de secado + panel termodinámico de 4 subplots).
  P5 (Auxiliar) — tipo/modo por enum, biomasa (combustibles por id estable),
  resistencia, calendario de arranque, efecto térmico, resumen. P6 (Motor) —
  caudal, pérdidas de carga por componentes/total, ventilador, resultados, y
  toda la sección de **chimenea solar** con extractor eólico (terreno z₀ por
  clave estable). **Patrón clave de F3**: varios radios/selectores guardaban el
  rótulo traducido como valor y luego hacían string-matching (`"Constantes" in
  forz_sel`, `md_sel == "Días reales consecutivos"`, `tipo_pared.startswith`,
  z₀ por label) → se migraron a **options con claves estables + format_func**,
  derivando la lógica de la clave, no del texto; la sección "Aire de entrada"
  de P4 lee `cam_forz_idx` (índice) en vez del label. Dicts module-level de
  opciones (combustibles, z₀, dirección de flujo, cara de caída) eliminados o
  convertidos a listas de ids. ~600 claves nuevas por idioma (p4+p5+p6).
  Passthroughs de `calculos/`/`core/` y advertencias marcados `# i18n: exento`
  (F5). Suite **1244** (+3), AppTest: P4/P5/P6 renderizan en ES/EN/PT sin
  claves crudas. `ruff` bajó de 54 a 52 (se limpiaron dicts). Residuo F4: solo
  P7 (~68 literales).

- **F4 (P7 + componentes compartidos)**: `ui/p7_resultados.py` (2400 líneas)
  migrada **completa** — dashboard integrado (colector, auxiliar, cámara,
  motor, chimenea, balance, ciclo), pipeline transitoria con sus 5 figuras
  Plotly, corridas paramétricas (con `progreso_punto`/tarjetas/tablas),
  ventana de producción (gran escala), operación anual detallada (tabla 12
  meses + figura), tabla de resultados completa y bloque de guardado
  (.txt/.json/PDF). Radio de modo de cálculo (transitorio/constantes) migrado
  a claves estables. **Componentes compartidos** (parte del plan de F4):
  `ui/componentes/carta_psicrometrica.py` (cromo de la figura: ejes, series,
  isentálpica, nota adiabática), `graficas.py::grafica_termodinamica_camara`
  (panel TD de 3 subplots usado en P7), `espesores.py` (selector "Otro…" +
  espesor personalizado) y `esquemas.py` (fallback de SVG faltante) — vía
  `graficas.yaml` con namespaces nuevos `carta`/`termo` + nuevo `comun.yaml`.
  Los generadores de snapshot `.txt`/`.json` de P7 (`_texto_resultados_completo`,
  `_bloque_meta_emplazamiento_clima`, `_json_*`) quedan en ES (artefactos de
  exportación, no `st.*`; su i18n sería F6). Gotcha YAML: la clave `no:` sin
  comillas se parsea como booleano `False` → todas las `"no":` quedan
  quoteadas. **Toda la UI visible de las 7 pestañas está traducida.** Suite
  **1245**, AppTest P7 en ES/EN/PT sin claves crudas. Residuo del audit: solo
  la vista del manual (`manual.py` 7 + `manual_render.py` 1) que es F8, más un
  comentario en `header.py` (falso positivo).

- **F5 (advertencias por código)**: stub `ui/componentes/advertencias_widget.py`
  implementado como **render único** — `texto_advertencia(adv, lang)` traduce
  `advertencias.<CODIGO>.mensaje/.sugerencia` interpolando `adv.contexto`, con
  `default=adv.mensaje/.sugerencia` (un código sin plantilla YAML muestra igual
  el ES de core, nunca la clave cruda); `render_advertencias(advs, *,
  con_sugerencia)` unifica los 4 renders inline de P3–P6 (P3 con sugerencia, P4–P6
  sin). Nuevo `advertencias.yaml` en los 3 idiomas con **43 códigos** (el censo
  creció de los 39 del plan por las CAM_*/CONS_* de la cámara ampliada S48).
  Donde el mensaje ES de core interpolaba una constante ausente de `contexto`
  (`_V_MAX_MS`, `_FRACCION_DUCTOS`, umbrales de temperatura en K) la plantilla se
  reformula sin el número (o baja la constante a literal): **todos los placeholders
  ⊆ claves de `contexto`** (test dedicado). Se eliminaron los `_ICONOS_SEVERIDAD`
  locales y el import `Severidad` de P4/P5/P6 (quedaban solo para el render); P3
  conserva `Severidad` por los conteos del resumen. P7 queda igual: sus
  `res.advertencias` son `list[str]` de runtime de `calculos/`, no `Advertencia`
  con código → ES (`# i18n: exento`). Tests F5 (+4): censo de códigos de core con
  plantilla en los 3 idiomas, placeholders ⊆ contexto, y fallback de
  `texto_advertencia` al ES de core. Suite **1249**. E2E: los 43 códigos ×3
  idiomas interpolan sin placeholders crudos ni caída al default.

- **F6 (reporte PDF)**: `ui/reporte.py` migrada a i18n. `generar_reporte_pdf`
  gana el parámetro `idioma` (P7 pasa `idioma_actual()`); un closure
  `tr = _hacer_tr(idioma)` (`tr("colector.titulo") → traducir("reporte.colector.titulo",
  idioma)`) se enhebra a portada, las 7 `_seccion_*`, los 4 recolectores de
  figuras `_figuras_p{2,3,4,7}` y el header/footer de `_crear_doc`. Nuevo
  namespace `reporte.*` (244 claves/idioma) en `ui/idiomas/{es,en,pt}/reporte.yaml`.
  `_fmt` gana `tr=` opcional para los booleanos (Sí/No). La tabla de
  `_bloque_advertencias` retraduce el mensaje **por código** reusando
  `advertencias.*` (F5) — `tr.idioma` se expone en el closure para eso, con
  fallback al ES serializado. Valores numéricos/unidades/códigos de enum quedan
  en ES v1 (`reporte.py` usa reportlab, no `st.*`, así que el audit no lo
  escanea). **Bug latente de F2 corregido**: el valor `NO` (noroeste) del
  selector de orientación de P2 y la clave `no:` de varios YAML se coercían a
  booleano (mostraban "False"/clave cruda) — se quotearon; nuevo guard
  `test_yaml_sin_coercion_de_tipos` escanea el YAML crudo de toda la familia.
  Tests F6 (+7): `test_reporte_i18n.py` (tr por idioma, PDF válido en los 3
  idiomas con snapshots sintéticos, retraducción por código + fallback). Suite
  **1256**. E2E: PDF generado en ES/EN/PT (~74 kB) sin claves crudas.

- **F7 (catálogos)**: los YAML de `catalogo/materiales|productos/` ganan
  `descripcion_en`/`descripcion_pt` junto a cada `descripcion` (**39 items**:
  19 materiales + 20 productos; insertados con un script textual que preserva
  comentarios/orden, keyed por `(archivo, id)` porque `manzana` existe en dos
  archivos con descripciones distintas). Nuevo helper
  `ui.componentes.idiomas.t_catalogo(datos, default)` (envuelve `campo_i18n` con
  `idioma_actual()`); lo usan los `format_func` de los selectores de material de
  P3/P4/P6 y la etiqueta de producto de P4 (`_productos_disponibles`), y el PDF
  (F6) resuelve las descripciones de material vía `campo_i18n(props,
  "descripcion", tr.idioma)` — el snapshot `props_catalogo` serializa el dict
  completo (`_mat_props`), así que arrastra las traducciones. `notas`/`fuente`
  quedan ES v1; los bloques `capa_fina:` intactos. Los generadores `.txt`/`.json`
  (`_texto_config_*`, `_texto_resultados_completo`) **no** se traducen (ES). Tests
  F7 (+2): `descripcion_en/_pt` presentes y no vacías en los 39 items;
  `campo_i18n` sobre catálogo real (con `notas` cayendo a ES). Suite **1258**.

- **F8 (manual multiidioma — infraestructura)**: los 23 `.md` se movieron a
  `manual/capitulos/es/` (ES canónico); nuevo `manual_contenido.ruta_capitulo
  (archivo, lang) → (ruta, es_fallback)` con **fallback a ES**. El visor
  `ui/manual.py` se reescribió lang-aware: chrome traducido vía `manual.ui.*`
  (nuevo `manual.yaml` ×3), títulos del TOC vía `manual.toc.<slug>.*` con
  **fallback al ES de la tupla `CAPITULOS`** (por eso NO se agregan claves
  `manual.toc.*`/`manual.parte.*` hasta F9). El idioma sale de `idioma_actual()`
  (query param `?lang=` en la pestaña del manual = sesión nueva). **Todos los
  enlaces propagan `&lang=`**: sidebar, índice, breadcrumb, prev/next,
  `boton_manual`/`enlace_manual_inline` (desde la vista de diseño, con
  `idioma_actual()`), el enlace global de `Secasol.py`, y los enlaces internos
  del markdown reescritos por `manual._propagar_lang` (regex sobre
  `](?manual=slug#ancla)`). Capítulo sin traducción → se muestra el ES + aviso
  `manual.ui.solo_es`. `render_bloques` gana `label_profundidad` (el "🔬 En
  profundidad" traducido). El deploy copia `manual/` recursivo → sin cambios en
  `deploy_hf.yml`. **`auditar_i18n.py` = 0** literales (se marcaron 2 falsos
  positivos: `"\n".join` separador y código comentado en `header.py`). Tests F8
  (+4 en `test_manual.py`): ES completo en `es/`, `ruta_capitulo` fallback,
  `_url`/`_propagar_lang` con `&lang=`, chrome traducido. AppTest e2e: `?manual=
  colector&lang=en` (aviso solo_es + "Back to the designer" + enlaces lang=en) y
  `?manual=indice&lang=pt` ("Manual do Secasol") sin excepción. Suite **1262**.

## Pendientes

- **i18n F9 (único trabajo grande que queda)**: traducir los 22 capítulos del
  manual a EN y PT (capítulo a capítulo, en `manual/capitulos/{en,pt}/`), más las
  claves `manual.toc.*`/`manual.parte.*` de los títulos del TOC. La infra ya está
  (F8): al dejar el `.md` traducido en la carpeta del idioma, el visor lo toma
  solo. Verificación visual de F1–F8 en navegador (selector 🌐, `?lang=en`
  directo, una advertencia de cada severidad, descripciones de material/producto,
  el **PDF exportado en cada idioma**, y el **manual con `?lang=`**).
- **Verificación post-deploy manual en el Space** (checklist Fase 3 del plan):
  botón "📖 Manual" desde el iframe de HF (pop-ups), `?manual=indice`, KaTeX en
  un capítulo con ecuaciones (`?manual=radiacion`), carga de `.json` intacta, y
  **un caso de referencia de cámara** local vs Space (lección S46) — panel
  "🔧 Entorno" para comparar versiones.
- Verificación manual e2e de barridos en Streamlit (etapa 12, pendiente
  histórico).
- v1.0: i18n (`docs/notas/plan_i18n.md`) + refinamiento del análisis anual.
