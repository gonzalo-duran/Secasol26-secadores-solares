<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/catalogo

Ruta: `core/catalogo.py`

## Descripción

Cargador del catálogo de materiales del colector solar.

Carga los cuatro archivos YAML de la carpeta catalogo/materiales/ al importar
el módulo. Los diccionarios resultantes son de solo lectura durante la sesión.

Estructura de cada entrada de material:
    descripcion, conductividad_termica [W/m·K], densidad [kg/m³],
    calor_especifico [J/kg·K], T_max_servicio [K], fuente, notas.
    Cubiertas añaden: transmitancia_solar, emisividad_ir.
    Placas añaden: absortancia_solar, emisividad_ir.

## Clases y funciones

*(Sin clases ni funciones públicas de nivel superior.)*

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
