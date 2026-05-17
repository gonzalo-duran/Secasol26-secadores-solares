# Especificación de implementación — Motor dinámico de cámara de secado
## Proyecto: Software de prediseño de secadores solares (INENCO–UNSa / CONICET)

**Para:** Claude Code  
**Fecha de diseño:** 2026-05-13 (Sesión 23)  
**Complementa:** `bitacora_sesion23.md` y el archivo `Balance_de_calor_y_masa_en_camara.md` del proyecto.  
**Estado del repositorio al inicio:** 609 tests pasan, 1 xfailed. Todas las pestañas P1–P7 implementadas.

---

## 1. Contexto del proyecto y convenciones obligatorias

### 1.1 Qué es este software

Software de prediseño de secadores solares de alimentos, escrito en Python con Streamlit. El usuario es un ingeniero o estudiante con formación en transferencia de calor. El nivel de modelado es "complejidad media": suficiente para tomar decisiones de prediseño (dimensiones, áreas, caudales) pero sin reemplazar una simulación nodal completa tipo Simusol.

### 1.2 Convenciones de código — **NO negociables**

- **SI estricto** en todo `core/` y `calculos/`. Las conversiones de unidades ocurren exclusivamente en `ui/componentes/unidades.py`.
- **Temperaturas en Kelvin** internamente. Se muestran en °C al usuario en la UI.
- **Humedad absoluta (ω)** en kg_agua/kg_aire_seco internamente.
- **Humedad base seca (X)** en kg_agua/kg_seco internamente. Los usuarios ingresan también en base seca (es la convención del área).
- **Tiempo en segundos** internamente en el motor. Los parámetros cinéticos del catálogo vienen en min⁻¹; convertir en el motor con `k_SI = k_cat / 60.0`.
- Archivos/módulos: `snake_case`. Clases: `PascalCase`. Variables físicas con sufijo de unidad: `T_flujo_K`, `m_evap_kg_s`, `A_cuerpo_m2`.
- Sin `import streamlit` en `core/` ni `calculos/`.
- `ValueError` con código de error en `__post_init__`. `RuntimeError` en cálculos.
- Tests con imports absolutos (`from calculos.modulo import ...`). El `conftest.py` gestiona el path.
- Black `line-length=100`, Ruff reglas E, F, I, W.

### 1.3 Estructura de carpetas relevante

```
secador_solar/
├── core/
│   ├── camara.py           ← MODIFICAR: agregar nuevas dataclasses
│   ├── advertencias.py     ← leer para reusar códigos de advertencia existentes
│   └── catalogo.py         ← leer para entender cómo se accede al catálogo de productos
├── calculos/
│   ├── camara_calc.py      ← NO BORRAR. Renombrar funciones públicas con sufijo _estatico
│   ├── camara_calc_dinamico.py   ← CREAR: motor nuevo
│   ├── psicrometria.py     ← reusar funciones de HR, ω_sat, presión de vapor
│   ├── correlaciones_nusselt.py  ← reusar calcular_h_int()
│   └── balance_global.py   ← MODIFICAR: agregar armar_forzantes_aire()
├── ui/
│   ├── p4_camara.py        ← MODIFICAR: agregar selector modo estático/dinámico
│   └── p7_resultados.py    ← MODIFICAR: mostrar trayectorias multi-día
└── tests/
    └── test_calculos/
        └── test_camara_calc_dinamico.py   ← CREAR
```

---

## 2. Por qué se crea el motor dinámico — el problema con el modelo actual

El motor actual en `camara_calc.py` resuelve `MR(t) = MR_obj` algebraicamente con `brentq`. Esto tiene dos fallas físicas graves:

**Falla 1 — Independencia de la masa:** el moisture ratio es una variable intensiva (normalizada). 5 kg y 10 kg de producto con iguales condiciones entregan el mismo tiempo de secado. Esto es incorrecto porque el caudal de aire tiene una capacidad finita de absorber vapor: a mayor masa, mayor tasa de evaporación, mayor carga de humedad del aire, mayor HR local, mayor X_eq local, y menor fuerza motriz de secado. El tiempo crece de forma no lineal con la masa.

**Falla 2 — Independencia de la temperatura de operación:** el parámetro `k` del modelo cinético está fijo en el catálogo. Cambiar la temperatura de operación en P4 sólo afecta X_eq vía la isoterma GAB. Pero físicamente `k = k(T)` sigue una relación de Arrhenius; a mayor temperatura, k crece exponencialmente y el tiempo cae de forma importante.

**Falla 3 — Condiciones estáticas:** las condiciones del aire de entrada (T y HR) se toman como escalares constantes. En un día solar real, T_colector(t) y HR(t) son series horarias variables. El modelo actual no captura ni el transitorio de calentamiento matutino ni el enfriamiento vespertino.

