"""Tests unitarios para calculos/correlaciones_nusselt.py.

Estrategia
----------
1. Tests de valor exacto o aproximado contra referencias bibliográficas.
2. Tests de invariantes físicas (Nu ≥ 1, monotonicidad, continuidad).
3. Tests de selección automática: verificar qué correlación se elige
   según Re, L/Dh y tipo de pared.
4. Tests de advertencias: verificar que se emiten los códigos correctos.
5. Tests de la función principal calcular_h_int().

Valores de referencia
---------------------
Los valores de Nu de referencia se calcularon con las expresiones
explícitas de cada correlación (no son mediciones experimentales).
El objetivo es detectar regresiones en la implementación.
"""

from __future__ import annotations

import math

import pytest

from calculos.correlaciones_nusselt import (
    CORRELACIONES_FORZADO,
    CORRELACIONES_NATURAL,
    K_AIRE,
    PR_AIRE,
    RE_LAMINAR_MAX,
    RE_TURBULENTO_MIN,
    calcular_h_int,
    nusselt_cengel,
    nusselt_dittus_boelter,
    nusselt_forzado_local,
    nusselt_gnielinski,
    nusselt_heaton,
    nusselt_hollands_inclinada,
    nusselt_mixto_local,
    nusselt_natural_canal,
    nusselt_shah_london,
    nusselt_shah_london_simetrico,
    nusselt_sparrow_liu,
)

# Tolerancia relativa para comparaciones numéricas
RTOL = 1e-6


def casi_igual(a, b, rtol=RTOL):
    return abs(a - b) <= rtol * abs(b) + 1e-12


# =============================================================================
# 1. Shah & London — laminar, una pared caliente
# =============================================================================


class TestShahLondon:

    def test_valor_exacto(self):
        """Nu = 5.385 exacto."""
        assert casi_igual(nusselt_shah_london(1000.0, PR_AIRE), 5.385)

    def test_independiente_de_Re_y_Pr(self):
        """Nu no depende de Re ni Pr (solución analítica exacta)."""
        Nu1 = nusselt_shah_london(500.0, 0.5)
        Nu2 = nusselt_shah_london(2000.0, 0.9)
        assert casi_igual(Nu1, Nu2)

    def test_error_fuera_de_rango(self):
        """Lanza ValueError para Re ≥ 2300."""
        with pytest.raises(ValueError, match="Shah & London"):
            nusselt_shah_london(2300.0, PR_AIRE)

    def test_positivo(self):
        assert nusselt_shah_london(1000.0, PR_AIRE) > 0.0


class TestShahLondonSimetrico:

    def test_valor_exacto(self):
        """Nu = 8.235 exacto."""
        assert casi_igual(nusselt_shah_london_simetrico(1000.0, PR_AIRE), 8.235)

    def test_mayor_que_asimetrico(self):
        """Nu simétrico > Nu asimétrico (ambas paredes calientes → más transferencia)."""
        Nu_sim = nusselt_shah_london_simetrico(1000.0, PR_AIRE)
        Nu_asim = nusselt_shah_london(1000.0, PR_AIRE)
        assert Nu_sim > Nu_asim

    def test_error_fuera_de_rango(self):
        with pytest.raises(ValueError):
            nusselt_shah_london_simetrico(2500.0, PR_AIRE)


# =============================================================================
# 2. Heaton — laminar, entrada térmica
# =============================================================================


