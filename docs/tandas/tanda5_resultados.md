# TANDA 5 — DATACLASS `Resultados` Y CIERRE DEL MODELO DE DATOS CENTRAL
# Software de prediseño de secadores solares — INENCO/UNSa
# Sesión 8

---

## 1. Rol de `Resultados` en la arquitectura

`Resultados` es el **espejo de salida** del objeto `Proyecto`. Mientras que todas las
demás secciones (`Emplazamiento`, `Colector`, `Camara`, etc.) almacenan solo entradas
del usuario, `Resultados` almacena exclusivamente outputs calculados por los solvers.

Con Tanda 5 **se cierra el modelo de datos central**. El `Proyecto` queda completo:

```
Proyecto
├── meta
├── configuracion
├── emplazamiento
├── clima
├── colector          (None si tipología CAJA)
├── camara
├── auxiliar          (None si sin auxiliar)
├── motor             (None si convección natural)
└── resultados        ← ESTA TANDA
    ├── clima
    ├── colector
    ├── camara
    ├── auxiliar
    ├── motor
    └── global
```

---

## 2. Mecanismo de invalidación por hash (implementación concreta)

### 2.1 Dataclass base `BloqueResultados`

Todos los sub-bloques de `Resultados` heredan de esta clase base:

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib, json

@dataclass
class BloqueResultados:
    """
    Clase base para todos los bloques de resultados.
    Gestiona el mecanismo de invalidación por hash de entradas.
    """
    _stale: bool = field(default=True, init=False, repr=False)
    # True  → resultados desactualizados (entradas cambiaron o nunca se calculó).
    # False → resultados válidos para las entradas actuales.

    _hash_entradas: str | None = field(default=None, init=False, repr=False)
    # SHA-256 de las entradas que se usaron para calcular este bloque.
    # None si nunca se calculó.

    _timestamp: datetime | None = field(default=None, init=False, repr=False)
    # Cuándo se calculó por última vez (UTC).

    _advertencias_runtime: list = field(default_factory=list, init=False, repr=False)
    # Advertencias generadas durante el cálculo (post-solver).
    # Distinto de las advertencias estáticas de __post_init__ de las dataclasses
    # de entrada — esas viven en Colector.advertencias, Camara.advertencias, etc.

    def marcar_calculado(self, hash_entradas: str) -> None:
        """Llamar al finalizar el cálculo exitosamente."""
        object.__setattr__(self, '_stale', False)
        object.__setattr__(self, '_hash_entradas', hash_entradas)
        object.__setattr__(self, '_timestamp', datetime.now(timezone.utc))

    def marcar_stale(self) -> None:
        """Llamar cuando una entrada upstream cambia."""
        object.__setattr__(self, '_stale', True)

    def verificar_vigencia(self, hash_entradas_actual: str) -> bool:
        """
        Compara el hash actual de las entradas con el guardado.
        Si difieren, marca stale y retorna False.
        """
        if self._hash_entradas != hash_entradas_actual:
            self.marcar_stale()
            return False
        return not self._stale
```

### 2.2 Función de hash de entradas

```python
def calcular_hash_entradas(*secciones) -> str:
    """
    Calcula el SHA-256 de las entradas relevantes para un bloque de resultados.
    Recibe las secciones de entrada del Proyecto que afectan ese bloque.

    Uso:
        hash_col = calcular_hash_entradas(proyecto.emplazamiento,
                                          proyecto.clima,
                                          proyecto.colector)
        hash_cam = calcular_hash_entradas(proyecto.emplazamiento,
                                          proyecto.clima,
                                          proyecto.colector,
                                          proyecto.auxiliar,
                                          proyecto.camara)
    """
    import dataclasses
    datos = []
    for seccion in secciones:
        if seccion is None:
            datos.append(None)
        else:
            # dataclasses.asdict serializa recursivamente. Los campos con
            # pandas.DataFrame o numpy.ndarray necesitan conversión previa.
            d = dataclasses.asdict(seccion)
            datos.append(d)

    serializado = json.dumps(datos, sort_keys=True, default=str)
    return hashlib.sha256(serializado.encode()).hexdigest()
