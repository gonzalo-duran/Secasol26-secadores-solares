# Flujo de trabajo — tres niveles

**Desde S65 (2026-08-02), ampliado en S67 (2026-11-12).** Las decisiones están registradas
como ADR-008 (dos ramas) y ADR-010 (tres niveles) en [[docs/decisiones]]; acá está el detalle
operativo. Las reglas mínimas que Claude necesita en
cada sesión están en [[CLAUDE]] §Convenciones de trabajo.

---

## 1. Por qué

**`git push` a `main` despliega a producción.** El workflow `.github/workflows/deploy_hf.yml`
escucha solo esa rama y sincroniza el código al Space de Hugging Face, que es por donde los
compañeros usan la app. No hay paso intermedio ni aprobación: el push *es* el deploy.

Hasta S64 se trabajaba directamente sobre `main` local, con el working tree como única zona de
trabajo y sin commitear hasta que algo estuviera listo. Eso arrastraba dos problemas:

1. **Un proyecto grande pasa varias sesiones "con las tripas abiertas".** Cuando se corrige un
   problema de fondo —un modelo físico mal planteado, por ejemplo— el código queda a mitad de
   camino durante días. Commitear eso a `main` y pushear pondría en producción algo que no
   funciona, y **deshacer un deploy roto en HF es peor que esperar**.
2. **No commitear tampoco es gratis.** S63 y S64 acumularon 61 archivos sin un solo punto de
   retorno. Un `git restore` mal tipeado y se perdían dos sesiones enteras.

Las dos ramas resuelven la contradicción: se commitea seguido, pero en un lugar que no puede
llegar a producción.

También pesó la experiencia del **salto de S59 a S61**: volver atrás fue trabajoso porque no
había tags. Las versiones liberadas 1.0.0 a 1.4.0 existían como commits, pero había que ir a
buscarlas al log a mano.

---

## 2. La estructura

| nivel | qué es |
|---|---|
| **`testing`** | **Todo el trabajo.** Commits locales, tan frecuentes como haga falta. Romperla es gratis: `main` sigue intacto y los tags están a un `git switch` de distancia. |
| **`main` local** | **Lo acordado.** Lo que el usuario y Claude ya revisaron y dieron por bueno. **Nunca se le commitea directo.** Solo avanza por `merge --ff-only` desde `testing`, cuando el usuario lo pide. **No es un deploy.** |
| **remoto** (`origin/main`: GitHub + Space de HF) | **La versión estable.** Solo recibe un push después de analizar bien lo que hay en `main` local, con bump de versión. |

El cambio conceptual de S65: **`main` deja de ser donde se trabaja y pasa a ser una
afirmación**. Desde S67 esa afirmación es *"esto está acordado"*, no *"esto está en
producción"*: `main` local **puede ir por delante de `origin/main`** el tiempo que haga falta.

**Consecuencia a tener presente:** ya no vale que "un push accidental no puede hacer nada".
Lo que protege producción es que **llevar algo a `main` local y pushear son dos actos
separados** — y el push lo hace solo el usuario.

**Tags como puntos de retorno** (locales): `v0.7.0`, `v1.0.0`, `v1.1.0`, `v1.2.0`, `v1.3.0`,
`v1.4.0`. `git diff v1.4.0..testing` dice exactamente qué entró desde la última versión
liberada.

---

## 3. El ciclo de trabajo

```bash
git branch                 # verificar que estamos en testing ANTES de editar
git switch testing         # si no
```

Durante la sesión, commits en `testing` al cierre de cada etapa. Los mensajes se redactan en
`.commit_msgs/` (carpeta **gitignoreada**, dentro del repo para que sea clicable desde VSCode)
y se commitea con `git commit -F`:

```bash
git add -A
git commit -F .commit_msgs/msgN_lo_que_sea.txt
```

**Los mensajes de commit no llevan trailer de coautoría** — ni `Co-Authored-By`, ni menciones a
Claude o Anthropic, ni `noreply@anthropic.com`.

Opcionalmente, un tag local en cada hito que se probó en la app:

```bash
git tag s65-validado
```

---

## 4. De `testing` a `main` local, y de ahí a producción

### 4.1 Llevar lo acordado a `main` local

