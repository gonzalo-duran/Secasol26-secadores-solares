# Bitácora — Sesión 28 (2026-05-17)

**Tema:** Tres líneas de trabajo en paralelo: (1) refactor del módulo motor en dos fases (Haaland + tipos de malla + ΔP singulares + presión dinámica + ΔP por tipo de colector, con tests de regresión anclados al extractor empírico Gatti 150), (2) Etapa A de tipología CAJA (Camara admisible para CAJA con cubierta translúcida obligatoria, sin colector externo, aporte Q_rad al producto), (3) migración global a Plotly + mejoras de UX en P2 (día de diseño) y P4 (capa fina T-dependiente).

**Estado al cierre:** 685 tests pasan + 2 xfailed. Sin commits. 5 archivos nuevos de tests; 5 documentos en `docs/notas/` (especificación motor, cubiertas translúcidas, papers de referencia). Directorio `validacion/` movido fuera de raíz. Mejoras 14–17 marcadas implementadas en `docs/notas/mejoras.md`; queda pendiente la 18.

---

## 63. Punto de partida

S27 cerró con 632 tests pasando, motor de cámara consolidado y motor cinético eliminado. Quedaban abiertos en la pizarra:

- **Mejora 14** (P2): perfiles horarios del día de diseño.
- **Mejora 15** (P2): descarga CSV del día.
- **Mejora 16** (P4): tiempo de secado independiente de masa/espesor cuando se usa capa fina — bug grave.
- **Mejora 17** (todas): migración a Plotly para hover/zoom/export nativos.
- **Mejora 18** (CAJA): U_paredes no impacta visiblemente — postergada.
- **Refactor motor**: anclaje empírico (Gatti 150, 76 W / 900 m³/h) sugería que el modelo subestimaba ΔP por ignorar singulares, presión dinámica de salida y rugosidad real de placa.
- **Techo translúcido en cámara**: pedido conceptual del usuario en `docs/notas/cubiertas translucidas en camara de secado.md` (escrito esta sesión) — el campo `cubierta_translucida` existía como bool decorativo pero sin efecto físico.
- **CAJA implementable**: tras consolidar el motor TD en S27, ya había andamiaje para hacer una "cámara solar pura" con T_ent=T_amb + aporte radiativo.

El plan se atacó en cuatro frentes simultáneos.

---

## 64. Refactor del motor — Fase 1 (rugosidad + tipos de malla)

### 64.1 Haaland con rugosidad real del catálogo

Antes: `estimar_delta_P_colector` usaba ε=5e-5 m hardcodeado para la fricción de canal. Ahora `placas.yaml` declara `rugosidad_m` por material (galvanizada pintada 5e-5, aluminio pintado 3e-5, TiNOX pulido 2e-5, galvanizada cruda 1e-4) y `motor_calc._delta_P_canal_colector` lee `colector.unidad.placa_absorbedora.rugosidad_m` con fallback al default conservador (`_RUGOSIDAD_DEFAULT_M = 5e-5`).

`_factor_friccion_haaland(Re, eps_rel)` (nueva en `motor_calc.py`) implementa la correlación explícita de Haaland (1983) con error < 2 % vs Colebrook-White implícita. Régimen laminar f=64/Re (independiente de ε), turbulento (Re ≥ 4000) Haaland puro, transición 2300–4000 mezcla lineal.

### 64.2 K_malla parametrizado por tipo de bandeja

Antes: `K_MALLA = 2.0` fijo (malla mosquitera densa, sobreestima para bandejas comunes).

Ahora:

```python
TIPOS_MALLA = {
    "alambre_fino":          2.0,   # mosquitera ≤ 1 mm
    "alambre_grueso":        1.0,   # malla galvanizada 1.5–3 mm (default)
    "chapa_perforada_50pc":  3.5,
    "chapa_perforada_30pc":  8.0,
    "tela_metalica_densa":   4.0,
}
K_MALLA = 1.0   # default cambiado de 2.0 a alambre_grueso (más representativo)
```

`_K_malla_efectivo(tipo_malla)` resuelve con fallback. Lectura de `bandejas.tipo_malla` (campo opcional).

### 64.3 Geometría de lecho desde catálogo

