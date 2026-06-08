<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/clima

Ruta: `core/clima.py`

## Descripción

Dataclasses para los datos climáticos del emplazamiento.

El objeto Clima almacena la serie temporal horaria descargada de NASA POWER,
ya convertida a unidades SI. El índice del DataFrame es DatetimeIndex UTC tz-aware.

Columnas del DataFrame (definidas en COLUMNAS_SI):
    T_amb_K:    temperatura ambiente a 2 m [K]
    GHI_Wm2:    irradiancia global horizontal [W/m²]
    DNI_Wm2:    irradiancia directa normal [W/m²]
    DHI_Wm2:    irradiancia difusa horizontal [W/m²]
    WS_ms:      velocidad del viento a 2 m [m/s]
    presion_Pa: presión superficial [Pa]
    HR:         humedad relativa [fracción, 0–1]

## Clases y funciones

**Clases:**

- `CalidadClima`
- `Clima`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
