# Bitácora — Sesión 62

Sesión larga y de una sola naturaleza: **correr el modelo contra prediseños reales del
usuario y arreglar lo que aparece**. Casi todo lo de acá salió de una corrida concreta, no de
leer código.

Se liberaron dos versiones en el medio: **1.3.0** (convección natural en secadores pasivos) y
**1.4.0** (respaldo del auxiliar y correcciones del balance de cámara). Lo que quedó después
de la 1.4.0 está **sin commitear** — ver §7.

---

## 1. Lo que se cerró del work stream de convección natural

**RESPALDO del auxiliar** (etapas 2 y 3 del spec). Hasta S61 `RESPALDO_INDEPENDIENTE`
aplicaba el mismo ΔT aguas arriba que `SERIE_POSCOLECTOR`: elegirlo no cambiaba ningún
número. Ahora la potencia entra al **nodo de aire** de la cámara y, con set point, se modula
despejándola —`Q_aux = clamp(T_set·den − num_base, 0, Q_max)`, error nulo, sin iterar—.

**El respaldo refuerza el tiro**, que es la consecuencia que solo era posible después del
motor de caudal de S61: en un cajón con bocas, ṁ pasa de 0.0124 a 0.0633 kg/s entre 0 y
3000 W. Para eso `estimar_T_flujo_estacionario` también recibe la potencia.

Alcance por pipeline: Constantes, Transitorio y el encadenado de lotes (ventana y anual, para
ARMARIO y GRAN_ESCALA-BATCH). El túnel semicontinuo queda fuera por decisión explícita y lo
avisa.

---

## 2. Los bugs que encontraron las corridas reales

En orden de aparición, todos detectados por el usuario probando en Streamlit:

**El set point no llegaba al pipeline transitorio.** El techo de potencia viaja como serie en
las forzantes, pero la consigna es un escalar que se pasa aparte, y `_correr_motor_TD` no lo
hacía: la resistencia corría **siempre a plena potencia**. Entregaba 500 W con el aire ya a
91 °C y la consigna en 60 °C. Constantes sí la respetaba, así que **las dos rutas hacían
física distinta con la misma configuración**.

**El film convectivo interior de pared se evaluaba con la temperatura equivocada** (bug mío de
S61). Se le pasaba la T del aire **de entrada**; en tipología CAJA el aire entra a la
ambiente, así que `ΔT = 0` idénticamente, el Rayleigh se anulaba y quedaba solo el término
forzado: `h ≈ 0.5` en vez de ~2.4 (pared) / 3.7 (vidriado). La cámara resultaba **8× más
aislada de lo que es**, y por eso una resistencia chica sostenía cualquier consigna. El motor
ahora resuelve **dos veces por paso**: la primera estima `T_flujo`, la segunda usa el film
corregido. Consumo del auxiliar +31 %.

*Mutación de verificación:* con el bug, `U_pared` queda **congelado en 0.1933 en todos los
pasos**, idéntico con la cámara a 25 °C que a 65 °C.

**La potencia del auxiliar se pedía en kW con tope 100.** Escribir `5000` —pensando en watts,
que es como se compran, como los imprime el reporte y como los guarda el snapshot— daba
5000 kW, chocaba contra el tope y **el valor no se aplicaba**: la corrida seguía con la
potencia anterior sin que la pantalla lo dijera. Pasó a watts y sin tope.

**Tres pérdidas de campos por reconstrucción campo por campo** (el patrón del albedo de S36,
que apareció **cuatro veces** en esta sesión):

| Dónde | Qué perdía | Consecuencia |
|---|---|---|
| `camara_calc._calcular_termodinamico` | `Q_rad_aire_W`, `energia_rad_aire_total_J` | diagnósticos vacíos |
| `balance_global._correr_aux_y_armar_forzantes` | `Q_rad_aire_W`, `t0_utc` | todas las corridas transitorias |
| `simulacion_ventana._slice_forzantes` | `Q_rad_aire_W`, `t0_utc` | **cada lote** del anual/ventana |

