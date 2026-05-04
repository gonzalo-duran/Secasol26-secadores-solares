# SHOPPING LIST BIBLIOGRÁFICA — Tanda 3 paso 2

**Proyecto:** Software de prediseño de secadores solares.
**Tarea:** Conseguir 1–3 papers por producto con parámetros tabulados de capa fina (Lewis/Page/Henderson-Pabis/Midilli/Logarítmico) y/o isoterma (GAB/Oswin/Henderson) bajo condiciones bien documentadas.
**Generada:** Sesión 6.

---

## Cómo usar este documento

Para cada producto se listan papers en orden de prioridad (1 = más importante). Por cada paper aparece:

- **Cita corta** y **DOI** o URL.
- **Disponibilidad estimada**: Open Access (OA) / MINCyT (Elsevier, Wiley, Springer, Tandfonline → debería abrir vía CONICET) / SciHub-territory (último recurso) / SEDICI/RIDAA/repositorio local (OA argentino) / Closed Access.
- **Qué se espera extraer**: capa_fina (modelos), isoterma (modelos), propiedades_básicas, condiciones de calibración.
- **Calidad esperada** que asignaríamos al set en YAML (ALTA/MEDIA/BAJA).
- **Notas** específicas (variedad, pretratamiento, rangos de T y v).

Al bajar cada paper, subilo al Project knowledge con un nombre claro tipo `producto_AutorAño.pdf`. Yo después extraigo los números directo del PDF en Project.

**Total estimado:** 35–40 papers, ~70% accesibles vía MINCyT.

---

## frutas.yaml

### 1. manzana (Malus domestica)

**Estado de la literatura:** muy abundante, modelos bien calibrados. Default propuesto: Sacilik 2006 (organic apple) + Meisami-Asl 2009/2010 (Golab variety). Default de isoterma: ver Veltchev 2014 o Tsami 1990.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Sacilik K, Elicin AK (2006). The thin layer drying characteristics of organic apple slices. *J Food Eng* 73(3):281-289. | 10.1016/j.jfoodeng.2005.01.024 | MINCyT (Elsevier) | Lewis, Page, Henderson-Pabis, Midilli params @ 40-60°C, v=0.6 m/s, 5 mm. ALTA. |
| 2 | Meisami-Asl E, Rafiee S, Keyhani A, Tabatabaeefar A (2009). Mathematical modeling of moisture content of apple slices (var. Golab) during drying. *Pakistan Journal of Nutrition* 8(6):804-809. | 10.3923/pjn.2009.804.809 | OA (scialert, intermitente) | Midilli params @ 40-80°C, v=0.5 m/s, 2/4/6 mm. ALTA. |
| 3 | Zarein M, Samadi SH, Ghobadian B (2013). Kinetic drying and mathematical modeling of apple slices on dehydration process. *J Food Process Technol* 4:247. | 10.4172/2157-7110.1000247 | OA (CC-BY) | Midilli params @ 50-95°C, v=1 m/s, 3/5/7 mm. MEDIA (revista de bajo factor). Útil para extender rango T. |

**Isoterma:** Tsami E, Marinos-Kouris D, Maroulis ZB (1990). Water sorption isotherms of raisins, currants, figs, prunes and apricots. *J Food Sci* 55(6):1594-1597. **OA (Wiley)**. GAB params apple. ALTA. → Si no encontramos isoterma directa de manzana fresca, usar este.

**Notas para el catálogo:**
- *Default* en YAML: Sacilik 2006 (Page + Midilli + Henderson-Pabis), variedad Granny Smith orgánica, T=40-60°C, v=0.6 m/s.
- *Alternativa* en `notas`: Meisami-Asl Golab para rango ampliado.

---

