# Bitácora — Sesión 50 (2026-07-09)

**Tema:** Fase **F9** del plan i18n (`docs/notas/plan_i18n.md`) — traducción
completa del manual de usuario a **inglés y portugués (PT-BR)** — y **release
1.0.0**, la primera versión mayor de Secasol. Sesión local con Claude Code.

**Estado al cierre:** **v1.0.0 en producción** (Space `gonzalojduran/Secasol26`),
`origin/main` = `5b045d6`, deploy a HF disparado por el push. Suite **1261
passed + 1 skipped**, `black`/`ruff`/`auditar_i18n.py` limpios. El manual queda
**100 % traducido a ES/EN/PT** (contenido + índice + navegación). Con esto se
cierran todos los hitos de la hoja de ruta a 1.0.

---

## Qué se hizo

### 1. Decisión de arranque (prioridad y orden)

El plan F9 dejaba abiertas dos decisiones (memoria de S49). Se resolvieron con el
usuario:

- **Prioridad de idioma:** **EN primero completo, luego PT** ("el idioma del
  hermano país").
- **Orden de capítulos:** **Parte II (uso) primero**, luego Parte III
  (fundamentos), Parte IV (técnica) y apéndices.

### 2. Traducción del contenido — 22 capítulos × 2 idiomas

Se crearon `manual/capitulos/en/` y `manual/capitulos/pt/` con los **23 archivos**
cada uno (~22.100 palabras por idioma). Bloques traducidos, en orden:

- **Parte II — Guía por secciones:** `01_introduccion`, `10_tipologia`,
  `11_emplazamiento`, `12_colector`, `13_camara`, `14_auxiliar`, `15_motor`,
  `16_resultados`.
- **Parte III — Fundamentos:** `20_radiacion`, `21_psicrometria`,
  `22_fisica_secado`, `23_convenciones`, `24_catalogo_productos`.
- **Parte IV — Referencia técnica:** `30_tec_emplazamiento`, `31_tec_colector`,
  `32_tec_camara`, `33_tec_industrial`, `34_tec_chimenea_motor`,
  `35_tec_auxiliar`, `36_tec_resultados`.
- **Apéndices:** `90_apendice_codigo`, `91_glosario`, `92_bibliografia`.

**Sintaxis propia del manual preservada** en cada archivo: bloques
`<!-- profundidad: Título -->` (título traducido), `<!-- esquema: id | caption -->`
(id intacto, caption traducido), enlaces internos `?manual=slug` (el `&lang=` lo
propaga el render), anclas `{#ancla}`, y **todas las tablas y ecuaciones KaTeX
exactas**. Detalles: los **glosarios se re-alfabetizaron** por idioma; las **rutas
de código** del apéndice quedan intactas; en la tabla de productos se tradujeron
los nombres comunes conservando los **nativos** (yacón, algarroba/alfarroba,
charqui, yerba mate/erva-mate, coca).

### 3. Índice y navegación del visor (claves TOC)

Último pendiente de F9: los rótulos del índice/sidebar/breadcrumb/prev-next caían
al ES de la tupla `CAPITULOS`. Se agregaron a `ui/idiomas/{en,pt}/manual.yaml`:

- `manual.toc.<slug>.titulo` + `.descripcion` (23 capítulos).
- `manual.parte."0".."4"` (5 partes: I, II, III, IV, Apéndices).

**Diseño respetado** (documentado en los YAML): el **ES canónico vive en la tupla
`CAPITULOS`** — `ui/manual.py::_titulo/_descripcion/_parte` resuelven por
`traducir("manual.toc.…", lang, default=cap.titulo)`, así que **ES no lleva esas
claves** (solo EN/PT). **Gotcha resuelto:** las claves de parte se quotearon
(`"0":`) para que el flatten dé `manual.parte.0` y matchee el
`f"manual.parte.{idx}"` (idx `int` de `enumerate`).

### 4. Tests

- **`test_ruta_capitulo_fallback_a_es`** (`test_manual.py`): asumía EN sin
  traducciones (usaba `CAPITULOS[0]`). Reescrito para buscar dinámicamente un
  capítulo sin `.md` en `en/` y hacer `pytest.skip` cuando ese idioma esté
  completo (hoy skippea porque EN está 100 %).
- **`test_paridad_de_claves_entre_idiomas`** (`test_idiomas.py`): se agregó la
  exención `_FAMILIAS_SOLO_EN_PT = ("manual.toc.", "manual.parte.")` — exentas de
  la comparación contra ES, **pero exigiendo paridad EN↔PT** entre ellas (ninguna
  traducción del TOC puede quedar a medias).
- **`test_manual_ui_chrome_traducido`**: antes verificaba el fallback a la tupla;
  ahora comprueba `EN="3 · Solar collector"`, `PT="3 · Coletor solar"`, `ES` por
  default de la tupla.

### 5. Release 1.0.0

- `VERSION_SOFTWARE` `0.17.0` → `1.0.0` (`core/proyecto.py`).
- `CHANGELOG.md`: entrada **`[1.0.0] — 2026-07-09`** (Added F9 contenido + TOC;
  Changed versión + fin del aviso "solo en español" para EN/PT). `[Unreleased]`
  queda con mejoras post-1.0 (refinamiento anual + pérdidas IR nocturnas).
- Commit **`5b045d6`** (52 archivos, +6510/−24) + **push a `main`** → **deploy a
  HF Spaces disparado**. Push sin trabas (no hizo falta el playbook de
  credenciales).

**Verificación local:** `black` ✓, `ruff` ✓, `auditar_i18n.py` = 0, suite **1261
passed + 1 skipped** (el −1 vs 1262 es el skip del test de fallback, que ahora
skippea porque EN está 100 %).

---

## Pendiente para la próxima sesión

- **Verificación post-deploy en el Space** (lección S46, deploy HF no hermético):
  el usuario **corrió una prueba en el Space y detectó "arreglitos"** — se
  abordan en otra sesión. Chequear que el rebuild quedó OK y que el manual EN/PT
  se sirve bien tras el proxy de HF (botón 📖, `?manual=indice&lang=en`/`&lang=pt`,
  KaTeX, selector 🌐, carga `.json`).
- **Mejoras post-1.0** (del `[Unreleased]`): refinamiento de la pestaña de
  análisis anual (métricas sobre 8760 h) y pérdidas IR nocturnas del vidriado +
  discretización vertical del producto por bandeja.

---

## Notas

- **`docs/mapa_conexiones.md` sin cambios:** F9 fue traducción de contenido
  (`.md` del manual + YAML de i18n); no agregó ni movió widgets, campos del core
  ni consumidores.
- Convenciones i18n ya consolidadas en `CLAUDE.md` §Internacionalización y en la
  memoria `reference-i18n-convenciones` (no requirieron cambios en F9).
