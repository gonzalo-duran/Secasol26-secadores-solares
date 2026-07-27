<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/manual_render

Ruta: `ui/componentes/manual_render.py`

## Descripción

Parser y render de los capítulos markdown del manual.

Los capítulos (``manual/capitulos/*.md``) son markdown estándar más tres
convenciones propias, invisibles al leerlos en GitHub/Obsidian:

- Bloques "En profundidad" (nivel 2 de lectura), delimitados por comentarios
  HTML::

      <!-- profundidad: Título del bloque -->
      ...contenido markdown, ecuaciones $$...$$, tablas...
      <!-- /profundidad -->

  El visor los convierte en ``st.expander`` colapsados. No se anidan.

- Esquemas SVG (los de ``assets/esquemas/``), como directiva en línea propia::

      <!-- esquema: colectores_seccion_transversal | Caption opcional -->

- Anclas explícitas en headings, con sufijo ``{#ancla}``::

      ## Isotermas de sorción {#isotermas}

  Se renderizan con ``st.header/st.subheader(..., anchor=...)`` para que los
  enlaces ``?manual=slug#ancla`` funcionen sin depender de la generación
  automática de anclas de Streamlit (frágil con acentos). Solo los headings
  con ``{#...}`` son linkeables desde otros capítulos.

Las funciones de parseo y extracción son puras (sin streamlit) para poder
testearlas sin servidor; solo ``render_bloques`` usa streamlit.

## Clases y funciones

**Clases:**

- `Bloque`

**Funciones:**

- `separar_ancla_heading()`
- `parsear_capitulo()`
- `extraer_enlaces_manual()`
- `extraer_anclas()`
- `extraer_esquemas()`
- `render_bloques()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
