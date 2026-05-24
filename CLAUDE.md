# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Iniciar la aplicación Streamlit
.venv/bin/python -m streamlit run Secasol.py

# Ejecutar todos los tests
.venv/bin/python -m pytest

# Ejecutar un archivo de tests específico
.venv/bin/python -m pytest tests/test_core/test_colector.py

# Ejecutar un test individual
.venv/bin/python -m pytest tests/test_calculos/test_colector_calc.py::TestHVientoMcAdams::test_formula_exacta_3ms

# Tests con output detallado
.venv/bin/python -m pytest -v

# Formato y linting (correr antes de commitear)
.venv/bin/python -m black .
.venv/bin/python -m ruff check .
```

El entorno virtual está en `.venv/`. Siempre prefijá los comandos de Python con `.venv/bin/python`.

## Convenciones de trabajo

**Control de versiones:** se trabaja en el repo local (working tree) por defecto, sin commits ni push, salvo que el usuario indique explícitamente que quiere commitear o subir a GitHub. Los cambios quedan visibles vía `git diff` y pueden descartarse con `git restore` si hace falta. Solo cuando el usuario lo pida explícitamente se arman commits (y solo cuando lo pida explícitamente se hace `git push`).

## Deploy (desde S33)

El repo de GitHub es **privado** (`gonzalo-duran/Secasol26-secadores-solares`). La app se despliega en **Hugging Face Spaces** (`gonzalojduran/Secasol26`) vía Docker + template Streamlit. Cada `git push` a `main` dispara `.github/workflows/deploy_hf.yml`, que sincroniza el código al Space y rebuildea automáticamente la imagen. Compañeros acceden por URL pública (`https://huggingface.co/spaces/gonzalojduran/Secasol26`) sin instalar nada y sin ver el código.

Implicancia operativa: **un push a `main` actualiza la app en producción**. Si hay que pushear cambios que no deberían llegar a producción todavía, usar rama distinta de `main`. El secreto `HF_TOKEN` está en GitHub → Settings → Secrets and variables → Actions. La carpeta `Secasol26/` en raíz es el clon local del Space (gitignoreada) — históricamente se usaba para deploy manual; el Action volvió obsoleto el push manual.

## Arquitectura

La aplicación es un **prediseñador de secadores solares** (Streamlit). El usuario configura el sistema pestaña a pestaña; cada pestaña escribe en un objeto `Proyecto` central guardado en `st.session_state.proyecto`.

### Capas (separación estricta)

```
Secasol.py                ← entry point Streamlit, construye las pestañas
ui/p{1-7}_*.py            ← UI por pestaña, llaman a core/ y calculos/
ui/componentes/           ← widgets reutilizables (header, gráficas, unidades, serialización)
ui/reporte.py             ← generación de reporte PDF (P7)
core/                     ← dataclasses del modelo de datos (sin Streamlit)
calculos/                 ← motores numéricos puros (sin Streamlit)
catalogo/materiales/*.yaml ← catálogos de materiales (cubiertas, placas, aislantes, fondos)
catalogo/productos/*.yaml  ← productos a secar
validacion/               ← scripts de validación física (HWB, Klein) — fuera del pipeline UI
tests/                    ← pytest (suite extensa, ver bitácora más reciente para conteo actual)
data/cache/nasa_power/    ← caché parquet de NASA POWER (gitignoreado)
docs/bitacora/            ← bitácoras de sesión (registro histórico de decisiones)
docs/mapa_conexiones.md   ← mapa widget → campo → consumidor (mantenido manualmente)
assets/                   ← logos institucionales para el header y el reporte PDF
```

**Regla clave:** `core/` y `calculos/` no importan `streamlit`. La UI es la única que lo usa. `validacion/` puede importar de `core/` y `calculos/` pero no de `ui/`.

### Objeto raíz

`core/proyecto.py` define `Proyecto`, el único objeto en `st.session_state`. Tiene secciones opcionales:

