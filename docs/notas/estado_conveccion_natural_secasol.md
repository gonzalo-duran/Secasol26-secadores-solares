# Convección natural en Secasol — estado actual, huecos y plan

**Fecha:** S61 (2026-07-26). **Documento de referencia + resguardo de contexto.**

Consolida **todo lo charlado** sobre convección natural en las distintas secciones de
Secasol: qué hay hoy (con evidencia `archivo:línea`), qué falta, las decisiones de diseño ya
tomadas, y el estado de la conversación para poder continuar aunque se pierda el contexto del
chat.

Documentos hermanos:
- `docs/notas/spec_conveccion_natural_y_respaldo.md` — spec del motor de flotabilidad
  unificado + auxiliar en respaldo (diseño detallado).
- `docs/mapa_auxiliar.md` — mapa del sistema auxiliar (física + interrelaciones).
- `docs/notas/balance de calor y masa en camara ampliado.md` — balance físico base (§7
  circuito de aire).

---

## 1. Las DOS acepciones de "convección natural" (no confundirlas)

Todo lo que sigue depende de separar dos cosas distintas que se llaman igual:

- **(A) Motor de caudal** — *qué mueve el aire* a través del secador cuando no hay
  ventilador. Es la flotabilidad (efecto chimenea / stack effect) que fija `ṁ`.
- **(B) Coeficiente `h_conv` interno** — *la transferencia de calor* entre el aire y el
  producto / las paredes **dentro** de cada sección. Puede ser forzada, natural o mixta.

Una sección puede tener resuelto (A) y no (B), o viceversa. El error clásico es decir "no
hay convección natural" sin aclarar cuál de las dos.

---

## 2. Inventario por sección (qué hay HOY)

| Sección | (A) Motor de caudal | (B) `h_conv` interno | Propiedades del aire |
|---------|--------------------|--------------------|--------------------|
| **Colector (tipos 1–4)** | recibe `ṁ` del lazo (con chimenea → natural; con motor → forzado) | **natural + mixta local** (Churchill), nodo a nodo | **variables** `propiedades_aire(T_f(x), P)` |
| **Chimenea** | **ES el motor de tiro natural** (`ΔP_tiro`, equilibrio brentq) | ducto: Re forzado | **ρ, μ variables** (`densidad_aire`, `viscosidad_aire`) |
| **Cámara de secado** | **con chimenea → natural; SIN chimenea → CONSTANTE** | **forzado, placa plana** (Pohlhausen/McAdams) | **μ, Pr, k CONSTANTES**; solo ρ variable |
| **Caño maestro** (industrial) | forzado (banco + ventilador) | `h_int` + `h_w` McAdams | variables |
| **Auxiliar** | — (aporta ΔT en serie, o `Q_aux` en respaldo) | — | **cp = 1007 CONSTANTE** |

### Evidencia

**Colector** — `colector_calc.py:365 coef_conveccion_interna_local`, usa
`propiedades_aire(T_film, P)` (`:400`) y `nusselt_mixto_local` (`:415`, Churchill flotación
asistida). Los tipos 2/3/4 lo reusan (`colector_tipos234_calc.py:78,644`). **Desde S36.**

**Chimenea** — es el **driver** de la convección natural del sistema:
- `chimenea_calc.py:119 delta_P_tiro_Pa` = `g·H_eff·(ρ_amb − ρ_chim)`, con
  **`H_eff = altura_chimenea + altura útil de la cámara`**.
- `:199 delta_P_chimenea_Pa` — resistencia del ducto (Re forzado, `ρ`/`μ` variables a
  `T_chim`: `:244-248`).
- `:271 caudal_natural_kgs` — equilibrio `ΔP_tiro = ΔP_resist` por `brentq`.

**Cámara** — el hueco:
- `camara_calc.py:69 _h_conv_camara_placa_plana` → **placa plana FORZADA**:
  `Re<5e5: Nu=0.664·Re^0.5·Pr^(1/3)` (Pohlhausen); `Re>5e5: Nu=0.037·Re^0.8·Pr^(1/3)`
  (McAdams). `Re = ρ·v·L/μ`, `v = ṁ/(ρ·ancho·alto)`.
- Constantes: `_MU_AIRE_PA_S=1.96e-5`, `_K_AIRE_W_MK=0.028`, `_PR_AIRE=0.71`
  (`camara_calc.py:60-62`). **Solo `ρ` es variable** (`:81 densidad_aire_humedo`).
- **`camara_termodinamica.py` NO importa nada de convección natural.** Las correlaciones
  existen (`correlaciones_nusselt.py:869 nusselt_natural_canal` Churchill-Chu, `:888
  nusselt_mixto_local`) pero **las usa SOLO el colector.**

**Auxiliar** — `auxiliar_calc.py:31 CP_AIRE=1007` constante. Calentamiento sensible
`ΔT = Q_eff/(ṁ·cp)`.

---

## 3. Los huecos (confirmados con evidencia)

### Hueco 1 — Motor de caudal sin chimenea — ✅ CERRADO (S61, ver §10)
`balance_global.py:1604`: `chimenea_activa = motor is None **and chimenea is not None**`.
`:1672 if not chimenea_activa:` → usa el **caudal de diseño constante**
(`camara.flujo.caudal_masico_kg_s`, `:1603`).

