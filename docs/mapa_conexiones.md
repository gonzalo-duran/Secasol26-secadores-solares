# Mapa de conexiones — Secasol

> Documento auto-generado el 2026-05-19 (revisado al cierre de S30 extendida 2026-05-20, S31 2026-05-21, S32 2026-05-22, S34 2026-05-29, S35 2026-06-01, **S36–S45 2026-06-23**, **S47 2026-07-06**, **S48 2026-07-07**).
> Objetivo: detectar **widgets UI sin consumidor en `calculos/`** y **campos consumidos sin widget UI** (toggles/inputs huérfanos).
>
> S33 (deploy a HF Spaces) no introdujo cableado widget→campo→consumidor: ver `docs/bitacora/bitacora_sesion33.md`.
> El detalle histórico S36→S45 está consolidado al final (sección "Resueltos"); la **tabla maestra** ya refleja S40 (modo industrial), S44 (techo translúcido + ventana CAJA/ARMARIO) y S47 (cámara radiativa orientada).

---

## Resumen ejecutivo

> Nota S48: el **manual de usuario** (mejora 36) no introduce cableado widget→campo→consumidor: la vista `?manual=<slug>` (`ui/manual.py`, intercept en `Secasol.py`) es **stateless** (no toca `st.session_state.proyecto`) y los botones "📖 Manual" de P1–P7 (`ui/componentes/manual_link.py`) solo emiten un anchor `target=_blank`.
>
> Nota S49: la **internacionalización ES/EN/PT** (mejora 37, fases F0–F4) tampoco introduce cableado widget→campo→consumidor: solo reemplaza literales visibles por `t("clave")` (diccionarios `ui/idiomas/{es,en,pt}/*.yaml`). El único cambio de estado es el selector 🌐 (`ui/componentes/idiomas.py::selector_idioma`) que guarda `st.session_state["idioma"]` ↔ query param `?lang=`, y el fix de `nav_seccion` (ahora guarda claves estables `p1..p7` en vez del rótulo, para que la navegación sobreviva al cambio de idioma). Ningún campo del `Proyecto` cambió.

Desconexiones / atenuaciones reales vigentes (eran 3 a inicio de S30):

| # | Widget UI | Campo escrito | Estado |
|---|-----------|---------------|--------|
| 1 | "Espesor placa absorbedora [mm]" (P3) | `proyecto.colector.unidad.espesor_placa_m` | ⚠️ No es leído por ningún cálculo térmico (se asume capacitancia despreciable). Decisión consciente de no incorporar capacitancia de placa por ahora. |
| 2 | Sliders **T_op / HR_op** del aire de entrada (P4) | (condición de borde, no campo persistente) | ⚠️ **Atenuados desde S39.** Con coeficientes de transporte variables en t (`coef_transporte_func` recalculado por paso), en modos **Sintético / Día real / Anual** el borde y los coeficientes salen del clima/colector → los sliders **no influyen** en el resultado. **Solo** son condición de borde efectiva en modo **Constantes**. Decisión consciente (ver `bitacora_sesion39.md`). |

**Corregido en S30 (2026-05-19):**

- **"N° cubiertas" (P3)**: propagado a los 4 motores numéricos vía `_U_cubierta_efectiva` (Hollands + radiación gris paralela). Acompañó la corrección de dos bugs preexistentes en los signos del residual `_sistema_nodo` (F1 en los 4 tipos, F3 en Tipo 1) que producían raíces espurias con `T_cub_e` físicamente imposibles. Ver `validacion/validacion_hwb.py`.
- **F4 Tipos 2/3/4**: agregado el término convectivo `conv_ci_int = h·(T_int − T_f_ci)·W_abs` al balance de la cara interna del fondo, restaurando coherencia local con la EDO del fluido inferior (que ya lo cobraba). Ver `validacion/comparar_f4.py`.
- **Chimenea solar**: el huérfano se cerró completo en 4 pasos. (a) Nuevo `calculos/chimenea_calc.py` con `delta_P_tiro_Pa`, `delta_P_chimenea_Pa`, `caudal_natural_kgs` (tiro térmico + brentq sobre equilibrio). (b) Migrada estructuralmente de `Colector` a `Proyecto` top-level (nuevo `core/chimenea.py`) para que también aplique a tipología CAJA. (c) UI propia en **P6** (Motor), accesible cuando el toggle de motor está OFF. (d) Integrada en `balance_global.calcular_todo`: cuando motor=None y chimenea presente, el caudal natural reemplaza al caudal manual de la cámara durante la simulación (try/finally restaura).

**Completado en S30 extendida (2026-05-19/20)** — cierre físico completo del lazo natural:

- **Visualización en P7 modo constantes**: panel dedicado, tabla expander con 8 filas, warning explícito si desviación |ṁ_nat − ṁ_design|/ṁ_design > 30 %, snapshots `.txt`/`.json` con bloque chimenea.
- **Picard cerrado por el colector en modo constantes**: `calcular_todo` itera T_chim ↔ ṁ_nat ↔ T_salida_colector mutando `velocidad_diseno_ms` del colector en cada paso (try/finally restaura). 10 iter máx, tol 0.5 K. Demo: converge en 7 iter; ṁ_nat ~55 % menor que el single-pass original (que sobreestimaba con v de diseño).
- **Acople transitorio con motor TD**: `calcular_todo_transitorio` corre Picard sobre el horizonte (5 iter máx). `m_dot_aire_seco_kg_s` ya era array en `ForzantesAire`; el motor TD interpola por t. Auxiliar transitorio recibe ṁ promedio del horizonte (limitación de primer orden documentada). `ResultadosCompletosTransitorio.chimenea` poblado con series horarias.
- **Re-corrida del colector hora a hora**: nuevo `_correr_colector_horizonte` itera el solver del colector cada hora con v efectiva `ṁ_nat(t) / (ρ · A_canal · n_par)`. Cambia T_sal_col(t) ~−15 °C respecto a la forzante UI precomputada con velocidad de diseño (en escenarios donde ṁ_nat ≠ ṁ_design).
- **POA precomputada en `ForzantesAire`**: nuevo campo `I_g_POA_W_m2` (opcional). Helper compartido `calculos/clima_calc.calcular_POA_horizonte` aplica transposición Liu-Jordan con pvlib (mismo modelo que P3, ahora deduplicado). P4 puebla la POA desde clima real; el sugerido de I_g en P7 modo constantes ahora sale de quantile 90 de POA. Si POA no está disponible (forzante sintética, clima incompleto), el balance global cae a GHI con aviso explícito `ADV_PICARD_POA_NO_DISPONIBLE`.

Todas las demás conexiones revisadas (toggles de auxiliar, motor, cubierta translúcida, pared compuesta, HR de entrada, T_prod inicial, etc.) están correctamente cableadas.

---

## Diagrama 1 — Arquitectura general (3 capas)

```mermaid
graph LR
  subgraph UI["ui/ (Streamlit)"]
    P1[P1 Tipología]
    P2[P2 Emplazamiento]
    P3[P3 Colector]
    P4[P4 Cámara]
    P5[P5 Auxiliar]
    P6[P6 Motor]
    P7[P7 Resultados]
  end

  subgraph CORE["core/ (dataclasses, SI estricto)"]
    PROY[Proyecto]
    CFG[Configuracion]
    EMP[Emplazamiento]
    CLI[Clima]
    COL[Colector]
    CAM[Camara]
    AUX[Auxiliar]
    MOT[Motor]
    CHIM[Chimenea]
    RES[Resultados]
    PROY --> CFG
    PROY --> EMP
    PROY --> CLI
    PROY --> COL
    PROY --> CAM
    PROY --> AUX
    PROY --> MOT
    PROY --> CHIM
    PROY --> RES
  end

  subgraph CALC["calculos/ (motores numéricos)"]
    CLIMA_C[clima_calc.py]
    COL_C[colector_calc.py / tipos234_calc.py]
    CAM_C[camara_calc.py / termodinamica.py]
    AUX_C[auxiliar_calc.py]
    MOT_C[motor_calc.py]
    CHIM_C[chimenea_calc.py]
    BAL[balance_global.py]
  end

  P1 --> CFG
  P2 --> EMP
  P2 -.descarga.-> CLI
  P3 --> COL
  P4 --> CAM
  P5 --> AUX
  P6 --> MOT
  P6 --> CHIM
  P7 -.lee.-> RES

  EMP --> CLIMA_C
  COL --> COL_C
  CAM --> CAM_C
  AUX --> AUX_C
  COL --> MOT_C
  CAM --> MOT_C
  MOT --> MOT_C
  CHIM --> CHIM_C
  PROY --> BAL
  BAL --> RES
```

**Regla arquitectónica**: `core/` y `calculos/` no importan `streamlit`. La conversión de unidades **físicas** (°C↔K, kPa↔Pa, %↔fracción) ocurre en `ui/componentes/unidades.py`. Desde S35 las conversiones de **ángulos** (Duffie↔UI360↔pvlib) son matemática pura y viven en `calculos/conversiones_angulo.py` (fuente de verdad única, consumida por `clima_calc` y por el catálogo de barridos); `unidades.py` las **re-exporta** por compatibilidad con la UI histórica. Nunca duplicar la fórmula.

---

## Diagrama 2 — Cascada de invalidación

