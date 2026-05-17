# Bitácora — Sesión 23 (2026-05-13)

**Tema:** Diseño completo del motor diferencial dinámico para la cámara de secado. Revisión crítica del modelo actual de capa fina, incorporación del Capítulo 2 de RISSPA como fuente de referencia, y toma de todas las decisiones de arquitectura del nuevo motor. **Sesión de diseño puro — sin código generado.** Implementación prevista con VS Code + Claude Code en sesiones siguientes.

**Estado al cierre de la sesión:** Motor diferencial completamente diseñado (ecuaciones, firma, dataclass, tests, transición). Suite de tests existente sin cambios (609 passed, 1 xfailed). No se modificó ningún archivo del repositorio.

---

## 29. Diagnóstico del modelo de capa fina actual — limitaciones identificadas

### 29.1 Naturaleza intensiva del modelo actual

El modelo vigente en `calculos/camara_calc.py` resuelve `MR(t) = MR_obj` algebraicamente mediante `brentq` y entrega siempre el mismo tiempo de secado independientemente de la masa de producto cargada. Esto es físicamente incorrecto porque el moisture ratio es una variable **intensiva** (normalizada por kg de materia seca) y la función `brentq` sólo invierte la curva MR(t) sin acoplar el balance de masa del aire en cámara.

Dos consecuencias directas:
- **La masa no importa:** 5 kg y 10 kg de producto con iguales X_0, X_obj, T_ent, HR_ent entregan el mismo t_secado. El caudal de aire puede no alcanzar para llevarse el agua real evaporada.
- **La temperatura de operación casi no importa:** sólo afecta X_eq vía la isoterma GAB (corrección psicrométrica de Sesión 18), pero el parámetro k permanece igual para cualquier temperatura de entrada. Esto es incorrecto: k depende fuertemente de T (relación de Arrhenius).

### 29.2 La temperatura de operación no modifica k

Cuando el usuario cambia la temperatura de operación en P4, el modelo de capa fina evalúa MR(t) con los mismos k, n, a, b, c del catálogo. Los parámetros publicados en la literatura son constantes del **experimento de laboratorio** (condiciones fijas de T, velocidad, HR), no constantes del producto. En rigor, `k = k(T)` sigue una relación tipo Arrhenius:

```
k(T) = k₀ · exp(−Ea / (R·T))      [T en K, R = 8.314 J/mol·K]
```

donde k₀ es el factor pre-exponencial y Ea la energía de activación aparente del proceso de difusión interna. Mientras el catálogo no tenga k₀ y Ea, el motor usará k constante y emitirá advertencia `PROD_K_CONSTANTE_SIN_ARRHENIUS`.

### 29.3 Impacto en el prediseño

El modelo actual puede subestimar o sobreestimar el tiempo de secado de forma significativa cuando:
- La masa por bandeja es alta respecto al caudal de aire (aire cargado, HR local sube, X_eq sube, secado frena).
- La temperatura de operación difiere apreciablemente de la temperatura de calibración de los parámetros del catálogo (efecto Arrhenius).
- El proceso dura varios días con condiciones variables (HR nocturna puede re-humectar sin que el modelo lo capture).

---

## 30. Fuente RISSPA Capítulo 2 — aporte a la física del secado

Se incorporó como referencia el Capítulo 2 del libro de secado solar de la Red RISSPA. Aportes relevantes al diseño del motor:

### 30.1 Tres fases del proceso de secado

1. **Fase de velocidad creciente:** transitorio de calentamiento inicial, habitualmente despreciable en duración.
2. **Fase de velocidad constante:** la superficie del producto está saturada de agua libre. La velocidad de secado depende principalmente de las condiciones del aire circundante (T, HR, velocidad) y es casi independiente del producto. El producto se mantiene a temperatura de bulbo húmedo. Esta fase puede no existir en productos altamente higroscópicos.
3. **Fase de velocidad decreciente:** comienza al alcanzar la humedad crítica. La resistencia interna del material domina. La difusión de humedad desde el interior hacia la superficie es el proceso limitante. Es la fase que modelan los modelos de capa fina (Lewis, Page, etc.).

Los modelos de capa fina publicados en la literatura son, en su base teórica, truncamientos al primer término de la solución de la Ley de Fick (∂X/∂t = Def · ∂²X/∂x²) para distintas geometrías. Page generaliza empíricamente ese resultado con el exponente n.

