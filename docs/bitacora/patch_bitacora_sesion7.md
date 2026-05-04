# PATCH DE BITÁCORA — SESIÓN 7
# Para integrar en bitacora_sesion6.md (reemplazar el encabezado y actualizar las secciones afectadas)

## ENCABEZADO — reemplazar la línea de "Última actualización":

**Última actualización:** Sesión 7 (Tanda 3 paso 2 en curso — cambio de flujo de trabajo; 4 archivos YAML de catálogo generados en estructura vacía; plantilla de referencia generada; `frutas.yaml` v1.0 conservado; auditoría de DOIs completada)

**Estado:** Modelo de datos central definido hasta `Camara`. Catálogo de materiales v1 cerrado. Tanda 3 paso 2 EN CURSO: 5 archivos YAML generados (16 productos total), `frutas.yaml` parcialmente poblado (manzana con 3 modelos CF + yacón con 2 modelos CF + GAB). Los restantes 15 productos esperan carga de coeficientes por el usuario. Sin código aún.

---

## SECCIÓN 5.10 — Agregar subsección 5.10.7 (Sesión 7):

### 5.10.7 Decisiones y cambios de Sesión 7

**Cambio de flujo de trabajo (decisión principal de Sesión 7):**

El flujo A+C establecido en Sesión 6 se reemplaza por un flujo más eficiente:

- **Flujo anterior (A+C):** usuario consigue PDFs → los sube al Project knowledge → Claude parsea PDFs y extrae coeficientes → Claude llena los YAMLs.
- **Flujo nuevo (B+C):** Claude genera estructura YAML completa con todos los campos en `null` → usuario busca y carga los coeficientes directamente en los archivos YAML por su cuenta.

**Razón del cambio:** la carga de ~60 papers al Project knowledge para que Claude los parsee consumiría los tokens semanales completos sin dejar margen para el desarrollo del código (EDOs, módulos de cálculo, Streamlit). El usuario, con acceso directo a los papers, puede cargar los coeficientes de forma eficiente.

**Consecuencias:**
- Los PDFs que estaban en el Project knowledge fueron retirados por el usuario (reduce consumo de tokens).
- El Project knowledge queda limpio para la bitácora y documentación del proyecto.
- Claude genera estructura YAML autodocumentada (con notas operativas, papers sugeridos, advertencias de uso) para guiar la carga.

**Decisiones confirmadas en Sesión 7:**
- [x] `frutas.yaml` v1.0 se conserva intacto (manzana con Sacilik 2006, yacón con Shi 2013 + Marques 2022 — datos verificados del PDF).
- [x] `params` es diccionario plano `{k: ..., n: ...}` — esquema simple confirmado. Sin extensión `sets_por_temperatura`.
- [x] Plantilla maestra `PLANTILLA_REFERENCIA_CATALOGO.md` generada — guía operativa de carga.

**Auditoría de DOIs completada en Sesión 7:**
- Se descubrió que el DOI `10.1016/j.jfoodeng.2005.05.052` atribuido a "Doymaz 2006 sobre durazno" en la shopping list era INCORRECTO (ese DOI corresponde a Gill et al. sobre inulinasa). Corregido.
- DOI real para Doymaz sobre durazno: **Doymaz & Bilici (2014)** `10.1515/ijfe-2014-0026` (Int J Food Eng, De Gruyter). Verificado en fuentes cruzadas.
- Se auditaron los 6 DOIs restantes del `frutas.yaml`; todos verificados en metadatos de PDFs o fuentes cruzadas.
- **Política de citas establecida:** solo registrar DOIs verificados en el PDF del paper o en fuente externa que lo liste textualmente. Si no verificado: escribir "[DOI no verificado]" o citar sin DOI.

**Conteo de productos:**
- La bitácora §5.9.10 menciona 19 productos. El catálogo real tiene **16 productos** en 5 archivos. La discrepancia de 3 sigue sin resolverse. Acción: revisar §5.9.10 en sesión siguiente para identificar si la lista canónica era 16 o 19, y cuáles son los 3 faltantes (si los hay).

---

## SECCIÓN 5.10.4 — Reemplazar tabla de estado de productos:

Estado al cierre Sesión 7:

| Archivo | Producto | Capa fina | Isoterma |
|---|---|---|---|
| `frutas.yaml` | manzana | 3/3 poblados (Log=ALTA, Page=MEDIA, Midilli=MEDIA) | PENDIENTE |
| `frutas.yaml` | durazno | 0/0 (sin estructura aún — no se encontraron coeficientes en PDFs disponibles) | PENDIENTE |
| `frutas.yaml` | yacón | 2/2 poblados (Page=ALTA, Midilli=ALTA — Shi 2013) | GAB ALTA (Marques 2022) |
| `hortalizas.yaml` | tomate | Estructura vacía | Estructura vacía |
| `hortalizas.yaml` | papa | Estructura vacía | Estructura vacía |
| `hortalizas.yaml` | cebolla | Estructura vacía | Estructura vacía |
| `hortalizas.yaml` | pimiento_rojo | Estructura vacía | Estructura vacía |
| `hortalizas.yaml` | zanahoria_rallada | Estructura vacía (con caveat geométrico) | Estructura vacía |
| `hortalizas.yaml` | perejil | Estructura vacía | Estructura vacía |
| `hortalizas.yaml` | apio | ESTIMADA_POR_ANALOGIA con perejil | ESTIMADA_POR_ANALOGIA |
| `hortalizas.yaml` | mandioca | Estructura vacía | Estructura vacía |
| `hojas_aromaticas.yaml` | te_yerba | Estructura vacía | Estructura vacía |
| `hojas_aromaticas.yaml` | oregano | Estructura vacía | Estructura vacía |
| `hojas_aromaticas.yaml` | coca | ESTIMADA_POR_ANALOGIA con te_yerba | ESTIMADA_POR_ANALOGIA |
| `legumbres_frutos.yaml` | algarroba | Estructura vacía | Estructura vacía |
| `carnes.yaml` | charqui_vacuno | Estructura vacía | Estructura vacía |

