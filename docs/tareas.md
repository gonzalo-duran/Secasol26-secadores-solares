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

### Convección natural (S61) — dos huecos cerrados, tres pendientes

Ver `docs/bitacora/bitacora_sesion61.md` y, para el detalle con mediciones,
`docs/notas/estado_conveccion_natural_secasol.md` (§9, §10) y
`spec_conveccion_natural_y_respaldo.md` (§7). **Cerrados:** el `h_conv` interno de la cámara
(mixta + propiedades variables) y el motor de caudal del cajón desnudo (bocas + equilibrio de
tiro), más las bocas en el circuito forzado y el caudal de referencia en renovaciones de aire.
Queda, en orden:

- **RESPALDO del auxiliar** (etapa 2 del spec) — `Q_aux` al nodo de aire de la cámara +
  set-point sobre `T_flujo` + coacción a `RESISTENCIA_ELECTRICA`, solo CAJA/ARMARIO. Hoy
  `RESPALDO_INDEPENDIENTE` no tiene física propia: aplica su ΔT como si fuera serie.
  **Es el próximo paso.**

- **Acoples de sección desigual** — colector↔boca de entrada y boca de salida↔base de
  chimenea se suponen de **igual sección**. Cuando no lo son hay una contracción/expansión
  que altera la presión dinámica y que el modelo no representa. Decisión consciente del
  usuario (S61), anotada como corrección futura.

- **Ventana y anual ignoran el lazo natural** — `armar_forzantes_ventana` arma las forzantes
  con el caudal de diseño (`simulacion_anual.py:465`), así que ni la chimenea ni las bocas
  gobiernan el caudal en esos modos. Es una limitación **previa**, pero desde S61 es visible
  desde la UI: se pueden cargar bocas y no ver ningún efecto en el modo anual. Decidir si se
  ocultan los controles ahí o se mete el Picard en esos pipelines.

- **Sin validar contra datos medidos** — ni el `h_conv` de cámara ni el motor de caudal están
  contrastados con mediciones; los coeficientes de pérdida de boca son de manual. Extensión
  natural de la mejora 38 fase 4.

- **Historia temporal por zona en `simular_cascada`** — deuda de la mejora 38 fase 4:
  habilitaría el overlay contra termopares fijos del túnel y una previa de N zonas en P4.

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

## Completado (hitos recientes)

- **`PoliticaRecarga` se persiste con el proyecto (S59)** — el pendiente venía de S57 y
  pesaba más desde S58, con dos campos nuevos. El bloqueo real no era "dónde guardarla"
  sino que estaba **en la capa equivocada**: definida en `calculos/simulacion_ventana.py`,
  no podía entrar a `Proyecto` sin invertir la dependencia (el modelo de datos pasaría a
  depender del motor numérico). Se movió a **`core/operacion.py`** —es una dataclass de
  datos puros con validación por códigos de error, la forma exacta de un objeto de
  `core/`— y cuelga de `Configuracion.politica_recarga`, junto a `ventana_inicio`/
  `ventana_fin`. Tres efectos: (1) viaja en el snapshot `.json`, así que reabrir un
  proyecto y recalcular ya reproduce el reporte guardado; (2) la huella de vigencia la
  toma sola, lo que permitió **eliminar** el `extras={"politica": ...}`, la clave
  `p4_politica_recarga` y dos helpers de `vigencia.py`; (3) el **modo VENTANA**, que nunca
  la leía y quedaba clavado en los defaults sin ningún widget que la gobernara, ahora la
  obedece igual que el anual. De paso se tapó el gotcha de siempre: P1 reconstruye
  `Configuracion` campo por campo en cada rerun y habría pisado la política.

- **`h_w` de McAdams: decidido no corregir a la altura del equipo (S59)** — el
  pendiente que venía de S57 quedó cerrado como **[[docs/decisiones|ADR-006]]**, sin
  cambios de código. Se midió primero la magnitud del sesgo: corrigiendo el colector
  Tipo 1 de 2 m a su altura real de montaje, Q_util sube 0.5–2 % (z = 1–1.5 m) y
  hasta 5–7 % en el caso extremo (z = 0.5 m, terreno rugoso, v = 5 m/s); en las
  envolventes, `1/h_w` es el 4 % de la resistencia total en pared aislada
  (irrelevante), 25 % en techo alveolar, 32 % en chapa sin aislar y **59 % en el caño
  maestro desnudo** — ahí un ±20 % en `h_w` mueve U un 8 %. Se decidió **no corregir**:
  McAdams no tiene altura de referencia (Jürges 1924, placa de 0.5 m en túnel con
  velocidad de corriente libre) y el scatter de esa familia de correlaciones es de
  ±30–50 % (Palyvos 2008), así que el factor de perfil cae dentro del ruido; además la
  literatura de la que salen los `F_R·U_L` de contraste la aplica con el viento de
  estación. El sesgo tiene **un solo signo** y va a favor de la seguridad: sobrestima
  las pérdidas, subestima el rendimiento. `perfil_viento.py` documenta la excepción en
  su docstring para que no se "arregle" en una sesión futura, y el ADR deja anotado el
  contra-argumento (ISO 9806 mide el viento a la altura del colector) y la vía de
  menor costo si se reabre.

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
