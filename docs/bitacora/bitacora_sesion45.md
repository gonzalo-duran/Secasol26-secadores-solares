# Bitácora — Sesión 45 (2026-06-22)

**Tema:** Auditoría integral del proyecto de cara al **seminario del INENCO del viernes**
(presentación "en sociedad" de Secasol). Auditoría en cinco dimensiones (uso,
funcionalidades, operación, UX/UI, modelos físicos) con foco en los textos de
ayuda/onboarding para un usuario primerizo, + aplicación de los **quick-wins** de bajo
riesgo.

**Audiencia objetivo (decisión del usuario):** investigadores/técnicos del INENCO —
colegas con base física pero no expertos en el software ⇒ ayudas **técnicas pero
orientadoras**, no didácticas para legos.

**Estado al cierre:** Quick-wins P0 + P1 implementados y verificados. Suite **1042 passed**
(sin cambio de conteo — todo lo aplicado es texto/help/markdown/docstring, no lógica).
Validaciones físicas: **HWB 4/4 ✓**, **ADITAL 7/7 ✓**, **Klein discrepancia esperada y
documentada** (no es bug). Black/ruff limpios en lo tocado. Sin commitear (working tree,
sobre v0.14.0). Plan aprobado en `~/.claude/plans/silly-swimming-puppy.md`.

---

## Metodología

Exploración en paralelo con 3 agentes Explore (UX/ayudas, funcionalidad/operación, modelos
físicos) + **verificación directa en código** de los hallazgos de mayor severidad. Conclusión
transversal: **el proyecto estaba bastante más sólido de lo que reportaron las exploraciones
automáticas** — varios "riesgos" y "carencias" resultaron ya resueltos al leer el código.

### Hallazgos que resultaron falsos positivos (ya estaban resueltos)
- **Demo-safety:** "ventana sin clima", "motor TD no converge", "transitorio cae a
  constantes" — los tres **ya tienen** `st.info`/`st.warning` claros
  (`p7_resultados.py:1506`, `:1922-1934`, `:1680-1685`).
- **Checklist de configuración en P7:** ya existía como `_seccion_config()`
  (`p7_resultados.py:424`) con ✓/✗ por sección.
- **Help de geometría en P3:** 3 de 4 widgets (ancho, espaciado, velocidad) ya tenían `help=`
  adecuado; solo `largo_m` era pobre.
- **Help en P4:** `tipo_pared`, `forz_sel`, `hz_sel` ya tenían `help=` detallado; solo el
  selector de Producto era escueto.
- **Acimut en P2:** el `help` ya aclara que el óptimo en hemisferio sur es Norte (180°).
- **Advertencias de colector en P3:** el expander ya auto-expande si hay críticas
  (`expanded=bool(criticas)`).

---

## Quick-wins aplicados

### P0 (texto de ayuda / onboarding / credibilidad física)
1. **`Secasol.py`** — expander "👋 Cómo empezar" en el sidebar: flujo P1→P7, qué datos tener
   a mano (lat/lon, producto), y aclaración de que es herramienta de **prediseño** (orden de
   magnitud, no certificación).
2. **`ui/p1_tipologia.py`** — expander "¿Qué tipología elegir?" con tabla comparativa
   Caja / Armario / Gran escala (qué es, cuándo, subsistemas), **antes** del radio.
3. **`ui/p3_colector.py`** — mejora del `help` de `largo_m` (de "variable de optimización" a
   trade-off salto térmico vs ΔP) y aclaración de que `ancho_m` es por módulo unitario.
4. **`ui/p3_colector.py`** — `help` del espesor de placa: es diagnóstico, **no entra al
   balance** (capacitancia de placa despreciable; cuasi-estacionario).
5. **`ui/p4_camara.py`** — `help` enriquecido del selector de **Producto** (al elegirlo se
   cargan isoterma GAB, propiedades básicas y humedad de equilibrio).
6. **`calculos/colector_tipos234_calc.py:41`** — **fix de docstring desactualizado**: decía
   "Propiedades del aire constantes a 323 K", pero el `h_int` del canal activo **sí** usa
   propiedades locales `T_f(x)` (vía `coef_conveccion_interna_local`, `:634`). Reescrito para
   reflejar que solo quedan constantes a 323 K el aire estanco (Hollands) y los previews de
   campo/banco. Quitaba una trampa de credibilidad frente a la audiencia experta.

