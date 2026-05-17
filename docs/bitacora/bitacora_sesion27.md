# Bitácora — Sesión 27 (2026-05-15 / 2026-05-16)

**Tema:** Refactor mayor del motor termodinámico de cámara según el documento `docs/notas/balance de calor y masa en camara ampliado.md`. Consolidación del andamiaje del motor cinético (camara_calc_dinamico.py de S23) dentro del motor difusivo (camara_termodinamica.py de S20–S21), con pared 3-nodos, forzantes horarias, cp(X) variable y política B anti-rehumectación. Eliminación del motor cinético dual.

**Estado al cierre:** 632 tests pasan + 1 xfailed. UI consolidada (P4 binario Estático/Termodinámico, P7 limpio). Scripts de validación cruzada adaptados al motor difusivo. Sin commits aún.

---

## 55. Punto de partida y motivación

El documento `docs/notas/balance de calor y masa en camara ampliado.md` (escrito por el usuario para esta sesión) detalla el balance acoplado que se quería en el motor termodinámico: pared en 3 nodos (T_cam_int, T_cam_ext) con `h_int + k/e + h_w` separados, cp del producto variable como `(c_ps + c_pa·X)`, balance de masa de agua via difusión `R = h_d·A_prod·(W_sat(T_prod) − W_cam)`, forzantes horarias de aire (T_sal_col, ω_amb, T_amb, v_viento).

Estado previo en el código (S26):

- `camara_termodinamica.py` (S20–S21) — motor difusivo con `ω_sup = ω_sat(T_prod)·a_w_GAB(X)`, balance entálpico riguroso, pared colapsada en `U_muros` único, boundary constante.
- `camara_calc_dinamico.py` (S23) — motor cinético Lewis/Page con sistema 5×5 fsolve, forzantes horarias, política B, pared 3-nodos, eventos. Inconsistente con el espíritu del spec ampliado (usa cinética empírica en vez de difusión termodinámica).

Decisión arquitectónica acordada con el usuario en discusión inicial:

| Decisión | Resultado |
|---|---|
| Balance de energía | Mantener formulación entálpica rigurosa (no la `m·cp·ΔT` simplificada del spec) |
| Evaporación | Mantener `ω_sup = ω_sat·a_w_GAB(X)` (no `a_w=1` del spec — captura período de velocidad decreciente) |
| Psicrometría | Mantener Buck 1981 (no Threlkeld 1973 del spec — Buck tiene ~8 % menos error contra ASHRAE) |
| Forzantes | Implementar sintéticas + reales |
| `camara_calc_dinamico.py` | Borrar; mover su andamiaje (forzantes, fsolve, política B, eventos) a `camara_termodinamica.py` |

El refactor se ejecutó en 4 fases secuenciales con suite verde al cierre de cada una.

---

## 56. Fase 1 — Pared 3-nodos en `resolver_estado_camara`

**Cambio matemático**: la cascada `1/U_muros = 1/h_int + esp/k_aisl + 1/h_w` queda calculada dentro del solver. T_cam_int y T_cam_ext se reconstruyen como post-cómputo a partir de Q_pared:

```
T_cam_int = T_flujo − Q_pared / (h_int · A_cuerpo)
T_cam_ext = T_amb   + Q_pared / (h_w   · A_cuerpo)
```

Observación clave del análisis previo: el sistema algebraico **sigue siendo 2×2** (T_flujo, ω_flujo). T_cam_int y T_cam_ext no son incógnitas independientes — son lineales en T_flujo una vez fijos los coeficientes. El valor real que aporta exponer estos nodos es:

1. Diagnóstico (T_int y T_ext son observables).
2. Variabilidad de h_w con v_viento(t) en Fase 2 (con U_muros lumped no era posible).
3. Base para acoplar radiación al cielo en una iteración futura.

`EstadoCamara` gana 3 campos: `T_cam_int_K`, `T_cam_ext_K`, `U_pared_W_m2K`. Firma de `resolver_estado_camara` elimina `U_muros_W_m2K` y agrega `h_w_W_m2K`, `k_aisl_W_mK`, `esp_cam_m`. Wire-up en `_calcular_termodinamico` deriva `k_aisl/esp_cam` a partir del `U_muros` del data model en condiciones de diseño (h_w default a v_viento=2 m/s).

**Tests**: 5 nuevos. Verifican balance estacionario de pared (`h_int·(T_f−T_ci) = (k/e)·(T_ci−T_ce) = h_w·(T_ce−T_amb)`), orden `T_flujo > T_ci > T_ce > T_amb`, consistencia de U_total.

Suite al cierre: **652 pasan** (+5 nuevos), 1 xfailed.

---

## 57. Fase 2 — Forzantes horarias + cp(X) + política B

### 57.1 Firma de `simular_secado`

