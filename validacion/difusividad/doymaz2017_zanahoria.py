"""Zanahoria: reajuste de D dentro de Secasol contra Doymaz 2017 (S71).

Doymaz I. (2017). Drying kinetics, rehydration and colour characteristics of convective
hot-air drying of carrot slices. Heat Mass Transfer 53:25–35. DOI 10.1007/s00231-016-1791-8.

Muestras **control** (sin pretratamiento): rodajas de 2.5 cm de diámetro, 50 g por
corrida en bandeja perforada, aire a 2 m/s perpendicular a las caras, X0 = 8.33.
Digitalizadas en S71: Fig. 2A (50 °C; espesores 0.4 / 0.7 / 1.0 cm) y Fig. 1 (control,
0.4 cm; 50 / 60 / 70 °C). Las dos figuras coinciden en el caso común (0.4 cm, 50 °C).

A diferencia de ``reajuste_difusividad.py`` (que reconstruye la curva del paper desde su D y
compara el tiempo a MR = 0.2), acá se comparan las **curvas X(t) medidas completas**.

Hallazgo (S71): **ningún D único reproduce los tres espesores**, ni con la película de
Secasol ni con ninguna película más débil (factor libre sobre h), ni contando el canto de la
rodaja. El D que ajusta cada curva crece con el espesor (~d^1.3). La regla de S70 ("si D
crece con el espesor, limitaba el aire") no aplica: el tiempo de secado crece ×1.6 de 0.4 a
1.0 cm, menos que con película pura (×2.5) y que con difusión pura (×6.25). Causa probable:
encogimiento, que Secasol no modela. Soydan & Doymaz 2026 (mismo gabinete) repite el patrón;
Filipović 2022 (otro laboratorio) también, pero ahí lo explica la carga fija por área de
bandeja (las rodajas finas cubren toda la bandeja). Decisión del usuario: cargar el D de
0.4 cm (el ensayo más parecido al rallado), calidad BAJA.

Simulación en ``validacion/difusividad/curvas.py`` (con radiación de paredes del gabinete,
que acá no cambia nada: el ensayo está dominado por la difusión).

Supuestos (el paper no los informa): humedad absoluta del aire constante, HR 10 % a 50 °C;
``h`` de placa plana del diámetro de la rodaja con 2 m/s; caras de la rodaja (sin el canto)
como área de transferencia, igual que el motor.

Uso: ``.venv/bin/python -m validacion.difusividad.doymaz2017_zanahoria``
"""

from __future__ import annotations

import numpy as np

from calculos.psicrometria import humedad_absoluta
from validacion.difusividad.curvas import D_a, D_optimo, Ensayo, arrhenius, error

PRODUCTO = "zanahoria_rallada"
X0 = 8.33
V_AIRE_MS = 2.0
DIAMETRO_M = 0.025
P_PA = 101325.0
OMEGA = humedad_absoluta(0.10, 323.15, P_PA)  # HR 10 % a 50 °C, misma ω a 60 y 70 °C

# X cada 15 min desde t = 15 min [kg agua / kg ms], clave (espesor_m, T_C).
_X_MEDIDO = {
    # Fig. 2A, 50 °C
    (0.004, 50.0): [7.34, 6.35, 5.56, 4.76, 4.02, 3.38, 2.88, 2.42, 2.02, 1.72, 1.38, 1.16,
                    1.00, 0.81, 0.69, 0.54, 0.49, 0.36, 0.26, 0.18, 0.12],
    (0.007, 50.0): [7.47, 6.68, 6.03, 5.46, 4.92, 4.44, 3.96, 3.58, 3.20, 2.79, 2.46, 2.20,
                    1.93, 1.66, 1.44, 1.23, 1.08, 0.92, 0.79, 0.69, 0.62, 0.49, 0.43, 0.33,
                    0.23, 0.18, 0.12],
    (0.010, 50.0): [7.66, 6.94, 6.43, 5.84, 5.44, 5.01, 4.64, 4.21, 3.92, 3.58, 3.27, 3.03,
                    2.73, 2.45, 2.26, 2.13, 1.94, 1.76, 1.66, 1.46, 1.38, 1.21, 1.06, 0.91,
                    0.79, 0.59, 0.53, 0.43, 0.36, 0.26, 0.21, 0.16, 0.11, 0.07],
    # Fig. 1B y 1C, control 0.4 cm
    (0.004, 60.0): [7.13, 5.89, 4.79, 3.74, 2.84, 2.15, 1.56, 1.09, 0.75, 0.54, 0.35, 0.23,
                    0.17, 0.11, 0.08],
    (0.004, 70.0): [6.69, 5.23, 3.82, 2.66, 1.71, 1.17, 0.70, 0.40, 0.27, 0.18, 0.09],
}  # fmt: skip


def medido(espesor_m: float, T_C: float = 50.0) -> tuple[np.ndarray, np.ndarray]:
    """``(t [min], X)`` digitalizados, con el punto inicial."""
    X = np.array([X0] + _X_MEDIDO[(espesor_m, T_C)])
    return 15.0 * np.arange(len(X)), X


def ensayo(espesor_m: float = 0.004) -> Ensayo:
    """El ensayo de Doymaz 2017 con el espesor pedido."""
    return Ensayo(
        producto=PRODUCTO,
        X0=X0,
        espesor_m=espesor_m,
        v_aire_ms=V_AIRE_MS,
        L_placa_m=DIAMETRO_M,
        omega=OMEGA,
        c_ps_J_kgK=1470.0,
    )


def main() -> None:
    print("Espesor a 50 °C (D óptimo por curva):")
    for e in (0.004, 0.007, 0.010):
        t, X = medido(e)
        r0, b0 = error(ensayo(e), t, X, None, 50.0)
        D, r = D_optimo(ensayo(e), t, X, 50.0)
        print(
            f"   {e * 1000:4.1f} mm  solo película RMSE {r0:.3f} (MBE {b0:+.3f})"
            f"  →  D = {D:.2e}  RMSE {r:.3f}"
        )
    print("\nTemperatura, 4 mm:")
    pares = []
    for T_C in (50.0, 60.0, 70.0):
        t, X = medido(0.004, T_C)
        D, r = D_optimo(ensayo(), t, X, T_C)
        pares.append((T_C, D))
        print(f"   {T_C:4.0f} °C  D = {D:.2e}  RMSE {r:.3f}")
    D50, E_a = arrhenius(pares)
    print(f"\n→ Arrhenius: D(50 °C) = {D50:.2e} m²/s, E_a = {E_a / 1000:.1f} kJ/mol")
    for T_C, _ in pares:
        t, X = medido(0.004, T_C)
        r, b = error(ensayo(), t, X, D_a(T_C, D50, E_a), T_C)
        print(f"   con la recta, {T_C:.0f} °C: RMSE {r:.3f}  MBE {b:+.3f}")


if __name__ == "__main__":
    main()
