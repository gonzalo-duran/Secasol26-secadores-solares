<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/idiomas

Ruta: `ui/componentes/idiomas.py`

## Descripción

Idioma activo de la sesión + selector 🌐 (capa con estado, importa streamlit).

La resolución del idioma es: ``st.session_state["idioma"]`` → query param
``?lang=`` (si es válido se copia a la sesión) → español. El query param
permite compartir URLs pre-configuradas del Space y que el manual (pestaña
aparte, stateless) herede el idioma (fase F8 del plan i18n).

La función :func:`t` es el punto de entrada de traducción para TODA la UI:
``t("p1.tipologia.label")``. NUNCA llamarla a nivel de módulo (el idioma
cambia entre reruns): los dicts de etiquetas module-level deben ser funciones.
Ver ``docs/notas/plan_i18n.md`` y CLAUDE.md §Internacionalización.

## Clases y funciones

**Funciones:**

- `idioma_actual()`
- `t()`
- `t_catalogo()`
- `selector_idioma()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
