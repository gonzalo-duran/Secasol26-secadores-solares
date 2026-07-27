# Bitácora — Sesión 61

Convección natural, de punta a punta. La sesión arrancó con cinco decisiones de diseño
abiertas y terminó con **los dos huecos cerrados** (el `h_conv` interno de la cámara y el
motor de caudal del cajón desnudo), más tres bugs que aparecieron recién cuando el usuario
probó el resultado en Streamlit con un secador real.

El resguardo de contexto vive en `docs/notas/estado_conveccion_natural_secasol.md` (§9 y §10,
con las mediciones) y en `docs/notas/spec_conveccion_natural_y_respaldo.md` (§7, qué se apartó
del plan). **Esta bitácora es el resumen; esos dos documentos son la fuente.**

---

## 1. Las cinco decisiones (§6 del doc de estado)

Cerradas por el usuario sobre el fundamento de Incropera cap. 9 documentado en la sesión
anterior:

1. **aire↔producto** — placa horizontal con `L = A_s/P`, rama según el signo de ΔT (9.32 débil
   con el aire más caliente, que es el caso del secado; 9.30/9.31 fuerte al revés), mixta
   **transversal n = 7/2**.
2. **aire↔paredes** — **separado**, placa vertical Churchill-Chu con piso `Nu → 0.68`.
3. **empuje por humedad** — fuera de v1, anotado como refinamiento.
4. **motor de caudal** — stack effect con `brentq` (Ostrach queda como cota de validación).
5. **orden** — `h_conv` interno primero, por ser prerrequisito.

---

## 2. `h_conv` interno de la cámara (hueco 2)

Era placa plana **forzada** con μ/Pr/k congelados a ~50 °C, y **el mismo coeficiente** servía
para el producto y para el film interior de la pared. A bajo caudal —el régimen de todo
secador pasivo— eso daba dos resultados falsos: `h → 0`, y con el film de pared atado a él
`U_total → 0`, o sea **la cámara parecía perfectamente aislada justo cuando más pierde**.

Ahora hay dos coeficientes, mixtos y con propiedades variables: producto por placa horizontal
(rama por signo de ΔT, `n = 7/2`) y pared por placa vertical (Churchill-Chu, `n = 3`, con el
piso conductivo que impide que `UA` se anule).

| v [m/s] | `h` viejo | `h` nuevo | ratio |
|---|---|---|---|
| 1.00 | 3.56 | 3.60 | 1.01 |
| 0.25 | 1.78 | 2.00 | 1.13 |
| 0.05 | 0.80 | 1.52 | 1.91 |
| 0.00 | **0.00** | **1.47** | ∞ |

End-to-end: agua evaporada **+60 %** a `ṁ = 0.05 kg/s` y **+165 %** a `ṁ = 0.01`. En régimen
forzado (≳0.5 m/s) los diseños no se mueven.

**Tres decisiones de implementación que el plan no anticipaba:** las ramas se combinan con
`max` (envolvente continua, en vez de cortar en el Ra tabulado y meter saltos del 6 % y 33 %);
la mixta se aplica sobre los **h** y no sobre los Nu, porque cada componente usa su propia
longitud característica; el ΔT de la película interior de pared sale de dos pasadas de punto
fijo repartiendo por resistencias.

---

## 3. Motor de caudal del cajón desnudo (hueco 1)

Un secador pasivo sin chimenea corría con el **caudal de diseño constante**. Ahora
`ConfiguracionFlujo` acepta **áreas de boca** y, con las dos definidas, el caudal lo resuelve
el mismo motor de flotabilidad que ya usaba la chimenea: `H_eff` pasa a ser la altura de la
cámara y las bocas son la resistencia.

Lo que el plan no preveía y hubo que resolver:

- **Faltaba de dónde sacar `T_flujo`.** En modo Constantes sin colector el empuje salía de una
  heurística fija `T_amb + 25 K` que **no depende de ṁ**, así que congelaba el lazo en una
  iteración con un tiro inventado. Se agregó `camara_calc.estimar_T_flujo_estacionario`, que
  resuelve el CSTR una sola vez (`brentq` sobre `q_prod + Q_rad − ṁ_w·L_v = 0`) sin integrar
  el secado. Con colector se conserva `T_sal_col − 5 K`, que es el camino validado.
- **Los topes de Picard quedaban cortos** al amortiguar (α = 0.5 duplica los pasos): 10 → 14
  en Constantes y 5 → 12 en transitorio. Medido, cada iteración cuesta ~0.1 s.
- **Guarda `CHIM_LAZO_SIN_RESISTENCIA`** para el lazo sin chimenea ni bocas ni pérdidas, donde
  el equilibrio no existe y `brentq` fallaba con un error opaco de bracket.

---

## 4. Ampliación: las bocas también dimensionan el ventilador

El usuario señaló que las bocas son dimensionamiento **también en convección forzada**. Tenía
razón, y había algo peor: `estimar_delta_P_singulares` ya traía términos de entrada, salida y
difusor, pero **calculados sobre la velocidad del ducto** — o sea suponiendo una boca del
tamaño del ducto. Estrangular la entrada de la cámara no movía el dimensionado del motor. Era
el mismo supuesto implícito que el usuario venía arrastrando ("supuse que la boca de entrada
de la cámara era igual a la salida del colector"), enterrado en un coeficiente.

Ahora el bloque se muestra con o sin ventilador y `_delta_P_bocas_forzado` calcula el ΔP sobre
el área real, **apagando** los tres términos genéricos. Y los `K` dejaron de ser fijos:

| Boca | Del otro lado | K |
|---|---|---|
| Entrada | ambiente (caja) | 0.5 |
| Entrada | colector (armario) | 0.3 |
| Salida | atmósfera | 1.0 |
| Salida | chimenea | 0.5 |

Con chimenea, el término de entrada se descuenta del bundle de singulares del ducto para no
contar dos veces la descarga: con la boca a la sección de la chimenea el caudal no cambia; con
una más angosta, baja.

**Fuera de alcance por decisión del usuario:** los acoples de **sección desigual**
(colector↔boca, boca↔chimenea) producen una contracción que altera la presión dinámica y que
el modelo no representa. Anotado como corrección futura — es el trabajo de la sesión que viene.

---

## 5. Tres bugs que solo aparecieron probando

Los tres salieron cuando el usuario corrió su cajón real (0.5 × 0.5 × 0.6 m, 6 kg de manzana,
Salta, 5/7/2023). Ninguno lo habría encontrado un test.

**a) El widget de bocas desaparecía (mío, esta sesión).** Lo até a `proyecto.camara is not
None`, y la cámara del usuario no era construible: 8 bandejas × 0.07 m = 0.56 m de pila en una
cámara de 0.50 m (`COHE_BANDEJAS_NO_CABEN_EN_CAMARA`). El bloque se ocultaba **sin decir nada,
justo cuando estaba editando** y más necesitaba verlo. Lección: los widgets no pueden colgar
de objetos del core que pueden fallar a validar. Test de regresión:
`test_bocas_se_dibujan_aunque_la_camara_no_sea_construible`.

**b) El control contradecía a su propia ayuda (pre-existente).** El slider "Temperatura del
aire de entrada" tenía rango **30–90 °C**, y su texto de ayuda para CAJA decía *"el aire
entrante es el ambiente… configurar T ≈ T_amb representativa"*. El día del ensayo tenía media
**10.5 °C**. La app pedía algo que el control prohibía — misma clase que el tope de 10 m/s de
velocidad que rompía gran escala. Ahora, sin colector, T y HR de entrada **se derivan del
clima** y se muestran como lectura; con colector siguen editables.

