# Spec de diseño — Convección natural unificada (cajón + chimenea) y auxiliar en modo respaldo

**Estado (S61):** la **etapa 1 está implementada** — motor de flotabilidad del cajón desnudo
(bocas + `H_eff` de cámara + equilibrio + Picard amortiguado), con su UI en P4 y sus tests.
Ver §7 al final para lo que quedó igual y lo que cambió respecto de esta propuesta. Las
**etapas 2 (RESPALDO) y 3 (resto de UI) siguen pendientes**.

**Autor de la física de fondo:** decisiones tomadas con el usuario (Dr. en secado solar) en
la discusión de S61. Referencia física: `docs/notas/balance de calor y masa en camara
ampliado.md` (§7 circuito de aire) y `docs/notas/cubiertas translucidas en camara de
secado.md`.

---

## 0. Motivación — dos huecos que comparten un motor

1. **El cajón desnudo no tiene convección natural.** Un secador de tipo CAJA sin chimenea
   ni motor (caso muy común: caja con cubierta translúcida y bocas de aire) usa hoy un
   **caudal de diseño constante** (`balance_global.py`, rama `if not chimenea_activa`). El
   caudal de un secador pasivo **no es constante**: lo mueve la flotabilidad, que depende del
   estado térmico (sol, día/noche). Es un caso de mucha aplicación y hoy está mal resuelto.

2. **El auxiliar en modo `RESPALDO_INDEPENDIENTE` no tiene física propia.** Hoy aplica su ΔT
   como si fuera `SERIE_POSCOLECTOR` (en Constantes/Transitorio) o no hace nada (en Ventana).
   El modo respaldo real es **una resistencia eléctrica dentro de la cámara** que inyecta
   calor al aire.

Los dos comparten el **mismo motor de flotabilidad**: en el cajón desnudo el sol calienta el
aire y lo mueve; en respaldo la resistencia hace lo mismo (o lo refuerza). Construir el motor
de convección natural del cajón **habilita los dos**.

---

## 1. Decisiones tomadas (cerradas con el usuario)

- **Un solo modelo de convección natural** para CAJA y chimenea. La chimenea es la columna
  **alta con ducto**; el cajón/armario es la columna **corta con bocas**. Mismo fenómeno
  (efecto chimenea / stack effect), distinta altura y resistencia.
- La validación ADITAL **no aplica** (es un secador industrial de convección **forzada**, no
  CAJA ni ARMARIO). No condiciona este diseño.
- **RESPALDO**: solo tipologías **CAJA y ARMARIO** (nunca gran escala). Fuerza el tipo a
  **`RESISTENCIA_ELECTRICA`** (el quemador de leña **se anula** en este modo — no existe un
  quemador dentro de la cámara). `Q_aux` va al **nodo de aire** de la cámara por convección.
- **Empuje del tiro** = `T_flujo − T_amb`, siendo `T_flujo` la temperatura del aire **en el
  interior** de la cámara (en el CSTR de un nodo, coincide con la de salida).
- **Bocas**: el usuario carga **área de entrada** `A_in` y **área de salida** `A_out` (dato
  lógico en cajas/armarios). El coeficiente de pérdida `K` es **interno** (default físico), no
  lo carga el usuario.
- **Convergencia**: Picard **amortiguado** (sub-relajación, "B1").
- **Set-point de respaldo**: controla `T_flujo` (aire de cámara) modulando `Q_aux`.

---

## 2. Física

### 2.1 Motor de flotabilidad (tiro térmico) — unificado

El caudal natural de equilibrio se obtiene cuando el **tiro** iguala a la **resistencia** del
lazo. Se reusa la maquinaria de `calculos/chimenea_calc.py`, que ya lo resuelve para la
chimenea (`delta_P_tiro_Pa`, `caudal_natural_kgs` con `brentq`).

**Tiro térmico** (ya existe, sirve tal cual):

```
ΔP_tiro = g · H_eff · (ρ_amb − ρ_flujo)          ρ ∝ 1/T  (gas ideal, P común)
```

