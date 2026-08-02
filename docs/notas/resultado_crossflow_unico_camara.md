# Resultado — cross-flow único en la cámara de secado

**Sesión:** S64. **Plan:** [[docs/notas/plan_crossflow_unico_camara]].
**Estado:** las 5 etapas implementadas. **Suite 1978 passed + 2 skips, 0 fallas.**
Ruff, black y `auditar_i18n.py` limpios (0 literales visibles pendientes).
**Nada commiteado:** `origin/main` sigue en `080eec7` (v1.4.0), con S63 y S64 encima en el
working tree.

Este documento registra **qué pasó al implementar**, que no es lo mismo que lo que el plan
decía que iba a pasar. Las desviaciones están en §3 y los hallazgos que no estaban previstos
en §4 — varios salieron de tests que fallaron, no de haberlos buscado.

---

## 1. Lo que se implementó

| Etapa | Estado | Nota |
|---|---|---|
| 1 — anular el through-flow | ✅ | `VERTICAL_ASCENDENTE` coaccionado, no borrado |
| 2 — la segunda cara de la bandeja | ✅ | `A = n·A_bandeja·(1 + f_malla·0.5)` |
| 3 — carga uniforme, espesor derivado | ✅ | derivado en `Camara.__post_init__` |
| 4 — guardarraíl de espesor | ⚠️ parcial | **el grueso ya existía** (§3.4) |
| 5 — óptimo de espaciado | ✅ | parámetro registrado en el barrido |

### 1.1 El modelo que quedó

```
A_prod = n_bandejas · área_bandeja · (1 + f_abierta_malla · _FACTOR_CARA_INFERIOR)
h      = coef_conveccion_producto_local(v_canal, …)        [placa plana mixta, Incropera 9.64]
v_canal = ṁ / (ρ · ancho · (separación − espesor) · (n−1))
espesor = masa / (ρ_material · (1−ε) · área_bandeja · n_bandejas)     ← DERIVADO
N_etapas = 8                                                          [cadena de aire]
```

`_FACTOR_CARA_INFERIOR = 0.5` quedó anclado en el cociente rama débil/fuerte de
`nusselt_placa_horizontal` sobre el Ra de una bandeja, no en un "valor típico":

| Ra | Nu fuerte | Nu débil | débil/fuerte |
|---|---|---|---|
| 1e4 | 5.40 | 3.28 | 0.61 |
| 1e5 | 9.60 | 5.20 | 0.54 |
| 1e6 | 17.08 | 8.24 | 0.48 |
| 1e7 | 32.32 | 13.06 | 0.40 |

---

## 2. Resultados medidos

### 2.1 El caso de referencia (armario indirecto forzado)

| | S63 (through-flow) | S64 (cross-flow) |
|---|---|---|
| A_prod | 45.83 m² | **3.25 m²** (2.50 la cara superior sola) |
| h | 24.58 W/m²K | **2.70 W/m²K** |
| NTU | 32.6 | **0.246** |
| acercamiento al equilibrio | ~100 % | **21.5 %** |
| espesor de capa | 2.00 cm (declarado) | **0.82 cm** (derivado) |

Es la regresión anunciada en el plan §6: el armario vuelve del orden de las 100 h de secado.

### 2.2 Los siete snapshots del repo

Todos cargan, migran y calculan. Los tres que traían `VERTICAL_ASCENDENTE` pasan a cross-flow
con aviso en P4.

| proyecto | tipología | motor | `direccion_flujo` | espesor derivado | NTU | ΔP cámara |
|---|---|---|---|---|---|---|
| armario indirecto forzado | ARMARIO | ventilador | VERTICAL → HORIZONTAL | 0.82 cm | 0.220 | 0.005 Pa |
| cajón chimenea + extractor + resistencia | CAJA | chimenea | VERTICAL → HORIZONTAL | 0.61 cm | 1.491 | 0.001 Pa |
| armario con resistencia | CAJA | — | VERTICAL → HORIZONTAL | 0.87 cm | 1.484 | 0.000 Pa |
| armario modo anual | ARMARIO | chimenea | HORIZONTAL | 0.68 cm | 0.126 | 0.031 Pa |
| cajón con chimenea | CAJA | chimenea | HORIZONTAL | 0.72 cm | 0.165 | 0.010 Pa |
| cajón convección natural | CAJA | — | HORIZONTAL | 0.65 cm | 0.222 | 0.015 Pa |

