"""
ENTRENAMIENTO DEL MODELO DE IA - Prototipo BIOTEC S.A.S.
Ejecutar en Google Colab (gratis) o en el computador con Python 3.10+.

Qué hace:
 1. Obtiene datos horarios de temperatura (o humedad):
      FUENTE = "openmeteo" -> clima histórico real de El Banco, Magdalena (gratis, sin clave)
      FUENTE = "csv"       -> lecturas propias exportadas desde Supabase (lecturas.csv)
 2. Construye el conjunto de entrenamiento (últimas 6 horas -> valor dentro de 3 horas).
 3. Entrena y compara 3 modelos: persistencia (base), regresión lineal y Random Forest.
 4. Evalúa la ALERTA ANTICIPADA (¿superará el umbral?) con accuracy, precisión, recall y F1.
 5. Guarda modelo.joblib, metricas.json y graficas_modelo.png para el informe y la app.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import joblib
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, r2_score, recall_score)

from ia_utils import HORIZONTE, REZAGOS, a_serie_horaria, dataset_supervisado

# ----------------------------- CONFIGURACIÓN -----------------------------
FUENTE = "openmeteo"          # "openmeteo" o "csv"
VARIABLE = "temp_aire"        # columna a predecir: temp_aire, hum_aire, temp_sustrato
UMBRAL_ALERTA = 33.0          # alerta si el valor predicho >= umbral (ajustar con la empresa)
LAT, LON = 9.00, -73.97       # El Banco, Magdalena (aprox.)
ANIOS = [2024, 2025]          # años de clima histórico a descargar
ARCHIVO_CSV = "lecturas.csv"  # exportado desde Supabase (Table editor > lecturas > Export)

# ----------------------------- 1. DATOS ----------------------------------
def descargar_openmeteo() -> pd.DataFrame:
    """Clima horario histórico (reanálisis) desde Open-Meteo, un año por petición."""
    variable_api = {"temp_aire": "temperature_2m", "hum_aire": "relative_humidity_2m"}[VARIABLE]
    partes = []
    for anio in ANIOS:
        params = {
            "latitude": LAT, "longitude": LON,
            "start_date": f"{anio}-01-01", "end_date": f"{anio}-12-31",
            "hourly": variable_api, "timezone": "UTC",
        }
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=60)
        r.raise_for_status()
        h = r.json()["hourly"]
        partes.append(pd.DataFrame({"creado_en": pd.to_datetime(h["time"], utc=True),
                                    VARIABLE: h[variable_api]}))
        print(f"Año {anio}: {len(h['time'])} horas descargadas")
    return pd.concat(partes, ignore_index=True)


if FUENTE == "openmeteo":
    df = descargar_openmeteo()
else:
    df = pd.read_csv(ARCHIVO_CSV)

serie = a_serie_horaria(df, "creado_en", VARIABLE)
print(f"Serie horaria: {len(serie)} horas, desde {serie.index.min()} hasta {serie.index.max()}")
print(serie.describe().round(2))

X, y = dataset_supervisado(serie, HORIZONTE, REZAGOS)
if len(X) < 200:
    raise SystemExit("Muy pocos datos (menos de 200 horas). Use FUENTE='openmeteo' o espere más días de lecturas.")

# División TEMPORAL: 80 % más antiguo para entrenar, 20 % más reciente para probar.
# (Nunca se mezclan al azar en series de tiempo: sería hacer trampa con el futuro.)
corte = int(len(X) * 0.8)
X_tr, X_te, y_tr, y_te = X.iloc[:corte], X.iloc[corte:], y.iloc[:corte], y.iloc[corte:]
print(f"Entrenamiento: {len(X_tr)} filas | Prueba: {len(X_te)} filas")

# ----------------------------- 2. MODELOS --------------------------------
modelos = {
    "Persistencia (base)": None,   # predice que dentro de 3 h el valor será igual al actual
    "Regresión lineal": LinearRegression(),
    "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=5,
                                           random_state=42, n_jobs=-1),
}

resultados, predicciones = {}, {}
for nombre, modelo in modelos.items():
    if modelo is None:
        pred = X_te["lag_0"].values
    else:
        modelo.fit(X_tr, y_tr)
        pred = modelo.predict(X_te)
    predicciones[nombre] = pred

    real_alerta = (y_te.values >= UMBRAL_ALERTA).astype(int)
    pred_alerta = (pred >= UMBRAL_ALERTA).astype(int)
    resultados[nombre] = {
        "MAE": round(mean_absolute_error(y_te, pred), 3),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_te, pred))), 3),
        "R2": round(r2_score(y_te, pred), 3),
        "alerta_accuracy": round(accuracy_score(real_alerta, pred_alerta), 3),
        "alerta_precision": round(precision_score(real_alerta, pred_alerta, zero_division=0), 3),
        "alerta_recall": round(recall_score(real_alerta, pred_alerta, zero_division=0), 3),
        "alerta_F1": round(f1_score(real_alerta, pred_alerta, zero_division=0), 3),
        "matriz_confusion": confusion_matrix(real_alerta, pred_alerta, labels=[0, 1]).tolist(),
    }

tabla = pd.DataFrame(resultados).T.drop(columns="matriz_confusion")
print("\n=== RESULTADOS EN EL CONJUNTO DE PRUEBA ===")
print(tabla.to_string())

# El mejor modelo es el de menor RMSE (sin contar la persistencia)
candidatos = {k: v for k, v in resultados.items() if modelos[k] is not None}
mejor = min(candidatos, key=lambda k: candidatos[k]["RMSE"])
print(f"\nMejor modelo: {mejor}")

# ----------------------------- 3. GUARDAR --------------------------------
joblib.dump({
    "modelo": modelos[mejor], "nombre": mejor, "variable": VARIABLE,
    "rezagos": REZAGOS, "horizonte_h": HORIZONTE, "umbral": UMBRAL_ALERTA,
    "sklearn_version": sklearn.__version__,
}, "modelo.joblib")

with open("metricas.json", "w", encoding="utf-8") as f:
    json.dump({"fuente": FUENTE, "variable": VARIABLE, "horizonte_h": HORIZONTE,
               "rezagos": REZAGOS, "umbral": UMBRAL_ALERTA, "n_entrenamiento": len(X_tr),
               "n_prueba": len(X_te), "mejor_modelo": mejor, "resultados": resultados,
               "sklearn_version": sklearn.__version__}, f, ensure_ascii=False, indent=2)

# Gráficas para el informe: real vs predicho (últimas 2 semanas de prueba) y error
fig, ax = plt.subplots(2, 1, figsize=(11, 7))
n = min(336, len(y_te))
ax[0].plot(y_te.index[-n:], y_te.values[-n:], label="Real", linewidth=1.5)
ax[0].plot(y_te.index[-n:], predicciones[mejor][-n:], label=f"Predicho ({mejor})", linewidth=1)
ax[0].plot(y_te.index[-n:], predicciones["Persistencia (base)"][-n:], label="Persistencia", alpha=0.5)
ax[0].axhline(UMBRAL_ALERTA, color="red", linestyle="--", label="Umbral de alerta")
ax[0].set_title(f"{VARIABLE}: predicción a {HORIZONTE} h (últimas 2 semanas del conjunto de prueba)")
ax[0].legend()
nombres = list(resultados)
ax[1].bar(nombres, [resultados[k]["RMSE"] for k in nombres], color=["gray", "tab:blue", "tab:green"])
ax[1].set_title("RMSE por modelo (menor es mejor)")
plt.tight_layout()
plt.savefig("graficas_modelo.png", dpi=150)
print("Archivos guardados: modelo.joblib, metricas.json, graficas_modelo.png")
