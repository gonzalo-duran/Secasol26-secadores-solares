# Bitácora — Sesión 38 (2026-06-08)

**Tema:** Eliminación del motor de capa fina de la cámara de secado. La cámara pasa a
tener un **único** motor físico (termodinámico, balance acoplado calor-masa).

**Estado al cierre:** Implementado y verificado. Suite **872 passed, 0 failed, 0 xfailed**
(antes 919 + 2 xfailed; bajan ~49 ítems por borrado/poda de tests del motor capa fina y por
des-xfailear 2 tests que ahora pasan). Versión local bumpeada a **0.11.0**. AppTest: las 7
secciones renderizan sin excepción. Sin commitear (working tree puro). Diff acotado a la
eliminación (se restauraron los reformateos de `black .` sobre archivos ajenos a la tarea).

---

## 166. Diagnóstico físico — por qué se elimina el motor de capa fina

El usuario reportó que el motor de capa fina "nunca funcionó bien" mientras el termodinámico
(TD) "funciona como tiene que ser". Diagnóstico desde la física:

**Qué es el modelo de capa fina.** Correlaciones empíricas de la razón de humedad
MR(t) = (X−X_eq)/(X₀−X_eq) (Lewis/Page/Henderson-Pabis/Midilli/Logarítmico), ajustadas sobre
curvas de secado de **una capa delgada** expuesta a aire a **T, HR y v constantes** en
laboratorio. Los coeficientes (k, n, a, b, c) son **agrupados (lumped)**: meten difusión
interna, capa límite, encogimiento y geometría en pocos números, válidos solo en las
(T, HR, v, espesor) del experimento.

**Por qué fallaba en la práctica (bug de implementación + límite intrínseco):**
1. **Evaluación de punto único a temperatura pico.** En modo Constantes corría a
   `T_operacion = T_salida_colector` a irradiancia de diseño (el pico) y HR constante durante
   todo el secado → sobreestima k medio → tiempos demasiado cortos (síntoma "0.25 h").
2. **Insensible al espesor de lecho.** El k está calibrado a un espesor de laboratorio
   (p.ej. yacón a 4 mm); para lechos gruesos no frena (solo emitía una advertencia, el número
   seguía mal).
3. **Insensible a la velocidad de aire.** El k de catálogo está a una v de laboratorio
   (yacón a 1.5 m/s, bomba de calor); convección natural va mucho más lento, sin corregir.
4. **Sin temperaturas ni flujos.** No tiene balance de energía → no entrega T_producto,
   T_aire ni flujos de calor (de ahí que en P7 se viera "vacío" al lado del TD).
5. **Desacoplado de los pipelines transitorio/multidía/anual** (solo existía en Constantes).

**Qué aportaba vs el TD:** en teoría, especificidad empírica del producto (cinética medida)
y un ancla de validación. Tal como estaba implementado (punto único, T pico, sin corregir v,
solo en Constantes), aportaba poco y se leía como roto. **Decisión del usuario:** eliminarlo y
quedarse con el TD, que es físicamente completo e **independiente** de capa fina (lee
`propiedades_basicas` + `isoterma.gab` + geometría; nunca toca los bloques `capa_fina:`).

## 167. Alcance de la eliminación (quirúrgica)

Profundidad **quirúrgica** (decisión del usuario): borrar motor + UI + dispatcher + tests del
motor, pero **conservar** los campos `modo_calculo`/`modelo_capa_fina`/`modelo_isoterma` como
vestigiales para back-compat de snapshots. **No tocar** los bloques `capa_fina:` de los
catálogos (dato muerto, cero riesgo).

- **`calculos/camara_calc.py`**: borrados `calcular_tiempo_secado_estatico`, `evaluar_MR`,
  `calcular_X_eq_gab`, `_interpolar_params_cf` y la dataclass `ResultadosCamara`. `calcular_camara`
  ahora delega siempre en `_calcular_termodinamico`. Docstring del módulo reescrito.
- **`core/camara.py`**: `Camara.__post_init__` coacciona `modo_calculo == "capa_fina"` →
  `"termodinamico"` (back-compat). Quitadas la validación `MOD_CAPA_FINA_NO_DISPONIBLE` y la
  advertencia `PROD_CALIDAD_DATOS_BAJA` (validaban un campo ya no consumido). Conservadas la
  validación de isoterma (la usa el TD) y la advertencia de espesor de bandeja (renombrada la
  constante a `_ESPESOR_MAX_BANDEJA_M`, mensaje motor-agnóstico).
- **`calculos/balance_global.py`**: `resumen_camara` simplificado a la única firma
  (`ResultadoMotorTermodinamico`); quitados el import y el alias del tipo capa fina.
- **`ui/p4_camara.py`**: quitado el `st.radio` de motor (modo siempre `termodinamico`), el
  selector "modelo cinético de capa fina" (se conserva `modelo_cf` vestigial para round-trip),
  `_resumen_resultado_capa_fina`, la rama `"capa_fina"` del discriminador de horizonte, el
  import e `isinstance(res, ResultadosCamara)`.
- **`ui/p7_resultados.py`**: borrada `_fig_drying_curve` y las 4 ramas `else` de capa fina de
  las firmas de display (reporte, snapshot, dashboard, tabla); el `st.info` de supuestos.
