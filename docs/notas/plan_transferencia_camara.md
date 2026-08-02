# Plan — topología de transferencia de calor y masa en la cámara

**Origen:** S63. El usuario observa que en la carta psicrométrica de un secador
**indirecto** (cámara opaca, bien aislada, sin auxiliar) el aire de salida no cae sobre la
adiabática de saturación y sale con HR muy baja, cuando la teoría del secador indirecto dice
que el proceso en cámara es calentamiento sensible en colector + **enfriamiento evaporativo
casi adiabático** en cámara.

**Caso de referencia:** `tests/armario indirecto forzado/` — armario 0.5×0.5×1.1 m, cámara
opaca (U_pared 0.80 W/m²K), colector 2×(2.5×1.0) m, ventilador, 9.5 kg de manzana en
10 bandejas de 0.25 m² con capa de 2 cm, flujo **VERTICAL_ASCENDENTE** de 0.0342 kg/s,
ventana 20–27/04/2010, Salta (1187 m, P = 89 202 Pa). Reproducible al decimal desde el
snapshot `.json` + `obtener_clima`.

---

## 1. Diagnóstico

Son **tres problemas apilados**. Solo el primero es lo que se ve en la carta; el segundo es
la buena noticia; el tercero es el que importa.

### 1.1 La carta psicrométrica compara dos instantes distintos (bug)

`calculos/carta_psicrometrica.py` elige el punto representativo con dos criterios que no
comparten base temporal:

- entrada: `_idx_repr_forzantes` → `argmax(POA)` sobre **todo el horizonte** → hora 157
- salida: `_idx_camara_en_tiempo` → punto más cercano de la trayectoria de cámara, que
  **termina cuando el producto alcanza X_obj** → hora 154.01

Desfasaje **3 h**. Lo que se dibuja:

| estado | T | ω | HR |
|---|---|---|---|
| Entrada cámara (h 157) | 51.96 °C | 4.061 g/kg | 4.3 % |
| Salida cámara (h 154) | 33.51 °C | **3.486 g/kg** | 9.6 % |

Δh = **−20.2 kJ/kg** y ω **decrece**: el aire aparece secándose al atravesar el secador, que
es imposible sin condensación. Además `argmax(POA)` sobre una ventana de 7 días cae casi
siempre en el **último** día, cuando el producto ya está seco — el instante menos
representativo del proceso.

**Por qué apareció recién ahora:** el desfasaje exige `t_secado < t(POA máx)`, o sea que el
horizonte sobreviva al lote. Con horizontes de 24 h que no terminan el secado, la trayectoria
de cámara cubre todo el horizonte y los índices coinciden. Se hizo visible con las **ventanas
multidía** (VENTANA para CAJA/ARMARIO, S44), no por un cambio de física.

### 1.2 El balance de cámara es correcto — y sí sigue la adiabática

Alineando los instantes (interpolando forzantes a la base temporal de la cámara), el residuo
del balance de energía del aire es **5×10⁻¹² W**. No hay término perdido ni doble conteo: el
vapor entra al aire con `h_v(T_prod)` y el calor latente sale del nodo del producto, que es la
formulación correcta.

En el pico del **día 1**, con producto húmedo (X = 4.17):

```
T_ent 51.53 °C, ω 5.78 g/kg  →  T_out 45.64 °C, ω 7.59 g/kg
Δh = −1.29 kJ/kg           contra 6 kJ/kg de enfriamiento sensible
ṁ·Δh = −44.28 W = −37.64 (pérdida de pared) − 6.64 (inercia térmica del producto)
T_prod = 20.48 °C          vs  T_bulbo húmedo = 21.10 °C   →  0.6 K
```

El producto se para en el bulbo húmedo y **todo** el desvío de la adiabática se explica por la
pared más la inercia del producto. La relación de Lewis (`K_m = h/(cp·Le^{2/3})`) está bien
implementada. Durante el secado activo el motor hace la física esperada.

### 1.3 El problema real: NTU = 0.19 — la topología de transferencia

```
A_prod = n_bandejas × área_bandeja = 2.5 m²      ← la huella, nada más
h_conv = 2.53 W/m²K                              ← placa plana externa, v = 0.137 m/s
NTU = K_m·A_prod/ṁ = 0.19  →  el aire recorre el 15 % del camino al equilibrio
```

