# Plan — cross-flow único en la cámara de secado

**Origen:** S64. Revisión crítica de la topología de transferencia que introdujo S63.
**Decisión:** eliminar el through-flow (`VERTICAL_ASCENDENTE`) y dejar **cross-flow como única
topología** de la cámara de secado.

---

## 1. Contexto: por qué se revierte una decisión de la sesión anterior

S63 le dio a la cámara dos topologías de transferencia despachadas por
`flujo.direccion_flujo`, en paridad con lo que `motor_calc` ya hacía para la pérdida de carga:

- `HORIZONTAL` → over-flow: el aire pasa **entre** bandejas. `A = n·A_bandeja`, placa plana.
- `VERTICAL_ASCENDENTE` → through-flow: el aire **atraviesa** el lecho.
  `A = a_v·V_lecho` con `a_v = 6(1−ε)/(Φ_s·d_p)`, y `h` por Ranz-Marshall.

El cambio movió el caso de referencia 11× (154 h → 13.55 h). El análisis de S64 encontró tres
problemas encadenados.

### 1.1 El par `(d_p, Φ_s)` del catálogo es internamente inconsistente

En **las dos** fórmulas, `d_p` y `Φ_s` nunca aparecen por separado. `motor_calc.py:390` usa
`phi_dp = phi_s * d_p`, y `area_especifica_lecho_m2_m3` lo usa en el denominador. Ese producto
es el **diámetro de Sauter** `d_sv = 6·V_partícula/S_partícula`, que es una propiedad medible
de la partícula, no dos perillas independientes.

`catalogo/productos/frutas.yaml:94` declara `diametro_eq_m: 0.006` (el **espesor** de la rodaja,
con una nota que lo justifica *"para Ergun lo relevante es la dimensión normal al flujo"*) y
`esfericidad: 0.6`. Producto: `d_sv = 3.6 mm`. Pero `Φ_s = 0.6` **es** la esfericidad de la
rodaja, y esa esfericidad solo es consistente con el diámetro de la esfera equivalente en
volumen. Se aplica la corrección de forma dos veces.

| geometría de rodaja | d_vol | Φ_real | **d_sv** | a_v real | a_v del modelo | error |
|---|---|---|---|---|---|---|
| D=50 mm, e=6 mm | 28.2 mm | 0.514 | **14.5 mm** | 227 m²/m³ | 917 m²/m³ | **4.03×** |
| D=40 mm, e=6 mm | 24.3 mm | 0.569 | **13.9 mm** | 238 m²/m³ | 917 m²/m³ | 3.85× |

Propagación al armario de referencia (10 bandejas 0.25 m², capa 2 cm):

| | modelo S63 | con `d_sv` real |
|---|---|---|
| A_prod | 45.8 m² | 11.4 m² |
| h | 24.6 W/m²K | 13.8 W/m²K |
| NTU | 35.5 | 4.9 |
| ΔP del lecho, 10 bandejas | **31.6 Pa** | **4.0 Pa** (viscoso 20.4 → 1.25 Pa, 16×) |

### 1.2 Con ese número el through-flow pasivo es imposible — y el modelo se autorefuta

Presión motriz de un armario pasivo: `Δp_stack = ρ·g·H·(ΔT/T) ≈ 1.0·9.81·2·(20/300) ≈ 1.3 Pa`.
El modelo cobra **31.6 Pa** por atravesar el lecho: 24× la presión disponible. Es decir, el
modelo afirma que un armario ascendente pasivo no puede mover aire. Los armarios ascendentes
pasivos existen y funcionan (observación de campo del usuario), así que el número está mal.

Con el `d_sv` geométricamente correcto el balance cierra al filo (1.25 Pa viscosos contra 1.3
disponibles), que es exactamente cómo son estos secadores: lentos, capas finas, pocas bandejas.
De ahí se sigue que en un secador pasivo el aire **no percola al 100 %**: se reparte entre el
camino que atraviesa y el que rodea (perímetro de bandeja, canales, recirculación).

### 1.3 El resultado dejó de depender del modelo del lecho

A NTU 32 el aire sale saturado. Dividir NTU por 16 lo deja en 2.0, que aún da 86 % de
acercamiento al equilibrio. Consecuencias:

- El número que S63 produjo (13.55 h) **no lo produjo Ranz-Marshall**; lo produjo cruzar el
  umbral de saturación. Cualquier correlación con NTU ≳ 3 daba lo mismo.
- El diagnóstico `diagnostico_transferencia` dice *"limitado por energía"* en todo secador
  vertical razonable: nace sin poder discriminar diseños.
- Como prediseñador, en vertical el modelo dejó de responder a espesor de capa, número de
  bandejas y tamaño de partícula.

### 1.4 La decisión