```

**Nota de implementación:** `json.dumps(..., default=str)` convierte datetime, Path y
otros tipos no serializables a string. Para arrays numpy/pandas dentro de las dataclasses,
se recomienda convertir a listas antes de serializar, o excluir los DataFrames de clima
del hash (dado que el clima se referencia por su propio hash de descarga NASA POWER).

### 2.3 Grafo de invalidación concreto

Cuando el usuario modifica una entrada, se invalidan en cascada todos los bloques
de resultados que dependen de ella:

```
ENTRADA MODIFICADA          → BLOQUES A INVALIDAR
─────────────────────────────────────────────────────────────────────
emplazamiento               → clima, colector, camara, motor, global
clima (descarga NASA POWER) → colector, camara, motor, global
colector                    → colector, camara, motor, global
auxiliar                    → camara, motor, global
camara                      → camara, motor, global
motor                       → motor, global
```

El bloque `resultados.clima` es especial: no tiene solver propio, solo
post-procesa los datos de NASA POWER. Se invalida con `emplazamiento`.

**Implementación en Streamlit:** cada widget de entrada en cada pestaña llama a un
callback que, al cambiar el valor, invoca `marcar_stale()` en los bloques afectados
según el grafo. La UI lee `_stale` para mostrar el badge "⚠ Desactualizado".

---

## 3. Estructura de `Resultados`

```python
@dataclass
class Resultados:
    clima:    ResultadosClima    = field(default_factory=ResultadosClima)
    colector: ResultadosColector = field(default_factory=ResultadosColector)
    camara:   ResultadosCamara   = field(default_factory=ResultadosCamara)
    auxiliar: ResultadosAuxiliar = field(default_factory=ResultadosAuxiliar)
    motor:    ResultadosMotor    = field(default_factory=ResultadosMotor)
    global_:  ResultadosGlobal   = field(default_factory=ResultadosGlobal)
    # Nota: `global` es palabra reservada en Python → usar `global_`
    # En la UI y en la serialización JSON se puede usar la clave "global".
```

---

## 4. Sub-bloques de `Resultados`

### 4.1 `ResultadosClima`

No tiene solver propio — es un post-proceso de los datos crudos de NASA POWER.

```python
@dataclass
class ResultadosClima(BloqueResultados):

    # Series temporales procesadas (DatetimeIndex tz-aware)
    # Cada campo es un pd.Series o None si no calculado aún.
    irradiancia_global_horizontal_W_m2:   object = None  # GHI
    irradiancia_directa_normal_W_m2:      object = None  # DNI
    irradiancia_difusa_horizontal_W_m2:   object = None  # DHI
    temperatura_ambiente_K:               object = None
    humedad_relativa_fraccion:            object = None
    velocidad_viento_m_s:                 object = None  # a 2 m
    presion_atm_Pa:                       object = None

    # Estadísticos del período (escalares)
    T_ambiente_media_K:     float | None = None
    T_ambiente_max_K:       float | None = None
    T_ambiente_min_K:       float | None = None
    irradiancia_media_W_m2: float | None = None
    energia_total_MJ_m2:    float | None = None  # integral GHI sobre el período
    horas_sol_efectivas:    float | None = None  # horas con GHI > 50 W/m²

    # Calidad
    fraccion_datos_validos: float | None = None  # [0, 1] — 1.0 = sin huecos
    n_horas_faltantes:      int   | None = None
