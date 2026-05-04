# TANDA 3 PASO 3 — VALIDACIONES E INVARIANTES DE `Camara`
# Software de prediseño de secadores solares — INENCO/UNSa
# Sesión 8

---

## 1. Filosofía (consistente con Tanda 2 paso 3)

Mismas dos categorías que en `Colector`:

- **Errores duros (`raise ValueError`):** el objeto queda en estado físicamente imposible o
  explícitamente no soportado en v0. La construcción falla. El usuario no puede continuar
  hasta resolver el problema.

- **Advertencias (`Advertencia` en lista):** configuraciones legales pero problemáticas.
  No bloquean construcción ni cálculos. Se acumulan y la UI las muestra con severidad.

**Convención de códigos:** `ÁREA_QUÉ_DÓNDE`, mayúsculas.
Áreas para `Camara`:
  - `GEO`  — geometría de la cámara
  - `CONS` — construcción (materiales de muros/cubierta)
  - `BAND` — bandejas (número, espesor, carga)
  - `FLUJO`— configuración de flujo de aire
  - `PROD` — producto (modelo, calidad de datos, rango de calibración)
  - `INIO` — inocuidad (específico para carnes)
  - `COHE` — coherencia cruzada entre subsecciones

La `Advertencia` es la misma dataclass definida en Tanda 2 paso 3 (`core/advertencias.py`).

---

## 2. Reparto de validaciones por nivel

```
Camara.__post_init__
│
├── valida GeometriaCamara       → errores GEO
├── valida ConstruccionCamara    → errores/advertencias CONS
├── valida ConfiguracionBandejas → errores/advertencias BAND
├── valida ConfiguracionFlujo    → errores/advertencias FLUJO
├── valida CargaProducto         → errores/advertencias PROD + INIO
└── valida coherencia cruzada    → errores/advertencias COHE
    (geometría × bandejas × flujo × carga producto)
```

Cada sub-validación puede ser un método privado `_validar_geometria()`, etc.
`Camara.advertencias: list[Advertencia]` consolida todo al final.

---

## 3. Errores duros

### 3.1 Geometría (`GeometriaCamara`)

```
GEO_DIMENSIONES_NO_POSITIVAS
```
**Condición:** cualquiera de `largo_m`, `ancho_m`, `alto_m` ≤ 0.
**Tipo:** `ValueError`.
**Mensaje:** "Dimensiones de la cámara deben ser positivas. Recibido: largo={largo}, ancho={ancho}, alto={alto}."

```
GEO_VOLUMEN_MINIMO
```
**Condición:** `largo × ancho × alto < 0.01` m³ (10 litros).
**Tipo:** `ValueError`.
**Razón:** un secador funcional mínimo necesita espacio para al menos una bandeja.
**Mensaje:** "Volumen de cámara demasiado pequeño ({vol:.4f} m³). Mínimo operativo: 0.01 m³."

---

### 3.2 Bandejas (`ConfiguracionBandejas`)

```
BAND_N_BANDEJAS_NO_POSITIVO
```
**Condición:** `n_bandejas < 1`.
**Tipo:** `ValueError`.
**Mensaje:** "Número de bandejas debe ser ≥ 1."

```
BAND_ESPESOR_NO_POSITIVO
```
**Condición:** `espesor_capa_m ≤ 0`.
**Tipo:** `ValueError`.
**Mensaje:** "Espesor de capa de producto debe ser positivo."

```
BAND_SEPARACION_INSUFICIENTE
```
**Condición:** `separacion_entre_bandejas_m < espesor_capa_m + 0.01`.
**Tipo:** `ValueError`.
**Razón:** físicamente imposible — la capa de producto no cabe entre bandejas con margen
mínimo de 1 cm para circulación de aire.
**Mensaje:** "Separación entre bandejas ({sep:.3f} m) insuficiente para espesor de capa ({esp:.3f} m) + margen mínimo de 0.01 m."

---

### 3.3 Flujo de aire (`ConfiguracionFlujo`)

```
FLUJO_CAUDAL_NO_POSITIVO
```
**Condición:** `caudal_masico_kg_s ≤ 0`.
**Tipo:** `ValueError`.
**Mensaje:** "Caudal másico debe ser positivo."

```
FLUJO_RECIRCULACION_NO_IMPLEMENTADA
```
**Condición:** `fraccion_recirculacion > 0`.
**Tipo:** `NotImplementedError`.
**Razón:** recirculación no implementada en v0 (complejidad adicional en balance de masa
de vapor — el aire recirculado ya está parcialmente saturado).
**Mensaje:** "Recirculación de aire (fraccion={frac}) no implementada en v0. Usar fraccion_recirculacion=0."

