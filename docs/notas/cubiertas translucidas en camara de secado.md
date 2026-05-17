# Camaras de secado translucidas en los tres modos de dimensionamiento

## Fundamentación:
 
Se desea modificar los modos de operación en las tres instancias de diseño (caja, armario, secador industrial), agregando la posibilidad de que los techos de las cámaras de secado sean translucidos, permitiendo el incremento de entalpía en el aire circulante mediante el ingreso de radiación solar al interior de la cámara.

Se propone analizar la siguiente situación, común en comportamiento a las tres instancias de diseño:

1. En el caso de que el usuario requiera diseño de cámara con techo translucido, el usuario activará la opcion de diseño. 
2. Se considerará que las cámaras tienen techos planos, translúcidos, de adecuada transmitancia en el visible y baja conductividad térmica. 3. El material de los techos translucidos tomará las posibles opciones de la librería de cubiertas, que ya fué cargada para los colectores solares.  
4. Por una cuestión de simplicidad se considerará que la radiación horizontal incide de manera normal al plano del techo (techos planos).
5. El aporte de energía extra se calculará como Ig_horizontal * tau_cubierta * alfa_producto, donde Ig_horizontal es la radiación global sobre plano horizontal, tau_cubierta la transmitancia visible de la cubierta del techo, y alfa_producto la absortividad del producto de la bandeja, que recibe la exposición directa a la radiación solar que ingresa al secador. Como simplificación en esta ocasión, se implementará que alfa_producto = 0.6

## La situación actual

El documento de balance lo dice explícitamente en la Observación 1: el modelo actual representa una cámara *sin incidencia de radiación solar sobre el producto* — secador indirecto puro.

## La física del problema con techo translúcido

Cuando la cubierta superior de la cámara es translúcida, la radiación solar global I_g que incide sobre el techo se atenúa al pasar por la cubierta (transmitancia τ_cubierta) y luego una fracción es absorbida por la superficie del producto (absortividad α_producto). La potencia radiativa que llega al producto es:

**Q_rad_prod = I_g · τ_cubierta · α_producto · A_rad**

A_rad va a ser, en esta iteración el área de la bandeja superior, que "ve" directamente la radiación solar incidente.


Podriamos pensar que el termino Q_rad_prod se activa o desactiva segun el tipo de cubierta, si cubierta_translucida = True, y 0 en caso contrario.

Entonces, en secadores con cubiertas translucidas el producto recibe un flujo de energía radiante adicional Q_rad_prod que eleva su temperatura. Al subir T_prod, ocurren dos cosas que aceleran el secado: primero, la presión de saturación p_sat(T_prod) sube, lo que aumenta la fuerza impulsora difusiva (W_sat(T_prod) − W_cam); segundo, si T_prod > T_flujo, el producto le entrega calor al aire por convección en lugar de recibirlo, lo que cambia el signo del primer término. 

Este segundo efecto es lo que distingue a un secador mixto de uno indirecto: el producto puede estar más caliente que el aire circundante.

## Sobre dónde no se modifica nada

Un punto importante: el balance de masa del aire **no cambia**. La evaporación sigue siendo conducida por la diferencia de humedad absoluta (W_sat(T_prod) − W_cam), y el coeficiente difusivo K_m sigue viniendo de Chilton-Colburn. Lo que cambia es la T_prod que se usa para evaluar esa W_sat, porque ahora T_prod sube más rápido (o a un nivel más alto) gracias a la radiación.

El balance de energía del flujo de aire tampoco cambia en su forma: el aire sigue intercambiando con el producto por convección y recibiendo vapor a T_prod. Lo que sí cambia es el valor numérico de T_prod (más alto), por lo que el aire puede enfriarse menos — o incluso calentarse — al pasar por la cámara.

## Cómo se implementaría en código

La implementación sería relativamente quirúrgica, y te la planteo en capas:

**Capa 1 — Datos (camara.py).** Agregar a `ConstruccionCamara` los campos `tau_cubierta_solar` (float, default 0.85) y algo para la inclinación del techo si fuera necesario. En el catálogo de productos, agregar `alfa_solar` como propiedad opcional. En `ConstruccionCamara`, estos campos solo tienen sentido cuando `cubierta_translucida = True`; si es False, se ignoran.

**Capa 2 — Motor termodinámico (camara_termodinamica.py).** En `resolver_estado_camara`, el balance de energía del producto incluiría un argumento adicional `Q_rad_W` (float, default 0.0). Internamente, el término se suma al lado derecho de la EDO de dT_prod/dt. Cuando `cubierta_translucida = False`, el llamador pasa Q_rad_W = 0 y el comportamiento es idéntico al actual.