```mermaid
graph TD
  T[Cambio en P1: tipología → CAJA] -.invalida.-> COL_NULL[proyecto.colector = None]
  T -.invalida.-> MOT_NULL[proyecto.motor = None]

  LL[Cambio lat/lon en P2] -.invalida.-> CLI_NULL[proyecto.clima = None]

  AUX_OFF[Toggle OFF P5] --> AUX_NULL[proyecto.auxiliar = None]
  MOT_OFF[Toggle OFF P6] --> MOT_NULL2[proyecto.motor = None]
  CHIM_OFF[Toggle chimenea OFF P6] --> CHIM_NULL[proyecto.chimenea = None]

  classDef warn fill:#fff3cd,stroke:#856404
  class COL_NULL,MOT_NULL,CLI_NULL,AUX_NULL,MOT_NULL2,CHIM_NULL warn
```

---

## Diagrama 3 — P3 Colector (estado final S30)

```mermaid
graph LR
  subgraph UI3["ui/p3_colector.py"]
    W_TIPO["selectbox Tipo colector"]
    W_NCUB[selectbox N° cubiertas]
    W_ESPCC[number_input esp_cub_cub si n=2]
    W_IDCUB[selectbox id_cubierta]
    W_ECUB[number_input espesor_cubierta]
    W_IDPL[selectbox id_placa]
    W_EPL["number_input espesor_placa ⚑"]
    W_IDAI[selectbox id_aislante]
    W_EAI[number_input espesor_aislante]
    W_IDFO[selectbox id_fondo]
    W_EFO[number_input espesor_fondo]
    W_GEO[ancho/largo/espaciado/v_diseño]
    W_BANCO[n_serie/n_paralelo]
  end

  subgraph DATA["core/colector.py"]
    U[ColectorUnidad]
    B[BancoColectores]
  end

  subgraph CONS["Consumidores en calculos/"]
    C1[colector_calc.py Tipo 1]
    C234[colector_tipos234_calc.py Tipos 2-4]
    UCE["_U_cubierta_efectiva (Hollands + radiación)"]
    MC[motor_calc.estimar_delta_P_colector]
  end

  W_TIPO --> U
  W_NCUB --> U
  W_ESPCC --> U
  W_IDCUB --> U
  W_ECUB --> U
  W_IDPL --> U
  W_IDAI --> U
  W_EAI --> U
  W_IDFO --> U
  W_GEO --> U
  W_BANCO --> B

  W_EPL -.->|⚠️ huérfano| U
  W_EFO -.->|solo Tipo1 advertencia| U

  U --> UCE
  UCE --> C1
  UCE --> C234
  U --> MC
  B --> C1
  B --> C234
  B --> MC

  classDef orph fill:#f8d7da,stroke:#721c24
  classDef fix fill:#d4edda,stroke:#155724
  class W_EPL orph
  class W_NCUB,W_ESPCC,UCE fix
```

**Hallazgos P3 (actuales)**:
- `n_cubiertas` + `espaciado_entre_cubiertas_m`: ✓ Conectados a los 4 motores numéricos vía `_U_cubierta_efectiva` (corrección S30, 2026-05-19). La doble cubierta agrega resistencia serie cubierta–cavidad–cubierta usando Hollands + radiación entre superficies grises paralelas.
- `espesor_placa_m`: ⚠️ Configurable pero no entra al balance térmico. El modelo asume capacitancia despreciable de la placa.
- **Chimenea**: ya no está en P3. Se migró a `Proyecto.chimenea` (top-level, definida en `core/chimenea.py`) y su UI vive en P6.

---

## Diagrama 4 — P4 Cámara

```mermaid
graph LR
  subgraph UI4["ui/p4_camara.py"]
    W_PROD[producto/X0/Xobj/masa]
    W_ISO["selectbox modelo_isoterma"]
    W_TPROD["checkbox T_prod inicial ⚑"]
    W_GEO[largo/ancho/alto cámara]
    W_TECHO["checkbox techo translúcido ⚑"]
    W_CUB[selectbox cubierta_translucida_id]
    W_ARAD[number_input A_rad]
    W_PARED[radio simple/compuesta + capas]
    W_BAND[n_bandejas/dim/porosidad/...]
    W_FLUJO[caudal/dirección/recirculación]
    W_HR["checkbox HR entrada ⚑"]
    W_HORIZ["selectbox horizonte de simulación"]
  end

  subgraph DATA4["core/camara.py"]
    CARGA[CargaProducto]
    GEOM[GeometriaCamara]
    CONST[ConstruccionCamara]
    PARED[ParedCamara → capas]
    BAND[ConfiguracionBandejas]
    FLUJO[ConfiguracionFlujo]
    FZA["ForzantesAire (modo TD)"]
  end

  subgraph CONS4["calculos/"]
    CCAM[camara_calc.py wire-up TD]
    CTD[camara_termodinamica.py]
    MOTPC[motor_calc.estimar_delta_P_camara]
    POAH["clima_calc.calcular_POA_horizonte"]
    ARM["balance_global.armar_forzantes_aire"]
  end

  W_PROD --> CARGA
  W_ISO --> CARGA
  W_TPROD --> CARGA
  W_GEO --> GEOM
  W_TECHO --> CONST
  W_CUB --> CONST
  W_ARAD --> CONST
  W_PARED --> PARED
  W_BAND --> BAND
  W_FLUJO --> FLUJO
  W_HR --> FLUJO

  CARGA --> CCAM
  CARGA --> CTD
  CONST --> CCAM
  PARED -.U/R/espesor.-> CCAM
  GEOM --> CCAM
  GEOM --> MOTPC
  BAND --> CCAM
  BAND --> MOTPC
  FLUJO --> CCAM
  FLUJO --> MOTPC

  %% Modo transitorio: P4 arma forzantes desde clima + POA
  W_HORIZ -.->|si modo TD + clima real| POAH
  POAH -->|I_g_POA_W_m2| ARM
  ARM --> FZA
  FZA --> CTD

  classDef new fill:#d4edda,stroke:#155724
  class POAH,ARM,FZA new
```

**Hallazgos P4 (estado al cierre de S32)**:

- Todas las conexiones de cámara (dataclasses → solvers) cableadas correctamente. La pared compuesta se consume vía métodos agregados (`U_conduccion_W_m2K`, `R_conduccion_m2K_W`, `espesor_total_m`) en `camara_calc.py:735`.
- **Modo transitorio**: P4 arma `ForzantesAire` desde el clima horario real. Ahora la forzante incluye **dos series de irradiancia separadas**:
  - `I_g_W_m2`: GHI sobre el techo de la cámara (input al motor termodinámico de cámara para Q_rad por techo translúcido).
  - `I_g_POA_W_m2`: POA sobre el plano del colector (input a `_correr_colector_horizonte` cuando el lazo natural por chimenea está activo). Calculada con `calculos.clima_calc.calcular_POA_horizonte` (transposición Liu-Jordan con pvlib, mismo modelo que P3).
- Si DNI/DHI no están disponibles (clima incompleto, modo sintético), POA queda en `None` y el balance global cae a GHI con aviso explícito `ADV_PICARD_POA_NO_DISPONIBLE`.
- **"Día real" habilitado en CAJA (S32b)**: nuevo helper `_construir_forzantes_reales_caja` arma `ForzantesAire` desde clima NASA + `cfg.dia_analisis` directamente, con `T_salida_colector_K = T_amb_K` (la cámara *es* el colector). `_disponibilidad_forzantes_reales` ahora hace branch por tipología (CAJA exige sólo clima; ARMARIO/GRAN_ESCALA siguen exigiendo P3). El radio "Forzantes del aire de entrada" muestra label dinámico ("Día real (clima ambiente)" en CAJA / "Día real (clima + colector)" en el resto).
- **Presión atmosférica corregida por altitud (S32c)**: el botón "Calcular" computa `P_proyecto_Pa` vía `presion_representativa_proyecto` y lo propaga a `_construir_forzantes_termodinamico` (ω desde HR y T_amb) y a `calcular_camara` (motor termodinámico). Caption visible con el origen del valor.

---

## Diagrama 5 — P5 Auxiliar + P6 Motor / Chimenea (toggles raíz)

