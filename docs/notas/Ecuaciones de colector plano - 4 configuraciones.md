# Ecuaciones de balance de energía en colectores solares.

Estas ecuaciones tienen por objetivo modelar el comportamiento térmico de un colector solar de aire.
Tipos de colectores solares a modelar:
    1. Colector solar de placa plana, con absorbedor en el fondo del cuerpo del colector y circulación de aire por encima del absorbedor.
    2. Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulación de flujo. En esta configuracion el flujo circula por ambos canales (arriba y abajo del absorbedor).
    3. Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulación de flujo. En esta configuracion el flujo circula por el canal inferior (entre la cara inferior del absorbedor y fondo). El canal superior (entre cubierta y cara superior del absorbedor) está cerrado formando un recinto estanco.
    4. Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulacion de flujo. En esta configuracion el flujo circula por el canal superior (entre cubierta y cara superior del absorbedor). El canal inferior (entre cara inferior del absorbedor y fondo) forma un recinto estanco.

## Criterios constructivos:
    Para simplificar vamos a suponer que los distintos tipos de colectores se construyen con los mismos criterios constructivos. Así, los 4 colectores se construyen con mismos materiales. La diferencia fundamental entre cada uno de los 4 tipos es la ubicacion del absorbedor y la circulacion de flujo.
    El cuerpo de los colectores se construye conformando un cajón. El cajon se puede construir en madera, o mediante el uso de chapa galvanizada calibre 27, para las paredes externas e internas del cajón, y colocando aislación en el espacio entre paredes internas y externas (lana de vidrio, espuma de poliestireno).
    La cubierta del colector solar se construye mediante una lámina de material de alta transmitancia (policarbonato alveolar,plastico de invernaderos, vidrio)

## Hipotesis comunes a todos los modelos de colectores solares:
    1. Modelo cuasi estacionario: Se desprecia la acumulación de calor en todas las superficies que conforman el colector. Las variaciones temporales en temperaturas  de superficies y flujo de aire solo serán consecuencia de las variaciones temporales en las condiciones ambientales (temperatura ambiente, radiación solar, velocidad de viento), o consecuencia de variación temporal en el flujo de aire que circula por el interior del colector.
    2. Flujo de aire undireccional y desarrollado. Los cuatro modelos de colector pueden operar tanto con circulación natural como forzada. El flujo puede ser laminar, en transición o turbulento.
    3. La dirección predominante de transferencia de energía corresponde a la dirección longitudinal en sentido de la circulación de flujo - eje x. La dirección del eje y corresponde a la perpendicular en el sentido de las alturas del colector, que se miden perpendicularmente entre cubierta y fondo de colector. El eje z corresponde al ancho del colector, y supondremos que los elementos que conforman el colector (cubierta, cuerpo) son homogéneos e isotrópicos, por lo que en la dirección Z el flujo de calor es despreciable.
    4. Los colectores toman aire a temperatura ambiente, en el plano yz correspondiente a la coordenada x = 0, y el flujo de aire sale del colector através de la boca de salida, que se encuentra en el plano yz en la coordenada x = L, donde L es el largo del colector. El colector cumple la ecuación de continuidad, la unica entrada de flujo se encuentra en el plano yz para x=0, y la unica salida en el plano yz para x=L.
    5. Los colectores, en sus distintos tipos, son prismas regulares de largo L, alto A y ancho W.
    6. A fines prácticos y tomando en cuenta modelo cuasiestacionario, el absorbedor de calor, tendrá espesor o grosor despreciable. De esta manera la conducción de calor en el absorbedor se despreciará.
    7. En el caso en el que el cuerpo y paredes del colector se construyan con compuesto de doble chapa galvanizada y aislación entre chapas, y de forma similar a lo que sucede con el absorbedor de calor, se despreciará la conduccion de calor en las chapas galvanizadas. En esta configuracion la resistencia térmica de la pared compuesta chapa+aislantea+chapa será entonces la del aislante.
    8. Se considerará que las pérdidas de calor desde el absorbedor al ambiente se producen sobre todo en la dirección del eje y. Entonces, las pérdidas de calor por los laterales del colector (U_edge) son minimas, y se contabilizarán como parte de las pérdidas de calor en la dirección y. Así, siguiendo la notación usual U_edge << U_top + U_bottom, donde U_top U_bottom y U_edge representan las pérdidas de calor desde el absorbedor por arriba, por debajo y por los costados del colector.
    9. Suponemos que la absortividad de la cubierta es despreciable.
    