**Incoherencia estructural del proyecto:**

> Para la **pérdida de carga**, `calculos/motor_calc.py` sabe que el producto es un lecho
> empacado: usa Ergun con `porosidad_lecho`, `diametro_eq_particula_m` y `esfericidad`, y
> distingue VERTICAL (el aire atraviesa el lecho) de HORIZONTAL (cross-flow entre bandejas en
> paralelo).
>
> Para **calor y masa**, `calculos/camara_calc.py` trata al mismo producto como una placa
> plana lisa del tamaño de la bandeja, con **una sola topología hardcodeada**, ignorando
> `direccion_flujo`, el espesor de capa, la porosidad y el tamaño de partícula.

Los tres campos del lecho existen en el data model y **no entran jamás** al transporte. El
catálogo de productos ya trae `forma_geometrica` (rotulado *"para Ergun"*) con los datos
necesarios.

En este secador las bandejas ocupan el **100 % de la huella** con flujo vertical: el aire no
tiene por dónde pasar que no sea a través del lecho. Con los datos del catálogo de manzana
(d_eq = 6 mm, ε = 0.45, Φ = 0.6):

| | modelo actual | lecho atravesado |
|---|---|---|
| Área de transferencia | 2.5 m² (huella) | **45.8 m²** (`a_v = 917 m²/m³`) → ×18.3 |
| h | 2.53 W/m²K (placa) | **25.1 W/m²K** (Ranz-Marshall, Re_p = 44) → ×9.9 |
| **h·A** | — | **×182** |
| NTU | 0.19 | **34.5** |

### 1.4 Verificación: barrido de h·A

Escalar `h_conv` preserva Chilton-Colburn (y por lo tanto el bulbo húmedo) y equivale a
escalar el área en el álgebra, porque ambos entran como `h·A` y `K_m·A`:

| factor | NTU | t_secado | T_out | HR_out | Δh [kJ/kg] | T_prod − T_wb |
|---|---|---|---|---|---|---|
| **×1 (hoy)** | 0.19 | **154 h** | 45.6 °C | **10.8 %** | −1.29 | −0.62 K |
| ×3 | 0.56 | 60 h | 39.9 °C | 19.4 % | −0.67 | −0.13 K |
| ×10 | 1.87 | 34.8 h | 31.5 °C | 41.7 % | +0.09 | +0.06 K |
| ×30 | 5.6 | **14.7 h** | 25.8 °C | 68.4 % | +0.60 | +0.17 K |
| ×100 | 18.7 | 13.9 h | 22.9 °C | **88.0 %** | +0.86 | +0.22 K |
| ×182 (lecho) | 34.5 | ~13.7 h | ~22 °C | **~94 %** | +0.8 | +0.3 K |

El motor converge exactamente a la teoría: aire saliendo saturado **sobre la adiabática**,
producto clavado en el bulbo húmedo (±0.34 K). El Δh se vuelve **positivo** porque a NTU alto
el aire sale por debajo de la ambiente y la pared aporta calor en vez de perderlo —
enfriamiento evaporativo de manual.

**Consecuencia:** el secador pasa de estar *limitado por transferencia* (154 h) a estar
*limitado por energía* (~14 h, consistente con el balance: 18.5 MJ de agua contra ~23 MJ/día
de colector). El diagnóstico de S62 §5 —*"desbalanceado, 73 % de la energía se va con el aire
de salida, usa el 4 % de su capacidad"*— **es un artefacto del modelo de transferencia, no una
propiedad del diseño**: con el área del lecho el aire sale a ~22 °C y el escape casi no pierde.

### 1.5 Problemas secundarios de la misma familia

1. **`aprovechamiento_aire` usa la capacidad isotérmica** (`simulacion_anual.py`):
   `ω_sat(T_ent) − ω_ent` = 110 g/kg a 51 °C. El techo termodinámico real de una cámara
   adiabática es `ω_sat(T_wb) − ω_ent` = **12.8 g/kg**. El denominador es ~8× lo alcanzable,
   así que *todo* secador da catastrófico.
