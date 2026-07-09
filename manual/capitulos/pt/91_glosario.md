# Glossário

Termos e símbolos usados na interface e neste manual, em ordem alfabética. As unidades são
as internas (SI) salvo indicação.

## Termos {#terminos}

**Absorvedor** — a placa que capta a radiação no coletor e a transfere ao ar. Sua
absortância $\alpha$ define quanta radiação converte em calor.

**Albedo ($\rho_g$)** — fração da radiação que o solo reflete [0–1]. Entra na componente
refletida da [POA](?manual=radiacion#transposicion).

**Atividade de água ($a_w$)** — umidade relativa de equilíbrio do ar em contato com o
produto [0–1]. Mede quão "disponível" está a água do produto. Ver
[Física da secagem](?manual=secado#actividad).

**Base seca / base úmida** — duas formas de expressar a umidade do produto: por kg de
matéria seca ($X$) ou por kg totais ($w$). O Secasol usa base seca. Ver
[Física da secagem](?manual=secado#base-seca).

**Batch** — leva ou lote de secagem: carrega-se, seca-se completa, descarrega-se.

**Carta psicrométrica** — ver Psicrometria.

**COP de secagem** — energia de evaporação obtida por unidade de energia investida (solar
útil + auxiliar + motor).

**CSTR** — *continuous stirred-tank reactor*: modelo de mistura perfeita usado para o ar da
câmara (sem gradientes internos).

**Cobertura** — o envidraçamento do coletor ou das faces translúcidas da câmara
(policarbonato, vidro, filme). Transmite radiação ($\tau$) e freia as perdas convectivas.

**DHI / DNI / GHI** — as três componentes da radiação reportadas pelas bases de dados:
difusa horizontal, direta normal e global horizontal. Ver
[Radiação solar](?manual=radiacion#componentes).

**Dia típico mensal** — dia de 24 h construído pela média hora a hora de todos os dias de um
mês. Base do modo de análise Anual.

**Duto mestre** — o coletor (manifold) que recolhe o ar dos ramais do banco de coletores em
grande escala. Ver [Técnico · Industrial](?manual=tec-industrial#cano-maestro).

**Fração solar** — parte do calor total aportada pelo sol:
$E_{solar}/(E_{solar}+E_{auxiliar})$.

**GAB** — modelo de isoterma de sorção (Guggenheim–Anderson–de Boer) com parâmetros
$X_m, C, K$ por produto. Ver [Física da secagem](?manual=secado#isotermas).

**Isoterma de sorção** — relação de equilíbrio $X \leftrightarrow a_w$ a temperatura dada.

**Laço Picard** — iteração de ponto fixo que fecha o acoplamento entre a temperatura da
chaminé, a vazão natural e a saída do coletor. Ver
[Técnico · Motor e chaminé](?manual=tec-chimenea#picard).

**POA** — *plane of array*: irradiância sobre o plano inclinado e orientado do coletor,
obtida por transposição de GHI/DNI/DHI. É a radiação que todos os cálculos de coletor usam.

**Psicrometria** — termodinâmica do ar úmido. Ver [Psicrometria](?manual=psicrometria).

**Semicontínuo** — subtipo de grande escala: túnel em contracorrente onde o produto avança
por zonas enquanto o ar circula em sentido oposto.

**Set-point** — temperatura objetivo do auxiliar; o controle entrega apenas a potência
necessária para alcançá-la.

**Tiragem térmica** — depressão que uma coluna de ar quente (menos denso) gera e que move o
ar em convecção natural.

**Warm-start** — arrancar um solver a partir da solução do ponto anterior (acelera e
robustece a convergência nó a nó do coletor).

**Janela (de produção)** — lapso real [início, fim] sobre o qual se roda a análise multidia
com clima horário.

## Símbolos frequentes {#simbolos}

| Símbolo | Magnitude | Unidade SI |
|---|---|---|
| $\beta$ | inclinação do coletor | ° |
| $\gamma$ | azimute (convenção Duffie) | ° |
| $\theta_z$, $\theta_i$ | ângulo zenital solar / de incidência | ° |
| $I_g$, $I_{POA}$ | irradiância global / no plano do coletor | W/m² |
| $\tau$, $\alpha$, $\varepsilon$ | transmitância, absortância, emissividade | – |
| $T_f$, $T_{abs}$, $T_{prod}$, $T_{flujo}$ | temperaturas (fluido, absorvedor, produto, ar de câmara) | K |
| $\dot m$, $\dot m_{as}$ | vazão mássica (ar, ar seco) | kg/s |
| $\dot m_w$ | taxa de evaporação | kg/s |
| $\omega$ | umidade absoluta do ar | kg água/kg ar seco |
| $X$ | umidade do produto (base seca) | kg água/kg seco |
| $a_w$ | atividade de água | – |
| $h_{conv}$, $h_w$, $h_{int}$ | coef. de convecção (produto, vento, canal) | W/(m²·K) |
| $K_m$ | coef. de transferência de massa | kg/(m²·s) |
| $U$ | condutância global | W/(m²·K) |
| $\Delta P$ | perda de carga | Pa |
| $Re$, $Nu$, $Pr$, $Ra$, $Le$, $Sh$ | números adimensionais (Reynolds, Nusselt, Prandtl, Rayleigh, Lewis, Sherwood) | – |
| $D_h$ | diâmetro hidráulico | m |
| $L_v$, $h_v$ | calor latente / entalpia do vapor | J/kg |
| $c_p$, $c_{p,h}$ | calor específico (ar, ar úmido) | J/(kg·K) |
| $\rho$, $\mu$, $k$ | densidade, viscosidade, condutividade | SI |
| $\varepsilon$ (leito) | porosidade | – |
| $d_p$, $\Phi_s$ | diâmetro de partícula, esfericidade | m, – |

---

**Ver também:** [Convenções de unidades e ângulos](?manual=convenciones).