## 1. Colector solar de placa plana, con absorbedor en el fondo del cuerpo del colector y circulación de aire por encima del absorbedor:
    Las ecuaciones describen la transferencia de calor desde un elemento diferencial de cubierta dA_cub = dx * W
    La relacion entre las diversas alturas es: Alto_col = esp_cub + Alto_c1 + esp_ais
    En forma similar a la cubierta, las ecuaciones describen la transferencia de calor desde un elemento diferencial de absorbedor dA_abs = dx * W_abs
    El ancho del absorbedor, W_abs puede ser mayor que el ancho de colector W para representar colectores con absorbedor conformado en chapa galvanizada ondulada
    
### Nomenclatura:
    Alto del colector: Alto_col
    Altura del canal entre absorbedor y colector: Alto_c1
    Area superficial de la cubierta: A_cub
    Espesor de la aislación: esp_ais
    Espesor de la cubierta: esp_cub
    Emisividad IR de la cubierta: em_cub
    Emisividad IR del absorbedor: em_abs
    Constante de Stefan Boltzman: sigmaSB
    Temperatura ambiente: Tamb
    Temperatura de cielo: Tcie
    Temperatura de la cara externa de la cubierta: Tcub_e
    Temperatura de la cara interna de la cubierta: Tcub_i
    Temperatura del aire en el nodo i: Tair_i
    Temperatura del aire en el nodo i-1: Tair_(i-1)
    Temperatura del absorbedor: T_abs
    Temperatura de la cara externa del cuerpo del colector: T_bot
    Coeficiente convectivo para viento: h_wind
    Coeficiente convectivo para flujo interno: h_int1
    Conductividad térmica de la cubierta: k_cub
    Conductividad térmica del aislante: k_ais
    Flujo masico circulante: mpunto_1
    Calor específico aire: cp_air
    Transmitancia de cubierta: tau_cub
    Absortividad del absorbedor: alfa_abs
    Irradiacion global normal sobre cubierta: I_g
            
### balance de calor para la cubierta:
    #### Desde la cara externa la cubierta pierde calor al ambiente por convección debido a las ráfagas de viento, mediante la expresión: 
        h_wind * (Tcub_e - Tamb) * dA_cub
    #### Desde la cara externa la cubierta pierde calor al cielo por radiación, mediante la expresión: 
        em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴)
    #### En el interior de la cubierta hay conduccion de calor con la expresión: 
        -k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor: 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### Desde la cara interna de la cubierta hay transferencia de calor por conveccion al flujo de aire que circula por el canal:
        h_int1 * (T_abs - Tcub_i) * dA_cub
    #### La ecuacion de balance de calor para la cubierta es:
        h_wind * (Tcub_e - Tamb) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴) - k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴) +  h_int1 * (T_abs - Tcub_i) * dA_cub = 0
    
### balance de calor para el flujo de aire:
    #### intercambio convectivo desde la cara interna de la cubierta al fujo:
        h_int1 * (Tair_i - Tcub_i) * dA_cub
    #### intercambio convectivo desde el absorbedor al flujo:
        h_int1 * (Tair_i - T_abs) * dA_abs
    #### ganancia de calor por transporte de masa:
        mpunto_1 * cp_air * (Tair_i-Tair_(i-1))
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int1 * (Tair_i - Tcub_i) * dA_cub +  h_int1 * (Tair_i - T_abs) * dA_cub + mpunto_1 * cp_air * (Tair_i-Tair_(i-1)) = 0

### balance de calor para el absorbedor: 
    #### intercambio convectivo desde el absorbedor al flujo:
        h_int1 * (Tair_i - T_abs) * dA_abs
    #### ganancia de energía en absorbedor por radiación incidente:
        I_g * tau_cub * alfa_abs * dA_abs
    #### intercambio radiativo entre cubierta y absorbedor:
        em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(Tcub_i + 273.15)⁴)
    #### perdida de calor por conducción al cuerpo del colector
        -k_ais/esp_ais * (T_abs - T_bot) * dA_abs
    #### La ecuacion de balance de calor para el absorbedor es: 
        h_int1 * (Tair_i - T_abs) * dA_abs + I_g * tau_cub * alfa_abs * dA_abs + em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(Tcub_i + 273.15)⁴) -k_ais/esp_ais * (T_abs - T_bot) * dA_abs = 0
        
