# Bitácora — Sesión 57 (2026-07-22)

Sesión larga, con cuatro bloques encadenados: cierre de pendientes chicos, un fix de
física del viento, la reescritura completa del **modo anual sobre 8760 h**, y los
arreglos salidos de la primera corrida real del usuario sobre ese modo.

Suite: **1604 passed + 1 skip** (desde 1525). Ruff y black limpios.

## 1. Pendientes chicos (commiteados)

- `b047dd5` — **versión de Secasol en el panel 🔧 Entorno**. Sale de
  `core/version.py::__version__`, no del `CHANGELOG.md` ni de los tags: la whitelist del
  deploy no los copia al Space, así que leerlos en runtime andaría en local y fallaría
  justo en producción. `tests/test_core/test_version.py` ata la constante al último
  encabezado liberado.
- `41d70b8` — **limpieza de ruff, 47 → 0**. 30 con `--fix`; los 17 restantes a mano
  porque `F841`/`E402` pueden tapar bugs reales. Ninguno lo era: los `E402` eran imports
  bajo un banner de sección (no hacks de `sys.path`) y los `F841`, restos de refactor.

## 2. Altura de referencia del viento y z₀ (`3b10dcf`)

**Fix.** `chimenea_calc` asumía viento a 10 m pero recibía el de 2 m del contrato
`Clima.WS_ms`. Subestimaba la velocidad en el tope por `ln(2/z₀)/ln(10/z₀) ≈ 0.70` y el
término motriz del extractor —que va con v²— **a la mitad**. Caudal natural con
extractor: **+14 a +35 %** según viento y T_chim.

**Fuente única.** La fórmula del perfil logarítmico estaba duplicada en `clima_medido` y
`chimenea_calc`, cada una con su z₀ → extraída a `calculos/perfil_viento.py`. Y z₀ pasó
a ser propiedad del **sitio** (`Emplazamiento.z0_terreno_m`, catálogo Davenport-Wieringa,
widget en P2 junto al albedo). Antes el mismo terreno físico podía entrar al modelo con
dos valores: la ingesta lo hardcodeaba en 0.05 mientras P6 ofrecía un selector — hasta
**23 % de error** en `v` con anemómetro a 10 m sobre terreno rugoso.

## 3. Split del hook de paridad i18n (`c5cc8be`)

El hook corría los 22 tests de i18n tras **cada** YAML editado, y como la paridad compara
los tres idiomas, fallaba por construcción mientras se editaba de a uno: 14 avisos en una
sesión, de los cuales solo 4 decían algo.

El eje de la partición no es importancia sino **decidibilidad**: qué puede ser cierto
después de editar *un* archivo. Los 4 tests cross-idioma llevan `@pytest.mark.i18n_paridad`
y corren en un hook de `Stop` (fin de turno); el resto sigue en `PostToolUse`. Los 14
avisos habrían sido 4.

## 4. Modo anual sobre 8760 h — el bloque grande

Plan completo en `docs/notas/plan_anual_8760.md`.

### La auditoría que lo disparó

El modo anual corría el TD sobre el **día típico** de cada mes. Nueve problemas
verificados, cuatro de fondo:

1. `kg_secados_anual` era **agua evaporada** rotulada como producto seco (factor 2-4× de
   sobrelectura). El help de P4 lo agravaba: "kg de producto fresco secados".
2. **η_térmica ≡ η_colector**, siempre, por cancelación algebraica: `Q_aire` se *define*
   como `η_col·POA·A_col` y `η_térmica = Q_aire/(POA·A_col)`. Mostraba 0.5 los 12 meses
   para cualquier diseño. Comprobado numéricamente.
3. **η_drying ≡ η_total**, por `E_aux` hardcodeado en 0.
4. El **colector real no entraba**: η fijo en 0.5. Cambiar tipo o cubiertas en P3 no
   movía el anual salvo por el área.

De las cuatro eficiencias de Augustus Leon, solo dos llevaban información y una estaba
duplicada.

### El pipeline

`simulacion_ventana._simular_ventana_batch` **ya** encadenaba lotes sobre clima real y ya
calculaba producto seco de verdad, validado contra ADITAL. Correr el anual como una
ventana de 365 días resolvió cinco de los nueve problemas sin escribir física nueva.

