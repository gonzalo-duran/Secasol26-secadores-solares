# BITÁCORA — SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

**Última actualización:** Sesión 8 (Tandas 3 paso 3, 4 y 5 cerradas — modelo de datos central COMPLETO)
**Estado:** Modelo de datos central 100% definido (todas las dataclasses, validaciones, mecanismo de invalidación). Catálogo de materiales v1 cerrado. Tanda 3 paso 2 EN CURSO (catálogo de productos — el usuario carga coeficientes de forma autónoma). Sin código aún. Siguiente paso: estructura de carpetas + convenciones + esqueleto del repo.

---

## 1. Contexto y objetivo del proyecto

Software de **prediseño** (no simulación detallada tipo Simusol, ni diseño mecánico final) de secadores solares de alimentos, orientado a usuarios técnicos con formación en transferencia de calor.

**Usuario destinatario:** Ingenieros y estudiantes del curso de posgrado "Secadores Solares" de la Maestría en Energías Renovables (M.E.R.), Facultad de Ciencias Exactas, UNSa, Argentina.

**Espíritu del proyecto:** Académico, comunitario, abierto. Pensado para compartirse vía GitHub entre colegas, alumnos y comunidad científica.

**Nivel de modelado:** Complejidad media. Suficiente para tomar decisiones de ingeniería de prediseño (dimensiones, áreas, caudales, potencias auxiliares) pero sin pretender reemplazar simulación nodal completa.

---

## 2. Perfil del desarrollador (referencia para Claude)

- Licenciado en Física, Doctor en Ciencias especialidad Energías Renovables.
- Investigador Adjunto CONICET, INENCO–UNSa.
- Docente de Transferencia de Calor y Materia (5° año Lic. Física y Lic. Energías Renovables).
- Docente posgrado M.E.R.–UNSa: Transferencia de Calor y Materia, Energía Solar 1 y 2, Simulación de Procesos Termodinámicos en EERR, Secado Solar Industrial, Eficiencia Energética en la Industria, Domótica para Arquitectura Bioclimática.
- Experiencia: diseño de secadores solares de alimentos a amplia escala de producción.
- Software de simulación de referencia: **Simusol** (www.simusol.org), nivel experto.
- Experiencia de programación: Visual Basic y C++ (oxidado). Entiende lógica de Python pero requiere que Claude codee.
- Datos experimentales: dispone de mediciones de muchos secadores reales (a usar como casos de validación).
- **Acceso bibliográfico:** Biblioteca Electrónica MINCyT (CONICET) — paywall-free a Elsevier (J Food Eng, Drying Technology, Energy Convers Manag, Food Res Int), Wiley, Springer, Tandfonline.

**Hardware:**
- Notebook DELL G15 5515, Ryzen 5000, 32 GB DDR4, GeForce RTX 3050 4 GB.
- Sistema operativo: Fedora 44 con Plasma 6.6.4.
- IDE: VS Code instalado.
- Cuenta Claude Pro activa.

---

## 3. Decisiones técnicas tomadas

### 3.1 Stack tecnológico

| Área | Decisión |
|---|---|
| Lenguaje | Python 3 |
| Cálculo científico | NumPy, SciPy, Matplotlib, pvlib, pandas |
| Interfaz | **Streamlit** (renderizado en navegador, multidispositivo) |
| Motor de EDOs | `scipy.integrate.solve_ivp` |
| Datos climáticos | NASA POWER vía `pvlib.iotools.get_nasa_power` |
| Repositorio | GitHub (público desde el inicio) |
| Licencia | **MIT** |
| Deploy opcional | Streamlit Community Cloud (gratuito, conecta directo a GitHub) |

### 3.2 Idioma

Versión inicial: **español** completo (interfaz y código/comentarios). Bilingüe como mejora futura.

### 3.3 Sistema de unidades

**SI estricto en todo el cálculo interno.**