**Dos lecturas que no esperábamos:**

1. **El espesor derivado da 0.61–0.87 cm en los siete, y todos declaraban ~2 cm.** No era una
   particularidad del proyecto de referencia: es sistemático. Todos los proyectos cargaban
   entre 2× y 3× menos producto del que su capa declarada suponía, y hasta S63 el modelo
   calculaba con la capa declarada.
2. **El ΔP de cámara queda entre 0.000 y 0.031 Pa en todos.** En cross-flow la cámara
   prácticamente no ofrece resistencia: toda la del lazo está en bocas, ductos y chimenea.

### 2.3 El lazo de tiro no colapsa (verificación §7.3 del plan)

Era la preocupación abierta: con NTU alto el aire sale casi a la ambiente y mata el empuje que
lo mueve, realimentando hacia el estancamiento. Corrido sobre los pasivos:

| proyecto | Picard | iteraciones | `T_flujo` (T_amb = 20 °C) |
|---|---|---|---|
| cajón chimenea + extractor | converge | 6 | 32.2 °C |
| armario con resistencia | converge | 5 | 29.9 °C |
| armario modo anual | converge | 4 | 60.3 °C |

**El riesgo era propio del régimen de NTU alto, así que retirar el through-flow lo elimina en
vez de agravarlo.** Queda cerrado.

### 2.4 El óptimo de espaciado existe y es medible (etapa 5)

Cajón pasivo real, capa derivada 0.65 cm, 8 bandejas:

| separación | v_canal | h | NTU | ΔP cámara |
|---|---|---|---|---|
| 2.0 cm | 0.635 m/s | 4.25 W/m²K | 0.340 | 0.3955 Pa |
| 2.5 cm | 0.463 | 3.71 | 0.297 | 0.1579 |
| 3.0 cm | 0.365 | 3.37 | 0.270 | 0.0800 |
| 4.0 cm | 0.256 | 2.98 | 0.239 | 0.0301 |
| 5.0 cm | 0.197 | 2.77 | 0.222 | 0.0150 |
| 6.0 cm | 0.160 | 2.64 | 0.211 | 0.0087 |

Comprimir el canal de 6 a 2 cm da **1.6× de `h` a costa de 45× de ΔP**. Con el caudal fijo
(esta tabla) gana siempre comprimir; con el lazo de tiro cerrado —que es lo que hace el barrido
ahora que el parámetro está registrado— el ΔP se come el caudal y aparece el óptimo.

---

## 3. Desviaciones respecto del plan

### 3.1 La clase de flujo se llama `ConfiguracionFlujo`, no `FlujoAire`

Error de nombre en el plan. Sin consecuencias.

### 3.2 El módulo del lecho se mudó a `core/lecho.py`

El plan ponía `espesor_capa_derivado_m` en `calculos/lecho_producto.py` y lo llamaba desde
`Camara.__post_init__`. Eso habría sido el **primer `core → calculos` del proyecto**: una
inversión de capas. Se movió el módulo entero a `core/lecho.py` y `calculos/lecho_producto.py`
quedó como **shim de re-export**, con lo que ningún consumidor de `calculos/` cambió. Mismo
patrón que `calculos/simulacion_ventana` con `PoliticaRecarga` (S59).

Por lo mismo, `AREA_ABIERTA_MALLA` y `area_abierta_malla_efectiva` viven en `core/lecho.py` y
no en `motor_calc.py` como decía el plan: son geometría de bandeja compartida por el ΔP y por
la transferencia. `TIPOS_MALLA` (el K de pérdida de carga) se queda donde estaba.

### 3.3 `CAM_CAPA_CIERRA_EL_CANAL` no hacía falta — y hubo que **relajar** la regla existente

