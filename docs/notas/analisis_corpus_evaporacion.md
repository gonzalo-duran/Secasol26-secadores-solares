# Corpus de papers para calibrar el modelo de evaporación (S69)

**Fecha:** 2026-11-19 · **Rama:** `testing` (`ca68ceb`) · **Fuente:**
`docs/Papers de secadores p_ calibrar secasol/` (16 PDF, 14 trabajos distintos).

Objetivo de la línea de trabajo (esta sesión y las siguientes): revisar el **modelo de
evaporación de agua en el producto** de Secasol contra la literatura del grupo INENCO y dos
trabajos externos. Esta nota es el inventario, el cruce y el diagnóstico. No propone código
todavía.

---

## 1. Inventario

Tipo: **M** = modelado puro · **E** = medición pura · **M+V** = modelo con validación medida.

| # | Referencia | Tipo | Escala / tecnología | Producto | Aporte al modelo de evaporación |
|---|---|---|---|---|---|
| 1 | Condorí & Saravia 1998, *Renew. Energy* 13(4) | M (parámetros de ensayos) | Invernadero, 50 m², forzado, cámara simple y doble | Pimiento rojo | **Origen de `Hpd(X)`**: `ṁ_w = Hpd(X)·(W_s(T_p) − W)`, `Hpd = a* + b*·X` (pimiento: `0.0264·X`). Función característica `f_p(Z)`, tiempo equivalente `t*`, curva de secado generalizada. Tabla 1 completa de parámetros |
| 2 | Condorí, Echazú & Saravia 2001, *Renew. Energy* 22 | E | Túnel invernadero (13 m, carros), forzado | Pimiento, ajo | Curvas de secado por tipo de corte (vaina entera 6 d, mitad longitudinal 3 d) y espesor (ajo 3 mm). Carga 5–7 kg/m² bandeja. `T − T_a = 0.0208·I` |
| 3 | Condorí & Saravia 2003, *Renew. Energy* 28 | M+V | Túnel invernadero, contracorriente | Pimiento | `Hpd(X)` en un túnel discretizado por secciones (EDO 2º orden en `W(y)`); **validado contra la curva del primer carro**; `f_p = 0.331 − 0.127·Z`; producción 4.76 kg/h |
| 4 | Condorí 2009, ASADES 13 | M | Secador ideal (agua libre) | Agua libre | Potencial de secado `P_T = A·I + q_v·ṁ·[W_s(T_w) − W_a]` e índice `Z`; **eficiencia de secador por bandejas de agua** |
| 5 | Saravia, Alía & Sánchez 2007, ASADES 11 (`docs/notas/Saravia2007.pdf`) | M+V | Minisecador de laboratorio | Banana | **Método para obtener `Ahd(X)` y `Ahc(X)` de una curva de secado**. Dataset completo: `X(τ) = exp(1.035 − 0.1989·τ[h])`, `T_p(τ) = (40τ + 55.6)/(τ + 1.94)`, `T_c = 40 °C`, HR 25 %, v 1.6 m/s, `A_t = 0.282 m²`, `M_s = 0.0974 kg`, `p = 87 kPa` |
| 6 | Durán & Condorí 2009, ASADES 13 | M | Pasivo semi-industrial, chimenea + extractor | Pimiento (180 kg) | Usa el método 5 con polinomios `Ahd(x)`, `Ahc(x)` de pimiento (Condorí 1998). Acople térmico–presión–humedad en SIMUSOL. Sin validación |
| 7 | Condorí, Durán, Vargas & Echazú 2009, ASADES 13 | E | ADITAL San Carlos, túnel forzado + leña, 200 m² colectores | Pimiento (~2 t) | Primer día de carga: T y HR de entrada/salida, perfiles 2D de T y v, curva de peso de muestra (seco en ~30 h de sol) |
| 8 | Condorí, Durán, Echazú & Díaz Russo 2010, ERMA 25 | E | ADITAL híbrido solar–biomasa (195 m², 26 colectores, 2.4 t) | Pimiento | Ídem 7 + campaña híbrida mayo 2010 (3 días): HR sube ~30 % en cámara, T de producto, intercambiador |
| 9 | Condorí et al. 2012, ASADES 16 | E | Planta San Carlos: túnel 16.8 m + presecado directo + 24 kW eléctricos, 32 colectores | Pimiento (3.5 t) | Diagramas de caja abr–may 2010: medianas `T_e/T_s cámara 37.7/37.5 °C`, `HR_e/HR_s 8.5/16.8 %`; v entrada media 0.71 m/s; "aire sale sin completar su potencial de secado" |
| 10 | Durán, Condorí & Díaz Russo 2012, CBENS (T302) | E | Ídem 9 (versión 22 carros / 4.6 t) | Pimiento | Mismos datos que 9, con la geometría anterior a la cámara de presecado |
| 11 | Durán, Molina, Condorí & Buchller 2008, ASADES 12 (PDFA ×2, idénticos) | E | Doméstico: chimenea CPC + extractor vs ventiladores FV | **Agua libre**, esponjas, charqui | **Ensayo de evaporación de agua libre** en paralelo; v salida 0.2 (pasivo) vs 2.1 m/s (forzado); charqui 3.58 → 1.98 kg en ~2 días |
| 12 | Durán et al. 2011, ASADES 15 | E | Doméstico pasivo CPC modular | Nopalito | Muestra 103 g → 5 g en 1.5 días; HR cámara ~5 % |
| 13 | Martínez, Condorí & Albesa 2016, CBENS | E | Pequeño híbrido solar–eléctrico, colector doble paso con matriz porosa | Sin carga | Solo térmico: η vs caudal (óptimo 0.06 m³/s, η 54 %). **No aporta a evaporación** (sí al colector) |
| 14 | Altobelli et al. 2013, ASADES 17 | E | Estufa de curado de tabaco bulk curing, gas | Tabaco Virginia | Consumo de gas por kg curado, aislación de piso. **No aporta a evaporación** (sí a envolvente/auxiliar) |
| 15 | Simate 2003, *Renew. Energy* 28 (externo) | M+V | Natural, modo mixto vs indirecto, 90 kg | Maíz | **Lecho profundo** con capa fina de Page (Misra–Brooker) + isoterma Chung-Pfost + conducción en el lecho; validado en simulador solar (MRD 1–1.8 %) |
| 16 | Hachemi, Abed & Asnoun 1998, *Renew. Energy* 13(4) (externo) | M+V débil | Forzado, tres lechos en serie, simulador solar | Lana | Lecho profundo de tres zonas (frentes de T y de humedad); cinética logarítmica de Lewis `dM/dt = −k(M − M_e)` |