### balance de calor para el cuerpo del colector:
    #### ganancia de calor por conduccion desde el absorbedor al fondo del colector:
        -k_ais/esp_ais * (T_abs - T_bot) * dA_abs
    #### perdida de calor convectiva desde el fondo del colector al ambiente:
        h_wind * (T_bot - Tamb) * dA_cub
    #### balance de calor del fondo al ambiente:
        -k_ais/esp_ais * (T_abs - T_bot) * dA_abs +  h_wind * (T_bot - Tamb) * dA_cub = 0
        
## 2. Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulación de flujo. Flujo circulante por ambos canales (arriba y abajo del absorbedor).
    Las ecuaciones describen la transferencia de calor desde un elemento diferencial de cubierta dA_cub = dx * W
    La relacion entre las diversas alturas es: Alto_col = esp_cub + Alto_c1 + Alto_c2 + esp_ais
    Al colocar el absorbedor a medio camino entre el fondo del colector y la cubierta se forman dos canales de circulacion de flujo. 
    Los dos canales son recintos estancos, cada uno con una entrada y una salida de flujo, y no tienen comunicación entre ellos.
    En forma similar a la cubierta, las ecuaciones describen la transferencia de calor desde un elemento diferencial de absorbedor dA_abs = dx * W_abs
    El ancho del absorbedor, W_abs puede ser mayor que el ancho de colector W para representar colectores con absorbedor conformado en chapa galvanizada ondulada
    El flujo por cada uno de los canales puede ser distinto.
    Como no consideramos conducción de calor en el absorbedor, las dos caras de la placa absorbedora no tienen diferencia de temperatura y ambas se encuentran a T_abs
    
### Nomenclatura:
    Alto del colector: Alto_col
    Altura del canal entre absorbedor y colector: Alto_c1
    Altura del canal entre absorbedor y fondo: Alto_c2
    Area superficial de la cubierta: A_cub
    Espesor de la aislación: esp_ais
    Espesor de la cubierta: esp_cub
    Emisividad IR de la cubierta: em_cub
    Emisividad IR del absorbedor: em_abs
    Constante de Stefan Boltzman: sigmaSB
    Temperatura ambiente: Tamb
    Temperatura de cielo: Tcie
    Temperatura de la cara externa de la cubierta: Tcub_e
    Temperatura de la cara interna de la cubierta: Tcub_i
    Temperatura del aire en el nodo i canal superior: Taircs_i
    Temperatura del aire en el nodo i-1 canal superior: Taircs_(i-1)
    Temperatura del aire en el nodo i canal inferior: Tairci_i
    Temperatura del aire en el nodo i-1 canal inferior: Tairci_(i-1)
    Temperatura del absorbedor: T_abs
    Temperatura de la cara interna del cuerpo del colector: T_int
    Temperatura de la cara externa del cuerpo del colector: T_bot
    Coeficiente convectivo para viento: h_wind
    Coeficiente convectivo para flujo del canal superior: h_int1
    Coeficiente convectivo para el flujo del canal inferior: h_int2
    Conductividad térmica de la cubierta: k_cub
    Conductividad térmica del aislante: k_ais
    Flujo masico circulante por canal superior: mpunto_1
    Flujo masico circulante por canal inferior: mpunto_2
    Calor específico aire: cp_air
    Transmitancia de cubierta: tau_cub
    Absortividad del absorbedor: alfa_abs
    Irradiacion global normal sobre cubierta: I_g

### balance de calor para la cubierta:
    #### Desde la cara externa la cubierta pierde calor al ambiente por convección debido a las ráfagas de viento, mediante la expresión: 
        h_wind * (Tcub_e - Tamb) * dA_cub
    #### Desde la cara externa la cubierta pierde calor al cielo por radiación, mediante la expresión: 
        em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴)
    #### En el interior de la cubierta hay conduccion de calor con la expresión: 
        -k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### Desde la cara interna de la cubierta hay transferencia de calor por conveccion al flujo de aire que circula por el canal superior:
        h_int1 * (T_abs - Tcub_i) * dA_cub
    #### La ecuacion de balance de calor para la cubierta es:
        h_wind * (Tcub_e - Tamb) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴) - k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴) +  h_int1 * (T_abs - Tcub_i) * dA_cub = 0\

### balance de calor para el flujo de aire en el canal superior:
    #### intercambio convectivo desde la cara interna de la cubierta al flujo del canal superior:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub
    #### intercambio convectivo desde el absorbedor al flujo:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### ganancia de calor por transporte de masa:
        mpunto_1 * cp_air * (Taircs_i-Taircs_(i-1))
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub +  h_int1 * (Taircs_i - T_abs) * dA_cub + mpunto_1 * cp_air * (Taircs_i-Tair_(i-1)) = 0
        