```mermaid
graph LR
  subgraph UI56["ui/"]
    T5["toggle Incorporar auxiliar"]
    W5[tipo/modo/P_nom/T_max/setpoint/nocturno]
    T6["toggle Incorporar motor"]
    W6[accionamiento/caudal/ΔP/η/tensión]
    BTNM["botón Calcular motor"]
    T6C["toggle Incorporar chimenea (solo si motor OFF)"]
    W6C[diámetro/altura/material chimenea]
    T6E["toggle Agregar extractor eólico (solo si chimenea ON)"]
    W6E[Cp / Kt / D_ext / z0_terreno]
    BTNC["botón Calcular chimenea (S32d)"]
    SS_CHIM["st.session_state['p6_chimenea_eval']"]
  end

  subgraph CORE56["core/"]
    AUX_DC[Auxiliar dataclass]
    MOT_DC[Motor dataclass]
    CHIM_DC[Chimenea dataclass]
  end

  subgraph CALC56["calculos/"]
    AUXC[auxiliar_calc.py]
    AUXT[calcular_auxiliar_transitorio]
    MOTC[motor_calc.py]
    CHIMC["chimenea_calc.py — delta_P_tiro, caudal_natural_kgs"]
    NATH["_caudal_natural_horizonte (por hora)"]
    NATL["_caudal_natural_loop (preliminar + balance const)"]
    CORH["_correr_colector_horizonte (re-corre colector con v efectiva)"]
    BG_C["balance_global.calcular_todo — Picard cerrado por colector"]
    BG_T["balance_global.calcular_todo_transitorio — Picard sobre horizonte + motor TD"]
    PRP["presion_representativa_proyecto (S32c) → P_Pa híbrido"]
  end

  T5 -->|OFF| NULL_A[auxiliar = None]
  T5 -->|ON| W5
  W5 --> AUX_DC
  AUX_DC --> AUXC
  AUX_DC -->|disponible_nocturno ⚑| AUXT

  T6 -->|OFF| NULL_M[motor = None]
  T6 -->|ON| W6
  W6 --> MOT_DC
  BTNM --> MOT_DC
  MOT_DC --> MOTC

  NULL_M --> T6C
  T6C -->|ON| W6C
  W6C --> CHIM_DC
  T6C -->|ON| T6E
  T6E -->|ON| W6E
  W6E --> CHIM_DC
  CHIM_DC --> CHIMC

  %% Botón Calcular chimenea (preliminar S32d): T_chim heurística + condiciones
  %% representativas del clima, llama al lazo natural local y persiste el dict.
  BTNC -->|heurística T_chim| NATL
  PRP --> NATL
  NATL --> SS_CHIM
  SS_CHIM -.lee.-> P7C["P7 checklist · Chimenea ✅"]

  %% Modo constantes
  PRP --> BG_C
  CHIMC --> BG_C
  BG_C -->|muta v_diseño| CORH_C[_correr_colector estacionario re-llamado]
  BG_C -->|caudal natural| AUXC

  %% Modo transitorio
  PRP --> BG_T
  CHIMC --> NATH
  NATH --> BG_T
  BG_T --> CORH
  CORH -->|"T_sal_col(t)"| BG_T
  BG_T -->|"m_dot(t) en forzantes"| TD["motor TD (camara_termodinamica)"]
  TD -->|"T_flujo(t) = T_chim"| BG_T

  classDef pic fill:#d4edda,stroke:#155724
  classDef s32 fill:#cfe2ff,stroke:#084298
  class BG_C,BG_T,NATH,CORH pic
  class BTNC,SS_CHIM,PRP,NATL s32
```

**Hallazgos P5/P6 (estado al cierre de S32)**:

- Toggle `disponible_nocturno` del auxiliar solo afecta al modo transitorio (`calcular_auxiliar_transitorio`); en modo cuasi-estacionario es ignorado — comportamiento esperado.
- Chimenea en P6 (sólo si motor OFF): estructuralmente coexisten en el dataclass, son mutuamente excluyentes desde la UI.
- **Lazo natural cerrado en ambos modos** (desde S30 extendida):
  - *Constantes*: Picard `T_chim ↔ ṁ_nat ↔ T_sal_col` en `calcular_todo`. Re-corre el colector estacionario mutando `velocidad_diseno_ms`. 10 iter máx, tol 0.5 K. Try/finally restaura.
  - *Transitorio*: Picard sobre todo el horizonte en `calcular_todo_transitorio`. Por iteración: `_caudal_natural_horizonte` calcula ṁ(t) hora a hora; `_correr_colector_horizonte` re-corre el colector cada hora con v efectiva; motor TD consume las nuevas forzantes; `T_flujo(t)` realimenta T_chim(t). 5 iter máx, tol 0.5 K.
- **POA correcta en el solver del colector**: en ambos pipelines la radiación que entra al solver del colector es POA (no GHI). Ver §101 de la bitácora y diagrama 4 abajo.
- **Botón "Calcular chimenea" en P6 (S32d)**: resuelve `_caudal_natural_loop` con T_chim heurística (Tamb+25 K CAJA / +30 K ARMARIO) + condiciones representativas del clima. Persiste en `st.session_state["p6_chimenea_eval"]` para que P7 marque el checklist como ✅. **Los números son preliminares**: P7 vuelve a resolver con Picard completo.
- **Presión atmosférica corregida por altitud (S32c)**: `presion_representativa_proyecto` (helper público en `balance_global.py`) propagada a `_resolver_aux_cam_const`, `_correr_colector(_horizonte)`, `_caudal_natural_loop`/`_horizonte`. También consumida directamente desde `ui/p4_camara.py` (botón Calcular) y `ui/p6_motor.py` (estimar_delta_P_*, delta_P_tiro_Pa, delta_P_turbina_motriz_Pa).

---

## Diagrama 6 — P7 Corridas paramétricas (barridos, S35)

Patrón **inverso** al resto del mapa: los widgets de barrido **no escriben en `Proyecto`**. Seleccionan, desde un catálogo curado, **un campo existente del `Proyecto`** (o una forzante) para barrerlo en N puntos sin mutar el proyecto persistente. El estado es **efímero** (`session_state`, no se serializa al JSON).

```mermaid
graph LR
  subgraph UI7["ui/p7_resultados.py — _render_barridos_parametricos"]
    W_PARAM["selectbox parámetro a barrer"]
    W_RANGO["min / max / N puntos (unidades UI)"]
    W_KPI["multiselect KPIs avanzados (opt-in)"]
    BTN["botón Correr barrido (≤3 comparables)"]
    SS_B["session_state['p7_barridos_{modo}']"]
    SS_T["session_state['p7_t_calc_base_s_{constantes,transitorio}']"]
  end

  subgraph CATB["calculos/ (catálogos + motor de barrido)"]
    CPAR["catalogo_parametros_barrido.ParametroBarrido<br/>(path, si_a_ui/ui_a_si, filtros tipología+modo)"]
    CKPI["catalogo_kpis_barrido.KpiBarrido<br/>(6 fijos + 14 avanzados, extractores tolerantes)"]
    CORR["barrido_parametrico.correr_barrido<br/>(aplicar_parametro → dataclasses.replace → __post_init__)"]
    ANG["conversiones_angulo.* (acimut/pendiente UI↔SI)"]
  end

  subgraph BG7["calculos/balance_global.py"]
    RC["resumen_camara (fuente de verdad única S35)"]
    CT["calcular_todo / calcular_todo_transitorio / operacion_anual"]
  end

  W_PARAM --> CPAR
  W_RANGO --> CORR
  W_KPI --> CKPI
  BTN --> CORR
  CPAR -->|path → campo Proyecto| CORR
  ANG --> CORR
  CORR -->|dispatch por modo| CT
  CT --> RC
  RC --> CKPI
  CKPI --> SS_B
  SS_B -.lee.-> RES7["_render_resultados_barridos (curvas superpuestas)"]
  CT -.estima tiempo.-> SS_T

  classDef new fill:#d4edda,stroke:#155724
  class CPAR,CKPI,CORR,ANG,RC new
```

**Hallazgos P7 barridos (S35)**:

- **Sin huérfanos nuevos**: cada `path` del catálogo (`camara.flujo.caudal_masico_kg_s`, `colector.unidad.largo_m`, `colector.banco.n_serie/n_paralelo`, `emplazamiento.{pendiente,acimut}_colector_deg`, `camara.carga_producto.*`, `camara.geometria.*`) apunta a un campo **ya cableado** del `Proyecto`. El barrido los lee y los reescribe vía `dataclasses.replace` (regatilla `__post_init__` → revalida). Las forzantes (`forzante:HR_camara`, `forzante:T_amb`, solo modo Constantes) devuelven override sin tocar el proyecto.
- **Filtrado por tipología y modo**: `parametros_para_tipologia` oculta parámetros no aplicables. `pendiente`/`acimut` solo en `{transitorio, anual}` (en Constantes la POA es input directo, no se recalcula). El sweep de ángulos se construye en unidades de UI (`linspace` UI → `ui_a_si` por punto) para sortear la no-monotonía del acimut — usa `conversiones_angulo` (S35).
- **`resumen_camara` (S35; motor único desde S38)**: fuente de verdad única para extraer `t_secado_s`/`masa_agua_kg`/`status`/`convergio` del resultado de cámara (`ResultadoMotorTermodinamico`). La consumen el barrido (`catalogo_kpis_barrido`), `balance_global._extraer_t_y_masa` (wrapper) y `p7_resultados._resumen_camara` (agrega conversión a horas en la frontera UI).
- **Tolerancia a fallos**: un punto que lanza `ValueError`/`RuntimeError` (ej. `n_paralelo=0`) deja un **hueco** en la curva, no aborta el barrido. KPIs no aplicables al modo se extraen como `None` (`getattr` con default).
- **Estado efímero**: los barridos viven en `session_state['p7_barridos_{modo}']` y **no se persisten** en el JSON/TXT/PDF del proyecto. La estimación de tiempo usa una base stasheada en `p7_t_calc_base_s_{constantes,transitorio}` tras cada cálculo normal.

---

## Diagrama 7 — Modo industrial / gran escala (pipeline VENTANA, S40)

Patrón **propio** del modo industrial: cuando `tipologia == GRAN_ESCALA` y `modo_analisis == VENTANA`, P7 enruta a `balance_global.calcular_todo_ventana` (no a `calcular_todo`/`calcular_todo_transitorio`). La cadena térmica completa se arma hora a hora sobre el lapso `[ventana_inicio, ventana_fin]` y la producción es **emergente** (no se fuerza `X_objetivo`).

