# Secasol — Prediseñador de Secadores Solares
### Contenido para presentación · Seminario INENCO · 45 min

> **Cómo usar este archivo:** cada bloque separado por `---` es una diapositiva.
> El texto bajo **🎤 Notas** es para vos (orador), no va en la slide.
> Llevá este markdown a Claude chat y pedile que lo renderice como deck visual.
> **Timing total ≈ 45 min:** Intro 5' · Recorrido de capacidades 15' · Modelos físicos 8' · Demo 10' · Validación + cierre 5' · margen Q&A 2'.

---

## Secasol
### Prediseñador de secadores solares
**[Tu nombre]** — GEEDSP / INENCO (CONICET–UNSa)
Seminario INENCO · Junio 2026

🎤 **Notas:** Presentación "en sociedad" del software. Arrancar con una frase gancho: *"Una herramienta para diseñar secadores solares antes de cortar la primera chapa."*

---

## De qué va esta charla
1. **Por qué** un prediseñador de secadores solares
2. **Qué es Secasol** y cómo se usa (flujo de 7 pasos)
3. **Recorrido de capacidades** — tipologías, modos, subsistemas
4. **Los modelos físicos** detrás (y cómo los validamos)
5. **Demo en vivo** — un prediseño de punta a punta
6. **Hoja de ruta** y cierre

🎤 **Notas:** ~30 segundos. Marcar que habrá demo en vivo para mantener la atención.

---

# 1 · Motivación
**(≈ 5 min)**

---

## El problema del diseño de secadores solares
- El secado solar es clave para **agregar valor** a la producción regional (frutas, hortalizas, hierbas, carnes).
- Diseñar un secador implica **acoplar** muchos subsistemas: colector, cámara, producto, clima, movimiento de aire, calentamiento auxiliar.
- Hoy ese diseño se hace **a mano, fragmentado**, o se sobredimensiona "por las dudas".
- **No existe** una herramienta libre e integrada que prediseñe el sistema completo con física real y clima del sitio.

🎤 **Notas:** Conectar con la experiencia del grupo: secadores transferidos al medio (charqui, ADITAL, etc.). Mencionar que el sobredimensionado cuesta plata y energía.

---

## La propuesta
> **Secasol:** un prediseñador integral que toma el **clima real del emplazamiento** y la **física acoplada** de calor y masa, y te dice si tu secador **seca lo que querés, en el tiempo que querés.**

- Herramienta de **prediseño** (orden de magnitud), no de certificación.
- Pensada para **investigadores, técnicos y formación** (MER-UNSa / INENCO).
- Libre, accesible por navegador, sin instalar nada.

🎤 **Notas:** Subrayar "prediseño": es para explorar y dimensionar rápido, no para reemplazar el cálculo de detalle ni la medición. Esto te cubre ante preguntas de rigor.

---

# 2 · Qué es Secasol
**(≈ 5 min)**

---

## En una imagen
- App web (**Streamlit**) — corre en el navegador, sin instalación.
- El usuario configura el sistema **pestaña a pestaña**.
- Todo se integra en un único objeto `Proyecto` y se resuelve con un **balance global acoplado**.

`[SLIDE VISUAL: screenshot de la app — header INENCO/GEEDSP + navegación lateral P1–P7]`

🎤 **Notas:** Acá va un screenshot real de la app abierta. Mostrar el header institucional y el menú lateral de 7 secciones.

---

## El flujo de trabajo: 7 pasos
1. **Tipología** — tipo de secador y modo de análisis
2. **Emplazamiento** — coordenadas + clima satelital (NASA POWER)
3. **Colector** — materiales, geometría, velocidad de aire
4. **Cámara** — geometría, producto a secar, carga
5. **Auxiliar** — calentamiento de respaldo (opcional)
6. **Motor** — ventilador o chimenea solar
7. **Resultados** — corrida completa + reporte

🎤 **Notas:** El flujo es guiado pero flexible. Cada pestaña escribe en el proyecto central; P7 es la "fuente de verdad" que integra todo con un lazo iterativo (Picard).

---

# 3 · Recorrido de capacidades
**(≈ 15 min — el corazón de la charla)**

🎤 **Notas:** Esta es la parte donde mostrás que el proyecto es **grande**. No te detengas en cada detalle; mostrá amplitud y profundidad. Una slide por subsistema.