En un prediseñador, **la dirección local del flujo sobre el producto no es algo que el usuario
pueda responder con confianza**, y la disposición real de bocas en CAJA/ARMARIO —entrada en el
extremo inferior de una cara, salida en el extremo superior de la cara opuesta— es *cross
ventilation con displacement flow*: el flujo **global** es diagonal ascendente, pero **local
sobre la bandeja es cross-flow**. En túnel batch el flujo es horizontal directamente.

> La posición de las aberturas fija la **escala** del flujo; la disposición de las bandejas fija
> la **dirección local** sobre el producto. Son dos problemas separados y la literatura los
> trata por separado.

Fijar cross-flow con carga uniforme convierte el área de transferencia en un escalar limpio,
elimina un parámetro que el usuario no puede responder, y es coherente con el modelo de **nodo
único** que tienen todas las cámaras salvo el túnel semicontinuo (que ya usa `simular_cascada`
con N zonas y no se toca).

---

## 2. Física del modelo

### 2.1 Qué captura

- **Cross-flow sobre bandeja**: el aire barre paralelo a la superficie libre del lecho.
  `h` por convección **mixta transversal** (`coef_conveccion_producto_local`): forzada de placa
  plana sobre el largo de cámara + natural de placa horizontal con `L = A_s/P`, combinadas con
  `n = 7/2` (Incropera Ec. 9.64) porque forzada y empuje son perpendiculares. La rama natural la
  decide el signo de ΔT (rama débil 9.32 con el aire más caliente; fuerte 9.30/9.31 con el
  producto más caliente). **Esto ya existe y no se toca.**
- **Velocidad del canal**: `v = ṁ/(ρ·ancho·espacio_libre·(n−1))`, la misma sección que usa
  `motor_calc` para ΔP (unificada en S63).
- **Las dos caras de la bandeja**: el aire circula por encima y por debajo. Cota superior 2× el
  área superior, reducida por el área abierta de la malla y por el peor desempeño de la cara
  inferior.
- **Aire estratificado en 8 sub-etapas en serie** (`_N_ETAPAS_OVERFLOW`): el canal es un
  intercambiador continuo. Con N = 1 reproduce el CSTR exactamente.
- **Chilton-Colburn** (`K_m = h/(cp·Le^{2/3})`) preserva que el producto se pare en el bulbo
  húmedo y que el aire siga la adiabática cuando la cámara es adiabática.
- **Carga uniforme**: masa, área, número de bandejas y espesor quedan acoplados por una única
  ecuación, y el espesor pasa a ser la variable derivada.

### 2.2 Qué NO captura

- **La percolación parcial.** El aire real de un armario ascendente atraviesa *algo* de lecho.
  Modelarlo bien exige un reparto de caudal entre caminos paralelos resuelto por igualdad de
  Δp (§7.2, trabajo futuro). Este plan adopta la cota "todo el aire rodea", que para el pasivo
  es la más cercana a la realidad y para el forzado es una subestimación deliberada.
- **La resistencia interna a la difusión.** El motor termodinámico no la tiene: `a_w` depende de
  `X` solo por GAB. Es el límite dominante del modelo y la razón del guardarraíl de la etapa 4.
- **El signo real del empuje en la cara inferior.** Se adopta un factor fijo (§2.4). El
  tratamiento correcto requiere el empuje solutal, ver §2.3.
- **Gradientes espaciales dentro de la cámara.** El producto sigue siendo un nodo único: la
  bandeja de abajo y la de arriba comparten `X` y `T_prod`. El aire sí se estratifica (8
  etapas). Es coherente con lo que declara el proyecto para CAJA/ARMARIO/túnel batch.
- **Encogimiento del producto.** `ε` y el volumen del lecho se mantienen constantes.

### 2.3 El empuje solutal — límite declarado de la cara inferior

El mecanismo que motiva tratar peor la cara inferior es real: una superficie que evapora hacia
abajo libera aire húmedo, que es **más liviano** que el aire seco a igual temperatura
(M_agua = 18 vs M_aire = 29), queda atrapado contra la cara en estratificación estable y suprime
la transferencia de masa. Con `v` de 0.1–0.5 m/s la advección no alcanza a barrerlo.

Pero ese empuje **compite con el térmico** y el signo neto se invierte. Con
`Δρ/ρ ≈ −ΔT/T − 0.59·Δω` (coeficiente solutal exacto: `∂lnρ/∂ω = 1/(1+ω) − 1.608/(1+1.608ω)`):

| caso | T_aire | T_prod | Δρ/ρ de la película | cara inferior |
|---|---|---|---|---|
| armario indirecto, producto en bulbo húmedo | 51 °C | 21 °C | **+0.091** | inestable → **favorece** |
| cerca del equilibrio | 27 °C | 25 °C | +0.003 | inestable (marginal) |
| caja directa, producto insolado | 40 °C | **50 °C** | **−0.081** | estable → **suprime** |

