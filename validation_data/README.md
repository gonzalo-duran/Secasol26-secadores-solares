# Datos de validación experimental

Este directorio contiene mediciones experimentales de secadores solares reales,
usadas para validar los modelos numéricos implementados en `calculos/`.

## Formato esperado

Cada dataset se organiza en un subdirectorio con:

```
validation_data/
└── nombre_secador_año/
    ├── README.md          ← descripción del secador, condiciones, fuente
    ├── datos.csv          ← series temporales medidas
    └── metadata.yaml      ← parámetros geométricos y del producto
```

## Columnas mínimas esperadas en datos.csv

| Columna | Unidad | Descripción |
|---|---|---|
| `timestamp` | ISO 8601 | Marca temporal (tz-aware) |
| `T_amb_C` | °C | Temperatura ambiente |
| `GHI_W_m2` | W/m² | Irradiancia global horizontal |
| `T_salida_colector_C` | °C | Temperatura de salida del colector |
| `HR_camara_pct` | % | Humedad relativa en cámara |
| `masa_producto_kg` | kg | Masa del producto (evolución temporal) |

Las columnas adicionales dependen del secador instrumentado.

## Datasets disponibles

*(Agregar aquí los datasets al irlos incorporando)*
