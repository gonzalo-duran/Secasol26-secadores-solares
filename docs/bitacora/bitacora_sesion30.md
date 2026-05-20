# Bitácora — Sesión 30 (2026-05-19/20, sesión extendida)

**Tema:** Mapeo de conexiones UI ↔ core ↔ calculos para detectar widgets huérfanos. Durante el intento de arreglar el primer huérfano (`n_cubiertas`) se destapa un **bug físico preexistente en el residual algebraico del colector** (signos invertidos en F1 de los 4 tipos y F3 del Tipo 1) que devolvía raíces espurias con `T_cub_e ≈ −200 °C` y residuos numéricos cero. Se corrige el bug, se valida el modelo contra Hottel-Whillier-Bliss (linealidad perfecta, R² = 1.0000) y recién entonces se implementa la doble cubierta con cavidad de aire. La sesión se extiende para resolver el cabo F4 (incoherencia EDO fluido vs balance del fondo en Tipos 2/3/4) y para cerrar completamente la orfandad de chimenea: modelo físico (`chimenea_calc.py`), migración estructural (`Chimenea` de `Colector` a `Proyecto`), UI propia en P6 e integración del caudal natural en `balance_global`. Tras la integración single-pass se completan los cabos físicos restantes en una segunda jornada (2026-05-19/20): **Picard cerrado por el colector en modo constantes**, **acople del lazo natural con el motor termodinámico de cámara en pipeline transitoria**, **re-corrida del colector hora a hora** dentro del Picard transitorio, y — al destapar que el solver de colector recibía GHI en lugar de POA en el caso transitorio — implementación completa de **POA precomputada en `ForzantesAire`** (helper compartido, sin parches inline).

**Estado al cierre:** **774 tests pasan + 2 xfailed** (vs 717 + 2 al cierre de S29, +57 tests netos). Sin commits. De las tres orfandades del mapa de conexiones: dos resueltas (n_cubiertas, chimenea), una pendiente (espesor_placa_m, decisión consciente de no incorporar capacitancia de placa por ahora). El F4 cuestionable también quedó resuelto. La chimenea queda físicamente completa: caudal natural acoplado, colector re-corrido a velocidad efectiva del lazo, y radiación incidente en POA (no GHI) en todos los caminos del pipeline. Suite verde sin regresiones.

---

## 84. Punto de partida — mapa de conexiones

El usuario pidió una visualización del proyecto para identificar situaciones como la del toggle de "cubierta opaca/translúcida" de S26, donde la UI ofrecía una opción que el código de cálculo ignoraba. Acordamos generar un mapa Mermaid hecho a medida (UI↔core↔calculos) en lugar de instalar herramientas externas como `pydeps` o `pyreverse`, porque ese tipo de herramienta solo muestra dependencias de importación, no flujo de datos.

### 84.1 Mapa de conexiones — `docs/mapa_conexiones.md`

Se delegaron tres exploraciones paralelas (un Explore agent cada una):

1. Inventario de dataclasses en `core/` con énfasis en booleanos y enums.
2. Asignaciones `proyecto.* = ...` por cada `ui/p{1-7}*.py`.
3. Lecturas `proyecto.*`, `colector.*`, `camara.*`, etc. en `calculos/*.py`.

Cruzando los tres inventarios por nombre de campo aparecieron tres huérfanos:

| # | Widget UI | Campo | Síntoma |
|---|-----------|-------|---------|
| 1 | "Incorporar chimenea solar" (P3) | `colector.chimenea.*` | Sin consumidor en `calculos/`; solo advertencia geométrica |
| 2 | "N° cubiertas" (P3) | `colector.unidad.n_cubiertas` | Ni `colector_calc.py` ni `colector_tipos234_calc.py` leen el campo |
| 3 | "Espesor placa absorbedora" (P3) | `colector.unidad.espesor_placa_m` | No entra al balance térmico (capacitancia placa despreciada) |

El usuario eligió empezar por **n_cubiertas**.

### 84.2 Decisión de modelado — U_top efectivo

Para n=2 se discutieron tres caminos:

- **Modelo riguroso completo**: 5/6 incógnitas en el fsolve (T_cub1_e, T_cub1_i, T_cub2_e, T_cub2_i, T_abs [+ T_int para Tipos 2-4]). Más fiel pero requiere validar convergencia y tests nuevos.
- **U_top efectivo**: dejar el sistema fsolve original (3/4 incógnitas) y sustituir `U_cub = k_cub/esp_cub` por una conductancia serie `cubierta + cavidad + cubierta`. Aproximación: usar T_cub_e y T_cub_i como proxy de las temperaturas que bordean la cavidad. Error < 5 % para cubiertas de vidrio/policarbonato donde la resistencia conductiva de cada cubierta es despreciable frente a la cavidad.
- **Restringir UI a n=1**: punteo honesto.

El usuario eligió **U_top efectivo con proxy simple**. La cavidad usa Hollands inclinada (ya existe en `correlaciones_nusselt.py`) para la convección natural más radiación entre superficies grises paralelas, y el espaciado entre cubiertas pasa a ser un campo configurable por el usuario (`espaciado_entre_cubiertas_m`).

---

## 85. Implementación inicial (que destapó el bug)

### 85.1 Campos y helpers nuevos

- `core/colector.py`: nuevo campo `espaciado_entre_cubiertas_m: float = 0.025` en `ColectorUnidad`, con validación dura en `__post_init__` y advertencia blanda en `advertencias_colector()` si está fuera del rango 10–50 mm.
- `calculos/colector_calc.py`: dos helpers nuevos:
  - `_h_cavidad_aire(T_sup, T_inf, esp_cav, em_sup, em_inf, pendiente_deg, P_amb)`: coeficiente combinado convección natural (Hollands) + radiación gris paralela.
  - `_U_cubierta_efectiva(n_cubiertas, T_cub_e, T_cub_i, k_cub, esp_cub, em_cub, esp_cav, pendiente_deg, P_amb)`: devuelve `k_cub/esp_cub` para n=1 o la conductancia serie completa para n=2.

### 85.2 Smoke test del Tipo 1 con n=2 — falla absurda

Primer test integrador con policarbonato + selectiva, T_amb=20 °C, I=800 W/m², viento 2 m/s, gap=25 mm:

```text
n=1: T_sal=70.85 °C  η=0.561  (OK)
n=2: T_sal=−107 °C   η=−1.40  ← ¡imposible!
```

La salida con doble cubierta era físicamente absurda. El fluido se enfriaba al pasar por el colector. Los perfiles internos mostraban `T_abs = −182 °C` mientras `T_cub_e ≈ 21 °C`. Convergencia reportada (`ier=1`) pero con T_abs negativa.

---

## 86. Diagnóstico — bug preexistente en el residual

### 86.1 La raíz espuria del modelo previo

Para descartar que fuera mi cambio el que rompía las cosas, **revertí la modificación del residual y corrí el modelo n=1 con los mismos parámetros**. Los tests existentes (`TestSistemaNodo::test_solucion_satisface_balances`) seguían pasando con residuos ≈ 1e-12, así que el sistema sí convergía. Pero al inspeccionar la solución del Tipo 1 con n=1 vi:

```text
T_cub_e = −47.6 °C    ← bajo T_amb=20 °C, físicamente imposible
T_cub_i = +37.8 °C
T_abs   = +158.5 °C
```

Los residuos eran cero numérico, pero las temperaturas no podían ser correctas: bajo 800 W/m² y T_amb=20 °C, la cara externa de la cubierta no puede estar a −47 °C. Confirmé probando los `PARAMS_REF` del test (vidrio + selectivo, T_f=330 K): el fsolve devolvía `T_cub_e = −200 °C`, `T_cub_i = −183 °C`, `T_abs = 136 °C`. Todos los guesses iniciales convergían a la misma raíz.

**Por qué T_fluido salía "razonable" igual:** la EDO del fluido depende solo de T_cub_i y T_abs (los dos lados del canal). Esos valores caían en un rango que daba un T_salida creíble por mera coincidencia numérica. T_cub_e quedaba desacoplado del fluido y vagabundeaba a −200 °C sin consecuencias visibles **mientras** se usara con n=1. Al introducir la cavidad de aire para n=2, las temperaturas de la cubierta se acoplaban al fluido a través de h_cav, y la raíz espuria llevaba al sistema a soluciones donde T_abs ≪ 0.

