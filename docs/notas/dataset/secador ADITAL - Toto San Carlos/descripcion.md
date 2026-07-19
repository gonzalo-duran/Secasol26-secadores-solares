# Dataset — Secador híbrido ADITAL, San Carlos (Salta). Ensayo estacional cosecha 2010

> Pre-completado por Claude (2026-07-18) a partir del capítulo 3 de la tesis doctoral
> y de la inspección directa de los tres `.xls`. Los ítems marcados ❓ los debe
> confirmar/completar Gonzalo.

## Identificación

- **Secador / instalación:** secador solar híbrido (solar + quemador de leña) ADITAL,
  San Carlos, Salta. Banco de 26 colectores de paso paralelo (7.5 × 0.94 × 0.1 m, dos
  grupos de 13) + caño maestro de 18 m de sección creciente + ventilador centrífugo
  4 HP / 900 rpm + intercambiador de banco de tubos sobre quemador de leña + túnel de
  secado de 14 m × 3 m × 1.85 m (cosecha 2010, carga máx ~4 t de pimiento).
- **Campaña:** ensayo estacional en funcionamiento híbrido, 2010-04-14 20:30 →
  2010-06-18 14:30 (cierre de cosecha 2010).
- **Referencia:** `docs/notas/papers/Tesis doctoral Gonzalo Duran - Capitulo 3.pdf`,
  §4 (págs. 64–77).

## Emplazamiento

- **Coordenadas:** 25°53′ S, 65°56′ O, ~1700 msnm (**confirmado por Gonzalo,
  2026-07-18**: las coordenadas de la tesis —22°52′59″ S, 64°40′00″ O— son un typo).
  Usar estas para el completado con NASA POWER.

## Adquisición

- **Dataloggers:** Campbell CR23X → variables del secador cada **10 min** (16 canales).
  Campbell CR1000 → variables climáticas a 3 m de altura cada **1 min** (radiación
  global horizontal, T, HR, velocidad y dirección de viento). **Los archivos
  compartidos casi no incluyen los datos del CR1000** (solo 4 días de radiación
  horizontal + T ambiente, al paso de 10 min: 10-may 00:00 → 13-may 23:50).
  **Crudos del CR1000:** existen, pero en un HDD no disponible durante el receso de
  invierno (confirmado 2026-07-18; recuperables recién al volver al INENCO,
  ~principios de agosto 2026).
- **Zona horaria:** hora local Argentina (UTC−3). ❓ confirmar.
- **Convención del timestamp:** lectura **instantánea** cada 10 min, NO promediada
  (**confirmado por Gonzalo, 2026-07-18**; los `med/min/max` diarios de las hojas son
  agregados hechos después en Excel, no del logger).
- **Formato:** `.xls` (Excel 97-2003). Timestamps como serial de Excel (epoch 1900).
  Decimal punto. Marcador de dato inválido: string `'NAN'`.

## Archivos y hojas

| Archivo | Hoja | Contenido |
|---|---|---|
| `…14-4-2010 a 28-4-2010.xls` (15 MB) | `14-4 a 28-4 2010` (1966×43) | **Período 1** (14-4 20:30 → 28-4 15:20): solo 8 canales de T (caño extremo/medio, col 1, col 2, entr cámara, quemador, chimenea, intercambiador) + med/min/max diarios intercalados. Sin HR ni T producto. |
| ídem | `28-4 a 14-5 2010` (2247×54) | **Período 2** (28-4 16:50 → 14-5 12:50): 13 canales (HR ent/sal + 11 T) + med/min/max diarios. |
| ídem | `15-5 a 18-6 2010` (4985×54) | **Período 3** (15-5 00:00 → 18-6 14:30): mismos 13 canales + agregados. ⚠️ **el orden quemador↔chimenea está invertido respecto al período 2**. |
| ídem | `graficos *` | Hojas de gráficos (sin datos útiles). |
| `…28-4-2010 a 14-5-2010.xls` (2 MB) | `CR1000_Table1 7-4ver` (2247×52) | Período 2 "estilo logger": 16 columnas — incluye **Radiación horizontal y T ambiente (solo 10→13 may)** y `DiffVolt(1)/(2)` crudos. |
| `…15-5-2010 a 18-6-2010.xls` (3.6 MB) | `Hoja1` (4985×15) | Período 3 limpio, sin agregados (13 canales). |

## Canales (nombres varían entre hojas)

Termocuplas K: `Temp entr/medio/sal caño` (caño maestro: extremo norte / medio /
salida sur), `Temp sal col1` (colector fila 3), `Temp sal col2` (fila 5),
`Temp salida inter` (intercambiador), `Temp quemador`, `Temp (gases) chimenea`,
`Temp entr/sal camara`, `Temp prod` (pimiento testigo). Higrómetros Vaisala HMP45A:
`HR entrada/salida` de cámara. `DiffVolt(1)/(2)`: puente de Wheatstone de Pt100
(T horno / gases), **sin calibrar** (mV, −727 a +89). ❓ ¿existe la curva de calibración?

## Calidad conocida (detectada en la inspección)

- Huecos: período 1 → 1 hueco de 220 min (15-abr 08:50); período 2 → 1 hueco de 6 h;
  período 3 → sin huecos. Entre hojas: ~1.5 h (28-4) y ~11 h (14→15 may).
- `'NAN'` string: 671 en P1, ~285 en P2 (quemador/chimenea), 371 en P3.
- **HR del período 2 sin convertir** (0.46–14.5 % y valores negativos → señal cruda);
  en período 3 sí están en % (1.8–72.7). ❓ confirmar si P2 tiene conversión pendiente.
- Sin viento ni presión en ningún archivo. Radiación solo horizontal y solo 4 días.
- Eventos operativos (tesis): colector 2 desconectado del caño maestro del 18 al 22-may
  (valores no representativos); 8-may y 16-may el secador posiblemente sin operar;
  últimos días de junio a carga parcial/intermitente.
- Rutina del quemador: carga ~60 kg de leña a las 08:00 (dura 2–3 h) y ~80–90 kg a las
  19:00 (3–4 h). Leña urundel/quebracho, PCI ≈ 4582 kcal/kg. Jornada 08:00–21:00/23:00.

## Configuración vinculada (para el modelo Secasol)

Colectores: 26 × (7.5 × 0.94 m), inclinación variable estacional (~30–35°), acimut
Norte. η medida 0.6–0.7 (típica), F_R(τα) ≈ 0.71. Caudal: v media 1.4 m/s en difusor
de 1.8 × 1.2 m, ρ ≈ 1.1 kg/m³ (≈ 6200 m³/h nominal RETScreen). Cámara 2010: túnel
14 m, 20 carros (~175 kg c/u). ❓ inclinación exacta de colectores durante abr–jun 2010.
