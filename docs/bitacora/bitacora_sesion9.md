# BITÁCORA — SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

**Última actualización:** Sesión 9 (Estructura de carpetas, convenciones, requirements.txt y esqueleto del repo — COMPLETOS. Entorno de desarrollo local operativo.)  
**Estado:** Modelo de datos central 100% definido (Tandas 1–5). Esqueleto del repo generado y operativo. Entorno de desarrollo local configurado (Fedora 44, Python 3.12, venv, VS Code con plugins). Tanda 3 paso 2 EN CURSO (catálogo de productos — el usuario carga coeficientes de forma autónoma). Siguiente paso: codear Pestaña 2 (emplazamiento y clima).

---

## 1\. Contexto y objetivo del proyecto

Software de **prediseño** (no simulación detallada tipo Simusol, ni diseño mecánico final) de secadores solares de alimentos, orientado a usuarios técnicos con formación en transferencia de calor.

**Usuario destinatario:** Ingenieros y estudiantes del curso de posgrado "Secadores Solares" de la Maestría en Energías Renovables (M.E.R.), Facultad de Ciencias Exactas, UNSa, Argentina.

**Espíritu del proyecto:** Académico, comunitario, abierto. Pensado para compartirse vía GitHub entre colegas, alumnos y comunidad científica.

**Nivel de modelado:** Complejidad media. Suficiente para tomar decisiones de ingeniería de prediseño (dimensiones, áreas, caudales, potencias auxiliares) pero sin pretender reemplazar simulación nodal completa.

---

## 2\. Perfil del desarrollador (referencia para Claude)

