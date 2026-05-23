# Bitácora — Sesión 31 (2026-05-20/21)

**Tema:** Tres features grandes pedidas por el usuario en cascada, todas ligadas a deudas físicas de la hoja de ruta a 1.0 (ΔP en bandejas, modo ANUAL de cámara) más un refactor estructural del extractor eólico que la conversación destapó como mejor opción de modelado:

1. **K_rugosidad por bandeja con producto en cross-flow** (cierra "ΔP en bandejas" de la hoja de ruta).
2. **Extractor eólico migrado de tipo de motor a accesorio de chimenea** (refactor coherente con el modelo físico — turbina sombrero chino genera depresión motriz en la base de la chimenea, no es un accionamiento independiente).
3. **Operación anual de cámara con cascada A + B** (Augustus Leon analítica + motor TD por día típico mensual; cierra "modo ANUAL de cámara" de la hoja de ruta).

Además: dos revisiones puramente conceptuales pedidas por el usuario (toggle `disponible_nocturno` del auxiliar y mapeo del quemador de biomasa) que no derivaron en cambios de código pero quedaron documentadas en la conversación.

**Estado al cierre:** **833 tests + 2 xfailed** (vs 774 + 2 al cierre de S30, +59 netos). **Tres commits pusheados a origin/main** (`1daf636` + `dced34b` + `301c4ac`). De la hoja de ruta a 1.0, **dos de los tres tópicos quedaron cerrados** (ΔP bandejas y modo ANUAL de cámara); falta el modo industrial (`Tipologia.GRAN_ESCALA`).

---

## 121. K_rugosidad en bandejas con producto

### 121.1 Diagnóstico físico

El usuario notó que el modelo de `estimar_delta_P_camara` no captura adecuadamente la pérdida de carga del aire pasando por encima de un lecho de producto rugoso en flujo HORIZONTAL. La causa: Darcy-Weisbach con `f = 64/Re` (laminar) o `f = 0.316·Re^(-0.25)` (Blasius) trata la superficie como pared lisa, ignorando que las partículas del producto sobresalen y generan estelas/separaciones de capa límite.

Se discutieron tres aproximaciones:

1. **Rugosidad distribuida**: ε_rel = d_p/Dh en Haaland. Defendible físicamente pero extrapola Moody fuera del rango Nikuradse (ε_rel típica 0.05–0.5 para producto en canal de 3–8 cm).
2. **Pérdida de forma concentrada**: K·ρv²/2 una vez por bandeja, con K función de d_p/espacio_libre. Más empírica pero encaja con la arquitectura del módulo (mismo patrón que K_malla).
3. **Combinación de las dos**.

**Decisión:** opción (2) sola, con tabla de anclajes interpolada linealmente:

| ratio d_p/espacio_libre | K propuesto |
|---|---|
| < 0.05 | 0.2 |
| 0.05–0.15 | 0.2 → 0.5 |
| 0.15–0.30 | 0.5 → 1.0 |
| 0.30–0.50 | 1.0 → 2.0 |
| > 0.50 | 2.0 (cap) |

Sin correlación específica de literatura para "cross-flow sobre lecho rugoso de secador"; tabla inspirada en Idelchik / Crane TP-410 para bancos de obstáculos y rugosidades altas.

En **VERTICAL_ASCENDENTE** la ecuación de Ergun ya captura la rugosidad del producto vía Φ_s y d_p; lo único que faltaba era una pérdida de transición fija `K_TRANSICION_LECHO = 1.5` (contracción 0.5 al entrar + expansión Borda-Carnot 1.0 al salir), aplicada por bandeja sobre ρv₀²/2.

### 121.2 Implementación

- `core/camara.py`: campo `K_rugosidad_producto: Optional[float] = None` en `ConfiguracionBandejas`. Default None ⇒ autocalcular; usuario puede forzar override. Validación `BAND_K_RUGOSIDAD_INVALIDO` si negativo.
- `calculos/motor_calc.py`:
  - Constantes `K_TRANSICION_LECHO = 1.5` y tabla `_K_RUGOSIDAD_TABLA`.
  - Helper `_K_rugosidad_default(d_p, espacio_libre)` con interpolación lineal por tramos.
  - Modificación de `estimar_delta_P_camara`:
    - HORIZONTAL: `+ K_rug · ρ·v_canal²/2 · n_bandejas` (una vez por bandeja, no por canal).
    - VERTICAL: `+ K_TRANSICION_LECHO · ρ·v₀²/2 · n_bandejas`.
