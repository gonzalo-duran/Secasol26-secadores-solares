# Bitácora — Sesión 36 (2026-06-03)

**Tema:** Tres mejoras del modelo físico del colector y la cámara: (1) **albedo del suelo
seleccionable → POA** (componente solar reflejada), (2) **coeficiente convectivo interno LOCAL**
(h(x) con propiedades del aire variables + Nu de entrada + blending de régimen + convección mixta),
y (3) **modo multi-día: "repetir día típico" vs "días reales consecutivos"** del motor TD.

**Estado al cierre de la sesión:** Las tres features implementadas y verificadas end-to-end en
working tree. Suite **914 passed, 2 xfailed** (+29 respecto a S35: +9 albedo, +17 h local, +3
multi-día). Validación HWB OK con el nuevo criterio. Sin commitear (working tree puro, según
convención). Versión local bumpeada a **0.9.0**.

---

## 155. Albedo del suelo seleccionable → POA

**Motivación:** para colectores **inclinados/verticales** (frecuentes en el trabajo del usuario)
la componente de solar reflejado del suelo en la POA es significativa: el término
`GHI·ρ·(1−cos β)/2` vale `0.5·GHI·ρ` en vertical. El albedo `ρ` estaba **fijo en 0.25** (default
de pvlib) porque `calcular_POA_horizonte` no pasaba el argumento `albedo`.

**Aclaración física (con el usuario):** el albedo es onda corta (solar) y alimenta la POA, NO el
coeficiente radiativo IR (que usa emisividad del suelo, no albedo). Alcance: solo albedo → POA.

| Archivo | Cambio |
| :--- | :--- |
| `core/emplazamiento.py` | Nuevo campo `albedo_suelo: float = 0.25` + validación `EMPL_ALBEDO_INVALIDO` (rango [0,1]). Default = comportamiento histórico. |
| `calculos/clima_calc.py` | `calcular_POA_horizonte` pasa `albedo=emplazamiento.albedo_suelo` a `get_total_irradiance`. **Único cambio de consumidor** — todos los call-sites (P3, P4, P7, operación anual, transitorio) heredan el albedo porque pasan por esa función. |
| `calculos/catalogo_albedos.py` | **Nuevo.** Catálogo curado ES (Cemento 0.30, Suelo desnudo 0.17, Suelo con pasto 0.20, Pasto fresco 0.26, Arena 0.40, Urbano 0.18, Nieve 0.65) con valores de `pvlib.albedo.SURFACE_ALBEDOS` + helper `etiqueta_desde_albedo`. |
| `ui/p3_colector.py` | `_render_albedo_suelo`: selectbox de superficies + "Personalizado"; reconstruye el emplazamiento con `dataclasses.replace`. |
| `ui/p7_resultados.py`, `ui/reporte.py` | `albedo_suelo` en snapshot JSON/TXT y en la tabla del PDF. |

**Bug encontrado y corregido durante la verificación e2e (AppTest):** `ui/p2_emplazamiento.py`
reconstruía `Emplazamiento(...)` **campo por campo en cada rerun** (dos sitios), omitiendo el
campo nuevo → reseteaba `albedo_suelo` a 0.25 en cada interacción y la feature quedaba muerta.
Los unit tests no lo detectaban (llaman a `calcular_POA_horizonte` directo); solo apareció
corriendo la app. **Fix de raíz (decisión del usuario):** migrar ambas reconstrucciones a
`dataclasses.replace(empl, <solo lo que cambia>)`, que preserva todos los campos no tocados —
elimina la *clase entera* de bug (cualquier campo futuro de `Emplazamiento` se preserva solo).

**Verificación e2e (AppTest sobre `Secasol.py` real, clima de caché, tilt 30°):** POA diaria sube
de Σ=5680.6 (ρ=0.20) a 5885.9 W/m² (ρ=0.65), +3.61 %; persistencia del albedo tras reruns OK.

Tests (+9): `test_core/test_emplazamiento.py` (3), `test_calculos/test_clima_calc.py` (2 POA),
`test_calculos/test_catalogo_albedos.py` (4).

