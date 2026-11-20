"""Reajuste de la difusividad efectiva del catálogo **dentro de Secasol** (S70, 1.5.1).

Problema (S70, ver bitácora): los papers de capa fina calculan ``D_eff`` ajustando la
curva entera con el primer término de Fick, como si el aire no opusiera resistencia.
Ese ``D`` absorbe la película del equipo de ensayo, y Secasol —que suma su propia
película en serie— la contaba dos veces: con el ``D`` de Sacilik 2006 la manzana secaba
2–4 veces más lento que el ensayo del que salió el número.

Método (política adoptada con el usuario):

1. Se **reconstruye la curva del paper** con su propio ``D`` y su propia convención de
   longitud: ``MR(t) = A·exp(−μ₁²·D·t/L²)`` (lámina: ``A = 8/π²``, ``μ₁ = π/2``, L =
   camino de difusión; cilindro: ``A = 4/β₁²``, ``μ₁ = β₁ = 2.405``, L = radio). No hace
   falta digitalizar figuras: es la curva que el propio paper ajustó a sus datos.
2. Se estima el ``h`` del equipo como **placa plana del largo de la pieza** (la capa límite
   se reinicia en cada rodaja de una capa simple), con la velocidad de aire del paper
   (``coef_conveccion_producto_local``) y ``K_m`` por Chilton-Colburn, igual que el motor.
   **El h casi nunca se informa: es el supuesto que más pesa y queda anotado por caso.**
3. Se busca el ``D`` con el que Secasol (película + difusión en serie, misma isoterma del
   catálogo) tarda lo mismo en llegar a ``MR = 0.2``. Se usa ``MR = 0.2`` y no el final
   para no depender del equilibrio.
4. Con varias temperaturas, ``E_a`` sale de la regresión de ``ln D`` contra ``1/T``.

Uso: ``.venv/bin/python -m validacion.difusividad.reajuste_difusividad``
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from calculos.camara_calc import _LE_AGUA_AIRE, coef_conveccion_producto_local
from calculos.camara_termodinamica import simular_secado
from calculos.psicrometria import actividad_agua_isoterma, cp_aire_humedo, humedad_absoluta
from core import catalogo
from core.camara import ForzantesAire

MR_OBJETIVO = 0.2
_R = 8.314462618
_BETA1_CILINDRO = 2.404825557695773


@dataclass(frozen=True)
class CasoPaper:
    """Un ensayo de capa fina publicado, con lo necesario para reconstruirlo."""

    producto: str
    fuente: str
    D_paper: tuple[tuple[float, float], ...]  # (T_aire °C, D m²/s) del paper
    geometria: str  # "lamina" | "cilindro"
    L_paper_m: float  # camino de difusión (lámina) o radio (cilindro) en la fórmula del paper
    dimension_secasol_m: float  # d_p de Secasol: espesor (2 caras) o diámetro
    caras: int  # caras expuestas en el ensayo (lámina): 1 o 2
    v_aire_ms: float
    L_placa_m: float  # largo de la pieza en la dirección del aire (para h)
    X0: float
    HR: float = 0.10  # HR del aire de secado (si el paper no la da: supuesto)
    supuestos: tuple[str, ...] = field(default_factory=tuple)


CASOS: tuple[CasoPaper, ...] = (
    CasoPaper(
        producto="manzana",
        fuente="Sacilik & Elicin 2006, J Food Eng 73:281 (rango 40–60 °C)",
        D_paper=((40.0, 2.27e-10), (60.0, 4.97e-10)),
        geometria="lamina",
        L_paper_m=0.0025,  # H = semiespesor de 5 mm (ec. 8)
        dimension_secasol_m=0.005,
        caras=2,  # bandeja de piso perforado
        v_aire_ms=0.8,
        L_placa_m=0.06,
        X0=4.57,
        supuestos=(
            "el paper no tabula D por condición: extremos del rango asignados a 40 y 60 °C con 5 mm",
            "HR 10 % (no informada)",
            "rodaja de ~60 mm de diámetro",
        ),
    ),
    CasoPaper(
        producto="pimiento_rojo",
        fuente="Vega et al. 2007, J Food Eng 79:1460, Tabla 4",
        D_paper=((50.0, 3.2e-9), (60.0, 6.9e-9), (70.0, 10.2e-9), (80.0, 11.2e-9)),
        geometria="lamina",
        L_paper_m=0.005,  # semiespesor de cubos de 1 cm
        dimension_secasol_m=0.010,
        caras=2,
        v_aire_ms=2.5,
        L_placa_m=0.01,
        X0=10.11,
        HR=0.08,  # Tabla 3: 11.4 % a 50 °C … 2.9 % a 80 °C
        supuestos=("cubo de 1 cm tratado como lámina de 10 mm (como el paper)",),
    ),
    CasoPaper(
        producto="aji_rojo",
        fuente="Kaleemullah & Kailappan 2006, J Food Eng 76:531",
        D_paper=((50.0, 3.78e-9), (65.0, 7.10e-9)),
        geometria="cilindro",
        L_paper_m=0.006,
        dimension_secasol_m=0.012,
        caras=2,
        v_aire_ms=0.4,
        L_placa_m=0.012,
        X0=3.25,
        supuestos=("diámetro de 12 mm (catálogo): el paper no lo informa",),
    ),
    CasoPaper(
        producto="ciruela",
        fuente="Goyal et al. 2007, J Food Eng 79:176, Tabla 4 (control)",
        D_paper=((55.0, 3.04e-10), (60.0, 3.44e-10), (65.0, 3.69e-10)),
        geometria="lamina",
        L_paper_m=0.0035,  # 'L = espesor' con π²Dt/L² ≡ camino de 3.5 mm (una cara)
        dimension_secasol_m=0.0035,
        caras=1,  # bandejas de aluminio macizas
        v_aire_ms=0.8,
        L_placa_m=0.04,
        X0=9.86,
        supuestos=("rodaja de ~40 mm", "HR 10 % (no informada)"),
    ),
    CasoPaper(
        producto="durazno",
        fuente="Kingsly et al. 2007, Int J Food Sci Technol 42:65, Tabla 4 (control)",
        D_paper=((55.0, 3.04e-10), (65.0, 3.62e-10)),
        geometria="lamina",
        L_paper_m=0.0035,
        dimension_secasol_m=0.0035,
        caras=1,
        v_aire_ms=0.8,
        L_placa_m=0.05,
        X0=6.3,
        supuestos=(
            "unidad de la tabla leída como ×10⁻¹⁰ m²/s",
            "X0 del catálogo",
            "HR 10 % (no informada)",
        ),
    ),
    CasoPaper(
        producto="papa",
        fuente="Hassini et al. 2007, J Food Eng 79:47, Tabla 1 (L0, 0.5 m/s)",
        D_paper=((40.0, 4.01e-9), (55.0, 4.39e-9), (70.0, 5.36e-9), (85.0, 6.13e-9)),
        geometria="lamina",
        L_paper_m=0.010,  # losa de 10 mm secada por una cara
        dimension_secasol_m=0.010,
        caras=1,
        v_aire_ms=0.5,
        L_placa_m=0.045,
        X0=4.25,
        supuestos=(
            "el paper usa la solución de tiempos cortos (√t); se reconstruye con el primer modo",
            "HR 10 % (no informada)",
        ),
    ),
)


def _aw_func(producto: str):
    iso = catalogo.isoterma_gab(producto)

    def aw(X: float) -> float:
        if X <= 0.0:
            return 0.0
        try:
            return actividad_agua_isoterma(X, iso)
        except ValueError:
            return 1.0

    return aw


def _X_eq(aw, HR: float) -> float:
    return brentq(lambda X: aw(X) - HR, 1e-6, 50.0)


def t_paper_s(caso: CasoPaper, D: float) -> float:
    """Tiempo hasta MR = 0.2 de la curva que el paper ajustó (primer modo de Fick)."""
    if caso.geometria == "cilindro":
        A, mu = 4.0 / _BETA1_CILINDRO**2, _BETA1_CILINDRO
    else:
        A, mu = 8.0 / math.pi**2, math.pi / 2.0
    return caso.L_paper_m**2 / (mu**2 * D) * math.log(A / MR_OBJETIVO)


def t_secasol_s(caso: CasoPaper, T_C: float, D: float | None, P_Pa: float = 90000.0) -> float:
    """Tiempo hasta MR = 0.2 en Secasol: capa simple, película estimada + difusión en serie."""
    T = T_C + 273.15
    w = humedad_absoluta(caso.HR, T, P_Pa)
    aw = _aw_func(caso.producto)
    Xe = _X_eq(aw, caso.HR)
    X_obj = Xe + MR_OBJETIVO * (caso.X0 - Xe)
    rho = catalogo.PRODUCTOS[caso.producto]["propiedades_basicas"]["densidad_aparente"]
    m_fresca = 1.0
    m_s = m_fresca / (1.0 + caso.X0)
    d = caso.dimension_secasol_m if caso.caras == 2 else caso.L_paper_m
    if caso.geometria == "cilindro":
        A = 4.0 * m_fresca / (rho * caso.dimension_secasol_m)  # superficie lateral
    else:
        A = caso.caras * m_fresca / (rho * d)
    h = coef_conveccion_producto_local(
        caso.v_aire_ms, T, T - 5.0, w, P_Pa, caso.L_placa_m, caso.L_placa_m
    )
    K_m = h / (cp_aire_humedo(w) * _LE_AGUA_AIRE ** (2.0 / 3.0))
    tasa = None
    if D is not None:
        dif = catalogo.DifusionInterna(D, T, 0.0, caso.geometria)
        # Camino de difusión: semiespesor con 2 caras; espesor completo con 1 cara.
        dim = caso.dimension_secasol_m if caso.caras == 2 else 2.0 * caso.L_paper_m
        tasa = lambda Tp: dif.tasa_primer_modo_s(Tp, dim)  # noqa: E731
    t_max = 400.0 * 3600.0
    fz = ForzantesAire(
        t_s=np.array([0.0, t_max]),
        T_ent_K=np.full(2, T),
        omega_ent=np.full(2, w),
        m_dot_aire_seco_kg_s=np.full(2, 5.0),  # capa fina: el aire no se carga
        T_amb_K=np.full(2, T),
        v_viento_ms=np.full(2, 1.0),
    )
    r = simular_secado(
        T_prod_inicial_K=T - 10.0,
        X_prod_inicial_kg_kg=caso.X0,
        X_prod_objetivo_kg_kg=X_obj,
        m_seco_prod_kg=m_s,
        c_ps_J_kgK=1600.0,
        forzantes=fz,
        A_prod_m2=A,
        A_cuerpo_m2=0.01,
        h_conv_W_m2K=h,
        K_m_kg_m2s=K_m,
        k_aisl_W_mK=0.03,
        esp_cam_m=0.05,
        P_Pa=P_Pa,
        aw_func=aw,
        tasa_difusion_func=tasa,
        t_max_s=t_max,
    )
    return r.t_secado_s if r.t_secado_s is not None else math.inf


def reajustar(caso: CasoPaper) -> dict:
    """D de Secasol por temperatura, E_a y D a 50 °C (o la T más baja del paper)."""
    filas = []
    for T_C, D_p in caso.D_paper:
        objetivo = t_paper_s(caso, D_p)
        t_pel = t_secasol_s(caso, T_C, None)
        if t_pel >= objetivo:
            # Solo la película ya tarda más que el paper: no hay D que ajuste. El
            # supuesto de h queda corto para ese equipo; se reporta y no se ajusta.
            filas.append((T_C, D_p, None, objetivo, t_pel))
            continue
        f = lambda lD: t_secasol_s(caso, T_C, 10.0**lD) - objetivo  # noqa: E731
        D_s = 10.0 ** brentq(f, -12.5, -6.0, xtol=1e-3)
        filas.append((T_C, D_p, D_s, objetivo, t_pel))
    validas = [(T, D) for T, _, D, _, _ in filas if D is not None]
    E_a = 0.0
    if len(validas) >= 2:
        x = np.array([1.0 / (T + 273.15) for T, _ in validas])
        y = np.log([D for _, D in validas])
        E_a = max(0.0, -np.polyfit(x, y, 1)[0] * _R)
    D_ref = None
    T_ref = 50.0
    if validas:
        T_ref = 50.0 if any(T <= 50.0 for T, _ in validas) else min(T for T, _ in validas)
        T0, D0 = min(validas, key=lambda p: abs(p[0] - T_ref))
        D_ref = D0 * math.exp(-E_a / _R * (1 / (T_ref + 273.15) - 1 / (T0 + 273.15)))
    return {"filas": filas, "E_a": E_a, "T_ref_C": T_ref, "D_ref": D_ref}


def main() -> None:
    for caso in CASOS:
        r = reajustar(caso)
        print(f"\n== {caso.producto} — {caso.fuente}")
        print("   T °C   D paper    D Secasol   t paper [h]  t solo película [h]")
        for T_C, D_p, D_s, t_obj, t_pel in r["filas"]:
            ds = f"{D_s:.2e}" if D_s else "   —    "
            print(f"   {T_C:4.0f}  {D_p:.2e}  {ds}   {t_obj / 3600:8.2f}   {t_pel / 3600:8.2f}")
        if r["D_ref"]:
            print(
                f"   → D_ref = {r['D_ref']:.2e} m²/s a {r['T_ref_C']:.0f} °C, "
                f"E_a = {r['E_a'] / 1000:.1f} kJ/mol"
            )
        for s in caso.supuestos:
            print(f"   supuesto: {s}")


if __name__ == "__main__":
    main()
