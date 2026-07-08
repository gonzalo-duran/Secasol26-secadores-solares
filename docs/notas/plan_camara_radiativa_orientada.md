# Plan — Cámara radiativa orientada

> Caja toda-translúcida, techo a un agua, orientación propia de la cámara, reparto de radiación producto/aire.
> Plan aprobado en sesión de planificación (2026-07-06). Estado: **implementado** (misma sesión, 2026-07-06).
> Ver `docs/bitacora/bitacora_sesion47.md` para el detalle de la implementación y verificación (1073 tests).

## Contexto

Hoy la única orientación del modelo es la del colector (`Emplazamiento.acimut_colector_deg`/`pendiente_colector_deg`); en tipología CAJA (sin colector) P2 igual muestra "Orientación del colector" y esos ángulos no alimentan nada físico. El techo translúcido es una sola superficie **horizontal** que recibe **GHI cruda** (`Q_rad = GHI·τ·α·A_rad`, directo al producto) más una pérdida `UA_techo`. Se quiere: (fase 1, CAJA) acimut propio de la cámara, techo a un agua con pendiente, toggle translúcida/opaca por cara — la cámara opera como colector; (fase 2, ARMARIO/GRAN_ESCALA) mismo mecanismo con orientación de cámara independiente del banco de colectores. Se implementan juntas.

**Decisiones del usuario:** techo a un agua (alto mayor atrás/menor adelante, laterales trapezoidales, pendiente + cara de caída); vidriado material+espesor únicos con toggle por cara (piso siempre opaco); orientación de cámara en **P4** (P2 oculta el expander del colector en CAJA); fases 1+2 juntas; **reparto de radiación producto/aire con factores de intercepción f_i por cara**.

## Física del modelo (validada con el usuario)

**Geometría solar — rigurosa hora a hora:** POA por cara vía pvlib (posición solar SPA: declinación estacional + ángulo horario, con lat/lon/altitud/tz reales) y transposición Liu-Jordan isotrópica (consistente con el colector). Por cara: directa = `cos θ_i` (AOI), difusa de cielo = `(1+cos β)/2` (pared vertical ve medio cielo), reflejada del suelo = `(1−cos β)/2·albedo·GHI`. Caja convexa → sin sombreado mutuo de la directa; sin obstrucciones externas (misma hipótesis que el colector).

**Reparto interno:** el motor es CSTR con un único nodo de producto (bandejas no discretizadas). La radiación transmitida por cada cara i se reparte:

- **Al producto**: fracción de intercepción `f_i`. Techo → `f = A_rad/A_techo_geom` (bandeja superior, como hoy). Caras verticales → silueta del lecho: `f = clip(n_bandejas·espesor_capa_m / alto_m, 0, 1)` (los cantos del lecho; asume bandejas que ocupan el ancho de la cámara — documentar). La `separacion_entre_bandejas_m` queda implícita: más separación = más hueco = menos intercepción.
- **Al aire**: el resto `(1−f_i)` lo absorben paredes internas/piso (`absortancia_interior`, campo nuevo, default 0.85) y entra como fuente `Q_rad_aire(t)` en el balance algebraico de `T_flujo`. Es el modo colector de la caja (efecto invernadero).

```
Q_rad_prod(t) = τ·α_prod·Σᵢ fᵢ·Aᵢ·POAᵢ(t) = τ·α_prod·A_rad·I_eq_prod(t),   I_eq_prod = Σ fᵢ·Aᵢ·POAᵢ / A_rad
Q_rad_aire(t) = τ·α_int·Σᵢ (1−fᵢ)·Aᵢ·POAᵢ(t)                                 [serie de potencia, W]
```

Back-compat de firma: techo-solo β=0 → `I_eq_prod = GHI` exacta (shortcut sin pvlib). **Cambio numérico deliberado**: el reparto se aplica también al techo — la radiación del techo que hoy "se pierde" (la fracción 1−f que no intercepta la bandeja superior) pasa a calentar el aire. Proyectos CAJA/techo-translúcido existentes darán **más ganancia** que antes; es corrección física, se documenta en CHANGELOG y bitácora. Los tests ancla existentes son relacionales/smoke (no fijan esos números), pero verificar.

