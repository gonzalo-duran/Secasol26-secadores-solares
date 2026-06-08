<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: core/motor

Ruta: `core/motor.py`

## Descripción

Dataclass del motor / ventilador del sistema de convección forzada.

Motor se almacena en Proyecto.motor. Es None para tipologías de convección
natural (proyecto.motor = None en ese caso — no instanciar Motor).

Las potencias se calculan en __post_init__ a partir de la pérdida de carga del
sistema y las eficiencias del ventilador y el motor eléctrico:

    P_hidráulica = Q_vol × ΔP_total
    P_eje        = P_hid / η_ventilador
    P_eléctrica  = P_eje / η_motor
    P_a_instalar = P_elec × factor_servicio

La pérdida de carga total puede ingresarse directamente o calcularse a partir
de las pérdidas en colector, cámara y ductos.

## Clases y funciones

**Clases:**

- `TipoAccionamiento`
- `Motor`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
