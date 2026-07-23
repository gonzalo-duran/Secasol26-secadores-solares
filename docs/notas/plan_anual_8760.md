# Plan — Modo anual sobre 8760 h reales

Reemplazo del modo anual actual (12 días típicos mensuales) por una simulación sobre
la serie horaria real del año, reusando el pipeline de ventana ya validado.

Decidido con el usuario en S57. Estado: **E1–E5 implementadas** (working tree; pendiente la prueba manual en Streamlit con clima real de NASA).

## 1. Por qué

El modo anual actual corre el motor termodinámico 12 veces, una por mes, sobre el
**día típico** de ese mes (`clima_calc.dia_tipo_mensual` = `groupby(hour).mean()`),
replicado hasta llenar un horizonte de 72 h. La auditoría de S57 encontró que eso
entrega números con problemas serios:

| # | Problema | Verificado |
|---|---|---|
| 1 | `kg_secados_anual` es **agua evaporada**, rotulada como "kg secados/año" y documentada como "kg de producto fresco secados" | `kg_secados_mes = m_evap · n_batches`, y `m_evap = res.masa_evaporada_total_kg` |
| 2 | **η_térmica ≡ η_colector**, siempre. Como P4 no pasa `eta_colector`, muestra 0.5 los 12 meses para cualquier diseño | Álgebra: `Q_aire ≡ η_col·POA·A_col` y `η_térmica = Q_aire/(POA·A_col)`. Comprobado numéricamente: η_col=0.3/0.5/0.7 → η_térmica=0.3/0.5/0.7 |
| 3 | **η_drying ≡ η_total**, siempre, porque `E_aux` está hardcodeado en 0 y ambas dividen por `E_solar_J` | Comprobado: 0.0304223770 en ambas |
| 4 | El **colector real no entra**: η fijo en 0.5, así que cambiar tipo/cubiertas/materiales en P3 no mueve el anual salvo por el área | `_ETA_COLECTOR_DEFAULT = 0.5`; P4 llama `calcular_operacion_anual_camara(proyecto)` sin el parámetro |
| 5 | `I_g_diaria_minima_MJ_m2` es **campo huérfano**: documentado como "descuenta días no operables", validado en `__post_init__`, sin widget y sin uso | `grep` sin resultados fuera de `core/camara.py` |
| 6 | `batches_por_mes` es **aserción del usuario** sin chequeo contra `t_secado_h`: se pueden pedir 30 batches/mes con t_secado=72 h (90 días en un mes de 30) | Sin validación cruzada |
| 7 | El **día típico borra la variabilidad**: un día promedio nunca está nublado, y el secado es no lineal | `groupby(hour).mean()` |
| 8 | `t_secado_promedio_h` promedia **solo los meses que convergieron** | `[p.t_secado_h for p in puntos if p.convergio]` |
| 9 | El batch arranca implícitamente a **medianoche** (E_solar se integra desde la hora 0) | `POA_horizonte = np.tile(POA_dia, n_dias)[:horas_op]` |

De las cuatro eficiencias de Augustus Leon, entonces, **solo dos llevan información**
(η_drying y η_pickup) y una de esas dos está duplicada.

## 2. Qué se resuelve solo con cambiar de pipeline

`calculos/simulacion_ventana.py::_simular_ventana_batch` **ya hace** el encadenado de
lotes event-driven sobre clima real horario, y está validado contra la campaña de
ADITAL. Correr el anual como una ventana de 365 días resuelve, sin escribir física
nueva:

- **1** → `masa_seca_producida_kg` ya existe y es producto seco de verdad
  (`m_seco_total·(1+X_objetivo)`).
- **6** → `n_batches_completos` pasa a ser **resultado**, no entrada.
- **7** → clima real: las rachas nubladas alargan lotes o los frustran.
- **8** → el lote que no cierra queda registrado como tal (`batch_en_progreso`).
- **9** → el encadenado es event-driven: cada lote arranca cuando termina el anterior,
  no a medianoche.

## 3. El costo, y cómo se paga

Medido sobre el fixture de `test_ventana_glue`, el pipeline de ventana escala **lineal**
a ~26 ms/hora simulada:

| Ventana | Tiempo | Extrapolado a 8760 h |
|---|---|---|
| 72 h | 2.00 s | 4.1 min |
| 168 h | 4.41 s | 3.8 min |
| 336 h | 8.79 s | 3.8 min |

El desglose muestra dónde está: **95.4 % es el colector** (8.57 s de 8.98 s en 336 h),
porque `_correr_colector_horizonte_forzado` corre el solver estacionario una vez por
hora. La cámara sobre un año entero cuesta ~12 s.

### Sustituto interpolado del colector

En el pipeline de ventana el colector se resuelve **con `T_entrada = T_amb`**. En
Hottel-Whillier-Bliss eso anula el término de pérdidas `U_L·(T_in − T_amb)`, así que
la respuesta queda casi afín en POA. Verificado contra el solver real:

```
T_amb=10 °C, v=1 m/s → ΔT = 3.32, 14.16, 24.99, 35.70, 46.27, 56.71 K
                       para POA = 100..1100 W/m²
incrementos por cada 200 W/m²: 10.84, 10.83, 10.71, 10.57, 10.44  (pendiente casi cte)
```

El espacio de entrada es **3-D**: `(POA, T_amb, v_viento)`. No hay una cuarta dimensión
porque `T_entrada = T_amb` y la velocidad del módulo, cuando se deriva del caudal del
sistema, depende de `T_amb` solamente (vía ρ).

**Validación del sustituto** (grilla 9×5×4 = 180 solves, `RegularGridInterpolator`
lineal, 60 puntos aleatorios contra el solver):

