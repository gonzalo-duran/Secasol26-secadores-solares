"""
Superficie de respuesta del colector — sustituto interpolado del solver.

Corre el solver estacionario del colector sobre una grilla de condiciones de
borde y devuelve un interpolador que evalúa ``ΔT = T_salida − T_ambiente`` en
tiempo despreciable. Pensado para horizontes largos (el modo anual, 8760 h),
donde llamar al solver una vez por hora domina el costo de la simulación.

**Por qué el espacio de entrada es 3-D.** En los pipelines de convección forzada
el colector se resuelve siempre con ``T_entrada = T_amb`` (ver
``balance_global._correr_colector_horizonte_forzado``). Eso deja la respuesta
determinada por ``(POA, T_amb, v_viento)``: la velocidad del aire en el canal,
cuando se deriva del caudal del sistema, depende de ``T_amb`` únicamente (vía la
densidad), así que no agrega una cuarta dimensión.

**Por qué la interpolación es exacta en la práctica.** Con ``T_entrada = T_amb``
el término de pérdidas de Hottel-Whillier-Bliss, ``U_L·(T_in − T_amb)``, se
anula, y la respuesta queda casi afín en POA — la curvatura restante viene de la
dependencia de ``U_L`` y ``F_R`` con la temperatura de placa y el viento, que es
suave. Medido contra el solver real sobre una grilla 9×5×4: error medio 0.076 K,
p95 0.217 K, máximo 0.276 K. Para dimensionarlo: el propio modelo de colector,
validado contra el prototipo de 10 m del INENCO, da RMSE 0.9 °C frente a
medición real (mejora 38, fase 2). El error de interpolación es un orden por
debajo del error del modelo contra la realidad.

**Qué NO cambia respecto del solver.** La superficie hereda todas las hipótesis
del modelo que muestrea: régimen cuasi-estacionario (sin inercia térmica del
colector, un paso de nube se refleja instantáneamente), capacitancia de placa
despreciable, y la mecánica de canales del tipo configurado. No es una
simplificación física adicional — es el mismo modelo, evaluado por interpolación
en vez de por resolución.

El módulo es puro: no importa ``streamlit`` ni ``core``. Recibe el proyecto solo
para pasárselo al solver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.interpolate import RegularGridInterpolator

# ---------------------------------------------------------------------------
# Constantes de grilla
# ---------------------------------------------------------------------------

# Fracciones del POA máximo para los nodos. Más densas cerca de cero, que es
# donde la respuesta se aparta más de la recta (arranque del colector).
_FRACCIONES_POA: tuple[float, ...] = (0.0, 0.04, 0.12, 0.23, 0.38, 0.54, 0.69, 0.85, 1.0)

_N_NODOS_T_DEFAULT: int = 5
_N_NODOS_V_DEFAULT: int = 4

# Span mínimo de cada eje [unidades del eje]. Evita que un clima sintético con
# T_amb o viento constante genere un eje degenerado (RegularGridInterpolator
# exige nodos estrictamente crecientes).
_SPAN_MIN_T_K: float = 1.0
_SPAN_MIN_V_MS: float = 0.5
_SPAN_MIN_POA: float = 50.0

# Márgenes con que se extiende el rango observado, para que las horas reales
# caigan dentro de la grilla y no haya que extrapolar.
_MARGEN_T_K: float = 2.0
_MARGEN_V_MS: float = 0.5


@dataclass(frozen=True)
class SuperficieColector:
    """Superficie de respuesta ``ΔT(POA, T_amb, v_viento)`` del colector.

    Attributes:
        POA_nodos: Nodos del eje de irradiancia POA [W/m²], crecientes.
        T_amb_nodos: Nodos del eje de temperatura ambiente [K], crecientes.
        v_viento_nodos: Nodos del eje de velocidad de viento [m/s], crecientes.
        delta_T_K: Salto térmico del colector en cada nodo [K], shape
            ``(n_POA, n_T, n_v)``. Siempre ≥ 0.
        n_solves: Cantidad de llamadas al solver que costó construirla.
        n_fallas: Nodos donde el solver no convergió y hubo que rellenar.
        m_dot_sistema_kg_s: Caudal del sistema con el que se muestreó [kg/s],
            o ``None`` si se usó la ``velocidad_diseno_ms`` nominal.
        P_amb_Pa: Presión ambiente del muestreo [Pa].
    """

    POA_nodos: np.ndarray
    T_amb_nodos: np.ndarray
    v_viento_nodos: np.ndarray
    delta_T_K: np.ndarray
    n_solves: int = 0
    n_fallas: int = 0
    m_dot_sistema_kg_s: Optional[float] = None
    P_amb_Pa: float = 101325.0
    _interp: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        for nombre, eje in (
            ("POA", self.POA_nodos),
            ("T_amb", self.T_amb_nodos),
            ("v_viento", self.v_viento_nodos),
        ):
            if len(eje) < 2:
                raise ValueError(
                    f"SUPCOL_EJE_INSUFICIENTE: el eje '{nombre}' necesita al menos "
                    f"2 nodos (recibido: {len(eje)})."
                )
            if not np.all(np.diff(eje) > 0):
                raise ValueError(
                    f"SUPCOL_EJE_NO_CRECIENTE: los nodos de '{nombre}' deben ser "
                    "estrictamente crecientes."
                )
        forma = (len(self.POA_nodos), len(self.T_amb_nodos), len(self.v_viento_nodos))
        if self.delta_T_K.shape != forma:
            raise ValueError(
                f"SUPCOL_FORMA_INVALIDA: delta_T_K tiene shape {self.delta_T_K.shape}, "
                f"se esperaba {forma}."
            )
        object.__setattr__(
            self,
            "_interp",
            RegularGridInterpolator(
                (self.POA_nodos, self.T_amb_nodos, self.v_viento_nodos),
                self.delta_T_K,
                method="linear",
                bounds_error=False,
                fill_value=None,
            ),
        )

    def evaluar(
        self,
        POA_W_m2,
        T_amb_K,
        v_viento_ms,
    ) -> np.ndarray:
        """Salto térmico del colector ``ΔT = T_salida − T_amb`` [K].

        Los argumentos se recortan al rango de la grilla antes de interpolar: la
        grilla se construye cubriendo el clima del proyecto, así que un recorte
        solo actúa en bordes por redondeo, y evita extrapolaciones salvajes si
        el llamador pasa condiciones fuera del muestreo.

        Args:
            POA_W_m2: Irradiancia en el plano del colector [W/m²], escalar o array.
            T_amb_K: Temperatura ambiente [K], escalar o array.
            v_viento_ms: Velocidad del viento [m/s], escalar o array.

        Returns:
            ``ΔT`` [K], mismo shape que la entrada (broadcast). Siempre ≥ 0: el
            colector no enfría el aire por debajo del ambiente, igual que el
            recorte que aplica ``_correr_colector_horizonte_forzado``.
        """
        POA = np.clip(np.asarray(POA_W_m2, dtype=float), self.POA_nodos[0], self.POA_nodos[-1])
        T = np.clip(np.asarray(T_amb_K, dtype=float), self.T_amb_nodos[0], self.T_amb_nodos[-1])
        v = np.clip(
            np.asarray(v_viento_ms, dtype=float),
            self.v_viento_nodos[0],
            self.v_viento_nodos[-1],
        )
        POA, T, v = np.broadcast_arrays(POA, T, v)
        puntos = np.column_stack([POA.ravel(), T.ravel(), v.ravel()])
        dT = np.asarray(self._interp(puntos), dtype=float).reshape(POA.shape)
        return np.maximum(dT, 0.0)

    def T_salida_K(self, POA_W_m2, T_amb_K, v_viento_ms) -> np.ndarray:
        """Temperatura de salida del colector [K] = ``T_amb + ΔT``."""
        T_amb = np.asarray(T_amb_K, dtype=float)
        return T_amb + self.evaluar(POA_W_m2, T_amb_K, v_viento_ms)


# ---------------------------------------------------------------------------
# Construcción de los ejes
# ---------------------------------------------------------------------------


def _eje_lineal(lo: float, hi: float, n: int, span_min: float) -> np.ndarray:
    """``n`` nodos equiespaciados en [lo, hi], garantizando un span mínimo."""
    lo, hi = float(min(lo, hi)), float(max(lo, hi))
    if hi - lo < span_min:
        centro = 0.5 * (lo + hi)
        lo, hi = centro - 0.5 * span_min, centro + 0.5 * span_min
    return np.linspace(lo, hi, max(2, int(n)))


def _eje_POA(POA_max: float) -> np.ndarray:
    """Nodos de POA en [0, POA_max], densificados cerca de cero."""
    POA_max = max(float(POA_max), _SPAN_MIN_POA)
    return np.array([f * POA_max for f in _FRACCIONES_POA], dtype=float)


def _rellenar_fallas(delta_T: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Completa los nodos donde el solver falló, interpolando sobre el eje POA.

    Se rellena a lo largo de POA —el eje dominante— usando los nodos válidos de
    la misma columna ``(T_amb, v)``. Dejar un cero en el hueco deformaría la
    superficie alrededor y contaminaría la interpolación de puntos vecinos que
    sí convergieron, que es peor que el comportamiento del lazo hora a hora.
    Si una columna entera falló, queda en cero (colector sin aporte).
    """
    salida = delta_T.copy()
    n_POA = delta_T.shape[0]
    idx = np.arange(n_POA, dtype=float)
    for j in range(delta_T.shape[1]):
        for k in range(delta_T.shape[2]):
            col_ok = ok[:, j, k]
            if col_ok.all():
                continue
            if not col_ok.any():
                salida[:, j, k] = 0.0
                continue
            salida[:, j, k] = np.interp(idx, idx[col_ok], delta_T[col_ok, j, k])
    return salida