Cruce en |ΔT| ≈ 2.2 K. Con el producto por debajo del aire —armario indirecto, que es el caso
más común— la película de abajo se enfría más de lo que se humedece, resulta **más pesada**,
drena y la rama es la fuerte. El mecanismo descrito domina cuando el producto está **más
caliente** que el aire: CAJA con techo translúcido y producto insolado.

`camara_calc._rayleigh` documenta explícitamente que solo implementa el empuje térmico y que el
solutal (Incropera Ec. 9.65) es refinamiento pendiente; figura como decisión cerrada *"empuje
por humedad: fuera de v1"*. **Este plan no lo implementa**: se adopta el factor fijo y el límite
queda declarado en el docstring.

### 2.4 Anclaje del factor de cara inferior

`φ_inf = 0.5` no es un número inventado: es el cociente entre la rama débil y la fuerte de
`correlaciones_nusselt.nusselt_placa_horizontal` en el rango de Ra de una bandeja
(`L = A_s/P ≈ 0.125 m`, ΔT 10–30 K ⇒ Ra ~1e5–1e7):

| Ra | Nu fuerte | Nu débil | débil/fuerte |
|---|---|---|---|
| 1e4 | 5.40 | 3.28 | 0.608 |
| 1e5 | 9.60 | 5.20 | 0.542 |
| 1e6 | 17.08 | 8.24 | 0.483 |
| 1e7 | 32.32 | 13.06 | 0.404 |

Coincide con el "la mitad o menos" de Incropera para placa caliente mirando hacia abajo.

---

## 3. Inventario de objetos

### 3.1 Se ELIMINAN

| Objeto | Archivo | Por qué |
|---|---|---|
| `es_flujo_atravesado()` | `calculos/camara_calc.py:290` | Único consumidor de la binaria de topología |
| rama `if atravesado:` de `_construir_params_termodinamico` | `calculos/camara_calc.py:584-636` | Área de lecho + sus 3 advertencias |
| `_FRACCION_HUELLA_MIN` | `calculos/camara_calc.py:123` | Solo lo usa `CAM_LECHO_BYPASS` |
| `_FACTOR_CARGA_COHERENTE` | `calculos/camara_calc.py:126` | La incoherencia pasa a ser imposible (§5.3) |
| advertencias `CAM_LECHO_BYPASS`, `CAM_LECHO_DEGENERADO`, `CAM_LECHO_CARGA_INCOHERENTE` | `calculos/camara_calc.py` | Todas eran del camino atravesado |
| `area_especifica_lecho_m2_m3()` | `calculos/lecho_producto.py:105` | Solo la usaba `area_transferencia_lecho_m2` |
| `area_transferencia_lecho_m2()` | `calculos/lecho_producto.py:125` | Área de partícula, sin consumidor |
| `h_conv_lecho()` (Ranz-Marshall) | `calculos/lecho_producto.py:171` | Sin consumidor |
| `_delta_P_lecho_por_bandeja()` (Ergun) | `calculos/motor_calc.py:353` | Sin consumidor |
| `K_TRANSICION_LECHO` | `calculos/motor_calc.py:403` | Contracción/expansión de entrada al lecho |
| despacho `if direccion == VERTICAL_ASCENDENTE` | `calculos/motor_calc.py:567-572` | Rama muerta |
| selectbox de dirección de flujo (`_dir_keys`, `_dir_enum`) | `ui/p4_camara.py:2971-2983` | El usuario deja de elegir |
| claves `p4.flujo.direccion.*` | `ui/idiomas/{es,en,pt}/p4.yaml:255-258` | Widget eliminado (los 3 idiomas) |

### 3.2 Se CREAN

| Objeto | Archivo | Rol |
|---|---|---|
| `AREA_ABIERTA_MALLA: dict[str, float]` | `calculos/motor_calc.py` | Fracción de área abierta por tipo de malla. **Mismas claves** que `TIPOS_MALLA` |
| `_area_abierta_efectiva(tipo_malla)` | `calculos/motor_calc.py` | Lookup calcado de `_K_malla_efectivo:80` |
| `_FACTOR_CARA_INFERIOR: float = 0.5` | `calculos/camara_calc.py` | Anclado en §2.4 |
| `espesor_capa_derivado_m(...)` | `calculos/lecho_producto.py` | Inversa exacta de `masa_que_llena_el_lecho_kg` |
| error `CAM_CAPA_CIERRA_EL_CANAL` | `core/camara.py` | Guarda: espesor ≥ separación |
| advertencia `CAM_ESPESOR_FUERA_DE_VALIDEZ` | `core/camara.py::advertencias_camara` | Guardarraíl de difusión interna |
| `espesor_ensayo_m` | `catalogo/productos/*.yaml` | Junto a `forma_geometrica` |
| entrada `separacion_entre_bandejas_m` | `calculos/catalogo_parametros_barrido.py` | Habilita el barrido del óptimo (etapa 5) |

