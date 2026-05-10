# Bitácora — Sesión 20 (2026-05-09)

**Tema:** Modelo termodinámico transitorio de cámara de secado — diseño, decisiones de fondo y cierre de Sub-tarea 1 (ampliación de psicrometría).

**Estado al cierre de la sesión:** S1, S2, S3 y S4 (a+b) cerradas. Tests nuevos en S20: `test_psicrometria.py` 82 (38 base S18 + 44 nuevos), `test_camara_termodinamica.py` 40 (21 solver + 19 motor), `test_camara_dispatcher.py` 10, +9 en `test_camara.py` (4 modo + 5 T_inicial). Suite global: **590 passed, 1 xfailed**. Quedan pendientes S5 (curvas dinámicas en P7) y S6 (validación cruzada).

---

## 24. Decisiones técnicas — Sesión 20

### 24.1 Decisión: segundo motor de cámara, no reemplazo del existente

El modelo de capa fina (Lewis / Page / Henderson-Pabis / Midilli / Logarítmico) de S15 se mantiene como motor "rápido" o "simplificado" de Pestaña 4. Se agrega un **segundo motor termodinámico** que resuelve el balance acoplado de calor y masa con dinámica transitoria, en paralelo al primero. Switch de modo en `Camara.modo_calculo: Literal["capa_fina", "termodinamico"]`. Default: `"capa_fina"` para conservar comportamiento actual del proyecto.

Razón de la decisión: los modelos de capa fina son útiles cuando el usuario tiene parámetros (k, n, a, b, c) ajustados experimentalmente para su producto. El motor termodinámico es preferible cuando se quiere predecir comportamiento sin esos parámetros, partiendo solo de propiedades termofísicas y geometría.

### 24.2 Hipótesis físicas del modelo termodinámico

Las elecciones se fijaron luego de discusión iterativa entre el desarrollador y Claude:

| Aspecto | Elección | Justificación breve |
| :--- | :--- | :--- |
| Formulación balance flujo | Entalpía de aire húmedo h(T,ω) acoplada | Más limpia que sensible + latente separados; reusa `entalpia_aire_humedo` |
| Cinética de evaporación | Modelo difusivo: ṁ_w = h_m·A_prod·(ω_sat(T_prod)·a_w − ω_flujo) | Más físico que capa fina; permite predicción sin parámetros ajustados |
| Régimen | Transitorio: 2 EDOs (T_prod, X_prod) + 4 algebraicas | Captura dinámica real |
| Estado del aire en cámara | Mezcla perfecta (CSTR): ω_flujo = ω_salida | Coherente con hipótesis 2 (un solo nodo de aire); conservador |
| Capacitancia térmica de paredes | Despreciada (cuasi-estacionario) | Consistente con motor de colectores |
| Radiación interna paredes↔producto | Despreciada (v0) | Secador indirecto, ΔT pequeña, evita parámetros adicionales |
| Detección de t_secado | Event detection de solve_ivp (X_prod = X_obj) | Una integración vs múltiples con brentq externo |

### 24.3 Sistema de ecuaciones (caso secador armario, esquema 7.b)

**Variables de estado** (EDOs): `[T_prod, X_prod]`.
**Variables algebraicas** (sistema implícito por paso): `[T_flujo, ω_flujo, T_cam_int, T_cam_ext]`.

**EDOs:**

```
dX_prod/dt = − ṁ_w / m_seco_prod
m_prod·cp_prod · dT_prod/dt = h_conv·A_prod·(T_flujo − T_prod) − ṁ_w · L_v(T_prod)
```

**Sistema algebraico (en cada paso):**

```
(a) Balance de masa:
    ω_flujo = ω_ent + ṁ_w / ṁ_as
    con ṁ_w = h_m·A_prod·(ω_sat(T_prod)·a_w(X_prod) − ω_flujo)

(b) Balance de energía del flujo (entalpía):
    ṁ_as·[h(T_flujo,ω_flujo) − h(T_ent,ω_ent)]
        = − h_conv·A_cuerpo·(T_flujo − T_cam_int)
          − h_conv·A_prod·(T_flujo − T_prod)
          + ṁ_w · h_v(T_prod)

    Nota de signo: el último término es POSITIVO. El vapor evaporado sale
    del producto a T_prod y se incorpora al aire llevando consigo su
    entalpía h_v(T_prod) = L_v0 + cp_v·(T_prod − T_ref), referenciada a
    T_ref para que sea consistente con la convención de entalpia_aire_humedo.
    (Una versión inicial de esta ecuación tenía el signo invertido — corregido
    al implementar S2.)

(c) Conducción en paredes:
    h_conv·A·(T_flujo − T_cam_int) = (k/e)·A·(T_cam_int − T_cam_ext)

(d) Convección externa:
    (k/e)·A·(T_cam_int − T_cam_ext) = h_w·A·(T_cam_ext − T_amb)
```

