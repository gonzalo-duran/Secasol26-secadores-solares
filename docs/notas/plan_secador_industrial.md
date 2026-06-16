# Plan — Modo Gran Escala / Industrial (dos subtipos: Batch y Semicontinuo)

> **Origen:** plan armado y aprobado en plan mode (S40, jun 2026). Recuperado del
> transcript y persistido acá para que sobreviva a reinicios. La hoja de ruta hacia
> v1.0 se cierra con este modo industrial.

## Estado de implementación (actualizar al avanzar)

| Fase | Qué es | Estado |
|------|--------|--------|
| 0 | Ventana de análisis + `SubtipoGranEscala` (enums/campos en `core/proyecto.py`) | ✅ Hecho |
| 1 | Motor cámara multi-etapa `simular_cascada` + `calcular_camara_cascada` | ✅ Hecho |
| 2 | Orquestador `simular_ventana` + `calcular_todo_ventana` | ✅ Hecho |
| 3 | Caño maestro `CanoMaestro` + `cano_maestro_calc.py` | ✅ Hecho |
| 4 | Híbrido con `cargas_arranque` (calendario mañana/tarde) + leña | ✅ Hecho |
| 5 | **UI (P1 ✅, P3 ✅, P4 ✅, P5 ✅, P6 ✅, P7 ✅) + serialización ✅** | ✅ Completa |
| 6 | Validación vs ADITAL ✅ + docs (CHANGELOG/bitácora/CLAUDE/mapa/tareas) ✅ | ✅ Completa |

**PLAN COMPLETO.** Tests: **942 passed**. Versión bumpeada a **0.13.0**. Trabajo en working
tree sin commitear (S38+S39+S40). Resta solo: commit/push (a criterio del usuario) y verificación
e2e manual en Streamlit. Hoja de ruta a 1.0: con el modo industrial cerrado, queda solo pulido
(i18n + manual de usuario).

---

## Contexto

La tipología `GRAN_ESCALA` existía solo como **etiqueta cosmética**: en todo el
pipeline (`balance_global.py`, P3/P4/P6/P7) la única tipología que ramificaba era
`CAJA`. `ARMARIO` y `GRAN_ESCALA` recorrían exactamente el mismo cálculo (mismo motor
TD batch CSTR de una sola cámara, mismo `BancoColectores` que solo escala
caudal/área linealmente). Completar el modo industrial es el último hito hacia v1.0.

La referencia física canónica es el **secador híbrido ADITAL de San Carlos** (tesis
doctoral del usuario, cap. 3): banco de 26 colectores con **caño maestro** de sección
creciente, **túnel de secado semicontinuo a contracorriente** con 24 carros (5000 kg),
quemador de leña **en serie** como arranque mañana/tarde, ventilador centrífugo.

**Decisión estructural (usuario):** gran escala se subdivide en **dos subtipos de
igual jerarquía**, ninguno subordinado al otro:

1. **Batch de gran escala** — lotes: carga → secado → descarga → recarga.
2. **Semicontinuo industrial** — carga completa, producto a **contracorriente** del
   aire, estilo ADITAL.

Ambos deben estar presentes en toda la planificación con el mismo nivel de desarrollo.

## Decisiones ya acordadas en la discusión

- **Corridas horarias en cualquier horizonte.** El costo está medido y es no-problema:
  ~26 ms/resolución de colector, ~57 s para 3 meses y ~76 s para 4 meses de clima
  real horario (la cámara TD es ~15 ms, despreciable). Sin Picard de chimenea (forzado).
- **Resolución climática:** serie real horaria **siempre** para campaña (semana →
  varios meses); el día-típico-mensual se reserva solo para "año completo".
- **Período = ventana `[fecha_inicio, fecha_fin]`** libre + presets (1 semana / 1 mes /
  campaña / año). Subsume y reemplaza el binario `DIARIO`/`ANUAL`.
- **Estacionalidad de disponibilidad (% uso mensual, tabla 2 de la tesis) → diferida
  a la futura capa económica.** La caída estacional climática emerge sola de simular
  el clima real; el % de uso es disponibilidad de producto, no física.
