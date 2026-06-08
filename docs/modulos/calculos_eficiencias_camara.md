<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/eficiencias_camara

Ruta: `calculos/eficiencias_camara.py`

## Descripción

Eficiencias de cámara de secado — método Augustus Leon (RSER 2002).

Define las cuatro eficiencias del método estándar de evaluación de desempeño
de secadores solares. Las funciones toman primitivas (m_agua, energías,
áreas) para ser usables tanto desde simulaciones (motor termodinámico) como
desde balances analíticos a escala mensual.

Referencia:
    Augustus Leon, M., Kumar, S., Bhattacharya, S.C. (2002).
    "A comprehensive procedure for performance evaluation of solar food dryers".
    Renewable and Sustainable Energy Reviews 6(4), pp. 367-393.

Convención de unidades: SI estricto (J, kg, m, s, K).

## Clases y funciones

**Funciones:**

- `calor_latente_agua_J_kg()`
- `eta_drying()`
- `eta_pickup()`
- `eta_termica_camara()`
- `eta_total_sistema()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