### 3.3 Se MODIFICAN

| Objeto | Archivo | Cambio |
|---|---|---|
| `ConfiguracionFlujo.__post_init__` | `core/camara.py:663` | Coacciona `VERTICAL_ASCENDENTE` → `HORIZONTAL` en vez de aceptarlo |
| `Camara.__post_init__` | `core/camara.py` | Deriva `bandejas.espesor_capa_m` de la carga (§5.3) |
| `advertencias_camara` (`tipo_malla is None`) | `core/camara.py:1235` | La malla ahora también gatea el **área**, no solo ΔP |
| `area_transversal_flujo_m2()` | `calculos/camara_calc.py:233` | Colapsa a `ancho × alto`; sigue sirviendo al film de pared |
| `_h_producto` (closure) | `calculos/camara_calc.py:678` | Una sola rama; sin `if atravesado` |
| cálculo de `A_prod` | `calculos/camara_calc.py:637-639` | `n·A_bandeja·(1 + f_abierta·φ_inf)` |
| `n_etapas_aire` | `calculos/camara_calc.py:650` | Siempre `_N_ETAPAS_OVERFLOW` |
| `estimar_delta_P_camara()` | `calculos/motor_calc.py:512` | Sin despacho; solo cross-flow |
| docstring de módulo | `calculos/lecho_producto.py:1-20` | De "lecho atravesado" a "rugosidad de canal + carga uniforme" |
| deserialización de flujo | `ui/p4_camara.py:1554` | Coacciona **con aviso visible** |
| input de espesor de capa | `ui/p4_camara.py` | De `number_input` a métrica derivada de solo lectura |
| help que menciona Ergun | `ui/idiomas/{es,en,pt}/p4.yaml:183-184` | Reescrito |

### 3.4 Se CONSERVA (y por qué)

| Objeto | Razón |
|---|---|
| `DireccionFlujo.VERTICAL_ASCENDENTE` (miembro del enum) | Los `.json` guardados lo traen; tiene que deserializar antes de coaccionarse. Precedente: `modo_calculo="capa_fina"` sobrevive en el enum y se coacciona en `Camara.__post_init__` desde S38 |
| `geometria_lecho()`, `d_p_es_default()` | `d_p` sigue vivo como **altura de rugosidad** del canal en `_delta_P_producto_crossflow` (`ε_eff = max(ε_chapa, d_p)`) |
| `volumen_lecho_m3()`, `masa_que_llena_el_lecho_kg()` | Son la restricción de carga uniforme (§5.3) |
| `area_canal_entre_bandejas_m2()` | Es la sección de referencia única del cross-flow |
| `coef_conveccion_producto_local()`, `_rayleigh()`, `nusselt_placa_horizontal()` | El modelo de transferencia que queda |
| `chimenea_calc.caudal_natural_kgs()` | El motor de tiro térmico **ya existe** (S61, `brentq`), con `H_camara_m = geometria.alto_m` (`balance_global.py:867,1039`), que es exactamente la geometría de bocas en los extremos |
| `simular_cascada()` | Es el túnel semicontinuo; fuera de alcance |

### 3.5 Queda VESTIGIAL (consecuencia no obvia)

**`esfericidad` (Φ_s) se queda sin ningún consumidor.** Después del cambio:

| campo del lecho | consumidor que sobrevive |
|---|---|
| `d_p` (`diametro_eq_particula_m`) | rugosidad de canal en `_delta_P_producto_crossflow` |
| `ε` (`porosidad_lecho`) | restricción `m = ρ·(1−ε)·V` |
| **`Φ_s` (`esfericidad`)** | **ninguno** — solo aparecía en `Φ_s·d_p` de Ergun y `a_v` |

Se conserva el campo en `ConfiguracionBandejas` y en el catálogo (back-compat de snapshots y
posible reactivación futura), documentado como vestigial en el mismo registro que
`modelo_capa_fina`.

**Efecto lateral positivo:** con `Φ_s` fuera de juego, la inconsistencia del `d_sv` (§1.1) deja
de tener consecuencias. El único uso que le queda a `d_p` es como altura de rugosidad, y ahí
*"la dimensión normal al flujo"* —la lectura que el catálogo ya declara— **es la correcta**. No
hace falta tocar el catálogo.

---

### 3.6 Correcciones al inventario, encontradas al implementar (S64)