**Justificación del cuasi-estacionario en el aire:** el tiempo de residencia del aire en la cámara (segundos) es órdenes de magnitud menor que el tiempo de secado (horas), por lo que el balance del aire colapsa de EDO a algebraico.

### 24.4 Sub-tarea S1 (CERRADA) — ampliación de `calculos/psicrometria.py`

**Funciones agregadas** (todas con tests, 44/44 verde local):

| Función | Modelo | Referencia |
| :--- | :--- | :--- |
| `calor_latente_vaporizacion(T_K)` | Lineal: L_v = 2.501e6 − 2370·(T−T_ref) | Rogers & Yau (1989) |
| `cp_aire_humedo(omega)` | cp = cp_as + ω·cp_v | Mezcla ideal de gases |
| `volumen_especifico_aire_humedo(T_K, omega, P_Pa)` | v = R·T·(1+ω/ε)/P | Gas ideal, ASHRAE F2021 |
| `densidad_aire_humedo(T_K, omega, P_Pa)` | ρ = (1+ω)/v | — |
| `temperatura_bulbo_humedo(T_K, omega, P_Pa)` | Saturación adiabática vía brentq | ASHRAE F2021 §1 |
| `actividad_agua_desde_X_GAB(X, X_m, C, K)` | Inversión analítica cuadrática | van den Berg & Bruin (1981) |
| `coef_transferencia_masa_chilton_colburn(h_conv, T_K, ω, P, Le)` | h_m = h/(ρ·cp·Le^(2/3)) | Incropera & DeWitt §6.7 |

**Constantes promovidas a nivel de módulo:** `_CP_AIRE_SECO=1006`, `_CP_VAPOR=1805`, `_LV_0=2_501_000`, `_T_REF=273.15`, `_R_AIRE_SECO=287.058`, `_K_LV=2370`. Antes vivían dentro de `entalpia_aire_humedo`. Se promovieron porque las funciones nuevas las comparten.

**Nuevo import:** `from scipy.optimize import brentq` (usado en T_wb).

### 24.5 Notas técnicas relevantes para futuras sesiones

1. **T_wb por brentq, no por punto fijo amortiguado.** Versión inicial con iteración amortiguada oscilaba a 40 °C / HR=30 %. Brentq con bracket `[T_dp − 0.5, T_db]` converge en < 20 iteraciones siempre. El bracket es válido porque el residuo `f(T_wb) = cp·(T_db−T_wb) − (ω_sat(T_wb)−ω)·L_v(T_wb)` cambia de signo: en T_db es < 0 y en T_dp es > 0.

2. **T_wb termodinámica vs saturación adiabática.** ASHRAE define la "T_wb termodinámica" incluyendo entalpía del agua líquida que abandona el sistema. Esta función resuelve "T de saturación adiabática" pura, que es la magnitud físicamente correcta para el balance de cámara (T a la que tiende el producto en régimen de tasa constante de secado). Diferencia: < 1 °C en 5–80 °C. El test ASHRAE 50 °C / HR=20 % usa tolerancia de 1 °C.

3. **Inversión analítica de GAB.** La cuadrática `X(C−1)·u² + [X_m·C − X(C−2)]·u − X = 0` con `u = K·a_w` tiene siempre dos raíces reales (discriminante > 0 garantizado para C > 1). De las dos, la positiva es la física (producto de raíces = c/a < 0). Test round-trip pasa con tolerancia 1e-9 para 24 combinaciones (4 productos × 6 a_w). Caso degenerado C=1 manejado con cuadrática propia. Si X excede el rango GAB (resulta a_w > 1), lanza `PSICRO_GAB_AW_FUERA_RANGO`.

