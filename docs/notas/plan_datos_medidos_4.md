# Plan — Mejora 38, Fase 4: validación y calibración de cámara y producto

## Contexto

Las fases 1a/1b (ingesta de clima medido y motor agnóstico al paso), 2/2b (validación del
colector, aislado y forzado con el clima del propio ensayo) y 3 (calibración 1-D) cerraron el
lazo **ingesta → validación → calibración** para el **colector**. La Fase 4 lo extiende al
**segundo eslabón**: la cámara de secado y el producto.

**Decisiones de alcance (usuario, 2026-07-20):**

1. **Señales a validar (las cuatro):** curva de secado (masa o X del producto), T del aire en
   cámara, HR del aire en cámara, T del producto.
2. **Forzado: cámara aislada + overlay de P7.** Las métricas finas y la calibración corren
   sobre la **cámara aislada** forzada con el aire de entrada **medido en el propio ensayo**
   (espejo exacto de la fase 2b). Además, si P7 ya corrió, se ofrece el overlay
   medido-vs-cadena-completa como **diagnóstico visual con métricas, sin calibrar sobre él**.
3. **Túnel semicontinuo: sin tocar el motor.** Se valida contra lo que `ResultadoCascada` ya
   expone —muestras de descarga (`X_salida_por_avance`) y perfiles espaciales finales— y se
   deja documentada la deuda de agregar historia temporal por zona a `simular_cascada` (ver
   §Deuda técnica).
4. **UI: P4 para las series, P7 para el túnel.** Nodo único y batch se validan contra series
   de tiempo → sección en P4, espejo de P3. El semicontinuo se valida contra perfiles y
   descargas → junto al dashboard de ventana en P7, donde ya viven esos objetos.

## Terreno: qué expone hoy cada topología (verificado en código)

| Caso | Motor | Serie temporal disponible |
|---|---|---|
| CAJA/ARMARIO (nodo único) | `camara_termodinamica.simular_secado` | Completa: `t_array_s`, `T_prod_K`, `X_prod_kg_kg`, `T_flujo_K`, `omega_flujo_kg_kg`, `HR_flujo`, `m_dot_w_kg_s` |
| GRAN_ESCALA **batch** | `simulacion_ventana._simular_ventana_batch` | **Nada concatenado**: agregados + un punto representativo. Cada lote reinicia en t=0, X=X_inicial |
| GRAN_ESCALA **semicontinuo** | `camara_termodinamica.simular_cascada` | **Sin historia por zona**: `X_salida_por_avance`, `T_prod_salida_por_avance_K` y perfiles espaciales **finales** (`X_perfil_zonas`, `T_aire_perfil_zonas_K`, `omega_aire_perfil_zonas`) |

Consecuencia de diseño: la validación por **serie de tiempo** solo es directa sobre
`simular_secado`. Por eso la Fase 4 fuerza la **cámara aislada** con `calcular_camara`
(nodo único) aunque el proyecto sea GRAN_ESCALA batch — el ensayo de un lote *es* un nodo
único; el encadenado de lotes de la ventana es un artefacto de producción, no de física.

## Física del modelo

**Qué valida cada señal (y qué no):**

- **X(t) del producto (curva de secado)** — el observable integrador del balance de masa.
  Ajusta bien ⇒ la cadena `ṁ_w = h_m·A·(ω_sat(T_prod)·a_w(X) − ω_flujo)` es correcta *en
  conjunto*. Es la señal de mayor valor y también la más degenerada: un error en `K_m`, en
  `A_prod` efectiva y en la isoterma GAB producen curvas parecidas. Por eso la calibración
  1-D debe hacerse **con las otras señales fijas como control**, no sobre X sola.
- **T del aire en cámara (`T_flujo`)** — valida el balance de energía del nodo de aire
  (sensible del aire, pérdida por paredes `UA`, latente de la evaporación). Es sensible a
  `U_pared` y al caudal; poco sensible a la isoterma.
- **HR del aire (`HR_flujo`)** — la más informativa sobre el **acople** calor-masa: es la
  respuesta directa del agua evaporada al caudal de aire. Un buen ajuste simultáneo de
  `T_flujo` y `HR_flujo` es la evidencia más fuerte de que el CSTR es adecuado.
- **T del producto (`T_prod`)** — valida el reparto sensible/latente. En la fase de velocidad
  constante debe quedar cerca del bulbo húmedo; un simulado sistemáticamente alto delata
  evaporación subestimada (`K_m` bajo).

