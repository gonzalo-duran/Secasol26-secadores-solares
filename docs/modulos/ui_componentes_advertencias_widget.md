<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/advertencias_widget

Ruta: `ui/componentes/advertencias_widget.py`

## Descripción

Widget único de render de advertencias con i18n por código (plan i18n, F5).

Reemplaza los renders inline duplicados de P3–P6. Cada :class:`Advertencia`
se traduce por su ``codigo`` contra las claves
``advertencias.<CODIGO>.mensaje`` / ``.sugerencia``, interpolando
``adv.contexto``. La cascada de :func:`traducir` cubre el fallback por
idioma; además se pasa el texto ES de ``core/`` (``adv.mensaje`` /
``adv.sugerencia``) como ``default``, de modo que un código todavía sin
plantilla YAML muestra igual el mensaje original en español (nunca la clave
cruda ni una excepción).

## Clases y funciones

**Funciones:**

- `texto_advertencia()`
- `render_advertencias()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