- `H_eff = altura_útil_cámara + altura_chimenea`  → para el **cajón desnudo**, `altura_chimenea = 0`
  ⇒ `H_eff = altura de la cámara`. Débil (H chico) pero **no nulo ni constante**.
- `ρ_flujo` evaluada a `T_flujo` (aire interior de la cámara).

**Resistencia del lazo** (acá está lo nuevo):

```
ΔP_resist = ΔP_bocas  [+ ΔP_ducto_chimenea]  [+ ΔP_lecho (Ergun, ya existe)]
```

Resistencia de **bocas** (nueva, `delta_P_bocas_Pa`):

```
ΔP_bocas = K_in · ½·ρ·v_in²  +  K_out · ½·ρ·v_out²
           con  v_in = ṁ/(ρ·A_in),  v_out = ṁ/(ρ·A_out)
```

- `K_in = 0.5` (contracción de canto vivo), `K_out = 1.0` (pérdida de energía cinética del
  chorro a la salida). **Constantes internas documentadas**, con posible override "avanzado" a
  futuro. Mismo concepto que el `K_singular` que ya usa la chimenea en su ducto.

**Equilibrio** (reusa `caudal_natural_kgs` con `brentq`):

```
ΔP_tiro(T_flujo) = ΔP_resist(ṁ)   →   ṁ_nat
```

### 2.2 Auxiliar en modo respaldo (resistencia dentro de cámara)

Aporte de calor al **nodo de aire** de la cámara:

```
Q_aux = potencia_nominal · fraccion_operacion · η_resistencia        (η ≈ 1)
```

Se **suma al numerador** del balance de aire en `resolver_estado_camara` (mismo renglón donde
hoy está `Q_rad_aire_W`, pero acá es un aporte **real y controlable** — la resistencia entrega
por convección/contacto, no por radiación transparente):

```
numerador  = ṁ·cp·T_REF + ṁ·(h_ent − ω·L_v0) + UA·T_amb + hA_p·T_prod + ṁ_w·h_v + Q_rad_aire + Q_aux
denominador = ṁ·cp + UA + hA_p
T_flujo = numerador / denominador
```

- **NO precalienta `T_ent`** (a diferencia de SERIE). En ARMARIO `T_ent = T_sal_colector`; en
  CAJA `T_ent = T_amb`. `Q_aux` entra **adentro**.
- Convive con el colector (armario) y con `Q_rad` (paredes translúcidas): la cámara puede
  recibir aire precalentado + `Q_aux` + `Q_rad` a la vez.

**Set-point** (controla `T_flujo`, modulando `Q_aux`): dado que `T_flujo = (num_base + Q_aux)/
den`, para alcanzar `T_set`:

```
Q_aux = clamp( T_set · denominador − num_base , 0 , Q_max )
```

- `num_base` = numerador **sin** `Q_aux`. `Q_max = potencia_nominal · fraccion`.
- Si el colector/sol ya llevan `T_flujo ≥ T_set` ⇒ `Q_aux = 0`. Si `Q_max` no alcanza ⇒
  `Q_aux = Q_max` (subdimensionado, aviso). Es **algebraico** dentro del solve de cámara ⇒ no
  rompe la linealidad (mismo criterio que los coeficientes de transporte variables de S39).

### 2.3 Regímenes de convección (cómo entra al lazo)

| Régimen | Qué mueve `ṁ` | Picard | Efecto de `Q_aux` |
|---------|---------------|--------|-------------------|
| **Forzada** (hay motor) | el ventilador impone `ṁ` | **No** | `Q_aux` sube `T_flujo` a `ṁ` fijo |
| **Natural** (chimenea **o** cajón) | flotabilidad: `ṁ ← tiro ← T_flujo` | **Sí, amortiguado** | `Q_aux` sube `T_flujo` ⇒ más tiro ⇒ más `ṁ` (enciende/refuerza la convección) |

