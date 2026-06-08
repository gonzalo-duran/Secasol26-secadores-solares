<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/validacion_cruzada_yacon

Ruta: `validacion/validacion_cruzada_yacon.py`

## Descripción

validacion_cruzada_yacon.py
============================
Validación cruzada de los motores de secado disponibles tras la consolidación
del motor termodinámico (S26/2026-05-16).

Compara para condiciones de contorno idénticas:
  - Motor A: capa fina estático (calcular_tiempo_secado_estatico) — modelo
    algebraico empírico, no depende de la masa del producto.
  - Motor B: termodinámico TD con forzantes constantes — balance acoplado
    con pared 3-nodos, evaporación difusiva, condiciones de aire fijas.
  - Motor C: termodinámico TD con forzantes sintéticas día/noche —
    mismo motor B pero con T_sal_col(t) y T_amb(t) senoidales (pico a
    las 12 h, ±15 K T_col, ±5 K T_amb), incluyendo política B
    anti-rehumectación nocturna.

NOTA: El antiguo Motor C (cinético Lewis/Page con forzantes,
camara_calc_dinamico.py) se eliminó al consolidar el motor termodinámico.
El presente Motor C usa el mismo solver físico que B pero alimentado por
una serie senoidal — la diferencia entre B y C aísla el efecto del ciclo
diurno sobre el tiempo total de secado.

Ejecutar desde la raíz del proyecto:
    .venv/bin/python validacion/validacion_cruzada_yacon.py

Salida: tabla en consola + archivo validacion/validacion_cruzada_yacon.md

## Clases y funciones

**Funciones:**

- `correr_motor_A()`
- `correr_motor_B()`
- `correr_motor_C()`
- `extraer_metricas()`
- `formatear_reporte()`
- `main()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
