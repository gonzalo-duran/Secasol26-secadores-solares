"""
validacion_cruzada_yacon.py
============================
Validación cruzada de los motores de secado disponibles tras la consolidación
del motor termodinámico (S26/2026-05-16).

Compara para condiciones de contorno idénticas:
  - Motor A: capa fina estático (calcular_tiempo_secado_estatico) — modelo
    algebraico empírico, no depende de la masa del producto.
  - Motor B: termodinámico TD con forzantes constantes — balance acoplado
    con pared 3-nodos, evaporación difusiva, condiciones de aire fijas.
  - Motor C: termodinámico TD con forzantes sintéticas día/noche —
    mismo motor B pero con T_sal_col(t) y T_amb(t) senoidales (pico a
    las 12 h, ±15 K T_col, ±5 K T_amb), incluyendo política B
    anti-rehumectación nocturna.

NOTA: El antiguo Motor C (cinético Lewis/Page con forzantes,
camara_calc_dinamico.py) se eliminó al consolidar el motor termodinámico.
El presente Motor C usa el mismo solver físico que B pero alimentado por
una serie senoidal — la diferencia entre B y C aísla el efecto del ciclo
diurno sobre el tiempo total de secado.

Ejecutar desde la raíz del proyecto:
    .venv/bin/python validacion/validacion_cruzada_yacon.py

Salida: tabla en consola + archivo validacion/validacion_cruzada_yacon.md
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Condiciones de contorno — mismas para los tres motores
# ---------------------------------------------------------------------------

# Condiciones del aire (representativas de secado solar en Salta, día típico)
T_OP_K = 333.15  # 60 °C — temperatura de operación en cámara
HR_OP = 0.15  # 15 % HR — aire caliente y seco
T_AMB_K = 298.15  # 25 °C — temperatura ambiente exterior
P_PA = 87000.0  # Pa — presión atmosférica Salta (~1187 m snm)

# Geometría de la cámara (armario estándar de referencia)
LARGO_M = 1.2
ANCHO_M = 0.8
ALTO_M = 1.5
N_BANDEJAS = 5
AREA_BAND = 0.50  # m² por bandeja
ESP_CAPA = 0.020  # m espesor de capa de producto
SEP_BAND = 0.15  # m separación entre bandejas
U_MUROS = 0.5  # W/m²K conductancia muros

# Flujo de aire
M_DOT_KG_S = 0.060  # kg/s aire seco

# Producto — yacón
MASA_KG = 5.0  # kg totales (fresco)
X_0 = 9.0  # kg agua / kg ms  (90 % bh)
X_OBJ = 0.50  # kg agua / kg ms  (~33 % bh — objetivo secado solar)

# Horizonte de simulación
HORIZONTE_H = 96  # horas (4 días)
N_DIAS_C = 4  # Motor C: cuántos días replicar el sintético

# Amplitudes del día sintético (Motor C)
T_SAL_COL_AMP_K = 15.0  # ±15 K en T_sal_col (pico al mediodía)
T_AMB_AMP_K = 5.0  # ±5 K en T_amb
V_VIENTO_MS = 2.0  # constante en el sintético

# ---------------------------------------------------------------------------
# Imports del proyecto
# ---------------------------------------------------------------------------
from calculos.balance_global import construir_serie_sintetica_dia_tipo
from calculos.camara_calc import calcular_camara, calcular_tiempo_secado_estatico
from calculos.psicrometria import humedad_absoluta
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    GeometriaCamara,
    ParedCamara,
)

PARED_AISLADA = ParedCamara(
    capas=[
        CapaPared(material_id="lana_vidrio_media", espesor_m=0.080, catalogo="aislantes"),
    ]
)  # U_cond ≈ 0.5 W/(m²·K)

# ---------------------------------------------------------------------------
# Helper: construir objeto Camara yacón
# ---------------------------------------------------------------------------


def _camara_yacon(modo: str) -> Camara:
    return Camara(
        geometria=GeometriaCamara(largo_m=LARGO_M, ancho_m=ANCHO_M, alto_m=ALTO_M),
        construccion=ConstruccionCamara(pared=PARED_AISLADA),
        bandejas=ConfiguracionBandejas(
            n_bandejas=N_BANDEJAS,
            area_bandeja_m2=AREA_BAND,
            espesor_capa_m=ESP_CAPA,
            separacion_entre_bandejas_m=SEP_BAND,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=M_DOT_KG_S),
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=MASA_KG,
            humedad_inicial_X=X_0,
            humedad_objetivo_X=X_OBJ,
            modelo_capa_fina="page",
        ),
        modo_calculo=modo,
    )


# ---------------------------------------------------------------------------
# Motor A — capa fina estático
# ---------------------------------------------------------------------------


def correr_motor_A():
    print("  [A] Motor capa fina estático...")
    cam = _camara_yacon("capa_fina")
    return calcular_tiempo_secado_estatico(cam, T_OP_K, HR_OP, P_Pa=P_PA)


# ---------------------------------------------------------------------------
# Motor B — termodinámico TD con forzantes constantes
# ---------------------------------------------------------------------------


def correr_motor_B():
    print("  [B] Motor termodinámico — forzantes constantes...")
    cam = _camara_yacon("termodinamico")
    return calcular_camara(
        cam,
        T_operacion_K=T_OP_K,
        HR_operacion=HR_OP,
        T_amb_K=T_AMB_K,
        P_Pa=P_PA,
        t_max_s=HORIZONTE_H * 3600.0,
        # forzantes_aire=None  → wire-up arma degeneradas (constantes)
    )


# ---------------------------------------------------------------------------
# Motor C — termodinámico TD con forzantes sintéticas día/noche
# ---------------------------------------------------------------------------


def correr_motor_C():
    print("  [C] Motor termodinámico — forzantes sintéticas día/noche...")
    cam = _camara_yacon("termodinamico")
    omega_amb = humedad_absoluta(HR_OP, T_OP_K, P_PA)
    fz = construir_serie_sintetica_dia_tipo(
        T_sal_col_promedio_K=T_OP_K,
        T_sal_col_amplitud_K=T_SAL_COL_AMP_K,
        omega_amb=omega_amb,
        m_dot_aire_seco_kg_s=M_DOT_KG_S,
        T_amb_promedio_K=T_AMB_K,
        T_amb_amplitud_K=T_AMB_AMP_K,
        v_viento_ms=V_VIENTO_MS,
        n_dias=N_DIAS_C,
    )
    return calcular_camara(
        cam,
        T_operacion_K=T_OP_K,
        HR_operacion=HR_OP,
        T_amb_K=T_AMB_K,
        P_Pa=P_PA,
        t_max_s=float(fz.t_s[-1]),
        forzantes_aire=fz,
    )


# ---------------------------------------------------------------------------
# Extraer métricas comparables
# ---------------------------------------------------------------------------


def extraer_metricas(res_A, res_B, res_C) -> dict:
    """Devuelve dict con métricas clave de cada motor."""
    # --- Motor A ---
    t_A = res_A.t_secado_s
    X_eq_A = res_A.X_eq_kg_kg
    adv_A = list(res_A.advertencias)

    # --- Motor B (termodinámico, constantes) ---
    t_B = res_B.t_secado_s
    masa_evap_B = res_B.masa_evaporada_total_kg
    T_prod_final_B = float(res_B.T_prod_K[-1]) if len(res_B.T_prod_K) else None
    T_max_B = res_B.T_max_alcanzada_K
    horas_clipeo_B = res_B.horas_clipeo_nocturno_s / 3600.0
    adv_B = list(res_B.advertencias)

    # --- Motor C (termodinámico, sintético día/noche) ---
    t_C = res_C.t_secado_s
    masa_evap_C = res_C.masa_evaporada_total_kg
    T_prod_final_C = float(res_C.T_prod_K[-1]) if len(res_C.T_prod_K) else None
    T_max_C = res_C.T_max_alcanzada_K
    horas_clipeo_C = res_C.horas_clipeo_nocturno_s / 3600.0
    horas_HR_alta_C = res_C.horas_HR_alta_s / 3600.0
    adv_C = list(res_C.advertencias)

    return dict(
        # Motor A
        t_A_h=t_A / 3600 if t_A else None,
        X_eq_A=X_eq_A,
        adv_A=adv_A,
        # Motor B
        t_B_h=t_B / 3600 if t_B else None,
        status_B=res_B.status,
        masa_evap_B=masa_evap_B,
        T_prod_fin_B=T_prod_final_B,
        T_max_B=T_max_B,
        horas_clipeo_B=horas_clipeo_B,
        adv_B=adv_B,
        # Motor C
        t_C_h=t_C / 3600 if t_C else None,
        status_C=res_C.status,
        masa_evap_C=masa_evap_C,
        T_prod_fin_C=T_prod_final_C,
        T_max_C=T_max_C,
        horas_clipeo_C=horas_clipeo_C,
        horas_HR_alta_C=horas_HR_alta_C,
        adv_C=adv_C,
    )


# ---------------------------------------------------------------------------
# Formatear reporte
# ---------------------------------------------------------------------------


def formatear_reporte(m: dict) -> str:
    def fh(v):
        return f"{v:.2f} h" if v is not None else "NO CONVERGIÓ"

    def fc(v):
        return f"{v:.3f} kg/kg ms" if v is not None else "—"

    diff_BA = (m["t_B_h"] - m["t_A_h"]) / m["t_A_h"] * 100 if m["t_B_h"] and m["t_A_h"] else None
    diff_CA = (m["t_C_h"] - m["t_A_h"]) / m["t_A_h"] * 100 if m["t_C_h"] and m["t_A_h"] else None
    diff_CB = (m["t_C_h"] - m["t_B_h"]) / m["t_B_h"] * 100 if m["t_C_h"] and m["t_B_h"] else None

    def fp(v):
        return f"{v:+.1f}%" if v is not None else "—"

    adv_A_str = "\n      ".join(m["adv_A"]) if m["adv_A"] else "(ninguna)"
    adv_B_str = "\n      ".join(m["adv_B"]) if m["adv_B"] else "(ninguna)"
    adv_C_str = "\n      ".join(m["adv_C"]) if m["adv_C"] else "(ninguna)"

    lines = [
        "=" * 70,
        "VALIDACIÓN CRUZADA — YACÓN (post-consolidación motor termodinámico)",
        f"Condiciones: T_op={T_OP_K-273.15:.0f}°C, HR={HR_OP:.0%}, "
        f"ṁ={M_DOT_KG_S:.3f} kg/s, P={P_PA:.0f} Pa",
        f"Producto: X_0={X_0} → X_obj={X_OBJ} kg/kg ms, masa={MASA_KG} kg",
        f"Geometría: {LARGO_M}×{ANCHO_M}×{ALTO_M} m, {N_BANDEJAS} bandejas×{AREA_BAND} m²",
        "=" * 70,
        "",
        "┌─────────────────────────────────────┬──────────────────┬───────────────────┐",
        "│  Motor                              │  t_secado        │  Δ vs Motor A     │",
        "├─────────────────────────────────────┼──────────────────┼───────────────────┤",
        f"│  A — Capa fina estático             │  {fh(m['t_A_h']):16s}│  (referencia)     │",
        f"│  B — TD forzantes constantes        │  {fh(m['t_B_h']):16s}│  {fp(diff_BA):17s}│",
        f"│  C — TD día sintético (senoidal)    │  {fh(m['t_C_h']):16s}│  {fp(diff_CA):17s}│",
        "└─────────────────────────────────────┴──────────────────┴───────────────────┘",
        "",
        f"  Δ C vs B (efecto del ciclo día/noche): {fp(diff_CB)}",
        "",
        "DETALLES MOTOR B (termodinámico, constantes):",
        f"  status                : {m['status_B']}",
        f"  masa evaporada        : {m['masa_evap_B']:.3f} kg",
        (
            f"  T_prod final          : {m['T_prod_fin_B']-273.15:.1f} °C"
            if m["T_prod_fin_B"]
            else "  T_prod final          : —"
        ),
        f"  T_max alcanzada       : {m['T_max_B']-273.15:.1f} °C",
        f"  horas clipeo (pol. B) : {m['horas_clipeo_B']:.1f} h",
        "",
        "DETALLES MOTOR C (termodinámico, día sintético):",
        f"  status                : {m['status_C']}",
        f"  masa evaporada        : {m['masa_evap_C']:.3f} kg",
        (
            f"  T_prod final          : {m['T_prod_fin_C']-273.15:.1f} °C"
            if m["T_prod_fin_C"]
            else "  T_prod final          : —"
        ),
        f"  T_max alcanzada       : {m['T_max_C']-273.15:.1f} °C",
        f"  horas clipeo (pol. B) : {m['horas_clipeo_C']:.1f} h",
        f"  horas HR > 95 %       : {m['horas_HR_alta_C']:.1f} h",
        "",
        "DETALLES MOTOR A (capa fina estático):",
        f"  X_eq usado            : {fc(m['X_eq_A'])}",
        "",
        "ADVERTENCIAS:",
        f"  Motor A: {adv_A_str}",
        f"  Motor B: {adv_B_str}",
        f"  Motor C: {adv_C_str}",
        "",
        "INTERPRETACIÓN:",
    ]

    if m["t_A_h"] and m["t_B_h"]:
        if abs(diff_BA or 0) > 30:
            lines.append(
                f"  Motor A vs B: divergencia del {diff_BA:+.0f}% — el modelo "
                "estático no captura el cuello de botella del aire (efecto masa)."
            )
        else:
            lines.append(
                f"  Motor A vs B: divergencia del {diff_BA:+.0f}% — coherencia "
                "aceptable; aire poco saturado, masa moderada."
            )
    if m["t_B_h"] and m["t_C_h"]:
        if abs(diff_CB or 0) > 15:
            lines.append(
                f"  Motor C vs B: divergencia del {diff_CB:+.0f}% — el ciclo día/noche "
                "tiene impacto significativo (Política B anti-rehumectación activa)."
            )
        else:
            lines.append(
                f"  Motor C vs B: divergencia del {diff_CB:+.0f}% — el ciclo día/noche "
                "no domina el balance global."
            )

    lines += [
        "",
        "LIMITACIONES Y NOTAS:",
        "  - Motor A: T fija, sin dinámica de masa ni T_prod; referencia rápida.",
        "  - Motor B: aire de entrada constante. cp(X) variable y pared 3-nodos.",
        "  - Motor C: senoidal sintética; n_dias replica el mismo día tipo.",
        "    NO usa clima NASA POWER real (eso es modo 'real' en la UI).",
        "  - Yacón sin Arrhenius en el catálogo → el motor termodinámico usa K_m",
        "    difusivo + GAB de Marques 2022, no la cinética Lewis/Page.",
        "  - Tras la consolidación del motor (2026-05-16) se eliminó el antiguo",
        "    'Motor C cinético dinámico'. La comparación útil que queda es A→B (efecto",
        "    masa y balance acoplado) y B→C (efecto del ciclo día/noche).",
        "",
        "=" * 70,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("\nValidación cruzada — Yacón (motor termodinámico consolidado)")
    print("-" * 60)

    try:
        res_A = correr_motor_A()
    except Exception as e:
        print(f"  ERROR Motor A: {e}")
        res_A = None

    try:
        res_B = correr_motor_B()
    except Exception as e:
        print(f"  ERROR Motor B: {e}")
        res_B = None

    try:
        res_C = correr_motor_C()
    except Exception as e:
        print(f"  ERROR Motor C: {e}")
        res_C = None

    if res_A is None or res_B is None or res_C is None:
        print("\nAl menos un motor falló. Revisar errores arriba.")
        return

    print()
    m = extraer_metricas(res_A, res_B, res_C)
    reporte = formatear_reporte(m)
    print(reporte)

    out = Path(__file__).parent / "validacion_cruzada_yacon.md"
    out.write_text(
        "```\n" + reporte + "\n```\n\n"
        "## Parámetros de entrada\n\n"
        f"| Parámetro | Valor |\n|---|---|\n"
        f"| T_operacion | {T_OP_K-273.15:.0f} °C |\n"
        f"| HR_operacion | {HR_OP:.0%} |\n"
        f"| T_ambiente | {T_AMB_K-273.15:.0f} °C |\n"
        f"| P_atm | {P_PA:.0f} Pa |\n"
        f"| ṁ_aire | {M_DOT_KG_S:.3f} kg/s |\n"
        f"| X_0 | {X_0} kg/kg ms |\n"
        f"| X_obj | {X_OBJ} kg/kg ms |\n"
        f"| masa | {MASA_KG} kg |\n"
        f"| Motor C — amplitud T_sal_col | ±{T_SAL_COL_AMP_K:.1f} K |\n"
        f"| Motor C — amplitud T_amb | ±{T_AMB_AMP_K:.1f} K |\n"
        f"| Motor C — n_dias | {N_DIAS_C} |\n",
        encoding="utf-8",
    )
    print(f"\nReporte guardado en: {out.resolve()}")


if __name__ == "__main__":
    main()
