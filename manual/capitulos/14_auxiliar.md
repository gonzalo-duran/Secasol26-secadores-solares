# 5 · Calentamiento auxiliar

El auxiliar es el **respaldo térmico** del secador: una resistencia eléctrica o
un quemador de biomasa que aporta calor cuando el sol no alcanza — días
nublados, arranque temprano, atardecer, o campañas donde perder una tanda
cuesta más que la leña. Es **opcional**: un secador puramente solar
simplemente no lo incorpora.

## Cuándo conviene {#cuando}

Dos señales típicas de que el diseño necesita auxiliar:

- El [modo transitorio o anual](?manual=resultados) muestra que el producto no
  llega a la humedad objetivo dentro de la ventana segura (riesgo de deterioro
  nocturno o de tanda perdida).
- La **fracción solar** del balance queda alta pero el tiempo de secado es
  inaceptable en los meses críticos.

El objetivo del prediseño es dimensionarlo **al mínimo**: el dashboard de
Resultados reporta la energía auxiliar y la fracción solar para juzgarlo.

## Tipo y ubicación {#tipo}

- **Tipo**: resistencia **eléctrica** (rendimiento ≈ 1, consumo en kWh) o
  quemador de **biomasa** (consumo en kg de leña vía poder calorífico y
  rendimiento del quemador).
- **Ubicación**: en **serie poscolector** (toma el aire precalentado del
  colector y lo termina de calentar — lo usual) o como **respaldo
  independiente** (toma aire ambiente y calienta por su cuenta).

El auxiliar **no agrega humedad**: es calentamiento sensible puro. En la
[carta psicrométrica](?manual=psicrometria#carta) su tramo es horizontal
(sube T, ω constante) — igual que el colector.

## Potencia y set-point {#setpoint}

Se define la **potencia nominal** y, opcionalmente, un **set-point** de
temperatura: con set-point, el auxiliar entrega **solo la potencia necesaria**
para alcanzarlo (control modulante ideal). Si el aire ya llega más caliente que
el set-point, el auxiliar no gasta nada; si la potencia no alcanza para llegar,
entrega el máximo y avisa.

<!-- profundidad: El balance del auxiliar -->
El auxiliar se modela en régimen estacionario, sin inercia:

$$
Q_{eff} = \dot m\,c_{p}\,(T_{salida}-T_{entrada})
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p}}
$$

Con set-point $T_{sp}$: $Q_{set}=\dot m c_p (T_{sp}-T_{ent})$, recortado entre
0 y $Q_{max}$. La leña consumida sale de
$m_{leña}=E_{aux}/(PCI\cdot\eta_{quemador})$, con la energía integrada sobre el
horizonte. Ecuaciones y casos límite en
[Técnico · Auxiliar](?manual=tec-auxiliar#balance).
<!-- /profundidad -->

## Disponibilidad y calendario de arranque {#calendario}

- **Disponibilidad nocturna**: puede apagarse el auxiliar de noche (cuando la
  irradiancia es prácticamente nula), típico si la operación no tiene turno
  nocturno.
- **Calendario de arranque** (híbrido industrial): el quemador opera en
  **ventanas horarias** de mañana y atardecer — la operación real de un secador
  híbrido tipo ADITAL: encender temprano para arrancar la tanda y al atardecer
  para no perderla. Cada ventana se define por hora de inicio y duración, y el
  consumo de leña se acumula por ventana.

---

**Ver también:** [Técnico · Auxiliar](?manual=tec-auxiliar) (ecuaciones y
control), [4 · Cámara](?manual=camara) (a dónde va el aire),
[7 · Resultados](?manual=resultados) (fracción solar y consumo en el balance).