### 30.2 Humedad de equilibrio variable — implicación clave

El RISSPA §2.4.2 señala explícitamente que en aplicaciones de secado solar es habitual despreciar X_eq porque "la humedad relativa del aire fluctúa continuamente durante el proceso produciendo variaciones de la humedad de equilibrio. En esas condiciones Mwe resulta ser un parámetro difícil de determinar." 

Esto confirma el problema de usar X_eq estático (o semi-estático como en Sesión 18): si HR_local varía en el tiempo (por carga del aire o por variación diurna), X_eq debe recalcularse en cada instante con la isoterma GAB y la HR_local instantánea.

### 30.3 Calor latente de vaporización

El calor latente de vaporización del agua pura (RISSPA ec. 2.7):

```
Lv = (R / M_w) · (p_s1 − p_s2 · T)      [T en °C]
```

con p_s1 = 6547.1 J/kg, p_s2 = 4.23 J/(kg·°C), M_w = 18.01 kg/kmol, R = 8314 J/(kmol·K). Resulta ≈ 2450 kJ/kg a 20°C. En el producto, cuando el agua está ligada (capilares cerrados), Lv es mayor y depende además de X y del tipo de producto. Para prediseño se usa Lv_pura(T) como primera aproximación; la corrección por agua ligada queda como mejora futura.

### 30.4 Motor físico del secado

El capítulo confirma que la fuerza motriz dominante del proceso de secado es la diferencia de presiones parciales de vapor entre la superficie del producto y el aire circundante. Esto justifica la estructura del modelo CSTR: lo que importa es la HR_local (que determina la presión parcial de vapor del aire) comparada con la actividad de agua del producto (que determina la presión en la superficie).

---

## 31. Decisiones de arquitectura del motor dinámico

Todas las decisiones que siguen fueron acordadas explícitamente con el usuario durante la sesión.

### 31.1 Modelo de mezcla en cámara: CSTR

La cámara se trata como un reactor perfectamente mezclado (CSTR). El producto "ve" siempre el aire de salida mezclado. Coherente con el balance de un solo nodo `T_flujo` del documento `Balance_de_calor_y_masa_en_camara.md`. Alternativa (flujo pistón multi-bandeja) queda como mejora futura.

### 31.2 Horizonte temporal flexible y multi-día

El motor acepta una serie temporal de forzantes de longitud arbitraria. Tres modos de construcción de la serie:

| Modo | Serie temporal | Horizonte |
| :--- | :--- | :--- |
| **Diario** | 24 h del día criterio | 24 h |
| **Multi-día** | Día criterio replicado N veces (N configurable 1–21) | N×24 h |
| **Anual** | Serie real 8760 h desde día criterio | hasta 8760 h |

Para multi-día se replica el día tipo (escenario de "día típico"), no días consecutivos reales. La variabilidad meteorológica queda para mejora futura.

### 31.3 Comportamiento nocturno — Política B (secador abierto, sin re-humectación)

**Política adoptada:** el flujo de aire sigue 24/7 con las condiciones del colector+auxiliar. Si en algún instante dX/dt > 0 (el balance daría absorción de agua), se fuerza dX/dt = 0. Físicamente modela que el operador tapa el secador exactamente cuando hay riesgo de re-humectación.

Esta política permite que noches frías y secas (clima árido del NOA: Salta, Cafayate, San Antonio de los Cobres) contribuyan positivamente al secado. Diferencia un emplazamiento favorable de uno con noches húmedas (Chaco, Misiones) de forma automática.

Si el clipeo supera 3 h en una misma noche → advertencia `CAM_NOCHE_RIESGO_REHUMECTACION`.

### 31.4 Tipología CAJA excluida del motor dinámico (primera iteración)

En tipología CAJA la convección natural acopla T_aire con ṁ_aire en un lazo de retroalimentación que requiere un sub-modelo propio. Se mantiene el modelo estático actual para CAJA. El motor dinámico aplica sólo a **Armario** y **Gran escala**.

### 31.5 Tratamiento de los cinco modelos de capa fina en el motor dinámico