2. **La velocidad de transferencia contradice a la de ΔP.** En HORIZONTAL,
   `area_transversal_flujo_m2` da `ancho×alto` = 0.55 m²; `motor_calc` usa
   `ancho×espacio_libre×(n−1)` = 0.315 m². Dos velocidades para el mismo aire.
3. **El film del producto se evalúa con `T_ent`, no con `T_flujo`**
   (`camara_termodinamica.py:733`): es el mismo bug que S62 arregló para el film de **pared** y
   que quedó sin arreglar para el **producto**. Acá pesa ~4 % (rama débil, Nu ~ Ra^{1/5}); en
   CAJA, donde `T_ent = T_amb`, puede pesar más.
4. **`balance_global.py:1997`**: `HR_desde_omega(ω, T)` sin `P_Pa` → usa 101 325 Pa donde el
   proyecto tiene 89 202. Solo afecta coeficientes de referencia, pero es la misma clase de
   descuido.
5. **El CSTR no puede saturar por construcción**: aproximación `NTU/(1+NTU)` contra
   `1−exp(−NTU)` de flujo pistón. A NTU = 2 son 67 % vs 86 %. Con 10 bandejas en serie el
   arreglo real es escalonado. Irrelevante a NTU = 0.19; relevante una vez corregido §1.3.

---

## 2. Física del modelo

Qué captura el modelo propuesto, qué no, y dónde están sus límites.

### 2.1 Qué captura

- **Through-flow (VERTICAL_ASCENDENTE)**: el aire atraviesa la capa de producto. Área de
  transferencia = superficie de las partículas, `A = a_v·V_lecho` con
  `a_v = 6(1−ε)/(Φ_s·d_p)` (área específica de un lecho de partículas no esféricas,
  Geankoplis/Ergun — la misma definición que sostiene el término viscoso de Ergun). h por
  **Ranz-Marshall**, `Nu_p = 2 + 0.6·Re_p^{1/2}·Pr^{1/3}`, con `Re_p = G·d_p/μ` y
  `G = ṁ/A_sección` (velocidad superficial, no intersticial). Límite inferior `Nu_p → 2`:
  conducción pura a partícula aislada, que es el piso físico correcto a caudal nulo.
- **Over-flow (HORIZONTAL)**: el aire pasa **entre** bandejas. Área = área de bandeja
  (superficie libre del lecho), h por placa plana con la velocidad **del canal**
  `v = Q/(ancho·espacio_libre·(n−1))`, la misma que usa `motor_calc` para ΔP.
- La relación de Chilton-Colburn se preserva en ambos casos (`K_m = h/(cp·Le^{2/3})`), que es
  lo que garantiza que el producto se pare en el bulbo húmedo y que el aire siga la adiabática
  cuando la cámara es adiabática. **Esto ya funciona y no hay que tocarlo.**

### 2.2 Qué NO captura

- **Gradientes internos de la partícula — ahora es la limitación dominante.** El modelo sigue
  siendo de resistencia externa controlante, con `a_w` de la isoterma GAB en la superficie: la
  difusión interna solo aparece a través de `a_w(X)`. Mientras la resistencia externa estaba
  sobrestimada 182×, esta aproximación quedaba **enmascarada**; al corregirla queda a la vista.

  Medido tras la etapa 1: el lote de 9.5 kg evapora sus 7.55 kg de agua en **una sola mañana**
  (t_secado 13.7 h, con todo el secado entre las 8 y las 13:40 del día 1). Energéticamente
  cierra —18.5 MJ de calor latente contra ~23 MJ/día que entrega el colector, posible solo
  porque el aire ahora sale casi saturado y el escape casi no pierde—, así que **es la cota
  inferior correcta**: el secado limitado por energía. Un secador real es más lento porque la
  difusión interna manda en el período decreciente.

  **Cómo leer el resultado hoy:** el tiempo de secado que da el modelo es una **cota
  inferior**. Antes daba una cota superior equivocada por un factor 10. La verdad está en el
  medio y solo la puede fijar una medición (mejora 38 fase 4) o un modelo de difusión interna.
- **Distribución no uniforme del flujo entre bandejas.** Se supone que las N bandejas ven el
  mismo caudal. En through-flow real, el lecho de arriba recibe aire ya humedecido y las
  diferencias de compactación desvían caudal. Se cubre parcialmente con la etapa 4 (N etapas
  en serie), no con la 1.