**Errores sistemáticos esperados (no son "error de modelo"):**

- **`ω_ent` es la fuerza motriz.** Si el ensayo no midió HR a la entrada de cámara y se asume
  la del ambiente, el sesgo entra directo en la evaporación y la calibración lo **absorbe
  dentro de `K_m`**, devolviendo un coeficiente que en realidad compensa una humedad mal
  supuesta. La UI debe advertirlo explícitamente cuando `HR_ent` no venga del archivo.
- **CSTR (nodo único bien mezclado).** El modelo supone aire uniforme en la cámara. Un
  termopar cerca de la entrada leerá más caliente que el `T_flujo` del modelo y uno cerca de
  la salida, más frío. En cámaras profundas parte del residuo es **posición del sensor**, no
  error de modelo. Recomendación: validar contra el promedio de varios sensores, o declarar la
  posición y esperar un MBE de signo consistente.
- **Base de humedad.** `X` del modelo es **base seca** (kg agua/kg seco). Las pesadas de campo
  suelen ser masa húmeda o % base húmeda. La conversión exige la **masa seca** de la muestra;
  si se declara mal, aparece como un offset en toda la curva (MBE grande con R² alto).
- **Muestra vs carga total.** La pesada es de una bandeja o muestra testigo; el modelo integra
  la carga total. Es válido comparar X (intensivo), **no** masa absoluta ni masa evaporada.
- **Producto cuasi-congelado en el paso** (semicontinuo) y **recarga instantánea** (batch) son
  idealizaciones; en ensayos con avances lentos el escalón real está suavizado.

**Túnel — euleriano vs lagrangiano.** El motor integra cada columna a lo largo de su viaje
(lagrangiano); un termopar fijo en una posición ve **columnas distintas** según la cadencia.
Para el **aire** la distinción no importa (es euleriano en ambos). Para `T_prod`/`X` medidos en
posición fija, la señal del modelo sería escalonada con saltos en cada avance, y compararla
contra una medida continua produce un RMSE dominado por el artefacto del escalón. Por eso en
esta fase el túnel se valida solo contra **descargas** (comparación lagrangiana natural: la
columna que sale) y **perfiles espaciales al cierre** (comparación euleriana natural: foto
instantánea del túnel), que son justamente los dos objetos libres de ese artefacto.

## Arquitectura

**`core/validacion.py` — generalización (hoy hardcodea T de colector):**

- `VARIABLES_REFERENCIA` pasa a `("T_salida_colector", "T_camara", "HR_camara",
  "T_producto", "X_producto", "masa_producto")`.
- `UNIDADES_REFERENCIA` por variable: temperaturas `("C","K","F")`; `HR_camara`
  `("pct","frac")`; `X_producto` `("kg_kg","pct_bs","kg_kg_bh","pct_bh")`; `masa_producto`
  `("kg","g")`.
- `ConfigReferencia` gana `masa_seca_kg: Optional[float]` — necesaria para convertir
  `masa_producto` → X base seca (`X = m/m_seco − 1`). Validación
  `VREF_CONFIG_MASA_SECA_REQUERIDA` si la variable es `masa_producto` y no se declara.

**`calculos/ingesta_referencia.py` — ingesta por variable:**

- Tablas `_CONVERSORES_SI[variable][unidad] -> Callable` y `_RANGOS_QC[variable] ->
  (min, max)`, reemplazando el `_a_kelvin` + QC de T hardcodeados. `T_salida_colector`
  conserva exactamente el comportamiento actual (back-compat de la fase 2).
- `ingerir_forzantes_camara(df_crudo, config, *, columna_T_ent, columna_HR_ent=None,
  HR_ent_fija=None, columna_caudal=None, m_dot_fijo_kg_s=None, columna_T_amb=None,
  columna_viento=None, P_Pa) -> ForzantesAire` — espejo de `ingerir_clima_forzante` de 2b, pero
  produciendo directamente el `ForzantesAire` que consume el motor de cámara: `ω_ent` vía
  `psicrometria.humedad_absoluta(HR, T, P)`, `t_s` relativo al primer registro (el motor
  integra desde t=0), `I_g` = 0 salvo que se mapee. Advertencia `VREF_HR_ENT_ASUMIDA` cuando
  la HR de entrada no viene del archivo.

**`calculos/validacion_camara.py` (nuevo, puro):** la orquestación que en el colector vivía en
la UI (`_series_simuladas_colector`) acá es pura, porque no depende de widgets:

- `simular_camara_aislada(camara, forzantes, *, T_amb_K, P_Pa, factor_K_m, factor_h_conv)` —
  wrapper sobre `camara_calc.calcular_camara(forzantes_aire=…)`.
- `serie_simulada(resultado, variable, t0_utc) -> (DatetimeIndex, np.ndarray)` — mapea la
  variable canónica al array del `ResultadoMotorTermodinamico` (`T_camara`→`T_flujo_K`,
  `HR_camara`→`HR_flujo`, `T_producto`→`T_prod_K`, `X_producto`/`masa_producto`→`X_prod_kg_kg`)
  y convierte `t_array_s` a timestamps absolutos. Es lo que habilita reusar
  `ingesta_referencia.evaluar_ajuste` sin cambios.
- `pares_descarga_tunel(res_cascada, t0_utc)` y `perfil_zonas(res_cascada, variable)` — para
  el camino del túnel en P7.

**`calculos/camara_calc.py` — dos kwargs nuevos, default neutro:** `calcular_camara(...,
factor_K_m: float = 1.0, factor_h_conv: float = 1.0)` propagados a
`_construir_params_termodinamico`, que envuelve el `coef_transporte_func` multiplicando su
salida. Con los defaults el comportamiento es **bit-idéntico** al actual (ningún test
existente cambia). Son las perillas físicamente calibrables de la cámara: el catálogo de
barrido no tiene ninguna que ataque la transferencia de masa.

**Calibración:** reusa `calculos/calibracion.py::calibrar_1d` sin cambios. Parámetros
ofrecidos: `factor_K_m` (el principal), `factor_h_conv`, más los del catálogo de barrido que
apliquen (`masa_producto`, `humedad_inicial`, geometría de cámara) vía
`barrido_parametrico.aplicar_parametro`.

**UI:**

- `ui/p4_camara.py`: sección **"🔬 Validación con datos medidos"** (espejo de P3): carga del
  archivo → hoja/encabezado/fecha fija → mapeo de la **señal** (variable + columna + unidad) →
  mapeo del **aire de entrada** (T_ent, HR_ent o HR fija, caudal) → cámara aislada → overlay +
  métricas → **"🎯 Calibración"**. Más el **overlay de la cadena completa** (solo lectura) si
  hay resultados de P7 en `session_state`.
- `ui/p7_resultados.py`: en el dashboard de ventana y **solo** con
  `SubtipoGranEscala.SEMICONTINUO`, bloque de validación del túnel: X medida en las descargas
  vs `X_salida_por_avance`, y perfil medido por posición vs perfil espacial final, con métricas.
- i18n: `p4.validacion.*`, `p7.validacion_tunel.*`, `graficas.validacion.*` y
  `advertencias.VREF_*` nuevos — **en los TRES yaml** (paridad de claves y placeholders).

## Estado: E1–E5 COMPLETAS (S55, working tree). Suite 1497 + 1 skip.

**Ancla temporal (decisión del usuario, 2026-07-20):** se agregó ``t0_utc`` a
``ForzantesAire`` —su lugar natural, así lo heredan todos los pipelines y no solo el
transitorio— más ``ResultadosCompletosTransitorio.t0_utc``. Sin ese ancla las trayectorias
del motor (que integra desde t=0) no se pueden alinear contra una serie medida. Con eso quedó
implementado el **overlay de la cadena completa** en P4 (diagnóstico, sin calibrar); si las
forzantes fueron sintéticas, ``t0_utc is None`` y la UI lo avisa en vez de dibujar un overlay
corrido.

**E5 — validación del túnel (implementada).** Bloque "🔬 Validación del túnel con datos
medidos" en el dashboard de ventana de P7, solo en subtipo SEMICONTINUO. Dos comparaciones,
las únicas libres del artefacto euleriano↔lagrangiano: (a) **descargas** por avance —se carga
un muestreo de campo fechado y se contrasta contra `X_salida_por_avance`, con las descargas
fechadas al fin de su intervalo de avance desde `t0_utc`—; (b) **perfil espacial** al cierre
—tabla editable con el valor medido por zona (vacío donde no hay sensor) contra el perfil
final de X o de T del aire—. Para habilitarlo, `ResultadoVentana` expone ahora
`X_salida_por_avance`, `T_prod_salida_por_avance_K`, `intervalo_avance_s` y `t0_utc`
(`armar_forzantes_ventana` lo toma del índice del clima); `pares_descarga_tunel` funciona
sobre ambos resultados por duck-typing.