| Lo que decía el plan | Lo que resultó |
|---|---|
| La clase de flujo es `FlujoAire` | Es **`ConfiguracionFlujo`** |
| `AREA_ABIERTA_MALLA` va en `motor_calc.py` | Va en **`lecho_producto.py`**: es geometría de bandeja compartida por ΔP y transferencia, igual que `geometria_lecho`. Ponerla en `motor_calc` obligaba a `camara_calc → motor_calc`, una dependencia nueva que el módulo hoja evita. `TIPOS_MALLA` (el K de ΔP) se queda en `motor_calc` |
| Crear el error `CAM_CAPA_CIERRA_EL_CANAL` | **Ya existe** `BAND_SEPARACION_INSUFICIENTE` en `ConfiguracionBandejas.__post_init__`, que exige 1 cm de margen entre la capa y la bandeja de arriba. El fallback de `area_canal_entre_bandejas_m2` por espacio libre nulo es **inalcanzable**; el único camino vivo es `n_bandejas = 1`. Con el espesor derivado (etapa 3) hay que revisar que el mensaje sea legible cuando el que se pasa es el valor calculado, no uno tipeado |
| La restricción masa↔geometría no existe | **Existe parcialmente**: `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA` corta en 20 kg/m²/bandeja. Es un tope plano, no la relación física `ρ·(1−ε)·e`; la etapa 3 lo refina en vez de crearlo de cero. Su mensaje todavía dice *"máximo para capa fina"*, encuadre vestigial de S38 |

**Se retiró además `DiagnosticoTransferencia.atravesado`** (el campo describía la binaria) y se
corrigió `acercamiento_equilibrio`, que calculaba `NTU/(1+NTU)` —el CSTR— cuando el motor
integra la **cadena de N etapas** desde S63. Ahora usa `1 − (1 + NTU/N)^(−N)`. Era una
inconsistencia entre el diagnóstico y el modelo que quedó de la etapa 4 de S63.

### 3.7 Correcciones de la segunda tanda (etapas 2 y 3 implementadas)

| Lo que decía el plan | Lo que resultó |
|---|---|
| `espesor_capa_derivado_m` va en `calculos/lecho_producto.py` | El módulo **entero se mudó a `core/lecho.py`**. `Camara.__post_init__` lo necesita y habría sido el **primer `core → calculos`** del proyecto: una inversión de capas. `calculos/lecho_producto.py` quedó como shim de re-export, mismo patrón que `PoliticaRecarga` en `simulacion_ventana` |
| La etapa 4 crea el guardarraíl de espesor | **`BAND_ESPESOR_CAPA_GRANDE` ya existe** en `advertencias_camara`, con la física escrita (*"en lechos gruesos la resistencia interna a la difusión crece"*). Solo falta el refinamiento por producto (`espesor_ensayo_m`) en vez del umbral global de 5 cm |
| `BAND_SEPARACION_INSUFICIENTE` se conserva tal cual | Hubo que **relajarlo**: con el espesor derivado volvía inconstruible el proyecto industrial (120 bandejas, 4 cm de separación, capa de 3.5 cm). Ahora solo rechaza `espesor ≥ separación`; el margen de 1 cm es la advertencia nueva `CAM_CANAL_MUY_ESTRECHO` |
| La derivación corre antes de `_validar_coherencia` | Corre **después**: una sobrecarga grosera la diagnostica mejor `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA` (20 kg/m²) que el espesor que resultaría |

**Acoplamiento no obvio entre dos umbrales que estaban puestos por separado.** Con el tope de
20 kg/m² de `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA`, el espesor máximo alcanzable es
`20/(ρ·(1−ε))`. Para manzana (840 kg/m³) son **4.3 cm**, así que `BAND_ESPESOR_CAPA_GRANDE`
(umbral 5 cm) **nunca puede dispararse**; para orégano (350 kg/m³) son 10.4 cm y sí. Cualquier
ajuste de uno de los dos umbrales tiene que mirar al otro.

### 3.8 Hallazgo físico colateral: el encadenado inmediato no es cota superior

Lo destapó `test_ventana_glue` al fallar. Con lotes de ~100 h en vez de ~13 h, la **alineación
con el sol** pasa a mandar: un lote que arranca a las 3 de la mañana se pasa la noche sin secar
y no cierra dentro de la ventana. Medido en 6 días: **con espera 24 kg secos, sin espera
12 kg** —dos lotes contra uno— con la **misma agua evaporada** (~56 kg). No cambia cuánto se
seca, cambia cuántos lotes cierran.

Estaba escrito como verdad en `CLAUDE.md` y en el docstring de `simulacion_ventana.py` desde
S57. Los dos corregidos. **Corolario:** la política de recarga dejó de ser una restricción
operativa y pasó a ser una decisión de diseño que puede mejorar la producción.

---

## 4. Mapa de interrelaciones