- **Encogimiento del producto.** `ε`, `d_p` y `V_lecho` se mantienen constantes durante el
  secado. La manzana pierde ~80 % de su masa: el lecho se compacta y `a_v` sube mientras la
  permeabilidad baja. Efecto de segundo orden frente al ×182, pero es un límite declarado.
- **La malla de la bandeja.** `tipo_malla` no entra: no se modela ni la fracción de área que
  obstruye ni su resistencia. En through-flow con malla muy cerrada el área efectiva es menor
  que `a_v·V_lecho`.
- **El CSTR** (mientras no se haga la etapa 4): un tanque perfectamente mezclado no puede
  alcanzar saturación por construcción. A NTU = 34 la diferencia con flujo pistón es
  despreciable (97.7 % vs ~100 %), pero en el rango de diseño interesante (NTU 1–5) el CSTR
  **subestima** el aprovechamiento del aire.

### 2.3 Límites de validez declarados

- Ranz-Marshall se calibró para `Re_p` de ~1 a 10⁴ sobre esferas. Con rodajas planas
  (Φ_s = 0.6) la esfericidad corrige la geometría de forma aproximada, igual que en Ergun. Es
  el mismo compromiso que el proyecto ya aceptó para ΔP.
- `d_eq` de las rodajas está anotado en el catálogo como *"validar con medición si es
  crítico"*: se toma la dimensión normal al flujo (el espesor, ~6 mm) y no el diámetro de la
  esfera equivalente en volumen (~16 mm). Ese factor 2.7 en `d_p` mueve `a_v` y `Re_p` en
  sentidos opuestos, así que el efecto neto sobre NTU es moderado — pero **es la incerteza
  dominante del modelo nuevo** y hay que decirlo en la UI.
- Nada de esto está contrastado contra mediciones. Vale la advertencia general del work stream
  de convección natural: es coherencia interna, no validación.

---

## 3. Etapas

### Etapa 0 — la carta deja de mentir (aislada, sin tocar física) ✅ **HECHA (S63)**

- `calculos/carta_psicrometrica.py`: `_instante_representativo(camara, forzantes)` reemplaza a
  `_idx_repr_forzantes`. El instante lo fija **la cámara** (máxima evaporación, la misma regla
  que ya usaba Constantes; por construcción nunca cae en la cola con el producto seco) y las
  forzantes se **interpolan** ahí con `_forzante_en_tiempo`. Fallback: POA máxima **restringida
  al rango que la cámara simuló** — restringir el rango es lo que evita el desfasaje aunque no
  haya `ṁ_w`. `_serie()` normaliza atributos ausentes, porque
  `np.asarray(None, dtype=float)` devuelve un array 0-d de tamaño 1 en vez de fallar.
- `estados_proceso` devuelve `t_repr_s`; `ui/componentes/carta_psicrometrica.py` lo rotula con
  fecha y hora **locales** (`t0_utc` + zona horaria del sitio), con la hora del horizonte como
  fallback. Claves `graficas.carta.instante_fecha` / `instante_hora` en ES/EN/PT.
- Tests: `test_lote_que_termina_antes_del_horizonte_no_desalinea_los_estados` (verificado que
  **falla** con la regla anterior: Δω = −1.17 g/kg), `test_instante_representativo_es_el_de_
  maxima_evaporacion` y `test_sin_evaporacion_cae_a_poa_dentro_de_la_trayectoria`.

**Medido en el caso de referencia:** desfasaje 2.99 h → 0.00 h; Δω = −0.58 → **+1.86 g/kg**;
Δh = −20.17 → **−1.19 kJ/kg**; instante rotulado 24/04 13:11. Suite 1913 passed + 2 skips.
**No cambia ningún resultado del balance** — era la lectura, no el cálculo.

### Etapa 1 — topología de transferencia (el corazón) ✅ **HECHA (S63)**

