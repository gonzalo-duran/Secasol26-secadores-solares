# BITÁCORA — SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

**Última actualización:** 2025 (sesión inicial de definición de arquitectura)
**Estado:** Definición de arquitectura y decisiones de alto nivel. Sin código aún.

---

## 1. Contexto y objetivo del proyecto

Software de **prediseño** (no simulación detallada tipo Simusol, ni diseño mecánico final) de secadores solares de alimentos, orientado a usuarios técnicos con formación en transferencia de calor.

**Usuario destinatario:** Ingenieros y estudiantes del curso de posgrado "Secadores Solares" de la Maestría en Energías Renovables (M.E.R.), Facultad de Ciencias Exactas, UNSa, Argentina.

**Espíritu del proyecto:** Académico, comunitario, abierto. Pensado para compartirse vía GitHub entre colegas, alumnos y comunidad científica.

**Nivel de modelado:** Complejidad media. Suficiente para tomar decisiones de ingeniería de prediseño (dimensiones, áreas, caudales, potencias auxiliares) pero sin pretender reemplazar simulación nodal completa.

---

## 2. Perfil del desarrollador (referencia para Claude)

- Licenciado en Física, Doctor en Ciencias especialidad Energías Renovables.
- Investigador Adjunto CONICET, INENCO–UNSa.
- Docente de Transferencia de Calor y Materia (5° año Lic. Física y Lic. Energías Renovables).
- Docente posgrado M.E.R.–UNSa: Transferencia de Calor y Materia, Energía Solar 1 y 2, Simulación de Procesos Termodinámicos en EERR, Secado Solar Industrial, Eficiencia Energética en la Industria, Domótica para Arquitectura Bioclimática.
- Experiencia: diseño de secadores solares de alimentos a amplia escala de producción.
- Software de simulación de referencia: **Simusol** (www.simusol.org), nivel experto.
- Experiencia de programación: Visual Basic y C++ (oxidado). Entiende lógica de Python pero requiere que Claude codee.
- Datos experimentales: dispone de mediciones de muchos secadores reales (a usar como casos de validación).

**Hardware:**
- Notebook DELL G15 5515, Ryzen 5000, 32 GB DDR4, GeForce RTX 3050 4 GB.
- Sistema operativo: Fedora 44 con Plasma 6.6.4.
- IDE: VS Code instalado. Estado de Python/integración con VS Code: a verificar.
- Cuenta Claude Pro recién obtenida. Sin integraciones previas.

---

## 3. Decisiones técnicas tomadas

### 3.1 Stack tecnológico

| Área | Decisión |
|---|---|
| Lenguaje | Python 3 |
| Cálculo científico | NumPy, SciPy, Matplotlib, pvlib, pandas |
| Interfaz | **Streamlit** (renderizado en navegador, multidispositivo) |
| Motor de EDOs | `scipy.integrate.solve_ivp` |
| Datos climáticos | NASA POWER vía `pvlib.iotools.get_nasa_power` |
| Repositorio | GitHub (cuenta del usuario disponible) |
| Licencia | **MIT** (permisiva, simple, estándar del ecosistema científico Python) |
| Deploy opcional | Streamlit Community Cloud (gratuito, conecta directo a GitHub) |

### 3.2 Idioma

- Versión inicial: **español** completo (interfaz y código/comentarios).
- Versión bilingüe (español/inglés): considerada como mejora futura.

### 3.3 Sistema de unidades

**Sistema Internacional (SI) estricto en todo el cálculo interno.**

**Convención dura sobre temperatura:**
- Toda variable de temperatura en el modelo de datos central y en funciones de cálculo está en **Kelvin**, sin excepción.
- La conversión a °C ocurre **únicamente** en las dos fronteras:
  - Cuando el usuario ingresa un valor en Streamlit → callback convierte °C → K antes de guardar.
  - Cuando se muestra un valor en pantalla o gráfico → conversión K → °C para display.
- Esta convención debe documentarse en el README y en una guía de convenciones de código del repo.
- Motivo: prevenir el bug clásico de sumar K con ΔT sin convertir.

### 3.4 Convención de ángulos solares

- **Hacia el usuario** (interfaz y documentación): convención clásica de Duffie & Beckman adaptada al hemisferio sur.
  - Acimut 0° = Sur, girando hacia el Norte pasando por el Este (sentido antihorario).
  - Pendiente: 0° = horizontal, 90° = vertical.
- **Internamente** (dentro de pvlib y funciones que usen pvlib): convención de navegación.
  - 0° = Norte, 90° = Este, 180° = Sur, 270° = Oeste.
- Se implementará una **capa de conversión** entre ambas convenciones. Documentar para evitar bugs silenciosos.

### 3.5 Modelo físico de los colectores

