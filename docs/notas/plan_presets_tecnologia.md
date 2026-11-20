# Plan — Presets de tecnología: galería de secadores típicos

**Estado:** EN ESPERA (S68, 2026-11-17). Se implementó la Fase A completa y **se volvió atrás
por decisión del usuario**: no se implementa todavía. El código quedó guardado en un stash local
(§7), sin commitear. Antecedentes: [[docs/bitacora/bitacora_sesion68]].

---

## 1. Por qué

Después de la conferencia magistral de CONSYCSA, la observación del usuario es que Secasol es
grande y complejo para quien empieza (productor o alumno). Para ver un resultado hay que recorrer
las 7 pestañas, descargar el clima en P2, evaluar el colector en P3, calcular el horizonte en P4
y recién ahí P7 ofrece el transitorio. El objetivo es una entrada simple a partir de **secadores
típicos precargados**.

**Idea clave del usuario:** un preset **no es un proyecto de ejemplo, es una tecnología**
(tipología, materiales, dimensiones, colector, cámara, accionamiento) que se puede **llevar a
distintos sitios** y **cargar con distintos productos y masas**. Son tres ejes ortogonales:

| Eje | Contenido | Dónde vive hoy |
|---|---|---|
| Tecnología (preset) | `configuracion`, `colector`, `camara` (sin carga), `auxiliar`, `motor`, `chimenea` | secciones de `Proyecto` |
| Sitio | `emplazamiento` + `clima` | P2 |
| Producto | `camara.carga_producto` (id, masa, humedades) | P4 |

## 2. Decisiones tomadas con el usuario

- **Por fases.** Fase A: galería de presets que llena las 7 pestañas, con una guía de próximos
  pasos. Fase B: página "Inicio rápido" de un clic (plan propio al cerrar A).
- **Sitios.** Lista de sitios de referencia con un año de clima NASA POWER empaquetado
  (instantáneo y sin red) + cualquier lat/lon, que se descarga como hoy.
- **Catálogo inicial.** Caja directa natural, caja con chimenea solar, armario indirecto
  (natural y forzado) e industrial ADITAL.
- **Autoría.** El usuario diseña cada preset **en la propia app** y lo exporta con "Guardar
  como preset". Agregar uno no requiere tocar código.

## 3. Física del modelo (acoples al recombinar los ejes)

1. **Orientación.** `acimut_colector_deg` y `pendiente_colector_deg` viven en `Emplazamiento`
   (el sitio); `GeometriaCamara.acimut_camara_deg`, en la cámara. Un preset llevado al otro
   hemisferio quedaría mirando al polo. El preset guarda una **regla relativa**:
   - acimut `"ecuador"` (+ offset) o `"fijo"`. Hacia el ecuador = Duffie 0° si lat ≥ 0, 180° si
     lat < 0;
   - pendiente `{"latitud": |lat| + offset}` acotada a [0, 90], o fija;
   - cámara: mismo criterio.
   - **Los offsets se espejan entre hemisferios, no se rotan:** +20° = "20° del ecuador hacia el
     oeste" en ambos (N: γ = 0 + off; S: γ = 180 − off). Una rotación rígida haría que una cara
     que en Salta recibe el sol de la tarde pase a mirar al este en el hemisferio norte.
   - **Un plano horizontal (pendiente < 1°) se exporta como pendiente fija 0°**: es una decisión
     de diseño (techo plano, colector acostado), no un ajuste a la latitud.
   - Se resuelve al **aplicar** el preset. Si después el usuario edita la orientación en P2,
     manda lo editado.
2. **Capacidad de carga.** Desde S64 el espesor de capa se **deriva** de la masa
   (`Camara.__post_init__`). Cambiar producto o masa puede disparar `CAM_CAPA_DERIVADA_NO_ENTRA`
   o `COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA`. La máxima admisible es
   `m_max = min(20 kg/m²·A, ρ·(1−ε)·A·(s − 1 cm))`, con las mismas constantes que valida la
   cámara (`_CARGA_MAX_KG_M2`, `_MARGEN_LIBRE_BANDEJA_M`). La sugerida es
   `carga_sugerida_kg_m2 · A`, acotada a la máxima. Humedad inicial: `humedad_inicial_tipica`
   del catálogo. Humedad objetivo: el default de P4 (0.15), o la del preset si el producto es el
   mismo.
