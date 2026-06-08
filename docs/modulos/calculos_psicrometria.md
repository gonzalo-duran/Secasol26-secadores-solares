<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/psicrometria

Ruta: `calculos/psicrometria.py`

## Descripción

Ecuaciones psicrométricas del aire húmedo para el sistema de secado solar.

Todas las funciones trabajan en SI:
    T [K], P [Pa], ω [kg_agua / kg_aire_seco], HR [fracción 0–1]

Ecuación de presión de vapor de saturación: Buck (1981), válida para 0–100 °C
con error < 0.05 % en el rango de interés para secado (30–80 °C).

Constante psicrométrica: razón de masas molares agua/aire = 0.622
    (M_agua = 18.015 g/mol, M_aire_seco = 28.966 g/mol → 18.015/28.966 = 0.6220)

Referencias:
    - Buck AL (1981). New equations for computing vapor pressure and
      enhancement factor. J Appl Meteorol 20:1527-1532.
    - WMO-No.8 (2018). Guide to Instruments and Methods of Observation. Cap. 4.
    - Alduchov OA, Eskridge RE (1996). Improved Magnus form approximation of
      saturation vapor pressure. J Appl Meteorol 35:601-609.
    - Rogers RR, Yau MK (1989). A Short Course in Cloud Physics, 3rd ed.
      Pergamon Press. (Calor latente de vaporización lineal en T)
    - ASHRAE Fundamentals (2021), Cap. 1 — Psychrometrics. (Tabla de aire húmedo)
    - Incropera FP, DeWitt DP (2007). Fundamentals of Heat and Mass Transfer,
      6th ed. Wiley. (Analogía de Chilton-Colburn)
    - van den Berg C, Bruin S (1981). Water activity and its estimation in food
      systems. Water Activity: Influences on Food Quality. Academic Press.
      (Modelo GAB)

## Clases y funciones

**Funciones:**

- `presion_vapor_saturacion()`
- `humedad_absoluta()`
- `HR_desde_omega()`
- `omega_saturacion()`
- `temperatura_punto_rocio()`
- `balance_masa_camara()`
- `entalpia_aire_humedo()`
- `calor_latente_vaporizacion()`
- `cp_aire_humedo()`
- `volumen_especifico_aire_humedo()`
- `densidad_aire_humedo()`
- `temperatura_bulbo_humedo()`
- `actividad_agua_desde_X_GAB()`
- `coef_transferencia_masa_chilton_colburn()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