Antes:
```python
def simular_secado(*, T_ent_K, omega_ent_kg_kg, m_dot_as_kg_s, T_amb_K, cp_prod_J_kgK, ...)
```

Después:
```python
def simular_secado(*, forzantes: ForzantesAire, c_ps_J_kgK, T_max_admisible_K=None, ...)
```

Los 4 escalares de boundary se reemplazan por una única `ForzantesAire` con series horarias (`t_s`, `T_ent_K`, `omega_ent`, `m_dot_aire_seco_kg_s`, `T_amb_K`, `v_viento_ms`). El motor interpola linealmente en cada evaluación del RHS y recalcula `h_w(v_viento(t))` por McAdams. `h_conv` interior y `K_m` quedan congelados al inicio (decisión §24.10 mantenida — variación <5 % en rango operativo).

### 57.2 Capacidad térmica dinámica

`cp_prod_J_kgK` constante → `c_ps_J_kgK` (sólido seco). En el RHS:

```python
C_thermal = m_seco_prod_kg * (c_ps_J_kgK + _CP_AGUA_LIQ_J_KGK * X_safe)
dT_dt = (q_prod − m_dot_w · L_v) / C_thermal
```

Equivalente algebraicamente a `m_prod · cp_efectivo` con `cp_efectivo(X) = (c_ps + c_pa·X)/(1+X)`, pero evita el doble cómputo y respeta el modelo del spec ampliado.

### 57.3 Política B anti-rehumectación

Si la solución algebraica entrega `ṁ_w < 0` (fuerza motriz invertida — el aire entrante tiende a condensar sobre el producto), se re-resuelve con `K_m = 0` para forzar `ṁ_w = 0` y `dX/dt = 0`. Se cuenta el tiempo bajo este régimen en `horas_clipeo_nocturno_s`.

Implementación en helper `_resolver_con_politica_B`, llamado tanto en el RHS de la integración como en la reconstrucción a posteriori para que las trayectorias guardadas sean coherentes con el régimen efectivamente integrado.

### 57.4 Eventos

`event_X_obj` (terminal, ya existía) + nuevo `event_T_max` opcional (terminal, direction +1, status='dano_termico'). Diagnóstico adicional: `T_max_alcanzada_K`, `horas_HR_alta_s` (tiempo con HR_flujo > 95 %).

### 57.5 `ResultadoMotorTermodinamico` extendido

Nuevos campos: `T_cam_int_K`, `T_cam_ext_K`, `U_pared_W_m2K`, `HR_flujo` (arrays); `horas_clipeo_nocturno_s`, `horas_HR_alta_s`, `T_max_alcanzada_K` (escalares).

**Tests**: 8 nuevos. Forzantes senoidales modulan T_prod con std > 1 K; mayor v_viento → mayor U_pared; aire saturado + producto seco → no rehumecta (X final ≤ X inicial); cp(X) variable converge sin NaN; T_max bajo dispara `status='dano_termico'`.

Suite al cierre: **660 pasan** (+8 nuevos), 1 xfailed.

---

## 58. Fase 3 — Helpers de construcción de forzantes + wire-up opcional

### 58.1 `construir_serie_sintetica_dia_tipo` (nuevo en `balance_global.py`)

```
T_sal_col(h) = T_promedio + T_amplitud · sin(2π·(h − hora_pico + 6) / 24)
T_amb(h)     = T_amb_promedio + T_amb_amplitud · sin(...)
```

Con clamp `T_sal_col(h) ≥ T_amb(h)` hora a hora (sin radiación, el colector no puede enfriar el aire por debajo del ambiente). Reusa `armar_forzantes_aire` existente para la replicación multi-día.

### 58.2 `armar_forzantes_aire` existente — reuso para modo "real"

`armar_forzantes_aire(modo="diario"|"multi_dia"|"anual", T_salida_colector_K, omega_ambiente, T_amb_K, v_viento_ms, ...)` (S23) ya producía `ForzantesAire` desde series horarias. Se reusa para construir forzantes reales a partir del clima NASA POWER (P2) + T_sal_col(t) horaria del colector (P3).

### 58.3 Wire-up opcional en `calcular_camara`

```python
def calcular_camara(camara, ..., forzantes_aire: Optional[ForzantesAire] = None):
    if camara.modo_calculo == "termodinamico":
        return _calcular_termodinamico(..., forzantes_aire=forzantes_aire)
```

Si `forzantes_aire is None`, el wire-up arma degeneradas (2 puntos constantes) → comportamiento histórico. Si se pasa una `ForzantesAire`, el motor la usa tal cual.

**Tests**: 9 nuevos. Helper sintético (estructura, pico al mediodía, clamp T_col ≥ T_amb, multi-día replica exacto). Wire-up con `forzantes_aire=None` (T_flujo plano) vs forzantes senoidales (T_flujo modula >3 K). Capa fina ignora forzantes_aire sin fallar.

