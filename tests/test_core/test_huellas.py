"""Huella de entradas (core/huellas.py) — pieza pura del mecanismo de vigencia.

Cubre la firma barata del clima y que ``huella_entradas`` reaccione a lo que
determina un resultado: presencia/ausencia de secciones, cambios internos,
extras y la serie climática.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.camara import Camara, CargaProducto, GeometriaCamara
from core.clima import Clima
from core.huellas import FirmaClima, firma_clima, huella_entradas
from core.proyecto import Configuracion, Proyecto, Tipologia


def _proyecto() -> Proyecto:
    p = Proyecto(configuracion=Configuracion(tipologia=Tipologia.ARMARIO))
    p.camara = Camara(
        geometria=GeometriaCamara(largo_m=2.0, ancho_m=1.0, alto_m=1.5),
        carga_producto=CargaProducto(producto_id="manzana"),
    )
    return p


def _clima_df(n: int = 48, ghi0: float = 500.0) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    horas = np.array([t.hour for t in idx], dtype=float)
    return pd.DataFrame(
        {
            "GHI_Wm2": np.maximum(0.0, ghi0 * np.cos((horas - 12) / 24 * 2 * np.pi)),
            "T_amb_K": 288.0 + 5.0 * np.sin(horas / 24 * 2 * np.pi),
        },
        index=idx,
    )


class TestFirmaClima:
    def test_sin_clima_es_la_firma_vacia(self):
        assert firma_clima(_proyecto()) == FirmaClima()

    def test_captura_largo_y_sumas(self):
        proy = _proyecto()
        proy.clima = Clima(datos=_clima_df())
        f = firma_clima(proy)
        assert f.n_horas == 48
        assert f.suma_GHI > 0.0

    def test_distinto_clima_distinta_firma(self):
        a, b = _proyecto(), _proyecto()
        a.clima = Clima(datos=_clima_df(ghi0=500.0))
        b.clima = Clima(datos=_clima_df(ghi0=900.0))
        assert firma_clima(a) != firma_clima(b)


class TestHuellaEntradas:
    def test_estable_para_la_misma_config(self):
        assert huella_entradas(_proyecto(), ("camara",)) == huella_entradas(
            _proyecto(), ("camara",)
        )

    def test_una_seccion_ausente_cuenta(self):
        """Agregar una sección que estaba en None cambia la huella: ese es el
        caso del auxiliar configurado después de calcular (S58)."""
        from core.auxiliar import Auxiliar, ModoOperacionAuxiliar, TipoAuxiliar

        proy = _proyecto()
        antes = huella_entradas(proy, ("camara", "auxiliar"))
        proy.auxiliar = Auxiliar(
            tipo=TipoAuxiliar.RESISTENCIA_ELECTRICA,
            modo_operacion=ModoOperacionAuxiliar.SERIE_POSCOLECTOR,
            potencia_nominal_W=2000.0,
            set_point_T_K=328.15,
        )
        assert huella_entradas(proy, ("camara", "auxiliar")) != antes

    def test_cambio_interno_de_seccion_cambia_la_huella(self):
        proy = _proyecto()
        antes = huella_entradas(proy, ("camara",))
        proy.camara.geometria = GeometriaCamara(largo_m=3.0, ancho_m=1.0, alto_m=1.5)
        assert huella_entradas(proy, ("camara",)) != antes

    def test_extras_entran_y_su_orden_no_importa(self):
        proy = _proyecto()
        h1 = huella_entradas(proy, ("camara",), extras={"a": 1, "b": 2})
        h2 = huella_entradas(proy, ("camara",), extras={"b": 2, "a": 1})
        h3 = huella_entradas(proy, ("camara",), extras={"a": 9, "b": 2})
        assert h1 == h2
        assert h1 != h3

    def test_con_clima_false_ignora_la_serie(self):
        proy = _proyecto()
        proy.clima = Clima(datos=_clima_df())
        con = huella_entradas(proy, ("camara",), con_clima=True)
        sin = huella_entradas(proy, ("camara",), con_clima=False)
        assert con != sin
        # Con con_clima=False, cambiar el clima no mueve la huella.
        proy.clima = Clima(datos=_clima_df(ghi0=900.0))
        assert huella_entradas(proy, ("camara",), con_clima=False) == sin

    def test_no_revienta_sin_ninguna_seccion(self):
        assert isinstance(huella_entradas(Proyecto(), ("colector", "auxiliar")), str)
