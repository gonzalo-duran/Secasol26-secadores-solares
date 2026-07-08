# Técnico · Motor, chimenea solar y pérdidas de carga

Referencia técnica del movimiento del aire: pérdidas de carga globales del
sistema (ecuaciones por tramo), dimensionamiento del ventilador en convección
forzada, caudal de equilibrio en convección natural, lazo Picard, extractor
eólico y dimensionamiento de la chimenea solar. La guía de uso está en
[6 · Motor y chimenea](?manual=motor).

## 1. Dos formas de mover el aire {#dos-formas}

El aire puede circular por **convección forzada** (ventilador axial o
centrífugo) o por **convección natural** (chimenea solar, opcionalmente con
extractor eólico). La sección Motor habilita una u otra: con motor apagado
aparece la chimenea. El extractor eólico es **accesorio de la chimenea**, no un
tipo de motor.

En ambos casos hace falta la **pérdida de carga global** del lazo. La
diferencia: en forzada la $\Delta P$ **dimensiona el motor**; en natural la
$\Delta P$ (como función del caudal) **determina el caudal de equilibrio**.

## 2. Pérdidas de carga globales — ecuaciones por tramo {#perdidas}

Las pérdidas se descomponen en tramos en serie. Todos usan el mismo factor de
fricción de **Haaland** (aproximación explícita de Colebrook-White, ASHRAE
cap. 21):

$$
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
\quad(Re>4000),
\qquad f=\frac{64}{Re}\ (Re<2300)
$$

con mezcla lineal en la transición $2300<Re<4000$.

### 2.1 Colector (canal rectangular) — Darcy-Weisbach {#dp-colector}

$$
\Delta P_{col} = f\,\frac{L}{D_h}\,\frac{\rho v^2}{2},\qquad D_h=\frac{2We}{W+e}
$$

Serie: $\Delta P_{rama}=\Delta P_{unidad}\times n_{serie}$; paralelo:
$\Delta P_{banco}=\Delta P_{rama}$.

### 2.2 Cámara — según orientación del flujo {#dp-camara}

- **HORIZONTAL (cross-flow):** los $n_{bandejas}-1$ canales entre bandejas
  están **en paralelo** → la $\Delta P$ del sistema es la de **un** canal.
  $\Delta P_{cam}=\Delta P_{producto}+\Delta P_{malla}$, con
  $\Delta P_{producto}$ = fricción rugosa (rugosidad efectiva
  $\varepsilon_{eff}=\max(\varepsilon_{chapa},d_p)$) + obstrucción por bloqueo
  $C_{obs}(\beta)$, $\beta=e_{capa}/\text{separación}$.
- **VERTICAL ASCENDENTE (through-bed):** por bandeja
  $\Delta P=\Delta P_{malla}+\Delta P_{lecho}$ con **Ergun**:
  $$
  \frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
  $$
  La $\Delta P$ de malla usa coeficientes K tipo Idelchik/Crane según el tipo
  de malla.

### 2.3 Ductos y singulares {#dp-ductos}

$\Delta P_{ductos}$ por Darcy-Weisbach (rugosidad de galvanizado
$\varepsilon\approx0.15$ mm, ASHRAE) y singulares $\Delta P=K\,\rho v^2/2$
(codos, expansiones, entradas/salidas).

### 2.4 Caño maestro (solo gran escala) {#dp-cano}

En Gran escala se **suma** la $\Delta P$ del caño maestro (flujo acumulado,
sección variable — ver [Técnico · Modo industrial](?manual=tec-industrial#dp-cano)).

**Propiedades del aire:** $\rho(T,P)=P/(R_{aire}T)$ (gas ideal,
$R_{aire}=287.058$); $\mu(T)$ por Sutherland; presión atmosférica por altitud
según atmósfera estándar (ISA).

## 3. Convección forzada — dimensionamiento del motor {#forzada}

Con la $\Delta P$ total y el caudal volumétrico $Q$, las potencias se calculan
en cascada:

$$
P_{hid}=Q\,\Delta P
\;\xrightarrow{/\eta_{vent}}\;
P_{eje}=\frac{P_{hid}}{\eta_{vent}}
\;\xrightarrow{/\eta_{motor}}\;
P_{elec}=\frac{P_{eje}}{\eta_{motor}}
\;\xrightarrow{\times FS}\;
P_{inst}=P_{elec}\cdot FS
$$

con $\eta_{vent}$ rendimiento del ventilador, $\eta_{motor}$ del motor
eléctrico, $FS$ factor de servicio. La **corriente nominal** sale de
$I=P_{elec}/(V\cos\varphi)$, con $\cos\varphi=0.85$ (motor pequeño). Si el
usuario fija una velocidad de descarga, se añade la presión dinámica
$\Delta P_{din}=\rho v_{desc}^2/2$ a la $\Delta P$ total.

**Anclaje empírico** para validar el orden de magnitud: extractor de 76 W /
900 m³/h en un armario de ~50 kg → $P_{elec}$ esperada **50–100 W**.

## 4. Convección natural — caudal de equilibrio {#natural}

Sin motor, el aire circula por **tiro térmico**. El caudal de equilibrio es
aquel en que la presión **motriz** iguala la **resistiva**:

$$
\boxed{\;\Delta P_{tiro} + \Delta P_{turbina,motriz} = \Delta P_{chimenea}(\dot m) + \Delta P_{resto}(\dot m)\;}
$$

### 4.1 Tiro térmico (stack effect) {#tiro}

$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim}),
\qquad H_{eff}=H_{chimenea}+H_{camara}
$$