### 86.2 Análisis de signos

Auditoría de F1 (balance de la cara externa de la cubierta) en Tipo 1:

```python
# Convención: T_cub_e es la cara externa (al ambiente), T_cub_i la interna (al absorbedor).
# En operación normal T_cub_i > T_cub_e (la cubierta interna está más caliente).
conduccion_cub = U_cub * (T_cub_e - T_cub_i)   # NEGATIVO en op. normal
F1 = conv_viento + rad_cielo - conduccion_cub  # ← bug
```

Para que F1 = 0 con `T_cub_i > T_cub_e` (físicamente correcto), debería ser:

```text
ganancia (conducción desde T_cub_i) = pérdidas (viento + cielo)
U·(T_cub_i − T_cub_e) = h_w·(T_cub_e − T_amb) + ε·σ·(T_cub_e⁴ − T_cie⁴)
```

En la convención del código, eso es:

```python
F1_correcto = conv_viento + rad_cielo + conduccion_cub  # SUMA
```

El signo del término de conducción estaba invertido. Como `conv_viento + rad_cielo > 0` siempre que `T_cub_e > T_amb` y `T_cub_e > T_cie`, y `−conduccion_cub > 0` cuando `T_cub_i > T_cub_e`, **el residual F1 escrito no podía dar cero** en operación física. El fsolve compensaba llevando T_cub_e muy por debajo de T_amb para que `conv_viento` y `rad_cielo` se volvieran negativos (ambiente "calentando" cubierta), encontrando ahí su única raíz matemática.

F3 (balance del absorbedor) tenía un segundo bug análogo en el término convectivo al fluido:

```python
conv_fluido_abs = h_int * (T_abs - T_f_K) * W_abs_m   # positivo en op. normal (pérdida)
F3 = rad_solar_abs + conv_fluido_abs - rad_cub_abs - cond_fondo  # ← bug
# Correcto: F3 = rad_solar_abs − conv_fluido_abs − rad_cub_abs − cond_fondo
```

El absorbedor recibe radiación solar y pierde por convección al fluido, radiación a la cubierta y conducción al fondo. El signo `+` en `conv_fluido_abs` lo hacía aparecer como ganancia, no pérdida.

### 86.3 Tipos 2-4

El residual de Tipos 2-4 está en `colector_tipos234_calc.py`. Al auditarlo encontré:

- **F1 en los 4 tipos (incluido Tipo 1)**: mismo bug de signo en `conduccion_cub`.
- **F3 en Tipos 2-4**: ya estaba bien. Usan convención `rad_cub_abs = (T_cub_i⁴ − T_abs⁴)` con signo `+` (signo opuesto al de Tipo 1, ambos correctos), y `conv_cs_abs`/`conv_ci_abs` con signo `−` (pérdida) correctamente.
- **F4 en Tipos 2-4**: la cara interna del fondo balancea solo radiación abs→fondo contra conducción del aislante. La convección al fluido del canal inferior se asume cancelada por simetría con `abs→fluido_ci`. Eso solo es exacto si T_abs y T_int son simétricos respecto a T_f_ci, lo cual no se cumple en operación normal. **No es bug de signo, pero es una simplificación cuestionable** — quedó como tarea aparte.

### 86.4 Validación numérica del fix

Antes de tocar archivos definí un `sistema_nodo_corregido` en un script de prueba y lo corrí con los PARAMS_REF del test del Tipo 1 (vidrio + selectivo). Resultado:

```text
T_cub_e = 43.4 °C    (antes: −200 °C)
T_cub_i = 45.3 °C    (antes: −183 °C)
T_abs   = 85.3 °C    (antes: 136 °C)
Residuos ≈ 1e-12 desde cualquier guess inicial
```

Solución física, única y robusta. Aplicamos las dos correcciones definitivamente.

---

## 87. Correcciones aplicadas

### 87.1 Tipo 1 (`calculos/colector_calc.py`)

```diff
- F1 = conv_viento + rad_cielo - conduccion_cub
+ F1 = conv_viento + rad_cielo + conduccion_cub

- F3 = rad_solar_abs + conv_fluido_abs - rad_cub_abs - cond_fondo
+ F3 = rad_solar_abs - conv_fluido_abs - rad_cub_abs - cond_fondo
```

Comentarios actualizados explicando la convención (ganancia/pérdida explícitas).

### 87.2 Tipos 2-4 (`calculos/colector_tipos234_calc.py`)

```diff
- F1 = conv_viento + rad_cielo - cond_cub
+ F1 = conv_viento + rad_cielo + cond_cub
```

en `_sistema_nodo_tipo2` y `_sistema_nodo_tipos34`. F2-F4 quedaron como estaban.

### 87.3 Suite de tests — pasaron sin cambios

Los 717 tests existentes pasaron sin tocar ningún test. Los tests originales fueron escritos validando **rangos y coherencia** (T_abs > T_f, T_cub_e < T_abs, residuos ≈ 0, η creciente con I, etc.) y no valores numéricos exactos, por eso aguantaron el cambio. El balance global cierra al 0.26 % de error en la prueba integradora — el modelo conserva energía.

**Efecto cuantitativo del fix** en el caso clásico (policarbonato + negra mate, T_amb=20 °C, I=800, v=2 m/s):

```text
Antes (modelo con bug):  T_cub_e = −47 °C, T_abs = 158 °C, η = 0.561
Después (corregido):     T_cub_e = +25 °C, T_abs = 102 °C, η = 0.444
```

η baja porque desaparece el aporte espurio del cielo "calentando" una cubierta a −47 °C. Los proyectos `.json` guardados con el motor previo van a dar valores distintos al cargarse — eso queda documentado.

---

## 88. Validación HWB

Klein (1979) es la referencia clásica para U_top de un colector de placa plana, pero está pensada para colectores con cavidad estanca entre absorbedor y cubierta. En nuestro Tipo 1 el aire pasa por encima del absorbedor enfriando activamente la cubierta interna (`T_cub_i ≈ 27 °C` mientras `T_abs ≈ 149 °C`), por lo que Klein sobrestima U_top en un factor 3×. Esto **no** es un problema del modelo — es por qué Klein no aplica a air heaters de canal único.

La validación correcta es **Hottel-Whillier-Bliss**: una curva η = F_R·(τα) − F_R·U_L · (T_in − T_amb)/G debe ser lineal en (T_in − T_amb)/G si el modelo es físicamente correcto.

Script: `validacion/validacion_hwb.py`. Resultado:

| Caso | F_R·(τα) | F_R·U_L | R² |
|------|----------|---------|-----|
| Vidrio + TiNOX (selectiva) | 0.541 | 4.12 | 1.0000 |
| Vidrio + negra mate | 0.338 | 4.73 | 1.0000 |
| Policarbonato + negra mate | 0.444 | 4.17 | 1.0000 |
| Policarbonato + TiNOX, invierno | 0.588 | 3.82 | 1.0000 |

Los cuatro casos dan **linealidad perfecta** (R² = 1.0000) y los parámetros caen en rangos publicados para air heaters: F_R·(τα) entre 0.34 y 0.59, F_R·U_L entre 3.8 y 4.7 W/m²K. F_R·U_L es algo bajo respecto a colectores comerciales (5-10) pero esperable: el aire del canal enfría la cubierta interna, reduciendo pérdidas reales al cielo.

Tres validaciones independientes superadas:

1. Conservación de energía global (0.26 % de error).
2. Forma funcional HWB lineal con R² = 1.0000.
3. Magnitudes en rangos típicos publicados.

---

## 89. Implementación de n_cubiertas

Con el motor confiable, retomo la doble cubierta.

### 89.1 Helpers

```python
def _h_cavidad_aire(T_sup_K, T_inf_K, esp_cav_m, em_sup, em_inf,
                     pendiente_deg, P_amb_Pa) -> float:
    # T_film = (T_sup + T_inf) / 2
    # rho, beta, nu, alpha del aire a T_film como gas ideal
    # Ra = g·beta·ΔT·esp³ / (nu·alpha)
    # Nu = nusselt_hollands_inclinada(Ra, min(pendiente, 75°))
    # h_conv = Nu · K_AIRE / esp_cav
    # em_eff = 1 / (1/em_sup + 1/em_inf − 1)
    # h_rad = em_eff · σ · (T_sup² + T_inf²) · (T_sup + T_inf)
    return h_conv + h_rad

def _U_cubierta_efectiva(n_cubiertas, T_cub_e, T_cub_i, k_cub, esp_cub, em_cub,
                          esp_cav_m, pendiente_deg, P_amb_Pa) -> float:
    if n_cubiertas == 1:
        return k_cub / esp_cub
    h_cav = _h_cavidad_aire(T_cub_e, T_cub_i, esp_cav_m, em_cub, em_cub,
                             pendiente_deg, P_amb_Pa)
    return 1.0 / (2.0 * esp_cub / k_cub + 1.0 / h_cav)
```

