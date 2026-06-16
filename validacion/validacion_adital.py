"""Validación del modo industrial (gran escala) contra el secador ADITAL.

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
"""

from __future__ import annotations

import math

import numpy as np

from calculos.camara_calc import calcular_camara_cascada
from calculos.cano_maestro_calc import delta_T_cano_maestro, estimar_delta_P_cano_maestro
from calculos.colector_calc import calcular_colector_tipo1
from calculos.motor_calc import (
    densidad_aire,
    estimar_delta_P_camara,
    estimar_delta_P_colector,
    estimar_delta_P_singulares,
)
from calculos.psicrometria import humedad_absoluta
from core import presets
from core.camara import (
    Camara,
    ForzantesAire,
)
from core.colector import CanoMaestro, Colector
from core.motor import Motor

# --------------------------------------------------------------------------
# Constantes del emplazamiento y clima (San Carlos, Salta, ~1800 msnm)
# --------------------------------------------------------------------------
P_AMB_PA = 81_000.0  # ≈ presión a 1800 msnm (ISA)
ALTITUD_M = 1800.0

# Targets de campo (tesis, §3)
T_COL_MEDIODIA_C = 80.0
T_COL_OPERACION_C = 60.0
DT_CANO_C = -3.0
T_CAMARA_MIN_C, T_CAMARA_MAX_C = 40.0, 60.0


# --------------------------------------------------------------------------
# Construcción del secador ADITAL
# --------------------------------------------------------------------------
# Desde S41 el secador ADITAL vive en ``core/presets.py`` (única fuente de
# verdad, compartida con la cascada de tipología de P1). Estos wrappers
# conservan los nombres históricos del script.
def construir_colector_adital() -> Colector:
    """Banco ADITAL: 26 colectores 7.5×0.94 m de paso paralelo (tipo 1)."""
    return presets.colector_gran_escala()


def construir_cano_adital() -> CanoMaestro:
    """Caño maestro ADITAL: 18 m, sección representativa 1×0.90 m, no aislado."""
    return presets.cano_maestro_gran_escala()


def construir_camara_adital() -> Camara:
    """Túnel ADITAL: 18×3×1.85 m aislado, 24 carros × 14 bandejas, 5000 kg."""
    return presets.camara_gran_escala()


# --------------------------------------------------------------------------
# Clima sintético de un día de marzo (Figs. 15–19 de la tesis)
# --------------------------------------------------------------------------
def dia_sintetico_marzo(n_horas: int = 24) -> dict[str, np.ndarray]:
    """Serie horaria sintética que reproduce el día de ensayo de la tesis."""
    h = np.arange(n_horas, dtype=float)
    # T_amb: máx 38 °C a media tarde (~14 h), mín 8 °C de madrugada (~2 h).
    T_amb_C = 23.0 + 15.0 * np.cos((h - 14.0) / 24.0 * 2 * np.pi)
    # Irradiancia POA: coseno diurno, pico 1000 W/m² al mediodía solar (~13 h).
    I_poa = np.maximum(0.0, 1000.0 * np.cos((h - 13.0) / 24.0 * 2 * np.pi))
    I_poa[(h < 7) | (h > 19)] = 0.0
    # Viento: calmo de madrugada (~0.8 m/s), ráfagas de tarde (~5.5 m/s a las 16 h).
    v_viento = 0.8 + 2.4 * (1 + np.cos((h - 16.0) / 24.0 * 2 * np.pi))
    # HR ambiente: 90 % al amanecer (~6 h), ~20 % al mediodía.
    HR = 0.20 + 0.35 * (1 + np.cos((h - 6.0) / 24.0 * 2 * np.pi))
    HR = np.clip(HR, 0.15, 0.90)
    return {"h": h, "T_amb_C": T_amb_C, "I_poa": I_poa, "v_viento": v_viento, "HR": HR}


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_colector(colector: Colector) -> list[tuple]:
    """Check 1 — Salida de colector en dos puntos de operación de la tesis."""
    resultados = []

    # (a) Operación con ventilador, mediodía: I≈900, T_amb≈20 → tesis ~50–60 °C.
    res_op = calcular_colector_tipo1(
        colector,
        T_amb_K=20.0 + 273.15,
        I_g_W_m2=900.0,
        v_viento_ms=2.0,
        P_amb_Pa=P_AMB_PA,
        T_entrada_K=20.0 + 273.15,
    )
    T_op_C = res_op.T_salida_K - 273.15
    resultados.append(("Colector — operación (v=1.8 m/s, I=900, Ta=20)", T_op_C, "°C", 45.0, 70.0))

    # (b) Pico de mediodía a caudal de diseño: I=1000 W/m², T_amb=38 °C
    #     → tesis ~80 °C a la salida del colector.
    res_pico = calcular_colector_tipo1(
        colector,
        T_amb_K=38.0 + 273.15,
        I_g_W_m2=1000.0,
        v_viento_ms=2.0,
        P_amb_Pa=P_AMB_PA,
        T_entrada_K=38.0 + 273.15,
    )
    T_pico_C = res_pico.T_salida_K - 273.15
    resultados.append(
        ("Colector — pico mediodía (v=1.8 m/s, I=1000, Ta=38)", T_pico_C, "°C", 70.0, 90.0)
    )
    return resultados


