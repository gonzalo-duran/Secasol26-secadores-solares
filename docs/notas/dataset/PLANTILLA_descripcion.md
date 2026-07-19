# Plantilla — descripción de dataset medido

Copiar este archivo como `descripcion.md` dentro de la carpeta de cada dataset y
completar lo que aplique. Lo que no se sepa, dejarlo indicado como "desconocido"
(es información en sí misma para el acondicionamiento).

## Identificación

- **Secador / instalación:** (ej. ADITAL San Carlos; prototipo colector 10 m INENCO)
- **Campaña / período medido:** fechas de inicio y fin (aprox. está bien)
- **Referencia:** paper o capítulo de tesis que analiza estos datos (si está en
  `docs/notas/papers/`, nombrar el archivo)

## Emplazamiento

- **Lat / Lon / Altitud:** (para completar variables faltantes desde NASA POWER y
  estimar presión)

## Adquisición

- **Frecuencia de adquisición:** (5 min / 10 min / 15 min / …)
- **Zona horaria de los timestamps:** (hora local Argentina UTC−3, UTC, otra)
- **Convención del timestamp:** el valor registrado a las 10:00 ¿es lectura
  instantánea a las 10:00, o promedio del intervalo? Si es promedio, ¿del
  intervalo anterior (9:55–10:00) o del siguiente?
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
