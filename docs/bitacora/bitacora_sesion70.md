# Bitácora — Sesión 70

**Fecha:** 2026-11-19 / 20 · **Tema:** modelo de evaporación (Fases 0, 1, 2 y primer paso de
la 3) y releases **1.5.0** y **1.5.1**. Para retomar: **§16**.

## 1. Decisiones del usuario (§9 de [[docs/notas/plan_modelo_evaporacion]])

1. Camino **(b)**, resistencias en serie.
2. K del pimiento: verificar contra la tabla y discutir → se generalizó el inversor.
3. Productos sin isoterma: **isoterma por analogía, con aviso**. Tabla de analogías aprobada
   (§3). Perejil y apio → hoja. Charqui → sin isoterma, con aviso fuerte.
4. No hay registros crudos de los ensayos del grupo: **se digitalizan figuras**.
5. La pausa de S67 sobre transferencia de cámara se levanta a lo largo de este sprint.

## 2. K = 1.02 del pimiento

- Es el valor publicado (Vega 2007, Tabla 2). Con él, la GAB reproduce la Tabla 3 del mismo
  paper (X de equilibrio a 50–80 °C) dentro del `%E = 11` declarado.
- `actividad_agua_desde_X_GAB` rechazaba `K ≥ 1` y el `except` de `_aw_func` lo convertía en
  un **escalón 1/0 en X_m**. Ahora acepta `K > 0`: la raíz positiva cumple `K·a_w < 1`, así que
  `a_w < 1/K` (pimiento fresco: 0.973). Aviso de runtime `CAM_TD_GAB_K_MAYOR_1`.
- `K ≥ 1` es habitual en desorción de frutas azucaradas (uva y damasco de Kaymak 2004:
  1.00–1.04; yerba mate y algarroba también lo tocan).

## 3. Isotermas nuevas y analogías

Conseguidas con Claude in Chrome (ver §5):

| Producto | Isoterma | Fuente |
|---|---|---|
| tomate, cebolla, zanahoria | propia, GAB(T) a 45 °C | Kiranoudis et al. 1993, J Food Eng 20:55, Tabla 3 |
| yerba mate | propia, a 50 °C (sets 20–90 °C) | Schmalko 2005, tesis UBA, Tabla 8.4 |
| algarroba | propia, harina cruda a 45 °C | Prokopiuk et al. 2010, Int J Food Prop 13:692, Tabla 2 |
| ají rojo | analogía → pimiento rojo | mismo género |
| mandioca | analogía → papa | almidonoso |
| durazno, ciruela, granada | analogía → damasco | Kaymak 2004 desorción (`catalogo/isotermas_referencia.yaml`) |
| perejil, apio, orégano, coca | analogía → yerba mate | hoja |
| charqui | **ninguna** | Comaposada 2000 pendiente |

Verificaciones y hallazgos:

- **Kiranoudis**: el texto extraído pierde la escala de la cabecera; leída de la página
  renderizada, la Tabla 3 imprime `C0 ×10⁵` y `k0 ×10²`. Con eso la GAB reproduce la Tabla 2
  del paper dentro de `S_R ≈ 2.5 % b.s.` en las 5 hortalizas × 3 temperaturas.
- **Damasco** (Kaymak 2004): el PDF pierde el signo de `ΔH_k`; se tomó negativo, el criterio
  que reproduce exactamente la manzana y la papa ya cargadas del mismo paper.
- **Prokopiuk** es **adsorción** sobre **harina**, no desorción como decía la nota del
  catálogo. Levemente optimista para secado; es la única GAB de algarroba.
- **Citas erradas del catálogo**: Schmalko & Alzamora 2001 no es un paper de isotermas;
  Comaposada 2000 no es J Food Eng 43(2) (ese DOI no existe) sino Meat Science, y es cerdo.
- Pimiento **verde** (Kiranoudis) `K ≈ 0.66` vs pimiento **rojo** (Vega) `K = 1.02`:
  coherente con más azúcar en el fruto maduro.

## 4. Código

- `core/catalogo.py`: `ISOTERMAS_REFERENCIA` y `isoterma_gab(producto_id) → IsotermaGAB | None`
  (propia → analogía, sin encadenar). Vive en `core/` porque lo usan `core/camara.py` y
  `calculos/camara_calc.py`.