- **Decisión clave:** modelo con **discretización espacial** a lo largo de la dirección de flujo (no Hottel-Whillier-Bliss estacionario simple).
- Motivación: el usuario quiere poder determinar el **largo óptimo de colector** para una tipología y caudal dados, lo cual exige el perfil T(x) y η(x) y no solo valores globales.
- **Ecuaciones**: el usuario aportará un sistema de **ecuaciones diferenciales acopladas** que representan los balances de energía en placa absorbente, fluido (aire), cubierta y fondo del colector, más una **ecuación de difusión de vapor** para el aporte de vapor de agua al aire en cámara de secado (enfriamiento evaporativo).
- **Motor numérico:** `scipy.integrate.solve_ivp`.
  - Si los balances son estacionarios espaciales (derivada en x), se integra en x.
  - Si se requiere transitorio temporal, método de líneas: discretizar x con diferencias finitas e integrar en t.
- **Optimización de largo de colector:**
  - **Versión inicial (didáctica):** barrido paramétrico graficado — calcular para varios largos y mostrar T_salida vs L y η vs L.
  - **Versión avanzada (futura):** optimización formal con `scipy.optimize`.
- **Cámara de secado:** sistema EDO acoplado calor-masa (T del aire, humedad absoluta del aire, T y humedad del producto en modelo de capa fina o similar).
  - Para prediseño se evaluará desacoplar colector-cámara: el colector entrega T_salida(t) como condición de borde a la cámara.
  - Decisión definitiva de acople/desacople se tomará al recibir las ecuaciones específicas del usuario.

### 3.6 Validación

- El usuario dispone de datos experimentales de secadores reales.
- Los datos se almacenarán en `validation_data/` del repo desde el inicio.
- Se desarrollarán **tests automáticos** que validen los modelos contra esos datos para evitar regresiones al refactorizar.

### 3.7 Pendiente de definir

- **Visibilidad del repo desde el inicio:** público (recomendado para que alumnos clonen desde la primera versión) vs. privado (publicar al tener primera versión funcional). **Pregunta abierta para el usuario.**

---

## 4. Arquitectura del software (pestañas)

Diseño modular en pestañas/secciones interconectadas. Cada pestaña lee y escribe sobre un **modelo de datos central** (a definir en próxima sesión).

### 4.1 Pestaña 1 — Inicio

**Función:** elegir tipología de secador y modo de análisis.

#### 4.1.1 Tipologías de secador

**(a) Secador solar tipo caja**
- Carga: pequeña, hasta ~10 kg de producto fresco.
- Usuario típico: doméstico o muy pequeño productor.
- Sin colectores externos: efecto invernadero ocurre en la propia cámara de secado.
- Circulación de aire: convección natural, opcionalmente asistida por chimenea solar.
- **Nota de arquitectura:** modelo físico distinto a las otras tipologías porque la cámara *es* el colector.

**(b) Secador solar tipo armario**
- Carga: media, 0–100 kg de producto fresco.
- Cámara de secado (opaca o translúcida) + banco de 1 o 2 colectores solares de aire.
- Circulación: natural o forzada (ventilador o extractor eólico de turbina).
- Auxiliares opcionales: quemador de biomasa, resistencia eléctrica calentadora de aire.

**(c) Secador solar de gran escala con banco de colectores**
- Carga: 100 kg a varias toneladas de producto fresco.
- Circulación de aire: forzada (motor + ventilador).
- Cámara de secado (opaca o translúcida) + banco de 2 o más colectores con caño maestro de ventilación que dirige el aire caliente a la cámara.
- Auxiliares opcionales: quemador de biomasa, resistencia eléctrica.

**Decisión arquitectural pendiente:** ¿clases/módulos separados por tipología con interfaz común, o un modelo general parametrizado? Intuición preliminar: módulos separados con interfaz común. **A confirmar.**

#### 4.1.2 Modo de análisis

**(a) Análisis diario (datos horarios para un día)**
- Selección del día por uno de estos criterios:
  - Día específico elegido por el usuario.
  - Día más frío del año (menor temperatura ambiente media).
  - Día más caluroso del año (mayor temperatura ambiente media).
  - Cuatro días característicos: solsticios y equinoccios.

**(b) Análisis anual completo (datos horarios de los 8760 h)**
- Requiere **vectorización con NumPy** desde el inicio para que sea performante.

### 4.2 Pestaña 2 — Emplazamiento y recursos climáticos

**Función:** ubicar geográficamente el secador, orientarlo, y estimar el recurso energético en el sitio.

#### 4.2.1 Entradas del usuario

- Latitud y longitud del emplazamiento.
- Acimut del secador (convención usuario, ver §3.4).
- Pendiente del plano de colección.

#### 4.2.2 Datos a obtener de NASA POWER

- Temperatura ambiente.
- Radiación solar global sobre plano horizontal.
- Velocidad de viento (a nivel de suelo o menor altura disponible).
- Presión atmosférica.
- Altura del lugar.
- Humedad relativa ambiente.

**Procesamiento condicionado por la elección de §4.1.2** (un día específico o año completo).

