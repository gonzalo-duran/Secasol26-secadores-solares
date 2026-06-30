# 08 · Cierre — visión global de Secasol

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cierre de la charla: visión general, highlights de física y de código, aspectos
> clave, funcionalidad, validación, y posibilidades / futuro.

---

## 1. Qué es Secasol, en una frase

> **Secasol integra clima real, física acoplada de calor y masa, y tres escalas de
> secador — desde la caja familiar hasta el túnel industrial — en una sola
> herramienta de prediseño, libre, accesible por navegador y validada.**

Es un **prediseñador** (orden de magnitud, no certificación): sirve para explorar,
dimensionar y comparar rápido **antes de cortar la primera chapa**, no para
reemplazar el cálculo de detalle ni la medición.

---

## 2. Aspectos clave (lo que lo hace distinto)

1. **Física acoplada de verdad** — colector, cámara, producto, aire y auxiliar se
   resuelven **juntos** con un lazo global (Picard), no por separado.
2. **Clima real horario del sitio** — NASA POWER + pvlib, transposición a POA; el
   usuario solo da lat/lon.
3. **Tres tipologías y tres modos** — caja / armario / gran escala × diario /
   anual / ventana.
4. **Modo industrial completo** — banco de colectores, caño maestro, batch y túnel
   semicontinuo, híbrido con leña.
5. **Sequedad de salida emergente** — el sistema te dice cuánto seca, no se fuerza.
6. **Sistema de advertencias** — atrapa errores de diseño temprano y no falla en
   silencio.

---

## 3. Highlights de física

| Subsistema | Modelo |
|---|---|
| **Recurso solar** | Liu-Jordan (POA), SPA (posición solar), convenciones de ángulos rigurosas |
| **Colector** | 4 tipos de air heater, balances por superficie, $h_{int}$ **local** nodo-a-nodo, propiedades del aire variables con T, doble cubierta (Hollands) |
| **Cámara** | balance acoplado calor–masa (CSTR), evaporación **difusiva**, isoterma **GAB**, Chilton-Colburn, techo translúcido |
| **Industrial** | motor multi-etapa unificado (batch=1 zona, túnel=N zonas a contracorriente), caño maestro (ΔP/ΔT/uniformidad) |
| **Aire** | ventilador (ΔP→potencia) o chimenea solar (tiro térmico + extractor eólico), lazo Picard |
| **Auxiliar** | calentamiento sensible, control por set-point, calendario de arranque |

Base bibliográfica **clásica** (Duffie & Beckman, Hollands, McAdams, Swinbank,
Mujumdar, GAB, Chilton-Colburn, Augustus Leon, ASHRAE, Colebrook, Ergun): sin
sorpresas metodológicas.

---

## 4. Highlights de código (ingeniería de software)

- **Arquitectura en capas estrictas:** `ui/` (Streamlit) → `core/` (modelo de
  datos) → `calculos/` (motores numéricos). **La física no sabe de Streamlit** →
  se valida sin la UI.
- **SI estricto** en todo el núcleo; la conversión de unidades vive en **un solo
  lugar**.
- **Catálogos YAML** de materiales y productos → modularidad en subcomponentes.
- **~1042 tests** automatizados (un test por validación dura).
- **Repo privado** (GitHub) + **deploy automático** a Hugging Face Spaces en cada
  push → los colegas acceden por URL, sin instalar nada y sin ver el código.
- **Documentación viva:** bitácoras por sesión, mapa de conexiones, CHANGELOG,
  ADRs.

---

## 5. Validación (rigor honesto)

| Validación | Resultado |
|---|---|
| **Hottel-Whillier-Bliss** (linealidad de η del colector) | **R² ≥ 0.9998** ✓ |
| **ADITAL** (caso real de campo, San Carlos) | **7/7 checks** ✓ (colector 55/78 °C, caño −2.8 °C, cámara 57 °C, 5000 kg en ~5 días) |
| **Klein** (U_top) | discrepancia **esperada** — Klein asume cavidad estanca; esto es un air heater de canal único (el aire enfría la cubierta interna). HWB es la validación correcta. |

> La discrepancia con Klein es un punto de **rigor**, no una debilidad: tenemos la
> respuesta lista para Q&A.

---

## 6. Funcionalidad disponible hoy

- Configuración guiada en **7 pestañas**, proyecto reproducible (snapshot JSON).
- **Dashboard integrado** (balance energético, COP, fracción solar, t_secado).
- **Carta psicrométrica** del proceso (adiabaticidad emergente).
- **Corridas paramétricas** (barridos) para comparar diseños.
- **Reporte PDF** institucional como entregable.
- **Modo industrial** completo y validado; **multidía real** (ventana) también en
  caja/armario.

---

## 7. Hacia la versión 1.0 (roadmap)

**Hecho:** modo industrial cerrado y validado; carta psicrométrica; auditoría
hidrodinámica (ASHRAE); multidía real; techo translúcido con ganancia + pérdida.

**En camino:**
- Refinamiento del análisis anual integrado.
- Manual de usuario.
- Internacionalización (Esp / Por / Ing).

**Límites honestos del modelo (los decimos con naturalidad):**
- Es **prediseño** (orden de magnitud), no certificación ni medición.
- Tipos 2/3/4 de colector: algunas propiedades del aire aún constantes (impacto
  ~2–3 % en Q_útil).
- Catálogo de productos: pocos con **GAB calibrado**; cada producto nuevo requiere
  calibración previa.
- Lechos gruesos (>5 cm): el modelo difusivo sobreestima; el software **lo
  advierte**. La difusión interna del producto es extensión futura.

---

## 8. Cierre

> Una herramienta para **diseñar secadores solares antes de cortar la primera
> chapa**: clima real, física acoplada, tres escalas, libre y validada.

**Disponible ya** para usar y dar feedback (acceso por URL, sin instalar). El
feedback de colegas es lo que más la va a mejorar.

**Gracias.** ¿Preguntas?

---

## Referencias

- Ver docs 01–07 de esta serie para el detalle por subsistema.
- `CLAUDE.md`, `docs/arquitectura.md`, `docs/decisiones.md` — arquitectura y ADRs.
- `validacion/` — scripts de validación física (HWB, Klein, ADITAL).
