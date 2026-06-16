# Bitácora — Sesión 40 (2026-06-10)

**Tema:** Modo secador industrial / gran escala (`Tipologia.GRAN_ESCALA`) — último hito hacia
v1.0. Implementación completa de los dos subtipos (Batch y Semicontinuo a contracorriente estilo
ADITAL), con ventana de producción, motor de cámara en cascada, caño maestro, híbrido con
calendario de arranque, UI completa y validación de campo.

**Estado al cierre:** Implementado y validado. Suite **942 passed**. Versión local bumpeada a
**0.13.0**. Sin commitear (working tree, sobre el trabajo de S38/S39). La parte de cálculo (Fases
0–4 + glue) ya estaba en el working tree al iniciar la sesión; esta sesión completó la **UI
(Fase 5)**, la **validación contra ADITAL (Fase 6)** y la **documentación**.

---

## 178. Recuperación del plan tras reinicio

La sesión arrancó después de un reinicio que vació el contexto en medio de la implementación. El
plan industrial (armado y aprobado en plan mode) **no estaba en contexto**. Se recuperó del
transcript de Claude Code (`~/.claude/projects/.../*.jsonl`, extrayendo el `ExitPlanMode` con el
plan completo) y se **persistió en el repo** en `docs/notas/plan_secador_industrial.md` (con tabla
de estado por fase, que se fue actualizando a medida que avanzaba la sesión). El plan original
también estaba en `~/.claude/plans/graceful-puzzling-squid.md`.

**Lección:** los planes de plan mode no quedan versionados en el repo por defecto. Persistirlos en
`docs/notas/` los hace sobrevivir a reinicios y los vuelve descubribles.

## 179. Plan de 7 fases (recordatorio)

Gran escala = **dos subtipos de igual jerarquía** (`Configuracion.subtipo_gran_escala`): BATCH y
SEMICONTINUO. Idea arquitectónica central: **un único motor de cámara multi-etapa** (batch = N=1
zona; semicontinuo = N zonas a contracorriente con avance por cadencia), reusando intacto el núcleo
físico de `camara_termodinamica`. Fases 0–4 (core+cálculo) ya estaban hechas al iniciar; esta
sesión cubrió Fases 5 (UI) y 6 (validación + docs). Detalle completo en
`docs/notas/plan_secador_industrial.md`.

## 180. Fase 5 — UI

Cada pieza con su serialización (JSON + `.txt`) y back-compat, verificada con AppTest.

- **P1** (ya estaba): selector de subtipo + ventana de producción con presets.
- **P4** (`ui/p4_camara.py`): sección "Topología del túnel (semicontinuo)" gateada por
  `subtipo == SEMICONTINUO` → `n_zonas` + cadencia de avance, con caption derivado (residencia
  total, carga por columna). Construye `Camara.tunel: ConfiguracionTunel` en las dos rutas de
  instanciación (closure `_build_camara` + bloque del botón). Serialización con clave `tunel`
  (back-compat: ausente → None).
- **P7** (`ui/p7_resultados.py`): rama autocontenida para `modo_analisis == VENTANA` (`_render_ventana`):
  recorta `clima.datos` al lapso (`_slice_clima_ventana`, mapea las fechas al año del clima
  descargado), botón → `calcular_todo_ventana`, dashboard de producción (producto seco, tasa de
  régimen, agua evaporada, leña) + métricas por subtipo (BATCH: lotes, t medio/lote; SEMICONTINUO:
  columnas, X salida, throughput) + perfil espacial del túnel (`_fig_perfil_tunel`: X y T_aire por
  zona). Hace `return` antes del flujo Constantes/Transitorio (que es para CAJA/ARMARIO).
- **P5** (`ui/p5_auxiliar.py`): expander opcional "Calendario de arranque (híbrido mañana/tarde)"
  → checkbox + N cargas configurables (hora_inicio + duración, defaults 6 h/3 h y 18 h/4 h), que
  construye `Auxiliar.cargas_arranque`. **Aplica a todos los modos transitorios** (no solo gran
  escala): lo consume `calcular_auxiliar_transitorio`, llamado tanto por el pipeline DIARIO/multi-día
  como por el de ventana.
- **P3** (`ui/p3_colector.py`): sección "Caño maestro (manifold del banco)" dentro del expander de
  banco, gateada por `GRAN_ESCALA` → checkbox + largo/sección/aislado/aporte solar, con **preview de
  ΔP en vivo** (`estimar_delta_P_cano_maestro`). Construye `BancoColectores.cano_maestro`.
- **P6** (`ui/p6_motor.py`): en la rama "ΔP por componentes", si el banco tiene caño maestro su ΔP
  (a caudal total) se **suma a ductos de forma explícita** (entra al total del `Motor`, que con
  ductos=None solo aplicaría el 20 % heurístico) y se muestra en el desglose. Sin caño:
  comportamiento intacto.