El tercero era el grave: **la producción anual de una cámara translúcida subió 78 %** al
recuperarlo (114 → 203 kg/año, duración media de lote 91 → 43 h). El modo diario la calculaba
bien y el anual la subestimaba a la mitad. Los tres pasaron a `dataclasses.replace` o a
recorrer la dataclass.

**El sol no entraba al balance en tipología CAJA.** `energia_solar_util_MJ` se calculaba solo
como `ṁ·cp·(T_sal_col − T_amb)`, que sin colector da cero. Una caja translúcida se reportaba
con **fracción solar 0 %** y `COP_secado` 1.27 —mayor que 1 con la resistencia como única
entrada contabilizada, que no significa nada—. La energía ya estaba calculada por el motor;
faltaba sumarla. Pasa a 60 % solar y COP 0.51.

En el **modo anual** hubo que entrar en las dos magnitudes que ese modo distingue: el
**incidente** (`I_eq × A_translúcida`, por mes calendario) y el **útil** (`Q_rad + Q_rad_aire`
por lote, al mes de descarga). Un armario translúcido pasa de tener **todas** las métricas en
`None` a η_drying 7.9 % y energía específica 30.1 MJ/kg.

**`area_transversal_m2` ignoraba `direccion_flujo`.** Usaba siempre `ancho × alto`, la cara
perpendicular a un flujo horizontal. En un armario vertical la sección es la huella
`largo × ancho`: velocidad subestimada **2.2×**. El campo sí se respetaba en `motor_calc` para
la pérdida de carga, o sea que quedaba honrado para dimensionar el ventilador e ignorado para
la transferencia. **Impacto real: 1.3 %** (156 → 154 h) porque a esas velocidades manda la
convección natural.

---

## 3. Los topes de widgets

`st.number_input` **no recorta** un valor fuera de rango: lanza `StreamlitValueAboveMaxError` y
**rompe el render de la pestaña**. Abrir un prediseño industrial guardado podía tirar un
traceback.

Se auditaron los **113 topes** de la UI con un criterio explícito: se justifica solo el
**definicional** —fracción ≤ 1, ángulo ≤ 360, rendimiento ≤ 100 %, fecha—. Los **20
dimensionales** pasaron a `max(referencia, valor_cargado)`.

---

## 4. Bocas con sección distinta a la del elemento contiguo

Pedido explícito del usuario. Módulo nuevo `calculos/transiciones_seccion.py`, puro, que
consumen los dos circuitos: en convección natural la pérdida **define el caudal**, con
ventilador define la presión a entregar.

- **Expansión brusca** → Borda-Carnot, `K = (1 − A₁/A₂)²`. Exacta, del balance de cantidad de
  movimiento.
- **Contracción brusca** → Idelchik, `K = 0.5(1 − A₂/A₁)^0.75`.
- **Gradual** → se declara la **longitud** (lo que se mide con cinta), de ahí
  `θ = 2·atan(Δr/L)` con radios equivalentes, y `sin(θ/2)` interpola.

Lo elegante: **el caso brusco es el límite de la fórmula gradual**, no una rama aparte. Y la
cota `k ≤ 1` captura sola que un difusor de más de 45° desprende. Contra la tabla de Gibson:
0.45 vs 0.43 a 20°, 0.89 vs 0.87 a 40°. Ambos coeficientes referidos a la velocidad en la
**sección menor** (Idelchik/ASHRAE).

**UI**: un checkbox por boca. Tildado hereda la sección del contiguo (sin pérdida);
destildado aparece el campo del área. El campo de longitud de transición **solo aparece si hay
salto de sección**, y muestra el ángulo con el aviso de los 45°. Sin colector se deshabilita
el de entrada; sin chimenea el de salida.

**Back-compat**: flags `boca_*_hereda_seccion` con default `False`, así que todo proyecto
guardado se comporta igual.

