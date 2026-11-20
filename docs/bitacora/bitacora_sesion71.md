# Bitácora — Sesión 71

**Fecha:** 2026-11-20 · **Tema:** papers bajados desde el IER-UNAM e isoterma del charqui
(Comaposada 2000) con la meseta de la salmuera saturada. Continúa
[[docs/bitacora/bitacora_sesion70]] §16. Todo en `testing`, **sin commitear**.

## 1. Papers bajados (IER-UNAM, acceso autorizado por el usuario)

En `docs/Papers de secadores p_ calibrar secasol/` (fuera de git):
Comaposada 2000 (isotermas de carne salada), Demiray & Tulek 2012 (tomate), Demiray 2017
(cebolla), Doymaz 2004 (zanahoria: varía velocidad **y** espesor), Sanni 1997 (isotermas de
mandioca), Kaleemullah & Kailappan 2004 (isotermas de ají), Pauken 1999, Bower & Saylor 2009,
Shah 2012 (E&B; el de 2014 es ASHRAE Trans., no accesible por esta vía).

## 2. Isoterma del charqui (decisiones del usuario)

Comaposada, Gou & Arnau (2000) miden desorción de cerdo con 0/8/20/31 % NaCl b.s. a 5/13/26 °C.
No tabulan ni ajustan: se digitalizaron las Figs. 2 y 3 a 26 °C (puntos en el YAML).

**La carne salada tiene un escalón en a_w = 0.753** (solución saturada de NaCl): por debajo la
sal cristaliza y casi no retiene agua; por encima la disuelve. Una GAB única erraba hasta 4× en
X entre a_w 0.4 y 0.7 (a X = 0.2 daba a_w 0.45 contra ~0.72).

- **Decisión 1:** dos ramas + meseta. Rama baja = GAB de la carne sin sal ÷ (1+s) (el paper dice
  que debajo de 0.70 la sal no pesa en base libre de NaCl); meseta en 0.753 entre
  X = 0.169 y 0.662; rama alta = GAB con C = 1 sobre los puntos salados (el ajuste libre
  degenera: X_m → ∞, C → 0).
- **Decisión 2:** 20 % NaCl b.s. (~5 % sobre carne fresca).
- Base seca **total** (con la sal), coherente con `humedad_inicial_tipica`.
- Límite: 26 °C es la T más alta medida; a T de secado la isoterma real queda algo más baja.

## 3. Código

- `catalogo/productos/carnes.yaml`: bloque `isoterma.gab.meseta: {a_w, rama_alta}`.
- `core/catalogo.py`: `IsotermaGAB` gana `meseta_a_w`, `rama_alta`, `X_de_aw` (directa con
  escalón), `X_inicio_meseta`/`X_fin_meseta`/`K_max`; `_meseta_valida` (`CAT_MESETA_INVALIDA`);
  la meseta viaja también por analogía. `objetivo_secado` sin cambios de lógica (la bisección ya
  resuelve el escalón).
- `calculos/psicrometria.py::actividad_agua_isoterma(X, iso)`: inversa continua y monótona con
  meseta. La usan `camara_calc`, P4 (caption de a_w objetivo) y `validacion/difusividad`.
- **Dos bugs previos en `actividad_agua_desde_X_GAB`**, destapados por C = 1:
  - C = 1 resolvía `X(1−u)² = X_m·u`, que no es GAB (con C = 1 queda `X = X_m·u/(1−u)`). El
    test codificaba la misma fórmula equivocada. Ningún producto tenía C = 1.
  - C < 1 tiene dos raíces positivas y se tomaba la primera; ahora la menor.
  Test nuevo de ida y vuelta contra la GAB directa con C ∈ {0.5, 1, 6, 25}.
- Tests que usaban el charqui como "producto sin isoterma" ahora se la quitan con `monkeypatch`
  (el catálogo ya no tiene ninguno sin isoterma). Tests nuevos de la meseta en
  `tests/test_core/test_catalogo_isotermas.py`.

## 4. Efecto en la réplica de Durán 2008 (`validacion/duran2008/`)

| | a_w = 1 (hasta S70) | Comaposada | medido |
|---|---|---|---|
| X 18:30 día 1 | 0.54 | 0.55 | 0.57 |
| X 9:00 día 2 | 0.26 | 0.40 | ~0.48 (11 h) |
| X 17:00 día 2 | 0.15 | 0.18 | 0.24 |
| RMSE / MBE de X | 0.136 / −0.086 | **0.066 / −0.043** | |

