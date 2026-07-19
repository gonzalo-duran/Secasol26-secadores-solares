# Plantilla — descripción de dataset medido

Copiar este archivo como `descripcion.md` dentro de la carpeta de cada dataset y
completar lo que aplique. Lo que no se sepa, dejarlo indicado como "desconocido"
(es información en sí misma para el acondicionamiento).

## Identificación

- **Secador / instalación:** Este set de datos medidos corresponde al secador ADITAL San Carlos. Los resultados mas destacables de todo el set se mostraron y analizaron en /home/gduran/proyectos/secador_solar/docs/notas/papers/Tesis doctoral Gonzalo Duran - Capitulo 3.pdf. 
- **Campaña / período medido:** Fecha de inicio 14-4-2010. Fecha de finalizacion 18-6-2010
- **Referencia:** /home/gduran/proyectos/secador_solar/docs/notas/papers/Tesis doctoral Gonzalo Duran - Capitulo 3.pdf

## Emplazamiento

- **Lat / Lon / Altitud:**  25° 54' 00'' S, 65° 56' 00'' O, 1700 msnm

## Adquisición

- **Frecuencia de adquisición:** 10 min
- **Zona horaria de los timestamps:** hora local Argentina UTC−3
- **Convención del timestamp:** valores instantaneos tomados en el instante correspondiente, no promediados en el lapso de adquisición
- **Formato del archivo:** separador (coma/punto y coma/tab), decimal (coma o
  punto), formato de fecha (dd/mm/aaaa, etc.)

## Variables (una línea por columna del archivo)

| Columna | Qué mide | Unidad | Sensor y ubicación física |
|---------|----------|--------|---------------------------|
| ej. `T5` | T de flujo a la salida del colector | °C | termocupla K, boca de salida |
| ej. `RAD` | global en plano de colector | W/m² | piranómetro, β=20°, mirando N |

Para radiación indicar **inclinación y acimut del sensor** (¿plano del colector u
horizontal?). Para viento (si hubiera), **altura del anemómetro**.

## Configuración del secador durante la campaña

- Dimensiones de colector / cámara, caudal o velocidad de trabajo, producto y
  carga si hubo secado (o referencia al capítulo donde está descripto).
- Modo de operación: ¿ventilador (caudal conocido/constante?) o convección
  natural? ¿Quemador auxiliar activo, con qué rutina?

## Calidad conocida

- Huecos, cortes de logger, sensores que fallaron, períodos a descartar,
  cualquier anomalía que recuerdes.