class TestHeaton:

    def test_converge_hacia_shah_london_al_aumentar_L(self):
        """A mayor L, Heaton → Shah & London (monotonía descendente hacia 5.385).

        La fórmula Nu = 5.385·(1 + 0.0668·Gz^{2/3}) con Gz = Re·Pr·Dh/L
        converge asintóticamente a 5.385 solo cuando L → ∞. La convergencia
        es lenta (proporcional a L^{-2/3}), por lo que verificamos que:
        1. Nu(L=100) > Nu(L=10) > Nu(L=1) — monotonicidad correcta.
        2. Nu(L grande) se acerca a 5.385 (límite inferior es 5.385).
        """
        Dh = 0.05
        Nu_L1 = nusselt_heaton(1000.0, PR_AIRE, 1.0, Dh)
        Nu_L10 = nusselt_heaton(1000.0, PR_AIRE, 10.0, Dh)
        Nu_L100 = nusselt_heaton(1000.0, PR_AIRE, 100.0, Dh)
        assert Nu_L1 > Nu_L10 > Nu_L100 > 5.385, (
            f"Monotonicidad rota: Nu(1)={Nu_L1:.3f}, Nu(10)={Nu_L10:.3f}, "
            f"Nu(100)={Nu_L100:.3f}, límite=5.385"
        )

    def test_mayor_que_shah_london_canal_corto(self):
        """Para L/Dh < 50, Heaton > Shah & London (efectos de entrada)."""
        Dh = 0.05
        L = 1.0  # L/Dh = 20 < 50
        Nu_heaton = nusselt_heaton(1000.0, PR_AIRE, L, Dh)
        Nu_sl = nusselt_shah_london(1000.0, PR_AIRE)
        assert Nu_heaton > Nu_sl

    def test_valor_referencia(self):
        """Nu calculado a mano: Gz = 1000*0.703*0.05/1.0 = 35.15 → Nu = 5.385*(1+0.0668*35.15^{2/3})."""
        Re, Pr, L, Dh = 1000.0, 0.703, 1.0, 0.05
        Gz = Re * Pr * Dh / L
        Nu_esperado = 5.385 * (1.0 + 0.0668 * Gz ** (2.0 / 3.0))
        assert casi_igual(nusselt_heaton(Re, Pr, L, Dh), Nu_esperado)

    def test_monotono_en_L(self):
        """Mayor L → menor Nu (perfil más desarrollado)."""
        Dh = 0.05
        Nu_corto = nusselt_heaton(1000.0, PR_AIRE, 0.5, Dh)
        Nu_largo = nusselt_heaton(1000.0, PR_AIRE, 5.0, Dh)
        assert Nu_corto > Nu_largo

    def test_error_fuera_de_rango_Re(self):
        with pytest.raises(ValueError, match="Heaton"):
            nusselt_heaton(3000.0, PR_AIRE, 1.0, 0.05)

    def test_error_L_negativo(self):
        with pytest.raises(ValueError):
            nusselt_heaton(1000.0, PR_AIRE, -1.0, 0.05)


# =============================================================================
# 3. Gnielinski — transición
# =============================================================================


class TestGnielinski:

    def test_valor_referencia_Re5000(self):
        """Nu a Re=5000, Pr=0.703: calculado con la fórmula explícita."""
        Re, Pr = 5000.0, 0.703
        f = (0.790 * math.log(Re) - 1.64) ** (-2)
        Nu_esp = (
            (f / 8.0)
            * (Re - 1000.0)
            * Pr
            / (1.0 + 12.7 * math.sqrt(f / 8.0) * (Pr ** (2.0 / 3.0) - 1.0))
        )
        assert casi_igual(nusselt_gnielinski(Re, Pr), Nu_esp)

    def test_crece_con_Re(self):
        """Nu aumenta con Re."""
        Nu1 = nusselt_gnielinski(3000.0, PR_AIRE)
        Nu2 = nusselt_gnielinski(8000.0, PR_AIRE)
        assert Nu2 > Nu1

    def test_positivo(self):
        assert nusselt_gnielinski(5000.0, PR_AIRE) > 0.0

    def test_error_Re_bajo(self):
        with pytest.raises(ValueError, match="Gnielinski"):
            nusselt_gnielinski(2000.0, PR_AIRE)

    def test_continuidad_con_turbulento_en_10000(self):
        """Gnielinski y Dittus-Boelter no deben diferir más del 20% en Re=10000."""
        Nu_g = nusselt_gnielinski(10000.0, PR_AIRE)
        Nu_db = nusselt_dittus_boelter(10000.0, PR_AIRE)
        diferencia = abs(Nu_g - Nu_db) / Nu_db
        assert diferencia < 0.20, f"Salto Gnielinski→Dittus-Boelter en Re=10000: {diferencia:.1%}"