- **CAJA desnuda** (sin chimenea ni motor): caudal constante. **Mal** — un secador pasivo
  mueve el aire por flotabilidad, que varía con el estado térmico. **Caso de mucha
  aplicación.**
- **ARMARIO desnudo** (sin chimenea ni motor): **mismo hueco**.
- Con chimenea → natural (bien). Con motor → forzado (bien).

### Hueco 2 — `h_conv` de cámara: forzado y con propiedades constantes — ✅ CERRADO (S61)
- Era placa plana **forzada**: a bajo caudal (convección natural) `Re → 0` ⇒ `h_conv → 0`.
  Pero la convección natural pone un **piso** (vía Rayleigh) que el modelo **ignoraba** →
  **subestimaba `h_conv` justo en el régimen que nos importa.**
- `μ, Pr, k` **constantes** — la cámara había quedado atrás del colector (que usa
  `propiedades_aire`). **Requerimiento del usuario:** todas las propiedades (ρ, cp, β, ν, μ,
  k…) a la temperatura del nodo correspondiente.
- **Implementado (S61):** ver §9. Dos coeficientes mixtos con propiedades variables (producto
  = placa horizontal; pared = placa vertical con piso 0.68). A ≳0.5 m/s el resultado queda
  dentro del ~4 % del modelo viejo; a caudal casi nulo ya no colapsa.

### Hueco 3 (menor) — cp constante en el auxiliar
`CP_AIRE=1007`. Aceptable para un ΔT chico, pero anotado para coherencia.

---

## 4. Decisiones de diseño ya tomadas (S61)

Cerradas con el usuario (ver `spec_conveccion_natural_y_respaldo.md` para el detalle):

1. **Un solo motor de flotabilidad** para CAJA y chimenea. La chimenea = columna alta con
   ducto; el cajón/armario = columna corta con **bocas**. `H_eff = altura cámara [+ chimenea]`;
   resistencia = `bocas [+ ducto] [+ Ergun del lecho]`; equilibrio por `brentq`.
2. **Bocas**: el usuario carga **área de entrada `A_in`** y **área de salida `A_out`**. El
   coeficiente de pérdida `K` es **interno** (default `K_in=0.5`, `K_out=1.0`;
   `ΔP_bocas = K·½ρv²`, `v=ṁ/(ρA)`).
3. **Empuje** = `T_flujo − T_amb`, con `T_flujo` = T del aire **en el interior** de la cámara
   (CSTR de un nodo).
4. **RESPALDO_INDEPENDIENTE**: solo CAJA/ARMARIO; fuerza `RESISTENCIA_ELECTRICA` (quemador
   anulado); `Q_aux` al **nodo de aire** de la cámara (no precalienta `T_ent`); set-point
   sobre `T_flujo` modulando `Q_aux` (`Q_aux = clamp(T_set·den − num_base, 0, Q_max)`); en
   convección natural **`Q_aux` refuerza el tiro** (más `T_flujo` → más `ṁ`).
5. **Convergencia**: Picard **amortiguado** (sub-relajación `α≈0.5`, ~12 iter). El lazo
   `ṁ ↔ T_flujo` puede oscilar en 2-ciclo (lo vimos con aux fuerte + techo translúcido).
6. **ADITAL fuera** del alcance (es industrial forzado).

### Scope EXPANDIDO (S61, a partir de la verificación del §2–3)

7. **`h_conv` de cámara con convección natural/mixta** — reusar `nusselt_natural_canal` +
   `nusselt_mixto_local` (como el colector), para que a bajo caudal el coeficiente no
   colapse. **Prerrequisito** del motor de convección natural del cajón (sin esto, daría un
   `h_conv` irrealmente bajo).
8. **Propiedades del aire variables con T en la cámara** (`propiedades_aire`), reemplazando
   `μ/Pr/k` constantes.

---

## 5. Fundamento bibliográfico — Incropera & DeWitt, Cap. 9 "Free Convection"

**Fuente:** `docs/notas/papers/Incropera-Cap9.pdf` (7ª ed., 38 pp., leído completo S61). Es el
**sustento físico** del motor de convección natural para colector y cámara. Todo el capítulo se
apoya en la tríada **Gr → Ra = Gr·Pr → Nu = f(Ra, Pr)** y en la **solución de similaridad de
Ostrach** de las ecuaciones de momento+energía acopladas.

### 5.1 La base (§9.2–9.5)

- Ecuación de momento con flotación de **Boussinesq**: `u·∂u/∂x + v·∂u/∂y = gβ(T−T∞) + ν·∂²u/∂y²`
  (Ec. 9.5). Momento y energía quedan **acoplados** por el empuje (no se resuelven por separado
  como en forzada).
- **Gas ideal ⇒ β = 1/T** (Ec. 9.9). El colector ya lo usa (`beta_exp=1/T_film`,
  `colector_calc.py:410`); **la cámara no** (μ/Pr/k congelados, `camara_calc.py:60-62`).
- **Grashof** `Gr_L = gβ(Ts−T∞)L³/ν²` (Ec. 9.12) — hace el papel de `Re²`. **Rayleigh**
  `Ra_L = Gr·Pr` (Ec. 9.25).