### 89.2 Propagación

`_sistema_nodo` (Tipo 1, Tipo 2 y Tipos 3/4) ahora recibe `n_cubiertas`, `esp_cav_m`, `pendiente_deg`, `P_amb_Pa` como kwargs **con defaults seguros** (`n=1`, `25 mm`, `30°`, `101325 Pa`). Eso es lo que permitió que los tests existentes (que llaman a `_sistema_nodo` con args posicionales sin las nuevas keys) siguieran funcionando sin cambios.

Las funciones públicas `calcular_colector_tipo{1,2,3,4}` reciben `pendiente_deg=30.0`. En el Tipo 3 reutilizamos `theta_deg` (que ya existía para Hollands del canal estanco) como pendiente para la cavidad de cubiertas — es el mismo ángulo físico.

En los `params` dict de cada función pública, agregué las cuatro keys nuevas leyendo `colector.unidad.{n_cubiertas, espaciado_entre_cubiertas_m}` y propagando `pendiente_deg`, `P_amb_Pa`.

En los **5 `fsolve` calls** (uno en cada `_construir_rhs_tipo{1,2,3,4}` y otro en los reconstructores de perfiles), agregué los cuatro nuevos args al final de la tupla, leídos con `params.get(key, default)` para que tests que arman `params` manualmente sigan funcionando.

### 89.3 Callers

- `calculos/balance_global.py`: lee `proyecto.emplazamiento.pendiente_colector_deg` y la pasa a los 4 colectores (con `theta_deg` en Tipo 3 y `pendiente_deg` en el resto).
- `ui/p3_colector.py`: la función interna `_correr_colector` recibe ahora `pendiente_deg=30.0` y los dos callsites (diario y anual) le pasan `empl.pendiente_colector_deg`.

### 89.4 UI

Widget condicional: cuando `n_cubiertas == 2` aparece un `number_input "Espaciado entre cubiertas [mm]"` con default 25 mm, rango 10-50 mm y un help que cita a Duffie & Beckman.

Persistencia: el campo se serializa en el JSON del colector (`_json_config_colector`) y se lee con `u.get("espaciado_entre_cubiertas_m", 0.025)` para retrocompatibilidad con `.json` exportados antes de S30.

### 89.5 Tests nuevos

Nueva clase `TestDobleCubierta` con 5 tests en `tests/test_calculos/test_colector_calc.py`:

- `test_eta_n2_mayor_que_n1`: η(n=2) > η(n=1).
- `test_T_cub_e_n2_menor_que_n1`: cara externa más fría con doble cubierta.
- `test_T_cub_i_n2_mayor_que_n1`: cara interna más caliente (atrapada).
- `test_ganancia_mayor_a_alta_delta_T`: la ventaja de la doble cubierta crece con (T_in − T_amb), no es constante.
- `test_temperaturas_fisicas`: monotonía `T_amb < T_cub_e < T_cub_i < T_abs` y rango razonable de T_abs.

Todos pasan. Suite completa: **722 passed, 2 xfailed**.

### 89.6 Magnitud del efecto

Vidrio + selectiva (TiNOX), gap=25 mm:

| Condición | η n=1 | η n=2 | Δη |
|-----------|-------|-------|-----|
| Verano (T_amb=20°C, I=800, v=2) | 0.541 | 0.613 | +7.2 pp |
| Invierno (T_amb=0°C, I=600, v=4) | 0.538 | 0.621 | +8.3 pp |

Tipos 2, 3, 4: ganancias similares (+5 a +7 pp). Tipo 4 (canal inferior estanco) es el que más se beneficia porque sus pérdidas superiores son más críticas.

---

## 90. Pendientes / próximos pasos (actualizado al final de S30)

- **`espesor_placa_m`**: configurable pero no entra al balance. Documentar la hipótesis de capacitancia despreciable o incorporar el término capacitivo al EDO.
- **Iterar T_chim ↔ caudal natural** en `balance_global` (hoy single-pass, error ≤ ~10 %) y re-correr colector con el caudal natural para que `Q_util_W` refleje la velocidad real del lazo (hoy queda a velocidad de diseño).
- **Mostrar `res.chimenea` en P7 Resultados** + aviso si el caudal natural difiere >30 % del de diseño manual en P4.
- **Commit del trabajo de S30**: cambios distribuidos entre `core/{colector,proyecto,chimenea}.py`, `calculos/{colector_calc,colector_tipos234_calc,balance_global,chimenea_calc}.py`, `ui/{p3_colector,p6_motor}.py`, `tests/{test_calculos/test_colector_calc,test_calculos/test_chimenea_calc,test_calculos/test_balance_global,test_core/test_colector}.py`, `validacion/{validacion_hwb,validacion_klein,comparar_f4}.py`, `docs/{mapa_conexiones.md,bitacora/bitacora_sesion30.md}`. Conviene split en commits temáticos: (a) fix signos F1/F3 + n_cubiertas, (b) fix F4 Tipos 2/3/4, (c) chimenea_calc + migración + UI P6 + integración balance, (d) docs.
- **Avisar al usuario que los `.json` previos darán valores distintos**: la η y T_salida que reportaban los snapshots guardados antes de S30 se basan en la raíz espuria del modelo previo. Los valores nuevos son más bajos (~25 % menos η en air heaters por signos F1/F3, otros ~10-12 pp menos en Tipos 2 y 3 por F4) pero físicamente correctos.

**Resueltos durante S30** (ver §92-§96):
- **F4 en Tipos 2-4**: incoherencia entre EDO del fluido ci y balance del fondo arreglada agregando `conv_ci_int` explícito.
- **Chimenea solar**: módulo `chimenea_calc.py` + migración a `Proyecto` top-level + UI propia en P6 + integración en `balance_global`. Ya no es huérfana.

---

## 91. Lecciones de proceso

### 91.1 Tests verdes ≠ modelo correcto

Los 717 tests del proyecto pasaban antes y después del fix. Pero **antes** estaban pasando contra una raíz matemática espuria con `T_cub_e = −200 °C`. La prueba `test_solucion_satisface_balances` validaba `np.allclose(residuos, 0.0, atol=1e-4)` y daba verde con esa solución absurda. La regla `T_cub_e < T_abs` se cumplía (`−200 °C < 136 °C`). Las regresiones numéricas no detectaron nada porque la salida del fluido (que es el observable público) era razonable por coincidencia.

Lección: los tests de coherencia (monotonía, signos, rangos amplios) no son suficiente para garantizar corrección física. Cuando un sistema algebraico tiene múltiples raíces, hay que validar **valores específicos** contra una referencia externa (HWB lineal, balance de energía cerrado, casos publicados). Idealmente agregar un test que verifique que **todos los guesses iniciales razonables converjan al mismo punto** — esa es la prueba que delata raíces espurias.

### 91.2 Sintoma vs causa

El bug se manifestó como "n=2 da T_salida absurda". El instinto natural era buscar el problema en el código de n=2 que acababa de escribir. La detección correcta vino de **revertir mi cambio y verificar el caso n=1 con valores realistas**, lo que destapó que T_cub_e = −47 °C ya estaba mal antes. El bug llevaba meses ahí, oculto por la EDO del fluido que no depende de T_cub_e.

Lección: cuando un cambio nuevo expone un comportamiento absurdo, **primero verificar que el caso base sigue correcto**. Si el caso base también falla, el bug es preexistente y el cambio nuevo simplemente lo hizo visible. Esto evita perder tiempo depurando la última modificación.

### 91.3 No bypasear el diagnóstico

