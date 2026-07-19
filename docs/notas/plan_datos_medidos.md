# Plan — Mejora 38, Fase 1a: ingesta de datos climáticos medidos (CSV/XLS)

## Contexto

Secasol solo puede forzarse con clima NASA POWER. La mejora 38 (`docs/notas/mejoras.md`
§38) pide levantar datos medidos por el usuario. Secuencia acordada (discusión 2026-07-18):
**1a** ingesta remuestreada a horaria (motor intacto) → 1b motor agnóstico al paso → 2
validación → 3 calibración. Este plan cubre SOLO 1a. Dataset de referencia real: ADITAL
2010 (`docs/notas/dataset/secador ADITAL - Toto San Carlos/`, 10-minutal instantáneo, hora
local UTC−3, 'NAN' strings, headers que mutan entre hojas, HR cruda en un período, clima
casi ausente; coordenadas correctas 25°53′S 65°56′O ~1700 m).

**Idea central:** la ingesta produce el contrato existente `Clima.datos` (7 `COLUMNAS_SI`,
DatetimeIndex tz-aware UTC, paso horario, SI) → los motores no se tocan. Completador por
columna con **procedencia** (medida / derivada / completada-NASA / default) visible antes
de confirmar. POA medida en plano de colector = primera clase. Resolución nativa se guarda
para la fase 1b.

## Física del modelo

- **Remuestreo instantáneo → media horaria:** media de N muestras instantáneas = estimador
  insesgado de la media horaria; error despreciable en T/HR/presión (autocorrelación larga),
  ±10–20 % en GHI horaria con nubosidad cumular (aliasing de nubes; ruido no sesgado que se
  atenúa en agregados). Hora con <50 % de muestras válidas → NaN (mejor hueco explícito que
  media sesgada). Etiqueta = hora de inicio [HH, HH+1), UTC — réplica de NASA POWER para que
  día tipo y POA sean comparables entre fuentes. `datos_nativos` conserva lo que el promedio
  destruye (transitorios, para 1b).
- **Descomposición Erbs (GHI→DNI/DHI), solo si faltan componentes:** correlación horaria
  empírica; RMSE ~15–30 % en DNI horaria, mucho menor en agregados; sobreestima difusa en
  climas de alta claridad (Valles Calchaquíes, kt alto) → POA transpuesta algo subestimada
  en días claros. Se aplica DESPUÉS del remuestreo (la correlación es horaria). Con POA
  medida directa, Erbs solo alimenta caras de cámara y respaldo — segundo orden.
- **Completado NASA (sitio vs celda MERRA-2 ~0.5°):** T con sesgo por cota celda↔sitio
  (~−6.5 K/km; avisar si `altitud_nasa_m` vs `altitud_m` difieren >300 m — dato disponible);
  viento de celda no ve canalización de valle; GHI satelital ±15–20 % horario, bueno mensual.
  Mezclar columnas medidas con columnas de celda rompe correlación inter-variable — aceptable
  para prediseño, POR ESO la tabla de procedencia se muestra siempre antes de confirmar.
- **POA medida directa:** elimina los dos errores dominantes (descomposición + transposición);
  vale SOLO para el plano medido — si el usuario cambia pendiente/acimut después, avisar
  (warning, análogo a la invalidación por lat/lon). QC de rango es la única defensa contra
  piranómetro sucio/descalibrado (límite documentado).
- **Viento:** contrato del proyecto = `WS_ms` a 2 m (NASA WS2M). Viento medido a otra altura
  (ADITAL: 3 m) se normaliza a 2 m con perfil log neutro (z0=0.05 m). **Inconsistencia
  pre-existente documentada, NO se toca en 1a:** `chimenea_calc._Z_REF_VIENTO_M=10.0` asume
  10 m — issue aparte (altera resultados de P6, requiere revalidación propia).
- **Límites 1a:** paso horario (sub-horario = 1b); campaña dentro de un año calendario
  (`CLIMED_PERIODO_MULTIANIO`); ANUAL exige 12 meses cubiertos (gating); sin corrección de
  sesgo NASA↔sitio; QC marca/anula, no corrige.

## Arquitectura (validada contra el código por exploración)

**Nuevos módulos:**
- `core/clima_medido.py` — dataclasses puras (van en core para que `Clima` las referencie
  sin que core importe calculos): constantes `PROCEDENCIA_*`, `VARIABLES_MAPEABLES`
  (incluye `POA_med_Wm2`), `UNIDADES_POR_VARIABLE`, `MapeoColumna(variable, columna_origen,
  unidad)`, `ConfigMapeoClima(columna_timestamp, zona_horaria, convencion_timestamp
  instantanea|promedio_fin|promedio_inicio, columnas, hoja, fila_encabezado,
  altura_anemometro_m, plano_piranometro horizontal|plano_colector, marcadores_invalidos)`
  con validación `CLIMED_CONFIG_*` en `__post_init__`, `ChequeoQC`, `ReporteQC`.