`_geometria_lecho(bandejas, producto_id)` resuelve `(d_p, ε, Φ_s)` con cadena de prioridad:

1. Si el usuario seteó valores explícitos en `ConfiguracionBandejas`, usarlos.
2. Si el producto declara `forma_geometrica` en catálogo (manzana, papa actualizados esta sesión), leerlos.
3. Defaults conservadores: 8 mm / 0.45 / 0.6 (trozo medio sobre bandeja).

Reduce dependencia del usuario al rellenar manualmente cada vez.

---

## 65. Refactor del motor — Fase 2 (ΔP singulares + presión dinámica + ΔP por tipo)

### 65.1 ΔP singulares — nueva fuente de pérdida

`estimar_delta_P_singulares(Q_vol, v_ducto, n_paralelo, n_codos)` suma:

- **Entrada al sistema**: `K=0.5 · ρ·v²/2`.
- **Salida**: `K=1.0 · ρ·v²/2`.
- **Codos 90°**: `K=0.3` cada uno, default 2 codos.
- **Manifold paralelo**: `K=0.4 · n_paralelo · ρ·v²/2` si `n_paralelo > 1`.

Velocidad de referencia `v_ducto` es la del ducto principal (5–10 m/s típico en secadores solares con ø≈15 cm), distinta de la del canal de colector o de la superficial de cámara. Default 6 m/s; configurable desde P6.

`Motor.delta_P_singulares_Pa` (campo nuevo) y `Motor.v_descarga_m_s` (campo nuevo) en `core/motor.py`.

### 65.2 Presión dinámica de salida del ventilador

Antes el modelo sumaba sólo ΔP estática (col + cam + ductos). Para presión TOTAL del ventilador hay que incluir `ρ·v_descarga²/2` — la energía cinética que el aire se lleva en la boca de salida.

```python
dP_dinamica = ρ · v_descarga² / 2   # ~1.092 kg/m³ a 50 °C
self.perdida_carga_total_Pa = dP_col + dP_cam + dP_duc + dP_sing + dP_dinamica
```

`v_descarga` viene de `caudal / area_descarga` configurada por el usuario. Si `v_descarga is None`, queda en 0 (conservador a la baja, modelo histórico).

### 65.3 ΔP por tipo de colector (1/2/3/4)

`estimar_delta_P_colector(colector, ...)` ahora despacha según `tipo_colector`:

- **Tipo 1**: canal único de altura `espaciado_m`.
- **Tipo 2**: dos canales activos en paralelo → `max(ΔP_cs, ΔP_ci)` (el más restrictivo manda).
- **Tipo 3**: canal inferior activo (`espaciado_inferior_m`).
- **Tipo 4**: canal superior activo (`espaciado_m`).

Antes usaba siempre `espaciado_m` y subestimaba ΔP en Tipos 2/3 con canales más estrechos.

### 65.4 Anclaje empírico — tests de regresión

`tests/test_calculos/test_motor_anclaje.py` (nuevo, 6 tests). Contexto:

> En armarios de 50 kg de carga, el grupo UNSa/INENCO usa rutinariamente extractores tipo "campanita" Gatti 150 — **76 W eléctricos nominales con 900 m³/h (0.25 m³/s)** a descarga libre. Eficiencia total realista del conjunto motor+ventilador ~0.20–0.30 → ΔP útil ≈ 60–100 Pa, P_eléctrica esperada en operación: **40–150 W** (rango amplio porque depende de η reales del extractor concreto).

Los tests fijan un armario representativo (1.5×1.0×1.5 m, 5 bandejas×0.8 m², manzana 50 kg) y verifican que `P_eléctrica ∈ [40, 150 W]` con `Q = 900 m³/h`. Antes del refactor el modelo daba P < 20 W (subestimación gruesa por ignorar singulares + dinámica de salida).

### 65.5 Tests de Fase 2

`tests/test_calculos/test_motor_fase2.py` (nuevo, 12 tests): Haaland laminar/turbulento, K_malla por tipo con fallback, presión dinámica suma correctamente, ΔP Tipo 2 toma el mayor de los dos canales, ΔP Tipo 3/4 usa el canal activo correcto.

---

## 66. Tipología CAJA — Etapa A (Camara + cubierta translúcida obligatoria)