- Temperaturas: **Kelvin** en modelo y cálculos. Conversión a °C solo en frontera UI.
- Humedad del producto: **base seca** `X = m_agua / m_sólido_seco` [kg/kg ms]. UI puede ofrecer base húmeda con conversión automática.
- Humedad absoluta del aire: kg agua / kg aire seco.
- Humedad relativa: fracción [0,1] internamente, % en UI.
- Caudal másico: kg/s.
- Presión: Pa.
- Series temporales: `pandas.DataFrame` con `DatetimeIndex` tz-aware.

### 3.4 Convención de ángulos solares

- **Hacia el usuario:** convención Duffie & Beckman hemisferio sur. Acimut 0° = Sur. Pendiente 0° = horizontal.
- **Internamente (pvlib):** convención de navegación (0° = Norte, 90° = Este).
- **Almacenamiento:** grados, convención Duffie.
- Capa de conversión entre ambas convenciones — documentar para evitar bugs silenciosos.

### 3.5 Modelo físico de los colectores

- **Discretización espacial** a lo largo de la dirección de flujo (no Hottel-Whillier-Bliss estacionario simple).
- Motor numérico: `scipy.integrate.solve_ivp`.
- Optimización de largo: barrido paramétrico (v0) → `scipy.optimize` (futuro).
- Cámara: sistema EDO acoplado calor-masa. Decisión acople/desacople al recibir ecuaciones.

### 3.6 Validación

- Datos experimentales en `validation_data/`.
- Tests automáticos que validen modelos contra datos reales.

---

## 4. Arquitectura del software (pestañas)

### 4.1 Pestaña 1 — Inicio: tipología y modo de análisis

**Tipologías:**
- **(a) Caja:** hasta ~10 kg, convección natural, cámara = colector. `proyecto.colector = None`.
- **(b) Armario:** 0–100 kg, colector externo, circulación natural o forzada.
- **(c) Gran escala:** 100 kg – toneladas, forzada, banco de colectores.

**Decisión pendiente:** modular por tipología vs. modelo parametrizado único. Intuición: módulos separados con interfaz común. A confirmar al armar estructura de carpetas.

**Modos de análisis:**
- **(a) Diario:** un día (específico / más frío / más caluroso / solsticios y equinoccios).
- **(b) Anual:** 8760 h, requiere vectorización NumPy.

### 4.2 Pestaña 2 — Emplazamiento y recursos climáticos

Entradas: latitud, longitud, acimut, pendiente, altitud (opcional).
Datos NASA POWER: T_amb, GHI, DNI, DHI, WS2M, presión, HR, altitud.
Política de huecos: interpolación ≤3h, bloqueo + decisión usuario >3h.
Caché: parquet en `data/cache/nasa_power/{hash}.parquet`.
Salidas: gráficas de series + CSV descargable.

### 4.3–4.7 Pestañas 3–7

- P3: Colectores (discretización espacial, optimización de largo).
- P4: Cámara de secado (modelo acoplado calor-masa).
- P5: Sistema de calentamiento auxiliar.
- P6: Motores (solo convección forzada).
- P7: Resultados finales.

---

## 5. Modelo de datos central — COMPLETO (Tandas 1–5)

### 5.1 Filosofía

Dataclasses anidadas. Objeto raíz `Proyecto` en `st.session_state.proyecto`. No pydantic en v0.

### 5.2 Vista general

```
Proyecto
├── meta
├── configuracion
├── emplazamiento
├── clima
├── colector          (None si tipología CAJA)
├── camara
├── auxiliar          (None si sin auxiliar)
├── motor             (None si convección natural)
└── resultados
    ├── clima
    ├── colector
    ├── camara
    ├── auxiliar
    ├── motor
    └── global_
```

### 5.3 Separación entrada/salida y mecanismo de invalidación

Cada sección guarda solo entradas. `Resultados` guarda solo outputs calculados.

**`BloqueResultados`** — clase base de todos los sub-bloques de `Resultados`:
- `_stale: bool` — ¿desactualizado?
- `_hash_entradas: str | None` — SHA-256 de las entradas usadas en el último cálculo.
- `_timestamp: datetime | None` — cuándo se calculó (UTC).
- `_advertencias_runtime: list` — advertencias generadas durante el cálculo (post-solver).
- Métodos: `marcar_calculado(hash)`, `marcar_stale()`, `verificar_vigencia(hash_actual)`.

