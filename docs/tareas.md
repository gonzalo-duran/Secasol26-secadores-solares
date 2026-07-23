# Tareas y estado del proyecto

Backlog y estado de avance de **Secasol 26**. El historial de cambios liberados
está en [[CHANGELOG]]. Las instrucciones de trabajo en [[CLAUDE]]. Las
decisiones de diseño en [[docs/decisiones]].

> Estado general (S57): **v1.1.0 en producción y verificada en el Space** · suite
> pytest **1525 (+1 skip)** · `origin/main`=`b047dd5` · ruff y black limpios. **Mejora
> 38 CERRADA** (fases 1a, 1b, 2, 2b, 3 y 4); la 1.1.0 (`b8a6464`) sumó los **exports
> completos por modo** (PDF/TXT/JSON en Ventana y operación anual, caño maestro,
> validación/calibración en el reporte) más tres fixes UX de la corrida real sobre la
> 1.0, con el fix de CI del deploy encima (`2b56eec`: clone shallow + skip LFS). Las
> **corridas paramétricas quedaron cerradas** al verificarse e2e en local y en HF.

## En progreso

- **Historia temporal por zona en `simular_cascada`** — deuda de la mejora 38 fase 4:
  habilitaría el overlay contra termopares fijos del túnel y una previa de N zonas en P4.

- **Modo anual: no arrancar lotes con mal pronóstico** (S57) — hoy el encadenado
  carga un lote aunque el día venga nublado; un operador miraría el cielo. Infla los
  lotes frustrados con casos que en la práctica no ocurrirían. Es el pendiente más
  importante que dejó la discusión sobre qué significa "simulación anual".

- **`PoliticaRecarga` no se persiste** (S57) — vive en los widgets de P4, así que
  sobrevive la sesión pero no un guardar/cargar del proyecto. Falta decidir dónde
  guardarla: se acaba de eliminar `OperacionAnualConfig` de `Camara` y no conviene
  volver a meter configuración de operación ahí sin pensarlo.

- **Modo anual del túnel semicontinuo** — `simular_anual` lo rechaza con
  `ANUAL_SEMICONTINUO_NO_SOPORTADO`: su operación es flujo continuo, no lotes, así que
  el encadenado no aplica. Habría que pensarlo como "producción sostenida".

- **`validacion/validacion_cruzada_yacon.py` está roto** — importa
  `calcular_tiempo_secado_estatico`, que se eliminó en S38 junto con el motor de capa
  fina. Comparaba capa fina vs termodinámico, así que la mitad de su razón de ser ya no
  existe: decidir si se borra o se reescribe como comparación B vs C (TD constante vs
  TD con forzantes sintéticas). Los otros 5 scripts de `validacion/` corren OK.
  **Ojo:** todos necesitan `PYTHONPATH=.` (`PYTHONPATH=. .venv/bin/python
  validacion/<script>.py`), lo que el docstring de varios no dice.

- **`h_w` de McAdams usa el viento a 2 m sin corregir a la altura del equipo** —
  decisión de modelo pendiente, deliberadamente fuera del fix de S57. McAdams viene
  de datos de placa plana con velocidad de corriente libre y la literatura solar la
  aplica con soltura; corregir a la altura real del colector/cámara movería *todos*
  los resultados, no solo el lazo natural.

## Completado (hitos recientes)

- **Altura de referencia del viento y rugosidad del terreno (S57)** — dos arreglos
  encadenados. (1) **Fix**: `chimenea_calc` asumía viento a 10 m pero recibía el de
  2 m del contrato `Clima.WS_ms`, subestimando la velocidad en el tope por
  `ln(2/z₀)/ln(10/z₀) ≈ 0.70` y el término motriz del extractor —que va con v²— a la
  mitad; el caudal natural con extractor sube +14 a +35 % según viento y T_chim.
  (2) **Fuente única**: la fórmula del perfil logarítmico estaba duplicada en
  `clima_medido` y `chimenea_calc` con z₀ propio cada una → extraída a
  `calculos/perfil_viento.py`, y z₀ pasó a ser propiedad del sitio en
  `Emplazamiento.z0_terreno_m` (catálogo Davenport-Wieringa, widget en P2 →
  Ubicación, igual que el albedo). Antes el mismo terreno físico podía entrar al
  modelo con dos valores distintos: la ingesta lo hardcodeaba en 0.05 mientras P6
  ofrecía un selector — hasta 23 % de error en `v` con anemómetro a 10 m sobre
  terreno rugoso.

- **Corridas paramétricas (barridos) en P7 — cerradas (S57)** — la etapa 12
  (verificación manual e2e, no auto-testeable) quedó confirmada por el usuario: los
  barridos funcionan **en local y en el Space de HF**. El código estaba completo desde
  S35 (etapas 1-11, +52 tests, CHANGELOG 0.8.0); era el pendiente más viejo del backlog.

- **Limpieza de ruff (S57)** — de 47 errores a 0. 30 con `--fix` (`I001`, `F401`,
  `F541`) y 17 a mano: los `E402` eran imports colocados bajo un banner de sección (no
  hacks de `sys.path`), así que se subieron al tope; los `F841` eran restos de refactor
  —incluido el andamio de una UI de `consumo_biomasa_kg_h`/`corriente_maxima_A` en P5
  que nunca se construyó—. Ningún cambio de comportamiento.

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
