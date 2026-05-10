# Balance de calor y masa en la camara de secado.

## Observaciones:
    1. Este modelo representa el comportamiento de una cámara de secado sin incidencia de radiación solar sobre el producto, esto es, una cámara de secado con paredes opacas a la radiación (Secador de tipo indirecto, por la incidencia de radiación). 
    2. El modelo es global para la cámara de secado y producto. Esto significa que no se tomarán en cuenta gradientes de temperatura para el volumen de producto en cámara, ni para el flujo, ni en las paredes de la cámara de secado. Entonces, en el circuito térmico equivalente, la temperatura de producto está representada con un solo nodo T_prod, la temperatura del aire en la cámara se representa con T_flujo, y las caras internas y externas de las paredes de la cámara de secados son representadas con un nodo Tcam_int y Tcam_ext, respectivamente.
    3. Además, consideramos que solo el producto varía su temperatura en el tiempo, esto es, de los tres elementos que se modelan, el unico que tiene acumulación de calor es el producto. La condición inicial a la que se somete la temperatura del producto es T_prod (t = 0) = Tamb.
    4. Tomaremos a la cámara de secado como una caja rectangular de lados Largo_Cam, Ancho_cam, Alto_Cam. Supondremos que todas las paredes de la cámara comparten materiales, espesores y método constructivo. 
    Así, el área de la cámara de secado A_cam se estimará como A_cam = 4 * (Largo_Cam * Alto_Cam) + 2 * (Largo_Cam * Ancho_cam).
    5. El producto intercambia energía y vapor de agua con el aire circulante. Supondremos que el producto está colocado en bandejas. El área efectiva de intercambio para el producto es A_prod = A_bandeja * N * Den_carga
    Donde A_prod es el área de producto expuesto a intercambio convectivo y difusivo. A_bandeja es el área superficial de una bandeja donde se coloca el producto. N es el número de bandejas en la cámara de secado, y Den_carga es la densidad de carga de producto por bandeja, en kg/m2.
    6. Continuamos considerando que el secador cumple ecuación de continuidad de flujo de aire, esto es, tiene una solar entrada de aire (al ingreso de colectores en el caso de los secadores armario y secadores de gran escala, o en la boca de entrada de aire para los secadores de tipo caja), y una sola salida de aire (en la salida de cámara de secado, o en la salida de la chimenea solar para aquellos que tengan este elemento).
    7. A fin de poder aclarar la dinámica de comportamiento del flujo de aire en la cámara de secado, y los intercambios energéticos y de masa producto del proceso de enfriamiento evaporativo que se producen en la cámara de secado tendremos que el flujo de aire circula através del secador de la siguiente manera:
        7.a. En los secadores de tipo caja el flujo de aire circula con la siguiente disposición:
        En un secador de tipo caja el flujo de aire mpunto_aire va a ingresar al secador a condiciones de temperatura ambiente (Tamb), y humedad absoluta ambiente (Wamb). El flujo de aire  circula por la cámara de secado produciendóse el enfriamiento evaporativo por deshidratado del producto. Como consecuencia, al abandonar la camara de secado es expelido con una temperatura T2, y humedad absoluta W2. Un esquema simple es:
            Ingresa aire ambiente por boca de entrada (Tamb, Wamb) -> Aire circula por la Cámara de secado (aire en enfriamiento evaporativo)) -> Aire se expele por la boca de salida del secador (T2,W2).
        7.b. En un secador de armario, el movimiento del aire se produce de la siguiente manera:
        El flujo de aire  que ingresa en la entrada de colectores tiene temperatura Tamb y humedad absoluta Wamb. En colectores el aire sufre un proceso de calentamiento sensible, por lo que en la salida de colectores tiene temperatura T1, y humedad absoluta Wamb (no cambia por que no tiene aporte de vapor de agua). Luego atraviesa el sistema de calentamiento auxiliar (si lo hubiera), incrementando su temperatura, a W constante. En la cámara de secado el aire circulante encuentra al producto. Como consecuencia se produce el aire entrega energía en forma de calor al producto, disminuyendo su temperatura respecto a la salida de colectores. Asimismo, el aire gana vapor de agua, como resultado del deshidratado del producto. Entonces, a la salida de la cámara de secado el aire se encuentra a una temperatura T3 y humedad absoluta W3, cumpliendo T3 < T1 y W3 > W1 = Wamb. El esquema simplificado es:
            Ingreso de aire ambiente en entrada de colectores (Tamb, Wamb) -> calentamiento sensible en colectores, saliendo a T1 > Tamb, W1 = Wamb -> calentador auxiliar (si hubiera), saliendo a T2 > T1 y W2 = Wamb -> circulacion por camara de secado, enfriamiento evaporativo -> salida de camara de secado a T3 < T2, W3 > W2 -> circulacion por chimenea solar (si hubiera) -> salida al ambiente.
        7.c. En secadores de gran escala el circuito de movimiento de aire es similar al de un secador de tipo armario, salvo que el flujo de aire que sale de colectores se suma y recién ingresa al calentador auxiliar, o a la cámara de secado.
                

