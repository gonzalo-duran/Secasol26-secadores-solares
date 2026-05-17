#Papers: Cinética de Secado e Isotermas en Matrices Alimentarias

1. Análisis de Cinéticas de Secado por Producto

1.1. Comportamiento del secado en rodajas de durazno

* Referencia Bibliográfica: Kingsly et al. (2007).
* Configuración Experimental: Rodajas de durazno (Var. Shan-e-Punjab) con un grosor promedio de 3,5 ± 0,4 mm.
* Variables de Proceso: Temperaturas de 55 y 65 ºC con una velocidad de aire de 0,8 m/s en un secador de túnel de flujo cruzado. Se aplicaron pretratamientos de escaldado (50 ºC por 2 min) con metabisulfito de potasio (KMS) al 1% y ácido ascórbico al 1%.
* Resultados y Modelado:
  * Modelo de mejor ajuste: El modelo Logarítmico presentó los valores más altos de coeficiente de correlación (r^2 > 0,99) y los menores errores estadísticos registrados.
  * Parámetros Cinéticos: Los coeficientes de difusividad efectiva (D_{eff}) oscilaron entre 3,04 \times 10^{-12} y 4,41 \times 10^{-12} m^2/s.
  * Hallazgo principal: El secado ocurrió íntegramente en el periodo de tasa decreciente, donde el uso de KMS no solo previno el pardeamiento enzimático, sino que aumentó la permeabilidad celular, acelerando la transferencia de masa.

1.2. Estimación de la difusividad de humedad en papa con corrección por encogimiento

* Referencia Bibliográfica: Hassini et al. (2007).
* Configuración Experimental: Rodajas de papa (Var. Spunta) de 45 x 20 x 10 mm.
* Variables de Proceso: Temperaturas de 40, 55, 70 y 85 ºC con velocidades de aire de 0,5 y 1,0 m/s. Las muestras fueron escaldadas a 95 ºC durante 5 min para evitar el pardeamiento.
* Resultados y Modelado:
  * Modelo de mejor ajuste: Se empleó una solución numérica de la ecuación de transferencia de masa acoplada a la velocidad de la fase sólida debido al encogimiento.
  * Parámetros Cinéticos: La difusividad efectiva varió entre 3,55 \times 10^{-10} y 1,92 \times 10^{-9} m^2/s. Se identificó un coeficiente de contracción hidrológica promedio (\beta) de 1,37.
  * Hallazgo principal: El encogimiento de la papa fue calificado como "ideal", con una reducción de volumen del 77%; ignorar este fenómeno en el cálculo de difusividad induce errores sistemáticos de hasta el 90% debido a la reducción de las rutas difusivas.

1.3. Modelado de la cinética de secado en capa fina de ajíes rojos

* Referencia Bibliográfica: Kaleemullah y Kailappan (2006).
* Configuración Experimental: Ajíes rojos enteros (Var. Polyster) dispuestos en una capa de aproximadamente 1,6 cm de espesor.
* Variables de Proceso: Temperaturas de 50, 55, 60 y 65 ºC con una velocidad de aire de 0,4 m/s. No se aplicaron pretratamientos químicos.
* Resultados y Modelado:
  * Modelo de mejor ajuste: Los modelos de Page y Kaleemullah resultaron óptimos. El modelo de Kaleemullah destaca por incorporar la temperatura directamente en el término exponencial.
  * Parámetros Cinéticos: Los valores de D_{eff} aumentaron de 3,78 \times 10^{-9} a 7,10 \times 10^{-9} m^2/s al incrementar la temperatura del aire.
  * Hallazgo principal: Una temperatura de 55 ºC se determinó como el punto de equilibrio óptimo, minimizando el tiempo de proceso mientras se preservan los niveles de capsaicina (pungencia) y la coordenada de color rojo (a*), los cuales se degradan severamente a 65 ºC.

1.4. Secado en capa fina de pimiento rojo

* Referencia Bibliográfica: Akpinar (2003).
* Configuración Experimental: Rodajas de pimiento rojo procesadas en secador convectivo.
* Variables de Proceso: Temperaturas de entrada del aire de 55, 60 y 70 ºC con una velocidad de 1,5 m/s.
* Resultados y Modelado:
  * Modelo de mejor ajuste: Tras comparar 11 modelos, la "aproximación de la difusión" (variante de la solución de Fick de dos términos) describió satisfactoriamente las curvas (r = 0,9987).
  * Parámetros Cinéticos: Los coeficientes y constantes del modelo mostraron una dependencia directa con la temperatura del aire de entrada.
  * Hallazgo principal: La precisión en el modelado matemático de este producto es fundamental para optimizar el diseño industrial de secadores de flujo forzado.