4. **`densidad_aire_humedo` no estaba en la propuesta original.** Se agregó porque `coef_transferencia_masa_chilton_colburn` la necesita; separarla en función propia mejora testabilidad.

### 24.6 Pendientes — sub-tareas restantes para completar el motor termodinámico

| Sub-tarea | Descripción | Estado |
| :---: | :--- | :---: |
| S1 | Ampliar `calculos/psicrometria.py` (T_wb, L_v, v, ρ, inv-GAB, h_m) | **CERRADA** |
| S2 | Diseñar y validar el solver algebraico de cámara (4 ecuaciones) — función pura, testeable aislada | **CERRADA** |
| S3 | Construir el RHS y motor termodinámico completo con `solve_ivp` + event detection | **CERRADA** |
| S4a | Modificar dataclass `Camara` + `CargaProducto`, despachador `calcular_camara`, wire-up backend con motor termodinámico | **CERRADA** |
| S4b | Wire-up de UI en Pestaña 4 (selectbox de modo, T_prod_inicial opcional, gráfica básica termodinámica) | **CERRADA** |
| S5 | Actualizar Pestaña 7 para visualizar curvas dinámicas (T_prod, T_flujo, HR_flujo, ω_flujo) | Pendiente |
| S6 | Validación cruzada entre los dos motores (capa fina vs termodinámico) en casos donde deberían coincidir aproximadamente | Pendiente |

### 24.7 Pendiente independiente: `cp_producto` al catálogo — REVISADO al cerrar S4a

**Decisión final (S4a):** NO se agrega `cp_producto_J_kgK` como campo nuevo al catálogo. Se usa el campo existente `propiedades_basicas.calor_especifico_seco` (cp del sólido seco, ya presente para manzana, charqui, etc.) y se calcula el cp efectivo on-the-fly en `_calcular_termodinamico`:

```
cp_efectivo = (X_med · cp_w + cp_seco) / (1 + X_med),  X_med = (X_in + X_obj)/2
```

Justificación: una sola fuente de verdad en el catálogo; el cp efectivo varía ~50 % entre X=4 y X=0.15, pero la inercia térmica del producto solo importa en la transición temprana (luego dT/dt ≈ 0), así que la aproximación constante a X media es suficiente para prediseño. Si en S6 vemos que la aproximación es insuficiente, migramos a `cp_func: Callable[[X], float]` sin tocar la API de S3 (opción C de la decisión).

Fallback si el producto no tiene `calor_especifico_seco` en catálogo: 1500 J/(kg·K) con advertencia `CAM_TD_CP_SECO_FALTA`.

(Los valores típicos de la tabla original — frutas 3500–3900, carnes 3200–3500, etc. — son de cp del producto FRESCO con su agua, equivalentes al cp efectivo a X inicial. Quedan como referencia documental pero no se cargan al catálogo.)

### 24.8 Validación experimental: postergada

El desarrollador dispone de mediciones de secadores reales pero la validación cruzada con datos experimentales se posterga. No es bloqueante para v0 del motor termodinámico.

### 24.9 Sub-tarea S2 (CERRADA) — solver algebraico de cámara

**Archivo nuevo:** `calculos/camara_termodinamica.py` (separado de `camara_calc.py` que sigue siendo el motor capa fina).

**API expuesta:**

| Símbolo | Tipo | Descripción |
| :--- | :--- | :--- |
| `EstadoCamara` | `@dataclass(frozen=True)` | Resultado: `T_flujo_K`, `omega_flujo_kg_kg`, `m_dot_w_kg_s`, `q_prod_W`, `q_pared_W` |
| `resolver_estado_camara(...)` | función pura | Resuelve el sistema 4×4 dado (estado del producto, boundary, geometría, propiedades) |

**Decisión de diseño 1 — cascade analítico, sin `fsolve`:** las 4 ecuaciones son resolubles en forma cerrada cuando se fijan `h_conv` y `K_m` al inicio del paso, porque (a) es lineal en ω_flujo y (b) es lineal en T_flujo (la entalpía `h(T,ω) = cp_hum(ω)·(T−T_ref) + ω·L_v0` es afín en T). Costo O(1) por llamada, sin warm-start, sin fallos de convergencia. La no-linealidad real (h_conv evaluado a T_película) se delega a S3.