- **Nuevo módulo `calculos/lecho_producto.py`** (puro): `geometria_lecho` **movido desde
  `motor_calc._geometria_lecho`** (que queda como alias) para que haya una sola fuente de
  verdad, más `area_especifica_lecho_m2_m3`, `volumen_lecho_m3`, `area_transferencia_lecho_m2`,
  `h_conv_lecho` (Ranz-Marshall), `d_p_es_default` y `masa_que_llena_el_lecho_kg`.
- `calculos/camara_calc.py`: `_construir_params_termodinamico` decide topología con
  `es_flujo_atravesado(camara)`:
  - `VERTICAL_ASCENDENTE` → `A_prod = a_v·V_lecho`, h de lecho empacado sobre la velocidad
    másica superficial `G = ṁ/A_sección`.
  - `HORIZONTAL` → `A_prod = n·área_bandeja`, h de placa plana con la velocidad del canal
    (`area_canal_entre_bandejas_m2`, la misma sección que usa `motor_calc`).
- La convección natural (mixta) se mantiene **solo** en over-flow: dentro del lecho el empuje
  no tiene escala libre y el piso `Nu_p → 2` de Ranz-Marshall ya sostiene el coeficiente a
  caudal nulo, que era el motivo de tener la rama natural.
- Advertencias: `CAM_LECHO_BYPASS`, `CAM_LECHO_D_P_DEFAULT`, `CAM_LECHO_CARGA_INCOHERENTE`,
  `CAM_LECHO_DEGENERADO`.

**Corrección sobre el plan original:** la advertencia planificada era "bandejas que ocupan
≥ 90 % de la sección con flujo HORIZONTAL (geometría imposible)". Está mal: bandejas que llenan
la huella con flujo horizontal es **el armario de bandejas clásico** — el aire pasa por los
canales entre bandejas, no a través de ellas. La geometría problemática es la **opuesta**:
flujo vertical con bandejas que **no** cubren la huella, porque entonces parte del aire esquiva
el lecho por el perímetro mientras el modelo supone que lo atraviesa todo. Esa es la que quedó
implementada (`CAM_LECHO_BYPASS`).

**Medido en el caso de referencia** (armario indirecto forzado, flujo vertical):

| | antes | ahora |
|---|---|---|
| A_prod | 2.5 m² | **45.8 m²** |
| h | 2.5 W/m²K | **24.7 W/m²K** |
| NTU | 0.19 | **31.8** |
| HR de salida en el pico | 10.8 % | **92.8 %** |
| Δh entrada→salida | −1.3 kJ/kg | **+0.9 kJ/kg** |
| T_prod − T_bulbo húmedo | −0.6 K | **+0.3 K** |
| t_secado | 154 h | **13.7 h** |

Suite **1941 passed + 2 skips** (+28 tests nuevos en
`tests/test_calculos/test_topologia_transferencia_camara.py`). Ruff, black e i18n limpios.

**Hallazgo colateral:** la suite entera pasaba **sin un solo cambio** después de mover el
resultado 11×. Ningún test fijaba el tiempo de secado de una cámara de flujo vertical: el
número más visible del proyecto no estaba cubierto. Los tests nuevos lo cubren.

### Etapa 2 — coherencia de velocidad y films ✅ **HECHA (S63)**

- La unificación de la sección de paso (§1.5.2) entró con la etapa 1
  (`area_canal_entre_bandejas_m2`).
- **`T_flujo` al film del producto** (§1.5.3): `simular_secado._resolver` y
  `simular_cascada._resolver_zona` resuelven dos veces por paso —estimación con `T_ent`,
  refinación con `T_flujo`— y en esa segunda pasada recalculan **los dos** films, el de pared
  (que ya lo hacía desde S62) y el del producto. Con coeficientes congelados se hace una sola
  pasada: back-compat exacta. El primer argumento de `coef_transporte_func` pasa a ser
  `T_aire_camara_K`.

  **Medido:** en over-flow, donde el empuje entra en el Nusselt, evaluar con `T_ent`
  sobrestimaba `h` **1.92× a 0.02 m/s**, 1.41× a 0.1 m/s y 1.01× a 1 m/s. O sea: pesa en el
  secador **pasivo**, que es justo el que S61/S62 estaban arreglando. En el armario forzado de
  referencia el efecto es de tercer orden (13.72 → 13.73 h).

