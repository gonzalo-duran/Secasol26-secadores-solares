# Glosario

Términos y símbolos usados en la interfaz y en este manual, en orden
alfabético. Las unidades son las internas (SI) salvo indicación.

## Términos {#terminos}

**Absorbedor** — la placa que capta la radiación en el colector y la transfiere
al aire. Su absortancia $\alpha$ define cuánta radiación convierte en calor.

**Actividad de agua ($a_w$)** — humedad relativa de equilibrio del aire en
contacto con el producto [0–1]. Mide cuán "disponible" está el agua del
producto. Ver [Física del secado](?manual=secado#actividad).

**Albedo ($\rho_g$)** — fracción de la radiación que el suelo refleja [0–1].
Entra en la componente reflejada de la [POA](?manual=radiacion#transposicion).

**Base seca / base húmeda** — dos formas de expresar la humedad del producto:
por kg de materia seca ($X$) o por kg totales ($w$). Secasol usa base seca.
Ver [Física del secado](?manual=secado#base-seca).

**Batch** — tanda o lote de secado: se carga, se seca completa, se descarga.

**Caño maestro** — el manifold que colecta el aire de las ramas del banco de
colectores en gran escala. Ver [Técnico · Industrial](?manual=tec-industrial#cano-maestro).

**COP de secado** — energía de evaporación obtenida por unidad de energía
invertida (solar útil + auxiliar + motor).

**CSTR** — *continuous stirred-tank reactor*: modelo de mezcla perfecta usado
para el aire de la cámara (sin gradientes internos).

**Cubierta** — el vidriado del colector o del techo de la cámara
(policarbonato, vidrio, film). Transmite radiación ($\tau$) y frena las
pérdidas convectivas.

**DHI / DNI / GHI** — las tres componentes de la radiación reportadas por las
bases de datos: difusa horizontal, directa normal y global horizontal. Ver
[Radiación solar](?manual=radiacion#componentes).

**Día típico mensual** — día de 24 h construido promediando hora a hora todos
los días de un mes. Base del modo de análisis Anual.

**Fracción solar** — parte del calor total aportada por el sol:
$E_{solar}/(E_{solar}+E_{auxiliar})$.

**GAB** — modelo de isoterma de sorción (Guggenheim–Anderson–de Boer) con
parámetros $X_m, C, K$ por producto. Ver [Física del secado](?manual=secado#isotermas).

**Isoterma de sorción** — relación de equilibrio $X \leftrightarrow a_w$ a
temperatura dada.

**Lazo Picard** — iteración de punto fijo que cierra el acople entre la
temperatura de la chimenea, el caudal natural y la salida del colector. Ver
[Técnico · Motor y chimenea](?manual=tec-chimenea#picard).

**POA** — *plane of array*: irradiancia sobre el plano inclinado y orientado
del colector, obtenida por transposición desde GHI/DNI/DHI. Es la radiación que
usan todos los cálculos de colector.

**Psicrometría** — termodinámica del aire húmedo. Ver
[Psicrometría](?manual=psicrometria).

**Semicontinuo** — subtipo de gran escala: túnel a contracorriente donde el
producto avanza por zonas mientras el aire circula en sentido opuesto.

**Set-point** — temperatura objetivo del auxiliar; el control entrega solo la
potencia necesaria para alcanzarla.

**Tiro térmico** — depresión que genera una columna de aire caliente (menos
denso) y que mueve el aire en convección natural.

**Ventana (de producción)** — lapso real [inicio, fin] sobre el que se corre el
análisis multidía con clima horario.

**Warm-start** — arrancar un solver desde la solución del punto anterior
(acelera y robustece la convergencia nodo a nodo del colector).

## Símbolos frecuentes {#simbolos}

| Símbolo | Magnitud | Unidad SI |
|---|---|---|
| $\beta$ | pendiente del colector | ° |
| $\gamma$ | acimut (convención Duffie) | ° |
| $\theta_z$, $\theta_i$ | ángulo cenital solar / de incidencia | ° |
| $I_g$, $I_{POA}$ | irradiancia global / en plano del colector | W/m² |
| $\tau$, $\alpha$, $\varepsilon$ | transmitancia, absortancia, emisividad | – |
| $T_f$, $T_{abs}$, $T_{prod}$, $T_{flujo}$ | temperaturas (fluido, absorbedor, producto, aire de cámara) | K |
| $\dot m$, $\dot m_{as}$ | caudal másico (aire, aire seco) | kg/s |
| $\dot m_w$ | tasa de evaporación | kg/s |
| $\omega$ | humedad absoluta del aire | kg agua/kg aire seco |
| $X$ | humedad del producto (base seca) | kg agua/kg seco |
| $a_w$ | actividad de agua | – |
| $h_{conv}$, $h_w$, $h_{int}$ | coef. de convección (producto, viento, canal) | W/(m²·K) |
| $K_m$ | coef. de transferencia de masa | kg/(m²·s) |
| $U$ | conductancia global | W/(m²·K) |
| $\Delta P$ | pérdida de carga | Pa |
| $Re$, $Nu$, $Pr$, $Ra$, $Le$, $Sh$ | números adimensionales (Reynolds, Nusselt, Prandtl, Rayleigh, Lewis, Sherwood) | – |
| $D_h$ | diámetro hidráulico | m |
| $L_v$, $h_v$ | calor latente / entalpía del vapor | J/kg |
| $c_p$, $c_{p,h}$ | calor específico (aire, aire húmedo) | J/(kg·K) |
| $\rho$, $\mu$, $k$ | densidad, viscosidad, conductividad | SI |
| $\varepsilon$ (lecho) | porosidad | – |
| $d_p$, $\Phi_s$ | diámetro de partícula, esfericidad | m, – |

---

**Ver también:** [Convenciones de unidades y ángulos](?manual=convenciones).
