import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance


# ============================
#   MÉTRICAS NUMÉRICAS
# ============================

def psi_numeric(ref, cur, bins=10):
    """Population Stability Index."""
    ref = pd.Series(ref).dropna()
    cur = pd.Series(cur).dropna()

    if ref.empty or cur.empty:
        return np.nan

    quantiles = np.linspace(0, 1, bins + 1)
    cuts = np.quantile(ref, quantiles)

    ref_dist = np.histogram(ref, bins=cuts)[0] / len(ref)
    cur_dist = np.histogram(cur, bins=cuts)[0] / len(cur)

    ref_dist = np.where(ref_dist == 0, 1e-6, ref_dist)
    cur_dist = np.where(cur_dist == 0, 1e-6, cur_dist)

    return float(np.sum((ref_dist - cur_dist) * np.log(ref_dist / cur_dist)))

def ks_numeric(ref, cur):
    """Kolmogorov–Smirnov Test."""
    ref = pd.Series(ref).dropna()
    cur = pd.Series(cur).dropna()
    if ref.empty or cur.empty:
        return np.nan
    return float(ks_2samp(ref, cur).statistic)

def wasserstein_numeric(ref, cur):
    """1st Wasserstein Distance."""
    ref = pd.Series(ref).dropna()
    cur = pd.Series(cur).dropna()
    if ref.empty or cur.empty:
        return np.nan
    return float(wasserstein_distance(ref, cur))


# ============================
#   SCORE GENÉRICO
# ============================

def _score_numeric_series(ref, cur, metric: str):
    """Wrapper genérico para unificar PSI, KS, Wasserstein."""
    if metric == "psi":
        return psi_numeric(ref, cur)
    if metric == "ks":
        return ks_numeric(ref, cur)
    if metric == "wasserstein":
        return wasserstein_numeric(ref, cur)
    raise ValueError(f"Metric '{metric}' no implementada.")


# ============================
#   REFERENCIAS POR ESTRATEGIA
# ============================

def ref_decay_prefix_mass(df_hist, now=None, alpha=0.95):
    """Referencia tipo 'decay': EMA por variable."""
    return df_hist.ewm(alpha=1 - alpha, adjust=False).mean()


def ref_golden(df_hist):
    """Referencia tipo 'golden': media + varianza robusta."""
    return df_hist.rolling("48h").mean()


def ref_seasonal(df_hist, current_end=None):
    """Referencia estacional: último periodo."""
    window = "24h"
    return df_hist.last(window)
