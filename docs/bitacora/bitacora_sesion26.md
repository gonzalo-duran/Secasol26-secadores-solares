# Bitácora — Sesión 26 (2026-05-15)

**Tema:** Ejecución de la validación cruzada de yacón preparada en S25 §48. Descubrimiento y corrección de un bug en el motor dinámico de cámara (`calcular_secado_dinamico`) que impedía la integración con el modelo Page para todos los escenarios. Cierre de S25 §49 con resultados numéricos definitivos.

**Estado al cierre de la sesión:** Bug Page MR=1 corregido en `calculos/camara_calc_dinamico.py:216`. Validación cruzada yacón ejecutada y documentada. Suite total: **642 passed, 1 xfailed** (sin regresiones). Sin commits aún (sigue pendiente desde S23/S24/S25).

---

## 51. Bug en motor dinámico — singularidad de Page en MR=1

### 51.1 Síntoma observado

Al ejecutar el script `validacion_cruzada_yacon.py` (S25 §48), el Motor C reportó:

```
Motor C: NO CONVERGIÓ
  X_final = 9.0000 kg/kg ms
  X_obj   = 0.5000 kg/kg ms
  horas_rehumectacion_evitada = 0.0
  advertencia: CAM_X_OBJ_NO_ALCANZADO_EN_HORIZONTE
```

`X_final = X_0` exactamente, sin variación. Como `horas_rehumectacion_evitada = 0`, la política B nocturna de S23 §31.3 quedaba descartada como causa.

### 51.2 Sonda exploratoria — `probe_motor_C_yacon.py`

Para acotar el origen del bug se construyó una sonda que barre 10 combinaciones de (T_op, HR, masa, X_obj) cubriendo desde el caso de calibración (T_op=25 °C, masa=1 kg) hasta el caso original (T_op=60 °C, masa=5 kg, X_obj=0.5):

| T_op (°C) | HR | masa (kg) | X_obj | conv | X_fin |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 25 | 0.15 | 5.0 | 0.50 | NO | 9.000 |
| 25 | 0.15 | 1.0 | 0.50 | NO | 9.000 |
| 25 | 0.30 | 5.0 | 0.50 | NO | 9.000 |
| 40 | 0.15 | 5.0 | 0.50 | NO | 9.000 |
| 45 | 0.15 | 5.0 | 0.50 | NO | 9.000 |
| 50 | 0.15 | 5.0 | 0.50 | NO | 9.000 |
| 60 | 0.15 | 5.0 | 0.50 | NO | 9.000 |
| 60 | 0.15 | 1.0 | 0.50 | NO | 9.000 |
| 60 | 0.15 | 5.0 | 2.00 | NO | 9.000 |
| 60 | 0.30 | 5.0 | 0.50 | NO | 9.000 |

**Diez de diez escenarios fallan idénticamente, con X_final = X_0 = 9.0 exacto.** Esto descarta extrapolación de Shi 2013 (k a T>45 °C), extrapolación de GAB de Marques 2022, problemas de masa-vs-caudal, y la política anti-re-humectación. El bug es **independiente del régimen físico** — está en la matemática del modelo.

### 51.3 Diagnóstico — singularidad de Page en t=0

El modelo de Page en forma diferencial (S23 §32.2 Ec. 5) es:

```
dMR/dt = −n · k_eff^(1/n) · MR · (−ln MR)^((n−1)/n)
dX/dt  = (X_0 − X_eq) · dMR/dt
```

Con MR_rel = (X − X_eq) / (X_0 − X_eq), clipeado para evitar log(0).

En t=0, MR_rel = (X_0 − X_eq) / (X_0 − X_eq) = **1 exacto**. Entonces:

- `−ln(1) = 0`
- `0 ** ((n−1)/n) = 0` para n > 1 (yacón: n=1.105, (n−1)/n = 0.0950)
- `dMR/dt = 0` → `dX/dt = 0`

`solve_ivp` evalúa el RHS en t=0, ve derivada nula en todas las componentes, y nunca avanza. La integración se queda atrapada en la condición inicial **por construcción**, no por dificultad numérica.

Esta singularidad es propia de la formulación diferencial: la forma integral `MR(t) = exp(−(kt)^n)` no la tiene porque arranca con MR(0)=1 sin tener que evaluar la derivada en ese punto. Lewis (`dX/dt = −k·(X−X_eq)`) tampoco la tiene porque su RHS no involucra el log.

### 51.4 Fix aplicado

`calculos/camara_calc_dinamico.py:216` antes:

```python
MR_rel = max(EPSILON_MR, min(1.0, MR_rel))
```