- `calculos/psicrometria.py`: inversor GAB acepta `K ≥ 1`.
- `calculos/camara_calc.py`: `_aw_func` sobre el resolutor; avisos `CAM_TD_GAB_ANALOGIA`,
  `CAM_TD_GAB_K_MAYOR_1`, `CAM_TD_GAB_FALTA` (reescrito). **Se eliminó la rampa `X/X₀`**: la
  reserva es `a_w = clip(X/X_eq_catálogo, 0, 1)` — agua libre hasta la humedad de equilibrio.
- `core/camara.py`: `_validar_producto` y advertencias con el resolutor; nueva
  `PROD_ISOTERMA_ANALOGIA` (INFO); `PROD_ISOTERMA_FALLBACK` reescrita. Plantillas en los 3 YAML.
- Tests: `tests/test_core/test_catalogo_isotermas.py` (cobertura de todo el catálogo, `a_w`
  física en todo el rango, analogías aprobadas, sin encadenar); casos nuevos en
  `test_psicrometria.py`, `test_camara.py`, `test_camara_dispatcher.py`.

## 5. Efecto medido (Constantes, 60 °C, HR 15 %, 3 kg, X_obj = 0.15)

**Con la rampa, 14 de 19 productos no llegaban a X = 0.15 en 72 h**: `a_w = X/X₀` ponía al
producto en «equilibrio» con aire de HR ≈ 1–5 % y frenaba el secado. Ahora todos terminan en
8–14 h. Productos que ya tenían GAB: sin cambio, salvo pimiento (12.9 → 13.4 h, por el K).
Coincide con lo previsto en el plan §3 (la rampa simulaba mal un período decreciente), pero el
efecto era mucho mayor que «secan algo más rápido».

Consecuencia: **sin la resistencia interna (Fase 2) todos los productos son ahora optimistas
del mismo modo**; antes 14 eran pesimistas por un artefacto. La Fase 0 no se libera sola.

### Dos tests que dependían de la rampa

Ambos usan el cajón con **tomate** de `test_conveccion_natural_cajon._proyecto`:

- `test_balance_solar_camara`: exigía `COP_secado < 1`. Ahora da 1.047, y es física correcta:
  de noche el tomate se enfría a ~13 °C (bulbo húmedo) y evapora 0.8 kg con el calor que cede
  el aire ambiente (20 °C, 50 % HR), que `E_total` (sol + auxiliar + motor) no cuenta. El test
  pasó a la cota física `E_latente ≤ E_total + potencial adiabático del aire`.
- `test_respaldo_auxiliar` (set point): con 22 °C la resistencia no se apagaba nunca porque el
  producto húmedo (≈190 W latentes al mediodía) sostiene la cámara en 21.3 °C. Consigna a
  20.5 °C.

### COP con el aporte del ambiente (decisión del usuario: opción B)

Todas las energías del balance se miden respecto del ambiente, así que el calor que el
ambiente cede cuando el proceso queda **por debajo** de T_amb no estaba en ningún lado. Se
eligió el aporte **real** (B), no el potencial adiabático del aire (A, que mezclaba entregas
con un máximo teórico y duplicaba `aprovechamiento_aire` del anual):

```
Q_ambiente = max(0, −UA_loss·(T_flujo − T_amb))          envolvente: pared + techo vidriado
           + max(0, ṁ·cp_hum·(T_amb − T_salida))          aire que sale más frío que afuera
```

- Motor: `EstadoCamara.q_envolvente_W` (pared + techo; `q_pared_W` sigue siendo solo la pared
  opaca, para los nodos) y `ResultadoMotorTermodinamico.Q_ambiente_W` /
  `energia_ambiente_total_J`, integrados paso a paso como la radiación y el auxiliar.
- `balance_global`: `energia_ambiente_camara_MJ`, campo `energia_ambiente_MJ` en los dos modos,
  sumado a `E_total`.
- UI: métrica en P7 Transitorio, barra en el balance de Constantes, fila de la tabla, TXT,
  JSON y PDF (3 idiomas).
- Cajón con tomate: ambiente 1.02 MJ de 9.36 MJ → **COP = 0.934** (era 1.047). El test volvió a
  exigir `COP < 1`. Control: cámara a 50–60 °C con ambiente a 25 °C → aporte 0.