- **`P_Pa` en `HR_op`** (§1.5.4): `balance_global.py` usaba 101 325 Pa; a 1187 m la HR de
  referencia salía ~12 % baja.

Suite **1943 passed + 2 skips**.

### Etapa 3 — métricas honestas ✅ **HECHA (S63)**

- `aprovechamiento_aire` pasa a medirse contra la capacidad **adiabática**
  `ω_sat(T_wb) − ω_ent`, el único techo alcanzable. Con el isotérmico daba ~8 veces peor de lo
  posible y todo secador se reportaba catastrófico.
- **`temperatura_bulbo_humedo` funciona con aire sobre la ebullición local.** El chequeo de
  saturación se hacía en el bulbo **seco** y a 73 kPa (2650 m, ebullición a 91 °C) lanzaba
  `PSICRO_PV_EXCEDE_P`. Ese aire no puede estar saturado —hervir es otra cosa— pero **sí**
  tiene saturación adiabática. Ahora el bracket se acota a la ebullición: el caso que el
  usuario reportó en S57 pasa de quedar **excluido** del indicador a evaluarse (T_wb = 28.5 °C,
  capacidad 27 g/kg). Se suma `temperatura_ebullicion(P_Pa)`, inversión numérica de Buck (a
  101.325 kPa da 100.00 °C).
- **NTU expuesto en P4**: `diagnostico_transferencia` (puro) + bloque en la vista de resultados
  con superficie, h, NTU, acercamiento al equilibrio y el **régimen en palabras** (limitado por
  transferencia / intermedio / limitado por energía). Armario de referencia: NTU 32.6 en
  vertical (97 % de acercamiento) contra 0.19 en horizontal (16 %).

**Nota sobre el smoke de P4:** el bloque vive en la vista de **resultados**, así que un
`AppTest` que solo renderiza la página no lo alcanza —verificado— y no guardaría nada. El test
aprieta el botón de cálculo y después comprueba que las métricas estén.

Suite **1959 passed + 2 skips**.

### Etapa 4 — el aire como cadena de etapas ✅ **HECHA (S63)**

`resolver_cadena_camara` parte el camino del aire en N sub-etapas, cada una el mismo solve
algebraico exacto con 1/N de las áreas y el aire de la anterior como entrada. **Con N = 1
reproduce el CSTR exactamente**, así que la back-compat es literal.

**Corrección sobre el plan original.** El plan decía "N etapas en serie (una por bandeja)" y
proponía reusar `simular_cascada`. Dos desvíos:

1. **"Una por bandeja" solo vale en flujo vertical.** `motor_calc` ya lo tenía resuelto para la
   pérdida de carga: en VERTICAL el ΔP se multiplica por `n_bandejas` (el aire cruza una tras
   otra, **en serie**), y en HORIZONTAL los canales van **en paralelo** —el ΔP del sistema es el
   de un canal—, así que agregar bandejas no agrega etapas en serie. Lo que se discretiza en
   over-flow es el **largo del canal**, que es un intercambiador continuo. De ahí
   `n_etapas = n_bandejas` (atravesado) contra `_N_ETAPAS_OVERFLOW = 8`.
2. **No se reusó `simular_cascada`.** Aquella resuelve N zonas con **su propio estado de
   producto cada una** (2N EDOs) y aire a contracorriente: es la topología del túnel. Acá el
   producto sigue siendo **uno solo** y lo que se estratifica es el aire, así que alcanza con
   encadenar el solve algebraico dentro del RHS. El sistema de EDOs no cambia y el contrato del
   resultado tampoco.

**Convergencia medida** (acercamiento al equilibrio, ω):

| NTU | N=1 (CSTR) | N=2 | N=8 | N=32 | N=128 | pistón `1−e^{−NTU}` |
|---|---|---|---|---|---|---|
| 0.2 | 16.67 % | 17.36 % | 17.93 % | 18.08 % | 18.11 % | **18.13 %** |
| 1.0 | 50.00 % | 55.56 % | 61.03 % | 62.64 % | 63.07 % | **63.21 %** |
| 2.0 | 66.67 % | 75.00 % | 83.22 % | 85.63 % | 86.26 % | **86.47 %** |
| 5.0 | 83.33 % | 91.84 % | 97.94 % | 99.04 % | 99.26 % | **99.33 %** |
| 32 | 96.97 % | 99.65 % | 100.00 % | 100.00 % | 100.00 % | **100.00 %** |

