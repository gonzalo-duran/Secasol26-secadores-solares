# Bitácora — Sesión 55 (2026-07-20)

Sesión larga con tres bloques: (1) se **planificó y se implementó completa la mejora 38
fase 4** — validación y calibración de **cámara y producto** (E1–E6), la última pieza del
lazo ingesta → validación → calibración; (2) se **arreglaron y pushearon** dos bugs que el
usuario encontró probando (uno en el Space, uno en local con gran escala); (3) se explicitó
una limitación del modelo que estaba tácita (la previa de P4 en túnel semicontinuo).

Suite: **1497 passed + 1 skip** (1498 recolectados), desde 1426 al inicio de la sesión.
`origin/main` = `3f2f668`. Todo lo de la fase 4 queda en **working tree sin commitear**.

## 1. Bug del Space: `ZeroDivisionError` al cargar clima medido (commit `e8eec34`)

El usuario replicó en el Space la prueba del colector 10 m y se topó con un
`ZeroDivisionError` crudo de las tripas de pandas. **No era el entorno** —reprodujo idéntico
en local—, así que no tenía nada que ver con los pines de `requirements.txt` ni con el
Python del Dockerfile.

**Cadena causal:** mapeó como timestamp la columna `tiempo` de la hoja `medido`, que no es
una fecha sino **segundos transcurridos** (0, 300, 600…). `_parsear_timestamps` solo
reconoce números como serial de Excel dentro de [20000, 80000]; al quedar fuera, caía al
`pd.to_datetime` genérico, **que interpreta un número pelado como nanosegundos desde 1970**.
La serie quedaba con 108 timestamps del 1/1/1970 separados 300 ns → `inferir_frecuencia_s`
devolvía `3e-07 s` y **pasaba sus dos guardas** (es positivo y perfectamente regular) →
`regularizar_grilla` hacía `int(round(3e-07))` = 0 → `freq="0s"` → división por cero.

Lo grave no era el mapeo equivocado (elegir mal una columna es normal) sino que el error se
propagara en silencio por tres capas. **Fix en las tres:**

1. **Parser** — `CLIMED_TIMESTAMP_NUMERICO_AMBIGUO` cuando la columna es numérica pero no son
   seriales de Excel, con mensaje que explica que parece tiempo transcurrido. Con `fecha_fija`
   además interpreta bien un numérico en [0,1) como **hora de Excel** (0.375 = 09:00), que
   antes también se rompía.
2. **`inferir_frecuencia_s`** — el guarda `moda <= 0` pasó a `moda < 1 s`
   (`CLIMED_PASO_SUBSEGUNDO`).
3. **`regularizar_grilla`** — rechaza un paso que redondee a 0 s (`CLIMED_PASO_INVALIDO`) y
   acota el tamaño de la grilla (`CLIMED_GRILLA_EXCESIVA`) — bomba latente: 1 s sobre un año
   son 31 M de filas. Estas dos capas protegen también a P3, que reusa las mismas funciones.

**Regresión encontrada al arreglar:** `pd.to_numeric` sobre una columna de **datetimes**
devuelve epoch en nanosegundos (~1.3e18), así que el primer corte clasificaba mal las
columnas de fecha legítimas. Lo cazó el test e2e de ADITAL; se excluye explícitamente con
`pd.api.types.is_datetime64_any_dtype` + chequeo de objetos `datetime`.

**Decisión del usuario:** ampliar el catch a `Exception` en los **seis** puntos de ingesta de
archivos de P2 y P3, con la clave nueva `comun.error_inesperado` (ES/EN/PT) que muestra tipo
de excepción + detalle + qué revisar. Un traceback crudo en un Space público es peor que un
mensaje genérico.

## 2. Mejora 38 fase 4 — validación y calibración de cámara y producto

Plan completo en `docs/notas/plan_datos_medidos_4.md`. Antes de escribir código se
discutieron las alternativas en detalle (a pedido del usuario) y se cerraron cuatro
decisiones de alcance.

