<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/esquemas

Ruta: `ui/componentes/esquemas.py`

## Descripción

Helper para renderizar esquemas SVG en Streamlit.

Los archivos SVG viven en ``assets/esquemas/`` (raíz del repo). Se leen una
sola vez vía ``functools.lru_cache`` y se inyectan dentro de un iframe vía
``st.iframe``. El iframe aísla el SVG del CSS de Streamlit, evitando que el
tema oscuro repinte los textos del diagrama (``fill="#333"``) con los
colores del tema.

Ubicación en el repo: ui/componentes/esquemas.py

Uso en las pestañas::

    from ui.componentes.esquemas import mostrar_esquema

    mostrar_esquema("camara_dimensiones")
    mostrar_esquema("colectores_seccion_transversal", max_ancho_px=600)

Esquemas disponibles (cada uno corresponde a un archivo
``assets/esquemas/<nombre>.svg``):

- ``camara_dimensiones``: vista isométrica de la cámara con cotas.
- ``colectores_seccion_transversal``: sección transversal comparativa de
  los 4 tipos de colector.
- ``circuito_caja``: circuito de aire del secador tipo CAJA.
- ``circuito_armario``: circuito de aire del secador tipo ARMARIO.

## Clases y funciones

**Funciones:**

- `mostrar_esquema()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