def construir_superficie(
    proyecto,
    *,
    POA_W_m2_serie=None,
    T_amb_K_serie=None,
    v_viento_ms_serie=None,
    m_dot_sistema_kg_s: Optional[float] = None,
    P_amb_Pa: float = 101325.0,
    n_nodos_T: int = _N_NODOS_T_DEFAULT,
    n_nodos_v: int = _N_NODOS_V_DEFAULT,
) -> SuperficieColector:
    """Muestrea el solver del colector sobre una grilla y arma el interpolador.

    La grilla se adapta al clima del proyecto: si se pasan las series horarias,
    los ejes cubren su rango observado (con un margen), de modo que la
    evaluación posterior nunca extrapola. Sin series, se usan rangos genéricos
    amplios.

    El muestreo replica exactamente lo que hace el lazo hora a hora de
    ``balance_global._correr_colector_horizonte_forzado``: ``T_entrada = T_amb``
    y, si hay caudal de sistema, ``velocidad_diseno_ms`` derivada de él con la
    densidad a ``T_amb``. ``velocidad_diseno_ms`` se restaura en un ``finally``.

    Args:
        proyecto: Proyecto con ``colector`` configurado.
        POA_W_m2_serie: Serie horaria de POA [W/m²] para acotar el eje.
        T_amb_K_serie: Serie horaria de T ambiente [K] para acotar el eje.
        v_viento_ms_serie: Serie horaria de viento [m/s] para acotar el eje.
        m_dot_sistema_kg_s: Caudal del sistema [kg/s]. Si es None o no positivo,
            el colector se muestrea a su ``velocidad_diseno_ms`` nominal.
        P_amb_Pa: Presión ambiente [Pa].
        n_nodos_T: Nodos del eje de temperatura ambiente.
        n_nodos_v: Nodos del eje de viento.

    Returns:
        ``SuperficieColector`` lista para evaluar.

    Raises:
        ValueError: ``SUPCOL_SIN_COLECTOR`` si el proyecto no tiene colector.
    """
    from calculos.balance_global import _correr_colector, _velocidad_modulo_desde_caudal

    if proyecto.colector is None:
        raise ValueError(
            "SUPCOL_SIN_COLECTOR: no se puede construir la superficie de respuesta "
            "sin un colector configurado."
        )

    # --- Ejes, acotados al clima observado cuando está disponible ---
    if POA_W_m2_serie is not None and len(np.asarray(POA_W_m2_serie)) > 0:
        POA_max = float(np.nanmax(np.asarray(POA_W_m2_serie, dtype=float)))
    else:
        POA_max = 1300.0
    POA_nodos = _eje_POA(POA_max)

    if T_amb_K_serie is not None and len(np.asarray(T_amb_K_serie)) > 0:
        T_arr = np.asarray(T_amb_K_serie, dtype=float)
        T_lo, T_hi = float(np.nanmin(T_arr)) - _MARGEN_T_K, float(np.nanmax(T_arr)) + _MARGEN_T_K
    else:
        T_lo, T_hi = 263.15, 323.15
    T_nodos = _eje_lineal(T_lo, T_hi, n_nodos_T, _SPAN_MIN_T_K)

    if v_viento_ms_serie is not None and len(np.asarray(v_viento_ms_serie)) > 0:
        v_arr = np.asarray(v_viento_ms_serie, dtype=float)
        v_lo = max(0.0, float(np.nanmin(v_arr)) - _MARGEN_V_MS)
        v_hi = float(np.nanmax(v_arr)) + _MARGEN_V_MS
    else:
        v_lo, v_hi = 0.0, 12.0
    v_nodos = _eje_lineal(v_lo, v_hi, n_nodos_v, _SPAN_MIN_V_MS)

    # --- Muestreo ---
    delta_T = np.zeros((len(POA_nodos), len(T_nodos), len(v_nodos)), dtype=float)
    ok = np.zeros_like(delta_T, dtype=bool)
    n_solves = 0
    n_fallas = 0

    u = proyecto.colector.unidad
    v_diseno_original = float(u.velocidad_diseno_ms)
    derivar_v = m_dot_sistema_kg_s is not None and float(m_dot_sistema_kg_s) > 0.0
    try:
        for j, T_amb in enumerate(T_nodos):
            if derivar_v:
                v_modulo = _velocidad_modulo_desde_caudal(
                    proyecto.colector,
                    float(m_dot_sistema_kg_s),
                    float(T_amb),
                    P_amb_Pa,
                )
                u.velocidad_diseno_ms = float(np.clip(v_modulo, 0.05, 15.0))
            for i, POA in enumerate(POA_nodos):
                for k, v_viento in enumerate(v_nodos):
                    n_solves += 1
                    try:
                        _solver, T_sal_K = _correr_colector(
                            proyecto,
                            T_amb_K=float(T_amb),
                            I_g_W_m2=float(POA),
                            v_viento_ms=float(v_viento),
                            T_entrada_K=float(T_amb),
                            P_amb_Pa=P_amb_Pa,
                        )
                        delta_T[i, j, k] = max(0.0, float(T_sal_K) - float(T_amb))
                        ok[i, j, k] = True
                    except Exception:
                        # Mismo criterio que el lazo hora a hora: régimen
                        # patológico (fsolve sin converger, Re fuera de rango).
                        n_fallas += 1
    finally:
        u.velocidad_diseno_ms = v_diseno_original

    if n_fallas:
        delta_T = _rellenar_fallas(delta_T, ok)

    return SuperficieColector(
        POA_nodos=POA_nodos,
        T_amb_nodos=T_nodos,
        v_viento_nodos=v_nodos,
        delta_T_K=delta_T,
        n_solves=n_solves,
        n_fallas=n_fallas,
        m_dot_sistema_kg_s=(float(m_dot_sistema_kg_s) if derivar_v else None),
        P_amb_Pa=float(P_amb_Pa),
    )