```
FLUJO_DIRECCION_NO_SOPORTADA
```
**Condición:** `direccion_flujo` no está en `{HORIZONTAL, VERTICAL_ASCENDENTE}`.
**Tipo:** `NotImplementedError`.
**Razón:** flujo vertical descendente requiere un modelo de presión diferente — no implementado en v0.
**Mensaje:** "Dirección de flujo '{dir}' no soportada en v0. Opciones: HORIZONTAL, VERTICAL_ASCENDENTE."

---

### 3.4 Carga de producto (`CargaProducto`)

```
PROD_MASA_NO_POSITIVA
```
**Condición:** `masa_total_kg ≤ 0`.
**Tipo:** `ValueError`.
**Mensaje:** "Masa total de producto debe ser positiva."

```
PROD_HUMEDAD_INICIAL_NEGATIVA
```
**Condición:** `humedad_inicial_X < 0`.
**Tipo:** `ValueError`.
**Mensaje:** "Humedad inicial en base seca no puede ser negativa."

```
PROD_HUMEDAD_OBJETIVO_NEGATIVA
```
**Condición:** `humedad_objetivo_X < 0`.
**Tipo:** `ValueError`.
**Mensaje:** "Humedad objetivo en base seca no puede ser negativa."

```
PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL
```
**Condición:** `humedad_objetivo_X >= humedad_inicial_X`.
**Tipo:** `ValueError`.
**Mensaje:** "Humedad objetivo ({obj:.3f}) debe ser menor que humedad inicial ({ini:.3f}). El secado reduce la humedad."

```
MOD_CAPA_FINA_NO_DISPONIBLE
```
**Condición:** el modelo de capa fina seleccionado para el producto no tiene `params`
calibrados (todos `null`) en el catálogo YAML.
**Tipo:** `ValueError`.
**Mensaje:** "Modelo de capa fina '{modelo}' no disponible para '{producto}'. Cargar parámetros en el catálogo o seleccionar otro modelo."

```
MOD_ISOTERMA_NO_DISPONIBLE
```
**Condición:** el modelo de isoterma seleccionado para el producto no tiene `params`
calibrados en el catálogo YAML.
**Tipo:** `ValueError`.
**Razón:** la isoterma es necesaria para calcular la humedad de equilibrio, que es condición
de borde del sistema de EDOs de la cámara.
**Mensaje:** "Isoterma '{modelo}' no disponible para '{producto}'. Cargar parámetros o usar `humedad_equilibrio_aire_seco` como fallback (previa advertencia)."

**Excepción al error duro de isoterma:** si el catálogo tiene `humedad_equilibrio_aire_seco`
definido como fallback escalar, se permite continuar **sin error duro** pero **con advertencia
CRITICAL** `PROD_ISOTERMA_FALLBACK`. Ver §4.

---

### 3.5 Coherencia cruzada

```
COHE_BANDEJAS_NO_CABEN_EN_CAMARA
```
**Condición:** `n_bandejas × separacion_entre_bandejas_m > alto_m`.
**Tipo:** `ValueError`.
**Mensaje:** "Las {n} bandejas con separación {sep:.3f} m requieren {req:.3f} m de alto; la cámara tiene {alto:.3f} m."

```
COHE_AREA_BANDEJA_EXCEDE_CAMARA
```
**Condición:** `area_bandeja_m2 > largo_m × ancho_m`.
**Tipo:** `ValueError`.
**Mensaje:** "Área de bandeja ({ab:.3f} m²) excede el área de planta de la cámara ({ac:.3f} m²)."

```
COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA
```
**Condición:** `masa_total_kg / n_bandejas / area_bandeja_m2 > densidad_carga_max_kg_m2`.
Donde `densidad_carga_max_kg_m2` es un límite físico interno de ~20 kg/m² (capa de 3-4 cm
de densidad ~500 kg/m³ como máximo razonable para capa fina).
**Tipo:** `ValueError`.
**Mensaje:** "Carga de producto ({carga:.1f} kg/m²/bandeja) excede densidad máxima razonable para capa fina ({max:.1f} kg/m²). Revisar masa total o número/área de bandejas."

```
COHE_TIPOLOGIA_CAJA_CON_COLECTOR
```
**Condición:** `tipologia == CAJA` y `proyecto.colector is not None`.
**Tipo:** `ValueError`.
**Razón:** en tipología CAJA la cámara ES el colector — no puede haber colector externo.
Esta validación se hace a nivel `Proyecto`, no `Camara`, pero se lista aquí como referencia.
**Mensaje:** "Tipología CAJA no admite colector externo. proyecto.colector debe ser None."

