# Registro de decisiones de diseño (ADR)

Decisiones arquitectónicas relevantes de **Secasol 26**. Cada entrada anota
contexto, opciones, decisión y consecuencias. Para la arquitectura general ver
[[docs/arquitectura]]; para las convenciones de trabajo ver [[CLAUDE]].

> El registro histórico cronológico vive en `docs/bitacora/`. Esta nota resume
> las decisiones estructurales para navegación rápida desde Obsidian.

---

## ADR-001 — Separación estricta de capas (sin Streamlit en `core/`/`calculos/`)

- **Contexto:** la lógica física debía ser testeable y reutilizable fuera de la UI.
- **Opciones:** (a) acoplar cálculo a Streamlit; (b) separar capas con frontera dura.
- **Decisión:** `core/` y `calculos/` no importan `streamlit`; la UI es la única
  capa que lo usa. `validacion/` puede usar `core`/`calculos` pero no `ui`.
- **Consecuencias:** los motores se validan con pytest sin servidor; la UI es
  reemplazable. Cualquier import de `streamlit` fuera de `ui/` es un error.

## ADR-002 — SI estricto en el núcleo; conversión única en `unidades.py`

- **Contexto:** mezclar unidades (°C/K, %, fracción) genera errores difíciles de rastrear.
- **Decisión:** todo lo que circula por `core/`/`calculos/` está en SI estricto.
  La única conversión de unidades (y de convenciones de ángulos) vive en
  `ui/componentes/unidades.py`.
- **Consecuencias:** los motores asumen K, Pa, fracciones, kg/s. Toda entrada del
  usuario se convierte en la frontera de UI.

## ADR-003 — `Chimenea` como componente top-level (S30)

- **Contexto:** originalmente la chimenea era subcomponente del `Colector`, lo que
  impedía chimenea solar en tipología CAJA (sin colector).
- **Decisión:** `Chimenea` pasa a ser top-level en `Proyecto`. Los snapshots
  antiguos con `colector.chimenea` se migran en la deserialización.
- **Consecuencias:** convección natural disponible en todas las tipologías.

## ADR-004 — Motor termodinámico de cámara por defecto (S34)

- **Contexto:** el modo `capa_fina` usa cinéticas empíricas con `k` constante; el
  modo `termodinamico` resuelve el balance acoplado calor-masa.
- **Decisión:** `modo_calculo = "termodinamico"` como valor por defecto.
- **Consecuencias:** resultados más físicos; `t_secado_s` puede ser `None` si no
  converge. Las divergencias de firma se abstraen en helpers de balance y P7.

## ADR-005 — Deploy en Hugging Face Spaces vía GitHub Action (S33)

- **Contexto:** repo de GitHub privado; necesidad de que colegas accedan a la app
  sin instalar nada ni ver el código.
- **Decisión:** deploy automático a HF Spaces (Docker + Streamlit) en cada push a
  `main`. Un push a `main` actualiza producción.
- **Consecuencias:** cambios que no deben llegar a producción van en otra rama.

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