---

## 156. Coeficiente convectivo interno LOCAL (h(x))

**Motivación:** los motores de colector calculaban `h_int` **una sola vez** (escalar por canal
activo) con propiedades del aire **constantes a 323 K**. Limitaciones: en colectores largos a bajo
caudal (laminar) la longitud de entrada térmica es de 2–4 m pero el ruteo `L/Dh≥50 → Shah-London`
descartaba el realce de entrada (subestimaba h ~15–25 %); en baja velocidad/vertical el canal
trabaja en convección mixta-natural y se modelaba como forzado laminar `Nu=5.385`.

**Decisiones (con el usuario):** h(x) local completo; propiedades del aire vs T por polinomios;
blending suave de régimen; convección mixta incluida; validación HWB con piso laxo R²≥0.99 +
monotonía + parámetros (sin flag de propiedades constantes).

| Archivo | Cambio |
| :--- | :--- |
| `calculos/propiedades_aire.py` | **Nuevo.** `k(T), μ(T), Pr(T), cp(T)` (Sutherland + cp lineal + Pr derivado) y `ρ(T,P)` gas ideal. Reproducen los valores a 323 K dentro de 0.5 %. |
| `calculos/correlaciones_nusselt.py` | `nusselt_forzado_local` (entrada local consistente con Heaton/Cengel al promediar + blending continuo en Re=2300/10000), `nusselt_natural_canal` (Churchill-Chu), `nusselt_mixto_local` (Churchill `(Nu_f³+Nu_n³)^⅓`, flotación asistida). |
| `calculos/colector_calc.py` | Helper compartido `coef_conveccion_interna_local` (props a T_f(x) de película, Re local, Ra con `g·sin β` y ΔT del warm-start). Tipo 1: h y cp locales en RHS y reconstrucción; `ṁ` con `ρ(T_in)`; `h_int_medio`/`Re_medio` = promedios locales. |
| `calculos/colector_tipos234_calc.py` | `_h_local_canal` aplicado en los 3 RHS + 2 reconstrucciones (canal activo); el estanco mantiene Hollands local. Geometría por canal (Dh, A, pared) en `params`. |
| `validacion/validacion_hwb.py` | Piso `R²≥0.99` (era 0.95) + chequeo de monotonía (η↓ con x) + rangos `F_R·(τα)`/`F_R·U_L`. |

**Arquitectura:** `h_int` deja de ser escalar en `params`; se evalúa por nodo dentro del RHS con
`T_f(x)` y el warm-start de las temperaturas de superficie (mismo patrón que ya usaba el canal
estanco con Hollands). `_sistema_nodo` sigue recibiendo un `h` escalar — solo cambia su valor por
nodo. La radiación interna ya era local (full T⁴), no se tocó.

**Validación HWB:** con propiedades variables el R² baja de 1.0000 a **≈0.9997–0.9999** (los 4
casos pasan). La leve curvatura es física (HWB es una linealización de U_L constante); el R² alto
no es señal de buena física sino de parecerse a la idealización lineal — por eso el criterio pasó
a piso laxo + parámetros + monotonía.

**Verificación e2e (solver real, dos regímenes del usuario):**

| Régimen | Re | régimen | h_int_medio | T_sal | converge | perfil |
|---|---|---|---|---|---|---|
| 10 m/s, L=2.5 m | 30.300 | turbulento | 35.6 | 31.3 °C | ✓ | monótono |
| 10 m/s, L=10 m | 29.900 | turbulento | 34.9 | 43.3 °C | ✓ | monótono |
| 0.016 kg/s, L=2.5 m | 1.522 | laminar | 6.8 | 72.2 °C | ✓ | monótono |
| 0.016 kg/s, L=10 m | 1.459 | laminar | 6.3 | 106.5 °C | ✓ | monótono |

En laminar largo `h_int_medio`≈6.3 vs ~3.1 del viejo `Nu=5.385` constante (≈2×, por entrada +
mixta) — el objetivo de la mejora.

