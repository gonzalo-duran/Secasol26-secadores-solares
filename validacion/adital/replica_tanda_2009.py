"""Réplica de la tanda del 21/03/2009 en ADITAL: secado de pimiento (S70, Fase 3).

Condorí, Durán, Vargas & Echazú (2009), AVERMA 13:02.35 — "Secador solar híbrido.
Primeros ensayos". Primer día de carga de una tanda (~2 t de pimiento para
pimentón **en vaina entera**), ventilador desde la tarde; solo energía solar.

Medido (targets, orden de magnitud — Fase 3 no calibra):
- Muestra seca "a criterio del productor" en ~30 h de sol (2.5 días), Fig. 14:
  140 g → 40 g en 4 días (15:00 y 18:00 de cada día).
- HR de la cámara ≈ 10 % con ventilador, y **la salida casi igual a la entrada**
  (Fig. 11): el aire sale sin aprovechar su potencial de secado.
- Cámara 40–60 °C unas 8 h; cerca de las bandejas, 60 → 40 °C (Fig. 10).

Supuestos (no informados):
- X0 ≈ 3: la muestra pasa de 140 g a 40 g seca; con ~12 % b.h. final, m_s ≈ 35 g.
- Clima: el día sintético de marzo de ``validacion_adital`` repetido.
- Ventilador de 9 a 19 h (día 1 desde las 14 h); de noche, tiro natural (5 %).
- Lote (todos los carros cargados juntos), no el túnel semicontinuo.
- **La muestra estaba en el carro frente a la entrada de aire caliente** (dato del
  usuario, S70): se compara con un carro solo (1/24 de la carga) que recibe todo el
  caudal y el aire de entrada, no con la carga media.

Uso: ``.venv/bin/python -m validacion.adital.replica_tanda_2009``
"""

from __future__ import annotations

import dataclasses
from unittest import mock

import numpy as np

from calculos.camara_calc import calcular_camara
from calculos.cano_maestro_calc import delta_T_cano_maestro
from calculos.colector_calc import calcular_colector_tipo1
from calculos.motor_calc import densidad_aire
from calculos.psicrometria import HR_desde_omega, humedad_absoluta
from core import catalogo
from core.camara import ConfiguracionCarros, ForzantesAire
from validacion.validacion_adital import (
    P_AMB_PA,
    construir_camara_adital,
    construir_colector_adital,
    dia_sintetico_marzo,
)

# Fig. 14: peso de la muestra [g] a las 15:00 y 18:00 de los días 1..4.
PESO_MUESTRA_G = [140, 96, 77, 76, 59, 53, 40, 40]
HORAS_MUESTRA = [15, 18, 39, 42, 63, 66, 87, 90]  # h desde las 00:00 del día 1
M_SECA_G = 35.0  # supuesto: 40 g finales con ~12 % b.h.

T0_H = 14.0  # arranque: carga terminada después del mediodía solar


def forzantes(n_dias: int = 4, frac_noche: float = 0.05, m_dot_dia: float | None = None):
    """Forzantes horarias desde las 14 h del día 1, colector + caño maestro."""
    colector = construir_colector_adital()
    clima = dia_sintetico_marzo()
    m_dia = m_dot_dia or colector.caudal_total_m3_s() * densidad_aire(323.15, P_AMB_PA)
    h_abs = np.arange(T0_H, 24.0 * n_dias + 1e-9, 1.0)
    T_ent, T_amb, w, irr, v, m = [], [], [], [], [], []
    for ha in h_abs:
        k = int(ha) % 24
        Ta = clima["T_amb_C"][k] + 273.15
        Ig = clima["I_poa"][k]
        T_sal = Ta
        if Ig >= 50.0:
            r = calcular_colector_tipo1(
                colector,
                T_amb_K=Ta,
                I_g_W_m2=Ig,
                v_viento_ms=clima["v_viento"][k],
                P_amb_Pa=P_AMB_PA,
                T_entrada_K=Ta,
            )
            dT = delta_T_cano_maestro(
                colector.banco.cano_maestro,
                T_aire_K=r.T_salida_K,
                T_amb_K=Ta,
                I_g_W_m2=Ig,
                m_dot_as_kg_s=m_dia,
                v_viento_ms=clima["v_viento"][k],
                P_Pa=P_AMB_PA,
            )
            T_sal = r.T_salida_K + dT
        ventilador = 9 <= k < 19
        T_ent.append(T_sal if ventilador else Ta)
        T_amb.append(Ta)
        w.append(humedad_absoluta(clima["HR"][k], Ta, P_AMB_PA))
        irr.append(Ig)
        v.append(clima["v_viento"][k])
        m.append(m_dia if ventilador else frac_noche * m_dia)
    a = np.asarray
    return (h_abs - T0_H) * 3600.0, ForzantesAire(
        t_s=(h_abs - T0_H) * 3600.0,
        T_ent_K=a(T_ent),
        omega_ent=a(w),
        m_dot_aire_seco_kg_s=a(m),
        T_amb_K=a(T_amb),
        v_viento_ms=a(v),
        I_g_W_m2=np.zeros(len(h_abs)),
        I_g_POA_W_m2=a(irr),
    )