**`calcular_hash_entradas(*secciones)`** — SHA-256 sobre JSON serializado de las dataclasses de entrada relevantes. Barato (microsegundos).

**Grafo de invalidación:**

| Entrada modificada | Bloques a invalidar |
|---|---|
| emplazamiento | clima, colector, camara, motor, global |
| clima | colector, camara, motor, global |
| colector | colector, camara, motor, global |
| auxiliar | camara, motor, global |
| camara | camara, motor, global |
| motor | motor, global |

La irradiancia POA se calcula on-the-fly en el módulo de colector — `Clima` queda como "datos del sitio" puros.

### 5.4 Grafo de dependencias

```
emplazamiento → clima → colector → auxiliar ─┐
                           │                  ├→ camara → motor → global
                           └──────────────────┘
```

### 5.5 TANDA 1 — APROBADA — Meta, Configuracion, Emplazamiento, Clima

[Contenido sin cambios respecto a sesiones anteriores. Ver documentación de Tandas 1-2 para detalles de campos.]

**Resumen de dataclasses:**
- `Meta`: nombre, autor, fecha_creacion, fecha_modificacion, version_software, notas.
- `Configuracion`: tipologia (Enum), modo_analisis (Enum), dia_analisis, fecha_especifica.
- `Emplazamiento`: latitud_deg, longitud_deg, altitud_m, acimut_colector_deg, pendiente_colector_deg, zona_horaria.
- `Clima`: series temporales NASA POWER + CalidadClima (política de huecos).

### 5.6 TANDA 2 — APROBADA — Colector

[Contenido sin cambios. Ver documentación Tanda 2 para detalles de ColectorUnidad, BancoColectores, Chimenea, Colector.]

Catálogo de materiales v1 cerrado: 23 materiales en 5 categorías (4 cubiertas, 6 placas absorbentes, 5 aislantes, 4 fondos/carcasas, 4 materiales de chimenea).

Validaciones de `Colector` cerradas: ~12 errores duros + ~14 advertencias. Prefijos: `GEO_`, `MAT_`, `BANCO_`, `CHIM_`, `COHE_`. Dataclass `Advertencia` (frozen=True) con campos: codigo, severidad (INFO/WARNING/CRITICAL), mensaje, campo, sugerencia, contexto.

### 5.7 TANDA 3 PASO 1 — CERRADA — Camara

[Contenido sin cambios. Ver documentación Tanda 3 paso 1 para detalles de GeometriaCamara, ConstruccionCamara, ConfiguracionBandejas, ConfiguracionFlujo, CargaProducto, ModelosCamara.]

**Modelos de capa fina soportados** (tiempo `t` en minutos):
- `lewis`: MR = exp(-k·t)
- `page`: MR = exp(-k·t^n)
- `henderson`: MR = a·exp(-k·t)
- `midilli`: MR = a·exp(-k·t^n) + b·t
- `logaritmico`: MR = a·exp(-k·t) + c

**Modelos de isoterma soportados:**
- `gab`: X_eq = X_m·C·K·a_w / [(1-K·a_w)·(1-K·a_w + C·K·a_w)]
- `oswin`: X_eq = a·[a_w/(1-a_w)]^b
- `henderson`: 1 - a_w = exp(-c·T·X_eq^n)

### 5.8 TANDA 3 PASO 2 — EN CURSO — Catálogo de productos

**Flujo de trabajo (Sesión 7):** el usuario carga coeficientes de forma autónoma guiado por `PLANTILLA_REFERENCIA_CATALOGO.md` y las notas dentro de cada YAML. Claude ya no parsea PDFs (decisión de optimización de tokens).

**5 archivos YAML generados:**

