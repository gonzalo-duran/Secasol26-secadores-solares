# Secasol 26 — Herramienta de Prediseño de Secadores Solares

Software de prediseño de secadores solares de alimentos, desarrollado por el Grupo de Eficiencia Energética y Desarrollo Socio-Productivo (GEEDSP) — INENCO UNSa CONICET.

**Licencia:** GPLv3 &nbsp;|&nbsp; **Idioma:** Español &nbsp;|&nbsp; **Stack:** Python 3.11+ · Streamlit · NumPy · SciPy · pvlib

---

## Descripción

Herramienta de prediseño de secadores solares orientada a usuarios con formación
en transferencia de calor. Permite tomar decisiones de ingeniería de prediseño:
dimensiones, áreas, caudales, potencias auxiliares y estimación de tiempo de secado.

**Tipologías soportadas:**
- Caja (hasta ~10 kg, convección natural)
- Armario (0–100 kg, colector externo, circulación natural o forzada)
- Gran escala (100 kg – toneladas, forzada, banco de colectores)

**Datos climáticos:** NASA POWER API (vía pvlib), con caché local en formato Parquet.

---

## Instalación local

Secasol también corre en la nube, sin instalar nada:
<https://huggingface.co/spaces/gonzalojduran/Secasol26>. Para tenerlo en la propia
computadora alcanza con dos scripts, uno para instalar y otro para abrir la aplicación.
Instalan **las mismas versiones de librerías que la versión en producción**
(`requirements.txt`, fijadas con `==`), dentro de un entorno virtual `.venv` en la carpeta del
proyecto: no tocan el Python del sistema ni dejan nada fuera de esa carpeta.

### Requisitos

- **Python 3.11 o superior.** Se recomienda **3.13**, la versión que usa producción; con otra
  la aplicación funciona igual, pero algún resultado puede diferir en los últimos decimales.
- Conexión a internet: la primera instalación descarga unos 300 MB, y la aplicación consulta
  NASA POWER para el clima.

### 1. Descargar el proyecto

Con Git:

```bash
git clone https://github.com/gonzalo-duran/Secasol26-secadores-solares.git
cd Secasol26-secadores-solares
```

O sin Git: botón **Code → Download ZIP** en GitHub, y descomprimir.

### 2. Instalar y abrir

**Windows 10 / 11**

1. Instalar Python 3.13 desde <https://www.python.org/downloads/> marcando
   **"Add python.exe to PATH"**.
2. Doble clic en **`instalar_secasol.bat`** (una sola vez).
3. Doble clic en **`iniciar_secasol.bat`** cada vez que se quiera usar Secasol. Se abre en el
   navegador; para cerrarlo, cerrar la ventana negra.

**Linux / macOS**

```bash
bash instalar_secasol.sh      # una sola vez
bash iniciar_secasol.sh       # cada vez que se quiera usar Secasol (Ctrl+C para cerrar)
```

En Ubuntu/Debian puede hacer falta antes `sudo apt install python3-venv`.

**Opciones del instalador** (iguales en `.sh` y `.bat`):

| opción | qué hace |
|---|---|
| `--iniciar` | instala y abre la aplicación al terminar |
| `--limpio` | borra el `.venv` y lo crea de nuevo (útil si algo quedó a medias) |
| `--dev` | agrega las herramientas de desarrollo: `pytest`, `black`, `ruff` |

Para actualizar después de un `git pull`, volver a correr el instalador: reutiliza el `.venv` y
solo ajusta las versiones que cambiaron.

---

## Entorno de desarrollo

Para modificar el código:

```bash
bash setup_secador_solar.sh
```

Instala con `--dev` y además configura VS Code (plugins recomendados, intérprete del `.venv`,
configuraciones de depuración para Streamlit y pytest). En Windows se corre desde Git Bash.
Sin VS Code alcanza con `instalar_secasol.sh --dev` / `instalar_secasol.bat --dev`.

