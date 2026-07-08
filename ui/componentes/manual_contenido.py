"""Tabla de contenidos (TOC) declarativa del manual de usuario.

Este módulo NO importa streamlit: es la fuente de verdad de qué capítulos
existen, en qué orden se navegan y a qué archivo markdown corresponde cada
slug. Lo consumen el visor (``ui/manual.py``), el helper de botones
(``ui/componentes/manual_link.py``) y los tests de integridad
(``tests/test_ui/test_manual.py``).

El contenido vive en ``manual/capitulos/*.md`` (raíz del repo). Cada capítulo
se identifica por un *slug* en kebab-case que es la clave del query param
(``?manual=<slug>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CAPITULOS_DIR = Path(__file__).resolve().parent.parent.parent / "manual" / "capitulos"

# Slug reservado para la página índice (no corresponde a ningún .md).
SLUG_INDICE = "indice"


@dataclass(frozen=True)
class CapituloManual:
    """Un capítulo del manual.

    Attributes:
        slug: Identificador kebab-case usado en ``?manual=<slug>``.
        titulo: Título humano mostrado en índice, sidebar y breadcrumb.
        archivo: Nombre del archivo markdown dentro de ``manual/capitulos/``.
        parte: Rótulo de la parte a la que pertenece (agrupa el índice).
        descripcion: Una línea para la card del índice.
    """

    slug: str
    titulo: str
    archivo: str
    parte: str
    descripcion: str

    @property
    def ruta(self) -> Path:
        """Ruta absoluta al archivo markdown del capítulo."""
        return CAPITULOS_DIR / self.archivo


_PARTE_I = "Parte I — Empezar"
_PARTE_II = "Parte II — Guía por secciones"
_PARTE_III = "Parte III — Fundamentos"
_PARTE_IV = "Parte IV — Referencia técnica"
_APENDICES = "Apéndices"

# Orden de la tupla = orden de navegación (índice, sidebar, anterior/siguiente).
CAPITULOS: tuple[CapituloManual, ...] = (
    CapituloManual(
        slug="introduccion",
        titulo="Introducción",
        archivo="01_introduccion.md",
        parte=_PARTE_I,
        descripcion="Qué es Secasol, alcance de prediseño, flujo de trabajo y cómo usar este manual.",
    ),
    CapituloManual(
        slug="tipologia",
        titulo="1 · Tipología",
        archivo="10_tipologia.md",
        parte=_PARTE_II,
        descripcion="Caja, armario o gran escala; modo de análisis y ventana de producción.",
    ),
    CapituloManual(
        slug="emplazamiento",
        titulo="2 · Emplazamiento y clima",
        archivo="11_emplazamiento.md",
        parte=_PARTE_II,
        descripcion="Coordenadas, descarga NASA POWER, calidad de datos y orientación del colector.",
    ),
    CapituloManual(
        slug="colector",
        titulo="3 · Colector solar",
        archivo="12_colector.md",
        parte=_PARTE_II,
        descripcion="Los 4 tipos de colector de aire, materiales, geometría y banco.",
    ),
    CapituloManual(
        slug="camara",
        titulo="4 · Cámara de secado",
        archivo="13_camara.md",
        parte=_PARTE_II,
        descripcion="Geometría, paredes, bandejas, producto y modos de operación de la cámara.",
    ),
    CapituloManual(
        slug="auxiliar",
        titulo="5 · Calentamiento auxiliar",
        archivo="14_auxiliar.md",
        parte=_PARTE_II,
        descripcion="Respaldo eléctrico o a biomasa: modos de operación y consumos.",
    ),
    CapituloManual(
        slug="motor",
        titulo="6 · Motor y chimenea",
        archivo="15_motor.md",
        parte=_PARTE_II,
        descripcion="Ventilador, chimenea solar y extractor eólico; pérdidas de carga del circuito.",
    ),
    CapituloManual(
        slug="resultados",
        titulo="7 · Resultados",
        archivo="16_resultados.md",
        parte=_PARTE_II,
        descripcion="Correr el prediseño, leer el dashboard, carta psicrométrica y exportación.",
    ),
    CapituloManual(
        slug="radiacion",
        titulo="Radiación solar y plano orientado",
        archivo="20_radiacion.md",
        parte=_PARTE_III,
        descripcion="Componentes GHI/DNI/DHI, geometría solar y transposición al plano del colector.",
    ),
    CapituloManual(
        slug="psicrometria",
        titulo="Psicrometría",
        archivo="21_psicrometria.md",
        parte=_PARTE_III,
        descripcion="Humedad absoluta y relativa, saturación, y cómo leer la carta psicrométrica.",
    ),
    CapituloManual(
        slug="secado",
        titulo="Física del secado",
        archivo="22_fisica_secado.md",
        parte=_PARTE_III,
        descripcion="Actividad de agua, isotermas de sorción y la dinámica del producto.",
    ),
    CapituloManual(
        slug="catalogo-productos",
        titulo="El catálogo de productos",
        archivo="24_catalogo_productos.md",
        parte=_PARTE_III,
        descripcion="Qué productos trae Secasol, cómo se eligieron, humedades típicas y estado de calibración.",
    ),
    CapituloManual(
        slug="convenciones",
        titulo="Convenciones de unidades y ángulos",
        archivo="23_convenciones.md",
        parte=_PARTE_III,
        descripcion="SI estricto interno y las tres convenciones de acimut que usa Secasol.",
    ),
    CapituloManual(
        slug="tec-emplazamiento",
        titulo="Técnico · Recurso solar y clima",
        archivo="30_tec_emplazamiento.md",
        parte=_PARTE_IV,
        descripcion="NASA POWER, política de huecos y transposición Liu-Jordan con ecuaciones.",
    ),
    CapituloManual(
        slug="tec-colector",
        titulo="Técnico · Colector de placa plana",
        archivo="31_tec_colector.md",
        parte=_PARTE_IV,
        descripcion="Balances por superficie de los 4 tipos, correlaciones de Nusselt y solución numérica.",
    ),
    CapituloManual(
        slug="tec-camara",
        titulo="Técnico · Cámara de secado",
        archivo="32_tec_camara.md",
        parte=_PARTE_IV,
        descripcion="Balance acoplado calor-masa, pared compuesta, techo translúcido y bandejas.",
    ),
    CapituloManual(
        slug="tec-industrial",
        titulo="Técnico · Modo industrial",
        archivo="33_tec_industrial.md",
        parte=_PARTE_IV,
        descripcion="Banco de colectores, caño maestro, túnel semicontinuo y validación ADITAL.",
    ),
    CapituloManual(
        slug="tec-chimenea",
        titulo="Técnico · Motor, chimenea y pérdidas de carga",
        archivo="34_tec_chimenea_motor.md",
        parte=_PARTE_IV,
        descripcion="ΔP del circuito, tiro térmico, extractor eólico y lazo Picard.",
    ),
    CapituloManual(
        slug="tec-auxiliar",
        titulo="Técnico · Calentamiento auxiliar",
        archivo="35_tec_auxiliar.md",
        parte=_PARTE_IV,
        descripcion="Balance del auxiliar, control por set-point y calendario de arranque.",
    ),
    CapituloManual(
        slug="tec-resultados",
        titulo="Técnico · Balance global y resultados",
        archivo="36_tec_resultados.md",
        parte=_PARTE_IV,
        descripcion="Orquestación del cálculo, modos constantes/transitorio/ventana y verificación.",
    ),
    CapituloManual(
        slug="apendice-codigo",
        titulo="Apéndice · Implementación en código",
        archivo="90_apendice_codigo.md",
        parte=_APENDICES,
        descripcion="Dónde vive cada modelo en el código fuente, para quien quiera leerlo o extenderlo.",
    ),
    CapituloManual(
        slug="glosario",
        titulo="Glosario",
        archivo="91_glosario.md",
        parte=_APENDICES,
        descripcion="Términos y símbolos usados en el manual y en la interfaz.",
    ),
    CapituloManual(
        slug="bibliografia",
        titulo="Bibliografía",
        archivo="92_bibliografia.md",
        parte=_APENDICES,
        descripcion="Referencias citadas en los capítulos técnicos.",
    ),
)

# Índice rápido slug → capítulo.
POR_SLUG: dict[str, CapituloManual] = {c.slug: c for c in CAPITULOS}

# Partes en orden de aparición (para agrupar índice y sidebar).
PARTES: tuple[str, ...] = tuple(dict.fromkeys(c.parte for c in CAPITULOS))

# Capítulo del manual que corresponde a cada sección de la app de diseño.
SLUG_POR_SECCION: dict[str, str] = {
    "p1": "tipologia",
    "p2": "emplazamiento",
    "p3": "colector",
    "p4": "camara",
    "p5": "auxiliar",
    "p6": "motor",
    "p7": "resultados",
}