- **Solución de Ostrach** (§9.4, Ecs. 9.13–9.22): similaridad `η=(y/x)(Gr_x/4)^{1/4}` → 2 EDOs
  (9.17–9.18). Da **a la vez**:
  - **campo de velocidad** `u=(2ν/x)Gr_x^{1/2}·f'(η)` (Fig. 9.4a; `f'_max≈0.28` para aire) →
    **escala de velocidad del tiro natural** (0.33 m/s en placa de 0.25 m, Ej. 9.1);
  - **Nusselt** `Nu_x=(Gr_x/4)^{1/4}·g(Pr)`, con
    `g(Pr)=0.75Pr^{1/2}/(0.609+1.221Pr^{1/2}+1.238Pr)^{1/4}` (Ecs. 9.19–9.20).
- **Transición a turbulencia**: placa vertical `Ra_{x,c}=Gr·Pr≈10⁹` (Ec. 9.23).
- **Punto clave:** las correlaciones empíricas de §9.6 (Churchill-Chu, placa horizontal) **son la
  destilación ingenieril de la propia solución de Ostrach** — la Ec. 9.27 coincide con la
  analítica 9.21 para Ra moderado-alto y la extiende. El "sustento hidrodinámico de momento" y
  las correlaciones que usaremos son la **misma física**.

### 5.2 Caja de herramientas → mapeo a Secasol

| Fenómeno en Secasol | Geometría Incropera | Ec(s). | Estado en código |
|---|---|---|---|
| Colector — `h_int` del canal | canal/placa inclinada, mixta asistida | §9.7, **9.64** (n=3) | ✅ `nusselt_mixto_local` |
| Colector — cavidad doble cubierta | cavidad rectangular **inclinada** | **9.54** (Hollands) | ✅ `_U_cubierta_efectiva` |
| **Cámara — aire↔producto (bandeja horiz.)** | **placa horizontal**, `L=A_s/P` | **9.29 + 9.30/9.31 / 9.32** | ❌ hoy placa plana **forzada** |
| Cámara — aire↔paredes verticales | placa vertical | **9.26/9.27** (piso `Nu→0.68`) | ⚠️ hoy embebido en `UA` (fijo) |
| Cámara — entre bandejas apiladas | canal vertical (Elenbaas) | 9.36/9.45 | ❌ no modelado |
| Motor de caudal (cajón/chimenea) | stack + BL de momento (Ostrach) | β=1/T, `u~(ν/L)Gr^{1/2}` | parcial (solo chimenea) |
| **Empuje por humedad** (secado) | Gr con Δρ de concentración | **9.65/9.66** | ❌ no modelado |
| Régimen mixto (criterio) | `Gr/Re²≈1` | §9.9 | ⚠️ implícito |

### 5.3 Hallazgo clave para la cámara — placa horizontal (§9.6.2), con respaldo textual

El capítulo **confirma con ecuaciones exactas** lo discutido sobre la estratificación:

- **Longitud característica de placa horizontal: `L = A_s/P`** (Ec. 9.29) — responde la pregunta
  abierta que tenía la vieja §5.
- **La correlación depende del signo de ΔT y de la orientación de la cara** (pp. 609–610, Fig. 9.7):
  - **Caliente-arriba / fría-abajo** (inestable, **fuerte**): `Nu=0.54Ra^{1/4}` (9.30, `10⁴–10⁷`);
    `Nu=0.15Ra^{1/3}` (9.31, `10⁷–10¹¹`).
  - **Caliente-abajo / fría-arriba** (estable, **débil**): `Nu=0.52Ra^{1/5}` (9.32, `10⁴–10⁹`).
- **En secado el aire está más caliente que el producto** (enfriado por evaporación) ⇒ el producto
  es "superficie fría **mirando arriba**" ⇒ **rama débil, Ec. 9.32**. En el transitorio temprano /
  bandeja calentada por sol desde abajo (producto más caliente) se invierte a 9.30/9.31. **Se elige
  nodo a nodo por el signo de `T_flujo − T_prod`.**
- **El piso que hoy falta:** con Ra finito el Nu de placa horizontal **nunca es cero**, y el de
  placa vertical tiene **piso conductivo `Nu→0.68`** (Ec. 9.27). Hoy el modelo forzado da
  `Re→0 ⇒ h→0`. La natural pone el piso.

### 5.4 Dos matices nuevos (no estaban en el radar)

- **Convección mixta TRANSVERSAL (§9.9, Ec. 9.64).** En la cámara el flujo forzado es horizontal y
  la flotación vertical → **perpendiculares** (no asistidas). Incropera recomienda **n=7/2** para
  transversal con placa horizontal (vs. **n=3** asistido del colector):
  `Nu = (Nu_F^{7/2} + Nu_N^{7/2})^{2/7}`. La combinación mixta de la cámara **no** es la del colector.
- **Empuje por concentración (§9.10, Ec. 9.65).** El aire junto al producto húmedo está más cargado
  de vapor, y el vapor (18 g/mol) es más liviano que el aire (29) → ese aire es menos denso →
  **flota**. En secado la flotación por humedad **se suma** a la térmica; con `Le≈1` la analogía
  calor-masa es limpia (Ec. 9.66). Refinamiento de 2° orden pero propio de un secadero.

### 5.5 Arquitectura propuesta (reusar los módulos puros existentes)

