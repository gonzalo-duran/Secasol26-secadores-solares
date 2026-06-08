#!/bin/bash
# Actualiza las notas de Obsidian del proyecto (mapa de módulos + arquitectura).
#
# Regenera docs/modulos/*.md y el bloque autogenerado de docs/arquitectura.md
# a partir del código fuente actual. Idempotente: se puede correr cuando se
# agregan o eliminan módulos.
set -euo pipefail

# Ubicarse en la raíz del proyecto (carpeta padre de scripts/).
cd "$(dirname "$0")/.."

# Preferir el intérprete del entorno virtual del proyecto si existe.
if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" scripts/generar_notas_obsidian.py
echo "Notas de Obsidian actualizadas."
