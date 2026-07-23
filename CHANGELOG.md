# Changelog

Todos los cambios notables a Secasol se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

Mejoras post-1.2 (sin orden estricto):

- **No arrancar lotes con mal pronóstico** en el modo anual: hoy el encadenado carga un
  lote aunque el día venga nublado, cosa que ningún operador hace, y eso infla los lotes
  frustrados con casos que en la práctica no ocurrirían.
- **Persistir `PoliticaRecarga`** en el snapshot del proyecto: hoy vive en los widgets de
  P4, así que sobrevive la sesión pero no un guardar/cargar.
- Historia temporal por zona en `simular_cascada` (deuda de la mejora 38, fase 4):
  habilitaría el overlay contra termopares fijos del túnel y una vista previa de N zonas
  en P4.
- Modo anual para el **túnel semicontinuo**: hoy `simular_anual` lo rechaza con
  `ANUAL_SEMICONTINUO_NO_SOPORTADO` porque su operación es flujo continuo y no lotes.
- `h_w` de McAdams usa el viento a 2 m sin corregir a la altura del equipo.
- Pérdidas IR nocturnas del vidriado y discretización vertical del producto por bandeja (fuera
  de alcance de la cámara radiativa orientada — ver `docs/notas/plan_camara_radiativa_orientada.md`).

## [1.2.0] — 2026-07-23

### Changed

- **Modo anual reescrito sobre las 8760 h reales del clima** (S57). Reemplaza el
  esquema de "12 días típicos mensuales", que tenía problemas de fondo detectados en
  una auditoría: el número titular `kg_secados_anual` era **agua evaporada** rotulada
  como producto seco (factor 2-4× de sobrelectura); **η_térmica era idénticamente
  igual a η_colector** (0.5 fijo para cualquier diseño, por cancelación algebraica) y
  **η_total idéntica a η_drying** (por `E_aux` hardcodeado en 0); el colector real no
  entraba al cálculo salvo por su área; y `I_g_diaria_minima_MJ_m2` se declaraba y
  validaba sin usarse nunca.

  El motor nuevo (`calculos/simulacion_anual.py`) reusa el pipeline de ventana ya
  validado contra ADITAL: encadena lotes event-driven sobre el clima horario real, así
  que **la cantidad de lotes es un resultado** y la variabilidad del clima aparece
  (lotes que se alargan, lotes frustrados, dispersión de duración p50/p90).

  Métricas nuevas: producto seco y agua evaporada **separados**, lotes completos vs
  frustrados, días operables, energía específica [MJ/kg agua], fracción solar (compara
  energías útiles, no irradiancia incidente contra auxiliar), η_drying y η_total ahora
  con **auxiliar implementado** (dejan de ser el mismo número), y `aprovechamiento_aire`
  —deliberadamente no llamado η_pickup, porque no es comparable con esa literatura—.
  P7 suma **descarga CSV** de la tabla mensual, que no existía.

- **Superficie de respuesta del colector** (`calculos/superficie_colector.py`): el
  solver estacionario corriendo una vez por hora era el 95 % del costo del anual. Como
  en los pipelines forzados `T_entrada = T_amb`, el término de pérdidas de
  Hottel-Whillier-Bliss se anula y la respuesta queda casi afín en POA sobre un espacio
  de 3 dimensiones. ~180 solves interpolados reemplazan 8760: **3.76 min → 4.7 s (48×)**,
  con error medio 0.003 K y máximo 0.033 K sobre serie anual real.

- **Política de recarga de lotes** (`simulacion_ventana.PoliticaRecarga`). El
  encadenado recargaba en el instante exacto en que terminaba el lote anterior —a las
  3 de la madrugada si tocaba—, cosa que ningún operador hace. Ahora el lote siguiente
  espera a la hora de carga del día (default 8:00) y respeta un tiempo de maniobra
  (default 1 h). Sobre un año completo: **58 → 52 lotes, 1044 → 936 kg (−10 %)**. La
  tasa de régimen pasa a dividir por el **ciclo** (secado + espera) y no solo por el
  secado, que la sobrestimaba. Se puede desactivar, con aviso de que el número vuelve
  a ser una cota superior. Configurable en P4.

### Removed

- `calculos/operacion_anual_camara.py`, `OperacionAnualConfig` y el campo
  `Camara.operacion_anual` (el slider `batches_por_mes` de P4 desaparece: es un
  resultado). Las eficiencias tautológicas η_térmica y la duplicada η_total del
  esquema viejo ya no se reportan como tales.

### Fixed

- **La presión del sitio salía de la altitud de la grilla NASA, no del emplazamiento.**
  La celda de NASA POWER es de 0.5° y su altitud promedia el terreno que abarca: para
  Salta capital (1187 m) reporta **2786 m**, y `presion_representativa_proyecto` tomaba
  su presión media (73.1 kPa) tal cual. Error del 17 % en P que se propaga a toda la
  psicrometría —ω_sat ∝ P_sat/(P − P_sat), así que el aire "podía" cargar más humedad
  de la real y el secado salía **optimista**— y bajaba el punto de ebullición de 96 a
  91 °C. Ahora se aplica una **reducción barométrica** de la altitud de grilla a la del
  sitio (`_reducir_presion_a_altitud_sitio`), que conserva el desvío meteorológico de la
  fuente respecto de ISA pero lo ubica a la altura correcta: 73.10 → **89.15 kPa** en el
  caso real. Detectado sobre un reporte PDF del usuario. La leyenda de la carta
  psicrométrica afirmaba "altitud del emplazamiento", cosa que era falsa; ahora dice
  "presión del sitio".

- **Claves i18n crudas en el reporte PDF** (`reporte.anual.graficas`,
  `reporte.anual.fig.kg_mes`): faltaban en los YAML y salían literales. Y el rótulo
  "Lotes completados (sin completar)" se pisaba con su valor por ser demasiado largo
  para la columna.

- **El modo anual abortaba en sitios de altura.** Con el aire de entrada por encima de
  la ebullición local (a 2650 m el agua hierve a 91 °C), `omega_saturacion` lanzaba
  `PSICRO_PV_EXCEDE_P` y se perdía la simulación entera. Reportado por el usuario. Dos
  niveles: la métrica `aprovechamiento_aire` excluye esas horas —y el bloque de
  métricas va envuelto, así ninguna derivada puede tirar abajo una corrida de un año—,
  y el motor de cámara topea la presión de vapor al 90 % de la total
  (`_omega_saturacion_acotada`) para no abortar, avisando con `CAM_TD_SOBRE_EBULLICION`
  que **los resultados de esas horas no son confiables**: el modelo describe
  evaporación difusiva, no hervor.

