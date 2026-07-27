<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/unidades

Ruta: `ui/componentes/unidades.py`

## Descripción

Conversiones entre unidades de la interfaz de usuario y el SI interno.

Regla de oro del proyecto: todo lo que entra a core/ y calculos/ está en SI.
Esta es la ÚNICA capa de conversión entre la UI y el modelo.

Convenciones de ángulos (tres en total):
    Almacenamiento interno (Duffie & Beckman):
        acimut γ: 0°=Sur, +90°=Oeste, -90°=Este, ±180°=Norte. Rango [−180°, +180°].
        Usado en core/emplazamiento.py.
    UI de usuario (convención geográfica local, rango completo):
        acimut α: 0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0°, 360°).
        Usado en el widget de acimut de p2_emplazamiento.py.
    pvlib (cálculo interno de irradiancia):
        surface_azimuth ψ: 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste. Rango [0°, 360°).
        Usado en calculos/clima_calc.py y pvlib.irradiance.

    Conversiones:
        Duffie → UI360:  α = (−γ) mod 360
        UI360  → Duffie: γ = (−α) mod 360; si γ > 180: γ −= 360
        Duffie → pvlib:  ψ = (180 + γ) mod 360
        pvlib  → Duffie: γ = (ψ − 180) mod 360; si γ > 180: γ −= 360

Nota: las cuatro conversiones de acimut viven ahora en
``calculos/conversiones_angulo.py`` (matemática pura, también la consume la
capa de cálculo) y se re-exportan acá por compatibilidad con los consumidores
históricos de la UI.

## Clases y funciones

**Funciones:**

- `celsius_a_kelvin()`
- `kelvin_a_celsius()`
- `kpa_a_pa()`
- `pa_a_kpa()`
- `pa_a_hpa()`
- `porcentaje_a_fraccion()`
- `fraccion_a_porcentaje()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