```
core/camara.py
  FlujoAire.__post_init__ ──coacciona──> DireccionFlujo.HORIZONTAL
  Camara.__post_init__ ──deriva──> bandejas.espesor_capa_m
        │                            │
        │                            ├─> camara_calc.area_canal_entre_bandejas_m2
        │                            │        (espacio_libre = separacion − espesor)
        │                            ├─> motor_calc._delta_P_producto_crossflow (β = espesor/sep)
        │                            └─> lecho_producto.volumen_lecho_m3
        │
        └─> advertencias_camara ──> CAM_ESPESOR_FUERA_DE_VALIDEZ, tipo_malla

calculos/camara_calc.py::_construir_params_termodinamico
        ├─ A_prod = n·A_bandeja·(1 + f_abierta·φ_inf)
        │            └── motor_calc._area_abierta_efectiva(tipo_malla)
        ├─ _h_producto ──> coef_conveccion_producto_local (mixta 9.64)
        │                      └── _rayleigh (solo térmico — límite §2.3)
        ├─ n_etapas_aire = _N_ETAPAS_OVERFLOW
        └─ area_transversal_flujo_m2 ──> film de pared (coef_conveccion_pared_local)

camara_termodinamica.simular_secado
        └─ resolver_cadena_camara(N etapas) ──> resolver_estado_camara

motor_calc.estimar_delta_P_camara (solo cross-flow)
        └─> chimenea_calc.caudal_natural_kgs (delta_P_resto_fn)
                └─> balance_global._caudal_natural_loop / _caudal_natural_horizonte
                        └─ H_camara_m = geometria.alto_m   [tiro = bocas en los extremos]

barrido_parametrico.aplicar_parametro ──_set_campo_via_replace──> re-dispara __post_init__
        └─ por eso la derivación del espesor DEBE vivir en core/, no en la UI
```

**El lazo crítico** que este cambio toca de forma indirecta: `ΔP_cámara → ṁ_natural → v_canal →
h → evaporación → T_flujo → tiro térmico → ṁ_natural`. Al desaparecer el ΔP de Ergun (31.6 Pa
en el caso vertical), el caudal natural sube y el lazo se relaja. Es el lazo cuyo posible
colapso quedó abierto en el análisis (§7.3).

---

## 5. Etapas

### Etapa 1 — anular el through-flow

1. `core/camara.py`: `FlujoAire.__post_init__` coacciona en vez de validar contra la lista.
2. `ui/p4_camara.py:1554`: la deserialización detecta `VERTICAL_ASCENDENTE` en el `.json`
   **antes** de construir el objeto y emite `st.warning` explicando la migración. Después del
   `__post_init__` la información se pierde, así que el aviso tiene que salir de la capa de
   carga.
3. Borrar lo listado en §3.1 de `camara_calc.py`, `motor_calc.py`, `lecho_producto.py`.
4. `ui/p4_camara.py`: quitar el selectbox; `direccion=DireccionFlujo.HORIZONTAL` fijo.
5. i18n: borrar `p4.flujo.direccion.*` y reescribir el help de `:183-184` **en los tres YAML en
   el mismo cambio** (los tests exigen paridad de claves).

### Etapa 2 — la segunda cara de la bandeja

1. `AREA_ABIERTA_MALLA` en `motor_calc.py`, mismas claves que `TIPOS_MALLA:65`:
   `alambre_fino`, `alambre_grueso`, `chapa_perforada_50pc` (0.50), `chapa_perforada_30pc`
   (0.30), `tela_metalica_densa`. Default 0.5 cuando `tipo_malla is None` (paralelo a
   `K_MALLA:77`).
2. `_FACTOR_CARA_INFERIOR = 0.5` en `camara_calc.py`, con la tabla de §2.4 en el comentario.
3. `A_prod = b.n_bandejas * b.area_bandeja_m2 * (1 + f_abierta * _FACTOR_CARA_INFERIOR)`.
4. Docstring con el límite de §2.3 (inversión de signo del empuje neto).
5. Extender la advertencia de `tipo_malla is None` (`core/camara.py:1235`).

### Etapa 3 — carga uniforme: el espesor se deriva

`m = ρ_material · (1−ε) · A_bandeja · n_bandejas · espesor`

> **Cuidado con el `(1−ε)`.** `densidad_aparente` del catálogo es densidad de **material**
> (manzana 840 kg/m³, ASHRAE Ch.19, `frutas_v0.1_manzana.yaml:56`), no densidad de lecho, pese
> al nombre. Sin el `(1−ε)` el resultado se va ~2.2× (42 kg en vez de 23.1 kg para el caso de
> referencia). `masa_que_llena_el_lecho_kg:146` ya lo hace bien.

1. `espesor_capa_derivado_m(masa_kg, area_bandeja_m2, n_bandejas, densidad_kg_m3, porosidad)` en
   `lecho_producto.py`.
2. `Camara.__post_init__` la aplica cuando hay `carga_producto` con densidad conocida.
   **Tiene que vivir en `core/`, no en P4:** `barrido_parametrico` ya puede variar
   `camara.carga_producto.masa_total_kg` y `camara.bandejas.area_bandeja_m2`
   (`catalogo_parametros_barrido.py:269,285`) mutando vía `dataclasses.replace`, que re-dispara
   `__post_init__`. Derivarlo solo en la UI dejaría el barrido con un espesor viejo — es la
   cuarta reaparición del patrón "reconstruir campo por campo pierde en silencio".
