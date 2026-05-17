# Bitácora — Sesión 25

**Tema:** Corrección de error de unidades en catálogo de manzana (Sacilik 2006), incorporación de constantes de Arrhenius para manzana y durazno, y preparación del script de validación cruzada de motores con yacón.

**Estado al cierre de la sesión:** `frutas.yaml` corregido y extendido (ver §45–§47). Script `validacion_cruzada_yacon.py` generado y pendiente de ejecución con Claude Code (ver §48). Suite de tests: sin cambios respecto a S24 (642 pasan, 1 xfailed) — los cambios de esta sesión son solo en `frutas.yaml`, ningún archivo de `core/` o `calculos/` fue tocado.

---

## 45. Corrección de error de unidades — `frutas.yaml` (manzana, Sacilik 2006)

### Diagnóstico

La bitácora S24 §44 documentó como pendiente verificar `k=0.0761 min⁻¹` en el modelo logarítmico de manzana, que producía `t_secado ≈ 10 min` (físicamente imposible).

Durante la sesión se realizó la verificación cruzando tres fuentes:

1. **Cálculo analítico:** con `k=0.0761 min⁻¹`, el modelo logarítmico `MR = a·exp(-k·t) + c` con `a=1.7506`, `c=-0.7718` predice `MR=0.01` en `t≈11 min`.
2. **Consulta al paper:** Sacilik & Elicin (2006) Figura 2 tiene eje temporal hasta **500 min**; Figura 3 hasta **700 min**. En ambas, `MR→0.01` al final del experimento.
3. **Verificación con k/60:** con `k=0.0761/60 = 0.001268 min⁻¹`, el modelo predice `MR=0.01` en `t≈636 min` — coherente con las figuras del paper.

**Conclusión:** Sacilik 2006 tiene una **inconsistencia interna documentada**: la nomenclatura declara `t` en minutos, pero los coeficientes de la Tabla 2 fueron ajustados con `t` en horas. El catálogo había cargado los valores numéricos de la tabla directamente como `min⁻¹`, error que afectaba a los tres modelos del paper.

### Correcciones aplicadas (÷60 en todos los k de Sacilik 2006)

| Modelo | Parámetro | Valor anterior | Valor corregido | Unidad |
|--------|-----------|---------------|-----------------|--------|
| `logaritmico` | k | 0.0761 | **0.001268** | min⁻¹ |
| `page` | k | 0.1153 | **0.001922** | min⁻ⁿ |
| `midilli` | k | 0.1281 | **0.002135** | min⁻ⁿ |
| `midilli` | b | −0.03897 | **−0.000650** | min⁻¹ |

Cada corrección está documentada en el campo `notas` del modelo correspondiente en `frutas.yaml`, con referencia a esta sesión (S25) y la justificación.

---

## 46. Nuevo bloque `arrhenius` — esquema y criterios

Se incorporó un nuevo campo `arrhenius` a nivel de producto (hermano de `capa_fina` e `isoterma`) con el siguiente esquema:

```yaml
arrhenius:
  modelo_base: page        # modelo de capa fina sobre el que se ajustó k(T)
  k0_s: <float>            # factor pre-exponencial [s⁻¹] — unidad interna del motor
  Ea_J_mol: <float>        # energía de activación [J/mol]
  rango_T_K: [T_min, T_max]
  R2_fit: <float>
  calidad_datos: ALTA | MEDIA | BAJA
  fuente: "<cita + DOI>"
  notas: |
    ...
```

**Convención de unidades:** `k0_s` en **s⁻¹** (unidad interna de `camara_calc_dinamico.py`, que trabaja en segundos). Los comentarios documentan el equivalente en `min⁻¹` para legibilidad. Los valores en notación científica (`1.432e5`) son interpretados como string por PyYAML — se usa notación decimal (`143200.0`) para compatibilidad con `yaml.safe_load`.

**Criterio de calidad:** el fit de Arrhenius se realiza sobre `ln(k) vs 1/T` (regresión lineal). Se acepta en el catálogo solo con R² ≥ 0.99 para calidad ALTA, o con justificación explícita para MEDIA.

---

## 47. Constantes de Arrhenius incorporadas

### Manzana — Doymaz (2010)