--------------------------------------------------------------------------------


2. Matriz Técnica Comparativa de Difusividad y Transferencia de Masa

Producto	Temperatura (ºC)	Grosor/Capa (mm)	Modelo de mejor ajuste	Difusividad Efectiva (D_{eff} en m^2/s)	Referencia
Durazno	55 - 65	3,5	Logarítmico	3,04 \times 10^{-12} - 4,41 \times 10^{-12}	Kingsly et al., 2007
Papa	40 - 85	10,0	Numérico (Fick + Contracción)	3,55 \times 10^{-10} - 1,92 \times 10^{-9}	Hassini et al., 2007
Ajíes Rojos	50 - 65	16,0	Page / Kaleemullah	3,78 \times 10^{-9} - 7,10 \times 10^{-9}	Kaleemullah, 2006
Pimiento Rojo	55 - 70	S/D	Aproximación de Difusión	No reportado en el extracto	Akpinar, 2003


--------------------------------------------------------------------------------


3. Modelado Matemático y Parámetros de Ajuste

* Listado de Modelos: En los estudios analizados se aplicaron los siguientes modelos:
  1. Newton (o Lewis).
  2. Page.
  3. Modified Page.
  4. Henderson and Pabis.
  5. Logarítmico.
  6. Wang and Singh.
  7. Hustrulid and Flikke.
  8. Kaleemullah (específico, con dependencia térmica en el exponente).
  9. Solución analítica/numérica basada en Crank (base de los modelos difusivos).
* Análisis de Desempeño: La validación se realizó mediante rigurosidad estadística, seleccionando modelos con máximo coeficiente de determinación (r^2) y mínimos valores de chi-cuadrado reducido (\chi^2), error cuadrático medio (RMSE) y error de sesgo medio (MBE). En el caso de duraznos, el modelo logarítmico superó consistentemente a Page en estos indicadores.
* Influencia Térmica: La relación entre la difusividad y la temperatura absoluta se ajusta a la ecuación de Arrhenius: D_{eff} = D_0 \exp(-E_a / RT).
  * Para los ajíes rojos, se calculó una energía de activación (E_a) de 37,76 kJ/mol.
  * Para la papa, según el término exponencial de la ecuación empírica reportada por Hassini (31580 / RT), se determinó una E_a de 31,58 kJ/mol. Ambos valores reflejan la sensibilidad de la movilidad del agua frente al incremento de la energía térmica en la matriz.


--------------------------------------------------------------------------------


4. Conclusiones Técnicas Integradas

* Efecto de la Temperatura: El incremento térmico reduce drásticamente los tiempos de secado en todas las matrices ensayadas al aumentar la presión de vapor interna y los coeficientes de difusividad efectiva.
* Impacto de los Pretratamientos: El uso de KMS en duraznos y el escaldado en papas cumplen la doble función de prevenir el pardeamiento enzimático y alterar la estructura celular para facilitar la salida del agua, incrementando la tasa de transferencia de masa.
* Fenómeno de Encogimiento: En la papa, el encogimiento es de tipo "ideal" (reducción de volumen igual al volumen de agua evaporada), alcanzando una contracción del 77%. La utilización del coeficiente de contracción hidrológica (\beta = 1,37) es imperativa para evitar sobreestimaciones críticas de la difusividad.
* Periodo de Secado Predominante: No se identificó un periodo de tasa constante significativo; los procesos están gobernados por el periodo de tasa decreciente, lo que confirma que la resistencia interna a la difusión es el mecanismo controlante del transporte de humedad.

---------------------------------------------------------------------------------

A continuación se presentan los modelos matemáticos de cinética de secado y de isotermas de sorción aplicados en cada uno de los archivos analizados:

### 1. Kinetic Drying and Mathematical Modeling of Apple Slices on Dehydration Process
Se ajustaron **9 modelos** de relación de humedad:
*   Wang and Singh, Henderson and Pabis, Logarítmico, Page Modificado, Aproximación de la difusión, Page, Henderson and Pabis Modificado, Newton y **Midilli et al.** (este último resultó ser el más adecuado).