- **Aluvión de advertencias repetidas en corridas largas.** La deduplicación comparaba
  strings exactos, pero los mensajes llevan el número de horas de cada lote ("durante
  5.6 h"), así que no filtraba nada: 52 lotes daban ~100 avisos casi idénticos y
  escondían los que sí eran distintos. Ahora se agrupan por **código**, con el conteo
  de cuántos lotes lo dispararon.

- El fixture de clima de los tests de barrido tenía **HR en porcentaje** violando el
  contrato de `Clima` (fracción [0,1]). El motor anual viejo lo enmascaraba: atrapaba
  el fallo mes a mes y devolvía ceros con advertencias, así que el test daba verde con
  los 12 meses fallando en silencio.

## [1.1.0] — 2026-07-21

### Added

- **Exports completos por modo de análisis** — el reporte de prediseño (PDF) y los
  snapshots TXT/JSON ahora cubren **todos** los modos, no solo Constantes/Transitorio:
  - **Modo Ventana (gran escala)**: la rama de producción de P7 gana el bloque de
    exportación (antes no había PDF, TXT ni JSON en ese modo). El reporte incluye la
    sección **"Producción en ventana"**: producto seco, tasa de régimen, agua evaporada,
    leña, estado; sub-bloque por subtipo (lotes en batch; avances, X de salida,
    throughput, cadencia y perfil por zonas en semicontinuo); **diagnóstico del caño
    maestro** (ΔT media/peor sobre el lapso y ΔP al caudal del sistema — antes sin
    representación en ningún export; `ResultadoVentana` gana los campos
    `cano_delta_T_media_K`/`cano_delta_T_minima_K`/`cano_delta_P_Pa` y
    `armar_forzantes_ventana` devuelve además un dict de diagnósticos); figuras del
    perfil del túnel y carta psicrométrica. La portada del PDF y el bloque de
    configuración de TXT/JSON suman **subtipo de gran escala, lapso de la ventana y
    paso de trabajo**.
  - **Operación anual de cámara**: si P4 la corrió, entra a los tres exports — agregados
    anuales (kg/año, eficiencias de Augustus Leon, energías, t de secado promedio),
    tabla de 12 meses y gráfica de barras kg/mes + η_total (builder
    `_fig_operacion_anual` extraído para reuso del PDF).
- **Validación y calibración con datos medidos en el reporte PDF** — sección nueva
  **"Validación con datos medidos"**, incluida automáticamente si el usuario validó o
  calibró algo en la sesión (colector en P3, cámara en P4, túnel en P7): overlay
  medido-vs-simulado, tabla de métricas (RMSE/MBE/MAE/R²/NSE/Willmott), y si hubo
  calibración la curva objetivo-vs-parámetro con el valor óptimo (los factores de cámara
  llevan su lectura física y la nota de que son diagnóstico, no diseño). La validación
  del túnel de P7 ahora **se persiste** en la sesión (snapshots de descargas y perfil
  por zona) y se invalida al recalcular la ventana.

- **Validación y calibración de cámara y producto (mejora 38, fase 4)** — P4 gana la
  sección **"🔬 Validación con datos medidos"**: se carga el archivo de un ensayo de cámara, se
  elige qué señal validar (**T del aire en cámara, HR del aire, T del producto, humedad del
  producto o pesadas de la muestra**) y la cámara se corre **aislada**, forzada con el aire de
  entrada medido en el mismo archivo, de modo que el error del colector no se mezcle con el de
  la cámara. Overlay medido-vs-simulado + métricas (RMSE/MBE/MAE/R²/NSE/Willmott) + bloque
  **"🎯 Calibración"** que barre un coeficiente de transporte y devuelve el factor que mejor
  ajusta. Módulos nuevos: `calculos/validacion_camara.py` (orquestación **pura**: corre la
  cámara aislada, extrae la serie de cada variable con timestamps absolutos y expone los dos
  objetos de comparación del túnel) y `ui/componentes/validacion_widget.py` (tabla de métricas,
  overlay, curva de calibración y perfil de zonas, compartidos con P3). `core/validacion.py` y
  `calculos/ingesta_referencia.py` se generalizaron a las seis variables de referencia con
  conversión y QC por magnitud (incluida la conversión de pesadas y de base húmeda a base
  seca), y `ingerir_forzantes_camara` construye el `ForzantesAire` desde el propio ensayo,
  dejando una advertencia por cada supuesto (HR de entrada, caudal, T ambiente, viento).
  La calibración distingue **qué se puede aplicar y qué no**: el **área efectiva de
  intercambio** (`area_bandeja`, parámetro nuevo del catálogo de barridos) es un campo real
  del proyecto —multiplica tanto `h·A` como `K_m·A`, y su valor ajustado es interpretable
  ("el área efectiva es 1.8× la de bandeja, coherente con rodajas apiladas")— así que tiene
  botón "aplicar" como en P3; `factor_K_m`/`factor_h_conv` quedan como **diagnóstico** y no
  se guardan, porque lo que absorben (analogía de Chilton-Colburn, isoterma del cultivar,
  ω de entrada supuesta) no transfiere a otro producto ni caudal. P4 suma además el bloque
  **"🔗 Diagnóstico de la cadena completa"**, que contrasta lo medido contra el resultado
  transitorio de P7 (sin calibrar sobre él: el residuo mezcla todos los eslabones).
  En **P7**, para el túnel semicontinuo, se suma **"🔬 Validación del túnel con datos
  medidos"**: como `simular_cascada` no guarda historia por zona, la comparación usa los dos
  objetos que sí son directos y libres del artefacto euleriano↔lagrangiano — las **descargas**
  por avance (la columna que sale, contra un muestreo de campo fechado) y el **perfil espacial**
  al cierre (tabla editable de valores medidos por zona, contra la foto instantánea del túnel),
  cada uno con sus métricas. `ResultadoVentana` pasa a exponer `X_salida_por_avance`,
  `T_prod_salida_por_avance_K`, `intervalo_avance_s` y `t0_utc` para hacerlo posible.
  Plan en `docs/notas/plan_datos_medidos_4.md`.

- **Calibración del modelo contra datos medidos (mejora 38, fase 3)** — la sección de
  validación de P3 gana un bloque **"🎯 Calibración"**: barre un parámetro del colector
  (velocidad de diseño, largo) sobre un rango y se queda con el valor que **minimiza el ajuste**
  contra el medido (RMSE / |MBE| / MAE), con curva objetivo-vs-parámetro, métricas del óptimo y
  botón para aplicarlo al proyecto. Motor puro nuevo `calculos/calibracion.py` (`calibrar_1d`
  recibe un callback de evaluación → desacoplado de la simulación/UI, reusa
  `metricas_validacion` como función objetivo y `barrido_parametrico.aplicar_parametro` para
  setear el parámetro). Verificado end-to-end sobre el colector 10 m del INENCO: la calibración
  encuentra automáticamente el óptimo (v ≈ 8 m/s → RMSE 0.91 °C, R² 0.987).
- **Validación de colector aislado con clima propio del ensayo (mejora 38, fase 2b)** — la
  sección de validación de P3 puede **forzar el colector con la temperatura ambiente y la
  irradiancia (POA) medidas en el propio archivo** (no con el clima de P2), aislando el modelo
  del colector de la representatividad del clima. Soporta además **timestamp de solo hora**
  (fecha fija del ensayo). Nuevas `ConfigReferencia.fecha_fija` y
  `ingesta_referencia.ingerir_clima_forzante`. Verificado end-to-end contra el prototipo de
  colector de 10 m del INENCO (tesis cap. 2): a caudal alto (~0.8 kg/s) el modelo reproduce la
  T de salida medida con **RMSE 0.91 °C, MBE +0.20 °C, R² 0.987**.
- **Validación por canal de salida (Tipo 2)** — en colector de doble canal activo (Tipo 2), la
  validación permite elegir la salida simulada a comparar: **mezcla (media), canal superior o
  canal inferior**, para empalmar con la columna medida correspondiente. Tipos 1/3/4 usan la
  única salida.
- **Validación del colector con datos medidos (mejora 38, fase 2)** — P3 gana una sección
  **"🔬 Validación con datos medidos"**: se carga (aparte del clima) una serie medida de
  temperatura de salida del colector, se corre el colector sobre ese período con el clima de
  P2 y se muestran el **overlay medido vs simulado** y las **métricas de ajuste**
  (RMSE, MBE con signo, MAE, R², NSE, índice de Willmott). Módulo puro nuevo
  `calculos/metricas_validacion.py` (reusable como función objetivo de la calibración,
  fase 3), `core/validacion.py` + `calculos/ingesta_referencia.py` (ingesta de la señal de
  referencia reusando la maquinaria de la fase 1a + alineación temporal medido↔simulado por
  interpolación de la serie simulada a los timestamps medidos). Sin dependencias nuevas.
- **Motor de simulación agnóstico al paso temporal (mejora 38, fase 1b)** — P1 gana un
  selector de **paso de trabajo** (1 hora por defecto / 15 min / 10 min / 5 min) para los modos
  Diario, multidía y Ventana (el modo Anual queda siempre horario). El paso sub-horario
  re-remuestrea desde `Clima.datos_nativos` cuando hay resolución nativa fina (dato real) o
  interpola el clima horario con aviso de **resolución sintética** (`ADV_PASO_SINTETICO`);
  a 5 min se advierte además que el colector (sin capacitancia térmica) sobre-reacciona a
  los transitorios de nube. Núcleo nuevo: `clima_medido.remuestrear_a_paso` y
  `clima_calc.resolver_datos_trabajo` (baseline interpolado + sobrescritura con columnas
  nativas reales, procedencia por columna). Las forzantes derivan el `dt` del índice del
  clima (no lo asumen horario) y el paso máximo del integrador del motor termodinámico se
  deriva del espaciado de las forzantes. `Configuracion.paso_trabajo_s` (default 3600,
  back-compat total; se coacciona a horario en Anual).
- **Ingesta de datos climáticos medidos (mejora 38, fase 1a)** — P2 gana un selector de
  fuente de clima: NASA POWER (flujo histórico) o **datos medidos** (archivo propio CSV /
  Excel .xls/.xlsx). Pipeline puro en `calculos/clima_medido.py`: mapeo declarativo de
  columnas con auto-sugerencia (excluye canales de proceso del secador), timestamps como
  serial Excel o texto (zona horaria y convención instantánea/promedio declarables),
  marcadores `'NAN'`, conversión de unidades a SI, normalización del viento a 2 m (perfil
  log), QC físico con reporte (rangos, irradiancia nocturna, cota extraterrestre, sensor
  congelado), remuestreo a paso horario (media, etiqueta = inicio de hora, réplica NASA),
  derivación DNI/DHI por Erbs, **completado por columna desde NASA POWER con procedencia
  visible** (medida / derivada / completada), política de huecos existente y cache parquet
  propia (`data/cache/clima_medido/`). La resolución nativa se conserva en
  `Clima.datos_nativos` para la futura fase 1b (motor sub-horario).
- **POA medida en plano de colector**: si el piranómetro está coplanar con el colector, la
  columna `POA_med_Wm2` reemplaza a la transposición Liu-Jordan para el colector
  (`calcular_POA_horizonte` la devuelve directo cuando se llama sin overrides); las caras
  de la cámara radiativa siguen transponiendo desde GHI/DNI/DHI.
- `Clima` gana `fuente` ("nasa_power"/"medido"/"hibrido"), `procedencia` por columna,
  `frecuencia_nativa_s`, `datos_nativos`, `mapeo` y `qc` (back-compat total).
- Snapshot JSON de sección "clima_medido" (mapeo + hashes) con restauración desde la cache
  local sin re-subir el archivo.
- Gating del modo ANUAL por cobertura: con clima de campaña parcial (< 12 meses) P4 lo
  bloquea con aviso claro (`ANUAL_CLIMA_INCOMPLETO` defensivo en `operacion_anual_camara`).
- Dependencias nuevas pinneadas: `xlrd==2.0.2` (.xls legado) y `openpyxl==3.1.5` (.xlsx).
- Validado end-to-end contra el dataset real ADITAL 2010 (tesis cap. 3): los tres `.xls`
  de la campaña se ingieren con sus trampas reales (test de integración `skipif` +
  verificación AppTest con descarga NASA real).

Nota: la mejora 38 queda **cerrada** en esta versión — fases 1a, 1b, 2, 2b, 3 (colector) y 4
(cámara y producto); ver `docs/notas/plan_datos_medidos.md` y `plan_datos_medidos_4.md`.

### Changed

- **`camara_calc.calcular_camara` / `calcular_camara_cascada` aceptan `factor_h_conv` y
  `factor_K_m`** (default **1.0**, resultado idéntico al anterior): son las perillas físicamente
  calibrables de la cámara, que el catálogo de barridos no cubría — ninguno de sus parámetros
  ataca la transferencia de masa. `factor_K_m` escala solo la evaporación; `factor_h_conv`
  arrastra a K_m por Chilton-Colburn y además cambia el calor sensible.
- **`ForzantesAire` gana `t0_utc`**: el instante absoluto que corresponde a `t_s[0] == 0`. El
  motor integra en tiempo relativo, así que sin ese ancla sus trayectorias no se pueden alinear
  contra una serie medida. Lo llenan los tres constructores de forzantes de P4 desde el índice
  del clima real y `armar_forzantes_ventana` desde el lapso; lo propagan
  `ResultadosCompletosTransitorio.t0_utc` y `ResultadoVentana.t0_utc`. Queda en `None` con
  forzantes sintéticas (la UI lo avisa en vez de dibujar un overlay corrido).

### Fixed

- **Modo Ventana sin botón de reporte** (reporte del usuario, corrida ADITAL): en gran
  escala + ventana, P7 no mostraba los botones de guardado (TXT/JSON/PDF). Las condiciones
  representativas de Constantes (T_amb, POA, viento, HR) pasaron a opcionales de punta a
  punta en los generadores para que la rama de ventana pueda exportar sin sliders.
- **P4 parecía colgado al calcular cámara en modo ventana**: el armado de forzantes (que
  re-corre el colector hora a hora sobre el lapso) ocurría fuera del spinner. Ahora el
  spinner "Armando forzantes del horizonte…" cubre esa etapa.
- **UX de validación de cámara**: aviso explícito en P4 de que conviene validar después de
  correr el sistema completo en P7, no como atajo temprano (reporte del usuario).
- **Gran escala + Ventana: P4 perdía la ventana y caía a un día sintético** — en tipología
  `GRAN_ESCALA` con modo VENTANA, el flag `usar_ventana` de P4 excluía explícitamente la gran
  escala (`and not es_gran_escala`), con el argumento de que el túnel tiene su pipeline propio
  en P7. Consecuencia: la vista previa de cámara caía a la rama "día real / sintético", que
  exige P3 evaluado **en modo diario** — condición que en VENTANA nunca se cumple, porque P3
  evalúa sobre la ventana. El usuario veía el aviso "P3 sin calcular (ejecutá 'Calcular
  desempeño del colector' en modo diario)" y la previa se calculaba con un **día sintético**,
  perdiendo el lapso y el clima real que P2 y P3 sí habían usado. Ahora el modo VENTANA vale
  para todas las tipologías en la previa de P4 (el constructor `_construir_forzantes_ventana`
  ya era agnóstico a la tipología); P7 sigue siendo la fuente de verdad, con su pipeline de
  cascada para el túnel. Además, en modo ventana los sliders de borde T_op/HR_op se ocultan,
  porque el aire de entrada sale del clima y del colector.
- **La previa de P4 en túnel semicontinuo no avisaba que resuelve un solo nodo** — P4 llama
  siempre a `calcular_camara` (CSTR monozona), nunca a `calcular_camara_cascada`: el gráfico de
  trayectorias necesita series temporales que `ResultadoCascada` no expone (solo perfiles
  finales y descargas por avance). El mensaje informativo del subtipo describía la topología
  del túnel pero no decía que los números de la previa **no** son los del túnel. Ahora, en
  subtipo SEMICONTINUO, un aviso explícito antes del botón de cálculo y sobre los resultados
  aclara que la previa es de un nodo (orden de magnitud), que no reproduce la variación
  longitudinal ni la sequedad emergente, y que el comportamiento completo se evalúa en P7.
- **Columna de timestamp mal mapeada crasheaba con `ZeroDivisionError` (detectado en el Space)**
  — mapear como timestamp una columna de **tiempo transcurrido** (0, 300, 600… segundos desde el
  inicio del ensayo) hacía que `pd.to_datetime` la leyera como **nanosegundos desde 1970**: la
  serie quedaba con paso 3e-07 s, pasaba los guardas de `inferir_frecuencia_s` (positivo y
  regular) y llegaba a `regularizar_grilla`, donde `int(round(3e-07)) == 0` producía `freq="0s"`
  → división por cero en las tripas de pandas, con traceback crudo en pantalla. Corregido en tres
  capas: (1) el parser corta con `CLIMED_TIMESTAMP_NUMERICO_AMBIGUO` cuando la columna es numérica
  pero no son seriales de Excel, y con fecha fija interpreta bien un numérico en [0,1) como **hora
  de Excel** (0.375 = 09:00); (2) `inferir_frecuencia_s` rechaza pasos < 1 s
  (`CLIMED_PASO_SUBSEGUNDO`); (3) `regularizar_grilla` rechaza un paso que redondea a 0 s
  (`CLIMED_PASO_INVALIDO`) y acota el tamaño de la grilla (`CLIMED_GRILLA_EXCESIVA`, bomba latente:
  1 s sobre un año son 31 M de filas). Las capas 2 y 3 protegen también la validación de P3, que
  reusa las mismas funciones.
- **Carga de archivos: nunca más un traceback crudo en producción** — los seis puntos de ingesta
  de archivos del usuario en P2 y P3 (listar hojas, leer tabla, procesar) atrapaban solo
  `ValueError`/`RuntimeError`; cualquier otra excepción de parseo llegaba a la pantalla como
  traceback. Ahora caen en un `except Exception` con el mensaje traducido `comun.error_inesperado`
  (tipo de excepción + detalle + qué revisar), en ES/EN/PT.
- **P3: tope artificial de 10 m/s en la velocidad de diseño crasheaba con caudal alto** — el
  `number_input` de velocidad tenía `max_value=10.0` hardcodeado (sin fundamento físico; el core
  no impone tope duro, solo una advertencia > 3 m/s). Al aplicar una calibración con óptimo
  > 10 m/s (gran escala / caudal alto, ej. 11.7 m/s) el widget lanzaba
  `StreamlitValueAboveMaxError`. Ahora el máximo se adapta al valor actual
  (`max(50.0, velocidad)`), sin tope artificial bajo; ídem el largo del colector
  (`max(20.0, largo)`). Test de regresión con velocidad óptima de 15 m/s.
- **Timestamp de solo-hora (`datetime.time`) daba error de parseo** — `pd.read_excel` devuelve
  una columna de solo hora como objetos `datetime.time`, que el parser convertía a NaT (P2 daba
  `CLIMED_TIMESTAMP_INVALIDO`, P3 `VREF_TODO_INVALIDO`). Se unificó el parser base
  (`clima_medido._parsear_timestamps`, ahora con `fecha_fija`): maneja `datetime.time` y da un
  error claro `CLIMED_TIMESTAMP_SOLO_HORA` si falta la fecha. **Se agregó la opción "el archivo
  trae solo la hora" + fecha del ensayo también a la ingesta de clima medido de P2 (fase 1a)**,
  además de P3. `ConfigMapeoClima.fecha_fija` (serializada a isoformat en el hash/snapshot).
  Tests de regresión con objetos `datetime.time`. Afectaba al `.xls` real del colector 10 m.
- **P3 calibración: "aplicar valor óptimo" no refrescaba el campo de geometría** — el
  `number_input` de velocidad/largo conservaba el valor viejo (Streamlit prioriza el
  session_state sobre `value=`). Ahora al aplicar el óptimo se **fija el valor del widget**
  vía un pendiente que se escribe al session_state al tope del render (antes de instanciar el
  widget) — patrón robusto que no depende de re-leer `value=` ni del orden de reconstrucción
  del colector; los widgets omiten `value=` cuando su key ya está en session_state (sin
  warning). Regresión con AppTest que hace clic en el botón real (velocidad 5 → 15 m/s).
- **P3 validación: `AttributeError` al abrir la sección con datos medidos** —
  `_render_validacion_colector` referenciaba `CONVENCIONES_TIMESTAMP` en el módulo equivocado
  (`calculos.clima_medido` en vez de `core.validacion`), reventando el render de P3. Corregido
  y **blindado con un smoke test de AppTest** que renderiza P3 completo (antes el render no
  tenía cobertura y esta clase de bug se colaba).
- **Modo ANUAL: humedad relativa dividida dos veces por 100** — `operacion_anual_camara`
  re-dividía la HR del día típico por 100, pero `clima_calc`/`clima_medido` ya la entregan
  como fracción [0, 1]. La ω ambiente salía ~100× baja (aire irrealmente seco) → secado
  anual optimista. Ahora la HR se trata como fracción, consistente con el pipeline
  transitorio (`balance_global`); el cálculo se aisló en el helper puro `_omega_ambiente_dia`
  con test de regresión. **Altera los resultados del modo ANUAL** respecto de versiones
  previas (ahora físicamente correctos).

## [1.0.0] — 2026-07-09

**Primera versión mayor.** Cierra la internacionalización ES/EN/PT del manual (fase F9 del
plan i18n): el manual queda **100 % traducido** a los tres idiomas — contenido, chrome del
visor, índice y navegación. Con esto se completan todos los hitos de la hoja de ruta a 1.0
(pérdida de carga en bandejas, análisis anual, modo industrial/gran escala, manual estilo
SAM e i18n completa).

### Added

- **i18n F9 — traducción del manual a EN/PT**: los 22 capítulos del manual (23 archivos,
  ~22.100 palabras por idioma) traducidos completos al inglés y al portugués (PT-BR) en
  `manual/capitulos/{en,pt}/`. Cubre Parte II (guía por secciones), Parte III (fundamentos),
  Parte IV (referencia técnica) y apéndices (código, glosario, bibliografía). Se preserva la
  sintaxis propia del manual: bloques `<!-- profundidad -->`, esquemas SVG, enlaces internos
  `?manual=slug`, anclas `{#…}`, tablas y ecuaciones KaTeX. Los glosarios se re-alfabetizan
  por idioma; las rutas de código del apéndice quedan intactas; los nombres nativos de
  productos (yacón, algarroba, charqui, yerba mate, coca) se conservan.
- **i18n F9 — índice y navegación del manual traducidos**: claves `manual.toc.<slug>.titulo/`
  `.descripcion` (23 capítulos) y `manual.parte.<idx>` (5 partes) en `ui/idiomas/{en,pt}/`
  `manual.yaml`. El índice, el sidebar, el breadcrumb y los enlaces anterior/siguiente ahora
  muestran los títulos en el idioma activo. El ES canónico sigue viviendo en la tupla
  `CAPITULOS` (resuelto por `default=cap.titulo`), por lo que estas familias existen solo en
  EN/PT; el test de paridad de claves las exime contra ES pero exige paridad EN↔PT.

### Changed

- `VERSION_SOFTWARE` → `1.0.0`.
- Los capítulos EN/PT del manual dejan de mostrar el aviso "solo disponible en español": la
  vista sirve el `.md` traducido directamente (el fallback a ES de `ruta_capitulo` sigue como
  red de seguridad para cualquier archivo que faltara).

## [0.17.0] — 2026-07-09

Internacionalización ES/EN/PT de toda la aplicación (fases F0–F8 del plan i18n):
UI de las 7 pestañas, componentes, advertencias de diseño, reporte PDF, catálogos
e infraestructura multiidioma del manual. Único pendiente hacia el 100 %: traducir
los 22 capítulos del manual (F9).

### Added

- **Internacionalización ES/EN/PT — infraestructura + piloto (fases F0–F1 del plan i18n)**:
  módulo `ui/componentes/traducciones.py` (loader puro de diccionarios YAML con fallback
  idioma→ES→clave, nunca lanza) + `ui/componentes/idiomas.py` (`t()`, `idioma_actual()`,
  selector 🌐 en sidebar con `?lang=` en la URL). Diccionarios `ui/idiomas/{es,en,pt}/`
  (sidebar + P1 completos, ~140 claves por idioma). Migrados `Secasol.py` (sidebar,
  onboarding, entorno, contacto) y `ui/p1_tipologia.py` (piloto). **Fix del bug latente
  `nav_seccion`**: la navegación guarda claves estables (`p1`..`p7`) con `format_func`, así
  la selección sobrevive al cambio de idioma. Tests `tests/test_ui/test_idiomas.py` (18:
  paridad de claves/placeholders entre idiomas, fallbacks, heurística anti-regresión de
  literales) y script de auditoría `scripts/auditar_i18n.py`.
- **i18n F2**: P2 (Emplazamiento) y P3 (Colector) migradas completas a `t()`, incluyendo
  las figuras Plotly (nombres de serie, ejes, títulos, marcas), la tabla mensual y los
  encabezados del CSV. Diccionario compartido `graficas.yaml` (meses, ejes y series
  comunes). ~370 claves nuevas por idioma.
- **i18n F3**: P4 (Cámara), P5 (Auxiliar) y P6 (Motor) migradas completas a `t()` — widgets,
  helps, métricas, spinners, warnings, selectores por enum/clave estable (tipo auxiliar,
  modo de operación, forzantes, dirección de flujo, tipo de pared, terreno z₀) y las figuras
  Plotly de la cámara (curva de secado + panel termodinámico). Se resolvieron los radios que
  guardaban el rótulo como valor (forzantes, horizonte, composición multidía) migrándolos a
  claves estables + `format_func`, para que la selección sobreviva al cambio de idioma.
  ~600 claves nuevas por idioma.
- **i18n F4**: P7 (Resultados) migrada completa a `t()` — dashboard integrado (colector,
  auxiliar, cámara, motor, chimenea, balance, ciclo), pipeline transitoria con sus 5 figuras,
  corridas paramétricas, ventana de producción, operación anual detallada, tabla de resultados
  y bloque de guardado (.txt/.json/PDF). Componentes compartidos: figura de la **carta
  psicrométrica**, panel termodinámico de cámara (`grafica_termodinamica_camara`), selector de
  espesores y fallback de esquemas — con `graficas.yaml` (namespaces `carta`/`termo`) y nuevo
  `comun.yaml`. Radio de modo de cálculo migrado a claves estables. Toda la UI de las 7
  pestañas queda traducida. Los generadores de snapshot `.txt`/`.json` y los mensajes de
  `core/`/`calculos/` quedan en ES (fases F5–F7). ~350 claves nuevas por idioma.
- **i18n F5**: advertencias de diseño por código. Widget único
  `ui/componentes/advertencias_widget.py` (`texto_advertencia` + `render_advertencias`) que
  traduce cada `Advertencia` de `core/` por su `codigo` contra
  `advertencias.<CODIGO>.mensaje/.sugerencia` interpolando `adv.contexto`, con fallback al
  texto ES de core si falta la plantilla. Nuevo `advertencias.yaml` en los 3 idiomas con los
  **43 códigos** de diseño (colector, cámara, auxiliar, motor, chimenea). Los renders inline
  de P3–P6 se unifican en el widget; se eliminan los `_ICONOS_SEVERIDAD` duplicados. Los
  mensajes de runtime de `calculos/` (P7) siguen en ES. 86 claves nuevas por idioma.
- **i18n F6**: reporte PDF (`ui/reporte.py`). `generar_reporte_pdf(..., idioma)` recibe el
  idioma activo desde P7 y lo enhebra como closure `tr` a portada, secciones (colector,
  cámara, auxiliar, motor, chimenea, resultados globales), recolectores de figuras y
  header/footer. Nuevo namespace `reporte.*` (244 claves por idioma). La tabla de advertencias
  del PDF retraduce los mensajes por código reusando `advertencias.*` (F5). Los valores
  numéricos, unidades y códigos de enum/estado quedan en v1. Fix de un bug latente de F2: la
  clave/valor `"NO"` (noroeste) del selector de orientación de P2 se coercía a booleano
  (mostraba "False") — se quotea; guard `test_yaml_sin_coercion_de_tipos` para toda la
  familia de YAML.
- **i18n F7**: catálogos de materiales y productos. Cada item de `catalogo/materiales|productos/`
  gana `descripcion_en`/`descripcion_pt` (39 items). Nuevo helper
  `ui.componentes.idiomas.t_catalogo(datos, default)` (envuelve `campo_i18n` con el idioma
  activo); los `format_func` de los selectores de material/producto de P3/P4/P6 y las etiquetas
  del producto lo usan, y el reporte PDF resuelve las descripciones de material vía
  `campo_i18n(..., tr.idioma)`. `notas`/`fuente` de los catálogos quedan en ES (v1); los
  bloques `capa_fina:` no se tocan.
- **i18n F8**: infraestructura multiidioma del manual de usuario. Los capítulos se movieron a
  `manual/capitulos/<lang>/` (ES completo; EN/PT parciales, su traducción es F9);
  `manual_contenido.ruta_capitulo(archivo, lang)` resuelve con fallback a ES y el visor muestra
  un aviso cuando cae al español. El chrome del visor se traduce vía el namespace `manual.ui.*`
  y los títulos del TOC vía `manual.toc.*` con fallback al ES de la tupla `CAPITULOS`. Todos los
  enlaces del manual propagan `&lang=` (sidebar, índice, breadcrumb, navegación, botones desde la
  vista de diseño, y los enlaces internos del markdown). Con esto el `scripts/auditar_i18n.py`
  llega a **0** literales pendientes.

---

## [0.16.0] — 2026-07-08

**Manual de usuario** (S48, integrado a la cámara radiativa en S49). Ver
`docs/bitacora/bitacora_sesion48.md`.

### Added

- **Manual de usuario estilo SAM (mejora 36)**: manual autocontenido que se abre en una
  pestaña paralela del navegador (`?manual=<slug>`), sin perder la sesión de diseño.
  22 capítulos markdown en `manual/capitulos/` organizados en 4 partes + apéndices:
  guía operativa por sección (P1–P7), fundamentos transversales (radiación y plano
  orientado, psicrometría, física del secado, convenciones de unidades/ángulos),
  referencia técnica completa por subsistema (adaptada del material del seminario
  INENCO, con ecuaciones KaTeX), mapa de implementación en código, glosario y
  bibliografía. Dos niveles de lectura por capítulo (idea general + bloques
  desplegables "🔬 En profundidad"), enlaces cruzados entre conceptos, esquemas SVG
  y navegación por índice/anterior/siguiente. Botón "📖 Manual" en cada sección y
  enlace global en el sidebar. Infraestructura: TOC declarativo
  (`ui/componentes/manual_contenido.py`), parser puro testeable
  (`ui/componentes/manual_render.py`), vista stateless (`ui/manual.py`) interceptada
  en `Secasol.py` antes de inicializar el proyecto. 148 tests de integridad de
  contenido (`tests/test_ui/test_manual.py`). Incluye un capítulo de fundamentos
  "El catálogo de productos" (los 19 productos, humedades típicas, estado de
  calibración GAB y rol vestigial de las cinéticas de capa fina).
- Sidebar del manual: enlace **"⬅ Volver al diseñador"** (navega en la misma pestaña a la
  vista de diseño; el proyecto de la pestaña original no se toca).

### Changed

- Capítulos del manual actualizados a la **cámara radiativa orientada** (0.15.0): `13_camara`
  gana "Orientación y techo a un agua" y "Superficies translúcidas"; `32_tec_camara` documenta
  el reparto producto/aire ($I_{eq,prod}$, $Q_{rad,aire}$, factores de intercepción) y el
  término nuevo del balance del aire; menciones ajustadas en tipología, emplazamiento,
  resultados, psicrometría, glosario y apéndice de código.

---

## [0.15.0] — 2026-07-06

**Cámara radiativa orientada** (S47): cambio de paradigma para la tipología CAJA — la cámara
pasa a operar como colector propio, con orientación y techo a un agua independientes del banco
de colectores. Habilita también orientar la cámara distinto del colector en ARMARIO/GRAN_ESCALA.
Ver `docs/notas/plan_camara_radiativa_orientada.md` y `docs/bitacora/bitacora_sesion47.md`.

### Added

- **Orientación propia de la cámara y techo a un agua**: `GeometriaCamara.acimut_camara_deg`
  (convención Duffie), `pendiente_techo_deg` + `cara_caida_techo`, independiente de la
  orientación del banco de colectores.
- **Superficies translúcidas por cara** (`ConstruccionCamara.caras_translucidas`): además del
  techo, ahora se puede vidriar frente/atrás/laterales (mismo material y espesor para todas).
  Cada cara activa capta radiación según su propia inclinación y acimut (transposición
  Liu-Jordan vía pvlib, `calculos/radiacion_camara.py`).
- **Reparto de radiación producto/aire**: la radiación transmitida por cada cara translúcida se
  reparte entre lo que intercepta directamente el producto (factor de intercepción `f_i` — techo:
  `A_rad/A_techo_geom`; paredes: silueta del lecho apilado) y lo que calientan las superficies
  internas opacas (nuevo término `Q_rad_aire` en el balance de `T_flujo`, con
  `ConstruccionCamara.absortancia_interior`, default 0.85). Modela el efecto invernadero de una
  caja con paredes vidriadas.
- P4: sección "Orientación y techo a un agua" (pendiente, acimut, cara de caída) y "Superficies
  translúcidas" (5 toggles + vista previa de área/inclinación/orientación por cara) en Geometría
  de la cámara, disponibles en todas las tipologías.
- P2: en tipología CAJA, el expander "Orientación del colector" se reemplaza por una nota que
  apunta a P4 (no hay colector externo cuya orientación configurar).
- Barridos paramétricos: `pendiente_techo_camara` y `acimut_camara` (Transitorio/Anual, las 3
  tipologías); `BarridoConfig.forzantes_builder` reconstruye las forzantes por punto en modo
  Transitorio cuando el parámetro barrido solo afecta el armado de forzantes (no un campo que
  lea el motor directamente).

### Changed

- **Cambio numérico deliberado en CAJA/techo-translúcido**: la fracción de radiación del techo
  que antes "se perdía" (no interceptaba la bandeja superior y no se contabilizaba en ningún
  lado) ahora calienta el aire vía `Q_rad_aire`. Proyectos CAJA existentes con techo translúcido
  darán **más ganancia térmica** que antes — es una corrección física (radiación real que la caja
  efectivamente capta), no un bug. La irradiancia equivalente al producto (`I_g_W_m2` en
  `ForzantesAire`) sigue siendo bit-idéntica a GHI en la configuración histórica (techo-solo,
  techo plano).
- `calculos/clima_calc.calcular_POA_horizonte` acepta `tilt_deg`/`acimut_duffie_deg` opcionales
  (antes tomaba siempre la orientación del colector desde `Emplazamiento`).

### Compatibilidad de archivos guardados

Snapshots `.json`/`.txt` anteriores a 0.15.0 cargan sin error: los campos nuevos (orientación,
caras translúcidas) toman sus defaults históricos (techo horizontal, solo techo translúcido).
Los resultados de proyectos CAJA con techo translúcido existentes **cambian** al recalcular
(ver "Changed" arriba) — es la corrección física esperada, no una regresión.

### Verificación

Suite: 1042 → **1073 tests** (31 nuevos), sin regresiones. `black`/`ruff` limpios. UI verificada
en vivo con `streamlit.testing.v1.AppTest` (CAJA/ARMARIO, sin excepciones).

---

## [0.14.1] — 2026-06-26

Correcciones de **infraestructura de despliegue** (no de física ni de lógica de cálculo)
detectadas al probar la app en producción tras el seminario. Ver `docs/bitacora/bitacora_sesion46.md`.

### Fixed

- **Discrepancia local ↔ Hugging Face en resultados de cámara**: un mismo prediseño daba agua
  evaporada muy distinta entre el repo local y el Space (0.26 vs 4.77 kg; producto a 92 °C sin
  secar en el remoto), con código, clima e inputs idénticos. Causa: `requirements.txt` con
  rangos `>=` dejaba que cada rebuild de HF instalara versiones de librería distintas a las del
  entorno local; el solver de cámara convergía a una solución basura. Se **pinnea** todo el stack
  con `==` (numpy/scipy/pandas/pvlib/streamlit/plotly/pyarrow/pyyaml/reportlab/kaleido) a las
  versiones del entorno de referencia. Confirmado en producción.
- **Carga de `.json` en Hugging Face fallaba con `AxiosError: 403`**: la protección XSRF de
  Streamlit, tras el reverse-proxy de HF, rechazaba la subida del `file_uploader`. Se agregó
  `--server.enableXsrfProtection=false` al `ENTRYPOINT` del Dockerfile del Space (lado HF; el
  deploy desde GitHub preserva ese Dockerfile, por lo que el cambio persiste). No es un cambio
  del repo, pero queda documentado.

### Added

- **Panel "🔧 Entorno"** en el sidebar (`Secasol.py`): muestra la versión de Python y de las
  librerías de cálculo que corre la instancia, para diagnosticar de un vistazo discrepancias
  entre el repo local y el despliegue remoto.

---

## [0.14.0] — 2026-06-16

Tanda de mejoras de UX/física a partir del modo industrial (mejoras 25–35 de
`docs/notas/mejoras.md`; sesiones S41–S44).

### Added

- **Espesores de mercado** (mejoras 25 y 26): nuevo helper `ui/componentes/espesores.py`
  (`selector_espesor_mm`) que ofrece medidas estándar de mercado en lugar de un campo numérico
  libre. Maderas (`pino`/`contrachapado_fenolico`) en pulgadas + mm (1/4"…2") en P3 (fondo) y P4
  (paredes); policarbonato alveolar en 4/6/8/10/16 mm en P3 (cubierta). Ambos con escape
  "Otro (personalizado)…".
- **k efectivo del policarbonato según espesor** (mejora 26): mapa `k_efectivo_por_espesor_mm` en
  `cubiertas.yaml` (4→0.05 … 16→0.08 W/m·K) y nuevo campo `ColectorUnidad.k_cubierta_efectivo_W_mK`
  (override opcional, default None) consumido por los motores de colector. Elegir un espesor de
  mercado fija el k efectivo correspondiente sin mutar el catálogo global.
- **Carta psicrométrica del proceso** (mejora 27): nueva carta del proceso completo del secador
  (Ambiente → Salida colector → Entrada cámara → Salida cámara) en P7 (modos Constantes,
  Transitorio y Ventana) y en el reporte PDF. Sin dependencia externa: se construye sobre
  `calculos/psicrometria.py` (parametrizado por `P_Pa` → corrección por altitud). Nuevos
  `calculos/carta_psicrometrica.py` (puro) + `ui/componentes/carta_psicrometrica.py` (Plotly).
  Adiabático (cámara indirecta) vs no adiabático (cámara directa) emerge del balance; valor
  representativo = mediodía solar (POA máx).
- **Espesor del techo translúcido con pérdida conductiva al balance** (mejora 33): nuevo campo
  `ConstruccionCamara.cubierta_translucida_espesor_m` + selector de espesor en P4 (espejo de P3,
  medidas de mercado del alveolar). El techo translúcido ya no solo aporta `Q_rad`: su conducción
  `U_techo = k_efectivo/espesor` (en serie con films interior/McAdams) entra al balance térmico de
  cámara, descontando la cara del techo de la envolvente opaca para no doble-contar
  (`camara_calc` + `camara_termodinamica.resolver_estado_camara`/`simular_secado`/`simular_cascada`).
- **Ventana de producción para CAJA/ARMARIO como multidía real** (mejora 35): el modo
  `ModoAnalisis.VENTANA` deja de ser exclusivo de gran escala. Para CAJA/ARMARIO se comporta como un
  multidía real sobre el lapso `[ventana_inicio, ventana_fin]` con clima horario; P7 enruta el
  pipeline de producción (`_render_ventana`) solo en GRAN_ESCALA y el resto cae al transitorio normal,
  con forzantes construidas por `_construir_forzantes_ventana` (P4).
- **Resultados de colector sobre la ventana en P3** (mejora 34): `_evaluar_ventana` ahora resuelve día
  y noche (sin sol, T_salida ≈ T_amb), expone la serie de T del absorbedor, el perfil T(x) a mediodía
  solar del primer día y las marcas de POA máx + mediodía solar por día; render en dos tabs.

### Changed

- **Gráfica climática de la ventana de producción** (mejora 30): las figuras de P2 ahora cubren el
  dominio temporal completo de la ventana (1 semana, 1 mes, …) en vez de encimar todos los días sobre
  un "día imaginario de 24 h". Helper `_eje_x_temporal` que auto-detecta multi-día y usa eje datetime;
  el día de diseño (DIARIO) conserva las etiquetas de hora.
- **Modelo hidrodinámico de pérdidas de carga** (mejora 29, auditoría con ASHRAE cap. 3/21):
  - ΔP del **producto en cross-flow** ahora usa un modelo combinado general (`_delta_P_producto_crossflow`):
    fricción de pared rugosa (Colebrook con ε = tamaño del producto) + obstrucción por bloqueo
    `C_obs(β)`. Reemplaza la tabla heurística `_K_rugosidad_default`.
  - **Fricción unificada en Colebrook/Haaland** en todo el circuito (se retiró el Blasius del canal
    horizontal de cámara); rugosidad de galvanizado ε≈0.15 mm (ASHRAE Tabla 1).
  - **Pérdidas singulares ampliadas** (taxonomía ASHRAE cap. 21): se agregó el difusor de entrada a
    cámara (`estimar_delta_P_singulares` ahora devuelve `'difusor'`) y se documentó el manifold
    banco→caño como confluencia (Junction).
  - El campo `Camara.bandejas.K_rugosidad_producto` pasa a ser override del coeficiente de obstrucción.
- **Orden de evaluación en la pestaña colectores** (mejora 31): "Evaluación del desempeño del colector
  unitario" aparece antes que "Evaluación del campo de colectores" (gateada a GRAN_ESCALA), reflejando
  el flujo correcto colector → banco.

### Fixed

- **Persistencia de la ventana/año al navegar** (mejora 28): en modo industrial, navegar P1↔P2 varias
  veces ya no pierde la referencia de la ventana de producción ni revierte el año de descarga al
  default 2022. Re-touch curado de widget-keys en `Secasol.py` (antes del dispatch) + sembrado robusto
  del año desde P1 (`_resolver_anio_descarga`).
- **Tope de espesor de fondo de colector** (mejora 25): el espesor de fondo en P3 estaba limitado a
  5 mm, imposible para tableros de madera (3/4" = 19 mm). Ahora hasta 100 mm en madera.
- **Sobreconteo del ΔP de cámara horizontal** (mejora 29): los canales entre bandejas están en
  paralelo, así que el ΔP del sistema es el de un canal (antes se multiplicaba por `n_canales` y
  `n_bandejas`). En túnel con carros, la obstrucción ahora se acumula en serie × n_carros (antes se
  tomaban todas las bandejas como paralelas, subestimando la pérdida por producto industrial).
- **Compensación de presiones del caño maestro** (mejora 32): el preview `estimar_delta_P_cano_maestro`
  metía el caudal total por toda la sección creciente, invirtiendo la compensación al activar el toggle.
  Ahora usa el modelo de flujo acumulado `Q(f)=Q_total·f` con sección local (coincide con la eval de
  campo); `ResultadoCampoColectores` expone `dP_troncal_Pa` + `v_troncal_perfil_ms` y P3 muestra el
  perfil de velocidad del troncal. Física unificada en todos los consumidores (incl. sizing del
  ventilador en P6).

---

## [0.13.0] — 2026-06-10

**Modo secador industrial / gran escala (`Tipologia.GRAN_ESCALA`)** — último hito hacia v1.0.
Hasta ahora `GRAN_ESCALA` era cosmético (idéntico a `ARMARIO`). Se implementó por completo,
con dos subtipos de igual jerarquía: **Batch** (lotes) y **Semicontinuo** (túnel a
contracorriente, estilo ADITAL). Suite: 942 tests.

### Added

- **Ventana de producción** (`ModoAnalisis.VENTANA`): el período de análisis pasa a ser un lapso
  `[inicio, fin]` libre con presets (1 semana / 1 mes / campaña), simulado con clima real horario.
  Subsume el binario DIARIO/ANUAL (que se mantiene para tipologías chicas). Configurable en **P1**.
- **Motor de cámara multi-etapa** (`camara_termodinamica.simular_cascada`): el túnel semicontinuo
  es una cascada de N zonas a contracorriente con avance de columnas por cadencia fija; la sequedad
  de salida es emergente. Batch = caso N=1. Reusa intacto el núcleo físico (evaporación difusiva +
  GAB + coeficientes variables en t de S39). Punto de entrada `camara_calc.calcular_camara_cascada`.
- **Orquestador de ventana** (`simulacion_ventana.simular_ventana` + `balance_global.calcular_todo_ventana`):
  arma forzantes horarias desde clima real (colector hora a hora + caño maestro + auxiliar) y acumula
  producción sobre el lapso. Métrica: kg seco + tasa de régimen (kg/día) + leña consumida.
- **Caño maestro** (`core.colector.CanoMaestro` + `calculos/cano_maestro_calc.py`): manifold de
  sección creciente que colecta el aire de las ramas; modelos de ΔP (fricción Haaland + accesorios),
  ΔT térmica (pérdida convectiva + aporte solar) y uniformidad de distribución. Configurable en **P3**.
- **Híbrido con calendario de arranque** (`core.auxiliar.CargaArranque` + `auxiliar.cargas_arranque`):
  el quemador opera en ventanas horarias de mañana/atardecer (independiente de la irradiancia) en vez
  de potencia constante; acumula leña consumida. Configurable en **P5**. Aplica a todos los modos
  transitorios.
- **UI completa**: P1 (subtipo + ventana), P3 (caño maestro), P4 (topología del túnel: n_zonas +
  cadencia), P5 (calendario de arranque), P6 (ΔP del sistema incluye el caño maestro), P7 (dashboard
  de producción sobre la ventana: producto seco, tasa de régimen, leña + perfil espacial del túnel).
  Serialización JSON + `.txt` con back-compat en todas.
- **Validación de campo** (`validacion/validacion_adital.py`): la cadena térmica del modo industrial
  se contrasta contra las mediciones del secador ADITAL (tesis doctoral, San Carlos, marzo 2009).
  4/4 checks térmicos OK (salida colector 55/78 °C, caño maestro ΔT −2.8 °C, cámara 57 °C) y campaña
  de 5000 kg en ~5 días, todos dentro de los rangos medidos en campo.

---

## [0.12.0] — 2026-06-09

Coeficientes de transporte de cámara variables en el tiempo + limpieza de los inputs de operación
(T_op/HR_op) que eran residuo del motor de capa fina. Suite: 875 tests.

### Changed

- **`h_conv` y `K_m` interiores de la cámara dejan de congelarse** (antes "opción ii" §24.10). El
  motor termodinámico (`camara_termodinamica.simular_secado`) acepta un `coef_transporte_func`
  opcional que recalcula los coeficientes **por paso** desde el estado real del aire
  (`T_ent(t)`, `T_prod(t)`, `ω_ent(t)`, `ṁ(t)`); el closure se arma en
  `camara_calc._calcular_termodinamico` (placa plana + Chilton-Colburn, película en
  `(T_ent+T_prod)/2`). Reevaluar desde cantidades conocidas no rompe la linealidad del sistema
  algebraico por paso. Back-compat: sin el callable se usan los escalares congelados. **Efecto:** en
  los modos Sintético/Día real/Anual los valores de T_op/HR_op ya **no influyen** en el resultado
  (la cámara queda gobernada por el clima/colector y los coeficientes variables); solo son
  condición de borde en modo Constantes.
- **UX P4/P7:** los sliders de "operación de cámara" se renombraron a **aire de entrada** (condición
  de borde) y se eliminó el texto "HR → X_eq vía GAB" (residuo de capa fina). Se aclara que la T y
  la HR **dentro** de la cámara son salida dinámica del motor. Además, en P4 los sliders T_op/HR_op
  se **ocultan** en modo **Día real** (con datos reales disponibles), reemplazados por una nota — no
  intervienen en ese modo (si "Día real" cae a "Sintético" por falta de datos, se siguen mostrando).
  Para leer el modo sin lag, el radio de forzantes pasó a usar `key="cam_forz_sel"`.

### Added

- Tests del callable de coeficientes en `tests/test_calculos/test_camara_termodinamica.py`
  (consistencia con el caso congelado, los coeficientes mandan en el secado, evaluación por paso
  con `ṁ(t)` variable).

---

## [0.11.0] — 2026-06-08

Eliminación del motor de capa fina: la cámara de secado pasa a tener un **único** motor físico (termodinámico, balance acoplado calor-masa). Suite: 872 tests.

### Removed

- **Motor de cámara "capa fina"** (correlaciones empíricas MR(t) de Lewis/Page/Henderson-Pabis/Midilli/Logarítmico). Diagnóstico (ver `docs/bitacora/bitacora_sesion38.md`): era un evaluador de punto único a temperatura pico, insensible al espesor de lecho y a la velocidad de aire reales (el k está calibrado a un espesor y velocidad de laboratorio), no entregaba temperaturas ni flujos, y no existía en los pipelines transitorio/multidía/anual — produciendo tiempos de secado irreales. El motor termodinámico, físicamente completo e independiente, lo reemplaza. Se eliminaron `calcular_tiempo_secado_estatico`, `evaluar_MR`, `calcular_X_eq_gab`, `_interpolar_params_cf` y la dataclass `ResultadosCamara` de `calculos/camara_calc.py`, el selector de motor en P4, y las ramas de capa fina en P7. Tests del motor borrados/migrados.

### Changed

- **`calcular_camara` despacha siempre al motor termodinámico**. El campo `Camara.modo_calculo` queda **vestigial**: `Camara.__post_init__` coacciona el legacy `"capa_fina"` → `"termodinamico"`, de modo que los snapshots `.json` antiguos cargan sin error. Los campos `modelo_capa_fina`/`modelo_isoterma` y los bloques `capa_fina:` de los catálogos se conservan como dato (no los consume el cálculo).
- **`balance_global.resumen_camara`** se simplifica a la única firma de resultado (`ResultadoMotorTermodinamico`).

---

## [0.10.0] — 2026-06-04

Tanda de mejoras UX/UI (backlog `docs/notas/mejoras.md`, ítems 20–24): navegación lateral persistente, subsecciones colapsadas al inicio, consistencia de materiales en cámara, y descarga de imágenes y datos por gráfico. Suite: 919 tests + 2 xfailed.

### Added

- **Descarga de imágenes Plotly con la vista del usuario** (S37, mejora 23). Helper `ui/componentes/graficas.mostrar_plotly` que centraliza el render con la modebar **siempre visible** y descarga **PNG ×2**; al correr en el navegador, captura el zoom/pan/ejes que el usuario dejó (no la figura original). Aplicado a los 22 gráficos de P2/P3/P4/P7.
- **Descarga de los datos numéricos por gráfico (CSV)** (S37, mejora 24). Bajo cada gráfico, botón "⬇ Datos (CSV)" con la serie detrás del gráfico, extraída server-side de `fig.data` (`_fig_a_dataframe`: formato ancho si comparten x, lado a lado si difieren). +4 tests.

### Changed

- **Navegación por secciones movida a una cinta lateral persistente** (S37, mejora 20). `Secasol.py` reemplaza `st.tabs` por un `st.radio` en el sidebar (fijo al scrollear) con dispatch que renderiza solo la sección activa (más rápido y aislado; el estado vive en `session_state.proyecto`). Fix asociado en `ui/componentes/header.py`: se dejó de ocultar todo el `stToolbar` (que escondía el botón nativo de reapertura del sidebar); ahora se oculta solo `stToolbarActions` + `stDecoration`.
- **Subsecciones de P1–P6 colapsadas al iniciar** (S37, mejora 21). Los 18 `st.expander` de subsección arrancan con `expanded=False` (vista compacta; P7 sin colapsar, `st.subheader` sin convertir).
- **Materiales de la cámara con nombres y unidades amigables** (S37, mejora 22). Los selectores de material de P4 (techo translúcido + pared simple/compuesta) muestran la `descripcion` del catálogo (no la key interna) y los espesores pasan de m a mm, alineando P4 con P3. Solo presentación; sin cambios en el modelo.

### Fixed

- **Extractor de datos de gráficos robusto** (S37). `_fig_a_dataframe` (mejora 24) crasheaba en la figura anual de colector (trazas con el mismo `x` pero perfiles `y` de distinto largo por el paso adaptativo del solver). Ahora alinea cada `y` a la longitud del `x` compartido y envuelve la extracción en `try/except` para que un fallo de exportación nunca rompa el render del gráfico.

---

## [0.9.0] — 2026-06-03

Tres mejoras del modelo físico del colector y la cámara: albedo del suelo seleccionable (componente solar reflejada en la POA), coeficiente convectivo interno calculado localmente nodo a nodo, y modo multi-día con días reales consecutivos. Suite: 914 tests + 2 xfailed.

### Added

- **Albedo del suelo seleccionable → POA** (S36, 2026-06-03). Nuevo campo `Emplazamiento.albedo_suelo` (default 0.25) con desplegable de superficies usuales en P3 (`calculos/catalogo_albedos.py`: cemento, suelo desnudo, pasto, arena, urbano, nieve — valores de `pvlib.albedo.SURFACE_ALBEDOS` — + "Personalizado"). Reemplaza el albedo fijo 0.25 que usaba `calcular_POA_horizonte`; alimenta la componente reflejada `GHI·ρ·(1−cos β)/2`, relevante para colectores inclinados/verticales. Se propaga a todos los consumidores de POA (P3, P4, P7, operación anual, transitorio) por el único choke point. Snapshot JSON/TXT y reporte PDF incluyen el valor. +9 tests.
- **Coeficiente convectivo interno LOCAL** (S36, 2026-06-03). `h_int` se calcula **nodo a nodo** (antes un escalar único) con propiedades del aire dependientes de `T_f(x)` (`calculos/propiedades_aire.py`: `k(T), μ(T), Pr(T), cp(T), ρ(T,P)`), Nusselt de entrada térmica local, blending continuo de régimen (Re=2300/10000) y convección mixta de Churchill para baja velocidad/vertical (`nusselt_forzado_local`, `nusselt_natural_canal`, `nusselt_mixto_local`). Aplica a los 4 tipos de colector vía el helper `colector_calc.coef_conveccion_interna_local`. El caudal másico se fija con `ρ(T_entrada)`. En colectores largos a bajo caudal (laminar) el realce de entrada — antes descartado por el ruteo `L/Dh≥50` — eleva `h` ~2×. +17 tests.
- **Modo multi-día: "días reales consecutivos"** (S36, 2026-06-03). En el motor termodinámico de cámara con horizonte Multi-día y forzantes "Día real", P4 ofrece un selector "Repetir día típico" (actual) vs "Días reales consecutivos" (N días calendario del clima NASA desde el día de diseño, con variabilidad real día a día). Nuevo helper puro `clima_calc.slice_n_dias_consecutivos` (recorta N días y trunca en el borde de año avisando). En ARMARIO corre el colector hora a hora sobre el horizonte real (reusa `p3_colector._evaluar_diario`). El consumidor `calcular_todo_transitorio` no cambia (ya procesa horizontes no periódicos). +3 tests.

### Changed

- **`ui/p2_emplazamiento.py` reconstruye `Emplazamiento` con `dataclasses.replace`** (S36) en vez de enumerar los campos a mano. El patrón anterior reseteaba silenciosamente cualquier campo no listado en cada rerun (bug que mataba la persistencia del albedo); `replace` preserva todos los campos no modificados y elimina la clase de bug para futuros campos.
- **Caudal másico del colector con densidad a la temperatura de entrada** (S36, antes `RHO_AIRE_REF` constante a 323 K).

### Fixed

- **Persistencia del albedo del suelo entre reruns** (S36): ver el cambio de `dataclasses.replace` en P2.

### Docs

- **Validación HWB con propiedades variables** (S36). `validacion/validacion_hwb.py` adopta piso de linealidad `R²≥0.99` (el observado baja de 1.0000 a ≈0.999 por la curvatura física de propiedades variables) + chequeo de monotonía de η + rangos de `F_R·(τα)` y `F_R·U_L`. La corrección física se valida por parámetros, no por R². CLAUDE.md y `docs/mapa_conexiones.md` actualizados.

---

## [0.8.0] — 2026-06-01

Corridas paramétricas en P7, refactor de conversiones de ángulo a la capa de cálculo, e integración del proyecto con Obsidian. Migración de deploy a Hugging Face Spaces y motor termodinámico de cámara como default. Suite: 885 tests + 2 xfailed.

### Added

- **Corridas paramétricas (barridos) en P7** (S35, 2026-06-01). El usuario varía un único parámetro curado, corre N simulaciones y compara hasta 3 corridas con gráficas superpuestas por KPI. Disponible en los 3 modos (Constantes, Transitorio, Anual). Resultados efímeros (solo `session_state`, no se persisten al JSON). Nuevos módulos: `calculos/catalogo_parametros_barrido.py` (~15 parámetros con metadata, filtros por tipología y modo), `calculos/barrido_parametrico.py` (motor `correr_barrido` con captura de error por punto — un punto inválido deja hueco sin abortar), `calculos/catalogo_kpis_barrido.py` (6 KPIs fijos + 14 avanzados opt-in, extractores tolerantes a los 3 modos). UI en `ui/p7_resultados.py`. +52 tests.

### Changed

- **Conversiones de acimut movidas a `calculos/conversiones_angulo.py`** (S35, 2026-06-01). Las 4 funciones `acimut_*` (Duffie ↔ UI360 ↔ pvlib) eran matemática pura que vivía en `ui/componentes/unidades.py`; ahora la fuente de verdad es `calculos/` (consumible por la capa de cálculo, que no puede importar de `ui/`). `unidades.py` las re-exporta por compatibilidad. `clima_calc.py` ya no tiene su copia privada. Cambia una invariante documentada: las conversiones de unidades **físicas** (°C↔K, kPa↔Pa, %↔fracción) siguen en `unidades.py`; las de **ángulos** son matemática pura en `calculos/`.

- **`resumen_camara()` como fuente de verdad única** del resumen de cámara (S35). Abstrae las firmas divergentes de `ResultadoMotorTermodinamico` y `ResultadosCamara` en un dict (`t_secado_s`, `masa_agua_kg`, `status`, `convergio`). `balance_global._extraer_t_y_masa` y `ui/p7_resultados._resumen_camara` ahora delegan en él (antes duplicaban la lógica).

- **Default de `Camara.modo_calculo` cambiado a `"termodinamico"`** (S34, 2026-05-29). Hasta la S33 el default era `"capa_fina"` "para preservar comportamiento histórico"; ahora es el motor termodinámico (balance acoplado calor-masa con `solve_ivp`, único soportado por la operación anual). Snapshots `.json` antiguos sin el campo cargan con el nuevo default; los que tienen el campo explícito lo respetan.

- **`st.components.v1.html` → `st.iframe`** en `ui/componentes/esquemas.py`. La API anterior está deprecada y se elimina después del 2026-06-01. `st.iframe` (Streamlit ≥1.57) acepta HTML crudo como `src` y mantiene el aislamiento del CSS de Streamlit que necesitamos para que el tema oscuro no repinte los textos de los SVG.

- **Esquema de tipo de colector en P3 reorganizado**: se ocultó la vista isométrica `colector_tipo1.svg` (no aportaba contenido nuevo) y la sección transversal comparativa de los 4 tipos se movió a un `st.expander` colapsado por defecto, siguiendo el patrón de P1 (circuito de aire) y P4 (esquema de cámara). El SVG queda en `assets/esquemas/` por si se quiere reactivar.

### Docs

- **Integración con Obsidian** (S35, 2026-06-01). Script `scripts/generar_notas_obsidian.py` (solo stdlib, no toca código, idempotente) genera una nota por módulo en `docs/modulos/`. Nuevos documentos de navegación `docs/arquitectura.md`, `docs/tareas.md`, `docs/decisiones.md`, `docs/obsidian-integracion-proyecto.md`. Bloques "Ver también (Obsidian)" con enlaces `[[...]]` al pie de `README.md`, `CLAUDE.md` y `CHANGELOG.md`. `.obsidian/` agregado a `.gitignore`.

### Infrastructure

- **Migración de deploy a Hugging Face Spaces** (S33, 2026-05-23). Repo de GitHub cambiado a privado. La app ahora corre en `https://huggingface.co/spaces/gonzalojduran/Secasol26` vía Docker + template Streamlit. Deploy automático en cada push a `main` mediante GitHub Action (`.github/workflows/deploy_hf.yml`) que sincroniza el código al Space y dispara rebuild. Git LFS configurado en el Space para fonts `.ttf` y logos `.png`. Caché de NASA POWER excluido del deploy — se regenera en runtime.

---

## [0.7.0] — 2026-05-20

Primer release post-prototipo. Cierre físico del modelo de colector solar y del lazo natural por chimenea. Validación contra Hottel-Whillier-Bliss (R²=1.0000). Suite: 774 tests + 2 xfailed.

### Added

- **Chimenea solar** como componente top-level del proyecto.
  - Modelo físico de tiro térmico, fricción y pérdidas singulares (`calculos/chimenea_calc.py`).
  - UI propia en P6 (accesible cuando el motor está apagado — convección natural).
  - Lazo natural acoplado completamente: en modo Constantes y en modo Transitorio el caudal se resuelve por iteración Picard hasta convergencia, re-corriendo el colector con la velocidad efectiva impuesta por el caudal natural.
  - Visualización completa en P7 (ambos modos): métricas instantáneas, series horarias, balance del lazo, advertencia automática si el caudal natural difiere más del 30% del caudal manual configurado en P4.

- **Doble cubierta** para colectores: parámetro `n_cubiertas` (1 o 2) con espaciado configurable. El modelo agrega resistencia serie cubierta–cavidad–cubierta usando Hollands (convección natural inclinada) + radiación entre superficies grises paralelas. Aplica a los 4 tipos de colector. Ganancia típica de eficiencia: +5 a +8 pp.

- **POA (Plane of Array)** computada hora a hora desde DNI/GHI/DHI del clima NASA POWER, propagada como variable de primera clase en las forzantes (`ForzantesAire.I_g_POA_W_m2`). Garantiza que el solver del colector reciba la irradiancia sobre el plano inclinado del absorbedor, no la horizontal del piranómetro.

- **Persistencia por pestaña**: cada una de P3/P4/P5/P6 tiene botones "Guardar configuración (.txt)" y "Guardar configuración (.json)" con snapshot reconstruible. P7 guarda el prediseño completo con todos los inputs, propiedades del catálogo, advertencias estáticas y resultados de simulación si fueron corridos.

- **Carga de configuración guardada (.json)** en P3/P4/P5/P6: file_uploader al inicio de cada pestaña que reconstruye los dataclasses desde el JSON, valida la sección y actualiza la UI.

- **Reporte PDF integral** en P7 (`ui/reporte.py`): header institucional GEEDSP/INENCO con logos, secciones tabuladas para cada pestaña, gráficas reconstruidas desde la sesión, advertencias activas. Tipografía DejaVu Sans incrustada para soporte completo de Unicode.

- **Validación física del modelo de colector** contra Hottel-Whillier-Bliss (HWB) y modelo de Klein para los 4 tipos (`validacion/validacion_hwb.py`, `validacion/validacion_klein.py`). Linealidad perfecta de η vs (T_med − T_amb)/I con R² = 1.0000.

### Changed

- **Entry point renombrado**: el script principal pasa de `app.py` a `Secasol.py`. Ejecutar con `streamlit run Secasol.py`.

- **Chimenea solar** migrada de subcomponente de Colector a componente top-level (`Proyecto.chimenea`). Esto permite chimenea también en tipología CAJA (donde no hay colector externo). Los snapshots `.json` antiguos que traen la chimenea bajo `colector.chimenea` la restauran automáticamente en `proyecto.chimenea`.

- **Sugerido automático de irradiancia** en P7 modo Constantes: ahora calcula POA representativa con `pvlib` sobre el año de clima cargado y toma el quantile 90 (antes salía del quantile 90 de GHI con label engañoso "POA").

- **Adaptación a deprecación de Streamlit**: reemplazo global de `use_container_width=True` por `width="stretch"` (deprecación programada para 2025-12-31).

- **Limpieza de dependencias**: se quita `matplotlib` de `requirements.txt`. La migración a Plotly para gráficas interactivas ocurrió durante el ciclo S23-S29; ningún módulo del proyecto importa matplotlib hoy, y ninguna otra dependencia lo requiere. Instalaciones nuevas pesan ~30 MB menos.

### Fixed

- **Corrección crítica de signos** en el residual algebraico del solver de colector (F1 en los 4 tipos y F3 en Tipo 1). El bug producía raíces espurias con la cara externa de la cubierta a temperaturas físicamente imposibles (≈ −200 °C) y residuos numéricos cero, enmascarando el problema. Impacto al corregir: la eficiencia térmica η baja aproximadamente 25 puntos porcentuales en air heaters (los valores anteriores estaban sobreestimados). Validación HWB con R² = 1.0000 confirma el nuevo modelo.

- **Coherencia local del balance térmico** en colectores Tipos 2/3/4: agregado el término convectivo de la cara interna del fondo (`conv_ci_int = h·ΔT·W_abs`) que faltaba en el balance, restaurando coherencia con la EDO del fluido del canal inferior. Impacto: Δη ≈ −10 a −12 pp en Tipos 2 y 3 (Tipo 4 sin cambio significativo).

- **POA correcta en el solver del colector** en todos los caminos del pipeline (P3 horario/diario, P3 constantes, P7 constantes, P7 transitorio con clima real). Antes, el pipeline transitorio le pasaba GHI etiquetada como POA al solver, lo que subestimaba la T de salida del colector y, en cadena, el tiro térmico y el caudal natural. Para latitudes intermedias (ej. Salta, lat −24.79°) y tilt típico (25–30°) el efecto puede ser de hasta 25–30% en invierno.

### Removed

- **Sección de chimenea de P3**: la UI de chimenea ya no aparece en la pestaña del Colector. Su lugar es P6 (Motor), accesible cuando se desactiva el motor eléctrico.

### Incompatibilidad de archivos guardados

> **Importante para quien tenga snapshots `.json` o `.txt` anteriores a 0.7.0:**
>
> Los archivos cargan sin error, pero las corridas nuevas darán **números distintos** a los originales, por las correcciones físicas y el lazo natural acoplado. Concretamente:
>
> - Las eficiencias η de los colectores serán menores (típicamente −25 pp por el fix de signos F1/F3, y −10/−12 pp adicionales en Tipos 2/3 por el fix F4).
> - El caudal natural por chimenea será distinto al single-pass anterior (típicamente menor cuando antes estaba sobreestimado por correr el colector con velocidad de diseño en lugar de la velocidad efectiva del lazo).
> - La T de salida del colector en pipeline transitorio cambia porque ahora se calcula con POA real, no con GHI.
>
> Los valores anteriores no eran "correctos en otro sentido": eran simplemente erróneos por bugs físicos que se mantuvieron sin detectar. Los resultados post-0.7.0 son los físicamente válidos.

---

## [0.1.0]

Estado de prototipo. 7 pestañas operativas (Tipología/Configuración, Emplazamiento/Clima, Colector, Cámara, Auxiliar, Motor, Resultados). Motor termodinámico de cámara con pared 3 nodos, forzantes horarias multi-día (sintéticas o reales NASA POWER), política anti-rehumectación, eventos de humedad objetivo y temperatura máxima del producto. Tipología CAJA con cubierta translúcida y radiación directa al producto. Capa fina con dependencia de temperatura. 4 tipos de colector de placa plana. Pared compuesta multi-capa de cámara. Pipeline P7 transitoria. UI Plotly. 717 tests + 2 xfailed.

---

## Ver también (Obsidian)

- [[README]] — descripción de producto.
- [[docs/tareas]] — backlog y estado actual.