- **Fuente:** Doymaz I (2010). Food Bioprod Process 88(2-3):124-132. DOI:10.1016/j.fbp.2009.09.003.
- **Condiciones:** modelo Page, T=50/60/70°C, v=1.5 m/s, espesor 5 mm, variedad Amasya Red.
- **Datos:** k = 0.0162, 0.0302, 0.0522 min⁻ⁿ a 50, 60, 70°C.
- **Fit:** R²=0.9995, Ea=53.95 kJ/mol, k0=143200 s⁻¹.
- **Calidad:** ALTA.

Valores interpolados de referencia:

| T (°C) | k (min⁻ⁿ) |
|--------|----------|
| 40 | 0.0086 |
| 50 | 0.0163 |
| 55 | 0.0221 |
| 60 | 0.0298 |
| 70 | 0.0526 |

### Durazno — Doymaz (2006)

- **Fuente:** Doymaz I (2006). J Food Eng 76(3):561-566. DOI:10.1016/j.jfoodeng.2005.05.052.
- **Condiciones:** modelo Page, T=50/60/70°C, v=0.8 m/s, espesor 4 mm, control (sin tratamiento).
- **Datos:** k = 0.0087, 0.0195, 0.0316 min⁻ⁿ a 50, 60, 70°C.
- **Fit:** R²≈0.997, Ea=59.59 kJ/mol, k0=651300 s⁻¹.
- **Calidad:** MEDIA (solo 3 puntos; `capa_fina` del durazno sigue PENDIENTE).

### Yacón — sin Arrhenius (deliberado)

Los k de Shi 2013 no son monótonos con T: k(15°C) < k(5°C) y k(45°C) < k(35°C). Causa probable: secado por bomba de calor con HR variable entre ensayos — la k absorbió el efecto de la HR, no solo de la T. El fit de Arrhenius sobre todos los puntos da R²≈0.80, inaceptable. El motor dinámico emitirá `PROD_K_CONSTANTE_SIN_ARRHENIUS` usando k=0.217 min⁻¹ (default 25°C) — comportamiento correcto y documentado.

---

## 48. Script de validación cruzada — `validacion_cruzada_yacon.py`

### Motivación

La validación S6 de la bitácora S24 §44 pedía correr yacón en los tres motores y documentar la magnitud de las diferencias. El script fue generado en esta sesión y está listo para ejecutar con Claude Code.

### Diseño del script

El script corre los tres motores con condiciones de contorno idénticas:

| Motor | Módulo | Modelo cinético |
|-------|--------|----------------|
| A — capa fina estático | `calcular_tiempo_secado_estatico` | Page k constante, T fija, GAB para X_eq |
| B — termodinámico TD | `calcular_camara(modo='termodinamico')` | Difusión + aw(X) via GAB, T_prod como estado |
| C — dinámico | `calcular_secado_dinamico` | Page k constante (sin Arrhenius), GAB por paso, forzantes constantes |

**Condiciones de contorno:**

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| T_operacion | 60°C (333.15 K) | Temperatura típica de salida de colector en Salta en verano |
| HR_operacion | 15% | Aire caliente y seco, condición favorable |
| T_ambiente | 25°C | Exterior del secador |
| P_atm | 87000 Pa | Salta (~1187 m snm) |
| ṁ_aire | 0.060 kg/s | Armario estándar de referencia |
| X_0 → X_obj | 9.0 → 0.50 kg/kg ms | X_0 típico yacón; X_obj conservador (secado parcial) |
| masa | 5 kg (fresco) | Carga representativa para armario |
| Horizonte | 96 h | Suficiente para los tres motores |

**Geometría:** armario 1.2×0.8×1.5 m, 5 bandejas×0.50 m², U_muros=0.5 W/m²K.

### Limitaciones conocidas documentadas en el script

1. **Motor C sin Arrhenius:** k=0.217 min⁻¹ fija (T_cal=25°C). Como T_op=60°C >> 25°C, el k real sería mayor → Motor C sobreestima t_secado respecto a lo que daría con Arrhenius.
2. **GAB extrapolada:** calibrada a 50-60°C (Marques 2022); T_op=60°C está en el límite superior del rango.
3. **Shi 2013 fuera de rango:** k calibrado a 5-45°C; T_op=60°C es extrapolación.

### Ejecución pendiente

```bash
# Desde raíz del proyecto:
.venv/bin/python validacion_cruzada_yacon.py
```