### balance de calor para el absorbedor:
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### intercambio convectivo desde el absorbedor al flujo del canal superior:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio radiativo entre cubierta y fondo:
        em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴)
    #### ganancia de energía en absorbedor por radiación incidente:
        I_g * tau_cub * alfa_abs * dA_abs
    #### La ecuacion de balance de calor apara el absorbedor es:
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)+ h_int1 * (Taircs_i - T_abs) * dA_abs+h_int2 * (Tairci_i - T_abs) * dA_abs+em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴) = I_g * tau_cub * alfa_abs * dA_abs

### balance de calor para el flujo de aire en el canal inferior:
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio convectivo desde el fondo del colector al flujo:
        h_int2 * (Tairci_i - T_int) * dA_abs
    #### ganancia de calor por transporte de masa:
        mpunto_2 * cp_air * (Tairci_i-Tairci_(i-1))
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int2 * (Tairci_i - T_abs) * dA_abs + h_int2 * (Tairci_i - T_int) * dA_abs + mpunto_2 * cp_air * (Tairci_i-Tairci_(i-1))= 0
        
### balance de calor para el cuerpo del colector:
    #### ganancia de calor por conduccion desde la cara interna a la externa del fondo del colector:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs
    #### perdida de calor convectiva desde el fondo del colector al ambiente:
        h_wind * (T_bot - Tamb) * dA_cub
    #### balance de calor del fondo al ambiente:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs +  h_wind * (T_bot - Tamb) * dA_cub = 0

##  3.Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulación de flujo. Flujo circulante por canal inferior.
    Las ecuaciones describen la transferencia de calor desde un elemento diferencial de cubierta dA_cub = dx * W
    La relacion entre las diversas alturas es: Alto_col = esp_cub + Alto_c1 + Alto_c2 + esp_ais
    Al colocar el absorbedor a medio camino entre el fondo del colector y la cubierta se forman dos canales de circulacion de flujo. 
    En esta configuracion el canal superior está ciego, forma un recinto estanco sin entrada ni salida de flujo. El canal  inferior si tiene circulacion de flujo, con una entrada y una salida.
    En forma similar a la cubierta, las ecuaciones describen la transferencia de calor desde un elemento diferencial de absorbedor dA_abs = dx * W_abs
    El ancho del absorbedor, W_abs puede ser mayor que el ancho de colector W para representar colectores con absorbedor conformado en chapa galvanizada ondulada.
    Como no consideramos conducción de calor en el absorbedor, las dos caras de la placa absorbedora no tienen diferencia de temperatura y ambas se encuentran a T_abs
    
### Nomenclatura:
    Alto del colector: Alto_col
    Altura del canal entre absorbedor y colector: Alto_c1
    Altura del canal entre absorbedor y fondo: Alto_c2
    Area superficial de la cubierta: A_cub
    Espesor de la aislación: esp_ais
    Espesor de la cubierta: esp_cub
    Emisividad IR de la cubierta: em_cub
    Emisividad IR del absorbedor: em_abs
    Constante de Stefan Boltzman: sigmaSB
    Temperatura ambiente: Tamb
    Temperatura de cielo: Tcie
    Temperatura de la cara externa de la cubierta: Tcub_e
    Temperatura de la cara interna de la cubierta: Tcub_i
    Temperatura del aire en el nodo i canal superior: Taircs_i
    Temperatura del aire en el nodo i-1 canal superior: Taircs_(i-1)
    Temperatura del aire en el nodo i canal inferior: Tairci_i
    Temperatura del aire en el nodo i-1 canal inferior: Tairci_(i-1)
    Temperatura del absorbedor: T_abs
    Temperatura de la cara interna del cuerpo del colector: T_int
    Temperatura de la cara externa del cuerpo del colector: T_bot
    Coeficiente convectivo para viento: h_wind
    Coeficiente convectivo para flujo del canal superior: h_int1
    Coeficiente convectivo para el flujo del canal inferior: h_int2
    Conductividad térmica de la cubierta: k_cub
    Conductividad térmica del aislante: k_ais
    Flujo masico circulante por canal inferior: mpunto_2
    Calor específico aire: cp_air
    Transmitancia de cubierta: tau_cub
    Absortividad del absorbedor: alfa_abs
    Irradiacion global normal sobre cubierta: I_g

