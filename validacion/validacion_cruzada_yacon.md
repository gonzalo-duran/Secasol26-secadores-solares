```
======================================================================
VALIDACIÓN CRUZADA — YACÓN (post-consolidación motor termodinámico)
Condiciones: T_op=60°C, HR=15%, ṁ=0.060 kg/s, P=87000 Pa
Producto: X_0=9.0 → X_obj=0.5 kg/kg ms, masa=5.0 kg
Geometría: 1.2×0.8×1.5 m, 5 bandejas×0.5 m²
======================================================================

┌─────────────────────────────────────┬──────────────────┬───────────────────┐
│  Motor                              │  t_secado        │  Δ vs Motor A     │
├─────────────────────────────────────┼──────────────────┼───────────────────┤
│  A — Capa fina estático             │  0.10 h          │  (referencia)     │
│  B — TD forzantes constantes        │  58.46 h         │  +60409.1%        │
│  C — TD día sintético (senoidal)    │  58.82 h         │  +60778.0%        │
└─────────────────────────────────────┴──────────────────┴───────────────────┘

  Δ C vs B (efecto del ciclo día/noche): +0.6%

DETALLES MOTOR B (termodinámico, constantes):
  status                : X_obj_alcanzado
  masa evaporada        : 4.250 kg
  T_prod final          : 34.0 °C
  T_max alcanzada       : 34.0 °C
  horas clipeo (pol. B) : 0.0 h

DETALLES MOTOR C (termodinámico, día sintético):
  status                : X_obj_alcanzado
  masa evaporada        : 4.250 kg
  T_prod final          : 36.3 °C
  T_max alcanzada       : 36.3 °C
  horas clipeo (pol. B) : 0.0 h
  horas HR > 95 %       : 0.0 h

DETALLES MOTOR A (capa fina estático):
  X_eq usado            : 0.031 kg/kg ms

ADVERTENCIAS:
  Motor A: CAM_T_FUERA_RANGO_CALIBRACION: T_operacion=60.0 °C fuera del rango de calibración del modelo 'page' (5–45 °C, margen ±10 K). La extrapolación puede ser imprecisa.
      CAM_ESPESOR_FUERA_CALIBRACION: espesor de capa 2.0 cm > 3× el espesor de calibración (0.4 cm). El modelo de capa fina subestima el tiempo de secado para capas gruesas. Considerar reducir el espesor de producto en bandeja o usar un modelo difusivo.
      CAM_RIESGO_SATURACION_AIRE: ω_salida calculada (0.2258 kg/kg) > ω_saturación (0.1850 kg/kg). El caudal de aire es insuficiente para transportar toda el agua evaporada sin saturarse. Aumentar el caudal o reducir la carga de producto.
      CAM_HR_SALIDA_ALTA: HR_salida = 100.0%. El aire sale casi saturado — condiciones de secado deficientes. Considerar aumentar el caudal de aire o reducir la carga.
  Motor B: (ninguna)
  Motor C: (ninguna)

INTERPRETACIÓN:
  Motor A vs B: divergencia del +60409% — el modelo estático no captura el cuello de botella del aire (efecto masa).
  Motor C vs B: divergencia del +1% — el ciclo día/noche no domina el balance global.

LIMITACIONES Y NOTAS:
  - Motor A: T fija, sin dinámica de masa ni T_prod; referencia rápida.
  - Motor B: aire de entrada constante. cp(X) variable y pared 3-nodos.
  - Motor C: senoidal sintética; n_dias replica el mismo día tipo.
    NO usa clima NASA POWER real (eso es modo 'real' en la UI).
  - Yacón sin Arrhenius en el catálogo → el motor termodinámico usa K_m
    difusivo + GAB de Marques 2022, no la cinética Lewis/Page.
  - Tras la consolidación del motor (2026-05-16) se eliminó el antiguo
    'Motor C cinético dinámico'. La comparación útil que queda es A→B (efecto
    masa y balance acoplado) y B→C (efecto del ciclo día/noche).

======================================================================
```

## Parámetros de entrada

| Parámetro | Valor |
|---|---|
| T_operacion | 60 °C |
| HR_operacion | 15% |
| T_ambiente | 25 °C |
| P_atm | 87000 Pa |
| ṁ_aire | 0.060 kg/s |
| X_0 | 9.0 kg/kg ms |
| X_obj | 0.5 kg/kg ms |
| masa | 5.0 kg |
| Motor C — amplitud T_sal_col | ±15.0 K |
| Motor C — amplitud T_amb | ±5.0 K |
| Motor C — n_dias | 4 |