---

## 4. Advertencias estáticas

### 4.1 Geometría

```
GEO_RELACION_ASPECTO_EXTREMA
```
**Condición:** `largo/ancho > 10` o `largo/ancho < 0.1`.
**Severidad:** WARNING.
**Mensaje:** "Relación largo/ancho = {ratio:.1f}. Una cámara muy alargada o muy cuadrada puede generar flujo no uniforme. Rango recomendado: 0.5–5."

```
GEO_ALTO_INUSUAL
```
**Condición:** `alto_m < 0.3` o `alto_m > 3.0`.
**Severidad:** WARNING.
**Mensaje:** "Alto de cámara ({alto:.2f} m) fuera del rango típico para secadores solares (0.3–3.0 m)."

---

### 4.2 Construcción

```
CONS_CUBIERTA_TRANSLUCIDA_FOTOSENSIBLE
```
**Condición:** `cubierta_translucida == True` y `producto.fotosensible == True`.
**Severidad:** WARNING.
**Mensaje:** "Producto fotosensible '{producto}' con cubierta translúcida. La exposición a radiación UV puede degradar pigmentos/aceites esenciales. Considerar cubierta opaca o filtro UV."

```
CONS_SIN_AISLACION_LATERAL
```
**Condición:** conductancia térmica efectiva de muros laterales > 2.0 W/(m²·K)
(material de baja resistencia térmica sin aislación).
**Severidad:** INFO.
**Mensaje:** "Muros laterales con baja resistencia térmica. Considerar aislación para mejorar eficiencia del secador."

---

### 4.3 Bandejas

```
BAND_ESPESOR_CAPA_GRANDE
```
**Condición:** `espesor_capa_m > 0.05` (5 cm).
**Severidad:** WARNING.
**Razón:** los modelos de capa fina asumen que la resistencia interna de masa es
despreciable respecto a la resistencia externa. Para capas gruesas esta hipótesis falla.
**Mensaje:** "Espesor de capa {esp:.3f} m supera el límite típico de capa fina (0.05 m). Los modelos de capa fina pueden subestimar el tiempo de secado. Considerar bandeja más delgada o modelo difusivo."

```
BAND_N_BANDEJAS_ELEVADO
```
**Condición:** `n_bandejas > 20`.
**Severidad:** INFO.
**Mensaje:** "Número de bandejas elevado ({n}). Verificar uniformidad de flujo de aire entre bandejas."

```
BAND_MALLA_SIN_ESPECIFICAR
```
**Condición:** `tipo_malla` es `None` o `"sin_especificar"`.
**Severidad:** INFO.
**Mensaje:** "Tipo de malla de bandeja no especificado. La resistencia de la malla afecta la caída de presión total del sistema."

---

### 4.4 Flujo de aire

```
FLUJO_VELOCIDAD_SUPERFICIAL_BAJA
```
**Condición:** velocidad superficial calculada `v_sup = caudal / (ancho × alto) < 0.3 m/s`.
**Severidad:** WARNING.
**Razón:** por debajo de ~0.3 m/s el coeficiente convectivo cae significativamente y el
secado pasa a estar limitado por la resistencia externa de masa (el modelo de capa fina
fue calibrado típicamente a v ≥ 0.5 m/s).
**Mensaje:** "Velocidad superficial de aire ({v:.2f} m/s) por debajo del rango típico de calibración de modelos de capa fina (≥ 0.5 m/s). El modelo puede sobrestimar la tasa de secado."

```
FLUJO_VELOCIDAD_SUPERFICIAL_ALTA
```
**Condición:** `v_sup > 3.0 m/s`.
**Severidad:** INFO.
**Mensaje:** "Velocidad superficial alta ({v:.2f} m/s). Verificar que la potencia del ventilador sea compatible con la caída de presión del sistema."

```
FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA
```
**Condición:** `HR_entrada_fraccion` es `None`.
**Severidad:** WARNING.
**Mensaje:** "Humedad relativa de entrada del aire no especificada. El cálculo de la humedad de equilibrio usará el valor de fallback del catálogo, reduciendo la precisión del modelo."

---

### 4.5 Producto / modelos

```
PROD_CALIDAD_DATOS_BAJA
```
**Condición:** `calidad_datos` del modelo seleccionado es `BAJA` o `ESTIMADA_POR_ANALOGIA`.
**Severidad:** WARNING.
**Mensaje:** "Modelo '{modelo}' para '{producto}' tiene calidad de datos '{calidad}'. Los resultados son orientativos. Ver notas en catálogo."

