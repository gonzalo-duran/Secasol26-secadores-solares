# Bitácora — Sesión 68

**Fecha:** 2026-11-17 · **Tema:** presets de tecnología (galería de secadores típicos). Plan
escrito, Fase A implementada y **vuelta atrás**: queda en espera.

## 1. Punto de partida

Después de la conferencia magistral de CONSYCSA (con gran éxito), el usuario observa que Secasol,
por su alcance, es grande y complejo para quien empieza (productor o alumno). Pide entrar en
modo plan para pensar una forma más simple de iniciar: dejar **presets de secadores típicos**
cargados para que un novato pueda ejecutar algo directo.

En la discusión aporta la idea que ordena todo el diseño: un preset es una **tecnología**
(materiales, dimensiones, tipo) que se puede **colocar en distintos lugares** y **cargar con
distintos productos** (tipo y masa). Tres ejes ortogonales: tecnología × sitio × producto.

Decisiones: por fases (A galería + guía; B inicio rápido de un clic), sitios de referencia con
clima empaquetado + coordenadas propias, catálogo inicial de cinco secadores (caja directa, caja
con chimenea, armario natural y forzado, ADITAL), y presets autorados desde la propia app.

## 2. Lo que pasó

1. Plan aprobado y **Fase A implementada completa**: orientación portable, sitios con clima
   NASA 2023, galería en P1, guía 🧭, exportador en P7, preset ADITAL desde `core/presets.py`,
   capítulo de manual ES/EN/PT. Suite **2061 passed, 2 skipped**; black, ruff e i18n limpios.
2. Al revisarlo, el usuario decide **no implementarlo todavía**. Se vuelve atrás:
   - el código va a un **stash local** (`S68 presets de tecnologia - Fase A implementada (sin
     aprobar)`, 46 archivos) y el working tree vuelve a `ca68ceb`;
   - el plan, enriquecido con lo aprendido al implementar, queda en
     [[docs/notas/plan_presets_tecnologia]] y se referencia en [[docs/tareas]].

Lo que vale la pena recordar está en el §4.3 del plan. El hallazgo principal: para un armario, el
camino real a un resultado pasa por la evaluación diaria del colector en P3 (lo exige P4 para
las forzantes reales), y eso justifica la Fase B.

## 3. Entorno

`.venv` estaba roto: el upgrade a Fedora 45 sacó `/usr/bin/python3.14`. Se rehízo con el
CPython 3.14.6 que gestiona `uv`. Esto **no** se revirtió (está fuera del repo).

## 4. Estado al cierre

- `testing` = `main` local = `ca68ceb`, sin cambios en el working tree salvo este documento,
  el plan y la entrada de `docs/tareas.md`. Nada commiteado ni pusheado.
- Sin tocar: `docs/asades2026/` y `uv.lock` (no versionados, de antes).
- Pendientes: las cuatro decisiones del §5 del plan, cuando se retome.