### 66.1 Modelo de datos

`ConstruccionCamara` (en `core/camara.py`) cambia drásticamente:

| Antes | Después |
|---|---|
| `cubierta_translucida: bool = False` (decorativo) | `cubierta_translucida_id: Optional[str] = None` (referencia al catálogo) |
| — | `A_rad_m2: Optional[float] = None` (default = `area_bandeja_m2` de la primera bandeja — sólo la superior "ve" el sol) |

`__post_init__` valida que el id exista en `catalogo.CUBIERTAS`. Sigue siendo retrocompatible: cubierta opaca (= `None`) anula `τ·α·A_rad = 0` sin coste.

### 66.2 Coherencia CAJA

`verificar_coherencia_proyecto` (en `balance_global.py`) agrega regla:

```
PROY_CAJA_SIN_CUBIERTA_TRANSLUCIDA: tipología CAJA requiere techo translúcido
(cubierta_translucida_id no-None). Sin colector externo, la radiación solar
a través de la cubierta es la única fuente de energía del producto.
```

La restricción histórica `CAJA → motor = None` se mantiene (convección natural).

### 66.3 Tests integrales CAJA

`tests/test_calculos/test_caja.py` (nuevo, 5 tests):

- Cámara CAJA pequeña (0.6×0.4×0.3 m, 1 bandeja, 1 kg manzana) con cubierta vidrio_común + I_g sinusoidal → seca dentro de 24 h.
- Misma cámara sin radiación (`I_g = 0`) → no seca (aire ambiente a T_amb sin aporte energético).
- CAJA + colector → error de coherencia.
- CAJA + cubierta opaca → error de coherencia.
- Verificación de A_rad default (toma `area_bandeja_m2`).

---

## 67. Radiación al producto en motor TD — Capas 1–4

Implementación según `docs/notas/cubiertas translucidas en camara de secado.md` (escrito por el usuario esta sesión).

### 67.1 Capa 1 — `ForzantesAire.I_g_W_m2`

Campo opcional `I_g_W_m2: Optional[np.ndarray] = None`. En `__post_init__`, si es None se rellena con ceros (cámara opaca o modo Constantes sin sol). Si se provee, valida que tenga la misma longitud que `t_s`.

### 67.2 Capa 2 — `simular_secado` aporte radiativo

El RHS de la EDO del producto agrega:

```python
Q_rad = I_g(t) · τ_cub · α_prod · A_rad
dT_prod/dt = (q_prod + Q_rad − ṁ_w · L_v) / C_thermal
```

donde τ_cub viene de `catalogo.CUBIERTAS[id]["transmitancia_solar"]`, α_prod del producto (`alfa_solar` opcional, default 0.6 — superficie sólida media), A_rad de `ConstruccionCamara.A_rad_m2` o fallback a la bandeja superior. `I_g(t)` interpolado de forzantes.

### 67.3 Capa 3 — `construir_serie_sintetica_dia_tipo` con I_g

```python
I_g(h) = I_g_pico · sin(π·(h − salida) / duracion)   si en horas de sol
       = 0                                            si noche
```

Curva sinusoidal positiva, pico al mediodía solar, default `I_g_pico=900 W/m²`, `salida=6`, `puesta=18`. Permite simulación "día sintético" con sol.

### 67.4 Capa 4 — Wire-up en `_calcular_termodinamico`

Lee `cons.cubierta_translucida_id`. Si está, busca τ en catálogo, lee α de producto (default 0.6), resuelve A_rad. Si la cubierta es opaca (id None), τ=0 y A_rad=0 anulan el término sin más lógica.

### 67.5 Tests

`tests/test_calculos/test_radiacion_cubierta.py` (nuevo, 16 tests). Cubre:

- `ForzantesAire`: longitud inconsistente de I_g levanta error; default a ceros.
- `simular_secado`: con τ=0 el motor ignora I_g aunque sea no-cero; con τ>0 e I_g>0 el T_prod sube más que con I_g=0; balance de energía cierra (Q_rad alimenta el cambio de entalpía del producto).
- `construir_serie_sintetica_dia_tipo`: I_g sinusoidal positiva, máximo al mediodía, cero en noche.
- Integración con `armar_forzantes_aire`: pasa I_g al ForzantesAire de salida.