El motor dinámico resuelve las tres fallas acoplando el modelo cinético de capa fina con el balance de masa y energía de la cámara en forma diferencial, alimentado por series horarias de condiciones del aire.

---

## 3. Decisiones de diseño acordadas — resumen ejecutivo

| Decisión | Valor acordado |
| :--- | :--- |
| Modelo de mezcla en cámara | CSTR (perfectamente mezclado) |
| Horizonte temporal | Flexible: diario / multi-día / anual |
| Comportamiento nocturno | Política B: flujo continuo, clip dX/dt>0 a 0 (no re-humectación) |
| Tipologías soportadas | **Armario** y **Gran escala** únicamente. CAJA queda para iteración futura |
| Modelos Lewis y Page | Primer ciudadano en motor dinámico |
| Henderson-Pabis y Logarítmico | Reducidos a Lewis (usar k del catálogo, ignorar a y c). Advertencia |
| Midilli | Deshabilitado en motor dinámico. Fallback al motor estático con advertencia |
| k(T) | Usar Arrhenius si catálogo tiene k0/Ea; k constante si no, con advertencia |
| Calor latente Lv | Constante 2.45e6 J/kg en primera iteración. Gancho para Lv(T) futuro |
| Método de integración | `scipy.integrate.solve_ivp` con `method='LSODA'` |
| Tolerancias solver | `rtol=1e-6`, `atol=1e-8` |
| Flujo mínimo | `ṁ_min = 1e-4 kg/s` |
| Alarma HR saturación | `HR_alarm = 0.95` |
| Tolerancia evento X_obj | `tol_X_obj = 1e-4 kg/kg` |
| Horizonte máximo | 21 días |

---

## 4. Sistema de ecuaciones del motor

### 4.1 Variables de estado (integradas por solve_ivp)

```
y = [X, T_prod_K]

X(t)         — humedad base seca del producto [kg agua/kg seco]
             — condición inicial: X(0) = X_0
T_prod_K(t)  — temperatura del producto [K]
             — condición inicial: T_prod_K(0) = T_amb_K(t=0)
```

### 4.2 Variables algebraicas (resueltas por fsolve en cada llamada al RHS)

```
incógnitas = [T_flujo_K, T_cam_int_K, T_cam_ext_K, omega_salida, dX_dt]
```

### 4.3 Forzantes externas (interpoladas de series horarias)

```
T_ent_K(t)       — temperatura del aire de entrada a cámara [K]
omega_ent(t)     — humedad absoluta del aire de entrada [kg/kg ms]
m_dot_aire_s(t)  — caudal másico de aire seco [kg/s]
T_amb_K(t)       — temperatura ambiente exterior [K]
v_viento_ms(t)   — velocidad del viento [m/s]
```

### 4.4 Las cinco ecuaciones del sistema algebraico interno

**(Ec. 1) Balance de masa de agua en el aire — CSTR:**
```
omega_salida - omega_ent = m_evap_kg_s / m_dot_aire_s

donde:
    m_evap_kg_s = m_seco_kg * max(0.0, -dX_dt)    ← max(0,·) aplica regla anti-rehumectación
    m_seco_kg   = masa_total_kg / (1.0 + X_0)
```

**(Ec. 2) Balance de energía del flujo de aire:**
```
m_dot_aire_s * CP_AIRE * (T_flujo_K - T_ent_K)
    + h_conv_W_m2K * A_cuerpo_m2 * (T_flujo_K - T_cam_int_K)
    + h_conv_W_m2K * A_prod_m2   * (T_flujo_K - T_prod_K)
    + m_evap_kg_s  * LV_J_KG
    = 0
```

**(Ec. 3) Continuidad de calor — pared interna ↔ conducción:**
```
h_conv_W_m2K * A_cuerpo_m2 * (T_flujo_K - T_cam_int_K)
    = (k_aisl_W_mK / esp_cam_m) * A_cuerpo_m2 * (T_cam_int_K - T_cam_ext_K)
```

**(Ec. 4) Continuidad de calor — conducción ↔ exterior:**
```
(k_aisl_W_mK / esp_cam_m) * A_cuerpo_m2 * (T_cam_int_K - T_cam_ext_K)
    = h_w_W_m2K * A_cuerpo_m2 * (T_cam_ext_K - T_amb_K)

donde h_w_W_m2K = h_viento(v_viento_ms)    ← usar correlación McAdams de colector_calc.py
```

**(Ec. 5) Modelo cinético de capa fina en forma diferencial:**

Para modelo **Lewis** (y los reducidos Henderson-Pabis / Logarítmico):
```
dX_dt = -k_SI * (X - X_eq)

donde:
    k_SI = k_arrhenius(T_flujo_K) si hay k0/Ea en catálogo
           k_catalogo / 60.0      si no (k constante en min⁻¹ → s⁻¹)
    X_eq = gab(HR_local, T_flujo_K, params_gab)
    HR_local = calcular_HR(T_flujo_K, omega_salida)   ← usar psicrometria.py
```