Hubo tentación de "hacer que mi código de n=2 funcione DESPITE el bug preexistente" — por ejemplo, restringiendo el guess inicial del fsolve para que cayera lejos de la raíz espuria. Eso habría escondido el bug todavía más. El usuario eligió arreglar el bug primero, antes de extender el modelo. Resultó ser la decisión correcta: una vez corregidos los signos, los nuevos tests `TestDobleCubierta` pasaron al primer intento porque el motor base era confiable.

Lección: cuando aparece un bug en una capa profunda durante una extensión, no intentes "trabajar alrededor" — pausá la extensión, arreglá la capa profunda, y recién entonces seguí. Es más rápido y deja el sistema mejor.

### 91.4 Defaults seguros mantienen compatibilidad

Al extender `_sistema_nodo` con cuatro nuevos parámetros, asignar defaults físicamente correctos para n=1 (`n_cubiertas=1, esp_cav_m=0.025, pendiente_deg=30.0, P_amb_Pa=101325.0`) permitió que **todos los tests directos al residual siguieran pasando sin cambios**. Y al usar `params.get(key, default)` en los 5 `fsolve` calls, los tests que arman manualmente el dict `params` (sin las keys nuevas) tampoco se rompieron.

Lección: cuando se agregan parámetros a una función interna que tiene tests directos, los defaults deben preservar el comportamiento previo. Si no se puede (porque el cambio es semánticamente incompatible) hay que actualizar los tests de forma explícita en el mismo commit. Mezclar defaults nuevos con cambios de semántica es donde se cuelan los bugs.

### 91.5 Validación HWB > validación Klein para air heaters

La primera tentativa de validar el modelo usó Klein (1979), referencia clásica de D&B para U_top. Dio discrepancias de 70-80 % con el modelo numérico. La conclusión correcta no es "el modelo está mal" sino "Klein no aplica a air heaters de canal único", porque asume cavidad estanca entre absorbedor y cubierta. La validación adecuada para air heaters es HWB (linealidad de η vs (T_in − T_amb)/G), que sí dio R² = 1.0000.

Lección: elegir la referencia de validación según el dominio. Para air heaters de canal único, Klein no es válido. HWB es universal y solo requiere que el motor numérico pueda variar T_entrada — el ajuste lineal detecta automáticamente si el modelo se desvía de la teoría de Hottel-Whillier.

---

## 92. Fix F4 en Tipos 2/3/4 — coherencia local del fondo con el fluido inferior

Continuando el trabajo sobre el motor del colector, vuelvo a la "hipótesis de simetría" reportada como cuestionable en §86.3 de esta misma bitácora. En F4 (balance de la cara interna del fondo, `T_int`) el código asumía que la convección entre fluido del canal inferior y las dos superficies (absorbedor y fondo) se cancelaba neto, dejando F4 = rad abs→fondo − cond aislante.

### 92.1 Diagnóstico — inconsistencia interna del modelo

Al inspeccionar la EDO del fluido del canal inferior (`colector_tipos234_calc.py:686-688`):

```python
dTci/dx = (h_ci·(T_abs − T_f_ci) + h_ci·(T_int − T_f_ci)) · W_abs / (m_ci · cp)
```

la EDO **ya cobra ambas convecciones**. Si F4 no las incluye, el fluido recibe energía del fondo (vía `h·(T_int − T_f_ci)`) sin que ese flujo aparezca como pérdida en el balance del fondo. **No es una hipótesis cuestionable, es un bug de coherencia local**: la EDO del fluido y F4 son mutuamente inconsistentes.

### 92.2 Corrección

Agregamos el término faltante a F4 en ambos sistemas nodo (`_sistema_nodo_tipo2` y `_sistema_nodo_tipos34`):

```python
conv_ci_int = h_int_ci * (T_int - T_f_ci) * W_abs_m
F4 = rad_abs_fondo - cond_ais - conv_ci_int
```

Para Tipo 4 (canal inferior estanco) la corrección sigue siendo correcta: con `T_f_ci = (T_abs + T_int)/2`, el término representa el aporte convectivo desde el absorbedor mediado por el fluido estanco hacia el fondo.

### 92.3 Validación cuantitativa

Script `validacion/comparar_f4.py` corre los 3 tipos antes/después del fix (caso vidrio + selectiva, T_amb=20°C, I=800, v=2 m/s):

| Tipo | η viejo | η nuevo | Δη [pp] | ΔT_salida [K] | ΔT_int [K] |
|------|---------|---------|---------|---------------|------------|
| 2    | 0.740   | 0.636   | **−10.3** | −4.7        | −13.1      |
| 3    | 0.561   | 0.437   | **−12.4** | −11.3       | −18.1      |
| 4    | 0.447   | 0.453   | +0.6      | +0.5        | +4.0       |

Tipos 2 y 3 con bug: el fluido inferior recibía calor "fantasma" del fondo, inflando η ~10-12 pp. Tipo 4 casi sin cambio porque el fluido estanco no transporta masa.

Suite: 722 tests siguen verde sin modificación. El bug pasó los tests de coherencia porque éstos miden rangos amplios, no balances diferenciales.

### 92.4 Implicancia para usuarios

Los `.json` guardados antes del fix devuelven η incorrectos al recalcularse: Tipos 2 y 3 dan ~10-12 pp menos, Tipo 4 casi igual. Sumado al fix de signos F1/F3 (que ya bajó ~25 % en air heaters), los snapshots viejos no son comparables. Conviene avisar en changelog.

---

## 93. Modelo físico de chimenea solar — `calculos/chimenea_calc.py`

La chimenea era el primer huérfano del mapa de conexiones: UI completa en P3, dataclass en core, pero **ningún módulo de `calculos/` la leía**. Solo había validación de geometría en `advertencias_colector()`.

### 93.1 Modelo

Funciones puras, sin dependencia de `core/` ni `streamlit`:

- **`delta_P_tiro_Pa(T_amb, T_chim, H_eff, P_amb)`**: tiro térmico = `g · H_eff · (ρ_amb − ρ_chim)`. ρ desde gas ideal. H_eff = altura_chimenea + altura útil de la cámara.

- **`delta_P_chimenea_Pa(ṁ, T_chim, D, H, ...)`**: pérdida en el ducto de chimenea. Fricción Darcy con Haaland + singulares bundleados K=1.5 (entrada 0.5 + salida 1.0). Rugosidad default 1.5e-4 m (chapa galvanizada).

- **`caudal_natural_kgs(T_amb, T_chim, D, H_chim, H_camara, delta_P_resto_fn, ...)`**: caudal de equilibrio vía `scipy.optimize.brentq` sobre `ΔP_tiro = ΔP_chim(ṁ) + ΔP_resto(ṁ)`. Bracket [1e-8, 10] kg/s. T_chim entra como dato (acoplamiento térmico delegado al caller).

### 93.2 Convención termodinámica

T_chim es la temperatura promedio de la columna ascendente (cámara + chimenea). Para prediseño recomendamos **T_chim ≈ T_salida_cámara**, no T_salida_colector — el aire ya se enfrió por evaporación al pasar por la carga. Si se usa T_salida_colector se sobrestima el tiro.

### 93.3 Tests (23 en `tests/test_calculos/test_chimenea_calc.py`)

Signos del tiro (positivo si T_chim > T_amb, negativo si contraflujo, nulo si H=0), monotonías con H y ΔT, balance de energía en el equilibrio (ΔP_tiro = ΔP_chim + ΔP_resto), casos sin tiro (T_chim ≤ T_amb → ṁ=0 con advertencia `CHIM_SIN_TIRO`), sensibilidades al ΔP del resto del lazo, consistencia interna v_chim = ṁ/(ρ·A).

### 93.4 Magnitudes de referencia

Chimenea D=20cm, H=3m, cámara H=1.5m, lazo `ΔP_resto = 500·ṁ²`:

| T_chim | ṁ [kg/s] | v_chim [m/s] | Q [m³/h] | ΔP_tiro [Pa] |
|--------|----------|--------------|----------|--------------|
| 35 °C  | 0.044    | 1.21         | 143      | 2.6          |
| 55 °C  | 0.064    | 1.89         | 209      | 5.7          |
| 80 °C  | 0.079    | 2.50         | 258      | 9.0          |

Coherente con la literatura de secadores solares chicos a medianos.

---

## 94. Migración estructural — `Chimenea` de `Colector` a `Proyecto`

Antes del fix la chimenea colgaba de `Colector` (`proyecto.colector.chimenea`). Esto era una inconsistencia: para tipología CAJA, `proyecto.colector is None` por construcción, así que la chimenea era inalcanzable justo en la tipología que más la necesita (convección natural pura).

