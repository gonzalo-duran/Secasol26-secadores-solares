# Plan — Mejora 38, Fase 2: validación medido vs simulado (colector)

## Contexto

Fases 1a (ingesta de clima medido) y 1b (motor agnóstico al paso) ya permiten forzar el
modelo con datos propios a la resolución nativa. La Fase 2 cierra el lazo de **validación**:
contrastar la salida **simulada** contra una señal **medida** de referencia y cuantificar el
ajuste (RMSE, MBE, MAE, R², NSE, índice de Willmott).

**Decisiones de alcance (usuario, 2026-07-19):**
- **Colector aislado primero**: la señal a validar es la **temperatura de salida del
  colector** simulada vs medida. Caso ideal: prototipo colector 10 m del INENCO (validar el
  modelo del colector aislado, sin la cadena completa cámara/producto).
- **Carga separada de la señal de referencia**: uploader propio en P3, independiente del
  clima de P2 (el medido de referencia puede venir en otro archivo que el clima).
- El módulo de métricas se diseña **genérico y puro** desde el arranque: la Fase 3
  (calibración) lo reusa como función objetivo.

## Física del modelo

- **Qué valida la T de salida del colector:** es el observable integrador del modelo de
  colector (balance HWB + Nu local + propiedades del aire variables + POA). Un buen ajuste
  respalda la cadena óptica-térmica; un sesgo sistemático (MBE) apunta a un parámetro
  (absortancia, U_L, η₀) — insumo directo para la Fase 3.
- **Errores sistemáticos esperados (no son "error de modelo"):**
  - *Representatividad del clima:* si el clima de forzado es NASA (celda ~0.5°) y el medido
    es del sitio, la POA de entrada ya trae error → parte del residuo es del forzante, no del
    colector. **Recomendación fuerte: validar con clima MEDIDO del mismo ensayo** (1a), con
    POA medida coplanar (1a) para eliminar transposición.
  - *Estado cuasi-estacionario:* el colector no tiene capacitancia → en transitorios de nube
    la T simulada reacciona más rápido que la real (la placa real amortigua). A paso fino
    (1b) esto se ve como picos simulados más agudos. Es esperable; se mitiga validando en
    condiciones de cielo estable o a paso ≥ 10–15 min.
  - *Convención de timestamp:* medido instantáneo vs promedio del intervalo → medio paso de
    corrimiento → sesgo aparente en la subida/bajada. La ingesta declara la convención (reuso
    de 1a) y alinea antes de comparar.
- **Alineación temporal:** medido y simulado viven en grillas distintas. Se **interpola la
  serie simulada a los timestamps medidos** (o ambas a una grilla común) y se descartan los
  pares con NaN. La interpolación lineal de T es benigna (autocorrelación larga). Solo se
  comparan instantes con dato válido en ambas; `n_pares` se reporta siempre.
- **Métricas (definiciones fijas, sobre pares alineados sin NaN):**
  - RMSE = √⟨(sim−med)²⟩ — magnitud del error, penaliza outliers.
  - MBE = ⟨sim−med⟩ — **sesgo con signo** (clave para diagnosticar qué parámetro corregir).
  - MAE = ⟨|sim−med|⟩ — error típico robusto.
  - R² = coef. de determinación (correlación²) — captura forma, **ciego al sesgo**.
  - NSE (Nash–Sutcliffe) = 1 − Σ(sim−med)²/Σ(med−⟨med⟩)² — skill vs la media (puede ser <0).
  - d (Willmott) = 1 − Σ(sim−med)²/Σ(|sim−⟨med⟩|+|med−⟨med⟩|)² — acuerdo acotado [0,1].
  - Se reportan **RMSE + MBE + R²** como principales; NSE/d/MAE como secundarios. Unidades de
    la señal (°C) para RMSE/MBE/MAE; adimensionales para R²/NSE/d.

## Arquitectura (validada contra el código)

**Nuevos módulos:**
- `calculos/metricas_validacion.py` — **puro** (numpy, sin pandas/streamlit): `rmse`, `mbe`,
  `mae`, `r2`, `nse`, `indice_willmott` sobre dos arrays alineados (NaN → error
  `MVAL_SERIES_VACIAS`/filtrado); `MetricasAjuste` (frozen dataclass con todas + `n_pares`);
  `calcular_metricas(y_med, y_sim) -> MetricasAjuste`. Reusable como función objetivo (Fase 3).
- `core/validacion.py` — dataclasses puras: `ConfigReferencia(columna_timestamp,
  columna_valor, unidad, variable="T_salida_colector_C", zona_horaria, convencion_timestamp,
  hoja, fila_encabezado, marcadores_invalidos)` con validación `VREF_CONFIG_*`;
  `SenalReferencia(variable, serie [pd.Series SI], unidad_origen, frecuencia_nativa_s,
  n_invalidos)`.