- `ui/p4_camara.py`: checkbox "Forzar K rugosidad" + number_input cuando activo; sino caption con el K auto calculado, d_p y ratio. Help tooltip con la física completa.
- Serialización en `from_dict`/`to_dict` para snapshots .json.

### 121.3 Tests

Archivo `tests/test_calculos/test_motor_fase2.py` extendido con +10 tests:
- 5 del helper `_K_rugosidad_default` (saturación en extremos, punto tabulado exacto, interpolación lineal, degenerados).
- 5 de integración en `estimar_delta_P_camara` (HORIZONTAL con K_rug > 0 vs K=0, auto vs override, VERTICAL con término de transición, validación de error negativo).

**Resultado:** 22 tests en el archivo, 0 regresiones. Suite global pasa de 774 a 784.

---

## 122. Extractor eólico — migrado de motor a accesorio de chimenea

### 122.1 Diagnóstico

El usuario preguntó si "incorporamos extractor eólico a la chimenea solar". El código tenía `TipoAccionamiento.EXTRACTOR_EOLICO` como un tipo de motor (alternativa a `MOTOR_ELECTRICO`), con campos `diametro_extractor_m` y `velocidad_viento_diseno_m_s`. UI en P6 (selectbox de tipo motor). Pero el comentario `"En v0 el caudal del extractor no se calcula automáticamente"` confirmó que era un stub: guardaba parámetros pero no resolvía la curva turbina ↔ ΔP del sistema. Además, **conceptualmente**: una turbina sombrero chino genera depresión en la base de un conducto vertical, no es un accionamiento independiente. Pertenece al lado motriz natural (chimenea), no al forzado (motor).

Se discutió la física del balance ampliado:

$$\Delta P_{\text{térmico}} + \Delta P_{\text{turbina}}(v_{\text{viento}}) = \Delta P_{\text{resistivo}} + \Delta P_{K,\text{turbina}}(v_{\text{flujo}})$$

Con dos términos nuevos a sumar al lazo Picard:

- **Motriz**: `Cp · ρ_amb · v_viento² / 2`, con Cp ≈ 0.3–0.6 (sin correlación específica; default 0.4).
- **Resistivo**: `Kt · ρ_chim · v_extractor² / 2`, con Kt ≈ 1.0 (cubre expansión + obstrucción de álabes).

Más una **corrección logarítmica del viento NASA POWER** (medido a 10 m) a la altura del tope de la chimenea:

$$v(z) = v(10) \cdot \frac{\ln(z/z_0)}{\ln(10/z_0)}$$

con z₀ rugosidad del terreno (0.001 mar/lago, 0.03 campo abierto, 0.05 rural medio default, 0.20 suburbano, 0.50 urbano denso).

**Casos límite cubiertos**:
- v_viento = 0 + sol fuerte: turbina solo agrega resistencia → caudal *menor* que chimenea desnuda (caso contraintuitivo que el modelo ahora captura).
- Sin sol + viento alto: ΔP_térmico ≈ 0, ΔP_turbina motriz mueve el aire.
- Sol + viento: efectos se suman.

### 122.2 Decisiones de diseño (acordadas con `AskUserQuestion`)

1. **Migración de snapshots .json viejos**: con aviso visible (`st.warning`), convirtiendo automáticamente `tipo_accionamiento: EXTRACTOR_EOLICO` a `motor=None` + `chimenea con extractor activo` (preservando diámetro original, defaults para Cp/Kt/z0).
2. **Parametrización UI**: parámetros libres con defaults (no catálogo de turbinas comerciales).
3. **Independencia**: el extractor *requiere* chimenea presente (no es montable sobre techo de cámara directamente).
4. **Perfil de viento logarítmico**: incluido desde el arranque (default z₀=0.05, override por tipo de terreno).

