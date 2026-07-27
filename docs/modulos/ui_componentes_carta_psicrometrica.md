<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/carta_psicrometrica

Ruta: `ui/componentes/carta_psicrometrica.py`

## Descripción

Carta psicrométrica del proceso completo del secador — figura Plotly (mejora 27).

Capa UI: ensambla la figura interactiva a partir de la capa de cálculo pura
``calculos/carta_psicrometrica.py``. Dibuja:

- el fondo de la carta a la presión del emplazamiento (curva de saturación +
  familia de HR constante 10–90 %),
- la **poligonal del proceso** (ambiente → salida colector → entrada cámara →
  salida cámara) con marcadores y etiquetas,
- la **isentálpica de referencia** punteada desde la entrada de la cámara, para
  visualizar si el secado fue ≈ adiabático (cámara indirecta, el punto de salida
  cae sobre la línea) o no adiabático (cámara directa con techo translúcido, el
  punto de salida queda por encima).

Eje X = temperatura de bulbo seco [°C]; eje Y = humedad absoluta ω [g/kg].

## Clases y funciones

**Funciones:**

- `fig_carta_psicrometrica()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
