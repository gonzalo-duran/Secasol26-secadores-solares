# 4 · Cámara de secado

La cámara es donde ocurre el secado: el aire caliente del colector (o del
auxiliar) pasa por las bandejas de producto, le entrega calor y se lleva la
humedad. En esta sección se define la **geometría** de la cámara, su
**construcción** (paredes, techo), las **bandejas**, el **producto** y su
**carga**. El motor físico que la resuelve es un balance acoplado de calor y
masa: el aire se enfría y se humedece al secar, y la velocidad de secado
"emerge" de la física — no de una curva empírica.

<!-- esquema: camara_dimensiones | Geometría de la cámara con sus cotas. -->

## Geometría {#geometria}

Largo, ancho y alto definen el volumen y —junto con el techo— la **envolvente**
por donde la cámara pierde calor al ambiente. El largo en el sentido del flujo
es además la longitud característica de la transferencia aire→producto.

## Paredes {#pared}

La pared puede ser **simple** (un material con su espesor) o **compuesta**
(capas en serie: chapa + aislante + chapa, madera + poliestireno, etc.). El
modelo agrega las resistencias de las capas y calcula la pérdida
$Q_{pared}=U\,A\,(T_{flujo}-T_{amb})$, donde $U$ combina la convección
interior, la conducción de las capas y el viento exterior.

En la práctica: el aislante manda. Duplicar el espesor de aislante baja las
pérdidas casi a la mitad; cambiar la chapa exterior casi no cambia nada.

## Techo translúcido {#techo}

Opcionalmente el techo puede ser translúcido (policarbonato alveolar): aporta
**ganancia solar directa** sobre la primera bandeja — es lo que convierte una
Caja en secador — pero también **pierde más calor** que un techo opaco aislado.
El modelo captura los dos efectos, con el espesor del alveolar como parámetro
(ver [Técnico · Cámara](?manual=tec-camara#techo-translucido)).

## Bandejas y dirección del flujo {#bandejas}

El número de bandejas y sus dimensiones fijan el **área de contacto**
aire–producto. La **dirección del flujo** es una decisión de diseño importante:

- **Horizontal** (el aire pasa *sobre* las bandejas): hidráulicamente suave,
  transferencia moderada.
- **Vertical ascendente** (el aire *atraviesa* el lecho): máximo contacto y
  secado más parejo, pero la pérdida de carga del lecho crece mucho — la paga
  el ventilador o el tiro de la chimenea
  ([6 · Motor](?manual=motor)).

<!-- profundidad: La pérdida de carga del lecho (Ergun) -->
En flujo vertical, la caída de presión del lecho empacado se calcula con la
ecuación de **Ergun**, que suma un término viscoso (dominante a baja velocidad)
y uno inercial:

$$
\frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
$$

con $\varepsilon$ la porosidad del lecho, $d_p$ el diámetro de partícula y
$\Phi_s$ la esfericidad. Estos parámetros salen del catálogo del producto o de
defaults conservadores. Un lecho de rodajas finas y compactas puede multiplicar
la $\Delta P$ respecto de un lecho de trozos gruesos.
<!-- /profundidad -->

## Producto y carga {#producto}

El producto se elige del **catálogo** (con sus propiedades de sorción y
constantes térmicas ya cargadas) y se define la **carga**: masa fresca,
humedad inicial $X_0$ y humedad objetivo $X_{obj}$, ambas en **base seca**
(kg de agua por kg de materia seca — la diferencia con la base húmeda está
explicada en [Física del secado](?manual=secado#base-seca)).

El corazón del modelo de producto es la **isoterma de sorción GAB**: a medida
que el producto se seca, su actividad de agua cae y el secado se frena solo —
así aparecen los períodos de tasa decreciente sin ninguna curva empírica
ajustada ([Física del secado](?manual=secado#isotermas)).

## Condiciones de operación y forzantes {#modos-forzantes}

La sección permite elegir de dónde salen las condiciones del aire que entra a
la cámara:

- **Constantes**: temperatura y humedad de operación fijadas a mano (los
  controles T/HR de esta sección). Útil para exploración rápida.
- **Sintético / Día real / Anual**: las forzantes salen del **clima y del
  colector** hora a hora. **En estos modos los controles T/HR de operación no
  influyen** — la condición de borde real es la salida del colector (más el
  auxiliar si existe).

El **horizonte de simulación** (modo transitorio) define cuántas horas se
integra el balance.

## Operación anual {#operacion-anual}

Con [modo de análisis Anual](?manual=tipologia#modo-analisis), aparece la
sección de **operación anual**: se define cuántos **batches por mes** se
procesan y Secasol corre el día típico de cada mes, estimando producción anual
y las cuatro **eficiencias de secado** (drying, pickup, térmica, total) por mes.
El detalle mensual se muestra después en [7 · Resultados](?manual=resultados).

## Túnel semicontinuo (Gran escala) {#tunel}

Con subtipo **Semicontinuo**, acá se configura la **topología del túnel**:
número de zonas y cadencia de avance de las columnas de carros. La sequedad de
salida **no se impone**: es un resultado — si el producto sale más húmedo que
el objetivo, hay que alargar el túnel, bajar la cadencia o subir la temperatura
([Técnico · Modo industrial](?manual=tec-industrial#semicontinuo)).

---

**Ver también:** [Técnico · Cámara](?manual=tec-camara) (las ecuaciones del
balance acoplado), [Física del secado](?manual=secado) e
[Psicrometría](?manual=psicrometria) (fundamentos),
[5 · Auxiliar](?manual=auxiliar) (si el sol no alcanza).