| Archivo | Productos | Estado |
|---|---|---|
| `frutas.yaml` | manzana, durazno, yacón | manzana: 3 modelos CF (Sacilik 2006). yacón: Page+Midilli (Shi 2013) + GAB (Marques 2022). durazno: estructura vacía. |
| `hortalizas.yaml` | tomate, papa, cebolla, pimiento_rojo, zanahoria_rallada, perejil, apio, mandioca | Estructura vacía. apio: ESTIMADA_POR_ANALOGIA con perejil. |
| `hojas_aromaticas.yaml` | te_yerba, oregano, coca | Estructura vacía. coca: ESTIMADA_POR_ANALOGIA con te_yerba. |
| `legumbres_frutos.yaml` | algarroba | Estructura vacía. |
| `carnes.yaml` | charqui_vacuno | Estructura vacía. |

**Total: 16 productos.** (La bitácora anterior mencionaba 19 — discrepancia no resuelta. Verificar §5.9.10 original.)

**Decisiones de esquema:**
- `params` es diccionario plano `{k, n, a, b, c}` — esquema simple, sin extensión `sets_por_temperatura`.
- `propiedades_basicas` lleva `calidad_propiedades_basicas` y `fuente_propiedades_basicas` propios.
- `humedad_equilibrio_aire_seco`: fallback escalar cuando no hay isoterma calibrada.
- Estructura top-level: diccionario con clave = `producto_id`.

**DOIs verificados (verificación directa en PDF o fuente cruzada):**

| Paper | DOI |
|---|---|
| Sacilik & Elicin (2006) — manzana | `10.1016/j.jfoodeng.2005.03.024` |
| Kingsly et al. (2006) — durazno | `10.1111/j.1365-2621.2006.01210.x` |
| Shi et al. (2013) — yacón | `10.1016/j.enconman.2013.03.032` |
| Marques et al. (2022) — yacón | `10.1016/j.lwt.2022.113151` |
| Zarein et al. (2013) — manzana | `10.4172/2157-7110.1000247` |
| Kaymak-Ertekin & Gedik (2004) — isotermas | `10.1016/j.lwt.2003.10.012` |
| Doymaz & Bilici (2014) — durazno | `10.1515/ijfe-2014-0026` |

**Política de DOIs:** solo citar DOI verificado en PDF o fuente externa. Si no verificado: escribir `[DOI no verificado]`.

**Entregables de Tanda 3 paso 2:** `frutas.yaml`, `hortalizas.yaml`, `hojas_aromaticas.yaml`, `legumbres_frutos.yaml`, `carnes.yaml`, `shopping_list_bibliografica_tanda3.md`, `PLANTILLA_REFERENCIA_CATALOGO.md`.

### 5.9 TANDA 3 PASO 3 — CERRADA — Validaciones e invariantes de Camara

**14 errores duros** (prefijos: `GEO_`, `BAND_`, `FLUJO_`, `PROD_`, `MOD_`, `COHE_`):

| Código | Cuándo |
|---|---|
| `GEO_DIMENSIONES_NO_POSITIVAS` | dim ≤ 0 |
| `GEO_VOLUMEN_MINIMO` | vol < 0.01 m³ |
| `BAND_N_BANDEJAS_NO_POSITIVO` | n < 1 |
| `BAND_ESPESOR_NO_POSITIVO` | espesor ≤ 0 |
| `BAND_SEPARACION_INSUFICIENTE` | sep < espesor + 0.01 m |
| `FLUJO_CAUDAL_NO_POSITIVO` | Q ≤ 0 |
| `FLUJO_RECIRCULACION_NO_IMPLEMENTADA` | fraccion > 0 (v0) |
| `FLUJO_DIRECCION_NO_SOPORTADA` | dir ∉ {HORIZONTAL, VERTICAL_ASCENDENTE} |
| `PROD_MASA_NO_POSITIVA` | masa ≤ 0 |
| `PROD_HUMEDAD_INICIAL_NEGATIVA` | X_ini < 0 |
| `PROD_HUMEDAD_OBJETIVO_NEGATIVA` | X_obj < 0 |
| `PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL` | X_obj ≥ X_ini |
| `MOD_CAPA_FINA_NO_DISPONIBLE` | params null en catálogo |
| `MOD_ISOTERMA_NO_DISPONIBLE` | params null y sin fallback escalar |
| `COHE_BANDEJAS_NO_CABEN_EN_CAMARA` | n × sep > alto |
| `COHE_AREA_BANDEJA_EXCEDE_CAMARA` | A_band > largo×ancho |
| `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA` | carga > 20 kg/m²/bandeja |
| `COHE_TIPOLOGIA_CAJA_CON_COLECTOR` | CAJA + colector ≠ None (nivel Proyecto) |