### 2. durazno (Prunus persica)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Kingsly ARP, Singh DB (2007). Drying kinetics of pomegranate arils. *J Food Eng* 79:741-744. | (no es durazno, pero útil de referencia) | MINCyT | — |
| 1 | **Vega-Galvez A, Andrés A, Gonzalez E, Notte-Cuello E, Chacana M, Lemus-Mondaca R (2009). Mathematical modelling on the drying process of yellow squash (Cucurbita pepo) and water sorption isotherms.** | búsqueda pendiente | — | — |
| 1 | Kingsly ARP, Goyal RK, Manikantan MR, Ilyas SM (2007). Effects of pretreatments and drying air temperature on drying behaviour of peach slice. *Int J Food Sci Tech* 42(1):65-69. | 10.1111/j.1365-2621.2006.01210.x | MINCyT (Wiley) | Page params @ 55-65°C, pretratamientos. ALTA. |
| 2 | Goyal RK, Kingsly ARP, Manikantan MR, Ilyas SM (2006). Mathematical modelling of thin layer drying kinetics of plum in a tunnel dryer. *J Food Eng* 79(1):176-180. | 10.1016/j.jfoodeng.2006.01.041 | MINCyT (Elsevier) | (Análoga, ciruela). MEDIA-ANALOGÍA si no encontramos durazno directo. |
| 3 | Doymaz I (2011). Drying of thyme; mismo autor publicó sobre durazno. Buscar: Doymaz I, "drying behaviour of dipped peach". *J Food Eng* 76:561-566 (2006). | 10.1016/j.jfoodeng.2005.05.052 | MINCyT (Elsevier) | Logarítmico, Midilli params, peach pretratada con KOH. ALTA. |

**Isoterma:** Kaymak-Ertekin F, Gedik A (2004). Sorption isotherms and isosteric heat of sorption for grapes, apricots, apples and potatoes. *LWT* 37(4):429-438. **MINCyT (Elsevier)**. GAB y Oswin params para apricot (análogo más cercano a durazno entre los del paper).

---

### 3. yacón (Smallanthus sonchifolius)

**Aviso:** No encontré papers de Durán/Condorí en INENCO con cinética calibrada de yacón. Si tenés trabajos posteriores tuyos no indexados (ASADES, ERMA), ¡pasalos! Eso eleva la calidad del set.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Shi Q, Zheng Y, Zhao Y (2013). Mathematical modeling on thin-layer heat pump drying of yacon (Smallanthus sonchifolius) slices. *Energy Convers Manag* 71:208-216. | 10.1016/j.enconman.2013.03.032 | MINCyT (Elsevier) | Midilli params @ 5-45°C, v=0.5-2 m/s. ALTA. **Es el paper canónico.** |
| 2 | Marques GS et al. (2022). Convective drying of yacón (Smallanthus sonchifolius) slices: A simple physical model including shrinkage. *J Food Eng* — [confirmar referencia] | 10.1016/j.jfoodeng.2022.0086X | MINCyT (Elsevier) | Modelo físico con encogimiento, difusividad efectiva. MEDIA-ALTA. |
| 3 | Quiroga M et al. (2007). Curvas de secado experimentales de hojas de yacón. *Avances en Energías Renovables y Medio Ambiente* (ASADES) 11(1):2.53-2.58. | (sin DOI, ASADES) | OA (web ASADES) | Datos de hojas, no raíz. INFO/ANALOGÍA. |

**Isoterma:** Reis FR et al. (2012). Sorption isotherms of yacon (Smallanthus sonchifolius). *J Food Process Eng* — buscar. **MINCyT (Wiley)**.

---

## hortalizas.yaml