### balance de calor para la cubierta:
    #### Desde la cara externa la cubierta pierde calor al ambiente por convección debido a las ráfagas de viento, mediante la expresión: 
        h_wind * (Tcub_e - Tamb) * dA_cub
    #### Desde la cara externa la cubierta pierde calor al cielo por radiación, mediante la expresión: 
        em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴)
    #### En el interior de la cubierta hay conduccion de calor con la expresión: 
        -k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### Desde la cara interna de la cubierta hay transferencia de calor por conveccion al aire del canal superior:
        h_int1 * (T_abs - Tcub_i) * dA_cub
    #### La ecuacion de balance de calor para la cubierta es:
        h_wind * (Tcub_e - Tamb) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴) - k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴) +  h_int1 * (T_abs - Tcub_i) * dA_cub = 0\

### balance de calor para aire en el canal superior:
    #### intercambio convectivo desde la cara interna de la cubierta al flujo del canal superior:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub
    #### intercambio convectivo desde el absorbedor al flujo:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub +  h_int1 * (Taircs_i - T_abs) * dA_cub = 0
        
### balance de calor para el absorbedor:
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### intercambio convectivo desde el absorbedor al flujo del canal superior:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio radiativo entre cubierta y fondo:
        em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴)
    #### ganancia de energía en absorbedor por radiación incidente:
        I_g * tau_cub * alfa_abs * dA_abs
    #### La ecuacion de balance de calor apara el absorbedor es:
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)+ h_int1 * (Taircs_i - T_abs) * dA_abs+h_int2 * (Tairci_i - T_abs) * dA_abs+em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴) = I_g * tau_cub * alfa_abs * dA_abs

### balance de calor para el flujo de aire en el canal inferior:
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio convectivo desde el fondo del colector al flujo:
        h_int2 * (Tairci_i - T_int) * dA_abs
    #### ganancia de calor por transporte de masa:
        mpunto_2 * cp_air * (Tairci_i-Tairci_(i-1))
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int2 * (Tairci_i - T_abs) * dA_abs + h_int2 * (Tairci_i - T_int) * dA_abs + mpunto_2 * cp_air * (Tairci_i-Tairci_(i-1))= 0
        
### balance de calor para el cuerpo del colector:
    #### ganancia de calor por conduccion desde la cara interna a la externa del fondo del colector:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs
    #### perdida de calor convectiva desde el fondo del colector al ambiente:
        h_wind * (T_bot - Tamb) * dA_cub
    #### balance de calor del fondo al ambiente:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs +  h_wind * (T_bot - Tamb) * dA_cub = 0

##  4. Colector solar de placa plana con absorbedor colocado a media altura entre la cubierta y el fondo, formando dos canales de circulación de flujo. Flujo circulante por canal superior.
    Las ecuaciones describen la transferencia de calor desde un elemento diferencial de cubierta dA_cub = dx * W
    La relacion entre las diversas alturas es: Alto_col = esp_cub + Alto_c1 + Alto_c2 + esp_ais
    Al colocar el absorbedor a medio camino entre el fondo del colector y la cubierta se forman dos canales de circulacion de flujo. 
    En esta configuracion el canal superior tiene circulacion. El canal  inferior forma un recinto estanco sin entrada ni salida de flujo.
    En forma similar a la cubierta, las ecuaciones describen la transferencia de calor desde un elemento diferencial de absorbedor dA_abs = dx * W_abs
    El ancho del absorbedor, W_abs puede ser mayor que el ancho de colector W para representar colectores con absorbedor conformado en chapa galvanizada ondulada.
    Como no consideramos conducción de calor en el absorbedor, las dos caras de la placa absorbedora no tienen diferencia de temperatura y ambas se encuentran a T_abs
    