3. **El lecho es del producto.** ε, d_p, Φ_s y K de rugosidad (`ConfiguracionBandejas`) son
   propiedades del producto: al aplicar el preset vuelven a sus defaults para que
   `core.lecho.geometria_lecho` las tome del catálogo del producto nuevo.
4. **Fechas.** El día específico y la ventana de producción del preset se llevan al año del
   clima del sitio.
5. **Lo que no captura.** Un preset es un **punto de partida**, no el diseño óptimo para cada
   sitio y producto. Puede quedar sobre- o subdimensionado. Lo dicen la UI y el manual; lo
   señalan las advertencias de siempre.

## 4. Diseño (lo implementado en el stash)

### 4.1 Formato

`catalogo/presets/<id>.json` (`catalogo/` ya está en la whitelist de `deploy_hf.yml`): el
**mismo esquema de secciones** que el snapshot completo de P7, con `"seccion":
"preset_tecnologia"`, sin `emplazamiento`/`clima`/resultados, y un bloque `preset` (id = nombre
de archivo, nombre/descripción `{es,en,pt}`, orden, esquema, regla de orientación,
`carga_sugerida_kg_m2`, `productos_sugeridos`, `modo_analisis`). Reusa los deserializadores
`_from_json_*` de cada pestaña y sus rutas de back-compat.

### 4.2 Módulos

| Pieza | Archivo |
|---|---|
| Regla de orientación | `core/orientacion.py` (`ReglaOrientacion`, `resolver_orientacion`, `regla_desde_orientacion`) |
| Sitios de referencia | `core/sitios.py` + `catalogo/sitios/sitios.yaml` + `clima/<id>_<anio>.parquet` |
| Lectura del parquet | `calculos/clima_calc.clima_desde_parquet` (factorizado de la rama de caché de `obtener_clima`) |
| Lógica de preset (pura) | `core/preset_tecnologia.py`: `PresetInfo`, `rango_masa_kg`, `cargar_producto`, `orientar` |
| (De)serialización | `ui/componentes/presets_tecnologia.py` (`listar_presets`, `aplicar_preset`, `exportar_preset`); se extrae `carga_proyecto._reconstruir_equipos` |
| Galería + guía 🧭 en P1 | `ui/componentes/galeria_presets.py` |
| "Guardar como preset" en P7 | `ui/p7_resultados._render_guardar_preset`: solo con resultado vigente, así todo preset publicado ya corrió una vez |
| Preset ADITAL | `scripts/generar_preset_adital.py` → `industrial_adital.json`. **La fuente de verdad siguen siendo las factories de `core/presets.py`**; un test exige que coincidan |
| Empaquetar climas | `scripts/empaquetar_clima_sitios.py` (`.venv/bin/python -m scripts.…`) |
| Manual | capítulo nuevo `02_inicio_rapido.md` (slug `inicio-rapido`, Parte I) en ES/EN/PT + párrafo en la Introducción |
| i18n | `p1.presets.*`, `p7.preset_export.*`, línea en `sidebar.como_empezar`, `manual.toc.inicio-rapido` |

### 4.3 Hallazgos de la implementación (no redescubrir)

- **El camino real hasta un resultado es más largo de lo que parece.** En armario, las
  forzantes reales de P4 exigen una **evaluación diaria del colector en P3**
  (`p4_camara._disponibilidad_forzantes_reales`), y P4 arranca en forzantes "constantes" con el
  expander cerrado. La guía tiene que reflejar: clima → *Calcular desempeño del colector* (si
  hay colector) → *⚙️ Calcular cámara* → P7. Al cargar el preset se preselecciona
  `cam_forz_key = "real"`. En ventana industrial, P7 corre todo directo; en anual, el paso es
  *☀️ Calcular año completo*. **Esto es lo que justifica la Fase B.**
