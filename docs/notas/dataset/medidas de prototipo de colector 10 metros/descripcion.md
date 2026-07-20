# Dataset — Prototipo de colector solar de aire de paso paralelo (10 m), INENCO Salta

## Identificación

- **Instalación:** prototipo de **colector solar de aire de paso paralelo de flujo**, con
  absorbedor de chapa galvanizada ondulada. Aire circula **por arriba y por debajo** del
  absorbedor (doble paso paralelo, misma dirección).
- **Descripción física:** Tesis doctoral Gonzalo Durán, **Capítulo 2** (`docs/notas/papers/
  Tesis doctoral Gonzalo Duran - Capitulo 2.pdf`). Construido en el Taller del INENCO
  (téc. Carlos Fernández). Este modelo de colector fue luego replicado en secadores
  industriales (ProSol Huacalera, ProSol San Carlos, **ADITAL San Carlos** — cap. 3, ProSol
  Santa María, este último acortado a 5.8 m).
- **Ensayo del archivo:** un día, **9 de junio** (año según nombre de archivo: 2007; el
  capítulo menciona la campaña de caracterización de 14 días en junio/diciembre de 2008 —
  ⚠️ posible ensayo preliminar o discrepancia de año, a confirmar por el autor). Lapso
  09:00–17:55 hora local, **paso 5 min** (108 registros). Mediodía solar ≈ 13:00.

## Emplazamiento

- **Sitio:** campo experimental del INENCO, UNSa, Sede Central, Salta Capital.
- **Coordenadas (del cap. 2):** **lat 24°48′ S (≈ −24.80°), lon 65°25′ O (≈ −65.42°)**,
  altitud ≈ 1187 m (Salta capital).
- **Orientación:** hacia el **Norte**, sobre soporte articulado que sigue la altura solar →
  los ensayos se hicieron con **incidencia normal** (sombra de marcador verificada). Por eso
  la irradiancia medida (columna `I`) es **global sobre el plano del colector (POA)**.

## Adquisición

- **Datalogger:** NUDAM 425, frecuencia de toma **1 a 5 min** (este archivo: 5 min).
- **Temperatura:** termocuplas **tipo K calibradas**, con protección contra IR (capuchones).
  Error absoluto **< 0.5 °C**.
- **Irradiancia:** piranómetro fotovoltaico **LI-COR LI-200**, coplanar con el colector
  (POA). Error a escala completa **10 %**.
- **Velocidad de flujo:** anemómetro de hilo caliente **TSI VelociCalc**, toma manual en
  entrada y salida (error 0.01 m/s para v < 20 m/s, T < 70 °C). El caudal másico se obtiene
  promediando v de entrada y salida: `ṁ = ρ·v·A_tr`.
- **Forzado del flujo:** ventilador centrífugo ¼ Hp en la entrada + registro articulado a la
  salida para variar el caudal (curva de eficiencia).

## Archivos y hojas

- **`Medidas 9-06-07.xls`** (⚠️ binario **gitignoreado**; solo se versiona este `.md`):
  - **`medido`** — **datos de campo** (la referencia para validar). 108 filas, header en la
    fila 0, 09:00→17:55, paso 5 min.
  - **`simulado`** — simulación propia de la tesis (paso sub-segundo; caudal simulado 0.8 kg/s,
    η sim ≈ 0.67, η med ≈ 0.65). **No** es dato de campo; sirve de contraste secundario.
  - **`grafico`** — hoja auxiliar de gráficos (prácticamente vacía).

## Canales (hoja `medido`)

| Columna | Significado | Unidad |
|---|---|---|
| `hora` | Hora local (solo hora, **sin fecha**) | HH:MM:SS |
| `tiempo` | Segundos desde el inicio (0…32100) | s |
| `Tin arr` / `Tin ab` | T de entrada, canal superior / inferior | °C |
| `Ta` | Temperatura ambiente | °C |
| `Tm ab` / `Tm arr` | T de flujo al centro del colector, inf. / sup. | °C |
| `Ts ab` / `Ts arr` | T de flujo a la **salida**, inf. / sup. | °C |
| `I` | **Irradiancia global sobre el plano del colector (POA)** | W/m² |
| `Tin med` | Media de entrada = (Tin arr + Tin ab)/2 | °C |
| `Tout med` | **Media de salida** = (Ts arr + Ts ab)/2 — **señal a validar** | °C |
| `Eficiencia medida` | (vacía en este archivo) | — |

Rangos observados: `Ta` 6.5–24.2 °C, `I` 16–842 W/m², `Tin med` 8.2–25.7 °C,
`Tout med` 6.1–31.4 °C.

## Calidad conocida (detectada en la inspección)

1. **Timestamp sin fecha:** `hora` es solo la hora del día. Para ingerir en Secasol hay que
   asignarle la fecha del ensayo (9-jun). ⚠️ Limitación: la ingesta de referencia actual
   (`ingerir_referencia`) parsearía "09:00:00" con la fecha de hoy — **hay que anteponer la
   fecha** (o agregar soporte de "fecha fija" a la config). *Pendiente de la fase 2.*
