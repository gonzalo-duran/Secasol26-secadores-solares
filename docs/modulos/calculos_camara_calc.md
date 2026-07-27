<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/camara_calc

Ruta: `calculos/camara_calc.py`

## Descripción

Motor numérico de la cámara de secado solar — wire-up del motor termodinámico.

Desde S38 la cámara tiene un **único** motor físico: el balance acoplado
calor-masa (``calculos.camara_termodinamica.simular_secado``). Este módulo arma
los parámetros del motor a partir del objeto ``Camara`` (geometría, materiales,
flujo, producto) y expone el punto de entrada único ``calcular_camara``.

El antiguo motor de "capa fina" (correlaciones empíricas MR(t) de
Lewis/Page/Henderson-Pabis/Midilli/Logarítmico) fue eliminado: era un evaluador
de punto único a temperatura pico, insensible al espesor de lecho y a la
velocidad de aire reales, sin temperaturas ni flujos, y desacoplado de los
pipelines transitorio/multidía/anual. El motor termodinámico lo reemplaza con
física completa.

Lee del catálogo del producto:
    - propiedades_basicas.calor_especifico_seco → c_ps (sólido seco).
    - isoterma.gab.params → para construir aw_func (actividad de agua).

Coeficientes convectivos interiores (S61)
-----------------------------------------
Hasta S60 había **uno solo**, forzado (placa plana con μ/Pr/k congelados a
~50 °C), compartido entre el producto y el film interior de la pared. A bajo
caudal —el caso de todo secador de convección natural— eso daba ``h → 0`` y, con
el film de pared atado a él, ``U_total → 0``: la cámara aparecía perfectamente
aislada justo cuando más pierde. Ahora hay dos, ambos de convección **mixta** y
con propiedades del aire variables con T:

- ``coef_conveccion_producto_local`` — placa horizontal (bandeja), rama según el
  signo de ΔT, combinación transversal ``n = 7/2``.
- ``coef_conveccion_pared_local`` — placa vertical (Churchill-Chu), combinación
  asistida ``n = 3``, con el piso conductivo ``Nu → 0.68``.

A velocidades de convección forzada (≳0.5 m/s) el resultado queda dentro del
~4 % del modelo viejo; la diferencia aparece cuando el flujo se apaga. Ver
``docs/notas/estado_conveccion_natural_secasol.md``.

Referencias:
    - Mujumdar AS (2007). Handbook of Industrial Drying, 3ª ed. CRC Press.
    - Anderson RB (1946); Guggenheim EA (1966); De Boer JH (1953) — modelo GAB.
    - Incropera & DeWitt (7ª ed.), cap. 9 "Free Convection".

## Clases y funciones

**Clases:**

- `_ParamsCamaraTD`

**Funciones:**

- `coef_conveccion_producto_local()`
- `coef_conveccion_pared_local()`
- `estimar_T_flujo_estacionario()`
- `calcular_camara()`
- `calcular_camara_cascada()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
