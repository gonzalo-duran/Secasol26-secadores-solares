"""
Clases base del sistema de advertencias y mecanismo de invalidación de resultados.

Contiene:
    - Severidad: Enum con niveles INFO, WARNING, CRITICAL.
    - Advertencia: dataclass frozen que representa un aviso de validación.
    - BloqueResultados: clase base para todos los sub-bloques de Resultados,
      con mecanismo de hash para detectar desactualización.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severidad(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Advertencia:
    """Representa un aviso generado durante la validación de una sección.

    Attributes:
        codigo: Identificador único con prefijo de sección (ej: GEO_VOLUMEN_MINIMO).
        severidad: Nivel de severidad (INFO, WARNING, CRITICAL).
        mensaje: Descripción legible del problema.
        campo: Nombre del campo de la dataclass que lo origina.
        sugerencia: Acción recomendada al usuario.
        contexto: Información adicional de diagnóstico (valores actuales, umbrales).
    """

    codigo: str
    severidad: Severidad
    mensaje: str
    campo: str
    sugerencia: str
    contexto: dict[str, Any] = field(default_factory=dict)


def calcular_hash_entradas(*secciones: Any) -> str:
    """Calcula un hash SHA-256 sobre las secciones de entrada serializadas.

    Usado para detectar si los resultados calculados siguen siendo vigentes
    respecto al estado actual de las entradas.

    Args:
        *secciones: Dataclasses de entrada a incluir en el hash.

    Returns:
        String hexadecimal de 64 caracteres (SHA-256).
    """
    import dataclasses

    datos = [dataclasses.asdict(s) for s in secciones]
    serializado = json.dumps(datos, sort_keys=True, default=str)
    return hashlib.sha256(serializado.encode()).hexdigest()


@dataclass
class BloqueResultados:
    """Clase base para todos los sub-bloques de Resultados.

    Implementa el mecanismo de invalidación por hash: cada bloque sabe
    si sus resultados siguen siendo válidos respecto a las entradas actuales.

    Attributes:
        _stale: True si los resultados están desactualizados o nunca calculados.
        _hash_entradas: Hash SHA-256 de las entradas usadas en el último cálculo.
        _timestamp: Momento UTC en que se realizó el último cálculo.
        _advertencias_runtime: Advertencias generadas durante el cálculo (post-solver).
    """

    _stale: bool = field(default=True, repr=False)
    _hash_entradas: str | None = field(default=None, repr=False)
    _timestamp: datetime | None = field(default=None, repr=False)
    _advertencias_runtime: list[Advertencia] = field(default_factory=list, repr=False)

    def marcar_calculado(self, hash_entradas: str) -> None:
        """Marca el bloque como calculado y actualiza el hash y timestamp.

        Args:
            hash_entradas: Hash SHA-256 de las entradas usadas en este cálculo.
        """
        self._stale = False
        self._hash_entradas = hash_entradas
        self._timestamp = datetime.now(tz=timezone.utc)

    def marcar_stale(self) -> None:
        """Marca el bloque como desactualizado (requiere recálculo)."""
        self._stale = True

    def verificar_vigencia(self, hash_entradas_actual: str) -> bool:
        """Verifica si los resultados almacenados siguen siendo válidos.

        Args:
            hash_entradas_actual: Hash actual de las entradas relevantes.

        Returns:
            True si los resultados son vigentes, False si requieren recálculo.
        """
        if self._stale or self._hash_entradas is None:
            return False
        return self._hash_entradas == hash_entradas_actual