### P1 (pulido UX)
7. **`ui/p6_motor.py`** — caption de decisión **forzada vs natural** (cuándo conviene cada
   una: control de caudal/ΔP vs sin electricidad) al inicio de la pestaña.
8. **`ui/p7_resultados.py`** — leyenda bajo el checklist de `_seccion_config`: aclara qué es
   **obligatorio** (Cámara P4; Clima P2 en multidía/anual/ventana; Colector P3 salvo Caja) vs
   **opcional** (Auxiliar P5, Motor/Chimenea P6) — para que un ❌ en opcionales no asuste.
9. **`ui/p3_colector.py`** — resumen `st.error`/`st.warning` de una línea **antes** del
   expander de advertencias del colector, para que las críticas/warnings no pasen
   desapercibidas de un vistazo.

### Extra (credibilidad de validación)
10. **`validacion/validacion_klein.py`** — nota aclaratoria en el output: la discrepancia ~3×
    (Klein > modelo) es **ESPERADA y NO es bug**. Klein (1979) asume cavidad estanca
    absorbedor-cubierta; en un air heater de canal único el aire enfría la cubierta interna y
    reduce U_top real. La validación válida para air heaters es HWB. Referencia: §91.5 de la
    bitácora S30.

---

## Auditoría de modelos físicos — síntesis defendible

- **Referencias clásicas** en todos los motores: Duffie & Beckman (colector/HWB), ASHRAE
  (ductos/psicrometría), Mujumdar (cámara), Augustus Leon (eficiencias), Incropera
  (Chilton-Colburn), Van den Berg & Bruin (GAB).
- **Validaciones** que pasan: HWB (R²≥0.9998), ADITAL (7/7, caso real de campo — colector
  55/78 °C, caño −2.8 °C, cámara 57 °C, 5000 kg en 5 días).
- **Robustez numérica:** `solve_ivp` lanza `RuntimeError` si no converge (no silencioso);
  `fsolve` con warm-start y log de no-convergencia; `brentq` con brackets físicos.
- **Simplificaciones a tener presentes para preguntas** (todas legítimas y documentadas):
  CSTR de aire en cámara (OK para Armario; cascada por zonas para Gran escala), evaporación
  difusiva válida <5 cm de lecho (advertencia `BAND_ESPESOR_*`), GAB con fallback escalar
  (advertencia CRITICAL si falta calibración), pérdidas laterales del colector despreciadas
  (válido si L/W>3).

### Munición para Q&A del seminario
- *"¿Por qué Klein no coincide?"* → Klein asume cavidad estanca; esto es canal único, el aire
  enfría la cubierta interna. Validación correcta = HWB (R²≈1). (Ahora también en el output.)
- *"¿El espesor de placa no afecta?"* → Cuasi-estacionario, capacitancia despreciable. (Tooltip.)
- *"¿CSTR es realista?"* → Sí para Armario; Gran escala usa cascada por zonas en serie.

---

## Verificación
- **Suite: 1042 passed** (sin regresiones; conteo sin cambio).
- **HWB 4/4 ✓**, **ADITAL 7/7 ✓**, **Klein** discrepancia esperada (script ahora auto-explicado).
- **black** limpio en los 7 archivos tocados; **ruff** limpio (los 2 errores I001/F401 en
  `validacion_klein.py` son **pre-existentes** en HEAD — imports sin ordenar + `math` sin
  usar; fuera de scope, no introducidos esta sesión).
- **AppTest smoke:** entry point + P1/P3/P4/P6/P7 renderizan sin excepción.

## Pendientes (post-seminario, anotados en el plan)
- Homogeneizar propiedades de aire locales en Tipos 2/3/4 (impacto ~2-3% en Q_util).
- Refactor back-compat S38: que `_modelos_disponibles()` liste por `isoterma.gab`, no `capa_fina`.
- Validación ADITAL contra NASA POWER histórico real 2009 (hoy usa clima sintético cualitativo).
- Elevar `fsolve` no-convergente de advertencia a error si >10% de nodos fallan.
- Limpiar los 2 ruff pre-existentes de `validacion_klein.py` (trivial).
- **Mejora 36** (manual estilo SAM) e i18n (idiomas) siguen pendientes de la hoja de ruta a 1.0.
