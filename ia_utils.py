"""
Funciones compartidas por el entrenamiento (entrenar_modelo.py) y la
aplicación (app.py). Así el modelo recibe SIEMPRE las variables construidas
de la misma forma.

Idea del modelo: con las últimas REZAGOS horas de una variable (p. ej. la
temperatura del aire) y la hora del día, predecir su valor HORIZONTE horas
después. Si el valor predicho supera el umbral, el sistema genera una
ALERTA ANTICIPADA.
"""
import numpy as np
import pandas as pd

REZAGOS = 6        # horas de historia que mira el modelo
HORIZONTE = 3      # horas hacia adelante que predice


def a_serie_horaria(df: pd.DataFrame, col_tiempo: str, col_valor: str) -> pd.Series:
    """Convierte lecturas irregulares (cada 1-5 min) en una serie de promedios por hora."""
    datos = df[[col_tiempo, col_valor]].dropna().copy()
    datos[col_tiempo] = pd.to_datetime(datos[col_tiempo], utc=True)
    datos[col_valor] = pd.to_numeric(datos[col_valor], errors="coerce")
    serie = datos.set_index(col_tiempo)[col_valor].sort_index().resample("1h").mean()
    return serie.interpolate(limit=3)   # rellena huecos cortos (máx. 3 horas)


def matriz_features(serie: pd.Series, rezagos: int = REZAGOS) -> pd.DataFrame:
    """lag_0 = valor de la hora actual, lag_1 = hora anterior, ... + hora del día."""
    X = pd.DataFrame({f"lag_{i}": serie.shift(i) for i in range(rezagos)}, index=serie.index)
    hora = serie.index.tz_convert("America/Bogota").hour if serie.index.tz is not None else serie.index.hour
    X["hora_sin"] = np.sin(2 * np.pi * np.asarray(hora) / 24)
    X["hora_cos"] = np.cos(2 * np.pi * np.asarray(hora) / 24)
    return X


def dataset_supervisado(serie: pd.Series, horizonte: int = HORIZONTE, rezagos: int = REZAGOS):
    """Devuelve X (variables de entrada) e y (valor real HORIZONTE horas después)."""
    X = matriz_features(serie, rezagos)
    y = serie.shift(-horizonte).rename("objetivo")
    datos = pd.concat([X, y], axis=1).dropna()
    return datos.drop(columns="objetivo"), datos["objetivo"]


def ultima_fila_features(serie: pd.Series, rezagos: int = REZAGOS):
    """Variables de la hora más reciente, para hacer una predicción en vivo."""
    X = matriz_features(serie, rezagos).dropna()
    if X.empty:
        return None
    return X.iloc[[-1]]


def grados_dia(temp_diaria_media: pd.Series, t_base: float = 12.0) -> pd.Series:
    """Grados-día acumulados: suma de (T media diaria - T base) cuando es positiva.
    T base de referencia para larvas de H. illucens: ~10-12 °C (Chia et al., 2018)."""
    gd = (temp_diaria_media - t_base).clip(lower=0)
    return gd.cumsum()
