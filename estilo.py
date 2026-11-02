import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

:root {
  --bg: #0a0d14;
  --vidrio: rgba(16, 22, 34, 0.65);
  --borde: rgba(0, 255, 136, 0.2);
  --verde: #00ff88;
  --azul: #00d4ff;
  --muted: #a0aabf;
}

html, body, .stApp, [class*="css"] { font-family: 'Outfit', sans-serif; }
html, body { background: var(--bg); }

/* Scrollbars ultrafinas estilo SaaS corporativo */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(10, 13, 20, 0.5);
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 255, 136, 0.2);
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 255, 136, 0.4);
}

/* Fondo: degradados suaves */
.stApp {
  background:
    radial-gradient(circle at 15% 0%, rgba(0, 212, 255, 0.12), transparent 45%),
    radial-gradient(circle at 90% 100%, rgba(0, 255, 136, 0.1), transparent 40%),
    var(--bg);
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {
  background: transparent !important;
}

/* --- FONDO AVANZADO PARA LA BARRA LATERAL --- */
[data-testid="stSidebar"] {
  background: 
    linear-gradient(180deg, rgba(10, 13, 20, 0.94) 0%, rgba(6, 9, 15, 0.99) 100%),
    radial-gradient(circle at 50% 0%, rgba(0, 255, 136, 0.08), transparent 50%) !important;
  backdrop-filter: blur(18px);
  border-right: 1px solid var(--borde);
}

/* Títulos con gradiente élite */
h1, h2, h3 { font-weight: 800; letter-spacing: -0.01em; }
h1 {
  background: linear-gradient(90deg, #ffffff, var(--azul));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Tarjetas de métricas con efecto de iluminación superior (Glow Elite) */
[data-testid="stMetric"] {
  background: linear-gradient(145deg, rgba(16, 22, 34, 0.85), rgba(10, 13, 20, 0.95));
  border: 1px solid var(--borde);
  border-radius: 16px;
  padding: 18px 14px;
  backdrop-filter: blur(14px);
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(0, 255, 136, 0.2);
  transition: transform 0.2s ease, border-color 0.2s ease;
}
[data-testid="stMetric"]:hover {
  border-color: rgba(0, 255, 136, 0.4);
  transform: translateY(-2px);
}

[data-testid="stMetricValue"] { 
  color: var(--verde); 
  font-weight: 600; 
  font-size: 1.5rem !important; 
  white-space: normal !important; 
}

[data-testid="stMetricLabel"] { 
  color: var(--muted); 
}

/* Alertas, formularios, tablas y gráficas */
[data-testid="stAlert"] {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
}
[data-testid="stForm"] {
  background: var(--vidrio);
  border: 1px solid var(--borde);
  border-radius: 18px;
  backdrop-filter: blur(12px);
}
[data-testid="stDataFrame"], [data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
  background: var(--vidrio);
  border: 1px solid var(--borde);
  border-radius: 16px;
  padding: 8px;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
}

/* Botones con brillo corporativo */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 12px;
  border: 1px solid var(--verde);
  background: rgba(0, 255, 136, 0.08);
  color: var(--verde);
  font-weight: 600;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 15px rgba(0, 255, 136, 0.1);
}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  background: var(--verde);
  color: #04110a;
  border-color: var(--verde);
  box-shadow: 0 6px 22px rgba(0, 255, 136, 0.3);
  transform: translateY(-1px);
}

/* Campos de texto y selectores */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  background: rgba(0, 0, 0, 0.4) !important;
  border-radius: 10px !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
}

/* Barra de progreso (grados-día) */
.stProgress > div > div > div > div { background-image: linear-gradient(90deg, var(--azul), var(--verde)); }

/* --- MENÚ LATERAL PROFESIONAL ULTRA-PRO --- */
[data-testid="stRadio"] > label {
  font-size: 0.75rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  color: var(--muted) !important;
  background: transparent !important;
  border: none !important;
  padding: 0 0 6px 4px !important;
}

/* Tarjetas base del menú con efecto vidrio avanzado */
[data-testid="stRadio"] div[role="radiogroup"] label {
  background: rgba(16, 22, 34, 0.45) !important;
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  border-radius: 12px !important;
  padding: 10px 14px !important;
  margin-bottom: 8px !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  cursor: pointer;
  backdrop-filter: blur(10px);
}

/* Efecto al pasar el cursor (Hover) */
[data-testid="stRadio"] div[role="radiogroup"] label:hover {
  background: rgba(0, 255, 136, 0.06) !important;
  border-color: rgba(0, 255, 136, 0.3) !important;
  transform: translateX(4px);
}

/* ESTILO PARA LA OPCIÓN SELECCIONADA (Activa) */
[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(0, 255, 136, 0.18), rgba(16, 22, 34, 0.85)) !important;
  border-color: var(--verde) !important;
  box-shadow: 0 4px 20px rgba(0, 255, 136, 0.18);
}

/* Texto de las opciones del menú */
[data-testid="stRadio"] div[role="radiogroup"] label p {
  font-weight: 600 !important;
  color: #f8f9fa !important;
}
"""


def aplicar_estilo() -> None:
    """Inyecta el tema visual sin video. Llamar una sola vez, después de st.set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)