# BITÁCORA — SOFTWARE DE PREDISEÑO DE SECADORES SOLARES

**Última actualización:** Sesión 20 — Mejoras UX/UI: tipo de colector, acimut [0-360], gráficas POA, evaluación del colector (2026-05-07).  
**Estado:** **Todas las pestañas implementadas (P1–P7) + psicrometría + motor dimensionado + evaluación gráfica del colector.** Flujo end-to-end completo. **487 tests pasan, 1 xfailed** (ver §8). Siguiente paso: repo GitHub + poblar catálogo de productos.

---

## 1\. Contexto y objetivo del proyecto

Software de **prediseño** (no simulación detallada tipo Simusol, ni diseño mecánico final) de secadores solares de alimentos, orientado a usuarios técnicos con formación en transferencia de calor.

**Usuario destinatario:** Ingenieros y estudiantes del curso de posgrado "Secadores Solares" de la Maestría en Energías Renovables (M.E.R.), Facultad de Ciencias Exactas, UNSa, Argentina.

**Espíritu del proyecto:** Académico, comunitario, abierto. Pensado para compartirse vía GitHub entre colegas, alumnos y comunidad científica.

**Nivel de modelado:** Complejidad media. Suficiente para tomar decisiones de ingeniería de prediseño (dimensiones, áreas, caudales, potencias auxiliares) pero sin pretender reemplazar simulación nodal completa.

---

## 2\. Perfil del desarrollador (referencia para Claude)

