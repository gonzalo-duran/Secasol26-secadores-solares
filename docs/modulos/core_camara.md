<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/camara

Ruta: `core/camara.py`

## Descripción

Dataclasses de la cámara de secado solar.

Jerarquía:
    Camara
    ├── GeometriaCamara       — dimensiones internas [m]
    ├── ConstruccionCamara    — materiales/cubierta/aislación
    ├── ConfiguracionBandejas — número, área, espesor de capa, separación
    ├── ConfiguracionFlujo    — caudal, dirección, HR de entrada
    └── CargaProducto         — producto, humedades y modelos de secado

Almacenado en Proyecto.camara. Para tipologías ARMARIO y GRAN_ESCALA la cámara
recibe aire precalentado por el colector externo. Para tipología CAJA se admite
también una Camara, pero con `construccion.cubierta_translucida_id` obligatoria
(la única fuente de energía es la radiación solar a través del techo).

Convención de unidades (SI estricto):
    Temperaturas: K
    Longitudes:   m
    Masas:        kg
    Humedades del producto: kg agua / kg masa seca (base seca, X)
    Humedad relativa del aire: fracción [0, 1]
    Caudal másico: kg/s

## Clases y funciones

**Clases:**

- `DireccionFlujo`
- `CaraCamara`
- `GeometriaCamara`
- `CapaPared`
- `ParedCamara`
- `CarasTranslucidas`
- `ConstruccionCamara`
- `ConfiguracionBandejas`
- `ConfiguracionFlujo`
- `CargaProducto`
- `ConfiguracionTunel`
- `ConfiguracionCarros`
- `Camara`
- `ForzantesAire`

**Funciones:**

- `advertencias_camara()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
