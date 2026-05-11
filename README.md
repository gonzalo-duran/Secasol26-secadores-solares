# Secasol 26 — Herramienta de Prediseño de Secadores Solares

Software de prediseño de secadores solares de alimentos, desarrollado por el Grupo de Eficiencia Energética y Desarrollo Socio-Productivo (GEEDSP) — INENCO UNSa CONICET.

**Licencia:** MIT &nbsp;|&nbsp; **Idioma:** Español &nbsp;|&nbsp; **Stack:** Python 3.11+ · Streamlit · NumPy · SciPy · pvlib

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

## Instalación (entorno de desarrollo local)

### Requisitos previos

- Python 3.11 o superior
- Git

> **Windows:** instalar [Git for Windows](https://git-scm.com/) (incluye Git Bash) y
> [Python 3.12](https://www.python.org/) marcando **"Add Python to PATH"** durante la instalación.
> Todos los comandos de esta sección se ejecutan desde **Git Bash**, no desde cmd ni PowerShell.

Verificar versiones:

```bash
python3 --version
git --version
```

---

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/secador_solar.git
cd secador_solar
```

---

### 2. Crear y activar el entorno virtual

**Linux / Fedora:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (Git Bash):**
```bash
python -m venv .venv
source .venv/Scripts/activate
```

El prompt cambia a `(.venv)` cuando el entorno está activo. Para desactivarlo: `deactivate`.

---

### 3. Instalar dependencias

Para desarrollo (incluye testing y linters):
```bash
pip install -r requirements-dev.txt
```

Para uso solamente (sin herramientas de desarrollo):
```bash
pip install -r requirements.txt
```

---

### 4. Ejecutar la aplicación

```bash
streamlit run app.py
```

La aplicación se abre automáticamente en el navegador en `http://localhost:8501`.

---

### Setup automatizado (script)

El repositorio incluye `setup_secador_solar.sh`, que automatiza los pasos 2–4 más la
instalación de plugins de VS Code. Soporta Fedora, Windows 10/11 (Git Bash) y otras
distribuciones Linux.

**Linux / Fedora:**
```bash
chmod +x setup_secador_solar.sh
./setup_secador_solar.sh
```

**Windows (Git Bash):**
```bash
bash setup_secador_solar.sh
```

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
├── app.py                        # Entry point de Streamlit
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── setup_secador_solar.sh        # Script de setup multiplataforma
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
3. Conectar el repositorio y seleccionar `app.py` como entry point.
4. Streamlit Cloud instala automáticamente las dependencias de `requirements.txt`.

---

## Créditos

Desarrollado por Gonzalo Durán. GEEDSP INENCO — Instituto de Investigación en Energías No Convencionales,
Universidad Nacional de Salta – CONICET.
