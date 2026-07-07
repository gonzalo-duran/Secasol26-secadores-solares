# Plan de integración S48 — cámara ampliada (Dell) + manual de usuario (rama remota)

> Guía operativa para la sesión del 2026-07-08 en la Dell G15, escrita al cierre
> de la S47 (manual de usuario). Pensada para ejecutarla con Claude Code local:
> pasale este archivo como contexto y seguí las fases en orden.

## Situación de partida (2026-07-07)

Existen **tres estados** del código:

| Dónde | Qué tiene | Estado |
|---|---|---|
| **Dell G15 (working tree local)** | Ampliación grande del modo de funcionamiento de la cámara de secado (sesión de ayer) | **Sin commitear ni pushear** |
| **`main` (GitHub)** | Versión estable v0.14.1 | = producción en HF Space (deploy automático en cada push) |
| **`claude/hola-code-vs-local-cli-vjvre6` (GitHub)** | Manual de usuario completo (mejora 36): 21 capítulos + visor `?manual=` + 142 tests. Commit `a5f4093`, 42 archivos | Pusheada, **no mergeada** |

**Regla de oro:** un push a `main` deploya a producción al instante. Nada llega a
`main` sin suite verde. Una feature = un merge = un deploy verificable.

**Orden elegido: cámara primero, manual después.** (a) La cámara es física de
producción: se deploya y verifica **sola**, sin mezclar causas si algo difiere
local↔Space (lección S46). (b) El manual *describe* la cámara: los capítulos
`13_camara.md` y `32_tec_camara.md` deben actualizarse para reflejar la
ampliación **antes** de que el manual llegue a producción.

---

## Fase 0 — Asegurar el trabajo de la Dell (primero que todo)

En la Dell, sobre el repo local con la cámara ampliada:

```bash
git status                        # ver qué hay
git checkout -b feature/camara-ampliada
git add -A
git commit -m "<mensaje descriptivo de la ampliación de cámara>"
git push -u origin feature/camara-ampliada
```

Con esto el trabajo ya está **a salvo en GitHub** aunque todavía no en
producción. Recién después seguir con lo demás.

**Checklist antes de pasar a Fase 1:**

- [ ] `.venv/bin/python -m pytest` → **toda la suite verde** (anotar el conteo).
- [ ] `.venv/bin/python -m black .` y `ruff check .` limpios (los ~54 avisos
      preexistentes de ruff no cuentan).
- [ ] Si la ampliación agregó/actualizó **alguna librería**: pinnearla con `==`
      en `requirements.txt` (gotcha S46 — el Space resuelve solo lo pinneado).
- [ ] ¿La sesión de ayer generó bitácora? Ver **conflicto de numeración** en
      Fase 2 (la rama del manual ya trae `bitacora_sesion47.md`).

## Fase 1 — Cámara ampliada → `main` → producción

```bash
git checkout main
git pull origin main
git merge feature/camara-ampliada     # (o vía PR en GitHub si se prefiere)
.venv/bin/python -m pytest            # suite verde sobre el merge
git push origin main                  # ← esto deploya a producción
```

**Verificación post-deploy (Space `gonzalojduran/Secasol26`):**

- [ ] El Action `deploy_hf.yml` terminó OK (pestaña Actions de GitHub).
- [ ] Panel "🔧 Entorno" del sidebar: mismas versiones local ↔ remoto.
- [ ] Correr **un caso de referencia de cámara** en local y en el Space:
      mismos números (la lección de la S46: 0.26 vs 4.77 kg fue por entorno).

## Fase 2 — Integrar el manual con la cámara nueva

Traer `main` actualizado a la rama del manual y resolver conflictos:

```bash
git checkout claude/hola-code-vs-local-cli-vjvre6
git pull origin claude/hola-code-vs-local-cli-vjvre6
git merge main
```

### Conflictos esperados y cómo resolverlos