# =============================================================================
# 4. Dittus-Boelter — turbulento clásico
# =============================================================================


class TestDittusBoelter:

    def test_valor_referencia_Re20000(self):
        """Nu = 0.023 * 20000^0.8 * 0.703^0.4."""
        Re, Pr = 20000.0, 0.703
        Nu_esp = 0.023 * Re**0.8 * Pr**0.4
        assert casi_igual(nusselt_dittus_boelter(Re, Pr), Nu_esp)

    def test_crece_con_Re(self):
        Nu1 = nusselt_dittus_boelter(10000.0, PR_AIRE)
        Nu2 = nusselt_dittus_boelter(50000.0, PR_AIRE)
        assert Nu2 > Nu1

    def test_error_Re_bajo(self):
        with pytest.raises(ValueError, match="Dittus-Boelter"):
            nusselt_dittus_boelter(5000.0, PR_AIRE)

    def test_positivo(self):
        assert nusselt_dittus_boelter(20000.0, PR_AIRE) > 0.0


# =============================================================================
# 5. Sparrow & Liu — turbulento, una pared caliente
# =============================================================================


class TestSparrowLiu:

    def test_valor_referencia_Re20000(self):
        """Nu = 0.0158 * 20000^0.8."""
        Re = 20000.0
        Nu_esp = 0.0158 * Re**0.8
        assert casi_igual(nusselt_sparrow_liu(Re, PR_AIRE), Nu_esp)

    def test_menor_que_dittus_boelter(self):
        """Sparrow-Liu da Nu menor que Dittus-Boelter (una pared vs dos)."""
        Re = 20000.0
        Nu_sl = nusselt_sparrow_liu(Re, PR_AIRE)
        Nu_db = nusselt_dittus_boelter(Re, PR_AIRE)
        assert Nu_sl < Nu_db

    def test_error_Re_bajo(self):
        with pytest.raises(ValueError, match="Sparrow"):
            nusselt_sparrow_liu(5000.0, PR_AIRE)

    def test_crece_con_Re(self):
        Nu1 = nusselt_sparrow_liu(10000.0, PR_AIRE)
        Nu2 = nusselt_sparrow_liu(40000.0, PR_AIRE)
        assert Nu2 > Nu1


# =============================================================================
# 6. Cengel — turbulento con corrección de entrada
# =============================================================================


class TestCengel:

    def test_valor_referencia(self):
        """Nu = 0.023*Re^0.8*Pr^0.4*(1+(Dh/L)^0.7)."""
        Re, Pr, L, Dh = 20000.0, 0.703, 0.5, 0.05
        Nu_esp = 0.023 * Re**0.8 * Pr**0.4 * (1.0 + (Dh / L) ** 0.7)
        assert casi_igual(nusselt_cengel(Re, Pr, L, Dh), Nu_esp)

    def test_converge_a_dittus_boelter_largo_largo(self):
        """Para L >> Dh, Cengel → Dittus-Boelter."""
        Re, Pr = 20000.0, PR_AIRE
        Dh = 0.05
        L = 1000.0  # L/Dh = 20000
        Nu_c = nusselt_cengel(Re, Pr, L, Dh)
        Nu_db = nusselt_dittus_boelter(Re, Pr)
        assert casi_igual(Nu_c, Nu_db, rtol=1e-3)

    def test_mayor_que_dittus_boelter_canal_corto(self):
        """Para L/Dh pequeño, Cengel > Dittus-Boelter."""
        Re, Pr, Dh = 20000.0, PR_AIRE, 0.05
        L = 0.3  # L/Dh = 6
        Nu_c = nusselt_cengel(Re, Pr, L, Dh)
        Nu_db = nusselt_dittus_boelter(Re, Pr)
        assert Nu_c > Nu_db

    def test_error_Re_bajo(self):
        with pytest.raises(ValueError, match="Cengel"):
            nusselt_cengel(5000.0, PR_AIRE, 1.0, 0.05)

    def test_error_L_negativo(self):
        with pytest.raises(ValueError):
            nusselt_cengel(20000.0, PR_AIRE, -1.0, 0.05)


