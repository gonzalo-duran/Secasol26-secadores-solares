<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/balance_global

Ruta: `calculos/balance_global.py`

## Descripción

Orquestador del cálculo global del secador solar.

Encadena los solvers de colector → auxiliar → cámara y calcula el balance
energético completo del sistema.

Flujo de cálculo:
    1. Colector (Tipo 1): T_entrada → T_salida, Q_util, η.
    2. Auxiliar (si configurado): T_salida_col → T_salida_aux, Q_aux.
    3. Cámara: T_entrada_camara → t_secado, X_final, masa_agua.
    4. Balance global: COP, fracción solar, etc.

Hipótesis de v0:
    - Condiciones cuasi-estacionarias durante todo el ciclo de secado.
    - Se usan condiciones representativas ingresadas por el usuario (no
      integración horaria sobre el día).
    - El colector se calcula siempre como Tipo 1 (canal único sobre absorbedor).
      Los Tipos 2, 3, 4 requieren selección explícita en versiones futuras.

## Clases y funciones

**Clases:**

- `ResultadosCompletos`
- `ResultadosCompletosTransitorio`

**Funciones:**

- `verificar_coherencia_proyecto()`
- `empl_de()`
- `presion_representativa_proyecto()`
- `resumen_camara()`
- `caudal_masico_banco_kg_s()`
- `conveccion_natural_activa()`
- `armar_forzantes_aire()`
- `construir_serie_sintetica_dia_tipo()`
- `calcular_todo()`
- `calcular_todo_transitorio()`
- `armar_forzantes_ventana()`
- `calcular_todo_ventana()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