- `calculos/clima_medido.py` — pipeline puro, errores prefijo `CLIMED_`:
  `listar_hojas(bytes, nombre)` · `leer_tabla(bytes, nombre, *, hoja, fila_encabezado)`
  (CSV sniffer; .xls→xlrd, .xlsx→openpyxl) · `sugerir_mapeo(columnas)` (regex
  acento-insensible; lista de exclusión de canales de proceso: quemador|chimenea|caño|
  inter|prod|volt) · `aplicar_mapeo(df, config)` (timestamp serial-Excel o string →
  tz-localize→UTC, marcadores→NaN, unidades→SI, viento→2 m, plano_colector→`POA_med_Wm2`) ·
  `inferir_frecuencia_s` (moda de diffs, <80 % → `CLIMED_FRECUENCIA_IRREGULAR`) ·
  `regularizar_grilla` · `qc_fisico(df, *, lat, lon, alt_m)` (rangos → NaN; GHI nocturna
  clip; GHI>1.2·extraterrestre → NaN; sensor congelado → solo aviso; variable 100 % NaN →
  `CLIMED_TODO_INVALIDO`) · `remuestrear_horario` (media, closed/label left, <50 % → NaN) ·
  `derivar_dni_dhi_erbs` (pvlib erbs, patrón ya usado en tests) · `completar_con_nasa(df,
  emplazamiento, anio, *, obtener_clima_fn=None)` (inyectable para tests; reusa
  `obtener_clima` + su cache) · `ingerir_clima_medido(df_crudo, config, emplazamiento, *,
  obtener_clima_fn=None) -> Clima` (orquesta todo + reusa `_aplicar_politica_huecos` de
  clima_calc — a esa altura filas==horas vale; exponer alias público) ·
  `meses_cubiertos(datos, tz)` · cache: `hash_archivo`, `hash_ingesta(hash+config)`,
  `guardar_cache_medido`/`cargar_cache_medido` (parquet en `data/cache/clima_medido/`,
  metadatos como clima_calc), `config_desde_dict`.

**Modificaciones:**
- `core/clima.py`: `Clima` gana campos con default (back-compat total, nada los pasa
  posicional): `fuente="nasa_power"` ("medido"/"hibrido"), `procedencia: dict|None`,
  `frecuencia_nativa_s`, `datos_nativos`, `mapeo`, `qc` + constante
  `COLUMNA_POA_MEDIDA="POA_med_Wm2"` (NO entra a COLUMNAS_SI). Docstring: WS_ms es a 2 m.
- `calculos/clima_calc.py::calcular_POA_horizonte`: si `tilt_deg is None and
  acimut_duffie_deg is None and "POA_med_Wm2" in datos_clima` → devuelve la medida
  (clip ≥0) con relleno fila-a-fila por transposición donde sea NaN. Verificado: los 7
  call sites del plano del colector llaman sin overrides; el único con overrides es
  `radiacion_camara.poa_caras_camara` (caras de cámara — correcto que transponga).
- `ui/p2_emplazamiento.py` (secciones nuevas, helpers puros módulo-nivel testeables):
  radio de fuente `p2_fuente_clima` (claves estables nasa_power/medido + format_func) →
  flujo medido por pasos con session_state prefijo `p2_med_` (patrón anti-reprocesado
  `st.session_state.pop(key_uploader)` + `st.rerun()` de p5:274-303; tabla cruda cacheada
  por (hash,hoja,fila) para no re-parsear 15 MB por rerun; resultado invalidado si cambia
  el hash de config): subir → hoja/encabezado (excel) → mapeo (selectbox columna+unidad por
  variable, auto-sugerido; tz, convención, altura anemómetro, plano piranómetro) →
  procesar (spinner, errores CLIMED_*) → revisión (métricas CalidadClima reutilizadas,
  tabla de procedencia, reporte QC, previews con `_fig_temperatura`/`_fig_irradiancia`,
  decisión de huecos con el patrón existente) → confirmar (`proyecto.clima = resultado`,
  cache, limpiar prefijo, success). Snapshot JSON de sección "clima_medido" (hash + mapeo)
  que restaura desde cache sin re-subir. Secciones existentes de P2 siguen andando
  (mismo contrato); ajustar captions por fuente y guarda si el día de análisis cae fuera
  del período.
- Gating ANUAL (punto real verificado: `ui/p4_camara.py:1350 _render_operacion_anual`):
  si `len(meses_cubiertos(...)) < 12` → warning + return (sin botón). Defensivo:
  `ValueError("ANUAL_CLIMA_INCOMPLETO")` en `operacion_anual_camara` antes del bucle.
  Caption informativo en P1 si fuente medida con cobertura parcial.
- Strings de fuente: `presion_representativa_proyecto` etiqueta por
  `getattr(clima, "fuente", "nasa_power")`; P7 `_bloque_meta_emplazamiento_clima` agrega
  fuente/procedencia/período (aditivo, reporte.py lee con .get()); fila "Fuente" en PDF.
