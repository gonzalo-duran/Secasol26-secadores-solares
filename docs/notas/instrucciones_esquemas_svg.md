# Instrucciones para integrar esquemas SVG en Secasol26

## Contexto

Queremos agregar esquemas explicativos (SVG inline) en la UI de Streamlit
para que el usuario entienda la geometría y el circuito de aire de cada
componente. Los SVG se guardan como archivos `.svg` en `assets/esquemas/`
y se renderizan vía `st.markdown(unsafe_allow_html=True)`.

## Paso 1 — Crear la carpeta y los archivos SVG

Crear `assets/esquemas/` con los siguientes archivos SVG.
Cada archivo es SVG puro (sin `<?xml>` ni `<!DOCTYPE>`), empieza con `<svg`.
Usar colores fijos (no CSS variables) compatibles con fondo blanco y oscuro:
- Textos: `#333` (claro) — en Streamlit se ve bien en ambos temas.
- Bordes: `#555`
- Colores funcionales: mantener los mismos del diseño original
  (rojo `#E24B4A` para flujo, naranja `#EF9F27` para sol, verde `#5DCAA5`
  para bandejas, azul `#85B7EB` para cubierta, violeta `#534AB7` para cotas,
  marrón `#854F0B` para separaciones, etc.)

### assets/esquemas/camara_dimensiones.svg

Esquema isométrico de la cámara de secado mostrando `largo_m`, `ancho_m`,
`alto_m`, `area_bandeja_m2`, `separacion_entre_bandejas_m`, dirección del
flujo (entrada abajo, salida arriba cara opuesta), y bandejas con producto.

(Copiar el SVG del widget `camara_secado_isometrico_v2` de esta conversación,
reemplazando las clases CSS `class="th"` / `class="ts"` por estilos inline:
- `class="th"` → `font-family="sans-serif" font-size="13" font-weight="600"`
- `class="ts"` → `font-family="sans-serif" font-size="10"` )

### assets/esquemas/colector_tipo1.svg

Vista isométrica del colector tipo 1 (canal único, absorbedor en el fondo).
(Copiar del widget `colector_tipo1_isometrico`, misma conversión de clases.)

### assets/esquemas/colectores_seccion_transversal.svg

Secciones transversales comparativas de los 4 tipos de colector.
(Copiar del widget `colectores_seccion_transversal_4tipos`.)

### assets/esquemas/circuito_caja.svg

Circuito de aire del secador tipo CAJA (versión corregida v2).
(Copiar del widget `circuito_aire_secador_caja_v2`.)

### assets/esquemas/circuito_armario.svg

Circuito de aire del secador tipo ARMARIO completo (versión corregida v2).
(Copiar del widget `circuito_aire_secador_armario_v2`.)


## Paso 2 — Crear el helper `ui/componentes/esquemas.py`

```python
"""Helper para renderizar esquemas SVG inline en Streamlit.

Los archivos SVG viven en assets/esquemas/. Se leen una sola vez
y se renderizan con st.markdown(unsafe_allow_html=True) envueltos
en un <div> centrado con ancho máximo configurable.

Uso en las pestañas::

    from ui.componentes.esquemas import mostrar_esquema

    mostrar_esquema("camara_dimensiones")
    mostrar_esquema("colector_tipo1", max_ancho_px=500)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st

_ESQUEMAS_DIR = Path(__file__).parent.parent.parent / "assets" / "esquemas"


@lru_cache(maxsize=32)
def _leer_svg(nombre: str) -> str:
    """Lee el contenido SVG del archivo. Cachea en memoria."""
    ruta = _ESQUEMAS_DIR / f"{nombre}.svg"
    if not ruta.is_file():
        return ""
    return ruta.read_text(encoding="utf-8")


def mostrar_esquema(
    nombre: str,
    max_ancho_px: int = 680,
    caption: str | None = None,
) -> None:
    """Renderiza un esquema SVG inline en la UI.

    Args:
        nombre: Nombre del archivo sin extensión (ej. "camara_dimensiones").
        max_ancho_px: Ancho máximo del contenedor en píxeles.
        caption: Texto opcional debajo del esquema.
    """
    svg = _leer_svg(nombre)
    if not svg:
        st.caption(f"[esquema '{nombre}' no encontrado]")
        return

    html = (
        f'<div style="max-width:{max_ancho_px}px; margin:0.5em auto; '
        f'text-align:center;">\n{svg}\n</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    if caption:
        st.caption(caption)
```


## Paso 3 — Integrar en las pestañas de la UI

### En `ui/p4_camara.py` (Pestaña Cámara)

Dentro del expander de geometría, antes o después de los inputs de
`largo_m`, `ancho_m`, `alto_m`, agregar:

```python
from ui.componentes.esquemas import mostrar_esquema

# Dentro del expander de geometría:
with st.expander("📐 Esquema de la cámara", expanded=False):
    mostrar_esquema("camara_dimensiones",
                    caption="Esquema de la cámara de secado con sus dimensiones principales.")
```

### En `ui/p3_colector.py` (Pestaña Colector)

Después de la selección del tipo de colector, mostrar el esquema relevante:

```python
from ui.componentes.esquemas import mostrar_esquema

# Después del selectbox de tipo de colector:
with st.expander("📐 Esquema del colector", expanded=False):
    if tipo_sel == 1:
        mostrar_esquema("colector_tipo1",
                        caption="Colector Tipo 1: canal único con absorbedor en el fondo.")
    mostrar_esquema("colectores_seccion_transversal", max_ancho_px=600,
                    caption="Sección transversal comparativa de los 4 tipos de colector.")
```

### En `ui/p1_tipologia.py` (Pestaña Tipología)

Después de la descripción de la tipología seleccionada:

```python
from ui.componentes.esquemas import mostrar_esquema

# Después de st.info(_DESC_TIPOLOGIA[tipo_sel]):
with st.expander("📐 Circuito de aire", expanded=False):
    if tipo_sel == Tipologia.CAJA:
        mostrar_esquema("circuito_caja",
                        caption="Circuito de aire del secador tipo Caja.")
    elif tipo_sel == Tipologia.ARMARIO:
        mostrar_esquema("circuito_armario",
                        caption="Circuito de aire del secador tipo Armario.")
```


## Paso 4 — Convertir clases CSS a estilos inline en los SVG

Los SVG generados en esta conversación usan clases de la UI de Claude
(`class="th"`, `class="ts"`) que no existen en Streamlit. Hay que hacer
un find-and-replace global en cada archivo SVG:

```
Reemplazar:  class="th"
Por:         font-family="sans-serif" font-size="13" font-weight="600" fill="#333"

Reemplazar:  class="ts"
Por:         font-family="sans-serif" font-size="10" fill="#555"

Reemplazar:  class="leader"
Por:         stroke="#999" stroke-width="0.5"
```

Si algún elemento `<text>` ya tiene `fill="..."` explícito (colores de cotas,
flujo, etc.), ese `fill` tiene prioridad — verificar que no se duplique.

También reemplazar las CSS variables por colores fijos:
```
var(--color-text-primary)        →  #333
var(--color-text-secondary)      →  #777
var(--color-text-tertiary)       →  #999
var(--color-border-primary)      →  #555
var(--color-border-tertiary)     →  #ddd
var(--color-background-secondary) → #f5f5f5
```

## Notas

- Los SVG usan `width="100%" viewBox="..."` así que son responsivos.
- El helper usa `@lru_cache` para no releer el disco en cada rerun de Streamlit.
- No se agrega ninguna dependencia nueva — solo `st.markdown` que ya se usa.
- Los archivos SVG son estáticos y no tocan `core/` ni `calculos/`.
