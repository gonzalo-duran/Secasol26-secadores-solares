# Bitácora — Sesión 42 (2026-06-16)

**Tema:** Backlog de mejoras (`docs/notas/mejoras.md`), modo industrial. Esta sesión
cubrió **31** (orden de las subrutinas de evaluación en la pestaña de colectores) y
**32** (revisión de la compensación de sección del caño maestro — el toggle
"sección creciente").

**Estado al cierre:** Implementado y verificado. Suite **1011 passed** (+6). Black/ruff
limpios. Validación ADITAL 7/7. Sin commitear (working tree, sobre S38–S41). Verificado
con AppTest (orden de subsecciones + render de métricas del campo) y con
`validacion/validacion_adital.py`.

---

## Decisiones de diseño (acordadas con el usuario en planificación)

- **31 acotada a GRAN_ESCALA:** NO extender la evaluación de banco/campo a ARMARIO.
  Un armario de 4-6 colectores en 2-3 ramas en paralelo no justifica modelar un caño
  maestro (caída de presión, pérdidas/ganancias térmicas del manifold). El banco queda
  solo en modo industrial; solo se reordena.
- **32 — unificar la física en todos los consumidores**, incluido el dimensionado del
  ventilador en P6, no solo arreglar la pantalla de P3 (evitar dos modelos conviviendo).
- **Generalidad preservada:** ADITAL es referencia (chequeo de orden de magnitud), no
  objetivo de calibración (memoria `feedback_generalidad_no_adital`).

---

## 31 — Orden de las subrutinas de evaluación (colector → banco)

- `ui/p3_colector.py`: se invirtió el orden de las dos subsecciones dentro de `render()`.
  - Antes: "Sección 5b: Evaluación del campo de colectores" (gateada GRAN_ESCALA) →
    "Sección 6: Evaluación del desempeño del colector" (sin gate).
  - Ahora: "Sección 5b: Evaluación del desempeño del colector **unitario**" → "Sección
    5c: Evaluación del campo de colectores (banco, GRAN_ESCALA)".
- Swap limpio: bloques independientes (`p3_eval` vs `p3_campo`), ambos después de fijar
  `proyecto.colector`. Los `st.divider()` quedan coherentes; "Guardar configuración"
  sigue último. En CAJA/ARMARIO solo se ve la eval de colector unitario.

## 32 — Compensación de sección del caño maestro

**Diagnóstico (confirmado con números antes de tocar nada):**
- **Preview** `estimar_delta_P_cano_maestro`: metía el **caudal total** por toda la
  sección creciente → activar el toggle disparaba la fricción (1.17 → 8.42 Pa en el caso
  de prueba) e **invertía** la compensación; `v_troncal` no cambiaba con el toggle.
- **Eval de campo** `evaluar_campo_colectores`: ya usaba caudal acumulado (`Q_acum`,
  física correcta), pero el `dP_sistema` mezclaba rama+troncal (dominado por la rama) →
  el toggle apenas movía el número (6.18 → 6.90 Pa) y la compensación, que actúa sobre la
  **velocidad**, no se mostraba en ningún lado.

**Física correcta (flujo acumulado `Q(x)=Q_total·x/L`):**

| Caso | Fricción | Velocidad |
|------|----------|-----------|
| Constante GRANDE (A_L en todo) | 0.42 Pa | 0.01→2.0 m/s |
| Constante CHICA (A_0 en todo) | 12.44 Pa | 0.02→8.0 m/s |
| Creciente A_0→A_L | 1.06 Pa | 0.02→2.0 m/s ✅ |

La compensación es real: el caño creciente acota la velocidad a ~2 m/s con mucho menos
material que el caño grande constante, y es dramáticamente mejor que un caño chico
constante. **Sutileza:** el toggle compara OFF=constante-grande (mejor caso de ΔP) vs
ON=creciente → "activar no baja el ΔP"; lo que la compensación controla es la
**velocidad acotada con menos material**, por eso hay que mostrar el perfil de velocidad,
no solo el ΔP.

**Cambios:**
- `calculos/cano_maestro_calc.py::estimar_delta_P_cano_maestro` — modelo de flujo
  acumulado `Q(f)=Q_total·f` con sección local vía `seccion_en_fraccion` (unifica las
  ramas constante/variable en un solo loop, coincide con `_dP_troncal_tramos_Pa`).
  Retorno agrega `v_fin_ms` (extremo ventilador) y `v_max_ms` (máx del perfil);
  `v_troncal_ms` se mantiene == `v_fin_ms` por back-compat.
- `calculos/campo_colectores_calc.py` — `ResultadoCampoColectores` expone `dP_troncal_Pa`
  (ΔP del troncal completo boca 1→ventilador, aislado de la rama) y `v_troncal_perfil_ms`
  (velocidad por tramo, far→fan). Poblados solo con caño y N>1.
- `ui/p3_colector.py` — preview del caño: caption con sección inicio→fin + v acotada
  (v_max) + ΔP. Eval de campo: métricas nuevas "ΔP troncal del caño" + "v troncal
  (mín→máx)"; `_fig_campo_colectores` agrega un panel inferior con el **perfil de
  velocidad del troncal** (la demostración directa de la compensación).

**Impacto en el motor (P6) y validación:** el ΔP del caño baja (era conservador ~3×),
pero las singulares dominan → impacto acotado. `validacion_adital.py`: 7/7, ΔP caño 3.2 Pa,
ΔP total 543 Pa, ventilador 3.4 HP (vs 4 HP nameplate).

---

## Tests (+6) y verificación

- `tests/test_calculos/test_cano_maestro.py` (+3): `v_fin_ms`/`v_max_ms` en el retorno;
  caño chico constante fricciona >5× el grande; creciente acota v (== v_fin) y fricciona
  <0.5× el chico constante (ya no invierte). Docstring del test previo actualizado al
  modelo nuevo (sigue válido: creciente > constante-grande).
- `tests/test_calculos/test_campo_colectores.py` (+3): troncal+perfil expuestos con caño;
  perfil vacío y ΔP troncal nulo sin caño; ΔP troncal y v_max responden al estrechar la
  sección de inicio.
- AppTest: P3 en GRAN_ESCALA renderiza sin excepción; subheaders en orden colector→campo;
  fila de métricas del campo (ΔP troncal 1.3 Pa, v troncal 0.50→2.52 m/s) renderiza.
- `validacion/validacion_adital.py` 7/7. Suite completa **1011 passed**. Black/ruff limpios.

## Pendientes del backlog de mejoras

- **27** — Diagrama psicrométrico del proceso completo (resultados + reporte).
- **33** — Selección de idiomas (Esp/Por/Ing) con banderitas.
- **34** — Manual estilo SAM (ventana emergente, markdown con hipervínculos).
