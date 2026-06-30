# 07 · Resultados — integración, reporte y flujo de trabajo

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: qué toma, hace y entrega la pestaña P7; el flujo de trabajo del usuario;
> la carta psicrométrica; las corridas paramétricas; y la exportación de
> resultados y componentes.

---

## 1. P7 como fuente de verdad

Las pestañas P1–P6 **configuran** el sistema (cada una escribe en el objeto
`Proyecto` central de `st.session_state`). **P7 es la que resuelve todo de forma
acoplada** y es la **fuente de verdad**: las vistas previas de las pestañas
intermedias (botones "Calcular X") usan heurísticas o modelos lineales
preliminares; el número final, con el lazo de Picard completo, sale de P7.

**Flujo conceptual:**
```
P1..P6  →  Proyecto (session_state)  →  P7: balance global acoplado  →  Dashboard + Reporte
```

---

## 2. Qué toma — verificación de coherencia

Antes de calcular, P7 verifica las **invariantes cruzadas** del proyecto
(`verificar_coherencia_proyecto`): p. ej. CAJA no admite colector externo ni motor
y exige techo translúcido; auxiliar en SERIE_POSCOLECTOR exige colector; motor
exige cámara; anual no aplica a CAJA. Los errores se muestran y bloquean el
cálculo inconsistente.

También fija la **presión representativa** del emplazamiento (media anual del
clima si hay; ISA por altitud si no; 101325 Pa de fallback) — un único valor para
colector, cámara y psicrométricas.

---

## 3. Qué hace — tres modos de cálculo

P7 enruta a uno de **tres puntos de entrada** de `balance_global.py` según el modo
de análisis:

| Modo | Función | Forzantes |
|---|---|---|
| **Constantes** | `calcular_todo(proyecto, T_amb, I_g, v_viento, T_ent, HR)` | condiciones representativas únicas |
| **Transitorio** | `calcular_todo_transitorio(proyecto, clima, dia_criterio)` | horizonte horario (día de diseño / multidía) |
| **Ventana** | `calcular_todo_ventana(proyecto, clima_df)` | lapso real `[inicio, fin]` (gran escala / multidía) |

Los tres encadenan **colector → auxiliar → cámara** y, si hay chimenea, cierran el
**lazo natural por Picard** (doc 05). La armadura de forzantes del aire
(`armar_forzantes_aire` / `armar_forzantes_ventana`) construye T_ent, ω_ent, ṁ,
GHI sobre el techo de cámara y **POA sobre el plano del colector**.

### 3.1 Sugerencia automática de irradiancia (modo Constantes)

Para no obligar al usuario a inventar un valor "representativo", P7 sugiere
condiciones desde el clima descargado (`_sugerir_condiciones`): toma el
**quantile 90 de la POA** representativa (transposición Liu-Jordan) y el
quantile 75 de T_amb. Si no hay POA, cae al q90 de GHI (conservador).

---

## 4. Qué entrega — dashboard integrado

El resultado (`ResultadosCompletos`) integra el **balance energético completo**:

$$
E_{total}=E_{solar,util}+E_{auxiliar}+E_{motor},
\qquad
E_{secado}=m_{agua}\,L_v
$$
$$
\text{COP}_{secado}=\frac{m_{agua}\,L_v}{E_{total}},
\qquad
\text{Fracción solar}=\frac{E_{solar}}{E_{solar}+E_{auxiliar}}
$$

más **tiempo de secado**, **masa de producto seco** ($m_{tot}/(1+X_0)$),
**rendimiento de masa**, las salidas de cada subsistema (colector, auxiliar,
cámara, chimenea) y las advertencias/errores acumulados. El dashboard muestra
métricas, un **Sankey** simplificado de energía y, según el modo:

- **Transitorio:** trayectorias horarias (T, X, flujos).
- **Ventana (gran escala):** **dashboard de producción** — kg secos, tasa de
  régimen (kg/día), leña, y **perfil espacial del túnel** en semicontinuo.
- **Anual:** si P4 calculó operación anual, panel de detalle mensual.

---

## 5. Carta psicrométrica del proceso (S43)

Una salida muy visual y "que habla" al público técnico: la **carta psicrométrica
corregida por altitud** que traza el proceso real del aire
(`calculos/carta_psicrometrica.py`, sin librería externa, sobre `psicrometria.py`):

```
Ambiente → [colector: calentamiento sensible, ω cte] → [auxiliar: +T, ω cte]
        → [cámara: secado] → salida
```