### 2.1. Hallazgo estructural que condicionó el diseño

Los tres pipelines de cámara **no exponen lo mismo**:

| Caso | Motor | Serie temporal |
|---|---|---|
| CAJA/ARMARIO (nodo único) | `simular_secado` | Completa |
| GRAN_ESCALA batch | `_simular_ventana_batch` | **Nada concatenado** (agregados + un punto representativo; cada lote reinicia en t=0) |
| GRAN_ESCALA semicontinuo | `simular_cascada` | **Sin historia por zona** (solo perfiles finales + valores por avance) |

Consecuencia: la validación por serie de tiempo solo es directa sobre `simular_secado`. Por
eso la fase 4 fuerza la **cámara aislada** aun en GRAN_ESCALA batch — el ensayo de un lote
*es* un nodo único; el encadenado de lotes es un artefacto de producción, no de física.

### 2.2. Decisiones de alcance (usuario)

1. **Las cuatro señales**: curva de secado (masa o X), T del aire en cámara, HR del aire, T
   del producto.
2. **Cámara aislada + overlay de P7**: métricas y calibración sobre la cámara aislada forzada
   con el aire de entrada medido del propio ensayo (espejo de la fase 2b), más overlay
   medido-vs-cadena-completa como diagnóstico visual **sin** calibrar sobre él.
3. **Túnel sin tocar el motor**: se valida contra descargas y perfiles; la historia por zona
   queda como deuda registrada.
4. **UI: P4 para las series, P7 para el túnel.**

### 2.3. Implementación (E1–E6)

- **E1** — `core/validacion.py` generalizado a **seis** variables (`T_salida_colector`,
  `T_camara`, `HR_camara`, `T_producto`, `X_producto`, `masa_producto`) con unidades por
  magnitud y `ConfigReferencia.masa_seca_kg`. `ingesta_referencia` con conversión y QC **por
  variable**: base húmeda → base seca (`X_bs = X_bh/(1−X_bh)`, con `X_bh ≥ 1` inválido),
  pesada → X (`X = m/m_seco − 1`), HR a fracción con clip benigno 1 < HR ≤ 1.02 → 1.
  Back-compat exacta de `T_salida_colector`. +17 tests.
- **E2** — `ingerir_forzantes_camara`: arma el `ForzantesAire` desde el propio ensayo (ω vía
  `psicrometria.humedad_absoluta`, caudal volumétrico → másico **de aire seco** descontando
  vapor) y **deja una advertencia por cada supuesto**: `VREF_HR_ENT_ASUMIDA`,
  `VREF_T_AMB_ASUMIDA`, `VREF_VIENTO_ASUMIDO`, `VREF_CAUDAL_ASUMIDO`. +9 tests.
- **E3** — `calculos/validacion_camara.py` (269 líneas, **puro**): `simular_camara_aislada`,
  `serie_simulada` (reancla `t_array_s` a timestamps absolutos), `pares_descarga_tunel`,
  `perfil_zonas`, `evaluar_camara`. En el colector esta orquestación vivía en la UI; acá es
  pura y la reusan P4 y P7. Más `factor_h_conv`/`factor_K_m` en `camara_calc` (default 1.0 →
  **bit-idéntico**, con test que lo verifica). +19 tests, incluido uno de **recuperación de
  parámetro**: `calibrar_1d` recupera el `factor_K_m` inyectado en una señal sintética.
- **E4** — UI en P4: "🔬 Validación con datos medidos" + "🎯 Calibración" + "🔗 Diagnóstico
  de la cadena completa". Se extrajeron los helpers de gráfica a
  `ui/componentes/validacion_widget.py` y **se portó P3 a usarlos** (sin duplicar). i18n ×3.
  4 smoke tests de AppTest.
