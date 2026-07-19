# Plan — Mejora 38, Fase 1b: motor agnóstico al paso temporal

## Contexto

Fase 1a (S51) dejó la ingesta de clima medido produciendo el contrato horario
`Clima.datos` (motores intactos) y **preservando la resolución nativa** en
`Clima.datos_nativos` (ej. 600 s post-QC). Fase 1b hace que el pipeline transitorio
trabaje a **paso seleccionable** (`dt` = 1 h / 15 min / 10 min / 5 min) en los modos
**DIARIO / multidía / VENTANA**. **ANUAL queda horario por diseño** (día típico mensual).

**Decisiones de alcance (usuario, 2026-07-19):**
- Paso sub-horario habilitado para **ambas fuentes**: clima medido nativo re-remuestrea
  desde `datos_nativos`; NASA POWER (u horario) se **interpola** al paso fino con
  advertencia de *resolución sintética* (`ADV_PASO_SINTETICO`).
- **`dt = 1 h` por defecto**; 15 min opt-in; 5 min permitido con **advertencia física**.

## Auditoría de supuestos `dt=1h` (paso 0, hecha)

Hallazgo central: **el motor TD y el pipeline transitorio ya son casi agnósticos al
paso** — operan sobre `forzantes.t_s` e interpolan las forzantes linealmente en cada
evaluación del RHS (`camara_termodinamica:444`). El paso horario está cableado en pocos
puntos:

| # | Lugar | Asume | Trabajo 1b |
|---|-------|-------|-----------|
| 1 | `clima_medido.remuestrear_horario:645` (`"1h"`) | agrega a hora | generalizar a paso destino |
| 2 | `balance_global.armar_forzantes_ventana:1965` (`t_s=arange(n)·3600`) | 3600 s | derivar `dt` del `df.index` |
| 3 | `armar_forzantes_aire` (`dt_s=3600` default) | — | ✅ ya parametrizado; pasarle `dt` |
| 4 | `camara_termodinamica` `max_step=3600.0` (678, 1142) | cap integrador | derivar de espaciado de `t_s` |
| 5 | `_correr_colector_horizonte` (colector por nodo) | costo ∝ nodos | advertencia física + costo |
| 6 | `ui/p1_tipologia.py` | sin selector | selector `dt` gateado |
| 7 | `operacion_anual_camara`, `dia_tipo_mensual` | horario | **sin cambios** (ANUAL horario) |

No-hallazgos (ya agnósticos): `slice_clima_ventana` y `slice_n_dias_consecutivos`
slicean por máscara de fecha (no por conteo de filas); `auxiliar_calc` mapea
`t/3600 % 24` a hora del día (correcto a cualquier paso).

## Física del modelo

- **Cuasi-estacionariedad del colector:** τ del absorbedor sin capacitancia ≈ 3–5 min.
  A 15 min y a 10 min (paso muy común en dataloggers, ej. CR23X) el modelo estacionario
  nodo-a-nodo es sólido (≥ 2·τ); a 5 min es marginal (el
  colector *sobre-reacciona* a transitorios de nube porque no tiene inercia térmica
  → picos de T_salida más agudos que la realidad). Por eso 5 min lleva
  `ADV_PASO_FINO_COLECTOR`. Mejora futura (fuera de 1b): retardo de 1er orden a la
  salida del colector.
- **Interpolación de las forzantes en el motor TD:** el RHS interpola linealmente entre
  nodos; refinar el paso solo agrega valor si los nodos traen información nueva
  (transitorios reales). Con nodos sub-horarios *reales* (medido nativo) se captura la
  dinámica de nubes; con nodos *interpolados* de NASA horario no se agrega información
  física — de ahí la advertencia de resolución sintética.
- **Upsampling sintético de NASA (elección del usuario):** interpolar T/HR/P/viento
  horarios a 15/5 min es benigno (autocorrelación larga). Interpolar GHI/POA horarios es
  **cosmético**: suaviza la curva sin reponer los transitorios sub-horarios que el paso
  fino busca. Se permite (para ejercitar la maquinaria y homogeneizar el pipeline) pero
  con `ADV_PASO_SINTETICO` explícito. No se aplica descomposición ni transposición extra:
  se interpola la POA/GHI ya resuelta a nivel horario.
- **Remuestreo nativo → paso de trabajo (medido):** si `paso_nativo ≤ dt`, media por
  bin (estimador insesgado, misma lógica que 1a; <50 % de muestras → NaN). Si
  `paso_nativo > dt` (nativo más grueso que el paso pedido, ej. nativo 30 min con dt
  15 min), se interpola con la misma advertencia sintética que NASA.
- **Costo computacional:** el colector se re-corre por nodo (~26 ms). VENTANA de 1 semana:
  168 nodos a 1 h → ~4 s; 672 a 15 min → ~17 s (forzado); ×5 con Picard natural.
  A 5 min una semana ≈ 2016 nodos → minutos. La UI muestra estimación/aviso antes de
  correr modos largos a paso fino.
- **Límites 1b:** ANUAL horario (sin cambio); presión/energía por trapezoide sobre
  `t_s` (ya lo hace, agnóstico); el paso es global del proyecto (un solo `dt` por corrida).

## Arquitectura (validada contra el código)

**Campo nuevo (core):**
- `core/configuracion.py::Configuracion.paso_trabajo_s: float = 3600.0` (default →
  back-compat total; nada lo pasa posicional). Validación `__post_init__`
  `CFG_PASO_TRABAJO_*`: ∈ {3600, 900, 600, 300} y solo != 3600 si modo != ANUAL
  (coacción defensiva a 3600 si ANUAL, con la UI como guardia primaria).