Notas de higiene del corpus:

- Los dos `Documento_completo.pdf-PDFA` son **el mismo archivo** (md5 idéntico).
- **T302 (10) ≈ ASADES 2012 (9)**: mismo texto y figuras, con distinta geometría de carros
  (22 × 210 kg = 4.6 t contra 20 × 270 kg = 6 t). Usar 9 como versión final.
- **Coordenadas de San Carlos inconsistentes**: (8) da `22°52′59″ S, 64°40′ O`; (4) da
  `25°54′ S, 65°57′ O`. La segunda es la correcta para San Carlos (Salta); conviene revisar
  qué coordenadas usa el preset/validación ADITAL.
- (8) informa "0.73 m³/h" de flujo a la salida de cámara: incompatible con 0.06–0.175 m/s en
  5.4 m² (≈ 1–3 m³/s). Error de unidades en el original.
- (6): el polinomio `Ahc(x)` perdió exponentes en la extracción de texto (`−1.21x + 4.26x + 0.82`,
  seguramente `−1.21x² + 4.26x + 0.82`); las unidades de `Ahd` y `Ahc` no están declaradas.
  Hay que ir a la figura del PDF original.
- (1): las unidades de `Hpd` ("kg water/s·kg fresh") no cierran con la ecuación (2) tal como
  está escrita; el valor sirve para la **forma** de la caída con X, no para el valor absoluto.

## 2. Cruce por tipo y por tecnología

| | Pequeña escala (doméstica / laboratorio) | Invernadero / túnel invernadero | Gran escala indirecta (ADITAL / San Carlos) |
|---|---|---|---|
| **M** | Condorí 2009 (agua libre, ideal) | Condorí & Saravia 1998 | Durán & Condorí 2009 (pasivo semi-industrial) |
| **M+V** | Saravia 2007 (minisecador); Simate 2003; Hachemi 1998 | Condorí & Saravia 2003 | — |
| **E** | Durán 2008 (agua libre, charqui); Durán 2011 (nopal); Martínez 2016 (sin carga) | Condorí 2001 | Condorí 2009; Condorí 2010; Condorí 2012 / T302 |

Lectura del cruce:

1. **El hueco está en la gran escala indirecta**: tiene tres campañas medidas y ningún modelo
   validado contra ellas. Es exactamente el lugar donde Secasol tiene el motor de cascada
   (`simular_cascada`) y la `validacion/validacion_adital.py` (que valida la cadena **térmica**,
   no la evaporación).
2. **El único M+V a escala de equipo con carga real** es Condorí & Saravia 2003 (túnel
   invernadero, primer carro). Es tecnología de ganancia directa —producto que recibe radiación
   a través del túnel—, que en Secasol corresponde a la cámara radiativa (`Q_rad` repartido).
3. **Los M+V externos (Simate, Hachemi) son de lecho profundo atravesado**, un régimen que
   Secasol retiró en S64 (cross-flow único). Sirven como contraste físico, no como calibración
   directa.
