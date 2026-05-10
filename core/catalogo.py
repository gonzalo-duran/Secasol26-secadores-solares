"""
Cargador del catálogo de materiales del colector solar.

Carga los cuatro archivos YAML de la carpeta catalogo/materiales/ al importar
el módulo. Los diccionarios resultantes son de solo lectura durante la sesión.

Estructura de cada entrada de material:
    descripcion, conductividad_termica [W/m·K], densidad [kg/m³],
    calor_especifico [J/kg·K], T_max_servicio [K], fuente, notas.
    Cubiertas añaden: transmitancia_solar, emisividad_ir.
    Placas añaden: absortancia_solar, emisividad_ir.
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

_RAIZ: pathlib.Path = pathlib.Path(__file__).parent.parent
_DIR_MATERIALES: pathlib.Path = _RAIZ / "catalogo" / "materiales"
_DIR_PRODUCTOS: pathlib.Path = _RAIZ / "catalogo" / "productos"

_ARCHIVOS_PRODUCTOS: list[str] = [
    "frutas.yaml",
    "hortalizas.yaml",
    "carnes.yaml",
    "hojas_aromaticas.yaml",
    "legumbres_frutos.yaml",
]


def _cargar(nombre: str) -> dict[str, Any]:
    """Carga un archivo YAML de materiales desde la carpeta catalogo/materiales/.

    Args:
        nombre: Nombre del archivo YAML (ej.: 'cubiertas.yaml').

    Returns:
        Diccionario con los materiales del archivo.

    Raises:
        RuntimeError: Si el archivo no existe o no puede parsearse.
    """
    ruta = _DIR_MATERIALES / nombre
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"Catálogo no encontrado: {ruta}. "
            "Verificá que el archivo exista en catalogo/materiales/."
        )
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Error al parsear {ruta}: {exc}") from exc
    return datos or {}


def _cargar_productos() -> dict[str, Any]:
    """Carga y fusiona todos los archivos YAML de productos en un único diccionario.

    Cada archivo puede contener múltiples productos como claves de primer nivel.
    En caso de colisión de IDs entre archivos, el último archivo gana y se emite
    una advertencia en stderr.

    Returns:
        Diccionario {producto_id: datos_producto} con todos los productos disponibles.
    """
    import sys

    resultado: dict[str, Any] = {}
    for archivo in _ARCHIVOS_PRODUCTOS:
        ruta = _DIR_PRODUCTOS / archivo
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"[catalogo] Advertencia: {ruta} no encontrado, ignorado.", file=sys.stderr)
            continue
        except yaml.YAMLError as exc:
            print(f"[catalogo] Error al parsear {ruta}: {exc}", file=sys.stderr)
            continue
        if not datos:
            continue
        for prod_id, prod_datos in datos.items():
            if prod_id in resultado:
                print(
                    f"[catalogo] Advertencia: producto '{prod_id}' duplicado en {archivo}, "
                    "se sobreescribe.",
                    file=sys.stderr,
                )
            resultado[prod_id] = prod_datos
    return resultado


# Catálogos de materiales — cargados al importar el módulo
CUBIERTAS: dict[str, Any] = _cargar("cubiertas.yaml")
PLACAS: dict[str, Any] = _cargar("placas.yaml")
AISLANTES: dict[str, Any] = _cargar("aislantes.yaml")
FONDOS: dict[str, Any] = _cargar("fondos.yaml")

# Catálogo de productos — fusión de todos los archivos de productos
PRODUCTOS: dict[str, Any] = _cargar_productos()
