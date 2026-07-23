# Bitácora — Sesión 58 (2026-07-23)

Tres bloques: liberar el bloque anual como 1.2.0, cerrar el pendiente que S57 había
dejado primero en la lista —**no arrancar lotes con mal pronóstico**— y un fix de
coherencia de caudales salido de una corrida real del usuario.

Suite: **1652 passed + 1 skip** (desde 1604). Ruff y black limpios.

## 1. Release 1.2.0 (`52ccf7f`, `e76a963`)

El bloque completo de S57 estaba en el working tree sin commitear. Se commiteó en dos
pasos: la feature (`52ccf7f`) y el release (`e76a963`), con el contenido de
`[Unreleased]` movido a `## [1.2.0] — 2026-07-23` y `core/version.py` en 1.2.0 —
`tests/test_core/test_version.py` ata las dos fuentes.

Al mover el bloque quedó `[Unreleased]` con la hoja de ruta sola, renombrada a
"Mejoras post-1.2", con los dos pendientes nuevos de S57 sumados.

`.gitignore` gana `reporte_*.pdf`: el PDF de la corrida real del usuario había quedado
untrackeado dentro de `tests/`. Es un artefacto de la app, no fuente.

Pusheado a `origin/main` → deploy a HF disparado.

## 2. La decisión de cargar

### El problema

El encadenado cargaba un lote **cada vez que el secador quedaba libre**. Si ese día venía
nublado, el lote arrancaba igual: se arrastraba sin terminar, ocupaba la cámara y sumaba
al conteo de lotes frustrados. Ningún operador hace eso — mira el cielo antes de llenar
el secador. El conteo de frustrados quedaba inflado con casos que no ocurren.

### Las dos decisiones de modelado

Ambas las tomó el usuario, y ambas cambian qué significa el número que sale:

**Ventana de decisión: un día.** Se integra la POA del día en que se cargaría; si no
llega al umbral, se espera al siguiente. Es la decisión que se toma mirando el cielo a la
mañana. La alternativa —mirar los N días que dura el lote— es más fiel a un lote de
varios días, pero pedía estimar esa duración antes de simularlo.

**Pronóstico perfecto.** La decisión usa la irradiación que el día **efectivamente va a
tener**, no una predicción con error. Es una idealización deliberada: da la cota superior
de la buena decisión. La alternativa evaluada fue el pronóstico de persistencia (decidir
con lo que se vio ayer), que es el baseline meteorológico estándar y se equivoca cuando
el tiempo cambia. Queda anotada como posible refinamiento.

El sesgo del pronóstico perfecto va **en sentido opuesto** al de la espera de recarga de
S57 (que baja la producción), y los dos son chicos frente a la variabilidad interanual
del recurso.

### La implementación

`PoliticaRecarga` —que ya era el objeto "cuándo se carga"— se extiende al "si conviene
cargar": `exigir_pronostico` (default on) + `umbral_pronostico_MJ_m2` (default 8.0). El
umbral es el mismo con el que ya se contaban los **días operables**, así que las dos
cantidades son directamente comparables.

`_energia_diaria_POA` reduce el array de POA a MJ/m² por **día local** una sola vez por
corrida (no depende del lote). El agrupamiento es local y no UTC por la misma razón que
la desagregación mensual: la jornada del operador es local.

Detalles que importan:

- **La decisión mira el día, no el instante.** A las 8 de la mañana el sol siempre es
  flojo; decidir con la irradiancia instantánea del momento de cargar rechazaría todos
  los días.
- **Sin POA no se decide a ciegas.** Si las forzantes no traen irradiación en el plano
  del colector, el dict sale vacío, el criterio no se aplica y se avisa con
  `VENTANA_PRONOSTICO_SIN_POA`. Un dict vacío significa "no se puede decidir", no "día
  malo".