**Fuera de alcance (anotar como mejoras futuras):** pérdidas IR nocturnas del vidriado (modelo conductivo puro); discretización vertical del producto por bandeja (gradientes/sombreado bandeja a bandeja — irrepresentable con nodo único).

**Otras decisiones:** `alto_m` = alto MEDIO (`alto_menor/mayor = alto ∓ (L_caida/2)·tanβ`; volumen y área transversal media exactos, `H_camara` chimenea sin cambios). `cara_caida_techo` es parámetro (caída transversal al flujo no se obtiene girando la cámara). `acimut_camara_deg` (Duffie, default 180) = normal exterior del frente; caras: frente γ, atrás γ+180, der γ+90, izq γ−90 (mirando en dirección del flujo); techo = acimut de la cara de caída; tilts 90° verticales, β techo. **Constantes**: sigue sin ganancia radiativa (I_g=0, como hoy). **Sintético**: `I_g_max` se interpreta por cara → factores escalares desde `radiacion_camara`.

## Etapas

### Etapa 1 — Modelo de datos en `core/camara.py`
- `GeometriaCamara`: `pendiente_techo_deg = 0.0`, `acimut_camara_deg = 180.0`, `cara_caida_techo: Literal["frente","atras","lateral_izq","lateral_der"] = "frente"`. Validaciones: `GEO_PENDIENTE_TECHO_INVALIDA` ([0,60]), `GEO_ACIMUT_CAMARA_INVALIDO` ([−180,180]), `GEO_CARA_CAIDA_INVALIDA`, `GEO_ALTO_MENOR_INSUFICIENTE` (≤0.05 m).
- Properties: `alto_menor_m`, `alto_mayor_m`, `A_techo_geom_m2` (=planta/cosβ), `caras() -> dict[str, CaraCamara]` (frozen: área, tilt, acimut Duffie; laterales trapezoidales `largo·alto_m`), `A_cuerpo_total_m2` (≡ `2(LA+lA+La)` con β=0 — test lo ancla). Wrap → `normalizar_acimut_duffie()` nueva en `calculos/conversiones_angulo.py`.
- `CarasTranslucidas` (frozen, 5 bools, default solo techo) en `ConstruccionCamara.caras_translucidas`; `cubierta_translucida_id` sigue de master switch. Campo nuevo `absortancia_interior: float = 0.85` (validación `CONS_ABSORTANCIA_INTERIOR_INVALIDA`, (0,1]).
- Coherencia: `PROY_CAJA_SIN_CUBIERTA_TRANSLUCIDA` (balance_global, ~130) extendida a "id None o 0 caras activas" (mismo código).
- `advertencias_camara(camara, latitud_deg=None)`: `CAM_PENDIENTE_TECHO_EXTREMA` (β>45), `CAM_VIDRIADO_SIN_CARAS`, `CAM_CARA_ORIENTACION_DESFAVORABLE` (cara vertical al polo, según latitud), `CAM_A_RAD_MAYOR_QUE_TECHO`.
- Chequeo bandejas vs alto (~726) compara contra `alto_menor_m`.
- **Hito 1: suite verde, campos inertes.**

### Etapa 2 — POA por superficie: `calculos/radiacion_camara.py` (nuevo)
- `clima_calc.calcular_POA_horizonte`: kwargs opcionales `tilt_deg=None, acimut_duffie_deg=None` (None → lee del emplazamiento; 9 call sites intactos). Patrón de `p2_emplazamiento._calcular_poa_horaria:258-298`.
- Módulo nuevo (sin streamlit, SI, docstrings Google es):
  - `factores_intercepcion(camara) -> dict[str, float]` — f_i por cara (techo y verticales, fórmulas de arriba).
  - `poa_caras_camara(datos, empl, camara) -> dict[str, pd.Series]`.
  - `series_radiacion_camara(datos, empl, camara) -> tuple[pd.Series, pd.Series]` → `(I_eq_prod, Q_rad_aire_W)`. Shortcut techo-solo β=0: `I_eq_prod = GHI` sin pvlib (Q_rad_aire también desde GHI). Sin caras activas / cubierta None → ceros.
  - `factores_sinteticos(camara) -> tuple[float, float]` — para modo sintético (factor de I_g_max al producto y W por W/m² al aire); (1.0, factor_techo) en default.