```mermaid
graph TD
  subgraph UIIND["ui/ (widgets gran escala)"]
    P1S["P1 · subtipo (Batch/Semicontinuo) + ventana inicio/fin"]
    P3S["P3 · caño maestro (manifold)"]
    P4S["P4 · topología túnel (n_zonas + cadencia)"]
    P5S["P5 · calendario de arranque (híbrido)"]
    P7BTN["P7 · botón Calcular ventana de producción"]
  end

  subgraph COREIND["core/"]
    CFGv["configuracion.{subtipo_gran_escala, ventana_inicio/fin, ModoAnalisis.VENTANA}"]
    CANO["colector.banco.cano_maestro (CanoMaestro)"]
    TUNEL["camara.tunel (ConfiguracionTunel)"]
    ARRQ["auxiliar.cargas_arranque (list[CargaArranque])"]
  end

  subgraph BGV["balance_global.calcular_todo_ventana"]
    PRPv["presion_representativa_proyecto → P_Pa"]
    AFV["armar_forzantes_ventana"]
    POAv["clima_calc.calcular_POA_horizonte → POA(t)"]
    COLv["_correr_colector_horizonte_forzado → T_sal_col(t)"]
    DTCANO["cano_maestro_calc.delta_T_cano_maestro → ΔT(t) al aire"]
    AUXv["auxiliar_calc.calcular_auxiliar_transitorio (máscara calendario) → Q_aux(t)"]
    FZAV["ForzantesAire (ventana): T_ent(t), ω_ent(t), ṁ(t), POA(t), GHI(t)"]
  end

  subgraph SIMV["simulacion_ventana.simular_ventana — despacho por subtipo"]
    BATCH["BATCH → calcular_camara (encadena lotes; descarga al alcanzar X_obj)"]
    SEMI["SEMICONTINUO → calcular_camara_cascada → camara_termodinamica.simular_cascada (túnel N zonas a contracorriente, avance por cadencia)"]
    RESV["ResultadoVentana: kg seco, tasa kg/día, leña, perfil X/T/ω por zona"]
  end

  P1S --> CFGv
  P3S --> CANO
  P4S --> TUNEL
  P5S --> ARRQ

  CFGv --> AFV
  P7BTN --> PRPv
  PRPv --> AFV
  AFV --> POAv
  POAv -->|"POA(t)"| COLv
  CANO --> DTCANO
  COLv --> DTCANO
  ARRQ --> AUXv
  DTCANO --> FZAV
  AUXv --> FZAV
  COLv --> FZAV

  FZAV --> BATCH
  FZAV --> SEMI
  CFGv -.subtipo.-> BATCH
  CFGv -.subtipo.-> SEMI
  TUNEL --> SEMI
  BATCH --> RESV
  SEMI --> RESV

  RESV -->|session_state p7_resultado_ventana| P7R["P7 · _render_resultados_ventana (dashboard producción + perfil túnel)"]

  classDef ind fill:#d4edda,stroke:#155724
  classDef s40 fill:#cfe2ff,stroke:#084298
  class AFV,POAv,COLv,DTCANO,AUXv,FZAV ind
  class BATCH,SEMI,RESV s40
```

**Hallazgos modo industrial (S40, validado S42/S44)**:

- **Despacho único batch↔cascada**: `simular_ventana` decide por `configuracion.subtipo_gran_escala`. Batch = cascada de N=1 zona (encadena lotes con `calcular_camara`, descarga al alcanzar `X_objetivo`); semicontinuo = `simular_cascada` (N zonas en serie, aire a contracorriente, columnas avanzan por `intervalo_avance_h`). Reusan intacto el núcleo físico (evaporación difusiva + GAB + coeficientes variables en t de S39).
- **Cadena térmica hora a hora**: `armar_forzantes_ventana` encadena POA(t) → colector forzado `_correr_colector_horizonte_forzado` → ΔT del caño maestro (`delta_T_cano_maestro`, resta/suma al aire) → aporte auxiliar con calendario (`calcular_auxiliar_transitorio` + `_mascara_calendario`). Validada contra ADITAL (`validacion/validacion_adital.py`, 4/4 → 7/7 en S45).
- **Caño maestro — gotcha de compensación (fix S42)**: la distribución usa **flujo acumulado** de las ramas del banco, no caudal uniforme. El default `CanoMaestro.absortancia_solar=0.90` es de chapa pintada; galvanizado desnudo ≈ 0.35.
- **Ventana ≠ solo gran escala (S44)**: `ModoAnalisis.VENTANA` también aplica a CAJA/ARMARIO, pero ahí P7 cae al transitorio normal (`calcular_todo_transitorio`) con forzantes del lapso (`p4_camara._construir_forzantes_ventana`). El pipeline de producción de este diagrama (`_render_ventana` con banco/caño/túnel) queda **gateado a `GRAN_ESCALA`**.

---

## Tabla maestra — widget → campo → consumidor

