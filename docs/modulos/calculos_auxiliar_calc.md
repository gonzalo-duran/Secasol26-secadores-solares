<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/auxiliar_calc

Ruta: `calculos/auxiliar_calc.py`

## Descripción

Motor numérico del sistema de calentamiento auxiliar.

Calcula el salto de temperatura que produce el auxiliar sobre el flujo de aire
y los consumos de energía asociados.

Modelo:
    Balance de energía en régimen estacionario (sin inercia térmica):
        Q_eff = m_dot × cp_aire × (T_salida - T_entrada)
    Despejando T_salida:
        T_salida = T_entrada + Q_eff / (m_dot × cp_aire)

    Q_eff = potencia_nominal_W × fraccion_potencia_operacion

    Si set_point_T_K está definido y T_salida_sin_control > set_point,
    el modelo asume control proporcional ideal: el auxiliar entrega solo la
    potencia necesaria para alcanzar el set point.

## Clases y funciones

**Clases:**

- `ResultadosAuxiliar`
- `ResultadosAuxiliarTransitorio`

**Funciones:**

- `calcular_auxiliar()`
- `calcular_auxiliar_transitorio()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
