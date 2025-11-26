"""
Módulo de funciones para detección de drift univariado.

Responsabilidades principales:
1) Estrategias de referencia (baseline)
   - ref_decay_prefix_mass : referencia con decaimiento exponencial en el tiempo.
   - ref_seasonal_cycles   : referencia estacional basada en ciclos completos.
   - ref_golden            : referencia a partir de ventanas históricas estables.

2) Métodos estadísticos (drift univariado)
   - psi_numeric           : Population Stability Index (PSI).
   - ks_numeric            : Kolmogorov–Smirnov (KS).
   - wasserstein_numeric   : Distancia de Wasserstein.
   - score_numeric_series  : wrapper unificado para elegir la métrica.

Notas:
    • Este módulo NO decide umbrales (eso se hace en drift_thresholds.py).
    • Este módulo NO se preocupa de ventanas ni episodios (eso se hace en pipeline_drift.py).
    • Todas las funciones asumen series numéricas ya alineadas y limpias a nivel de índice.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance


# ============================================================
#  Estrategias de Referencias
# ============================================================

def ref_decay_prefix_mass(
    df_hist: pd.DataFrame, # DataFrame histórico
    now: pd.Timestamp, # Timestamp actual (fin de ventana corriente)
    half_life_hours: int = 24 * 7, # Vida media del decaimiento en horas
    target_mass: float = 0.95, # Fracción de masa acumulada objetivo
) -> pd.DataFrame:
    """
    Referencia con decaimiento exponencial.
    
    Pondera observaciones pasadas exponencialmente, priorizando datos recientes
    Retorna el prefijo que concentra `target_mass` del peso total acumulado    
    """
    # Constante de tiempo
    tau = pd.Timedelta(hours=half_life_hours) / np.log(2)
    # Pesos exponenciales
    dt = (now - df_hist.index)
    w = np.exp(-dt / tau).astype(float)

    # ordenamos por recencia (más recientes primero)
    order = np.argsort(-df_hist.index.view("i8"))
    w_sorted = w.values[order]
    # Masa acumulada(normalizada)
    cum = np.cumsum(w_sorted) / w_sorted.sum()
    # Corte target_mass
    cut_idx = np.searchsorted(cum, 0.95 if target_mass is None else target_mass, side="left")
    take_pos = order[: (cut_idx + 1)]
    
    # DataFrame con las observaciones que cumplen el criterio de masa
    return df_hist.iloc[np.sort(take_pos)]


def ref_seasonal_cycles(
    df_hist: pd.DataFrame,
    current_end: pd.Timestamp,
    cycle_hours: float = 24.0,
    cycles_back: int = 7,
) -> pd.DataFrame:
    """
    Construye una referencia estacional basada en ciclos completos.

    Ejemplo para cycle_hours=24:
    - toma los últimos 7 días completos antes de current_end
    - extrae cada ciclo día desde (t - k*24h) hasta (t - (k-1)*24h)
    - concatena todos los ciclos como referencia robusta
    """
    if df_hist.empty:
        return df_hist

    cycle = pd.Timedelta(hours=cycle_hours)

    refs = []

    for k in range(1, cycles_back + 1):
        end_k = current_end - (k - 1) * cycle
        start_k = end_k - cycle

        seg = df_hist.loc[start_k:end_k]
        if len(seg) > 0:
            refs.append(seg)

    if not refs:
        return df_hist

    return pd.concat(refs)


def ref_golden(
    df_hist: pd.DataFrame, # DataFrame histórico
    win: str = "30min", # Tamano ventana para análisis
    step: str = "10min", # Paso entre ventanas
    k: int = 40) -> pd.DataFrame: # número de ventanas a seleccionar
    """
    Referencia basada en ventanas históricas estables
    
    Selecciona las k ventanas más estables del historial evaluando
    estabilidad mediante IQR/mediana normalizado
    """

    win_td = pd.to_timedelta(win)
    step_td = pd.to_timedelta(step)
    # Generar timestamps de inicio de ventanas
    starts = []
    t = df_hist.index.min()
    tmax = df_hist.index.max()

    while t + win_td <= tmax:
        starts.append(t)
        t += step_td

    # Evaluar estabilidad de cada ventana
    windows = []
    for t0 in starts:
        t1 = t0 + win_td - pd.Timedelta(nanoseconds=1)
        sub = df_hist.loc[t0:t1]
        if len(sub) < 3:
            continue

        num = sub.select_dtypes(include="number")

        # Calcular RSD robusto (IQR/mediana)
        med = num.median()
        iqr = num.quantile(0.75) - num.quantile(0.25)
        rsd = (iqr / (med.abs() + 1e-12)).replace([np.inf, -np.inf], np.nan)
        score = rsd.median(skipna=True)

        windows.append((t0, t1, float(score)))

    # Seleccionar las k ventanas más estables
    top = (pd.DataFrame(windows, columns=["t0","t1","score"])
             .sort_values("score")
             .head(k))

    # Concatenar datos de ventanas seleccionadas
    parts = [df_hist.loc[t0:t1] for t0, t1, _ in top.itertuples(index=False)]

    # DataFrame concatenado de las k ventanas más estables
    return pd.concat(parts, axis=0) 

# ============================================================
#  Métodos Estadísticos
# ============================================================

def ks_numeric(ref, cur) -> float | None:
    # Mide la máxima diferencia entre funciones de distribución acumulada
    r = pd.to_numeric(ref, errors="coerce").dropna()
    c = pd.to_numeric(cur, errors="coerce").dropna()
    if len(r) < 5 or len(c) < 5:
        return None
    
    # Estadístico KS en [0, 1], donde mayor valor = mayor diferencia
    return float(ks_2samp(r, c, alternative="two-sided", mode="auto").statistic)


def wasserstein_numeric(ref, cur) -> float | None:
    # Mide el costo de transformar una distribución en otra
    r = pd.to_numeric(ref, errors="coerce").dropna()
    c = pd.to_numeric(cur, errors="coerce").dropna()
    if len(r) < 5 or len(c) < 5:
        return None
    # Distancia Wasserstein (≥ 0), donde mayor valor = mayor diferencia
    return float(wasserstein_distance(r, c))

def psi_numeric(ref, cur, n_bins: int = 10) -> float | None:
    # Mide divergencia mediante discretización y comparación de frecuencias
    r = pd.to_numeric(ref, errors="coerce").dropna().to_numpy()
    c = pd.to_numeric(cur, errors="coerce").dropna().to_numpy()

    if r.size < 5 or c.size < 5:
        return None

    qs = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(r, qs)

    # Caso degenerado
    edges = np.unique(edges)
    if edges.size < 2:
        return 0.0

    r_bins, edges = np.histogram(r, bins=edges)
    c_bins, _ = np.histogram(c, bins=edges)

    # Frecuencias normalizadas con suavizado
    eps = 1e-6
    p_r = np.clip(r_bins.astype(float) / r_bins.sum(), eps, 1.0)
    p_c = np.clip(c_bins.astype(float) / c_bins.sum(), eps, 1.0)

    p_r /= p_r.sum()
    p_c /= p_c.sum()

    # Valor PSI (≥ 0), donde mayor valor = mayor divergencia
    return float(np.sum((p_c - p_r) * np.log(p_c / p_r)))

def score_numeric_series(a: pd.Series, b: pd.Series, method: str) -> float | None:
    """
    Wrapper unificado para calcular métrica de drift
    Retorna Valor de la métrica según el método elegido
    """
    method = str(method).lower()

    if method == "psi":
        return psi_numeric(a, b, n_bins=10)
    if method == "ks":
        return ks_numeric(a, b)
    if method == "wasserstein":
        return wasserstein_numeric(a, b)

    # fallback: PSI
    return psi_numeric(a, b, n_bins=10)