| Archivo | Qué hizo la rama del manual | Resolución |
|---|---|---|
| `ui/p4_camara.py` | Solo 2 líneas: import de `manual_contenido`/`manual_link` + `boton_manual(SLUG_POR_SECCION["p4"])` tras `st.header("4 · Cámara de Secado")` | **Conservar ambos**: los cambios de la cámara ampliada + esas 2 líneas |
| `CHANGELOG.md` | Entrada "Added: Manual de usuario…" en `[Unreleased]` | Conservar **ambas** entradas (cámara y manual) |
| `CLAUDE.md` | Árbol de capas (+`ui/manual.py`, `manual/capitulos/`), subsección "Manual de usuario", nota de whitelist en §Deploy | Conservar ambos: lo que la cámara haya tocado + las adiciones del manual |
| `docs/tareas.md` | Estado general → S47 + hito manual | Fusionar a mano (actualizar conteo de tests al real post-merge) |
| `docs/notas/mejoras.md` | Ítem 36 → `[IMPLEMENTADO]` | Conservar ambos |
| `docs/mapa_conexiones.md` | Nota S47 (el manual no agrega cableado) | Conservar ambos |
| `docs/bitacora/bitacora_sesion47.md` | **La rama del manual la creó.** Si la sesión de la Dell también generó una 47: la de la Dell fue primero cronológicamente → **queda 47**, y la del manual se renombra a `bitacora_sesion48.md` (ajustar también las 2 menciones "S47" en `docs/tareas.md` y `docs/mapa_conexiones.md`) | Renumerar si colisiona |

### Actualizar el manual a la cámara nueva (clave)

Los capítulos del manual describen la cámara **previa** a la ampliación.
Con Claude Code local, revisar y actualizar contra el código nuevo:

- [ ] `manual/capitulos/13_camara.md` — guía de la sección P4: ¿aparecieron
      controles/modos nuevos? ¿cambió el flujo de trabajo?
- [ ] `manual/capitulos/32_tec_camara.md` — referencia técnica: ¿cambiaron
      ecuaciones, hipótesis, coeficientes, modos de operación?
- [ ] Si hay funcionalidad nueva visible en resultados:
      `16_resultados.md` / `36_tec_resultados.md`.
- [ ] `90_apendice_codigo.md` §cámara — si cambiaron módulos/funciones.
- [ ] Si un capítulo nuevo o un heading con ancla cambia: correr
      `pytest tests/test_ui/test_manual.py` — los 142 tests validan que todos
      los enlaces/anclas/esquemas sigan resolviendo.

### Cerrar la fase

```bash
.venv/bin/python -m pytest            # suite completa verde (≥1184 + lo de cámara)
.venv/bin/python -m black . && .venv/bin/python -m ruff check .
git commit                            # el merge + actualizaciones del manual
git push origin claude/hola-code-vs-local-cli-vjvre6
```

Probar en local: `streamlit run Secasol.py` → botón "📖 Manual" en cada
sección, `?manual=indice`, `?manual=camara` (verificar que describe la cámara
nueva), enlaces cruzados, expanders, ecuaciones.

## Fase 3 — Manual → `main` → producción

```bash
git checkout main
git merge claude/hola-code-vs-local-cli-vjvre6
.venv/bin/python -m pytest
git push origin main                  # ← segundo deploy
```

**Verificación post-deploy específica del manual:**

- [ ] `manual/capitulos/` llegó al Space (el workflow tiene la línea nueva
      `cp -r ../manual/ src/manual/`).
- [ ] En el Space: el botón "📖 Manual" abre **pestaña nueva** desde adentro
      del iframe de HF (si el navegador la bloquea → habilitar pop-ups; el
      fallback con clic de rueda está documentado en la intro del manual).
- [ ] `<url-del-space>/?manual=indice` carga el índice; un capítulo con
      ecuaciones (ej. `?manual=radiacion`) renderiza KaTeX.
- [ ] La app de diseño sigue intacta (cargar un `.json` y verificar).

## Fase 4 — Limpieza y cierre

- [ ] Borrar ramas ya mergeadas:
      `git push origin --delete feature/camara-ampliada claude/hola-code-vs-local-cli-vjvre6`
      (+ `git branch -d` locales).
- [ ] Bitácora de la sesión S48 (esta integración).
- [ ] Considerar bump de versión en `CHANGELOG.md` (la cámara ampliada + el
      manual justifican un `0.15.0`) y mover lo de `[Unreleased]` a la versión.
- [ ] `docs/tareas.md`: para la v1.0 quedaría solo i18n + refinamiento anual.

## Si algo sale mal

- **Producción rota tras un push a `main`**: `git revert <merge-commit>` y push
  — el Action redeploya la versión anterior en minutos. Por eso los dos deploys
  van **separados**: se sabe cuál revertir.
- **El merge de Fase 2 se complica más de lo esperado**: abortar con
  `git merge --abort` y pedirle a Claude Code local que haga la integración
  archivo por archivo (los cambios del manual en `ui/p*.py` son mínimos y
  re-aplicables a mano; el grueso del manual son archivos **nuevos** que no
  conflictúan jamás).
