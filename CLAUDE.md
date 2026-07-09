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

El workflow copia una **whitelist** de carpetas (`Secasol.py`, `ui/`, `calculos/`, `core/`, `assets/`, `catalogo/`, `manual/`) — al agregar una carpeta top-level nueva que la app necesite en runtime, hay que sumarla al `deploy_hf.yml` (así se agregó `manual/` para el manual de usuario; `docs/` NO se deploya).

Implicancia operativa: **un push a `main` actualiza la app en producción**. Si hay que pushear cambios que no deberían llegar a producción todavía, usar rama distinta de `main`. El secreto `HF_TOKEN` está en GitHub → Settings → Secrets and variables → Actions. La carpeta `Secasol26/` en raíz es el clon local del Space (gitignoreada) — históricamente se usaba para deploy manual; el Action volvió obsoleto el push manual.

**El deploy NO es hermético — dos gotchas críticos (S46):**
- **`requirements.txt` debe estar pinneado con `==`.** El Dockerfile del Space corre `pip install -r requirements.txt` en cada rebuild; con rangos `>=` HF resolvía a versiones distintas de las del entorno local → **mismos código/clima/inputs daban resultados numéricos distintos** (el solver de cámara convergía a basura). Pin a las versiones del `.venv` local. El panel **"🔧 Entorno"** en el sidebar (`Secasol.py::_diagnostico_entorno`) muestra Python + versiones para comparar local vs remoto de un vistazo. (Nota: el pin fija las librerías, NO el Python — HF usa el del Dockerfile, `python:3.13.5-slim`.)
- **El `file_uploader` (carga de `.json`) requiere XSRF desactivado en HF.** Detrás del proxy de HF Spaces, la protección XSRF de Streamlit rechaza la subida con `AxiosError: 403`. El `ENTRYPOINT` del **Dockerfile del Space** (lado HF, NO en el repo) lleva `--server.enableXsrfProtection=false` (todo en una sola línea). El deploy desde GitHub **preserva** ese Dockerfile, así que el flag persiste; el Dockerfile no se versiona en el repo.

## Arquitectura

La aplicación es un **prediseñador de secadores solares** (Streamlit). El usuario configura el sistema pestaña a pestaña; cada pestaña escribe en un objeto `Proyecto` central guardado en `st.session_state.proyecto`.

### Capas (separación estricta)

