# TANDA 4 — DATACLASSES `Auxiliar` Y `Motor`
# Software de prediseño de secadores solares — INENCO/UNSa
# Sesión 8

---

## 1. Contexto y decisiones de diseño previas

Del grafo de dependencias (bitácora §5.4):

```
colector → auxiliar ─┐
                     ├→ camara → motor → global
clima   ─────────────┘
```

- `Auxiliar` recibe aire desde el colector (o directamente del ambiente si es respaldo
  independiente) y lo entrega a la cámara con una temperatura mayor.
- `Motor` dimensiona el ventilador/extractor para vencer la pérdida de carga del sistema
  completo (colector + ductos + cámara).
- Ambas dataclasses son **opcionales** en el objeto `Proyecto`:
  - `proyecto.auxiliar = None` si no hay calentamiento auxiliar.
  - `proyecto.motor = None` en tipologías de convección natural (CAJA, ARMARIO sin motor).

---

## 2. Dataclass `Auxiliar`

### 2.1 Tipos de auxiliar soportados en v0

```python
class TipoAuxiliar(Enum):
    RESISTENCIA_ELECTRICA = "RESISTENCIA_ELECTRICA"
    QUEMADOR_BIOMASA      = "QUEMADOR_BIOMASA"
```

En v0 no se implementa: bomba de calor, gas natural, GLP (demasiada complejidad de
combustión). Se puede agregar en versiones futuras añadiendo valores al Enum.

### 2.2 Modos de operación

```python
class ModoOperacionAuxiliar(Enum):
    SERIE_POSCOLECTOR   = "SERIE_POSCOLECTOR"
    # El auxiliar calienta el aire DESPUÉS del colector, en serie.
    # Entradas: T_salida_colector, caudal_masico_colector.
    # Uso típico: ampliar el rango de temperatura de operación en días nublados
    # o como refuerzo nocturno con biomasa.

    RESPALDO_INDEPENDIENTE = "RESPALDO_INDEPENDIENTE"
    # El auxiliar opera INDEPENDIENTEMENTE del colector.
    # Tiene su propio circuito de aire (toma aire del ambiente directamente).
    # Uso típico: secado nocturno o en días sin sol con quemador de biomasa.
    # En este modo, el auxiliar ES la única fuente de calor.
```

### 2.3 Estructura de la dataclass

```python
@dataclass
class Auxiliar:
    # ------------------------------------------------------------------
    # IDENTIFICACIÓN
    # ------------------------------------------------------------------
    tipo: TipoAuxiliar
    modo_operacion: ModoOperacionAuxiliar

    # ------------------------------------------------------------------
    # PARÁMETROS COMUNES (todos los tipos)
    # ------------------------------------------------------------------
    potencia_nominal_W: float
    # Potencia térmica nominal entregada al aire [W].
    # Para resistencia eléctrica: potencia eléctrica ≈ potencia térmica (η ≈ 1).
    # Para quemador de biomasa: potencia térmica = PCI × flujo_combustible × η_quemador.

    temperatura_maxima_salida_K: float
    # T máxima del aire a la salida del auxiliar [K].
    # Límite de seguridad: no superar la T_max del material de bandeja / producto.
    # Se usa para verificar que el set point no dañe el producto.

    set_point_T_K: float | None = None
    # Temperatura objetivo del aire a la salida del auxiliar [K].
    # Si None: el auxiliar opera a potencia nominal constante (modo on/off manual).
    # Si definido: el modelo asume control proporcional ideal hasta la potencia nominal.

    fraccion_potencia_operacion: float = 1.0
    # Fracción de potencia nominal en operación [0, 1].
    # Permite modelar operación parcial (ej: quemador al 60% de carga).
    # Default = 1.0 (potencia completa).

    disponible_nocturno: bool = False
    # ¿Puede operar de noche?
    # Resistencia eléctrica: True si hay energía eléctrica disponible.
    # Quemador de biomasa: True siempre (no depende del sol).
    # Usado por el módulo de resultados para calcular horas de operación efectiva.

    # ------------------------------------------------------------------
    # PARÁMETROS ESPECÍFICOS DE QUEMADOR DE BIOMASA
    # ------------------------------------------------------------------
    tipo_biomasa: str | None = None
    # Nombre del combustible: "leña_seca", "pellets_madera", "cáscara_girasol",
    # "bagazo_caña", etc. String libre en v0.

    PCI_MJ_kg: float | None = None
    # Poder calorífico inferior del combustible [MJ/kg].
    # Referencia típica:
    #   leña seca (~20% humedad): PCI ≈ 14–15 MJ/kg
    #   pellets de madera:        PCI ≈ 17–18 MJ/kg
    #   cáscara de girasol:       PCI ≈ 16   MJ/kg
    #   bagazo de caña (seco):    PCI ≈ 17   MJ/kg

    eficiencia_quemador: float | None = None
    # η del quemador [fracción 0–1].
    # Quemadores de biomasa simples (tipo rocket): η ≈ 0.60–0.75.
    # Quemadores industriales: η ≈ 0.80–0.90.

    consumo_biomasa_kg_h: float | None = None
    # Consumo estimado de combustible [kg/h] a potencia nominal.
    # Relación: consumo = potencia_nominal_W / (PCI × 1e6/3600 × η).
    # Si se ingresan PCI y η, el módulo calcula esto automáticamente.
    # Si se ingresa directamente, se usa como override.

    # ------------------------------------------------------------------
    # PARÁMETROS ESPECÍFICOS DE RESISTENCIA ELÉCTRICA
    # ------------------------------------------------------------------
    tension_V: float | None = None
    # Tensión de alimentación [V]. Típico: 220 V (monofásico) o 380 V (trifásico).

    corriente_maxima_A: float | None = None
    # Corriente máxima [A]. Informativo para dimensionar instalación eléctrica.

    # ------------------------------------------------------------------
    # METADATOS
    # ------------------------------------------------------------------
    notas: str = ""
    advertencias: list = field(default_factory=list)
    # Poblada por __post_init__.
```

