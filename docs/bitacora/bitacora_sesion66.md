# Bitácora — Sesión 66

**Fecha:** 2026-11-09 · **Tema:** hotfix 1.4.1, carta psicrométrica desactivada en producción.

## 1. Contexto

La presentación pública de Secasol en ASADES 2026 (Salto) es el **11/11/2026**, y ahí la app
del Space se usa en vivo. El usuario vio que la **carta psicrométrica** del proceso daba
resultados muy raros, en algunos casos erróneos, y pidió que **en producción no se vea ni se
use**. El `main` local y `testing` la conservan.

`testing` no se podía liberar: S63/S64 cambian los resultados de todos los proyectos, no están
probados en Streamlit, y el trabajo presentado describe la 1.4.0.

## 2. Lo hecho

**Hotfix sobre `v1.4.0`**, rama `hotfix-1.4.1`, worktree `../secador_solar_hotfix`:

- `ui/componentes/carta_psicrometrica.py`: `CARTA_HABILITADA = False`. Con el interruptor
  apagado, `fig_carta_psicrometrica` devuelve `None`. Es el **único** punto de entrada de la
  figura, y sus cuatro consumidores ya trataban `None` como "no aplica":
  `p7_resultados._render_carta_psicrometrica` (llamada desde los modos Constantes,
  Transitorio y Ventana) y los dos bloques de figuras del PDF (`_figuras_global`,
  `_figuras_ventana`). La sección desaparece sin aviso ni hueco.
- `core/version.py` → `1.4.1`; entrada `[1.4.1]` en el `CHANGELOG` (sección *Removed*).
- Manual, capítulos 16, 21 y 36 en ES/EN/PT: aviso de "desactivada temporalmente" al
  comienzo de cada sección `{#carta}`. El resto del texto no se tocó, para que volver atrás
  sea solo borrar esa línea.
- **No se tocó** `calculos/carta_psicrometrica.py` ni sus tests: el cálculo sigue, solo no se
  muestra. Los estados del aire siguen en el export TXT/JSON, que son datos y no la figura.

**Documentación en `testing`:** ADR-009 en `docs/decisiones.md`, §6.1 y §9 en
`docs/flujo_de_trabajo.md`, nota en `CLAUDE.md`, pendiente en `docs/tareas.md`, aviso en el
`[Unreleased]` del `CHANGELOG`.

## 3. La excepción a ADR-008

Por pedido explícito del usuario, el `main` local **no** se pone al día con el hotfix: queda en
`080eec7` (1.4.0, con carta), **un commit detrás de `origin/main`**. Deja de ser espejo exacto
de producción mientras dure. Al próximo release, `testing` absorbe el hotfix con
`git merge -s ours hotfix-1.4.1` para que el `--ff-only` vuelva a funcionar, la versión nueva
va por encima de 1.4.1 y el `CHANGELOG` suma la entrada `[1.4.1]`.

## 4. Verificación

- Tests afectados (versión, manual, idiomas, carta, reporte, P7): 255 passed + 1 skip.
- Suite completa del hotfix: **1847 passed + 4 skips**, 0 fallas (7 min 21 s). Son 1851 tests, igual que en 1.4.0 (1850 + 1); los 3 skips de más dependen del entorno, no del cambio.
- Ruff y black limpios en los archivos tocados.
- Smoke: con el interruptor apagado `fig_carta_psicrometrica(...)` devuelve `None`.

## 5. Lo que queda abierto

1. **Diagnosticar la carta** (en `testing`, donde sigue visible). Antecedente: la etapa 0 de
   S63 corrigió que la carta comparaba dos instantes distintos; **ese arreglo no está en
   1.4.0**, así que parte de lo que vio el usuario en producción puede estar ya resuelto en
   `testing`. Hay que reproducir su caso en las dos ramas antes de concluir.
2. **Verificar el Space** después del push: `curl
   https://huggingface.co/api/spaces/gonzalojduran/Secasol26` (`runtime.stage = RUNNING`), el
   sidebar "🔧 Entorno" debe decir 1.4.1, y P7 no debe mostrar la carta.
3. Reconciliación de ramas al próximo release (§3).

## 6. Instaladores locales (pedido para abrir el repo al público)

`instalar_secasol.sh` / `.bat` + `iniciar_secasol.sh` / `.bat` en la raíz, en **las dos ramas**
(hotfix y testing: `requirements*.txt`, `README.md` y `setup_secador_solar.sh` eran idénticos
entre ambas, así que los archivos son los mismos). Decisiones:

- **Entorno en `.venv` del proyecto con `requirements.txt` pinneado** = el stack de producción.
  Python preferido 3.13 (el del Space); acepta ≥ 3.11 con aviso, porque el pin fija las
  librerías pero no el intérprete (gotcha de S46). Las dependencias **transitivas** no están
  pinneadas, igual que en el Space.
- **`.venv` sin pip o roto se rehace solo**: es exactamente lo que dejó `uv` hoy.
- **`--server.showEmailPrompt false`** en el arranque: sin eso, la primera vez Streamlit se
  queda esperando un email en la consola y un usuario nuevo ve una ventana colgada.
- Los `.bat` son **ASCII puro y CRLF** (`.gitattributes`): cmd no muestra UTF-8 por defecto y
  con LF puede leer mal las etiquetas `goto`.
- `setup_secador_solar.sh` queda para el **entorno de desarrollo** y delega en `--dev`.

**Verificado:** instalador Linux en un clon limpio (54 s, Python 3.12 con aviso, "Secasol
1.4.1 listo"); arranque con `HOME` vacío sin prompt (health 200 a los 2 s); `--dev` y opción
inválida; suite completa sobre ese `.venv` recién instalado (ver abajo). `.bat` bajo `wine`:
argumentos y los cuatro caminos de error correctos. **No verificado: el `.bat` con un Python
de Windows real** —el instalador MSI no se completa bajo wine—; **probarlo en una PC con
Windows antes de anunciar el repo.**

## Incidente menor

El `.venv` apareció vacío (Python 3.12, sin paquetes): lo había recreado `uv` desde el proyecto
de la conferencia. Se reconstruyó con Python 3.14 + `requirements-dev.txt`. No es un problema
del repo.

## Ver también

- [[docs/decisiones]] — ADR-009.
- [[docs/flujo_de_trabajo]] — §6.1, procedimiento de hotfix.
- [[docs/bitacora/bitacora_sesion64]] — sesión anterior con cambios de código.
- [[docs/tareas]] — backlog.