- **Hito 2: helpers testeados standalone (`tests/test_calculos/test_radiacion_camara.py`).**

### Etapa 3 — Motor: término `Q_rad_aire` + áreas por cara
- `calculos/camara_termodinamica.py` (cambios mínimos y aditivos):
  - `resolver_estado_camara(..., Q_rad_aire_W: float = 0.0)`: sumando en numerador del balance lineal de `T_flujo` (sigue lineal; default 0 = back-compat exacta).
  - `simular_secado` / `simular_cascada`: acepta serie opcional `Q_rad_aire_W` (interpolada por paso como I_g; None → 0). Cascada reparte `/N` como las áreas.
- `core/camara.py::ForzantesAire`: campo `Q_rad_aire_W: Optional[np.ndarray] = None` (None → ceros; docstring con semántica). Docstring de `I_g_W_m2` actualizado: "irradiancia equivalente al producto; coincide con GHI para techo horizontal único".
- `calculos/camara_calc.py::_construir_params_termodinamico` (155-229): `A_cuerpo = g.A_cuerpo_total_m2`; `A_techo` del motor → `A_transl_total = Σ` áreas de caras activas; `A_cuerpo_opaco = A_cuerpo_total − A_transl_total`; τ/α/A_rad/R_cond y área transversal sin cambios. Pasa `Q_rad_aire` de las forzantes al motor. Cascada hereda vía `_ParamsCamaraTD`.
- **Hito 3: suite verde; con forzantes sin `Q_rad_aire_W` el comportamiento es idéntico al actual.**

### Etapa 4 — Builders de forzantes (fases 1 y 2 a la vez)
`I_g_W_m2` pasa de GHI a `I_eq_prod` y se agrega `Q_rad_aire_W`, vía `series_radiacion_camara` (try/except → fallback GHI + advertencia; `I_g_POA_W_m2` del colector NO se toca):
1. `ui/p4_camara.py::_forzantes_desde_slice` (~262-305; cubre días reales ARMARIO/CAJA y ventana multidía) — param `camara` nuevo.
2. `_construir_forzantes_reales` día único (~405) y `_construir_forzantes_reales_caja` (~516).
3. Rama sintético (~201-213): `factores_sinteticos` sobre la semicampana.
4. `balance_global.armar_forzantes_ventana` (~1810) — **fase 2 GRAN_ESCALA** (batch y túnel).
5. `operacion_anual_camara.py::_calcular_punto_mensual` (~202) — **fase 2 ARMARIO anual**.
- Actualizar texto del aviso `ADV_PICARD_POA_NO_DISPONIBLE` (fallback del colector a `I_g_W_m2`, ahora I_eq_prod; solo ocurre en sintético).
- **Hito 4: pipelines corren; ARMARIO opaco bit-idéntico; CAJA/techo-translúcido con el cambio numérico deliberado documentado (verificar magnitud razonable contra el anclaje del armario 50 kg).**

### Etapa 5 — UI (P4/P2) + serialización JSON
- P4 geometría (~1600-1627), todas las tipologías: pendiente techo [°] (0–60), acimut de cámara en UI360 (conversiones `acimut_duffie_a_ui360`/`acimut_ui360_a_duffie`, patrón P2:669-731), selectbox cara de caída (help con convención izq/der mirando en dirección del flujo); caption alto frente/atrás, volumen, área real de techo. `_build_camara` (~2484) y constructor (~2585) propagan campos (usar `dataclasses.replace` donde aplique — gotcha S36).
- P4 "Techo translúcido" → "Superficies translúcidas" (~1629-1698): material/espesor sin cambios; 5 toggles (default solo techo); tabla preview cara|área|tilt|orientación|f_i|translúcida desde `geometria.caras()` + `factores_intercepcion`; en CAJA error si 0 caras activas.
- Serialización: `_json_config_camara` agrega campos; `_from_json_camara` (~1011-1133) con `.get(..., default)` → **snapshot viejo = defaults**. Test round-trip + dict viejo.
- P2 (~669-731): expander orientación del colector oculto si CAJA (caption → P4); gráfica POA en CAJA usa (β, γ) de la cámara vía `_calcular_poa_horaria`.
- **Hito 5: smoke manual Streamlit (CAJA caras+pendiente; ARMARIO cámara ≠ colector).**

