"""
SENSOR VIRTUAL - Ruta B (simulada)
Genera lecturas realistas y las guarda en Supabase como si fueran de un nodo.
La base es el clima horario REAL de El Banco (Open-Meteo); al sustrato se le
suma el calor que generan las larvas y una humedad que varía lentamente.

IMPORTANTE (honestidad académica): estos datos se identifican con
nodo = "virtual-01" y deben declararse como SIMULADOS en el informe.

Modos:
  python sensor_virtual.py historico 30   -> carga los últimos 30 días (para tener datos ya)
  python sensor_virtual.py vivo 60        -> envía una lectura cada 60 segundos (para la demo)
"""
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from supabase import create_client

# ---- CONFIGURACIÓN (copiar de Supabase: Project Settings > API) ----
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU_ANON_PUBLIC_KEY"
CAMA = "cama-01"
NODO = "virtual-01"
LAT, LON = 9.00, -73.97

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def clima_horario(dias: int) -> pd.DataFrame:
    """Temperatura y humedad horarias reales de los últimos 'dias' días."""
    fin = datetime.now(timezone.utc).date() - timedelta(days=2)   # el archivo tiene ~2 días de rezago
    inicio = fin - timedelta(days=dias)
    params = {"latitude": LAT, "longitude": LON, "start_date": str(inicio), "end_date": str(fin),
              "hourly": "temperature_2m,relative_humidity_2m", "timezone": "UTC"}
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=60)
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame({"t": pd.to_datetime(h["time"], utc=True),
                       "temp": h["temperature_2m"], "hum": h["relative_humidity_2m"]}).dropna()
    # Se desplaza la serie para que termine "ahora"
    desfase = datetime.now(timezone.utc) - df["t"].max().to_pydatetime()
    df["t"] = df["t"] + desfase
    return df


def lectura_desde_clima(temp, hum, hum_sus_prev):
    """Convierte clima exterior en condiciones dentro del galpón y de la cama de cría."""
    t_aire = temp + random.uniform(-0.4, 0.4) + 1.0           # galpón algo más cálido
    h_aire = min(98, max(35, hum + random.uniform(-2, 2)))
    t_sus = t_aire + random.uniform(2.0, 5.0)                 # calor metabólico de las larvas
    h_sus = min(80, max(45, hum_sus_prev + random.uniform(-0.6, 0.5)))
    return round(t_aire, 2), round(h_aire, 2), round(t_sus, 2), round(h_sus, 2)


def modo_historico(dias: int):
    df = clima_horario(dias)
    filas, h_sus = [], 68.0
    for _, fila in df.iterrows():
        for minuto in (0, 15, 30, 45):       # 4 lecturas por hora
            t_a, h_a, t_s, h_sus = lectura_desde_clima(fila["temp"], fila["hum"], h_sus)
            filas.append({"creado_en": (fila["t"] + timedelta(minutes=minuto)).isoformat(),
                          "nodo": NODO, "cama": CAMA, "temp_aire": t_a, "hum_aire": h_a,
                          "temp_sustrato": t_s, "hum_sustrato": h_sus})
    for i in range(0, len(filas), 500):      # se envía en bloques de 500
        sb.table("lecturas").insert(filas[i:i + 500]).execute()
        print(f"Insertadas {min(i + 500, len(filas))} de {len(filas)}")


def modo_vivo(segundos: int):
    df = clima_horario(3)
    base_t, base_h = float(df["temp"].iloc[-1]), float(df["hum"].iloc[-1])
    h_sus, paso = 68.0, 0
    while True:
        hora = datetime.now().hour
        ciclo = 3.5 * np.sin(2 * np.pi * (hora - 9) / 24)    # día más caliente que la noche
        t_a, h_a, t_s, h_sus = lectura_desde_clima(base_t + ciclo, base_h - 2 * ciclo, h_sus)
        sb.table("lecturas").insert({"nodo": NODO, "cama": CAMA, "temp_aire": t_a, "hum_aire": h_a,
                                     "temp_sustrato": t_s, "hum_sustrato": h_sus}).execute()
        paso += 1
        print(f"[{paso}] aire {t_a} C {h_a} % | sustrato {t_s} C {h_sus} %")
        time.sleep(segundos)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "vivo"
    valor = int(sys.argv[2]) if len(sys.argv) > 2 else (30 if modo == "historico" else 60)
    modo_historico(valor) if modo == "historico" else modo_vivo(valor)
