<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: calculos/catalogo_parametros_barrido

Ruta: `calculos/catalogo_parametros_barrido.py`

## Descripción

Catálogo de parámetros barrideables para las corridas paramétricas de P7.

Define la lista curada de parámetros que el usuario puede variar en un barrido
paramétrico, junto con su metadata: ``path`` al campo de la dataclass del
``Proyecto``, unidades, conversiones UI↔SI, rango admisible y filtros por
tipología y modo de cálculo.

Está en código Python (no YAML) a propósito:
    - Los ``path`` son referencias a campos de dataclasses; un typo se detecta
      temprano vía ``AttributeError`` al resolverlo (ver
      ``calculos/barrido_parametrico.py``), no en runtime de la UI.
    - Las conversiones (``si_a_ui``/``ui_a_si``) y ``transform_pre_set`` son
      callables que no serializan bien a YAML.

Sobre las conversiones:
    - ``si_a_ui`` / ``ui_a_si`` convierten entre la unidad que ve el usuario y
      el SI interno. Para ángulos reutilizan ``calculos/conversiones_angulo``.
      Para los dos forzantes escalares (HR, T_amb) las fórmulas son triviales y
      se declaran inline acá (este módulo es metadata declarativa, no lógica de
      cálculo; y ``calculos/`` no puede importar de ``ui/``).
    - ``transform_pre_set`` se aplica al valor SI ya resuelto, justo antes de
      asignarlo al campo (ej. ``int`` para contadores de colectores). ``None``
      cuando no hace falta.

Casos especiales — paths con prefijo ``"forzante:"`` (``HR_camara``, ``T_amb``):
    no mutan el ``Proyecto``; el barrido los inyecta como argumentos del modo
    Constantes (``calcular_todo``). Por eso solo soportan el modo ``constantes``.

## Clases y funciones

**Clases:**

- `ParametroBarrido`

**Funciones:**

- `obtener_parametro()`
- `parametros_para_tipologia()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