**Detalle de implementación (gotchas):** P4 y P6 tienen dos construcciones de su dataclass (closure
de preview + bloque de botón) — ambas debieron actualizarse. Black reformatea líneas pre-existentes
(el repo no está black-clean); se cuidó que los archivos editados queden black-clean en las líneas
nuevas. Ruff: sin errores nuevos (los baseline de cada archivo se contaron con `git stash` para
confirmar). AppTest de `from_function` corre cada función aislada (sin closures ni helpers del
módulo): hubo que pasar todo por `kwargs` e inlinear el setup.

## 181. Fase 6 — Validación contra ADITAL

Nuevo script standalone `validacion/validacion_adital.py` (fuera de pytest, como los demás de
`validacion/`). Valida la **cadena térmica** del modo industrial contra las mediciones de campo de
la tesis doctoral del usuario (Cap. 3, secador híbrido ADITAL, San Carlos, Salta, marzo 2009). Usa
un **clima sintético de marzo** que reproduce las Figs. 15–19 de la tesis (sin dependencia de red).

Parámetros de ADITAL extraídos de la tesis: 26 colectores 7.5×0.94 m (195 m²); caño maestro 18 m de
sección creciente, galvanizado desnudo no aislado; túnel 18×3×1.85 m aislado, 24 carros, 5000 kg de
pimiento; ventilador centrífugo 4 HP, ~600 m³/h por colector.

**Resultado: 4/4 checks térmicos OK.**

| Magnitud | Modelo | Tesis |
|----------|--------|-------|
| Salida colector — operación (v=1.8, I=900, Ta=20) | 55.1 °C | ~50–60 °C |
| Salida colector — pico mediodía (I=1000, Ta=38) | 78.2 °C | ~80 °C |
| Caño maestro — ΔT | −2.8 °C | −3 °C |
| Cámara — T entrada media (horas de sol) | 57.5 °C | 40–60 °C |

Capacidad de campaña: 1000 kg/día fresco → **5000 kg en 5.0 días** (tesis: 4–5 días de sol).

**Hallazgos durante la validación:**

1. **`CanoMaestro.absortancia_solar` default = 0.90 es de chapa pintada oscura.** El caño de ADITAL
   es galvanizado desnudo (brillante, α≈0.35). Con 0.90 el modelo daba el caño *calentando* el aire
   (+2.8 °C); con α=0.35 da ΔT = −2.8 °C, consistente con el −3 °C de la tesis. **No se cambió el
   default del core** (afectaría comportamiento/tests existentes) — queda documentado como gotcha en
   `CLAUDE.md` y a criterio del usuario si conviene bajarlo o señalarlo en la UI de P3.
2. **A caudal de diseño (v=1.8 m/s) el colector llega a ~80 °C en pico** (I=1000, Ta=38) — no hace
   falta suponer flujo casi nulo (v=0.4 daba 127 °C, cuasi-estancamiento irreal).
3. **Bug en el clima sintético del script** (corregido): el signo del coseno de `T_amb` invertía
   día/noche (mínimo a las 14 h en vez de máximo).

## 182. Documentación (cierre de Fase 6)

- `CHANGELOG.md`: nueva entrada **[0.13.0]** con el modo industrial completo (Added).
- `core/proyecto.py`: `VERSION_SOFTWARE` → **0.13.0**.
- `docs/mapa_conexiones.md`: filas S40 en la tabla maestra (P1 subtipo/ventana, P3 caño maestro, P4
  túnel, P5 calendario, P6 ΔP caño, P7 dashboard ventana) + nota de cierre.
- `CLAUDE.md`: nueva sección "Modo industrial / gran escala (`GRAN_ESCALA`, S40)" + descripciones de
  pestañas actualizadas.
- `docs/tareas.md`: modo industrial movido a Completado; estado general → v0.13.0 / 942 tests.
- `docs/notas/plan_secador_industrial.md`: tabla de estado por fase completa.

## 183. Pendiente

- **Commit/push** del trabajo S38+S39+S40 (a criterio del usuario; push a `main` = deploy a HF
  Spaces). El working tree acumula S38, S39 y S40 sin commitear.
- **Verificación e2e manual en Streamlit** del modo industrial completo (crear proyecto GRAN_ESCALA
  en cada subtipo, ventana de campaña, calcular en P7).
- Hoja de ruta a 1.0: con el modo industrial completo y validado, resta solo pulido — i18n
  (idiomas) y manual de usuario estilo SAM.
- Decisión abierta: ¿bajar el default `CanoMaestro.absortancia_solar` a ~0.35 (galvanizado) o
  exponerlo/aclararlo en la UI de P3?