```
Proyecto
├── meta: Meta
├── configuracion: Configuracion  (Tipología: CAJA / ARMARIO / GRAN_ESCALA)
├── emplazamiento: Emplazamiento
├── clima: Clima
├── colector: Colector            ← None para tipología CAJA
├── camara: Camara
├── auxiliar: Auxiliar            ← None si sin auxiliar
├── motor: Motor                  ← None si convección natural
├── chimenea: Chimenea            ← None si motor presente; top-level desde S30
└── resultados: Resultados
```

`Chimenea` es **top-level** (no subcomponente de `Colector`) desde la sesión 30. Esto permite chimenea solar también en tipología CAJA. Los snapshots `.json` antiguos que la traen bajo `colector.chimenea` la restauran automáticamente en `proyecto.chimenea` durante la deserialización.

### Colector solar (`core/colector.py`)

El sistema de colectores tiene jerarquía propia:
```
Colector
├── unidad: ColectorUnidad   ← geometría + materiales de un módulo
└── banco: BancoColectores   ← configuración serie/paralelo
```

Los materiales se validan contra `catalogo/materiales/` en `__post_init__`. El catálogo se carga en `core/catalogo.py` al importar el módulo (no en `__init__`).

### Sistema de advertencias

`core/advertencias.py` define:
- `Advertencia` (frozen dataclass): código con prefijo de sección (ej. `GEO_LARGO_PEQUENO`), severidad INFO/WARNING/CRITICAL, mensaje, campo, sugerencia, contexto.
- `BloqueResultados`: clase base para resultados con hash SHA-256 para detectar desactualización (stale).

Las advertencias estáticas de diseño se generan en funciones separadas (`advertencias_colector()` en `core/colector.py`, `advertencias_camara()` en `core/camara.py`, etc.), no bloquean la instanciación pero deben mostrarse antes de calcular.

### Motores numéricos del colector (`calculos/`)

Cuatro tipos de colector de placa plana:
- **Tipo 1** (`colector_calc.py`): canal único, absorbedor en fondo, flujo por encima.
- **Tipos 2, 3, 4** (`colector_tipos234_calc.py`): absorbedor a media altura, variantes de canal activo/estanco.

Todos usan modelo cuasi-estacionario: `scipy.integrate.solve_ivp` (EDO del fluido en x) + `scipy.optimize.fsolve` (sistema no lineal de superficies en cada nodo, con warm-start).

El modelo soporta **doble cubierta con cavidad de aire** vía `n_cubiertas + espaciado_entre_cubiertas_m`, propagados a los 4 motores a través del helper `_U_cubierta_efectiva` (Hollands para convección natural en cavidad + radiación gris entre superficies paralelas).

`espesor_placa_m` está expuesto en la UI pero **no entra al balance térmico** — el modelo asume capacitancia térmica de la placa despreciable. Decisión consciente al cierre de la S30 (ver `docs/mapa_conexiones.md`).

`calculos/correlaciones_nusselt.py` es el catálogo de correlaciones de convección (Shah-London, Heaton, Gnielinski, Sparrow-Liu, Dittus-Boelter, Cengel-Ghajar, Hollands). La función `calcular_h_int()` selecciona automáticamente según Re y L/Dh, o usa la indicada por el usuario.

El solver de colector recibe **POA** (radiación en plano del colector, transposición Liu-Jordan con `pvlib`), no GHI. Esto vale en todos los pipelines: P3 horario/diario, P3 constantes, P7 constantes, P7 transitorio con clima real.

### Motores numéricos de cámara — tres motores con dispatcher

`Camara.modo_calculo: Literal["capa_fina", "termodinamico"]` selecciona uno de dos motores físicos. El dispatcher único vive en `calculos/camara_calc.py::calcular_camara()`:

