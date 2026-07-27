<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/carta_psicrometrica

Ruta: `calculos/carta_psicrometrica.py`

## Descripción

Carta psicrométrica del proceso completo del secador (mejora 27).

Capa de cálculo **pura** (sin Streamlit ni Plotly): genera las curvas de fondo de
la carta psicrométrica (saturación, HR constante, isentálpicas) y extrae los
estados del aire húmedo en los puntos del proceso de secado:

    1. Ambiente            (T_amb, ω_amb)
    2. Salida del colector  — calentamiento sensible (ω constante)
    3. Entrada a la cámara  — calentamiento sensible del auxiliar (ω constante)
    4. Salida de la cámara  — el aire gana vapor (sube ω)

El tramo 3→4 es **enfriamiento ≈ adiabático** (sobre la isentálpica) en cámaras
indirectas/opacas, y **no adiabático** (h sube) en cámaras directas con techo
translúcido — esto **emerge solo** del balance porque el estado de salida
``(T_flujo, ω_flujo)`` ya sale del motor termodinámico de cámara (que incluye
``Q_rad`` del techo). La carta es descriptiva: grafica los estados calculados.

Todo en SI (T [K] en la API interna, °C en los estados expuestos para graficar;
ω [kg_agua/kg_aire_seco]; P [Pa]). La corrección por altitud entra vía ``P_Pa``
(la presión representativa del emplazamiento).

Reusa ``calculos/psicrometria.py`` (mismo módulo que el motor de cámara) — sin
dependencias externas.

## Clases y funciones

**Clases:**

- `EstadoPsicro`

**Funciones:**

- `curvas_fondo()`
- `isentalpica()`
- `estados_proceso()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