```
PROD_ISOTERMA_FALLBACK
```
**Condición:** no hay isoterma calibrada y se usa `humedad_equilibrio_aire_seco` como
escalar de fallback.
**Severidad:** CRITICAL.
**Mensaje:** "Sin isoterma calibrada para '{producto}'. Usando humedad de equilibrio escalar ({Xeq:.3f} kg/kg ms) como fallback. El cálculo de la cinética de secado tendrá precisión reducida — la humedad de equilibrio real depende de la HR del aire en cámara."

```
PROD_T_FUERA_RANGO_CALIBRACION
```
**Condición:** la temperatura de operación estimada (T_salida del colector) está fuera del
rango de calibración del modelo de capa fina del producto, con un margen del 15%.
Por ejemplo: modelo calibrado a 40-60°C y T_operacion = 75°C → fuera de rango.
**Severidad:** WARNING.
**Mensaje:** "Temperatura de operación estimada ({T:.1f} °C) fuera del rango de calibración del modelo '{modelo}' para '{producto}' ({Tmin:.1f}–{Tmax:.1f} °C). La extrapolación puede ser imprecisa."
**Nota de implementación:** este check requiere que `Colector` haya calculado T_salida
primero → es un chequeo de runtime, no estático puro. En `__post_init__` solo se puede
hacer si T_operacion se pasa explícitamente; de lo contrario, moverlo a `Resultados.camara.advertencias_runtime`.

```
PROD_HUMEDAD_OBJETIVO_INALCANZABLE
```
**Condición:** `humedad_objetivo_X < humedad_equilibrio_aire_seco × 0.95`.
**Severidad:** CRITICAL.
**Razón:** la humedad de equilibrio es el límite termodinámico de secado bajo las
condiciones de aire. Si el objetivo está por debajo, el secado no puede alcanzarlo.
**Mensaje:** "Humedad objetivo ({obj:.3f} kg/kg ms) está por debajo de la humedad de equilibrio estimada ({Xeq:.3f} kg/kg ms). El secador no podrá alcanzar ese objetivo bajo las condiciones de operación actuales."

---

### 4.6 Inocuidad (solo para carnes)

```
INIO_PRODUCTO_CARNE_SIN_ISOTERMA
```
**Condición:** `producto.categoria == CARNE` y no hay isoterma calibrada.
**Severidad:** CRITICAL.
**Razón:** para carnes la actividad de agua final es un criterio de inocuidad obligatorio
(a_w < 0.85 para inhibir patógenos). Sin isoterma no se puede calcular a_w.
**Mensaje:** "ALERTA DE INOCUIDAD: producto de categoría CARNE sin isoterma calibrada. No es posible verificar que a_w < 0.85 en el producto seco. Cargar isoterma de carne (con nivel de sal equivalente) antes de usar los resultados para toma de decisiones."

```
INIO_A_W_FINAL_INSEGURA
```
**Condición:** `a_w_final_calculada >= 0.85` (si se pudo calcular a partir de la isoterma
y la humedad final estimada).
**Severidad:** CRITICAL.
**Razón:** a_w ≥ 0.85 permite el crecimiento de Staphylococcus aureus, Salmonella y otros
patógenos. Producto no estable a temperatura ambiente.
**Mensaje:** "ALERTA DE INOCUIDAD: a_w final estimada ({aw:.3f}) ≥ 0.85. El producto no será microbiológicamente estable. Extender el tiempo de secado o reducir la humedad objetivo."
**Nota:** este check es de runtime (depende del resultado del cálculo), no puramente estático. Definir en `Resultados.camara.advertencias_runtime`. Se lista aquí para completitud del dominio de inocuidad.

---

## 5. Tabla resumen