Para modelo **Page**:
```
MR_rel = (X - X_eq) / (X_0 - X_eq_inicial)   ← X_eq_inicial fijo en t=0
MR_rel = max(epsilon, min(1.0, MR_rel))        ← epsilon = 1e-6, evitar log(0)

dMR_dt = -n * k_SI**(1.0/n) * MR_rel * (-log(MR_rel))**((n-1.0)/n)
dX_dt  = (X_0 - X_eq_inicial) * dMR_dt
```

**Nota importante sobre X_eq_inicial:** para el modelo Page se usa X_eq calculado en t=0 como denominador del MR_rel, para mantener consistencia con la definición original del modelo. El X_eq local sólo entra en Ec.1 (balance de masa) y en la regla anti-rehumectación.

### 4.5 Las dos ODEs devueltas al solver

```
dX_dt        = (resuelto en Ec. 5)

dT_prod_dt   = (h_conv_W_m2K * A_prod_m2 * (T_flujo_K - T_prod_K)
                - m_evap_kg_s * LV_J_KG)
               / (m_prod_actual_kg * cp_prod_J_kgK)

donde m_prod_actual_kg = m_seco_kg * (1.0 + X)   ← masa que varía con el secado
      cp_prod_J_kgK    = del catálogo de productos
```

### 4.6 Constantes físicas a usar

```python
CP_AIRE: float = 1007.0       # J/kg·K — calor específico del aire
LV_J_KG: float = 2.45e6      # J/kg   — calor latente de vaporización (primera iteración)
R_GAS: float   = 8.314        # J/mol·K — constante de gas (para Arrhenius)
```

### 4.7 k(T) con Arrhenius

```python
def k_arrhenius(T_K: float, k0: float, Ea_J_mol: float) -> float:
    """Constante de secado a temperatura T [K]. Resultado en s⁻¹."""
    return k0 * math.exp(-Ea_J_mol / (R_GAS * T_K))
```

Si el catálogo no tiene `k0` / `Ea_J_mol` para el producto → usar k constante del catálogo y emitir advertencia `PROD_K_CONSTANTE_SIN_ARRHENIUS`.

---

## 5. Flujo de cómputo del RHS — lógica detallada

El RHS es la función que `solve_ivp` llama en cada paso. Recibe `(t, y)` y devuelve `dydt`.

```
def _rhs(t, y, <todos los parámetros como argumentos extra o closure>):

    X, T_prod_K = y[0], y[1]

    # --- 1. Interpolar forzantes al instante t ---
    T_ent_K      = interp_T_ent(t)
    omega_ent    = interp_omega_ent(t)
    m_dot_aire_s = interp_m_dot(t)
    T_amb_K      = interp_T_amb(t)
    v_viento_ms  = interp_v_viento(t)

    # --- 2. Verificar flujo mínimo ---
    if m_dot_aire_s < M_DOT_MIN_KG_S:
        acumular_advertencia("FLUJO_NULO_TRANSITORIO")
        # Solo decay térmico del producto hacia T_amb por paredes
        dT_prod_dt = _decay_termico_pasivo(T_prod_K, T_amb_K, ...)
        return [0.0, dT_prod_dt]

    # --- 3. Calcular h_conv y h_w ---
    v_cam_ms     = m_dot_aire_s / (rho_aire * A_pasaje_m2)
    h_conv       = calcular_h_int(...)          # correlaciones_nusselt.py
    h_w          = h_viento_mcadams(v_viento_ms)  # de colector_calc.py

    # --- 4. Verificar pre-condición de rehumectación ---
    #    Estimación rápida con omega_ent (sin acoplar) para detectar modo cerrado
    HR_est = calcular_HR(T_ent_K, omega_ent)
    X_eq_est = gab(HR_est, T_ent_K, params_gab)
    modo_cerrado = (X_eq_est >= X)   # si True, imponer dX_dt = 0

    # --- 5. Resolver sistema algebraico 5x5 (o 4x4 si modo_cerrado) ---
    if modo_cerrado:
        sol = _resolver_sistema_cerrado(
            T_prod_K, T_ent_K, omega_ent, m_dot_aire_s, T_amb_K,
            h_conv, h_w, A_cuerpo_m2, k_aisl_W_mK, esp_cam_m
        )
        dX_dt = 0.0
        acumular_horas_clipeo(dt_estimado)
    else:
        x0_guess = _semilla_caliente()    # solución del paso anterior
        sol = fsolve(
            _sistema_algebraico,
            x0=x0_guess,
            args=(...),
            full_output=True
        )
        _verificar_convergencia_fsolve(sol)
        T_flujo_K, T_cam_int_K, T_cam_ext_K, omega_salida, dX_dt = sol[0]

        # Recheck: si después de resolver dX_dt > 0, forzar modo cerrado
        if dX_dt > 0.0:
            dX_dt = 0.0
            acumular_horas_clipeo(dt_estimado)
            # Recalcular T_flujo con omega_salida = omega_ent (sin evaporación)
            sol = _resolver_sistema_cerrado(...)

    # --- 6. Guardar semilla para el próximo paso ---
    _actualizar_semilla_caliente([T_flujo_K, T_cam_int_K, T_cam_ext_K, omega_salida, dX_dt])

    # --- 7. Calcular m_evap y dT_prod_dt ---
    m_evap_kg_s = m_seco_kg * abs(dX_dt)
    dT_prod_dt  = (h_conv * A_prod_m2 * (T_flujo_K - T_prod_K)
                   - m_evap_kg_s * LV_J_KG) / (m_prod_actual(X) * cp_prod_J_kgK)

    return [dX_dt, dT_prod_dt]
```

