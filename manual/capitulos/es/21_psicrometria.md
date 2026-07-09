# Psicrometría — el aire húmedo y su carta

El secado es, en el fondo, un problema de **aire húmedo**: el aire entra con
cierta capacidad de llevarse agua, la usa sobre el producto, y sale más frío y
más húmedo. La psicrometría es el lenguaje para describir ese proceso, y la
**carta psicrométrica** es su mapa. Este capítulo define las magnitudes
(humedad absoluta, humedad relativa, saturación, entalpía) y enseña a leer la
carta que Secasol traza en [7 · Resultados](?manual=resultados#carta).

## Humedad absoluta y humedad relativa {#humedades}

Dos formas distintas —y complementarias— de decir "cuánta agua hay en el aire":

- **Humedad absoluta** $\omega$ [kg de agua / kg de aire seco]: la masa de
  vapor por unidad de masa de aire seco. Es la variable de **conservación**: si
  no se agrega ni quita agua, $\omega$ no cambia aunque cambie la temperatura.
- **Humedad relativa** HR [0–1]: cuán cerca está el vapor de la **saturación**
  a esa temperatura: $HR = p_v/p_{sat}(T)$. Es la variable de **capacidad**: a
  HR baja el aire "tiene sed"; a HR = 1 no admite más agua.

La clave del secado solar está en la relación entre ambas: **calentar el aire
no cambia su $\omega$, pero baja su HR** — porque $p_{sat}(T)$ crece
exponencialmente con la temperatura. Aire ambiente a 20 °C y 60 % HR, calentado
a 50 °C, baja a ~11 % HR: pasó de tibio y húmedo a sediento, sin quitarle ni
una gota de agua. Eso hace el colector.

<!-- profundidad: Las relaciones psicrométricas que usa Secasol -->
Con presión total $P$ y presión parcial de vapor $p_v$:

$$
\omega = 0.622\,\frac{p_v}{P - p_v},
\qquad
\omega_{sat}(T) = 0.622\,\frac{p_{sat}(T)}{P - p_{sat}(T)}
$$

La presión de saturación $p_{sat}(T)$ se evalúa con la correlación estándar
ASHRAE. Nótese la dependencia con $P$: a mayor **altitud** (menor presión), la
misma $p_v$ da más $\omega$ — por eso Secasol corrige toda la psicrometría por
la presión del emplazamiento. La **entalpía del aire húmedo** (por kg de aire
seco) es

$$
h = c_{p,as}\,T + \omega\,(L_v + c_{p,v}\,T)
$$

y el calor específico del aire húmedo $c_{p,h}=1006+1805\,\omega$ J/(kg·K).
Estas mismas funciones las usa el motor de cámara
([Técnico · Cámara](?manual=tec-camara#cstr)).
<!-- /profundidad -->

## Qué pasa en cada componente del secador {#proceso}

Sobre las variables $(T, \omega)$:

| Tramo | T | ω | HR | Proceso |
|---|---|---|---|---|
| Colector | ↑ | = | ↓↓ | calentamiento sensible |
| Auxiliar | ↑ | = | ↓ | calentamiento sensible |
| Cámara | ↓ | ↑ | ↑ | secado (≈ adiabático) |

En la cámara el aire cede calor sensible para evaporar agua y la incorpora como
vapor: por eso se **enfría y humedece a la vez**. Si la cámara fuera
perfectamente adiabática, la entalpía del aire se conservaría (el calor
sensible que pierde ≈ el latente que gana).

## La carta psicrométrica {#carta}

La carta es el plano **temperatura de bulbo seco (eje X) vs humedad absoluta
$\omega$ (eje Y)**, con dos familias de curvas de fondo:

- La **curva de saturación** (HR = 100 %): la frontera superior; más allá el
  agua condensa.
- Las curvas de **HR constante** (10 % a 90 %): abanico entre el eje X y la
  saturación.

Sobre ese fondo, Secasol traza la **poligonal del proceso** con los estados
calculados: **ambiente → salida del colector → entrada a cámara (tras el
auxiliar) → salida de cámara**, más una **isentálpica de referencia** punteada
desde la entrada de la cámara.

Cómo leerla:

- Los tramos de colector y auxiliar son **horizontales hacia la derecha**
  ($\omega$ constante, T sube). Su longitud es el trabajo térmico logrado.
- El tramo de cámara sube **hacia la izquierda**: el aire se enfría y gana
  agua. Su proyección vertical ($\Delta\omega$) multiplicada por el caudal de
  aire seco es la **tasa de agua evaporada**.
- Si la salida de cámara cae **sobre** la isentálpica punteada, el secado fue
  ≈ adiabático (cámara indirecta bien aislada). Si queda **por encima**, hubo
  aporte extra de calor en la cámara (superficies translúcidas); **por debajo**,
  pérdidas por paredes. Esto **no se impone**: emerge del balance.
- La distancia del punto de salida a la **curva de saturación** es el margen
  que quedó sin usar: salida muy lejos de saturación con producto aún húmedo
  sugiere caudal alto o cámara corta; salida pegada a saturación indica aire
  agotado (bien aprovechado, pero atención a condensación).

La carta se dibuja **a la presión del emplazamiento**: en altura, las curvas se
desplazan y los mismos (T, HR) dan otra $\omega$.

## Bulbo húmedo y temperatura de rocío {#bulbo-humedo}

Dos temperaturas auxiliares útiles al interpretar resultados:

- **Bulbo húmedo** $T_{bh}$: la temperatura de equilibrio de una superficie
  mojada ventilada — el límite inferior al que puede enfriarse el aire por
  evaporación (y una cota de la temperatura del producto durante el período de
  secado intenso).
- **Punto de rocío** $T_r$: la temperatura a la que el aire, enfriándose a
  $\omega$ constante, satura. Si alguna superficie del secador está por debajo
  de $T_r$, habrá condensación.

---

**Ver también:** [7 · Resultados](?manual=resultados#carta) (dónde se traza la
carta), [Física del secado](?manual=secado) (el lado del producto),
[Técnico · Cámara](?manual=tec-camara) (el balance que produce los estados).