- **Alcance v1.0 industrial:** túnel semicontinuo + batch escalado + caño maestro +
  híbrido con arranque mañana/tarde. **Economía fuera** de este plan.
- **UX/caché:** gatear la simulación de ventana tras botón explícito + cache en
  `session_state` (patrón ya usado en P3/P7). El cuidado es UX, no CPU.

## Idea arquitectónica central: motor de cámara multi-etapa unificado

Batch y semicontinuo son **el mismo motor** con distinta topología y cadencia — esto
honra "ambos de igual importancia" sin duplicar física:

- **Batch** = cascada de **N=1 zona**, aire de un solo paso, ciclo carga→seca→descarga.
- **Semicontinuo** = cascada de **N zonas en serie**, aire a **contracorriente**
  (entra caliente por la zona N donde sale producto seco, sale húmedo por la zona 1
  donde entra producto fresco); las columnas **avanzan una posición** según la cadencia.

```
   AIRE  ───────────────────────────────────►  (sale húmedo)
   ┌────────┬────────┬───  ───┬────────┐
   │ zona N │ zona.. │        │ zona 1 │
   │ (seco) │        │        │(fresco)│
   └────────┴────────┴───  ───┴────────┘
   PRODUCTO ◄───────────────────────────────   (carros avanzan)
```

**Por hora (régimen transitorio, no pseudo-estacionario):**
1. Marchar el aire de la zona N→1: en cada zona, resolver el estado de aire de salida
   con la algebraica CSTR existente (`camara_termodinamica.resolver_estado_camara`)
   dado el aire de entrada y el estado de producto (cuasi-congelado en la hora → **sin
   Picard**, simple paso secuencial).
2. Integrar la EDO de producto `[T_prod_i, X_prod_i]` una hora en cada zona, con los
   coeficientes de transporte variables en t ya existentes (S39).
3. Cuando toca según la **cadencia** (p.ej. diaria): desplazar las columnas
   (zona i ← zona i−1; zona 1 ← carga fresca; zona N → descarga como producto seco).

Reusa intacto el núcleo físico de `camara_termodinamica.py` (evaporación difusiva
`ṁ_w = h_m·A·(ω_sat·a_w − ω_flujo)`, GAB, coeficientes variables). Lo nuevo es la
**orquestación en cascada + cadencia + acumulación de producción sobre la ventana**.

## Plan por fases (ambos subtipos en cada fase)

### Fase 0 — Reformulación del período (ventana)  ✅
Fundamento, agnóstico de tipología.

- `core/proyecto.py`: agregar `ModoAnalisis.VENTANA`; nuevos campos en `Configuracion`:
  `ventana_inicio: date | None`, `ventana_fin: date | None`. Mantener `DIARIO`/`ANUAL`
  para back-compat de snapshots y tipologías chicas (DIARIO = día de diseño, ANUAL =
  año con día-típico). Validación en `__post_init__` (fin > inicio, rango ≤ 1 año).
- `core/proyecto.py` `SubtipoGranEscala(Enum) = {BATCH, SEMICONTINUO}`; campo
  `Configuracion.subtipo_gran_escala: SubtipoGranEscala = BATCH` (solo significativo si
  `tipologia == GRAN_ESCALA`).
- Deserialización: snapshots viejos sin estos campos → defaults coherentes.

### Fase 1 — Motor de cámara multi-etapa unificado  ✅
- `calculos/camara_termodinamica.py`: nuevo orquestador `simular_cascada(...)` que
  generaliza `simular_secado`. Parametrizado por `n_zonas`, `contracorriente: bool`,
  `cadencia`, y un callable de forzantes horarias por zona. `simular_secado` (batch
  monozona actual) se mantiene como caso `n_zonas=1` — **sin romper** los tests que lo
  llaman directo.