Suite al cierre: **669 pasan** (+9 nuevos), 1 xfailed.

---

## 59. Fase 4 — UI P4 y P7 + tests integrales + eliminación del motor cinético

### 59.1 P4 — selector de motor reducido a 2 opciones

Antes (3 opciones): `Capa fina Estático` / `Capa fina Dinámico` / `Termodinámico`.
Después (2 opciones): `Capa fina Estático` / `Termodinámico (balance acoplado)`.

El modo "Capa fina Dinámico" del motor cinético desapareció. Su rol (forzantes horarias + multi-día) quedó absorbido por el termodinámico consolidado.

### 59.2 P4 — sub-controles del modo termodinámico

Tres modos de forzantes:

- **Constantes (rápido)** — `forzantes_aire=None`, comportamiento histórico equivalente a una corrida puntual.
- **Día sintético (senoidal)** — `construir_serie_sintetica_dia_tipo(T_amplitud=15 K, T_amb_amplitud=5 K)`.
- **Día real (clima + colector)** — extrae `T_sal_col(t)` de `st.session_state["p3_eval"]` y `ω_amb(t)`, `T_amb(t)`, `v_viento(t)` del clima NASA POWER. Si P3 o P2 no están listos, cae a sintético con warning.

Horizonte de 1 a 21 días para los modos sintético y real (replica el día tipo). Métricas extra en el display: T_max producto, horas anti-rehumectación, horas HR > 95 %. Gráfica nueva `_grafica_secado_termodinamico` con 4 paneles: X(t), temperaturas (T_prod, T_aire, T_pared int/ext), HR_flujo y banda 95 %, tasa de evaporación.

Helpers obsoletos eliminados de P4: `_params_motor_dinamico`, `_geometria_motor_dinamico`, `_construir_forzantes_p4`, `_grafica_secado_dinamico`.

### 59.3 P7 — limpio de referencias al motor cinético

- Bloque "Cámara — Motor Dinámico" eliminado (~50 líneas).
- `_resumen_camara` y `_texto_resultados_completo` simplificados (sin rama `ResultadosCamaraDinamico`).
- Tabla de resultados unificada.

### 59.4 Eliminaciones definitivas

| Archivo | Acción |
|---|---|
| `calculos/camara_calc_dinamico.py` | borrado |
| `tests/test_calculos/test_camara_calc_dinamico.py` | borrado (38 tests) |
| `core/camara.ResultadosCamaraDinamico` | borrado (dataclass) |

### 59.5 Test integral end-to-end

Nueva clase `TestIntegralEndToEnd` en `test_balance_global.py`: cámara armario + forzantes sintéticas 3 días → trayectorias coherentes (X final < X inicial, T_flujo oscila con std > 2 K, sin NaN, `T_cam_int ≤ T_flujo` en todo punto).

Suite al cierre: **632 pasan** (perdimos 38 del dinámico borrado, ganamos 1 integral), 1 xfailed.

---

## 60. Adaptación de los scripts de validación cruzada S26

`validacion_cruzada_yacon.py` y `probe_motor_C_yacon.py` (raíz, untracked desde S26) referenciaban `calcular_secado_dinamico` borrado. Adaptados al motor consolidado:

### 60.1 `validacion_cruzada_yacon.py` — Motor C redefinido

| Motor | Antes (S26) | Después (S27) |
|---|---|---|
| A | capa fina estático | capa fina estático (sin cambio) |
| B | termodinámico TD constantes | termodinámico TD constantes (sin cambio) |
| C | dinámico cinético Lewis/Page con forzantes | **termodinámico TD con forzantes sintéticas día/noche** |

La comparación útil que queda es:

- **A → B**: efecto del balance de masa del aire (cuello de botella por saturación). En el escenario yacón (T_op=60 °C, 5 kg, 0.060 kg/s), A da 0.10 h vs B da 58.46 h — A subestima groseramente.
- **B → C**: efecto del ciclo día/noche con forzantes sintéticas (±15 K en T_sal_col, ±5 K en T_amb). En este caso C da 58.82 h (+0.6 %) — el ciclo no domina porque el T_op promedio se mantiene alto y la política B no se activa (`horas_clipeo = 0`).

### 60.2 `probe_motor_C_yacon.py` — sonda en motor TD

Grilla de 10 escenarios. Resultados clave:

| T_op | HR | masa | conv | t_h | h_clipeo |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 25 °C | 0.15 | 5 kg | NO | — | 0 |
| 25 °C | 0.15 | 1 kg | SÍ | 17.81 | 0 |
| 40 °C | 0.15 | 5 kg | SÍ | 80.07 | 0 |
| 60 °C | 0.15 | 5 kg | SÍ | 58.82 | 0 |
| 60 °C | 0.30 | 5 kg | SÍ | 83.61 | **3.0** |