**20 advertencias estáticas** (prefijos: `GEO_`, `CONS_`, `BAND_`, `FLUJO_`, `PROD_`, `INIO_`). Severidades: INFO, WARNING, CRITICAL.

Destacadas:
- `PROD_ISOTERMA_FALLBACK` (CRITICAL): sin isoterma calibrada, usa escalar.
- `PROD_HUMEDAD_OBJETIVO_INALCANZABLE` (CRITICAL): X_obj < X_eq × 0.95.
- `INIO_PRODUCTO_CARNE_SIN_ISOTERMA` (CRITICAL): carne sin isoterma → no se puede verificar a_w.
- `INIO_A_W_FINAL_INSEGURA` (CRITICAL, runtime): a_w ≥ 0.85 → producto microbiológicamente inestable.

**2 advertencias de runtime** (van a `Resultados.camara._advertencias_runtime`, no a `__post_init__`): `PROD_T_FUERA_RANGO_CALIBRACION`, `INIO_A_W_FINAL_INSEGURA`.

**Umbrales de diseño:** vol_min = 0.01 m³, espesor_max_capa_fina = 0.05 m, carga_max = 20 kg/m²/bandeja, v_min = 0.3 m/s, v_max = 3.0 m/s.

Entregable: `tanda3_paso3_validaciones_camara.md`.

### 5.10 TANDA 4 — CERRADA — Auxiliar y Motor

#### Auxiliar

```python
class TipoAuxiliar(Enum):
    RESISTENCIA_ELECTRICA = "RESISTENCIA_ELECTRICA"
    QUEMADOR_BIOMASA      = "QUEMADOR_BIOMASA"

class ModoOperacionAuxiliar(Enum):
    SERIE_POSCOLECTOR      = "SERIE_POSCOLECTOR"
    RESPALDO_INDEPENDIENTE = "RESPALDO_INDEPENDIENTE"
```

**Campos clave:** `tipo`, `modo_operacion`, `potencia_nominal_W`, `temperatura_maxima_salida_K`, `set_point_T_K`, `fraccion_potencia_operacion`, `disponible_nocturno`. Campos específicos de biomasa: `PCI_MJ_kg`, `eficiencia_quemador`, `consumo_biomasa_kg_h`. Campos de resistencia: `tension_V`, `corriente_maxima_A`.

**6 errores duros** (`AUX_`): potencia, T_max, set_point, fracción, biomasa sin PCI, PCI sin eficiencia.
**4 advertencias** (`AUX_`): T_max alta para producto, eficiencia quemador baja, resistencia sin tensión, respaldo sin disponibilidad nocturna.

#### Motor

```python
class TipoAccionamiento(Enum):
    MOTOR_ELECTRICO     = "MOTOR_ELECTRICO"
    EXTRACTOR_EOLICO    = "EXTRACTOR_EOLICO"
    CONVECCION_NATURAL  = "CONVECCION_NATURAL"  # → proyecto.motor = None
```

**Campos clave:** `tipo_accionamiento`, `caudal_volumetrico_m3_s`, `perdida_carga_total_Pa` (override o calculada de sub-componentes), `eficiencia_ventilador` (default 0.55), `eficiencia_motor` (default 0.85), `factor_servicio` (default 1.15), `tension_V`.

**Campos calculados en `__post_init__`:** `potencia_hidraulica_W`, `potencia_eje_W`, `potencia_electrica_W`, `potencia_a_instalar_W`, `corriente_nominal_A`.

**Estimación automática de ΔP ductos:** 20% de (ΔP_colector + ΔP_cámara) si no se especifica → advertencia `MOT_DUCTOS_ESTIMADOS` (INFO).

