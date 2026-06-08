<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/probe_motor_C_yacon

Ruta: `validacion/probe_motor_C_yacon.py`

## Descripción

probe_motor_C_yacon.py
======================
Sonda exploratoria del motor termodinámico (TD) con yacón.

Tras la consolidación del motor (2026-05-16) se eliminó el antiguo "Motor C
cinético dinámico" (camara_calc_dinamico). El motor TD difusivo lo absorbió,
por lo que esta sonda corre ahora `simular_secado` vía `calcular_camara` con
forzantes sintéticas día/noche, y reporta en qué rango de (T_op, HR, masa,
X_obj) el motor converge a X_obj dentro del horizonte.

Diferencia clave con la sonda anterior: el motor TD usa K_m difusivo + GAB
para el yacón (NO usa la cinética Lewis/Page Shi 2013 que era central en el
motor cinético borrado). Por eso los rangos donde converge pueden diferir
significativamente respecto al reporte histórico de S26.

## Clases y funciones

**Funciones:**

- `correr_TD()`
- `main()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