- Licenciado en Física, Doctor en Ciencias especialidad Energías Renovables.  
- Investigador Adjunto CONICET, INENCO–UNSa.  
- Docente de Transferencia de Calor y Materia (5° año Lic. Física y Lic. Energías Renovables).  
- Docente posgrado M.E.R.–UNSa: Transferencia de Calor y Materia, Energía Solar 1 y 2, Simulación de Procesos Termodinámicos en EERR, Secado Solar Industrial, Eficiencia Energética en la Industria, Domótica para Arquitectura Bioclimática.  
- Experiencia: diseño de secadores solares de alimentos a amplia escala de producción.  
- Software de simulación de referencia: **Simusol** ([www.simusol.org](http://www.simusol.org)), nivel experto.  
- Experiencia de programación: Visual Basic y C++ (oxidado). Entiende lógica de Python pero requiere que Claude codee.  
- Datos experimentales: dispone de mediciones de muchos secadores reales (a usar como casos de validación).  
- **Acceso bibliográfico:** Biblioteca Electrónica MINCyT (CONICET) — paywall-free a Elsevier (J Food Eng, Drying Technology, Energy Convers Manag, Food Res Int), Wiley, Springer, Tandfonline.

**Hardware:**

- Notebook DELL G15 5515, Ryzen 5000, 32 GB DDR4, GeForce RTX 3050 4 GB.  
- Sistema operativo: Fedora 44 con Plasma 6.6.4.  
- IDE: VS Code instalado desde repositorio oficial Microsoft (RPM), **no Flatpak**.  
- Cuenta Claude Pro activa.

---

## 3\. Decisiones técnicas tomadas

### 3.1 Stack tecnológico

| Área | Decisión |
| :---- | :---- |
| Lenguaje | Python 3.12 (desarrollo local) / 3.11 mínimo declarado en pyproject.toml |
| Cálculo científico | NumPy, SciPy, Matplotlib, pvlib, pandas |
| Interfaz | **Streamlit** (renderizado en navegador, multidispositivo) |
| Motor de EDOs | `scipy.integrate.solve_ivp` |
| Datos climáticos | NASA POWER vía `pvlib.iotools.get_nasa_power` |
| Repositorio | GitHub (público desde el inicio) |
| Licencia | **MIT** |
| Deploy opcional | Streamlit Community Cloud (gratuito, conecta directo a GitHub) |

**Nota sobre versión de Python:** se desarrolla en Python 3.12 (nativo de Fedora 44). El proyecto declara 3.11 como versión mínima soportada en `pyproject.toml`. No se usan features exclusivas de 3.12.

### 3.2 Idioma

Versión inicial: **español** completo (interfaz y código/comentarios). Bilingüe como mejora futura.

### 3.3 Sistema de unidades

**SI estricto en todo el cálculo interno.**

- Temperaturas: **Kelvin** en modelo y cálculos. Conversión a °C solo en frontera UI.  
- Humedad del producto: **base seca** `X = m_agua / m_sólido_seco` [kg/kg ms].  
- Humedad absoluta del aire: kg agua / kg aire seco.  
- Humedad relativa: fracción [0,1] internamente, % en UI.  
- Caudal másico: kg/s. Presión: Pa.  
- Series temporales: `pandas.DataFrame` con `DatetimeIndex` tz-aware.

### 3.4 Convención de ángulos solares

Hay **tres convenciones** en el proyecto, ninguna debe mezclarse:

| Nombre | Descripción | Dónde se usa |
| :---- | :---- | :---- |
| **Duffie** | 0°=Sur, +90°=Oeste, -90°=Este, ±180°=Norte. Rango [-180, +180] | Almacenamiento en `core/emplazamiento.py` |
| **UI360** | 0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste. Rango [0, 360) | Widget de acimut en `ui/p2_emplazamiento.py` (Sesión 20) |
| **pvlib** | 0°=Norte, 90°=Este, 180°=Sur, 270°=Oeste. Rango [0, 360) | Cálculos internos con `pvlib.irradiance` |

**Conversiones** (todas en `ui/componentes/unidades.py`, nunca en `core/` ni `calculos/`):
- Duffie → UI360: `α = (−γ) mod 360`
- UI360 → Duffie: `γ = (−α) mod 360`; si γ > 180: γ −= 360
- Duffie → pvlib: `ψ = (180 + γ) mod 360`
- pvlib → Duffie: `γ = (ψ − 180) mod 360`; si γ > 180: γ −= 360

### 3.5 Modelo físico de los colectores (Sesión 12)

- **Modelo cuasi-estacionario:** sin acumulación de calor en superficies sólidas.
- **Discretización espacial** en x (dirección del flujo). En cada nodo x: sistema algebraico no lineal para temperaturas de superficies; temperatura del fluido integrada con `solve_ivp`.
- **Factor de forma radiativo = 1** en todos los intercambios radiativos internos.
- **Absortividad de cubierta despreciable.**
- **Propiedades del aire constantes** a 323 K (50°C): cp=1007 J/kg·K, k=0.02814 W/m·K, μ=1.963×10⁻⁵ Pa·s, Pr=0.703. Densidad como gas ideal en convección natural.
- Solver: `solve_ivp` RK45, rtol=atol=1e-6, max_step=L/50. `fsolve` con warm-start entre nodos.

### 3.6 Correlaciones de transferencia de calor (Sesión 12)

Todas en `calculos/correlaciones_nusselt.py`. Default: selección automática según Re y L/Dh. Seleccionable por el usuario desde la UI.

**Flujo forzado:**

| Correlación | Régimen | Re | Observación |
| :---- | :---- | :---- | :---- |
| Shah & London (1978) asimétrico | Laminar | < 2300 | Nu=5.385; una pared caliente; L/Dh ≥ 50 |
| Shah & London (1978) simétrico | Laminar | < 2300 | Nu=8.235; dos paredes calientes (Tipo 2) |
| Heaton et al. (1964) | Laminar | < 2300 | Corrección entrada térmica; L/Dh < 50 |
| Gnielinski (1976) | Transición | 2300–10000 | Default transición |
| Dittus-Boelter (1930) | Turbulento | > 10000 | Dos paredes calientes (Tipo 2) |
| Sparrow & Liu (1979) | Turbulento | > 10000 | Una pared caliente; default Tipos 1, 3, 4 |
| Cengel & Ghajar (2014) | Turbulento | > 10000 | Corrección L/Dh < 10 |

**Convección natural:** Hollands et al. (1976), cavidad inclinada 0°–75°.

**Correlaciones atmosféricas:**
- `T_cielo`: Swinbank (1963): `T_cie = 0.0552 · T_amb^1.5` [K]. Válida para T_amb < 320 K.
- `h_viento`: McAdams (1954): `h = 5.7 + 3.8 · v` [W/m²·K]. Advertencia para v ≥ 5 m/s.

### 3.7 Validación

- Datos experimentales en `validation_data/`.  
- Tests automáticos contra datos reales (trabajo futuro).

---

## 4\. Arquitectura del software (pestañas)

### 4.1 Pestaña 1 — Tipología y Configuración — IMPLEMENTADA (Sesión 19)

**Tipologías:** Caja (convección natural, cámara=colector), Armario (colector externo), Gran escala (banco de colectores).  
**Modos:** Diario, Anual (8760 h). Criterios de día: solsticio verano/invierno, equinoccio, más caluroso, más frío, específico.  
Efecto cascada: al seleccionar tipología CAJA se anulan automáticamente `proyecto.colector` y `proyecto.motor` con aviso al usuario.

### 4.2 Pestaña 2 — Emplazamiento y recursos climáticos — IMPLEMENTADA (Sesión 10, mejorada Sesión 20)

NASA POWER vía pvlib. Caché parquet con metadata de altitud embebida. Política de huecos: ≤3h interpolación, >3h NaN. Ver §13.

**Sesión 20:**
- Widget de acimut cambiado a rango [0°, 360°] con convención UI360 (0=S, 90=E, 180=N, 270=O). Almacenamiento interno sigue siendo Duffie.
- Tab "Irradiancia solar" ahora muestra dos subgráficos: plano horizontal (GHI/DNI/DHI de NASA POWER) y plano del colector (POA global transpuesto con Hay-Davies vía pvlib), usando la pendiente e inclinación configuradas. Métricas de GHI anual vs POA anual con diferencia.

### 4.3 Pestaña 3 — Colector Solar de Aire — IMPLEMENTADA (Sesiones 11–12, mejorada Sesión 20)

**Sesión 11:** configuración de entrada, validación estática, UI.  
**Sesión 12:** motores numéricos de los 4 tipos.  
**Sesión 20:** selector de tipo, geometría diferenciada, evaluación gráfica.

**Jerarquía de dataclasses:**
```
Colector
├── ColectorUnidad    — materiales + geometría + velocidad de diseño
├── BancoColectores   — n_serie, n_paralelo
└── Optional[Chimenea]
```

**Campos clave de `ColectorUnidad` (actualizado Sesión 20):**
`ancho_m`, `largo_m`, `espaciado_m`, `n_cubiertas`, `velocidad_diseno_ms`,
`tipo_colector` (1–4), `espaciado_inferior_m` (canal absorbedor–fondo, Tipos 2/3/4),
`id_cubierta + espesor_cubierta_m`, `id_placa + espesor_placa_m`,
`id_aislante + espesor_aislante_m`, `id_fondo + espesor_fondo_m`.

**Sesión 20 — mejoras UI:**
- Nueva sección "Tipo de colector" al inicio con selectbox (Tipos 1–4) y descripción de cada configuración.
- Para Tipos 2, 3 y 4: aparecen dos campos de espaciado (canal superior cubierta–absorbedor y canal inferior absorbedor–fondo). Para Tipo 1: campo único.
- `balance_global.py` despacha al calculador correcto según `tipo_colector`; para Tipo 2 usa `T_salida_mezcla_K` como salida.
- Botón "Calcular desempeño del colector": evalúa el colector con los datos climáticos de P2 usando el modo de análisis definido en P1. Ver §20.1.

**Tests:** 32 tests en `test_colector.py` (Sesión 11) + 37+40 en test_colector_calc y test_colector_tipos234_calc (Sesión 12).

### 4.4 Pestaña 4 — Cámara de Secado — IMPLEMENTADA (Sesión 15)

Modelo de capa fina: Lewis, Page, Henderson, Midilli, Logarítmico. Isoterma GAB. Brentq para tiempo de secado. Curva X(t). Advertencias de diseño (13 tipos).  
Con corrección psicrométrica (Sesión 18): X_eq se recalcula con HR_media del canal, no solo HR_entrada.

### 4.5 Pestaña 5 — Calentamiento Auxiliar — IMPLEMENTADA (Sesión 16)

Tipos: resistencia eléctrica, quemador de biomasa. Modos: serie pos-colector, respaldo independiente. Control de set-point: si T_entrada > T_set, Q_efectivo=0; si Q_necesario < Q_max, throttle.

### 4.6 Pestaña 6 — Motor / Ventilador — IMPLEMENTADA (Sesión 16)

Motor eléctrico y extractor eólico. Cadena de potencias: P_hid → P_eje → P_elec → P_inst. Auto-estimación de ΔP desde P3 y P4 (Darcy-Weisbach + Ergun según flujo).

### 4.7 Pestaña 7 — Resultados — IMPLEMENTADA (Sesión 17)

Dashboard: colector, auxiliar, cámara, motor, balance energético, curva de secado. Jerarquía `Resultados` con `BloqueResultados` y hash SHA-256 para detectar stale.

---

## 5\. Modelo de datos central — COMPLETO (Tandas 1–5)

### 5.1–5.4 Filosofía, estructura y grafo de dependencias

Dataclasses anidadas. Raíz `Proyecto` en `st.session_state.proyecto`.

Grafo: `emplazamiento → clima → colector → auxiliar → camara → motor → global`

Invalidación: cada modificación de entradas marca como stale todos los bloques aguas abajo.

### 5.5–5.11 Tandas 1–5 (todas cerradas)

Ver versiones anteriores de la bitácora para detalle de cada dataclass. Resumen del estado actual:

**`core/` — todos CON CÓDIGO REAL:**
- `advertencias.py`, `proyecto.py`, `emplazamiento.py`, `clima.py`, `catalogo.py`, `colector.py`
- `camara.py`, `auxiliar.py`, `motor.py`, `resultados.py`

**`calculos/` — todos CON CÓDIGO REAL:**
- `clima_calc.py`, `correlaciones_nusselt.py`, `colector_calc.py`, `colector_tipos234_calc.py`
- `camara_calc.py`, `auxiliar_calc.py`, `motor_calc.py`, `balance_global.py`, `psicrometria.py`

**`ui/` — todas las pestañas CON CÓDIGO REAL:**
- `p1_tipologia.py` … `p7_resultados.py`, `componentes/unidades.py`

**Nota sobre patrón de resultados (Sesión 12):** las funciones `calcular_colector_tipo*` devuelven dataclasses propias (`ResultadosColectorTipoN`) — no `ResultadosColector` del core. La integración con `BloqueResultados` y `marcar_calculado()` es responsabilidad del código de orquestación en `resultados.py`. Separación de responsabilidades correcta.

---

## 6\. Estructura de carpetas del repo

```
secador_solar/
├── app.py                              ← CON CÓDIGO REAL
├── requirements.txt / requirements-dev.txt / pyproject.toml
├── README.md / LICENSE / .gitignore
├── core/                               ← modelo de datos
├── calculos/
│   ├── clima_calc.py                         (S10)
│   ├── correlaciones_nusselt.py              (S12)
│   ├── colector_calc.py                      (S12)
│   ├── colector_tipos234_calc.py             (S12–13)
│   ├── camara_calc.py                        (S15 + psicro S18)
│   ├── auxiliar_calc.py                      (S16)
│   ├── motor_calc.py                         (S16 + densidad/Ergun S19)
│   ├── balance_global.py                     (S17)
│   └── psicrometria.py                       (S18)
├── catalogo/
│   ├── materiales/                           (4 YAML)
│   └── productos/                            (5 YAML — a poblar)
├── ui/
│   ├── componentes/unidades.py               (S10)
│   ├── p1_tipologia.py                       (S19)
│   ├── p2_emplazamiento.py                   (S10 + bugfix S19)
│   ├── p3_colector.py                        (S11)
│   ├── p4_camara.py                          (S15)
│   ├── p5_auxiliar.py                        (S16)
│   ├── p6_motor.py                           (S16)
│   └── p7_resultados.py                      (S17)
├── data/cache/nasa_power/                    (.parquet, en .gitignore)
├── tests/
│   ├── conftest.py
│   ├── test_core/
│   │   ├── test_proyecto_coherencia.py       (3)
│   │   ├── test_emplazamiento.py             (13)
│   │   ├── test_colector.py                  (32)
│   │   ├── test_camara.py                    (32)
│   │   ├── test_auxiliar.py                  (25)
│   │   └── test_motor.py                     (65, incl. S19)
│   └── test_calculos/
│       ├── test_clima_calc.py                (9)
│       ├── test_unidades.py                  (25)
│       ├── test_correlaciones_nusselt.py     (59)
│       ├── test_colector_calc.py             (37)
│       ├── test_colector_tipos234_calc.py    (57)
│       ├── test_camara_calc.py               (38)
│       ├── test_psicrometria.py              (55)
│       └── test_balance_global.py            (18)
└── docs/bitacora/
```

**Total (2026-05-07, Sesión 20):** 487 tests pasan, 1 xfailed (charqui_vacuno sin params de capa fina, anotado como strict xfail).  
**Incremento en Sesión 20:** +14 tests (conversiones UI360↔Duffie en `test_unidades.py`).

---

## 7\. Convenciones de código

- Archivos/módulos: `snake_case`. Clases: `PascalCase`. Funciones/variables: `snake_case`.
- Variables físicas con sufijo de unidad: `largo_m`, `T_salida_K`, `Q_util_W`.
- **Regla de oro:** todo lo que entra a `core/` y `calculos/` está en SI. Conversiones solo en `ui/componentes/unidades.py`.
- Docstrings: Google style, en español, obligatorio en `core/` y `calculos/`.
- Type hints obligatorios. `from __future__ import annotations` en todos los módulos de core/.
- Sin `import streamlit` en `core/` ni `calculos/`. Sin cálculo físico en `ui/`.
- `ValueError` con código de error en `__post_init__`. `RuntimeError` en cálculos.
- Tests con imports absolutos (`from calculos.modulo import ...`). Sin hacks de `sys.path`. El `conftest.py` gestiona el path.
- Black `line-length=100`, Ruff reglas E, F, I, W.

---

## 8\. Entorno de desarrollo local

- Fedora 44, Python 3.12, venv en `~/proyectos/secador_solar/.venv`
- VS Code (RPM oficial), plugins: Python, Pylance, Black, Ruff, debugpy, autoDocstring, YAML, TOML, GitLens.
- **Tests: 487 tests pasan, 1 xfailed** (2026-05-07, Sesión 20). Ver §6 para desglose por archivo.
- Repo GitHub: pendiente de crear.

---

## 9\. Plan de trabajo

**COMPLETADO:**
1. ✅ Modelo de datos central (Tandas 1–5).
2. ✅ Estructura de carpetas, convenciones, dependencias, esqueleto.
3. ✅ Pestaña 2 (emplazamiento y clima) — Sesión 10.
4. ✅ Pestaña 3 — configuración y validación estática — Sesión 11.
5. ✅ Motor numérico 4 tipos de colector — Sesión 12.
6. ✅ Catálogo de correlaciones de Nusselt — Sesión 12.
7. ✅ Pestaña 4 (cámara de secado) — Sesión 15.
8. ✅ Pestaña 5 (auxiliar) — Sesión 16.
9. ✅ Pestaña 6 (motor/ventilador) — Sesión 16.
10. ✅ Pestaña 7 (resultados / balance global) — Sesión 17.
11. ✅ Psicrometría + corrección de X_eq por HR_media — Sesión 18.
12. ✅ Pestaña 1 (tipología y configuración) — Sesión 19.
13. ✅ Densidad de aire variable (Sutherland + ISA) — Sesión 19.
14. ✅ Ergun para lecho de producto en cámara vertical — Sesión 19.

**COMPLETADO (Sesión 20):**
15. ✅ Tipo de colector seleccionable (1–4) con geometría diferenciada en P3.
16. ✅ Acimut en P2 con rango [0°, 360°] y convención UI360.
17. ✅ Gráficas POA vs GHI en P2 (transposición Hay-Davies con pvlib).
18. ✅ Botón "Calcular desempeño del colector" en P3 con gráficas 9a y 9b (diario y anual).

**PENDIENTE:**
19. Crear repositorio en GitHub.
20. Poblar catálogo de productos (Doymaz & Bilici 2014, Kaymak-Ertekin & Gedik 2004).
21. Mejora §10: `h_int` natural canal estanco Tipos 3/4.
22. Verificar k manzana en frutas.yaml (k=0.0761 min⁻¹ posible error de unidades).

---

## 10\. Decisiones pendientes

- [ ] **Conteo de productos:** bitácora anterior menciona 19, catálogo actual tiene 16. Verificar.
- [ ] **Durazno sin coeficientes CF:** conseguir Doymaz & Bilici 2014 (`10.1515/ijfe-2014-0026`).
- [ ] **Manzana sin isoterma:** conseguir Kaymak-Ertekin & Gedik 2004 (`10.1016/j.lwt.2003.10.012`).
- [ ] **Poblar catálogo de productos** (Tanda 3 paso 2 EN CURSO).
- [ ] **Acople vs. desacople colector-cámara:** decidir al implementar Pestaña 4.
- [ ] **Tipología CAJA:** modelo físico distinto. Definir cuando llegue su turno.
- [ ] **Deserialización** (dict → dataclasses): trabajo futuro.
- [ ] **`chimeneas.yaml`:** pendiente crear con los 4 materiales específicos. Por ahora Chimenea valida contra `fondos.yaml`.
- [x] **`espaciado_c2_m` en ColectorUnidad** (Sesión 12, resuelto Sesión 13): se optó por **Opción 2a** — agregar kwargs `alto_cs_m: float | None = None` y `alto_ci_m: float | None = None` a las firmas de `calcular_colector_tipo2/3/4()`, no como atributo del core. Default `None` reproduce comportamiento simétrico previo (`alto = unidad.espaciado_m`). Permite geometrías asimétricas sin tocar `ColectorUnidad`. Ver §15.11.
- [ ] **h_int del canal estanco en Tipos 3 y 4** (Sesión 12): actualmente se usa Re=500 como proxy (laminar bajo). Mejora futura: calcular Ra con diferencia de temperatura entre paredes y usar `calcular_h_int(..., modo="natural")`.

---

## 11\. Herramientas y aclaraciones operativas

- **Project knowledge:** solo la bitácora. PDFs de papers retirados (Sesión 7). YAMLs de productos en máquina del usuario.
- **Claude Code:** disponible cuando el repo esté en GitHub.
- **Tokens:** sin PDFs, el contexto por turno es significativamente más liviano.

---

## 12\. Próximo paso al retomar

**Camino A — GitHub:**
*"Vamos a crear el repositorio en GitHub."*

**Camino B — Catálogo de productos:**
*"Cargué coeficientes para [productos]. Revisalos antes de seguir."*

**Camino C — Mejora física (h_int canal estanco):**
*"Vamos a cerrar la mejora de §10 del colector."*

---

## 13\. Decisiones técnicas — Sesión 10

### 13.1 Política de huecos — bug y solución

`pandas.interpolate(limit=3)` rellena desde ambos extremos y puede completar huecos de >3h. **Solución:** interpolar sin límite, luego restaurar NaN en grupos de duración >3h identificados por `groupby`.

### 13.2 Metadatos del caché parquet

Altitud NASA embebida como metadata de schema pyarrow (`b"altitud_nasa_m"`). Sin sidecar JSON.

### 13.3 Conversión de ángulos — caso degenerado

`acimut_pvlib_a_duffie(0°) = 180°`. Rango canónico `(−180°, +180°]`. Los tests de round-trip excluyen `−180°`.

### 13.4 Parámetros NASA POWER en pvlib 0.15.1

`"RH2M"` y `"PS"` se pasan con nombre NASA directamente. Altitud en `meta["altitude"]`.

---

## 14\. Decisiones técnicas — Sesión 11

### 14.1 Velocidad de diseño en ColectorUnidad

`velocidad_diseno_ms` va en `ColectorUnidad`: `Q_total = n_paralelo × (v × ancho × espaciado)`. No en Motor ni Camara.

### 14.2 Validación de materiales en `__post_init__`

`catalogo.py` carga los 4 YAML al importar (no lazy). `ColectorUnidad.__post_init__` valida IDs contra dicts globales.

### 14.3 Chimenea usa materiales de `fondos.yaml`

No existe `chimeneas.yaml`. Chimenea valida contra `fondos.yaml`. Pendiente crear el archivo.

### 14.4 Advertencias estáticas como función módulo

`advertencias_colector(colector)` en lugar de método de instancia. Permite testeo aislado sin UI.

---

## 15\. Decisiones técnicas — Sesión 12

### 15.1 Arquitectura cuasi-estacionaria en x

Sistema EDOs en `x ∈ [0, L]` (no EDP). `solve_ivp` integra en la dirección del flujo. `fsolve` con warm-start resuelve el sistema algebraico en cada nodo.

**Guess inicial de fsolve:** `T_abs_guess = max(T_f_activo, T_amb) + 20 K`. Un guess inadecuado puede llevar a raíces espurias físicamente imposibles — detectado y corregido durante testing.

### 15.2 Estructura de sistemas algebraicos por tipo

| Tipo | Descripción | EDOs | Sistema algebraico |
| :---- | :---- | :---- | :---- |
| 1 | Absorbedor en fondo, flujo por encima | 1 (`T_f`) | 3×3: `[T_cub_e, T_cub_i, T_abs]` |
| 2 | Absorbedor a media altura, flujo en ambos canales | 2 (`T_f_cs`, `T_f_ci`) | 4×4: `[T_cub_e, T_cub_i, T_abs, T_int]` |
| 3 | Flujo canal inferior, canal superior estanco | 1 (`T_f_ci`) | 4×4 + `T_f_cs = (T_cub_i + T_abs)/2` |
| 4 | Flujo canal superior, canal inferior estanco | 1 (`T_f_cs`) | 4×4 + `T_f_ci = (T_abs + T_int)/2` |

**Despeje analítico del canal estanco:** sin transporte de masa, `h·(T_f−T_sup) + h·(T_f−T_inf) = 0` → `T_f = (T_sup + T_inf)/2`. Exacto con h uniforme en ambas paredes.

**Temperatura de fondo en Tipos 2/3/4:** dos temperaturas: `T_int` (cara interna, hacia canal inferior) y `T_bot` (cara externa). Despeje: `T_bot = (U_ais·T_int + h_wind·T_amb) / (U_ais + h_wind)`.

### 15.3 Tipo 2 — velocidades independientes por canal

`v_diseno_cs_ms` y `v_diseno_ci_ms` como argumentos de `calcular_colector_tipo2()`, no como atributos del core. El core tiene un único `velocidad_diseno_ms`.

**Temperatura de mezcla a la salida:**
`T_mezcla = (m_cs · T_cs + m_ci · T_ci) / (m_cs + m_ci)`

### 15.4 Selección de correlación por tipo de pared

| Tipo y canal | `pared` en `calcular_h_int()` |
| :---- | :---- |
| Tipo 1 | `"una_pared"` |
| Tipo 2, canal superior | `"una_pared"` |
| Tipo 2, canal inferior | `"dos_paredes"` |
| Tipos 3 y 4, canal activo | `"una_pared"` |

### 15.5 Bug corregido — signo en F3 (balance del absorbedor, Tipos 2/3/4)

Raíz espuria detectada: `T_abs ≈ 301 K` con `T_f = 330 K` e `I_g = 800 W/m²`. Causa: los términos de cesión de calor del absorbedor al fluido sumaban en lugar de restar.

**Corrección:**
`F3 = rad_solar − conv_cs_abs − conv_ci_abs + rad_cub_abs − rad_abs_fondo`

donde `conv_*_abs = h·(T_abs − T_f)·W > 0` representa cesión (resta del balance). Detectado por los tests de invariantes físicas.

### 15.6 Correlación de Swinbank — límite de validez

`T_cie = T_amb` en T_amb ≈ 327 K (54°C). Para el rango de trabajo del software (T_amb < 320 K), la invariante se cumple. Documentado en tests.

### 15.7 Convergencia de Heaton hacia Shah & London

Convergencia proporcional a `L^{-2/3}`. Para diferencia < 0.1% se necesitaría L ≈ 19 km. En colectores reales, Heaton da Nu 5–40% mayor que Shah & London — física correcta que justifica su uso para L/Dh < 50.

### 15.8 Verificación de campos del core accedidos por los motores

Todos los campos de `ColectorUnidad` y `BancoColectores` usados en los motores numéricos verificados contra la bitácora §4.3: `ancho_m`, `largo_m`, `espaciado_m`, `velocidad_diseno_ms`, `id_cubierta`, `espesor_cubierta_m`, `id_placa`, `id_aislante`, `espesor_aislante_m`, `id_fondo`, `n_serie`, `n_paralelo`. **Todos existen en el core.** Keys del catálogo: `transmitancia_solar`, `emisividad_ir`, `conductividad_W_mK`, `absortividad_solar`. **Todas existen en los YAML.**

### 15.9 Convención de advertencias en los motores

Strings con prefijo `COL_*` (e.g., `"COL_FLUJO_LAMINAR: ..."`, `"COL_VIENTO_FUERA_RANGO_MCADAMS: ..."`). Consistente con Tipo 1. La conversión a la dataclass `Advertencia` del core es responsabilidad del código de orquestación en `resultados.py`.

### 15.10 Tests — imports en el repo real

Tests de `calculos/` usan imports absolutos del paquete (`from calculos.colector_tipos234_calc import ...`). Sin hacks de `sys.path` ni `types.ModuleType`. El `conftest.py` gestiona el path del proyecto.

---

## 16\. Decisiones técnicas — Sesión 13

### 16.1 Test de regresión bug §15.5 (signo F3)

Se agregó la clase `TestRegresionBugF3` en `tests/test_calculos/test_colector_tipos234_calc.py` con **6 tests** que blindan el bug original de signo en F3. Estrategia adoptada: **Opción A** (evaluación directa del residuo F3 en punto patológico), no Opción B (raíz espuria end-to-end).

**Punto patológico discriminante:**
`T_amb = 300 K`, `T_f_cs = T_f_ci = 330 K`, `T_abs = 301 K`, `I_g = 400 W/m²`.

Con los signos correctos `F3 ≈ +894 W/m`. Con el bug reintroducido (signos invertidos en `conv_cs_abs` y `conv_ci_abs`) `F3 ≈ −150 W/m`. El test exige `F3 > 500 W/m`, threshold elegido para resistir variaciones razonables de los demás términos del balance. La diferencia entre versiones es exactamente `2·(h_cs + h_ci)·(T_f − T_abs)·W ≈ 1044 W/m` con los parámetros de `_params_ref_tipo2()`.

**Calibración del threshold (validada localmente con stubs de `calcular_h_int`):**
- I_g=800, T_f=330, T_abs=301: F3_correcto=1207, F3_bug=163. Threshold > 200 < 1100 funciona.
- I_g=400, T_f=330, T_abs=301: F3_correcto=894, F3_bug=−150. **Cambio de signo** → más diagnóstico, threshold = 500.

**Tests complementarios** (parametrizados sobre `canal_activo ∈ {"superior", "inferior"}`):
- `test_F3_tipo2_signo_correcto_en_punto_patologico` — 1 test.
- `test_F3_tipos34_signo_correcto_en_punto_patologico` — 2 tests.
- `test_balance_isotermico_residuos_nulos_tipo2` — 1 test.
- `test_balance_isotermico_residuos_nulos_tipos34` — 2 tests.

Los tests isotérmicos (`I_g=0`, todas las T iguales, `T_cie = T_amb`) no detectan este bug específico (porque `T_abs = T_f → conv_*_abs = 0`), pero blindan contra otras familias de bugs de signo en F1, F2, F3, F4.

### 16.2 Alturas independientes de canales en Tipos 2/3/4 — Opción 2a

Resolución del pendiente §10 marcado en Sesión 12. Decisión: agregar las alturas como argumentos de los motores, no como atributos del core (`ColectorUnidad` sigue con un único `espaciado_m`).

**Firmas extendidas:**
```python
def calcular_colector_tipo2(colector, T_amb_K, I_g_W_m2, v_viento_ms, P_amb_Pa,
                            T_entrada_K, v_diseno_cs_ms, v_diseno_ci_ms,
                            alto_cs_m: float | None = None,
                            alto_ci_m: float | None = None,
                            correlacion_nusselt_cs=None, correlacion_nusselt_ci=None)

def calcular_colector_tipo3(colector, T_amb_K, I_g_W_m2, v_viento_ms, P_amb_Pa,
                            T_entrada_K,
                            alto_cs_m: float | None = None,
                            alto_ci_m: float | None = None,
                            correlacion_nusselt=None)

def calcular_colector_tipo4(colector, T_amb_K, I_g_W_m2, v_viento_ms, P_amb_Pa,
                            T_entrada_K,
                            alto_cs_m: float | None = None,
                            alto_ci_m: float | None = None,
                            correlacion_nusselt=None)
```

**Convención de nombres:** `alto_cs_m` / `alto_ci_m` (canal superior / canal inferior), consistente con `v_diseno_cs_ms`, `v_diseno_ci_ms`, `m_punto_cs_kgs`, `m_punto_ci_kgs`, `h_int_cs`, `h_int_ci`. Se renombraron también las variables internas `alto_c1_m` / `alto_c2_m` → `alto_cs_m` / `alto_ci_m` en los tres motores.

**Default `None` → simétrico:** si los kwargs llegan sin valor, ambos toman `unidad.espaciado_m`. Los 40 tests de Sesión 12 siguen pasando sin tocar.

**Validación dura:** constante local `ALTO_CANAL_MIN_M = 0.005` en `colector_tipos234_calc.py` (con comentario indicando que debe mantenerse sincronizada con `_ESP_MIN_M` en `core/colector.py`). Alturas menores levantan `ValueError` con códigos `GEO_ALTO_CS_MINIMO` / `GEO_ALTO_CI_MINIMO`. Se duplica la constante en `calculos/` para evitar dependencia inversa hacia `core/`.

**Tests nuevos** (clase `TestAlturasIndependientes`, **11 tests**):
- 3 tests: `default_None_equivale_a_pasar_espaciado` (uno por tipo).
- 6 tests: validación parametrizada sobre `(motor, canal)` levantando `ValueError`.
- 1 test: Tipo 2 con `alto_cs_m ≠ alto_ci_m` produce caudales y temperaturas de salida distintas.
- 1 test: Tipo 3 con canal estanco superior pequeño (caso de uso real).

### 16.3 Limitación física documentada en código — Tipo 3 con canal estanco pequeño

El caso de uso "canal superior estanco angosto en Tipo 3 para reducir pérdidas al ambiente" está soportado **geométricamente** por la Opción 2a, pero **el efecto físico completo requiere también** la mejora de §10: pasar `h_int` del canal estanco a `modo="natural"` con Ra calculado.

**Razón:** la implementación actual usa `Re=500` fijo en convección forzada para los canales estancos. Con esa correlación, achicar `alto_cs_m` reduce `Dh`, lo que aumenta `h_int = Nu·k/Dh` — **opuesto al efecto físico real** (donde reducir el canal inhibe convección natural y disminuye `h_int`).

Documentado en docstring del test `test_tipo3_canal_estanco_pequeno_caso_uso_real` para que no se pierda. Cuando se aborde la mejora de §10 (canal estanco modo natural), conviene hacerlo en una misma tanda con verificación de que en Tipo 3 con `alto_cs_m << alto_ci_m` la T de salida y el `Q_util` mejoran respecto al caso simétrico, como predice la física.

### 16.4 Plan de chequeos al pasar al repo local — COMPLETADO (Sesión 14)

✅ **Ejecutado 2026-05-06. Resultado: 235 tests, todos pasan. Ruff y black limpios.**

Los bugs encontrados y corregidos están documentados en §17.

**4) Validación funcional del test de regresión §15.5** (smoke check opcional, pendiente de ejecutar):

Para verificar que `TestRegresionBugF3` efectivamente detecta el bug, reintroducirlo temporalmente:

```bash
# En _sistema_nodo_tipo2 y _sistema_nodo_tipos34, cambiar:
#   F3 = rad_solar - conv_cs_abs - conv_ci_abs + rad_cub_abs - rad_abs_fondo
# por:
#   F3 = rad_solar + conv_cs_abs + conv_ci_abs + rad_cub_abs - rad_abs_fondo
pytest tests/test_calculos/test_colector_tipos234_calc.py::TestRegresionBugF3 -v
# Esperado: 3 fallos (los tests F3 con threshold 500 W/m) + 3 pasados (los isotérmicos).
# Revertir con git checkout antes de seguir.
```

Validado en Sesión 13 con stubs de `calcular_h_int`: con bug, `F3 ≈ −150 W/m` falla el assert `F3 > 500`; sin bug, `F3 ≈ +894 W/m` pasa.

### 16.5 Próximo paso al retomar (post-Sesión 14)

Suite verde confirmada. Los tres caminos abiertos siguen siendo los mismos que cierran §12:
- **A:** Pestaña 4 (cámara de secado) — siguiente cuello de botella del flujo end-to-end.
- **B:** Poblar catálogo de productos — bibliografía pendiente: Doymaz & Bilici 2014, Kaymak-Ertekin & Gedik 2004.
- **C:** Crear repositorio en GitHub — desbloquea Claude Code y compartibilidad.

Adicional pendiente con prioridad media tras §16.3:
- **D:** Cerrar la mejora de §10 (`h_int` natural en canal estanco), que complementa la Opción 2a recién implementada para que el caso de uso de Tipo 3 con canal superior pequeño se modele correctamente. Trabajo acotado, ~1 sesión.

---

## 17\. Correcciones técnicas — Sesión 14 (2026-05-06)

Corrida local sobre el repo tras Sesiones 12–13. Todos los bugs estaban en archivos no commitados (`??` en git status).

### 17.1 Imports rotos en tests de Sesión 12

`test_correlaciones_nusselt.py` y `test_colector_calc.py` usaban `sys.path.insert(0, os.path.dirname(__file__))` + imports directos (`from correlaciones_nusselt import ...`, `from colector_calc import ...`). Esto violaba la convención §7 y provocaba `ModuleNotFoundError` al correr pytest desde la raíz. Corregido a imports absolutos (`from calculos.X import ...`), eliminando el hack de path.

### 17.2 Funciones inexistentes en test_colector_calc.py

El archivo importaba `_h_int_forzado_W_m2K` y `_h_int_natural_W_m2K` de `colector_calc`, pero esas funciones fueron refactorizadas hacia `correlaciones_nusselt.py` en Sesión 12 y ya no existen en `colector_calc`. Solución: se agregaron wrappers locales de test con la interfaz antigua, implementados sobre `calcular_h_int()`.

### 17.3 Claves YAML incorrectas en los motores de cálculo

`colector_calc.py` y `colector_tipos234_calc.py` accedían a claves que no existen en los YAMLs:

| Clave usada en código | Clave real en YAML | Archivo |
| :--- | :--- | :--- |
| `conductividad_W_mK` | `conductividad_termica` | cubiertas.yaml, aislantes.yaml |
| `absortividad_solar` | `absortancia_solar` | placas.yaml |

La UI (`p3_colector.py`) y `catalogo.py` ya usaban los nombres correctos. Corregido en los dos motores de cálculo.

### 17.4 Clave emisividad_ir faltante en fondos.yaml

`_extraer_params_materiales()` en `colector_tipos234_calc.py` accedía a `mat_fondo["emisividad_ir"]` para el intercambio radiativo absorbedor↔fondo interior (Tipos 2/3/4). `fondos.yaml` no tenía esa clave. Agregada con valores de Incropera Tabla 12.1:

| Material | ε_IR |
| :--- | :--- |
| galvanizada_sin_pintura | 0.22 (oxidada/envejecida) |
| galvanizada_pintada | 0.90 (pintura oscura) |
| contrachapado_fenolico | 0.90 (madera/fenólico) |
| pino | 0.90 (madera no tratada) |

### 17.5 Variables locales sin usar en RHS de Tipos 3 y 4

En los closures `_construir_rhs_tipo3` y `_construir_rhs_tipo4`, quedaban asignaciones residuales de refactoring previo (`T_f_cs_conv`, `T_f_ci_conv`) y dos variables de desempaquetado nunca usadas (`T_cub_i` en Tipo 3, `T_int` en Tipo 4). Eliminadas/reemplazadas por `_`.

---

## 18\. Decisiones técnicas — Sesión 15 (2026-05-07) — Pestaña 4: Cámara de Secado

### 18.1 Modelos de capa fina implementados

Cinco modelos en `calculos/camara_calc.py`:

| Modelo | Ecuación | Referencia |
| :--- | :--- | :--- |
| Lewis | MR = exp(−k·t) | Lewis (1921) |
| Page | MR = exp(−k·t^n) | Page (1949) |
| Henderson-Pabis | MR = a·exp(−k·t) | Henderson & Pabis (1961) |
| Midilli | MR = a·exp(−k·t^n) + b·t | Midilli et al. (2002) |
| Logarítmico | MR = a·exp(−k·t) + c | Yagcioglu et al. (1999) |

**t en minutos** (convención universal en la literatura de secado). Las EDOs son algebraicas para t; el tiempo se obtiene con `scipy.optimize.brentq` sobre `MR(t) - MR_obj = 0`.

**MR_obj** = (X_obj − X_eq) / (X_0 − X_eq). Forzado al rango [0, 1) para evitar degeneraciones numéricas.

### 18.2 Isoterma GAB

X_eq = X_m · C · K · a_w / [(1 − K·a_w)(1 − K·a_w + C·K·a_w)]

donde a_w = HR (fracción). Se usa con HR_entrada si no hay corrección psicrométrica; con HR_media después de la corrección de Sesión 18.

Si no hay parámetros GAB en el catálogo: fallback a `humedad_equilibrio_aire_seco` escalar. Si tampoco existe ese campo → `ValueError` duro.

### 18.3 Masa evaporada — cálculo algebraico

```
m_seco = masa_total_kg / (1 + X_0)
masa_agua_evaporada = m_seco × (X_0 − X_obj)
```

Puramente algebraico, no integrado. Aplica tanto para el balance psicrométrico como para el resultado reportado.

### 18.4 Dataclass ResultadosCamara

Campos principales: `t_secado_s`, `t_secado_h`, `masa_agua_evaporada_kg`, `X_eq_kg_kg`, `MR_objetivo`, `curva_t_s`, `curva_X`, `advertencias`, `convergencia_ok`. Campos psicrométricos agregados en Sesión 18: ver §21.1.

### 18.5 Advertencias generadas por la cámara (13 tipos)

Prefijos: `GEO_*`, `CONS_*`, `BAND_*`, `FLUJO_*`, `PROD_*`, `INIO_*`. Las advertencias no bloquean la instanciación; se muestran antes de calcular. Separación de `advertencias_camara()` (función de módulo) del constructor para permitir testing aislado.

### 18.6 Test xfailed documentado

`test_advertencia_inio_carne_sin_isoterma` marcado con `@pytest.mark.xfail(strict=True)`. Razón: `charqui_vacuno` no tiene parámetros de capa fina → `MOD_CAPA_FINA_NO_DISPONIBLE` se lanza antes de poder instanciar `Camara`. Se convierte en test verde cuando se carguen los coeficientes cinéticos.

---

## 19\. Decisiones técnicas — Sesión 16 (2026-05-07) — Pestañas 5 y 6

### 19.1 Calentamiento auxiliar — control de set-point

`calcular_auxiliar()` implementa lógica de operación realista:

1. Si `T_entrada_K ≥ T_set_point_K`: `Q_efectivo = 0` (el colector ya calienta suficiente).
2. Si `T_entrada_K < T_set_point_K` y se especifica `masa_agua_a_evaporar_kg`: calcula `Q_necesario = m_dot_seco × cp_aire × (T_set − T_entrada)` y throttlea si `Q_necesario < Q_max`. Sin masa de agua: opera a plena potencia hasta set-point.
3. Quemador de biomasa: `consumo = Q_efectivo / (PCS_biomasa × η_comb)`, donde `PCS_biomasa = 15 MJ/kg` y `η_comb` es configurable.

### 19.2 Motor — cadena de potencias

```
P_hid = Q_vol × ΔP_total
P_eje = P_hid / η_ventilador
P_elec = P_eje / η_motor
P_inst = P_elec × FS
```

Si `perdida_carga_total_Pa is None` y hay componentes: `ΔP_total = ΔP_col + ΔP_cam + ΔP_duc`, donde `ΔP_duc` es 20 % de `ΔP_col + ΔP_cam` si no se especifica (advertencia `MOT_DUCTOS_ESTIMADOS`).

Corriente: `I = P_elec / (V_tensión × cos_φ)`, con `cos_φ = 0.85`. Solo si `tension_V` está definida.

### 19.3 Extractor eólico

Requiere `diametro_extractor_m`. Advertencia `MOT_EXTRACTOR_VIENTO_BAJO` si `v_viento_diseno < 2 m/s`. Las potencias se calculan igual (P_hid/P_eje); `η_motor = 1.0` (no hay motor eléctrico). El campo `potencia_electrica_W` queda como `None`.

### 19.4 Estimación ΔP en motor_calc.py (versión S16, antes de S19)

**Colector:** Darcy-Weisbach con ρ y μ fijos a 50°C (1.093 kg/m³, 1.963×10⁻⁵ Pa·s). Dh = 2We/(W+e). f = 64/Re (laminar) o 0.316 Re^−0.25 (Blasius, turbulento).  
**Cámara:** K\_malla × ρv_sup²/2 × n\_bandejas, donde v_sup = Q_vol/(ancho×alto).

Esta versión fue reemplazada en Sesión 19 por las funciones de densidad variable — ver §23.

---

## 20\. Decisiones técnicas — Sesión 17 (2026-05-07) — Pestaña 7: Resultados

### 20.1 Jerarquía de resultados

```
Resultados
├── ResultadosClima      ← irradiancia, T_amb, v_viento del día de análisis
├── ResultadosColector   ← T_salida, Q_util, η_colector
├── ResultadosAuxiliar   ← Q_efectivo, consumo_electrico o consumo_biomasa
├── ResultadosCamara     ← t_secado, masa_agua_evaporada, curva X(t)
├── ResultadosMotor      ← potencias, ΔP, corriente
└── ResultadosGlobal     ← E_solar, E_aux, E_motor, COP, fraccion_solar
```

Todas heredan `BloqueResultados` (hash SHA-256 sobre inputs para detectar stale).

### 20.2 balance_global.py — calcular_todo()

Encadena: colector → (temperatura de salida) → auxiliar → (temperatura efectiva) → cámara. Calcula balance energético:

```
E_solar [kWh] = Q_util_colector × t_secado_h
E_aux   [kWh] = Q_efectivo_aux × t_secado_h
E_evap  [kWh] = masa_agua × Lv   (Lv = 2.45 MJ/kg)
COP = E_evap / (E_solar + E_aux + E_motor)
fraccion_solar = E_solar / (E_solar + E_aux)
```

### 20.3 verificar_coherencia_proyecto() — 5 errores cruzados

| Código | Condición |
| :--- | :--- |
| `PROY_CAJA_CON_COLECTOR` | tipología CAJA pero `proyecto.colector is not None` |
| `PROY_CAJA_CON_MOTOR` | tipología CAJA pero `proyecto.motor is not None` |
| `PROY_ARMARIO_SIN_COLECTOR` | tipología ARMARIO pero `proyecto.colector is None` |
| `PROY_SIN_CAMARA` | `proyecto.camara is None` en cualquier tipología |
| `PROY_CAUDAL_INCOHERENTE` | caudal del motor ≠ caudal de la cámara (tolerancia 5%) |

---

## 21\. Decisiones técnicas — Sesión 18 (2026-05-07) — Psicrometría

### 21.1 Módulo calculos/psicrometria.py

Funciones implementadas:

| Función | Modelo | Referencia |
| :--- | :--- | :--- |
| `presion_vapor_saturacion(T_K)` | Buck (1981): `611.21·exp((18.678−T_C/234.5)·T_C/(257.14+T_C))` | Buck AL (1981) |
| `humedad_absoluta(HR, T_K, P_Pa)` | ω = ε·Pv/(P−Pv), ε = 0.622 | Gas ideal |
| `HR_desde_omega(ω, T_K, P_Pa)` | Inversa exacta | — |
| `omega_saturacion(T_K, P_Pa)` | humedad_absoluta(HR=1.0, ...) | — |
| `temperatura_punto_rocio(HR, T_K)` | Alduchov & Eskridge (1996) | J Appl Meteorol 35:601 |
| `balance_masa_camara(...)` | ω_sal = ω_ent + m_agua/(ṁ_seco·t) | Cuasi-estacionario |
| `entalpia_aire_humedo(T_K, ω)` | h = cp_as·ΔT + ω·(Lv + cp_v·ΔT) | — |

Constantes: cp_as=1006 J/kg·K, cp_v=1805 J/kg·K, Lv=2 501 000 J/kg, T_ref=273.15 K.

### 21.2 Corrección psicrométrica en calcular_tiempo_secado()

Bloque agregado al final del motor de cámara (después del primer brentq):

1. Calcular ω_entrada desde `(HR_entrada, T_operacion, P)`.
2. Balance de masa: ω_salida = ω_entrada + masa_agua_evaporada / (ṁ_seco · t_secado).
3. Calcular HR_salida = `HR_desde_omega(ω_salida, T_operacion, P)`.
4. Advertir si `HR_salida > 0.95` (`CAM_RIESGO_SATURACION_AIRE`).
5. HR_media = (HR_entrada + HR_salida) / 2.
6. Recalcular X_eq con `HR_media` (via GAB o fallback).
7. Si `|X_eq_corregido − X_eq_original| > 0.001 kg/kg`: re-ejecutar brentq con X_eq corregido → `t_secado_corregido`.

Campos nuevos en `ResultadosCamara`: `omega_entrada_kg_kg`, `omega_salida_kg_kg`, `HR_salida`, `HR_media`, `X_eq_corregido_kg_kg`, `t_secado_corregido_s`.

**Efecto físico:** el aire húmedo aumenta X_eq (el producto no puede secarse tan bajo como con aire seco), por lo que el tiempo corregido es mayor o igual que el original. La corrección es significativa cuando el caudal es bajo y/o la masa de agua es grande.

### 21.3 Manejo de `HR=None` en ConfiguracionFlujo

Si `flujo.HR_entrada_fraccion is None`, la función toma `HR = 0.0` como fallback conservador (aire seco → X_eq mínimo → tiempo mínimo, sin corrección psicrométrica). Se genera la advertencia `FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA` en el nivel de diseño.

---

## 22\. Decisiones técnicas — Sesión 19 (2026-05-07) — Pestaña 1 y bug matplotlib

### 22.1 Pestaña 1 — Tipología y Configuración

Implementada en `ui/p1_tipologia.py`. Tres secciones:

- **A — Metadatos:** nombre del proyecto, autor, notas libres.
- **B — Tipología:** radio con descripción expandida por opción. Efecto cascada si se selecciona CAJA: anula `proyecto.colector` y `proyecto.motor` con aviso.
- **C — Modo y criterio de día:** DIARIO o ANUAL (ANUAL deshabilitado para CAJA en v0). Selectbox de DiaAnalisis; datepicker adicional para DiaAnalisis.ESPECIFICO.

### 22.2 Bug matplotlib FixedLocator — causa raíz y solución definitiva

**Síntoma:** `UserWarning: FixedLocator should be used with FixedFormatter — 13 locations but 12 labels` en las figuras de irradiancia, temperatura, viento y tabla mensual de P2.

**Causa raíz:** UTC→local timezone conversion crea un bucket de enero extra cuando el primer dato UTC del año corresponde al 31/12 en hora local. `resample("ME")` sobre el año completo producía 13 grupos (dic previo + 12 meses del año), pero las etiquetas eran solo 12.

**Primera corrección (insuficiente):** cambiar `ax.set_xticks(meses) + ax.set_xticklabels(labels)` a `ax.set_xticks(x, labels=...)`. No atacaba la causa raíz.

**Corrección definitiva:** después de la conversión de zona horaria, filtrar:

```python
datos_local = datos_local[datos_local.index.year == clima.anio]
```

y derivar las etiquetas del eje x directamente desde el índice del resample:

```python
etiquetas = [_MES_ABBR[ts.month - 1] for ts in serie_mensual.index]
```

Esto garantiza n_ticks == n_labels independientemente de artefactos de zona horaria.

---

## 23\. Decisiones técnicas — Sesión 19 (2026-05-07) — Densidad variable + Ergun

### 23.1 Propiedades del aire como funciones de T y P

Tres funciones nuevas en `calculos/motor_calc.py`:

**`presion_atmosferica(altitud_m)`** — ISA estándar, troposfera:

P = 101 325 × (1 − 2.25577×10⁻⁵ · h)^5.25588

Error < 0.1% para h < 11 000 m.

**`densidad_aire(T_K, P_Pa)`** — gas ideal:

ρ = P / (R_aire · T),   R_aire = 287.058 J/(kg·K)

**`viscosidad_aire(T_K)`** — ley de Sutherland (1893):

μ = μ_ref · (T/T_ref)^1.5 · (T_ref + S) / (T + S)

con μ_ref = 1.716×10⁻⁵ Pa·s, T_ref = 273.11 K, S = 110.4 K. Error < 2% para 200–2 000 K.

Antes de S19 se usaban constantes fijas (ρ=1.093 kg/m³, μ=1.963×10⁻⁵ Pa·s @ 50°C). Ahora `estimar_delta_P_colector` y `estimar_delta_P_camara` aceptan `T_K` y `P_Pa` con defaults iguales a 50°C/nivel del mar → **retrocompatibles**.

### 23.2 Ecuación de Ergun para lecho de producto

Aplicable en flujo **VERTICAL_ASCENDENTE** cuando `diametro_eq_particula_m` está definido.

**Ecuación de Ergun (1952):**

ΔP/L = 150·μ·v₀·(1−ε)² / [(Φ_s·d_p)²·ε³] + 1.75·ρ·v₀²·(1−ε) / [(Φ_s·d_p)·ε³]

donde:
- v₀ = Q_vol / area_bandeja [m/s] — velocidad superficial a través del lecho
- L = espesor_capa_m [m]
- ε = porosidad_lecho (default 0.45)
- Φ_s = esfericidad (default 0.60 — valor típico para rodajas de fruta)
- d_p = diametro_eq_particula_m

El término viscoso (Blake-Kozeny) domina para Re_p < 10; el inercial (Burke-Plummer) para Re_p > 1000; Ergun cubre el rango completo.

### 23.3 Nuevos campos en ConfiguracionBandejas

| Campo | Tipo | Default | Validación |
| :--- | :--- | :--- | :--- |
| `porosidad_lecho` | float | 0.45 | (0, 1) — BAND_POROSIDAD_INVALIDA |
| `diametro_eq_particula_m` | Optional[float] | None | > 0 si no es None — BAND_DIAMETRO_PARTICULA_NO_POSITIVO |
| `esfericidad` | float | 0.60 | (0, 1] — BAND_ESFERICIDAD_INVALIDA |

Si `diametro_eq_particula_m is None` → ΔP_lecho = 0 (la función `_delta_P_lecho_por_bandeja` retorna 0 inmediatamente).

### 23.4 Distinción HORIZONTAL vs. VERTICAL en estimar_delta_P_camara

**HORIZONTAL** (default): v_ref = Q_vol / (ancho × alto), ΔP = K_malla × ρv²/2 × n_bandejas. El lecho no está en el camino del flujo → Ergun no aplica.

**VERTICAL_ASCENDENTE**: v₀ = Q_vol / area_bandeja, ΔP por bandeja = ΔP_malla + ΔP_lecho. Total = (ΔP_malla + ΔP_lecho) × n_bandejas.

### 23.5 Tests nuevos — Sesión 19

Agregados en `tests/test_core/test_motor.py`:

- `TestPresionAtmosferica` (4 tests): nivel del mar, Salta ≈87 500 Pa, monotonía.
- `TestDensidadAire` (5 tests): valores 0°C/50°C, decrece con T, gas ideal exacto.
- `TestViscosidadAire` (4 tests): valor referencia Sutherland, crece con T, siempre positiva.
- `TestDeltaPColectorDensidadVariable` (2 tests): smoke con altitud y temperatura.
- `TestDeltaPCamaraVerticalErgun` (6 tests): Ergun activo > sin Ergun, fórmula malla exacta, monotonía en caudal y espesor.
- `TestConfiguracionBandejasErgun` (11 tests): errores duros de los 3 campos nuevos + casos límite válidos.

**Total sesión 19:** +30 tests → 473 pasan.

---

## 24\. Decisiones técnicas — Sesión 20 (2026-05-07) — Mejoras UX/UI

### 24.1 Mejora #6 — Tipo de colector seleccionable en P3

**Motivación:** la pestaña P3 no permitía al usuario distinguir ni cambiar entre los 4 tipos de colector de placa plana implementados en los motores numéricos.

**Cambios en `core/colector.py`:**
- Dos nuevos campos en `ColectorUnidad`:
  - `tipo_colector: int = 1` — selector entre los 4 tipos.
  - `espaciado_inferior_m: float = 0.025` — altura del canal absorbedor–fondo (usado en Tipos 2, 3, 4).
- Validación dura en `__post_init__`: `tipo_colector` debe estar en {1, 2, 3, 4}; `espaciado_inferior_m ≥ 5 mm`.
- Nuevas advertencias estáticas `GEO_ESPACIADO_INF_PEQUENO` / `GEO_ESPACIADO_INF_GRANDE` para Tipos 2/3/4.

**Cambios en `ui/p3_colector.py`:**
- Nueva primera sección "Tipo de colector" con selectbox y descripción por tipo.
- Sección de geometría diferenciada: Tipo 1 muestra un campo de espaciado ("cubierta–placa"); Tipos 2/3/4 muestran dos campos ("canal superior" y "canal inferior").
- `ColectorUnidad(...)` incluye `tipo_colector` y `espaciado_inferior_m`.

**Cambios en `calculos/balance_global.py`:**
- Despacha al calculador correcto según `tipo_colector` (1→`calcular_colector_tipo1`, 2→tipo2, etc.).
- Para Tipo 2: usa `T_salida_mezcla_K` como temperatura de salida.
- `ResultadosCompletos.colector` tipado como `Optional[Any]` (acepta los 4 tipos de resultado).

**Cambios en `ui/p7_resultados.py`:**
- Usa `getattr` para `T_salida_K` (Tipo 2 → `T_salida_mezcla_K`), `Re_medio`, `h_int_medio`, `regimen_flujo`, que tienen nombres distintos según el tipo.

### 24.2 Mejora #7 — Acimut [0°, 360°] con convención UI360

**Motivación:** la convención Duffie con rango [-180, +180] resulta contraintuitiva. La nueva convención UI360 (0=S, 90=E, 180=N, 270=O) es más natural y cubre el rango completo.

**Arquitectura:** tres convenciones en el proyecto (ver §3.4 actualizado). La conversión ocurre exclusivamente en `ui/componentes/unidades.py`. El almacenamiento en `core/emplazamiento.py` sigue siendo Duffie sin cambios.

**Nuevas funciones en `ui/componentes/unidades.py`:**
- `acimut_duffie_a_ui360(γ)` → α = (−γ) mod 360
- `acimut_ui360_a_duffie(α)` → γ = (−α) mod 360; si γ > 180: γ −= 360

**Cambios en `ui/p2_emplazamiento.py`:**
- Widget `number_input` de acimut cambiado a rango [0, 360] con etiqueta "0°=Sur, 90°=Este, 180°=Norte, 270°=Oeste".
- Tabla de referencia de puntos cardinales actualizada (SE, NE, NO, SO).
- Conversión UI360→Duffie antes de construir `Emplazamiento(...)`.

**Tests nuevos en `tests/test_ui/test_unidades.py`:**
- `test_acimut_duffie_a_ui360` (7 casos parametrizados): Sur, Este, Norte (±180°), Oeste, SE.
- `test_acimut_ui360_a_duffie` (6 casos parametrizados): Sur, Este, Norte, Oeste, SE, SO.
- `test_acimut_ui360_duffie_son_inversas` (6 ángulos en round-trip).
- **Total: +14 tests → 487 pasan.**

**Caso degenerado Norte:** `duffie_a_ui360(+180°) = 180°` y `duffie_a_ui360(−180°) = 180°` (ambas representaciones de Norte dan el mismo valor UI360). En el sentido inverso, `ui360_a_duffie(180°) = +180°`.

### 24.3 Mejora #8 — Gráficas POA en P2

**Motivación:** la gráfica de irradiancia solo mostraba plano horizontal (GHI/DNI/DHI de NASA POWER), pero el diseño de un colector depende de la irradiancia sobre el plano inclinado (POA).

**Implementación:**
- Función `_calcular_poa_horaria(datos_local, lat, lon, alt, pendiente, acimut_pvlib)` en `ui/p2_emplazamiento.py`:
  1. `pvlib.solarposition.get_solarposition()` para ángulos solares hora a hora.
  2. `pvlib.irradiance.get_total_irradiance()` con modelo Hay-Davies para transposición POA.
  3. Clip de valores negativos (nighttime).
- Función `_fig_irradiancia_comparativa(datos_local, poa_horaria)`: dos subplots verticales.
  - Panel superior: barras GHI/DHI/DNI (plano horizontal).
  - Panel inferior: barra POA global (plano colector, en verde).
- Métricas bajo la figura: GHI anual, POA anual, diferencia (útil para evaluar la ganancia de inclinar el colector).

**Nota de performance:** el cálculo de posición solar para 8760 horas + transposición tarda < 1 segundo con pvlib.

### 24.4 Mejora #9 — Evaluación del desempeño del colector (Botón "Calcular")

**Motivación:** el usuario necesita ver el desempeño térmico del colector configurado en condiciones reales, sin tener que correr el balance global de P7.

**Arquitectura:** todas las funciones auxiliares viven en `ui/p3_colector.py` (ya había imports de matplotlib/numpy/pvlib allí). Sin dependencias inversas de `core/` hacia `ui/`.

**Flujo de datos:**
1. Verifica que existan `proyecto.emplazamiento`, `proyecto.clima`.
2. Convierte clima a zona horaria local y recorta al año de análisis.
3. Según `cfg.modo_analisis`:
   - **DIARIO:** selecciona el día según `cfg.dia_analisis` (→ `_seleccionar_dia`), corre el solver para cada hora con POA > 50 W/m².
   - **ANUAL:** para cada mes, toma el día 15 (o el más cercano disponible), encuentra el mediodía solar (hora con POA máxima), corre el solver una vez por mes.
4. Persiste resultados en `st.session_state["p3_eval"]` para sobrevivir reruns.

**Función `_correr_colector(colector, T_amb_K, I_g_W_m2, v_viento_ms)`:**
- Despacha al motor correcto según `tipo_colector`.
- `T_entrada_K = T_amb_K` (análisis standalone del colector).
- `v_viento_ms = max(v_viento_ms, 0.5)` para evitar singularidad en McAdams.
- Retorna `None` si I_g < 50 W/m² (sin sol) o si el solver falla.

**Extracción de perfil de temperatura del fluido (9b) por tipo:**
| Tipo | Campo usado |
| :--- | :--- |
| 1 | `T_fluido_K` |
| 2 | `(T_f_cs_K + T_f_ci_K) / 2` (promedio de los dos canales) |
| 3 | `T_f_ci_K` (canal inferior activo) |
| 4 | `T_f_cs_K` (canal superior activo) |

**Gráfica 9a — T_salida vs tiempo:**
- DIARIO: T_salida y T_ambiente vs hora, POA en eje secundario, línea vertical en mediodía solar.
- ANUAL: T_salida y T_ambiente a mediodía del día 15 vs mes (12 puntos), POA en eje secundario.

**Gráfica 9b — Perfil T_fluido vs largo:**
- DIARIO: una curva T_fluido(x) a mediodía solar, T_entrada marcada como línea horizontal de referencia.
- ANUAL: 12 curvas superpuestas (una por mes), cada una en distinto color.

**Simplicidad vs. precisión en modo ANUAL:** se usa el día 15 de cada mes a mediodía solar como representativo del mes. Esto es suficiente para prediseño. Un refinamiento futuro podría promediar múltiples días del mes, pero no agrega valor pedagógico significativo.

**Performance esperada:**
- DIARIO: ~10 llamadas al solver × ~300 ms c/u ≈ 3 segundos.
- ANUAL: 12 llamadas × ~300 ms ≈ 4 segundos.

Ambos son aceptables para un botón "Calcular" con `st.spinner`.
