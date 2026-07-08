"""Motor de corridas paramétricas (barridos) para P7.

Un barrido corre N simulaciones variando un único parámetro del catálogo
(``calculos/catalogo_parametros_barrido.py``) y dejando todo lo demás constante.

Este módulo contiene, por ahora, la maquinaria de **aplicación de un valor al
proyecto** (``aplicar_parametro`` + resolución de path). El loop completo
(``correr_barrido``) y las dataclasses de configuración/resultado se agregan en
una etapa posterior.

Estrategia de aplicación:
    Para un parámetro normal se localiza el dataclass *padre* del campo (el que
    contiene el atributo final) y se lo reemplaza con ``dataclasses.replace``,
    lo que **regatilla su ``__post_init__``** y por lo tanto revalida el valor
    nuevo contra los códigos ``ValueError`` del modelo. El padre nuevo se
    reasigna a su *abuelo*. Las dataclasses del modelo son mutables, así que la
    reasignación in place funciona.

    Para un parámetro *forzante* (``HR_camara``, ``T_amb``) no se muta el
    proyecto: ``aplicar_parametro`` devuelve un override que el caller inyecta
    como argumento del modo Constantes (``calcular_todo``).
"""

from __future__ import annotations

import copy
import dataclasses
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from calculos.balance_global import (
    calcular_todo,
    calcular_todo_transitorio,
    resumen_camara,
)
from calculos.catalogo_kpis_barrido import kpis_fijos_para_modo, obtener_kpi
from calculos.catalogo_parametros_barrido import ParametroBarrido, obtener_parametro
from calculos.operacion_anual_camara import calcular_operacion_anual_camara


def _resolver(obj: Any, partes: list[str]) -> Any:
    """Sigue una cadena de atributos desde ``obj``.

    Devuelve ``None`` si algún eslabón intermedio es ``None`` (ej. el colector
    de un proyecto CAJA), para que el caller emita un error claro.
    """
    actual = obj
    for nombre in partes:
        actual = getattr(actual, nombre)
        if actual is None:
            return None
    return actual


def _set_campo_via_replace(proyecto: Any, path: str, valor: Any) -> None:
    """Asigna ``valor`` al campo ``path`` del proyecto vía ``dataclasses.replace``.

    Reemplaza el dataclass padre (regatillando su ``__post_init__``) y lo
    reasigna a su abuelo.

    Raises:
        ValueError: Si el contenedor padre es ``None`` (sección ausente) o si
            el campo no existe en el dataclass padre. Los ``ValueError`` de
            validación del propio ``__post_init__`` se propagan tal cual.
    """
    partes = path.split(".")
    leaf = partes[-1]
    padre_path = partes[:-1]

    padre = _resolver(proyecto, padre_path)
    if padre is None:
        raise ValueError(
            f"BARRIDO_CONTENEDOR_NONE: el contenedor de '{path}' es None en el proyecto "
            "(¿sección no configurada para esta tipología?)."
        )

    try:
        nuevo_padre = dataclasses.replace(padre, **{leaf: valor})
    except TypeError as exc:
        raise ValueError(
            f"BARRIDO_CAMPO_INEXISTENTE: '{leaf}' no es un campo de {type(padre).__name__}."
        ) from exc

    if len(padre_path) == 1:
        setattr(proyecto, padre_path[0], nuevo_padre)
    else:
        abuelo = _resolver(proyecto, padre_path[:-1])
        setattr(abuelo, padre_path[-1], nuevo_padre)


def aplicar_parametro(proyecto: Any, parametro_id: str, valor_si: float) -> dict | None:
    """Aplica un valor de barrido al proyecto, o devuelve un override de forzante.

    Args:
        proyecto: ``Proyecto`` sobre el que aplicar (se muta in place para
            parámetros normales). El caller es responsable de pasar un clon si
            no quiere contaminar el original.
        parametro_id: Id de un parámetro del catálogo.
        valor_si: Valor en unidades SI a aplicar.

    Returns:
        ``None`` para parámetros normales (el proyecto quedó mutado). Para
        parámetros forzante, un dict ``{"forzante": <nombre>, "valor_si": <v>}``
        sin mutar el proyecto.

    Raises:
        KeyError: Si ``parametro_id`` no está en el catálogo.
        ValueError: Si el valor es inválido para el campo (propagado desde el
            ``__post_init__`` del modelo) o el path no se puede resolver.
    """
    parametro = obtener_parametro(parametro_id)
    valor = parametro.transform_pre_set(valor_si) if parametro.transform_pre_set else valor_si

    if parametro.es_forzante:
        return {"forzante": parametro.nombre_forzante, "valor_si": valor}

    _set_campo_via_replace(proyecto, parametro.path, valor)
    return None


