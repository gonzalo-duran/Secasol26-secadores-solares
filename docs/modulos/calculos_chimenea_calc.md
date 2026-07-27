<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/chimenea_calc

Ruta: `calculos/chimenea_calc.py`

## Descripción

Modelo de chimenea solar — tiro térmico, fricción y caudal de equilibrio.

Modelo cuasi-estacionario unidimensional. La chimenea induce flujo natural
por diferencia de densidad entre la columna de aire caliente (cámara + chimenea)
y la atmósfera circundante. El caudal de equilibrio se obtiene cuando el tiro
disponible iguala las pérdidas totales del lazo.

Fenómenos modelados:
- Tiro térmico (stack effect): ΔP_tiro = g·H_eff·(ρ_amb − ρ_chim).
- Fricción en el ducto de chimenea: Darcy-Weisbach con Haaland.
- Pérdidas singulares de entrada y salida (K bundleado por defecto = 1.5).
- Extractor eólico opcional en el tope (turbina sombrero chino): agrega un
  término motriz ΔP = Cp·ρ_amb·v_viento²/2 al balance, donde v_viento se
  corrige de la altura del contrato de `Clima` (2 m, ver `perfil_viento`) a la
  altura del tope via perfil logarítmico. La turbina también introduce una
  resistencia adicional al flujo Kt·ρ_chim·v_extractor²/2.

Convención termodinámica:
- T_chim es la temperatura promedio de la columna ascendente (cámara + chimenea).
- Para prediseño se recomienda T_chim ≈ T_salida_camara (el aire ya pasó por
  el enfriamiento evaporativo en la cámara), no T_salida_colector.
- H_eff = altura_chimenea + altura útil de la cámara (entrada de aire frío
  en la base, salida por la chimenea superior).

API pública:
- `delta_P_tiro_Pa`: tiro térmico disponible.
- `delta_P_turbina_motriz_Pa`: depresión motriz del extractor eólico.
- `delta_P_chimenea_Pa`: pérdida en el ducto (fricción + singulares + turbina).
- `caudal_natural_kgs`: caudal másico de equilibrio del lazo completo.

El módulo es puro: no depende de `core/` ni de `streamlit`. Toma primitivas
para mantenerse testeable y reusable desde cualquier capa.

## Clases y funciones

**Funciones:**

- `delta_P_tiro_Pa()`
- `delta_P_turbina_motriz_Pa()`
- `delta_P_chimenea_Pa()`
- `coeficientes_bocas()`
- `delta_P_bocas_Pa()`
- `caudal_natural_kgs()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
