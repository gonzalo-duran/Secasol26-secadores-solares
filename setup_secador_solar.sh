#!/usr/bin/env bash
# =============================================================================
# Setup del ENTORNO DE DESARROLLO de Secasol (Linux / macOS / Git Bash en Windows)
# =============================================================================
# Para solo USAR Secasol no hace falta este script: alcanza con
#     bash instalar_secasol.sh        (Linux / macOS)
#     instalar_secasol.bat            (Windows, doble clic)
#
# Este script es para quien va a modificar el código:
#   1. Instala Secasol con las herramientas de desarrollo
#      (delega en: instalar_secasol.sh --dev → pytest, black, ruff).
#   2. Instala los plugins de VS Code recomendados (si el comando 'code' existe).
#   3. Escribe .vscode/settings.json, extensions.json y launch.json para usar el .venv.
#
# Uso (desde la carpeta del repositorio):
#     bash setup_secador_solar.sh
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")"

VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; AZUL='\033[0;34m'; SIN_COLOR='\033[0m'
info() { echo -e "${AZUL}[INFO]${SIN_COLOR} $1"; }
ok()   { echo -e "${VERDE}[OK]${SIN_COLOR} $1"; }
warn() { echo -e "${AMARILLO}[WARN]${SIN_COLOR} $1"; }
separador() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
    *)                    OS="unix" ;;
esac

# =============================================================================
# Paso 1: Instalación con herramientas de desarrollo
# =============================================================================
separador "Paso 1/3 — Instalando Secasol (modo desarrollo)"
if [[ "$OS" == "windows" ]]; then
    warn "En Git Bash se usa el instalador de Windows."
    cmd.exe //c "instalar_secasol.bat --dev" < /dev/null
else
    bash ./instalar_secasol.sh --dev
fi

if command -v code &> /dev/null; then
    INSTALAR_PLUGINS=true
else
    warn "El comando 'code' (VS Code) no está en el PATH: se saltean los plugins."
    warn "Para habilitarlo: VS Code → Ctrl+Shift+P → 'Shell Command: Install code command in PATH'"
    INSTALAR_PLUGINS=false
fi

# =============================================================================
# Paso 2: Instalar plugins de VS Code
# =============================================================================
separador "Paso 2/3 — Instalando plugins de VS Code"

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
# Paso 3: Configurar VS Code para el proyecto
# =============================================================================
separador "Paso 3/3 — Configurando VS Code para el proyecto"

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

separador "✅ Entorno de desarrollo listo"
cat << 'EOF'

  - Abrir el proyecto:       code .
  - Correr la aplicación:    bash iniciar_secasol.sh   (Windows: iniciar_secasol.bat)
  - Suite de tests (~10 min): .venv/bin/python -m pytest
  - Antes de commitear:      .venv/bin/python -m black .  &&  .venv/bin/python -m ruff check .

EOF
