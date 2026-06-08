# Integración de Obsidian con proyectos de código y Claude Code

## Contexto y objetivo

El objetivo es integrar Obsidian con los directorios de proyectos existentes (por ejemplo `/home/gduran/proyectos/secador_solar/`) **sin duplicar archivos**, de manera que Obsidian pueda visualizar y navegar todos los archivos `.md` y `.py` del proyecto, y que esa documentación estructurada sirva como contexto enriquecido para Claude Code.

Obsidian fue instalado desde KDE Discover (Flatpak) en Fedora Linux con escritorio KDE Plasma.

---

## Situación actual

- Obsidian instalado y funcionando.
- El vault fue abierto directamente apuntando a la carpeta del proyecto: `/home/gduran/proyectos/secador_solar/` (usando "Open folder as vault").
- El proyecto ya tiene archivos como `CLAUDE.md`, `README.md`, `CHANGELOG.md` y subcarpetas como `assets/`, `calculos/`, `catalogo/`, `core/`, `data/`, `docs/`, `Secasol26/`, `tests/`, `ui/`, `validacion/`, `validation_data/`.
- El graph view (`Ctrl+Shift+G`) está disponible, pero actualmente muestra pocos o ningún nodo porque los archivos `.md` existentes no se referencian entre sí con la sintaxis `[[doble corchete]]`.

---

## Problema principal

Obsidian genera nodos en el graph view **únicamente para archivos `.md`** que contienen o son referenciados mediante la sintaxis `[[nombre-de-archivo]]`. Los archivos `.py`, `.json`, `.csv`, etc. aparecen en el explorador de archivos de Obsidian pero **no generan nodos en el grafo**.

Para tener una red visual útil, los archivos `.md` del proyecto deben referenciarse entre sí.

---

## Solución a implementar por Claude Code

Claude Code debe generar los scripts y archivos necesarios para que Obsidian tenga una vista completa y navegable del proyecto, sin copiar ni mover archivos existentes.

### Tarea 1: Crear estructura de notas `.md` interconectadas

Crear o actualizar los siguientes archivos `.md` dentro del proyecto, con referencias cruzadas usando `[[doble corchete]]`:

#### Archivos a crear o actualizar

**`CLAUDE.md`** (ya existe, actualizar si es necesario)
- Instrucciones principales para Claude Code sobre el proyecto.
- Debe contener links a: `[[README]]`, `[[docs/arquitectura]]`, `[[docs/tareas]]`, `[[docs/decisiones]]`.

**`docs/arquitectura.md`** (crear si no existe)
- Descripción de la arquitectura del sistema.
- Links a: `[[README]]`, `[[CLAUDE]]`, `[[docs/decisiones]]`.
- Referencia a los módulos principales del proyecto (listar subcarpetas relevantes).

**`docs/tareas.md`** (crear si no existe)
- Backlog de tareas y estado actual del proyecto.
- Links a: `[[CLAUDE]]`, `[[docs/decisiones]]`, `[[CHANGELOG]]`.
- Formato sugerido: lista de tareas con estado (`pendiente`, `en progreso`, `completado`).

**`docs/decisiones.md`** (crear si no existe)
- Registro de decisiones de diseño (ADR — Architecture Decision Records).
- Links a: `[[docs/arquitectura]]`, `[[CLAUDE]]`.
- Cada decisión con: contexto, opciones consideradas, decisión tomada, consecuencias.

**`CHANGELOG.md`** (ya existe, actualizar si es necesario)
- Historial de cambios del proyecto.
- Link a: `[[README]]`, `[[docs/tareas]]`.

### Tarea 2: Script Python para inspección del proyecto y generación de notas

Crear un script `scripts/generar_notas_obsidian.py` que:

1. **Escanee el proyecto** y liste todos los archivos `.py` con sus rutas relativas.
2. **Para cada módulo `.py` importante** (no `__init__.py`, no archivos de test pequeños), genere una nota `.md` en `docs/modulos/` con:
   - Nombre del módulo.
   - Ruta relativa.
   - Docstring del módulo (si existe), extraído con `ast`.
   - Lista de clases y funciones definidas en el módulo.
   - Link de vuelta a `[[docs/arquitectura]]`.