### 2.4 Validaciones de `Auxiliar.__post_init__`

#### Errores duros

```
AUX_POTENCIA_NO_POSITIVA
```
**Condición:** `potencia_nominal_W ≤ 0`.
**Tipo:** `ValueError`.

```
AUX_T_MAX_SALIDA_INVALIDA
```
**Condición:** `temperatura_maxima_salida_K < 273.15` (< 0°C) o
`temperatura_maxima_salida_K > 473.15` (> 200°C, límite razonable para secado de alimentos).
**Tipo:** `ValueError`.
**Mensaje:** "Temperatura máxima de salida del auxiliar ({T:.1f} K = {Tc:.1f}°C) fuera del rango operativo para secado de alimentos (0–200°C)."

```
AUX_SET_POINT_EXCEDE_T_MAX
```
**Condición:** `set_point_T_K is not None and set_point_T_K > temperatura_maxima_salida_K`.
**Tipo:** `ValueError`.
**Mensaje:** "Set point ({sp:.1f} K) supera la temperatura máxima de salida ({tmax:.1f} K)."

```
AUX_FRACCION_INVALIDA
```
**Condición:** `fraccion_potencia_operacion < 0 or fraccion_potencia_operacion > 1`.
**Tipo:** `ValueError`.

```
AUX_BIOMASA_SIN_PCI
```
**Condición:** `tipo == QUEMADOR_BIOMASA and PCI_MJ_kg is None and consumo_biomasa_kg_h is None`.
**Tipo:** `ValueError`.
**Razón:** sin PCI ni consumo directo no es posible calcular el balance de energía.
**Mensaje:** "Quemador de biomasa requiere PCI_MJ_kg o consumo_biomasa_kg_h."

```
AUX_BIOMASA_SIN_EFICIENCIA
```
**Condición:** `tipo == QUEMADOR_BIOMASA and PCI_MJ_kg is not None and eficiencia_quemador is None`.
**Tipo:** `ValueError`.
**Mensaje:** "Si se especifica PCI_MJ_kg, también se requiere eficiencia_quemador."

#### Advertencias

```
AUX_T_MAX_ALTA_PARA_PRODUCTO
```
**Condición:** `temperatura_maxima_salida_K > 343.15` (> 70°C).
**Severidad:** WARNING.
**Mensaje:** "Temperatura máxima de salida del auxiliar ({T:.1f}°C) puede dañar productos
sensibles al calor (carotenoides, aceites esenciales). Verificar con T_max del producto."

```
AUX_BIOMASA_EFICIENCIA_BAJA
```
**Condición:** `tipo == QUEMADOR_BIOMASA and eficiencia_quemador < 0.50`.
**Severidad:** WARNING.
**Mensaje:** "Eficiencia del quemador ({η:.0%}) muy baja. Considerar mejoras de diseño
(precalentamiento de aire, aislación del cuerpo del quemador)."