2. **Día de caudal ALTO (~0.8 kg/s):** el salto `Tout−Tin` es chico (media ≈ 1.8 °C, máx
   ≈ 7 °C) e incluso **negativo al amanecer** (colector frío enfría el aire). **Esto es
   físicamente correcto para caudal alto** (mismo Q_útil repartido en mucha más masa → ΔT
   bajo, η alta): balance de energía a mediodía (I≈800, A≈9.17 m², η≈0.65) → ṁ ≈ 0.8 kg/s,
   consistente con la hoja `simulado`. **No es un error de medición ni de etiquetado.** Es un
   buen punto de validación a **caudal alto** (complementa los días de 0.25–0.45 kg/s del
   cap. 2, de η ≈ 0.6).
3. **Asimetría entre canales:** `Ts arr` (superior) suele quedar más frío que `Ts ab`
   (inferior) — el cap. 2 lo atribuye a menor circulación por el canal superior. La media
   `Tout med` es la magnitud a comparar.
4. **`I` es POA** (piranómetro coplanar) → en Secasol se mapea como POA medida, **no** se
   transpone.

## Configuración vinculada (para el modelo Secasol)

**Colector** (cap. 2 — superficie de captación 9.76 m × 0.94 m, alto 0.1 m; 4 módulos de
2.44 m):
- **Tipo:** paso paralelo doble (aire por arriba y por debajo del absorbedor) → familia
  **Tipo 2/3/4** de Secasol (absorbedor a media altura). Elegir la variante de **ambos
  canales activos en paralelo** (ver `calculos/colector_tipos234_calc.py`).
- **Geometría:** largo **9.76 m**, ancho **0.94 m**, alto de cuerpo **0.10 m** (absorbedor a
  media altura → dos canales de ~0.045 m).
- **Cubierta:** policarbonato alveolar **4 mm**, anti-UV.
- **Absorbedor:** chapa galvanizada **ondulada** calibre 30, pintada **negro mate** (pintura
  de alta temperatura); ondulaciones paralelas al flujo; +10 % de área desplegada.
  Absortancia ≈ 0.9–0.95.
- **Aislante:** lana de vidrio **50 mm**, cara aluminizada hacia el flujo.
- **Fondo:** chapa galvanizada plana calibre 27.
- **Caudal de este ensayo:** **≈ 0.8 kg/s** (alto). η medida a mediodía ≈ 0.65.
- **Emplazamiento:** lat −24.80°, lon −65.42°, alt ≈ 1187 m, acimut Norte.
- **Parámetros HWB de referencia (cap. 2):** F_R·(τα) ≈ **0.7147**, F_R·U_L ≈ **45.079
  W/m²K** (útiles para contrastar / calibrar en la fase 3).

## Cómo validar en Secasol (P3 → "🔬 Validación con datos medidos") — **fase 2b**

1. En P3 configurar el colector con la geometría/materiales de arriba (Tipo 2, largo 9.76 m,
   ancho 0.94 m; materiales por defecto ya coinciden con la tesis).
2. Cargar el archivo, hoja `medido`, mapear: **timestamp = `hora`**, **valor = `Tout med`**
   (°C). Tildar **"el archivo trae solo la hora"** y poner **fecha = 9-jun-2007**.
3. Tildar **"forzar el colector con el clima medido del archivo"** → mapear
   **Ta = `Ta`** y **POA = `I`** (W/m²). Así el colector se valida **aislado**, forzado con el
   ambiente y la irradiancia del propio ensayo (no con NASA).
4. La app corre el colector sobre el período y calcula RMSE/MBE/R² contra `Tout med`.

### Resultado de validación (verificado end-to-end, S54)

Corriendo el pipeline 2b sobre este archivo (108 pares a 5 min), forzando con `Ta`+`I`
medidos, el modelo de colector de Secasol reproduce `Tout med` así (barriendo la velocidad de
diseño, que a caudal alto es el parámetro dominante):

| v_diseño [m/s] | RMSE [°C] | MBE [°C] | R² |
|---|---|---|---|
| 2.0 | 11.65 | +9.07 | 0.859 |
| 6.0 | 1.78 | +1.34 | 0.981 |
| **8.0** | **0.91** | **+0.20** | **0.987** |
| 10.0 | 1.28 | −0.51 | 0.984 |

A **v ≈ 8 m/s** (consistente con el día de **caudal alto ≈ 0.8 kg/s** por los dos canales) el
ajuste es **excelente** (RMSE < 1 °C, sesgo despreciable, R² 0.987) → **validación fuerte del
modelo de colector contra datos de campo**. La curva RMSE(v) es el objeto que la **fase 3
(calibración)** minimizará automáticamente.