- **"No se dio la orden de cargar" ≠ "el secador no seca".** Si ningún día del lapso
  supera el umbral no sale el `VENTANA_BATCH_SIN_LOTES` genérico sino
  `VENTANA_PRONOSTICO_BLOQUEA_TODO`, que dice cuántos días se evaluaron y contra qué
  umbral. El diagnóstico y la corrección son distintos.

### Efecto medido

Sobre 60 días sintéticos con 35 % de días nublados:

```
sin criterio (S57)   lotes=8  seco=144.0 kg  saltados=0
umbral 8 MJ/m²       lotes=7  seco=126.0 kg  saltados=4
umbral 15 MJ/m²      lotes=7  seco=126.0 kg  saltados=4
```

Solo 4 de los 21 días nublados se saltean, y es correcto: el criterio se evalúa **cuando
el secador está libre**, y la mayor parte del tiempo está ocupado con un lote en curso.
Que 8 y 15 MJ/m² den lo mismo confirma que la nubosidad sintética separa limpio los dos
grupos de días.

Sobre este fixture el efecto en lotes frustrados no se ve (los lotes duran ~7 días, así
que un día malo al inicio no es decisivo): se vería en un secador de lotes cortos. El
efecto principal acá es sobre la producción, −12 %.

### La métrica

`dias_salteados_pronostico` se lee **junto a** `dias_operables`, y esa es su razón de
ser: separa "no había sol" (recurso) de "había sol pero el secador estaba ocupado"
(operación). Expuesta en P4, en el detalle de P7 y en los tres exports.

## 3. Tres notas que decían algo falso

Las leyendas de "cota superior" de P4, P7 y el reporte PDF seguían afirmando que el
modelo "recarga un lote apenas termina el anterior, sin turnos ni tiempo de carga, y
arranca lotes aunque el clima venga malo".

La primera mitad dejó de ser cierta en **1.2.0** (`PoliticaRecarga`) y la segunda en esta
sesión. Reescritas en los tres idiomas para decir cuál es la idealización que **queda**:
el pronóstico perfecto. Una nota de supuestos que no se actualiza con el modelo es peor
que no tenerla — el lector la usa para calibrar cuánto creerle al número.

## 4. El caudal de cámara no seguía al del colector

Salido de una corrida del usuario: armario en Salta, colector tipo 2 de 2.5 m a 2 m/s. El
banco entrega **0.055 kg/s** y la cámara arrancaba en **0.030** —el default de fábrica de
`ConfiguracionFlujo`—, con la única señal de una advertencia **al final** del cálculo
anual, cuando el año ya había corrido.

El sistema es hermético: lo que sale del banco entra a la cámara. Que el default no lo
respetara convertía un dato derivable en una trampa: el usuario que no lo corregía a mano
corría el año entero con los dos caudales desacoplados.

**Lo que no había que hacer** era forzar la igualdad. El propio usuario planteó el caso
legítimo: colector sobredimensionado, aire demasiado caliente a la salida, y la estrategia
de mezclar aire ambiente para bajarlo — ahí el caudal de cámara es **mayor** que el del
banco a propósito. Así que el caudal sigue al colector **por defecto**, con un checkbox
para desacoplarlo y un aviso en el momento de desacoplarlo, no al final.

Tres detalles:

- **La misma función en los dos lados.** `balance_global.caudal_masico_banco_kg_s` es
  nueva, es la inversa exacta de `_velocidad_modulo_desde_caudal` (misma sección, misma
  densidad) y la usan tanto P4 para proponer el caudal como la advertencia para
  evaluarlo. Si P4 hubiera propuesto con ρ≈1.1 —como hacía el hint— y la advertencia
  evaluara con ρ(T_amb, P_sitio), el usuario habría aceptado la propuesta y la corrida le
  habría avisado igual que sus caudales son incoherentes. Hay un test para eso.
- **No pisar una decisión.** El checkbox arranca activado si el caudal guardado es el
  default de fábrica o ya coincide con el banco; si el proyecto trae un valor propio
  (snapshot cargado, dilución deliberada), arranca desactivado.