### Nomenclatura:
    Alto del colector: Alto_col
    Altura del canal entre absorbedor y colector: Alto_c1
    Altura del canal entre absorbedor y fondo: Alto_c2
    Area superficial de la cubierta: A_cub
    Espesor de la aislación: esp_ais
    Espesor de la cubierta: esp_cub
    Emisividad IR de la cubierta: em_cub
    Emisividad IR del absorbedor: em_abs
    Constante de Stefan Boltzman: sigmaSB
    Temperatura ambiente: Tamb
    Temperatura de cielo: Tcie
    Temperatura de la cara externa de la cubierta: Tcub_e
    Temperatura de la cara interna de la cubierta: Tcub_i
    Temperatura del aire en el nodo i canal superior: Taircs_i
    Temperatura del aire en el nodo i-1 canal superior: Taircs_(i-1)
    Temperatura del aire en el nodo i canal inferior: Tairci_i
    Temperatura del aire en el nodo i-1 canal inferior: Tairci_(i-1)
    Temperatura del absorbedor: T_abs
    Temperatura de la cara interna del cuerpo del colector: T_int
    Temperatura de la cara externa del cuerpo del colector: T_bot
    Coeficiente convectivo para viento: h_wind
    Coeficiente convectivo para flujo del canal superior: h_int1
    Coeficiente convectivo para el flujo del canal inferior: h_int2
    Conductividad térmica de la cubierta: k_cub
    Conductividad térmica del aislante: k_ais
    Flujo masico circulante por canal inferior: mpunto_2
    Calor específico aire: cp_air
    Transmitancia de cubierta: tau_cub
    Absortividad del absorbedor: alfa_abs
    Irradiacion global normal sobre cubierta: I_g

### balance de calor para la cubierta:
    #### Desde la cara externa la cubierta pierde calor al ambiente por convección debido a las ráfagas de viento, mediante la expresión: 
        h_wind * (Tcub_e - Tamb) * dA_cub
    #### Desde la cara externa la cubierta pierde calor al cielo por radiación, mediante la expresión: 
        em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴)
    #### En el interior de la cubierta hay conduccion de calor con la expresión: 
        -k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### Desde la cara interna de la cubierta hay transferencia de calor por conveccion al aire del canal superior:
        h_int1 * (T_abs - Tcub_i) * dA_cub
    #### La ecuacion de balance de calor para la cubierta es:
        h_wind * (Tcub_e - Tamb) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_e + 273.15)⁴ -(Tcie + 273.15)⁴) - k_cub/esp_cub * (Tcub_i - Tcub_e) * dA_cub + em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴) +  h_int1 * (T_abs - Tcub_i) * dA_cub = 0\

### balance de calor para el flujo de aire en el canal superior:
    #### intercambio convectivo desde la cara interna de la cubierta al flujo del canal superior:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub
    #### intercambio convectivo desde el absorbedor al flujo:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### ganancia de calor por transporte de masa:
        mpunto_1 * cp_air * (Taircs_i-Taircs_(i-1))
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int1 * (Taircs_i - Tcub_i) * dA_cub +  h_int1 * (Taircs_i - T_abs) * dA_cub + mpunto_1 * cp_air * (Taircs_i-Tair_(i-1)) = 0
        
### balance de calor para el absorbedor:
    #### Desde la cara interna de la cubierta hay transferencia de calor por radiacion hacia el absorbedor (canal superior): 
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)
    #### intercambio convectivo desde el absorbedor al flujo del canal superior:
        h_int1 * (Taircs_i - T_abs) * dA_abs
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio radiativo entre cubierta y fondo:
        em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴)
    #### ganancia de energía en absorbedor por radiación incidente:
        I_g * tau_cub * alfa_abs * dA_abs
    #### La ecuacion de balance de calor apara el absorbedor es:
        em_cub * sigmaSB * dA_cub * ((Tcub_i + 273.15)⁴ -(T_abs + 273.15)⁴)+ h_int1 * (Taircs_i - T_abs) * dA_abs+h_int2 * (Tairci_i - T_abs) * dA_abs+em_abs * sigmaSB * dA_abs * ((T_abs + 273.15)⁴ -(T_int + 273.15)⁴) = I_g * tau_cub * alfa_abs * dA_abs

### balance de calor para el flujo de aire en el canal inferior:
    #### intercambio convectivo desde el absorbedor al flujo del canal inferior:
        h_int2 * (Tairci_i - T_abs) * dA_abs
    #### intercambio convectivo desde el fondo del colector al flujo:
        h_int2 * (Tairci_i - T_int) * dA_abs
    #### La ecuacion de balance de calor para el flujo de aire circulante es:
        h_int2 * (Tairci_i - T_abs) * dA_abs + h_int2 * (Tairci_i - T_int) * dA_abs = 0
        
### balance de calor para el cuerpo del colector:
    #### ganancia de calor por conduccion desde la cara interna a la externa del fondo del colector:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs
    #### perdida de calor convectiva desde el fondo del colector al ambiente:
        h_wind * (T_bot - Tamb) * dA_cub
    #### balance de calor del fondo al ambiente:
        -k_ais/esp_ais * (T_int - T_bot) * dA_abs +  h_wind * (T_bot - Tamb) * dA_cub = 0