- `calculos/ingesta_referencia.py` — parseo del archivo de referencia reusando la maquinaria
  de 1a (`clima_medido.leer_tabla`, `listar_hojas`, parseo de timestamp serial-Excel/texto,
  `inferir_frecuencia_s`, `regularizar_grilla`, `remuestrear_a_paso`): `ingerir_referencia(
  df_crudo, config) -> SenalReferencia` (timestamp→UTC, marcadores→NaN, unidad→SI [°C→K o se
  mantiene °C para display], QC de rango). `alinear_con_simulada(senal, t_sim, y_sim) ->
  (y_med, y_sim_alineada, timestamps)` (interpola la simulada a los timestamps medidos).

**Modificaciones:**
- `ui/p3_colector.py`: nueva sección **"🔬 Validación con datos medidos"** (expander, al pie
  del tab). Flujo con session_state prefijo `p3_val_`: subir archivo → hoja/encabezado (excel)
  → mapear (columna timestamp + columna de T de salida + unidad + tz + convención) → procesar
  (spinner, errores `VREF_*`) → **correr el colector sobre el período de la referencia**
  (reusa `_evaluar_ventana`/`_evaluar_diario` con el slice de clima que cubre el lapso medido;
  aviso claro si el clima de P2 no cubre el período) → overlay Plotly (medido vs simulado, dos
  trazas) + **tabla de métricas** (RMSE/MBE/R² destacados; NSE/d/MAE en detalle) + n_pares y
  período efectivo. Helpers puros module-level testeables (`_config_referencia_desde_widgets`,
  `_tabla_metricas`).
- i18n: árbol nuevo `p3.validacion.*` (~25 claves) + `graficas.validacion.*` + errores
  `advertencias.VREF_*`/`MVAL_*` si se muestran — **en los TRES yaml** (paridad).
- `requirements.txt`: sin dependencias nuevas (reusa xlrd/openpyxl de 1a).

## Estado: E1–E5 + FASE 2b IMPLEMENTADAS (S54, working tree). Suite 1411+1.

**Fase 2b (S54):** validación de colector aislado forzado con el clima del propio ensayo.
`ConfigReferencia.fecha_fija` (timestamps de solo hora) + `ingesta_referencia.
ingerir_clima_forzante` (Ta + POA medidas → df de forzado con `POA_med_Wm2`) +
`_series_simuladas_colector(clima_forzante=…)`. UI en P3: checkboxes "fecha fija" y "forzar con
clima medido" con mapeo de Ta/POA. **Fix colateral:** `AttributeError` de
`CONVENCIONES_TIMESTAMP` (módulo equivocado) en el render de P3, blindado con smoke test
AppTest. **Validación real (prototipo colector 10 m INENCO, cap. 2):** a v≈8 m/s (caudal alto
0.8 kg/s) RMSE 0.91 °C, MBE +0.20 °C, R² 0.987.

## Etapas (cada una: suite verde + black/ruff + auditar_i18n.py)

- **E1** `calculos/metricas_validacion.py` puro + `MetricasAjuste`. Tests: valores exactos
  contra casos analíticos (serie idéntica → RMSE=0, R²=1, MBE=0; sesgo constante → MBE=sesgo,
  R²=1; anti-correlación → R² bajo/NSE<0); manejo de NaN/longitudes. ~10 tests. Riesgo bajo.
- **E2** `core/validacion.py` (dataclasses + validación) + `calculos/ingesta_referencia.py`
  (parseo reusando 1a). Fixture: CSV/xls sintético estilo ADITAL (serial Excel, 'NAN', T en
  °C, 10-min). Tests: ingesta correcta, unidades, timestamp, QC. ~8 tests. Riesgo medio.
- **E3** `alinear_con_simulada` + orquestación validación (correr colector sobre el lapso +
  alinear + métricas). Test: señal sintética = simulada + ruido conocido → métricas esperadas;
  cobertura parcial del clima → aviso. ~6 tests. Riesgo medio.
- **E4** UI P3 (sección validación) + i18n ×3 + overlay/tabla. Helpers puros con tests
  (patrón test_p2_medido). Prueba manual: archivo real. Riesgo alto (UI).
- **E5** Cierre: test de integración (skipif) con dato real si está disponible; CHANGELOG,
  mejoras.md §38, bitácora, mapa_conexiones, memoria, capítulo/nota de manual si aplica.

Camino crítico: E1→E2→E3→E4. E1 desbloquea Fase 3.

## Verificación end-to-end

1. Suite + black + ruff + `auditar_i18n.py` (=0) en cada etapa.
2. E1: métricas contra casos analíticos cerrados (idéntica, sesgada, anti-correlada).
3. E3: colector forzado con clima medido de un ensayo + T de salida medida del mismo ensayo →
   RMSE/MBE/R² físicamente razonables (RMSE ~2–5 °C esperable para prediseño).
4. E4 (app): cargar la referencia, ver overlay + métricas; período fuera del clima → aviso.

## Relación con Fase 3 (calibración)

`metricas_validacion.calcular_metricas` es la **función objetivo** que la Fase 3 minimizará
(reusando la maquinaria de barridos `calculos/barrido_parametrico.py`): barrer un parámetro
(absortancia, U_L, η₀) y quedarse con el que minimiza RMSE/|MBE| contra la referencia. Por eso
E1 se diseña puro y desacoplado de la UI.
