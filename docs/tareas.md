# Tareas y estado del proyecto

Backlog y estado de avance de **Secasol 26**. El historial de cambios liberados
está en [[CHANGELOG]]. Las instrucciones de trabajo en [[CLAUDE]]. Las
decisiones de diseño en [[docs/decisiones]].

> Estado general (S52): **v1.0.0 en producción** · suite pytest **1353 (+1 skip)**.
> **Mejora 38 fase 1a implementada en working tree (sin commitear):** ingesta de
> datos climáticos medidos (CSV/XLS) en P2 con completador NASA por procedencia,
> POA medida y gating de ANUAL — validada end-to-end con el dataset real ADITAL
> 2010. **S52:** resuelto el bug colateral HR/100 del modo ANUAL (ω ambiente ~100×
> baja; altera resultados ANUAL). Pendientes de la mejora: 1b (paso sub-horario),
> 2 (validación), 3 (calibración) — plan en `docs/notas/plan_datos_medidos.md`.
> Sigue pendiente la verificación post-deploy de la 1.0.0 en el Space
> ("arreglitos" del usuario) y la prueba manual del flujo de clima medido.

## En progreso

- **Mejora 38 — toma de datos externos medidos** — fase 1a COMPLETA en working
  tree (S51): ingesta P2 + pipeline `calculos/clima_medido.py` + POA medida +
  cache + i18n ×3. Falta: prueba manual del usuario + commit/push; fases 1b/2/3.
  Hallazgos colaterales: bug HR/100 del modo ANUAL **resuelto (S52)**; queda la
  inconsistencia viento 2 m vs 10 m en chimenea. Ver
  `docs/bitacora/bitacora_sesion52.md` (y S51 para la fase 1a).

- **Corridas paramétricas (barridos) en P7** — código completo (etapas 1-11);
  resta la verificación manual e2e en Streamlit (etapa 12).

## Completado (hitos recientes)

- **🎉 Release 1.0.0 (S50)** — primera versión mayor. Cierra la hoja de ruta a
  1.0. Ver `docs/bitacora/bitacora_sesion50.md`.
- **Internacionalización ES/EN/PT completa (mejora 37, F0–F9)** — plan en
  `docs/notas/plan_i18n.md`. **F0–F8** (v0.17.0): infra + selector 🌐, toda la UI
  de las 7 pestañas + componentes, advertencias por código (F5), reporte PDF
  (F6), catálogos (F7) e infra multiidioma del manual (F8). **F9** (v1.0.0):
  los 22 capítulos del manual traducidos completos a EN y PT
  (`manual/capitulos/{en,pt}/`) + índice/navegación (`manual.toc.*` +
  `manual.parte.*` en `ui/idiomas/{en,pt}/manual.yaml`; el ES canónico vive en la
  tupla `CAPITULOS`, exento del test de paridad con paridad EN↔PT). `auditar_i18n.py`
  = 0. Ver `docs/bitacora/bitacora_sesion50.md`.
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
