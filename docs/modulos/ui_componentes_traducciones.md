<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/traducciones

Ruta: `ui/componentes/traducciones.py`

## Descripción

Infraestructura de internacionalización (i18n) — capa pura, sin streamlit.

Carga diccionarios de traducción desde ``ui/idiomas/<lang>/*.yaml`` y resuelve
claves jerárquicas con fallback en cascada: idioma pedido → español → default →
la clave literal. La capa con estado (idioma activo de la sesión, selector 🌐)
vive en ``ui/componentes/idiomas.py``; este módulo es funcional y testeable sin
servidor.

Convención de claves (ver CLAUDE.md §Internacionalización): el nombre del
archivo YAML es el namespace raíz (``p1.yaml`` → claves ``p1.*``) y el
anidamiento interno se aplana con puntos (``tipologia: {label: ...}`` →
``p1.tipologia.label``). Los placeholders son siempre nombrados y se
interpolan con ``str.format`` — si la interpolación falla, se devuelve la
plantilla sin interpolar (este módulo NUNCA lanza por una clave o un formato
roto: un texto imperfecto es mejor que una UI caída).

## Clases y funciones

**Funciones:**

- `cargar_diccionario()`
- `traducir()`
- `campo_i18n()`
- `recargar()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