Cuando una etapa quedó revisada y el usuario la da por buena:

```bash
git switch main
git merge --ff-only testing      # main local = lo acordado hasta acá
git switch testing
```

**Sin `git push`.** No hace falta bump de versión ni entrada cerrada en el `CHANGELOG`: eso es
del paso siguiente.

### 4.2 Liberar a producción

Solo después de analizar bien lo que hay en `main` local, con el avance **estable y probado en
Streamlit**:

```bash
git switch main
git merge --ff-only testing      # por si testing siguió avanzando con cosas ya acordadas
git push origin main             # ← el ÚNICO comando que toca producción
git push origin --tags           # los tags no viajan solos
git switch testing
```

Si `origin/main` tiene commits que `main` local no tiene (un hotfix, §6.1), el push es
rechazado. **No se fuerza:** primero `testing` absorbe el hotfix y `main` local se adelanta de
nuevo.

**Por qué `--ff-only`:** si falla, es porque `main` divergió — o sea, porque alguien commiteó
ahí directo. Que el comando falle es la señal de que se violó la regla, no un obstáculo.

**Antes de liberar hace falta:** suite completa verde (~12 min), `ruff`, `black`,
`auditar_i18n.py`, entrada en el `CHANGELOG` y **bump de versión** — el criterio adoptado en
S62 es *si cambian los resultados, cambia la versión*, porque sin bump dos reportes rotulados
igual darían números distintos y nada permitiría distinguirlos.

---

## 5. Qué NO puede tocar producción

Conviene tenerlo presente para saber dónde se puede escribir con libertad:

| | llega al Space |
|---|---|
| un commit local (en cualquier rama) | **no** — nada sale de la máquina sin `git push` |
| `docs/` (bitácoras, planes, notas, este archivo) | **no** — fuera de la whitelist del deploy |
| `CLAUDE.md`, `CHANGELOG.md`, `README.md` | **no** — fuera de la whitelist |
| `tests/` | **no** — fuera de la whitelist |
| `.commit_msgs/` | **no** — gitignoreada, ni siquiera se versiona |
| `Secasol.py`, `ui/`, `calculos/`, `core/`, `assets/`, `catalogo/`, `manual/`, `requirements.txt` | **sí** |

La whitelist está en `deploy_hf.yml`. **Al agregar una carpeta top-level nueva que la app
necesite en runtime, hay que sumarla ahí** o la app va a fallar en el Space y no en local.

---

## 6. Vuelta atrás

- **Rompí `testing`:** `git switch main` para volver a terreno firme, o
  `git reset --hard <commit>` dentro de `testing`.
- **Quiero ver qué cambió desde la última versión liberada:** `git diff v1.4.0..testing`.
- **Llegó algo roto a producción:** `git revert` sobre el merge y push. **Nunca
  `push --force`** — dejaría el repo y el Space en estados distintos, que es exactamente el
  problema que se quiere evitar.

### 6.1 Hotfix de producción sin pasar por `testing` (desde S66, ADR-009)

Cuando producción necesita un arreglo **ya** y `testing` tiene trabajo que no se puede liberar,
el hotfix se arma sobre el **tag** de la versión en producción, en un worktree aparte para no
tocar `testing`:

```bash
git worktree add ../secador_solar_hotfix -b hotfix-X.Y.Z vX.Y.(Z-1)
# editar en ../secador_solar_hotfix, bump en core/version.py + CHANGELOG, suite completa
git -C ../secador_solar_hotfix add -A
git -C ../secador_solar_hotfix commit -F .commit_msgs/<mensaje>.txt
git tag vX.Y.Z hotfix-X.Y.Z
git push origin hotfix-X.Y.Z:main     # ← deploy (fast-forward sobre origin/main)
```

Después, `main` local se pone al día con `git switch main && git merge --ff-only
hotfix-X.Y.Z` **salvo que se decida lo contrario** (caso 1.4.1: el usuario quiso que el `main`
local conserve la funcionalidad retirada). Al próximo release, `testing` absorbe el hotfix con
`git merge hotfix-X.Y.Z` (si el arreglo vale para `testing`) o `git merge -s ours
hotfix-X.Y.Z` (si solo valía para producción), y la versión nueva tiene que ser mayor que la
del hotfix.

