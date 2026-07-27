<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/huellas

Ruta: `core/huellas.py`

## Descripción

Huellas de las entradas de un cálculo, para detectar resultados viejos.

Varios resultados de Secasol se **calculan en una pestaña y se muestran en
otra**: el análisis anual se corre en P4 y lo dibujan P7 y el reporte; el
horizonte transitorio lo arma P4 y lo consume P7; los resultados de P7 quedan
en sesión y alimentan los exports TXT/JSON/PDF. Ninguno de esos consumidores
recalcula, así que cambiar la configuración después de calcular dejaba números
viejos en pantalla sin ninguna señal — en un reporte real del usuario (S58) dos
bloques del **mismo PDF** se contradecían (``E_aux = 74 MJ`` vs ``0 MJ``).

Este módulo da la pieza pura del mecanismo: huellear las secciones del proyecto
que determinan un resultado. Quién guarda esa huella y cómo se avisa es
responsabilidad de ``ui/componentes/vigencia.py``.

El clima entra por una **firma barata** (largo, extremos del índice y sumas de
GHI y T_amb) en vez de serializar el DataFrame de 8760 filas: alcanza para
detectar que se cambió de sitio, de año o de fuente de datos.

## Clases y funciones

**Clases:**

- `FirmaClima`

**Funciones:**

- `firma_clima()`
- `huella_entradas()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