| Código | Nivel | Severidad | Cuándo |
|---|---|---|---|
| `GEO_DIMENSIONES_NO_POSITIVAS` | Error duro | — | dim ≤ 0 |
| `GEO_VOLUMEN_MINIMO` | Error duro | — | vol < 0.01 m³ |
| `BAND_N_BANDEJAS_NO_POSITIVO` | Error duro | — | n < 1 |
| `BAND_ESPESOR_NO_POSITIVO` | Error duro | — | esp ≤ 0 |
| `BAND_SEPARACION_INSUFICIENTE` | Error duro | — | sep < esp + 0.01 |
| `FLUJO_CAUDAL_NO_POSITIVO` | Error duro | — | Q ≤ 0 |
| `FLUJO_RECIRCULACION_NO_IMPLEMENTADA` | Error duro | — | fraccion > 0 |
| `FLUJO_DIRECCION_NO_SOPORTADA` | Error duro | — | dir ∉ {HORIZ, VERT_ASC} |
| `PROD_MASA_NO_POSITIVA` | Error duro | — | masa ≤ 0 |
| `PROD_HUMEDAD_INICIAL_NEGATIVA` | Error duro | — | X_ini < 0 |
| `PROD_HUMEDAD_OBJETIVO_NEGATIVA` | Error duro | — | X_obj < 0 |
| `PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL` | Error duro | — | X_obj ≥ X_ini |
| `MOD_CAPA_FINA_NO_DISPONIBLE` | Error duro | — | params null en catálogo |
| `MOD_ISOTERMA_NO_DISPONIBLE` | Error duro | — | params null y sin fallback |
| `COHE_BANDEJAS_NO_CABEN_EN_CAMARA` | Error duro | — | n × sep > alto |
| `COHE_AREA_BANDEJA_EXCEDE_CAMARA` | Error duro | — | A_band > largo×ancho |
| `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA` | Error duro | — | carga > 20 kg/m² |
| `COHE_TIPOLOGIA_CAJA_CON_COLECTOR` | Error duro | — | tipología CAJA + colector ≠ None |
| `GEO_RELACION_ASPECTO_EXTREMA` | Advertencia | WARNING | largo/ancho > 10 o < 0.1 |
| `GEO_ALTO_INUSUAL` | Advertencia | WARNING | alto < 0.3 o > 3.0 m |
| `CONS_CUBIERTA_TRANSLUCIDA_FOTOSENSIBLE` | Advertencia | WARNING | translúcida + fotosensible |
| `CONS_SIN_AISLACION_LATERAL` | Advertencia | INFO | U_muros > 2 W/(m²K) |
| `BAND_ESPESOR_CAPA_GRANDE` | Advertencia | WARNING | esp > 0.05 m |
| `BAND_N_BANDEJAS_ELEVADO` | Advertencia | INFO | n > 20 |
| `BAND_MALLA_SIN_ESPECIFICAR` | Advertencia | INFO | malla = None |
| `FLUJO_VELOCIDAD_SUPERFICIAL_BAJA` | Advertencia | WARNING | v < 0.3 m/s |
| `FLUJO_VELOCIDAD_SUPERFICIAL_ALTA` | Advertencia | INFO | v > 3.0 m/s |
| `FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA` | Advertencia | WARNING | HR_entrada = None |
| `PROD_CALIDAD_DATOS_BAJA` | Advertencia | WARNING | calidad BAJA o ANALOGIA |
| `PROD_ISOTERMA_FALLBACK` | Advertencia | CRITICAL | sin isoterma, usa escalar |
| `PROD_T_FUERA_RANGO_CALIBRACION` | Advertencia | WARNING | T_op fuera rango modelo |
| `PROD_HUMEDAD_OBJETIVO_INALCANZABLE` | Advertencia | CRITICAL | X_obj < X_eq × 0.95 |
| `INIO_PRODUCTO_CARNE_SIN_ISOTERMA` | Advertencia | CRITICAL | CARNE sin isoterma |
| `INIO_A_W_FINAL_INSEGURA` | Advertencia runtime | CRITICAL | a_w ≥ 0.85 (post-solver) |

---

## 6. Estructura de implementación sugerida