### 2. Drying kinetics of pomegranate arils
Se investigaron **4 modelos** de capa delgada:
*   Newton, Henderson and Pabis, **Page** (el más adecuado) y Page Modificado.

### 3. Effects of pretreatments and drying air temperature on drying behaviour of peach slice
Se evaluaron **6 modelos** de capa delgada:
*   Newton, Page, Page Modificado, Henderson and Pabis, **Logarítmico** (mejor ajuste) y Wang and Singh.

### 4. Estimation of potato moisture diffusivity from convective drying kinetics with correction for shrinkage
El estudio se centró en **métodos de cálculo de difusividad** en lugar de modelos empíricos de capa delgada:
*   **Método Analítico:** Basado en la solución de la ley de Fick para una lámina rectangular.
*   **Método Numérico:** Solución de balances de masa acoplados por la velocidad de encogimiento.
*   Para predecir la difusividad, se usó una relación tipo **Arrhenius** para la temperatura y una **ley exponencial** para el contenido de humedad.

### 5. Hot-air drying characteristics of red pepper (2002)
Se utilizaron modelos teóricos y empíricos:
*   Solución de la segunda ley de Fick (simplificada), Ecuación Exponencial y la **Ecuación de Page** (representó mejor las características).

### 6. Mathematical modeling of drying of potato slices in a forced convective dryer based on important parameters
Se examinaron **21 expresiones**, seleccionando las **8 mejores**:
*   Page, Page Modificado, Two-term, Aproximación de la difusión, Verma et al., **Midilli–Kucuk** (el mejor modelo), Weibull y Page Modificado II.

### 7. Mathematical modeling of hot-air drying kinetics of red bell pepper (var. Lamuyo) (2007)
Se aplicaron modelos de cinética e isotermas:
*   **Cinética:** Newton, Henderson–Pabis, Page y **Page Modificado** (mejor ajuste).
*   **Isotermas:** Modelo **GAB** (Guggenheim–Andersen–de Boer).

### 8. Mathematical modelling of thin layer drying kinetics of plum in a tunnel dryer
Se ajustaron **6 modelos** de capa delgada:
*   Newton, Page, Page Modificado, Henderson and Pabis, **Logarítmico** (mejor ajuste) y Wang and Singh.

### 9. Modelling of thin-layer drying kinetics of red chillies
Se seleccionaron y compararon **4 modelos**:
*   Lewis, Hustrulid and Flikke, **Page** y el **modelo de Kaleemullah** (estos dos últimos fueron los más adecuados).

### 10. Single layer drying behaviour of potato slices in a convective cyclone dryer and mathematical modeling
Se probaron **11 modelos** de capa delgada:
*   Newton, Page, Page Modificado (dos variantes), Henderson and Pabis, Logarítmico, Two-term, Two-term exponencial, Wang and Singh, **Aproximación de la difusión** (el más adecuado) y Verma et al.

### 11. Sorption isotherms and isosteric heat of sorption for grapes, apricots, apples and potatoes
Se evaluaron **11 modelos de isotermas** (6 de dos parámetros y 5 de tres parámetros):
*   **Modelos:** BET, GAB, Chung–Pfost, Chung–Pfost Modificado, Chen, **Halsey** (mejor ajuste general), Halsey Modificado, Henderson, Henderson Modificado, Iglesias–Chirife y Oswin.

### 12 y 13. The thin layer drying characteristics of organic apple slices
Se ajustaron **10 modelos** comunes de capa delgada:
*   Newton, Page, Henderson and Pabis, **Logarítmico** (mejor ajuste), Two-term, Two-term exponencial, Wang and Singh, Aproximación de la difusión, Henderson and Pabis Modificado y Midilli et al.

### 14. Thin layer drying of red pepper (2003)
Se testearon **11 ecuaciones** de capa delgada:
*   Newton, Page, Page Modificado, Henderson and Pabis, Logarítmico, Two-term, Wang and Singh, **Aproximación de la difusión** (el más satisfactorio), Verma et al., Henderson and Pabis Modificado y Two-term exponencial.

### 15. Water Sorption Isotherms of Raisins, Currants, Figs, Prunes and Apricots
Este archivo se centró específicamente en el uso de una ecuación:
*   Modelo **GAB**, ajustado mediante regresión no lineal directa para estimar parámetros como el contenido de humedad monocapa ($X_m$).
