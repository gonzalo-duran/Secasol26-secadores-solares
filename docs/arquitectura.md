# Arquitectura del sistema

Visión general de la arquitectura de **Secasol 26**, el prediseñador de
secadores solares. Para el detalle operativo y las convenciones de trabajo, ver
[[CLAUDE]]. Para la descripción de producto, ver [[README]]. Las decisiones de
diseño se registran en [[docs/decisiones]].

## Capas (separación estricta)

```
Secasol.py                ← entry point Streamlit, construye las pestañas
ui/p{1-7}_*.py            ← UI por pestaña, llaman a core/ y calculos/
ui/componentes/           ← widgets reutilizables (header, gráficas, unidades, serialización)
core/                     ← dataclasses del modelo de datos (sin Streamlit)
calculos/                 ← motores numéricos puros (sin Streamlit)
catalogo/materiales/*.yaml ← catálogos de materiales
catalogo/productos/*.yaml  ← productos a secar
validacion/               ← scripts de validación física (HWB, Klein)
tests/                    ← suite pytest
```

**Regla clave:** `core/` y `calculos/` **no importan `streamlit`**. La UI es la
única capa que lo usa. `validacion/` puede importar de `core/` y `calculos/`
pero no de `ui/`.

## Objeto raíz

`core/proyecto.py` define `Proyecto`, el único objeto en `st.session_state`.
Agrupa las secciones del modelo: `meta`, `configuracion`, `emplazamiento`,
`clima`, `colector`, `camara`, `auxiliar`, `motor`, `chimenea`, `resultados`.

**Todo lo que cuelgue de `Proyecto` vive en `core/`.** No es una preferencia de
estilo: una dataclass definida en `calculos/` obligaría a `core/proyecto.py` a
importar del motor numérico, invirtiendo la dependencia. Fue exactamente lo que
bloqueó dos sesiones la persistencia de `PoliticaRecarga` (S59), que estaba en
`calculos/simulacion_ventana.py` — ver [[docs/bitacora/bitacora_sesion59]].

## Subsistemas principales

- **Colector solar** (`core/colector.py` + `calculos/colector_calc.py`,
  `calculos/colector_tipos234_calc.py`): cuatro tipos de placa plana, modelo
  cuasi-estacionario con `solve_ivp` + `fsolve`. Soporta doble cubierta.
- **Cámara de secado** (`core/camara.py` + `calculos/camara_calc.py`,
  `calculos/camara_termodinamica.py`): **motor único** desde S38, el balance
  acoplado calor-masa (`simular_secado`). El antiguo motor de capa fina se
  eliminó; `Camara.modo_calculo` quedó vestigial y coacciona a
  `"termodinamico"`. Batch y túnel semicontinuo comparten el mismo núcleo vía
  `simular_cascada` (N=1 zona vs N zonas a contracorriente).
- **Operación** (`core/operacion.py`, S59): cómo el operador maneja el secador
  —hora de carga, maniobra, si mira el pronóstico antes de llenar— separado de
  la descripción física del equipo. `Configuracion.politica_recarga`; la leen el
  modo ANUAL y el modo VENTANA de gran escala BATCH.
- **Balance global** (`calculos/balance_global.py`): orquesta todo el cálculo,
  incluido el lazo de convección natural por chimenea (Picard).
- **Clima** (`calculos/clima_calc.py`): descarga NASA POWER, caché parquet,
  transposición POA con pvlib.
- **Clima medido** (`core/clima_medido.py` + `calculos/clima_medido.py`, mejora 38
  fase 1a): ingesta de archivos del usuario (CSV/XLS) → contrato `Clima.datos`; paso
  de trabajo sub-horario en fase 1b (`clima_calc.resolver_datos_trabajo`).
- **Validación y calibración** (`calculos/metricas_validacion.py`,
  `core/validacion.py`, `calculos/ingesta_referencia.py`, `calculos/calibracion.py`,
  mejora 38 fases 2/2b/3): contrasta el modelo contra datos de campo (métricas
  RMSE/MBE/R², forzado con clima propio del ensayo) y calibra 1-D un parámetro
  minimizando el ajuste. UI en P3 ("🔬 Validación con datos medidos").

## Convenciones críticas

- **Unidades:** SI estricto en `core/` y `calculos/`. La única conversión vive
  en `ui/componentes/unidades.py`.
- **Ángulos:** tres convenciones (Duffie, UI360, pvlib); conversiones solo en
  `unidades.py`.

## Ver también

- [[README]]
- [[CLAUDE]]
- [[docs/decisiones]]
- [[docs/tareas]]

<!-- INICIO MODULOS AUTOGENERADO -->

## Mapa de módulos

_Esta sección se autogenera con `scripts/generar_notas_obsidian.py`. No editar a mano: los cambios se sobrescriben en cada corrida._

### `(raíz)/`

- [[docs/modulos/Secasol]] — Secador Solar — Software de Prediseño de Secadores Solares

### `calculos/`