**Convergencia (Picard amortiguado, B1).** El lazo `ṁ_{n+1} = tiro(T_flujo(ṁ_n))` tiene
realimentación negativa (más calor → más tiro → más caudal → menos ΔT por unidad de masa) y
**puede oscilar en 2-ciclo** si la pendiente del mapa es < −1 (es el caso que vimos con aux
fuerte + techo translúcido). Con `Q_aux` inyectado adentro el aporte es mayor ⇒ más propenso a
oscilar. Solución: **sub-relajación**

```
ṁ_{n+1} = α · tiro(T_flujo(ṁ_n)) + (1 − α) · ṁ_n     con α ≈ 0.5
```

y subir el tope de iteraciones (~12). El criterio de convergencia es el residual real
`|tiro(T_flujo) − ṁ|`.

---

## 3. Cambios por módulo

### `core/`

- **`ConfiguracionFlujo`** (`core/camara.py`): + `area_entrada_aire_m2: Optional[float]` y
  `area_salida_aire_m2: Optional[float]`. Validación en `__post_init__` (> 0 si se definen).
  `None` = no definidas (back-compat).
- **`Auxiliar`** (`core/auxiliar.py`): coacción `RESPALDO_INDEPENDIENTE ⇒ tipo =
  RESISTENCIA_ELECTRICA` (en `__post_init__` o en la UI). Documentar que el quemador no aplica
  en respaldo.

### `calculos/`

- **`chimenea_calc.py`** (se generaliza; renombrarlo o dejarlo como está y agregar):
  - `delta_P_bocas_Pa(m_dot, A_in, A_out, rho, K_in=0.5, K_out=1.0)`.
  - Generalizar `caudal_natural_kgs` para que la resistencia total sea `ducto [+ bocas]` según
    haya chimenea o no, y `H_eff` use la altura de cámara con `altura_chimenea = 0` si no hay
    chimenea.
- **`camara_termodinamica.py`**:
  - `resolver_estado_camara(..., Q_aux_W=0.0)` — nuevo término al numerador del aire.
  - `simular_secado` propaga `Q_aux_W` (constante) o el **control de set-point** (`T_set`,
    `Q_max`) evaluado por paso.
- **`balance_global.py`**:
  - `conveccion_natural_activa = (motor is None) and (chimenea is not None or bocas_definidas)`
    — reemplaza al `chimenea_activa`. Cubre el cajón desnudo.
  - Ruteo de **RESPALDO**: no tocar `T_ent`; pasar `Q_aux` al solver de cámara. En SERIE, todo
    sigue igual.
  - Picard **amortiguado** (α, más iteraciones) en el lazo natural.
  - Forzada: `Q_aux` a `ṁ` fijo, sin Picard.
  - **Los dos pipelines**: Constantes (`_caudal_natural_loop`, `_resolver_aux_cam_const`) y
    Transitorio (`_caudal_natural_horizonte`, `_correr_aux_y_armar_forzantes`).

### `ui/`

- **P4** (`p4_camara.py`): inputs de **área de entrada** y **área de salida** de aire, visibles
  cuando la convección natural es posible (motor off, CAJA/ARMARIO). Aviso si es cajón desnudo
  sin bocas (cae a caudal de diseño con sugerencia de definirlas).
- **P5** (`p5_auxiliar.py`): al elegir `RESPALDO_INDEPENDIENTE`, **forzar/deshabilitar** el
  selector de tipo a `RESISTENCIA_ELECTRICA` (quemador oculto), con nota. **Consecuencia en el
  entregable T_sal_aux(t) (S60):** en respaldo el auxiliar **no** produce un ΔT sobre la
  entrada, así que esa gráfica (T_entrada → T_sal_aux) pierde sentido; para respaldo la
  gráfica relevante es `T_flujo(t)` (aire de cámara) mostrando el efecto de `Q_aux`. Definir si
  se adapta la gráfica según el modo.
- **i18n**: claves nuevas en `es/en/pt` (bocas en p4, respaldo en p5).

