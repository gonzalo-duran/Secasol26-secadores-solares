# Plan — Percolación parcial en la cámara

**Estado:** PROPUESTA (S67, 2026-11-12). Nada implementado. Hay **cuatro decisiones del
usuario** pendientes (§3) antes de tocar código.

**Antecedentes:** [[docs/notas/plan_transferencia_camara]] (S63, introdujo el lecho atravesado),
[[docs/notas/plan_crossflow_unico_camara]] (S64, lo retiró; este plan es su §7.2),
[[docs/bitacora/bitacora_sesion67]] (el síntoma volvió a verse en la carta).

---

## 1. Por qué

El modelo de cámara está entre dos cotas y hoy usa la inferior:

| | S64 — todo el aire **rodea** | S63 — todo el aire **atraviesa** |
|---|---|---|
| área de intercambio | bandeja, dos caras (3.25 m²) | partícula (45.8 m², con el `d_sv` mal) |
| NTU del armario de referencia | 0.246 | 32.6 |
| aire de salida | seco (HR 16–28 %) | saturado |
| tiempo de secado | ~100 h | 13.55 h |
| sensibilidad a la masa cargada | casi nula | saturada |

En S67, con la carta ya corregida, el usuario volvió a ver el síntoma que había disparado S63:
**HR y ω de salida bajas, y que no responden a la masa ni al X final.** Es consecuencia directa
de la cota "todo rodea": el área no depende de cuánto producto hay.

La verdad está en el medio. El aire real se **reparte** entre atravesar el lecho y rodear la
bandeja, y ese reparto no es un dato que el usuario pueda declarar (criterio de S64): tiene que
ser un **resultado** de la geometría.

---

## 2. Física del modelo

### 2.1 Qué captura

**Topología.** Con la entrada abajo y la salida arriba (flujo global diagonal ascendente,
criterio de S64), todo el caudal tiene que subir un nivel de bandeja por vez. En cada nivel hay
dos caminos **en paralelo**:

- **Camino A — atravesar:** por el área de la bandeja, a través del lecho y la malla.
  `ΔP_A = Ergun(v_s, espesor, d_sv, ε) + K_malla·ρ·(v_s/f_abierta)²/2`, con
  `v_s = f·ṁ/(ρ·A_bandeja)`.
- **Camino B — rodear:** recorre el canal entre bandejas en horizontal y sube por el paso libre
  que deja la bandeja. `ΔP_B = ΔP_canal_crossflow(ṁ_B) + K_paso·ρ·v_paso²/2`, con
  `v_paso = (1−f)·ṁ/(ρ·A_paso)`. El primer término es el `_delta_P_producto_crossflow` que ya
  existe.

**Reparto.** `f` es la raíz de `ΔP_A(f) = ΔP_B(f)` (`brentq`, una incógnita, monótona). Se
supone igual en todos los niveles.

**Transferencia.** Cada corriente intercambia con su propia ley:

- la que atraviesa: área de partícula `a_v·V_lecho`, `a_v = 6(1−ε)/d_sv`, y `h` de lecho
  (Ranz-Marshall, con piso `Nu → 2`);
- la que rodea: lo que hay hoy (dos caras de bandeja, placa plana mixta, velocidad del canal),
  pero con el caudal `(1−f)·ṁ`.

Las dos corrientes se mezclan a la salida. Para **no tocar el motor** (`resolver_cadena_camara`
recibe una sola conductancia) se le pasa la conductancia **equivalente** que reproduce la
efectividad mezclada `E = f·E_A + (1−f)·E_B`. Chilton-Colburn se conserva, así que el producto
sigue parándose en el bulbo húmedo.

**Hidráulica del lazo.** El ΔP de la cámara pasa de ≈ 0 a `n_niveles × ΔP_nivel`, y entra al
balance de tiro de los pasivos y al ΔP del ventilador.

### 2.2 Qué NO captura

- **Resistencia interna a la difusión.** Sigue sin existir. Al subir la transferencia externa,
  vuelve a ser el límite dominante: el tiempo de secado sigue siendo una **cota inferior**, y
  más ajustada a la energía disponible que hoy.
- **Frente de secado dentro del lecho.** El producto es un solo estado `[T_prod, X_prod]`: no
  hay bandejas de abajo secándose antes que las de arriba.
- **Canalización.** El aire real busca los huecos del lecho; Ergun supone lecho uniforme.
- **Bocas con pleno distribuidor.** Si la entrada y la salida reparten el aire en toda la altura
  (armario de bandejas forzado con plenos laterales), no hay diferencia de presión entre caras
  de la bandeja y el flujo es cross-flow puro. El modelo propuesto lo representa solo como caso
  límite (paso libre grande ⇒ `f → 0`), no como topología aparte.
- **Empuje solutal** en la cara inferior: sigue el factor fijo 0.5 de S64 para la corriente que
  rodea.

### 2.3 Límites de validez

