<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/campo_colectores_calc

Ruta: `calculos/campo_colectores_calc.py`

## Descripción

Red hidráulica y térmica del campo de colectores — gran escala (S41).

Modelo de prediseño del **campo completo** (banco + caño maestro): resuelve el
reparto real de caudal entre las ramas del banco considerando la pérdida de
carga acumulada del troncal del caño maestro, y evalúa la temperatura de salida
de cada rama a su caudal propio.

Física / metodología (ASHRAE Handbook 2017, cap. 21 "Duct Design"):
    - Fricción por tramo: Darcy-Weisbach con factor de Haaland (Ec. 34),
      sección local del troncal interpolada (constante o creciente, S41).
    - Pérdidas singulares de boca: ΔP = C·(ρv²/2) con C referido a la sección
      de la rama (Ec. 33) — campana de reducción + llave mariposa del
      ``CanoMaestro``. La pérdida de mezcla de la unión convergente (Ec. 32/33
      con C de la Duct Fitting Database) se desprecia en v1: es de segundo
      orden frente a fricción de troncal + resistencia de rama.
    - Igualdad de presión total: todas las trayectorias (rama i + troncal desde
      su boca hasta el ventilador) ven la misma ΔP total. El reparto {q_i} se
      resuelve por punto fijo amortiguado sobre esa igualdad.

Convención de numeración: la **boca 1 es el extremo lejano** al ventilador
(inicio del caño, sección mínima si es variable); la boca N descarga junto al
ventilador. El troncal se discretiza en N tramos de largo L/N; el tramo i
transporta el caudal acumulado de las bocas 1..i.

Capa calculos/: sin Streamlit. Consumido por la UI de P3 (sección "Evaluación
del campo de colectores").

## Clases y funciones

**Clases:**

- `ResultadoCampoColectores`

**Funciones:**

- `evaluar_campo_colectores()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