Medido en el cajón del usuario (chimenea Ø 0.25 m): boca al 20 % de la sección → −1.7 % de
caudal; al 10 % → −7.1 %; y desarrollar la transición 0.6 m recupera parte.

---

## 5. Análisis del armario indirecto forzado (sin cambios de código)

`tests/armario indirecto forzado/` — armario con colector de 2×(2.5×1.0 m), cámara **opaca**
de 0.275 m³, ventilador, 9.5 kg de manzana, ventana 20–27/04/2010. Reproducido al decimal.

**Resultado: 156 h de secado, COP 0.109.** El reparto de los 163.5 MJ que el colector entrega:

| | |
|---|---|
| se va con el aire de salida | **119.2 MJ (73 %)** |
| evaporación | 18.1 MJ (11 %) |
| pérdida por paredes | 5.1 MJ (3 %) |

El aire entra a 31 °C y sale a 28.4 °C: cede **2.7 K**. Sale con 24 % de HR habiendo ganado
**0.8 g/kg** cuando podía cargar 21 — usa el **4 % de su capacidad**. El producto se queda a
15.4 °C (bulbo húmedo, física correcta).

**Diagnóstico**: el secador está desbalanceado. 5 m² de colector para 9.5 kg en 0.275 m³; con
0.25 m² de sección el aire repta a 0.12 m/s y los coeficientes quedan en ~2 W/m²K.

**Incoherencia geométrica anotada**: las bandejas son de 0.25 m², **exactamente la huella de
la cámara** — ocupan el 100 %, así que el aire debe atravesar la malla, mientras el modelo
calcula la velocidad sobre la sección vacía. Y `tipo_malla` está sin especificar.

---

## 6. Decisiones tomadas con el usuario

- **`Q_aux` va 100 % al aire por convección**, sin reparto radiativo: una resistencia de
  secador no llega a incandescencia. (Matiz registrado: un elemento a 200–300 °C emite en IR
  **medio**, no cercano; no cambia la decisión.)
- **Transiciones**: brusca por defecto **+ opción gradual** por longitud.
- **Incidente de la cámara**: `A_translúcida`, no `A_rad` — mismo criterio que el colector,
  toda la radiación sobre la superficie captadora antes de cualquier eficiencia.
- **Respaldo en ventana/anual**: solo ARMARIO y GRAN_ESCALA-BATCH; el túnel queda fuera.
- **Criterio de versionado adoptado**: *si cambian los resultados, cambia la versión*.

---

## 7. Estado al cierre

- **`origin/main` = `080eec7` (v1.4.0), pusheado y deployado.** Space `RUNNING`.
- **24 archivos SIN COMMITEAR** sobre esa base, con cinco bloques: balance solar de cámara
  (diario + anual), aviso de set point inalcanzable, rótulo de la previa de P4, bocas con
  sección distinta (módulo + UI + serialización), y el fix de `direccion_flujo`.
- **Suite 1910 passed + 2 skips.** Ruff, black y auditoría i18n limpios.
- El usuario **no probó todavía** los cambios posteriores a la 1.4.0.

**Pregunta abierta que quedó sin responder** (última de la sesión): con bandejas que ocupan
toda la huella, ¿se modela el flujo **a través** de la malla —más trabajo, necesita
`tipo_malla`— o se documenta como límite del modelo?

Los pendientes vivos están en `docs/tareas.md`, sección "Salidos de las corridas reales de
S62", que se escribió en esta sesión justamente porque vivían solo en la conversación.

## Ver también

- [[docs/tareas]] — backlog, con la lista de pendientes al día.
- [[docs/notas/spec_conveccion_natural_y_respaldo]] — §8 y §8.1, desvíos del plan.
- [[docs/mapa_auxiliar]] — la inconsistencia de RESPALDO, ya cerrada.
- [[CHANGELOG]] — `[1.3.0]`, `[1.4.0]` y el `[Unreleased]` con lo que falta commitear.
