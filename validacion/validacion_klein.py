"""Validación del modelo de Tipo 1 contra la fórmula empírica de Klein (1979).

La fórmula de Klein para U_top (Duffie & Beckman, ec. 6.4.9) es la referencia
empírica clásica para el coeficiente global de pérdidas superiores de un
colector de placa plana. La comparamos contra el U_top "medido" del modelo
numérico, definido como:

    U_top_modelo = Q_top / (T_abs_medio - T_amb)

donde Q_top son las pérdidas por la cubierta superior (viento + radiación al
cielo) integradas a lo largo del colector.

La idea es verificar que tras la corrección de signos del residual, las
pérdidas superiores del modelo numérico estén en el mismo orden de magnitud
que Klein para un rango razonable de condiciones operativas.

Referencias
-----------
Duffie, J.A. & Beckman, W.A. (2013). Solar Engineering of Thermal Processes,
4ª ed., Wiley. Capítulo 6, ecuación 6.4.9 (Klein 1979).
"""

from __future__ import annotations

import math
import numpy as np

from core.colector import Colector, ColectorUnidad, BancoColectores
from calculos.colector_calc import (
    calcular_colector_tipo1,
    _h_viento_W_m2K,
    _T_cielo_K,
    SIGMA_SB,
)
from core.catalogo import CUBIERTAS, PLACAS


def u_top_klein(
    N: int,
    T_pm_K: float,
    T_amb_K: float,
    h_w_W_m2K: float,
    em_p: float,
    em_g: float,
    beta_deg: float,
) -> float:
    """Coeficiente de pérdidas superiores U_top según Klein (1979).

    Fórmula empírica ec. 6.4.9 de Duffie & Beckman.

    Args:
        N: Número de cubiertas transparentes.
        T_pm_K: Temperatura media de la placa absorbedora [K].
        T_amb_K: Temperatura ambiente [K].
        h_w_W_m2K: Coeficiente convectivo del viento sobre la cubierta [W/m²·K].
        em_p: Emisividad IR de la placa [adim].
        em_g: Emisividad IR de la cubierta [adim].
        beta_deg: Inclinación del colector respecto a la horizontal [°].

    Returns:
        U_top [W/m²·K].
    """
    f = (1.0 + 0.089 * h_w_W_m2K - 0.1166 * h_w_W_m2K * em_p) * (1.0 + 0.07866 * N)
    C = 520.0 * (1.0 - 0.000051 * beta_deg**2)
    e = 0.430 * (1.0 - 100.0 / T_pm_K)

    # Componente convectiva (entre placa y ambiente vía cubiertas y viento)
    termino_C = C / T_pm_K * ((T_pm_K - T_amb_K) / (N + f)) ** e
    U_conv = 1.0 / (N / termino_C + 1.0 / h_w_W_m2K)

    # Componente radiativa (linealizada)
    numerador_rad = SIGMA_SB * (T_pm_K + T_amb_K) * (T_pm_K**2 + T_amb_K**2)
    denominador_rad = (
        1.0 / (em_p + 0.00591 * N * h_w_W_m2K) + (2.0 * N + f - 1.0 + 0.133 * em_p) / em_g - N
    )
    U_rad = numerador_rad / denominador_rad

    return U_conv + U_rad


def u_top_modelo(resultado, T_amb_K, h_wind, em_cub, T_cie_K=None):
    """Estima U_top del modelo a partir de las pérdidas superiores integradas.

    Q_top(x) = h_w·(T_cub_e(x) − T_amb) + ε·σ·(T_cub_e(x)⁴ − T_cie⁴)
    U_top_modelo = ⟨Q_top⟩ / ⟨T_abs(x) − T_amb⟩

    Si T_cie_K=None, se usa T_cie = T_amb (consistencia con Klein, que no
    distingue cielo de ambiente).
    """
    T_ref_cie = T_amb_K if T_cie_K is None else T_cie_K
    T_cub_e = resultado.T_cub_e_K
    T_abs = resultado.T_abs_K
    q_conv = h_wind * (T_cub_e - T_amb_K)
    q_rad = em_cub * SIGMA_SB * (T_cub_e**4 - T_ref_cie**4)
    q_top = q_conv + q_rad
    dT = T_abs - T_amb_K
    # Promedios a lo largo de x
    return float(np.mean(q_top) / np.mean(dT))