### El costo, y la superficie de respuesta (E1)

El pipeline escala lineal a ~26 ms/h → 3.8 min para 8760 h, de los cuales **95 % es el
colector** (solver estacionario una vez por hora).

La salida vino de la física: en los pipelines forzados `T_entrada = T_amb`, lo que anula
el término de pérdidas de Hottel-Whillier-Bliss y deja la respuesta **casi afín en POA**
sobre un espacio de solo 3 dimensiones. `calculos/superficie_colector.py` muestrea el
solver en una grilla adaptada al clima (~180 solves) e interpola:

```
3.76 min → 4.68 s (48×)
acuerdo sobre serie anual real: medio 0.003 K | máx 0.033 K
```

Para dimensionarlo: el modelo de colector validado contra el prototipo de 10 m del INENCO
da RMSE 0.9 °C contra medición real. El error de interpolación es un orden por debajo.
Y de paso resuelve el problema 4: la superficie se construye con el colector **real**.

### Motor, métricas y UI (E2–E4)

- `LoteVentana`: historia por lote (carga, descarga, duración, masas, completo). Sin eso
  no se podía atribuir producción a un mes.
- `simular_encadenado_lotes`: entrada pública que no lee `subtipo_gran_escala` — el
  encadenado no es del secador industrial, es de cualquier secador batch.
- `calculos/simulacion_anual.py`: orquesta y desagrega. **Convención**: un lote se cuenta
  en el mes en que se **descarga** (hora local del sitio); la energía solar se integra
  por mes calendario, porque es un flujo y no un evento.
- Métricas nuevas: producto seco y agua evaporada **separados**, lotes completos vs
  frustrados, dispersión p50/p90, días operables (que resucita el campo huérfano),
  energía específica [MJ/kg], fracción solar —que compara energías **útiles**, no
  irradiancia incidente contra auxiliar—, y `aprovechamiento_aire`, deliberadamente **no**
  llamado η_pickup porque no es comparable con esa literatura.
- P4 pierde el slider `batches_por_mes`; P7 gana tabla mensual con **descarga CSV**.

### Limpieza (E5)

Eliminados `calculos/operacion_anual_camara.py`, `OperacionAnualConfig` y
`Camara.operacion_anual`. Los barridos en modo anual usaban el módulo viejo: migrados.

**Hallazgo**: al migrar el test del barrido anual apareció que el fixture armaba el clima
con **HR en porcentaje**, violando el contrato. El motor viejo lo enmascaraba —atrapaba el
fallo mes a mes y devolvía ceros con advertencias— así que **el test daba verde con los 12
meses fallando en silencio**. Misma clase de bug que el HR/100 de S52.

## 5. La corrida real del usuario, y lo que destapó

Armario con manzana, Salta, techo translúcido. Tres cosas:

**(a) Crash en altura.** `PSICRO_PV_EXCEDE_P` con `HR=1.000, T=92.8 °C, P=73.2 kPa`. El
sitio estaba a ~2650 m (altitud mal cargada) donde el agua hierve a **91.1 °C**: por
encima, la saturación no está definida. Reventaba `aprovechamiento_aire`, métrica que yo
había agregado. Arreglado en dos niveles: la métrica excluye esas horas, y el bloque de
métricas va envuelto — **ninguna derivada puede tirar abajo una corrida de un año**.

**(b) La cámara tenía el mismo límite.** `omega_saturacion(T_prod)` sin guarda. Decisión
del usuario: **recortar y avisar fuerte**. `_omega_saturacion_acotada` topea la presión de
vapor al 90 % de la total, y `CAM_TD_SOBRE_EBULLICION` dice explícitamente que los
resultados de esas horas **no son confiables** — el modelo describe evaporación difusiva,
no hervor. El tope es arbitrario y está documentado como tal.

**(c) Aluvión de advertencias.** La deduplicación comparaba strings exactos, pero los
mensajes llevan el número de horas del lote ("durante 5.6 h") → no filtraba nada: 52 lotes
daban ~100 avisos. Ahora se agrupan por **código**, con el conteo de lotes que lo
dispararon. En una prueba: 30 avisos → 2. No es cosmético: con 100 mensajes idénticos, uno
distinto pasa desapercibido, y "se repitió en 34 de 52 lotes" es información.