El plan proponía crear un error para el caso "la capa cierra el canal". Ya existía
`BAND_SEPARACION_INSUFICIENTE`, que además exigía **1 cm de aire libre**. Con el espesor
derivado esa regla volvía **inconstruible** el proyecto industrial de prueba (11 000 kg,
120 bandejas de 5 m², separación 4 cm ⇒ capa de 3.5 cm): `ValueError` en `__post_init__`, o
sea que el `.json` no se podía ni abrir.

El margen de 1 cm es una **heurística de diseño, no una imposibilidad física**, y bloquear
diseños apretados pero legítimos es exactamente lo que se corrigió en S62 (commit `8420c70`,
*"los topes de los widgets dejan de bloquear diseños legítimos"*). Se reestructuró:

- **error duro** solo si `espesor ≥ separación` (la capa literalmente no entra);
- **advertencia `CAM_CANAL_MUY_ESTRECHO`** (WARNING) si entra pero deja menos de 1 cm.

### 3.4 La etapa 4 ya estaba casi hecha

`BAND_ESPESOR_CAPA_GRANDE` **ya existía** en `advertencias_camara`, con la física correcta
escrita: *"en lechos gruesos la resistencia interna a la difusión de humedad crece y el secado
real puede ser más lento que el estimado"*. Lo único que falta de la etapa 4 es el refinamiento
por producto (`espesor_ensayo_m` en el catálogo) en vez del umbral global de 5 cm.

Aparte, la restricción masa↔geometría tampoco era inexistente:
`COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA` ya cortaba en 20 kg/m²/bandeja. Es un tope plano, no
la relación física; la etapa 3 lo refina en vez de crearlo de cero. (Su mensaje todavía dice
*"máximo para capa fina"*, encuadre vestigial de S38.)

### 3.5 La derivación corre **después** de `_validar_coherencia`

Al principio corría antes y una sobrecarga grosera (500 kg sobre 5 bandejas de 0.5 m²) la
diagnosticaba `CAM_CAPA_DERIVADA_NO_ENTRA` en vez del mensaje de 20 kg/m², que es más
informativo. Se invirtió el orden. `_validar_coherencia` no lee el espesor, así que es seguro.

### 3.6 Se retiró `DiagnosticoTransferencia.atravesado`

El campo describía la binaria eliminada. Lo consumía `ui/p4_camara.py` para elegir entre dos
textos de topología; quedó uno solo.

---

## 4. Hallazgos colaterales

Ninguno de estos estaba en el plan. **Cuatro de los cinco los destapó un test al fallar**, no
una búsqueda deliberada.

### 4.1 El encadenado inmediato de lotes **no es cota superior de producción**

Lo destapó `test_ventana_glue::test_desactivar_la_espera_no_baja_la_produccion`.

Hasta S63 era cierto: arrancar el lote siguiente apenas termina el anterior nunca podía
producir menos que esperar a la hora de carga. Valía porque el lote entraba holgado en un día.
Con lotes del orden de 100 h la **alineación con el sol** pasa a mandar: un lote que arranca a
las 3 de la mañana se pasa la noche sin secar y no llega a cerrar dentro de la ventana.

Medido en una ventana de 6 días:

| | con espera (política activa) | sin espera (encadenado inmediato) |
|---|---|---|
| producto seco | **24.0 kg** | **12.0 kg** |
| agua evaporada | 56.0 kg | 55.7 kg |

**No cambia cuánto se seca; cambia cuántos lotes cierran** — dos contra uno.

La afirmación estaba escrita como verdad en `CLAUDE.md` y en el docstring de
`simulacion_ventana.py` desde S57. Las dos corregidas. **Corolario:** la política de recarga
dejó de ser una restricción operativa y pasó a ser una **decisión de diseño que puede mejorar
la producción**.

### 4.2 El diagnóstico de NTU describía el CSTR y el motor integra una cadena

