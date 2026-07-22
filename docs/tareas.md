# Tareas y estado del proyecto

Backlog y estado de avance de **Secasol 26**. El historial de cambios liberados
está en [[CHANGELOG]]. Las instrucciones de trabajo en [[CLAUDE]]. Las
decisiones de diseño en [[docs/decisiones]].

> Estado general (S57): **v1.1.0 en producción** · suite pytest **1525 (+1 skip)** ·
> `origin/main`=`2b56eec`; en working tree, la versión en el panel 🔧 Entorno (sin
> commitear). **Mejora 38 CERRADA** (fases 1a, 1b,
> 2, 2b, 3 y 4) y **release 1.1.0 commiteado y pusheado** (`b8a6464`), con el fix de
> CI del deploy encima (`2b56eec`: clone shallow + skip LFS, que evitaba el corte del
> clone del Space). La 1.1.0 suma los **exports completos por modo** (PDF/TXT/JSON en
> Ventana y operación anual, caño maestro, validación/calibración en el reporte) más
> tres fixes UX salidos de la corrida real del usuario sobre la 1.0.

## En progreso

- **Corridas paramétricas (barridos) en P7** — código completo (etapas 1-11);
  resta la verificación manual e2e en Streamlit (etapa 12).

- **Verificación post-deploy del Space** — confirmar que HF rebuildeó la 1.1.0 con
  el workflow corregido (`2b56eec`).

- **Limpieza de ruff** — 47 errores preexistentes en archivos no tocados (eran 14 en
  S55 con el mismo criterio; parece bump de versión de ruff en el `.venv`). Los
  archivos tocados en S56 pasan limpio.

- **Inconsistencia viento 2 m vs 10 m** — arrastrada desde la mejora 38; el clima
  medido y NASA POWER no coinciden en la altura de referencia del viento.

## Completado (hitos recientes)

- **Versión de Secasol en el panel 🔧 Entorno (S57)** — el panel del sidebar abre con
  `**Secasol** <versión>` antes de Python y las librerías, para ver de un vistazo si el
  Space corre el mismo código que el repo local (un deploy que no rebuildeó deja
  producción con código viejo y el mismo entorno de librerías). La versión sale de
  `core/version.py::__version__` — no del `CHANGELOG.md` ni de los tags, que **no se
  deployan** al Space; `tests/test_core/test_version.py` ata esa constante al último
  encabezado liberado del changelog.

- **Release 1.1.0 — exports completos por modo (S56)** — el reporte PDF y los
  snapshots TXT/JSON dejan de cubrir solo Constantes/Transitorio: se suman el modo
  **Ventana** (producción, perfil del túnel, descargas, leña, diagnóstico del **caño
  maestro**) y el panel de **operación anual** (agregados + 12 puntos mensuales), más
  la sección de **validación/calibración con datos medidos** (colector, cámara y
  túnel), que entra al PDF automáticamente si existe. Incluye tres fixes UX de la
  primera corrida real del usuario sobre la 1.0 en el Space. Ver
  `docs/bitacora/bitacora_sesion56.md`.

- **Mejora 38 — toma de datos externos medidos (S51–S55)** — lazo completo
  **ingesta → validación → calibración**. Fases 1a (clima medido en P2), 1b (motor
  agnóstico al paso), 2/2b/3 (colector: validación, forzado con el clima del propio
  ensayo y calibración 1-D; validado con el prototipo 10 m del INENCO, RMSE 0.91 °C,
  R² 0.987) y **4** (cámara y producto: cuatro señales medibles, cámara aislada
  forzada con el aire de entrada del ensayo, calibración del área efectiva —aplicable—
  y de los factores de transporte —diagnóstico—, diagnóstico de cadena completa en P4
  y validación del túnel por descargas y perfil en P7). Módulos nuevos:
  `calculos/{metricas_validacion,ingesta_referencia,calibracion,validacion_camara}.py`,
  `core/validacion.py`, `ui/componentes/validacion_widget.py`. **Deuda registrada:**
  historia temporal por zona en `simular_cascada` (habilitaría el overlay contra
  termopares fijos del túnel y una previa de N zonas en P4).

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
