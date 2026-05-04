# PLANTILLA DE REFERENCIA — Catálogo de Productos
# Software de prediseño de secadores solares — INENCO/UNSa

**Versión:** Sesión 7 (post-cambio de flujo)
**Uso:** Guía de carga cuando completás los coeficientes en los archivos YAML.
**Mantenerla al lado** mientras buscás y cargás papers.

---

## 1. Estructura de un archivo YAML de catálogo

Cada archivo (`frutas.yaml`, `hortalizas.yaml`, etc.) es un **diccionario** cuyas claves son los `producto_id`:

```yaml
producto_id_1:
  descripcion: "..."
  categoria: FRUTA | HORTALIZA | HOJA_AROMATICA | LEGUMBRE_FRUTO | CARNE
  tipo_secado: CAPA_FINA
  fotosensible: true | false
  propiedades_basicas:
    ...
  capa_fina:
    ...
  isoterma:
    ...
  notas: |
    ...

producto_id_2:
  ...
```

---

## 2. Convenciones de unidades (SI estricto — NO negociar)

| Campo | Unidad | Notas |
|---|---|---|
| Temperaturas en `condiciones_calibracion` | **Kelvin** | Ej: 60°C → 333.15 K |
| Tiempo en modelos de capa fina | **minutos** | Convención de los papers; el módulo convierte internamente |
| Humedad del producto (`X`) | kg agua / kg ms | BASE SECA siempre. Convertir: `X = X_bh / (1 - X_bh)` |
| Humedad relativa del aire (`HR_aire`) | fracción [0, 1] | No porcentaje. Ej: 30% → 0.30 |
| Densidad | kg/m³ | |
| Calor específico | J/(kg·K) | |
| `v_aire_m_s` | m/s | |
| `espesor_m` | metros | Ej: 5 mm → 0.005 |

---

## 3. Bloque `propiedades_basicas` — campos completos

```yaml
propiedades_basicas:

  densidad_aparente: 840.0           # kg/m³ — del producto FRESCO, antes de secar
  calor_especifico_seco: 1810.0      # J/(kg·K) — del SÓLIDO SECO (sin agua)
  humedad_inicial_tipica: 4.6        # kg agua / kg ms — base seca, rango típico
  humedad_equilibrio_aire_seco: 0.10 # kg/kg ms — fallback cuando no hay isoterma
                                     # calibrada. Valor a HR~0.10-0.15, T~298K.
                                     # La isoterma es la fuente oficial.

  calidad_propiedades_basicas: ALTA  # ALTA | MEDIA | BAJA
  fuente_propiedades_basicas: |
    Densidad: ASHRAE Handbook Refrig. 2018 Ch.19; USDA SR-28.
    Calor específico: Apellido Año (DOI verificado).
    Humedad inicial: Apellido Año (DOI verificado).
```

**Sobre `calidad_propiedades_basicas`:**
- `ALTA`: valor de handbook o paper con medición directa.
- `MEDIA`: estimado por Choi-Okos con composición de otro paper, o por analogía con producto similar.
- `BAJA`: estimado "a ojo" o sin fuente clara.

---

## 4. Bloque `capa_fina` — los 5 modelos soportados

### Formas matemáticas (tiempo `t` en MINUTOS)

| Modelo | Fórmula | Params |
|---|---|---|
| `lewis` | MR = exp(-k·t) | `k` |
| `page` | MR = exp(-k·t^n) | `k`, `n` |
| `henderson` | MR = a·exp(-k·t) | `a`, `k` |
| `midilli` | MR = a·exp(-k·t^n) + b·t | `a`, `k`, `n`, `b` |
| `logaritmico` | MR = a·exp(-k·t) + c | `a`, `k`, `c` |

**MR** = (M - M_e) / (M_0 - M_e) adimensional [0, 1].
Muchos papers simplifican MR = M/M_0 cuando M_e << M_0 — es válido para períodos largos y productos con alta humedad inicial.

### Estructura de un bloque de modelo

```yaml
capa_fina:

  page:                              # nombre del modelo (clave fija del esquema)
    params:
      k: 0.1153                      # min^(-n) — SIEMPRE positivo
      n: 1.2965                      # adimensional — típicamente 0.5 a 2.0
    condiciones_calibracion:
      T_K: 333.15                    # K — si es una única T
      # T_K: [313.15, 323.15, 333.15]  # si el paper da el mismo set para un rango
      v_aire_m_s: 0.8                # m/s
      espesor_m: 0.005               # m (5 mm)
      HR_aire: 0.25                  # fracción; poner null si el paper no lo reporta
    calidad_datos: ALTA              # ALTA | MEDIA | BAJA | ESTIMADA_POR_ANALOGIA
    fuente: "Apellido AA, Apellido BB (YYYY). Título breve. Revista Vol(N):pp-pp. DOI:xx.xxxx/xxxxx"
    notas: |
      Variedad: nombre. Pretratamiento: descripción o "ninguno".
      R² = 0.99xx reportado en paper.
      Observación si hay algo especial sobre cómo extraer o usar estos datos.

  midilli:
    params:
      a: 1.0041
      k: 0.1281                      # min^(-n)
      n: 0.82
      b: -0.03897                    # min^(-1) — puede ser negativo
    condiciones_calibracion:
      T_K: 333.15
      v_aire_m_s: 0.8
      espesor_m: 0.005
      HR_aire: null
    calidad_datos: ALTA
    fuente: "Sacilik K, Elicin AK (2006). J Food Eng 73(3):281-289. DOI:10.1016/j.jfoodeng.2005.03.024"
    notas: |
      Modelo 10 de Tabla 2. Coeficientes globales (todas T y espesores combinados).
      R² = 0.9980, χ² = 0.17e-3.
```