| Modelo | Estado en motor dinámico | Razón |
| :--- | :--- | :--- |
| Lewis | ✅ Primer ciudadano | Formulación diferencial trivial |
| Page | ✅ Primer ciudadano | Más usado en literatura de secado solar; diferencial limpio sin t explícito |
| Henderson-Pabis | ⚠️ Aproximado como Lewis | Factor a ≈ 1 es artefacto de ajuste; dX/dt = −k·(X−X_eq) con k del catálogo. Advertencia `CAM_HP_REDUCIDO_A_LEWIS` |
| Logarítmico | ⚠️ Aproximado como Lewis | Offset c contradice X_eq de GAB; dX/dt = −k·(X−X_eq) con k del catálogo. Advertencia `CAM_LOG_REDUCIDO_A_LEWIS` |
| Midilli | ❌ Deshabilitado en motor dinámico | Término b·t lineal con t explícito; sin asíntota física; rate-bouncing irreal. Fallback al motor estático con advertencia `MOD_CAPA_FINA_NO_DISPONIBLE_DINAMICO` |

### 31.6 Tratamiento de k(T)

El motor es agnóstico: si el catálogo tiene `k0` y `Ea` (Arrhenius), usa:
```
k(T_flujo) = k0 · exp(−Ea / (R·T_flujo))
```
Si sólo tiene `k` a temperatura de referencia, usa ese valor constante y emite `PROD_K_CONSTANTE_SIN_ARRHENIUS`. El catálogo de productos debe actualizarse con k0/Ea cuando se pueble (trabajo pendiente).

### 31.7 Terminación y reportes

| Condición | Resultado |
| :--- | :--- |
| X(t) = X_obj alcanzado | `convergencia_a_X_obj=True`, reporta `t_secado_s` |
| Fin de horizonte sin alcanzar X_obj | `convergencia_a_X_obj=False`, advertencia `CAM_X_OBJ_NO_ALCANZADO_EN_HORIZONTE`, reporta `X_final` |
| T_prod > T_max_admisible_K del catálogo | Terminación con advertencia crítica de daño térmico |
| ṁ_aire < ṁ_min sostenido | Advertencia `FLUJO_INSUFICIENTE_SISTEMATICO` |

### 31.8 Parámetros de configuración numérica

| Parámetro | Valor | Justificación |
| :--- | :--- | :--- |
| `ṁ_min` | 1e-4 kg/s | Umbral de "flujo nulo"; físicamente despreciable |
| `HR_saturacion_alarma` | 0.95 | Igual al umbral existente en motor estático |
| `tol_X_obj` | 1e-4 kg/kg | Tolerancia de evento de terminación |
| `horizonte_max_dias` | 21 | Cap para modos multi-día y anual |
| Método solver | LSODA | Se adapta entre stiff/non-stiff; maneja bien transiciones amanecer/atardecer |
| rtol / atol | 1e-6 / 1e-8 | Balance entre precisión y costo computacional |

---

## 32. Sistema de ecuaciones del motor dinámico

### 32.1 Variables del sistema

**Estados diferenciales** (integrados por `solve_ivp`):

- `X(t)` — humedad base seca [kg agua/kg seco], condición inicial X(0) = X_0
- `T_prod(t)` — temperatura del producto [K], condición inicial T_prod(0) = T_amb(0)

**Variables algebraicas** (resueltas por `fsolve` interno en cada llamada al RHS):

- `T_flujo` — temperatura del aire mezclado en cámara [K]
- `T_cam_int` — temperatura cara interna de pared [K]
- `T_cam_ext` — temperatura cara externa de pared [K]
- `ω_salida` — humedad absoluta del aire de salida [kg agua/kg aire seco]
- `(dX/dt)` — velocidad de secado instantánea [kg/kg/s], acoplada al modelo cinético

**Forzantes** (interpoladas linealmente de series horarias):

- `T_ent(t)` — temperatura del aire de entrada a cámara [K]
- `ω_ent(t)` — humedad absoluta del aire de entrada [kg/kg ms]
- `ṁ_aire_seco(t)` — caudal másico de aire seco [kg/s]
- `T_amb(t)` — temperatura ambiente exterior [K]
- `v_viento(t)` — velocidad del viento [m/s]

### 32.2 Sistema algebraico interno (5×5)

**(1) Balance de masa de agua en el aire:**
```
ω_salida − ω_ent = m_evap / ṁ_aire_seco
m_evap = m_seco · max(0, −dX/dt)
m_seco = m_total / (1 + X_0)
```

