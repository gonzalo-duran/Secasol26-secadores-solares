<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/version

Ruta: `core/version.py`

## Descripción

Versión de Secasol.

Fuente única de la versión que corre la aplicación. Vive en `core/` —y no se lee del
`CHANGELOG.md` ni del último tag de git— porque el deploy a Hugging Face Spaces copia
una whitelist de carpetas (`Secasol.py`, `ui/`, `calculos/`, `core/`, `assets/`,
`catalogo/`, `manual/`) y ni el changelog ni el historial de git viajan: leerlos en
runtime andaría en local y fallaría en el Space, que es justo el entorno que el panel
"🔧 Entorno" del sidebar quiere diagnosticar.

Al liberar una versión hay que actualizar este valor junto con el `CHANGELOG.md`;
`tests/test_core/test_version.py` verifica que ambos coincidan.

## Clases y funciones

*(Sin clases ni funciones públicas de nivel superior.)*

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
