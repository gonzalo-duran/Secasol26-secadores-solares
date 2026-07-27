<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/barrido_parametrico

Ruta: `calculos/barrido_parametrico.py`

## Descripción

Motor de corridas paramétricas (barridos) para P7.

Un barrido corre N simulaciones variando un único parámetro del catálogo
(``calculos/catalogo_parametros_barrido.py``) y dejando todo lo demás constante.

Este módulo contiene, por ahora, la maquinaria de **aplicación de un valor al
proyecto** (``aplicar_parametro`` + resolución de path). El loop completo
(``correr_barrido``) y las dataclasses de configuración/resultado se agregan en
una etapa posterior.

Estrategia de aplicación:
    Para un parámetro normal se localiza el dataclass *padre* del campo (el que
    contiene el atributo final) y se lo reemplaza con ``dataclasses.replace``,
    lo que **regatilla su ``__post_init__``** y por lo tanto revalida el valor
    nuevo contra los códigos ``ValueError`` del modelo. El padre nuevo se
    reasigna a su *abuelo*. Las dataclasses del modelo son mutables, así que la
    reasignación in place funciona.

    Para un parámetro *forzante* (``HR_camara``, ``T_amb``) no se muta el
    proyecto: ``aplicar_parametro`` devuelve un override que el caller inyecta
    como argumento del modo Constantes (``calcular_todo``).

## Clases y funciones

**Clases:**

- `BarridoConfig`
- `PuntoBarrido`
- `ResultadosBarrido`

**Funciones:**

- `aplicar_parametro()`
- `correr_barrido()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