- **Navegación desde la guía:** `nav_seccion` es la key de un widget ya renderizado en el run;
  se cambia por `on_click` (callback), no asignándola en el cuerpo.
- **`.gitignore` ignora `*.parquet` globalmente:** hace falta la excepción
  `!catalogo/sitios/clima/*.parquet`. En el Space, su `.gitattributes` ya manda `*.parquet` por
  LFS, igual que los PNG de `assets/`.
- **Clima empaquetado:** 6 sitios × año 2023 ≈ 250 KB c/u (~1.5 MB). Propuesta de sitios:
  Salta, Cafayate, San Carlos, Abra Pampa, Santiago del Estero, Petrolina (BR). **La lista la
  define el usuario.**
- **Costo de la matriz de tests:** `calcular_todo` sobre un preset tarda ~1 s (ADITAL
  incluido); la matriz preset × 6 sitios × 2 productos entra en la suite sin problema.

## 5. Decisiones abiertas para el usuario

1. **Lista de sitios de referencia** (§4.3).
2. **Pendiente mínima** en la regla "latitud": en Petrolina (−9.4°) da un colector casi plano
   (9.7°). ¿Mínimo de ~15° por escurrimiento de lluvia y polvo?
3. **Caudal de ADITAL:** las factories de `core/presets.py` disparan `PROY_CAUDAL_INCONSISTENTE`
   (ventilador 4.37 m³/s contra 3.45 m³/s de la cámara a 1710 m, +26 %). Viene de antes de S68.
4. **Los cuatro presets del catálogo inicial** (caja directa, caja con chimenea, armario natural,
   armario forzado): los diseña el usuario en la app y los exporta.

## 6. Verificación (la que pasó en S68)

- Tests nuevos: `tests/test_core/test_orientacion.py` (29), `tests/test_ui/test_presets_tecnologia.py`
  (35, incluye la matriz preset × sitio × producto con `calcular_todo` como guardián de
  regresión), `tests/test_ui/test_galeria_presets.py` (3, AppTest: carga y navegación).
- Suite completa: **2061 passed, 2 skipped** (base 1978 + 2). black, ruff (excluyendo
  `docs/asades2026/`) y `scripts/auditar_i18n.py` limpios.
- Pendiente: prueba manual en Streamlit del recorrido completo con un armario.

## 7. Cómo retomar

El código de la Fase A está en un **stash local** de `testing`, creado sobre `ca68ceb`:

    git stash list            # buscar "S68 presets de tecnologia - Fase A implementada"
    git stash apply stash@{N} # aplica sin borrar el stash; resolver conflictos si testing avanzó

Incluye los 46 archivos (código, YAML de i18n, climas `.parquet`, manual, tests, y también las
entradas de documentación que se habían escrito: ADR-011, CHANGELOG, `mapa_conexiones.md`,
sección de `CLAUDE.md`). **Ojo:** un stash es local y frágil (se pierde con `git stash drop` o
`clear`). Si se quiere conservarlo más tiempo, conviene pasarlo a una rama
(`git stash branch presets-fase-a stash@{N}`), que es un commit y lo decide el usuario.

Si `testing` avanzó mucho y el stash no aplica limpio, este documento alcanza para
reimplementar: §3 (física), §4 (diseño) y §4.3 (hallazgos).

## 8. Fase B (fuera de este plan)

Página "Inicio rápido" (Tecnología → Sitio → Producto → **Simular** → 4–5 KPIs → "Abrir en modo
completo"). Requiere sacar de `ui/p4_camara.py` (`_construir_forzantes_termodinamico`, bloque del
botón *Calcular cámara*) una función `correr_horizonte(proyecto)` —que también resuelva la
evaluación diaria del colector de P3— y deje `p4_horizonte_resultado` / `p4_horizonte_meta` en
`session_state`, para que P7 lo tome como si lo hubiera calculado P4.
