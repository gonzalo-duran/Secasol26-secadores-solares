<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/manual

Ruta: `ui/manual.py`

## Descripción

Vista del manual de usuario (mejora 36) — estilo SAM, multiidioma (F8).

Se activa con el query param ``?manual=<slug>`` interceptado en ``Secasol.py``
ANTES de inicializar el estado de sesión: la vista es *stateless* y nunca toca
``st.session_state.proyecto``. Los enlaces internos del manual recargan la
página (mismo tab) preservando ``&lang=``; los botones que apuntan al manual
desde la vista de diseño usan ``target=_blank`` (ver
``ui/componentes/manual_link.py``).

Idioma (F8): el visor lee ``idioma_actual()`` (del query param ``?lang=`` en
la pestaña del manual). El *chrome* del visor se traduce vía el namespace
``manual.ui.*``; los títulos del TOC vía ``manual.toc.<slug>.*`` con fallback
al ES de la tupla ``CAPITULOS``. El contenido de cada capítulo vive en
``manual/capitulos/<lang>/*.md``; si falta la traducción se muestra el ES con
un aviso (``manual.ui.solo_es``). La traducción de los 22 capítulos es F9.

## Clases y funciones

**Funciones:**

- `render_manual()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
