"""Gráficas reutilizables de la UI compartidas entre pestañas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from calculos.camara_termodinamica import ResultadoMotorTermodinamico


def grafica_termodinamica_camara(
    res: "ResultadoMotorTermodinamico",
    X_obj: float,
    prod_id: str,
) -> plt.Figure:
    """Tres paneles temporales del motor termodinámico de la cámara.

    Panel 1: humedad del producto X(t) con X_obj y t_secado.
    Panel 2: temperaturas del producto y del aire en cámara.
    Panel 3: flujos de calor q_aire→producto y q_pérdida_pared.

    Args:
        res: Resultado del motor termodinámico de cámara.
        X_obj: Humedad objetivo en base seca [kg agua / kg ms].
        prod_id: Identificador del producto, para el título.

    Returns:
        Figura matplotlib con tres paneles compartiendo eje X.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(7, 9), sharex=True)
    t_h = res.t_array_s / 3600.0

    ax1.plot(t_h, res.X_prod_kg_kg, color="#1f77b4", linewidth=2, label="X(t)")
    ax1.axhline(
        X_obj, color="red", linestyle=":", linewidth=1.5,
        label=f"X_obj = {X_obj:.3f}",
    )
    if res.t_secado_s is not None:
        ax1.axvline(
            res.t_secado_s / 3600.0, color="orange", linestyle="-.",
            linewidth=1.5,
            label=f"t_secado = {res.t_secado_s / 3600.0:.1f} h",
        )
    ax1.set_ylabel("X [kg agua / kg ms]")
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)

    T_prod_C = res.T_prod_K - 273.15
    T_flujo_C = res.T_flujo_K - 273.15

    ax2.plot(t_h, T_prod_C, color="#d62728", linewidth=2, label="T producto")
    ax2.set_ylabel("T producto [°C]", color="#d62728")
    ax2.tick_params(axis="y", labelcolor="#d62728")

    ax2b = ax2.twinx()
    ax2b.plot(t_h, T_flujo_C, color="#2ca02c", linewidth=1.5,
              linestyle="--", label="T aire (cámara)")
    ax2b.set_ylabel("T aire cámara [°C]", color="#2ca02c")
    ax2b.tick_params(axis="y", labelcolor="#2ca02c")

    flujo_rango = float(T_flujo_C.max() - T_flujo_C.min())
    ax2b.annotate(
        f"var. T_aire = {flujo_rango:.1f} °C",
        xy=(0.98, 0.05), xycoords="axes fraction",
        ha="right", fontsize=7, color="#2ca02c",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
    )

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="lower right")
    ax2.grid(True, alpha=0.3)

    ax3.plot(t_h, res.q_prod_W, color="#ff7f0e", linewidth=1.5, label="q aire→producto")
    ax3.plot(t_h, res.q_pared_W, color="#9467bd", linewidth=1.5, label="q pérdida pared")
    ax3.set_ylabel("Flujo de calor [W]")
    ax3.set_xlabel("Tiempo [h]")
    ax3.legend(fontsize=8, loc="upper right")
    ax3.grid(True, alpha=0.3)

    fig.suptitle(
        f"Motor termodinámico — {prod_id} (status: {res.status})",
        fontsize=11,
    )
    fig.tight_layout()
    return fig