### Etapa 6 — Consumidores derivados
- P7: en CAJA omitir labels de colector (~599-610); snapshot/resumen con campos nuevos; sugerencia de irradiancia (~482) en CAJA usa I_eq_prod. `ui/reporte.py`: tabla emplazamiento por tipología, filas nuevas de cámara, figura POA de CAJA con orientación de cámara.
- `docs/mapa_conexiones.md`, `CHANGELOG.md` (Added + Changed por el cambio numérico), bitácora (decisiones: I_eq_prod, reparto f_i, alto medio, α_int; mejoras futuras: IR nocturna, discretización por bandeja).

### Etapa 7 — Barridos paramétricos
- `catalogo_parametros_barrido.py`: `pendiente_techo_camara` (path `camara.geometria.pendiente_techo_deg`) y `acimut_camara` (conversiones UI360).
- **Fix necesario:** en barrido transitorio `forzantes_base` se congela → barrer orientación sería no-op. `BarridoConfig.forzantes_builder: Callable | None`, invocado por punto en `_despachar_motor` (~247); P7 inyecta el closure (creado en ui/, no invierte capas).

## Tests

- **Red de back-compat (pasan SIN editar):** `test_techo_translucido.py` (resolver_estado_camara con params explícitos → intactos), `test_camara_termodinamica.py`, `test_camara_cascada.py`, `test_radiacion_cubierta.py`, `test_balance_global*.py`, `test_operacion_anual_camara.py`, `test_simulacion_ventana.py`, `test_pared_camara.py`, `test_proyecto_coherencia.py`, `test_forzantes_reales.py` (los de ARMARIO opaco). `test_caja.py` es smoke/relacional — debería pasar; si algún assert fija números de Q_rad, revisar si es el cambio deliberado antes de tocar.
- **Nuevos:** 1 test por código de error (nombre = código en minúsculas); geometría un agua a mano (β=30°, caída frente y lateral; β=0 ≡ fórmulas actuales); `test_radiacion_camara.py` (shortcut GHI exacto, monotonía al agregar caras, cara vertical vs pvlib directo, f_i a mano con bandejas conocidas, factores sintéticos); `Q_rad_aire` en resolver (0 = histórico; >0 sube T_flujo); balance de energía cierra con el término nuevo; builders con cámara orientada (I_g ≠ GHI, POA colector intacta, Q_rad_aire poblada); round-trip JSON; barridos con builder.

## Verificación
- Por hito: `.venv/bin/python -m pytest` + `black .` + `ruff check .`
- E2E: `.venv/bin/python -m streamlit run Secasol.py` — (a) CAJA: pendiente 25° acimut Norte + frente/laterales translúcidos → P7 diario: Q_rad mayor y curva más ancha que techo-solo; T_flujo sube por Q_rad_aire; (b) snapshot JSON viejo carga con defaults; ARMARIO opaco da resultados idénticos a hoy; (c) ARMARIO con cámara ≠ colector: POA colector inalterada; (d) orden de magnitud contra anclaje armario 50 kg.
- Working tree puro, sin commits (convención del repo).

## Riesgos anotados
- **Cambio numérico deliberado** en CAJA/techo-translúcido existentes (Q_rad_aire antes perdido): validar magnitud, documentar en CHANGELOG.
- Cascada multi-zona reparte áreas y Q_rad_aire `/N` uniforme (la cara frente pertenece a la zona 1) — aproximación de prediseño, documentar.
- f_i de paredes asume bandejas a lo ancho de la cámara y no depende de la altura del stack vs posición — aproximación de silueta, documentar en docstring.
- Fallback NaN de POA cae a GHI por hora (sobreestima en caras verticales) — convención existente heredada.
- Esquema visual `camara_dimensiones` no muestra el un agua — pendiente opcional, no bloqueante.

## Ver también

- [[mapa_conexiones]] — widget → campo → consumidor.
- `Balance_de_calor_y_masa_en_camara_ampliado.md` (raíz) — derivación del motor termodinámico donde entra `Q_rad_aire`.