### `tests/`

- **Cajón desnudo**: `ṁ_nat` varía con el estado térmico (mediodía > noche); mayor sol ⇒ mayor
  `ṁ`; sin bocas ⇒ cae a caudal de diseño con aviso.
- **Bocas**: `ΔP_bocas` crece al achicar `A`; el equilibrio da `ṁ` coherente.
- **RESPALDO**: `Q_aux` entra al balance de aire; `T_flujo` sube; set-point modula `Q_aux`
  (0 si el colector ya supera; `Q_max` si subdimensionado); `Q_aux` **aumenta el tiro** (más
  `ṁ` que sin respaldo).
- **Picard amortiguado**: converge en el caso que antes oscilaba.
- **Forzada**: `ṁ` fijo, `Q_aux` sumado, sin Picard.
- **Back-compat**: chimenea sin bocas ⇒ resultado idéntico al actual; `RESPALDO` que hoy no
  hace nada pasa a la física nueva (los tests viejos que asumían "respaldo = serie" se revisan).

---

## 4. Compatibilidad y migración

- **Chimenea existente:** cuando hay chimenea, la resistencia sigue siendo el **ducto** (modelo
  validado); las bocas son opcionales/aditivas. Si `A_in/A_out` son `None`, la resistencia es
  la de hoy ⇒ **proyectos con chimenea no cambian de resultado**.
- **Cajón desnudo + bocas** ⇒ convección natural nueva. **Cajón desnudo sin bocas** ⇒ caudal de
  diseño (comportamiento actual) + aviso sugiriendo definir las bocas. Migración suave.
- **RESPALDO** hoy aplicaba ΔT como SERIE (inconsistencia documentada en `docs/mapa_auxiliar.md`)
  ⇒ pasa a la física correcta. Revisar los snapshots/tests que dependían del comportamiento viejo.

---

## 5. Riesgos y cuidados

1. **Convergencia del Picard** — el motivo por el que hay que amortiguar desde el arranque (no
   como parche a posteriori). Es el punto más delicado; los tests deben cubrir el caso oscilante.
2. **No romper la chimenea validada** — la resistencia de ducto se preserva; las bocas son
   aditivas solo donde corresponde.
3. **Supuesto de un nodo (CSTR)** — el empuje usa `T_flujo − T_amb` sobre `H_cámara`, ignorando
   el gradiente vertical real dentro del cajón. Consistente con el resto del motor; documentarlo.
4. **Dirección del flujo** — la flotabilidad implica flujo **vertical** (entra abajo, sale
   arriba). Hoy `direccion_flujo` es HORIZONTAL por default; decidir si se auto-ajusta o se avisa.

---

## 6. Orden de implementación sugerido (por etapas, cada una con sus tests)

1. **Motor de flotabilidad del cajón desnudo** (bocas + `H_eff` de cámara + equilibrio +
   Picard amortiguado). Es el bloque **urgente y autónomo**: mejora todos los cajones pasivos,
   con o sin auxiliar.
2. **RESPALDO** (`Q_aux` al nodo de aire + set-point + coacción a resistencia). Depende de (1)
   para el caso de convección natural.
3. **UI** (bocas en P4, respaldo en P5, adaptación del gráfico T_sal_aux/T_flujo) + i18n.
4. Cada etapa cierra con sus tests y con la suite completa en verde.

---

## 7. Qué se implementó de la etapa 1 (S61) y en qué se apartó del plan

Implementado tal cual: `delta_P_bocas_Pa` con `K_in=0.5`/`K_out=1.0` internos; `H_eff` = altura
de cámara (+ chimenea si hay); equilibrio por `brentq` reusando `caudal_natural_kgs`;
`ConfiguracionFlujo.area_entrada_aire_m2`/`area_salida_aire_m2` con validación; activación por
`conveccion_natural_activa` (motor off **y** (chimenea **o** bocas)); Picard con sub-relajación
`α = 0.5`; back-compat de chimenea sin bocas; widgets en P4 + i18n ×3.