```
AUX_RESISTENCIA_SIN_TENSION
```
**Condición:** `tipo == RESISTENCIA_ELECTRICA and tension_V is None`.
**Severidad:** INFO.
**Mensaje:** "Tensión de alimentación no especificada. No se podrá verificar la corriente
máxima para el dimensionamiento eléctrico."

```
AUX_RESPALDO_SIN_DISPONIBILIDAD_NOCTURNA
```
**Condición:** `modo_operacion == RESPALDO_INDEPENDIENTE and not disponible_nocturno`.
**Severidad:** INFO.
**Mensaje:** "Auxiliar en modo RESPALDO_INDEPENDIENTE marcado como no disponible nocturno.
Verificar si es intencional — el modo respaldo independiente se usa habitualmente para
extender el secado fuera del horario solar."
```

---

## 3. Dataclass `Motor`

### 3.1 Alcance en v0

`Motor` en v0 es un **módulo de prediseño**, no de simulación dinámica. El objetivo es:

1. Calcular la **pérdida de carga total del sistema** (colector + cámara + ductos).
2. Elegir el punto de operación del ventilador (caudal × presión).
3. Calcular la potencia eléctrica del motor y la corriente nominal.
4. Disparar advertencias si el punto de operación está fuera del rango eficiente del ventilador.

No se modela: curva real del ventilador (se usa aproximación parabólica), variación de
densidad del aire con T, pérdidas en codos y expansiones (se usa coeficiente global).

### 3.2 Tipos de accionamiento soportados

```python
class TipoAccionamiento(Enum):
    MOTOR_ELECTRICO     = "MOTOR_ELECTRICO"     # ventilador axial o centrífugo con motor
    EXTRACTOR_EOLICO    = "EXTRACTOR_EOLICO"    # turbina eólica tipo "sombrero chino"
    CONVECCION_NATURAL  = "CONVECCION_NATURAL"  # sin motor (proyecto.motor = None)
```

`CONVECCION_NATURAL` → `proyecto.motor = None`. Si se instancia `Motor` con
`tipo == CONVECCION_NATURAL`, se levanta error duro.

### 3.3 Estructura de la dataclass

```python
@dataclass
class Motor:
    # ------------------------------------------------------------------
    # IDENTIFICACIÓN
    # ------------------------------------------------------------------
    tipo_accionamiento: TipoAccionamiento

    # ------------------------------------------------------------------
    # PARÁMETROS DEL SISTEMA (pérdida de carga)
    # ------------------------------------------------------------------
    caudal_volumetrico_m3_s: float
    # Caudal volumétrico de diseño [m³/s].
    # Relación: Q_vol = Q_masico / rho_aire.
    # rho_aire se calcula en el módulo a partir de T_media_sistema y
    # presión atmosférica del emplazamiento.

    perdida_carga_total_Pa: float | None = None
    # Pérdida de carga total del sistema [Pa].
    # Si None: el módulo la calcula a partir de los sub-componentes.
    # Si se ingresa directamente: se usa como override (ej: valor medido en campo).

    # Sub-componentes de pérdida de carga (todos opcionales; se usan si
    # perdida_carga_total_Pa es None):
    delta_P_colector_Pa: float | None = None
    # ΔP en el banco de colectores [Pa]. Calculado por el módulo de colector.

    delta_P_camara_Pa: float | None = None
    # ΔP en la cámara de secado [Pa].
    # Estimación: ΔP_camara = k_resistencia × (rho × v²/2) × n_bandejas.
    # k_resistencia depende del tipo de malla. En v0: k = 2.0 (estimación conservadora).

    delta_P_ductos_Pa: float | None = None
    # ΔP en ductos de conexión [Pa].
    # Si None: se estima como 20% de (ΔP_colector + ΔP_camara) como margen de seguridad.

    # ------------------------------------------------------------------
    # PARÁMETROS DEL VENTILADOR / MOTOR
    # ------------------------------------------------------------------
    eficiencia_ventilador: float = 0.55
    # η del ventilador [fracción 0–1].
    # Referencia: ventiladores axiales simples: η ≈ 0.45–0.60.
    # Ventiladores centrífugos de media presión: η ≈ 0.60–0.75.
    # Default conservador: 0.55.

    eficiencia_motor: float = 0.85
    # η del motor eléctrico [fracción 0–1].
    # Motores pequeños (<1 kW): η ≈ 0.75–0.85.
    # Default: 0.85.

    factor_servicio: float = 1.15
    # Factor de servicio para sobredimensionar la potencia nominal del motor [-].
    # Estándar NEMA: 1.15 para aplicaciones continuas.
    # Potencia nominal a instalar = potencia_calculada × factor_servicio.

    tension_V: float | None = None
    # Tensión de alimentación [V]. 220 (monofásico) o 380 (trifásico).

    # ------------------------------------------------------------------
    # PARÁMETROS DEL EXTRACTOR EÓLICO (solo si tipo == EXTRACTOR_EOLICO)
    # ------------------------------------------------------------------
    diametro_extractor_m: float | None = None
    # Diámetro del extractor tipo turbina [m]. Tallas comunes: 0.30, 0.45, 0.60 m.

    velocidad_viento_diseno_m_s: float | None = None
    # Velocidad de viento de diseño [m/s]. Usar percentil 50 del sitio.
    # Fuente: datos NASA POWER WS2M del emplazamiento.

    # ------------------------------------------------------------------
    # METADATOS
    # ------------------------------------------------------------------
    notas: str = ""
    advertencias: list = field(default_factory=list)
    # Poblada por __post_init__.

    # ------------------------------------------------------------------
    # RESULTADOS CALCULADOS EN __post_init__
    # (se computan si los datos son suficientes; None si faltan entradas)
    # ------------------------------------------------------------------
    potencia_hidraulica_W: float | None = field(default=None, init=False)
    # P_hid = Q_vol × ΔP_total [W]

    potencia_eje_W: float | None = field(default=None, init=False)
    # P_eje = P_hid / η_ventilador [W]

    potencia_electrica_W: float | None = field(default=None, init=False)
    # P_elec = P_eje / η_motor [W]

    potencia_a_instalar_W: float | None = field(default=None, init=False)
    # P_inst = P_elec × factor_servicio [W] → potencia nominal del motor a comprar

    corriente_nominal_A: float | None = field(default=None, init=False)
    # I = P_elec / (V × cos_phi) para monofásico (cos_phi = 0.85 default).
    # Solo si tension_V está definida.