# =============================================================================
# 7. Hollands — convección natural
# =============================================================================


class TestHollandsInclinada:

    def test_conduccion_pura_Ra_bajo(self):
        """Para Ra·cosθ < 1708: Nu = 1 (solo conducción)."""
        # Ra=100, θ=45°: Ra·cos45° ≈ 71 << 1708
        Nu = nusselt_hollands_inclinada(100.0, 45.0)
        assert casi_igual(Nu, 1.0)

    def test_Nu_minimo_es_uno(self):
        """Nu nunca puede ser < 1."""
        for Ra in [0.0, 1.0, 1000.0]:
            for theta in [0.0, 30.0, 60.0, 75.0]:
                Nu = nusselt_hollands_inclinada(Ra, theta)
                assert Nu >= 1.0, f"Nu={Nu} < 1 para Ra={Ra}, θ={theta}°"

    def test_crece_con_Ra(self):
        """Mayor Ra → mayor Nu (más convección)."""
        Nu1 = nusselt_hollands_inclinada(1e4, 45.0)
        Nu2 = nusselt_hollands_inclinada(1e6, 45.0)
        assert Nu2 > Nu1

    def test_horizontal_Ra_grande(self):
        """Para θ=0° y Ra grande, Nu debe ser > 1."""
        Nu = nusselt_hollands_inclinada(1e5, 0.0)
        assert Nu > 1.0

    def test_Ra_cero(self):
        """Ra = 0 → Nu = 1."""
        assert casi_igual(nusselt_hollands_inclinada(0.0, 45.0), 1.0)

    def test_error_theta_negativo(self):
        with pytest.raises(ValueError, match="theta_deg"):
            nusselt_hollands_inclinada(1e5, -5.0)

    def test_error_theta_mayor_90(self):
        with pytest.raises(ValueError, match="theta_deg"):
            nusselt_hollands_inclinada(1e5, 95.0)

    def test_rango_tipico_colector(self):
        """Para θ=30°, Ra=1e5: Nu en rango físico razonable [1, 10]."""
        Nu = nusselt_hollands_inclinada(1e5, 30.0)
        assert 1.0 <= Nu <= 10.0, f"Nu={Nu:.2f} fuera de rango típico"


# =============================================================================
# 8. Catálogos — integridad
# =============================================================================


class TestCatalogos:

    def test_correlaciones_forzado_tienen_metadatos_completos(self):
        """Todos los campos de CorrelacionNusselt están presentes."""
        for nombre, meta in CORRELACIONES_FORZADO.items():
            assert meta.nombre == nombre
            assert meta.modo == "forzado"
            assert meta.nombre_display != ""
            assert meta.referencia != ""
            assert meta.notas != ""

    def test_correlaciones_natural_tienen_metadatos_completos(self):
        for nombre, meta in CORRELACIONES_NATURAL.items():
            assert meta.nombre == nombre
            assert meta.modo == "natural"
            assert meta.nombre_display != ""

    def test_correlaciones_forzado_esperadas_presentes(self):
        esperadas = {
            "shah_london",
            "shah_london_simetrico",
            "heaton",
            "gnielinski",
            "dittus_boelter",
            "sparrow_liu",
            "cengel",
        }
        assert esperadas.issubset(set(CORRELACIONES_FORZADO.keys()))

    def test_hollands_en_natural(self):
        assert "hollands" in CORRELACIONES_NATURAL


