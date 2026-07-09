"""Selector de espesores con medidas de mercado (mejoras 25 y 26).

Las maderas de tablero se venden en pulgadas y submúltiplos; el policarbonato
alveolar en 4/6/8/10/16 mm. Este helper centraliza un selector que ofrece las
medidas estándar disponibles en mercado más una opción ``Otro
(personalizado)…`` que revela el ``number_input`` libre (coherente con el patrón
"Definido por el usuario" de los materiales). Lo consumen P3 (cubierta y fondo)
y P4 (capas de pared).
"""

from __future__ import annotations

import streamlit as st

# Materiales de madera del catálogo ``fondos.yaml``. Se venden en pulgadas; el
# resto de los fondos (chapa) usan otras medidas y mantienen el input libre.
MATERIALES_MADERA: frozenset[str] = frozenset({"pino", "contrachapado_fenolico"})

# Espesores estándar de tableros de madera disponibles en mercado: (mm, rótulo).
# El mm es el valor exacto; el rótulo muestra la pulgada equivalente. Editable.
ESPESORES_MADERA_MM: list[tuple[float, str]] = [
    (6.35, '6.4 mm — 1/4"'),
    (9.53, '9.5 mm — 3/8"'),
    (12.7, '12.7 mm — 1/2"'),
    (15.88, '15.9 mm — 5/8"'),
    (18.0, "18 mm — placa métrica"),
    (19.05, '19.0 mm — 3/4"'),
    (25.4, '25.4 mm — 1"'),
    (31.75, '31.8 mm — 1¼"'),
    (38.1, '38.1 mm — 1½"'),
    (50.8, '50.8 mm — 2"'),
]

_OTRO = "__otro__"


def selector_espesor_mm(
    label: str,
    espesor_actual_m: float,
    key: str,
    *,
    opciones_mm: list[tuple[float, str]] | None = None,
    min_mm: float = 0.3,
    max_mm: float = 100.0,
    step: float = 0.5,
    tol_mm: float = 0.1,
) -> float:
    """Selector de espesor con medidas de mercado + escape ``Otro``.

    Si ``opciones_mm`` es ``None`` expone un ``number_input`` libre
    (comportamiento histórico). Si se pasan opciones expone un ``selectbox`` con
    las medidas estándar más ``Otro (personalizado)…`` al final, que revela el
    input libre.

    Args:
        label: Rótulo del widget.
        espesor_actual_m: Espesor previo [m], usado para preseleccionar.
        key: Clave base de los widgets de Streamlit (única por sección).
        opciones_mm: Medidas estándar ``(mm, etiqueta)``. ``None`` → input libre.
        min_mm: Mínimo del input libre [mm].
        max_mm: Máximo del input libre [mm].
        step: Paso del input libre [mm].
        tol_mm: Tolerancia para reconocer el espesor previo como una opción [mm].

    Returns:
        Espesor seleccionado [mm].
    """
    espesor_actual_mm = espesor_actual_m * 1000.0
    valor_seed = float(min(max(espesor_actual_mm, min_mm), max_mm))

    if not opciones_mm:
        return st.number_input(
            label,
            min_value=min_mm,
            max_value=max_mm,
            value=valor_seed,
            step=step,
            key=key,
        )

    from ui.componentes.idiomas import t

    valores = [mm for mm, _ in opciones_mm]
    etiquetas: dict[object, str] = {mm: et for mm, et in opciones_mm}
    etiquetas[_OTRO] = t("comun.espesor.otro")
    opciones: list[object] = [*valores, _OTRO]

    # ¿El espesor previo coincide con una medida estándar (dentro de tolerancia)?
    coincidencia = next((mm for mm in valores if abs(mm - espesor_actual_mm) <= tol_mm), None)
    idx = opciones.index(coincidencia) if coincidencia is not None else opciones.index(_OTRO)

    seleccion = st.selectbox(
        label,
        options=opciones,
        index=idx,
        format_func=lambda o: etiquetas[o],
        key=f"{key}_sel",
    )
    if seleccion == _OTRO:
        return st.number_input(
            t("comun.espesor.personalizado"),
            min_value=min_mm,
            max_value=max_mm,
            value=valor_seed,
            step=step,
            key=f"{key}_otro",
        )
    return float(seleccion)
