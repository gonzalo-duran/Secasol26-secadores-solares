# Bitácora — Sesión 67

**Fecha:** 2026-11-12 · **Tema:** diagnóstico y corrección de la carta psicrométrica (la razón
del hotfix 1.4.1).

## 1. Punto de partida

El usuario pide averiguar por qué la carta da resultados raros: en un armario indirecto a
condiciones constantes y tasa de evaporación constante, el calentamiento en colectores se ve
bien pero el tramo de cámara **no se ve a entalpía constante**. Propone ensayar a condiciones
constantes para no mezclar el problema con la representación de un proceso variable, y pide
discriminar entre cuatro sospechosos: la carta, el modelo de evaporación, el balance de calor
y masa, u otra cosa.

## 2. Diagnóstico

Once corridas en modo Constantes sobre `tests/armario indirecto forzado/` (cámara opaca
0.5×0.5×1.1 m, 5 cm de lana de vidrio, 9.5 kg de manzana, 34 g/s), variando sol, HR, caudal y
temperatura ambiente; repetidas sobre el código de producción (worktree del hotfix) con el
mismo comportamiento.

### 2.1 El balance de cámara cierra

En régimen de tasa constante:

    ṁ_as·(h_sal − h_ent) = −q_pared + ṁ_w·cp_agua·T_prod

Caso base: −35.3 W = −44.2 W + 9.0 W, **residuo 0.0 W**. El producto se estabiliza en bulbo
húmedo (32.3 °C) y el calor que recibe iguala al latente (161 W contra 161 W). Con el aislante
llevado a 5 m como prueba, Δh = +0.26 kJ/kg = exactamente el término del agua líquida: el
modelo reproduce la **línea de saturación adiabática**. Ni la evaporación ni el balance tienen
el problema.

### 2.2 Tres defectos de la carta

1. **Escala.** El eje de humedad se autoescalaba a la saturación en la temperatura máxima del
   gráfico (250 g/kg a 65 °C) mientras el tramo de cámara se movía entre 25.8 y 27.7 g/kg.
   Todo el proceso quedaba como una línea horizontal. **Esto es lo que el usuario vio** como
   "no va a entalpía constante".
2. **"Ambiente" sobresaturado.** En Constantes la ω salía del slider "HR del aire de entrada"
   evaluado a la temperatura de entrada a la cámara. Con 57 °C y 20 % son 25.8 g/kg = HR 110 %
   a 25 °C; con 1000 W/m², 160 %; con el slider en 40 %, 220 %. No era solo el dibujo: esa ω es
   la que usaba el motor.
3. **Instante representativo en t = 0.** El criterio "máxima evaporación" cae en el arranque
   cuando el producto empieza más caliente que el bulbo húmedo (aire seco o colector tibio):
   ahí cede calor sensible y la salida queda **por encima** de la isentálpica en una cámara
   opaca (+2.2 kJ/kg, 63 % de la caída sensible, con 400 W/m²).

### 2.3 El apartamiento real

La cámara del armario no es adiabática **en términos relativos**: pierde 37–56 W por pared
contra 100–250 W de latente útil, y la salida cae 12–29 % de la caída sensible por debajo de la
isentálpica. Es correcto, y pesa tanto porque desde S64 el acercamiento al equilibrio es de
~21 % (el aire sale a HR 28 %).

## 3. Lo implementado

- **`calculos/balance_global.py`** — `calcular_todo(..., HR_referida_a_ambiente=False)`. Con
  el flag, `HR_camara` es la HR ambiente: fija ω a `T_amb` y la HR de entrada a la cámara se
  deriva a la temperatura real (`_HR_a_temperatura`), también en el Picard del lazo natural.
  El default conserva la semántica vieja, así que los tests y llamadores existentes no cambian.
  Campo nuevo `ResultadosCompletos.omega_entrada_kg_kg`: la ω del proceso deja de recalcularse
  en P7 y en el PDF, cada uno por su lado.
- **`calculos/carta_psicrometrica.py`** — en Constantes la ω sale del resultado; instante
  representativo por `_instante_regimen`, que descarta el arranque del producto
  (`|dT_prod/dt|` por debajo del 5 % de su valor inicial ≈ 3 constantes de tiempo). El
  transitorio conserva el criterio de S63.
- **`ui/componentes/carta_psicrometrica.py`** — eje de humedad ajustado al proceso y a la
  saturación adiabática (`_rango_omega_g_kg`); etiquetas de HR dentro del cuadro; la nota va a
  la esquina seca, informa el **Δh medido** y deja de decir "≈ adiabática".
