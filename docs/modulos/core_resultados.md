<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/resultados

Ruta: `core/resultados.py`

## Descripción

Dataclasses de resultados del proyecto de prediseño.

`Resultados` es el espejo de salida del objeto `Proyecto`. Almacena
exclusivamente outputs calculados por los solvers; las entradas viven
en las secciones de configuración (Emplazamiento, Colector, Camara, etc.).

Todos los sub-bloques heredan de `BloqueResultados` (core/advertencias.py),
que implementa el mecanismo de invalidación por hash de entradas.

Naming: las clases se llaman ResultadosXxx para consistencia con tanda5.
En los módulos de cálculo (calculos/) se usan nombres distintos para los
outputs del solver puntual (ej. ResultadosColectorTipo1, ResultadosCamara
en camara_calc.py), sin colisión porque los prefijos de módulo los distinguen.

## Clases y funciones

**Clases:**

- `ResultadosClima`
- `ResultadosColector`
- `ResultadosAuxiliar`
- `ResultadosCamara`
- `ResultadosMotor`
- `ResultadosGlobal`
- `Resultados`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
