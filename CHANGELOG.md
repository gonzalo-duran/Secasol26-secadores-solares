# Changelog

Todos los cambios notables a Secasol se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

Hoja de ruta a 1.0 (sin orden estricto):

- Pérdida de carga en bandejas de producto (correlación tipo Ergun para esferas / lecho poroso).
- Refinamiento de la pestaña de análisis anual (métricas integradas sobre 8760 h).
- Modo secador industrial (`Tipologia.GRAN_ESCALA`): banco de colectores, distribución del flujo, sectorización de cámara.

---

## [0.7.0] — 2026-05-20

Primer release post-prototipo. Cierre físico del modelo de colector solar y del lazo natural por chimenea. Validación contra Hottel-Whillier-Bliss (R²=1.0000). Suite: 774 tests + 2 xfailed.

### Added

- **Chimenea solar** como componente top-level del proyecto.
  - Modelo físico de tiro térmico, fricción y pérdidas singulares (`calculos/chimenea_calc.py`).
  - UI propia en P6 (accesible cuando el motor está apagado — convección natural).
  - Lazo natural acoplado completamente: en modo Constantes y en modo Transitorio el caudal se resuelve por iteración Picard hasta convergencia, re-corriendo el colector con la velocidad efectiva impuesta por el caudal natural.
  - Visualización completa en P7 (ambos modos): métricas instantáneas, series horarias, balance del lazo, advertencia automática si el caudal natural difiere más del 30% del caudal manual configurado en P4.

- **Doble cubierta** para colectores: parámetro `n_cubiertas` (1 o 2) con espaciado configurable. El modelo agrega resistencia serie cubierta–cavidad–cubierta usando Hollands (convección natural inclinada) + radiación entre superficies grises paralelas. Aplica a los 4 tipos de colector. Ganancia típica de eficiencia: +5 a +8 pp.

- **POA (Plane of Array)** computada hora a hora desde DNI/GHI/DHI del clima NASA POWER, propagada como variable de primera clase en las forzantes (`ForzantesAire.I_g_POA_W_m2`). Garantiza que el solver del colector reciba la irradiancia sobre el plano inclinado del absorbedor, no la horizontal del piranómetro.

- **Persistencia por pestaña**: cada una de P3/P4/P5/P6 tiene botones "Guardar configuración (.txt)" y "Guardar configuración (.json)" con snapshot reconstruible. P7 guarda el prediseño completo con todos los inputs, propiedades del catálogo, advertencias estáticas y resultados de simulación si fueron corridos.

- **Carga de configuración guardada (.json)** en P3/P4/P5/P6: file_uploader al inicio de cada pestaña que reconstruye los dataclasses desde el JSON, valida la sección y actualiza la UI.

- **Reporte PDF integral** en P7 (`ui/reporte.py`): header institucional GEEDSP/INENCO con logos, secciones tabuladas para cada pestaña, gráficas reconstruidas desde la sesión, advertencias activas. Tipografía DejaVu Sans incrustada para soporte completo de Unicode.

- **Validación física del modelo de colector** contra Hottel-Whillier-Bliss (HWB) y modelo de Klein para los 4 tipos (`validacion/validacion_hwb.py`, `validacion/validacion_klein.py`). Linealidad perfecta de η vs (T_med − T_amb)/I con R² = 1.0000.

### Changed

- **Entry point renombrado**: el script principal pasa de `app.py` a `Secasol.py`. Ejecutar con `streamlit run Secasol.py`.

- **Chimenea solar** migrada de subcomponente de Colector a componente top-level (`Proyecto.chimenea`). Esto permite chimenea también en tipología CAJA (donde no hay colector externo). Los snapshots `.json` antiguos que traen la chimenea bajo `colector.chimenea` la restauran automáticamente en `proyecto.chimenea`.

- **Sugerido automático de irradiancia** en P7 modo Constantes: ahora calcula POA representativa con `pvlib` sobre el año de clima cargado y toma el quantile 90 (antes salía del quantile 90 de GHI con label engañoso "POA").

- **Adaptación a deprecación de Streamlit**: reemplazo global de `use_container_width=True` por `width="stretch"` (deprecación programada para 2025-12-31).

### Fixed

- **Corrección crítica de signos** en el residual algebraico del solver de colector (F1 en los 4 tipos y F3 en Tipo 1). El bug producía raíces espurias con la cara externa de la cubierta a temperaturas físicamente imposibles (≈ −200 °C) y residuos numéricos cero, enmascarando el problema. Impacto al corregir: la eficiencia térmica η baja aproximadamente 25 puntos porcentuales en air heaters (los valores anteriores estaban sobreestimados). Validación HWB con R² = 1.0000 confirma el nuevo modelo.

- **Coherencia local del balance térmico** en colectores Tipos 2/3/4: agregado el término convectivo de la cara interna del fondo (`conv_ci_int = h·ΔT·W_abs`) que faltaba en el balance, restaurando coherencia con la EDO del fluido del canal inferior. Impacto: Δη ≈ −10 a −12 pp en Tipos 2 y 3 (Tipo 4 sin cambio significativo).

- **POA correcta en el solver del colector** en todos los caminos del pipeline (P3 horario/diario, P3 constantes, P7 constantes, P7 transitorio con clima real). Antes, el pipeline transitorio le pasaba GHI etiquetada como POA al solver, lo que subestimaba la T de salida del colector y, en cadena, el tiro térmico y el caudal natural. Para latitudes intermedias (ej. Salta, lat −24.79°) y tilt típico (25–30°) el efecto puede ser de hasta 25–30% en invierno.

### Removed

- **Sección de chimenea de P3**: la UI de chimenea ya no aparece en la pestaña del Colector. Su lugar es P6 (Motor), accesible cuando se desactiva el motor eléctrico.

### Incompatibilidad de archivos guardados

> **Importante para quien tenga snapshots `.json` o `.txt` anteriores a 0.7.0:**
>
> Los archivos cargan sin error, pero las corridas nuevas darán **números distintos** a los originales, por las correcciones físicas y el lazo natural acoplado. Concretamente:
>
> - Las eficiencias η de los colectores serán menores (típicamente −25 pp por el fix de signos F1/F3, y −10/−12 pp adicionales en Tipos 2/3 por el fix F4).
> - El caudal natural por chimenea será distinto al single-pass anterior (típicamente menor cuando antes estaba sobreestimado por correr el colector con velocidad de diseño en lugar de la velocidad efectiva del lazo).
> - La T de salida del colector en pipeline transitorio cambia porque ahora se calcula con POA real, no con GHI.
>
> Los valores anteriores no eran "correctos en otro sentido": eran simplemente erróneos por bugs físicos que se mantuvieron sin detectar. Los resultados post-0.7.0 son los físicamente válidos.

---

## [0.1.0]

Estado de prototipo. 7 pestañas operativas (Tipología/Configuración, Emplazamiento/Clima, Colector, Cámara, Auxiliar, Motor, Resultados). Motor termodinámico de cámara con pared 3 nodos, forzantes horarias multi-día (sintéticas o reales NASA POWER), política anti-rehumectación, eventos de humedad objetivo y temperatura máxima del producto. Tipología CAJA con cubierta translúcida y radiación directa al producto. Capa fina con dependencia de temperatura. 4 tipos de colector de placa plana. Pared compuesta multi-capa de cámara. Pipeline P7 transitoria. UI Plotly. 717 tests + 2 xfailed.