- **El tope del widget** dejó de ser 10 kg/s fijo: un banco grande mueve más que eso y el
  tope habría recortado el caudal del propio colector. Misma lección que la velocidad
  máxima de P3 en S54.

## 5. El reporte que se contradecía a sí mismo

Segunda corrida del usuario (armario, Salta, modo anual, con auxiliar eléctrico de
2000 W y calendario de arranque 5–8 y 19–22). Preguntó si la gráfica de producción de P7
tomaba el auxiliar o era una réplica de lo de P4 — y si no estaríamos parchando tanto que
las excepciones se vuelven regla.

**Los dos bloques del mismo PDF se contradecían:**

| bloque | E_auxiliar | fracción solar |
|---|---|---|
| `resultados_globales` (P7 recalcula) | 74.34 MJ | 0.769 |
| `operacion_anual` (replay de P4) | 0.00 MJ | 1.000 |

**El cálculo estaba bien.** Reproduje su configuración exacta contra
`armar_forzantes_ventana`: `E_aux = 424.8 MJ`, `fracción solar = 0.858`, η_drying ≠
η_total. El auxiliar entra al anual por un solo lugar y funciona.

**Lo que fallaba era la vigencia.** P7 no recalcula el anual: reproduce el objeto que P4
dejó en `session_state["p4_resultado_anual"]`, y ese objeto no se invalidaba **nunca**.
El usuario corrió el año y después configuró P5; el bloque global vio el auxiliar y el
anual quedó congelado en un mundo sin auxiliar.

El dato que le da la razón en la sospecha de fondo: `core/advertencias.py` tiene
`BloqueResultados` con hash SHA-256 y `verificar_vigencia()` —el mecanismo de
invalidación, construido desde el principio— y **no lo usaba nadie**. Cero call-sites
fuera de `core/`. Se diseñó para exactamente este problema y se dejó de lado cada vez que
había que sacar una feature.

Ahora `simulacion_anual.hash_entradas_anual` huellea colector, cámara, auxiliar,
emplazamiento, política y una firma barata del clima (largo, extremos del índice y sumas
de GHI y T_amb, en vez de serializar el DataFrame). `ui/componentes/vigencia.py` es el
único lugar que conoce la convención de claves, para que P4, P7 y el reporte no la
repliquen. Si no coincide: panel en rojo, botón para recalcular ahí mismo, y el bloque
anual **no entra** a los exports.

**Elección deliberada:** detectar y avisar, no recalcular solo. P7 es una vista; que
dispare 5 s de cómputo por entrar a la pestaña sería peor que el problema.

### Las otras dos cosas de la misma corrida

**Dos secciones de paramétricas.** No era diseño: en modo ANUAL el panel anual se montó
arriba del flujo de transitorio/constantes sin cortarlo, y ambos llamaban a
`_render_barridos_parametricos`. Ahora hay una sola, la del modo que se corre.

**Faltaban gráficas.** Había una (kg/mes + lotes) con datos ya calculados sin usar. Van
tres más: energía mensual solar vs auxiliar —la que responde "¿cuánto trabaja el
auxiliar y cuándo?"—, duración media de lote por mes con p50/p90 del año como referencia,
y días operables vs días del mes. Para la primera hubo que desagregar el auxiliar por mes
(`PuntoMensualAnual.E_auxiliar_MJ`): existía solo como total del año.

Detalle al agregarlo: el total anual pasó a recomponerse de los meses. El solver del
auxiliar integra con regla trapezoidal y el anual por rectángulos hora a hora (igual que
la solar); la diferencia era ~1.4 %, chica, pero un resumen que no es la suma de su
propia tabla es una contradicción más.

### Auditoría del render de P7

`p4_forzantes_horizonte` / `p4_horizonte_meta` tienen **la misma clase de problema**: P4
los persiste y solo se borran al pasar a modo Constantes, nunca al cambiar la
configuración. El impacto es menor porque P7 sí recorre la cámara y el auxiliar encima de
esas forzantes, pero si se cambia el colector en P3 después de armar el horizonte, P7
sigue usando el aire viejo. Queda anotado como pendiente: el mecanismo de huella ya está,
falta aplicarlo.

