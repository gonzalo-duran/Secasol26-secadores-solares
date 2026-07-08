# Tareas y estado del proyecto

Backlog y estado de avance de **Secasol 26**. El historial de cambios liberados
está en [[CHANGELOG]]. Las instrucciones de trabajo en [[CLAUDE]]. Las
decisiones de diseño en [[docs/decisiones]].

> Estado general (S48): v0.15.0 · 7 pestañas funcionales + manual de usuario ·
> suite pytest 1221. Hoja de ruta a 1.0: **modo industrial completo y validado**
> + mejoras 25–36 implementadas + cámara radiativa orientada. Resta solo i18n y
> refinamiento del análisis anual.

## En progreso

- **Corridas paramétricas (barridos) en P7** — código completo (etapas 1-11);
  resta la verificación manual e2e en Streamlit (etapa 12).

## Completado (hitos recientes)

- **Cámara radiativa orientada (S47, v0.15.0)** — la cámara gana orientación
  propia (acimut) y techo a un agua independientes del banco de colectores;
  hasta 5 caras translúcidas con transposición POA por cara y reparto de la
  radiación producto/aire (`calculos/radiacion_camara.py`). Barridos de
  pendiente/acimut de cámara. Ver `docs/bitacora/bitacora_sesion47.md`.
- **Manual de usuario estilo SAM (S48, mejora 36)** — manual autocontenido en
  pestaña paralela (`?manual=<slug>`): 22 capítulos markdown en
  `manual/capitulos/` (guía por sección, fundamentos, referencia técnica del
  seminario adaptada, apéndices), dos niveles de lectura (texto + expanders
  "En profundidad"), ecuaciones KaTeX, enlaces cruzados, esquemas SVG. Visor
  stateless (`ui/manual.py`) + TOC declarativo + parser puro con 148 tests de
  integridad. Botón "📖 Manual" en P1–P7 y sidebar.
- **Tanda de mejoras UX/física (S41–S44, mejoras 25–35)** — espesores de mercado
  (madera/policarbonato) con k efectivo por espesor; auditoría hidrodinámica
  ASHRAE (ΔP producto cross-flow, paralelos/serie); carta psicrométrica del
  proceso (P7 + reporte); techo translúcido con espesor y pérdida conductiva al
  balance; modo Ventana de producción como multidía real para CAJA/ARMARIO;
  resultados de colector día/noche sobre la ventana en P3. Detalle en
  `docs/notas/mejoras.md` (marcadas `[IMPLEMENTADO]`) y bitácoras S41–S44.
- **Modo industrial / gran escala (S40)** — `Tipologia.GRAN_ESCALA` completo con
  dos subtipos (Batch / Semicontinuo a contracorriente estilo ADITAL). Ventana de
  producción, motor de cámara en cascada, caño maestro, híbrido con calendario de
  arranque, UI completa (P1/P3/P4/P5/P6/P7) y validación de campo contra ADITAL
  (`validacion/validacion_adital.py`, 4/4 checks térmicos OK). Plan y estado por
  fase en [[docs/notas/plan_secador_industrial]].
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