- `propiedades_aire.py`: agregar `beta_aire(T)=1/T`.
- `correlaciones_nusselt.py`: agregar `nusselt_placa_horizontal(Ra, Pr, cara, signo_dT)`
  (9.30/9.31/9.32) y `nusselt_placa_vertical(Ra, Pr)` (Churchill-Chu 9.26/9.27); generalizar el
  combinador mixto a `nusselt_mixto(Nu_F, Nu_N, n)` (9.64) reusable por colector (n=3) y cámara
  (n=7/2).
- `camara_calc.py`: reemplazar `_h_conv_camara_placa_plana` (constante) por
  `coef_conveccion_camara_local` análogo al del colector — `propiedades_aire(T_film)` + `Ra` con
  `L=A/P` + rama por signo de ΔT + mixta transversal. El closure `_coef_transporte` (`:268`) ya
  está enchufado al solver por paso (S39) ⇒ integración limpia, **sin romper la linealidad** del
  sistema algebraico.

---

## 6. Decisiones CERRADAS (S61, tras documentar §5)

Las preguntas abiertas del motor convectivo interno de la cámara (longitud característica, mixta
vs. separar producto/paredes, reusar helper) **quedaron respondidas por §5** (placa horizontal
`L=A/P`, rama por signo de ΔT 9.30/9.31/9.32, mixta transversal n=7/2). Las 5 que faltaban las
cerró el usuario así:

1. **Cámara aire↔producto — esquema de §5.3/§5.4 tal cual.** `L = A_s/P` (9.29); rama por signo
   de `T_flujo − T_prod`: **9.32** (`Nu=0.52·Ra^{1/5}`, débil) cuando el aire está más caliente
   —caso normal del secado— y **9.30/9.31** (`0.54·Ra^{1/4}` / `0.15·Ra^{1/3}`) cuando el producto
   está más caliente; combinación mixta **transversal n = 7/2** (Ec. 9.64).
2. **Aire↔paredes/techo — SEPARADO**, con placa vertical Churchill-Chu (9.26/9.27) y su piso
   conductivo `Nu→0.68`. Hoy el film interior de `U_total` comparte el `h_conv` del producto
   (`camara_termodinamica.py:294, 314, 349`), así que a bajo caudal `h→0` hacía `UA→0` y la
   cámara aparecía perfectamente aislada. El motor recibe un coeficiente de pared propio con
   default = `h_conv` (back-compat de tests y de llamadas históricas).
3. **Empuje por humedad (9.65/9.66) — NO en esta tanda.** `Ra` solo térmico en v1; queda anotado
   como refinamiento de 2° orden (evita acoplar ω al Picard `ṁ↔T_flujo` antes de validar el lazo
   térmico).
4. **Motor de caudal — stack effect** (chimenea generalizada a bocas, balance de ΔP con `brentq`,
   como ya fijaba la decisión §4.1); la velocidad de Ostrach queda como **cota de validación**, no
   como driver.
5. **Orden — `h_conv` interno de la cámara PRIMERO** (es prerrequisito: sin él el motor de caudal
   del cajón correría con un `h_conv` irrealmente bajo). El motor de caudal va después.

---

## 7. Estado del working tree y de la conversación (resguardo de contexto)

**Base:** `origin/main = b3fe91f` (S58). El working tree tiene el trabajo de **S59 sin
commitear** (ADR-006 `h_w`; `PoliticaRecarga` en `Configuracion`) que el usuario venía
probando.

**Cambios de código de esta tanda (S60–S61) que SOBREVIVEN en el working tree:**
- **`ui/p5_auxiliar.py` + `ui/idiomas/{es,en,pt}/p5.yaml`**: reemplazo del what-if escalar por
  la **gráfica transitoria `T_sal_aux(t)`** (entregable de P5). Reusa
  `calcular_auxiliar_transitorio` (cero física nueva). **Probado por el usuario, funciona.**
- **Motor convectivo interno de la cámara (S61)** — ver §9. Sin cambios de UI.
- **Motor de caudal del cajón desnudo (S61)** — ver §10. Con widgets en P4 e i18n ×3.
- **Bocas en el circuito forzado + `K` por topología (S61)** — §10.1 y §10.2, con P6.
- **Controles de P4 que mentían en un cajón pasivo (S61)** — §10.3: borde derivado del
  ambiente, fix del fallback de 25 °C, y §10.5 caudal en renovaciones de aire.

Suite **1800 passed + 1 skip** (eran 1715+1 al empezar la tanda; +85 tests nuevos).
**Todo probado por el usuario en Streamlit.**

**Cambios de código que se REVIRTIERON** (volvieron a la base S59, suite 1715+1):
- Todo lo demás de S60: fix Picard (sub-relajación), preservación de `Q_rad_aire` en el
  transitorio, relajar el bloqueo del aux en CAJA, reruteo de la previa de P4 por chimenea,
  labels del psicrométrico, cercanía de X_obj en P7. **Se revirtió TODO a pedido del usuario**
  tras detectar que el "fix" de `Q_rad_aire` metía radiación directo al aire (física
  incorrecta: la radiación va al **producto**, que calienta el aire por convección — ver
  `cubiertas translucidas…md`).

**Documentos creados (docs, no se deployan):**
- `docs/mapa_auxiliar.md`, `docs/notas/spec_conveccion_natural_y_respaldo.md`, y este.
- `docs/bitacora/bitacora_sesion61.md` (resumen de la sesión), **ADR-007** en
  `docs/decisiones.md`, filas nuevas en `docs/mapa_conexiones.md`, backlog en
  `docs/tareas.md`.