El tramo de cámara es **adiabático o no-adiabático según emerge del balance** (no
se impone): si la cámara pierde calor a las paredes, el proceso se aparta de la
isentálpica. El estado representativo se toma al **mediodía solar**. En el **túnel
semicontinuo** se traza el **camino del aire por zonas** a contracorriente.

---

## 6. Corridas paramétricas (barridos)

`calculos/barrido_parametrico.py` permite **comparar diseños** barriendo un
parámetro (geometría, caudal, materiales…) y midiendo KPIs (t_secado, COP,
fracción solar, T_salida…):

- `aplicar_parametro` muta un campo del proyecto vía `dataclasses.replace`
  (path tipo `colector.unidad.velocidad_diseno_ms`).
- `correr_barrido(BarridoConfig)` clona el proyecto (sin re-descargar clima),
  aplica cada valor, despacha el motor correspondiente y extrae KPIs
  (`ResultadosBarrido` con puntos convergidos/no convergidos).

Sirve para responder "¿qué pasa si duplico el área de colector / cambio el
caudal / uso doble cubierta?" sin rehacer la configuración a mano.

---

## 7. Exportación — resultados y componentes

P7 exporta el proyecto completo en tres formatos:

| Formato | Qué | Para qué |
|---|---|---|
| **JSON** | snapshot serializado del `Proyecto` + resultados | **reproducible**: se puede recargar y re-correr idéntico |
| **TXT** | informe de texto plano | lectura rápida / pegar en mail |
| **PDF** | reporte con portada institucional, figuras (P2/P3/P4/P7) y tablas | **entregable** que el usuario se lleva (reportlab + kaleido) |

El JSON serializa **cada componente** (colector, cámara, auxiliar, motor/chimenea)
vía los helpers `_json_config_*` de cada pestaña — así se puede versionar un
diseño, compartirlo o reabrirlo. El PDF es el "wow" tangible para cerrar la demo.

---

## 8. Flujo de trabajo del usuario (de punta a punta)

1. **P1** — tipología (caja/armario/gran escala) y modo de análisis.
2. **P2** — lat/lon → descarga NASA POWER → POA vs GHI.
3. **P3** — colector: tipo, materiales, geometría, banco → evaluación gráfica.
4. **P4** — cámara: geometría, pared, producto, carga, bandejas.
5. **P5** — auxiliar (opcional).
6. **P6** — motor o chimenea → ΔP del sistema.
7. **P7** — corrida acoplada completa → dashboard + carta psicrométrica +
   exportar JSON/TXT/PDF.

El flujo es **guiado pero flexible**: cada pestaña escribe en el proyecto central;
se puede ir y volver, y P7 integra todo con el lazo iterativo.

---

## 9. Highlights de implementación (a nivel código)

| Qué | Dónde |
|---|---|
| Orquestación (3 modos) | `calculos/balance_global.py::calcular_todo`, `calcular_todo_transitorio`, `calcular_todo_ventana` |
| Resultado integrado | `balance_global.py::ResultadosCompletos` (COP, fracción solar, energías) |
| Coherencia cruzada del proyecto | `balance_global.py::verificar_coherencia_proyecto` |
| Forzantes del aire | `balance_global.py::armar_forzantes_aire`, `armar_forzantes_ventana` |
| Sugerencia de irradiancia (q90 POA) | `ui/p7_resultados.py::_sugerir_condiciones` |
| Dashboard y Sankey | `ui/p7_resultados.py` |
| Carta psicrométrica | `calculos/carta_psicrometrica.py::estados_proceso` |
| Corridas paramétricas | `calculos/barrido_parametrico.py::correr_barrido` |
| Reporte PDF | `ui/reporte.py` (reportlab + kaleido) |
| Export JSON/TXT | `p7_resultados.py::_json_resultados_completo`, `_texto_resultados_completo` |

**Puntos a destacar en la charla:**
1. *P7 es la fuente de verdad*: integra todo con Picard, no son números sueltos
   de cada pestaña.
2. *Balance energético cerrado*: COP, fracción solar, energías solar/auxiliar/motor.
3. *Carta psicrométrica con adiabaticidad emergente* — vistosa y técnica.
4. *Corridas paramétricas* para comparar diseños sin rehacer config.
5. *Tres entregables* (JSON reproducible, TXT, PDF institucional).

---

## Referencias

- Augustus Leon et al. — eficiencias de secado (drying/pickup/térmica/total).
- ASHRAE / Threlkeld — psicrometría (carta corregida por altitud).
- reportlab + kaleido — generación del reporte PDF.