```
Secasol.py                ← entry point Streamlit, construye las pestañas
ui/p{1-7}_*.py            ← UI por pestaña, llaman a core/ y calculos/
ui/componentes/           ← widgets reutilizables (header, gráficas, unidades, serialización)
ui/reporte.py             ← generación de reporte PDF (P7)
ui/manual.py              ← vista del manual de usuario (?manual=<slug>, estilo SAM)
ui/idiomas/{es,en,pt}/*.yaml ← diccionarios de traducción (i18n, ver §Internacionalización)
manual/capitulos/<lang>/*.md ← contenido del manual (22 capítulos; ES completo, EN/PT parciales F9)
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

Desde S36 el coeficiente convectivo interno se calcula **localmente nodo a nodo** (no un escalar único): `nusselt_forzado_local` (entrada térmica + blending continuo de régimen en Re=2300/10000), `nusselt_natural_canal` y `nusselt_mixto_local` (convección mixta de Churchill para baja velocidad/vertical). Las propiedades del aire dejan de ser constantes a 323 K: `calculos/propiedades_aire.py` da `k(T), μ(T), Pr(T), cp(T), ρ(T,P)` evaluadas en `T_f(x)`. El helper de orquestación `colector_calc.coef_conveccion_interna_local()` (reusado por los Tipos 2/3/4) combina propiedades locales + Nu local + flotación (Ra con `g·sin β` y ΔT del warm-start). El caudal másico se fija con `ρ(T_entrada)`.

El solver de colector recibe **POA** (radiación en plano del colector, transposición Liu-Jordan con `pvlib`), no GHI. Esto vale en todos los pipelines: P3 horario/diario, P3 constantes, P7 constantes, P7 transitorio con clima real.

### Motor numérico de cámara — motor único (termodinámico)

Desde **S38** la cámara tiene un **único** motor físico: el balance acoplado calor-masa. El punto de entrada es `calculos/camara_calc.py::calcular_camara()`, que arma los parámetros desde el objeto `Camara` y delega en `camara_termodinamica.py::simular_secado`:

| Módulo | Modelo físico | Estado de resultado |
|--------|---------------|---------------------|
| `camara_termodinamica.py::simular_secado` | Balance acoplado calor-masa, EDOs `[T_prod, X_prod]` + 4 algebraicas, evaporación difusiva `ṁ_w = h_m·A·(ω_sat(T_prod)·a_w − ω_flujo)`, CSTR | `ResultadoMotorTermodinamico`, `t_secado_s: float | None` (None si no convergió), `masa_evaporada_total_kg` |

**Coeficientes de transporte variables en el tiempo (S39):** `h_conv` interior y `K_m` ya **no se congelan**. `simular_secado` acepta `coef_transporte_func(T_ent(t), T_prod(t), ω_ent(t), ṁ(t)) → (h_conv, K_m)` (closure construido en `camara_calc._calcular_termodinamico` con placa plana + Chilton-Colburn, película en `(T_ent+T_prod)/2`), evaluado por paso. Reevaluar desde cantidades conocidas al inicio del paso no rompe la linealidad del sistema algebraico (`resolver_estado_camara` sin cambios). Si el callable es `None`, se usan los escalares congelados (back-compat: tests que llaman `simular_secado` directo con escalares no cambian). **Consecuencia:** en modos Sintético/Día real/Anual los sliders T_op/HR_op de P4 ya **no influyen** en el cálculo (borde y coeficientes salen del clima/colector); solo son condición de borde en modo Constantes. Ver `docs/bitacora/bitacora_sesion39.md`.

El antiguo motor de **capa fina** (correlaciones empíricas MR(t) de Lewis/Page/Henderson-Pabis/Midilli/Logarítmico) fue **eliminado en S38**: era un evaluador de punto único a temperatura pico, insensible al espesor de lecho y a la velocidad de aire reales, sin temperaturas ni flujos, y desacoplado de los pipelines transitorio/multidía/anual (ver `docs/bitacora/bitacora_sesion38.md`). El campo `Camara.modo_calculo` quedó **vestigial** (back-compat de snapshots): `Camara.__post_init__` coacciona cualquier `"capa_fina"` heredado a `"termodinamico"`. `modelo_capa_fina` es vestigial puro (no lo lee nadie para calcular); `modelo_isoterma` es semi-vestigial (lo usa la validación/advertencias de `core/camara.py`, pero el TD hardcodea `"gab"`). **Ojo:** los bloques `capa_fina:` de los catálogos **no son inertes** — `_modelos_disponibles()` los lee para filtrar qué productos aparecen en el selector de P4 (`_productos_disponibles`); borrarlos sacaría productos del dropdown. El detalle de la deuda vestigial está en `docs/bitacora/bitacora_sesion38.md` §170.

**Operación anual de cámara** (cascada A + B, solo con `modo_analisis == ANUAL`): el módulo `calculos/operacion_anual_camara.py` corre `simular_secado` sobre el día típico de cada mes (promedio horario desde NASA POWER vía `clima_calc.dia_tipo_mensual`), estima `T_salida_colector` con modelo lineal `T_amb + η_col·POA·A / (ṁ·c_p)` (Opción A), y calcula las 4 eficiencias de Augustus Leon (`calculos/eficiencias_camara.py`: η_drying, η_pickup, η_térmica, η_total). El usuario configura `batches_por_mes` en P4 vía `Camara.operacion_anual: OperacionAnualConfig`. Resumen anual en P4 + tabla mensual + barras en P7.

La firma del resultado de cámara (`ResultadoMotorTermodinamico`) se accede uniformemente vía `balance_global.resumen_camara()` (reusado por `_extraer_t_y_masa` y `ui/p7_resultados._resumen_camara()`).

`camara_calc.py` también contiene la lógica de pared compuesta vía `ConstruccionCamara.pared` (capas con resistencia térmica agregada), techo translúcido con Q_rad cuando está activo, y bandejas (Ergun para pérdida de carga en lecho).

**Techo translúcido — ganancia + pérdida (S44):** el techo translúcido aporta `Q_rad = I_g·τ·α·A_rad` **y** una pérdida conductiva del vidriado. `ConstruccionCamara.cubierta_translucida_espesor_m` (default 6 mm) define `U_techo = 1/(1/h_conv + espesor/k_efectivo + 1/h_w)` (k del mapa `k_efectivo_por_espesor_mm` del catálogo para el alveolar). `camara_calc` **descuenta la cara del techo de la envolvente opaca** `A_cuerpo` (para no doble-contar) y pasa `R_cond_techo`/`A_techo` a `resolver_estado_camara`, que suma `UA_techo` al balance de `T_flujo` (el diagnóstico `q_pared` queda como pared opaca). Techo opaco → `A_techo=0`, sin efecto.

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

### Modo industrial / gran escala (`GRAN_ESCALA`, S40)

Desde **S40** la tipología `GRAN_ESCALA` es funcional (antes era cosmética, idéntica a `ARMARIO`). Tiene **dos subtipos de igual jerarquía** en `Configuracion.subtipo_gran_escala` (`SubtipoGranEscala`): **BATCH** (lotes) y **SEMICONTINUO** (túnel a contracorriente estilo ADITAL). La referencia física es el secador híbrido ADITAL de San Carlos (tesis doctoral del usuario, cap. 3).

- **Período = ventana** (`ModoAnalisis.VENTANA`): lapso `[ventana_inicio, ventana_fin]` con clima real horario, en vez del binario DIARIO/ANUAL (que se mantiene para CAJA/ARMARIO). **Desde S44**, `VENTANA` también está disponible para **CAJA/ARMARIO** como **multidía real**: P7 enruta el pipeline de producción (`_render_ventana` con banco/caño/túnel) **solo** en `GRAN_ESCALA`; para CAJA/ARMARIO cae al transitorio normal (`calcular_todo_transitorio`) con forzantes del lapso construidas por `p4_camara._construir_forzantes_ventana` (reusa la maquinaria de "días reales consecutivos").
- **Motor de cámara multi-etapa unificado** (`camara_termodinamica.simular_cascada`): batch y semicontinuo son **el mismo motor** con distinta topología. Batch = cascada de N=1 zona; semicontinuo = N zonas en serie con aire a contracorriente y avance de columnas por cadencia fija (`Camara.tunel: ConfiguracionTunel` con `n_zonas` + `intervalo_avance_h`). La sequedad de salida es **emergente** (no se fuerza `X_objetivo`). Régimen transitorio sin Picard intra-paso (producto cuasi-congelado en el paso). Punto de entrada `camara_calc.calcular_camara_cascada`; reusa intacto el núcleo físico (evaporación difusiva + GAB + coeficientes variables en t de S39).
- **Caño maestro** (`core.colector.BancoColectores.cano_maestro: CanoMaestro`): manifold de sección creciente que colecta el aire de las ramas del banco. `calculos/cano_maestro_calc.py` da ΔP (fricción Haaland + accesorios), ΔT térmica (pérdida convectiva McAdams + aporte solar en la cara superior) y uniformidad de distribución. **Gotcha:** el default `CanoMaestro.absortancia_solar=0.90` es de chapa pintada; el galvanizado desnudo necesita α≈0.35 (ver `validacion/validacion_adital.py`).
- **Híbrido con calendario de arranque** (`core.auxiliar.Auxiliar.cargas_arranque: list[CargaArranque]`): el quemador opera en ventanas horarias de mañana/atardecer (independiente de la irradiancia) en vez de potencia constante, y acumula leña. Lo consume `auxiliar_calc.calcular_auxiliar_transitorio` vía `_mascara_calendario`, usado tanto por el pipeline transitorio (DIARIO/multi-día) como por el de ventana.
- **Orquestación**: `simulacion_ventana.simular_ventana` despacha batch↔cascada según el subtipo y acumula producción (kg seco + tasa de régimen kg/día + leña). `balance_global.calcular_todo_ventana(proyecto, clima_datos_df)` es el punto de entrada de P7: `armar_forzantes_ventana` arma las forzantes horarias (colector forzado hora a hora + ΔT caño maestro + auxiliar con calendario) y delega en `simular_ventana`.
- **Validación**: `validacion/validacion_adital.py` (standalone, fuera de pytest) contrasta la cadena térmica contra los datos de campo de ADITAL (4/4 checks: salida colector ~55/78 °C, caño maestro ΔT −2.8 °C, cámara 57 °C, campaña 5000 kg en ~5 días).

### Pestañas (`ui/`)

- **P1** `p1_tipologia.py` — tipología (CAJA/ARMARIO/GRAN_ESCALA), modo de análisis (DIARIO/ANUAL/**VENTANA**), criterio de día. Cascada: cambiar a CAJA anula colector y motor con aviso. En `GRAN_ESCALA` (S40): selector de **subtipo** (Batch/Semicontinuo) y de **ventana de producción** (inicio/fin + presets 1 semana / 1 mes / campaña).
- **P2** `p2_emplazamiento.py` — lat/lon/altitud/acimut/pendiente/tz. Descarga NASA POWER vía `calculos/clima_calc.py`. Gráficas POA vs GHI.
- **P3** `p3_colector.py` — tipo (1–4), cubierta(s), placa, aislante, fondo, geometría, banco. En `GRAN_ESCALA` (S40): sección **caño maestro** (manifold) dentro del expander de banco, con preview de ΔP. Botón de evaluación gráfica diaria y anual con tránsito SPA y POA máx.
- **P4** `p4_camara.py` — geometría, pared (compuesta con capas), techo translúcido opcional, bandejas, flujo, carga de producto, selector de modo de cálculo, horizonte (modo transitorio). En `modo_analisis == ANUAL` con motor termodinámico, aparece la sección "Operación anual" con slider de batches/mes y card resumen anual (4 métricas). En subtipo **SEMICONTINUO** (S40): sección **topología del túnel** (n_zonas + cadencia de avance) → `Camara.tunel`.
- **P5** `p5_auxiliar.py` — auxiliar eléctrico o biomasa, modo de operación, setpoint, η, PCI. Expander opcional **calendario de arranque** (S40, híbrido mañana/tarde) → `Auxiliar.cargas_arranque`.
- **P6** `p6_motor.py` — motor eléctrico (axial/centrífugo) o chimenea solar (cuando motor OFF). La chimenea puede equiparse opcionalmente con un **extractor eólico** (turbina sombrero chino) en el tope, que agrega al balance del lazo natural un término motriz `Cp·ρ·v_viento²/2` (con corrección logarítmica del viento NASA POWER de 10 m a la altura del tope) y un término resistivo `Kt·ρ·v_flujo²/2`. Estima ΔP del sistema; en `GRAN_ESCALA` (S40) el ΔP del **caño maestro** se suma a ductos.
- **P7** `p7_resultados.py` — orquesta `calcular_todo`, `calcular_todo_transitorio` o **`calcular_todo_ventana`** (modo VENTANA, S40), muestra dashboard integrado, exporta JSON/TXT/PDF del proyecto. Sugerencia automática de irradiancia: quantile 90 de POA representativa. Si P4 calculó operación anual, agrega panel detalle mensual. En modo VENTANA (gran escala): **dashboard de producción** (producto seco, tasa de régimen, leña + perfil espacial del túnel en semicontinuo).

`Secasol.py` es el entry point que monta `st.set_page_config`, llama a `ui.componentes.header.render_header()`, inicializa `st.session_state.proyecto`, y construye las 7 pestañas con `st.tabs([...])`.

### Manual de usuario (mejora 36, estilo SAM)

Con `?manual=<slug>` en la URL, `Secasol.py` intercepta **antes** de inicializar `proyecto` y renderiza `ui/manual.py` (con `st.stop()` al final). **La vista manual es stateless: nunca toca `st.session_state.proyecto`.** Los botones "📖 Manual" de P1–P7 (`ui/componentes/manual_link.py::boton_manual`) y el enlace del sidebar abren SIEMPRE con `target=_blank` — un clic sin `_blank` desde la vista de diseño recargaría la app y perdería el proyecto.

- Contenido: `manual/capitulos/<lang>/*.md` (22 capítulos por idioma; **ES completo obligatorio**, EN/PT parciales — la traducción es F9). `manual_contenido.ruta_capitulo(archivo, lang)` resuelve el .md con **fallback a ES** y devuelve `(ruta, es_fallback)`; si cae al ES el visor muestra el aviso `manual.ui.solo_es`. TOC declarativo (slug → archivo → parte) en `ui/componentes/manual_contenido.py` (sin imports de streamlit, testeable). El **orden de navegación lo fija la tupla `CAPITULOS`**, no el número de archivo. Al agregar un capítulo: crear el .md **en `es/`** + declararlo en `CAPITULOS` + enlazarlo desde algún capítulo (los tests exigen que ninguno quede aislado).
- **i18n del visor (F8):** el chrome se traduce vía `manual.ui.*`; los títulos del TOC vía `manual.toc.<slug>.titulo/.descripcion` con **fallback al ES de la tupla** (`traducir(..., default=cap.titulo)` — por eso no hay claves `manual.toc.*`/`manual.parte.*` hasta F9). El idioma sale de `idioma_actual()` (query param `?lang=` en la pestaña del manual, que es sesión nueva). **Todos los enlaces del manual propagan `&lang=`** (sidebar, índice, breadcrumb, prev/next, `boton_manual`/`enlace_manual_inline`, el enlace global de `Secasol.py`, y los enlaces internos del markdown reescritos por `manual._propagar_lang`). El deploy copia `manual/` recursivo → las subcarpetas por idioma viajan sin cambios en `deploy_hf.yml`.
- Sintaxis propia de los .md (parseada por `ui/componentes/manual_render.py`, funciones puras + `render_bloques`): bloques `<!-- profundidad: Título -->…<!-- /profundidad -->` → `st.expander` (segundo nivel de lectura); `<!-- esquema: nombre | caption -->` → `mostrar_esquema`; anclas explícitas `## Título {#ancla}` → `st.header(anchor=)`; enlaces internos `[texto](?manual=slug#ancla)`; ecuaciones KaTeX `$`/`$$` nativas de `st.markdown`.
- `tests/test_ui/test_manual.py` valida integridad: TOC↔disco, sintaxis de profundidad, que todo enlace/ancla/esquema resuelva, `$$` balanceado, higiene de URLs. Al agregar un capítulo: crear el .md + declararlo en `CAPITULOS`.

### Internacionalización (i18n, desde S49)

La UI es multiidioma **ES/EN/PT** (plan completo en `docs/notas/plan_i18n.md`; fases F0–F8
hechas, F9 —traducción de los 22 capítulos del manual— pendiente). Arquitectura:
`ui/componentes/traducciones.py` (loader puro, sin
streamlit: aplana `ui/idiomas/<lang>/*.yaml` a claves con puntos, prefijadas con el stem del
archivo) + `ui/componentes/idiomas.py` (estado: `idioma_actual()` = session_state →
`?lang=` → ES; `t(clave, **kwargs)`; `selector_idioma()` 🌐 del sidebar). Fallback en
cascada: idioma → ES → default → clave literal visible; `t()` **nunca lanza** (format roto →
plantilla sin interpolar).

Namespaces: el archivo YAML es la raíz (`p1.yaml` → `p1.*`); `comun.*` (repetidos),
`sidebar.*` (Secasol.py), `p1..p7.*` (subnivel = bloque visual, widget = `.label`/`.help`),
`graficas.*`, `reporte.*`, `advertencias.<CODIGO>.mensaje/.sugerencia`, `catalogo.*`,
`manual.*`.

**Reglas duras:**
- **Todo string visible nuevo pasa por `t()` y se agrega a los TRES YAML en el mismo
  cambio** (los tests exigen paridad de claves y de placeholders entre idiomas).
- **Nunca `t()` a nivel de módulo** (el idioma cambia entre reruns): los dicts de etiquetas
  module-level se convierten en claves resueltas dentro de `render()`.
- Widgets de opciones: **options = valores estables** (enums, códigos `p1..p7`) +
  `format_func` con `t()` — jamás el rótulo traducido como valor (gotcha `nav_seccion`).
- Placeholders **siempre nombrados** (`{lapso_dias}`); la lógica se resuelve en Python antes
  de `t()`; plurales con par de claves `.singular`/`.plural`.
- Las plantillas de advertencias solo pueden interpolar claves presentes en `adv.contexto`.
  Las advertencias de diseño (`Advertencia` de `core/`) se renderizan con el **widget único**
  `ui/componentes/advertencias_widget.py::render_advertencias` (F5): traduce por
  `advertencias.<CODIGO>.mensaje/.sugerencia` con `default=adv.mensaje/.sugerencia` (un código
  sin plantilla YAML muestra igual el ES de core, nunca la clave cruda). Los `_mostrar_advertencias`
  de P3–P6 delegan en él; P3 pasa `con_sugerencia=True`. Las `res.advertencias` de P7 son
  `list[str]` de runtime de `calculos/` (no `Advertencia`), quedan en ES (`# i18n: exento`).
- v1 mantiene el **punto decimal** y los formatos numéricos actuales en los 3 idiomas.
- **Catálogos (F7):** los YAML de `catalogo/materiales|productos/` llevan `descripcion_en`/
  `descripcion_pt` junto a `descripcion` (39 items). La UI resuelve la descripción en el idioma
  activo con `ui.componentes.idiomas.t_catalogo(datos, default=id)` (envuelve `campo_i18n` +
  `idioma_actual`); en el PDF (F6) se usa `campo_i18n(props, "descripcion", tr.idioma)`. `notas`/
  `fuente` quedan en ES (v1). **No traducir los generadores de snapshot `.txt`/`.json`** (los
  `_texto_config_*`/`_json_*`/`_texto_resultados_completo` — artefactos de exportación, ES). El
  snapshot `props_catalogo` serializa el dict completo, así que arrastra las traducciones.
- **Reporte PDF (F6):** `generar_reporte_pdf(..., idioma=idioma_actual())`; el idioma se
  enhebra como closure `tr("colector.titulo", ...)` → `traducir("reporte.colector.titulo", …)`
  a todas las `_seccion_*`/`_figuras_*`/`_crear_doc`. `tr.idioma` queda expuesto para que
  `_bloque_advertencias` retraduzca los mensajes por código (namespace `advertencias.*`, F5).
  Valores numéricos/unidades/códigos de enum quedan en v1. `reporte.py` usa reportlab (no
  `st.*`) → el audit no lo escanea.
- **Gotcha YAML (bool/None):** una **clave o valor** `no`/`No`/`NO`/`yes`/`Yes`/`on`/`off`/
  `null` sin comillas se parsea como booleano/None (`no:`→clave `False`; valor `Yes`→`True`;
  `NO`→`False`). La paridad NO lo detecta (los 3 idiomas comparten el error). Quotear siempre
  (`"no": "NO"`). Lo cubre `test_yaml_sin_coercion_de_tipos` sobre el YAML crudo.
- Literales legítimamente no traducibles (marca, mails): comentario `# i18n: exento` en la
  línea (el test heurístico de `tests/test_ui/test_idiomas.py` lo respeta). Auditoría del
  residuo por archivo: `.venv/bin/python scripts/auditar_i18n.py`.

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

**La única conversión de unidades físicas (°C↔K, kPa↔Pa, %↔fracción) ocurre en `ui/componentes/unidades.py`.** La conversión de ángulos entre convenciones es matemática pura y vive en `calculos/conversiones_angulo.py` (la consumen tanto la UI como `calculos/`); `unidades.py` la re-exporta por compatibilidad. Ver "Convención de ángulos".

### Convención de ángulos (crítico)

Hay tres convenciones y **no deben mezclarse**:
- **Duffie & Beckman** (almacenamiento en `Emplazamiento`, lógica de cálculo): acimut γ: 0° = Sur, +90° = Oeste, −90° = Este. Rango [−180, +180].
- **UI360** (entrada del usuario en P2 desde S20): 0° = Norte, sentido horario. Rango [0, 360).
- **pvlib** (cálculo interno de irradiancia): surface_azimuth ψ: 0° = Norte, 90° = Este, 180° = Sur. Rango [0, 360).

Conversiones (matemática pura en **`calculos/conversiones_angulo.py`**, re-exportadas desde `ui/componentes/unidades.py` para los consumidores históricos de la UI; nunca duplicar la fórmula en otro módulo):
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

Suite con pytest. Estructura: `tests/test_core/` para validaciones de dataclasses, `tests/test_calculos/` para motores numéricos, `tests/test_ui/` para helpers de UI testeables sin servidor. Validación física del modelo de colector en `validacion/` (HWB, Klein) — scripts standalone que confirman linealidad vs el modelo de Hottel-Whillier-Bliss. Con propiedades del aire variables (desde S36) el R² es ≈0.999 (era 1.0000 con propiedades constantes); el criterio es R²≥0.99 + monotonía de η + parámetros `F_R·(τα)`/`F_R·U_L` en rango.

Un test por validación dura. Nombre del test = nombre del código de error en minúsculas cuando aplica (ej. `test_MOT_CAUDAL_NO_POSITIVO`).

### Documentación viva

- `docs/bitacora/bitacora_sesion{N}.md` — registro cronológico por sesión. La última bitácora siempre tiene el estado más actualizado (conteo de tests, trabajo no commiteado, pendientes).
- `docs/mapa_conexiones.md` — tabla widget → campo → consumidor, mantenida manualmente. Útil para detectar widgets huérfanos y campos sin UI.
- `docs/notas/` — especificaciones técnicas puntuales (ej. `especificacion_motor_dinamico_camara.md`).
- `CHANGELOG.md` — versiones liberadas con Added/Changed/Fixed.
- `Balance_de_calor_y_masa_en_camara_ampliado.md` (raíz) — derivación física de las ecuaciones del motor termodinámico de cámara.

Antes de cambios estructurales grandes, consultar la bitácora más reciente para entender el contexto histórico de las decisiones.

## Ver también (Obsidian)

Notas enlazadas para navegación en el *graph view* de Obsidian:

- [[README]] — descripción de producto.
- [[docs/arquitectura]] — capas, subsistemas y mapa de módulos.
- [[docs/tareas]] — backlog y estado.
- [[docs/decisiones]] — registro de decisiones de diseño (ADR).