Con gas ideal a presión común $\rho\propto1/T$, así que $\Delta P_{tiro}>0$
cuando $T_{chim}>T_{amb}$ (flujo ascendente) y $\Delta P_{tiro}<0$ cuando
$T_{chim}<T_{amb}$ (tiro nulo de noche → $\dot m=0$). $H_{eff}$ incluye la
altura útil de la cámara (desde la entrada de aire frío hasta la base de la
chimenea).

### 4.2 Resolución numérica {#brentq}

$\Delta P_{chimenea}(\dot m)$ (fricción + singulares + resistencia del
extractor) y $\Delta P_{resto}(\dot m)$ (colector + cámara + ductos, función
monótona con $f(0)=0$) son funciones del caudal. La raíz de la ecuación de
equilibrio se resuelve con **`scipy.optimize.brentq`** acotada a
$[\dot m_{min}, \dot m_{max}]$. Devuelve $\dot m$, la velocidad en chimenea y
todas las componentes de $\Delta P$.

## 5. Extractor eólico (turbina sombrero chino) {#extractor}

Accesorio opcional en el tope de la chimenea. Agrega **dos** términos:

- **Motriz** — depresión que genera la rotación de la turbina:
  $$\Delta P_{turbina}=C_p\,\rho_{amb}\,v_{viento}^2/2$$
  con $C_p\approx0.3$–$0.6$. El viento NASA POWER (medido a **10 m**) se
  corrige a la **altura del tope** $z=H_{camara}+H_{chimenea}$ por **perfil
  logarítmico**:
  $$v(z)=v_{10}\,\frac{\ln(z/z_0)}{\ln(10/z_0)}$$
  con $z_0$ la rugosidad aerodinámica del terreno.
- **Resistivo** — la turbina obstruye el flujo:
  $\Delta P=K_t\,\rho_{chim}\,v_{ext}^2/2$, evaluado a la velocidad por el
  diámetro propio del extractor.

El término motriz entra al lado izquierdo de la ecuación de equilibrio; el
resistivo, al $\Delta P_{chimenea}$.

## 6. Lazo Picard — acople térmico-hidráulico {#picard}

El caudal natural toma $T_{chim}$ **como dato**, pero físicamente $T_{chim}$
depende del caudal (a más caudal, menos $\Delta T$ en el colector → $T_{chim}$
baja → menos tiro). Este acople se cierra con **iteración de punto fijo
(Picard)** sobre el triángulo:

$$
T_{chim} \longleftrightarrow \dot m_{nat} \longleftrightarrow T_{salida,colector}
$$

- **Modo Constantes**: hasta 10 iteraciones, tolerancia 0.5 K. En cada
  iteración se re-corre el colector estacionario con la velocidad implicada por
  el caudal natural, se recalcula $\dot m_{nat}$, y la temperatura del aire de
  cámara realimenta $T_{chim}$.
- **Modo Transitorio**: Picard sobre **todo el horizonte** horario, hasta 5
  iteraciones, tolerancia 0.5 K. Por iteración se calcula $\dot m(t)$ hora a
  hora, se re-corre el solver del colector cada hora con la velocidad efectiva
  $v(t)=\dot m_{nat}(t)/(\rho A_{canal} n_{par})$, el motor de cámara consume
  las nuevas forzantes y $T_{flujo}(t)$ realimenta $T_{chim}(t)$.

Si la chimenea tiene **extractor activo**, el balance del lazo suma además
$\Delta P_{turbina,motriz}(v_{viento}(t))$ al lado motriz y $K_t\rho v^2/2$ al
resistivo. Las horas con tiro nulo ($T_{chim}\le T_{amb}$) reciben $\dot m=0$.

## 7. Dimensionamiento de la chimenea solar {#chimenea}

La chimenea se dimensiona por su **geometría** (diámetro, altura), que fija:

- El **tiro disponible** vía $H_{eff}$ (a mayor altura, mayor
  $\Delta P_{tiro}$).
- La **resistencia propia** $\Delta P_{chimenea}=K_{total}\,\rho v^2/2$ con
  $K_{total}=f\,H/D+K_{singular}$.

El prediseño busca la combinación diámetro/altura que entrega el caudal
objetivo con el $\Delta T$ esperado del colector. La chimenea es un componente
**de nivel superior** del proyecto (no un subcomponente del colector), lo que
permite chimenea solar también en tipología Caja.

---

**Ver también:** [6 · Motor y chimenea](?manual=motor) (guía de uso),
[Técnico · Colector](?manual=tec-colector#perdidas) y
[Técnico · Cámara](?manual=tec-camara#bandejas) (las $\Delta P$ de cada tramo),
[Técnico · Balance global](?manual=tec-resultados) (dónde se cierra el lazo),
[Apéndice · Implementación](?manual=apendice-codigo#motor),
[Bibliografía](?manual=bibliografia#ashrae).
