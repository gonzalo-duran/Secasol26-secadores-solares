"""Huellas de las entradas de un cálculo, para detectar resultados viejos.

Varios resultados de Secasol se **calculan en una pestaña y se muestran en
otra**: el análisis anual se corre en P4 y lo dibujan P7 y el reporte; el
horizonte transitorio lo arma P4 y lo consume P7; los resultados de P7 quedan
en sesión y alimentan los exports TXT/JSON/PDF. Ninguno de esos consumidores
recalcula, así que cambiar la configuración después de calcular dejaba números
viejos en pantalla sin ninguna señal — en un reporte real del usuario (S58) dos
bloques del **mismo PDF** se contradecían (``E_aux = 74 MJ`` vs ``0 MJ``).

Este módulo da la pieza pura del mecanismo: huellear las secciones del proyecto
que determinan un resultado. Quién guarda esa huella y cómo se avisa es
responsabilidad de ``ui/componentes/vigencia.py``.

El clima entra por una **firma barata** (largo, extremos del índice y sumas de
GHI y T_amb) en vez de serializar el DataFrame de 8760 filas: alcanza para
detectar que se cambió de sitio, de año o de fuente de datos.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from core.advertencias import calcular_hash_entradas


@dataclass(frozen=True)
class FirmaClima:
    """Resumen serializable de la serie climática cargada en el proyecto.

    Attributes:
        n_horas: Cantidad de filas de la serie (0 si no hay clima).
        t_inicio: Primer timestamp del índice, como texto.
        t_fin: Último timestamp del índice, como texto.
        suma_GHI: Suma de la irradiancia global horizontal [W/m²·h].
        suma_T_amb: Suma de la temperatura ambiente [K·h].
    """

    n_horas: int = 0
    t_inicio: str = ""
    t_fin: str = ""
    suma_GHI: float = 0.0
    suma_T_amb: float = 0.0


def firma_clima(proyecto: Any) -> FirmaClima:
    """Firma barata de ``proyecto.clima.datos``.

    Args:
        proyecto: Proyecto a inspeccionar. Sin clima devuelve la firma vacía.

    Returns:
        ``FirmaClima`` con el largo, los extremos del índice y dos sumas.
    """
    datos = getattr(getattr(proyecto, "clima", None), "datos", None)
    if datos is None or len(datos) == 0:
        return FirmaClima()

    sumas: dict[str, float] = {}
    columnas = getattr(datos, "columns", [])
    for col in ("GHI_Wm2", "T_amb_K"):
        if col in columnas:
            serie = datos[col]
            # nansum sin numpy: la serie de pandas ya ignora NaN al sumar.
            sumas[col] = float(serie.sum(skipna=True))

    return FirmaClima(
        n_horas=int(len(datos)),
        t_inicio=str(datos.index[0]),
        t_fin=str(datos.index[-1]),
        suma_GHI=round(sumas.get("GHI_Wm2", 0.0), 3),
        suma_T_amb=round(sumas.get("T_amb_K", 0.0), 3),
    )


def _normalizar(valor: Any) -> Any:
    """Lleva un extra a algo que ``json.dumps`` serialice de forma estable.

    Las dataclasses se expanden a dict (dos instancias iguales dan la misma
    huella); el resto se deja como está y ``calcular_hash_entradas`` cae a
    ``str`` si hace falta.
    """
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return dataclasses.asdict(valor)
    return valor


def huella_entradas(
    proyecto: Any,
    secciones: Iterable[str],
    *,
    extras: Optional[Mapping[str, Any]] = None,
    con_clima: bool = True,
) -> str:
    """Huella SHA-256 de las secciones del proyecto que determinan un resultado.

    Una sección ausente (``None``) también se huellea: agregar el auxiliar
    después de calcular tiene que invalidar el resultado, y ese es exactamente
    el caso que abrió el mecanismo (S58).

    Args:
        proyecto: Proyecto a huellear.
        secciones: Nombres de atributos de ``Proyecto`` (``"colector"``,
            ``"camara"``, …). Los que no existan cuentan como ausentes.
        extras: Entradas que no son secciones del proyecto (condiciones de
            borde, política de recarga, kwargs del builder de forzantes). Se
            ordenan por clave para que la huella no dependa del orden.
        con_clima: Si incluir la firma de la serie climática.

    Returns:
        Hash SHA-256 hexadecimal.
    """
    partes: list[Any] = []
    if con_clima:
        partes.append(firma_clima(proyecto))
    partes.extend(getattr(proyecto, nombre, None) for nombre in secciones)
    if extras:
        partes.append({clave: _normalizar(extras[clave]) for clave in sorted(extras)})
    return calcular_hash_entradas(*partes)
