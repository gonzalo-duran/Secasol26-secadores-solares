<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/conversiones_angulo

Ruta: `calculos/conversiones_angulo.py`

## Descripción

Conversiones puras entre las tres convenciones de acimut del proyecto.

Estas funciones son **matemática pura de ángulos** (sin estado, sin Streamlit,
sin pandas/numpy): convierten un acimut entre las convenciones Duffie & Beckman,
UI360 y pvlib. Viven en ``calculos/`` —y no en ``ui/componentes/unidades.py``—
porque las consume tanto la UI (widgets de P2/P3, reporte) como la capa de
cálculo (``clima_calc`` para la transposición POA, y el catálogo de barridos
paramétricos). ``ui/componentes/unidades.py`` las re-exporta por compatibilidad.

Las tres convenciones (ver también CLAUDE.md):
    Duffie & Beckman (almacenamiento interno, ``core/emplazamiento.py``):
        acimut γ: 0°=Sur, +90°=Oeste, −90°=Este, ±180°=Norte. Rango [−180, +180].
    UI360 (widget de usuario en P2):
        acimut α: 0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0, 360).
    pvlib (cálculo interno de irradiancia):
        surface_azimuth ψ: 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste. Rango [0, 360).

    Conversiones:
        Duffie → UI360:  α = (−γ) mod 360
        UI360  → Duffie: γ = (−α) mod 360; si γ > 180: γ −= 360
        Duffie → pvlib:  ψ = (180 + γ) mod 360
        pvlib  → Duffie: γ = (ψ − 180) mod 360; si γ > 180: γ −= 360

## Clases y funciones

**Funciones:**

- `acimut_duffie_a_pvlib()`
- `acimut_duffie_a_ui360()`
- `acimut_ui360_a_duffie()`
- `acimut_pvlib_a_duffie()`
- `normalizar_acimut_duffie()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
