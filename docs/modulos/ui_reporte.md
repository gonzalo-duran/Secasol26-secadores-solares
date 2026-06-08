<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/reporte

Ruta: `ui/reporte.py`

## Descripción

Generador de reporte PDF del prediseño completo.

Toma toda la información que producen los snapshots .json/.txt de las pestañas
P1–P7 más las gráficas que se generan en cada pestaña, y arma un PDF
estructurado con header institucional (GEEDSP / INENCO / CONICET-UNSa) en
cada página.

Las figuras de Plotly se exportan a PNG mediante ``kaleido`` (pinned a 0.2.1
en requirements.txt — la 1.x requiere Chrome instalado en el sistema, lo cual
no es viable en Streamlit Community Cloud).

API pública:
    generar_reporte_pdf(proyecto, session_state, res, T_amb_C, I_g, v_viento,
                       HR_cam_pct) -> bytes

## Clases y funciones

**Funciones:**

- `generar_reporte_pdf()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
