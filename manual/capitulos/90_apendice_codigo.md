# Apéndice · Implementación en código

Secasol es software libre (GPLv3). Este apéndice mapea cada modelo físico del
manual a su módulo en el código fuente, para quien quiera leerlo, auditarlo o
extenderlo. La arquitectura es de **capas estrictas**: `ui/` (interfaz
Streamlit) → `core/` (modelo de datos) → `calculos/` (motores numéricos). **La
física no sabe de la interfaz**, por eso se testea y valida sin ella (~1000+
tests automatizados).

Convenciones del código: SI estricto en el núcleo (la conversión de unidades
vive en un solo lugar), catálogos YAML de materiales y productos, un test por
validación dura.

## Recurso solar y clima {#emplazamiento}

Capítulo: [Técnico · Recurso solar y clima](?manual=tec-emplazamiento)

| Qué | Dónde |
|---|---|
| Descarga + caché + huecos + SI | `calculos/clima_calc.py::obtener_clima` |
| Política de huecos (≤3 h interpola, >3 h NaN) | `clima_calc._aplicar_politica_huecos` |
| Clave de caché SHA-256 (lat, lon, año) | `clima_calc._hash_cache` |
| Transposición GHI/DNI/DHI → POA | `clima_calc.calcular_POA_horizonte` |
| Posición solar (SPA) | `pvlib.solarposition.get_solarposition` |
| Transposición Liu-Jordan / isotrópico | `pvlib.irradiance.get_total_irradiance` |
| Mediodía solar verdadero (tránsito) | `calculos/solar_geometria.py::mediodia_solar_transit` |
| Conversiones de acimut | `calculos/conversiones_angulo.py` |
| Día típico mensual / recortes de ventana | `clima_calc.dia_tipo_mensual`, `slice_clima_ventana`, `slice_n_dias_consecutivos` |
| Modelo de datos del clima | `core/clima.py` (`Clima`, `CalidadClima`) |

## Colector {#colector}

Capítulo: [Técnico · Colector de placa plana](?manual=tec-colector)

| Qué | Dónde |
|---|---|
| Solver Tipo 1 (orquestación) | `calculos/colector_calc.py::calcular_colector_tipo1` |
| Solvers Tipos 2/3/4 | `calculos/colector_tipos234_calc.py` |
| Sistema algebraico por nodo | `colector_calc.py::_sistema_nodo` |
| RHS de la EDO + warm-start | `colector_calc.py::_construir_rhs` (`solve_ivp` RK45 + `fsolve`) |
| $h_{int}$ local nodo a nodo | `colector_calc.py::coef_conveccion_interna_local` |
| Catálogo de correlaciones de Nusselt | `calculos/correlaciones_nusselt.py::calcular_h_int`, `nusselt_mixto_local` |
| Propiedades del aire $k,\mu,Pr,c_p,\rho(T,P)$ | `calculos/propiedades_aire.py::propiedades_aire` |
| Conductancia de doble cubierta | `colector_calc.py::_U_cubierta_efectiva` (Hollands + radiación) |
| Convección de viento / cielo | `_h_viento_W_m2K` (McAdams), `_T_cielo_K` (Swinbank) |
| Pérdida de carga del canal | `calculos/motor_calc.py::_delta_P_canal_colector`, `estimar_delta_P_colector` |
| Modelo de datos modular | `core/colector.py` (`Colector`, `ColectorUnidad`, `BancoColectores`) |

## Cámara de secado {#camara}

Capítulo: [Técnico · Cámara de secado](?manual=tec-camara)

| Qué | Dónde |
|---|---|
| Punto de entrada de cámara | `calculos/camara_calc.py::calcular_camara` |
| Sistema algebraico CSTR (analítico) | `calculos/camara_termodinamica.py::resolver_estado_camara` |
| Integración de las 2 EDOs + evento | `camara_termodinamica.py::simular_secado` |
| Coeficientes variables en el tiempo | `camara_calc.py::_construir_params_termodinamico::_coef_transporte` |
| $h_{conv}$ placa plana / Chilton-Colburn | `camara_calc.py::_h_conv_camara_placa_plana` |
| Inversión GAB → $a_w(X)$ | `calculos/psicrometria.py::actividad_agua_desde_X_GAB` |
| $\omega_{sat}(T)$, entalpía, $c_p$ húmedo | `calculos/psicrometria.py` |
| Pared compuesta (R en serie) | `core/camara.py::ConstruccionCamara.pared` |
| Superficies translúcidas ($U_{techo}$ + $Q_{rad}$ + $Q_{rad,aire}$) | `camara_calc.py` + `resolver_estado_camara` |
| Radiación por caras (POA por cara, reparto producto/aire) | `calculos/radiacion_camara.py` |
| Orientación de la cámara y techo a un agua | `core/camara.py::GeometriaCamara.caras()` |
| ΔP de lecho (Ergun) y malla | `calculos/motor_calc.py::_delta_P_lecho_por_bandeja` |
| Dirección de flujo | `core/camara.py::DireccionFlujo`, `ConfiguracionFlujo` |