```python
# core/camara.py

def __post_init__(self):
    advertencias: list[Advertencia] = []

    advertencias += self._validar_geometria()
    advertencias += self._validar_construccion()
    advertencias += self._validar_bandejas()
    advertencias += self._validar_flujo()
    advertencias += self._validar_producto()
    advertencias += self._validar_coherencia()

    object.__setattr__(self, 'advertencias', advertencias)
    # (si Camara es frozen=True usar object.__setattr__)


def _validar_geometria(self) -> list[Advertencia]:
    g = self.geometria
    advertencias = []

    # --- Errores duros ---
    if g.largo_m <= 0 or g.ancho_m <= 0 or g.alto_m <= 0:
        raise ValueError(
            f"GEO_DIMENSIONES_NO_POSITIVAS: dimensiones deben ser positivas. "
            f"Recibido: largo={g.largo_m}, ancho={g.ancho_m}, alto={g.alto_m}."
        )
    vol = g.largo_m * g.ancho_m * g.alto_m
    if vol < 0.01:
        raise ValueError(
            f"GEO_VOLUMEN_MINIMO: volumen {vol:.4f} m³ < 0.01 m³ mínimo operativo."
        )

    # --- Advertencias ---
    ratio = g.largo_m / g.ancho_m
    if ratio > 10 or ratio < 0.1:
        advertencias.append(Advertencia(
            codigo="GEO_RELACION_ASPECTO_EXTREMA",
            severidad=Severidad.WARNING,
            mensaje=f"Relación largo/ancho = {ratio:.1f}. Rango recomendado: 0.5–5.",
            campo="geometria.largo_m / geometria.ancho_m",
            sugerencia="Verificar uniformidad de flujo de aire."
        ))
    if not (0.3 <= g.alto_m <= 3.0):
        advertencias.append(Advertencia(
            codigo="GEO_ALTO_INUSUAL",
            severidad=Severidad.WARNING,
            mensaje=f"Alto de cámara {g.alto_m:.2f} m fuera del rango típico (0.3–3.0 m).",
            campo="geometria.alto_m"
        ))

    return advertencias


def _validar_bandejas(self) -> list[Advertencia]:
    b = self.bandejas
    advertencias = []

    # --- Errores duros locales ---
    if b.n_bandejas < 1:
        raise ValueError("BAND_N_BANDEJAS_NO_POSITIVO: n_bandejas debe ser ≥ 1.")
    if b.espesor_capa_m <= 0:
        raise ValueError("BAND_ESPESOR_NO_POSITIVO: espesor_capa_m debe ser positivo.")
    if b.separacion_entre_bandejas_m < b.espesor_capa_m + 0.01:
        raise ValueError(
            f"BAND_SEPARACION_INSUFICIENTE: separación {b.separacion_entre_bandejas_m:.3f} m "
            f"< espesor {b.espesor_capa_m:.3f} m + margen 0.01 m."
        )

    # --- Advertencias locales ---
    if b.espesor_capa_m > 0.05:
        advertencias.append(Advertencia(
            codigo="BAND_ESPESOR_CAPA_GRANDE",
            severidad=Severidad.WARNING,
            mensaje=f"Espesor de capa {b.espesor_capa_m:.3f} m > 0.05 m. "
                    f"Los modelos de capa fina pueden subestimar el tiempo de secado.",
            campo="bandejas.espesor_capa_m",
            sugerencia="Reducir espesor o usar modelo difusivo."
        ))
    if b.n_bandejas > 20:
        advertencias.append(Advertencia(
            codigo="BAND_N_BANDEJAS_ELEVADO",
            severidad=Severidad.INFO,
            mensaje=f"{b.n_bandejas} bandejas. Verificar uniformidad de flujo.",
            campo="bandejas.n_bandejas"
        ))
    if b.tipo_malla is None:
        advertencias.append(Advertencia(
            codigo="BAND_MALLA_SIN_ESPECIFICAR",
            severidad=Severidad.INFO,
            mensaje="Tipo de malla no especificado. La resistencia de malla afecta la "
                    "caída de presión total.",
            campo="bandejas.tipo_malla"
        ))

    return advertencias


def _validar_flujo(self) -> list[Advertencia]:
    f = self.flujo
    g = self.geometria
    advertencias = []

    # --- Errores duros ---
    if f.caudal_masico_kg_s <= 0:
        raise ValueError("FLUJO_CAUDAL_NO_POSITIVO: caudal_masico_kg_s debe ser positivo.")
    if f.fraccion_recirculacion > 0:
        raise NotImplementedError(
            f"FLUJO_RECIRCULACION_NO_IMPLEMENTADA: fraccion={f.fraccion_recirculacion}. "
            f"No implementado en v0. Usar fraccion_recirculacion=0."
        )
    if f.direccion_flujo not in (DireccionFlujo.HORIZONTAL, DireccionFlujo.VERTICAL_ASCENDENTE):
        raise NotImplementedError(
            f"FLUJO_DIRECCION_NO_SOPORTADA: '{f.direccion_flujo}' no soportada en v0."
        )

    # --- Advertencias ---
    # Velocidad superficial: Q_vol = Q_mas / rho_aire (usar rho=1.1 kg/m³ como estimación)
    rho_aire_est = 1.1  # kg/m³ a ~50°C, 1 atm
    Q_vol = f.caudal_masico_kg_s / rho_aire_est
    v_sup = Q_vol / (g.ancho_m * g.alto_m)
    if v_sup < 0.3:
        advertencias.append(Advertencia(
            codigo="FLUJO_VELOCIDAD_SUPERFICIAL_BAJA",
            severidad=Severidad.WARNING,
            mensaje=f"Velocidad superficial estimada {v_sup:.2f} m/s < 0.3 m/s. "
                    f"El modelo de capa fina puede sobrestimar la tasa de secado.",
            campo="flujo.caudal_masico_kg_s",
            contexto={"v_sup_m_s": v_sup, "Q_vol_m3_s": Q_vol}
        ))
    elif v_sup > 3.0:
        advertencias.append(Advertencia(
            codigo="FLUJO_VELOCIDAD_SUPERFICIAL_ALTA",
            severidad=Severidad.INFO,
            mensaje=f"Velocidad superficial estimada {v_sup:.2f} m/s > 3.0 m/s. "
                    f"Verificar potencia del ventilador.",
            campo="flujo.caudal_masico_kg_s",
            contexto={"v_sup_m_s": v_sup}
        ))
    if f.HR_entrada_fraccion is None:
        advertencias.append(Advertencia(
            codigo="FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA",
            severidad=Severidad.WARNING,
            mensaje="HR entrada no especificada. Se usará fallback escalar del catálogo.",
            campo="flujo.HR_entrada_fraccion"
        ))

    return advertencias


def _validar_producto(self) -> list[Advertencia]:
    p = self.carga_producto
    advertencias = []
    catalogo = p.catalogo_entry  # el bloque del producto leído del YAML

    # --- Errores duros ---
    if p.masa_total_kg <= 0:
        raise ValueError("PROD_MASA_NO_POSITIVA: masa_total_kg debe ser positiva.")
    if p.humedad_inicial_X < 0:
        raise ValueError("PROD_HUMEDAD_INICIAL_NEGATIVA: humedad_inicial_X ≥ 0 requerida.")
    if p.humedad_objetivo_X < 0:
        raise ValueError("PROD_HUMEDAD_OBJETIVO_NEGATIVA: humedad_objetivo_X ≥ 0 requerida.")
    if p.humedad_objetivo_X >= p.humedad_inicial_X:
        raise ValueError(
            f"PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL: objetivo {p.humedad_objetivo_X:.3f} "
            f"≥ inicial {p.humedad_inicial_X:.3f}."
        )

    # Modelo de capa fina
    modelo_cf = p.modelo_capa_fina  # ej: "page", "midilli", "logaritmico"
    cf_entry = catalogo.get("capa_fina", {}).get(modelo_cf, {})
    params_cf = (cf_entry or {}).get("params", None)
    params_vacios = params_cf is None or all(v is None for v in params_cf.values())
    if params_vacios:
        raise ValueError(
            f"MOD_CAPA_FINA_NO_DISPONIBLE: modelo '{modelo_cf}' sin parámetros "
            f"calibrados para '{p.producto_id}'. Cargar en catálogo o seleccionar otro modelo."
        )

    # Modelo de isoterma
    modelo_iso = p.modelo_isoterma  # ej: "gab"
    iso_entry = catalogo.get("isoterma", {}).get(modelo_iso, {})
    params_iso = (iso_entry or {}).get("params", None)
    params_iso_vacios = params_iso is None or all(v is None for v in params_iso.values())
    X_eq_fallback = catalogo.get("propiedades_basicas", {}).get("humedad_equilibrio_aire_seco")
    if params_iso_vacios:
        if X_eq_fallback is not None:
            # Hay fallback escalar → advertencia CRITICAL pero no error duro
            advertencias.append(Advertencia(
                codigo="PROD_ISOTERMA_FALLBACK",
                severidad=Severidad.CRITICAL,
                mensaje=f"Sin isoterma calibrada para '{p.producto_id}'. "
                        f"Usando X_eq_fallback = {X_eq_fallback:.3f} kg/kg ms.",
                campo="carga_producto.modelo_isoterma",
                sugerencia="Cargar parámetros GAB en catálogo para mayor precisión."
            ))
        else:
            raise ValueError(
                f"MOD_ISOTERMA_NO_DISPONIBLE: isoterma '{modelo_iso}' sin parámetros "
                f"para '{p.producto_id}' y sin fallback escalar en catálogo."
            )

    # --- Advertencias ---
    calidad = (cf_entry or {}).get("calidad_datos")
    if calidad in ("BAJA", "ESTIMADA_POR_ANALOGIA"):
        advertencias.append(Advertencia(
            codigo="PROD_CALIDAD_DATOS_BAJA",
            severidad=Severidad.WARNING,
            mensaje=f"Modelo '{modelo_cf}' para '{p.producto_id}' tiene calidad '{calidad}'. "
                    f"Resultados orientativos.",
            campo="carga_producto.modelo_capa_fina"
        ))

    # Humedad objetivo inalcanzable
    X_eq = X_eq_fallback or 0.0  # si no hay fallback, este check es orientativo
    if X_eq > 0 and p.humedad_objetivo_X < X_eq * 0.95:
        advertencias.append(Advertencia(
            codigo="PROD_HUMEDAD_OBJETIVO_INALCANZABLE",
            severidad=Severidad.CRITICAL,
            mensaje=f"Humedad objetivo {p.humedad_objetivo_X:.3f} < X_eq estimado "
                    f"{X_eq:.3f} × 0.95. El secador no alcanzará ese objetivo.",
            campo="carga_producto.humedad_objetivo_X",
            contexto={"X_eq_estimado": X_eq, "X_objetivo": p.humedad_objetivo_X}
        ))

    # Inocuidad — carne sin isoterma
    categoria = catalogo.get("categoria", "")
    if categoria == "CARNE" and params_iso_vacios:
        advertencias.append(Advertencia(
            codigo="INIO_PRODUCTO_CARNE_SIN_ISOTERMA",
            severidad=Severidad.CRITICAL,
            mensaje=f"ALERTA DE INOCUIDAD: '{p.producto_id}' (CARNE) sin isoterma calibrada. "
                    f"No se puede verificar a_w < 0.85.",
            campo="carga_producto.modelo_isoterma",
            sugerencia="Cargar isoterma de carne con nivel de sal equivalente al producto."
        ))

    return advertencias


def _validar_coherencia(self) -> list[Advertencia]:
    g = self.geometria
    b = self.bandejas
    p = self.carga_producto
    advertencias = []

    # --- Errores duros cruzados ---
    alto_requerido = b.n_bandejas * b.separacion_entre_bandejas_m
    if alto_requerido > g.alto_m:
        raise ValueError(
            f"COHE_BANDEJAS_NO_CABEN_EN_CAMARA: {b.n_bandejas} bandejas × "
            f"{b.separacion_entre_bandejas_m:.3f} m = {alto_requerido:.3f} m > "
            f"alto cámara {g.alto_m:.3f} m."
        )
    if b.area_bandeja_m2 > g.largo_m * g.ancho_m:
        raise ValueError(
            f"COHE_AREA_BANDEJA_EXCEDE_CAMARA: área bandeja {b.area_bandeja_m2:.3f} m² > "
            f"área planta {g.largo_m * g.ancho_m:.3f} m²."
        )
    carga_por_m2 = p.masa_total_kg / b.n_bandejas / b.area_bandeja_m2
    if carga_por_m2 > 20.0:
        raise ValueError(
            f"COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA: carga {carga_por_m2:.1f} kg/m²/bandeja "
            f"> 20 kg/m² máximo para capa fina."
        )

    return advertencias
```