**Implementación del sistema algebraico como función para fsolve:**

```python
def _sistema_algebraico(incognitas, X, T_prod_K, T_ent_K, omega_ent,
                         m_dot_aire_s, T_amb_K, h_conv, h_w,
                         A_cuerpo_m2, A_prod_m2, k_aisl_W_mK, esp_cam_m,
                         m_seco_kg, params_capa_fina, params_gab,
                         X_0, X_eq_inicial, modelo):

    T_flujo_K, T_cam_int_K, T_cam_ext_K, omega_salida, dX_dt = incognitas

    # Variables derivadas
    m_evap   = m_seco_kg * max(0.0, -dX_dt)
    HR_local = calcular_HR(T_flujo_K, omega_salida)         # psicrometria.py
    X_eq     = gab(HR_local, T_flujo_K, params_gab)

    # k efectiva
    k_eff = k_arrhenius(...) if tiene_arrhenius else k_cat_SI

    # dX_dt del modelo cinético (Ec. 5)
    if modelo == "lewis":
        dX_dt_model = -k_eff * (X - X_eq)
    elif modelo == "page":
        MR_rel = max(EPSILON, min(1.0, (X - X_eq) / (X_0 - X_eq_inicial)))
        dMR_dt = -n * k_eff**(1.0/n) * MR_rel * (-log(MR_rel))**((n-1.0)/n)
        dX_dt_model = (X_0 - X_eq_inicial) * dMR_dt

    # Residuos del sistema
    r1 = omega_salida - omega_ent - m_evap / m_dot_aire_s                               # Ec.1
    r2 = (m_dot_aire_s * CP_AIRE * (T_flujo_K - T_ent_K)
          + h_conv * A_cuerpo_m2 * (T_flujo_K - T_cam_int_K)
          + h_conv * A_prod_m2   * (T_flujo_K - T_prod_K)
          + m_evap * LV_J_KG)                                                           # Ec.2
    r3 = (h_conv * A_cuerpo_m2 * (T_flujo_K - T_cam_int_K)
          - (k_aisl_W_mK / esp_cam_m) * A_cuerpo_m2 * (T_cam_int_K - T_cam_ext_K))   # Ec.3
    r4 = ((k_aisl_W_mK / esp_cam_m) * A_cuerpo_m2 * (T_cam_int_K - T_cam_ext_K)
          - h_w * A_cuerpo_m2 * (T_cam_ext_K - T_amb_K))                               # Ec.4
    r5 = dX_dt - dX_dt_model                                                            # Ec.5

    return [r1, r2, r3, r4, r5]
```

---

## 6. Eventos del solver

Definir como funciones con atributos `.terminal` y `.direction`:

```python
def event_X_obj(t, y, X_obj, *args):
    return y[0] - X_obj
event_X_obj.terminal  = True
event_X_obj.direction = -1    # sólo cuando X decrece hacia X_obj

def event_HR_saturacion(t, y, *args):
    # Calcular HR_local a partir del estado actual y las forzantes interpoladas
    ...
    return HR_local - HR_ALARM   # HR_ALARM = 0.95
event_HR_saturacion.terminal  = False
event_HR_saturacion.direction = +1    # sólo cuando HR sube

def event_T_prod_critica(t, y, T_max_K, *args):
    return y[1] - T_max_K     # T_max_K del catálogo; deshabilitar si es None
event_T_prod_critica.terminal  = True
event_T_prod_critica.direction = +1
```

---

## 7. Nuevas dataclasses a crear / modificar

### 7.1 ForzantesAire (nueva, en `core/camara.py`)

