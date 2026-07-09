# Apêndice · Implementação em código

O Secasol é software livre (GPLv3). Este apêndice mapeia cada modelo físico do manual ao seu
módulo no código-fonte, para quem quiser lê-lo, auditá-lo ou estendê-lo. A arquitetura é de
**camadas estritas**: `ui/` (interface Streamlit) → `core/` (modelo de dados) → `calculos/`
(motores numéricos). **A física não sabe da interface**, por isso se testa e valida sem ela
(~1000+ testes automatizados).

Convenções do código: SI estrito no núcleo (a conversão de unidades vive num só lugar),
catálogos YAML de materiais e produtos, um teste por validação dura.

## Recurso solar e clima {#emplazamiento}

Capítulo: [Técnico · Recurso solar e clima](?manual=tec-emplazamiento)

| O quê | Onde |
|---|---|
| Download + cache + lacunas + SI | `calculos/clima_calc.py::obtener_clima` |
| Política de lacunas (≤3 h interpola, >3 h NaN) | `clima_calc._aplicar_politica_huecos` |
| Chave de cache SHA-256 (lat, lon, ano) | `clima_calc._hash_cache` |
| Transposição GHI/DNI/DHI → POA | `clima_calc.calcular_POA_horizonte` |
| Posição solar (SPA) | `pvlib.solarposition.get_solarposition` |
| Transposição Liu-Jordan / isotrópico | `pvlib.irradiance.get_total_irradiance` |
| Meio-dia solar verdadeiro (trânsito) | `calculos/solar_geometria.py::mediodia_solar_transit` |
| Conversões de azimute | `calculos/conversiones_angulo.py` |
| Dia típico mensal / recortes de janela | `clima_calc.dia_tipo_mensual`, `slice_clima_ventana`, `slice_n_dias_consecutivos` |
| Modelo de dados do clima | `core/clima.py` (`Clima`, `CalidadClima`) |

## Coletor {#colector}

Capítulo: [Técnico · Coletor de placa plana](?manual=tec-colector)

| O quê | Onde |
|---|---|
| Solver Tipo 1 (orquestração) | `calculos/colector_calc.py::calcular_colector_tipo1` |
| Solvers Tipos 2/3/4 | `calculos/colector_tipos234_calc.py` |
| Sistema algébrico por nó | `colector_calc.py::_sistema_nodo` |
| RHS da EDO + warm-start | `colector_calc.py::_construir_rhs` (`solve_ivp` RK45 + `fsolve`) |
| $h_{int}$ local nó a nó | `colector_calc.py::coef_conveccion_interna_local` |
| Catálogo de correlações de Nusselt | `calculos/correlaciones_nusselt.py::calcular_h_int`, `nusselt_mixto_local` |
| Propriedades do ar $k,\mu,Pr,c_p,\rho(T,P)$ | `calculos/propiedades_aire.py::propiedades_aire` |
| Condutância de dupla cobertura | `colector_calc.py::_U_cubierta_efectiva` (Hollands + radiação) |
| Convecção de vento / céu | `_h_viento_W_m2K` (McAdams), `_T_cielo_K` (Swinbank) |
| Perda de carga do canal | `calculos/motor_calc.py::_delta_P_canal_colector`, `estimar_delta_P_colector` |
| Modelo de dados modular | `core/colector.py` (`Colector`, `ColectorUnidad`, `BancoColectores`) |

## Câmara de secagem {#camara}

Capítulo: [Técnico · Câmara de secagem](?manual=tec-camara)

| O quê | Onde |
|---|---|
| Ponto de entrada de câmara | `calculos/camara_calc.py::calcular_camara` |
| Sistema algébrico CSTR (analítico) | `calculos/camara_termodinamica.py::resolver_estado_camara` |
| Integração das 2 EDOs + evento | `camara_termodinamica.py::simular_secado` |
| Coeficientes variáveis no tempo | `camara_calc.py::_construir_params_termodinamico::_coef_transporte` |
| $h_{conv}$ placa plana / Chilton-Colburn | `camara_calc.py::_h_conv_camara_placa_plana` |
| Inversão GAB → $a_w(X)$ | `calculos/psicrometria.py::actividad_agua_desde_X_GAB` |
| $\omega_{sat}(T)$, entalpia, $c_p$ úmido | `calculos/psicrometria.py` |
| Parede composta (R em série) | `core/camara.py::ConstruccionCamara.pared` |
| Superfícies translúcidas ($U_{techo}$ + $Q_{rad}$ + $Q_{rad,aire}$) | `camara_calc.py` + `resolver_estado_camara` |
| Radiação por faces (POA por face, repartição produto/ar) | `calculos/radiacion_camara.py` |
| Orientação da câmara e teto de uma água | `core/camara.py::GeometriaCamara.caras()` |
| ΔP de leito (Ergun) e malha | `calculos/motor_calc.py::_delta_P_lecho_por_bandeja` |
| Direção de fluxo | `core/camara.py::DireccionFlujo`, `ConfiguracionFlujo` |