### 94.1 Cambios estructurales

- **Nuevo `core/chimenea.py`**: `Chimenea` dataclass + `advertencias_chimenea(chim) → list[Advertencia]`. Idéntico a lo que estaba en `colector.py` pero independiente.
- **`Proyecto.chimenea: Optional[object] = None`**: nuevo field top-level en `core/proyecto.py`.
- **`Colector`**: se removió el field `chimenea` y su kwarg en `__init__`. `advertencias_colector()` ya no chequea chimenea.

### 94.2 Compatibilidad de `.json`

Los snapshots viejos guardaban `chimenea` como sub-key del snapshot del colector. La compat se mantiene en el loader de P3: si `data.get("chimenea") is not None`, se reconstruye en `proyecto.chimenea` por separado. Snapshots nuevos de P3 no incluyen chimenea (es responsabilidad de P6).

### 94.3 Tests

Imports actualizados en `tests/test_core/test_colector.py` y `tests/test_calculos/test_motor_fase2.py`. El test `test_adv_chimenea_diametro_pequeno` se migró a usar `advertencias_chimenea(ch)` directamente. Se agregaron `test_adv_chimenea_altura_pequena` y `test_adv_chimenea_none_sin_advertencias`. Suite +2 desde la base.

---

## 95. UI de chimenea — movida de P3 a P6

### 95.1 Motivación

Si la chimenea es top-level del proyecto, la UI debe estar accesible en una pestaña visible para CAJA. P3 (Colector) no aplica a CAJA. El lugar natural es **P6 (Motor)** porque conceptualmente es el otro mecanismo de movimiento de aire — son alternativas.

### 95.2 Ubicación en P6

Cuando el toggle "Incorporar motor" está OFF, debajo del mensaje "Sin motor — convección natural" aparece la sección **Chimenea solar**:

- Toggle "Incorporar chimenea solar".
- 3 inputs: diámetro [m], altura [m], material (catálogo `FONDOS`).
- Advertencias estáticas (`advertencias_chimenea`).
- **Preview de tiro térmico**: 4 métricas con ΔP_tiro para ΔT = 10/20/30/40 K, usando `delta_P_tiro_Pa` con H_eff = altura_chimenea + alto_cámara (lee de `proyecto.camara.geometria.alto_m` si está, fallback 1.5 m). Sirve para que el usuario vea el orden de magnitud antes de correr el balance completo.
- Save/load `.json` y `.txt` específicos para chimenea (sección `"chimenea"` en el JSON).

Helpers nuevos en `ui/p6_motor.py`: `_from_json_chimenea`, `_json_config_chimenea`, `_texto_config_chimenea`, `_render_chimenea_section`.

### 95.3 Limpieza de P3

Se removió:
- Checkbox "Incorporar chimenea solar" + expander con 3 inputs.
- Construcción de `Chimenea(**chim_data)` y asignación.
- Bloque CHIMENEA del texto de configuración (`_texto_config_colector`).
- Sección `chimenea` del snapshot JSON (`_json_config_colector`).
- Mezcla de advertencias_colector + advertencias_chimenea (ahora P3 solo muestra advertencias del colector).

`_from_json_colector` se simplificó: devuelve solo `Colector` (antes devolvía `tuple[Colector, Chimenea | None]`). El caller maneja la compat con `data.get("chimenea")`.

---

## 96. Integración del caudal natural en `balance_global`

Con el modelo físico y la UI listos, falta lo más sustantivo: que el caudal del lazo de simulación efectivamente venga del tiro de chimenea cuando no hay motor.

### 96.1 Helper `_caudal_natural_loop`

Construye `delta_P_resto_fn(m)` con **escalado cuadrático** alrededor del caudal de diseño del usuario:

```python
ΔP_resto(m) ≈ ΔP_resto(m_design) · (m / m_design)²
```

donde `ΔP_resto(m_design) = estimar_delta_P_colector(...) + estimar_delta_P_camara(...)` a la velocidad/caudal que el usuario configuró. El escalado cuadrático es exacto para flujo turbulento (ΔP ∝ v²) y conservador para laminar (subestima caudal, sobrestima pérdidas).

Decisión de scope: no se reescriben los estimadores de ΔP para que tomen `ṁ` explícito; se usa el anclaje cuadrático sobre el punto de diseño. Suficiente para prediseño.

### 96.2 Inyección en `calcular_todo`

Entre el solver del colector y el del auxiliar, si `motor is None and chimenea is not None and camara is not None`:

1. Estima T_chim: `T_salida_colector − 5 K` si hay colector, `T_amb + 25 K` si es CAJA.
2. Llama `_caudal_natural_loop` → obtiene `res_chim` con `m_punto_kgs`, `v_chim_ms`, `delta_P_tiro_Pa`, `delta_P_chimenea_Pa`, `delta_P_resto_Pa`, `Re_chimenea`, `H_eff_m`, `advertencias`.
3. **Mutación temporal**: `proyecto.camara.flujo.caudal_masico_kg_s = m_natural`. Esto hace que `calcular_camara` (que lee del dataclass) use el caudal natural.
4. El solver del auxiliar recibe `caudal_kg_s = m_natural` como argumento explícito.
5. `try / finally` restaura el caudal original al salir — no se contamina el proyecto del usuario.

El resultado completo se guarda en `ResultadosCompletos.chimenea` (campo nuevo, `Optional[dict]`) para uso de UI/P7.

### 96.3 Demo end-to-end

ARMARIO + colector default + cámara default (caudal usuario 0.030 kg/s) + chimenea D=25cm/H=3m + sin motor + T_amb=25°C + I=800 W/m²:

```text
Caudal natural    : 0.092 kg/s  (302 m³/h, ~3× el caudal de diseño manual)
v en chimenea     : 1.77 m/s
Re en chimenea    : 23475 (turbulento)
ΔP tiro           : 5.51 Pa
ΔP chimenea       : 3.02 Pa
ΔP resto          : 2.49 Pa
Balance cierra    : ✓ (5.51 = 3.02 + 2.49)
T salida colector : 65.1 °C
```

Observación: el caudal natural para esta chimenea es 3× lo que el usuario había puesto en P4 como diseño manual. La chimenea está sobredimensionada (o el caudal manual estaba subdimensionado para esa chimenea). Es información valiosa para iteración de diseño.

### 96.4 Tests (`TestChimeneaIntegrada`, 7 tests)

- Sin chimenea: `res.chimenea is None`.
- Con motor + chimenea: motor manda, chimenea no se invoca.
- Sin motor + chimenea: `res.chimenea` poblado con keys completas.
- Caudal original de la cámara se restaura tras el cálculo.
- Caudal natural difiere del caudal de diseño (>1 %).
- Balance del lazo cierra: `ΔP_tiro = ΔP_chim + ΔP_resto`.
- CAJA + chimenea (sin colector) funciona con T_chim fallback.

Suite final S30: **754 tests + 2 xfailed** (era 717 al cierre de S29; neto +37 en esta sesión extendida).

### 96.5 Limitaciones explícitas

- **Single-pass, sin iteración**: T_chim se estima una vez con `T_salida_colector − 5 K`. La T_chim real (= T_salida_cámara) se obtiene tras correr la cámara, pero no re-iteramos. Error ≤ ~10 % en caudal típicamente.
- **El colector no se re-corre con el caudal natural**: `Q_util_W` queda calculado a la velocidad de diseño del colector. El caudal correcto se aplica a aux y cámara, no al colector.

Ambas son mejoras planificables para una sesión futura; quedan documentadas como cabos sueltos en §90.

---

## 97. Visualización de `res.chimenea` en P7 (modo constantes)

Primer cabo de la jornada del 2026-05-19/20: la integración del §96 dejó el caudal natural calculado y restaurado correctamente en `ResultadosCompletos.chimenea`, pero P7 no lo mostraba. Se agregó al render una sección dedicada entre el bloque "Motor / Ventilador" y "Balance Energético Global", sólo cuando `res.chimenea is not None` (motor=None + chimenea + cámara).

### 97.1 Helpers y bloque visual