**Decisión de diseño 2 — opción A para v0 (`U_muros` global):** el solver consume directamente `U_muros_W_m2K` (que ya existía en `ConstruccionCamara`) en lugar de descomponer en h_conv_int + k/e + h_w. Consecuencia: T_cam_int y T_cam_ext NO se reportan en v0. Si se necesitan en S5 (visualización) se migra a opción B.

**Decisión de diseño 3 — `K_m` como conductancia másica directa [kg/(m²·s)]:** el solver recibe `K_m_kg_m2s = ρ·h_m_chilton`, no `h_m` en m/s. Razón: la fuerza impulsora del balance es Δω y el flujo debe salir en kg/s; pasar K_m directamente evita ambigüedad de unidades y mantiene la función "pura algebraica" sin acoplarse a propiedades termodinámicas internamente. Es responsabilidad del llamador (S3) calcular ρ con (T_ent, ω_ent, P) y multiplicar.

**Cascade de cuatro pasos:**

1. ω_sup = ω_sat(T_prod, P) · a_w(X_prod), con clip a `[0, 1]` por tolerancia de la inversión GAB.
2. ω_flujo = (ṁ_as·ω_ent + K_m·A_prod·ω_sup) / (ṁ_as + K_m·A_prod)  ← lineal directo
3. ṁ_w = ṁ_as·(ω_flujo − ω_ent)  ← signo: + evaporación, − condensación
4. T_flujo = [ṁ_as·c_h·T_ref + ṁ_as·(h_ent − ω_flujo·L_v0) + UA·T_amb + h·A_p·T_prod + ṁ_w·h_v(T_prod)] / (ṁ_as·c_h + UA + h·A_p)

donde c_h = cp_hum(ω_flujo) y h_v(T_prod) = L_v0 + cp_v·(T_prod − T_ref) (consistente con la convención de `entalpia_aire_humedo`).

**Bug de signo encontrado y corregido durante S2:** la ecuación (b) tal como estaba escrita en §24.3 tenía el último término con signo negativo (`− ṁ_w·h_v(T_prod)`). Físicamente debe ser **positivo**: el vapor sale del producto a T_prod e ingresa al aire llevando consigo su entalpía. Verificación física: con sólo evaporación (sin pérdidas, sin convección sensible), h_sal debe ser > h_ent porque el aire ganó masa de vapor — sólo se cumple con signo +. Corregido en los 3 lugares (código, test que pasaba tautológicamente, ecuación de §24.3).

**Tests (21 totales) en `tests/test_calculos/test_camara_termodinamica.py`:**

| Clase | n | Cobertura |
| :--- | :---: | :--- |
| `TestEstadoCamaraBasico` | 4 | Estructura del resultado, T_flujo en bracket (T_amb, T_ent), ω_flujo > ω_ent en evaporación, signos de q |
| `TestCasosLimite` | 7 | K_m=0 sin evap, a_w=0 con condensación, equilibrio másico, caudal alto → aire pasa, U_muros=0 aislante perfecta, sin drivers térmicos, T_prod > T_ent calienta al aire |
| `TestBalancesCierran` | 2 | Residuos de (a) y (b) ≈ 0 (precisión doble flotante: < 1e-9 y < 1e-6 W respectivamente) |
| `TestValidacionEntradas` | 8 | Errores duros para 7 parámetros + clipeo silencioso de a_w > 1 |

**Notas para S3:**

1. **No-linealidad pendiente:** h_conv y K_m dependen de T_película = (T_flujo + T_prod)/2, pero el solver los recibe como inputs. En el RHS de `solve_ivp` hay dos opciones: (i) iteración punto-fijo de 2-3 pasos por llamada (más preciso), (ii) congelar h_conv y K_m durante el paso de integración y dejar que `solve_ivp` controle el error vía el paso adaptativo (más rápido, posiblemente suficiente para prediseño).

2. **El estado del producto entra como input externo:** S2 no resuelve el balance del producto (EDO en T_prod, X_prod). Eso es S3 — `resolver_estado_camara` se llama una vez por evaluación del RHS para obtener ṁ_w y q_prod, que alimentan dT_prod/dt y dX_prod/dt.

3. **Event detection X_prod = X_obj:** trivial con `events=` de `solve_ivp` definiendo `e(t, y) = y[1] - X_obj` con `terminal=True`.

### 24.10 Sub-tarea S3 (CERRADA) — motor termodinámico transitorio

