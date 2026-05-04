SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

Hola, quiero crear un software de prediseño de secadores solares. 

Antes de empezar, te pongo en estado de situación. Soy un licenciado en Física y doctor en ciencias especialidad Energías Renovables que trabaja en el INENCO CONICET UNSa como Investigador Adjunto de la carrera de investigador científico del CONICET. Tengo mucha experiencia diseñando secadores solares de alimentos de muy amplia escala de producción. Ademas de eso soy docente de Transferencia de Calor y Materia, para el 5to año de licenciatura en Física, y Licenciatura en Energías Renovables, y docente en varios cursos de posgrado de la Maestría en Energías Renovables de la facultad de Ciencias Exactas de la UNSa, Argentina. Alguno de los cursos son transferencia de calor y materia, energía solar 1 y 2, simulacion de procesos termodinamicos aplicados a las energías renovables, secado solar industrial, eficiencia energética en la industria, y domótica para arquitectura bioclimatica.

Si bien se programar (visual basic y C++ hace muchos años), estuve utilizando en mis simulaciones numericas de sistemas solares y térmicos el software Simusol (www.simusol.org), en el cual me considero un experto. Entiendo la logica detrás del código escrito en python, pero estoy oxidado en la escritura y codeo, por lo que voy a necesitar que vos codees todo lo que te vaya solicitando.

El software de prediseño de secadores solares que quiero diseñar está pensado para ser utilizado en el contexto del curso de posgrado de la M.E.R UNSa "Secadores solares", entonces, está pensado para un usuario técnico, un ingeniero que tiene idea de transferencia de calor y quiere prediseñar secadores solares.

Me gustaría que el software se pueda compartir entre colegas, alumnos y comunidad científica en general, por lo que creo que deberia ser capaz de subirse a un repo en github. Tengo yo una cuenta en github, por lo que puedo usarla.

Respecto al codigo, creo que convendría que nos paremos en python con todos los paquetes de calculo científico (scipy, numpy, matplotlib, pvlib, etc), como "motor" para la parte de cálculo del software.

Te comento para que tengas en cuenta, por si es necesario, las especificaciones de mi hardware: DELL G15 5515 Ryzen 5000, 32 gb DDR4, geforce rtx 3050 4gb. Estoy corriendo Fedora 44 plasma 6.6.4. Tengo instalado vscode, para usar como IDE, pero no sé si está instalado python y bien linkeado a vscode. Ademas, recien hoy tengo Claude Pro por lo que no tengo ningun tipo de integracion con vscode ni nada.

Ademas de todo esto, soy un usuario completamente novato en Claude Pro y no use nunca Claude Code, por lo que me gustaría que comentes, y en funcion de este proyecto que te estoy describiendo, me digas cuales de las herramientas disponibles en una cuenta Claude Pro son adecuadas para este proyecto.

Volviendo al software, te comento, creo que es bueno que el programa cumpla con las siguientes características:

    a.- primero que nada, me parece importante que pueda funcionar con una interfaz que se muestre en un navegador web, y con las características tales de interfaz como para que se pueda ejecutar en distintos dispositivos atraves del navegador web (notebook, celular, tablet, etc)

    b.- quiero pensar en un diseño modular, distribuido en subpestañas o secciones, las cuales se encargarán de dimensionar distintas partes del sistema total, de manera tal que cada una de estas secciones pueda tomar informacion de las otras, y a su vez entregar datos a las otras secciones para poder llegar al diseño final.

Iremos trabajando progresivamente las secciones y su contenido, pero te defino a grandes rasgos cuales son las pestañas o secciones relevantes para el diseño:

1.- Pestaña de inicio, donde se va a elegir entre varias tipologias de secadores solares (secadores de tipo caja, secadores tipo armario, secadores con banco de colectores solares de aire y camara de secado)

2.- Pestaña de emplazamiento en el lugar de prediseño y estimacion de recursos climaticos en el lugar de prediseño.

3.- Pestaña de definicion y dimensionamiento de colectores solares

4.- Pestaña de definicion y dimensionamiento de camara de secado

5.- Pestaña de definicion y dimensionamiento de sistema de calentamiento auxiliar

6.- Pestaña de dimensionamiento de motores (en el caso de secadores de conveccion forzada)

7.- Pestaña de resultados finales


Ahora voy a ahondar en las secciones nombradas en la lista precedente. 

1.- Pestaña de inicio: Quiero que en esta pestaña inicial el usuario del software pueda especificar el tipo de secador que se piensa dimensionar, y el tipo de analisis que se va a realizar para el prediseño. 

