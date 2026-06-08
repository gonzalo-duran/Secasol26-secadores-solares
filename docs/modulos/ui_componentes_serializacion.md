<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/serializacion

Ruta: `ui/componentes/serializacion.py`

## Descripción

Helpers de serialización para los botones de "Guardar configuración".

Se exponen:

* :func:`json_default` — handler para ``json.dumps(..., default=json_default)``
  que convierte ``Enum``, ``datetime``, ``date``, ``numpy`` y dataclasses anidadas
  en estructuras JSON-friendly.
* :func:`to_jsonable` — convierte recursivamente un objeto (dataclass, enum, dict,
  list, np.ndarray, etc.) en una estructura compuesta de tipos primitivos.
* :func:`dump_json` — serializa con ``indent=2`` y ``ensure_ascii=False`` para
  que el usuario lea acentos y eñes correctamente.

Diseñado para uso en las pestañas P3–P7. No introduce dependencia con Streamlit
para que sea testeable y compatible con la regla de capas del proyecto.

## Clases y funciones

**Funciones:**

- `to_jsonable()`
- `json_default()`
- `dump_json()`
- `nombre_archivo_descarga()`
- `nombre_archivo_reporte()`
- `parsear_json_seccion()`
- `limpiar_session_state_prefijo()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