### 4. pimiento_rojo (Capsicum annuum, para pimentón)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Akpinar EK, Bicer Y, Yildiz C (2003). Thin layer drying of red pepper. *J Food Eng* 59(1):99-104. | 10.1016/S0260-8774(02)00425-9 | MINCyT (Elsevier) | Lewis, Page, Henderson-Pabis, Midilli params @ 55-70°C, v=1-1.5 m/s. ALTA. |
| 2 | Vega A, Fito P, Andrés A, Lemus R (2007). Mathematical modeling of hot-air drying kinetics of red bell pepper. *J Food Eng* 79(4):1460-1466. | 10.1016/j.jfoodeng.2006.04.028 | MINCyT (Elsevier) | Page, Midilli params @ 50-80°C, v=2.5 m/s. ALTA. |
| 3 | Doymaz I, Pala M (2002). Hot-air drying characteristics of red pepper. *J Food Eng* 55(4):331-335. | 10.1016/S0260-8774(02)00110-3 | MINCyT (Elsevier) | Page params @ 55-70°C. MEDIA. |

**Isoterma:** Kaleemullah S, Kailappan R (2007). Modelling of thin-layer drying kinetics of red chillies. *J Food Eng* 76(4):531-537. **MINCyT (Elsevier)**.

---

### 5. cebolla (Allium cepa)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Sharma GP, Verma RC, Pathare PB (2005). Mathematical modeling of infrared radiation thin layer drying of onion slices. *J Food Eng* 71(3):282-286. | 10.1016/j.jfoodeng.2005.02.010 | MINCyT (Elsevier) | Page, Midilli, Logarítmico. ALTA. |
| 2 | Pathare PB, Sharma GP (2006). Effective moisture diffusivity of onion slices undergoing infrared convective drying. *J Biosystems Eng* 93(3):285-291. | 10.1016/j.biosystemseng.2005.12.010 | MINCyT (Elsevier) | Difusividad, Ea. ALTA. |
| 3 | Mitra J, Shrivastava SL, Rao PS (2012). Onion dehydration: a review. *J Food Sci Technol* 49(3):267-277. | 10.1007/s13197-011-0369-1 | MINCyT (Springer) | Revisión, valores comparados. INFO. |

**Isoterma:** Mitra J et al. (review arriba) consolida varios estudios.

---

### 6. papa (Solanum tuberosum)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Akpinar EK, Midilli A, Bicer Y (2003). Single layer drying behavior of potato slices in a convective cyclone dryer and mathematical modeling. *Energy Convers Manag* 44(10):1689-1705. | 10.1016/S0196-8904(02)00171-1 | MINCyT (Elsevier) | Lewis, Page, Henderson-Pabis, Midilli params @ 60-80°C, v=1-1.5 m/s. ALTA. **Canónico.** |
| 2 | Naderinezhad S, Etesami N, Najafabady AP, Falavarjani MG (2016). Mathematical modeling of drying of potato slices in a forced convective dryer based on important parameters. *Food Sci Nutr* 4(1):110-118. | 10.1002/fsn3.258 | OA (Wiley) | Midilli-Kucuk params @ 45-70°C, v=1.6-1.81 m/s. ALTA. |
| 3 | Hassini L, Azzouz S, Peczalski R, Belghith A (2007). Estimation of potato moisture diffusivity from convective drying kinetics with correction for shrinkage. *J Food Eng* 79(1):47-56. | 10.1016/j.jfoodeng.2006.01.025 | MINCyT (Elsevier) | Difusividad efectiva con corrección por encogimiento. ALTA. |

**Isoterma:** Kaymak-Ertekin & Gedik 2004 (citado en durazno) tiene papa también.

---

### 7. tomate (Solanum lycopersicum)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Doymaz I (2007). Air-drying characteristics of tomatoes. *J Food Eng* 78(4):1291-1297. | 10.1016/j.jfoodeng.2005.12.047 | MINCyT (Elsevier) | Page, Midilli params @ 55-70°C, v=2 m/s. ALTA. **Canónico.** |
| 2 | Garavand AT, Rafiee S, Keyhani A (2011). Mathematical modeling of thin-layer drying kinetics of tomato. *Int Trans J Eng Manag Appl Sci Technol* 2(2):147-160. | (revista de menor impacto) | OA dudoso | Midilli params @ 40-80°C, HR 20-60%, v=2 m/s. MEDIA. |
| 3 | Sacilik K, Keskin R, Elicin AK (2006). Mathematical modelling of solar tunnel drying of thin layer organic tomato. *J Food Eng* 73(3):231-238. | 10.1016/j.jfoodeng.2005.01.025 | MINCyT (Elsevier) | Logarítmico, Page bajo condiciones de secado solar real. ALTA. |

