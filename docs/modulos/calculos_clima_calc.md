<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/clima_calc

Ruta: `calculos/clima_calc.py`

## Descripción

Obtención y caché de datos climáticos NASA POWER.

Descarga datos horarios anuales vía pvlib.iotools.get_nasa_power,
aplica la política de huecos y guarda/lee el caché en parquet.

Política de huecos:
    Huecos ≤ 3 h consecutivos → interpolación lineal en tiempo.
    Huecos > 3 h              → se dejan como NaN; CalidadClima.n_horas_bloqueadas > 0
                                 indica que la UI debe solicitar decisión al usuario.

Conversiones NASA POWER → SI (realizadas aquí, no en core/):
    Temperatura: °C → K  (+273.15)
    Presión:     kPa → Pa (×1000)
    HR:          % → fracción (÷100)
    GHI/DNI/DHI y velocidad del viento: ya en W/m² y m/s (sin conversión).

## Clases y funciones

**Funciones:**

- `obtener_clima()`
- `calcular_POA_horizonte()`
- `dia_tipo_mensual()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