A 25 °C con 5 kg el motor TD no converge en 96 h (la combinación HR/masa/caudal es marginal). A 40 °C+ converge. A 60 °C/30 % HR aparecen 3 h de política B activa — esperable porque el aire entrante está cerca de saturación nocturna.

**Diferencia con la sonda S26**: el motor cinético borrado partía de `dX/dt = −k·(X−X_eq)` con `k(25 °C) = 0.217 min⁻¹` (Shi 2013), no sensible a la carga de aire. El motor TD difusivo sí siente el cuello de botella — por eso la grilla de S27 muestra no-convergencia en escenarios que S26 daba como triviales y viceversa.

---

## 61. Decisiones de diseño documentadas para futuro

### 61.1 Por qué no se siguió la letra del spec

El usuario propuso inicialmente cuatro cambios "puristas" según el documento `balance de calor y masa en camara ampliado.md`:

1. Balance de aire `m·cp·ΔT + h·A·(T_f−T_ci) + h·A_prod·(T_f−T_prod) = 0` (sin término latente explícito en el aire).
2. Evaporación con `a_w = 1` (superficie de agua libre, sólo período de velocidad constante).
3. Psicrometría Threlkeld 1973 (`p_s(T) = 610.7·10^(8.2·(T−273)/T)`).
4. Forzantes constantes (sin ciclo día/noche).

Tras la presentación de los trade-offs (diferencias numéricas, equivalencia matemática, blast radius), las cuatro se reconsideraron:

| Item | Spec | Decisión final | Razón |
|---|---|---|---|
| Balance aire | `m·cp·ΔT` | Entalpía rigurosa | Ya escrita y validada; difiere <2 % del spec |
| `a_w` superficie | 1 | GAB(X) | a_w=1 ignora período higroscópico (X→0 imposible físicamente) |
| Psicrometría | Threlkeld 1973 | Buck 1981 | Threlkeld tiene ~8 % de error contra ASHRAE, Buck <0.05 % |
| Forzantes | constantes | sintéticas + reales | El usuario pidió B+C explícitamente al ver opciones |

**Lección de proceso**: el usuario es muy receptivo a comparaciones numéricas concretas. Mostrar la tabla de errores Buck vs Threlkeld vs ASHRAE en tres temperaturas cambió la decisión inmediatamente. Mantener esta práctica para futuros cambios físicos.

### 61.2 Cabos sueltos pendientes

- **Modo "Día real" en P4** — implementado. Probarlo en vivo cuando haya un proyecto con P3 calculado y clima descargado.
- **Repetir validación cruzada con manzana/durazno** (S25 §47, S26 §54) — productos con Arrhenius. El motor TD difusivo no usa Arrhenius (usa K_m + GAB), así que la comparación cinético-vs-difusivo ya no aplica como en S26. Replantear el sentido del benchmark.
- **Test de regresión Page MR=1** (S26 §54) — obsoleto. El bug estaba en el motor cinético borrado. No corresponde portar el test.
- **`t_max_s` configurable desde UI** (S24 §44) — sigue pendiente.
- **Commit y push** del trabajo acumulado de S23 + S24 + S25 + S26 + S27.
- **Repo GitHub público.**

---

## 62. Estado de archivos

| Archivo | Acción | Detalle |
|---|---|---|
| `calculos/camara_termodinamica.py` | reescrito | 4×4 algebraico, forzantes horarias, política B, cp(X), eventos T_max |
| `calculos/camara_calc.py` | modificado | wire-up con forzantes opcionales, decomposición de pared |
| `calculos/balance_global.py` | modificado | nueva `construir_serie_sintetica_dia_tipo` |
| `core/camara.py` | modificado | `ResultadosCamaraDinamico` eliminado |
| `ui/p4_camara.py` | reescrito | selector binario, 3 modos forzantes, gráfica TD nueva |
| `ui/p7_resultados.py` | modificado | sin rama dinámica, tabla unificada |
| `calculos/camara_calc_dinamico.py` | **borrado** |  |
| `tests/test_calculos/test_camara_calc_dinamico.py` | **borrado** | 38 tests |
| `tests/test_calculos/test_camara_termodinamica.py` | extendido | +13 tests (5 Fase 1 + 8 Fase 2) |
| `tests/test_calculos/test_balance_global.py` | extendido | +10 tests (9 Fase 3 + 1 integral) |
| `validacion_cruzada_yacon.py` | adaptado | Motor C ahora TD sintético |
| `probe_motor_C_yacon.py` | adaptado | sonda en motor TD |

Suite total: **632 passed, 1 xfailed** (sin regresiones).
