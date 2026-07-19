---
name: cierre-sesion
description: Cierre de sesión de trabajo — arma la bitácora de la sesión siguiendo el formato del proyecto, actualiza docs/tareas.md y deja todo en el working tree para revisar (sin commitear).
disable-model-invocation: true
---

# Cierre de sesión

Ritual de fin de sesión de Secasol. Produce la bitácora de la sesión y actualiza el
estado del backlog. **Todo queda en el working tree — NUNCA commitear ni pushear**
(regla del proyecto: commits solo cuando el usuario lo pide explícitamente).

## Pasos

1. **Determinar el número de sesión.** Buscar el N más alto en
   `docs/bitacora/bitacora_sesion*.md`. Si ya existe una bitácora de la sesión en curso
   (creada durante la sesión o con la fecha de hoy), actualizarla; si no, crear
   `bitacora_sesion{N+1}.md`.

2. **Juntar el estado real** (no de memoria):
   - `git -C . status` y `git diff --stat` → trabajo commiteado vs working tree.
   - `git log --oneline -10` → commits de la sesión, si los hubo.
   - Conteo de tests: `.venv/bin/python -m pytest --collect-only -q 2>/dev/null | tail -1`.
   - Versión actual: primer bloque de `CHANGELOG.md`.

3. **Escribir la bitácora** con la estructura de las sesiones recientes (usar la última
   como referencia de tono y formato):
   - Título: `# Bitácora — Sesión N (YYYY-MM-DD)` + párrafo de resumen ejecutivo.
   - `## Qué se hizo` con subsecciones `### 1. ...`, `### 2. ...` numeradas por tema,
     incluyendo decisiones tomadas y su porqué (las bitácoras son el registro histórico
     de decisiones del proyecto).
   - `## Pendiente para la próxima sesión` — lista concreta y accionable.
   - `## Notas` — gotchas, deuda técnica, observaciones.

4. **Actualizar `docs/tareas.md`:**
   - Blockquote de "Estado general (SN)": sesión, versión en producción, conteo de tests.
   - Mover ítems terminados de "En progreso" a "Completado (hitos recientes)".
   - Agregar pendientes nuevos detectados en la sesión.

5. **Reportar al usuario:** resumen de lo escrito, recordar que quedó sin commitear, y
   preguntar si quiere commitear (solo entonces armar el commit, mensaje corto sin
   HEREDOC — preferencia del usuario).

## Advertencias

- El repo es un vault de Obsidian: si el usuario tiene Obsidian abierto, el autosave
  puede pisar los .md editados desde afuera. Recordarle que cierre Obsidian o recargue.
- No inventar conteos ni estados: todo dato de la bitácora sale de comandos corridos en
  el momento.