4. **Hay tres ensayos de agua libre** (Durán 2008; Condorí 1998, 600 bandejas negras, 235 kg en
   3½ días; y el modelo ideal de Condorí 2009). Con `a_w = 1` y sin resistencia interna,
   **aíslan la película externa** (Chilton-Colburn) del resto del modelo.

## 3. El linaje del modelo de evaporación

Toda la literatura del grupo usa la **misma ecuación de Dalton en humedades absolutas**:

```
ṁ_w = [coeficiente] · (W_sat(T_p) − W_aire)          (1998, 2003, 2007, 2009)
(c_ps + c_pa·X)·M_s·dT_p/dt − h_fg·M_s·dX/dt = Ahc·(T_c − T_p)
```

y Secasol hereda esa estructura (`balance de calor y masa en camara ampliado.md`, que cita a
Saravia 2007 casi textual). La diferencia está en **dónde vive la caída de la velocidad de
secado**:

| | Coeficiente | Fuerza impulsora | Qué hace caer la velocidad |
|---|---|---|---|
| INENCO 1998–2009 | `Hpd(X)` o `Ahd(X)` **empírico global**, ajustado de una curva de secado | `W_s(T_p) − W` | El coeficiente (área + película + **resistencia interna**) |
| Secasol (S38→) | `K_m = ρ·h_m` por **Chilton-Colburn** (solo película externa), × `A_prod` geométrico | `ω_sat(T_p)·a_w(X) − ω` | Solo `a_w(X)` de la isoterma GAB |
| Simate / Hachemi | Capa fina (Page / Lewis) + EMC | `M − M_e` | La constante cinética de capa fina |

### 3.1 Cuantificación

Caída relativa del factor que frena la evaporación, pimiento, de X = 9.65 a 0.1
(GAB con `X_m = 0.08, C = 12.53`; dos valores de K porque el del catálogo no es válido, ver §3.2):

| X [kg/kg] | `a_w` GAB (K = 0.95) | `a_w` GAB (K = 0.85) | `Hpd/Hpd₀` Condorí 1998 (lineal) | `Ahd/Ahd₀` Durán 2009 (cúbico) |
|---|---|---|---|---|
| 9.65 | ≈ 1 | ≈ 1 | 1.000 | 1.000 |
| 5 | ≈ 1 | ≈ 1 | 0.518 | 0.115 |
| 2.3 | ≈ 1 | ≈ 1 | 0.238 | 0.011 |
| 1 | 0.97 | ≈ 1 | 0.104 | 0.003 |
| 0.5 | 0.89 | 0.99 | 0.052 | 0.002 |
| 0.2 | 0.65 | 0.73 | 0.021 | 0.0009 |
| 0.1 | 0.33 | 0.37 | 0.010 | 0.0005 |

**Conclusión:** en Secasol la fuerza impulsora no empieza a caer hasta X ≈ 0.5–1; el producto
evapora **a velocidad de período constante durante ~95 % del agua a remover**. Los coeficientes
empíricos del grupo caen un orden de magnitud entre fresco y medio seco (X ≈ 1–2.3). Es el
límite ya registrado en CLAUDE.md ("el modelo no tiene resistencia interna a la difusión"),
y su consecuencia sería: evaporación sobrestimada desde el día 2 y tiempos de lote cortos.

Los ensayos medidos dan tiempos que el modelo tiene que poder reproducir: pimiento en vaina
2–2.5 días de sol en ADITAL (7, 8); mitad longitudinal 3 días contra vaina entera 6 días en el
túnel invernadero (2) —**la geometría del corte duplica el tiempo**, cosa que una película
externa con `a_w(X)` no puede ver—; 110 h en cámara simple simulada (1).

### 3.2 Hallazgo concreto: la isoterma del pimiento no funciona

`catalogo/productos/hortalizas.yaml → pimiento_rojo.isoterma.gab.params` tiene **`K = 1.02`**
(Vega et al. 2007, Tabla 2). `actividad_agua_desde_X_GAB` exige `K ∈ (0, 1)` y lanza
`PSICRO_GAB_K_FUERA_RANGO`; el `except` de `camara_calc._aw_func` cae entonces a
`1.0 if X > X_m else 0.0`. **Para el pimiento —el producto central de todo este corpus— el
`a_w` de Secasol es un escalón**: no hay ningún frenado hasta X = 0.08, y ahí se corta de golpe.
Hay que revisar si el K de Vega es un error de transcripción o un ajuste legítimo con K > 1
(GAB admite K ≥ 1 a altas X en algunos productos, pero entonces `a_w → 1/K < 1` y la inversión
necesita otro tratamiento).

Revisando los 20 productos: solo manzana, papa y yacón tienen GAB válido; los otros 16 tienen
`params: null` y caen a la reserva `a_w = X/X₀` (rampa lineal). Detalle y consecuencias en
[[docs/notas/plan_modelo_evaporacion]] §1.4.