---

## 7. Notas de implementación

**Sobre `PROD_T_FUERA_RANGO_CALIBRACION`:** este check requiere T_operacion del colector,
que no está disponible en `Camara.__post_init__`. Moverlo a `Resultados.camara.advertencias_runtime`
cuando se resuelva el colector. En el `__post_init__` se puede hacer un check preliminar si el
usuario especificó una T_operacion_estimada opcional en `ConfiguracionFlujo`.

**Sobre `INIO_A_W_FINAL_INSEGURA`:** es puramente de runtime — depende del resultado numérico
del solver. Va a `Resultados.camara.advertencias_runtime`, no a `Camara.advertencias`.

**Sobre el orden de validación:** se recomienda validar en el orden del `__post_init__` de arriba
(geometría → construcción → bandejas → flujo → producto → coherencia). Los errores duros de
geometría y bandejas deben evaluarse primero porque los checks de coherencia los usan.

**Sobre `rho_aire_est` en la validación de flujo:** 1.1 kg/m³ es una estimación a ~50°C y 1 atm.
Para mayor precisión, el módulo de emplazamiento puede proveer la densidad del aire real
(función de T_ambiente y presión a la altitud del sitio). En v0 la estimación es suficiente
para el check de advertencia.

**Valores umbral — decisiones de diseño:**
- `vol_min = 0.01 m³`: equivale a un secador casero de ~22×22×20 cm. Cualquier cosa menor no
  es un secador funcional.
- `espesor_max_capa_fina = 0.05 m`: estándar de la literatura (Mujumdar 2007).
- `carga_max = 20 kg/m²`: 5 cm de producto a ~400 kg/m³ de densidad aparente. Límite práctico
  superior de capa fina.
- `v_min = 0.3 m/s`, `v_max = 3.0 m/s`: rango de calibración de la mayoría de los modelos
  de capa fina de la literatura.
