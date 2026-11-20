"""
Cargador del catálogo de materiales del colector solar.

Carga los cuatro archivos YAML de la carpeta catalogo/materiales/ al importar
el módulo. Los diccionarios resultantes son de solo lectura durante la sesión.

Estructura de cada entrada de material:
    descripcion, conductividad_termica [W/m·K], densidad [kg/m³],
    calor_especifico [J/kg·K], T_max_servicio [K], fuente, notas.
    Cubiertas añaden: transmitancia_solar, emisividad_ir.
    Placas añaden: absortancia_solar, emisividad_ir.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from typing import Any

import yaml

_RAIZ: pathlib.Path = pathlib.Path(__file__).parent.parent
_DIR_MATERIALES: pathlib.Path = _RAIZ / "catalogo" / "materiales"
_DIR_PRODUCTOS: pathlib.Path = _RAIZ / "catalogo" / "productos"

_ARCHIVOS_PRODUCTOS: list[str] = [
    "frutas.yaml",
    "hortalizas.yaml",
    "carnes.yaml",
    "hojas_aromaticas.yaml",
    "legumbres_frutos.yaml",
]


def _cargar(nombre: str) -> dict[str, Any]:
    """Carga un archivo YAML de materiales desde la carpeta catalogo/materiales/.

    Args:
        nombre: Nombre del archivo YAML (ej.: 'cubiertas.yaml').

    Returns:
        Diccionario con los materiales del archivo.

    Raises:
        RuntimeError: Si el archivo no existe o no puede parsearse.
    """
    ruta = _DIR_MATERIALES / nombre
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"Catálogo no encontrado: {ruta}. "
            "Verificá que el archivo exista en catalogo/materiales/."
        )
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Error al parsear {ruta}: {exc}") from exc
    return datos or {}


def _cargar_productos() -> dict[str, Any]:
    """Carga y fusiona todos los archivos YAML de productos en un único diccionario.

    Cada archivo puede contener múltiples productos como claves de primer nivel.
    En caso de colisión de IDs entre archivos, el último archivo gana y se emite
    una advertencia en stderr.

    Returns:
        Diccionario {producto_id: datos_producto} con todos los productos disponibles.
    """
    import sys

    resultado: dict[str, Any] = {}
    for archivo in _ARCHIVOS_PRODUCTOS:
        ruta = _DIR_PRODUCTOS / archivo
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"[catalogo] Advertencia: {ruta} no encontrado, ignorado.", file=sys.stderr)
            continue
        except yaml.YAMLError as exc:
            print(f"[catalogo] Error al parsear {ruta}: {exc}", file=sys.stderr)
            continue
        if not datos:
            continue
        for prod_id, prod_datos in datos.items():
            if prod_id in resultado:
                print(
                    f"[catalogo] Advertencia: producto '{prod_id}' duplicado en {archivo}, "
                    "se sobreescribe.",
                    file=sys.stderr,
                )
            resultado[prod_id] = prod_datos
    return resultado


# Catálogos de materiales — cargados al importar el módulo
CUBIERTAS: dict[str, Any] = _cargar("cubiertas.yaml")
PLACAS: dict[str, Any] = _cargar("placas.yaml")
AISLANTES: dict[str, Any] = _cargar("aislantes.yaml")
FONDOS: dict[str, Any] = _cargar("fondos.yaml")

# Catálogo de productos — fusión de todos los archivos de productos
PRODUCTOS: dict[str, Any] = _cargar_productos()


def _cargar_isotermas_referencia() -> dict[str, Any]:
    """Carga catalogo/isotermas_referencia.yaml (materiales que no son productos).

    Returns:
        Diccionario {id: datos} con el mismo esquema `isoterma.gab` que los
        productos. Vacío si el archivo no existe.
    """
    ruta = _RAIZ / "catalogo" / "isotermas_referencia.yaml"
    try:
        with open(ruta, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


# Isotermas de materiales de referencia para analogías (S70)
ISOTERMAS_REFERENCIA: dict[str, Any] = _cargar_isotermas_referencia()


@dataclass(frozen=True)
class IsotermaGAB:
    """Parámetros GAB resueltos para un producto (S70).

    Attributes:
        X_m: Humedad de monocapa [kg_agua/kg_seco].
        C: Constante de Guggenheim [adim].
        K: Constante multicapa [adim]. Puede ser ≥ 1 (ajustes de desorción de
            productos azucarados); ver `actividad_agua_desde_X_GAB`.
        origen: "propia" si el producto tiene isoterma medida; "analogia" si
            la toma prestada de otro material.
        material_fuente: Id del producto o material de referencia del que
            salen los parámetros (el propio producto si `origen == "propia"`).
    """

    X_m: float
    C: float
    K: float
    origen: str
    material_fuente: str


def _params_gab_validos(datos: dict[str, Any] | None) -> tuple[float, float, float] | None:
    """Devuelve (X_m, C, K) si el bloque `isoterma.gab.params` está completo y positivo."""
    gab = ((datos or {}).get("isoterma") or {}).get("gab") or {}
    params = gab.get("params") or {}
    try:
        valores = tuple(float(params[k]) for k in ("X_m", "C", "K"))
    except (KeyError, TypeError, ValueError):
        return None
    if any(v <= 0.0 for v in valores):
        return None
    return valores  # type: ignore[return-value]


def isoterma_gab(producto_id: str) -> IsotermaGAB | None:
    """Resuelve la isoterma GAB de un producto: propia o por analogía.

    Orden: (1) `isoterma.gab.params` del producto; (2) si faltan,
    `isoterma.gab.analogia: <id>`, que se busca primero entre los productos
    (su isoterma **propia**, sin encadenar analogías) y después en
    catalogo/isotermas_referencia.yaml. La analogía es una decisión de catálogo
    documentada en cada producto (fuente y notas), no una inferencia del código.

    Args:
        producto_id: Id del producto en el catálogo.

    Returns:
        `IsotermaGAB`, o None si el producto no tiene isoterma propia ni una
        analogía resoluble. El llamador decide la reserva y el aviso.
    """
    datos = PRODUCTOS.get(producto_id) or {}
    propios = _params_gab_validos(datos)
    if propios is not None:
        return IsotermaGAB(*propios, origen="propia", material_fuente=producto_id)

    analogia = (((datos.get("isoterma") or {}).get("gab")) or {}).get("analogia")
    if not analogia:
        return None
    fuente = PRODUCTOS.get(analogia) or ISOTERMAS_REFERENCIA.get(analogia)
    prestados = _params_gab_validos(fuente)
    if prestados is None:
        return None
    return IsotermaGAB(*prestados, origen="analogia", material_fuente=str(analogia))


# ---------------------------------------------------------------------------
# Difusión interna del producto (S70, plan modelo de evaporación Fase 2)
# ---------------------------------------------------------------------------

#: Primer autovalor de difusión por geometría de la pieza. La tasa del primer
#: modo de Fick es ``λ = μ₁²·D_eff/L²`` con ``L`` = semiespesor (lámina) o radio.
AUTOVALOR_DIFUSION: dict[str, float] = {
    "lamina": math.pi / 2.0,
    "cilindro": 2.404825557695773,
    "esfera": math.pi,
}

_R_GAS_J_MOLK = 8.314462618


@dataclass(frozen=True)
class DifusionInterna:
    """Difusividad efectiva del agua en el producto (S70).

    Attributes:
        D_ref_m2_s: Difusividad efectiva a ``T_ref_K`` [m²/s].
        T_ref_K: Temperatura de referencia [K].
        E_a_J_mol: Energía de activación de Arrhenius [J/mol]. 0 = sin
            dependencia con la temperatura.
        geometria: ``"lamina"``, ``"cilindro"`` o ``"esfera"``.
    """

    D_ref_m2_s: float
    T_ref_K: float
    E_a_J_mol: float
    geometria: str

    def D_eff_m2_s(self, T_K: float) -> float:
        """Difusividad a ``T_K`` por Arrhenius."""
        return self.D_ref_m2_s * math.exp(
            -self.E_a_J_mol / _R_GAS_J_MOLK * (1.0 / T_K - 1.0 / self.T_ref_K)
        )

    def tasa_primer_modo_s(self, T_K: float, dimension_pieza_m: float) -> float:
        """λ = μ₁²·D_eff(T)/L² [1/s], con ``L = dimension_pieza_m / 2``.

        ``dimension_pieza_m`` es el espesor de la lámina o el diámetro del
        cilindro/esfera: el mismo ``d_p`` que usa el lecho (``core.lecho``).
        """
        L = dimension_pieza_m / 2.0
        return AUTOVALOR_DIFUSION[self.geometria] ** 2 * self.D_eff_m2_s(T_K) / (L * L)


def difusion_interna(producto_id: str) -> DifusionInterna | None:
    """Difusividad efectiva del producto, o None si el catálogo no la trae.

    Lee el bloque ``difusion_interna`` del producto. **Sin analogías**: la
    difusividad depende de la microestructura y del corte, y prestarla entre
    productos sería inventar el dato que más pesa en el tiempo de secado.

    Args:
        producto_id: Id del producto en el catálogo.

    Returns:
        `DifusionInterna`, o None si el bloque falta o está incompleto.
    """
    bloque = (PRODUCTOS.get(producto_id) or {}).get("difusion_interna") or {}
    try:
        D = float(bloque["D_ref_m2_s"])
        T_ref = float(bloque["T_ref_K"])
        E_a = float(bloque.get("E_a_J_mol") or 0.0)
    except (KeyError, TypeError, ValueError):
        return None
    geometria = str(bloque.get("geometria", "lamina"))
    if D <= 0.0 or T_ref <= 0.0 or E_a < 0.0 or geometria not in AUTOVALOR_DIFUSION:
        return None
    return DifusionInterna(D_ref_m2_s=D, T_ref_K=T_ref, E_a_J_mol=E_a, geometria=geometria)


# ---------------------------------------------------------------------------
# Objetivo de secado por producto (S70)
# ---------------------------------------------------------------------------

#: a_w objetivo por defecto: umbral habitual de estabilidad microbiológica de
#: frutas, hortalizas y hojas secas (por debajo de ~0.6 no crecen mohos ni
#: levaduras). Un producto puede declarar otro en ``objetivo_secado.a_w``.
AW_OBJETIVO_DEFAULT: float = 0.60

#: X objetivo de reserva para productos sin isoterma ni X declarado [kg/kg ms].
#: Es el valor global que Secasol usaba para todos hasta S70; no tiene criterio
#: de a_w detrás.
X_OBJETIVO_RESERVA: float = 0.15


@dataclass(frozen=True)
class ObjetivoSecado:
    """Humedad final objetivo de un producto y de dónde sale (S70).

    Attributes:
        X: Humedad objetivo en base seca [kg agua / kg ms].
        a_w: Actividad de agua que corresponde a ``X`` según la isoterma del
            producto, o None si no tiene isoterma.
        origen: ``"aw_default"`` (isoterma en ``AW_OBJETIVO_DEFAULT``),
            ``"aw_catalogo"`` (isoterma en la a_w que declara el producto),
            ``"X_catalogo"`` (X declarado: criterio comercial) o ``"reserva"``.
    """

    X: float
    a_w: float | None
    origen: str


def humedad_desde_aw_gab(iso: IsotermaGAB, a_w: float) -> float:
    """Isoterma GAB directa: ``X = X_m·C·K·a / ((1 − K·a)·(1 − K·a + C·K·a))``.

    Raises:
        ValueError: ``CAT_AW_FUERA_DE_ISOTERMA`` si ``K·a_w ≥ 1`` (la GAB diverge).
    """
    u = iso.K * a_w
    if not 0.0 <= a_w < 1.0 or u >= 1.0:
        raise ValueError(
            f"CAT_AW_FUERA_DE_ISOTERMA: a_w={a_w:.3f} con K={iso.K:.4f} (K·a_w = {u:.3f} ≥ 1)."
        )
    return iso.X_m * iso.C * u / ((1.0 - u) * (1.0 - u + iso.C * u))


def objetivo_secado(producto_id: str) -> ObjetivoSecado:
    """X objetivo por defecto del producto, derivado de una a_w objetivo (S70).

    Prioridad: ``objetivo_secado.X`` del catálogo (criterio comercial, p. ej.
    humedad de venta) → ``objetivo_secado.a_w`` del catálogo → ``AW_OBJETIVO_DEFAULT``
    sobre la isoterma (propia o por analogía) → ``X_OBJETIVO_RESERVA``.

    Las isotermas del catálogo están a ~45 °C; a temperatura de almacenamiento la
    misma X da una a_w algo menor, así que el criterio queda del lado seguro.
    """
    bloque = (PRODUCTOS.get(producto_id) or {}).get("objetivo_secado") or {}
    iso = isoterma_gab(producto_id)

    def _aw_de(X: float) -> float | None:
        if iso is None:
            return None
        lo, hi = 0.0, 1.0 / iso.K if iso.K > 1.0 else 1.0
        for _ in range(60):  # bisección sobre la GAB directa (monótona)
            mid = 0.5 * (lo + hi)
            try:
                X_mid = humedad_desde_aw_gab(iso, mid)
            except ValueError:
                hi = mid
                continue
            lo, hi = (mid, hi) if X_mid < X else (lo, mid)
        return 0.5 * (lo + hi)

    if bloque.get("X") is not None:
        X = float(bloque["X"])
        return ObjetivoSecado(X=X, a_w=_aw_de(X), origen="X_catalogo")
    if iso is not None:
        a_w = float(bloque.get("a_w") or AW_OBJETIVO_DEFAULT)
        origen = "aw_catalogo" if bloque.get("a_w") is not None else "aw_default"
        return ObjetivoSecado(X=humedad_desde_aw_gab(iso, a_w), a_w=a_w, origen=origen)
    return ObjetivoSecado(X=X_OBJETIVO_RESERVA, a_w=None, origen="reserva")
