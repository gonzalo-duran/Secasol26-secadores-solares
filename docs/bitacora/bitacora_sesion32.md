# Bitácora — Sesión 32 (2026-05-22)

**Tema:** Cuatro mejoras encadenadas sobre el modo CAJA y el manejo físico global del proyecto:

1. **Equinoccios separados** (P1): `DiaAnalisis.EQUINOCCIO` único → dos valores distintos (`EQUINOCCIO_MARZO` 21/3 y `EQUINOCCIO_SEPTIEMBRE` 21/9), con labels que explicitan la estación en hemisferio sur.
2. **"Día real" habilitado en tipología CAJA** (P4): el motor termodinámico ahora acepta forzantes reales (clima NASA + cfg.dia_analisis) en CAJA, sin requerir P3.
3. **Presión atmosférica corregida por altitud** (todo el pipeline): helper híbrido (media anual NASA POWER → ISA → fallback) propagado a cámara, colector, chimenea y motor.
4. **Botón "Calcular chimenea" en P6**: resuelve el lazo natural con condiciones representativas y persiste el resultado para que P7 lo cuente como sección evaluada en el checklist.

**Estado al cierre:** **833 tests + 2 xfailed** (sin cambio numérico respecto a S31 — los cambios fueron de wire-up y nuevos helpers UI, no agregaron lógica testeable adicional). **Sin commits aún** (working tree puro, esperando aprobación explícita).

---

## 126. Equinoccios separados — `EQUINOCCIO_MARZO` y `EQUINOCCIO_SEPTIEMBRE`

### 126.1 Diagnóstico

El usuario notó que en P1, al elegir "modo de análisis diario", el selectbox listaba un único `Equinoccio (21 mar / 21 sep)`. Físicamente son dos días distintos: declinación con signo opuesto, diferente recorrido solar (más relevante en latitudes altas), distinto clima. El label "21 mar / 21 sep" era engañoso además porque la resolución de fecha en `ui/p2_emplazamiento.py:283` y `ui/p3_colector.py:637` mapeaba siempre al **21 de marzo** únicamente.

### 126.2 Decisiones (acordadas con `AskUserQuestion`)

1. **Nombres internos del enum**: por fecha neutra (`EQUINOCCIO_MARZO`, `EQUINOCCIO_SEPTIEMBRE`), no por estación. La estación se explicita sólo en el label de la UI ("Equinoccio de otoño — 21 mar (hem. sur)").
2. **Compat de snapshots viejos**: el usuario eligió "mapear `"EQUINOCCIO"` a 21 mar al cargar", pero el diagnóstico mostró que **no existe loader de `Configuracion`** (`Configuracion` se construye sólo desde la UI; ningún `from_dict` ni `file_uploader` la consume). El JSON de P7 es export-only. Decisión: no agregar código de compat sin consumer; documentado para reabrir si aparece un loader a futuro.

### 126.3 Implementación

- `core/proyecto.py:35`: enum `DiaAnalisis` ahora con `EQUINOCCIO_MARZO` y `EQUINOCCIO_SEPTIEMBRE` (eliminado `EQUINOCCIO` viejo).
- `ui/p1_tipologia.py:66-67`: dos labels separados con explicitación de estación en hem. sur.
- `ui/p2_emplazamiento.py:283-286, 754-761`: rama nueva para 21/9 en `_fecha_dia_analisis` y entrada en el dict `_LABELS_DIA` del subheader "Recurso climático del día de diseño".
- `ui/p3_colector.py:637-640`: rama nueva en `_seleccionar_dia`.

### 126.4 Tests

Sin tests nuevos. Ningún test existente referenciaba el enum `EQUINOCCIO` (solo `test_solar_geometria.py` usa fechas literales 2020-03-21 / 2020-09-23 sin tocar el enum). Suite sigue en 833.

### 126.5 Deuda física observada

El método `_fecha_dia_analisis` (en P2) y `_seleccionar_dia` (en P3) son **casi-duplicados** de la misma lógica. Es código de UI, no de cálculo, así que no rompe la separación de capas, pero al agregar la rama nueva se duplica el if/elif en dos archivos. Refactor a un helper compartido `ui/componentes/dia_analisis.py` queda pendiente como limpieza de código.

---

## 127. "Día real" habilitado en tipología CAJA

### 127.1 Diagnóstico

El usuario navegaba un caso CAJA + diario + cámara con motor termodinámico, y al ir a la sección "Forzantes del aire de entrada" no podía elegir "Día real (clima + colector)" — el botón aparecía deshabilitado con el aviso *"P3 sin calcular"*. Causa: la verificación `_disponibilidad_forzantes_reales` exigía `p3_eval["modo"] == "diario"`, pero en CAJA **no hay P3** (la cámara actúa como colector directo).