Tests (+17): `test_propiedades_aire.py` (5), `test_correlaciones_nusselt.py` (9 locales),
`test_colector_calc.py::TestCoefConveccionLocal` (3).

---

## 157. Modo multi-día: "repetir día típico" vs "días reales consecutivos"

**Motivación:** el horizonte Multi-día del motor termodinámico **replicaba N veces el día de
diseño** (`armar_forzantes_aire` hace `np.tile` de la serie de 24 h). La simulación es continua (el
producto arrastra `T_prod`/`X` entre días), pero el forzante meteorológico era el mismo día
repetido — no captura variabilidad real día a día. Se agregó la opción de tomar **N días calendario
reales consecutivos** del clima a partir del día de diseño.

**Decisiones (con el usuario):** selector visible **solo con forzantes "Día real"**; borde de año
(día de diseño + N cruza el 31-dic) → **recortar y avisar** (no se inventa empalme); flag en
`session_state` (sin tocar dataclasses del core).

| Archivo | Cambio |
| :--- | :--- |
| `calculos/clima_calc.py` | Nuevo `slice_n_dias_consecutivos(datos_local, fecha_inicio, n_dias) -> (slice, n_dias_efectivo, truncado)` — puro, trunca en el borde de año. |
| `ui/p4_camara.py` | Helpers `_resolver_fecha_dia` (dedup del mapeo `dia_analisis → fecha`) y `_forzantes_desde_slice` (arma forzantes de 24·N h **sin replicar**, por el camino `n_reps=1` de `armar_forzantes_aire`). Rama `dias_consecutivos` en los dos builders reales: CAJA (T_sal_col=T_amb) y ARMARIO (corre el colector hora a hora sobre el slice reusando `p3_colector._evaluar_diario`, sin depender de `p3_eval`). UI: `st.radio` "Repetir día típico"/"Días reales consecutivos" + `st.warning` si el recorte trunca. Meta con `horizonte_tipo` y `n_dias_efectivo`. |
| `ui/p7_resultados.py` | La métrica "Horizonte" muestra el tipo ("día típico repetido"/"días reales consecutivos"). |

**Costo/flujo:** el motor TD (lo caro) es idéntico — ambos modos simulan 24·N h. CAJA consecutivo
≈ costo cero; ARMARIO motor-eléctrico agrega correr el colector sobre N días reales (~segundos; con
chimenea ya se re-corre en Picard). `calcular_todo_transitorio` **no se tocó** (ya procesa horizontes
largos no periódicos).

**Verificación e2e (builders reales, clima de caché):** repetir → días idénticos; consecutivo →
días distintos; borde de año (30-dic + 5) → recorta a 2 días y avisa; ARMARIO consecutivo corre el
colector sobre días reales (T_ent_max ~70 °C).

Tests (+3): `test_clima_calc.py` (2: recorte normal + truncación de año),
`test_balance_global.py` (1: serie de 24·N sin replicar preserva días distintos).

---

## 158. Pendiente para siguientes sesiones

- **Convección mixta/natural vertical en el canal**: se incluyó la combinación de Churchill, pero
  el supuesto es flotación **asistida** (flujo ascendente). Validar para casos de flujo opuesto.
- **Refinamientos radiativos** (separados, NO en esta tanda): factor de forma cielo/suelo IR para
  colectores verticales/inclinados, y transmisión IR de cubiertas plásticas.
- **Multi-día**: el selector repetir/consecutivos aplica solo al forzante "Día real". Variabilidad
  día a día del **sintético** queda fuera de alcance. La elección no se persiste en el snapshot JSON
  (vive en `session_state`, como `cam_n_dias`).
- Heredados: modo industrial (`GRAN_ESCALA`) — único pendiente de la hoja de ruta a 1.0;
  validación cruzada motor TD vs capa fina; poblar catálogo de productos.
- Etiqueta de sesión "S36" usada en docstrings/docs; ajustar si difiere la numeración.