## 6. La pregunta de fondo: qué significa "simulación anual"

El usuario preguntó si el modo anual estaba secando 10 kg durante un año. **No**: son N
tandas encadenadas (58 sobre el fixture). Pero su forma de plantearlo —*"cuando llegue al
equilibrio, dejar que pase al siguiente día y largar otra vez"*— señaló un hueco real:
recargábamos en el **instante exacto** en que terminaba el lote anterior, a las 3 de la
madrugada si tocaba.

`PoliticaRecarga` (hora de carga default 8:00 + maniobra 1 h) modela la espera. Efecto
sobre un año: **58 → 52 lotes, 1044 → 936 kg (−10 %)**. La tasa de régimen pasó a dividir
por el **ciclo** (secado + espera), no solo por el secado, que la sobrestimaba.

En P4, `st.time_input` en vez de `number_input`: la hora del día se lee "08:00", no "8.00".

## 7. El reporte PDF real del usuario

Armario con manzana en Salta, corrida anual completa. El PDF destapó cuatro cosas:

**(a) La presión no era la del sitio.** La carta psicrométrica decía "P = 73.1 kPa
(altitud del emplazamiento)" pero el emplazamiento está a 1187 m (87.9 kPa ISA). Los
73.1 kPa venían de la **altitud de la grilla NASA: 2786 m**, que el propio reporte
mostraba en la página 1. La celda de 0.5° promedia el altiplano circundante.

`presion_representativa_proyecto` prefería la media de NASA "para capturar el sesgo
local", pero le metía la altura equivocada. Impacto: 17 % de error en P → ω_sat más alta
→ **secado optimista**, y ebullición a 91 en vez de 96 °C (que es lo que había causado el
crash del bloque 5). Arreglado con reducción barométrica que conserva el desvío
meteorológico de la fuente: **73.10 → 89.15 kPa**.

**(b) Claves i18n crudas en el PDF**: `reporte.anual.graficas` y
`reporte.anual.fig.kg_mes` salían literales — faltaban en los YAML desde E4.

**(c) Rótulo pisado**: "Lotes completados (sin completar)" no entraba en la columna.

**(d) Leyenda falsa** en la carta psicrométrica, corregida a "presión del sitio".

**Lo que el reporte confirmó del diseño del usuario**: `ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE`
(banco 0.011 kg/s vs cámara 0.030) más `CAM_HR_FLUJO_ALTA` en 50 de 169 lotes → el caudal
no cierra. La agregación de advertencias del bloque 5 funcionó como se esperaba: los
conteos ("se repitió en 50 de 169 lotes") convirtieron el ruido en diagnóstico.

Resultados con sentido físico: 347 kg de producto seco contra 1343 kg de agua (relación
3.9×, coherente con manzana de X=4.6 a 0.15), 169 lotes, η secado 0.169, 14.13 MJ/kg
agua — dentro del rango de literatura. Estacionalidad visible: junio 11 lotes,
diciembre 17. **Esos números van a bajar** al repetir la corrida con la presión
corregida.

## Pendientes

- **No arrancar lotes con mal pronóstico** — hoy el modelo carga aunque el día venga
  nublado; un operador miraría el cielo. Infla los lotes frustrados con casos que no
  ocurrirían. Es la que más falta de la lista que salió de la discusión.
- **`PoliticaRecarga` no se persiste** en el snapshot del proyecto: vive en los widgets.
  Sobrevive la sesión pero no un guardar/cargar. Hay que decidir dónde guardarla — se
  acaba de sacar `OperacionAnualConfig` de `Camara` y no conviene volver a meter config
  ahí sin pensarlo.
- **Modo anual del túnel semicontinuo**: rechazado con `ANUAL_SEMICONTINUO_NO_SOPORTADO`.
  Su operación es flujo continuo, no lotes; habría que pensarlo como producción sostenida.
- `validacion/validacion_cruzada_yacon.py` sigue roto desde S38.
- `h_w` de McAdams usa el viento a 2 m sin corregir a la altura del equipo.

## Ver también

- [[docs/notas/plan_anual_8760]]
- [[docs/tareas]]
- [[CHANGELOG]]
