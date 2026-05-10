# Bitácora — Sesión 21 (2026-05-10)

**Tema:** S5 — integración del motor termodinámico de cámara con el balance global y la Pestaña 7. Cierre de la integración end-to-end del motor TD: P4 (entrada) → balance global (orquestación) → P7 (resultados).

**Estado al cierre de la sesión:** S5 cerrada en sus tres frentes (balance global, P7, tests). Suite global: **594 passed, 1 xfailed** (+4 tests nuevos). Verificación manual con `streamlit run app.py` confirmada por el desarrollador. Sub-tarea S6 (validación cruzada del motor TD contra capa fina) sigue pendiente.

---

## 25. Decisiones técnicas — Sesión 21

### 25.1 Decisión: el motor TD reemplaza capa fina en el balance global cuando está activo

Discusión inicial entre tres opciones para integrar el motor termodinámico al `balance_global`:

| Opción | Pros | Contras |
| :--- | :--- | :--- |
| Diagnóstico avanzado (no toca balance global) | Más simple, no rompe nada | t_secado del balance global puede contradecir la del motor TD |
| **Motor TD reemplaza capa fina cuando está activo (elegida)** | Coherencia entre P4 y P7 | Requiere refactor del balance global y manejar `t_secado=None` |
| Ambos en paralelo, comparativo | Útil para validación | Doble orquestación, decisión menor para v0 |

Razón: la variable `Camara.modo_calculo` ya es la fuente de verdad sobre qué motor querés usar; respetar esa elección a lo largo de todo el pipeline es más predecible que tener dos t_secado diferentes en pestañas distintas.

### 25.2 Refactor de `calculos/balance_global.py`

**Cambios estructurales:**

- Import: `calcular_camara` (dispatcher de `camara_calc.py:683` que ya despachaba por `modo_calculo`) en lugar de `calcular_tiempo_secado` (capa fina directa).
- Tipo de `ResultadosCompletos.camara`: `Optional[Union[ResultadosCamara, ResultadoMotorTermodinamico]]`. Alias `_SolverCamaraUnion` definido a nivel de módulo.
- `calcular_todo` ahora pasa `T_amb_K` al dispatcher (necesario en TD para U_muros y fallback de T_prod_inicial).

**Helper nuevo `_extraer_t_y_masa(solver_cam) -> tuple[Optional[float], float]`:** abstrae los nombres divergentes entre los dos resultados:

| Campo | Capa fina (`ResultadosCamara`) | TD (`ResultadoMotorTermodinamico`) |
| :--- | :--- | :--- |
| t_secado_s | `float` (siempre) | `float \| None` (None si `t_max_alcanzado` o `error`) |
| masa de agua | `masa_agua_extraida_kg` | `masa_evaporada_total_kg` |

**Manejo de no-convergencia (motor TD):** cuando `t_secado_s is None`, el balance global no puede multiplicar potencias × tiempo. Los campos energéticos (`energia_solar_util_MJ`, `energia_auxiliar_MJ`, `energia_motor_MJ`, `energia_secado_MJ`, `energia_total_MJ`, `COP_secado`, `fraccion_solar`) se dejan como `None` y se emite advertencia `BG_TD_NO_CONVERGE` con el `status` reportado por el solver. La masa de producto seco SÍ se sigue calculando porque no depende del tiempo.

### 25.3 Refactor de `ui/p7_resultados.py`

**Helper local `_resumen_camara(cam) -> tuple[t_h | None, masa_agua, status_str, ok]`:** reusado en las cuatro secciones que tocan resultados de cámara para evitar branchs `isinstance` dispersos.

**Cuatro secciones branchadas con `isinstance(cam, ResultadoMotorTermodinamico)`:**

1. **Dashboard cámara** — métricas distintas por modo:
   - Capa fina: tiempo, X_eq, agua evaporada, MR objetivo + curva X(t).
   - TD: tiempo (o `—` si no convergió), status, agua evaporada, X final + gráfica termodinámica de 3 paneles. Si `status='t_max_alcanzado'` se muestra `st.warning` destacado; si `status='error'`, `st.error`.
2. **Resumen del ciclo** — usa el helper para mostrar t_h y masa.
3. **Tabla exportable** — agrega filas de "X final" y "T producto final" en TD; "X_eq" solo en capa fina.
4. **Texto del prediseño (.txt exportable)** — bloque CÁMARA con campos por modo, incluye etiqueta "Modo cálculo".

### 25.4 Extracción a `ui/componentes/graficas.py`

La función `_grafica_termodinamica` vivía local en P4 (líneas 95-145). P7 también la necesita en S5. Para no duplicar:

- `ui/componentes/graficas.py` (era stub vacío) ahora aloja `grafica_termodinamica_camara(res, X_obj, prod_id) -> plt.Figure`.
- `ui/p4_camara.py` y `ui/p7_resultados.py` importan desde ese módulo.

Decisión: importar entre módulos UI horizontalmente (`p7 → p4`) generaría acoplamiento indeseable. La regla del proyecto es separar por capas pero las pestañas son hermanas, no jerarquías, así que componentes compartidos van en `ui/componentes/`.

### 25.5 Tests nuevos — `TestModoTermodinamico` en `test_balance_global.py`

Cuatro tests, fixture `proyecto_yacon_TD` (yacón con GAB calibrada → converge en termodinámico).

| Test | Verifica |
| :--- | :--- |
| `test_devuelve_ResultadoMotorTermodinamico` | `isinstance` correcto + `status='X_obj_alcanzado'` |
| `test_balance_energetico_calculado_cuando_converge` | Energías y COP poblados igual que con capa fina |
| `test_masa_agua_usa_masa_evaporada_total` | E_secado se computa con `masa_evaporada_total_kg` (no con `masa_agua_extraida_kg`, que no existe en TD) |
| `test_no_convergencia_emite_advertencia_y_energias_None` | Manzana sin GAB con HR=50% → fallback aw lineal se atasca → `t_secado=None`, status `t_max_alcanzado`, advertencia `BG_TD_NO_CONVERGE`, energías `None`, pero `masa_producto_seco_kg` igual se calcula |

Suite global: **594 passed, 1 xfailed** (+4 vs sesión 20).

### 25.6 Pendiente para S6 — validación cruzada

El motor TD ya está integrado de punta a punta pero no hay aún validación de que sus predicciones sean razonables comparadas con el motor de capa fina (que tiene parámetros experimentales). Agenda para sesión 22:

- Para 1-2 productos con tanto k de capa fina como GAB calibradas (ej. yacón, durazno), correr ambos motores con las mismas condiciones y comparar t_secado y X(t).
- Documentar en bitácora la magnitud de la diferencia y el rango operativo en el que ambos motores coinciden / divergen.
- Refrescar la advertencia `CAM_TD_GAB_FALTA` con la magnitud del error esperado por usar fallback aw lineal.

### 25.7 Mejora informal identificada — `t_max_s` configurable desde UI

El balance global llama al dispatcher con el default `t_max_s=72*3600` (de `calcular_camara`). Para casos límite (productos muy húmedos, caudales bajos) podría hacer falta configurarlo desde P4 o P7. No bloqueante para v0; se deja como TODO para una mejora futura.
