# Bitácora — Sesión 64

**Fecha:** 2026-08-01
**Tema:** revisión crítica de la topología de transferencia que introdujo S63. Se retira el
through-flow y la cámara queda con **una sola topología: cross-flow**.

**Punto de partida:** el usuario pide analizar con ojo crítico lo implementado en S63 y
pregunta, sobre la tabla de cómo quedó el modelo, *"¿desde cuándo no tenemos convección natural
en flujo vertical?"*, señalando que **los armarios de convección ascendente existen y
funcionan** — y que ese flujo no es vertical puro sino ascendente con componentes en x e y.

---

## 1. El análisis: tres problemas encadenados

### 1.1 El par `(d_p, Φ_s)` del catálogo es internamente inconsistente

En Ergun (`motor_calc.py:390`, `phi_dp = phi_s * d_p`) y en el área específica del lecho, `d_p`
y `Φ_s` **nunca aparecen por separado**: solo entra su producto, que es el **diámetro de
Sauter** `d_sv = 6·V/S`, una propiedad medible de la partícula y no dos perillas.

El catálogo pone `diametro_eq_m = 6 mm` (el **espesor** de la rodaja) y `esfericidad = 0.6`.
Producto: `d_sv = 3.6 mm`. Pero 0.6 **es** la esfericidad de la rodaja, y solo es consistente
con el diámetro de la esfera equivalente en volumen: se aplicaba la corrección de forma **dos
veces**.

| rodaja | d_vol | Φ_real | **d_sv** | a_v real | a_v del modelo |
|---|---|---|---|---|---|
| D=50 e=6 mm | 28.2 mm | 0.514 | **14.5 mm** | 227 m²/m³ | 917 m²/m³ (**4.03×**) |

Propagación: área **4× alta**, término viscoso de Ergun **16×**.

### 1.2 El modelo se autorefutaba

Presión motriz de un armario pasivo: `ρ·g·H·(ΔT/T) ≈ 1.3 Pa`. El modelo cobraba **31.6 Pa** por
atravesar el lecho — **24× lo disponible**. O sea: afirmaba que un armario ascendente pasivo no
puede mover aire. **La observación de campo del usuario es, por sí sola, evidencia de que el
número está mal**, por un camino independiente del argumento geométrico.

Con el `d_sv` correcto el balance cierra al filo (1.25 Pa viscosos contra 1.3 disponibles), que
es como son esos secadores: lentos, capas finas, pocas bandejas. De ahí que el aire real **no
percola al 100 %**: se reparte entre atravesar y rodear.

### 1.3 El resultado ya no dependía del modelo del lecho

A NTU 32 el aire sale saturado; dividir NTU por 16 todavía da 86 % de acercamiento. El número
que S63 celebró (13.55 h) **no lo produjo Ranz-Marshall**: lo produjo cruzar el umbral de
saturación. Como prediseñador, el modelo había dejado de responder al espesor, al número de
bandejas y al tamaño de partícula.

### 1.4 Sobre "convección natural en vertical"