- **Tests**: borrado `test_camara_calc.py`; podados `test_camara_dispatcher.py`,
  `test_psicrometria.py` (integración capa fina) y `test_core/test_camara.py`
  (`MOD_CAPA_FINA_NO_DISPONIBLE` + advertencia de calibración). Los 2 `xfail(strict=True)` que
  dependían de `MOD_CAPA_FINA_NO_DISPONIBLE` (tomate sin GAB, charqui carne sin isoterma)
  ahora **pasan** (los productos tienen fallback escalar de X_eq → instancian y emiten
  `PROD_ISOTERMA_FALLBACK` / `INIO_PRODUCTO_CARNE_SIN_ISOTERMA`): se les quitó el marcador.

## 168. Fixtures de test re-dimensionadas (efecto colateral)

Varios tests end-to-end usaban fixtures con `modo_calculo="capa_fina"` + producto manzana, que
**siempre** convergían (brentq). Con el motor único TD, esa config no alcanza X_obj (manzana a
X_obj=0.15 con su GAB no llega; `t_secado_s=None`). Se re-dimensionaron las fixtures de
`test_balance_global.py::proyecto_armario_completo` y
`test_barrido_parametrico.py::proyecto_completo` a una cámara chica de flujo activo con **yacón**
(GAB real), que converge bajo TD en todo el rango de caudales barridos (verificado: 53 h a
caudal 0.02, 29 h a 0.06, con I_g=800). Mocks de `test_catalogo_kpis_barrido.py` migrados a la
firma TD (`status`/`masa_evaporada_total_kg`).

## 169. Verificación

- Suite: **872 passed, 0 failed, 0 xfailed**.
- `black --check` sobre los 11 archivos editados: limpio.
- `ruff`: sin errores nuevos introducidos (`camara_calc.py` limpio; los F401 que persisten en
  `balance_global`/p4/p7 son deuda pre-existente, fuera del diff de esta tarea).
- Back-compat: `Camara(modo_calculo="capa_fina").modo_calculo == "termodinamico"`.
- AppTest: las 7 secciones (incl. P4 y P7, que tuvieron cirugía estructural) renderizan sin
  excepción.

## 170. Deuda técnica — campos vestigiales de capa fina

La eliminación fue quirúrgica: el **cálculo** ya no usa capa fina, pero quedaron campos/datos
en el modelo de datos para no romper snapshots `.json` viejos ni los ~13 archivos de test que
los construyen. Estado preciso de cada uno (no todos están igual de muertos):

| Símbolo | Estado | Quién lo lee hoy |
|---|---|---|
| `Camara.modo_calculo` (`core/camara.py:526`) | **Vestigial de comportamiento** | Se lee en `operacion_anual_camara`, `balance_global`, `p7`, `reporte`, pero todos preguntan `== "termodinamico"` (siempre true). Se serializa y se muestra. `__post_init__` coacciona `"capa_fina"`→`"termodinamico"`. |
| `CargaProducto.modelo_capa_fina` (`core/camara.py:411`) | **Vestigial puro** (pasajero 100%) | Nadie lo lee para calcular. Solo se serializa, se reconstruye en `_build_camara`, y se imprime en el reporte PDF. |
| `CargaProducto.modelo_isoterma` (`core/camara.py:412`) | **Semi-vestigial** | **Sí** lo consumen la validación `MOD_ISOTERMA_NO_DISPONIBLE` (`core/camara.py:563`) y las advertencias (`:825`). Pero el TD hardcodea `"gab"` y lo ignora en el cálculo. Default `"gab"` → coherente. |
| Bloques `capa_fina:` en catálogos | **NO inerte** | `_modelos_disponibles()` los lee y `p4._productos_disponibles()` (`p4_camara.py:81`) los usa para **filtrar qué productos aparecen en el selector de P4**. El TD no usa los `k,n`, pero borrarlos **sacaría productos del dropdown**. |
| `core/resultados.py::ResultadosCamara` (BloqueResultados) | **Inerte** | Placeholder tipado nunca poblado con sus campos (el resultado del motor se asigna directo). |

**Plan de limpieza total (opcional, riesgo creciente) — NO hacer salvo pedido:**

1. Borrar `modelo_capa_fina` (el más fácil; nadie lo lee). Toca su def, la serialización
   (`p4_camara` `_json/_from_json`), el reporte PDF y los constructores en tests.
2. Decidir `modelo_isoterma`: o se elimina y la validación/advertencias pasan a hardcodear
   `"gab"`, o se conserva.
3. Cambiar el gate de productos de P4 para mirar `isoterma`/`propiedades_basicas` en vez de
   `capa_fina:`, y recién entonces poder borrar los bloques `capa_fina:` de los YAML.
4. Eliminar `modo_calculo` + el placeholder `ResultadosCamara` de `core/resultados.py`, con
   shim de back-compat para snapshots viejos (`modo_calculo:"capa_fina"` ignorado al cargar).

**Recomendación:** dejarlo como está. Es inerte para el cálculo, los snapshots cargan, y la
limpieza total tiene más superficie de riesgo (serialización + tests + UI) que beneficio. El
punto de mayor impacto visible con menor riesgo es el (1) si molesta ver "capa fina" en el
reporte/snapshot.

## 171. Otros pendientes

- Único pendiente de la hoja de ruta a 1.0: **modo industrial (`Tipologia.GRAN_ESCALA`)**.
- Mejoras UX/UI 25 (selector de idioma) y 26 (manual estilo SAM) de `docs/notas/mejoras.md`.
