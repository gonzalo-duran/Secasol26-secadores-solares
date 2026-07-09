# Appendix · Code implementation

Secasol is free software (GPLv3). This appendix maps each physical model of the
manual to its module in the source code, for anyone who wants to read, audit or
extend it. The architecture is of **strict layers**: `ui/` (Streamlit interface) →
`core/` (data model) → `calculos/` (numerical engines). **The physics does not know
about the interface**, which is why it is tested and validated without it (~1000+
automated tests).

Code conventions: strict SI in the core (the unit conversion lives in a single
place), YAML catalogs of materials and products, one test per hard validation.

## Solar resource and climate {#emplazamiento}

Chapter: [Technical · Solar resource and climate](?manual=tec-emplazamiento)

| What | Where |
|---|---|
| Download + cache + gaps + SI | `calculos/clima_calc.py::obtener_clima` |
| Gap policy (≤3 h interpolate, >3 h NaN) | `clima_calc._aplicar_politica_huecos` |
| SHA-256 cache key (lat, lon, year) | `clima_calc._hash_cache` |
| GHI/DNI/DHI → POA transposition | `clima_calc.calcular_POA_horizonte` |
| Solar position (SPA) | `pvlib.solarposition.get_solarposition` |
| Liu-Jordan / isotropic transposition | `pvlib.irradiance.get_total_irradiance` |
| True solar noon (transit) | `calculos/solar_geometria.py::mediodia_solar_transit` |
| Azimuth conversions | `calculos/conversiones_angulo.py` |
| Monthly typical day / window slices | `clima_calc.dia_tipo_mensual`, `slice_clima_ventana`, `slice_n_dias_consecutivos` |
| Climate data model | `core/clima.py` (`Clima`, `CalidadClima`) |

## Collector {#colector}

Chapter: [Technical · Flat-plate collector](?manual=tec-colector)

| What | Where |
|---|---|
| Type 1 solver (orchestration) | `calculos/colector_calc.py::calcular_colector_tipo1` |
| Type 2/3/4 solvers | `calculos/colector_tipos234_calc.py` |
| Algebraic system per node | `colector_calc.py::_sistema_nodo` |
| ODE RHS + warm-start | `colector_calc.py::_construir_rhs` (`solve_ivp` RK45 + `fsolve`) |
| Local $h_{int}$ node by node | `colector_calc.py::coef_conveccion_interna_local` |
| Nusselt correlation catalog | `calculos/correlaciones_nusselt.py::calcular_h_int`, `nusselt_mixto_local` |
| Air properties $k,\mu,Pr,c_p,\rho(T,P)$ | `calculos/propiedades_aire.py::propiedades_aire` |
| Double-cover conductance | `colector_calc.py::_U_cubierta_efectiva` (Hollands + radiation) |
| Wind / sky convection | `_h_viento_W_m2K` (McAdams), `_T_cielo_K` (Swinbank) |
| Channel pressure drop | `calculos/motor_calc.py::_delta_P_canal_colector`, `estimar_delta_P_colector` |
| Modular data model | `core/colector.py` (`Colector`, `ColectorUnidad`, `BancoColectores`) |

## Drying chamber {#camara}

Chapter: [Technical · Drying chamber](?manual=tec-camara)

| What | Where |
|---|---|
| Chamber entry point | `calculos/camara_calc.py::calcular_camara` |
| CSTR algebraic system (analytical) | `calculos/camara_termodinamica.py::resolver_estado_camara` |
| Integration of the 2 ODEs + event | `camara_termodinamica.py::simular_secado` |
| Time-varying coefficients | `camara_calc.py::_construir_params_termodinamico::_coef_transporte` |
| Flat-plate $h_{conv}$ / Chilton-Colburn | `camara_calc.py::_h_conv_camara_placa_plana` |
| GAB inversion → $a_w(X)$ | `calculos/psicrometria.py::actividad_agua_desde_X_GAB` |
| $\omega_{sat}(T)$, enthalpy, moist $c_p$ | `calculos/psicrometria.py` |
| Composite wall (R in series) | `core/camara.py::ConstruccionCamara.pared` |
| Translucent surfaces ($U_{techo}$ + $Q_{rad}$ + $Q_{rad,aire}$) | `camara_calc.py` + `resolver_estado_camara` |
| Radiation per face (POA per face, product/air split) | `calculos/radiacion_camara.py` |
| Chamber orientation and mono-pitch roof | `core/camara.py::GeometriaCamara.caras()` |
| Bed ΔP (Ergun) and mesh | `calculos/motor_calc.py::_delta_P_lecho_por_bandeja` |
| Flow direction | `core/camara.py::DireccionFlujo`, `ConfiguracionFlujo` |

