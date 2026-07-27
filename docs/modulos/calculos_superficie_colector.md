<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/superficie_colector

Ruta: `calculos/superficie_colector.py`

## Descripción

Superficie de respuesta del colector — sustituto interpolado del solver.

Corre el solver estacionario del colector sobre una grilla de condiciones de
borde y devuelve un interpolador que evalúa ``ΔT = T_salida − T_ambiente`` en
tiempo despreciable. Pensado para horizontes largos (el modo anual, 8760 h),
donde llamar al solver una vez por hora domina el costo de la simulación.

**Por qué el espacio de entrada es 3-D.** En los pipelines de convección forzada
el colector se resuelve siempre con ``T_entrada = T_amb`` (ver
``balance_global._correr_colector_horizonte_forzado``). Eso deja la respuesta
determinada por ``(POA, T_amb, v_viento)``: la velocidad del aire en el canal,
cuando se deriva del caudal del sistema, depende de ``T_amb`` únicamente (vía la
densidad), así que no agrega una cuarta dimensión.

**Por qué la interpolación es exacta en la práctica.** Con ``T_entrada = T_amb``
el término de pérdidas de Hottel-Whillier-Bliss, ``U_L·(T_in − T_amb)``, se
anula, y la respuesta queda casi afín en POA — la curvatura restante viene de la
dependencia de ``U_L`` y ``F_R`` con la temperatura de placa y el viento, que es
suave. Medido contra el solver real sobre una grilla 9×5×4: error medio 0.076 K,
p95 0.217 K, máximo 0.276 K. Para dimensionarlo: el propio modelo de colector,
validado contra el prototipo de 10 m del INENCO, da RMSE 0.9 °C frente a
medición real (mejora 38, fase 2). El error de interpolación es un orden por
debajo del error del modelo contra la realidad.

**Qué NO cambia respecto del solver.** La superficie hereda todas las hipótesis
del modelo que muestrea: régimen cuasi-estacionario (sin inercia térmica del
colector, un paso de nube se refleja instantáneamente), capacitancia de placa
despreciable, y la mecánica de canales del tipo configurado. No es una
simplificación física adicional — es el mismo modelo, evaluado por interpolación
en vez de por resolución.

El módulo es puro: no importa ``streamlit`` ni ``core``. Recibe el proyecto solo
para pasárselo al solver.

## Clases y funciones

**Clases:**

- `SuperficieColector`

**Funciones:**

- `construir_superficie()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
