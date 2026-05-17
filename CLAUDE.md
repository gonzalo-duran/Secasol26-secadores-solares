# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Iniciar la aplicación Streamlit
.venv/bin/python -m streamlit run app.py

# Ejecutar todos los tests
.venv/bin/python -m pytest

# Ejecutar un archivo de tests específico
.venv/bin/python -m pytest tests/test_core/test_colector.py

# Ejecutar un test individual
.venv/bin/python -m pytest tests/test_calculos/test_colector_calc.py::TestHVientoMcAdams::test_formula_exacta_3ms

# Tests con output detallado
.venv/bin/python -m pytest -v
```

El entorno virtual está en `.venv/`. Siempre prefijá los comandos de Python con `.venv/bin/python`.

## Arquitectura

La aplicación es un **prediseñador de secadores solares** (Streamlit). El usuario configura el sistema pestaña a pestaña; cada pestaña escribe en un objeto `Proyecto` central guardado en `st.session_state.proyecto`.

### Capas (separación estricta)

```
Secasol.py                ← entry point Streamlit, construye las pestañas
ui/p{1-7}_*.py            ← UI por pestaña, llaman a core/ y calculos/
ui/componentes/           ← widgets reutilizables
core/                     ← dataclasses del modelo de datos (sin Streamlit)
calculos/                 ← motores numéricos puros (sin Streamlit)
catalogo/materiales/*.yaml ← catálogos de materiales (cubiertas, placas, aislantes, fondos)
catalogo/productos/*.yaml  ← productos a secar
tests/                    ← pytest (235 tests)
data/cache/nasa_power/    ← caché parquet de NASA POWER (gitignoreado)
```

**Regla clave:** `core/` y `calculos/` no importan `streamlit`. La UI es la única que lo usa.

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
└── resultados: Resultados
```

### Colector solar (`core/colector.py`)

El sistema de colectores tiene jerarquía propia:
```
Colector
├── unidad: ColectorUnidad   ← geometría + materiales de un módulo
├── banco: BancoColectores   ← configuración serie/paralelo
└── chimenea: Optional[Chimenea]
```

Los materiales se validan contra `catalogo/materiales/` en `__post_init__`. El catálogo se carga en `core/catalogo.py` al importar el módulo (no en `__init__`).

### Sistema de advertencias

`core/advertencias.py` define:
- `Advertencia` (frozen dataclass): código con prefijo de sección (ej. `GEO_LARGO_PEQUENO`), severidad INFO/WARNING/CRITICAL, mensaje, campo, sugerencia, contexto.
- `BloqueResultados`: clase base para resultados con hash SHA-256 para detectar desactualización (stale).

Las advertencias estáticas de diseño se generan en funciones separadas (`advertencias_colector()` en `core/colector.py`), no bloquean la instanciación pero deben mostrarse antes de calcular.

### Motores numéricos (`calculos/`)

Cuatro tipos de colector de placa plana:
- **Tipo 1** (`colector_calc.py`): canal único, absorbedor en fondo, flujo por encima.
- **Tipos 2, 3, 4** (`colector_tipos234_calc.py`): absorbedor a media altura, variantes de canal activo/estanco.

Todos usan modelo cuasi-estacionario: `scipy.integrate.solve_ivp` (EDO del fluido en x) + `scipy.optimize.fsolve` (sistema no lineal de superficies en cada nodo, con warm-start).

`calculos/correlaciones_nusselt.py` es el catálogo de correlaciones de convección (Shah-London, Gnielinski, Sparrow-Liu, Dittus-Boelter, Hollands). La función `calcular_h_int()` selecciona automáticamente según Re y L/Dh, o usa la indicada por el usuario.

`calculos/clima_calc.py` descarga datos horarios anuales de **NASA POWER** vía `pvlib.iotools.get_nasa_power`, cachéa en parquet (SHA-256 por lat/lon/año), e interpola huecos ≤ 3 h.

### Convención de unidades (crítico)

**Todo lo que circula por `core/` y `calculos/` está en SI estricto:**
- Temperatura en K (no °C)
- Presión en Pa (no kPa)
- Humedad relativa como fracción 0–1 (no %)
- Ángulos en grados (°) pero con convención Duffie

**La única conversión de unidades ocurre en `ui/componentes/unidades.py`**, incluyendo la conversión de ángulos entre convenciones.

### Convención de ángulos (crítico)

Hay dos convenciones y **no deben mezclarse**:
- **Duffie & Beckman** (almacenamiento en `Emplazamiento`, UI): acimut γ: 0° = Sur, +90° = Oeste, −90° = Este. Rango [−180, +180].
- **pvlib** (cálculo interno de irradiancia): surface_azimuth ψ: 0° = Norte, 90° = Este, 180° = Sur. Rango [0, 360).
- Conversión: ψ = (180 + γ) mod 360. Implementada en `ui/componentes/unidades.py`, **nunca en `core/` ni `calculos/`**.