- [[docs/modulos/calculos_auxiliar_calc]] — Motor numérico del sistema de calentamiento auxiliar.
- [[docs/modulos/calculos_balance_global]] — Orquestador del cálculo global del secador solar.
- [[docs/modulos/calculos_barrido_parametrico]] — Motor de corridas paramétricas (barridos) para P7.
- [[docs/modulos/calculos_calibracion]] — Calibración 1-D contra datos medidos (mejora 38, fase 3).
- [[docs/modulos/calculos_camara_calc]] — Motor numérico de la cámara de secado solar — wire-up del motor termodinámico.
- [[docs/modulos/calculos_camara_termodinamica]] — Solver algebraico de cámara — motor termodinámico transitorio.
- [[docs/modulos/calculos_campo_colectores_calc]] — Red hidráulica y térmica del campo de colectores — gran escala (S41).
- [[docs/modulos/calculos_cano_maestro_calc]] — Física del caño maestro (manifold) del banco de colectores — gran escala (S40).
- [[docs/modulos/calculos_carta_psicrometrica]] — Carta psicrométrica del proceso completo del secador (mejora 27).
- [[docs/modulos/calculos_catalogo_albedos]] — Catálogo de albedos de superficies usuales para la transposición POA.
- [[docs/modulos/calculos_catalogo_kpis_barrido]] — Catálogo de KPIs extraíbles de un resultado de simulación para los barridos.
- [[docs/modulos/calculos_catalogo_parametros_barrido]] — Catálogo de parámetros barrideables para las corridas paramétricas de P7.
- [[docs/modulos/calculos_catalogo_rugosidades]] — Catálogo de rugosidades aerodinámicas del terreno para el perfil de viento.
- [[docs/modulos/calculos_chimenea_calc]] — Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.
- [[docs/modulos/calculos_clima_calc]] — Obtención y caché de datos climáticos NASA POWER.
- [[docs/modulos/calculos_clima_medido]] — Pipeline de ingesta de datos climáticos medidos por el usuario (mejora 38, F1a).
- [[docs/modulos/calculos_colector_calc]] — Motor numérico del colector solar de aire — Tipo 1.
- [[docs/modulos/calculos_colector_tipos234_calc]] — Motor numérico de colectores solares de aire — Tipos 2, 3 y 4.
- [[docs/modulos/calculos_conversiones_angulo]] — Conversiones puras entre las tres convenciones de acimut del proyecto.
- [[docs/modulos/calculos_correlaciones_nusselt]] — Catálogo de correlaciones de Nusselt para colectores solares de aire y cámara.
- [[docs/modulos/calculos_eficiencias_camara]] — Eficiencias de cámara de secado — método Augustus Leon (RSER 2002).
- [[docs/modulos/calculos_ingesta_referencia]] — Ingesta de la señal de referencia medida (mejora 38, fase 2).
- [[docs/modulos/calculos_metricas_validacion]] — Métricas de bondad de ajuste — validación medido vs simulado (mejora 38, fase 2).
- [[docs/modulos/calculos_motor_calc]] — Estimación de pérdidas de carga para el dimensionamiento del motor.
- [[docs/modulos/calculos_perfil_viento]] — Perfil logarítmico de viento en la capa límite atmosférica.
- [[docs/modulos/calculos_propiedades_aire]] — Propiedades termofísicas del aire seco en función de la temperatura.
- [[docs/modulos/calculos_psicrometria]] — Ecuaciones psicrométricas del aire húmedo para el sistema de secado solar.
- [[docs/modulos/calculos_radiacion_camara]] — Irradiancia equivalente sobre las superficies translúcidas de la cámara.
- [[docs/modulos/calculos_simulacion_anual]] — Modo anual sobre las 8760 h reales del clima.
- [[docs/modulos/calculos_simulacion_ventana]] — Orquestador de ventana — simulación de producción sobre un lapso [inicio, fin].
- [[docs/modulos/calculos_solar_geometria]] — Geometría solar — utilidades de tiempo y posición.
- [[docs/modulos/calculos_superficie_colector]] — Superficie de respuesta del colector — sustituto interpolado del solver.
- [[docs/modulos/calculos_validacion_camara]] — Orquestación de la validación de cámara y producto (mejora 38, fase 4).

### `core/`