---

## 68. Capa fina T-dependiente — Mejora 16 (bug grave)

### 68.1 Diagnóstico

El usuario observó que el tiempo de secado en modo "capa fina" salía **0.25 h** para yacón a cualquier T_op, masa y espesor. Causa raíz: `calcular_tiempo_secado` (renombrado esta sesión a `calcular_tiempo_secado_estatico`) leía sólo el escalar top-level de `params` y **ignoraba completamente `sets_por_temperatura`**. Para yacón el escalar top-level es `k=0.217 min⁻¹` (calibrado a 25 °C), así que daba el mismo tiempo a 60 °C que a 25 °C.

### 68.2 Fix

Nueva fn `_interpolar_params_cf(modelo_entry, T_K)`:

```python
def _interpolar_params_cf(modelo_entry, T_K):
    sets = modelo_entry["params"].get("sets_por_temperatura")
    if not sets:
        return {k: v for k, v in modelo_entry["params"].items() if k != "sets_por_temperatura"}
    T_arr = np.array([s["T_K"] for s in sets])
    param_keys = [key for key in sets[0] if key not in ("T_K", "R2")]
    return {key: float(np.interp(T_K, T_arr, [s[key] for s in sets])) for key in param_keys}
```

Para yacón ahora:

| T_op | k (interpolado) | t_secado capa fina |
|:---:|:---:|:---:|
| 15 °C | 0.069 min⁻¹ | ~40 min |
| 25 °C | 0.217 min⁻¹ | ~13 min |
| 35 °C | 0.341 min⁻¹ | ~9 min |

`np.interp` extrapola por valores extremos si T_op cae fuera del rango calibrado (la advertencia `CAM_T_FUERA_RANGO_CALIBRACION` se mantiene como antes).

### 68.3 Independencia masa/espesor

Es **correcta** por diseño: el modelo de capa fina es intensivo (descripcion de la cinética de un sólo gramo). La independencia con la masa NO es un bug.

### 68.4 Nueva advertencia `CAM_ESPESOR_FUERA_CALIBRACION`

Si `espesor_capa_real > 3 × espesor_capa_calibracion` (del catálogo), el modelo subestima el tiempo de secado porque la resistencia interna a la transferencia de masa deja de ser despreciable. Mensaje sugiere reducir espesor o usar el motor TD difusivo.

### 68.5 Catálogo actualizado

- **Manzana** (`frutas.yaml`): GAB cargado desde Kaymak-Ertekin & Gedik (2004) con `sets_por_temperatura` a 30/45/60 °C. Calidad MEDIA (P% = 10.16). `forma_geometrica` agregada (d_eq=6 mm, ε=0.45, Φ_s=0.6).
- **Papa** (`hortalizas.yaml`): X0 actualizada a 4.5 (Naderinezhad 2016). Modelo Midilli con `sets_por_temperatura` a 318/328/333 K. `forma_geometrica` agregada (d_eq=10 mm, Φ_s=0.7).

---

## 69. Migración a Plotly — Mejora 17

`requirements.txt` agrega `plotly>=6.0.0`. Archivos migrados:

| Archivo | Antes | Después |
|---|---|---|
| `ui/p2_emplazamiento.py` | matplotlib.pyplot | plotly.graph_objects + make_subplots |
| `ui/p3_colector.py` | matplotlib.pyplot | plotly.graph_objects |
| `ui/p4_camara.py` | matplotlib.pyplot | plotly.graph_objects |
| `ui/componentes/graficas.py` | matplotlib | plotly (componentes reutilizables) |
| `ui/p7_resultados.py` | matplotlib | plotly |

Ganancias inmediatas: hover con tooltip exacto, zoom/pan nativo con mouse, exportación PNG/SVG desde el menú de la figura, eje secundario `yaxis2` nativo para T+POA en P3.

### Workaround Plotly + datetime

`add_vline(x=ts, annotation_text=...)` falla con `TypeError` cuando x es un Timestamp porque internamente intenta `sum([x, x])` para posicionar la anotación. Solución en `ui/p3_colector.py`:

```python
def _add_vline_datetime(fig, *, x, text, color, dash, width, xanchor):
    fig.add_shape(type="line", xref="x", yref="paper",
                  x0=x, x1=x, y0=0, y1=1, line=dict(color=color, dash=dash, width=width))
    fig.add_annotation(x=x, y=1.0, xref="x", yref="paper",
                       text=text, showarrow=False, xanchor=xanchor, yanchor="bottom",
                       font=dict(color=color, size=11))
```

Se usa para las verticales de mediodía solar y POA máx en las gráficas de P3.

---

## 70. P2 — día de diseño + descarga CSV (Mejoras 14 y 15)

### 70.1 Nueva sección "Recurso climático del día de diseño"

Visible sólo cuando `proyecto.configuracion.modo_analisis == ModoAnalisis.DIARIO`. Resuelve la fecha aplicando el criterio de `DiaAnalisis`:

- **Específico** → `proyecto.configuracion.fecha_especifica`.
- **Solsticio verano/invierno**, **equinoccio primavera/otoño** → fecha astronómica para el hemisferio del emplazamiento.
- **Más caluroso/frío del año** → `T_amb_K.resample("D").mean().idxmax/min()`.

Muestra 5 métricas (T media, T min/max, GHI diario, POA diario, viento medio) y 3 tabs Plotly:

- Temperatura horaria (`_fig_temperatura_diaria`).
- Irradiancia: GHI horizontal + POA en plano del colector (`_fig_irradiancia_diaria`, eje secundario para POA).
- Viento + HR (`_fig_viento_hr_diaria`, eje secundario).

El cálculo de `poa_horaria` fue hoistado fuera de los tabs para reutilizarlo en métricas y en la gráfica de irradiancia.

### 70.2 CSV del día

Botón "Descargar CSV del día (dd/mm/yyyy)" al final de la sección diaria. Reutiliza `_generar_csv()` filtrando `datos_dia`. Coexiste con el botón anual existente.

---

## 71. P6 motor — UI de ΔP singulares + presión dinámica + fix tensión (Mejora 13)

### 71.1 Expander de ΔP singulares

Nuevo expander en P6 (modo "Desglosar ΔP"): muestra el aporte de singulares con el cálculo `estimar_delta_P_singulares(Q, v_ducto, n_paralelo, n_codos)`. Slider para `v_ducto` (default 6 m/s, rango 1–20). `n_paralelo` se lee de `colector.banco.n_paralelo` si hay colector. `n_codos` por defecto 2 (entrada y salida del banco).

### 71.2 Presión dinámica de salida

Campo nuevo en la UI: "Velocidad en boca de descarga del ventilador [m/s]" (default = None → 0). Si > 0, se reporta `dP_dinamica = ρ·v²/2` en el desglose y se suma a la pérdida total.

### 71.3 Fix duplicate checkbox key (Mejora 13)

`ui/p6_motor.py` línea 351: el checkbox "Especificar tensión de alimentación" colisionaba con otro checkbox autogenerado en P5 cuando ambos usaban etiquetas similares. Solución: `key="motor_usar_tension"` explícito.

---

## 72. Forzantes reales testables

Refactor menor pero importante: `_construir_forzantes_reales` y `_disponibilidad_forzantes_reales` en `ui/p4_camara.py` ahora reciben `p3_eval` como argumento explícito en vez de leer `st.session_state["p3_eval"]`. Esto permite tests unitarios sin levantar Streamlit.

`tests/test_ui/test_forzantes_reales.py` (nuevo, 12 tests): proyecto mínimo con clima sintético 24 h + p3_eval con T_salida_C horaria → la función devuelve `ForzantesAire` consumible por el motor TD; modo anual levanta error; sin clima levanta error; multi-día replica la serie de 24 h; omega es consistente con HR y T_amb del clima; T_ent nocturna ≈ T_amb (colector apagado).

---

## 73. Colector Tipos 3 y 4 — Hollands en canal estanco

### 73.1 Bug detectado

`_construir_rhs_tipo3` (Tipo 3 = canal inferior activo, superior estanco) usaba `h_int_cs` precomputado como `K_AIRE / alto_cs_m` (Nu=1, conducción pura). Esto sobreestima la resistencia térmica del canal estanco superior cuando el absorbedor (caliente) está abajo: la convección natural es inestable y arranca cuando `Ra > Ra_crítico` (Hollands 1976).

