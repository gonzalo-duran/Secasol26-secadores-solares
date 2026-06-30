# 05 · Movimiento del aire — Motor y Chimenea solar

> Material fuente para el seminario INENCO. Audiencia técnica.
> Cubre: pérdidas de carga globales del sistema (ecuaciones por tramo), el
> dimensionamiento del ventilador en convección forzada, la determinación del
> caudal en convección natural, el **lazo Picard**, el extractor eólico y el
> dimensionamiento de la chimenea solar.

---

## 1. Dos formas de mover el aire

El aire puede circular por **convección forzada** (ventilador axial o centrífugo)
o por **convección natural** (chimenea solar, opcionalmente con extractor eólico).
La pestaña **P6** habilita una u otra: con motor OFF aparece la chimenea. El
tipo de accionamiento (`TipoAccionamiento`) solo tiene **MOTOR_ELECTRICO** y
**CONVECCION_NATURAL** desde S31 — el extractor eólico es **accesorio de la
chimenea**, no un tipo de motor.

En ambos casos hace falta la **pérdida de carga global** del lazo. La diferencia:
en forzada la $\Delta P$ **dimensiona el motor**; en natural la $\Delta P$ (como
función del caudal) **determina el caudal de equilibrio**.

---

## 2. Pérdidas de carga globales — ecuaciones por tramo

Las pérdidas de carga globales se descomponen en tramos en serie. Todos usan el mismo factor de fricción de **Haaland** (aprox. explícita de Colebrook-White, ASHRAE cap. 21):

