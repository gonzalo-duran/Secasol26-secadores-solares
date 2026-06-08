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
        f  = 64/Re               (laminar, Re < 2 300)
        f  = 0.316·Re^(-0.25)   (Blasius turbulento, 2 300 ≤ Re < 100 000)
        En banco serie: ΔP_rama = ΔP_unidad × n_serie
        En paralelo:   ΔP banco = ΔP rama

    Cámara — flujo HORIZONTAL:
        ΔP_cam = K_malla × (ρ · v_sup²/2) × n_bandejas
        v_sup = Q_vol / (ancho × alto)
        K_malla = 2.0 (malla de alambre, conservador)

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