- `calculos/camara_calc.py`: `calcular_camara()` despacha a batch (N=1) o túnel
  (N zonas, contracorriente) según `subtipo_gran_escala`. Reusa el closure de
  coeficientes de transporte de `_calcular_termodinamico`.
- Salida: perfil espacial estacionario `X_i`, `T_air,i`, `ω_i`; throughput; m_evap.
- Tests: `test_camara_cascada.py` — equivalencia N=1 ↔ batch actual; contracorriente
  con N>1 da gradiente monótono de X; conservación de masa de agua; balance de energía.

### Fase 2 — Orquestador de ventana (horario sobre [inicio, fin])  ✅
- `calculos/simulacion_ventana.py` (nuevo): `simular_ventana(proyecto)`:
  1. Serie horaria real NASA POWER sobre `[inicio, fin]` (reusa `clima_calc.py` + caché).
  2. POA por hora (`calcular_POA_horizonte`).
  3. Colector hora a hora — solo horas de sol; noche → T_salida ≈ T_amb.
  4. Auxiliar en serie (Fase 4) eleva T_ent según el calendario de arranque.
  5. Motor de cámara en cascada (Fase 1) consume las forzantes y acumula producción.
- **Acumulación de producción:** Batch = lotes completados × masa/lote (+ parcial final);
  Semicontinuo = throughput sostenido × días operativos, con transitorio de llenado.
- **Métrica:** kg seco acumulado en la ventana + tasa de régimen sostenible (kg/día) +
  lotes/cadencia + energía solar vs biomasa + kg de leña consumida.
- `balance_global.py`: `calcular_todo_ventana(...)` análoga a `calcular_todo_transitorio`.
- Tests: `test_simulacion_ventana.py`.

### Fase 3 — Caño maestro (hidráulica del banco)  ✅
- `core/colector.py`: `CanoMaestro` con geometría del manifold (sección creciente, n
  bocas, llaves por rama) y `n_serie` real. ΔP de distribución.
- `calculos/cano_maestro_calc.py`: ΔP del manifold, operación en depresión, aporte solar
  parcial del caño (~3 °C de pérdida neta pese a no estar aislado).
- Acople al motor: el ΔP del sistema que ve el ventilador incluye banco + caño + cámara.
- Tests: `test_cano_maestro.py`.

### Fase 4 — Híbrido con arranque mañana/tarde  ✅
- `core/auxiliar.py`: `CargaArranque` + `cargas_arranque` (calendario diario de cargas
  de leña a la mañana y al atardecer) en vez de potencia constante.
- `calculos/auxiliar_calc.py`: perfil horario de Q_aux según calendario; acumular leña.
- Tests: `test_auxiliar_arranque.py`.

### Fase 5 — UI (P1, P4, P5, P6, P7) + serialización  🔶 EN CURSO
- **P1** (`p1_tipologia.py`) ✅: selector de subtipo (Batch/Semicontinuo) cuando
  `GRAN_ESCALA`; selector de ventana (inicio/fin + presets 1 semana / 1 mes / campaña).
  DIARIO/ANUAL siguen para CAJA/ARMARIO.
- **P4** (`p4_camara.py`) ✅: sección "Topología del túnel (semicontinuo)" gateada por
  `subtipo_gran_escala == SEMICONTINUO` (n_zonas + cadencia de avance + caption con
  residencia total y carga por columna); construye `Camara.tunel`. Batch usa las
  bandejas clásicas sin cambios. Serialización JSON `tunel` (con back-compat) + bloque
  TÚNEL en el export `.txt`. Verificado: round-trip, back-compat sin clave, AppTest
  (sección aparece solo en semicontinuo), suite 942 passed.
- **P5** (`p5_auxiliar.py`) ✅: expander "Calendario de arranque (híbrido mañana/tarde)"
  opcional (checkbox + N cargas configurables hora_inicio/duración, defaults 6h/3h y
  18h/4h) → construye `Auxiliar.cargas_arranque`. Aplica a todos los modos transitorios
  (Día real, multi-día, ventana), no solo gran escala. Serialización JSON + bloque txt
  con back-compat. Verificado round-trip + AppTest (checkbox persiste cargas), suite 942.