`DiagnosticoTransferencia.acercamiento_equilibrio` calculaba `NTU/(1+NTU)` —el CSTR— cuando el
motor integra `resolver_cadena_camara` con N = 8 desde S63. Corregido a `1 − (1+NTU/N)^(−N)`.
A NTU = 2 son **83 % contra 67 %**. Era una inconsistencia entre el diagnóstico y el modelo
que arrastraba desde la etapa 4 de S63.

### 4.3 Dos umbrales que se pisan

Con el tope de 20 kg/m² de `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA`, el espesor máximo
alcanzable es `20/(ρ_material·(1−ε))`:

| producto | ρ [kg/m³] | espesor máximo | ¿puede dispararse `BAND_ESPESOR_CAPA_GRANDE` (5 cm)? |
|---|---|---|---|
| manzana | 840 | 4.3 cm | **no, nunca** |
| orégano | 350 | 10.4 cm | sí |

Los dos umbrales se pusieron por separado y ahora que el espesor se deriva quedaron acoplados.
Cualquier ajuste de uno tiene que mirar al otro.

### 4.4 `d_p` cambió de signo

En Ergun `d_p` era diámetro de partícula: partícula **más chica** ⇒ más superficie ⇒ **más**
ΔP. En cross-flow es la altura de rugosidad de la pared del canal (`ε_eff = max(ε_chapa, d_p)`):
grano **más grande** ⇒ **más** ΔP. El test que lo verificaba afirmaba lo contrario.

Corolario práctico: hay que evaluarlo en régimen **turbulento**. Con el caudal chico de la
fixture original, `f = 64/Re` no depende de la rugosidad y los dos casos daban idénticos
(`0.00182 > 0.00182`).

**Efecto lateral bueno:** con `Φ_s` sin consumidores (§5.2), la inconsistencia del diámetro de
Sauter que motivó todo el cambio deja de tener consecuencias. El único uso vivo de `d_p` es
como altura de rugosidad, y ahí *"la dimensión normal al flujo"* —la lectura que el catálogo ya
declara— **es la correcta**. No hubo que tocar el catálogo.

### 4.5 El anclaje empírico del extractor 76 W sobrevive, pero no por la cámara

`test_motor_anclaje` exigía que **la cámara sola** aportara > 30 Pa, apoyado en Ergun. En
cross-flow aporta **0.09 Pa**: 300× menos.

El anclaje de campo **sigue en pie**: `test_potencia_electrica_en_rango_realista` pasa sin
cambios, porque los 76 W los explican ductos, codos y colector (singulares > 30 Pa a 6 m/s).
El test se reescribió para afirmar eso explícitamente —la cámara aporta poco y las singulares
dominan por más de 10×— en vez de bajarle el umbral en silencio.

**Duda que quedó escrita en el propio test, porque es del usuario y no del modelo:** 50 kg
sobre 5 bandejas de 0.8 m² son 12.5 kg/m², o sea ~2.7 cm de capa. Eso es un lecho, no una
monocapa. Si el armario real de 50 kg es de flujo atravesado —y con un extractor de 76 W puede
permitírselo—, la cámara sí aporta ΔP y el modelo lo está subestimando a propósito. Es el
riesgo asumido del plan §7.1, ahora con un número concreto encima.

### 4.6 Un test fijaba el conteo del catálogo de barrido

`test_catalogo_tiene_18_parametros` afirmaba `len(CATALOGO_PARAMETROS) == 18`. Al registrar
`separacion_bandejas` pasó a 19. **La suite había dado verde justo antes de agregar el
parámetro y el módulo que lo verificaba no estaba en el subconjunto que se corrió después**:
apareció por un `grep`, no por la corrida. Actualizado a 19 con la nota de qué lo agregó.

---

## 5. Estado del código

### 5.1 Archivos

43 archivos tocados, +2633/−539 — **incluye S63 sin commitear**, que arrastra el mismo working
tree. Lo propio de S64:

| capa | archivos |
|---|---|
| `core/` | `camara.py` (coacción, derivación, advertencia nueva, relajación de la separación), **`lecho.py` (nuevo, movido)** |
| `calculos/` | `camara_calc.py`, `motor_calc.py`, `catalogo_parametros_barrido.py`, `simulacion_ventana.py`, `lecho_producto.py` (shim) |
| `ui/` | `p4_camara.py` (selector fuera, espesor a métrica, aviso de migración), 3 × `p4.yaml`, 3 × `advertencias.yaml` |
| docs | `CHANGELOG.md`, `CLAUDE.md`, este documento y el plan |

### 5.2 Lo que quedó vestigial

| símbolo | estado |
|---|---|
| `DireccionFlujo.VERTICAL_ASCENDENTE` | sobrevive en el enum para deserializar; coaccionado en `__post_init__` |
| `ConfiguracionBandejas.esfericidad` (Φ_s) | **sin ningún consumidor**: solo aparecía en `Φ_s·d_p` de Ergun y del área específica |
| `esfericidad` en `catalogo/productos/*.yaml` | ídem; se conserva por back-compat |

### 5.3 Tests

**13 módulos tocados.** `test_topologia_transferencia_camara.py` se reescribió entero (los
28 tests de S63 cubrían la binaria eliminada; quedaron 25 sobre el modelo nuevo). Los otros 12
se adaptaron: `test_motor_fase2`, `test_balance_global`, `test_cadena_etapas_camara`,
`test_diagnostico_transferencia`, `test_camara_conveccion_natural`, `test_motor_anclaje`,
`test_radiacion_camara`, `test_ventana_glue`, `test_catalogo_parametros_barrido`,
`test_core/test_camara`, `test_core/test_motor`, `test_ui/test_diagnostico_ntu_p4`.

Un test quedó **más fuerte** de lo que estaba: `test_la_masa_del_lecho_cierra_con_la_carga_
declarada` verifica que `masa_que_llena_el_lecho_kg` devuelve exactamente los 9.5 kg cargados
—la comprobación dura de la restricción de carga uniforme—, donde antes comparaba contra una
constante recalculada a mano.

### 5.4 Costo de la suite

**11 min 38 s**, de los cuales **314 s (44 %) se los lleva
`test_barrido_parametrico::test_correr_barrido_anual`**. No es patológico: es un barrido anual
con lotes que ahora integran ~8× más horizonte. Si molesta el tiempo de iteración, la salida
limpia es `@pytest.mark.slow` + exclusión del hook de `PostToolUse`, como ya se hace con
`i18n_paridad`.

---

## 6. Lo que queda abierto

1. **Bump de versión.** Por el criterio de S62 (*si cambian los resultados, cambia la versión*)
   corresponde menor como mínimo: cambian **todos** los proyectos, no solo los verticales.
2. **Smoke en Streamlit de P4** — lo único de la verificación §8 del plan que no se corrió.
3. **`espesor_ensayo_m` por producto** (lo que falta de la etapa 4), mirando el acoplamiento
   con el tope de 20 kg/m² de §4.3.
4. **La percolación parcial** (plan §7.2): reparto de caudal entre caminos paralelos resuelto
   por igualdad de Δp, con la fracción que atraviesa el lecho como **resultado** y no como
   declaración. Requiere arreglar antes el `d_sv` del catálogo.
5. **El empuje solutal** (plan §2.3): mientras no esté, el factor de cara inferior es fijo y no
   distingue el armario indirecto (donde la cara de abajo **favorece**) de la caja directa con
   producto insolado (donde **suprime**).
6. **Nada de esto está contrastado contra una medición.** Vale la advertencia general del work
   stream: es coherencia interna, no validación. Extensión natural de la mejora 38 fase 4.

## Ver también

- [[docs/notas/plan_crossflow_unico_camara]] — el plan que este documento cierra.
- [[docs/notas/plan_transferencia_camara]] — el plan de S63 que este revierte parcialmente.
- [[docs/bitacora/bitacora_sesion63]] — la sesión que introdujo el through-flow.
- [[docs/notas/plan_datos_medidos_4]] — la validación que cerraría esto contra datos reales.
- [[CHANGELOG]] — el `[Unreleased]` con todo lo de esta sesión.
- [[docs/tareas]] — backlog.