| Modo | Módulo | Modelo físico | Estado de resultado |
|------|--------|---------------|---------------------|
| `capa_fina` (default) | `camara_calc.py::calcular_tiempo_secado_estatico` | Lewis/Page/Henderson-Pabis/Midilli/Logarítmico con k constante; X_eq por GAB con HR_media | `ResultadosCamara`, `t_secado_s: float`, `masa_agua_extraida_kg` |
| `termodinamico` | `camara_termodinamica.py::simular_secado` | Balance acoplado calor-masa, EDOs `[T_prod, X_prod]` + 4 algebraicas, evaporación difusiva `ṁ_w = h_m·A·(ω_sat(T_prod)·a_w − ω_flujo)`, CSTR | `ResultadoMotorTermodinamico`, `t_secado_s: float | None` (None si no convergió), `masa_evaporada_total_kg` |

**Operación anual de cámara** (cascada A + B, solo con `modo_calculo == "termodinamico"` y `modo_analisis == ANUAL`): el módulo `calculos/operacion_anual_camara.py` corre `simular_secado` sobre el día típico de cada mes (promedio horario desde NASA POWER vía `clima_calc.dia_tipo_mensual`), estima `T_salida_colector` con modelo lineal `T_amb + η_col·POA·A / (ṁ·c_p)` (Opción A), y calcula las 4 eficiencias de Augustus Leon (`calculos/eficiencias_camara.py`: η_drying, η_pickup, η_térmica, η_total). El usuario configura `batches_por_mes` en P4 vía `Camara.operacion_anual: OperacionAnualConfig`. Resumen anual en P4 + tabla mensual + barras en P7.

Las divergencias entre las dos firmas de resultado se abstraen en `balance_global._extraer_t_y_masa()` y `ui/p7_resultados._resumen_camara()`. Cualquier cambio en una firma requiere actualizar ambos helpers — no hay error de tipo que lo avise.

`camara_calc.py` también contiene la lógica de pared compuesta vía `ConstruccionCamara.pared` (capas con resistencia térmica agregada), techo translúcido con Q_rad cuando está activo, y bandejas (Ergun para pérdida de carga en lecho).

### Acople con `balance_global` y lazo Picard

`calculos/balance_global.py` orquesta todo el cálculo. Funciones principales:

- `calcular_todo(proyecto, T_amb_K, I_g_W_m2, v_viento_ms, T_entrada_K, HR_camara)` — modo Constantes. Devuelve `ResultadosCompletos`.
- `calcular_todo_transitorio(proyecto, clima_anual, dia_criterio)` — modo Transitorio sobre horizonte horario. Devuelve `ResultadosCompletosTransitorio`.
- `armar_forzantes_aire(...)` — construye `ForzantesAire` (T_ent, ω_ent, ṁ, GHI sobre techo cámara, **POA sobre plano colector**, T_amb, v_viento) consumido por motor TD y dinámico.
- `construir_serie_sintetica_dia_tipo(...)` — serie 24 h sintética para diario sin clima real.

**Lazo natural por chimenea** (cuando `motor=None` y `chimenea` presente): Picard cerrado `T_chim ↔ ṁ_nat ↔ T_salida_colector`. Si la chimenea tiene `extractor_activo`, el balance suma además `ΔP_turbina_motriz(v_viento(t))` al lado motriz y `Kt·ρ·v_flujo²/2` al resistivo — el extractor es accesorio de la chimenea, no tipo de motor (`TipoAccionamiento` solo tiene MOTOR_ELECTRICO y CONVECCION_NATURAL desde S31).
- *Modo Constantes*: 10 iter máx, tol 0.5 K. Re-corre el colector estacionario en cada iteración mutando `velocidad_diseno_ms` (try/finally restaura el valor original).
- *Modo Transitorio*: Picard sobre todo el horizonte, 5 iter máx, tol 0.5 K. Por iteración: `_caudal_natural_horizonte` calcula ṁ(t) hora a hora; `_correr_colector_horizonte` re-corre el solver del colector cada hora con v efectiva `ṁ_nat(t) / (ρ · A_canal · n_par)`; motor TD consume las nuevas forzantes; `T_flujo(t)` realimenta T_chim(t).

Si POA no está disponible (forzante sintética, clima incompleto), el balance cae a GHI con aviso explícito `ADV_PICARD_POA_NO_DISPONIBLE`.

