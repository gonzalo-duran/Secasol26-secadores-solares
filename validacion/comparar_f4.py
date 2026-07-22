"""Comparativa F4 con/sin término convectivo cara interna fondo ↔ fluido ci.

Corre los colectores Tipo 2, 3 y 4 con un caso operativo típico (vidrio +
selectiva, T_amb=20 °C, I=800 W/m², viento 2 m/s) con el F4 corregido
(incluye conv_ci_int) y luego monkey-patchea los `_sistema_nodo_*` para
reproducir el comportamiento previo (F4 sin conv_ci_int). Imprime una
tabla con η, T_salida y T_int para cuantificar el impacto.

Uso:
    .venv/bin/python -m validacion.comparar_f4
"""

from __future__ import annotations

from calculos import colector_tipos234_calc as mod
from calculos.colector_tipos234_calc import (
    calcular_colector_tipo2,
    calcular_colector_tipo3,
    calcular_colector_tipo4,
)
from core.colector import Colector

CASO = dict(
    T_amb_K=293.15,  # 20 °C
    I_g_W_m2=800.0,
    v_viento_ms=2.0,
    P_amb_Pa=101325.0,
    T_entrada_K=293.15,  # 20 °C
)
V_DISENO_MS = 0.5  # canal activo


def _wrap_viejo_tipo2(orig):
    """Wrap que devuelve F4 SIN el término conv_ci_int (modelo previo)."""

    def wrapper(
        vars_,
        T_f_cs_K,
        T_f_ci_K,
        T_amb_K,
        T_cie_K,
        I_g_W_m2,
        h_wind,
        h_int_cs,
        h_int_ci,
        tau_cub,
        alfa_abs,
        em_cub,
        em_abs,
        em_fondo,
        k_cub,
        esp_cub,
        k_ais,
        esp_ais,
        W_m,
        W_abs_m,
        n_cubiertas=1,
        esp_cav_m=0.025,
        pendiente_deg=30.0,
        P_amb_Pa=101325.0,
    ):
        F = orig(
            vars_,
            T_f_cs_K,
            T_f_ci_K,
            T_amb_K,
            T_cie_K,
            I_g_W_m2,
            h_wind,
            h_int_cs,
            h_int_ci,
            tau_cub,
            alfa_abs,
            em_cub,
            em_abs,
            em_fondo,
            k_cub,
            esp_cub,
            k_ais,
            esp_ais,
            W_m,
            W_abs_m,
            n_cubiertas,
            esp_cav_m,
            pendiente_deg,
            P_amb_Pa,
        )
        T_int = vars_[3]
        conv_ci_int = h_int_ci * (T_int - T_f_ci_K) * W_abs_m
        F_old = F.copy()
        F_old[3] = F[3] + conv_ci_int  # deshace el aporte agregado
        return F_old

    return wrapper


def _wrap_viejo_tipos34(orig):
    def wrapper(
        vars_,
        T_f_activo_K,
        T_f_estanco_K,
        T_amb_K,
        T_cie_K,
        I_g_W_m2,
        h_wind,
        h_int_activo,
        h_int_estanco,
        k_cub,
        esp_cub,
        em_cub,
        k_ais,
        esp_ais,
        em_abs,
        em_fondo,
        tau_cub,
        alfa_abs,
        W_m,
        W_abs_m,
        canal_activo,
        n_cubiertas=1,
        esp_cav_m=0.025,
        pendiente_deg=30.0,
        P_amb_Pa=101325.0,
    ):
        F = orig(
            vars_,
            T_f_activo_K,
            T_f_estanco_K,
            T_amb_K,
            T_cie_K,
            I_g_W_m2,
            h_wind,
            h_int_activo,
            h_int_estanco,
            k_cub,
            esp_cub,
            em_cub,
            k_ais,
            esp_ais,
            em_abs,
            em_fondo,
            tau_cub,
            alfa_abs,
            W_m,
            W_abs_m,
            canal_activo,
            n_cubiertas,
            esp_cav_m,
            pendiente_deg,
            P_amb_Pa,
        )
        T_int = vars_[3]
        if canal_activo == "superior":  # Tipo 4: ci estanco
            T_f_ci = T_f_estanco_K
            h_ci = h_int_estanco
        else:  # Tipo 3: ci activo
            T_f_ci = T_f_activo_K
            h_ci = h_int_activo
        conv_ci_int = h_ci * (T_int - T_f_ci) * W_abs_m
        F_old = F.copy()
        F_old[3] = F[3] + conv_ci_int
        return F_old

    return wrapper


