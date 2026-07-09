"""Auditoría read-only del avance de internacionalización (plan i18n).

Cuenta, por archivo de la UI, cuántas llamadas ``st.*`` tienen un string
literal visible como primer argumento (o en ``help=``) — es decir, cuánto
falta migrar a ``t()``. No modifica nada.

Uso:
    .venv/bin/python scripts/auditar_i18n.py           # resumen por archivo
    .venv/bin/python scripts/auditar_i18n.py -v        # además, cada línea

La heurística es la misma del test anti-regresión
(``tests/test_ui/test_idiomas.py``): comillas dobles con letras, escape con
``# i18n: exento``. Es una cota inferior (los textos multilínea entre
paréntesis se cuentan por su primera línea).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_WIDGETS_VISIBLES = (
    "title|header|subheader|caption|markdown|info|warning|error|success|"
    "radio|selectbox|multiselect|text_input|text_area|number_input|date_input|"
    "checkbox|toggle|button|download_button|metric|expander|slider|tabs"
)
_RE_LITERAL_VISIBLE = re.compile(
    rf"""st(?:\.sidebar)?\.(?:{_WIDGETS_VISIBLES})\(\s*f?"[^"\n]*[A-Za-zÁÉÍÓÚáéíóúÑñ]"""
)
_RE_HELP_LITERAL = re.compile(r"""help=\s*f?"[^"\n]*[A-Za-zÁÉÍÓÚáéíóúÑñ]""")


def auditar_archivo(ruta: Path) -> list[tuple[int, str]]:
    """Devuelve las líneas (número, texto) con literales visibles sin t()."""
    hallazgos: list[tuple[int, str]] = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if "# i18n: exento" in linea:
            continue
        if _RE_LITERAL_VISIBLE.search(linea) or _RE_HELP_LITERAL.search(linea):
            hallazgos.append((n, linea.strip()))
    return hallazgos


def main() -> None:
    verboso = "-v" in sys.argv
    objetivos = [RAIZ / "Secasol.py"]
    objetivos += sorted((RAIZ / "ui").rglob("*.py"))

    total = 0
    for ruta in objetivos:
        hallazgos = auditar_archivo(ruta)
        if not hallazgos:
            continue
        total += len(hallazgos)
        print(f"{ruta.relative_to(RAIZ)}: {len(hallazgos)}")
        if verboso:
            for n, linea in hallazgos:
                print(f"    {n}: {linea}")
    print(f"\nTotal de literales visibles pendientes: {total}")


if __name__ == "__main__":
    main()
