"""
probe_motor_C_yacon.py
======================
Sonda exploratoria del motor termodinámico (TD) con yacón.

Tras la consolidación del motor (2026-05-16) se eliminó el antiguo "Motor C
cinético dinámico" (camara_calc_dinamico). El motor TD difusivo lo absorbió,
por lo que esta sonda corre ahora `simular_secado` vía `calcular_camara` con
forzantes sintéticas día/noche, y reporta en qué rango de (T_op, HR, masa,
X_obj) el motor converge a X_obj dentro del horizonte.

Diferencia clave con la sonda anterior: el motor TD usa K_m difusivo + GAB
para el yacón (NO usa la cinética Lewis/Page Shi 2013 que era central en el
motor cinético borrado). Por eso los rangos donde converge pueden diferir
significativamente respecto al reporte histórico de S26.
"""

from __future__ import annotations

from calculos.balance_global import construir_serie_sintetica_dia_tipo
from calculos.camara_calc import calcular_camara
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

# Geometría fija (igual al script principal)
LARGO_M, ANCHO_M, ALTO_M = 1.2, 0.8, 1.5
N_BANDEJAS, AREA_BAND = 5, 0.50
ESP_CAPA, SEP_BAND = 0.020, 0.15
PARED_AISLADA = ParedCamara(
    capas=[
        CapaPared(material_id="lana_vidrio_media", espesor_m=0.080, catalogo="aislantes"),
    ]
)  # R = 0.080/0.040 = 2.0 m²K/W → U_cond = 0.5 W/(m²·K)
M_DOT = 0.060
P_PA = 87000.0
T_AMB_K = 298.15
V_VIENTO_MS = 2.0

# Producto fijo — yacón
X_0 = 9.0


def _camara(masa_kg: float, X_obj: float) -> Camara:
    return Camara(
        geometria=GeometriaCamara(largo_m=LARGO_M, ancho_m=ANCHO_M, alto_m=ALTO_M),
        construccion=ConstruccionCamara(pared=PARED_AISLADA),
        bandejas=ConfiguracionBandejas(
            n_bandejas=N_BANDEJAS,
            area_bandeja_m2=AREA_BAND,
            espesor_capa_m=ESP_CAPA,
            separacion_entre_bandejas_m=SEP_BAND,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=M_DOT),
        carga_producto=CargaProducto(
            producto_id="yacon",
            masa_total_kg=masa_kg,
            humedad_inicial_X=X_0,
            humedad_objetivo_X=X_obj,
            modelo_capa_fina="page",
        ),
        modo_calculo="termodinamico",
    )


def correr_TD(T_op_C, HR, masa_kg, X_obj, horizonte_h=96, n_dias=4):
    """Corre el motor TD con forzantes sintéticas día/noche."""
    T_op_K = T_op_C + 273.15
    omega_amb = humedad_absoluta(HR, T_op_K, P_PA)
    fz = construir_serie_sintetica_dia_tipo(
        T_sal_col_promedio_K=T_op_K,
        T_sal_col_amplitud_K=15.0,
        omega_amb=omega_amb,
        m_dot_aire_seco_kg_s=M_DOT,
        T_amb_promedio_K=T_AMB_K,
        T_amb_amplitud_K=5.0,
        v_viento_ms=V_VIENTO_MS,
        n_dias=n_dias,
    )
    try:
        return calcular_camara(
            _camara(masa_kg, X_obj),
            T_operacion_K=T_op_K,
            HR_operacion=HR,
            T_amb_K=T_AMB_K,
            P_Pa=P_PA,
            t_max_s=min(float(fz.t_s[-1]), horizonte_h * 3600.0),
            forzantes_aire=fz,
        )
    except Exception as e:
        return f"EXCEPTION: {type(e).__name__}: {e}"


def main():
    print(
        f"{'T_op':>5} {'HR':>5} {'masa':>5} {'X_obj':>6} {'conv':>5} "
        f"{'t_h':>7} {'X_fin':>7} {'h_clip':>6} {'adv':>5} status"
    )
    print("-" * 85)

    grid = [
        # (T_op_C, HR, masa_kg, X_obj)
        (25, 0.15, 5.0, 0.5),
        (25, 0.15, 1.0, 0.5),
        (25, 0.30, 5.0, 0.5),
        (40, 0.15, 5.0, 0.5),
        (45, 0.15, 5.0, 0.5),
        (50, 0.15, 5.0, 0.5),
        (60, 0.15, 5.0, 0.5),
        (60, 0.15, 1.0, 0.5),
        (60, 0.15, 5.0, 2.0),
        (60, 0.30, 5.0, 0.5),
    ]

    for T_op, HR, masa, X_obj in grid:
        res = correr_TD(T_op, HR, masa, X_obj)
        if isinstance(res, str):
            print(f"{T_op:>5} {HR:>5.2f} {masa:>5.1f} {X_obj:>6.2f}   ---   {res}")
            continue
        conv = "SI" if res.status == "X_obj_alcanzado" else "NO"
        t_h = (res.t_secado_s / 3600.0) if res.t_secado_s else float("nan")
        X_fin = float(res.X_prod_kg_kg[-1]) if len(res.X_prod_kg_kg) else float("nan")
        h_clip = res.horas_clipeo_nocturno_s / 3600.0
        n_adv = len(res.advertencias)
        status = res.status
        print(
            f"{T_op:>5} {HR:>5.2f} {masa:>5.1f} {X_obj:>6.2f} "
            f"{conv:>5} {t_h:>7.2f} {X_fin:>7.3f} {h_clip:>6.1f} {n_adv:>5} {status}"
        )


if __name__ == "__main__":
    main()