## Modo industrial {#industrial}

Capítulo: [Técnico · Modo industrial](?manual=tec-industrial)

| O quê | Onde |
|---|---|
| Repartição de vazão do campo (ASHRAE cap. 21) | `calculos/campo_colectores_calc.py` |
| ΔP duto mestre (fluxo acumulado) | `calculos/cano_maestro_calc.py::estimar_delta_P_cano_maestro` |
| ΔT duto mestre (2 variantes) | `cano_maestro_calc.py::delta_T_cano_maestro` |
| Uniformidade de distribuição | `cano_maestro_calc.py::uniformidad_distribucion` |
| Seção variável do duto | `core.colector.CanoMaestro.seccion_en_fraccion` |
| Motor batch/semicontínuo | `calculos/camara_termodinamica.py::simular_cascada` |
| Topologia do túnel | `core.camara.ConfiguracionTunel` |
| Despacho de janela | `calculos/simulacion_ventana.py::simular_ventana` |
| Forçantes + entrada de Resultados | `calculos/balance_global.py::armar_forzantes_ventana`, `calcular_todo_ventana` |
| Validação ADITAL | `validacion/validacion_adital.py` |

## Motor, chaminé e perdas de carga {#motor}

Capítulo: [Técnico · Motor e chaminé](?manual=tec-chimenea)

| O quê | Onde |
|---|---|
| Potências do motor (forçada) | `core/motor.py::__post_init__` |
| ΔP coletor / câmara / singulares | `calculos/motor_calc.py::estimar_delta_P_*` |
| Fator de atrito de Haaland | `motor_calc.py::_factor_friccion_haaland` |
| Tiragem térmica | `calculos/chimenea_calc.py::delta_P_tiro_Pa` |
| ΔP do duto + resistência do exaustor | `chimenea_calc.py::delta_P_chimenea_Pa` |
| Exaustor motriz + correção de vento | `chimenea_calc.py::delta_P_turbina_motriz_Pa`, `_v_viento_a_altura` |
| Vazão de equilíbrio (brentq) | `chimenea_calc.py::caudal_natural_kgs` |
| Laço Picard (Constantes) | `calculos/balance_global.py::calcular_todo` + `_caudal_natural_loop` |
| Laço Picard (Transitório) | `balance_global.py::_caudal_natural_horizonte`, `_correr_colector_horizonte` |

## Aquecimento auxiliar {#auxiliar}

Capítulo: [Técnico · Auxiliar](?manual=tec-auxiliar)

| O quê | Onde |
|---|---|
| Balanço escalar do auxiliar | `calculos/auxiliar_calc.py::calcular_auxiliar` |
| Solver transitório (horizonte) | `auxiliar_calc.py::calcular_auxiliar_transitorio` |
| Máscara de calendário híbrido | `auxiliar_calc.py::_mascara_calendario` |
| Consumo/lenha (PCI, η) | `core/auxiliar.py` (`CargaArranque`) |
| Modelo de dados | `core/auxiliar.py` (`Auxiliar`, `TipoAuxiliar`, `ModoOperacion`) |

## Balanço global e resultados {#resultados}

Capítulo: [Técnico · Balanço global](?manual=tec-resultados)

| O quê | Onde |
|---|---|
| Orquestração (3 modos) | `calculos/balance_global.py::calcular_todo`, `calcular_todo_transitorio`, `calcular_todo_ventana` |
| Resultado integrado (COP, fração solar) | `balance_global.py::ResultadosCompletos` |
| Coerência cruzada do projeto | `balance_global.py::verificar_coherencia_proyecto` |
| Forçantes do ar | `balance_global.py::armar_forzantes_aire` |
| Sugestão de irradiância (q90 POA) | `ui/p7_resultados.py::_sugerir_condiciones` |
| Carta psicrométrica | `calculos/carta_psicrometrica.py::estados_proceso` |
| Eficiências de secagem (Augustus Leon) | `calculos/eficiencias_camara.py` |
| Operação anual de câmara | `calculos/operacion_anual_camara.py` |
| Simulações paramétricas | `calculos/barrido_parametrico.py::correr_barrido` |
| Relatório PDF | `ui/reporte.py` (reportlab + kaleido) |

## Validação física {#validacion}

| Validação | Script | Resultado |
|---|---|---|
| Hottel-Whillier-Bliss (linearidade de η do coletor) | `validacion/` (HWB) | R² ≥ 0,999 |
| ADITAL (caso real de campo) | `validacion/validacion_adital.py` | checks de ordem de grandeza ✓ |
| Klein ($U_{top}$) | `validacion/` (Klein) | discrepância **esperada**: Klein assume cavidade estanque; o Tipo 1 é um canal varrido pelo ar |

---

**Ver também:** [Introdução](?manual=introduccion), [Bibliografia](?manual=bibliografia).
