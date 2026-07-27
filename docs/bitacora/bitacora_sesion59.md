# Bitácora — Sesión 59

Dos pendientes viejos del backlog, los dos heredados de S57. El primero se cerró
**sin escribir código**; el segundo resultó ser un problema de capas disfrazado de
problema de almacenamiento.

## 1. `h_w` de McAdams: decidido no corregir (ADR-006)

El pendiente decía que `h_w = 5.7 + 3.8·v` recibe el viento del contrato de `Clima`
(2 m desde S57) sin corregirlo a la altura del equipo, que está típicamente entre
0.5 y 1.5 m. Siete call sites en cinco módulos: colector Tipo 1, Tipos 2/3/4, pared
y techo de cámara, y film externo del caño maestro. La chimenea es la única que ya
corregía.

**Primero medir, después decidir.** Corriendo el solver real del colector Tipo 1 con
`v` y con `v·factor_altura`:

| z₀ | z_colector | factor | ΔT_salida | Δη | ΔQ_util |
|---|---|---|---|---|---|
| 0.05 | 1.5 m | 0.92 | +0.2/+0.3 K | +0.3 pp | +0.5/+0.9 % |
| 0.05 | 1.0 m | 0.81 | +0.4/+0.7 K | +0.8 pp | +1.2/+2.4 % |
| 0.05 | 0.5 m | 0.62 | +0.9/+1.6 K | +1.8 pp | +2.4/+5.3 % |
| 0.10 | 0.5 m | 0.54 | +1.1/+2.2 K | +2.4 pp | +3.1/+7.0 % |

Y el peso de `1/h_w` en la resistencia total de cada envolvente (v = 3 m/s), con el
ΔU que produce bajar `h_w` un 20 %:

| Envolvente | fracción de R | ΔU |
|---|---|---|
| Cámara, pared aislada 5 cm | 4 % | −0.6 % |
| Cámara, techo alveolar 6 mm | 25 % | −3.6 % |
| Cámara, chapa sin aislar | 32 % | −4.7 % |
| **Caño maestro, chapa desnuda** | **59 %** | **−8.4 %** |

**Decisión: no corregir.** McAdams no tiene altura de referencia —sale de Jürges
(1924), placa de 0.5 m en túnel de viento con velocidad de corriente libre— y el
scatter de esa familia de correlaciones es de ±30–50 % (Palyvos 2008 revisó ~90), así
que un factor de perfil de 0.8 cae dentro del ruido de la propia correlación.
Anteponerle un log-law riguroso sería precisión falsa. Además la literatura de la que
salen los `F_R·U_L` de contraste la aplica con el viento de estación meteorológica.

El sesgo tiene **un solo signo** y va a favor de la seguridad: sobrestima `h_w`,
sobrestima las pérdidas, subestima el rendimiento.

Queda registrado el contra-argumento por si el criterio cambia: **ISO 9806 exige medir
el viento a la altura del colector y paralelo a él**, así que los parámetros de ensayo
normalizados corresponden a la velocidad local. Si alguna vez se valida contra ensayos
propios bajo norma, conviene reabrir. También queda anotada la vía de menor costo
(altura de montaje con default 2 m ⇒ ningún resultado guardado se mueve) y la fórmula
del promedio del perfil sobre superficies extendidas.

**Lo importante del cierre:** el docstring de `perfil_viento.py` decía "todo consumidor
que necesite el viento a otra altura debe pasar por este módulo", regla que `h_w`
aparentaba violar. Ahora declara la excepción y por qué la regla aplica al viento como
variable atmosférica y no a la `v` empírica de una correlación de film. Sin eso, una
sesión futura "arregla" la incoherencia sin saber que fue deliberada.

Subproducto que vale por separado: **el caño maestro desnudo es mucho más sensible a
`h_w` de lo que uno esperaría** (59 % de la resistencia). Si el ΔT del caño no cierra
contra medición, ese es el primer parámetro a mirar, no la conducción.

## 2. `PoliticaRecarga` se persiste con el proyecto

### El problema, que estaba críptico en el backlog

Los cinco campos de `PoliticaRecarga` son decisiones del operador —hora de carga,
maniobra, espera activa, exigir pronóstico, umbral— o sea entradas del modelo, igual
que el espesor del aislante. Pero vivían así:

```
widgets de P4 → PoliticaRecarga(...) armada al vuelo dentro del `if calcular`
              → simular_anual(...) + session_state["p4_politica_recarga"]
```