def caso(
    nombre: str,
    id_cubierta: str,
    id_placa: str,
    T_amb_C: float,
    I_g: float,
    v_w: float,
    beta: float,
):
    """Corre un caso del modelo y lo compara contra Klein."""
    u = ColectorUnidad(
        ancho_m=1.0,
        largo_m=2.0,
        id_cubierta=id_cubierta,
        id_placa=id_placa,
    )
    col = Colector(unidad=u, banco=BancoColectores())
    T_amb_K = T_amb_C + 273.15
    res = calcular_colector_tipo1(
        colector=col,
        T_amb_K=T_amb_K,
        I_g_W_m2=I_g,
        v_viento_ms=v_w,
        P_amb_Pa=101325.0,
        T_entrada_K=T_amb_K,
        pendiente_deg=beta,
    )
    h_w, _ = _h_viento_W_m2K(v_w)
    em_cub = CUBIERTAS[id_cubierta]["emisividad_ir"]
    em_abs = PLACAS[id_placa]["emisividad_ir"]
    T_cie_K = _T_cielo_K(T_amb_K)
    T_pm_K = float(np.mean(res.T_abs_K))

    # Klein contra T_amb
    U_klein = u_top_klein(
        N=1, T_pm_K=T_pm_K, T_amb_K=T_amb_K, h_w_W_m2K=h_w, em_p=em_abs, em_g=em_cub, beta_deg=beta
    )
    # Modelo contra T_amb (consistente con Klein)
    U_mod_a = u_top_modelo(res, T_amb_K, h_w, em_cub, T_cie_K=None)
    # Modelo contra T_cie (físicamente exacto pero diverge de Klein)
    U_mod_c = u_top_modelo(res, T_amb_K, h_w, em_cub, T_cie_K=T_cie_K)

    disc = abs(U_klein - U_mod_a) / U_klein * 100
    print(
        f"  {nombre:30s}  T_pm={T_pm_K-273.15:5.1f}°C  η={res.eta_termica:.3f}  "
        f"U_klein={U_klein:5.2f}  U_mod(Tamb)={U_mod_a:5.2f}  U_mod(Tcie)={U_mod_c:5.2f}  "
        f"disc={disc:4.1f}%"
    )
    return disc


if __name__ == "__main__":
    print("=" * 110)
    print("Validación U_top: modelo numérico Tipo 1  vs.  Klein 1979 (D&B ec. 6.4.9)")
    print("=" * 110)
    print(
        f"  {'Caso':30s}  {'T_pm':>10s}  {'η':>5s}  {'U_klein':>7s}  "
        f"{'U_mod(Tamb)':>11s}  {'U_mod(Tcie)':>11s}  {'disc':>5s}"
    )
    print("-" * 110)

    discrepancias = []

    # Casos con vidrio + placa selectiva (caso clásico de D&B)
    discrepancias.append(
        caso(
            "vidrio, selectiva, viento bajo",
            id_cubierta="vidrio_comun",
            id_placa="aluminio_tinox",
            T_amb_C=20,
            I_g=800,
            v_w=1.0,
            beta=30,
        )
    )
    discrepancias.append(
        caso(
            "vidrio, selectiva, viento alto",
            id_cubierta="vidrio_comun",
            id_placa="aluminio_tinox",
            T_amb_C=20,
            I_g=800,
            v_w=4.0,
            beta=30,
        )
    )
    discrepancias.append(
        caso(
            "vidrio, selectiva, invierno",
            id_cubierta="vidrio_comun",
            id_placa="aluminio_tinox",
            T_amb_C=0,
            I_g=600,
            v_w=3.0,
            beta=45,
        )
    )

    # Casos con placa no selectiva (negro mate clásico)
    discrepancias.append(
        caso(
            "vidrio, negra mate",
            id_cubierta="vidrio_comun",
            id_placa="galvanizada_pintada_negro_mate",
            T_amb_C=20,
            I_g=800,
            v_w=2.0,
            beta=30,
        )
    )
    discrepancias.append(
        caso(
            "policarbonato, negra mate",
            id_cubierta="policarbonato_alveolar",
            id_placa="galvanizada_pintada_negro_mate",
            T_amb_C=20,
            I_g=800,
            v_w=2.0,
            beta=30,
        )
    )

    print("-" * 110)
    print(f"Discrepancia media: {np.mean(discrepancias):.1f}%   máx: {max(discrepancias):.1f}%")
    print("(Klein es empírica; discrepancias <20% son aceptables. >30% sugieren bug.)")