## 6. Guardar sin poder cargar

El usuario preguntó dónde estaba el botón de cargar proyecto completo. No estaba, y el
hueco era más grande de lo que parecía:

- P7 exporta `prediseno_completo.json`, pero **nada lo lee**.
- Los cargadores existentes son por sección (P3 colector, P4 cámara, P5 auxiliar, P6
  motor/chimenea). **Meta, configuración y emplazamiento no se cargaban en ningún lado**:
  aunque reconstruyeras todo pieza por pieza, tipología, modo, lat/lon/altitud y zona
  horaria había que tipearlos de nuevo.
- El archivo completo no servía **ni para cargar de a partes**: `parsear_json_seccion`
  valida el `seccion` de la raíz, que dice `"prediseno_completo"`, así que P4 lo
  rechazaba. Los sub-dicts internos sí traen su propio `seccion`, pero no había nada que
  los repartiera.

O sea: la exportación creció por sección y el "guardar todo" se agregó después, sin el
camino de vuelta. Misma forma que el resto de lo que apareció esta sesión.

`ui/componentes/carga_proyecto.py` es plomería pura: no reimplementa ninguna
reconstrucción, reparte cada sub-dict al deserializador que ya existía. Dos decisiones:

- **Una sección que falla no aborta la carga.** Si un id de catálogo cambió de nombre,
  esa sección se omite con un aviso y el resto entra. Recuperar el 90 % de un proyecto es
  mejor que rechazar el archivo entero.
- **El clima no viaja** (8760 filas harían un archivo enorme). Se avisa con qué año se
  guardó; como la caché parquet es por (lat, lon, año), rebajarlo en P2 es instantáneo.

El botón va en P1, a pedido del usuario: cargar ahí deja las siete pestañas servidas.

**Lo que destapó el round-trip:** `z0_terreno_m` no estaba en el exportador del
emplazamiento. Se agregó en S57 como propiedad del sitio y nadie lo sumó al snapshot, así
que guardar y cargar perdía el terreno elegido y lo devolvía al default de 0.05 m. El
test que lo atrapa es el fuerte de la suite nueva: **la huella de entradas del modo anual
del proyecto cargado tiene que ser idéntica a la del original**. Si un campo que entra al
cálculo se pierde en el viaje, el hash cambia y el test falla — sin tener que enumerar
campo por campo.

Probado contra el archivo real del usuario: carga sin un solo aviso.

## 7. Vigencia, generalizada (cierra el pendiente de §5)

El pendiente que §5 dejó anotado —la vigencia del horizonte transitorio— resultó ser la
punta de un patrón más amplio. Auditando el ciclo de vida de `session_state` aparecieron
**cuatro** resultados con el mismo hueco, no uno:

| resultado | lo calcula | lo consume | ¿se invalidaba? |
|---|---|---|---|
| anual | P4 | P7 + PDF | ✅ (S58 §5) |
| horizonte (`p4_forzantes_horizonte`) | P4 | P7 transitorio | ❌ solo al pasar a Constantes |
| transitorio (`p7_resultados_tr`) | P7 | dashboard + exports | ❌ **nunca** |
| constantes (`p7_resultados`) | P7 | dashboard + exports | ❌ **nunca** |
| ventana (`p7_resultado_ventana`) | P7 | dashboard + exports | ❌ **nunca** |

Los tres de P7 son el mismo bug de §5 un nivel más arriba: calculás en P7, cambiás el
auxiliar en P5, volvés sin apretar "Calcular" y el PDF sale con los números viejos.

Frente a la pregunta del usuario en §5 —"¿no estaremos parchando tanto que las excepciones
se vuelven regla?"— la respuesta fue **hacer la regla**, no un quinto parche. En vez de
copiar el chequeo del anual cuatro veces:

- **`core/huellas.py`** (puro): `huella_entradas(proyecto, secciones, extras=, con_clima=)`.
  Huellea secciones del proyecto (una ausente también cuenta —ese era el caso del auxiliar
  configurado después de calcular), el clima por una firma barata (`FirmaClima`: largo,
  extremos del índice, sumas de GHI y T_amb) y extras que no son secciones (condiciones de
  borde, política, kwargs del builder). `hash_entradas_anual` pasó a ser un envoltorio de
  tres líneas sobre esto; `_HuellaAnual` se borró.
- **`ui/componentes/vigencia.py`** ahora es un **registro**: `DERIVADOS` mapea cada
  resultado a su clave de `session_state`, las secciones que lo determinan y si el clima
  entra. `registrar` / `estado` / `invalidar` son las tres operaciones; los envoltorios del
  anual (`registrar_anual`, `resultado_anual_vigente`) siguen exportados para no tocar sus
  call-sites. Agregar un resultado derivado nuevo es **una fila** en `DERIVADOS`, no otro
  chequeo copiado.

Qué determina a cada uno, con criterio físico y no mecánico:

- **El horizonte NO depende del auxiliar.** Las forzantes son el aire *antes* del auxiliar:
  P7 le suma P5 y el motor encima al re-correr. Configurar P5 no invalida el horizonte —lo
  invalida el transitorio, que sí los incorpora. Hay un test para cada mitad.
- **Constantes no toca el clima** (`con_clima=False`): las condiciones de borde son los
  sliders de P7, que viajan como extras. Mover un slider sin recalcular ahora también marca
  el resultado como viejo.
- **Los kwargs del builder son entradas del horizonte** (`extras_horizonte`): el día de
  análisis o el tipo de forzantes cambian el aire aunque el equipo sea el mismo. Los campos
  *derivados* del meta (`n_dias` efectivo, `horizonte_tipo`) quedan afuera a propósito.

En la UI: si el horizonte quedó viejo, P7 cierra la puerta a calcular y ofrece **rehacerlo
sin volver a P4** (`_rehacer_horizonte` reusa `_construir_forzantes_builder_desde_meta`, que
ya existía para los barridos); si un resultado de P7 quedó viejo, el dashboard lo muestra
marcado y la exportación se **bloquea** (`_render_botones_guardado(vigente=...)`) — un
archivo con números viejos sale del programa y se lee después, cuando ya no queda el aviso
en pantalla.

**Detalle del hook:** ruff corre con `--fix` en el PostToolUse, así que agregar los imports
*antes* que sus usos los borra como no usados. Reponer el import después de escribir los
call-sites.

Suite: **1677 passed + 1 skip** (desde 1656). `core/huellas.py` y el registro general suman
+21 tests (`test_core/test_huellas.py`, `test_ui/test_vigencia.py`). Ruff y black limpios.

## Pendientes

- **`PoliticaRecarga` no se persiste** — ahora con dos campos más, el pendiente pesa un
  poco más: la configuración de operación completa vive en widgets y no sobrevive un
  guardar/cargar. Sigue abierto dónde guardarla. (Desde S58 al menos se comparte en
  `session_state` para que P7 pueda recalcular con la misma política.)
- **Pronóstico de persistencia** como alternativa al perfecto, para cuantificar el valor
  de tener un buen pronóstico (correr las dos y restar).
- **Modo anual del túnel semicontinuo**: rechazado con `ANUAL_SEMICONTINUO_NO_SOPORTADO`.
- `validacion/validacion_cruzada_yacon.py` sigue roto desde S38.
- `h_w` de McAdams usa el viento a 2 m sin corregir a la altura del equipo.
- **Verificación pendiente del usuario**: repetir la corrida anual de Salta en el Space
  con la presión corregida (73.10 → 89.15 kPa). Los 347 kg / 169 lotes del reporte de
  S57 van a bajar.

## Ver también

- [[docs/bitacora/bitacora_sesion57]]
- [[docs/tareas]]
- [[CHANGELOG]]