---

## Tres tipologías de secador
| Tipología | Qué es | Escala |
|---|---|---|
| **Caja** | Colector y cámara integrados; el sol entra directo (techo translúcido). Suele ser convección natural. | Chica (familiar, baja inversión) |
| **Armario** | Colector externo + cámara con bandejas; aire forzado o natural. | Media (mejor control de T) |
| **Gran escala** | Banco de colectores + cámara industrial (lotes o túnel). | Comercial (cientos–miles de kg) |

🎤 **Notas:** La tipología define qué subsistemas se habilitan. Mostrar los esquemas SVG de circuito de aire (caja vs armario) que ya están en la app.

---

## Tres modos de análisis
- **Diario** — un día de diseño (solsticios, equinoccios, día más caluroso/frío, o fecha específica).
- **Anual** — operación mes a mes sobre las 8760 h, con eficiencias de Augustus Leon.
- **Ventana** — un lapso real `[inicio, fin]` con clima horario (una semana, un mes, una campaña).

🎤 **Notas:** El modo Ventana es clave para el modo industrial (campañas de producción) pero también sirve como multidía real en armario/caja. Todo corre sobre **clima real horario**, no promedios.

---

## Subsistema colector solar
- **4 tipos** de colector de placa plana de aire (canal único; absorbedor a media altura con canales activos/estancos).
- **Doble cubierta** con cavidad de aire (convección natural de Hollands + radiación).
- Coeficiente convectivo **local nodo a nodo**, con propiedades del aire variables con T.
- Resolución **cuasi-estacionaria**: EDO del fluido + sistema no lineal de superficies en cada nodo.
- Recibe **POA** (radiación en el plano del colector), no GHI — transposición Liu-Jordan con `pvlib`.

🎤 **Notas:** Mostrar la gráfica de desempeño T(x) del colector y la curva η vs ΔT. Este es el subsistema más maduro y validado.

---

## Subsistema cámara — motor termodinámico
- **Un único motor físico:** balance acoplado **calor–masa**.
- EDOs de temperatura y humedad del producto + evaporación **difusiva** (`ṁ_w = h_m·A·(ω_sat·a_w − ω_flujo)`).
- Isoterma de sorción **GAB** por producto.
- Coeficientes de transporte **variables en el tiempo** (Chilton-Colburn).
- Pared **compuesta** (capas en serie), **techo translúcido** con ganancia + pérdida, bandejas (Ergun).

🎤 **Notas:** Enfatizar el salto: pasamos de correlaciones empíricas de "capa fina" (un punto a T pico) a un motor acoplado sensible al espesor de lecho, la velocidad de aire y el clima real. Mostrar las trayectorias T_producto(t) y X(t).

---

## Modo industrial / gran escala
- **Dos subtipos:** lotes (**batch**) y **túnel semicontinuo** a contracorriente (estilo ADITAL).
- Motor de cámara **multi-etapa unificado**: batch = 1 zona; semicontinuo = N zonas en serie con avance de columnas.
- **Caño maestro** (manifold de sección creciente): ΔP, ΔT térmica y uniformidad de distribución.
- **Híbrido con calendario de arranque**: quemador de leña en ventanas de mañana/atardecer.
- **Referencia física:** secador híbrido **ADITAL** de San Carlos (tesis doctoral, cap. 3).

🎤 **Notas:** Este es tu diferencial. La sequedad de salida es **emergente** (no se fuerza). Mencionar la validación contra ADITAL: 5000 kg en ~5 días, números que reproducen el campo.

---

## Movimiento del aire
- **Convección forzada:** ventilador axial o centrífugo, dimensionado por pérdida de carga.
- **Convección natural:** chimenea solar (tiro térmico), opcionalmente con **extractor eólico** (turbina sombrero chino).
- Lazo natural cerrado por **Picard** (`T_chim ↔ ṁ_nat ↔ T_salida_colector`).
- Pérdida de carga: Colebrook-White, Ergun (lecho de producto), coeficientes ASHRAE de ductos.

🎤 **Notas:** Mostrar que el sistema decide el caudal de equilibrio en convección natural, no se asume. La auditoría hidrodinámica se hizo contra ASHRAE cap. 3/21.

