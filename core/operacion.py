"""
Configuración de operación del secador — cómo lo maneja el operador.

Separa las decisiones de **operación** (a qué hora se carga, si se mira el cielo
antes de llenar) de la descripción **física** del equipo (`core/camara.py`,
`core/colector.py`) y del escenario de **análisis** (tipología, modo, ventana).

Vive en `core/` y no en `calculos/` porque forma parte del modelo de datos: cuelga
de `Configuracion.politica_recarga`, viaja en el snapshot `.json` del proyecto y
entra en la huella de vigencia del resultado anual. `calculos/simulacion_ventana.py`
—que es quien la consume— la reexporta por compatibilidad, porque nació ahí en S57
antes de que hubiera un proyecto que la persistiera.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PoliticaRecarga:
    """Cuándo se carga el lote siguiente después de descargar el anterior.

    Sin política, el encadenado recarga **en el instante exacto** en que termina
    el lote previo: si uno cierra a las 3 de la madrugada, el siguiente arranca
    a las 3 de la madrugada y quema horas sin sol hasta que amanezca. Ningún
    operador hace eso — descarga y recarga de mañana. Modelar la espera baja la
    producción hacia lo realista (S57, a pedido del usuario).

    Además del *cuándo* horario, la política cubre el **si conviene cargar**: un
    operador no llena el secador un día que viene nublado. Ver
    ``exigir_pronostico`` y ``calculos.simulacion_ventana._energia_diaria_POA``.

    La consumen los dos pipelines que encadenan lotes sobre clima real: el modo
    ANUAL (``calculos.simulacion_anual.simular_anual``) y el modo VENTANA de gran
    escala (``calculos.balance_global.calcular_todo_ventana``). Ambos la leen de
    ``proyecto.configuracion.politica_recarga``, así que la misma operación rige
    los dos y sobrevive a un guardar/cargar del proyecto (S59).

    Attributes:
        activa: Si es False se conserva el encadenado inmediato (cota superior).
        hora_carga_h: Hora local del día en que se cargan los lotes [0, 24).
        maniobra_h: Tiempo de descarga + recarga [h]. El lote siguiente no puede
            empezar antes de ``t_fin + maniobra_h``, y además debe caer en la
            hora de carga.
        exigir_pronostico: Si es True, un lote solo se carga cuando la
            irradiación del **día de carga** sobre el plano del colector supera
            ``umbral_pronostico_MJ_m2``; si no, se espera al día siguiente. Con
            False se carga siempre, que era el comportamiento hasta S58.
        umbral_pronostico_MJ_m2: Irradiación diaria mínima en el plano del
            colector para decidir cargar [MJ/m²·día].

    Note:
        **El pronóstico es perfecto.** La decisión se toma con la irradiación
        que el día efectivamente va a tener, no con una predicción con error.
        Es una idealización deliberada (elegida por el usuario en S58): da la
        **cota superior de la buena decisión** —el operador que nunca se
        equivoca— y por lo tanto sobrestima levemente la producción respecto de
        una operación real, que carga algún día que sale nublado y saltea algún
        día que sale bueno. El sentido del sesgo es opuesto al de ``activa`` y
        ambos son chicos frente a la variabilidad interanual del recurso.
    """

    activa: bool = True
    hora_carga_h: float = 8.0
    maniobra_h: float = 1.0
    exigir_pronostico: bool = True
    umbral_pronostico_MJ_m2: float = 8.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.hora_carga_h < 24.0):
            raise ValueError(
                f"RECARGA_HORA_INVALIDA: hora_carga_h={self.hora_carga_h} fuera de [0, 24)."
            )
        if self.maniobra_h < 0.0:
            raise ValueError(f"RECARGA_MANIOBRA_NEGATIVA: maniobra_h={self.maniobra_h} < 0.")
        if self.umbral_pronostico_MJ_m2 < 0.0:
            raise ValueError(
                f"RECARGA_UMBRAL_NEGATIVO: umbral_pronostico_MJ_m2="
                f"{self.umbral_pronostico_MJ_m2} < 0."
            )

    def a_dict(self) -> dict[str, float | bool]:
        """Serializa a un dict JSON-able (snapshot del proyecto)."""
        return {
            "activa": self.activa,
            "hora_carga_h": self.hora_carga_h,
            "maniobra_h": self.maniobra_h,
            "exigir_pronostico": self.exigir_pronostico,
            "umbral_pronostico_MJ_m2": self.umbral_pronostico_MJ_m2,
        }

    @classmethod
    def desde_dict(cls, datos: dict | None) -> "PoliticaRecarga":
        """Reconstruye desde el dict de :meth:`a_dict`.

        Los snapshots anteriores a S59 no traen el bloque; en ese caso se
        devuelven los defaults, que son los que esas corridas usaron de hecho.
        Las claves desconocidas se ignoran.

        Raises:
            ValueError: propaga la validación de ``__post_init__`` si algún
                valor del snapshot está fuera de rango.
        """
        if not datos:
            return cls()
        campos = {f: datos[f] for f in cls.__dataclass_fields__ if f in datos}
        return cls(
            activa=bool(campos.get("activa", True)),
            hora_carga_h=float(campos.get("hora_carga_h", 8.0)),
            maniobra_h=float(campos.get("maniobra_h", 1.0)),
            exigir_pronostico=bool(campos.get("exigir_pronostico", True)),
            umbral_pronostico_MJ_m2=float(campos.get("umbral_pronostico_MJ_m2", 8.0)),
        )