Se separaron tres cosas que en el proyecto se llaman igual. Lo que S63 eliminó fue **solo** el
film aire↔producto, y solo en la rama atravesada; el motor de caudal y el film de pared quedaron
intactos. La justificación escrita en el código (*"dentro del lecho el empuje no tiene escala
libre"*) se auditó con el Rayleigh-Darcy: `Ra_D ≈ 1` contra el crítico `4π² ≈ 39.5` para una
capa de 2 cm de rodajas — **correcta, con un margen de 40×**, pero con un rango de validez que
nunca se había declarado (una capa de 10 cm de trozos grandes con ΔT 20 K da `Ra_D ≈ 45`).

---

## 2. La decisión

**Anular `VERTICAL_ASCENDENTE` y dejar cross-flow como única topología.** Razones del usuario:

> La posición de las aberturas fija la **escala** del flujo; la disposición de las bandejas fija
> la **dirección local** sobre el producto. Son dos problemas separados y la literatura los
> trata por separado.

La disposición real de bocas en CAJA/ARMARIO —entrada abajo en una cara, salida arriba en la
opuesta— es *cross ventilation con displacement flow*: el flujo **global** es diagonal
ascendente, pero **local sobre la bandeja es cross-flow**. Fijarlo con carga uniforme convierte
el área en un escalar limpio y elimina un parámetro que un usuario de prediseño no puede
responder con confianza.

Decisiones tomadas en la planificación: **cara inferior con factor fijo** (no se implementa el
empuje solutal), **espesor derivado** de la carga, y **el motor de tiro existente** (S61) en vez
de esperar el capítulo de ASHRAE —que, se verificó, no está en `docs/notas/papers/`—.

Plan completo en [[docs/notas/plan_crossflow_unico_camara]].
Resultado detallado en [[docs/notas/resultado_crossflow_unico_camara]].

---

## 3. Lo implementado

Cinco etapas. El detalle está en el documento de resultado; acá el resumen.

1. **Anular el through-flow.** `VERTICAL_ASCENDENTE` sobrevive en el enum para deserializar y
   `ConfiguracionFlujo.__post_init__` lo coacciona (patrón de `modo_calculo="capa_fina"`, S38);
   el aviso lo da la capa de carga de P4, la última que ve el valor original. Fuera:
   `es_flujo_atravesado`, la rama atravesada completa, Ergun, `K_TRANSICION_LECHO`,
   Ranz-Marshall y el área específica de partícula.
2. **Las dos caras de la bandeja.** `A = n·A_bandeja·(1 + f_abierta_malla · 0.5)`. `tipo_malla`
   deja de gobernar solo el ΔP. El 0.5 sale del cociente rama débil/fuerte de
   `nusselt_placa_horizontal` en el Ra de una bandeja (0.61 a 1e4, 0.48 a 1e6), no de un valor
   típico.
3. **Espesor derivado de la carga uniforme**, en `Camara.__post_init__` —no en la UI, porque el
   barrido paramétrico muta masa y área vía `dataclasses.replace`—. Widget de P4 a `st.metric`.
4. **Guardarraíl de espesor:** ya existía (§4).
5. **Barrido del espaciado entre bandejas** registrado en `catalogo_parametros_barrido.py`.

---

## 4. Lo que apareció al implementar

Seis desviaciones y seis hallazgos; **cuatro de estos los destapó un test al fallar**, no una
búsqueda. Los cuatro que más pesan:

### 4.1 El plan proponía crear un error; hubo que **relajar** el que existía

Con el espesor derivado, `BAND_SEPARACION_INSUFICIENTE` —que exigía 1 cm de aire libre— volvía
**inconstruible** el proyecto industrial de prueba (11 000 kg, 120 bandejas, separación 4 cm ⇒
capa de 3.5 cm): el `.json` no se podía ni abrir. Ese margen es una heurística de diseño, no una
imposibilidad física. Ahora el error duro es solo `espesor ≥ separación`, y el margen pasó a la
advertencia nueva `CAM_CANAL_MUY_ESTRECHO`. Mismo criterio que S62 con los topes de widgets
(`8420c70`).

### 4.2 El encadenado inmediato de lotes **no es cota superior de producción**

Lo destapó `test_ventana_glue`. Con lotes de ~100 h la **alineación con el sol** pasa a mandar:
un lote que arranca a las 3 de la mañana se pasa la noche sin secar y no cierra dentro de la
ventana. Medido en 6 días: **con espera 24 kg secos, sin espera 12 kg**, con la **misma agua
evaporada** (~56 kg). No cambia cuánto se seca, cambia cuántos lotes cierran.

Estaba escrito como verdad en `CLAUDE.md` y en `simulacion_ventana.py` desde S57. **Corregido en
los dos.** Corolario: la política de recarga dejó de ser una restricción operativa y pasó a ser
una decisión de diseño que puede mejorar la producción.

### 4.3 La etapa 4 ya estaba casi hecha, y dos umbrales se pisan

`BAND_ESPESOR_CAPA_GRANDE` ya existía con la física correcta escrita. Falta solo el refinamiento
por producto. Pero apareció un acoplamiento: con el tope de 20 kg/m² de
`COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA`, el espesor máximo alcanzable es `20/(ρ·(1−ε))` — para
manzana **4.3 cm, así que esa advertencia nunca puede dispararse**; para orégano 10.4 cm y sí.

### 4.4 El anclaje del extractor 76 W sobrevive, pero no por la cámara

`test_motor_anclaje` exigía > 30 Pa **de la cámara sola**, apoyado en Ergun. En cross-flow
aporta **0.09 Pa**. El anclaje de campo sigue en pie —los 76 W los explican ductos, codos y
colector— y el test se reescribió para afirmar eso, no para bajarle el umbral en silencio.
**Duda que quedó escrita en el propio test:** 50 kg sobre 5 bandejas de 0.8 m² son ~2.7 cm de
capa, que es un lecho. Si el armario real es de flujo atravesado, el modelo lo subestima a
propósito.

**Otros dos:** el `acercamiento_equilibrio` del diagnóstico calculaba el CSTR cuando el motor
integra una cadena de 8 etapas desde S63 (a NTU = 2, 83 % contra 67 %); y `d_p` cambió de signo
—en Ergun era diámetro de partícula (más chica ⇒ más ΔP), en cross-flow es altura de rugosidad
(más grande ⇒ más ΔP)—, lo que de paso **vuelve inocua la inconsistencia del `d_sv`**: el único
uso vivo de `d_p` es como rugosidad, y ahí *"la dimensión normal al flujo"* del catálogo es la
lectura correcta. No hubo que tocar el catálogo.

---

## 5. Resultados sobre los proyectos del usuario

| | S63 | S64 |
|---|---|---|
| A_prod (armario de referencia) | 45.83 m² | **3.25 m²** |
| h | 24.58 W/m²K | **2.70 W/m²K** |
| NTU | 32.6 | **0.246** |
| acercamiento al equilibrio | ~100 % | **21.5 %** |

**Los siete snapshots cargan, migran y calculan.** Dos lecturas que no se esperaban:

- **El espesor derivado da 0.61–0.87 cm en los siete, y todos declaraban ~2 cm.** Era
  sistemático, no una particularidad del caso de referencia: todos cargaban entre 2× y 3× menos
  producto del que su capa declarada suponía.
- **El ΔP de cámara queda entre 0.000 y 0.031 Pa** en todos. En cross-flow la cámara casi no
  ofrece resistencia; toda la del lazo está en bocas, ductos y chimenea.

**El lazo de tiro no colapsa** (era la preocupación abierta): Picard converge en 4–6 iteraciones
y `T_flujo` queda entre 29.9 y 60.3 °C contra 20 °C ambiente. El riesgo era propio del régimen
de NTU alto, así que retirar el through-flow lo elimina en vez de agravarlo.

**El óptimo de espaciado existe y es medible:** comprimir el canal de 6 a 2 cm da 1.6× de `h` a
costa de **45× de ΔP**.

---

## 6. Estado al cierre

- **Suite 1978 passed + 2 skips.** Ruff, black y `auditar_i18n.py` limpios.
- **Nada commiteado.** `origin/main` sigue en `080eec7` (v1.4.0), con S63 **y** S64 encima:
  43 archivos, +2633/−539.
- **13 módulos de tests tocados.** `test_topologia_transferencia_camara.py` reescrito entero
  (los 28 de S63 cubrían la binaria eliminada; quedaron 25 sobre el modelo nuevo).
- **Módulo movido:** `calculos/lecho_producto.py` → **`core/lecho.py`**, con shim de
  re-export. `Camara.__post_init__` lo necesita y habría sido el primer `core → calculos` del
  proyecto.
- **Vestigial nuevo:** `esfericidad` (Φ_s) quedó **sin ningún consumidor**.
- **Costo de suite: 11 min 38 s**, de los cuales **314 s (44 %)** son
  `test_barrido_parametrico::test_correr_barrido_anual`.

### Lo que queda abierto

1. **Bump de versión** — por el criterio de S62 corresponde menor como mínimo: cambian **todos**
   los proyectos, no solo los verticales.
2. **Smoke en Streamlit de P4** — lo único de la verificación del plan que no se corrió.
3. `espesor_ensayo_m` por producto, mirando el acoplamiento con el tope de 20 kg/m².
4. **La percolación parcial**: reparto de caudal entre caminos paralelos por igualdad de Δp, con
   la fracción que atraviesa el lecho como **resultado**. Requiere arreglar antes el `d_sv`.
5. **El empuje solutal**: mientras no esté, el factor de cara inferior es fijo y no distingue el
   armario indirecto (donde la cara de abajo **favorece**) de la caja directa con producto
   insolado (donde **suprime**). El cruce está en |ΔT| ≈ 2.2 K.
6. **Nada contrastado contra una medición.** Sigue siendo el pendiente número uno.

## Ver también

- [[docs/notas/plan_crossflow_unico_camara]] — el plan.
- [[docs/notas/resultado_crossflow_unico_camara]] — el resultado detallado.
- [[docs/bitacora/bitacora_sesion63]] — la sesión que introdujo el through-flow.
- [[CHANGELOG]] — el `[Unreleased]`.
- [[docs/tareas]] — backlog.
