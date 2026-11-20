"""Réplica en Secasol del secador de caja forzado de Durán et al. 2008 (S70).

Durán, Molina, Condorí & Buchller (2008), AVERMA 12:03.87–03.94. Caja de
1.0 × 0.85 × 0.20 m, policarbonato alveolar 4 mm, lana de vidrio 25 mm, dos
niveles de bandeja; ventilación por dos ventiladores de PC alimentados por FV.
Ensayo de charqui de agosto de 2008 en el INENCO (Salta), 11:00 del día 1 a
~18:00 del día 2.

Supuestos (el paper no los informa):
- Forzantes = T ambiente y radiación **medidas** (Fig. 17, digitalizadas); NASA
  POWER no reproduce ningún par de días de agosto de 2008 (RMSE_T ≥ 3.4 °C).
- ω ambiente 0.0040 kg/kg, inferida de la HR interna (Fig. 20) menos el
  aporte de la evaporación.
- Caudal 0.022 m³/s: 2 ventiladores Ø 8 cm (área anular) × v_salida medida 2–3 m/s.
- CAJA **sin motor y sin bocas** = caudal constante: Secasol no admite CAJA con
  ventilador (``PROY_CAJA_CON_MOTOR``).
- Carga por secador 1.79 kg (3.584 kg entre los dos), X0 = 1.15 (muestra del
  secador con panel, Fig. 22). Área de bandeja = área cubierta por las fetas
  (~50 % de 0.8 m² por nivel).

Uso: ``.venv/bin/python -m validacion.duran2008.replica_charqui_forzado``
"""

import json
from pathlib import Path

import numpy as np

from calculos.balance_global import calcular_todo_transitorio
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    ForzantesAire,
    GeometriaCamara,
    ParedCamara,
)
from core.emplazamiento import Emplazamiento
from core.proyecto import Configuracion, Proyecto, Tipologia

D = str(Path(__file__).parent) + "/"
f17 = json.load(open(D + "datos_digitalizados.json"))


def interp(serie, th):
    a = np.array(serie)
    a = a[np.argsort(a[:, 0])]
    return np.interp(th, a[:, 0], a[:, 1])


def correr(
    Q_m3s=0.022,
    omega_amb=0.0040,
    area_band=0.40,
    X0=1.15,
    m_fresca=1.79,
    v_viento=0.5,
    X_obj=0.155,
    producto="charqui_vacuno",
    horas=31.0,
    paso_h=0.25,
    verbose=True,
):
    th = np.arange(0.0, horas + 1e-9, paso_h)  # h desde 11:00 día 1
    T_amb = interp(f17["T"], th) + 273.15
    G = np.clip(interp(f17["G"], th), 0, None)
    G[G < 10] = 0.0
    rho = 88000 / (287.0 * 300.0)
    m_dot = Q_m3s * rho
    n = len(th)
    forz = ForzantesAire(
        t_s=th * 3600.0,
        T_ent_K=T_amb.copy(),
        omega_ent=np.full(n, omega_amb),
        m_dot_aire_seco_kg_s=np.full(n, m_dot),
        T_amb_K=T_amb,
        v_viento_ms=np.full(n, v_viento),
        I_g_W_m2=G,
        I_g_POA_W_m2=G,
    )
    pared = ParedCamara(
        capas=[
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
            CapaPared(material_id="lana_vidrio_media", espesor_m=0.025, catalogo="aislantes"),
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
        ]
    )
    cam = Camara(
        geometria=GeometriaCamara(largo_m=1.0, ancho_m=0.85, alto_m=0.20),
        bandejas=ConfiguracionBandejas(
            n_bandejas=2, area_bandeja_m2=area_band, separacion_entre_bandejas_m=0.08
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=m_dot),
        construccion=ConstruccionCamara(
            cubierta_translucida_id="policarbonato_alveolar",
            cubierta_translucida_espesor_m=0.004,
            pared=pared,
        ),
        carga_producto=CargaProducto(
            producto_id=producto,
            masa_total_kg=m_fresca,
            humedad_inicial_X=X0,
            humedad_objetivo_X=X_obj,
        ),
    )
    proy = Proyecto(
        configuracion=Configuracion(tipologia=Tipologia.CAJA),
        emplazamiento=Emplazamiento(latitud_deg=-24.73, longitud_deg=-65.41, altitud_m=1190.0),
        camara=cam,
    )
    res = calcular_todo_transitorio(proy, forzantes_base=forz, n_dias=2)
    return th, res


if __name__ == "__main__":
    th, res = correr()
    print("errores", res.errores)
    pass
    c = res.camara
    pass


def comparar(th, res, etiqueta=""):
    med = json.load(open(D + "datos_digitalizados.json"))
    c = res.camara
    t = np.asarray(c.t_array_s) / 3600.0
    sim = {
        "X": np.asarray(c.X_prod_kg_kg),
        "Tf": np.asarray(c.T_flujo_K) - 273.15,
        "HR": np.asarray(c.HR_flujo) * 100,
        "Tp": np.asarray(c.T_prod_K) - 273.15,
    }
    out = {}
    for k_med, k_sim in [("X_panel", "X"), ("Tflujo_panel", "Tf"), ("HR_panel", "HR")]:
        a = np.array(med[k_med])
        a = a[np.argsort(a[:, 0])]
        a = a[(a[:, 0] <= t[-1])]
        s = np.interp(a[:, 0], t, sim[k_sim])
        out[k_med] = (np.sqrt(np.mean((s - a[:, 1]) ** 2)), np.mean(s - a[:, 1]))
    return t, sim, out


def tabla(th, res):
    t, sim, out = comparar(th, res)
    med = json.load(open(D + "datos_digitalizados.json"))
    print(" hora   X_sim  X_med | Tf_sim Tf_med | HR_sim HR_med | Tprod")
    for h in [0, 2, 4, 6, 7.5, 13, 18, 20, 21, 22, 24, 26, 28, 30]:

        def m(k):
            a = np.array(med[k])
            sel = a[np.abs(a[:, 0] - h) < 0.35]
            return f"{sel[:,1].mean():6.2f}" if len(sel) else "    - "

        i = np.argmin(abs(t - h))
        print(
            f"{(11+h)%24:5.1f}  {sim['X'][i]:6.2f} {m('X_panel')} | {sim['Tf'][i]:6.1f} {m('Tflujo_panel')} | {sim['HR'][i]:6.1f} {m('HR_panel')} | {sim['Tp'][i]:5.1f}"
        )
    for k, (r, b) in out.items():
        print(f"  {k}: RMSE {r:.3f}  MBE {b:+.3f}")
    print("  m_evap total sim:", round(res.camara.masa_evaporada_total_kg, 3), "kg")


if __name__ == "__main__":
    tabla(th, res)