---

## Recurso climático
- Descarga **horaria anual** de **NASA POWER** (vía `pvlib`).
- Caché local (parquet) por sitio/año; política de huecos transparente.
- **Transposición a POA** (plano del colector) con tilt y acimut reales.
- Convenciones de ángulos rigurosas (Duffie ↔ UI ↔ pvlib), centralizadas.

🎤 **Notas:** Punto fuerte para la audiencia solar: usamos la misma fuente y librería (pvlib) estándar de la industria fotovoltaica. El usuario solo pone lat/lon.

---

## Resultados y análisis
- **Dashboard integrado:** balance energético, COP, fracción solar, tiempo de secado.
- **Modos:** constantes representativas · transitorio · ventana de producción.
- **Carta psicrométrica del proceso** (corregida por altitud) — calentamiento sensible → secado adiabático/no-adiabático **emergente**.
- **Corridas paramétricas** (barridos) para comparar diseños.
- **Exportación:** reporte PDF, JSON (snapshot reproducible), TXT.

🎤 **Notas:** La carta psicrométrica es muy vistosa y "habla" al público técnico. Mostrarla. El reporte PDF es el entregable que el usuario se lleva.

---

# 4 · Los modelos físicos
**(≈ 8 min — para la audiencia experta del INENCO)**

🎤 **Notas:** Acá ganás credibilidad. Mostrá que las hipótesis son explícitas y las referencias son clásicas.

---

## Base bibliográfica
- **Colector:** Duffie & Beckman (Hottel-Whillier-Bliss), Swinbank (cielo), McAdams (viento), Hollands (cavidad).
- **Cámara:** Mujumdar (secado), GAB (Van den Berg & Bruin), Chilton-Colburn (Incropera).
- **Eficiencias:** Augustus Leon et al. (drying, pickup, térmica, total).
- **Hidrodinámica:** ASHRAE (fluidos y ductos), Colebrook-White, Ergun.

🎤 **Notas:** Todas referencias estándar, sin sorpresas metodológicas. Esto desactiva preguntas de "¿de dónde sale esto?".

---

## Hipótesis explícitas (y defendibles)
- Colector **cuasi-estacionario**: capacitancia de placa despreciable (τ_placa ≪ tiempo de residencia).
- Cámara como **CSTR** (mezcla perfecta): válido para armario compacto; gran escala usa **cascada por zonas**.
- Evaporación **difusiva** válida para lechos delgados (<5 cm); el software **advierte** si se excede.
- GAB con **fallback** y advertencia crítica si el producto no está calibrado.

🎤 **Notas:** El sistema de advertencias atrapa errores de diseño temprano y no falla en silencio. Mencionar que las simplificaciones están documentadas, no escondidas.

---

## Validación
- **Hottel-Whillier-Bliss (linealidad de η):** **R² ≥ 0.9998** ✓ — confirma la física del colector.
- **ADITAL (caso real de campo, San Carlos):** **7/7 checks** ✓ — colector 55/78 °C, caño −2.8 °C, cámara 57 °C, 5000 kg en 5 días.
- **Klein (U_top):** discrepancia grande **esperada** — Klein asume cavidad estanca; esto es un air heater de canal único (el aire enfría la cubierta interna). HWB es la validación correcta para air heaters.

🎤 **Notas:** Si alguien pregunta por Klein, ya tenés la respuesta: no aplica a este tipo de colector, por eso usamos HWB. Es un punto de rigor, no una debilidad.

---

## Ingeniería de software
- Arquitectura en capas estrictas: **UI / core / cálculos** (la física no sabe de Streamlit).
- **SI estricto** en todo el núcleo; conversión de unidades en un único lugar.
- **~1042 tests** automatizados.
- Repo privado (GitHub) + **deploy automático** a Hugging Face Spaces en cada push.

🎤 **Notas:** Importante para mostrar que es software serio y mantenible, no un script. La separación de capas permite que la física se valide sin la UI.

---

# 5 · Demo en vivo
**(≈ 10 min)**

🎤 **Notas:** Tener la app YA abierta en otra pestaña/pantalla. **Plan B:** screenshots de respaldo por si falla internet (la descarga NASA POWER necesita red). Elegí un caso que sabés que converge.

---