**6 errores duros** (`MOT_`): convección natural instanciada, caudal, eficiencias, factor servicio, extractor sin diámetro.
**6 advertencias** (`MOT_`): ductos estimados, potencia baja (<30W), potencia alta (>5kW), sin tensión, viento bajo para extractor.
**1 advertencia runtime** (`MOT_DELTA_P_REAL_DISTINTA_DISENO`): ΔP real difiere >30% de la de diseño.

Entregable: `tanda4_auxiliar_motor.md`.

### 5.11 TANDA 5 — CERRADA — Resultados (cierre del modelo de datos)

#### BloqueResultados (clase base)

```python
@dataclass
class BloqueResultados:
    _stale: bool = True
    _hash_entradas: str | None = None
    _timestamp: datetime | None = None
    _advertencias_runtime: list = field(default_factory=list)

    def marcar_calculado(self, hash_entradas: str) -> None: ...
    def marcar_stale(self) -> None: ...
    def verificar_vigencia(self, hash_entradas_actual: str) -> bool: ...
```

#### Sub-bloques y campos principales

**`ResultadosClima`:** series temporales NASA POWER procesadas (GHI, DNI, DHI, T_amb, HR, v_viento, P_atm) + estadísticos (T_media, E_total_MJ_m2, horas_sol_efectivas, fraccion_datos_validos).

**`ResultadosColector`:** perfil espacial (x_m, T_fluido_K, T_placa_K, T_cubierta_K, eta_local) + series temporales (T_salida_K, eta_global, Q_util_W, irradiancia_POA_W_m2) + globales (T_salida_media_K, eta_media, Q_util_total_MJ, largo_optimo_m).

**`ResultadosCamara`:** evolución temporal (tiempo_s, X_producto, MR_producto, T_aire_camara_K, HR_aire_camara_fraccion, omega_aire_kg_kg, tasa_secado_kg_s) + resultados clave (tiempo_secado_h, X_final_alcanzado, masa_agua_evaporada_kg, objetivo_alcanzado) + inocuidad (a_w_final, inocuidad_ok).

**`ResultadosAuxiliar`:** energia_aportada_MJ, fraccion_energia_total, horas_operacion. Biomasa: consumo_biomasa_kg, costo_estimado. Eléctrico: energia_electrica_kWh, costo_estimado.

**`ResultadosMotor`:** punto de operación (caudal, ΔP real, v_superficial) + potencias (hidráulica, eje, eléctrica, a instalar, corriente) + indicadores (eficiencia_sistema_ventilacion, potencia_especifica_W_kg_h).

**`ResultadosGlobal`:** balance energético completo (solar disponible, útil colector, auxiliar, total, secado) + indicadores (eficiencia_global_sistema, COP_secado, fraccion_solar, autonomia_solar_fraccion) + resumen del ciclo (tiempo_secado_h, masa_fresco/seco/evaporada, rendimiento_masa) + dimensiones del sistema + errores_cruzados.

#### Indicadores globales clave

- `eficiencia_global_sistema = energia_secado / energia_solar_disponible`
- `COP_secado = masa_agua_evaporada × Lv / energia_total_sistema` (valores típicos: 0.10–0.35)
- `potencia_especifica_W_kg_h` (W eléctricos por kg de agua evaporada por hora)

#### Validaciones cruzadas a nivel Proyecto (5 errores duros + 2 advertencias)

**Errores duros (`PROY_`):**
- `PROY_CAJA_CON_COLECTOR`: CAJA + colector ≠ None.
- `PROY_CAJA_CON_MOTOR`: CAJA + motor ≠ None.
- `PROY_AUXILIAR_SERIE_SIN_COLECTOR`: SERIE_POSCOLECTOR + colector = None.
- `PROY_MOTOR_SIN_CAMARA`: motor ≠ None + camara = None.
- `PROY_ANUAL_SIN_VECTORIZACION`: análisis anual + tipología CAJA (no implementado v0).

**Advertencias (`PROY_`):**
- `PROY_CAUDAL_INCONSISTENTE` (WARNING): motor vs cámara difieren >15%.
- `PROY_T_COLECTOR_EXCEDE_T_MAX_PRODUCTO` (CRITICAL, runtime): T_salida_max > T_max_recomendada del producto.

