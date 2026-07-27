<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/metricas_validacion

Ruta: `calculos/metricas_validacion.py`

## Descripción

Métricas de bondad de ajuste — validación medido vs simulado (mejora 38, fase 2).

Funciones puras (numpy, sin pandas ni streamlit) que cuantifican el ajuste entre
una serie **medida** de referencia y una serie **simulada** ya alineadas (mismos
instantes, misma longitud). Diseñadas para ser reusadas como **función objetivo**
por la calibración (fase 3), por eso no dependen de la UI ni del pipeline.

Convención: ``medido`` es la referencia (verdad de campo), ``simulado`` la salida
del modelo. El signo del sesgo (MBE) es ``simulado − medido`` (positivo = el modelo
sobreestima). Las métricas se calculan sobre los pares **sin NaN** en ninguna de
las dos series; ``n_pares`` reporta cuántos quedaron.

Definiciones (sobre los ``n`` pares válidos):
    RMSE = √⟨(s − m)²⟩                        [unidades de la señal]
    MBE  = ⟨s − m⟩                            [unidades de la señal, con signo]
    MAE  = ⟨|s − m|⟩                          [unidades de la señal]
    R²   = corr(m, s)²                        [adimensional, ciego al sesgo]
    NSE  = 1 − Σ(s − m)² / Σ(m − ⟨m⟩)²        [adimensional, skill vs la media]
    d    = 1 − Σ(s − m)² / Σ(|s − ⟨m⟩| + |m − ⟨m⟩|)²   [índice de Willmott, [0, 1]]

## Clases y funciones

**Clases:**

- `MetricasAjuste`

**Funciones:**

- `rmse()`
- `mbe()`
- `mae()`
- `r2()`
- `nse()`
- `indice_willmott()`
- `calcular_metricas()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
