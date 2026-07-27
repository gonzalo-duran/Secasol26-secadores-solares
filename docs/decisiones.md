# Registro de decisiones de diseño (ADR)

Decisiones arquitectónicas relevantes de **Secasol 26**. Cada entrada anota
contexto, opciones, decisión y consecuencias. Para la arquitectura general ver
[[docs/arquitectura]]; para las convenciones de trabajo ver [[CLAUDE]].

> El registro histórico cronológico vive en `docs/bitacora/`. Esta nota resume
> las decisiones estructurales para navegación rápida desde Obsidian.

---

## ADR-001 — Separación estricta de capas (sin Streamlit en `core/`/`calculos/`)

- **Contexto:** la lógica física debía ser testeable y reutilizable fuera de la UI.
- **Opciones:** (a) acoplar cálculo a Streamlit; (b) separar capas con frontera dura.
- **Decisión:** `core/` y `calculos/` no importan `streamlit`; la UI es la única
  capa que lo usa. `validacion/` puede usar `core`/`calculos` pero no `ui`.
- **Consecuencias:** los motores se validan con pytest sin servidor; la UI es
  reemplazable. Cualquier import de `streamlit` fuera de `ui/` es un error.

## ADR-002 — SI estricto en el núcleo; conversión única en `unidades.py`

- **Contexto:** mezclar unidades (°C/K, %, fracción) genera errores difíciles de rastrear.
- **Decisión:** todo lo que circula por `core/`/`calculos/` está en SI estricto.
  La única conversión de unidades (y de convenciones de ángulos) vive en
  `ui/componentes/unidades.py`.
- **Consecuencias:** los motores asumen K, Pa, fracciones, kg/s. Toda entrada del
  usuario se convierte en la frontera de UI.

## ADR-003 — `Chimenea` como componente top-level (S30)

- **Contexto:** originalmente la chimenea era subcomponente del `Colector`, lo que
  impedía chimenea solar en tipología CAJA (sin colector).
- **Decisión:** `Chimenea` pasa a ser top-level en `Proyecto`. Los snapshots
  antiguos con `colector.chimenea` se migran en la deserialización.
- **Consecuencias:** convección natural disponible en todas las tipologías.

## ADR-004 — Motor termodinámico de cámara por defecto (S34)

- **Contexto:** el modo `capa_fina` usa cinéticas empíricas con `k` constante; el
  modo `termodinamico` resuelve el balance acoplado calor-masa.
- **Decisión:** `modo_calculo = "termodinamico"` como valor por defecto.
- **Consecuencias:** resultados más físicos; `t_secado_s` puede ser `None` si no
  converge. Las divergencias de firma se abstraen en helpers de balance y P7.

## ADR-005 — Deploy en Hugging Face Spaces vía GitHub Action (S33)

- **Contexto:** repo de GitHub privado; necesidad de que colegas accedan a la app
  sin instalar nada ni ver el código.
- **Decisión:** deploy automático a HF Spaces (Docker + Streamlit) en cada push a
  `main`. Un push a `main` actualiza producción.
- **Consecuencias:** cambios que no deben llegar a producción van en otra rama.

## ADR-006 — `h_w` de McAdams usa el viento del contrato (2 m) sin corregir a la altura del equipo (S59)

- **Contexto:** desde S57 el viento de `Clima.WS_ms` está referido a **2 m** y
  `calculos/perfil_viento.py` es la fuente única para trasladarlo a otra altura. La
  chimenea lo usa (el extractor eólico va con `v²` en el tope). Los siete call sites de
  McAdams `h_w = 5.7 + 3.8·v` —colector Tipo 1, Tipos 2/3/4, pared y techo de cámara, y
  film externo del caño maestro— siguen recibiendo el viento de 2 m sin corregir, aunque
  el equipo esté típicamente entre 0.5 y 1.5 m sobre el suelo. Quedó anotado como
  pendiente de modelo, deliberadamente fuera del fix de S57.
- **Magnitud del efecto** (medida, no estimada — solver real del colector y fracciones de
  resistencia de cada envolvente):
  - **Colector Tipo 1** corrigiendo de 2 m a la altura de montaje: con z₀ = 0.05 m,
    z = 1.5 m → ΔT_salida +0.2/+0.3 K y Q_util +0.5/+0.9 %; z = 1.0 m → +0.4/+0.7 K y
    +1.2/+2.4 %; z = 0.5 m → +0.9/+1.6 K y +2.4/+5.3 %. El peor caso explorado
    (z₀ = 0.10 m, z = 0.5 m, v = 5 m/s) da +2.2 K y +7 %.
  - **Envolventes**, peso de `1/h_w` en R_total a v = 3 m/s y ΔU si `h_w` baja 20 %:
    pared de cámara aislada 5 cm → 4 % y −0.6 % (irrelevante); techo alveolar 6 mm →
    25 % y −3.6 %; chapa sin aislar → 32 % y −4.7 %; **caño maestro de chapa desnuda →
    59 % y −8.4 %** (el más sensible de todos).
  - El sesgo tiene **un solo signo**: el equipo está casi siempre por debajo de 2 m, así
    que el modelo sobrestima `h_w`, sobrestima las pérdidas y **subestima el
    rendimiento**. El error va a favor de la seguridad del prediseño.