- Licenciado en Física, Doctor en Ciencias especialidad Energías Renovables.  
- Investigador Adjunto CONICET, INENCO–UNSa.  
- Docente de Transferencia de Calor y Materia (5° año Lic. Física y Lic. Energías Renovables).  
- Docente posgrado M.E.R.–UNSa: Transferencia de Calor y Materia, Energía Solar 1 y 2, Simulación de Procesos Termodinámicos en EERR, Secado Solar Industrial, Eficiencia Energética en la Industria, Domótica para Arquitectura Bioclimática.  
- Experiencia: diseño de secadores solares de alimentos a amplia escala de producción.  
- Software de simulación de referencia: **Simusol** ([www.simusol.org](http://www.simusol.org)), nivel experto.  
- Experiencia de programación: Visual Basic y C++ (oxidado). Entiende lógica de Python pero requiere que Claude codee.  
- Datos experimentales: dispone de mediciones de muchos secadores reales (a usar como casos de validación).  
- **Acceso bibliográfico:** Biblioteca Electrónica MINCyT (CONICET) — paywall-free a Elsevier (J Food Eng, Drying Technology, Energy Convers Manag, Food Res Int), Wiley, Springer, Tandfonline.

**Hardware:**

- Notebook DELL G15 5515, Ryzen 5000, 32 GB DDR4, GeForce RTX 3050 4 GB.  
- Sistema operativo: Fedora 44 con Plasma 6.6.4.  
- IDE: VS Code instalado desde repositorio oficial Microsoft (RPM), **no Flatpak**.  
- Cuenta Claude Pro activa.

---

## 3\. Decisiones técnicas tomadas

### 3.1 Stack tecnológico

| Área | Decisión |
| :---- | :---- |
| Lenguaje | Python 3.12 (desarrollo local) / 3.11 mínimo declarado en pyproject.toml |
| Cálculo científico | NumPy, SciPy, Matplotlib, pvlib, pandas |
| Interfaz | **Streamlit** (renderizado en navegador, multidispositivo) |
| Motor de EDOs | `scipy.integrate.solve_ivp` |
| Datos climáticos | NASA POWER vía `pvlib.iotools.get_nasa_power` |
| Repositorio | GitHub (público desde el inicio) |
| Licencia | **MIT** |
| Deploy opcional | Streamlit Community Cloud (gratuito, conecta directo a GitHub) |

**Nota sobre versión de Python:** se desarrolla en Python 3.12 (nativo de Fedora 44). El proyecto declara 3.11 como versión mínima soportada en `pyproject.toml` para compatibilidad con colegas en Ubuntu 22.04+, Debian 12+. No se usan features exclusivas de 3.12.

### 3.2 Idioma

Versión inicial: **español** completo (interfaz y código/comentarios). Bilingüe como mejora futura.

### 3.3 Sistema de unidades

**SI estricto en todo el cálculo interno.**

- Temperaturas: **Kelvin** en modelo y cálculos. Conversión a °C solo en frontera UI.  
- Humedad del producto: **base seca** `X = m_agua / m_sólido_seco` \[kg/kg ms\]. UI puede ofrecer base húmeda con conversión automática.  
- Humedad absoluta del aire: kg agua / kg aire seco.  
- Humedad relativa: fracción \[0,1\] internamente, % en UI.  
- Caudal másico: kg/s.  
- Presión: Pa.  
- Series temporales: `pandas.DataFrame` con `DatetimeIndex` tz-aware.

### 3.4 Convención de ángulos solares

- **Hacia el usuario:** convención Duffie & Beckman hemisferio sur. Acimut 0° \= Sur. Pendiente 0° \= horizontal.  
- **Internamente (pvlib):** convención de navegación (0° \= Norte, 90° \= Este).  
- **Almacenamiento:** grados, convención Duffie.  
- Capa de conversión entre ambas convenciones en `ui/componentes/unidades.py` — documentar para evitar bugs silenciosos.

### 3.5 Modelo físico de los colectores

- **Discretización espacial** a lo largo de la dirección de flujo (no Hottel-Whillier-Bliss estacionario simple).  
- Motor numérico: `scipy.integrate.solve_ivp`.  
- Optimización de largo: barrido paramétrico (v0) → `scipy.optimize` (futuro).  
- Cámara: sistema EDO acoplado calor-masa. Decisión acople/desacople al recibir ecuaciones.

### 3.6 Validación

- Datos experimentales en `validation_data/`.  
- Tests automáticos que validen modelos contra datos reales.

---

## 4\. Arquitectura del software (pestañas)

### 4.1 Pestaña 1 — Inicio: tipología y modo de análisis

**Tipologías:**

- **(a) Caja:** hasta \~10 kg, convección natural, cámara \= colector. `proyecto.colector = None`.  
- **(b) Armario:** 0–100 kg, colector externo, circulación natural o forzada.  
- **(c) Gran escala:** 100 kg – toneladas, forzada, banco de colectores.

**Modos de análisis:**

- **(a) Diario:** un día (específico / más frío / más caluroso / solsticios y equinoccios).  
- **(b) Anual:** 8760 h, requiere vectorización NumPy.

### 4.2 Pestaña 2 — Emplazamiento y recursos climáticos

Entradas: latitud, longitud, acimut, pendiente, altitud (opcional). Datos NASA POWER: T\_amb, GHI, DNI, DHI, WS2M, presión, HR, altitud. Política de huecos: interpolación ≤3h, bloqueo \+ decisión usuario \>3h. Caché: parquet en `data/cache/nasa_power/{hash}.parquet`. Salidas: gráficas de series \+ CSV descargable.

### 4.3–4.7 Pestañas 3–7

- P3: Colectores (discretización espacial, optimización de largo).  
- P4: Cámara de secado (modelo acoplado calor-masa).  
- P5: Sistema de calentamiento auxiliar.  
- P6: Motores (solo convección forzada).  
- P7: Resultados finales.

---

## 5\. Modelo de datos central — COMPLETO (Tandas 1–5)

### 5.1 Filosofía

Dataclasses anidadas. Objeto raíz `Proyecto` en `st.session_state.proyecto`. No pydantic en v0.

### 5.2 Vista general

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

    └── global\_

### 5.3 Separación entrada/salida y mecanismo de invalidación

Cada sección guarda solo entradas. `Resultados` guarda solo outputs calculados.

**`BloqueResultados`** — clase base de todos los sub-bloques de `Resultados`:

- `_stale: bool` — ¿desactualizado?  
- `_hash_entradas: str | None` — SHA-256 de las entradas usadas en el último cálculo.  
- `_timestamp: datetime | None` — cuándo se calculó (UTC).  
- `_advertencias_runtime: list` — advertencias generadas durante el cálculo (post-solver).  
- Métodos: `marcar_calculado(hash)`, `marcar_stale()`, `verificar_vigencia(hash_actual)`.

**`calcular_hash_entradas(*secciones)`** — SHA-256 sobre JSON serializado de las dataclasses de entrada relevantes.

**Grafo de invalidación:**

| Entrada modificada | Bloques a invalidar |
| :---- | :---- |
| emplazamiento | clima, colector, camara, motor, global |
| clima | colector, camara, motor, global |
| colector | colector, camara, motor, global |
| auxiliar | camara, motor, global |
| camara | camara, motor, global |
| motor | motor, global |

### 5.4 Grafo de dependencias

emplazamiento → clima → colector → auxiliar ─┐

                           │                  ├→ camara → motor → global

                           └──────────────────┘

### 5.5 TANDA 1 — APROBADA — Meta, Configuracion, Emplazamiento, Clima

**Resumen de dataclasses:**

- `Meta`: nombre, autor, fecha\_creacion, fecha\_modificacion, version\_software, notas.  
- `Configuracion`: tipologia (Enum), modo\_analisis (Enum), dia\_analisis, fecha\_especifica.  
- `Emplazamiento`: latitud\_deg, longitud\_deg, altitud\_m, acimut\_colector\_deg, pendiente\_colector\_deg, zona\_horaria.  
- `Clima`: series temporales NASA POWER \+ CalidadClima (política de huecos).

### 5.6 TANDA 2 — APROBADA — Colector

Catálogo de materiales v1 cerrado: 23 materiales en 5 categorías (4 cubiertas, 6 placas absorbentes, 5 aislantes, 4 fondos/carcasas, 4 materiales de chimenea).

Validaciones de `Colector` cerradas: \~12 errores duros \+ \~14 advertencias. Prefijos: `GEO_`, `MAT_`, `BANCO_`, `CHIM_`, `COHE_`. Dataclass `Advertencia` (frozen=True) con campos: codigo, severidad (INFO/WARNING/CRITICAL), mensaje, campo, sugerencia, contexto.

### 5.7 TANDA 3 PASO 1 — CERRADA — Camara

**Modelos de capa fina soportados** (tiempo `t` en minutos):

- `lewis`: MR \= exp(-k·t)  
- `page`: MR \= exp(-k·t^n)  
- `henderson`: MR \= a·exp(-k·t)  
- `midilli`: MR \= a·exp(-k·t^n) \+ b·t  
- `logaritmico`: MR \= a·exp(-k·t) \+ c

**Modelos de isoterma soportados:**

- `gab`: X\_eq \= X\_m·C·K·a\_w / \[(1-K·a\_w)·(1-K·a\_w \+ C·K·a\_w)\]  
- `oswin`: X\_eq \= a·\[a\_w/(1-a\_w)\]^b  
- `henderson`: 1 \- a\_w \= exp(-c·T·X\_eq^n)

### 5.8 TANDA 3 PASO 2 — EN CURSO — Catálogo de productos

**Flujo de trabajo:** el usuario carga coeficientes de forma autónoma guiado por `PLANTILLA_REFERENCIA_CATALOGO.md` y las notas dentro de cada YAML.

**5 archivos YAML:**

| Archivo | Productos | Estado |
| :---- | :---- | :---- |
| `frutas.yaml` | manzana, durazno, yacón | manzana: 3 modelos CF (Sacilik 2006). yacón: Page+Midilli (Shi 2013\) \+ GAB (Marques 2022). durazno: estructura vacía. |
| `hortalizas.yaml` | tomate, papa, cebolla, pimiento\_rojo, zanahoria\_rallada, perejil, apio, mandioca | Estructura vacía. apio: ESTIMADA\_POR\_ANALOGIA con perejil. |
| `hojas_aromaticas.yaml` | te\_yerba, oregano, coca | Estructura vacía. coca: ESTIMADA\_POR\_ANALOGIA con te\_yerba. |
| `legumbres_frutos.yaml` | algarroba | Estructura vacía. |
| `carnes.yaml` | charqui\_vacuno | Estructura vacía. |

**Total: 16 productos.** (Discrepancia pendiente con conteo anterior de 19 — verificar.)

**Decisiones de esquema:**

- `params` es diccionario plano `{k, n, a, b, c}`.  
- `propiedades_basicas` lleva `calidad_propiedades_basicas` y `fuente_propiedades_basicas` propios.  
- `humedad_equilibrio_aire_seco`: fallback escalar cuando no hay isoterma calibrada.  
- Estructura top-level: diccionario con clave \= `producto_id`.

**DOIs verificados:**

| Paper | DOI |
| :---- | :---- |
| Sacilik & Elicin (2006) — manzana | `10.1016/j.jfoodeng.2005.03.024` |
| Kingsly et al. (2006) — durazno | `10.1111/j.1365-2621.2006.01210.x` |
| Shi et al. (2013) — yacón | `10.1016/j.enconman.2013.03.032` |
| Marques et al. (2022) — yacón | `10.1016/j.lwt.2022.113151` |
| Zarein et al. (2013) — manzana | `10.4172/2157-7110.1000247` |
| Kaymak-Ertekin & Gedik (2004) — isotermas | `10.1016/j.lwt.2003.10.012` |
| Doymaz & Bilici (2014) — durazno | `10.1515/ijfe-2014-0026` |

**Política de DOIs:** solo citar DOI verificado en PDF o fuente externa.

### 5.9 TANDA 3 PASO 3 — CERRADA — Validaciones e invariantes de Camara

**14 errores duros** \+ **20 advertencias estáticas** \+ **2 advertencias de runtime.**

Errores duros destacados (prefijos `GEO_`, `BAND_`, `FLUJO_`, `PROD_`, `MOD_`, `COHE_`): dimensiones no positivas, volumen mínimo, bandejas no caben en cámara, área bandeja excede cámara, carga excede capacidad geométrica, modelo de capa fina no disponible, isoterma no disponible, recirculación no implementada (v0), tipología CAJA con colector.

Advertencias runtime: `PROD_T_FUERA_RANGO_CALIBRACION`, `INIO_A_W_FINAL_INSEGURA` (a\_w ≥ 0.85 → producto microbiológicamente inestable, CRITICAL).

**Umbrales de diseño:** vol\_min \= 0.01 m³, espesor\_max\_capa\_fina \= 0.05 m, carga\_max \= 20 kg/m²/bandeja, v\_min \= 0.3 m/s, v\_max \= 3.0 m/s.

### 5.10 TANDA 4 — CERRADA — Auxiliar y Motor

**Auxiliar:**

- `TipoAuxiliar`: RESISTENCIA\_ELECTRICA, QUEMADOR\_BIOMASA.  
- `ModoOperacionAuxiliar`: SERIE\_POSCOLECTOR, RESPALDO\_INDEPENDIENTE.  
- 6 errores duros (`AUX_`) \+ 4 advertencias.

**Motor:**

- `TipoAccionamiento`: MOTOR\_ELECTRICO, EXTRACTOR\_EOLICO, CONVECCION\_NATURAL (→ proyecto.motor \= None).  
- Campos calculados en `__post_init__`: potencia\_hidraulica\_W, potencia\_eje\_W, potencia\_electrica\_W, potencia\_a\_instalar\_W, corriente\_nominal\_A.  
- Estimación automática ΔP ductos: 20% de (ΔP\_colector \+ ΔP\_cámara) si no se especifica → advertencia `MOT_DUCTOS_ESTIMADOS` (INFO).  
- 6 errores duros (`MOT_`) \+ 6 advertencias \+ 1 advertencia runtime.

### 5.11 TANDA 5 — CERRADA — Resultados (cierre del modelo de datos)

**Sub-bloques:** ResultadosClima, ResultadosColector, ResultadosCamara, ResultadosAuxiliar, ResultadosMotor, ResultadosGlobal. Todos heredan de BloqueResultados.

**Indicadores globales clave:**

- `eficiencia_global_sistema = energia_secado / energia_solar_disponible`  
- `COP_secado = masa_agua_evaporada × Lv / energia_total_sistema` (valores típicos: 0.10–0.35)  
- `potencia_especifica_W_kg_h`

**Validaciones cruzadas a nivel Proyecto (5 errores duros \+ 2 advertencias):**

- `PROY_CAJA_CON_COLECTOR`, `PROY_CAJA_CON_MOTOR`, `PROY_AUXILIAR_SERIE_SIN_COLECTOR`, `PROY_MOTOR_SIN_CAMARA`, `PROY_ANUAL_SIN_VECTORIZACION`.  
- `PROY_CAUDAL_INCONSISTENTE` (WARNING), `PROY_T_COLECTOR_EXCEDE_T_MAX_PRODUCTO` (CRITICAL, runtime).

**Serialización:** `proyecto_a_json()` vía `dataclasses.asdict()` \+ `json.dump()`. Deserialización: trabajo futuro.

**Layout de módulos del core (IMPLEMENTADO en esqueleto):**

core/

├── advertencias.py   → Advertencia, Severidad, BloqueResultados  ← CON CÓDIGO REAL

├── proyecto.py       → Proyecto, Meta, Configuracion              ← CON CÓDIGO REAL

├── emplazamiento.py  → Emplazamiento                              ← esqueleto

├── clima.py          → Clima, CalidadClima                        ← esqueleto

├── colector.py       → ColectorUnidad, BancoColectores, ...       ← esqueleto

├── camara.py         → GeometriaCamara, ..., Camara               ← esqueleto

├── auxiliar.py       → Auxiliar, TipoAuxiliar, ...                ← esqueleto

├── motor.py          → Motor, TipoAccionamiento                   ← esqueleto

└── resultados.py     → Resultados, ResultadosClima, ...           ← esqueleto

---

## 6\. Estructura de carpetas del repo — APROBADA (Sesión 9\)

secador\_solar/

├── app.py                            ← entry point Streamlit (CON CÓDIGO REAL)

├── requirements.txt

├── requirements-dev.txt

├── pyproject.toml                    ← config black \+ ruff \+ pytest

├── README.md

├── LICENSE                           ← MIT

├── .gitignore

├── core/                             ← modelo de datos (sin UI)

├── calculos/                         ← motores numéricos (sin UI)

├── catalogo/

│   ├── materiales/materiales\_v1.yaml

│   └── productos/                    ← 5 YAMLs de productos

├── ui/

│   ├── p1\_tipologia.py ... p7\_resultados.py

│   └── componentes/

│       ├── advertencias\_widget.py

│       ├── unidades.py               ← ÚNICA capa de conversión UI↔core

│       └── graficas.py

├── data/cache/nasa\_power/            ← .parquet cacheados (en .gitignore)

├── validation\_data/

├── tests/

│   ├── conftest.py                   ← CON CÓDIGO REAL (fixtures)

│   ├── test\_core/

│   │   └── test\_proyecto\_coherencia.py ← CON CÓDIGO REAL (3 tests)

│   └── test\_calculos/

└── docs/

    ├── SETUP\_GIT.md

    └── bitacora/

**Decisión sobre tipologías:** modelo parametrizado único (no archivos separados por tipología). La diferenciación ocurre dentro de cada función de cálculo mediante condicionales sobre `proyecto.configuracion.tipologia`.

---

## 7\. Convenciones de código — APROBADAS (Sesión 9\)

### Nombres

- Archivos y módulos: `snake_case`  
- Clases: `PascalCase`  
- Funciones y variables: `snake_case`  
- Variables físicas: sufijo de unidad cuando no es obvia — `largo_m`, `T_salida_K`, `Q_util_W`  
- Constantes: `SCREAMING_SNAKE_CASE` — `VERSION_SOFTWARE`, `T_AMB_K`

### Regla de oro de unidades

**Todo lo que entra a `core/` y `calculos/` está en SI.** Las conversiones viven exclusivamente en `ui/componentes/unidades.py`. Funciones con nombres explícitos: `celsius_a_kelvin()`, `acimut_duffie_a_pvlib()`, etc.

### Docstrings

Google style, en español. Obligatorio en todas las funciones de `core/` y `calculos/`.

### Type hints

Obligatorios en todas las firmas de `core/` y `calculos/`. `from __future__ import annotations` en todos los módulos de core/.

### Estructura de funciones de cálculo

Reciben dataclasses de `core/`, devuelven el sub-bloque de `Resultados` correspondiente ya marcado con `marcar_calculado()`.

### Separación UI / lógica

Ningún `import streamlit` en `core/` ni `calculos/`. Ningún cálculo físico en `ui/`.

### session\_state

Un único objeto raíz: `st.session_state.proyecto` de tipo `Proyecto`.

### Manejo de errores

- Validación de entrada: `ValueError` con código de error como prefijo en `__post_init__`.  
- Errores de cálculo: `RuntimeError`.  
- En UI: los `ValueError` se capturan y muestran con `st.error()`.

### Tests

Un test por validación dura. Nombre del test \= nombre del código en minúsculas.

### Formato y linting

- **Black** `line-length = 100`, `target-version = ["py311"]`  
- **Ruff** con reglas E, F, I, W (ignora E501 — lo maneja black)  
- Configuración en `pyproject.toml`

---

## 8\. Entorno de desarrollo local — OPERATIVO (Sesión 9\)

- **OS:** Fedora 44, Plasma 6.6.4  
- **Python:** 3.12 nativo del sistema (instalado vía dnf)  
- **venv:** `~/proyectos/secador_solar/.venv`  
- **VS Code:** instalado desde repositorio oficial Microsoft (RPM). Plugins instalados: Python, Pylance, Black Formatter, Ruff, debugpy, autoDocstring (Google style), YAML, TOML, GitLens.  
- **`.vscode/settings.json`:** format on save con black, organize imports con ruff, pytest integrado, autoDocstring Google style.  
- **`.vscode/launch.json`:** configuraciones de debug para Streamlit y pytest.  
- **Tests:** 3 tests pasan (`test_proyecto_coherencia.py`).  
- **Repo GitHub:** pendiente de crear (instrucciones en `docs/SETUP_GIT.md`).

---

## 9\. Plan de trabajo acordado

**COMPLETADO:**

1. ✅ Definir el modelo de datos central (Tandas 1–5).  
2. ✅ Definir la estructura de carpetas del repo.  
3. ✅ Definir convenciones de código.  
4. ✅ Definir lista de dependencias (`requirements.txt`).  
5. ✅ Esqueleto del proyecto generado y operativo localmente.

**PENDIENTE:**

6. Crear repositorio en GitHub (público) — instrucciones en `docs/SETUP_GIT.md`.  
7. Codear **Pestaña 2** (emplazamiento y clima) — **PRÓXIMO PASO**.  
8. Pestaña por pestaña: 3, 4, 5, 6, 7\.  
9. Para cada tipología: el usuario aporta las EDOs, Claude codea, tests de validación.

---

## 10\. Decisiones pendientes

- [ ] **Conteo de productos:** bitácora anterior menciona 19, catálogo actual tiene 16\. Verificar lista canónica.  
- [ ] **Durazno sin coeficientes de CF:** conseguir Doymaz & Bilici 2014 (`10.1515/ijfe-2014-0026`).  
- [ ] **Manzana sin isoterma:** conseguir Kaymak-Ertekin & Gedik 2004 (`10.1016/j.lwt.2003.10.012`).  
- [ ] **Poblar catálogo de productos** (Tanda 3 paso 2 EN CURSO — autónomo).  
- [ ] **Acople vs. desacople colector-cámara:** decidir al recibir las ecuaciones del usuario.  
- [ ] **Tipología CAJA:** modelo físico distinto. Definir cuando llegue su turno.  
- [ ] **Deserialización** (dict → dataclasses anidadas): trabajo futuro.

---

## 11\. Herramientas y aclaraciones operativas

- **Project knowledge:** solo contiene la bitácora (este archivo). Los PDFs de papers fueron retirados (Sesión 7). Los YAMLs de productos viven en la máquina del usuario.  
- **Claude Code:** disponible para cuando el repo esté en GitHub. Opera sobre archivos reales con commits.  
- **Tokens:** sin PDFs en Project knowledge el contexto por turno es significativamente más liviano.

---

## 12\. Próximo paso al retomar

**Crear el repo en GitHub y arrancar con el código de la Pestaña 2 (emplazamiento y clima).**

Abrir con:

*"Retomemos. El entorno está operativo. Vamos con el código de la Pestaña 2."*

O si ya creaste el repo en GitHub:

*"Repo creado en GitHub. Vamos con la Pestaña 2."*

O si cargaste coeficientes en los YAMLs:

*"Cargué coeficientes para \[productos\]. Revisalos antes de seguir con la Pestaña 2."*  