**Isoterma:** Akanbi CT, Adeyemi RS, Ojo A (2006). Drying characteristics and sorption isotherm of tomato slices. *J Food Eng* 73(2):157-163. **MINCyT (Elsevier)**.

---

### 8. zanahoria_rallada (Daucus carota)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Doymaz I (2004). Convective air drying characteristics of thin layer carrots. *J Food Eng* 61(3):359-364. | 10.1016/S0260-8774(03)00142-0 | MINCyT (Elsevier) | Page params @ 50-70°C, v=1-2 m/s. ALTA. |
| 2 | Erenturk S, Gulaboglu MS, Gultekin S (2004). The thin-layer drying characteristics of rosehip. (cita análoga - por ahora la dejo como referencia secundaria si zanahoria no alcanza) | — | — | — |
| 2 | Aghbashlo M, Kianmehr MH, Khani S, Ghasemi M (2009). Mathematical modelling of thin-layer drying of carrot. *Int Agrophys* 23:313-317. | (open archive) | OA | Newton, Page, Henderson-Pabis params. MEDIA. |
| 3 | Reyes A, Alvarez PI, Marquardt FH (2002). Drying of carrots in a fluidized bed. *Drying Technol* 20(7):1463-1483. | 10.1081/DRT-120005860 | MINCyT (Tandfonline) | Difusividad, Ea. INFO. |

**Nota especial:** Para *rallada*, la geometría es muy distinta de *rodajas*. Usar Doymaz como referencia y agregar una *advertencia explícita en notas del YAML* sobre la diferencia geométrica. La calibración del paper es para rodajas; para rallado el espesor efectivo es menor → drying más rápido. Recomiendo poner `calidad_datos: MEDIA` aunque el paper sea ALTA, justamente por la mismatch geométrica.

---

### 9. apio (Apium graveolens)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Demir V, Gunhan T, Yagcioglu AK (2007). Mathematical modelling of convection drying of green table olives. (no es apio, pero el grupo trabajó otros) — buscar específicamente: | — | — | — |
| 1 | Singh GD et al. (2008). Studies on drying kinetics, water activity and ascorbic acid retention in celery. — buscar | — | — | — |
| 1 | **Apio en literatura tiene cobertura más limitada que el resto de hortalizas. Plan B: usar apio + perejil con ANALOGIA a otras hojas / hortalizas con alta superficie específica.** | — | — | MEDIA-ANALOGIA probable. |

**Acción**: te paso este como producto donde primero hay que buscar más profundo. Si querés, en próxima sesión hago búsqueda extensa específica de apio. Mientras tanto, lo trato como `ESTIMADA_POR_ANALOGIA` con perejil/zanahoria.

---

### 10. perejil (Petroselinum crispum)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Soysal Y (2004). Microwave drying characteristics of parsley. *Biosyst Eng* 89(2):167-173. | 10.1016/j.biosystemseng.2004.07.008 | MINCyT (Elsevier) | Page, Henderson-Pabis params, microondas. MEDIA (es microondas, no aire caliente — usar como referencia). |
| 2 | Doymaz I (2006). Thin-layer drying behaviour of mint leaves. *J Food Eng* 74(3):370-375. | 10.1016/j.jfoodeng.2005.03.009 | MINCyT (Elsevier) | Page params @ 35-60°C, v=1.06 m/s. ANALOGIA hojas aromáticas. ALTA-MEDIA. |
| 3 | Soysal Y, Öztekin S, Eren Ö (2006). Microwave drying of parsley: modelling, kinetics, and energy aspects. *Biosystems Eng* 93:403-413. | 10.1016/j.biosystemseng.2006.01.017 | MINCyT (Elsevier) | Page, Midilli. Idem, microondas. |

