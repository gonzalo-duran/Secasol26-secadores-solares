# Bitácora — Sesión 69

**Fecha:** 2026-11-19 · **Tema:** modelo de evaporación del producto. Lectura y cruce del corpus
de papers del grupo; diagnóstico y plan. **Nada implementado.**

## 1. Punto de partida

El usuario abre una línea de trabajo de varias sesiones sobre el **modelo de evaporación de agua
en el producto**. Aporta `docs/Papers de secadores p_ calibrar secasol/`: 16 PDF (14 trabajos)
del grupo INENCO —modelado puro, mediciones puras y modelo con validación, de escala doméstica,
invernadero y gran escala— más dos externos (Simate 2003, Hachemi 1998).

## 2. Lo que pasó

1. Lectura completa del corpus y cruce por tipo × tecnología →
   [[docs/notas/analisis_corpus_evaporacion]]. El hueco: la gran escala indirecta (ADITAL /
   San Carlos) tiene tres campañas medidas y ningún modelo validado.
2. Diagnóstico: Secasol tiene la misma ecuación de Dalton que el linaje INENCO, pero la caída de
   la velocidad vive solo en `a_w(X)` (GAB); el grupo la ponía en un coeficiente global `Hpd(X)`
   que cae 1–3 órdenes de magnitud. Falta la resistencia interna.
3. Hallazgos en el catálogo: el pimiento tiene GAB con `K = 1.02` (el inversor lo rechaza →
   `a_w` en escalón); 16 de 20 productos no tienen GAB y usan la rampa `a_w = X/X₀`. Hay tres
   modelos según el producto.
4. Plan escrito: [[docs/notas/plan_modelo_evaporacion]] (Fases 0–3, recomendación de
   resistencias en serie, cinco decisiones abiertas en el §9). Entrada en [[docs/tareas]].

## 3. Higiene del corpus (para no tropezar después)

- Los dos `Documento_completo.pdf-PDFA` son el mismo archivo. T302 ≈ ASADES 2012.
- Coordenadas de San Carlos inconsistentes entre papers (22°53′ S vs 25°54′ S; la buena es la
  segunda). Revisar qué usa la validación de ADITAL.
- Unidades dudosas: `Hpd` de Condorí 1998, `Ahd`/`Ahc` de Durán 2009 (exponentes perdidos en la
  extracción), "0.73 m³/h" de Condorí 2010.

## 4. Estado al cierre

- `testing` = `main` local = `ca68ceb`. Nuevos sin versionar: la carpeta de papers, la nota de
  análisis, el plan y esta bitácora; `docs/tareas.md` modificado. Nada commiteado ni pusheado.
- Sin tocar: el stash de presets (S68), `docs/asades2026/`, `uv.lock`.
- **Al retomar:** leer el plan §9 y decidir el camino; luego la Fase 0.
