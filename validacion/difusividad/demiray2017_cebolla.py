"""Cebolla: reajuste de D dentro de Secasol contra Demiray et al. 2017 (S71).

Demiray E, Seker A, Tulek Y (2017). Drying kinetics of onion (Allium cepa L.) slices with
convective and microwave drying. Heat Mass Transfer 53:1817–1827.
DOI 10.1007/s00231-016-1943-x.

Rodajas circulares de 7 ± 1 mm, gabinete con aire a 0.2 m/s, 50 / 60 / 70 °C, X0 = 8.85
(89.83 % b.h.). Fig. 1 (secado convectivo) digitalizada en S71. Su Tabla 4 da
D = 3.5e-8 … 9.4e-8 m²/s, dos órdenes por encima de lo habitual en vegetales: no se usa.

Supuestos (el paper no los informa): rodajas de ~6 cm de diámetro (largo de placa para h);
2 caras expuestas; humedad absoluta del aire constante, HR 10 % a 50 °C.

Uso: ``.venv/bin/python -m validacion.difusividad.demiray2017_cebolla``
"""

from __future__ import annotations

import numpy as np

from calculos.psicrometria import humedad_absoluta
from validacion.difusividad.curvas import D_a, D_optimo, Ensayo, arrhenius, error

ENSAYO = Ensayo(
    producto="cebolla",
    X0=8.85,
    espesor_m=0.007,
    v_aire_ms=0.2,
    L_placa_m=0.06,
    omega=humedad_absoluta(0.10, 323.15, 101325.0),
)

# Fig. 1, cada 30 min desde t = 30 min [kg agua / kg ms].
_X_MEDIDO = {
    50.0: [7.06, 5.77, 4.93, 4.06, 3.44, 2.73, 2.27, 1.89, 1.47, 1.24, 1.01, 0.81, 0.65,
           0.54, 0.42, 0.34, 0.27, 0.21, 0.15],
    60.0: [6.59, 5.07, 3.95, 3.00, 2.18, 1.66, 1.20, 0.85, 0.58, 0.42, 0.30, 0.21],
    70.0: [5.98, 4.33, 2.95, 1.84, 1.05, 0.53, 0.19],
}  # fmt: skip


def medido(T_C: float) -> tuple[np.ndarray, np.ndarray]:
    """``(t [min], X)`` digitalizados, con el punto inicial."""
    X = np.array([ENSAYO.X0] + _X_MEDIDO[T_C])
    return 30.0 * np.arange(len(X)), X


def main(ensayo: Ensayo = ENSAYO) -> None:
    pares = []
    for T_C in sorted(_X_MEDIDO):
        t, X = medido(T_C)
        r0, b0 = error(ensayo, t, X, None, T_C)
        D, r = D_optimo(ensayo, t, X, T_C)
        pares.append((T_C, D))
        print(
            f"   {T_C:4.0f} °C  solo película RMSE {r0:.3f} (MBE {b0:+.3f})"
            f"  →  D = {D:.2e}  RMSE {r:.3f}"
        )
    D50, E_a = arrhenius(pares)
    print(f"→ Arrhenius: D(50 °C) = {D50:.2e} m²/s, E_a = {E_a / 1000:.1f} kJ/mol")
    for T_C in sorted(_X_MEDIDO):
        t, X = medido(T_C)
        r, b = error(ensayo, t, X, D_a(T_C, D50, E_a), T_C)
        print(f"   con la recta, {T_C:.0f} °C: RMSE {r:.3f}  MBE {b:+.3f}")


if __name__ == "__main__":
    main()