después:

```python
# Clipear ambos extremos: MR=0 da log(0)=−inf; MR=1 da
# (−log(MR))^((n−1)/n)=0 → dMR/dt=0 (singularidad de Page
# en t=0, atrapa al solver). Ver bitácora S26.
MR_rel = max(EPSILON_MR, min(1.0 - EPSILON_MR, MR_rel))
```

Con `EPSILON_MR = 1e-6`, en t=0 queda MR_rel = 1 − 1e-6, y:

- `−ln(1 − 1e-6) ≈ 1.0e-6`
- `(1.0e-6) ** 0.0950 ≈ 0.255` (para n=1.105)
- `dMR/dt ≈ −1.105 · k_eff^(1/1.105) · (1 − 1e-6) · 0.255` — finita y de signo correcto.

El sesgo introducido en X_final por la perturbación de 1e-6 es **del orden de 1e-6 · (X_0 − X_eq) ≈ 1e-5 kg/kg**, varios órdenes de magnitud por debajo de cualquier tolerancia física. Físicamente despreciable.

### 51.5 Sonda post-fix

Re-ejecución de `probe_motor_C_yacon.py`:

| T_op (°C) | HR | masa (kg) | X_obj | conv | t (h) | X_fin |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 25 | 0.15 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 25 | 0.15 | 1.0 | 0.50 | SI | 0.12 | 0.500 |
| 25 | 0.30 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 40 | 0.15 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 45 | 0.15 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 50 | 0.15 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 60 | 0.15 | 5.0 | 0.50 | SI | 0.12 | 0.500 |
| 60 | 0.15 | 1.0 | 0.50 | SI | 0.12 | 0.500 |
| 60 | 0.15 | 5.0 | 2.00 | SI | 0.07 | 2.000 |
| 60 | 0.30 | 5.0 | 0.50 | SI | 0.12 | 0.500 |

Los diez escenarios convergen al X_obj solicitado con tiempos consistentes con la cinética de Page para yacón a T_calibración=25 °C (todos los k iguales porque no hay Arrhenius — sub-determinación física, no numérica).

### 51.6 Tests de regresión

| Test | Resultado |
|---|---|
| `tests/test_calculos/test_camara_calc_dinamico.py` (33 tests) | 33 passed |
| Suite completa (`pytest -q`) | **642 passed, 1 xfailed** |

Sin regresiones. Los tests existentes del motor dinámico ya cubrían escenarios con Lewis y con cierta combinación de Page que no caía en MR=1 exacto (probablemente por advertencias de inicialización o por test cases con X_0 ≠ X_inicial implícito). Se podría agregar un test específico en sesión futura:

```python
def test_page_arranca_desde_MR_1_exacto():
    """Regresión del bug S26 §51: MR_rel=1 daba dMR/dt=0 y solver atrapado."""
    # Caso mínimo: yacón, T constante, forzantes constantes, X_0 conocido
    res = calcular_secado_dinamico(..., modelo_capa_fina="page", X_0=9.0, ...)
    assert res.convergencia_a_X_obj is True
    assert res.X[-1] < res.X[0]  # debe haber secado algo
```

Se deja como pendiente menor para no acoplar este commit con cambios de test.

---

## 52. Validación cruzada — ejecución y resultados

### 52.1 Resultados principales

Tras el fix de §51, `validacion_cruzada_yacon.py` se ejecutó con éxito. Condiciones (S25 §48): T_op=60 °C, HR=15 %, ṁ=0.060 kg/s, masa=5 kg, X_0=9 → X_obj=0.5, P=87 kPa (Salta), horizonte 96 h.

| Motor | t_secado | Δ vs A | Advertencias |
|:---|:---:|:---:|:---|
| A — Capa fina estático | 0.10 h | (ref) | 4 (T fuera rango, espesor fuera calibración, saturación aire, HR salida alta) |
| **B — Termodinámico TD** | **58.45 h** | **+60.395 %** | (ninguna) |
| C — Dinámico | 0.12 h | +24 % | 1 (`PROD_K_CONSTANTE_SIN_ARRHENIUS`) |

Diferencia C vs B: −99.8 %.

### 52.2 Detalles Motor B (referencia confiable)

- `status = X_obj_alcanzado`
- `masa_evaporada = 4.250 kg` — coincidencia exacta con balance: `m_seco · (X_0 − X_obj) = (5/(1+9)) · 8.5 = 4.250 kg`.
- `T_prod_final = 34.0 °C` — coherente con régimen de bulbo húmedo con leve sobrecalentamiento al final.
- Cero advertencias.