Además, el mismo catálogo guarda **Page de Vega 2007 para pimiento a 50–80 °C** (`capa_fina`),
que desde S38 es vestigial: la información sobre el período decreciente ya está cargada y no se
usa para calcular.

### 3.3 Otros fenómenos que el corpus señala

- **Calor del suelo / inercia nocturna** (2, 3): el desvío modelo–medición del túnel invernadero
  se concentra de noche por el calor almacenado en el suelo. Secasol no tiene suelo.
- **Rehidratación nocturna** (2): solo apreciable con dos o más días malos; el ajo en láminas no
  rehidrata por debajo de HR 70 % (isoterma de desorción, Piñaga). Secasol tiene la política B
  (no condensar), no readsorción.
- **Radiación directa sobre el producto** (1, 2, 3, 15): en el túnel invernadero y el modo mixto
  es el término `(τα_p)·A_pi·I` del balance del producto, que Secasol ya tiene vía cámara
  radiativa.
- **Distribución no uniforme del aire en la boca del túnel** (7, 8, 9): v de 0.2 a 1.3 m/s en la
  sección de entrada, secado desparejo en los dos primeros carros. Es un efecto de escala que
  un modelo 0-D/cascada no captura; queda como límite declarado.
- **"El aire sale sin completar su potencial de secado"** (7, 8, 9): HR de salida 17 % de
  mediana, ΔT entrada–salida ≈ 0–5 °C. Es una observación cuantitativa contra la que contrastar
  el `acercamiento_equilibrio` y la `aprovechamiento_aire` de Secasol en ADITAL.

## 4. Qué datos medidos son utilizables y para qué

| Nivel | Qué se valida | Datos | Calidad |
|---|---|---|---|
| **1. Película externa** (`K_m`, `a_w = 1`) | Chilton-Colburn + balance del aire | Durán 2008 (agua libre, dos secadores en paralelo, pesos + T + HR + v); Condorí 1998 (bandejas de agua, 50 m²) | Series en figuras → hay que digitalizar; ¿existen los registros del datalogger? |
| **2. Cinética del producto** (resistencia interna) | `Ahd(X)` / `K_int(X,T)` | Saravia 2007 (banana, **dataset completo en texto**); Durán 2009 (`Ahd(x)`, `Ahc(x)` pimiento); Condorí 1998 (`Hpd = 0.0264·X` pimiento) | El de Saravia es el único reproducible solo con el PDF |
| **3. Sistema** | Cámara completa con carga | Condorí 2003 (primer carro túnel invernadero); ADITAL 2009/2010 (curva de peso + T/HR e/s); San Carlos 2012 (estadísticos T/HR e/s, carga 3.5 t); nopal 2011; charqui 2008 | Figuras y estadísticos; la tesis cap. 3 tiene la versión más completa de ADITAL |

Ojo con el nivel 3: Secasol es un prediseñador **general**. ADITAL y San Carlos sirven como
chequeo de orden de magnitud, no como objetivo de calibración; lo que se calibra tiene que ser
una ley física o de producto (niveles 1 y 2) que después se verifica en los equipos.

Para el nivel 3 la maquinaria ya existe: mejora 38, fase 4 (validación/calibración de cámara),
planificada en `plan_datos_medidos_4.md` y sin implementar.

## 5. Preguntas abiertas para la próxima discusión

1. **¿Dónde poner la resistencia interna?** Tres caminos, todos compatibles con la forma de
   Dalton actual:
   - (a) factor empírico `f(X)` que multiplica `K_m` (el `Hpd(X)/Hpd₀` del grupo), ajustado por
     el método de Saravia 2007;
   - (b) **resistencias en serie** `1/K = 1/K_ext(v, T) + 1/K_int(X, T, espesor)`, con `K_int`
     desde una difusividad efectiva con Arrhenius (los papers de `docs/notas/papers/` traen
     `D_eff` y `E_a`); conserva la dependencia con el caudal, que el `Hpd` medido en un solo
     secador confunde con el producto, y recupera el corte/espesor que muestra Condorí 2001;
   - (c) volver a usar la capa fina (Page) como velocidad límite.
2. **El K del pimiento** (§3.2): ¿corregir el dato, o el inversor GAB?
3. **¿Los registros crudos existen?** Los ensayos de agua libre (2008) y ADITAL (2009–2010)
   están en figuras; si hay archivos del datalogger, el nivel 1 y el 3 se vuelven inmediatos.
4. Relación con la decisión de S67 de **no tocar la transferencia de cámara sin mediciones**
   (`plan_percolacion_parcial.md`): este corpus es la primera tanda de mediciones; conviene
   decidir si alcanza para mover el modelo de evaporación o si primero se valida el nivel 1.