### Cuándo usar cada `calidad_datos`

| Valor | Cuándo usarlo |
|---|---|
| `ALTA` | Paper peer-reviewed, condiciones documentadas (T, v, h), R² ≥ 0.99 reportado. |
| `MEDIA` | Paper bueno pero coeficientes globales (no por T), o HR no reportada, o tesis/congreso. |
| `BAJA` | Literatura gris, paper de bajo factor de impacto sin revisión clara. |
| `ESTIMADA_POR_ANALOGIA` | Copiados de otro producto similar. **Obligatorio** explicar en `notas` qué producto se tomó como base y por qué. |

### Advertencia frecuente: papers que NO dan coeficientes

Muchos papers reportan solo r²/χ²/RMSE pero **no publican los valores de k, n, a, b**.
En ese caso: poner `params: null` y en `notas` escribir algo como:

```yaml
params: null
notas: |
  Paper evaluado: Apellido (YYYY). NO publica coeficientes, solo estadísticos
  de bondad de ajuste (r²=0.99, χ²=0.001). Inutilizable para params.
  Buscar alternativa: Doymaz & Bilici (2014) DOI:10.1515/ijfe-2014-0026
  sí publica coeficientes.
```

---

## 5. Bloque `isoterma` — los 3 modelos soportados

### Formas matemáticas

| Modelo | Fórmula | Params |
|---|---|---|
| `gab` | X_eq = X_m·C·K·a_w / [(1-K·a_w)·(1-K·a_w + C·K·a_w)] | `X_m`, `C`, `K` |
| `oswin` | X_eq = a·[a_w/(1-a_w)]^b | `a`, `b` |
| `henderson` | 1 - a_w = exp(-c·T·X_eq^n) | `c`, `n` |

Donde:
- `X_eq` = humedad de equilibrio [kg agua / kg ms, **base seca**]
- `a_w` = actividad de agua [0, 1]
- `X_m` = contenido de humedad de la monocapa [kg/kg ms]
- `C` = constante de Guggenheim [adimensional]
- `K` = constante de corrección GAB [adimensional, típicamente 0.7-1.0]
- `T` en el modelo de Henderson: algunos autores lo ponen en K, otros en °C — verificar en el paper.

**Para SECADO usar siempre rama de DESORCIÓN.** Si el paper solo tiene adsorción, indicarlo en notas con calidad rebajada.

### Estructura de un bloque de isoterma

```yaml
isoterma:

  gab:
    params:
      X_m: 0.129                     # kg/kg ms — monolayer moisture content
      C: 1.50                        # constante Guggenheim
      K: 0.978                       # constante GAB
    rango_T_K: [323.15, 333.15]      # [T_min, T_max] en K
    calidad_datos: ALTA
    fuente: "Apellido AA et al. (YYYY). Revista Vol:pp. DOI:xx"
    notas: |
      Rama de desorción. Pearson > 0.997.
      Si rango T no cubre las condiciones de uso → advertencia en módulo.
```

---

## 6. Campo `notas` — qué poner siempre

El campo `notas` es texto libre (YAML literal block `|`). Incluir siempre:

1. **Pretratamientos** usados en el ensayo de calibración (blanching, KMS, limón, ninguno).
2. **Variedad** del producto si el paper la especifica.
3. **Advertencias de extrapolación**: si el rango T calibrado es muy diferente al rango de uso esperado en secadores solares NOA (30-65°C).
4. **Referencias descartadas**: papers evaluados que no dieron coeficientes o que se descartaron y por qué. Evita que alguien más pierda tiempo evaluando el mismo paper.
5. Para `ESTIMADA_POR_ANALOGIA`: qué producto se tomó como base, por qué es análogo, y qué incertidumbre introduce.

---

## 7. Cómo citar: formato obligatorio del campo `fuente`

```
"Apellido A, Apellido B (YYYY). Título completo o abreviado. Revista Vol(N):pp-pp. DOI:xx.xxxx/xxxxx"
```

**Regla**: solo poner DOI si lo verificaste en el PDF del paper o en una fuente que lo liste textualmente (ScienceDirect, DOI.org, Springer, etc.). Si no lo verificaste, omitirlo:

```
"Apellido A et al. (YYYY). Título. Revista Vol(N):pp-pp. [DOI no verificado]"
```

---

## 8. Valores de `fotosensible`

