<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/camara_termodinamica

Ruta: `calculos/camara_termodinamica.py`

## Descripción

Solver algebraico de cámara — motor termodinámico transitorio.

Resuelve el sistema acoplado para las variables algebraicas
(T_flujo, ω_flujo, T_cam_int, T_cam_ext) dado el estado del producto
(T_prod, X_prod) y las condiciones de boundary (T_ent, ω_ent, T_amb).

Hipótesis:
- CSTR (mezcla perfecta): aire en cámara uniforme a (T_flujo, ω_flujo).
- Cuasi-estacionario en aire (residencia << tiempo de secado).
- Pared en 3 nodos: T_flujo → T_cam_int (convección interior h_conv_int) →
  T_cam_ext (conducción por aislante k_aisl/esp_cam) → T_amb (convección
  exterior h_w por viento). La cascada se resuelve analíticamente en
  U_total = 1/(1/h_conv_int + esp_cam/k_aisl + 1/h_w); T_cam_int y T_cam_ext
  se reconstruyen como post-cómputos de la solución de T_flujo.
- Cinética de evaporación difusiva: ṁ_w = K_m · A_prod · (ω_sup − ω_flujo),
  con K_m la conductancia másica [kg/(m²·s)] y ω_sup = ω_sat(T_prod)·a_w(X_prod).

Resolución analítica directa (sin iteración interna), aprovechando la
linealidad del sistema cuando se fijan h_conv_int, K_m al inicio del paso:
    1. ω_sup = ω_sat(T_prod) · a_w(X_prod)
    2. (a) lineal en ω_flujo  → ω_flujo directo
    3. ṁ_w = ṁ_as · (ω_flujo − ω_ent)
    4. (b) lineal en T_flujo  → T_flujo directo
    5. T_cam_int, T_cam_ext por reparto resistivo de Q_pared

Referencias:
    - Bitácora Sesión 20 §24.3 (sistema de ecuaciones).
    - docs/notas/balance de calor y masa en camara ampliado.md (3-nodos pared).
    - Hallaire M (1963), reformulado en Mujumdar AS (ed.) Handbook of
      Industrial Drying, 4th ed., Cap. 3.

## Clases y funciones

**Clases:**

- `EstadoCamara`
- `ResultadoMotorTermodinamico`
- `ResultadoCascada`

**Funciones:**

- `resolver_estado_camara()`
- `simular_secado()`
- `simular_cascada()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