**c) La T ambiente representativa estaba rota (pre-existente).** `_T_amb_representativa_K`
leía `clima.T_amb_K`, pero `Clima` guarda las series como **columnas del DataFrame `datos`**.
`getattr` devolvía `None` ⇒ **siempre** caía al fallback de 25 °C aunque el clima estuviera
cargado. En el cajón salteño de julio son **15 K de error** en la condición de borde con la
que se estiman pérdidas a paredes y temperatura inicial del producto.

---

## 6. El caudal de referencia, en renovaciones de aire

El usuario cerró la sesión con la observación más filosa: corriendo su cajón, **P4 daba 33.3 h
de secado y P7 63.8 h**. Una estimación rápida que difiere ~92 % de la rigurosa no es una
estimación.

La causa: el default de `ConfiguracionFlujo` (0.030 kg/s) está pensado para convección
forzada; en su caja son **11.6 renovaciones de aire por minuto**. Propuso pedir el caudal en
renovaciones de volumen de cámara por minuto y convertirlo con ρ a la temperatura ambiente.

Medido con su clima real:

| | ṁ [kg/s] | renovaciones/min |
|---|---|---|
| Default del toggle | 0.0260 | **11.6** |
| 1 renovación/min (su propuesta) | 0.0023 | 1.00 |
| **Lo que resuelve el lazo natural** | **0.0021** | **0.94** |

Su regla del pulgar cae a **5 %** del caudal real, y el mini-Picard de punto de diseño da
1.14 / 1.83 / 2.13 ren/min en tres geometrías: **el rango de un cajón pasivo es 1–2 ren/min**.
En agua evaporada, la previa pasa de sobrestimar **+28 %** a **+0.9 %**.

Implementado sin ventilador ni colector: el widget pide renovaciones/min (default 1) y el
caudal másico sale de `ren × V × ρ(T_amb, P_sitio)/60`. La densidad usa la T y la presión del
sitio (a 10 °C y 1187 m el aire pesa 1.08 kg/m³, no 1.2). Back-compat: solo se reemplaza el
caudal si viene igual al default de fábrica; uno elegido a mano se convierte y se respeta.

---

## 7. Estado al cierre

- **Suite 1800 passed + 1 skip** (eran 1715+1 al empezar). Ruff y black limpios; paridad i18n
  ×3 en verde.
- **Nada commiteado** — el working tree sigue sobre `origin/main = b3fe91f` (S58) y arrastra
  también el trabajo de S59 sin commitear.
- Corrida de referencia del usuario guardada en `tests/tests cajon conveccion natural/`
  (`.json` + PDF).

**Pendientes que deja la sesión**, en orden:

1. **RESPALDO** (etapa 2 del spec): `Q_aux` al nodo de aire de la cámara + set-point sobre
   `T_flujo` + coacción a resistencia eléctrica, solo CAJA/ARMARIO.
2. **Acoples de sección desigual** colector↔boca y boca↔chimenea.
3. **Ventana y anual ignoran el lazo natural** — `armar_forzantes_ventana` usa el caudal de
   diseño (`simulacion_anual.py:465`). Es una limitación **previa** (la chimenea también se
   ignoraba ahí), pero ahora es visible: se pueden cargar bocas y no ver ningún efecto en el
   modo anual. Decidir si se ocultan los controles en esos modos o se mete el Picard.
4. **Validación contra datos medidos** de cámara y de cajón pasivo: nada de lo de esta sesión
   está contrastado con mediciones, y los `K` de boca son de manual.

## Ver también

- [[docs/notas/estado_conveccion_natural_secasol]] — §9 (`h_conv`), §10 (motor de caudal,
  con todas las mediciones), §10.5 (renovaciones de aire).
- [[docs/notas/spec_conveccion_natural_y_respaldo]] — §7, desvíos del plan.
- [[docs/mapa_auxiliar]] — mapa del auxiliar, con la inconsistencia que cierra el RESPALDO.
- [[docs/decisiones]] — ADR-007.
