# 01 · Emplazamiento — Recurso solar y clima del sitio

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: descarga NASA POWER, conversión a SI, política de huecos,
> y la transposición del recurso global horizontal (GHI) al plano del
> colector (POA) con sus ecuaciones, hipótesis y convenciones de ángulos.

---

## 1. Qué entrega esta pestaña

La pestaña **P2 (Emplazamiento)** convierte tres datos del usuario —**latitud,
longitud, altitud**— más la **orientación del colector** (pendiente β y acimut γ)
en una **serie climática horaria anual** lista para alimentar todos los motores
físicos aguas abajo. En particular produce:

- Series horarias en **SI estricto**: `T_amb_K`, `GHI_Wm2`, `DNI_Wm2`, `DHI_Wm2`,
  `WS_ms` (viento), `HR` (fracción 0–1), `presion_Pa`.
- La **irradiancia sobre plano inclinado y orientado (POA)**, que es la que
  realmente "ve" el colector, calculada por transposición de GHI/DNI/DHI.

La filosofía es: **el usuario solo pone lat/lon**; la misma fuente y librería
estándar de la industria fotovoltaica (NASA POWER + `pvlib`) hacen el resto.

---

## 2. Descarga de datos — NASA POWER vía `pvlib`

### 2.1 Fuente y librería

Los datos provienen del servicio **NASA POWER** (Prediction Of Worldwide Energy
Resources), reanálisis satelital con cobertura global en grilla de ~0.5°. La
descarga se hace con:   

```python
pvlib.iotools.get_nasa_power(latitude, longitude, start, end,
                             parameters=_PARAMETROS_NASA, map_variables=True)
```

`pvlib` arma la URL de la API, traduce los nombres de variables y devuelve un
`DataFrame` horario tz-aware más un diccionario de metadatos (incluye la
**altitud del punto de grilla**, que se embebe en el caché).

### 2.2 Variables solicitadas

```
ghi            ALLSKY_SFC_SW_DWN   [W/m²]   global horizontal
dni            ALLSKY_SFC_SW_DNI   [W/m²]   directa normal
dhi            ALLSKY_SFC_SW_DIFF  [W/m²]   difusa horizontal
temp_air       T2M                 [°C]     temperatura del aire a 2 m
wind_speed_2m  WS2M                [m/s]    viento a 2 m
RH2M           RH2M                [%]      humedad relativa a 2 m
PS             PS                  [kPa]    presión superficial
```

El período pedido es **el año calendario completo** (1-ene a 31-dic), es decir
**8760 horas**.

### 2.3 Conversión a SI (hecha en la capa de cálculo, no en `core/`)

```
T:  °C  → K        (+273.15)
P:  kPa → Pa       (×1000)
HR: %   → fracción (÷100)
GHI/DNI/DHI [W/m²] y viento [m/s]: sin conversión.
```

> **Regla de arquitectura:** la única conversión física de unidades del recurso
> ocurre aquí (`clima_calc.py`). De ahí en más todo circula en SI estricto por
> `core/` y `calculos/`.

### 2.4 Caché transparente

Para no golpear la API en cada corrida, el resultado se guarda en **parquet**
con clave **SHA-256 de `(lat, lon, año)`** (redondeados a 4 decimales). La
altitud del punto de grilla se embebe en los metadatos del parquet. Una segunda
corrida del mismo sitio/año lee del disco (instantáneo, sin red).

### 2.5 Política de huecos (calidad explícita, no silenciosa)

NASA POWER tiene ocasionales valores faltantes. La política es:

- Huecos de **≤ 3 h** consecutivas → **interpolación lineal en el tiempo**.
- Huecos de **> 3 h** → se **dejan como `NaN`**; el contador
  `CalidadClima.n_horas_bloqueadas > 0` le indica a la UI que debe pedirle una
  decisión al usuario.

El conteo de huecos originales, mayor hueco, horas interpoladas y horas
bloqueadas viaja en `CalidadClima`. **No se rellena en silencio.**

---

## 3. Del recurso global horizontal (GHI) al plano del colector (POA)

Este es el corazón físico de la pestaña. NASA POWER entrega el recurso sobre
**plano horizontal**; el colector está **inclinado** un ángulo β y **orientado**
con acimut γ. Hay que **transponer**.

### 3.1 Geometría solar (posición del Sol)

Para cada timestamp horario se calcula la posición solar con el algoritmo
**SPA (Solar Position Algorithm)** de `pvlib`:

```python
pvlib.solarposition.get_solarposition(times, latitude, longitude, altitude)
```

que devuelve el **cenital aparente** $\theta_z$ y el **acimut solar** $\gamma_s$.
SPA resuelve internamente, en función de `(lat, lon, fecha-hora)`:

- **Declinación solar** $\delta$ (varía con el día del año):
  $$\delta \approx 23.45^\circ \cdot \sin\!\left(360^\circ\,\frac{284 + n}{365}\right)$$
  con $n$ el día juliano.
- **Ángulo horario** $\omega$ (desde el mediodía solar verdadero, con ecuación
  del tiempo y corrección de longitud).
- **Cenital solar**:
  $$\cos\theta_z = \sin\phi\sin\delta + \cos\phi\cos\delta\cos\omega$$
  con $\phi$ la latitud.

> Secasol **no reimplementa** estas fórmulas: delega en SPA (precisión
> sub-grado, incluye refracción y ecuación del tiempo). El **tránsito solar**
> (mediodía verdadero) se calcula aparte con
> `solar_geometria.mediodia_solar_transit` (vía `sun_rise_set_transit_spa`)
> para elegir la hora representativa del día sin depender de `idxmax(GHI)`.

### 3.2 Ángulo de incidencia sobre el plano

El **ángulo de incidencia** $\theta_i$ entre el rayo directo y la normal del
plano inclinado (β, γ) es la magnitud clave de la componente directa:

$$
\cos\theta_i = \cos\theta_z\cos\beta
  + \sin\theta_z\sin\beta\cos(\gamma_s - \gamma)
$$

### 3.3 Transposición de Liu-Jordan (modelo isotrópico)

La irradiancia total sobre el plano (POA) se descompone en **tres
contribuciones** (modelo de Liu-Jordan, difuso isotrópico):

$$
\boxed{\,I_{POA} = \underbrace{I_b\,\cos\theta_i}_{\text{directa}}
  \;+\; \underbrace{I_d\,\frac{1+\cos\beta}{2}}_{\text{difusa de cielo}}
  \;+\; \underbrace{I\,\rho_g\,\frac{1-\cos\beta}{2}}_{\text{reflejada del suelo}}\,}
$$

donde:
- $I_b = \text{DNI}$ (directa normal), proyectada por $\cos\theta_i$.
- $I_d = \text{DHI}$ (difusa horizontal), atenuada por el **factor de vista del
  cielo** $(1+\cos\beta)/2$.
- $I = \text{GHI}$ (global horizontal), reflejada por el suelo con **albedo**
  $\rho_g$ y factor de vista $(1-\cos\beta)/2$.

El **albedo** $\rho_g$ es configurable (`Emplazamiento.albedo_suelo`, default
0.25; catálogo de albedos por tipo de superficie en
`calculos/catalogo_albedos.py`).

> Se usa el modelo **isotrópico** por simplicidad y coherencia entre P3 y el
> lazo natural transitorio. `pvlib` también soporta Hay-Davies, Reindl, Klucher,
> King y Perez; el parámetro `modelo_difuso` deja abierta la sustitución.

En código, las tres componentes las suma `pvlib.irradiance.get_total_irradiance`,
al que Secasol le pasa β (`pendiente_colector_deg`), γ ya convertido a
convención pvlib, la posición solar SPA, DNI/GHI/DHI y el albedo.

### 3.4 Hipótesis de la transposición

- **Cielo difuso isotrópico**: la difusa se reparte uniforme en la bóveda
  (subestima levemente la circumsolar; conservador para prediseño).
- **Suelo lambertiano** de albedo uniforme.
- **Cada hora se trata como cuasi-instantánea** a la posición solar del bin
  horario (resolución horaria de NASA POWER).
- **Fallback conservador**: si DNI o DHI faltan una hora dada, no se puede
  separar directa/difusa → se asume **POA = GHI** esa hora (subestima POA con
  β>0, pero evita propagar `NaN` al solver del colector). Valores negativos por
  artefacto numérico cerca del horizonte se **clipean a 0**.

---

## 4. Convención de ángulos (crítico — tres convenciones que no se mezclan)

El acimut tiene **tres convenciones** y mezclarlas es una fuente clásica de
errores de orientación. Centralizadas en `calculos/conversiones_angulo.py`
(matemática pura, sin estado), re-exportadas por `ui/componentes/unidades.py`:

| Convención | 0° | +90° | Rango | Uso |
|---|---|---|---|---|
| **Duffie & Beckman** | Sur | Oeste | [−180, +180] | almacenamiento interno (`core/emplazamiento.py`) y lógica de cálculo |
| **UI360** | (widget) | — | [0, 360) | entrada del usuario en P2 |
| **pvlib** | Norte | Este | [0, 360) | cálculo interno de irradiancia |

Conversión usada en la transposición POA:

$$\psi_{pvlib} = (180^\circ + \gamma_{Duffie}) \bmod 360^\circ$$

Verificación: γ=0° (Sur)→ψ=180° (Sur) ✓; γ=90° (Oeste)→ψ=270° ✓;
γ=−90° (Este)→ψ=90° ✓; γ=±180° (Norte)→ψ=0° ✓.

> La fórmula **vive en un solo lugar**. Nunca se duplica en otro módulo: tanto la
> UI como `clima_calc` la importan de `conversiones_angulo.py`.

---

## 5. Helpers temporales (modos de análisis)

`clima_calc.py` también provee los recortes de la serie anual que consumen los
distintos modos:

- **`dia_tipo_mensual(datos, mes, tz_local)`** — promedia hora a hora todos los
  registros de un mes → "día típico" de 24 h. Convierte a hora local antes de
  agrupar para que el pico solar caiga cerca de las 12 locales. Alimenta el modo
  **Anual** (un batch representativo por mes).
- **`slice_n_dias_consecutivos(...)`** — recorta N días reales consecutivos
  (modo multidía); si cruza el 31-dic, trunca y lo marca (`truncado=True`), sin
  inventar empalmes.
- **`slice_clima_ventana(clima, inicio, fin)`** — recorta el lapso `[inicio, fin]`
  mapeado al año de la serie. Compartido por P2, P3 y P7 (modo **Ventana**).

---

## 6. Highlights de implementación (a nivel código)

| Qué                                           | Dónde                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------------- |
| Descarga + caché + huecos + SI                | `calculos/clima_calc.py::obtener_clima`                                           |
| Lista de parámetros NASA                      | `clima_calc._PARAMETROS_NASA`                                                     |
| Política de huecos (≤3 h interpola, >3 h NaN) | `clima_calc._aplicar_politica_huecos`                                             |
| Clave de caché SHA-256 (lat, lon, año)        | `clima_calc._hash_cache`                                                          |
| **Transposición GHI/DNI/DHI → POA**           | `clima_calc.calcular_POA_horizonte`                                               |
| Posición solar (SPA)                          | `pvlib.solarposition.get_solarposition` (llamado en `calcular_POA_horizonte`)     |
| Transposición Liu-Jordan / isotrópico         | `pvlib.irradiance.get_total_irradiance`                                           |
| Mediodía solar verdadero (tránsito)           | `calculos/solar_geometria.py::mediodia_solar_transit`                             |
| Conversión de acimut Duffie→pvlib             | `calculos/conversiones_angulo.py::acimut_duffie_a_pvlib`                          |
| Día típico mensual / slices de ventana        | `clima_calc.dia_tipo_mensual`, `slice_clima_ventana`, `slice_n_dias_consecutivos` |
| Modelo de datos del clima                     | `core/clima.py` (`Clima`, `CalidadClima`, `COLUMNAS_SI`)                          |

**Puntos a destacar en la charla:**
1. *El usuario solo da lat/lon*: todo lo demás (8760 h, POA, conversiones) es
   automático y cacheado.
2. *Misma fuente y librería que la industria FV* (NASA POWER + pvlib) → rigor y
   reproducibilidad.
3. *Calidad de datos explícita*: los huecos no se tapan en silencio; el sistema
   avisa.
4. *Convenciones de ángulos centralizadas*: un solo lugar, verificado con casos
   de prueba (Sur/Este/Oeste/Norte).
5. *El colector recibe POA, no GHI* — esto vale en **todos** los pipelines (P3
   horario/diario, constantes, P7 transitorio y ventana).

---

## Referencias

- Duffie, J. & Beckman, W. *Solar Engineering of Thermal Processes* (geometría
  solar, transposición Liu-Jordan, factor de vista del cielo).
- Liu, B. & Jordan, R. (1963) — modelo isotrópico de difusa.
- Reda, I. & Andreas, A. — Solar Position Algorithm (SPA), base de
  `pvlib.solarposition`.
- NASA POWER — *Prediction Of Worldwide Energy Resources*, reanálisis MERRA-2.
- `pvlib-python` — librería estándar de modelado del recurso solar.