**Archivo:** `calculos/camara_termodinamica.py` (mismas dependencias que S2 + numpy + scipy.integrate).

**API expuesta:**

| Símbolo | Tipo | Descripción |
| :--- | :--- | :--- |
| `ResultadoMotorTermodinamico` | `@dataclass(frozen=True)` | Series temporales (T_prod, X_prod, T_flujo, ω_flujo, ṁ_w, q_prod, q_pared) + t_secado_s + status + masa_evaporada_total + advertencias |
| `simular_secado(...)` | función pura | Integra las EDOs (T_prod, X_prod) con `solve_ivp` LSODA + event detection X_prod=X_obj |

**Decisión clave (opción ii):** `h_conv` y `K_m` se reciben como inputs **fijos** y se mantienen congelados durante toda la simulación. El llamador (S4) los computa con T_película de referencia. Razón: la variación de h_conv con T es < 5 % en el rango operativo (∝ T^0.3 vía k_aire); `solve_ivp` adaptativo absorbe el error residual. Si en S6 se ve insuficiente, migramos a iteración punto-fijo interna.

**EDOs integradas:**

```
dX_prod/dt = − ṁ_w / m_seco_prod
m_prod·cp_prod · dT_prod/dt = q_prod − ṁ_w · L_v(T_prod)
```

donde `m_prod(t) = m_seco · (1 + X_prod(t))` y `(q_prod, ṁ_w)` salen de `resolver_estado_camara` evaluado en cada paso del RHS. Reconstrucción a posteriori de las algebraicas para devolver series temporales completas.

**Status posibles:** `X_obj_alcanzado` | `t_max_alcanzado` | `X_inicial_ya_seco` | `error`. Caso degenerado (producto ya seco al inicio) se devuelve sin integrar.

**Tests (19) en `test_camara_termodinamica.py`:**

| Clase | n | Cobertura |
| :--- | :---: | :--- |
| `TestMotorBasico` | 4 | Estructura del resultado, X monotónico, T en bracket, t_secado en orden de magnitud (h) |
| `TestEventDetection` | 3 | X(t_secado) ≈ X_obj, X_inicial ≤ X_obj devuelve t=0, t_max insuficiente devuelve advertencia |
| `TestConservacionFisica` | 3 | Balance de masa global cierra al 1 %, T_prod → T_wb en régimen tasa constante (a_w=1, caudal alto), T_prod → T_ent sin evap ni pérdidas |
| `TestSensibilidad` | 3 | t_secado decrece con caudal, h_conv y T_ent (validación de gradientes) |
| `TestValidacionMotor` | 6 | Errores duros para 6 parámetros |

### 24.11 Sub-tarea S4a (CERRADA) — modelo de datos + despachador

**Modificaciones a `core/camara.py`:**

- `Camara.modo_calculo: Literal["capa_fina", "termodinamico"] = "capa_fina"` con validación en `__post_init__`. Default conservador para preservar comportamiento histórico.
- `CargaProducto.T_prod_inicial_K: Optional[float] = None` con validación de rango razonable [-10 °C, +70 °C] (refrigerado a precalentado). Si `None`, el motor termodinámico usa T_amb como fallback.

**Modificaciones a `calculos/camara_calc.py`:**

- Función pública `calcular_camara(camara, T_op, HR_op, T_amb_K=298.15, P_Pa=101325, t_max_s=72h)` — punto de entrada único; despacha por `modo_calculo`. Compatible con UI existente: en modo capa_fina retorna `ResultadosCamara` (passthrough); en modo termodinámico retorna `ResultadoMotorTermodinamico`.
- Función interna `_calcular_termodinamico(camara, ...)` — el "wire-up" que prepara argumentos desde Camara y delega en `simular_secado`. Lee `propiedades_basicas.calor_especifico_seco` y `isoterma.gab.params` del catálogo. Calcula:
  - cp efectivo a X media (opción B — ver §24.7).
  - Áreas: A_prod = n_bandejas·area_bandeja, A_cuerpo = perímetro de paralelepípedo.
  - h_conv con correlación de placa plana (laminar Pohlhausen / turbulento McAdams según Re=5e5).
  - K_m por Chilton-Colburn directo: `K_m = h_conv / (cp_hum · Le^(2/3))` en kg/(m²·s).
  - aw_func desde GAB del catálogo si está calibrada; fallback rampa lineal `a_w = clip(X/X_inicial, 0, 1)` con advertencia `CAM_TD_GAB_FALTA`.