```

### 3.4 Lógica de cálculo en `__post_init__`

```python
def __post_init__(self):
    advertencias = []

    # 1. Validaciones duras
    self._validar()  # ver §3.5

    # 2. Calcular ΔP_total si no fue ingresado directamente
    if self.perdida_carga_total_Pa is None:
        dP_col = self.delta_P_colector_Pa or 0.0
        dP_cam = self.delta_P_camara_Pa or 0.0
        dP_duc = self.delta_P_ductos_Pa
        if dP_duc is None:
            dP_duc = 0.20 * (dP_col + dP_cam)  # margen 20%
            advertencias.append(Advertencia(
                codigo="MOT_DUCTOS_ESTIMADOS",
                severidad=Severidad.INFO,
                mensaje=f"ΔP ductos no especificada. Estimada como 20% de "
                        f"ΔP_col+cam = {dP_duc:.1f} Pa.",
                campo="delta_P_ductos_Pa"
            ))
        dP_total = dP_col + dP_cam + dP_duc
        object.__setattr__(self, 'perdida_carga_total_Pa', dP_total)

    # 3. Calcular potencias
    if self.caudal_volumetrico_m3_s > 0 and self.perdida_carga_total_Pa > 0:
        P_hid  = self.caudal_volumetrico_m3_s * self.perdida_carga_total_Pa
        P_eje  = P_hid / self.eficiencia_ventilador
        P_elec = P_eje / self.eficiencia_motor
        P_inst = P_elec * self.factor_servicio

        object.__setattr__(self, 'potencia_hidraulica_W', P_hid)
        object.__setattr__(self, 'potencia_eje_W', P_eje)
        object.__setattr__(self, 'potencia_electrica_W', P_elec)
        object.__setattr__(self, 'potencia_a_instalar_W', P_inst)

        # 4. Corriente nominal
        if self.tension_V is not None:
            cos_phi = 0.85  # factor de potencia típico motor monofásico pequeño
            I = P_elec / (self.tension_V * cos_phi)
            object.__setattr__(self, 'corriente_nominal_A', I)

    object.__setattr__(self, 'advertencias', advertencias)