```

### 4.2 `ResultadosColector`

Resultados del solver del colector (perfil espacial + globales temporales).

```python
@dataclass
class ResultadosColector(BloqueResultados):

    # ---- Perfil espacial a lo largo del colector ----
    # Cada campo es un np.ndarray de shape (n_x,) o None.
    # n_x = número de nodos de discretización espacial (definido en el solver).
    # Estos arrays corresponden a una condición de referencia (mediodía solar,
    # día típico) para visualización del perfil T(x), eta(x).

    x_m:            object = None  # posiciones a lo largo del colector [m]
    T_fluido_K:     object = None  # perfil de T del fluido [K]
    T_placa_K:      object = None  # perfil de T de la placa absorbente [K]
    T_cubierta_K:   object = None  # perfil de T de la cubierta [K]
    eta_local:      object = None  # eficiencia local instantánea [-]

    # ---- Series temporales (para el período analizado) ----
    # Cada campo es un pd.Series con DatetimeIndex o None.
    T_salida_K:          object = None  # T del fluido a la salida del colector
    eta_global:          object = None  # eficiencia global instantánea [-]
    Q_util_W:            object = None  # calor útil instantáneo [W]
    irradiancia_POA_W_m2: object = None # irradiancia en plano de colección

    # ---- Globales del período ----
    T_salida_media_K:    float | None = None
    T_salida_max_K:      float | None = None
    eta_media:           float | None = None
    Q_util_total_MJ:     float | None = None  # energía útil total del período
    largo_optimo_m:      float | None = None  # largo donde η empieza a caer
                                              # (resultado del barrido paramétrico)

    # ---- Advertencias runtime ----
    # Pobladas durante el cálculo, no en __post_init__.
    # Ejemplos: T_placa > T_max_material, estancamiento detectado, etc.
    # Usan los mismos códigos que las advertencias estáticas pero con prefijo _RT.
    # Ej: "RT_MAT_T_PLACA_EXCEDE_T_MAX_SERVICIO"
```

### 4.3 `ResultadosCamara`

Resultados del solver de la cámara (cinética de secado).

```python
@dataclass
class ResultadosCamara(BloqueResultados):

    # ---- Evolución temporal del secado ----
    tiempo_s:              object = None  # vector de tiempos [s]
    X_producto:            object = None  # humedad del producto X(t) [kg/kg ms]
    MR_producto:           object = None  # moisture ratio MR(t) [-]
    T_aire_camara_K:       object = None  # T del aire en la cámara [K]
    HR_aire_camara_fraccion: object = None  # HR del aire en cámara [0,1]
    omega_aire_kg_kg:      object = None  # humedad absoluta del aire [kg/kg_as]
    tasa_secado_kg_s:      object = None  # tasa de evaporación instantánea [kg/s]

    # ---- Resultados clave del ciclo de secado ----
    tiempo_secado_s:       float | None = None  # tiempo total para alcanzar X_objetivo
    tiempo_secado_h:       float | None = None  # idem en horas (para display)
    X_final_alcanzado:     float | None = None  # humedad final real [kg/kg ms]
    masa_agua_evaporada_kg: float | None = None # agua total evaporada [kg]
    energia_secado_MJ:     float | None = None  # energía total consumida en secado

    # ---- Indicadores de calidad del secado ----
    objetivo_alcanzado:    bool | None = None   # ¿se llegó a X_objetivo?
    fraccion_secado:       float | None = None  # X_final/X_inicial (0→1 = completo)

    # ---- Inocuidad (solo para carnes) ----
    a_w_final:             float | None = None  # actividad de agua al final
    inocuidad_ok:          bool | None = None   # True si a_w < 0.85

    # ---- Advertencias runtime ----
    # Incluye: INIO_A_W_FINAL_INSEGURA, PROD_T_FUERA_RANGO_CALIBRACION,
    # y cualquier advertencia dinámica del solver.
```

### 4.4 `ResultadosAuxiliar`

```python
@dataclass
class ResultadosAuxiliar(BloqueResultados):

    # ---- Balance energético del auxiliar ----
    energia_aportada_MJ:        float | None = None  # energía térmica total aportada
    fraccion_energia_total:     float | None = None  # qué % de la energía total del
                                                     # sistema viene del auxiliar
    horas_operacion:            float | None = None  # horas reales de operación

    # ---- Específico quemador de biomasa ----
    consumo_biomasa_kg:         float | None = None  # consumo total del período
    costo_biomasa_estimado_ARS: float | None = None  # opcional, si el usuario dio precio

    # ---- Específico resistencia eléctrica ----
    energia_electrica_kWh:      float | None = None  # consumo eléctrico total
    costo_electrico_estimado_ARS: float | None = None  # opcional
