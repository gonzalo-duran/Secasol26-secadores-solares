"""Widget único de render de advertencias con i18n por código (plan i18n, F5).

Reemplaza los renders inline duplicados de P3–P6. Cada :class:`Advertencia`
se traduce por su ``codigo`` contra las claves
``advertencias.<CODIGO>.mensaje`` / ``.sugerencia``, interpolando
``adv.contexto``. La cascada de :func:`traducir` cubre el fallback por
idioma; además se pasa el texto ES de ``core/`` (``adv.mensaje`` /
``adv.sugerencia``) como ``default``, de modo que un código todavía sin
plantilla YAML muestra igual el mensaje original en español (nunca la clave
cruda ni una excepción).
"""

from __future__ import annotations

from collections.abc import Iterable

import streamlit as st

from core.advertencias import Advertencia, Severidad
from ui.componentes.idiomas import idioma_actual
from ui.componentes.traducciones import traducir

_ICONOS_SEVERIDAD: dict[Severidad, str] = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}


def texto_advertencia(adv: Advertencia, lang: str) -> tuple[str, str]:
    """Resuelve (mensaje, sugerencia) traducidos de una advertencia.

    Args:
        adv: Advertencia generada en ``core/``.
        lang: Código de idioma destino (``es``/``en``/``pt``).

    Returns:
        Tupla ``(mensaje, sugerencia)`` traducida e interpolada con
        ``adv.contexto``. Si la clave no existe o el formato falla, cae al
        texto ES de ``core/`` (``adv.mensaje`` / ``adv.sugerencia``).
    """
    mensaje = traducir(
        f"advertencias.{adv.codigo}.mensaje", lang, default=adv.mensaje, **adv.contexto
    )
    sugerencia = traducir(
        f"advertencias.{adv.codigo}.sugerencia", lang, default=adv.sugerencia, **adv.contexto
    )
    return mensaje, sugerencia


def render_advertencias(
    advertencias: Iterable[Advertencia], *, con_sugerencia: bool = True
) -> None:
    """Muestra una lista de advertencias con icono y color por severidad.

    Widget único que unifica los renders inline de P3–P6. El idioma se toma
    de la sesión en cada llamada (nunca a nivel de módulo, ver
    CLAUDE.md §Internacionalización).

    Args:
        advertencias: Iterable de :class:`Advertencia` a mostrar.
        con_sugerencia: Si ``True`` agrega la sugerencia (💡) bajo el mensaje.
    """
    lang = idioma_actual()
    for adv in advertencias:
        icono = _ICONOS_SEVERIDAD.get(adv.severidad, "•")
        mensaje, sugerencia = texto_advertencia(adv, lang)
        texto = f"{icono} **{adv.codigo}** — {mensaje}"
        if con_sugerencia and sugerencia:
            texto += f"\n\n💡 {sugerencia}"
        if adv.severidad == Severidad.CRITICAL:
            st.error(texto)
        elif adv.severidad == Severidad.WARNING:
            st.warning(texto)
        else:
            st.info(texto)
