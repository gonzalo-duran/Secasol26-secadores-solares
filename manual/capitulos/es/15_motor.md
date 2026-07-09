# 6 · Motor, ventilador y chimenea solar

Algo tiene que mover el aire a través del colector, la cámara y los ductos. Hay
dos caminos: **convección forzada** (un ventilador con motor eléctrico — más
control, más caudal, consume energía) o **convección natural** (una chimenea
solar que induce tiro térmico — sin electricidad, caudal menor y variable con
el sol). Esta sección dimensiona uno u otro a partir de la **pérdida de carga**
de todo el circuito.

## Elegir el accionamiento {#eleccion}

Reglas prácticas:

- **Forzada**: necesaria con lechos gruesos o flujo vertical (mucha pérdida de
  carga), bancos de colectores grandes, o cuando el proceso exige caudal
  estable. Es la opción segura en escala industrial.
- **Natural**: atractiva donde no hay red eléctrica o se busca costo operativo
  cero. Exige un circuito hidráulicamente "suave" (pérdidas bajas) y acepta que
  el caudal siga al sol: de noche no hay tiro.

Con el motor apagado, la sección ofrece la **chimenea solar**; son mutuamente
excluyentes.

## Motor / ventilador {#motor}

Se elige tipo (axial/centrífugo), caudal de diseño y rendimientos. Con la
pérdida de carga total del sistema, Secasol calcula la cascada de potencias:

$$
P_{hid}=Q\,\Delta P
\;\to\; P_{eje}=P_{hid}/\eta_{vent}
\;\to\; P_{elec}=P_{eje}/\eta_{motor}
\;\to\; P_{inst}=P_{elec}\cdot FS
$$

y la corriente nominal estimada. Orden de magnitud sano para un armario de
~50 kg: **50–100 W eléctricos** (un extractor comercial de 900 m³/h ronda los
76 W). Si el número da muy por encima, el circuito tiene demasiada pérdida de
carga — revisar lecho, velocidades y ductos antes de agrandar el motor.

## Chimenea solar {#chimenea}

La chimenea genera **tiro térmico**: el aire caliente de su interior pesa menos
que el ambiente y "flota", aspirando aire a través del secador:

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim})
$$

A mayor **altura** y mayor **temperatura** interior, más tiro. El caudal que
resulta **no se asume: se resuelve** — es el punto donde el tiro disponible
iguala la resistencia del circuito. De noche ($T_{chim}\le T_{amb}$) el tiro es
nulo y el caudal cero: el secado natural es intrínsecamente diurno.

<!-- profundidad: El acople colector–chimenea (lazo Picard) -->
Hay un acople sutil: el tiro depende de la temperatura de la chimenea, que
depende de la salida del colector, que depende del caudal… que depende del
tiro. Secasol cierra este lazo por **iteración de punto fijo (Picard)**: parte
de una estimación, corre el colector, recalcula el caudal natural y repite
hasta converger (tanto en modo constantes como hora a hora en el transitorio).
Por eso el botón "Calcular chimenea" de esta sección da un número
**preliminar** con una heurística de temperatura, y el número final —con el
lazo completo— sale de [7 · Resultados](?manual=resultados). El detalle está en
[Técnico · Motor y chimenea](?manual=tec-chimenea#picard).
<!-- /profundidad -->

## Extractor eólico {#extractor}

La chimenea puede llevar en el tope un **extractor eólico** (turbina "sombrero
chino"): el viento la hace girar y genera una depresión adicional que ayuda al
tiro, a costa de una pequeña obstrucción del flujo. El viento del clima (medido
a 10 m) se corrige a la altura real del tope por perfil logarítmico. Es un
**accesorio de la chimenea**, no un tipo de motor: suma su término motriz al
balance del tiro.

## Pérdidas de carga del sistema {#dp}

La sección estima y desglosa la $\Delta P$ total: colector (canal), cámara
(bandejas/lecho según la dirección de flujo), ductos y singulares (codos,
entradas, salidas) y — en Gran escala — el **caño maestro**. Este desglose es la
herramienta de diagnóstico: si un tramo domina, ahí está la oportunidad de
diseño (agrandar el canal, bajar la velocidad, repartir el lecho).

---

**Ver también:** [Técnico · Motor, chimenea y pérdidas de
carga](?manual=tec-chimenea) (todas las ecuaciones por tramo),
[3 · Colector](?manual=colector#geometria) y
[4 · Cámara](?manual=camara#bandejas) (dónde se origina la pérdida de carga),
[7 · Resultados](?manual=resultados) (el lazo completo).