**Capa 3 — Motor dinámico (camara_calc_dinamico.py).** Acá es donde se vuelve interesante: I_g varía en el tiempo, hora a hora. La estructura de `ForzantesAire` ya tiene una serie temporal. Se podría agregar un campo `I_g_techo_W_m2` a las forzantes (o calcularlo en `armar_forzantes_aire` a partir de la geometría solar y la irradiancia global). En cada paso de integración de `solve_ivp`, el RHS de la EDO de T_prod sumaría el término `I_g(t) · τ_cubierta · α_producto · A_techo / (M_s · (c_ps + c_pa · X))`.

**Capa 4 — Wire-up (camara_calc.py y balance_global.py).** En `_calcular_termodinamico`, leer `cubierta_translucida`, `tau_cubierta_solar` y `alfa_solar` del catálogo, computar Q_rad_W = I_g · τ · α · A_techo, y pasarlo al solver. En el balance global, si se quiere reportar la energía radiativa directa como fracción del total, se suma a los resultados.

Esta formulación es que es **aditiva y no invasiva**: cuando `cubierta_translucida = False` (el caso actual), Q_rad = 0 y nada cambia. Todos los tests existentes siguen pasando sin tocar una línea. La radiación directa sobre el producto es simplemente un sumando extra en la ecuación de energía del producto.

## Posiblidad de implementación en los tres tipos de cámara

**Tipo CAJA:** El docstring de `camara.py` dice literalmente "Almacenado en Proyecto.camara. Es None para tipología CAJA (que aún no está implementada en v0)." Y en `camara_calc_dinamico.py` la restricción es explícita: "Solo tipologías Armario y Gran escala (no CAJA)." La verificación de coherencia en `balance_global.py` confirma que CAJA no admite colector externo ni motor — es convección natural pura. En la práctica, la tipología CAJA ni siquiera tiene cámara instanciada hoy. El flujo de aire descrito en el documento de balance (sección 7.a) es simplemente: aire ambiente entra → enfriamiento evaporativo en cámara → aire sale. Sin colector, sin calentamiento previo, sin radiación sobre producto.

**Tipo ARMARIO y GRAN_ESCALA:** Tienen cámara implementada, con los motores de capa fina y termodinámico funcionando. Pero la Observación 1 del documento de balance es inequívoca: "cámara de secado con paredes opacas a la radiación." La ecuación [2] del paper de ASADES que tenemos como referencia tampoco tiene término radiativo: el lado derecho solo tiene `A_t · h_c · (T_c − T_p)`.

Entonces estamos ante una situación donde el toggle `cubierta_translucida` existe en `ConstruccionCamara` como campo booleano, y ya dispara una advertencia si el producto es fotosensible, pero **no tiene efecto alguno sobre la física del cálculo**. Es un atributo decorativo.

## Lo que implica para la implementación

Esto simplifica bastante el enfoque, porque la modificación es transversal a todas las tipologías. El término Q_rad_prod que discutimos antes tiene que poder inyectarse en cualquier motor de cámara, y la lógica de decisión es la misma en los tres casos:

Para **CAJA**, el secador es inherentemente directo o mixto — es una caja con cubierta translúcida donde el sol le da al producto. Es quizás el caso donde la radiación directa es más importante, porque no tiene colector que precaliente el aire. El único aporte energético que recibe el producto (además del aire ambiente) es esa radiación transmitida. Cuando eventualmente implementemos CAJA, la cubierta translúcida no debería ser opcional sino la configuración por defecto (o incluso obligatoria).

Para **ARMARIO** y **GRAN_ESCALA**, es una mejora opcional: el secador puede ser indirecto (cubierta opaca, como ahora) o mixto (techo translúcido + colectores). En el caso mixto, el producto recibe calor de dos fuentes: el aire precalentado por colectores/auxiliar, y la radiación directa a través del techo.

Desde el punto de vista de la implementación en código, el concepto unificador es que Q_rad_prod es un forzante externo del balance de energía del producto, igual que T_entrada_aire o I_g son forzantes. El wire-up de cada tipología computa ese Q_rad_prod de manera ligeramente distinta (porque el área del techo, la inclinación, y la disponibilidad de I_g pueden variar), pero la ecuación en el motor termodinámico es idéntica en los tres casos.

## Que hacer: 

Formulación unificada del término Q_rad para las tres tipologías.