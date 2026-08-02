# Bitácora — Sesión 63

**Fecha:** 2026-07-30 / 31
**Tema:** el aire de la cámara no seguía la adiabática. Diagnóstico y corrección completa de la
transferencia de calor y masa.

**Punto de partida:** el usuario observa que en la carta psicrométrica de su armario
**indirecto** (cámara opaca, bien aislada, sin auxiliar) el aire de salida no cae sobre la
adiabática de saturación y sale con HR muy baja. La teoría del secador indirecto dice
calentamiento sensible en colector + enfriamiento evaporativo **casi adiabático** en cámara.
Sospecha —correcta— de que era el síntoma de un problema físico mayor.

**Caso de referencia:** `tests/armario indirecto forzado/` — armario 0.5×0.5×1.1 m, cámara
opaca, colector 2×(2.5×1.0) m, ventilador, 9.5 kg de manzana en 10 bandejas con capa de 2 cm,
flujo **vertical ascendente**, ventana 20–27/04/2010, Salta (1187 m, 89.2 kPa). Reproducible al
decimal desde el `.json` + `obtener_clima`.

---

## 1. El diagnóstico: tres problemas apilados

### 1.1 La carta psicrométrica comparaba dos instantes distintos (bug)

`carta_psicrometrica.py` tomaba la **entrada** en el pico de POA de **todo el horizonte**
(hora 157) y la **salida** en el punto más cercano de la trayectoria de cámara, que **termina
cuando el producto alcanza X_obj** (hora 154). Desfasaje de 3 h.

Lo que dibujaba: entrada 51.96 °C / 4.061 g/kg, salida 33.51 °C / **3.486 g/kg**. El aire
aparecía **perdiendo** 0.6 g/kg al atravesar el secador —imposible sin condensación— con
Δh = −20.2 kJ/kg que no era del proceso sino del desfasaje.

Apareció al empezar a correr **ventanas multidía**: el desfasaje exige que el horizonte
sobreviva al lote. Con horizontes de 24 h que no terminan el secado, los índices coincidían.

### 1.2 El balance de cámara estaba bien

Alineando los instantes, el residuo del balance de energía del aire es **5×10⁻¹² W**. No había
término perdido ni doble conteo. En el pico del día 1, con producto húmedo:

```
ṁ·Δh = −44.28 W = −37.64 (pérdida de pared) − 6.64 (inercia térmica del producto)
T_prod = 20.48 °C   vs   T_bulbo húmedo = 21.10 °C
```

El producto se paraba en el bulbo húmedo y **todo** el desvío de la adiabática se explicaba.
La relación de Lewis estaba bien implementada.

### 1.3 El problema real: NTU = 0.19

```
A_prod = n_bandejas × área_bandeja = 2.5 m²   ← la huella, nada más
h_conv = 2.53 W/m²K                            ← placa plana externa, v = 0.137 m/s
NTU = 0.19  →  el aire recorría el 15 % del camino al equilibrio
```

**La incoherencia estructural:** para la **pérdida de carga**, `motor_calc` sabía desde siempre
que el producto es un lecho empacado —usa Ergun con porosidad, esfericidad y diámetro de
partícula, y distingue vertical de horizontal—. Para **calor y masa**, `camara_calc` trataba al
mismo producto como una placa plana lisa del tamaño de la bandeja, **siempre**, ignorando
`direccion_flujo`, el espesor de capa y los tres campos del lecho, que estaban en el data model
y en el catálogo sin que nadie los leyera para transferir.

No era un coeficiente mal ajustado: era una **topología faltante**.

---

## 2. Las cuatro etapas

Plan completo en [[docs/notas/plan_transferencia_camara]], con la física del modelo, sus
límites y los desvíos respecto de lo planificado.

### Etapa 0 — la carta deja de mentir

Una sola base temporal: el instante lo fija **la cámara** (máxima evaporación, la misma regla
que ya usaba el modo Constantes, que por construcción nunca cae en la cola con el producto
seco) y las forzantes se **interpolan** ahí. La carta además **rotula el instante** que muestra
(fecha y hora locales), que no se decía en ningún lado.

**No cambia ningún resultado del balance:** estaba mal la lectura, no el cálculo.

### Etapa 1 — topología de transferencia (el corazón)

Módulo nuevo `calculos/lecho_producto.py`, **única fuente de verdad** de la geometría del lecho
(`geometria_lecho` se mudó desde `motor_calc`, que la conserva como alias).