1.1 El tipo de secador va a abrir distintas variantes en las posibilidades de diseño. Los tipos de secadores que se proponen son los siguientes:

    1.1.1 Secador solar de tipo caja: El secador solar de tipo caja es un secador solar de pequeña carga de producto (normalmente hasta 10 kg de producto fresco), y está destinado usualmente a usuarios domésticos o muy pequeños productores que no tienen grandes volumenes de producto fresco para secar, ni tienen necesidad de producir el deshidratado con gran velocidad. El secador solar de tipo caja no tiene colectores solares, y el efecto invernadero se produce en la camara de secado. La circulacion de aire en el secador es por conveccion natural, y puede estar asistido por una chimenea solar.

    1.1.2. Secador solar de tipo armario: El secador de tipo armario es un secador solar de carga media (de 0 a 100 kg de producto fresco). A diferencia del anterior, el secador de tipo armario tiene una cámara de secado (que puede ser opaca o translucida) y un banco de uno o dos colectores solares de aire. La circulacion de aire puede ser por medios naturales o forzados por ventilador o extractor eólico de turbina. Puede contar con mecanismos auxiliares de calentamiento de aire (quemadores de biomasa, resistencias electricas calentadoras de aire).

    1.1.3. Secador solar de gran escala con banco de colectores: Este tipo de secador solar es de gran capacidad de carga (100 kg a varias toneladas de producto fresco). A diferencia de los anteriores, la circulacion de aire se produce por medios forzados, con motor y ventilador. Cuenta con una cámara de secado, que puede ser translucida u opaca, y un banco de dos o mas colectores solares, con disposición tal que el aire caliente se recoge en un caño maestro de ventilacion, y es dirigido a la cámara de secado. Asimismo, puede contar con mecanismos auxiliares de calentamiento de aire (quemadores de biomasa, resistencias electricas calentadoras de aire).

1.2 El tipo de análisis que vamos a realizar para el prediseño abre dos posibilidades:

    1.2.1 Analisis de funcionamiento a lo largo de un día, a partir de datos horarios. El día de analisis se elegirá segun este criterio:
        1.2.1.1 Seleccion de un dia determinado por el usuario
        1.2.1.2 Criterio del día mas frio del año (menor temperatura ambiente media para ese dia)
        1.2.1.3 Criterio del día mas caluroso del año (mayor temperatura ambiente media para ese dia)
        1.2.1.4 Criterio de los cuatro dias caracteristicos (dias de los solsticios y equinoccios)
    1.2.2 Analisis de funcionamiento a lo largo de todo un año, a partir de datos horarios
    
2.- Pestaña de emplazamiento en el lugar de prediseño y estimacion de recursos climáticos: Esta pestaña tiene por objetivo emplazar y orientar el prediseño, y en funcion de ese emplazamiento y orientación, estimar el recurso energético en ese lugar, para poder usar esa informacion como insumo en las secciones que siguen en el diseño. Vamos a trabajar en esta pestaña de la siguiente manera:

    2.1 Como primer medida el usuario tiene que colocar el emplazamiento del diseño con la latitud y longitud del lugar. Con esa información, vamos a invocar la api de NASA Power y a partir de la ubicación del secador, vamos a consultar a la API para obtener los datos climaticos del lugar, que son los siguientes:
    
        2.1.1 Temperatura ambiente del lugar
        2.1.2 Radiación solar global sobre plano horizontal
        2.1.3 Velocidad de viento sobre suelo o a la menor altura que se disponga
        2.1.4 Presion atmosférica en el lugar
        2.1.5 Altura del lugar
        2.1.6 Humedad relativa ambiente
    
    Vamos a solicitar los datos de NASA Power y segun la eleccion del apartado 1.2 vamos a procesar esos datos para un día, o para todo un año
    
    2.2 Por otro lado, en esta seccion vamos a orientar el secador. La orientación que hagamos tiene que tomar los datos de acimut y pendiente, que tienen que ser definidos por el usuario. En estos angulos usaremos el criterio normal para sistemas solares, esto es, acimut 0 en el Sur, girando hacia el Norte pasando por el Este (sentido antihorario). Pendiente 0 para plano horizontal y creciendo hasta 90 para plano vertical.
    
Con todo esto, quiero que la pestaña de emplazamiento y estimacion de recursos pueda entregarte graficas de radiacion global horizontal y en el plano de coleccion, temperatura ambiente, velocidad de viento, presion atmosferica, humedad relativa. Ademas me gustaría que entregue al usuario un archivo csv con esta info recabada

-----Este archivo log se irá actualizando con sucesivas descripciones del resto de las pestañas-----
    
 
