#!/usr/bin/env bash
# =============================================================================
# Setup del proyecto Secasol — Software de Prediseño de Secadores Solares
# =============================================================================
# Este script automatiza el setup inicial del entorno de desarrollo.
# Plataformas soportadas:
#   - Fedora 40 o superior
#   - Windows 10 / 11  (ejecutar desde Git Bash, NO desde cmd ni PowerShell)
#
# Stack del proyecto:
#   - Streamlit (interfaz web)
#   - numpy / scipy / pandas (cálculo científico)
#   - pvlib (datos solares y POA)
#   - Plotly + Kaleido (gráficos interactivos en la UI y export a PNG para
#     el reporte PDF). Nota: matplotlib NO se usa en el proyecto desde el
#     ciclo S23-S29; el motor gráfico es exclusivamente Plotly.
#   - ReportLab (generación de PDF)
#
# Qué hace:
#   1. Detecta el sistema operativo.
#   2. En Fedora: instala Python 3.12 y herramientas básicas vía dnf.
#      En Windows: verifica que Python ≥3.11 esté instalado manualmente.
#   3. Verifica que el zip del esqueleto esté descomprimido en ~/proyectos/.
#   4. Crea el entorno virtual .venv dentro del proyecto.
#   5. Instala las dependencias de desarrollo.
#   6. Instala los plugins de VS Code recomendados.
#   7. Configura VS Code para usar el venv automáticamente.
#   8. Corre los tests para verificar que todo funciona.
#
# Uso (Fedora):
#   1. Descomprimir secador_solar_esqueleto.zip en ~/proyectos/
#   2. chmod +x setup_secador_solar.sh
#   3. ./setup_secador_solar.sh
#
# Uso (Windows 10/11):
#   1. Instalar Git for Windows (https://git-scm.com/) — incluye Git Bash.
#   2. Instalar Python 3.12 desde https://www.python.org/
#      IMPORTANTE: marcar "Add Python to PATH" durante la instalación.
#   3. Descomprimir secador_solar_esqueleto.zip en C:\Users\TuUsuario\proyectos\
#      (debe quedar la carpeta proyectos\secador_solar\)
#   4. Abrir Git Bash y ejecutar:
#         cd ~/proyectos/secador_solar
#         bash setup_secador_solar.sh
#
# Requisitos comunes:
#   - Conexión a internet
#   - VS Code instalado (comando 'code' disponible en PATH)
#     Si no está: abrir VS Code → Ctrl+Shift+P → "Shell Command: Install code in PATH"
# =============================================================================

set -e  # Abortar si algún comando falla

# --- Configuración ---
PROYECTO_DIR="$HOME/proyectos/secador_solar"
PYTHON_VERSION="3.12"
PYTHON_VERSION_MIN="3.11"  # Versión mínima aceptable (según pyproject.toml)
VENV_NAME=".venv"

# --- Colores para mensajes ---
ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
AZUL='\033[0;34m'
SIN_COLOR='\033[0m'

info()    { echo -e "${AZUL}[INFO]${SIN_COLOR} $1"; }
ok()      { echo -e "${VERDE}[OK]${SIN_COLOR} $1"; }
warn()    { echo -e "${AMARILLO}[WARN]${SIN_COLOR} $1"; }
error()   { echo -e "${ROJO}[ERROR]${SIN_COLOR} $1" >&2; }

separador() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}

# =============================================================================
# Detección del sistema operativo
# =============================================================================
# Posibles valores de OSTYPE: linux-gnu, linux (Fedora), msys (Git Bash en Win),
# cygwin, darwin. Usamos 'uname -s' como respaldo.
detectar_os() {
    case "$(uname -s)" in
        Linux*)
            if command -v dnf &> /dev/null; then
                echo "fedora"
            else
                echo "linux_otro"
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "windows"
            ;;
        *)
            echo "desconocido"
            ;;
    esac
}

OS=$(detectar_os)

# =============================================================================
# Paso 1: Verificación del sistema
# =============================================================================
separador "Paso 1/8 — Verificando sistema"

