"""Ajuste de D contra curvas X(t) medidas de capa fina, dentro de Secasol (S71).

Simula una pieza en capa simple con el mismo núcleo que el motor de cámara: película de
placa plana (``coef_conveccion_producto_local`` + Chilton-Colburn) en serie con el primer
modo de Fick (``DifusionInterna``) y la isoterma del catálogo. El aire no se carga
(caudal grande): es la condición de un ensayo de capa fina.

A diferencia de ``reajuste_difusividad.py`` (que reconstruye la curva del paper desde su D
y compara el tiempo a MR = 0.2), acá se comparan las **curvas medidas completas**, lo que
evita depender de la convención de longitud de cada paper.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from calculos.camara_calc import _LE_AGUA_AIRE, coef_conveccion_producto_local
from calculos.camara_termodinamica import simular_secado
from calculos.psicrometria import cp_aire_humedo
from core import catalogo
from core.camara import ForzantesAire
from validacion.difusividad.reajuste_difusividad import _aw_func

_R = 8.314462618


@dataclass(frozen=True)
class Ensayo:
    """Un ensayo de capa fina publicado.

    Attributes:
        producto: Id del catálogo (densidad, isoterma).
        X0: Humedad inicial [kg/kg b.s.].
        espesor_m: Espesor de la rodaja (lámina, 2 caras expuestas) [m].
        v_aire_ms: Velocidad del aire sobre la pieza [m/s].
        L_placa_m: Largo de la pieza en la dirección del aire (para h) [m].
        omega: Humedad absoluta del aire [kg/kg].
        c_ps_J_kgK: Calor específico de la materia seca [J/(kg·K)].
        P_Pa: Presión [Pa].
        radiacion_paredes: Si True, suma al ``h`` de **calor** (no al de masa) la
            radiación linealizada con paredes a la temperatura del aire,
            ``h_rad = 4·ε·σ·T_m³`` con ``T_m`` entre el aire y ~25 K por debajo
            (producto cerca del bulbo húmedo). Es la geometría de un gabinete
            calefaccionado: a baja velocidad pesa tanto como la convección.
    """

    producto: str
    X0: float
    espesor_m: float
    v_aire_ms: float
    L_placa_m: float
    omega: float
    c_ps_J_kgK: float = 1500.0
    P_Pa: float = 101325.0
    radiacion_paredes: bool = True


_SIGMA = 5.670374419e-8
_EPS_PRODUCTO = 0.9


def h_radiacion_paredes(T_aire_K: float) -> float:
    """h radiativo linealizado producto-paredes del gabinete [W/(m²·K)]."""
    T_m = T_aire_K - 12.5
    return 4.0 * _EPS_PRODUCTO * _SIGMA * T_m**3


def simular(
    e: Ensayo, D: float | None, T_C: float, f_h: float = 1.0, t_max_h: float = 24.0
) -> tuple[np.ndarray, np.ndarray]:
    """Curva X(t) de Secasol. ``D`` a ``T_C`` (None = solo película). Devuelve (t [min], X)."""
    T = T_C + 273.15
    rho = catalogo.PRODUCTOS[e.producto]["propiedades_basicas"]["densidad_aparente"]
    A = 2.0 / (rho * e.espesor_m)  # por kg fresco, 2 caras
    h = f_h * coef_conveccion_producto_local(
        e.v_aire_ms, T, T - 5.0, e.omega, e.P_Pa, e.L_placa_m, e.L_placa_m
    )
    K_m = h / (cp_aire_humedo(e.omega) * _LE_AGUA_AIRE ** (2.0 / 3.0))  # masa: solo convección
    h_calor = h + (h_radiacion_paredes(T) if e.radiacion_paredes else 0.0)
    tasa = None
    if D is not None:
        dif = catalogo.DifusionInterna(D, T, 0.0, "lamina")
        tasa = lambda Tp: dif.tasa_primer_modo_s(Tp, e.espesor_m)  # noqa: E731
    t_max = t_max_h * 3600.0
    fz = ForzantesAire(
        t_s=np.array([0.0, t_max]),
        T_ent_K=np.full(2, T),
        omega_ent=np.full(2, e.omega),
        m_dot_aire_seco_kg_s=np.full(2, 5.0),  # capa fina: el aire no se carga
        T_amb_K=np.full(2, T),
        v_viento_ms=np.full(2, 1.0),
    )
    r = simular_secado(
        T_prod_inicial_K=T - 25.0,
        X_prod_inicial_kg_kg=e.X0,
        X_prod_objetivo_kg_kg=0.01,
        m_seco_prod_kg=1.0 / (1.0 + e.X0),
        c_ps_J_kgK=e.c_ps_J_kgK,
        forzantes=fz,
        A_prod_m2=A,
        A_cuerpo_m2=0.01,
        h_conv_W_m2K=h_calor,
        K_m_kg_m2s=K_m,
        k_aisl_W_mK=0.03,
        esp_cam_m=0.05,
        P_Pa=e.P_Pa,
        aw_func=_aw_func(e.producto),
        tasa_difusion_func=tasa,
        t_max_s=t_max,
    )
    return np.asarray(r.t_array_s) / 60.0, np.asarray(r.X_prod_kg_kg)


def error(
    e: Ensayo, t_med_min, X_med, D: float | None, T_C: float, f_h: float = 1.0
) -> tuple[float, float]:
    """``(RMSE, MBE)`` de X simulada contra la medida (sim − med)."""
    t_s, X_s = simular(e, D, T_C, f_h)
    d = np.interp(t_med_min, t_s, X_s, right=X_s[-1]) - np.asarray(X_med)
    return float(np.sqrt(np.mean(d**2))), float(np.mean(d))


def D_optimo(e: Ensayo, t_med_min, X_med, T_C: float) -> tuple[float, float]:
    """D que minimiza el RMSE de una curva (grilla log + sección áurea). Devuelve (D, RMSE)."""

    def f(lD: float) -> float:
        return error(e, t_med_min, X_med, 10.0**lD, T_C)[0]

    grilla = np.linspace(-11.3, -7.5, 39)
    vals = [f(x) for x in grilla]
    i = int(np.argmin(vals))
    lo, hi = grilla[max(i - 1, 0)], grilla[min(i + 1, len(grilla) - 1)]
    for _ in range(25):
        a, b = hi - 0.618 * (hi - lo), lo + 0.618 * (hi - lo)
        if f(a) < f(b):
            hi = b
        else:
            lo = a
    D = 10.0 ** (0.5 * (lo + hi))
    return D, f(math.log10(D))


def arrhenius(pares: list[tuple[float, float]], T_ref_C: float = 50.0) -> tuple[float, float]:
    """Regresión ``ln D`` vs ``1/T``. Devuelve ``(D(T_ref), E_a [J/mol])``."""
    x = np.array([1.0 / (T + 273.15) for T, _ in pares])
    pend = np.polyfit(x, np.log([D for _, D in pares]), 1)
    return float(math.exp(np.polyval(pend, 1.0 / (T_ref_C + 273.15)))), float(-pend[0] * _R)


def D_a(T_C: float, D_ref: float, E_a: float, T_ref_C: float = 50.0) -> float:
    """D a ``T_C`` por Arrhenius desde ``D_ref`` a ``T_ref_C``."""
    return D_ref * math.exp(-E_a / _R * (1.0 / (T_C + 273.15) - 1.0 / (T_ref_C + 273.15)))