- Helper `_h_conv_camara_placa_plana(...)` con propiedades del aire constantes a T_película (~50 °C): μ=1.96e-5, k=0.028, Pr=0.71. Variación < 5 % en rango operativo.

**Tests (19):**

| Archivo | Tests | Cobertura |
| :--- | :---: | :--- |
| `test_camara.py` (extendido) | 9 | 4 `modo_calculo` + 5 `T_prod_inicial_K` |
| `test_camara_dispatcher.py` (nuevo) | 10 | Helper h_conv (2), Despachador capa_fina/termodinamico (3), Wire-up (5: T_inicial None vs explícita, GAB sí/no, series consistentes, X decreciente) |

**Hallazgos importantes durante S4a (relevantes para la UI y para S6):**

1. **Fallback aw lineal es no-físico.** Con `aw = X / X_inicial`, cuando X cae a `X_inicial · HR_op` se cumple ω_sup = ω_ent y el aire deja de evaporar antes de alcanzar X_obj. Productos sin GAB calibrada quedarán pegados en `t_max_alcanzado` para X_obj agresivos. **Workaround documentado en advertencia y resaltado en UI (S4b).**

2. **Caudal default 0.030 kg/s en cámara default (0.8×1.5 m²) da v ≈ 0.025 m/s** → Re laminar ≈ 1500 → h_conv ≈ 0.5 W/(m²·K) por correlación de placa plana → secador inviable. La capa fina lo absorbe en sus parámetros empíricos pero el motor termodinámico lo expone. La UI necesita sugerir caudales razonables (S4b lo deja como TODO informal — convendría agregarlo en S5 o como advertencia estática en `core/camara.py`).

### 24.12 Sub-tarea S4b (CERRADA) — wire-up de UI

**Modificaciones a `ui/p4_camara.py`:**

- Imports actualizados: `calcular_camara`, `ResultadoMotorTermodinamico`, `ResultadosCamara`.
- Helper `_T_amb_representativa_K(proyecto)` — media anual de NASA POWER si hay clima cargado, fallback 25 °C; devuelve también el origen como string para UI.
- Helper `_grafica_termodinamica(res, X_obj, prod_id)` — tres paneles compartiendo eje X: (a) X(t) con X_obj y t_secado, (b) T_producto y T_aire en °C, (c) q_aire→producto y q_pared en W.
- Nueva sección F "Modo de cálculo (motor numérico)" — radio button capa_fina/termodinámico con tooltip explicativo. Si modo = termodinámico:
  - Caption con T_amb representativa y origen.
  - Checkbox opcional para definir T inicial del producto explícitamente.
  - **Advertencia destacada** si el producto no tiene GAB calibrada.
- Wire-up al construir `Camara` y `CargaProducto`: propaga `modo_calculo` y `T_prod_inicial_K`.
- Branch en display: `ResultadoMotorTermodinamico` → 4 métricas (t_secado, status, agua evap, X final) + gráfica termodinámica; `ResultadosCamara` → display existente intacto.
- `_texto_config_camara` extendido con T_prod_inicial y MOTOR NUMÉRICO.

**Limitación:** la UI no es testeable por `pytest` automáticamente (Streamlit requiere servidor). Verificación manual pendiente: levantar `streamlit run app.py` y confirmar (a) selectbox aparece, (b) modo termodinámico calcula y grafica, (c) advertencia GAB para manzana, (d) yacón en termodinámico converge.

---

**Próximo arranque:** Sub-tarea S5 — Pestaña 7 (Resultados) debe extender la visualización para curvas dinámicas del motor termodinámico cuando ese modo esté activo. Hoy P7 espera `ResultadosCamara`; necesita branch isomorfo al de P4 que detecte `ResultadoMotorTermodinamico` y muestre las series (T_prod, T_flujo, ω_flujo, q) con la gráfica integrada al resto del balance global. Decisión a tomar al inicio: ¿se requiere actualizar `calculos/balance_global.py` para que el balance global use el motor termodinámico en vez del de capa fina cuando el usuario lo elija, o el motor termodinámico convive como modo "diagnóstico avanzado" sin cambiar el balance global?