### 127.2 Decisión

En CAJA el aire de entrada al lecho es **directamente ambiente** (la cámara es el colector vía techo translúcido). Físicamente:

- T_salida_colector(t) ≡ T_amb(t) — sin colector externo que precaliente.
- ω, viento, I_g(t) salen del clima NASA POWER del día elegido.

Esto es coherente con el manejo del lazo natural por chimenea ya implementado en S30 para CAJA (donde `T_chim_serie = T_amb + 25 K` como heurística cuando no hay colector).

### 127.3 Implementación

`ui/p4_camara.py`:

- **`_disponibilidad_forzantes_reales`** ahora hace branch por tipología:
  - CAJA: basta clima cargado en P2.
  - ARMARIO/GRAN_ESCALA: exige clima **y** `p3_eval` (modo diario).
- **`_construir_forzantes_reales_caja`** (helper nuevo, ~85 líneas): arma `ForzantesAire` desde `proyecto.clima.datos` + `cfg.dia_analisis` directamente, resolviendo la fecha del día con la misma lógica de `_fecha_dia_analisis`/`_seleccionar_dia` (incluyendo los dos equinoccios nuevos). `T_salida_colector_K = T_amb_K.copy()`. POA opcional vía `calcular_POA_horizonte`.
- **`_construir_forzantes_termodinamico`** rutea: si `tipo_forzantes=="real"` y tipología CAJA → `_construir_forzantes_reales_caja`; sino → `_construir_forzantes_reales` (la versión P3-dependiente de siempre).
- **UI**: el radio "Forzantes del aire de entrada" muestra dinámicamente:
  - `"Día real (clima ambiente)"` para CAJA.
  - `"Día real (clima + colector)"` para el resto.
  El `st.info` confirmatorio también se adapta para no decir "T_sal_col(t) del cálculo P3" cuando es CAJA.

### 127.4 Tests

Sin tests nuevos. Helper nuevo es código de UI Streamlit-dependiente; testarlo requeriría mockear `Proyecto` + `Clima` + `Emplazamiento` completos. Queda como deuda menor.

---

## 128. Presión atmosférica corregida por altitud — propagación end-to-end

### 128.1 Diagnóstico

El usuario preguntó si los cálculos del motor termodinámico (presión y presión parcial de vapor) usaban la altitud especificada en P2, o si se asumía 0 msnm. **Diagnóstico exhaustivo (rastreo de `P_Pa`/`P_amb_Pa` en `calculos/`, `core/` y `ui/`)**:

Todos los call-sites de `calcular_camara`, `calcular_tiempo_secado_estatico`, `simular_secado` y `estimar_delta_P_*` usaban **el default 101 325 Pa hardcodeado**. La función `presion_atmosferica(altitud_m)` (ISA troposférica) existía en `motor_calc.py:178` pero sólo se invocaba para cálculos internos del motor eléctrico (no para psicrometría ni para densidad del aire en cámara/colector/chimenea).

Disponibilidad de datos que **no se usaban**:
1. `Emplazamiento.altitud_m` (P2, default 1187 m = Salta).
2. `Clima.altitud_nasa_m` (altitud del punto de grilla NASA POWER).
3. `Clima.datos["presion_Pa"]` — **presión superficial horaria real** descargada de NASA POWER (PS en kPa → Pa).

**Impacto físico**: para Salta (~1187 m), P_ISA ≈ 88 kPa (no 101 kPa). ω_sat ∝ P_sat/(P − P_sat), así que a igual T y HR, **ω_amb real es ~15% más alta** que la calculada con 101 325 Pa. No despreciable en regímenes de HR bajo / cámara caliente. ΔP por Darcy-Weisbach también baja ~13% (ρ menor → menos potencia hidráulica esperada). Tiro térmico de chimenea pierde fuerza motriz proporcionalmente.

### 128.2 Decisiones (acordadas con `AskUserQuestion`)

1. **Fuente de P**: **Híbrido** — media anual NASA POWER si hay clima cargado; ISA con `altitud_m` si no; 101 325 Pa fallback. (Descartado: NASA horaria con variabilidad — mete ruido innecesario en prediseño.)
2. **Alcance inicial**: cámara + colector. (Luego extendido a chimenea + motor en la misma sesión a pedido del usuario.)

### 128.3 Implementación — primera ronda (cámara + colector)

**`calculos/balance_global.py`** — nuevo helper público:

```python
def presion_representativa_proyecto(proyecto) -> tuple[float, str]:
    """Política híbrida. Devuelve (P_Pa, origen_descriptivo)."""
    # 1. Clima cargado con columna 'presion_Pa' → media anual.
    # 2. Emplazamiento.altitud_m → ISA troposférica.
    # 3. Fallback 101325 Pa.
```

Sanity: Salta (1187 m, sin clima cargado) → P = 87.85 kPa (ISA). Con clima NASA POWER cargado, la media anual queda en ese mismo rango (~88 kPa con variabilidad estacional).

**Propagación en `balance_global.py`**:
- `_resolver_aux_cam_const(P_Pa=...)` — nuevo kwarg, se pasa a `calcular_camara`.
- `_correr_colector(P_amb_Pa=...)` — reemplaza el hardcoded 101325 en `_kwargs_comunes`.
- `_correr_colector_horizonte(P_amb_Pa=...)` — se pasa a `_correr_colector` interno.
- `calcular_todo` y `calcular_todo_transitorio` computan `P_proyecto_Pa` **una vez al inicio**, agregan `ADV_PRESION_PROYECTO: <origen>` a `res.advertencias`, y propagan a colector + cámara en single-pass y en lazo Picard.

**`calculos/operacion_anual_camara.py`** (`_calcular_punto_mensual`):
- Reemplazado `P_amb = 101325.0` por `P_amb, _ = presion_representativa_proyecto(proyecto)`.
- `calcular_camara(..., P_Pa=P_amb, ...)` ahora propaga el valor a las 12 simulaciones mensuales.

**`ui/p4_camara.py`**:
- El botón "Calcular" computa `P_proyecto_Pa` una vez (vía el helper), muestra `st.caption("Presión atmosférica usada: …")` con el origen, y propaga a `_construir_forzantes_termodinamico(P_Pa=…)` y a `calcular_camara(P_Pa=…)` (modos termodinámico y capa fina).

### 128.4 Implementación — segunda ronda (chimenea + motor)

**`calculos/balance_global.py`** — extendida la propagación:
- `_caudal_natural_loop(..., P_amb_Pa=P_proyecto_Pa, ...)` desde `calcular_todo` (lazo Picard de chimenea constantes).
- `_caudal_natural_horizonte(..., P_amb_Pa=P_proyecto_Pa, ...)` desde `calcular_todo_transitorio` (Picard sobre horizonte).
- Esto propaga automáticamente a `caudal_natural_kgs` → `delta_P_tiro_Pa`, `delta_P_turbina_motriz_Pa`, `delta_P_chimenea_Pa` (todas usan `densidad_aire(T, P)`), y a `estimar_delta_P_colector` / `estimar_delta_P_camara` que esos helpers ya invocaban internamente con `P_amb_Pa`.

**`ui/p6_motor.py`**:
- `render()` computa `P_proyecto_Pa` al inicio (helper).
- Propagado a 7 callsites:
  - `caudal_masico_a_volumetrico(...)` (sugerencia de Q desde cámara P4).
  - `estimar_delta_P_colector(P_Pa=…)` (auto P3).
  - `estimar_delta_P_camara(P_Pa=…)` (auto P4).
  - `estimar_delta_P_singulares(P_Pa=…)` (dos llamadas: render inicial y recálculo si v_ducto cambia).
  - `delta_P_tiro_Pa(P_amb_Pa=…)` en el preview de tiro térmico (4 columnas con ΔT = 10/20/30/40 K).
  - `delta_P_turbina_motriz_Pa(P_amb_Pa=…)` en el preview del extractor eólico.
- Eliminada constante `_P_ATM_DEFAULT_PA = 101325.0` (quedó sin uso).

### 128.5 No cubierto en esta sesión (deuda física menor)

`core/motor.py:177`: cálculo de `ρ_descarga = 101325/(287.058·323.15)` cuando hay `v_descarga` declarada. Es un término de presión dinámica de salida muy menor (cero salvo que el usuario meta `v_descarga`), y la dataclass `Motor` no recibe P como atributo. Modificarlo requiere ampliar la firma de `Motor` o pasar P en `_calcular`. Queda como deuda futura si surge un caso real en sitio elevado con `v_descarga` no nula.

### 128.6 Tests

Sin tests nuevos. El sanity check manual del helper se hizo con script ad-hoc (Salta 1187 m → 87.85 kPa; sin emplazamiento → 101325 fallback; msnm=0 → 101.33 kPa). Suite sigue verde (833). **Deuda de tests**: `tests/test_calculos/test_balance_global.py::test_presion_representativa_proyecto_*` para cubrir las tres ramas (clima cargado, sin clima con emplazamiento, fallback).