El script imprime la tabla comparativa en consola y guarda `validacion_cruzada_yacon.md` con los resultados y los parámetros de entrada. Los resultados numéricos se documentarán en §49 de la próxima sesión una vez ejecutado con Claude Code.

---

## 49. Resultados de la validación cruzada

Script ejecutado en sesión S26 (ver bitácora S26 §51 para el diagnóstico del bug encontrado y el fix aplicado en `camara_calc_dinamico.py` antes de poder cerrar esta tabla).

### Resultados definitivos — yacón, T_op=60 °C, HR=15 %, ṁ=0.060 kg/s, masa=5 kg, X_0=9 → X_obj=0.5

| Motor | t_secado | Δ vs Motor A | Estado |
|---|---|---|---|
| **A — Capa fina estático** | 0.10 h | (referencia) | converge; 4 advertencias |
| **B — Termodinámico TD** | **58.45 h** | +60.395 % | converge; sin advertencias; m_evap=4.250 kg; T_prod_final=34.0 °C |
| **C — Dinámico** | 0.12 h | +24 % | converge tras fix S26 §51; 1 advertencia (`PROD_K_CONSTANTE_SIN_ARRHENIUS`) |

Diferencia C vs B: **−99.8 %**.

### Interpretación física

1. **A y C colapsan al mismo número (~0.1 h).** Con k constante (sin Arrhenius para yacón), forzantes constantes y modelo Page de cinética intensiva, el motor dinámico se reduce esencialmente al algebraico. La pequeña diferencia (+24 %) viene del paso adaptativo de `solve_ivp` vs la inversión `brentq` directa de Motor A.
2. **Solo Motor B captura el cuello de botella del aire.** En 60 °C / 15 % HR / ṁ=0.060 kg/s, el balance de masa muestra que el caudal es insuficiente para arrastrar los 4.25 kg de agua en horas. Motor A *sabe* esto (emite `CAM_RIESGO_SATURACION_AIRE`: ω_salida=0.226 > ω_sat=0.185 kg/kg, y `CAM_HR_SALIDA_ALTA`: 100 %) pero **no corrige el tiempo**. Motor B integra el balance y entrega 58.45 h, que es el orden de magnitud realista para este escenario.
3. **Coherencia interna de B.** La masa evaporada (4.250 kg) coincide exactamente con `m_seco · (X_0 − X_obj) = 0.5 · 8.5 = 4.25 kg` — balance cerrado a la precisión de impresión.
4. **Validación de la advertencia teórica de S23 §29.1** (modelo de capa fina es intensivo) con datos concretos: la magnitud del sesgo en este escenario es ≈600× (B/A).

### Recomendación de uso

- **Motor A** queda como referencia rápida para exploración, no para prediseño en régimen saturado.
- **Motor B (termodinámico)** es el motor de prediseño confiable para condiciones donde el aire puede saturarse.
- **Motor C (dinámico)** sólo aporta valor sobre A cuando hay forzantes variables (perfiles horarios día/noche, ṁ variable por viento) o cuando el producto tiene Arrhenius (k(T) no constante). Para yacón, mientras Shi 2013 no entregue k(T) monótono, C aporta lo mismo que A en condiciones constantes.

Los archivos `validacion_cruzada_yacon.md` y `probe_motor_C_yacon.py` quedan en la raíz como evidencia ejecutable.

---

## 50. Pendiente para siguientes sesiones

- **Completar §49** con resultados numéricos del script de validación cruzada.
- **Lector de Arrhenius en el catálogo:** el motor dinámico necesita un lector que extraiga `arrhenius.k0_s` y `arrhenius.Ea_J_mol` del catálogo y los pase como `k0_arrhenius` y `Ea_J_mol` a `calcular_secado_dinamico()`. Hoy ese wire-up no existe — el campo está en el YAML pero no se lee.
- **Poblar `capa_fina` del durazno:** con coeficientes de Doymaz 2006 (Page, T=50/60/70°C), que ya tenemos para el Arrhenius pero no para los params de capa fina.
- **Isoterma GAB de manzana:** Kaymak-Ertekin & Gedik (2004) sigue pendiente.
- **`t_max_s` configurable desde UI** (hoy hardcodeado a 72 h).
- **Commit y push** de todo el trabajo de S23 + S24 + S25.
- **Repo GitHub público.**