# =============================================================================
# 9. calcular_h_int — selección automática
# =============================================================================


class TestCalcularHInt:
    """Tests de la función principal calcular_h_int()."""

    # Geometría de referencia: colector típico 1m×2m, canal 5 cm
    DH = 2 * 0.05 * 1.0 / (0.05 + 1.0)  # ≈ 0.0952 m
    L = 2.0
    K = K_AIRE
    PR = PR_AIRE

    def _Re(self, target_Re: float) -> float:
        """Devuelve m_punto para Re objetivo (no se usa aquí — Re se pasa directamente)."""
        return target_Re

    # --- Selección automática por régimen ---

    def test_auto_laminar_desarrollado_una_pared(self):
        """Re < 2300, L/Dh > 50, una pared → shah_london."""
        Re = 1000.0
        L = 10.0  # L/Dh = 10/0.0952 ≈ 105 > 50
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, L, self.K, "una_pared", "forzado"
        )
        assert nombre == "shah_london"
        assert regimen == "laminar"
        assert h > 0.0
        assert any("COL_FLUJO_LAMINAR" in a for a in adv)

    def test_auto_laminar_desarrollado_dos_paredes(self):
        """Re < 2300, L/Dh > 50, dos paredes → shah_london_simetrico."""
        Re = 1000.0
        L = 10.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, L, self.K, "dos_paredes", "forzado"
        )
        assert nombre == "shah_london_simetrico"

    def test_auto_laminar_en_desarrollo(self):
        """Re < 2300, L/Dh < 50 → heaton."""
        Re = 1000.0
        L = 0.5  # L/Dh = 0.5/0.0952 ≈ 5.25 < 50
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, L, self.K, "una_pared", "forzado"
        )
        assert nombre == "heaton"

    def test_auto_transicion(self):
        """2300 < Re < 10000 → gnielinski."""
        Re = 5000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, self.L, self.K, "una_pared", "forzado"
        )
        assert nombre == "gnielinski"
        assert regimen == "transicion"

    def test_auto_turbulento_una_pared(self):
        """Re > 10000, L/Dh > 10, una pared → sparrow_liu."""
        Re = 20000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, self.L, self.K, "una_pared", "forzado"
        )
        assert nombre == "sparrow_liu"
        assert regimen == "turbulento"

    def test_auto_turbulento_dos_paredes(self):
        """Re > 10000, dos paredes → dittus_boelter."""
        Re = 20000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, self.L, self.K, "dos_paredes", "forzado"
        )
        assert nombre == "dittus_boelter"

    def test_auto_turbulento_entrada_pronunciada(self):
        """Re > 10000, L/Dh < 10 → cengel."""
        Re = 20000.0
        L = 0.5  # L/Dh = 0.5/0.0952 ≈ 5.25 < 10
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, L, self.K, "una_pared", "forzado"
        )
        assert nombre == "cengel"
        assert any("COL_ENTRADA_TERMICA" in a for a in adv)

    # --- Modo natural ---

    def test_natural_hollands_default(self):
        """Modo natural sin especificar → hollands."""
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re=0.0,
            Pr=self.PR,
            Dh_m=self.DH,
            L_m=self.L,
            k_fluido_W_mK=self.K,
            pared="una_pared",
            modo="natural",
            Ra=1e5,
            theta_deg=45.0,
        )
        assert nombre == "hollands"
        assert regimen == "natural"
        assert h > 0.0

    def test_natural_advertencia_theta_alto(self):
        """θ > 75° → advertencia COL_NUSSELT_THETA_FUERA_RANGO."""
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re=0.0,
            Pr=self.PR,
            Dh_m=self.DH,
            L_m=self.L,
            k_fluido_W_mK=self.K,
            pared="una_pared",
            modo="natural",
            Ra=1e5,
            theta_deg=80.0,
        )
        assert any("COL_NUSSELT_THETA_FUERA_RANGO" in a for a in adv)

    # --- Selección manual por usuario ---

    def test_usuario_puede_forzar_dittus_boelter_turbulento(self):
        """Usuario elige dittus_boelter en turbulento → se usa sin advertencia de rango."""
        Re = 20000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re,
            self.PR,
            self.DH,
            self.L,
            self.K,
            "una_pared",
            "forzado",
            correlacion="dittus_boelter",
        )
        assert nombre == "dittus_boelter"
        # No debe haber advertencia de rango (Re está dentro de rango válido)
        assert not any("FUERA_RANGO" in a for a in adv)

    def test_usuario_fuera_de_rango_genera_advertencia(self):
        """Usuario elige gnielinski en turbulento → advertencia Re fuera de rango."""
        Re = 30000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re, self.PR, self.DH, self.L, self.K, "una_pared", "forzado", correlacion="gnielinski"
        )
        assert nombre == "gnielinski"
        assert any("COL_NUSSELT_FUERA_RANGO" in a for a in adv)

    def test_usuario_pared_incompatible_genera_advertencia(self):
        """Usuario elige sparrow_liu (una pared) en colector Tipo 2 → advertencia."""
        Re = 20000.0
        h, Nu, nombre, regimen, adv = calcular_h_int(
            Re,
            self.PR,
            self.DH,
            self.L,
            self.K,
            "dos_paredes",
            "forzado",
            correlacion="sparrow_liu",
        )
        assert any("COL_NUSSELT_PARED_INCOMPATIBLE" in a for a in adv)

    def test_correlacion_invalida_lanza_error(self):
        """Nombre de correlación inexistente → ValueError."""
        with pytest.raises(ValueError, match="no disponible"):
            calcular_h_int(
                20000.0,
                self.PR,
                self.DH,
                self.L,
                self.K,
                "una_pared",
                "forzado",
                correlacion="inexistente",
            )

    def test_natural_correlacion_invalida_lanza_error(self):
        with pytest.raises(ValueError, match="no disponible"):
            calcular_h_int(
                0.0,
                self.PR,
                self.DH,
                self.L,
                self.K,
                "una_pared",
                "natural",
                Ra=1e5,
                theta_deg=45.0,
                correlacion="inexistente",
            )

    # --- Invariantes físicas de h_int ---

    def test_h_positivo_todos_los_regimenes(self):
        """h_int > 0 en todos los regímenes y configuraciones."""
        casos = [
            (500.0, "una_pared", 2.0),  # laminar desarrollado
            (1000.0, "una_pared", 0.3),  # laminar en desarrollo
            (5000.0, "una_pared", 2.0),  # transición
            (20000.0, "una_pared", 2.0),  # turbulento una pared
            (20000.0, "dos_paredes", 2.0),  # turbulento dos paredes
            (20000.0, "una_pared", 0.3),  # turbulento entrada pronunciada
        ]
        for Re, pared, L in casos:
            h, *_ = calcular_h_int(Re, self.PR, self.DH, L, self.K, pared, "forzado")
            assert h > 0.0, f"h ≤ 0 para Re={Re}, pared={pared}, L={L}"

    def test_h_crece_con_Re_forzado(self):
        """h_int crece con Re (más flujo → más transferencia)."""
        Re_vals = [500.0, 5000.0, 20000.0]
        h_vals = []
        for Re in Re_vals:
            h, *_ = calcular_h_int(Re, self.PR, self.DH, self.L, self.K, "una_pared", "forzado")
            h_vals.append(h)
        assert all(
            h_vals[i] < h_vals[i + 1] for i in range(len(h_vals) - 1)
        ), f"h no monotónico: {h_vals}"