## Industrial mode {#industrial}

Chapter: [Technical · Industrial mode](?manual=tec-industrial)

| What | Where |
|---|---|
| Field flow split (ASHRAE ch. 21) | `calculos/campo_colectores_calc.py` |
| Main-duct ΔP (accumulated flow) | `calculos/cano_maestro_calc.py::estimar_delta_P_cano_maestro` |
| Main-duct ΔT (2 variants) | `cano_maestro_calc.py::delta_T_cano_maestro` |
| Distribution uniformity | `cano_maestro_calc.py::uniformidad_distribucion` |
| Variable duct section | `core.colector.CanoMaestro.seccion_en_fraccion` |
| Batch/semi-continuous engine | `calculos/camara_termodinamica.py::simular_cascada` |
| Tunnel topology | `core.camara.ConfiguracionTunel` |
| Window dispatch | `calculos/simulacion_ventana.py::simular_ventana` |
| Forcings + Results entry | `calculos/balance_global.py::armar_forzantes_ventana`, `calcular_todo_ventana` |
| ADITAL validation | `validacion/validacion_adital.py` |

## Motor, chimney and pressure drops {#motor}

Chapter: [Technical · Motor and chimney](?manual=tec-chimenea)

| What | Where |
|---|---|
| Motor powers (forced) | `core/motor.py::__post_init__` |
| Collector / chamber / fitting ΔP | `calculos/motor_calc.py::estimar_delta_P_*` |
| Haaland friction factor | `motor_calc.py::_factor_friccion_haaland` |
| Thermal draft | `calculos/chimenea_calc.py::delta_P_tiro_Pa` |
| Duct ΔP + extractor resistance | `chimenea_calc.py::delta_P_chimenea_Pa` |
| Driving extractor + wind correction | `chimenea_calc.py::delta_P_turbina_motriz_Pa`, `_v_viento_a_altura` |
| Equilibrium flow (brentq) | `chimenea_calc.py::caudal_natural_kgs` |
| Picard loop (Constants) | `calculos/balance_global.py::calcular_todo` + `_caudal_natural_loop` |
| Picard loop (Transient) | `balance_global.py::_caudal_natural_horizonte`, `_correr_colector_horizonte` |

## Auxiliary heating {#auxiliar}

Chapter: [Technical · Auxiliary](?manual=tec-auxiliar)

| What | Where |
|---|---|
| Scalar auxiliary balance | `calculos/auxiliar_calc.py::calcular_auxiliar` |
| Transient solver (horizon) | `auxiliar_calc.py::calcular_auxiliar_transitorio` |
| Hybrid schedule mask | `auxiliar_calc.py::_mascara_calendario` |
| Consumption/firewood (LCV, η) | `core/auxiliar.py` (`CargaArranque`) |
| Data model | `core/auxiliar.py` (`Auxiliar`, `TipoAuxiliar`, `ModoOperacion`) |

## Global balance and results {#resultados}

Chapter: [Technical · Global balance](?manual=tec-resultados)

| What | Where |
|---|---|
| Orchestration (3 modes) | `calculos/balance_global.py::calcular_todo`, `calcular_todo_transitorio`, `calcular_todo_ventana` |
| Integrated result (COP, solar fraction) | `balance_global.py::ResultadosCompletos` |
| Project cross consistency | `balance_global.py::verificar_coherencia_proyecto` |
| Air forcings | `balance_global.py::armar_forzantes_aire` |
| Irradiance suggestion (q90 POA) | `ui/p7_resultados.py::_sugerir_condiciones` |
| Psychrometric chart | `calculos/carta_psicrometrica.py::estados_proceso` |
| Drying efficiencies (Augustus Leon) | `calculos/eficiencias_camara.py` |
| Annual chamber operation | `calculos/operacion_anual_camara.py` |
| Parametric runs | `calculos/barrido_parametrico.py::correr_barrido` |
| PDF report | `ui/reporte.py` (reportlab + kaleido) |

## Physical validation {#validacion}

| Validation | Script | Result |
|---|---|---|
| Hottel-Whillier-Bliss (collector η linearity) | `validacion/` (HWB) | R² ≥ 0.999 |
| ADITAL (real field case) | `validacion/validacion_adital.py` | order-of-magnitude checks ✓ |
| Klein ($U_{top}$) | `validacion/` (Klein) | **expected** discrepancy: Klein assumes a sealed cavity; Type 1 is a channel swept by the air |

---

**See also:** [Introduction](?manual=introduccion),
[Bibliography](?manual=bibliografia).