### Pestañas (`ui/`)

- **P1** `p1_tipologia.py` — tipología (CAJA/ARMARIO/GRAN_ESCALA), modo de análisis (DIARIO/ANUAL), criterio de día. Cascada: cambiar a CAJA anula colector y motor con aviso.
- **P2** `p2_emplazamiento.py` — lat/lon/altitud/acimut/pendiente/tz. Descarga NASA POWER vía `calculos/clima_calc.py`. Gráficas POA vs GHI.
- **P3** `p3_colector.py` — tipo (1–4), cubierta(s), placa, aislante, fondo, geometría, banco. Botón de evaluación gráfica diaria y anual con tránsito SPA y POA máx.
- **P4** `p4_camara.py` — geometría, pared (compuesta con capas), techo translúcido opcional, bandejas, flujo, carga de producto, selector de modo de cálculo, horizonte (modo transitorio). En `modo_analisis == ANUAL` con motor termodinámico, aparece la sección "Operación anual" con slider de batches/mes y card resumen anual (4 métricas).
- **P5** `p5_auxiliar.py` — auxiliar eléctrico o biomasa, modo de operación, setpoint, η, PCI.
- **P6** `p6_motor.py` — motor eléctrico (axial/centrífugo) o chimenea solar (cuando motor OFF). La chimenea puede equiparse opcionalmente con un **extractor eólico** (turbina sombrero chino) en el tope, que agrega al balance del lazo natural un término motriz `Cp·ρ·v_viento²/2` (con corrección logarítmica del viento NASA POWER de 10 m a la altura del tope) y un término resistivo `Kt·ρ·v_flujo²/2`. Estima ΔP del sistema.
- **P7** `p7_resultados.py` — orquesta `calcular_todo` o `calcular_todo_transitorio`, muestra dashboard integrado, exporta JSON/TXT/PDF del proyecto. Sugerencia automática de irradiancia: quantile 90 de POA representativa. Si P4 calculó operación anual, agrega panel detalle mensual: tabla 12 meses con t_secado, m_evap/batch, kg/mes y las 4 eficiencias + barras kg/mes con línea η_total.

`Secasol.py` es el entry point que monta `st.set_page_config`, llama a `ui.componentes.header.render_header()`, inicializa `st.session_state.proyecto`, y construye las 7 pestañas con `st.tabs([...])`.

### Convención de unidades (crítico)

**Todo lo que circula por `core/` y `calculos/` está en SI estricto:**
- Temperatura en K (no °C)
- Presión en Pa (no kPa)
- Humedad relativa como fracción 0–1 (no %)
- Humedad absoluta ω en kg_agua/kg_aire_seco
- Humedad del producto X en kg_agua/kg_seco (base seca)
- Tiempo en s (los parámetros cinéticos del catálogo vienen en min⁻¹ y se convierten en el motor: `k_SI = k_cat / 60.0`)
- Caudal másico en kg/s; volumétrico en m³/s
- Ángulos en grados (°) pero con convención Duffie (ver abajo)

**La única conversión de unidades ocurre en `ui/componentes/unidades.py`**, incluyendo la conversión de ángulos entre convenciones.

### Convención de ángulos (crítico)

Hay tres convenciones y **no deben mezclarse**:
- **Duffie & Beckman** (almacenamiento en `Emplazamiento`, lógica de cálculo): acimut γ: 0° = Sur, +90° = Oeste, −90° = Este. Rango [−180, +180].
- **UI360** (entrada del usuario en P2 desde S20): 0° = Norte, sentido horario. Rango [0, 360).
- **pvlib** (cálculo interno de irradiancia): surface_azimuth ψ: 0° = Norte, 90° = Este, 180° = Sur. Rango [0, 360).

Conversiones (todas en `ui/componentes/unidades.py`, **nunca en `core/` ni `calculos/`**):
- Duffie → UI360: `α = (−γ) mod 360`
- UI360 → Duffie: `γ = (−α) mod 360`; si γ > 180: γ −= 360
- Duffie → pvlib: `ψ = (180 + γ) mod 360`
- pvlib → Duffie: `γ = (ψ − 180) mod 360`; si γ > 180: γ −= 360