case "$OS" in
    fedora)
        ok "Fedora detectado."
        ;;
    linux_otro)
        warn "Distribución Linux detectada, pero no es Fedora (no se encontró 'dnf')."
        warn "El paso de instalación de Python se saltea."
        warn "Asegurate de tener Python ${PYTHON_VERSION_MIN}+ instalado manualmente."
        warn ""
        read -p "¿Continuar de todas formas? (s/N) " respuesta
        if [[ ! "$respuesta" =~ ^[sS]$ ]]; then
            exit 1
        fi
        ;;
    windows)
        ok "Windows detectado (Git Bash)."
        warn "El script NO puede instalar Python automáticamente en Windows."
        warn "Si todavía no lo instalaste:"
        warn "  1. Descargá Python ${PYTHON_VERSION} desde https://www.python.org/"
        warn "  2. Marcá 'Add Python to PATH' en el instalador."
        warn "  3. Cerrá y volvé a abrir Git Bash, luego corré el script de nuevo."
        warn ""
        ;;
    *)
        error "Sistema operativo no reconocido: $(uname -s)"
        error "Este script soporta Fedora y Windows 10/11 (Git Bash)."
        exit 1
        ;;
esac

if ! command -v code &> /dev/null; then
    warn "El comando 'code' (VS Code CLI) no está disponible."
    warn "Si VS Code está instalado, abrilo y ejecutá:"
    warn "  Ctrl+Shift+P → 'Shell Command: Install code command in PATH'"
    warn ""
    read -p "¿Continuar de todas formas y saltear la instalación de plugins? (s/N) " respuesta
    if [[ ! "$respuesta" =~ ^[sS]$ ]]; then
        exit 1
    fi
    INSTALAR_PLUGINS=false
else
    ok "VS Code detectado."
    INSTALAR_PLUGINS=true
fi

# =============================================================================
# Paso 2: Instalación / verificación de Python
# =============================================================================
separador "Paso 2/8 — Verificando Python ${PYTHON_VERSION_MIN}+"

if [[ "$OS" == "fedora" ]]; then
    info "Instalando Python ${PYTHON_VERSION} y herramientas del sistema vía dnf..."
    info "Esto puede pedir tu contraseña de sudo..."
    sudo dnf install -y --skip-unavailable \
        python3 \
        python3-devel \
        git \
        gcc \
        gcc-c++ \
        make
    ok "Paquetes del sistema instalados."
else
    info "Saltando instalación vía gestor de paquetes (no es Fedora)."
fi

# Buscar el binario de Python adecuado (multiplataforma)
# Orden de preferencia: python3.12, python3.11, python3, python, py
PYTHON_BIN=""
for candidato in python${PYTHON_VERSION} python3.11 python3 python py; do
    if command -v "$candidato" &> /dev/null; then
        VERSION_REAL=$("$candidato" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "")
        if [[ -z "$VERSION_REAL" ]]; then
            continue
        fi
        MAJOR=$(echo "$VERSION_REAL" | cut -d. -f1)
        MINOR=$(echo "$VERSION_REAL" | cut -d. -f2)
        MIN_MINOR=$(echo "$PYTHON_VERSION_MIN" | cut -d. -f2)
        # Aceptar Python 3.x con x >= MIN_MINOR
        if [[ "$MAJOR" -eq 3 && "$MINOR" -ge "$MIN_MINOR" ]]; then
            PYTHON_BIN=$(command -v "$candidato")
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "No se encontró Python ${PYTHON_VERSION_MIN}+ disponible en PATH."
    if [[ "$OS" == "windows" ]]; then
        error "Instalá Python desde https://www.python.org/ marcando 'Add Python to PATH',"
        error "luego abrí una nueva ventana de Git Bash y volvé a correr el script."
    else
        error "Instalá Python ${PYTHON_VERSION} manualmente y volvé a correr el script."
    fi
    exit 1
fi

ok "Python disponible en: ${PYTHON_BIN}"
"${PYTHON_BIN}" --version

# Verificar que pip esté disponible
if ! "${PYTHON_BIN}" -m pip --version &> /dev/null; then
    error "pip no está disponible. Intentando instalarlo con ensurepip..."
    "${PYTHON_BIN}" -m ensurepip --upgrade || {
        error "No se pudo instalar pip."
        if [[ "$OS" == "fedora" ]]; then
            error "  sudo dnf install python3-pip"
        else
            error "Reinstalá Python asegurándote de incluir pip en la instalación."
        fi
        exit 1
    }
fi
ok "pip disponible: $("${PYTHON_BIN}" -m pip --version)"

# =============================================================================
# Paso 3: Verificar que el esqueleto esté descomprimido
# =============================================================================
separador "Paso 3/8 — Verificando carpeta del proyecto"