```python
@dataclass
class ForzantesAire:
    """Serie temporal de condiciones del aire de entrada a la cámara.
    
    Todos los arrays deben tener la misma longitud.
    El tiempo t_s[0] = 0.0 siempre (el motor integra desde t=0).
    """
    t_s: np.ndarray           # tiempo [s], t_s[0] = 0.0
    T_ent_K: np.ndarray       # temperatura de entrada [K]
    omega_ent: np.ndarray     # humedad absoluta de entrada [kg/kg ms]
    m_dot_aire_seco_kg_s: np.ndarray  # caudal másico [kg/s]
    T_amb_K: np.ndarray       # temperatura ambiente [K]
    v_viento_ms: np.ndarray   # velocidad del viento [m/s]
    
    def __post_init__(self):
        n = len(self.t_s)
        for nombre, arr in [("T_ent_K", self.T_ent_K),
                             ("omega_ent", self.omega_ent),
                             ("m_dot_aire_seco_kg_s", self.m_dot_aire_seco_kg_s),
                             ("T_amb_K", self.T_amb_K),
                             ("v_viento_ms", self.v_viento_ms)]:
            if len(arr) != n:
                raise ValueError(f"FORZANTES_LONGITUD_INCONSISTENTE: {nombre} tiene {len(arr)} elementos, esperado {n}")
        if self.t_s[0] != 0.0:
            raise ValueError("FORZANTES_T_INICIAL: t_s[0] debe ser 0.0")
```

### 7.2 ResultadosCamaraDinamico (nueva, en `core/camara.py`)

```python
@dataclass
class ResultadosCamaraDinamico:
    # Estado de terminación
    convergencia_a_X_obj: bool
    motivo_terminacion: str      # "X_OBJ_ALCANZADO" | "FIN_HORIZONTE"
                                 # | "DAÑO_TERMICO" | "FLUJO_SOSTENIDO_NULO"

    # Escalares de resultado
    t_secado_s: Optional[float]  # None si no convergió
    X_final: float
    masa_agua_evaporada_kg: float

    # Métricas operativas
    dias_efectivos_secado: float       # horas útiles / 24
    horas_rehumectacion_evitada: float
    horas_flujo_nulo: float

    # Trayectorias (para gráficos en P7)
    t_s: np.ndarray
    X: np.ndarray
    T_prod_K: np.ndarray
    T_flujo_K: np.ndarray
    HR_local: np.ndarray
    omega_salida: np.ndarray
    m_evap_acumulada_kg: np.ndarray

    # Diagnóstico numérico
    advertencias: list
    convergencia_fsolve_ok: bool
    n_pasos_fsolve_fallidos: int
```

### 7.3 Modificación de `camara_calc.py` existente

Renombrar las funciones públicas con sufijo `_estatico`. Ejemplo:

```python
# Antes:
def calcular_tiempo_secado(camara, producto, ...) -> ResultadosCamara:

# Después:
def calcular_tiempo_secado_estatico(camara, producto, ...) -> ResultadosCamara:
```

Esto preserva los 38 tests existentes (actualizar los imports en `test_camara_calc.py`).

---

## 8. Función `calcular_secado_dinamico` — firma completa

Ubicación: `calculos/camara_calc_dinamico.py`

```python
def calcular_secado_dinamico(
    *,
    # Estado inicial y objetivo
    masa_total_kg: float,
    X_0: float,
    X_obj: float,
    
    # Parámetros del producto (del catálogo YAML)
    # Obligatorios:
    modelo_capa_fina: str,           # "lewis" | "page" | "henderson_pabis" | "logaritmico"
    k_catalogo_min: float,           # k en min⁻¹ (convención de literatura)
    cp_prod_J_kgK: float,
    params_gab: dict,                # {"Xm": ..., "C": ..., "K": ...} o None → fallback escalar
    humedad_equilibrio_escalar: Optional[float],  # fallback si no hay GAB
    # Opcionales:
    n_page: float = 1.0,             # exponente Page (ignorado si modelo != "page")
    k0_arrhenius: Optional[float] = None,
    Ea_J_mol: Optional[float] = None,
    T_max_admisible_K: Optional[float] = None,
    
    # Geometría de la cámara
    A_cuerpo_m2: float,              # área total de paredes de la cámara
    A_prod_m2: float,                # área efectiva de intercambio del producto
    k_aisl_W_mK: float,              # conductividad térmica del aislante/pared
    esp_cam_m: float,                # espesor de la pared
    A_pasaje_m2: float,              # área de sección transversal del flujo en cámara
    
    # Serie temporal de forzantes (ya armada upstream)
    forzantes: ForzantesAire,
    
    # Configuración numérica
    horizonte_s: Optional[float] = None,   # None → usar len(forzantes)*intervalo
    tol_X_obj: float = 1e-4,
    rtol: float = 1e-6,
    atol: float = 1e-8,
    
) -> ResultadosCamaraDinamico:
    """Motor dinámico de secado de cámara.
    
    Integra el sistema acoplado (capa fina diferencial + balance de masa y
    energía del aire en cámara CSTR) a lo largo de la serie de forzantes.
    
    Aplica Política B de operación nocturna: flujo continuo 24/7, dX/dt clipeado
    a 0 cuando el balance daría rehumectación.
    
    Soporta tipologías Armario y Gran escala. No soporta tipología CAJA.
    
    Parameters
    ----------
    (ver descripción de campos arriba)
    
    Returns
    -------
    ResultadosCamaraDinamico
    """
```

