"""
Pestaña 4 — Cámara de Secado.

Permite al usuario configurar la geometría, bandejas, flujo y carga de producto
de la cámara de secado solar. Calcula el tiempo de secado estimado y muestra
la curva de humedad X(t) según el modelo de capa fina seleccionado.

Sin cálculo en el motor de cámara: solo configuración, validación estática y
cálculo de tiempo de secado via calculos/camara_calc.py.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from calculos.camara_calc import calcular_camara
from calculos.camara_termodinamica import ResultadoMotorTermodinamico
from calculos.camara_calc import ResultadosCamara
from core import catalogo
from core.advertencias import Severidad
from core.camara import (
    Camara,
    CargaProducto,
    ConfiguracionBandejas,
    ConfiguracionFlujo,
    ConstruccionCamara,
    DireccionFlujo,
    GeometriaCamara,
    _modelos_disponibles,
    advertencias_camara,
)
from ui.componentes.graficas import grafica_termodinamica_camara
from ui.componentes.unidades import celsius_a_kelvin, kelvin_a_celsius

# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------

_ICONOS_SEVERIDAD = {
    Severidad.INFO: "ℹ️",
    Severidad.WARNING: "⚠️",
    Severidad.CRITICAL: "🚨",
}

_T_OP_MIN_C: float = 30.0
_T_OP_MAX_C: float = 90.0
_T_OP_DEFAULT_C: float = 55.0

_HR_DEFAULT_PCT: float = 20.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _productos_disponibles() -> dict[str, str]:
    """Retorna {prod_id: label} solo para productos con al menos un modelo calibrado."""
    result: dict[str, str] = {}
    for prod_id, datos in catalogo.PRODUCTOS.items():
        if _modelos_disponibles(datos):
            desc = datos.get("descripcion", prod_id)
            label = f"{prod_id} — {desc[:60]}..." if len(desc) > 60 else f"{prod_id} — {desc}"
            result[prod_id] = label
    return result


def _mostrar_advertencias(adv_list: list) -> None:
    """Muestra la lista de Advertencia en la UI con el icono correspondiente."""
    for adv in adv_list:
        icono = _ICONOS_SEVERIDAD.get(adv.severidad, "•")
        if adv.severidad == Severidad.CRITICAL:
            st.error(f"{icono} **{adv.codigo}** — {adv.mensaje}")
        elif adv.severidad == Severidad.WARNING:
            st.warning(f"{icono} **{adv.codigo}** — {adv.mensaje}")
        else:
            st.info(f"{icono} **{adv.codigo}** — {adv.mensaje}")


def _T_amb_representativa_K(proyecto) -> tuple[float, str]:
    """Devuelve T_amb representativa para el motor termodinámico, con su origen.

    Si hay clima cargado, usa la media anual; si no, fallback 25 °C.
    """
    clima = getattr(proyecto, "clima", None)
    if clima is not None and getattr(clima, "T_amb_K", None) is not None:
        T_arr = np.asarray(clima.T_amb_K)
        if T_arr.size > 0:
            T = float(np.nanmean(T_arr))
            return T, f"media anual NASA POWER = {T - 273.15:.1f} °C"
    return 298.15, "fallback 25 °C (sin clima cargado)"




def _grafica_curva_secado(resultados, X_0: float, X_obj: float, prod_id: str) -> plt.Figure:
    """Genera la figura de la curva de secado X(t)."""
    fig, ax = plt.subplots(figsize=(7, 4))

    t_h = resultados.t_array_s / 3600.0
    ax.plot(t_h, resultados.X_array_kg_kg, color="#1f77b4", linewidth=2, label="X(t)")

    ax.axhline(resultados.X_eq_kg_kg, color="gray", linestyle="--", linewidth=1,
               label=f"X_eq = {resultados.X_eq_kg_kg:.3f} kg/kg ms")
    ax.axhline(X_obj, color="red", linestyle=":", linewidth=1.5,
               label=f"X_obj = {X_obj:.3f} kg/kg ms")
    ax.axhline(X_0, color="green", linestyle=":", linewidth=1,
               label=f"X₀ = {X_0:.3f} kg/kg ms", alpha=0.6)

    if resultados.convergencia_ok:
        t_sec_h = resultados.t_secado_s / 3600.0
        ax.axvline(t_sec_h, color="orange", linestyle="-.", linewidth=1.5,
                   label=f"t_secado = {t_sec_h:.1f} h")

    ax.set_xlabel("Tiempo [h]")
    ax.set_ylabel("Humedad X [kg agua / kg ms]")
    ax.set_title(f"Curva de secado — {prod_id} · modelo {resultados.modelo_usado}")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Generador de texto de configuración
# ---------------------------------------------------------------------------

def _texto_config_camara(cam: "Camara") -> str:
    from datetime import date
    g = cam.geometria
    b = cam.bandejas
    f = cam.flujo
    c = cam.carga_producto
    lines = [
        "=== CONFIGURACIÓN DE LA CÁMARA DE SECADO ===",
        f"Fecha: {date.today()}",
        "",
        "GEOMETRÍA",
        f"  Largo : {g.largo_m:.2f} m",
        f"  Ancho : {g.ancho_m:.2f} m",
        f"  Alto  : {g.alto_m:.2f} m",
        "",
        "BANDEJAS",
        f"  N° bandejas    : {b.n_bandejas}",
        f"  Área c/u       : {b.area_bandeja_m2:.3f} m²",
        f"  Espesor capa   : {b.espesor_capa_m * 100:.1f} cm",
        f"  Separación     : {b.separacion_entre_bandejas_m * 100:.1f} cm",
        "",
        "PRODUCTO Y CARGA",
        f"  Producto       : {c.producto_id}",
        f"  Masa total     : {c.masa_total_kg:.1f} kg",
        f"  Modelo capa fina: {c.modelo_capa_fina}",
        f"  Modelo isoterma : {c.modelo_isoterma}",
        f"  T_prod inicial : "
        + (
            f"{c.T_prod_inicial_K - 273.15:.1f} °C (explícita)"
            if c.T_prod_inicial_K is not None
            else "T_amb (fallback)"
        ),
        "",
        "FLUJO",
        f"  Caudal másico  : {f.caudal_masico_kg_s:.4f} kg/s",
        f"  Dirección      : {f.direccion_flujo.value}",
        f"  Recirculación  : {f.fraccion_recirculacion:.0%}",
        "",
        f"MOTOR NUMÉRICO  : {cam.modo_calculo}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------


def render() -> None:
    """Renderiza la Pestaña 4 — Cámara de Secado."""
    st.header("4 · Cámara de Secado")

    proyecto = st.session_state.proyecto

    # -----------------------------------------------------------------------
    # Sección A: Producto
    # -----------------------------------------------------------------------
    st.subheader("Producto a secar")

    productos_disp = _productos_disponibles()
    if not productos_disp:
        st.error(
            "No se encontraron productos con modelos de capa fina calibrados en el catálogo. "
            "Verificar los archivos en catalogo/productos/."
        )
        return

    ids_disponibles = list(productos_disp.keys())
    labels_disponibles = list(productos_disp.values())

    # Valor previo guardado
    prod_previo = "manzana"
    if proyecto.camara is not None and proyecto.camara.carga_producto.producto_id in ids_disponibles:
        prod_previo = proyecto.camara.carga_producto.producto_id

    idx_default = ids_disponibles.index(prod_previo) if prod_previo in ids_disponibles else 0
    prod_sel_label = st.selectbox(
        "Producto",
        options=labels_disponibles,
        index=idx_default,
        help="Solo se muestran productos con al menos un modelo de capa fina calibrado.",
    )
    prod_id = ids_disponibles[labels_disponibles.index(prod_sel_label)]
    datos_prod = catalogo.PRODUCTOS[prod_id]
    props = datos_prod.get("propiedades_basicas") or {}

    modelos_disp = _modelos_disponibles(datos_prod)

    col1, col2 = st.columns(2)
    with col1:
        # Humedad inicial: default desde catálogo
        X_ini_default = float(props.get("humedad_inicial_tipica", 4.0))
        if proyecto.camara is not None and proyecto.camara.carga_producto.producto_id == prod_id:
            X_ini_default = proyecto.camara.carga_producto.humedad_inicial_X

        X_ini = st.number_input(
            "Humedad inicial X₀ [kg agua / kg ms]",
            min_value=0.01,
            max_value=50.0,
            value=X_ini_default,
            step=0.1,
            format="%.2f",
            help="Base seca. Típicamente 4–16 kg/kg ms para frutas y hortalizas frescas.",
        )

        X_obj = st.number_input(
            "Humedad objetivo X_obj [kg agua / kg ms]",
            min_value=0.01,
            max_value=X_ini - 0.01,
            value=min(
                0.15,
                X_ini - 0.01,
            ) if proyecto.camara is None else min(
                proyecto.camara.carga_producto.humedad_objetivo_X, X_ini - 0.01
            ),
            step=0.01,
            format="%.3f",
            help=(
                "Humedad final deseada en base seca. "
                "Valores típicos de almacenamiento: 0.10–0.20 kg/kg ms."
            ),
        )

        masa_kg = st.number_input(
            "Masa total a secar [kg]",
            min_value=0.1,
            max_value=10000.0,
            value=float(
                proyecto.camara.carga_producto.masa_total_kg
                if proyecto.camara is not None else 10.0
            ),
            step=0.5,
            format="%.1f",
        )

    with col2:
        modelo_cf_idx = 0
        if proyecto.camara is not None and proyecto.camara.carga_producto.modelo_capa_fina in modelos_disp:
            modelo_cf_idx = modelos_disp.index(proyecto.camara.carga_producto.modelo_capa_fina)

        modelo_cf = st.selectbox(
            "Modelo cinético de capa fina",
            options=modelos_disp,
            index=modelo_cf_idx,
            help=(
                "Solo se muestran los modelos con parámetros calibrados para el producto. "
                "El modelo logarítmico de Sacilik 2006 es el recomendado para manzana."
            ),
        )

        # Información del modelo seleccionado
        cf = datos_prod.get("capa_fina") or {}
        m_entry = cf.get(modelo_cf) or {}
        calidad_cf = (m_entry.get("calidad_datos") or "").upper() if m_entry else ""
        fuente_cf = m_entry.get("fuente", "—") if m_entry else "—"
        cond = m_entry.get("condiciones_calibracion") or {} if m_entry else {}
        T_K_cal = cond.get("T_K")
        v_cal = cond.get("v_aire_m_s")

        if calidad_cf:
            icono_cal = {"ALTA": "🟢", "MEDIA": "🟡", "BAJA": "🔴"}.get(calidad_cf, "⚪")
            st.caption(f"{icono_cal} Calidad: {calidad_cf}")
        if T_K_cal:
            T_rango = T_K_cal if isinstance(T_K_cal, list) else [T_K_cal]
            T_str = f"{min(T_rango)-273.15:.0f}–{max(T_rango)-273.15:.0f} °C"
            st.caption(f"🌡️ Rango calibración: {T_str}"
                       + (f"  |  💨 v = {v_cal} m/s" if v_cal else ""))
        if fuente_cf and fuente_cf != "—":
            with st.expander("Fuente bibliográfica"):
                st.caption(fuente_cf[:300] + "..." if len(fuente_cf) > 300 else fuente_cf)

        # Isoterma disponible?
        iso = datos_prod.get("isoterma") or {}
        iso_entry = iso.get("gab") or {}
        params_iso = iso_entry.get("params") or {} if iso_entry else {}
        tiene_gab = (
            params_iso.get("X_m") is not None
            and params_iso.get("C") is not None
            and params_iso.get("K") is not None
        )
        X_eq_fallback = props.get("humedad_equilibrio_aire_seco")
        if tiene_gab:
            st.success("✅ Isoterma GAB calibrada disponible.")
        elif X_eq_fallback is not None:
            st.warning(
                f"⚠️ Sin isoterma GAB. Se usará X_eq = {X_eq_fallback:.3f} kg/kg ms (fallback)."
            )

    # -----------------------------------------------------------------------
    # Sección B: Geometría y construcción
    # -----------------------------------------------------------------------
    with st.expander("Geometría de la cámara", expanded=True):
        c1, c2, c3 = st.columns(3)
        geo_prev = proyecto.camara.geometria if proyecto.camara is not None else GeometriaCamara()
        largo = c1.number_input("Largo [m]", min_value=0.1, max_value=20.0,
                                value=geo_prev.largo_m, step=0.05, format="%.2f")
        ancho = c2.number_input("Ancho [m]", min_value=0.1, max_value=10.0,
                                value=geo_prev.ancho_m, step=0.05, format="%.2f")
        alto = c3.number_input("Alto [m]", min_value=0.1, max_value=5.0,
                               value=geo_prev.alto_m, step=0.05, format="%.2f")
        vol = largo * ancho * alto
        st.caption(
            f"Volumen interno: {vol:.3f} m³  |  Área de planta: {largo*ancho:.3f} m²"
        )

        cons_prev = proyecto.camara.construccion if proyecto.camara is not None else ConstruccionCamara()
        cubierta_trans = st.checkbox("Cubierta translúcida", value=cons_prev.cubierta_translucida,
                                     help="Cubierta superior que permite el paso de luz solar.")
        U_muros = st.number_input(
            "Conductancia lateral U_muros [W/(m²·K)]",
            min_value=0.1, max_value=10.0, value=cons_prev.U_muros_W_m2K,
            step=0.1, format="%.2f",
            help=(
                "Conductancia térmica efectiva de los muros. "
                "Madera 10 cm: ~0.5. Chapa sin aislación: ~5. "
                "Poliestireno 5 cm + chapa: ~0.4."
            ),
        )

    # -----------------------------------------------------------------------
    # Sección C: Bandejas
    # -----------------------------------------------------------------------
    with st.expander("Configuración de bandejas", expanded=True):
        band_prev = (
            proyecto.camara.bandejas if proyecto.camara is not None else ConfiguracionBandejas()
        )
        c1, c2 = st.columns(2)
        n_bandejas = c1.number_input("Número de bandejas", min_value=1, max_value=100,
                                      value=band_prev.n_bandejas, step=1)
        area_bandeja = c2.number_input("Área por bandeja [m²]", min_value=0.01, max_value=10.0,
                                        value=band_prev.area_bandeja_m2, step=0.05, format="%.3f")
        c3, c4 = st.columns(2)
        espesor_capa = c3.number_input(
            "Espesor de capa de producto [m]",
            min_value=0.002, max_value=0.2, value=band_prev.espesor_capa_m,
            step=0.005, format="%.3f",
            help="Modelos de capa fina válidos para espesor ≤ 5 cm.",
        )
        sep_bandejas = c4.number_input(
            "Separación entre bandejas [m]",
            min_value=0.02, max_value=1.0, value=band_prev.separacion_entre_bandejas_m,
            step=0.01, format="%.3f",
            help="Distancia libre entre superficies de bandejas consecutivas.",
        )
        st.caption(
            f"Altura total ocupada por bandejas: {n_bandejas * sep_bandejas:.2f} m  |  "
            f"Área total de bandeja: {n_bandejas * area_bandeja:.2f} m²  |  "
            f"Carga estimada: {masa_kg / n_bandejas / area_bandeja:.1f} kg/m²/bandeja"
        )

    # -----------------------------------------------------------------------
    # Sección D: Flujo de aire
    # -----------------------------------------------------------------------
    with st.expander("Flujo de aire", expanded=True):
        flujo_prev = proyecto.camara.flujo if proyecto.camara is not None else ConfiguracionFlujo()

        # Sugerir caudal del colector si está disponible
        caudal_sugerido = flujo_prev.caudal_masico_kg_s
        hint_caudal = ""
        if proyecto.colector is not None:
            Q_m3s = proyecto.colector.caudal_total_m3_s()
            rho_est = 1.1
            m_col = Q_m3s * rho_est
            hint_caudal = (
                f"El colector entrega {Q_m3s*1000:.1f} L/s → "
                f"~{m_col:.3f} kg/s (a ρ≈{rho_est} kg/m³)."
            )

        c1, c2 = st.columns(2)
        caudal = c1.number_input(
            "Caudal másico [kg/s]",
            min_value=0.001, max_value=10.0, value=caudal_sugerido,
            step=0.001, format="%.4f",
            help=hint_caudal or "Caudal de aire seco que circula por la cámara.",
        )
        if hint_caudal:
            c1.caption(f"💡 {hint_caudal}")

        dir_opciones = {
            "HORIZONTAL": DireccionFlujo.HORIZONTAL,
            "VERTICAL_ASCENDENTE": DireccionFlujo.VERTICAL_ASCENDENTE,
        }
        dir_prev_str = flujo_prev.direccion_flujo.value
        dir_sel = c2.selectbox(
            "Dirección del flujo",
            options=list(dir_opciones.keys()),
            index=list(dir_opciones.keys()).index(dir_prev_str),
        )
        direccion = dir_opciones[dir_sel]

        usar_HR = st.checkbox(
            "Especificar HR de entrada",
            value=flujo_prev.HR_entrada_fraccion is not None,
            help="Si no se especifica, el cálculo usa el fallback escalar del catálogo.",
        )
        HR_entrada_frac: float | None = None
        if usar_HR:
            HR_pct = st.slider(
                "HR del aire en entrada a la cámara [%]",
                min_value=5, max_value=95,
                value=int((flujo_prev.HR_entrada_fraccion or _HR_DEFAULT_PCT / 100) * 100),
                step=1,
            )
            HR_entrada_frac = HR_pct / 100.0

        # Velocidad superficial estimada
        rho_est = 1.1
        Q_vol = caudal / rho_est
        v_sup = Q_vol / (ancho * alto) if (ancho * alto) > 0 else 0.0
        st.caption(
            f"Velocidad superficial estimada: {v_sup:.2f} m/s  |  "
            f"Q_vol ≈ {Q_vol * 1000:.1f} L/s"
        )

    # -----------------------------------------------------------------------
    # Sección E: Condiciones de operación
    # -----------------------------------------------------------------------
    with st.expander("Condiciones de operación", expanded=True):
        hint_T = (
            "Temperatura del aire en la cámara. "
            "Típicamente ≈ T_salida del colector solar."
        )
        T_op_prev_C = _T_OP_DEFAULT_C
        if proyecto.camara is not None and "T_operacion_K" in st.session_state:
            T_op_prev_C = kelvin_a_celsius(st.session_state.get("cam_T_operacion_K", celsius_a_kelvin(_T_OP_DEFAULT_C)))

        T_op_C = st.slider(
            "Temperatura de operación en cámara [°C]",
            min_value=int(_T_OP_MIN_C),
            max_value=int(_T_OP_MAX_C),
            value=int(st.session_state.get("cam_T_op_C", _T_OP_DEFAULT_C)),
            step=1,
            help=hint_T,
        )
        st.session_state["cam_T_op_C"] = T_op_C

        HR_op_pct = st.slider(
            "HR en cámara para cálculo de X_eq [%]",
            min_value=5, max_value=95,
            value=int(st.session_state.get("cam_HR_op_pct", _HR_DEFAULT_PCT)),
            step=1,
            help=(
                "Humedad relativa del aire dentro de la cámara. "
                "Determina X_eq via isoterma GAB. En la práctica sube durante el secado; "
                "para prediseño se usa un valor representativo."
            ),
        )
        st.session_state["cam_HR_op_pct"] = HR_op_pct

    # -----------------------------------------------------------------------
    # Sección F: Modo de cálculo (capa fina vs termodinámico)
    # -----------------------------------------------------------------------
    with st.expander("Modo de cálculo (motor numérico)", expanded=False):
        modo_prev = (
            proyecto.camara.modo_calculo
            if proyecto.camara is not None
            else "capa_fina"
        )
        modo_idx = ["capa_fina", "termodinamico"].index(modo_prev)
        modo_label = st.radio(
            "Motor para el cálculo del secado",
            options=["Capa fina (cinética empírica)", "Termodinámico (balance acoplado)"],
            index=modo_idx,
            help=(
                "**Capa fina:** modelos Lewis/Page/Henderson/Midilli/Logarítmico con "
                "parámetros calibrados experimentalmente para cada producto. Rápido, "
                "requiere coeficientes en el catálogo.\n\n"
                "**Termodinámico:** integración acoplada calor-masa con `solve_ivp`. "
                "Más físico, devuelve curvas dinámicas de T_producto, T_aire, q. "
                "Requiere isoterma GAB calibrada para resultados confiables."
            ),
        )
        modo_calculo = (
            "capa_fina" if modo_label.startswith("Capa fina") else "termodinamico"
        )

        T_prod_inicial_K_val: float | None = None
        if modo_calculo == "termodinamico":
            T_amb_repr_K, T_amb_origen = _T_amb_representativa_K(proyecto)
            st.caption(
                f"📍 T ambiente representativa: **{T_amb_repr_K - 273.15:.1f} °C** "
                f"({T_amb_origen}). Se usa para pérdidas a paredes y como T inicial "
                "del producto si no se define explícitamente."
            )
            usar_T_prod_explicita = st.checkbox(
                "Definir T inicial del producto explícitamente "
                "(refrigerado, precalentado, etc.)",
                value=(
                    proyecto.camara is not None
                    and proyecto.camara.carga_producto.T_prod_inicial_K is not None
                ),
            )
            if usar_T_prod_explicita:
                T_prod_default_C = (
                    kelvin_a_celsius(
                        proyecto.camara.carga_producto.T_prod_inicial_K
                    )
                    if (
                        proyecto.camara is not None
                        and proyecto.camara.carga_producto.T_prod_inicial_K is not None
                    )
                    else 25.0
                )
                T_prod_inicial_C = st.number_input(
                    "T inicial del producto [°C]",
                    min_value=-10.0, max_value=70.0,
                    value=float(T_prod_default_C),
                    step=1.0,
                    help="Rango razonable: −10 °C (refrigerado) a +70 °C (precalentado).",
                )
                T_prod_inicial_K_val = celsius_a_kelvin(T_prod_inicial_C)

            # Heads-up sobre dependencia GAB
            iso = (catalogo.PRODUCTOS.get(prod_id, {}).get("isoterma") or {}).get("gab") or {}
            iso_params = iso.get("params") or {}
            tiene_gab = (
                iso_params.get("X_m") is not None
                and iso_params.get("C") is not None
                and iso_params.get("K") is not None
            )
            if not tiene_gab:
                st.warning(
                    "⚠️ El producto seleccionado **no tiene parámetros GAB calibrados**. "
                    "El motor termodinámico usará un fallback no-físico (rampa lineal "
                    "`a_w = X / X_inicial`) que sobrestima el secado en X bajo. Para "
                    "resultados confiables, cargar parámetros GAB en el catálogo o "
                    "elegir otro producto."
                )

    # -----------------------------------------------------------------------
    # Botón de cálculo
    # -----------------------------------------------------------------------
    st.divider()
    calcular = st.button("⚙️ Calcular cámara", type="primary")

    if calcular:
        try:
            geo = GeometriaCamara(largo_m=largo, ancho_m=ancho, alto_m=alto)
            cons = ConstruccionCamara(cubierta_translucida=cubierta_trans, U_muros_W_m2K=U_muros)
            band = ConfiguracionBandejas(
                n_bandejas=n_bandejas,
                area_bandeja_m2=area_bandeja,
                espesor_capa_m=espesor_capa,
                separacion_entre_bandejas_m=sep_bandejas,
            )
            flujo = ConfiguracionFlujo(
                caudal_masico_kg_s=caudal,
                fraccion_recirculacion=0.0,
                direccion_flujo=direccion,
                HR_entrada_fraccion=HR_entrada_frac,
            )
            carga = CargaProducto(
                producto_id=prod_id,
                masa_total_kg=masa_kg,
                humedad_inicial_X=X_ini,
                humedad_objetivo_X=X_obj,
                modelo_capa_fina=modelo_cf,
                modelo_isoterma="gab",
                T_prod_inicial_K=T_prod_inicial_K_val,
            )
            camara = Camara(
                geometria=geo,
                construccion=cons,
                bandejas=band,
                flujo=flujo,
                carga_producto=carga,
                modo_calculo=modo_calculo,
            )
            proyecto.camara = camara

        except (ValueError, NotImplementedError) as exc:
            st.error(f"❌ Error de configuración: {exc}")
            return

        # Advertencias estáticas
        adv_list = advertencias_camara(camara)
        if adv_list:
            st.subheader("Advertencias de diseño")
            _mostrar_advertencias(adv_list)
        else:
            st.success("✅ Diseño sin advertencias.")

        # Cálculo numérico — el despachador elige capa_fina o termodinámico.
        T_op_K = celsius_a_kelvin(float(T_op_C))
        HR_op = HR_op_pct / 100.0
        T_amb_calc_K, _ = _T_amb_representativa_K(proyecto)

        try:
            res = calcular_camara(
                camara, T_op_K, HR_op, T_amb_K=T_amb_calc_K,
            )
        except Exception as exc:
            st.error(f"❌ Error en el cálculo: {exc}")
            return

        # Advertencias del cálculo
        if res.advertencias:
            st.subheader("Advertencias del cálculo")
            for msg in res.advertencias:
                st.warning(f"⚠️ {msg}")

        # Display branched por tipo de resultado
        if isinstance(res, ResultadoMotorTermodinamico):
            # ---- Display motor termodinámico ----
            st.subheader("Resultados del motor termodinámico")
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            if res.t_secado_s is not None:
                col_r1.metric(
                    "Tiempo de secado",
                    f"{res.t_secado_s / 3600.0:.1f} h",
                )
            else:
                col_r1.metric("Tiempo de secado", "no alcanzado", help=res.status)
            col_r2.metric("Status", res.status)
            col_r3.metric(
                "Agua evaporada",
                f"{res.masa_evaporada_total_kg:.2f} kg",
                help="Integral de ṁ_w(t) sobre la simulación.",
            )
            col_r4.metric(
                "X final",
                f"{res.X_prod_kg_kg[-1]:.4f}",
                help="Humedad del producto al final de la integración.",
            )

            fig = grafica_termodinamica_camara(res, X_obj, prod_id)
            st.pyplot(fig)
            plt.close(fig)
        else:
            # ---- Display motor capa fina (existente) ----
            st.subheader("Resultados del prediseño")

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            t_h = res.t_secado_s / 3600.0

            col_r1.metric(
                "Tiempo de secado",
                f"{t_h:.1f} h" if res.convergencia_ok else f">{t_h:.0f} h",
                help="Tiempo estimado para reducir X₀ a X_obj.",
            )
            col_r2.metric(
                "X_eq",
                f"{res.X_eq_kg_kg:.4f} kg/kg ms",
                help=f"Humedad de equilibrio ({res.fuente_X_eq}).",
            )
            col_r3.metric(
                "Agua extraída",
                f"{res.masa_agua_extraida_kg:.2f} kg",
                help="Masa de agua que debe evaporarse.",
            )
            col_r4.metric(
                "MR objetivo",
                f"{res.MR_obj:.4f}",
                help="Razón de humedad al final del secado.",
            )

            if not res.convergencia_ok:
                st.warning(f"⚠️ {res.mensaje_convergencia}")

            fig = _grafica_curva_secado(res, X_ini, X_obj, prod_id)
            st.pyplot(fig)
            plt.close(fig)

        # Resumen compacto
        with st.expander("Resumen de la configuración"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Producto:** {prod_id}")
                st.write(f"**Masa:** {masa_kg:.1f} kg")
                st.write(f"**X₀:** {X_ini:.2f} kg/kg ms")
                st.write(f"**X_obj:** {X_obj:.3f} kg/kg ms")
                st.write(f"**Modelo capa fina (catálogo):** {modelo_cf}")
                st.write(f"**Motor numérico:** {modo_calculo}")
                st.write(f"**T_operación:** {T_op_C} °C")
                st.write(f"**HR_operación:** {HR_op_pct} %")
            with c2:
                st.write(f"**Cámara:** {largo}×{ancho}×{alto} m")
                st.write(f"**Bandejas:** {n_bandejas} × {area_bandeja:.2f} m²")
                st.write(f"**Espesor capa:** {espesor_capa*100:.1f} cm")
                st.write(f"**Caudal:** {caudal:.4f} kg/s")
                st.write(f"**Dirección:** {dir_sel}")
                if isinstance(res, ResultadosCamara):
                    st.write(f"**Fuente X_eq:** {res.fuente_X_eq}")
                else:
                    st.write(f"**T_amb (cálculo):** {T_amb_calc_K - 273.15:.1f} °C")

    # --- Guardar configuración ---
    if proyecto.camara is not None:
        st.divider()
        st.download_button(
            "Guardar configuración de la cámara (.txt)",
            data=_texto_config_camara(proyecto.camara),
            file_name="config_camara.txt",
            mime="text/plain",
            use_container_width=True,
        )