### 122.3 Implementación

- `core/motor.py`: eliminado `EXTRACTOR_EOLICO` del enum `TipoAccionamiento` (queda con MOTOR_ELECTRICO y CONVECCION_NATURAL). Eliminados campos `diametro_extractor_m`, `velocidad_viento_diseno_m_s` y advertencias asociadas (`MOT_EXTRACTOR_SIN_DIAMETRO`, `MOT_EXTRACTOR_VIENTO_BAJO`).
- `core/chimenea.py`: agregados `extractor_activo: bool`, `diametro_extractor_m`, `Cp_turbina`, `Kt_turbina`, `z0_terreno_m` con validaciones `CHIM_EXTRACTOR_SIN_DIAMETRO`, `CHIM_CP_TURBINA_INVALIDO`, `CHIM_KT_TURBINA_INVALIDO`, `CHIM_Z0_INVALIDO`. Advertencia `CHIM_EXTRACTOR_DIAMETRO_PEQUENO` si d_ext < d_chim (estrangulamiento).
- `calculos/chimenea_calc.py`:
  - Helper `_v_viento_a_altura(v_10m, z, z0)` con perfil logarítmico.
  - Función `delta_P_turbina_motriz_Pa(v_viento_local, Cp, T_amb, P)`.
  - `delta_P_chimenea_Pa` extendida con parámetros opcionales `Kt_turbina` y `diametro_extractor_m`.
  - `caudal_natural_kgs` extendida con `extractor_activo`, `Cp_turbina`, `Kt_turbina`, `diametro_extractor_m`, `z0_terreno_m`, `v_viento_10m_ms`. Devuelve nuevas claves `delta_P_turbina_motriz_Pa` y `v_viento_local_ms`.
- `calculos/balance_global.py`: `_caudal_natural_loop` (modo Constantes) y `_caudal_natural_horizonte` (Transitorio) propagan `v_viento_ms` y los parámetros del extractor al brentq del lazo Picard.
- `ui/p6_motor.py`:
  - Sección motor: eliminado selectbox "Extractor eólico", eliminada sección de parámetros del extractor, limpiada serialización (`from_dict` ya no lee bloque `eolico`).
  - Sección chimenea (visible cuando `motor=None`): checkbox "Agregar extractor eólico en el tope" + expander con número D_ext, Cp, Kt, selectbox de terreno (z₀). Help tooltip con física completa. Preview en vivo del viento corregido + ΔP motriz cuando hay datos de clima en P2.
  - **Migración con aviso**: `_from_json_motor` devuelve ahora `tuple[Motor|None, Chimenea|None, str|None]`. Si JSON viejo trae `tipo_accionamiento=EXTRACTOR_EOLICO`, construye una `Chimenea` migrada con extractor activo, devuelve `(None, chim, mensaje_aviso)`. Callsite muestra `st.warning` con el aviso.
- Tests:
  - Nuevos: 22 tests en `tests/test_calculos/test_chimenea_calc.py` (6 perfil log de viento, 4 motriz turbina, 6 caudal con extractor en casos límite v=0/sol=0/suma, 6 validaciones de la dataclass).
  - Eliminados: 4 tests obsoletos de `MOT_EXTRACTOR_SIN_DIAMETRO` y `MOT_EXTRACTOR_VIENTO_BAJO` en `tests/test_core/test_motor.py`.

**Resultado:** Suite global pasa de 784 a 803 (+19 netos). Sin regresiones.

---

## 123. Operación anual de cámara — cascada A + B (Augustus Leon)

### 123.1 Punto de partida

El usuario corría modo ANUAL en P1 pero al llegar a P4 y P7 veía solo cálculos de "día sintético" — el modo anual estaba presente en core (enum `ModoAnalisis.ANUAL`) y en clima (descarga 8760 h NASA POWER), pero **no había wire-up de cámara anual**. El motor termodinámico solo corría batches puntuales de 1–3 días.

Se discutió por qué no era trivial:

- **Secado solar es batch discreto**, no continuo. A diferencia de ACS/calefacción (f-chart Duffie-Beckman) o PV (∫POA·η), no hay método estándar único para "rendimiento mensual de secador" — el batch es la unidad natural.
- **Existen tres familias de aproximaciones en literatura**:
  1. Eficiencias agregadas (Bala 2005, **Augustus Leon-Kumar-Bhattacharya 2002** "A comprehensive procedure for performance evaluation of solar food dryers", RSER 6(4):367-393).
  2. Simulación batch-by-batch sobre 8760 h (Karim & Hawlader 2004, Ekechukwu & Norton 1999).
  3. Día típico mensual + ratio de utilización (Forson et al. 2007, Janjai et al.).

### 123.2 Decisión

Cascada **A + B** acordada con el usuario:
- **A (analítica)**: modelo lineal del colector `T_sal = T_amb + η_col·POA·A/(ṁ·cp)` para alimentar forzantes mensuales sin re-correr el solver del colector cada mes.
- **B (termodinámica)**: motor TD corre con día típico del mes (promedio horario NASA POWER) sobre horizonte de 3 días por defecto.

Decisiones cerradas con `AskUserQuestion`:
- **Eficiencias mostradas**: las 4 de Augustus Leon completas (η_drying, η_pickup, η_térmica, η_total).
- **Batches/mes**: configurable por slider en P4 (1–30).
- **Ubicación UI**: resumen en P4 + detalle en P7.

### 123.3 Implementación

**Modelo de datos** (`core/camara.py`):
- `OperacionAnualConfig` (`batches_por_mes` default 10, `I_g_diaria_minima_MJ_m2` default 8, `horizonte_horas_batch` default 72). Validaciones `ANUAL_BATCHES_FUERA_RANGO`, `ANUAL_HORIZONTE_FUERA_RANGO`, `ANUAL_I_G_MINIMA_NEGATIVA`.
- Atributo opcional `Camara.operacion_anual: Optional[OperacionAnualConfig] = None`.

**Cálculo** (módulos nuevos):
- `calculos/eficiencias_camara.py`:
  - `calor_latente_agua_J_kg(T_K)` correlación lineal 2.501e6 − 2.386e3·(T−273.15).
  - Las 4 eficiencias Augustus Leon como funciones puras que reciben primitivas (J, kg, m²) — usables tanto desde simulaciones como desde balances analíticos.
- `calculos/operacion_anual_camara.py`:
  - Dataclasses `PuntoMensualCamara` (1 batch representativo del mes) y `ResultadosAnualCamara` (12 puntos + agregados anuales).
  - `_T_salida_colector_lineal` (modelo A).
  - `_calcular_punto_mensual` que para cada mes: día tipo mensual → POA → T_sal_col lineal → forzantes multi-día → **delega a `calcular_camara` (dispatcher)** para correr motor TD → calcula las 4 eficiencias.
  - `calcular_operacion_anual_camara` orquestador que itera 12 meses, captura excepciones por mes, agrega ponderado por kg/mes.
- `calculos/clima_calc.py`: helper nuevo `dia_tipo_mensual(datos_clima, mes, tz_local)` — promedia cada hora del día sobre todos los registros del mes; devuelve DataFrame de 24 filas con DatetimeIndex sintético del día 15 del mes para que `calcular_POA_horizonte` funcione.

**UI** (`ui/p4_camara.py` y `ui/p7_resultados.py`):

Versión inicial: sección anual aparecía **al final** del cálculo del batch puntual termodinámico (dentro de `if isinstance(res, ResultadoMotorTermodinamico):`). El usuario detectó el problema al correr el caso anual: "veo todavía corridas en base a día sintético". Diagnóstico: la sección estaba enterrada, P4 no avisaba del modo ANUAL, y en P7 el panel anual quedaba al final tras todo el resultado del día único.