**Núcleo de remuestreo (calculos):**
- `clima_medido.py`: generalizar `remuestrear_horario` → `remuestrear_a_paso(df_nativo,
  paso_nativo_s, paso_destino_s, *, convencion)`. `remuestrear_horario` queda como wrapper
  fino (`paso_destino_s=3600`) para back-compat. Ramas: agregar (media) si
  `paso_destino ≥ paso_nativo`; interpolar (con flag sintético) si `<`.
- `clima_calc.py`: nueva `resolver_datos_trabajo(clima, paso_s) -> (df, advertencias)`
  — único punto que entrega el DataFrame al paso de trabajo:
  - `paso_s == 3600` → `clima.datos` tal cual (camino histórico, sin advertencia).
  - `paso_s < 3600` con `datos_nativos` y `frecuencia_nativa_s ≤ paso_s` →
    `remuestrear_a_paso(datos_nativos, …)` (real).
  - resto → interpolar `clima.datos` horario al paso (`df.resample(f"{paso}s").interpolate`)
    + `ADV_PASO_SINTETICO`.
  Reusa la política de huecos donde aplique. POA/GHI se interpolan ya resueltas.

**Forzantes (balance_global):**
- `armar_forzantes_ventana`: derivar `dt` de `df.index` (`(idx[1]-idx[0]).total_seconds()`,
  fallback 3600 si `n==1`) en vez de `·3600`. El `df` que recibe ya viene al paso de
  trabajo (el llamador lo resuelve con `resolver_datos_trabajo`).
- `calcular_todo_ventana`, `calcular_todo_transitorio`: sin cambio de firma (reciben
  forzantes con `t_s` correcto); el `dt` viaja dentro de `forzantes.t_s`.
- `armar_forzantes_aire`: los llamadores pasan `dt_s=paso_trabajo_s` (ya soportado).

**Motor TD (camara_termodinamica):**
- `simular_secado` y `simular_cascada`: derivar `max_step` del espaciado de las forzantes
  (`min(3600.0, mediana(diff(t_s)))`) en vez del literal `3600.0`. Sin cambio de firma.

**UI:**
- `ui/p1_tipologia.py`: selector `p1_paso_trabajo` (options estables `"h"/"15min"/"5min"`
  → `{3600,900,600,300}` + `format_func` con `t()`), **solo visible si modo != ANUAL**;
  escribe `configuracion.paso_trabajo_s` vía `dataclasses.replace`. Caption de aviso a
  15/5 min (sintético si fuente horaria; físico a 5 min).
- `ui/p4_camara.py` (`_construir_forzantes_ventana`) y `ui/p7_resultados.py`
  (`_render_ventana`, rama transitoria): resolver el slice con `resolver_datos_trabajo(
  clima, proyecto.configuracion.paso_trabajo_s)` antes de armar forzantes; propagar
  advertencias sintéticas a la UI. Estimación/aviso de costo antes de correr modos largos
  a paso fino.

**i18n (los TRES yaml, paridad):**
- `p1.paso.*` (label/help/opciones h/15min/10min/5min + caption sintético/físico).
- `advertencias.ADV_PASO_SINTETICO.*`, `advertencias.ADV_PASO_FINO_COLECTOR.*`.

## Etapas (cada una: suite verde + black/ruff + auditar_i18n.py)

- **E1** Core: `Configuracion.paso_trabajo_s` + validación. Tests back-compat/validación.
  Riesgo bajo.
- **E2** Remuestreo: `remuestrear_a_paso` + wrapper; `resolver_datos_trabajo`. Fixtures:
  nativo 600 s → 900/300 s (real); horario → 900 s (sintético, con advertencia). ~8 tests.
  Riesgo medio.
- **E3** Forzantes agnósticas: `armar_forzantes_ventana` deriva dt; `max_step` derivado en
  motor TD. Test clave: **equivalencia** — misma VENTANA a 1 h vs 15 min sobre forzante
  suave converge (t_secado/masa dentro de tolerancia); serie fina tiene N× nodos. ~6 tests.
  Riesgo medio.
- **E4** UI P1 selector + gating ANUAL + i18n ×3. Helper puro `_opciones_paso`. Riesgo medio.
- **E5** Wire-up P4/P7: resolver al paso de trabajo + propagación de advertencias + aviso de
  costo. Prueba AppTest DIARIO/VENTANA a 15 min. Riesgo medio-alto.
- **E6** Cierre: integración con .xls ADITAL nativo 10 min → VENTANA a 15 min real (nativo)
  vs 5 min; CHANGELOG [Unreleased], mejoras.md §38, bitácora, mapa_conexiones.md, memoria.

Camino crítico: E1→E2→E3→E5; E4 paralelizable tras E1.

## Verificación end-to-end

1. Suite + black + ruff + `auditar_i18n.py` (=0) en cada etapa.
2. E3: equivalencia 1 h↔15 min sobre entrada suave (convergencia); divergencia esperada y
   documentada sobre entrada con transitorios (el paso fino captura picos que el horario borra).
3. E5 (app): DIARIO y VENTANA a 15 min corren y grafican; 5 min dispara warning físico;
   NASA a 15 min dispara `ADV_PASO_SINTETICO`; ANUAL no muestra selector.
4. E6: ADITAL nativo 10 min → VENTANA mayo-junio 2010 a 15 min (real, sin advertencia
   sintética) vs a 5 min (con advertencia física); coherencia de masa evaporada acumulada.
