<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/validacion_hwb

Ruta: `validacion/validacion_hwb.py`

## Descripción

Validación del modelo Tipo 1 contra la curva HWB (Hottel-Whillier-Bliss).

La curva HWB describe el rendimiento estacionario de un colector como:
    η = F_R · (τα) - F_R · U_L · (T_in − T_amb) / G

Si el modelo es físicamente correcto:
1. La regresión `η vs (T_in − T_amb)/G` debe ser LINEAL.
2. El intercepto debe ser positivo y ≤ τα efectivo.
3. La pendiente debe ser negativa (mayor ΔT → mayor pérdida → menor η).
4. F_R · U_L debe estar en rango típico para air heaters: 4–12 W/m²·K.
5. F_R · (τα) debe estar en rango típico: 0.4–0.75.

Si el balance global cierra y la curva HWB es lineal con parámetros razonables,
el modelo es válido en sentido físico (referencia: D&B Cap. 6.7).

## Clases y funciones

**Funciones:**

- `construir_curva_hwb()`
- `evaluar_caso()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