def check_cano_maestro(colector: Colector) -> list[tuple]:
    """Check 2 — Caída térmica del caño maestro ≈ −3 °C (tesis)."""
    cano = colector.banco.cano_maestro
    # Caudal másico total: 26 colectores a caudal de diseño.
    Q_total = colector.caudal_total_m3_s()
    T_aire_K = T_COL_MEDIODIA_C + 273.15
    m_dot = Q_total * densidad_aire(T_aire_K, P_AMB_PA)

    dT = delta_T_cano_maestro(
        cano,
        T_aire_K=T_aire_K,
        T_amb_K=38.0 + 273.15,
        I_g_W_m2=1000.0,
        m_dot_as_kg_s=m_dot,
        v_viento_ms=2.0,
        P_Pa=P_AMB_PA,
    )
    return [("Caño maestro — ΔT (no aislado, con aporte solar)", dT, "°C", -5.0, 0.0)]


def check_camara(colector: Colector, camara: Camara, clima: dict) -> tuple[list[tuple], dict]:
    """Check 3 — Temperatura de cámara 40–60 °C vía cascada (contexto)."""
    h = clima["h"]
    n = len(h)
    # T_salida del colector hora a hora (forzante de la cámara).
    T_sal_col_K = np.empty(n)
    for i in range(n):
        if clima["I_poa"][i] < 50.0:  # noche: sin colección, T ≈ ambiente
            T_sal_col_K[i] = clima["T_amb_C"][i] + 273.15
            continue
        res = calcular_colector_tipo1(
            colector,
            T_amb_K=clima["T_amb_C"][i] + 273.15,
            I_g_W_m2=clima["I_poa"][i],
            v_viento_ms=clima["v_viento"][i],
            P_amb_Pa=P_AMB_PA,
            T_entrada_K=clima["T_amb_C"][i] + 273.15,
        )
        # Caño maestro: aplicar su ΔT.
        Q_total = colector.caudal_total_m3_s()
        m_dot = Q_total * densidad_aire(res.T_salida_K, P_AMB_PA)
        dT = delta_T_cano_maestro(
            colector.banco.cano_maestro,
            T_aire_K=res.T_salida_K,
            T_amb_K=clima["T_amb_C"][i] + 273.15,
            I_g_W_m2=clima["I_poa"][i],
            m_dot_as_kg_s=m_dot,
            v_viento_ms=clima["v_viento"][i],
            P_Pa=P_AMB_PA,
        )
        T_sal_col_K[i] = res.T_salida_K + dT

    omega_ent = np.array(
        [humedad_absoluta(hr, T + 273.15, P_AMB_PA) for hr, T in zip(clima["HR"], clima["T_amb_C"])]
    )
    m_dot_cam = camara.flujo.caudal_masico_kg_s
    fz = ForzantesAire(
        t_s=h * 3600.0,
        T_ent_K=T_sal_col_K,
        omega_ent=omega_ent,
        m_dot_aire_seco_kg_s=np.full(n, m_dot_cam),
        T_amb_K=clima["T_amb_C"] + 273.15,
        v_viento_ms=clima["v_viento"],
        I_g_W_m2=np.zeros(n),  # techo opaco aislado
        I_g_POA_W_m2=clima["I_poa"],
    )

    T_ref = float(np.mean(T_sal_col_K))
    res_cas = calcular_camara_cascada(
        camara,
        T_operacion_K=T_ref,
        HR_operacion=0.15,
        forzantes_aire=fz,
        T_amb_K=float(np.mean(clima["T_amb_C"]) + 273.15),
        P_Pa=P_AMB_PA,
        n_avances=1,
    )

    # T del aire de cámara durante horas de sol (forzante a la zona caliente).
    sol = clima["I_poa"] > 200.0
    T_cam_sol_C = T_sal_col_K[sol] - 273.15
    T_cam_media = float(np.mean(T_cam_sol_C))

    throughput_kg_dia = (
        res_cas.throughput_fresco_kg_s * 86400.0 if res_cas.throughput_fresco_kg_s else None
    )
    contexto = {
        "T_entrada_camara_sol_C": (float(T_cam_sol_C.min()), float(T_cam_sol_C.max())),
        "throughput_kg_dia": throughput_kg_dia,
        "dias_para_5000kg": (5000.0 / throughput_kg_dia if throughput_kg_dia else None),
    }
    checks = [
        ("Cámara — T entrada media (horas de sol)", T_cam_media, "°C", 40.0, 65.0),
    ]
    return checks, contexto


