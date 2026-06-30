# Bitácora — Sesión 46 (2026-06-26)

**Tema:** Resolución de **discrepancia local ↔ remoto (Hugging Face)** detectada al probar
Secasol post-seminario, + **bug de carga de `.json` en HF** (403). Dos fallos de
**infraestructura de despliegue** (no de física ni de lógica de cálculo), ambos cerrados.

**Estado al cierre:** Causa raíz #1 (entorno sin pinnear) corregida y **confirmada en
producción** (commit `df899f2`, pusheado → desplegado en HF). Causa raíz #2 (XSRF tras el
proxy de HF) corregida vía Dockerfile del Space (lado HF) y **confirmada**: la carga de
`.json` ya funciona en el remoto. Suite **1042 passed** (sin cambio de conteo — todo lo
tocado es config/infra/UI aditiva). Versión bump a **0.14.1**.

---

## Problema 1 — Discrepancia local ↔ remoto en agua evaporada de cámara

### Síntoma
El mismo prediseño (ARMARIO, modo VENTANA, Salta 2009, manzana 6 kg, ventana 7 días) daba
resultados de cámara **cualitativamente distintos** entre el repo local y el Space:

| | Local (correcto) | Remoto (incorrecto) |
|---|---|---|
| Agua evaporada | 4.77 kg | **0.26 kg** |
| Status | `X_obj_alcanzado` | `t_max_alcanzado` |
| X final | 0.15 (seco) | **4.36** (casi sin secar) |
| T_max producto | 45 °C | **92 °C** |
| Horas HR>95% | 0.1 h | 7.6 h |

Caso reproducible guardado en `tests/pruebas de coincidencia/` (JSONs por sección +
prediseño completo + reporte PDF).

### Diagnóstico (descarte sistemático)
1. **Código — descartado.** El Space corre lo desplegado el 2026-06-22 (commit `125d8c4`);
   `git diff 125d8c4..HEAD -- Secasol.py ui calculos core assets catalogo requirements.txt`
   = **vacío**. Los commits posteriores (docs/licencia) no disparan deploy porque el workflow
   solo copia esos directorios, no `docs/`. La fecha del último auto-deploy en HF
   (2026-06-22 20:48 UTC, vía API pública) lo confirma.
2. **Clima — descartado.** Re-descarga fresca de NASA POWER 2009 = **bit-idéntica** al caché
   parquet (`max|Δ| = 0` en T/HR/GHI/presión). NASA no revisó el dato; pvlib 0.15.1 lo parsea
   igual. (Experimento: backup del caché → `obtener_clima(..., forzar_descarga=True)` → diff →
   restaurar.)
3. **Inputs — descartados.** Confirmado por el usuario: ṁ cámara 0.041 kg/s, colector v=1.5 m/s,
   250 cm²/canal, 37.5 l/s/unidad. Idénticos en ambas corridas.
4. **Entorno — CAUSA RAÍZ.** Local: Python **3.14.6**, numpy 2.4.4 / scipy 1.17.1 / pandas
   3.0.2 / pvlib 0.15.1. HF: Python **3.13.5** (`FROM python:3.13.5-slim`) + librerías **sin
   pinnear** (`requirements.txt` con `>=`). Cada rebuild de HF resolvía pip a lo más nuevo de
   esa fecha → stack distinto del local. El solver de cámara (`solve_ivp`/`fsolve`) con
   librerías distintas convergía a una solución basura (producto a 92 °C sin secar). Una
   diferencia de 18× **no** es redondeo: es cualitativa, propia de un cambio de comportamiento
   de versión.

### Fix (commit `df899f2`, pusheado → deploy HF)
- **`requirements.txt` pinneado con `==`** a las versiones del entorno local (numpy 2.4.4,
  scipy 1.17.1, pandas 3.0.2, pvlib 0.15.1, streamlit 1.57.0, plotly 6.7.0, pyarrow 24.0.0,
  pyyaml 6.0.3, reportlab 4.5.1, kaleido 0.2.1). Seguro en Python 3.13.5.
- **Panel "🔧 Entorno"** en el sidebar (`Secasol.py::_diagnostico_entorno()`): muestra Python +
  versiones de librerías, para comparar local vs remoto de un vistazo en el futuro.

### Confirmación
Tras el redeploy, el Space da **4.77 kg** (correcto). Como HF **sigue en Python 3.13.5** (no se
tocó) y ahora anda, la causa era **las versiones de librería**, no el Python. **Caso cerrado.**

---

## Problema 2 — Carga de `.json` en HF falla con `AxiosError: 403`

### Síntoma
Subir un `.json` por el `file_uploader` de cualquier pestaña (P3–P6) mostraba en el navegador
`AxiosError: Request failed with status code 403`. Anda en local, falla en HF, **igual en las
5 pestañas**.

### Diagnóstico
**No es el código de carga** (que ni se ejecuta): el 403 es el POST del navegador para subir el
archivo, rechazado por el servidor **antes** de procesarlo. Causa: la **protección XSRF** de
Streamlit, que tras el reverse-proxy de Hugging Face bloquea la subida del `file_uploader`.
Problema conocido de "Streamlit + HF Spaces + file_uploader". El patrón idéntico de fallo en las
5 pestañas (mismo helper `parsear_json_seccion`, Python puro sin filesystem) confirmó que el
problema era de servidor, no de lógica.

### Fix (lado HF — Dockerfile del Space)
Se agregó el flag `--server.enableXsrfProtection=false` al `ENTRYPOINT` del Dockerfile del Space
(en una sola línea — partirlo en dos rompe el parser de Docker). El deploy desde GitHub
**preserva** el Dockerfile del Space (`cp Dockerfile /tmp/...`), así que el cambio **persiste**
en los próximos push. **Seguro:** app pública de prediseño, sin login ni datos sensibles.

### Confirmación
La carga de `.json` ya funciona en el remoto. **Caso cerrado.**

---

## Aprendizajes transversales
- El deploy a HF **no es hermético**: clima en vivo (no copia el caché), librerías sin pinnear
  (hasta este fix), y el Dockerfile vive del lado del Space (no del repo). Ante "anda en local,
  no en el remoto", **mirar primero el panel 🔧 Entorno** y comparar versiones.
- Tres confusiones honestas en el camino antes de aislar la causa real (se culpó al caudal, luego
  se descartaron las librerías por "diferencia demasiado grande"): el método correcto fue el
  **descarte sistemático con experimentos** (diff de clima, diff de código por rango de commits,
  confirmación de inputs con el usuario).

## Verificación
- **Suite: 1042 passed** (sin regresiones; conteo sin cambio — los cambios son config/infra/UI
  aditiva, sin lógica de cálculo).
- **black** + **ruff** limpios en `Secasol.py` y `requirements.txt`.
- Discrepancia de evaporación: **resuelta y confirmada en producción** (4.77 kg en HF).
- Carga `.json` en HF: **resuelta y confirmada**.

## Pendientes (heredados, post-seminario)
- Hermetizar más el deploy: copiar el caché climático al Space o embeber la serie en el JSON
  (hoy el clima se baja en vivo); evaluar versionar el Dockerfile en el repo.
- Subir el `FROM python:3.13.5` del Dockerfile del Space a 3.14 para igualar también el Python
  (no fue necesario para el bug, pero cierra la última asimetría de entorno).
- Los pendientes físicos de S45 (aire local en Tipos 2/3/4, refactor back-compat S38, ADITAL vs
  NASA real, etc.) siguen abiertos.