Nunca tocaban `Proyecto`, que es lo único que se serializa. Se guardaba el prediseño
completo, se reabría al día siguiente, se recalculaba el año y **salía otro número que
el del reporte guardado, sin ningún aviso**: los widgets habían vuelto a sus defaults.
Con los dos campos de S58 el agujero se ensanchó, porque también se perdía la decisión
de mirar el pronóstico, que es la que más mueve el conteo de lotes.

La nota del backlog decía "no volver a meterla en `Camara` sin pensarlo", en referencia
a haber sacado `OperacionAnualConfig` de ahí en S57. Correcto, pero era una advertencia,
no un destino — por eso el ítem quedó abierto dos sesiones.

### El bloqueo real: una inversión de capas

No era "dónde guardarla". Era que **`PoliticaRecarga` estaba definida en la capa
equivocada**: en `calculos/simulacion_ventana.py`. Todo lo que entre a `Proyecto` vive
en `core/`; si `core/proyecto.py` importara de `calculos/`, el modelo de datos pasaría
a depender del motor numérico. El ítem no se podía resolver eligiendo un lugar porque
le faltaba un paso previo.

Y la clase ya tenía la forma exacta de una dataclass de `core/`: datos puros más
validación en `__post_init__` con códigos de error (`RECARGA_HORA_INVALIDA`,
`RECARGA_MANIOBRA_NEGATIVA`, `RECARGA_UMBRAL_NEGATIVO`). Estaba en `calculos/` por
accidente histórico: nació dentro del módulo de simulación en S57.

### Lo implementado

`core/operacion.py` nuevo, con `PoliticaRecarga` + `a_dict()`/`desde_dict()`.
`simulacion_ventana` la reexporta (los imports existentes siguen andando). Cuelga de
`Configuracion.politica_recarga`, junto a `ventana_inicio`/`ventana_fin`, que son
parámetros de escenario de operación igual que ella.

Tres consecuencias, dos de ellas no previstas al empezar:

1. **Viaja en el snapshot.** P7 la exporta en `json_cfg` y en el TXT;
   `_reconstruir_configuracion` la lee. Los snapshots anteriores no traen el bloque y
   caen a los defaults —que son los que esas corridas usaron de hecho—, así que se
   reproducen igual.

2. **La vigencia se simplifica.** `SECCIONES_ANUAL` ya incluía `"configuracion"` y
   `huella_entradas` expande dataclasses anidadas, así que la política entra sola. Se
   **eliminaron** el `extras={"politica": ...}` de `hash_entradas_anual`, la clave
   `p4_politica_recarga` de `session_state` y los helpers `politica_anual_guardada` y
   `extras_anual` de `vigencia.py`. Tres andamios que existían solo porque la política
   estaba fuera del proyecto.

3. **El modo VENTANA la obedece.** Esto no estaba en el backlog: `balance_global`
   llamaba a `simular_ventana(...)` sin política y `simular_ventana` llamaba a la rama
   BATCH sin pasarla, así que el encadenado de gran escala quedaba clavado en los
   defaults del motor **sin ningún widget que lo gobernara** — misma física que el
   anual, con la operación fija. Ahora la lee del proyecto. De paso recibe el ancla de
   hora local (el mismo `_hora_offset_local` que alinea el calendario del auxiliar) en
   vez de suponer que `t = 0` es medianoche local. El túnel semicontinuo la ignora a
   propósito: avanza columnas por cadencia, no encadena lotes.

### Dos gotchas de la UI

- **P1 pisaba la política en cada rerun.** P1 reconstruye `Configuracion` campo por
  campo, y en Streamlit **todas** las pestañas se renderizan en cada rerun, así que
  cualquier campo que no se propague explícitamente vuelve a su default. Es el mismo
  gotcha de `dataclasses.replace` que ya había mordido con el albedo en S36. Ahora la
  arrastra explícitamente, con el comentario que explica por qué.
- **Cuándo se escribe.** Primero la escribí solo al apretar "Calcular año"; después vi
  que P4 asigna `proyecto.camara` en **cada rerun** (línea 2855) y la alineé con esa
  convención. Mover un widget tiene que marcar el año calculado como desactualizado en
  el acto, igual que cambiar la geometría, y el .json exportado tiene que decir lo mismo
  que muestran los widgets.

### Tests