**Corrida de referencia del usuario:** `tests/tests cajon conveccion natural/` (`.json` de
prediseño completo + PDF). Es el caso con el que se midió todo lo de §10.4 y §10.5.

**Nada commiteado** (convención: commitea el usuario).

### Por dónde retomar

1. **RESPALDO** — etapa 2 del spec. Diseño ya cerrado (§4.4 de este doc); ahora que existe el
   motor de caudal, en convección natural `Q_aux` **refuerza el tiro**.
2. **Acoples de sección desigual** (§10.2, limitación anotada).
3. **Ventana y anual ignoran el lazo natural** — `armar_forzantes_ventana` usa el caudal de
   diseño (`simulacion_anual.py:465`); desde S61 es visible desde la UI. Decidir si se ocultan
   los controles en esos modos o se mete el Picard.
4. **Validación con datos medidos** de cámara y cajón pasivo.

**Discusión abierta que quedó sin cerrar:** si la previa de P4 debería resolver el lazo
natural completo (P4 y P7 coincidirían por construcción) o seguir siendo vista rápida. Con el
caudal en renovaciones de aire la brecha bajó de ~92 % a ~1 % en el caso medido, así que la
urgencia bajó, pero la pregunta sigue en pie.

---

## 8. Log de decisiones de la charla (cronológico, para reconstruir el razonamiento)

1. Bug del auxiliar: la vista previa de P5 presuponía `T_entrada=60 °C` (salida de colector)
   en CAJA, donde el aire es ambiente. → Se rediseñó el entregable de P5 como
   **`T_sal_aux(t)` transitoria** (implementado, probado).
2. Se pidió mapear el auxiliar → `docs/mapa_auxiliar.md`. Ahí se detectó que
   **`RESPALDO_INDEPENDIENTE` no tiene física propia** (aplica ΔT como serie).
