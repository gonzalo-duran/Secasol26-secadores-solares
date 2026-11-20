# Plan — Modelo de evaporación del producto (S69; Fase 0 hecha en S70)

**Fecha:** 2026-11-19 · **Rama:** `testing` (`ca68ceb`) · **Estado:** diagnóstico hecho, camino
a elegir. **Nada implementado.**

Documentos hermanos:

- [[docs/notas/analisis_corpus_evaporacion]]: inventario de los 14 trabajos, cruce
  tipo × tecnología, linaje del modelo y datos utilizables. **Leer primero.**
- Corpus: `docs/Papers de secadores p_ calibrar secasol/`.
- Antecedentes: [[docs/notas/balance de calor y masa en camara ampliado]],
  `docs/notas/Saravia2007.pdf`, [[docs/notas/plan_percolacion_parcial]] (en espera desde S67),
  [[docs/notas/plan_datos_medidos_4]] (validación de cámara, sin implementar).

---

## 1. Contexto y motivación

### 1.1 Qué hace hoy Secasol

La evaporación en cámara (`calculos/camara_termodinamica.py:16-17`, resuelta en
`resolver_estado_camara`, `:325-333`) es

```
ṁ_w = K_m · A_prod · (ω_sat(T_prod) · a_w(X) − ω_flujo)
K_m = h_conv / (cp_hum · Le^(2/3))          ← Chilton-Colburn, camara_calc.py:662 y :670
a_w(X)                                       ← isoterma GAB del catálogo, camara_calc.py:562-590
```

`K_m` representa **solo la película externa**: depende del aire (velocidad, propiedades) y no del
producto. El único lugar por donde el producto puede frenar la evaporación es `a_w(X)`.

### 1.2 Qué hace el linaje INENCO

Misma ecuación de Dalton en humedades absolutas, pero con un **coeficiente global empírico**
que cae con X: `Hpd(X) = a* + b*·X` (Condorí & Saravia 1998, 2003), `Ahd(X)` ajustado de una
curva de secado (Saravia 2007; Durán & Condorí 2009, polinomio cúbico para pimiento). Ese
coeficiente absorbe área, película y **resistencia interna**.

### 1.3 Los números que justifican el plan

Caída relativa del factor que frena la evaporación, pimiento, X de 9.65 a 0.1:

| X | `a_w` GAB (K=0.95) | `Hpd/Hpd₀` Condorí 1998 | `Ahd/Ahd₀` Durán 2009 |
|---|---|---|---|
| 9.65 | ≈ 1 | 1.000 | 1.000 |
| 2.3 | ≈ 1 | 0.238 | 0.011 |
| 1 | 0.97 | 0.104 | 0.003 |
| 0.5 | 0.89 | 0.052 | 0.002 |
| 0.1 | 0.33 | 0.010 | 0.0005 |

Con GAB, la fuerza impulsora no cae hasta X ≈ 0.5–1: el producto evapora a **velocidad de
período constante durante ~95 % del agua a remover**.

### 1.4 El estado real del catálogo (hallazgo de esta sesión)

`camara_calc._aw_func` lee solo `isoterma.gab.params` del catálogo. Revisados los 20 productos:

| Comportamiento de `a_w(X)` | Productos | Por qué |
|---|---|---|
| **GAB válido**: período decreciente solo al final (X < 0.5–1) | manzana, papa, yacón (3) | `X_m, C, K` cargados y `K ∈ (0,1)` |
| **Escalón**: 1 hasta X = 0.08, 0 debajo | **pimiento_rojo** (1) | `K = 1.02` (Vega 2007) → `PSICRO_GAB_K_FUERA_RANGO` → el `except` de `camara_calc.py:578-579` |
| **Rampa lineal** `a_w = X/X₀` | los otros 16 | `params` en `null` → `CAM_TD_GAB_FALTA` (`camara_calc.py:581-590`) |

Consecuencias:

1. **El modelo no es uno solo, son tres**, según el producto que elija el usuario, y ninguno de
   los tres está elegido por física.
2. La rampa de reserva `X/X₀` tiene **por casualidad la forma del `Hpd` lineal de Condorí**,
   pero puesta en el lugar equivocado: multiplica a `ω_sat` (una actividad de agua `a_w = 0.5`
   con el producto a medio secar es físicamente falsa: equivaldría a equilibrio con aire al 50 %
   de HR) en vez de al coeficiente.
