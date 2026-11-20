"""Presets de sistema completo para tipologías (S41).

Factories de configuración inicial coherente. El preset de **gran escala** es
el secador híbrido ADITAL de San Carlos, Salta (tesis doctoral, cap. 3):
túnel semicontinuo a contracorriente de 18 m con 24 carros, banco de 26
colectores descargando a un caño maestro no aislado, y ~5000 kg de pimiento
por campaña.

Lo consumen:
    - ``ui/p1_tipologia.py``: cascada al cambiar la tipología a GRAN_ESCALA
      (puebla colector, cámara y motor con valores realistas de escala
      industrial en lugar de los defaults de armario).
    - ``validacion/validacion_adital.py``: el caso de validación reusa estas
      mismas factories (una sola fuente de verdad para el secador ADITAL).

Capa core/: sin Streamlit.
"""

from __future__ import annotations

from core import catalogo
from core.camara import (
    Camara,
    CapaPared,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionCarros,
    ConfiguracionFlujo,
    ConfiguracionTunel,
    ConstruccionCamara,
    GeometriaCamara,
    ParedCamara,
)
from core.colector import BancoColectores, CanoMaestro, Colector, ColectorUnidad
from core.motor import Motor

# Caudal másico de aire del sistema ADITAL [kg/s] (ventilador centrífugo). Medido en
# 2010 tras el cambio de ventilador: 1.4 m/s medios en el difusor de entrada a la cámara
# (1.2 × 1.8 m), ρ ≈ 1.1 kg/m³ → 3.3 kg/s (tesis de G. Durán, cap. 3). El de diseño era
# 600 m³/h por colector (≈ 3.8 kg/s). Hasta S70 el preset usaba 3.8 en la cámara pero el
# banco de colectores, armado con un solo canal, entregaba la mitad.
_CAUDAL_ADITAL_KG_S: float = 3.3
# Densidad de referencia para convertir a caudal volumétrico (~50 °C, 1800 m).
_RHO_REF_KG_M3: float = 0.87


def cano_maestro_gran_escala() -> CanoMaestro:
    """Caño maestro ADITAL: 18 m, sección 1×0.90 m, galvanizado desnudo.

    Chapa galvanizada brillante → α_solar ≈ 0.35 (no el 0.90 default de chapa
    pintada): con galvanizado el aporte solar no domina y la pérdida neta da
    ΔT ≈ −3 °C (dato de campo de la tesis).
    """
    return CanoMaestro(
        largo_m=18.0,
        ancho_m=1.0,
        alto_m=0.90,
        # Sección creciente real de ADITAL (tesis §2): 0.30×0.50 m en el
        # extremo lejano → 1×0.90 m en el ventilador.
        ancho_inicio_m=0.30,
        alto_inicio_m=0.50,
        aislado=False,
        aporte_solar=True,
        absortancia_solar=0.35,
    )


def colector_gran_escala() -> Colector:
    """Banco ADITAL: 26 colectores 7.5×0.94 m (tipo 1) en paralelo + caño."""
    return Colector(
        unidad=ColectorUnidad(
            largo_m=7.5,
            ancho_m=0.94,
            # Chapa ondulada a media altura: el aire pasa por arriba y por debajo
            # (tesis, cap. 2) → Tipo 2, dos canales de ~5 cm (estimado por el
            # usuario, S70). Hasta S70 era Tipo 1 con un solo canal de 5 cm.
            espaciado_m=0.05,
            espaciado_inferior_m=0.05,
            # 26 × 0.94 × (0.05 + 0.05) × 1.5 m/s ≈ 3.7 m³/s ≈ 3.3 kg/s (medido en 2010).
            velocidad_diseno_ms=1.5,
            tipo_colector=2,
            n_cubiertas=1,
        ),
        banco=BancoColectores(
            n_serie=1,
            n_paralelo=26,
            cano_maestro=cano_maestro_gran_escala(),
        ),
    )


def camara_gran_escala() -> Camara:
    """Túnel ADITAL: 18×3×1.85 m aislado, 24 carros × 14 bandejas, 5000 kg.

    La carga total (5000 kg de pimiento en lecho de 4 cm) se distribuye en
    24 carros de 14 bandejas de 0.95 m² (≈ 319 m² de superficie de secado).
    El túnel semicontinuo avanza un carro cada 5 h (cadencia del operario).
    """
    pared = ParedCamara(
        capas=[
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
            CapaPared(material_id="lana_vidrio_media", espesor_m=0.05, catalogo="aislantes"),
            CapaPared(material_id="galvanizada_pintada", espesor_m=0.0006, catalogo="fondos"),
        ]
    )
    carros = ConfiguracionCarros(n_carros=24, bandejas_por_carro=14)
    return Camara(
        geometria=GeometriaCamara(largo_m=18.0, ancho_m=3.0, alto_m=1.85),
        construccion=ConstruccionCamara(pared=pared),
        bandejas=ConfiguracionBandejas(
            n_bandejas=carros.n_bandejas_total,  # derivado (lo sincroniza Camara)
            area_bandeja_m2=0.95,
            espesor_capa_m=0.04,
            separacion_entre_bandejas_m=0.10,
        ),
        flujo=ConfiguracionFlujo(caudal_masico_kg_s=_CAUDAL_ADITAL_KG_S, HR_entrada_fraccion=0.15),
        carga_producto=CargaProducto(
            # Pimiento para pimentón en vaina entera (S70): el producto real de ADITAL,
            # X0 ≈ 3 (Condorí 2009). Hasta S70: pimiento morrón cortado, X0 = 10.7.
            producto_id="pimiento_pimenton",
            masa_total_kg=5000.0,
            humedad_inicial_X=3.0,
            humedad_objetivo_X=catalogo.objetivo_secado("pimiento_pimenton").X,
            modelo_capa_fina="page",
            modelo_isoterma="gab",
        ),
        carros=carros,
        tunel=ConfiguracionTunel(n_zonas=24, intervalo_avance_h=5.0),
    )


def motor_gran_escala() -> Motor:
    """Ventilador del sistema ADITAL: caudal volumétrico ≈ 3.8 kg/s / ρ."""
    return Motor(caudal_volumetrico_m3_s=round(_CAUDAL_ADITAL_KG_S / _RHO_REF_KG_M3, 2))
