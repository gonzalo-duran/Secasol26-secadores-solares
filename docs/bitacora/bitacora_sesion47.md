# Bitácora — Sesión 47 (2026-07-07)

## Tema de la sesión

**Manual de usuario estilo SAM (mejora 36)** — el único ítem pendiente de las 36
mejoras y el pendiente de producto central para la v1.0 (junto con i18n). Sesión
corrida en Claude Code remoto (web); planificación en modo plan con exploración
previa de `docs/notas/seminario/` y de la UI.

## Decisiones de diseño (acordadas con el usuario en plan mode)

1. **Niveles de lectura**: cada capítulo abre con la idea general y despliega los
   entresijos en bloques `st.expander` "🔬 En profundidad"; el detalle completo
   por subsistema vive en capítulos técnicos aparte (Parte IV), enlazados.
2. **Vehículo**: el manual es una **vista de la misma app** ruteada por query
   param (`?manual=<slug>`), abierta en **otra pestaña del navegador**
   (`target=_blank`) — modelo SAM, sin infraestructura de build nueva, mismo
   deploy a HF. Se descartó MkDocs (segundo pipeline + gotcha de static serving
   en el Space).
3. **Alcance**: manual completo en una tanda (21 capítulos), con 2 pilotos
   primero (colector + radiación) para validar KaTeX/expanders/anclas e2e.
4. **Fuente técnica**: los 8 markdown de `docs/notas/seminario/` **adaptados**
   (registro de charla → referencia didáctica; "Highlights de implementación" →
   apéndice de código; Referencias → bibliografía consolidada; se purgan las
   referencias a sesiones internas).

## Qué se construyó

### Infraestructura del visor

- `ui/componentes/manual_contenido.py` — TOC declarativo (`CapituloManual`,
  `CAPITULOS`, `POR_SLUG`, `PARTES`, `SLUG_POR_SECCION`). Sin streamlit.
- `ui/componentes/manual_render.py` — parser puro (`parsear_capitulo`,
  `extraer_enlaces_manual`, `extraer_anclas`, `extraer_esquemas`,
  `separar_ancla_heading`) + `render_bloques` (un `st.markdown` **por bloque**
  para acotar KaTeX e intercalar expanders/esquemas/headings con ancla).
  Errores de sintaxis con código (`MANUAL_PROFUNDIDAD_SIN_CIERRE`, `_ANIDADA`,
  `_CIERRE_SUELTO`, `_SIN_TITULO`).
- `ui/componentes/manual_link.py` — `boton_manual` (anchor pill `_blank`) +
  `enlace_manual_inline`. **Regla dura**: todo enlace al manual desde la vista
  de diseño va con `target=_blank`; sin él, el clic recarga la app y pierde
  `st.session_state.proyecto`.
- `ui/manual.py` — vista stateless: sidebar propio con TOC por partes (enlaces,
  no widgets), breadcrumb, índice generado del TOC (`?manual=indice` o slug
  inválido), navegación anterior/siguiente, `lru_cache` de lectura.
- `Secasol.py` — intercept de `st.query_params["manual"]` **antes** de
  inicializar `proyecto`, con `st.stop()`; enlace global "📖 Manual del
  usuario" en el sidebar.
- `ui/p1..p7_*.py` — `boton_manual(SLUG_POR_SECCION["pN"])` tras el
  `st.header` de cada sección (2 líneas por archivo: import + llamada).
- `.github/workflows/deploy_hf.yml` — línea `cp -r ../manual/ src/manual/`
  (la whitelist del deploy no copiaba `docs/`; el manual vive top-level).

### Sintaxis de los capítulos (markdown + convenciones parseables)

- `<!-- profundidad: Título -->` … `<!-- /profundidad -->` → expander (sin
  anidamiento).
- `<!-- esquema: nombre | caption -->` → `mostrar_esquema` (reusa los 5 SVG de
  `assets/esquemas/`).
- `## Título {#ancla}` → `st.header(anchor="ancla")` (anclas explícitas; no se
  depende de la generación automática de Streamlit, frágil con acentos).
- Enlaces internos `[texto](?manual=slug#ancla)` — markdown puro, sin HTML.
- Ecuaciones `$`/`$$` — KaTeX nativo de `st.markdown` (primer uso de ecuaciones
  renderizadas en la UI del proyecto). Regla editorial: `aligned`, nunca
  `align`; sin `$` literal.