def check_perdidas_carga(colector: Colector, camara: Camara) -> tuple[list[tuple], dict]:
    """Check 4 (sanidad) — ΔP del sistema y potencia del ventilador en orden de
    magnitud plausible para un secador de esta escala.

    NO es calibración contra ADITAL: el ventilador real es de 4 HP (nameplate,
    sobredimensionado). Se verifica que el modelo GENERAL (ASHRAE/Colebrook +
    modelo combinado de producto) caiga en un rango razonable, no que reproduzca
    un punto de operación medido.
    """
    Q = colector.caudal_total_m3_s()
    T_op_K = T_COL_OPERACION_C + 273.15

    dP_col = estimar_delta_P_colector(colector, T_K=T_op_K, P_Pa=P_AMB_PA)
    dP_cano = estimar_delta_P_cano_maestro(
        colector.banco.cano_maestro, Q, T_K=T_op_K, P_Pa=P_AMB_PA
    )["total"]
    dP_cam = estimar_delta_P_camara(camara, T_K=T_op_K, P_Pa=P_AMB_PA)
    # Velocidad en el acople cuadrado→circular al ventilador (ø 0.45 m, tesis).
    v_ducto = Q / (math.pi * 0.45**2 / 4.0)
    sing = estimar_delta_P_singulares(
        Q_vol_m3_s=Q,
        v_ducto_m_s=v_ducto,
        n_paralelo=colector.banco.n_paralelo,
        n_codos=3,
        T_K=T_op_K,
        P_Pa=P_AMB_PA,
    )
    dP_total = dP_col + dP_cano + dP_cam + sing["total"]

    mot = Motor(
        caudal_volumetrico_m3_s=Q,
        delta_P_colector_Pa=dP_col,
        delta_P_camara_Pa=dP_cam,
        delta_P_ductos_Pa=dP_cano,
        delta_P_singulares_Pa=sing["total"],
        eficiencia_ventilador=0.55,
        eficiencia_motor=0.85,
    )
    P_HP = mot.potencia_electrica_W / 746.0

    contexto = {
        "dP_total_Pa": dP_total,
        "P_elec_W": mot.potencia_electrica_W,
        "P_HP": P_HP,
        "v_ducto_ms": v_ducto,
        "desglose": {
            "colector": dP_col,
            "cano": dP_cano,
            "camara": dP_cam,
            "singulares": sing["total"],
        },
    }
    checks = [
        ("ΔP total del sistema (orden de magnitud)", dP_total, "Pa", 200.0, 1500.0),
        ("Potencia del ventilador (vs 4 HP nameplate)", P_HP, "HP", 1.5, 6.0),
        ("ΔP cámara > 0 (producto pesa en el túnel)", dP_cam, "Pa", 1.0, 500.0),
    ]
    return checks, contexto


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    print("=" * 78)
    print("  VALIDACIÓN — Modo industrial (gran escala) vs secador ADITAL")
    print("  Referencia: Tesis doctoral G. Durán, Cap. 3 (San Carlos, Salta, 2009)")
    print("=" * 78)

    colector = construir_colector_adital()
    camara = construir_camara_adital()
    clima = dia_sintetico_marzo()

    # ΔP del caño maestro (contexto hidráulico).
    dP = estimar_delta_P_cano_maestro(
        colector.banco.cano_maestro, colector.caudal_total_m3_s(), T_K=323.15, P_Pa=P_AMB_PA
    )

    todos: list[tuple] = []
    todos += check_colector(colector)
    todos += check_cano_maestro(colector)
    checks_cam, contexto = check_camara(colector, camara, clima)
    todos += checks_cam
    checks_dp, ctx_dp = check_perdidas_carga(colector, camara)
    todos += checks_dp

    print(
        f"\n  Caudal total del banco: {colector.caudal_total_m3_s():.2f} m³/s "
        f"({colector.caudal_total_m3_s() * 3600:.0f} m³/h)"
    )
    print(f"  Área de colección: {colector.area_total_m2():.0f} m² (tesis: 195 m²)")
    print(f"  ΔP caño maestro: {dP['total']:.1f} Pa " f"(v_troncal {dP['v_troncal_ms']:.1f} m/s)")
    dg = ctx_dp["desglose"]
    print(
        f"  ΔP sistema: {ctx_dp['dP_total_Pa']:.0f} Pa "
        f"(col {dg['colector']:.0f} + caño {dg['cano']:.0f} + cámara {dg['camara']:.0f} "
        f"+ sing {dg['singulares']:.0f}) → ventilador {ctx_dp['P_HP']:.1f} HP "
        f"(nameplate ADITAL: 4 HP, sobredimensionado)"
    )

    print("\n  " + "-" * 74)
    print(f"  {'Magnitud':<48}{'Modelo':>10}{'Rango OK':>14}")
    print("  " + "-" * 74)
    n_ok = 0
    for label, valor, unidad, lo, hi in todos:
        ok = lo <= valor <= hi
        n_ok += ok
        marca = "✓" if ok else "✗"
        print(f"  {marca} {label:<46}{valor:>8.1f} {unidad}{f'[{lo:.0f},{hi:.0f}]':>14}")
    print("  " + "-" * 74)
    print(f"  {n_ok}/{len(todos)} validaciones térmicas dentro de rango.")

    print("\n  Contexto (capacidad de campaña):")
    te = contexto["T_entrada_camara_sol_C"]
    print(
        f"    T entrada cámara (sol): {te[0]:.1f}–{te[1]:.1f} °C  "
        f"(tesis cámara: {T_CAMARA_MIN_C:.0f}–{T_CAMARA_MAX_C:.0f} °C)"
    )
    tp = contexto["throughput_kg_dia"]
    dias = contexto["dias_para_5000kg"]
    if tp:
        print(f"    Throughput nominal: {tp:.0f} kg/día fresco " f"(24 carros, cadencia 5 h)")
        print(
            f"    → 5000 kg en {dias:.1f} días de operación " f"(tesis: 5000 kg en 4–5 días de sol)"
        )
    print("=" * 78)


if __name__ == "__main__":
    main()