- **E5** — UI en P7 (solo semicontinuo): "🔬 Validación del túnel", con **descargas** por
  avance (comparación lagrangiana, fechadas desde `t0_utc`) y **perfil espacial** al cierre
  (tabla editable por zona, comparación euleriana). `ResultadoVentana` pasa a exponer
  `X_salida_por_avance`, `T_prod_salida_por_avance_K`, `intervalo_avance_s` y `t0_utc`.
  `pares_descarga_tunel` sirve para ambos resultados por duck-typing. +7 tests.
- **E6** — CHANGELOG, plan, `mejoras.md` §38 y memoria.

### 2.4. Decisión de diseño: qué se puede "aplicar" y qué no

El usuario preguntó por qué la calibración de cámara no tenía botón "aplicar" como la de
colector. La objeción inicial ("`factor_K_m` no es un campo del proyecto") estaba mal
planteada; la discusión produjo una salida mejor:

- **`area_bandeja` (área efectiva de intercambio) — APLICABLE.** Multiplica *tanto* `h·A`
  como `K_m·A`, o sea que es **matemáticamente el mismo knob** que `factor_h_conv`, pero es un
  campo real del proyecto y su valor es **interpretable y falsable**: "el área efectiva
  ajustada es 1.8× la de bandeja" es verificable para una capa de rodajas apiladas. Se agregó
  como parámetro del catálogo de barridos (18 en total) y tiene botón "aplicar" con el patrón
  pendiente de session_state de P3.
- **`factor_K_m` / `factor_h_conv` — DIAGNÓSTICO.** Agrupan el error de la analogía de
  Chilton-Colburn, los parámetros GAB del cultivar y —si no se midió HR de entrada— el sesgo
  de `ω_ent`. Nada de eso transfiere a otro producto ni caudal, así que persistirlos
  promovería un factor de corrección al estatus de parámetro de diseño. Se informan con su
  lectura física, no se guardan.

### 2.5. `ForzantesAire.t0_utc`

El overlay de cadena completa quedó bloqueado al principio porque
`ResultadosCompletosTransitorio` **no tenía ancla temporal absoluta**: el motor integra desde
t=0 y sin fecha no hay forma de alinear contra una serie medida (un overlay corrido es peor
que no tenerlo). Por decisión del usuario se agregó `t0_utc` — **a `ForzantesAire`**, que es
su lugar natural: así lo heredan todos los pipelines, no solo el transitorio. Lo llenan los
tres constructores de P4 desde el índice del clima y `armar_forzantes_ventana` desde el lapso;
lo propagan `ResultadosCompletosTransitorio` y `ResultadoVentana`. Queda `None` con forzantes
sintéticas, y la UI lo avisa.

## 3. Bug de gran escala + ventana en P4 (reportado con capturas)

Con preset ADITAL semicontinuo emplazado en Salta y ventana de 7 días: P2 y P3 evaluaban bien
la ventana, pero al llegar a P4 aparecía *"Día real no disponible: P3 sin calcular (ejecutá
'Calcular desempeño del colector' en modo diario)"* y la previa caía a **día sintético**,
perdiendo el lapso y el clima real.

**Causa:** el flag de P4 era `usar_ventana = ... VENTANA and not es_gran_escala`. La exclusión
era deliberada ("el túnel tiene su pipeline propio en P7"), pero al excluirse de la rama de
ventana, P4 caía a la rama "día real / sintético", **que exige `p3_eval["modo"] == "diario"`**
— condición que en VENTANA nunca se cumple porque P3 evalúa sobre la ventana. En S44 se hizo
que VENTANA funcionara como multidía real **para CAJA/ARMARIO** y esa misma línea dejó afuera
a gran escala.

**Fix:** `usar_ventana` ya no excluye gran escala. `_construir_forzantes_ventana` **ya era
agnóstico a la tipología** (solo distingue CAJA para `T_sal_col = T_amb`), así que no hubo que
tocar la maquinaria, solo dejar de bloquearla. P7 sigue siendo la fuente de verdad. De paso,
en modo ventana los sliders de borde T_op/HR_op se ocultan (el aire sale del clima y del
colector). Ruff cazó dos cruces de variables (`datos_slice` vs `datos_dia`) al enganchar el
ancla en los distintos constructores. +3 tests (`TestVentanaEnGranEscala`).

