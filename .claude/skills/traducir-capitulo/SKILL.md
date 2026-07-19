---
name: traducir-capitulo
description: Traduce o resincroniza un capítulo del manual de usuario (manual/capitulos/es/*.md) hacia EN y PT, respetando la sintaxis propia del manual, y corre los tests de integridad. Usar al crear un capítulo nuevo o tras editar el contenido ES de uno existente.
---

# Traducir / sincronizar capítulo del manual

Argumento: nombre de archivo del capítulo (ej. `05_colector.md`) o su slug del TOC.
Sin argumento: detectar con `git diff`/`git status` qué capítulos de `manual/capitulos/es/`
cambiaron y proponer cuáles sincronizar.

El **ES es la fuente de verdad** (`manual/capitulos/es/<archivo>.md`). EN y PT viven en
`manual/capitulos/en/` y `manual/capitulos/pt/` con el mismo nombre de archivo.

## Pasos

1. **Leer el capítulo ES completo** y, si existen, las versiones EN/PT actuales (para
   traducir incrementalmente lo que cambió, no regenerar todo de cero si la edición fue
   puntual).

2. **Traducir preservando la sintaxis propia del manual** (parseada por
   `ui/componentes/manual_render.py`):
   - Bloques `<!-- profundidad: Título -->` … `<!-- /profundidad -->`: traducir el
     título, mantener la sintaxis del comentario intacta.
   - `<!-- esquema: nombre | caption -->`: traducir SOLO el caption; `nombre` es un
     identificador de asset y no se toca.
   - Anclas explícitas `## Título {#ancla}`: traducir el título, **NUNCA el ancla**
     (las anclas son estables entre idiomas; los enlaces internos dependen de ellas).
   - Enlaces internos `[texto](?manual=slug#ancla)`: traducir el texto visible; slug y
     ancla quedan idénticos.
   - Ecuaciones KaTeX `$...$` / `$$...$$`: intactas (verificar `$$` balanceado).
   - Bloques de código, rutas de archivo, nombres de variables/campos: intactos.

3. **Terminología técnica consistente** con los capítulos ya traducidos: revisar cómo se
   tradujeron términos clave en capítulos EN/PT existentes (ej. colector → collector /
   coletor; cámara de secado → drying chamber / câmara de secagem; chimenea solar →
   solar chimney / chaminé solar) y reusar ese vocabulario.

4. **Sincronizar el TOC**: si el título del capítulo cambió, actualizar
   `manual.toc.<slug>.titulo` / `.descripcion` en `ui/idiomas/en/manual.yaml` y
   `ui/idiomas/pt/manual.yaml` (el ES canónico vive en la tupla `CAPITULOS` de
   `ui/componentes/manual_contenido.py`).

5. **Capítulo nuevo** (además de traducir): declararlo en la tupla `CAPITULOS`, enlazarlo
   desde algún otro capítulo (los tests exigen que ninguno quede aislado) y agregar las
   claves `manual.toc.*` en los tres idiomas.

6. **Verificar**:
   ```bash
   .venv/bin/python -m pytest tests/test_ui/test_manual.py tests/test_ui/test_idiomas.py -q
   ```
   Reportar el resultado; si algo falla, corregir antes de dar por cerrado.

## Reglas

- No traducir los generadores de snapshot `.txt`/`.json` ni contenido fuera del manual.
- Mantener punto decimal y formatos numéricos en los 3 idiomas (regla v1 del plan i18n).
- Todo queda en el working tree; no commitear salvo pedido explícito.