- Queda fuera: el calor sensible del propio producto al enfriarse, y `Lv` fijo a 20 °C
  (`LV_AGUA_MJ_KG = 2.450`, ~2–3 % bajo a 50–60 °C). El modo VENTANA/cascada no tiene COP y no
  se tocó.

## 6. Claude in Chrome en Fedora

El Chrome era **Flatpak**: el native messaging host de Claude Code no se ve desde el sandbox.
Se instaló Chrome nativo (RPM de Google) en paralelo; funciona sin tocar nada más. Para que la
descarga no abra un diálogo hay que desactivar «Preguntar dónde guardar» en el Chrome nativo.
ScienceDirect identificó la sesión como UNAM (México): los papers restringidos no se bajaron.

## 7. Estado a mitad de sesión (histórico; ver §16)

- `testing` = `ca68ceb` + Fase 0 sin commitear. PDFs nuevos en `docs/notas/papers/`
  (gitignoreados); transcripción de Prokopiuk en `.md` (sí versionable).
- **Pendiente:** Comaposada 2000 desde el IER; luego Fase 1 (digitalizar ensayos de agua libre:
  Durán 2008, Condorí 1998).

## 8. Primera réplica: secador de caja de Durán et al. 2008 (charqui, forzado)

Caso en `validacion/duran2008/` (script + datos digitalizados de las Figs. 17, 18, 20 y 22).
Supuestos en el docstring del script. Resultado, caja con ventiladores FV:

| | Secasol | Medido |
|---|---|---|
| X: 1.15 → 0.57 | **~2.5 h** | ~7.5 h de sol (día 1) |
| X ≈ 0.24 | 4.5 h | ~31 h (dos días) |
| T flujo, día 1 con producto | 18–20 °C | 25–29 °C |
| HR interna | 35–44 % | 16–27 % |
| T flujo con caja casi seca (control térmico) | 22–27 °C | 25–29 °C |

- **La parte térmica de la caja anda**: sin evaporación, el aire queda ~3 °C por debajo de lo
  medido. El error de T y HR con producto es consecuencia de evaporar ~7× más rápido: la
  energía se va en latente.
- **El error es la resistencia interna** (charqui corre además con `a_w = 1`): ajuste de
  Fick a la Fig. 22 da `D_eff ≈ 1–3·10⁻¹⁰ m²/s` (fetas 6–10 mm), en rango de carne vacuna.
  Primer dato para la Fase 2. El caudal no cambia nada (0.012–0.026 m³/s: 4.4–4.5 h).
- **Hueco de modelo**: `PROY_CAJA_CON_MOTOR` impide una CAJA con ventilador, y este secador
  doméstico la tiene. Se replicó como CAJA sin motor ni bocas (caudal constante).

## 9. Fase 2: resistencia interna (implementada)

Diseño cerrado en el §2.3 del plan: nodo de superficie `X_s`, flujo interno
`λ·m_s·(X − X_s)` con `λ = μ₁²·D_eff(T)/L²` (primer modo de Fick, `L` = mitad del `d_p` de la
pieza), igualado al de la película con `a_w(X_s)`. Opt-in: sin difusividad en el catálogo el
motor es idéntico al previo.

- **Motor** (`calculos/camara_termodinamica.py`): `humedad_superficie_producto` (raíz escalar;
  la cadena es afín en `ω_sup`, así que `G` sale exacto), parámetro `tasa_difusion_func` en
  `simular_secado` y `simular_cascada`, `EstadoCamara.X_sup_kg_kg` y serie
  `ResultadoMotorTermodinamico.X_sup_kg_kg`.
- **Catálogo**: `core.catalogo.DifusionInterna` / `difusion_interna(id)` (sin analogías) y
  bloque `difusion_interna` en 7 productos:

| Producto | D_ref [m²/s] | T_ref | E_a [kJ/mol] | Geometría | Fuente | Calidad |
|---|---|---|---|---|---|---|
| manzana | 3.5e-10 | 50 °C | 34 (de los extremos del rango) | lámina 6 mm | Sacilik 2006 | MEDIA |
| pimiento rojo | 3.51e-9 | 50 °C | 39.7 | lámina 8 mm | Vega 2007 (regresión) | ALTA |
| ají rojo | 3.78e-9 | 50 °C | 37.76 | cilindro 12 mm | Kaleemullah 2006 | ALTA |
| ciruela | 3.04e-10 | 55 °C | 17.9 (ajuste S70) | lámina 3.5 mm | Goyal 2007 | MEDIA |
| durazno | 3.04e-10 | 55 °C | 16.1 | lámina 3.5 mm | Kingsly 2007 | BAJA (unidad, mismo 3.04 que ciruela) |
| papa | 4.01e-9 (aparente) | 40 °C | 8.8 | lámina 10 mm | Hassini 2007, col. L0 | MEDIA |
| charqui | 1.1e-10 | 30 °C | — | lámina 6 mm (supuesta) | ajuste Durán 2008 | BAJA |

  Durazno, ciruela y charqui recibieron además `forma_geometrica` (antes caían al `d_p` de
  8 mm por defecto; cambia también la rugosidad del canal en el ΔP).
- **Avisos**: runtime `CAM_TD_DIFUSION_FALTA`; diseño `PROD_SIN_DIFUSION_INTERNA` (WARNING, 3
  idiomas); línea ✅/⚠️ en la tarjeta de producto de P4.
- **Tests**: `tests/test_calculos/test_difusion_interna.py` (23): igualdad de flujos, límites
  `λ → ∞` y `λ → 0`, catálogo, Arrhenius contra Vega Tabla 4, **curva de Saravia 2007**,
  wire-up.

Efecto (Constantes, 60 °C, HR 15 %, 3 kg en 5 bandejas, X_obj 0.20): manzana 10.6 → 18.6 h,
charqui 8.7 → 24.3 h, ciruela 11.5 → 13.6, durazno 11.0 → 12.7, pimiento 11.6 → 12.4, ají
9.6 → 10.1, papa 9.9 → 10.3 h. Las difusividades aparentes de pimiento, ají y papa
(~4·10⁻⁹) dejan el secado limitado por el aire en este caso.

Réplica Durán 2008 con difusión: RMSE X 0.32 → 0.10, T flujo 9.8 → 5.6 °C, HR 22 → 6.9 %
(circular para X: la D del charqui sale de esa curva). Lo que queda: de noche el modelo sigue
secando (X 0.55 → 0.35) y la muestra no; es la **isoterma** del charqui (a_w = 1 a 3 °C), no
la difusión — Comaposada sigue siendo lo que falta.

Pendiente: 12 productos sin difusividad (tomate, cebolla, zanahoria, yerba, algarroba,
perejil, apio, mandioca, orégano, coca, granada, yacón); `diagnostico_transferencia` todavía no
distingue resistencia externa de interna (§4 del plan).

## 10. X objetivo por debajo del equilibrio

Pedido del usuario al probar manzana en la app: con aire a 25 °C y 20 % HR el producto se
equilibra en X ≈ 0.17, así que el X_obj = 0.15 por defecto es **inalcanzable**, y la app
sugería "aumentar el horizonte".

- `camara_calc.humedad_equilibrio_alcanzable`: invierte el **mismo** `aw_func` del motor en la
  HR mínima del aire **sin la humedad del producto** (`_HR_aire_sin_evaporacion`: ω de entrada a
  `max(T_flujo, T_ent)`, que ya incluye colector, auxiliar y radiación). No se usa `HR_flujo`:
  si la corrida corta con el producto húmedo, ese aire nunca se secó y el equilibrio quedaba
  sobrestimado (decía "inalcanzable" cuando faltaba tiempo).
- `ResultadoMotorTermodinamico.X_equilibrio_kg_kg`; aviso runtime
  `CAM_TD_X_OBJ_BAJO_EQUILIBRIO`; en P4 y P7 un `st.error` traducido
  (`comun.x_obj_bajo_equilibrio`) con el valor de X_eq, que **reemplaza** al consejo de
  ampliar el horizonte.
- **Bug numérico de paso** en `actividad_agua_desde_X_GAB`: la fórmula cuadrática directa
  cancelaba con X → 0 (a ∝ X) y a X = 1e-9 daba `a_w` fuera de rango, que el `except` del
  motor convertía en **agua libre**. Con la raíz de superficie de la Fase 2 eso podía dar una
  raíz espuria cerca de cero. Forma estable (q = −(b + sgn(b)·√disc)/2).
- Tests: `tests/test_calculos/test_equilibrio_objetivo.py` (7).

El usuario considera además que X_obj = 0.15 por defecto es bajo: queda para decidir el
valor por defecto (no se cambió).