- `VERTICAL_ASCENDENTE` → el aire **atraviesa** el lecho: `A = a_v·V_lecho` con
  `a_v = 6(1−ε)/(Φ_s·d_p)`, y h por **Ranz-Marshall** sobre la velocidad másica superficial. El
  piso `Nu_p → 2` (conducción a partícula aislada) sostiene el coeficiente a caudal nulo, que
  es lo que hace falta en un secador pasivo.
- `HORIZONTAL` → el aire pasa **entre** bandejas: área de bandeja y placa plana, ahora con la
  velocidad **del canal** (antes transferencia usaba la cara entera de la cámara y ΔP el canal:
  dos velocidades para el mismo aire, 0.55 m² contra 0.225 m²).

Cuatro advertencias nuevas: `CAM_LECHO_BYPASS`, `CAM_LECHO_D_P_DEFAULT`,
`CAM_LECHO_CARGA_INCOHERENTE`, `CAM_LECHO_DEGENERADO`.

**Corrección sobre el plan:** la advertencia planificada era "bandejas que llenan la huella con
flujo HORIZONTAL = geometría imposible". Está mal: eso es el armario de bandejas clásico, el
aire pasa por los canales. La geometría problemática es la **opuesta** — flujo vertical con
bandejas que **no** cubren la huella, porque ahí parte del aire esquiva el lecho.

### Etapa 2 — coherencia de films

El film del producto se evaluaba con `T_ent`, cuando la fuerza impulsora del balance es
`h·A·(T_flujo − T_prod)`. Es **el mismo arreglo que S62 hizo para el film de pared** y que
había quedado sin hacer para el producto. Se resuelve dos veces por paso (estimación con
`T_ent`, refinación con `T_flujo`), el patrón que ya usaba la pared; ahora lo comparten los dos
films, también en el motor de cascada del túnel.

Medido — pesa donde manda la convección natural, o sea el **secador pasivo**:

| v_aire | h con `T_ent` | h con `T_flujo` | sobrestimación |
|---|---|---|---|
| 0.02 m/s | 2.32 | 1.21 | **1.92×** |
| 0.10 m/s | 2.49 | 1.76 | 1.41× |
| 1.00 m/s | 5.27 | 5.20 | 1.01× |

Más el `P_Pa` faltante en el `HR_desde_omega` de `balance_global` (usaba 101 325 Pa donde el
proyecto tiene 89 202: la HR de referencia salía ~12 % baja).

### Etapa 3 — métricas honestas

- **`aprovechamiento_aire` se medía contra un techo inalcanzable**: la saturación
  **isotérmica**, `ω_sat(T_ent) − ω_ent` = 110 g/kg a 51 °C, cuando el techo real de una cámara
  adiabática es `ω_sat(T_wb) − ω_ent` = **12.8 g/kg**. Daba ~8 veces peor de lo posible y
  **todo** secador se reportaba catastrófico.
- **Se resolvió de paso un problema viejo del usuario.** Al pasar al criterio adiabático el
  cálculo se caía con `PSICRO_PV_EXCEDE_P` — el mismo error reportado en **S57** con el armario
  a 2650 m. Causa: `temperatura_bulbo_humedo` chequeaba saturación en el bulbo **seco**, y a
  73 kPa el agua hierve a 91 °C. Pero ese aire no puede estar saturado (hervir es otra cosa) y
  **sí** tiene saturación adiabática. Ahora el bracket se acota a la ebullición local en vez de
  fallar. En S57 la solución había sido **excluir** esas horas; ahora se evalúan: T_wb = 28.5 °C
  y capacidad 27 g/kg. Se agregó `temperatura_ebullicion(P_Pa)` (inversión de Buck; a
  101.325 kPa da 100.00 °C).
- **NTU expuesto en P4** (`diagnostico_transferencia`, puro): superficie, h, NTU, acercamiento
  al equilibrio y el **régimen en palabras** (limitado por transferencia / intermedio /
  limitado por energía). Era el número que dice si el secador está bien cargado y no aparecía
  en ninguna vista.

### Etapa 4 — el aire como cadena de etapas

Un CSTR **no puede saturar por construcción** (`NTU/(1+NTU)`); el aire recorre un camino
humedeciéndose, que es flujo pistón (`1−exp(−NTU)`). A **NTU = 2, 67 % contra 86 %**.

`resolver_cadena_camara` parte el camino en N sub-etapas; con **N = 1 reproduce el CSTR
exactamente**. Las etapas las fija la topología, con el mismo criterio que ΔP: `n_bandejas` en
vertical (en serie) y 8 en horizontal (canales en paralelo, pero cada uno continuo).

