"""Carga de un proyecto completo desde el JSON que exporta P7.

P7 sabía **guardar** el proyecto entero (``prediseno_completo.json``) pero no
había forma de volver a cargarlo: solo existían cargadores por sección
(colector en P3, cámara en P4, auxiliar en P5, motor/chimenea en P6), y ni
siquiera servían para el archivo completo, porque ``parsear_json_seccion``
valida el campo ``seccion`` de la raíz —que dice ``"prediseno_completo"``— y lo
rechazaba. Meta, configuración y emplazamiento no se cargaban en ningún lado.
Resultado: el snapshot completo era un artefacto de archivo, no un "guardar
proyecto" (S58).

Este módulo desarma ese JSON y reparte cada sub-dict al deserializador que ya
existía. Es la capa de plomería: no reimplementa ninguna reconstrucción.

**El clima no viaja en el snapshot** — solo su metadato (año, fuente, calidad),
porque las 8760 filas harían un archivo enorme. Al cargar se restauran los
parámetros con los que se lo descargó y se avisa que hay que volver a traerlo en
P2; como la caché parquet es por (lat, lon, año), en general es instantáneo.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, Optional

SECCION_COMPLETA = "prediseno_completo"


class ErrorCargaProyecto(Exception):
    """El JSON no es un proyecto completo de Secasol o está corrupto."""


def _fecha(valor: Any) -> Optional[date]:
    """Convierte un ISO date a ``date``; None si viene vacío o mal formado."""
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def _reconstruir_meta(datos: dict, meta_actual):
    """Meta con nombre/autor/notas del snapshot.

    ``fecha_creacion`` y ``version_software`` se conservan del archivo (son
    historia del proyecto); ``fecha_modificacion`` se deja como la trae, y el
    primer guardado posterior la actualiza.
    """
    from datetime import datetime

    if not datos:
        return meta_actual
    cambios: dict[str, Any] = {}
    for campo in ("nombre", "autor", "notas", "version_software"):
        if datos.get(campo) is not None:
            cambios[campo] = datos[campo]
    for campo in ("fecha_creacion", "fecha_modificacion"):
        crudo = datos.get(campo)
        if crudo:
            try:
                cambios[campo] = datetime.fromisoformat(str(crudo))
            except (TypeError, ValueError):
                pass
    return replace(meta_actual, **cambios)


def _reconstruir_configuracion(datos: dict):
    """Configuración (P1): tipología, modo, día/ventana y paso de trabajo."""
    from core.proyecto import (
        Configuracion,
        DiaAnalisis,
        ModoAnalisis,
        SubtipoGranEscala,
        Tipologia,
    )

    if not datos:
        return Configuracion()
    kwargs: dict[str, Any] = {}
    for campo, enum in (
        ("tipologia", Tipologia),
        ("modo_analisis", ModoAnalisis),
        ("dia_analisis", DiaAnalisis),
        ("subtipo_gran_escala", SubtipoGranEscala),
    ):
        crudo = datos.get(campo)
        if crudo is not None:
            try:
                kwargs[campo] = enum(crudo)
            except ValueError as exc:
                raise ErrorCargaProyecto(f"CARGA_ENUM_INVALIDO: {campo}={crudo!r} ({exc})") from exc
    kwargs["fecha_especifica"] = _fecha(datos.get("fecha_especifica"))
    for campo in ("ventana_inicio", "ventana_fin"):
        fecha = _fecha(datos.get(campo))
        if fecha is not None:
            kwargs[campo] = fecha
    if datos.get("paso_trabajo_s") is not None:
        kwargs["paso_trabajo_s"] = float(datos["paso_trabajo_s"])
    # Política de recarga (S59). Los snapshots anteriores no la traen: en ese
    # caso `desde_dict` devuelve los defaults, que son los que esas corridas
    # usaron de hecho, así que el proyecto viejo se reproduce igual.
    from core.operacion import PoliticaRecarga

    try:
        kwargs["politica_recarga"] = PoliticaRecarga.desde_dict(datos.get("politica_recarga"))
    except (TypeError, ValueError) as exc:
        raise ErrorCargaProyecto(f"CARGA_POLITICA_INVALIDA: {exc}") from exc
    return Configuracion(**kwargs)


def _reconstruir_emplazamiento(datos: dict):
    """Emplazamiento (P2). El acimut viaja en convención Duffie, como se guarda."""
    from core.emplazamiento import Emplazamiento

    if not datos:
        return None
    kwargs: dict[str, Any] = {}
    for campo_json, campo_obj in (
        ("latitud_deg", "latitud_deg"),
        ("longitud_deg", "longitud_deg"),
        ("altitud_m", "altitud_m"),
        ("albedo_suelo", "albedo_suelo"),
        ("zona_horaria", "zona_horaria"),
        ("acimut_colector_deg_duffie", "acimut_colector_deg"),
        ("pendiente_colector_deg", "pendiente_colector_deg"),
        ("z0_terreno_m", "z0_terreno_m"),
    ):
        valor = datos.get(campo_json)
        if valor is not None:
            kwargs[campo_obj] = valor
    return Emplazamiento(**kwargs)


def cargar_proyecto_completo(datos: dict) -> tuple[Any, list[str]]:
    """Reconstruye un ``Proyecto`` completo desde el JSON exportado por P7.

    Cada sección se reconstruye con el mismo deserializador que usa su pestaña,
    y una sección que falle **no aborta la carga**: se omite y se reporta. Es
    preferible recuperar un proyecto al 90 % —con el aviso de qué falta— que
    rechazar el archivo entero por un catálogo que cambió de nombre.

    Args:
        datos: Dict del JSON completo (raíz con ``seccion == "prediseno_completo"``).

    Returns:
        ``(proyecto, avisos)``. ``avisos`` describe lo que no se pudo cargar y
        lo que hay que rehacer a mano (el clima).

    Raises:
        ErrorCargaProyecto: si el JSON no es un proyecto completo de Secasol.
    """
    from core.proyecto import Proyecto

    if not isinstance(datos, dict):
        raise ErrorCargaProyecto("CARGA_JSON_NO_ES_OBJETO: el archivo no es un objeto JSON.")
    seccion = datos.get("seccion")
    if seccion != SECCION_COMPLETA:
        raise ErrorCargaProyecto(
            f"CARGA_SECCION_INCORRECTA: el archivo dice seccion={seccion!r} y se "
            f"esperaba {SECCION_COMPLETA!r}. Para cargar una sección suelta usá "
            "el cargador de su propia pestaña."
        )

    avisos: list[str] = []
    proyecto = Proyecto()
    proyecto.meta = _reconstruir_meta(datos.get("meta") or {}, proyecto.meta)
    proyecto.configuracion = _reconstruir_configuracion(datos.get("configuracion") or {})

    try:
        proyecto.emplazamiento = _reconstruir_emplazamiento(datos.get("emplazamiento") or {})
    except (ValueError, TypeError) as exc:
        avisos.append(f"emplazamiento: {exc}")

    # Secciones opcionales, cada una con el deserializador de su pestaña.
    secciones: list[tuple[str, str, Any]] = []
    from ui.p3_colector import _from_json_colector
    from ui.p4_camara import _from_json_camara
    from ui.p5_auxiliar import _from_json_auxiliar
    from ui.p6_motor import _from_json_chimenea, _from_json_motor

    secciones.append(("colector", "colector", _from_json_colector))
    secciones.append(("camara", "camara", _from_json_camara))
    secciones.append(("auxiliar", "auxiliar", _from_json_auxiliar))
    secciones.append(("chimenea", "chimenea", _from_json_chimenea))

    for clave_json, atributo, constructor in secciones:
        crudo = datos.get(clave_json)
        if not crudo:
            continue
        try:
            setattr(proyecto, atributo, constructor(crudo))
        except (KeyError, ValueError, TypeError) as exc:
            avisos.append(f"{clave_json}: {exc}")

    # El motor devuelve (motor, chimenea_legacy, aviso): los snapshots viejos
    # traían la chimenea colgando del motor.
    crudo_motor = datos.get("motor")
    if crudo_motor:
        try:
            motor, chim_legacy, aviso = _from_json_motor(crudo_motor)
            proyecto.motor = motor
            if chim_legacy is not None and proyecto.chimenea is None:
                proyecto.chimenea = chim_legacy
            if aviso:
                avisos.append(f"motor: {aviso}")
        except (KeyError, ValueError, TypeError) as exc:
            avisos.append(f"motor: {exc}")

    return proyecto, avisos


def resumen_clima_snapshot(datos: dict) -> Optional[dict]:
    """Metadatos del clima que traía el snapshot, para poder rehacer la descarga.

    Devuelve None si el proyecto se guardó sin clima. El DataFrame horario no
    viaja en el archivo: hay que volver a traerlo en P2.
    """
    clima = datos.get("clima") or {}
    if not clima:
        return None
    return {
        "anio": clima.get("anio"),
        "fuente": clima.get("fuente"),
        "n_horas": clima.get("n_horas"),
    }