3. Guarda `CAM_CAPA_CIERRA_EL_CANAL` si `espesor ≥ separacion_entre_bandejas_m`. Hoy ese caso
   hace que `area_canal_entre_bandejas_m2:285` caiga al fallback y que `estimar_delta_P_camara`
   devuelva `0.0` en silencio (`motor_calc.py:593`).
4. P4: el espesor pasa a `st.metric` de solo lectura. Si no hay producto cargado se mantiene el
   input manual (camino de fallback).

### Etapa 4 — guardarraíl de espesor

> **Reencuadre necesario respecto de la formulación original.** La justificación no puede ser la
> validez de la cinética de capa fina: ese motor se **eliminó en S38** y `modelo_capa_fina` es
> vestigial puro — nadie lo lee para calcular. (Ojo: los bloques `capa_fina:` del catálogo **no**
> son inertes, `_modelos_disponibles()` los usa para filtrar el selector de productos de P4.)
> La razón real es que el motor termodinámico **no tiene resistencia interna a la difusión**:
> por encima de cierto espesor el tiempo de secado es una cota inferior cada vez más optimista.

1. `espesor_ensayo_m` en `catalogo/productos/*.yaml`, junto a `forma_geometrica`, con la fuente
   del paper de cinética de cada producto (están en `docs/notas/papers/`).
2. `CAM_ESPESOR_FUERA_DE_VALIDEZ` en `advertencias_camara`, con plantilla en los tres YAML del
   namespace `advertencias.*`.

### Etapa 5 — el óptimo de espaciado (subproducto, opcional)

Con cross-flow fijo, el espaciado entra en `h` de forma directa vía la velocidad del canal; en
modo natural entra **dos veces con signos opuestos**: menos espaciado → más `v` → más `h`, pero
más ΔP → menos ṁ por `caudal_natural_kgs`. El óptimo es computable **hoy** —el motor de tiro ya
existe— y falta solo registrar `camara.bandejas.separacion_entre_bandejas_m` en
`catalogo_parametros_barrido.py`, una entrada con el mismo patrón que la de `:285`.

---

## 5.6 Estado de implementación (cierre de S64)

| Etapa | Estado |
|---|---|
| 1 — anular el through-flow | ✅ hecha |
| 2 — la segunda cara de la bandeja | ✅ hecha |
| 3 — carga uniforme, espesor derivado | ✅ hecha |
| 4 — guardarraíl de espesor | ⚠️ el grueso ya existía (`BAND_ESPESOR_CAPA_GRANDE`); falta `espesor_ensayo_m` por producto |
| 5 — óptimo de espaciado | ✅ parámetro registrado en `catalogo_parametros_barrido.py` |

**Suite 1978 passed + 2 skips**, ruff/black/`auditar_i18n` limpios. Los **7 snapshots `.json`**
del repo cargan, migran y calculan; los tres que traían `VERTICAL_ASCENDENTE` pasan a
cross-flow con aviso. **El lazo de tiro no colapsa** (§7.3): Picard converge en 4–6 iteraciones
y `T_flujo` queda entre 29.9 y 60.3 °C contra 20 °C ambiente — era un fenómeno de NTU alto, así
que retirar el through-flow lo elimina.

Medido sobre los snapshots: el espesor derivado da **0.61–0.87 cm** donde todos declaraban
~2 cm, y el ΔP de cámara queda entre **0.000 y 0.031 Pa** en los siete.

**Costo de suite:** 11 min 45 s, de los cuales **314 s (44 %) se los lleva
`test_barrido_parametrico::test_correr_barrido_anual`** — no es patológico, es un barrido anual
con lotes que ahora integran ~8× más horizonte. Si molesta el tiempo de iteración, la salida es
marcarlo `@pytest.mark.slow` y excluirlo del hook de `PostToolUse`, como ya se hace con
`i18n_paridad`.

---

## 6. Regresiones esperadas

- **Los tres proyectos con `VERTICAL_ASCENDENTE` cambian de resultado**, y mucho. El armario de
  referencia vuelve de 13.55 h al orden de 100 h (cross-flow con las dos caras queda por encima
  de las 154 h pre-S63, pero del mismo orden).
- **Todo proyecto HORIZONTAL cambia** por el área de la segunda cara: `A` sube ~1.25–1.3× con
  malla de 50–60 % de área abierta, `NTU` en la misma proporción.
- **Todo proyecto con producto cargado puede cambiar** si su espesor declarado no cerraba con la
  masa: el derivado lo reemplaza. En el caso de referencia, 2 cm declarados → 0.8 cm reales.
