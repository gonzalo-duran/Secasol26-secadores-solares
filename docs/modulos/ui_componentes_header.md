<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/header

Ruta: `ui/componentes/header.py`

## Descripción

Header institucional de Secasol26.

Renderiza la barra superior con nombre del programa y logos institucionales.
Oculta el toolbar nativo de Streamlit (espacio vacío con enlace de deploy).

Ubicación en el repo: ui/componentes/header.py

Uso en Secasol.py::

    from ui.componentes.header import render_header

    st.set_page_config(
        page_title="Secasol26",
        page_icon="☀️",
        layout="wide",
    )
    render_header()
    tab1, tab2, ... = st.tabs([...])

Logos esperados en assets/ (raíz del repo):
    assets/logo_grupo.png   — logo del grupo de investigación (fondo transparente)
    assets/logo_inenco.png  — logo INENCO / CONICET      (fondo transparente)

Nota sobre selectores CSS:
    Los data-testid de Streamlit son semiprivados. Verificados con Streamlit 1.33+.
    Si una actualización los cambia, inspeccionar con DevTools del navegador y
    ajustar los selectores en _CSS_OCULTAR_TOOLBAR.

## Clases y funciones

**Funciones:**

- `render_header()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