**Tres cosas que el plan no anticipaba:**

1. **Faltaba `T_flujo` para el cajón.** El lazo necesita la temperatura del aire interior en
   cada iteración, y en modo Constantes sin colector el balance no la tenía: usaba la
   heurística `T_amb + 25 K`, que **no depende de ṁ** y por lo tanto congelaba el lazo
   (convergía en una iteración con un tiro inventado). Se agregó
   `camara_calc.estimar_T_flujo_estacionario`, que resuelve el CSTR **una vez** con el
   producto en su estado estacionario (`brentq` sobre `q_prod + Q_rad − ṁ_w·L_v = 0`) en vez
   de integrar el secado. Con colector se conserva la heurística `T_sal_col − 5 K`, que es el
   camino validado. Sin esto, una caja translúcida —donde **todo** el calor entra por el
   producto insolado— no habría tenido tiro.
2. **El tope de iteraciones del transitorio quedaba corto.** Amortiguar duplica los pasos
   (5 → 8 en un cajón típico) y el tope era 5, así que habría reportado "no convergió" en
   casos que sí convergen. Medido: ~0.1 s por iteración ⇒ se subió a 12 (Constantes, 10 → 14).
3. **Guarda de lazo sin resistencia.** Sin chimenea, sin bocas y sin pérdidas, el equilibrio no
   existe (el caudal sería infinito, no cero) y `brentq` fallaba con un error opaco de bracket.
   Ahora `caudal_natural_kgs` lo detecta y lanza `CHIM_LAZO_SIN_RESISTENCIA`; el balance ni
   siquiera llega ahí, porque `conveccion_natural_activa` exige chimenea o bocas.

**Riesgo 4 del §5 sigue abierto:** `direccion_flujo` no se auto-ajusta a VERTICAL_ASCENDENTE
cuando hay bocas, aunque la flotabilidad implica flujo vertical. Hoy solo afecta el rótulo.

**Ampliación pedida por el usuario (misma sesión):** las bocas se extendieron al circuito
**forzado** —con ventilador no cambian el caudal pero sí la presión que debe entregar— y los
coeficientes pasaron a depender de la topología (`coeficientes_bocas`), con el descuento del
término de entrada en `K_singular_chim` para no contar dos veces la descarga. Detalle en §10.1
y §10.2 del doc de estado. Los **acoples de sección desigual** (colector↔boca, boca↔chimenea)
quedan explícitamente **fuera de alcance** por decisión del usuario, anotados como corrección
futura.

---

## 8. Qué se implementó de las etapas 2 y 3 (S62) y en qué se apartó del plan

Implementado tal cual: `Q_aux` al numerador del nodo de aire; set-point por
`clamp(T_set·den − num_base, 0, Q_max)` resuelto **dentro** del solve, sin iterar;
coacción `RESPALDO ⇒ RESISTENCIA_ELECTRICA` en `__post_init__`; ruteo en Constantes y
Transitorio sin tocar `T_ent`; P5 con el selector de tipo restringido y la gráfica
adaptada; i18n ×3.

**Cuatro cosas que el plan no anticipaba:**

1. **El techo de potencia tuvo que viajar como forzante.** `Q_aux_max` depende de la hora
   (calendario de arranque, disponibilidad nocturna) y esa lógica vive en
   `auxiliar_calc`. Se agregó `ForzantesAire.Q_aux_max_W` y se extrajo
   `auxiliar_calc.mascara_disponibilidad` —antes enterrada dentro de
   `calcular_auxiliar_transitorio`— para que serie y respaldo compartan **la misma** regla
   en vez de duplicarla y desincronizarse. En Constantes, que no tiene serie, va un
   escalar.
2. **El lazo natural no veía el auxiliar.** `estimar_T_flujo_estacionario` (S61) no
   recibía `Q_aux`, así que el caudal salía **idéntico** con y sin respaldo: el auxiliar
   calentaba pero no movía más aire, que es justo el acople que justificaba hacer esto
   ahora. Lo detectó un test.