---

### 11. mandioca (Manihot esculenta)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Dairo OU, Aderinlewo AA, Adeosun OJ, Ola IA, Salaudeen T (2015). Solar drying kinetics of cassava slices in a mixed flow dryer. *Acta Technol Agric* 18(4):102-107. | 10.1515/ata-2015-0021 | OA (de Gruyter) | Midilli params bajo secado solar. ALTA. |
| 2 | Sanni LO, Atere C, Kuye A (1997). Moisture sorption isotherms of fufu and tapioca at different temperatures. *J Food Eng* 34(2):203-212. | 10.1016/S0260-8774(97)00072-6 | MINCyT (Elsevier) | GAB params para mandioca procesada. ALTA. |
| 3 | Hernández JA, Pavón G, García MA (2000). Analytical solution of mass transfer equation considering shrinkage for modeling food-drying kinetics. *J Food Eng* 45(1):1-10. | 10.1016/S0260-8774(00)00033-9 | MINCyT (Elsevier) | Modelo difusivo con encogimiento. INFO. |

---

## hojas_aromaticas.yaml

### 12. coca (Erythroxylum coca)

**ALERTA — Decisión L:** Literatura científica internacional escasa por restricciones legales. Los papers en inglés son sobre extracción de cocaína (Casale, Plowman, Aynilian) y no sirven para cinética de secado.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | **Búsqueda recomendada:** SEDICI UNLP, repositorio UMSA (Bolivia), Cybertesis UNALM (Perú), ASADES, AVERMA. Términos: "secado hoja coca", "kinetics drying coca leaves". | — | OA repositorios LATAM | — |
| 2 | UNODC (2006/2019). World Drug Report Coca Survey — incluye humedad inicial coca fresca = 57% (bh). | reportes.unodc.org | OA | Solo humedad inicial, no cinética. |
| 3 | **Plan B (probable):** ANALOGIA con yerba mate + nota explícita en YAML sobre incertidumbre. | — | — | Marcar `calidad_datos: ESTIMADA_POR_ANALOGIA` + cita a yerba mate. |

**Recomendación operativa**: en YAML, para coca, escribir capa_fina/isoterma copiando de yerba mate (Goneli 2014 / Kanawade 2011) con nota grande:
```yaml
notas: "Datos estimados por analogía con yerba mate. Literatura específica de cinética de secado de hoja de coca es escasa (restricciones legales). Si se obtienen datos calibrados para hoja de coca de NOA o región andina, reemplazar."
```

---

### 13. te_yerba (Ilex paraguariensis para yerba; Camellia sinensis para té)

**Decisión:** la entrada `te_yerba` agrupa té y yerba mate. Defino cuál tomamos como default.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Goneli ALD et al. (2014). Mathematical modeling of yerba mate (*Ilex paraguariensis*) thin layer drying. *J Food Process Eng* — buscar referencia exacta. | búsqueda pendiente | MINCyT probable | Page, Midilli params para yerba mate. ALTA. |
| 2 | Schmalko ME, Alzamora SM (2001). Color, chlorophyll, caffeine, and water content variation during yerba maté processing. *Drying Technol* 19(3-4):599-610. | 10.1081/DRT-100103937 | MINCyT (Tandfonline) | Datos generales del proceso INTA Cerro Azul. INFO. |
| 3 | Panchariya PC, Popovic D, Sharma AL (2002). Thin-layer modelling of black tea drying process. *J Food Eng* 52(4):349-357. | 10.1016/S0260-8774(01)00126-1 | MINCyT (Elsevier) | Lewis params para black tea @ 80-120°C, v=0.25-0.6 m/s. ALTA. |

**Recomendación**: separar este producto en DOS entradas en `hojas_aromaticas.yaml`:
- `yerba_mate`: Goneli como default.
- `te_negro`: Panchariya como default.

