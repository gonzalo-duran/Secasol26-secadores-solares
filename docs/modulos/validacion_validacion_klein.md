<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/validacion_klein

Ruta: `validacion/validacion_klein.py`

## Descripción

Validación del modelo de Tipo 1 contra la fórmula empírica de Klein (1979).

La fórmula de Klein para U_top (Duffie & Beckman, ec. 6.4.9) es la referencia
empírica clásica para el coeficiente global de pérdidas superiores de un
colector de placa plana. La comparamos contra el U_top "medido" del modelo
numérico, definido como:

    U_top_modelo = Q_top / (T_abs_medio - T_amb)

donde Q_top son las pérdidas por la cubierta superior (viento + radiación al
cielo) integradas a lo largo del colector.

La idea es verificar que tras la corrección de signos del residual, las
pérdidas superiores del modelo numérico estén en el mismo orden de magnitud
que Klein para un rango razonable de condiciones operativas.

Referencias
-----------
Duffie, J.A. & Beckman, W.A. (2013). Solar Engineering of Thermal Processes,
4ª ed., Wiley. Capítulo 6, ecuación 6.4.9 (Klein 1979).

## Clases y funciones

**Funciones:**

- `u_top_klein()`
- `u_top_modelo()`
- `caso()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