**(2) Balance de energía del flujo de aire:**
```
ṁ_aire_seco · cp_aire · (T_flujo − T_ent)
    + h_conv · A_cuerpo · (T_flujo − T_cam_int)
    + h_conv · A_prod   · (T_flujo − T_prod)
    + m_evap · Lv(T_prod) = 0
```

**(3) Continuidad de calor en pared (interna ↔ conducción):**
```
h_conv · A_cuerpo · (T_flujo − T_cam_int)
    = (k_aisl / esp_cam) · A_cuerpo · (T_cam_int − T_cam_ext)
```

**(4) Continuidad de calor en pared (conducción ↔ exterior):**
```
(k_aisl / esp_cam) · A_cuerpo · (T_cam_int − T_cam_ext)
    = h_w(v_viento) · A_cuerpo · (T_cam_ext − T_amb)
```
donde `h_w` se calcula con la correlación de McAdams ya implementada en `colector_calc.py`.

**(5) Modelo cinético de capa fina** — en forma diferencial con X_eq local:

Para Lewis:
```
dX/dt = −k(T_flujo) · (X − X_eq)
```

Para Page:
```
dMR/dt = −n · k(T_flujo)^(1/n) · MR · (−ln MR)^((n−1)/n)
dX/dt  = (X_0 − X_eq) · dMR/dt
MR_rel = (X − X_eq) / (X_0 − X_eq),  clipeado a (ε, 1]  con ε=1e-6
```

En ambos casos: `X_eq = GAB(HR_local(T_flujo, ω_salida), T_flujo)` actualizado en cada paso.

### 32.3 ODEs devueltas al solver

```
dX/dt     = (resuelto en ec. 5)

dT_prod/dt = [h_conv · A_prod · (T_flujo − T_prod) − m_evap · Lv(T_prod)]
             / (m_prod_actual · cp_prod)

m_prod_actual = m_seco · (1 + X(t))   ← para prediseño puede usarse m_total constante
```

### 32.4 Flujo de cómputo dentro del RHS

En cada llamada de `solve_ivp` al RHS con estado (X, T_prod) al instante t:

1. Interpolar T_ent, ω_ent, ṁ_aire, T_amb, v_viento al instante t.
2. Si `ṁ_aire < ṁ_min` → retornar `(0, dT_prod_dt_pasivo)` y acumular advertencia.
3. Si `ṁ_aire ≥ ṁ_min` → resolver el sistema 5×5 con `fsolve`. Semilla inicial: solución del paso anterior (warm-start). En t=0 usar `(T_ent, T_ent, T_amb, ω_ent, 0)`.
4. Verificar regla anti-rehumectación: si `dX/dt > 0` → re-resolver con `dX/dt = 0` forzado (sistema cae a 4×4 con `ω_salida = ω_ent`). Acumular contador de horas con clipeo.
5. Calcular `dT_prod/dt` y devolver `[dX/dt, dT_prod/dt]`.

### 32.5 Eventos del solver

```python
event_X_obj.terminal  = True    # X − X_obj = 0, direction = −1
event_HR_sat.terminal = False   # HR_local − 0.95 = 0
event_T_prod_crit.terminal = True   # T_prod − T_max_admisible = 0 (si existe en catálogo)
```

### 32.6 Calor latente y h_conv

- **Lv:** en primera iteración constante a 2.45 MJ/kg. Gancho preparado para `Lv_pura(T_prod)` con ecuación RISSPA 2.7 en iteración siguiente.
- **h_conv interno:** reutilizar `correlaciones_nusselt.py` con velocidad del aire en cámara `v_cam = Q_vol / A_pasaje`. Un único h_conv para interfaz aire-pared y aire-producto (mejora futura: diferenciarlos).
- **k en SI:** `k_SI = k_catalogo_min⁻¹ / 60`. Conversión interna, invisible al usuario.

---

## 33. Firma del motor y dataclass de resultados

### 33.1 Firma del motor dinámico

```python
def calcular_secado_dinamico(
    *,
    masa_total_kg: float,
    X_0: float,
    X_obj: float,
    params_producto: ParamsProducto,     # k, n, modelo, GAB, cp, k0, Ea (opcional), T_max_K (opcional)
    geometria: GeometriaCamara,          # A_cuerpo, A_prod, esp_cam, k_aisl
    forzantes: ForzantesAire,            # arrays: t_s, T_ent_K, ω_ent, ṁ_kg_s, T_amb_K, v_viento_ms
    horizonte_s: float,
    tol_X_obj: float = 1e-4,
) -> ResultadosCamaraDinamico:
```

