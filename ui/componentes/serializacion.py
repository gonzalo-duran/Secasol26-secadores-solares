"""Helpers de serialización para los botones de "Guardar configuración".

Se exponen:

* :func:`json_default` — handler para ``json.dumps(..., default=json_default)``
  que convierte ``Enum``, ``datetime``, ``date``, ``numpy`` y dataclasses anidadas
  en estructuras JSON-friendly.
* :func:`to_jsonable` — convierte recursivamente un objeto (dataclass, enum, dict,
  list, np.ndarray, etc.) en una estructura compuesta de tipos primitivos.
* :func:`dump_json` — serializa con ``indent=2`` y ``ensure_ascii=False`` para
  que el usuario lea acentos y eñes correctamente.

Diseñado para uso en las pestañas P3–P7. No introduce dependencia con Streamlit
para que sea testeable y compatible con la regla de capas del proyecto.
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
from datetime import date, datetime
from enum import Enum
from typing import Any


def _is_numpy_scalar(obj: Any) -> bool:
    try:
        import numpy as np
    except ImportError:
        return False
    return isinstance(obj, np.generic)


def _numpy_to_native(obj: Any) -> Any:
    return obj.item()


def _is_numpy_array(obj: Any) -> bool:
    try:
        import numpy as np
    except ImportError:
        return False
    return isinstance(obj, np.ndarray)


def to_jsonable(obj: Any, *, max_array_len: int = 0) -> Any:
    """Convierte recursivamente ``obj`` en una estructura JSON-friendly.

    Reglas:
        * ``Enum``                  → su ``.value``.
        * ``datetime``, ``date``    → ISO 8601 (string).
        * ``numpy.ndarray``         → ``list`` (truncado a ``max_array_len`` si > 0).
        * ``numpy`` scalars          → tipo Python nativo.
        * ``dataclass`` (no campos calculados) → ``dict`` con cada campo recursivo.
        * ``dict``                  → ``dict`` recursivo.
        * ``list`` / ``tuple``       → ``list`` recursivo.
        * ``float`` NaN/inf         → ``None`` (JSON estándar no los admite).
        * Resto                     → se devuelve tal cual (str/int/bool/None).

    Args:
        obj: Cualquier objeto del modelo de datos del proyecto.
        max_array_len: Si > 0, los ``np.ndarray`` se truncan a esta longitud
            como precaución contra outputs gigantes. ``0`` = sin truncar.

    Returns:
        Estructura compuesta exclusivamente de tipos serializables por
        ``json.dumps``.
    """
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if _is_numpy_scalar(obj):
        return _numpy_to_native(obj)
    if _is_numpy_array(obj):
        seq = obj.tolist()
        if max_array_len > 0 and len(seq) > max_array_len:
            return seq[:max_array_len] + ["…(truncado)"]
        return [to_jsonable(x, max_array_len=max_array_len) for x in seq]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {}
        for f in dataclasses.fields(obj):
            try:
                val = getattr(obj, f.name)
            except AttributeError:
                continue
            out[f.name] = to_jsonable(val, max_array_len=max_array_len)
        return out
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, max_array_len=max_array_len) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x, max_array_len=max_array_len) for x in obj]
    return str(obj)


def json_default(obj: Any) -> Any:
    """``default=`` hook para ``json.dumps`` cuando ``to_jsonable`` no se usó."""
    return to_jsonable(obj)


def dump_json(d: Any, *, indent: int = 2) -> str:
    """Serializa ``d`` con configuración estándar del proyecto.

    Usa ``ensure_ascii=False`` para preservar acentos y eñes en strings.
    """
    return json.dumps(to_jsonable(d), indent=indent, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Helpers para nombres de archivo de descarga
# ---------------------------------------------------------------------------


def _slug_proyecto(nombre: str | None) -> str:
    """Devuelve un slug seguro para nombre de archivo a partir del nombre de
    proyecto. Reemplaza espacios y caracteres no [A-Za-z0-9_-] por ``_``.
    Si el resultado es vacío, devuelve ``"prediseno"``.
    """
    if not nombre:
        return "prediseno"
    s = nombre.strip()
    # Normalizar: minúsculas, espacios → _, eliminar acentos básicos por equivalente ascii
    reemplazos = str.maketrans("áéíóúÁÉÍÓÚñÑüÜ", "aeiouAEIOUnNuU")
    s = s.translate(reemplazos)
    # Permitir solo alfanuméricos y _-, el resto a _
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s)
    s = s.strip("_").lower()
    return s or "prediseno"


def _timestamp_descarga() -> str:
    """Devuelve un timestamp YYYY-MM-DD_HH-MM (orden cronológico, Windows-safe)."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def nombre_archivo_descarga(proyecto, seccion: str, ext: str) -> str:
    """Construye el nombre de archivo para una descarga por sección.

    Formato: ``<proyecto>_<seccion>_<YYYY-MM-DD_HH-MM>.<ext>``

    Args:
        proyecto: Objeto Proyecto (se usa ``proyecto.meta.nombre``).
        seccion: Identificador de sección (ej. ``"colector"``, ``"camara"``).
        ext: Extensión sin punto (ej. ``"txt"``, ``"json"``).

    Returns:
        Nombre de archivo listo para usar en ``st.download_button(file_name=...)``.
    """
    meta = getattr(proyecto, "meta", None)
    slug = _slug_proyecto(getattr(meta, "nombre", None) if meta else None)
    return f"{slug}_{seccion}_{_timestamp_descarga()}.{ext}"