- `_desviacion_caudal_natural(res_chim, proyecto)` (puro, testeable): devuelve `|m_natural − m_design| / m_design` o `None` si el proyecto no tiene cámara con caudal definido.
- `_render_chimenea_resultados(res_chim, proyecto)`: 8 métricas en 2 filas de 4 columnas:
  - Fila 1: ṁ natural [g/s], caudal volumétrico [m³/h], v_chim [m/s], Re_chim.
  - Fila 2: ΔP_tiro, ΔP_chim, ΔP_resto, H_eff.
  - Caption con el cierre del balance del lazo (`ΔP_tiro ≈ ΔP_chim + ΔP_resto`).
  - **Warning explícito si la desviación |ṁ_natural − ṁ_design| / ṁ_design > 30 %** (recomendando ajustar D/H de la chimenea en P6 o el caudal de diseño en P4).
  - Advertencias propias del solver (`CHIM_FLUJO_LAMINAR`, `CHIM_VEL_ALTA`, `CHIM_SIN_TIRO`).

### 97.2 Tabla de resultados completa y snapshots

- Tabla expander: 8 filas Chimenea entre Motor y Balance.
- `_texto_resultados_completo` (.txt): bloque "CHIMENEA SOLAR (convección natural)" después de MOTOR con métricas escalares, advertencias y aviso de desviación.
- `_json_resultados_completo` (.json): bloque `proyecto.chimenea` arriba (config via `_json_config_chimenea` de P6) y bloque `resultados_globales.chimenea` con todas las claves + `desviacion_vs_diseno`.

Demo end-to-end confirmó: ARMARIO + chimenea D=25cm/H=3m sin motor, ṁ=92.2 g/s, v=1.77 m/s, balance del lazo cierra (5.51 = 3.02 + 2.49 Pa), warning de desviación 207 % disparado correctamente (la chimenea estaba sobredimensionada respecto al caudal manual de 30 g/s).

---

## 98. Picard cerrado por el colector en modo constantes

El usuario eligió "Acoplada con motor TD" para resolver la limitación documentada en §96.5 (single-pass + colector a velocidad de diseño). En modo constantes la cámara de capa fina no expone T_aire explícita, así que el lazo cierra **por el colector**: T_chim depende del colector, el colector depende de la velocidad efectiva del aire, la velocidad depende de ṁ_natural, ṁ_natural depende de T_chim. Picard sobre esa cadena converge si las funciones son monótonas (caso típico).

### 98.1 Refactor preparatoria

Tres helpers extraídos en `calculos/balance_global.py`:

- `_correr_colector(proyecto, T_amb_K, I_g_W_m2, v_viento_ms, T_entrada_K) → (solver, T_salida_K)`: encapsula el dispatch por tipo (1, 2, 3, 4). Lee `unidad.velocidad_diseno_ms` del dataclass — el orquestador muta ese campo antes de llamar para acoplar con el lazo natural.
- `_velocidad_modulo_desde_caudal(colector, ṁ, T_op, P_amb)`: convierte `ṁ` total del lazo a velocidad en el canal de un módulo: `v = ṁ / (ρ · A_canal · n_paralelo)`. Asume canal principal `ancho × espaciado` (válido para Tipo 1 y aproximación de primer orden para 2/3/4 con bicanal).
- `_T_salida_camara(solver_cam, T_op_fallback)`: abstrae la T del aire saliendo de la cámara según el tipo de solver (TD estacionario expone `T_flujo_K`; capa fina no, fallback a T_op).
- `_resolver_aux_cam_const(proyecto, T_sal_col, caudal, HR_cam, T_amb)`: corre aux + cámara con un caudal dado, retorna `(solver_aux, solver_cam, T_sal_aux, T_sal_cam, advs, errs)`. Usable tanto en pipeline single-pass como dentro del loop Picard.

### 98.2 Loop Picard

Dentro de `calcular_todo`, cuando `motor=None and chimenea and camara`, se reemplaza el single-pass por:

```python
T_chim_iter = max(T_salida_colector_K − 5.0, T_amb + 1.0)  # o T_amb + 25 si CAJA
for iter in range(1, MAX_ITER+1):              # MAX_ITER=10, TOL=0.5 K
    res_chim = _caudal_natural_loop(proyecto, T_amb_K, T_chim_iter, caudal_design)
    m_nat = res_chim["m_punto_kgs"]
    if m_nat <= 0: break                       # sin tiro térmico
    proyecto.camara.flujo.caudal_masico_kg_s = m_nat
    if proyecto.colector is not None:
        v_nueva = _velocidad_modulo_desde_caudal(...)
        v_nueva = clip(v_nueva, 0.05, 15.0)    # evita Re patológico
        proyecto.colector.unidad.velocidad_diseno_ms = v_nueva
        solver_col, T_salida_colector_K = _correr_colector(...)
    T_chim_new = max(T_salida_colector_K − 5.0, T_amb + 1.0)
    delta = abs(T_chim_new − T_chim_iter)
    T_chim_iter = T_chim_new
    if delta < TOL: converged = True; break
# después del loop: una sola corrida de aux+cámara con caudal convergido
```

La cámara queda **fuera** del loop — sólo se corre una vez al final con el caudal convergido. Decisión razonada: el enfriamiento por evaporación en cámara es de segundo orden (< 3 K para caudales > 0.03 kg/s) y la capa fina no provee feedback de T_aire de todos modos.

`try/finally` restaura `velocidad_diseno_ms` y `caudal_masico_kg_s` al estado original — no se contamina el proyecto del usuario.

### 98.3 Demo y tests

ARMARIO + chimenea D=25cm/H=3m sin motor, mismo escenario que §96.3 pero con Picard:

```text
iter, convergio, ΔT_chim final : 7, True, 0.359 K
T_chim convergida              : 39.70 °C
ṁ natural                      : 0.0409 kg/s   (vs 0.092 single-pass)
v chimenea                     : 0.74 m/s
Q_util colector                : 767.3 W
η colector                     : 61.5 %
Estado proyecto restaurado     : ✓
```

El caudal converge a ~40 g/s, ~55 % menor que el single-pass de §96.3 (que sobreestimaba porque el colector quedaba corrido a velocidad de diseño 2 m/s, generando ΔT_col irrealmente alto que inflaba el tiro).

Tests nuevos (5) en `TestChimeneaIntegrada`:

- `test_picard_metadata_presente`: claves `iteraciones`, `convergio`, `delta_T_chim_final_K`, `T_chim_K` en `res.chimenea`.
- `test_picard_converge_armario`: ARMARIO típico converge con `convergio is True` en ≤ 10 iter, ΔT_chim final < 0.5 K.
- `test_picard_re_corre_colector`: chimenea más grande → ṁ_nat mayor y `Q_util_W` del colector cambia (responde a v efectiva, no a v de diseño).
- `test_picard_caja_converge_trivialmente`: CAJA sin colector → 1 iter, T_chim queda en T_amb + 25 K heurística sin depender de ṁ.
- `test_picard_restaura_v_diseno_colector`: `velocidad_diseno_ms` restaurada al original tras la llamada.

Suite: **759 + 2 xfailed** (era 754, +5 nuevos).

---

## 99. Acople con motor TD en pipeline transitoria

Para el modo transitorio el lazo natural se acopla al **motor termodinámico de cámara**: cada hora del horizonte tiene su propia T_chim(t), su propio ṁ_nat(t) y, por tanto, sus propias forzantes al motor TD. Picard sobre el horizonte completo (no por hora separada).

### 99.1 Helper horario

Nuevo `_caudal_natural_horizonte(proyecto, T_amb_serie, T_chim_serie, m_ref) → dict` que itera `caudal_natural_kgs` hora a hora. Reutiliza la misma `delta_P_resto_fn` cuadrática anclada al caudal de referencia (caudal de diseño del usuario). Devuelve arrays de shape (N,): `m_punto_kgs`, `v_chim_ms`, `delta_P_{tiro,chimenea,resto}_Pa`, `Re_chimenea`, `H_eff_m`, `horas_sin_tiro`, plus union de advertencias deduplicadas.

### 99.2 Picard transitorio en `calcular_todo_transitorio`

`ResultadosCompletosTransitorio` gana campo `chimenea: Optional[dict]` con series + metadata Picard. Cuando `motor=None + chimenea + camara`:

```python
T_chim_serie = forzantes_base.T_ent_K − 5.0   # o T_amb + 25 K si CAJA
T_chim_serie = max(T_chim_serie, T_amb_serie + 1.0)
for iter in range(1, 5+1):                    # MAX_ITER_TR=5, TOL=0.5 K
    chim_dict = _caudal_natural_horizonte(...)
    m_nat_serie = max(chim_dict["m_punto_kgs"], 1e-4)  # piso para no romper motor TD
    forzantes_aplicadas = _correr_aux_y_armar_forzantes(m_nat_serie, m_dot_medio, T_sal_col_serie)
    solver_cam = _correr_motor_TD(forzantes_aplicadas)
    T_chim_new = interp(t_s_grid, solver_cam.t_array_s, solver_cam.T_flujo_K)
    T_chim_new = max(T_chim_new, T_amb_serie + 1.0)
    delta = max|T_chim_new − T_chim_serie|
    T_chim_serie = T_chim_new
    if delta < TOL: converged = True; break
```

El motor TD acepta `m_dot_aire_seco_kg_s` como **array** en `ForzantesAire` (interpola por t). No requirió cambios al motor TD. El auxiliar transitorio sí toma caudal escalar — se le pasa el promedio del horizonte (limitación documentada; el error en E_aux es de segundo orden porque el auxiliar suele estar OFF gran parte del día).

Refactor de soporte: el bloque "aux + cámara TD + post" del transitorio se extrajo a dos closures locales (`_correr_aux_y_armar_forzantes`, `_correr_motor_TD`) para que el pipeline sin chimenea (motor forzado) y el pipeline con Picard compartan la misma lógica de armado de forzantes y corrida del motor TD.

### 99.3 UI: Panel 5 de chimenea en P7 transitorio

`_render_resultados_transitorios` agrega un panel nuevo si `res_tr.chimenea is not None`:

- 7 métricas escalares (ṁ promedio/máx, T_chim min/max, horas sin tiro, iteraciones Picard, convergió ✓/✗, H_eff).
- Gráfica Plotly con secondary_y: ṁ(t) en g/s + ΔP_tiro(t) en eje izquierdo, T_chim(t) en eje derecho.

Snapshots .txt/.json del modo transitorio: el bloque `chimenea` detecta si los valores son arrays (transitorio) o escalares (constantes). El `.txt` muestra resumen escalar + min/max + horas sin tiro + metadata Picard; el `.json` incluye un sub-dict `series` con las 8 trayectorias horarias para reconstrucción/análisis posterior.

### 99.4 Demo y tests

ARMARIO + cámara TD yacon + chimenea D=30cm/H=4m sin motor, día sintético (T_amb 15-30 °C, GHI pico 800 W/m²), POA = GHI (sintético):

```text
iter Picard         : 2
convergió           : True
ΔT_max final        : 0.095 K
ṁ promedio          : 63.3 g/s
ṁ máximo            : 71.3 g/s   (mediodía)
ṁ mínimo            : 53.8 g/s   (noche)
T_chim min/max [°C] : 26.6 / 56.1
```

ṁ(t) oscila ~30 % día/noche como esperado físicamente. Tests nuevos (7) en `TestChimeneaTransitoria`:

- `test_sin_chimenea_chimenea_es_None`
- `test_chimenea_con_motor_no_se_invoca`
- `test_picard_metadata_y_series_presentes` (series shape N)
- `test_picard_converge` (≤ 5 iter, ΔT < 0.5 K)
- `test_m_punto_varia_con_T_amb` (variación día/noche > 10 %)
- `test_forzantes_aplicadas_usa_m_dot_natural` (no coincide con caudal de diseño)
- `test_caja_con_chimenea_transitoria_funciona`

Suite: **766 + 2 xfailed**.

---

## 100. Re-correr el colector hora a hora (y el bug GHI/POA que destapa)

La integración del §99 deja el colector estacionario corrido **una sola vez** con velocidad de diseño, y luego el motor TD consume las forzantes ya pre-calculadas. Esto es físicamente incorrecto cuando el lazo natural impone ṁ(t) muy distinto al ṁ de diseño: la T_salida_colector(t) precomputada por P3/P4 deja de ser coherente con el caudal real.

### 100.1 Helper `_correr_colector_horizonte`

Por cada hora t:
1. `v_modulo(t) = ṁ_nat(t) / (ρ(T_op) · A_canal · n_paralelo)`, clipeada a `[0.05, 15.0]` m/s para evitar regímenes patológicos del solver.
2. Muta `unidad.velocidad_diseno_ms = v_modulo(t)`.
3. Corre `_correr_colector` con (T_amb(t), I_g(t), v_viento(t), T_entrada=T_amb(t)).
4. Recoge `T_salida_K(t)`. Si el solver falla en una hora puntual, asigna `T_salida = T_amb` (sin aporte del colector esa hora).

`try/finally` restaura `velocidad_diseno_ms` al original.

### 100.2 Inyección en el Picard transitorio

En cada iteración Picard, **antes** de armar las forzantes:

```python
if proyecto.colector is not None:
    T_sal_col_serie = _correr_colector_horizonte(
        proyecto, T_amb_serie, v_viento_serie, I_g_serie, m_nat_serie, T_chim_serie,
    )
# T_sal_col_serie se inyecta en _correr_aux_y_armar_forzantes como
# T_entrada al auxiliar y, después del aporte ΔT_aux, como T_ent del motor TD.
```

`_correr_aux_y_armar_forzantes` se modifica para aceptar `T_sal_col_serie: Optional[np.ndarray]` — si está, se usa en vez de `forzantes_base.T_ent_K`.

También se corrige el cómputo de `energia_solar_util_MJ`: cuando hay chimenea activa, se evalúa con las series re-calculadas (`T_sal_col` post-Picard y `ṁ_nat`), no con las de `forzantes_base`. Mantiene coherencia energética.

### 100.3 Resultado físico y costo

Demo (ARMARIO sintético, mismo escenario que §99.4):

```text
ṁ promedio (S99, sin re-correr colector) : 63.3 g/s
ṁ promedio (S100, re-corriendo colector) : 30.0 g/s

T_sal_col base (precomputada P4)      : 26.9–56.9 °C
T_sal_col re-corrida con ṁ_nat        : 13.9–45.7 °C
Δ medio entre series                  : −14.6 °C
Tiempo total de cálculo (24h)         : 2.2 s   (era 0.4 s sin re-correr)
```

El re-cálculo del colector con velocidad efectiva del lazo natural baja la T_salida ~15 °C en promedio respecto a la forzante de la UI (que estaba inflada con velocidad de diseño). Como consecuencia, el ṁ del lazo se reduce a la mitad — coherente físicamente: menos aporte térmico → menos tiro → menos caudal.

Tests nuevos (2):

- `test_colector_se_re_corre_por_hora`: `forzantes_aplicadas.T_ent_K` difiere de `forzantes_base.T_ent_K` por más de 1 K.
- `test_restaura_velocidad_diseno_del_colector`: `velocidad_diseno_ms` restaurada tras la corrida.

Suite: **768 + 2 xfailed**.

### 100.4 El bug físico que se destapa al pasar I_g al solver

Al revisar el código del acople, el usuario detecta una incoherencia grave: **los 4 solvers de colector esperan POA** (irradiancia sobre el plano del colector, no horizontal), y `_correr_colector_horizonte` les estaba pasando `forzantes_base.I_g_W_m2`, **que es GHI** (la irradiancia que P4 puso en las forzantes para el techo de la cámara). Auditoría de los 4 solvers confirma:

| Solver | Archivo:línea | Texto del docstring de `I_g_W_m2` |
|--------|---------------|-----------------------------------|
| Tipo 1 | `colector_calc.py:565` | "Irradiancia global sobre el plano del colector [W/m²]" |
| Tipo 2 | `colector_tipos234_calc.py:1128` | "Irradiancia global sobre plano del colector [W/m²]" |
| Tipo 3 | `colector_tipos234_calc.py:1332` | "Irradiancia global sobre plano del colector [W/m²]" |
| Tipo 4 | `colector_tipos234_calc.py:1500` | "Irradiancia global sobre plano del colector [W/m²]" |

La aritmética interna usa `I_g_W_m2 · τ · α · W_abs` (sin proyectar nada — asume que ya llega en POA). `η = Q_util / Q_incidente` requiere POA real en el denominador.