El motor es agnóstico del modo P1. La responsabilidad de construir `ForzantesAire` queda en `balance_global.py` o en una función auxiliar `armar_forzantes_aire(modo, n_dias, ...)`.

### 33.2 Construcción de forzantes upstream

```python
def armar_forzantes_aire(
    *,
    modo: Literal["diario", "multi_dia", "anual"],
    n_dias: int,                              # sólo para multi_dia
    resultados_colector_dia: Any,             # ResultadosColectorTipoN
    resultados_auxiliar_dia: Optional[ResultadosAuxiliar],
    serie_motor: ResultadosMotor,             # caudal de diseño o serie eólica
    clima: ClimaProcesado,
) -> ForzantesAire:
```

Lógica interna:
- **T_ent:** T_salida_auxiliar si auxiliar activo, T_salida_col si no. Durante noche: T_salida_col = T_amb.
- **ω_ent:** ω_amb (el colector/auxiliar no aporta vapor).
- **ṁ_aire:** constante de diseño si motor eléctrico; ṁ(v_viento) si extractor eólico.
- **Multi-día:** replicar 24 h del día tipo N veces. Serie anual: usar datos reales desde día criterio.

### 33.3 Dataclass ResultadosCamaraDinamico

```python
@dataclass
class ResultadosCamaraDinamico:
    # Estado de terminación
    convergencia_a_X_obj: bool
    motivo_terminacion: str          # "X_OBJ_ALCANZADO" | "FIN_HORIZONTE"
                                     # | "DAÑO_TERMICO" | "FLUJO_SOSTENIDO_NULO"

    # Escalares
    t_secado_s: Optional[float]      # válido sólo si convergencia_a_X_obj=True
    X_final: float                   # siempre válido
    masa_agua_evaporada_kg: float

    # Métricas operativas
    dias_efectivos_secado: float
    horas_rehumectacion_evitada: float
    horas_flujo_nulo: float

    # Trayectorias para P7
    t_s: np.ndarray
    X: np.ndarray
    T_prod_K: np.ndarray
    T_flujo_K: np.ndarray
    HR_local: np.ndarray
    omega_salida: np.ndarray
    m_evap_acumulada_kg: np.ndarray

    # Diagnóstico numérico
    advertencias: list[Advertencia]
    convergencia_fsolve_ok: bool
    n_pasos_fsolve_fallidos: int
```

---

## 34. Plan de tests y validación

### 34.1 Tests unitarios del motor (`test_camara_calc_dinamico.py`)

| # | Nombre | Qué verifica |
| :--- | :--- | :--- |
| 1 | `test_limite_aire_infinito` | ṁ → 1e6 kg/s: t_secado coincide con motor estático ±5% |
| 2 | `test_flujo_nulo_sostenido` | ṁ = 0 en 24 h: X_final = X_0, advertencia disparada |
| 3 | `test_sin_fuerza_motriz` | T_ent = T_amb, ω_ent = ω_sat: dX/dt = 0 en todo el horizonte |
| 4 | `test_conservacion_masa` | ∫ m_evap dt = m_seco·(X_0 − X_final), tolerancia 1e-4 kg |
| 5 | `test_sensibilidad_masa` | masa×2 → t_secado mayor pero < 2×t_secado_original |
| 6 | `test_sensibilidad_temperatura` | T_ent + 10 K → t_secado menor (cuando k(T) esté implementado) |
| 7 | `test_continuidad_trayectoria` | X(t) y T_prod(t) son C⁰ en sunrise/sunset (sin saltos) |
| 8 | `test_multi_dia_continuidad` | X al final del día 1 = X inicial del día 2 |
| 9 | `test_advertencia_no_alcanza` | Si X_obj no se alcanza en horizonte → `convergencia_a_X_obj=False` + advertencia |
| 10 | `test_page_mr_limite_inferior` | MR_rel → 0: no hay división por cero ni NaN en dX/dt |

### 34.2 Tests de regresión contra motor estático

Para condiciones de aire muy en exceso (ṁ grande) y baja masa, ambos motores deben dar t_secado compatible con tolerancia 5%. Esto valida que el dinámico no introduce sesgos sistemáticos respecto al estático ya validado.