### 73.2 Fix

Nueva función `_Ra_canal_estanco(dT, L, T_film)` en `colector_tipos234_calc.py`:

```
Ra = g · β · ΔT · L³ · Pr / ν²
con β = 1/T_film (gas ideal), ν = μ/ρ a 323 K
```

Se aplica `nusselt_hollands_inclinada(Ra, θ)` cuando el canal estanco está orientado con la cara caliente abajo (Tipo 3); se mantiene Nu=1 cuando la cara caliente está arriba (Tipo 4: canal estanco inferior con absorbedor encima — convección suprimida por estratificación).

`calcular_colector_tipo3` recibe ahora `theta_deg=45.0` (inclinación del colector); se reusa el warm-start del nodo anterior para evaluar `T_film` y `ΔT` del estanco sin iteración adicional.

### 73.3 Tests

`tests/test_calculos/test_colector_tipos234_calc.py` extendido: a inclinaciones grandes (60°) Tipo 3 con I_g alta muestra `h_int_cs > K_AIRE/L` (Hollands activo), Tipo 4 conserva `h_int_cs = K_AIRE/L` siempre.

---

## 74. Psicrometría — L_v extrapolado a T < 0 °C

`calor_latente_vaporizacion(T_K)` antes levantaba `ValueError` si `T_K ≤ 273.15`. El solver de cámara visita ocasionalmente temperaturas bajas (madrugada fría, enfriamiento evaporativo en cámara con aire muy seco), lo que causaba crashes intermitentes en simulaciones de 7+ días con clima real.

Fix: extrapolación lineal del modelo `L_v(T) = L_v0 − K_lv·(T − T_ref)` hasta T_K = 250 K (-23 °C). Error de extrapolación < 5 % entre -20 °C y 0 °C, suficiente para los tránsitos ocasionales del solver. Por debajo de 250 K (ya es sublimación pura) se mantiene la guarda.

---

## 75. Estado de archivos

### Modificados (uncommitted)

| Archivo | Naturaleza del cambio |
|---|---|
| `calculos/motor_calc.py` | +320 líneas: Haaland, TIPOS_MALLA, ΔP singulares, geometría de lecho, ΔP por tipo |
| `calculos/camara_termodinamica.py` | +330 líneas: I_g en forzantes, Q_rad en RHS del producto |
| `calculos/camara_calc.py` | +175 líneas: `_interpolar_params_cf`, advertencia espesor, wire-up Q_rad, renombrado a `_estatico` |
| `calculos/balance_global.py` | +256 líneas: I_g en `construir_serie_sintetica_dia_tipo` y `armar_forzantes_aire`, coherencia CAJA |
| `calculos/colector_tipos234_calc.py` | +90 líneas: `_Ra_canal_estanco`, Hollands en Tipos 3/4 |
| `calculos/psicrometria.py` | L_v extrapolado a -23 °C |
| `core/camara.py` | `cubierta_translucida_id` + `A_rad_m2`, validación catálogo |
| `core/motor.py` | `delta_P_singulares_Pa`, `v_descarga_m_s` |
| `catalogo/materiales/placas.yaml` | `rugosidad_m` por material |
| `catalogo/productos/frutas.yaml` | GAB manzana + forma_geometrica |
| `catalogo/productos/hortalizas.yaml` | Papa: X0=4.5, Midilli con sets, forma_geometrica |
| `ui/p2_emplazamiento.py` | Plotly + sección día de diseño + CSV día |
| `ui/p3_colector.py` | Plotly + `_add_vline_datetime` |
| `ui/p4_camara.py` | Plotly + `_construir_forzantes_reales(p3_eval)` |
| `ui/p6_motor.py` | UI de singulares + v_descarga, fix duplicate key |
| `ui/p7_resultados.py` | Plotly |
| `ui/componentes/graficas.py` | Plotly |
| `requirements.txt` | +plotly>=6.0.0 |
| `docs/notas/mejoras.md` | Mejoras 14–17 marcadas implementadas, 18 pendiente |

### Nuevos (untracked)

