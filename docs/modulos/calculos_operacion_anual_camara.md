<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/operacion_anual_camara

Ruta: `calculos/operacion_anual_camara.py`

## Descripción

Operación anual de la cámara de secado (cascada A + B).

Implementa el método de evaluación anual del prediseñador en dos pasadas:

- **Opción A** (analítica): modelo lineal del colector ``T_sal = T_amb +
  η·POA·A_col / (ṁ·c_p)`` que alimenta forzantes mensuales sintéticas.
- **Opción B** (termodinámica): el motor ``camara_termodinamica.simular_secado``
  corre con el día típico del mes sobre un horizonte de varios días,
  obteniendo m_evap y t_secado del batch representativo.

Para cada mes se construye el "día típico" promediando horariamente los
registros NASA POWER del mes, se replica sobre el horizonte del batch, y
se obtienen las 4 eficiencias de Augustus Leon (RSER 2002). Los resultados
mensuales se escalan a operación anual con ``batches_por_mes``.

Referencias del método:
    Augustus Leon, M., Kumar, S., Bhattacharya, S.C. (2002).
    "A comprehensive procedure for performance evaluation of solar food dryers".
    Renewable and Sustainable Energy Reviews 6(4), pp. 367-393.

    Forson, F.K., Nazha, M.A.A., Akuffo, F.O., Rajakaruna, H. (2007).
    "Design of mixed-mode natural convection solar crop dryers".
    Renewable Energy 32(14), pp. 2306-2319.

## Clases y funciones

**Clases:**

- `PuntoMensualCamara`
- `ResultadosAnualCamara`

**Funciones:**

- `calcular_operacion_anual_camara()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