if [ ! -d "$PROYECTO_DIR" ]; then
    error "No encontré la carpeta del proyecto en: $PROYECTO_DIR"
    error ""
    error "Antes de correr este script tenés que:"
    error "  1. Descargar secador_solar_esqueleto.zip"
    error "  2. Descomprimirlo de modo que quede la carpeta:"
    error "       $PROYECTO_DIR"
    error ""
    if [[ "$OS" == "windows" ]]; then
        error "En Windows desde Git Bash:"
        error "  mkdir -p ~/proyectos"
        error "  cd ~/proyectos"
        error "  unzip ~/Downloads/secador_solar_esqueleto.zip"
        error ""
        error "  (~/proyectos equivale a C:\\Users\\TuUsuario\\proyectos)"
    else
        error "Ejemplo:"
        error "  mkdir -p ~/proyectos"
        error "  cd ~/proyectos"
        error "  unzip ~/Descargas/secador_solar_esqueleto.zip"
    fi
    exit 1
fi

if [ ! -f "$PROYECTO_DIR/requirements-dev.txt" ]; then
    error "La carpeta $PROYECTO_DIR existe pero no contiene requirements-dev.txt."
    error "Verificá que el zip se descomprimió correctamente."
    exit 1
fi

ok "Proyecto encontrado en: $PROYECTO_DIR"
cd "$PROYECTO_DIR"

# =============================================================================
# Paso 4: Crear entorno virtual
# =============================================================================
separador "Paso 4/8 — Creando entorno virtual"

if [ -d "$VENV_NAME" ]; then
    warn "Ya existe un entorno virtual en $PROYECTO_DIR/$VENV_NAME"
    read -p "¿Borrarlo y crear uno nuevo? (s/N) " respuesta
    if [[ "$respuesta" =~ ^[sS]$ ]]; then
        rm -rf "$VENV_NAME"
        info "Entorno anterior eliminado."
    else
        info "Reutilizando entorno existente."
    fi
fi

if [ ! -d "$VENV_NAME" ]; then
    "${PYTHON_BIN}" -m venv "$VENV_NAME"
    ok "Entorno virtual creado en: $PROYECTO_DIR/$VENV_NAME"
fi

# Activar venv — la ruta del activate difiere según el OS
# En Git Bash sobre Windows el separador es '/' igual que en Linux,
# pero el script de activación vive en Scripts/ en vez de bin/
if [[ "$OS" == "windows" ]]; then
    ACTIVATE_PATH="$VENV_NAME/Scripts/activate"
else
    ACTIVATE_PATH="$VENV_NAME/bin/activate"
fi

if [ ! -f "$ACTIVATE_PATH" ]; then
    error "No se encontró el script de activación del venv en: $ACTIVATE_PATH"
    error "El entorno virtual puede estar corrupto. Borralo y volvé a correr el script."
    exit 1
fi

# shellcheck source=/dev/null
source "$ACTIVATE_PATH"
ok "Entorno virtual activado."

PYTHON_VENV=$(command -v python)
info "Python activo: $PYTHON_VENV"
python --version

# =============================================================================
# Paso 5: Actualizar pip y instalar dependencias
# =============================================================================
separador "Paso 5/8 — Instalando dependencias"

info "Actualizando pip..."
pip install --upgrade pip --quiet
ok "pip actualizado: $(pip --version)"

info "Instalando dependencias del proyecto (requirements-dev.txt)..."
info "Esto puede tardar unos minutos la primera vez:"
info "  - numpy, scipy, pandas, pvlib (cálculo científico y datos solares)"
info "  - streamlit (interfaz web)"
info "  - plotly + kaleido (gráficas interactivas + export a PNG para el reporte PDF)"
info "  - reportlab (generación del PDF)"
info "El paquete más pesado es kaleido (~50 MB — trae Chromium embebido para"
info "exportar gráficos de Plotly a imágenes sin un navegador del sistema)."
pip install -r requirements-dev.txt
ok "Todas las dependencias instaladas."

# =============================================================================
# Paso 6: Instalar plugins de VS Code
# =============================================================================
separador "Paso 6/8 — Instalando plugins de VS Code"

