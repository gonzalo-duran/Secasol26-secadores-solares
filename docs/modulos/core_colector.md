<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/colector

Ruta: `core/colector.py`

## Descripción

Dataclasses del sistema de colectores solares de aire tipo placa plana.

Jerarquía:
    Colector
    ├── ColectorUnidad  — describe un módulo físico (materiales + geometría + velocidad)
    └── BancoColectores — configuración en serie/paralelo

La chimenea solar es ahora un componente top-level (``Proyecto.chimenea``,
definido en ``core/chimenea.py``) porque es utilizable también en tipología
CAJA donde ``Proyecto.colector`` es None.

Flujo de aire en banco en paralelo:
    Q_total = n_paralelo × (v × ancho × espaciado)  [m³/s]
    El motor ve Q_total; cada rama del banco trabaja a velocidad_diseno_ms.

Almacenamiento de ángulos: Duffie (acimut 0° = Sur) en Emplazamiento.
La irradiancia en plano inclinado (POA) se calcula on-the-fly en calculos/
con pvlib.irradiance, no se guarda en Colector.

## Clases y funciones

**Clases:**

- `ColectorUnidad`
- `CanoMaestro`
- `BancoColectores`
- `Colector`

**Funciones:**

- `advertencias_colector()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