## Guion de la demo
**Caso sugerido: Armario para [producto] en [tu localidad].**
1. **P1** — Tipología Armario, modo Diario (día más caluroso) → mostrar la guía "¿Qué tipología elegir?".
2. **P2** — Cargar lat/lon de tu sitio, descargar clima → mostrar GHI vs POA.
3. **P3** — Elegir colector Tipo 1, materiales, geometría → botón "Evaluar colector": curva T(x) y η.
4. **P4** — Geometría de cámara, elegir producto, carga → motor termodinámico: trayectorias T y X.
5. **P6** — Chimenea solar o ventilador → ΔP del sistema.
6. **P7** — Correr el prediseño completo → dashboard + **carta psicrométrica** + reporte PDF.

🎤 **Notas:** Si el tiempo aprieta, podés llegar con el proyecto pre-cargado (snapshot JSON) y mostrar P3→P7. Tené el JSON listo por las dudas. Cerrá la demo descargando el reporte PDF: es el "wow" tangible.

---

## (Opcional) Demo del modo industrial
- Tipología **Gran escala**, subtipo **semicontinuo**, ventana de **una campaña**.
- Mostrar el **dashboard de producción**: kg secos, tasa de régimen (kg/día), leña, **perfil espacial del túnel**.

🎤 **Notas:** Solo si te sobra tiempo y querés rematar con el caso ADITAL. Requiere clima descargado para el lapso. Si no, dejalo para Q&A.

---

# 6 · Cierre
**(≈ 4 min)**

---

## Hacia la versión 1.0
- **Hecho:** modo industrial completo y validado; carta psicrométrica; auditoría hidrodinámica; multidía real.
- **En camino:** refinamiento del análisis anual integrado; manual de usuario; internacionalización (Esp/Por/Ing).
- **Disponible ya** para usar y dar feedback (acceso por URL, sin instalar).

🎤 **Notas:** Invitar al grupo a usarlo y reportar. El feedback de colegas es lo que más lo va a mejorar.

---

## En síntesis
> **Secasol integra clima real, física acoplada de calor y masa, y tres escalas de secador — desde la caja familiar hasta el túnel industrial — en una sola herramienta de prediseño, libre y validada.**

**Gracias.** ¿Preguntas?
`[contacto / URL de la app / repo]`

🎤 **Notas:** Dejar la URL visible. Agradecer a GEEDSP/INENCO/CONICET y a quien corresponda.

---

# Backup · Preparación para Q&A
🎤 **Notas:** Slides de respaldo, no se muestran salvo que pregunten.

---

## Q&A — respuestas listas
- **"¿Por qué Klein no coincide con el modelo?"** → Klein (1979) asume cavidad estanca absorbedor–cubierta; en un air heater de canal único el aire pasa por encima del absorbedor y enfría la cubierta interna, reduciendo U_top real. La validación válida para air heaters es **HWB** (R²≈1).
- **"¿El espesor de la placa absorbedora no afecta?"** → No: el modelo es cuasi-estacionario y asume capacitancia térmica de placa despreciable. Es un dato geométrico, no entra al balance.
- **"¿El supuesto de mezcla perfecta (CSTR) es realista?"** → Para armario (volumen compacto) sí; para gran escala usamos una **cascada por zonas** en serie que relaja el supuesto.
- **"¿Qué pasa con lechos gruesos (>5 cm)?"** → El modelo difusivo sobreestima; el software **lo advierte** explícitamente. La difusión interna del producto es una extensión futura.
- **"¿De dónde sale el clima?"** → NASA POWER horario, vía pvlib (estándar FV). El usuario solo da lat/lon.

---

## Q&A — límites honestos del modelo
- Es **prediseño** (orden de magnitud), no certificación ni reemplazo de medición.
- Tipos 2/3/4 de colector: algunas propiedades del aire aún constantes (impacto ~2-3 % en Q_útil) — en hoja de mejora.
- Catálogo de productos: pocos con GAB calibrado; cada producto nuevo requiere calibración previa.
- Validación industrial (ADITAL) usa clima sintético cualitativo; el contraste contra clima histórico real es trabajo futuro.

🎤 **Notas:** Mostrar estos límites con naturalidad si preguntan — transmite rigor, no debilidad. Tenés un roadmap claro para cada uno.