### Datos climáticos (`calculos/clima_calc.py`)

Descarga datos horarios anuales de **NASA POWER** vía `pvlib.iotools.get_nasa_power`. Caché parquet con clave SHA-256 por (lat, lon, año). Política de huecos: interpolación lineal en tiempo para huecos ≤ 3 h; huecos > 3 h se dejan NaN y `CalidadClima.n_horas_bloqueadas > 0` indica que la UI debe pedir decisión al usuario.

Conversiones NASA POWER → SI realizadas en el módulo (no en `core/`):
- Temperatura: °C → K (+273.15)
- Presión: kPa → Pa (×1000)
- HR: % → fracción (÷100)
- GHI/DNI/DHI [W/m²] y viento [m/s]: sin conversión.

Helper compartido `calcular_POA_horizonte` aplica transposición Liu-Jordan con pvlib (mismo modelo usado por P3 y por el lazo natural del transitorio).

### Convenciones de código

- Archivos/módulos: `snake_case`. Clases: `PascalCase`. Funciones/variables: `snake_case`.
- Variables físicas con sufijo de unidad: `largo_m`, `T_salida_K`, `Q_util_W`, `m_evap_kg_s`.
- Constantes: `SCREAMING_SNAKE_CASE` — `T_AMB_K`, `_RUGOSIDAD_DEFAULT_M`.
- Docstrings: Google style, en español, obligatorio en `core/` y `calculos/`.
- Type hints obligatorios. `from __future__ import annotations` en todos los módulos de core/ y calculos/.
- `ValueError` con código de error como prefijo en `__post_init__` (ej. `MOT_CAUDAL_NO_POSITIVO`). `RuntimeError` en errores de cálculo.
- Tests con imports absolutos (`from calculos.modulo import ...`). Sin hacks de `sys.path`. `conftest.py` gestiona el path.
- Black `line-length=100`, target-version `py311`. Ruff reglas E, F, I, W (ignora E501 — lo maneja black). Configuración en `pyproject.toml`.

### Stack y dependencias

Python 3.11+. Streamlit (UI), NumPy/SciPy/pandas (cálculo), pvlib (datos solares y POA), pyarrow (caché parquet), plotly (gráficas interactivas; matplotlib ya no se usa desde S23-S29), PyYAML (catálogos), reportlab + kaleido 0.2.x (reporte PDF). Ver `requirements.txt` y `requirements-dev.txt`.

### Tests

Suite con pytest. Estructura: `tests/test_core/` para validaciones de dataclasses, `tests/test_calculos/` para motores numéricos, `tests/test_ui/` para helpers de UI testeables sin servidor. Validación física del modelo de colector en `validacion/` (HWB, Klein) — scripts standalone que confirman R² = 1.0000 vs el modelo lineal de Hottel-Whillier-Bliss.

Un test por validación dura. Nombre del test = nombre del código de error en minúsculas cuando aplica (ej. `test_MOT_CAUDAL_NO_POSITIVO`).

### Documentación viva

- `docs/bitacora/bitacora_sesion{N}.md` — registro cronológico por sesión. La última bitácora siempre tiene el estado más actualizado (conteo de tests, trabajo no commiteado, pendientes).
- `docs/mapa_conexiones.md` — tabla widget → campo → consumidor, mantenida manualmente. Útil para detectar widgets huérfanos y campos sin UI.
- `docs/notas/` — especificaciones técnicas puntuales (ej. `especificacion_motor_dinamico_camara.md`).
- `CHANGELOG.md` — versiones liberadas con Added/Changed/Fixed.
- `Balance_de_calor_y_masa_en_camara_ampliado.md` (raíz) — derivación física de las ecuaciones del motor termodinámico de cámara.

Antes de cambios estructurales grandes, consultar la bitácora más reciente para entender el contexto histórico de las decisiones.
