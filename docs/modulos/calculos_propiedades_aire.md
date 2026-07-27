<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/propiedades_aire

Ruta: `calculos/propiedades_aire.py`

## Descripción

Propiedades termofísicas del aire seco en función de la temperatura.

Provee correlaciones ``k(T)``, ``mu(T)``, ``cp(T)``, ``Pr(T)`` y ``rho(T, P)``
para usar en el cálculo **local** del coeficiente convectivo interno de los
colectores (``colector_calc.py`` y ``colector_tipos234_calc.py``), donde la
temperatura del fluido varía a lo largo del canal y las propiedades constantes
a 323 K dejan de ser adecuadas (colectores largos de alto ΔT).

Es aire **seco** (no húmedo: para aire húmedo ver ``psicrometria.py``). El
módulo es puro (sin Streamlit, sin estado). Rango de validez: ~270–420 K.

Coherencia con el modelo histórico: a 323 K (50 °C) las correlaciones
reproducen, dentro de ~1 %, los valores constantes que usaban los motores de
colector (cp=1007, k=0.02814, μ=1.963e-5, Pr=0.703).

Correlaciones
-------------
- Viscosidad dinámica μ(T): ley de Sutherland (White, Viscous Fluid Flow).
- Conductividad térmica k(T): ley de Sutherland para conductividad.
- Calor específico cp(T): ajuste lineal a tablas de aire seco (Incropera).
- Número de Prandtl: Pr(T) = cp(T)·μ(T)/k(T) (consistente, no ajuste aparte).
- Densidad ρ(T, P): gas ideal, ρ = P/(R·T), R = 287.058 J/kg·K.

Referencias
-----------
- White, F.M. Viscous Fluid Flow, 3ª ed. (Sutherland μ y k).
- Incropera & DeWitt, Fundamentals of Heat and Mass Transfer (tablas aire seco).

## Clases y funciones

**Funciones:**

- `mu_aire()`
- `k_aire()`
- `cp_aire()`
- `pr_aire()`
- `beta_aire()`
- `rho_aire()`
- `propiedades_aire()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
