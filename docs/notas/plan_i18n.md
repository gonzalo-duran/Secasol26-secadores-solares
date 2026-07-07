# Plan de internacionalización (i18n) — Secasol ES/EN/PT

> Plan acordado en la S47 (2026-07-07), para ejecutar en fases DESPUÉS de la
> integración S48 (cámara ampliada + manual → main; ver
> `plan_integracion_S48.md`). No abrir la rama i18n antes de ese merge.

## Contexto y decisiones cerradas

Secasol es 100% monolingüe español, sin ninguna infraestructura de traducción.
Censo del volumen traducible: **~817 strings de UI** (80% en p3–p7), **~280 del
PDF**, **~115 de gráficas Plotly**, **39 advertencias** (mensaje+sugerencia),
**~206 errores técnicos**, **39 descripciones de catálogo**, **~40 etiquetas de
enums**, y el **manual (22 capítulos, ~3.100 líneas)**.

Decisiones tomadas con el usuario (no re-discutir):

1. **Mecanismo: `t()` propio + diccionarios YAML por idioma** (es/en/pt), claves
   jerárquicas estables, fallback idioma→ES→clave. Sin gettext/babel, sin
   dependencias nuevas. (Se evaluó gettext: su fortaleza —traductores externos
   con Poedit/Weblate— no aplica al flujo actual "Claude traduce + Gonzalo
   revisa"; si algún día se suma un equipo de traductores, migrar es posible.)
2. **Advertencias: por código en la UI.** core/ no se toca; la UI traduce
   mapeando `adv.codigo` → plantilla por idioma interpolando `adv.contexto`,
   con fallback al `mensaje` ES. Los ~206 `ValueError/RuntimeError` técnicos
   quedan en español.
3. **Manual: solo infraestructura multiidioma ahora** (carpetas
   `manual/capitulos/es|en|pt/` + fallback a ES con aviso); la traducción de
   los 22 capítulos es la fase final, capítulo a capítulo.
4. **Selector: 🌐 en sidebar + query param `?lang=`** (session_state; el query
   param permite que el manual —pestaña aparte, stateless— herede el idioma y
   que se compartan URLs pre-configuradas del Space). Default ES.
5. **Números y formato: v1 mantiene punto decimal y formatos actuales** en los
   3 idiomas (decisión consciente; candidato a v2).

Dos hallazgos del audit que el plan corrige de paso:

- **Bug latente `nav_seccion`**: el radio de navegación (`Secasol.py`,
  `key="nav_seccion"`) guarda el **rótulo** como valor — con rótulos que
  cambian por idioma, la selección se rompería al cambiar de idioma. Migrar a
  options estables (`p1`..`p7`) + `format_func` (primera tarea de F1).
- **`contexto` incompleto en algunas advertencias**: hay mensajes/sugerencias
  ES que interpolan constantes que no están en `contexto` (ej.
  `GEO_VELOCidad_BAJA` usa `_V_MAX_MS`). Las plantillas EN/PT solo pueden
  interpolar claves presentes en `contexto`; donde falte, se reformula la
  traducción sin ese número (+ fallback runtime a ES como red).

## 1. Arquitectura del módulo i18n

Patrón probado del manual: **loader puro separado del getter con estado**.

### `ui/componentes/traducciones.py` (nuevo — puro, sin streamlit, testeable)

```python
IDIOMAS = ("es", "en", "pt");  IDIOMA_DEFAULT = "es"
DIR_IDIOMAS = Path(__file__).resolve().parent.parent / "idiomas"   # ui/idiomas/

@lru_cache(maxsize=len(IDIOMAS))
def cargar_diccionario(lang) -> dict[str, str]:
    # Lee ui/idiomas/<lang>/*.yaml, aplana anidamiento a claves con puntos,
    # prefija con el stem del archivo (p3.yaml → "p3."). Idioma inexistente → {}.

def traducir(clave, lang, /, default=None, **kwargs) -> str:
    # Resolución: dict(lang) → dict("es") → default → clave literal.
    # Interpola con str.format (soporta {largo_m:.2f}); si el format falla,
    # devuelve la plantilla sin interpolar — NUNCA lanza.

def campo_i18n(datos: dict, campo: str, lang: str) -> str:
    # Catálogos: datos[f"{campo}_{lang}"] si existe y lang != "es"; si no datos[campo].

def recargar() -> None:   # cache_clear para desarrollo/tests
```

### `ui/componentes/idiomas.py` (nuevo — importa streamlit)

```python
def idioma_actual() -> str:
    # session_state["idioma"] → query param ?lang= (válido → se copia a session)
    # → "es". try/except → "es" fuera de runtime (pytest sin servidor).

def t(clave, **kwargs) -> str:            # traducir(clave, idioma_actual(), **kwargs)

def selector_idioma() -> None:
    # 🌐 selectbox sidebar, options=IDIOMAS estables, format_func
    # {"es": "Español", "en": "English", "pt": "Português"};
    # on_change sincroniza session_state + st.query_params["lang"].
```

### Diccionarios: `ui/idiomas/<lang>/*.yaml`

- **Dentro de `ui/`** (NO top-level): el deploy copia `ui/` recursivo → cero
  cambios en `deploy_hf.yml`, cero riesgo de olvidar la línea (olvidarla
  mostraría claves crudas en producción). Coherente con capas: traducir es
  responsabilidad de la UI.
- **Un archivo por idioma+sección** (≈14 × 3): `comun, sidebar, p1..p7,
  graficas, reporte, advertencias, catalogo, manual`. Diffs por fase acotados;
  el más grande (p4 post-S48) ~200 claves. Anidados por dentro (el loader
  aplana).

## 2. Convención de claves (documentar en CLAUDE.md)

| Namespace | Contenido | Ejemplo |
|---|---|---|
| `comun.*` | textos repetidos entre secciones | `comun.boton.calcular` |
| `sidebar.*` | todo Secasol.py | `sidebar.nav.p3` |
| `p1.*`…`p7.*` | por sección, subnivel = bloque visual | `p3.geometria.largo.label` |
| `graficas.*` | ejes/títulos plotly compartidos | `graficas.eje.hora_del_dia` |
| `reporte.*` | PDF | `reporte.portada.titulo` |
| `advertencias.<CODIGO>.mensaje/.sugerencia` | plantillas por código | `advertencias.GEO_LARGO_PEQUENO.mensaje` |
| `catalogo.*` | rótulos de UI del catálogo ("Fuente:") | `catalogo.detalle.fuente` |
| `manual.*` | visor + TOC | `manual.toc.colector.titulo`, `manual.ui.solo_es` |

Reglas duras:

- Widget: `<sección>.<bloque>.<campo>.label`; su tooltip = misma clave `.help`.
- Enums: `.value` técnicos NO se traducen; labels vía
  `format_func=lambda e: t(f"p1.tipologia.{e.value.lower()}")`. Los dicts
  module-level `_ETIQUETAS_*` pasan a funciones (el idioma cambia entre reruns
  — **nunca `t()` a nivel de módulo**).
- Placeholders **siempre nombrados**; la lógica se resuelve en Python antes de
  `t()`. Plurales: par de claves `.singular`/`.plural` elegidas con `n == 1`
  (regla válida en ES/EN/PT).
- Textos largos: bloques YAML `|` (una clave multilínea, no siete).
- Una clave publicada no se renombra.

## 3. Fases (cada una en verde antes de la siguiente)

Método por fase: Claude reemplaza literal→`t()` archivo por archivo y en el
mismo paso puebla `es/` (copia el literal) y traduce `en/` + `pt/`. Script
read-only `scripts/auditar_i18n.py` (regex de literales en llamadas `st.*`)
mide el residuo por archivo al cierre de cada fase. Cierre = pytest + black +
ruff + e2e (§7) + bitácora.

| Fase | Alcance | Volumen |
|---|---|---|
| **F0** | Precondición: merge S48 hecho. **Re-censar P4** (la cámara ampliada agrega strings) | — |
| **F1** | Infra completa + tests + selector 🌐 + `Secasol.py` (sidebar y nav con **options estables** — fix `nav_seccion`) + piloto `p1_tipologia.py` | ~120 claves |
| **F2** | `p2_emplazamiento.py` + `p3_colector.py` (incl. sus figuras plotly) | ~330 |
| **F3** | `p4_camara.py` (re-censado) + `p5_auxiliar.py` + `p6_motor.py` | ~400+ |
| **F4** | `p7_resultados.py` + componentes compartidos (graficas, carta_psicrometrica, header, espesores, serializacion) | ~250 |
| **F5** | Advertencias por código: completar el stub `ui/componentes/advertencias_widget.py` como render único (reemplaza los 4 renders inline de p3/p4/p5/p6) + `advertencias.yaml` con los 39 códigos | 78×3 |
| **F6** | PDF: `generar_reporte_pdf(..., idioma)`, `tr` enhebrado a las `_seccion_*` | ~280 |
| **F7** | Catálogos: `descripcion_en`/`descripcion_pt` en los YAML (39 items) + `campo_i18n` en los format_func. `notas`/`fuente` quedan ES en v1. No tocar bloques `capa_fina:` | 78 campos |
| **F8** | Manual multiidioma (infra): mover a `manual/capitulos/es/`, `ruta_capitulo(cap, lang)` + fallback con aviso, TOC vía `traducir(..., default=cap.titulo)`, enlaces internos y `boton_manual` propagan `&lang=`, tests parametrizados por idioma en disco | ~50 |
| **F9+** | Traducción de los 22 capítulos del manual a EN y PT (capítulo a capítulo, revisable) | ~3.100 líneas ×2 |

## 4. Advertencias traducidas (detalle F5)

`ui/componentes/advertencias_widget.py` (hoy stub vacío):

```python
def texto_advertencia(adv, lang) -> tuple[str, str]:
    # traducir(f"advertencias.{adv.codigo}.mensaje", lang, default=adv.mensaje,
    #          **adv.contexto)  — try/except → adv.mensaje si el format falla.

def render_advertencias(advertencias, *, con_sugerencia=True) -> None:
    # Widget único: icono por Severidad + st.error/warning/info.
    # Unifica los 4 renders inline (p3 muestra sugerencia, p4-p6 no → flag).
```

Durante F5: audit código por código (39) anotando en comentario YAML qué claves
de `contexto` están disponibles para cada plantilla. Las `_advertencias_runtime`
de `BloqueResultados` (P7) pasan por el mismo widget. El PDF replica el
fallback sobre los dicts serializados.

## 5. Tests — `tests/test_ui/test_idiomas.py` (crece por fase)

1. Cada YAML parsea; valores no vacíos; sin claves duplicadas post-aplanado.
2. **Paridad de claves**: set(en) == set(es) == set(pt) (faltantes Y huérfanas),
   con allowlist `manual.toc.*`/`manual.parte.*` (el ES canónico vive en el TOC).
3. **Paridad de placeholders**: mismo set de campos nombrados por clave entre
   idiomas (`string.Formatter().parse`).
4. **Cobertura de advertencias**: los 39 códigos (extraídos por regex de
   core/) tienen `.mensaje`/`.sugerencia` en los 3 idiomas; placeholders ⊆
   claves de `contexto` del bloque fuente (best effort).
5. Unidad de `traducir`/`campo_i18n`/`idioma_actual` (fallbacks, format roto
   no lanza).
6. **Heurística anti-regresión**: lista `_ARCHIVOS_MIGRADOS` que crece por
   fase; regex que prohíbe literales con letras como primer arg de `st.*` y en
   `help=` en esos archivos (escape hatch: comentario `# i18n: exento`).
7. Tests del manual parametrizados por idioma (F8): ES completo obligatorio;
   EN/PT parciales validan solo lo que exista.

## 6. Documentación

- **CLAUDE.md**: sección "Internacionalización": arquitectura, tabla de
  namespaces, regla dura **"todo string visible nuevo pasa por `t()` y se
  agrega a los 3 YAML en el mismo cambio"**, gotchas (no `t()` module-level;
  options estables + format_func; plantillas de advertencias solo interpolan
  `contexto`; punto decimal se mantiene).