Quedar un poco corto del pistón perfecto con N = 8 es **deliberado**, no solo barato: el pistón
también es una idealización —una cámara real tiene mezcla axial—, así que la verdad está entre
el CSTR y el pistón.

**Efecto en el caso de referencia:** t_secado 13.73 → **13.55 h**, y el aire de salida pasa de
92.6 % a **100 % de HR** — saturado sobre la adiabática, que es lo que la teoría predice para
un secador indirecto bien acoplado. Chico, como corresponde a NTU = 32; la etapa paga donde el
secador está mal cargado.

**Gotcha del set point (regresión encontrada por la suite).** Al partir la cámara en etapas,
dejar que cada una modulara su propia potencia auxiliar daba **un controlador por tramo**: el
primero, que ve el aire frío de entrada, encendía siempre aunque el sol ya hubiera superado la
consigna aguas abajo, y la resistencia no se apagaba nunca. Un termostato mide el aire de la
cámara y gobierna **una sola** potencia. Como cada etapa es afín en su potencia y la
composición también, la potencia total se despeja con dos evaluaciones de la cadena (Q = 0 y
Q = Q_max) más una final — sin iterar, igual que el despeje algebraico de una sola etapa.

**De yapa:** la pérdida de pared queda mejor calculada, porque cada tramo pierde con **su**
temperatura en vez de con una sola para toda la cámara. `estimar_T_flujo_estacionario` (el
punto de diseño que alimenta el tiro térmico) usa la misma cadena, para no estimar con un
modelo distinto del que después simula. **Costo:** el transitorio de 7 días del armario pasa de
0.1 s a 0.4 s.

---

## 4. Regresiones esperadas

- **Todo proyecto con `VERTICAL_ASCENDENTE` cambia de resultado**, y mucho: en el caso de
  referencia el tiempo de secado cae 11× (154 h → 13.7 h). Cambian en cascada la producción
  anual, la fracción solar, el COP, η_drying y la energía específica.
- Los proyectos HORIZONTAL cambian por la velocidad del canal (sección 2.4× menor en el caso
  de referencia ⇒ h ~1.6× mayor).
- **Ningún test existente cambió de valor** (suite verde sin tocar un solo assert), lo que en
  sí es el hallazgo: no había cobertura del tiempo de secado en flujo vertical.
- Por el criterio adoptado en S62 (*si cambian los resultados, cambia la versión*), esto es un
  **bump menor como mínimo**, con nota destacada en el CHANGELOG: los reportes anteriores de
  secadores de flujo vertical **sobrestiman groseramente el tiempo de secado**.

---

## 5. Decisiones tomadas

- **Correlación de through-flow: Ranz-Marshall** sobre el área específica de partícula
  (S63, usuario). Alternativas descartadas: j-factor de Colburn (da ~15 W/m²K, también satura)
  y "área de lecho con h de placa y factor de forma" (deja la física como perilla).
- **Alcance: topología según `direccion_flujo`**, paridad completa con `motor_calc`
  (S63, usuario). Descartado: corregir solo el caso vertical, y esconder el modelo nuevo tras
  una perilla con el default actual (dejaba el número por defecto equivocado).

## 6. Abierto

- `tipo_malla` sigue sin modelarse (§2.2). Es la pregunta que quedó abierta al cierre de S62 y
  la etapa 1 la responde **parcialmente**: ya no hace falta la malla para saber que el aire
  atraviesa el lecho, pero sí haría falta para el área efectiva si la malla es muy cerrada.
- Validación contra mediciones: sin datos, esto sigue siendo coherencia interna. Extensión
  natural de la mejora 38 fase 4.

## Ver también

- [[docs/bitacora/bitacora_sesion62]] — §5, el análisis del armario cuyo diagnóstico este plan
  corrige.
- [[Balance_de_calor_y_masa_en_camara_ampliado]] — derivación del balance que §1.2 confirma.
- [[docs/notas/plan_datos_medidos_4]] — validación de cámara y producto, el lazo que cerraría
  esto contra datos reales.
- [[docs/tareas]] — backlog.
