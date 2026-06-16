"""Tests de calculos/solar_geometria.py."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from calculos.solar_geometria import (
    bin_horario_que_contiene,
    mediodia_solar_transit,
)

# Coordenadas Salta capital (referencia del proyecto).
_LAT_SALTA = -24.7821
_LON_SALTA = -65.4232
_TZ_SALTA = "America/Argentina/Salta"


class TestMediodiaSolarTransit:
    """El tránsito SPA debe caer cerca de 13:15-13:25 hora local en Salta
    todos los días del año (ecuación del tiempo varía ±15 min)."""

    @pytest.mark.parametrize(
        "fecha,hora_min,hora_max",
        [
            # (fecha, rango aceptable [hh, mm] - [hh, mm])
            (date(2020, 12, 21), (13, 0), (13, 35)),  # solsticio verano
            (date(2020, 6, 21), (13, 0), (13, 35)),  # solsticio invierno
            (date(2020, 3, 21), (12, 50), (13, 30)),  # equinoccio marzo
            (date(2020, 9, 23), (12, 50), (13, 30)),  # equinoccio septiembre
        ],
    )
    def test_transit_salta_en_rango_esperado(self, fecha, hora_min, hora_max):
        transit = mediodia_solar_transit(fecha, _LAT_SALTA, _LON_SALTA, _TZ_SALTA)
        h, m = transit.hour, transit.minute
        assert (h, m) >= hora_min, f"{transit} antes de {hora_min}"
        assert (h, m) <= hora_max, f"{transit} después de {hora_max}"

    def test_transit_es_tz_aware(self):
        transit = mediodia_solar_transit(
            date(2020, 12, 21),
            _LAT_SALTA,
            _LON_SALTA,
            _TZ_SALTA,
        )
        assert transit.tz is not None
        assert str(transit.tz) == _TZ_SALTA

    def test_acepta_string(self):
        t1 = mediodia_solar_transit("2020-12-21", _LAT_SALTA, _LON_SALTA, _TZ_SALTA)
        t2 = mediodia_solar_transit(
            date(2020, 12, 21),
            _LAT_SALTA,
            _LON_SALTA,
            _TZ_SALTA,
        )
        assert t1 == t2

    def test_acepta_timestamp(self):
        t1 = mediodia_solar_transit(
            pd.Timestamp("2020-12-21"),
            _LAT_SALTA,
            _LON_SALTA,
            _TZ_SALTA,
        )
        t2 = mediodia_solar_transit(
            date(2020, 12, 21),
            _LAT_SALTA,
            _LON_SALTA,
            _TZ_SALTA,
        )
        assert t1 == t2

    def test_no_depende_de_orientacion_del_colector(self):
        """El tránsito SPA es geométrico — no debe variar por nada del colector.

        Tautología pero documenta la diferencia con idxmax(POA): sólo lat,
        lon y fecha lo afectan. Acá sólo verificamos que la función no
        acepta argumentos extra del colector — defensa de signatura.
        """
        # No hay forma de pasar pendiente/acimut a la función → ya está protegido.
        # Este test sirve más como documentación que como verificación.
        sig = mediodia_solar_transit.__annotations__
        assert "pendiente" not in sig
        assert "acimut" not in sig


class TestBinHorarioQueContiene:

    @pytest.fixture
    def indice_horario_dia(self):
        """24 bins horarios del 21 dic 2020 en hora Salta."""
        return pd.date_range(
            "2020-12-21 00:00",
            "2020-12-21 23:00",
            freq="h",
            tz=_TZ_SALTA,
        )

    def test_13_20_cae_en_bin_13(self, indice_horario_dia):
        """Convención [t, t+1h): 13:20 está en el bin 13:00."""
        t = pd.Timestamp("2020-12-21 13:20:00", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t.hour == 13
        assert bin_t.minute == 0

    def test_13_00_cae_en_bin_13(self, indice_horario_dia):
        """Borde inclusivo: 13:00:00 cae en el bin 13:00."""
        t = pd.Timestamp("2020-12-21 13:00:00", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t.hour == 13

    def test_13_59_cae_en_bin_13(self, indice_horario_dia):
        """Borde superior exclusivo: 13:59:59 sigue en el bin 13:00."""
        t = pd.Timestamp("2020-12-21 13:59:59", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t.hour == 13

    def test_14_00_cae_en_bin_14(self, indice_horario_dia):
        """14:00:00 ya cae en el bin siguiente."""
        t = pd.Timestamp("2020-12-21 14:00:00", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t.hour == 14

    def test_antes_del_indice_devuelve_primero(self, indice_horario_dia):
        t = pd.Timestamp("2020-12-20 23:00:00", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t == indice_horario_dia[0]

    def test_despues_del_indice_devuelve_ultimo(self, indice_horario_dia):
        t = pd.Timestamp("2020-12-22 05:00:00", tz=_TZ_SALTA)
        bin_t = bin_horario_que_contiene(t, indice_horario_dia)
        assert bin_t == indice_horario_dia[-1]

    def test_indice_vacio_levanta(self):
        idx_vacio = pd.DatetimeIndex([], tz=_TZ_SALTA)
        with pytest.raises(ValueError, match="BIN_INDICE_VACIO"):
            bin_horario_que_contiene(
                pd.Timestamp("2020-12-21 13:00", tz=_TZ_SALTA),
                idx_vacio,
            )
