# Bitácora — Sesión 34 (2026-05-29)

**Tema:** Cambio del motor numérico de cámara por defecto: de `capa_fina` a `termodinamico`.

**Estado al cierre de la sesión:** Default del campo `Camara.modo_calculo` cambiado a `"termodinamico"`. UI de P4 y deserialización de snapshots reflejan el nuevo default. Suite de tests pasa (833 passed, 2 xfailed) tras adaptar 2 fixtures y 1 test que asumían el default histórico.

---

## 143. Motivación

Hasta la S33, el campo `Camara.modo_calculo` traía `"capa_fina"` como default "para preservar comportamiento histórico" (el motor termodinámico — balance acoplado calor-masa con `solve_ivp`, EDOs T_prod/X_prod, GAB para a_w — se incorporó después y arrancó como opción opt-in).

A esta altura del proyecto, el motor termodinámico es el camino físicamente más completo y el único soportado por la operación anual de cámara. Mantener `capa_fina` como default obligaba al usuario nuevo a cambiar explícitamente el selector cada vez. El usuario decidió invertir la convención: el default ahora es `"termodinamico"` y `"capa_fina"` queda como alternativa rápida/empírica para usuarios que la pidan explícitamente.

---

## 144. Cambios aplicados

| Archivo | Cambio |
| :--- | :--- |
| `core/camara.py` | `modo_calculo: Literal[...] = "termodinamico"` (era `"capa_fina"`). Docstring actualizada. |
| `ui/p4_camara.py` | Fallback de la UI cuando `proyecto.camara is None`: `"termodinamico"`. Fallback de deserialización de snapshots antiguos sin campo `modo_calculo`: `"termodinamico"`. |
| `CLAUDE.md` | Tabla de motores de cámara: la nota `(default)` se movió a la fila `termodinamico`, con sufijo "desde S34". |
| `CHANGELOG.md` | Entry en `[Unreleased] / Changed`. |
| `tests/test_core/test_camara.py` | `test_default_es_capa_fina` → `test_default_es_termodinamico`. |
| `tests/test_calculos/test_balance_global.py` | Fixture `proyecto_armario_completo` agrega `modo_calculo="capa_fina"` explícito (4 tests dependían del default histórico). |
| `tests/test_calculos/test_camara_dispatcher.py` | Fixture `camara_manzana_capa_fina` agrega `modo_calculo="capa_fina"` explícito (el test cubre ese camino específicamente). |

---

## 145. Verificación

```
.venv/bin/python -m pytest -q
833 passed, 2 xfailed in 24.02s
```

Mismo conteo y mismos xfailed que al cierre de S33.

---

## 146. Impacto en snapshots existentes

Snapshots `.json` exportados antes de S34 que tenían `modo_calculo: "capa_fina"` siguen restaurando explícitamente ese modo (el campo está en el JSON). Snapshots que no tenían el campo (anteriores a su introducción) ahora cargan con `"termodinamico"` por el cambio en el fallback de deserialización — el usuario que recupere un proyecto muy viejo verá inicialmente el motor termodinámico activo, y puede cambiarlo manualmente si quiere reproducir la corrida original.

---

## 147. Deploy

El push de esta sesión a `main` dispara el GitHub Action `deploy_hf.yml` (configurado en S33), que sincroniza el código al Space `gonzalojduran/Secasol26` y dispara rebuild. La app pública refleja el nuevo default sin intervención manual.

---

## 148. Pendiente para siguientes sesiones

- Heredados de S33: validación cruzada motor TD vs capa fina, poblar catálogo de productos, verificar k de manzana.
- Plan grande pendiente de implementación: **corridas paramétricas en P7** (lista curada por tipología, 3 modos, hasta 3 barridos comparables). Diseño guardado en `/home/gduran/.claude/plans/effervescent-petting-breeze.md` — esperando ok del usuario para arrancar.