---

## 129. Botón "Calcular chimenea" en P6 — y P7 cuenta chimenea como evaluada

### 129.1 Diagnóstico

El usuario notó que cuando configuraba chimenea en P6 (motor=None), al ir a P7 el checklist "Estado de configuración" mostraba `P6 · Motor ❌`. La chimenea solo se "calculaba" implícitamente dentro de `calcular_todo` (Picard de balance global), pero P6 no tenía botón propio para mostrar números intermedios.

### 129.2 Decisión

Agregar un botón "🌪️ Calcular chimenea" en P6 (sección chimenea, sólo visible cuando motor=None + chimenea ON) que resuelve el lazo natural con **condiciones representativas** (no el Picard completo del balance global) y persiste el resultado en `st.session_state["p6_chimenea_eval"]`. Esto:

1. Le da al usuario números intermedios (ṁ_nat, v_chim, Re, ΔP_tiro, ΔP_ducto, ΔP_resto, ΔP_turbina motriz si extractor activo, H_eff) **antes de ir a P7**.
2. Habilita que el checklist de P7 marque la sección como evaluada.

**Aceptación explícita del usuario** sobre la divergencia preliminar P6 vs Picard completo P7: *"de acuerdo con que los numeros de p6 sean preliminares y en p7 tengamos todo bien resuelto"*. Esta validación queda en feedback persistente.

### 129.3 Implementación

**`ui/p6_motor.py`** — dos helpers nuevos:

- **`_condiciones_representativas_chimenea(proyecto)`** → `(T_amb_K, v_viento_ms, origen_str)`. Si hay clima cargado, devuelve la media anual de `T_amb_K` y `WS_ms` (con string de origen "media anual NASA POWER (P2)"); sino fallback 20 °C / 2 m/s.
- **`_render_calcular_chimenea(proyecto, chimenea)`**:
  - Verifica que `proyecto.camara is not None` (lazo natural necesita caudal y geometría de cámara). Sin cámara → warning + return.
  - Heurística de T_chim: **+25 K** sobre T_amb para CAJA, **+30 K** para ARMARIO/GRAN_ESCALA.
  - Botón "🌪️ Calcular chimenea" llama `_caudal_natural_loop(proyecto, T_amb_K, T_chim_K, m_design_kgs, P_amb_Pa=P_proyecto_Pa, v_viento_ms)` (con presión del helper de S32 §128).
  - Persiste el dict de resultados en `st.session_state["p6_chimenea_eval"]` con los inputs usados.
  - Render: 8 métricas en 2 filas de 4 columnas (caudal natural, v_chim, Re, ΔP_tiro, ΔP_ducto, ΔP_resto, ΔP_turbina si > 0, H_eff). Advertencias del solver en expander. Caption final con inputs y nota de que P7 vuelve a resolver con Picard completo.

**`_render_chimenea_section`** invoca `_render_calcular_chimenea(proyecto, nueva)` después del preview de tiro térmico y antes del bloque "Guardar configuración".

**Limpieza**: cuando el toggle de chimenea se apaga, `st.session_state.pop("p6_chimenea_eval", None)` para no dejar resultados huérfanos.

**`ui/p7_resultados.py`** — checklist actualizado:

```python
motor_o_chim_ok = (proyecto.motor is not None) or (
    proyecto.chimenea is not None
    and st.session_state.get("p6_chimenea_eval") is not None
)
if proyecto.motor is not None:
    label_p6 = "P6 · Motor"
elif proyecto.chimenea is not None:
    label_p6 = "P6 · Chimenea"
else:
    label_p6 = "P6 · Motor / Chimenea"
```

Tres comportamientos posibles del checklist:
- Hay motor → "P6 · Motor ✅" (cuando `proyecto.motor` está seteada — pre-existente).
- Hay chimenea + se corrió "Calcular chimenea" → "P6 · Chimenea ✅".
- Nada de lo anterior → "P6 · Motor / Chimenea ❌".

### 129.4 Limitación documentada

Los números de P6 son **preliminares**: usan `T_chim = T_amb + ΔT_heuristic` constante. En P7 el Picard completo realimenta `T_chim` desde el solver de cámara y `T_sal_col` desde el solver de colector, así que los valores reales pueden diferir 10–30 % de la vista previa. Está explicitado en el caption del bloque de resultados de P6 (*"En P7 se vuelve a resolver con el lazo Picard completo"*).

### 129.5 Tests

Sin tests nuevos (UI-only). Smoke check de imports + suite verde.