# =============================================================================
# Punto de entrada
# =============================================================================


class TestNusseltLocal:
    """Nusselt local: entrada térmica, blending de régimen y convección mixta."""

    def test_decae_a_desarrollado_aguas_abajo(self):
        """Laminar: Nu(x) alto cerca de la entrada, decae al valor desarrollado."""
        Re, Pr, Dh = 1500.0, 0.7, 0.05
        nu_entrada = nusselt_forzado_local(Re, Pr, Dh, x_m=0.05, pared="una_pared")
        nu_lejos = nusselt_forzado_local(Re, Pr, Dh, x_m=1000.0, pared="una_pared")
        assert nu_entrada > nu_lejos
        assert nu_lejos == pytest.approx(5.385, rel=0.02)  # → desarrollado una pared

    def test_desarrollado_dos_paredes(self):
        """Dos paredes: el límite desarrollado es 8.235."""
        nu = nusselt_forzado_local(1500.0, 0.7, 0.05, x_m=1000.0, pared="dos_paredes")
        assert nu == pytest.approx(8.235, rel=0.02)

    def test_promedio_laminar_reproduce_heaton(self):
        """El promedio de Nu_x laminar sobre 0..L reproduce Heaton (consistencia)."""
        Re, Pr, Dh, L = 1500.0, 0.7, 0.05, 3.0
        xs = [L * (i + 0.5) / 400 for i in range(400)]  # punto medio, evita x=0
        nu_avg = sum(nusselt_forzado_local(Re, Pr, Dh, x, "una_pared") for x in xs) / len(xs)
        nu_heaton = nusselt_heaton(Re, Pr, L, Dh)
        assert nu_avg == pytest.approx(nu_heaton, rel=0.05)

    def test_blending_continuo_en_Re_2300(self):
        """No hay salto en Nu al cruzar Re=2300 (blending suave)."""
        kw = dict(Pr=0.7, Dh_m=0.05, x_m=1.0, pared="una_pared")
        nu_lo = nusselt_forzado_local(Re=RE_LAMINAR_MAX - 1.0, **kw)
        nu_hi = nusselt_forzado_local(Re=RE_LAMINAR_MAX + 1.0, **kw)
        assert nu_hi == pytest.approx(nu_lo, rel=0.05)

    def test_blending_continuo_en_Re_10000(self):
        """No hay salto en Nu al cruzar Re=10000 (blending suave)."""
        kw = dict(Pr=0.7, Dh_m=0.05, x_m=1.0, pared="una_pared")
        nu_lo = nusselt_forzado_local(Re=RE_TURBULENTO_MIN - 1.0, **kw)
        nu_hi = nusselt_forzado_local(Re=RE_TURBULENTO_MIN + 1.0, **kw)
        assert nu_hi == pytest.approx(nu_lo, rel=0.05)

    def test_natural_canal_cero_sin_flotacion(self):
        """Sin flotación (Ra ≤ 0) la componente natural es 0."""
        assert nusselt_natural_canal(0.0, 0.7) == 0.0
        assert nusselt_natural_canal(-10.0, 0.7) == 0.0

    def test_natural_canal_crece_con_Ra(self):
        """La componente natural crece con Ra."""
        assert nusselt_natural_canal(1e5, 0.7) < nusselt_natural_canal(1e7, 0.7)

    def test_mixta_reduce_a_forzado_sin_flotacion(self):
        """Con Ra=0, el Nu mixto coincide con el forzado local."""
        kw = dict(Re=1500.0, Pr=0.7, Dh_m=0.05, x_m=1.0, pared="una_pared")
        assert nusselt_mixto_local(Ra=0.0, **kw) == pytest.approx(
            nusselt_forzado_local(1500.0, 0.7, 0.05, 1.0, "una_pared")
        )

    def test_mixta_supera_forzado_con_flotacion(self):
        """A baja velocidad con flotación fuerte, el mixto supera al forzado puro."""
        kw = dict(Re=400.0, Pr=0.7, Dh_m=0.05, x_m=1.0, pared="una_pared")
        nu_forzado = nusselt_forzado_local(400.0, 0.7, 0.05, 1.0, "una_pared")
        nu_mixto = nusselt_mixto_local(Ra=1e6, **kw)
        assert nu_mixto > nu_forzado


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