```

### 3.5 Validaciones de `Motor.__post_init__`

#### Errores duros

```
MOT_CONVECCION_NATURAL_CON_MOTOR
```
**Condición:** `tipo_accionamiento == CONVECCION_NATURAL`.
**Tipo:** `ValueError`.
**Mensaje:** "Para convección natural usar proyecto.motor = None, no instanciar Motor."

```
MOT_CAUDAL_NO_POSITIVO
```
**Condición:** `caudal_volumetrico_m3_s ≤ 0`.
**Tipo:** `ValueError`.

```
MOT_EFICIENCIA_VENTILADOR_INVALIDA
```
**Condición:** `not (0 < eficiencia_ventilador <= 1)`.
**Tipo:** `ValueError`.

```
MOT_EFICIENCIA_MOTOR_INVALIDA
```
**Condición:** `not (0 < eficiencia_motor <= 1)`.
**Tipo:** `ValueError`.

```
MOT_FACTOR_SERVICIO_INVALIDO
```
**Condición:** `factor_servicio < 1.0`.
**Tipo:** `ValueError`.
**Mensaje:** "Factor de servicio debe ser ≥ 1.0 (sin sobredimensionamiento)."

```
MOT_EXTRACTOR_SIN_DIAMETRO
```
**Condición:** `tipo == EXTRACTOR_EOLICO and diametro_extractor_m is None`.
**Tipo:** `ValueError`.
**Mensaje:** "Extractor eólico requiere diametro_extractor_m."

#### Advertencias

```
MOT_DUCTOS_ESTIMADOS
```
(Ver §3.4 — se genera en el cálculo si `delta_P_ductos_Pa` es None.)
**Severidad:** INFO.

```
MOT_POTENCIA_BAJA
```
**Condición:** `potencia_a_instalar_W is not None and potencia_a_instalar_W < 30`.
**Severidad:** INFO.
**Mensaje:** "Potencia a instalar ({P:.0f} W) muy baja. Verificar si un extractor eólico
o convección natural podría ser suficiente, evitando el costo de instalación eléctrica."

```
MOT_POTENCIA_ALTA
```
**Condición:** `potencia_a_instalar_W is not None and potencia_a_instalar_W > 5000`.
**Severidad:** WARNING.
**Mensaje:** "Potencia a instalar ({P:.0f} W) elevada para un secador solar. Revisar
las pérdidas de carga — posiblemente la geometría del colector o la cámara sea subóptima."

```
MOT_SIN_TENSION
```
**Condición:** `tipo == MOTOR_ELECTRICO and tension_V is None`.
**Severidad:** INFO.
**Mensaje:** "Tensión de alimentación no especificada. No se calculará corriente nominal."

```
MOT_EXTRACTOR_VIENTO_BAJO
```
**Condición:** `tipo == EXTRACTOR_EOLICO and velocidad_viento_diseno_m_s is not None
and velocidad_viento_diseno_m_s < 2.0`.
**Severidad:** WARNING.
**Mensaje:** "Velocidad de viento de diseño ({v:.1f} m/s) baja para extractor eólico.
El caudal generado puede ser insuficiente para el secado. Considerar motor eléctrico."

---

## 4. Tabla resumen de validaciones Tanda 4

| Código | Dataclass | Nivel | Severidad | Cuándo |
|---|---|---|---|---|
| `AUX_POTENCIA_NO_POSITIVA` | Auxiliar | Error duro | — | P ≤ 0 |
| `AUX_T_MAX_SALIDA_INVALIDA` | Auxiliar | Error duro | — | T < 0°C o > 200°C |
| `AUX_SET_POINT_EXCEDE_T_MAX` | Auxiliar | Error duro | — | set_point > T_max |
| `AUX_FRACCION_INVALIDA` | Auxiliar | Error duro | — | fraccion ∉ [0,1] |
| `AUX_BIOMASA_SIN_PCI` | Auxiliar | Error duro | — | biomasa sin PCI ni consumo |
| `AUX_BIOMASA_SIN_EFICIENCIA` | Auxiliar | Error duro | — | PCI definido sin η |
| `AUX_T_MAX_ALTA_PARA_PRODUCTO` | Auxiliar | Advertencia | WARNING | T_max > 70°C |
| `AUX_BIOMASA_EFICIENCIA_BAJA` | Auxiliar | Advertencia | WARNING | η < 50% |
| `AUX_RESISTENCIA_SIN_TENSION` | Auxiliar | Advertencia | INFO | resistencia sin V |
| `AUX_RESPALDO_SIN_DISPONIBILIDAD_NOCTURNA` | Auxiliar | Advertencia | INFO | respaldo no nocturno |
| `MOT_CONVECCION_NATURAL_CON_MOTOR` | Motor | Error duro | — | tipo = CONV_NAT |
| `MOT_CAUDAL_NO_POSITIVO` | Motor | Error duro | — | Q ≤ 0 |
| `MOT_EFICIENCIA_VENTILADOR_INVALIDA` | Motor | Error duro | — | η_v ∉ (0,1] |
| `MOT_EFICIENCIA_MOTOR_INVALIDA` | Motor | Error duro | — | η_m ∉ (0,1] |
| `MOT_FACTOR_SERVICIO_INVALIDO` | Motor | Error duro | — | fs < 1.0 |
| `MOT_EXTRACTOR_SIN_DIAMETRO` | Motor | Error duro | — | extractor sin diámetro |
| `MOT_DUCTOS_ESTIMADOS` | Motor | Advertencia | INFO | ΔP_ductos = None |
| `MOT_POTENCIA_BAJA` | Motor | Advertencia | INFO | P_inst < 30 W |
| `MOT_POTENCIA_ALTA` | Motor | Advertencia | WARNING | P_inst > 5000 W |
| `MOT_SIN_TENSION` | Motor | Advertencia | INFO | motor sin tensión |
| `MOT_EXTRACTOR_VIENTO_BAJO` | Motor | Advertencia | WARNING | v_viento < 2.0 m/s |

---

## 5. Integración en el objeto `Proyecto`

```python
@dataclass
class Proyecto:
    # ... campos existentes ...
    auxiliar: Auxiliar | None = None
    motor:    Motor    | None = None