if [ "$INSTALAR_PLUGINS" = true ]; then
    PLUGINS=(
        "ms-python.python"              # Soporte Python (oficial Microsoft)
        "ms-python.vscode-pylance"      # IntelliSense rápido
        "ms-python.black-formatter"     # Integración con black
        "charliermarsh.ruff"            # Integración con ruff
        "ms-python.debugpy"             # Debugger
        "njpwerner.autodocstring"       # Genera docstrings Google-style automáticamente
        "redhat.vscode-yaml"            # Para los catálogos en YAML
        "tamasfe.even-better-toml"      # Para pyproject.toml
        "eamodio.gitlens"               # Mejoras a Git en VS Code
    )

    for plugin in "${PLUGINS[@]}"; do
        info "Instalando: $plugin"
        code --install-extension "$plugin" --force > /dev/null 2>&1 || warn "Falló: $plugin (continuando)"
    done

    ok "Plugins instalados."
else
    warn "Salteando instalación de plugins (VS Code CLI no disponible)."
fi

# =============================================================================
# Paso 7: Configurar VS Code para el proyecto
# =============================================================================
separador "Paso 7/8 — Configurando VS Code para el proyecto"

mkdir -p .vscode

# La ruta del intérprete en settings.json varía según el OS.
# En Windows el venv queda en .venv\Scripts\python.exe
if [[ "$OS" == "windows" ]]; then
    PYTHON_INTERP_PATH="\${workspaceFolder}/.venv/Scripts/python.exe"
else
    PYTHON_INTERP_PATH="\${workspaceFolder}/.venv/bin/python"
fi

cat > .vscode/settings.json << EOF
{
    "python.defaultInterpreterPath": "${PYTHON_INTERP_PATH}",
    "python.terminal.activateEnvironment": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.testing.unittestEnabled": false,
    "python.analysis.typeCheckingMode": "basic",
    "python.analysis.autoImportCompletions": true,
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit",
            "source.fixAll.ruff": "explicit"
        }
    },
    "ruff.enable": true,
    "ruff.organizeImports": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/.pytest_cache": true
    },
    "autoDocstring.docstringFormat": "google",
    "autoDocstring.startOnNewLine": true
}
EOF
ok "Archivo .vscode/settings.json creado."

cat > .vscode/extensions.json << 'EOF'
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "charliermarsh.ruff",
        "ms-python.debugpy",
        "njpwerner.autodocstring",
        "redhat.vscode-yaml",
        "tamasfe.even-better-toml",
        "eamodio.gitlens"
    ]
}
EOF
ok "Archivo .vscode/extensions.json creado."

cat > .vscode/launch.json << 'EOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Streamlit: Secasol.py",
            "type": "debugpy",
            "request": "launch",
            "module": "streamlit",
            "args": ["run", "Secasol.py"],
            "console": "integratedTerminal",
            "justMyCode": false
        },
        {
            "name": "Pytest: archivo actual",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": ["${file}", "-v"],
            "console": "integratedTerminal"
        }
    ]
}
EOF
ok "Archivo .vscode/launch.json creado (configuraciones de depuración)."

# =============================================================================
# Paso 8: Verificar que todo funciona corriendo los tests
# =============================================================================
separador "Paso 8/8 — Verificando setup con los tests"

info "Corriendo pytest..."
if pytest tests/ -v; then
    ok "Todos los tests pasaron."
else
    error "Algunos tests fallaron. Revisar la salida anterior."
    exit 1
fi

# =============================================================================
# Mensaje final
# =============================================================================
separador "✅ Setup completo"

if [[ "$OS" == "windows" ]]; then
    ACTIVATE_MSG="source .venv/Scripts/activate"
else
    ACTIVATE_MSG="source .venv/bin/activate"
fi

cat << EOF

El proyecto está listo para empezar a codear.

Próximos pasos:

  1. Abrir el proyecto en VS Code:
       cd $PROYECTO_DIR
       code .

  2. VS Code te va a sugerir instalar los plugins recomendados.
     Dale "Install All".

  3. VS Code va a usar automáticamente el venv de .venv/.
     Para verificarlo: abrir cualquier archivo .py y mirar abajo a la derecha,
     debería decir "Python 3.x ('.venv': venv)".

  4. Para activar el venv en una terminal externa:
       cd $PROYECTO_DIR
       ${ACTIVATE_MSG}

  5. Para correr la aplicación Streamlit:
       streamlit run Secasol.py

  6. Para crear el repo en GitHub, seguí las instrucciones en:
       docs/SETUP_GIT.md

¡A codear! 🚀
EOF
