"""Carta psicrométrica del proceso completo del secador (mejora 27).

Capa de cálculo **pura** (sin Streamlit ni Plotly): genera las curvas de fondo de
la carta psicrométrica (saturación, HR constante, isentálpicas) y extrae los
estados del aire húmedo en los puntos del proceso de secado:

    1. Ambiente            (T_amb, ω_amb)
    2. Salida del colector  — calentamiento sensible (ω constante)
    3. Entrada a la cámara  — calentamiento sensible del auxiliar (ω constante)
    4. Salida de la cámara  — el aire gana vapor (sube ω)

El tramo 3→4 es **enfriamiento ≈ adiabático** (sobre la isentálpica) en cámaras
indirectas/opacas, y **no adiabático** (h sube) en cámaras directas con techo
translúcido — esto **emerge solo** del balance porque el estado de salida
``(T_flujo, ω_flujo)`` ya sale del motor termodinámico de cámara (que incluye
``Q_rad`` del techo). La carta es descriptiva: grafica los estados calculados.

Todo en SI (T [K] en la API interna, °C en los estados expuestos para graficar;
ω [kg_agua/kg_aire_seco]; P [Pa]). La corrección por altitud entra vía ``P_Pa``
(la presión representativa del emplazamiento).

Reusa ``calculos/psicrometria.py`` (mismo módulo que el motor de cámara) — sin
dependencias externas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from calculos.psicrometria import (
    HR_desde_omega,
    entalpia_aire_humedo,
    humedad_absoluta,
    omega_saturacion,
)

# Familia de curvas de HR constante a dibujar (fracción 0–1).
_HR_LINEAS: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
# Tolerancia para colapsar estados consecutivos casi idénticos (sin colector /
# sin auxiliar el calentamiento sensible no agrega un punto nuevo).
_TOL_T_C: float = 0.3
_TOL_OMEGA: float = 1e-4


@dataclass(frozen=True)
class EstadoPsicro:
    """Estado del aire húmedo en un punto del proceso.

    Attributes:
        nombre: Etiqueta del punto (ej. "Ambiente", "Salida colector").
        T_C: Temperatura de bulbo seco [°C].
        omega_kg_kg: Humedad absoluta [kg_agua / kg_aire_seco].
        HR: Humedad relativa [fracción 0–1].
        h_J_kg: Entalpía específica [J / kg_aire_seco].
    """

    nombre: str
    T_C: float
    omega_kg_kg: float
    HR: float
    h_J_kg: float


def _omega_para_entalpia(T_K: float, h_J_kg: float) -> float:
    """ω tal que entalpia_aire_humedo(T_K, ω) = h [kg/kg].

    La entalpía es lineal en ω para T fija, así que se invierte con dos
    evaluaciones (sin tocar las constantes privadas de psicrometria):
        h(ω) = h0 + (h1 − h0)·ω   con h0 = h(T, 0), h1 = h(T, 1).
    """
    h0 = entalpia_aire_humedo(T_K, 0.0)
    h1 = entalpia_aire_humedo(T_K, 1.0)
    return (h_J_kg - h0) / (h1 - h0)


def curvas_fondo(
    T_min_C: float,
    T_max_C: float,
    P_Pa: float,
    *,
    n: int = 120,
    hr_lineas: tuple[float, ...] = _HR_LINEAS,
) -> dict[str, Any]:
    """Curvas de fondo de la carta psicrométrica a presión ``P_Pa``.

    Args:
        T_min_C, T_max_C: Rango de temperatura de bulbo seco [°C].
        P_Pa: Presión total [Pa] (corrección por altitud).
        n: Número de puntos por curva.
        hr_lineas: Fracciones de HR constante a dibujar.

    Returns:
        dict con:
            ``T_C``: np.ndarray del eje de temperatura [°C].
            ``omega_sat``: ω de saturación (HR=100 %) [kg/kg], con NaN donde
                Pv ≥ P (físicamente imposible).
            ``hr``: dict {HR: ω(T) [kg/kg]} con NaN fuera de rango.
    """
    T_C = np.linspace(T_min_C, T_max_C, n)
    T_K = T_C + 273.15

    def _omega_hr(hr: float) -> np.ndarray:
        out = np.full(n, np.nan)
        for i, t in enumerate(T_K):
            try:
                out[i] = humedad_absoluta(hr, float(t), P_Pa)
            except ValueError:
                out[i] = np.nan  # Pv ≥ P: fuera del dominio físico
        return out

    omega_sat = _omega_hr(1.0)
    hr_curvas = {hr: _omega_hr(hr) for hr in hr_lineas}

    return {"T_C": T_C, "omega_sat": omega_sat, "hr": hr_curvas}


def isentalpica(
    h_J_kg: float,
    T_min_C: float,
    T_max_C: float,
    P_Pa: float,
    *,
    n: int = 60,
) -> tuple[np.ndarray, np.ndarray]:
    """Línea de entalpía constante h en la carta: (T_C, ω) con ω ≥ 0 y ≤ ω_sat.

    Útil para dibujar la referencia adiabática desde la entrada de la cámara
    (el tramo 3→4 sigue ≈ esta línea en cámaras indirectas).
    """
    T_C = np.linspace(T_min_C, T_max_C, n)
    omega = np.full(n, np.nan)
    for i, tc in enumerate(T_C):
        T_K = tc + 273.15
        w = _omega_para_entalpia(T_K, h_J_kg)
        if w < 0:
            continue
        try:
            w_sat = omega_saturacion(T_K, P_Pa)
        except ValueError:
            w_sat = np.inf
        omega[i] = min(w, w_sat)
    return T_C, omega


def _estado(nombre: str, T_K: float, omega: float, P_Pa: float) -> EstadoPsicro:
    """Construye un EstadoPsicro desde (T_K, ω) calculando HR y h."""
    hr = HR_desde_omega(omega, T_K, P_Pa)
    h = entalpia_aire_humedo(T_K, omega)
    return EstadoPsicro(nombre=nombre, T_C=T_K - 273.15, omega_kg_kg=omega, HR=hr, h_J_kg=h)


def _colapsar(estados: list[EstadoPsicro]) -> list[EstadoPsicro]:
    """Elimina estados consecutivos casi idénticos (sin colector / sin auxiliar
    el calentamiento sensible no agrega un punto nuevo). Conserva el primero y
    el último siempre."""
    if len(estados) <= 1:
        return estados
    out = [estados[0]]
    for e in estados[1:]:
        prev = out[-1]
        igual = (
            abs(e.T_C - prev.T_C) < _TOL_T_C and abs(e.omega_kg_kg - prev.omega_kg_kg) < _TOL_OMEGA
        )
        if igual:
            out[-1] = e  # mantener la etiqueta más avanzada del proceso
        else:
            out.append(e)
    return out


def _idx_repr_forzantes(forzantes) -> int:
    """Índice representativo en las forzantes: hora de POA máxima (≈ mediodía
    solar / pico de operación). Fallback: máxima T_ent; luego el punto medio."""
    poa = getattr(forzantes, "I_g_POA_W_m2", None)
    if poa is not None and len(poa) > 0 and np.any(np.isfinite(poa)):
        return int(np.nanargmax(poa))
    T_ent = getattr(forzantes, "T_ent_K", None)
    if T_ent is not None and len(T_ent) > 0:
        return int(np.nanargmax(T_ent))
    return 0


def _idx_camara_en_tiempo(camara, t_repr_s: float) -> int:
    """Índice de la trayectoria de cámara más cercano a ``t_repr_s``.

    La trayectoria de cámara tiene su propia base temporal (``t_array_s``,
    pasos del integrador), distinta de la base horaria de las forzantes.
    """
    t_arr = getattr(camara, "t_array_s", None)
    if t_arr is None or len(t_arr) == 0:
        return 0
    return int(np.argmin(np.abs(np.asarray(t_arr, dtype=float) - t_repr_s)))


def _camara_es_directa(camara) -> bool:
    """True si la cámara recibe radiación (techo translúcido): Q_rad > 0."""
    q_rad = getattr(camara, "Q_rad_W", None)
    if q_rad is None or len(q_rad) == 0:
        return False
    return bool(np.nanmax(q_rad) > 1.0)


def _idx_inlet(estados: list[EstadoPsicro]) -> int:
    """Índice del estado de entrada a la cámara/túnel (para la isentálpica de
    referencia). El penúltimo estado salvo que haya una etiqueta "Entrada …"."""
    for i, e in enumerate(estados):
        if e.nombre.startswith("Entrada"):
            return i
    return max(0, len(estados) - 2)


def _estados_ventana(res: Any, P_Pa: float) -> Optional[dict[str, Any]]:
    """Estados del proceso para el modo Ventana (gran escala).

    BATCH: Ambiente → Entrada cámara → Salida cámara (lote representativo).
    SEMICONTINUO: Ambiente → Entrada túnel → path del aire por las zonas (la
    zona N−1 recibe el aire caliente/seco y la 0 lo descarga húmedo).
    """
    T_amb = getattr(res, "aire_T_amb_K", None)
    T_ent = getattr(res, "aire_T_ent_K", None)
    omega = getattr(res, "aire_omega_ent", None)
    if T_amb is None or T_ent is None or omega is None:
        return None

    perfil_T = getattr(res, "perfil_T_aire_zonas_K", None)
    perfil_w = getattr(res, "perfil_omega_aire_zonas", None)
    tiene_perfil = (
        perfil_T is not None
        and perfil_w is not None
        and len(perfil_T) == len(perfil_w)
        and len(perfil_T) > 0
    )

    if tiene_perfil:
        # SEMICONTINUO: el aire entra por la zona N−1 (caliente/seca) y sale por
        # la zona 0 (fría/húmeda) → se recorre el perfil en sentido N−1 → 0. Las
        # zonas NO se colapsan: son puntos espaciales distintos del túnel, aunque
        # sean termodinámicamente próximos.
        n = len(perfil_T)
        estados = [
            _estado("Ambiente", T_amb, omega, P_Pa),
            _estado("Entrada túnel", T_ent, omega, P_Pa),
        ]
        for k in range(n - 1, -1, -1):
            if k == 0:
                etq = "Salida túnel"
            elif n <= 8 or k == n - 1:
                etq = f"Zona {k}"
            else:
                etq = ""
            estados.append(_estado(etq, float(perfil_T[k]), float(perfil_w[k]), P_Pa))
    else:
        # BATCH: salida de cámara representativa (capturada en simulación).
        T_out = getattr(res, "aire_T_salida_K", None)
        w_out = getattr(res, "aire_omega_salida", None)
        if T_out is None or w_out is None:
            return None
        estados = _colapsar(
            [
                _estado("Ambiente", T_amb, omega, P_Pa),
                _estado("Entrada cámara", T_ent, omega, P_Pa),
                _estado("Salida cámara", float(T_out), float(w_out), P_Pa),
            ]
        )

    return {
        "estados": estados,
        "camara_directa": bool(getattr(res, "camara_directa", False)),
        "idx_inlet": _idx_inlet(estados),
    }


def estados_proceso(
    res: Any,
    *,
    P_Pa: float,
    omega_amb: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Extrae los estados del proceso desde un resultado del balance global.

    Soporta los tres modos:
        - **Constantes** (``ResultadosCompletos``): T's escalares + ω del llamador.
        - **Transitorio** (``ResultadosCompletosTransitorio``): índice de POA máx.
        - **Ventana** (``ResultadoVentana``, gran escala): BATCH = 3 estados;
          SEMICONTINUO = entrada + path del aire por las zonas del túnel.

    Args:
        res: Resultado del balance global.
        P_Pa: Presión representativa [Pa].
        omega_amb: Humedad absoluta ambiente/entrada [kg/kg]. Requerida solo en
            modo Constantes (donde no hay forzantes con ω).

    Returns:
        dict con ``estados`` (list[EstadoPsicro]), ``camara_directa`` (bool) e
        ``idx_inlet`` (índice del estado de entrada a la cámara/túnel), o
        ``None`` si el resultado no permite construir el proceso.
    """
    # --- Ventana (gran escala): se detecta por el atributo ``subtipo``. ---
    if getattr(res, "subtipo", None) is not None:
        return _estados_ventana(res, P_Pa)

    camara = getattr(res, "camara", None)
    if camara is None:
        return None

    # --- Transitorio: tiene forzantes base (salida colector) y aplicadas
    #     (entrada cámara, con auxiliar) ---
    fa = getattr(res, "forzantes_aplicadas", None)
    fb = getattr(res, "forzantes_base", None)
    if fa is not None:
        idx = _idx_repr_forzantes(fa)
        omega = float(fa.omega_ent[idx])
        T_amb_K = float(fa.T_amb_K[idx])
        T_col_K = float(fb.T_ent_K[idx]) if fb is not None else T_amb_K
        T_cam_in_K = float(fa.T_ent_K[idx])
        t_repr_s = float(fa.t_s[idx])
        idx_c = _idx_camara_en_tiempo(camara, t_repr_s)
        T_cam_out_K = float(np.asarray(camara.T_flujo_K)[idx_c])
        omega_out = float(np.asarray(camara.omega_flujo_kg_kg)[idx_c])

        estados = _colapsar(
            [
                _estado("Ambiente", T_amb_K, omega, P_Pa),
                _estado("Salida colector", T_col_K, omega, P_Pa),
                _estado("Entrada cámara", T_cam_in_K, omega, P_Pa),
                _estado("Salida cámara", T_cam_out_K, omega_out, P_Pa),
            ]
        )
        return {
            "estados": estados,
            "camara_directa": _camara_es_directa(camara),
            "idx_inlet": _idx_inlet(estados),
        }

    # --- Constantes: T's escalares desde el resultado; ω de entrada del llamador ---
    if omega_amb is None:
        return None

    colector = getattr(res, "colector", None)
    T_cam_in_K = getattr(res, "T_entrada_camara_K", None)
    if T_cam_in_K is None:
        return None
    T_cam_in_K = float(T_cam_in_K)

    if colector is not None:
        T_amb_K = float(getattr(colector, "T_entrada_K", T_cam_in_K))
        T_col_K = float(
            getattr(colector, "T_salida_K", getattr(colector, "T_salida_mezcla_K", T_cam_in_K))
        )
    else:
        # CAJA: sin colector externo, el aire llega a la cámara a T ambiente.
        T_amb_K = T_cam_in_K
        T_col_K = T_cam_in_K

    # Salida de cámara: representativa = instante de máxima evaporación.
    m_dot_w = np.asarray(getattr(camara, "m_dot_w_kg_s", []), dtype=float)
    if m_dot_w.size > 0 and np.any(np.isfinite(m_dot_w)):
        idx_c = int(np.nanargmax(m_dot_w))
    else:
        idx_c = -1
    T_cam_out_K = float(np.asarray(camara.T_flujo_K)[idx_c])
    omega_out = float(np.asarray(camara.omega_flujo_kg_kg)[idx_c])

    estados = _colapsar(
        [
            _estado("Ambiente", T_amb_K, omega_amb, P_Pa),
            _estado("Salida colector", T_col_K, omega_amb, P_Pa),
            _estado("Entrada cámara", T_cam_in_K, omega_amb, P_Pa),
            _estado("Salida cámara", T_cam_out_K, omega_out, P_Pa),
        ]
    )
    return {
        "estados": estados,
        "camara_directa": _camara_es_directa(camara),
        "idx_inlet": _idx_inlet(estados),
    }