**Solución (Opción B + ajuste menor en P7)**:
- En P4: cuando `modo_analisis == ANUAL`, la sección "📅 Operación anual de cámara" aparece **arriba**, antes del botón de batch puntual. El batch puntual queda accesible debajo como "Test puntual de un día (opcional)".
- Se extrajo un closure `_build_camara` que arma la `Camara` desde los widgets actuales (incluyendo override `modo_calculo="termodinamico"` para el flujo anual). Permite que el botón "Calcular operación anual" funcione sin requerir correr el batch puntual primero.
- En P7: cuando `modo_analisis == ANUAL` y hay `p4_resultado_anual` en session_state, el panel mensual se renderiza al principio (tabla 12 meses + barras kg/mes con η_total como línea sobre eje secundario). Si modo ANUAL pero no se calculó aún, banner info dirigiendo a P4.

**Tests** (`tests/test_calculos/test_operacion_anual_camara.py`, 30 nuevos):
- 3 calor latente del agua.
- 14 las 4 eficiencias (canónicos, monotonías, clipeos, casos límite).
- 6 `dia_tipo_mensual` con clima sintético senoidal.
- 4 validaciones `OperacionAnualConfig`.
- 3 smoke del orquestador.

### 123.4 Bug live detectado por el usuario

Tras desplegar la UI nueva, el usuario corrió "Calcular operación anual" en un caso ARMARIO real y reportó **12 errores idénticos**:

```
ANUAL_MES_01_FALLO: simular_secado() got an unexpected keyword argument 'UA_perdidas_paredes_W_K'
```

Causa: `_calcular_punto_mensual` invocaba `simular_secado` directamente con parámetros que el motor no acepta (`UA_perdidas_paredes_W_K`, `T_amb_K_ref`). El motor TD requiere `h_conv_W_m2K`, `K_m_kg_m2s`, `k_aisl_W_mK`, `esp_cam_m`, `P_Pa`, `aw_func` que se calculan desde la dataclass `Camara`.

**Fix:** cambiar la llamada para delegar a `calcular_camara` (el dispatcher de `calculos/camara_calc.py`), que arma todos los parámetros desde la dataclass. Se eliminaron tres helpers ahora muertos: `_cp_producto`, `_area_cuerpo_m2`, `_UA_paredes`.

El orquestador captura excepciones por mes y deja un `MES_FALLO` por cada uno — por eso aparecía 12 veces el mismo error, no era un bug nuevo cada mes.

**Resultado tras el fix:** Suite pasa de 803 a 833 (+30 netos en S31c). El usuario validó que el modo anual corre los 12 meses sin error.

---

## 124. Revisiones conceptuales (sin cambios de código)

### 124.1 Toggle `disponible_nocturno` del auxiliar

El usuario pidió revisar qué hace el toggle. Diagnóstico:

- **Modo Transitorio** (`calculos/auxiliar_calc.py::calcular_auxiliar_transitorio`): cuando `disponible_nocturno=False` y hay `I_g_W_m2_serie`, los pasos con `I_g ≤ _I_G_UMBRAL_DIA_W_M2 = 10 W/m²` reciben `Q_efectivo=0` forzado.
- **Modo Constantes**: el toggle se ignora (calcular_auxiliar escalar no recibe irradiancia).
- **Advertencia estática**: `AUX_RESPALDO_SIN_DISPONIBILIDAD_NOCTURNA` (Severidad INFO) cuando `modo_operacion=RESPALDO_INDEPENDIENTE` y `disponible_nocturno=False`.

Discusión: el toggle es **binario** (no es "operar solo hasta X kg evaporados", ni "ventana horaria nocturna", ni "modo intermitente de mantenimiento"). Con `disponible_nocturno=True` el auxiliar opera 24 hs a potencia nominal (modulada por set_point si está definido). En modo `SERIE_POSCOLECTOR` sin set_point: consumo nocturno enorme porque el colector no aporta y el auxiliar carga todo el calentamiento.

Decisión del usuario: **no cambiar nada por ahora**, queda documentado como deuda física (`disponible_nocturno` en modo Constantes ignorado, sin estrategias sutiles tipo "apagado por humedad alcanzada").

### 124.2 Quemador de biomasa

El usuario sospechó que "no está mapeado". Diagnóstico:

Sí está mapeado completamente: enum, validaciones, helper de consumo, UI, persistencia, reporte TXT. **Pero termodinámicamente el tipo no cambia nada del cálculo del calor entregado al aire** — la única diferencia con `RESISTENCIA_ELECTRICA` es el output reportado (kg/h de combustible vs W eléctricos). Posibles deudas físicas listadas: inercia térmica de arranque/apagado, η variable con carga, modo on/off vs modulación continua, carga mínima, disponibilidad de combustible.

Decisión del usuario: **no cambiar nada por ahora**, queda documentado como deuda física.

---

## 125. Estructura de commits y pusheo

El usuario optó por **3 commits limpios sin `git add -p`**:

1. `1daf636` `feat(chimenea): migra extractor eolico de motor a accesorio de chimenea` — 7 archivos puros (`core/motor.py`, `core/chimenea.py`, `calculos/chimenea_calc.py`, `calculos/balance_global.py`, `ui/p6_motor.py`, `tests/test_calculos/test_chimenea_calc.py`, `tests/test_core/test_motor.py`).
2. `dced34b` `feat(camara): K_rugosidad en bandejas y operacion anual cascada A+B` — 9 archivos (`core/camara.py`, `calculos/motor_calc.py`, `calculos/clima_calc.py`, `calculos/eficiencias_camara.py`, `calculos/operacion_anual_camara.py`, `ui/p4_camara.py`, `ui/p7_resultados.py`, `tests/test_calculos/test_motor_fase2.py`, `tests/test_calculos/test_operacion_anual_camara.py`). Mezcla K_rug + anual porque comparten `core/camara.py` y `ui/p4_camara.py`.
3. `301c4ac` `docs: actualiza CLAUDE.md y mapa_conexiones con cambios de S31` — `CLAUDE.md`, `docs/mapa_conexiones.md`.

Pusheados a `origin/main` con `git push`.

---

## Conteo final

- Tests: **833 + 2 xfailed** (+59 netos desde 774 de S30).
- Archivos modificados: 15.
- Archivos nuevos: 3 (`calculos/eficiencias_camara.py`, `calculos/operacion_anual_camara.py`, `tests/test_calculos/test_operacion_anual_camara.py`).
- Líneas netas: +3060 / −1244.

## Deudas físicas abiertas tras S31

- **η_colector del modo anual no se conecta con resultados de P3** (usa default 0.5 fijo en el modelo lineal — opción A). Sería una iteración futura: leer la η_térmica anual del colector calculada en P3 cuando esté disponible.
- **Auxiliar mensual en operación anual**: `E_aux_batch_MJ = 0` siempre en `_calcular_punto_mensual`. Habría que modelar el auxiliar mensual (lo que requiere el motor TD termodinámico con auxiliar acoplado, o una estimación analítica de consumo mensual).
- **Caso CAJA (sin colector) en modo anual**: orquestador rechaza con "ANUAL_REQUIERE_COLECTOR" hoy. Para CAJA habría que cambiar el modelo A — sin colector no aplica `T_sal = T_amb + η·POA·A/(ṁ·cp)`, sería directamente POA sobre el techo translúcido + balance interno de cámara.
- **`disponible_nocturno` en modo Constantes**: hoy se ignora; tema abierto para iteración futura si surge necesidad de estrategias más sutiles ("apagado por humedad alcanzada", "ventana horaria nocturna").
- **Quemador de biomasa con física diferenciada**: inercia térmica de arranque/apagado, η variable con carga, operación on/off con histéresis cuando hay set_point.
- **Hoja de ruta a 1.0 restante**: modo industrial (`Tipologia.GRAN_ESCALA`) — particularidades de prediseño para 100 kg–toneladas (banco de colectores, distribución de flujo, sectorización de cámara, recirculación).

## Convención de workflow consolidada

Se documentó en CLAUDE.md (sección nueva "Convenciones de trabajo") y en memoria persistente (`feedback_workflow.md`): **se trabaja en repo local (working tree) por defecto, sin commits ni push, salvo que el usuario indique explícitamente lo contrario**. Un commit pedido no implica push automático.
