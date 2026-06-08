<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/comparar_f4

Ruta: `validacion/comparar_f4.py`

## Descripción

Comparativa F4 con/sin término convectivo cara interna fondo ↔ fluido ci.

Corre los colectores Tipo 2, 3 y 4 con un caso operativo típico (vidrio +
selectiva, T_amb=20 °C, I=800 W/m², viento 2 m/s) con el F4 corregido
(incluye conv_ci_int) y luego monkey-patchea los `_sistema_nodo_*` para
reproducir el comportamiento previo (F4 sin conv_ci_int). Imprime una
tabla con η, T_salida y T_int para cuantificar el impacto.

Uso:
    .venv/bin/python -m validacion.comparar_f4

## Clases y funciones

**Funciones:**

- `correr_tipos()`
- `main()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
