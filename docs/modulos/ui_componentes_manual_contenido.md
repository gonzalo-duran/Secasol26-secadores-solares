<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/manual_contenido

Ruta: `ui/componentes/manual_contenido.py`

## Descripción

Tabla de contenidos (TOC) declarativa del manual de usuario.

Este módulo NO importa streamlit: es la fuente de verdad de qué capítulos
existen, en qué orden se navegan y a qué archivo markdown corresponde cada
slug. Lo consumen el visor (``ui/manual.py``), el helper de botones
(``ui/componentes/manual_link.py``) y los tests de integridad
(``tests/test_ui/test_manual.py``).

El contenido vive en ``manual/capitulos/*.md`` (raíz del repo). Cada capítulo
se identifica por un *slug* en kebab-case que es la clave del query param
(``?manual=<slug>``).

## Clases y funciones

**Clases:**

- `CapituloManual`

**Funciones:**

- `ruta_capitulo()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