---

## 9. Función `armar_forzantes_aire` — firma y lógica

Ubicación: `calculos/balance_global.py` (agregar al módulo existente)

```python
def armar_forzantes_aire(
    *,
    modo: str,                       # "diario" | "multi_dia" | "anual"
    n_dias: int = 1,                 # solo para modo "multi_dia"
    T_salida_colector_K: np.ndarray, # serie horaria 24 h del día criterio [K]
    omega_ambiente: np.ndarray,      # serie horaria 24 h [kg/kg ms] — no cambia en colector
    T_salida_auxiliar_K: Optional[np.ndarray],  # None si no hay auxiliar
    m_dot_aire_seco_kg_s: float,     # caudal de diseño constante (motor eléctrico)
    v_viento_ms: Optional[np.ndarray] = None,   # serie horaria 24 h — si extractor eólico
    T_amb_K: Optional[np.ndarray] = None,       # serie horaria 24 h [K]
    dt_s: float = 3600.0,            # intervalo temporal de la serie [s]
) -> ForzantesAire:
    """Construye la serie de forzantes de entrada a la cámara.
    
    Lógica:
    - T_ent = T_salida_auxiliar_K si hay auxiliar activo, T_salida_colector_K si no.
    - omega_ent = omega_ambiente (el colector/auxiliar no aporta vapor de agua).
    - ṁ = m_dot_aire_seco_kg_s constante (motor eléctrico) o función de v_viento
           con relación lineal extractor eólico (cuando v_viento_ms no es None).
    - Multi-día: replica la serie de 24 h N veces.
    - Anual: usa la serie completa tal como viene (debe tener 8760 h).
    """
```

---

## 10. Advertencias nuevas a registrar

Agregar al sistema de advertencias existente (`core/advertencias.py` o donde estén los códigos):

| Código | Severidad | Descripción |
| :--- | :--- | :--- |
| `CAM_X_OBJ_NO_ALCANZADO_EN_HORIZONTE` | WARNING | No se llegó a X_obj en el horizonte. Reportar X_final alcanzado. |
| `CAM_NOCHE_RIESGO_REHUMECTACION` | WARNING | Más de 3 h nocturnas con dX/dt clipeado. El emplazamiento puede requerir cierre nocturno. |
| `MOD_CAPA_FINA_NO_DISPONIBLE_DINAMICO` | WARNING | El producto sólo tiene parámetros Midilli. Se usa fallback al motor estático. |
| `CAM_HP_REDUCIDO_A_LEWIS` | INFO | Henderson-Pabis reducido a Lewis en motor dinámico (factor a ignorado). |
| `CAM_LOG_REDUCIDO_A_LEWIS` | INFO | Logarítmico reducido a Lewis en motor dinámico (offset c ignorado). |
| `PROD_K_CONSTANTE_SIN_ARRHENIUS` | INFO | k del producto tratada como constante; no hay parámetros k0/Ea en catálogo. |
| `FLUJO_NULO_TRANSITORIO` | INFO | ṁ < ṁ_min en pasos individuales. Acumulable. |
| `FLUJO_INSUFICIENTE_SISTEMATICO` | WARNING | ṁ < ṁ_min en >30% del horizonte. El diseño del extractor/ventilador no es viable. |
| `CAM_FSOLVE_FALLIDO` | WARNING | fsolve no convergió en N pasos. Resultados en esos instantes son aproximados. |

---

## 11. Modificaciones en UI

### 11.1 `ui/p4_camara.py` — agregar selector de modo

Agregar al inicio de la pestaña, con lógica de deshabilitación:

```python
modo_calculo = st.selectbox(
    "Modo de cálculo",
    options=["Dinámico (riguroso)", "Estático (rápido)"],
    help="Dinámico: acopla balance de masa/energía del aire con la cinética. "
         "Estático: modelo algebraico intensivo (no depende de masa ni T variable)."
)

# Si el producto tiene sólo Midilli → forzar estático con aviso
if producto_tiene_solo_midilli:
    modo_calculo = "Estático (rápido)"
    st.warning("El producto seleccionado sólo tiene parámetros Midilli, "
               "incompatibles con el motor dinámico. Se usa el modo estático.")

# Si la tipología es CAJA → forzar estático con aviso
if tipologia == "CAJA":
    modo_calculo = "Estático (rápido)"
    st.info("El motor dinámico no está disponible para tipología CAJA en esta versión.")
```