- **P7** — slider "HR del aire ambiente", default 50 %, rango 5–100 %. Barrido rotulado
  "Humedad relativa ambiente". Exports TXT/PDF: "HR ambiente".
- i18n en los tres idiomas (`graficas.carta.delta_h` nuevo; `nota_indirecta`, `p7.condiciones.hr`
  y `reporte.global.hr_cam` reescritos).

### Física del modelo

- **Qué captura:** ω se conserva en el calentamiento sensible (colector + auxiliar); la HR baja
  con la temperatura. Es lo que ya hacían los modos Transitorio/Ventana/Anual con el clima.
- **Qué no cambia:** el motor de cámara, la evaporación, la cadena de 8 etapas. Solo cambia la
  condición de borde de humedad del modo Constantes.
- **Límite:** el descarte del arranque supone forzantes constantes (relajación monótona de
  `T_prod`); por eso no se aplicó al transitorio.

## 4. Cuánto cambia el modo Constantes

Armario de referencia, 25 °C ambiente:

| sol | slider | antes (HR a T_entrada) | ahora (HR ambiente) |
|---|---|---|---|
| 800 | 20 % | ω 25.8 g/kg (amb. 110 %), 239 g/h, no seca en 72 h | ω 4.5, 423 g/h, 22.4 h |
| 800 | 50 % | ω 68.7 (276 %), 113 g/h, no seca | ω 11.4, 310 g/h, 26.3 h |
| 1000 | 20 % | ω 38.1 (160 %), 269 g/h, 37.1 h | ω 4.5, 450 g/h, 18.7 h |
| 400 | 50 % | ω 28.4 (121 %), 89 g/h, no seca | ω 11.4, 198 g/h, no seca |

Con la semántica vieja el mismo valor del slider significaba un aire distinto según la
temperatura del colector; por eso mejorar el colector empeoraba la condición de humedad.

## 5. Verificación

- 7 tests nuevos en `tests/test_ui/test_carta_constantes.py` (proyecto real: ω del ambiente,
  ambiente no sobresaturado, modo de compatibilidad, **cierre del balance de entalpía**,
  instante fuera del arranque, escala) y 3 en `test_carta_psicrometrica.py`.
- Módulos afectados: 134 passed. Suite completa: **1988 passed + 2 skips** (12 min 11 s).
- Ruff y black limpios.

## 6. Abierto

1. **Validación del usuario en Streamlit** (P7 Constantes y PDF).
2. Transitorio, Ventana y cámaras translúcidas no se revisaron.
3. Reactivar la carta en producción es decisión del próximo release (ADR-009).
4. El cambio del slider se suma a S63/S64 como motivo de bump de versión.

## 7. Percolación parcial: plan escrito, implementación en espera

Probando la carta corregida el usuario notó que la HR y la ω de salida siguen bajas y **no
responden a la masa ni al X final**. Se verificó con 17 corridas: es el comportamiento del
modelo de S64 (el área es la de las bandejas, no la del producto; acercamiento a saturación
~19 %), el mismo síntoma que había disparado S63. Lo que sí mueve la salida es la relación
área de bandejas / caudal.

Se escribió [[docs/notas/plan_percolacion_parcial]] (el §7.2 del plan de S64): reparto del
caudal entre atravesar el lecho y rodear la bandeja, con la fracción como **resultado**. Un
prototipo de orden de magnitud da 50–86 % de acercamiento en forzado y vuelve a hacer pesar la
masa.

**Decisión del usuario: no implementarlo todavía.** Primero va a traer **ensayos propios de
secadores solares** (operación y dinámica) para calibrar contra mediciones — *"si no vamos a
estar dando vueltas en círculo"*. Es el tercer cambio de topología de la cámara en tres
sesiones sin un dato medido; el plan queda como propuesta con cuatro decisiones abiertas.

## 8. `main` local adelantado a pedido del usuario

El usuario pidió llevar `testing` a `main` **local**, sin push. Deja a `main` local por delante
de `origin/main` (que además tiene el commit del hotfix 1.4.1, ausente acá): **`main` local ya
no es espejo de producción** hasta el próximo release. Un `git push` desde `main` va a ser
rechazado por no ser fast-forward — no forzarlo; la reconciliación sigue siendo la de ADR-009
(`git merge -s ours hotfix-1.4.1` en `testing`, versión > 1.4.1).

## Ver también

- [[docs/bitacora/bitacora_sesion66]] — el hotfix que apagó la carta.
- [[docs/tareas]] · [[CHANGELOG]] · [[docs/decisiones]] (ADR-009).