3. **Actualice `docs/arquitectura.md`** agregando links `[[docs/modulos/nombre_modulo]]` a cada nota generada.

Ejemplo de nota generada para `core/modelo.py`:

```markdown
# Módulo: core/modelo

Ruta: `core/modelo.py`

## Descripción
<!-- docstring del módulo si existe -->

## Clases y funciones
- `ClasePrincipal`
- `funcion_utilitaria()`

## Ver también
- [[docs/arquitectura]]
- [[CLAUDE]]
```

### Tarea 3: Configuración de Obsidian para archivos no-markdown

Crear o verificar el archivo `.obsidian/app.json` con la configuración necesaria para que Obsidian muestre archivos `.py`, `.json`, `.csv`, etc. en el explorador (aunque no generen nodos en el grafo):

```json
{
  "useMarkdownLinks": false,
  "showUnsupportedFiles": true
}
```

> Nota: Obsidian instalado como Flatpak puede tener restricciones de acceso a directorios fuera de su sandbox. Si el vault fue abierto directamente como carpeta del proyecto (no mediante symlink), esto no debería ser un problema.

### Tarea 4: Script de mantenimiento

Crear un script `scripts/actualizar_notas_obsidian.sh` (bash) que pueda ejecutarse periódicamente para mantener las notas actualizadas cuando se agreguen nuevos módulos al proyecto:

```bash
#!/bin/bash
# Actualiza las notas de Obsidian para el proyecto
cd "$(dirname "$0")/.."
python3 scripts/generar_notas_obsidian.py
echo "Notas de Obsidian actualizadas."
```

---

## Estructura final esperada del proyecto en Obsidian

```
secador_solar/
├── CLAUDE.md                    ← instrucciones para Claude Code (con links [[]])
├── README.md                    ← descripción general (con links [[]])
├── CHANGELOG.md                 ← historial (con links [[]])
├── docs/
│   ├── arquitectura.md          ← estructura del sistema (con links [[]])
│   ├── tareas.md                ← backlog y estado (con links [[]])
│   ├── decisiones.md            ← ADRs (con links [[]])
│   └── modulos/
│       ├── core_modelo.md       ← generado por script
│       ├── ui_dashboard.md      ← generado por script
│       └── ...
├── scripts/
│   ├── generar_notas_obsidian.py
│   └── actualizar_notas_obsidian.sh
├── core/
├── ui/
├── data/
└── ...
```

---

## Graph view resultante

Una vez implementado, el graph view de Obsidian (`Ctrl+Shift+G`) mostrará:

- **Nodo central**: `CLAUDE.md` y `README.md` con muchas conexiones.
- **Nodo de documentación**: `docs/arquitectura.md` conectado a todos los módulos.
- **Nodos de módulos**: uno por cada archivo `.py` importante, conectados a arquitectura.
- **Nodos de gestión**: `docs/tareas.md`, `docs/decisiones.md`, `CHANGELOG.md`.

---

## Notas adicionales para Claude Code

- El proyecto está en `/home/gduran/proyectos/secador_solar/`.
- Usar `ast` de Python estándar para parsear los archivos `.py` (no requiere dependencias externas).
- No modificar ningún archivo `.py` existente.
- No borrar ni sobreescribir el contenido existente de `CLAUDE.md`, `README.md` o `CHANGELOG.md`; solo **agregar** al final las secciones de links faltantes si no existen.
- Los archivos nuevos en `docs/` deben crearse solo si no existen; si existen, no sobreescribir.
- El script `generar_notas_obsidian.py` debe ser idempotente (se puede correr múltiples veces sin duplicar contenido).
- Agregar `.obsidian/` al `.gitignore` si no está ya incluido, para no versionar la configuración local de Obsidian.

---

## Referencia: cómo funciona el graph view de Obsidian

- Solo archivos `.md` dentro del vault generan nodos.
- Un link `[[nombre]]` en un `.md` crea una arista (conexión) entre ese archivo y el archivo `nombre.md`.
- Los archivos `.py`, `.json`, `.csv` aparecen en el explorador de archivos de Obsidian pero no en el grafo.
- Los nodos con más conexiones aparecen más grandes y centrales en el grafo.
- Se puede filtrar el grafo por carpeta, tag o profundidad de conexión desde el panel del grafo.