---

## 130. Revisión conceptual — día sintético del motor termodinámico

El usuario preguntó si el "día sintético" (modo de forzantes del motor TD) usa temperatura ambiente constante o una función de tiempo. **Diagnóstico** (`construir_serie_sintetica_dia_tipo` en `calculos/balance_global.py:839`):

- **T_salida_colector(h)**: senoidal con amplitud **±15 K** sobre T_op, pico a las 12 h.
- **T_amb(h)**: senoidal con amplitud **±5 K** sobre T_amb_repr, pico a las 12 h (misma fase).
- **I_g(h)**: semicampana seno positiva, pico `I_g_max` (input usuario) a las 12 h, cero entre 18 h y 6 h.
- **ω_amb, v_viento, ṁ_aire_seco**: constantes todo el día.
- Piso de seguridad: `T_sal_col(h) ≥ T_amb(h)` (sin radiación el colector no enfría el aire).

Decisión: documentar el comportamiento, no cambiar nada por ahora. Las amplitudes 15/5 K son fijas en código; parametrizarlas desde la UI queda como deuda menor si el usuario lo necesita más adelante.

---

## Conteo final

- Tests: **833 + 2 xfailed** (sin cambio respecto a S31).
- Archivos modificados: 7 (`core/proyecto.py`, `calculos/balance_global.py`, `calculos/operacion_anual_camara.py`, `ui/p1_tipologia.py`, `ui/p2_emplazamiento.py`, `ui/p3_colector.py`, `ui/p4_camara.py`, `ui/p6_motor.py`, `ui/p7_resultados.py`).
- Archivos nuevos: 0 (todo wire-up + helpers UI dentro de archivos existentes).
- Líneas netas estimadas: +280 / −40 (no commiteado).
- Commits: **0** (working tree puro al cierre — sin push pedido por el usuario aún).

## Deudas físicas y de tests post-S32

- **Tests del helper `presion_representativa_proyecto`**: tres ramas a cubrir (clima cargado, ISA, fallback). En `tests/test_calculos/test_balance_global.py`.
- **`core/motor.py:177` `ρ_descarga` hardcoded** a 101325 Pa cuando hay `v_descarga`. Requiere ampliar firma de `Motor` para pasar P. Caso real: motor en sitio elevado con `v_descarga` no nula.
- **`_caudal_natural_loop` sin P propagada cuando se llama desde tests directos**: el default sigue siendo 101325; los callers del balance global ya lo pasan, pero un test directo del módulo `chimenea_calc` no usa P del proyecto.
- **Refactor `_fecha_dia_analisis` ↔ `_seleccionar_dia`**: duplicación entre `p2_emplazamiento.py` y `p3_colector.py` (y ahora también una tercera copia en `_construir_forzantes_reales_caja` de `p4_camara.py`). Extraer a `ui/componentes/dia_analisis.py`.
- **Amplitudes ±15/±5 K del día sintético**: hardcoded; parametrizar si surge necesidad.
- **Auxiliar mensual y CAJA anual** (heredado S31c): el orquestador anual sigue rechazando CAJA, y `E_aux_batch_MJ = 0` en todos los meses. La extensión natural a CAJA está habilitada parcialmente por §127 (forzantes reales sin colector funcionan), pero el orquestador `calcular_operacion_anual_camara` mantiene el guard `ANUAL_REQUIERE_COLECTOR`. Se podría reabrir con el modelo "POA sobre techo translúcido + balance interno" cuando se priorice.
- **`disponible_nocturno` en modo Constantes** (heredado): se ignora.
- **Quemador de biomasa con física diferenciada** (heredado): hoy termodinámicamente equivalente a resistencia eléctrica.
- **Hoja de ruta a 1.0 restante**: modo industrial (`Tipologia.GRAN_ESCALA`) — único de los tres tópicos originales sin cerrar.

## Validaciones del usuario en esta sesión

- Acepta que P6 chimenea muestre números preliminares (con T_chim heurística) y P7 resuelva con Picard completo — validó explícitamente: *"de acuerdo con que los numeros de p6 sean preliminares y en p7 tengamos todo bien resuelto"*.
- Eligió convención de nombres por fecha neutra (`EQUINOCCIO_MARZO/SEPTIEMBRE`) en el enum, con estación en hem. sur sólo en label de UI.
- Confirmó la política híbrida de presión (media NASA anual → ISA → fallback) y extensión a todo el pipeline (cámara + colector + chimenea + motor).

## Convención de workflow respetada

Toda la sesión se trabajó en working tree puro, sin commits ni push. Suite verde al cierre.
