"""Barrido de la difusividad del charqui en la réplica de Durán 2008 (S71).

Política de S70: el D que se carga en el catálogo es el que hace que **Secasol**
reproduzca el ensayo, con su película y su isoterma. Este script corre la réplica
completa (``replica_charqui_forzado.correr``) para cada D y compara contra la
X(t) medida (Fig. 22). Cada corrida tarda ~1 s.

Uso::

    .venv/bin/python -m validacion.duran2008.barrido_difusividad 8e-11 9.5e-11 1.1e-10
"""

from __future__ import annotations

import copy
import sys

import numpy as np

from core import catalogo
from validacion.duran2008 import replica_charqui_forzado as replica

_DEFAULT = (6e-11, 8e-11, 9e-11, 9.5e-11, 1e-10, 1.1e-10, 1.3e-10, 2e-10)


def barrer(valores_D: tuple[float, ...] = _DEFAULT) -> list[tuple[float, float, float]]:
    """Corre la réplica para cada D y devuelve ``(D, RMSE_X, MBE_X)``."""
    base = copy.deepcopy(catalogo.PRODUCTOS["charqui_vacuno"])
    filas = []
    try:
        for D in valores_D:
            datos = copy.deepcopy(base)
            datos["difusion_interna"]["D_ref_m2_s"] = D
            catalogo.PRODUCTOS["charqui_vacuno"] = datos
            th, res = replica.correr(verbose=False)
            t, sim, out = replica.comparar(th, res)
            rmse, mbe = out["X_panel"]
            X = sim["X"]
            x_noche = X[np.argmin(abs(t - 7.5))], X[np.argmin(abs(t - 22.0))]
            print(
                f"D={D:.2e}  RMSE_X={rmse:.4f}  MBE_X={mbe:+.4f}  "
                f"X 18:30={x_noche[0]:.3f}  X 9:00={x_noche[1]:.3f}",
                flush=True,
            )
            filas.append((D, rmse, mbe))
    finally:
        catalogo.PRODUCTOS["charqui_vacuno"] = base
    return filas


if __name__ == "__main__":
    args = tuple(float(a) for a in sys.argv[1:]) or _DEFAULT
    filas = barrer(args)
    D_opt, rmse_opt, _ = min(filas, key=lambda f: f[1])
    print(f"\nMínimo del barrido: D = {D_opt:.2e} m²/s (RMSE_X {rmse_opt:.4f})")