3. **La energía no se reportaba si el lote no terminaba.** El bloque de energías de
   Constantes está detrás de un gate de convergencia (`BG_TD_NO_CONVERGE`), pensado para
   `Q × t_secado`. Para respaldo la energía es una integral que existe igual, y el caso
   donde más interesa es precisamente aquel en que el secado **no** termina. Se reporta
   fuera del gate.
4. **Dos reconstrucciones campo por campo perdían datos** (`camara_calc` y
   `balance_global._correr_aux_y_armar_forzantes`): `Q_rad_aire_W`,
   `energia_rad_aire_total_J` y `t0_utc` quedaban en su default. Pre-existentes, no
   introducidas acá; se pasaron a `dataclasses.replace`.

**Contraintuición registrada:** con set-point, la energía **total** puede ser MAYOR que a
potencia plena, porque a potencia plena el lote termina antes y la integración se corta.
Comparar siempre potencia media, no la integral, entre corridas de distinta duración.

**Sin validar contra mediciones**, como todo lo de S61.

### 8.1 Correcciones salidas de la primera corrida real (S62)

El usuario corrió una CAJA de 0.25 m³ con 10 kg de manzana y una resistencia de 250 W en
respaldo (`tests/test analisis armario con resistencia/`), y de ahí salieron tres arreglos:

1. **La máscara de disponibilidad se ataba solo a `I_g_W_m2`.** Donde la irradiancia viaja
   como POA y ese campo queda en ceros, la máscara daba todo falso y el respaldo se apagaba
   **sin decir nada** (`E_aux = 0`), mientras P5 —que usa las forzantes del horizonte de
   P4— dibujaba la potencia disponible: las dos pestañas se contradecían. Ahora
   `_irradiancia_para_mascara` cae a POA, y si el respaldo **nunca** llega a operar en todo
   el horizonte se emite `ADV_RESPALDO_NUNCA_OPERA` en vez de reportar un cero mudo.
2. **`temperatura_maxima_salida_K` no se controlaba en respaldo.** En serie lo hace
   `calcular_auxiliar` sobre la T de salida del equipo; en respaldo no hay tal salida, así
   que el límite ahora se contrasta contra `T_flujo` (`AUX_RESPALDO_EXCEDE_T_MAX`). **Solo
   avisa, no recorta**, como en serie. En la corrida del usuario el producto llegó a 63.4 °C
   contra un límite declarado de 65 °C sin una sola advertencia.
3. **El gráfico de P5 se leía como una consigna de temperatura.** Con el eje en kW, los
   escalones parecían una rampa de calentamiento hacia un set point. Pasó a ser un estado
   binario "opera / no opera", con la potencia en el título.

**Decisión de modelo confirmada (usuario, S62):** el aporte del respaldo va **100 % al aire
por convección**, sin reparto radiativo — una resistencia de secador no llega a
incandescencia y su emisión IR no compite con la convección desde el elemento. El límite del
supuesto queda documentado en el docstring de `resolver_estado_camara`.

**Lección de diagnóstico:** el primer análisis atribuyó el `E_aux = 0` de una captura al
bug de la máscara. No era eso: el pipeline real **sí** puebla `I_g_W_m2` (5 puntos en
P4/P7), y la captura y el `.json` exportado eran de dos corridas distintas (61.5 h con
`E_aux = 0` vs 37.5 h con 15.26 MJ). El bug de la máscara es real y latente, pero no era ese
síntoma. Reproducir antes de afirmar causalidad.

## Ver también

- `docs/mapa_auxiliar.md` — mapa del auxiliar (incluye la inconsistencia de RESPALDO que esto cierra).
- `docs/notas/balance de calor y masa en camara ampliado.md` — §7 circuito de aire.
- `calculos/chimenea_calc.py` — motor de tiro a generalizar.
- `calculos/camara_termodinamica.py::resolver_estado_camara` — dónde entra `Q_aux`.