**Dos desvíos del plan:** (a) "una etapa por bandeja" solo vale en vertical; (b) no se reusó
`simular_cascada`, que resuelve N zonas con **su propio estado de producto cada una** — acá el
producto sigue siendo uno y lo que se estratifica es el aire, así que alcanzó con encadenar el
solve algebraico dentro del RHS, sin tocar las EDOs ni el contrato del resultado.

**Regresión que encontró la suite:** dejar que cada etapa modulara su propia potencia auxiliar
daba **un controlador por tramo**, y el primero —que ve el aire frío de entrada— encendía
siempre aunque el sol ya hubiera superado la consigna aguas abajo. Lo detectó el test de S62
`test_la_resistencia_se_apaga_cuando_el_sol_ya_supera_la_consigna`: 34 W donde debía haber 0. Un
termostato mide el aire de la cámara y gobierna **una sola** potencia; como la cadena es afín en
la potencia total, se despeja con dos evaluaciones más una final, sin iterar.

---

## 3. El resultado sobre el caso del usuario

| | antes de S63 | después |
|---|---|---|
| A_prod | 2.5 m² | **45.8 m²** |
| h | 2.5 W/m²K | **24.7 W/m²K** |
| NTU | 0.19 | **32.6** |
| HR del aire de salida en el pico | 8–11 % | **100 %** |
| Δh entrada→salida en cámara | −20.2 kJ/kg (con el bug de la carta) | **+0.93 kJ/kg** |
| T_prod − T_bulbo húmedo | −0.6 K | +0.3 K |
| t_secado | 156 h | **13.55 h** |

El aire sale **saturado sobre la adiabática**: exactamente lo que pedía la teoría del secador
indirecto. El Δh positivo es correcto — a NTU alto el aire sale por debajo de la ambiente y la
pared **aporta** calor en vez de perderlo (enfriamiento evaporativo).

**El diagnóstico de S62 §5 queda invalidado.** Aquello concluía "armario desbalanceado, 73 % de
la energía se va con el aire de salida, usa el 4 % de su capacidad". Era un **artefacto** del
modelo de transferencia: con el área del lecho el aire sale a ~21 °C y el escape casi no pierde.

---

## 4. Hallazgos colaterales

- **La suite entera pasaba sin tocar un solo assert después de mover el resultado 11×.** Ningún
  test fijaba el tiempo de secado de una cámara de flujo vertical: el número más visible del
  proyecto no estaba cubierto. Los tests nuevos lo cubren.
- **El proyecto de prueba tiene un input incoherente**, que ahora el modelo avisa: la capa
  declarada de 2 cm sobre 10 bandejas se llenaría con 23.1 kg y se cargan 9.5 (capa real
  ≈ 0.8 cm).
- **`CAM_HR_FLUJO_ALTA` empezó a dispararse** (9.8 h con HR > 95 %). Nunca saltaba porque el
  aire jamás se humedecía. Es el modelo diciendo que el cuello de botella se movió: ya no es la
  transferencia, ahora es el **caudal**.
- **Un smoke de AppTest que renderiza la página no alcanza la vista de resultados.** El primer
  test del bloque de NTU pasaba sin ejercitar nada; hay que apretar el botón de cálculo.

---

## 5. Estado al cierre

- **Suite 1983 passed + 2 skips** (era 1910 + 2 al cierre de S62). Ruff, black y
  `auditar_i18n.py` limpios.
- **Nada commiteado.** `origin/main` sigue en `080eec7` (v1.4.0).
- **Corresponde bump de versión antes de liberar**: por el criterio de S62 —*si cambian los
  resultados, cambia la versión*— y acá cambian 11× en flujo vertical. Los reportes anteriores
  de secadores de flujo vertical **sobrestiman groseramente el tiempo de secado**.
- El usuario estaba probando en Streamlit mientras se implementaba; no llegó a reportar la
  corrida.

**Lo que queda abierto no es una etapa sino un límite del modelo:** no hay resistencia interna
a la difusión (`a_w` depende de `X` solo por GAB), y ahora que la resistencia externa dejó de
estar sobrestimada 182× es la que manda. El lote evapora sus 7.55 kg en una sola mañana, lo que
cierra energéticamente (18.5 MJ de latente contra ~23 MJ/día del colector), así que el tiempo
de secado es la **cota inferior**. Antes daba una cota superior errada 10×. La verdad está en el
medio y solo la fija una medición.

## Ver también

- [[docs/notas/plan_transferencia_camara]] — el plan, con la física del modelo y sus límites.
- [[docs/bitacora/bitacora_sesion62]] — §5, el análisis cuyo diagnóstico esta sesión corrige.
- [[docs/tareas]] — backlog al día.
- [[CHANGELOG]] — el `[Unreleased]` con todo lo de esta sesión.