3. El pimiento, producto central del corpus y de ADITAL, es el peor caso.
4. Los parámetros de Page (`capa_fina`) de varios productos —que sí describen el período
   decreciente— están cargados y son vestigiales desde S38.

## 2. Física del modelo

### 2.1 Lo que se quiere separar

La resistencia al paso del agua tiene dos tramos en serie:

```
agua en el interior ──[R_int(X, T, forma)]── superficie ──[R_ext = 1/K_m(v, T)]── aire de cámara
```

- **`a_w(X)`** es **termodinámica de equilibrio**: dice a qué humedad del aire el producto deja
  de perder agua. Fija `X_eq` y el final del secado. No es una resistencia.
- **`R_ext`** es la película: depende del aire. Ya está bien representada (Chilton-Colburn).
- **`R_int`** es **cinética del producto**: difusión del agua líquida/vapor hacia la superficie,
  con el frente de evaporación retrocediendo hacia adentro (Saravia 2007, §4: "ello corre la
  superficie de evaporación hacia el interior"). **Falta en Secasol.**

El `Hpd(X)` empírico mide `1/(R_ext + R_int)` multiplicado por el área, todo junto, en un
secador particular. Por eso confunde el caudal de ese secador con la cinética del producto.

### 2.2 Los tres caminos posibles

| Camino | Forma | Captura | No captura | Datos que pide |
|---|---|---|---|---|
| **(a) Factor empírico** | `K = K_m · f(X)`, `f` del producto | Período decreciente con la forma medida | Efecto del espesor/corte; `f` medido a una v y T da mal a otras (atribuye a `f` lo que era película) | Una curva de secado por producto (método Saravia 2007) |
| **(b) Resistencias en serie** | `1/K = 1/K_m(v,T) + 1/K_int(X,T,L)`, con `K_int` desde una difusividad efectiva y Arrhenius `D = D₀·exp(−E_a/RT)` | Período decreciente; dependencia con espesor/corte; con la T del producto; **conserva la dependencia con el caudal**; se reduce a la película pura con X alto | Encogimiento (salvo que se agregue); gradientes dentro de la pieza (es una resistencia concentrada, no un perfil de Fick) | `D_eff`, `E_a`, espesor característico. Los papers de `docs/notas/papers/` los traen para varios productos |
| **(c) Capa fina como velocidad límite** | `ṁ_w = min(ṁ_Dalton, ṁ_Page)` o similar | Reproduce curvas de capa fina de laboratorio | Las constantes de Page son de un secador de laboratorio con aire fijo; mezclar un límite empírico con un balance físico es lo que se sacó en S38 | Ya cargados (`capa_fina` del catálogo) |

**Recomendación: (b).** Es la única que separa lo que depende del aire (lo que el usuario diseña)
de lo que depende del producto (lo que el catálogo provee). Además, con `K_int → ∞` vuelve al
modelo actual, y con `K_m → ∞` es la difusión pura. El `Hpd(X)` del grupo pasa a ser una
**medición** contra la que se verifica, no un parámetro de entrada.

### 2.3 Cómo se ancla `K_int` — **cerrado en S70**

La forma linealizada que proponía este párrafo (`K_int ≈ ρ_s·D/L·dX/dω_sup`, evaluada en la
humedad media) **se descartó**: con la isoterma plana en X alto daba `K_int → ∞` justo cuando
la superficie ya está seca. Lo implementado resuelve la superficie de manera explícita:

```
interno:  ṁ = λ(T)·m_s·(X − X_s)          λ = μ₁²·D_eff(T)/L²   (primer modo de Fick)
externo:  ṁ = G·(ω_sat(T_prod)·a_w(X_s) − ω_ent)
```

- `L` = mitad de la dimensión de la **pieza** (`d_p` del lecho: espesor de rodaja, diámetro de
  ají); `μ₁ = π/2` lámina, 2.405 cilindro, π esfera. Escrito por kg de sólido, no necesita el
  área de la pieza.
- La cadena de aire es afín en `ω_sup` con los films fijos, así que `G` sale exacto de un
  solve sin resistencia y `X_s` es una raíz escalar monótona por paso
  (`camara_termodinamica.humedad_superficie_producto`). Tres solves por paso en vez de dos.
- `λ → ∞` reproduce el modelo previo; el período constante y el decreciente salen solos.
- **Anclaje Saravia 2007** (banana, 5 mm, 40 °C, 25 % HR): con `D_eff = 1.4·10⁻¹⁰ m²/s` —el
  `λ = 0.1989 h⁻¹` del paper con su espesor— RMSE en X de 0.08 en 10 h y T de producto a 5 h
  de 37.9 °C contra 36.8 °C medido. Sin resistencia interna, RMSE 1.27 (seca en < 2 h).
- Difusividad **aparente** (espesor inicial), no corregida por encogimiento: Secasol tiene
  espesor fijo (Hassini 2007: la corregida es ~10× menor en papa).

### 2.4 Lo que queda fuera de alcance, explícito

- **Perfil de humedad dentro de la pieza**: un nodo de producto por etapa; no hay
  discretización radial.
- **Encogimiento**: el área `A_prod` es geométrica y constante (Hassini 2007: ignorarlo sesga
  la `D_eff` hasta 90 %; por eso la `D_eff` del catálogo tiene que venir de papers que lo
  corrigen o declararse aparente).
- **Rehidratación / readsorción nocturna**: la isoterma es de desorción; la política B solo
  impide condensar.
- **Calor del suelo** (el desvío nocturno de Condorí 2003): Secasol no tiene suelo.
- **Distribución no uniforme del aire en la boca del túnel** (ADITAL, San Carlos): efecto 2D/3D,
  fuera de un modelo 0-D o de cascada.
- **Lecho atravesado**: retirado en S64 y fuera de este plan (Simate y Hachemi quedan como
  contraste).

## 3. Fases

Cada fase se cierra con verificación y espera aprobación antes de la siguiente.

### Fase 0 — Saneamiento del `a_w` (independiente del camino elegido)

Objetivo: que `a_w(X)` sea **solo** termodinámica de equilibrio, igual para todos los productos.

- Resolver el `K = 1.02` del pimiento: verificar contra Vega 2007 Tabla 2; si el valor es
  correcto, el inversor GAB debe tratar `K ≥ 1` (a_w acotado por `1/K`) en vez de rechazarlo.
- Reemplazar la rampa `X/X₀` por una reserva físicamente admisible (por ejemplo, `a_w = 1`
  hasta `humedad_equilibrio_aire_seco` con una isoterma genérica por familia de producto), y
  **avisar** al usuario cuál productos corren sin isoterma propia.
- Cargar isotermas faltantes donde el catálogo ya cita la fuente como "PENDIENTE".

**Esto cambia resultados**: los 16 productos con rampa van a secar **más rápido** al pasar a una
isoterma real (la rampa hoy simula, mal, parte del período decreciente). Por eso la Fase 0 no se
puede liberar sola: va junto con la Fase 2, o queda en `testing`.

### Fase 1 — Validar la película externa con agua libre

Objetivo: confirmar `K_m` (Chilton-Colburn + área) en el caso donde no hay resistencia interna.

- Datos: Durán 2008 (dos secadores domésticos en paralelo, bandejas de agua y esponjas);
  Condorí 1998 (600 bandejas negras, 235 kg en 3½ días, 50 m²); modelo ideal de Condorí 2009.
- Mecanismo en Secasol: un "producto" agua libre (`a_w = 1`, `X` muy alto, sin `K_int`).
- Criterio: tasa de evaporación simulada vs medida, con las métricas de
  `calculos/metricas_validacion.py`.
- Depende de digitalizar figuras o de que existan los registros del datalogger.

### Fase 2 — Resistencia interna (camino elegido en §2.2)

- Implementar `K_int` y la composición en serie dentro del closure `_coef_transporte`
  (`camara_calc.py:665`), que ya devuelve `(h, K_m)` por paso: el motor no cambia de forma.
- Catálogo: nuevo bloque por producto (`D_eff₀`, `E_a`, longitud característica derivada de la
  forma geométrica ya cargada en `forma_geometrica`).
- Calibración y verificación contra el dataset de Saravia 2007 (banana, completo en el texto).
- Verificación de forma contra `Hpd(X)` y `Ahd(X)` de pimiento.

### Fase 3 — Verificación a escala de sistema

- Túnel invernadero (Condorí 2003, primer carro) y ADITAL / San Carlos (2009, 2010, 2012):
  tiempos de secado (2–3 días de sol), HR de salida (mediana 17 %), ΔT de entrada a salida de cámara.
- **Como chequeo de orden de magnitud, no como objetivo de calibración** (Secasol es un
  prediseñador general).
- Encaja en la mejora 38, fase 4 ([[docs/notas/plan_datos_medidos_4]]).

## 4. Inventario de objetos (para la Fase 0 + 2; tentativo hasta elegir el camino)

| Objeto | Archivo | Acción | Por qué |
|---|---|---|---|
| `_aw_func` (reserva escalón y rampa) | `calculos/camara_calc.py:562-590` | **Modificar** | Hoy hay tres modelos según el producto (§1.4) |
| `actividad_agua_desde_X_GAB` | `calculos/psicrometria.py:510` | **Modificar** (si el K del pimiento es legítimo) | Rechaza `K ≥ 1` |
| `_coef_transporte` (closure) | `calculos/camara_calc.py:665-670` | **Modificar** | Lugar natural de la composición en serie: ya se evalúa por paso con `T_prod` |
| `K_m` inicial escalar | `calculos/camara_calc.py:662` | Modificar en paralelo | Se usa con el closure en `None` (compatibilidad hacia atrás) |
| `resolver_estado_camara` / `resolver_cadena_camara` | `calculos/camara_termodinamica.py:170`, `:435` | **Conservar** | Reciben `K_m` como dato; el sistema algebraico sigue lineal |
| `simular_secado`, `simular_cascada` | `calculos/camara_termodinamica.py:661`, `:1303` | Conservar | Idem; el closure ya llega por paso |
| `diagnostico_transferencia` | `calculos/camara_calc.py:864` | **Modificar** | El acercamiento al equilibrio debe distinguir resistencia externa vs interna |
| Bloque `isoterma.gab` del pimiento | `catalogo/productos/hortalizas.yaml:350-358` | **Corregir** | `K = 1.02` |
| Bloques `isoterma.gab.params: null` (16 productos) | `catalogo/productos/*.yaml` | **Completar** donde haya fuente | Hoy caen a la rampa |
| Bloque nuevo de cinética interna | `catalogo/productos/*.yaml` | **Crear** | `D_eff₀`, `E_a`, fuente |
| `capa_fina` | catálogo | **Conservar vestigial** | Filtra el selector de P4 (`_productos_disponibles`); útil como verificación |
| `Camara.modelo_capa_fina` | `core/camara.py:737` | Vestigial (sin cambio) | Compatibilidad hacia atrás de snapshots |
| `core/lecho.py` (espesor derivado) | `core/lecho.py:180` | **Consumir** | El espesor de capa es candidato para la longitud característica si la pieza es la capa |
| Tests | `tests/test_calculos/test_camara_termodinamica.py`, `test_psicrometria.py`, `test_validacion_camara.py` | Ampliar | Un test por código de error nuevo |
| Advertencias nuevas | `core/` + 3 YAML de `ui/idiomas/` | **Crear** | Producto sin isoterma / sin cinética interna |

## 5. Mapa de interrelaciones

```
catálogo (isoterma, cinética interna, forma)
   └─► camara_calc._propiedades / _aw_func / _coef_transporte
          ├─► simular_secado (CAJA, ARMARIO, DIARIO/VENTANA) ─► balance_global.calcular_todo[_transitorio]
          ├─► simular_cascada (GRAN_ESCALA batch y semicontinuo) ─► simulacion_ventana ─► calcular_todo_ventana
          ├─► simulacion_anual (8760 h, lotes encadenados) ─► P4 resumen anual, P7, reporte PDF
          ├─► barrido_parametrico (muta la cámara vía dataclasses.replace)
          └─► diagnostico_transferencia ─► P4/P7 (acercamiento al equilibrio)
```

Todo cálculo de cámara pasa por el mismo closure, así que **un cambio ahí alcanza a todos los
modos y tipologías a la vez**. Eso es lo bueno y lo riesgoso.

## 6. Regresiones esperadas

- **Todos los proyectos cambian de resultado.** Lotes más largos, menos agua evaporada por día
  a partir del segundo día y, en el modo anual, menos lotes completos.
- En la Fase 0 sola, los productos con rampa secarían **más rápido** (§3).
- Los tests con valores numéricos fijos de tiempo de secado o masa evaporada van a romper y hay
  que re-anclarlos con una justificación, no solo actualizar el número.
- El `acercamiento_equilibrio` y `aprovechamiento_aire` cambian de lectura: con resistencia
  interna, el aire de salida puede quedar seco por el producto y no por falta de NTU, que es lo
  que se midió en ADITAL ("el aire sale sin completar su potencial de secado").
- Requiere bump de versión y entrada en CHANGELOG cuando se libere.

## 7. Riesgo asumido

- **Pocos productos tendrán `D_eff` de fuente confiable** al principio: el resto corre sin
  resistencia interna, con aviso. El modelo seguirá siendo optimista para ellos.
- La forma concentrada de `K_int` (§2.3) es una aproximación. Si el dataset de Saravia 2007 no
  la sostiene, hay que volver al camino (a) para ese producto.
- La validación del sistema (Fase 3) se apoya en figuras digitalizadas si no aparecen los
  registros crudos.

## 8. Verificación

1. Fase 0: test por producto del catálogo, con `a_w(X)` monótona, en `[0, 1]` y con `a_w → 1`
   en X alto. Ningún producto cae en el escalón.
2. Fase 1: tasa de agua libre simulada vs Durán 2008 / Condorí 1998, RMSE y MBE.
3. Fase 2: reproducir `X(τ)` de Saravia 2007 (banana, 40 °C, 25 % HR, 1.6 m/s) con `R²` y RMSE;
   comprobar que la forma de `K/K₀` vs X cae en el rango de `Hpd(X)` de Condorí para pimiento.
4. Fase 3: tiempos de lote de pimiento en ADITAL dentro de 2–3 días de sol; HR de salida del
   orden medido.
5. Suite completa, black, ruff, `scripts/auditar_i18n.py`; revisor de convenciones tras la Fase 2.

## 9. Decisiones (cerradas en S70, 2026-11-19)

1. **Camino:** (b) resistencias en serie.
2. **K del pimiento:** el dato es el publicado (Vega 2007, Tabla 2). Se generalizó el inversor
   GAB para `K ≥ 1` (`a_w` acotada por `1/K`), con aviso `CAM_TD_GAB_K_MAYOR_1`. No es rareza
   del pimiento: uva y damasco de Kaymak 2004 dan `K` 1.00–1.04 en desorción.
3. **Reserva sin isoterma:** isoterma por **analogía** declarada en el catálogo
   (`isoterma.gab.analogia`, resuelta en `core.catalogo.isoterma_gab`) con aviso
   `PROD_ISOTERMA_ANALOGIA`. Solo el charqui queda sin isoterma (la sal la cambia por completo):
   `a_w = 1` hasta `humedad_equilibrio_aire_seco`, aviso `PROD_ISOTERMA_FALLBACK`. La rampa
   `X/X₀` se eliminó.
4. **Registros crudos:** no existen; se digitalizan figuras.
5. **Relación con S67:** se avanza a lo largo del sprint, sin exigir la Fase 1 como condición.

Fase 0 implementada en S70: ver [[docs/bitacora/bitacora_sesion70]].

### Texto original de las decisiones abiertas (S69)

1. **Camino** (§2.2): (a), (b) o (c). Recomendado (b).
2. **K del pimiento**: ¿se corrige el dato o se generaliza el inversor GAB?
3. **Reserva sin isoterma** (§3, Fase 0): ¿isoterma genérica por familia o bloquear el producto?
4. **Registros crudos**: ¿existen los archivos del datalogger del ensayo de agua libre 2008 y de
   ADITAL 2009–2010? Si no, se digitalizan figuras.
5. **Relación con S67**: la decisión de no tocar la transferencia de cámara sin mediciones;
   ¿este corpus alcanza para avanzar, o se exige primero la Fase 1?