**Módulo `Proyecto.validar_coherencia_global()`** — se llama antes de cualquier cálculo.

#### Serialización

```python
def proyecto_a_json(proyecto: Proyecto, path: str) -> None:
    d = dataclasses.asdict(proyecto)
    json.dump(d, f, default=str, indent=2)
```

Deserialización completa (dict → dataclasses anidadas): trabajo futuro al armar el esqueleto.

#### Layout de módulos del core

```
core/
├── advertencias.py   → Advertencia, Severidad, BloqueResultados
├── proyecto.py       → Proyecto, Meta, Configuracion
├── emplazamiento.py  → Emplazamiento
├── clima.py          → Clima, CalidadClima
├── colector.py       → ColectorUnidad, BancoColectores, Chimenea, Colector
├── camara.py         → GeometriaCamara, ConstruccionCamara,
│                       ConfiguracionBandejas, ConfiguracionFlujo,
│                       CargaProducto, ModelosCamara, Camara
├── auxiliar.py       → Auxiliar, TipoAuxiliar, ModoOperacionAuxiliar
├── motor.py          → Motor, TipoAccionamiento
└── resultados.py     → Resultados, ResultadosClima, ResultadosColector,
                        ResultadosCamara, ResultadosAuxiliar,
                        ResultadosMotor, ResultadosGlobal
```

Entregable: `tanda5_resultados.md`.

---

## 6. Plan de trabajo acordado

**Antes de codear (COMPLETADO):**
1. ~~Definir el modelo de datos central~~ ✅ COMPLETO (Tandas 1–5).
2. Definir la **estructura de carpetas del repo** — PENDIENTE.
3. Definir **convenciones de código** — PENDIENTE.
4. Definir **lista de dependencias** (`requirements.txt`) — PENDIENTE.

**Una vez aprobado lo anterior:**
5. Esqueleto del proyecto: `requirements.txt`, `README.md`, `LICENSE`, módulos vacíos, `app.py` mínimo.
6. Crear repositorio en GitHub (público).
7. Codear pestaña por pestaña, **empezando por Pestaña 2** (emplazamiento y clima).

**Para cada tipología (cuando llegue su turno):**
8. El usuario aporta las ecuaciones diferenciales acopladas.
9. Claude codea los modelos numéricos.
10. Tests de validación contra `validation_data/`.

---

## 7. Tandas pendientes (orden acordado)

- **Tanda 3 paso 2 (EN CURSO):** el usuario carga coeficientes en los 5 archivos YAML de forma autónoma.
- **Estructura de carpetas + convenciones + `requirements.txt`** — siguiente tarea.
- **Esqueleto del repo** — después de aprobar estructura y convenciones.
- **Código:** pestaña 2 primero, luego 3, 4, 5, 6, 7.

---

## 8. Herramientas y aclaraciones operativas

- **Project knowledge:** solo contiene la bitácora (este archivo). Los PDFs de papers fueron retirados (Sesión 7, optimización de tokens). Los YAMLs de productos viven en la máquina del usuario.
- **Claude Code:** para usar cuando el repo tenga estructura. Opera sobre archivos reales con commits.
- **Notificaciones:** Claude no puede enviar notificaciones al OS/browser. Al terminar cada entregable grande se pone `✅ LISTO — [nombre]` al final del mensaje.
- **Tokens:** sin PDFs en Project knowledge el contexto por turno es significativamente más liviano. Reservar capacidad para el desarrollo del código.

---

## 9. Decisiones tomadas (síntesis completa)

### Tandas 1–2 (sesiones 1–5)
[Ver versiones anteriores para el detalle. Resumen:]
- Stack tecnológico, idioma, unidades, convenciones de ángulos.
- Dataclasses sobre dict, no pydantic.
- Separación entrada/salida con `Resultados` espejo.
- Invalidación por hash de entradas.
- Estructura `Colector` completa con catálogo de 23 materiales.
- Sistema de advertencias con `Advertencia` (frozen=True) y `Severidad` (Enum).