### Contenido — 21 capítulos en `manual/capitulos/`

- **Parte I**: `01_introduccion` (qué es, público, flujo P1→P7, cómo usar el
  manual, límites honestos del modelo).
- **Parte II** (guía por sección, espejo P1–P7): `10_tipologia`,
  `11_emplazamiento`, `12_colector` (piloto), `13_camara`, `14_auxiliar`,
  `15_motor`, `16_resultados`. Fuentes: seminario + `mapa_conexiones.md`
  (incluye la advertencia de que los sliders T/HR de P4 solo influyen en modo
  Constantes, y que el botón de chimenea de P6 es preliminar).
- **Parte III** (fundamentos): `20_radiacion` (piloto; componentes GHI/DNI/DHI,
  SPA, incidencia, Liu-Jordan), `21_psicrometria` (ω/HR, carta, bulbo húmedo),
  `22_fisica_secado` (base seca, a_w, GAB, períodos de secado emergentes),
  `23_convenciones` (SI estricto + tres convenciones de acimut con fórmulas).
- **Parte IV** (técnica, seminario adaptado): `30_tec_emplazamiento`,
  `31_tec_colector`, `32_tec_camara`, `33_tec_industrial`,
  `34_tec_chimenea_motor`, `35_tec_auxiliar`, `36_tec_resultados`. Ecuaciones
  intactas; `08_cierre.md` no genera capítulo (alimenta intro y apéndice).
- **Apéndices**: `90_apendice_codigo` (los "Highlights de implementación" del
  seminario compilados por subsistema + validación HWB/ADITAL/Klein),
  `91_glosario` (términos + tabla de símbolos), `92_bibliografia` (consolidada
  por tema con anclas citables `{#clave}`).

### Tests

`tests/test_ui/test_manual.py` — **142 tests** (funciones puras, sin servidor):
TOC↔disco (declarados existen, sin huérfanos, slugs kebab-case únicos), sintaxis
de profundidad (parsea + errores esperados), **enlaces internos resuelven**
(slug y ancla contra el capítulo destino), ningún capítulo queda aislado,
esquemas existen en `assets/esquemas/`, `$$` balanceado por bloque, sin
`\begin{align}`, `SLUG_POR_SECCION` cubre p1..p7, sin URLs absolutas
hardcodeadas.

## Verificación

- **Suite completa: 1184 passed** (1042 previas + 142 del manual). black + ruff
  limpios.
- E2E visual con Playwright sobre `streamlit run` (contenedor remoto):
  `?manual=indice` (índice por partes), `?manual=colector` (tabla de tipos +
  SVG en iframe + expanders + enlaces), `?manual=radiacion` (KaTeX inline y
  display renderizado, boxed Liu-Jordan OK), breadcrumb y
  anterior/siguiente correctos. Sidebar del manual con capítulo activo
  resaltado.
- Pendiente de verificación **post-deploy en HF** (cuando se pushee a `main`):
  que el iframe del Space permita el popup `_blank` y que `manual/` llegue vía
  el `cp` nuevo del workflow.

## Documentación actualizada

- `docs/notas/mejoras.md` — ítem 36 → `[IMPLEMENTADO]` con detalle.
- `CLAUDE.md` — árbol de capas (+`ui/manual.py`, `manual/capitulos/`), nueva
  subsección "Manual de usuario", nota de whitelist en §Deploy.
- `CHANGELOG.md` — Added en [Unreleased].
- `docs/tareas.md` — estado general S47 + hito completado.
- `docs/mapa_conexiones.md` — nota S47 (el manual no agrega cableado
  widget→campo; vista stateless).

## Pendientes que deja la sesión

- Verificación post-deploy en HF Spaces (popup `_blank` desde el iframe +
  llegada de `manual/` al Space).
- Deep-links contextuales adicionales con `enlace_manual_inline` (ej. junto a
  la carta psicrométrica de P7 → `?manual=psicrometria`) — el helper ya existe,
  no se usó todavía.
- Los pendientes heredados de S45/S46 (aire local en Tipos 2/3/4, hermetizar
  caché climático del deploy, Python 3.14 del Dockerfile) siguen abiertos.
- i18n del manual (los .md son la unidad natural de traducción).