def correr_tipos(col: Colector) -> dict:
    """Corre Tipo 2, 3 y 4 con el módulo en su estado actual."""
    r2 = calcular_colector_tipo2(
        col,
        CASO["T_amb_K"],
        CASO["I_g_W_m2"],
        CASO["v_viento_ms"],
        CASO["P_amb_Pa"],
        CASO["T_entrada_K"],
        v_diseno_cs_ms=V_DISENO_MS,
        v_diseno_ci_ms=V_DISENO_MS,
    )
    r3 = calcular_colector_tipo3(
        col,
        CASO["T_amb_K"],
        CASO["I_g_W_m2"],
        CASO["v_viento_ms"],
        CASO["P_amb_Pa"],
        CASO["T_entrada_K"],
    )
    r4 = calcular_colector_tipo4(
        col,
        CASO["T_amb_K"],
        CASO["I_g_W_m2"],
        CASO["v_viento_ms"],
        CASO["P_amb_Pa"],
        CASO["T_entrada_K"],
    )
    return {"tipo2": r2, "tipo3": r3, "tipo4": r4}


def _T_int_final(r) -> float:
    """Extrae T_int en el último nodo del perfil."""
    return float(r.T_int_K[-1])


def _T_salida(r) -> float:
    # Tipo 2 expone T_salida_mezcla_K, Tipos 3/4 exponen T_salida_K
    return float(getattr(r, "T_salida_mezcla_K", None) or r.T_salida_K)


def main() -> None:
    col = Colector()

    print("=" * 78)
    print(" Comparativa F4: con conv_ci_int (fix S30) vs sin conv_ci_int (modelo previo)")
    print(f" Caso: T_amb=20°C, I=800 W/m², v_viento=2 m/s, v_diseño={V_DISENO_MS} m/s")
    print("=" * 78)

    # 1) Estado actual (con fix)
    res_nuevo = correr_tipos(col)

    # 2) Monkey-patch para reproducir el modelo previo
    orig_t2 = mod._sistema_nodo_tipo2
    orig_t34 = mod._sistema_nodo_tipos34
    mod._sistema_nodo_tipo2 = _wrap_viejo_tipo2(orig_t2)
    mod._sistema_nodo_tipos34 = _wrap_viejo_tipos34(orig_t34)
    try:
        res_viejo = correr_tipos(col)
    finally:
        mod._sistema_nodo_tipo2 = orig_t2
        mod._sistema_nodo_tipos34 = orig_t34

    # 3) Tabla
    print(
        f"\n{'Tipo':<6} {'η_viejo':>9} {'η_nuevo':>9} {'Δη [pp]':>10} "
        f"{'Tsal_viejo':>11} {'Tsal_nuevo':>11} {'ΔTsal':>8} "
        f"{'Tint_viejo':>11} {'Tint_nuevo':>11} {'ΔTint':>8}"
    )
    print("-" * 110)
    for tipo in ("tipo2", "tipo3", "tipo4"):
        rv, rn = res_viejo[tipo], res_nuevo[tipo]
        eta_v, eta_n = float(rv.eta_termica), float(rn.eta_termica)
        ts_v, ts_n = _T_salida(rv), _T_salida(rn)
        ti_v, ti_n = _T_int_final(rv), _T_int_final(rn)
        print(
            f"{tipo:<6} {eta_v:>9.4f} {eta_n:>9.4f} {100*(eta_n-eta_v):>+10.2f} "
            f"{ts_v-273.15:>10.2f}° {ts_n-273.15:>10.2f}° {ts_n-ts_v:>+7.2f} "
            f"{ti_v-273.15:>10.2f}° {ti_n-273.15:>10.2f}° {ti_n-ti_v:>+7.2f}"
        )

    print("\nNotas:")
    print(" - Δη en puntos porcentuales (pp).")
    print(" - ΔTsal y ΔTint en K (= °C de diferencia).")
    print(" - 'viejo' = F4 sin conv_ci_int; 'nuevo' = F4 con conv_ci_int (fix S30).")


if __name__ == "__main__":
    main()