```

**Reglas de negocio a nivel `Proyecto`** (no implementadas aún, se definirán en Tanda 5
al diseñar `Resultados`):

- Si `tipologia == CAJA` → `motor` debe ser `None` (CAJA usa convección natural).
- Si `tipologia == ARMARIO` con `motor is not None` → el motor debe ser
  `MOTOR_ELECTRICO` o `EXTRACTOR_EOLICO`.
- Si `auxiliar is not None` y `modo_operacion == SERIE_POSCOLECTOR` →
  `colector` no puede ser `None` (no hay colector del que ser "post").

Estas validaciones cruzadas van en `Proyecto.__post_init__`, no en las dataclasses
individuales, porque requieren ver múltiples secciones al mismo tiempo.

---

## 6. Decisiones de diseño tomadas en Tanda 4

- [x] **`Auxiliar` y `Motor` son opcionales en `Proyecto`** (pueden ser `None`).
- [x] **Los resultados de potencias se calculan en `Motor.__post_init__`**, no en un módulo separado. Esto facilita que la UI los muestre inmediatamente al definir el motor.
- [x] **`perdida_carga_total_Pa` puede ingresarse directamente** (override) para usuarios que tienen el dato de campo o de catálogo del fabricante.
- [x] **Factor de ductos = 20%** como estimación automática cuando no se especifica. Valor conservador estándar para sistemas de distribución de aire cortos.
- [x] **cos_phi = 0.85** como default para el cálculo de corriente nominal. Valor típico para motores de inducción de pequeña potencia.
- [x] **`TipoAuxiliar` y `TipoAccionamiento` son Enums**, no strings libres. Esto garantiza que el código falle en tiempo de construcción si se usa un valor no soportado.
- [x] **Extractor eólico soportado como tipo de accionamiento** pero sin modelo de curva de rendimiento en v0 — solo se ingresa diámetro y velocidad de viento de diseño; el cálculo de caudal se deja para el módulo de resultados usando tablas de fabricante o correlaciones empíricas.

---

## 7. Pendiente para Tanda 5 (`Resultados`)

- Validaciones cruzadas `Proyecto`-nivel (`motor == None` si tipología CAJA, etc.).
- `Resultados.auxiliar`: fracción de operación real vs nominal, ahorro energético, costo estimado de biomasa por ciclo de secado.
- `Resultados.motor`: resumen del punto de operación, eficiencia global del sistema de ventilación, potencia específica (W por kg de producto seco).
- Advertencias runtime de `Motor`: si la ΔP real calculada por el solver difiere >30% de la ΔP de diseño → `MOT_DELTA_P_REAL_DISTINTA_DISENO`.