## 11. Fase 3, primer intento: tanda de ADITAL del 21/03/2009

`validacion/adital/replica_tanda_2009.py`. Fuente: Condorí, Durán, Vargas & Echazú 2009
(AVERMA 13:02.35; Condorí 2010 ERMA 25 repite los mismos datos). Lote de ~2 t (2010: 2400 kg)
de pimiento para pimentón **en vaina entera**, ventilador desde la tarde, solo sol. Día
sintético de marzo de `validacion_adital` repetido 4 días, colector + caño maestro hora a hora,
ventilador 9–19 h, tiro natural de noche (5 %).

- **X0 ≈ 3, no 10.7**: la muestra de la Fig. 14 va de 140 g a 40 g seca; con ~12 % b.h.
  final, m_s ≈ 35 g. El X0 = 10.7 del preset es el del pimiento morrón fresco (Vega 2007).
- **El modelo seca la tanda más lento que la muestra**: X a las 18 h de los días 1–4 = 2.76 /
  2.20 / 1.64 / 1.09 contra 1.74 / 1.17 / 0.51 / 0.14 medido. **Idéntico con y sin difusión**:
  a 2 t el secador está limitado por el aire (HR 8 → 18 % de entrada a salida al mediodía).
  Con 3.8 kg/s (caudal del preset de cámara; el banco da 1.9) llega a 0.78; con 1 t, a 0.05.
- **Los datos de cámara no cierran un balance**: a las 16 h (Figs. 10–11) entrada 62 °C/10 %
  y salida 48 °C/9 % dan Δω = −9.4 g/kg (el aire perdería agua). Y secar 2 t de X 3 a 0.14
  en 30 h de sol exige Δω ≈ +7 g/kg a 1.9 kg/s: incompatible con "HR de salida ≈ entrada".
  La muestra (una sola, pesada a mano) probablemente no representa a la carga media.
- Inconsistencia de entrada a revisar: caudal del preset de cámara (3.8 kg/s) contra el del
  banco de colectores (2.2 m³/s ≈ 1.9 kg/s).

Conclusión provisoria: este ensayo no discrimina el modelo de evaporación (limita el aire y
los datos no cierran masa). Preguntas al usuario (autor del ensayo) antes de seguir.

## 12. Carros en serie: la transferencia de gran escala estaba ~26× baja

Dato del usuario: **la muestra de la Fig. 14 estaba en el carro frente a la entrada de aire
caliente**. Al simular ese carro solo seguía secando lento, con y sin difusión: el `h` sobre el
producto en ADITAL era **~2 W/(m²·K)** y el NTU 0.20.

Causa (bug de modelo, previo): `area_canal_entre_bandejas_m2` tomaba las
`n_carros × bandejas_por_carro` = 336 bandejas como **una sola pila** de 335 canales en paralelo
(68 m² de paso contra 5.55 m² de sección del túnel) → 0.06 m/s sobre el producto, contra
0.2–1.25 m/s medidos (Condorí 2009, Fig. 13). Además la placa plana usaba los 18 m del túnel.
`motor_calc` (ΔP) ya trataba los carros en serie desde la mejora 29, y el docstring decía que
ambas usaban la misma sección.

- Fix en `calculos/camara_calc.py`: con carros, canales = `bandejas_por_carro − 1`;
  `longitud_flujo_producto_m` = `largo_carro_m` o `largo / n_carros` (la capa límite se reinicia
  en cada carro; la pared sigue con el largo total). ADITAL: canal 2.65 m², 1.65 m/s, L 0.75 m,
  h 5.2, NTU 0.53. Tests: `tests/test_calculos/test_carros_transferencia.py` (5).
- **Cambia todo resultado de gran escala con carros** (BATCH y SEMICONTINUO). Los 521 tests de
  cámara/gran escala pasan; `validacion_adital` sigue 7/7 (la cadena térmica no depende de esto).

Réplica con el fix (`validacion/adital/replica_tanda_2009.py`):

| X a las 18 h, días 1–4 | d1 | d2 | d3 | d4 |
|---|---|---|---|---|
| Muestra (primer carro) | 1.74 | 1.17 | 0.51 | 0.14 |
| Carga media 2 t (antes del fix) | 2.76 | 2.20 | 1.64 | 1.09 |
| Carga media 2 t (con fix) | 2.63 | 1.77 | 0.93 | 0.18 |
| Primer carro, difusión 8 mm (catálogo) | 2.47 | 1.19 | 0.11 | 0.05 |
| Primer carro, difusión 25 mm (vaina entera) | 2.49 | 1.33 | 0.46 | 0.09 |

