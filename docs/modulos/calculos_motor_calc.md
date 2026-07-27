<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/motor_calc

Ruta: `calculos/motor_calc.py`

## Descripción

Estimación de pérdidas de carga para el dimensionamiento del motor.

Provee funciones para calcular ΔP en el banco de colectores y en la cámara
de secado. Estos valores se usan como entrada al objeto Motor.

Modelos:
    Colector (canal rectangular) — Darcy-Weisbach:
        ΔP = f × (L/Dh) × (ρ × v²/2)
        Dh = 2·W·e / (W + e)    [diámetro hidráulico canal plano]
        f  = 64/Re                         (laminar, Re < 2 300)
        f  = Haaland(Re, ε/Dh)             (turbulento; aprox. de Colebrook,
             ASHRAE cap. 21 ec. 19; mismo f en colector, caño maestro y cámara)
        En banco serie: ΔP_rama = ΔP_unidad × n_serie
        En paralelo:   ΔP banco = ΔP rama

    Cámara — flujo HORIZONTAL (cross-flow, canales EN PARALELO):
        Los n_canales = n_bandejas−1 espacios entre bandejas están en paralelo:
        el ΔP del sistema es el de UN canal (no la suma). v_canal reparte el
        caudal: v_canal = Q_vol / (ancho · espacio_libre · n_canales).
        ΔP_cam = ΔP_producto + ΔP_malla_lateral, con
        ΔP_producto = fricción rugosa (Colebrook, ε_eff = max(ε_chapa, d_p)) +
                      obstrucción por bloqueo C_obs(β), β = espesor_capa/separacion.
        (Modelo combinado, mejora 29; reemplaza el Blasius + tabla heurística.)

    Cámara — flujo VERTICAL_ASCENDENTE:
        Por bandeja: ΔP = ΔP_malla + ΔP_lecho
        ΔP_malla = K_malla × (ρ · v₀²/2)
        ΔP_lecho = Ergun(v₀, ε, Φ_s, d_p, L)   [si d_p está definido]
        v₀ = Q_vol / area_bandeja

    Ergun (lecho empacado):
        ΔP/L = 150·μ·v₀·(1-ε)² / [(Φ_s·d_p)²·ε³]
             + 1.75·ρ·v₀²·(1-ε) / [(Φ_s·d_p)·ε³]

Propiedades del aire:
    ρ(T,P) = P / (R_aire · T)          [gas ideal, R_aire = 287.058 J/(kg·K)]
    μ(T)   = Sutherland (1893)         [válido 200–2 000 K, error < 2 %]
    P_atm(h) = ISA (atmósfera estándar, troposfera, h < 11 000 m)

## Clases y funciones

**Funciones:**

- `presion_atmosferica()`
- `densidad_aire()`
- `viscosidad_aire()`
- `estimar_delta_P_colector()`
- `estimar_delta_P_camara()`
- `estimar_delta_P_singulares()`
- `caudal_masico_a_volumetrico()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