Esto altera levemente la lista de 19 → 20 productos. **Decisión tuya** si cerramos la lista a 19 o admitimos esta partición. Si lo mantenemos como `te_yerba` única → defaulteamos a yerba mate (es el producto más relevante en NOA).

---

### 14. orégano (Origanum vulgare)

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Soysal Y, Arslan M, Keskin M (2009). Intermittent microwave-convective air drying of oregano. *Food Sci Technol Int* 15(4):397-406. | 10.1177/1082013209346588 | MINCyT (SAGE) | Page, Midilli, Henderson-Pabis. ALTA. |
| 2 | Akpinar EK (2006). Mathematical modelling of thin layer drying process under open sun of some aromatic plants. *J Food Eng* 77(4):864-870. | 10.1016/j.jfoodeng.2005.08.014 | MINCyT (Elsevier) | Incluye orégano + otras aromáticas. ALTA. |
| 3 | Lemus-Mondaca R et al. (2012). Effect of drying methods on drying kinetics, energy features and quality of oregano leaves. *Food Bioprod Process* — buscar. | — | MINCyT probable | — |

---

## legumbres_frutos.yaml

### 15. algarroba (Prosopis alba/nigra)

**Buen panorama:** hay literatura argentina específica accesible.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Prokopiuk D, Coschiza M, Martínez-Navarrete N, Andrés A, Chiralt A, Cruz G (2010). Influence of roasting on the water sorption isotherms of Argentinean algarroba (Prosopis alba Griseb) pods. *Int J Food Properties* 13(4):692-701. | 10.1080/10942910902742055 | MINCyT (Tandfonline) | GAB y BET params para algarroba cruda y tostada. ALTA. |
| 2 | Cattaneo F, Costamagna MS, Zampini IC, Sayago J, Alberto MR, Chamorro V, Pazos A, Thomas-Valdés S, Schmeda-Hirschmann G, Isla MI (2016). Flour from *Prosopis alba* cotyledons: A natural source of nutrient and bioactive phytochemicals. *Food Chem* 208:89-96. | 10.1016/j.foodchem.2016.03.115 | MINCyT (Elsevier) | Composición y humedad inicial. INFO para propiedades_básicas. |
| 3 | **Sancho A, Iriarte A et al. (UNLP/UNCa). El deshidratado de los frutos de algarroba (Prosopis alba): análisis comparativo entre secador solar y métodos tradicionales del NOA.** | http://sedici.unlp.edu.ar/handle/10915/129751 | OA SEDICI | Cinética experimental en secador solar **INENCO**. Curvas de pérdida de masa. ALTA — fuente local. |
| 4 | Cattaneo F et al. (2020). *Prosopis* spp. powder: influence of chemical components in water adsorption properties. *Int J Food Sci Tech* 56(1):278-288. | 10.1111/ijfs.14636 | MINCyT (Wiley) | Isotermas comparadas P. alba vs P. nigra. ALTA. |

---

## carnes.yaml

### 16. charqui_vacuno (carne vacuna deshidratada salada)

**Aviso especial:** considerar actividad de agua (`a_w`) para riesgo microbiológico, no solo humedad. Esto va en notas del YAML.

| # | Cita | DOI / URL | Acceso | Qué extraer |
|---|------|-----------|--------|-------------|
| 1 | Trujillo FJ, Wiangkaew C, Pham QT (2007). Drying modeling and water diffusivity in beef meat. *J Food Eng* 78(1):74-85. | 10.1016/j.jfoodeng.2005.09.008 | MINCyT (Elsevier) | Difusividad efectiva, Page params. ALTA. |
| 2 | Álvarez D, Castillo M, Garrido MD, Bañón S, Nieto G (2010). Drying kinetics of meat. (revisar referencia exacta — autores citados en review reciente) | — | MINCyT probable | Midilli params para ripening de carne. ALTA. |
| 3 | Sanjuán N, Cárcel JA, Clemente G, Mulet A (2003). Modelling of the rehydration process of brocolli florets. (NO es carne, ignorar). Buscar en su lugar: | — | — | — |
| 3 | Singh B, Kumar A, Gupta AK (2007). Study of mass transfer kinetics and effective diffusivity during osmotic dehydration of carrot cubes. (NO es carne tampoco). Para charqui buscar: | — | — | — |
| 3 | **Aykin-Dincer E, Erbas M (2018). Drying kinetics, adsorption isotherms and quality characteristics of vacuum-dried beef slices with different salt contents.** *Meat Science* 145:114-120. | 10.1016/j.meatsci.2018.06.022 | MINCyT (Elsevier) | Page, Midilli params + isotermas con sal. ALTA — específico para charqui-like. |

