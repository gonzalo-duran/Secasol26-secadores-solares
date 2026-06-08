# Tareas y estado del proyecto

Backlog y estado de avance de **Secasol 26**. El historial de cambios liberados
está en [[CHANGELOG]]. Las instrucciones de trabajo en [[CLAUDE]]. Las
decisiones de diseño en [[docs/decisiones]].

> Estado general (S35): v0.8.0 · 7 pestañas funcionales · suite pytest 885 + 2 xfailed.
> Hoja de ruta a 1.0: resta el modo industrial.

## En progreso

- **Corridas paramétricas (barridos) en P7** — código completo (etapas 1-11);
  resta la verificación manual e2e en Streamlit (etapa 12).

## Pendiente

- **Modo industrial / gran escala** — completar la tipología `GRAN_ESCALA`
  (banco de colectores, secado a toneladas). Último hito hacia v1.0.

## Completado (hitos recientes)

- **Corridas paramétricas (barridos) en P7** (S35): variar un parámetro, N
  corridas, hasta 3 comparables; 3 modos; resultados efímeros.
- **Integración con Obsidian** (S35): notas autogeneradas por módulo + enlaces
  `[[...]]` en los documentos principales.
- **Operación anual de cámara** (cascada A + B) con motor termodinámico:
  eficiencias de Augustus Leon, resumen anual en P4 y detalle mensual en P7.
- **Motor termodinámico de cámara** como modo de cálculo por defecto (S34).
- **Migración de deploy a Hugging Face Spaces** vía GitHub Action (S33).
- **Chimenea solar top-level** con extractor eólico opcional (S30–S31).

## Ver también

- [[CLAUDE]]
- [[docs/decisiones]]
- [[CHANGELOG]]