- **P3** (`p3_colector.py`) ✅: sección "Caño maestro (manifold del banco)" dentro del
  expander de banco, gateada por GRAN_ESCALA (checkbox opcional + largo/sección/aislado/
  aporte solar) → construye `BancoColectores.cano_maestro`; preview de ΔP en vivo
  (`estimar_delta_P_cano_maestro`). Serialización JSON + bloque txt con back-compat.
- **P6** (`p6_motor.py`) ✅: en la rama "ΔP por componentes", si el banco tiene caño
  maestro, su ΔP (`estimar_delta_P_cano_maestro` a Q_total) se **suma a ductos** de forma
  explícita (entra al total del Motor) y se muestra en el desglose. Sin caño: comportamiento
  intacto. Verificado AppTest: ΔP total con caño > sin caño, suite 942.
- **P7** (`p7_resultados.py`) ✅: rama autocontenida en modo VENTANA (`_render_ventana`):
  recorta `clima.datos` al lapso (`_slice_clima_ventana`, mapea fechas al año del clima),
  botón → `calcular_todo_ventana`, dashboard con producto seco / tasa de régimen / agua
  evaporada / leña + métricas por subtipo (BATCH: lotes, t medio/lote; SEMICONTINUO:
  columnas, X salida, throughput) + perfil espacial del túnel (`_fig_perfil_tunel`,
  X y T_aire por zona). Verificado AppTest render+cálculo ambos subtipos, suite 942.
- Serialización (`ui/componentes/`) ⬜: nuevos campos en JSON con back-compat.

### Fase 6 — Validación y documentación  🔶
- `validacion/validacion_adital.py` ✅: valida la **cadena térmica** del modo industrial
  contra las mediciones de campo de la tesis (Cap. 3, San Carlos, marzo 2009), con clima
  sintético de marzo (reproduce Figs. 15–19). **4/4 checks térmicos OK**: salida colector
  operación 55 °C (tesis ~50–60), pico mediodía 78 °C (tesis ~80), caño maestro ΔT −2.8 °C
  (tesis −3), T cámara 57 °C (tesis 40–60). Campaña: 1000 kg/día → 5000 kg en 5.0 días
  (tesis 4–5 días de sol). **Hallazgos:** (1) el default `CanoMaestro.absortancia_solar=0.90`
  es de chapa pintada; el galvanizado desnudo de ADITAL necesita α≈0.35 para dar ΔT≈−3 °C
  (con 0.90 el caño *calienta* el aire). (2) a caudal de diseño (v=1.8 m/s) el colector da
  ~80 °C en pico — no hace falta suponer flujo casi nulo.
- ⬜ `docs/bitacora/bitacora_sesion40.md`, `CHANGELOG.md`, `docs/mapa_conexiones.md`,
  `CLAUDE.md` (sección de tipología industrial), `docs/tareas.md` (hito v1.0).

## Decisiones tomadas con recomendación (confirmadas)

1. **Régimen del túnel:** cascada **transitoria** (estado por zona persistente, avance
   discreto por cadencia) — más fiel que pseudo-estacionario y cuesta lo mismo.
2. **Cadencia de carga/avance:** por **horario del operario** (configurable);
   alternativa event-driven (al alcanzar X_objetivo).
3. **Métrica:** acumulado en ventana **+** tasa de régimen (ambos).
4. **N etapas del túnel:** configurable por el usuario.
5. **Ubicación del subtipo:** `Configuracion.subtipo_gran_escala`.

## Verificación end-to-end

- `pytest` completo + `black .` + `ruff check .`.
- Streamlit: crear proyecto GRAN_ESCALA en cada subtipo, elegir ventana de campaña,
  calcular en P7 y verificar producción acumulada + tasa + leña, y (semicontinuo) el
  perfil espacial del túnel. Confirmar que CAJA/ARMARIO siguen idénticos.
- Validación física contra los números de ADITAL (Fase 6).
