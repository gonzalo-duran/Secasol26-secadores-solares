<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: validacion/validacion_adital

Ruta: `validacion/validacion_adital.py`

## Descripción

Validación del modo industrial (gran escala) contra el secador ADITAL.

Referencia canónica: tesis doctoral de Gonzalo Durán, **Capítulo 3** —
"El uso de colectores solares de aire en secadores solares de escala
industrial: Ensayos en campo" (secador híbrido solar-leña ADITAL, San Carlos,
Salta, ~1800 msnm; ensayos de marzo 2009).

Parámetros de diseño de ADITAL (tesis, §2):
  - Banco: **26 colectores** de paso paralelo, 7.5 m × 0.94 m × 0.10 m, en dos
    grupos de 13 a los lados del caño maestro. Área de colección **195 m²**.
  - **Caño maestro** de 18 m, sección creciente (0.30×0.5 m → 1×0.90 m), 26 bocas
    con campana de reducción + llave mariposa. **No aislado** pero con aporte
    solar en su cara superior.
  - **Túnel** semicontinuo a contracorriente: 1.85 m alto × 3 m ancho × 18 m
    largo, aislado (lana de vidrio 5 cm). **24 carros, 5000 kg** de pimiento.
  - Ventilador centrífugo 4 HP, caudal de diseño ~600 m³/h por colector.

Resultados de campo (tesis, §3, días 20–22 marzo 2009) — los TARGETS:
  - **T salida colector ≈ 80 °C** al mediodía solar (ventilador apagado).
    Con ventilador (~14 h) la T de operación baja a ~60 °C; los colectores dan
    > 40 °C por ~8 h.
  - **Caño maestro: ΔT ≈ −3 °C** (pese a no estar aislado, por el aporte solar).
  - **Cámara de secado: 40–60 °C** durante ~8 h; incremento ~30 °C sobre ambiente.
  - Energía suficiente para **5000 kg en 4–5 días de sol**.

Clima sintético de un día de marzo (reproduce las Figs. 15–19 de la tesis;
sin dependencia de red): T_amb 8→38 °C, I_POA pico 1000 W/m², viento 1→5 m/s,
HR 90 %→20 %.

Criterio de validación: el modelo reproduce la **cadena térmica** medida en
campo (salida de colector + caída del caño maestro + temperatura de cámara).
La cinética de secado/throughput se reporta como contexto (depende de la
calibración GAB del pimiento, marcada MEDIA en el catálogo).

Uso:
    .venv/bin/python -m validacion.validacion_adital

## Clases y funciones

**Funciones:**

- `construir_colector_adital()`
- `construir_cano_adital()`
- `construir_camara_adital()`
- `dia_sintetico_marzo()`
- `check_colector()`
- `check_cano_maestro()`
- `check_camara()`
- `check_perdidas_carga()`
- `main()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
