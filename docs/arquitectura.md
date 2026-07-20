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

## Subsistemas principales

- **Colector solar** (`core/colector.py` + `calculos/colector_calc.py`,
  `calculos/colector_tipos234_calc.py`): cuatro tipos de placa plana, modelo
  cuasi-estacionario con `solve_ivp` + `fsolve`. Soporta doble cubierta.
- **Cámara de secado** (`core/camara.py` + `calculos/camara_calc.py`,
  `calculos/camara_termodinamica.py`): dos motores físicos (`capa_fina`,
  `termodinamico`) con dispatcher único.
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
- [[docs/modulos/calculos_camara_calc]] — Motor numérico de la cámara de secado solar — modelos de capa fina.
- [[docs/modulos/calculos_camara_termodinamica]] — Solver algebraico de cámara — motor termodinámico transitorio.
- [[docs/modulos/calculos_chimenea_calc]] — Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.
- [[docs/modulos/calculos_clima_calc]] — Obtención y caché de datos climáticos NASA POWER.
- [[docs/modulos/calculos_colector_calc]] — Motor numérico del colector solar de aire — Tipo 1.
- [[docs/modulos/calculos_colector_tipos234_calc]] — Motor numérico de colectores solares de aire — Tipos 2, 3 y 4.
- [[docs/modulos/calculos_correlaciones_nusselt]] — Catálogo de correlaciones de Nusselt para colectores solares de aire.
- [[docs/modulos/calculos_eficiencias_camara]] — Eficiencias de cámara de secado — método Augustus Leon (RSER 2002).
- [[docs/modulos/calculos_motor_calc]] — Estimación de pérdidas de carga para el dimensionamiento del motor.
- [[docs/modulos/calculos_operacion_anual_camara]] — Operación anual de la cámara de secado (cascada A + B).
- [[docs/modulos/calculos_psicrometria]] — Ecuaciones psicrométricas del aire húmedo para el sistema de secado solar.
- [[docs/modulos/calculos_solar_geometria]] — Geometría solar — utilidades de tiempo y posición.

### `core/`

- [[docs/modulos/core_advertencias]] — Clases base del sistema de advertencias y mecanismo de invalidación de resultados.
- [[docs/modulos/core_auxiliar]] — Dataclasses del sistema de calentamiento auxiliar.
- [[docs/modulos/core_camara]] — Dataclasses de la cámara de secado solar.
- [[docs/modulos/core_catalogo]] — Cargador del catálogo de materiales del colector solar.
- [[docs/modulos/core_chimenea]] — Chimenea solar — componente independiente del lazo aerodinámico.
- [[docs/modulos/core_clima]] — Dataclasses para los datos climáticos del emplazamiento.
- [[docs/modulos/core_colector]] — Dataclasses del sistema de colectores solares de aire tipo placa plana.
- [[docs/modulos/core_emplazamiento]] — Dataclass de emplazamiento geográfico del secador solar.
- [[docs/modulos/core_motor]] — Dataclass del motor / ventilador del sistema de convección forzada.
- [[docs/modulos/core_proyecto]] — Dataclasses raíz del proyecto: Meta, Configuracion y Proyecto.
- [[docs/modulos/core_resultados]] — Dataclasses de resultados del proyecto de prediseño.

### `ui/`

- [[docs/modulos/ui_componentes_advertencias_widget]] — Componente reutilizable de UI.
- [[docs/modulos/ui_componentes_esquemas]] — Helper para renderizar esquemas SVG en Streamlit.
- [[docs/modulos/ui_componentes_graficas]] — Gráficas reutilizables de la UI compartidas entre pestañas.
- [[docs/modulos/ui_componentes_header]] — Header institucional de Secasol26.
- [[docs/modulos/ui_componentes_serializacion]] — Helpers de serialización para los botones de "Guardar configuración".
- [[docs/modulos/ui_componentes_unidades]] — Conversiones entre unidades de la interfaz de usuario y el SI interno.
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
- [[docs/modulos/validacion_validacion_cruzada_yacon]] — validacion_cruzada_yacon.py
- [[docs/modulos/validacion_validacion_hwb]] — Validación del modelo Tipo 1 contra la curva HWB (Hottel-Whillier-Bliss).
- [[docs/modulos/validacion_validacion_klein]] — Validación del modelo de Tipo 1 contra la fórmula empírica de Klein (1979).

<!-- FIN MODULOS AUTOGENERADO -->