## Nomenclatura:
    hconv_int = Coeficiente convectivo del flujo de aire en el interior de la cámara de secado.
    A_cuerpo = Area conjunta de todas las superficies de la cámara de secado.
    T_flujo = Nodo que representa globalmente la temperatura del flujo a la salida de la cámara de secado.
    Tcam_int = Nodo que representa globalmente la temperatura de las caras internas de la cámara de secado.
    k_aisl = Conductividad térmica de las paredes del secador.
    esp_cam = Espesor de las paredes del secador.
    Tcam_ext = Temperatura de las caras externas de las paredes de la cámara.
    h_w = Coeficiente convectivo por viento.
    Tamb = Temperatura ambiente.
    mpunto_aire = flujo másico de aire que circula por la cámara de secado
    

## Balance de calor en el cuerpo del secador:
### Ganancia de energía en las paredes por convección desde el flujo:
    hconv_int * A_cuerpo * (T_flujo - Tcam_int)
### Pérdida de calor por conducción en paredes:
    -k_aisl * A_cuerpo/esp_cam (Tcam_int - Tcam_ext)
### Pérdida de calor por conveccion al exterior:
    h_w * A_cuerpo * (Tcam_ext - Tamb)
### Balance de calor en cuerpo de camara de secado:
    hconv_int * A_cuerpo * (T_flujo - Tcam_int) - k_aisl * A_cuerpo/esp_cam (Tcam_int - Tcam_ext) + h_w * A_cuerpo * (Tcam_ext - Tamb) = 0

## Balance de calor para el flujo de aire:
### Flujo de calor por transporte de masa:
    mpunto_aire * cp_aire * (T_flujo - Tsal_colector)
### Pérdida de calor por conveccion en paredes:
    hconv_int * A_cuerpo * (T_flujo - Tcam_int)
### Pérdida de calor por convecció con el producto:
    hconv_int * A_prod * (T_flujo - T_prod)
### Balance de calor para el flujo:
    mpunto_aire * cp_aire * (T_flujo - Tsal_colector) +  hconv_int * A_cuerpo * (T_flujo - Tcam_int) + hconv_int * A_prod * (T_flujo - T_prod) = 0

## Balance de calor para el producto:
### Variación temporal de temperatura:
    mprod * cp_prod * d(T_prod)/dt
    La condición inicial supuesta para la temperatura de producto es:
    T_prod (t = 0) = Tamb
### Ganancia de calor por convección:
    hconv_int * A_prod * (T_flujo - T_prod)
### Balance de calor en el producto:
    mprod * cp_prod * d(T_prod)/dt + hconv_int * A_prod * (T_flujo - T_prod) = 0
    
## Balance de masa
    La ecuación de balance de masa de agua en el interior de la cámara de secado es:
    mpunto_w = mpunto_aire * (W_producto - W_flujo)
    En esta ecuacion mpunto_w representa el flujo de vapor de agua que evapora el producto durante el proceso de secado y que es tomado por el aire circulante. mpunto_aire represente el flujo de aire que ingresa a la cámara de secado. W_producto representa el contenido de agua del producto, y W_flujo la humedad absoluta del aire que ingresa a la cámara de secado.