### Sesión 6 (Tanda 3 paso 2 abierta)
- [x] Estrategia A+C para catálogo de productos (usuario consigue PDFs, Claude extrae).
- [x] Modelos de capa fina: Page + Midilli como mínimo.
- [x] Default + 1-2 alternativas en notas (no catálogo ancho).
- [x] `te_yerba`: entrada única, default yerba mate.
- [x] `apio`: ESTIMADA_POR_ANALOGIA con perejil.
- [x] `yacón`: default Shi 2013.
- [x] Esquema YAML: diccionario top-level con clave = `producto_id`.
- [x] `propiedades_basicas` lleva `calidad_propiedades_basicas` y `fuente_propiedades_basicas`.
- [x] `humedad_equilibrio_aire_seco`: fallback escalar.

### Sesión 7 (cambio de flujo + YAMLs estructura vacía)
- [x] Flujo de carga cambiado: usuario carga coeficientes de forma autónoma (optimización de tokens).
- [x] PDFs retirados del Project knowledge.
- [x] `params` esquema simple (diccionario plano, sin `sets_por_temperatura`).
- [x] 4 archivos YAML de estructura vacía generados.
- [x] `PLANTILLA_REFERENCIA_CATALOGO.md` generada.
- [x] DOI falso corregido (`10.1016/j.jfoodeng.2005.05.052` no era Doymaz sobre durazno). DOI correcto de Doymaz sobre durazno: `10.1515/ijfe-2014-0026`.
- [x] Política de DOIs: solo citar verificado.

### Sesión 8 (Tandas 3 paso 3, 4 y 5)
- [x] **Tanda 3 paso 3 cerrada:** 14 errores duros + 20 advertencias para `Camara`. 2 advertencias de runtime.
- [x] **Tanda 4 cerrada:** `Auxiliar` (6 errores duros + 4 advertencias) + `Motor` (6 errores duros + 6 advertencias + 1 runtime). Motor calcula potencias en `__post_init__`. ΔP ductos = 20% si no especificada.
- [x] **Tanda 5 cerrada:** `Resultados` espejo con 6 sub-bloques. `BloqueResultados` como clase base con mecanismo de hash. Grafo de invalidación explícito. 5 errores duros + 2 advertencias a nivel `Proyecto`. `COP_secado` como indicador global.
- [x] **Modelo de datos central COMPLETO.**

---

## 10. Decisiones pendientes

- [ ] **Modular por tipología vs. modelo parametrizado único:** confirmar al armar estructura de carpetas.
- [ ] **Acople vs. desacople colector-cámara:** decidir al recibir las ecuaciones del usuario.
- [ ] **Tipología CAJA:** modelo físico distinto. Definir cuando llegue su turno.
- [ ] **Conteo de productos:** bitácora anterior menciona 19, catálogo actual tiene 16. Verificar lista canónica.
- [ ] **Durazno sin coeficientes de CF:** conseguir Doymaz & Bilici 2014 (`10.1515/ijfe-2014-0026`).
- [ ] **Manzana sin isoterma:** conseguir Kaymak-Ertekin & Gedik 2004 (`10.1016/j.lwt.2003.10.012`).
- [ ] **Poblar catálogo de productos** (Tanda 3 paso 2 EN CURSO — autónomo).
- [ ] **Estructura de carpetas del repo** — siguiente tarea de Claude.
- [ ] **Convenciones de código** — junto con estructura de carpetas.
- [ ] **`requirements.txt`** — junto con estructura de carpetas.
- [ ] **Esqueleto del repo** — después de aprobar lo anterior.

---

## 11. Próximo paso al retomar

**Estructura de carpetas + convenciones de código + `requirements.txt` + esqueleto del repo.**

Abrir con:

> *"Retomemos. El modelo de datos central está completo (Tandas 1–5 aprobadas). Sigamos con la estructura de carpetas del repo, las convenciones de código y el requirements.txt."*

O si el usuario ya cargó algunos coeficientes en los YAMLs:

> *"Cargué coeficientes para [productos]. Revisalos antes de seguir con la estructura del repo."*
