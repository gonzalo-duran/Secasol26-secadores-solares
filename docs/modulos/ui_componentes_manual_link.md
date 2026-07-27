<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/manual_link

Ruta: `ui/componentes/manual_link.py`

## Descripción

Botones y enlaces hacia el manual de usuario.

El manual se abre SIEMPRE en otra pestaña del navegador (``target="_blank"``),
al estilo del manual de SAM: el usuario lo consulta en paralelo sin perder la
sesión de diseño. Un clic sin ``_blank`` recargaría la app y perdería el
``Proyecto`` en ``st.session_state``, así que todos los enlaces que se
renderizan DENTRO de la vista de diseño deben pasar por este módulo.

La URL es relativa (``?manual=<slug>``): el navegador la resuelve contra el
documento actual, así que funciona igual en ``localhost:8501`` y detrás del
proxy/iframe de Hugging Face Spaces.

## Clases y funciones

**Funciones:**

- `boton_manual()`
- `enlace_manual_inline()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
