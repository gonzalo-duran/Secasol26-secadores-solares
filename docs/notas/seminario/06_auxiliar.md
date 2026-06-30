# 06 · Sistema de calentamiento auxiliar

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: las ecuaciones del auxiliar, su impacto en el balance de calor y **dónde**
> impacta en la cadena del aire, incluyendo el calendario de arranque del híbrido
> industrial.

---

## 1. Para qué sirve y dónde se ubica

El auxiliar (eléctrico o de biomasa) es el **respaldo térmico** del secador: aporta
calor cuando el sol no alcanza (días nublados, arranque temprano, atardecer). Es
**opcional** (`proyecto.auxiliar = None` si no hay). Tiene dos modos de ubicación
(`ModoOperacion`):

- **SERIE_POSCOLECTOR** — el auxiliar está **entre el colector y la cámara**: toma
  el aire ya precalentado por el colector ($T_{ent}=T_{salida,colector}$) y lo
  termina de calentar antes de la cámara.
- **RESPALDO_INDEPENDIENTE** — toma aire ambiente ($T_{ent}=T_{amb}$) y lo calienta
  por su cuenta (respaldo total).

> En **gran escala** el aire de todas las ramas se suma en el caño maestro y
> **recién entonces** entra al auxiliar (o directo a la cámara).

---

## 2. Ecuaciones — balance de energía estacionario

El auxiliar se modela como un calentador en **régimen estacionario, sin inercia
térmica**. El balance de energía sobre el aire es:

$$
\boxed{\;Q_{eff} = \dot m\,c_{p,aire}\,(T_{salida}-T_{entrada})\;}
\qquad\Rightarrow\qquad
T_{salida} = T_{entrada} + \frac{Q_{eff}}{\dot m\,c_{p,aire}}
$$

con $c_{p,aire}\approx1007$ J/(kg·K). La potencia disponible es
$Q_{max}=P_{nominal}\cdot f_{operacion}$ (fracción de potencia de operación).

### 2.1 Control por set-point (proporcional ideal)

Si hay set-point $T_{sp}$, el auxiliar entrega **solo** la potencia necesaria para
alcanzarlo:
$$
Q_{set} = \dot m\,c_{p}\,(T_{sp}-T_{entrada})
$$
- $Q_{set}<0$ → el aire ya supera el set-point: $Q_{eff}=0$ (aviso
  `AUX_T_ENTRADA_SUPERA_SET_POINT`).
- $0\le Q_{set}\le Q_{max}$ → $Q_{eff}=Q_{set}$ (control activo, modula).
- $Q_{set}>Q_{max}$ → $Q_{eff}=Q_{max}$ a tope (aviso `AUX_SET_POINT_NO_ALCANZABLE`).

Si no hay set-point, $Q_{eff}=Q_{max}$. Hay además un tope físico
$T_{max,salida}$ que dispara aviso si se excede.

### 2.2 Consumos

- **Resistencia eléctrica** ($\eta\approx1$): $P_{elec}=Q_{eff}$.
- **Quemador de biomasa:** consumo $[\text{kg/h}]$ proporcional a la fracción
  activa; la **leña total** sale de la energía entregada, el PCI y el rendimiento:
  $$ m_{leña} = \frac{E_{aux}}{PCI\cdot\eta_{quemador}} $$
  con $E_{aux}=\int Q_{eff}\,dt$ (trapezoidal sobre el horizonte) y $PCI$ poder
  calorífico inferior de la biomasa.

---

## 3. Impacto en el balance global — dónde entra

El auxiliar **eleva la temperatura de la corriente de aire** que alimenta la cámara.
En la cadena del aire (modo armario):

```
T_amb → [colector: +ΔT sensible] → T1 → [AUXILIAR: +ΔT] → T2 → [cámara] → T3 < T2
```

Concretamente, $T_{salida}$ del auxiliar pasa a ser la **condición de borde
$T_{ent}$** del motor termodinámico de cámara (doc 03), modificando todo el balance
calor–masa aguas abajo (más temperatura del aire → más capacidad de evaporación →
secado más rápido). El auxiliar **no agrega humedad** ($\omega$ constante): es
calentamiento **sensible** puro.

En el modo **Transitorio/Ventana**, el auxiliar se evalúa **hora a hora**
(`calcular_auxiliar_transitorio`) sobre la serie de $T_{ent}(t)$, reusando la
lógica escalar paso a paso, y acumula $E_{aux}$ y leña.

---

## 4. Disponibilidad temporal y calendario de arranque (híbrido S40)

El auxiliar tiene una **política de operación temporal**:

- **`disponible_nocturno`**: si es `False` y se pasa la serie de irradiancia, los
  pasos con $I_g \le 10$ W/m² (noche) se fuerzan a $Q_{eff}=0$ (auxiliar apagado de
  noche).
- **Calendario de arranque** (`Auxiliar.cargas_arranque: list[CargaArranque]`):
  para el **híbrido industrial**, el quemador opera en **ventanas horarias**
  específicas de mañana/atardecer (independiente de la irradiancia), no a potencia
  constante. La máscara `_mascara_calendario` mapea cada paso a su hora del día
  $((t/3600)+\text{offset})\bmod 24$ y lo marca activo si cae dentro de alguna
  ventana $[\text{inicio}, \text{inicio}+\text{duración})$ (con envoltura si cruza
  la medianoche).

Esto reproduce la operación real de un secador híbrido tipo ADITAL: el quemador se
enciende temprano para arrancar el secado y al atardecer para no perder la tanda,
acumulando leña en cada ventana.

---

## 5. Highlights de implementación (a nivel código)

| Qué | Dónde |
|---|---|
| Balance escalar del auxiliar | `calculos/auxiliar_calc.py::calcular_auxiliar` |
| Control por set-point (3 casos) | `calcular_auxiliar` (lógica de `Q_para_set_point`) |
| Solver transitorio (horizonte) | `auxiliar_calc.py::calcular_auxiliar_transitorio` |
| Máscara de calendario híbrido | `auxiliar_calc.py::_mascara_calendario` |
| Consumo/leña (PCI, η) | `core/auxiliar.py` (`PCI_MJ_kg`, `eficiencia_quemador`, `CargaArranque`) |
| Modelo de datos | `core/auxiliar.py` (`Auxiliar`, `TipoAuxiliar`, `ModoOperacion`) |

**Puntos a destacar en la charla:**
1. *Calentamiento sensible puro* — sube $T$ a $\omega$ constante, justo antes de la
   cámara.
2. *Control por set-point modulante* — entrega solo lo necesario, con avisos si no
   alcanza o si el aire ya está caliente.
3. *Trazabilidad de consumo* — energía, potencia eléctrica o **leña** (vía PCI·η).
4. *Calendario de arranque* — el híbrido opera en ventanas mañana/tarde, no a
   potencia constante (clave del modo industrial).

---

## Referencias

- Balance de energía en régimen estacionario (calentador de aire) — texto estándar.
- Datos de PCI de biomasa — tablas de poder calorífico de leña/residuos.