`tests/test_core/test_operacion.py` nuevo (validación, serialización ida y vuelta,
snapshot parcial, claves desconocidas, `default_factory` no compartida). En
`test_carga_proyecto.py` la fixture del round-trip pasó a tener los cinco campos
distintos del default —si se perdieran, volverían a 8:00 / 1 h / on / 8 MJ— más un test
de snapshot viejo sin el bloque y otro de política corrupta. En `test_ventana_glue.py`,
tres tests de que el modo VENTANA obedece la política (y de que el semicontinuo la
ignora). En `test_p4_render_smoke.py`, dos AppTest: que los widgets arrancan de la
política guardada y que mover uno actualiza el proyecto.

El smoke de los widgets se verificó con una mutación deliberada (`value=1.0` en vez de
`value=pol_guardada.maniobra_h`): falla como debe. Sin esa comprobación un smoke test
que solo mira `not at.exception` puede pasar sin ejercitar nada.

## 3. Cierre de los dos pendientes que dejó §2

El usuario pidió los dos.

**Widgets de política en modo VENTANA.** El bloque de widgets se extrajo de
`_render_operacion_anual` a `_render_politica_recarga(proyecto) -> bool`, que además es
quien escribe la política en el proyecto. Se renderiza en ANUAL (como antes) y en
VENTANA cuando `_ventana_encadena_lotes(proyecto)` — o sea gran escala en subtipo BATCH.
En VENTANA va sin botón: el cálculo se dispara en P7. El túnel semicontinuo queda
afuera a propósito (avanza columnas por cadencia, no recarga) y CAJA/ARMARIO en VENTANA
también, porque caen al transitorio multidía, que no encadena. Dos claves i18n nuevas
(`p4.ventana_operacion.titulo/.caption`) en los tres idiomas.

**Operación asumida en el reporte PDF.** El PDF mostraba `dias_salteados_pronostico`
sin decir contra qué umbral, ni a qué hora se carga, ni cuánto dura la maniobra — o sea
que los números no eran reproducibles. Nuevo `_bloque_politica_recarga`, insertado en la
sección anual y en la de ventana (solo BATCH), que además dice que el pronóstico es
perfecto. La política sale del snapshot completo vía `_politica_snapshot`, que la busca
bajo `configuracion` — no hizo falta tocar el snapshot del resultado. Nueve claves nuevas
en `reporte.operacion.*` × 3 idiomas.

Con la espera desactivada el bloque **no** informa hora de carga: no significa nada, y
en su lugar declara que el resultado es la cota superior de producción.

`tests/test_ui/test_reporte_operacion.py` nuevo (15 tests): el bloque en los tres
idiomas, el caso sin política (snapshot viejo), el de encadenado inmediato, y el cableado
sección → bloque incluyendo que el semicontinuo no lo muestre.

**Por qué no se verifica sobre los bytes del PDF:** las fuentes van subseteadas y el
texto no se recupera descomprimiendo los streams (se probó). El PDF completo sí se generó
end-to-end sin excepción con el bloque adentro; el seam que los tests cubren es
sección → bloque, que es donde puede romperse el cableado.

## Cierre

Suite: **1715 passed + 1 skip** (desde 1677 al abrir la sesión, +38). Ruff y black
limpios. Nada commiteado: queda todo en el working tree para que el usuario lo pruebe en
local.

Se regeneraron además las notas de módulo de Obsidian
(`scripts/generar_notas_obsidian.py`): estaban paradas hacía varias sesiones — entraron
37 módulos que faltaban (todo `clima_medido`, `simulacion_anual`, `simulacion_ventana`,
`perfil_viento`, `huellas`, `vigencia`, `operacion`, el manual…) y se borró la de
`calculos/operacion_anual_camara`, eliminado en S57. De paso se corrigió en
`docs/arquitectura.md` una afirmación que estaba mal desde S38: decía que la cámara
tenía "dos motores físicos (`capa_fina`, `termodinamico`)" cuando el de capa fina se
eliminó en esa sesión.

## Pendientes

- **Pronóstico de persistencia** como alternativa al perfecto (correr las dos y restar
  da el valor de tener buen pronóstico).
- **Modo anual del túnel semicontinuo**: rechazado con `ANUAL_SEMICONTINUO_NO_SOPORTADO`.
- `validacion/validacion_cruzada_yacon.py` sigue roto desde S38.
- **Verificación pendiente del usuario**: la corrida anual de Salta en el Space con la
  presión corregida.

## Ver también

- [[docs/bitacora/bitacora_sesion58]]
- [[docs/decisiones]] — ADR-006
- [[docs/tareas]]
- [[CHANGELOG]]