- Cambian en cascada producción anual, fracción solar, energía específica, η_drying.
- Por el criterio de S62 (*si cambian los resultados, cambia la versión*), corresponde **bump
  menor como mínimo**, con nota destacada en `CHANGELOG.md`.

---

## 7. Riesgo asumido y trabajo futuro

### 7.1 Se pierde una configuración físicamente válida

**Un secador de lecho atravesado forzado es una máquina real.** Con ventilador, los 31.6 Pa del
lecho se pagan sin problema, y los secadores de lecho industriales hacen exactamente eso. El
argumento de presión que justifica eliminar el through-flow vale para el **pasivo**. El armario
de referencia tiene motor eléctrico, así que para él la eliminación es una subestimación
deliberada.

Mitigación: git conserva la rama completa (`geometria_lecho` + Ranz-Marshall + Ergun) y este
documento deja registrado que reactivarla exige primero arreglar el `d_sv` del catálogo.

### 7.2 El camino correcto de largo plazo

Reparto de caudal entre **caminos paralelos** resuelto por igualdad de Δp: camino 1 a través del
lecho (Ergun), camino 2 alrededor (cross-flow). La fracción `f` que atraviesa pasa a ser
**resultado** y no declaración, y el área se mezcla: `A = f·A_lecho + (1−f)·A_bandeja`. El
proyecto ya tiene las dos piezas de ΔP y ya sabe resolver un balance de presión con `brentq`.
Requiere el `d_sv` arreglado para no dar `f ≈ 0` por construcción.

### 7.3 Queda abierto: el lazo evaporación → tiro

Con NTU alto el aire sale de la cámara casi a la ambiente, lo que **mata el empuje que lo
mueve**: menos caudal → mayor NTU → más saturación → más frío. Antes de S63 (NTU 0.19) el aire
casi no se enfriaba y la chimenea trabajaba con el ΔT del colector entero. Es testeable con los
dos cajones pasivos del repo y forma parte de la verificación (§8.3).

### 7.4 Sin validación experimental

Nada de esto está contrastado contra mediciones. Vale la advertencia general del work stream de
convección natural: es coherencia interna, no validación. Extensión natural de la mejora 38
fase 4 (`docs/notas/plan_datos_medidos_4.md`).

---

## 8. Verificación

1. **Suite completa**: `.venv/bin/python -m pytest`.
   Auditar y reescribir los tests que fijan comportamiento vertical:
   `tests/test_calculos/test_topologia_transferencia_camara.py` (28 tests de S63, mayormente
   obsoletos), `test_cadena_etapas_camara.py`, `test_diagnostico_transferencia.py`,
   `test_camara_conveccion_natural.py`, `test_motor_anclaje.py`, `test_motor_fase2.py`,
   `tests/test_core/test_motor.py`, `tests/test_ui/test_diagnostico_ntu_p4.py`.
   Tests nuevos: coacción de `VERTICAL_ASCENDENTE`; área de dos caras contra `tipo_malla`;
   espesor derivado como inversa exacta de `masa_que_llena_el_lecho_kg` (ida y vuelta);
   `CAM_CAPA_CIERRA_EL_CANAL`; que el barrido de masa re-derive el espesor.
2. **Migración de snapshots**: cargar los tres `.json` con `VERTICAL_ASCENDENTE`
   (`tests/armario indirecto forzado/`, `tests/test analisis armario con resistencia/`,
   `tests/test 2 analisis cajon con chimenea extractor y resistencia/`) y verificar que migran
   con aviso y corren de punta a punta hasta el reporte.
3. **Lazo de tiro** (§7.3): en los dos cajones pasivos, verificar que el caudal del motor natural
   sube al desaparecer el ΔP de Ergun y que `T_flujo` no colapsa el tiro.
4. **Calidad**: `black .`, `ruff check .`, `scripts/auditar_i18n.py`, y
   `pytest -m i18n_paridad` con los tres idiomas ya escritos.
5. **Smoke en Streamlit** de P4: sin selector de dirección de flujo, espesor como métrica
   derivada, advertencias de malla y de espesor visibles.

## Ver también

- [[docs/notas/resultado_crossflow_unico_camara]] — **el resultado de implementar este plan**:
  lo medido, las desviaciones y los hallazgos colaterales.
- [[docs/notas/plan_transferencia_camara]] — el plan de S63 que este revierte parcialmente.
- [[docs/bitacora/bitacora_sesion63]] — la sesión que introdujo el through-flow.
- [[docs/notas/estado_conveccion_natural_secasol]] — §6.3, el empuje solutal pendiente.
- [[docs/notas/plan_datos_medidos_4]] — la validación que cerraría esto contra datos reales.
- [[docs/decisiones]] — ADR-007, el caudal como resultado en un secador pasivo.
- [[docs/tareas]] — backlog.
