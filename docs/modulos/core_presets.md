<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/presets

Ruta: `core/presets.py`

## Descripción

Presets de sistema completo para tipologías (S41).

Factories de configuración inicial coherente. El preset de **gran escala** es
el secador híbrido ADITAL de San Carlos, Salta (tesis doctoral, cap. 3):
túnel semicontinuo a contracorriente de 18 m con 24 carros, banco de 26
colectores descargando a un caño maestro no aislado, y ~5000 kg de pimiento
por campaña.

Lo consumen:
    - ``ui/p1_tipologia.py``: cascada al cambiar la tipología a GRAN_ESCALA
      (puebla colector, cámara y motor con valores realistas de escala
      industrial en lugar de los defaults de armario).
    - ``validacion/validacion_adital.py``: el caso de validación reusa estas
      mismas factories (una sola fuente de verdad para el secador ADITAL).

Capa core/: sin Streamlit.

## Clases y funciones

**Funciones:**

- `cano_maestro_gran_escala()`
- `colector_gran_escala()`
- `camara_gran_escala()`
- `motor_gran_escala()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