## Modo industrial {#industrial}

Capítulo: [Técnico · Modo industrial](?manual=tec-industrial)

| Qué | Dónde |
|---|---|
| Reparto de caudal del campo (ASHRAE cap. 21) | `calculos/campo_colectores_calc.py` |
| ΔP caño maestro (flujo acumulado) | `calculos/cano_maestro_calc.py::estimar_delta_P_cano_maestro` |
| ΔT caño maestro (2 variantes) | `cano_maestro_calc.py::delta_T_cano_maestro` |
| Uniformidad de distribución | `cano_maestro_calc.py::uniformidad_distribucion` |
| Sección variable del caño | `core.colector.CanoMaestro.seccion_en_fraccion` |
| Motor batch/semicontinuo | `calculos/camara_termodinamica.py::simular_cascada` |
| Topología del túnel | `core.camara.ConfiguracionTunel` |
| Despacho de ventana | `calculos/simulacion_ventana.py::simular_ventana` |
| Forzantes + entrada de Resultados | `calculos/balance_global.py::armar_forzantes_ventana`, `calcular_todo_ventana` |
| Validación ADITAL | `validacion/validacion_adital.py` |

## Motor, chimenea y pérdidas de carga {#motor}

Capítulo: [Técnico · Motor y chimenea](?manual=tec-chimenea)

| Qué | Dónde |
|---|---|
| Potencias del motor (forzada) | `core/motor.py::__post_init__` |
| ΔP colector / cámara / singulares | `calculos/motor_calc.py::estimar_delta_P_*` |
| Factor de fricción de Haaland | `motor_calc.py::_factor_friccion_haaland` |
| Tiro térmico | `calculos/chimenea_calc.py::delta_P_tiro_Pa` |
| ΔP del ducto + resistencia del extractor | `chimenea_calc.py::delta_P_chimenea_Pa` |
| Extractor motriz + corrección de viento | `chimenea_calc.py::delta_P_turbina_motriz_Pa`, `_v_viento_a_altura` |
| Caudal de equilibrio (brentq) | `chimenea_calc.py::caudal_natural_kgs` |
| Lazo Picard (Constantes) | `calculos/balance_global.py::calcular_todo` + `_caudal_natural_loop` |
| Lazo Picard (Transitorio) | `balance_global.py::_caudal_natural_horizonte`, `_correr_colector_horizonte` |

## Calentamiento auxiliar {#auxiliar}

Capítulo: [Técnico · Auxiliar](?manual=tec-auxiliar)

| Qué | Dónde |
|---|---|
| Balance escalar del auxiliar | `calculos/auxiliar_calc.py::calcular_auxiliar` |
| Solver transitorio (horizonte) | `auxiliar_calc.py::calcular_auxiliar_transitorio` |
| Máscara de calendario híbrido | `auxiliar_calc.py::_mascara_calendario` |
| Consumo/leña (PCI, η) | `core/auxiliar.py` (`CargaArranque`) |
| Modelo de datos | `core/auxiliar.py` (`Auxiliar`, `TipoAuxiliar`, `ModoOperacion`) |

## Balance global y resultados {#resultados}

Capítulo: [Técnico · Balance global](?manual=tec-resultados)

| Qué | Dónde |
|---|---|
| Orquestación (3 modos) | `calculos/balance_global.py::calcular_todo`, `calcular_todo_transitorio`, `calcular_todo_ventana` |
| Resultado integrado (COP, fracción solar) | `balance_global.py::ResultadosCompletos` |
| Coherencia cruzada del proyecto | `balance_global.py::verificar_coherencia_proyecto` |
| Forzantes del aire | `balance_global.py::armar_forzantes_aire` |
| Sugerencia de irradiancia (q90 POA) | `ui/p7_resultados.py::_sugerir_condiciones` |
| Carta psicrométrica | `calculos/carta_psicrometrica.py::estados_proceso` |
| Eficiencias de secado (Augustus Leon) | `calculos/eficiencias_camara.py` |
| Operación anual de cámara | `calculos/operacion_anual_camara.py` |
| Corridas paramétricas | `calculos/barrido_parametrico.py::correr_barrido` |
| Reporte PDF | `ui/reporte.py` (reportlab + kaleido) |

## Validación física {#validacion}

| Validación | Script | Resultado |
|---|---|---|
| Hottel-Whillier-Bliss (linealidad de η del colector) | `validacion/` (HWB) | R² ≥ 0.999 |
| ADITAL (caso real de campo) | `validacion/validacion_adital.py` | checks de orden de magnitud ✓ |
| Klein ($U_{top}$) | `validacion/` (Klein) | discrepancia **esperada**: Klein asume cavidad estanca; el Tipo 1 es un canal barrido por el aire |

---

**Ver también:** [Introducción](?manual=introduccion),
[Bibliografía](?manual=bibliografia).
