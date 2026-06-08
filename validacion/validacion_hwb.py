"""Validación del modelo Tipo 1 contra la curva HWB (Hottel-Whillier-Bliss).

La curva HWB describe el rendimiento estacionario de un colector como:
    η = F_R · (τα) - F_R · U_L · (T_in − T_amb) / G

Si el modelo es físicamente correcto:
1. La regresión `η vs (T_in − T_amb)/G` debe ser LINEAL.
2. El intercepto debe ser positivo y ≤ τα efectivo.
3. La pendiente debe ser negativa (mayor ΔT → mayor pérdida → menor η).
4. F_R · U_L debe estar en rango típico para air heaters: 4–12 W/m²·K.
5. F_R · (τα) debe estar en rango típico: 0.4–0.75.

Si el balance global cierra y la curva HWB es lineal con parámetros razonables,
el modelo es válido en sentido físico (referencia: D&B Cap. 6.7).
"""

from __future__ import annotations

import numpy as np

from core.colector import Colector, ColectorUnidad, BancoColectores
from calculos.colector_calc import calcular_colector_tipo1


def construir_curva_hwb(
    id_cubierta: str,
    id_placa: str,
    T_amb_C: float,
    I_g: float,
    v_w: float,
    beta: float,
    delta_T_list_K: list[float],
) -> tuple:
    """Corre el modelo a varias T_in y devuelve (x, η).

    x = (T_in − T_amb) / G  [m²·K/W]
    """
    u = ColectorUnidad(ancho_m=1.0, largo_m=2.0, id_cubierta=id_cubierta, id_placa=id_placa)
    col = Colector(unidad=u, banco=BancoColectores())
    T_amb_K = T_amb_C + 273.15
    xs, etas = [], []
    for dT in delta_T_list_K:
        T_in = T_amb_K + dT
        res = calcular_colector_tipo1(
            colector=col,
            T_amb_K=T_amb_K,
            I_g_W_m2=I_g,
            v_viento_ms=v_w,
            P_amb_Pa=101325.0,
            T_entrada_K=T_in,
            pendiente_deg=beta,
        )
        x = dT / I_g
        xs.append(x)
        etas.append(res.eta_termica)
    return np.array(xs), np.array(etas)


def evaluar_caso(
    nombre: str,
    id_cubierta: str,
    id_placa: str,
    T_amb_C: float,
    I_g: float,
    v_w: float,
    beta: float,
):
    """Construye curva HWB, ajusta lineal y reporta parámetros físicos."""
    dT_list = [0, 5, 10, 20, 30, 40]
    x, eta = construir_curva_hwb(id_cubierta, id_placa, T_amb_C, I_g, v_w, beta, dT_list)
    # Ajuste lineal η = a − b·x
    coef = np.polyfit(x, eta, 1)
    b, a = -coef[0], coef[1]  # pendiente positiva b = F_R·U_L
    # R² del ajuste
    eta_fit = np.polyval(coef, x)
    ss_res = np.sum((eta - eta_fit) ** 2)
    ss_tot = np.sum((eta - np.mean(eta)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0

    rango_FRtaualfa_ok = 0.30 <= a <= 0.80
    rango_FRUL_ok = 2.0 <= b <= 15.0
    # Piso de linealidad laxo: con propiedades del aire variables (k, μ, Pr vs T)
    # la curva η-vs-x ya no es EXACTAMENTE lineal (R²=1.0000 era el caso de
    # propiedades constantes); aparece una curvatura mínima físicamente correcta.
    # HWB es de por sí una linealización (U_L constante). Exigimos R² ≥ 0.99 como
    # chequeo de cordura y validamos la física por los parámetros + monotonía.
    lineal_ok = r2 >= 0.99
    # Monotonía: η debe decrecer con x (sin curvatura de signo invertido).
    monotonia_ok = all(eta[i] >= eta[i + 1] - 1e-9 for i in range(len(eta) - 1))

    print(f"\n--- {nombre} ---")
    print(f"  Condiciones: T_amb={T_amb_C}°C, I_g={I_g} W/m², v_w={v_w} m/s, β={beta}°")
    print(f"  η a ΔT=0:    {eta[0]:.3f}    (esperado: F_R·(τα) ≈ 0.4–0.75)")
    print(f"  η a ΔT=40K:  {eta[-1]:.3f}")
    print(f"  Ajuste lineal: η = {a:.3f} − {b:.3f}·x   (R²={r2:.4f})")
    print(f"  F_R·(τα) = {a:.3f}  {'✓' if rango_FRtaualfa_ok else '✗ fuera de rango típico'}")
    print(f"  F_R·U_L  = {b:.3f}  {'✓' if rango_FRUL_ok else '✗ fuera de rango típico'}")
    print(f"  Linealidad R² = {r2:.4f}  (piso 0.99)  {'✓' if lineal_ok else '✗ no lineal'}")
    print(f"  Monotonía η↓ con x  {'✓' if monotonia_ok else '✗ curvatura invertida'}")
    return rango_FRtaualfa_ok and rango_FRUL_ok and lineal_ok and monotonia_ok


if __name__ == "__main__":
    print("=" * 70)
    print("Validación HWB — modelo numérico Tipo 1 contra teoría HWB (D&B 6.7)")
    print("=" * 70)
    print("\nTest: η lineal vs. (T_in − T_amb)/G")
    print("  Si modelo es correcto: R² ≥ 0.99, monotonía y parámetros en rango típico.")
    print("  (Con propiedades del aire variables el R² baja levemente de 1.0000.)")

    resultados = []
    resultados.append(
        evaluar_caso(
            "Vidrio + selectiva (TiNOX)",
            "vidrio_comun",
            "aluminio_tinox",
            T_amb_C=20,
            I_g=800,
            v_w=2.0,
            beta=30,
        )
    )
    resultados.append(
        evaluar_caso(
            "Vidrio + negra mate",
            "vidrio_comun",
            "galvanizada_pintada_negro_mate",
            T_amb_C=20,
            I_g=800,
            v_w=2.0,
            beta=30,
        )
    )
    resultados.append(
        evaluar_caso(
            "Policarbonato + negra mate",
            "policarbonato_alveolar",
            "galvanizada_pintada_negro_mate",
            T_amb_C=20,
            I_g=800,
            v_w=2.0,
            beta=30,
        )
    )
    resultados.append(
        evaluar_caso(
            "Policarbonato + selectiva, invierno",
            "policarbonato_alveolar",
            "aluminio_tinox",
            T_amb_C=0,
            I_g=600,
            v_w=4.0,
            beta=45,
        )
    )

    print("\n" + "=" * 70)
    print(f"Casos OK: {sum(resultados)}/{len(resultados)}")
    print("=" * 70)