- [[docs/modulos/core_advertencias]] — Clases base del sistema de advertencias y mecanismo de invalidación de resultados.
- [[docs/modulos/core_auxiliar]] — Dataclasses del sistema de calentamiento auxiliar.
- [[docs/modulos/core_camara]] — Dataclasses de la cámara de secado solar.
- [[docs/modulos/core_catalogo]] — Cargador del catálogo de materiales del colector solar.
- [[docs/modulos/core_chimenea]] — Chimenea solar — componente independiente del lazo aerodinámico.
- [[docs/modulos/core_clima]] — Dataclasses para los datos climáticos del emplazamiento.
- [[docs/modulos/core_clima_medido]] — Dataclasses de configuración y reporte para la ingesta de datos climáticos medidos.
- [[docs/modulos/core_colector]] — Dataclasses del sistema de colectores solares de aire tipo placa plana.
- [[docs/modulos/core_emplazamiento]] — Dataclass de emplazamiento geográfico del secador solar.
- [[docs/modulos/core_huellas]] — Huellas de las entradas de un cálculo, para detectar resultados viejos.
- [[docs/modulos/core_motor]] — Dataclass del motor / ventilador del sistema de convección forzada.
- [[docs/modulos/core_operacion]] — Configuración de operación del secador — cómo lo maneja el operador.
- [[docs/modulos/core_presets]] — Presets de sistema completo para tipologías (S41).
- [[docs/modulos/core_proyecto]] — Dataclasses raíz del proyecto: Meta, Configuracion y Proyecto.
- [[docs/modulos/core_resultados]] — Dataclasses de resultados del proyecto de prediseño.
- [[docs/modulos/core_validacion]] — Dataclasses de validación medido vs simulado (mejora 38, fase 2).
- [[docs/modulos/core_version]] — Versión de Secasol.

### `ui/`

- [[docs/modulos/ui_componentes_advertencias_widget]] — Widget único de render de advertencias con i18n por código (plan i18n, F5).
- [[docs/modulos/ui_componentes_carga_proyecto]] — Carga de un proyecto completo desde el JSON que exporta P7.
- [[docs/modulos/ui_componentes_carta_psicrometrica]] — Carta psicrométrica del proceso completo del secador — figura Plotly (mejora 27).
- [[docs/modulos/ui_componentes_espesores]] — Selector de espesores con medidas de mercado (mejoras 25 y 26).
- [[docs/modulos/ui_componentes_esquemas]] — Helper para renderizar esquemas SVG en Streamlit.
- [[docs/modulos/ui_componentes_graficas]] — Gráficas reutilizables de la UI compartidas entre pestañas.
- [[docs/modulos/ui_componentes_header]] — Header institucional de Secasol26.
- [[docs/modulos/ui_componentes_idiomas]] — Idioma activo de la sesión + selector 🌐 (capa con estado, importa streamlit).
- [[docs/modulos/ui_componentes_manual_contenido]] — Tabla de contenidos (TOC) declarativa del manual de usuario.
- [[docs/modulos/ui_componentes_manual_link]] — Botones y enlaces hacia el manual de usuario.
- [[docs/modulos/ui_componentes_manual_render]] — Parser y render de los capítulos markdown del manual.
- [[docs/modulos/ui_componentes_serializacion]] — Helpers de serialización para los botones de "Guardar configuración".
- [[docs/modulos/ui_componentes_traducciones]] — Infraestructura de internacionalización (i18n) — capa pura, sin streamlit.
- [[docs/modulos/ui_componentes_unidades]] — Conversiones entre unidades de la interfaz de usuario y el SI interno.
- [[docs/modulos/ui_componentes_validacion_widget]] — Widgets compartidos de validación contra datos medidos (mejora 38).
- [[docs/modulos/ui_componentes_vigencia]] — Vigencia de los resultados que se calculan en un lado y se muestran en otro.
- [[docs/modulos/ui_manual]] — Vista del manual de usuario (mejora 36) — estilo SAM, multiidioma (F8).
- [[docs/modulos/ui_p1_tipologia]] — Pestaña 1 — Tipología y Configuración del Análisis.
- [[docs/modulos/ui_p2_emplazamiento]] — Pestaña 2 — Emplazamiento y Recursos Climáticos.
- [[docs/modulos/ui_p3_colector]] — Pestaña 3 — Definición y dimensionamiento del colector solar de aire.
- [[docs/modulos/ui_p4_camara]] — Pestaña 4 — Cámara de Secado.
- [[docs/modulos/ui_p5_auxiliar]] — Pestaña 5 — Calentamiento Auxiliar.
- [[docs/modulos/ui_p6_motor]] — Pestaña 6 — Motor / Ventilador.
- [[docs/modulos/ui_p7_resultados]] — Pestaña 7 — Resultados del Prediseño.
- [[docs/modulos/ui_reporte]] — Generador de reporte PDF del prediseño completo.

### `validacion/`

- [[docs/modulos/validacion_comparar_f4]] — Comparativa F4 con/sin término convectivo cara interna fondo ↔ fluido ci.
- [[docs/modulos/validacion_probe_motor_C_yacon]] — probe_motor_C_yacon.py
- [[docs/modulos/validacion_validacion_adital]] — Validación del modo industrial (gran escala) contra el secador ADITAL.
- [[docs/modulos/validacion_validacion_cruzada_yacon]] — validacion_cruzada_yacon.py
- [[docs/modulos/validacion_validacion_hwb]] — Validación del modelo Tipo 1 contra la curva HWB (Hottel-Whillier-Bliss).
- [[docs/modulos/validacion_validacion_klein]] — Validación del modelo de Tipo 1 contra la fórmula empírica de Klein (1979).

<!-- FIN MODULOS AUTOGENERADO -->