---

## SECCIÓN 8 — Agregar aclaración nueva (Sesión 7):

**Aclaración nueva (sesión 7):** Los PDFs de papers científicos fueron retirados del Project knowledge por el usuario (decisión de optimización de tokens). La carga de coeficientes en los YAMLs la realiza el usuario directamente, guiado por `PLANTILLA_REFERENCIA_CATALOGO.md` y las notas operativas dentro de cada archivo YAML. Claude no necesita acceso a los PDFs en este nuevo flujo.

---

## SECCIÓN 9 — Agregar decisiones de Sesión 7:

- [x] **Cambio de flujo de carga de catálogo:** de A+C (Claude parsea PDFs) a B+C (usuario carga coeficientes directamente). Razón: optimización de tokens para reservar capacidad para desarrollo de código.
- [x] **PDFs retirados del Project knowledge** por el usuario para reducir consumo de tokens por turno.
- [x] **`params` esquema simple** confirmado: diccionario plano `{k, n, a, b, c}`. Sin extensión `sets_por_temperatura`.
- [x] **Plantilla maestra generada:** `PLANTILLA_REFERENCIA_CATALOGO.md` — guía operativa para carga de coeficientes.
- [x] **4 archivos YAML de estructura vacía generados:** `hortalizas.yaml` (8 productos), `hojas_aromaticas.yaml` (3 productos), `legumbres_frutos.yaml` (1 producto), `carnes.yaml` (1 producto).
- [x] **DOI falso corregido:** `10.1016/j.jfoodeng.2005.05.052` (no era Doymaz sobre durazno). DOI correcto de Doymaz sobre durazno: `10.1515/ijfe-2014-0026` (Doymaz & Bilici 2014).
- [x] **Política de DOIs establecida:** solo citar DOI verificado en PDF o fuente externa. Si no verificado, escribir "[DOI no verificado]".

---

## SECCIÓN 10 — Actualizar decisiones pendientes:

Agregar:
- [ ] **Resolver discrepancia de conteo:** bitácora dice 19 productos, catálogo tiene 16. Identificar si la lista canónica es 16 o 19, y cuáles son los 3 faltantes (si los hay). Revisar §5.9.10 original.
- [ ] **Durazno sin coeficientes:** los 3 PDFs cargados en Sesión 7 no aportaron coeficientes (2 eran de otros productos — ciruela y granada; 1 — Kingsly 2006 — no publica coeficientes). Conseguir Doymaz & Bilici (2014) DOI:10.1515/ijfe-2014-0026 para poblar `durazno.capa_fina`.
- [ ] **Manzana sin isoterma:** conseguir Kaymak-Ertekin & Gedik (2004) DOI:10.1016/j.lwt.2003.10.012 o alternativa para poblar `manzana.isoterma.gab`.

---

## SECCIÓN 11 — Reemplazar "Próximo paso al retomar":

**Tanda 3 paso 2 — continuación: el usuario carga coeficientes en los YAMLs.**

### Estado al retomar

- 5 archivos YAML generados: `frutas.yaml` (parcialmente poblado), `hortalizas.yaml`, `hojas_aromaticas.yaml`, `legumbres_frutos.yaml`, `carnes.yaml` (todos en estructura vacía esperando coeficientes).
- Plantilla de referencia `PLANTILLA_REFERENCIA_CATALOGO.md` disponible como guía.
- Shopping list bibliográfica de Sesión 6 disponible con papers sugeridos por producto.

### Flujo en sesiones siguientes

El usuario carga coeficientes de forma autónoma. Cuando el usuario haya cargado los coeficientes de algún/os producto/s, retoma el chat con algo como:

> "Cargué los coeficientes de [producto1] y [producto2]. Revisalos y confirmame que el formato está bien antes de seguir."

Claude revisa el YAML, verifica coherencia de unidades y formato, y da el visto bueno o señala correcciones.

Una vez que el catálogo esté suficientemente poblado (al menos 8-10 productos con datos reales), se puede avanzar a **Tanda 3 paso 3** (validaciones de `Camara`) sin esperar a que los 16 productos estén completos.

### Siguiente tarea de Claude cuando retome

Si el usuario quiere avanzar con el **código** sin esperar el catálogo completo, la siguiente tarea para Claude es **Tanda 3 paso 3**: definir las validaciones e invariantes de `Camara` (errores duros + advertencias estáticas, análoga a Tanda 2 paso 3). Esta tanda no requiere coeficientes cargados.
