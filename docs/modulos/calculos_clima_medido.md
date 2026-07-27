<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/clima_medido

Ruta: `calculos/clima_medido.py`

## Descripción

Pipeline de ingesta de datos climáticos medidos por el usuario (mejora 38, F1a).

Transforma un archivo tabular (CSV / Excel) con mediciones de campaña en un
objeto :class:`core.clima.Clima` con el MISMO contrato que el clima NASA POWER
(7 columnas ``COLUMNAS_SI``, índice horario UTC tz-aware, unidades SI), de modo
que todos los motores aguas abajo funcionen sin cambios.

Etapas del pipeline (orden de :func:`ingerir_clima_medido`):
    1. ``aplicar_mapeo``       — columnas del archivo → variables canónicas SI.
    2. ``inferir_frecuencia_s``— paso temporal nativo (ej. 600 s).
    3. ``regularizar_grilla``  — huecos de filas → filas NaN explícitas.
    4. ``qc_fisico``           — control de calidad físico con reporte.
    5. ``remuestrear_horario`` — media horaria (etiqueta = inicio de hora, UTC).
    6. ``derivar_dni_dhi_erbs``— descomposición GHI → DNI/DHI si faltan.
    7. ``completar_con_nasa``  — columnas ausentes desde NASA POWER.
    8. Política de huecos existente (``clima_calc.aplicar_politica_huecos``).

Cada columna del resultado queda etiquetada con su PROCEDENCIA_* (medida /
derivada / completada_nasa / default) para mostrarse al usuario antes de
confirmar. La serie al paso nativo se conserva en ``Clima.datos_nativos``
(reservada para la fase 1b, motor sub-horario).

Errores con prefijo ``CLIMED_``: ValueError para datos/configuración inválidos,
RuntimeError para fallas de entorno (p. ej. descarga NASA).

## Clases y funciones

**Funciones:**

- `listar_hojas()`
- `leer_tabla()`
- `sugerir_mapeo()`
- `aplicar_mapeo()`
- `inferir_frecuencia_s()`
- `regularizar_grilla()`
- `qc_fisico()`
- `remuestrear_a_paso()`
- `remuestrear_horario()`
- `derivar_dni_dhi_erbs()`
- `completar_con_nasa()`
- `meses_cubiertos()`
- `ingerir_clima_medido()`
- `hash_archivo()`
- `config_a_dict()`
- `config_desde_dict()`
- `hash_ingesta()`
- `guardar_cache_medido()`
- `cargar_cache_medido()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