### 34.3 Validación experimental

El usuario dispone de mediciones de secadores reales. Plan:

1. Crear carpeta `validacion/casos_experimentales/` con casos documentados.
2. Cada caso: condiciones operativas registradas (T, HR, ṁ a lo largo del tiempo) + curva X(t) medida.
3. Motor recibe las condiciones como forzantes reales (no idealizadas).
4. Comparar X(t) predicho vs medido. Métricas: RMSE sobre MR, coeficiente R².
5. Umbral de aceptación para prediseño: R² > 0.9 en al menos 3 productos distintos.

Esta validación es la que habilita oficialmente al motor dinámico como "validado para prediseño".

---

## 35. Plan de transición — motor estático → dinámico

### 35.1 Coexistencia

- **`camara_calc.py`** permanece sin cambios. Funciones públicas renombradas con sufijo `_estatico` (p. ej. `calcular_tiempo_secado_estatico`).
- **`camara_calc_dinamico.py`** nuevo módulo con el motor dinámico.
- Los **38 tests existentes** de `test_camara_calc.py` siguen pasando sin modificación.
- Los tests nuevos van a `test_camara_calc_dinamico.py`.

### 35.2 Selector en P4

P4 ofrece un selector "Modo de cálculo":
- **Estático (rápido):** modelo algebraico actual. Adecuado para exploración inicial o cuando el producto sólo tiene parámetros de Midilli.
- **Dinámico (riguroso):** motor diferencial acoplado. Default para Armario y Gran escala una vez validado.

### 35.3 Fallback Midilli

Si el producto sólo tiene parámetros de Midilli y el usuario eligió modo dinámico: advertencia `MOD_CAPA_FINA_NO_DISPONIBLE_DINAMICO` + fallback automático al modo estático. P4 y P7 señalizan visualmente que se usó el fallback.

### 35.4 Migración definitiva

Cuando el motor dinámico esté validado experimentalmente (R² > 0.9 en al menos 3 productos), deprecar el modo estático como default. Mantenerlo como opción explícita para usuarios que la necesiten (CAJA, Midilli, velocidad).

---

## 36. Pendiente para siguiente sesión

- ~~**Implementar `camara_calc_dinamico.py`**~~ → ✅ implementado (§37)
- ~~**Actualizar `core/camara.py`** con `ResultadosCamaraDinamico` y `ForzantesAire`~~ → ✅ (§37)
- ~~**Escribir tests** de `test_camara_calc_dinamico.py`~~ → ✅ 19 tests pasan (§37)
- ~~**h_int natural canal estanco Tipos 3/4**~~ → ✅ (§37)
- ~~**Implementar `armar_forzantes_aire()`**~~ → ✅ (§37.2, sesión siguiente)
- ~~**Agregar selector de modo**~~ → ✅ tres opciones: Estático / Dinámico / Termodinámico
- ~~**Actualizar `ui/p7_resultados.py`**~~ → ✅ tres paneles X(t)/T(t)/HR(t), métricas operativas (§37.2)
- **Poblar catálogo con k₀/Ea** para al menos 2 productos (Doymaz & Bilici 2014, otros).
- Items pendientes: repo GitHub, verificar k de manzana en `frutas.yaml`.

---

## 37. Trabajo implementado en sesión de código (2026-05-13 — Claude Code)

### 37.1 Mejoras de interfaz y bugs corregidos

**Mejora §10 (h_int natural canal estanco, Tipos 3/4):**
- Tipo 3 (canal superior estanco): `h_int_cs` calculado per-nodo con Hollands et al. (1976) en función de Ra(ΔT, alto_cs_m). Parámetro `theta_deg=45.0` agregado a `calcular_colector_tipo3()`.
- Tipo 4 (canal inferior estanco): Nu=1 (configuración estable), `h_int_ci = K_AIRE / alto_ci_m`. Anterior hack Re=500 eliminado.
- Nuevo helper `_Ra_canal_estanco()` en `colector_tipos234_calc.py`. Función `nusselt_hollands_inclinada` importada directamente.

**Mejora 14 (P2 modo diario):** sección "Recurso climático del día de diseño" visible solo cuando `modo_analisis == DIARIO`, con tabs de T, irradiancia y viento/HR horarios.