def nombre_archivo_reporte(proyecto, ext: str = "pdf") -> str:
    """Nombre del archivo de reporte completo.

    Formato: ``reporte_<proyecto>_<YYYY-MM-DD_HH-MM>.<ext>``
    """
    meta = getattr(proyecto, "meta", None)
    slug = _slug_proyecto(getattr(meta, "nombre", None) if meta else None)
    return f"reporte_{slug}_{_timestamp_descarga()}.{ext}"


# ---------------------------------------------------------------------------
# Helpers para la carga de JSONs guardados
# ---------------------------------------------------------------------------


def parsear_json_seccion(
    uploaded_file: Any, seccion_esperada: str
) -> tuple[dict | None, str | None]:
    """Parsea un archivo JSON subido por ``st.file_uploader`` y valida la sección.

    Args:
        uploaded_file: Objeto que devuelve ``st.file_uploader`` (o ``None``).
        seccion_esperada: Valor esperado del campo ``"seccion"`` del dict
            raíz (ej. ``"colector"``, ``"camara"``).

    Returns:
        Tupla ``(data, error_msg)``. Si todo OK: ``(dict, None)``.
        Si hay error: ``(None, "mensaje")``. Si no se subió nada:
        ``(None, None)``.
    """
    if uploaded_file is None:
        return None, None
    try:
        contenido = uploaded_file.read()
        if isinstance(contenido, bytes):
            contenido = contenido.decode("utf-8")
        data = json.loads(contenido)
    except UnicodeDecodeError as exc:
        return None, f"Archivo no es UTF-8 válido: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"Archivo JSON inválido: {exc}"

    if not isinstance(data, dict):
        return None, "El JSON no es un objeto (debe ser un dict en la raíz)."

    actual = data.get("seccion")
    if actual != seccion_esperada:
        return None, (
            f"El archivo es de sección '{actual}', "
            f"se esperaba '{seccion_esperada}'."
        )
    return data, None


def limpiar_session_state_prefijo(session_state, prefijo: str) -> int:
    """Elimina todas las claves de session_state que empiecen con ``prefijo``.

    Útil al cargar una configuración nueva para que los widgets relancen
    sus valores por defecto desde ``proyecto.X`` en lugar de usar los
    valores cacheados de la sesión.

    Args:
        session_state: ``st.session_state`` (o un dict compatible).
        prefijo: ej. ``"p3_"`` para limpiar todo el estado de P3.

    Returns:
        Número de claves eliminadas.
    """
    claves = [k for k in list(session_state.keys()) if str(k).startswith(prefijo)]
    for k in claves:
        try:
            del session_state[k]
        except KeyError:
            pass
    return len(claves)