Sigue secando algo de noche (0.15 contra ~0.09 medido) y queda seco de más el día 2.

## 5. D del charqui reajustado dentro de Secasol

El `D_ref = 1.1e-10` de S70 salió de un ajuste de Fick fuera de Secasol, con a_w = 1. Barrido de
D en la réplica completa (cada corrida ~1 s), con la isoterma nueva:

| D [m²/s] | 6e-11 | 9e-11 | **9.5e-11** | 1e-10 | 1.1e-10 | 2e-10 |
|---|---|---|---|---|---|---|
| RMSE_X | 0.142 | 0.050 | **0.048** | 0.051 | 0.066 | 0.201 |
| MBE_X | +0.129 | +0.016 | **0.000** | −0.015 | −0.043 | −0.185 |

Mínimo nítido: el ensayo está limitado por la difusión interna y D queda bien determinado
(siempre como D/L²: las fetas de 6 mm son un supuesto). Cargado **9.5e-11**. Con ese valor:
X 18:30 = 0.60 (med 0.57), 11:00 día 2 = 0.39 (0.48), 17:00 día 2 = 0.23 (0.24). Residuo: la
noche sigue secando ~0.15 de X contra ~0.09, y T del aire ~4 °C baja (lado térmico de la caja).

Barrido reproducible: `.venv/bin/python -m validacion.duran2008.barrido_difusividad` (monkeypatchea
`D_ref_m2_s` del charqui y corre la réplica completa por cada D).

## 6. Zanahoria: D crece con el espesor y no es el aire

**Papers.** El Doymaz 2004 bajado escalda los cubos y su Tabla 2 es inconsistente consigo
misma (D recalculado con su propia pendiente: 2× abajo en cubos de 2 cm, 18–50× en los de
1 cm). Se bajaron además **Doymaz 2017** (Heat Mass Transfer 53:25, rodajas control sin
pretratamiento, el que S70 tenía en mente), **Soydan & Doymaz 2026** (Chem Eng Commun, mismo
gabinete, 3/6/9 mm) y **Filipović 2022** (Thermal Science, OA, otro laboratorio, 3/6/9 mm).

**Método.** `validacion/difusividad/doymaz2017_zanahoria.py`: curvas X(t) **completas**
digitalizadas (Fig. 2A: 4/7/10 mm a 50 °C; Fig. 1: control 4 mm a 50/60/70 °C), simuladas en
Secasol con película de placa plana (Ø 2.5 cm, 2 m/s) + Fick en serie, D por curva.

**Hallazgo.**

| 50 °C | solo película | D óptimo | RMSE |
|---|---|---|---|
| 4 mm | RMSE 1.86 (seca rápido de más) | 2.9e-10 | 0.17 |
| 7 mm | 1.59 | 6.5e-10 | 0.17 |
| 10 mm | 1.44 | 1.0e-9 | 0.18 |

La película de Secasol no limita (solo película seca demasiado rápido). Un D único da RMSE
0.97; con un factor libre sobre h (0.05–1) el mejor par deja 0.63, y contando el canto de la
rodaja 0.49 — siempre con la fina rápida y la gruesa lenta. El tiempo crece ×1.6 de 4 a 10 mm:
**por debajo de los dos límites** de película + difusión en serie (×2.5 película pura, ×6.25
difusión pura). La regla de S70 ("D que crece con el espesor = limitaba el aire") **no aplica
acá**. Causa probable: encogimiento.

**Contraste.** Soydan & Doymaz 2026: 255/570/675 min para 3/6/9 mm (×2.65 para ×3), mismo
patrón, mismo gabinete. Filipović 2022: ×1.45–2.65 para ×3, pero con **carga fija de
3 kg/m²**: las rodajas de 3 mm cubren toda la bandeja (se superponen) y el área expuesta deja de
depender del espesor — que es justo como modela Secasol la bandeja. Sus D (1e-8 a 3e-7) son
dos órdenes altos y no se usan; solo informan tiempo hasta peso constante.

**Decisión del usuario:** cargar el D de 4 mm, calidad BAJA, con la anomalía documentada.
`zanahoria_rallada.difusion_interna`: D(50 °C) = **2.89e-10**, E_a = **29.1 kJ/mol** (Arrhenius
de 50/60/70 °C; el paper da 37.8), `dimension_pieza_m = 0.001` (rallado; el d_p del lecho queda
en el default porque también es rugosidad). Riesgo: si la tendencia sigue hacia piezas finas,
a 1 mm el secado real es más lento que el simulado.

## 7. Tomate y cebolla (Demiray): no dan D