**Primer uso — 1.4.1 (2026-11-09):** carta psicrométrica desactivada en producción antes de
ASADES 2026. Ver ADR-009 en [[docs/decisiones]].

---

## 7. Lo que esta política NO resuelve

Vale dejarlo escrito para no confundir higiene de proceso con calidad técnica.

**El problema real de S63 no fue de git: fue de interpretación física.** Se construyó una
topología de transferencia entera —área específica de partícula, Ranz-Marshall, Ergun sobre el
lecho— apoyada en un valor del catálogo que estaba **4× mal**, sin verificar ese valor antes de
edificar encima. De ahí escaló a la pérdida de carga, al diagnóstico de NTU, a las métricas y
al motor de caudal, y hubo que revertirlo en S64.

Ninguna rama, ningún commit y ningún hook habrían evitado eso. Lo que lo evita es **verificar
los números de entrada antes de construir sobre ellos**, sobre todo cuando vienen de un
catálogo cuyo valor fue elegido para otro uso. La política de ramas hace que el error sea más
barato de deshacer; no lo hace menos probable.

---

## 8. Herramientas propuestas y todavía no adoptadas

- **`git worktree`** — tener `main` checkeado en otra carpeta (`git worktree add
  ../secador_solar_prod main`) para correr producción y `testing` en paralelo sobre el mismo
  `.json`, sin cambiar de rama ni invalidar la caché de Streamlit. Útil el día que valga la
  pena comparar; hoy las dos versiones dan números tan distintos que la comparación no
  aportaría.
- **Hook `pre-push`** que corra la suite completa cuando el push es a `main` y aborte si falla.
  Son 12 minutos, pero solo se ejecuta al liberar, que es raro. Conviene ponerlo **antes del
  primer push posterior a la 1.4.0**.

---

## 9. Estado al momento de escribir esto

**Actualización S67 (2026-11-12) — tres niveles (ADR-010):**

```
origin/main  a143fcf   ← v1.4.1 estable en GitHub y HF: 1.4.0 sin carta psicrométrica
hotfix-1.4.1 a143fcf   ← rama del hotfix (worktree ../secador_solar_hotfix)
main         0c0855c   ← lo acordado: S63 + S64 + instaladores + carta corregida (S67). Sin pushear
testing      0c0855c+  ← el trabajo en curso
```

`main` local está **por delante** de `origin/main` y **no contiene** el commit del hotfix.
Antes de liberar: `git merge -s ours hotfix-1.4.1` en `testing`, bump de versión por encima de
1.4.1 y entrada `[1.4.1]` en el `CHANGELOG`.

**Actualización S66 (2026-11-09) — hotfix 1.4.1:**

```
origin/main  <hotfix>  ← v1.4.1 en producción: 1.4.0 sin carta psicrométrica
hotfix-1.4.1 <hotfix>  ← rama del hotfix (worktree ../secador_solar_hotfix)
main         080eec7   ← v1.4.0, CON carta; un commit detrás de origin/main (ADR-009)
testing      51bf9c7+  ← S62 post-1.4.0 + S63 + S64, CON carta, sin pushear
```

Estado original (S65):

```
main     080eec7  [origin/main]   ← v1.4.0, en producción, intacto
testing  356cb98                  ← S62 post-1.4.0 + S63 + S64, sin pushear
tags     v0.7.0 v1.0.0 v1.1.0 v1.2.0 v1.3.0 v1.4.0   (locales)
```

Pendiente antes de poder liberar: bump de versión y validación en Streamlit de P4 (espesor de
capa como métrica derivada, sin selector de dirección de flujo). Ver
[[docs/bitacora/bitacora_sesion64]].

## Ver también

- [[CLAUDE]] — las reglas mínimas, en el archivo que se carga en cada sesión.
- [[docs/decisiones]] — ADR-008 (dos ramas), ADR-009 (hotfix) y ADR-010 (tres niveles).
- [[docs/tareas]] — backlog y estado.
- `docs/SETUP_GIT.md` — creación original del repo. **Desactualizado** (dice repo público y
  otro nombre); se conserva como registro histórico.