```
construcción: 4.7 s
error vs solver: medio 0.076 K | p95 0.217 K | máx 0.276 K
```

Para dimensionar ese error: el modelo de colector validado contra el prototipo de 10 m
del INENCO da **RMSE 0.9 °C** contra medición real. El error de interpolación es ~4×
menor que el error propio del modelo contra la realidad — es ruido frente a la física
que ya se acepta.

**Beneficio doble**: además de bajar el colector de 3.7 min a ~5 s, el sustituto se
construye **con el colector real del proyecto**, lo que resuelve el problema 4 — hoy el
anual ignora el diseño del colector.

Estimación del anual completo: ~5 s (grilla) + ~12 s (cámara) + overhead ≈ **20-30 s**,
viable en HF Spaces.

## 4. Física del modelo — qué captura y qué no

**Captura:**
- Variabilidad real del clima hora a hora: rachas nubladas, estacionalidad, noches.
- Encadenado real de lotes: la duración de cada lote depende del clima que le tocó, y
  el siguiente arranca cuando termina el anterior.
- Acoplamiento colector→cámara con el colector **real** del proyecto (vía sustituto).
- Auxiliar con calendario de arranque (ya integrado en el pipeline de ventana).

**No captura (límites conscientes):**
- **El CSTR de la cámara sigue siendo un nodo único**: no hay perfil espacial de humedad
  ni temperatura dentro del lecho, ni gradiente entre bandejas. Una bandeja de arriba y
  una de abajo secan igual. Vale como prediseño; no reemplaza un modelo distribuido.
- **El sustituto del colector es cuasi-estacionario**, igual que el solver que
  reemplaza: no hay inercia térmica del colector. En transiciones rápidas (paso de nube)
  el ΔT real tarda en responder; el modelo lo hace instantáneo.
- **Política de operación parcial** (agregada tras la primera corrida real del
  usuario): el encadenado espera a la hora de carga del día y descuenta un tiempo de
  maniobra (`PoliticaRecarga`), lo que bajó la producción un 10 % sobre el fixture
  anual. Sigue sin haber turnos de trabajo ni fines de semana, así que el resultado
  **sigue siendo una cota superior**, aunque menos holgada.
- **No hay decisión de no-operar**: el modelo carga un lote aunque el pronóstico sea
  malo. Un operador real no arranca un lote un día nublado. Esto sesga hacia lotes
  frustrados que en la práctica no ocurrirían.
- **Un solo año de clima** (el de NASA POWER descargado): no hay estadística
  interanual, así que la dispersión reportada es intra-anual, no de años buenos vs malos.

## 5. Etapas

### E1 — Sustituto del colector (`calculos/superficie_colector.py`)
Módulo puro nuevo. `construir_superficie(proyecto, ...)` corre el solver sobre la grilla
y devuelve un objeto con `evaluar(POA, T_amb, v) -> ΔT`, vectorizado. Grilla adaptada al
rango real del clima del proyecto (no fija). Test de exactitud contra el solver como el
de validación de arriba, con umbral p95 < 0.3 K.

Enchufe: `_correr_colector_horizonte_forzado` gana un camino rápido opcional.

### E2 — Motor anual (`calculos/simulacion_anual.py`)
Corre `armar_forzantes_ventana` + encadenado de lotes sobre los 8760 h. Requiere
extender `_simular_ventana_batch` para devolver **historia por lote** (inicio, fin,
duración, masa evaporada, status) — hoy solo devuelve agregados. Con eso se atribuye
cada lote a su mes.

### E3 — Métricas
Dataclass nueva con: producto seco kg/año y kg/mes; agua evaporada (separada y bien
rotulada); lotes completos vs frustrados; días operables reales; energía específica de
secado [MJ/kg agua]; fracción solar; consumo de auxiliar (leña/electricidad); dispersión
de duración de lote (p50/p90); η_drying y η_pickup. **Se eliminan** η_térmica
(tautológica) y η_total (duplicada de η_drying mientras E_aux=0 — con el auxiliar
implementado en E2 vuelve a tener sentido y se conserva).

### E4 — UI (P4 + P7) + CSV
P4: la sección anual pierde `batches_por_mes` como entrada (pasa a resultado) y resuelve
el huérfano `I_g_diaria_minima_MJ_m2` (implementarlo como criterio de día operable o
borrarlo). P7: tabla mensual + figuras + **`download_button` CSV** (hoy no existe CSV en
todo el anual; el único `to_csv` del repo está en P2 para el clima).

### E5 — Exports y cierre
TXT/JSON/PDF, i18n ×3, `docs/mapa_conexiones.md`, CLAUDE.md, CHANGELOG. Eliminación de
`calculos/operacion_anual_camara.py` y su config, con back-compat de snapshots que
traigan `operacion_anual`.

## 6. Riesgos

- **Snapshots viejos**: `Camara.operacion_anual` desaparece como entrada. Hay que
  aceptarlo y ignorarlo al deserializar, no romper la carga.
- **Clima incompleto**: el anual ya exige 12 meses (`ANUAL_CLIMA_INCOMPLETO`); se
  mantiene.
- **Tiempo en HF**: si los ~25 s estimados se van a minutos en el Space, hay que
  considerar barra de progreso por mes y/o cachear el resultado por hash del proyecto.
- **`_MAX_BATCHES = 10_000`** alcanza para un año (un lote de 12 h daría ~730).

## Ver también

- [[docs/notas/plan_secador_industrial]] — pipeline de ventana que se reusa.
- [[docs/bitacora/bitacora_sesion40]] — validación ADITAL del encadenado de lotes.
- [[docs/tareas]]