**Qué se puede aplicar y qué no (decisión del usuario, 2026-07-20).** La calibración de
cámara distingue dos clases de parámetro, y la distinción es física, no de implementación:

- **``area_bandeja`` — área efectiva de intercambio: APLICABLE.** Es un campo real del
  proyecto y multiplica *tanto* ``h·A`` (sensible) como ``K_m·A`` (evaporación), o sea que es
  matemáticamente el mismo knob que ``factor_h_conv`` pero **interpretable y falsable**: "el
  área efectiva ajustada es 1.8× la de bandeja declarada" es una afirmación verificable para
  una capa de rodajas apiladas. Por eso tiene botón "aplicar" como en P3 (parámetro nuevo del
  catálogo de barridos + patrón pendiente de session_state para refrescar el widget).
- **``factor_K_m`` / ``factor_h_conv`` — correcciones al cierre: DIAGNÓSTICO.** No son
  propiedades de la cámara: agrupan el error de la analogía de Chilton-Colburn, los parámetros
  GAB del cultivar y —si no se midió HR de entrada— el sesgo de ``ω_ent``. Nada de eso
  transfiere a otro producto ni a otro caudal, así que persistirlos en el proyecto promovería
  un factor de corrección al estatus de parámetro de diseño. Se informan y se interpretan
  ("un factor > 1 significa que el modelo subestima el transporte"), no se guardan.

## Etapas (cada una: suite verde + black/ruff + `auditar_i18n.py`)

- **E1** — `core/validacion.py` generalizado + tablas de conversión/QC por variable en
  `ingesta_referencia`. Tests: cada variable/unidad convierte a SI, QC por rango, back-compat
  de `T_salida_colector`, `VREF_CONFIG_MASA_SECA_REQUERIDA`. ~12 tests. Riesgo bajo.
- **E2** — `ingerir_forzantes_camara` → `ForzantesAire`. Tests: ω desde HR+T, `t_s[0]==0`,
  HR asumida → advertencia, caudal fijo vs columna, huecos. ~8 tests. Riesgo medio.
- **E3** — `calculos/validacion_camara.py` + kwargs `factor_*` en `camara_calc`. Tests:
  factores 1.0 ⇒ resultado idéntico al actual; `factor_K_m>1` ⇒ seca más rápido (monotonía);
  `serie_simulada` devuelve la longitud y el timestamp correctos por variable. ~10 tests.
  Riesgo medio (toca `camara_calc`, mitigado por el default neutro).
- **E4** — UI P4: validación + calibración + overlay de cadena. i18n ×3. Helpers puros
  testeables + smoke `AppTest` (la lección del `AttributeError` de la 2b). Riesgo alto (UI).
- **E5** — UI P7: validación del túnel (descargas + perfiles). i18n ×3. Riesgo medio.
- **E6** — Cierre: CHANGELOG, `mejoras.md` §38, bitácora S55, `mapa_conexiones.md`, memoria,
  capítulo de manual si aplica, y registro de la deuda técnica de abajo.

Camino crítico: E1→E2→E3→E4. E5 es independiente de E4.

## Verificación end-to-end

1. Suite + black + ruff + `auditar_i18n.py` (=0) en cada etapa.
2. E3: señal sintética generada por el propio motor + ruido conocido ⇒ métricas esperadas y
   `calibrar_1d` recupera el `factor_K_m` inyectado (test de recuperación de parámetro).
3. E4 (app): ensayo real de cámara del usuario → overlay + métricas físicamente razonables;
   calibrar `factor_K_m` y verificar que el óptimo mejora el RMSE de X(t).
4. E5 (app): campaña ADITAL → descargas y perfil de zonas contra lo medido.

## Deuda técnica registrada (para futuras implementaciones de Secasol)

**Historia temporal por zona en `simular_cascada`.** Hoy `ResultadoCascada` guarda solo
perfiles espaciales finales y valores por avance, lo que impide el overlay temporal contra
termopares fijos del túnel. Para habilitarlo haría falta persistir arrays
`(n_zonas, n_pasos)` de `T_aire`, `T_prod`, `omega` y `X`, más el mapeo
euleriano→lagrangiano descrito en §Física (qué columna ocupa la zona *j* en el instante *t*,
señal escalonada por avance). Se decidió **no** hacerlo en la Fase 4 para no tocar el núcleo
físico ya validado contra ADITAL (7/7 checks) y para no pagar el costo de memoria por corrida.
Candidato natural a una Fase 5 con su propio plan.