- La carga media llega a X ≈ 0.15–0.18 al cuarto día; el primer carro, antes: coherente con
  "seco en ~30 h de sol" para la muestra.
- Con el espesor de la vaina entera (~25 mm) en lugar del de los cubos de Vega (8 mm), los días
  3–4 del primer carro caen sobre lo medido (0.64/0.46/0.14 contra 0.69/0.51/0.14 a las 15/18 h
  del día 3 y 15 h del día 4). Indicio, no calibración: una sola muestra.
- El día 1 (140 → 96 g en 3 h) no lo reproduce ninguna variante: posible agua superficial del
  lavado.
- Ahora con el aire acoplado, la HR sube de 8 a ~27 % de entrada a salida al mediodía: el modelo
  ya no dice "aire subaprovechado" para 2 t. Los datos de cámara de 2009 no cierran masa (§11),
  así que no se pueden usar para zanjarlo.

## 13. X objetivo por producto desde una a_w objetivo (decisión del usuario)

Un X objetivo único (0.15) significaba cosas muy distintas: manzana a_w 0.16 (sobresecada y
por debajo del equilibrio con aire al 20 % HR), yerba/hojas/papa/algarroba a_w 0.63–0.72
(húmedas, en el límite de mohos). Subirlo a 0.20–0.25 —propuesta inicial— habría dejado esos
productos en a_w 0.80–0.83.

- `core.catalogo.objetivo_secado(id) → ObjetivoSecado(X, a_w, origen)`: prioridad
  `objetivo_secado.X` del catálogo (criterio comercial) → `objetivo_secado.a_w` del catálogo →
  `AW_OBJETIVO_DEFAULT = 0.60` sobre la isoterma (propia o por analogía) → reserva 0.15 (hoy
  solo el charqui). `humedad_desde_aw_gab` es la GAB directa.
- Defaults resultantes: manzana 0.402, tomate 0.271, cebolla 0.255, durazno/ciruela/granada
  0.237, zanahoria 0.232, yacón 0.212, pimiento/ají 0.196, papa/mandioca 0.140, hojas
  (yerba, perejil, apio, orégano, coca) 0.104, algarroba 0.099, charqui 0.150 (reserva).
- P4: al elegir producto propone su X; debajo, "con este X el producto queda en a_w ≈ …" y el
  valor propuesto (3 idiomas); sin isoterma, aviso de que el default no tiene criterio de a_w.
- No cambió el default de la dataclass `CargaProducto.humedad_objetivo_X` (0.15), que solo usan
  los proyectos armados por código; tampoco el preset de ADITAL (X_obj = 1.0, de la tesis).
- Las isotermas están a ~45 °C: a temperatura de almacenamiento la misma X da a_w algo menor
  (criterio del lado seguro). Productos con humedad comercial propia (p. ej. pimentón 10–12 %
  b.h.) se declaran con `objetivo_secado.X` en su ficha; no se cargó ninguno todavía.
- Tests: `TestObjetivoSecadoPorProducto` en `tests/test_calculos/test_equilibrio_objetivo.py`.

## 14. Política de difusividades, Fase 1 y largo de placa (2026-11-20)

**Difusividades de la literatura (decisión del usuario: adoptar el método).** Los D de capa
fina absorben la película del equipo de ensayo. Política: el D del catálogo es el que hace que
**Secasol** reproduzca el ensayo publicado, con el h del equipo estimado como placa plana sobre
la pieza (el h casi nunca se informa; queda anotado por caso). Herramienta:
`validacion/difusividad/reajuste_difusividad.py` (reconstruye la curva del paper con su propio D
y su convención de L; busca el D de Secasol que llega a MR = 0.2 al mismo tiempo).
Primer resultado: ciruela +17 %, durazno +19 %, manzana +37 % (40 °C); en pimiento, ají y papa
la película estimada sola ya es más lenta que el ensayo → el h de esos equipos (canasta, malla,
cubos) era mayor: D publicado = cota inferior. Cuando el "D" de un paper crece con el espesor
(tomate, cebolla), no es una propiedad del producto: limitaba el aire.
**No se sacó la 1.5.1 por eso**: la corrección era menor que la incertidumbre del h.