**Notas técnicas sobre NASA POWER:**
- Resolución espacial ~0.5° × 0.625°. Para zonas con gradientes orográficos fuertes (Puna, Cuyo, etc.) puede haber error notable.
- Datos horarios disponibles, con latencia de varios meses.
- Se usa `pvlib.iotools.get_nasa_power` (no requests manuales).
- **A futuro:** dejar abierta la posibilidad de alimentar el software con datos de SMN o estaciones del INENCO para validación.

#### 4.2.3 Salidas de la pestaña

- Gráficas de: irradiancia global horizontal, irradiancia en plano de colección, temperatura ambiente, velocidad de viento, presión atmosférica, humedad relativa.
- Archivo **CSV descargable** con toda la información recabada.

### 4.3 Pestaña 3 — Definición y dimensionamiento de colectores solares

A desarrollar. Implica el modelo de discretización espacial y el sub-análisis de optimización de largo (§3.5).

### 4.4 Pestaña 4 — Definición y dimensionamiento de cámara de secado

A desarrollar. Modelo acoplado calor-masa (§3.5).

### 4.5 Pestaña 5 — Definición y dimensionamiento de sistema de calentamiento auxiliar

A desarrollar.

### 4.6 Pestaña 6 — Dimensionamiento de motores

Aplica solo a tipologías con convección forzada. A desarrollar.

### 4.7 Pestaña 7 — Resultados finales

A desarrollar.

---

## 5. Plan de trabajo acordado

**Antes de codear:**

1. Definir el **modelo de datos central** que viaja entre pestañas: variables, unidades, tipos, qué pestaña escribe y cuáles leen cada variable.
2. Definir la **estructura de carpetas del repo**: `core/`, `app/` o `pages/`, `data/`, `validation_data/`, `tests/`, `docs/`.
3. Definir **convenciones de código**: naming, unidades, docstrings, type hints, formato.
4. Definir **lista preliminar de dependencias** (`requirements.txt`).

**Una vez aprobado lo anterior:**

5. Generar el esqueleto del proyecto: `requirements.txt`, `README.md`, `LICENSE` (MIT), estructura de módulos vacíos, y `app.py` mínimo de Streamlit con pestañas vacías navegables.
6. Crear repositorio en GitHub.
7. Comenzar a llenar pestaña por pestaña, **empezando por la Pestaña 2** (emplazamiento y recursos climáticos) porque alimenta a todas las demás.

**Para cada tipología de secador (cuando llegue su turno):**

8. El usuario aporta las ecuaciones diferenciales acopladas de balance de energía en colector + ecuación de difusión de vapor en cámara, con notación clara, símbolos definidos, unidades, y referencias bibliográficas si están disponibles.
9. Claude codea los modelos numéricos correspondientes.
10. Tests de validación contra datos experimentales de `validation_data/`.

---

## 6. Herramientas Claude Pro recomendadas para este proyecto

| Herramienta | Uso para este proyecto | Cuándo |
|---|---|---|
| **Projects** | Imprescindible. Carga contexto persistente (rol del usuario, bitácora, papers). | Crear desde el inicio. |
| **Artifacts** | Renderizado de código y documentos largos (los `.py` aparecen ahí, descargables). | Día a día durante el desarrollo en chat. |
| **Claude Code** (terminal) | Opera directamente sobre el repo: lee, modifica archivos, corre tests, hace commits. Mucho más potente que el chat para iterar sobre código existente. Se instala en Fedora vía npm, autenticación con cuenta Pro. | **Más adelante**, una vez que el repo tenga estructura. Primero definir arquitectura y esqueleto en chat. |
| **Extensión Claude Code para VS Code** | Integra Claude Code dentro del editor. Resolvería de paso el tema "Python linkeado a VS Code". | Cuando se pase a Claude Code. |
| **Búsqueda web** | Uso puntual (verificar APIs, papers). El usuario ya tiene el conocimiento del dominio. | Casos específicos. |
| **Creación de docx/xlsx/pptx** | NO aplica para este proyecto (orientado a documentos de oficina). | — |

---

## 7. Decisiones pendientes (síntesis)

- [ ] **Visibilidad del repo:** público desde el inicio vs. privado hasta primera versión funcional.
- [ ] **Modelo de datos central:** estructura completa (próxima sesión).
- [ ] **Estructura de carpetas:** propuesta concreta (próxima sesión).
- [ ] **Convenciones de código:** documento de referencia (próxima sesión).
- [ ] **Modular por tipología vs. modelo parametrizado único:** confirmar enfoque modular separado.
- [ ] **Acople vs. desacople colector-cámara:** decidir al recibir las ecuaciones específicas.

---

## 8. Próximo paso al retomar

Claude presenta una propuesta concreta de:

1. Modelo de datos central.
2. Estructura de carpetas del repo.
3. Convenciones de código.
4. `requirements.txt` preliminar.

El usuario revisa, marca lo que no le cierra, se ajusta, y recién entonces se genera el esqueleto del repo.
