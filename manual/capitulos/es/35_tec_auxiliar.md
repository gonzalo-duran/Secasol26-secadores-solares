# Técnico · Sistema de calentamiento auxiliar

Referencia técnica del auxiliar: balance de energía, control por set-point,
consumos, impacto en el balance global y calendario de arranque del híbrido
industrial. La guía de uso está en [5 · Calentamiento auxiliar](?manual=auxiliar).

## 1. Para qué sirve y dónde se ubica {#ubicacion}

El auxiliar (eléctrico o de biomasa) es el **respaldo térmico** del secador:
aporta calor cuando el sol no alcanza (días nublados, arranque temprano,
atardecer). Es **opcional**. Tiene dos modos de ubicación:

- **SERIE POSCOLECTOR** — el auxiliar está **entre el colector y la cámara**:
  toma el aire ya precalentado por el colector
  ($T_{ent}=T_{salida,colector}$) y lo termina de calentar antes de la cámara.
- **RESPALDO INDEPENDIENTE** — toma aire ambiente ($T_{ent}=T_{amb}$) y lo
  calienta por su cuenta (respaldo total).

En **gran escala** el aire de todas las ramas se suma en el caño maestro y
**recién entonces** entra al auxiliar (o directo a la cámara).

## 2. Balance de energía estacionario {#balance}

El auxiliar se modela como un calentador en **régimen estacionario, sin inercia
térmica**. El balance de energía sobre el aire es:

$$
\boxed{\;Q_{eff} = \dot m\,c_{p,aire}\,(T_{salida}-T_{entrada})\;}
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p,aire}}
$$

con $c_{p,aire}\approx1007$ J/(kg·K). La potencia disponible es
$Q_{max}=P_{nominal}\cdot f_{operacion}$ (fracción de potencia de operación).

### 2.1 Control por set-point (proporcional ideal) {#set-point}

Si hay set-point $T_{sp}$, el auxiliar entrega **solo** la potencia necesaria
para alcanzarlo:
$$
Q_{set} = \dot m\,c_{p}\,(T_{sp}-T_{entrada})
$$

- $Q_{set}<0$ → el aire ya supera el set-point: $Q_{eff}=0$ (con aviso).
- $0\le Q_{set}\le Q_{max}$ → $Q_{eff}=Q_{set}$ (control activo, modula).
- $Q_{set}>Q_{max}$ → $Q_{eff}=Q_{max}$ a tope (aviso de set-point no
  alcanzable).

Si no hay set-point, $Q_{eff}=Q_{max}$. Hay además un tope físico
$T_{max,salida}$ que dispara aviso si se excede.

### 2.2 Consumos {#consumos}

- **Resistencia eléctrica** ($\eta\approx1$): $P_{elec}=Q_{eff}$.
- **Quemador de biomasa:** consumo [kg/h] proporcional a la fracción activa;
  la **leña total** sale de la energía entregada, el PCI (poder calorífico
  inferior) y el rendimiento del quemador:
  $$ m_{leña} = \frac{E_{aux}}{PCI\cdot\eta_{quemador}} $$
  con $E_{aux}=\int Q_{eff}\,dt$ (integración trapezoidal sobre el horizonte).

## 3. Impacto en el balance global {#impacto}

El auxiliar **eleva la temperatura de la corriente de aire** que alimenta la
cámara. En la cadena del aire (modo armario):

$$
T_{amb} \xrightarrow{\text{colector: }+\Delta T} T_1
\xrightarrow{\text{auxiliar: }+\Delta T} T_2
\xrightarrow{\text{cámara}} T_3 < T_2
$$

La $T_{salida}$ del auxiliar pasa a ser la **condición de borde** $T_{ent}$ del
motor termodinámico de cámara ([Técnico · Cámara](?manual=tec-camara)),
modificando todo el balance calor–masa aguas abajo (más temperatura del aire →
más capacidad de evaporación → secado más rápido). El auxiliar **no agrega
humedad** ($\omega$ constante): es calentamiento **sensible** puro — en la
[carta psicrométrica](?manual=psicrometria) es un tramo horizontal.

En los modos **Transitorio/Ventana**, el auxiliar se evalúa **hora a hora**
sobre la serie de $T_{ent}(t)$, reusando la lógica escalar paso a paso, y
acumula energía y leña.

## 4. Disponibilidad temporal y calendario de arranque {#calendario}

El auxiliar tiene una **política de operación temporal**:

- **Disponibilidad nocturna**: si está deshabilitada y se dispone de la serie
  de irradiancia, los pasos con $I_g \le 10$ W/m² (noche) se fuerzan a
  $Q_{eff}=0$ (auxiliar apagado de noche).
- **Calendario de arranque**: para el **híbrido industrial**, el quemador opera
  en **ventanas horarias** específicas de mañana/atardecer (independiente de la
  irradiancia), no a potencia constante. Cada paso se mapea a su hora del día
  $((t/3600)+\text{offset})\bmod 24$ y se marca activo si cae dentro de alguna
  ventana $[\text{inicio}, \text{inicio}+\text{duración})$ (con envoltura si
  cruza la medianoche).

Esto reproduce la operación real de un secador híbrido tipo ADITAL: el quemador
se enciende temprano para arrancar el secado y al atardecer para no perder la
tanda, acumulando leña en cada ventana (ver
[Técnico · Modo industrial](?manual=tec-industrial#calendario)).

---

**Ver también:** [5 · Calentamiento auxiliar](?manual=auxiliar) (guía de uso),
[Técnico · Cámara](?manual=tec-camara) (a dónde entra el aire calentado),
[Apéndice · Implementación](?manual=apendice-codigo#auxiliar).