**Fase 1 — película contra agua libre.** Condorí 1998 no alcanza (sin área de bandejas, sin
caudal, sin clima). Durán 2008, bandejas de 20 × 10 cm (dato del usuario), secador con panel FV,
13:00–17:30: 55 g en 4.5 h = 0.61 kg/m²h. Balance de la bandeja (sol bajo policarbonato,
evaporación, convección y radiación) con la película de Secasol: **11.7–12.0 g/h contra 12.2
medidos** si la bandeja recibe el sol de lleno (6–7 g/h a media sombra). Contra Carrier/ASHRAE
(superficies de agua): Secasol con el largo de la **bandeja** queda 10–35 % abajo en 0.05–3 m/s;
con el largo de la **cámara**, 2–3× abajo a 1–3 m/s.

**Cambio de modelo: la placa es la bandeja** (decisión del usuario).
`camara_calc.longitud_flujo_producto_m` = `área_bandeja / ancho`, acotado por el largo de la
cámara y del carro. Armario por defecto: L 1.2 → 0.625 m, h casi igual (a 0.06 m/s manda la
convección natural). ADITAL: L 0.75 → 0.32 m, h 5.2 → 7.8, NTU 0.53 → 0.80. **Cambian los
resultados** (más donde la velocidad es mayor). Tests en `test_carros_transferencia.py`.

Consecuencias en las réplicas:
- Charqui (Durán 2008): el D que mejor ajusta el día 1 con la película nueva es 1.09e-10, igual
  al del catálogo (1.1e-10): domina la resistencia interna y el valor estaba bien determinado.
- ADITAL, primer carro: con la película nueva el pimiento de Vega (cubos cortados, 3.5e-9) seca
  demasiado rápido. Ajustando a la muestra (días 2–4; el día 1 tiene la caída anómala): **D ≈
  2.1e-10 m²/s a 50 °C** (lámina equivalente 8 mm, E_a de Vega) → 1.19/0.55/0.41/0.16/0.12
  contra 1.17/0.69/0.51/0.14/0.14. Coherente con la vaina entera con piel (Condorí 2001: vaina
  entera 6 d contra mitades 3 d). Calidad BAJA: una muestra.

## 15. Release 1.5.1 (preparado, 2026-11-20)

- **Caudal del preset de ADITAL**: 3.8 kg/s era el de diseño de la tesis (600 m³/h × 26); 1.9
  salía del preset del colector, armado como Tipo 1 con **un** canal de 5 cm. El usuario aclaró
  que la chapa ondulada forma **dos** canales de ~5 cm (aire por arriba y por debajo, tesis
  cap. 2) → Tipo 2. Medido en 2010 (cap. 3): 1.4 m/s medios en el difusor de 1.2 × 1.8 m,
  ρ 1.1 → **3.3 kg/s**. Preset: Tipo 2, 2 × 5 cm, 1.5 m/s, cámara 3.3 kg/s.
- **Bug general de Tipo 2/3**: `ColectorUnidad.seccion_canal_m2` contaba siempre el canal
  superior. Ahora depende del tipo (2: suma; 3: inferior). Afecta `caudal_total_m3_s`,
  `caudal_masico_banco_kg_s`, la velocidad del lazo natural, el área de la boca y el preview de
  P3. Tests en `test_core/test_colector.py`.
- **Producto nuevo** `pimiento_pimenton` (vaina entera) y **yerba mate** con difusividad de
  Schmalko y `dimension_pieza_m` = 0.36 mm.
- `validacion_adital` despacha por tipo de colector. Con el preset nuevo: 5/7. Quedan afuera
  (a decidir con el usuario): (1) pico de colector 67.9 °C contra el rango 70–90, pero los 80 °C
  medidos eran **con el ventilador apagado** (con ventilador ~60 °C, Condorí 2009); (2) potencia
  del ventilador 14.7 HP contra 4 HP de placa: con 3.7 m³/s, 1350 Pa de singulares, casi todo el
  acople de ø 0.45 m a 23 m/s.
- `test_ventana_glue::test_el_encadenado_inmediato_ya_no_es_cota_superior`: con lotes más
  cortos ambas políticas cierran 3 lotes; el test conserva lo que importa (el encadenado
  inmediato no produce más) y deja de exigir la misma agua evaporada.