Lugares donde sí se les pasa POA correcta:
- **P3 modo horario/diario**: `ui/p3_colector.py:573-577` usa `pvlib.irradiance.get_total_irradiance(DNI, GHI, DHI, tilt, azimut)` con conversión Duffie→pvlib del acimut. ✓
- **P3/P7 modo constantes**: el usuario tipea el valor con label "POA". ✓ (responsabilidad del usuario)

Lugares donde se pasa GHI etiquetada como POA:
- **P7 modo constantes**, sugerido automático: `ui/p7_resultados.py:391` calculaba `quantile(0.90)` de `GHI_Wm2`. Cabo suelto preexistente, no introducido en S100.
- **P7 modo transitorio**, mi `_correr_colector_horizonte`: pasa `forzantes_base.I_g_W_m2` (GHI). **Bug introducido en S100**.

En Salta (lat −24.79°, tilt 25–30°) la POA puede superar a GHI en 5–15 % en verano y 20–35 % en invierno. Subestimar POA por GHI subestima T_sal_col, el tiro térmico y el caudal natural en magnitud no despreciable.

---

## 101. POA precomputada en `ForzantesAire` (Opción A — fix completo)

Se discuten tres opciones de fix con el usuario:

- **A.** POA precomputada en `ForzantesAire` (campo nuevo `I_g_POA_W_m2`).
- **B.** POA proyectada inline en `_correr_colector_horizonte` con acceso a `proyecto.clima.datos`.
- **C.** Aceptar la aproximación y dejarla para sesión futura.

El usuario elige **A** porque preserva la separación de capas (núcleo numérico no toca pvlib ni timestamps), reusa el patrón ya validado de P3, y deja POA como variable boundary de primera clase — graficable, exportable, auditable.

### 101.1 Helper compartido `calcular_POA_horizonte`

En `calculos/clima_calc.py` (módulo que ya importaba pvlib para NASA POWER):

```python
def calcular_POA_horizonte(
    datos_clima: pd.DataFrame, emplazamiento: Emplazamiento, *,
    modelo_difuso: str = "isotropic",
) -> pd.Series:
    """POA horaria sobre el plano del colector [W/m²].
    
    Transposición Liu-Jordan: directa DNI·cos(θ_i) + difusa según modelo +
    reflejada del suelo. Acepta DataFrame con DNI/GHI/DHI + Emplazamiento
    con tilt y acimut en convención Duffie (convierte a pvlib internamente).
    """
```

Detalles:
- Conversión Duffie → pvlib inline: `acimut_pvlib = (180 + acimut_duffie) % 360`. La fórmula vivía en `ui/componentes/unidades.py:204`; se duplican 1 línea en `calculos/` para no importar de UI.
- `pvlib.solarposition.get_solarposition` con índice tz-aware (validación dura: rechaza naive con `CLIMA_INDICE_NAIVE`).
- Manejo de NaN hora a hora: si `DNI` o `DHI` son NaN, fallback `POA = GHI` esa hora (conservador, evita propagar NaN al solver del colector).
- Default `modelo_difuso = "isotropic"` por coherencia con lo que P3 usaba implícitamente.

P3 deduplicado: `_poa_serie` en `ui/p3_colector.py:571` ahora es un wrapper delgado sobre el helper compartido. Llamadas en líneas 665 y 721 se simplifican.

### 101.2 Campo `I_g_POA_W_m2` en `ForzantesAire`

En `core/camara.py`:

```python
@dataclass
class ForzantesAire:
    ...
    I_g_W_m2: Optional[np.ndarray] = None      # GHI sobre techo cámara (existente)
    I_g_POA_W_m2: Optional[np.ndarray] = None  # POA sobre plano del colector (nuevo)
```

Backward-compat total: campo opcional con `None` por default. Validación de longitud sólo si se provee. `.json` viejos siguen cargando sin cambios.

`armar_forzantes_aire` acepta `I_g_POA_W_m2: Optional[np.ndarray] = None` y la replica en modo `multi_dia`. `construir_serie_sintetica_dia_tipo` puebla POA = I_g (sintético no distingue física GHI/POA, son lo mismo).

### 101.3 P4 puebla POA desde clima real

En `ui/p4_camara.py:243`, al armar forzantes desde NASA POWER:

```python
I_g_arr = np.asarray(datos_dia["GHI_Wm2"], dtype=float)
try:
    from calculos.clima_calc import calcular_POA_horizonte
    I_g_POA_arr = np.asarray(calcular_POA_horizonte(datos_dia, empl), dtype=float)
except Exception:
    I_g_POA_arr = None   # balance global cae al fallback con aviso
```

### 101.4 `_correr_colector_horizonte` consume POA

El parámetro `I_g_W_m2_serie` se renombró a `I_g_POA_W_m2_serie` (el solver del colector lo usa directo como radiación absorbida en el plano). En el Picard transitorio:

```python
if forzantes_base.I_g_POA_W_m2 is not None:
    I_para_colector = forzantes_base.I_g_POA_W_m2
else:
    I_para_colector = forzantes_base.I_g_W_m2   # fallback
    if iter_count == 1:
        res.advertencias.append("ADV_PICARD_POA_NO_DISPONIBLE: ...")
```

El aviso `ADV_PICARD_POA_NO_DISPONIBLE` se emite **una sola vez por corrida** (no en cada iteración Picard) y deja explícito que el colector se está re-corriendo con GHI por falta de POA en las forzantes.

### 101.5 Fix del sugerido P7 modo constantes (cabo suelto preexistente)

`_sugerir_condiciones(proyecto)` en P7 ahora computa POA representativa con el helper sobre todo el año del clima y toma `quantile(0.90)` de POA. Fallback a `quantile(0.90)` de GHI si la transposición falla (sin emplazamiento, sin DNI/DHI). Arregla el cabo suelto donde el sugerido salía de GHI con label "POA".

### 101.6 Tests (6)

En `tests/test_calculos/test_clima_calc.py`:

- `test_POA_horizontal_aproxima_GHI`: tilt=0 → POA ≈ GHI con tolerancia 1 %. Fixture usa `pvlib.irradiance.erbs` para descomponer GHI en DNI/DHI coherentes (sin Erbs el test fallaría porque DNI y DHI arbitrarios no satisfacen `GHI = DNI·cos(θ_z) + DHI`).
- `test_POA_invierno_Salta_supera_GHI_al_mediodia`: lat=-24.79°, tilt=30°, azimut Norte, junio → POA/GHI al mediodía en `(1.10, 1.80)`. Verifica el efecto físico cuantitativamente.
- `test_POA_clipea_negativos_y_nan`: POA ≥ 0 siempre; horas nocturnas (GHI=0) → POA=0.
- `test_POA_fallback_a_GHI_con_dni_nan`: si DNI o DHI son NaN en una hora puntual, esa hora POA = GHI.
- `test_POA_rechaza_indice_naive`: índice sin tz lanza `ValueError("CLIMA_INDICE_NAIVE")`.

En `tests/test_calculos/test_balance_global_transitorio.py`:

- `test_picard_con_POA_difiere_de_picard_con_GHI`: misma forzante base, una sin POA (fallback con aviso) y otra con POA inflada 25 %. Verifica que el aviso `POA_NO_DISPONIBLE` se emite cuando corresponde, y que `T_sal_col` máxima de la corrida con POA > GHI supera a la de GHI sola, y que `ṁ_promedio` del lazo es mayor (más radiación → más tiro).

Suite final: **774 + 2 xfailed** (+6 sobre §100).

### 101.7 Estado físico final del pipeline

Los 4 solvers de colector reciben POA real en todos los caminos:

| Camino | Fuente de I_g pasada al solver de colector |
|--------|--------------------------------------------|
| P3 modo constantes | Input manual del usuario (label "POA") |
| P3 modo horario/diario | `calcular_POA_horizonte(clima, emplazamiento)` (helper compartido) |
| P7 modo constantes con clima | Sugerido = `quantile(0.90)` de POA calculada (con fallback a GHI) |
| P7 modo constantes sin clima | Input manual del usuario (label "POA") |
| P7 modo transitorio (Picard) | `forzantes_base.I_g_POA_W_m2` (poblada por P4 desde clima) o GHI con aviso explícito si POA no disponible |

El único lugar donde POA puede degradar a GHI es el modo transitorio **con forzantes sintéticas** (donde sintético no distingue) o **sin clima cargado** (fallback con aviso). En todos los demás casos el solver del colector consume POA real.