- **Monocapa.** Ergun vale para lechos de varias capas de partícula. Los siete snapshots del
  repo tienen 0.6–0.9 cm de capa con rodajas de 6 mm: es **una capa y media**. Ahí el "lecho" es
  más una placa perforada por los huecos entre rodajas que un medio poroso. Ver decisión §3.3.
- **Caudal nulo.** `Nu → 2` sostiene `h` cuando `v_s → 0`; con NTU muy alto el resultado deja de
  depender de la correlación (el problema 1.3 de S64). El diagnóstico tiene que decirlo.
- **Rayleigh-Darcy.** La convección natural dentro del lecho se desprecia; S64 lo auditó con
  margen 40× para capas de 2 cm, pero una capa de 10 cm de trozos grandes ya no lo cumple.

---

## 3. Decisiones que necesita el usuario

### 3.1 Qué es el "paso libre" que rodea la bandeja

Es el parámetro que más mueve el resultado (tabla de §4) y hoy **no existe** en el modelo de
datos. Opciones:

- **(a) Holgura perimetral** [cm] entre bandeja y pared, con default (propuesto: 1 cm), más la
  diferencia `huella − área_bandeja` que ya se conoce. *Recomendada:* es un dato constructivo
  que el usuario sabe.
- **(b) Solo `huella − área_bandeja`**, sin dato nuevo. En el armario de referencia la bandeja
  cubre toda la huella (0.25 m² de 0.25 m²), así que daría `f = 1`: lecho atravesado puro.
- **(c) Fracción de paso libre** [%] como dato directo.

### 3.2 Alcance por tipología

¿Aplica a CAJA, ARMARIO y GRAN_ESCALA por igual? En el túnel industrial el aire entra
horizontal y forzado entre carros: el paso libre es enorme y `f` debería salir ≈ 0 solo. Falta
confirmar que eso es lo que se quiere, o excluir el túnel explícitamente.

### 3.3 Régimen de monocapa

- **(a)** Usar Ergun siempre y avisar con una advertencia cuando `espesor < 3·d_p`.
- **(b)** Tratar la monocapa como placa perforada (pérdida por área abierta entre partículas).
  Más correcto, pero agrega un segundo modelo y una transición.

*Recomendada:* (a) en este plan, (b) como trabajo posterior si una medición lo pide.

### 3.4 Geometría de partícula en el catálogo

El `d_sv` hay que arreglarlo sí o sí (prerequisito declarado en S64). Propuesta: que el catálogo
declare la **forma** (rodaja: diámetro y espesor; cubo: lado; esfera; cilindro) y `d_sv` se
**derive** (`rodaja: 3·D·e/(D+2e)`), en vez de un número suelto. `diametro_eq_m` queda como
rugosidad del canal, que es su único uso vivo. ¿De acuerdo, y con qué diámetros de rodaja por
producto? (Para manzana se usó D = 50 mm, e = 6 mm ⇒ `d_sv` = 14.5 mm.)

---

## 4. Órdenes de magnitud (prototipo, no es código del repo)

Armario de referencia (10 bandejas de 0.25 m², manzana, `d_sv` 14.5 mm, ε 0.45), correlaciones
de manual, propiedades constantes. **Son estimaciones para decidir, no resultados del modelo.**

| caso | espesor | fracción que atraviesa | ΔP cámara | acercamiento a saturación |
|---|---|---|---|---|
| forzado 34 g/s, holgura 1 cm | 0.82 cm | 81 % | 1.5 Pa | 82 % (S64: 15–20 %) |
| holgura 0.5 cm | 0.82 cm | 90 % | 1.7 Pa | 86 % |
| holgura 2 cm | 0.82 cm | 68 % | 1.1 Pa | 73 % |
| holgura 4 cm | 0.82 cm | 50 % | 0.7 Pa | 59 % |
| masa 3 kg | 0.26 cm | 87 % | 0.7 Pa | 50 % |
| masa 20 kg | 1.73 cm | 75 % | 2.5 Pa | 85 % |
| masa 40 kg | 3.46 cm | 69 % | 4.1 Pa | 79 % |
| pasivo 6 g/s | 0.82 cm | 73 % | 0.10 Pa | 98 % |
| pasivo 12 g/s | 0.82 cm | 77 % | 0.26 Pa | 95 % |

Lecturas:

- **El aire de salida vuelve a acercarse a saturación** en el armario indirecto, sin llegar al
  100 % de S63.
- **La masa vuelve a importar:** 50 % de acercamiento con 3 kg, 85 % con 20 kg.
- **El pasivo deja de ser imposible.** Con el `d_sv` correcto y el espesor derivado (0.8 cm, no
  los 2 cm declarados), atravesar las diez bandejas cuesta 0.1–0.3 Pa contra ~1.3 Pa de tiro.
  Los 31 Pa de S63 venían de los dos errores juntos.
- **La holgura es la perilla sensible:** de 0.5 a 4 cm el acercamiento va de 86 % a 59 %.

---

## 5. Etapas

### Etapa 1 — Geometría de partícula (`core/lecho.py`, catálogos)

