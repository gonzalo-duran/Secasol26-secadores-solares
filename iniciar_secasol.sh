#!/usr/bin/env bash
# =============================================================================
# Abre Secasol en el navegador — Linux y macOS
# =============================================================================
# Uso (desde la carpeta del proyecto):   bash iniciar_secasol.sh
# Requiere haber corrido antes:           bash instalar_secasol.sh
# Para cerrar la aplicación: Ctrl+C en esta terminal.
# Argumentos extra se pasan a Streamlit (ej.: --server.port 8600).
# =============================================================================

set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c "import streamlit" >/dev/null 2>&1; then
    echo "[ERROR] Secasol no está instalado en esta carpeta." >&2
    echo "        Corré primero:  bash instalar_secasol.sh" >&2
    exit 1
fi

echo "Abriendo Secasol en el navegador (la dirección aparece abajo, normalmente http://localhost:8501)..."
echo "Para cerrarla: Ctrl+C en esta terminal."
echo

# showEmailPrompt=false: sin esto, la primera vez Streamlit se queda esperando un
# email en la consola y la aplicación nunca arranca.
exec .venv/bin/python -m streamlit run Secasol.py \
    --server.showEmailPrompt false \
    --browser.gatherUsageStats false \
    "$@"