| Archivo | Contenido |
|---|---|
| `tests/test_calculos/test_caja.py` | 5 tests — tipología CAJA con cubierta translúcida |
| `tests/test_calculos/test_motor_anclaje.py` | 6 tests — regresión Gatti 150 |
| `tests/test_calculos/test_motor_fase2.py` | 12 tests — Haaland, TIPOS_MALLA, presión dinámica, ΔP por tipo |
| `tests/test_calculos/test_radiacion_cubierta.py` | 16 tests — Q_rad en motor TD |
| `tests/test_ui/test_forzantes_reales.py` | 12 tests — wire-up P2+P3 → ForzantesAire |
| `docs/notas/cubiertas translucidas en camara de secado.md` | Especificación del usuario para Q_rad (referencia) |
| `docs/notas/especificacion_motor_dinamico_camara.md` | Especificación histórica S23 (para referencia) |
| `docs/notas/balance de calor y masa en camara ampliado.md` | Especificación del refactor S27 |
| `docs/notas/papers/` | 12 papers sci-hub + 1 índice.md (manzana, papa, durazno, granada, pimiento, ciruela, uva, raisins) |
| `docs/notas/Saravia2007.pdf` | Paper de referencia para integral entálpico |
| `validacion/` | `validacion_cruzada_yacon.py` + .md (movidos desde raíz) + `probe_motor_C_yacon.py` |

Suite total: **685 passed, 2 xfailed** (vs 632 al cierre de S27, +51 tests netos + 2 xfailed = 53 cambios totales).

---

## 76. Cabos sueltos para próxima sesión

- **Mejora 18 (CAJA / U_paredes sin impacto visible)**: pendiente. Hipótesis a explorar: en CAJA el balance está dominado por el techo translúcido (Q_rad) y la cubierta inferior abierta al ambiente, así que U_muros laterales tiene poco peso relativo. Cuantificar con sonda paramétrica antes de tocar el modelo.
- **A_rad configurable en P4**: hoy default a `area_bandeja_m2` de la superior, pero no hay UI para overrride.
- **α_solar por producto** en `frutas.yaml` y `hortalizas.yaml`: usa default 0.6. Cargar valores específicos (manzana ~0.7, papa ~0.55, etc.) en próxima iteración.
- **Commit del trabajo de S23 + S24 + S25 + S26 + S27 + S28**: sigue pendiente desde S27. Empieza a ser bloque grande; conviene partir en commits temáticos (refactor motor / tipología CAJA / radiación cámara / migración Plotly / mejoras UX P2 P6 / catálogo).
- **`t_max_s` configurable desde UI** (heredado S24 §44).
- **Repo GitHub público** (heredado S27).

---

## 77. Lecciones de proceso

### 77.1 El bug de capa fina (Mejora 16) es un anti-patrón conocido

`sets_por_temperatura` existía en el YAML desde sesiones anteriores pero el código sólo leía el top-level. Es el mismo patrón que el bool decorativo `cubierta_translucida` antes del refactor: **el dato existe en el modelo pero la lógica del cálculo lo ignora**, y nadie se da cuenta hasta que el usuario observa el síntoma (tiempo de secado constante).

Acción para el futuro: cuando se agrega un campo opcional a un YAML del catálogo, confirmar que al menos un test lo lee y verifica que cambia el resultado. Si no, el campo es decorativo.

### 77.2 Anclaje empírico antes de creer al modelo

Los tests de `test_motor_anclaje.py` se escribieron como regresión contra un número concreto del campo (Gatti 150, 76 W). Sin ese anclaje, el modelo se podía "validar" formalmente contra Darcy-Weisbach y aún así devolver P_eléctrica = 12 W para un secador que en la práctica consume 76. La cobertura física no garantiza realismo cuantitativo: hay que anclar contra mediciones reales del grupo.

### 77.3 Migración Plotly: el bug de add_vline + datetime

Plotly 6.x tiene un bug confirmado donde `add_vline(x=ts, annotation_text=...)` falla con `TypeError: unsupported operand type(s) for +` cuando x es Timestamp porque internamente computa el centro de la anotación con `sum([x, x])`. Workaround estable: separar shape de annotation (`_add_vline_datetime`). Mantener el helper hasta que arreglen el bug aguas arriba.