- Formas en `forma_geometrica` de los productos que hoy la tienen; `diametro_sauter_m(producto)`
  derivado. `Φ_s` deja de ser vestigial o se retira.
- Tests: `d_sv` de rodaja, cubo y esfera contra la fórmula; paridad de catálogo.
- **No cambia ningún resultado** (nadie consume `d_sv` todavía).

### Etapa 2 — Hidráulica del reparto (`calculos/`, módulo nuevo `percolacion_camara.py`)

- `ΔP_lecho` (Ergun + malla), `ΔP_rodeo` (canal + paso), `fraccion_percolacion(...)` por
  `brentq`. Módulo puro, sin dependencias de UI.
- Campo nuevo según §3.1 (en `ConfiguracionBandejas`, con default y back-compat de snapshots).
- `estimar_delta_P_camara` devuelve el ΔP del conjunto; verificar que el Picard del lazo
  natural sigue convergiendo.
- Tests: `f → 0` con paso libre grande, `f → 1` con paso nulo, monotonía con holgura, masa y
  caudal; ΔP igual por los dos caminos en la solución.

### Etapa 3 — Transferencia (`calculos/camara_calc.py`)

- `h` y área de lecho para la corriente que atraviesa; conductancia equivalente en el closure
  `coef_transporte_func`. El motor (`camara_termodinamica.py`) **no se toca**.
- `f` se reevalúa por paso (depende de `ṁ(t)` y de las propiedades), igual que `h` hoy.
- Tests: **con `f = 0` reproduce S64 al decimal**; con `f = 1` y `d_sv` de S63 reproduce el
  orden de S63; el balance de entalpía del aire sigue cerrando (test de S67).

### Etapa 4 — Diagnóstico, UI e i18n

- `diagnostico_transferencia` en P4: fracción que atraviesa, NTU de cada corriente, ΔP de
  cámara, y el régimen en palabras.
- Advertencias: monocapa (§3.3), NTU saturado (resultado insensible al modelo), y la de
  bypass si el paso libre domina.
- Widget del paso libre en P4 → bandejas. Tres idiomas. Capítulos del manual de cámara y de
  referencia técnica.
- `docs/mapa_conexiones.md`.

### Etapa 5 — Verificación sobre los proyectos del usuario

- Los siete snapshots: cargan, calculan, y tabla antes/después (NTU, HR de salida, tiempo de
  secado, ΔP, caudal natural en los pasivos).
- **Lazo evaporación → tiro** (pendiente §7.3 de S64): con NTU alto el aire sale frío y el tiro
  cae. Confirmar que el Picard converge y que el caudal no colapsa.
- Carta psicrométrica en Constantes: el tramo de cámara tiene que seguir la isentálpica y
  terminar más cerca de saturación.
- Barrido de masa y de holgura, para ver que el modelo **discrimina diseños** (el criterio que
  S63 no cumplía).
- Anclaje del extractor de 76 W: revisar si el ΔP de cámara cambia la lectura.

### Etapa 6 — Cierre

Bitácora, CHANGELOG, `docs/tareas.md`, ADR nuevo (la topología de la cámara cambia por tercera
vez: dejar escrito por qué esta es la que queda). **Cambian todos los proyectos ⇒ bump de
versión**, junto con S63, S64 y S67.

---

## 6. Riesgos

1. **Un parámetro nuevo que manda.** La holgura mueve el resultado tanto como cualquier otra
   variable de diseño y nadie la midió. Mitigación: default conservador, barrido disponible, y
   el diagnóstico de P4 mostrando `f`.
2. **Volver a la saturación.** Si `f` resulta alto en todos los casos, el modelo vuelve a no
   discriminar (S63). El prototipo sugiere que no (50–86 % de acercamiento en forzado), pero
   los pasivos dan 95–98 %. Hay que mirarlo en la etapa 5 antes de dar el plan por bueno.
3. **Tiempo de secado todavía más optimista.** Sin difusión interna, mejorar la transferencia
   externa acerca el resultado a la cota de energía. Conviene decidir si el modelo de difusión
   interna va **antes** de liberar esto.
4. **Sin validación.** Sigue siendo el pendiente número uno. Una HR o temperatura de salida
   medida en un armario cargado alcanzaría para calibrar la holgura efectiva.
5. **El código de transferencia de S63 no está en git.** S63 y S64 se commitearon juntos
   (`9a87097`), así que Ranz-Marshall y el área específica hay que reescribirlos; Ergun sí
   sobrevive en `v1.4.0` (`calculos/motor_calc.py`).

---

## Ver también

- [[docs/notas/plan_crossflow_unico_camara]] — §1 (el `d_sv`), §7.2 (el origen de este plan).
- [[docs/notas/resultado_crossflow_unico_camara]]
- [[docs/bitacora/bitacora_sesion63]] · [[docs/bitacora/bitacora_sesion64]] ·
  [[docs/bitacora/bitacora_sesion67]]
- [[docs/tareas]]
