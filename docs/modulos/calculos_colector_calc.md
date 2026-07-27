<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/colector_calc

Ruta: `calculos/colector_calc.py`

## Descripción

Motor numérico del colector solar de aire — Tipo 1.

Modela un colector solar de placa plana con absorbedor en el fondo del cuerpo
del colector y circulación de aire por encima del absorbedor (canal único).

Modelo cuasi-estacionario con discretización espacial a lo largo del eje x
(dirección del flujo). En cada posición x se resuelve un sistema no lineal
algebraico de 3 ecuaciones (cubierta cara externa, cubierta cara interna,
absorbedor) para obtener T_cub_e, T_cub_i y T_abs. La temperatura del fluido
T_f(x) se integra con scipy.integrate.solve_ivp.

Hipótesis principales
---------------------
- Modelo cuasi-estacionario: sin acumulación de calor en superficies sólidas.
- Flujo unidireccional en x, desarrollado hidráulica y térmicamente.
- Transferencia de calor despreciable en dirección z (ancho).
- Factor de forma radiativo cubierta–absorbedor = 1 (superficies paralelas
  infinitas).
- Absortividad de la cubierta despreciable.
- Pérdidas laterales contabilizadas en U_bottom (despreciadas explícitamente).
- Propiedades del aire (cp, k, mu, Pr, rho) dependientes de la temperatura local
  T_f(x) vía ``calculos.propiedades_aire`` (desde S36; antes constantes a 323 K).
  Las constantes ``*_AIRE`` que quedan se usan solo para cálculos asesores
  (Re_medio informativo) y para la cavidad de doble cubierta.

Correlaciones
-------------
- T_cielo:  Swinbank (1963).
- h_viento: McAdams (1954), válida estrictamente para v < 5 m/s;
            se emite advertencia para v ≥ 5 m/s.
- h_int: delegado a ``calculos.correlaciones_nusselt.calcular_h_int()``.
         Selección automática según Re y L/Dh, o correlación elegida por
         el usuario. Ver ese módulo para detalle de cada correlación.

Referencias
-----------
- Duffie & Beckman, "Solar Engineering of Thermal Processes", 4ª ed.
- Swinbank, Q. J. R. Meteorol. Soc. 89, 339-348, 1963.
- McAdams, "Heat Transmission", 3ª ed., 1954.
- Ver calculos/correlaciones_nusselt.py para referencias de Nusselt.

## Clases y funciones

**Clases:**

- `ResultadosColectorTipo1`

**Funciones:**

- `coef_conveccion_interna_local()`
- `calcular_colector_tipo1()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
