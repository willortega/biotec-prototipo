"""
SISTEMA INTELIGENTE DE GESTIÓN BIOTECNOLÓGICA - Prototipo BIOTEC S.A.S.
Aplicación web (Streamlit) con 5 secciones:
  1. Monitoreo      - lecturas en tiempo real, alertas por rango y alerta anticipada (IA)
  2. Lotes          - registro y actualización de lotes (trazabilidad)
  3. Eventos        - alimentación, volteos, cambios de etapa, incidencias
  4. Trazabilidad   - historial completo de un lote + condiciones ambientales + grados-día
  5. Modelo de IA   - métricas del modelo y explicación

Ejecutar en el computador:   streamlit run app.py
Claves: archivo .streamlit/secrets.toml con SUPABASE_URL y SUPABASE_KEY
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

import joblib
import pandas as pd
import streamlit as st
from supabase import create_client

from ia_utils import a_serie_horaria, grados_dia, ultima_fila_features

st.set_page_config(page_title="BIOTEC - Gestión inteligente", page_icon="🪰", layout="wide")

# Rangos de referencia INICIALES: ajustarlos con la empresa y la literatura (Paso 1.9 de la guía)
RANGOS = {
    "temp_aire": (24.0, 33.0, "Temperatura del aire (°C)"),
    "hum_aire": (50.0, 80.0, "Humedad del aire (%)"),
    "temp_sustrato": (25.0, 35.0, "Temperatura del sustrato (°C)"),
    "hum_sustrato": (55.0, 75.0, "Humedad del sustrato (%)"),
}
ETAPAS = ["Larva", "Prepupa", "Cosechado", "Descartado"]
TIPOS_EVENTO = ["Alimentación", "Volteo", "Cambio de etapa", "Muestreo", "Incidencia", "Otro"]


@st.cache_resource
def cliente():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


sb = cliente()


@st.cache_data(ttl=60)
def leer_lecturas(cama: str, desde_iso: str, hasta_iso: str | None = None) -> pd.DataFrame:
    q = sb.table("lecturas").select("*").eq("cama", cama).gte("creado_en", desde_iso)
    if hasta_iso:
        q = q.lte("creado_en", hasta_iso)
    datos = q.order("creado_en", desc=True).limit(5000).execute().data
    df = pd.DataFrame(datos)
    if not df.empty:
        df["creado_en"] = pd.to_datetime(df["creado_en"], utc=True)
        df = df.sort_values("creado_en")
    return df


@st.cache_data(ttl=30)
def leer_tabla(nombre: str) -> pd.DataFrame:
    return pd.DataFrame(sb.table(nombre).select("*").order("id", desc=True).execute().data)


def camas_disponibles() -> list[str]:
    lotes = leer_tabla("lotes")
    camas = set(lotes["cama"].dropna()) if not lotes.empty else set()
    return sorted(camas | {"cama-01"})


def cargar_modelo():
    if os.path.exists("modelo.joblib"):
        return joblib.load("modelo.joblib")
    return None


# ------------------------------------------------------------------ MENÚ
st.sidebar.title("🪰 BIOTEC S.A.S.")
st.sidebar.caption("Prototipo de gestión biotecnológica IoT + IA")
seccion = st.sidebar.radio("Sección", ["Monitoreo", "Lotes", "Eventos", "Trazabilidad", "Modelo de IA"])
if st.sidebar.button("🔄 Actualizar datos"):
    st.cache_data.clear()

# ------------------------------------------------------------- MONITOREO
if seccion == "Monitoreo":
    st.header("Monitoreo ambiental en tiempo real")
    c1, c2 = st.columns(2)
    cama = c1.selectbox("Cama de cría", camas_disponibles())
    horas = c2.select_slider("Periodo", options=[6, 12, 24, 48, 72, 168], value=24,
                             format_func=lambda h: f"Últimas {h} h")
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    df = leer_lecturas(cama, desde)

    if df.empty:
        st.warning("No hay lecturas en este periodo. Verifique que el nodo esté encendido y enviando datos.")
        st.stop()

    ultima = df.iloc[-1]
    minutos = (datetime.now(timezone.utc) - ultima["creado_en"]).total_seconds() / 60
    st.caption(f"Última lectura: hace {minutos:.0f} min · nodo {ultima['nodo']} · {len(df)} lecturas en el periodo")
    if minutos > 20:
        st.error(f"⚠️ El nodo no reporta hace {minutos:.0f} minutos (posible falla de energía o WiFi).")

    cols = st.columns(4)
    for col, (var, (minimo, maximo, etiqueta)) in zip(cols, RANGOS.items()):
        v = ultima.get(var)
        if pd.isna(v):
            col.metric(etiqueta, "sin dato")
            continue
        fuera = v < minimo or v > maximo
        col.metric(etiqueta, f"{v:.1f}", "FUERA DE RANGO" if fuera else "en rango",
                   delta_color="inverse" if fuera else "off")
        if fuera:
            st.error(f"🚨 {etiqueta} = {v:.1f} (rango recomendado {minimo}–{maximo})")

    # Alerta anticipada con el modelo de IA
    paquete = cargar_modelo()
    if paquete is not None:
        datos_ia = leer_lecturas(cama, (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat())
        serie = a_serie_horaria(datos_ia, "creado_en", paquete["variable"]) if not datos_ia.empty else None
        fila = ultima_fila_features(serie, paquete["rezagos"]) if serie is not None else None
        if fila is not None:
            pred = float(paquete["modelo"].predict(fila)[0])
            texto = (f"🤖 Predicción IA ({paquete['nombre']}): {RANGOS[paquete['variable']][2]} "
                     f"dentro de {paquete['horizonte_h']} h ≈ **{pred:.1f}**")
            if pred >= paquete["umbral"]:
                st.warning(texto + f" → **ALERTA ANTICIPADA** (umbral {paquete['umbral']}). "
                           "Sugerencia: ventilar, sombrear o humedecer antes de que ocurra.")
            else:
                st.info(texto + " → sin riesgo previsto.")
        else:
            st.info("🤖 El modelo necesita al menos 6 horas continuas de lecturas para predecir.")

    st.subheader("Evolución de las variables")
    tabla = df.set_index("creado_en")
    g1, g2 = st.columns(2)
    g1.line_chart(tabla[["temp_aire", "temp_sustrato"]], y_label="°C")
    g2.line_chart(tabla[["hum_aire", "hum_sustrato"]], y_label="%")
    with st.expander("Ver lecturas en tabla y descargar"):
        st.dataframe(df, use_container_width=True)
        st.download_button("Descargar CSV", df.to_csv(index=False), f"lecturas_{cama}.csv", "text/csv")

# ------------------------------------------------------------------ LOTES
elif seccion == "Lotes":
    st.header("Registro de lotes")
    with st.form("nuevo_lote", clear_on_submit=True):
        st.subheader("Nuevo lote")
        c1, c2, c3 = st.columns(3)
        codigo = c1.text_input("Código del lote *", placeholder="L-2026-001")
        cama = c2.text_input("Cama *", value="cama-01")
        fecha_siembra = c3.date_input("Fecha de siembra *", value=date.today())
        c4, c5, c6 = st.columns(3)
        tipo = c4.selectbox("Tipo de sustrato", ["Frutas y verduras", "Residuos de cocina", "Cerdaza",
                                                 "Gallinaza", "Mezcla", "Otro"])
        origen = c5.text_input("Origen / proveedor del sustrato")
        responsable = c6.text_input("Responsable")
        c7, c8 = st.columns(2)
        peso_sus = c7.number_input("Peso del sustrato (kg)", min_value=0.0, step=1.0)
        peso_lar = c8.number_input("Peso de larvas sembradas (g)", min_value=0.0, step=10.0)
        obs = st.text_area("Observaciones")
        if st.form_submit_button("Guardar lote"):
            if not codigo or not cama:
                st.error("El código y la cama son obligatorios.")
            else:
                try:
                    sb.table("lotes").insert({
                        "codigo": codigo.strip(), "cama": cama.strip(), "fecha_siembra": str(fecha_siembra),
                        "tipo_sustrato": tipo, "origen_sustrato": origen, "responsable": responsable,
                        "peso_sustrato_kg": peso_sus, "peso_larvas_g": peso_lar, "observaciones": obs,
                    }).execute()
                    st.cache_data.clear()
                    st.success(f"Lote {codigo} guardado.")
                except Exception as e:
                    st.error(f"No se pudo guardar (¿código repetido?): {e}")

    lotes = leer_tabla("lotes")
    if lotes.empty:
        st.info("Aún no hay lotes registrados.")
    else:
        st.subheader("Actualizar etapa o registrar cosecha")
        sel = st.selectbox("Lote", lotes["codigo"])
        lote = lotes[lotes["codigo"] == sel].iloc[0]
        with st.form("actualizar"):
            c1, c2, c3, c4 = st.columns(4)
            etapa = c1.selectbox("Etapa", ETAPAS, index=ETAPAS.index(lote["etapa"]) if lote["etapa"] in ETAPAS else 0)
            f_cos = c2.date_input("Fecha de cosecha", value=None)
            p_cos = c3.number_input("Larva cosechada (kg)", min_value=0.0, step=0.5)
            p_fra = c4.number_input("Frass / abono (kg)", min_value=0.0, step=0.5)
            if st.form_submit_button("Actualizar"):
                cambios = {"etapa": etapa}
                if f_cos:
                    cambios["fecha_cosecha"] = str(f_cos)
                if p_cos > 0:
                    cambios["peso_cosecha_kg"] = p_cos
                if p_fra > 0:
                    cambios["peso_frass_kg"] = p_fra
                sb.table("lotes").update(cambios).eq("id", int(lote["id"])).execute()
                sb.table("eventos_lote").insert({"lote_id": int(lote["id"]), "tipo": "Cambio de etapa",
                                                 "descripcion": f"Etapa: {etapa}"}).execute()
                st.cache_data.clear()
                st.success("Lote actualizado.")
        st.subheader("Todos los lotes")
        st.dataframe(lotes.drop(columns=["id"]), use_container_width=True)

# ---------------------------------------------------------------- EVENTOS
elif seccion == "Eventos":
    st.header("Registro de eventos de un lote")
    lotes = leer_tabla("lotes")
    if lotes.empty:
        st.info("Primero registre un lote.")
        st.stop()
    activos = lotes[~lotes["etapa"].isin(["Cosechado", "Descartado"])]
    opciones = activos if not activos.empty else lotes
    with st.form("evento", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        sel = c1.selectbox("Lote", opciones["codigo"])
        tipo = c2.selectbox("Tipo de evento", TIPOS_EVENTO)
        cantidad = c3.number_input("Cantidad (kg), si aplica", min_value=0.0, step=0.5)
        desc = st.text_input("Descripción")
        resp = st.text_input("Responsable")
        if st.form_submit_button("Registrar evento"):
            lote_id = int(opciones[opciones["codigo"] == sel]["id"].iloc[0])
            sb.table("eventos_lote").insert({"lote_id": lote_id, "tipo": tipo, "descripcion": desc,
                                             "cantidad_kg": cantidad if cantidad > 0 else None,
                                             "responsable": resp}).execute()
            st.cache_data.clear()
            st.success("Evento registrado.")
    eventos = leer_tabla("eventos_lote")
    if not eventos.empty:
        eventos = eventos.merge(lotes[["id", "codigo"]], left_on="lote_id", right_on="id", suffixes=("", "_l"))
        st.dataframe(eventos[["fecha", "codigo", "tipo", "cantidad_kg", "descripcion", "responsable"]],
                     use_container_width=True)

# ----------------------------------------------------------- TRAZABILIDAD
elif seccion == "Trazabilidad":
    st.header("Trazabilidad completa de un lote")
    lotes = leer_tabla("lotes")
    if lotes.empty:
        st.info("Aún no hay lotes registrados.")
        st.stop()
    sel = st.selectbox("Seleccione el lote", lotes["codigo"])
    lote = lotes[lotes["codigo"] == sel].iloc[0]

    st.subheader("1. Origen y datos del lote")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cama", lote["cama"])
    c2.metric("Siembra", str(lote["fecha_siembra"]))
    c3.metric("Etapa", lote["etapa"])
    c4.metric("Sustrato", f"{lote['peso_sustrato_kg'] or 0:.0f} kg")
    st.write(f"**Tipo de sustrato:** {lote['tipo_sustrato']} · **Origen:** {lote['origen_sustrato'] or '—'} · "
             f"**Responsable:** {lote['responsable'] or '—'}")
    if pd.notna(lote.get("peso_cosecha_kg")) and lote.get("peso_sustrato_kg"):
        tasa = 100 * float(lote["peso_cosecha_kg"]) / float(lote["peso_sustrato_kg"])
        st.success(f"Cosecha: {lote['peso_cosecha_kg']} kg de larva el {lote['fecha_cosecha']} · "
                   f"tasa de bioconversión ≈ {tasa:.1f} % (larva / sustrato, peso fresco)")

    st.subheader("2. Eventos registrados")
    eventos = pd.DataFrame(sb.table("eventos_lote").select("*").eq("lote_id", int(lote["id"]))
                           .order("fecha").execute().data)
    if eventos.empty:
        st.caption("Sin eventos registrados.")
    else:
        st.dataframe(eventos[["fecha", "tipo", "cantidad_kg", "descripcion", "responsable"]], use_container_width=True)
        alim = eventos[eventos["tipo"] == "Alimentación"]["cantidad_kg"].sum()
        st.caption(f"Total de alimento agregado: {alim:.1f} kg en {int((eventos['tipo'] == 'Alimentación').sum())} alimentaciones")

    st.subheader("3. Condiciones ambientales durante el ciclo")
    inicio = pd.Timestamp(lote["fecha_siembra"], tz="UTC")
    fin = pd.Timestamp(lote["fecha_cosecha"], tz="UTC") + pd.Timedelta(days=1) if pd.notna(lote.get("fecha_cosecha")) \
        else pd.Timestamp.now(tz="UTC")
    lect = leer_lecturas(lote["cama"], inicio.isoformat(), fin.isoformat())
    if lect.empty:
        st.warning("No hay lecturas del nodo para la cama y el periodo de este lote.")
    else:
        resumen = []
        for var, (minimo, maximo, etiqueta) in RANGOS.items():
            s = pd.to_numeric(lect[var], errors="coerce").dropna()
            if s.empty:
                continue
            resumen.append({"Variable": etiqueta, "Promedio": round(s.mean(), 1), "Mínimo": round(s.min(), 1),
                            "Máximo": round(s.max(), 1),
                            "% tiempo fuera de rango": round(100 * ((s < minimo) | (s > maximo)).mean(), 1)})
        st.dataframe(pd.DataFrame(resumen), use_container_width=True, hide_index=True)
        st.line_chart(lect.set_index("creado_en")[["temp_aire", "temp_sustrato"]], y_label="°C")

        st.subheader("4. Grados-día y fecha estimada de cosecha")
        col_t = "temp_sustrato" if lect["temp_sustrato"].notna().any() else "temp_aire"
        diaria = lect.set_index("creado_en")[col_t].astype(float).resample("1D").mean().dropna()
        c1, c2 = st.columns(2)
        t_base = c1.number_input("Temperatura base (°C)", value=12.0, step=0.5,
                                 help="Referencia: ~10–12 °C para larvas (Chia et al., 2018)")
        gd_obj = c2.number_input("Grados-día objetivo hasta cosecha", value=300.0, step=10.0,
                                 help="Calibrar con lotes anteriores de la empresa (Paso 4.6 de la guía)")
        gd = grados_dia(diaria, t_base)
        acumulado = float(gd.iloc[-1]) if not gd.empty else 0.0
        st.progress(min(acumulado / gd_obj, 1.0), text=f"{acumulado:.0f} de {gd_obj:.0f} grados-día acumulados")
        ritmo = float((diaria - t_base).clip(lower=0).tail(3).mean()) if not diaria.empty else 0
        if acumulado >= gd_obj:
            st.success("El lote alcanzó los grados-día objetivo: revisar si está listo para cosecha.")
        elif ritmo > 0:
            dias = (gd_obj - acumulado) / ritmo
            st.info(f"Al ritmo actual (~{ritmo:.1f} GD/día), faltan ≈ {dias:.0f} días → "
                    f"cosecha estimada hacia el {(date.today() + timedelta(days=round(dias))).isoformat()}")

# ------------------------------------------------------------ MODELO DE IA
elif seccion == "Modelo de IA":
    st.header("Modelo de inteligencia artificial")
    paquete = cargar_modelo()
    if paquete is None:
        st.warning("No se encontró modelo.joblib. Entrénelo con entrenar_modelo.py (Semana 4 de la guía).")
        st.stop()
    st.write(f"**Modelo en uso:** {paquete['nombre']} · **Variable:** {RANGOS[paquete['variable']][2]} · "
             f"**Predice a:** {paquete['horizonte_h']} h · **Usa:** últimas {paquete['rezagos']} h · "
             f"**Umbral de alerta:** {paquete['umbral']}")
    if os.path.exists("metricas.json"):
        with open("metricas.json", encoding="utf-8") as f:
            m = json.load(f)
        st.caption(f"Datos: {m['fuente']} · entrenamiento {m['n_entrenamiento']} h · prueba {m['n_prueba']} h")
        tabla = pd.DataFrame(m["resultados"]).T.drop(columns="matriz_confusion")
        st.dataframe(tabla, use_container_width=True)
        st.caption("MAE/RMSE: error promedio en las unidades de la variable (menor es mejor). "
                   "R²: proporción de la variación explicada (más cerca de 1 es mejor). "
                   "F1: equilibrio entre alertas acertadas y alertas perdidas.")
    if os.path.exists("graficas_modelo.png"):
        st.image("graficas_modelo.png")