**Isoterma con sal:** Comaposada J, Gou P, Arnau J (2000). The effect of sodium chloride on water vapor pressure on meat surface. *J Food Eng* 43(2):119-123. **MINCyT (Elsevier)**. Contexto de actividad de agua para charqui salado.

**Notas para YAML:**
- Marcar `requiere_a_w_seguimiento: true` (o algo equivalente — ver si lo agregamos al esquema en Tanda 3 paso 3 como advertencia `PROD_A_W_FUERA_RANGO_SEGURO`).
- Agregar al notas: "Charqui salado tradicional NOA: salado previo modifica isoterma. Riesgo microbiológico requiere `a_w < 0.85` para producto estable."

---

## RESUMEN

### Cobertura esperada

| Producto | Calidad esperada del set principal | Acceso de papers críticos |
|----------|------------------------------------|---------------------------|
| manzana | ALTA | OA + MINCyT |
| durazno | ALTA-MEDIA | MINCyT |
| yacón | ALTA | MINCyT (+ALTA si tenés papers tuyos) |
| pimiento_rojo | ALTA | MINCyT |
| cebolla | ALTA | MINCyT |
| papa | ALTA | MINCyT + OA |
| tomate | ALTA | MINCyT |
| zanahoria_rallada | MEDIA (geometría) | MINCyT |
| apio | BAJA-MEDIA (literatura escasa) | A buscar |
| perejil | MEDIA (modos no convectivos) | MINCyT |
| mandioca | ALTA | OA + MINCyT |
| coca | ESTIMADA_POR_ANALOGIA | Repositorios LATAM (improbable) |
| te/yerba | ALTA (separar?) | MINCyT |
| orégano | ALTA | MINCyT |
| algarroba | ALTA — fuentes argentinas | MINCyT + SEDICI |
| charqui_vacuno | ALTA | MINCyT |

### Productos que requieren decisión tuya antes de avanzar

1. **te_yerba**: ¿Lo dejamos como entrada única (default = yerba mate) o lo separamos en `yerba_mate` + `te_negro`? Si separamos, la lista pasa a 20 productos en v1.
2. **apio**: ¿Búsqueda extendida en próxima sesión, o asumimos `ESTIMADA_POR_ANALOGIA` con perejil/zanahoria desde ya?
3. **Yacón**: ¿Tenés papers propios (INENCO) con cinética de yacón ajustada que no estén indexados en Scopus/Web of Science? Si los hay, son el default natural.

### Próximo paso

1. Vos descargás los papers de prioridad 1 de los 5 primeros productos (manzana, durazno, yacón, pimiento, cebolla) y los subís al Project knowledge.
2. Yo, en paralelo, te entrego en el próximo turno el bloque YAML de manzana versión "estructura cerrada + propiedades básicas con fuente verificable + slots de capa fina e isoterma marcados con la cita esperada". Eso te da el patrón del YAML antes de meter números.
3. A medida que vayas subiendo PDFs, voy poblando los YAML con números reales y citas.

**Ritmo realista**: con esta estrategia, sesiones siguientes cerramos 3–5 productos por sesión a calidad ALTA. 19 productos en 4–5 sesiones de trabajo.