## 4. La previa de P4 en semicontinuo no avisaba que resuelve un solo nodo

El usuario preguntó por qué P4 resuelve con nodo único y si el usuario final estaba al tanto.
No lo estaba: el mensaje del subtipo describía la topología del túnel pero no decía que los
números de la previa **no** son los del túnel.

**Por qué es de un nodo:** además de la convención del proyecto (las pestañas intermedias son
vistas previas, P7 es la fuente de verdad), hay una razón dura — el gráfico de P4 dibuja X(t),
T_prod(t), T_flujo(t), ṁ_w(t) y `ResultadoCascada` **no expone series temporales**, solo
perfiles finales y valores por avance. Literalmente no hay qué graficar desde una cascada.

**Fix:** aviso explícito **solo en SEMICONTINUO** (en batch la previa sí es fiel:
`_simular_ventana_batch` encadena ese mismo `calcular_camara` lote a lote), en **dos lugares**
—antes del botón y sobre los resultados, que es donde se leen los números—, aclarando que es
de un nodo, que no reproduce la variación longitudinal ni la sequedad emergente, y que el
comportamiento completo se evalúa en P7. ES/EN/PT + test que verifica que el aviso aparece.

## Pendiente para la próxima sesión

1. **Probar la fase 4 en Streamlit con un ensayo real de cámara** — es lo único que ningún
   test cubre, y en la fase 2 fue justamente probándolo que salieron los bugs importantes.
2. **Decidir el commit** de todo el working tree (22 modificados + 5 nuevos, ~2577 líneas).
   Conviene separarlo en al menos tres commits: la fase 4, los dos fixes de bugs (afectan a lo
   que ya está en producción) y el `t0_utc` (infraestructura transversal).
3. Verificación manual e2e de las **corridas paramétricas** en P7 (etapa 12, pendiente vieja).
4. Sigue la inconsistencia **viento 2 m (contrato del clima) vs 10 m** (`chimenea_calc`).

## Notas

- **Deuda técnica registrada (candidata a fase 5):** historia temporal por zona en
  `simular_cascada` — arrays `(n_zonas, n_pasos)` de `T_aire`, `T_prod`, `omega`, `X` más el
  mapeo euleriano→lagrangiano. Habilitaría el overlay contra termopares fijos del túnel **y**
  una vista previa real de N zonas en P4. No se hizo en la fase 4 para no tocar el núcleo ya
  validado contra ADITAL (7/7) ni pagar el costo de memoria por corrida.
- **Gotcha físico a vigilar en las pruebas:** si el ensayo no midió HR a la entrada de cámara,
  el error de `ω_ent` lo **absorbe `K_m`** durante la calibración y el factor "calibrado"
  compensa una humedad supuesta, no un defecto del modelo. La UI lo advierte, pero conviene
  tenerlo presente al interpretar resultados.
- **Gotcha de tests:** `AppTest.from_function` serializa **solo** el cuerpo de la función —los
  helpers module-level no viajan— y `at.session_state` **no expone `.get()`** (hay que usar
  subíndice). Ambos costaron un rato.
- **Gotcha de CHANGELOG:** al insertar la entrada de la fase 4 se creó un `### Changed` en
  medio del bloque *Added*, dejando huérfanas las entradas de las fases 3 y 2b. Ya corregido;
  conviene revisar la estructura de secciones después de insertar entradas largas.
- Ruff reporta **34 errores preexistentes** en `chimenea_calc`, `correlaciones_nusselt`,
  `p5_auxiliar` y varios tests — verificado con `git stash` que no son de esta sesión.
- Recordatorio Obsidian: si está abierto, el autosave puede pisar los `.md` editados desde
  afuera ([[feedback-obsidian-vscode]]).
