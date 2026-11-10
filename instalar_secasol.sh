#!/usr/bin/env bash
# =============================================================================
# Instalador de Secasol — Linux y macOS
# =============================================================================
# Crea un entorno virtual de Python dentro de la carpeta del proyecto (.venv) e
# instala las MISMAS versiones de librerías que corre la versión en producción
# (requirements.txt, pinneado con ==). No toca el Python del sistema ni instala
# nada fuera de esta carpeta.
#
# Uso (desde la carpeta del proyecto):
#     bash instalar_secasol.sh              # uso normal
#     bash instalar_secasol.sh --iniciar    # instala y abre la aplicación
#     bash instalar_secasol.sh --dev        # + pytest, black y ruff (desarrollo)
#     bash instalar_secasol.sh --limpio     # borra .venv y lo crea de nuevo
#
# Después, para abrir la aplicación:
#     bash iniciar_secasol.sh
#
# Requisitos: Python 3.11 o superior (se recomienda 3.13, la versión que usa
# producción) y conexión a internet (descarga ~300 MB la primera vez).
# =============================================================================

set -euo pipefail

# Versiones de Python aceptadas, en orden de preferencia. 3.13 primero porque
# es la de producción (imagen python:3.13.5-slim del Space).
PY_PREFERIDAS=(3.13 3.12 3.14 3.11)
PY_MIN_MINOR=11
VENV=".venv"

VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; ROJO='\033[0;31m'; AZUL='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${AZUL}[..]${NC} $1"; }
ok()    { echo -e "${VERDE}[OK]${NC} $1"; }
aviso() { echo -e "${AMARILLO}[!!]${NC} $1"; }
error() { echo -e "${ROJO}[ERROR]${NC} $1" >&2; }

uso() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

DEV=false; INICIAR=false; LIMPIO=false
for arg in "$@"; do
    case "$arg" in
        --dev)     DEV=true ;;
        --iniciar) INICIAR=true ;;
        --limpio)  LIMPIO=true ;;
        -h|--help) uso ;;
        *) error "Opción desconocida: $arg (ver --help)"; exit 1 ;;
    esac
done

# Trabajar siempre desde la carpeta del proyecto, se llame de donde se llame.
cd "$(dirname "$0")"
if [[ ! -f requirements.txt || ! -f Secasol.py ]]; then
    error "No encuentro requirements.txt / Secasol.py junto a este script."
    error "Corré el instalador desde la carpeta del repositorio de Secasol."
    exit 1
fi

echo
echo "=============================================="
echo "  Secasol — instalación local"
echo "=============================================="

# -----------------------------------------------------------------------------
# 1. Python
# -----------------------------------------------------------------------------
version_ok() {  # $1 = ejecutable; éxito si es Python 3.>=11
    "$1" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, $PY_MIN_MINOR) else 1)" \
        >/dev/null 2>&1
}

PY=""
for v in "${PY_PREFERIDAS[@]}"; do
    if command -v "python$v" >/dev/null 2>&1 && version_ok "python$v"; then
        PY="$(command -v "python$v")"; break
    fi
done
if [[ -z "$PY" ]]; then
    for cand in python3 python; do
        if command -v "$cand" >/dev/null 2>&1 && version_ok "$cand"; then
            PY="$(command -v "$cand")"; break
        fi
    done
fi
if [[ -z "$PY" ]]; then
    error "No encontré Python 3.$PY_MIN_MINOR o superior."
    error "Instalalo y volvé a correr este script. Por ejemplo:"
    error "  Ubuntu/Debian:  sudo apt install python3 python3-venv"
    error "  Fedora:         sudo dnf install python3"
    error "  macOS:          https://www.python.org/downloads/  (o: brew install python@3.13)"
    exit 1
fi
ok "Python: $PY ($("$PY" --version 2>&1))"
case "$("$PY" -c 'import sys; print(sys.version_info[1])')" in
    13) ;;
    *) aviso "Producción usa Python 3.13. Con otra versión la app funciona, pero algún"
       aviso "resultado numérico puede diferir en los últimos decimales." ;;
esac

# -----------------------------------------------------------------------------
# 2. Entorno virtual
# -----------------------------------------------------------------------------
if [[ "$LIMPIO" == true && -d "$VENV" ]]; then
    info "Borrando el entorno anterior ($VENV)..."
    rm -rf "$VENV"
fi

# Un .venv sin pip (p. ej. creado por otra herramienta) o roto se rehace.
if [[ -d "$VENV" ]] && ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
    aviso "Hay un $VENV que no sirve (sin Python o sin pip). Se crea uno nuevo."
    rm -rf "$VENV"
fi

if [[ ! -d "$VENV" ]]; then
    info "Creando el entorno virtual en $VENV ..."
    if ! "$PY" -m venv "$VENV"; then
        rm -rf "$VENV"
        error "No se pudo crear el entorno virtual."
        error "En Ubuntu/Debian falta el paquete venv:  sudo apt install python3-venv"
        error "(o python3.X-venv para la versión exacta que tengas)."
        exit 1
    fi
    ok "Entorno virtual creado."
else
    ok "Se reutiliza el entorno existente ($VENV). Usá --limpio para rehacerlo."
fi
VPY="$VENV/bin/python"

# -----------------------------------------------------------------------------
# 3. Librerías
# -----------------------------------------------------------------------------
REQ="requirements.txt"
[[ "$DEV" == true ]] && REQ="requirements-dev.txt"

info "Actualizando pip..."
"$VPY" -m pip install --upgrade pip --quiet --disable-pip-version-check
info "Instalando librerías de $REQ (la primera vez tarda unos minutos)..."
"$VPY" -m pip install -r "$REQ" --disable-pip-version-check
ok "Librerías instaladas."

# -----------------------------------------------------------------------------
# 4. Verificación
# -----------------------------------------------------------------------------
info "Verificando la instalación..."
if ! VERSION="$("$VPY" - <<'PY'
import importlib
for mod in ("streamlit", "numpy", "scipy", "pandas", "pvlib", "plotly", "kaleido",
            "reportlab", "yaml", "pyarrow", "openpyxl", "xlrd"):
    importlib.import_module(mod)
import calculos.balance_global  # noqa: F401  (motor completo + catálogos)
import ui.p7_resultados  # noqa: F401  (interfaz)
from core.version import __version__
print(__version__)
PY
)"; then
    error "La verificación falló (ver el error de arriba)."
    exit 1
fi
ok "Secasol $VERSION listo."

if [[ "$DEV" == true ]]; then
    echo
    echo "Herramientas de desarrollo instaladas. Suite completa (~10 min):"
    echo "    $VPY -m pytest"
fi

echo
echo "Para abrir la aplicación:"
echo "    bash iniciar_secasol.sh"
echo "Se abre en el navegador (http://localhost:8501). Para cerrarla: Ctrl+C en esta terminal."
echo

if [[ "$INICIAR" == true ]]; then
    exec bash ./iniciar_secasol.sh
fi