- `true`: el producto contiene pigmentos o principios activos que se degradan con luz UV (clorofila, antocianinas, carotenos, aceites esenciales). Ejemplos: hojas de coca, yerba mate, orégano, pimiento rojo.
- `false`: el secado a plena luz no afecta la calidad del producto de manera significativa. Ejemplos: papa, mandioca, charqui.
- En la UI, esto sirve para que el módulo de resultados sugiera proteger la cámara de radiación directa o advirtir sobre exposición excesiva.

---

## 9. Ejemplo completo de un producto correctamente llenado

El ejemplo de referencia es `manzana` en `frutas.yaml` (Sesión 7, datos de Sacilik 2006 verificados del PDF):

```yaml
manzana:
  descripcion: "Manzana (Malus domestica) en rodajas..."
  categoria: FRUTA
  tipo_secado: CAPA_FINA
  fotosensible: false
  propiedades_basicas:
    densidad_aparente: 840.0
    calor_especifico_seco: 1810.0
    humedad_inicial_tipica: 4.6
    humedad_equilibrio_aire_seco: 0.10
    calidad_propiedades_basicas: ALTA
    fuente_propiedades_basicas: |
      Densidad: ASHRAE Handbook Refrig. 2018 Ch.19; USDA SR-28.
      Calor específico: Mykhailyk & Lebovka (2013) arXiv:1305.1340.
      Humedad inicial: Sacilik & Elicin (2006) DOI:10.1016/j.jfoodeng.2005.03.024.
  capa_fina:
    logaritmico:
      params:
        a: 1.7506
        k: 0.0761
        c: -0.7718
      condiciones_calibracion:
        T_K: [313.15, 323.15, 333.15]
        v_aire_m_s: 0.8
        espesor_m: [0.005, 0.009]
        HR_aire: null
      calidad_datos: ALTA
      fuente: "Sacilik K, Elicin AK (2006). J Food Eng 73(3):281-289. DOI:10.1016/j.jfoodeng.2005.03.024"
      notas: |
        Mejor ajuste de 10 modelos. R²=0.9983. Variedad Starking orgánica.
        Pretratamiento: inmersión 5% solución limón 5 min.
  isoterma:
    gab:
      params: null                   # Pendiente — conseguir Kaymak-Ertekin (2004)
      rango_T_K: null
      calidad_datos: null
      fuente: "PENDIENTE — Kaymak-Ertekin & Gedik (2004) DOI:10.1016/j.lwt.2003.10.012"
  notas: |
    Default recomendado: modelo logarítmico (Sacilik 2006).
    Isoterma pendiente.
```

---

## 10. Checklist antes de guardar un producto como "completo"

- [ ] Al menos un modelo de capa_fina con `params` no-null y `calidad_datos` no-null.
- [ ] Todos los `params: null` tienen una nota explicando qué se necesita para llenarlo.
- [ ] Todos los DOIs en `fuente` fueron verificados (en el PDF o en fuente externa).
- [ ] Las temperaturas en `condiciones_calibracion` están en Kelvin.
- [ ] La humedad inicial está en base seca.
- [ ] `fotosensible` tiene el valor correcto para el producto.
- [ ] El campo `notas` menciona pretratamientos y variedad del ensayo de calibración.
- [ ] Si hay `ESTIMADA_POR_ANALOGIA`, la nota explica el producto base y la justificación.

---

## 11. DOIs verificados disponibles (al cierre Sesión 7)

Estos DOIs fueron verificados directamente en los metadatos de los PDFs o en fuentes cruzadas durante Sesiones 6-7. Son seguros para usar en `fuente`:

| Paper | DOI verificado | Verificación |
|---|---|---|
| Sacilik & Elicin (2006) — manzana | `10.1016/j.jfoodeng.2005.03.024` | Metadato Title del PDF |
| Kingsly et al. (2006) — durazno | `10.1111/j.1365-2621.2006.01210.x` | Texto interno del PDF |
| Shi et al. (2013) — yacón (heat pump) | `10.1016/j.enconman.2013.03.032` | Metadato Subject del PDF |
| Marques et al. (2022) — yacón (LWT) | `10.1016/j.lwt.2022.113151` | URL y cita HAL en el PDF |
| Zarein et al. (2013) — manzana | `10.4172/2157-7110.1000247` | Texto del PDF |
| Kaymak-Ertekin & Gedik (2004) — isotermas | `10.1016/j.lwt.2003.10.012` | Fuente cruzada (múltiples citas en literatura) |
| Doymaz & Bilici (2014) — durazno | `10.1515/ijfe-2014-0026` | Fuente cruzada (De Gruyter + Frontiers) |
| Goyal et al. (2007) — ciruela (en archivo durazno) | `10.1016/j.jfoodeng.2006.01.041` | Metadato del PDF |
| Kingsly et al. (2007) — granada (en archivo durazno) | `10.1016/j.jfoodeng.2006.02.033` | Metadato del PDF |

**Nota**: Doymaz & Bilici (2014) tiene editor **De Gruyter**, no Elsevier. Verificar si MINCyT cubre De Gruyter. Si no, es Open Access parcial.