| Pestaña | Widget UI | Campo `Proyecto.*` | Leído por |
| ------- | --------- | ------------------- | --------- |
| P1 | tipología (radio) | `configuracion.tipologia` | `balance_global` |
| P1 | modo_analisis | `configuracion.modo_analisis` | `balance_global` |
| P1 | dia_analisis (7 valores: `SOLSTICIO_VERANO/INVIERNO`, `EQUINOCCIO_MARZO/SEPTIEMBRE` ← S32a, `MAS_CALUROSO`, `MAS_FRIO`, `ESPECIFICO`) | `configuracion.dia_analisis` | `ui/p2_emplazamiento._fecha_dia_analisis`, `ui/p3_colector._seleccionar_dia`, `ui/p4_camara._construir_forzantes_reales_caja` (S32b) |
| P2 | latitud/longitud | `emplazamiento.lat/lon_deg` | `clima_calc.obtener_clima` |
| P2 | altitud (display NASA + override usuario) | `emplazamiento.altitud_m` | `calculos.balance_global.presion_representativa_proyecto` (S32c → ISA cuando no hay clima) |
| P2 | acimut/pendiente | `emplazamiento.acimut/pendiente` | `solar_geometria` (vía emplazamiento) |
| **P3** (cross-tab) | albedo del suelo (selectbox superficies + personalizado) | `emplazamiento.albedo_suelo` | `clima_calc.calcular_POA_horizonte` (componente reflejada `GHI·ρ·(1−cosβ)/2` → POA → solver colector y todos los consumidores de POA). **Widget en P3, campo en Emplazamiento.** Reemplaza el `0.25` hardcodeado de pvlib. Catálogo en `calculos/catalogo_albedos.py`. |
| P2 | zona_horaria | `emplazamiento.zona_horaria` | `solar_geometria` |
| P2 (S51) | radio fuente de clima (`p2_fuente_clima`, nasa_power/medido) | rama de `render()` | flujo NASA histórico o `_render_clima_medido` |
| P2 (S51) | uploader + mapeo de columnas clima medido (`p2_med_*`) | `ConfigMapeoClima` → `clima_medido.ingerir_clima_medido` → `proyecto.clima` (fuente medido/hibrido, procedencia, datos_nativos) | todos los consumidores de `Clima.datos` (contrato intacto); `calcular_POA_horizonte` usa `POA_med_Wm2` si existe |
| P2 (S51) | snapshot sección "clima_medido" (mapeo + hashes) | cache `data/cache/clima_medido/` | restauración sin re-subir archivo |
| P4 (S51) | gating ANUAL por cobertura | `clima_medido.meses_cubiertos` < 12 → warning y sin botón | `simulacion_anual.simular_anual` (el motor simula el lapso que reciba; exigir los 12 meses es responsabilidad de la UI) |
| P3 | N° cubiertas ⚑ | `colector.unidad.n_cubiertas` + `espaciado_entre_cubiertas_m` | `colector_calc`, `tipos234_calc` (vía `_U_cubierta_efectiva`) |
| **P3** | **Espesor placa** ⚑ | `colector.unidad.espesor_placa_m` | **⚠️ ninguno** |
| P3 | id_cubierta/espesor_cubierta | `colector.unidad.*` | `colector_calc`, `tipos234_calc` |
| P3 | espesor cubierta (policarbonato → k según espesor) | `colector.unidad.k_cubierta_efectivo_W_mK` | `colector_calc`, `tipos234_calc` (override de `k_cub`; default None = catálogo). Mapa `k_efectivo_por_espesor_mm` en `cubiertas.yaml`. Selector `ui/componentes/espesores.py`. |
| P3 | id_placa | `colector.unidad.id_placa` | `colector_calc`, `tipos234_calc`, `motor_calc` (rugosidad) |
| P3 | id_aislante/espesor_aislante | `colector.unidad.*` | `colector_calc`, `tipos234_calc` |
| P3 | id_fondo | `colector.unidad.id_fondo` | `tipos234_calc` (no Tipo 1) |
| P3 | geometría + banco | `colector.unidad/banco.*` | `colector_calc`, `tipos234_calc`, `motor_calc` |
| P4 | producto/X/masa/modelos | `camara.carga_producto.*` | `camara_calc`, `camara_termodinamica` |
| P4 | T_prod inicial | `camara.carga_producto.T_prod_inicial_K` | `camara_termodinamica` |
| P4 | geometría cámara (incl. orientación/techo un agua, S47) | `camara.geometria.*` | `camara_calc`, `motor_calc`, `calculos.radiacion_camara` |
| P4 | vidriado (material/espesor/caras translúcidas, S47) + A_rad | `camara.construccion.*` | `camara_calc`, `camara_termodinamica`, `calculos.radiacion_camara` |
| P4 | pared compuesta (capas) | `camara.construccion.pared.capas` | `camara_calc` (vía métodos U/R) |
| P4 | bandejas (todo) | `camara.bandejas.*` | `camara_calc`, `motor_calc` |
| P1 (S58) | "📂 Cargar proyecto completo" (uploader .json) | **todo** el `Proyecto` (meta, configuración, emplazamiento, colector, cámara, auxiliar, motor, chimenea) | `ui/componentes/carga_proyecto.py::cargar_proyecto_completo` — reparte cada sub-dict a los `_from_json_*` de P3/P4/P5/P6. Camino de vuelta del export `prediseno_completo` de P7. **El clima NO viaja** (metadato solamente): hay que rebajarlo en P2. |
| P4 | caudal/dirección/recirc/HR | `camara.flujo.*` | `camara_calc`, `motor_calc` |
| P4 (S58) | "Tomar el caudal del colector" (checkbox, default on) | `camara.flujo.caudal_masico_kg_s` ← `balance_global.caudal_masico_banco_kg_s(colector, T_amb, P_sitio)` | Sistema hermético: el caudal de cámara **sigue** al del banco. Misma función que evalúa `ADV_VENTANA_CAUDAL_BANCO_INCOHERENTE` → el valor propuesto nunca la dispara. Desacoplable (mezcla con aire ambiente); no se pisa un caudal propio del proyecto. |
| P4 | ~~modo_calculo (radio)~~ **eliminado en S38** | `camara.modo_calculo` (vestigial; coacción `capa_fina`→`termodinamico`) | `camara_calc.calcular_camara` (motor único: termodinámico) |
| ~~P4~~ | ~~batches_por_mes (slider, solo ANUAL)~~ | **eliminado en S57** | La cantidad de lotes pasó a ser un **resultado** de `simulacion_anual.simular_anual` (encadenado event-driven sobre 8760 h), no una entrada del usuario. `OperacionAnualConfig` y su campo `Camara.operacion_anual` fueron eliminados. |
| P4 (S57) | política de recarga: activa / hora de carga / maniobra (solo ANUAL) | (efímero: widgets `p4_anual_recarga_*`, **no** se persiste en el snapshot) | `simulacion_ventana.PoliticaRecarga` → `simular_anual(politica_recarga=…)` |
| P4 (S58) | pronóstico: no cargar en días malos / umbral MJ/m²·día (solo ANUAL) | (efímero: widgets `p4_anual_pronostico_*`, **no** se persiste) | `PoliticaRecarga.exigir_pronostico` / `.umbral_pronostico_MJ_m2` → `_simular_ventana_batch` (gating de carga por `_energia_diaria_POA`) |
| P4 → P7 | `ResultadosAnual` (session_state) | `st.session_state["p4_resultado_anual"]` + `_hash` + `p4_politica_recarga` | `p7_resultados._render_operacion_anual_detalle` (tabla + 4 figuras) y `reporte.py`. **P7 NO recalcula: reproduce el objeto de P4.** Desde S58 la vigencia se verifica con `simulacion_anual.hash_entradas_anual` vía `ui/componentes/vigencia.py`; si no coincide, P7 muestra el panel en rojo con botón de recálculo y los exports omiten el bloque. |
| P5 | tipo/modo/P_nom/setpoint/T_max/η_quem/PCI | `auxiliar.*` | `auxiliar_calc` |
| P5 | disponible_nocturno ⚑ | `auxiliar.disponible_nocturno` | `calcular_auxiliar_transitorio` |
| P5 | tipo_biomasa/PCI/η | `auxiliar.*` | `auxiliar.consumo_biomasa_efectivo_kg_h()` |
| P6 | accionamiento/caudal/ΔP/η/factor | `motor.*` | `motor_calc`, `Motor.__post_init__` |
| P6 | chimenea (D, H, material) | `proyecto.chimenea.*` (top-level) | `chimenea_calc.{delta_P_tiro_Pa, caudal_natural_kgs}`, `balance_global._caudal_natural_loop` (constantes) y `_caudal_natural_horizonte` + `_correr_colector_horizonte` (transitorio, dentro de Picard) |
| P6 | extractor eólico en chimenea (`extractor_activo`, `diametro_extractor_m`, `Cp_turbina`, `Kt_turbina`) | `proyecto.chimenea.{extractor_activo, ...}` | `chimenea_calc.{delta_P_turbina_motriz_Pa, _v_viento_a_altura, caudal_natural_kgs}` (motriz + Kt + perfil log de viento). Propagado a `_caudal_natural_loop`/`_caudal_natural_horizonte` con `v_viento_ref_ms` desde forzantes. **La referencia del viento es 2 m** (contrato `Clima.WS_ms`), no 10 m — corregido en S57. |
| **P2** (cross-tab, S57) | rugosidad del terreno z₀ (selectbox Davenport-Wieringa + personalizado) | `emplazamiento.z0_terreno_m` | **Dos consumidores**: (a) `clima_medido._viento_a_2m` vía `ConfigMapeoClima.z0_terreno_m` — normaliza el anemómetro a 2 m y entra en `hash_ingesta` para invalidar la caché; (b) `chimenea_calc._v_viento_a_altura` vía `balance_global._z0_terreno(proyecto)` — lleva el viento al tope. **Widget en P2, campo en Emplazamiento**, igual que el albedo. Catálogo en `calculos/catalogo_rugosidades.py`. `Chimenea.z0_terreno_m` quedó **vestigial** (back-compat de snapshots; P6 lo espeja y lo muestra en solo lectura). |
| P6 → P7 (S32d) | botón "Calcular chimenea" — resultado preliminar del lazo natural | `st.session_state["p6_chimenea_eval"]` (dict de `_caudal_natural_loop` con T_chim heurística) | `ui/p7_resultados._render_estado` (lee para marcar `P6 · Chimenea ✅` en checklist). El balance global de P7 **no lee este dict** — vuelve a resolver con Picard completo. |
| (interno, S32c) | presión atmosférica corregida por altitud | — (calculada de `clima.datos["presion_Pa"]` o `emplazamiento.altitud_m`) | `presion_representativa_proyecto` → `_resolver_aux_cam_const`, `_correr_colector(_horizonte)`, `_caudal_natural_loop`/`_horizonte`, `ui/p4_camara` (botón Calcular), `ui/p6_motor` (estimar_delta_P_*, delta_P_tiro_Pa, delta_P_turbina_motriz_Pa) |
| P4→core | I_g_POA(t) sobre plano colector | `forzantes_base.I_g_POA_W_m2` (transitorio) | `balance_global._correr_colector_horizonte` → `_correr_colector` → `colector_calc`/`tipos234_calc` |
| P4→core (S47) | I_eq_prod(t) sobre caras translúcidas de la cámara | `forzantes_base.I_g_W_m2` (transitorio; antes GHI cruda) | `calculos.radiacion_camara.series_radiacion_camara` → `camara_termodinamica.simular_secado` (Q_rad al producto) |
| P4→core (S47) | Q_rad_aire(t): radiación no interceptada por el producto | `forzantes_base.Q_rad_aire_W` | `calculos.radiacion_camara.series_radiacion_camara` → `camara_termodinamica.resolver_estado_camara` (suma al balance de `T_flujo`) |
| (interno) | POA representativa anual (sugerido P7) | — | `ui/p7_resultados._sugerir_condiciones` → `calcular_POA_horizonte` (quantile 90) |
| P7 (S35) | barrido: parámetro / rango / N / KPIs avanzados | **ningún campo `Proyecto`** (estado efímero `session_state['p7_barridos_{modo}']`) | `barrido_parametrico.correr_barrido` lee el `path` del `ParametroBarrido` seleccionado sobre una **copia** del proyecto (`dataclasses.replace`, sin mutar el persistente). KPIs vía `catalogo_kpis_barrido` + `balance_global.resumen_camara` |
| (interno, S35) | base de tiempo de cálculo para estimar barrido | — (`session_state['p7_t_calc_base_s_{constantes,transitorio}']`) | `ui/p7_resultados` stash tras cada `calcular_todo(_transitorio)` normal |
| **P1** (S40) | subtipo de gran escala (radio Batch/Semicontinuo, solo `GRAN_ESCALA`) | `configuracion.subtipo_gran_escala` (`SubtipoGranEscala`) | `simulacion_ventana.simular_ventana` (despacho batch↔cascada), `camara_calc.calcular_camara_cascada`, `ui/p4_camara` (gate de la sección túnel) |
| **P1** (S40) | ventana de análisis (date_input inicio/fin + presets 1 sem/1 mes/campaña) | `configuracion.{ventana_inicio, ventana_fin}` + `ModoAnalisis.VENTANA` | `ui/p7_resultados._slice_clima_ventana` → `balance_global.calcular_todo_ventana` → `armar_forzantes_ventana` |
| **P1** (S53) | paso de trabajo (radio 1 h / 15 min / 10 min / 5 min, solo si `modo ≠ ANUAL`; mejora 38 fase 1b) | `configuracion.paso_trabajo_s` (`{3600,900,600,300}`; coacción a 3600 en ANUAL) | `clima_calc.resolver_datos_trabajo` (→ `clima_medido.remuestrear_a_paso`) vía `ui/p4_camara._datos_local_paso` y `ui/p7_resultados._slice_clima_ventana`; el `dt` se propaga por `forzantes.t_s` y el `max_step` del motor (`camara_termodinamica._max_step_desde_forzantes`) |
| **P3** (S40) | caño maestro (checkbox + largo/sección/aislado/aporte solar, solo `GRAN_ESCALA`) | `colector.banco.cano_maestro` (`CanoMaestro`) | `cano_maestro_calc.{estimar_delta_P_cano_maestro, delta_T_cano_maestro}` vía `balance_global.armar_forzantes_ventana` (ΔT al aire) y `ui/p6_motor` (ΔP a ductos) |
| **P3** (S54) | validación con datos medidos (uploader de la T de salida medida + mapeo; mejora 38 fase 2/2b) | `ConfigReferencia`/`SenalReferencia` (session_state `p3_val_*`, no toca `Proyecto`) | `calculos/ingesta_referencia.{ingerir_referencia, ingerir_clima_forzante, alinear_con_simulada, evaluar_ajuste}` + `calculos/metricas_validacion.calcular_metricas`; corre el colector sobre el período vía `ui/p3_colector._series_simuladas_colector` → `_evaluar_ventana` (fase 2b: forzado con clima medido del propio archivo + `fecha_fija`) |
| **P3** (S54) | calibración del modelo (barrer parámetro min/max/N + objetivo; mejora 38 fase 3) | session_state `p3_cal_*`; el óptimo se aplica al `Proyecto` vía `aplicar_parametro` | `calculos/calibracion.calibrar_1d` (motor puro, callback de evaluación) + `calculos/barrido_parametrico.aplicar_parametro` + `calculos/metricas_validacion` (función objetivo RMSE/|MBE|/MAE) |
| **P4** (S40) | topología del túnel (n_zonas + cadencia de avance, solo `SEMICONTINUO`) | `camara.tunel` (`ConfiguracionTunel`) | `camara_calc.calcular_camara_cascada` → `camara_termodinamica.simular_cascada` |
| **P5** (S40) | calendario de arranque (checkbox + N cargas hora_inicio/duración) | `auxiliar.cargas_arranque` (`list[CargaArranque]`) | `auxiliar_calc.calcular_auxiliar_transitorio` (vía `_mascara_calendario`) → consumido por `balance_global` transitorio **y** ventana |
| **P6** (S40) | ΔP del caño maestro (derivado, no widget) | — (lee `colector.banco.cano_maestro`) | `ui/p6_motor` suma `estimar_delta_P_cano_maestro(Q_total)` a `motor.delta_P_ductos_Pa` (explícito → entra al total del `Motor`) |
| **P7** (S40) | botón "Calcular ventana de producción" (solo `VENTANA`) | `st.session_state["p7_resultado_ventana"]` (`ResultadoVentana`) | `ui/p7_resultados._render_resultados_ventana` (dashboard producción + perfil túnel) |
| **P4** (S44) | espesor del techo translúcido (`selector_espesor_mm`, solo si hay cubierta translúcida) | `camara.construccion.cubierta_translucida_espesor_m` | `camara_calc._construir_params_termodinamico` (computa `U_techo=k_efectivo/espesor`, descuenta la cara del techo de `A_cuerpo`) → `camara_termodinamica.resolver_estado_camara` (suma `UA_techo` al balance de `T_flujo`) |
| **P4** (S44) | modo Ventana en CAJA/ARMARIO (sin widget propio; deriva de `ModoAnalisis.VENTANA` + tipología ≠ GRAN_ESCALA) | `st.session_state["p4_horizonte_*"]` (vía `_construir_forzantes_ventana`) | `ui/p7_resultados` rama transitoria → `balance_global.calcular_todo_transitorio` (el `_render_ventana` gran-escala queda gateado a `GRAN_ESCALA`) |
| **P3** (S44) | botón "Evaluar colector" en modo Ventana (sin campo nuevo) | `st.session_state["p3_eval"]` (`{"modo": "ventana", ...}` enriquecido: `T_abs_C`, `x_noon`, `marcas_*`) | `ui/p3_colector._evaluar_ventana` (día y noche) → `_fig_T_salida_ventana` + `_fig_T_fluido_dia` |
| **P4** (S39) | sliders T_op / HR_op del aire de entrada | (condición de borde) | `camara_calc._calcular_termodinamico` → `simular_secado`. **Atenuados:** con `coef_transporte_func` variable en t solo pesan en modo **Constantes**; en Sintético/Día real/Anual el borde sale del clima/colector (ver Resumen ejecutivo #2). |
| **P7** (S43) | carta psicrométrica del proceso (sin widget de entrada; se dibuja de los resultados) | — (lee `res`/`res_tr`/ventana + `omega_amb`) | `ui/p7_resultados._render_carta_psicrometrica` y `ui/reporte.py` → `ui/componentes/carta_psicrometrica.fig_carta_psicrometrica` (sobre `calculos/psicrometria.py`; adiabático/no-adiabático **emerge** del balance; representativo = mediodía solar; en túnel semicontinuo traza el path del aire por zonas a contracorriente) |
| **P4** (S47) | pendiente/acimut/cara de caída del techo (un agua) | `camara.geometria.{pendiente_techo_deg, acimut_camara_deg, cara_caida_techo}` | `GeometriaCamara.caras()` (áreas/tilt/acimut por cara) → `calculos.radiacion_camara`, `camara_calc._construir_params_termodinamico` (A_cuerpo, A_techo) |
| **P4** (S47) | superficies translúcidas (5 toggles: techo/frente/atrás/laterales) | `camara.construccion.caras_translucidas` (`CarasTranslucidas`) | `ConstruccionCamara.caras_translucidas_activas()` → `calculos.radiacion_camara.series_radiacion_camara`, `camara_calc._construir_params_termodinamico` (A_techo = suma de caras activas) |
| **P2** (S47) | expander "Orientación del colector" oculto en CAJA (info → P4) | — (gate por `configuracion.tipologia`) | `ui/p2_emplazamiento.render` (sin campo nuevo; la orientación de la caja vive en `camara.geometria`) |

> **S40 (modo industrial / gran escala):** todos los widgets de arriba están cableados extremo a extremo (UI → core → cálculo) y verificados con AppTest. La cadena térmica completa (colector → caño maestro → cámara) está validada contra datos de campo de ADITAL en `validacion/validacion_adital.py`.
>
> **S44 (techo translúcido + ventana CAJA/ARMARIO):** el espesor del techo translúcido entra al balance como conducción del vidriado; el modo Ventana se generaliza a CAJA/ARMARIO como multidía real (el pipeline de producción `_render_ventana` queda solo para gran escala).
>
> **S47 (cámara radiativa orientada):** la cámara tiene orientación y techo a un agua propios (independientes del banco de colectores); hasta 5 caras pueden ser translúcidas (mismo material/espesor). La radiación de cada cara se reparte entre el producto (factor de intercepción `f_i`) y el aire (`Q_rad_aire`, vía superficies internas — efecto invernadero de la caja). Cambio numérico deliberado: proyectos CAJA/techo-translúcido existentes ganan más energía que antes (la fracción del techo que no interceptaba la bandeja superior ya no se descarta). Ver `docs/notas/plan_camara_radiativa_orientada.md` y `calculos/radiacion_camara.py`.

---

## Recomendaciones

Pendientes:

1. **`espesor_placa_m`**: documentar explícitamente que el modelo asume capacitancia térmica de la placa despreciable, o incorporar el término al EDO si la masa de la placa es relevante.
2. **A_rad configurable desde P4** (hoy default a `area_bandeja_m2` superior). Heredado de S29.
3. **α_solar por producto** en `frutas.yaml`/`hortalizas.yaml` (default 0.6). Heredado de S29.

✓ **Resueltos en S30 (2026-05-19):**

- **`n_cubiertas`** conectada a los 4 motores numéricos vía `_U_cubierta_efectiva`, junto con `espaciado_entre_cubiertas_m`.
- **Bugs preexistentes de signos** en F1 (los 4 tipos) y F3 (Tipo 1) del residual algebraico — raíz espuria con `T_cub_e ≈ −200 °C`. Validado contra HWB con R²=1.0000 (en S30, con propiedades del aire constantes; desde S36 el modelo usa propiedades variables y el R² es ≈0.999, ver nota de h local más abajo).
- **F4 Tipos 2/3/4**: incoherencia entre EDO del fluido ci y balance del fondo corregida agregando `conv_ci_int` explícito.
- **Chimenea solar**: cerrado el ciclo huérfano → modelo (`chimenea_calc.py`), migración a `Proyecto` top-level, UI propia en P6, integración del caudal natural en `balance_global` (single-pass).

✓ **Resueltos en S30 extendida (2026-05-19/20)** — completan el cierre físico del lazo natural:

- **Visualizar `res.chimenea` en P7 modo constantes**: panel, tabla, snapshots `.txt`/`.json` y warning explícito si la desviación |ṁ_nat − ṁ_design|/ṁ_design > 30 %.
- **Iterar T_chim ↔ ṁ_nat ↔ T_salida_colector** (Picard cerrado por el colector) en `calcular_todo` (modo constantes). 10 iter máx, tol 0.5 K. Mutación temporal de `velocidad_diseno_ms` con `try/finally`.
- **Acople con motor termodinámico de cámara** en pipeline transitoria (`calcular_todo_transitorio`): Picard sobre el horizonte completo (5 iter máx). `ResultadosCompletosTransitorio.chimenea` con series horarias. UI: Panel 5 de chimenea con ṁ(t), T_chim(t), ΔP_tiro(t).
- **Re-correr el colector hora a hora** dentro del Picard transitorio: nuevo `_correr_colector_horizonte` itera el solver estacionario con v efectiva impuesta por el ṁ_nat de cada hora. Coherencia energética en `energia_solar_util_MJ` con las series re-calculadas.
- **POA precomputada en `ForzantesAire`**: nuevo campo `I_g_POA_W_m2` opcional + helper compartido `calculos.clima_calc.calcular_POA_horizonte` (transposición Liu-Jordan con pvlib). P4 puebla la POA desde clima real. P3 deduplicado (su `_poa_serie` ahora es wrapper del helper). Sugerido de I_g en P7 modo constantes ahora sale de quantile 90 de POA. Fix del bug físico: los 4 solvers de colector reciben POA en todos los caminos (P3 horario/diario, P3/P7 constantes, P7 transitorio con clima). Fallback a GHI con aviso `ADV_PICARD_POA_NO_DISPONIBLE` sólo en forzantes sintéticas o clima sin DNI/DHI.

Ver `docs/bitacora/bitacora_sesion30.md` (§84-§101) y `validacion/{validacion_hwb,comparar_f4}.py`. Suite al cierre: **774 + 2 xfailed** (era 717 + 2 al cierre de S29; +57 tests netos en la sesión extendida).

✓ **Resueltos en S31 (2026-05-20/21)** — cierra dos tópicos de la hoja de ruta a 1.0:

- **K_rugosidad por bandeja con producto** (S31a, cierra "ΔP en bandejas"): nuevo campo `ConfiguracionBandejas.K_rugosidad_producto` (default auto desde tabla `d_p/espacio_libre`). En HORIZONTAL suma `K_rug · ρ·v_canal²/2 · n_bandejas`; en VERTICAL suma `K_TRANSICION_LECHO=1.5 · ρ·v₀²/2 · n_bandejas` (Ergun ya cubría la rugosidad del producto vía Φ_s, d_p). Tabla anclada en Idelchik / Crane TP-410.
- **Extractor eólico migrado a accesorio de chimenea** (S31b): eliminado `TipoAccionamiento.EXTRACTOR_EOLICO`; agregados `extractor_activo`/`Cp_turbina`/`Kt_turbina`/`z0_terreno_m`/`diametro_extractor_m` en `Chimenea`. Balance del lazo natural ampliado con término motriz `Cp·ρ·v_viento²/2` (corregido a la altura del tope por perfil log) + resistivo `Kt·ρ·v_extractor²/2`. Migración automática de `.json` viejos con `st.warning`.
- **Operación anual de cámara cascada A+B** (S31c, cierra "modo ANUAL de cámara"): módulo `calculos/operacion_anual_camara.py` con orquestador que corre motor TD sobre el día típico de cada mes (de `clima_calc.dia_tipo_mensual`). Las 4 eficiencias de Augustus Leon (RSER 2002) en `calculos/eficiencias_camara.py`. UI: en P4 sección "📅 Operación anual" **arriba** cuando `modo_analisis==ANUAL`, con batch puntual de día sintético como test secundario debajo. En P7 panel mensual al principio cuando hay resultado anual calculado. **SUPERSEDIDO EN S57**: reemplazado por `calculos/simulacion_anual.py` (8760 h reales, encadenado de lotes); el módulo y `OperacionAnualConfig` fueron eliminados. Ver `docs/notas/plan_anual_8760.md`.

Ver `docs/bitacora/bitacora_sesion31.md` (§121-§125). Suite al cierre de S31: **833 + 2 xfailed** (+59 tests netos desde S30).

✓ **Resueltos en S32 (2026-05-22)** — mejoras del modo CAJA + propagación física global:

- **Equinoccios separados** (S32a): el enum `DiaAnalisis` ahora tiene dos valores distintos `EQUINOCCIO_MARZO` (21/3) y `EQUINOCCIO_SEPTIEMBRE` (21/9), con labels que explicitan la estación en hem. sur. Antes el valor único `EQUINOCCIO` mapeaba siempre al 21 de marzo aunque el label decía "21 mar / 21 sep" — bug latente corregido. Rama nueva agregada en `_fecha_dia_analisis` (P2), `_seleccionar_dia` (P3) y `_construir_forzantes_reales_caja` (P4).
- **"Día real" habilitado en tipología CAJA** (S32b): nuevo helper `_construir_forzantes_reales_caja` en `ui/p4_camara.py` arma `ForzantesAire` desde clima NASA + `cfg.dia_analisis` sin requerir P3, con `T_salida_colector_K = T_amb_K` (la cámara *es* el colector). `_disponibilidad_forzantes_reales` ahora hace branch por tipología.
- **Presión atmosférica corregida por altitud** (S32c, propagada a cámara + colector + chimenea + motor): nuevo helper `presion_representativa_proyecto(proyecto) -> (P_Pa, origen)` en `calculos/balance_global.py` con política híbrida (media anual NASA POWER → ISA con `altitud_m` → 101 325 Pa). Propagado a `_resolver_aux_cam_const`, `_correr_colector(_horizonte)`, `_caudal_natural_loop`/`_horizonte`, `ui/p4_camara.py` (botón Calcular) y `ui/p6_motor.py` (estimar_delta_P_*, delta_P_tiro_Pa, delta_P_turbina_motriz_Pa). Para Salta (~1187 m) P ≈ 88 kPa (no 101 kPa); ω_sat ~15 % más alta a igual T/HR. Pendiente: `core/motor.py:177` (ρ_descarga hardcoded a 101325).
- **Botón "Calcular chimenea" en P6** (S32d): nuevo helper `_render_calcular_chimenea` con dos auxiliares (`_condiciones_representativas_chimenea` y heurística T_chim = Tamb + 25 K CAJA / +30 K ARMARIO). Resuelve `_caudal_natural_loop` y persiste resultado en `st.session_state["p6_chimenea_eval"]`. P7 checklist actualizado: marca `P6 · Chimenea ✅` cuando hay chimenea + eval. Los números son **preliminares**; P7 vuelve a resolver con Picard completo (divergencia aceptada por el usuario).

Ver `docs/bitacora/bitacora_sesion32.md` (§126-§130). Suite al cierre de S32: **833 + 2 xfailed** (sin cambio — todo wire-up + helpers UI sin tests nuevos; deuda explícita en la bitácora).

✓ **S33 (2026-05-26)** — deploy a Hugging Face Spaces vía GitHub Action (`deploy_hf.yml`). Infraestructura: **sin cambios de cableado** widget→campo→consumidor. Ver `docs/bitacora/bitacora_sesion33.md`.

✓ **S34 (2026-05-29)** — default de `Camara.modo_calculo` invertido de `capa_fina` a `termodinamico` (`core/camara.py`, fallbacks de UI/deserialización en `ui/p4_camara.py`). El motor termodinámico es el camino físicamente completo y el único soportado por la operación anual. Ver `docs/bitacora/bitacora_sesion34.md`. Suite al cierre: **833 + 2 xfailed** (sin cambio neto; 2 fixtures y 1 test adaptados al nuevo default).

✓ **S35 (2026-06-01)** — corridas paramétricas en P7 + refactor de ángulos + integración Obsidian:

- **Conversiones de ángulo a `calculos/`**: nuevo `calculos/conversiones_angulo.py` (matemática pura, fuente de verdad única). `ui/componentes/unidades.py` las re-exporta; `clima_calc` consume del módulo nuevo. **Cambió una invariante documentada** del mapa (ver regla arquitectónica en Diagrama 1).
- **`resumen_camara` (fuente de verdad única)**: en `balance_global.py`, accede a la firma de resultado de cámara (`ResultadoMotorTermodinamico`; motor único desde S38). La consumen el barrido, `_extraer_t_y_masa` (wrapper) y `p7_resultados._resumen_camara`.
- **Barridos paramétricos (feature completa, etapas 1-11)**: nuevos `calculos/{catalogo_parametros_barrido,barrido_parametrico,catalogo_kpis_barrido}.py` + UI en `p7_resultados.py` (3 call-sites: Constantes/Transitorio/Anual). Estado **efímero** en `session_state`, no toca el `Proyecto`. Ver Diagrama 6 arriba. **Pendiente: etapa 12** (verificación manual e2e en Streamlit, no auto-testeable).
- **Integración Obsidian**: notas de módulos autogeneradas (`scripts/generar_notas_obsidian.py` → `docs/modulos/`), docs de navegación (`docs/{arquitectura,tareas,decisiones}.md`) y bloques `[[...]]` en README/CLAUDE/CHANGELOG. Solo documentación.

Ver `docs/bitacora/bitacora_sesion35.md` (§149-§154). Suite al cierre de S35: **885 + 2 xfailed** (+52 tests: barrido_parametrico 18, catalogo_kpis 15, catalogo_parametros 11, p7_barridos 6). Sin commitear (working tree puro).

✓ **S36 (2026-06-03)** — modelo físico del colector (albedo→POA + h_int local):

- **Albedo del suelo seleccionable** (S36a): `emplazamiento.albedo_suelo` (widget en P3, cross-tab) → `clima_calc.calcular_POA_horizonte` (componente reflejada solar). Ver la fila en la tabla maestra y el catálogo `calculos/catalogo_albedos.py`. Bug colateral corregido: `ui/p2_emplazamiento.py` reconstruía `Emplazamiento` campo por campo y reseteaba el albedo en cada rerun → migrado a `dataclasses.replace` (preserva campos no tocados; elimina la clase de bug para campos futuros).
- **Coeficiente convectivo interno LOCAL** (S36b): `h_int` ya no es un escalar único; se evalúa nodo a nodo en los 4 motores con propiedades del aire vs T (`calculos/propiedades_aire.py`), Nu de entrada local, blending de régimen y convección mixta (`calculos/correlaciones_nusselt.py`), vía el helper `colector_calc.coef_conveccion_interna_local`. Cambio interno (sin widgets nuevos). El caudal másico se fija con `ρ(T_entrada)`.
- **Modo multi-día "días reales consecutivos"** (S36c): widget en P4 (`st.radio` "Repetir día típico"/"Días reales consecutivos", solo con forzantes "Día real" + Multi-día; flag en `session_state["cam_multidia_consecutivo"]`, no en el core). Consume el clima vía `clima_calc.slice_n_dias_consecutivos` (recorta N días reales desde el día de diseño, trunca en el borde de año). En ARMARIO corre el colector sobre el slice (`p3_colector._evaluar_diario`); arma forzantes sin replicar (`p4_camara._forzantes_desde_slice` → `armar_forzantes_aire` con `n_reps=1`). Meta del horizonte con `horizonte_tipo`/`n_dias_efectivo` → etiqueta en P7.

Ver `docs/bitacora/bitacora_sesion36.md` (§155-§158). Suite al cierre de S36: **914 + 2 xfailed** (+29: albedo 9, h local 17, multi-día 3). Validación HWB con piso R²≥0.99 + monotonía + parámetros. Sin commitear (working tree puro).

✓ **S37 (2026-06-04)** — tanda UX/UI (mejoras 20–24). **Sin cambios de cableado** widget→campo→consumidor (son layout/presentación/export):

- **Mejora 20**: navegación movida de `st.tabs` a un `st.radio` en el sidebar (`Secasol.py`, key `nav_seccion`) con dispatch que renderiza solo la sección activa. Fix en `ui/componentes/header.py` (ocultar solo `stToolbarActions`+`stDecoration`, no todo el `stToolbar`, para conservar el botón de reapertura del sidebar).
- **Mejora 21**: subsecciones de P1–P6 con `expanded=False` al inicio.
- **Mejora 22**: selectores de material de P4 muestran `descripcion` del catálogo + espesores en mm (solo presentación; valores guardados siguen siendo las keys del catálogo).
- **Mejoras 23–24**: helper `ui/componentes/graficas.mostrar_plotly` (chokepoint de los 22 gráficos) agrega descarga PNG (vista del navegador) y CSV de datos (`_fig_a_dataframe`, server-side).

Ver `docs/bitacora/bitacora_sesion37.md` (§159-§164). Suite al cierre de S37: **919 + 2 xfailed** (+5: extractor de datos de gráficos + regresión del fix). Versión local 0.10.0. Sin commitear (working tree puro).

✓ **S38 (2026-06) — motor de cámara único (termodinámico):** se **eliminó** el motor de capa fina (MR(t) empíricos). `Camara.modo_calculo` quedó **vestigial** (`__post_init__` coacciona `"capa_fina"`→`"termodinamico"`); `modelo_capa_fina` es vestigial puro; `modelo_isoterma` es semi-vestigial (lo lee la validación de `core/camara.py`, el TD hardcodea `"gab"`). **Ojo:** los bloques `capa_fina:` de los catálogos **no son inertes** — `_modelos_disponibles()` los lee para filtrar qué productos aparecen en el selector de P4. La fila del radio `modo_calculo` en la tabla maestra ya refleja esto. Ver `bitacora_sesion38.md` §170.

✓ **S39 (2026-06) — coeficientes de transporte variables en t:** `h_conv`/`K_m` dejan de congelarse; `simular_secado` acepta `coef_transporte_func(T_ent, T_prod, ω_ent, ṁ) → (h_conv, K_m)` (closure en `camara_calc._calcular_termodinamico`, película en `(T_ent+T_prod)/2`), evaluado por paso. **Hallazgo de cableado:** los sliders **T_op/HR_op** de P4 quedan **atenuados** (solo borde efectivo en modo Constantes) — ver Resumen ejecutivo #2 y la fila P4(S39) de la tabla. Ver `bitacora_sesion39.md`.

✓ **S40 (2026-06) — modo industrial / gran escala (cerrado y validado):** tipología `GRAN_ESCALA` funcional con subtipos BATCH/SEMICONTINUO, `ModoAnalisis.VENTANA`, motor de cámara multi-etapa (`simular_cascada`), caño maestro (`CanoMaestro`), híbrido con calendario de arranque. **Todos los widgets cableados extremo a extremo y verificados con AppTest** — ver las 7 filas marcadas **(S40)** en la tabla maestra. Cadena térmica validada contra ADITAL (`validacion/validacion_adital.py`). Ver `bitacora_sesion40.md`.

✓ **S41 (2026-06) — espesores + persistencia + hidrodinámica ASHRAE:** selectores de espesor en mm (`ui/componentes/espesores.selector_espesor_mm`) reusados en P3/P4; persistencia de ventana/año; red hidráulica del caño maestro y ΔP con métodos ASHRAE/Idelchik (mejora 29). Sin huérfanos nuevos. Ver `bitacora_sesion41.md`.

✓ **S42 (2026-06) — colectores industrial:** reorden de la UI colector→banco en P3; **fix de la compensación del caño maestro** (flujo acumulado de las ramas del banco). Cableado sin cambios estructurales. Ver `bitacora_sesion42.md`.

✓ **S43 (2026-06) — carta psicrométrica del proceso:** nuevo `ui/componentes/carta_psicrometrica.py` sobre `calculos/psicrometria.py` (sin librería externa). Se dibuja de los **resultados** (no escribe en `Proyecto`) en P7 y en el reporte PDF, completa incl. modo Ventana; adiabático/no-adiabático **emerge** del balance; representativo = mediodía solar; túnel semicontinuo = path del aire por zonas a contracorriente. Ver la fila P7(S43) de la tabla maestra. Ver `bitacora_sesion43.md`.

✓ **S44 (2026-06) — techo translúcido al balance + ventana CAJA/ARMARIO:** el espesor del techo translúcido (`cubierta_translucida_espesor_m`) entra como conducción del vidriado (`U_techo` al balance de `T_flujo`, se descuenta la cara del techo de `A_cuerpo`); el modo Ventana se generaliza a CAJA/ARMARIO como **multidía real** (`_render_ventana` de producción queda solo para gran escala). Ver las filas **(S44)** de la tabla maestra. Ver `bitacora_sesion44.md`.

✓ **S45 (2026-06-23) — auditoría integral pre-seminario INENCO:** quick-wins de UX (onboarding + ayudas para usuario nuevo), fix de docstring de Tipos234 y nota Klein. **Sin cambios de cableado** widget→campo→consumidor. Validación HWB 4/4 + ADITAL 7/7. Suite **1042 tests**. v0.14.0 en producción (HF Spaces). Ver `bitacora_sesion45.md`.

✓ **S47 (2026-07-06) — cámara radiativa orientada:** la cámara gana orientación propia (`geometria.acimut_camara_deg`) y techo a un agua (`pendiente_techo_deg` + `cara_caida_techo`), independiente del banco de colectores; hasta 5 caras pueden ser translúcidas (`construccion.caras_translucidas`, mismo material/espesor). Nuevo módulo `calculos/radiacion_camara.py` (POA por cara + reparto producto/aire con factores de intercepción `f_i`); nuevo término `Q_rad_aire` en `resolver_estado_camara`/`simular_secado`/`simular_cascada` y en `ForzantesAire`. Los 6 builders de forzantes (CAJA/ARMARIO día-único y multidía, ventana gran escala, anual) pasaron de GHI cruda a irradiancia equivalente por orientación. P2 oculta "Orientación del colector" en CAJA. Ver las filas **(S47)** de la tabla maestra. **Cambio numérico deliberado** en CAJA/techo-translúcido existentes (ver CHANGELOG). Ver `docs/notas/plan_camara_radiativa_orientada.md`.

---

## Cómo regenerar este mapa

Este documento se construyó con tres pasadas de exploración paralela:

- Inventario de dataclasses en `core/`
- Asignaciones `proyecto.* = ...` en `ui/p*.py`
- Lecturas `proyecto.*` / `colector.*` en `calculos/*.py`

Luego se cruzaron por nombre de campo y se verificaron los huérfanos sospechosos con `grep`. Pedile a Claude que regenere si hubo cambios estructurales (renombres, nuevos dataclasses, nuevos motores).