- **Chequeo del pico de colector corregido** (decisión del usuario): los 80 °C eran con el
  ventilador apagado; a caudal de diseño se compara contra 55–75 °C (medido con ventilador ~60).
- **Ventilador: pendiente.** El usuario confirma que es de 4 HP y que el caudal en el ventilador
  no tendría por qué ser menor que en el difusor, salvo que en el primer año (2 t de carga,
  energía de sobra) se haya abierto la esclusa lateral entre ventilador y difusor para mezclar
  aire ambiente. Con 3.7 m³/s el modelo da 14.7 HP (1350 Pa de singulares, casi todo el acople
  de ø 0.45 m a 23 m/s): revisar el modelo de pérdidas singulares del acople.

## 16. Estado al cierre y para retomar (desde el IER)

**Producción:** v1.5.1 (`origin/main` = `main` = `testing` = `aa8f932`, tags `v1.5.0` y
`v1.5.1`). Verificada en el Space (panel Entorno). La rama `hotfix-1.4.1` y el worktree
`../secador_solar_hotfix` ya no hacen falta (borrarlos solo si el usuario lo pide). Fuera de git
a propósito: `docs/Papers de secadores p_ calibrar secasol/` (PDFs con copyright),
`docs/asades2026/`, `uv.lock`.

**Qué hay en el modelo** (detalle en §8–15, en `CLAUDE.md` y en
[[docs/notas/plan_modelo_evaporacion]]):
- `a_w` por isoterma propia o por analogía; sin rampa; K ≥ 1 aceptado.
- Resistencia interna en serie (nodo de superficie, Fick primer modo) en 9 productos.
- Película con el largo de la **bandeja** (Fase 1 anclada en agua libre).
- Carros en serie; colectores Tipo 2/3 con la sección de sus canales activos.
- X objetivo por producto desde a_w = 0.60; aviso de X objetivo bajo el equilibrio.

**Para conseguir en el IER** (acceso institucional; desde México no usar el de la UNAM):
1. **Comaposada, Gou & Arnau 2000**, Meat Science 55(3), PII S0309174099001540 — isoterma de
   carne salada para el charqui (hoy corre con `a_w = 1`: seca de noche en la réplica de Durán
   2008).
2. **Difusividades con varios espesores o curvas** para reajustar dentro de Secasol:
   - tomate: Demiray & Tulek 2012, Heat Mass Transfer 48 (DOI 10.1007/s00231-011-0942-1);
   - cebolla: Demiray et al. 2017, Heat Mass Transfer (DOI 10.1007/s00231-016-1943-x);
   - zanahoria: Doymaz (zanahoria naranja, aire caliente, sin pretratamiento);
   - mandioca: Sanni 1997; ají (isoterma): Kaleemullah 2004.
   Los de acceso abierto ya leídos están citados en §14 y en la respuesta del 20/11.
3. **Evaporación de agua libre** (validación independiente de la película a varias
   velocidades): Pauken 1999 (Exp. Heat Transfer), Bower & Saylor 2009 (IJHMT), Shah 2014.

**Siguientes pasos, en orden sugerido:**
1. Ventilador de ADITAL: el modelo pide 14.7 HP contra 4 HP reales; revisar los singulares del
   acople de ø 0.45 m (1350 Pa a 23 m/s). El usuario confirma 4 HP y que el caudal en el
   ventilador es el del difusor (salvo la esclusa lateral abierta el primer año).
2. Reajustar con `validacion/difusividad/reajuste_difusividad.py` las difusividades de tomate,
   cebolla, zanahoria y el resto con los papers del punto 2; cargar las que queden bien
   determinadas.
3. Isoterma del charqui con Comaposada.
4. Ensayo propio de agua libre (bandejas de área conocida, balanza, anemómetro, T/HR) cuando el
   usuario vuelva a Argentina.
5. Fase 3 con la planta de San Carlos 2012 (diagramas de caja de T y HR de campaña).

**Herramientas nuevas:** `validacion/duran2008/` (caja con charqui), `validacion/adital/`
(tanda de 2009, primer carro y carga media), `validacion/difusividad/` (reajuste de D),
`validacion/validacion_adital.py` (6/7 con el preset nuevo).