---

## Flujo de trabajo de desarrollo

### Antes de commitear

```bash
# Formatear código
black .

# Verificar linting
ruff check .

# Correr tests
pytest
```

---

### Estructura del proyecto

```
secador_solar/
├── Secasol.py                    # Entry point de Streamlit
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── instalar_secasol.sh / .bat    # Instalación local (Linux-macOS / Windows)
├── iniciar_secasol.sh / .bat     # Abre la aplicación en el navegador
├── setup_secador_solar.sh        # Entorno de desarrollo (instala --dev + VS Code)
├── core/                         # Modelo de datos (dataclasses, validaciones)
├── calculos/                     # Motores numéricos (independientes de UI)
│   ├── clima_calc.py
│   ├── correlaciones_nusselt.py
│   ├── colector_calc.py
│   ├── colector_tipos234_calc.py
│   ├── camara_calc.py
│   ├── auxiliar_calc.py
│   ├── motor_calc.py
│   ├── balance_global.py
│   └── psicrometria.py
├── catalogo/                     # Datos estáticos en YAML
│   ├── materiales/
│   └── productos/
├── ui/                           # Componentes Streamlit
│   ├── componentes/
│   │   └── unidades.py           # Conversiones de unidades y ángulos
│   ├── p1_tipologia.py
│   ├── p2_emplazamiento.py
│   ├── p3_colector.py
│   ├── p4_camara.py
│   ├── p5_auxiliar.py
│   ├── p6_motor.py
│   └── p7_resultados.py
├── data/cache/nasa_power/        # Caché local de datos climáticos (en .gitignore)
├── validation_data/              # Datos experimentales para validación
├── tests/                        # Tests automáticos
└── docs/                         # Documentación y bitácoras
```

---

### Convenciones clave

- **Unidades:** SI estricto en todo el cálculo interno. Conversiones °C↔K y %↔fracción
  solo en `ui/componentes/unidades.py`.
- **Ángulos:** convención Duffie & Beckman hacia el usuario (acimut 0° = Sur).
  Conversión a convención de navegación (pvlib) en la capa de UI.
- **Docstrings:** Google style, en español, en todas las funciones de `core/` y `calculos/`.
- **Type hints:** obligatorios en firmas de `core/` y `calculos/`.
- **session_state:** un único objeto raíz `st.session_state.proyecto` de tipo `Proyecto`.

---

## Deploy en Streamlit Community Cloud

1. Hacer push del repo a GitHub (repositorio público).
2. Ingresar a [share.streamlit.io](https://share.streamlit.io).
3. Conectar el repositorio y seleccionar `Secasol.py` como entry point.
4. Streamlit Cloud instala automáticamente las dependencias de `requirements.txt`.

---

## Créditos

Desarrollado por Gonzalo Durán. GEEDSP INENCO — Instituto de Investigación en Energías No Convencionales,
Universidad Nacional de Salta – CONICET.

## Licencia

Secasol 26 — Herramienta de prediseño de secadores solares.
Copyright (C) 2025-2026 INENCO — Instituto de Investigación en Energías No Convencionales
(Universidad Nacional de Salta – CONICET).

Este programa es software libre: usted puede redistribuirlo y/o modificarlo bajo los
términos de la **Licencia Pública General de GNU (GNU GPL)** publicada por la Free
Software Foundation, en su **versión 3**.

Este programa se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA
GARANTÍA**; ni siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD PARA UN
PROPÓSITO PARTICULAR. Véase la Licencia Pública General de GNU para más detalles.

El texto completo de la licencia está en el archivo [LICENSE](LICENSE).

## Ver también (Obsidian)

- [[CLAUDE]] — instrucciones para Claude Code y convenciones.
- [[docs/arquitectura]] — arquitectura del sistema y mapa de módulos.
- [[CHANGELOG]] — historial de cambios.