3. Pregunta: ¿dónde entra la potencia Joule? → Se aclaró: `Q_eff → ΔT_aux → se suma a `T_ent`
   antes de la cámara → entra al balance de cámara vía la entalpía del aire entrante (no como
   término interno).
4. Diseño de RESPALDO: **resistencia dentro de cámara**, `Q_aux` al aire, solo CAJA/ARMARIO,
   fuerza resistencia eléctrica, set-point sobre `T_flujo`, convive con colector (pero el aux
   "se muda" adentro, no en cascada).
5. Motor de caudal: se descubrió que **el cajón desnudo no tiene convección natural**
   (constante). Decisión: **motor de flotabilidad unificado** caja+chimenea; bocas `A_in/A_out`;
   Picard amortiguado B1; empuje `T_flujo − T_amb`.
6. Se explicó `K` (coef. de pérdida de boca) → default interno, el usuario solo carga áreas.
7. Se escribió el **spec** (`spec_conveccion_natural_y_respaldo.md`).
8. Comentario del usuario: **todas las propiedades del aire deben ser función de la T del
   nodo**. Y pregunta: ¿de verdad no hay convección natural en la cámara del armario?
9. Verificación (§2–3): el `h_conv` de cámara es **forzado placa plana con μ/Pr/k
   constantes**; las correlaciones natural/mixta existen pero **las usa solo el colector**. →
   Scope expandido (ítems 7–8).
10. Se discutió cómo resolver el motor convectivo interno de la cámara (natural/mixta +
    propiedades variables). El usuario redirigió a **fundamentar la física en Incropera Cap. 9**.
11. Se leyó completo `docs/notas/papers/Incropera-Cap9.pdf` y se documentó el mapeo
    correlación→sección en §5: placa horizontal `L=A/P` con rama por signo de ΔT
    (9.30/9.31/9.32) para aire↔producto; Churchill-Chu (9.26/9.27) para paredes; mixta
    transversal n=7/2 (9.64); empuje por humedad (9.65/9.66); Ostrach como base hidrodinámica.
    Confirmó con cita la rama **débil** (9.32) durante el secado (aire > producto).
12. El usuario cerró las **5 decisiones** de §6 (rama por signo de ΔT + `L=A/P` + mixta n=7/2;
    pared **separada** con placa vertical; empuje por humedad **fuera** de v1; motor de caudal
    por **stack effect**; y **`h_conv` interno primero**).
13. Se implementó el `h_conv` interno de la cámara (§9). Probado en Streamlit por el usuario.
14. Se implementó el **motor de caudal del cajón desnudo** (§10), etapa 1 del spec.
    **Próximo: RESPALDO** (`Q_aux` al nodo de aire + set-point + coacción a resistencia
    eléctrica), etapa 2 del spec.

---

## 9. Implementación del `h_conv` interno de la cámara (S61)

Cierra el **Hueco 2**. Cero cambios de UI y cero cambios de contrato hacia afuera: los
llamadores que no pasan el film de pared conservan el comportamiento histórico.

**Módulos puros nuevos / extendidos**

| Archivo | Qué se agregó |
|---|---|
| `calculos/propiedades_aire.py` | `beta_aire(T) = 1/T` (Ec. 9.9) + clave `beta` en el dict agregado. |
| `calculos/correlaciones_nusselt.py` | `nusselt_placa_horizontal(Ra, inestable)` (9.30/9.31/9.32), `nusselt_placa_vertical(Ra, Pr)` (Churchill-Chu 9.26/9.27), `nusselt_mixto(Nu_F, Nu_N, n)` genérico (9.64) + constantes `N_MIXTO_ASISTIDA=3` / `N_MIXTO_TRANSVERSAL=3.5`. `nusselt_mixto_local` quedó reescrito sobre el combinador. |
| `calculos/camara_calc.py` | `_rayleigh`, `_L_caracteristica_bandeja`, `coef_conveccion_producto_local`, `coef_conveccion_pared_local`; `_h_conv_camara_placa_plana` pasó a propiedades variables; el wire-up arma **dos** closures (`coef_transporte_func` y `coef_pared_func`). |
| `calculos/camara_termodinamica.py` | `resolver_estado_camara(..., h_conv_pared_W_m2K=None)` — gobierna `U_total`, `U_techo` y la reconstrucción de `T_cam_int`; `simular_secado`/`simular_cascada` aceptan `coef_pared_func`. |

**Decisiones de implementación que no estaban en el spec**

- **Continuidad por envolvente, no por corte.** Las ramas 9.30↔9.31 se combinan con `max`
  (se cruzan en `Ra ≈ 2·10⁷`); igual 9.27↔9.26 (cruce cerca de `Ra = 10⁹`). Cortar en el
  límite tabulado metía saltos del 6 % y del 33 % que el solver ve como discontinuidad.
- **La combinación mixta se aplica sobre los `h`, no sobre los `Nu`.** Cada componente usa su
  propia longitud característica (largo de flujo para la forzada, `A/P` o altura para la
  natural), así que combinar Nusselt sería dimensionalmente inconsistente; sobre los
  coeficientes es la misma media potencial de 9.64.
- **Longitud de bandeja.** El core guarda el *área* de bandeja pero no sus lados: se supone un
  rectángulo con la relación de aspecto de la planta de la cámara (`_L_caracteristica_bandeja`).
  Bandeja cuadrada ⇒ `L = s/4`, como corresponde.
- **ΔT de la pared.** El empuje en la pared lo gobierna el salto en la **película interior**,
  no `T_flujo − T_amb`. Como depende del propio `h`, se resuelve con **dos pasadas** de punto
  fijo repartiendo `ΔT` entre `R_int`, `R_cond` y `R_ext` (basta: `Nu ~ Ra^{1/4}`).
- **Exponente de la pared:** `n = 3`, no 7/2 — sobre una pared vertical el empuje corre a lo
  largo de la superficie; el 7/2 de Incropera es para flujo transversal con placa *horizontal*.

**Efecto medido** (cámara 1.2×0.8×1.0 m, 5 bandejas de 0.5 m², tomate 10 kg)

| v [m/s] | `h` viejo (forzado) | `h` nuevo (mixto) | ratio |
|---|---|---|---|
| 1.00 | 3.56 | 3.60 | 1.01 |
| 0.50 | 2.52 | 2.62 | 1.04 |
| 0.25 | 1.78 | 2.00 | 1.13 |
| 0.10 | 1.13 | 1.62 | 1.44 |
| 0.05 | 0.80 | 1.52 | 1.91 |
| 0.00 | **0.00** | **1.47** | ∞ |

End-to-end (`calcular_camara`, 24 h): agua evaporada **+60 %** a `ṁ = 0.05 kg/s`, **+165 %** a
`ṁ = 0.01 kg/s`. En régimen forzado (≳0.5 m/s) el diseño no se mueve; el cambio pesa donde
tenía que pesar. **Falta contrastarlo contra datos medidos de cámara** (mejora 38 fase 4).

---

## 10. Implementación del motor de caudal del cajón (S61)

Cierra el **Hueco 1**. Un secador pasivo sin chimenea ya no corre con el caudal de diseño
constante: lo resuelve el equilibrio entre el tiro de la columna de aire de la cámara y la
resistencia de sus bocas.

| Archivo | Qué se agregó |
|---|---|
| `core/camara.py` | `ConfiguracionFlujo.area_entrada_aire_m2` / `area_salida_aire_m2` (+ validación `FLUJO_AREA_*_NO_POSITIVA`) y la propiedad `bocas_definidas`. |
| `calculos/chimenea_calc.py` | `delta_P_bocas_Pa` (K_in=0.5 / K_out=1.0 internos); `caudal_natural_kgs` generalizada — con `diametro_chim_m = altura_chim_m = 0` la columna es la cámara y la resistencia son las bocas; guarda `CHIM_LAZO_SIN_RESISTENCIA`; `NAT_VEL_BOCA_ALTA`. |
| `calculos/camara_calc.py` | `estimar_T_flujo_estacionario` — resuelve el CSTR una vez (`brentq` sobre el balance del producto) para dar el `T_flujo` que empuja el tiro. |
| `calculos/balance_global.py` | `conveccion_natural_activa` (reemplaza `chimenea_activa`), `_areas_bocas`, propagación a los dos pipelines, `ALFA_SUBRELAJACION = 0.5`, topes 10 → 14 (Constantes) y 5 → 12 (transitorio). |
| `calculos/chimenea_calc.py` (§10.2) | `coeficientes_bocas(hay_colector, hay_chimenea)` — los `K` salen de la topología; descuento del término de entrada en `K_singular_chim` para no contar dos veces la descarga. |
| `ui/p4_camara.py` + `p4.yaml` ×3 | Bloque "Bocas de aire" dentro de Flujo (con **o sin** ventilador), con serialización TXT/JSON — sin eso el dato se perdía al guardar, como pasó con la política de recarga en S59. |
| `ui/p6_motor.py` + `p6.yaml` ×3 (§10.1) | `_delta_P_bocas_forzado` — ΔP de bocas en el circuito forzado, apagando los `K` genéricos de entrada/salida/difusor que estimaban lo mismo sobre la velocidad del ducto. |

**Lo que decide el resultado**

- El tiro de un cajón es **débil**: con `H = 1 m` y `ΔT = 20 K` da ~0.75 Pa, contra las decenas
  de Pa de una chimenea de 3 m. Por eso el caudal sale chico y **muy sensible al área de las
  bocas**, que es la única resistencia del lazo.
- `ṁ ∝ √ΔT` (tiro lineal en ΔT, resistencia cuadrática en ṁ) — verificado en los tests.
- El lazo es **estable** en el cajón: más caudal ⇒ el mismo calor se reparte en más masa ⇒
  menos `T_flujo` ⇒ menos tiro. Realimentación negativa. Por eso converge, y por eso la
  sub-relajación es una red de seguridad más que una necesidad en este caso.

**Medido** (cajón 1.2 × 0.8 × 1.0 m, techo alveolar, tomate 10 kg, `I_g = 800 W/m²`,
`T_amb = 20 °C`, caudal de diseño cargado 0.05 kg/s):

| Bocas | ṁ resuelto [kg/s] | v salida [m/s] | Agua evaporada [kg] |
|---|---|---|---|
| sin definir | 0.0500 (dato) | — | 2.44 |
| 0.02 m² | 0.0073 | 0.35 | 1.89 |
| 0.05 m² | 0.0137 | 0.26 | 2.13 |
| 0.20 m² | 0.0314 | 0.15 | 2.34 |

O sea: **el caudal de diseño típico sobrestima lo que un cajón pasivo realmente mueve**, y con
él la producción. Es el sesgo que este motor corrige.

En el transitorio de 2 días con clima sintético el caudal respira con el estado térmico
(0.012–0.024 kg/s) y **no se apaga de noche**: el producto entrega el calor que acumuló, y esa
inercia sostiene el tiro cuando el ambiente ya se enfrió.

**Sin validar contra datos medidos.** No hay dataset de cajón pasivo en el repo; los `K` de boca
son valores de manual (contracción de canto vivo / descarga de chorro), no ajustados.

### 10.1 Las bocas valen para las dos formas de mover el aire

El usuario señaló que las bocas son dimensionamiento **también con ventilador**, y tenía razón:
ahí no cambian el caudal —lo impone el ventilador— pero fijan **la presión que tiene que
entregar** y con ella la potencia eléctrica. Peor todavía, la cadena forzada ya tenía términos de
entrada (`K = 0.5`), salida (`K = 1.0`) y difusor (`K = 0.3`) **calculados sobre la velocidad del
ducto**, o sea suponiendo una boca del tamaño del ducto: estrangular la entrada de la cámara no
movía el dimensionado del motor. Era el mismo supuesto implícito que el usuario venía arrastrando
("supuse que la boca de entrada de la cámara era igual a la salida del colector"), enterrado en un
coeficiente en vez de expuesto como dato.

Implementado: el bloque de bocas se muestra con o sin ventilador; `ui/p6_motor._delta_P_bocas_forzado`
calcula el ΔP sobre el área real y devuelve los overrides que **apagan** entrada, salida y difusor
de `estimar_delta_P_singulares` — son la misma transición estimada de otra forma, y sumarlas sería
contarla dos veces. Codos y manifold, que son del ducto, sobreviven.

### 10.2 Los `K` salen de la topología (`coeficientes_bocas`)

| Boca | Qué hay del otro lado | K | Por qué |
|---|---|---|---|
| Entrada | ambiente (caja) | 0.5 | contracción de canto vivo desde aire en reposo |
| Entrada | colector (armario) | 0.3 | el aire llega ducteado y se **expande** en la cámara |
| Salida | atmósfera | 1.0 | el chorro pierde toda su energía cinética |
| Salida | chimenea | 0.5 | contracción al ducto; la descarga real es **en el tope** |

Con chimenea, el término de entrada se **descuenta** de `K_singular_chim` (1.5 → 1.0): lo aporta
la boca sobre su área real. Verificado: con la boca de salida a la sección de la chimenea el
caudal no cambia; con una boca más angosta, baja. Y con una boca **más ancha** que la chimenea el
caudal sube un poco, que es lo correcto — una salida holgada tiene menos contracción que una del
diámetro del ducto.

**Limitación anotada a pedido del usuario:** los dos acoples —salida de colector ↔ boca de entrada
y boca de salida ↔ base de chimenea— se suponen de **igual sección**. Cuando no coinciden hay una
contracción/expansión extra que cambia la presión dinámica del aire circulante y que este modelo
**no** representa. Decisión consciente: se deja como factor a corregir a futuro (definir los
acoples es trabajo de la sesión siguiente).

---

## Ver también

- `docs/notas/papers/Incropera-Cap9.pdf` — **fundamento físico** (Free Convection, 7ª ed.; ver §5).
- `docs/notas/spec_conveccion_natural_y_respaldo.md`
- `docs/mapa_auxiliar.md`
- `docs/mapa_conexiones.md`
- `calculos/correlaciones_nusselt.py` (`nusselt_natural_canal`, `nusselt_mixto_local` — a reusar)
- `calculos/colector_calc.py::coef_conveccion_interna_local` (el patrón a replicar en cámara)
- `calculos/propiedades_aire.py` (propiedades variables a enchufar en cámara)

### 10.3 Los controles que mentían en un cajón pasivo

Probando el cajón real (5 kg de manzana, 0.5³ m, Salta, 5/7/2023) el usuario señaló que los
toggles de P4 confunden en un secador sin colector. Verificado, y era peor que confusión:

- El slider "Temperatura del aire de entrada" tenía rango **30–90 °C**, y su propio texto de
  ayuda para CAJA decía *"el aire entrante es el ambiente… configurar T ≈ T_amb representativa"*.
  El día del ensayo tenía **media 10.5 °C**: la app pedía algo que el control **prohibía**.
  Misma clase de bug que el tope de 10 m/s de velocidad que rompía gran escala — límite de
  widget sin fundamento físico.
- Peor: `_T_amb_representativa_K` leía `clima.T_amb_K`, pero `Clima` guarda las series como
  **columnas del DataFrame `datos`**. `getattr` devolvía `None` ⇒ **siempre** caía al fallback
  de 25 °C, aunque el clima estuviera cargado. 15 K de error en la condición de borde.

Cerrado así: sin colector, T y HR de entrada se **derivan del clima** y se muestran como
lectura (no hay nada que caliente el aire); con colector siguen editables. Y con convección
natural el caudal se rotula como **referencia** —lo resuelve el tiro—, con el caudal de
equilibrio para ΔT = 5 K y 15 K mostrado bajo las bocas, que es lo que permite dimensionarlas
sin salir de P4. Se dan dos puntos y no uno solo porque el ΔT real lo decide el balance de la
cámara y varía hora a hora: mostrar un número único se leería como predicción.

### 10.5 El caudal de referencia en renovaciones de aire

El usuario detectó lo que hacía inútil la previa de P4: corriendo su cajón con el caudal que
traía el toggle, P4 daba **33.3 h** de secado y P7 **63.8 h**. Una estimación rápida que
difiere ~92 % de la rigurosa no es una estimación.

La causa: el default de `ConfiguracionFlujo` (**0.030 kg/s**) está pensado para convección
forzada. En su caja (0.5 × 0.5 × 0.6 m) son **11.6 renovaciones de aire por minuto**.

**Medido con el clima real de su día** (5-7/7/2023, Salta, POA real, 3 días):

| | ṁ [kg/s] | renovaciones/min |
|---|---|---|
| Default del toggle | 0.0260 | **11.6** |
| 1 renovación/min (propuesta del usuario) | 0.0023 | 1.00 |
| **Lo que resuelve el lazo natural en P7** | **0.0021** | **0.94** |

La regla del pulgar del usuario cae a **5 %** del caudal real. Y un mini-Picard de punto de
diseño (`estimar_T_flujo_estacionario` ↔ `caudal_natural_kgs`, sin integrar el secado) da
1.14 / 1.83 / 2.13 ren/min para tres geometrías distintas: **el rango natural de un cajón
pasivo es 1–2 renovaciones/min**, lo que confirma el anclaje.

Efecto en la previa, sobre 6 días con clima real (agua evaporada, contra el lazo natural):
default **+28 %**, 1 renovación/min **+0.9 %**.

Implementado: sin ventilador **ni colector**, el widget pide renovaciones/min (default 1) y
el caudal másico sale de `ren × V_cámara × ρ(T_amb) / 60`. La densidad usa la T y la presión
**del sitio** (`_rho_aire_ambiente`): a 10 °C y 1187 m el aire pesa ~1.08 kg/m³, no 1.2. El
campo en kg/s queda como lectura para no tener dos controles del mismo número, y bajo las
bocas se muestra el equilibrio también en renovaciones. **Back-compat:** solo se reemplaza el
caudal si viene igual al default de fábrica (nunca fue una decisión); un caudal elegido a
mano se convierte y se respeta.

### 10.4 Corrida de referencia del cajón (usuario, S61)

`tests/tests cajon conveccion natural/` — caja toda translúcida (policarbonato alveolar),
0.5 × 0.5 × 0.5 m, 6 kg de manzana, bocas 0.02/0.02 m², Salta, día 5/7/2023 (media 10.5 °C,
POA 4.67 kWh/m²·día), modo DIARIO:

- **ṁ natural ≈ 0.0040 kg/s** (máx 0.0050) contra los **0.030** cargados como diseño — **7.5×
  menos aire**. Picard convergió en 7 iteraciones, 0 horas sin tiro.
- Evaporó 4.27 kg: X de 4.6 → 0.62, sin alcanzar el objetivo 0.15 en el horizonte.
- **T_prod final 3.2 °C**, por debajo de la ambiente media: enfriamiento evaporativo en un día
  de invierno.

Es el primer caso end-to-end del motor de caudal con clima real y confirma la dirección del
sesgo: **el caudal de diseño sobrestimaba fuerte lo que un cajón pasivo mueve**.
