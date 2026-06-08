<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/camara_calc

Ruta: `calculos/camara_calc.py`

## Descripción

Motor numérico de la cámara de secado solar — modelos de capa fina.

Implementa:
    - Isoterma GAB: X_eq = f(a_w, X_m, C, K)
    - Modelos cinéticos de capa fina: Lewis, Page, Henderson, Midilli, Logarítmico
    - Función principal: calcular_tiempo_secado_estatico()

Supuestos del modelo de prediseño:
    - Condiciones cuasi-estacionarias: T_aire y HR_aire constantes durante el secado.
    - a_w ≈ HR_operacion (gas ideal, aproximación válida para prediseño).
    - Modelo de capa fina: resistencia de transferencia de masa externa despreciable
      frente a la interna (Biot de masa >> 1), o bien los coeficientes k, n, etc.
      ya absorben el efecto del coeficiente externo.
    - Tiempo t en MINUTOS en los modelos (convención de los papers de referencia).

Modelos implementados (Razón de Humedad MR = (X - X_eq) / (X₀ - X_eq)):
    - lewis:       MR = exp(-k·t)                   params: {k}
    - page:        MR = exp(-k·t^n)                 params: {k, n}
    - henderson:   MR = a·exp(-k·t)                 params: {a, k}
    - midilli:     MR = a·exp(-k·t^n) + b·t         params: {a, k, n, b}
    - logaritmico: MR = a·exp(-k·t) + c             params: {a, k, c}

Referencias:
    - Mujumdar AS (2007). Handbook of Industrial Drying, 3ª ed. CRC Press.
    - Midilli A, Kucuk H, Yapar Z (2002). A new model for single-layer drying.
      Drying Technology 20(7):1503-1513.
    - Anderson RB (1946). J Am Chem Soc 68:686; Guggenheim EA (1966);
      De Boer JH (1953) — modelo GAB.

## Clases y funciones

**Clases:**

- `ResultadosCamara`

**Funciones:**

- `calcular_X_eq_gab()`
- `evaluar_MR()`
- `calcular_tiempo_secado_estatico()`
- `calcular_camara()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