# ---------------------------------------------------------------------------
# Dataclasses de configuración y resultado del barrido
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BarridoConfig:
    """Configuración de una corrida paramétrica.

    Attributes:
        parametro_id: Id del parámetro a variar (del catálogo).
        valores_si: Valores SI a evaluar, en orden.
        modo: Modo de cálculo (``"constantes"``, ``"transitorio"``, ``"anual"``).
        nombre: Nombre legible de la corrida (para la UI).
        kpis_extra: Ids de KPIs avanzados opt-in a extraer además de los fijos.
        condiciones_constantes: Kwargs de ``calcular_todo`` (T_amb_K, I_g_W_m2,
            v_viento_ms, T_entrada_K, HR_camara). Requerido en modo Constantes.
        forzantes_base: ``ForzantesAire`` del horizonte. Requerido en Transitorio
            salvo que se provea ``forzantes_builder``.
        forzantes_builder: Si se provee, se invoca con el **proyecto clonado y
            ya mutado** en cada punto del barrido para reconstruir las
            forzantes desde cero, en vez de reutilizar ``forzantes_base``
            congelada. Necesario para parámetros cuyo efecto pasa por las
            forzantes en vez de por un campo directo del solver (ej.
            ``acimut_camara``/``pendiente_techo_camara``: la irradiancia
            equivalente de la cámara se computa al armar las forzantes, no
            en el motor). ``None`` (default) → usa ``forzantes_base`` tal
            cual, comportamiento histórico.
        n_dias: Días simulados en Transitorio.
    """

    parametro_id: str
    valores_si: tuple[float, ...]
    modo: str
    nombre: str
    kpis_extra: tuple[str, ...] = ()
    condiciones_constantes: Optional[dict] = None
    forzantes_base: Any = None
    forzantes_builder: Optional[Callable[[Any], Any]] = None
    n_dias: Optional[int] = None


@dataclass(frozen=True)
class PuntoBarrido:
    """Resultado de un punto (un valor del parámetro) del barrido.

    Attributes:
        valor_si: Valor SI evaluado.
        valor_ui: Mismo valor en unidad de UI (para ejes de gráficas).
        convergio: True si la simulación produjo un resultado utilizable.
        kpis: Mapa ``kpi_id -> valor`` (``None`` cuando el KPI no aplica/convergió).
        error: Mensaje de error si el punto falló; ``None`` si corrió.
        advertencias: Advertencias emitidas por el cálculo en este punto.
    """

    valor_si: float
    valor_ui: float
    convergio: bool
    kpis: dict[str, float | None]
    error: Optional[str]
    advertencias: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadosBarrido:
    """Resultado completo de una corrida paramétrica.

    Attributes:
        config: Configuración con la que se corrió.
        parametro_meta: Metadata del parámetro barrido (label, unidades, etc.).
        puntos: Resultado por valor evaluado, en el orden de ``valores_si``.
        t_ejecucion_s: Tiempo total de ejecución del barrido [s].
        nombre: Nombre de la corrida (copia de ``config.nombre`` para la UI).
        creado_en: Timestamp ISO 8601 de creación.
    """

    config: BarridoConfig
    parametro_meta: ParametroBarrido
    puntos: tuple[PuntoBarrido, ...]
    t_ejecucion_s: float
    nombre: str
    creado_en: str


# ---------------------------------------------------------------------------
# Motor del barrido
# ---------------------------------------------------------------------------

# Mapa nombre de forzante -> claves de condiciones_constantes que reemplaza.
# T_amb se inyecta tanto como T ambiente como T de entrada al colector (en el
# sistema abierto de P7, T_entrada ≈ T_amb).
_FORZANTE_A_CONDICIONES: dict[str, tuple[str, ...]] = {
    "HR_camara": ("HR_camara",),
    "T_amb": ("T_amb_K", "T_entrada_K"),
}


def _clonar_proyecto_sin_clima(proyecto: Any) -> Any:
    """Clona el proyecto con ``deepcopy`` pero comparte ``clima`` por referencia.

    El clima (``proyecto.clima``) es un ``DataFrame`` anual horario pesado y el
    barrido nunca lo muta, así que copiarlo por punto sería puro desperdicio.
    Se lo desacopla antes del ``deepcopy`` y se readjunta la referencia original
    al clon (de solo lectura para el barrido).
    """
    clima_ref = getattr(proyecto, "clima", None)
    if clima_ref is None:
        return copy.deepcopy(proyecto)
    proyecto.clima = None
    try:
        clon = copy.deepcopy(proyecto)
    finally:
        proyecto.clima = clima_ref
    clon.clima = clima_ref
    return clon


def _aplicar_forzante_a_condiciones(condiciones: dict, override: dict) -> None:
    """Inyecta un override de forzante en el dict de condiciones (in place)."""
    nombre = override["forzante"]
    valor = override["valor_si"]
    for clave in _FORZANTE_A_CONDICIONES.get(nombre, ()):
        condiciones[clave] = valor


