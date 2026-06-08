#!/usr/bin/env python3
"""Generador de notas Obsidian a partir de los módulos Python del proyecto.

Escanea las carpetas de código fuente del proyecto y, para cada módulo `.py`
relevante, genera una nota Markdown en ``docs/modulos/`` con su docstring,
clases y funciones de nivel superior. Luego actualiza ``docs/arquitectura.md``
con la lista de enlaces ``[[doble corchete]]`` a esas notas, de modo que el
*graph view* de Obsidian muestre la red de módulos.

Características de diseño:
    - Solo usa la biblioteca estándar (``ast``, ``pathlib``). Sin dependencias.
    - **No modifica** ningún archivo ``.py`` del proyecto.
    - **Idempotente**: se puede correr múltiples veces sin duplicar contenido.
      Las notas de ``docs/modulos/`` se regeneran por completo en cada corrida
      (cada una lleva un marcador de autogeneración) y el bloque de enlaces en
      ``docs/arquitectura.md`` se reemplaza entre marcadores delimitadores.

Uso:
    python3 scripts/generar_notas_obsidian.py
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

# --- Configuración ---------------------------------------------------------

# Raíz del proyecto = carpeta padre de este script (scripts/ -> raíz).
RAIZ = Path(__file__).resolve().parent.parent

# Carpetas de código fuente a escanear (relativas a la raíz del proyecto).
CARPETAS_FUENTE = ("core", "calculos", "ui", "validacion")

# Módulos sueltos en la raíz que también queremos documentar.
MODULOS_RAIZ = ("Secasol.py",)

# Carpeta donde se escriben las notas generadas.
DIR_MODULOS = RAIZ / "docs" / "modulos"

# Archivo de arquitectura que enlaza a todas las notas de módulos.
ARQUITECTURA = RAIZ / "docs" / "arquitectura.md"

# Marcador que identifica una nota como autogenerada (para regenerar sin riesgo).
MARCADOR_AUTOGEN = "<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->"

# Marcadores que delimitan el bloque autogenerado dentro de arquitectura.md.
INICIO_BLOQUE = "<!-- INICIO MODULOS AUTOGENERADO -->"
FIN_BLOQUE = "<!-- FIN MODULOS AUTOGENERADO -->"


# --- Modelo de datos -------------------------------------------------------


@dataclass
class InfoModulo:
    """Información extraída de un módulo Python para generar su nota."""

    ruta_relativa: str  # ej. "core/colector.py"
    slug: str  # ej. "core_colector" (nombre de la nota sin extensión)
    titulo: str  # ej. "core/colector"
    docstring: str  # docstring del módulo ("" si no tiene)
    clases: list[str] = field(default_factory=list)
    funciones: list[str] = field(default_factory=list)


# --- Escaneo y parseo ------------------------------------------------------


def _es_modulo_relevante(ruta: Path) -> bool:
    """Indica si un archivo .py debe documentarse.

    Excluye ``__init__.py`` (no aportan al grafo) y cualquier cosa bajo
    carpetas ocultas o de tests.
    """
    if ruta.name == "__init__.py":
        return False
    partes = ruta.parts
    if any(p.startswith(".") for p in partes):
        return False
    if "tests" in partes:
        return False
    return True


def _recolectar_rutas() -> list[Path]:
    """Devuelve las rutas de los módulos .py a documentar, ordenadas."""
    rutas: list[Path] = []
    for carpeta in CARPETAS_FUENTE:
        base = RAIZ / carpeta
        if base.is_dir():
            rutas.extend(p for p in base.rglob("*.py") if _es_modulo_relevante(p))
    for nombre in MODULOS_RAIZ:
        candidato = RAIZ / nombre
        if candidato.is_file():
            rutas.append(candidato)
    return sorted(rutas)


def _slug_desde_ruta(ruta_relativa: str) -> str:
    """Convierte una ruta relativa en un slug único para el nombre de la nota.

    ``core/colector.py`` -> ``core_colector``.
    """
    sin_ext = ruta_relativa[:-3] if ruta_relativa.endswith(".py") else ruta_relativa
    return sin_ext.replace("/", "_").replace("\\", "_")


def analizar_modulo(ruta: Path) -> InfoModulo:
    """Parsea un módulo .py con ``ast`` y extrae su metadata.

    Args:
        ruta: Ruta absoluta al archivo .py.

    Returns:
        InfoModulo con docstring, clases y funciones de nivel superior.
    """
    ruta_relativa = ruta.relative_to(RAIZ).as_posix()
    slug = _slug_desde_ruta(ruta_relativa)
    titulo = ruta_relativa[:-3] if ruta_relativa.endswith(".py") else ruta_relativa

    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return InfoModulo(
            ruta_relativa=ruta_relativa,
            slug=slug,
            titulo=titulo,
            docstring=f"*(No se pudo parsear el módulo: {exc})*",
        )

    docstring = ast.get_docstring(arbol) or ""
    clases: list[str] = []
    funciones: list[str] = []
    for nodo in arbol.body:
        if isinstance(nodo, ast.ClassDef):
            clases.append(nodo.name)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Solo funciones públicas de nivel superior (no helpers privados).
            if not nodo.name.startswith("_"):
                funciones.append(nodo.name)

    return InfoModulo(
        ruta_relativa=ruta_relativa,
        slug=slug,
        titulo=titulo,
        docstring=docstring,
        clases=clases,
        funciones=funciones,
    )


# --- Generación de notas ---------------------------------------------------


def _primera_linea(texto: str) -> str:
    """Devuelve la primera línea no vacía de un texto (para resúmenes)."""
    for linea in texto.splitlines():
        if linea.strip():
            return linea.strip()
    return ""


def renderizar_nota(info: InfoModulo) -> str:
    """Construye el contenido Markdown de la nota de un módulo."""
    lineas: list[str] = [MARCADOR_AUTOGEN, ""]
    lineas.append(f"# Módulo: {info.titulo}")
    lineas.append("")
    lineas.append(f"Ruta: `{info.ruta_relativa}`")
    lineas.append("")
    lineas.append("## Descripción")
    lineas.append("")
    lineas.append(
        info.docstring.strip() if info.docstring.strip() else "*(Sin docstring de módulo.)*"
    )
    lineas.append("")
    lineas.append("## Clases y funciones")
    lineas.append("")
    if info.clases:
        lineas.append("**Clases:**")
        lineas.append("")
        lineas.extend(f"- `{nombre}`" for nombre in info.clases)
        lineas.append("")
    if info.funciones:
        lineas.append("**Funciones:**")
        lineas.append("")
        lineas.extend(f"- `{nombre}()`" for nombre in info.funciones)
        lineas.append("")
    if not info.clases and not info.funciones:
        lineas.append("*(Sin clases ni funciones públicas de nivel superior.)*")
        lineas.append("")
    lineas.append("## Ver también")
    lineas.append("")
    lineas.append("- [[docs/arquitectura]]")
    lineas.append("- [[CLAUDE]]")
    lineas.append("")
    return "\n".join(lineas)


def limpiar_notas_autogeneradas() -> None:
    """Elimina las notas previas autogeneradas en ``docs/modulos/``.

    Solo borra archivos que contengan el marcador de autogeneración, para no
    tocar notas escritas a mano que el usuario haya colocado en la carpeta.
    """
    if not DIR_MODULOS.is_dir():
        return
    for archivo in DIR_MODULOS.glob("*.md"):
        try:
            if MARCADOR_AUTOGEN in archivo.read_text(encoding="utf-8"):
                archivo.unlink()
        except OSError:
            continue


def escribir_notas(modulos: list[InfoModulo]) -> list[InfoModulo]:
    """Escribe una nota .md por módulo en ``docs/modulos/``."""
    DIR_MODULOS.mkdir(parents=True, exist_ok=True)
    for info in modulos:
        destino = DIR_MODULOS / f"{info.slug}.md"
        destino.write_text(renderizar_nota(info), encoding="utf-8")
    return modulos


# --- Actualización de arquitectura.md --------------------------------------


def _construir_bloque_modulos(modulos: list[InfoModulo]) -> str:
    """Arma el bloque Markdown con los enlaces a las notas de módulos.

    Agrupa por carpeta de primer nivel para una lectura más clara.
    """
    por_carpeta: dict[str, list[InfoModulo]] = {}
    for info in modulos:
        carpeta = info.ruta_relativa.split("/")[0] if "/" in info.ruta_relativa else "(raíz)"
        por_carpeta.setdefault(carpeta, []).append(info)

    lineas: list[str] = [INICIO_BLOQUE, ""]
    lineas.append("## Mapa de módulos")
    lineas.append("")
    lineas.append(
        "_Esta sección se autogenera con `scripts/generar_notas_obsidian.py`. "
        "No editar a mano: los cambios se sobrescriben en cada corrida._"
    )
    lineas.append("")
    for carpeta in sorted(por_carpeta):
        lineas.append(f"### `{carpeta}/`")
        lineas.append("")
        for info in sorted(por_carpeta[carpeta], key=lambda m: m.titulo):
            resumen = _primera_linea(info.docstring)
            sufijo = f" — {resumen}" if resumen else ""
            lineas.append(f"- [[docs/modulos/{info.slug}]]{sufijo}")
        lineas.append("")
    lineas.append(FIN_BLOQUE)
    return "\n".join(lineas)


def actualizar_arquitectura(modulos: list[InfoModulo]) -> None:
    """Inserta o reemplaza el bloque de módulos en ``docs/arquitectura.md``.

    Si el archivo no existe, no hace nada (debe crearse aparte con el contenido
    redactado a mano). Si existe pero no tiene los marcadores, los agrega al
    final. Si ya tiene el bloque, lo reemplaza (idempotente).
    """
    if not ARQUITECTURA.is_file():
        return

    bloque = _construir_bloque_modulos(modulos)
    contenido = ARQUITECTURA.read_text(encoding="utf-8")

    if INICIO_BLOQUE in contenido and FIN_BLOQUE in contenido:
        antes = contenido.split(INICIO_BLOQUE)[0].rstrip("\n")
        despues = contenido.split(FIN_BLOQUE, 1)[1].lstrip("\n")
        partes = [antes, "", bloque]
        if despues.strip():
            partes.extend(["", despues])
        nuevo = "\n".join(partes).rstrip("\n") + "\n"
    else:
        nuevo = contenido.rstrip("\n") + "\n\n" + bloque + "\n"

    ARQUITECTURA.write_text(nuevo, encoding="utf-8")


# --- Orquestación ----------------------------------------------------------


def main() -> None:
    """Punto de entrada: escanea, genera notas y actualiza arquitectura."""
    rutas = _recolectar_rutas()
    modulos = [analizar_modulo(r) for r in rutas]

    limpiar_notas_autogeneradas()
    escribir_notas(modulos)
    actualizar_arquitectura(modulos)

    print(
        f"Notas de Obsidian generadas: {len(modulos)} módulos en {DIR_MODULOS.relative_to(RAIZ)}/"
    )
    if ARQUITECTURA.is_file():
        print(f"Actualizado: {ARQUITECTURA.relative_to(RAIZ)}")
    else:
        print(
            f"Aviso: {ARQUITECTURA.relative_to(RAIZ)} no existe; no se insertó el mapa de módulos."
        )


if __name__ == "__main__":
    main()