```

### 4.5 `ResultadosMotor`

```python
@dataclass
class ResultadosMotor(BloqueResultados):

    # ---- Punto de operación ----
    caudal_volumetrico_m3_s:    float | None = None
    perdida_carga_total_Pa:     float | None = None  # ΔP real calculada por solver
    velocidad_superficial_m_s:  float | None = None  # v en la sección de la cámara

    # ---- Potencias (calculadas también en Motor.__post_init__ con ΔP de diseño;
    #       aquí se recalculan con ΔP real del solver) ----
    potencia_hidraulica_W:      float | None = None
    potencia_eje_W:             float | None = None
    potencia_electrica_W:       float | None = None
    potencia_a_instalar_W:      float | None = None
    corriente_nominal_A:        float | None = None

    # ---- Indicadores ----
    eficiencia_sistema_ventilacion: float | None = None  # η_v × η_m
    potencia_especifica_W_kg_h:     float | None = None
    # W eléctricos por kg de agua evaporada por hora — indicador de eficiencia
    # de la instalación de ventilación.

    # ---- Advertencias runtime ----
    # Incluye MOT_DELTA_P_REAL_DISTINTA_DISENO si la ΔP real difiere > 30%
    # de la ΔP de diseño ingresada por el usuario.
```

### 4.6 `ResultadosGlobal`

Agrega todos los bloques anteriores en indicadores de sistema completo.

```python
@dataclass
class ResultadosGlobal(BloqueResultados):

    # ---- Balance energético global ----
    energia_solar_disponible_MJ:   float | None = None  # E solar en el área del colector
    energia_util_colector_MJ:      float | None = None  # energía entregada por el colector
    energia_auxiliar_MJ:           float | None = None  # energía del auxiliar (0 si None)
    energia_total_sistema_MJ:      float | None = None  # util_col + auxiliar
    energia_secado_MJ:             float | None = None  # energía consumida en evaporar agua
    fraccion_solar:                float | None = None  # solar / total [0,1]

    # ---- Indicadores de desempeño ----
    eficiencia_global_sistema:     float | None = None
    # η_global = energia_secado / energia_solar_disponible
    # Indicador de cuán bien el sistema convierte la radiación en secado.

    COP_secado:                    float | None = None
    # COP = masa_agua_evaporada_kg × Lv / energia_total_sistema_J
    # Lv = calor latente de vaporización (~2.45 MJ/kg a 20°C)
    # Adimensional. Valores típicos secadores solares: 0.10–0.35.

    consumo_electrico_total_kWh:   float | None = None  # motor + auxiliar eléctrico
    autonomia_solar_fraccion:      float | None = None  # 1.0 = 100% solar, sin auxiliar

    # ---- Resumen del ciclo de secado ----
    tiempo_secado_total_h:         float | None = None
    masa_producto_fresco_kg:       float | None = None
    masa_producto_seco_kg:         float | None = None
    masa_agua_evaporada_kg:        float | None = None
    rendimiento_masa:              float | None = None  # kg_seco / kg_fresco

    # ---- Dimensiones del sistema (resumen para informe) ----
    area_colectores_m2:            float | None = None
    area_camara_m2:                float | None = None  # área de planta
    n_bandejas:                    int   | None = None
    potencia_motor_a_instalar_W:   float | None = None

    # ---- Validaciones cruzadas a nivel Proyecto ----
    # (realizadas al calcular este bloque, no en __post_init__ de las secciones)
    errores_cruzados: list = field(default_factory=list)
    # Lista de strings con errores de coherencia detectados al integrar resultados.
    # Ej: "Motor dimensionado para 0.08 m³/s pero cámara requiere 0.12 m³/s".