$$
\frac{1}{\sqrt f} = -1.8\log_{10}\!\left[\left(\frac{\varepsilon/D_h}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]
\quad(Re>4000),
\qquad f=\frac{64}{Re}\ (Re<2300)
$$
con mezcla lineal en la transición $2300<Re<4000$.

### 2.1 Colector (canal rectangular) — Darcy-Weisbach
$$
\Delta P_{col} = f\,\frac{L}{D_h}\,\frac{\rho v^2}{2},\qquad D_h=\frac{2We}{W+e}
$$
Serie: $\Delta P_{rama}=\Delta P_{unidad}\times n_{serie}$; paralelo:
$\Delta P_{banco}=\Delta P_{rama}$.

### 2.2 Cámara — según orientación del flujo
- **HORIZONTAL (cross-flow):** los $n_{bandejas}-1$ canales entre bandejas están
  **en paralelo** → la $\Delta P$ del sistema es la de **un** canal.
  $\Delta P_{cam}=\Delta P_{producto}+\Delta P_{malla}$, con $\Delta P_{producto}$
  = fricción rugosa (Colebrook, $\varepsilon_{eff}=\max(\varepsilon_{chapa},d_p)$)
  + obstrucción por bloqueo $C_{obs}(\beta)$, $\beta=e_{capa}/separacion$.
- **VERTICAL_ASCENDENTE (through-bed):** por bandeja
  $\Delta P=\Delta P_{malla}+\Delta P_{lecho}$ con **Ergun**:
  $$
  \frac{\Delta P}{L}=\frac{150\,\mu v_0(1-\varepsilon)^2}{(\Phi_s d_p)^2\varepsilon^3}+\frac{1.75\,\rho v_0^2(1-\varepsilon)}{(\Phi_s d_p)\varepsilon^3}
  $$
  La $\Delta P$ de malla usa coeficientes K tipo Idelchik/Crane según el tipo de
  malla.

### 2.3 Ductos y singulares
$\Delta P_{ductos}$ por Darcy-Weisbach (rugosidad de galvanizado
$\varepsilon\approx0.15$ mm, ASHRAE Tabla 1) y singulares $\Delta P=K\,\rho v^2/2$
(codos, expansiones, entradas/salidas).

### 2.4 Caño maestro (solo gran escala)
En `GRAN_ESCALA` se **suma** la $\Delta P$ del caño maestro (flujo acumulado,
sección variable — ver doc 04).

> **Propiedades del aire:** $\rho(T,P)=P/(R_{aire}T)$ (gas ideal,
> $R_{aire}=287.058$); $\mu(T)$ por Sutherland (1893); $P_{atm}(h)$ por ISA.

---

## 3. Convección forzada — dimensionamiento del motor

Con la $\Delta P$ total y el caudal volumétrico $Q$, las potencias se calculan en
cascada (`core/motor.py::__post_init__`):

$$
P_{hid}=Q\,\Delta P
\;\xrightarrow{/\eta_{vent}}\;
P_{eje}=\frac{P_{hid}}{\eta_{vent}}
\;\xrightarrow{/\eta_{motor}}\;
P_{elec}=\frac{P_{eje}}{\eta_{motor}}
\;\xrightarrow{\times FS}\;
P_{inst}=P_{elec}\cdot FS
$$

con $\eta_{vent}$ rendimiento del ventilador, $\eta_{motor}$ del motor eléctrico,
$FS$ factor de servicio. La **corriente nominal** sale de
$I=P_{elec}/(V\cos\varphi)$, con $\cos\varphi=0.85$ (motor pequeño). Si el usuario
fija una velocidad de descarga, se añade la presión dinámica
$\Delta P_{din}=\rho v_{desc}^2/2$ a la $\Delta P$ total.

> **Anclaje empírico** para validar el orden de magnitud: extractor 76 W /
> 900 m³/h en un armario de ~50 kg → $P_{elec}$ esperada **50–100 W**.

---

## 4. Convección natural — caudal de equilibrio

Sin motor, el aire circula por **tiro térmico**. El caudal de equilibrio es aquel
en que la presión **motriz** iguala la **resistiva**:

$$
\boxed{\;\Delta P_{tiro} + \Delta P_{turbina,motriz} = \Delta P_{chimenea}(\dot m) + \Delta P_{resto}(\dot m)\;}
$$

### 4.1 Tiro térmico (stack effect)
$$
\Delta P_{tiro}=g\,H_{eff}\,(\rho_{amb}-\rho_{chim}),
\qquad H_{eff}=H_{chimenea}+H_{camara}
$$
Con gas ideal a P común $\rho\propto1/T$, así que $\Delta P_{tiro}>0$ cuando
$T_{chim}>T_{amb}$ (flujo ascendente) y $\Delta P_{tiro}<0$ cuando $T_{chim}<T_{amb}$
(tiro nulo de noche → $\dot m=0$). $H_{eff}$ incluye la altura útil de la cámara
(desde la entrada de aire frío hasta la base de la chimenea).

### 4.2 Resolución numérica
$\Delta P_{chimenea}(\dot m)$ (fricción + singulares + resistencia del extractor) y
$\Delta P_{resto}(\dot m)$ (colector + cámara + ductos, callable monótona con
$f(0)=0$) son funciones del caudal. La raíz de la ecuación de equilibrio se
resuelve con **`scipy.optimize.brentq`** acotada a $[\dot m_{min}, \dot m_{max}]$.
Devuelve $\dot m$, $v_{chim}$ y todas las componentes de $\Delta P$.

---

## 5. Extractor eólico (turbina sombrero chino)

Accesorio opcional en el tope de la chimenea. Agrega **dos** términos:

- **Motriz** — depresión que genera la rotación de la turbina:
  $$\Delta P_{turbina}=C_p\,\rho_{amb}\,v_{viento}^2/2$$
  con $C_p\approx0.3$–$0.6$. El viento NASA POWER (medido a **10 m**) se corrige a
  la **altura del tope** $z=H_{camara}+H_{chimenea}$ por **perfil logarítmico**:
  $$v(z)=v_{10}\,\frac{\ln(z/z_0)}{\ln(10/z_0)}$$
  con $z_0$ rugosidad aerodinámica del terreno.
- **Resistivo** — la turbina obstruye el flujo:
  $\Delta P=K_t\,\rho_{chim}\,v_{ext}^2/2$, evaluado a la velocidad por el diámetro
  propio del extractor.

El término motriz entra al lado izquierdo de la ecuación de equilibrio; el
resistivo, al $\Delta P_{chimenea}$.

---

## 6. Lazo Picard — acople térmico-hidráulico

`caudal_natural_kgs` toma $T_{chim}$ **como dato**, pero físicamente $T_{chim}$
depende del caudal (a más caudal, menos $\Delta T$ en el colector → $T_{chim}$
baja → menos tiro). Este acople se cierra con **iteración de punto fijo (Picard)**
sobre el triángulo:
$$
T_{chim} \longleftrightarrow \dot m_{nat} \longleftrightarrow T_{salida,colector}
$$

- **Modo Constantes** (`balance_global.calcular_todo`): **10 iter** máx, **tol
  0.5 K**. En cada iteración se re-corre el colector estacionario mutando
  `velocidad_diseno_ms` (con `try/finally` que restaura el valor original),
  se recalcula $\dot m_{nat}$ con `_caudal_natural_loop`, y $T_{flujo}$
  realimenta $T_{chim}$.
- **Modo Transitorio** (`calcular_todo_transitorio`): Picard sobre **todo el
  horizonte** horario, **5 iter** máx, tol 0.5 K. Por iteración:
  `_caudal_natural_horizonte` calcula $\dot m(t)$ hora a hora;
  `_correr_colector_horizonte` re-corre el solver del colector cada hora con la
  velocidad efectiva $v(t)=\dot m_{nat}(t)/(\rho A_{canal} n_{par})$; el motor TD
  consume las nuevas forzantes; $T_{flujo}(t)$ realimenta $T_{chim}(t)$.

Si la chimenea tiene **extractor activo**, el balance del lazo suma además
$\Delta P_{turbina,motriz}(v_{viento}(t))$ al lado motriz y $K_t\rho v^2/2$ al
resistivo. Las horas con tiro nulo ($T_{chim}\le T_{amb}$) reciben $\dot m=0$.

---

## 7. Dimensionamiento de la chimenea solar

La chimenea se dimensiona por su **geometría** (diámetro, altura) que fija:
- El **tiro disponible** vía $H_{eff}$ (a mayor altura, mayor $\Delta P_{tiro}$).
- La **resistencia propia** $\Delta P_{chimenea}=K_{total}\,\rho v^2/2$ con
  $K_{total}=f\,H/D+K_{singular}$.

El prediseño busca la combinación diámetro/altura que entrega el caudal objetivo
con el $\Delta T$ esperado del colector. La chimenea es **top-level** desde S30
(no subcomponente del colector), lo que permite chimenea solar también en
tipología CAJA.

---

## 8. Highlights de implementación (a nivel código)

| Qué | Dónde |
|---|---|
| Potencias del motor (forzada) | `core/motor.py::__post_init__` ($P_{hid}\to P_{eje}\to P_{elec}\to P_{inst}$) |
| ΔP colector / cámara / singulares | `calculos/motor_calc.py::estimar_delta_P_colector`, `estimar_delta_P_camara`, `estimar_delta_P_singulares` |
| Factor de fricción Haaland | `motor_calc.py::_factor_friccion_haaland` |
| Tiro térmico | `calculos/chimenea_calc.py::delta_P_tiro_Pa` |
| ΔP del ducto + resistencia extractor | `chimenea_calc.py::delta_P_chimenea_Pa` |
| Extractor motriz + corrección de viento | `chimenea_calc.py::delta_P_turbina_motriz_Pa`, `_v_viento_a_altura` |
| Caudal de equilibrio (brentq) | `chimenea_calc.py::caudal_natural_kgs` |
| Lazo Picard (Constantes) | `calculos/balance_global.py::calcular_todo` + `_caudal_natural_loop` |
| Lazo Picard (Transitorio) | `balance_global.py::_caudal_natural_horizonte`, `_correr_colector_horizonte` |

**Puntos a destacar en la charla:**
1. *El sistema decide el caudal de equilibrio* en convección natural — no se
   asume; sale de igualar motriz y resistiva.
2. *Picard cierra el acople térmico-hidráulico* (T_chim ↔ ṁ ↔ T_colector), tanto
   en estado estacionario como hora a hora.
3. *El extractor eólico es un accesorio*, no un tipo de motor: agrega un término
   motriz y uno resistivo, con el viento corregido a la altura del tope.
4. *Dimensionamiento de motor trazable*: hidráulica → eje → eléctrica → instalada,
   con corriente nominal.
5. *Misma física de fricción* (Haaland/ASHRAE) en colector, cámara, ductos y caño.

---

## Referencias

- ASHRAE Handbook 2017, cap. 21 — *Duct Design* (fricción, singulares).
- Haaland (1983) / Colebrook-White — factor de fricción.
- Idelchik / Crane TP-410 — coeficientes K de singulares y mallas.
- Ergun (1952) — lecho empacado.
- Bansal / Chen et al. — chimeneas solares y stack effect.
