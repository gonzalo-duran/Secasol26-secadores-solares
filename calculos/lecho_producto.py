"""Re-export de ``core.lecho`` por compatibilidad.

La geometría del lecho se mudó a ``core/lecho.py`` en S64: ``Camara.__post_init__``
la necesita para derivar el espesor de capa de la carga uniforme, y ``core/`` no
puede importar de ``calculos/`` sin invertir las capas del proyecto. Este módulo
existe para que los consumidores de ``calculos/`` sigan importando desde donde ya
lo hacían. Mismo patrón que ``calculos/simulacion_ventana`` con ``PoliticaRecarga``.
"""

from __future__ import annotations

from core.lecho import (
    AREA_ABIERTA_DEFAULT,
    AREA_ABIERTA_MALLA,
    D_P_DEFAULT_M,
    EPSILON_DEFAULT,
    PHI_S_DEFAULT,
    area_abierta_malla_efectiva,
    d_p_es_default,
    espesor_capa_derivado_m,
    geometria_lecho,
    masa_que_llena_el_lecho_kg,
    volumen_lecho_m3,
)

__all__ = [
    "AREA_ABIERTA_DEFAULT",
    "AREA_ABIERTA_MALLA",
    "D_P_DEFAULT_M",
    "EPSILON_DEFAULT",
    "PHI_S_DEFAULT",
    "area_abierta_malla_efectiva",
    "d_p_es_default",
    "espesor_capa_derivado_m",
    "geometria_lecho",
    "masa_que_llena_el_lecho_kg",
    "volumen_lecho_m3",
]