```

---

## 5. Validaciones cruzadas a nivel `Proyecto`

Estas validaciones **no pueden hacerse en las dataclasses individuales** porque
requieren ver múltiples secciones simultáneamente. Se implementan en un método
`Proyecto.validar_coherencia_global()` que se llama antes de cualquier cálculo.

### 5.1 Errores duros a nivel Proyecto

```
PROY_CAJA_CON_COLECTOR
```
**Condición:** `tipologia == CAJA and colector is not None`.
**Tipo:** `ValueError`.
**Mensaje:** "Tipología CAJA no admite colector externo (la cámara ES el colector)."

```
PROY_CAJA_CON_MOTOR
```
**Condición:** `tipologia == CAJA and motor is not None`.
**Tipo:** `ValueError`.
**Mensaje:** "Tipología CAJA usa convección natural. Usar motor = None."

```
PROY_AUXILIAR_SERIE_SIN_COLECTOR
```
**Condición:** `auxiliar is not None
              and auxiliar.modo_operacion == SERIE_POSCOLECTOR
              and colector is None`.
**Tipo:** `ValueError`.
**Mensaje:** "Auxiliar en modo SERIE_POSCOLECTOR requiere colector definido."

```
PROY_MOTOR_SIN_CAMARA
```
**Condición:** `motor is not None and camara is None`.
**Tipo:** `ValueError`.
**Mensaje:** "Motor definido pero sin cámara. Definir cámara primero."

```
PROY_ANUAL_SIN_VECTORIZACION
```
**Condición:** `modo_analisis == ANUAL and colector is None`.
**Tipo:** `NotImplementedError`.
**Razón:** el análisis anual con tipología CAJA no está implementado en v0.
**Mensaje:** "Análisis anual para tipología CAJA no implementado en v0."

### 5.2 Advertencias a nivel Proyecto

```
PROY_CAUDAL_INCONSISTENTE
```
**Condición:** `motor is not None and camara is not None`
              `and abs(motor.caudal_volumetrico_m3_s - Q_camara) / Q_camara > 0.15`.
Donde `Q_camara` se deriva de `camara.flujo.caudal_masico_kg_s / rho_aire`.
**Severidad:** WARNING.
**Mensaje:** "Caudal del motor ({Q_m:.4f} m³/s) difiere >15% del caudal de cámara ({Q_c:.4f} m³/s). Verificar consistencia."

```
PROY_T_COLECTOR_EXCEDE_T_MAX_PRODUCTO
```
**Condición:** `colector is not None and camara is not None`
              `and resultados.colector.T_salida_max_K > camara.carga_producto.T_max_recomendada_K`.
**Severidad:** CRITICAL.
**Mensaje:** "T máxima del colector ({T:.1f}°C) supera T máxima recomendada para '{producto}' ({Tmax:.1f}°C). El producto puede dañarse."
**Nota:** requiere resultados calculados → advertencia runtime en `ResultadosGlobal`.

---

## 6. Serialización del `Proyecto` completo

El `Proyecto` completo (entradas + resultados) se puede serializar a JSON/YAML para:
- Guardar y cargar proyectos desde disco.
- Comparar escenarios (guardar dos versiones, mostrar side-by-side).
- Versionado en el repositorio de datos experimentales.

```python
import dataclasses, json

def proyecto_a_dict(proyecto: Proyecto) -> dict:
    """Serializa el Proyecto completo a dict (sin pandas/numpy)."""
    return dataclasses.asdict(proyecto)

def proyecto_a_json(proyecto: Proyecto, path: str) -> None:
    d = proyecto_a_dict(proyecto)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2, default=str)

def proyecto_desde_json(path: str) -> dict:
    """Devuelve el dict — la reconstrucción de dataclasses es trabajo futuro."""
    with open(path, encoding='utf-8') as f:
        return json.load(f)
