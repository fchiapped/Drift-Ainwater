from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance
# ============================================================

#  KS  (Kolmogorov-Smirnov)
def ks_numeric(ref, cur) -> float | None:
    r = pd.to_numeric(ref, errors="coerce").dropna()
    c = pd.to_numeric(cur, errors="coerce").dropna()
    if len(r) < 5 or len(c) < 5:
        return None
    return float(ks_2samp(r, c, alternative="two-sided", mode="auto").statistic)

# Wasserstein
def wasserstein_numeric(ref, cur) -> float | None:
    r = pd.to_numeric(ref, errors="coerce").dropna()
    c = pd.to_numeric(cur, errors="coerce").dropna()
    if len(r) < 5 or len(c) < 5:
        return None
    return float(wasserstein_distance(r, c))

#  PSI  (Population Stability Index)
def psi_numeric(ref, cur, n_bins: int = 10) -> float | None:
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

    eps = 1e-6
    p_r = np.clip(r_bins.astype(float) / r_bins.sum(), eps, 1.0)
    p_c = np.clip(c_bins.astype(float) / c_bins.sum(), eps, 1.0)

    p_r /= p_r.sum()
    p_c /= p_c.sum()

    return float(np.sum((p_c - p_r) * np.log(p_c / p_r)))

def score_numeric_series(a: pd.Series, b: pd.Series, metric: str) -> float | None:
    """
    Wrapper genérico para métricas numéricas de drift.

    Métricas soportadas:
      - 'psi'
      - 'ks'
      - 'wasserstein'

    Si la métrica no se reconoce, se usa PSI como fallback.
    """
    metric = str(metric).lower()

    if metric == "psi":
        return psi_numeric(a, b, n_bins=10)
    if metric == "ks":
        return ks_numeric(a, b)
    if metric == "wasserstein":
        return wasserstein_numeric(a, b)

    # fallback: PSI
    return psi_numeric(a, b, n_bins=10)
# ============================================================
#  Estrategias de referencias
# ============================================================

# Referencia Exponencial
def ref_decay_prefix_mass(
    df_hist: pd.DataFrame,
    now: pd.Timestamp,
    half_life_hours: int = 24 * 7,
    target_mass: float = 0.95,
) -> pd.DataFrame:
    if df_hist.empty:
        return df_hist

    tau = pd.Timedelta(hours=half_life_hours) / np.log(2)
    dt = (now - df_hist.index)
    w = np.exp(-dt / tau).astype(float)

    # ordenamos por recencia (más recientes primero)
    order = np.argsort(-df_hist.index.view("i8"))
    w_sorted = w.values[order]
    cum = np.cumsum(w_sorted) / w_sorted.sum()
    cut_idx = np.searchsorted(cum, 0.95 if target_mass is None else target_mass, side="left")
    take_pos = order[: (cut_idx + 1)]
    return df_hist.iloc[np.sort(take_pos)]

# Referencia Estacional
def ref_seasonal(
    df_hist: pd.DataFrame,
    current_end: pd.Timestamp,
    weeks_back: int = 12,
) -> pd.DataFrame:
    if df_hist.empty:
        return df_hist.iloc[:0]

    slot = current_end.dayofweek * 24 + current_end.hour
    dw, hh = df_hist.index.dayofweek, df_hist.index.hour
    mask = (dw * 24 + hh) == slot
    hist = df_hist.loc[mask].loc[:current_end]
    if hist.empty:
        return df_hist.iloc[:0]

    start_lim = current_end - pd.Timedelta(weeks=weeks_back)
    return hist.loc[start_lim:]

# Referencia Estabilidad
def ref_golden(df_hist: pd.DataFrame,
               win: str = "30min",
               step: str = "10min",
               k: int = 40) -> pd.DataFrame:

    if df_hist.empty:
        return df_hist.iloc[:0]

    win_td = pd.to_timedelta(win)
    step_td = pd.to_timedelta(step)

    starts = []
    t = df_hist.index.min()
    tmax = df_hist.index.max()

    while t + win_td <= tmax:
        starts.append(t)
        t += step_td

    windows = []
    for t0 in starts:
        t1 = t0 + win_td - pd.Timedelta(nanoseconds=1)
        sub = df_hist.loc[t0:t1]
        if len(sub) < 3:
            continue

        num = sub.select_dtypes(include="number")
        if num.empty:
            continue

        med = num.median()
        iqr = num.quantile(0.75) - num.quantile(0.25)
        rsd = (iqr / (med.abs() + 1e-12)).replace([np.inf, -np.inf], np.nan)
        score = rsd.median(skipna=True)

        windows.append((t0, t1, float(score)))

    if not windows:
        return df_hist.iloc[:0]

    top = (pd.DataFrame(windows, columns=["t0","t1","score"])
             .sort_values("score")
             .head(k))

    parts = [df_hist.loc[t0:t1] for t0, t1, _ in top.itertuples(index=False)]
    return pd.concat(parts, axis=0)