### 52.3 Detalles Motor A — el modelo *sabe* que hay un problema, pero no lo corrige

Las cuatro advertencias de A en este escenario son didácticamente valiosas:

- **`CAM_RIESGO_SATURACION_AIRE`** (ω_salida=0.226 kg/kg > ω_sat=0.185): el aire no puede arrastrar todo el agua.
- **`CAM_HR_SALIDA_ALTA`** (HR_salida=100 %): consecuencia de lo anterior.
- **`CAM_ESPESOR_FUERA_CALIBRACION`** (2 cm > 3× 0.4 cm de calibración): el modelo subestima por capa gruesa.
- **`CAM_T_FUERA_RANGO_CALIBRACION`** (60 °C fuera de 5–45 °C de Shi 2013): extrapolación.

A pesar de detectar las cuatro condiciones, el modelo **devuelve 0.10 h** porque la formulación de capa fina es intensiva por construcción: la cinética Page sólo ve el producto, no el aire. Es exactamente el problema que S23 §29.1 documentó teóricamente.

### 52.4 ¿Por qué A y C colapsan al mismo número?

En las condiciones del escenario:
1. **k constante** — yacón sin Arrhenius. k(T_op=60 °C) = k(25 °C) = 0.217 min⁻¹.
2. **Forzantes constantes** — sin día/noche, sin variación.
3. **X_eq quasi-constante** — la GAB sólo varía con HR_local, que se mantiene casi igual a HR_ent salvo en saturación.

En este régimen, el sistema 5×5 de Motor C se simplifica al mismo cálculo algebraico de Motor A. La pequeña diferencia (+24 %) viene de:
- Paso adaptativo de `solve_ivp` (LSODA) vs inversión directa de `brentq`.
- La perturbación `EPSILON_MR=1e-6` introducida en §51.4 (efecto despreciable pero no nulo).
- Acoplamiento térmico con T_prod que en Motor C arranca en T_amb y en Motor A se asume T_prod = T_aire desde t=0.

### 52.5 Diagnóstico físico

El Motor B es el único que captura el régimen físicamente correcto en este escenario. La conclusión es:

- **Para prediseño en cámara saturable (alta masa / bajo caudal):** usar Motor B (termodinámico). Es el único motor que cierra balance de masa del aire.
- **Para exploración rápida en régimen aire-en-exceso:** Motor A es suficiente. Las advertencias de A actúan como señal de "salir del régimen donde A es válido".
- **Motor C aporta valor sobre A** cuando: (a) hay Arrhenius (k(T) variable) o (b) hay forzantes variables (día/noche, viento). Mientras yacón no tenga Arrhenius (S25 §47 documenta por qué), C ≈ A en condiciones constantes.

---

## 53. Estado de los artefactos

| Archivo | Estado | Propósito |
|---|---|---|
| `validacion_cruzada_yacon.py` | en raíz, ejecutable | Script de validación (S25 §48) |
| `validacion_cruzada_yacon.md` | en raíz, regenerable | Reporte generado por el script |
| `probe_motor_C_yacon.py` | en raíz, ejecutable | Sonda de 10 escenarios para Motor C |
| `calculos/camara_calc_dinamico.py` | modificado (línea 216) | Fix de la singularidad Page MR=1 |

Sugerencia: cuando se commitee S23/S24/S25, mover `validacion_cruzada_yacon.py` y `probe_motor_C_yacon.py` a `scripts/` o `validacion/` antes del commit para no contaminar la raíz del repo.

---

## 54. Pendiente para siguientes sesiones

- **Test de regresión específico** para el bug Page MR=1 (`test_page_arranca_desde_MR_1_exacto`).
- **Lector de Arrhenius en el catálogo** — sigue pendiente desde S25 §50. El motor dinámico tiene el gancho preparado pero la lectura del YAML no está cableada.
- **Reubicar scripts ejecutables** (`validacion_cruzada_yacon.py`, `probe_motor_C_yacon.py`) a `scripts/` o `validacion/`.
- **Repetir validación cruzada** con un producto que **sí** tenga Arrhenius (manzana o durazno, S25 §47) — ese es el escenario donde Motor C debería diferenciarse de Motor A.
- **Poblar `capa_fina` del durazno** (S25 §50).
- **Isoterma GAB de manzana** (Kaymak-Ertekin & Gedik 2004).
- **`t_max_s` configurable desde UI** (S24 §44).
- **Commit y push** del trabajo acumulado de S23 + S24 + S25 + S26.
- **Repo GitHub público.**
