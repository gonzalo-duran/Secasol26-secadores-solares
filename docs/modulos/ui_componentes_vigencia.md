<!-- generado automáticamente por scripts/generar_notas_obsidian.py -->

# Módulo: ui/componentes/vigencia

Ruta: `ui/componentes/vigencia.py`

## Descripción

Vigencia de los resultados que se calculan en un lado y se muestran en otro.

Varios resultados de Secasol viven en ``session_state`` entre pestañas y **nadie
los recalcula al mostrarlos**:

===============  ==========================  ==============================
resultado        lo calcula                  lo consume
===============  ==========================  ==============================
``anual``        P4 ("Calcular año")         P7 + reporte PDF
``horizonte``    P4 (forzantes del aire)     P7 (rama transitoria)
``transitorio``  P7 ("Calcular")             dashboard + exports TXT/JSON/PDF
``constantes``   P7 ("Calcular")             dashboard + exports TXT/JSON/PDF
===============  ==========================  ==============================

Sin detección de desactualización, cambiar la configuración después de calcular
deja números viejos en pantalla sin ninguna señal. En un reporte real del
usuario (S58) los dos bloques del **mismo PDF** se contradecían:
``resultados_globales`` decía ``E_aux = 74.34 MJ`` y ``operacion_anual``,
``0.0 MJ`` — el año se había corrido antes de configurar P5. El cálculo estaba
bien; lo que faltaba era detectar que había quedado viejo.

Este módulo es el **único** lugar que conoce la convención: por cada resultado,
la clave de ``session_state`` donde vive el valor, la clave hermana donde vive
su huella (``<clave>_hash``) y qué secciones del proyecto lo determinan. P4, P7
y el reporte no la replican. La huella en sí la calcula ``core.huellas``, que es
puro.

**Elección deliberada:** detectar y avisar, no recalcular solo. P7 es una vista;
que dispare varios segundos de cómputo por entrar a la pestaña sería peor que el
problema que resuelve.

## Clases y funciones

**Clases:**

- `Derivado`

**Funciones:**

- `extras_horizonte()`
- `huella()`
- `registrar()`
- `estado()`
- `invalidar()`
- `registrar_anual()`
- `resultado_anual_vigente()`
- `horizonte_vigente()`

## Ver también

- [[docs/arquitectura]]
- [[CLAUDE]]