Módulo común nuevo `validacion/difusividad/curvas.py` (`Ensayo`, `simular`, `error`,
`D_optimo`, `arrhenius`): pieza en capa fina con película + Fick en serie, contra curvas X(t)
completas. Suma al h de **calor** (no al de masa) la radiación linealizada con las paredes de un
gabinete calefaccionado, `h_rad = 4εσT³` ≈ 6 W/m²K. La zanahoria pasó a usarlo: no cambia
(2.89e-10; E_a 29.3 kJ/mol, actualizado en el catálogo).

- **Tomate (Demiray & Tulek 2012):** tomates **cortados en cuartos**, sin espesor informado, con
  piel de un lado; Fig. 2 es una nube dispersa. Su D (1.0–2.65e-9) usa un L desconocido. No
  se usa.
- **Cebolla (Demiray 2017):** rodajas de 7 mm, 0.2 m/s, 50/60/70 °C; Fig. 1 digitalizada
  (`validacion/difusividad/demiray2017_cebolla.py`). Su Tabla 4 (3.5–9.4e-8) está dos órdenes
  alta. En Secasol, **solo la película ya seca más lento que lo medido** (MBE +2.3 a +3.1 sin
  radiación, +0.8 a +1.4 con ella): no hay D posible (sale E_a = 142 kJ/mol, sin sentido). Con
  h ×2 la película sola casi ajusta. Causas probables: la rodaja se separa en anillos (área
  varias veces mayor que dos caras) y "0.2 m/s" es una lectura puntual. No se carga.

**Observación de modelo (no se tocó):** la cámara de Secasol no tiene intercambio IR
producto–paredes, solo radiación solar transmitida. En un gabinete a 0.2 m/s el IR de paredes
pesa tanto como la convección (6 contra 7 W/m²K). En secadores solares de convección natural
(0.1–0.3 m/s) con paredes calientes podría ser un hueco; evaluar con la réplica de Durán 2008
(caja con paredes al sol), que hoy queda ~4 °C fría.

## 8. Búsqueda de ensayos de tomate y cebolla (sin resultado utilizable)

Bajados a la carpeta de papers y descartados para D:

| paper | producto | por qué no |
|---|---|---|
| Akhijani 2016, Res Agr Eng 62:15 (OA) | tomate 3/5/7 mm × 0.5/1/2 m/s | secador **solar**: T variable no tabulada, Page en S (n 1.4–2.3) |
| Das Purkayastha 2013, J Food Sci Technol 50:642 | tomate | rodajas **escaldadas**; D no monótono con T |
| Süfer 2017, J Food Process Preserv 41:e13239 | cebolla 3/7 mm | horno de **convección natural**, rodajas en placa de Petri (1 cara), D con geometría de cilindro |
| Kumar 2006, LWT 39:700 | cebolla 2/4/6 mm | secado **infrarrojo** asistido por aire |
| Abbasi 2009 (SID) | cebolla, discos 3 mm × 30 mm | no se pudo bajar (sid.ir no entrega el PDF) |

**Patrón que se repite.** Akhijani 2016 (con t en min, única lectura coherente de su Tabla 2)
también da tiempo a MR = 0.2 ×1.5–1.7 para espesor ×2.33, por debajo de película pura, y la
velocidad pesa (×1.35–1.55 de 0.5 a 2 m/s). Son ya **cuatro ensayos de tres laboratorios**
(Doymaz 2017, Soydan & Doymaz 2026, Filipović 2022, Akhijani 2016) en zanahoria y tomate con
dependencia del espesor sub-lineal. En Filipović la explica la carga por área de bandeja; en
los otros, no hay explicación dentro de película + Fick. Candidato: **encogimiento** (las
rodajas finas pierden proporcionalmente más espesor y área). Si se confirma, es un hueco del
modelo que afecta a todo producto con D cargado desde un único espesor.

## 9. Pendientes

- Tomate y cebolla siguen sin D. Lo más útil sería un ensayo propio (rodajas de espesor
  medido, gabinete a T constante, velocidad conocida) o pedir datos crudos a los autores.
- ¿Encogimiento? Si la anomalía de espesor aparece en más productos, es un hueco del modelo.
- Isotermas de mandioca (Sanni 1997) y ají (Kaleemullah 2004): hoy corren por analogía.
- Agua libre: Pauken 1999 / Bower & Saylor 2009 / Shah 2012 contra la película de Fase 1.
- Ventilador de ADITAL (14.7 vs 4 HP), de §16 de S70.