- `requirements.txt`: **agregar `xlrd==2.0.2` y `openpyxl==3.1.5` pinneados** (los .xls
  legado y .xlsx de usuarios; comentario estilo del archivo). Deploy HF: instalan limpio
  en python:3.13-slim; `docs/` (datasets) no se deploya.
- i18n: árboles nuevos `p2.fuente.*`, `p2.medido.*` (~60 claves), `p4.anual.clima_incompleto`,
  `p1.modo.clima_parcial`, fila PDF en `reporte.yaml` — **en los TRES yaml** (paridad
  exigida por test_idiomas). Nunca t() a nivel módulo; options estables + format_func.

## Etapas (cada una termina con suite verde + black/ruff)

- **E0** Dependencias: requirements.txt (xlrd/openpyxl). Done: pip install limpio, .xls
  ADITAL abre. Riesgo bajo.
- **E1** Core: `core/clima_medido.py` + campos de `Clima`. Tests: back-compat defaults,
  validación de config. Riesgo bajo.
- **E2** Pipeline núcleo: leer/sugerir/mapear/frecuencia/regularizar/remuestrear.
  Fixture clave `_df_estilo_adital()` (10-min, serial Excel, 'NAN', hueco 220 min, columna
  cruda fuera de rango, nombres reales). ~11 tests. Riesgo medio.
- **E3** QC físico + ReporteQC. ~5 tests. Riesgo medio.
- **E4** Erbs + completador NASA (obtener_clima_fn fake) + `ingerir_clima_medido` +
  `meses_cubiertos`. ~9 tests. Done: el Clima resultante pasa por `dia_tipo_mensual`,
  `slice_clima_ventana` y `armar_forzantes_aire` SIN tocarlos. Riesgo medio-alto.
- **E5** POA medida en `calcular_POA_horizonte`. ~5 tests + regresión exacta de los
  existentes. Riesgo medio. (Paralelizable con E6/E8 tras E4.)
- **E6** Cache parquet + snapshot de sección + roundtrip config. ~4 tests. Riesgo medio.
- **E7** UI P2 + i18n ×3 (la etapa más grande). Helpers puros `_config_desde_widgets`,
  `_tabla_procedencia`, `_resumen_medido` con tests (patrón test_p2_ventana). Done manual:
  flujo completo con CSV sintético y con el .xls ADITAL real; recarga + snapshot restaura
  sin re-subir. Riesgo alto.
- **E8** Gating ANUAL + strings de fuente + PDF. ~4 tests. Riesgo bajo.
- **E9** Cierre: test de integración `skipif` sobre los .xls ADITAL reales (hojas,
  sugerencia sobre headers reales, ingesta end-to-end de `Hoja1`), CHANGELOG [Unreleased],
  mejoras.md §38 estado, bitácora, mapa_conexiones.md, capítulo/nota de manual si aplica.
- **E8b (OPCIONAL, decidir al final):** flag "extender a año completo con NASA"
  (habilitaría ANUAL con campañas parciales, fuente="hibrido").

Camino crítico: E0→E1→E2→E3→E4→E7; E5/E6/E8 cuelgan de E4, paralelizables antes de E7.

## Verificación end-to-end

1. Suite completa + black + ruff + `auditar_i18n.py` (=0 residuo) en cada etapa.
2. E2–E4: fixture ADITAL-sintético reproduce las trampas reales; HR cruda del período 2
   debe terminar en `CLIMED_TODO_INVALIDO` (con nombre de variable) — el usuario decide
   no mapearla o corregirla.
3. E7 (manual, app corriendo): cargar `Medidas ADITAL 15-5-2010 a 18-6-2010.xls` hoja
   `Hoja1` con coords 25°53′S 65°56′O → mapear (solo T/HR de secador NO se mapean — son
   canales de proceso; clima completo desde NASA 2010) → confirmar → P2 grafica el período;
   P4/P7 corren VENTANA/multidía sobre mayo-junio 2010; P4 ANUAL bloqueado con aviso claro.
4. Segundo caso manual: CSV sintético con GHI+T+timestamp (sin DNI/DHI/viento/presión) →
   procedencia muestra derivada (DNI/DHI Erbs) + completada-NASA (viento) — tabla coherente.

## Hallazgos colaterales (NO se tocan en 1a — decisión del usuario aparte)

1. **BUG confirmado modo ANUAL:** `operacion_anual_camara.py:176` divide HR por 100 pero
   `clima_calc.py:257` ya la convirtió a fracción → ω ambiente ~100× baja en ANUAL (aire
   irrealmente seco → secado optimista). Fix de una línea + test; altera resultados ANUAL
   existentes. Recomendación: mini-fix separado ANTES de esta mejora.
2. Inconsistencia viento 2 m (contrato/NASA WS2M) vs `chimenea_calc` que asume 10 m —
   issue aparte (afecta P6, requiere revalidación).
