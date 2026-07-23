"""Vigencia de los resultados que se calculan en un lado y se muestran en otro.

Varios resultados de Secasol viven en ``session_state`` entre pestañas y **nadie
los recalcula al mostrarlos**:

===============  ==========================  ==============================
resultado        lo calcula                  lo consume
===============  ==========================  ==============================
``anual``        P4 ("Calcular año")         P7 + reporte PDF
``horizonte``    P4 (forzantes del aire)     P7 (rama transitoria)
``transitorio``  P7 ("Calcular")             dashboard + exports TXT/JSON/PDF
``constantes``   P7 ("Calcular")             dashboard + exports TXT/JSON/PDF
===============  ==========================  ==============================

Sin detección de desactualización, cambiar la configuración después de calcular
deja números viejos en pantalla sin ninguna señal. En un reporte real del
usuario (S58) los dos bloques del **mismo PDF** se contradecían:
``resultados_globales`` decía ``E_aux = 74.34 MJ`` y ``operacion_anual``,
``0.0 MJ`` — el año se había corrido antes de configurar P5. El cálculo estaba
bien; lo que faltaba era detectar que había quedado viejo.

Este módulo es el **único** lugar que conoce la convención: por cada resultado,
la clave de ``session_state`` donde vive el valor, la clave hermana donde vive
su huella (``<clave>_hash``) y qué secciones del proyecto lo determinan. P4, P7
y el reporte no la replican. La huella en sí la calcula ``core.huellas``, que es
puro.

**Elección deliberada:** detectar y avisar, no recalcular solo. P7 es una vista;
que dispare varios segundos de cómputo por entrar a la pestaña sería peor que el
problema que resuelve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

#: Política de recarga con la que P4 corrió el año. No es sección del proyecto
#: (vive en los widgets de P4), así que viaja aparte y entra como extra.
CLAVE_POLITICA = "p4_politica_recarga"

#: Secciones que determinan cualquier cosa calculada sobre el aire que entra a
#: la cámara: la configuración fija tipología y modo, el emplazamiento la
#: posición solar y la presión, y colector y cámara el propio circuito.
_SECCIONES_AIRE = ("configuracion", "emplazamiento", "colector", "camara")


@dataclass(frozen=True)
class Derivado:
    """Un resultado guardado en ``session_state`` que puede quedar viejo.

    Attributes:
        clave: Clave de ``session_state`` donde vive el valor.
        secciones: Atributos de ``Proyecto`` que lo determinan.
        con_clima: Si la serie climática entra a la huella.
    """

    clave: str
    secciones: tuple[str, ...]
    con_clima: bool = True

    @property
    def clave_hash(self) -> str:
        """Clave hermana donde vive la huella."""
        return f"{self.clave}_hash"


#: Registro de resultados derivados. Agregar uno nuevo es agregar una fila acá
#: y llamar a ``registrar``/``estado`` donde se calcula y donde se muestra.
DERIVADOS: dict[str, Derivado] = {
    # El año depende de todo el sistema, auxiliar incluido: ese fue el caso real.
    "anual": Derivado("p4_resultado_anual", _SECCIONES_AIRE + ("auxiliar",)),
    # Las forzantes son el aire **antes** del auxiliar: P7 le suma el auxiliar y
    # el motor encima, así que cambiar P5 no las invalida.
    "horizonte": Derivado("p4_forzantes_horizonte", _SECCIONES_AIRE),
    # Los resultados de P7 sí incorporan auxiliar y motor/chimenea.
    "transitorio": Derivado(
        "p7_resultados_tr", _SECCIONES_AIRE + ("auxiliar", "motor", "chimenea")
    ),
    # Modo Constantes: no toca la serie climática (las condiciones de borde son
    # los sliders, y viajan como extras).
    "constantes": Derivado(
        "p7_resultados",
        _SECCIONES_AIRE + ("auxiliar", "motor", "chimenea"),
        con_clima=False,
    ),
    # Ventana de producción (gran escala). El lapso y el paso de trabajo viven
    # en ``configuracion``, así que cambiar la ventana ya invalida el resultado.
    "ventana": Derivado(
        "p7_resultado_ventana", _SECCIONES_AIRE + ("auxiliar", "motor", "chimenea")
    ),
}

#: Kwargs del builder de forzantes que P4 deja en ``p4_horizonte_meta``. Son
#: entradas del horizonte tanto como las secciones del proyecto: cambiar el día
#: de análisis o el tipo de forzantes cambia el aire aunque el equipo sea el
#: mismo. Los demás campos del meta (``n_dias`` efectivo, ``horizonte_tipo``)
#: son **derivados** del cálculo, no entradas, y quedan afuera a propósito.
_EXTRAS_HORIZONTE = (
    "usar_ventana",
    "tipo_forzantes",
    "T_op_K",
    "HR_op",
    "T_amb_calc_K",
    "n_dias_solicitado",
    "I_g_max_W_m2",
    "P_proyecto_Pa",
    "dias_consecutivos",
)

# Compatibilidad con los consumidores del anual, que nombran sus claves.
CLAVE_RESULTADO = DERIVADOS["anual"].clave
CLAVE_HASH = DERIVADOS["anual"].clave_hash


def extras_horizonte(meta: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """Extras de un horizonte a partir del meta que persiste P4.

    Args:
        meta: ``p4_horizonte_meta`` (o None/incompleto, en horizontes viejos).

    Returns:
        Dict con los kwargs del builder presentes en el meta.
    """
    if not meta:
        return {}
    return {k: meta[k] for k in _EXTRAS_HORIZONTE if k in meta}


def huella(proyecto, nombre: str, *, extras: Optional[Mapping[str, Any]] = None) -> str:
    """Huella actual de las entradas de un resultado derivado.

    Args:
        proyecto: Proyecto actual.
        nombre: Clave del registro (``"anual"``, ``"horizonte"``, …).
        extras: Entradas que no son secciones del proyecto.

    Returns:
        Hash SHA-256 hexadecimal.
    """
    from core.huellas import huella_entradas

    d = DERIVADOS[nombre]
    return huella_entradas(proyecto, d.secciones, extras=extras, con_clima=d.con_clima)


def registrar(
    session_state,
    nombre: str,
    valor: Any,
    proyecto,
    *,
    extras: Optional[Mapping[str, Any]] = None,
) -> None:
    """Guarda un resultado junto a la huella de las entradas con que se calculó.

    Args:
        session_state: ``st.session_state`` (o un dict, para tests).
        nombre: Clave del registro.
        valor: Resultado a guardar.
        proyecto: Proyecto con el que se calculó.
        extras: Entradas que no son secciones del proyecto.
    """
    d = DERIVADOS[nombre]
    session_state[d.clave] = valor
    try:
        session_state[d.clave_hash] = huella(proyecto, nombre, extras=extras)
    except Exception:
        # Un fallo al huellear no puede tumbar un cálculo que salió bien: sin
        # huella el resultado se muestra marcado como no verificable.
        session_state.pop(d.clave_hash, None)


def estado(
    proyecto,
    session_state,
    nombre: str,
    *,
    extras: Optional[Mapping[str, Any]] = None,
) -> tuple[Optional[Any], bool]:
    """Resultado guardado y si sigue correspondiendo a la configuración actual.

    Args:
        proyecto: Proyecto actual.
        session_state: ``st.session_state`` (o un dict, para tests).
        nombre: Clave del registro.
        extras: Entradas que no son secciones del proyecto.

    Returns:
        ``(valor, vigente)``. Sin resultado devuelve ``(None, True)`` — no hay
        nada que pueda estar desactualizado. Si no se guardó la huella
        (resultado de una sesión anterior al mecanismo) se devuelve
        ``vigente=False``: es preferible pedir un recálculo a mostrar números
        que nadie puede verificar.
    """
    d = DERIVADOS[nombre]
    valor = session_state.get(d.clave)
    if valor is None:
        return None, True

    hash_guardado = session_state.get(d.clave_hash)
    if not hash_guardado:
        return valor, False

    try:
        hash_actual = huella(proyecto, nombre, extras=extras)
    except Exception:
        # Un fallo al huellear no puede tumbar el render: se muestra el
        # resultado, pero marcado como no verificable.
        return valor, False
    return valor, hash_actual == hash_guardado


def invalidar(session_state, nombre: str) -> None:
    """Borra un resultado derivado y su huella.

    Args:
        session_state: ``st.session_state`` (o un dict, para tests).
        nombre: Clave del registro.
    """
    d = DERIVADOS[nombre]
    session_state.pop(d.clave, None)
    session_state.pop(d.clave_hash, None)


# ---------------------------------------------------------------------------
# Envoltorios por resultado
# ---------------------------------------------------------------------------


def politica_anual_guardada(session_state) -> Any:
    """Política de recarga con la que se corrió el año (None si no hay)."""
    return session_state.get(CLAVE_POLITICA)


def extras_anual(session_state) -> dict[str, Any]:
    """Extras del resultado anual: la política con la que se corrió."""
    return {"politica": politica_anual_guardada(session_state)}


def registrar_anual(session_state, resultado, proyecto, politica=None) -> None:
    """Guarda el resultado anual, la política usada y la huella.

    Args:
        session_state: ``st.session_state`` (o un dict, para tests).
        resultado: ``ResultadosAnual`` recién calculado.
        proyecto: Proyecto con el que se corrió el año.
        politica: ``PoliticaRecarga`` usada (None = la default del motor).
    """
    session_state[CLAVE_POLITICA] = politica
    registrar(session_state, "anual", resultado, proyecto, extras={"politica": politica})


def resultado_anual_vigente(proyecto, session_state) -> tuple[Optional[Any], bool]:
    """Resultado anual guardado y si sigue correspondiendo a la configuración."""
    return estado(proyecto, session_state, "anual", extras=extras_anual(session_state))


def horizonte_vigente(proyecto, session_state) -> tuple[Optional[Any], dict, bool]:
    """Forzantes del horizonte transitorio, su meta y si siguen vigentes.

    Returns:
        ``(forzantes, meta, vigente)``. El meta es ``{}`` si no hay horizonte.
    """
    meta = session_state.get("p4_horizonte_meta") or {}
    fz, vigente = estado(proyecto, session_state, "horizonte", extras=extras_horizonte(meta))
    return fz, meta, vigente
