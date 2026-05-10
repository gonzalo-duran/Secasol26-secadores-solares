"""
Dataclasses de la cámara de secado solar.

Jerarquía:
    Camara
    ├── GeometriaCamara       — dimensiones internas [m]
    ├── ConstruccionCamara    — materiales/cubierta/aislación
    ├── ConfiguracionBandejas — número, área, espesor de capa, separación
    ├── ConfiguracionFlujo    — caudal, dirección, HR de entrada
    └── CargaProducto         — producto, humedades y modelos de secado

Almacenado en Proyecto.camara. Es None para tipología CAJA (que aún no está
implementada en v0).

Convención de unidades (SI estricto):
    Temperaturas: K
    Longitudes:   m
    Masas:        kg
    Humedades del producto: kg agua / kg masa seca (base seca, X)
    Humedad relativa del aire: fracción [0, 1]
    Caudal másico: kg/s
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

# Modos válidos de cálculo de cámara
_MODOS_CALCULO_VALIDOS: tuple[str, ...] = ("capa_fina", "termodinamico")
# Rango razonable para T inicial del producto (caso refrigerado a precalentado)
_T_PROD_INICIAL_MIN_K: float = 263.15   # −10 °C
_T_PROD_INICIAL_MAX_K: float = 343.15   # +70 °C

from core import catalogo
from core.advertencias import Advertencia, Severidad

# ---------------------------------------------------------------------------
# Umbrales de diseño
# ---------------------------------------------------------------------------

_VOL_MIN_M3: float = 0.01           # 10 litros — mínimo para secador funcional
_ALTO_MIN_TIPICO_M: float = 0.3     # límite inferior de rango típico [m]
_ALTO_MAX_TIPICO_M: float = 3.0     # límite superior de rango típico [m]
_RATIO_LARGO_ANCHO_MAX: float = 10.0
_RATIO_LARGO_ANCHO_MIN: float = 0.1
_ESPESOR_MAX_CAPA_FINA_M: float = 0.05   # 5 cm — límite de capa fina
_N_BANDEJAS_ALTO: int = 20
_V_SUP_MIN_MS: float = 0.3          # velocidad superficial mínima [m/s]
_V_SUP_MAX_MS: float = 3.0          # velocidad superficial máxima [m/s]
_RHO_AIRE_EST: float = 1.1          # densidad de aire estimada a ~50°C [kg/m³]
_CARGA_MAX_KG_M2: float = 20.0      # carga máxima de producto por m² de bandeja
_U_MUROS_ALTO_W_M2K: float = 2.0   # umbral de conductancia lateral alta


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class DireccionFlujo(Enum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL_ASCENDENTE = "VERTICAL_ASCENDENTE"


# ---------------------------------------------------------------------------
# Sub-dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GeometriaCamara:
    """Dimensiones internas de la cámara de secado.

    Attributes:
        largo_m: Dimensión horizontal en la dirección del flujo [m].
        ancho_m: Dimensión horizontal transversal al flujo [m].
        alto_m: Altura libre interna [m].
    """

    largo_m: float = 1.2
    ancho_m: float = 0.8
    alto_m: float = 1.5

    def __post_init__(self) -> None:
        if self.largo_m <= 0 or self.ancho_m <= 0 or self.alto_m <= 0:
            raise ValueError(
                f"GEO_DIMENSIONES_NO_POSITIVAS: dimensiones deben ser positivas. "
                f"Recibido: largo={self.largo_m}, ancho={self.ancho_m}, alto={self.alto_m}."
            )
        vol = self.largo_m * self.ancho_m * self.alto_m
        if vol < _VOL_MIN_M3:
            raise ValueError(
                f"GEO_VOLUMEN_MINIMO: volumen {vol:.4f} m³ < {_VOL_MIN_M3} m³ mínimo operativo."
            )


@dataclass
class ConstruccionCamara:
    """Propiedades constructivas de la cámara.

    Attributes:
        cubierta_translucida: True si la cubierta superior permite el paso de luz.
        U_muros_W_m2K: Conductancia térmica efectiva de los muros laterales [W/(m²·K)].
    """

    cubierta_translucida: bool = False
    U_muros_W_m2K: float = 0.5


@dataclass
class ConfiguracionBandejas:
    """Configuración del sistema de bandejas de secado.

    Attributes:
        n_bandejas: Número total de bandejas en la cámara.
        area_bandeja_m2: Área de carga de producto por bandeja [m²].
        espesor_capa_m: Espesor de la capa de producto sobre la bandeja [m].
            Los modelos de capa fina son válidos para espesor ≤ 0.05 m.
        separacion_entre_bandejas_m: Distancia entre superficies de bandejas
            consecutivas [m]. Debe ser > espesor_capa_m + 0.01 m.
        tipo_malla: Identificador del tipo de malla (para cálculo de caída de presión).
            None si no se especifica.
    """

    n_bandejas: int = 5
    area_bandeja_m2: float = 0.50
    espesor_capa_m: float = 0.020
    separacion_entre_bandejas_m: float = 0.15
    tipo_malla: Optional[str] = None
    porosidad_lecho: float = 0.45
    diametro_eq_particula_m: Optional[float] = None
    esfericidad: float = 0.60

    def __post_init__(self) -> None:
        if self.n_bandejas < 1:
            raise ValueError(
                "BAND_N_BANDEJAS_NO_POSITIVO: n_bandejas debe ser ≥ 1. "
                f"Recibido: {self.n_bandejas}."
            )
        if self.area_bandeja_m2 <= 0:
            raise ValueError(
                f"BAND_AREA_NO_POSITIVA: area_bandeja_m2={self.area_bandeja_m2:.4f} m² ≤ 0."
            )
        if self.espesor_capa_m <= 0:
            raise ValueError(
                f"BAND_ESPESOR_NO_POSITIVO: espesor_capa_m={self.espesor_capa_m:.4f} m ≤ 0."
            )
        if self.separacion_entre_bandejas_m <= 0:
            raise ValueError(
                f"BAND_SEPARACION_NO_POSITIVA: separacion_entre_bandejas_m="
                f"{self.separacion_entre_bandejas_m:.4f} m ≤ 0."
            )
        margen_min = self.espesor_capa_m + 0.01
        if self.separacion_entre_bandejas_m < margen_min:
            raise ValueError(
                f"BAND_SEPARACION_INSUFICIENTE: separación {self.separacion_entre_bandejas_m:.3f} m "
                f"< espesor_capa {self.espesor_capa_m:.3f} m + margen 0.01 m "
                f"= {margen_min:.3f} m mínimo."
            )
        if not (0.0 < self.porosidad_lecho < 1.0):
            raise ValueError(
                f"BAND_POROSIDAD_INVALIDA: porosidad_lecho={self.porosidad_lecho:.3f} "
                "fuera del rango válido (0, 1)."
            )
        if self.diametro_eq_particula_m is not None and self.diametro_eq_particula_m <= 0:
            raise ValueError(
                f"BAND_DIAMETRO_PARTICULA_NO_POSITIVO: diametro_eq_particula_m="
                f"{self.diametro_eq_particula_m:.6f} m ≤ 0."
            )
        if not (0.0 < self.esfericidad <= 1.0):
            raise ValueError(
                f"BAND_ESFERICIDAD_INVALIDA: esfericidad={self.esfericidad:.3f} "
                "fuera del rango válido (0, 1]."
            )


@dataclass
class ConfiguracionFlujo:
    """Configuración del flujo de aire a través de la cámara.

    Attributes:
        caudal_masico_kg_s: Caudal másico de aire seco que atraviesa la cámara [kg/s].
            Debe coincidir con el caudal del banco de colectores (cuando aplica).
        fraccion_recirculacion: Fracción del aire recirculado [0, 1].
            Solo 0 está implementado en v0.
        direccion_flujo: Dirección del flujo de aire en la cámara.
        HR_entrada_fraccion: Humedad relativa del aire en la entrada de la cámara
            [fracción 0–1]. None implica uso de fallback del catálogo.
    """

    caudal_masico_kg_s: float = 0.030
    fraccion_recirculacion: float = 0.0
    direccion_flujo: DireccionFlujo = DireccionFlujo.HORIZONTAL
    HR_entrada_fraccion: Optional[float] = None

    def __post_init__(self) -> None:
        if self.caudal_masico_kg_s <= 0:
            raise ValueError(
                f"FLUJO_CAUDAL_NO_POSITIVO: caudal_masico_kg_s={self.caudal_masico_kg_s:.4f} "
                "kg/s ≤ 0. El caudal debe ser positivo."
            )
        if self.fraccion_recirculacion > 0:
            raise NotImplementedError(
                f"FLUJO_RECIRCULACION_NO_IMPLEMENTADA: fraccion={self.fraccion_recirculacion:.3f}. "
                "La recirculación de aire no está implementada en v0. "
                "Usar fraccion_recirculacion=0."
            )
        if self.direccion_flujo not in (
            DireccionFlujo.HORIZONTAL,
            DireccionFlujo.VERTICAL_ASCENDENTE,
        ):
            raise NotImplementedError(
                f"FLUJO_DIRECCION_NO_SOPORTADA: '{self.direccion_flujo}' no soportada en v0. "
                "Opciones: HORIZONTAL, VERTICAL_ASCENDENTE."
            )
        if self.HR_entrada_fraccion is not None and not (0.0 <= self.HR_entrada_fraccion <= 1.0):
            raise ValueError(
                f"FLUJO_HR_ENTRADA_INVALIDA: HR_entrada_fraccion={self.HR_entrada_fraccion:.3f} "
                "fuera del rango válido [0, 1]."
            )


@dataclass
class CargaProducto:
    """Producto a secar y condiciones de secado objetivo.

    Attributes:
        producto_id: Clave del producto en el catálogo YAML (ej.: 'manzana').
        masa_total_kg: Masa total de producto fresco a secar [kg].
        humedad_inicial_X: Humedad inicial en base seca [kg agua / kg ms].
        humedad_objetivo_X: Humedad final objetivo en base seca [kg agua / kg ms].
            Debe ser menor que humedad_inicial_X.
        modelo_capa_fina: Nombre del modelo cinético de capa fina a usar.
            Opciones según catálogo: 'page', 'midilli', 'henderson', 'lewis', 'logaritmico'.
        modelo_isoterma: Modelo de isoterma de sorción para calcular X_eq.
            'gab' es el único implementado en v0.
    """

    producto_id: str = "manzana"
    masa_total_kg: float = 10.0
    humedad_inicial_X: float = 4.6
    humedad_objetivo_X: float = 0.15
    modelo_capa_fina: str = "logaritmico"
    modelo_isoterma: str = "gab"
    T_prod_inicial_K: Optional[float] = None

    def __post_init__(self) -> None:
        if self.masa_total_kg <= 0:
            raise ValueError(
                f"PROD_MASA_NO_POSITIVA: masa_total_kg={self.masa_total_kg:.3f} kg ≤ 0."
            )
        if self.humedad_inicial_X < 0:
            raise ValueError(
                f"PROD_HUMEDAD_INICIAL_NEGATIVA: humedad_inicial_X={self.humedad_inicial_X:.4f} < 0. "
                "La humedad en base seca no puede ser negativa."
            )
        if self.humedad_objetivo_X < 0:
            raise ValueError(
                f"PROD_HUMEDAD_OBJETIVO_NEGATIVA: humedad_objetivo_X={self.humedad_objetivo_X:.4f} < 0."
            )
        if self.humedad_objetivo_X >= self.humedad_inicial_X:
            raise ValueError(
                f"PROD_HUMEDAD_OBJETIVO_MAYOR_INICIAL: objetivo {self.humedad_objetivo_X:.4f} "
                f">= inicial {self.humedad_inicial_X:.4f}. El secado reduce la humedad."
            )
        if self.T_prod_inicial_K is not None:
            if not (
                _T_PROD_INICIAL_MIN_K <= self.T_prod_inicial_K <= _T_PROD_INICIAL_MAX_K
            ):
                raise ValueError(
                    f"PROD_T_INICIAL_FUERA_RANGO: T_prod_inicial_K="
                    f"{self.T_prod_inicial_K:.2f} K ∉ "
                    f"[{_T_PROD_INICIAL_MIN_K:.2f}, {_T_PROD_INICIAL_MAX_K:.2f}] K. "
                    "Rango razonable: producto refrigerado (−10 °C) a precalentado (70 °C). "
                    "Si es None, el motor termodinámico usa T_amb como fallback."
                )


# ---------------------------------------------------------------------------
# Camara (raíz de la sección)
# ---------------------------------------------------------------------------


@dataclass
class Camara:
    """Cámara de secado solar completa.

    Almacenada en Proyecto.camara. Es None para tipología CAJA en v0.

    Attributes:
        geometria: Dimensiones internas de la cámara.
        construccion: Propiedades constructivas (cubierta, aislación lateral).
        bandejas: Configuración del sistema de bandejas.
        flujo: Configuración del flujo de aire.
        carga_producto: Producto y condiciones de secado.
        modo_calculo: Selector del motor numérico:
            'capa_fina'    → modelo cinético empírico (Lewis/Page/...).
            'termodinamico' → balance acoplado calor-masa con `solve_ivp`.
            Default: 'capa_fina' para preservar comportamiento histórico.
    """

    geometria: GeometriaCamara = field(default_factory=GeometriaCamara)
    construccion: ConstruccionCamara = field(default_factory=ConstruccionCamara)
    bandejas: ConfiguracionBandejas = field(default_factory=ConfiguracionBandejas)
    flujo: ConfiguracionFlujo = field(default_factory=ConfiguracionFlujo)
    carga_producto: CargaProducto = field(default_factory=CargaProducto)
    modo_calculo: Literal["capa_fina", "termodinamico"] = "capa_fina"

    def __post_init__(self) -> None:
        if self.modo_calculo not in _MODOS_CALCULO_VALIDOS:
            raise ValueError(
                f"CAM_MODO_INVALIDO: modo_calculo='{self.modo_calculo}' no es válido. "
                f"Opciones: {_MODOS_CALCULO_VALIDOS}."
            )
        self._validar_producto()
        self._validar_coherencia()

    def _validar_producto(self) -> None:
        """Valida que el producto y sus modelos existan en el catálogo.

        Raises:
            ValueError: Si el producto_id no existe, o si el modelo de capa fina
                seleccionado no tiene parámetros calibrados para el producto.
                También si no hay isoterma ni fallback escalar.
        """
        p = self.carga_producto

        if p.producto_id not in catalogo.PRODUCTOS:
            ids = list(catalogo.PRODUCTOS.keys())
            raise ValueError(
                f"PROD_ID_NO_ENCONTRADO: '{p.producto_id}' no existe en el catálogo "
                f"de productos. Disponibles: {ids}."
            )

        datos = catalogo.PRODUCTOS[p.producto_id]

        # Modelo de capa fina con params calibrados
        cf = datos.get("capa_fina") or {}
        modelo_entry = cf.get(p.modelo_capa_fina) or {}
        params_cf = modelo_entry.get("params") or {} if modelo_entry else {}
        params_cf_vacios = not params_cf or all(
            v is None
            for v in params_cf.values()
            if not isinstance(v, (list, dict))
        )
        if params_cf_vacios:
            modelos_disponibles = _modelos_disponibles(datos)
            raise ValueError(
                f"MOD_CAPA_FINA_NO_DISPONIBLE: modelo '{p.modelo_capa_fina}' sin parámetros "
                f"calibrados para '{p.producto_id}'. "
                f"Modelos disponibles: {modelos_disponibles}. "
                "Cargar parámetros en el catálogo o seleccionar otro modelo."
            )

        # Isoterma: error duro solo si no hay parámetros Y no hay fallback escalar
        iso = datos.get("isoterma") or {}
        iso_entry = iso.get(p.modelo_isoterma) or {}
        params_iso = iso_entry.get("params") or {} if iso_entry else {}
        params_iso_vacios = not params_iso or all(
            v is None
            for v in params_iso.values()
            if not isinstance(v, (list, dict))
        )
        X_eq_fallback = (datos.get("propiedades_basicas") or {}).get(
            "humedad_equilibrio_aire_seco"
        )
        if params_iso_vacios and X_eq_fallback is None:
            raise ValueError(
                f"MOD_ISOTERMA_NO_DISPONIBLE: isoterma '{p.modelo_isoterma}' sin parámetros "
                f"para '{p.producto_id}' y sin fallback escalar en catálogo. "
                "Cargar parámetros o agregar 'humedad_equilibrio_aire_seco' en propiedades_basicas."
            )

    def _validar_coherencia(self) -> None:
        """Valida invariantes de coherencia cruzada entre secciones.

        Raises:
            ValueError: Si las bandejas no caben en la cámara, si el área de
                bandeja supera el área de planta, o si la carga por m² excede
                el límite de capa fina.
        """
        g = self.geometria
        b = self.bandejas
        p = self.carga_producto

        alto_requerido = b.n_bandejas * b.separacion_entre_bandejas_m
        if alto_requerido > g.alto_m:
            raise ValueError(
                f"COHE_BANDEJAS_NO_CABEN_EN_CAMARA: {b.n_bandejas} bandejas × "
                f"{b.separacion_entre_bandejas_m:.3f} m = {alto_requerido:.3f} m > "
                f"alto cámara {g.alto_m:.3f} m."
            )

        area_planta = g.largo_m * g.ancho_m
        if b.area_bandeja_m2 > area_planta:
            raise ValueError(
                f"COHE_AREA_BANDEJA_EXCEDE_CAMARA: área bandeja {b.area_bandeja_m2:.3f} m² > "
                f"área planta {area_planta:.3f} m²."
            )

        carga_por_m2 = p.masa_total_kg / b.n_bandejas / b.area_bandeja_m2
        if carga_por_m2 > _CARGA_MAX_KG_M2:
            raise ValueError(
                f"COHE_CARGA_EXCEDE_CAPACIDAD_GEOMETRICA: carga {carga_por_m2:.1f} kg/m²/bandeja "
                f"> {_CARGA_MAX_KG_M2:.0f} kg/m² máximo para capa fina. "
                "Revisar masa total o número/área de bandejas."
            )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _modelos_disponibles(datos_producto: dict) -> list[str]:
    """Retorna los IDs de modelos de capa fina con parámetros calibrados."""
    cf = datos_producto.get("capa_fina") or {}
    disponibles = []
    for modelo_id, entry in cf.items():
        if entry is None:
            continue
        params = entry.get("params") or {}
        tiene_params = params and not all(
            v is None
            for v in params.values()
            if not isinstance(v, (list, dict))
        )
        if tiene_params:
            disponibles.append(modelo_id)
    return disponibles


# ---------------------------------------------------------------------------
# Advertencias estáticas (chequeos de diseño no bloqueantes)
# ---------------------------------------------------------------------------


def advertencias_camara(camara: Camara) -> list[Advertencia]:
    """Genera la lista de advertencias estáticas de diseño para la cámara.

    Las advertencias no bloquean la instanciación pero deben mostrarse al usuario
    antes de calcular. Complementan los errores duros de __post_init__.

    Args:
        camara: Objeto Camara completamente instanciado.

    Returns:
        Lista de Advertencia, posiblemente vacía si el diseño es correcto.
    """
    adv: list[Advertencia] = []
    g = camara.geometria
    c = camara.construccion
    b = camara.bandejas
    f = camara.flujo
    p = camara.carga_producto

    datos = catalogo.PRODUCTOS.get(p.producto_id) or {}
    props = datos.get("propiedades_basicas") or {}

    # --- GEO: relación de aspecto ---
    ratio = g.largo_m / g.ancho_m
    if ratio > _RATIO_LARGO_ANCHO_MAX or ratio < _RATIO_LARGO_ANCHO_MIN:
        adv.append(Advertencia(
            codigo="GEO_RELACION_ASPECTO_EXTREMA",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Relación largo/ancho = {ratio:.1f}. "
                f"Rango recomendado: {_RATIO_LARGO_ANCHO_MIN}–{_RATIO_LARGO_ANCHO_MAX}. "
                "Una cámara muy alargada o cuadrada puede generar flujo no uniforme."
            ),
            campo="geometria",
            sugerencia="Verificar uniformidad de flujo de aire sobre las bandejas.",
            contexto={"ratio_largo_ancho": round(ratio, 2)},
        ))

    # --- GEO: alto inusual ---
    if not (_ALTO_MIN_TIPICO_M <= g.alto_m <= _ALTO_MAX_TIPICO_M):
        adv.append(Advertencia(
            codigo="GEO_ALTO_INUSUAL",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Alto de cámara {g.alto_m:.2f} m fuera del rango típico "
                f"({_ALTO_MIN_TIPICO_M}–{_ALTO_MAX_TIPICO_M} m) para secadores solares."
            ),
            campo="geometria.alto_m",
            sugerencia="Verificar el dimensionamiento vertical del secador.",
            contexto={"alto_m": g.alto_m},
        ))

    # --- CONS: cubierta translúcida + producto fotosensible ---
    if c.cubierta_translucida and datos.get("fotosensible", False):
        adv.append(Advertencia(
            codigo="CONS_CUBIERTA_TRANSLUCIDA_FOTOSENSIBLE",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Producto fotosensible '{p.producto_id}' con cubierta translúcida. "
                "La exposición a radiación UV puede degradar pigmentos o aceites esenciales."
            ),
            campo="construccion.cubierta_translucida",
            sugerencia="Considerar cubierta opaca o filtro UV.",
            contexto={"producto_id": p.producto_id},
        ))

    # --- CONS: muros sin aislación ---
    if c.U_muros_W_m2K > _U_MUROS_ALTO_W_M2K:
        adv.append(Advertencia(
            codigo="CONS_SIN_AISLACION_LATERAL",
            severidad=Severidad.INFO,
            mensaje=(
                f"Muros laterales con U = {c.U_muros_W_m2K:.1f} W/(m²·K) > "
                f"{_U_MUROS_ALTO_W_M2K} W/(m²·K). Baja resistencia térmica."
            ),
            campo="construccion.U_muros_W_m2K",
            sugerencia="Agregar aislación para mejorar la eficiencia térmica del secador.",
            contexto={"U_muros": c.U_muros_W_m2K},
        ))

    # --- BAND: espesor de capa grande ---
    if b.espesor_capa_m > _ESPESOR_MAX_CAPA_FINA_M:
        adv.append(Advertencia(
            codigo="BAND_ESPESOR_CAPA_GRANDE",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Espesor de capa {b.espesor_capa_m * 100:.1f} cm > "
                f"{_ESPESOR_MAX_CAPA_FINA_M * 100:.0f} cm. "
                "Los modelos de capa fina pueden subestimar el tiempo de secado."
            ),
            campo="bandejas.espesor_capa_m",
            sugerencia="Reducir espesor de capa o evaluar un modelo difusivo.",
            contexto={"espesor_m": b.espesor_capa_m, "limite_m": _ESPESOR_MAX_CAPA_FINA_M},
        ))

    # --- BAND: muchas bandejas ---
    if b.n_bandejas > _N_BANDEJAS_ALTO:
        adv.append(Advertencia(
            codigo="BAND_N_BANDEJAS_ELEVADO",
            severidad=Severidad.INFO,
            mensaje=f"{b.n_bandejas} bandejas. Verificar uniformidad de flujo entre bandejas.",
            campo="bandejas.n_bandejas",
            sugerencia="Con muchas bandejas en serie, la última recibe aire más húmedo.",
            contexto={"n_bandejas": b.n_bandejas, "limite": _N_BANDEJAS_ALTO},
        ))

    # --- BAND: malla sin especificar ---
    if b.tipo_malla is None:
        adv.append(Advertencia(
            codigo="BAND_MALLA_SIN_ESPECIFICAR",
            severidad=Severidad.INFO,
            mensaje="Tipo de malla de bandeja no especificado. Afecta la caída de presión.",
            campo="bandejas.tipo_malla",
            sugerencia="Especificar tipo de malla para estimación de pérdida de carga en motor.",
            contexto={},
        ))

    # --- FLUJO: velocidad superficial ---
    Q_vol = f.caudal_masico_kg_s / _RHO_AIRE_EST
    v_sup = Q_vol / (g.ancho_m * g.alto_m)
    if v_sup < _V_SUP_MIN_MS:
        adv.append(Advertencia(
            codigo="FLUJO_VELOCIDAD_SUPERFICIAL_BAJA",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Velocidad superficial de aire {v_sup:.2f} m/s < {_V_SUP_MIN_MS} m/s. "
                "El coeficiente convectivo externo puede ser bajo. "
                "El modelo de capa fina puede sobrestimar la tasa de secado."
            ),
            campo="flujo.caudal_masico_kg_s",
            sugerencia=(
                f"Aumentar caudal de aire para superar {_V_SUP_MIN_MS} m/s "
                "de velocidad superficial."
            ),
            contexto={"v_sup_m_s": round(v_sup, 3)},
        ))
    elif v_sup > _V_SUP_MAX_MS:
        adv.append(Advertencia(
            codigo="FLUJO_VELOCIDAD_SUPERFICIAL_ALTA",
            severidad=Severidad.INFO,
            mensaje=(
                f"Velocidad superficial de aire {v_sup:.2f} m/s > {_V_SUP_MAX_MS} m/s. "
                "Verificar compatibilidad del motor con la pérdida de presión."
            ),
            campo="flujo.caudal_masico_kg_s",
            sugerencia="Reducir caudal o aumentar la sección transversal de la cámara.",
            contexto={"v_sup_m_s": round(v_sup, 3)},
        ))

    # --- FLUJO: HR de entrada no especificada ---
    if f.HR_entrada_fraccion is None:
        adv.append(Advertencia(
            codigo="FLUJO_HUMEDAD_ENTRADA_NO_ESPECIFICADA",
            severidad=Severidad.WARNING,
            mensaje=(
                "HR de entrada del aire no especificada. "
                "El cálculo de X_eq usará el fallback escalar del catálogo."
            ),
            campo="flujo.HR_entrada_fraccion",
            sugerencia="Especificar HR de entrada para mayor precisión en el cálculo de X_eq.",
            contexto={},
        ))

    # --- PROD: calidad de datos baja ---
    cf = datos.get("capa_fina") or {}
    modelo_entry = cf.get(p.modelo_capa_fina) or {}
    calidad = (modelo_entry.get("calidad_datos") or "").upper() if modelo_entry else ""
    if calidad in ("BAJA", "ESTIMADA_POR_ANALOGIA"):
        adv.append(Advertencia(
            codigo="PROD_CALIDAD_DATOS_BAJA",
            severidad=Severidad.WARNING,
            mensaje=(
                f"Modelo '{p.modelo_capa_fina}' para '{p.producto_id}' tiene "
                f"calidad '{calidad}'. Resultados orientativos."
            ),
            campo="carga_producto.modelo_capa_fina",
            sugerencia="Verificar con datos experimentales propios o literatura específica.",
            contexto={"calidad": calidad},
        ))

    # --- PROD: isoterma fallback ---
    iso = datos.get("isoterma") or {}
    iso_entry = iso.get(p.modelo_isoterma) or {}
    params_iso = iso_entry.get("params") or {} if iso_entry else {}
    params_iso_validos = (
        params_iso.get("X_m") is not None
        and params_iso.get("C") is not None
        and params_iso.get("K") is not None
    )
    X_eq_fallback = props.get("humedad_equilibrio_aire_seco")
    if not params_iso_validos and X_eq_fallback is not None:
        adv.append(Advertencia(
            codigo="PROD_ISOTERMA_FALLBACK",
            severidad=Severidad.CRITICAL,
            mensaje=(
                f"Sin isoterma GAB calibrada para '{p.producto_id}'. "
                f"Se usará X_eq = {X_eq_fallback:.3f} kg/kg ms (fallback escalar). "
                "La humedad de equilibrio real depende de la HR del aire."
            ),
            campo="carga_producto.modelo_isoterma",
            sugerencia="Cargar parámetros GAB en el catálogo para mayor precisión.",
            contexto={"X_eq_fallback": X_eq_fallback},
        ))

    # --- PROD: humedad objetivo inalcanzable (vs fallback estático) ---
    if X_eq_fallback is not None and p.humedad_objetivo_X < X_eq_fallback * 0.95:
        adv.append(Advertencia(
            codigo="PROD_HUMEDAD_OBJETIVO_INALCANZABLE",
            severidad=Severidad.CRITICAL,
            mensaje=(
                f"Humedad objetivo {p.humedad_objetivo_X:.3f} kg/kg ms está por debajo "
                f"del X_eq estimado ({X_eq_fallback:.3f} × 0.95 = {X_eq_fallback * 0.95:.3f}). "
                "El secador puede no alcanzar ese objetivo bajo las condiciones de operación."
            ),
            campo="carga_producto.humedad_objetivo_X",
            sugerencia="Aumentar X_objetivo o mejorar las condiciones de operación del secador.",
            contexto={"X_eq_estimado": X_eq_fallback, "X_objetivo": p.humedad_objetivo_X},
        ))

    # --- INIO: carne sin isoterma ---
    categoria = datos.get("categoria", "").upper()
    if categoria == "CARNE" and not params_iso_validos:
        adv.append(Advertencia(
            codigo="INIO_PRODUCTO_CARNE_SIN_ISOTERMA",
            severidad=Severidad.CRITICAL,
            mensaje=(
                f"ALERTA DE INOCUIDAD: '{p.producto_id}' (CARNE) sin isoterma calibrada. "
                "No es posible verificar que a_w < 0.85 en el producto seco."
            ),
            campo="carga_producto.modelo_isoterma",
            sugerencia=(
                "Cargar isoterma de carne con el nivel de sal equivalente al producto "
                "antes de usar los resultados para toma de decisiones."
            ),
            contexto={"producto_id": p.producto_id, "categoria": "CARNE"},
        ))

    return adv