Agregar selector de horizonte temporal cuando modo = dinámico:

```python
if modo_calculo == "Dinámico (riguroso)":
    modo_horizonte = st.selectbox(
        "Horizonte de secado",
        options=["Diario (1 día)", "Multi-día", "Anual"],
    )
    if modo_horizonte == "Multi-día":
        n_dias = st.number_input("Número de días", min_value=1, max_value=21, value=3)
```

### 11.2 `ui/p7_resultados.py` — gráficas del motor dinámico

En el bloque de cámara de secado, si `ResultadosCamaraDinamico`:

- **Curva X(t):** eje X en horas o días (según horizonte). Marcar con línea vertical el instante de X_obj si se alcanzó. Marcar períodos de clipeo nocturno con banda sombreada.
- **Curva T_prod(t) y T_flujo(t):** superpuestas en el mismo gráfico.
- **Curva HR_local(t):** con línea punteada horizontal en 0.95.
- **Rotulado de no-convergencia:** si `convergencia_a_X_obj=False`, mostrar con `st.warning` el mensaje: "En {N} días de análisis no se alcanzó X_obj = {X_obj:.3f} kg/kg. Humedad final alcanzada: {X_final:.3f} kg/kg."

---

## 12. Tests a escribir — `test_camara_calc_dinamico.py`

### 12.1 Tests unitarios del motor (mínimo requerido)

```python
# Test 1 — Caso límite: aire infinito recupera el motor estático
def test_limite_aire_infinito():
    """Con ṁ → ∞, t_secado coincide con motor estático ±5%."""
    # Configurar ṁ = 1e5 kg/s, condiciones constantes, producto Lewis simple
    # Comparar t_secado_dinamico vs t_secado_estatico
    assert abs(t_din - t_est) / t_est < 0.05

# Test 2 — Flujo nulo sostenido
def test_flujo_nulo_sostenido():
    """Con ṁ = 0 en todo el horizonte, X_final == X_0 y hay advertencia."""
    # m_dot_aire = 0 en toda la serie
    assert resultado.X_final == pytest.approx(X_0, abs=1e-6)
    assert resultado.convergencia_a_X_obj == False
    assert any("FLUJO" in a.codigo for a in resultado.advertencias)

# Test 3 — Sin fuerza motriz (aire saturado)
def test_sin_fuerza_motriz():
    """Con HR_ent = 0.99 en todo el horizonte, dX/dt ≈ 0."""
    # omega_ent tal que HR ≈ 0.99 → X_eq > X en todo instante → clipeo total
    assert resultado.X_final == pytest.approx(X_0, abs=1e-4)

# Test 4 — Conservación de masa
def test_conservacion_masa():
    """La masa de agua evaporada acumulada es consistente con el cambio en X."""
    m_evap_esperada = m_seco * (resultado.X[0] - resultado.X[-1])
    assert resultado.masa_agua_evaporada_kg == pytest.approx(m_evap_esperada, abs=1e-4)

# Test 5 — Sensibilidad a masa: más masa → más tiempo
def test_sensibilidad_masa():
    """Duplicar la masa de producto aumenta el tiempo de secado."""
    res_5kg  = calcular_secado_dinamico(..., masa_total_kg=5.0, ...)
    res_10kg = calcular_secado_dinamico(..., masa_total_kg=10.0, ...)
    assert res_10kg.t_secado_s > res_5kg.t_secado_s
    # Y el efecto no es lineal (no se duplica exactamente)
    assert res_10kg.t_secado_s < 2.0 * res_5kg.t_secado_s  # sub-lineal

# Test 6 — Continuidad de X(t)
def test_continuidad_trayectoria():
    """X(t) no tiene saltos en transiciones amanecer/atardecer."""
    dX = np.diff(resultado.X)
    # Los saltos abruptos deben ser menores que un umbral físico razonable
    assert np.all(np.abs(dX) < 0.1)   # 0.1 kg/kg en un paso → irreal

# Test 7 — Multi-día: continuidad entre días
def test_multi_dia_continuidad():
    """X al final del día 1 coincide con X al inicio del día 2."""
    # En modo multi-día con 2 días, el X al t=86400 s es X al inicio del segundo día
    idx_fin_dia1 = np.searchsorted(resultado.t_s, 86400.0)
    assert resultado.X[idx_fin_dia1] == pytest.approx(resultado.X[idx_fin_dia1 + 1], abs=1e-6)

# Test 8 — No convergencia reportada correctamente
def test_advertencia_no_alcanza():
    """Si horizonte es demasiado corto, reporta X_final con advertencia."""
    # Horizonte de 1 hora para un producto que tarda días
    resultado = calcular_secado_dinamico(..., horizonte_s=3600.0, ...)
    assert resultado.convergencia_a_X_obj == False
    assert resultado.motivo_terminacion == "FIN_HORIZONTE"
    assert resultado.X_final > X_obj

# Test 9 — Page: MR_rel cercano a 0 no genera NaN
def test_page_mr_limite_inferior():
    """Con Page y X muy próximo a X_eq, no hay división por cero."""
    # X_0 muy próximo a X_obj muy próximo a X_eq → MR_rel → ε
    resultado = calcular_secado_dinamico(..., modelo_capa_fina="page", ...)
    assert not np.any(np.isnan(resultado.X))
    assert not np.any(np.isnan(resultado.T_prod_K))

# Test 10 — Regresión: dinámico vs estático en condiciones favorables
def test_regresion_vs_estatico():
    """En condiciones de aire en exceso, ambos motores coinciden ±5%."""
    # Motor estático con brentq
    t_est = calcular_tiempo_secado_estatico(...)
    # Motor dinámico con ṁ muy grande
    res_din = calcular_secado_dinamico(..., masa_total_kg=0.001, ...)
    assert abs(res_din.t_secado_s - t_est) / t_est < 0.05
```