**Mejora 15 (CSV del día):** botón de descarga CSV filtrado al día de diseño.

**Mejora 16 (bug k(T) en motor estático):** nueva función `_interpolar_params_cf(modelo_entry, T_K)` que interpola linealmente k, n, etc. desde `sets_por_temperatura`. Anteriormente se usaba siempre el escalar top-level (25°C fijo).  Advertencia `CAM_ESPESOR_FUERA_CALIBRACION` cuando espesor > 3× espesor de calibración.

### 37.2 Motor dinámico de cámara — implementación del núcleo

**Paso 1 — Renombramiento:** `calcular_tiempo_secado` → `calcular_tiempo_secado_estatico` en `camara_calc.py` y en todos los tests (`test_camara_calc.py`, `test_psicrometria.py`).

**Paso 2 — Nuevas dataclasses en `core/camara.py`:**
- `ForzantesAire`: serie temporal de forzantes (t_s, T_ent_K, omega_ent, m_dot_aire_seco_kg_s, T_amb_K, v_viento_ms). Validación de longitudes y t_s[0]=0 en `__post_init__`.
- `ResultadosCamaraDinamico`: resultados del motor (trayectorias, métricas operativas, diagnóstico numérico).

**Paso 3 — `calculos/camara_calc_dinamico.py` (nuevo):**
- `k_arrhenius()`: k(T) via Arrhenius si catálogo tiene k0/Ea.
- `_h_conv_camara()`: h convectivo interno con Dittus-Boelter/Gnielinski/Shah-London según Re.
- `_sistema_algebraico()`: sistema 5×5 con residuos de Ec.1–5 del §32 de la bitácora.
- `_resolver_sistema_cerrado()`: sub-sistema lineal para modo anti-re-humectación.
- `calcular_secado_dinamico()`: motor principal — solve_ivp LSODA, Política B nocturna, 3 eventos (X_obj, HR_saturación, T_prod_crítica), warm-start para fsolve.

**Paso 4 — `tests/test_calculos/test_camara_calc_dinamico.py` (nuevo):** 19 tests en 10 clases cubriendo los casos especificados en §34. Suite total: 628 pasan, 1 xfailed.

### 37.3 Estado de la transición

| Paso | Estado |
| :--- | :--- |
| Renombrar funciones estáticas | ✅ |
| `ForzantesAire` y `ResultadosCamaraDinamico` | ✅ |
| `calcular_secado_dinamico()` | ✅ |
| `armar_forzantes_aire()` | ✅ |
| Selector en P4 | ✅ |
| Gráficas dinámicas en P7 | ✅ |

### 37.3 Detalles de implementación — `armar_forzantes_aire`, P4 y P7

**`armar_forzantes_aire()` en `calculos/balance_global.py`:** construye `ForzantesAire` desde arrays de T_salida_colector y omega_ambiente. Modos: `diario` (as-is), `multi_dia` (tile N), `anual` (pass-through). Fallbacks: v_viento → 2 m/s, T_amb → T_ent − 10 K. 14 tests nuevos incluyendo pipeline armar → calcular.

**P4 — tres modos de cálculo:**
- **Estático:** brentq algebraico (comportamiento previo).
- **Dinámico:** nuevo — llama `calcular_secado_dinamico` con condiciones constantes 24 h × n_días. Selector de horizonte diario / multi-día. Deshabilita para CAJA y productos Midilli-only. Guarda resultado en `session_state["p4_resultado_dinamico"]` para P7. Gráfica de 3 paneles X(t)/T(t)/HR(t) en P4.
- **Termodinámico:** motor TD acoplado (comportamiento previo).

**P7 — soporte dinámico:**
- `_fig_trayectorias_dinamico(res, X_obj)`: figura de 3 paneles (X, T, HR) con marcadores de t_secado, X_obj, alarma de saturación 95%.
- `_resumen_camara` actualizado para `ResultadosCamaraDinamico`.
- Sección "Cámara de Secado — Motor Dinámico" con 5 métricas: tiempo, X_final, agua evaporada, días efectivos, horas de re-humectación evitada.
- Rotulado de no-convergencia cuando `convergencia_a_X_obj=False`.
- Advertencia cuando horas_rehumectacion_evitada ≥ 3 h.
- `_texto_resultados_completo` y tabla de resultados actualizados para los tres tipos de resultado de cámara.