- **Opciones:** (a) altura de montaje por equipo, ruteada por `perfil_viento`, con
  default neutro de 2 m; (b) corregir solo donde el efecto es real (caño maestro, techo
  translúcido, chapa sin aislar); (c) corregir los siete sitios con alturas físicas
  honestas; (d) no tocar y documentar.
- **Decisión:** **(d) no corregir.** McAdams no tiene altura de referencia: sale de
  Jürges (1924), una placa de 0.5 m en túnel de viento con velocidad de corriente libre
  sobre la placa; no hay ninguna altura atmosférica en la correlación. El scatter de esa
  familia de correlaciones es de ±30–50 % (Palyvos 2008 revisó ~90), de modo que un
  factor de perfil logarítmico de 0.8 cae **dentro del ruido de la propia correlación** —
  anteponerle un log-law riguroso sería precisión falsa. Además toda la literatura solar
  de referencia (Duffie & Beckman, Klein, HWB) la aplica con el viento de estación
  meteorológica, así que hay una calibración implícita en ese uso, y los parámetros
  `F_R·U_L` contra los que se contrasta el modelo salen de ahí.
- **Consecuencias:**
  - `perfil_viento.py` NO es fuente única para `h_w`, y eso es **deliberado**: la regla
    "todo consumidor pasa por este módulo" aplica al viento como variable atmosférica
    (chimenea, ingesta), no a la `v` empírica de una correlación de film. El docstring
    del módulo y los de los cuatro consumidores anotan la excepción para que no se
    "arregle" la incoherencia en una sesión futura.
  - El contra-argumento queda registrado por si el criterio cambia: ISO 9806 exige medir
    el viento **a la altura del colector y paralelo a él**, así que los parámetros de
    ensayo corresponden a la velocidad local. Si en algún momento se valida el modelo
    contra ensayos normalizados propios, conviene revisar esta decisión.
  - Si se reabre, la opción (a) es la de menor costo: default 2 m ⇒ ningún resultado
    guardado se mueve, y el usuario declara la altura real cuando la sabe. Para
    superficies extendidas verticales lo riguroso no es `v(z)` puntual sino el promedio
    del perfil sobre la altura, `v̄ = v_ref·[ln(H/z₀) − 1 + z₀/H] / ln(2/z₀)`.

## ADR-007 — En un secador pasivo el caudal es un **resultado**, no un dato (S61)

- **Contexto:** hasta S60 un secador sin ventilador ni chimenea —el cajón o armario con
  bocas, caso de mucha aplicación— corría con `camara.flujo.caudal_masico_kg_s`, un número
  que carga el usuario. Pero en un equipo pasivo nadie impone el caudal: lo fija el
  equilibrio entre el tiro térmico de la columna de aire caliente y la resistencia del
  circuito. El campo existía porque el modelo nació pensando en convección forzada.
- **Decisión:** cuando no hay ventilador y el lazo tiene alguna resistencia declarada
  (chimenea **o** bocas de la cámara), el caudal lo resuelve `caudal_natural_kgs` y el valor
  del usuario pasa a ser **referencia de escalado**, no el caudal. Sin chimenea ni bocas se
  conserva el comportamiento previo (caudal constante), para que ningún proyecto anterior
  cambie de resultado.
- **Corolario de interfaz:** en un cajón pasivo sin colector, el caudal de referencia se pide
  en **renovaciones de aire por minuto** y no en kg/s. Un caudal másico no tiene anclaje
  cuando nadie lo impone; renovaciones/min es la unidad con la que se dimensiona ventilación
  y tiene rango físico conocido.
- **Magnitud del efecto** (medida sobre el cajón del usuario, clima real de Salta,
  5-7/7/2023):
  - El default de fábrica (0.030 kg/s) equivale a **11.6 renovaciones/min**; el lazo natural
    resuelve **0.94**. Un factor **12**.
  - Con ese default la previa de P4 daba **33.3 h** de secado contra **63.8 h** de P7 (~92 %
    de diferencia). Con el anclaje de 1 renovación/min, el error en agua evaporada baja de
    **+28 %** a **+0.9 %**.
  - El mini-Picard de punto de diseño da 1.14 / 1.83 / 2.13 ren/min en tres geometrías ⇒ el
    rango de un cajón pasivo es **1–2 renovaciones/min**.
- **Consecuencias:**
  - El caudal de referencia sigue haciendo falta: ancla el escalado cuadrático de
    `ΔP_resto(m)` y actúa de respaldo en las horas sin tiro. Por eso se conserva editable,
    con otro rótulo, en vez de eliminarse.
  - **Los pipelines de ventana y anual todavía no lo obedecen**: `armar_forzantes_ventana`
    usa el caudal de diseño. Es una limitación previa (la chimenea también se ignoraba ahí),
    pero ahora es visible desde la UI y hay que resolverla.
  - La conversión renovaciones → kg/s usa ρ a la **T y presión del sitio**, no 1.2 kg/m³ de
    manual: en Salta a 10 °C y 1187 m el aire pesa 1.08 kg/m³.
  - Nada de esto está validado contra datos medidos de un cajón pasivo, y los coeficientes
    de pérdida de boca son de manual (contracción de canto vivo / descarga de chorro).

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