- `docs/notas/mejoras.md` (ítem nuevo), `docs/tareas.md` (fases como backlog),
  `CHANGELOG.md`, bitácora por fase.

## 7. Verificación e2e por fase

1. Suite completa + black + ruff.
2. `streamlit run` y, por cada idioma (selector y también `?lang=en` directo):
   screenshot de cada página tocada — ninguna clave cruda visible (`p3.` en
   pantalla = bug), ningún ES residual en EN/PT.
3. F5: forzar una advertencia de cada severidad en los 3 idiomas.
4. F6: generar el PDF en los 3 idiomas.
5. F8: `?manual=colector&lang=en` → aviso "solo en español" + el idioma se
   hereda desde el botón 📖 de la app.
6. `scripts/auditar_i18n.py` → conteo residual por archivo.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Colisión con la integración S48 | i18n arranca sobre main ya integrado; re-censo de P4 en F0 |
| Nav rota al cambiar idioma | options estables `p1..p7` + format_func (primera tarea de F1) |
| `contexto` insuficiente en advertencias | plantilla reformulada sin el dato + fallback runtime a ES |
| f-strings con lógica | lógica en Python, valores a `t()`; plurales por par de claves |
| Deriva ES-YAML vs código | regla CLAUDE.md + test heurístico + script de auditoría |
| Claves crudas en producción | YAML viajan dentro de `ui/` (deploy sin cambios) + fallback a clave visible en e2e |
| Performance | 3 dicts en memoria (~1.600 claves), lookup O(1), lru_cache por proceso |

## Archivos clave

**Crear:** `ui/componentes/traducciones.py`, `ui/componentes/idiomas.py`,
`ui/idiomas/{es,en,pt}/*.yaml` (~14 por idioma), `tests/test_ui/test_idiomas.py`,
`scripts/auditar_i18n.py`.
**Modificar (por fase):** `Secasol.py`, `ui/p1..p7_*.py`, `ui/componentes/`
(graficas, carta_psicrometrica, header, espesores, serializacion,
advertencias_widget, manual_contenido, manual_render, manual_link, manual.py),
`ui/reporte.py`, `catalogo/**/*.yaml`, `CLAUDE.md`, docs.
**Sin cambios:** `core/`, `calculos/`, `.github/workflows/deploy_hf.yml`.