def _despachar_motor(proyecto: Any, config: BarridoConfig, override: dict | None) -> Any:
    """Corre el motor correspondiente al modo y devuelve el objeto de resultado."""
    if config.modo == "constantes":
        condiciones = dict(config.condiciones_constantes or {})
        if override is not None:
            _aplicar_forzante_a_condiciones(condiciones, override)
        return calcular_todo(proyecto=proyecto, **condiciones)
    if config.modo == "transitorio":
        forzantes = (
            config.forzantes_builder(proyecto)
            if config.forzantes_builder is not None
            else config.forzantes_base
        )
        return calcular_todo_transitorio(
            proyecto,
            forzantes_base=forzantes,
            n_dias=config.n_dias or 1,
        )
    if config.modo == "anual":
        return calcular_operacion_anual_camara(proyecto)
    raise ValueError(f"BARRIDO_MODO_DESCONOCIDO: '{config.modo}'.")


def _ids_kpis_a_extraer(config: BarridoConfig) -> list[str]:
    """Ids de KPIs a extraer: los fijos del modo + los extra válidos para el modo."""
    ids = [k.id for k in kpis_fijos_para_modo(config.modo)]
    for kid in config.kpis_extra:
        kpi = obtener_kpi(kid)
        if config.modo in kpi.modos_validos and kid not in ids:
            ids.append(kid)
    return ids


def _extraer_kpis(resultado: Any, ids_kpis: list[str]) -> dict[str, float | None]:
    """Aplica cada extractor al resultado, tolerando extractores que fallen."""
    kpis: dict[str, float | None] = {}
    for kid in ids_kpis:
        try:
            kpis[kid] = obtener_kpi(kid).extractor(resultado)
        except Exception:  # noqa: BLE001 — un extractor roto no debe tumbar el punto
            kpis[kid] = None
    return kpis


def _convergio(resultado: Any, modo: str) -> bool:
    """Heurística de convergencia del punto a partir del resultado."""
    cam = getattr(resultado, "camara", None)
    if cam is not None:
        return bool(resumen_camara(cam)["convergio"])
    # Modo anual (u otros sin cámara escalar): el resultado agregado existe.
    return True


def _advertencias_de(resultado: Any) -> list[str]:
    advs = getattr(resultado, "advertencias", None)
    return list(advs) if advs else []


def correr_barrido(
    proyecto_base: Any,
    config: BarridoConfig,
    *,
    callback_progreso: Optional[Callable[[int, int, float], None]] = None,
) -> ResultadosBarrido:
    """Ejecuta una corrida paramétrica secuencial.

    Para cada valor de ``config.valores_si``: clona el proyecto base (sin copiar
    el clima), aplica el parámetro, corre el motor del modo y extrae los KPIs.
    Captura ``ValueError`` y ``RuntimeError`` por punto: marca el punto como
    fallido y sigue con el siguiente (un valor inválido no aborta el barrido).

    Args:
        proyecto_base: ``Proyecto`` configurado y validado. No se muta.
        config: Configuración del barrido.
        callback_progreso: Si se pasa, se llama por punto con
            ``(indice_completados, total, valor_ui_actual)``.

    Returns:
        ResultadosBarrido con un ``PuntoBarrido`` por valor evaluado.
    """
    parametro = obtener_parametro(config.parametro_id)
    ids_kpis = _ids_kpis_a_extraer(config)
    total = len(config.valores_si)

    t0 = time.perf_counter()
    puntos: list[PuntoBarrido] = []

    for i, valor_si in enumerate(config.valores_si):
        valor_ui = parametro.si_a_ui(valor_si)
        try:
            clon = _clonar_proyecto_sin_clima(proyecto_base)
            override = aplicar_parametro(clon, config.parametro_id, valor_si)
            resultado = _despachar_motor(clon, config, override)
            puntos.append(
                PuntoBarrido(
                    valor_si=valor_si,
                    valor_ui=valor_ui,
                    convergio=_convergio(resultado, config.modo),
                    kpis=_extraer_kpis(resultado, ids_kpis),
                    error=None,
                    advertencias=_advertencias_de(resultado),
                )
            )
        except (ValueError, RuntimeError) as exc:
            puntos.append(
                PuntoBarrido(
                    valor_si=valor_si,
                    valor_ui=valor_ui,
                    convergio=False,
                    kpis={kid: None for kid in ids_kpis},
                    error=str(exc),
                    advertencias=[],
                )
            )
        if callback_progreso is not None:
            callback_progreso(i + 1, total, valor_ui)

    t_ejecucion = time.perf_counter() - t0
    return ResultadosBarrido(
        config=config,
        parametro_meta=parametro,
        puntos=tuple(puntos),
        t_ejecucion_s=t_ejecucion,
        nombre=config.nombre,
        creado_en=datetime.now().isoformat(timespec="seconds"),
    )