```

**Nota:** la deserialización completa (dict → instancias de dataclasses anidadas)
es más compleja y queda para cuando tengamos el esqueleto del repo. En v0,
cargar un proyecto guardado puede hacerse vía dict directo si se necesita.

---

## 7. Cierre del modelo de datos central

Con Tanda 5 aprobada, el **modelo de datos central queda completo**. Resumen de todas
las dataclasses definidas:

```
core/
├── advertencias.py      → Advertencia, Severidad, BloqueResultados
├── proyecto.py          → Proyecto (raíz), Meta, Configuracion
├── emplazamiento.py     → Emplazamiento
├── clima.py             → Clima, CalidadClima
├── colector.py          → ColectorUnidad, BancoColectores, Chimenea, Colector
├── camara.py            → GeometriaCamara, ConstruccionCamara,
│                          ConfiguracionBandejas, ConfiguracionFlujo,
│                          CargaProducto, ModelosCamara, Camara
├── auxiliar.py          → Auxiliar, TipoAuxiliar, ModoOperacionAuxiliar
├── motor.py             → Motor, TipoAccionamiento
└── resultados.py        → Resultados, ResultadosClima, ResultadosColector,
                           ResultadosCamara, ResultadosAuxiliar,
                           ResultadosMotor, ResultadosGlobal
```

**Total de códigos de validación definidos a lo largo de las Tandas 1-5:**

| Prefijo | Dataclass | Errores duros | Advertencias |
|---|---|---|---|
| `GEO`, `MAT`, `BANCO`, `CHIM`, `COHE` | Colector | ~12 | ~14 |
| `GEO`, `CONS`, `BAND`, `FLUJO`, `PROD`, `INIO`, `COHE` | Camara | 14 | 20 |
| `AUX_` | Auxiliar | 6 | 4 |
| `MOT_` | Motor | 6 | 6 |
| `PROY_` | Proyecto (cruzadas) | 5 | 2 |
| **Total** | | **~43** | **~46** |

---

## 8. Decisiones tomadas en Tanda 5

- [x] **`BloqueResultados` como clase base** con `_stale`, `_hash_entradas`, `_timestamp` y métodos `marcar_calculado()`, `marcar_stale()`, `verificar_vigencia()`.
- [x] **Función `calcular_hash_entradas(*secciones)`** usando SHA-256 sobre JSON serializado de las dataclasses de entrada relevantes.
- [x] **Grafo de invalidación explícito** (tabla en §2.3): cada entrada invalida exactamente los bloques que dependen de ella.
- [x] **`ResultadosGlobal._` como agregador**: el bloque global solo se calcula cuando todos los bloques upstream están vigentes.
- [x] **`global_` como nombre de campo** (evita colisión con palabra reservada Python). La UI y el JSON usan la clave `"global"`.
- [x] **Validaciones cruzadas a nivel `Proyecto`** separadas de las validaciones de dataclasses individuales — se implementan en `Proyecto.validar_coherencia_global()`.
- [x] **`_advertencias_runtime` en cada bloque** para separar advertencias estáticas (de `__post_init__`) de las dinámicas (post-solver).
- [x] **Serialización a JSON** con `dataclasses.asdict` + `default=str` para los tipos no serializables. Deserialización diferida para versión futura.
- [x] **`COP_secado`** como indicador de eficiencia global — más informativo que `η_colector` sola porque captura el desempeño del sistema completo.

---

## 9. Próximos pasos (post-Tanda 5)

El modelo de datos está cerrado. Las siguientes tareas del plan acordado (bitácora §6):

1. **Estructura de carpetas del repo** (confirmación del layout `core/`, `app/`, `data/`, etc.).
2. **Convenciones de código** (naming, docstrings, type hints, formato Black/Ruff).
3. **`requirements.txt`** — lista de dependencias.
4. **Esqueleto del proyecto**: `app.py` mínimo con pestañas vacías navegables, módulos vacíos, `README.md`, `LICENSE` MIT.
5. **Crear repositorio en GitHub** (público).
6. **Empezar a codear**, comenzando por Pestaña 2 (emplazamiento y clima, que alimenta todo lo demás).