def correr(masa_kg=2000.0, X0=3.0, con_difusion=True, d_pieza_m=None, **kw_forz):
    _, fz = forzantes(**kw_forz)
    cam = construir_camara_adital()
    cam = dataclasses.replace(
        cam,
        tunel=None,
        carga_producto=dataclasses.replace(
            cam.carga_producto, masa_total_kg=masa_kg, humedad_inicial_X=X0, humedad_objetivo_X=0.05
        ),
    )
    if d_pieza_m is not None:
        cam = dataclasses.replace(
            cam, bandejas=dataclasses.replace(cam.bandejas, diametro_eq_particula_m=d_pieza_m)
        )
    f = catalogo.difusion_interna if con_difusion else (lambda pid: None)
    with mock.patch.object(catalogo, "difusion_interna", f):
        res = calcular_camara(
            cam, 323.15, 0.15, 298.15, P_AMB_PA, t_max_s=float(fz.t_s[-1]), forzantes_aire=fz
        )
    return fz, res


def correr_primer_carro(con_difusion=True, d_pieza_m=None, masa_total_kg=2000.0, **kw_forz):
    """El carro frente a la entrada: 1/24 de la carga con todo el caudal y aire fresco."""
    _, fz = forzantes(**kw_forz)
    cam = construir_camara_adital()
    cam = dataclasses.replace(
        cam,
        tunel=None,
        carros=ConfiguracionCarros(n_carros=1, bandejas_por_carro=cam.carros.bandejas_por_carro),
        geometria=dataclasses.replace(
            cam.geometria, largo_m=cam.geometria.largo_m / cam.carros.n_carros
        ),
        bandejas=dataclasses.replace(cam.bandejas, diametro_eq_particula_m=d_pieza_m),
        carga_producto=dataclasses.replace(
            cam.carga_producto,
            masa_total_kg=masa_total_kg / cam.carros.n_carros,
            humedad_inicial_X=3.0,
            humedad_objetivo_X=0.05,
        ),
    )
    f = catalogo.difusion_interna if con_difusion else (lambda pid: None)
    with mock.patch.object(catalogo, "difusion_interna", f):
        res = calcular_camara(
            cam, 323.15, 0.15, 298.15, P_AMB_PA, t_max_s=float(fz.t_s[-1]), forzantes_aire=fz
        )
    return fz, res


def resumen(fz, res, etiqueta):
    th = res.t_array_s / 3600.0 + T0_H
    X = res.X_prod_kg_kg
    X_med = np.array(PESO_MUESTRA_G) / M_SECA_G - 1.0
    X_sim = np.interp(HORAS_MUESTRA, th, X)
    # HR entrada vs salida al mediodía de los días 2 y 3
    filas = []
    for dia in (1, 2):
        h = 24 * dia + 13.0
        i = int(np.argmin(abs(th - h)))
        T_e = float(np.interp(h - T0_H, fz.t_s / 3600, fz.T_ent_K))
        w_e = float(np.interp(h - T0_H, fz.t_s / 3600, fz.omega_ent))
        HR_e = HR_desde_omega(w_e, T_e, P_AMB_PA)
        filas.append(
            (dia + 1, T_e - 273.15, HR_e * 100, res.T_flujo_K[i] - 273.15, res.HR_flujo[i] * 100)
        )
    print(f"\n== {etiqueta}  ({res.status})")
    print("   hora   X_sim   X_med")
    for hm, xs, xm in zip(HORAS_MUESTRA, X_sim, X_med):
        print(f"   d{hm // 24 + 1} {hm % 24:02d}h  {xs:5.2f}  {xm:5.2f}")
    print("   mediodía: día  T_ent  HR_ent | T_sal  HR_sal")
    for d, te, he, ts, hs in filas:
        print(f"              {d}   {te:5.1f}  {he:5.1f} | {ts:5.1f}  {hs:5.1f}")
    print(f"   agua evaporada: {res.masa_evaporada_total_kg:.0f} kg")


if __name__ == "__main__":
    print("### Carga completa (2 t en 24 carros): la media, no la muestra")
    for con in (True, False):
        fz, res = correr(con_difusion=con)
        resumen(fz, res, "con difusión (Vega 2007, lámina 8 mm)" if con else "sin difusión")
    print("\n### Primer carro (frente a la entrada): comparable con la muestra")
    for etq, kw in [
        ("sin difusión", dict(con_difusion=False)),
        ("con difusión, 8 mm (catálogo)", dict()),
        ("con difusión, vaina entera ~25 mm", dict(d_pieza_m=0.025)),
    ]:
        fz, res = correr_primer_carro(**kw)
        resumen(fz, res, etq)