### 12.2 Fixture recomendada

Crear un fixture en `conftest.py` o al inicio del archivo con:
- Un producto simple tipo Lewis (k=0.003 min⁻¹, GAB con Xm=0.05, C=10, K=0.8)
- Una serie de forzantes de 24 h con T_ent=333 K (60°C) constante, HR=0.3 constante, ṁ=0.05 kg/s constante
- Geometría simple: cámara 1×0.5×0.5 m, esp=0.05 m, k_aisl=0.04 W/mK

---

## 13. Plan de transición y compatibilidad

### 13.1 Archivos afectados — resumen

| Archivo | Acción | Detalle |
| :--- | :--- | :--- |
| `calculos/camara_calc.py` | Modificar | Renombrar funciones públicas con `_estatico` |
| `calculos/camara_calc_dinamico.py` | Crear | Motor nuevo completo |
| `calculos/balance_global.py` | Modificar | Agregar `armar_forzantes_aire()` |
| `core/camara.py` | Modificar | Agregar `ForzantesAire` y `ResultadosCamaraDinamico` |
| `ui/p4_camara.py` | Modificar | Agregar selector de modo y horizonte |
| `ui/p7_resultados.py` | Modificar | Gráficas multi-día y rotulado de no-convergencia |
| `tests/test_calculos/test_camara_calc.py` | Modificar | Actualizar imports con sufijo `_estatico` |
| `tests/test_calculos/test_camara_calc_dinamico.py` | Crear | 10 tests unitarios + regresión |

### 13.2 Orden de implementación sugerido

1. Renombrar funciones en `camara_calc.py` + corregir imports en tests → suite verde.
2. Crear `ForzantesAire` y `ResultadosCamaraDinamico` en `core/camara.py`.
3. Implementar `camara_calc_dinamico.py` (el motor nuevo, núcleo del trabajo).
4. Implementar `armar_forzantes_aire()` en `balance_global.py`.
5. Agregar tests en `test_camara_calc_dinamico.py`.
6. Modificar `p4_camara.py` con selector.
7. Modificar `p7_resultados.py` con gráficas nuevas.

### 13.3 Cómo verificar al final

- `pytest` en raíz debe dar todos los tests anteriores verdes + los 10 nuevos.
- Correr la app (`streamlit run app.py`) y verificar:
  - P4 con modo Estático reproduce el comportamiento previo exactamente.
  - P4 con modo Dinámico, masa 5 kg y masa 10 kg → tiempos distintos.
  - P4 con modo Dinámico, horizonte 1 día, producto que tarda 3 días → rotulado de no-convergencia visible en P7.

---

## 14. Referencias y archivos relacionados

- `calculos/psicrometria.py` — funciones de HR, ω_saturación, presión de vapor. Reutilizar sin modificar.
- `calculos/correlaciones_nusselt.py` — función `calcular_h_int()`. Reutilizar sin modificar.
- `colector_calc.py` — función de coeficiente convectivo por viento (McAdams). Copiar o importar.
- `Balance_de_calor_y_masa_en_camara.md` — documento de origen de las ecuaciones del balance. Las ecuaciones de esta especificación son fiel derivación de ese documento.
- `bitacora_sesion23.md` — bitácora de diseño con decisiones razonadas y referencias bibliográficas.
- Capítulo 2, RISSPA (en Project Knowledge) — base física del proceso de secado (tres fases, velocidad de secado, difusión, calor latente).
