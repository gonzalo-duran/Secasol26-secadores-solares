#!/usr/bin/env bash
# =============================================================================
# Setup del proyecto Secador Solar — Software de Prediseño
# =============================================================================
# Este script automatiza el setup inicial del entorno de desarrollo en Fedora.
#
# Qué hace:
#   1. Verifica que estás en Fedora.
#   2. Instala Python 3.12 y herramientas básicas vía dnf.
#   3. Verifica que el zip del esqueleto esté descomprimido en ~/proyectos/.
#   4. Crea el entorno virtual .venv dentro del proyecto.
#   5. Instala las dependencias de desarrollo.
#   6. Instala los plugins de VS Code recomendados.
#   7. Configura VS Code para usar el venv automáticamente.
#   8. Corre los tests para verificar que todo funciona.
#
# Uso:
#   1. Descomprimir secador_solar_esqueleto.zip en ~/proyectos/
#      (debe quedar la carpeta ~/proyectos/secador_solar/)
#   2. Hacer ejecutable el script:
#         chmod +x setup_secador_solar.sh
#   3. Ejecutar:
#         ./setup_secador_solar.sh
#
# Requisitos:
#   - Fedora 40 o superior
#   - Conexión a internet
#   - VS Code instalado (comando 'code' disponible en PATH)
# =============================================================================

set -e  # Abortar si algún comando falla

# --- Configuración ---
PROYECTO_DIR="$HOME/proyectos/secador_solar"
PYTHON_VERSION="3.12"
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
# Paso 1: Verificación del sistema
# =============================================================================
separador "Paso 1/8 — Verificando sistema"

if ! command -v dnf &> /dev/null; then
    error "Este script requiere Fedora (no se encontró 'dnf')."
    error "Si estás en otra distro, instalá Python ${PYTHON_VERSION} manualmente"
    error "y corré los pasos 4 en adelante a mano."
    exit 1
fi
ok "Fedora detectado."

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
# Paso 2: Instalación de Python 3.12 y herramientas
# =============================================================================
separador "Paso 2/8 — Instalando Python ${PYTHON_VERSION} y herramientas del sistema"

info "Esto puede pedir tu contraseña de sudo..."

# En Fedora 44, Python 3.12 es el intérprete del sistema.
# Los nombres de paquete correctos son python3 y python3-devel.
# python3-pip no existe como paquete separado: pip viene incluido con python3.
# git, gcc, gcc-c++ y make probablemente ya estén instalados, --skip-unavailable
# evita que el comando falle si algún paquete ya está presente o no existe.
sudo dnf install -y --skip-unavailable \
    python3 \
    python3-devel \
    git \
    gcc \
    gcc-c++ \
    make

ok "Paquetes del sistema instalados."

# Buscar el binario de Python 3.12 — puede llamarse python3.12 o python3
PYTHON_BIN=""
for candidato in python${PYTHON_VERSION} python3; do
    if command -v "$candidato" &> /dev/null; then
        VERSION_REAL=$("$candidato" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ "$VERSION_REAL" == "${PYTHON_VERSION}"* ]] || [[ "$VERSION_REAL" == "3."* ]]; then
            PYTHON_BIN=$(which "$candidato")
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "No se encontró Python 3 después de la instalación."
    exit 1
fi

ok "Python disponible en: ${PYTHON_BIN}"
${PYTHON_BIN} --version

# Verificar que pip esté disponible en el intérprete encontrado
if ! ${PYTHON_BIN} -m pip --version &> /dev/null; then
    error "pip no está disponible. Intentando instalarlo con ensurepip..."
    ${PYTHON_BIN} -m ensurepip --upgrade || {
        error "No se pudo instalar pip. Instalalo manualmente con:"
        error "  sudo dnf install python3-pip"
        exit 1
    }
fi
ok "pip disponible: $(${PYTHON_BIN} -m pip --version)"

# =============================================================================
# Paso 3: Verificar que el esqueleto esté descomprimido
# =============================================================================
separador "Paso 3/8 — Verificando carpeta del proyecto"

if [ ! -d "$PROYECTO_DIR" ]; then
    error "No encontré la carpeta del proyecto en: $PROYECTO_DIR"
    error ""
    error "Antes de correr este script tenés que:"
    error "  1. Descargar secador_solar_esqueleto.zip"
    error "  2. Descomprimirlo en ~/proyectos/"
    error "     (debe quedar la carpeta ~/proyectos/secador_solar/)"
    error ""
    error "Ejemplo:"
    error "  mkdir -p ~/proyectos"
    error "  cd ~/proyectos"
    error "  unzip ~/Descargas/secador_solar_esqueleto.zip"
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
    ${PYTHON_BIN} -m venv "$VENV_NAME"
    ok "Entorno virtual creado en: $PROYECTO_DIR/$VENV_NAME"
fi

# Activar venv para los pasos siguientes
source "$VENV_NAME/bin/activate"
ok "Entorno virtual activado."

# Verificar que estamos usando el Python del venv
PYTHON_VENV=$(which python)
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
info "Esto puede tardar unos minutos la primera vez (numpy, scipy, pvlib...)"
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
    warn "Salteando instalación de plugins."
fi

# =============================================================================
# Paso 7: Configurar VS Code para el proyecto
# =============================================================================
separador "Paso 7/8 — Configurando VS Code para el proyecto"

mkdir -p .vscode

cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
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
            "name": "Streamlit: app.py",
            "type": "debugpy",
            "request": "launch",
            "module": "streamlit",
            "args": ["run", "app.py"],
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
     debería decir "Python 3.12.x ('.venv': venv)".

  4. Para activar el venv en una terminal externa:
       cd $PROYECTO_DIR
       source .venv/bin/activate

  5. Para correr la aplicación Streamlit (todavía vacía):
       streamlit run app.py

  6. Para crear el repo en GitHub, seguí las instrucciones en:
       docs/SETUP_GIT.md

¡A codear! 🚀
EOF
